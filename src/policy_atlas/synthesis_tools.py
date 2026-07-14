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
from typing import TYPE_CHECKING, Any, Literal, NotRequired, Protocol, TypedDict, cast

from sqlalchemy import ColumnElement, case, func
from sqlalchemy import select as sa_select
from sqlalchemy.engine import Connection

from policy_atlas.embeddings import EMBEDDING_PROFILE, UNIT_POLICY, validate_vector
from policy_atlas.extract import record_ids_by_profile
from policy_atlas.extraction_records import PROFILE_ID as IOF_PROFILE_ID
from policy_atlas.implementation_context_records import PROFILE_ID as ICF_PROFILE_ID
from policy_atlas.schema import (
    CONTEXT_TYPES,
    EFFECT_DIRECTIONS,
    characterisation_result,
    chunk_embedding,
    extraction_result,
    grouping_result,
    implementation_context_finding,
    intervention_outcome_finding,
    project_source_snapshot,
    search_coverage_record,
    selection_result,
    source_appraisal_result,
    source_classification_result,
    source_extraction_record,
    source_snapshot,
    source_tag,
)
from policy_atlas.schema import chunk as chunk_table
from policy_atlas.screen import effective_screen_rows
from policy_atlas.tags import has_control_character
from policy_atlas.usage import UsageAccumulator

if TYPE_CHECKING:
    from policy_atlas.synthesis_backend import SectionProseWire

# --- Plan-pinned constants (plan.md rev 2 — binding; the caps-bind test
# asserts these module constants are the values enforced on the live path,
# the V2 dead-config lesson) ---

SECTION_CAP = 8
# Generation turns per section loop. The forced claims emission IS the
# SECTION_TURN_CAP-th turn (plan review M4): at most SECTION_TURN_CAP - 1 tool
# turns occur, so the pre-run budget maximum is exact, never exceeded.
SECTION_TURN_CAP = 6
# Read-tool calls EXECUTED per turn. The writer prompt asks for "up to 6" —
# this is the code-side enforcement: overflow calls get an error result and
# count as rejected, so a degenerate 30-call turn cannot blow the per-turn
# retrieval/transcript envelope (turn_cap bounds turns, not work per turn).
READ_CALLS_PER_TURN_CAP = 6
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
FINDING_KINDS = ("iof", "icf")
FINDING_KIND_PROFILES = {"iof": IOF_PROFILE_ID, "icf": ICF_PROFILE_ID}
FINDING_KIND_UNAVAILABLE = "not extracted in this run"


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
    text_basis: NotRequired[str]  # "full_text" | "abstract_only"
    origin: str  # "selected" | "unselected_screened"
    # Citability under the appraised-evidence rule (contract rev 8 M4):
    # produce-grounded-block cites only appraised evidence, while screen bounds
    # READING — the model may read unappraised chunks but a citation to one
    # rejects, so the record says which is which.
    appraised: bool
    fused_score: float
    # Owner-adopted default metadata set (ADR 0015 §8 / B-B3): terse, attached
    # on the record itself, each key present ONLY when its value exists
    # (omit-if-absent). ``is_retracted`` is deliberately not surfaced.
    year: NotRequired[Any]
    evidence_type: NotRequired[str]
    appraisal_label: NotRequired[str]
    venue: NotRequired[str]
    cited_by: NotRequired[Any]


class FindingRecord(TypedDict):
    """One extracted finding as id-keyed data for the section loop.

    Anchors are extract-verified; the model cites ``finding_id`` and never
    authors these quotes — code resolves cited ids back to the stored anchors.
    """

    kind: Literal["iof"]
    finding_id: str
    extraction_record_id: str
    pss_id: str
    document_title: str
    intervention: str
    outcome: str
    population: str | None
    setting: str | None
    comparator: str | None
    effect_direction: str
    estimate_level: str | None
    study_design: str | None
    study_geography: str | None
    stratum_qualifiers: list[dict[str, str]]
    statistics: dict[str, Any]
    causality_by_design: str | None
    effect_basis: str | None
    is_primary: bool | None
    field_coverage: dict[str, str]
    # Owner-adopted default metadata set (ADR 0015 §8 / B-B3): omit-if-absent.
    year: NotRequired[Any]
    evidence_type: NotRequired[str]
    appraisal_label: NotRequired[str]
    venue: NotRequired[str]
    cited_by: NotRequired[Any]


