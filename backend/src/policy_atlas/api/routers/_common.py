"""Private ownership and contract-projection helpers shared by API routers."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.engine import Connection, RowMapping

from policy_atlas.api.contract import LatestRun, TaskOut, RunOut
from policy_atlas.core.schema import (
    capability_run,
    project,
    task,
    task_source_snapshot,
)


def owned_task(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    user_id: str,
    include_archived: bool = False,
    for_update: bool = False,
) -> RowMapping:
    """Return an owned task or the contract's indistinguishable 404.

    Args:
        conn: Open database connection.
        task_id: Requested task identity.
        user_id: Authenticated owner's subject.
        include_archived: Whether an archived task can be observed.
        for_update: Whether the caller needs a row lock for a mutation.

    Returns:
        The owned task row.

    Raises:
        HTTPException: Always 404 for missing, archived, or cross-owner rows.
    """
    statement = select(task).where(task.c.task_id == task_id).where(
        task.c.owner_user_id == user_id
    )
    if not include_archived:
        statement = statement.where(task.c.status == "active")
    if for_update:
        statement = statement.with_for_update()
    row = conn.execute(statement).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="resource not found")
    return row


def owned_project(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    user_id: str,
) -> RowMapping:
    """Return an owned project or the contract's indistinguishable 404.

    Args:
        conn: Open database connection.
        project_id: Requested project identity.
        user_id: Authenticated owner's subject.

    Returns:
        The owned project row.

    Raises:
        HTTPException: Always 404 for missing or cross-owner rows, so an
            unknown project and someone else's are indistinguishable.
    """
    row = conn.execute(
        select(project)
        .where(project.c.project_id == project_id)
        .where(project.c.owner_user_id == user_id)
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="resource not found")
    return row


def run_out(row: RowMapping | dict[str, Any]) -> RunOut:
    """Project one capability-run row into its public contract shape."""
    return RunOut(
        capability_run_id=row["capability_run_id"],
        task_id=row["task_id"],
        plan_id=row["plan_id"],
        plan_version=row["plan_version"],
        status=row["status"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
    )


def task_out(conn: Connection, row: RowMapping | dict[str, Any]) -> TaskOut:
    """Project a task row with its derived latest capability-run read model."""
    latest = conn.execute(
        select(capability_run)
        .where(capability_run.c.task_id == row["task_id"])
        .order_by(capability_run.c.started_at.desc(), capability_run.c.capability_run_id.desc())
        .limit(1)
    ).mappings().one_or_none()
    latest_out = None
    source_count = None
    if latest is not None:
        latest_out = LatestRun(
            capability_run_id=latest["capability_run_id"],
            status=latest["status"],
            started_at=latest["started_at"],
            ended_at=latest["ended_at"],
        )
        # Same population the funnel's ``found`` counts. Derived per read and
        # only once a run exists: before that, ``None`` says the question has
        # not been asked, which is not the same as a run that found nothing.
        source_count = int(
            conn.execute(
                select(func.count())
                .select_from(task_source_snapshot)
                .where(task_source_snapshot.c.task_id == row["task_id"])
            ).scalar_one()
        )
    return TaskOut(
        task_id=row["task_id"],
        name=row["name"],
        question=row["question"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        archived_at=row["archived_at"],
        latest_run=latest_out,
        project_id=row["project_id"],
        source_count=source_count,
    )
