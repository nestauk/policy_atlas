"""Synthesise component: terminal evidence artefact composition.

This module owns task 013's terminus component. It resolves optional upstream
references, mints the artefact, proposes sections, runs the capped section
agent loop, validates typed claims, judges cited/reasoning claims, performs the
single bounded repair pass, writes the 001 substrate rows and finally writes the
``synthesis_result`` roll-up as the last database statement.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from functools import cached_property
from typing import Any, cast

import structlog
from sqlalchemy import case as sa_case
from sqlalchemy import select as sa_select
from sqlalchemy import update as sa_update
from sqlalchemy.engine import Connection, Engine

from policy_atlas.core.hashing import content_hash
from policy_atlas.core.schema import (
    EVIDENCE_TYPES,
    addressable_unit,
    annotation,
    artefact,
    block,
    characterisation_result,
    evidence_scope,
    extraction_result,
    grouping_result,
    implementation_context_finding,
    intervention_outcome_finding,
    project_source_snapshot,
    runs,
    search_coverage_record,
    selection_result,
    source_appraisal_result,
    source_extraction_record,
    source_snapshot,
    synthesis_result,
)
from policy_atlas.core.schema import chunk as chunk_table
from policy_atlas.core.schema import citation as citation_table
from policy_atlas.core.tags import has_control_character
from policy_atlas.core.usage import UsageAccumulator
from policy_atlas.evidence_base.assess.appraise import SCORE_LABELS
from policy_atlas.evidence_base.assess.screen import effective_screen_rows
from policy_atlas.evidence_base.extract.extract import record_ids_by_profile
from policy_atlas.evidence_base.extract.icf_records import PROFILE_ID as ICF_PROFILE_ID
from policy_atlas.evidence_base.extract.iof_records import PROFILE_ID as IOF_PROFILE_ID
from policy_atlas.evidence_base.extract.quote_verify import BasisText, QuoteMatcher, build_basis
from policy_atlas.evidence_base.synthesis.grounding_judge import (
    ENVELOPE_VERSION,
    JUDGE_MODEL,
    JUDGE_PROMPT_VERSION,
    GroundingJudgeBackend,
    build_envelope,
)
from policy_atlas.evidence_base.synthesis.summary_prompts import (
    SUMMARISER_PROMPT_VERSION,
    SUMMARY_JUDGE_PROMPT_VERSION,
)
from policy_atlas.evidence_base.synthesis.synthesis_backend import (
    FORBIDDEN_SECTION_TITLES,
    KEY_FINDINGS_GAP_MAX,
    KEY_FINDINGS_PROMPT_VERSION,
    NAV_LABEL_MAX,
    SECTION_FOCUS_MAX,
    SECTION_PROMPT_VERSION,
    SECTION_TITLE_PROPOSAL_MAX,
    SECTION_TOOL_SCHEMAS,
    SECTIONS_PROMPT_VERSION,
    SYNTHESIS_MODEL,
    ClaimWire,
    RepairItemWire,
    SectionProposalWire,
    SectionProseWire,
    SectionRepairWire,
    SynthesisBackend,
    _chunk_content_by_id,
)
from policy_atlas.evidence_base.synthesis.synthesis_tools import (
    ARTEFACT_TITLE_MAX,
    GROUP_ID_EXPECTED_FORM,
    REASONING_CLAIMS_MAX,
    RETRIEVAL_UNIT_CAP,
    SCREEN_CONFIDENCE_MAX,
    SCREEN_CONFIDENCE_MIN,
    SECTION_CAP,
    SECTION_TURN_CAP,
    SYNTH_CHUNK_CHAR_BUDGET,
    SYNTH_CHUNK_TOP_K,
    ChunkRetriever,
    MalformedEmissionError,
    PassThroughChunkReranker,
    RetrievalUnitCapError,
    SynthesisDirectiveError,
    ToolExchange,
    build_retrieval_scope,
    build_section_tools,
    chunk_text_basis_case,
    facet_of_group_id,
    gathered_ids,
    is_qualified_group_id,
    make_findings_reader,
    make_lookup_reader,
    parse_synthesis_directive,
    run_section_loop,
)
from policy_atlas.runtime.progress import ProgressEmitter

log = structlog.get_logger()

CLAIM_TYPES: tuple[str, ...] = (
    "finding",
    "chunk",
    "pattern",
    "theme",
    "gap",
    "reasoning",
)
JUDGED_TYPES = {"finding", "chunk", "reasoning"}
ANNOTATION_BY_CLAIM_TYPE = {
    "finding": "citation",
    "chunk": "citation",
    "pattern": "pattern",
    "theme": "theme",
    "gap": "gap",
    "reasoning": "reasoning",
}

# The two new grounded block kinds (ADR 0015 §8). Both are ordinary grounded
# blocks (annotations, citations, judge) distinguished only by section role.
CONCLUSIONS_TITLE = "Conclusions"
KEY_FINDINGS_TITLE = "Key findings"
KEY_FINDINGS_FOCUS = "The report's headline claims."
# Section focus the judge sees for the key-findings pass (envelope v2).
KEY_FINDINGS_SECTION_FOCUS = "key findings"
# The headline evidence claim types the key-findings pass may re-state —
# finding/chunk/pattern plus gap restatements (task 034 S3). Theme and
# reasoning stay out. Intersected with the run's available claim types.
KEY_FINDINGS_CLAIM_TYPES = {"finding", "chunk", "pattern", "gap"}


def _conclusions_focus(intent: str) -> str:
    """Return the code-injected conclusions section focus (ADR 0015 §8).

    Evidence-descriptive by construction — weigh the assembled evidence as a
    whole, never a recommendation or a verdict (EB scope).
    """
    return (
        f"What the evidence amounts to on: {intent}. "
        "Weigh strength, conflict and what remains unanswered — descriptively, "
        "never as a recommendation."
    )


def _spans_overlap(a: tuple[int, int], bound: Sequence[tuple[int, int]]) -> bool:
    """Return True if span ``a`` overlaps any span in ``bound``."""
    return any(a[0] < end and start < a[1] for start, end in bound)


def bind_spans(prose: str, texts: list[str]) -> list[tuple[int, int] | None]:
    """Bind each claim text to a char-offset span into ``prose`` (ADR 0015 §2).

    Ordered-cursor binding: each text is located from the running cursor; a text
    not found forward falls back to the first occurrence NOT overlapping any
    already-bound span. Empty text never binds. Overlapping spans are forbidden
    (fail-closed). By construction ``prose[start:end] == text`` for every bound
    span.

    Args:
        prose: The authored section prose.
        texts: Claim texts to bind, in emission order.

    Returns:
        One span ``(start, end)`` per text, or ``None`` on bind failure.
    """
    spans: list[tuple[int, int] | None] = []
    bound: list[tuple[int, int]] = []
    cursor = 0
    for text in texts:
        if not text:
            spans.append(None)
            continue
        index = prose.find(text, cursor)
        if index == -1:
            # Fall back to any occurrence not overlapping an already-bound span.
            search = 0
            index = -1
            while True:
                candidate = prose.find(text, search)
                if candidate == -1:
                    break
                span_candidate = (candidate, candidate + len(text))
                if not _spans_overlap(span_candidate, bound):
                    index = candidate
                    break
                search = candidate + 1
        if index == -1:
            spans.append(None)
            continue
        span = (index, index + len(text))
        if _spans_overlap(span, bound):
            spans.append(None)
            continue
        spans.append(span)
        bound.append(span)
        cursor = max(cursor, index + len(text))
    return spans


@dataclass(frozen=True)
class SpliceItem:
    """One positioned claim for :func:`splice_and_rebind`.

    ``replacement`` is ``None`` to keep the original prose segment verbatim, or
    a string to splice in its place. ``claim_text`` is the text whose new span
    is recorded (located inside the emitted segment): for a kept segment it is
    the segment itself; for a replacement it is the rewritten claim's text, or
    ``None`` when the segment carries no claim (assertion removed/deleted).
    """

    key: int
    span: tuple[int, int]
    replacement: str | None
    claim_text: str | None


def splice_and_rebind(
    prose: str, items: Sequence[SpliceItem]
) -> tuple[str, dict[int, tuple[int, int] | None]]:
    """Rebuild prose in one pass, recomputing every span by construction.

    Walks all positioned claims ascending by start: inter-claim prose is emitted
    verbatim; a kept claim re-emits its original segment (span recorded); a
    replaced claim emits its ``replacement`` and records the new span by locating
    ``claim_text`` inside it. No delta arithmetic — offsets are recomputed from
    the emitted pieces (ADR 0015 §4).

    Args:
        prose: The original section prose.
        items: Positioned claims (kept + repaired); order-independent input.

    Returns:
        ``(new_prose, new_span_map)`` where ``new_span_map`` maps each item key
        to its new span, or ``None`` when the item carries a claim whose text is
        not a substring of its replacement segment (a repair validation failure).
        Keys for segments carrying no claim are absent.
    """
    ordered = sorted(items, key=lambda item: item.span[0])
    pieces: list[str] = []
    span_map: dict[int, tuple[int, int] | None] = {}
    cursor = 0
    out_len = 0
    for item in ordered:
        start, end = item.span
        inter = prose[cursor:start]
        pieces.append(inter)
        out_len += len(inter)
        if item.replacement is None:
            segment = prose[start:end]
            seg_start = out_len
            pieces.append(segment)
            out_len += len(segment)
            span_map[item.key] = (seg_start, out_len)
        else:
            segment = item.replacement
            seg_base = out_len
            pieces.append(segment)
            out_len += len(segment)
            if item.claim_text is not None and item.claim_text != "":
                rel = segment.find(item.claim_text)
                if rel == -1:
                    span_map[item.key] = None
                else:
                    span_map[item.key] = (
                        seg_base + rel,
                        seg_base + rel + len(item.claim_text),
                    )
        cursor = end
    tail = prose[cursor:]
    pieces.append(tail)
    return "".join(pieces), span_map


@dataclass(frozen=True)
class SynthesiseContext:
    """Scope-level input to synthesise.

    Attributes:
        scope_id: Evidence scope whose evidence base is composed.
        intent: Scope intent used for title derivation, sectioning and seeds.
        context: Scope context JSONB, optionally carrying a synthesis directive.
        characterisation_run_id: Optional explicit characterisation reference.
        selection_run_id: Optional explicit selection reference.
        extraction_run_id: Optional explicit extraction reference.
        grouping_run_id: Optional explicit grouping reference.
    """

    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]
    characterisation_run_id: uuid.UUID | None = None
    selection_run_id: uuid.UUID | None = None
    extraction_run_id: uuid.UUID | None = None
    grouping_run_id: uuid.UUID | None = None


class SynthesiseFailure(Exception):
    """Structural or backend synthesis failure.

    Attributes:
        error: Short reason code/message safe for event-log persistence.
        blocks_written: Block ids already persisted before the failure.
    """

    error: str
    blocks_written: list[str]

    def __init__(self, error: str, *, blocks_written: list[str] | None = None) -> None:
        """Create a synthesis failure.

        Args:
            error: Short reason code/message, never raw provider response bodies.
            blocks_written: Already-persisted block ids, if any.
        """
        super().__init__(error)
        self.error = error
        self.blocks_written = list(blocks_written or [])


@dataclass(frozen=True)
class SectionSpec:
    """Validated section specification."""

    title: str
    focus: str
    group_ids: list[str] = field(default_factory=list)
    # Short contents-list label (task 032 G6). Optional: artefacts produced
    # before that slice carry none, and the client falls back to a shortened
    # title rather than treating absence as an error.
    nav_label: str | None = None
    # Composition role (ADR 0015 §8): "standard" for proposed/directive
    # sections, "conclusions" for the code-injected foot section, "key_findings"
    # for the final key-findings pass. Roll-up only — never a block-table column.
    role: str = "standard"

    def as_seed(self) -> dict[str, Any]:
        """Return the prompt-facing section record."""
        return {"title": self.title, "focus": self.focus, "group_ids": self.group_ids}


@dataclass(frozen=True)
class ResolvedReferences:
    """Resolved upstream references and their source path."""

    characterisation_run_id: uuid.UUID | None
    selection_run_id: uuid.UUID | None
    extraction_run_id: uuid.UUID | None
    grouping_run_id: uuid.UUID | None
    how_resolved: dict[str, str]
    characterisation_row: Mapping[str, Any] | None
    selection_row: Mapping[str, Any] | None
    extraction_row: Mapping[str, Any] | None
    grouping_row: Mapping[str, Any] | None

    def any_resolved(self) -> bool:
        """Return true when any upstream substrate reference resolved."""
        return any(
            value is not None
            for value in (
                self.characterisation_run_id,
                self.selection_run_id,
                self.extraction_run_id,
                self.grouping_run_id,
            )
        )


@dataclass(frozen=True)
class CorpusProfile:
    """Screened-corpus counts and citation metadata."""

    screened_docs: int
    ingested_docs: int
    appraised_docs: int
    appraised_ingested_docs: int
    appraised_pss_ids: set[str]


@dataclass(frozen=True)
class ChunkInfo:
    """One frozen chunk and its owning screened document."""

    chunk_id: str
    pss_id: str
    source_snapshot_id: str
    sequence: int
    content: str
    segmentation_policy: str
    text_basis: str
    origin: str
    appraised: bool


@dataclass(frozen=True)
class FindingInfo:
    """One extracted finding plus the data required for synthesis validation."""

    kind: str
    finding_id: str
    pss_id: str
    source_snapshot_id: str
    record: dict[str, Any]
    grounding: list[dict[str, Any]]
    effect_direction: str | None


@dataclass(frozen=True)
class CoverageRecord:
    """One search coverage row used by gap validation."""

    record_id: str
    backends: Any
    adequacy_verdict: str
    verdict_origin: str


@dataclass(frozen=True)
class SubstrateView:
    """In-memory substrate consumed by pure claim validators."""

    characterisation: dict[str, Any] | None
    selection: dict[str, Any] | None
    extraction: dict[str, Any] | None
    grouping: dict[str, Any] | None
    corpus: CorpusProfile
    coverage_records: dict[str, CoverageRecord]
    chunk_by_id: dict[str, ChunkInfo]
    chunks_by_pss_id: dict[str, list[ChunkInfo]]
    finding_by_id: dict[str, FindingInfo]
    icf_finding_by_id: dict[str, FindingInfo]
    icf_profile_available: bool
    basis_by_snapshot_id: dict[str, BasisText]
    selected_pss_ids: set[str]

    @cached_property
    def characterisation_theme_ids(self) -> set[str]:
        """Return real characterisation theme ids for theme validation."""
        if self.characterisation is None:
            return set()
        raw_themes = self.characterisation.get("themes", [])
        if not isinstance(raw_themes, list):
            return set()
        ids: set[str] = set()
        for theme in raw_themes:
            if not isinstance(theme, dict):
                continue
            raw_id = theme.get("theme_id") or theme.get("id") or theme.get("name")
            if isinstance(raw_id, str) and raw_id:
                ids.add(raw_id)
        return ids

    @cached_property
    def grouping_group_ids(self) -> set[str]:
        """Return real grouping ids from the persisted grouping payload."""
        if self.grouping is None:
            return set()
        ids: set[str] = set()
        for group in _grouping_records(self.grouping):
            ids.add(_required_group_id(group))
        return ids

    @cached_property
    def group_by_id(self) -> dict[str, dict[str, Any]]:
        """Return grouping records keyed by real group id."""
        if self.grouping is None:
            return {}
        result: dict[str, dict[str, Any]] = {}
        for group in _grouping_records(self.grouping):
            result[_required_group_id(group)] = group
        return result

    @property
    def extraction_direction_spread(self) -> dict[str, int]:
        """Compute effect-direction spread over all referenced extraction findings."""
        counts: Counter[str] = Counter()
        for finding in self.finding_by_id.values():
            if finding.effect_direction is not None:
                counts[finding.effect_direction] += 1
        return dict(sorted(counts.items()))

    @property
    def all_finding_by_id(self) -> dict[str, FindingInfo]:
        """Return IOF and ICF findings keyed by finding id."""
        return {**self.finding_by_id, **self.icf_finding_by_id}


@dataclass(frozen=True)
class CitationDraft:
    """Citation row plus annotation-payload metadata."""

    chunk_id: str
    quote: str
    origin: str
    match_status: str
    spans: list[dict[str, Any]]


@dataclass
class ClaimDraft:
    """A validated claim ready for optional judging and persistence."""

    claim_id: str
    claim_index: int
    claim_type: str
    text: str
    annotation_type: str
    payload: dict[str, Any]
    citation_rows: list[CitationDraft] = field(default_factory=list)
    cited_ids: list[str] = field(default_factory=list)
    judge_chunk_ids: set[str] = field(default_factory=set)
    verdict: str | None = None
    weakly_grounded: bool = False
    rationale: str | None = None
    judge_io_ref: str | None = None
    flags: list[str] = field(default_factory=list)
    # The claim's bound char-offset span into the section prose (ADR 0015).
    span: tuple[int, int] | None = None


@dataclass(frozen=True)
class RejectedClaim:
    """A claim rejected by deterministic validation."""

    claim_id: str
    claim_index: int
    claim: ClaimWire
    reason: str
    structural: bool = True
    chunk_quote_failed: bool = False
    # True when the claim's text could not be bound as a span into the prose
    # (mirrors ``chunk_quote_failed``); routes to the repair lane and, when
    # exhausted, counts into ``span_bind_failures``.
    span_bind_failed: bool = False
    # The claim's bound span when it bound but failed a per-type validator
    # (a structural rejection carries its span so repair can splice it).
    span: tuple[int, int] | None = None


@dataclass(frozen=True)
class ClaimValidationBatch:
    """Validated and rejected claims from one pass."""

    drafts: list[ClaimDraft]
    rejected: list[RejectedClaim]


@dataclass
class SectionAccounting:
    """Per-section counters for roll-up provenance and block summaries."""

    tool_call_counts: dict[str, int]
    tool_call_count: int
    gathered_id_hash: str
    turns_used: int
    turn_cap_hit: bool
    repair_taken: bool = False
    repair_count_mismatch: bool = False
    repair_unparseable: bool = False
    chunk_claims_rejected: int = 0
    claims_rejected_structural: int = 0
    gap_claims_degraded: int = 0
    # Span-anchored counters (ADR 0015): claims whose text never bound into the
    # prose (exhausted); judge-flagged unspanned assertions bound into the prose;
    # unspanned excerpts the judge returned that did not bind, split by reason
    # (item 17(ii), first-match precedence): the excerpt overlapped a final
    # claim span, was an exact duplicate of an already-bound excerpt / a stale
    # pre-splice result, or was not locatable in the final prose.
    span_bind_failures: int = 0
    unspanned_assertions: int = 0
    unspanned_overlap_filtered: int = 0
    unspanned_duplicate_stale: int = 0
    unspanned_unlocated: int = 0
    # Tool calls the section loop refused to execute (unknown tool, invalid
    # arguments, per-turn read-batch overflow) — counted so protocol drift is
    # visible next to the successful tool_call_count.
    rejected_tool_calls: int = 0
    # True when the block's final prose was never scanned by the unspanned-
    # assertion judge lane (no judged-type claims, or a splice changed the
    # prose after the last judge call): a zero unspanned count then means
    # "not looked at", not "clean" (ADR 0015 §5 honest-accounting).
    unspanned_lane_skipped: bool = False


def derive_artefact_title(intent: str) -> str:
    """Derive the deterministic artefact title from scope intent.

    Args:
        intent: Scope intent.

    Returns:
        Intent with control characters stripped and a trailing ellipsis when
        truncated to :data:`ARTEFACT_TITLE_MAX`.
    """
    stripped = "".join(ch for ch in intent if not _is_control(ch))
    if len(stripped) <= ARTEFACT_TITLE_MAX:
        return stripped
    return f"{stripped[: ARTEFACT_TITLE_MAX - 1]}…"


def generation_budget_max() -> int:
    """Return the binding maximum generation-call count for this slice.

    Two proposal calls (propose + one bounded repair), one generation lane per
    proposed section (``SECTION_CAP``) plus the code-injected conclusions
    section — which rides above ``SECTION_CAP`` by construction (ADR 0015 §8) —
    each lane being its turns plus judge/repair/rejudge, plus the final
    key-findings pass (one emission plus judge/repair/rejudge).
    """
    return 2 + (SECTION_CAP + 1) * (SECTION_TURN_CAP + 3) + (1 + 3)


def build_ledger(claims: Sequence[ClaimDraft]) -> list[dict[str, Any]]:
    """Build the rolling prior-section ledger (prompt-facing; slimmed).

    Per-record ``cited_ids``/``flags``/a repeated non-citable note are dropped
    (022 rider 18 / F0 § DTO spec): the "ledger is context, never evidence,
    not citable" rule is already stated once at the prompt level
    (``SECTION_SYSTEM_PROMPT``), so repeating it — and carrying fields the
    prompt tells the model never to cite — on every record was pure input
    waste, not information the model needs. The evidence-bearing key-findings
    ledger (:func:`_key_findings_ledger`) is a separate, unslimmed record type.

    Args:
        claims: Persisted claims from prior sections, in write order.

    Returns:
        Slimmed claim records: ``claim_id``, ``claim_type``, ``text`` only.
    """
    return [
        {
            "claim_id": claim.claim_id,
            "claim_type": claim.claim_type,
            "text": claim.text,
        }
        for claim in claims
    ]


def validate_claims(
    claims: Sequence[ClaimWire],
    *,
    substrate: SubstrateView,
    section_index: int,
    section_group_ids: set[str],
    citable_finding_ids: set[str],
    citable_chunk_ids: set[str],
    spans: Sequence[tuple[int, int] | None],
    claim_ids: Sequence[str] | None = None,
    claim_indices: Sequence[int] | None = None,
    available_claim_types: set[str] | None = None,
    reasoning_count_start: int = 0,
    gap_restatement_seeds: Sequence[Mapping[str, Any]] | None = None,
    gap_restatement_count_start: int = 0,
) -> ClaimValidationBatch:
    """Validate emitted claims against an in-memory substrate view.

    Args:
        claims: Raw wire claims from the synthesis backend.
        substrate: In-memory substrate view.
        section_index: Zero-based section index for default claim ids.
        section_group_ids: Group ids assigned to this section.
        citable_finding_ids: Finding ids seeded or returned by this section.
        citable_chunk_ids: Chunk ids returned by this section.
        spans: Bound char-offset spans (one per claim, aligned): ``None`` for a
            claim whose text did not bind into the prose (span-bind failure,
            routed to the repair lane). ADR 0015 §2.
        claim_ids: Optional explicit ids, used for repair replacements.
        claim_indices: Optional original slot indices, used for repair ordering.
        available_claim_types: Optional claim-type gate. When omitted, it is
            computed from the substrate.
        reasoning_count_start: Reasoning claims already accepted for this
            section outside this batch, so the per-section cap binds across
            the initial and repair passes together.
        gap_restatement_seeds: When set (key-findings pass), gap claims must
            re-state a seed gap by matching ``grade`` and ``coverage_base``.
            ``None`` keeps the ordinary section-loop gap validator.
        gap_restatement_count_start: Gap restatements already accepted in
            this section, so the cap binds across the initial and repair
            passes together.

    Returns:
        Validated drafts and rejected claims.
    """
    # `is not None`, not truthiness: an explicitly EMPTY gate (e.g. the
    # key-findings intersection on a thin substrate) must reject, never
    # silently reopen to the full substrate set.
    available = (
        available_claim_types
        if available_claim_types is not None
        else available_claim_types_for_substrate(substrate)
    )
    drafts: list[ClaimDraft] = []
    rejected: list[RejectedClaim] = []
    reasoning_count = reasoning_count_start
    gap_restatement_accepted = gap_restatement_count_start
    for offset, claim in enumerate(claims):
        claim_id = (
            claim_ids[offset]
            if claim_ids is not None and offset < len(claim_ids)
            else f"s{section_index}c{offset}"
        )
        claim_index = (
            claim_indices[offset]
            if claim_indices is not None and offset < len(claim_indices)
            else offset
        )
        span = spans[offset] if offset < len(spans) else None
        if span is None:
            # The claim's text did not bind as a span into the prose — a
            # span-bind failure routes to the repair lane (ADR 0015 §2).
            rejected.append(
                _reject(
                    claim,
                    claim_id=claim_id,
                    claim_index=claim_index,
                    reason="span_not_found",
                    structural=False,
                    span_bind_failed=True,
                )
            )
            continue
        if claim.claim_type == "reasoning":
            reasoning_count += 1
        result = _validate_claim(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            substrate=substrate,
            section_group_ids=section_group_ids,
            citable_finding_ids=citable_finding_ids,
            citable_chunk_ids=citable_chunk_ids,
            reasoning_count=reasoning_count,
            available_claim_types=available,
            gap_restatement_seeds=gap_restatement_seeds,
            gap_restatement_accepted=gap_restatement_accepted,
        )
        if isinstance(result, RejectedClaim):
            # A structural rejection carries its bound span so the repair lane
            # can splice its prose segment in place (ADR 0015 §4).
            rejected.append(replace(result, span=span))
        else:
            result.span = span
            drafts.append(result)
            if result.claim_type == "gap" and gap_restatement_seeds is not None:
                gap_restatement_accepted += 1
    return ClaimValidationBatch(drafts=drafts, rejected=rejected)


def available_claim_types_for_substrate(substrate: SubstrateView) -> set[str]:
    """Return claim types currently gated on by the substrate.

    Args:
        substrate: The run's assembled substrate view.
    """
    claim_types = {"gap", "reasoning"}
    if substrate.extraction is not None:
        claim_types.add("finding")
    if substrate.corpus.appraised_docs > 0:
        claim_types.add("chunk")
    if (
        substrate.characterisation is not None
        or substrate.extraction is not None
        or substrate.grouping is not None
    ):
        claim_types.add("pattern")
    if substrate.characterisation is not None or substrate.grouping is not None:
        claim_types.add("theme")
    return claim_types


def _is_control(ch: str) -> bool:
    return ord(ch) < 32 or ord(ch) == 127


def _json_sha256(value: Any) -> str:
    material = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _group_id(group: Any) -> str | None:
    if not isinstance(group, dict):
        return None
    value = group.get("group_id")
    if not isinstance(value, str) or not value:
        return None
    return value if is_qualified_group_id(value) else None


def _required_group_id(group: Any) -> str:
    group_id = _group_id(group)
    if group_id is None:
        raise SynthesiseFailure(
            f"grouping_group_id_invalid: expected form {GROUP_ID_EXPECTED_FORM}"
        )
    if isinstance(group, dict):
        facet = group.get("facet")
        if isinstance(facet, str) and facet_of_group_id(group_id) != facet:
            raise SynthesiseFailure(
                "grouping_group_id_invalid: group id facet must match its "
                f"payload facet; expected form {GROUP_ID_EXPECTED_FORM}"
            )
    return group_id


def _grouping_records(payload: Any) -> list[dict[str, Any]]:
    """Return grouping records from a flattened summary or facet-keyed payload."""
    if not isinstance(payload, dict):
        return []
    raw_groups = payload.get("groups")
    if isinstance(raw_groups, list):
        return [group for group in raw_groups if isinstance(group, dict)]

    groups: list[dict[str, Any]] = []
    for facet, facet_payload in payload.items():
        if not isinstance(facet, str) or not isinstance(facet_payload, dict):
            continue
        raw_facet_groups = facet_payload.get("groups")
        if not isinstance(raw_facet_groups, list):
            continue
        for group in raw_facet_groups:
            if not isinstance(group, dict):
                continue
            if "facet" in group:
                groups.append(group)
            else:
                groups.append({**group, "facet": facet})
    return groups


def _grouping_facet_payloads(payload: Any) -> list[tuple[str, dict[str, Any]]]:
    """Return ``(facet, payload)`` pairs from the persisted grouping JSON."""
    if not isinstance(payload, dict):
        return []
    pairs: list[tuple[str, dict[str, Any]]] = []
    for facet, facet_payload in payload.items():
        if not isinstance(facet, str) or not isinstance(facet_payload, dict):
            continue
        if isinstance(facet_payload.get("groups"), list):
            pairs.append((facet, facet_payload))
    return pairs


def _selected_pss_ids(selection_row: Mapping[str, Any] | None) -> set[str]:
    if selection_row is None:
        return set()
    selected = selection_row.get("selected")
    if not isinstance(selected, list):
        return set()
    ids: set[str] = set()
    for item in selected:
        if not isinstance(item, dict):
            continue
        pss_id = item.get("pss_id")
        if isinstance(pss_id, str):
            ids.add(pss_id)
    return ids


def _uuid_from_selection_provenance(row: Mapping[str, Any]) -> uuid.UUID:
    provenance = row.get("selection_provenance")
    if not isinstance(provenance, dict):
        raise SynthesiseFailure("selection_provenance_invalid")
    raw = provenance.get("characterisation_run_id")
    if not isinstance(raw, str):
        raise SynthesiseFailure("selection_provenance_invalid")
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise SynthesiseFailure("selection_provenance_invalid") from exc


def _load_result_row(
    conn: Connection,
    table: Any,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    run_id: uuid.UUID,
    name: str,
) -> Mapping[str, Any]:
    row = conn.execute(
        sa_select(table)
        .where(table.c.project_id == project_id)
        .where(table.c.evidence_scope_id == scope_id)
        .where(table.c.run_id == run_id)
    ).mappings().one_or_none()
    if row is None:
        raise SynthesiseFailure(f"missing_referenced_row: {name}")
    return cast("Mapping[str, Any]", row)


def _resolve_references(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    context: SynthesiseContext,
) -> ResolvedReferences:
    grouping_row: Mapping[str, Any] | None = None
    extraction_row: Mapping[str, Any] | None = None
    selection_row: Mapping[str, Any] | None = None
    characterisation_row: Mapping[str, Any] | None = None
    how: dict[str, str] = {}

    grouping_run_id = context.grouping_run_id
    extraction_run_id = context.extraction_run_id
    selection_run_id = context.selection_run_id
    characterisation_run_id = context.characterisation_run_id

    if grouping_run_id is not None:
        grouping_row = _load_result_row(
            conn,
            grouping_result,
            project_id=project_id,
            scope_id=context.scope_id,
            run_id=grouping_run_id,
            name="grouping",
        )
        how["grouping"] = "explicit"
        resolved_extraction = cast("uuid.UUID", grouping_row["extraction_run_id"])
        if extraction_run_id is not None and extraction_run_id != resolved_extraction:
            raise SynthesiseFailure("reference_mismatch: extraction_run_id")
        how["extraction"] = (
            "explicit" if extraction_run_id is not None else "transitive:grouping"
        )
        extraction_run_id = resolved_extraction

    if extraction_run_id is not None:
        extraction_row = _load_result_row(
            conn,
            extraction_result,
            project_id=project_id,
            scope_id=context.scope_id,
            run_id=extraction_run_id,
            name="extraction",
        )
        how.setdefault("extraction", "explicit")
        resolved_selection = cast("uuid.UUID", extraction_row["selection_run_id"])
        if selection_run_id is not None and selection_run_id != resolved_selection:
            raise SynthesiseFailure("reference_mismatch: selection_run_id")
        how["selection"] = (
            "explicit" if selection_run_id is not None else "transitive:extraction"
        )
        selection_run_id = resolved_selection

    if selection_run_id is not None:
        selection_row = _load_result_row(
            conn,
            selection_result,
            project_id=project_id,
            scope_id=context.scope_id,
            run_id=selection_run_id,
            name="selection",
        )
        how.setdefault("selection", "explicit")
        resolved_characterisation = _uuid_from_selection_provenance(selection_row)
        if (
            characterisation_run_id is not None
            and characterisation_run_id != resolved_characterisation
        ):
            raise SynthesiseFailure("reference_mismatch: characterisation_run_id")
        how["characterisation"] = (
            "explicit" if characterisation_run_id is not None else "transitive:selection"
        )
        characterisation_run_id = resolved_characterisation

    if characterisation_run_id is not None:
        characterisation_row = _load_result_row(
            conn,
            characterisation_result,
            project_id=project_id,
            scope_id=context.scope_id,
            run_id=characterisation_run_id,
            name="characterisation",
        )
        how.setdefault("characterisation", "explicit")

    return ResolvedReferences(
        characterisation_run_id=characterisation_run_id,
        selection_run_id=selection_run_id,
        extraction_run_id=extraction_run_id,
        grouping_run_id=grouping_run_id,
        how_resolved=how,
        characterisation_row=characterisation_row,
        selection_row=selection_row,
        extraction_row=extraction_row,
        grouping_row=grouping_row,
    )


def _load_corpus_profile(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
) -> CorpusProfile:
    # Screened-in scope = effective-relevant join via the helper (never a raw
    # status='relevant' join, which would leak in demoted docs and double-count
    # confirmed ones).
    effective = effective_screen_rows()
    relevant_rows = conn.execute(
        sa_select(
            project_source_snapshot.c.project_source_snapshot_id,
            project_source_snapshot.c.full_text_status,
            source_snapshot.c.text_basis,
            source_appraisal_result.c.source_appraisal_result_id,
        )
        .select_from(effective)
        .join(
            project_source_snapshot,
            (
                project_source_snapshot.c.project_source_snapshot_id
                == effective.c.project_source_snapshot_id
            )
            & (project_source_snapshot.c.project_id == effective.c.project_id),
        )
        .join(
            source_snapshot,
            source_snapshot.c.source_snapshot_id
            == project_source_snapshot.c.source_snapshot_id,
        )
        .outerjoin(
            source_appraisal_result,
            (
                source_appraisal_result.c.project_source_snapshot_id
                == project_source_snapshot.c.project_source_snapshot_id
            )
            & (source_appraisal_result.c.project_id == project_id)
            & (source_appraisal_result.c.evidence_scope_id == scope_id),
        )
        .where(effective.c.project_id == project_id)
        .where(effective.c.evidence_scope_id == scope_id)
        .where(effective.c.status == "relevant")
        .order_by(project_source_snapshot.c.project_source_snapshot_id)
    ).fetchall()
    appraised_pss_ids: set[str] = set()
    ingested_docs = 0
    appraised_ingested = 0
    for row in relevant_rows:
        appraised = row.source_appraisal_result_id is not None
        if appraised:
            appraised_pss_ids.add(str(row.project_source_snapshot_id))
        # Text availability, not fetch-pipeline state: full_text_status describes
        # the fetch pipeline only (schema comment) — an uploaded document carries
        # its full text on the envelope snapshot (text_basis='full_text', chunked
        # at upload ingest) and is equally "screened-in ingested".
        if row.full_text_status == "ingested" or row.text_basis == "full_text":
            ingested_docs += 1
            if appraised:
                appraised_ingested += 1
    return CorpusProfile(
        screened_docs=len(relevant_rows),
        ingested_docs=ingested_docs,
        appraised_docs=len(appraised_pss_ids),
        appraised_ingested_docs=appraised_ingested,
        appraised_pss_ids=appraised_pss_ids,
    )


def _load_bases_for_snapshots(
    conn: Connection,
    snapshot_ids: Sequence[uuid.UUID],
    metadata_by_snapshot: Mapping[str, Any],
) -> dict[str, BasisText]:
    """Batch-load basis text for a set of distinct source snapshots.

    Replaces the former one-chunk-query-per-snapshot pattern (013 review N+1
    finding, task 020 C3 rider): every snapshot's chunks are fetched in ONE
    query over the whole distinct-snapshot set, then grouped in Python. A
    chunkless snapshot (abstract-only basis) reads its envelope metadata's
    ``abstract`` from ``metadata_by_snapshot`` — already selected by the
    caller's findings query — so the chunkless fallback costs zero extra
    queries.

    Args:
        conn: Open database connection.
        snapshot_ids: Distinct source snapshot ids to build bases for.
        metadata_by_snapshot: Each snapshot id's envelope ``source_snapshot``
            metadata dict (string-keyed by ``str(snapshot_id)``), for the
            chunkless fallback.

    Returns:
        Mapping from ``str(snapshot_id)`` to its :class:`BasisText`.
    """
    if not snapshot_ids:
        return {}
    chunk_rows = conn.execute(
        sa_select(
            chunk_table.c.source_snapshot_id,
            chunk_table.c.chunk_id,
            chunk_table.c.content,
        )
        .where(chunk_table.c.source_snapshot_id.in_(snapshot_ids))
        .order_by(
            chunk_table.c.source_snapshot_id,
            chunk_table.c.sequence,
            chunk_table.c.chunk_id,
        )
    ).fetchall()
    chunks_by_snapshot: dict[str, list[tuple[str, str]]] = {}
    for row in chunk_rows:
        key = str(row.source_snapshot_id)
        chunks_by_snapshot.setdefault(key, []).append(
            (str(row.chunk_id), cast("str", row.content))
        )
    basis_by_snapshot: dict[str, BasisText] = {}
    for snapshot_id in snapshot_ids:
        key = str(snapshot_id)
        chunks = chunks_by_snapshot.get(key)
        if chunks:
            basis_by_snapshot[key] = build_basis(chunks)
        else:
            metadata = metadata_by_snapshot.get(key)
            abstract = metadata.get("abstract") if isinstance(metadata, dict) else None
            basis_by_snapshot[key] = build_basis(
                [(None, abstract if isinstance(abstract, str) else "")]
            )
    return basis_by_snapshot


def _load_screened_chunks(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    selected_pss_ids: set[str],
    appraised_pss_ids: set[str],
) -> tuple[dict[str, ChunkInfo], dict[str, list[ChunkInfo]], dict[str, BasisText]]:
    # The text-bearing snapshot per document: the fetched full-text snapshot when
    # the fetch pipeline ingested one, else the envelope snapshot acquired for
    # the doc. full_text_status is fetch-pipeline state, never text availability
    # (schema comment).
    text_snapshot_id = sa_case(
        (
            project_source_snapshot.c.full_text_status == "ingested",
            project_source_snapshot.c.full_text_snapshot_id,
        ),
        else_=project_source_snapshot.c.source_snapshot_id,
    )
    chunk_text_basis = chunk_text_basis_case(
        chunk_table.c.source_snapshot_id,
        project_source_snapshot.c.source_snapshot_id,
        source_snapshot.c.text_basis,
    )
    # Screened-in scope = effective-relevant join via the helper (same rule as
    # _load_corpus_profile — a second, previously-missed raw source_screening_
    # result consumer feeding the synthesise chunk lane).
    effective = effective_screen_rows()
    rows = conn.execute(
        sa_select(
            project_source_snapshot.c.project_source_snapshot_id,
            chunk_table.c.chunk_id,
            chunk_table.c.source_snapshot_id,
            chunk_table.c.sequence,
            chunk_table.c.content,
            chunk_table.c.segmentation_policy,
            chunk_text_basis,
        )
        .select_from(effective)
        .join(
            project_source_snapshot,
            (
                project_source_snapshot.c.project_source_snapshot_id
                == effective.c.project_source_snapshot_id
            )
            & (project_source_snapshot.c.project_id == effective.c.project_id),
        )
        .join(
            source_snapshot,
            source_snapshot.c.source_snapshot_id
            == project_source_snapshot.c.source_snapshot_id,
        )
        .join(chunk_table, chunk_table.c.source_snapshot_id == text_snapshot_id)
        .where(effective.c.project_id == project_id)
        .where(effective.c.evidence_scope_id == scope_id)
        .where(effective.c.status == "relevant")
        .order_by(
            project_source_snapshot.c.project_source_snapshot_id,
            chunk_table.c.sequence,
            chunk_table.c.chunk_id,
        )
    ).fetchall()
    chunk_by_id: dict[str, ChunkInfo] = {}
    chunks_by_pss: dict[str, list[ChunkInfo]] = {}
    for row in rows:
        pss_id = str(row.project_source_snapshot_id)
        chunk_id = str(row.chunk_id)
        info = ChunkInfo(
            chunk_id=chunk_id,
            pss_id=pss_id,
            source_snapshot_id=str(row.source_snapshot_id),
            sequence=cast("int", row.sequence),
            content=cast("str", row.content),
            segmentation_policy=cast("str", row.segmentation_policy),
            text_basis=cast("str", row.text_basis),
            origin="selected" if pss_id in selected_pss_ids else "unselected_screened",
            appraised=pss_id in appraised_pss_ids,
        )
        chunk_by_id[chunk_id] = info
        chunks_by_pss.setdefault(pss_id, []).append(info)
    basis_by_snapshot: dict[str, BasisText] = {}
    for chunks in chunks_by_pss.values():
        if not chunks:
            continue
        snapshot_id = chunks[0].source_snapshot_id
        basis_by_snapshot[snapshot_id] = build_basis(
            [(chunk.chunk_id, chunk.content) for chunk in chunks]
        )
    return chunk_by_id, chunks_by_pss, basis_by_snapshot


def _load_coverage_records(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
) -> dict[str, CoverageRecord]:
    rows = conn.execute(
        sa_select(
            search_coverage_record.c.search_coverage_record_id,
            search_coverage_record.c.backends,
            search_coverage_record.c.adequacy_verdict,
            search_coverage_record.c.verdict_origin,
        )
        .where(search_coverage_record.c.project_id == project_id)
        .where(search_coverage_record.c.evidence_scope_id == scope_id)
        .order_by(search_coverage_record.c.search_coverage_record_id)
    ).fetchall()
    return {
        str(row.search_coverage_record_id): CoverageRecord(
            record_id=str(row.search_coverage_record_id),
            backends=row.backends,
            adequacy_verdict=cast("str", row.adequacy_verdict),
            verdict_origin=cast("str", row.verdict_origin),
        )
        for row in rows
    }


def _extraction_profile_ids(extraction_row: Mapping[str, Any] | None) -> set[str]:
    if extraction_row is None:
        return set()
    provenance = extraction_row.get("extraction_provenance")
    if not isinstance(provenance, Mapping):
        raise SynthesiseFailure(
            "corrupt_reference: extraction_result.extraction_provenance must be an object"
        )
    profiles = provenance.get("profiles")
    if not isinstance(profiles, Mapping):
        raise SynthesiseFailure(
            "corrupt_reference: extraction_result.extraction_provenance missing "
            "the profiles map"
        )
    return {key for key in profiles if isinstance(key, str)}


def _relevance_annotations(extraction_row: Mapping[str, Any] | None) -> dict[str, str]:
    """Read this run's B2′ relevance marks from the extraction provenance.

    Run-scoped by design (ADR 0023): relevance is question-relative, so it lives
    in the extraction result's ``extraction_provenance["relevance"]["annotations"]``
    JSONB — never on the finding rows. Returns ``{finding_id: "priority" |
    "normal"}`` (only the two enum values survive), or an empty map when the run
    carried no emphasis / the annotator failed open. Malformed shapes degrade to
    empty rather than raising — the consumer never fabricates a mark.
    """
    if extraction_row is None:
        return {}
    provenance = extraction_row.get("extraction_provenance")
    if not isinstance(provenance, Mapping):
        return {}
    relevance = provenance.get("relevance")
    if not isinstance(relevance, Mapping):
        return {}
    annotations = relevance.get("annotations")
    if not isinstance(annotations, Mapping):
        return {}
    return {
        str(finding_id): mark
        for finding_id, mark in annotations.items()
        if isinstance(finding_id, str) and mark in ("priority", "normal")
    }


def _extraction_record_ids_by_profile(
    extraction_row: Mapping[str, Any] | None,
) -> dict[str, list[uuid.UUID]]:
    if extraction_row is None:
        return {}
    docs = extraction_row.get("docs")
    if not isinstance(docs, list):
        return {}
    mapped_docs = [cast("dict[str, Any]", doc) for doc in docs if isinstance(doc, dict)]
    raw_by_profile = record_ids_by_profile(mapped_docs)
    record_ids: dict[str, list[uuid.UUID]] = {}
    for profile_id, raw_ids in raw_by_profile.items():
        parsed: list[uuid.UUID] = []
        for raw_id in raw_ids:
            if isinstance(raw_id, uuid.UUID):
                parsed.append(raw_id)
            elif isinstance(raw_id, str):
                try:
                    parsed.append(uuid.UUID(raw_id))
                except ValueError:
                    continue
        record_ids[profile_id] = parsed
    return record_ids


def _load_findings(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    extraction_row: Mapping[str, Any] | None,
    relevance_annotations: Mapping[str, str] | None = None,
) -> tuple[dict[str, FindingInfo], dict[str, FindingInfo], bool, dict[str, BasisText]]:
    annotations = relevance_annotations or {}
    profile_ids = _extraction_profile_ids(extraction_row)
    record_ids_by_profile = _extraction_record_ids_by_profile(extraction_row)
    iof_record_ids = record_ids_by_profile.get(IOF_PROFILE_ID, [])
    icf_record_ids = record_ids_by_profile.get(ICF_PROFILE_ID, [])
    iof_rows: Sequence[Any] = []
    if iof_record_ids:
        iof_rows = conn.execute(
            sa_select(
                intervention_outcome_finding.c.finding_id,
                intervention_outcome_finding.c.intervention,
                intervention_outcome_finding.c.outcome,
                intervention_outcome_finding.c.population,
                intervention_outcome_finding.c.setting,
                intervention_outcome_finding.c.comparator,
                intervention_outcome_finding.c.effect_direction,
                intervention_outcome_finding.c.estimate_level,
                intervention_outcome_finding.c.study_design,
                intervention_outcome_finding.c.study_geography,
                intervention_outcome_finding.c.stratum_qualifiers,
                intervention_outcome_finding.c.statistics,
                intervention_outcome_finding.c.causality_by_design,
                intervention_outcome_finding.c.effect_basis,
                intervention_outcome_finding.c.is_primary,
                intervention_outcome_finding.c.field_coverage,
                intervention_outcome_finding.c.grounding,
                source_extraction_record.c.project_source_snapshot_id,
                source_extraction_record.c.source_snapshot_id,
                source_snapshot.c.metadata,
            )
            .select_from(intervention_outcome_finding)
            .join(
                source_extraction_record,
                (
                    source_extraction_record.c.extraction_record_id
                    == intervention_outcome_finding.c.extraction_record_id
                )
                & (source_extraction_record.c.project_id == project_id),
            )
            .join(
                source_snapshot,
                source_snapshot.c.source_snapshot_id
                == source_extraction_record.c.source_snapshot_id,
            )
            .where(intervention_outcome_finding.c.project_id == project_id)
            .where(intervention_outcome_finding.c.extraction_record_id.in_(iof_record_ids))
            .order_by(
                source_extraction_record.c.extraction_record_id,
                intervention_outcome_finding.c.finding_id,
            )
        ).fetchall()
    icf_rows: Sequence[Any] = []
    if icf_record_ids:
        icf_rows = conn.execute(
            sa_select(
                implementation_context_finding.c.finding_id,
                implementation_context_finding.c.context_type,
                implementation_context_finding.c.claim,
                implementation_context_finding.c.intervention,
                implementation_context_finding.c.outcome,
                implementation_context_finding.c.population,
                implementation_context_finding.c.setting,
                implementation_context_finding.c.study_geography,
                implementation_context_finding.c.study_design,
                implementation_context_finding.c.claim_level,
                implementation_context_finding.c.claim_basis,
                implementation_context_finding.c.level,
                implementation_context_finding.c.resource_requirements,
                implementation_context_finding.c.workforce_requirements,
                implementation_context_finding.c.field_coverage,
                implementation_context_finding.c.grounding,
                source_extraction_record.c.project_source_snapshot_id,
                source_extraction_record.c.source_snapshot_id,
                source_snapshot.c.metadata,
            )
            .select_from(implementation_context_finding)
            .join(
                source_extraction_record,
                (
                    source_extraction_record.c.extraction_record_id
                    == implementation_context_finding.c.extraction_record_id
                )
                & (source_extraction_record.c.project_id == project_id),
            )
            .join(
                source_snapshot,
                source_snapshot.c.source_snapshot_id
                == source_extraction_record.c.source_snapshot_id,
            )
            .where(implementation_context_finding.c.project_id == project_id)
            .where(implementation_context_finding.c.extraction_record_id.in_(icf_record_ids))
            .order_by(
                source_extraction_record.c.extraction_record_id,
                implementation_context_finding.c.finding_id,
            )
        ).fetchall()
    findings: dict[str, FindingInfo] = {}
    icf_findings: dict[str, FindingInfo] = {}
    snapshot_ids: list[uuid.UUID] = []
    seen_snapshots: set[str] = set()
    metadata_by_snapshot: dict[str, Any] = {}

    def _remember_snapshot(row: Any) -> tuple[str, str]:
        pss_id = str(row.project_source_snapshot_id)
        metadata = row.metadata if isinstance(row.metadata, dict) else {}
        source_snapshot_id = cast("uuid.UUID", row.source_snapshot_id)
        basis_key = str(source_snapshot_id)
        if basis_key not in seen_snapshots:
            seen_snapshots.add(basis_key)
            snapshot_ids.append(source_snapshot_id)
            metadata_by_snapshot[basis_key] = metadata
        return pss_id, basis_key

    for row in iof_rows:
        pss_id, basis_key = _remember_snapshot(row)
        metadata = row.metadata if isinstance(row.metadata, dict) else {}
        title = metadata.get("title")
        finding_id = str(row.finding_id)
        grounding = row.grounding if isinstance(row.grounding, list) else []
        record = {
            "kind": "iof",
            "finding_id": finding_id,
            "pss_id": pss_id,
            "document_title": title if isinstance(title, str) and title else f"source {pss_id}",
            "intervention": row.intervention,
            "outcome": row.outcome,
            "population": row.population,
            "setting": row.setting,
            "comparator": row.comparator,
            "effect_direction": row.effect_direction,
            "estimate_level": row.estimate_level,
            "study_design": row.study_design,
            "study_geography": row.study_geography,
            "stratum_qualifiers": row.stratum_qualifiers,
            "statistics": row.statistics,
            "causality_by_design": row.causality_by_design,
            "effect_basis": row.effect_basis,
            "is_primary": row.is_primary,
            "field_coverage": row.field_coverage,
        }
        mark = annotations.get(finding_id)
        if mark is not None:
            record["relevance"] = mark
        findings[finding_id] = FindingInfo(
            kind="iof",
            finding_id=finding_id,
            pss_id=pss_id,
            source_snapshot_id=basis_key,
            record=record,
            grounding=cast("list[dict[str, Any]]", grounding),
            effect_direction=cast("str", row.effect_direction),
        )
    for row in icf_rows:
        pss_id, basis_key = _remember_snapshot(row)
        metadata = row.metadata if isinstance(row.metadata, dict) else {}
        title = metadata.get("title")
        finding_id = str(row.finding_id)
        grounding = row.grounding if isinstance(row.grounding, list) else []
        record = {
            "kind": "icf",
            "finding_id": finding_id,
            "pss_id": pss_id,
            "document_title": title if isinstance(title, str) and title else f"source {pss_id}",
            "context_type": row.context_type,
            "claim": row.claim,
            "intervention": row.intervention,
            "outcome": row.outcome,
            "population": row.population,
            "setting": row.setting,
            "study_geography": row.study_geography,
            "study_design": row.study_design,
            "claim_level": row.claim_level,
            "claim_basis": row.claim_basis,
            "level": row.level,
            "resource_requirements": row.resource_requirements,
            "workforce_requirements": row.workforce_requirements,
            "field_coverage": row.field_coverage,
        }
        mark = annotations.get(finding_id)
        if mark is not None:
            record["relevance"] = mark
        icf_findings[finding_id] = FindingInfo(
            kind="icf",
            finding_id=finding_id,
            pss_id=pss_id,
            source_snapshot_id=basis_key,
            record=record,
            grounding=cast("list[dict[str, Any]]", grounding),
            effect_direction=None,
        )
    basis_by_snapshot = _load_bases_for_snapshots(conn, snapshot_ids, metadata_by_snapshot)
    return findings, icf_findings, ICF_PROFILE_ID in profile_ids, basis_by_snapshot


def _characterisation_summary(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    themes_payload = row.get("themes")
    raw_themes = themes_payload.get("themes", []) if isinstance(themes_payload, dict) else []
    themes: list[dict[str, Any]] = []
    if isinstance(raw_themes, list):
        for item in raw_themes:
            if not isinstance(item, dict):
                continue
            members = item.get("member_ids", [])
            if not isinstance(members, list):
                members = []
            theme_id = item.get("theme_id") or item.get("id") or item.get("name")
            themes.append(
                {
                    "theme_id": theme_id,
                    "name": item.get("name"),
                    "description": item.get("description"),
                    "size": item.get("size", len(members)),
                    "member_ids": sorted(str(member) for member in members),
                }
            )
    return {"coverage": row.get("coverage", {}), "themes": themes}


def _selection_summary(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    selected = row.get("selected")
    selected_count = len(selected) if isinstance(selected, list) else 0
    return {
        "strategy": row.get("strategy"),
        "budget": row.get("budget"),
        "selected_count": selected_count,
        "flags": row.get("flags", {}),
    }


def _extraction_summary(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {"counts": row.get("counts", {})}


def _grouping_summary(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    payload = row.get("groups")
    facet_payloads = _grouping_facet_payloads(payload)
    groups: list[dict[str, Any]] = []
    for facet, facet_payload in facet_payloads:
        for item in _grouping_records({facet: facet_payload}):
            group_id = _required_group_id(item)
            members = item.get("member_finding_ids", [])
            if not isinstance(members, list):
                members = []
            groups.append(
                {
                    "group_id": group_id,
                    "facet": item.get("facet", facet),
                    "label": item.get("label"),
                    "description": item.get("description"),
                    "size": item.get("size", len(members)),
                    "direction_spread": item.get("direction_spread", {}),
                    "member_finding_ids": sorted(str(member) for member in members),
                }
            )
    residuals: dict[str, dict[str, Any]] = {}
    for facet, facet_payload in facet_payloads:
        facet_residuals = {"ungrouped": facet_payload.get("ungrouped", {})}
        if "no_value" in facet_payload:
            facet_residuals["no_value"] = facet_payload.get("no_value", {})
        residuals[facet] = facet_residuals
    facets = [facet for facet, _ in facet_payloads]
    raw_counts = row.get("counts")
    facet_counts = {
        facet: raw_counts.get(facet, {})
        for facet in facets
        if isinstance(raw_counts, dict) and isinstance(raw_counts.get(facet), dict)
    }
    raw_flags = row.get("flags")
    facet_status = {
        facet: raw_flags.get(facet, {})
        for facet in facets
        if isinstance(raw_flags, dict) and isinstance(raw_flags.get(facet), dict)
    }
    return {
        "facet": facets[0] if len(facets) == 1 else None,
        "facets": facets,
        "groups": groups,
        "residuals": residuals,
        "counts": facet_counts,
        "facet_status": facet_status,
    }


def _residual_count(residual: Any) -> dict[str, int]:
    """Slim a raw facet residual bucket down to its member count.

    The raw ``ungrouped``/``no_value`` payloads persisted by ``group`` carry
    membership (``finding_ids`` / ``member_finding_ids``) alongside the count
    — prompt-facing residuals carry the count only (022 rider 18).
    """
    if not isinstance(residual, dict):
        return {"count": 0}
    members = residual.get("finding_ids", residual.get("member_finding_ids", []))
    return {"count": len(members) if isinstance(members, list) else 0}


def _characterisation_summary_prompt(
    summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Prompt-facing characterisation summary: themes without membership ids.

    Internal consumers (``SubstrateView.characterisation``) keep the full
    ``_characterisation_summary`` records, ``member_ids`` included — this
    slims only at the seed/prompt boundary (F0 § DTO spec).
    """
    if summary is None:
        return None
    themes = [
        {key: value for key, value in theme.items() if key != "member_ids"}
        for theme in summary.get("themes", [])
        if isinstance(theme, dict)
    ]
    return {**summary, "themes": themes}


