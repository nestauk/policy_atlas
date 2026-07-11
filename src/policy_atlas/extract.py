"""Extract component (task 011): the framework's first findings-layer write.

Per selected document: load the selection row, resolve the extraction basis
(full-text chunks or the envelope abstract), check the durable memo, window and
fan out the ``extract_iof_v5`` calls, validate / verify / dedup the emitted
records, then write the durable ``source_extraction_record`` +
``intervention_outcome_finding`` rows and, last of all, the run-scoped
``extraction_result`` roll-up.

The pipeline is deterministic apart from the model call itself: memo lookup,
windowing, quote verification and every DB write are pure or parent-ordered so
that concurrent window calls never change the persisted state. Extraction
failure is coverage, never component failure — the component only raises
structurally (missing selection row, invariant violation).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, NamedTuple, cast

import structlog
from sqlalchemy import select as sa_select
from sqlalchemy.engine import Connection

from policy_atlas.extract_prompt import (
    EXTRACT_MAX_OUTPUT_TOKENS,
    EXTRACTION_MODEL,
    PROMPT_VERSION,
)
from policy_atlas.extraction_backend import ExtractionBackend
from policy_atlas.extraction_records import (
    ABSTRACT_SEGMENT_ID,
    PROFILE_ID,
    SCHEMA_VERSION,
    ExtractionWindowPayload,
    IOFRecord,
    IOFRecordWire,
)
from policy_atlas.junk_judge import (
    JUNK_JUDGE_PROMPT_VERSION,
    JunkJudgeBackend,
    JunkVerdictWire,
    validate_verdict_coverage,
)
from policy_atlas.quote_verify import (
    FIELD_RULES_VERSION,
    QUOTE_VERIFIER_VERSION,
    QuoteMatch,
    QuoteMatcher,
    build_basis,
    claim_key,
    dedup_records,
    validate_record,
)
from policy_atlas.schema import (
    MEMO_STATUSES,
    chunk,
    extraction_result,
    intervention_outcome_finding,
    project_source_snapshot,
    selection_result,
    source_classification_result,
    source_extraction_record,
    source_snapshot,
)
from policy_atlas.usage import TokenUsage, UsageAccumulator
from policy_atlas.windowing import greedy_windows as _shared_greedy_windows

log = structlog.get_logger()

# --- Windowing / call constants (plan-pinned; every knob enters the fingerprint) ---

WINDOW_CHAR_BUDGET = 150_000
WINDOW_OVERLAP_CHUNKS = 1
OVERSIZE_SUBSEGMENT_OVERLAP = 1_000
OVERSIZE_POLICY = "char_split_v1"
EXTRACT_RETRY_CAP = 1
MAX_CONCURRENT_EXTRACT = 4
EXTRACTION_PROFILE = PROFILE_ID

# 018 C5 junk judge: component.completed payload record cap (flag-not-drop —
# every flagged finding is counted; only the displayed record list is capped).
JUNK_FLAGGED_RECORDS_CAP = 50


class ExtractError(Exception):
    """Structural extract failure — missing selection row or invariant violation.

    Raised (never returned) so the harness routes it to ``component.failed``;
    it is deliberately distinct from a per-document extraction failure, which is
    coverage recorded in the roll-up.
    """


@dataclass(frozen=True)
class ExtractContext:
    """Scope-level input to extract.

    Attributes:
        scope_id: Evidence scope being extracted.
        intent: Scope intent, carried for wiring uniformity with the other
            scope components. It is **not** consumed by extraction (contract
            rev 1.5): extraction is question-agnostic, so no intent enters the
            prompt or the extraction fingerprint. Keeping it here means the
            ``functools.partial`` context construction in the harness is uniform
            across components; a reviewer need not re-flag its presence.
        context: Scope context JSONB (unused by extraction in v1).
        selection_run_id: Explicit selection run whose ``selected`` set is
            extracted — the compile-fails-closed upstream reference.
    """

    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]
    selection_run_id: uuid.UUID


def extraction_fingerprint(
    mode: str, *, junk_judge_active: bool = False
) -> tuple[str, dict[str, Any]]:
    """Build the extraction fingerprint and its canonical component map.

    The digest is the **full** sha256 hex (no truncation — the column is TEXT)
    over the canonical JSON of every output-affecting knob: profile, both model
    layers' schema version, prompt, model, backend mode, field-rule set, quote
    verifier, the full windowing policy, and the output/retry caps. Any change
    that alters stored findings bumps a component version and thus the digest,
    so an upgrade creates records alongside rather than reusing stale ones.

    Args:
        mode: The backend mode (``"live"`` or ``"stub"``), from
            ``backend.mode`` — a stub result can never masquerade as a live one.
        junk_judge_active: Whether a junk judge backend was supplied. Judged
            and unjudged runs never reuse each other's records (018 C5).

    Returns:
        A ``(fingerprint_hex, components)`` pair. ``components`` is recorded
        verbatim in ``extraction_provenance`` (plus runtime keys), so a test can
        assert every component version appears there.
    """
    components: dict[str, Any] = {
        "profile": PROFILE_ID,
        "schema": SCHEMA_VERSION,
        "prompt": PROMPT_VERSION,
        "model": EXTRACTION_MODEL,
        "mode": mode,
        "field_rules": FIELD_RULES_VERSION,
        "verifier": QUOTE_VERIFIER_VERSION,
        "window": {
            "char_budget": WINDOW_CHAR_BUDGET,
            "overlap": WINDOW_OVERLAP_CHUNKS,
            "oversize_policy": OVERSIZE_POLICY,
            "oversize_overlap": OVERSIZE_SUBSEGMENT_OVERLAP,
        },
        "max_output_tokens": EXTRACT_MAX_OUTPUT_TOKENS,
        "retry_cap": EXTRACT_RETRY_CAP,
        "junk_judge": JUNK_JUDGE_PROMPT_VERSION if junk_judge_active else None,
    }
    canonical = json.dumps(components, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest, components


@dataclass
class _ExtractCallBudget:
    """Pre-run call ceiling; every call (initial or retry) reserves one slot."""

    maximum: int
    used: int = 0

    def reserve(self) -> bool:
        if self.used >= self.maximum:
            return False
        self.used += 1
        return True


@dataclass
class _Doc:
    """One selected document threaded through the pipeline in selected order."""

    pss_id: uuid.UUID
    text_basis: str
    envelope_snapshot_id: uuid.UUID
    full_text_snapshot_id: uuid.UUID | None
    metadata: dict[str, Any]
    primary_evidence_type: str | None
    chunks: list[tuple[uuid.UUID, str]]

    # Resolved basis (set by _resolve_basis).
    basis: str = ""
    basis_snapshot_id: uuid.UUID | None = None
    record_snapshot_id: uuid.UUID | None = None
    original_segments: Sequence[tuple[str | None, str]] = ()
    window_payloads: list[ExtractionWindowPayload] = field(default_factory=list)

    # Provenance class.
    reused: bool = False
    extractable: bool = False  # basis-ok, memo-miss: needs calls

    # Outcome.
    status: str = ""
    error: str | None = None
    extraction_record_id: uuid.UUID | None = None
    finding_count: int = 0

    # Fresh-run payloads / counters.
    survivors: list[IOFRecord] = field(default_factory=list)
    groundings: list[list[dict[str, Any]]] = field(default_factory=list)
    coverage_by_survivor: list[dict[str, str]] = field(default_factory=list)
    invalid_dropped: int = 0
    dedup_collapsed: int = 0
    quote_unverified: int = 0

    # Junk judge (018 C5) — flag-not-drop accounting for this document.
    junk_flagged_count: int = 0
    junk_flagged_records: list[dict[str, Any]] = field(default_factory=list)
    junk_judge_failed: bool = False

    @property
    def title(self) -> str:
        value = self.metadata.get("title")
        return value if isinstance(value, str) else ""

    @property
    def abstract(self) -> str | None:
        value = self.metadata.get("abstract")
        return value if isinstance(value, str) else None


# --- Selection load + document loading -------------------------------------


def _load_selection(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    selection_run_id: uuid.UUID,
) -> list[dict[str, Any]]:
    row = conn.execute(
        sa_select(selection_result.c.selected)
        .where(selection_result.c.project_id == project_id)
        .where(selection_result.c.evidence_scope_id == scope_id)
        .where(selection_result.c.run_id == selection_run_id)
    ).first()
    if row is None:
        raise ExtractError(
            f"no selection row for scope {scope_id} and selection_run_id "
            f"{selection_run_id} — run select first"
        )
    selected = row.selected
    if not isinstance(selected, list):
        raise ExtractError("selection_result.selected payload must be a list")
    return cast("list[dict[str, Any]]", selected)


def _load_docs(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    selected: list[dict[str, Any]],
) -> list[_Doc]:
    """Load each selected document in selected-list order.

    Joins the selected pss ids to their envelope snapshot metadata +
    full-text link and (LEFT JOIN) the classification result for
    ``primary_evidence_type``; full-text chunks are loaded and grouped by
    snapshot. A selected pss id with no pss row is a structural failure.
    """
    order: list[tuple[uuid.UUID, str]] = []
    for record in selected:
        raw_id = record.get("pss_id")
        if not isinstance(raw_id, str):
            raise ExtractError("selected record missing a string pss_id")
        try:
            pss_id = uuid.UUID(raw_id)
        except ValueError as exc:
            raise ExtractError(f"selected record carries an invalid pss_id: {raw_id!r}") from exc
        text_basis = record.get("text_basis")
        order.append((pss_id, text_basis if isinstance(text_basis, str) else ""))

    pss_ids = [pss_id for pss_id, _ in order]
    loaded: dict[uuid.UUID, dict[str, Any]] = {}
    if pss_ids:
        rows = conn.execute(
            sa_select(
                project_source_snapshot.c.project_source_snapshot_id,
                project_source_snapshot.c.source_snapshot_id,
                project_source_snapshot.c.full_text_snapshot_id,
                source_snapshot.c.metadata,
                source_classification_result.c.primary_evidence_type,
            )
            .select_from(
                project_source_snapshot.join(
                    source_snapshot,
                    project_source_snapshot.c.source_snapshot_id
                    == source_snapshot.c.source_snapshot_id,
                ).outerjoin(
                    source_classification_result,
                    (
                        source_classification_result.c.project_source_snapshot_id
                        == project_source_snapshot.c.project_source_snapshot_id
                    )
                    & (source_classification_result.c.project_id == project_id)
                    & (source_classification_result.c.evidence_scope_id == scope_id),
                )
            )
            .where(project_source_snapshot.c.project_id == project_id)
            .where(project_source_snapshot.c.project_source_snapshot_id.in_(pss_ids))
        ).fetchall()
        for row in rows:
            loaded[cast("uuid.UUID", row.project_source_snapshot_id)] = {
                "source_snapshot_id": row.source_snapshot_id,
                "full_text_snapshot_id": row.full_text_snapshot_id,
                "metadata": dict(row.metadata) if row.metadata is not None else {},
                "primary_evidence_type": row.primary_evidence_type,
            }

    chunk_source_ids = {
        _frozen_text_snapshot_id(row["full_text_snapshot_id"], row["source_snapshot_id"])
        for row in loaded.values()
    }
    chunks_by_snapshot: dict[uuid.UUID, list[tuple[uuid.UUID, str]]] = {}
    if chunk_source_ids:
        chunk_rows = conn.execute(
            sa_select(chunk.c.source_snapshot_id, chunk.c.chunk_id, chunk.c.content)
            .where(chunk.c.source_snapshot_id.in_(chunk_source_ids))
            .order_by(chunk.c.source_snapshot_id, chunk.c.sequence)
        ).fetchall()
        for chunk_row in chunk_rows:
            snapshot_id = cast("uuid.UUID", chunk_row.source_snapshot_id)
            chunks_by_snapshot.setdefault(snapshot_id, []).append(
                (cast("uuid.UUID", chunk_row.chunk_id), cast("str", chunk_row.content))
            )

    docs: list[_Doc] = []
    for pss_id, text_basis in order:
        row_data = loaded.get(pss_id)
        if row_data is None:
            raise ExtractError(f"selected pss {pss_id} has no project_source_snapshot row")
        full_text_id = cast("uuid.UUID | None", row_data["full_text_snapshot_id"])
        envelope_id = cast("uuid.UUID", row_data["source_snapshot_id"])
        docs.append(
            _Doc(
                pss_id=pss_id,
                text_basis=text_basis,
                envelope_snapshot_id=envelope_id,
                full_text_snapshot_id=full_text_id,
                metadata=cast("dict[str, Any]", row_data["metadata"]),
                primary_evidence_type=row_data["primary_evidence_type"],
                chunks=chunks_by_snapshot.get(
                    _frozen_text_snapshot_id(full_text_id, envelope_id), []
                ),
            )
        )
    return docs


# --- Basis resolution + windowing ------------------------------------------


def _frozen_text_snapshot_id(
    full_text_snapshot_id: uuid.UUID | None, envelope_snapshot_id: uuid.UUID
) -> uuid.UUID:
    """The frozen text's home snapshot — the single statement of the rule.

    The full-text snapshot when one was ingested (acquired docs), else the
    envelope snapshot itself (uploaded docs carry their chunks there — the 008
    corpus model). Chunk loading, basis resolution and the memo/record key all
    resolve through here so they can never silently diverge.
    """
    return (
        full_text_snapshot_id if full_text_snapshot_id is not None else envelope_snapshot_id
    )


def _fail_basis(doc: _Doc, *, basis: str, snapshot_id: uuid.UUID, error: str) -> None:
    doc.basis = basis
    doc.record_snapshot_id = snapshot_id
    doc.status = "extraction_failed"
    doc.error = error


def _resolve_basis(doc: _Doc) -> None:
    """Resolve the extraction basis and window segments for one document.

    On success sets ``basis`` / ``basis_snapshot_id`` / ``original_segments``
    and the window payloads. On failure the document is marked
    ``extraction_failed`` with ``basis_mismatch`` (state mismatch) or
    ``empty_basis`` (present-but-empty text — never ``no_findings``, which would
    be a false absence). Failure records use the envelope snapshot when the
    basis snapshot is unavailable (NOT NULL honesty).
    """
    if doc.text_basis == "full_text":
        basis_snapshot_id = _frozen_text_snapshot_id(
            doc.full_text_snapshot_id, doc.envelope_snapshot_id
        )
        if not doc.chunks:
            # An ingested-but-chunkless snapshot is empty text; a doc selected as
            # full_text with no chunks anywhere is a selection/state mismatch.
            error = "empty_basis" if doc.full_text_snapshot_id is not None else "basis_mismatch"
            _fail_basis(doc, basis="full_text", snapshot_id=basis_snapshot_id, error=error)
            return
        doc.basis = "full_text"
        doc.basis_snapshot_id = basis_snapshot_id
        doc.record_snapshot_id = basis_snapshot_id
        segments = [(str(chunk_id), content) for chunk_id, content in doc.chunks]
        doc.original_segments = segments
        doc.window_payloads = _window_payloads(doc, segments)
        return

    if doc.text_basis == "abstract_only":
        abstract = doc.metadata.get("abstract")
        if not isinstance(abstract, str) or not abstract:
            _fail_basis(
                doc,
                basis="abstract_only",
                snapshot_id=doc.envelope_snapshot_id,
                error="empty_basis",
            )
            return
        doc.basis = "abstract_only"
        doc.basis_snapshot_id = doc.envelope_snapshot_id
        doc.record_snapshot_id = doc.envelope_snapshot_id
        doc.original_segments = [(None, abstract)]
        doc.window_payloads = _window_payloads(doc, [(ABSTRACT_SEGMENT_ID, abstract)])
        return

    # Any other text_basis value — a state the current select can't emit; record
    # the thinnest basis with the envelope snapshot so the loud failure is durable.
    _fail_basis(
        doc, basis="abstract_only", snapshot_id=doc.envelope_snapshot_id, error="basis_mismatch"
    )


def _greedy_windows(segments: list[tuple[str, str]]) -> list[list[tuple[str, str]]]:
    """Greedy ordered windows using extraction's pinned constants."""
    return _shared_greedy_windows(
        segments,
        char_budget=WINDOW_CHAR_BUDGET,
        overlap_segments=WINDOW_OVERLAP_CHUNKS,
        oversize_overlap_chars=OVERSIZE_SUBSEGMENT_OVERLAP,
    )


