"""Extract component (task 011): the framework's first findings-layer write.

Per selected document: load the selection row, resolve the extraction basis
(full-text chunks or the envelope abstract), check the durable memo, window and
fan out the ``extract_iof`` prompt calls (versioned by
``extract_prompt.PROMPT_VERSION``), validate / verify / dedup the emitted
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
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, NamedTuple, cast

import structlog
from sqlalchemy import select as sa_select
from sqlalchemy.engine import Connection

from policy_atlas import tracing
from policy_atlas.extract_prompt import (
    EXTRACT_MAX_OUTPUT_TOKENS,
    EXTRACTION_MODEL,
    PROMPT_VERSION,
    UNCLASSIFIED_EVIDENCE_TYPE,
)
from policy_atlas.extraction_backend import ExtractionBackend, StubICFExtractionBackend
from policy_atlas.extraction_records import (
    ABSTRACT_SEGMENT_ID,
    PROFILE_ID,
    SCHEMA_VERSION,
    ExtractionWindowPayload,
    IOFRecord,
    IOFRecordWire,
)
from policy_atlas.finding_vetter import (
    FINDING_VETTER_MAX_OUTPUT_TOKENS,
    FINDING_VETTER_MODEL,
    FINDING_VETTER_PROMPT_VERSION,
    FINDING_VETTER_REASONING_EFFORT,
    ICF_FINDING_VETTER_MAX_OUTPUT_TOKENS,
    ICF_FINDING_VETTER_MODEL,
    ICF_FINDING_VETTER_PROMPT_VERSION,
    ICF_FINDING_VETTER_REASONING_EFFORT,
    FindingVetterBackend,
    ICFFindingVetterBackend,
    ICFVetterVerdictWire,
    VetterVerdictWire,
    validate_icf_verdict_coverage,
    validate_verdict_coverage,
)
from policy_atlas.implementation_context_prompt import (
    ICF_EXTRACT_MAX_OUTPUT_TOKENS,
    ICF_EXTRACTION_MODEL,
    ICF_PROMPT_VERSION,
)
from policy_atlas.implementation_context_records import (
    PROFILE_ID as ICF_PROFILE_ID,
)
from policy_atlas.implementation_context_records import (
    SCHEMA_VERSION as ICF_SCHEMA_VERSION,
)
from policy_atlas.implementation_context_records import (
    ICFRecord,
    ICFRecordWire,
)
from policy_atlas.openai_client import CallBudget
from policy_atlas.quote_verify import (
    FIELD_RULES_VERSION,
    ICF_FIELD_RULES_VERSION,
    QUOTE_VERIFIER_VERSION,
    QuoteMatch,
    QuoteMatcher,
    build_basis,
    claim_key,
    dedup_icf_records,
    dedup_records,
    icf_claim_key,
    validate_icf_record,
    validate_record,
)
from policy_atlas.schema import (
    MEMO_STATUSES,
    chunk,
    extraction_result,
    implementation_context_finding,
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
KNOWN_PROFILE_IDS = (PROFILE_ID, ICF_PROFILE_ID)

# 018 C5 finding vetter: component.completed payload record cap (flag-not-drop —
# every flagged finding is counted; only the displayed record list is capped).
VETTED_OUT_RECORDS_CAP = 50


@dataclass(frozen=True)
class ExtractionProfileBundle:
    """Concrete extraction profile wiring for the shared document pipeline.

    The two instances in this module are deliberately plain data, not a
    registry. Each bundle carries every profile-specific seam: fingerprint,
    backend, validation/dedup, table writer and optional vetter.
    """

    profile_id: str
    fingerprint: Callable[[str, bool], tuple[str, dict[str, Any]]]
    backend: Any
    wire_record_model: type[Any]
    validate_record: Callable[..., Any]
    dedup_records: Callable[..., tuple[list[Any], int]]
    claim_key: Callable[..., tuple[object, ...]]
    write_finding: Callable[..., None]
    vetter_backend: Any | None
    validate_vetter_coverage: Callable[..., None]
    judge_payload_entry: Callable[..., dict[str, Any]]
    vetted_out_record: Callable[..., dict[str, Any]]


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


def _digest(components: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Canonical sha256 digest of a fingerprint component map, paired back with it."""
    canonical = json.dumps(components, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return digest, components


def extraction_fingerprint(
    mode: str, *, finding_vetter_active: bool = False
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
        finding_vetter_active: Whether a finding-vetter backend was supplied. Vetted
            and unvetted runs never reuse each other's records (018 C5).

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
        "finding_vetter": (
            {
                "prompt": FINDING_VETTER_PROMPT_VERSION,
                "model": FINDING_VETTER_MODEL,
                "reasoning_effort": FINDING_VETTER_REASONING_EFFORT,
                "max_output_tokens": FINDING_VETTER_MAX_OUTPUT_TOKENS,
            }
            if finding_vetter_active
            else None
        ),
    }
    return _digest(components)


def icf_extraction_fingerprint(
    mode: str, *, finding_vetter_active: bool = False
) -> tuple[str, dict[str, Any]]:
    """Build the ICF extraction fingerprint and canonical component map.

    Args:
        mode: The ICF backend mode (``"live"`` or ``"stub"``).
        finding_vetter_active: Whether the ICF finding-vetter backend was supplied.

    Returns:
        A ``(fingerprint_hex, components)`` pair for the ICF profile only.
    """
    components: dict[str, Any] = {
        "profile": ICF_PROFILE_ID,
        "schema": ICF_SCHEMA_VERSION,
        "prompt": ICF_PROMPT_VERSION,
        "model": ICF_EXTRACTION_MODEL,
        "mode": mode,
        "field_rules": ICF_FIELD_RULES_VERSION,
        "verifier": QUOTE_VERIFIER_VERSION,
        "window": {
            "char_budget": WINDOW_CHAR_BUDGET,
            "overlap": WINDOW_OVERLAP_CHUNKS,
            "oversize_policy": OVERSIZE_POLICY,
            "oversize_overlap": OVERSIZE_SUBSEGMENT_OVERLAP,
        },
        "max_output_tokens": ICF_EXTRACT_MAX_OUTPUT_TOKENS,
        "retry_cap": EXTRACT_RETRY_CAP,
        "finding_vetter": (
            {
                "prompt": ICF_FINDING_VETTER_PROMPT_VERSION,
                "model": ICF_FINDING_VETTER_MODEL,
                "reasoning_effort": ICF_FINDING_VETTER_REASONING_EFFORT,
                "max_output_tokens": ICF_FINDING_VETTER_MAX_OUTPUT_TOKENS,
            }
            if finding_vetter_active
            else None
        ),
    }
    return _digest(components)


_ExtractCallBudget = CallBudget


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
    sent_evidence_type: str | None = None

    # Fresh-run payloads / counters.
    survivors: list[Any] = field(default_factory=list)
    groundings: list[list[dict[str, Any]]] = field(default_factory=list)
    coverage_by_survivor: list[dict[str, str]] = field(default_factory=list)
    invalid_dropped: int = 0
    dedup_collapsed: int = 0
    quote_unverified: int = 0

    # Finding vetter (018 C5) — flag-not-drop accounting for this document.
    vetted_out_count: int = 0
    vetted_out_records: list[dict[str, Any]] = field(default_factory=list)
    vetting_failed: bool = False

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


def _scrub_findings(findings: list[Any], wire_record_model: type[Any]) -> list[Any]:
    """Strip NUL characters from every string in the wire records.

    Model output is untrusted data; Postgres rejects ``\\u0000`` in TEXT and
    JSONB, so an emitted NUL would abort the whole write transaction (observed
    on the first live run). Scrubbed at the backend boundary, before
    validation/verification, like any other encoding hygiene.
    """
    return [
        wire_record_model.model_validate(_scrub_nul(record.model_dump()))
        for record in findings
    ]


def _run_windows(
    docs: list[_Doc],
    *,
    profile: ExtractionProfileBundle,
) -> tuple[
    dict[int, dict[int, list[Any]]],
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
    extraction_backend = profile.backend
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

    results: dict[tuple[int, int], list[Any]] = {}
    errors: dict[tuple[int, int], Exception] = {}
    usage_totals = UsageAccumulator()

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_EXTRACT) as executor:
        submitted: list[tuple[tuple[int, int], Future[Any]]] = []
        for key in tasks:
            if not budget.reserve():  # unreachable by construction; fail closed
                errors[key] = RuntimeError("call budget exhausted")
                continue
            doc_index, _ = key
            payload = payloads[key]
            docs[doc_index].sent_evidence_type = (
                payload.primary_evidence_type or UNCLASSIFIED_EVIDENCE_TYPE
            )
            submitted.append((
                key,
                tracing.submit_with_context(
                    executor, extraction_backend.extract, payload
                ),
            ))
        wait([future for _, future in submitted])
        for key, future in submitted:
            try:
                response, usage = future.result()
                results[key] = _scrub_findings(
                    list(response.findings), profile.wire_record_model
                )
                usage_totals.add(usage)
            except Exception as exc:  # noqa: BLE001 — reduced to a type name for the record
                errors[key] = exc

    retry_count = 0
    for key in list(errors):
        if not budget.reserve():
            continue
        retry_count += 1
        doc_index, _ = key
        payload = payloads[key]
        docs[doc_index].sent_evidence_type = (
            payload.primary_evidence_type or UNCLASSIFIED_EVIDENCE_TYPE
        )
        try:
            response, usage = extraction_backend.extract(payload)
            results[key] = _scrub_findings(
                list(response.findings), profile.wire_record_model
            )
            usage_totals.add(usage)
        except Exception as exc:  # noqa: BLE001
            errors[key] = exc
        else:
            del errors[key]

    per_doc: dict[int, dict[int, list[Any]]] = {}
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


def _process_doc(
    doc: _Doc,
    window_findings: dict[int, list[Any]],
    *,
    profile: ExtractionProfileBundle,
) -> None:
    """Run the within-document pipeline for a document whose windows all succeeded."""
    wire_records: list[Any] = []
    for window_index in sorted(window_findings):
        wire_records.extend(window_findings[window_index])

    if not wire_records:
        doc.status = "no_findings"
        doc.finding_count = 0
        return

    validated = [profile.validate_record(wire) for wire in wire_records]
    doc.invalid_dropped = sum(1 for item in validated if item.grain_invalid)
    valid = [item for item in validated if not item.grain_invalid]
    if not valid:
        doc.status = "extraction_failed"
        doc.error = "invalid_records"
        doc.finding_count = 0
        return

    coverage_by_claim: dict[tuple[object, ...], dict[str, str]] = {}
    stored: list[Any] = []
    for item in valid:
        record = item.record
        stored.append(record)
        key = profile.claim_key(record)
        if key not in coverage_by_claim:
            coverage_by_claim[key] = item.field_coverage

    survivors, collapsed = profile.dedup_records(stored)
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
        coverage_list.append(coverage_by_claim[profile.claim_key(record)])

    doc.status = "extracted"
    doc.finding_count = len(survivors)
    doc.survivors = survivors
    doc.groundings = groundings
    doc.coverage_by_survivor = coverage_list
    doc.quote_unverified = quote_unverified


# --- Finding vetter (018 C5) --------------------------------------------------


@dataclass(frozen=True)
class _FindingVetterJudgment:
    verdicts: list[Any]
    usage: TokenUsage | None


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


def _icf_judge_payload_entry(index: int, record: ICFRecord) -> dict[str, Any]:
    """Build one ICF dedup survivor's id-keyed judge input entry."""
    return {
        "index": index,
        "context_type": record.context_type,
        "claim": record.claim,
        "context_label": record.context_label,
        "intervention": record.intervention,
        "claim_level": record.claim_level,
        "claim_basis": record.claim_basis,
        "quotes": [anchor.quote for anchor in record.anchors],
    }


def _iof_vetted_out_record(record: IOFRecord, verdict: VetterVerdictWire) -> dict[str, Any]:
    """Build the summary record for one IOF finding excluded by the vetter."""
    return {
        "intervention": record.intervention,
        "outcome": record.outcome,
        "flag_class": verdict.flag_class,
        "reason": verdict.reason,
    }


def _icf_vetted_out_record(
    record: ICFRecord, verdict: ICFVetterVerdictWire
) -> dict[str, Any]:
    """Build the summary record for one ICF finding excluded by the vetter."""
    return {
        "context_type": record.context_type,
        "claim": record.claim,
        "intervention": record.intervention,
        "flag_class": verdict.flag_class,
        "reason": verdict.reason,
    }


def _judge_finding_vetter(doc: _Doc, profile: ExtractionProfileBundle) -> _FindingVetterJudgment:
    """Call the finding vetter for one document's dedup survivors.

    Runs AFTER ``dedup_records`` and BEFORE the IOF insert (``doc.survivors``
    etc. are still parent-owned until verdict application). A judge
    call/parse/coverage failure is handled by the submitting thread so one
    failed document cannot affect another document's filtering.

    Args:
        doc: An ``extracted`` document with dedup survivors already resolved.
        profile: The extraction profile bundle carrying the judge seam.

    Returns:
        Covered verdicts plus the judge call's token usage.
    """
    if profile.vetter_backend is None:
        raise RuntimeError("finding vetter backend is not configured")
    findings = [
        profile.judge_payload_entry(index, record)
        for index, record in enumerate(doc.survivors)
    ]
    response, usage = profile.vetter_backend.judge({"findings": findings})
    profile.validate_vetter_coverage(findings, list(response.verdicts))
    return _FindingVetterJudgment(verdicts=list(response.verdicts), usage=usage)


def _apply_finding_vetter_verdicts(
    doc: _Doc, verdicts: list[Any], *, profile: ExtractionProfileBundle
) -> None:
    """Apply covered finding-vetter verdicts to one document in the parent thread."""

    vetted_out_by_index: dict[int, Any] = {
        verdict.finding_index: verdict
        for verdict in verdicts
        if verdict.verdict == "flagged"
    }
    if not vetted_out_by_index:
        return

    kept_survivors: list[IOFRecord] = []
    kept_groundings: list[list[dict[str, Any]]] = []
    kept_coverage: list[dict[str, str]] = []
    for index, (record, grounding, coverage) in enumerate(
        zip(doc.survivors, doc.groundings, doc.coverage_by_survivor, strict=True)
    ):
        verdict = vetted_out_by_index.get(index)
        if verdict is None:
            kept_survivors.append(record)
            kept_groundings.append(grounding)
            kept_coverage.append(coverage)
            continue
        doc.vetted_out_records.append(profile.vetted_out_record(record, verdict))

    doc.vetted_out_count = len(doc.vetted_out_records)
    doc.survivors = kept_survivors
    doc.groundings = kept_groundings
    doc.coverage_by_survivor = kept_coverage
    doc.finding_count = len(kept_survivors)
    if not kept_survivors:
        # Every finding was vetted out: the doc contributes no usable
        # evidence, so its status says so honestly — `vetted_out_count`
        # preserves the distinction from a genuinely-empty extraction.
        doc.status = "no_findings"


def _run_finding_vetters(
    docs: list[_Doc], profile: ExtractionProfileBundle
) -> dict[str, int]:
    """Run finding-vetter calls in parallel and apply verdicts deterministically.

    Args:
        docs: Documents after extraction post-processing.
        profile: The extraction profile bundle carrying the judge seam.

    Returns:
        Aggregated vetter token usage. Usage accumulation stays on the
        submitting thread because ``UsageAccumulator`` is mutable and has no
        internal locking.
    """
    candidates = [
        (doc_index, doc)
        for doc_index, doc in enumerate(docs)
        if doc.extractable and doc.status == "extracted" and doc.survivors
    ]
    usage_totals = UsageAccumulator()
    if not candidates:
        return usage_totals.payload()

    judgments: dict[int, _FindingVetterJudgment] = {}
    errors: dict[int, Exception] = {}
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_EXTRACT) as executor:
        submitted: list[tuple[int, Future[Any]]] = [
            (
                doc_index,
                tracing.submit_with_context(
                    executor, _judge_finding_vetter, doc, profile
                ),
            )
            for doc_index, doc in candidates
        ]
        wait([future for _, future in submitted])
        for doc_index, future in submitted:
            try:
                judgments[doc_index] = future.result()
            except Exception as exc:  # noqa: BLE001 — reduced to a type name for the record
                errors[doc_index] = exc

    for doc_index, doc in candidates:
        error = errors.get(doc_index)
        if error is not None:
            doc.vetting_failed = True
            log.warning(
                "extract.vetting_failed",
                pss_id=str(doc.pss_id),
                error=type(error).__name__,
            )
            continue
        judgment = judgments[doc_index]
        _apply_finding_vetter_verdicts(doc, judgment.verdicts, profile=profile)
        usage_totals.add(judgment.usage)

    return usage_totals.payload()


