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

# --- Lifecycle event vocabulary, both generations (task 038, contract V1) ---
#
# New writes emit `task.*`. `event_log` is append-only, so rows written before
# the slice still say `project.*` and every reader must accept both — this is
# the one place the pairing is declared. The four kinds are the ones the
# writers emit: rename and archive here, share and unshare in `routers/tasks`.
LIFECYCLE_EVENT_KINDS: tuple[str, ...] = (
    "renamed",
    "archived",
    "shared_publicly",
    "unshared",
)


def both_generations(*kinds: str) -> frozenset[str]:
    """Return each lifecycle kind under both the new and the pre-038 prefix.

    Args:
        *kinds: Bare kind names, e.g. ``"renamed"`` — each must be one of
            :data:`LIFECYCLE_EVENT_KINDS`.

    Returns:
        The ``task.<kind>`` and ``project.<kind>`` event types for every kind.

    Raises:
        ValueError: If a name is not a declared lifecycle kind.
    """
    unknown = set(kinds) - set(LIFECYCLE_EVENT_KINDS)
    if unknown:
        raise ValueError(f"not lifecycle event kinds: {sorted(unknown)}")
    return frozenset(f"{prefix}.{kind}" for kind in kinds for prefix in ("task", "project"))


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