def _window_payloads(doc: _Doc, segments: list[tuple[str, str]]) -> list[ExtractionWindowPayload]:
    payloads: list[ExtractionWindowPayload] = []
    for window_index, window in enumerate(_greedy_windows(segments)):
        payloads.append(
            ExtractionWindowPayload(
                pss_id=str(doc.pss_id),
                window_index=window_index,
                title=doc.title,
                abstract=doc.abstract,
                primary_evidence_type=doc.primary_evidence_type,
                segments=[{"segment_id": sid, "content": content} for sid, content in window],
                metadata=doc.metadata,
            )
        )
    return payloads


# --- Memo -------------------------------------------------------------------


class _MemoHit(NamedTuple):
    """One durable memo row (success states only) for a basis snapshot."""

    extraction_record_id: uuid.UUID
    status: str
    basis: str
    finding_count: int


def _apply_memo(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    fingerprint: str,
    docs: list[_Doc],
) -> None:
    """Mark basis-ok documents reused (memo hit) or extractable (memo miss)."""
    basis_snapshots = [
        doc.basis_snapshot_id
        for doc in docs
        if doc.status == "" and doc.basis_snapshot_id is not None
    ]
    memo: dict[uuid.UUID, _MemoHit] = {}
    if basis_snapshots:
        rows = conn.execute(
            sa_select(
                source_extraction_record.c.extraction_record_id,
                source_extraction_record.c.source_snapshot_id,
                source_extraction_record.c.status,
                source_extraction_record.c.basis,
                source_extraction_record.c.finding_count,
            )
            .where(source_extraction_record.c.project_id == project_id)
            .where(source_extraction_record.c.extraction_fingerprint == fingerprint)
            .where(source_extraction_record.c.status.in_(MEMO_STATUSES))
            .where(source_extraction_record.c.source_snapshot_id.in_(basis_snapshots))
        ).fetchall()
        for row in rows:
            memo[cast("uuid.UUID", row.source_snapshot_id)] = _MemoHit(
                extraction_record_id=row.extraction_record_id,
                status=row.status,
                basis=row.basis,
                finding_count=int(row.finding_count),
            )

    for doc in docs:
        if doc.status != "" or doc.basis_snapshot_id is None:
            continue
        hit = memo.get(doc.basis_snapshot_id)
        if hit is None:
            doc.extractable = True
            continue
        doc.reused = True
        doc.extraction_record_id = hit.extraction_record_id
        doc.status = hit.status
        doc.basis = hit.basis
        doc.finding_count = hit.finding_count