def _grouping_summary_prompt(summary: dict[str, Any] | None) -> dict[str, Any] | None:
    """Prompt-facing grouping summary: groups/residuals without membership ids.

    Internal consumers (``SubstrateView.grouping``) keep the full
    ``_grouping_summary`` records, ``member_finding_ids`` included — this
    slims only at the seed/prompt boundary (F0 § DTO spec): prompt-side group
    records carry id/label/description/size/spread, residuals carry counts,
    never membership UUID lists.
    """
    if summary is None:
        return None
    groups = [
        {key: value for key, value in group.items() if key != "member_finding_ids"}
        for group in summary.get("groups", [])
        if isinstance(group, dict)
    ]
    residuals = {
        facet: {
            residual_kind: _residual_count(payload)
            for residual_kind, payload in facet_residuals.items()
        }
        for facet, facet_residuals in summary.get("residuals", {}).items()
        if isinstance(facet_residuals, dict)
    }
    return {**summary, "groups": groups, "residuals": residuals}


def _substrate_summaries(refs: ResolvedReferences, corpus: CorpusProfile) -> dict[str, Any]:
    summaries: dict[str, Any] = {
        "corpus": {
            "screened": corpus.screened_docs,
            "ingested": corpus.ingested_docs,
            "appraised": corpus.appraised_docs,
        }
    }
    char_summary = _characterisation_summary_prompt(
        _characterisation_summary(refs.characterisation_row)
    )
    if char_summary is not None:
        summaries["characterisation"] = char_summary
    selection_summary = _selection_summary(refs.selection_row)
    if selection_summary is not None:
        summaries["selection"] = selection_summary
    extraction_summary = _extraction_summary(refs.extraction_row)
    if extraction_summary is not None:
        summaries["extraction"] = extraction_summary
    grouping_summary = _grouping_summary_prompt(_grouping_summary(refs.grouping_row))
    if grouping_summary is not None:
        summaries["grouping"] = grouping_summary
    return summaries


