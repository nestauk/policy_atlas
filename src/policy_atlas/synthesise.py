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
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

import structlog
from sqlalchemy import case as sa_case
from sqlalchemy import select as sa_select
from sqlalchemy.engine import Connection

from policy_atlas.grounding import content_hash
from policy_atlas.grounding_judge import (
    ENVELOPE_VERSION,
    JUDGE_MODEL,
    JUDGE_PROMPT_VERSION,
    GroundingJudgeBackend,
    build_envelope,
)
from policy_atlas.quote_verify import BasisText, QuoteMatcher, build_basis
from policy_atlas.schema import (
    addressable_unit,
    annotation,
    artefact,
    block,
    characterisation_result,
    extraction_result,
    grouping_result,
    intervention_outcome_finding,
    project_source_snapshot,
    search_coverage_record,
    selection_result,
    source_appraisal_result,
    source_extraction_record,
    source_screening_result,
    source_snapshot,
    synthesis_result,
)
from policy_atlas.schema import chunk as chunk_table
from policy_atlas.schema import citation as citation_table
from policy_atlas.synthesis_backend import (
    FORBIDDEN_SECTION_TITLES,
    SECTION_FOCUS_MAX,
    SECTION_PROMPT_VERSION,
    SECTION_TITLE_MAX,
    SECTION_TOOL_SCHEMAS,
    SECTIONS_PROMPT_VERSION,
    SYNTHESIS_MODEL,
    ClaimWire,
    SectionClaimsWire,
    SectionProposalWire,
    SynthesisBackend,
)
from policy_atlas.synthesis_tools import (
    ARTEFACT_TITLE_MAX,
    REASONING_CLAIMS_MAX,
    REPAIR_ROUND_CAP,
    RETRIEVAL_UNIT_CAP,
    SECTION_CAP,
    SECTION_TURN_CAP,
    SYNTH_CHUNK_CHAR_BUDGET,
    SYNTH_CHUNK_TOP_K,
    ChunkRetriever,
    PassThroughChunkReranker,
    RetrievalUnitCapError,
    SynthesisDirectiveError,
    ToolExchange,
    build_retrieval_scope,
    build_section_tools,
    gathered_ids,
    make_findings_reader,
    make_lookup_reader,
    parse_synthesis_directive,
    run_section_loop,
)
from policy_atlas.tags import has_control_character

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
    origin: str
    appraised: bool


@dataclass(frozen=True)
class FindingInfo:
    """One extracted finding plus the data required for synthesis validation."""

    finding_id: str
    pss_id: str
    source_snapshot_id: str
    record: dict[str, Any]
    grounding: list[dict[str, Any]]
    effect_direction: str


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
    basis_by_snapshot_id: dict[str, BasisText]
    selected_pss_ids: set[str]

    @property
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

    @property
    def grouping_group_ids(self) -> set[str]:
        """Return real grouping ids from the persisted grouping payload."""
        if self.grouping is None:
            return set()
        raw_groups = self.grouping.get("groups", [])
        if not isinstance(raw_groups, list):
            return set()
        ids: set[str] = set()
        for group in raw_groups:
            group_id = _group_id(group)
            if group_id is not None:
                ids.add(group_id)
        return ids

    @property
    def group_by_id(self) -> dict[str, dict[str, Any]]:
        """Return grouping records keyed by real group id."""
        if self.grouping is None:
            return {}
        raw_groups = self.grouping.get("groups", [])
        if not isinstance(raw_groups, list):
            return {}
        result: dict[str, dict[str, Any]] = {}
        for group in raw_groups:
            if not isinstance(group, dict):
                continue
            group_id = _group_id(group)
            if group_id is not None:
                result[group_id] = group
        return result

    @property
    def extraction_direction_spread(self) -> dict[str, int]:
        """Compute effect-direction spread over all referenced extraction findings."""
        counts: Counter[str] = Counter()
        for finding in self.finding_by_id.values():
            counts[finding.effect_direction] += 1
        return dict(sorted(counts.items()))


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


@dataclass(frozen=True)
class RejectedClaim:
    """A claim rejected by deterministic validation."""

    claim_id: str
    claim_index: int
    claim: ClaimWire
    reason: str
    structural: bool = True
    chunk_quote_failed: bool = False


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
    chunk_claims_rejected: int = 0
    claims_rejected_structural: int = 0
    gap_claims_degraded: int = 0


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
    """Return the binding maximum generation-call count for this slice."""
    return 2 + SECTION_CAP * (SECTION_TURN_CAP + 3)


