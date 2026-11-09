"""Section-loop tools, retrieval helper, loop runner and directive parser (task 013).

This module owns the *code-enforced* side of the repo's first agent loop: the
plan-pinned constants, the three read-only scoped tools (``search_chunks`` /
``query_findings`` / ``lookup``), the staged retrieval pipeline behind the
``retrieve`` seam's first increment, the bounded loop runner, and the
fail-closed ``context["synthesis"]`` directive parser. The prompt-bearing
surfaces live in :mod:`policy_atlas.evidence_search.synthesis.section_prompt` and
:mod:`policy_atlas.evidence_search.synthesis.grounding_judge`; nothing in this module
composes prose.

Disciplines binding here (contract 013): the tool set is closed, read-only and
substrate-scoped; an unknown tool name is a validation error, never executed;
caps are enforced in code and cap exhaustion forces the claims emission, never
extends the loop; ``search`` remains acquire's alone — no egress verb exists in
this module.
"""

from __future__ import annotations

import hashlib
import html
import json
import math
import re
import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager, nullcontext
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, NotRequired, Protocol, TypedDict, cast

import structlog
from sqlalchemy import ColumnElement, case, func, true
from sqlalchemy import select as sa_select
from sqlalchemy import text as sa_text
from sqlalchemy.engine import Connection
from sqlalchemy.sql.elements import Label

from policy_atlas.api.stage_vocabulary import activity
from policy_atlas.core import liveness, tracing
from policy_atlas.core.embeddings import (
    EMBEDDING_PROFILE,
    UNIT_CHAR_BUDGET,
    UNIT_POLICY,
    embed_with_retry,
    validate_vector,
)
from policy_atlas.core.liveness import ACTIVITY_QUERY_MAX as ACTIVITY_QUERY_MAX
from policy_atlas.core.liveness import normalise_query as normalise_query
from policy_atlas.core.schema import (
    CONTEXT_TYPES,
    EFFECT_DIRECTIONS,
    EVIDENCE_TYPES,
    characterisation_result,
    chunk_embedding,
    extraction_result,
    grouping_result,
    implementation_context_finding,
    intervention_outcome_finding,
    search_coverage_record,
    selection_result,
    source_appraisal_result,
    source_classification_result,
    source_extraction_record,
    source_screening_result,
    source_snapshot,
    source_tag,
    task_source_snapshot,
    vector_literal,
)
from policy_atlas.core.schema import chunk as chunk_table
from policy_atlas.core.tags import has_control_character
from policy_atlas.core.tokens import word_tokens as _tokens
from policy_atlas.core.usage import UsageAccumulator, UsageResult, add_token_usage
from policy_atlas.evidence_search.assess.appraise import appraisal_tier
from policy_atlas.evidence_search.assess.screen import effective_screen_rows
from policy_atlas.evidence_search.extract.extract import record_ids_by_profile
from policy_atlas.evidence_search.extract.icf_records import PROFILE_ID as ICF_PROFILE_ID
from policy_atlas.evidence_search.extract.iof_records import PROFILE_ID as IOF_PROFILE_ID
from policy_atlas.evidence_search.extract.quote_verify import QuoteMatcher, build_basis

if TYPE_CHECKING:
    from policy_atlas.evidence_search.synthesis.section_prompt import SectionProseWire

log = structlog.get_logger()

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
SYNTH_CHUNK_TOP_K = 8
SYNTH_CHUNK_CHAR_BUDGET = 24_000
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
# Oversized chunks are returned as the winning embedding unit widened by this
# many characters on each side. Normal chunks are never windowed.
OVERSIZED_CHUNK_WINDOW_MARGIN_CHARS = 300
SCREEN_CONFIDENCE_MIN = 0.5
SCREEN_CONFIDENCE_MAX = 4.0
SCREEN_CONFIDENCE_DEFAULT_LO = 1.0
SCREEN_CONFIDENCE_DEFAULT_HI = 2.0
# The closed column set the directive may boost over (select's vocabulary).
BOOST_COLUMNS = ("origin", "primary_evidence_type", "text_basis")
# search_chunks query bound (022 rider 16 shares this with the per-turn query
# embedding batch warm-up, so both sides of the bound stay in one place).
SEARCH_QUERY_MAX_LENGTH = 1000
# Shared row cap for windowed lookup/selection returns (one knob, two surfaces).
LOOKUP_ROW_CAP = 100
# Bounds shared with the directive grammar (contract rev 8 M5).
DIRECTIVE_SECTION_TEXT_MAX = 200
# A template's section instructions are code, not model output: the baseline's
# eight foci (``baseline_prompt.BASELINE_SECTIONS``) are lead-authored, versioned
# with the template and 250-450 characters each. The 200-character bound above
# exists to fence *untrusted* directive text — a steering delta, a proposal —
# so it still governs every title, every nav label and every focus outside
# template mode (task 044, plan S2).
DIRECTIVE_TEMPLATE_FOCUS_MAX = 600
DIRECTIVE_LIST_MAX = 200

# The closed lookup query vocabulary v1 (plan rev 2). Unknown kind → tool-level
# validation error, never executed; all queries scoped to task_id + the
# resolved run references; side-effect-free.
#
# ``screening_by_doc`` (022 rider 16) widens the vocabulary to screening rows:
# unlike the other ``_by_doc`` kinds, its doc_id is NOT required to be
# screened-in — that is the whole point of the widening (a not_relevant /
# excluded_retracted doc's own screening history is otherwise unreachable to
# an in-loop reader).
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
    "screening_by_doc",
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
    tss_id: str  # owning task_source_snapshot
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
    window_start: NotRequired[int]
    window_end: NotRequired[int]