# --- Fan-out ----------------------------------------------------------------


def _scrub_nul(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, list):
        return [_scrub_nul(item) for item in value]
    if isinstance(value, dict):
        return {key: _scrub_nul(item) for key, item in value.items()}
    return value


def _scrub_findings(findings: list[IOFRecordWire]) -> list[IOFRecordWire]:
    """Strip NUL characters from every string in the wire records.

    Model output is untrusted data; Postgres rejects ``\\u0000`` in TEXT and
    JSONB, so an emitted NUL would abort the whole write transaction (observed
    on the first live run). Scrubbed at the backend boundary, before
    validation/verification, like any other encoding hygiene.
    """
    return [
        IOFRecordWire.model_validate(_scrub_nul(record.model_dump()))
        for record in findings
    ]


def _run_windows(
    docs: list[_Doc],
    *,
    extraction_backend: ExtractionBackend,
) -> tuple[
    dict[int, dict[int, list[IOFRecordWire]]],
    dict[int, Exception],
    int,
    _ExtractCallBudget,
    int,
    dict[str, int],
]:
    """Run every extractable window through the backend with one retry per window.

    Returns per-document window findings (only for documents whose windows all
    succeeded), the surviving per-document failure exception, the call budget,
    and the total retry count.
    """
    tasks: list[tuple[int, int]] = []
    payloads: dict[tuple[int, int], ExtractionWindowPayload] = {}
    for doc_index, doc in enumerate(docs):
        if not doc.extractable:
            continue
        for payload in doc.window_payloads:
            key = (doc_index, payload.window_index)
            tasks.append(key)
            payloads[key] = payload

    baseline = len(tasks)
    maximum = baseline * (1 + EXTRACT_RETRY_CAP)
    budget = _ExtractCallBudget(maximum=maximum)
    log.info("extract.call_budget", baseline=baseline, maximum=maximum)

    results: dict[tuple[int, int], list[IOFRecordWire]] = {}
    errors: dict[tuple[int, int], Exception] = {}
    usage_totals = UsageAccumulator()

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_EXTRACT) as executor:
        submitted: list[tuple[tuple[int, int], Future[Any]]] = []
        for key in tasks:
            if not budget.reserve():  # unreachable by construction; fail closed
                errors[key] = RuntimeError("call budget exhausted")
                continue
            submitted.append((key, executor.submit(extraction_backend.extract, payloads[key])))
        wait([future for _, future in submitted])
        for key, future in submitted:
            try:
                response, usage = future.result()
                results[key] = _scrub_findings(list(response.findings))
                usage_totals.add(usage)
            except Exception as exc:  # noqa: BLE001 — reduced to a type name for the record
                errors[key] = exc

    retry_count = 0
    for key in list(errors):
        if not budget.reserve():
            continue
        retry_count += 1
        try:
            response, usage = extraction_backend.extract(payloads[key])
            results[key] = _scrub_findings(list(response.findings))
            usage_totals.add(usage)
        except Exception as exc:  # noqa: BLE001
            errors[key] = exc
        else:
            del errors[key]

    per_doc: dict[int, dict[int, list[IOFRecordWire]]] = {}
    for (doc_index, window_index), records in results.items():
        per_doc.setdefault(doc_index, {})[window_index] = records
    # The earliest failing window (window order) wins the recorded type name.
    doc_errors: dict[int, Exception] = {}
    for doc_index, window_index in sorted(errors):
        doc_errors.setdefault(doc_index, errors[(doc_index, window_index)])

    return per_doc, doc_errors, baseline, budget, retry_count, usage_totals.payload()


