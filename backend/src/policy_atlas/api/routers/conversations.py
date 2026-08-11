"""Conversation library, lifecycle, turn reads, and NDJSON chat streaming."""

from __future__ import annotations

import asyncio
import json
import queue
import threading
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.engine import Connection, Engine, RowMapping

from policy_atlas.api.app import ApiCapacity, ApiConflict
from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.chat_enrichment import enrich_chat_turn
from policy_atlas.api.chat_turns import ChatTurnResult, _phase_one_turn, run_chat_turn
from policy_atlas.api.contract import (
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_MAX,
    CancelledEvent,
    CancelTurnOut,
    ChatStreamEvent,
    ChatTurnCreate,
    ChatTurnOut,
    CompletedEvent,
    ConversationCreate,
    ConversationKind,
    ConversationListItemOut,
    ConversationOut,
    ConversationStatus,
    ConversationUpdate,
    DeltaEvent,
    FailedEvent,
    FailedEventError,
    LatestTurnPreviewOut,
    Page,
    PageMeta,
    ProgressEvent,
)
from policy_atlas.api.deps import (
    get_chat_backend,
    get_chat_embedding_backend,
    get_conn,
    get_current_user,
    get_engine,
    get_grounding_judge_backend,
)
from policy_atlas.api.routers._common import owned_project
from policy_atlas.core import tracing
from policy_atlas.core.embeddings import EmbeddingBackend
from policy_atlas.core.schema import (
    artefact,
    chat_turn,
    conversation,
    planning_transcript,
    project,
)
from policy_atlas.evidence_base.synthesis.grounding_judge import GroundingJudgeBackend
from policy_atlas.runtime.chat_backend import ChatBackend

router = APIRouter(
    prefix="/api/v1/conversations",
    tags=["conversations"],
    dependencies=[Depends(get_current_user)],
)

project_router = APIRouter(
    prefix="/api/v1/projects",
    tags=["conversations"],
    dependencies=[Depends(get_current_user)],
)

_LIVE_CANCELS_MAX = 256
_live_cancels_guard = threading.Lock()
_live_cancels: dict[uuid.UUID, threading.Event] = {}

_PREVIEW_MAX_CHARS = 240


def _not_found() -> HTTPException:
    """Return the shared opaque resource-not-found response."""
    return HTTPException(status_code=404, detail="resource not found")


def _conversation_out(row: RowMapping) -> ConversationOut:
    """Project a durable conversation row into the public read shape."""
    return ConversationOut(
        id=row["id"],
        project_id=row["project_id"],
        kind=cast(ConversationKind, row["kind"]),
        title=row["title"],
        status=cast(ConversationStatus, row["status"]),
        entry_artefact_id=row["entry_artefact_id"],
        created_at=row["created_at"],
        closed_at=row["closed_at"],
        archived_at=row["archived_at"],
    )


def _owned_conversation(
    conn: Connection,
    *,
    conversation_id: uuid.UUID,
    user_id: str,
    include_archived: bool = False,
    for_update: bool = False,
) -> RowMapping:
    """Return an owned conversation, hiding unknown and cross-owner rows alike."""
    statement = (
        select(conversation)
        .select_from(conversation.join(project, conversation.c.project_id == project.c.project_id))
        .where(conversation.c.id == conversation_id)
        .where(project.c.owner_user_id == user_id)
        .where(project.c.status == "active")
    )
    if not include_archived:
        statement = statement.where(conversation.c.status != "archived")
    if for_update:
        statement = statement.with_for_update()
    row = conn.execute(statement).mappings().one_or_none()
    if row is None:
        raise _not_found()
    return row


def _preview_snippet(value: str | None) -> str | None:
    """Bound a preview to one compact line without changing short content."""
    if value is None:
        return None
    normalized = " ".join(value.split())
    if len(normalized) <= _PREVIEW_MAX_CHARS:
        return normalized
    return f"{normalized[:_PREVIEW_MAX_CHARS - 1]}…"