# --- Writes -----------------------------------------------------------------


def _write_iof_finding(
    conn: Connection,
    project_id: uuid.UUID,
    record_id: uuid.UUID,
    record: IOFRecord,
    grounding: list[dict[str, Any]],
    coverage: dict[str, str],
    created_at: datetime,
) -> None:
    """Write one validated IOF finding."""
    conn.execute(
        intervention_outcome_finding.insert().values(
            finding_id=uuid.uuid4(),
            project_id=project_id,
            extraction_record_id=record_id,
            intervention=record.intervention,
            outcome=record.outcome,
            population=record.population,
            setting=record.setting,
            comparator=record.comparator,
            effect_direction=record.effect_direction,
            estimate_level=record.estimate_level,
            study_design=record.study_design,
            study_geography=record.study_geography,
            stratum_qualifiers=[
                {"type": stratum.type, "value": stratum.value}
                for stratum in record.stratum_qualifiers
            ],
            statistics=record.statistics.model_dump(),
            causality_by_design=record.causality_by_design,
            effect_basis=record.effect_basis,
            is_primary=record.is_primary,
            is_prevalence_only=record.is_prevalence_only,
            field_coverage=coverage,
            grounding=grounding,
            created_at=created_at,
        )
    )


def _write_icf_finding(
    conn: Connection,
    project_id: uuid.UUID,
    record_id: uuid.UUID,
    record: ICFRecord,
    grounding: list[dict[str, Any]],
    coverage: dict[str, str],
    created_at: datetime,
) -> None:
    """Write one validated ICF finding."""
    conn.execute(
        implementation_context_finding.insert().values(
            finding_id=uuid.uuid4(),
            project_id=project_id,
            extraction_record_id=record_id,
            context_type=record.context_type,
            claim=record.claim,
            context_label=record.context_label,
            intervention=record.intervention,
            outcome=record.outcome,
            population=record.population,
            setting=record.setting,
            study_geography=record.study_geography,
            study_design=record.study_design,
            claim_level=record.claim_level,
            claim_basis=record.claim_basis,
            level=record.level,
            resource_requirements=record.resource_requirements,
            workforce_requirements=record.workforce_requirements,
            field_coverage=coverage,
            grounding=grounding,
            created_at=created_at,
        )
    )