# --- Per-document pipeline --------------------------------------------------


def _grounding_entry(segment_id: str | None, quote: str, match: QuoteMatch) -> dict[str, Any]:
    """Build one anchor's grounding entry.

    ``segment_id`` is the model's *claim* about location, stored verbatim as
    untrusted data and never dereferenced. The top-level ``chunk_id`` is the
    **verified** location — the first span found by the presence check against
    the whole document basis (``None`` when unverified or abstract-basis) — so
    a consumer reading ``chunk_id`` can never be steered by a fabricated claim.
    """
    return {
        "segment_id": segment_id,
        "chunk_id": match.spans[0].chunk_id if match.spans else None,
        "quote": quote,
        "match_status": match.status,
        "quote_verified": match.status != "failed",
        "spans": [
            {"chunk_id": span.chunk_id, "start": span.start, "end": span.end}
            for span in match.spans
        ],
    }


def _process_doc(doc: _Doc, window_findings: dict[int, list[IOFRecordWire]]) -> None:
    """Run the within-document pipeline for a document whose windows all succeeded."""
    wire_records: list[IOFRecordWire] = []
    for window_index in sorted(window_findings):
        wire_records.extend(window_findings[window_index])

    if not wire_records:
        doc.status = "no_findings"
        doc.finding_count = 0
        return

    validated = [validate_record(wire) for wire in wire_records]
    doc.invalid_dropped = sum(1 for item in validated if item.grain_invalid)
    valid = [item for item in validated if not item.grain_invalid]
    if not valid:
        doc.status = "extraction_failed"
        doc.error = "invalid_records"
        doc.finding_count = 0
        return

    coverage_by_claim: dict[tuple[object, ...], dict[str, str]] = {}
    stored: list[IOFRecord] = []
    for item in valid:
        record = cast("IOFRecord", item.record)
        stored.append(record)
        key = claim_key(record)
        if key not in coverage_by_claim:
            coverage_by_claim[key] = item.field_coverage

    survivors, collapsed = dedup_records(stored)
    doc.dedup_collapsed = collapsed

    matcher = QuoteMatcher(build_basis(doc.original_segments))
    groundings: list[list[dict[str, Any]]] = []
    coverage_list: list[dict[str, str]] = []
    quote_unverified = 0
    for record in survivors:
        entries: list[dict[str, Any]] = []
        any_failed = False
        for anchor in record.anchors:
            match = matcher.find(anchor.quote)
            if match.status == "failed":
                any_failed = True
            entries.append(_grounding_entry(anchor.segment_id, anchor.quote, match))
        if any_failed:
            quote_unverified += 1
        groundings.append(entries)
        coverage_list.append(coverage_by_claim[claim_key(record)])

    doc.status = "extracted"
    doc.finding_count = len(survivors)
    doc.survivors = survivors
    doc.groundings = groundings
    doc.coverage_by_survivor = coverage_list
    doc.quote_unverified = quote_unverified