def build_ledger(claims: Sequence[ClaimDraft]) -> list[dict[str, Any]]:
    """Build the rolling prior-section ledger.

    Args:
        claims: Persisted claims from prior sections, in write order.

    Returns:
        Claim records marked as context-only and never citable evidence.
    """
    return [
        {
            "claim_id": claim.claim_id,
            "claim_type": claim.claim_type,
            "text": claim.text,
            "cited_ids": list(claim.cited_ids),
            "flags": list(claim.flags),
            "ledger_note": "context, never evidence — not citable",
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
    claim_ids: Sequence[str] | None = None,
    claim_indices: Sequence[int] | None = None,
    available_claim_types: set[str] | None = None,
) -> ClaimValidationBatch:
    """Validate emitted claims against an in-memory substrate view.

    Args:
        claims: Raw wire claims from the synthesis backend.
        substrate: In-memory substrate view.
        section_index: Zero-based section index for default claim ids.
        section_group_ids: Group ids assigned to this section.
        citable_finding_ids: Finding ids seeded or returned by this section.
        citable_chunk_ids: Chunk ids returned by this section.
        claim_ids: Optional explicit ids, used for repair replacements.
        claim_indices: Optional original slot indices, used for repair ordering.
        available_claim_types: Optional claim-type gate. When omitted, it is
            computed from the substrate.

    Returns:
        Validated drafts and rejected claims.
    """
    available = available_claim_types or available_claim_types_for_substrate(substrate)
    drafts: list[ClaimDraft] = []
    rejected: list[RejectedClaim] = []
    reasoning_count = 0
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
        )
        if isinstance(result, RejectedClaim):
            rejected.append(result)
        else:
            drafts.append(result)
    return ClaimValidationBatch(drafts=drafts, rejected=rejected)


