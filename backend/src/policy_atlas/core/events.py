"""Canonical event-log repository — append-only, ordered by (project_id, sequence).

Append-only is enforced at the repository layer: no update/delete code path exists.
Separate from LangGraph execution checkpoints (audit plane ≠ telemetry plane).

# ponytail: app-side max+1 safe under serial single-writer (v3.0 model);
#            DB trigger / REVOKE is the deferred hardening path.
# Cross-project contamination is enforced by the DB composite FK
# event_log(run_id, project_id) → runs(run_id, project_id) when run_id is set.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import event_log


def append(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID | None,
    event_type: str,
    payload: dict[str, Any],
) -> uuid.UUID:
    """Append one event to a project's log and return its ID.

    Assigns ``sequence = max+1`` per project. **Assumes a single writer per project**
    (the v3.0 serial model, ADR 0001 §6): concurrent appenders would read the same max and
    collide on the ``(project_id, sequence)`` unique constraint — a hard ``IntegrityError``,
    never silent misordering. A concurrency-safe allocator is a registered deferred seam.

    Args:
        conn: Open database connection.
        project_id: Project the event belongs to; scopes the sequence counter.
        run_id: Run the event belongs to, or ``None`` for a project lifecycle
            audit event.
        event_type: Event name (e.g. ``"run.started"``).
        payload: JSON-serialisable event body.

    Returns:
        The new event's ``event_id``.
    """
    seq_result = conn.execute(
        select(func.coalesce(func.max(event_log.c.sequence), 0)).where(
            event_log.c.project_id == project_id
        )
    )
    current_max = seq_result.scalar_one()
    sequence = current_max + 1

    event_id = uuid.uuid4()
    conn.execute(
        event_log.insert().values(
            event_id=event_id,
            run_id=run_id,
            project_id=project_id,
            sequence=sequence,
            event_type=event_type,
            occurred_at=datetime.now(UTC),
            payload=payload,
        )
    )
    return event_id


def read(
    conn: Connection,
    project_id: uuid.UUID,
    event_types: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Return events for a project ordered by sequence (not occurred_at).

    Args:
        conn: Open database connection.
        project_id: Project whose events to read.
        event_types: When given, restrict the read to these ``event_type``
            values (pushed into the SQL ``WHERE``, not a post-filter) —
            callers that only ever want a fixed vocabulary avoid a full
            project-history scan. ``None`` (default) reads every event,
            unchanged from prior behaviour.

    Returns:
        Event rows as dicts, ordered by ascending sequence.
    """
    query = select(event_log).where(event_log.c.project_id == project_id)
    if event_types is not None:
        query = query.where(event_log.c.event_type.in_(event_types))
    rows = conn.execute(query.order_by(event_log.c.sequence))
    return [dict(row._mapping) for row in rows]


def read_for_run(
    conn: Connection, project_id: uuid.UUID, run_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Return all events for one run within a project, ordered by sequence.

    Args:
        conn: Open database connection.
        project_id: Project whose events to read.
        run_id: Run to scope the read to.

    Returns:
        Event rows as dicts, ordered by ascending sequence.
    """
    rows = conn.execute(
        select(event_log)
        .where(event_log.c.project_id == project_id)
        .where(event_log.c.run_id == run_id)
        .order_by(event_log.c.sequence)
    )
    return [dict(row._mapping) for row in rows]
