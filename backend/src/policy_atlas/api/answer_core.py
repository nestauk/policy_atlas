"""Read-only grounded-answer core shared by chat and the Task Agent.

One question, one pinned scope, one cited answer — and nothing durable. The
generation half of a chat turn (frame, readers, tool loop, citation floor,
citation-source resolution) lives here so a Task Agent turn taken while a
scoping walk is paused on its baseline gate can answer from the same
evidence, over that walk's pinned component runs, without inheriting the
chat's reservation, single-flight locks, ``chat_turn`` row or eligibility
fences. Those stay in ``api.chat_turns``: this module writes no rows and
takes no locks.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.chat_scope import ResolvedRunScope, build_chat_readers
from policy_atlas.core import tracing
from policy_atlas.core.embeddings import EmbeddingBackend
from policy_atlas.core.usage import usage_details, usage_metadata
from policy_atlas.evidence_search.extract.quote_verify import (
    BasisText,
    build_basis,
    locate_unique_span,
)
from policy_atlas.evidence_search.synthesis.synthesis_tools import (
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
    CHAT_MODEL,
    CHAT_PROMPT_VERSION,
    build_chat_messages,
)

#: User-facing activity label emitted before each read tool runs.
_TOOL_LABELS = {
    "search_chunks": "Searching the evidence…",
    "query_findings": "Reading findings…",
    "lookup": "Looking up sources…",
}


class CancelCheck(Protocol):
    """Caller-supplied stop signal, raising to abandon the answer.

    Called with no arguments at turn and tool boundaries, where a durable
    cross-process cancel may also be re-read, and with ``check_row=False``
    per streamed prose fragment, where only the in-process signal is cheap
    enough to consult.
    """

    def __call__(self, *, check_row: bool = True) -> None:
        """Raise the caller's cancellation signal if this answer should stop."""