def available_claim_types_for_substrate(substrate: SubstrateView) -> set[str]:
    """Return claim types currently gated on by the substrate."""
    claim_types = {"gap", "reasoning"}
    if substrate.extraction is not None:
        claim_types.add("finding")
    if substrate.corpus.appraised_ingested_docs > 0:
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
    for key in ("group_id", "id", "label"):
        value = group.get(key)
        if isinstance(value, str) and value:
            return value
    return None


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
        extraction_run_id = resolved_extraction
        how["extraction"] = "transitive:grouping"

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
        selection_run_id = resolved_selection
        how["selection"] = "transitive:extraction"

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
        characterisation_run_id = resolved_characterisation
        how["characterisation"] = "transitive:selection"

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
    relevant_rows = conn.execute(
        sa_select(
            project_source_snapshot.c.project_source_snapshot_id,
            project_source_snapshot.c.full_text_status,
            source_snapshot.c.text_basis,
            source_appraisal_result.c.source_appraisal_result_id,
        )
        .select_from(source_screening_result)
        .join(
            project_source_snapshot,
            (
                project_source_snapshot.c.project_source_snapshot_id
                == source_screening_result.c.project_source_snapshot_id
            )
            & (project_source_snapshot.c.project_id == source_screening_result.c.project_id),
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
        .where(source_screening_result.c.project_id == project_id)
        .where(source_screening_result.c.evidence_scope_id == scope_id)
        .where(source_screening_result.c.status == "relevant")
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


def _basis_for_snapshot(conn: Connection, source_snapshot_id: uuid.UUID) -> BasisText:
    rows = conn.execute(
        sa_select(chunk_table.c.chunk_id, chunk_table.c.content)
        .where(chunk_table.c.source_snapshot_id == source_snapshot_id)
        .order_by(chunk_table.c.sequence, chunk_table.c.chunk_id)
    ).fetchall()
    if rows:
        return build_basis([(str(row.chunk_id), cast("str", row.content)) for row in rows])
    snapshot = conn.execute(
        sa_select(source_snapshot.c.metadata)
        .where(source_snapshot.c.source_snapshot_id == source_snapshot_id)
    ).mappings().one()
    metadata = snapshot["metadata"] if isinstance(snapshot["metadata"], dict) else {}
    abstract = metadata.get("abstract")
    return build_basis([(None, abstract if isinstance(abstract, str) else "")])


def _load_screened_chunks(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    selected_pss_ids: set[str],
    appraised_pss_ids: set[str],
) -> tuple[dict[str, ChunkInfo], dict[str, list[ChunkInfo]], dict[str, BasisText]]:
    # The text-bearing snapshot per document: the fetched full-text snapshot when
    # the fetch pipeline ingested one, else the envelope snapshot when it carries
    # full text itself (uploads — chunked at upload ingest). full_text_status is
    # fetch-pipeline state, never text availability (schema comment).
    text_snapshot_id = sa_case(
        (
            project_source_snapshot.c.full_text_status == "ingested",
            project_source_snapshot.c.full_text_snapshot_id,
        ),
        else_=project_source_snapshot.c.source_snapshot_id,
    )
    rows = conn.execute(
        sa_select(
            project_source_snapshot.c.project_source_snapshot_id,
            chunk_table.c.chunk_id,
            chunk_table.c.source_snapshot_id,
            chunk_table.c.sequence,
            chunk_table.c.content,
            chunk_table.c.segmentation_policy,
        )
        .select_from(source_screening_result)
        .join(
            project_source_snapshot,
            (
                project_source_snapshot.c.project_source_snapshot_id
                == source_screening_result.c.project_source_snapshot_id
            )
            & (project_source_snapshot.c.project_id == source_screening_result.c.project_id),
        )
        .join(
            source_snapshot,
            source_snapshot.c.source_snapshot_id
            == project_source_snapshot.c.source_snapshot_id,
        )
        .join(chunk_table, chunk_table.c.source_snapshot_id == text_snapshot_id)
        .where(source_screening_result.c.project_id == project_id)
        .where(source_screening_result.c.evidence_scope_id == scope_id)
        .where(source_screening_result.c.status == "relevant")
        .where(
            (project_source_snapshot.c.full_text_status == "ingested")
            | (source_snapshot.c.text_basis == "full_text")
        )
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


def _extraction_record_ids(extraction_row: Mapping[str, Any] | None) -> list[uuid.UUID]:
    if extraction_row is None:
        return []
    docs = extraction_row.get("docs")
    if not isinstance(docs, list):
        return []
    ids: list[uuid.UUID] = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        raw_id = doc.get("extraction_record_id")
        if not isinstance(raw_id, str):
            continue
        try:
            ids.append(uuid.UUID(raw_id))
        except ValueError:
            continue
    return ids


def _load_findings(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    extraction_row: Mapping[str, Any] | None,
) -> tuple[dict[str, FindingInfo], dict[str, BasisText]]:
    record_ids = _extraction_record_ids(extraction_row)
    if not record_ids:
        return {}, {}
    rows = conn.execute(
        sa_select(
            intervention_outcome_finding.c.finding_id,
            intervention_outcome_finding.c.intervention,
            intervention_outcome_finding.c.outcome,
            intervention_outcome_finding.c.population,
            intervention_outcome_finding.c.comparator,
            intervention_outcome_finding.c.effect_direction,
            intervention_outcome_finding.c.estimate_level,
            intervention_outcome_finding.c.study_design,
            intervention_outcome_finding.c.stratum_qualifiers,
            intervention_outcome_finding.c.statistics,
            intervention_outcome_finding.c.causality_by_design,
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
            source_snapshot.c.source_snapshot_id == source_extraction_record.c.source_snapshot_id,
        )
        .where(intervention_outcome_finding.c.project_id == project_id)
        .where(intervention_outcome_finding.c.extraction_record_id.in_(record_ids))
        .order_by(
            source_extraction_record.c.extraction_record_id,
            intervention_outcome_finding.c.finding_id,
        )
    ).fetchall()
    findings: dict[str, FindingInfo] = {}
    basis_by_snapshot: dict[str, BasisText] = {}
    for row in rows:
        pss_id = str(row.project_source_snapshot_id)
        metadata = row.metadata if isinstance(row.metadata, dict) else {}
        title = metadata.get("title")
        finding_id = str(row.finding_id)
        source_snapshot_id = cast("uuid.UUID", row.source_snapshot_id)
        basis_key = str(source_snapshot_id)
        if basis_key not in basis_by_snapshot:
            basis_by_snapshot[basis_key] = _basis_for_snapshot(conn, source_snapshot_id)
        grounding = row.grounding if isinstance(row.grounding, list) else []
        record = {
            "finding_id": finding_id,
            "pss_id": pss_id,
            "document_title": title if isinstance(title, str) and title else f"source {pss_id}",
            "intervention": row.intervention,
            "outcome": row.outcome,
            "population": row.population,
            "comparator": row.comparator,
            "effect_direction": row.effect_direction,
            "estimate_level": row.estimate_level,
            "study_design": row.study_design,
            "stratum_qualifiers": row.stratum_qualifiers,
            "statistics": row.statistics,
            "causality_by_design": row.causality_by_design,
            "is_primary": row.is_primary,
            "field_coverage": row.field_coverage,
        }
        findings[finding_id] = FindingInfo(
            finding_id=finding_id,
            pss_id=pss_id,
            source_snapshot_id=basis_key,
            record=record,
            grounding=cast("list[dict[str, Any]]", grounding),
            effect_direction=cast("str", row.effect_direction),
        )
    return findings, basis_by_snapshot


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
    raw_groups = payload.get("groups", []) if isinstance(payload, dict) else []
    groups: list[dict[str, Any]] = []
    if isinstance(raw_groups, list):
        for item in raw_groups:
            if not isinstance(item, dict):
                continue
            members = item.get("member_finding_ids", [])
            if not isinstance(members, list):
                members = []
            groups.append(
                {
                    "group_id": _group_id(item),
                    "label": item.get("label"),
                    "description": item.get("description"),
                    "size": item.get("size", len(members)),
                    "direction_spread": item.get("direction_spread", {}),
                    "member_finding_ids": sorted(str(member) for member in members),
                }
            )
    residuals: dict[str, Any] = {}
    if isinstance(payload, dict):
        residuals = {
            "ungrouped": payload.get("ungrouped", {}),
            "no_value": payload.get("no_value", {}),
        }
    return {"facet": row.get("facet"), "groups": groups, "residuals": residuals}


def _substrate_summaries(refs: ResolvedReferences, corpus: CorpusProfile) -> dict[str, Any]:
    summaries: dict[str, Any] = {
        "corpus": {
            "screened": corpus.screened_docs,
            "ingested": corpus.ingested_docs,
            "appraised": corpus.appraised_docs,
        }
    }
    char_summary = _characterisation_summary(refs.characterisation_row)
    if char_summary is not None:
        summaries["characterisation"] = char_summary
    selection_summary = _selection_summary(refs.selection_row)
    if selection_summary is not None:
        summaries["selection"] = selection_summary
    extraction_summary = _extraction_summary(refs.extraction_row)
    if extraction_summary is not None:
        summaries["extraction"] = extraction_summary
    grouping_summary = _grouping_summary(refs.grouping_row)
    if grouping_summary is not None:
        summaries["grouping"] = grouping_summary
    return summaries


def _substrate_view(
    *,
    refs: ResolvedReferences,
    corpus: CorpusProfile,
    coverage_records: dict[str, CoverageRecord],
    chunk_by_id: dict[str, ChunkInfo],
    chunks_by_pss_id: dict[str, list[ChunkInfo]],
    finding_by_id: dict[str, FindingInfo],
    basis_by_snapshot_id: dict[str, BasisText],
    selected_pss_ids: set[str],
) -> SubstrateView:
    return SubstrateView(
        characterisation=_characterisation_summary(refs.characterisation_row),
        selection=_selection_summary(refs.selection_row),
        extraction=_extraction_summary(refs.extraction_row),
        grouping=_grouping_summary(refs.grouping_row),
        corpus=corpus,
        coverage_records=coverage_records,
        chunk_by_id=chunk_by_id,
        chunks_by_pss_id=chunks_by_pss_id,
        finding_by_id=finding_by_id,
        basis_by_snapshot_id=basis_by_snapshot_id,
        selected_pss_ids=selected_pss_ids,
    )


def _validate_sections(
    proposal: SectionProposalWire,
    *,
    grouping_group_ids: set[str] | None,
) -> tuple[list[SectionSpec], list[str]]:
    reasons: list[str] = []
    sections = proposal.sections
    if not 1 <= len(sections) <= SECTION_CAP:
        reasons.append(f"section_count_out_of_range: 1..{SECTION_CAP}")
    forbidden = {title.casefold() for title in FORBIDDEN_SECTION_TITLES}
    seen_titles: set[str] = set()
    parsed: list[SectionSpec] = []
    for index, section in enumerate(sections):
        title = section.title
        focus = section.focus
        if not title or len(title) > SECTION_TITLE_MAX or has_control_character(title):
            reasons.append(f"sections[{index}].title_invalid")
        if title.casefold() in forbidden:
            reasons.append(f"sections[{index}].title_forbidden")
        folded = title.casefold()
        if folded in seen_titles:
            reasons.append(f"sections[{index}].title_duplicate")
        seen_titles.add(folded)
        if not focus or len(focus) > SECTION_FOCUS_MAX or has_control_character(focus):
            reasons.append(f"sections[{index}].focus_invalid")
        group_ids = list(section.group_ids)
        # Reasons are the repair call's instructions (fed back verbatim as
        # data) — instructive sentences, not bare codes, or the repair repeats
        # the mistake.
        if grouping_group_ids is None and group_ids:
            reasons.append(
                f"sections[{index}].group_ids_without_grouping: no facet "
                "grouping is referenced on this run, so group_ids must be "
                "omitted entirely (an empty list); characterisation theme ids "
                "are not group ids"
            )
        elif grouping_group_ids is not None:
            unknown = sorted(set(group_ids) - grouping_group_ids)
            if unknown:
                reasons.append(
                    f"sections[{index}].group_ids_unknown: {unknown[:5]} are "
                    "not supplied facet group ids — copy ids exactly from the "
                    "grouping records, or omit group_ids"
                )
        parsed.append(SectionSpec(title=title, focus=focus, group_ids=group_ids))
    return parsed, reasons


def _sections_from_directive(sections: list[dict[str, Any]]) -> list[SectionSpec]:
    return [
        SectionSpec(
            title=cast("str", section["title"]),
            focus=cast("str", section["focus"]),
            group_ids=list(cast("list[str]", section.get("group_ids", []))),
        )
        for section in sections
    ]


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
) -> RejectedClaim:
    return RejectedClaim(
        claim_id=claim_id,
        claim_index=claim_index,
        claim=claim,
        reason=reason,
        structural=structural,
        chunk_quote_failed=chunk_quote_failed,
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
            claim, claim_id=claim_id, claim_index=claim_index, substrate=substrate
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
    anchors_payload: list[dict[str, Any]] = []
    citation_rows: list[CitationDraft] = []
    judge_chunk_ids: set[str] = set()
    flags: list[str] = []
    for finding_id in claim.cited_finding_ids:
        finding = substrate.finding_by_id.get(finding_id)
        if finding is None:
            return _reject(
                claim,
                claim_id=claim_id,
                claim_index=claim_index,
                reason="unknown_finding_id",
            )
        basis = substrate.basis_by_snapshot_id.get(finding.source_snapshot_id)
        if basis is None:
            return _reject(
                claim,
                claim_id=claim_id,
                claim_index=claim_index,
                reason="finding_basis_missing",
            )
        matcher = QuoteMatcher(basis)
        for grounding in finding.grounding:
            quote = grounding.get("quote")
            if not isinstance(quote, str) or not quote:
                flags.append("quote_unverified")
                anchors_payload.append(
                    {
                        "finding_id": finding_id,
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
                "quote": quote,
                "match_status": match.status,
                "spans": spans_payload,
            }
            if match.status == "failed" or not match.spans:
                flags.append("quote_unverified")
                anchors_payload.append(anchor_record)
                continue
            for span in match.spans:
                if span.chunk_id is None:
                    continue
                chunk = substrate.chunk_by_id.get(span.chunk_id)
                if chunk is None:
                    continue
                judge_chunk_ids.add(span.chunk_id)
                citation_rows.append(
                    CitationDraft(
                        chunk_id=span.chunk_id,
                        quote=quote,
                        origin=chunk.origin,
                        match_status=match.status,
                        spans=[
                            {"chunk_id": span.chunk_id, "start": span.start, "end": span.end}
                        ],
                    )
                )
            anchors_payload.append(anchor_record)
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
    if substrate.corpus.appraised_ingested_docs <= 0:
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
        chunks = substrate.chunks_by_pss_id.get(chunk.pss_id, [])
        if not chunks:
            return _reject(
                claim,
                claim_id=claim_id,
                claim_index=claim_index,
                reason="chunk_basis_missing",
            )
        basis = build_basis([(item.chunk_id, item.content) for item in chunks])
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
        span_records: list[dict[str, Any]] = []
        for span in match.spans:
            if span.chunk_id is None:
                continue
            spanned_chunk = substrate.chunk_by_id.get(span.chunk_id)
            if spanned_chunk is None:
                continue
            judge_chunk_ids.add(span.chunk_id)
            span_payload = {
                "chunk_id": span.chunk_id,
                "start": span.start,
                "end": span.end,
                "origin": spanned_chunk.origin,
            }
            span_records.append(span_payload)
            citation_rows.append(
                CitationDraft(
                    chunk_id=span.chunk_id,
                    quote=quote,
                    origin=spanned_chunk.origin,
                    match_status=match.status,
                    spans=[span_payload],
                )
            )
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


def _validate_gap_claim(
    claim: ClaimWire,
    *,
    claim_id: str,
    claim_index: int,
    substrate: SubstrateView,
) -> ClaimDraft | RejectedClaim:
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
) -> int:
    judged = [claim for claim in claims if claim.claim_type in JUDGED_TYPES]
    if not judged:
        return 0
    envelope_claims: list[dict[str, Any]] = []
    chunk_ids: set[str] = set()
    for claim in judged:
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
    chunks = [
        {
            "chunk_record_id": chunk_id,
            "segmentation_policy": substrate.chunk_by_id[chunk_id].segmentation_policy,
            "content": substrate.chunk_by_id[chunk_id].content,
        }
        for chunk_id in sorted(chunk_ids)
        if chunk_id in substrate.chunk_by_id
    ]
    envelope = build_envelope(claims=envelope_claims, chunks=chunks)
    response = grounding_judge_backend.judge_block(envelope)
    verdicts = response.verdicts
    expected = {claim.claim_id for claim in judged}
    actual = {verdict.claim_id for verdict in verdicts}
    if expected != actual:
        raise SynthesiseFailure("judge_coverage_invalid")
    by_id = {verdict.claim_id: verdict for verdict in verdicts}
    judge_io_ref = _json_sha256(
        {"envelope": envelope, "verdicts": response.model_dump(mode="json")}
    )
    for claim in judged:
        verdict = by_id[claim.claim_id]
        claim.verdict = verdict.verdict
        claim.weakly_grounded = claim.weakly_grounded or verdict.weakly_grounded
        claim.rationale = verdict.rationale
        claim.judge_io_ref = judge_io_ref
    return 1


def _failing_records(
    rejected: Sequence[RejectedClaim],
    drafts: Sequence[ClaimDraft],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for rejection in rejected:
        claim_data = rejection.claim.model_dump(mode="json")
        records.append(
            {
                "claim_id": rejection.claim_id,
                "claim_index": rejection.claim_index,
                "claim": claim_data,
                "reason": rejection.reason,
                "rationale": rejection.reason,
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
                }
            )
    return sorted(records, key=lambda item: (int(item["claim_index"]), str(item["claim_id"])))


def _replacement_validation(
    replacements: SectionClaimsWire,
    *,
    failing: Sequence[dict[str, Any]],
    substrate: SubstrateView,
    section_index: int,
    section_group_ids: set[str],
    citable_finding_ids: set[str],
    citable_chunk_ids: set[str],
    available_claim_types: set[str],
) -> ClaimValidationBatch:
    claim_ids = [str(item["claim_id"]) for item in failing]
    claim_indices = [int(item["claim_index"]) for item in failing]
    return validate_claims(
        replacements.claims[: len(failing)],
        substrate=substrate,
        section_index=section_index,
        section_group_ids=section_group_ids,
        citable_finding_ids=citable_finding_ids,
        citable_chunk_ids=citable_chunk_ids,
        claim_ids=claim_ids,
        claim_indices=claim_indices,
        available_claim_types=available_claim_types,
    )


def _finalize_claims(
    *,
    initial: ClaimValidationBatch,
    replacements: ClaimValidationBatch | None,
    failing: Sequence[dict[str, Any]],
    accounting: SectionAccounting,
) -> list[ClaimDraft]:
    by_index = {draft.claim_index: draft for draft in initial.drafts}
    initial_rejections = {rejection.claim_index: rejection for rejection in initial.rejected}
    failing_indices = [int(item["claim_index"]) for item in failing]
    if replacements is not None:
        replacement_drafts = {draft.claim_index: draft for draft in replacements.drafts}
        replacement_rejections = {
            rejection.claim_index: rejection for rejection in replacements.rejected
        }
        for index in failing_indices:
            if index in replacement_drafts:
                by_index[index] = replacement_drafts[index]
                continue
            if index in by_index:
                # An originally valid but unsupported claim still has honest
                # persistence as an unsupported claim if repair fails structurally.
                continue
            rejection = replacement_rejections.get(index) or initial_rejections.get(index)
            if rejection is not None:
                _count_exclusion(rejection, accounting=accounting)
    else:
        for rejection in initial.rejected:
            _count_exclusion(rejection, accounting=accounting)
    return [by_index[index] for index in sorted(by_index)]


def _count_exclusion(rejection: RejectedClaim, *, accounting: SectionAccounting) -> None:
    if rejection.chunk_quote_failed:
        accounting.chunk_claims_rejected += 1
    else:
        accounting.claims_rejected_structural += 1


def _section_claims(
    *,
    section_index: int,
    raw_claims: SectionClaimsWire,
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
) -> tuple[list[ClaimDraft], dict[str, int]]:
    call_counts = {"judge": 0, "repair": 0, "rejudge": 0}
    initial = validate_claims(
        raw_claims.claims,
        substrate=substrate,
        section_index=section_index,
        section_group_ids=section_group_ids,
        citable_finding_ids=citable_finding_ids,
        citable_chunk_ids=citable_chunk_ids,
        available_claim_types=available_claim_types,
    )
    call_counts["judge"] += _judge_claims(
        claims=initial.drafts,
        substrate=substrate,
        grounding_judge_backend=grounding_judge_backend,
    )
    failing = _failing_records(initial.rejected, initial.drafts)
    replacements: ClaimValidationBatch | None = None
    if failing:
        accounting.repair_taken = True
        call_counts["repair"] += 1
        repair_claims = synthesis_backend.repair_section(seed, transcript, failing=failing)
        replacements = _replacement_validation(
            repair_claims,
            failing=failing,
            substrate=substrate,
            section_index=section_index,
            section_group_ids=section_group_ids,
            citable_finding_ids=citable_finding_ids,
            citable_chunk_ids=citable_chunk_ids,
            available_claim_types=available_claim_types,
        )
        call_counts["rejudge"] += _judge_claims(
            claims=replacements.drafts,
            substrate=substrate,
            grounding_judge_backend=grounding_judge_backend,
        )
    final = _finalize_claims(
        initial=initial,
        replacements=replacements,
        failing=failing,
        accounting=accounting,
    )
    for claim in final:
        if "gap_degraded" in claim.flags:
            accounting.gap_claims_degraded += 1
        if claim.verdict == "unsupported_mis_cited" and "unsupported_mis_cited" not in claim.flags:
            claim.flags.append("unsupported_mis_cited")
    return final, call_counts


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
    claims: Sequence[ClaimDraft],
    substrate: SubstrateView,
    created_at: datetime,
) -> str:
    texts = [claim.text for claim in claims]
    content = "\n\n".join(texts)
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
    offset = 0
    for index, claim in enumerate(claims):
        if index > 0:
            offset += 2
        start = offset
        end = start + len(claim.text)
        offset = end
        unit_id = uuid.uuid4()
        annotation_id = uuid.uuid4()
        conn.execute(
            addressable_unit.insert().values(
                unit_id=unit_id,
                block_id=block_id,
                unit_type="text_span",
                locator={"start": start, "end": end},
                content=claim.text,
                created_at=created_at,
            )
        )
        conn.execute(
            annotation.insert().values(
                annotation_id=annotation_id,
                block_id=block_id,
                unit_id=unit_id,
                annotation_type=claim.annotation_type,
                payload=_annotation_payload(claim, substrate),
                created_at=created_at,
            )
        )
        for citation in claim.citation_rows:
            conn.execute(
                citation_table.insert().values(
                    citation_id=uuid.uuid4(),
                    annotation_id=annotation_id,
                    chunk_id=uuid.UUID(citation.chunk_id),
                    quote=citation.quote,
                    verification_result="pass",
                    created_at=created_at,
                )
            )
    return str(block_id)


def _group_member_findings(
    section: SectionSpec,
    *,
    substrate: SubstrateView,
) -> list[dict[str, Any]]:
    if substrate.grouping is None:
        return []
    member_ids: set[str] = set()
    for group_id in section.group_ids:
        group = substrate.group_by_id.get(group_id)
        if group is None:
            continue
        members = group.get("member_finding_ids", [])
        if isinstance(members, list):
            member_ids.update(str(member) for member in members if isinstance(member, str))
    return [
        substrate.finding_by_id[finding_id].record
        for finding_id in sorted(member_ids)
        if finding_id in substrate.finding_by_id
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
        "gap_claims_degraded": accounting.gap_claims_degraded,
        "repair_taken": accounting.repair_taken,
        "turn_cap_hit": accounting.turn_cap_hit,
    }


def _rollup_counts(
    *,
    all_claims: Sequence[ClaimDraft],
    section_blocks: Sequence[dict[str, Any]],
    sections_total: int,
    substrate: SubstrateView,
    groups_unsectioned: int | None,
    chunk_claims_rejected: int,
    gap_claims_degraded: int,
    tool_calls_total: int,
) -> dict[str, Any]:
    verdict_counts: Counter[str] = Counter()
    for claim in all_claims:
        if claim.verdict is not None:
            verdict_counts[claim.verdict] += 1
    origin_counts = _citation_counts_by_origin(all_claims)
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
        "citations_from_unselected": origin_counts["unselected_screened"],
        "chunk_claims_rejected": chunk_claims_rejected,
        "gap_claims_degraded": gap_claims_degraded,
        "tool_calls_total": tool_calls_total,
        "findings_cited_distinct": len(finding_ids),
    }
    if substrate.extraction is not None:
        counts["findings_total"] = len(substrate.finding_by_id)
    if substrate.grouping is not None:
        counts["groups_total"] = len(substrate.grouping_group_ids)
        counts["groups_unsectioned"] = groups_unsectioned or 0
    return counts


def _rollup_flags(
    *,
    groups_unsectioned: int,
    all_claims: Sequence[ClaimDraft],
    section_blocks: Sequence[dict[str, Any]],
    chunk_claims_rejected: int,
    gap_claims_degraded: int,
    turn_cap_hit: bool,
    repair_path_taken: bool,
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
    if gap_claims_degraded:
        flags["gap_claims_degraded"] = True
    if turn_cap_hit:
        flags["turn_cap_hit"] = True
    if repair_path_taken:
        flags["repair_path_taken"] = True
    if any(block["citations_verified"] == 0 for block in section_blocks):
        flags["uncited_sections"] = True
    return flags


def _generation_call_count(call_counts: Mapping[str, int]) -> int:
    return sum(call_counts.values())


def _reserve_generation(call_counts: dict[str, int], phase: str) -> None:
    if _generation_call_count(call_counts) + 1 > generation_budget_max():
        raise SynthesiseFailure("budget_exceeded")
    call_counts[phase] = call_counts.get(phase, 0) + 1


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

    Returns:
        Component summary for ``component.completed``.

    Raises:
        SynthesiseFailure: Structural/backend failure. Roll-up is never written
            on failure; post-block failures carry already-written block ids.
    """
    reranker = chunk_reranker if chunk_reranker is not None else PassThroughChunkReranker()
    blocks_written: list[str] = []
    call_counts = {
        "proposal": 0,
        "proposal_repair": 0,
        "section_turns": 0,
        "judge": 0,
        "repair": 0,
        "rejudge": 0,
    }
    refs = _resolve_references(conn, project_id=project_id, context=context)
    corpus = _load_corpus_profile(conn, project_id=project_id, scope_id=context.scope_id)
    if not refs.any_resolved() and corpus.ingested_docs == 0:
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
    if corpus.ingested_docs > 0:
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
        )

    selected_pss_ids_str = {str(item) for item in selected_pss_ids}
    chunk_by_id, chunks_by_pss_id, chunk_bases = _load_screened_chunks(
        conn,
        project_id=project_id,
        scope_id=context.scope_id,
        selected_pss_ids=selected_pss_ids_str,
        appraised_pss_ids=corpus.appraised_pss_ids,
    )
    finding_by_id, finding_bases = _load_findings(
        conn, project_id=project_id, extraction_row=refs.extraction_row
    )
    basis_by_snapshot = {**chunk_bases, **finding_bases}
    coverage_records = _load_coverage_records(
        conn, project_id=project_id, scope_id=context.scope_id
    )
    substrate = _substrate_view(
        refs=refs,
        corpus=corpus,
        coverage_records=coverage_records,
        chunk_by_id=chunk_by_id,
        chunks_by_pss_id=chunks_by_pss_id,
        finding_by_id=finding_by_id,
        basis_by_snapshot_id=basis_by_snapshot,
        selected_pss_ids=selected_pss_ids_str,
    )
    summaries = _substrate_summaries(refs, corpus)

    created_at = datetime.now(UTC)
    artefact_id = uuid.uuid4()
    conn.execute(
        artefact.insert().values(
            artefact_id=artefact_id,
            project_id=project_id,
            title=derive_artefact_title(context.intent),
            created_at=created_at,
        )
    )

    if directive.sections is not None:
        sections = _sections_from_directive(directive.sections)
        section_source = "scope_context"
    else:
        try:
            _reserve_generation(call_counts, "proposal")
            proposal = synthesis_backend.propose_sections(
                intent=context.intent, substrate=summaries
            )
        except RuntimeError as exc:
            raise SynthesiseFailure(type(exc).__name__, blocks_written=blocks_written) from exc
        grouping_group_ids = substrate.grouping_group_ids if substrate.grouping else None
        sections, reasons = _validate_sections(proposal, grouping_group_ids=grouping_group_ids)
        if reasons:
            try:
                _reserve_generation(call_counts, "proposal_repair")
                repaired = synthesis_backend.propose_sections(
                    intent=context.intent, substrate=summaries, rejection=reasons
                )
            except RuntimeError as exc:
                raise SynthesiseFailure(
                    type(exc).__name__, blocks_written=blocks_written
                ) from exc
            sections, reasons = _validate_sections(
                repaired,
                grouping_group_ids=substrate.grouping_group_ids if substrate.grouping else None,
            )
            if reasons:
                raise SynthesiseFailure(
                    "section_proposal_invalid", blocks_written=blocks_written
                )
        section_source = "proposal"

    assigned_groups = {group_id for section in sections for group_id in section.group_ids}
    groups_unsectioned = len(substrate.grouping_group_ids - assigned_groups)

    findings_reader = (
        make_findings_reader(
            conn,
            project_id=project_id,
            extraction_run_id=refs.extraction_run_id,
            evidence_scope_id=context.scope_id,
            grouping_groups=cast("list[dict[str, Any]]", grouping_summary["groups"])
            if grouping_summary is not None
            else None,
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
    section_rollups: list[dict[str, Any]] = []
    section_provenance: list[dict[str, Any]] = []
    total_chunk_rejections = 0
    total_gap_degraded = 0
    total_tool_calls = 0
    turn_cap_hit_any = False
    repair_path_taken = False

    for section_index, section in enumerate(sections):
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
            "substrate": summaries,
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
        }
        tools = build_section_tools(
            retriever=retriever,
            findings_reader=findings_reader,
            lookup_reader=lookup_reader,
        )
        try:
            loop_result = run_section_loop(
                synthesis_backend,
                seed=seed,
                tools=tools,
            )
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
        )
        raw_claims = loop_result["claims"] or SectionClaimsWire(claims=[])
        try:
            claims, section_call_counts = _section_claims(
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
            )
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
            claims=claims,
            substrate=substrate,
            created_at=created_at,
        )
        blocks_written.append(block_id)
        total_chunk_rejections += accounting.chunk_claims_rejected
        total_gap_degraded += accounting.gap_claims_degraded
        total_tool_calls += accounting.tool_call_count
        turn_cap_hit_any = turn_cap_hit_any or accounting.turn_cap_hit
        repair_path_taken = repair_path_taken or accounting.repair_taken
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
        "reranker": retrieval_provenance.get("reranker", getattr(reranker, "mode", "none")),
    }
    provenance = {
        "prompt_versions": {
            "sections": SECTIONS_PROMPT_VERSION,
            "section": SECTION_PROMPT_VERSION,
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
        },
        "caps": {
            "SECTION_CAP": SECTION_CAP,
            "SECTION_TURN_CAP": SECTION_TURN_CAP,
            "SYNTH_CHUNK_TOP_K": SYNTH_CHUNK_TOP_K,
            "SYNTH_CHUNK_CHAR_BUDGET": SYNTH_CHUNK_CHAR_BUDGET,
            "RETRIEVAL_UNIT_CAP": RETRIEVAL_UNIT_CAP,
            "REPAIR_ROUND_CAP": REPAIR_ROUND_CAP,
        },
        "sections": section_provenance,
        "inherited_chain_base": _inherited_chain_base(refs),
        "directive": directive.as_provenance(),
    }
    counts = _rollup_counts(
        all_claims=all_claims,
        section_blocks=section_rollups,
        sections_total=len(sections),
        substrate=substrate,
        groups_unsectioned=groups_unsectioned,
        chunk_claims_rejected=total_chunk_rejections,
        gap_claims_degraded=total_gap_degraded,
        tool_calls_total=total_tool_calls,
    )
    flags = _rollup_flags(
        groups_unsectioned=groups_unsectioned,
        all_claims=all_claims,
        section_blocks=section_rollups,
        chunk_claims_rejected=total_chunk_rejections,
        gap_claims_degraded=total_gap_degraded,
        turn_cap_hit=turn_cap_hit_any,
        repair_path_taken=repair_path_taken,
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
    }
