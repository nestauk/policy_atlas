"""Task-scoped serialization primitives for API mutations."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.engine import Connection, RowMapping

from policy_atlas.core.schema import task


def task_lock(conn: Connection, task_id: uuid.UUID) -> RowMapping:
    """Lock one task row for the duration of the caller transaction.

    Args:
        conn: Open transaction that owns the lock.
        task_id: Task to serialise mutations for.

    Returns:
        The locked task row.

    Raises:
        LookupError: If the task does not exist.
    """
    row = conn.execute(
        select(task).where(task.c.task_id == task_id).with_for_update()
    ).mappings().one_or_none()
    if row is None:
        raise LookupError(f"unknown task id: {task_id}")
    return row
