"""Section-loop tools, retrieval helper, loop runner and directive parser (task 013).

This module owns the *code-enforced* side of the repo's first agent loop: the
plan-pinned constants, the three read-only scoped tools (``search_chunks`` /
``query_findings`` / ``lookup``), the staged retrieval pipeline behind the
``retrieve`` seam's first increment, the bounded loop runner, and the
fail-closed ``context["synthesis"]`` directive parser. The prompt-bearing
surfaces live in :mod:`policy_atlas.synthesis_backend` and
:mod:`policy_atlas.grounding_judge`; nothing in this module composes prose.

Disciplines binding here (contract 013): the tool set is closed, read-only and
substrate-scoped; an unknown tool name is a validation error, never executed;
caps are enforced in code and cap exhaustion forces the claims emission, never
extends the loop; ``search`` remains acquire's alone — no egress verb exists in
this module.
"""

from __future__ import annotations

import math
import re
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, TypedDict, cast

from sqlalchemy import case, func
from sqlalchemy import select as sa_select
from sqlalchemy.engine import Connection

from policy_atlas.embeddings import EMBEDDING_PROFILE, UNIT_POLICY, validate_vector
from policy_atlas.schema import (
    EFFECT_DIRECTIONS,
    characterisation_result,
    chunk_embedding,
    extraction_result,
    grouping_result,
    intervention_outcome_finding,
    project_source_snapshot,
    search_coverage_record,
    selection_result,
    source_appraisal_result,
    source_classification_result,
    source_extraction_record,
    source_screening_result,
    source_snapshot,
    source_tag,
)
from policy_atlas.schema import chunk as chunk_table
from policy_atlas.tags import has_control_character

if TYPE_CHECKING:
    from policy_atlas.synthesis_backend import SectionClaimsWire

# --- Plan-pinned constants (plan.md rev 2 — binding; the caps-bind test
# asserts these module constants are the values enforced on the live path,
# the V2 dead-config lesson) ---

SECTION_CAP = 8
# Generation turns per section loop. The forced claims emission IS the
# SECTION_TURN_CAP-th turn (plan review M4): at most SECTION_TURN_CAP - 1 tool
# turns occur, so the pre-run budget maximum is exact, never exceeded.
SECTION_TURN_CAP = 6
REPAIR_ROUND_CAP = 1
SYNTH_CHUNK_TOP_K = 8
SYNTH_CHUNK_CHAR_BUDGET = 24_000
# Fail-closed in-memory retrieval ceiling over the screened corpus's embedding
# units. Beyond it the component fails structurally naming the cap — the
# index-backed `retrieve` slice is the upgrade, never a degraded sample.
RETRIEVAL_UNIT_CAP = 20_000
# Top-N per relevance leg BEFORE fusion (plan review M5): priors/boosts/the
# reranker operate on this bounded candidate set; "zero-relevance never
# surfaced by boost alone" is defined as not-in-either-leg's-pool → not a
# candidate.
CANDIDATE_POOL_PER_LEG = 200
REASONING_CLAIMS_MAX = 3
# Artefact title: verbatim intent, control characters stripped, truncated with
# a trailing ellipsis at this bound.
ARTEFACT_TITLE_MAX = 300
# Reciprocal Rank Fusion constant over (cosine rank, lexical rank) within the
# candidate pool; ties break on str(unit_id) lexicographic (plan review m10).
RRF_K = 60
# A referenced selection is a soft ranking prior, never a filter: chunks of
# selected documents get this multiplicative boost on the fused score,
# recorded in provenance.
SELECTION_PRIOR_BOOST = 2.0
# Directive retrieval-boost weights clamp to this range (contract rev 8 M5).
# Deliberate divergence from the select precedent (plan review m6): select
# REJECTS out-of-range weights; the synthesise directive grammar CLAMPS them.
BOOST_CLAMP_MIN = 0.1
BOOST_CLAMP_MAX = 10.0
# The closed column set the directive may boost over (select's vocabulary).
BOOST_COLUMNS = ("origin", "primary_evidence_type", "text_basis")
# Bounds shared with the directive grammar (contract rev 8 M5).
DIRECTIVE_SECTION_TEXT_MAX = 200
DIRECTIVE_LIST_MAX = 200

# The closed lookup query vocabulary v1 (plan rev 2). Unknown kind → tool-level
# validation error, never executed; all queries scoped to project_id + the
# resolved run references; side-effect-free.
LOOKUP_QUERY_KINDS = (
    "appraisal_by_doc",
    "classification_by_doc",
    "selection_rationale",
    "coverage_records",
    "characterisation_summary",
    "grouping_groups",
    "tags_by_doc",
    "docs_by_tag",
    "tag_aggregate",
)

# The closed tool set of the section loop.
SECTION_TOOL_NAMES = ("search_chunks", "query_findings", "lookup")


# --- Shared record types (id-keyed data records — never instructions) ---


class ChunkSearchResult(TypedDict):
    """One frozen chunk record returned by ``search_chunks``.

    ``origin`` records the selection prior's honesty contract: ``selected`` |
    ``unselected_screened`` — an unselected-but-screened chunk is reachable and
    its citation records this origin (never silently widened reading).
    """

    chunk_record_id: str  # str(chunk_id) — the citable id
    pss_id: str  # owning project_source_snapshot
    document_title: str
    sequence: int
    content: str  # the full frozen chunk text (the only quotable surface)
    origin: str  # "selected" | "unselected_screened"
    # Citability under the appraised-evidence rule (contract rev 8 M4):
    # produce-grounded-block cites only appraised evidence, while screen bounds
    # READING — the model may read unappraised chunks but a citation to one
    # rejects, so the record says which is which.
    appraised: bool
    fused_score: float


class FindingRecord(TypedDict):
    """One extracted finding as id-keyed data for the section loop.

    Anchors are extract-verified; the model cites ``finding_id`` and never
    authors these quotes — code resolves cited ids back to the stored anchors.
    """

    finding_id: str
    pss_id: str
    document_title: str
    intervention: str
    outcome: str
    population: str | None
    comparator: str | None
    effect_direction: str
    estimate_level: str | None
    study_design: str | None
    stratum_qualifiers: list[dict[str, str]]
    statistics: dict[str, Any]
    causality_by_design: str | None
    is_primary: bool | None
    field_coverage: dict[str, str]


class ToolCallRequest(TypedDict):
    """One tool call as requested by the backend on a loop turn."""

    tool: str
    arguments: dict[str, Any]


class ToolExchange(TypedDict):
    """One executed (or rejected) tool call with its id-keyed result.

    ``result`` carries either the tool's data payload or a bounded
    ``{"error": ...}`` validation record (unknown tool / bad arguments); a
    rejected call still consumed its turn.
    """

    tool: str
    arguments: dict[str, Any]
    result: dict[str, Any]


# --- Directive types (the fail-closed context["synthesis"] grammar) ---


class SynthesisDirectiveError(Exception):
    """Malformed synthesis directive; synthesise fails closed."""


