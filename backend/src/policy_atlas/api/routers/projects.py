"""Owner-scoped project routes — the named grouping above the task row.

Since task 038 the screen word and the code word agree: this row is a **Project**
and a `task` row is a **Task**. A project carries a name, a description and an owner;
its task count is derived per request rather than cached on the row.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, NamedTuple

import structlog
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import case, func, select, update
from sqlalchemy.engine import Connection, RowMapping
from sqlalchemy.sql.elements import ColumnElement

from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract import (
    LIST_PAGE_SIZE_DEFAULT,
    PAGE_SIZE_MAX,
    Page,
    PageMeta,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    Visibility,
)
from policy_atlas.api.deps import get_conn, get_current_user
from policy_atlas.api.identity import owner_display_for
from policy_atlas.api.routers.access import (
    OWNER_EMAIL_MAX,
    accessible_project,
    accessible_task,
    creator_org_id,
    listing_scope,
    own_estate,
    owner_email_filter,
    trace_admin_listing,
)
from policy_atlas.api.routers.common import resolve_owner_display
from policy_atlas.core.schema import app_user, project, project_membership, task

log = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/projects",
    tags=["projects"],
    dependencies=[Depends(get_current_user)],
)


#: The only columns `PATCH /api/v1/projects/{id}` may write **by splat**.
#: Explicitly **not** `visibility`: contract § 6, i.4 makes
#: :func:`_cascade_visibility` its sole writer. `ProjectUpdate` now carries
#: the field — the route routes it to the cascade by name — and this list is
#: what guarantees the generic path can never carry it to the column instead.
#: Asserted structurally by
#: `test_project_visibility_never_reaches_the_column_through_the_splat`.
_PATCHABLE_COLUMNS = ("name", "description")


def _cascade_visibility(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    org_id: uuid.UUID | None,
    visibility: Visibility,
) -> None:
    """Set a project's visibility and carry every member task with it.

    Contract § 6, i.4 — **the only writer of `project.visibility`**, and
    the reason `PATCH /api/v1/projects/{id}` may accept the field at all.
    Two statements in the request's single transaction (`deps.get_conn`), so
    no reader ever observes a project and its members disagreeing.

    **Both invariant fields are written, not just `visibility`.** A visibility
    change does not move a row between organisations, and members already
    match their project's `org_id` — i.1 inherits it, the assignment path
    syncs it, and enrolment moves a person's rows as one set. So the `org_id`
    write is a no-op on every row the API itself produced. It is written
    anyway, deliberately: if a member ever *does* mismatch — an operator
    assignment, a pre-invariant row, a future path that forgets — the choice
    is between self-healing it here and leaving an exposed row in place while
    the property test reports it after the fact. "Every member follows its
    project" is the rule, so the cascade makes both fields true rather than
    half of them.

    **Archived members are included** (contract § 6, i.4). They are excluded
    from the derived task count, not from the row's visibility: an archived
    Task is still readable by whoever may read it, so leaving it behind would
    keep exactly the rows nobody is looking at readable by the organisation
    after the owner made the Project private.

    Args:
        conn: Open database connection, inside the request transaction.
        project_id: The project whose visibility is changing.
        org_id: That project's organisation — what members are synced to.
        visibility: The new visibility for the project. Each member is then
            **recomputed, not assigned**: membership is many-to-many
            (ADR 0032), and a member is org-visible if *any* project it is
            in is org-visible, private otherwise (owner ruling 2026-08-27).
            With a single membership that collapses to "the member follows
            its project", the pre-0032 behaviour; a member shared with an
            org-visible project stays org-visible when this one goes
            private.
    """
    conn.execute(
        update(project)
        .where(project.c.project_id == project_id)
        .values(visibility=visibility)
    )
    member_ids = select(project_membership.c.task_id).where(
        project_membership.c.project_id == project_id
    )
    # The project row is written first, so this EXISTS reads the new value
    # along with every other membership the member holds.
    in_any_org_project = (
        select(project_membership.c.task_id)
        .select_from(
            project_membership.join(
                project,
                project.c.project_id == project_membership.c.project_id,
            )
        )
        .where(project_membership.c.task_id == task.c.task_id)
        .where(project.c.visibility == "org")
        .exists()
    )
    # No status filter, on purpose: archived members follow too.
    conn.execute(
        update(task)
        .where(task.c.task_id.in_(member_ids))
        .values(
            visibility=case((in_any_org_project, "org"), else_="private"),
            org_id=org_id,
            updated_at=datetime.now(UTC),
        )
    )


class _Members(NamedTuple):
    """A project's caller-visible active members: how many, and the newest update."""

    total: int
    newest_update: datetime | None