def _latest_turn_preview(
    conn: Connection, row: RowMapping
) -> LatestTurnPreviewOut | None:
    """Read the latest durable turn from the table selected by conversation kind."""
    if row["kind"] == "chat":
        latest = conn.execute(
            select(chat_turn.c.user_message, chat_turn.c.answer, chat_turn.c.completed_at)
            .where(chat_turn.c.conversation_id == row["id"])
            .order_by(chat_turn.c.turn_index.desc())
            .limit(1)
        ).mappings().one_or_none()
        if latest is None:
            return None
        return LatestTurnPreviewOut(
            user_message=_preview_snippet(latest["user_message"]) or "",
            reply_snippet=_preview_snippet(latest["answer"]),
            at=latest["completed_at"],
        )
    latest = conn.execute(
        select(
            planning_transcript.c.user_message,
            planning_transcript.c.reply,
            planning_transcript.c.completed_at,
        )
        .where(planning_transcript.c.conversation_id == row["id"])
        .order_by(planning_transcript.c.turn_index.desc())
        .limit(1)
    ).mappings().one_or_none()
    if latest is None:
        return None
    return LatestTurnPreviewOut(
        user_message=_preview_snippet(latest["user_message"]) or "",
        reply_snippet=_preview_snippet(latest["reply"]),
        at=latest["completed_at"],
    )


def _chat_turn_out(row: RowMapping) -> ChatTurnOut:
    """Project one durable chat turn into the stable read contract."""
    payload = row["answer_payload"]
    payload = payload if isinstance(payload, dict) else {}
    claims = payload.get("claims", [])
    citations = payload.get("citations", [])
    return ChatTurnOut(
        id=row["id"],
        conversation_id=row["conversation_id"],
        turn_index=row["turn_index"],
        client_turn_id=row["client_turn_id"],
        user_message=row["user_message"],
        answer=row["answer"],
        status=cast(Literal["pending", "completed", "failed", "cancelled"], row["status"]),
        created_at=row["created_at"],
        completed_at=row["completed_at"],
        claims=claims if isinstance(claims, list) else [],
        citations=citations if isinstance(citations, list) else [],
        enrichment=(
            payload.get("enrichment") if isinstance(payload.get("enrichment"), dict) else None
        ),
        warning_not_evidence_checked=bool(payload.get("warning_not_evidence_checked", False)),
        handoff=payload.get("handoff") if payload.get("handoff") == "evidence_not_held" else None,
        stopped_before_evidence_check=bool(payload.get("stopped_before_evidence_check", False)),
    )


def _assert_entry_artefact(
    conn: Connection, *, project_id: uuid.UUID, entry_artefact_id: uuid.UUID
) -> None:
    """Ensure an entry-context artefact belongs to the target project."""
    exists = conn.execute(
        select(artefact.c.artefact_id)
        .where(artefact.c.artefact_id == entry_artefact_id)
        .where(artefact.c.project_id == project_id)
    ).scalar_one_or_none()
    if exists is None:
        raise _not_found()


