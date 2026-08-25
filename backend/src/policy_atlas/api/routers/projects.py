"""Owner-scoped project lifecycle resource routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

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
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
)
from policy_atlas.api.deps import get_conn, get_current_user
from policy_atlas.api.lifecycle import archive_project, rename_project
from policy_atlas.api.routers._common import (
    memberships_for_projects,
    owned_portfolio,
    owned_project,
    project_out,
)
from policy_atlas.core.schema import capability_run, portfolio_membership, project

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
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
) -> Page[ProjectOut]:
    """List the authenticated user's projects with derived latest-run state."""
    where = [project.c.owner_user_id == user.user_id]
    if status_filter != "all":
        where.append(project.c.status == status_filter)
    total = conn.execute(select(func.count()).select_from(project).where(*where)).scalar_one()
    rows = conn.execute(
        select(project)
        .where(*where)
        .order_by(project.c.updated_at.desc(), project.c.project_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).mappings().all()
    memberships = memberships_for_projects(conn, [row["project_id"] for row in rows])
    return Page(
        data=[
            project_out(conn, row, portfolio_ids=memberships[row["project_id"]])
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
    """Create one active project owned by the authenticated subject."""
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
        )
    )
    row = conn.execute(select(project).where(project.c.project_id == project_id)).mappings().one()
    return project_out(conn, row)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> ProjectOut:
    """Return one active project when it belongs to the caller."""
    return project_out(conn, owned_project(conn, project_id=project_id, user_id=user.user_id))


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> ProjectOut:
    """Apply the supplied project fields without changing omitted fields."""
    owned_project(conn, project_id=project_id, user_id=user.user_id, for_update=True)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        rename_project(conn, project_id, changes.pop("name"), user.user_id)
    if "question" in changes:
        conn.execute(
            update(project)
            .where(project.c.project_id == project_id)
            .values(question=changes["question"], updated_at=datetime.now(UTC))
        )
    assigned_ids: list[uuid.UUID] | None = None
    if "portfolio_ids" in changes:
        assigned_ids = list(dict.fromkeys(changes["portfolio_ids"] or []))
        # Unowned ids must 404 before any write, matching the portfolio
        # route — otherwise PATCH is an existence oracle for other owners.
        for target in assigned_ids:
            owned_portfolio(conn, portfolio_id=target, user_id=user.user_id)
        conn.execute(
            delete(portfolio_membership).where(
                portfolio_membership.c.project_id == project_id
            )
        )
        now = datetime.now(UTC)
        if assigned_ids:
            conn.execute(
                portfolio_membership.insert(),
                [
                    {
                        "portfolio_id": target,
                        "project_id": project_id,
                        "created_at": now,
                    }
                    for target in assigned_ids
                ],
            )
        conn.execute(
            update(project)
            .where(project.c.project_id == project_id)
            .values(updated_at=now)
        )
    row = conn.execute(select(project).where(project.c.project_id == project_id)).mappings().one()
    return project_out(conn, row, portfolio_ids=assigned_ids)


@router.post("/{project_id}/archive", response_model=ProjectOut)
def archive_project_route(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> ProjectOut:
    """Soft-delete a project unless its latest walk is active or parked."""
    owned_project(
        conn,
        project_id=project_id,
        user_id=user.user_id,
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
    return project_out(conn, refreshed)