def _write_docs(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    fingerprint: str,
    docs: list[_Doc],
    created_at: datetime,
    profile: ExtractionProfileBundle,
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
                primary_evidence_type=doc.sent_evidence_type,
                error=doc.error,
                finding_count=doc.finding_count,
                run_id=run_id,
                created_at=created_at,
            )
        )
        for record, grounding, coverage in zip(
            doc.survivors, doc.groundings, doc.coverage_by_survivor, strict=True
        ):
            profile.write_finding(
                conn,
                project_id,
                record_id,
                record,
                grounding,
                coverage,
                created_at,
            )


# --- Summary / invariants ---------------------------------------------------


def record_ids_by_profile(docs: Sequence[Mapping[str, Any]]) -> dict[str, list[Any]]:
    """Group a roll-up's extraction record ids by profile id.

    The reader for the per-profile ``extraction_result.docs`` shape this module
    writes (``_build_summary``), kept next to the writer so the two cannot
    drift. Entries without a ``profiles`` map are ignored — the roll-up shape
    is per-profile keyed, full stop.

    Args:
        docs: Stored ``extraction_result.docs``.

    Returns:
        Mapping from profile id to extraction record ids in document order.
    """
    grouped: dict[str, list[Any]] = {}
    for doc in docs:
        profiles = doc.get("profiles")
        if not isinstance(profiles, Mapping):
            continue
        for profile_id, block in profiles.items():
            if not isinstance(profile_id, str) or not isinstance(block, Mapping):
                continue
            record_id = block.get("extraction_record_id")
            if record_id is not None:
                grouped.setdefault(profile_id, []).append(record_id)
    return grouped


