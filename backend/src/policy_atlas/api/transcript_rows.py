"""Writes to one open Task Agent transcript row, shared by the turn dispatchers.

A row is *open* while it is ``pending`` (a fresh turn) or ``failed`` (the
latest turn, retried in place); every write that completes, fails or
half-commits a turn is guarded on that.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Update, select, update
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.contract import TaskAgentTurnOut
from policy_atlas.core.schema import task_agent_transcript


def open_row(task_id: uuid.UUID, transcript_id: uuid.UUID) -> Update:
    """Return an ``UPDATE`` of one transcript row, guarded on it being open."""
    return (
        update(task_agent_transcript)
        .where(task_agent_transcript.c.id == transcript_id)
        .where(task_agent_transcript.c.task_id == task_id)
        .where(task_agent_transcript.c.status.in_(("pending", "failed")))
    )


def answer_window(
    conn: Connection, task_id: uuid.UUID, conversation_id: uuid.UUID
) -> list[tuple[str, str]]:
    """Return this conversation's completed exchanges for an answer's memory."""
    rows = conn.execute(
        select(task_agent_transcript.c.user_message, task_agent_transcript.c.reply)
        .where(task_agent_transcript.c.task_id == task_id)
        .where(task_agent_transcript.c.conversation_id == conversation_id)
        .where(task_agent_transcript.c.status == "completed")
        .order_by(task_agent_transcript.c.turn_index.asc())
    ).all()
    return [(row[0], row[1]) for row in rows if row[1] is not None]


def fail(engine: Engine, *, task_id: uuid.UUID, transcript_id: uuid.UUID) -> None:
    """Terminally fail one open transcript row (retryable while it is latest)."""
    with engine.begin() as conn:
        conn.execute(
            open_row(task_id, transcript_id).values(status="failed", completed_at=datetime.now(UTC))
        )


def complete(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    transcript_id: uuid.UUID,
    result: TaskAgentTurnOut,
    extra: Mapping[str, Any] | None = None,
) -> None:
    """Complete one open transcript row with a turn's durable projection.

    Args:
        conn: The caller's open transaction.
        task_id: The task owning the row.
        transcript_id: The row.
        result: The turn as stored (raw, unlabelled).
        extra: Further columns to write (``task_agent_state``, ``part``);
            columns left out keep their stored value.

    Raises:
        RuntimeError: If the row was no longer open.
    """
    completed = conn.execute(
        open_row(task_id, transcript_id).values(
            reply=result.reply,
            response=result.model_dump(mode="json"),
            suggestions=result.suggestions,
            status="completed",
            completed_at=datetime.now(UTC),
            **(extra or {}),
        )
    )
    if completed.rowcount != 1:
        raise RuntimeError("task_agent transcript turn was not open at its commit")