# --- Junk judge (018 C5) -----------------------------------------------------


def _judge_payload_entry(index: int, record: IOFRecord) -> dict[str, Any]:
    """Build one dedup survivor's id-keyed judge input entry."""
    return {
        "index": index,
        "intervention": record.intervention,
        "outcome": record.outcome,
        "effect_direction": record.effect_direction,
        "estimate_level": record.estimate_level,
        "stratum_qualifiers": [
            {"type": stratum.type, "value": stratum.value}
            for stratum in record.stratum_qualifiers
        ],
        "quotes": [anchor.quote for anchor in record.anchors],
    }


def _apply_junk_judge(doc: _Doc, junk_judge_backend: JunkJudgeBackend) -> TokenUsage | None:
    """Judge one document's dedup survivors, excluding clear junk (flag-not-drop).

    Runs AFTER ``dedup_records`` and BEFORE the IOF insert (``doc.survivors``
    etc. are mutated in place, so ``_write_docs`` never sees excluded
    findings). A judge call/parse/coverage failure is fail-open: the document
    persists unfiltered and ``doc.junk_judge_failed`` is set for accounting —
    the filter is an enhancement, never an extraction blocker.

    Args:
        doc: An ``extracted`` document with dedup survivors already resolved.
        junk_judge_backend: The judge seam.

    Returns:
        The judge call's token usage, or ``None`` on failure or no usage.
    """
    findings = [_judge_payload_entry(index, record) for index, record in enumerate(doc.survivors)]
    try:
        response, usage = junk_judge_backend.judge({"findings": findings})
        validate_verdict_coverage(findings, response.verdicts)
    except Exception as exc:  # noqa: BLE001 — reduced to a type name for the record
        doc.junk_judge_failed = True
        log.warning(
            "extract.junk_judge_failed", pss_id=str(doc.pss_id), error=type(exc).__name__
        )
        return None

    junk_by_index: dict[int, JunkVerdictWire] = {
        verdict.finding_index: verdict
        for verdict in response.verdicts
        if verdict.verdict == "junk"
    }
    if not junk_by_index:
        return usage

    kept_survivors: list[IOFRecord] = []
    kept_groundings: list[list[dict[str, Any]]] = []
    kept_coverage: list[dict[str, str]] = []
    for index, (record, grounding, coverage) in enumerate(
        zip(doc.survivors, doc.groundings, doc.coverage_by_survivor, strict=True)
    ):
        verdict = junk_by_index.get(index)
        if verdict is None:
            kept_survivors.append(record)
            kept_groundings.append(grounding)
            kept_coverage.append(coverage)
            continue
        doc.junk_flagged_records.append(
            {
                "intervention": record.intervention,
                "outcome": record.outcome,
                "junk_class": verdict.junk_class,
                "reason": verdict.reason,
            }
        )

    doc.junk_flagged_count = len(doc.junk_flagged_records)
    doc.survivors = kept_survivors
    doc.groundings = kept_groundings
    doc.coverage_by_survivor = kept_coverage
    doc.finding_count = len(kept_survivors)
    if not kept_survivors:
        # Every finding was junk-flagged: the doc contributes no usable
        # evidence, so its status says so honestly — `junk_flagged_count`
        # preserves the distinction from a genuinely-empty extraction.
        doc.status = "no_findings"
    return usage


