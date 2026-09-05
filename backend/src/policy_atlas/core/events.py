"""Canonical event-log repository — append-only, ordered by (task_id, sequence).

Append-only is enforced at the repository layer: no update/delete code path exists.
Separate from LangGraph execution checkpoints (audit plane ≠ telemetry plane).

# ponytail: app-side max+1 safe under serial single-writer (v3.0 model);
#            DB trigger / REVOKE is the deferred hardening path.
# Cross-task contamination is enforced by the DB composite FK
# event_log(run_id, task_id) → runs(run_id, task_id) when run_id is set.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.schema import event_log


def append(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID | None,
    event_type: str,
    payload: dict[str, Any],
) -> uuid.UUID:
    """Append one event to a task's log and return its ID.

    Assigns ``sequence = max+1`` per task with a bounded SAVEPOINT retry on
    collision: since 025 the walk executor and the API's task-locked
    mutations are two unserialized writer families, so concurrent appenders can
    read the same max — the ``(task_id, sequence)`` unique constraint turns
    that into an ``IntegrityError`` we retry, never silent misordering.

    Args:
        conn: Open database connection.
        task_id: Task the event belongs to; scopes the sequence counter.
        run_id: Run the event belongs to, or ``None`` for a task lifecycle
            audit event.
        event_type: Event name (e.g. ``"run.started"``).
        payload: JSON-serialisable event body.

    Returns:
        The new event's ``event_id``.
    """
    # Two writer families exist per task since 025 (the walk executor and
    # API mutations under the task row lock), so the max+1 read can race —
    # retry the insert under a SAVEPOINT so an (task_id, sequence) collision
    # re-reads instead of poisoning the caller's transaction or failing a
    # component commit (review finding, 2026-07-21). Collisions stay hard
    # errors after the bounded retries; misordering remains impossible.
    event_id = uuid.uuid4()
    for attempt in range(5):
        current_max = conn.execute(
            select(func.coalesce(func.max(event_log.c.sequence), 0)).where(
                event_log.c.task_id == task_id
            )
        ).scalar_one()
        savepoint = conn.begin_nested()
        try:
            conn.execute(
                event_log.insert().values(
                    event_id=event_id,
                    run_id=run_id,
                    task_id=task_id,
                    sequence=current_max + 1,
                    event_type=event_type,
                    occurred_at=datetime.now(UTC),
                    payload=payload,
                )
            )
            savepoint.commit()
            return event_id
        except IntegrityError:
            savepoint.rollback()
            if attempt == 4:
                raise
    raise AssertionError("unreachable")  # pragma: no cover


def read(
    conn: Connection,
    task_id: uuid.UUID,
    event_types: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Return events for a task ordered by sequence (not occurred_at).

    Args:
        conn: Open database connection.
        task_id: Task whose events to read.
        event_types: When given, restrict the read to these ``event_type``
            values (pushed into the SQL ``WHERE``, not a post-filter) —
            callers that only ever want a fixed vocabulary avoid a full
            task-history scan. ``None`` (default) reads every event,
            unchanged from prior behaviour.

    Returns:
        Event rows as dicts, ordered by ascending sequence.
    """
    query = select(event_log).where(event_log.c.task_id == task_id)
    if event_types is not None:
        query = query.where(event_log.c.event_type.in_(event_types))
    rows = conn.execute(query.order_by(event_log.c.sequence))
    return [dict(row._mapping) for row in rows]


def read_for_run(
    conn: Connection, task_id: uuid.UUID, run_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Return all events for one run within a task, ordered by sequence.

    Args:
        conn: Open database connection.
        task_id: Task whose events to read.
        run_id: Run to scope the read to.

    Returns:
        Event rows as dicts, ordered by ascending sequence.
    """
    rows = conn.execute(
        select(event_log)
        .where(event_log.c.task_id == task_id)
        .where(event_log.c.run_id == run_id)
        .order_by(event_log.c.sequence)
    )
    return [dict(row._mapping) for row in rows]
