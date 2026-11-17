"""Record and retract in-app feedback events (task 059, ADR 0045).

The database row is the record. A Langfuse score on the trace of the component
run the feedback is about is a mirror, written after the row commits; the
score id is the row id, so the two reconcile. Rows are never deleted: an undo
sets ``retracted_at`` and deletes the mirrored score.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from langfuse import Langfuse
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.core import tracing
from policy_atlas.core.schema import FEEDBACK_TOGGLE_KINDS, feedback_event, runs


def record_feedback_event(
    conn: Connection,
    *,
    user_id: str,
    capability_run_id: uuid.UUID | None,
    component_run_id: uuid.UUID | None,
    surface: str,
    kind: str,
    target_type: str,
    target_id: str | None,
    payload: dict[str, Any],
    pa_version: str | None,
) -> tuple[uuid.UUID, str | None, list[uuid.UUID]]:
    """Insert one feedback event, replacing the active one for a toggle kind.

    For a kind in ``FEEDBACK_TOGGLE_KINDS`` the user's active row for the same
    run, target and kind is retracted first, in the same transaction, so a
    changed answer leaves one active row and keeps the history.

    Args:
        conn: Open database connection, inside a transaction.
        user_id: The token subject of the person giving the feedback. Their
            ``app_user`` row must exist.
        capability_run_id: The run the feedback is about, or ``None`` for a
            problem report made before a run exists.
        component_run_id: The component run whose trace the feedback joins
            to (ADR 0045 decision 5), or ``None`` when there is none.
        surface: Where in the UI the feedback was raised.
        kind: The feedback kind.
        target_type: What the feedback is attached to.
        target_id: The internal id of the target, as text.
        payload: The kind's fields, already validated by the caller.
        pa_version: The deployed version, or ``None``.

    Returns:
        The new row's id, the trace id copied from the component run (``None``
        when that run has none), and the ids of the rows this one replaced.

    Raises:
        sqlalchemy.exc.IntegrityError: A vocabulary check or foreign key
            rejects the row, or a concurrent submit won the toggle.
    """
    now = datetime.now(UTC)
    replaced: list[uuid.UUID] = []
    if kind in FEEDBACK_TOGGLE_KINDS:
        replaced = list(
            conn.execute(
                feedback_event.update()
                .where(
                    feedback_event.c.user_id == user_id,
                    feedback_event.c.capability_run_id == capability_run_id,
                    feedback_event.c.target_type == target_type,
                    feedback_event.c.target_id == target_id,
                    feedback_event.c.kind == kind,
                    feedback_event.c.retracted_at.is_(None),
                )
                .values(retracted_at=now)
                .returning(feedback_event.c.feedback_event_id)
            ).scalars()
        )
    trace_id = (
        None
        if component_run_id is None
        else conn.execute(
            select(runs.c.trace_id).where(runs.c.run_id == component_run_id)
        ).scalar_one_or_none()
    )
    event_id = uuid.uuid4()
    conn.execute(
        feedback_event.insert().values(
            feedback_event_id=event_id,
            user_id=user_id,
            capability_run_id=capability_run_id,
            trace_id=trace_id,
            surface=surface,
            kind=kind,
            target_type=target_type,
            target_id=target_id,
            payload=payload,
            pa_version=pa_version,
            created_at=now,
        )
    )
    return event_id, trace_id, replaced


def submit_feedback(
    engine: Engine,
    client: Langfuse | None,
    *,
    score_value: float | str,
    comment: str | None = None,
    score_metadata: dict[str, Any] | None = None,
    **event: Any,
) -> uuid.UUID:
    """Record one feedback event, then mirror it as a Langfuse score.

    The row commits before the mirror runs, and a mirror failure is logged
    and never raised (``tracing.feedback_score``).

    Args:
        engine: Database engine; this function owns the transaction.
        client: Langfuse client, or ``None`` for no-op tracing.
        score_value: The score for this kind: a number or a category name.
        comment: The user's free text, when there is some. It goes to the
            score comment and nowhere else outside the database.
        score_metadata: Extra score fields for the kind.
        **event: The keyword arguments of ``record_feedback_event``.

    Returns:
        The new row's id.
    """
    with engine.begin() as conn:
        event_id, trace_id, replaced = record_feedback_event(conn, **event)
    for old_id in replaced:
        tracing.delete_feedback_score(client, score_id=str(old_id))
    tracing.feedback_score(
        client,
        trace_id=trace_id,
        score_id=str(event_id),
        name=event["kind"],
        value=score_value,
        comment=comment,
        metadata={"feedback_event_id": str(event_id), **(score_metadata or {})},
    )
    return event_id


def retract_feedback(
    engine: Engine,
    client: Langfuse | None,
    *,
    user_id: str,
    feedback_event_id: uuid.UUID,
) -> bool:
    """Retract one of a user's own feedback events and delete its score.

    Args:
        engine: Database engine; this function owns the transaction.
        client: Langfuse client, or ``None`` for no-op tracing.
        user_id: The token subject of the caller. Another user's row is
            never retracted.
        feedback_event_id: The row to retract.

    Returns:
        Whether an active row of this user was retracted.
    """
    with engine.begin() as conn:
        retracted = conn.execute(
            feedback_event.update()
            .where(
                feedback_event.c.feedback_event_id == feedback_event_id,
                feedback_event.c.user_id == user_id,
                feedback_event.c.retracted_at.is_(None),
            )
            .values(retracted_at=datetime.now(UTC))
        ).rowcount
    if retracted:
        tracing.delete_feedback_score(client, score_id=str(feedback_event_id))
    return bool(retracted)
