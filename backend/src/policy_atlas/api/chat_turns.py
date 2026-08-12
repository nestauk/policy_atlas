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
from policy_atlas.core.usage import usage_metadata
from policy_atlas.evidence_base.extract.quote_verify import (
    BasisText,
    build_basis,
    locate_unique_span,
)
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


class ChatTurnCancelled(Exception):
    """Internal control signal for an explicitly cancelled chat turn."""


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


def apply_appraisal_labels(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map each citation's persisted ``appraisal_score`` to a read-time label.

    ``evidence_base.assess.appraise`` pins labels as read-time copy, never
    persisted (``SCORE_LABELS`` — "a stored label could drift from its
    score"). A chat citation therefore persists the numeric
    ``appraisal_score`` at answer time (like the judge verdicts, it is the
    appraisal AT ANSWER TIME — a later re-appraisal does not rewrite an old
    answer's chip) and this function derives ``appraisal_label`` from it
    fresh on every read, at the router/read-model serialization boundary —
    never baked into the durable ``answer_payload`` (task 029 delta-review).

    Args:
        citations: A turn's citation dicts, as persisted (or freshly
            resolved). Mutated copies are returned; the input is untouched.

    Returns:
        The same citations with ``appraisal_label`` set from
        ``appraisal_score`` (via ``SCORE_LABELS``) wherever a score is
        present and known; ``appraisal_score`` itself is not re-exposed —
        the frontend contract has only ever carried the label.
    """
    from policy_atlas.evidence_base.assess.appraise import SCORE_LABELS

    labelled: list[dict[str, Any]] = []
    for citation in citations:
        if not isinstance(citation, dict):
            labelled.append(citation)
            continue
        score = citation.get("appraisal_score")
        if score is None:
            labelled.append(citation)
            continue
        merged = dict(citation)
        merged.pop("appraisal_score", None)
        label = SCORE_LABELS.get(score)
        if label is not None:
            merged["appraisal_label"] = label
        labelled.append(merged)
    return labelled


def _snapped_chunk_quote(basis: BasisText, quote: str) -> tuple[str, bool] | None:
    """Locate ``quote`` uniquely in a chunk's ``quote_verify`` basis.

    Reuses ``quote_verify.locate_unique_span`` (qv_v1) — the canonical
    overlap-aware, word-boundary-guarded, case-fold-round-tripped locator —
    instead of a third parallel matcher. Returns the verbatim raw source text
    of the located span and whether it differs from the model's emitted
    ``quote`` (i.e. only a normalised, not exact, match). An absent or
    ambiguous quote returns ``None`` — the read-time locator
    (``repository.chunk_quote_context_out``) and its own fallback still
    handle those honestly at hover/click time.
    """
    if not quote:
        return None
    span = locate_unique_span(basis, quote)
    if span is None:
        return None
    start, end = span
    raw_text = basis.raw_text[start:end]
    return raw_text, raw_text != quote


def _resolve_citation_sources(
    engine: Engine, citations: list[dict[str, Any]], *, project_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Attach source display facts to floored citations (title + document id).

    References must read as documents, not durable ids (owner live check,
    2026-08-11). Bibliographic authority is the ENVELOPE snapshot per the
    artefact read model's rule; the pss id joins to the sources/dossier
    surface. Resolution failure leaves the honest id-only citation.

    Both branches are project-scoped (security review, 2026-08-11): a chunk's
    source_snapshot is content-keyed and can be shared by another project's
    project_source_snapshot, and a finding_id alone carries no project
    boundary, so either lookup left unscoped could resolve another project's
    document onto this project's citation (see
    ``repository.chunk_quote_context_out`` for the same chunk-side filter).

    Also resolves the cited document's ``appraisal_score`` + ``evidence_type``
    (mirroring ``repository.artefact_out``'s CitationOut resolution exactly —
    latest appraisal/classification row per project_source_snapshot_id,
    project-scoped, no narrower join). The score, not the label, is what
    persists here (``evidence_base.assess.appraise``'s read-time-copy pin —
    ``apply_appraisal_labels`` derives ``appraisal_label`` fresh on every read
    instead). At persist time this also snaps a chunk citation's
    model-emitted ``quote`` to the verbatim source text when ``quote_verify``
    locates it uniquely in that chunk's content (marking ``quote_snapped:
    true`` only when the text actually changed).
    """
    from policy_atlas.api.readmodels.repository import latest_row_by_id
    from policy_atlas.core.schema import chunk as chunk_table
    from policy_atlas.core.schema import (
        implementation_context_finding,
        intervention_outcome_finding,
        project_source_snapshot,
        pss_owns_snapshot,
        source_appraisal_result,
        source_classification_result,
        source_extraction_record,
        source_snapshot,
    )

    def _uuids(kind: str) -> set[uuid.UUID]:
        values: set[uuid.UUID] = set()
        for citation in citations:
            if citation.get("kind") != kind:
                continue
            try:
                values.add(uuid.UUID(str(citation.get("id"))))
            except ValueError:
                continue
        return values

    chunk_ids, finding_ids = _uuids("chunk"), _uuids("finding")
    facts: dict[str, dict[str, Any]] = {}
    chunk_contents: dict[str, str] = {}
    appraisal: dict[uuid.UUID, Any] = {}
    classification: dict[uuid.UUID, Any] = {}
    with engine.connect() as conn:
        if chunk_ids:
            for row in conn.execute(
                select(
                    chunk_table.c.chunk_id,
                    chunk_table.c.content,
                    project_source_snapshot.c.project_source_snapshot_id,
                    source_snapshot.c.metadata,
                    source_snapshot.c.source_locator,
                )
                .select_from(
                    chunk_table.join(
                        project_source_snapshot,
                        pss_owns_snapshot(chunk_table.c.source_snapshot_id),
                    ).join(
                        source_snapshot,
                        source_snapshot.c.source_snapshot_id
                        == project_source_snapshot.c.source_snapshot_id,
                    )
                )
                .where(chunk_table.c.chunk_id.in_(chunk_ids))
                .where(project_source_snapshot.c.project_id == project_id)
            ):
                meta = row.metadata if isinstance(row.metadata, dict) else {}
                title = meta.get("title") or row.source_locator
                facts[str(row.chunk_id)] = {
                    "source_title": title,
                    "source_id": str(row.project_source_snapshot_id),
                }
                chunk_contents[str(row.chunk_id)] = row.content
        if finding_ids:
            for table in (intervention_outcome_finding, implementation_context_finding):
                for row in conn.execute(
                    select(
                        table.c.finding_id,
                        project_source_snapshot.c.project_source_snapshot_id,
                        source_snapshot.c.metadata,
                        source_snapshot.c.source_locator,
                    )
                    .select_from(
                        table.join(
                            source_extraction_record,
                            table.c.extraction_record_id
                            == source_extraction_record.c.extraction_record_id,
                        )
                        .join(
                            project_source_snapshot,
                            project_source_snapshot.c.project_source_snapshot_id
                            == source_extraction_record.c.project_source_snapshot_id,
                        )
                        .join(
                            source_snapshot,
                            source_snapshot.c.source_snapshot_id
                            == project_source_snapshot.c.source_snapshot_id,
                        )
                    )
                    .where(table.c.finding_id.in_(finding_ids))
                    .where(table.c.project_id == project_id)
                ):
                    meta = row.metadata if isinstance(row.metadata, dict) else {}
                    facts[str(row.finding_id)] = {
                        "source_title": meta.get("title") or row.source_locator,
                        "source_id": str(row.project_source_snapshot_id),
                    }
        resolved_pss_ids = {uuid.UUID(fact["source_id"]) for fact in facts.values()}
        if resolved_pss_ids:
            # Same join/effective-row rules as repository.artefact_out's
            # CitationOut resolution: project-scoped, latest row per
            # project_source_snapshot_id wins. Narrowed to the pss ids already
            # resolved above (task 029 delta-review) — cost proportional to
            # citations, not to the whole project's appraisal/classification set.
            appraisal = latest_row_by_id(
                conn.execute(
                    select(
                        source_appraisal_result.c.project_source_snapshot_id,
                        source_appraisal_result.c.quality_score,
                        source_appraisal_result.c.appraised_at,
                    )
                    .where(source_appraisal_result.c.project_id == project_id)
                    .where(
                        source_appraisal_result.c.project_source_snapshot_id.in_(
                            resolved_pss_ids
                        )
                    )
                ).all(),
                "project_source_snapshot_id",
                "appraised_at",
            )
            classification = latest_row_by_id(
                conn.execute(
                    select(
                        source_classification_result.c.project_source_snapshot_id,
                        source_classification_result.c.primary_evidence_type,
                        source_classification_result.c.classified_at,
                    )
                    .where(source_classification_result.c.project_id == project_id)
                    .where(
                        source_classification_result.c.project_source_snapshot_id.in_(
                            resolved_pss_ids
                        )
                    )
                ).all(),
                "project_source_snapshot_id",
                "classified_at",
            )

    basis_cache: dict[str, BasisText] = {}
    resolved: list[dict[str, Any]] = []
    for citation in citations:
        key = str(citation.get("id"))
        source_facts = facts.get(key, {})
        merged = {**citation, **source_facts}

        source_id = source_facts.get("source_id")
        if source_id is not None:
            pss_id = uuid.UUID(source_id)
            appraisal_row = appraisal.get(pss_id)
            if appraisal_row is not None:
                # The score, not the label, persists (evidence_base.assess.appraise's
                # read-time-copy pin) — apply_appraisal_labels derives the label
                # fresh on every read from this score.
                merged["appraisal_score"] = appraisal_row.quality_score
            classification_row = classification.get(pss_id)
            if classification_row is not None:
                merged["evidence_type"] = classification_row.primary_evidence_type

        quote = citation.get("quote")
        if citation.get("kind") == "chunk" and quote:
            content = chunk_contents.get(key)
            if content is not None:
                basis = basis_cache.get(key)
                if basis is None:
                    basis = build_basis([(key, content)])
                    basis_cache[key] = basis
                snap = _snapped_chunk_quote(basis, cast(str, quote))
                if snap is not None:
                    raw_text, changed = snap
                    merged["quote"] = raw_text
                    if changed:
                        merged["quote_snapped"] = True
        resolved.append(merged)
    return resolved


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
    reserved_turn_id: uuid.UUID | None = None,
) -> ChatTurnResult | uuid.UUID:
    """Reserve one chat row or replay a completed row under the project lock.

    Args:
        conn: Open connection already inside the caller's transaction.
        project_id: Owner-scoped project id.
        conversation_id: Active chat conversation id.
        user_id: Authenticated project owner.
        message: Current user question.
        client_turn_id: Client-minted idempotency key.
        reserved_turn_id: The turn id the caller itself already reserved for
            this client_turn_id, if any (the streaming worker re-entering its
            own reservation). A live ``pending`` row under this
            client_turn_id is only retried in place when it matches; any
            other caller racing the same client_turn_id gets a conflict
            instead of resetting — and possibly double-running — a turn that
            is not its own (security review, 2026-08-11).
    """
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
        if existing["status"] == "pending" and existing["id"] != reserved_turn_id:
            # A live pending row under this client_turn_id belongs to someone
            # else's in-flight attempt (or a distinct racing call of our own) —
            # only the caller that reserved this exact row may proceed past
            # here (single-flight is the DB row, gated inside this lock).
            raise ApiConflict("chat_turn_in_progress", "a chat turn is already running")
        # A terminal failed/cancelled row, or the caller's own reserved
        # pending row, is retried in place. The streaming router registers
        # the live cancel handle before this second pass, so a newly
        # received explicit stop cannot be mistaken for a retry here.
        conn.execute(
            update(chat_turn)
            .where(chat_turn.c.id == existing["id"])
            .values(
                answer=None,
                answer_payload=None,
                capability_run_id=None,
                status="pending",
                completed_at=None,
            )
        )
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
    on_delta: Callable[[str], None] | None = None,
) -> Any:
    """Invoke one backend turn with the plan-pinned output ceiling."""
    return backend.chat_turn(
        messages,
        transcript,
        force_emit=force_emit,
        max_output_tokens=CHAT_MAX_OUTPUT_TOKENS,
        on_delta=on_delta,
    )