@dataclass(frozen=True)
class _ProfileRun:
    """Completed extraction pass for one selected profile."""

    profile_id: str
    docs: list[_Doc]
    components: dict[str, Any]
    fingerprint: str
    budget_baseline: int
    budget_maximum: int
    budget_used: int
    retry_count: int
    usage_totals: dict[str, int]
    finding_vetter_active: bool


def _doc_profile_summary(doc: _Doc, *, finding_vetter_active: bool) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "status": doc.status,
        "finding_count": doc.finding_count,
        "reused": doc.reused,
        "error": doc.error,
        "extraction_record_id": str(doc.extraction_record_id),
    }
    if finding_vetter_active:
        summary["vetted_out"] = doc.vetted_out_count
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


def _basis_counts(docs: Sequence[_Doc]) -> dict[str, Any]:
    selected = len(docs)
    full_text = sum(1 for doc in docs if doc.basis == "full_text")
    abstract_only = sum(1 for doc in docs if doc.basis == "abstract_only")
    return {
        "full_text": full_text,
        "abstract_only": abstract_only,
        "shares": {
            "full_text": full_text / selected if selected else 0.0,
            "abstract_only": abstract_only / selected if selected else 0.0,
        },
    }


def _profile_counts(docs: Sequence[_Doc], *, finding_vetter_active: bool) -> dict[str, Any]:
    counts: dict[str, Any] = {
        "extracted": sum(1 for doc in docs if doc.status == "extracted"),
        "no_findings": sum(1 for doc in docs if doc.status == "no_findings"),
        "failed": sum(1 for doc in docs if doc.status == "extraction_failed"),
        "fresh": sum(1 for doc in docs if not doc.reused),
        "reused": sum(1 for doc in docs if doc.reused),
    }
    if finding_vetter_active:
        counts["vetting_failed"] = sum(1 for doc in docs if doc.vetting_failed)

    field_coverage: dict[str, dict[str, int]] = {}
    for doc in docs:
        if doc.reused or doc.status != "extracted":
            continue
        for coverage in doc.coverage_by_survivor:
            for name, marker in coverage.items():
                field_coverage.setdefault(name, {})
                field_coverage[name][marker] = field_coverage[name].get(marker, 0) + 1

    counts["findings"] = {
        "total": sum(doc.finding_count for doc in docs if doc.status == "extracted"),
        "quote_unverified": sum(doc.quote_unverified for doc in docs if not doc.reused),
        "dedup_collapsed": sum(doc.dedup_collapsed for doc in docs if not doc.reused),
        "invalid_dropped": sum(doc.invalid_dropped for doc in docs if not doc.reused),
    }
    counts["field_coverage"] = field_coverage
    return counts


