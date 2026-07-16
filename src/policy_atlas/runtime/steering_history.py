"""Steering-history read model (task 024, decision 3).

The front-end's read surface over a project's steering history: a deterministic,
per-walk projection built from the ``capability_run`` table (the walk identities)
and the project's ``event_log`` (the steering-event vocabulary emitted by
:mod:`policy_atlas.runtime.steering_events`). Pure read — no writes, no LLM.

Partitioning pin (plan m3): walk membership is decided by the PAYLOAD's
``capability_run_id`` key, never by an ``event_log.run_id`` join.
``event_log.run_id`` is FK plumbing (the run a steering event happens to attach
to for the NOT NULL invariant); the payload key is the semantic walk the event
belongs to. Events whose payload lacks the key are excluded by the vocabulary
filter anyway — every steering-event payload carries it (:func:`policy_atlas.
runtime.steering_events.base_payload`).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core import events
from policy_atlas.core.schema import capability_run
from policy_atlas.runtime.steering_events import (
    AGENT_JUDGEMENT_ROUTED,
    COMPONENT_SKIPPED,
    STEERING_DECISION,
    STEERING_PAUSE,
    STEERING_REFUSED,
    STEERING_REJECTED,
)

# The steering-event vocabulary (plan "Event vocabulary" pin) — the only
# event_type values that ever belong to a walk story.
STEERING_EVENT_TYPES = frozenset(
    {
        STEERING_PAUSE,
        STEERING_DECISION,
        STEERING_REJECTED,
        STEERING_REFUSED,
        COMPONENT_SKIPPED,
        AGENT_JUDGEMENT_ROUTED,
    }
)


def steering_history(
    conn: Connection,
    project_id: uuid.UUID,
    capability_run_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """Rebuild a project's steering history as one story per capability-run walk.

    Args:
        conn: Open database connection. Pure read — no writes are issued.
        project_id: Project whose walks (and events) to read.
        capability_run_id: When given, scope the result to that single walk.

    Returns:
        Walk stories ordered by ``started_at`` then ``capability_run_id`` for
        determinism. Each story is a dict with ``capability_run_id``,
        ``status``, ``plan_id``, ``plan_version``, ``session_id``,
        ``started_at``, ``ended_at`` and ``events`` — the ordered list of
        steering events (``sequence``, ``event_type``, ``occurred_at``,
        ``payload``) belonging to that walk by payload key. With
        ``capability_run_id=None`` this covers every walk in the project; with
        a specific id it is a single-element list (empty ``events`` if the
        walk emitted none), or ``[]`` if no such walk exists.
    """
    walk_rows = conn.execute(
        select(capability_run)
        .where(capability_run.c.project_id == project_id)
        .order_by(capability_run.c.started_at, capability_run.c.capability_run_id)
    ).all()

    if capability_run_id is not None:
        walk_rows = [row for row in walk_rows if row.capability_run_id == capability_run_id]
        if not walk_rows:
            return []

    events_by_walk: dict[str, list[dict[str, Any]]] = {}
    for entry in events.read(conn, project_id):
        if entry["event_type"] not in STEERING_EVENT_TYPES:
            continue
        walk_key = entry["payload"].get("capability_run_id")
        if walk_key is None:
            # Not a walk-scoped steering event — excluded regardless of vocabulary.
            continue
        events_by_walk.setdefault(walk_key, []).append(
            {
                "sequence": entry["sequence"],
                "event_type": entry["event_type"],
                "occurred_at": entry["occurred_at"],
                "payload": entry["payload"],
            }
        )

    return [
        {
            "capability_run_id": row.capability_run_id,
            "status": row.status,
            "plan_id": row.plan_id,
            "plan_version": row.plan_version,
            "session_id": row.session_id,
            "started_at": row.started_at,
            "ended_at": row.ended_at,
            "events": events_by_walk.get(str(row.capability_run_id), []),
        }
        for row in walk_rows
    ]
