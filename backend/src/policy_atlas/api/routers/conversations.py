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

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, false, func, or_, select, update
from sqlalchemy.engine import Connection, Engine, RowMapping

from policy_atlas.api.app import ApiCapacity, ApiConflict
from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.chat_enrichment import enrich_chat_turn
from policy_atlas.api.chat_turns import (
    ChatTurnResult,
    _phase_one_turn,
    apply_appraisal_labels,
    run_chat_turn,
)
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
from policy_atlas.api.routers._access import (
    accessible_project,
    admin_read_leg,
    chat_mutable_project,
    own_chat_leg,
    own_conversation_leg,
    own_estate,
    trace_admin_read,
)
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

log = structlog.get_logger()

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

#: Label :func:`_graded_conversation`'s read path carries beside the row: did
#: the creator/owner grade match on its own? ``False`` means the admin leg is
#: what resolved the row, which is what the trace records. Mirrors
#: ``_access._OWN_LEG`` for the project/portfolio helpers; kept as its own
#: constant because the predicate it labels is this router's, not the shared
#: estate one.
_OWN_GRADE = "own_grade_matched"


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


def _graded_conversation(
    conn: Connection,
    *,
    conversation_id: uuid.UUID,
    user_id: str,
    write: bool,
    include_archived: bool = False,
    for_update: bool = False,
) -> RowMapping:
    """Resolve one conversation under its kind-specific accessibility predicate.

    A **chat** conversation is visible only to the colleague who created it,
    or — for the legacy pre-033 rows that carry no ``created_by`` — the
    project owner (the same NULL disjunct :func:`list_conversations` applies
    to the listing). A **planning** conversation stays owner-only this phase
    (contract § 4); colleague-authored planning turns are a later slice.

    Not accessible is always a **404**, never a 403: a colleague who did not
    create a chat must not learn the row exists at all — this is the guard
    that closes the ``GET /{id}`` / ``GET /{id}/turns`` deep-link leak.

    **The two grades diverge here, and only here.** Contract § 4 gives an
    administrator ``GET /{id}`` and ``GET /{id}/turns`` — traced — and gives
    them nothing else on this router. So the admin leg is disjoined into the
    predicate on the **read** path and is absent from the write path, where
    the creator/owner predicate stands exactly as it did: an administrator
    who is not the creator gets this router's ordinary 404 on ``PATCH``,
    ``archive`` and ``unarchive``, and that is deliberate — the router has no
    403 semantic to spend, and refusing a write is not a reason to confirm the
    row exists.

    Note what the admin leg *replaces*: the whole conjunction, ``own_estate``
    on the project included. That guard is the colleague's revocation lever
    (de-enrolment kills their chat), and an administrator is not reached by
    it. The project's ``status == "active"`` filter and the archived-
    conversation filter are **not** replaced — they are not tenancy, and an
    administrator observes the same rows anyone else would.

    Leg detection is one query: the own-grade conjunction is selected as a
    boolean column beside the row, so a row that came back with it ``False``
    was reached by the admin leg, and :func:`trace_admin_read` records it —
    one line per row, nothing for a caller who was entitled anyway.

    Args:
        conn: Open database connection.
        conversation_id: Requested conversation identity.
        user_id: The caller's token subject.
        write: Whether the caller needs the write grade. ``False`` adds the
            admin read leg; ``True`` is the creator/owner predicate alone.
            There is still no readable-but-not-writable 403 on this router —
            the divergence is which rows resolve, not which code is returned.
        include_archived: Whether an archived conversation can be observed.
        for_update: Take ``SELECT … FOR UPDATE`` on the row.

    Returns:
        The resolved conversation row.

    Raises:
        HTTPException: 404 when the row is missing, archived (unless
            ``include_archived``), or not accessible under its kind's
            predicate.
    """
    own_grade = and_(
        # The project must still be reachable by the caller: de-enrolment is a
        # revocation event (contract § 5), so a creator's chat on a project
        # they can no longer read dies with the org leg. own_estate, not the
        # full read grade — the admin read arrives as its own leg below.
        own_estate(project, user_id),
        or_(
            own_chat_leg(user_id),
            and_(
                conversation.c.kind == "planning",
                project.c.owner_user_id == user_id,
            ),
        ),
    )
    statement = (
        select(conversation)
        .select_from(conversation.join(project, conversation.c.project_id == project.c.project_id))
        .where(conversation.c.id == conversation_id)
        .where(project.c.status == "active")
    )
    if write:
        statement = statement.where(own_grade)
    else:
        # COALESCEd for the same reason `_access._own_leg_column` is: every
        # disjunct of `own_grade` compares a **nullable** column to the
        # caller's subject (`project.owner_user_id`, `conversation.created_by`),
        # so on a project with no owner the predicate is SQL NULL rather than
        # FALSE — and `not row[_OWN_GRADE]` would then be deciding the trace on
        # `not None`. NULL and FALSE mean one thing here ("no grade the caller
        # held without `is_admin`"), so the column says so.
        statement = statement.add_columns(
            func.coalesce(own_grade, false()).label(_OWN_GRADE)
        ).where(or_(own_grade, admin_read_leg(user_id)))
    if not include_archived:
        statement = statement.where(conversation.c.status != "archived")
    if for_update:
        # of=conversation: the statement joins project, and a bare FOR UPDATE
        # would lock the owner's project row on a creator's archive path —
        # the exact lock contract § 4 forbids on colleague chat paths.
        statement = statement.with_for_update(of=conversation)
    row = conn.execute(statement).mappings().one_or_none()
    if row is None:
        raise _not_found()
    if not write and not row[_OWN_GRADE]:
        trace_admin_read(
            kind="conversation", row_id=str(row["id"]), user_id=user_id
        )
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
        # Read-time label mapping (task 029 delta-review): the persisted
        # payload carries appraisal_score, never a label — apply_appraisal_labels
        # derives appraisal_label fresh on every read.
        citations=apply_appraisal_labels(citations) if isinstance(citations, list) else [],
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
    """List one readable project's conversations the caller created, newest first.

    Read-graded on the project (owner or same-org colleague may open the
    library), but the conversation rows themselves are narrowed further: a
    colleague sees only the chats *they* created, never the owner's or
    another colleague's. The owner keeps seeing every legacy pre-033 row
    (``created_by IS NULL``) as their own, in addition to rows their own
    subject created since.

    The filter is :func:`own_conversation_leg`, **not** its chat-narrowed
    sibling: this library lists both kinds, and the owner must keep seeing
    their project's planning conversation here. A colleague never matches a
    planning row anyway — planning conversations are minted by the runtime
    and record no ``created_by``, so only the project owner reaches them
    through the legacy disjunct.
    """
    accessible_project(conn, project_id=project_id, user_id=user.user_id, write=False)
    where = [
        conversation.c.project_id == project_id,
        own_conversation_leg(user.user_id),
    ]
    if kind is not None:
        where.append(conversation.c.kind == kind)
    if status_filter is None:
        where.append(conversation.c.status != "archived")
    else:
        where.append(conversation.c.status == status_filter)
    joined = conversation.join(project, conversation.c.project_id == project.c.project_id)
    total = conn.execute(
        select(func.count()).select_from(joined).where(*where)
    ).scalar_one()
    rows = conn.execute(
        select(conversation)
        .select_from(joined)
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
    """Create one active chat conversation with optional entry context.

    The first of the three mutations owner call (b) grants a same-org
    colleague (contract § 4). The grade is :func:`chat_mutable_project` — the
    owner or a colleague who can read the project, and never an admin.

    **This route can only ever mint a chat**, for anybody: ``kind`` is not a
    field on ``ConversationCreate`` (which forbids extras), it is written as
    the literal ``"chat"`` below, and planning conversations are minted
    exclusively by ``runtime.conversation_lifecycle`` under ``planning.py``'s
    owner-graded project lock. So "a planning conversation can only ever be
    created by the project owner" needs no branch here to hold — the shape of
    the request body is what enforces it, and a body carrying ``kind`` is
    rejected 422 before this function runs.

    **No project-row lock** (contract § 4). The lock this route used to take
    protected nothing a chat insert needs: the only uniqueness constraint on
    ``conversation`` is the partial index over ``kind = 'planning' AND status
    = 'active'``, which a chat row cannot collide with, and the insert itself
    carries a freshly minted primary key. Kept, it would have let any
    colleague block the owner's rename, archive and run-start.
    """
    chat_mutable_project(conn, project_id=project_id, user_id=user.user_id)
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
            created_by=user.user_id,
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
    """Resolve an active or closed conversation deep link under its grade."""
    return _conversation_out(
        _graded_conversation(
            conn, conversation_id=conversation_id, user_id=user.user_id, write=False
        )
    )


@router.patch("/{conversation_id}", response_model=ConversationOut)
def update_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> ConversationOut:
    """Rename an owned chat and/or set or clear its entry-context artefact."""
    row = _graded_conversation(
        conn,
        conversation_id=conversation_id,
        user_id=user.user_id,
        write=True,
        for_update=True,
    )
    if row["kind"] != "chat":
        raise HTTPException(status_code=422, detail="planning conversations cannot be renamed")
    changes = payload.model_dump(exclude_unset=True)
    if "title" in changes and changes["title"] is None:
        # Unlike entry_artefact_id, title has no clearable meaning — a chat's
        # title is only ever replaced, never cleared (rev 3 contract).
        raise HTTPException(status_code=422, detail="title cannot be cleared")
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
    row = _graded_conversation(
        conn,
        conversation_id=conversation_id,
        user_id=user.user_id,
        write=True,
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
    row = _graded_conversation(
        conn,
        conversation_id=conversation_id,
        user_id=user.user_id,
        write=True,
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
    row = _graded_conversation(
        conn, conversation_id=conversation_id, user_id=user.user_id, write=False
    )
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
            # a live stop handle, so a saturated registry fails closed by
            # raising inside the caller's still-open reservation transaction —
            # rolling the pending row back with it — instead of weakening
            # explicit cancellation.
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
        # Read-time label mapping (task 029 delta-review): see _chat_turn_out.
        citations=apply_appraisal_labels(citations) if isinstance(citations, list) else [],
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
    """Reserve a chat turn and stream its provider-neutral NDJSON lifecycle.

    The second of the three colleague mutations (contract § 4): post a turn to
    **your own** conversation. Two conditions, both resolved in the one
    statement below, both 404 on failure:

    - :func:`own_chat_leg` — the conversation is a chat the caller created,
      or a legacy pre-033 chat on a project they own. An owner cannot post
      into a colleague's chat and a colleague cannot post into the owner's.
    - :func:`own_estate` on the project — the caller must still reach the
      project as its owner or as a same-org colleague. This is the leg that
      **dies on de-enrolment**: clearing a colleague's ``org_id`` takes their
      turn POST to 404 on the next request, even though they still match
      ``created_by``. Deliberately :func:`own_estate` rather than the full
      read grade, so phase 8's admin leg never reaches this mutation.

    No lock is taken here. The reservation's lock lives one layer down, on the
    **conversation** row (``chat_turns._phase_one_turn``) — never on the
    owner's project row.
    """
    # Reservation happens before response headers. All authorization,
    # eligibility, idempotency, capacity and validation errors therefore use
    # ErrorEnvelope.
    with engine.begin() as conn:
        row = (
            conn.execute(
                select(conversation.c.project_id)
                .select_from(
                    conversation.join(project, conversation.c.project_id == project.c.project_id)
                )
                .where(conversation.c.id == conversation_id)
                .where(project.c.status == "active")
                .where(own_chat_leg(user.user_id))
                .where(own_estate(project, user.user_id))
            )
            .scalar_one_or_none()
        )
        if row is None:
            raise HTTPException(status_code=404, detail="resource not found")
        project_id = row
        # The pending-row pre-check that used to live here read before the
        # project row lock's serialization point (TOCTOU) and duplicated a
        # check `_phase_one_turn` already makes correctly inside that lock —
        # dropped in favour of the single locked-and-swept check (security
        # review, 2026-08-11).
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
        cancel_event: threading.Event | None = None
        if not isinstance(phase_one, ChatTurnResult):
            # Registered inside the still-open reservation transaction: a
            # saturated cancel registry raises here and rolls the pending row
            # back with it, instead of leaving an orphaned reservation for the
            # TTL to expire (security review, 2026-08-11).
            cancel_event = _register_cancel(phase_one)

    if isinstance(phase_one, ChatTurnResult):
        async def replay() -> AsyncIterator[bytes]:
            yield _line(CompletedEvent(turn=_turn_out(phase_one)))

        return StreamingResponse(replay(), media_type="application/x-ndjson")

    turn_id = phase_one
    events: queue.Queue[Any] = queue.Queue()

    def worker() -> None:
        """Complete persistence independently of a consumer disconnect."""
        completed_result: ChatTurnResult | None = None
        try:
            # Opened inside the worker thread: contextvars do not cross a
            # thread start. The session scope inside run_chat_turn nests under
            # this user scope.
            with tracing.trace_scope(user_id=user.user_id):
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
                    reserved_turn_id=turn_id,
                )
            if result.status == "cancelled":
                events.put(CancelledEvent(turn=_turn_out(result)))
            else:
                events.put(CompletedEvent(turn=_turn_out(result)))
                completed_result = result
        except Exception as exc:
            # run_chat_turn can raise before it ever opens its own try block
            # (e.g. a run_active conflict on re-entering this reservation, or
            # the non-blocking conversation lock) — that path never touches
            # the row, so CAS it closed ourselves. Guarded on our own turn_id
            # and "pending" so a normal post-try failure (which already
            # marked the row failed) is left alone (code review, 2026-08-11).
            code = exc.code if isinstance(exc, (ApiConflict, ApiCapacity)) else "chat_turn_failed"
            with engine.begin() as conn:
                conn.execute(
                    update(chat_turn)
                    .where(chat_turn.c.id == turn_id)
                    .where(chat_turn.c.status == "pending")
                    .values(
                        status="failed",
                        completed_at=datetime.now(UTC),
                        answer_payload={"error_code": code},
                    )
                )
            events.put(
                FailedEvent(
                    error=FailedEventError(code=code, message="chat turn failed"),
                    turn_id=turn_id,
                )
            )
        finally:
            _deregister_cancel(turn_id)
            events.put(None)

        # Kept outside the try/except/finally above (contract-verifier
        # finding, 2026-08-11): a thread-start failure here must only be
        # logged, never surface as a second terminal event after completed
        # has already been enqueued.
        if completed_result is not None:
            payload = completed_result.answer_payload or {}
            enrichment = payload.get("enrichment")
            if (
                not completed_result.replayed
                and isinstance(enrichment, dict)
                and enrichment.get("status") == "pending"
            ):
                enrichment_turn_id = completed_result.id

                def _enrich() -> None:
                    """Attach the judge's traces to the conversation session/user."""
                    with tracing.trace_scope(
                        session_id=conversation_id, user_id=user.user_id
                    ):
                        enrich_chat_turn(
                            engine=engine,
                            turn_id=enrichment_turn_id,
                            judge_backend=judge_backend,
                            langfuse_client=tracing.get_langfuse(),
                        )

                try:
                    threading.Thread(
                        target=_enrich,
                        name=f"policy-atlas-chat-enrichment-{completed_result.id}",
                        daemon=True,
                    ).start()
                except Exception:
                    log.exception(
                        "chat_enrichment_thread_start_failed", turn_id=str(completed_result.id)
                    )

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
    """Explicitly stop a pending chat turn, preserving any streamed partial.

    The third colleague mutation (contract § 4): cancel **your own** turn,
    resolved through the same two conditions as the turn POST —
    :func:`own_chat_leg` on the conversation and :func:`own_estate` on the
    project — so cancellation is isolated in both directions and dies with a
    colleague's org leg.

    One deliberate asymmetry with the POST: no ``project.status = 'active'``
    filter, which is the pre-033 behaviour preserved. Cancelling is a stop,
    not a start; refusing it on an archived project would strand a pending
    row for the TTL sweep with no way for its author to close it.

    No lock: the write below is already a compare-and-set guarded on
    ``status = 'pending'``.
    """
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
                .where(own_chat_leg(user.user_id))
                .where(own_estate(project, user.user_id))
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