def _profile_vetted_out(
    docs: Sequence[_Doc], *, finding_vetter_active: bool
) -> dict[str, Any] | None:
    if not finding_vetter_active:
        return None
    vetted_out_by_class: dict[str, int] = {}
    vetted_out_records: list[dict[str, Any]] = []
    for doc in docs:
        for record in doc.vetted_out_records:
            flag_class = cast("str", record["flag_class"])
            vetted_out_by_class[flag_class] = vetted_out_by_class.get(flag_class, 0) + 1
            vetted_out_records.append(record)
    vetted_out: dict[str, Any] = {
        "total": len(vetted_out_records),
        "by_class": vetted_out_by_class,
        "records": vetted_out_records[:VETTED_OUT_RECORDS_CAP],
    }
    if len(vetted_out_records) > VETTED_OUT_RECORDS_CAP:
        vetted_out["records_truncated"] = True
    return vetted_out


def _build_summary(
    base_docs: Sequence[_Doc],
    profile_runs: Sequence[_ProfileRun],
    *,
    selection_run_id: uuid.UUID,
) -> dict[str, Any]:
    selected = len(base_docs)
    counts_profiles: dict[str, Any] = {}
    provenance_profiles: dict[str, Any] = {}
    summary_profiles: dict[str, Any] = {}
    flags: list[str] = []
    usage_accumulator = UsageAccumulator()

    if selected == 0:
        flags.append("empty_selection")

    profile_docs_by_id: dict[str, dict[uuid.UUID, _Doc]] = {}
    for run in profile_runs:
        counts = _profile_counts(run.docs, finding_vetter_active=run.finding_vetter_active)
        counts_profiles[run.profile_id] = counts
        if counts["failed"] > 0 and "extraction_failures" not in flags:
            flags.append("extraction_failures")
        if counts.get("vetting_failed", 0) > 0 and "vetting_failed" not in flags:
            flags.append("vetting_failed")

        vetted_out = _profile_vetted_out(
            run.docs, finding_vetter_active=run.finding_vetter_active
        )
        profile_summary: dict[str, Any] = {"usage_totals": run.usage_totals}
        if vetted_out is not None:
            profile_summary["vetted_out"] = vetted_out
            if vetted_out["total"] > 0 and "vetted_out_present" not in flags:
                flags.append("vetted_out_present")
        summary_profiles[run.profile_id] = profile_summary
        profile_docs_by_id[run.profile_id] = {doc.pss_id: doc for doc in run.docs}
        provenance_profiles[run.profile_id] = {
            **run.components,
            "fingerprint": run.fingerprint,
            "call_budget": {
                "baseline": run.budget_baseline,
                "maximum": run.budget_maximum,
                "used": run.budget_used,
            },
            "retry_count": run.retry_count,
        }
        usage_accumulator.add_payload(run.usage_totals)

    docs_summary: list[dict[str, Any]] = []
    for doc in base_docs:
        profiles: dict[str, Any] = {}
        for run in profile_runs:
            profile_doc = profile_docs_by_id[run.profile_id][doc.pss_id]
            profiles[run.profile_id] = _doc_profile_summary(
                profile_doc, finding_vetter_active=run.finding_vetter_active
            )
        docs_summary.append(
            {
                "pss_id": str(doc.pss_id),
                "basis": doc.basis,
                "profiles": profiles,
            }
        )

    return {
        "docs": docs_summary,
        "counts": {
            "selected": selected,
            "basis": _basis_counts(base_docs),
            "profiles": counts_profiles,
        },
        "selection_run_id": str(selection_run_id),
        "flags": flags,
        "provenance": {"profiles": provenance_profiles, "pass_count": 1},
        "profiles": summary_profiles,
        "usage_totals": usage_accumulator.payload(),
    }


