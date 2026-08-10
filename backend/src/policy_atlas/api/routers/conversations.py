"""NDJSON chat-turn streaming and explicit cancellation endpoints."""

from __future__ import annotations

import asyncio
import json
import queue
import threading
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.engine import Engine

from policy_atlas.api.app import ApiCapacity, ApiConflict
from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.chat_turns import ChatTurnResult, _phase_one_turn, run_chat_turn
from policy_atlas.api.contract import (
    CancelledEvent,
    CancelTurnOut,
    ChatStreamEvent,
    ChatTurnCreate,
    ChatTurnOut,
    CompletedEvent,
    DeltaEvent,
    FailedEvent,
    FailedEventError,
    ProgressEvent,
)
from policy_atlas.api.deps import (
    get_chat_backend,
    get_chat_embedding_backend,
    get_current_user,
    get_engine,
)
from policy_atlas.core import tracing
from policy_atlas.core.embeddings import EmbeddingBackend
from policy_atlas.core.schema import chat_turn, conversation, project
from policy_atlas.runtime.chat_backend import ChatBackend

router = APIRouter(
    prefix="/api/v1/conversations",
    tags=["conversations"],
    dependencies=[Depends(get_current_user)],
)

_LIVE_CANCELS_MAX = 256
_live_cancels_guard = threading.Lock()
_live_cancels: dict[uuid.UUID, threading.Event] = {}


def _register_cancel(turn_id: uuid.UUID) -> threading.Event:
    """Register a bounded live-turn stop handle before provider work begins."""
    with _live_cancels_guard:
        if turn_id not in _live_cancels and len(_live_cancels) >= _LIVE_CANCELS_MAX:
            # Registered events are always live. There is no safe eviction of
            # a live stop handle, so a saturated registry fails closed at the
            # route reservation instead of weakening explicit cancellation.
            raise ApiCapacity("chat_capacity", "too many chat turns are in progress")
        return _live_cancels.setdefault(turn_id, threading.Event())


def _deregister_cancel(turn_id: uuid.UUID) -> None:
    """Remove a terminal turn's process-local cancellation handle."""
    with _live_cancels_guard:
        _live_cancels.pop(turn_id, None)


def _live_cancel(turn_id: uuid.UUID) -> threading.Event | None:
    """Read a live cancel handle without exposing the mutable registry."""
    with _live_cancels_guard:
        return _live_cancels.get(turn_id)


def _turn_out(result: ChatTurnResult) -> ChatTurnOut:
    """Project a service result into the stable terminal/read payload."""
    payload = result.answer_payload or {}
    claims = payload.get("claims", [])
    citations = payload.get("citations", [])
    return ChatTurnOut(
        id=result.id,
        conversation_id=result.conversation_id,
        turn_index=result.turn_index,
        client_turn_id=result.client_turn_id,
        user_message=result.user_message,
        answer=result.answer,
        status=cast(Literal["pending", "completed", "failed", "cancelled"], result.status),
        created_at=result.created_at,
        completed_at=result.completed_at,
        claims=claims if isinstance(claims, list) else [],
        citations=citations if isinstance(citations, list) else [],
        warning_not_evidence_checked=bool(payload.get("warning_not_evidence_checked", False)),
        handoff=payload.get("handoff") if payload.get("handoff") == "evidence_not_held" else None,
        stopped_before_evidence_check=bool(payload.get("stopped_before_evidence_check", False)),
    )


def _line(event: Any) -> bytes:
    """Encode exactly one complete NDJSON event line."""
    return (json.dumps(event.model_dump(mode="json"), separators=(",", ":")) + "\n").encode()


