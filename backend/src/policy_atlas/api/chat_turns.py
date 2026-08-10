"""Two-phase durable service for project-scoped read-only chat turns."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.engine import Connection, Engine, RowMapping

from policy_atlas.api.app import ApiCapacity, ApiConflict
from policy_atlas.api.chat_scope import build_chat_readers, resolve_terminal_run_components
from policy_atlas.api.routers._common import owned_project
from policy_atlas.core import tracing
from policy_atlas.core.embeddings import EmbeddingBackend
from policy_atlas.core.schema import capability_run, chat_turn, conversation, project
from policy_atlas.evidence_base.synthesis.synthesis_tools import (
    SECTION_TURN_CAP,
    ToolExchange,
    build_section_tools,
    gathered_ids,
    run_tool_loop,
)
from policy_atlas.runtime.chat_backend import ChatBackend
from policy_atlas.runtime.chat_context import assemble_chat_frame, window_turns
from policy_atlas.runtime.chat_floor import apply_citation_floor
from policy_atlas.runtime.chat_prompt import (
    CHAT_MAX_OUTPUT_TOKENS,
    CHAT_MESSAGE_MAX,
    CHAT_MODEL,
    CHAT_PROMPT_VERSION,
    build_chat_messages,
)

log = structlog.get_logger()

_PENDING_TTL = timedelta(minutes=10)
_OWNER_PENDING_CAP = 2
_TURN_LOCKS_MAX = 256
_turn_locks_guard = threading.Lock()
_turn_locks: dict[uuid.UUID, threading.Lock] = {}


@dataclass(frozen=True)
class ChatTurnResult:
    """Completed durable chat-turn projection returned by the service."""

    id: uuid.UUID
    conversation_id: uuid.UUID
    turn_index: int
    client_turn_id: uuid.UUID
    user_message: str
    answer: str | None
    answer_payload: dict[str, Any] | None
    capability_run_id: uuid.UUID | None
    status: str
    created_at: datetime
    completed_at: datetime | None
    replayed: bool


def _now() -> datetime:
    """Return a timezone-aware persistence timestamp."""
    return datetime.now(UTC)


def _turn_lock(conversation_id: uuid.UUID) -> threading.Lock:
    """Return the bounded process-local single-flight guard for one chat."""
    with _turn_locks_guard:
        if conversation_id not in _turn_locks and len(_turn_locks) >= _TURN_LOCKS_MAX:
            for key in [key for key, lock in _turn_locks.items() if not lock.locked()]:
                del _turn_locks[key]
        return _turn_locks.setdefault(conversation_id, threading.Lock())


def _row_result(row: RowMapping, *, replayed: bool) -> ChatTurnResult:
    """Project a durable chat row without recomputing its answer."""
    payload = row["answer_payload"]
    return ChatTurnResult(
        id=row["id"],
        conversation_id=row["conversation_id"],
        turn_index=row["turn_index"],
        client_turn_id=row["client_turn_id"],
        user_message=row["user_message"],
        answer=row["answer"],
        answer_payload=dict(payload) if isinstance(payload, dict) else None,
        capability_run_id=row["capability_run_id"],
        status=row["status"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
        replayed=replayed,
    )


def _expire_stale_pending_turns(conn: Connection, *, user_id: str) -> None:
    """Mark this owner's expired pending chat turns failed in a short transaction."""
    owned_conversations = (
        select(conversation.c.id)
        .select_from(conversation.join(project, conversation.c.project_id == project.c.project_id))
        .where(project.c.owner_user_id == user_id)
    )
    conn.execute(
        update(chat_turn)
        .where(chat_turn.c.conversation_id.in_(owned_conversations))
        .where(chat_turn.c.status == "pending")
        .where(chat_turn.c.created_at < _now() - _PENDING_TTL)
        .values(status="failed", completed_at=_now())
    )


def _first_question_title(message: str) -> str:
    """Return the server-derived, word-boundary title for a new chat."""
    normalized = " ".join(message.split())
    if len(normalized) <= 80:
        return normalized or "New chat"
    boundary = normalized.rfind(" ", 0, 80)
    return normalized[: boundary if boundary > 0 else 80]


