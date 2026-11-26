"""Authenticated operations-host routes (task 065, B4 and C5)."""

from __future__ import annotations

import csv
import io
import uuid
from collections.abc import Callable, Generator
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, or_, select, true
from sqlalchemy.engine import Connection, RowMapping

from policy_atlas.api.app import ApiCapacity, ApiConflict
from policy_atlas.api.auth import AuthenticatedUser, get_current_user
from policy_atlas.api.contract.ops import (
    IMPORT_CHARACTERS_MAX,
    IMPORT_PEOPLE_MAX,
    ActionResult,
    ApproveRequest,
    BulkCohort,
    BulkEnrol,
    BulkOut,
    BulkQuota,
    BulkSubjects,
    CohortOut,
    CohortRef,
    CohortSave,
    ImportCheck,
    ImportCheckOut,
    ImportProblem,
    ImportRow,
    InviteLinkCreate,
    InviteLinkOut,
    InviteLinkUpdate,
    LimitSourceOut,
    LimitsOut,
    OrganisationCreate,
    OrganisationOut,
    PersonCreate,
    PersonCreatedOut,
    PersonOut,
    QuotaSet,
    RequestInvite,
    RequestOut,
    RequestsOut,
    SelfSignupOut,
    validate_person_fields,
)
from policy_atlas.api.contract.tenancy import OrganisationRef
from policy_atlas.api.deps import Identity, get_conn, get_identity, get_settings
from policy_atlas.api.routers.common import created_in_last_days, effective_limits
from policy_atlas.api.settings import Settings
from policy_atlas.core import invite_code
from policy_atlas.core.schema import (
    app_user,
    cohort,
    cohort_member,
    invite_link,
    invite_link_cohort,
    ops_action,
    organisation,
    organisation_domain,
    task,
    waitlist_entry,
)
from policy_atlas.ops import commands
from policy_atlas.ops.errors import EnrolledElsewhere, NotFound, OpsError, ResendTooSoon
from policy_atlas.ops.sweep import RETRY_WAIT, TERMINAL_OUTCOMES

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


def _cognito_refusal(error: ClientError) -> str:
    """Name a Cognito refusal by its code only (no address, no request detail)."""
    code = error.response.get("Error", {}).get("Code", "") or "ClientError"
    return f"Cognito refused the request ({code}). Nothing was written."


def _not_self(actor: AuthenticatedUser, user_id: str) -> str:
    """Refuse the caller as a subject of de-enrol or deactivate.

    "Select everyone shown" includes the operator; locking yourself out is
    never what a bulk action meant (review stack, 2026-11-17). The CLI can.
    """
    if user_id == actor.user_id:
        raise OpsError("you cannot de-enrol or deactivate your own account from here")
    return user_id


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
    conn: Connection, row: RowMapping, *, settings: Settings, task_counts: dict[str, int],
    cohorts: dict[str, list[CohortRef]] | None = None,
    last_tasks: dict[str, datetime] | None = None,
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
        last_task_at=(last_tasks or {}).get(user_id),
        limits=LimitsOut(
            task_quota_per_year=limits.task_quota, runs_per_user=limits.runs,
            task_quota_from=LimitSourceOut(**asdict(limits.task_quota_from)),
            runs_from=LimitSourceOut(**asdict(limits.runs_from)),
        ),
        cohorts=(cohorts or {}).get(user_id, []),
    )


def _cohorts_of(conn: Connection, user_ids: list[str]) -> dict[str, list[CohortRef]]:
    """Each person's cohorts, by name."""
    found: dict[str, list[CohortRef]] = {}
    if not user_ids:
        return found
    for user_id, cohort_id, name in conn.execute(
        select(cohort_member.c.user_id, cohort.c.cohort_id, cohort.c.name)
        .join(cohort, cohort.c.cohort_id == cohort_member.c.cohort_id)
        .where(cohort_member.c.user_id.in_(user_ids))
        .order_by(cohort.c.name)
    ):
        found.setdefault(str(user_id), []).append(CohortRef(cohort_id=cohort_id, name=name))
    return found