# --- Writes -----------------------------------------------------------------


def _write_docs(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    fingerprint: str,
    docs: list[_Doc],
    created_at: datetime,
) -> None:
    """Write each non-reused document's record + findings in selected-set order."""
    for doc in docs:
        if doc.reused:
            continue
        record_id = uuid.uuid4()
        doc.extraction_record_id = record_id
        conn.execute(
            source_extraction_record.insert().values(
                extraction_record_id=record_id,
                project_id=project_id,
                source_snapshot_id=doc.record_snapshot_id,
                project_source_snapshot_id=doc.pss_id,
                extraction_fingerprint=fingerprint,
                status=doc.status,
                basis=doc.basis,
                error=doc.error,
                finding_count=doc.finding_count,
                run_id=run_id,
                created_at=created_at,
            )
        )
        for record, grounding, coverage in zip(
            doc.survivors, doc.groundings, doc.coverage_by_survivor, strict=True
        ):
            conn.execute(
                intervention_outcome_finding.insert().values(
                    finding_id=uuid.uuid4(),
                    project_id=project_id,
                    extraction_record_id=record_id,
                    intervention=record.intervention,
                    outcome=record.outcome,
                    population=record.population,
                    comparator=record.comparator,
                    effect_direction=record.effect_direction,
                    estimate_level=record.estimate_level,
                    study_design=record.study_design,
                    stratum_qualifiers=[
                        {"type": stratum.type, "value": stratum.value}
                        for stratum in record.stratum_qualifiers
                    ],
                    statistics=record.statistics.model_dump(),
                    causality_by_design=record.causality_by_design,
                    is_primary=record.is_primary,
                    is_prevalence_only=record.is_prevalence_only,
                    field_coverage=coverage,
                    grounding=grounding,
                    created_at=created_at,
                )
            )


# --- Summary / invariants ---------------------------------------------------


def _doc_summary(doc: _Doc, *, junk_judge_active: bool) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "pss_id": str(doc.pss_id),
        "status": doc.status,
        "basis": doc.basis,
        "finding_count": doc.finding_count,
        "reused": doc.reused,
        "error": doc.error,
        "extraction_record_id": str(doc.extraction_record_id),
    }
    if junk_judge_active:
        summary["junk_flagged"] = doc.junk_flagged_count
    return summary