def _group_doc_ids_by_group_id(
    grouping_summary: dict[str, Any] | None,
    all_findings: Mapping[str, FindingInfo],
) -> dict[str, set[str]]:
    if grouping_summary is None:
        return {}
    resolved: dict[str, set[str]] = {}
    raw_groups = grouping_summary.get("groups", [])
    if not isinstance(raw_groups, list):
        return resolved
    for group in raw_groups:
        if not isinstance(group, dict):
            continue
        group_id = group.get("group_id")
        if not isinstance(group_id, str):
            continue
        docs: set[str] = set()
        members = group.get("member_finding_ids", [])
        if isinstance(members, list):
            for member_id in members:
                if not isinstance(member_id, str):
                    continue
                finding = all_findings.get(member_id)
                if finding is not None:
                    docs.add(finding.pss_id)
        resolved[group_id] = docs
    return resolved


def _validate_sections(
    proposal: SectionProposalWire,
    *,
    grouping_group_ids: set[str] | None,
    section_budget: int | None = None,
) -> tuple[list[SectionSpec], list[str], list[str]]:
    """Validate a section proposal into specs.

    Returns ``(sections, reasons, normalisations)``. Integrity rules reject
    (``reasons`` drive the one bounded repair — instructive sentences, fed
    back verbatim as data, or the repair repeats the mistake). Two live model
    slips are instead **normalised and recorded** (the rev 8 M5
    clamp-over-reject posture — they annotate, they are not evidence-bearing):
    overlong titles/foci truncate to their bound with an ellipsis, and
    group_ids on a run with no grouping are stripped. ``normalisations`` is
    recorded in provenance, never silent.
    """
    reasons: list[str] = []
    normalisations: list[str] = []
    sections = proposal.sections
    section_cap = min(SECTION_CAP, section_budget) if section_budget is not None else SECTION_CAP
    if not 1 <= len(sections) <= section_cap:
        reasons.append(f"section_count_out_of_range: 1..{section_cap}")
    forbidden = {title.casefold() for title in FORBIDDEN_SECTION_TITLES}
    seen_titles: set[str] = set()
    parsed: list[SectionSpec] = []
    for index, section in enumerate(sections):
        title = section.title
        focus = section.focus
        if len(title) > SECTION_TITLE_PROPOSAL_MAX:
            reasons.append(
                f"sections[{index}].title_too_long: title must be "
                f"at most {SECTION_TITLE_PROPOSAL_MAX} characters"
            )
        if len(focus) > SECTION_FOCUS_MAX:
            focus = focus[: SECTION_FOCUS_MAX - 1] + "…"
            normalisations.append(f"sections[{index}].focus_truncated")
        if not title or has_control_character(title):
            reasons.append(
                f"sections[{index}].title_invalid: title must be a non-empty "
                "string with no control characters"
            )
        if title.casefold() in forbidden:
            reasons.append(
                f"sections[{index}].title_forbidden: generic or catch-all "
                "titles are rejected — name the specific aspect of the "
                "question or evidence"
            )
        folded = title.casefold()
        if folded in seen_titles:
            reasons.append(
                f"sections[{index}].title_duplicate: every section title must "
                "be distinct"
            )
        seen_titles.add(folded)
        if not focus or has_control_character(focus):
            reasons.append(
                f"sections[{index}].focus_invalid: focus must be a non-empty "
                "string with no control characters"
            )
        nav_label = section.nav_label
        if nav_label is not None:
            if has_control_character(nav_label) or not nav_label.strip():
                reasons.append(
                    f"sections[{index}].nav_label_invalid: nav_label must be a "
                    "non-empty string with no control characters, or omitted"
                )
            elif len(nav_label) > NAV_LABEL_MAX:
                # Rejected, not clamped: unlike an overlong title this is a
                # navigation label, and a mid-word stub is worse to scan than
                # the shortened title the client would otherwise fall back to.
                reasons.append(
                    f"sections[{index}].nav_label_too_long: nav_label must be "
                    f"at most {NAV_LABEL_MAX} characters"
                )
        group_ids = list(section.group_ids)
        if grouping_group_ids is None and group_ids:
            group_ids = []
            normalisations.append(f"sections[{index}].group_ids_stripped_no_grouping")
        elif grouping_group_ids is not None:
            unknown = sorted(set(group_ids) - grouping_group_ids)
            if unknown:
                reasons.append(
                    f"sections[{index}].group_ids_unknown: {unknown[:5]} are "
                    "not supplied qualified facet group ids — use expected form "
                    f"{GROUP_ID_EXPECTED_FORM}, copy ids exactly from the grouping "
                    "records, or omit group_ids"
                )
        parsed.append(
            SectionSpec(title=title, focus=focus, group_ids=group_ids, nav_label=nav_label)
        )
    return parsed, reasons, normalisations


def _sections_from_directive(sections: list[dict[str, Any]]) -> list[SectionSpec]:
    return [
        SectionSpec(
            title=cast("str", section["title"]),
            focus=cast("str", section["focus"]),
            group_ids=list(cast("list[str]", section.get("group_ids", []))),
            nav_label=cast("str | None", section.get("nav_label")),
        )
        for section in sections
    ]


# --- The pre-synthesise steer surface (022 item 14 / F5, § Steer schemas) ---
#
# Two side-effect-free callables an out-of-band caller uses to steer synthesise
# without a runtime pause (deferred seam): ``propose_synthesis_plan`` reads the
# resolved substrate and returns the proposal + the boostable vocabulary; the
# caller collects the user's response out-of-band and ``compile_synthesis_
# directive`` turns it into the existing fail-closed ``context["synthesis"]``
# directive grammar, which a later ``synthesise_scope`` invocation consumes
# verbatim. Neither mints an artefact nor writes any row.

_STEER_RESPONSE_KEYS = {"sections", "group_ids", "retrieval_boosts"}


def propose_synthesis_plan(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    context: SynthesiseContext,
    synthesis_backend: SynthesisBackend,
    section_budget: int | None = None,
) -> dict[str, Any]:
    """Propose a synthesis plan for a scope without minting anything (022 F5).

    A read-only, side-effect-free entry point for the pre-synthesise steer
    point (contract item 14). Unlike ``synthesise_scope``'s own proposal path —
    which mints the artefact *before* proposing sections — this resolves the
    same upstream substrate references, calls the backend's ``propose_sections``
    seam and reads the persisted grouping payload, minting no artefact and
    writing no row (no ``runs``-table contact beyond the reference reads
    ``_resolve_references`` performs). The out-of-band caller renders the result,
    collects the user's response and later submits it (via
    :func:`compile_synthesis_directive`) on a fresh ``synthesise_scope`` call.

    Args:
        conn: Open read connection; used only for reference/substrate reads.
        project_id: Owning project.
        context: Scope and optional upstream references, exactly as
            ``synthesise_scope`` resolves them (scope id, intent, the four run
            references). The steer surface reuses this bundle so its inputs
            never drift from the run's.
        synthesis_backend: The proposal backend (stub or live) — the same seam
            ``synthesise_scope`` calls.
        section_budget: Optional ordinary-section ceiling from the approved
            plan, applied to this P4 preview as well as execution.

    Returns:
        The § Steer schemas payload: ``proposed_sections`` (raw backend
        proposal, ``title``/``focus``/sorted ``group_ids``), ``available_groups``
        (``group_id``/``facet``/``label``/``size``, sorted by id) read from the
        grouping payload, and ``boostable`` (the directive-boost vocabulary:
        appraisal-tier values, evidence-type values, and the
        ``screen_confidence`` lo/hi bound ranges).

    Raises:
        SynthesiseFailure: If a named reference row is missing or references
            conflict (the same fail-closed resolution ``synthesise_scope`` uses).
    """
    refs = _resolve_references(conn, project_id=project_id, context=context)
    corpus = _load_corpus_profile(conn, project_id=project_id, scope_id=context.scope_id)
    summaries = _substrate_summaries(refs, corpus)

    proposal, _usage = synthesis_backend.propose_sections(
        intent=context.intent, substrate=summaries, section_budget=section_budget
    )
    proposed_sections = [
        {
            "title": section.title,
            "focus": section.focus,
            "group_ids": sorted(section.group_ids),
        }
        for section in proposal.sections
    ]

    grouping_summary = _grouping_summary(refs.grouping_row)
    available_groups: list[dict[str, Any]] = []
    if grouping_summary is not None:
        for group in grouping_summary["groups"]:
            available_groups.append(
                {
                    "group_id": group["group_id"],
                    "facet": group["facet"],
                    "label": group["label"],
                    "size": group["size"],
                }
            )
        available_groups.sort(key=lambda entry: cast("str", entry["group_id"]))

    boostable = {
        # The boost VOCABULARY (advisory), not corpus-present values: an
        # appraisal_tier / evidence_type boost that matches nothing is recorded
        # in unmatched_boosts, never fatal. Appraisal tiers are the 1..5 quality
        # scores (stringified as the directive stores them); evidence types are
        # the closed classification enum.
        "appraisal_tiers": [str(score) for score in sorted(SCORE_LABELS)],
        "evidence_types": sorted(EVIDENCE_TYPES),
        "screen_confidence": {
            "lo_bounds": [SCREEN_CONFIDENCE_MIN, SCREEN_CONFIDENCE_MAX],
            "hi_bounds": [SCREEN_CONFIDENCE_MIN, SCREEN_CONFIDENCE_MAX],
        },
    }

    return {
        "proposed_sections": proposed_sections,
        "available_groups": available_groups,
        "boostable": boostable,
    }


def compile_synthesis_directive(response: Mapping[str, Any]) -> dict[str, Any]:
    """Compile a steer response into the ``context["synthesis"]`` directive (022 F5).

    Deterministic, fail-closed and pure: it maps the out-of-band user response
    ``{"sections": [...], "group_ids": [...], "retrieval_boosts": {...}}`` to the
    *existing* directive grammar ``{"sections": [...], "retrieval_boosts": {...}}``
    and validates the result with the same rules ``parse_synthesis_directive``
    applies — the single source of validation truth, so qualified group-id form,
    screen-confidence bounds, boost enums and section rules cannot drift. The
    top-level ``group_ids`` is the available group-id universe (echoed from
    :func:`propose_synthesis_plan`'s ``available_groups``): each section's
    ``group_ids`` must resolve within it or the compile fails closed. Invalid
    input raises :class:`SynthesisDirectiveError` in the directive-error style;
    nothing is silently dropped. The same input always yields an equal directive
    (``group_ids`` lists are sorted, the one place the grammar leaves ordering
    free; section order — which is meaningful — is preserved).

    Args:
        response: The out-of-band user response object.

    Returns:
        The compiled ``context["synthesis"]`` directive value (assign it under
        the ``"synthesis"`` key of an evidence scope's context).

    Raises:
        SynthesisDirectiveError: If the response is structurally malformed or the
            compiled directive fails ``parse_synthesis_directive``'s rules.
    """
    if not isinstance(response, Mapping):
        raise SynthesisDirectiveError("synthesis steer response must be an object")
    unknown = set(response) - _STEER_RESPONSE_KEYS
    if unknown:
        raise SynthesisDirectiveError(
            f"synthesis steer response has invalid keys: {sorted(unknown)}"
        )

    grouping_group_ids: set[str] | None = None
    if "group_ids" in response:
        raw_universe = response["group_ids"]
        if not isinstance(raw_universe, list):
            raise SynthesisDirectiveError(
                "synthesis steer response group_ids must be a list"
            )
        universe: set[str] = set()
        for value in raw_universe:
            if not isinstance(value, str) or not value:
                raise SynthesisDirectiveError(
                    "synthesis steer response group_ids must contain non-empty strings"
                )
            universe.add(value)
        grouping_group_ids = universe

    directive: dict[str, Any] = {}
    if "sections" in response:
        raw_sections = response["sections"]
        if not isinstance(raw_sections, list):
            raise SynthesisDirectiveError(
                "synthesis steer response sections must be a list"
            )
        sections: list[dict[str, Any]] = []
        for index, raw_section in enumerate(raw_sections):
            if not isinstance(raw_section, Mapping):
                raise SynthesisDirectiveError(
                    f"synthesis steer response sections[{index}] must be an object"
                )
            # Copy verbatim so unknown keys reach parse_synthesis_directive and
            # fail closed (never silently dropped); only group_ids is
            # canonicalised (sorted) — the one ordering-free list.
            section = dict(raw_section)
            if "group_ids" in section and isinstance(section["group_ids"], list):
                section["group_ids"] = sorted(section["group_ids"], key=str)
            sections.append(section)
        directive["sections"] = sections
    if "retrieval_boosts" in response:
        # Verbatim so unknown/invalid boost keys, bounds and enums fail closed
        # in the single validation path below.
        directive["retrieval_boosts"] = response["retrieval_boosts"]

    # The single validation authority: identical rules to synthesise_scope's
    # own directive parse. Raises SynthesisDirectiveError on any violation.
    parse_synthesis_directive(
        {"synthesis": directive}, grouping_group_ids=grouping_group_ids
    )
    return directive


def _walk_path(root: Any, path: Sequence[str]) -> Any:
    current = root
    for segment in path:
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current


def _int_dict(value: Any) -> dict[str, int] | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return {"value": value}
    if not isinstance(value, dict):
        return None
    result: dict[str, int] = {}
    for key, raw_count in value.items():
        if (
            not isinstance(key, str)
            or isinstance(raw_count, bool)
            or not isinstance(raw_count, int)
        ):
            return None
        result[key] = raw_count
    return dict(sorted(result.items()))


def _claim_has_citation_payload(claim: ClaimWire) -> bool:
    return bool(claim.citations or claim.cited_finding_ids)


def _reject(
    claim: ClaimWire,
    *,
    claim_id: str,
    claim_index: int,
    reason: str,
    structural: bool = True,
    chunk_quote_failed: bool = False,
    span_bind_failed: bool = False,
) -> RejectedClaim:
    return RejectedClaim(
        claim_id=claim_id,
        claim_index=claim_index,
        claim=claim,
        reason=reason,
        structural=structural,
        chunk_quote_failed=chunk_quote_failed,
        span_bind_failed=span_bind_failed,
    )


def _base_payload(claim_id: str, claim: ClaimWire) -> dict[str, Any]:
    return {"claim_id": claim_id, "claim_type": claim.claim_type, "text": claim.text}


def _validate_claim(
    claim: ClaimWire,
    *,
    claim_id: str,
    claim_index: int,
    substrate: SubstrateView,
    section_group_ids: set[str],
    citable_finding_ids: set[str],
    citable_chunk_ids: set[str],
    reasoning_count: int,
    available_claim_types: set[str],
    gap_restatement_seeds: Sequence[Mapping[str, Any]] | None = None,
    gap_restatement_accepted: int = 0,
) -> ClaimDraft | RejectedClaim:
    if claim.claim_type not in available_claim_types:
        return _reject(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            reason="substrate_ungated_type",
        )
    if not claim.text:
        return _reject(
            claim, claim_id=claim_id, claim_index=claim_index, reason="empty_text"
        )
    if claim.claim_type == "finding":
        return _validate_finding_claim(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            substrate=substrate,
            citable_finding_ids=citable_finding_ids,
        )
    if claim.claim_type == "chunk":
        return _validate_chunk_claim(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            substrate=substrate,
            citable_chunk_ids=citable_chunk_ids,
        )
    if claim.claim_type == "pattern":
        return _validate_pattern_claim(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            substrate=substrate,
            section_group_ids=section_group_ids,
        )
    if claim.claim_type == "theme":
        return _validate_theme_claim(
            claim, claim_id=claim_id, claim_index=claim_index, substrate=substrate
        )
    if claim.claim_type == "gap":
        return _validate_gap_claim(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            substrate=substrate,
            gap_restatement_seeds=gap_restatement_seeds,
            gap_restatement_accepted=gap_restatement_accepted,
        )
    if claim.claim_type == "reasoning":
        return _validate_reasoning_claim(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            reasoning_count=reasoning_count,
        )
    return _reject(
        claim,
        claim_id=claim_id,
        claim_index=claim_index,
        reason="substrate_ungated_type",
    )


