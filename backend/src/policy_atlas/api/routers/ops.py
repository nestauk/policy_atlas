"""Authenticated operations-host routes (task 065, B4 and C5)."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Generator
from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.engine import Connection, RowMapping

from policy_atlas.api.app import ApiCapacity, ApiConflict
from policy_atlas.api.auth import AuthenticatedUser, get_current_user
from policy_atlas.api.contract.ops import (
    ActionResult,
    ApproveRequest,
    AssignmentOut,
    BulkEnrol,
    BulkOut,
    BulkQuota,
    BulkSubjects,
    LimitsOut,
    OrganisationCreate,
    OrganisationOut,
    PersonCreate,
    PersonCreatedOut,
    PersonOut,
    QuotaSet,
    RequestOut,
    RequestsOut,
    RowAssign,
    SelfSignupOut,
)
from policy_atlas.api.contract.tenancy import OrganisationRef
from policy_atlas.api.deps import Identity, get_conn, get_identity, get_settings
from policy_atlas.api.routers.common import effective_limits
from policy_atlas.api.settings import Settings
from policy_atlas.core.schema import (
    app_user,
    ops_action,
    organisation,
    organisation_domain,
    task,
    waitlist_entry,
)
from policy_atlas.ops import commands
from policy_atlas.ops.errors import EnrolledElsewhere, OpsError, ResendTooSoon

log = structlog.get_logger()


def require_ops(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> AuthenticatedUser:
    """Return an operations-role holder without creating an identity row."""
    is_ops = conn.execute(
        select(app_user.c.is_ops).where(app_user.c.user_id == user.user_id)
    ).scalar_one_or_none()
    if not is_ops:
        raise HTTPException(403, "your account does not have the ops role")
    return user


def after_commit(request: Request) -> Generator[None, None, None]:
    """Emit queued action traces only after the request transaction commits."""
    request.state.ops_log = []
    try:
        yield
    except BaseException:
        raise
    else:
        for line in request.state.ops_log:
            log.info("ops.action", **line)


router = APIRouter(
    prefix="/api/v1/ops",
    tags=["ops"],
    dependencies=[Depends(after_commit), Depends(require_ops)],
)


def _now() -> datetime:
    """Return an aware UTC timestamp for command functions."""
    return datetime.now(UTC)


def _identity(identity: Identity) -> tuple[Any, str]:
    """Return the configured Cognito client and user pool or refuse the write."""
    if identity.cognito is None or identity.pool_id is None:
        raise HTTPException(503, "identity provider is not configured")
    return identity.cognito, identity.pool_id


def _queue_log(
    request: Request, *, actor: str, action: str, target: str, outcome: str, action_id: uuid.UUID
) -> None:
    """Queue an email-free trace for :func:`after_commit`."""
    request.state.ops_log.append(
        {"actor": actor, "action": action, "target": target, "outcome": outcome,
         "action_id": str(action_id)}
    )


def _org(conn: Connection, org_id: uuid.UUID) -> commands.Organisation:
    """Resolve an organisation id or return the ordinary resource 404."""
    name = conn.execute(
        select(organisation.c.name).where(organisation.c.org_id == org_id)
    ).scalar_one_or_none()
    if name is None:
        raise HTTPException(404, f"no organisation {org_id}")
    return commands.Organisation(org_id=org_id, name=str(name))


def _organisation_out(conn: Connection, org_id: uuid.UUID) -> OrganisationOut:
    """Project one organisation with its operational counts and domains."""
    row = conn.execute(select(organisation).where(organisation.c.org_id == org_id)).mappings().one()
    people = int(conn.execute(
        select(func.count()).where(app_user.c.org_id == org_id)
    ).scalar_one())
    domains = list(conn.execute(
        select(organisation_domain.c.domain).where(organisation_domain.c.org_id == org_id)
        .order_by(organisation_domain.c.domain)
    ).scalars())
    return OrganisationOut(people=people, domains=domains, **row)


def _person_out(
    conn: Connection, row: RowMapping, *, settings: Settings, task_counts: dict[str, int]
) -> PersonOut:
    """Project one people-list row, resolving its effective limits."""
    values = dict(row)
    org_id = values.pop("organisation_id")
    org_name = values.pop("organisation_name")
    user_id = str(values["user_id"])
    limits = effective_limits(conn, user_id, settings=settings)
    return PersonOut(
        **values,
        organisation=(
            OrganisationRef(org_id=org_id, name=org_name) if org_id is not None else None
        ),
        tasks_this_year=task_counts.get(user_id, 0),
        limits=LimitsOut(task_quota_per_year=limits.task_quota, runs_per_user=limits.runs),
    )


@router.get("/organisations", response_model=list[OrganisationOut])
def list_organisations(conn: Annotated[Connection, Depends(get_conn)]) -> list[OrganisationOut]:
    """List organisations alphabetically with their people and domains."""
    rows = conn.execute(
        select(organisation, func.count(app_user.c.user_id).label("people"))
        .outerjoin(app_user, app_user.c.org_id == organisation.c.org_id)
        .group_by(*organisation.c)
        .order_by(organisation.c.name)
    ).mappings().all()
    domains: dict[uuid.UUID, list[str]] = {}
    for org_id, domain in conn.execute(
        select(organisation_domain.c.org_id, organisation_domain.c.domain).order_by(
            organisation_domain.c.domain
        )
    ):
        domains.setdefault(org_id, []).append(domain)
    return [
        OrganisationOut(domains=domains.get(row["org_id"], []), **row)
        for row in rows
    ]


@router.post("/organisations", response_model=OrganisationOut, status_code=status.HTTP_201_CREATED)
def create_organisation(
    body: OrganisationCreate, request: Request,
    actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> OrganisationOut:
    """Create an organisation and its durable audit record."""
    try:
        created = commands.create_organisation(conn, name=body.name)
    except OpsError as exc:
        raise ApiConflict("ops_refused", str(exc)) from None
    action_id = commands.record_action(conn, actor=actor.user_id, action="org.create",
                                       target=str(created.org_id), outcome="ok")
    _queue_log(request, actor=actor.user_id, action="org.create", target=str(created.org_id),
               outcome="ok", action_id=action_id)
    return _organisation_out(conn, created.org_id)


@router.post("/organisations/{org_id}/quota", response_model=OrganisationOut)
def set_organisation_quota(
    org_id: uuid.UUID, body: QuotaSet, request: Request,
    actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> OrganisationOut:
    """Set or clear an organisation's quota overrides."""
    try:
        commands.set_quota(conn, org_id=org_id, **body.model_dump())
    except OpsError as exc:
        if str(exc).startswith("no organisation"):
            raise HTTPException(404, str(exc)) from None
        raise ApiConflict("ops_refused", str(exc)) from None
    action_id = commands.record_action(conn, actor=actor.user_id, action="org.quota",
                                       target=str(org_id), outcome="ok")
    _queue_log(request, actor=actor.user_id, action="org.quota", target=str(org_id),
               outcome="ok", action_id=action_id)
    return _organisation_out(conn, org_id)


