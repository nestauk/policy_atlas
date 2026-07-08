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

from dataclasses import dataclass, field
from typing import Any, Protocol, TypedDict

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
