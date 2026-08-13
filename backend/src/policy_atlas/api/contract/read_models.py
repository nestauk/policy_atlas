"""Owner-scoped read-model contract (spec § Read models).

These are the shapes served under `/api/v1/projects/{id}/…` for `funnel`,
`landscape`, `groups`, `evidence`, `findings`, `decisions`, `artefact` and
`coverage`, plus the `chunk-context` seam. Read models render honest
absence: missing stages are `null`/absent, never faked.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from .planning import ExtractProfile
from .sse import DecidedBy

#: Evidence acquisition/screening origin. Mirrors the acquisition backends.
EvidenceOrigin = Literal["OpenAlex", "Overton", "Uploaded"]

#: Evidence status ladder (spec § Read models; demo `evidence` shape).
EvidenceStatus = Literal[
    "found",
    "screened_out",
    "relevant",
    "not_selected",
    "selected",
    "read_in_full",
    "findings_extracted",
    "cited",
    "unavailable",
]

#: The `?status=Included` filter shortcut: every ladder position reached
#: once a source has been screened in, i.e. the full ladder minus the two
#: pre-decision positions `found` (not yet screened) and `screened_out`
#: (screened out) — spec § Read models filters.
EVIDENCE_STATUS_INCLUDED: tuple[EvidenceStatus, ...] = (
    "relevant",
    "not_selected",
    "selected",
    "read_in_full",
    "findings_extracted",
    "cited",
    "unavailable",
)

#: Values accepted by the evidence `status` query filter: the full ladder
#: plus the `Included` aggregate shortcut (repeatable; combinable with
#: `cited`).
EvidenceStatusFilter = Literal[
    "found",
    "screened_out",
    "relevant",
    "not_selected",
    "selected",
    "read_in_full",
    "findings_extracted",
    "cited",
    "unavailable",
    "Included",
]

#: Run-scoped B2' relevance mark on a finding.
FindingRelevance = Literal["priority", "normal"]

#: Artefact section role (page order: key_findings, then standard, then
#: conclusions).
SectionRole = Literal["key_findings", "standard", "conclusions"]

#: Claim annotation type. Every annotation is a prose span; `citations` is
#: populated for `citation`-type claims only.
ClaimType = Literal["citation", "gap", "reasoning", "pattern", "theme", "unspanned_assertion"]


class FunnelOut(BaseModel):
    """The acquisition-to-citation funnel counts.

    Args:
        found: Total acquired.
        relevant: Passed abstract screening.
        screened_out: Excluded at screening.
        quality_checked: Passed appraisal.
        read_in_full: Full text ingested.
        selected: Passed selection.
        findings: Findings extracted.
        cited: Cited in the artefact.

    Any field is `None` before its stage has run — the funnel spans the
    full flow, unlike the screened-in-only `landscape`.
    """

    found: int | None = None
    relevant: int | None = None
    screened_out: int | None = None
    quality_checked: int | None = None
    read_in_full: int | None = None
    selected: int | None = None
    findings: int | None = None
    cited: int | None = None


class ThemeOut(BaseModel):
    """One landscape theme.

    Args:
        name: Theme name.
        size: Number of items in the theme.
        description: Short theme description.
        theme_id: Stable theme identity, absent for legacy characterisations.
    """

    name: str
    size: int
    description: str
    theme_id: uuid.UUID | None = None


class LandscapeOut(BaseModel):
    """Distributions over the screened-in set only (never the found count).

    Args:
        evidence_types: Counts by evidence type label.
        years: Counts by publication year.
        themes: Landscape themes.
        geographies: Optional counts by geography label.
    """

    evidence_types: dict[str, int] = Field(default_factory=dict)
    years: dict[str, int] = Field(default_factory=dict)
    themes: list[ThemeOut] = Field(default_factory=list)
    geographies: dict[str, int] | None = None


class GroupOut(BaseModel):
    """One group within a grouping facet.

    Args:
        label: Group label.
        description: Short group description.
        size: Number of members in the group.
    """

    label: str
    description: str
    size: int


class FacetGroupsOut(BaseModel):
    """Groups produced for one grouping facet.

    Args:
        facet: Grouping facet name.
        groups: Groups within the facet.
        ungrouped: Number of members not placed in any group.
    """

    facet: str
    groups: list[GroupOut] = Field(default_factory=list)
    ungrouped: int


class GroupsOut(BaseModel):
    """The `groups` read model.

    Args:
        facets: Per-facet group listings.
    """

    facets: list[FacetGroupsOut] = Field(default_factory=list)


class EvidenceItemOut(BaseModel):
    """One row of the paginated evidence/source list.

    Args:
        source_id: The source's identity.
        title: Source title.
        year: Publication year, or `None` if unknown.
        venue: Publication venue, or `None` if unknown.
        origin: Acquisition backend.
        status: Position on the evidence status ladder.
        status_reason: Optional human-readable reason for the current status
            (e.g. why screened out).
        evidence_type: Optional evidence type label.
        appraisal_tier: Optional appraisal tier label.
        cited: Whether this source is cited in the artefact.
        url: Optional source URL.
    """

    source_id: uuid.UUID
    title: str
    year: int | None = None
    venue: str | None = None
    origin: EvidenceOrigin
    status: EvidenceStatus
    status_reason: str | None = None
    evidence_type: str | None = None
    appraisal_tier: str | None = None
    cited: bool
    url: str | None = None
    screen_confidence: float | None = None
    screen_basis: str | None = None
    screen_stage: int | None = None
    screen_status: Literal["relevant", "not_relevant", "excluded_retracted"] | None = None
    # 028 refinement (additive): the LLMs' one-sentence reasons, recovered
    # from the event log (they are event-payload-only, never result-row
    # columns), and the read depth the status ladder otherwise collapses.
    screen_reason: str | None = None
    classification_reason: str | None = None
    read_in_full: bool = False


class FindingBaseOut(BaseModel):
    """One row of the paginated findings list.

    Args:
        finding_id: The finding's identity.
        statement: The finding's text/claim statement.
        source_id: Identity of the source the finding was extracted from.
        source_title: Title of that source.
        profile: Extraction profile the finding came from.
        relevance: Run-scoped B2' relevance mark, when the run has them.
    """

    finding_id: uuid.UUID
    statement: str
    source_id: uuid.UUID
    source_title: str
    profile: ExtractProfile
    relevance: FindingRelevance | None = None


class IofStatisticsOut(BaseModel):
    """Reported IOF statistics, with authentic nulls for absent values."""

    effect_size: float | None = None
    effect_size_type: str | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None
    standard_error: float | None = None
    p_value: float | None = None
    n: int | None = None
    k: int | None = None
    i_squared: float | None = None
    tau2: float | None = None


class IofFindingOut(FindingBaseOut):
    """An intervention-outcome finding, discriminated by ``profile='iof'``."""

    profile: Literal["iof"] = "iof"
    intervention: str
    outcome: str
    effect_direction: str
    statistics: IofStatisticsOut
    comparator: str | None = None
    estimate_level: str | None = None
    causality_by_design: str | None = None
    is_primary: bool | None = None
    stratum_qualifiers: list[dict[str, str]] = Field(default_factory=list)
    effect_basis: str | None = None
    study_geography: str | None = None
    population: str | None = None
    setting: str | None = None
    study_design: str | None = None
    quote: str | None = None
    quote_verified: bool | None = None
    groups: dict[str, str] = Field(default_factory=dict)


class IcfFindingOut(FindingBaseOut):
    """An implementation-context finding, discriminated by ``profile='icf'``."""

    profile: Literal["icf"] = "icf"
    context_type: str
    claim: str
    context_label: str | None = None
    intervention: str
    outcome: str | None = None
    population: str | None = None
    setting: str | None = None
    study_geography: str | None = None
    study_design: str | None = None
    claim_level: str | None = None
    claim_basis: str | None = None
    level: str | None = None
    resource_requirements: str | None = None
    workforce_requirements: str | None = None
    quote: str | None = None
    quote_verified: bool | None = None
    groups: dict[str, str] = Field(default_factory=dict)


type FindingOut = Annotated[IofFindingOut | IcfFindingOut, Field(discriminator="profile")]


class SourceTagOut(BaseModel):
    """One source tag assertion and its provenance."""

    tag: str
    tag_type: str
    asserted_by: str


class CitedInOut(BaseModel):
    """One latest-artefact claim which cites a source."""

    claim: str
    quote: str
    section_title: str


class SourceDossierOut(EvidenceItemOut):
    """The optional source dossier, including provenance and latest citations."""

    abstract: str | None = None
    abstract_source: Literal["provider", "llm_description"] | None = None
    publisher: str | None = None
    record_type: str | None = None
    language: str | None = None
    doi: str | None = None
    cited_by_count: int | None = None
    fwci: float | None = None
    tags: list[SourceTagOut] = Field(default_factory=list)
    cited_in: list[CitedInOut] = Field(default_factory=list)


class DecisionOut(BaseModel):
    """One entry in the paginated decision log.

    Args:
        sequence: The underlying event's `event_log` sequence.
        occurred_at: When the decision was recorded.
        kind: Decision kind.
        summary: Human-readable summary of the decision.
        decided_by: Who decided, when known.
        detail: Optional structured detail.
    """

    sequence: int
    occurred_at: datetime
    kind: str
    summary: str
    decided_by: DecidedBy | None = None
    detail: dict[str, Any] | None = None


class CitationOut(BaseModel):
    """One citation attached to a citation-type claim.

    Args:
        citation_id: Durable citation identity — the key for the
            chunk-context endpoint (`GET .../citations/{citation_id}/context`).
        n: Reference number (matches a `ReferenceOut.n`).
        source_id: The cited document's project source identity, when the
            citation resolves to one (joins to the sources/dossier surface).
        source_title: Cited source's title (envelope metadata).
        quote: The quoted span from the source.
        grounding_tier: Optional grounding-judge tier label.
        grounding_rationale: The grounding judge's recorded reason for the
            tier, when one was persisted with the verdict.
        appraisal_label: Optional appraisal label.
        evidence_type: The cited document's classified evidence type — the
            input the appraisal rubric scores from.
    """

    citation_id: uuid.UUID
    n: int
    source_id: uuid.UUID | None = None
    source_title: str
    quote: str
    grounding_tier: str | None = None
    grounding_rationale: str | None = None
    appraisal_label: str | None = None
    evidence_type: str | None = None


class GapCaveatOut(BaseModel):
    """The evidence-coverage caveat accompanying a gap claim."""

    search_space: str | None = None
    adequacy_verdict: str | None = None
    verdict_origin: str | None = None


class GapOut(BaseModel):
    """A structured gap explanation attached to one claim."""

    grade: str | None = None
    caveat: GapCaveatOut | None = None
    inferred: bool | None = None


class ThemeSourceOut(BaseModel):
    """One source contributing to a theme or grouping reference.

    Args:
        source_id: The project's source identity.
        title: Display title of the source.
    """

    source_id: uuid.UUID
    title: str


class ThemeRefItemOut(BaseModel):
    """One named durable theme or grouping reference.

    Args:
        name: Display name for the theme or group.
        description: Optional concise description.
        size: Optional number of members.
        facet: Grouping facet, when this is a group reference.
        sources: Resolved member sources, when member identities are available.
    """

    name: str
    description: str | None = None
    size: int | None = None
    facet: str | None = None
    sources: list[ThemeSourceOut] | None = None


class ThemeRefOut(BaseModel):
    """The durable themes or groups a theme claim describes.

    Args:
        source: Whether the references are characterisation themes or groups.
        base: Optional source-data basis recorded by synthesis.
        items: Resolved named references.
    """

    source: Literal["characterisation", "grouping"]
    base: str | None = None
    items: list[ThemeRefItemOut]


class ClaimOut(BaseModel):
    """One span-anchored claim annotation within a block.

    Args:
        claim_id: The claim's identity.
        claim_type: Annotation type.
        text: The spanned text.
        span: Character offsets `[start, end]` into the block's `prose`, or
            `None`.
        citations: Citations attached to this claim (citation-type only).
        theme: Named themes or groups referenced by a theme claim.
    """

    claim_id: uuid.UUID
    claim_type: ClaimType
    text: str
    span: tuple[int, int] | None = None
    citations: list[CitationOut] = Field(default_factory=list)
    weakly_grounded: bool | None = None
    gap: GapOut | None = None
    theme: ThemeRefOut | None = None


class BlockOut(BaseModel):
    """One prose block within an artefact section.

    Args:
        block_id: The block's identity.
        prose: The block's final persisted prose.
        claims: Span-anchored claim annotations over `prose`.
        gaps: Deprecated legacy coverage gaps. New structured gaps are carried
            by `ClaimOut.gap`; this field remains empty for new artefacts.
    """

    block_id: uuid.UUID
    prose: str
    claims: list[ClaimOut] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class SectionOut(BaseModel):
    """One artefact section.

    Args:
        title: Section title.
        role: Section role (determines page position).
        blocks: The section's prose blocks, in order.
        summary: Verified summary for a single-block section, if available.
        summary_status: Summary production state for a single-block section.
    """

    title: str
    role: SectionRole
    focus: str | None = None
    blocks: list[BlockOut] = Field(default_factory=list)
    summary: str | None = None
    summary_status: Literal["pending", "verified", "failed"] | None = None


class ReferenceOut(BaseModel):
    """One numbered reference in the artefact's reference list.

    Args:
        n: Reference number.
        title: Reference title.
        year: Publication year, or `None` if unknown.
        venue: Publication venue, or `None` if unknown.
        url: Optional reference URL.
    """

    n: int
    title: str
    year: int | None = None
    venue: str | None = None
    url: str | None = None


class CoverageSnapshotOut(BaseModel):
    """The artefact's embedded coverage snapshot.

    Args:
        source_count: Number of sources underlying the artefact.
        study_types: Counts by study type.
        year_range: Inclusive `[min_year, max_year]`, or `None`.
        included: Number of sources included.
        screened_out: Number of sources screened out.
    """

    source_count: int | None = None
    study_types: dict[str, int] = Field(default_factory=dict)
    year_range: tuple[int, int] | None = None
    included: int | None = None
    screened_out: int | None = None


class ArtefactOut(BaseModel):
    """The `artefact` read model — the synthesised evidence base.

    Args:
        artefact_id: The artefact's durable identity — the id a chat's
            entry-context chip binds to (029 strand 6).
        title: Artefact title.
        question: The evidence question the artefact answers.
        coverage_snapshot: Embedded coverage snapshot.
        sections: Artefact sections, in final page order.
        references: Numbered reference list.
        summary: Artefact-level summary, if produced.
        summary_status: Artefact-level summary production state.
    """

    artefact_id: uuid.UUID
    title: str
    question: str
    coverage_snapshot: CoverageSnapshotOut
    sections: list[SectionOut] = Field(default_factory=list)
    references: list[ReferenceOut] = Field(default_factory=list)
    summary: str | None = None
    summary_status: Literal["pending", "verified", "failed"] | None = None


class CoverageOut(BaseModel):
    """The `coverage` read model — the composed one-line coverage sentence.

    Args:
        sentence: The composed coverage sentence (stop condition + adequacy).
        base: Structured basis the sentence was composed from.
    """

    sentence: str
    base: dict[str, Any] = Field(default_factory=dict)
    backends: list[str] = Field(default_factory=list)
    backends_detail: list[CoverageBackendDetailOut] = Field(default_factory=list)


class CoverageQueryOut(BaseModel):
    """One completed query and its result count for a public backend."""

    query: str
    results: int


class CoverageBackendDetailOut(BaseModel):
    """Post-run source counts for one public backend.

    ``relevant`` is deliberately project-wide in C.1; per-query relevance
    was not recorded and is therefore absent.
    """

    backend: str
    results: int
    relevant: int
    queries: list[CoverageQueryOut] = Field(default_factory=list)


class ChunkContextOut(BaseModel):
    """The chunk-context read model for a cited span (the 008 seam).

    Args:
        context: Context text, clamped to a character window around the
            cited span.
        span_start: Start offset of the clamped context.
        span_end: End offset of the clamped context.
        clamped: Whether the window was clamped (hit a chunk boundary).
    """

    context: str
    span_start: int
    span_end: int
    clamped: bool
    previous: str | None = None
    next: str | None = None
    year: int | None = None
    venue: str | None = None