@router.get("/people", response_model=list[PersonOut])
def list_people(
    conn: Annotated[Connection, Depends(get_conn)],
    settings: Annotated[Settings, Depends(get_settings)],
    q: str | None = None,
) -> list[PersonOut]:
    """List people, optionally matching a literal case-insensitive search string."""
    query = select(
        app_user, organisation.c.org_id.label("organisation_id"),
        organisation.c.name.label("organisation_name"),
    ).outerjoin(organisation, organisation.c.org_id == app_user.c.org_id)
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        query = query.where(or_(
            app_user.c.display_name.ilike(pattern, escape="\\"),
            app_user.c.email.ilike(pattern, escape="\\"),
            organisation.c.name.ilike(pattern, escape="\\"),
        ))
    rows = conn.execute(
        query.order_by(app_user.c.display_name, app_user.c.user_id)
    ).mappings().all()
    subjects = [str(row["user_id"]) for row in rows]
    # ponytail: the people list is under one hundred rows; this grouped task query
    # and one effective-limits lookup per person are sufficient, with no cache.
    task_counts = {
        str(row["owner_user_id"]): int(row["count"])
        for row in conn.execute(
            select(task.c.owner_user_id, func.count().label("count"))
            .where(task.c.owner_user_id.in_(subjects))
            .where(task.c.created_at >= func.now() - func.make_interval(0, 0, 0, 365))
            .group_by(task.c.owner_user_id)
        ).mappings()
    } if subjects else {}
    return [_person_out(conn, row, settings=settings, task_counts=task_counts) for row in rows]