class ICFFindingRecord(TypedDict):
    """One implementation-context finding as id-keyed section-loop data."""

    kind: Literal["icf"]
    finding_id: str
    extraction_record_id: str
    pss_id: str
    document_title: str
    context_type: str
    claim: str
    intervention: str
    outcome: str | None
    population: str | None
    setting: str | None
    study_geography: str | None
    study_design: str | None
    claim_level: str | None
    claim_basis: str | None
    level: str | None
    resource_requirements: str | None
    workforce_requirements: str | None
    field_coverage: dict[str, str]
    year: NotRequired[Any]
    evidence_type: NotRequired[str]
    appraisal_label: NotRequired[str]
    venue: NotRequired[str]
    cited_by: NotRequired[Any]


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


class MalformedEmissionError(Exception):
    """A claims emission whose arguments failed structural validation.

    Raised by live backends when the provider's ``emit_section`` arguments do
    not parse into the wire models (strict constrained decoding is unavailable
    for the pattern claim's counts map). The loop runner treats it as a
    turn-consuming error exchange — the model reads the bounded validation
    error as data and re-emits — so recovery stays inside the turn budget; on
    the forced final turn it is a structural failure (never an extension).
    """


class SectionLoopResult(TypedDict):
    """Outcome of one bounded section tool-calling loop."""

    claims: SectionProseWire | None
    transcript: list[ToolExchange]
    turns_used: int
    tool_call_counts: dict[str, int]
    rejected_tool_calls: int
    turn_cap_hit: bool
    # Claim objects a live emission carried that failed structural validation
    # and were salvaged away (backend per-claim salvage) — counted, never
    # silent; the component lands them in claims_rejected_structural.
    malformed_claims: int
    usage_totals: dict[str, int]


_DIRECTIVE_KEYS = {"sections", "retrieval_boosts"}
_SECTION_KEYS_REQUIRED = {"title", "focus"}
_SECTION_KEYS_WITH_GROUPS = {"title", "focus", "group_ids"}
_BOOST_KEYS = {"columns", "tags", "appraisal_tier"}
_TOKEN_RE = re.compile(r"[0-9A-Za-z]+")
GROUP_ID_EXPECTED_FORM = "<facet>:gNN"
_QUALIFIED_GROUP_ID_RE = re.compile(r"^[a-z][a-z0-9_]*:g[0-9]{2,}$")


def _directive_fail(message: str) -> None:
    raise SynthesisDirectiveError(message)


def _tool_fail(message: str) -> None:
    raise ToolValidationError(message)