class FindingRecord(TypedDict):
    """One extracted finding as id-keyed data for the section loop.

    Anchors are extract-verified; the model cites ``finding_id`` and never
    authors these quotes — code resolves cited ids back to the stored anchors.
    """

    kind: Literal["iof"]
    finding_id: str
    extraction_record_id: str
    tss_id: str
    document_title: str
    intervention: str
    outcome: str
    unit: str | None
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
    # B2′ (024 / ADR 0023): "priority" | "normal" when this run's extraction
    # carries relevance annotations; absent otherwise (never fabricated).
    relevance: NotRequired[str]
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
    tss_id: str
    document_title: str
    context_type: str
    claim: str
    intervention: str
    outcome: str | None
    unit: str | None
    setting: str | None
    study_geography: str | None
    study_design: str | None
    claim_level: str | None
    claim_basis: str | None
    level: str | None
    resource_requirements: str | None
    workforce_requirements: str | None
    field_coverage: dict[str, str]
    # B2′ (024 / ADR 0023): "priority" | "normal" when this run carries
    # relevance annotations; absent otherwise (never fabricated).
    relevance: NotRequired[str]
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
class _ScreenConfidenceBoost:
    """Validated screen-confidence retrieval multiplier bounds."""

    lo: float = SCREEN_CONFIDENCE_DEFAULT_LO
    hi: float = SCREEN_CONFIDENCE_DEFAULT_HI


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
    section_budget: int | None = None
    #: Output kind. ``None`` is the Evidence search report — today's behaviour,
    #: unchanged. ``"baseline"`` is **parsed** as of task 044 phase 3.2 and its
    #: behaviour lands in phase 4.2; until then ``synthesise_scope`` accepts it
    #: and does nothing beyond the supplied-sections path it already has.
    template: str | None = None
    column_boosts: dict[str, dict[str, float]] = field(default_factory=dict)
    tag_boosts: dict[str, float] = field(default_factory=dict)
    appraisal_tier_boosts: dict[str, float] = field(default_factory=dict)
    screen_confidence: _ScreenConfidenceBoost = field(
        default_factory=_ScreenConfidenceBoost
    )

    def as_provenance(self) -> dict[str, Any]:
        """Return the executed directive as deterministic JSON-compatible data."""
        return {
            "sections_source": "scope_context" if self.sections is not None else "proposal",
            "section_budget": self.section_budget,
            # The output kind the run executed (task 044): ``None`` is the
            # Evidence search report. Recorded so replay never has to infer it.
            "template": self.template,
            "retrieval_boosts": {
                "columns": self.column_boosts,
                "tags": self.tag_boosts,
                "appraisal_tier": self.appraisal_tier_boosts,
                "screen_confidence": {
                    "lo": self.screen_confidence.lo,
                    "hi": self.screen_confidence.hi,
                },
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


#: Opens the connection one search reads through. Synthesis lends its own
#: component connection (:func:`borrowed_connection`); chat passes
#: ``engine.connect`` so every search is one short read on a fresh connection.
ConnectionFactory = Callable[[], AbstractContextManager[Connection]]


def borrowed_connection(conn: Connection) -> ConnectionFactory:
    """Return a connection factory that hands out ``conn`` and never closes it.

    Synthesis searches inside its component transaction (same isolation as every
    other read there), so the retriever borrows that connection rather than
    opening its own.

    Args:
        conn: The open connection to lend.

    Returns:
        A factory whose context manager yields ``conn`` and leaves it open.
    """
    return lambda: nullcontext(conn)


@dataclass(frozen=True)
class RetrievalScope:
    """The frozen retrieval scope of one synthesis run or one chat turn (task 057).

    It holds the documents and the snapshot each one's text lives in, read once;
    every search then runs one SQL statement over those snapshots, so no chunk
    text or vector is held in memory.

    Attributes:
        docs: Metadata keyed by task_source_snapshot id string (the prior's and
            the filters' inputs).
        snapshot_by_tss: The text-bearing snapshot per document (the full-text
            snapshot when one was ingested, else the envelope), frozen once.
        chunk_text_basis_by_tss: ``"abstract_only"`` or ``"full_text"`` per
            document: what its chunks are cut from.
        connect: Opens the connection each search reads through.
        task_tags: All tag values in the scoped task.
        unit_count: Embedding units in scope when the scope was built
            (provenance only).
    """

    docs: dict[str, dict[str, Any]]
    snapshot_by_tss: dict[str, uuid.UUID]
    chunk_text_basis_by_tss: dict[str, str]
    connect: ConnectionFactory
    task_tags: set[str] = field(default_factory=set)
    unit_count: int = 0

    @property
    def snapshot_ids(self) -> tuple[uuid.UUID, ...]:
        """The distinct text-bearing snapshot ids of the scope, sorted."""
        return tuple(sorted(set(self.snapshot_by_tss.values())))


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
    # Further tool calls a forced final turn carried beyond the emission that
    # was taken (task 056 D10: parallel tool calls stay on for that turn).
    extra_tool_calls_ignored: int
    usage_totals: dict[str, int]


class LoopTurn(TypedDict):
    """One backend response consumed by the shared bounded tool loop."""

    emission: Any | None
    tool_calls: list[dict[str, Any]]
    malformed: int
    extra_ignored: NotRequired[int]


class ToolLoopResult(TypedDict):
    """Outcome of one bounded tool loop with an adapter-owned emission."""

    emission: Any | None
    transcript: list[ToolExchange]
    turns_used: int
    tool_call_counts: dict[str, int]
    rejected_tool_calls: int
    turn_cap_hit: bool
    malformed_claims: int
    extra_tool_calls_ignored: int
    usage_totals: dict[str, int]


TurnFn = Callable[..., UsageResult[LoopTurn]]


_DIRECTIVE_KEYS = {"sections", "retrieval_boosts", "section_budget", "template"}

#: The output kinds ``template`` may name. Fail-closed: an unrecognised
#: template would otherwise silently fall back to the Evidence search report
#: while the plan row claims a baseline was written (task 044, plan S2).
TEMPLATE_KEYS = frozenset({"baseline"})

_SECTION_KEYS_REQUIRED = {"title", "focus"}
_SECTION_KEYS_WITH_GROUPS = {"title", "focus", "group_ids"}
#: ``nav_label`` is an optional extra on any section spec. ``SectionSpec`` and
#: ``_sections_from_directive`` have always read it; before task 044 the key
#: set below rejected it first, so a supplied section could never carry one.
#: ``turn_cap`` joined it in phase 4.2: a template's sections carry their own
#: generation-loop bound (the baseline's is
#: ``baseline_prompt.BASELINE_SECTION_TURN_CAP``), and a supplied section that
#: omits it falls back to the template default / ``SECTION_TURN_CAP``.
_SECTION_KEYS_OPTIONAL: set[str] = {"nav_label", "turn_cap"}
_SECTION_KEYS_ALLOWED: set[str] = _SECTION_KEYS_WITH_GROUPS | _SECTION_KEYS_OPTIONAL
_BOOST_KEYS = {"columns", "tags", "appraisal_tier", "screen_confidence"}
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


def facet_of_group_id(group_id: str) -> str:
    """Return the facet prefix of a facet-qualified group id.

    Owns the prefix-derivation half of the ``<facet>:gNN`` grammar so callers
    never re-implement the split.

    Args:
        group_id: Facet-qualified group id (``<facet>:gNN`` shape).

    Returns:
        The facet prefix.
    """
    return group_id.split(":", 1)[0]


def _bounded_string(
    value: Any, *, field: str, max_length: int = DIRECTIVE_SECTION_TEXT_MAX
) -> str:
    if not isinstance(value, str):
        _directive_fail(f"synthesis directive {field} must be a string")
    text = cast("str", value)
    if not text:
        _directive_fail(f"synthesis directive {field} must be non-empty")
    if len(text) > max_length:
        _directive_fail(
            f"synthesis directive {field} exceeds {max_length} characters"
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


def _tool_string_list(arguments: dict[str, Any], *, field: str) -> list[str] | None:
    raw_value = arguments.get(field)
    if raw_value is None:
        return None
    if (
        not isinstance(raw_value, list)
        or not raw_value
        or len(raw_value) > DIRECTIVE_LIST_MAX
    ):
        _tool_fail(f"{field} must be a bounded non-empty list")
    values: list[str] = []
    for item in raw_value:
        if not isinstance(item, str) or not item:
            _tool_fail(f"{field} must contain non-empty strings")
        if len(item) > DIRECTIVE_SECTION_TEXT_MAX or has_control_character(item):
            _tool_fail(f"{field} must contain bounded strings")
        values.append(item)
    return values


def _search_scope_filters(
    arguments: dict[str, Any],
    *,
    retriever: ChunkRetriever,
    group_doc_ids_by_group_id: Mapping[str, set[str]] | None,
) -> _ChunkScopeFilters | None:
    doc_ids: frozenset[str] | None = None
    raw_doc_ids = _tool_string_list(arguments, field="doc_ids")
    if raw_doc_ids is not None:
        parsed_doc_ids: set[str] = set()
        for raw_doc_id in raw_doc_ids:
            try:
                parsed_doc_ids.add(str(uuid.UUID(raw_doc_id)))
            except ValueError as exc:
                raise ToolValidationError("doc_ids must contain UUID strings") from exc
        unknown_doc_ids = sorted(parsed_doc_ids - set(retriever._scope.docs))
        if unknown_doc_ids:
            _tool_fail("doc_ids contains ids outside the scoped corpus")
        doc_ids = frozenset(parsed_doc_ids)

    group_doc_ids: frozenset[str] | None = None
    raw_group_ids = _tool_string_list(arguments, field="group_ids")
    if raw_group_ids is not None:
        if group_doc_ids_by_group_id is None:
            _tool_fail("group_ids requires grouping")
        resolved_group_docs: set[str] = set()
        assert group_doc_ids_by_group_id is not None
        for group_id in raw_group_ids:
            if not is_qualified_group_id(group_id):
                _tool_fail(f"group_ids must use expected form {GROUP_ID_EXPECTED_FORM}")
            if group_id not in group_doc_ids_by_group_id:
                _tool_fail(
                    f"group_ids contains an unknown group_id; expected form "
                    f"{GROUP_ID_EXPECTED_FORM} resolving to grouping records"
                )
            resolved_group_docs.update(group_doc_ids_by_group_id[group_id])
        group_doc_ids = frozenset(resolved_group_docs)

    evidence_types: frozenset[str] | None = None
    raw_evidence_types = _tool_string_list(arguments, field="evidence_types")
    if raw_evidence_types is not None:
        unknown_types = sorted(set(raw_evidence_types) - set(EVIDENCE_TYPES))
        if unknown_types:
            _tool_fail("evidence_types contains an unknown evidence type")
        evidence_types = frozenset(raw_evidence_types)

    tags: frozenset[str] | None = None
    raw_tags = _tool_string_list(arguments, field="tags")
    if raw_tags is not None:
        scoped_tags = set(retriever._scope.task_tags)
        if not scoped_tags:
            scoped_tags = {
                tag
                for doc in retriever._scope.docs.values()
                for tag in cast("list[str]", doc.get("tags", []))
            }
        unknown_tags = sorted(set(raw_tags) - scoped_tags)
        if unknown_tags:
            _tool_fail("tags contains an unknown scoped tag")
        tags = frozenset(raw_tags)

    if (
        doc_ids is None
        and group_doc_ids is None
        and evidence_types is None
        and tags is None
    ):
        return None
    return _ChunkScopeFilters(
        doc_ids=doc_ids,
        group_doc_ids=group_doc_ids,
        evidence_types=evidence_types,
        tags=tags,
    )


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


def _screen_confidence_bound(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        _directive_fail(f"synthesis directive {field} must be a number")
    normalized = float(value)
    if not math.isfinite(normalized):
        _directive_fail(f"synthesis directive {field} must be finite")
    return normalized


def _parse_screen_confidence_boost(value: Any) -> _ScreenConfidenceBoost:
    if not isinstance(value, dict):
        _directive_fail(
            "synthesis directive retrieval_boosts.screen_confidence must be an object"
        )
    unknown = set(value) - {"lo", "hi"}
    if unknown:
        _directive_fail(
            "synthesis directive retrieval_boosts.screen_confidence has invalid keys"
        )
    lo = (
        _screen_confidence_bound(
            value["lo"], field="retrieval_boosts.screen_confidence.lo"
        )
        if "lo" in value
        else SCREEN_CONFIDENCE_DEFAULT_LO
    )
    hi = (
        _screen_confidence_bound(
            value["hi"], field="retrieval_boosts.screen_confidence.hi"
        )
        if "hi" in value
        else SCREEN_CONFIDENCE_DEFAULT_HI
    )
    if not SCREEN_CONFIDENCE_MIN <= lo <= hi <= SCREEN_CONFIDENCE_MAX:
        _directive_fail(
            "synthesis directive retrieval_boosts.screen_confidence must satisfy "
            f"{SCREEN_CONFIDENCE_MIN} <= lo <= hi <= {SCREEN_CONFIDENCE_MAX}"
        )
    return _ScreenConfidenceBoost(lo=lo, hi=hi)


def _parse_sections(
    value: Any,
    *,
    grouping_group_ids: set[str] | None,
    section_budget: int | None = None,
    defer_group_membership: bool = False,
    focus_max: int = DIRECTIVE_SECTION_TEXT_MAX,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        _directive_fail("synthesis directive sections must be a list")
    section_cap = min(SECTION_CAP, section_budget) if section_budget is not None else SECTION_CAP
    if not value or len(value) > section_cap:
        _directive_fail(f"synthesis directive sections must contain 1..{section_cap} items")

    from policy_atlas.evidence_search.synthesis.synthesis_backend import FORBIDDEN_SECTION_TITLES

    forbidden = {title.casefold() for title in FORBIDDEN_SECTION_TITLES}
    parsed: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            _directive_fail(f"synthesis directive sections[{index}] must be an object")
        keys = set(item)
        if not _SECTION_KEYS_REQUIRED <= keys <= _SECTION_KEYS_ALLOWED:
            _directive_fail(f"synthesis directive sections[{index}] has invalid keys")
        title = _bounded_string(item["title"], field=f"sections[{index}].title")
        if title.casefold() in forbidden:
            _directive_fail(f"synthesis directive sections[{index}].title is forbidden")
        section: dict[str, Any] = {
            "title": title,
            "focus": _bounded_string(
                item["focus"], field=f"sections[{index}].focus", max_length=focus_max
            ),
        }
        if "nav_label" in item:
            section["nav_label"] = _bounded_string(
                item["nav_label"], field=f"sections[{index}].nav_label"
            )
        if "turn_cap" in item:
            section["turn_cap"] = _parse_section_turn_cap(item["turn_cap"], index)
        if "group_ids" in item:
            if grouping_group_ids is None and not defer_group_membership:
                _directive_fail("synthesis directive group_ids require grouping")
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
                if grouping_group_ids is not None and group_id not in grouping_group_ids:
                    _directive_fail(
                        f"synthesis directive group_ids[{group_index}] is unknown; "
                        f"expected form {GROUP_ID_EXPECTED_FORM} resolving to grouping "
                        "records"
                    )
                group_ids.append(group_id)
            section["group_ids"] = group_ids
        parsed.append(section)
    return parsed


def _parse_section_turn_cap(value: Any, index: int) -> int:
    """Validate one supplied section's generation-loop turn cap.

    Args:
        value: Candidate JSON directive value.
        index: Position of the section in the supplied list, for the message.

    Returns:
        The validated 1..``SECTION_TURN_CAP`` turn cap.

    Raises:
        SynthesisDirectiveError: If it is not an integer in range. Fail-closed
            rather than clamped: a cap is execution-bearing (it bounds provider
            calls), so a malformed one must not silently become a larger one.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        _directive_fail(f"synthesis directive sections[{index}].turn_cap must be an integer")
    if not 1 <= int(value) <= SECTION_TURN_CAP:
        _directive_fail(
            f"synthesis directive sections[{index}].turn_cap must be between 1 "
            f"and {SECTION_TURN_CAP}"
        )
    return int(value)


def _parse_retrieval_boosts(
    value: Any,
) -> tuple[
    dict[str, dict[str, float]],
    dict[str, float],
    dict[str, float],
    _ScreenConfidenceBoost,
]:
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
    screen_confidence = (
        _parse_screen_confidence_boost(value["screen_confidence"])
        if "screen_confidence" in value
        else _ScreenConfidenceBoost()
    )
    return column_boosts, tag_boosts, appraisal_tier_boosts, screen_confidence


def parse_synthesis_directive(
    context: dict[str, Any],
    *,
    grouping_group_ids: set[str] | None,
    defer_group_membership: bool = False,
) -> SynthesisDirective:
    """Parse the fail-closed ``context["synthesis"]`` directive.

    Args:
        context: Evidence-scope context JSON object.
        grouping_group_ids: Valid grouping ids when grouping is referenced, or
            ``None`` when no grouping substrate exists.
        defer_group_membership: Answer-time mode (steering validation, which has
            no grouping substrate on hand): ``group_ids`` are form/bounds-checked
            only, with membership enforced by the execution-time re-parse. Lets
            the P4 as_proposed delta carry the proposal's section→group bindings
            (review 028 M2) instead of 422ing at submit.

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

    template = _parse_template(raw["template"]) if "template" in raw else None
    section_budget = (
        _parse_section_budget(raw["section_budget"])
        if "section_budget" in raw
        else None
    )
    # In template mode ``section_budget`` means "proposals allowed on top of
    # the supplied list" (task 044, plan S2/P14), not "ceiling on the whole
    # report" — the baseline supplies eight required sections and allows two
    # proposals, so capping the supplied list at two would refuse the very
    # directive the template exists to carry. Outside template mode the
    # Evidence search meaning is untouched.
    supplied_cap = None if template is not None else section_budget
    sections = (
        _parse_sections(
            raw["sections"],
            grouping_group_ids=grouping_group_ids,
            section_budget=supplied_cap,
            defer_group_membership=defer_group_membership,
            focus_max=(
                DIRECTIVE_TEMPLATE_FOCUS_MAX
                if template is not None
                else DIRECTIVE_SECTION_TEXT_MAX
            ),
        )
        if "sections" in raw
        else None
    )
    column_boosts: dict[str, dict[str, float]] = {}
    tag_boosts: dict[str, float] = {}
    appraisal_tier_boosts: dict[str, float] = {}
    screen_confidence = _ScreenConfidenceBoost()
    if "retrieval_boosts" in raw:
        (
            column_boosts,
            tag_boosts,
            appraisal_tier_boosts,
            screen_confidence,
        ) = _parse_retrieval_boosts(raw["retrieval_boosts"])
    return SynthesisDirective(
        sections=sections,
        section_budget=section_budget,
        template=template,
        column_boosts=column_boosts,
        tag_boosts=tag_boosts,
        appraisal_tier_boosts=appraisal_tier_boosts,
        screen_confidence=screen_confidence,
    )


def _parse_template(value: Any) -> str:
    """Validate the optional output-template key.

    Args:
        value: Candidate JSON directive value.

    Returns:
        The validated template key.

    Raises:
        SynthesisDirectiveError: If it is not a known template.
    """
    if not isinstance(value, str) or value not in TEMPLATE_KEYS:
        _directive_fail(
            f"synthesis directive template must be one of {sorted(TEMPLATE_KEYS)}"
        )
    return str(value)


def _parse_section_budget(value: Any) -> int:
    """Validate the plan's ordinary-section ceiling in the synthesis grammar.

    Args:
        value: Candidate JSON directive value.

    Returns:
        The validated 2..SECTION_CAP ordinary-section budget.

    Raises:
        SynthesisDirectiveError: If the value is outside the executable range.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        _directive_fail("synthesis directive section_budget must be an integer")
    if not 2 <= value <= SECTION_CAP:
        _directive_fail(
            f"synthesis directive section_budget must be between 2 and {SECTION_CAP}"
        )
    return int(value)


def _metadata_title(metadata: Any, tss_id: uuid.UUID) -> str:
    if isinstance(metadata, dict):
        for key in ("title", "display_name", "name"):
            value = metadata.get(key)
            if isinstance(value, str) and value:
                return value
    return f"source {tss_id}"


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


def _doc_record(row: Any, selected_tss_ids: set[uuid.UUID]) -> dict[str, Any]:
    metadata = row.metadata if isinstance(row.metadata, dict) else {}
    doc: dict[str, Any] = {
        "title": _metadata_title(metadata, cast("uuid.UUID", row.tss_id)),
        "origin": row.origin,
        "primary_evidence_type": row.primary_evidence_type,
        "text_basis": row.text_basis,
        # "4" for a scored row, "Unrated" for a row with no score (task 056); None
        # only when the document has no appraisal row, which keeps it uncitable.
        "appraisal_tier": appraisal_tier(
            row.quality_score, unrated=bool(getattr(row, "unrated", False))
        ),
        "tags": [],
        "selected": cast("uuid.UUID", row.tss_id) in selected_tss_ids,
        "screen_confidence": row.screen_decision_confidence,
        "screen_stage": row.screen_stage,
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
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
    selected_tss_ids: set[uuid.UUID],
    extra_scope_ids: Sequence[uuid.UUID] = (),
    connect: ConnectionFactory,
) -> RetrievalScope:
    """Load the screened-in chunk retrieval scope.

    Reads the documents and the snapshot each one's text lives in, once; no
    chunk text, unit or vector is loaded (task 057 N8). Every later search reads
    the chunks of exactly these snapshots through ``connect``, so documents
    screened in after this call never join a running synthesis.

    **Several scopes** (task 045, S11, P13): an options-scoping chat answers
    over the longlist scope and the option searches' targeted scopes at once.
    A document screened in under more than one of them is **one** document:
    the precedence rule keeps one row per ``task_source_snapshot_id`` — the
    primary scope's row wins, then the latest by ``screened_at`` — and that
    row's scope supplies its classification and appraisal. With no extra
    scope the rule is inert (the effective row is already unique per scope
    and document).

    Args:
        conn: Open database connection.
        task_id: Task id that scopes every read.
        scope_id: Evidence scope id whose relevant screened documents form the
            retrieval corpus; with ``extra_scope_ids``, the primary scope.
        selected_tss_ids: Referenced selection set, used only as a soft prior.
        extra_scope_ids: Further evidence scopes whose relevant screened
            documents join the corpus under the precedence rule.
        connect: Opens the connection each search reads through (see
            :data:`ConnectionFactory`).

    Returns:
        The frozen document records and snapshot list.
    """
    # The text-bearing snapshot per document: the fetched full-text snapshot when
    # the fetch pipeline ingested one, else the envelope snapshot acquired for
    # the doc. full_text_status is fetch-pipeline state, never text availability
    # (schema comment).
    text_snapshot_id = case(
        (
            task_source_snapshot.c.full_text_status == "ingested",
            task_source_snapshot.c.full_text_snapshot_id,
        ),
        else_=task_source_snapshot.c.source_snapshot_id,
    ).label("text_snapshot_id")
    # Screened-in scope = effective-relevant join via the helper (never a raw
    # status='relevant' join, which would leak in demoted docs and double-read
    # confirmed ones).
    effective = effective_screen_rows()
    scope_ids = [scope_id, *(s for s in extra_scope_ids if s != scope_id)]
    # One row per document across the scopes (P13): the primary scope first,
    # then the latest screen, then the scope id for a deterministic tie-break.
    ranked = (
        sa_select(
            effective.c.task_id,
            effective.c.task_source_snapshot_id,
            effective.c.evidence_scope_id,
            effective.c.screen_decision_confidence,
            effective.c.screen_stage,
            func.row_number()
            .over(
                partition_by=effective.c.task_source_snapshot_id,
                order_by=(
                    case((effective.c.evidence_scope_id == scope_id, 0), else_=1),
                    effective.c.screened_at.desc(),
                    effective.c.evidence_scope_id,
                ),
            )
            .label("_scope_rank"),
        )
        .where(effective.c.task_id == task_id)
        .where(effective.c.evidence_scope_id.in_(scope_ids))
        .where(effective.c.status == "relevant")
        .subquery("scope_ranked")
    )
    screened_docs = (
        sa_select(
            task_source_snapshot.c.task_source_snapshot_id.label("tss_id"),
            task_source_snapshot.c.source_snapshot_id.label("envelope_snapshot_id"),
            text_snapshot_id,
            task_source_snapshot.c.origin,
            source_snapshot.c.metadata,
            source_snapshot.c.text_basis,
            source_classification_result.c.primary_evidence_type,
            source_appraisal_result.c.quality_score,
            source_appraisal_result.c.unrated,
            ranked.c.screen_decision_confidence,
            ranked.c.screen_stage,
        )
        .select_from(ranked)
        .join(
            task_source_snapshot,
            (
                task_source_snapshot.c.task_source_snapshot_id
                == ranked.c.task_source_snapshot_id
            )
            & (task_source_snapshot.c.task_id == ranked.c.task_id),
        )
        .join(
            source_snapshot,
            source_snapshot.c.source_snapshot_id == task_source_snapshot.c.source_snapshot_id,
        )
        .outerjoin(
            source_classification_result,
            (
                source_classification_result.c.task_source_snapshot_id
                == task_source_snapshot.c.task_source_snapshot_id
            )
            & (source_classification_result.c.task_id == task_id)
            & (source_classification_result.c.evidence_scope_id == ranked.c.evidence_scope_id),
        )
        .outerjoin(
            source_appraisal_result,
            (
                source_appraisal_result.c.task_source_snapshot_id
                == task_source_snapshot.c.task_source_snapshot_id
            )
            & (source_appraisal_result.c.task_id == task_id)
            & (source_appraisal_result.c.evidence_scope_id == ranked.c.evidence_scope_id),
        )
        .where(ranked.c._scope_rank == 1)
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
    # Every chunk of a document sits on its text snapshot, so the shared
    # chunk_text_basis_case rule gives one answer per document.
    chunk_text_basis = cast(
        "Label[str]",
        chunk_text_basis_case(
            screened_docs.c.text_snapshot_id,
            screened_docs.c.envelope_snapshot_id,
            screened_docs.c.text_basis,
        ),
    ).element.label("chunk_text_basis")
    doc_rows = conn.execute(
        sa_select(screened_docs, chunk_text_basis).order_by(screened_docs.c.tss_id)
    ).fetchall()
    docs = {
        str(row.tss_id): _doc_record(row, selected_tss_ids)
        for row in doc_rows
    }
    snapshot_by_tss = {
        str(row.tss_id): cast("uuid.UUID", row.text_snapshot_id) for row in doc_rows
    }
    chunk_text_basis_by_tss = {
        str(row.tss_id): cast("str", row.chunk_text_basis) for row in doc_rows
    }

    tags_rows = conn.execute(
        sa_select(
            source_tag.c.task_source_snapshot_id,
            source_tag.c.tag,
        )
        .where(source_tag.c.task_id == task_id)
        .where(source_tag.c.task_source_snapshot_id.in_(
            sa_select(screened_docs.c.tss_id)
        ))
        .order_by(
            source_tag.c.task_source_snapshot_id,
            source_tag.c.tag_type,
            source_tag.c.asserted_by,
            source_tag.c.tag,
        )
    ).fetchall()
    for row in tags_rows:
        tss_key = str(row.task_source_snapshot_id)
        if tss_key in docs:
            docs[tss_key]["tags"].append(row.tag)
    for doc in docs.values():
        doc["tags"] = sorted(set(cast("list[str]", doc["tags"])))
    task_tag_rows = conn.execute(
        sa_select(source_tag.c.tag)
        .where(source_tag.c.task_id == task_id)
        .order_by(source_tag.c.tag)
    ).fetchall()
    task_tags = {row.tag for row in task_tag_rows if isinstance(row.tag, str)}

    return RetrievalScope(
        docs=docs,
        snapshot_by_tss=snapshot_by_tss,
        chunk_text_basis_by_tss=chunk_text_basis_by_tss,
        connect=connect,
        task_tags=task_tags,
        unit_count=unit_count,
    )


def _sorted_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sorted_json(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_sorted_json(item) for item in value]
    return value


def oversized_chunk_window(
    content_length: int, anchor_start: int, anchor_end: int
) -> tuple[int, int] | None:
    """Return the window an oversized chunk is cut to, or ``None`` to send it whole.

    The one window rule for every place that hands chunk text to the section
    writer: the ``search_chunks`` tool return (anchored on the winning
    embedding unit) and the repair's dependency chunks (anchored on the cited
    quote, task 056 N5). A chunk at or under ``UNIT_CHAR_BUDGET`` characters is
    never windowed. An oversized one becomes the anchor stretch widened by
    ``OVERSIZED_CHUNK_WINDOW_MARGIN_CHARS`` on each side, clipped to the chunk.
    The caller marks the cut record with ``window_start`` / ``window_end``.

    Args:
        content_length: The full chunk's length in characters.
        anchor_start: Chunk-local start of the stretch to keep (inclusive).
        anchor_end: Chunk-local end of the stretch to keep (exclusive).

    Returns:
        ``(window_start, window_end)`` for an oversized chunk; ``None`` otherwise.

    Raises:
        ValueError: If an oversized chunk's anchor lies outside the chunk.
    """
    if content_length <= UNIT_CHAR_BUDGET:
        return None
    if anchor_start < 0 or anchor_end < anchor_start or anchor_end > content_length:
        raise ValueError("matched retrieval unit offsets are required for windows")
    return (
        max(0, anchor_start - OVERSIZED_CHUNK_WINDOW_MARGIN_CHARS),
        min(content_length, anchor_end + OVERSIZED_CHUNK_WINDOW_MARGIN_CHARS),
    )


def _longest_shared_stretch(haystack: str, needle: str) -> tuple[int, int] | None:
    """Return ``(position in haystack, length)`` of the longest piece of ``needle``.

    Deterministic: the longest length wins; among equal lengths, the earliest
    start in ``needle``, then its first occurrence in ``haystack``. ``None``
    when the two share no character at all.
    """

    def first_hit(length: int) -> int | None:
        for start in range(len(needle) - length + 1):
            position = haystack.find(needle[start : start + length])
            if position != -1:
                return position
        return None

    # A shared piece of length L contains one of every shorter length, so the
    # longest length is found by bisection.
    low, high, best = 1, len(needle), None
    while low <= high:
        middle = (low + high) // 2
        position = first_hit(middle)
        if position is None:
            high = middle - 1
        else:
            best = (position, middle)
            low = middle + 1
    return best


def _quote_anchor(content: str, quote: str) -> tuple[tuple[int, int], bool] | None:
    """Locate ``quote`` in ``content``: ``((start, end), found)`` or ``None``.

    The quote is matched the way verification matches it (the qv_v2
    normalisation of :class:`QuoteMatcher`). When it is not there, the anchor
    is the longest stretch of the normalised quote that is (``found`` False).
    ``None`` when the quote shares nothing with the chunk.
    """
    basis = build_basis([(None, content)])
    match = QuoteMatcher(basis).find(quote)
    if match.spans:
        return (match.spans[0].start, match.spans[-1].end), True
    normalised_quote = build_basis([(None, quote)]).normalised
    stretch = _longest_shared_stretch(basis.normalised, normalised_quote)
    if stretch is None:
        return None
    position, length = stretch
    return (basis.raw_start[position], basis.raw_end[position + length - 1]), False


def _repair_chunk_anchor(
    content: str, cited_quotes: Sequence[str], grounding_quotes: Sequence[str]
) -> tuple[int, int] | None:
    """The stretch of a repair dependency chunk its window is cut around.

    Quotes cited on this chunk all count (found, or their longest matching
    stretch). Finding grounding quotes are not bound to one chunk, so only the
    ones found here count, else the single longest stretch among them. The
    anchor is the span covering every counted stretch; ``None`` when there is
    nothing to anchor on (the chunk is then sent whole).
    """
    stretches: list[tuple[int, int]] = []
    for quote in cited_quotes:
        anchor = _quote_anchor(content, quote)
        if anchor is not None:
            stretches.append(anchor[0])
    grounding = [
        anchor for quote in grounding_quotes if (anchor := _quote_anchor(content, quote))
    ]
    found = [span for span, was_found in grounding if was_found]
    if found:
        stretches.extend(found)
    elif grounding:
        stretches.append(max((span for span, _ in grounding), key=lambda s: s[1] - s[0]))
    if not stretches:
        return None
    return min(start for start, _ in stretches), max(end for _, end in stretches)


def window_repair_dependency_chunks(failing: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cut each failing claim's oversized dependency chunks to a window (task 056 N5).

    Each dependency chunk over the oversized threshold goes through
    :func:`oversized_chunk_window`, anchored on the claim's citation quote for
    that chunk (a finding claim's anchor chunks: its findings' grounding
    quotes), and carries the same ``window_start`` / ``window_end`` marker as a
    windowed ``search_chunks`` return. Chunks at or under the threshold, chunks
    already windowed by the tool return, and chunks with nothing to anchor on
    are sent whole. The input records are not mutated.

    Args:
        failing: Dependency-complete failing-claim records for the repair.

    Returns:
        The records, with oversized dependency chunks windowed.
    """
    windowed: list[dict[str, Any]] = []
    for record in failing:
        dependencies = record.get("dependencies")
        chunks = dependencies.get("chunks") if isinstance(dependencies, dict) else None
        if not isinstance(dependencies, dict) or not isinstance(chunks, dict):
            windowed.append(record)
            continue
        claim = record.get("claim")
        citations = claim.get("citations") if isinstance(claim, dict) else None
        cited: dict[str, list[str]] = {}
        for citation in citations if isinstance(citations, list) else []:
            if isinstance(citation, dict) and isinstance(citation.get("quote"), str):
                chunk_id = str(citation.get("chunk_record_id") or "")
                cited.setdefault(chunk_id, []).append(citation["quote"])
        findings = dependencies.get("findings")
        grounding_quotes = [
            grounding["quote"]
            for finding in (findings.values() if isinstance(findings, dict) else [])
            if isinstance(finding, dict) and isinstance(finding.get("grounding"), list)
            for grounding in finding["grounding"]
            if isinstance(grounding, dict) and isinstance(grounding.get("quote"), str)
        ]
        new_chunks: dict[str, Any] = {}
        for chunk_id, chunk_record in chunks.items():
            content = chunk_record.get("content") if isinstance(chunk_record, dict) else None
            window = None
            if (
                isinstance(chunk_record, dict)
                and isinstance(content, str)
                and "window_start" not in chunk_record
                and len(content) > UNIT_CHAR_BUDGET
            ):
                anchor = _repair_chunk_anchor(
                    content, cited.get(str(chunk_id), []), grounding_quotes
                )
                if anchor is not None:
                    window = oversized_chunk_window(len(content), *anchor)
            if window is None or not isinstance(content, str):
                new_chunks[chunk_id] = chunk_record
                continue
            window_start, window_end = window
            new_chunks[chunk_id] = {
                **chunk_record,
                "content": content[window_start:window_end],
                "window_start": window_start,
                "window_end": window_end,
            }
        windowed.append({**record, "dependencies": {**dependencies, "chunks": new_chunks}})
    return windowed


# The one statement behind ``ChunkRetriever.search`` (task 057 N8, D7). It
# reproduces the in-memory Python retriever it replaced, rule for rule:
#
# - The units searched are the scope's units: the chunks of the frozen
#   text-bearing snapshots this search may read (``:snapshot_ids``, paired with
#   the document each belongs to in ``:tss_ids``), at this embedding profile and
#   unit policy.
# - Vector leg: cosine distance ``<=>``; only units with a positive cosine
#   (distance below 1) count, as the Python leg kept scores above 0.0. A zero
#   query or unit vector makes the distance NaN, which fails ``< 1``, which is
#   the Python rule that scored zero norms 0.0 and so left them out. The leg is
#   cut to its best ``:pool`` units, ties broken on the unit id (a uuid orders
#   like its text form, which the Python tie-break compared).
# - Word leg: the share of the query's distinct words found in the unit's
#   ``tokens`` (D7: the product's own score, not Postgres full-text ranking);
#   ``tokens && query`` keeps units sharing at least one word (served by the GIN
#   index). Cut and tie-break as the vector leg.
# - Reciprocal-rank fusion per unit: the sum of 1 / (:rrf_k + rank) over the legs
#   the unit is in, in double precision, added in the Python order.
# - Best unit per chunk: the highest fused score; on a tie, the unit that ranks
#   higher in the vector leg, then in the word leg (the Python retriever kept the
#   first unit it saw, and it saw the vector leg first, in rank order).
# Every fused chunk comes back (at most two pools' worth); Python applies the
# soft prior, sorts, reranks and cuts.
CHUNK_SEARCH_SQL = """
WITH scope_docs AS (
    SELECT d.snapshot_id, d.tss_id
    FROM unnest(CAST(:snapshot_ids AS uuid[]), CAST(:tss_ids AS uuid[]))
        AS d(snapshot_id, tss_id)
),
scope_units AS NOT MATERIALIZED (
    -- NOT MATERIALIZED on purpose: a MATERIALIZED chunk list was tried on the dev
    -- corpus (2026-11-03) and the planner then scanned the whole chunk_embedding
    -- table instead of probing it by chunk id (about 60 s a query). The planner
    -- repeats the chunk join once per leg this way (about 100 ms each on the dev
    -- corpus), which is the cheaper of the two.
    SELECT e.chunk_embedding_id AS unit_id, e.chunk_id, d.tss_id, e.embedding, e.tokens
    FROM scope_docs d
    JOIN chunk c ON c.source_snapshot_id = d.snapshot_id
    JOIN chunk_embedding e ON e.chunk_id = c.chunk_id
    WHERE e.embedding_profile = :embedding_profile
      AND e.unit_policy = :unit_policy
),
vector_leg AS (
    SELECT unit_id, chunk_id, tss_id,
           row_number() OVER (ORDER BY distance, unit_id) AS leg_rank
    FROM (
        SELECT unit_id, chunk_id, tss_id, distance
        FROM (
            SELECT unit_id, chunk_id, tss_id,
                   embedding <=> CAST(:query_vector AS vector) AS distance
            FROM scope_units
        ) scored
        WHERE distance < 1
        ORDER BY distance, unit_id
        LIMIT :pool
    ) pool
),
word_leg AS (
    SELECT unit_id, chunk_id, tss_id,
           row_number() OVER (ORDER BY score DESC, unit_id) AS leg_rank
    FROM (
        SELECT unit_id, chunk_id, tss_id,
               CAST((SELECT count(*)
                     FROM unnest(CAST(:query_words AS text[])) AS q(word)
                     WHERE q.word = ANY(u.tokens)) AS float8)
                   / :query_word_count AS score
        FROM scope_units u
        WHERE u.tokens && CAST(:query_words AS text[])
        ORDER BY score DESC, unit_id
        LIMIT :pool
    ) pool
),
fused AS (
    SELECT coalesce(v.unit_id, w.unit_id) AS unit_id,
           coalesce(v.chunk_id, w.chunk_id) AS chunk_id,
           coalesce(v.tss_id, w.tss_id) AS tss_id,
           v.leg_rank AS vector_rank,
           w.leg_rank AS word_rank,
           coalesce(CAST(1 AS float8) / (:rrf_k + v.leg_rank), 0)
             + coalesce(CAST(1 AS float8) / (:rrf_k + w.leg_rank), 0) AS fused_score
    FROM vector_leg v
    FULL JOIN word_leg w ON w.unit_id = v.unit_id
),
best AS (
    SELECT DISTINCT ON (chunk_id) chunk_id, unit_id, tss_id, fused_score
    FROM fused
    ORDER BY chunk_id, fused_score DESC, vector_rank ASC NULLS LAST, word_rank ASC
)
SELECT b.chunk_id, b.tss_id, b.fused_score, c.content, c.sequence, e.unit_locator
FROM best b
JOIN chunk c ON c.chunk_id = b.chunk_id
JOIN chunk_embedding e ON e.chunk_embedding_id = b.unit_id
"""


def _unit_offsets(locator: Any, content_length: int) -> tuple[int, int]:
    """Return a unit locator's ``(start, end)``, checked against its chunk.

    Raises:
        ValueError: If the locator is not an object of valid in-chunk offsets.
    """
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
        or end > content_length
    ):
        raise ValueError("chunk embedding unit_locator has invalid offsets")
    return start, end


@dataclass(frozen=True)
class _ChunkScopeFilters:
    """Validated candidate-pool filters for ``search_chunks``."""

    doc_ids: frozenset[str] | None = None
    group_doc_ids: frozenset[str] | None = None
    evidence_types: frozenset[str] | None = None
    tags: frozenset[str] | None = None


class ChunkRetriever:
    """Deterministic staged chunk retriever for one synthesis run or chat turn.

    Each search is one SQL statement (:data:`CHUNK_SEARCH_SQL`) over the scope's
    frozen snapshots; Python embeds the query, turns the filters into the
    documents the search may read, applies the soft prior, sorts, reranks, cuts
    to :data:`SYNTH_CHUNK_TOP_K`, windows oversized chunks and records
    provenance for the chunks it returns.

    Args:
        scope: The frozen retrieval scope (documents, snapshots, connection factory).
        embedder: Injected embedding backend; no network is opened here.
        directive: Parsed synthesis directive with retrieval boosts.
        reranker: Reranker seam applied after fusion and soft priors.
        selection_reference_resolved: Whether a selection run was referenced,
            which switches the screen-confidence factor off.
    """

    def __init__(
        self,
        scope: RetrievalScope,
        *,
        embedder: Any,
        directive: SynthesisDirective,
        reranker: ChunkRerankerBackend,
        selection_reference_resolved: bool = False,
    ) -> None:
        self._scope = scope
        self._embedder = embedder
        self._directive = directive
        self._reranker = reranker
        self._selection_reference_resolved = selection_reference_resolved
        self._query_vectors: dict[str, list[float]] = {}
        self._executed_boosts: dict[str, Any] = {}
        self._unmatched_boosts: dict[str, Any] = {}
        self._soft_prior_factors: dict[str, dict[str, Any]] = {}
        self._has_selected_docs = any(
            bool(doc.get("selected")) for doc in self._scope.docs.values()
        )
        self._refresh_boost_matches()

    def search(
        self, query: str, *, filters: _ChunkScopeFilters | None = None
    ) -> list[ChunkSearchResult]:
        """Search the scope's chunks with hybrid content relevance and soft priors.

        Args:
            query: Content query supplied by the section loop.
            filters: Optional validated scope filters applied before ranking.

        Returns:
            Ranked chunk records capped to :data:`SYNTH_CHUNK_TOP_K`.

        Raises:
            ValueError: If a matched unit's stored offsets are malformed.
        """
        query_vector = self._query_vector(query)
        query_words = sorted(_tokens(query))
        snapshot_ids, tss_ids = self._searchable_snapshots(filters)
        rows: list[Any] = []
        if snapshot_ids:
            with self._scope.connect() as conn:
                rows = list(
                    conn.execute(
                        sa_text(CHUNK_SEARCH_SQL),
                        {
                            "snapshot_ids": snapshot_ids,
                            "tss_ids": tss_ids,
                            "embedding_profile": EMBEDDING_PROFILE,
                            "unit_policy": UNIT_POLICY,
                            "query_vector": vector_literal(query_vector),
                            "query_words": query_words,
                            "query_word_count": max(1, len(query_words)),
                            "pool": CANDIDATE_POOL_PER_LEG,
                            "rrf_k": RRF_K,
                        },
                    )
                )

        candidates: list[ChunkSearchResult] = []
        factors_by_chunk: dict[str, dict[str, Any]] = {}
        for row in rows:
            chunk_id = str(row.chunk_id)
            tss_id = str(row.tss_id)
            prior, factors = self._soft_prior(tss_id)
            factors_by_chunk[chunk_id] = factors
            candidates.append(
                self._result_for_row(row, chunk_id, tss_id, float(row.fused_score) * prior)
            )
        ordered = sorted(
            candidates,
            key=lambda candidate: (-candidate["fused_score"], candidate["chunk_record_id"]),
        )
        reranked = self._reranker.rerank(query=query, candidates=ordered)
        allowed_ids = {candidate["chunk_record_id"] for candidate in ordered}
        sanitized = [
            candidate for candidate in reranked if candidate["chunk_record_id"] in allowed_ids
        ]
        returned = sanitized[:SYNTH_CHUNK_TOP_K]
        # Provenance records the prior factors of the returned chunks only
        # (owner, 2026-11-03).
        for candidate in returned:
            chunk_id = candidate["chunk_record_id"]
            self._soft_prior_factors[chunk_id] = factors_by_chunk[chunk_id]
        return returned

    def provenance(self) -> dict[str, Any]:
        """Return retrieval provenance for roll-up recording."""
        return {
            "reranker": self._reranker.mode,
            "selection_prior": SELECTION_PRIOR_BOOST if self._has_selected_docs else None,
            "executed_boosts": _sorted_json(self._executed_boosts),
            "unmatched_boosts": _sorted_json(self._unmatched_boosts),
            "soft_prior_factors": _sorted_json(self._soft_prior_factors),
            "confidence_suppressed": self._selection_reference_resolved,
            "doc_count": len(self._scope.docs),
            "unit_count": self._scope.unit_count,
        }

    def warm_queries(self, queries: Sequence[str]) -> None:
        """Batch-embed any of ``queries`` not yet cached, in one backend call.

        A read turn can carry several ``search_chunks`` calls with distinct
        queries; embedding each lazily inside :meth:`search` costs one
        backend round-trip per query. This embeds the turn's new, uncached
        queries together (022 rider 16) — per-query caching and retrieval
        determinism are unchanged: a query already cached, or embedded here,
        is never re-embedded, and :meth:`search` still resolves every query
        to the same vector regardless of whether it was warmed.

        Args:
            queries: Candidate query strings gathered from one turn's
                ``search_chunks`` calls. Duplicates and already-cached
                queries are skipped before the backend call.
        """
        uncached: list[str] = []
        seen: set[str] = set()
        for query in queries:
            if query in self._query_vectors or query in seen:
                continue
            seen.add(query)
            uncached.append(query)
        if not uncached:
            return
        vectors = embed_with_retry(self._embedder, uncached, kind="query")
        if len(vectors) != len(uncached):
            raise RuntimeError("embedding backend returned wrong query vector count")
        for query, vector in zip(uncached, vectors, strict=True):
            self._query_vectors[query] = validate_vector(vector)

    def _query_vector(self, query: str) -> list[float]:
        vector = self._query_vectors.get(query)
        if vector is None:
            vectors = embed_with_retry(self._embedder, [query], kind="query")
            if len(vectors) != 1:
                raise RuntimeError("embedding backend returned wrong query vector count")
            vector = validate_vector(vectors[0])
            self._query_vectors[query] = vector
        return vector

    def _searchable_snapshots(
        self, filters: _ChunkScopeFilters | None
    ) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
        """Return the snapshots this search may read, each with its document.

        A snapshot shared by two documents of the scope is searched once, under
        one of the documents the filters allow, chosen by its priors: a selected
        document before an unselected one, then an appraised one (an appraisal
        tier or quality score) before one without, then the smaller id.
        """

        # task 057 review: Codex 4 - the document that carries the boosts and the
        # citation identity is chosen by priors, not by whichever id sorts first.
        def priority(tss_id: str) -> tuple[bool, bool, str]:
            doc = self._scope.docs[tss_id]
            appraised = (
                doc.get("appraisal_tier") is not None or doc.get("quality_score") is not None
            )
            return (not doc.get("selected"), not appraised, tss_id)

        tss_by_snapshot: dict[uuid.UUID, str] = {}
        for tss_id in sorted(self._scope.docs, key=priority):
            if self._doc_matches_filters(tss_id, filters):
                tss_by_snapshot.setdefault(self._scope.snapshot_by_tss[tss_id], tss_id)
        snapshot_ids = sorted(tss_by_snapshot)
        return snapshot_ids, [uuid.UUID(tss_by_snapshot[s]) for s in snapshot_ids]

    def _doc_matches_filters(
        self, tss_id: str, filters: _ChunkScopeFilters | None
    ) -> bool:
        if filters is None:
            return True
        doc = self._scope.docs[tss_id]
        if filters.doc_ids is not None and tss_id not in filters.doc_ids:
            return False
        if filters.group_doc_ids is not None and tss_id not in filters.group_doc_ids:
            return False
        evidence_type = doc.get("primary_evidence_type")
        if (
            filters.evidence_types is not None
            and str(evidence_type) not in filters.evidence_types
        ):
            return False
        if filters.tags is not None:
            doc_tags = set(cast("list[str]", doc.get("tags", [])))
            if not doc_tags.intersection(filters.tags):
                return False
        return True

    def _result_for_row(
        self, row: Any, chunk_id: str, tss_id: str, score: float
    ) -> ChunkSearchResult:
        doc = self._scope.docs[tss_id]
        frozen_content = cast("str", row.content)
        content = frozen_content
        window_start: int | None = None
        window_end: int | None = None
        if len(frozen_content) > UNIT_CHAR_BUDGET:
            unit_start, unit_end = _unit_offsets(row.unit_locator, len(frozen_content))
            window = oversized_chunk_window(len(frozen_content), unit_start, unit_end)
            if window is not None:
                window_start, window_end = window
                content = frozen_content[window_start:window_end]
        result: ChunkSearchResult = {
            "chunk_record_id": chunk_id,
            "tss_id": tss_id,
            "document_title": cast("str", doc["title"]),
            "sequence": cast("int", row.sequence),
            "content": content,
            "text_basis": self._scope.chunk_text_basis_by_tss[tss_id],
            "origin": "selected" if doc.get("selected") else "unselected_screened",
            "appraised": doc.get("appraisal_tier") is not None,
            "fused_score": score,
        }
        if window_start is not None and window_end is not None:
            result["window_start"] = window_start
            result["window_end"] = window_end
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

    def _soft_prior(self, tss_id: str) -> tuple[float, dict[str, Any]]:
        """Return a document's clamped prior multiplier and its recorded factors."""
        doc = self._scope.docs[tss_id]
        selection_factor = (
            SELECTION_PRIOR_BOOST if self._has_selected_docs and doc.get("selected") else 1.0
        )
        multiplier = selection_factor
        column_factors: dict[str, dict[str, float]] = {}
        for column, values in self._directive.column_boosts.items():
            raw_value = doc.get(column)
            if raw_value is not None and str(raw_value) in values:
                factor = values[str(raw_value)]
                column_factors[column] = {str(raw_value): factor}
                multiplier *= factor
        tag_factors: dict[str, float] = {}
        for tag in cast("list[str]", doc.get("tags", [])):
            if tag in self._directive.tag_boosts:
                factor = self._directive.tag_boosts[tag]
                tag_factors[tag] = factor
                multiplier *= factor
        tier = doc.get("appraisal_tier")
        appraisal_factor = 1.0
        if tier is not None and str(tier) in self._directive.appraisal_tier_boosts:
            appraisal_factor = self._directive.appraisal_tier_boosts[str(tier)]
            multiplier *= appraisal_factor
        confidence_factor = 1.0
        if not self._selection_reference_resolved:
            confidence = doc.get("screen_confidence")
            if (
                not isinstance(confidence, bool)
                and isinstance(confidence, int | float)
                and math.isfinite(float(confidence))
            ):
                bounds = self._directive.screen_confidence
                confidence_factor = bounds.lo + float(confidence) * (bounds.hi - bounds.lo)
                multiplier *= confidence_factor
        raw_multiplier = multiplier
        executed_multiplier = min(
            BOOST_CLAMP_MAX, max(BOOST_CLAMP_MIN, raw_multiplier)
        )
        return executed_multiplier, {
            "selection": selection_factor,
            "columns": column_factors,
            "tags": tag_factors,
            "appraisal_tier": appraisal_factor,
            "screen_confidence": confidence_factor,
            "confidence_suppressed": self._selection_reference_resolved,
            "raw_multiplier": raw_multiplier,
            "executed_multiplier": executed_multiplier,
        }

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
    group_doc_ids_by_group_id: Mapping[str, set[str]] | None = None,
    char_budget: int = SYNTH_CHUNK_CHAR_BUDGET,
) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    """Build substrate-available read-only section tools.

    Args:
        retriever: Chunk retriever, or ``None`` when chunk claims are unavailable.
        findings_reader: Findings reader, or ``None`` without extraction.
        lookup_reader: Universal lookup reader.
        group_doc_ids_by_group_id: Optional grouping id to document-id map for
            ``search_chunks`` group filters.
        char_budget: Per-section cumulative chunk text budget.

    Returns:
        Mapping from tool name to validated callable.
    """
    if char_budget < 0:
        raise ValueError("char_budget must be non-negative")
    tools: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}
    used_chars = 0
    returned_chunk_ids: set[str] = set()
    returned_finding_ids: set[str] = set()
    returned_lookup_ids: set[str] = set()

    if retriever is not None:

        def search_chunks(arguments: dict[str, Any]) -> dict[str, Any]:
            nonlocal used_chars
            _validate_tool_keys(
                arguments,
                allowed={"query", "doc_ids", "group_ids", "evidence_types", "tags"},
            )
            query = _tool_string(
                arguments, field="query", max_length=SEARCH_QUERY_MAX_LENGTH, required=True
            )
            assert query is not None
            filters = _search_scope_filters(
                arguments,
                retriever=retriever,
                group_doc_ids_by_group_id=group_doc_ids_by_group_id,
            )
            chunks = retriever.search(query, filters=filters)
            remaining = char_budget - used_chars
            kept: list[dict[str, Any]] = []
            truncated = False
            for chunk in chunks:
                chunk_id = chunk["chunk_record_id"]
                if chunk_id in returned_chunk_ids:
                    kept.append(
                        _already_returned_reference(
                            id_key="chunk_record_id", record_id=chunk_id, record=chunk
                        )
                    )
                    continue
                content_len = len(chunk["content"])
                if content_len > remaining:
                    # Honest per-item skip: without a marker the dropped chunk is
                    # indistinguishable from "never retrieved" (the dedup path
                    # leaves an already_returned stub; this is its budget sibling).
                    truncated = True
                    kept.append(
                        {
                            "id": chunk_id,
                            "chunk_record_id": chunk_id,
                            "skipped_over_budget": True,
                        }
                    )
                    continue
                kept.append(dict(chunk))
                returned_chunk_ids.add(chunk_id)
                used_chars += content_len
                remaining -= content_len
            if len(kept) < len(chunks):
                truncated = True
            return {"chunks": kept, "truncated": truncated}

        tools["search_chunks"] = search_chunks

    if findings_reader is not None:

        def query_findings(arguments: dict[str, Any]) -> dict[str, Any]:
            _validate_findings_tool_arguments(arguments)
            result = findings_reader(arguments)
            deduped = dict(result)
            for key in ("findings", "iof_findings", "icf_findings"):
                records = deduped.get(key)
                if isinstance(records, list):
                    deduped[key] = _deduplicate_records(
                        records,
                        returned_ids=returned_finding_ids,
                        id_keys=("finding_id", "id"),
                    )
            return deduped

        tools["query_findings"] = query_findings

    def lookup(arguments: dict[str, Any]) -> dict[str, Any]:
        _validate_lookup_tool_arguments(arguments)
        return _deduplicate_lookup_result(
            lookup_reader(arguments),
            arguments=arguments,
            returned_lookup_ids=returned_lookup_ids,
        )

    tools["lookup"] = lookup
    return tools


def _load_extraction_docs(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    extraction_run_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
) -> tuple[list[dict[str, Any]], set[str]]:
    row = conn.execute(
        sa_select(extraction_result.c.docs, extraction_result.c.extraction_provenance)
        .where(extraction_result.c.task_id == task_id)
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
    tss_id = cast("uuid.UUID", row.task_source_snapshot_id)
    record: FindingRecord = {
        "kind": "iof",
        "finding_id": str(row.finding_id),
        "extraction_record_id": str(row.extraction_record_id),
        "tss_id": str(tss_id),
        "document_title": _metadata_title(metadata, tss_id),
        "intervention": cast("str", row.intervention),
        "outcome": cast("str", row.outcome),
        "unit": cast("str | None", row.unit),
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
    label = appraisal_tier(
        getattr(row, "quality_score", None), unrated=bool(getattr(row, "unrated", False))
    )
    if label is not None:
        record["appraisal_label"] = label
    venue = _metadata_venue(metadata)
    if venue is not None:
        record["venue"] = venue
    cited_by = _metadata_cited_by(metadata)
    if cited_by is not None:
        record["cited_by"] = cited_by
    return record


def _icf_finding_record(row: Any) -> ICFFindingRecord:
    metadata = row.metadata if isinstance(row.metadata, dict) else {}
    tss_id = cast("uuid.UUID", row.task_source_snapshot_id)
    record: ICFFindingRecord = {
        "kind": "icf",
        "finding_id": str(row.finding_id),
        "extraction_record_id": str(row.extraction_record_id),
        "tss_id": str(tss_id),
        "document_title": _metadata_title(metadata, tss_id),
        "context_type": cast("str", row.context_type),
        "claim": cast("str", row.claim),
        "intervention": cast("str", row.intervention),
        "outcome": cast("str | None", row.outcome),
        "unit": cast("str | None", row.unit),
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
    label = appraisal_tier(
        getattr(row, "quality_score", None), unrated=bool(getattr(row, "unrated", False))
    )
    if label is not None:
        record["appraisal_label"] = label
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
    task_id: uuid.UUID,
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
            intervention_outcome_finding.c.unit,
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
            source_extraction_record.c.task_source_snapshot_id,
            source_snapshot.c.metadata,
            source_classification_result.c.primary_evidence_type,
            source_appraisal_result.c.quality_score,
            source_appraisal_result.c.unrated,
        )
        .select_from(intervention_outcome_finding)
        .join(
            source_extraction_record,
            (
                source_extraction_record.c.extraction_record_id
                == intervention_outcome_finding.c.extraction_record_id
            )
            & (source_extraction_record.c.task_id == task_id),
        )
        .join(
            task_source_snapshot,
            (
                task_source_snapshot.c.task_source_snapshot_id
                == source_extraction_record.c.task_source_snapshot_id
            )
            & (task_source_snapshot.c.task_id == task_id),
        )
        .join(
            source_snapshot,
            source_snapshot.c.source_snapshot_id == task_source_snapshot.c.source_snapshot_id,
        )
        .outerjoin(
            source_classification_result,
            (
                source_classification_result.c.task_source_snapshot_id
                == task_source_snapshot.c.task_source_snapshot_id
            )
            & (source_classification_result.c.task_id == task_id)
            & (source_classification_result.c.evidence_scope_id == evidence_scope_id),
        )
        .outerjoin(
            source_appraisal_result,
            (
                source_appraisal_result.c.task_source_snapshot_id
                == task_source_snapshot.c.task_source_snapshot_id
            )
            & (source_appraisal_result.c.task_id == task_id)
            & (source_appraisal_result.c.evidence_scope_id == evidence_scope_id),
        )
        .where(intervention_outcome_finding.c.task_id == task_id)
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
    task_id: uuid.UUID,
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
            implementation_context_finding.c.unit,
            implementation_context_finding.c.setting,
            implementation_context_finding.c.study_geography,
            implementation_context_finding.c.study_design,
            implementation_context_finding.c.claim_level,
            implementation_context_finding.c.claim_basis,
            implementation_context_finding.c.level,
            implementation_context_finding.c.resource_requirements,
            implementation_context_finding.c.workforce_requirements,
            implementation_context_finding.c.field_coverage,
            source_extraction_record.c.task_source_snapshot_id,
            source_snapshot.c.metadata,
            source_classification_result.c.primary_evidence_type,
            source_appraisal_result.c.quality_score,
            source_appraisal_result.c.unrated,
        )
        .select_from(implementation_context_finding)
        .join(
            source_extraction_record,
            (
                source_extraction_record.c.extraction_record_id
                == implementation_context_finding.c.extraction_record_id
            )
            & (source_extraction_record.c.task_id == task_id),
        )
        .join(
            task_source_snapshot,
            (
                task_source_snapshot.c.task_source_snapshot_id
                == source_extraction_record.c.task_source_snapshot_id
            )
            & (task_source_snapshot.c.task_id == task_id),
        )
        .join(
            source_snapshot,
            source_snapshot.c.source_snapshot_id == task_source_snapshot.c.source_snapshot_id,
        )
        .outerjoin(
            source_classification_result,
            (
                source_classification_result.c.task_source_snapshot_id
                == task_source_snapshot.c.task_source_snapshot_id
            )
            & (source_classification_result.c.task_id == task_id)
            & (source_classification_result.c.evidence_scope_id == evidence_scope_id),
        )
        .outerjoin(
            source_appraisal_result,
            (
                source_appraisal_result.c.task_source_snapshot_id
                == task_source_snapshot.c.task_source_snapshot_id
            )
            & (source_appraisal_result.c.task_id == task_id)
            & (source_appraisal_result.c.evidence_scope_id == evidence_scope_id),
        )
        .where(implementation_context_finding.c.task_id == task_id)
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


def priority_counts_by_group(
    grouping_groups: list[dict[str, Any]] | None,
    relevance_annotations: Mapping[str, str] | None,
) -> dict[str, dict[str, int]]:
    """Per-group priority/normal/total member counts for the P4 proposal render.

    Pure (no DB, no I/O): the P4 steering bundle shows, per group, how many of
    its member findings the B2′ annotator marked ``priority`` — so the user
    sees where their stated emphasis landed before steering the synthesis shape.

    Args:
        grouping_groups: Flat group records (each carrying ``group_id`` and
            ``member_finding_ids``), or ``None``. The same shape
            ``_group_member_ids`` consumes.
        relevance_annotations: This run's marks (``finding_id`` → "priority" |
            "normal"), or ``None`` when the run carries no annotations.

    Returns:
        ``{group_id: {"priority": n, "normal": m, "total": t}}`` for each group
        with a qualified id. Members absent from the annotations map count into
        ``total`` only. An empty/``None`` annotations map yields all-zero
        priority/normal counts (never fabricated marks).
    """
    annotations = relevance_annotations or {}
    counts: dict[str, dict[str, int]] = {}
    for group in grouping_groups or []:
        group_id = group.get("group_id")
        if not isinstance(group_id, str) or not is_qualified_group_id(group_id):
            continue
        members = group.get("member_finding_ids") or group.get("finding_ids") or []
        member_ids = [member for member in members if isinstance(member, str)]
        priority = sum(1 for member in member_ids if annotations.get(member) == "priority")
        normal = sum(1 for member in member_ids if annotations.get(member) == "normal")
        counts[group_id] = {
            "priority": priority,
            "normal": normal,
            "total": len(member_ids),
        }
    return counts


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


def _record_identifier(
    record: Mapping[str, Any], id_keys: Sequence[str]
) -> tuple[str, str] | None:
    for key in id_keys:
        value = record.get(key)
        if isinstance(value, str) and value:
            return key, value
    return None


def _already_returned_reference(
    *, id_key: str, record_id: str, record: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    reference = {"id": record_id, id_key: record_id, "already_returned": True}
    if record is not None and isinstance(record.get("kind"), str):
        reference["kind"] = record["kind"]
    return reference


def _deduplicate_records(
    records: list[Any],
    *,
    returned_ids: set[str],
    id_keys: Sequence[str],
    namespace: str = "",
) -> list[Any]:
    deduped: list[Any] = []
    for record in records:
        if not isinstance(record, dict):
            deduped.append(record)
            continue
        identity = _record_identifier(record, id_keys)
        if identity is None:
            deduped.append(dict(record))
            continue
        id_key, record_id = identity
        member_key = f"{namespace}{record_id}"
        if member_key in returned_ids:
            deduped.append(
                _already_returned_reference(
                    id_key=id_key, record_id=record_id, record=record
                )
            )
            continue
        returned_ids.add(member_key)
        deduped.append(dict(record))
    return deduped


def _lookup_call_id(arguments: Mapping[str, Any]) -> str:
    canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    return f"lookup:{digest}"


def _deduplicate_lookup_result(
    result: dict[str, Any],
    *,
    arguments: Mapping[str, Any],
    returned_lookup_ids: set[str],
) -> dict[str, Any]:
    lookup_id = _lookup_call_id(arguments)
    if lookup_id in returned_lookup_ids:
        kind = result.get("kind") if isinstance(result.get("kind"), str) else None
        reference = _already_returned_reference(
            id_key="lookup_id", record_id=lookup_id
        )
        if kind is not None:
            reference["kind"] = kind
        return reference
    returned_lookup_ids.add(lookup_id)

    deduped = dict(result)
    payload = deduped.get("result")
    lookup_record_ids = returned_lookup_ids
    if isinstance(payload, list):
        deduped["result"] = _deduplicate_records(
            payload,
            returned_ids=lookup_record_ids,
            # Record ids share the set with lookup:<hash> call keys — namespace
            # them so a record id can never collide with another id space.
            namespace="lookup_record:",
            id_keys=("search_coverage_record_id", "group_id", "theme_id", "tss_id", "id"),
        )
    elif isinstance(payload, dict):
        nested = dict(payload)
        for key, value in payload.items():
            if isinstance(value, list):
                nested[key] = _deduplicate_records(
                    value,
                    returned_ids=lookup_record_ids,
                    id_keys=(
                        "search_coverage_record_id",
                        "group_id",
                        "theme_id",
                        "tss_id",
                        "id",
                    ),
                )
        deduped["result"] = nested
    return deduped


def make_findings_reader(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    extraction_run_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    grouping_groups: list[dict[str, Any]] | None,
    relevance_annotations: Mapping[str, str] | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Create a scoped extraction finding reader.

    Args:
        conn: Open database connection.
        task_id: Task id scoping all reads.
        extraction_run_id: Referenced extraction run id.
        evidence_scope_id: Evidence scope id.
        grouping_groups: Optional grouping records for group-id filtering.
        relevance_annotations: B2′ run-scoped marks (``finding_id`` → "priority"
            | "normal") from this run's extraction result, or ``None``. When
            present, each returned ``query_findings`` record gains a
            ``"relevance"`` key for its finding id; findings not in the map (and
            the ``None`` case) carry no ``"relevance"`` key — never fabricated.

    Returns:
        A validated ``query_findings`` implementation.
    """
    extraction_docs, available_profiles = _load_extraction_docs(
        conn,
        task_id=task_id,
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
            task_id=task_id,
            evidence_scope_id=evidence_scope_id,
            extraction_record_ids=ids_by_profile.get(IOF_PROFILE_ID, []),
        )
        if IOF_PROFILE_ID in available_profiles
        else []
    )
    icf_findings = (
        _load_icf_finding_records(
            conn,
            task_id=task_id,
            evidence_scope_id=evidence_scope_id,
            extraction_record_ids=ids_by_profile.get(ICF_PROFILE_ID, []),
        )
        if ICF_PROFILE_ID in available_profiles
        else []
    )
    annotations = relevance_annotations or {}

    def _marked(finding: Mapping[str, Any]) -> dict[str, Any]:
        record = dict(finding)
        mark = annotations.get(str(record.get("finding_id")))
        if mark is not None:
            record["relevance"] = mark
        return record

    findings_by_kind: dict[str, list[dict[str, Any]]] = {
        "iof": [_marked(finding) for finding in iof_findings],
        "icf": [_marked(finding) for finding in icf_findings],
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
            truncated = len(selected) > LOOKUP_ROW_CAP
            result[result_key] = selected[:LOOKUP_ROW_CAP]
            result[f"{kind}_truncated"] = truncated
        return result

    return reader


def _ensure_kind(arguments: dict[str, Any]) -> str:
    kind = _tool_string(arguments, field="kind", max_length=100, required=True)
    assert kind is not None
    if kind not in LOOKUP_QUERY_KINDS:
        _tool_fail("unknown lookup kind")
    return kind


def _screened_in_doc_ids(
    task_id: uuid.UUID,
    scope_ids: Sequence[uuid.UUID],
    *,
    screened_by_run_ids: set[uuid.UUID] | None = None,
) -> Any:
    """Select of these scopes' screened-in doc ids — the lookup read boundary.

    Effective-relevant via the helper (never a raw status='relevant' join),
    per the same screened-in-scope rule as ``_load_retrieval_scope``.
    """
    effective = effective_screen_rows(run_ids=screened_by_run_ids)
    query = (
        sa_select(effective.c.task_source_snapshot_id)
        .where(effective.c.task_id == task_id)
        .where(effective.c.evidence_scope_id.in_(list(scope_ids)))
        .where(effective.c.status == "relevant")
    )
    return query


def _scope_precedence(
    scope_column: ColumnElement[uuid.UUID], scope_id: uuid.UUID
) -> ColumnElement[int]:
    """Order the primary scope's row first (task 045, P13)."""
    return case((scope_column == scope_id, 0), else_=1)


def _doc_id_for_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    scope_ids: Sequence[uuid.UUID],
    arguments: dict[str, Any],
    screened_by_run_ids: set[uuid.UUID] | None = None,
) -> uuid.UUID:
    raw_doc_id = _tool_string(arguments, field="doc_id", max_length=100, required=True)
    assert raw_doc_id is not None
    doc_id = _parse_uuid(raw_doc_id, field="doc_id")
    exists = conn.execute(
        sa_select(task_source_snapshot.c.task_source_snapshot_id)
        .where(task_source_snapshot.c.task_id == task_id)
        .where(task_source_snapshot.c.task_source_snapshot_id == doc_id)
        .where(
            task_source_snapshot.c.task_source_snapshot_id.in_(
                _screened_in_doc_ids(
                    task_id, scope_ids, screened_by_run_ids=screened_by_run_ids
                )
            )
        )
    ).first()
    if exists is None:
        _tool_fail("doc_id is unknown")
    return doc_id


def _doc_id_for_task(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    arguments: dict[str, Any],
) -> uuid.UUID:
    """Validate a ``doc_id`` argument scoped to the task only.

    Unlike :func:`_doc_id_for_scope`, this does not require the document to be
    screened-in for the scope: ``screening_by_doc`` reads screening rows
    themselves, so a not_relevant / excluded_retracted / failed doc must
    resolve too — that is the read the widening exists for (022 rider 16).

    Args:
        conn: Open database connection.
        task_id: Task id scoping the read.
        arguments: Raw tool arguments carrying ``doc_id``.

    Returns:
        The validated document id.
    """
    raw_doc_id = _tool_string(arguments, field="doc_id", max_length=100, required=True)
    assert raw_doc_id is not None
    doc_id = _parse_uuid(raw_doc_id, field="doc_id")
    exists = conn.execute(
        sa_select(task_source_snapshot.c.task_source_snapshot_id)
        .where(task_source_snapshot.c.task_id == task_id)
        .where(task_source_snapshot.c.task_source_snapshot_id == doc_id)
    ).first()
    if exists is None:
        _tool_fail("doc_id is unknown")
    return doc_id


def _absent() -> dict[str, bool]:
    return {"absent": True}


def _snapshot_run_filter(
    run_id_column: ColumnElement[uuid.UUID], snapshot_run_ids: set[uuid.UUID] | None
) -> ColumnElement[bool]:
    """Return the optional turn-start run-snapshot predicate."""
    if snapshot_run_ids is None:
        return true()
    return run_id_column.in_(snapshot_run_ids)


def _selection_summary(row: Any) -> dict[str, Any]:
    selected = row.selected if isinstance(row.selected, list) else []
    bounded_selected: list[dict[str, Any]] = []
    for item in selected[:LOOKUP_ROW_CAP]:
        if isinstance(item, dict):
            bounded_selected.append({
                "tss_id": item.get("tss_id"),
                "reason": item.get("reason"),
                "stratum": item.get("stratum"),
            })
    return {
        "strategy": row.strategy,
        "budget": row.budget,
        "excluded": row.excluded,
        "flags": row.flags,
        "selected": bounded_selected,
        "selected_truncated": len(selected) > LOOKUP_ROW_CAP,
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
            if facet_of_group_id(group_id) != facet:
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


#: Lookup kinds that need a referenced upstream run; the reader below fails
#: them (``"<kind> requires <stage>"``) when that run id is absent. Every
#: other kind is always servable (it may return an empty or absent record).
LOOKUP_KIND_REQUIRED_RUN: dict[str, str] = {
    "selection_rationale": "selection",
    "characterisation_summary": "characterisation",
    "grouping_groups": "grouping",
}


def available_lookup_kinds(
    *,
    characterisation_run_id: uuid.UUID | None,
    selection_run_id: uuid.UUID | None,
    grouping_run_id: uuid.UUID | None,
) -> list[str]:
    """Return the lookup kinds a run can serve, in :data:`LOOKUP_QUERY_KINDS` order.

    The same facts :func:`make_lookup_reader` checks before it reads: a kind in
    :data:`LOOKUP_KIND_REQUIRED_RUN` is servable only when its upstream run id
    is referenced. The section writer's ``lookup`` tool then offers only these
    kinds (task 056 X3), so the model never spends a turn on a kind that can
    only fail.

    Args:
        characterisation_run_id: The referenced characterisation run, if any.
        selection_run_id: The referenced selection run, if any.
        grouping_run_id: The referenced grouping run, if any.

    Returns:
        The servable kinds.
    """
    present = {
        "characterisation": characterisation_run_id is not None,
        "selection": selection_run_id is not None,
        "grouping": grouping_run_id is not None,
    }
    return [
        kind
        for kind in LOOKUP_QUERY_KINDS
        if kind not in LOOKUP_KIND_REQUIRED_RUN or present[LOOKUP_KIND_REQUIRED_RUN[kind]]
    ]


def make_lookup_reader(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
    characterisation_run_id: uuid.UUID | None,
    selection_run_id: uuid.UUID | None,
    extraction_run_id: uuid.UUID | None,
    grouping_run_id: uuid.UUID | None,
    snapshot_run_ids: set[uuid.UUID] | None = None,
    extra_scope_ids: Sequence[uuid.UUID] = (),
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Create the universal closed-vocabulary lookup reader.

    With ``extra_scope_ids`` (task 045, S11) the per-document and scope-wide
    reads span every scope, a per-document label reading the primary scope's
    row first and then the latest (the retrieval precedence rule, P13); the
    selection, characterisation and grouping reads stay the primary scope's,
    since their run ids are the primary walk's.

    Args:
        conn: Open database connection.
        task_id: Task id scoping all reads.
        scope_id: Evidence scope id (the primary scope).
        characterisation_run_id: Optional referenced characterisation run.
        selection_run_id: Optional referenced selection run.
        extraction_run_id: Optional referenced extraction run.
        grouping_run_id: Optional referenced grouping run.
        snapshot_run_ids: Optional terminal-walk run ids bounding otherwise
            scope-wide records to the turn-start snapshot. ``None`` preserves
            synthesis's historic whole-scope reads.
        extra_scope_ids: Further evidence scopes the reads span.

    Returns:
        A validated ``lookup`` implementation.
    """
    scope_ids = [scope_id, *(s for s in extra_scope_ids if s != scope_id)]

    def reader(arguments: dict[str, Any]) -> dict[str, Any]:
        kind = _ensure_kind(arguments)
        if kind in {"appraisal_by_doc", "classification_by_doc", "tags_by_doc"}:
            doc_id = _doc_id_for_scope(
                conn,
                task_id=task_id,
                scope_ids=scope_ids,
                arguments=arguments,
                screened_by_run_ids=snapshot_run_ids,
            )
            result: Any
            if kind == "appraisal_by_doc":
                row = conn.execute(
                    sa_select(
                        source_appraisal_result.c.quality_score,
                        source_appraisal_result.c.rubric_version,
                        source_appraisal_result.c.unrated,
                    )
                    .where(source_appraisal_result.c.task_id == task_id)
                    .where(source_appraisal_result.c.evidence_scope_id.in_(scope_ids))
                    .where(source_appraisal_result.c.task_source_snapshot_id == doc_id)
                    .where(_snapshot_run_filter(
                        source_appraisal_result.c.appraised_by_run_id, snapshot_run_ids
                    ))
                    .order_by(
                        _scope_precedence(source_appraisal_result.c.evidence_scope_id, scope_id),
                        source_appraisal_result.c.appraised_at.desc(),
                    )
                ).first()
                result = (
                    _absent()
                    if row is None
                    else {
                        "quality_score": row.quality_score,
                        "rubric_version": row.rubric_version,
                    }
                )
                if row is not None and row.unrated:
                    # Only on an Unrated row (no score, task 056), so a scored
                    # row's result is unchanged.
                    result["unrated"] = True
            elif kind == "classification_by_doc":
                row = conn.execute(
                    sa_select(source_classification_result.c.primary_evidence_type)
                    .where(source_classification_result.c.task_id == task_id)
                    .where(source_classification_result.c.evidence_scope_id.in_(scope_ids))
                    .where(source_classification_result.c.task_source_snapshot_id == doc_id)
                    .where(_snapshot_run_filter(
                        source_classification_result.c.classified_by_run_id, snapshot_run_ids
                    ))
                    .order_by(
                        _scope_precedence(
                            source_classification_result.c.evidence_scope_id, scope_id
                        ),
                        source_classification_result.c.classified_at.desc(),
                    )
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
                    .where(source_tag.c.task_id == task_id)
                    .where(source_tag.c.task_source_snapshot_id == doc_id)
                    .where(_snapshot_run_filter(source_tag.c.created_by_run_id, snapshot_run_ids))
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

        if kind == "screening_by_doc":
            doc_id = _doc_id_for_task(conn, task_id=task_id, arguments=arguments)
            rows = conn.execute(
                sa_select(
                    source_screening_result.c.screen_stage,
                    source_screening_result.c.status,
                    source_screening_result.c.screen_basis,
                    source_screening_result.c.screen_decision_confidence,
                )
                .where(source_screening_result.c.task_id == task_id)
                .where(source_screening_result.c.evidence_scope_id.in_(scope_ids))
                .where(source_screening_result.c.task_source_snapshot_id == doc_id)
                .where(_snapshot_run_filter(
                    source_screening_result.c.screened_by_run_id, snapshot_run_ids
                ))
                # Failed attempts are retry history, never a decision — the
                # partial unique index (uq_ssr_scope_source_stage) guarantees
                # at most one non-failed row per stage, so this is honestly
                # every decided stage for the doc, never a filtered subset of
                # decisions (only attempt noise is excluded).
                .where(source_screening_result.c.status != "failed")
                .order_by(
                    _scope_precedence(source_screening_result.c.evidence_scope_id, scope_id),
                    source_screening_result.c.evidence_scope_id,
                    source_screening_result.c.screen_stage,
                )
            ).fetchall()
            return {
                "kind": kind,
                "result": [
                    {
                        "screen_stage": row.screen_stage,
                        "status": row.status,
                        "screen_basis": row.screen_basis,
                        "screen_decision_confidence": row.screen_decision_confidence,
                    }
                    for row in rows
                ],
            }

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
                .where(selection_result.c.task_id == task_id)
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
                .where(search_coverage_record.c.task_id == task_id)
                .where(search_coverage_record.c.evidence_scope_id.in_(scope_ids))
                .where(_snapshot_run_filter(
                    search_coverage_record.c.acquired_by_run_id, snapshot_run_ids
                ))
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
                .where(characterisation_result.c.task_id == task_id)
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
                .where(grouping_result.c.task_id == task_id)
                .where(grouping_result.c.evidence_scope_id == scope_id)
                .where(grouping_result.c.run_id == grouping_run_id)
            ).first()
            result = _absent() if row is None else _grouping_summary(row.groups)
            return {"kind": kind, "result": result}

        if kind == "docs_by_tag":
            tag = _tool_string(arguments, field="tag", max_length=200, required=True)
            assert tag is not None
            rows = conn.execute(
                sa_select(source_tag.c.task_source_snapshot_id)
                .where(source_tag.c.task_id == task_id)
                .where(source_tag.c.tag == tag)
                .where(_snapshot_run_filter(source_tag.c.created_by_run_id, snapshot_run_ids))
                .where(
                    source_tag.c.task_source_snapshot_id.in_(
                        _screened_in_doc_ids(
                            task_id,
                            scope_ids,
                            screened_by_run_ids=snapshot_run_ids,
                        )
                    )
                )
                .order_by(source_tag.c.task_source_snapshot_id)
            ).fetchall()
            return {
                "kind": kind,
                "result": sorted({str(row.task_source_snapshot_id) for row in rows}),
            }

        if kind == "tag_aggregate":
            by = _tool_string(arguments, field="by", max_length=20, required=True)
            if by not in {"type", "asserter"}:
                _tool_fail("by must be type or asserter")
            column = source_tag.c.tag_type if by == "type" else source_tag.c.asserted_by
            rows = conn.execute(
                sa_select(column.label("value"), func.count().label("tag_count"))
                .where(source_tag.c.task_id == task_id)
                .where(_snapshot_run_filter(source_tag.c.created_by_run_id, snapshot_run_ids))
                .where(
                    source_tag.c.task_source_snapshot_id.in_(
                        _screened_in_doc_ids(
                            task_id,
                            scope_ids,
                            screened_by_run_ids=snapshot_run_ids,
                        )
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


def _turn_search_queries(tool_calls: Sequence[Mapping[str, Any]]) -> list[str]:
    """Return this turn's well-formed ``search_chunks`` query strings.

    Malformed queries are skipped rather than raised — the actual tool call
    still runs its own validation and rejects them there; this is only a
    best-effort embedding warm-up (022 rider 16).
    """
    queries: list[str] = []
    for call in tool_calls:
        if not isinstance(call, Mapping) or call.get("tool") != "search_chunks":
            continue
        arguments = call.get("arguments")
        if not isinstance(arguments, Mapping):
            continue
        query = arguments.get("query")
        if (
            isinstance(query, str)
            and query
            and len(query) <= SEARCH_QUERY_MAX_LENGTH
            and not has_control_character(query)
        ):
            queries.append(query)
    return queries


def _execute_traced_tool(
    langfuse_client: Any | None,
    *,
    name: str,
    tool: Callable[[dict[str, Any]], dict[str, Any]],
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Run one read tool under a ``tool:{name}`` observation carrying its I/O."""
    return tracing.traced_call(
        langfuse_client,
        name=f"tool:{name}",
        as_type="tool",
        call=lambda: tool(arguments),
        update=lambda span, result: span.update(input=arguments, output=result),
    )


def run_tool_loop(
    turn_fn: TurnFn,
    *,
    tools: Mapping[str, Callable[[dict[str, Any]], dict[str, Any]]],
    turn_cap: int,
    retriever: ChunkRetriever | None = None,
    emit_label: str = "emit_section",
    on_tool_start: Callable[[str, dict[str, Any]], None] | None = None,
    langfuse_client: Any | None = None,
    on_tool_result: Callable[[str, dict[str, Any]], None] | None = None,
) -> ToolLoopResult:
    """Run the shared bounded read-tool loop with an adapter-owned terminal emission.

    Args:
        turn_fn: Backend turn adapter receiving transcript and ``force_emit``.
        tools: Closed read-only tool mapping.
        turn_cap: Maximum generation turns; final turn forces an emission.
        retriever: Optional chunk retriever used for per-turn query warm-up.
        emit_label: Terminal-emitter label recorded on a malformed retry.
        on_tool_start: Optional progress hook invoked before a valid tool call.
        langfuse_client: Optional Langfuse client; each executed read tool then
            traces as a ``tool:{name}`` observation beside the turn's generation.
        on_tool_result: Optional hook invoked with the tool's name and result
            after a tool call has run and been added to the transcript.

    Returns:
        Terminal emission, transcript, and bounded-loop accounting.

    Raises:
        RuntimeError: If the backend violates the loop protocol.
        ValueError: If ``turn_cap`` is not positive.
    """
    if turn_cap <= 0:
        raise ValueError("turn_cap must be positive")
    transcript: list[ToolExchange] = []
    tool_call_counts: dict[str, int] = {}
    rejected_tool_calls = 0
    malformed_claims = 0
    extra_tool_calls_ignored = 0
    usage_totals = UsageAccumulator()

    for turn in range(1, turn_cap + 1):
        force_emit = turn == turn_cap
        try:
            result, usage = turn_fn(transcript, force_emit=force_emit)
            usage_totals.add(usage)
        except MalformedEmissionError as exc:
            if force_emit:
                raise RuntimeError(
                    "malformed claims emission on the forced final turn"
                ) from exc
            transcript.append({
                "tool": emit_label,
                "arguments": {},
                "result": {"error": f"{emit_label} arguments invalid: {exc}"},
            })
            rejected_tool_calls += 1
            continue
        emission = result.get("emission")
        tool_calls = result.get("tool_calls", [])
        malformed_claims += int(result.get("malformed", 0))
        extra_tool_calls_ignored += int(result.get("extra_ignored", 0))
        if emission is not None:
            return {
                "emission": emission,
                "transcript": transcript,
                "turns_used": turn,
                "tool_call_counts": tool_call_counts,
                "rejected_tool_calls": rejected_tool_calls,
                "turn_cap_hit": force_emit,
                "malformed_claims": malformed_claims,
                "extra_tool_calls_ignored": extra_tool_calls_ignored,
                "usage_totals": usage_totals.payload(),
            }
        if force_emit and tool_calls:
            raise RuntimeError("backend returned tool call on forced emit turn")
        if not tool_calls:
            raise RuntimeError("backend returned no claims or tool calls")

        if retriever is not None:
            retriever.warm_queries(_turn_search_queries(tool_calls))

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
                if on_tool_start is not None:
                    on_tool_start(tool_name, cast("dict[str, Any]", arguments))
                tool_result = _execute_traced_tool(
                    langfuse_client,
                    name=tool_name,
                    tool=tools[tool_name],
                    arguments=cast("dict[str, Any]", arguments),
                )
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
            if on_tool_result is not None:
                on_tool_result(tool_name, tool_result)

    raise RuntimeError("section loop exhausted without emission")


def _tool_activity(tool_name: str, arguments: Mapping[str, Any]) -> str | None:
    """Return the activity line for a read tool the writer is about to run."""
    if tool_name == "search_chunks":
        query = normalise_query(arguments.get("query"))
        if query:
            return activity("synthesise.looking_for", query=query)
        return activity("synthesise.looking_up")
    if tool_name == "query_findings":
        return activity("synthesise.reading_findings")
    if tool_name == "lookup":
        return activity("synthesise.looking_up")
    return None


def run_section_loop(
    backend: Any,
    *,
    seed: dict[str, Any],
    tools: Mapping[str, Callable[[dict[str, Any]], dict[str, Any]]],
    turn_cap: int = SECTION_TURN_CAP,
    retriever: ChunkRetriever | None = None,
    langfuse_client: Any | None = None,
    section_line: str | None = None,
) -> SectionLoopResult:
    """Run one bounded section loop against the closed read-only tool set.

    While it runs, the loop publishes what the writer is doing (task 058,
    N3): before each read tool, "Looking for: <query>", "Reading findings" or
    "Looking up sources"; before the write turn, "Writing". Each line
    carries ``section_line`` so the user sees which section it belongs to.

    After each read tool returns, the loop also publishes the sources its
    results came from, so the page can say which sources the writer is
    drawing on (task 058, owner 2026-11-05; see :func:`read_sources`).

    The write turn (task 058, owner 2026-11-05) runs when the writer says it
    has gathered enough (a ``ready`` turn: it called ``write_section``) or
    when the turn budget runs out. It is the same loop turn as the ready
    signal, and its tokens are added to that turn's. A backend that returns
    claims on an open turn by itself (the offline scripted backend) is still
    accepted.

    Args:
        backend: Synthesis backend implementing ``section_turn``, and
            optionally ``section_emit_stream`` for a streamed write turn.
        seed: Id-keyed section seed.
        tools: Available substrate tools.
        turn_cap: Maximum generation turns; final turn forces emission.
        retriever: Optional chunk retriever. When given, a turn's uncached
            ``search_chunks`` query embeddings are batched into one backend
            call before the turn's tool calls execute (022 rider 16).
        langfuse_client: Optional Langfuse client for the tool spans.
        section_line: The section's own line ("Section 3 of 7 · Costs"),
            sent with every activity line, or ``None``.

    Returns:
        Claims, transcript and accounting counters.

    Raises:
        RuntimeError: If the backend violates the loop protocol.
    """

    def on_tool_start(tool_name: str, arguments: dict[str, Any]) -> None:
        line = _tool_activity(tool_name, arguments)
        if line is not None:
            liveness.publish_progress(activity=line, section=section_line)

    # The page's index for this section, as the streamed text uses it.
    display_index = int(seed.get("display_index", seed.get("section_index", 0)))

    def on_tool_result(_tool_name: str, result: dict[str, Any]) -> None:
        # Display-only: naming the sources must never stop the section.
        try:
            sources = read_sources(result)
        except Exception as exc:  # noqa: BLE001
            log.warning("synthesis.read_sources.failed", error=type(exc).__name__)
            return
        if sources:
            liveness.publish_section_sources(display_index, sources)

    stream_emit = getattr(backend, "section_emit_stream", None)

    def write(transcript: list[ToolExchange]) -> UsageResult[Mapping[str, Any]]:
        # The write turn: "Writing" for the user, then the section streamed
        # when the backend can, else the forced emit_section call.
        liveness.publish_progress(
            activity=activity("synthesise.writing"), section=section_line
        )
        if stream_emit is not None:
            streamed: UsageResult[Mapping[str, Any]] = stream_emit(seed, transcript)
            return streamed
        forced: UsageResult[Mapping[str, Any]] = backend.section_turn(
            seed, transcript, force_emit=True
        )
        return forced

    def turn_fn(
        transcript: list[ToolExchange], *, force_emit: bool
    ) -> UsageResult[LoopTurn]:
        if force_emit:
            result, usage = write(transcript)
        else:
            result, usage = backend.section_turn(seed, transcript, force_emit=False)
            if result.get("ready"):
                # The writer said it has enough (write_section, task 058):
                # write in this same loop turn and count both calls' tokens.
                result, write_usage = write(transcript)
                usage = add_token_usage(usage, write_usage)
        return {
            "emission": result.get("claims"),
            "tool_calls": result.get("tool_calls", []),
            "malformed": int(result.get("malformed_claims", 0)),
            "extra_ignored": int(result.get("extra_tool_calls_ignored", 0)),
        }, usage

    result = run_tool_loop(
        turn_fn,
        tools=tools,
        turn_cap=turn_cap,
        retriever=retriever,
        langfuse_client=langfuse_client,
        on_tool_start=on_tool_start,
        on_tool_result=on_tool_result,
    )
    return {
        "claims": cast("SectionProseWire | None", result["emission"]),
        "transcript": result["transcript"],
        "turns_used": result["turns_used"],
        "tool_call_counts": result["tool_call_counts"],
        "rejected_tool_calls": result["rejected_tool_calls"],
        "turn_cap_hit": result["turn_cap_hit"],
        "malformed_claims": result["malformed_claims"],
        "extra_tool_calls_ignored": result["extra_tool_calls_ignored"],
        "usage_totals": result["usage_totals"],
    }


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
                    if not isinstance(chunk, dict):
                        continue
                    # already_returned references stay citation-eligible (their
                    # content was shown earlier); budget-skip markers never are.
                    if chunk.get("skipped_over_budget"):
                        continue
                    if isinstance(chunk.get("chunk_record_id"), str):
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


# Sources named on the page while a section is written (task 058, owner 2026-11-05)

#: Gives each source id (a task source snapshot id) the short name the page shows.
type SourceLabeller = Callable[[Sequence[str]], Mapping[str, str]]

#: The name shown for a source with no title and no locator (never a raw id).
UNTITLED_SOURCE = "Untitled source"

#: How deep :func:`read_sources` looks into one tool result.
_READ_SOURCES_MAX_DEPTH = 6

_source_labeller: ContextVar[SourceLabeller | None] = ContextVar(
    "synthesis_source_labeller", default=None
)


@contextmanager
def source_labelling(labeller: SourceLabeller | None) -> Iterator[None]:
    """Name sources with ``labeller`` for the sources and citations shown live.

    In plain terms: while a section is written, the page shows which sources
    the writer read and which ones each sentence cites. The tool results only
    carry each source's title; ``labeller`` (built once per run from the
    database by :func:`make_source_labeller`) gives the shorter "Smith 2023"
    form. Without one, the record's own title is used.

    Args:
        labeller: Maps source ids to names, or ``None``.

    Yields:
        Nothing; the binding lasts until the block exits.
    """
    token = _source_labeller.set(labeller)
    try:
        yield
    finally:
        _source_labeller.reset(token)


def _record_title(record: Mapping[str, Any], source_id: str) -> str | None:
    """Return a record's own title, unless it is the ``source <id>`` placeholder."""
    for key in ("document_title", "title"):
        title = record.get(key)
        if isinstance(title, str) and title.strip() and title != f"source {source_id}":
            return title.strip()
    return None


def name_sources(found: Sequence[tuple[str, str | None]]) -> list[liveness.SourceRef]:
    """Give each ``(source_id, own_title)`` pair the name the page shows.

    The bound labeller's name wins; otherwise the record's own title; otherwise
    :data:`UNTITLED_SOURCE`. Repeated ids are kept once, in first-seen order.

    Args:
        found: Source ids with the title their record carried (or ``None``).

    Returns:
        ``(source_id, name)`` pairs.
    """
    unique: dict[str, str | None] = {}
    for source_id, title in found:
        if unique.get(source_id) is None:
            unique[source_id] = title
    if not unique:
        return []
    labeller = _source_labeller.get()
    labels: Mapping[str, str] = {}
    if labeller is not None:
        labels = labeller(list(unique))
    return [
        (source_id, labels.get(source_id) or title or UNTITLED_SOURCE)
        for source_id, title in unique.items()
    ]


def read_sources(result: Mapping[str, Any]) -> list[liveness.SourceRef]:
    """Name the sources one read tool's result came from, in first-seen order.

    Every record in the result that carries a ``tss_id`` counts: a chunk from
    ``search_chunks``, a finding from ``query_findings``, a document from
    ``lookup``. Stubs for records already returned, and chunks skipped over
    the text budget, carry no ``tss_id`` and so add nothing.

    Args:
        result: The tool's result.

    Returns:
        ``(source_id, name)`` pairs, each source once.
    """
    found: list[tuple[str, str | None]] = []

    def walk(value: Any, depth: int) -> None:
        if depth > _READ_SOURCES_MAX_DEPTH:
            return
        if isinstance(value, Mapping):
            tss_id = value.get("tss_id")
            if isinstance(tss_id, str) and tss_id:
                found.append((tss_id, _record_title(value, tss_id)))
            for child in value.values():
                if isinstance(child, Mapping | list):
                    walk(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                walk(child, depth + 1)

    walk(result, 0)
    return name_sources(found)


def citable_sources(
    seed: Mapping[str, Any], transcript: Sequence[ToolExchange]
) -> tuple[dict[str, tuple[str, str | None]], dict[str, tuple[str, str | None]]]:
    """Map the chunk and finding ids a section may cite to their sources.

    Args:
        seed: The section seed (its ``member_findings`` are citable).
        transcript: The section's tool exchanges so far.

    Returns:
        ``(by_chunk_id, by_finding_id)``, each mapping an id to
        ``(source_id, own_title)``.
    """
    by_chunk: dict[str, tuple[str, str | None]] = {}
    by_finding: dict[str, tuple[str, str | None]] = {}

    def keep(record: Any) -> None:
        if not isinstance(record, Mapping):
            return
        tss_id = record.get("tss_id")
        if not isinstance(tss_id, str) or not tss_id:
            return
        source = (tss_id, _record_title(record, tss_id))
        chunk_id = record.get("chunk_record_id")
        if isinstance(chunk_id, str):
            by_chunk.setdefault(chunk_id, source)
        finding_id = record.get("finding_id")
        if isinstance(finding_id, str):
            by_finding.setdefault(finding_id, source)

    for finding in seed.get("member_findings", []) or []:
        keep(finding)
    for exchange in transcript:
        result = exchange.get("result")
        if not isinstance(result, Mapping):
            continue
        for key in ("chunks", "findings", "iof_findings", "icf_findings"):
            records = result.get(key)
            if isinstance(records, list):
                for record in records:
                    keep(record)
    return by_chunk, by_finding


def _first_author(metadata: Mapping[str, Any]) -> str | None:
    """Return the first author's family name, or ``None`` when the record has none."""
    provider = metadata.get("provider_fields")
    provider = provider if isinstance(provider, Mapping) else {}
    name: str | None = None
    authorships = provider.get("authorships")
    if isinstance(authorships, list):
        for entry in authorships:
            if isinstance(entry, Mapping):
                value = entry.get("author_name")
                if isinstance(value, str) and value.strip():
                    name = value.strip()
                    break
    if name is None:
        authors = provider.get("authors")
        if isinstance(authors, str) and authors.strip():
            name = authors.strip()
        elif isinstance(authors, list):
            name = next((a.strip() for a in authors if isinstance(a, str) and a.strip()), None)
    if name is None:
        return None
    if "," in name:
        # "Smith, Jane": the family name comes first.
        return name.split(",", 1)[0].strip() or None
    return name.split()[-1]


def source_short_name(metadata: Mapping[str, Any], locator: str | None) -> str:
    """Return the short name the page shows for a source (task 058).

    The first author's family name (or, without authors, the publisher) and
    the year, as "Smith 2023", when both are known; otherwise the title, as
    the Result tab's references show it; otherwise where the source came from
    (its locator); otherwise :data:`UNTITLED_SOURCE`.

    Args:
        metadata: The source snapshot's metadata.
        locator: The source snapshot's locator, or ``None``.

    Returns:
        The name.
    """
    year = metadata.get("publication_year", metadata.get("year"))
    if not isinstance(year, int) or isinstance(year, bool):
        year = None
    who = _first_author(metadata)
    if who is None:
        publisher = metadata.get("publisher_org")
        who = publisher.strip() if isinstance(publisher, str) and publisher.strip() else None
    if who is not None and year is not None:
        return f"{who} {year}"
    title = metadata.get("title")
    if isinstance(title, str) and title.strip():
        return html.unescape(title.strip())
    if locator:
        return locator
    return UNTITLED_SOURCE


def make_source_labeller(conn: Connection, *, task_id: uuid.UUID) -> SourceLabeller:
    """Build a labeller that names a task's sources from the database, once each.

    Names are read on first use and remembered, so each source is read once
    per run.

    Args:
        conn: Open database connection.
        task_id: The task whose sources are named.

    Returns:
        A function from source ids to their short names (ids that are not
        this task's sources are left out).
    """
    known: dict[str, str] = {}

    def labels(source_ids: Sequence[str]) -> Mapping[str, str]:
        wanted: list[uuid.UUID] = []
        for source_id in source_ids:
            if source_id in known:
                continue
            try:
                wanted.append(uuid.UUID(source_id))
            except ValueError:
                continue
        if wanted:
            # An id that is not this task's source is remembered as unnamed,
            # so it is not read again.
            known.update({str(source_id): "" for source_id in wanted})
            rows = conn.execute(
                sa_select(
                    task_source_snapshot.c.task_source_snapshot_id,
                    source_snapshot.c.metadata,
                    source_snapshot.c.source_locator,
                )
                .join(
                    source_snapshot,
                    source_snapshot.c.source_snapshot_id
                    == task_source_snapshot.c.source_snapshot_id,
                )
                .where(task_source_snapshot.c.task_id == task_id)
                .where(task_source_snapshot.c.task_source_snapshot_id.in_(wanted))
            )
            for row in rows:
                metadata = row.metadata if isinstance(row.metadata, Mapping) else {}
                known[str(row.task_source_snapshot_id)] = source_short_name(
                    metadata, row.source_locator
                )
        return {
            source_id: known[source_id]
            for source_id in source_ids
            if known.get(source_id)
        }

    return labels