@dataclass(frozen=True)
class SynthesisDirective:
    """Validated ``context["synthesis"]`` directive.

    Semantics split per the 010/012 knowledge concept: structural violations
    are malformed and fail closed (:class:`SynthesisDirectiveError`); unknown
    boost *targets* (a column value, tag or tier matching nothing in the
    corpus) match nothing and surface via ``unmatched_boosts`` at execution —
    never fatal. Weights arrive already clamped to
    [``BOOST_CLAMP_MIN``, ``BOOST_CLAMP_MAX``].
    """

    sections: list[dict[str, Any]] | None = None  # validated section specs
    column_boosts: dict[str, dict[str, float]] = field(default_factory=dict)
    tag_boosts: dict[str, float] = field(default_factory=dict)
    appraisal_tier_boosts: dict[str, float] = field(default_factory=dict)

    def as_provenance(self) -> dict[str, Any]:
        """Return the executed directive as deterministic JSON-compatible data."""
        return {
            "sections_source": "scope_context" if self.sections is not None else "proposal",
            "retrieval_boosts": {
                "columns": self.column_boosts,
                "tags": self.tag_boosts,
                "appraisal_tier": self.appraisal_tier_boosts,
            },
        }


# --- The cross-encoder reranker seam (contract rev 7.5) ---


class ChunkRerankerBackend(Protocol):
    """The retrieval pipeline's cross-encoder slot.

    The spec's retrieval contract assigns this slot to Bedrock Rerank (the
    inference trust boundary); v1 ships only the pass-through default and no
    ``run_harness`` kwarg — the live backend and its injection point land with
    the Bedrock integration slice (no public kwarg while nothing live exists,
    the V2 dead-config lesson). The stage runs after fusion + soft priors and
    before the top-k/char-budget caps; it may only reorder the candidates it
    was given, never add or drop.
    """

    @property
    def mode(self) -> str:
        """``"none"`` for pass-through; a live backend names its provider."""
        ...

    def rerank(
        self, *, query: str, candidates: list[ChunkSearchResult]
    ) -> list[ChunkSearchResult]:
        """Reorder candidates by cross-encoded relevance to the query."""
        ...


class PassThroughChunkReranker:
    """The v1 default reranker: returns candidates unchanged (``reranker: "none"``)."""

    mode = "none"

    def rerank(
        self, *, query: str, candidates: list[ChunkSearchResult]
    ) -> list[ChunkSearchResult]:
        """Return the candidates in their given order.

        Args:
            query: The retrieval query (unused by the pass-through).
            candidates: Fused, prior-weighted candidates.

        Returns:
            The same list, unchanged.
        """
        del query
        return candidates


class RetrievalUnitCapError(Exception):
    """The screened corpus exceeds the in-memory retrieval unit cap.

    Args:
        unit_count: Number of embedding units in the scoped corpus.
        cap: The enforced maximum, normally :data:`RETRIEVAL_UNIT_CAP`.
    """

    def __init__(self, *, unit_count: int, cap: int) -> None:
        self.unit_count = unit_count
        self.cap = cap
        super().__init__(
            f"retrieval_unit_cap_exceeded: {unit_count} units exceeds "
            f"RETRIEVAL_UNIT_CAP {cap}"
        )


@dataclass(frozen=True)
class RetrievalScope:
    """In-memory retrieval substrate for one synthesis run.

    Attributes:
        docs: Metadata keyed by project_source_snapshot id string.
        units: Embedding-unit records with frozen unit text and vectors.
        chunks: Frozen chunk records keyed by chunk id string.
    """

    docs: dict[str, dict[str, Any]]
    units: list[dict[str, Any]]
    chunks: dict[str, dict[str, Any]]


class ToolValidationError(Exception):
    """A bounded tool argument validation failure."""


class SectionLoopResult(TypedDict):
    """Outcome of one bounded section tool-calling loop."""

    claims: SectionClaimsWire | None
    transcript: list[ToolExchange]
    turns_used: int
    tool_call_counts: dict[str, int]
    rejected_tool_calls: int
    turn_cap_hit: bool


_DIRECTIVE_KEYS = {"sections", "retrieval_boosts"}
_SECTION_KEYS_REQUIRED = {"title", "focus"}
_SECTION_KEYS_WITH_GROUPS = {"title", "focus", "group_ids"}
_BOOST_KEYS = {"columns", "tags", "appraisal_tier"}
_TOKEN_RE = re.compile(r"[0-9A-Za-z]+")


def _directive_fail(message: str) -> None:
    raise SynthesisDirectiveError(message)


def _tool_fail(message: str) -> None:
    raise ToolValidationError(message)


def _bounded_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        _directive_fail(f"synthesis directive {field} must be a string")
    text = cast("str", value)
    if not text:
        _directive_fail(f"synthesis directive {field} must be non-empty")
    if len(text) > DIRECTIVE_SECTION_TEXT_MAX:
        _directive_fail(
            f"synthesis directive {field} exceeds {DIRECTIVE_SECTION_TEXT_MAX} characters"
        )
    if has_control_character(text):
        _directive_fail(
            f"synthesis directive {field} must not contain control characters"
        )
    return text


def _tool_string(
    arguments: dict[str, Any], *, field: str, max_length: int, required: bool
) -> str | None:
    value = arguments.get(field)
    if value is None:
        if required:
            _tool_fail(f"{field} is required")
        return None
    if not isinstance(value, str) or not value:
        _tool_fail(f"{field} must be a non-empty string")
    text = cast("str", value)
    if len(text) > max_length or has_control_character(text):
        _tool_fail(f"{field} must be bounded text")
    return text