def _appraised_chunk_ids(transcript: list[ToolExchange]) -> set[str]:
    """Extract ids of appraised chunks actually exposed by chat tool calls."""
    appraised: set[str] = set()
    for exchange in transcript:
        if exchange["tool"] != "search_chunks":
            continue
        chunks = exchange["result"].get("chunks")
        if not isinstance(chunks, list):
            continue
        for chunk in chunks:
            if (
                isinstance(chunk, dict)
                and chunk.get("appraised") is True
                and isinstance(chunk.get("chunk_record_id"), str)
            ):
                appraised.add(chunk["chunk_record_id"])
    return appraised


def _phase_one_turn(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    conversation_id: uuid.UUID,
    user_id: str,
    message: str,
    client_turn_id: uuid.UUID,
) -> ChatTurnResult | uuid.UUID:
    """Reserve one chat row or replay a completed row under the project lock."""
    owned_project(conn, project_id=project_id, user_id=user_id, for_update=True)
    chat = (
        conn.execute(
            select(conversation)
            .where(conversation.c.id == conversation_id)
            .where(conversation.c.project_id == project_id)
        )
        .mappings()
        .one_or_none()
    )
    if chat is None or chat["kind"] != "chat" or chat["status"] != "active":
        raise LookupError("chat conversation not found")

    _expire_stale_pending_turns(conn, user_id=user_id)
    existing = (
        conn.execute(
            select(chat_turn)
            .where(chat_turn.c.conversation_id == conversation_id)
            .where(chat_turn.c.client_turn_id == client_turn_id)
        )
        .mappings()
        .one_or_none()
    )
    if existing is not None:
        if existing["user_message"] != message:
            raise ApiConflict("stale_turn", "client turn id is bound to a different message")
        if existing["status"] == "completed":
            return _row_result(existing, replayed=True)

    active_run = conn.execute(
        select(capability_run.c.capability_run_id)
        .where(capability_run.c.project_id == project_id)
        .where(capability_run.c.status.in_(("running", "paused")))
        .limit(1)
    ).scalar_one_or_none()
    if active_run is not None:
        raise ApiConflict("run_active", "finish the active run before starting a chat turn")
    completed_run = conn.execute(
        select(capability_run.c.capability_run_id)
        .where(capability_run.c.project_id == project_id)
        .where(capability_run.c.status.in_(("succeeded", "degraded")))
        .limit(1)
    ).scalar_one_or_none()
    if completed_run is None:
        raise ApiConflict("no_completed_run", "complete an analysis run before starting a chat")

    if existing is not None:
        latest_id = conn.execute(
            select(chat_turn.c.id)
            .where(chat_turn.c.conversation_id == conversation_id)
            .order_by(chat_turn.c.turn_index.desc())
            .limit(1)
        ).scalar_one()
        if latest_id != existing["id"]:
            raise ApiConflict("stale_turn", "only the latest chat turn may be retried")
        pending_after = conn.execute(
            select(chat_turn.c.id)
            .where(chat_turn.c.conversation_id == conversation_id)
            .where(chat_turn.c.turn_index > existing["turn_index"])
            .where(chat_turn.c.status == "pending")
            .limit(1)
        ).scalar_one_or_none()
        if pending_after is not None:
            raise ApiConflict("stale_turn", "a newer chat turn is pending")
        return cast(uuid.UUID, existing["id"])

    pending = conn.execute(
        select(chat_turn.c.id)
        .where(chat_turn.c.conversation_id == conversation_id)
        .where(chat_turn.c.status == "pending")
        .limit(1)
    ).scalar_one_or_none()
    if pending is not None:
        raise ApiConflict("chat_turn_in_progress", "a chat turn is already running")
    owner_pending = conn.execute(
        select(func.count())
        .select_from(
            chat_turn.join(conversation, chat_turn.c.conversation_id == conversation.c.id).join(
                project, conversation.c.project_id == project.c.project_id
            )
        )
        .where(project.c.owner_user_id == user_id)
        .where(chat_turn.c.status == "pending")
    ).scalar_one()
    if int(owner_pending) >= _OWNER_PENDING_CAP:
        raise ApiCapacity("chat_capacity", "too many chat turns are in progress")

    if chat["title"] == "New chat":
        conn.execute(
            update(conversation)
            .where(conversation.c.id == conversation_id)
            .values(title=_first_question_title(message))
        )
    max_turn_index = conn.execute(
        select(func.coalesce(func.max(chat_turn.c.turn_index), -1)).where(
            chat_turn.c.conversation_id == conversation_id
        )
    ).scalar_one()
    turn_id = uuid.uuid4()
    conn.execute(
        chat_turn.insert().values(
            id=turn_id,
            conversation_id=conversation_id,
            turn_index=int(max_turn_index) + 1,
            client_turn_id=client_turn_id,
            user_message=message,
            answer=None,
            answer_payload=None,
            capability_run_id=None,
            status="pending",
            created_at=_now(),
            completed_at=None,
        )
    )
    return turn_id