def _iof_fingerprint(mode: str, finding_vetter_active: bool) -> tuple[str, dict[str, Any]]:
    return extraction_fingerprint(mode, finding_vetter_active=finding_vetter_active)


def _icf_fingerprint(mode: str, finding_vetter_active: bool) -> tuple[str, dict[str, Any]]:
    return icf_extraction_fingerprint(mode, finding_vetter_active=finding_vetter_active)


def _iof_profile(
    extraction_backend: ExtractionBackend,
    finding_vetter_backend: FindingVetterBackend | None,
) -> ExtractionProfileBundle:
    return ExtractionProfileBundle(
        profile_id=PROFILE_ID,
        fingerprint=_iof_fingerprint,
        backend=extraction_backend,
        wire_record_model=IOFRecordWire,
        validate_record=validate_record,
        dedup_records=dedup_records,
        claim_key=claim_key,
        write_finding=_write_iof_finding,
        vetter_backend=finding_vetter_backend,
        validate_vetter_coverage=validate_verdict_coverage,
        judge_payload_entry=_judge_payload_entry,
        vetted_out_record=_iof_vetted_out_record,
    )


def _icf_profile(
    icf_extraction_backend: Any,
    icf_finding_vetter_backend: ICFFindingVetterBackend | None,
) -> ExtractionProfileBundle:
    return ExtractionProfileBundle(
        profile_id=ICF_PROFILE_ID,
        fingerprint=_icf_fingerprint,
        backend=icf_extraction_backend,
        wire_record_model=ICFRecordWire,
        validate_record=validate_icf_record,
        dedup_records=dedup_icf_records,
        claim_key=icf_claim_key,
        write_finding=_write_icf_finding,
        vetter_backend=icf_finding_vetter_backend,
        validate_vetter_coverage=validate_icf_verdict_coverage,
        judge_payload_entry=_icf_judge_payload_entry,
        vetted_out_record=_icf_vetted_out_record,
    )