def _cancelled_result(
    engine: Engine,
    *,
    turn_id: uuid.UUID,
    partial_answer: str,
) -> ChatTurnResult:
    """Persist an explicit stop while keeping its unverified streamed prose."""
    payload = {
        "claims": [],
        "citations": [],
        "warning_not_evidence_checked": False,
        "handoff": None,
        "stopped_before_evidence_check": True,
    }
    with engine.begin() as conn:
        conn.execute(
            update(chat_turn)
            .where(chat_turn.c.id == turn_id)
            .where(chat_turn.c.status.in_(("pending", "cancelled")))
            .values(
                answer=partial_answer,
                answer_payload=payload,
                status="cancelled",
                completed_at=_now(),
            )
        )
        row = conn.execute(select(chat_turn).where(chat_turn.c.id == turn_id)).mappings().one()
    return _row_result(row, replayed=False)


def _turn_was_cancelled(engine: Engine, *, turn_id: uuid.UUID) -> bool:
    """Return whether a racing no-live-generator cancel already changed the row."""
    with engine.connect() as conn:
        status = conn.execute(
            select(chat_turn.c.status).where(chat_turn.c.id == turn_id)
        ).scalar_one()
    return bool(status == "cancelled")


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
    cancel_event: threading.Event | None = None,
    reserved_turn_id: uuid.UUID | None = None,
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
        on_delta: Optional provider-neutral final-prose callback.
        cancel_event: Explicit stream-cancel signal, if this is a live turn.
        reserved_turn_id: The turn id the caller already reserved for this
            client_turn_id, if any (the streaming route's worker re-entering
            its own reservation) — see ``_phase_one_turn``.

    Returns:
        The completed or replayed durable chat turn.
    """
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
                reserved_turn_id=reserved_turn_id,
            )
        if isinstance(phase_one, ChatTurnResult):
            return phase_one
        turn_id = phase_one
        streamed_parts: list[str] = []

        def _check_cancelled(*, check_row: bool = True) -> None:
            if cancel_event is not None and cancel_event.is_set():
                raise ChatTurnCancelled()
            # The row check covers the no-live-generator cancel race; it runs
            # at turn/tool boundaries only — never per streamed delta.
            if check_row and _turn_was_cancelled(engine, turn_id=turn_id):
                raise ChatTurnCancelled()

        def _emit_delta(text: str) -> None:
            _check_cancelled(check_row=False)
            if text:
                streamed_parts.append(text)
                if on_delta is not None:
                    on_delta(text)

        try:
            _check_cancelled()
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

            call_count = 0

            def turn_fn(transcript: list[ToolExchange], *, force_emit: bool) -> Any:
                nonlocal call_count
                _check_cancelled()
                call_count += 1

                def _call() -> Any:
                    # The delta sink rides every turn: the backend only streams
                    # when it emits, and emission can happen on any turn, not
                    # just the turn-cap-forced one.
                    return _chat_backend_turn(
                        chat_backend,
                        messages,
                        transcript,
                        force_emit=force_emit,
                        on_delta=_emit_delta,
                    )

                def _record(span: Any, result: tuple[dict[str, Any], Any]) -> None:
                    response, usage = result
                    span.update(
                        input={
                            "messages": messages,
                            "tool_exchanges": len(transcript),
                            "force_emit": force_emit,
                        },
                        output=response,
                        metadata={
                            "prompt_version": CHAT_PROMPT_VERSION,
                            **usage_metadata(usage),
                        },
                        model=CHAT_MODEL,
                    )

                # The streaming adapter bypasses the instrumented-client path,
                # so the generation observation is opened here — without it the
                # turn's trace holds no model I/O at all (review stack,
                # live-trace lane).
                response, usage = tracing.traced_call(
                    langfuse_client,
                    name=f"chat:call{call_count}",
                    as_type="generation",
                    call=_call,
                    update=_record,
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

            def _on_tool_start(name: str, _arguments: dict[str, Any]) -> None:
                """Stop before a read or report its user-facing activity."""
                _check_cancelled()
                if on_progress is not None:
                    on_progress(labels[name])

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
                    on_tool_start=_on_tool_start,
                )
                _check_cancelled()
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
                # Trace-level I/O makes the turn legible from the trace *list*
                # (the persisted floored answer, not the raw emission — the
                # row and the trace must tell the same story).
                if root_span is not None:
                    root_span.update(
                        input={"question": message},
                        output={
                            "answer": floored.prose,
                            "citations": len(floored.citations),
                        },
                        metadata={"prompt_version": CHAT_PROMPT_VERSION, "model": CHAT_MODEL},
                    )
                trace_id = _trace_id(root_span)
            payload = {
                "claims": floored.claims,
                "citations": _resolve_citation_sources(
                    engine, floored.citations, project_id=project_id
                ),
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
                "stopped_before_evidence_check": False,
                "enrichment": {"status": "pending" if floored.citations else "not_applicable"},
            }
            if not streamed_parts:
                _emit_delta(floored.prose)
            with engine.begin() as conn:
                completed = conn.execute(
                    update(chat_turn)
                    .where(chat_turn.c.id == turn_id)
                    .where(chat_turn.c.status == "pending")
                    .values(
                        answer=floored.prose,
                        answer_payload=payload,
                        capability_run_id=scope.capability_run_id,
                        status="completed",
                        completed_at=_now(),
                    )
                )
                if completed.rowcount != 1:
                    row = (
                        conn.execute(select(chat_turn).where(chat_turn.c.id == turn_id))
                        .mappings()
                        .one()
                    )
                    if row["status"] == "cancelled":
                        # A durable cross-process cancel landed after our last
                        # in-process check but before this commit. Its partial
                        # is already persisted (the cancel path wrote it) — the
                        # terminal state stays cancelled, never overwritten to
                        # completed (security review, 2026-08-11).
                        return _row_result(row, replayed=False)
                    raise RuntimeError("chat turn was not open at terminal commit")
                row = (
                    conn.execute(select(chat_turn).where(chat_turn.c.id == turn_id))
                    .mappings()
                    .one()
                )
            return _row_result(row, replayed=False)
        except ChatTurnCancelled:
            return _cancelled_result(
                engine, turn_id=turn_id, partial_answer="".join(streamed_parts)
            )
        except Exception:
            log.exception(
                "chat_turn_failed", project_id=str(project_id), conversation_id=str(conversation_id)
            )
            with engine.begin() as conn:
                # Narrowed to "pending" only (security review, 2026-08-11): a
                # late failure must not overwrite a durable cancel that landed
                # first; an already-failed row leaves this a no-op.
                conn.execute(
                    update(chat_turn)
                    .where(chat_turn.c.id == turn_id)
                    .where(chat_turn.c.status == "pending")
                    .values(status="failed", completed_at=_now())
                )
            raise
    finally:
        lock.release()