@router.post("/people", response_model=PersonCreatedOut, status_code=status.HTTP_201_CREATED)
def create_person(
    body: PersonCreate, request: Request,
    actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
    identity: Annotated[Identity, Depends(get_identity)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PersonCreatedOut:
    """Ensure a person is invited and enrolled in the requested organisation."""
    cognito, pool_id = _identity(identity)
    org = _org(conn, body.org_id)
    try:
        enrolled = commands.ensure_account_enrolled(
            conn, cognito, pool_id=pool_id, email=body.email,
            display_name=body.display_name, org=org,
        )
    except EnrolledElsewhere as exc:
        raise ApiConflict("enrolled_elsewhere", str(exc)) from None
    except OpsError as exc:
        raise ApiConflict("ops_refused", str(exc)) from None
    outcome = "invited" if enrolled.invitation_sent else "enrolled"
    action_id = commands.record_action(conn, actor=actor.user_id, action="person.create",
                                       target=enrolled.user_id, outcome=outcome)
    _queue_log(request, actor=actor.user_id, action="person.create", target=enrolled.user_id,
               outcome=outcome, action_id=action_id)
    row = conn.execute(
        select(app_user, organisation.c.org_id.label("organisation_id"),
               organisation.c.name.label("organisation_name"))
        .outerjoin(organisation, organisation.c.org_id == app_user.c.org_id)
        .where(app_user.c.user_id == enrolled.user_id)
    ).mappings().one()
    return PersonCreatedOut(
        person=_person_out(conn, row, settings=settings, task_counts={}),
        invitation_sent=enrolled.invitation_sent,
    )


def _bulk(
    *, request: Request, actor: str, conn: Connection, user_ids: list[str], action: str,
    run: Callable[[str], str], skip: Callable[[Exception], bool] | None = None,
) -> BulkOut:
    """Run a command per subject in savepoints and audit every non-skipped result."""
    results: list[ActionResult] = []
    for user_id in user_ids:
        try:
            with conn.begin_nested():
                message = run(user_id)
                action_id = commands.record_action(
                    conn, actor=actor, action=action, target=user_id, outcome="ok"
                )
            _queue_log(request, actor=actor, action=action, target=user_id, outcome="ok",
                       action_id=action_id)
            results.append(ActionResult(user_id=user_id, outcome="ok", message=message,
                                        action_id=action_id))
        except Exception as exc:
            if skip is not None and skip(exc):
                # Nothing happened, so no audit row and no id.
                results.append(ActionResult(user_id=user_id, outcome="too_soon",
                                            message=str(exc), action_id=None))
                continue
            action_id = commands.record_action(
                conn, actor=actor, action=action, target=user_id, outcome="failed"
            )
            _queue_log(request, actor=actor, action=action, target=user_id, outcome="failed",
                       action_id=action_id)
            results.append(ActionResult(user_id=user_id, outcome="failed", message=str(exc),
                                        action_id=action_id))
    return BulkOut(results=results)


@router.post("/people/enrol", response_model=BulkOut)
def enrol_people(
    body: BulkEnrol, request: Request, actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> BulkOut:
    """Move each selected person to the destination organisation."""
    org = _org(conn, body.org_id)
    return _bulk(request=request, actor=actor.user_id, conn=conn, user_ids=body.user_ids,
                 action="person.move",
                 run=lambda user_id: commands.move_user(conn, sub=user_id, org=org).summary())


@router.post("/people/de-enrol", response_model=BulkOut)
def de_enrol_people(
    body: BulkSubjects, request: Request, actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> BulkOut:
    """De-enrol every selected person independently."""
    return _bulk(request=request, actor=actor.user_id, conn=conn, user_ids=body.user_ids,
                 action="person.de_enrol",
                 run=lambda user_id: commands.de_enrol_user(conn, sub=user_id).summary())


@router.post("/people/offboard", response_model=BulkOut)
def offboard_people(
    body: BulkSubjects, request: Request, actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
    identity: Annotated[Identity, Depends(get_identity)],
) -> BulkOut:
    """Disable and offboard every selected person independently."""
    cognito, pool_id = _identity(identity)
    return _bulk(request=request, actor=actor.user_id, conn=conn, user_ids=body.user_ids,
                 action="person.offboard", run=lambda user_id: commands.offboard_user(
                     conn, cognito, pool_id=pool_id, sub=user_id
                 ).summary())


@router.post("/people/resend", response_model=BulkOut)
def resend_people(
    body: BulkSubjects, request: Request,
    actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
    identity: Annotated[Identity, Depends(get_identity)],
) -> BulkOut:
    """Re-send eligible invitations, reporting cooldowns without audit rows."""
    cognito, pool_id = _identity(identity)
    now = _now()
    result = _bulk(
        request=request, actor=actor.user_id, conn=conn, user_ids=body.user_ids,
        action="person.resend",
        run=lambda user_id: commands.resend_invitation(
            conn, cognito, pool_id=pool_id, sub=user_id, now=now
        ).summary(),
        skip=lambda exc: isinstance(exc, ResendTooSoon),
    )
    cooling = [item for item in result.results if item.outcome == "too_soon"]
    if len(cooling) == len(result.results):
        # Contract B4: one person inside the hour is a 429; the message
        # carries the retry time (the envelope handler builds the response,
        # so a header set here would not reach the client).
        raise ApiCapacity("resend_cooldown", cooling[0].message)
    return result


@router.post("/people/quota", response_model=BulkOut)
def set_people_quota(
    body: BulkQuota, request: Request, actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> BulkOut:
    """Set the same quota overrides for every selected person."""
    return _bulk(
        request=request, actor=actor.user_id, conn=conn, user_ids=body.user_ids,
        action="person.quota", run=lambda user_id: commands.set_quota(
            conn, user_id=user_id, task_quota_per_year=body.task_quota_per_year,
            runs_per_user=body.runs_per_user,
        ).summary(),
    )


@router.get("/requests", response_model=RequestsOut)
def list_requests(
    conn: Annotated[Connection, Depends(get_conn)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RequestsOut:
    """List waitlist rows and their sweep-derived operational state."""
    rows = conn.execute(
        select(waitlist_entry).order_by(waitlist_entry.c.created_at, waitlist_entry.c.entry_id)
    ).mappings().all()
    ids = [str(row["entry_id"]) for row in rows]
    terminal = set(conn.execute(
        select(ops_action.c.target).where(
            ops_action.c.actor_user_id == "sweep", ops_action.c.action == "invite",
            ops_action.c.outcome == "enrolled_elsewhere", ops_action.c.target.in_(ids),
        )
    ).scalars()) if ids else set()
    domains = list(conn.execute(
        select(organisation_domain.c.domain).order_by(organisation_domain.c.domain)
    ).scalars())
    sent = int(conn.execute(select(func.count()).select_from(ops_action).where(
        ops_action.c.actor_user_id == "sweep", ops_action.c.action == "invite",
        ops_action.c.outcome == "invited",
        ops_action.c.at >= func.now() - func.make_interval(0, 0, 0, 0, 1),
    )).scalar_one())
    items: list[RequestOut] = []
    for row in rows:
        check = str(row["entry_id"]) in terminal
        note = None
        if check:
            note = conn.execute(
                select(organisation.c.name).select_from(
                    app_user.join(organisation, organisation.c.org_id == app_user.c.org_id)
                ).where(app_user.c.email == row["email"])
            ).scalar_one_or_none()
        items.append(RequestOut(
            **row,
            status="invited" if row["account_created_at"] is not None else
            "check" if check else "waiting",
            note=note,
        ))
    return RequestsOut(
        items=items,
        self_signup=SelfSignupOut(enabled=settings.self_signup_enabled, domains=domains,
                                 sent_this_hour=sent,
                                 max_per_hour=settings.self_signup_max_per_hour),
    )


@router.post("/requests/{entry_id}/approve", response_model=RequestOut)
def approve_request(
    entry_id: uuid.UUID, body: ApproveRequest, request: Request,
    actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
    identity: Annotated[Identity, Depends(get_identity)],
) -> RequestOut:
    """Approve a waitlist request using the shared sweep command."""
    cognito, pool_id = _identity(identity)
    org = _org(conn, body.org_id)
    try:
        approved = commands.approve_request(
            conn, cognito, pool_id=pool_id, entry_id=entry_id, org=org, now=_now()
        )
    except EnrolledElsewhere as exc:
        raise ApiConflict("enrolled_elsewhere", str(exc)) from None
    except OpsError as exc:
        raise ApiConflict("ops_refused", str(exc)) from None
    outcome = "invited" if approved.enrolment.invitation_sent else "enrolled"
    action_id = commands.record_action(
        conn, actor=actor.user_id, action="request.approve", target=str(entry_id), outcome=outcome
    )
    _queue_log(request, actor=actor.user_id, action="request.approve", target=str(entry_id),
               outcome=outcome, action_id=action_id)
    row = conn.execute(
        select(waitlist_entry).where(waitlist_entry.c.entry_id == entry_id)
    ).mappings().one()
    return RequestOut(**row, status="invited")


@router.post("/rows/assign", response_model=AssignmentOut)
def assign_rows(
    body: RowAssign, request: Request, actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> AssignmentOut:
    """Assign exactly one task or project to an organisation."""
    org = _org(conn, body.org_id)
    if (body.task_id is None) == (body.project_id is None):
        raise HTTPException(422, "give exactly one of task_id or project_id")
    try:
        assignment = commands.assign_rows(
            conn, org=org, task_id=body.task_id, project_id=body.project_id
        )
    except OpsError as exc:
        if str(exc).startswith(("no task", "no project")):
            raise HTTPException(404, str(exc)) from None
        raise HTTPException(422, str(exc)) from None
    target = str(body.task_id or body.project_id)
    action_id = commands.record_action(
        conn, actor=actor.user_id, action="rows.assign", target=target, outcome="ok"
    )
    _queue_log(request, actor=actor.user_id, action="rows.assign", target=target,
               outcome="ok", action_id=action_id)
    return AssignmentOut(
        org=OrganisationRef(org_id=org.org_id, name=org.name),
        project_id=assignment.project_id, tasks_moved=assignment.tasks_moved,
        projects_moved=assignment.projects_moved,
        followed_membership=assignment.followed_membership,
        privatised=assignment.privatised, message=assignment.summary(), action_id=action_id,
    )