def _member_estate(user_id: str) -> list[ColumnElement[bool]]:
    """The members a project's count and last activity read (contract § 8)."""
    return [task.c.status == "active", own_estate(task, user_id)]


def _task_counts(
    conn: Connection, project_ids: list[uuid.UUID], *, user_id: str
) -> dict[uuid.UUID, _Members]:
    """Count each project's active, caller-visible members in one query.

    Counted unconditionally before task 033, which would have shown a
    colleague the true size of a Project whose private Tasks they cannot
    open. Contract § 8: the count includes only rows the caller may read
    **and** rows in the caller's own organisation — :func:`own_estate`, which
    is the read grade minus the admin leg, so an administrator's card keeps
    showing their own organisation's count rather than a cross-organisation
    sum. The same members give the project's last activity (their newest
    ``updated_at``; task 058, round 12).

    Args:
        conn: Open database connection.
        project_ids: The projects to count for.
        user_id: The calling subject — the count is per-caller.

    Returns:
        Counts and newest updates by project id; projects with no visible
        member are absent.
    """
    if not project_ids:
        return {}
    rows = conn.execute(
        select(
            project_membership.c.project_id, func.count(), func.max(task.c.updated_at)
        )
        .select_from(
            project_membership.join(
                task,
                task.c.task_id == project_membership.c.task_id,
            )
        )
        .where(project_membership.c.project_id.in_(project_ids))
        .where(*_member_estate(user_id))
        .group_by(project_membership.c.project_id)
    ).all()
    return {row[0]: _Members(int(row[1]), row[2]) for row in rows}


def _last_activity_at(user_id: str) -> ColumnElement[Any]:
    """A project's last activity as SQL: the newest of its own creation and
    its caller-visible active members' ``updated_at`` (task 058, round 12)."""
    newest = (
        select(func.max(task.c.updated_at))
        .select_from(
            project_membership.join(task, task.c.task_id == project_membership.c.task_id)
        )
        .where(project_membership.c.project_id == project.c.project_id)
        .where(*_member_estate(user_id))
        .scalar_subquery()
    )
    return func.greatest(project.c.created_at, newest)


def _project_out(
    row: RowMapping, members: _Members | None, *, user_id: str, owner_display: str | None
) -> ProjectOut:
    """Project one project row into its public contract shape for one caller.

    Args:
        row: The project row.
        members: The caller-visible members (:func:`_task_counts`), or
            ``None`` when it has none.
        user_id: The calling subject, for `is_owner`.
        owner_display: How to name the owner — never an email.

    Returns:
        The public project shape.
    """
    return ProjectOut(
        project_id=row["project_id"],
        name=row["name"],
        description=row["description"],
        created_at=row["created_at"],
        task_count=members.total if members is not None else 0,
        last_activity_at=max(row["created_at"], members.newest_update)
        if members is not None and members.newest_update is not None
        else row["created_at"],
        visibility=row["visibility"],
        is_owner=row["owner_user_id"] == user_id,
        owner_display=owner_display,
        archived_at=row["archived_at"],
    )