def _parse_uuid(value: str, *, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ToolValidationError(f"{field} must be a UUID string") from exc


def _validate_tool_keys(arguments: dict[str, Any], *, allowed: set[str]) -> None:
    unknown = set(arguments) - allowed
    if unknown:
        _tool_fail("unknown argument key")


def _validate_findings_tool_arguments(arguments: dict[str, Any]) -> None:
    _validate_tool_keys(arguments, allowed={"finding_ids", "group_id", "effect_direction"})
    raw_ids = arguments.get("finding_ids")
    if raw_ids is not None:
        if not isinstance(raw_ids, list) or len(raw_ids) > DIRECTIVE_LIST_MAX:
            _tool_fail("finding_ids must be a bounded list")
        for item in raw_ids:
            if not isinstance(item, str) or not item:
                _tool_fail("finding_ids must contain non-empty strings")
    raw_group_id = arguments.get("group_id")
    if raw_group_id is not None and (not isinstance(raw_group_id, str) or not raw_group_id):
        _tool_fail("group_id must be a non-empty string")
    raw_direction = arguments.get("effect_direction")
    if raw_direction is not None and raw_direction not in EFFECT_DIRECTIONS:
        _tool_fail("effect_direction is invalid")


def _validate_lookup_tool_arguments(arguments: dict[str, Any]) -> None:
    _validate_tool_keys(arguments, allowed={"kind", "doc_id", "tag", "by"})
    kind = arguments.get("kind")
    if not isinstance(kind, str) or not kind:
        _tool_fail("kind must be a non-empty string")
    if kind not in LOOKUP_QUERY_KINDS:
        _tool_fail("unknown lookup kind")
    for field_name in ("doc_id", "tag"):
        value = arguments.get(field_name)
        if value is not None and (not isinstance(value, str) or not value):
            _tool_fail(f"{field_name} must be a non-empty string")
    by = arguments.get("by")
    if by is not None and by not in {"type", "asserter"}:
        _tool_fail("by must be type or asserter")


def _weight_value(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        _directive_fail(f"synthesis directive {field} weight must be a number")
    normalized = float(value)
    if not math.isfinite(normalized) or normalized <= 0:
        _directive_fail(f"synthesis directive {field} weight must be positive")
    return min(BOOST_CLAMP_MAX, max(BOOST_CLAMP_MIN, normalized))


def _string_weight_map(value: Any, *, field: str) -> dict[str, float]:
    if not isinstance(value, dict):
        _directive_fail(f"synthesis directive {field} must be an object")
    if len(value) > DIRECTIVE_LIST_MAX:
        _directive_fail(
            f"synthesis directive {field} exceeds {DIRECTIVE_LIST_MAX} entries"
        )
    parsed: dict[str, float] = {}
    for raw_key, raw_weight in value.items():
        if not isinstance(raw_key, str) or not raw_key:
            _directive_fail(f"synthesis directive {field} keys must be non-empty strings")
        if len(raw_key) > DIRECTIVE_SECTION_TEXT_MAX or has_control_character(raw_key):
            _directive_fail(f"synthesis directive {field} keys must be bounded text")
        parsed[raw_key] = _weight_value(raw_weight, field=f"{field}.{raw_key[:32]}")
    return parsed


def _parse_sections(
    value: Any, *, grouping_group_ids: set[str] | None
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        _directive_fail("synthesis directive sections must be a list")
    if not value or len(value) > SECTION_CAP:
        _directive_fail(f"synthesis directive sections must contain 1..{SECTION_CAP} items")

    from policy_atlas.synthesis_backend import FORBIDDEN_SECTION_TITLES

    forbidden = {title.casefold() for title in FORBIDDEN_SECTION_TITLES}
    parsed: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            _directive_fail(f"synthesis directive sections[{index}] must be an object")
        keys = set(item)
        if keys not in (_SECTION_KEYS_REQUIRED, _SECTION_KEYS_WITH_GROUPS):
            _directive_fail(f"synthesis directive sections[{index}] has invalid keys")
        title = _bounded_string(item["title"], field=f"sections[{index}].title")
        if title.casefold() in forbidden:
            _directive_fail(f"synthesis directive sections[{index}].title is forbidden")
        section: dict[str, Any] = {
            "title": title,
            "focus": _bounded_string(item["focus"], field=f"sections[{index}].focus"),
        }
        if "group_ids" in item:
            if grouping_group_ids is None:
                _directive_fail("synthesis directive group_ids require grouping")
            assert grouping_group_ids is not None
            raw_group_ids = item["group_ids"]
            if not isinstance(raw_group_ids, list) or len(raw_group_ids) > DIRECTIVE_LIST_MAX:
                _directive_fail("synthesis directive group_ids must be a bounded list")
            group_ids: list[str] = []
            for group_index, group_id in enumerate(raw_group_ids):
                if not isinstance(group_id, str) or not group_id:
                    _directive_fail(
                        "synthesis directive group_ids must contain non-empty strings"
                    )
                if (
                    len(group_id) > DIRECTIVE_SECTION_TEXT_MAX
                    or has_control_character(group_id)
                ):
                    _directive_fail("synthesis directive group_ids must be bounded text")
                if group_id not in grouping_group_ids:
                    _directive_fail(
                        f"synthesis directive group_ids[{group_index}] is unknown"
                    )
                group_ids.append(group_id)
            section["group_ids"] = group_ids
        parsed.append(section)
    return parsed


def _parse_retrieval_boosts(
    value: Any,
) -> tuple[dict[str, dict[str, float]], dict[str, float], dict[str, float]]:
    if not isinstance(value, dict):
        _directive_fail("synthesis directive retrieval_boosts must be an object")
    unknown = set(value) - _BOOST_KEYS
    if unknown:
        _directive_fail("synthesis directive retrieval_boosts has invalid keys")

    column_boosts: dict[str, dict[str, float]] = {}
    if "columns" in value:
        raw_columns = value["columns"]
        if not isinstance(raw_columns, dict):
            _directive_fail("synthesis directive retrieval_boosts.columns must be an object")
        for column, weights in raw_columns.items():
            if column not in BOOST_COLUMNS:
                _directive_fail("synthesis directive retrieval_boosts.columns has unknown column")
            column_boosts[column] = _string_weight_map(
                weights, field=f"retrieval_boosts.columns.{column}"
            )

    tag_boosts = (
        _string_weight_map(value["tags"], field="retrieval_boosts.tags")
        if "tags" in value
        else {}
    )
    appraisal_tier_boosts = (
        _string_weight_map(
            value["appraisal_tier"], field="retrieval_boosts.appraisal_tier"
        )
        if "appraisal_tier" in value
        else {}
    )
    return column_boosts, tag_boosts, appraisal_tier_boosts


def parse_synthesis_directive(
    context: dict[str, Any], *, grouping_group_ids: set[str] | None
) -> SynthesisDirective:
    """Parse the fail-closed ``context["synthesis"]`` directive.

    Args:
        context: Evidence-scope context JSON object.
        grouping_group_ids: Valid grouping ids when grouping is referenced, or
            ``None`` when no grouping substrate exists.

    Returns:
        A validated directive with retrieval boost weights clamped.

    Raises:
        SynthesisDirectiveError: If the directive is structurally malformed.
    """
    raw = context.get("synthesis")
    if raw is None:
        return SynthesisDirective()
    if not isinstance(raw, dict):
        _directive_fail("synthesis directive must be an object")
    unknown = set(raw) - _DIRECTIVE_KEYS
    if unknown:
        _directive_fail("synthesis directive has invalid top-level keys")

    sections = (
        _parse_sections(raw["sections"], grouping_group_ids=grouping_group_ids)
        if "sections" in raw
        else None
    )
    column_boosts: dict[str, dict[str, float]] = {}
    tag_boosts: dict[str, float] = {}
    appraisal_tier_boosts: dict[str, float] = {}
    if "retrieval_boosts" in raw:
        column_boosts, tag_boosts, appraisal_tier_boosts = _parse_retrieval_boosts(
            raw["retrieval_boosts"]
        )
    return SynthesisDirective(
        sections=sections,
        column_boosts=column_boosts,
        tag_boosts=tag_boosts,
        appraisal_tier_boosts=appraisal_tier_boosts,
    )


def _metadata_title(metadata: Any, pss_id: uuid.UUID) -> str:
    if isinstance(metadata, dict):
        for key in ("title", "display_name", "name"):
            value = metadata.get(key)
            if isinstance(value, str) and value:
                return value
    return f"source {pss_id}"


def _doc_record(row: Any, selected_pss_ids: set[uuid.UUID]) -> dict[str, Any]:
    metadata = row.metadata if isinstance(row.metadata, dict) else {}
    doc: dict[str, Any] = {
        "title": _metadata_title(metadata, cast("uuid.UUID", row.pss_id)),
        "origin": row.origin,
        "primary_evidence_type": row.primary_evidence_type,
        "text_basis": row.text_basis,
        "appraisal_tier": str(row.quality_score) if row.quality_score is not None else None,
        "tags": [],
        "selected": cast("uuid.UUID", row.pss_id) in selected_pss_ids,
    }
    for key in ("year", "publication_year"):
        value = metadata.get(key)
        if value is not None:
            doc[key] = value
    return doc


def build_retrieval_scope(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    selected_pss_ids: set[uuid.UUID],
) -> RetrievalScope:
    """Load the screened-in, appraised full-text retrieval scope.

    Args:
        conn: Open database connection.
        project_id: Project id that scopes every read.
        scope_id: Evidence scope id whose relevant screened documents form the
            retrieval corpus.
        selected_pss_ids: Referenced selection set, used only as a soft prior.

    Returns:
        Frozen document, chunk and unit records for in-memory retrieval.

    Raises:
        RetrievalUnitCapError: If the scoped embedding-unit count exceeds
            :data:`RETRIEVAL_UNIT_CAP`.
        ValueError: If a persisted vector or unit locator is malformed.
    """
    # The text-bearing snapshot per document: the fetched full-text snapshot when
    # the fetch pipeline ingested one, else the envelope snapshot when it carries
    # full text itself (uploads — chunked at upload ingest). full_text_status is
    # fetch-pipeline state, never text availability (schema comment).
    text_snapshot_id = case(
        (
            project_source_snapshot.c.full_text_status == "ingested",
            project_source_snapshot.c.full_text_snapshot_id,
        ),
        else_=project_source_snapshot.c.source_snapshot_id,
    ).label("text_snapshot_id")
    screened_docs = (
        sa_select(
            project_source_snapshot.c.project_source_snapshot_id.label("pss_id"),
            project_source_snapshot.c.source_snapshot_id.label("envelope_snapshot_id"),
            text_snapshot_id,
            project_source_snapshot.c.origin,
            source_snapshot.c.metadata,
            source_snapshot.c.text_basis,
            source_classification_result.c.primary_evidence_type,
            source_appraisal_result.c.quality_score,
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
            source_snapshot.c.source_snapshot_id == project_source_snapshot.c.source_snapshot_id,
        )
        .outerjoin(
            source_classification_result,
            (
                source_classification_result.c.project_source_snapshot_id
                == project_source_snapshot.c.project_source_snapshot_id
            )
            & (source_classification_result.c.project_id == project_id)
            & (source_classification_result.c.evidence_scope_id == scope_id),
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
        .where(
            (project_source_snapshot.c.full_text_status == "ingested")
            | (source_snapshot.c.text_basis == "full_text")
        )
        .subquery()
    )
    unit_count = int(
        conn.execute(
            sa_select(func.count())
            .select_from(chunk_embedding)
            .join(chunk_table, chunk_table.c.chunk_id == chunk_embedding.c.chunk_id)
            .where(chunk_table.c.source_snapshot_id.in_(
                sa_select(screened_docs.c.text_snapshot_id)
            ))
            .where(chunk_embedding.c.embedding_profile == EMBEDDING_PROFILE)
            .where(chunk_embedding.c.unit_policy == UNIT_POLICY)
        ).scalar_one()
    )
    if unit_count > RETRIEVAL_UNIT_CAP:
        raise RetrievalUnitCapError(unit_count=unit_count, cap=RETRIEVAL_UNIT_CAP)

    doc_rows = conn.execute(
        sa_select(screened_docs).order_by(screened_docs.c.pss_id)
    ).fetchall()
    docs = {
        str(row.pss_id): _doc_record(row, selected_pss_ids)
        for row in doc_rows
    }

    tags_rows = conn.execute(
        sa_select(
            source_tag.c.project_source_snapshot_id,
            source_tag.c.tag,
        )
        .where(source_tag.c.project_id == project_id)
        .where(source_tag.c.project_source_snapshot_id.in_(
            sa_select(screened_docs.c.pss_id)
        ))
        .order_by(
            source_tag.c.project_source_snapshot_id,
            source_tag.c.tag_type,
            source_tag.c.asserted_by,
            source_tag.c.tag,
        )
    ).fetchall()
    for row in tags_rows:
        pss_key = str(row.project_source_snapshot_id)
        if pss_key in docs:
            docs[pss_key]["tags"].append(row.tag)
    for doc in docs.values():
        doc["tags"] = sorted(set(cast("list[str]", doc["tags"])))

    unit_rows = conn.execute(
        sa_select(
            chunk_embedding.c.chunk_embedding_id,
            chunk_embedding.c.chunk_id,
            chunk_embedding.c.unit_locator,
            chunk_embedding.c.vector,
            chunk_table.c.sequence,
            chunk_table.c.content,
            chunk_table.c.segmentation_policy,
            screened_docs.c.pss_id,
        )
        .select_from(chunk_embedding)
        .join(chunk_table, chunk_table.c.chunk_id == chunk_embedding.c.chunk_id)
        .join(
            screened_docs,
            screened_docs.c.text_snapshot_id == chunk_table.c.source_snapshot_id,
        )
        .where(chunk_embedding.c.embedding_profile == EMBEDDING_PROFILE)
        .where(chunk_embedding.c.unit_policy == UNIT_POLICY)
        .order_by(
            screened_docs.c.pss_id,
            chunk_table.c.sequence,
            chunk_embedding.c.unit_index,
            chunk_embedding.c.chunk_embedding_id,
        )
    ).fetchall()

    chunks: dict[str, dict[str, Any]] = {}
    units: list[dict[str, Any]] = []
    for row in unit_rows:
        chunk_id = str(row.chunk_id)
        content = cast("str", row.content)
        chunks.setdefault(
            chunk_id,
            {
                "content": content,
                "sequence": cast("int", row.sequence),
                "pss_id": str(row.pss_id),
                "segmentation_policy": cast("str", row.segmentation_policy),
            },
        )
        locator = row.unit_locator
        if not isinstance(locator, dict):
            raise ValueError("chunk embedding unit_locator must be an object")
        start = locator.get("start")
        end = locator.get("end")
        if (
            isinstance(start, bool)
            or isinstance(end, bool)
            or not isinstance(start, int)
            or not isinstance(end, int)
            or start < 0
            or end < start
            or end > len(content)
        ):
            raise ValueError("chunk embedding unit_locator has invalid offsets")
        units.append(
            {
                "unit_id": str(row.chunk_embedding_id),
                "chunk_id": chunk_id,
                "pss_id": str(row.pss_id),
                "vector": validate_vector(row.vector),
                "text": content[start:end],
            }
        )
    return RetrievalScope(docs=docs, units=units, chunks=chunks)


def _tokens(text: str) -> set[str]:
    return {match.group(0).casefold() for match in _TOKEN_RE.finditer(text)}


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    numerator = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for left_value, right_value in zip(left, right, strict=True):
        numerator += left_value * right_value
        left_norm += left_value * left_value
        right_norm += right_value * right_value
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (math.sqrt(left_norm) * math.sqrt(right_norm))


def _ranked_pool(
    scored: list[tuple[float, dict[str, Any]]],
) -> list[tuple[float, dict[str, Any]]]:
    nonzero = [(score, unit) for score, unit in scored if score > 0.0]
    return sorted(nonzero, key=lambda item: (-item[0], str(item[1]["unit_id"])))[
        :CANDIDATE_POOL_PER_LEG
    ]


def _sorted_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sorted_json(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_sorted_json(item) for item in value]
    return value


class ChunkRetriever:
    """Deterministic staged chunk retriever for one synthesis run.

    Args:
        scope: In-memory retrieval scope loaded from the screened corpus.
        embedder: Injected embedding backend; no network is opened here.
        directive: Parsed synthesis directive with retrieval boosts.
        reranker: Reranker seam applied after fusion and soft priors.
    """

    def __init__(
        self,
        scope: RetrievalScope,
        *,
        embedder: Any,
        directive: SynthesisDirective,
        reranker: ChunkRerankerBackend,
    ) -> None:
        self._scope = scope
        self._embedder = embedder
        self._directive = directive
        self._reranker = reranker
        self._query_vectors: dict[str, list[float]] = {}
        self._executed_boosts: dict[str, Any] = {}
        self._unmatched_boosts: dict[str, Any] = {}
        self._has_selected_docs = any(
            bool(doc.get("selected")) for doc in self._scope.docs.values()
        )
        self._refresh_boost_matches()

    def search(self, query: str) -> list[ChunkSearchResult]:
        """Search frozen chunks with hybrid content relevance and soft priors.

        Args:
            query: Content query supplied by the section loop.

        Returns:
            Ranked chunk records capped to :data:`SYNTH_CHUNK_TOP_K`.
        """
        query_vector = self._query_vector(query)
        query_tokens = _tokens(query)
        cosine_pool = _ranked_pool([
            (_cosine(query_vector, cast("list[float]", unit["vector"])), unit)
            for unit in self._scope.units
        ])
        lexical_pool = _ranked_pool([
            (
                len(query_tokens & _tokens(cast("str", unit["text"])))
                / max(1, len(query_tokens)),
                unit,
            )
            for unit in self._scope.units
        ])

        fused_by_unit: dict[str, tuple[float, dict[str, Any]]] = {}
        for rank, (_score, unit) in enumerate(cosine_pool, start=1):
            unit_id = str(unit["unit_id"])
            current = fused_by_unit.get(unit_id, (0.0, unit))[0]
            fused_by_unit[unit_id] = (current + 1.0 / (RRF_K + rank), unit)
        for rank, (_score, unit) in enumerate(lexical_pool, start=1):
            unit_id = str(unit["unit_id"])
            current = fused_by_unit.get(unit_id, (0.0, unit))[0]
            fused_by_unit[unit_id] = (current + 1.0 / (RRF_K + rank), unit)

        best_by_chunk: dict[str, tuple[float, dict[str, Any]]] = {}
        for fused, unit in fused_by_unit.values():
            chunk_id = str(unit["chunk_id"])
            current_best = best_by_chunk.get(chunk_id)
            if current_best is None or fused > current_best[0]:
                best_by_chunk[chunk_id] = (fused, unit)

        candidates = [
            self._result_for_chunk(chunk_id, fused * self._soft_prior(chunk_id))
            for chunk_id, (fused, _unit) in best_by_chunk.items()
        ]
        ordered = sorted(
            candidates,
            key=lambda candidate: (-candidate["fused_score"], candidate["chunk_record_id"]),
        )
        reranked = self._reranker.rerank(query=query, candidates=ordered)
        allowed_ids = {candidate["chunk_record_id"] for candidate in ordered}
        sanitized = [
            candidate for candidate in reranked if candidate["chunk_record_id"] in allowed_ids
        ]
        return sanitized[:SYNTH_CHUNK_TOP_K]

    def provenance(self) -> dict[str, Any]:
        """Return retrieval provenance for roll-up recording."""
        return {
            "reranker": self._reranker.mode,
            "selection_prior": SELECTION_PRIOR_BOOST if self._has_selected_docs else None,
            "executed_boosts": _sorted_json(self._executed_boosts),
            "unmatched_boosts": _sorted_json(self._unmatched_boosts),
            "doc_count": len(self._scope.docs),
            "unit_count": len(self._scope.units),
        }

    def _query_vector(self, query: str) -> list[float]:
        vector = self._query_vectors.get(query)
        if vector is None:
            vectors = self._embedder.embed_texts([query])
            if len(vectors) != 1:
                raise RuntimeError("embedding backend returned wrong query vector count")
            vector = validate_vector(vectors[0])
            self._query_vectors[query] = vector
        return vector

    def _result_for_chunk(self, chunk_id: str, score: float) -> ChunkSearchResult:
        chunk = self._scope.chunks[chunk_id]
        pss_id = cast("str", chunk["pss_id"])
        doc = self._scope.docs[pss_id]
        return {
            "chunk_record_id": chunk_id,
            "pss_id": pss_id,
            "document_title": cast("str", doc["title"]),
            "sequence": cast("int", chunk["sequence"]),
            "content": cast("str", chunk["content"]),
            "origin": "selected" if doc.get("selected") else "unselected_screened",
            "appraised": doc.get("appraisal_tier") is not None,
            "fused_score": score,
        }

    def _soft_prior(self, chunk_id: str) -> float:
        chunk = self._scope.chunks[chunk_id]
        doc = self._scope.docs[cast("str", chunk["pss_id"])]
        multiplier = (
            SELECTION_PRIOR_BOOST
            if self._has_selected_docs and doc.get("selected")
            else 1.0
        )
        for column, values in self._directive.column_boosts.items():
            raw_value = doc.get(column)
            if raw_value is not None and str(raw_value) in values:
                multiplier *= values[str(raw_value)]
        for tag in cast("list[str]", doc.get("tags", [])):
            if tag in self._directive.tag_boosts:
                multiplier *= self._directive.tag_boosts[tag]
        tier = doc.get("appraisal_tier")
        if tier is not None and str(tier) in self._directive.appraisal_tier_boosts:
            multiplier *= self._directive.appraisal_tier_boosts[str(tier)]
        return multiplier

    def _refresh_boost_matches(self) -> None:
        executed_columns: dict[str, list[str]] = {}
        unmatched_columns: dict[str, list[str]] = {}
        for column, values in self._directive.column_boosts.items():
            matched: list[str] = []
            unmatched_values: list[str] = []
            doc_values = {
                str(doc[column])
                for doc in self._scope.docs.values()
                if doc.get(column) is not None
            }
            for target in values:
                (matched if target in doc_values else unmatched_values).append(target)
            if matched:
                executed_columns[column] = sorted(matched)
            if unmatched_values:
                unmatched_columns[column] = sorted(unmatched_values)

        doc_tags = {
            tag
            for doc in self._scope.docs.values()
            for tag in cast("list[str]", doc.get("tags", []))
        }
        matched_tags = sorted(
            target for target in self._directive.tag_boosts if target in doc_tags
        )
        unmatched_tags = sorted(
            target for target in self._directive.tag_boosts if target not in doc_tags
        )
        doc_tiers = {
            str(doc["appraisal_tier"])
            for doc in self._scope.docs.values()
            if doc.get("appraisal_tier") is not None
        }
        matched_tiers = sorted(
            target for target in self._directive.appraisal_tier_boosts if target in doc_tiers
        )
        unmatched_tiers = sorted(
            target for target in self._directive.appraisal_tier_boosts if target not in doc_tiers
        )

        executed: dict[str, Any] = {}
        if executed_columns:
            executed["columns"] = executed_columns
        if matched_tags:
            executed["tags"] = matched_tags
        if matched_tiers:
            executed["appraisal_tier"] = matched_tiers
        unmatched_result: dict[str, Any] = {}
        if unmatched_columns:
            unmatched_result["columns"] = unmatched_columns
        if unmatched_tags:
            unmatched_result["tags"] = unmatched_tags
        if unmatched_tiers:
            unmatched_result["appraisal_tier"] = unmatched_tiers
        self._executed_boosts = executed
        self._unmatched_boosts = unmatched_result


def build_section_tools(
    *,
    retriever: ChunkRetriever | None,
    findings_reader: Callable[[dict[str, Any]], dict[str, Any]] | None,
    lookup_reader: Callable[[dict[str, Any]], dict[str, Any]],
    char_budget: int = SYNTH_CHUNK_CHAR_BUDGET,
) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    """Build substrate-available read-only section tools.

    Args:
        retriever: Chunk retriever, or ``None`` when chunk claims are unavailable.
        findings_reader: Findings reader, or ``None`` without extraction.
        lookup_reader: Universal lookup reader.
        char_budget: Per-section cumulative chunk text budget.

    Returns:
        Mapping from tool name to validated callable.
    """
    if char_budget < 0:
        raise ValueError("char_budget must be non-negative")
    tools: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}
    used_chars = 0

    if retriever is not None:

        def search_chunks(arguments: dict[str, Any]) -> dict[str, Any]:
            nonlocal used_chars
            _validate_tool_keys(arguments, allowed={"query"})
            query = _tool_string(arguments, field="query", max_length=1000, required=True)
            assert query is not None
            if used_chars >= char_budget:
                return {"chunks": [], "truncated": True}
            chunks = retriever.search(query)
            remaining = char_budget - used_chars
            kept: list[ChunkSearchResult] = []
            truncated = False
            for chunk in chunks:
                content_len = len(chunk["content"])
                if content_len > remaining:
                    truncated = True
                    break
                kept.append(chunk)
                used_chars += content_len
                remaining -= content_len
            if len(kept) < len(chunks):
                truncated = True
            return {"chunks": kept, "truncated": truncated}

        tools["search_chunks"] = search_chunks

    if findings_reader is not None:

        def query_findings(arguments: dict[str, Any]) -> dict[str, Any]:
            _validate_findings_tool_arguments(arguments)
            return findings_reader(arguments)

        tools["query_findings"] = query_findings

    def lookup(arguments: dict[str, Any]) -> dict[str, Any]:
        _validate_lookup_tool_arguments(arguments)
        return lookup_reader(arguments)

    tools["lookup"] = lookup
    return tools


def _load_extraction_docs(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    extraction_run_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
) -> list[dict[str, Any]]:
    row = conn.execute(
        sa_select(extraction_result.c.docs)
        .where(extraction_result.c.project_id == project_id)
        .where(extraction_result.c.evidence_scope_id == evidence_scope_id)
        .where(extraction_result.c.run_id == extraction_run_id)
    ).first()
    if row is None:
        return []
    docs = row.docs
    if not isinstance(docs, list):
        return []
    return cast("list[dict[str, Any]]", docs)


def _record_ids_from_docs(docs: Sequence[dict[str, Any]]) -> list[uuid.UUID]:
    record_ids: list[uuid.UUID] = []
    for doc in docs:
        raw_id = doc.get("extraction_record_id")
        if isinstance(raw_id, str):
            try:
                record_ids.append(uuid.UUID(raw_id))
            except ValueError:
                continue
    return record_ids


def _finding_record(row: Any) -> FindingRecord:
    metadata = row.metadata if isinstance(row.metadata, dict) else {}
    pss_id = cast("uuid.UUID", row.project_source_snapshot_id)
    return {
        "finding_id": str(row.finding_id),
        "pss_id": str(pss_id),
        "document_title": _metadata_title(metadata, pss_id),
        "intervention": cast("str", row.intervention),
        "outcome": cast("str", row.outcome),
        "population": cast("str | None", row.population),
        "comparator": cast("str | None", row.comparator),
        "effect_direction": cast("str", row.effect_direction),
        "estimate_level": cast("str | None", row.estimate_level),
        "study_design": cast("str | None", row.study_design),
        "stratum_qualifiers": cast("list[dict[str, str]]", row.stratum_qualifiers),
        "statistics": cast("dict[str, Any]", row.statistics),
        "causality_by_design": cast("str | None", row.causality_by_design),
        "is_primary": cast("bool | None", row.is_primary),
        "field_coverage": cast("dict[str, str]", row.field_coverage),
    }


def _group_member_ids(grouping_groups: list[dict[str, Any]] | None) -> dict[str, set[str]]:
    if grouping_groups is None:
        return {}
    resolved: dict[str, set[str]] = {}
    for group in grouping_groups:
        raw_id = group.get("group_id") or group.get("id") or group.get("label")
        raw_members = group.get("member_finding_ids") or group.get("finding_ids")
        if isinstance(raw_id, str) and isinstance(raw_members, list):
            resolved[raw_id] = {member for member in raw_members if isinstance(member, str)}
    return resolved


def make_findings_reader(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    extraction_run_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    grouping_groups: list[dict[str, Any]] | None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Create a scoped extraction finding reader.

    Args:
        conn: Open database connection.
        project_id: Project id scoping all reads.
        extraction_run_id: Referenced extraction run id.
        evidence_scope_id: Evidence scope id.
        grouping_groups: Optional grouping records for group-id filtering.

    Returns:
        A validated ``query_findings`` implementation.
    """
    extraction_docs = _load_extraction_docs(
        conn,
        project_id=project_id,
        extraction_run_id=extraction_run_id,
        evidence_scope_id=evidence_scope_id,
    )
    extraction_record_ids = _record_ids_from_docs(extraction_docs)
    group_members = _group_member_ids(grouping_groups)
    if not extraction_record_ids:
        findings: list[FindingRecord] = []
    else:
        rows = conn.execute(
            sa_select(
                intervention_outcome_finding.c.finding_id,
                intervention_outcome_finding.c.extraction_record_id,
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
                source_extraction_record.c.project_source_snapshot_id,
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
                project_source_snapshot,
                (
                    project_source_snapshot.c.project_source_snapshot_id
                    == source_extraction_record.c.project_source_snapshot_id
                )
                & (project_source_snapshot.c.project_id == project_id),
            )
            .join(
                source_snapshot,
                (
                    source_snapshot.c.source_snapshot_id
                    == project_source_snapshot.c.source_snapshot_id
                ),
            )
            .where(intervention_outcome_finding.c.project_id == project_id)
            .where(
                intervention_outcome_finding.c.extraction_record_id.in_(
                    extraction_record_ids
                )
            )
            .order_by(
                intervention_outcome_finding.c.extraction_record_id,
                intervention_outcome_finding.c.finding_id,
            )
        ).fetchall()
        findings = [_finding_record(row) for row in rows]
    findings_by_id = {finding["finding_id"]: finding for finding in findings}

    def reader(arguments: dict[str, Any]) -> dict[str, Any]:
        raw_ids = arguments.get("finding_ids")
        requested_ids: set[str] | None = None
        if raw_ids is not None:
            if not isinstance(raw_ids, list) or len(raw_ids) > DIRECTIVE_LIST_MAX:
                _tool_fail("finding_ids must be a bounded list")
            requested_ids = set()
            for item in raw_ids:
                if not isinstance(item, str) or not item:
                    _tool_fail("finding_ids must contain strings")
                requested_ids.add(item)

        group_id = arguments.get("group_id")
        group_filter: set[str] | None = None
        if group_id is not None:
            if grouping_groups is None:
                _tool_fail("group_id requires grouping")
            if not isinstance(group_id, str) or not group_id:
                _tool_fail("group_id must be a string")
            if group_id not in group_members:
                _tool_fail("unknown group_id")
            group_filter = group_members[group_id]

        effect_direction = arguments.get("effect_direction")
        if effect_direction is not None and effect_direction not in EFFECT_DIRECTIONS:
            _tool_fail("effect_direction is invalid")

        selected = list(findings)
        if requested_ids is not None:
            selected = [
                finding for finding in selected if finding["finding_id"] in requested_ids
            ]
            missing = requested_ids - set(findings_by_id)
            if missing:
                selected = [finding for finding in selected if finding["finding_id"] not in missing]
        if group_filter is not None:
            selected = [
                finding for finding in selected if finding["finding_id"] in group_filter
            ]
        if effect_direction is not None:
            selected = [
                finding
                for finding in selected
                if finding["effect_direction"] == effect_direction
            ]
        truncated = len(selected) > 100
        return {"findings": selected[:100], "truncated": truncated}

    return reader


def _ensure_kind(arguments: dict[str, Any]) -> str:
    kind = _tool_string(arguments, field="kind", max_length=100, required=True)
    assert kind is not None
    if kind not in LOOKUP_QUERY_KINDS:
        _tool_fail("unknown lookup kind")
    return kind


def _doc_id_for_project(
    conn: Connection, *, project_id: uuid.UUID, arguments: dict[str, Any]
) -> uuid.UUID:
    raw_doc_id = _tool_string(arguments, field="doc_id", max_length=100, required=True)
    assert raw_doc_id is not None
    doc_id = _parse_uuid(raw_doc_id, field="doc_id")
    exists = conn.execute(
        sa_select(project_source_snapshot.c.project_source_snapshot_id)
        .where(project_source_snapshot.c.project_id == project_id)
        .where(project_source_snapshot.c.project_source_snapshot_id == doc_id)
    ).first()
    if exists is None:
        _tool_fail("doc_id is unknown")
    return doc_id


def _absent() -> dict[str, bool]:
    return {"absent": True}


def _selection_summary(row: Any) -> dict[str, Any]:
    selected = row.selected if isinstance(row.selected, list) else []
    bounded_selected: list[dict[str, Any]] = []
    for item in selected[:100]:
        if isinstance(item, dict):
            bounded_selected.append({
                "pss_id": item.get("pss_id"),
                "reason": item.get("reason"),
                "stratum": item.get("stratum"),
            })
    return {
        "strategy": row.strategy,
        "budget": row.budget,
        "excluded": row.excluded,
        "flags": row.flags,
        "selected": bounded_selected,
        "selected_truncated": len(selected) > 100,
    }


def _themes_summary(themes_payload: Any) -> dict[str, Any]:
    if not isinstance(themes_payload, dict):
        return {"themes": [], "unclustered": []}
    raw_themes = themes_payload.get("themes")
    themes: list[dict[str, Any]] = []
    if isinstance(raw_themes, list):
        for item in raw_themes:
            if not isinstance(item, dict):
                continue
            members = item.get("member_ids", [])
            if not isinstance(members, list):
                members = []
            themes.append({
                "theme_id": item.get("theme_id") or item.get("name"),
                "name": item.get("name"),
                "description": item.get("description"),
                "size": item.get("size", len(members)),
                "member_count": len(members),
                "member_ids": members,
            })
    return {"themes": themes, "unclustered": themes_payload.get("unclustered", [])}


def _grouping_summary(groups_payload: Any) -> dict[str, Any]:
    if not isinstance(groups_payload, dict):
        return {"groups": [], "residuals": {}}
    raw_groups = groups_payload.get("groups")
    groups: list[dict[str, Any]] = []
    if isinstance(raw_groups, list):
        for item in raw_groups:
            if not isinstance(item, dict):
                continue
            members = item.get("member_finding_ids", [])
            if not isinstance(members, list):
                members = []
            groups.append({
                "group_id": item.get("group_id") or item.get("label"),
                "label": item.get("label"),
                "description": item.get("description"),
                "size": item.get("size", len(members)),
                "direction_spread": item.get("direction_spread", {}),
                "member_finding_ids": members,
            })
    return {
        "groups": groups,
        "residuals": {
            "ungrouped": groups_payload.get("ungrouped"),
            "no_value": groups_payload.get("no_value"),
        },
    }


def make_lookup_reader(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    characterisation_run_id: uuid.UUID | None,
    selection_run_id: uuid.UUID | None,
    extraction_run_id: uuid.UUID | None,
    grouping_run_id: uuid.UUID | None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Create the universal closed-vocabulary lookup reader.

    Args:
        conn: Open database connection.
        project_id: Project id scoping all reads.
        scope_id: Evidence scope id.
        characterisation_run_id: Optional referenced characterisation run.
        selection_run_id: Optional referenced selection run.
        extraction_run_id: Optional referenced extraction run.
        grouping_run_id: Optional referenced grouping run.

    Returns:
        A validated ``lookup`` implementation.
    """

    def reader(arguments: dict[str, Any]) -> dict[str, Any]:
        kind = _ensure_kind(arguments)
        if kind in {"appraisal_by_doc", "classification_by_doc", "tags_by_doc"}:
            doc_id = _doc_id_for_project(conn, project_id=project_id, arguments=arguments)
            result: Any
            if kind == "appraisal_by_doc":
                row = conn.execute(
                    sa_select(
                        source_appraisal_result.c.quality_score,
                        source_appraisal_result.c.rubric_version,
                    )
                    .where(source_appraisal_result.c.project_id == project_id)
                    .where(source_appraisal_result.c.evidence_scope_id == scope_id)
                    .where(source_appraisal_result.c.project_source_snapshot_id == doc_id)
                ).first()
                result = (
                    _absent()
                    if row is None
                    else {
                        "quality_score": row.quality_score,
                        "rubric_version": row.rubric_version,
                    }
                )
            elif kind == "classification_by_doc":
                row = conn.execute(
                    sa_select(source_classification_result.c.primary_evidence_type)
                    .where(source_classification_result.c.project_id == project_id)
                    .where(source_classification_result.c.evidence_scope_id == scope_id)
                    .where(source_classification_result.c.project_source_snapshot_id == doc_id)
                ).first()
                result = (
                    _absent()
                    if row is None
                    else {"primary_evidence_type": row.primary_evidence_type}
                )
            else:
                rows = conn.execute(
                    sa_select(
                        source_tag.c.tag,
                        source_tag.c.tag_type,
                        source_tag.c.asserted_by,
                    )
                    .where(source_tag.c.project_id == project_id)
                    .where(source_tag.c.project_source_snapshot_id == doc_id)
                    .order_by(
                        source_tag.c.tag_type,
                        source_tag.c.asserted_by,
                        source_tag.c.tag,
                    )
                ).fetchall()
                result = [
                    {
                        "tag": row.tag,
                        "tag_type": row.tag_type,
                        "asserted_by": row.asserted_by,
                    }
                    for row in rows
                ]
            return {"kind": kind, "result": result}

        if kind == "selection_rationale":
            if selection_run_id is None:
                _tool_fail("selection_rationale requires selection")
            row = conn.execute(
                sa_select(
                    selection_result.c.strategy,
                    selection_result.c.budget,
                    selection_result.c.excluded,
                    selection_result.c.flags,
                    selection_result.c.selected,
                )
                .where(selection_result.c.project_id == project_id)
                .where(selection_result.c.evidence_scope_id == scope_id)
                .where(selection_result.c.run_id == selection_run_id)
            ).first()
            result = _absent() if row is None else _selection_summary(row)
            return {"kind": kind, "result": result}

        if kind == "coverage_records":
            rows = conn.execute(
                sa_select(
                    search_coverage_record.c.search_coverage_record_id,
                    search_coverage_record.c.backends,
                    search_coverage_record.c.stop_condition,
                    search_coverage_record.c.adequacy_verdict,
                    search_coverage_record.c.verdict_origin,
                )
                .where(search_coverage_record.c.project_id == project_id)
                .where(search_coverage_record.c.evidence_scope_id == scope_id)
                .order_by(search_coverage_record.c.search_coverage_record_id)
            ).fetchall()
            return {
                "kind": kind,
                "result": [
                    {
                        "search_coverage_record_id": str(row.search_coverage_record_id),
                        "backends": row.backends,
                        "stop_condition": row.stop_condition,
                        "adequacy_verdict": row.adequacy_verdict,
                        "verdict_origin": row.verdict_origin,
                    }
                    for row in rows
                ],
            }

        if kind == "characterisation_summary":
            if characterisation_run_id is None:
                _tool_fail("characterisation_summary requires characterisation")
            row = conn.execute(
                sa_select(characterisation_result.c.coverage, characterisation_result.c.themes)
                .where(characterisation_result.c.project_id == project_id)
                .where(characterisation_result.c.evidence_scope_id == scope_id)
                .where(characterisation_result.c.run_id == characterisation_run_id)
            ).first()
            result = (
                _absent()
                if row is None
                else {"coverage": row.coverage, **_themes_summary(row.themes)}
            )
            return {"kind": kind, "result": result}

        if kind == "grouping_groups":
            if grouping_run_id is None:
                _tool_fail("grouping_groups requires grouping")
            row = conn.execute(
                sa_select(grouping_result.c.groups)
                .where(grouping_result.c.project_id == project_id)
                .where(grouping_result.c.evidence_scope_id == scope_id)
                .where(grouping_result.c.run_id == grouping_run_id)
            ).first()
            result = _absent() if row is None else _grouping_summary(row.groups)
            return {"kind": kind, "result": result}

        if kind == "docs_by_tag":
            tag = _tool_string(arguments, field="tag", max_length=200, required=True)
            assert tag is not None
            rows = conn.execute(
                sa_select(source_tag.c.project_source_snapshot_id)
                .where(source_tag.c.project_id == project_id)
                .where(source_tag.c.tag == tag)
                .order_by(source_tag.c.project_source_snapshot_id)
            ).fetchall()
            return {
                "kind": kind,
                "result": sorted({str(row.project_source_snapshot_id) for row in rows}),
            }

        if kind == "tag_aggregate":
            by = _tool_string(arguments, field="by", max_length=20, required=True)
            if by not in {"type", "asserter"}:
                _tool_fail("by must be type or asserter")
            column = source_tag.c.tag_type if by == "type" else source_tag.c.asserted_by
            rows = conn.execute(
                sa_select(column.label("value"), func.count().label("tag_count"))
                .where(source_tag.c.project_id == project_id)
                .group_by(column)
                .order_by(column)
            ).fetchall()
            return {
                "kind": kind,
                "result": {
                    str(row._mapping["value"]): int(row._mapping["tag_count"])
                    for row in rows
                },
            }

        raise RuntimeError("unreachable lookup kind")

    return reader


def run_section_loop(
    backend: Any,
    *,
    seed: dict[str, Any],
    tools: Mapping[str, Callable[[dict[str, Any]], dict[str, Any]]],
    turn_cap: int = SECTION_TURN_CAP,
) -> SectionLoopResult:
    """Run one bounded section loop against the closed read-only tool set.

    Args:
        backend: Synthesis backend implementing ``section_turn``.
        seed: Id-keyed section seed.
        tools: Available substrate tools.
        turn_cap: Maximum generation turns; final turn forces emission.

    Returns:
        Claims, transcript and accounting counters.

    Raises:
        RuntimeError: If the backend violates the loop protocol.
    """
    if turn_cap <= 0:
        raise ValueError("turn_cap must be positive")
    transcript: list[ToolExchange] = []
    tool_call_counts: dict[str, int] = {}
    rejected_tool_calls = 0

    for turn in range(1, turn_cap + 1):
        force_emit = turn == turn_cap
        result = backend.section_turn(seed, transcript, force_emit=force_emit)
        claims = result.get("claims")
        tool_calls = result.get("tool_calls", [])
        if claims is not None:
            return {
                "claims": claims,
                "transcript": transcript,
                "turns_used": turn,
                "tool_call_counts": tool_call_counts,
                "rejected_tool_calls": rejected_tool_calls,
                "turn_cap_hit": force_emit,
            }
        if force_emit and tool_calls:
            raise RuntimeError("backend returned tool call on forced emit turn")
        if not tool_calls:
            raise RuntimeError("backend returned no claims or tool calls")
        if len(tool_calls) != 1:
            first = tool_calls[0] if tool_calls else {"tool": "invalid"}
            name = first.get("tool", "invalid")
            transcript.append({
                "tool": name if isinstance(name, str) else "invalid",
                "arguments": {},
                "result": {"error": "one tool call per turn"},
            })
            rejected_tool_calls += 1
            continue

        call = tool_calls[0]
        tool_name = call.get("tool")
        arguments = call.get("arguments", {})
        if not isinstance(tool_name, str):
            tool_name = "invalid"
        if not isinstance(arguments, dict):
            arguments = {}
        if tool_name not in tools:
            transcript.append({
                "tool": tool_name,
                "arguments": cast("dict[str, Any]", arguments),
                "result": {"error": f"unknown tool {tool_name!r}"},
            })
            rejected_tool_calls += 1
            continue
        try:
            tool_result = tools[tool_name](cast("dict[str, Any]", arguments))
        except ToolValidationError as exc:
            transcript.append({
                "tool": tool_name,
                "arguments": cast("dict[str, Any]", arguments),
                "result": {"error": str(exc)},
            })
            rejected_tool_calls += 1
            continue
        transcript.append({
            "tool": tool_name,
            "arguments": cast("dict[str, Any]", arguments),
            "result": tool_result,
        })
        tool_call_counts[tool_name] = tool_call_counts.get(tool_name, 0) + 1

    raise RuntimeError("section loop exhausted without emission")


def gathered_ids(transcript: Sequence[ToolExchange]) -> dict[str, set[str]]:
    """Extract chunk and finding ids returned during a section loop.

    Args:
        transcript: Executed and rejected tool exchanges.

    Returns:
        Sets of ids available for section-level citation validation.
    """
    chunk_ids: set[str] = set()
    finding_ids: set[str] = set()
    for exchange in transcript:
        result = exchange["result"]
        if exchange["tool"] == "search_chunks":
            chunks = result.get("chunks", [])
            if isinstance(chunks, list):
                for chunk in chunks:
                    if isinstance(chunk, dict) and isinstance(chunk.get("chunk_record_id"), str):
                        chunk_ids.add(cast("str", chunk["chunk_record_id"]))
        elif exchange["tool"] == "query_findings":
            findings = result.get("findings", [])
            if isinstance(findings, list):
                for finding in findings:
                    if isinstance(finding, dict) and isinstance(finding.get("finding_id"), str):
                        finding_ids.add(cast("str", finding["finding_id"]))
    return {"chunk_ids": chunk_ids, "finding_ids": finding_ids}
