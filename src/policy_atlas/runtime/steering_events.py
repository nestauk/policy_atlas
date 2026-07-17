"""Steering-event emission chassis (task 024, decision 1).

Every human-in-the-loop steering moment — pause, decision (user, orchestrator or
standing-default), rejected adjustment, refused intent, skip and the boundary
watch's judgement routing — becomes a canonical ``event_log`` event keyed to a
``capability_run`` walk identity. This module is the single append surface for
that vocabulary: it builds the pinned payload shapes, enforces the run-id
attachment invariant, and appends through :func:`policy_atlas.core.events.append`
so append-only stays inviolate. Structlog only, no prints.

Run-id attachment (plan pin, review M2 — ``event_log.run_id`` is NOT NULL):
an ``after_component`` event attaches to the run it is about; ``before_component``
and walk-level events attach to the most-recent attempted run id. Either way the
resolved run id MUST be non-None: **no steering event is emitted before the first
component run exists**. :func:`emit`/:func:`emit_standalone` assert this.

Transactional pairing (contract decision 1, finding m1): decision/skip/re-run
events commit on the SAME connection as their adjacent state change (the
plan-version row insert, the abandon flip) — use :func:`emit` inside that
transaction. Pause/refused/rejected events have no state-change partner and are
standalone appends — use :func:`emit_standalone`, which owns a short transaction.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

import structlog
from sqlalchemy.engine import Connection, Engine

from policy_atlas.core import events

log = structlog.get_logger()

# --- Event-type vocabulary (plan "Event vocabulary" pin) -------------------
# All six are declared now; only the four Phase-1-reachable types (pause,
# decision, rejected, skipped) are emitted by task 2. REFUSED and
# AGENT_JUDGEMENT_ROUTED are wired by the router/watch tasks (14/15).
STEERING_PAUSE = "steering.pause"
STEERING_DECISION = "steering.decision"
STEERING_REJECTED = "steering.rejected"
STEERING_REFUSED = "steering.refused"
COMPONENT_SKIPPED = "component.skipped"
AGENT_JUDGEMENT_ROUTED = "agent_judgement_routed"

Boundary = Literal["after_component", "before_component", "walk"]
DecidedBy = Literal["user", "orchestrator", "standing_default"]
DecisionResponse = Literal["continue", "adjust", "abort", "mode_change"]
RerunMode = Literal["additive", "replacement"]

# The invariant message names the rule so a violation is self-describing.
_NO_RUN_ID_INVARIANT = (
    "steering event {event_type!r} has no attachable run_id: no steering event is "
    "emitted before the first component run exists (event_log.run_id is NOT NULL)"
)


def base_payload(
    *,
    capability_run_id: uuid.UUID,
    plan_id: uuid.UUID,
    plan_version: int,
    boundary: Boundary,
    component: str | None = None,
) -> dict[str, Any]:
    """Build the common payload every steering event carries.

    Args:
        capability_run_id: The walk identity the event belongs to.
        plan_id: Plan identity current at the boundary (str-encoded in payload).
        plan_version: Plan version current at the boundary.
        boundary: Where the event sits — ``after_component``/``before_component``
            for boundary events, ``walk`` for walk-level events.
        component: Component the boundary concerns, when applicable.

    Returns:
        A fresh payload dict carrying ``capability_run_id``/``plan_id`` (both
        str), ``plan_version`` (int), ``boundary`` and — when given —
        ``component``.
    """
    payload: dict[str, Any] = {
        "capability_run_id": str(capability_run_id),
        "plan_id": str(plan_id),
        "plan_version": plan_version,
        "boundary": boundary,
    }
    if component is not None:
        payload["component"] = component
    return payload


def decision_payload(
    base: dict[str, Any],
    *,
    decided_by: DecidedBy,
    authored_by: str,
    response: DecisionResponse,
    interpreted_action: Any,
    confirmed: bool,
    user_text: str | None = None,
    rerun_mode: RerunMode | None = None,
) -> dict[str, Any]:
    """Extend a base payload with the decision-specific attribution fields.

    Args:
        base: The :func:`base_payload` result to extend (copied, not mutated).
        decided_by: Who answered the decision — ``user``, ``orchestrator`` or
            ``standing_default``.
        authored_by: Who authored the options/action (attribution seam,
            decision 9); ``user`` for a live user answer.
        response: The bounded response — ``continue``/``adjust``/``abort``, or
            ``mode_change`` for an Adjust that carries a new steering mode.
        interpreted_action: The bounded delta / action summary, or ``None`` when
            there is no action (a plain continue).
        confirmed: Whether the decision was confirmed before applying.
        user_text: Verbatim user prose, only when prose was given (``None`` this
            phase — the CLI free-text surface lands in task 17).
        rerun_mode: ``additive``/``replacement`` when the decision triggers a
            re-run, else ``None``.

    Returns:
        A new payload dict — ``base`` plus the decision fields.
    """
    payload = dict(base)
    payload["decided_by"] = decided_by
    payload["authored_by"] = authored_by
    payload["response"] = response
    payload["interpreted_action"] = interpreted_action
    payload["confirmed"] = confirmed
    payload["user_text"] = user_text
    payload["rerun_mode"] = rerun_mode
    return payload


def emit(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID | None,
    event_type: str,
    payload: dict[str, Any],
) -> uuid.UUID:
    """Append one steering event on an existing connection (transactional pairing).

    Use for decision/skip/re-run events that must commit atomically with their
    adjacent state change: call inside the same ``engine.begin()`` block as the
    plan-version write or abandon flip.

    Args:
        conn: Open connection whose transaction the event joins.
        project_id: Project the event belongs to.
        run_id: The resolved attachment run id. MUST NOT be ``None``.
        event_type: One of the module's event-type constants.
        payload: The event body.

    Returns:
        The new event's ``event_id``.

    Raises:
        ValueError: If ``run_id`` is ``None`` — the run-id attachment invariant.
    """
    if run_id is None:
        raise ValueError(_NO_RUN_ID_INVARIANT.format(event_type=event_type))
    log.info(
        "steering.event",
        event_type=event_type,
        run_id=str(run_id),
        capability_run_id=payload.get("capability_run_id"),
        boundary=payload.get("boundary"),
        component=payload.get("component"),
    )
    return events.append(
        conn,
        project_id=project_id,
        run_id=run_id,
        event_type=event_type,
        payload=payload,
    )


def emit_standalone(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID | None,
    event_type: str,
    payload: dict[str, Any],
) -> uuid.UUID:
    """Append one steering event in its own short transaction (no state partner).

    Use for pause/refused/rejected events, which have no adjacent state change to
    pair with. The run-id invariant is asserted before opening the transaction.

    Args:
        engine: Engine to open the short transaction on.
        project_id: Project the event belongs to.
        run_id: The resolved attachment run id. MUST NOT be ``None``.
        event_type: One of the module's event-type constants.
        payload: The event body.

    Returns:
        The new event's ``event_id``.

    Raises:
        ValueError: If ``run_id`` is ``None`` — the run-id attachment invariant.
    """
    if run_id is None:
        raise ValueError(_NO_RUN_ID_INVARIANT.format(event_type=event_type))
    with engine.begin() as conn:
        return emit(
            conn,
            project_id=project_id,
            run_id=run_id,
            event_type=event_type,
            payload=payload,
        )