def _cohort_rows(conn: Connection, cohort_id: uuid.UUID | None = None) -> list[CohortOut]:
    """Cohorts with their member counts, by name; or the one cohort asked for."""
    query = (
        select(cohort, func.count(cohort_member.c.user_id).label("people"))
        .outerjoin(cohort_member, cohort_member.c.cohort_id == cohort.c.cohort_id)
        .group_by(*cohort.c)
        .order_by(cohort.c.name)
    )
    if cohort_id is not None:
        query = query.where(cohort.c.cohort_id == cohort_id)
    return [CohortOut(**row) for row in conn.execute(query).mappings()]


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


@router.delete("/organisations/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organisation(
    org_id: uuid.UUID, request: Request,
    actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> Response:
    """Delete an organisation nothing points at; otherwise say what is still in it."""
    try:
        commands.delete_organisation(conn, org_id=org_id)
    except NotFound as exc:
        raise HTTPException(404, str(exc)) from None
    except OpsError as exc:
        raise ApiConflict("ops_refused", str(exc)) from None
    _audit(request, conn, actor=actor.user_id, action="organisation.delete", target=str(org_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/organisations/{org_id}/quota", response_model=OrganisationOut)
def set_organisation_quota(
    org_id: uuid.UUID, body: QuotaSet, request: Request,
    actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> OrganisationOut:
    """Set or clear an organisation's quota overrides."""
    try:
        change = commands.set_quota(conn, org_id=org_id, **body.model_dump())
    except NotFound as exc:
        raise HTTPException(404, str(exc)) from None
    except OpsError as exc:
        raise ApiConflict("ops_refused", str(exc)) from None
    _audit(request, conn, actor=actor.user_id, action="org.quota", target=change.audit_target())
    return _organisation_out(conn, org_id)


def _audit(request: Request, conn: Connection, *, actor: str, action: str, target: str) -> None:
    """Write one ok audit row and queue its trace."""
    action_id = commands.record_action(conn, actor=actor, action=action, target=target,
                                       outcome="ok")
    _queue_log(request, actor=actor, action=action, target=target, outcome="ok",
               action_id=action_id)


@router.get("/cohorts", response_model=list[CohortOut])
def list_cohorts(conn: Annotated[Connection, Depends(get_conn)]) -> list[CohortOut]:
    """List cohorts by name with how many people each holds."""
    return _cohort_rows(conn)


def _save(conn: Connection, cohort_id: uuid.UUID | None, body: CohortSave) -> commands.Cohort:
    """Run the save command, mapping its refusals to the ordinary errors."""
    try:
        return commands.save_cohort(conn, cohort_id=cohort_id, **body.model_dump())
    except NotFound as exc:
        raise HTTPException(404, str(exc)) from None
    except OpsError as exc:
        raise ApiConflict("ops_refused", str(exc)) from None


@router.post("/cohorts", response_model=CohortOut, status_code=status.HTTP_201_CREATED)
def create_cohort(
    body: CohortSave, request: Request,
    actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> CohortOut:
    """Create a cohort and its audit record."""
    saved = _save(conn, None, body)
    _audit(request, conn, actor=actor.user_id, action="cohort.create", target=str(saved.cohort_id))
    return _cohort_rows(conn, saved.cohort_id)[0]


@router.post("/cohorts/{cohort_id}", response_model=CohortOut)
def update_cohort(
    cohort_id: uuid.UUID, body: CohortSave, request: Request,
    actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> CohortOut:
    """Replace a cohort's details; its members are untouched."""
    _save(conn, cohort_id, body)
    _audit(request, conn, actor=actor.user_id, action="cohort.update", target=str(cohort_id))
    return _cohort_rows(conn, cohort_id)[0]


@router.post("/cohorts/{cohort_id}/quota", response_model=CohortOut)
def set_cohort_quota(
    cohort_id: uuid.UUID, body: QuotaSet, request: Request,
    actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> CohortOut:
    """Set or clear a cohort's quota overrides."""
    try:
        change = commands.set_quota(conn, cohort_id=cohort_id, **body.model_dump())
    except NotFound as exc:
        raise HTTPException(404, str(exc)) from None
    _audit(request, conn, actor=actor.user_id, action="cohort.quota",
           target=change.audit_target())
    return _cohort_rows(conn, cohort_id)[0]


@router.delete("/cohorts/{cohort_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cohort(
    cohort_id: uuid.UUID, request: Request,
    actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> Response:
    """Delete a cohort and its memberships; the people are untouched."""
    try:
        commands.delete_cohort(conn, cohort_id=cohort_id)
    except NotFound as exc:
        raise HTTPException(404, str(exc)) from None
    _audit(request, conn, actor=actor.user_id, action="cohort.delete", target=str(cohort_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    task_rows = conn.execute(
        select(
            task.c.owner_user_id,
            func.count().filter(created_in_last_days(365)),
            func.max(task.c.created_at),
        )
        .where(task.c.owner_user_id.in_(subjects))
        .group_by(task.c.owner_user_id)
    ).all() if subjects else []
    task_counts = {str(owner): int(count) for owner, count, _ in task_rows}
    last_tasks = {str(owner): at for owner, _, at in task_rows}
    cohorts = _cohorts_of(conn, subjects)
    return [
        _person_out(conn, row, settings=settings, task_counts=task_counts, cohorts=cohorts,
                    last_tasks=last_tasks)
        for row in rows
    ]


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
    cohorts = [_cohort(conn, cohort_id) for cohort_id in body.cohort_ids]
    try:
        enrolled = commands.ensure_account_enrolled(
            conn, cognito, pool_id=pool_id, email=body.email,
            display_name=body.display_name, org=org, reactivate=True,
        )
    except EnrolledElsewhere as exc:
        raise ApiConflict("enrolled_elsewhere", str(exc)) from None
    except OpsError as exc:
        raise ApiConflict("ops_refused", str(exc)) from None
    except ClientError as exc:
        raise ApiConflict("ops_refused", _cognito_refusal(exc)) from None
    outcome = "invited" if enrolled.invitation_sent else "enrolled"
    if enrolled.reactivated:
        outcome = f"reactivated, {outcome}"
    action_id = commands.record_action(conn, actor=actor.user_id, action="person.create",
                                       target=enrolled.user_id, outcome=outcome)
    _queue_log(request, actor=actor.user_id, action="person.create", target=enrolled.user_id,
               outcome=outcome, action_id=action_id)
    _join_cohorts(request, conn, actor=actor.user_id, user_id=enrolled.user_id, cohorts=cohorts)
    row = conn.execute(
        select(app_user, organisation.c.org_id.label("organisation_id"),
               organisation.c.name.label("organisation_name"))
        .outerjoin(organisation, organisation.c.org_id == app_user.c.org_id)
        .where(app_user.c.user_id == enrolled.user_id)
    ).mappings().one()
    return PersonCreatedOut(
        person=_person_out(conn, row, settings=settings, task_counts={},
                           cohorts=_cohorts_of(conn, [enrolled.user_id])),
        invitation_sent=enrolled.invitation_sent,
        reactivated=enrolled.reactivated,
    )


def _people_file_problem(values: list[str], header: list[str]) -> str | None:
    """Name the first fault of one record of a people file, or ``None``."""
    if len(values) != len(header):
        return f"this line has {len(values)} values; it needs 2: email and name."
    fields = dict(zip(header, values, strict=True))
    for column, article in (("email", "an"), ("name", "a")):
        if "\n" in fields[column] or "\r" in fields[column]:
            return f"{article} {column} cannot hold a line break."
    try:
        validate_person_fields(fields["email"], fields["name"])
    except ValueError as exc:
        return str(exc)
    return None


def check_people_file(text: str) -> ImportCheckOut:
    """Read a people file (CSV text) and answer its good lines and its faults.

    Python's ``csv`` reader in strict mode does the reading. A line number is
    the file line where the record starts, counting the header as line 1.

    Args:
        text: The file as the browser decoded it (UTF-8; a byte-order mark is allowed).

    Returns:
        The good lines with the address lower-cased, and every fault found.
    """
    def whole_file(message: str) -> ImportCheckOut:
        return ImportCheckOut(rows=[], errors=[ImportProblem(message=message)])

    if len(text) > IMPORT_CHARACTERS_MAX:
        return whole_file(f"A file can hold at most {IMPORT_CHARACTERS_MAX:,} characters.")
    if "\ufffd" in text:
        return whole_file(
            "This file is not saved as UTF-8. Save it as CSV UTF-8 and choose it again."
        )
    reader = csv.reader(io.StringIO(text.removeprefix("\ufeff"), newline=""), strict=True)
    records: list[tuple[int, list[str]]] = []
    start = 1
    try:
        for values in reader:
            records.append((start, values))
            start = reader.line_num + 1
    except csv.Error:
        return ImportCheckOut(rows=[], errors=[ImportProblem(
            line=start, message="the quotes on this line do not follow the CSV rules.")])
    header = [name.strip().lower() for name in records[0][1]] if records else []
    if sorted(header) != ["email", "name"]:
        if {"email", "name"} <= set(header):
            return whole_file("The file can have only the columns email and name, each once.")
        return whole_file("The file needs the columns email and name.")
    people = [(line, values) for line, values in records[1:]
              if any(value.strip() for value in values)]
    if len(people) > IMPORT_PEOPLE_MAX:
        return whole_file(f"A file can hold at most {IMPORT_PEOPLE_MAX} people.")
    rows: list[ImportRow] = []
    errors: list[ImportProblem] = []
    first_line: dict[str, int] = {}
    for line, values in people:
        problem = _people_file_problem(values, header)
        if problem is None:
            fields = dict(zip(header, values, strict=True))
            email, name = validate_person_fields(fields["email"], fields["name"])
            if email in first_line:
                problem = f"this email is already on line {first_line[email]}."
            else:
                first_line[email] = line
                rows.append(ImportRow(line=line, email=email, display_name=name))
        if problem is not None:
            errors.append(ImportProblem(line=line, message=problem))
    return ImportCheckOut(rows=rows, errors=errors)


@router.post("/people/import-check", response_model=ImportCheckOut)
def check_people_import(body: ImportCheck) -> ImportCheckOut:
    """Check a people file before the page creates its people; writes nothing."""
    return check_people_file(body.csv)


def _bulk(
    *, request: Request, actor: str, conn: Connection, user_ids: list[str], action: str,
    run: Callable[[str], str], skip: Callable[[Exception], bool] | None = None,
    target_of: Callable[[str], str] = str,
) -> BulkOut:
    """Run a command per subject in savepoints and audit every non-skipped result.

    ``target_of`` turns a subject into the audit row's target, when the row
    must say more than who (the cohort, or a quota's before and after).
    """
    results: list[ActionResult] = []
    for user_id in user_ids:
        try:
            with conn.begin_nested():
                message = run(user_id)
                target = target_of(user_id)
                action_id = commands.record_action(
                    conn, actor=actor, action=action, target=target, outcome="ok"
                )
            _queue_log(request, actor=actor, action=action, target=target, outcome="ok",
                       action_id=action_id)
            results.append(ActionResult(user_id=user_id, outcome="ok", message=message,
                                        action_id=action_id))
        except Exception as exc:
            if skip is not None and skip(exc):
                # Nothing happened, so no audit row and no id.
                results.append(ActionResult(user_id=user_id, outcome="too_soon",
                                            message=str(exc), action_id=None))
                continue
            target = target_of(user_id)
            action_id = commands.record_action(
                conn, actor=actor, action=action, target=target, outcome="failed"
            )
            _queue_log(request, actor=actor, action=action, target=target, outcome="failed",
                       action_id=action_id)
            # A refusal is written for the operator; anything else (a database
            # or Cognito error) stays out of the browser.
            message = str(exc) if isinstance(exc, OpsError) else f"failed; see action {action_id}"
            results.append(ActionResult(user_id=user_id, outcome="failed", message=message,
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
                 run=lambda user_id: commands.de_enrol_user(
                     conn, sub=_not_self(actor, user_id)
                 ).summary())


@router.post("/people/deactivate", response_model=BulkOut)
def deactivate_people(
    body: BulkSubjects, request: Request, actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
    identity: Annotated[Identity, Depends(get_identity)],
) -> BulkOut:
    """Disable and mark every selected person independently; they keep their organisation."""
    cognito, pool_id = _identity(identity)
    return _bulk(request=request, actor=actor.user_id, conn=conn, user_ids=body.user_ids,
                 action="person.deactivate", run=lambda user_id: commands.deactivate_user(
                     conn, cognito, pool_id=pool_id, sub=_not_self(actor, user_id)
                 ).summary())


@router.post("/people/reactivate", response_model=BulkOut)
def reactivate_people(
    body: BulkSubjects, request: Request, actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
    identity: Annotated[Identity, Depends(get_identity)],
) -> BulkOut:
    """Turn every selected person's login back on; roles are not restored."""
    cognito, pool_id = _identity(identity)
    return _bulk(request=request, actor=actor.user_id, conn=conn, user_ids=body.user_ids,
                 action="person.reactivate", run=lambda user_id: commands.reactivate_user(
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
        # One person inside the hour is a 429; the message
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
    # Each change's before and after, for its audit row; a failure has none.
    targets: dict[str, str] = {}

    def run(user_id: str) -> str:
        change = commands.set_quota(
            conn, user_id=user_id, task_quota_per_year=body.task_quota_per_year,
            runs_per_user=body.runs_per_user,
        )
        targets[user_id] = change.audit_target()
        return change.summary()

    return _bulk(
        request=request, actor=actor.user_id, conn=conn, user_ids=body.user_ids,
        action="person.quota", run=run,
        target_of=lambda user_id: targets.get(user_id, user_id),
    )


def _cohort(conn: Connection, cohort_id: uuid.UUID) -> commands.Cohort:
    """Resolve a cohort id or return the ordinary resource 404."""
    try:
        return commands.resolve_cohort(conn, cohort_id)
    except NotFound as exc:
        raise HTTPException(404, str(exc)) from None


def _join_cohorts(
    request: Request, conn: Connection, *, actor: str, user_id: str,
    cohorts: list[commands.Cohort],
) -> None:
    """Add a person to each cohort, auditing only the memberships that are new.

    Runs on the caller's transaction after the enrolment: a failure here rolls
    the enrolment back too.
    """
    for target in cohorts:
        if commands.add_to_cohort(conn, target=target, user_id=user_id).changed:
            _audit(request, conn, actor=actor, action="cohort.add",
                   target=f"{user_id}/cohort/{target.cohort_id}")


@router.post("/people/cohort-add", response_model=BulkOut)
def add_people_to_cohort(
    body: BulkCohort, request: Request, actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> BulkOut:
    """Add every selected person to one cohort."""
    target = _cohort(conn, body.cohort_id)
    return _bulk(request=request, actor=actor.user_id, conn=conn, user_ids=body.user_ids,
                 action="cohort.add", run=lambda user_id: commands.add_to_cohort(
                     conn, target=target, user_id=user_id).summary(),
                 target_of=lambda user_id: f"{user_id}/cohort/{target.cohort_id}")


@router.post("/people/cohort-remove", response_model=BulkOut)
def remove_people_from_cohort(
    body: BulkCohort, request: Request, actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> BulkOut:
    """Remove every selected person from one cohort."""
    target = _cohort(conn, body.cohort_id)
    return _bulk(request=request, actor=actor.user_id, conn=conn, user_ids=body.user_ids,
                 action="cohort.remove", run=lambda user_id: commands.remove_from_cohort(
                     conn, target=target, user_id=user_id).summary(),
                 target_of=lambda user_id: f"{user_id}/cohort/{target.cohort_id}")


@router.get("/requests", response_model=RequestsOut)
def list_requests(
    conn: Annotated[Connection, Depends(get_conn)],
    settings: Annotated[Settings, Depends(get_settings)],
    rejected: bool = False,
) -> RequestsOut:
    """List waitlist rows still waiting for a decision, and the rejected ones when asked."""
    # Only requests still waiting for a decision: an
    # invited person is on People, a rejected request is gone.
    rows = conn.execute(
        select(waitlist_entry)
        .where(
            waitlist_entry.c.account_created_at.is_(None),
            # Rejected rows are kept as a record and shown on request.
            true() if rejected else waitlist_entry.c.rejected_at.is_(None),
        )
        .order_by(waitlist_entry.c.created_at, waitlist_entry.c.entry_id)
    ).mappings().all()
    ids = [str(row["entry_id"]) for row in rows]
    terminal = set(conn.execute(
        select(ops_action.c.target).where(
            ops_action.c.actor_user_id == "sweep", ops_action.c.action == "invite",
            ops_action.c.outcome.in_(TERMINAL_OUTCOMES),
            ops_action.c.target.in_(ids),
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
    invites = _invite_reasons(conn, [
        row for row in rows
        if row["invite_code"] is not None and row["rejected_at"] is None
        and str(row["entry_id"]) not in terminal
    ])
    items: list[RequestOut] = []
    for row in rows:
        check = str(row["entry_id"]) in terminal
        note = None
        if check:
            # app_user.email carries no unique constraint: take the first match.
            note = conn.execute(
                select(organisation.c.name).select_from(
                    app_user.join(organisation, organisation.c.org_id == app_user.c.org_id)
                ).where(app_user.c.email == row["email"]).limit(1)
            ).scalar_one_or_none()
        items.append(RequestOut(
            **row,
            status="rejected" if row["rejected_at"] is not None else
            "check" if check else "waiting",
            note=note,
            invite=invites.get(row["entry_id"]),
        ))
    return RequestsOut(
        items=items,
        self_signup=SelfSignupOut(enabled=settings.self_signup_enabled, domains=domains,
                                 sent_this_hour=sent,
                                 max_per_hour=settings.self_signup_max_per_hour),
    )


def _invite_reasons(
    conn: Connection, rows: list[RowMapping]
) -> dict[uuid.UUID, RequestInvite]:
    """For waiting requests that carry a code: the link's label and why it has no account yet.

    Three reads for the whole page, never one for each request.
    """
    if not rows:
        return {}
    links = {
        str(row["code"]): commands.invite_link_record(row)
        for row in conn.execute(select(invite_link).where(
            invite_link.c.code.in_({row["invite_code"] for row in rows})
        )).mappings()
    }
    uses = {link_id: int(count) for link_id, count in conn.execute(
        select(waitlist_entry.c.invite_link_id, func.count())
        .where(waitlist_entry.c.invite_link_id.in_([
            link.invite_link_id for link in links.values()
        ]))
        .group_by(waitlist_entry.c.invite_link_id)
    )} if links else {}
    now = _now()
    retrying = set(conn.execute(select(ops_action.c.target).where(
        ops_action.c.actor_user_id == "sweep", ops_action.c.action == "invite",
        ops_action.c.outcome == "failed", ops_action.c.at > now - RETRY_WAIT,
        ops_action.c.target.in_([str(row["entry_id"]) for row in rows]),
    )).scalars())
    reasons: dict[uuid.UUID, RequestInvite] = {}
    for row in rows:
        link = links.get(str(row["invite_code"]))
        email = str(row["email"])
        reason = commands.invite_request_reason(
            invite_code=row["invite_code"],
            # The sweep's reading of the domain: split_part(email, '@', 2), lower-cased.
            request_domain=email.split("@")[1].lower() if "@" in email else "",
            link=link, uses=uses.get(link.invite_link_id, 0) if link else 0, now=now,
        )
        if reason is None:
            continue
        reasons[row["entry_id"]] = RequestInvite(
            label=link.label if link else None,
            reason="retry_wait" if reason == "next_run" and str(row["entry_id"]) in retrying
            else reason,
        )
    return reasons


@router.post("/requests/{entry_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject_request(
    entry_id: uuid.UUID, request: Request,
    actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> Response:
    """Take a request off the waitlist without an email."""
    try:
        commands.reject_request(conn, entry_id=entry_id, now=_now())
    except NotFound as exc:
        raise HTTPException(404, str(exc)) from None
    except OpsError as exc:
        raise ApiConflict("ops_refused", str(exc)) from None
    _audit(request, conn, actor=actor.user_id, action="request.reject", target=str(entry_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/requests/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_request(
    entry_id: uuid.UUID, request: Request,
    actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> Response:
    """Delete a rejected request for good."""
    try:
        commands.delete_request(conn, entry_id=entry_id)
    except NotFound as exc:
        raise HTTPException(404, str(exc)) from None
    except OpsError as exc:
        raise ApiConflict("ops_refused", str(exc)) from None
    _audit(request, conn, actor=actor.user_id, action="request.delete", target=str(entry_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    cohorts = [_cohort(conn, cohort_id) for cohort_id in body.cohort_ids]
    try:
        approved = commands.approve_request(
            conn, cognito, pool_id=pool_id, entry_id=entry_id, org=org, now=_now()
        )
    except NotFound as exc:
        raise HTTPException(404, str(exc)) from None
    except EnrolledElsewhere as exc:
        raise ApiConflict("enrolled_elsewhere", str(exc)) from None
    except OpsError as exc:
        raise ApiConflict("ops_refused", str(exc)) from None
    except ClientError as exc:
        raise ApiConflict("ops_refused", _cognito_refusal(exc)) from None
    outcome = "invited" if approved.enrolment.invitation_sent else "enrolled"
    action_id = commands.record_action(
        conn, actor=actor.user_id, action="request.approve", target=str(entry_id), outcome=outcome
    )
    _queue_log(request, actor=actor.user_id, action="request.approve", target=str(entry_id),
               outcome=outcome, action_id=action_id)
    _join_cohorts(request, conn, actor=actor.user_id, user_id=approved.enrolment.user_id,
                  cohorts=cohorts)
    row = conn.execute(
        select(waitlist_entry).where(waitlist_entry.c.entry_id == entry_id)
    ).mappings().one()
    return RequestOut(**row, status="invited")


def _invite_links(
    conn: Connection, settings: Settings, invite_link_id: uuid.UUID | None = None
) -> list[InviteLinkOut]:
    """Every invite link, newest first, or the one asked for, with its uses and state."""
    if settings.public_app_origin is None:
        raise HTTPException(503, "the public site's address is not configured")
    query = (
        select(invite_link, organisation.c.name.label("organisation_name"))
        .join(organisation, organisation.c.org_id == invite_link.c.org_id)
        .order_by(invite_link.c.created_at.desc(), invite_link.c.invite_link_id)
    )
    if invite_link_id is not None:
        query = query.where(invite_link.c.invite_link_id == invite_link_id)
    rows = conn.execute(query).mappings().all()
    ids = [row["invite_link_id"] for row in rows]
    uses = {link_id: int(count) for link_id, count in conn.execute(
        select(waitlist_entry.c.invite_link_id, func.count())
        .where(waitlist_entry.c.invite_link_id.in_(ids))
        .group_by(waitlist_entry.c.invite_link_id)
    )} if ids else {}
    cohorts: dict[uuid.UUID, list[CohortRef]] = {}
    for link_id, cohort_id, name in conn.execute(
        select(invite_link_cohort.c.invite_link_id, cohort.c.cohort_id, cohort.c.name)
        .join(cohort, cohort.c.cohort_id == invite_link_cohort.c.cohort_id)
        .where(invite_link_cohort.c.invite_link_id.in_(ids))
        .order_by(cohort.c.name)
    ) if ids else ():
        cohorts.setdefault(link_id, []).append(CohortRef(cohort_id=cohort_id, name=name))
    now = _now()
    items: list[InviteLinkOut] = []
    for row in rows:
        link = commands.invite_link_record(row)
        used = uses.get(link.invite_link_id, 0)
        items.append(InviteLinkOut(
            invite_link_id=link.invite_link_id, label=link.label,
            organisation=OrganisationRef(org_id=link.org_id, name=row["organisation_name"]),
            cohorts=cohorts.get(link.invite_link_id, []),
            allowed_domains=list(link.allowed_domains), max_uses=link.max_uses, uses=used,
            expires_at=link.expires_at, revoked_at=link.revoked_at, created_at=link.created_at,
            state=commands.invite_link_state(link, used, now),
            # The code travels in the fragment, which a browser never sends to a server.
            url=f"{settings.public_app_origin}/#invite={invite_code.display(link.code)}",
        ))
    return items


def _invite_link_refusal(run: Callable[[], commands.InviteLink]) -> commands.InviteLink:
    """Run one link command, mapping its refusals to the ordinary errors."""
    try:
        return run()
    except NotFound as exc:
        raise HTTPException(404, str(exc)) from None
    except OpsError as exc:
        raise ApiConflict("ops_refused", str(exc)) from None


@router.get("/invite-links", response_model=list[InviteLinkOut])
def list_invite_links(
    conn: Annotated[Connection, Depends(get_conn)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[InviteLinkOut]:
    """List every invite link with its organisation, cohorts, uses, state and address."""
    return _invite_links(conn, settings)


@router.post("/invite-links", response_model=InviteLinkOut,
             status_code=status.HTTP_201_CREATED)
def create_invite_link(
    body: InviteLinkCreate, request: Request,
    actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InviteLinkOut:
    """Make an invite link; the server makes its code."""
    org = _org(conn, body.org_id)
    cohorts = [_cohort(conn, cohort_id) for cohort_id in body.cohort_ids]
    link = _invite_link_refusal(lambda: commands.create_invite_link(
        conn, label=body.label, org=org, cohorts=cohorts, allowed_domains=body.allowed_domains,
        max_uses=body.max_uses, expires_at=body.expires_at, created_by=actor.user_id, now=_now(),
    ))
    _audit(request, conn, actor=actor.user_id, action="invite_link.create",
           target=str(link.invite_link_id))
    return _invite_links(conn, settings, link.invite_link_id)[0]


@router.post("/invite-links/{invite_link_id}", response_model=InviteLinkOut)
def update_invite_link(
    invite_link_id: uuid.UUID, body: InviteLinkUpdate, request: Request,
    actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InviteLinkOut:
    """Change a link's label, use limit and end."""
    _invite_link_refusal(lambda: commands.update_invite_link(
        conn, invite_link_id=invite_link_id, label=body.label, max_uses=body.max_uses,
        expires_at=body.expires_at, now=_now(),
    ))
    _audit(request, conn, actor=actor.user_id, action="invite_link.update",
           target=str(invite_link_id))
    return _invite_links(conn, settings, invite_link_id)[0]


@router.post("/invite-links/{invite_link_id}/revoke", response_model=InviteLinkOut)
def revoke_invite_link(
    invite_link_id: uuid.UUID, request: Request,
    actor: Annotated[AuthenticatedUser, Depends(require_ops)],
    conn: Annotated[Connection, Depends(get_conn)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InviteLinkOut:
    """Stop a link for good; the accounts it already made stay."""
    _invite_link_refusal(lambda: commands.revoke_invite_link(
        conn, invite_link_id=invite_link_id, now=_now(),
    ))
    _audit(request, conn, actor=actor.user_id, action="invite_link.revoke",
           target=str(invite_link_id))
    return _invite_links(conn, settings, invite_link_id)[0]
