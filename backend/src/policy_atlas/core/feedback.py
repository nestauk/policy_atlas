"""In-app feedback: the event envelope, retraction, and the trace join.

Postgres is the system of record. Every feedback record is one row of
``feedback_event`` with the same envelope columns, whatever its kind. The
Langfuse score that mirrors a record is written by
:func:`policy_atlas.core.tracing.score_feedback` after the row commits.

The functions here take an open connection and do not commit. The caller owns
the transaction, so that a record and its side rows commit together.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, NamedTuple

from sqlalchemy import exists, select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import FEEDBACK_TOGGLE_KINDS, event_log, feedback_event, runs


class RecordedFeedback(NamedTuple):
    """The result of :func:`record_feedback`.

    Attributes:
        feedback_event_id: The id of the new row.
        trace_id: The Langfuse trace that the new row joins to, if any.
        replaced_id: The id of the active row that the new row replaced (a
            toggle kind only), or ``None``. Its Langfuse score is now stale.
    """

    feedback_event_id: uuid.UUID
    trace_id: str | None
    replaced_id: uuid.UUID | None


def trace_id_for(
    conn: Connection, *, capability_run_id: uuid.UUID, component: str | None = None
) -> str | None:
    """Find the Langfuse trace that a feedback event on a run joins to.

    A user-facing run (``capability_run``) has one component run (``runs`` row)
    for each pipeline step, and each component run has its own trace. The
    ``runs`` table does not name its step, so the step comes from the
    ``component.started`` event of the component run.

    Args:
        conn: Open database connection.
        capability_run_id: The user-facing run.
        component: The pipeline step that the feedback is about (for example
            ``synthesise``), or ``None`` for the newest component run.

    Returns:
        The trace id of the newest matching component run, or ``None`` when no
        matching run has a stored trace (an old run, or tracing was off).
    """
    query = (
        select(runs.c.trace_id)
        .where(runs.c.capability_run_id == capability_run_id, runs.c.trace_id.is_not(None))
        .order_by(runs.c.started_at.desc())
        .limit(1)
    )
    if component is not None:
        query = query.where(
            exists().where(
                event_log.c.run_id == runs.c.run_id,
                event_log.c.task_id == runs.c.task_id,
                event_log.c.event_type == "component.started",
                event_log.c.payload["component"].astext == component,
            )
        )
    return conn.execute(query).scalar_one_or_none()


def retract_feedback(
    conn: Connection, *, feedback_event_id: uuid.UUID, user_id: str
) -> bool:
    """Retract one feedback record of a user. The row is kept.

    Args:
        conn: Open database connection.
        feedback_event_id: The record to retract.
        user_id: The caller. A user can retract only their own records.

    Returns:
        True when an active record of this user was retracted. False when
        there is no such record (wrong id, another user's record, or the
        record is already retracted).
    """
    retracted = conn.execute(
        feedback_event.update()
        .where(
            feedback_event.c.feedback_event_id == feedback_event_id,
            feedback_event.c.user_id == user_id,
            feedback_event.c.retracted_at.is_(None),
        )
        .values(retracted_at=datetime.now(UTC))
        .returning(feedback_event.c.feedback_event_id)
    ).first()
    return retracted is not None


def record_feedback(
    conn: Connection,
    *,
    user_id: str,
    surface: str,
    kind: str,
    target_type: str,
    target_id: str | None,
    payload: dict[str, Any],
    capability_run_id: uuid.UUID | None = None,
    component: str | None = None,
    pa_version: str | None = None,
) -> RecordedFeedback:
    """Insert one feedback record with the full envelope.

    For a toggle kind, a user has at most one active record per target. A new
    submit retracts the active record first and then inserts the new one, so
    the history of changes is kept. The unique partial index
    ``uq_feedback_event_active_toggle`` is the guard against two submits at the
    same time: the second one raises ``IntegrityError``.

    Args:
        conn: Open database connection. The ``app_user`` row of ``user_id``
            must exist.
        user_id: The token ``sub`` of the person who gives the feedback.
        surface: Where in the UI the feedback was given.
        kind: The feedback kind.
        target_type: The type of artefact that the feedback is about.
        target_id: The id of that artefact, or ``None`` for a problem report
            with no run.
        payload: The kind-specific fields, already validated by the caller.
        capability_run_id: The user-facing run, or ``None`` when there is none.
        component: The pipeline step whose trace this kind joins to. See
            :func:`trace_id_for`.
        pa_version: The version of the running application, if known.

    Returns:
        The ids that the caller needs to mirror the record to Langfuse.
    """
    replaced_id = None
    if kind in FEEDBACK_TOGGLE_KINDS:
        replaced_id = conn.execute(
            feedback_event.update()
            .where(
                feedback_event.c.user_id == user_id,
                feedback_event.c.target_type == target_type,
                feedback_event.c.target_id == target_id,
                feedback_event.c.kind == kind,
                feedback_event.c.retracted_at.is_(None),
            )
            .values(retracted_at=datetime.now(UTC))
            .returning(feedback_event.c.feedback_event_id)
        ).scalar_one_or_none()

    trace_id = (
        trace_id_for(conn, capability_run_id=capability_run_id, component=component)
        if capability_run_id is not None
        else None
    )
    feedback_event_id = uuid.uuid4()
    conn.execute(
        feedback_event.insert().values(
            feedback_event_id=feedback_event_id,
            user_id=user_id,
            capability_run_id=capability_run_id,
            trace_id=trace_id,
            surface=surface,
            kind=kind,
            target_type=target_type,
            target_id=target_id,
            payload=payload,
            pa_version=pa_version,
            created_at=datetime.now(UTC),
        )
    )
    return RecordedFeedback(feedback_event_id, trace_id, replaced_id)