def is_qualified_group_id(value: str) -> bool:
    """Return whether ``value`` uses the facet-qualified group id grammar.

    Args:
        value: Candidate group id.

    Returns:
        True when the id has the expected ``<facet>:gNN`` shape.
    """
    return bool(_QUALIFIED_GROUP_ID_RE.fullmatch(value))


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
    _validate_tool_keys(
        arguments,
        allowed={"kinds", "finding_ids", "group_id", "effect_direction", "context_type"},
    )
    raw_kinds = arguments.get("kinds")
    requested_kinds: set[str] | None = None
    if raw_kinds is not None:
        if not isinstance(raw_kinds, list) or len(raw_kinds) > DIRECTIVE_LIST_MAX:
            _tool_fail("kinds must be a bounded list")
        requested_kinds = set()
        for item in raw_kinds:
            if not isinstance(item, str) or not item:
                _tool_fail("kinds must contain non-empty strings")
            if item not in FINDING_KINDS:
                _tool_fail("unknown kind")
            requested_kinds.add(item)
        if not requested_kinds:
            _tool_fail("kinds must not be empty")
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
    if isinstance(raw_group_id, str) and not is_qualified_group_id(raw_group_id):
        _tool_fail(f"group_id must use expected form {GROUP_ID_EXPECTED_FORM}")
    raw_direction = arguments.get("effect_direction")
    if raw_direction is not None and raw_direction not in EFFECT_DIRECTIONS:
        _tool_fail("effect_direction is invalid")
    raw_context_type = arguments.get("context_type")
    if raw_context_type is not None and raw_context_type not in CONTEXT_TYPES:
        _tool_fail("context_type is invalid")
    effective_kinds = requested_kinds if requested_kinds is not None else set(FINDING_KINDS)
    if raw_direction is not None and effective_kinds != {"iof"}:
        _tool_fail("effect_direction requires iof findings only — pass kinds ['iof']")
    if raw_context_type is not None and effective_kinds != {"icf"}:
        _tool_fail("context_type requires icf findings only — pass kinds ['icf']")


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
                if not is_qualified_group_id(group_id):
                    _directive_fail(
                        "synthesis directive group_ids must use expected form "
                        f"{GROUP_ID_EXPECTED_FORM}"
                    )
                if group_id not in grouping_group_ids:
                    _directive_fail(
                        f"synthesis directive group_ids[{group_index}] is unknown; "
                        f"expected form {GROUP_ID_EXPECTED_FORM} resolving to grouping "
                        "records"
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


def _metadata_year(metadata: Any) -> Any:
    """Return a document's year from metadata, or ``None`` if absent."""
    if not isinstance(metadata, dict):
        return None
    for key in ("year", "publication_year"):
        value = metadata.get(key)
        if value is not None:
            return value
    return None


def _metadata_venue(metadata: Any) -> Any:
    """Return a document's publishing venue from metadata, or ``None``."""
    if not isinstance(metadata, dict):
        return None
    return metadata.get("publisher_org")


def _metadata_cited_by(metadata: Any) -> Any:
    """Return a document's citation count from ``provider_fields``, or ``None``.

    Guards a non-dict / absent ``provider_fields`` (never null-noise).
    """
    if not isinstance(metadata, dict):
        return None
    provider_fields = metadata.get("provider_fields")
    if not isinstance(provider_fields, dict):
        return None
    return provider_fields.get("cited_by_count")


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
    venue = _metadata_venue(metadata)
    if venue is not None:
        doc["venue"] = venue
    cited_by = _metadata_cited_by(metadata)
    if cited_by is not None:
        doc["cited_by"] = cited_by
    return doc


def chunk_text_basis_case(
    chunk_snapshot_id_col: ColumnElement[uuid.UUID],
    envelope_snapshot_id_col: ColumnElement[uuid.UUID],
    envelope_text_basis_col: ColumnElement[str],
) -> ColumnElement[str]:
    """Build the ``text_basis`` CASE shared by both chunk-retrieval read paths.

    A chunk is ``abstract_only`` exactly when it belongs to the envelope
    snapshot itself (no full-text snapshot was ingested for the doc) AND the
    envelope's own ``text_basis`` is not already ``full_text``; every other
    chunk is ``full_text``. Extracted (016 review stack) so this module's
    ``build_retrieval_scope`` and synthesise.py's ``_load_screened_chunks``
    encode the rule once and can never silently drift apart.

    Args:
        chunk_snapshot_id_col: The chunk row's ``source_snapshot_id`` column.
        envelope_snapshot_id_col: The document's envelope
            ``source_snapshot_id`` (or an equivalent labeled column/subquery
            reference).
        envelope_text_basis_col: The envelope snapshot's ``text_basis`` column.

    Returns:
        A ``"text_basis"``-labeled CASE expression.
    """
    return case(
        (
            (chunk_snapshot_id_col == envelope_snapshot_id_col)
            & (envelope_text_basis_col != "full_text"),
            "abstract_only",
        ),
        else_="full_text",
    ).label("text_basis")


def build_retrieval_scope(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    selected_pss_ids: set[uuid.UUID],
) -> RetrievalScope:
    """Load the screened-in chunk retrieval scope.

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
    # the fetch pipeline ingested one, else the envelope snapshot acquired for
    # the doc. full_text_status is fetch-pipeline state, never text availability
    # (schema comment).
    text_snapshot_id = case(
        (
            project_source_snapshot.c.full_text_status == "ingested",
            project_source_snapshot.c.full_text_snapshot_id,
        ),
        else_=project_source_snapshot.c.source_snapshot_id,
    ).label("text_snapshot_id")
    # Screened-in scope = effective-relevant join via the helper (never a raw
    # status='relevant' join, which would leak in demoted docs and double-read
    # confirmed ones).
    effective = effective_screen_rows()
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
        .where(effective.c.project_id == project_id)
        .where(effective.c.evidence_scope_id == scope_id)
        .where(effective.c.status == "relevant")
        .subquery()
    )
    chunk_text_basis = chunk_text_basis_case(
        chunk_table.c.source_snapshot_id,
        screened_docs.c.envelope_snapshot_id,
        screened_docs.c.text_basis,
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
            chunk_text_basis,
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
                "text_basis": cast("str", row.text_basis),
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
        # Unit text is frozen for the retriever's lifetime — tokenize once,
        # not on every search() call.
        self._unit_tokens: list[set[str]] = [
            _tokens(cast("str", unit["text"])) for unit in scope.units
        ]
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
                len(query_tokens & unit_tokens) / max(1, len(query_tokens)),
                unit,
            )
            for unit, unit_tokens in zip(self._scope.units, self._unit_tokens, strict=True)
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
        result: ChunkSearchResult = {
            "chunk_record_id": chunk_id,
            "pss_id": pss_id,
            "document_title": cast("str", doc["title"]),
            "sequence": cast("int", chunk["sequence"]),
            "content": cast("str", chunk["content"]),
            "text_basis": cast("str", chunk["text_basis"]),
            "origin": "selected" if doc.get("selected") else "unselected_screened",
            "appraised": doc.get("appraisal_tier") is not None,
            "fused_score": score,
        }
        # Owner-adopted default metadata set (ADR 0015 §8 / B-B3), sourced from
        # the doc record, omit-if-absent (no null-noise).
        year = doc.get("year", doc.get("publication_year"))
        if year is not None:
            result["year"] = year
        evidence_type = doc.get("primary_evidence_type")
        if evidence_type is not None:
            result["evidence_type"] = cast("str", evidence_type)
        appraisal_label = doc.get("appraisal_tier")
        if appraisal_label is not None:
            result["appraisal_label"] = cast("str", appraisal_label)
        venue = doc.get("venue")
        if venue is not None:
            result["venue"] = venue
        cited_by = doc.get("cited_by")
        if cited_by is not None:
            result["cited_by"] = cited_by
        return result

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
) -> tuple[list[dict[str, Any]], set[str]]:
    row = conn.execute(
        sa_select(extraction_result.c.docs, extraction_result.c.extraction_provenance)
        .where(extraction_result.c.project_id == project_id)
        .where(extraction_result.c.evidence_scope_id == evidence_scope_id)
        .where(extraction_result.c.run_id == extraction_run_id)
    ).first()
    if row is None:
        return [], set()
    docs = row.docs
    if not isinstance(docs, list):
        return [], set()
    mapped_docs = [cast("dict[str, Any]", doc) for doc in docs if isinstance(doc, dict)]
    provenance = row.extraction_provenance
    if not isinstance(provenance, Mapping):
        raise ToolValidationError(
            "corrupt_reference: extraction_result.extraction_provenance must be an object"
        )
    profiles = provenance.get("profiles")
    if not isinstance(profiles, Mapping):
        raise ToolValidationError(
            "corrupt_reference: extraction_result.extraction_provenance missing "
            "the profiles map"
        )
    return mapped_docs, {key for key in profiles if isinstance(key, str)}


def _record_ids_from_profile_map(raw_ids: Sequence[Any]) -> list[uuid.UUID]:
    record_ids: list[uuid.UUID] = []
    for raw_id in raw_ids:
        if isinstance(raw_id, uuid.UUID):
            record_ids.append(raw_id)
        elif isinstance(raw_id, str):
            try:
                record_ids.append(uuid.UUID(raw_id))
            except ValueError:
                continue
    return record_ids


def _finding_record(row: Any) -> FindingRecord:
    metadata = row.metadata if isinstance(row.metadata, dict) else {}
    pss_id = cast("uuid.UUID", row.project_source_snapshot_id)
    record: FindingRecord = {
        "kind": "iof",
        "finding_id": str(row.finding_id),
        "extraction_record_id": str(row.extraction_record_id),
        "pss_id": str(pss_id),
        "document_title": _metadata_title(metadata, pss_id),
        "intervention": cast("str", row.intervention),
        "outcome": cast("str", row.outcome),
        "population": cast("str | None", row.population),
        "setting": cast("str | None", row.setting),
        "comparator": cast("str | None", row.comparator),
        "effect_direction": cast("str", row.effect_direction),
        "estimate_level": cast("str | None", row.estimate_level),
        "study_design": cast("str | None", row.study_design),
        "study_geography": cast("str | None", row.study_geography),
        "stratum_qualifiers": cast("list[dict[str, str]]", row.stratum_qualifiers),
        "statistics": cast("dict[str, Any]", row.statistics),
        "causality_by_design": cast("str | None", row.causality_by_design),
        "effect_basis": cast("str | None", row.effect_basis),
        "is_primary": cast("bool | None", row.is_primary),
        "field_coverage": cast("dict[str, str]", row.field_coverage),
    }
    # Owner-adopted default metadata set (ADR 0015 §8 / B-B3), omit-if-absent.
    year = _metadata_year(metadata)
    if year is not None:
        record["year"] = year
    evidence_type = getattr(row, "primary_evidence_type", None)
    if evidence_type is not None:
        record["evidence_type"] = cast("str", evidence_type)
    quality_score = getattr(row, "quality_score", None)
    if quality_score is not None:
        record["appraisal_label"] = str(quality_score)
    venue = _metadata_venue(metadata)
    if venue is not None:
        record["venue"] = venue
    cited_by = _metadata_cited_by(metadata)
    if cited_by is not None:
        record["cited_by"] = cited_by
    return record


def _icf_finding_record(row: Any) -> ICFFindingRecord:
    metadata = row.metadata if isinstance(row.metadata, dict) else {}
    pss_id = cast("uuid.UUID", row.project_source_snapshot_id)
    record: ICFFindingRecord = {
        "kind": "icf",
        "finding_id": str(row.finding_id),
        "extraction_record_id": str(row.extraction_record_id),
        "pss_id": str(pss_id),
        "document_title": _metadata_title(metadata, pss_id),
        "context_type": cast("str", row.context_type),
        "claim": cast("str", row.claim),
        "intervention": cast("str", row.intervention),
        "outcome": cast("str | None", row.outcome),
        "population": cast("str | None", row.population),
        "setting": cast("str | None", row.setting),
        "study_geography": cast("str | None", row.study_geography),
        "study_design": cast("str | None", row.study_design),
        "claim_level": cast("str | None", row.claim_level),
        "claim_basis": cast("str | None", row.claim_basis),
        "level": cast("str | None", row.level),
        "resource_requirements": cast("str | None", row.resource_requirements),
        "workforce_requirements": cast("str | None", row.workforce_requirements),
        "field_coverage": cast("dict[str, str]", row.field_coverage),
    }
    year = _metadata_year(metadata)
    if year is not None:
        record["year"] = year
    evidence_type = getattr(row, "primary_evidence_type", None)
    if evidence_type is not None:
        record["evidence_type"] = cast("str", evidence_type)
    quality_score = getattr(row, "quality_score", None)
    if quality_score is not None:
        record["appraisal_label"] = str(quality_score)
    venue = _metadata_venue(metadata)
    if venue is not None:
        record["venue"] = venue
    cited_by = _metadata_cited_by(metadata)
    if cited_by is not None:
        record["cited_by"] = cited_by
    return record


def _load_iof_finding_records(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    extraction_record_ids: Sequence[uuid.UUID],
) -> list[FindingRecord]:
    if not extraction_record_ids:
        return []
    rows = conn.execute(
        sa_select(
            intervention_outcome_finding.c.finding_id,
            intervention_outcome_finding.c.extraction_record_id,
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
            source_extraction_record.c.project_source_snapshot_id,
            source_snapshot.c.metadata,
            source_classification_result.c.primary_evidence_type,
            source_appraisal_result.c.quality_score,
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
            source_snapshot.c.source_snapshot_id == project_source_snapshot.c.source_snapshot_id,
        )
        .outerjoin(
            source_classification_result,
            (
                source_classification_result.c.project_source_snapshot_id
                == project_source_snapshot.c.project_source_snapshot_id
            )
            & (source_classification_result.c.project_id == project_id)
            & (source_classification_result.c.evidence_scope_id == evidence_scope_id),
        )
        .outerjoin(
            source_appraisal_result,
            (
                source_appraisal_result.c.project_source_snapshot_id
                == project_source_snapshot.c.project_source_snapshot_id
            )
            & (source_appraisal_result.c.project_id == project_id)
            & (source_appraisal_result.c.evidence_scope_id == evidence_scope_id),
        )
        .where(intervention_outcome_finding.c.project_id == project_id)
        .where(intervention_outcome_finding.c.extraction_record_id.in_(extraction_record_ids))
        .order_by(
            intervention_outcome_finding.c.extraction_record_id,
            intervention_outcome_finding.c.finding_id,
        )
    ).fetchall()
    return [_finding_record(row) for row in rows]


def _load_icf_finding_records(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    extraction_record_ids: Sequence[uuid.UUID],
) -> list[ICFFindingRecord]:
    if not extraction_record_ids:
        return []
    rows = conn.execute(
        sa_select(
            implementation_context_finding.c.finding_id,
            implementation_context_finding.c.extraction_record_id,
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
            source_extraction_record.c.project_source_snapshot_id,
            source_snapshot.c.metadata,
            source_classification_result.c.primary_evidence_type,
            source_appraisal_result.c.quality_score,
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
            project_source_snapshot,
            (
                project_source_snapshot.c.project_source_snapshot_id
                == source_extraction_record.c.project_source_snapshot_id
            )
            & (project_source_snapshot.c.project_id == project_id),
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
            & (source_classification_result.c.evidence_scope_id == evidence_scope_id),
        )
        .outerjoin(
            source_appraisal_result,
            (
                source_appraisal_result.c.project_source_snapshot_id
                == project_source_snapshot.c.project_source_snapshot_id
            )
            & (source_appraisal_result.c.project_id == project_id)
            & (source_appraisal_result.c.evidence_scope_id == evidence_scope_id),
        )
        .where(implementation_context_finding.c.project_id == project_id)
        .where(implementation_context_finding.c.extraction_record_id.in_(extraction_record_ids))
        .order_by(
            implementation_context_finding.c.extraction_record_id,
            implementation_context_finding.c.finding_id,
        )
    ).fetchall()
    return [_icf_finding_record(row) for row in rows]


def _group_member_ids(grouping_groups: list[dict[str, Any]] | None) -> dict[str, set[str]]:
    if grouping_groups is None:
        return {}
    resolved: dict[str, set[str]] = {}
    for group in grouping_groups:
        raw_id = group.get("group_id")
        raw_members = group.get("member_finding_ids") or group.get("finding_ids")
        if not isinstance(raw_id, str) or not is_qualified_group_id(raw_id):
            raise ToolValidationError(
                f"grouping group ids must use expected form {GROUP_ID_EXPECTED_FORM}"
            )
        if isinstance(raw_members, list):
            resolved[raw_id] = {member for member in raw_members if isinstance(member, str)}
    return resolved


def _requested_finding_kinds(arguments: dict[str, Any]) -> tuple[str, ...]:
    raw_kinds = arguments.get("kinds")
    if raw_kinds is None:
        return FINDING_KINDS
    requested = []
    seen: set[str] = set()
    for kind in raw_kinds:
        if isinstance(kind, str) and kind in FINDING_KINDS and kind not in seen:
            requested.append(kind)
            seen.add(kind)
    return tuple(kind for kind in FINDING_KINDS if kind in seen)


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
    extraction_docs, available_profiles = _load_extraction_docs(
        conn,
        project_id=project_id,
        extraction_run_id=extraction_run_id,
        evidence_scope_id=evidence_scope_id,
    )
    ids_by_profile = {
        profile_id: _record_ids_from_profile_map(raw_ids)
        for profile_id, raw_ids in record_ids_by_profile(extraction_docs).items()
    }
    group_members = _group_member_ids(grouping_groups)
    iof_findings = (
        _load_iof_finding_records(
            conn,
            project_id=project_id,
            evidence_scope_id=evidence_scope_id,
            extraction_record_ids=ids_by_profile.get(IOF_PROFILE_ID, []),
        )
        if IOF_PROFILE_ID in available_profiles
        else []
    )
    icf_findings = (
        _load_icf_finding_records(
            conn,
            project_id=project_id,
            evidence_scope_id=evidence_scope_id,
            extraction_record_ids=ids_by_profile.get(ICF_PROFILE_ID, []),
        )
        if ICF_PROFILE_ID in available_profiles
        else []
    )
    findings_by_kind: dict[str, list[dict[str, Any]]] = {
        "iof": [dict(finding) for finding in iof_findings],
        "icf": [dict(finding) for finding in icf_findings],
    }
    available_by_kind = {
        kind
        for kind, profile_id in FINDING_KIND_PROFILES.items()
        if profile_id in available_profiles
    }

    def reader(arguments: dict[str, Any]) -> dict[str, Any]:
        _validate_findings_tool_arguments(arguments)
        requested_kinds = _requested_finding_kinds(arguments)
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
            if not is_qualified_group_id(group_id):
                _tool_fail(f"group_id must use expected form {GROUP_ID_EXPECTED_FORM}")
            if group_id not in group_members:
                _tool_fail(
                    f"unknown group_id; expected form {GROUP_ID_EXPECTED_FORM} "
                    "resolving to grouping records"
                )
            group_filter = group_members[group_id]

        effect_direction = arguments.get("effect_direction")
        if effect_direction is not None and effect_direction not in EFFECT_DIRECTIONS:
            _tool_fail("effect_direction is invalid")
        context_type = arguments.get("context_type")
        if context_type is not None and context_type not in CONTEXT_TYPES:
            _tool_fail("context_type is invalid")

        result: dict[str, Any] = {}
        for kind in requested_kinds:
            result_key = f"{kind}_findings"
            if kind not in available_by_kind:
                result[result_key] = FINDING_KIND_UNAVAILABLE
                continue
            selected = list(findings_by_kind[kind])
            if requested_ids is not None:
                selected = [
                    finding for finding in selected if finding["finding_id"] in requested_ids
                ]
            if group_filter is not None:
                selected = [
                    finding for finding in selected if finding["finding_id"] in group_filter
                ]
            if kind == "iof" and effect_direction is not None:
                selected = [
                    finding
                    for finding in selected
                    if finding["effect_direction"] == effect_direction
                ]
            if kind == "icf" and context_type is not None:
                selected = [
                    finding
                    for finding in selected
                    if finding["context_type"] == context_type
                ]
            truncated = len(selected) > 100
            result[result_key] = selected[:100]
            result[f"{kind}_truncated"] = truncated
        return result

    return reader


def _ensure_kind(arguments: dict[str, Any]) -> str:
    kind = _tool_string(arguments, field="kind", max_length=100, required=True)
    assert kind is not None
    if kind not in LOOKUP_QUERY_KINDS:
        _tool_fail("unknown lookup kind")
    return kind


def _screened_in_doc_ids(project_id: uuid.UUID, scope_id: uuid.UUID) -> Any:
    """Select of this scope's screened-in doc ids — the lookup read boundary.

    Effective-relevant via the helper (never a raw status='relevant' join),
    per the same screened-in-scope rule as ``_load_retrieval_scope``.
    """
    effective = effective_screen_rows()
    return (
        sa_select(effective.c.project_source_snapshot_id)
        .where(effective.c.project_id == project_id)
        .where(effective.c.evidence_scope_id == scope_id)
        .where(effective.c.status == "relevant")
    )


def _doc_id_for_scope(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    arguments: dict[str, Any],
) -> uuid.UUID:
    raw_doc_id = _tool_string(arguments, field="doc_id", max_length=100, required=True)
    assert raw_doc_id is not None
    doc_id = _parse_uuid(raw_doc_id, field="doc_id")
    exists = conn.execute(
        sa_select(project_source_snapshot.c.project_source_snapshot_id)
        .where(project_source_snapshot.c.project_id == project_id)
        .where(project_source_snapshot.c.project_source_snapshot_id == doc_id)
        .where(
            project_source_snapshot.c.project_source_snapshot_id.in_(
                _screened_in_doc_ids(project_id, scope_id)
            )
        )
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
        return {"groups": [], "residuals": {}, "facets": []}
    if isinstance(groups_payload.get("groups"), list):
        raise ToolValidationError(
            "grouping groups must be facet-keyed with group ids using expected "
            f"form {GROUP_ID_EXPECTED_FORM}"
        )
    groups: list[dict[str, Any]] = []
    residuals_by_facet: dict[str, dict[str, Any]] = {}
    facets: list[str] = []
    for facet, facet_payload in groups_payload.items():
        if not isinstance(facet, str) or not isinstance(facet_payload, dict):
            continue
        facet_groups = facet_payload.get("groups")
        if not isinstance(facet_groups, list):
            continue
        facets.append(facet)
        for item in facet_groups:
            if not isinstance(item, dict):
                continue
            group = {**item, "facet": item.get("facet", facet)}
            group_id = group.get("group_id")
            if not isinstance(group_id, str) or not is_qualified_group_id(group_id):
                raise ToolValidationError(
                    f"grouping group ids must use expected form {GROUP_ID_EXPECTED_FORM}"
                )
            if group_id.split(":", 1)[0] != facet:
                raise ToolValidationError(
                    "grouping group id facet must match its payload facet; "
                    f"expected form {GROUP_ID_EXPECTED_FORM}"
                )
            members = group.get("member_finding_ids", [])
            if not isinstance(members, list):
                members = []
            groups.append({
                "group_id": group_id,
                "facet": group.get("facet", facet),
                "label": group.get("label"),
                "description": group.get("description"),
                "size": group.get("size", len(members)),
                "direction_spread": group.get("direction_spread", {}),
                "member_finding_ids": members,
            })
        facet_residuals = {"ungrouped": facet_payload.get("ungrouped")}
        if "no_value" in facet_payload:
            facet_residuals["no_value"] = facet_payload.get("no_value")
        residuals_by_facet[facet] = facet_residuals
    return {
        "groups": groups,
        "residuals": residuals_by_facet,
        "facets": facets,
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
            doc_id = _doc_id_for_scope(
                conn, project_id=project_id, scope_id=scope_id, arguments=arguments
            )
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
                .where(
                    source_tag.c.project_source_snapshot_id.in_(
                        _screened_in_doc_ids(project_id, scope_id)
                    )
                )
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
                .where(
                    source_tag.c.project_source_snapshot_id.in_(
                        _screened_in_doc_ids(project_id, scope_id)
                    )
                )
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
    malformed_claims = 0
    usage_totals = UsageAccumulator()

    for turn in range(1, turn_cap + 1):
        force_emit = turn == turn_cap
        try:
            result, usage = backend.section_turn(seed, transcript, force_emit=force_emit)
            usage_totals.add(usage)
        except MalformedEmissionError as exc:
            if force_emit:
                raise RuntimeError(
                    "malformed claims emission on the forced final turn"
                ) from exc
            transcript.append({
                "tool": "emit_section",
                "arguments": {},
                "result": {"error": f"emit_section arguments invalid: {exc}"},
            })
            rejected_tool_calls += 1
            continue
        claims = result.get("claims")
        tool_calls = result.get("tool_calls", [])
        malformed_claims += int(result.get("malformed_claims", 0))
        if claims is not None:
            return {
                "claims": claims,
                "transcript": transcript,
                "turns_used": turn,
                "tool_call_counts": tool_call_counts,
                "rejected_tool_calls": rejected_tool_calls,
                "turn_cap_hit": force_emit,
                "malformed_claims": malformed_claims,
                "usage_totals": usage_totals.payload(),
            }
        if force_emit and tool_calls:
            raise RuntimeError("backend returned tool call on forced emit turn")
        if not tool_calls:
            raise RuntimeError("backend returned no claims or tool calls")

        executed_this_turn = 0
        for call in tool_calls:
            tool_name = call.get("tool")
            arguments = call.get("arguments", {})
            if not isinstance(tool_name, str):
                tool_name = "invalid"
            if not isinstance(arguments, dict):
                arguments = {}
            if executed_this_turn >= READ_CALLS_PER_TURN_CAP:
                transcript.append({
                    "tool": tool_name,
                    "arguments": cast("dict[str, Any]", arguments),
                    "result": {
                        "error": (
                            f"read batch limit ({READ_CALLS_PER_TURN_CAP} per turn) "
                            "exceeded; call not executed — re-request next turn"
                        )
                    },
                })
                rejected_tool_calls += 1
                continue
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
            executed_this_turn += 1

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
            for key in ("findings", "iof_findings", "icf_findings"):
                findings = result.get(key, [])
                if isinstance(findings, list):
                    for finding in findings:
                        if isinstance(finding, dict) and isinstance(
                            finding.get("finding_id"), str
                        ):
                            finding_ids.add(cast("str", finding["finding_id"]))
    return {"chunk_ids": chunk_ids, "finding_ids": finding_ids}