@router.get("", response_model=Page[ProjectOut])
def list_projects(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
    scope: Annotated[Literal["all", "mine"], Query()] = "all",
    owner_email: Annotated[str | None, Query(max_length=OWNER_EMAIL_MAX)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = LIST_PAGE_SIZE_DEFAULT,
    status_filter: Annotated[
        Literal["active", "archived", "all"], Query(alias="status")
    ] = "active",
) -> Page[ProjectOut]:
    """List the projects the caller may see, with a derived task count.

    Args:
        user: The authenticated caller.
        conn: Open database connection.
        scope: `all` (default) — the caller's own rows plus their
            organisation's org-visible rows, and for an administrator every
            row in every organisation — or `mine` for owner-only.
        owner_email: Narrow to one owner's rows. **Administrators only**; any
            other caller gets 422 `validation_error`, as does a value longer
            than `OWNER_EMAIL_MAX` or one carrying no `@` — see
            `tasks.list_tasks`.
        page: 1-indexed page number.
        page_size: Rows per page, server-capped.
        status_filter: `active` (default: not archived), `archived` or `all`
            (task 058, round 11), as `GET /tasks` takes it.

    Returns:
        One page of projects.

    Raises:
        HTTPException: 422 when a non-administrator passes `owner_email`.
    """
    scoped = listing_scope(conn, project, user_id=user.user_id, scope=scope)
    where = [
        scoped.predicate,
        owner_email_filter(conn, project, user_id=user.user_id, owner_email=owner_email),
    ]
    if status_filter == "active":
        where.append(project.c.archived_at.is_(None))
    elif status_filter == "archived":
        where.append(project.c.archived_at.is_not(None))
    total = conn.execute(select(func.count()).select_from(project).where(*where)).scalar_one()
    rows = conn.execute(
        select(*project.c, app_user.c.display_name.label("owner_display_name"))
        .select_from(
            project.outerjoin(app_user, app_user.c.user_id == project.c.owner_user_id)
        )
        .where(*where)
        # Newest activity first (task 058, round 12), so the page the list
        # shows is the page it would sort to; the project id breaks ties.
        .order_by(_last_activity_at(user.user_id).desc(), project.c.project_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).mappings().all()
    counts = _task_counts(conn, [row["project_id"] for row in rows], user_id=user.user_id)
    # One line per cross-organisation request (contract § 3a), emitted after
    # the page is known so it can carry the row count — including the zero an
    # `owner_email` search matching nobody produces.
    trace_admin_listing(
        scoped,
        kind="project",
        user_id=user.user_id,
        scope=scope,
        owner_email=owner_email,
        page=page,
        page_size=page_size,
        row_count=len(rows),
        total_items=int(total),
    )
    return Page(
        data=[
            _project_out(
                row,
                counts.get(row["project_id"]),
                user_id=user.user_id,
                owner_display=owner_display_for(
                    row["owner_user_id"], row["owner_display_name"]
                ),
            )
            for row in rows
        ],
        pagination=PageMeta(page=page, page_size=page_size, total_items=int(total)),
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> ProjectOut:
    """Create one project owned by the authenticated subject.

    With `from_task_id` (contract § 6, i.1) the new project inherits that
    task's `visibility` **and** organisation and takes it as its first
    member, all in the request's single transaction — so the invariant "a
    task in a project matches its project on both" holds from the
    moment the row exists rather than being repaired afterwards.

    The source task resolves under the **write** grade, not a read grade.
    Under a read grade a same-org colleague — or, once the admin leg lands, an
    administrator — could pull a row they do not own into a project and
    change its visibility, which is the concrete admin-write escape the
    contract names.

    Without `from_task_id`, the project is empty and its organisation is
    stamped from the creator (contract § 7).

    Args:
        payload: The create body.
        user: The authenticated caller.
        conn: Open database connection.

    Returns:
        The created project.

    Raises:
        HTTPException: 404 when `from_task_id` names a task the caller
            cannot read, 403 when they can read it but do not own it.
    """
    project_id = uuid.uuid4()
    source = (
        accessible_task(
            conn,
            task_id=payload.from_task_id,
            user_id=user.user_id,
            write=True,
            for_update=True,
        )
        if payload.from_task_id is not None
        else None
    )
    org_id = source.row["org_id"] if source is not None else creator_org_id(conn, user.user_id)
    values: dict[str, object] = {
        "project_id": project_id,
        "owner_user_id": user.user_id,
        "name": payload.name,
        "description": payload.description,
        "created_at": datetime.now(UTC),
        "org_id": org_id,
    }
    if source is not None:
        values["visibility"] = source.row["visibility"]
    conn.execute(project.insert().values(**values))
    if source is not None:
        conn.execute(
            project_membership.insert().values(
                project_id=project_id,
                task_id=source.row["task_id"],
                created_at=datetime.now(UTC),
            )
        )
        conn.execute(
            update(task)
            .where(task.c.task_id == source.row["task_id"])
            .values(updated_at=datetime.now(UTC))
        )
    row = conn.execute(
        select(project).where(project.c.project_id == project_id)
    ).mappings().one()
    return _project_out(
        row,
        _task_counts(conn, [project_id], user_id=user.user_id).get(project_id),
        user_id=user.user_id,
        owner_display=resolve_owner_display(conn, user.user_id),
    )


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> ProjectOut:
    """Return one project readable by the caller (owner or same-org colleague)."""
    access = accessible_project(
        conn, project_id=project_id, user_id=user.user_id, write=False
    )
    counts = _task_counts(conn, [project_id], user_id=user.user_id)
    return _project_out(
        access.row,
        counts.get(project_id),
        user_id=user.user_id,
        owner_display=resolve_owner_display(conn, access.row["owner_user_id"]),
    )


@router.post("/{project_id}/archive", response_model=ProjectOut)
def archive_project(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> ProjectOut:
    """Archive a project (task 058, round 11), as `POST /tasks/{id}/archive` does a task.

    Owner only. The project leaves the default list (`status=active`) and is
    listed under `status=archived`; it stays readable by id. Its tasks are
    left as they are: they keep their membership and stay on the Tasks list.
    Archiving an archived project changes nothing and keeps its first time.

    Args:
        project_id: The project to archive.
        user: The authenticated caller.
        conn: Open database connection.

    Returns:
        The project with its `archived_at`.

    Raises:
        HTTPException: 404 when the project is unreadable, 403 when it is
            readable but not owned.
    """
    access = accessible_project(
        conn, project_id=project_id, user_id=user.user_id, write=True, for_update=True
    )
    if access.row["archived_at"] is None:
        conn.execute(
            update(project)
            .where(project.c.project_id == project_id)
            .values(archived_at=datetime.now(UTC))
        )
        log.info("project.archived", project_id=str(project_id), actor=user.user_id)
    row = conn.execute(
        select(project).where(project.c.project_id == project_id)
    ).mappings().one()
    counts = _task_counts(conn, [project_id], user_id=user.user_id)
    return _project_out(
        row,
        counts.get(project_id),
        user_id=user.user_id,
        owner_display=resolve_owner_display(conn, row["owner_user_id"]),
    )


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> ProjectOut:
    """Apply the supplied project fields without changing omitted fields.

    **Two code paths, not one.** `name` and `description` are written by an
    explicit allow-list splat (`_PATCHABLE_COLUMNS`); `visibility` is read off
    the model **by name** and routed to :func:`_cascade_visibility`, and never
    joins the splat. Contract § 6, i.4 makes the cascade the only writer of
    `project.visibility`; a blind `.values(**changes)` hands the column to
    whatever field a later slice adds to `ProjectUpdate`, and the failure it
    produces is silent — the owner sets a Project private, the UI agrees, and
    its Tasks stay readable by the whole organisation. The field now exists on
    the model, so the allow-list is the thing keeping that true.

    `payload.visibility is not None` **is** "the caller supplied it": the
    model refuses an explicit null, so the absent value and the None value are
    the same state.

    **Owner-only, like every other write** (contract § 3): the route resolves
    through the write grade, so a same-org colleague gets 403 and an
    administrator — whose leg is a *read* leg — never reaches the cascade
    however wide their read becomes.

    The row is locked (`for_update`) because the cascade and the assignment
    path in `tasks.py` write overlapping rows: without it, an assignment
    that read this project's visibility a moment before the cascade
    committed would write the stale value onto the task it is assigning and
    leave an org-visible row inside a private Project.

    Args:
        project_id: The project to update.
        payload: The partial update. Supplying `visibility` runs the cascade.
        user: The authenticated caller.
        conn: Open database connection.

    Returns:
        The updated project. Its `task_count` is the caller-visible active
        member count — see the note below on what the outcome copy may claim.

    Raises:
        HTTPException: 404 when the project is unreadable, 403 when it is
            readable but not owned.
    """
    access = accessible_project(
        conn, project_id=project_id, user_id=user.user_id, write=True, for_update=True
    )
    supplied = payload.model_dump(exclude_unset=True)
    changes = {field: supplied[field] for field in _PATCHABLE_COLUMNS if field in supplied}
    if changes:
        conn.execute(
            update(project)
            .where(project.c.project_id == project_id)
            .values(**changes)
        )
    if payload.visibility is not None:
        _cascade_visibility(
            conn,
            project_id=project_id,
            org_id=access.row["org_id"],
            visibility=payload.visibility,
        )
    row = conn.execute(
        select(project).where(project.c.project_id == project_id)
    ).mappings().one()
    # The i.4 outcome number. Defined through the **caller's readable set**
    # (`_task_counts` is per-caller: read grade minus admin, active only), not
    # through "how many rows the cascade touched" — the outcome copy must
    # never name rows the reader cannot see. Since colleague assignment
    # (owner ruling 2026-08-27) a member may be owned by a same-org
    # colleague, so the two genuinely differ: the count names the members
    # this owner can read, which is the honest number for the copy.
    counts = _task_counts(conn, [project_id], user_id=user.user_id)
    return _project_out(
        row,
        counts.get(project_id),
        user_id=user.user_id,
        owner_display=resolve_owner_display(conn, row["owner_user_id"]),
    )