def _selected_profiles(
    requested: Sequence[str],
    *,
    extraction_backend: ExtractionBackend,
    finding_vetter_backend: FindingVetterBackend | None,
    icf_extraction_backend: Any,
    icf_finding_vetter_backend: ICFFindingVetterBackend | None,
) -> list[ExtractionProfileBundle]:
    requested_tuple = tuple(requested)
    if not requested_tuple:
        raise ExtractError("at least one extraction profile id must be requested")
    if len(set(requested_tuple)) != len(requested_tuple):
        raise ExtractError("duplicate extraction profile id requested")
    unknown = [profile_id for profile_id in requested_tuple if profile_id not in KNOWN_PROFILE_IDS]
    if unknown:
        raise ExtractError(f"unknown extraction profile id requested: {unknown[0]}")

    bundles = {
        PROFILE_ID: _iof_profile(extraction_backend, finding_vetter_backend),
        ICF_PROFILE_ID: _icf_profile(
            icf_extraction_backend, icf_finding_vetter_backend
        ),
    }
    return [
        bundles[profile_id]
        for profile_id in KNOWN_PROFILE_IDS
        if profile_id in requested_tuple
    ]


def _parse_extraction_directive(raw: Any) -> tuple[str, ...]:
    """Parse the scope-context extraction directive into canonical profile ids.

    Args:
        raw: The ``context["extraction"]`` object, or ``None``.

    Returns:
        Requested profile ids in ``KNOWN_PROFILE_IDS`` order.

    Raises:
        ExtractError: If the directive shape is malformed, names an unknown or
            duplicate profile id, is empty, or omits the required IOF profile.
    """
    if raw is None:
        return (PROFILE_ID,)
    if not isinstance(raw, dict):
        raise ExtractError("extraction directive must be an object")
    if not raw:
        return (PROFILE_ID,)
    if set(raw) != {"profiles"}:
        raise ExtractError("extraction directive must contain exactly ['profiles']")

    profiles_raw = raw["profiles"]
    if not isinstance(profiles_raw, list):
        raise ExtractError("extraction directive profiles must be a list")
    if not profiles_raw:
        raise ExtractError("extraction directive profiles must not be empty")

    requested: set[str] = set()
    for item in profiles_raw:
        if not isinstance(item, str):
            raise ExtractError("extraction directive profile id must be a string")
        if item not in KNOWN_PROFILE_IDS:
            raise ExtractError(
                f"extraction directive profiles contains unknown profile id {item!r}"
            )
        if item in requested:
            raise ExtractError(
                f"extraction directive profiles contains duplicate profile id {item!r}"
            )
        requested.add(item)
    if PROFILE_ID not in requested:
        raise ExtractError(
            f"extraction directive profiles must include {PROFILE_ID!r}; "
            "ICF-only extraction is unsupported"
        )
    return tuple(profile_id for profile_id in KNOWN_PROFILE_IDS if profile_id in requested)


def _clone_doc_for_profile(doc: _Doc) -> _Doc:
    """Clone shared document state into one profile-local outcome object."""
    return _Doc(
        pss_id=doc.pss_id,
        text_basis=doc.text_basis,
        envelope_snapshot_id=doc.envelope_snapshot_id,
        full_text_snapshot_id=doc.full_text_snapshot_id,
        metadata=doc.metadata,
        primary_evidence_type=doc.primary_evidence_type,
        chunks=list(doc.chunks),
        basis=doc.basis,
        basis_snapshot_id=doc.basis_snapshot_id,
        record_snapshot_id=doc.record_snapshot_id,
        original_segments=doc.original_segments,
        window_payloads=list(doc.window_payloads),
        status=doc.status,
        error=doc.error,
    )


