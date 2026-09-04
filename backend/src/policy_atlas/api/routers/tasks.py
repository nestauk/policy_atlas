"""Owner-scoped task lifecycle resource routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import Connection

from policy_atlas.api.app import ApiConflict
from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract import (
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_MAX,
    Page,
    PageMeta,
    TaskCreate,
    TaskOut,
    TaskUpdate,
)
from policy_atlas.api.deps import get_conn, get_current_user, get_optional_user
from policy_atlas.api.identity import owner_display_for
from policy_atlas.api.lifecycle import archive_task, rename_task
from policy_atlas.api.routers._access import (
    OWNER_EMAIL_MAX,
    accessible_task,
    assignable_project,
    creator_org_id,
    listing_scope,
    owner_email_filter,
    readable_or_public_task,
    trace_admin_listing,
)
from policy_atlas.api.routers._common import memberships_for_tasks, task_out
from policy_atlas.core import events
from policy_atlas.core.schema import (
    app_user,
    capability_run,
    project,
    project_membership,
    task,
)

log = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/tasks",
    tags=["tasks"],
    dependencies=[Depends(get_current_user)],
)

public_read_router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.get("", response_model=Page[TaskOut])
def list_tasks(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
    status_filter: Annotated[
        Literal["active", "archived", "all"], Query(alias="status")
    ] = "active",
    scope: Annotated[Literal["all", "mine"], Query()] = "all",
    project_id: Annotated[uuid.UUID | None, Query()] = None,
    owner_email: Annotated[str | None, Query(max_length=OWNER_EMAIL_MAX)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
) -> Page[TaskOut]:
    """List the tasks the caller may see, with derived latest-run state.

    Args:
        user: The authenticated caller.
        conn: Open database connection.
        status_filter: `active` (default), `archived` or `all`.
        scope: `all` (default) — the caller's own rows plus their
            organisation's org-visible rows, and for an administrator every
            row in every organisation — or `mine` for owner-only, the
            pre-033 behaviour. **The default is `all`**: a `mine` default
            would hide the whole feature behind a switcher.
        project_id: Narrow to one project's members. Server-side because
            `ProjectDetailView` filtered the default 50-row global page
            client-side and would silently under-report once the visible
            estate spans an organisation.
        owner_email: Narrow to one owner's rows. **Administrators only**; any
            other caller gets 422 `validation_error`, as does a value longer
            than `OWNER_EMAIL_MAX` or one carrying no `@` — the value is
            logged verbatim on the admin trace, so it is bounded and shaped at
            the boundary rather than in the log.
        page: 1-indexed page number.
        page_size: Rows per page, server-capped.

    Returns:
        One page of tasks.

    Raises:
        HTTPException: 422 when a non-administrator passes `owner_email`.
    """
    scoped = listing_scope(conn, task, user_id=user.user_id, scope=scope)
    where = [
        scoped.predicate,
        owner_email_filter(conn, task, user_id=user.user_id, owner_email=owner_email),
    ]
    if status_filter != "all":
        where.append(task.c.status == status_filter)
    if project_id is not None:
        where.append(
            task.c.task_id.in_(
                select(project_membership.c.task_id).where(
                    project_membership.c.project_id == project_id
                )
            )
        )
    total = conn.execute(select(func.count()).select_from(task).where(*where)).scalar_one()
    # One join, not one lookup per row: `owner_display` on a 200-row page
    # would otherwise be 200 extra round trips.
    rows = conn.execute(
        select(*task.c, app_user.c.display_name.label("owner_display_name"))
        .select_from(
            task.outerjoin(app_user, app_user.c.user_id == task.c.owner_user_id)
        )
        .where(*where)
        .order_by(task.c.updated_at.desc(), task.c.task_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).mappings().all()
    # One line per cross-organisation request (contract § 3a), emitted after
    # the page is known so it can carry the row count — including the zero
    # that an `owner_email` search matching nobody produces.
    trace_admin_listing(
        scoped,
        kind="task",
        user_id=user.user_id,
        scope=scope,
        owner_email=owner_email,
        page=page,
        page_size=page_size,
        row_count=len(rows),
        total_items=int(total),
    )
    memberships = memberships_for_tasks(conn, [row["task_id"] for row in rows])
    return Page(
        data=[
            task_out(
                conn,
                row,
                user_id=user.user_id,
                owner_display=owner_display_for(
                    row["owner_user_id"], row["owner_display_name"]
                ),
                project_ids=memberships[row["task_id"]],
            )
            for row in rows
        ],
        pagination=PageMeta(page=page, page_size=page_size, total_items=int(total)),
    )


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> TaskOut:
    """Create one active task owned by the authenticated subject.

    Stamps the creator's organisation onto the row (contract § 7) — NULL when
    the creator is unenrolled, which leaves the row reachable by its owner
    alone. `visibility` takes the column default `private` (owner amendment
    2026-08-26 — new work is unshared until its owner deliberately shares it).
    """
    now = datetime.now(UTC)
    task_id = uuid.uuid4()
    conn.execute(
        task.insert().values(
            task_id=task_id,
            name=payload.name,
            question=payload.question,
            status="active",
            owner_user_id=user.user_id,
            created_at=now,
            updated_at=now,
            archived_at=None,
            org_id=creator_org_id(conn, user.user_id),
        )
    )
    row = conn.execute(select(task).where(task.c.task_id == task_id)).mappings().one()
    return task_out(conn, row, user_id=user.user_id)


@public_read_router.get("/{task_id}", response_model=TaskOut)
def get_task(
    task_id: uuid.UUID,
    user: Annotated[AuthenticatedUser | None, Depends(get_optional_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> TaskOut:
    """Return one active task through its graded or redacted public leg."""
    access = readable_or_public_task(
        conn, task_id=task_id, user_id=None if user is None else user.user_id
    )
    if access.via_public:
        return task_out(
            conn, access.row, user_id=user.user_id if user else "", access="public"
        )
    return task_out(conn, access.row, user_id=user.user_id if user else "")


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> TaskOut:
    """Apply the supplied task fields without changing omitted fields.

    Resolves under the **write** grade (contract § 3: write is owner-only), so
    a same-org colleague who can now *see* this row in their listing gets 403
    `forbidden` here rather than the 404 that would claim the row does not
    exist — they are already looking at it.

    Three of the invariant's six paths run here (contract § 6). Setting
    `visibility` on a task that belongs to a project is **i.5**, refused
    409. Setting `project_ids` to a non-empty set is **i.2/i.3** — the
    member becomes org-visible if **any** named project is org-visible and
    private otherwise (owner ruling 2026-08-27), promotion and demotion being
    the same rule read in two directions; a set spanning two organisations is
    refused 409, since a row carries one `org_id`. Targets resolve under the
    **colleague-mutation** grade (owner ∪ same-org org-visible, never the
    admin leg — owner ruling 2026-08-27): a colleague may add their own task
    to an org-visible project they did not create. Setting it to `[]` (or
    `null`) is **i.6** — the row leaves with the visibility and organisation
    it had.

    Args:
        task_id: The task to update.
        payload: The partial update. A body carrying both `visibility` and
            `project_ids` was already rejected 422 by the model.
        user: The authenticated caller.
        conn: Open database connection.

    Returns:
        The updated task.

    Raises:
        HTTPException: 404 when the row is unreadable, 403 when it is
            readable but not owned.
        ApiConflict: 409 `visibility_conflict` when setting `visibility` on a
            task that belongs to a project.
    """
    access = accessible_task(
        conn, task_id=task_id, user_id=user.user_id, write=True, for_update=True
    )
    changes = payload.model_dump(exclude_unset=True)
    if "visibility" in changes:
        # i.5, enforced against the row already loaded. A task in a
        # project carries that project's visibility, so the only honest
        # answers are "change the Project's visibility" and "leave the Task
        # out of the Project" — never a silent write that the cascade would
        # contradict. The cascade itself, and the property over i.1-i.6,
        # land with the invariant.
        in_project = conn.execute(
            select(func.count())
            .select_from(project_membership)
            .where(project_membership.c.task_id == task_id)
        ).scalar_one()
        if int(in_project) > 0:
            raise ApiConflict(
                "visibility_conflict",
                "this task follows its task's visibility — change the task's "
                "visibility, or leave the task out of the task",
            )
        conn.execute(
            update(task)
            .where(task.c.task_id == task_id)
            .values(visibility=changes["visibility"], updated_at=datetime.now(UTC))
        )
    # Orthogonal to visibility/project membership (D1, contract § Design
    # decisions) — no interaction with the 409/422 rules above. Only a real
    # flip writes anything: a no-op PATCH (same value) writes neither the
    # column nor the audit event.
    if "is_public" in changes and bool(access.row["is_public"]) != changes["is_public"]:
        conn.execute(
            update(task)
            .where(task.c.task_id == task_id)
            .values(is_public=changes["is_public"], updated_at=datetime.now(UTC))
        )
        event_type = "task.shared_publicly" if changes["is_public"] else "task.unshared"
        events.append(
            conn,
            task_id=task_id,
            run_id=None,
            event_type=event_type,
            payload={"actor": user.user_id},
        )
        log.info(event_type, task_id=str(task_id), actor=user.user_id)
    if "name" in changes:
        rename_task(conn, task_id, changes.pop("name"), user.user_id)
    if "question" in changes:
        conn.execute(
            update(task)
            .where(task.c.task_id == task_id)
            .values(question=changes["question"], updated_at=datetime.now(UTC))
        )
    assigned_ids: list[uuid.UUID] | None = None
    if "project_ids" in changes:
        assigned_ids = list(dict.fromkeys(changes["project_ids"] or []))
        # NEW targets resolve under the colleague-mutation grade (owner ∪
        # same-org org-visible, never the admin leg — owner ruling
        # 2026-08-27): a colleague may add their own task to an org-visible
        # project they did not create. A project outside that estate
        # must be as invisible here as it is on its own route, or PATCH
        # becomes an existence oracle for someone else's rows. A project
        # the task is ALREADY in is kept without re-resolving the grade:
        # the body is replace-all, so re-checking would lock the owner out
        # of editing their own membership set the moment a colleague's
        # project they had joined went private. Its row is still loaded
        # and locked, because the visibility derivation below reads it.
        #
        # Locked either way, so a cascade running on the same project
        # cannot commit between this read and the write below and leave the
        # assigned row carrying the old visibility — which is precisely an
        # org-visible row inside a private Project. Both paths lock the
        # project row before writing, and the cascade's member UPDATE
        # takes row locks on the members it carries. The one interleaving
        # that can deadlock is a re-assign of a task *into the project
        # it is already in* racing that project's cascade; Postgres
        # aborts one side, and the request is a no-op the caller can
        # repeat.
        current_ids = {
            membership_row[0]
            for membership_row in conn.execute(
                select(project_membership.c.project_id).where(
                    project_membership.c.task_id == task_id
                )
            ).all()
        }
        group_rows = [
            conn.execute(
                select(project)
                .where(project.c.project_id == target)
                .with_for_update()
            ).mappings().one()
            if target in current_ids
            else assignable_project(
                conn, project_id=target, user_id=user.user_id
            ).row
            for target in assigned_ids
        ]
        now = datetime.now(UTC)
        assignment: dict[str, object] = {"updated_at": now}
        if group_rows:
            # i.2 (promotion) and i.3 (demotion) are one rule, not two
            # branches: the member is org-visible if **any** of its projects
            # is org-visible, private otherwise (owner ruling 2026-08-27 on
            # the ADR 0032 merge). Organisation is different — a row carries
            # exactly one `org_id`, so a set spanning two organisations has
            # no honest answer and is refused rather than picking a winner.
            org_ids = {group_row["org_id"] for group_row in group_rows}
            if len(org_ids) > 1:
                raise ApiConflict(
                    "visibility_conflict",
                    "these tasks belong to different organisations — a task "
                    "can only join tasks in one organisation",
                )
            assignment["visibility"] = (
                "org"
                if any(group_row["visibility"] == "org" for group_row in group_rows)
                else "private"
            )
            assignment["org_id"] = org_ids.pop()
        # i.6, the empty-list case: clearing every membership writes neither
        # field. The row keeps the visibility and organisation it had inside
        # its projects — leaving is not a way to change either, and a row
        # that was org-visible does not become private by being taken out.
        conn.execute(
            delete(project_membership).where(
                project_membership.c.task_id == task_id
            )
        )
        if assigned_ids:
            conn.execute(
                project_membership.insert(),
                [
                    {
                        "project_id": target,
                        "task_id": task_id,
                        "created_at": now,
                    }
                    for target in assigned_ids
                ],
            )
        conn.execute(
            update(task).where(task.c.task_id == task_id).values(**assignment)
        )
    row = conn.execute(select(task).where(task.c.task_id == task_id)).mappings().one()
    return task_out(conn, row, user_id=user.user_id, project_ids=assigned_ids)


@router.post("/{task_id}/archive", response_model=TaskOut)
def archive_task_route(
    task_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> TaskOut:
    """Soft-delete a task unless its latest walk is active or parked."""
    accessible_task(
        conn,
        task_id=task_id,
        user_id=user.user_id,
        write=True,
        include_archived=True,
        for_update=True,
    )
    latest = conn.execute(
        select(capability_run.c.status)
        .where(capability_run.c.task_id == task_id)
        .order_by(capability_run.c.started_at.desc(), capability_run.c.capability_run_id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest in {"running", "paused"}:
        raise ApiConflict("run_active", "the latest run is still active")
    # A run admitted but not yet inserted is invisible to the row check above —
    # consult the in-process dispatch reservation or archive can win that window
    # and the run executes against a hidden task (review finding codex-9).
    from policy_atlas.api.routers.runs import dispatch_reserved

    if dispatch_reserved(task_id):
        raise ApiConflict("run_active", "the latest run is still active")
    archive_task(conn, task_id, user.user_id)
    refreshed = conn.execute(
        select(task).where(task.c.task_id == task_id)
    ).mappings().one()
    return task_out(conn, refreshed, user_id=user.user_id)
