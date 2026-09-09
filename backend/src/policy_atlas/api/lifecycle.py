"""Transactional task lifecycle operations and their audit events."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select, update
from sqlalchemy.engine import Connection

from policy_atlas.core import events
from policy_atlas.core.schema import task

log = structlog.get_logger()


def rename_task(
    conn: Connection,
    task_id: uuid.UUID,
    new_name: str,
    actor: str,
) -> None:
    """Rename a task and append its audit event in the caller transaction.

    Args:
        conn: Open connection whose transaction owns both writes.
        task_id: Task to rename.
        new_name: New task name.
        actor: Authenticated actor recorded in the event payload.

    Raises:
        LookupError: If ``task_id`` does not identify a task.
    """
    name_from = conn.execute(
        select(task.c.name).where(task.c.task_id == task_id)
    ).scalar_one_or_none()
    if name_from is None:
        raise LookupError(f"unknown task id: {task_id}")

    timestamp = datetime.now(UTC)
    conn.execute(
        update(task)
        .where(task.c.task_id == task_id)
        .values(name=new_name, updated_at=timestamp)
    )
    events.append(
        conn,
        task_id=task_id,
        run_id=None,
        event_type="task.renamed",
        payload={"name_from": name_from, "name_to": new_name, "actor": actor},
    )
    log.info("task.renamed", task_id=str(task_id), actor=actor)


def archive_task(conn: Connection, task_id: uuid.UUID, actor: str) -> bool:
    """Archive a task once and append a same-transaction audit event.

    Args:
        conn: Open connection whose transaction owns both writes.
        task_id: Task to archive.
        actor: Authenticated actor recorded in the event payload.

    Returns:
        ``True`` when this call archived the task, ``False`` when it was
        already archived.

    Raises:
        LookupError: If ``task_id`` does not identify a task.
    """
    status = conn.execute(
        select(task.c.status)
        .where(task.c.task_id == task_id)
        .with_for_update()
    ).scalar_one_or_none()
    if status is None:
        raise LookupError(f"unknown task id: {task_id}")
    if status == "archived":
        return False

    timestamp = datetime.now(UTC)
    conn.execute(
        update(task)
        .where(task.c.task_id == task_id)
        .values(status="archived", archived_at=timestamp, updated_at=timestamp)
    )
    events.append(
        conn,
        task_id=task_id,
        run_id=None,
        event_type="task.archived",
        payload={"actor": actor},
    )
    log.info("task.archived", task_id=str(task_id), actor=actor)
    return True
