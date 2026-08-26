"""Owner-scoped project lifecycle resource routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.engine import Connection

from policy_atlas.api.app import ApiConflict
from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract import (
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_MAX,
    Page,
    PageMeta,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
)
from policy_atlas.api.deps import get_conn, get_current_user
from policy_atlas.api.identity import owner_display_for
from policy_atlas.api.lifecycle import archive_project, rename_project
from policy_atlas.api.routers._access import (
    OWNER_EMAIL_MAX,
    accessible_portfolio,
    accessible_project,
    creator_org_id,
    listing_scope,
    owner_email_filter,
    trace_admin_listing,
)
from policy_atlas.api.routers._common import project_out
from policy_atlas.core.schema import app_user, capability_run, project

router = APIRouter(
    prefix="/api/v1/projects",
    tags=["projects"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=Page[ProjectOut])
def list_projects(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
    status_filter: Annotated[
        Literal["active", "archived", "all"], Query(alias="status")
    ] = "active",
    scope: Annotated[Literal["all", "mine"], Query()] = "all",
    portfolio_id: Annotated[uuid.UUID | None, Query()] = None,
    owner_email: Annotated[str | None, Query(max_length=OWNER_EMAIL_MAX)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
) -> Page[ProjectOut]:
    """List the projects the caller may see, with derived latest-run state.

    Args:
        user: The authenticated caller.
        conn: Open database connection.
        status_filter: `active` (default), `archived` or `all`.
        scope: `all` (default) — the caller's own rows plus their
            organisation's org-visible rows, and for an administrator every
            row in every organisation — or `mine` for owner-only, the
            pre-033 behaviour. **The default is `all`**: a `mine` default
            would hide the whole feature behind a switcher.
        portfolio_id: Narrow to one portfolio's members. Server-side because
            `PortfolioDetailView` filtered the default 50-row global page
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
        One page of projects.

    Raises:
        HTTPException: 422 when a non-administrator passes `owner_email`.
    """
    scoped = listing_scope(conn, project, user_id=user.user_id, scope=scope)
    where = [
        scoped.predicate,
        owner_email_filter(conn, project, user_id=user.user_id, owner_email=owner_email),
    ]
    if status_filter != "all":
        where.append(project.c.status == status_filter)
    if portfolio_id is not None:
        where.append(project.c.portfolio_id == portfolio_id)
    total = conn.execute(select(func.count()).select_from(project).where(*where)).scalar_one()
    # One join, not one lookup per row: `owner_display` on a 200-row page
    # would otherwise be 200 extra round trips.
    rows = conn.execute(
        select(*project.c, app_user.c.display_name.label("owner_display_name"))
        .select_from(
            project.outerjoin(app_user, app_user.c.user_id == project.c.owner_user_id)
        )
        .where(*where)
        .order_by(project.c.updated_at.desc(), project.c.project_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).mappings().all()
    # One line per cross-organisation request (contract § 3a), emitted after
    # the page is known so it can carry the row count — including the zero
    # that an `owner_email` search matching nobody produces.
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
            project_out(
                conn,
                row,
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
    """Create one active project owned by the authenticated subject.

    Stamps the creator's organisation onto the row (contract § 7) — NULL when
    the creator is unenrolled, which leaves the row reachable by its owner
    alone. `visibility` takes the column default `private` (owner amendment
    2026-08-26 — new work is unshared until its owner deliberately shares it).
    """
    now = datetime.now(UTC)
    project_id = uuid.uuid4()
    conn.execute(
        project.insert().values(
            project_id=project_id,
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
    row = conn.execute(select(project).where(project.c.project_id == project_id)).mappings().one()
    return project_out(conn, row, user_id=user.user_id)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> ProjectOut:
    """Return one active project readable by the caller (owner or same-org colleague)."""
    access = accessible_project(conn, project_id=project_id, user_id=user.user_id, write=False)
    return project_out(conn, access.row, user_id=user.user_id)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> ProjectOut:
    """Apply the supplied project fields without changing omitted fields.

    Resolves under the **write** grade (contract § 3: write is owner-only), so
    a same-org colleague who can now *see* this row in their listing gets 403
    `forbidden` here rather than the 404 that would claim the row does not
    exist — they are already looking at it.

    Three of the invariant's six paths run here (contract § 6). Setting
    `visibility` on a project that belongs to a portfolio is **i.5**, refused
    409. Setting `portfolio_id` to a portfolio is **i.2/i.3** — the member
    takes that portfolio's `visibility` and `org_id`, promotion and demotion
    being the same rule read in two directions. Setting it to `null` is
    **i.6** — the row leaves with the visibility and organisation it had.

    Args:
        project_id: The project to update.
        payload: The partial update. A body carrying both `visibility` and
            `portfolio_id` was already rejected 422 by the model.
        user: The authenticated caller.
        conn: Open database connection.

    Returns:
        The updated project.

    Raises:
        HTTPException: 404 when the row is unreadable, 403 when it is
            readable but not owned.
        ApiConflict: 409 `visibility_conflict` when setting `visibility` on a
            project that belongs to a portfolio.
    """
    access = accessible_project(
        conn, project_id=project_id, user_id=user.user_id, write=True, for_update=True
    )
    changes = payload.model_dump(exclude_unset=True)
    if "visibility" in changes:
        # i.5, enforced against the row already loaded. A project in a
        # portfolio carries that portfolio's visibility, so the only honest
        # answers are "change the Project's visibility" and "leave the Task
        # out of the Project" — never a silent write that the cascade would
        # contradict. The cascade itself, and the property over i.1-i.6,
        # land with the invariant.
        if access.row["portfolio_id"] is not None:
            raise ApiConflict(
                "visibility_conflict",
                "this task follows its project's visibility — change the project's "
                "visibility, or leave the task out of the project",
            )
        conn.execute(
            update(project)
            .where(project.c.project_id == project_id)
            .values(visibility=changes["visibility"], updated_at=datetime.now(UTC))
        )
    if "name" in changes:
        rename_project(conn, project_id, changes.pop("name"), user.user_id)
    if "question" in changes:
        conn.execute(
            update(project)
            .where(project.c.project_id == project_id)
            .values(question=changes["question"], updated_at=datetime.now(UTC))
        )
    if "portfolio_id" in changes:
        target = changes["portfolio_id"]
        assignment: dict[str, object] = {
            "portfolio_id": target,
            "updated_at": datetime.now(UTC),
        }
        if target is not None:
            # An unowned portfolio must be as invisible here as it is on its
            # own route, or PATCH becomes an existence oracle for someone
            # else's rows. Locked (`for_update`) so a cascade running on the
            # same portfolio cannot commit between this read and the write
            # below and leave the assigned row carrying the old visibility —
            # which is precisely an org-visible row inside a private Project.
            #
            # Both paths lock the portfolio row before writing, and the
            # cascade's member UPDATE takes row locks on the members it
            # carries. The one interleaving that can deadlock is a re-assign
            # of a project *into the portfolio it is already in* racing that
            # portfolio's cascade; Postgres aborts one side, and the request
            # is a no-op the caller can repeat.
            group = accessible_portfolio(
                conn,
                portfolio_id=target,
                user_id=user.user_id,
                write=True,
                for_update=True,
            )
            # i.2 (promotion) and i.3 (demotion) are one rule, not two
            # branches: the member takes its portfolio's `visibility` **and**
            # `org_id`. Deterministic and silent by design — the request that
            # carries `visibility` for a row in a portfolio is the one that
            # 409s above, so an assignment cannot be a disguised visibility
            # argument, and the response states the resulting visibility.
            # (The screen names that outcome before the click; the copy is
            # phase 10b's, and `test_the_i5_then_i2_loop_ends_org_visible`
            # pins the sequence the copy exists to describe.)
            assignment["visibility"] = group.row["visibility"]
            assignment["org_id"] = group.row["org_id"]
        # i.6, the `target is None` case: clearing the assignment writes
        # neither field. The row keeps the visibility and organisation it had
        # inside the portfolio — leaving is not a way to change either, and a
        # row that was org-visible does not become private by being taken out.
        conn.execute(
            update(project).where(project.c.project_id == project_id).values(**assignment)
        )
    row = conn.execute(select(project).where(project.c.project_id == project_id)).mappings().one()
    return project_out(conn, row, user_id=user.user_id)


@router.post("/{project_id}/archive", response_model=ProjectOut)
def archive_project_route(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> ProjectOut:
    """Soft-delete a project unless its latest walk is active or parked."""
    accessible_project(
        conn,
        project_id=project_id,
        user_id=user.user_id,
        write=True,
        include_archived=True,
        for_update=True,
    )
    latest = conn.execute(
        select(capability_run.c.status)
        .where(capability_run.c.project_id == project_id)
        .order_by(capability_run.c.started_at.desc(), capability_run.c.capability_run_id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest in {"running", "paused"}:
        raise ApiConflict("run_active", "the latest run is still active")
    # A run admitted but not yet inserted is invisible to the row check above —
    # consult the in-process dispatch reservation or archive can win that window
    # and the run executes against a hidden project (review finding codex-9).
    from policy_atlas.api.routers.runs import dispatch_reserved

    if dispatch_reserved(project_id):
        raise ApiConflict("run_active", "the latest run is still active")
    archive_project(conn, project_id, user.user_id)
    refreshed = conn.execute(
        select(project).where(project.c.project_id == project_id)
    ).mappings().one()
    return project_out(conn, refreshed, user_id=user.user_id)