def _assert_invariants(docs: list[_Doc], *, selected_count: int) -> None:
    """Assert the coverage invariants before any write (violation raises)."""
    pss_ids = [doc.pss_id for doc in docs]
    if len(pss_ids) != selected_count or len(set(pss_ids)) != selected_count:
        raise ExtractError(
            "extract invariant violated: per-doc statuses do not cover the selected set"
        )
    extracted = sum(1 for doc in docs if doc.status == "extracted")
    no_findings = sum(1 for doc in docs if doc.status == "no_findings")
    failed = sum(1 for doc in docs if doc.status == "extraction_failed")
    if selected_count != extracted + no_findings + failed:
        raise ExtractError("extract invariant violated: status sum != selected")
    fresh = sum(1 for doc in docs if not doc.reused)
    reused = sum(1 for doc in docs if doc.reused)
    if selected_count != fresh + reused:
        raise ExtractError("extract invariant violated: fresh + reused != selected")
    if any(doc.reused and doc.status == "extraction_failed" for doc in docs):
        raise ExtractError("extract invariant violated: a failed doc is reused")


def _build_summary(
    docs: list[_Doc],
    *,
    selection_run_id: uuid.UUID,
    components: dict[str, Any],
    fingerprint: str,
    budget_baseline: int,
    budget_maximum: int,
    budget_used: int,
    retry_count: int,
    usage_totals: dict[str, int],
    junk_judge_active: bool,
) -> dict[str, Any]:
    selected = len(docs)
    counts = {
        "selected": selected,
        "extracted": sum(1 for doc in docs if doc.status == "extracted"),
        "no_findings": sum(1 for doc in docs if doc.status == "no_findings"),
        "failed": sum(1 for doc in docs if doc.status == "extraction_failed"),
        "fresh": sum(1 for doc in docs if not doc.reused),
        "reused": sum(1 for doc in docs if doc.reused),
    }
    if junk_judge_active:
        counts["junk_judge_failed"] = sum(1 for doc in docs if doc.junk_judge_failed)
    findings = {
        "total": sum(doc.finding_count for doc in docs if doc.status == "extracted"),
        "quote_unverified": sum(doc.quote_unverified for doc in docs if not doc.reused),
        "dedup_collapsed": sum(doc.dedup_collapsed for doc in docs if not doc.reused),
        "invalid_dropped": sum(doc.invalid_dropped for doc in docs if not doc.reused),
    }
    full_text = sum(1 for doc in docs if doc.basis == "full_text")
    abstract_only = sum(1 for doc in docs if doc.basis == "abstract_only")
    basis = {
        "full_text": full_text,
        "abstract_only": abstract_only,
        "shares": {
            "full_text": full_text / selected if selected else 0.0,
            "abstract_only": abstract_only / selected if selected else 0.0,
        },
    }
    field_coverage: dict[str, dict[str, int]] = {}
    for doc in docs:
        if doc.reused or doc.status != "extracted":
            continue
        for coverage in doc.coverage_by_survivor:
            for name, marker in coverage.items():
                field_coverage.setdefault(name, {})
                field_coverage[name][marker] = field_coverage[name].get(marker, 0) + 1

    junk_flagged: dict[str, Any] | None = None
    if junk_judge_active:
        junk_flagged_by_class: dict[str, int] = {}
        junk_flagged_records: list[dict[str, Any]] = []
        for doc in docs:
            for record in doc.junk_flagged_records:
                junk_class = cast("str", record["junk_class"])
                junk_flagged_by_class[junk_class] = junk_flagged_by_class.get(junk_class, 0) + 1
                junk_flagged_records.append(record)
        junk_flagged = {
            "total": len(junk_flagged_records),
            "by_class": junk_flagged_by_class,
            "records": junk_flagged_records[:JUNK_FLAGGED_RECORDS_CAP],
        }
        if len(junk_flagged_records) > JUNK_FLAGGED_RECORDS_CAP:
            junk_flagged["records_truncated"] = True

    flags: list[str] = []
    if counts["failed"] > 0:
        flags.append("extraction_failures")
    if selected == 0:
        flags.append("empty_selection")
    if junk_flagged is not None and junk_flagged["total"] > 0:
        flags.append("junk_flagged_present")
    # thin_extraction is deliberately NOT computed in v1 (contract "where computed").

    provenance = {
        **components,
        "fingerprint": fingerprint,
        "pass_count": 1,
        "call_budget": {
            "baseline": budget_baseline,
            "maximum": budget_maximum,
            "used": budget_used,
        },
        "retry_count": retry_count,
    }
    summary: dict[str, Any] = {
        "docs": [_doc_summary(doc, junk_judge_active=junk_judge_active) for doc in docs],
        "counts": counts,
        "findings": findings,
        "basis": basis,
        "field_coverage": field_coverage,
        "selection_run_id": str(selection_run_id),
        "flags": flags,
        "provenance": provenance,
        "usage_totals": usage_totals,
    }
    if junk_flagged is not None:
        summary["junk_flagged"] = junk_flagged
    return summary