def _chat_inputs(
    engine: Engine, *, conversation_id: uuid.UUID, turn_id: uuid.UUID
) -> tuple[uuid.UUID | None, list[tuple[str, str]]]:
    """Read the immutable frame selector and completed prior turn window."""
    with engine.connect() as conn:
        entry_artefact_id = conn.execute(
            select(conversation.c.entry_artefact_id).where(conversation.c.id == conversation_id)
        ).scalar_one()
        rows = conn.execute(
            select(chat_turn.c.user_message, chat_turn.c.answer)
            .where(chat_turn.c.conversation_id == conversation_id)
            .where(chat_turn.c.id != turn_id)
            .where(chat_turn.c.status == "completed")
            .order_by(chat_turn.c.turn_index.asc())
        ).all()
    return entry_artefact_id, [(row[0], row[1]) for row in rows if row[1] is not None]


def _trace_id(root_span: Any) -> str | None:
    """Read the SDK-exposed trace id without pretending one exists in no-op mode."""
    if root_span is None:
        return None
    value = getattr(root_span, "trace_id", None) or getattr(root_span, "id", None)
    return str(value) if value is not None else None


def _chat_backend_turn(
    backend: ChatBackend,
    messages: list[dict[str, str]],
    transcript: list[ToolExchange],
    *,
    force_emit: bool,
) -> Any:
    """Invoke one backend turn with the plan-pinned output ceiling."""
    return backend.chat_turn(
        messages, transcript, force_emit=force_emit, max_output_tokens=CHAT_MAX_OUTPUT_TOKENS
    )