@project_router.get("/{project_id}/conversations", response_model=Page[ConversationListItemOut])
def list_conversations(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
    kind: ConversationKind | None = None,
    status_filter: Annotated[
        ConversationStatus | None, Query(alias="status")
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
) -> Page[ConversationListItemOut]:
    """List one owned project's conversations, newest first, with turn previews."""
    owned_project(conn, project_id=project_id, user_id=user.user_id)
    where = [conversation.c.project_id == project_id]
    if kind is not None:
        where.append(conversation.c.kind == kind)
    if status_filter is None:
        where.append(conversation.c.status != "archived")
    else:
        where.append(conversation.c.status == status_filter)
    total = conn.execute(select(func.count()).select_from(conversation).where(*where)).scalar_one()
    rows = conn.execute(
        select(conversation)
        .where(*where)
        .order_by(conversation.c.created_at.desc(), conversation.c.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).mappings().all()
    return Page(
        data=[
            ConversationListItemOut(
                **_conversation_out(row).model_dump(),
                latest_turn_preview=_latest_turn_preview(conn, row),
            )
            for row in rows
        ],
        pagination=PageMeta(page=page, page_size=page_size, total_items=int(total)),
    )


@project_router.post(
    "/{project_id}/conversations",
    response_model=ConversationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    project_id: uuid.UUID,
    payload: ConversationCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> ConversationOut:
    """Create one active chat conversation with optional entry context."""
    owned_project(conn, project_id=project_id, user_id=user.user_id, for_update=True)
    if payload.entry_artefact_id is not None:
        _assert_entry_artefact(
            conn, project_id=project_id, entry_artefact_id=payload.entry_artefact_id
        )
    now = datetime.now(UTC)
    conversation_id = uuid.uuid4()
    conn.execute(
        conversation.insert().values(
            id=conversation_id,
            project_id=project_id,
            kind="chat",
            title="New chat",
            entry_artefact_id=payload.entry_artefact_id,
            status="active",
            created_at=now,
            closed_at=None,
            archived_at=None,
        )
    )
    row = conn.execute(
        select(conversation).where(conversation.c.id == conversation_id)
    ).mappings().one()
    return _conversation_out(row)


@router.get("/{conversation_id}", response_model=ConversationOut)
def get_conversation(
    conversation_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> ConversationOut:
    """Resolve an owned active or closed conversation deep link."""
    return _conversation_out(
        _owned_conversation(conn, conversation_id=conversation_id, user_id=user.user_id)
    )


@router.patch("/{conversation_id}", response_model=ConversationOut)
def update_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> ConversationOut:
    """Rename an owned chat and/or set or clear its entry-context artefact."""
    row = _owned_conversation(
        conn, conversation_id=conversation_id, user_id=user.user_id, for_update=True
    )
    if row["kind"] != "chat":
        raise HTTPException(status_code=422, detail="planning conversations cannot be renamed")
    changes = payload.model_dump(exclude_unset=True)
    entry_artefact_id = changes.get("entry_artefact_id")
    if entry_artefact_id is not None:
        _assert_entry_artefact(
            conn, project_id=row["project_id"], entry_artefact_id=entry_artefact_id
        )
    if changes:
        conn.execute(
            update(conversation).where(conversation.c.id == conversation_id).values(**changes)
        )
    refreshed = conn.execute(
        select(conversation).where(conversation.c.id == conversation_id)
    ).mappings().one()
    return _conversation_out(refreshed)


@router.post("/{conversation_id}/archive", response_model=ConversationOut)
def archive_conversation(
    conversation_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> ConversationOut:
    """Idempotently archive one owned chat conversation."""
    row = _owned_conversation(
        conn,
        conversation_id=conversation_id,
        user_id=user.user_id,
        include_archived=True,
        for_update=True,
    )
    if row["kind"] != "chat":
        raise HTTPException(status_code=422, detail="planning conversations cannot be archived")
    if row["status"] != "archived":
        conn.execute(
            update(conversation)
            .where(conversation.c.id == conversation_id)
            .values(status="archived", archived_at=datetime.now(UTC))
        )
    refreshed = conn.execute(
        select(conversation).where(conversation.c.id == conversation_id)
    ).mappings().one()
    return _conversation_out(refreshed)


@router.post("/{conversation_id}/unarchive", response_model=ConversationOut)
def unarchive_conversation(
    conversation_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> ConversationOut:
    """Idempotently restore an owned archived chat to active status."""
    row = _owned_conversation(
        conn,
        conversation_id=conversation_id,
        user_id=user.user_id,
        include_archived=True,
        for_update=True,
    )
    if row["kind"] != "chat":
        raise HTTPException(status_code=422, detail="planning conversations cannot be unarchived")
    if row["status"] == "archived":
        conn.execute(
            update(conversation)
            .where(conversation.c.id == conversation_id)
            .values(status="active", archived_at=None)
        )
    refreshed = conn.execute(
        select(conversation).where(conversation.c.id == conversation_id)
    ).mappings().one()
    return _conversation_out(refreshed)


@router.get("/{conversation_id}/turns", response_model=Page[ChatTurnOut])
def list_chat_turns(
    conversation_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
) -> Page[ChatTurnOut]:
    """Return an active owned chat's durable turns in ascending turn order."""
    row = _owned_conversation(conn, conversation_id=conversation_id, user_id=user.user_id)
    if row["kind"] != "chat" or row["status"] != "active":
        raise _not_found()
    total = conn.execute(
        select(func.count())
        .select_from(chat_turn)
        .where(chat_turn.c.conversation_id == conversation_id)
    ).scalar_one()
    rows = conn.execute(
        select(chat_turn)
        .where(chat_turn.c.conversation_id == conversation_id)
        .order_by(chat_turn.c.turn_index.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).mappings().all()
    return Page(
        data=[_chat_turn_out(turn) for turn in rows],
        pagination=PageMeta(page=page, page_size=page_size, total_items=int(total)),
    )


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
        enrichment=payload.get("enrichment")
        if isinstance(payload.get("enrichment"), dict)
        else None,
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
    judge_backend: Annotated[GroundingJudgeBackend, Depends(get_grounding_judge_backend)],
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
                payload = result.answer_payload or {}
                enrichment = payload.get("enrichment")
                if (
                    not result.replayed
                    and isinstance(enrichment, dict)
                    and enrichment.get("status") == "pending"
                ):
                    threading.Thread(
                        target=enrich_chat_turn,
                        kwargs={
                            "engine": engine,
                            "turn_id": result.id,
                            "judge_backend": judge_backend,
                            "langfuse_client": tracing.get_langfuse(),
                        },
                        name=f"policy-atlas-chat-enrichment-{result.id}",
                        daemon=True,
                    ).start()
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