def _run_profile(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    base_docs: Sequence[_Doc],
    selected_count: int,
    profile: ExtractionProfileBundle,
    created_at: datetime,
) -> _ProfileRun:
    finding_vetter_active = profile.vetter_backend is not None
    fingerprint, components = profile.fingerprint(
        profile.backend.mode, finding_vetter_active
    )
    docs = [_clone_doc_for_profile(doc) for doc in base_docs]
    _apply_memo(conn, project_id=project_id, fingerprint=fingerprint, docs=docs)

    per_doc, doc_errors, baseline, budget, retry_count, window_usage_totals = _run_windows(
        docs, profile=profile
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
            log.info(
                "extract.doc_failed",
                profile=profile.profile_id,
                pss_id=str(doc.pss_id),
                error=doc.error,
            )
            continue
        _process_doc(doc, per_doc.get(doc_index, {}), profile=profile)
    if profile.vetter_backend is not None:
        usage_accumulator.add_payload(_run_finding_vetters(docs, profile))
    usage_totals = usage_accumulator.payload()

    _assert_invariants(docs, selected_count=selected_count)
    _write_docs(
        conn,
        project_id=project_id,
        run_id=run_id,
        fingerprint=fingerprint,
        docs=docs,
        created_at=created_at,
        profile=profile,
    )
    return _ProfileRun(
        profile_id=profile.profile_id,
        docs=docs,
        components=components,
        fingerprint=fingerprint,
        budget_baseline=baseline,
        budget_maximum=budget.maximum,
        budget_used=budget.used,
        retry_count=retry_count,
        usage_totals=usage_totals,
        finding_vetter_active=finding_vetter_active,
    )


# --- Public entry point -----------------------------------------------------


def extract_scope(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ExtractContext,
    extraction_backend: ExtractionBackend,
    finding_vetter_backend: FindingVetterBackend | None = None,
    icf_extraction_backend: Any | None = None,
    icf_finding_vetter_backend: ICFFindingVetterBackend | None = None,
    profiles: Sequence[str] = (PROFILE_ID,),
) -> dict[str, Any]:
    """Extract findings for one evidence scope's selection.

    Loads the referenced selection row, resolves each document's basis, checks
    the durable memo per selected profile, fans out the windowed extraction
    calls, validates / verifies / dedups emitted records, writes durable
    profile records + findings and finally the run-scoped roll-up.

    Args:
        conn: Open database connection; all writes use its active transaction.
        project_id: Owning project.
        run_id: Run writing the extraction result.
        context: Scope-level extract input (carries the explicit selection run).
        extraction_backend: The IOF extraction seam.
        finding_vetter_backend: Optional IOF post-extract finding vetter.
        icf_extraction_backend: The ICF extraction seam. ``None`` resolves to the
            deterministic ICF stub, preserving no-default-egress behaviour.
        icf_finding_vetter_backend: Optional ICF post-extract finding vetter.
        profiles: Selected extraction profile ids. Profiles run in
            ``KNOWN_PROFILE_IDS`` order regardless of caller order.

    Returns:
        The extraction summary payload for ``component.completed``.

    Raises:
        ExtractError: If the selection row is missing, a profile id is unknown
            or duplicated, a selected pss lacks its snapshot row, or a coverage
            invariant fails.
    """
    profile_bundles = _selected_profiles(
        profiles,
        extraction_backend=extraction_backend,
        finding_vetter_backend=finding_vetter_backend,
        icf_extraction_backend=(
            icf_extraction_backend
            if icf_extraction_backend is not None
            else StubICFExtractionBackend()
        ),
        icf_finding_vetter_backend=icf_finding_vetter_backend,
    )
    selected = _load_selection(
        conn,
        project_id=project_id,
        scope_id=context.scope_id,
        selection_run_id=context.selection_run_id,
    )
    created_at = datetime.now(UTC)

    docs = _load_docs(
        conn,
        project_id=project_id,
        scope_id=context.scope_id,
        selected=selected,
    )
    for doc in docs:
        _resolve_basis(doc)

    profile_runs = [
        _run_profile(
            conn,
            project_id=project_id,
            run_id=run_id,
            base_docs=docs,
            selected_count=len(selected),
            profile=profile,
            created_at=created_at,
        )
        for profile in profile_bundles
    ]
    summary = _build_summary(
        docs,
        profile_runs,
        selection_run_id=context.selection_run_id,
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
    log.info(
        "extract.completed",
        selected=summary["counts"]["selected"],
        profiles=list(summary["counts"]["profiles"].keys()),
        flags=summary["flags"],
    )
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
    conn.execute(
        extraction_result.insert().values(
            extraction_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=run_id,
            selection_run_id=selection_run_id,
            extraction_provenance=summary["provenance"],
            docs=summary["docs"],
            counts=summary["counts"],
            flags=summary["flags"],
            created_at=created_at,
        )
    )