def run_chat_turn(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    conversation_id: uuid.UUID,
    user_id: str,
    message: str,
    client_turn_id: uuid.UUID,
    chat_backend: ChatBackend,
    embedding_backend: EmbeddingBackend | None = None,
    langfuse_client: Any = None,
    on_progress: Callable[[str], None] | None = None,
    on_delta: Callable[[str], None] | None = None,
) -> ChatTurnResult:
    """Run a chat turn with a short reservation and terminal commit transaction.

    Args:
        engine: Database engine.
        project_id: Owner-scoped project id.
        conversation_id: Active chat conversation id.
        user_id: Authenticated project owner.
        message: Current user question.
        client_turn_id: Client-minted idempotency key.
        chat_backend: Provider-neutral chat backend seam.
        embedding_backend: Optional query embedding backend for chat retrieval.
        langfuse_client: Optional tracing client.
        on_progress: Optional user-facing tool activity callback.
        on_delta: Reserved streaming delta callback, wired by Phase D.

    Returns:
        The completed or replayed durable chat turn.
    """
    del on_delta  # The C4 backend seam is buffered; Phase D owns token streaming.
    if len(message) > CHAT_MESSAGE_MAX:
        raise ValueError(f"chat message exceeds {CHAT_MESSAGE_MAX} characters")
    lock = _turn_lock(conversation_id)
    if not lock.acquire(blocking=False):
        raise ApiConflict("chat_turn_in_progress", "a chat turn is already running")
    try:
        with engine.begin() as conn:
            phase_one = _phase_one_turn(
                conn,
                project_id=project_id,
                conversation_id=conversation_id,
                user_id=user_id,
                message=message,
                client_turn_id=client_turn_id,
            )
        if isinstance(phase_one, ChatTurnResult):
            return phase_one
        turn_id = phase_one
        try:
            scope = resolve_terminal_run_components(engine, project_id=project_id)
            if scope is None:
                raise RuntimeError("completed capability run disappeared before chat execution")
            entry_artefact_id, prior_turns = _chat_inputs(
                engine, conversation_id=conversation_id, turn_id=turn_id
            )
            with engine.connect() as conn:
                frame = assemble_chat_frame(
                    conn, project_id=project_id, entry_artefact_id=entry_artefact_id
                )
            retriever, findings_reader, lookup_reader = build_chat_readers(
                engine, scope, project_id, embedding_backend=embedding_backend
            )
            tools = build_section_tools(
                retriever=retriever,
                findings_reader=findings_reader,
                lookup_reader=lookup_reader,
            )
            messages = build_chat_messages(
                frame_text=frame.text,
                window=[(turn.user_message, turn.answer) for turn in window_turns(prior_turns)],
                question=message,
            )

            def turn_fn(transcript: list[ToolExchange], *, force_emit: bool) -> Any:
                response, usage = _chat_backend_turn(
                    chat_backend, messages, transcript, force_emit=force_emit
                )
                return {
                    "emission": response.get("answer"),
                    "tool_calls": response.get("tool_calls", []),
                    "malformed": 0,
                }, usage

            labels = {
                "search_chunks": "Searching the evidence…",
                "query_findings": "Reading findings…",
                "lookup": "Looking up sources…",
            }
            with tracing.component_span(
                langfuse_client,
                run_id=turn_id,
                project_id=project_id,
                component="chat_v1",
                session_id=conversation_id,
            ) as root_span:
                loop = run_tool_loop(
                    turn_fn,
                    tools=tools,
                    turn_cap=SECTION_TURN_CAP,
                    retriever=retriever,
                    emit_label="emit_answer",
                    on_tool_start=(
                        (lambda name, _arguments: on_progress(labels[name]))
                        if on_progress is not None
                        else None
                    ),
                )
                if root_span is not None:
                    root_span.update(
                        metadata={"prompt_version": CHAT_PROMPT_VERSION, "model": CHAT_MODEL}
                    )
                trace_id = _trace_id(root_span)
            emission = loop["emission"]
            if emission is None:
                raise RuntimeError("chat loop completed without an answer emission")
            floored = apply_citation_floor(
                emission,
                tool_chunk_ids=gathered_ids(loop["transcript"])["chunk_ids"],
                tool_finding_ids=gathered_ids(loop["transcript"])["finding_ids"],
                frame_chunk_ids=set(frame.citable_chunk_ids),
                appraised_chunk_ids=_appraised_chunk_ids(loop["transcript"]),
            )
            payload = {
                "claims": floored.claims,
                "citations": floored.citations,
                "warning_not_evidence_checked": floored.warning_not_evidence_checked,
                "stripped": floored.stripped,
                "evidence_not_held": floored.evidence_not_held,
                "handoff": "evidence_not_held" if floored.evidence_not_held else None,
                "tool_digest": {
                    "calls": loop["tool_call_counts"],
                    "rejected": loop["rejected_tool_calls"],
                    "turns_used": loop["turns_used"],
                },
                "model_id": CHAT_MODEL,
                "prompt_version": CHAT_PROMPT_VERSION,
                "trace_id": trace_id,
            }
            with engine.begin() as conn:
                completed = conn.execute(
                    update(chat_turn)
                    .where(chat_turn.c.id == turn_id)
                    .where(chat_turn.c.status.in_(("pending", "failed", "cancelled")))
                    .values(
                        answer=floored.prose,
                        answer_payload=payload,
                        capability_run_id=scope.capability_run_id,
                        status="completed",
                        completed_at=_now(),
                    )
                )
                if completed.rowcount != 1:
                    raise RuntimeError("chat turn was not open at terminal commit")
                row = (
                    conn.execute(select(chat_turn).where(chat_turn.c.id == turn_id))
                    .mappings()
                    .one()
                )
            return _row_result(row, replayed=False)
        except Exception:
            log.exception(
                "chat_turn_failed", project_id=str(project_id), conversation_id=str(conversation_id)
            )
            with engine.begin() as conn:
                conn.execute(
                    update(chat_turn)
                    .where(chat_turn.c.id == turn_id)
                    .where(chat_turn.c.status.in_(("pending", "failed")))
                    .values(status="failed", completed_at=_now())
                )
            raise
    finally:
        lock.release()