# --- Public entry point -----------------------------------------------------


def extract_scope(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ExtractContext,
    extraction_backend: ExtractionBackend,
    junk_judge_backend: JunkJudgeBackend | None = None,
) -> dict[str, Any]:
    """Extract intervention-outcome findings for one evidence scope's selection.

    Loads the referenced selection row, resolves each document's basis, checks
    the durable memo, fans out the windowed extraction calls, validates /
    verifies / dedups the emitted records, writes the durable finding + record
    rows and finally the run-scoped roll-up, then returns the extraction summary.

    Args:
        conn: Open database connection; all writes use its active transaction.
        project_id: Owning project.
        run_id: Run writing the extraction result.
        context: Scope-level extract input (carries the explicit selection run).
        extraction_backend: The extraction seam (stub by default; live on key).
        junk_judge_backend: The 018 C5 post-extract junk filter (per-doc, after
            dedup, before the IOF insert). ``None`` (the default) turns judging
            off entirely — byte-identical behaviour to the pre-018-C5 pipeline.

    Returns:
        The extraction summary payload for ``component.completed``.

    Raises:
        ExtractError: If the selection row is missing, a selected pss lacks its
            snapshot row, or a coverage invariant fails.
    """
    junk_judge_active = junk_judge_backend is not None
    fingerprint, components = extraction_fingerprint(
        extraction_backend.mode, junk_judge_active=junk_judge_active
    )
    selected = _load_selection(
        conn,
        project_id=project_id,
        scope_id=context.scope_id,
        selection_run_id=context.selection_run_id,
    )
    created_at = datetime.now(UTC)

    if not selected:
        # Honest zero-doc run — group needs this reference row (unlike select's
        # no-row rule for an empty scope).
        summary = _build_summary(
            [],
            selection_run_id=context.selection_run_id,
            components=components,
            fingerprint=fingerprint,
            budget_baseline=0,
            budget_maximum=0,
            budget_used=0,
            retry_count=0,
            usage_totals=UsageAccumulator().payload(),
            junk_judge_active=junk_judge_active,
        )
        _write_rollup(
            conn,
            project_id=project_id,
            run_id=run_id,
            scope_id=context.scope_id,
            selection_run_id=context.selection_run_id,
            summary=summary,
            created_at=created_at,
        )
        log.info("extract.completed", **summary["counts"])
        return summary

    docs = _load_docs(
        conn,
        project_id=project_id,
        scope_id=context.scope_id,
        selected=selected,
    )
    for doc in docs:
        _resolve_basis(doc)
    _apply_memo(conn, project_id=project_id, fingerprint=fingerprint, docs=docs)

    per_doc, doc_errors, baseline, budget, retry_count, window_usage_totals = _run_windows(
        docs, extraction_backend=extraction_backend
    )
    usage_accumulator = UsageAccumulator()
    usage_accumulator.add_payload(window_usage_totals)
    for doc_index, doc in enumerate(docs):
        if not doc.extractable:
            continue
        error = doc_errors.get(doc_index)
        if error is not None:
            doc.status = "extraction_failed"
            doc.error = f"window_failed: {type(error).__name__}"
            doc.finding_count = 0
            log.info("extract.doc_failed", pss_id=str(doc.pss_id), error=doc.error)
            continue
        _process_doc(doc, per_doc.get(doc_index, {}))
        if junk_judge_backend is not None and doc.status == "extracted" and doc.survivors:
            usage_accumulator.add(_apply_junk_judge(doc, junk_judge_backend))
    usage_totals = usage_accumulator.payload()

    # Asserted BEFORE any row is written: the harness catches without rollback,
    # so a violation raising here must precede the writes it would indict.
    _assert_invariants(docs, selected_count=len(selected))

    _write_docs(
        conn,
        project_id=project_id,
        run_id=run_id,
        fingerprint=fingerprint,
        docs=docs,
        created_at=created_at,
    )

    summary = _build_summary(
        docs,
        selection_run_id=context.selection_run_id,
        components=components,
        fingerprint=fingerprint,
        budget_baseline=baseline,
        budget_maximum=budget.maximum,
        budget_used=budget.used,
        retry_count=retry_count,
        usage_totals=usage_totals,
        junk_judge_active=junk_judge_active,
    )
    # The roll-up is the LAST fallible statement (the 010 pattern): the harness
    # catches without rollback, so nothing may fail after this insert.
    _write_rollup(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=context.scope_id,
        selection_run_id=context.selection_run_id,
        summary=summary,
        created_at=created_at,
    )
    log.info("extract.completed", **summary["counts"])
    return summary


def _write_rollup(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    selection_run_id: uuid.UUID,
    summary: dict[str, Any],
    created_at: datetime,
) -> None:
    counts = {
        **summary["counts"],
        "findings": summary["findings"],
        "basis": summary["basis"],
        "field_coverage": summary["field_coverage"],
    }
    conn.execute(
        extraction_result.insert().values(
            extraction_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=run_id,
            selection_run_id=selection_run_id,
            extraction_provenance=summary["provenance"],
            docs=summary["docs"],
            counts=counts,
            flags=summary["flags"],
            created_at=created_at,
        )
    )