def _spans_to_citations(
    match: Any,
    quote: str,
    substrate: SubstrateView,
    *,
    with_origin: bool,
) -> tuple[list[dict[str, Any]], list[CitationDraft], set[str]]:
    """Turn verified quote spans into citation rows, one per spanned chunk.

    Args:
        match: Quote match result with verified spans.
        quote: The verified quote text.
        substrate: In-memory substrate view.
        with_origin: Whether span records carry the spanned chunk's origin.

    Returns:
        Span records, citation drafts and the spanned chunk ids.
    """
    span_records: list[dict[str, Any]] = []
    citation_rows: list[CitationDraft] = []
    chunk_ids: set[str] = set()
    for span in match.spans:
        if span.chunk_id is None:
            continue
        spanned_chunk = substrate.chunk_by_id.get(span.chunk_id)
        if spanned_chunk is None:
            continue
        chunk_ids.add(span.chunk_id)
        record: dict[str, Any] = {
            "chunk_id": span.chunk_id,
            "start": span.start,
            "end": span.end,
        }
        if with_origin:
            record["origin"] = spanned_chunk.origin
            record["text_basis"] = spanned_chunk.text_basis
        span_records.append(record)
        citation_rows.append(
            CitationDraft(
                chunk_id=span.chunk_id,
                quote=quote,
                origin=spanned_chunk.origin,
                match_status=match.status,
                spans=[record],
            )
        )
    return span_records, citation_rows, chunk_ids


def _validate_finding_claim(
    claim: ClaimWire,
    *,
    claim_id: str,
    claim_index: int,
    substrate: SubstrateView,
    citable_finding_ids: set[str],
) -> ClaimDraft | RejectedClaim:
    if substrate.extraction is None:
        return _reject(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            reason="substrate_ungated_type",
        )
    if not claim.cited_finding_ids:
        return _reject(
            claim, claim_id=claim_id, claim_index=claim_index, reason="finding_uncited"
        )
    if (
        claim.citations
        or claim.pattern is not None
        or claim.theme is not None
        or claim.gap is not None
    ):
        return _reject(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            reason="finding_payload_invalid",
        )
    missing = sorted(set(claim.cited_finding_ids) - citable_finding_ids)
    if missing:
        return _reject(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            reason="uncited_finding_id",
        )
    payload = _base_payload(claim_id, claim)
    payload["cited_finding_ids"] = list(claim.cited_finding_ids)
    all_findings = substrate.all_finding_by_id
    cited_kinds: list[str] = []
    anchors_payload: list[dict[str, Any]] = []
    citation_rows: list[CitationDraft] = []
    judge_chunk_ids: set[str] = set()
    flags: list[str] = []
    for finding_id in claim.cited_finding_ids:
        finding = all_findings.get(finding_id)
        if finding is None:
            return _reject(
                claim,
                claim_id=claim_id,
                claim_index=claim_index,
                reason="unknown_finding_id",
            )
        cited_kinds.append(finding.kind)
        basis = substrate.basis_by_snapshot_id.get(finding.source_snapshot_id)
        if basis is None:
            return _reject(
                claim,
                claim_id=claim_id,
                claim_index=claim_index,
                reason="finding_basis_missing",
            )
        matcher = QuoteMatcher(basis)
        if not finding.grounding:
            # An extraction row with no grounding is the extreme anchor
            # failure: nothing to verify, so the claim is weakly grounded.
            flags.append("quote_unverified")
            anchors_payload.append(
                {
                    "finding_id": finding_id,
                    "kind": finding.kind,
                    "quote": None,
                    "match_status": "failed",
                    "spans": [],
                }
            )
        for grounding in finding.grounding:
            quote = grounding.get("quote")
            if not isinstance(quote, str) or not quote:
                flags.append("quote_unverified")
                anchors_payload.append(
                    {
                        "finding_id": finding_id,
                        "kind": finding.kind,
                        "quote": quote,
                        "match_status": "failed",
                        "spans": [],
                    }
                )
                continue
            match = matcher.find(quote)
            spans_payload = [
                {"chunk_id": span.chunk_id, "start": span.start, "end": span.end}
                for span in match.spans
            ]
            anchor_record = {
                "finding_id": finding_id,
                "kind": finding.kind,
                "quote": quote,
                "match_status": match.status,
                "spans": spans_payload,
            }
            if match.status == "failed" or not match.spans:
                flags.append("quote_unverified")
                anchors_payload.append(anchor_record)
                continue
            _, span_rows, span_chunk_ids = _spans_to_citations(
                match, quote, substrate, with_origin=False
            )
            citation_rows.extend(span_rows)
            judge_chunk_ids.update(span_chunk_ids)
            anchors_payload.append(anchor_record)
    payload["cited_finding_kinds"] = cited_kinds
    payload["anchors"] = anchors_payload
    if "quote_unverified" in flags:
        payload["quote_unverified"] = True
    return ClaimDraft(
        claim_id=claim_id,
        claim_index=claim_index,
        claim_type="finding",
        text=claim.text,
        annotation_type="citation",
        payload=payload,
        citation_rows=citation_rows,
        cited_ids=list(claim.cited_finding_ids),
        judge_chunk_ids=judge_chunk_ids,
        weakly_grounded="quote_unverified" in flags,
        flags=sorted(set(flags)),
    )


def _validate_chunk_claim(
    claim: ClaimWire,
    *,
    claim_id: str,
    claim_index: int,
    substrate: SubstrateView,
    citable_chunk_ids: set[str],
) -> ClaimDraft | RejectedClaim:
    if substrate.corpus.appraised_docs <= 0:
        return _reject(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            reason="substrate_ungated_type",
        )
    if not claim.citations:
        return _reject(
            claim, claim_id=claim_id, claim_index=claim_index, reason="chunk_uncited"
        )
    if (
        claim.cited_finding_ids
        or claim.pattern is not None
        or claim.theme is not None
        or claim.gap is not None
    ):
        return _reject(
            claim, claim_id=claim_id, claim_index=claim_index, reason="chunk_payload_invalid"
        )
    payload = _base_payload(claim_id, claim)
    citations_payload: list[dict[str, Any]] = []
    citation_rows: list[CitationDraft] = []
    judge_chunk_ids: set[str] = set()
    cited_ids: list[str] = []
    for citation in claim.citations:
        chunk_id = citation.chunk_record_id
        quote = citation.quote
        if chunk_id not in citable_chunk_ids:
            return _reject(
                claim,
                claim_id=claim_id,
                claim_index=claim_index,
                reason="unreturned_chunk_id",
            )
        chunk = substrate.chunk_by_id.get(chunk_id)
        if chunk is None:
            return _reject(
                claim,
                claim_id=claim_id,
                claim_index=claim_index,
                reason="unknown_chunk_id",
            )
        if not chunk.appraised:
            return _reject(
                claim,
                claim_id=claim_id,
                claim_index=claim_index,
                reason="unappraised_doc_citation",
            )
        if not quote:
            return _reject(
                claim,
                claim_id=claim_id,
                claim_index=claim_index,
                reason="empty_quote",
                chunk_quote_failed=True,
            )
        basis = substrate.basis_by_snapshot_id.get(chunk.source_snapshot_id)
        if basis is None:
            return _reject(
                claim,
                claim_id=claim_id,
                claim_index=claim_index,
                reason="chunk_basis_missing",
            )
        match = QuoteMatcher(basis).find(quote)
        if match.status == "failed" or not match.spans:
            return _reject(
                claim,
                claim_id=claim_id,
                claim_index=claim_index,
                reason="quote_not_found",
                structural=False,
                chunk_quote_failed=True,
            )
        span_records, span_rows, span_chunk_ids = _spans_to_citations(
            match, quote, substrate, with_origin=True
        )
        citation_rows.extend(span_rows)
        judge_chunk_ids.update(span_chunk_ids)
        if not span_records:
            return _reject(
                claim,
                claim_id=claim_id,
                claim_index=claim_index,
                reason="quote_not_found",
                structural=False,
                chunk_quote_failed=True,
            )
        cited_ids.append(chunk_id)
        citations_payload.append(
            {
                "cited_chunk_record_id": chunk_id,
                "quote": quote,
                "match_status": match.status,
                "text_basis": chunk.text_basis,
                "spans": span_records,
            }
        )
    payload["citations"] = citations_payload
    return ClaimDraft(
        claim_id=claim_id,
        claim_index=claim_index,
        claim_type="chunk",
        text=claim.text,
        annotation_type="citation",
        payload=payload,
        citation_rows=citation_rows,
        cited_ids=cited_ids,
        judge_chunk_ids=judge_chunk_ids,
    )


def _validate_pattern_claim(
    claim: ClaimWire,
    *,
    claim_id: str,
    claim_index: int,
    substrate: SubstrateView,
    section_group_ids: set[str],
) -> ClaimDraft | RejectedClaim:
    if _claim_has_citation_payload(claim) or claim.theme is not None or claim.gap is not None:
        return _reject(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            reason="pattern_payload_invalid",
        )
    pattern = claim.pattern
    if pattern is None:
        return _reject(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            reason="content_scan_prohibited",
        )
    computed: dict[str, int] | None = None
    if pattern.computed_from == "characterisation_coverage":
        if substrate.characterisation is None:
            return _reject(
                claim,
                claim_id=claim_id,
                claim_index=claim_index,
                reason="substrate_ungated_type",
            )
        coverage = substrate.characterisation.get("coverage", {})
        computed = _int_dict(_walk_path(coverage, pattern.path))
    elif pattern.computed_from == "group_direction_spread":
        if substrate.grouping is None or pattern.group_id not in section_group_ids:
            return _reject(
                claim,
                claim_id=claim_id,
                claim_index=claim_index,
                reason="pattern_reference_invalid",
            )
        group = substrate.group_by_id.get(pattern.group_id or "")
        computed = _int_dict(group.get("direction_spread") if group else None)
    elif pattern.computed_from == "extraction_direction_spread":
        if substrate.extraction is None:
            return _reject(
                claim,
                claim_id=claim_id,
                claim_index=claim_index,
                reason="substrate_ungated_type",
            )
        computed = substrate.extraction_direction_spread
    elif pattern.computed_from == "icf_context_type_count":
        if substrate.extraction is None or not substrate.icf_profile_available:
            return _reject(
                claim,
                claim_id=claim_id,
                claim_index=claim_index,
                reason="substrate_ungated_type",
            )
        if pattern.group_id is not None:
            if substrate.grouping is None or pattern.group_id not in section_group_ids:
                return _reject(
                    claim,
                    claim_id=claim_id,
                    claim_index=claim_index,
                    reason="pattern_reference_invalid",
                )
            group = substrate.group_by_id.get(pattern.group_id)
            members = group.get("member_finding_ids", []) if group is not None else []
            if not isinstance(members, list):
                members = []
            computed = _icf_context_type_counts(
                substrate.icf_finding_by_id.get(member)
                for member in members
                if isinstance(member, str)
            )
        else:
            computed = _icf_context_type_counts(substrate.icf_finding_by_id.values())
    if computed is None:
        return _reject(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            reason="content_scan_prohibited",
        )
    stated = dict(sorted(pattern.stated.items()))
    if stated != dict(sorted(computed.items())):
        return _reject(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            reason="pattern_mismatch",
        )
    payload = _base_payload(claim_id, claim)
    payload["pattern"] = pattern.model_dump()
    payload["computed"] = computed
    return ClaimDraft(
        claim_id=claim_id,
        claim_index=claim_index,
        claim_type="pattern",
        text=claim.text,
        annotation_type="pattern",
        payload=payload,
    )


