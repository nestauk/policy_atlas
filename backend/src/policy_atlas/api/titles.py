"""Short names written by a model: a task's from its question, a chat's (task 058, round 14).

A task is created with a name cut from the question the user typed. Once the
user confirms the refined question (the plan is approved, or the question part
settles), :func:`name_task_from_question` asks the ``task_title`` step for a
short name and renames the task through :func:`~.lifecycle.rename_task`, as
Policy Atlas (actor ``agent``), with the title prompt's version and the
question in the event. It never overrides a name the user chose: a task the
user has renamed keeps its name. A failed call, or one that writes no line,
keeps the name too.

A chat is titled from its first message (:func:`name_chat_from_message`): the
first message's reservation writes a cut of the message at once, and the
``chat_title`` step's line replaces it; the cut stays when the call fails or
writes nothing.

Both run outside any request transaction, off the request's own thread
(:func:`in_background`), so the model call never holds a lock or delays a
reply.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from typing import Literal, Protocol

import structlog
from sqlalchemy import select, update
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.lifecycle import both_generations, rename_task
from policy_atlas.core.schema import conversation, event_log, task
from policy_atlas.runtime.title_prompt import TASK_TITLE_PROMPT_VERSION, clean_title

log = structlog.get_logger()


class TitleWriter(Protocol):
    """The title calls' seam: ``OpenAIAgentBackend`` and ``StubAgentBackend``."""

    def write_title(
        self,
        kind: Literal["task", "chat"],
        text: str,
        *,
        session_id: uuid.UUID | None = None,
    ) -> str | None:
        """Write a short title from a confirmed question or a chat's first message.

        Args:
            kind: ``task`` (``task_title_v1``) or ``chat`` (``chat_title_v1``).
            text: The question or the message.
            session_id: Optional Langfuse session id.

        Returns:
            The model's line, uncleaned, or ``None`` when it writes none.

        Raises:
            Exception: Any failure of the call; the caller keeps the name.
        """
        ...

#: The actor a written name is recorded under: History says "Policy Atlas".
TITLE_ACTOR = "agent"
_SYSTEM_ACTORS = frozenset({"agent", "orchestrator", "standing_default"})
_RENAMED = both_generations("renamed")


def _renames(conn: Connection, task_id: uuid.UUID) -> list[dict[str, object]]:
    rows = conn.execute(
        select(event_log.c.payload)
        .where(event_log.c.task_id == task_id, event_log.c.event_type.in_(_RENAMED))
        .order_by(event_log.c.sequence)
    ).scalars()
    return [row for row in rows if isinstance(row, dict)]


def user_renamed(conn: Connection, task_id: uuid.UUID) -> bool:
    """Whether a person has renamed the task (any rename not by Policy Atlas)."""
    return any(payload.get("actor") not in _SYSTEM_ACTORS for payload in _renames(conn, task_id))


def _named_for(conn: Connection, task_id: uuid.UUID) -> str | None:
    """The question the latest written name stands for, if any."""
    for payload in reversed(_renames(conn, task_id)):
        if payload.get("actor") == TITLE_ACTOR:
            question = payload.get("question")
            return question if isinstance(question, str) else None
    return None


def name_task_from_question(
    engine: Engine, agent: TitleWriter, *, task_id: uuid.UUID, question: str | None
) -> str | None:
    """Rename a task from its confirmed question, unless the user named it.

    Skips the call when the question is blank, the user has renamed the task,
    or the task already carries a name written for this same question.

    Args:
        engine: Database engine.
        agent: The title backend.
        task_id: The task.
        question: The refined question the user confirmed.

    Returns:
        The new name, or ``None`` when the task kept its name.
    """
    text = " ".join((question or "").split())
    if not text:
        return None
    with engine.connect() as conn:
        if user_renamed(conn, task_id) or _named_for(conn, task_id) == text:
            return None
    try:
        line = agent.write_title("task", text, session_id=task_id)
    except Exception:
        # A failed call keeps the name the task has.
        log.warning("task.title_failed", task_id=str(task_id), exc_info=True)
        return None
    if line is None or not line.strip():
        # No title written: the name the task has stands.
        return None
    name = clean_title(line, fallback=text)
    with engine.begin() as conn:
        current = conn.execute(
            select(task.c.name).where(task.c.task_id == task_id).with_for_update()
        ).scalar_one_or_none()
        # Checked again under the row lock: the user may have renamed it
        # while the call ran.
        if current is None or user_renamed(conn, task_id) or current == name:
            return None
        rename_task(
            conn,
            task_id,
            name,
            TITLE_ACTOR,
            extra={"prompt_version": TASK_TITLE_PROMPT_VERSION, "question": text},
        )
    return name


def name_chat_from_message(
    engine: Engine,
    agent: TitleWriter,
    *,
    conversation_id: uuid.UUID,
    message: str,
    placeholder: str,
) -> str | None:
    """Title a chat from its first message, in place of the message's cut.

    The first message's reservation titles the chat with a cut of the message
    at once (``placeholder``); this replaces it with the ``chat_title`` step's
    line while the chat still carries that cut. A failed call, or one that
    writes nothing, leaves the cut.

    Args:
        engine: Database engine.
        agent: The title backend.
        conversation_id: The chat.
        message: The user's first message.
        placeholder: The title the reservation wrote.

    Returns:
        The title written, or ``None`` when the chat kept its title.
    """
    try:
        line = agent.write_title("chat", message, session_id=conversation_id)
    except Exception:
        log.warning("chat.title_failed", conversation_id=str(conversation_id), exc_info=True)
        return None
    if line is None or not line.strip():
        return None
    written = clean_title(line, fallback=message)
    with engine.begin() as conn:
        updated = conn.execute(
            update(conversation)
            .where(conversation.c.id == conversation_id)
            # Only while nobody has titled it meanwhile.
            .where(conversation.c.title == placeholder)
            .values(title=written)
        ).rowcount
    return written if updated else None


def in_background(work: Callable[[], object], *, name: str) -> threading.Thread:
    """Run ``work`` on a daemon thread; a failure is logged, never raised."""

    def run() -> None:
        try:
            work()
        except Exception:
            log.exception("titles.background_failed", name=name)

    thread = threading.Thread(target=run, name=name, daemon=True)
    thread.start()
    return thread