@router.post(
    "/{conversation_id}/turns",
    response_model=ChatStreamEvent,
    response_class=StreamingResponse,
    responses={
        200: {
            "description": (
                "`application/x-ndjson`: progress/delta events followed by exactly one "
                "completed, failed, or cancelled terminal event."
            ),
            "content": {"application/x-ndjson": {"schema": {"type": "string"}}},
        }
    },
)
async def create_chat_turn_stream(
    conversation_id: uuid.UUID,
    body: ChatTurnCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    chat_backend: Annotated[ChatBackend, Depends(get_chat_backend)],
    embedding_backend: Annotated[EmbeddingBackend, Depends(get_chat_embedding_backend)],
) -> StreamingResponse:
    """Reserve a chat turn and stream its provider-neutral NDJSON lifecycle."""
    # Reservation happens before response headers. All ownership, eligibility,
    # idempotency, capacity and validation errors therefore use ErrorEnvelope.
    with engine.begin() as conn:
        row = (
            conn.execute(
                select(conversation.c.project_id)
                .select_from(
                    conversation.join(project, conversation.c.project_id == project.c.project_id)
                )
                .where(conversation.c.id == conversation_id)
                .where(project.c.owner_user_id == user.user_id)
                .where(project.c.status == "active")
            )
            .scalar_one_or_none()
        )
        if row is None:
            raise HTTPException(status_code=404, detail="resource not found")
        project_id = row
        existing_status = conn.execute(
            select(chat_turn.c.status)
            .where(chat_turn.c.conversation_id == conversation_id)
            .where(chat_turn.c.client_turn_id == body.client_turn_id)
        ).scalar_one_or_none()
        if existing_status == "pending":
            raise ApiConflict("chat_turn_in_progress", "a chat turn is already running")
        try:
            phase_one = _phase_one_turn(
                conn,
                project_id=project_id,
                conversation_id=conversation_id,
                user_id=user.user_id,
                message=body.message,
                client_turn_id=body.client_turn_id,
            )
        except LookupError:
            raise HTTPException(status_code=404, detail="resource not found") from None

    if isinstance(phase_one, ChatTurnResult):
        async def replay() -> AsyncIterator[bytes]:
            yield _line(CompletedEvent(turn=_turn_out(phase_one)))

        return StreamingResponse(replay(), media_type="application/x-ndjson")

    turn_id = phase_one
    cancel_event = _register_cancel(turn_id)
    events: queue.Queue[Any] = queue.Queue()

    def worker() -> None:
        """Complete persistence independently of a consumer disconnect."""
        try:
            result = run_chat_turn(
                engine,
                project_id=project_id,
                conversation_id=conversation_id,
                user_id=user.user_id,
                message=body.message,
                client_turn_id=body.client_turn_id,
                chat_backend=chat_backend,
                embedding_backend=embedding_backend,
                langfuse_client=tracing.get_langfuse(),
                on_progress=lambda label: events.put(ProgressEvent(label=label)),
                on_delta=lambda text: events.put(DeltaEvent(text=text)),
                cancel_event=cancel_event,
            )
            if result.status == "cancelled":
                events.put(CancelledEvent(turn=_turn_out(result)))
            else:
                events.put(CompletedEvent(turn=_turn_out(result)))
        except Exception:
            events.put(
                FailedEvent(
                    error=FailedEventError(code="chat_turn_failed", message="chat turn failed"),
                    turn_id=turn_id,
                )
            )
        finally:
            _deregister_cancel(turn_id)
            events.put(None)

    threading.Thread(target=worker, name=f"policy-atlas-chat-{turn_id}", daemon=True).start()

    async def stream() -> AsyncIterator[bytes]:
        # Cancellation of this generator (the client closing its fetch stream)
        # never reaches the independent worker above. It keeps its DB commit.
        while True:
            item = await asyncio.get_running_loop().run_in_executor(None, events.get)
            if item is None:
                return
            yield _line(item)

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@router.post("/{conversation_id}/turns/{turn_id}/cancel", response_model=CancelTurnOut)
def cancel_chat_turn(
    conversation_id: uuid.UUID,
    turn_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
) -> CancelTurnOut:
    """Explicitly stop a pending chat turn, preserving any streamed partial."""
    with engine.begin() as conn:
        status = (
            conn.execute(
                select(chat_turn.c.status)
                .select_from(
                    chat_turn.join(
                        conversation, chat_turn.c.conversation_id == conversation.c.id
                    ).join(project, conversation.c.project_id == project.c.project_id)
                )
                .where(chat_turn.c.id == turn_id)
                .where(chat_turn.c.conversation_id == conversation_id)
                .where(project.c.owner_user_id == user.user_id)
            )
            .scalar_one_or_none()
        )
        if status is None:
            raise HTTPException(status_code=404, detail="resource not found")
        live = _live_cancel(turn_id)
        if status == "pending" and live is not None:
            live.set()
        elif status == "pending":
            conn.execute(
                update(chat_turn)
                .where(chat_turn.c.id == turn_id)
                .where(chat_turn.c.status == "pending")
                .values(status="cancelled", completed_at=datetime.now(UTC))
            )
            status = conn.execute(
                select(chat_turn.c.status).where(chat_turn.c.id == turn_id)
            ).scalar_one()
    return CancelTurnOut(
        status=cast(Literal["pending", "completed", "failed", "cancelled"], status)
    )