def _icf_context_type_counts(findings: Iterable[FindingInfo | None]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for finding in findings:
        if finding is None:
            continue
        context_type = finding.record.get("context_type")
        if isinstance(context_type, str):
            counts[context_type] += 1
    return dict(sorted(counts.items()))


def _validate_theme_claim(
    claim: ClaimWire,
    *,
    claim_id: str,
    claim_index: int,
    substrate: SubstrateView,
) -> ClaimDraft | RejectedClaim:
    if _claim_has_citation_payload(claim) or claim.pattern is not None or claim.gap is not None:
        return _reject(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            reason="theme_payload_invalid",
        )
    theme = claim.theme
    if theme is None or not theme.referenced_ids or not theme.base:
        return _reject(
            claim, claim_id=claim_id, claim_index=claim_index, reason="theme_invalid"
        )
    if theme.source == "characterisation":
        valid_ids = substrate.characterisation_theme_ids
    else:
        valid_ids = substrate.grouping_group_ids
    if not valid_ids:
        return _reject(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            reason="substrate_ungated_type",
        )
    unknown = sorted(set(theme.referenced_ids) - valid_ids)
    if unknown:
        return _reject(
            claim, claim_id=claim_id, claim_index=claim_index, reason="theme_unknown_id"
        )
    payload = _base_payload(claim_id, claim)
    payload["theme"] = theme.model_dump()
    return ClaimDraft(
        claim_id=claim_id,
        claim_index=claim_index,
        claim_type="theme",
        text=claim.text,
        annotation_type="theme",
        payload=payload,
        cited_ids=list(theme.referenced_ids),
    )


def _validate_restated_gap_claim(
    claim: ClaimWire,
    *,
    claim_id: str,
    claim_index: int,
    seeds: Sequence[Mapping[str, Any]],
    accepted_count: int,
) -> ClaimDraft | RejectedClaim:
    """Accept a key-findings gap only as a re-statement of a seed section gap.

    Matches on ``grade`` and ``coverage_base``. The stored payload is copied
    from the seed so the headline cannot forge a coverage record the sections
    did not establish. The cap is deterministic and never forces a gap.
    """
    if _claim_has_citation_payload(claim) or claim.pattern is not None or claim.theme is not None:
        return _reject(
            claim, claim_id=claim_id, claim_index=claim_index, reason="gap_payload_invalid"
        )
    gap = claim.gap
    if gap is None or not gap.coverage_base:
        return _reject(claim, claim_id=claim_id, claim_index=claim_index, reason="gap_invalid")
    if accepted_count >= KEY_FINDINGS_GAP_MAX:
        return _reject(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            reason="gap_restatement_cap",
        )
    match = next(
        (
            seed
            for seed in seeds
            if seed.get("grade") == gap.grade and seed.get("coverage_base") == gap.coverage_base
        ),
        None,
    )
    if match is None:
        return _reject(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            reason="gap_not_restated",
        )
    payload = _base_payload(claim_id, claim)
    payload["gap"] = dict(match)
    return ClaimDraft(
        claim_id=claim_id,
        claim_index=claim_index,
        claim_type="gap",
        text=claim.text,
        annotation_type="gap",
        payload=payload,
        flags=[],
    )


def _validate_gap_claim(
    claim: ClaimWire,
    *,
    claim_id: str,
    claim_index: int,
    substrate: SubstrateView,
    gap_restatement_seeds: Sequence[Mapping[str, Any]] | None = None,
    gap_restatement_accepted: int = 0,
) -> ClaimDraft | RejectedClaim:
    if gap_restatement_seeds is not None:
        return _validate_restated_gap_claim(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            seeds=gap_restatement_seeds,
            accepted_count=gap_restatement_accepted,
        )
    if _claim_has_citation_payload(claim) or claim.pattern is not None or claim.theme is not None:
        return _reject(
            claim, claim_id=claim_id, claim_index=claim_index, reason="gap_payload_invalid"
        )
    gap = claim.gap
    if gap is None or not gap.coverage_base:
        return _reject(
            claim, claim_id=claim_id, claim_index=claim_index, reason="gap_invalid"
        )
    payload = _base_payload(claim_id, claim)
    gap_payload = gap.model_dump()
    flags: list[str] = []
    if gap.grade == "corpus_absence":
        record = (
            substrate.coverage_records.get(gap.coverage_record_id)
            if gap.coverage_record_id is not None
            else None
        )
        if record is None or record.adequacy_verdict == "inadequate":
            gap_payload["original_grade"] = gap_payload["grade"]
            gap_payload["grade"] = "inferred"
            gap_payload["coverage_base"] = "screened"
            gap_payload["degraded"] = True
            gap_payload["degradation_reason"] = (
                "coverage_record_invalid"
                if record is None
                else "coverage_record_inadequate"
            )
            flags.append("gap_degraded")
        else:
            gap_payload["caveat"] = {
                "search_space": record.backends,
                "adequacy_verdict": record.adequacy_verdict,
                "verdict_origin": record.verdict_origin,
            }
    elif gap.grade == "acknowledged_sparsity":
        if substrate.characterisation is None or gap.sparsity is None:
            return _reject(
                claim,
                claim_id=claim_id,
                claim_index=claim_index,
                reason="sparsity_signal_invalid",
            )
        coverage = substrate.characterisation.get("coverage", {})
        resolved = _walk_path(coverage, gap.sparsity.path)
        if (
            isinstance(resolved, bool)
            or not isinstance(resolved, int)
            or resolved != gap.sparsity.stated_count
        ):
            return _reject(
                claim,
                claim_id=claim_id,
                claim_index=claim_index,
                reason="sparsity_mismatch",
            )
    else:
        gap_payload["inferred"] = True
    payload["gap"] = gap_payload
    return ClaimDraft(
        claim_id=claim_id,
        claim_index=claim_index,
        claim_type="gap",
        text=claim.text,
        annotation_type="gap",
        payload=payload,
        flags=flags,
    )


def _validate_reasoning_claim(
    claim: ClaimWire,
    *,
    claim_id: str,
    claim_index: int,
    reasoning_count: int,
) -> ClaimDraft | RejectedClaim:
    if (
        _claim_has_citation_payload(claim)
        or claim.pattern is not None
        or claim.theme is not None
        or claim.gap is not None
    ):
        return _reject(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            reason="reasoning_payload_invalid",
        )
    if reasoning_count > REASONING_CLAIMS_MAX:
        return _reject(
            claim,
            claim_id=claim_id,
            claim_index=claim_index,
            reason="reasoning_over_cap",
        )
    payload = _base_payload(claim_id, claim)
    payload["tier_label"] = "tier_4_reasoning"
    return ClaimDraft(
        claim_id=claim_id,
        claim_index=claim_index,
        claim_type="reasoning",
        text=claim.text,
        annotation_type="reasoning",
        payload=payload,
    )


def _judge_claims(
    *,
    claims: Sequence[ClaimDraft],
    substrate: SubstrateView,
    grounding_judge_backend: GroundingJudgeBackend,
    section_prose: str,
    intent: str = "",
    section_focus: str = "",
    occupied_claims: Sequence[ClaimDraft] | None = None,
) -> tuple[int, dict[str, int], list[dict[str, Any]]]:
    # Verdict coverage is JUDGED_TYPES only (unchanged): finding/chunk take the
    # full lane, reasoning is strict-routed; pattern/theme/gap are validated
    # deterministically and never judged.
    claims_to_judge = [claim for claim in claims if claim.claim_type in JUDGED_TYPES]
    if not claims_to_judge:
        return 0, UsageAccumulator().payload(), []
    # The occupied-span map (item 17(i)) spans EVERY final valid claim, ALL
    # claim types — a pattern/theme/gap claim's prose is legitimately claimed,
    # so the judge must not flag it as unspanned. It is kept separate from the
    # judged set so verdict coverage is unaffected. It defaults to the judged
    # input's own claims (the initial call passes all valid drafts); the
    # re-judge passes the full post-splice claim set (kept + rejudged)
    # explicitly.
    span_source = claims if occupied_claims is None else occupied_claims
    envelope_claims: list[dict[str, Any]] = []
    chunk_ids: set[str] = set()
    for claim in claims_to_judge:
        chunk_ids.update(claim.judge_chunk_ids)
        record = {
            "claim_id": claim.claim_id,
            "claim_type": claim.claim_type,
            "text": claim.text,
            "citations": claim.payload.get("citations", claim.payload.get("anchors", [])),
        }
        if claim.claim_type == "finding":
            record["cited_finding_ids"] = claim.payload.get("cited_finding_ids", [])
        envelope_claims.append(record)
    occupied_claim_spans: list[dict[str, Any]] = [
        {"claim_id": claim.claim_id, "start": claim.span[0], "end": claim.span[1]}
        for claim in span_source
        if claim.span is not None
    ]
    # Envelope chunks, sourced from the substrate's stored chunk data
    # (SubstrateView), de-duped by id. In addition to the chunk claims' cited
    # chunks, each FINDING claim's verified anchors point into chunk records —
    # the judge must see that anchored text, not just the anchor quote
    # (ADR 0015 §8 / B-B3).
    for claim in claims_to_judge:
        if claim.claim_type != "finding":
            continue
        for anchor in claim.payload.get("anchors", []):
            if not isinstance(anchor, dict):
                continue
            for span in anchor.get("spans", []):
                anchored_id = span.get("chunk_id") if isinstance(span, dict) else None
                if isinstance(anchored_id, str):
                    chunk_ids.add(anchored_id)
    chunks = [
        {
            "chunk_record_id": chunk_id,
            "segmentation_policy": substrate.chunk_by_id[chunk_id].segmentation_policy,
            "text_basis": substrate.chunk_by_id[chunk_id].text_basis,
            "content": substrate.chunk_by_id[chunk_id].content,
        }
        for chunk_id in sorted(chunk_ids)
        if chunk_id in substrate.chunk_by_id
    ]
    envelope = build_envelope(
        claims=envelope_claims,
        chunks=chunks,
        section_prose=section_prose,
        span_map=occupied_claim_spans,
        intent=intent,
        section_focus=section_focus,
    )
    response, usage = grounding_judge_backend.judge_block(envelope)
    usage_totals = UsageAccumulator()
    usage_totals.add(usage)
    verdicts = response.verdicts
    expected = {claim.claim_id for claim in claims_to_judge}
    # The all-types span map (022 item 17(i)) shows the judge claim ids it has
    # no verdict duty for; a live judge may echo verdicts for them. Drop and
    # count those — coverage of the judged set itself stays exact.
    span_only_ids = {
        span["claim_id"]
        for span in occupied_claim_spans
        if isinstance(span.get("claim_id"), str)
    } - expected
    extra = [verdict for verdict in verdicts if verdict.claim_id in span_only_ids]
    if extra:
        log.info(
            "synthesise.judge_extra_verdicts_dropped",
            count=len(extra),
            claim_ids=sorted(verdict.claim_id for verdict in extra)[:10],
        )
        verdicts = [verdict for verdict in verdicts if verdict.claim_id not in span_only_ids]
    actual = {verdict.claim_id for verdict in verdicts}
    if expected != actual:
        raise SynthesiseFailure("judge_coverage_invalid")
    by_id = {verdict.claim_id: verdict for verdict in verdicts}
    judge_io_ref = _json_sha256(
        {"envelope": envelope, "verdicts": response.model_dump(mode="json")}
    )
    for claim in claims_to_judge:
        verdict = by_id[claim.claim_id]
        claim.verdict = verdict.verdict
        claim.weakly_grounded = claim.weakly_grounded or verdict.weakly_grounded
        claim.rationale = verdict.rationale
        claim.judge_io_ref = judge_io_ref
    unspanned = [
        {
            "excerpt": assertion.excerpt,
            "rationale": assertion.rationale,
            "judge_io_ref": judge_io_ref,
        }
        for assertion in response.unspanned_assertions
    ]
    return 1, usage_totals.payload(), unspanned


def _span_segment(prose: str, span: tuple[int, int] | None) -> str | None:
    if span is None:
        return None
    return prose[span[0] : span[1]]


def _paragraph_context(
    prose: str, span: tuple[int, int] | None
) -> dict[str, Any] | None:
    if span is None:
        return None
    start, end = span
    paragraph_start = prose.rfind("\n\n", 0, start)
    paragraph_start = 0 if paragraph_start == -1 else paragraph_start + 2
    paragraph_end = prose.find("\n\n", end)
    paragraph_end = len(prose) if paragraph_end == -1 else paragraph_end
    return {
        "start": paragraph_start,
        "end": paragraph_end,
        "text": prose[paragraph_start:paragraph_end],
    }


def _replacement_span(
    prose: str, span: tuple[int, int] | None
) -> dict[str, Any] | None:
    if span is None:
        return None
    return {"start": span[0], "end": span[1], "text": _span_segment(prose, span)}


def _record_id_from(record: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _transcript_records_by_id(
    transcript: Sequence[ToolExchange],
    *,
    tool: str,
    result_keys: Sequence[str],
    id_keys: Sequence[str],
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for exchange in transcript:
        if exchange["tool"] != tool:
            continue
        for result_key in result_keys:
            raw_records = exchange["result"].get(result_key)
            if not isinstance(raw_records, list):
                continue
            for raw_record in raw_records:
                if not isinstance(raw_record, dict) or raw_record.get(
                    "already_returned"
                ) or raw_record.get("skipped_over_budget"):
                    continue
                record_id = _record_id_from(raw_record, *id_keys)
                if record_id is not None:
                    records[record_id] = dict(raw_record)
    return records


def _chunk_dependency_from_info(chunk: ChunkInfo) -> dict[str, Any]:
    return {
        "chunk_record_id": chunk.chunk_id,
        "pss_id": chunk.pss_id,
        "source_snapshot_id": chunk.source_snapshot_id,
        "sequence": chunk.sequence,
        "content": chunk.content,
        "segmentation_policy": chunk.segmentation_policy,
        "text_basis": chunk.text_basis,
        "origin": chunk.origin,
        "appraised": chunk.appraised,
    }


def _chunk_dependencies(
    chunk_ids: Iterable[str],
    *,
    transcript: Sequence[ToolExchange],
    substrate: SubstrateView,
) -> dict[str, dict[str, Any]]:
    transcript_chunks = _transcript_records_by_id(
        transcript,
        tool="search_chunks",
        result_keys=("chunks",),
        id_keys=("chunk_record_id", "id"),
    )
    records: dict[str, dict[str, Any]] = {}
    for chunk_id in sorted(set(chunk_ids)):
        chunk = substrate.chunk_by_id.get(chunk_id)
        if chunk is not None:
            records[chunk_id] = _chunk_dependency_from_info(chunk)
            continue
        transcript_record = transcript_chunks.get(chunk_id)
        if transcript_record is not None:
            records[chunk_id] = transcript_record
    return records


def _finding_dependency_from_info(finding: FindingInfo) -> dict[str, Any]:
    record = dict(finding.record)
    record["source_snapshot_id"] = finding.source_snapshot_id
    record["grounding"] = list(finding.grounding)
    return record


def _finding_dependencies(
    finding_ids: Iterable[str],
    *,
    transcript: Sequence[ToolExchange],
    substrate: SubstrateView,
) -> dict[str, dict[str, Any]]:
    transcript_findings = _transcript_records_by_id(
        transcript,
        tool="query_findings",
        result_keys=("findings", "iof_findings", "icf_findings"),
        id_keys=("finding_id", "id"),
    )
    all_findings = substrate.all_finding_by_id
    records: dict[str, dict[str, Any]] = {}
    for finding_id in sorted(set(finding_ids)):
        finding = all_findings.get(finding_id)
        if finding is not None:
            records[finding_id] = _finding_dependency_from_info(finding)
            continue
        transcript_record = transcript_findings.get(finding_id)
        if transcript_record is not None:
            records[finding_id] = transcript_record
    return records


def _finding_anchor_chunk_ids(
    finding_ids: Iterable[str], substrate: SubstrateView
) -> set[str]:
    chunk_ids: set[str] = set()
    all_findings = substrate.all_finding_by_id
    for finding_id in finding_ids:
        finding = all_findings.get(finding_id)
        if finding is None:
            continue
        basis = substrate.basis_by_snapshot_id.get(finding.source_snapshot_id)
        if basis is None:
            continue
        matcher = QuoteMatcher(basis)
        for grounding in finding.grounding:
            quote = grounding.get("quote")
            if not isinstance(quote, str) or not quote:
                continue
            match = matcher.find(quote)
            for span in match.spans:
                if span.chunk_id is not None:
                    chunk_ids.add(span.chunk_id)
    return chunk_ids


def _coverage_record_dependency(record: CoverageRecord) -> dict[str, Any]:
    return {
        "search_coverage_record_id": record.record_id,
        "backends": record.backends,
        "adequacy_verdict": record.adequacy_verdict,
        "verdict_origin": record.verdict_origin,
    }


def _characterisation_themes_by_id(substrate: SubstrateView) -> dict[str, dict[str, Any]]:
    if substrate.characterisation is None:
        return {}
    themes = substrate.characterisation.get("themes", [])
    if not isinstance(themes, list):
        return {}
    records: dict[str, dict[str, Any]] = {}
    for theme in themes:
        if not isinstance(theme, dict):
            continue
        theme_id = _record_id_from(theme, "theme_id", "id", "name")
        if theme_id is not None:
            records[theme_id] = dict(theme)
    return records


def _computed_key(name: str, *, path: Sequence[str] = (), group_id: str | None = None) -> str:
    if group_id is not None:
        return f"{name}:{group_id}"
    if path:
        return f"{name}:/{'/'.join(path)}"
    return name


def _pattern_dependencies(
    claim: ClaimWire,
    *,
    substrate: SubstrateView,
) -> dict[str, dict[str, Any]]:
    pattern = claim.pattern
    if pattern is None:
        return {}
    records: dict[str, dict[str, Any]] = {}
    if pattern.computed_from == "characterisation_coverage":
        coverage = (
            substrate.characterisation.get("coverage", {})
            if substrate.characterisation
            else {}
        )
        records[
            _computed_key("characterisation_coverage", path=pattern.path)
        ] = {
            "computed_from": pattern.computed_from,
            "path": list(pattern.path),
            "value": _walk_path(coverage, pattern.path),
        }
    elif pattern.computed_from == "group_direction_spread":
        group = substrate.group_by_id.get(pattern.group_id or "")
        if group is not None:
            records[
                _computed_key(
                    "group_direction_spread", group_id=pattern.group_id
                )
            ] = {
                "computed_from": pattern.computed_from,
                "group_id": pattern.group_id,
                "direction_spread": group.get("direction_spread", {}),
            }
    elif pattern.computed_from == "extraction_direction_spread":
        records["extraction_direction_spread"] = {
            "computed_from": pattern.computed_from,
            "direction_spread": substrate.extraction_direction_spread,
        }
    elif pattern.computed_from == "icf_context_type_count":
        if pattern.group_id is not None:
            group = substrate.group_by_id.get(pattern.group_id)
            members = group.get("member_finding_ids", []) if group is not None else []
            if not isinstance(members, list):
                members = []
            counts = _icf_context_type_counts(
                substrate.icf_finding_by_id.get(member)
                for member in members
                if isinstance(member, str)
            )
        else:
            counts = _icf_context_type_counts(substrate.icf_finding_by_id.values())
        records[
            _computed_key("icf_context_type_count", group_id=pattern.group_id)
        ] = {
            "computed_from": pattern.computed_from,
            "group_id": pattern.group_id,
            "counts": counts,
        }
    return records


def _theme_dependencies(claim: ClaimWire, substrate: SubstrateView) -> dict[str, Any]:
    theme = claim.theme
    if theme is None:
        return {}
    if theme.source == "characterisation":
        themes = _characterisation_themes_by_id(substrate)
        return {
            "themes": {
                theme_id: themes[theme_id]
                for theme_id in sorted(set(theme.referenced_ids))
                if theme_id in themes
            }
        }
    groups = substrate.group_by_id
    return {
        "groups": {
            group_id: groups[group_id]
            for group_id in sorted(set(theme.referenced_ids))
            if group_id in groups
        }
    }


def _gap_dependencies(claim: ClaimWire, substrate: SubstrateView) -> dict[str, Any]:
    gap = claim.gap
    if gap is None:
        return {}
    dependencies: dict[str, Any] = {}
    if gap.coverage_record_id is not None:
        record = substrate.coverage_records.get(gap.coverage_record_id)
        if record is not None:
            dependencies["coverage_records"] = {
                gap.coverage_record_id: _coverage_record_dependency(record)
            }
    if gap.sparsity is not None:
        coverage = (
            substrate.characterisation.get("coverage", {})
            if substrate.characterisation
            else {}
        )
        dependencies["computed"] = {
            _computed_key("characterisation_coverage", path=gap.sparsity.path): {
                "computed_from": "characterisation_coverage",
                "path": list(gap.sparsity.path),
                "value": _walk_path(coverage, gap.sparsity.path),
            }
        }
    return dependencies


def _repair_dependency_records(
    claim: ClaimWire,
    *,
    transcript: Sequence[ToolExchange],
    substrate: SubstrateView,
) -> dict[str, Any]:
    dependencies: dict[str, Any] = {}
    if claim.claim_type == "chunk":
        dependencies["chunks"] = _chunk_dependencies(
            (citation.chunk_record_id for citation in claim.citations),
            transcript=transcript,
            substrate=substrate,
        )
    elif claim.claim_type == "finding":
        dependencies["findings"] = _finding_dependencies(
            claim.cited_finding_ids, transcript=transcript, substrate=substrate
        )
        anchor_chunk_ids = _finding_anchor_chunk_ids(claim.cited_finding_ids, substrate)
        dependencies["chunks"] = _chunk_dependencies(
            anchor_chunk_ids, transcript=transcript, substrate=substrate
        )
    elif claim.claim_type == "pattern":
        dependencies["computed"] = _pattern_dependencies(claim, substrate=substrate)
        if claim.pattern is not None and claim.pattern.group_id is not None:
            group = substrate.group_by_id.get(claim.pattern.group_id)
            if group is not None:
                dependencies["groups"] = {claim.pattern.group_id: group}
    elif claim.claim_type == "theme":
        dependencies.update(_theme_dependencies(claim, substrate))
    elif claim.claim_type == "gap":
        dependencies.update(_gap_dependencies(claim, substrate))
    return {
        key: value
        for key, value in sorted(dependencies.items())
        if value not in ({}, [], None)
    }


def _wire_claim_data(raw: Any) -> dict[str, Any]:
    """Project a failing record's claim back onto the strict wire shape.

    Judge-failing claims arrive with ENRICHED citation records (resolved
    ``cited_chunk_record_id``, ``match_status``, ``spans``, ``text_basis``) —
    annotation-shaped, not wire-shaped. The repair call re-validates through
    ``ClaimWire`` (extra=forbid), so strip citations down to the wire fields
    first; everything else passes through untouched.
    """
    if not isinstance(raw, dict):
        return {}
    data = {key: value for key, value in raw.items() if key in ClaimWire.model_fields}
    raw_citations = data.get("citations")
    if isinstance(raw_citations, list):
        citations: list[dict[str, Any]] = []
        for citation in raw_citations:
            if not isinstance(citation, dict):
                continue
            chunk_record_id = citation.get("chunk_record_id") or citation.get(
                "cited_chunk_record_id"
            )
            citations.append(
                {
                    "chunk_record_id": str(chunk_record_id or ""),
                    "quote": str(citation.get("quote") or ""),
                }
            )
        data["citations"] = citations
    return data


def _repair_input_records(
    failing: Sequence[dict[str, Any]],
    *,
    prose: str,
    transcript: Sequence[ToolExchange],
    substrate: SubstrateView,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for record in failing:
        claim = ClaimWire.model_validate(_wire_claim_data(record["claim"]))
        raw_span = record.get("span")
        span: tuple[int, int] | None = None
        if (
            isinstance(raw_span, list)
            and len(raw_span) == 2
            and all(isinstance(item, int) for item in raw_span)
        ):
            span = (raw_span[0], raw_span[1])
        records.append(
            {
                "claim_id": str(record["claim_id"]),
                "claim": claim.model_dump(mode="json"),
                "failure_reason": str(record.get("rationale") or record.get("reason") or ""),
                "replacement_span": _replacement_span(prose, span),
                "paragraph_context": _paragraph_context(prose, span),
                "dependencies": _repair_dependency_records(
                    claim, transcript=transcript, substrate=substrate
                ),
            }
        )
    return records


def _failing_records(
    rejected: Sequence[RejectedClaim],
    drafts: Sequence[ClaimDraft],
    *,
    prose: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for rejection in rejected:
        claim_data = rejection.claim.model_dump(mode="json")
        span = rejection.span
        records.append(
            {
                "claim_id": rejection.claim_id,
                "claim_index": rejection.claim_index,
                "claim": claim_data,
                "reason": rejection.reason,
                "rationale": rejection.reason,
                # Bound span + current prose segment (null when the claim never
                # bound — a span-bind failure), for the prose-splice repair.
                "span": list(span) if span is not None else None,
                "segment": _span_segment(prose, span),
            }
        )
    for draft in drafts:
        if draft.verdict == "unsupported_mis_cited":
            records.append(
                {
                    "claim_id": draft.claim_id,
                    "claim_index": draft.claim_index,
                    "claim": {
                        "claim_type": draft.claim_type,
                        "text": draft.text,
                        **{
                            key: draft.payload[key]
                            for key in ("citations", "cited_finding_ids")
                            if key in draft.payload
                        },
                    },
                    "reason": "unsupported_mis_cited",
                    "rationale": draft.rationale or "unsupported_mis_cited",
                    "span": list(draft.span) if draft.span is not None else None,
                    "segment": _span_segment(prose, draft.span),
                }
            )
    return sorted(records, key=lambda item: (int(item["claim_index"]), str(item["claim_id"])))


def _count_exclusion(rejection: RejectedClaim, *, accounting: SectionAccounting) -> None:
    if rejection.span_bind_failed:
        accounting.span_bind_failures += 1
    elif rejection.chunk_quote_failed:
        accounting.chunk_claims_rejected += 1
    else:
        accounting.claims_rejected_structural += 1


def _count_repair_exclusion(
    index: int,
    rejection_by_index: Mapping[int, RejectedClaim],
    accounting: SectionAccounting,
) -> None:
    """Count a failing claim excluded after its repair produced no valid claim.

    A structural rejection reuses its own exclusion bucket (chunk-quote vs
    generic); an unsupported draft with no rejection record counts generic.
    """
    rejection = rejection_by_index.get(index)
    if rejection is not None:
        _count_exclusion(rejection, accounting=accounting)
    else:
        accounting.claims_rejected_structural += 1


def _bind_into(
    prose: str, text: str, blocked: Sequence[tuple[int, int]]
) -> tuple[int, int] | None:
    """Bind ``text`` to the first occurrence in ``prose`` not overlapping
    any span in ``blocked``; ``None`` on failure. Empty text never binds."""
    if not text:
        return None
    search = 0
    while True:
        index = prose.find(text, search)
        if index == -1:
            return None
        span = (index, index + len(text))
        if not _spans_overlap(span, blocked):
            return span
        search = index + 1


def _finalize_no_repair(
    *,
    initial: ClaimValidationBatch,
    accounting: SectionAccounting,
) -> list[ClaimDraft]:
    """Finalise when no prose splice is applied (no failing, or repair
    exhausted): unsupported drafts persist verbatim, rejections are counted."""
    for rejection in initial.rejected:
        _count_exclusion(rejection, accounting=accounting)
    by_index = {draft.claim_index: draft for draft in initial.drafts}
    return [by_index[index] for index in sorted(by_index)]


def _repair_id_mismatch(
    repairs: Sequence[RepairItemWire], failing: Sequence[dict[str, Any]]
) -> bool:
    failing_ids = {str(record["claim_id"]) for record in failing}
    repair_ids = [repair.claim_id for repair in repairs]
    known_repair_ids = {claim_id for claim_id in repair_ids if claim_id in failing_ids}
    return (
        len(repair_ids) != len(failing_ids)
        or len(set(repair_ids)) != len(repair_ids)
        or known_repair_ids != failing_ids
    )


def _classify_unbound(
    excerpt: str,
    prose: str,
    *,
    claim_spans: Sequence[tuple[int, int]],
    accounting: SectionAccounting,
) -> None:
    """Classify an unspanned excerpt that failed to bind into one of three
    observability counters, by fixed first-match precedence (item 17(ii)).

    An excerpt can qualify for more than one bucket; the order is fixed so the
    counts stay disjoint and comparable across runs:

    1. ``unspanned_overlap_filtered`` — present in the prose but a locatable
       occurrence overlaps a final claim span (the judge over-reported inside
       claimed prose). Checked first, so an overlap-and-duplicate excerpt
       counts here.
    2. ``unspanned_duplicate_stale`` — present in the prose but every
       occurrence is already taken by an earlier-bound excerpt (an exact
       duplicate of an already-bound assertion, or a stale pre-splice result).
    3. ``unspanned_unlocated`` — not locatable in the final prose at all.

    ``claim_spans`` are the final claim spans only (never the bound-excerpt
    spans), so overlap classification measures judge over-report specifically.
    Prose is never modified (ADR 0015 §5); this lane only counts.
    """
    occurrences: list[tuple[int, int]] = []
    if excerpt:
        search = 0
        while True:
            index = prose.find(excerpt, search)
            if index == -1:
                break
            occurrences.append((index, index + len(excerpt)))
            search = index + 1
    if any(_spans_overlap(occ, claim_spans) for occ in occurrences):
        accounting.unspanned_overlap_filtered += 1
    elif occurrences:
        accounting.unspanned_duplicate_stale += 1
    else:
        accounting.unspanned_unlocated += 1


def _bind_unspanned(
    records: Sequence[dict[str, Any]],
    prose: str,
    *,
    accounting: SectionAccounting,
    claim_spans: Sequence[tuple[int, int]] = (),
) -> list[dict[str, Any]]:
    """Bind judge-returned unspanned excerpts into the final prose (flag-not-drop).

    Bound excerpts become addressable-unit + annotation mint records; excerpts
    that fail to bind are classified into the three unspanned counters
    (:func:`_classify_unbound`) and logged. Prose is never modified by this
    lane (ADR 0015 §5). ``claim_spans`` are blocked: an excerpt may not bind
    inside claimed prose — the lane flags text OUTSIDE claim spans by
    definition, so a claim-overlapping excerpt is filtered out rather than
    double-covering claimed text.
    """
    claim_span_list: list[tuple[int, int]] = list(claim_spans)
    blocked: list[tuple[int, int]] = list(claim_spans)
    minted: list[dict[str, Any]] = []
    for record in records:
        excerpt = str(record["excerpt"])
        span = _bind_into(prose, excerpt, blocked)
        if span is None:
            _classify_unbound(
                excerpt, prose, claim_spans=claim_span_list, accounting=accounting
            )
            log.info("synthesise.unspanned_unbound", excerpt=excerpt[:120])
            continue
        accounting.unspanned_assertions += 1
        blocked.append(span)
        minted.append(
            {
                "excerpt": record["excerpt"],
                "rationale": record["rationale"],
                "judge_io_ref": record["judge_io_ref"],
                "span": span,
            }
        )
    return minted


def _apply_and_rebuild(
    *,
    prose: str,
    initial: ClaimValidationBatch,
    failing: Sequence[dict[str, Any]],
    repairs: Sequence[RepairItemWire],
    substrate: SubstrateView,
    section_group_ids: set[str],
    citable_finding_ids: set[str],
    citable_chunk_ids: set[str],
    available_claim_types: set[str],
    grounding_judge_backend: GroundingJudgeBackend,
    accounting: SectionAccounting,
    intent: str = "",
    section_focus: str = "",
    gap_restatement_seeds: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[list[ClaimDraft], str, int, dict[str, int], list[dict[str, Any]]]:
    """Apply the prose-splice repair: rebuild prose in one pass, re-validate and
    re-judge the repaired claims, and rebind span-bind failures (ADR 0015 §4).

    Returns the final claims, the rebuilt prose, the rejudge call count, the
    rejudge usage payload, and the rejudge unspanned records.
    """
    # Id-keyed repair mapping: the repair wire may arrive in any order, and
    # unknown ids are rejected structurally rather than rebound positionally.
    repair_by_index: dict[int, RepairItemWire] = {}
    failing_by_index: dict[int, dict[str, Any]] = {}
    failing_by_id: dict[str, dict[str, Any]] = {}
    for record in failing:
        idx = int(record["claim_index"])
        failing_by_index[idx] = record
        failing_by_id[str(record["claim_id"])] = record
    for repair in repairs:
        repair_record = failing_by_id.get(repair.claim_id)
        if repair_record is None:
            accounting.claims_rejected_structural += 1
            log.info(
                "synthesise.repair_unknown_claim_id",
                claim_id=repair.claim_id,
            )
            continue
        idx = int(repair_record["claim_index"])
        if idx in repair_by_index:
            accounting.claims_rejected_structural += 1
            log.info(
                "synthesise.repair_duplicate_claim_id",
                claim_id=repair.claim_id,
            )
            continue
        repair_by_index[idx] = repair
    failing_indices = set(failing_by_index)

    draft_by_index = {draft.claim_index: draft for draft in initial.drafts}
    rejection_by_index = {
        rejection.claim_index: rejection for rejection in initial.rejected
    }

    # Positioned claims = every claim currently carrying a bound span.
    positioned: list[tuple[int, tuple[int, int]]] = []
    for draft in initial.drafts:
        if draft.span is not None:
            positioned.append((draft.claim_index, draft.span))
    for rejection in initial.rejected:
        if rejection.span is not None:
            positioned.append((rejection.claim_index, rejection.span))

    items: list[SpliceItem] = []
    replace_claim_by_index: dict[int, ClaimWire] = {}
    kept_draft_indices: set[int] = set()
    for idx, span in positioned:
        indexed_repair = repair_by_index.get(idx)
        if idx in failing_indices and indexed_repair is not None:
            if indexed_repair.claim is None:
                # Segment rewritten to carry no claim, or deleted (empty
                # segment): the original claim is excluded (exhausted repair).
                items.append(
                    SpliceItem(
                        key=idx,
                        span=span,
                        replacement=indexed_repair.replacement_segment,
                        claim_text=None,
                    )
                )
                _count_repair_exclusion(idx, rejection_by_index, accounting)
            else:
                items.append(
                    SpliceItem(
                        key=idx,
                        span=span,
                        replacement=indexed_repair.replacement_segment,
                        claim_text=indexed_repair.claim.text,
                    )
                )
                replace_claim_by_index[idx] = indexed_repair.claim
        elif idx in failing_indices:
            # Failing but no repair item (count mismatch): keep an unsupported
            # draft verbatim; drop a structural rejection (residual prose stays,
            # exclusion counted).
            if idx in draft_by_index:
                items.append(
                    SpliceItem(key=idx, span=span, replacement=None, claim_text=None)
                )
                kept_draft_indices.add(idx)
            elif idx in rejection_by_index:
                _count_exclusion(rejection_by_index[idx], accounting=accounting)
        else:
            # Surviving (passing) draft — kept verbatim, span shifts.
            items.append(
                SpliceItem(key=idx, span=span, replacement=None, claim_text=None)
            )
            kept_draft_indices.add(idx)

    new_prose, span_map = splice_and_rebind(prose, items)

    # Kept drafts shift to their rebuilt spans; the round-trip is a code
    # invariant, not a model failure.
    for idx in kept_draft_indices:
        draft = draft_by_index[idx]
        new_span = span_map[idx]
        if new_span is None or new_prose[new_span[0] : new_span[1]] != draft.text:
            raise SynthesiseFailure("span_rebind_invariant")
        draft.span = new_span

    # Reasoning cap binds across passes.
    reasoning_count = sum(
        1
        for idx in kept_draft_indices
        if draft_by_index[idx].claim_type == "reasoning"
    )
    gap_restatement_accepted = (
        sum(
            1
            for idx in kept_draft_indices
            if draft_by_index[idx].claim_type == "gap"
        )
        if gap_restatement_seeds is not None
        else 0
    )

    replacement_drafts: list[ClaimDraft] = []
    for idx in sorted(replace_claim_by_index):
        claim = replace_claim_by_index[idx]
        record = failing_by_index[idx]
        claim_id = str(record["claim_id"])
        new_span = span_map[idx]
        if new_span is None:
            # The rewritten claim text is not a substring of its replacement
            # segment — the repair fails validation; the claim is excluded.
            _count_repair_exclusion(idx, rejection_by_index, accounting)
            continue
        if claim.claim_type == "reasoning":
            reasoning_count += 1
        result = _validate_claim(
            claim,
            claim_id=claim_id,
            claim_index=idx,
            substrate=substrate,
            section_group_ids=section_group_ids,
            citable_finding_ids=citable_finding_ids,
            citable_chunk_ids=citable_chunk_ids,
            reasoning_count=reasoning_count,
            available_claim_types=available_claim_types,
            gap_restatement_seeds=gap_restatement_seeds,
            gap_restatement_accepted=gap_restatement_accepted,
        )
        if isinstance(result, RejectedClaim):
            _count_exclusion(result, accounting=accounting)
            continue
        if new_prose[new_span[0] : new_span[1]] != result.text:
            raise SynthesiseFailure("span_rebind_invariant")
        result.span = new_span
        replacement_drafts.append(result)
        if result.claim_type == "gap" and gap_restatement_seeds is not None:
            gap_restatement_accepted += 1

    # Span-bind-failed repairs: no splice — rebind the rewritten claim text into
    # the current prose; still unbound → excluded (span_bind_failures).
    rebound_drafts: list[ClaimDraft] = []
    blocked_spans: list[tuple[int, int]] = []
    for idx in kept_draft_indices:
        kept_span = draft_by_index[idx].span
        if kept_span is not None:
            blocked_spans.append(kept_span)
    for draft in replacement_drafts:
        if draft.span is not None:
            blocked_spans.append(draft.span)
    for idx in sorted(failing_indices):
        record = failing_by_index[idx]
        if record.get("span") is not None:
            continue  # a spanned failure, handled by the splice above
        indexed_repair = repair_by_index.get(idx)
        if indexed_repair is None or indexed_repair.claim is None:
            accounting.span_bind_failures += 1
            continue
        rebind = _bind_into(new_prose, indexed_repair.claim.text, blocked_spans)
        if rebind is None:
            accounting.span_bind_failures += 1
            continue
        if indexed_repair.claim.claim_type == "reasoning":
            reasoning_count += 1
        result = _validate_claim(
            indexed_repair.claim,
            claim_id=str(record["claim_id"]),
            claim_index=idx,
            substrate=substrate,
            section_group_ids=section_group_ids,
            citable_finding_ids=citable_finding_ids,
            citable_chunk_ids=citable_chunk_ids,
            reasoning_count=reasoning_count,
            available_claim_types=available_claim_types,
            gap_restatement_seeds=gap_restatement_seeds,
            gap_restatement_accepted=gap_restatement_accepted,
        )
        if isinstance(result, RejectedClaim):
            _count_exclusion(result, accounting=accounting)
            continue
        result.span = rebind
        blocked_spans.append(rebind)
        rebound_drafts.append(result)
        if result.claim_type == "gap" and gap_restatement_seeds is not None:
            gap_restatement_accepted += 1

    rejudged = replacement_drafts + rebound_drafts

    # The final claim set is assembled BEFORE the re-judge: its span map must
    # span EVERY final valid claim (kept + rejudged, all types), not only the
    # rejudged subset, so the unspanned lane sees the whole claimed surface of
    # the rebuilt prose (item 17(i)).
    final_by_index: dict[int, ClaimDraft] = {
        idx: draft_by_index[idx] for idx in kept_draft_indices
    }
    for draft in rejudged:
        final_by_index[draft.claim_index] = draft
    final = [final_by_index[idx] for idx in sorted(final_by_index)]

    rejudge_calls, rejudge_usage, rejudge_unspanned = _judge_claims(
        claims=rejudged,
        occupied_claims=final,
        substrate=substrate,
        grounding_judge_backend=grounding_judge_backend,
        section_prose=new_prose,
        intent=intent,
        section_focus=section_focus,
    )
    return final, new_prose, rejudge_calls, rejudge_usage, rejudge_unspanned


def _section_claims(
    *,
    section_index: int,
    raw_claims: SectionProseWire,
    seed: dict[str, Any],
    transcript: list[ToolExchange],
    substrate: SubstrateView,
    section_group_ids: set[str],
    citable_finding_ids: set[str],
    citable_chunk_ids: set[str],
    synthesis_backend: SynthesisBackend,
    grounding_judge_backend: GroundingJudgeBackend,
    available_claim_types: set[str],
    accounting: SectionAccounting,
    intent: str = "",
    section_focus: str = "",
    gap_restatement_seeds: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[list[ClaimDraft], str, list[dict[str, Any]], dict[str, int], dict[str, int]]:
    call_counts = {"judge": 0, "repair": 0, "rejudge": 0}
    usage_totals = UsageAccumulator()
    prose = raw_claims.prose
    spans = bind_spans(prose, [claim.text for claim in raw_claims.claims])
    initial = validate_claims(
        raw_claims.claims,
        substrate=substrate,
        section_index=section_index,
        section_group_ids=section_group_ids,
        citable_finding_ids=citable_finding_ids,
        citable_chunk_ids=citable_chunk_ids,
        spans=spans,
        available_claim_types=available_claim_types,
        gap_restatement_seeds=gap_restatement_seeds,
    )
    judge_calls, judge_usage, unspanned = _judge_claims(
        claims=initial.drafts,
        substrate=substrate,
        grounding_judge_backend=grounding_judge_backend,
        section_prose=prose,
        intent=intent,
        section_focus=section_focus,
    )
    call_counts["judge"] += judge_calls
    usage_totals.add_payload(judge_usage)
    failing = _failing_records(initial.rejected, initial.drafts, prose=prose)
    repair_input = _repair_input_records(
        failing,
        prose=prose,
        transcript=transcript,
        substrate=substrate,
    )

    final: list[ClaimDraft]
    final_prose = prose
    rejudge_unspanned: list[dict[str, Any]] = []
    if not failing:
        final = _finalize_no_repair(initial=initial, accounting=accounting)
    else:
        accounting.repair_taken = True
        call_counts["repair"] += 1
        repair_wire: SectionRepairWire | None
        try:
            repair_wire, repair_usage = synthesis_backend.repair_section(
                seed, transcript, failing=repair_input
            )
            usage_totals.add(repair_usage)
        except MalformedEmissionError:
            # The one repair call produced structurally unparseable output —
            # the repair is loop-free and unrepeatable, so the failing claims
            # land per the exhaustion rules (prose untouched; the counted
            # exclusions), never a whole-component failure.
            accounting.repair_unparseable = True
            repair_wire = None
        if repair_wire is None:
            final = _finalize_no_repair(initial=initial, accounting=accounting)
        else:
            if _repair_id_mismatch(repair_wire.repairs, failing):
                accounting.repair_count_mismatch = True
            (
                final,
                final_prose,
                rejudge_calls,
                rejudge_usage,
                rejudge_unspanned,
            ) = _apply_and_rebuild(
                prose=prose,
                initial=initial,
                failing=failing,
                repairs=repair_wire.repairs,
                substrate=substrate,
                section_group_ids=section_group_ids,
                citable_finding_ids=citable_finding_ids,
                citable_chunk_ids=citable_chunk_ids,
                available_claim_types=available_claim_types,
                grounding_judge_backend=grounding_judge_backend,
                accounting=accounting,
                intent=intent,
                section_focus=section_focus,
                gap_restatement_seeds=gap_restatement_seeds,
            )
            call_counts["rejudge"] += rejudge_calls
            usage_totals.add_payload(rejudge_usage)

    for claim in final:
        if "gap_degraded" in claim.flags:
            accounting.gap_claims_degraded += 1
        if claim.verdict == "unsupported_mis_cited" and "unsupported_mis_cited" not in claim.flags:
            claim.flags.append("unsupported_mis_cited")
    # Honest accounting for the unspanned lane (ADR 0015 §5): the lane rides
    # the judge call, so prose that no judge call scanned — no judged-type
    # claims at all, or a splice rebuilt the prose and the rejudge had nothing
    # to judge — reports "skipped", never a clean zero.
    scanning_calls = (
        call_counts["rejudge"] if final_prose != prose else call_counts["judge"]
    )
    if final_prose.strip() and scanning_calls == 0:
        accounting.unspanned_lane_skipped = True
    # Supersede, never concatenate (item 17(iii)): when the repair splice
    # rebuilt the prose, the initial scan's unspanned excerpts were located in
    # prose that no longer exists, so the re-judge's results (scanned against
    # the rebuilt prose) REPLACE them — never extend. A rebuild with no
    # re-judge (rejudged carried no judged claim → rejudge_unspanned == [])
    # therefore keeps no stale flags; unspanned_lane_skipped carries the
    # honesty. When the prose is unchanged (no repair, or a repair that kept
    # every segment verbatim), the initial scan stands.
    if final_prose != prose:
        unspanned = rejudge_unspanned
    minted_unspanned = _bind_unspanned(
        unspanned,
        final_prose,
        accounting=accounting,
        claim_spans=[claim.span for claim in final if claim.span is not None],
    )
    return final, final_prose, minted_unspanned, call_counts, usage_totals.payload()


def _claim_counts(claims: Sequence[ClaimDraft]) -> dict[str, int]:
    counts = {claim_type: 0 for claim_type in CLAIM_TYPES}
    for claim in claims:
        counts[claim.claim_type] += 1
    return counts


def _tier_distribution(claims: Sequence[ClaimDraft]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for claim in claims:
        if claim.verdict is not None:
            counts[claim.verdict] += 1
    return dict(sorted(counts.items()))


def _citation_counts_by_origin(claims: Sequence[ClaimDraft]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for claim in claims:
        for citation in claim.citation_rows:
            counts[citation.origin] += 1
    return {
        "selected": counts.get("selected", 0),
        "unselected_screened": counts.get("unselected_screened", 0),
    }


def _segmentation_policies(claim: ClaimDraft, substrate: SubstrateView) -> dict[str, str]:
    return {
        chunk_id: substrate.chunk_by_id[chunk_id].segmentation_policy
        for chunk_id in sorted(claim.judge_chunk_ids)
        if chunk_id in substrate.chunk_by_id
    }


def _annotation_payload(claim: ClaimDraft, substrate: SubstrateView) -> dict[str, Any]:
    payload = dict(claim.payload)
    if claim.verdict is not None:
        payload.update(
            {
                "verdict": claim.verdict,
                "weakly_grounded": claim.weakly_grounded,
                "rationale": claim.rationale,
                "judge_model": JUDGE_MODEL,
                "judge_prompt_version": JUDGE_PROMPT_VERSION,
                "envelope_version": ENVELOPE_VERSION,
                "segmentation_policies": _segmentation_policies(claim, substrate),
                "judge_io_ref": claim.judge_io_ref,
            }
        )
    return payload


def _write_section(
    conn: Connection,
    *,
    artefact_id: uuid.UUID,
    prose: str,
    claims: Sequence[ClaimDraft],
    unspanned: Sequence[dict[str, Any]],
    substrate: SubstrateView,
    created_at: datetime,
) -> str:
    # The block content IS the authored prose (ADR 0015 §3); each claim's
    # addressable unit locates its bound span, and unit.content == prose[span].
    content = prose
    block_id = uuid.uuid4()
    conn.execute(
        block.insert().values(
            block_id=block_id,
            artefact_id=artefact_id,
            content=content,
            content_hash=content_hash(content),
            created_at=created_at,
        )
    )
    unit_rows: list[dict[str, Any]] = []
    annotation_rows: list[dict[str, Any]] = []
    citation_rows: list[dict[str, Any]] = []
    for claim in claims:
        if claim.span is None:
            # Every persisted claim is span-anchored by construction.
            raise SynthesiseFailure("claim_span_missing")
        start, end = claim.span
        if content[start:end] != claim.text:
            raise SynthesiseFailure("span_rebind_invariant")
        unit_id = uuid.uuid4()
        annotation_id = uuid.uuid4()
        unit_rows.append(
            {
                "unit_id": unit_id,
                "block_id": block_id,
                "unit_type": "text_span",
                "locator": {"start": start, "end": end},
                "content": claim.text,
                "created_at": created_at,
            }
        )
        annotation_rows.append(
            {
                "annotation_id": annotation_id,
                "block_id": block_id,
                "unit_id": unit_id,
                "annotation_type": claim.annotation_type,
                "payload": _annotation_payload(claim, substrate),
                "created_at": created_at,
            }
        )
        citation_rows.extend(
            {
                "citation_id": uuid.uuid4(),
                "annotation_id": annotation_id,
                "chunk_id": uuid.UUID(citation.chunk_id),
                "quote": citation.quote,
                "verification_result": "pass",
                "created_at": created_at,
            }
            for citation in claim.citation_rows
        )
    for assertion in unspanned:
        start, end = assertion["span"]
        unit_id = uuid.uuid4()
        annotation_id = uuid.uuid4()
        unit_rows.append(
            {
                "unit_id": unit_id,
                "block_id": block_id,
                "unit_type": "text_span",
                "locator": {"start": start, "end": end},
                "content": assertion["excerpt"],
                "created_at": created_at,
            }
        )
        annotation_rows.append(
            {
                "annotation_id": annotation_id,
                "block_id": block_id,
                "unit_id": unit_id,
                "annotation_type": "unspanned_assertion",
                "payload": {
                    "excerpt": assertion["excerpt"],
                    "rationale": assertion["rationale"],
                    "judge_model": JUDGE_MODEL,
                    "judge_prompt_version": JUDGE_PROMPT_VERSION,
                    "envelope_version": ENVELOPE_VERSION,
                    "judge_io_ref": assertion["judge_io_ref"],
                },
                "created_at": created_at,
            }
        )
    if unit_rows:
        conn.execute(addressable_unit.insert(), unit_rows)
        conn.execute(annotation.insert(), annotation_rows)
    if citation_rows:
        conn.execute(citation_table.insert(), citation_rows)
    return str(block_id)


def _group_member_findings(
    section: SectionSpec,
    *,
    substrate: SubstrateView,
) -> list[dict[str, Any]]:
    if substrate.grouping is None:
        return []
    member_ids: list[str] = []
    seen: set[str] = set()
    for group_id in section.group_ids:
        group = substrate.group_by_id.get(group_id)
        if group is None:
            continue
        members = group.get("member_finding_ids", [])
        if isinstance(members, list):
            for member in members:
                if isinstance(member, str) and member not in seen:
                    member_ids.append(member)
                    seen.add(member)
    all_findings = substrate.all_finding_by_id
    return [
        all_findings[finding_id].record
        for finding_id in member_ids
        if finding_id in all_findings
    ]


def _computed_spread(section: SectionSpec, substrate: SubstrateView) -> dict[str, int] | None:
    if substrate.grouping is not None:
        spread: Counter[str] = Counter()
        for group_id in section.group_ids:
            group = substrate.group_by_id.get(group_id)
            if group is None:
                continue
            raw_spread = group.get("direction_spread", {})
            if isinstance(raw_spread, dict):
                for direction, count in raw_spread.items():
                    if isinstance(direction, str) and isinstance(count, int):
                        spread[direction] += count
        return dict(sorted(spread.items()))
    if substrate.extraction is not None:
        return substrate.extraction_direction_spread
    return None


def _groups_unsectioned_by_facet(
    substrate: SubstrateView, assigned_groups: set[str]
) -> dict[str, int]:
    if substrate.grouping is None:
        return {}
    counts: Counter[str] = Counter()
    raw_facets = substrate.grouping.get("facets", [])
    if isinstance(raw_facets, list):
        for facet in raw_facets:
            if isinstance(facet, str):
                counts.setdefault(facet, 0)
    for group_id, group in substrate.group_by_id.items():
        if group_id in assigned_groups:
            continue
        facet = group.get("facet")
        if not isinstance(facet, str) or not facet:
            facet = facet_of_group_id(group_id)
        counts[facet] += 1
    return dict(sorted(counts.items()))


def _gathered_hash(ids: dict[str, set[str]]) -> str:
    return _json_sha256({key: sorted(value) for key, value in sorted(ids.items())})


def _resolved_reference_payload(refs: ResolvedReferences) -> dict[str, Any]:
    return {
        "characterisation_run_id": (
            str(refs.characterisation_run_id) if refs.characterisation_run_id else None
        ),
        "selection_run_id": str(refs.selection_run_id) if refs.selection_run_id else None,
        "extraction_run_id": str(refs.extraction_run_id) if refs.extraction_run_id else None,
        "grouping_run_id": str(refs.grouping_run_id) if refs.grouping_run_id else None,
        "how_resolved": refs.how_resolved,
    }


def _substrate_profile(refs: ResolvedReferences, corpus: CorpusProfile) -> dict[str, Any]:
    return {
        "characterisation": bool(refs.characterisation_run_id),
        "characterisation_run_id": (
            str(refs.characterisation_run_id) if refs.characterisation_run_id else None
        ),
        "selection": bool(refs.selection_run_id),
        "selection_run_id": str(refs.selection_run_id) if refs.selection_run_id else None,
        "extraction": bool(refs.extraction_run_id),
        "extraction_run_id": str(refs.extraction_run_id) if refs.extraction_run_id else None,
        "grouping": bool(refs.grouping_run_id),
        "grouping_run_id": str(refs.grouping_run_id) if refs.grouping_run_id else None,
        "screened_docs": corpus.screened_docs,
        "ingested_docs": corpus.ingested_docs,
        "appraised_docs": corpus.appraised_docs,
    }


def _inherited_chain_base(refs: ResolvedReferences) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if refs.characterisation_run_id is not None:
        result["characterisation"] = {"run_id": str(refs.characterisation_run_id)}
    if refs.selection_run_id is not None:
        result["selection"] = {
            "run_id": str(refs.selection_run_id),
            "characterisation_run_id": (
                str(refs.characterisation_run_id) if refs.characterisation_run_id else None
            ),
        }
    if refs.extraction_run_id is not None:
        result["extraction"] = {
            "run_id": str(refs.extraction_run_id),
            "selection_run_id": str(refs.selection_run_id) if refs.selection_run_id else None,
        }
    if refs.grouping_run_id is not None:
        result["grouping"] = {
            "run_id": str(refs.grouping_run_id),
            "extraction_run_id": str(refs.extraction_run_id) if refs.extraction_run_id else None,
        }
    return result


def _anchor_counts(claims: Sequence[ClaimDraft]) -> tuple[int, int]:
    """Count verified and failed quote anchors across claims, per anchor.

    Finding-claim anchors carry a ``match_status``; chunk-claim citations only
    persist when verified (failures reject instead), so every persisted chunk
    citation counts as verified. Both operands share the per-anchor unit.
    """
    verified = 0
    failed = 0
    for claim in claims:
        for anchor in claim.payload.get("anchors", []):
            if anchor.get("match_status") == "failed":
                failed += 1
            else:
                verified += 1
        verified += len(claim.payload.get("citations", []))
    return verified, failed


def _blocks_rollup(
    *,
    section: SectionSpec,
    block_id: str,
    claims: Sequence[ClaimDraft],
    accounting: SectionAccounting,
) -> dict[str, Any]:
    origin_counts = _citation_counts_by_origin(claims)
    unverified = sum(1 for claim in claims if "quote_unverified" in claim.flags)
    return {
        "title": section.title,
        "focus": section.focus,
        "nav_label": section.nav_label,
        "role": section.role,
        "block_id": block_id,
        "group_ids": section.group_ids,
        "tool_call_count": accounting.tool_call_count,
        "claim_counts_by_type": _claim_counts(claims),
        "tier_distribution": _tier_distribution(claims),
        "unsupported_count": sum(1 for claim in claims if claim.verdict == "unsupported_mis_cited"),
        "weakly_grounded_count": sum(1 for claim in claims if claim.weakly_grounded),
        "citations_verified": sum(len(claim.citation_rows) for claim in claims),
        "citations_unverified": unverified,
        "citations_by_origin": origin_counts,
        "chunk_claims_rejected": accounting.chunk_claims_rejected,
        "claims_rejected_structural": accounting.claims_rejected_structural,
        "gap_claims_degraded": accounting.gap_claims_degraded,
        "span_bind_failures": accounting.span_bind_failures,
        "unspanned_assertions": accounting.unspanned_assertions,
        "unspanned_overlap_filtered": accounting.unspanned_overlap_filtered,
        "unspanned_duplicate_stale": accounting.unspanned_duplicate_stale,
        "unspanned_unlocated": accounting.unspanned_unlocated,
        "repair_taken": accounting.repair_taken,
        "repair_count_mismatch": accounting.repair_count_mismatch,
        "repair_unparseable": accounting.repair_unparseable,
        "turn_cap_hit": accounting.turn_cap_hit,
        "rejected_tool_calls": accounting.rejected_tool_calls,
        "unspanned_lane_skipped": accounting.unspanned_lane_skipped,
    }


def _rollup_counts(
    *,
    all_claims: Sequence[ClaimDraft],
    section_blocks: Sequence[dict[str, Any]],
    sections_total: int,
    substrate: SubstrateView,
    groups_unsectioned: int | None,
    groups_unsectioned_by_facet: Mapping[str, int] | None,
    chunk_claims_rejected: int,
    claims_rejected_structural: int,
    gap_claims_degraded: int,
    span_bind_failures: int,
    unspanned_assertions: int,
    unspanned_overlap_filtered: int,
    unspanned_duplicate_stale: int,
    unspanned_unlocated: int,
    tool_calls_total: int,
) -> dict[str, Any]:
    verdict_counts: Counter[str] = Counter()
    for claim in all_claims:
        if claim.verdict is not None:
            verdict_counts[claim.verdict] += 1
    origin_counts = _citation_counts_by_origin(all_claims)
    anchors_verified, anchors_unverified = _anchor_counts(all_claims)
    finding_ids = {
        cited_id
        for claim in all_claims
        if claim.claim_type == "finding"
        for cited_id in claim.cited_ids
    }
    counts: dict[str, Any] = {
        "blocks_written": len(section_blocks),
        "sections_total": sections_total,
        "claims_total": _claim_counts(all_claims),
        "claims_by_verdict_lane": dict(sorted(verdict_counts.items())),
        "citations_verified": sum(len(claim.citation_rows) for claim in all_claims),
        "citations_unverified": sum(
            1 for claim in all_claims if "quote_unverified" in claim.flags
        ),
        "anchors_verified": anchors_verified,
        "anchors_unverified": anchors_unverified,
        "citations_from_unselected": origin_counts["unselected_screened"],
        "chunk_claims_rejected": chunk_claims_rejected,
        "claims_rejected_structural": claims_rejected_structural,
        "gap_claims_degraded": gap_claims_degraded,
        "span_bind_failures": span_bind_failures,
        "unspanned_assertions": unspanned_assertions,
        "unspanned_overlap_filtered": unspanned_overlap_filtered,
        "unspanned_duplicate_stale": unspanned_duplicate_stale,
        "unspanned_unlocated": unspanned_unlocated,
        "tool_calls_total": tool_calls_total,
        "findings_cited_distinct": len(finding_ids),
    }
    if substrate.extraction is not None:
        counts["findings_total"] = len(substrate.finding_by_id) + len(
            substrate.icf_finding_by_id
        )
    if substrate.grouping is not None:
        counts["groups_total"] = len(substrate.grouping_group_ids)
        counts["groups_unsectioned"] = groups_unsectioned or 0
        counts["groups_unsectioned_by_facet"] = dict(groups_unsectioned_by_facet or {})
    return counts


def _rollup_flags(
    *,
    groups_unsectioned: int,
    all_claims: Sequence[ClaimDraft],
    section_blocks: Sequence[dict[str, Any]],
    chunk_claims_rejected: int,
    claims_rejected_structural: int,
    gap_claims_degraded: int,
    span_bind_failures: int,
    unspanned_assertions: int,
    turn_cap_hit: bool,
    repair_path_taken: bool,
    repair_count_mismatch: bool,
    repair_unparseable: bool,
) -> dict[str, bool]:
    flags: dict[str, bool] = {}
    if groups_unsectioned:
        flags["groups_unsectioned"] = True
    if any(claim.verdict == "unsupported_mis_cited" for claim in all_claims):
        flags["unsupported_claims_present"] = True
    if any(claim.weakly_grounded for claim in all_claims):
        flags["weakly_grounded_present"] = True
    if chunk_claims_rejected:
        flags["chunk_claims_rejected"] = True
    if claims_rejected_structural:
        flags["claims_rejected_structural"] = True
    if gap_claims_degraded:
        flags["gap_claims_degraded"] = True
    if span_bind_failures:
        flags["span_bind_failed"] = True
    if unspanned_assertions:
        flags["unspanned_assertions_present"] = True
    if turn_cap_hit:
        flags["turn_cap_hit"] = True
    if repair_path_taken:
        flags["repair_path_taken"] = True
    if repair_count_mismatch:
        flags["repair_count_mismatch"] = True
    if repair_unparseable:
        flags["repair_unparseable"] = True
    if any(block["citations_verified"] == 0 for block in section_blocks):
        flags["uncited_sections"] = True
    return flags


def _generation_call_count(call_counts: Mapping[str, int]) -> int:
    return sum(call_counts.values())


def _reserve_generation(call_counts: dict[str, int], phase: str) -> None:
    if _generation_call_count(call_counts) + 1 > generation_budget_max():
        raise SynthesiseFailure("budget_exceeded")
    call_counts[phase] = call_counts.get(phase, 0) + 1


def _key_findings_ledger(
    section_claim_groups: Sequence[tuple[SectionSpec, Sequence[ClaimDraft]]],
) -> list[dict[str, Any]]:
    """Build the key-findings seed ledger: surviving claims WITH evidence.

    Per section: title, role, and each surviving claim's ``text``,
    ``claim_type``, ``verdict``, ``cited_finding_ids`` and chunk citations
    (``chunk_record_id`` + ``quote``). Gap claims also carry
    ``payload["gap"]`` (grade + coverage base) so the pass can re-state
    them (task 034 S3). Data, not instructions (ADR 0015 §8).
    """
    ledger: list[dict[str, Any]] = []
    for section, claims in section_claim_groups:
        entries: list[dict[str, Any]] = []
        for claim in claims:
            chunk_citations = [
                {
                    "chunk_record_id": citation["cited_chunk_record_id"],
                    "quote": citation.get("quote"),
                }
                for citation in claim.payload.get("citations", [])
                if isinstance(citation, dict) and citation.get("cited_chunk_record_id")
            ]
            entry: dict[str, Any] = {
                "text": claim.text,
                "claim_type": claim.claim_type,
                "verdict": claim.verdict,
                "cited_finding_ids": list(claim.payload.get("cited_finding_ids", [])),
                "chunk_citations": chunk_citations,
            }
            if claim.claim_type == "gap":
                gap = claim.payload.get("gap")
                if isinstance(gap, dict):
                    entry["gap"] = {
                        "grade": gap.get("grade"),
                        "coverage_base": gap.get("coverage_base"),
                        "coverage_record_id": gap.get("coverage_record_id"),
                        "sparsity": gap.get("sparsity"),
                    }
            entries.append(entry)
        ledger.append(
            {"title": section.title, "role": section.role, "claims": entries}
        )
    return ledger


def _gap_restatement_seeds(ledger: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Collect verified gap payloads from the key-findings ledger."""
    seeds: list[dict[str, Any]] = []
    for section in ledger:
        claims = section.get("claims")
        if not isinstance(claims, list):
            continue
        for claim in claims:
            if not isinstance(claim, dict) or claim.get("claim_type") != "gap":
                continue
            gap = claim.get("gap")
            if (
                isinstance(gap, dict)
                and gap.get("grade")
                and gap.get("coverage_base")
            ):
                seeds.append(dict(gap))
    return seeds


def _key_findings_pass(
    conn: Connection,
    *,
    artefact_id: uuid.UUID,
    intent: str,
    section_claim_groups: Sequence[tuple[SectionSpec, Sequence[ClaimDraft]]],
    all_claims: Sequence[ClaimDraft],
    substrate: SubstrateView,
    synthesis_backend: SynthesisBackend,
    grounding_judge_backend: GroundingJudgeBackend,
    run_chunk_content: dict[str, str],
    available_claim_types: set[str],
    kf_section_index: int,
    created_at: datetime,
) -> dict[str, Any]:
    """Run the final key-findings pass (produced last, shown first).

    A schema-constrained emission over the run's surviving claims ledger, then
    the ordinary ``_section_claims`` grounding path with a synthetic seed and
    empty transcript. Conditional-required (ADR 0015 §8): an empty emission
    (empty/whitespace prose AND zero claims) mints NO block.

    Returns a result dict: ``present`` plus, when present, the minted
    ``block_id``, its ``claims``, ``block_rollup``, ``accounting`` and the
    ``call_counts``/``usage`` of the pass; when absent, ``reason``. Emission
    call count is always ``1`` (the pass ran).
    """
    kf_available = KEY_FINDINGS_CLAIM_TYPES & available_claim_types
    citable_finding_ids = {
        cited_id
        for claim in all_claims
        if claim.claim_type == "finding"
        for cited_id in claim.cited_ids
    }
    citable_chunk_ids = {
        cited_id
        for claim in all_claims
        if claim.claim_type == "chunk"
        for cited_id in claim.cited_ids
    }
    ledger = _key_findings_ledger(section_claim_groups)
    gap_seeds = _gap_restatement_seeds(ledger)
    seed = {
        "intent": intent,
        "substrate": {},
        "corpus": {},
        "available_tools": [],
        "available_claim_types": sorted(kf_available),
        "ledger": ledger,
        # Chunk-content map filtered to chunks cited by surviving claims only
        # (022 rider 16) — the pass's evidence surface, since it runs
        # transcript-free. ``citable_chunk_ids`` (below) already IS that set:
        # citation eligibility for this transcript-free pass already restricts
        # to chunks surviving claims cited, so no separate computation is
        # needed. The unfiltered union was ~2% wasted input (every section's
        # gathered-but-uncited chunks).
        "chunk_content_by_id": {
            chunk_id: content
            for chunk_id, content in run_chunk_content.items()
            if chunk_id in citable_chunk_ids
        },
    }
    usage_totals = UsageAccumulator()
    raw_kf, kf_usage = synthesis_backend.write_key_findings(seed)
    usage_totals.add(kf_usage)
    # The explicit absence path (test-owned): nothing is forced.
    if not raw_kf.prose.strip() and not raw_kf.claims:
        return {
            "present": False,
            "reason": "no_headline_claims",
            "emission_calls": 1,
            "usage": usage_totals.payload(),
        }

    section_spec = SectionSpec(
        title=KEY_FINDINGS_TITLE, focus=KEY_FINDINGS_FOCUS, role="key_findings"
    )
    accounting = SectionAccounting(
        tool_call_counts={},
        tool_call_count=0,
        gathered_id_hash=_gathered_hash({"finding_ids": set(), "chunk_ids": set()}),
        turns_used=0,
        turn_cap_hit=False,
    )
    claims, final_prose, minted_unspanned, call_counts, section_usage = _section_claims(
        section_index=kf_section_index,
        raw_claims=raw_kf,
        seed=seed,
        transcript=[],
        substrate=substrate,
        section_group_ids=set(),
        citable_finding_ids=citable_finding_ids,
        citable_chunk_ids=citable_chunk_ids,
        synthesis_backend=synthesis_backend,
        grounding_judge_backend=grounding_judge_backend,
        available_claim_types=kf_available,
        accounting=accounting,
        intent=intent,
        section_focus=KEY_FINDINGS_SECTION_FOCUS,
        gap_restatement_seeds=gap_seeds,
    )
    usage_totals.add_payload(section_usage)
    block_id = _write_section(
        conn,
        artefact_id=artefact_id,
        prose=final_prose,
        claims=claims,
        unspanned=minted_unspanned,
        substrate=substrate,
        created_at=created_at,
    )
    block_rollup = _blocks_rollup(
        section=section_spec,
        block_id=block_id,
        claims=claims,
        accounting=accounting,
    )
    return {
        "present": True,
        "block_id": block_id,
        "claims": claims,
        "block_rollup": block_rollup,
        "accounting": accounting,
        "emission_calls": 1,
        "call_counts": call_counts,
        "usage": usage_totals.payload(),
        "prose": final_prose,
    }


def synthesise_scope(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    context: SynthesiseContext,
    synthesis_backend: SynthesisBackend,
    grounding_judge_backend: GroundingJudgeBackend,
    embedding_backend: Any,
    chunk_reranker: Any = None,
    progress_emitter: ProgressEmitter | None = None,
) -> dict[str, Any]:
    """Run the synthesise component for one evidence scope.

    Args:
        conn: Open database connection; all writes use its active transaction.
        project_id: Owning project.
        run_id: Current run id.
        context: Scope and optional upstream references.
        synthesis_backend: Section proposal/section loop backend.
        grounding_judge_backend: Grounding judge backend.
        embedding_backend: Embedding backend for chunk search.
        chunk_reranker: Optional chunk reranker; defaults to pass-through.
        progress_emitter: Optional independently-transactional presentation
            event emitter. It never writes through ``conn``.

    Returns:
        Component summary for ``component.completed``.

    Raises:
        SynthesiseFailure: Structural/backend failure. Roll-up is never written
            on failure; post-block failures carry already-written block ids.
    """
    # Loud before any write: a same-run re-execution must fail while the
    # transaction is still healthy so the failure event can persist. The
    # uq_synr_scope_run unique stays as the concurrent-writer backstop.
    existing_rollup = conn.execute(
        sa_select(synthesis_result.c.run_id).where(
            synthesis_result.c.evidence_scope_id == context.scope_id,
            synthesis_result.c.run_id == run_id,
        )
    ).first()
    if existing_rollup is not None:
        raise SynthesiseFailure(
            f"same_run_reexecution: synthesis_result already exists for "
            f"scope {context.scope_id} run {run_id}"
        )
    reranker = chunk_reranker if chunk_reranker is not None else PassThroughChunkReranker()
    blocks_written: list[str] = []
    call_counts = {
        "proposal": 0,
        "proposal_repair": 0,
        "section_turns": 0,
        "judge": 0,
        "repair": 0,
        "rejudge": 0,
        # The final key-findings pass (ADR 0015 §8): emission + judge/repair/
        # rejudge, named consistently with the section lanes.
        "key_findings": 0,
        "key_findings_judge": 0,
        "key_findings_repair": 0,
        "key_findings_rejudge": 0,
    }
    usage_totals = UsageAccumulator()
    refs = _resolve_references(conn, project_id=project_id, context=context)
    corpus = _load_corpus_profile(conn, project_id=project_id, scope_id=context.scope_id)
    if not refs.any_resolved() and corpus.screened_docs == 0:
        raise SynthesiseFailure("no_groundable_substrate")

    selected_pss_id_strings = _selected_pss_ids(refs.selection_row)
    selected_pss_ids = {uuid.UUID(pss_id) for pss_id in selected_pss_id_strings}
    group_ids_for_directive = None
    grouping_summary = _grouping_summary(refs.grouping_row)
    if grouping_summary is not None:
        group_ids_for_directive = {
            str(group["group_id"])
            for group in grouping_summary["groups"]
            if isinstance(group.get("group_id"), str)
        }
    try:
        directive = parse_synthesis_directive(
            context.context, grouping_group_ids=group_ids_for_directive
        )
    except SynthesisDirectiveError as exc:
        raise SynthesiseFailure(f"synthesis_directive_invalid: {exc}") from exc

    retrieval_scope = None
    retriever: ChunkRetriever | None = None
    if corpus.screened_docs > 0:
        try:
            retrieval_scope = build_retrieval_scope(
                conn,
                project_id=project_id,
                scope_id=context.scope_id,
                selected_pss_ids=selected_pss_ids,
            )
        except RetrievalUnitCapError as exc:
            raise SynthesiseFailure(str(exc)) from exc
        retriever = ChunkRetriever(
            retrieval_scope,
            embedder=embedding_backend,
            directive=directive,
            reranker=reranker,
            selection_reference_resolved=refs.selection_run_id is not None,
        )

    selected_pss_ids_str = {str(item) for item in selected_pss_ids}
    chunk_by_id, chunks_by_pss_id, chunk_bases = _load_screened_chunks(
        conn,
        project_id=project_id,
        scope_id=context.scope_id,
        selected_pss_ids=selected_pss_ids_str,
        appraised_pss_ids=corpus.appraised_pss_ids,
    )
    # B2′ (024 / ADR 0023): this run's relevance marks, read run-scoped from the
    # extraction provenance. Empty when the run carried no emphasis / the
    # annotator failed open. Threaded into every finding surface so member
    # findings and query_findings results carry the mark; the priority block
    # renders only when marks are present.
    relevance_annotations = _relevance_annotations(refs.extraction_row)
    priority_block_active = bool(relevance_annotations)
    finding_by_id, icf_finding_by_id, icf_profile_available, finding_bases = _load_findings(
        conn,
        project_id=project_id,
        extraction_row=refs.extraction_row,
        relevance_annotations=relevance_annotations,
    )
    group_doc_ids_by_group_id = _group_doc_ids_by_group_id(
        grouping_summary,
        {**finding_by_id, **icf_finding_by_id},
    )
    basis_by_snapshot = {**chunk_bases, **finding_bases}
    coverage_records = _load_coverage_records(
        conn, project_id=project_id, scope_id=context.scope_id
    )
    substrate = SubstrateView(
        characterisation=_characterisation_summary(refs.characterisation_row),
        selection=_selection_summary(refs.selection_row),
        extraction=_extraction_summary(refs.extraction_row),
        grouping=_grouping_summary(refs.grouping_row),
        corpus=corpus,
        coverage_records=coverage_records,
        chunk_by_id=chunk_by_id,
        chunks_by_pss_id=chunks_by_pss_id,
        finding_by_id=finding_by_id,
        icf_finding_by_id=icf_finding_by_id,
        icf_profile_available=icf_profile_available,
        basis_by_snapshot_id=basis_by_snapshot,
        selected_pss_ids=selected_pss_ids_str,
    )
    summaries = _substrate_summaries(refs, corpus)
    section_substrate = {
        key: value for key, value in summaries.items() if key != "corpus"
    }
    corpus_summary = summaries.get("corpus", {})

    created_at = datetime.now(UTC)
    artefact_id = uuid.uuid4()
    conn.execute(
        artefact.insert().values(
            artefact_id=artefact_id,
            project_id=project_id,
            capability_run_id=conn.execute(
                sa_select(runs.c.capability_run_id)
                .where(runs.c.run_id == run_id)
                .where(runs.c.project_id == project_id)
            ).scalar_one_or_none(),
            title=derive_artefact_title(context.intent),
            created_at=created_at,
        )
    )

    proposal_normalisations: list[str] = []
    if directive.sections is not None:
        sections = _sections_from_directive(directive.sections)
        section_source = "scope_context"
    else:
        try:
            _reserve_generation(call_counts, "proposal")
            proposal, usage = synthesis_backend.propose_sections(
                intent=context.intent,
                substrate=summaries,
                section_budget=directive.section_budget,
            )
            usage_totals.add(usage)
        except RuntimeError as exc:
            raise SynthesiseFailure(
                # Our own RuntimeError messages are bounded and reduced by
                # construction (never raw response bodies) — carry them: the
                # failure event is the only diagnosable record.
                f"{type(exc).__name__}: {str(exc)[:200]}",
                blocks_written=blocks_written,
            ) from exc
        grouping_group_ids = substrate.grouping_group_ids if substrate.grouping else None
        sections, reasons, proposal_normalisations = _validate_sections(
            proposal,
            grouping_group_ids=grouping_group_ids,
            section_budget=directive.section_budget,
        )
        if reasons:
            try:
                _reserve_generation(call_counts, "proposal_repair")
                repaired, usage = synthesis_backend.propose_sections(
                    intent=context.intent,
                    substrate=summaries,
                    rejection=reasons,
                    section_budget=directive.section_budget,
                )
                usage_totals.add(usage)
            except RuntimeError as exc:
                raise SynthesiseFailure(
                    f"{type(exc).__name__}: {str(exc)[:200]}",
                    blocks_written=blocks_written,
                ) from exc
            sections, reasons, proposal_normalisations = _validate_sections(
                repaired,
                grouping_group_ids=substrate.grouping_group_ids if substrate.grouping else None,
                section_budget=directive.section_budget,
            )
            if reasons:
                raise SynthesiseFailure(
                    # Name the surviving rejection reasons (bounded) — the
                    # failure event is the only diagnosable record of WHY the
                    # bounded repair could not converge.
                    "section_proposal_invalid: " + "; ".join(reasons)[:600],
                    blocks_written=blocks_written,
                )
        if proposal_normalisations:
            log.info(
                "synthesise.proposal_normalised",
                normalisations=proposal_normalisations,
            )
        section_source = "proposal"

    # Code-inject the conclusions section LAST (ADR 0015 §8): it rides above
    # SECTION_CAP and is exempt from the FORBIDDEN_SECTION_TITLES check by
    # construction — proposals are validated BEFORE this injection, so a
    # PROPOSED "Conclusion(s)" title is still rejected; only this role-injected
    # section carries the "Conclusions" title. It runs through the normal
    # section loop (tools + ledger; its claims enter the ledger).
    sections = [
        *sections,
        SectionSpec(
            title=CONCLUSIONS_TITLE,
            focus=_conclusions_focus(context.intent),
            role="conclusions",
        ),
    ]
    if progress_emitter is not None:
        progress_emitter.emit_skeleton(
            [{"title": section.title, "focus": section.focus} for section in sections]
        )

    assigned_groups = {group_id for section in sections for group_id in section.group_ids}
    groups_unsectioned_by_facet = _groups_unsectioned_by_facet(substrate, assigned_groups)
    groups_unsectioned = sum(groups_unsectioned_by_facet.values())

    findings_reader = (
        make_findings_reader(
            conn,
            project_id=project_id,
            extraction_run_id=refs.extraction_run_id,
            evidence_scope_id=context.scope_id,
            grouping_groups=cast("list[dict[str, Any]]", grouping_summary["groups"])
            if grouping_summary is not None
            else None,
            relevance_annotations=relevance_annotations,
        )
        if refs.extraction_run_id is not None
        else None
    )
    lookup_reader = make_lookup_reader(
        conn,
        project_id=project_id,
        scope_id=context.scope_id,
        characterisation_run_id=refs.characterisation_run_id,
        selection_run_id=refs.selection_run_id,
        extraction_run_id=refs.extraction_run_id,
        grouping_run_id=refs.grouping_run_id,
    )

    available_claim_types = available_claim_types_for_substrate(substrate)
    all_claims: list[ClaimDraft] = []
    # Per-section (spec, surviving claims) for the key-findings ledger, and the
    # run-level chunk-content map (union of every section's transcript chunks).
    section_claim_groups: list[tuple[SectionSpec, list[ClaimDraft]]] = []
    run_chunk_content: dict[str, str] = {}
    section_rollups: list[dict[str, Any]] = []
    section_provenance: list[dict[str, Any]] = []
    total_chunk_rejections = 0
    total_structural_rejections = 0
    total_gap_degraded = 0
    total_span_bind_failures = 0
    total_unspanned_assertions = 0
    total_unspanned_overlap_filtered = 0
    total_unspanned_duplicate_stale = 0
    total_unspanned_unlocated = 0
    total_tool_calls = 0
    turn_cap_hit_any = False
    repair_path_taken = False
    repair_count_mismatch_any = False
    repair_unparseable_any = False

    for section_index, section in enumerate(sections):
        if progress_emitter is not None:
            progress_emitter.section_started(section_index)
        member_findings = _group_member_findings(section, substrate=substrate)
        member_finding_ids = {
            finding["finding_id"]
            for finding in member_findings
            if isinstance(finding.get("finding_id"), str)
        }
        seed = {
            "intent": context.intent,
            "section": section.as_seed(),
            "section_index": section_index,
            "substrate": section_substrate,
            "corpus": corpus_summary if isinstance(corpus_summary, dict) else {},
            "available_tools": [
                tool
                for tool in ("search_chunks", "query_findings", "lookup")
                if (
                    (tool == "search_chunks" and retriever is not None)
                    or (tool == "query_findings" and findings_reader is not None)
                    or tool == "lookup"
                )
            ],
            "available_claim_types": sorted(available_claim_types),
            "member_findings": member_findings,
            "computed_spread": _computed_spread(section, substrate),
            "ledger": build_ledger(all_claims),
            # B2′ (024): gates the v8 priority-findings block into the section
            # system prompt (a control flag on the seed, never a data-payload
            # field — see synthesis_backend._section_system_prompt).
            "priority_block_active": priority_block_active,
        }
        tools = build_section_tools(
            retriever=retriever,
            findings_reader=findings_reader,
            lookup_reader=lookup_reader,
            group_doc_ids_by_group_id=group_doc_ids_by_group_id,
        )
        try:
            loop_result = run_section_loop(
                synthesis_backend,
                seed=seed,
                tools=tools,
                retriever=retriever,
            )
            usage_totals.add_payload(loop_result["usage_totals"])
        except RuntimeError as exc:
            raise SynthesiseFailure(type(exc).__name__, blocks_written=blocks_written) from exc
        call_counts["section_turns"] += int(loop_result["turns_used"])
        if _generation_call_count(call_counts) > generation_budget_max():
            raise SynthesiseFailure("budget_exceeded", blocks_written=blocks_written)
        transcript = loop_result["transcript"]
        ids = gathered_ids(transcript)
        citable_finding_ids = member_finding_ids | ids["finding_ids"]
        citable_chunk_ids = ids["chunk_ids"]
        accounting = SectionAccounting(
            tool_call_counts=dict(loop_result["tool_call_counts"]),
            tool_call_count=sum(loop_result["tool_call_counts"].values()),
            gathered_id_hash=_gathered_hash(ids),
            turns_used=int(loop_result["turns_used"]),
            turn_cap_hit=bool(loop_result["turn_cap_hit"]),
            # Claim objects the live emission carried that failed structural
            # validation (backend per-claim salvage) — counted, never silent.
            claims_rejected_structural=int(loop_result.get("malformed_claims", 0)),
            rejected_tool_calls=int(loop_result.get("rejected_tool_calls", 0)),
        )
        raw_claims = loop_result["claims"] or SectionProseWire(prose="", claims=[])
        try:
            (
                claims,
                final_prose,
                minted_unspanned,
                section_call_counts,
                section_usage,
            ) = _section_claims(
                section_index=section_index,
                raw_claims=raw_claims,
                seed=seed,
                transcript=transcript,
                substrate=substrate,
                section_group_ids=set(section.group_ids),
                citable_finding_ids=citable_finding_ids,
                citable_chunk_ids=citable_chunk_ids,
                synthesis_backend=synthesis_backend,
                grounding_judge_backend=grounding_judge_backend,
                available_claim_types=available_claim_types,
                accounting=accounting,
                intent=context.intent,
                section_focus=section.focus,
            )
            usage_totals.add_payload(section_usage)
        except SynthesiseFailure as exc:
            raise SynthesiseFailure(
                exc.error, blocks_written=blocks_written or exc.blocks_written
            ) from exc
        except RuntimeError as exc:
            raise SynthesiseFailure(type(exc).__name__, blocks_written=blocks_written) from exc
        for phase, count in section_call_counts.items():
            call_counts[phase] += count
        if _generation_call_count(call_counts) > generation_budget_max():
            raise SynthesiseFailure("budget_exceeded", blocks_written=blocks_written)
        block_id = _write_section(
            conn,
            artefact_id=artefact_id,
            prose=final_prose,
            claims=claims,
            unspanned=minted_unspanned,
            substrate=substrate,
            created_at=created_at,
        )
        blocks_written.append(block_id)
        if progress_emitter is not None:
            progress_emitter.section_completed(section_index, prose=final_prose)
        total_chunk_rejections += accounting.chunk_claims_rejected
        total_structural_rejections += accounting.claims_rejected_structural
        total_gap_degraded += accounting.gap_claims_degraded
        total_span_bind_failures += accounting.span_bind_failures
        total_unspanned_assertions += accounting.unspanned_assertions
        total_unspanned_overlap_filtered += accounting.unspanned_overlap_filtered
        total_unspanned_duplicate_stale += accounting.unspanned_duplicate_stale
        total_unspanned_unlocated += accounting.unspanned_unlocated
        total_tool_calls += accounting.tool_call_count
        turn_cap_hit_any = turn_cap_hit_any or accounting.turn_cap_hit
        repair_path_taken = repair_path_taken or accounting.repair_taken
        repair_count_mismatch_any = (
            repair_count_mismatch_any or accounting.repair_count_mismatch
        )
        repair_unparseable_any = repair_unparseable_any or accounting.repair_unparseable
        section_rollups.append(
            _blocks_rollup(
                section=section,
                block_id=block_id,
                claims=claims,
                accounting=accounting,
            )
        )
        section_provenance.append(
            {
                "title": section.title,
                "tool_call_counts": accounting.tool_call_counts,
                "tool_call_count": accounting.tool_call_count,
                "turns_used": accounting.turns_used,
                "turn_cap_hit": accounting.turn_cap_hit,
                "gathered_id_hash": accounting.gathered_id_hash,
            }
        )
        all_claims.extend(claims)
        section_claim_groups.append((section, claims))
        run_chunk_content.update(_chunk_content_by_id(transcript))

    # The final key-findings pass (ADR 0015 §8): produced LAST (after every
    # section incl. conclusions), shown FIRST. Conditional-required — an empty
    # emission mints no block and nothing is forced.
    if progress_emitter is not None:
        progress_emitter.key_findings_started()
    try:
        key_findings_result = _key_findings_pass(
            conn,
            artefact_id=artefact_id,
            intent=context.intent,
            section_claim_groups=section_claim_groups,
            all_claims=all_claims,
            substrate=substrate,
            synthesis_backend=synthesis_backend,
            grounding_judge_backend=grounding_judge_backend,
            run_chunk_content=run_chunk_content,
            available_claim_types=available_claim_types,
            kf_section_index=len(sections),
            created_at=created_at,
        )
    except SynthesiseFailure as exc:
        raise SynthesiseFailure(
            exc.error, blocks_written=blocks_written or exc.blocks_written
        ) from exc
    except RuntimeError as exc:
        raise SynthesiseFailure(type(exc).__name__, blocks_written=blocks_written) from exc
    call_counts["key_findings"] += int(key_findings_result.get("emission_calls", 0))
    usage_totals.add_payload(key_findings_result.get("usage", UsageAccumulator().payload()))
    key_findings_rollup: dict[str, Any]
    if key_findings_result["present"]:
        kf_call_counts = key_findings_result["call_counts"]
        call_counts["key_findings_judge"] += kf_call_counts.get("judge", 0)
        call_counts["key_findings_repair"] += kf_call_counts.get("repair", 0)
        call_counts["key_findings_rejudge"] += kf_call_counts.get("rejudge", 0)
        kf_accounting: SectionAccounting = key_findings_result["accounting"]
        kf_claims: list[ClaimDraft] = list(key_findings_result["claims"])
        # Roll-up order is presentation order: the key-findings block leads.
        # Production order stays evidenced by provenance (it was written last).
        section_rollups.insert(0, key_findings_result["block_rollup"])
        blocks_written.append(key_findings_result["block_id"])
        total_chunk_rejections += kf_accounting.chunk_claims_rejected
        total_structural_rejections += kf_accounting.claims_rejected_structural
        total_gap_degraded += kf_accounting.gap_claims_degraded
        total_span_bind_failures += kf_accounting.span_bind_failures
        total_unspanned_assertions += kf_accounting.unspanned_assertions
        total_unspanned_overlap_filtered += kf_accounting.unspanned_overlap_filtered
        total_unspanned_duplicate_stale += kf_accounting.unspanned_duplicate_stale
        total_unspanned_unlocated += kf_accounting.unspanned_unlocated
        repair_path_taken = repair_path_taken or kf_accounting.repair_taken
        repair_count_mismatch_any = (
            repair_count_mismatch_any or kf_accounting.repair_count_mismatch
        )
        repair_unparseable_any = repair_unparseable_any or kf_accounting.repair_unparseable
        all_claims.extend(kf_claims)
        key_findings_rollup = {"present": True}
        if progress_emitter is not None:
            progress_emitter.key_findings_completed(prose=key_findings_result["prose"])
    else:
        key_findings_rollup = {
            "present": False,
            "reason": key_findings_result["reason"],
        }
        if progress_emitter is not None:
            progress_emitter.key_findings_completed(prose="")

    retrieval_provenance = retriever.provenance() if retriever is not None else {}
    retrieval_scope_payload = {
        "screened_doc_count": corpus.screened_docs,
        "ingested_doc_count": corpus.ingested_docs,
        "appraised_doc_count": corpus.appraised_docs,
        "unit_count": retrieval_provenance.get("unit_count", 0),
        "selection_prior": {
            "run_id": str(refs.selection_run_id),
            "selected_pss_ids": sorted(selected_pss_id_strings),
            "boost": retrieval_provenance.get("selection_prior"),
        }
        if refs.selection_run_id is not None
        else None,
        "executed_retrieval_boosts": retrieval_provenance.get("executed_boosts", {}),
        "unmatched_boosts": retrieval_provenance.get("unmatched_boosts", {}),
        "soft_prior_factors": retrieval_provenance.get("soft_prior_factors", {}),
        "confidence_suppressed": retrieval_provenance.get("confidence_suppressed", False),
        "reranker": retrieval_provenance.get("reranker", getattr(reranker, "mode", "none")),
    }
    provenance = {
        "prompt_versions": {
            "sections": SECTIONS_PROMPT_VERSION,
            "section": SECTION_PROMPT_VERSION,
            "key_findings": KEY_FINDINGS_PROMPT_VERSION,
            "judge": JUDGE_PROMPT_VERSION,
            "tool_schemas": {
                "version_note": "versioned with section prompt",
                "schema_count": len(SECTION_TOOL_SCHEMAS),
            },
        },
        "models": {"synthesis": SYNTHESIS_MODEL, "judge": JUDGE_MODEL},
        "envelope_policy_version": ENVELOPE_VERSION,
        "backend_modes": {
            "synthesis": synthesis_backend.mode,
            "grounding_judge": grounding_judge_backend.mode,
            "embedding": getattr(embedding_backend, "mode", "unknown"),
            "reranker": getattr(reranker, "mode", "none"),
        },
        "call_counts": call_counts,
        "generation_budget_max": generation_budget_max(),
        "substrate_profile": _substrate_profile(refs, corpus),
        "resolved_references": _resolved_reference_payload(refs),
        "retrieval_scope": retrieval_scope_payload,
        "section_set": {
            "source": section_source,
            "sections": [section.as_seed() for section in sections],
            "groups_unsectioned": groups_unsectioned,
            "groups_unsectioned_by_facet": groups_unsectioned_by_facet,
            # Deterministic proposal normalisations (visible, never silent):
            # overlong title/focus truncation; group_ids stripped when no
            # grouping is referenced (the rev 8 M5 clamp-over-reject posture).
            "proposal_normalisations": proposal_normalisations,
        },
        "caps": {
            "SECTION_CAP": SECTION_CAP,
            "SECTION_TURN_CAP": SECTION_TURN_CAP,
            "SYNTH_CHUNK_TOP_K": SYNTH_CHUNK_TOP_K,
            "SYNTH_CHUNK_CHAR_BUDGET": SYNTH_CHUNK_CHAR_BUDGET,
            "RETRIEVAL_UNIT_CAP": RETRIEVAL_UNIT_CAP,
            "REPAIR_ROUND_CAP": 1,  # never enforced beyond a single repair pass
        },
        "sections": section_provenance,
        "inherited_chain_base": _inherited_chain_base(refs),
        "directive": directive.as_provenance(),
        # B2′ (024 / ADR 0023): whether the v8 priority-findings block rendered
        # (iff the run carried relevance annotations) and how many findings the
        # run marked — so a reader distinguishes an annotated run from a bare one.
        "relevance": {
            "priority_block_active": priority_block_active,
            "annotated_finding_count": len(relevance_annotations),
        },
    }
    counts = _rollup_counts(
        all_claims=all_claims,
        section_blocks=section_rollups,
        sections_total=len(sections),
        substrate=substrate,
        groups_unsectioned=groups_unsectioned,
        groups_unsectioned_by_facet=groups_unsectioned_by_facet,
        chunk_claims_rejected=total_chunk_rejections,
        claims_rejected_structural=total_structural_rejections,
        gap_claims_degraded=total_gap_degraded,
        span_bind_failures=total_span_bind_failures,
        unspanned_assertions=total_unspanned_assertions,
        unspanned_overlap_filtered=total_unspanned_overlap_filtered,
        unspanned_duplicate_stale=total_unspanned_duplicate_stale,
        unspanned_unlocated=total_unspanned_unlocated,
        tool_calls_total=total_tool_calls,
    )
    # Conditional-required key-findings marker (ADR 0015 §8): present iff a
    # block was minted; the absence path records why nothing was forced.
    counts["key_findings"] = key_findings_rollup
    flags = _rollup_flags(
        groups_unsectioned=groups_unsectioned,
        all_claims=all_claims,
        section_blocks=section_rollups,
        chunk_claims_rejected=total_chunk_rejections,
        claims_rejected_structural=total_structural_rejections,
        gap_claims_degraded=total_gap_degraded,
        span_bind_failures=total_span_bind_failures,
        unspanned_assertions=total_unspanned_assertions,
        turn_cap_hit=turn_cap_hit_any,
        repair_path_taken=repair_path_taken,
        repair_count_mismatch=repair_count_mismatch_any,
        repair_unparseable=repair_unparseable_any,
    )

    conn.execute(
        synthesis_result.insert().values(
            synthesis_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=context.scope_id,
            run_id=run_id,
            characterisation_run_id=refs.characterisation_run_id,
            selection_run_id=refs.selection_run_id,
            extraction_run_id=refs.extraction_run_id,
            grouping_run_id=refs.grouping_run_id,
            artefact_id=artefact_id,
            synthesis_provenance=provenance,
            blocks=section_rollups,
            counts=counts,
            flags=flags,
            created_at=created_at,
        )
    )
    log.info("synthesise.completed", blocks_written=len(blocks_written), flags=flags)
    return {
        "artefact_id": str(artefact_id),
        "section_count": len(sections),
        "counts": counts,
        "flags": flags,
        "substrate_profile": _substrate_profile(refs, corpus),
        "usage_totals": usage_totals.payload(),
    }


SUMMARY_REGENERATE_CAP = 2


def write_summaries_after_commit(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    synthesis_backend: SynthesisBackend,
) -> dict[str, Any]:
    """Write navigation summaries after the synthesise transaction commits.

    Every summary operates over persisted raw prose and annotations, and every
    status write owns a short transaction. This deliberately sits outside the
    component transaction: provider or summary-storage failure cannot roll back
    a grounded artefact or fail its run.

    Args:
        engine: Database engine used for independent summary transactions.
        project_id: Owning project.
        run_id: Completed synthesise run.
        synthesis_backend: Shared live or stub writer/judge seam.

    Returns:
        Summary call/usage accounting suitable for the component event. Details
        are persisted under ``synthesis_provenance.summaries``.
    """
    try:
        source = _summary_source(engine, project_id=project_id, run_id=run_id)
    except Exception as exc:  # noqa: BLE001 - summaries must never fail a run
        log.warning(
            "synthesise.summary_source_failed",
            project_id=str(project_id),
            run_id=str(run_id),
            error=type(exc).__name__,
        )
        return _empty_summary_accounting(source_error=True)
    if source is None:
        return _empty_summary_accounting(source_error=False)

    artefact_id, artefact_title, question, block_specs = source
    records: list[dict[str, Any]] = []
    totals = UsageAccumulator()
    call_counts = {"writer": 0, "judge": 0}
    consecutive_provider_failures = 0
    provider_disabled = False
    disabled_logged = False

    for spec in block_specs:
        if provider_disabled:
            records.append(
                {
                    "kind": "block",
                    "block_id": spec["block_id"],
                    "status": "failed",
                    "reason": "provider_disabled",
                    "writer_calls": 0,
                    "judge_calls": 0,
                    "usage_totals": UsageAccumulator().payload(),
                }
            )
            _safe_persist_summary_status(
                engine, target="block", target_id=uuid.UUID(spec["block_id"]), status="failed"
            )
            continue
        detail = _block_summary_detail(engine, spec)
        result = _write_and_judge_summary(
            synthesis_backend=synthesis_backend,
            seed=detail,
            detail=detail,
        )
        totals.add_payload(result["usage_totals"])
        call_counts["writer"] += result["writer_calls"]
        call_counts["judge"] += result["judge_calls"]
        if result["provider_failure"]:
            consecutive_provider_failures += 1
            status = "failed"
            summary = None
            if consecutive_provider_failures >= 2:
                provider_disabled = True
                if not disabled_logged:
                    log.warning(
                        "synthesise.summary_provider_disabled",
                        project_id=str(project_id),
                        run_id=str(run_id),
                    )
                    disabled_logged = True
        else:
            consecutive_provider_failures = 0
            status = result["status"]
            summary = result["summary"]
        record = {
            "kind": "block",
            "block_id": spec["block_id"],
            "status": status,
            "reason": result["reason"],
            "writer_calls": result["writer_calls"],
            "judge_calls": result["judge_calls"],
            "usage_totals": result["usage_totals"],
        }
        records.append(record)
        _safe_persist_summary_status(
            engine,
            target="block",
            target_id=uuid.UUID(spec["block_id"]),
            status=status,
            summary=summary,
        )

    artefact_detail = _artefact_summary_detail(
        title=artefact_title,
        question=question,
        block_specs=block_specs,
        engine=engine,
    )
    if provider_disabled:
        artefact_result = _disabled_summary_result("provider_disabled")
    else:
        artefact_seed = {"kind": "artefact", **artefact_detail}
        artefact_result = _write_and_judge_summary(
            synthesis_backend=synthesis_backend,
            seed=artefact_seed,
            detail=artefact_detail,
        )
        totals.add_payload(artefact_result["usage_totals"])
        call_counts["writer"] += artefact_result["writer_calls"]
        call_counts["judge"] += artefact_result["judge_calls"]
        if artefact_result["provider_failure"]:
            consecutive_provider_failures += 1
            if consecutive_provider_failures >= 2 and not disabled_logged:
                log.warning(
                    "synthesise.summary_provider_disabled",
                    project_id=str(project_id),
                    run_id=str(run_id),
                )
                disabled_logged = True
    artefact_status = "failed" if artefact_result["provider_failure"] else artefact_result["status"]
    artefact_summary = None if artefact_status == "failed" else artefact_result["summary"]
    records.append(
        {
            "kind": "artefact",
            "artefact_id": str(artefact_id),
            "status": artefact_status,
            "reason": artefact_result["reason"],
            "writer_calls": artefact_result["writer_calls"],
            "judge_calls": artefact_result["judge_calls"],
            "usage_totals": artefact_result["usage_totals"],
        }
    )
    _safe_persist_summary_status(
        engine,
        target="artefact",
        target_id=artefact_id,
        status=artefact_status,
        summary=artefact_summary,
    )

    accounting = {
        "prompt_versions": {
            "summariser": SUMMARISER_PROMPT_VERSION,
            "judge": SUMMARY_JUDGE_PROMPT_VERSION,
        },
        "call_counts": call_counts,
        "usage_totals": totals.payload(),
        "per_summary": records,
        "provider_disabled": provider_disabled,
    }
    _persist_summary_provenance(
        engine, project_id=project_id, run_id=run_id, accounting=accounting
    )
    return accounting


def _empty_summary_accounting(*, source_error: bool) -> dict[str, Any]:
    return {
        "prompt_versions": {
            "summariser": SUMMARISER_PROMPT_VERSION,
            "judge": SUMMARY_JUDGE_PROMPT_VERSION,
        },
        "call_counts": {"writer": 0, "judge": 0},
        "usage_totals": UsageAccumulator().payload(),
        "per_summary": [],
        "provider_disabled": False,
        "source_error": source_error,
    }


def _summary_source(
    engine: Engine, *, project_id: uuid.UUID, run_id: uuid.UUID
) -> tuple[uuid.UUID, str, str, list[dict[str, str]]] | None:
    with engine.connect() as conn:
        row = conn.execute(
            sa_select(
                synthesis_result.c.artefact_id,
                artefact.c.title,
                evidence_scope.c.intent,
                synthesis_result.c.blocks,
            )
            .select_from(
                synthesis_result.join(
                    artefact, artefact.c.artefact_id == synthesis_result.c.artefact_id
                ).join(
                    evidence_scope,
                    evidence_scope.c.evidence_scope_id == synthesis_result.c.evidence_scope_id,
                )
            )
            .where(synthesis_result.c.project_id == project_id)
            .where(synthesis_result.c.run_id == run_id)
        ).first()
    if row is None:
        return None
    raw_blocks = row.blocks if isinstance(row.blocks, list) else []
    specs = [
        {
            "block_id": item["block_id"],
            "title": item.get("title", ""),
            "role": item.get("role", "standard"),
        }
        for item in raw_blocks
        if isinstance(item, dict) and isinstance(item.get("block_id"), str)
    ]
    return row.artefact_id, row.title, row.intent, specs


def _block_summary_detail(engine: Engine, spec: dict[str, str]) -> dict[str, Any]:
    block_id = uuid.UUID(spec["block_id"])
    with engine.connect() as conn:
        prose = conn.execute(
            sa_select(block.c.content).where(block.c.block_id == block_id)
        ).scalar_one()
        annotations = conn.execute(
            sa_select(
                addressable_unit.c.content,
                annotation.c.annotation_type,
                annotation.c.payload,
            )
            .select_from(
                annotation.join(
                    addressable_unit,
                    (addressable_unit.c.block_id == annotation.c.block_id)
                    & (addressable_unit.c.unit_id == annotation.c.unit_id),
                )
            )
            .where(annotation.c.block_id == block_id)
            .order_by(annotation.c.created_at, annotation.c.annotation_id)
        ).all()
    epistemic_annotations: list[dict[str, Any]] = []
    for row in annotations:
        payload = dict(row.payload) if isinstance(row.payload, dict) else {}
        flags: list[str] = []
        if payload.get("weakly_grounded"):
            flags.append("weakly_grounded")
        if payload.get("verdict") == "unsupported_mis_cited":
            flags.append("unsupported_mis_cited")
        if row.annotation_type == "gap" or payload.get("gap") is not None:
            flags.append("gap")
        epistemic_annotations.append(
            {
                "text": row.content,
                "annotation_type": row.annotation_type,
                "verdict": payload.get("verdict"),
                "flags": flags,
                "gap": payload.get("gap"),
                "payload": payload,
            }
        )
    return {
        "title": spec["title"],
        "role": spec["role"],
        "prose": prose,
        "epistemic_annotations": epistemic_annotations,
    }


def _artefact_summary_detail(
    *,
    title: str,
    question: str,
    block_specs: Sequence[dict[str, str]],
    engine: Engine,
) -> dict[str, Any]:
    blocks = [_block_summary_detail(engine, spec) for spec in block_specs]
    return {
        "title": title,
        "question": question,
        "sections": [
            {"title": spec["title"], "role": spec["role"]} for spec in block_specs
        ],
        "conclusion_bearing_blocks": [
            detail for detail in blocks if detail["role"] in {"key_findings", "conclusions"}
        ],
    }


# Deterministic floor under the judge (review 028): the prompt's length and
# no-citations rules were instruction-only, so a faithful-but-oversized or
# citation-carrying summary could persist as verified. Ceilings run 1.5x the
# prompt's ask — a hard stop for the pathological case, not a style check.
_SUMMARY_CITATION_RE = re.compile(r"\[\d+\]")
_SUMMARY_LENGTH_CEILING = {"artefact": 750}
_SUMMARY_LENGTH_CEILING_DEFAULT = 300


def _summary_format_violation(summary: str, *, seed: dict[str, Any]) -> str | None:
    """Return the deterministic-format failure reason, or ``None`` when clean."""
    ceiling = _SUMMARY_LENGTH_CEILING.get(str(seed.get("kind")), _SUMMARY_LENGTH_CEILING_DEFAULT)
    if len(summary) > ceiling:
        return "over_length"
    if _SUMMARY_CITATION_RE.search(summary):
        return "citation_markers"
    return None


def _write_and_judge_summary(
    *,
    synthesis_backend: SynthesisBackend,
    seed: dict[str, Any],
    detail: dict[str, Any],
) -> dict[str, Any]:
    totals = UsageAccumulator()
    writer_calls = 0
    judge_calls = 0
    for attempt in range(SUMMARY_REGENERATE_CAP + 1):
        try:
            emitted, usage = synthesis_backend.write_block_summary(seed)
            writer_calls += 1
            totals.add(usage)
            format_reason = _summary_format_violation(emitted.summary, seed=seed)
            if format_reason is not None:
                log.warning("synthesise.summary_format_violation", reason=format_reason)
                if attempt < SUMMARY_REGENERATE_CAP:
                    continue
                return {
                    "status": "failed",
                    "summary": None,
                    "reason": format_reason,
                    "provider_failure": False,
                    "writer_calls": writer_calls,
                    "judge_calls": judge_calls,
                    "usage_totals": totals.payload(),
                }
            verdict, usage = synthesis_backend.judge_summary(
                summary=emitted.summary, detail=detail
            )
            judge_calls += 1
            totals.add(usage)
        except Exception as exc:  # noqa: BLE001 - provider failure must degrade
            log.warning("synthesise.summary_provider_failure", error=type(exc).__name__)
            return {
                "status": "failed",
                "summary": None,
                "reason": "provider_failure",
                "provider_failure": True,
                "writer_calls": writer_calls,
                "judge_calls": judge_calls,
                "usage_totals": totals.payload(),
            }
        if verdict.verdict == "pass":
            return {
                "status": "verified",
                "summary": emitted.summary,
                "reason": verdict.reason,
                "provider_failure": False,
                "writer_calls": writer_calls,
                "judge_calls": judge_calls,
                "usage_totals": totals.payload(),
            }
        if attempt < SUMMARY_REGENERATE_CAP:
            continue
        return {
            "status": "failed",
            "summary": None,
            "reason": verdict.reason,
            "provider_failure": False,
            "writer_calls": writer_calls,
            "judge_calls": judge_calls,
            "usage_totals": totals.payload(),
        }
    raise AssertionError("summary retry loop must return")


def _disabled_summary_result(reason: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "summary": None,
        "reason": reason,
        "provider_failure": False,
        "writer_calls": 0,
        "judge_calls": 0,
        "usage_totals": UsageAccumulator().payload(),
    }


def _persist_summary_status(
    engine: Engine,
    *,
    target: str,
    target_id: uuid.UUID,
    status: str,
    summary: str | None = None,
) -> None:
    try:
        with engine.begin() as conn:
            table = block if target == "block" else artefact
            identifier = table.c.block_id if target == "block" else table.c.artefact_id
            conn.execute(
                sa_update(table)
                .where(identifier == target_id)
                .values(summary=summary if status == "verified" else None, summary_status=status)
            )
    except Exception as exc:  # noqa: BLE001 - isolate one summary transaction
        log.warning(
            "synthesise.summary_persist_failed",
            target=target,
            target_id=str(target_id),
            error=type(exc).__name__,
        )


def _safe_persist_summary_status(
    engine: Engine,
    *,
    target: str,
    target_id: uuid.UUID,
    status: str,
    summary: str | None = None,
) -> None:
    """Contain unexpected status-transaction faults to one summary target."""
    try:
        _persist_summary_status(
            engine,
            target=target,
            target_id=target_id,
            status=status,
            summary=summary,
        )
    except Exception as exc:  # noqa: BLE001 - one summary cannot stop the rest
        log.warning(
            "synthesise.summary_persist_failed",
            target=target,
            target_id=str(target_id),
            error=type(exc).__name__,
        )


def _persist_summary_provenance(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    accounting: dict[str, Any],
) -> None:
    try:
        with engine.begin() as conn:
            row = conn.execute(
                sa_select(synthesis_result.c.synthesis_provenance)
                .where(synthesis_result.c.project_id == project_id)
                .where(synthesis_result.c.run_id == run_id)
            ).first()
            if row is None:
                return
            provenance = dict(row.synthesis_provenance)
            provenance["summaries"] = accounting
            conn.execute(
                sa_update(synthesis_result)
                .where(synthesis_result.c.project_id == project_id)
                .where(synthesis_result.c.run_id == run_id)
                .values(synthesis_provenance=provenance)
            )
    except Exception as exc:  # noqa: BLE001 - summary provenance cannot fail a run
        log.warning(
            "synthesise.summary_provenance_persist_failed",
            project_id=str(project_id),
            run_id=str(run_id),
            error=type(exc).__name__,
        )