class ToolsBuilder(Protocol):
    """The section-tool builder seam, defaulting to ``build_section_tools``."""

    def __call__(
        self,
        *,
        retriever: Any,
        findings_reader: Callable[[dict[str, Any]], dict[str, Any]] | None,
        lookup_reader: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
        """Return the read-only tool set for one answer."""


@dataclass(frozen=True)
class AnswerBackends:
    """The provider seams one grounded answer calls out through.

    Args:
        chat: Provider-neutral chat backend.
        embedding: Optional query embedding backend for retrieval.
        langfuse: Optional tracing client.
        tools_builder: Section-tool builder, injectable so a caller can bind
            its own tool set.
    """

    chat: ChatBackend
    embedding: EmbeddingBackend | None = None
    langfuse: Any = None
    tools_builder: ToolsBuilder = cast(ToolsBuilder, build_section_tools)


@dataclass(frozen=True)
class AnswerPayload:
    """The citation-bearing half of a grounded answer, before persistence.

    Field order is the durable ``chat_turn.answer_payload`` key order:
    ``as_payload`` is what the chat service persists, unchanged.

    Args:
        claims: Floored structured claims.
        citations: Floored citations with source facts resolved.
        warning_not_evidence_checked: Whether the floor could not verify.
        stripped: Visible audit records for rejected citations.
        evidence_not_held: Whether the answer declared no held evidence.
        handoff: The handoff hint derived from ``evidence_not_held``.
        tool_digest: Per-answer tool-call accounting.
        model_id: Generating model identity.
        prompt_version: Generating prompt version.
        trace_id: Tracing trace id, when tracing is enabled.
        stopped_before_evidence_check: Always false here — a stop never
            reaches this payload, it is written by the caller's cancel path.
        enrichment: Downstream enrichment status for the citations.
    """

    claims: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    warning_not_evidence_checked: bool
    stripped: list[dict[str, str]]
    evidence_not_held: bool
    handoff: str | None
    tool_digest: dict[str, Any]
    model_id: str
    prompt_version: str
    trace_id: str | None
    stopped_before_evidence_check: bool = False
    enrichment: dict[str, Any] = field(default_factory=dict)

    def as_payload(self) -> dict[str, Any]:
        """Return the durable JSON payload shape, key order included."""
        return {
            "claims": self.claims,
            "citations": self.citations,
            "warning_not_evidence_checked": self.warning_not_evidence_checked,
            "stripped": self.stripped,
            "evidence_not_held": self.evidence_not_held,
            "handoff": self.handoff,
            "tool_digest": self.tool_digest,
            "model_id": self.model_id,
            "prompt_version": self.prompt_version,
            "trace_id": self.trace_id,
            "stopped_before_evidence_check": self.stopped_before_evidence_check,
            "enrichment": self.enrichment,
        }


def apply_appraisal_labels(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map each citation's persisted ``appraisal_score`` to a read-time label.

    ``evidence_search.assess.appraise`` pins labels as read-time copy, never
    persisted (``SCORE_LABELS`` — "a stored label could drift from its
    score"). A citation therefore persists the numeric ``appraisal_score`` at
    answer time (like the judge verdicts, it is the appraisal AT ANSWER TIME
    — a later re-appraisal does not rewrite an old answer's chip) and this
    function derives ``appraisal_label`` from it fresh on every read, at the
    router/read-model serialization boundary — never baked into the durable
    ``answer_payload`` (task 029 delta-review).

    Args:
        citations: A turn's citation dicts, as persisted (or freshly
            resolved). Mutated copies are returned; the input is untouched.

    Returns:
        The same citations with ``appraisal_label`` set from
        ``appraisal_score`` (via ``SCORE_LABELS``) wherever a score is
        present and known; ``appraisal_score`` itself is not re-exposed —
        the frontend contract has only ever carried the label.
    """
    from policy_atlas.evidence_search.assess.appraise import SCORE_LABELS

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
    engine: Engine, citations: list[dict[str, Any]], *, task_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Attach source display facts to floored citations (title + document id).

    References must read as documents, not durable ids (owner live check,
    2026-08-11). Bibliographic authority is the ENVELOPE snapshot per the
    artefact read model's rule; the tss id joins to the sources/dossier
    surface. Resolution failure leaves the honest id-only citation.

    Both branches are task-scoped (security review, 2026-08-11): a chunk's
    source_snapshot is content-keyed and can be shared by another task's
    task_source_snapshot, and a finding_id alone carries no task
    boundary, so either lookup left unscoped could resolve another task's
    document onto this task's citation (see
    ``repository.chunk_quote_context_out`` for the same chunk-side filter).

    Also resolves the cited document's ``appraisal_score`` + ``evidence_type``
    (mirroring ``repository.artefact_out``'s CitationOut resolution exactly —
    latest appraisal/classification row per task_source_snapshot_id,
    task-scoped, no narrower join). The score, not the label, is what
    persists here (``evidence_search.assess.appraise``'s read-time-copy pin —
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
        source_appraisal_result,
        source_classification_result,
        source_extraction_record,
        source_snapshot,
        task_source_snapshot,
        tss_owns_snapshot,
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
                    task_source_snapshot.c.task_source_snapshot_id,
                    source_snapshot.c.metadata,
                    source_snapshot.c.source_locator,
                )
                .select_from(
                    chunk_table.join(
                        task_source_snapshot,
                        tss_owns_snapshot(chunk_table.c.source_snapshot_id),
                    ).join(
                        source_snapshot,
                        source_snapshot.c.source_snapshot_id
                        == task_source_snapshot.c.source_snapshot_id,
                    )
                )
                .where(chunk_table.c.chunk_id.in_(chunk_ids))
                .where(task_source_snapshot.c.task_id == task_id)
            ):
                meta = row.metadata if isinstance(row.metadata, dict) else {}
                title = meta.get("title") or row.source_locator
                facts[str(row.chunk_id)] = {
                    "source_title": title,
                    "source_id": str(row.task_source_snapshot_id),
                }
                chunk_contents[str(row.chunk_id)] = row.content
        if finding_ids:
            for table in (intervention_outcome_finding, implementation_context_finding):
                for row in conn.execute(
                    select(
                        table.c.finding_id,
                        task_source_snapshot.c.task_source_snapshot_id,
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
                            task_source_snapshot,
                            task_source_snapshot.c.task_source_snapshot_id
                            == source_extraction_record.c.task_source_snapshot_id,
                        )
                        .join(
                            source_snapshot,
                            source_snapshot.c.source_snapshot_id
                            == task_source_snapshot.c.source_snapshot_id,
                        )
                    )
                    .where(table.c.finding_id.in_(finding_ids))
                    .where(table.c.task_id == task_id)
                ):
                    meta = row.metadata if isinstance(row.metadata, dict) else {}
                    facts[str(row.finding_id)] = {
                        "source_title": meta.get("title") or row.source_locator,
                        "source_id": str(row.task_source_snapshot_id),
                    }
        resolved_tss_ids = {uuid.UUID(fact["source_id"]) for fact in facts.values()}
        if resolved_tss_ids:
            # Same join/effective-row rules as repository.artefact_out's
            # CitationOut resolution: task-scoped, latest row per
            # task_source_snapshot_id wins. Narrowed to the tss ids already
            # resolved above (task 029 delta-review) — cost proportional to
            # citations, not to the whole task's appraisal/classification set.
            appraisal = latest_row_by_id(
                conn.execute(
                    select(
                        source_appraisal_result.c.task_source_snapshot_id,
                        source_appraisal_result.c.quality_score,
                        source_appraisal_result.c.appraised_at,
                    )
                    .where(source_appraisal_result.c.task_id == task_id)
                    .where(
                        source_appraisal_result.c.task_source_snapshot_id.in_(
                            resolved_tss_ids
                        )
                    )
                ).all(),
                "task_source_snapshot_id",
                "appraised_at",
            )
            classification = latest_row_by_id(
                conn.execute(
                    select(
                        source_classification_result.c.task_source_snapshot_id,
                        source_classification_result.c.primary_evidence_type,
                        source_classification_result.c.classified_at,
                    )
                    .where(source_classification_result.c.task_id == task_id)
                    .where(
                        source_classification_result.c.task_source_snapshot_id.in_(
                            resolved_tss_ids
                        )
                    )
                ).all(),
                "task_source_snapshot_id",
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
            tss_id = uuid.UUID(source_id)
            appraisal_row = appraisal.get(tss_id)
            if appraisal_row is not None:
                # The score, not the label, persists (evidence_search.assess.appraise's
                # read-time-copy pin) — apply_appraisal_labels derives the label
                # fresh on every read from this score.
                merged["appraisal_score"] = appraisal_row.quality_score
            classification_row = classification.get(tss_id)
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
    """Extract ids of appraised chunks actually exposed by tool calls."""
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


def _trace_id(root_span: Any) -> str | None:
    """Read the SDK-exposed trace id without pretending one exists in no-op mode."""
    if root_span is None:
        return None
    value = getattr(root_span, "trace_id", None) or getattr(root_span, "id", None)
    return str(value) if value is not None else None


def answer_over_scope(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    scope: ResolvedRunScope,
    entry_artefact_id: uuid.UUID | None,
    window: list[tuple[str, str]],
    question: str,
    backends: AnswerBackends,
    trace_run_id: uuid.UUID,
    trace_session_id: uuid.UUID | None,
    conversation_id: uuid.UUID | None = None,
    on_delta: Callable[[str], None] | None = None,
    on_progress: Callable[[str], None] | None = None,
    check_cancelled: CancelCheck | None = None,
) -> tuple[str, AnswerPayload]:
    """Answer one question over a pinned run scope, writing nothing.

    Assembles the entry frame, binds the scope's read-only tools, runs the
    chat tool loop, floors the emitted citations to what the turn actually
    read, and resolves each survivor's source facts. No row is written and no
    lock is taken here: eligibility, reservation and persistence belong to
    the caller (``api.chat_turns.run_chat_turn`` for the chat route).

    Args:
        engine: Database engine; only short read connections are opened.
        task_id: Task owning every piece of evidence this answer may cite.
        scope: Component runs of the walk this answer is pinned to — the
            latest completed walk for chat, a paused walk for a Task Agent
            turn held at its baseline gate.
        entry_artefact_id: Optional task-local artefact used as entry context.
        window: Prior ``(user_message, answer)`` pairs in ascending order;
            trimmed to the prompt's memory ceiling here.
        question: The current question.
        backends: Chat, embedding and tracing seams, plus the tool builder.
        trace_run_id: Identity this answer is traced under (the caller's turn
            id) — it names a span, never a durable ``runs`` row.
        trace_session_id: The Langfuse session this trace joins (the chat
            route's conversation id; a Task Agent turn's task id), or ``None``.
        conversation_id: Optional owning conversation, recorded in trace
            metadata so one conversation stays filterable.
        on_delta: Optional provider-neutral final-prose callback. When the
            backend streams nothing, the floored prose is emitted once at the
            end, so a caller sees the whole answer either way.
        on_progress: Optional user-facing read-tool activity callback.
        check_cancelled: Optional stop signal consulted at turn and tool
            boundaries and per streamed fragment; it raises to abandon.

    Returns:
        The floored prose and its citation payload.

    Raises:
        RuntimeError: If the tool loop completes without an answer emission.
    """
    chat_backend = backends.chat

    def _stop(*, check_row: bool = True) -> None:
        if check_cancelled is not None:
            check_cancelled(check_row=check_row)

    emitted = False

    def _emit_delta(text: str) -> None:
        nonlocal emitted
        _stop(check_row=False)
        if text:
            emitted = True
            if on_delta is not None:
                on_delta(text)

    with engine.connect() as conn:
        frame = assemble_chat_frame(conn, task_id=task_id, entry_artefact_id=entry_artefact_id)
    retriever, findings_reader, lookup_reader = build_chat_readers(
        engine, scope, task_id, embedding_backend=backends.embedding
    )
    tools = backends.tools_builder(
        retriever=retriever,
        findings_reader=findings_reader,
        lookup_reader=lookup_reader,
    )
    messages = build_chat_messages(
        frame_text=frame.text,
        window=[(turn.user_message, turn.answer) for turn in window_turns(window)],
        question=question,
    )

    call_count = 0

    def turn_fn(transcript: list[ToolExchange], *, force_emit: bool) -> Any:
        nonlocal call_count
        _stop()
        call_count += 1

        def _call() -> Any:
            # The delta sink rides every turn: the backend only streams
            # when it emits, and emission can happen on any turn, not
            # just the turn-cap-forced one.
            return chat_backend.chat_turn(
                messages,
                transcript,
                force_emit=force_emit,
                max_output_tokens=CHAT_MAX_OUTPUT_TOKENS,
                on_delta=_emit_delta,
            )

        def _record(span: Any, result: tuple[dict[str, Any], Any]) -> None:
            response, usage = result
            span.update(
                usage_details=usage_details(usage),
                input={
                    "messages": messages,
                    "tool_exchanges": len(transcript),
                    "force_emit": force_emit,
                },
                output=response,
                metadata={
                    "prompt_version": CHAT_PROMPT_VERSION,
                    "call_index": call_count,
                    **usage_metadata(usage),
                },
                model=CHAT_MODEL,
            )

        # The streaming adapter bypasses the instrumented-client path,
        # so the generation observation is opened here — without it the
        # turn's trace holds no model I/O at all (review stack,
        # live-trace lane).
        response, usage = tracing.traced_call(
            backends.langfuse,
            name="chat:call",
            as_type="generation",
            call=_call,
            update=_record,
        )
        return {
            "emission": response.get("answer"),
            "tool_calls": response.get("tool_calls", []),
            "malformed": 0,
        }, usage

    labels: Mapping[str, str] = _TOOL_LABELS

    def _on_tool_start(name: str, _arguments: dict[str, Any]) -> None:
        """Stop before a read or report its user-facing activity."""
        _stop()
        if on_progress is not None:
            on_progress(labels[name])

    with tracing.component_span(
        backends.langfuse,
        run_id=trace_run_id,
        task_id=task_id,
        component="chat",
        # The caller names the Langfuse session (ADR 0038): the chat route
        # passes its conversation id; a Task Agent turn at the gate passes the
        # task id, as every planning turn and run does.
        session_id=trace_session_id,
        conversation_id=conversation_id,
    ) as root_span:
        loop = run_tool_loop(
            turn_fn,
            tools=tools,
            turn_cap=SECTION_TURN_CAP,
            retriever=retriever,
            emit_label="emit_answer",
            on_tool_start=_on_tool_start,
            langfuse_client=backends.langfuse,
        )
        _stop()
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
                input={"question": question},
                output={
                    "answer": floored.prose,
                    "citations": len(floored.citations),
                },
                metadata={"prompt_version": CHAT_PROMPT_VERSION, "model": CHAT_MODEL},
            )
        trace_id = _trace_id(root_span)
    payload = AnswerPayload(
        claims=floored.claims,
        citations=_resolve_citation_sources(engine, floored.citations, task_id=task_id),
        warning_not_evidence_checked=floored.warning_not_evidence_checked,
        stripped=floored.stripped,
        evidence_not_held=floored.evidence_not_held,
        handoff="evidence_not_held" if floored.evidence_not_held else None,
        tool_digest={
            "calls": loop["tool_call_counts"],
            "rejected": loop["rejected_tool_calls"],
            "turns_used": loop["turns_used"],
        },
        model_id=CHAT_MODEL,
        prompt_version=CHAT_PROMPT_VERSION,
        trace_id=trace_id,
        stopped_before_evidence_check=False,
        enrichment={"status": "pending" if floored.citations else "not_applicable"},
    )
    if not emitted:
        _emit_delta(floored.prose)
    return floored.prose, payload
