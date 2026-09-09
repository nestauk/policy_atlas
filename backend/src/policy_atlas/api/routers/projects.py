"""Owner-scoped project routes — the named grouping above the task row.

The screen calls a project a **Task** and a `task` row a **Task**
(task 032 § Terms). A project carries a name, a description and an owner;
its task count is derived per request rather than cached on the row.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.engine import Connection, RowMapping

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
from policy_atlas.api.routers._common import owned_project
from policy_atlas.core.schema import project, task

router = APIRouter(
    prefix="/api/v1/projects",
    tags=["projects"],
    dependencies=[Depends(get_current_user)],
)


def _task_counts(conn: Connection, project_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Count each project's active tasks in one query."""
    if not project_ids:
        return {}
    rows = conn.execute(
        select(task.c.project_id, func.count())
        .where(task.c.project_id.in_(project_ids))
        .where(task.c.status == "active")
        .group_by(task.c.project_id)
    ).all()
    return {row[0]: int(row[1]) for row in rows}


def _project_out(row: RowMapping, task_count: int) -> ProjectOut:
    """Project one project row into its public contract shape."""
    return ProjectOut(
        project_id=row["project_id"],
        name=row["name"],
        description=row["description"],
        created_at=row["created_at"],
        task_count=task_count,
    )


@router.get("", response_model=Page[ProjectOut])
def list_projects(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
) -> Page[ProjectOut]:
    """List the authenticated user's projects with a derived task count."""
    where = project.c.owner_user_id == user.user_id
    total = conn.execute(select(func.count()).select_from(project).where(where)).scalar_one()
    rows = conn.execute(
        select(project)
        .where(where)
        .order_by(project.c.created_at.desc(), project.c.project_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).mappings().all()
    counts = _task_counts(conn, [row["project_id"] for row in rows])
    return Page(
        data=[_project_out(row, counts.get(row["project_id"], 0)) for row in rows],
        pagination=PageMeta(page=page, page_size=page_size, total_items=int(total)),
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> ProjectOut:
    """Create one project owned by the authenticated subject."""
    project_id = uuid.uuid4()
    conn.execute(
        project.insert().values(
            project_id=project_id,
            owner_user_id=user.user_id,
            name=payload.name,
            description=payload.description,
            created_at=datetime.now(UTC),
        )
    )
    row = conn.execute(
        select(project).where(project.c.project_id == project_id)
    ).mappings().one()
    return _project_out(row, 0)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> ProjectOut:
    """Return one project when it belongs to the caller."""
    row = owned_project(conn, project_id=project_id, user_id=user.user_id)
    counts = _task_counts(conn, [project_id])
    return _project_out(row, counts.get(project_id, 0))


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> ProjectOut:
    """Apply the supplied project fields without changing omitted fields."""
    owned_project(conn, project_id=project_id, user_id=user.user_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes:
        conn.execute(
            update(project)
            .where(project.c.project_id == project_id)
            .values(**changes)
        )
    row = conn.execute(
        select(project).where(project.c.project_id == project_id)
    ).mappings().one()
    counts = _task_counts(conn, [project_id])
    return _project_out(row, counts.get(project_id, 0))
