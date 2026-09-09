"""Owner-scoped task lifecycle resource routes."""

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
    TaskCreate,
    TaskOut,
    TaskUpdate,
)
from policy_atlas.api.deps import get_conn, get_current_user
from policy_atlas.api.lifecycle import archive_task, rename_task
from policy_atlas.api.routers._common import owned_project, owned_task, task_out
from policy_atlas.core.schema import capability_run, task

router = APIRouter(
    prefix="/api/v1/tasks",
    tags=["tasks"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=Page[TaskOut])
def list_tasks(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
    status_filter: Annotated[
        Literal["active", "archived", "all"], Query(alias="status")
    ] = "active",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
) -> Page[TaskOut]:
    """List the authenticated user's tasks with derived latest-run state."""
    where = [task.c.owner_user_id == user.user_id]
    if status_filter != "all":
        where.append(task.c.status == status_filter)
    total = conn.execute(select(func.count()).select_from(task).where(*where)).scalar_one()
    rows = conn.execute(
        select(task)
        .where(*where)
        .order_by(task.c.updated_at.desc(), task.c.task_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).mappings().all()
    return Page(
        data=[task_out(conn, row) for row in rows],
        pagination=PageMeta(page=page, page_size=page_size, total_items=int(total)),
    )


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> TaskOut:
    """Create one active task owned by the authenticated subject."""
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
        )
    )
    row = conn.execute(select(task).where(task.c.task_id == task_id)).mappings().one()
    return task_out(conn, row)


@router.get("/{task_id}", response_model=TaskOut)
def get_task(
    task_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> TaskOut:
    """Return one active task when it belongs to the caller."""
    return task_out(conn, owned_task(conn, task_id=task_id, user_id=user.user_id))


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> TaskOut:
    """Apply the supplied task fields without changing omitted fields."""
    owned_task(conn, task_id=task_id, user_id=user.user_id, for_update=True)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        rename_task(conn, task_id, changes.pop("name"), user.user_id)
    if "question" in changes:
        conn.execute(
            update(task)
            .where(task.c.task_id == task_id)
            .values(question=changes["question"], updated_at=datetime.now(UTC))
        )
    if "project_id" in changes:
        target = changes["project_id"]
        # An unowned project must be as invisible here as it is on its own
        # route, or PATCH becomes an existence oracle for someone else's rows.
        if target is not None:
            owned_project(conn, project_id=target, user_id=user.user_id)
        conn.execute(
            update(task)
            .where(task.c.task_id == task_id)
            .values(project_id=target, updated_at=datetime.now(UTC))
        )
    row = conn.execute(select(task).where(task.c.task_id == task_id)).mappings().one()
    return task_out(conn, row)


@router.post("/{task_id}/archive", response_model=TaskOut)
def archive_task_route(
    task_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> TaskOut:
    """Soft-delete a task unless its latest walk is active or parked."""
    owned_task(
        conn,
        task_id=task_id,
        user_id=user.user_id,
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
    return task_out(conn, refreshed)
