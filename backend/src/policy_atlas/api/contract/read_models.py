"""Owner-scoped read-model contract (spec § Read models).

These are the shapes served under `/api/v1/tasks/{id}/…` for `funnel`,
`landscape`, `groups`, `evidence`, `findings`, `decisions`, `artefact` and
`coverage`, plus the `chunk-context` seam. Read models render honest
absence: missing stages are `null`/absent, never faked.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .sse import DecidedBy
from .task_agent import ExtractProfile, OptionDesignOut
from .tasks import LatestRun

#: The longest user text an option route accepts (the option's words, a reason).
OPTION_TEXT_MAX = 1_000

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

#: Artefact section role (page order: key_findings, case_studies, then
#: standard, then conclusions).
SectionRole = Literal["key_findings", "case_studies", "standard", "conclusions"]

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
    # The document's own description — the provider abstract, a snippet, or
    # the provider's LLM-written description (flagged as such).
    abstract: str | None = None
    abstract_source: Literal["provider", "llm_description"] | None = None


class FindingBaseOut(BaseModel):
    """One row of the paginated findings list.

    Args:
        finding_id: The finding's identity.
        statement: The finding's text/claim statement.
        source_id: Identity of the source the finding was extracted from.
        source_title: Title of that source.
        profile: Extraction profile the finding came from.
        relevance: Run-scoped B2' relevance mark, when the run has them.
        chunk_id: Verified chunk identity from the first grounding anchor, or
            ``None`` for abstract-only findings.
    """

    finding_id: uuid.UUID
    statement: str
    source_id: uuid.UUID
    source_title: str
    profile: ExtractProfile
    relevance: FindingRelevance | None = None
    chunk_id: uuid.UUID | None = None


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


class AuthorshipOut(BaseModel):
    """One author and their institutions, for display.

    Args:
        name: Author display name. For a policy document with no named
            people this is the issuing organisation (corporate author).
        institutions: Institution display names, possibly empty.
    """

    name: str
    institutions: list[str] = Field(default_factory=list)


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

    publisher: str | None = None
    record_type: str | None = None
    language: str | None = None
    doi: str | None = None
    cited_by_count: int | None = None
    fwci: float | None = None
    tags: list[SourceTagOut] = Field(default_factory=list)
    cited_in: list[CitedInOut] = Field(default_factory=list)
    authorships: list[AuthorshipOut] = Field(default_factory=list)


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
        source_id: The cited document's task source identity, when the
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
        source_id: The task's source identity.
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


class CaseStudyCardOut(BaseModel):
    """One case-study programme card within the case-studies section.

    Args:
        card_id: Stable card identity.
        title: Programme name (place — instrument).
        prose: Short mechanism prose.
        claims: Span-anchored claim annotations within `prose`.
        result_claim_id: The claim carrying the programme's primary result,
            or ``None`` when the binding degrades.
        strength: Appraisal label of the cited evidence, when known.
        design: Evidence type / study design, when known.
        since_year: Earliest cited publication year, when known.
    """

    card_id: uuid.UUID
    title: str
    prose: str
    claims: list[ClaimOut] = Field(default_factory=list)
    result_claim_id: uuid.UUID | None = None
    strength: str | None = None
    design: str | None = None
    since_year: int | None = None


class SectionOut(BaseModel):
    """One artefact section.

    Args:
        title: Section title.
        role: Section role (determines page position).
        nav_label: Short scannable name for the contents list, or `None` for
            an artefact produced before the label existed. Absence is a normal
            state: the client falls back to a shortened title.
        blocks: The section's prose blocks, in order.
        cards: Case-study cards (populated only for ``case_studies`` sections).
        summary: Verified summary for a single-block section, if available.
        summary_status: Summary production state for a single-block section.
    """

    title: str
    role: SectionRole
    focus: str | None = None
    nav_label: str | None = None
    blocks: list[BlockOut] = Field(default_factory=list)
    cards: list[CaseStudyCardOut] = Field(default_factory=list)
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
        authorships: Authors and their institutions, for display.
    """

    n: int
    title: str
    year: int | None = None
    venue: str | None = None
    url: str | None = None
    authorships: list[AuthorshipOut] = Field(default_factory=list)


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


class MostRelevantNoteOut(BaseModel):
    """A grounded one-liner note for a top cited source.

    Args:
        source_id: The task source identity.
        note: One-sentence note restating only supplied evidence.
    """

    source_id: str
    note: str


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
        most_relevant_notes: Grounded notes for top cited sources.
        full_report_intro: Generated introduction to the full-report body, when present.
        summary: Artefact-level summary, if produced.
        summary_status: Artefact-level summary production state.
        template: Which write-up template produced this artefact
            (`"baseline"` for an options-scoping baseline; absent on every
            Evidence search report). Read straight off the roll-up — the
            client never derives it (task 044, C18).
        depth_label: How deep the pass behind this artefact went, in the
            words the roll-up recorded (`"scoping pass"` for a baseline).
    """

    artefact_id: uuid.UUID
    title: str
    question: str
    coverage_snapshot: CoverageSnapshotOut
    sections: list[SectionOut] = Field(default_factory=list)
    references: list[ReferenceOut] = Field(default_factory=list)
    most_relevant_notes: list[MostRelevantNoteOut] = Field(default_factory=list)
    full_report_intro: str | None = None
    summary: str | None = None
    summary_status: Literal["pending", "verified", "failed"] | None = None
    template: str | None = None
    depth_label: str | None = None


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

    ``relevant`` is deliberately task-wide in C.1; per-query relevance
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
            cited span. Truncated edges are snapped to a word boundary and
            marked with ``...``.
        span_start: Start offset of the clamped context.
        span_end: End offset of the clamped context.
        clamped: Whether the window was clamped (hit a chunk boundary).
        previous: Short tail of the previous chunk, only when the window
            reaches the start of this chunk; otherwise omitted.
        next: Short head of the next chunk, only when the window reaches
            the end of this chunk; otherwise omitted.
        authorships: Authors and their institutions, for display.
    """

    context: str
    span_start: int
    span_end: int
    clamped: bool
    previous: str | None = None
    next: str | None = None
    year: int | None = None
    venue: str | None = None
    authorships: list[AuthorshipOut] = Field(default_factory=list)


# --- The options-scoping longlist (task 045, S12; contract deliverables 9, 11) ---
#
# Assembled from the longlist walk's records, never written by a model (D15):
# the option rows, the run-keyed ``longlist_result`` (themes, coverage,
# judgements, guesses, counts) and the membership rows. Names on the wire are
# the product's; nothing here ever says "how sure" (ruling 33).

#: Where an option came from: clustered from documents, suggested by Policy
#: Atlas, drawn from the linked Evidence search's report, or added by the user.
OptionOrigin = Literal["clustered", "suggested", "from_evidence_search", "added_by_you"]

#: An option's state. "No in-scope evidence" is a condition, not a state.
OptionState = Literal["included", "excluded"]

#: Who excluded an option: the constrain step, or the user.
ExclusionBy = Literal["constrain", "user"]

#: What a document does with an option's intervention (comparators never
#: count as membership, so they have no value here).
OptionDocumentRole = Literal["evaluated", "described", "recommended", "mentioned"]

#: A document's study geography grouped against the plan's Where: ``where``
#: (in Where, shown under ``where_label``) · ``comparable`` (comparable
#: systems, OECD) · ``other`` · ``unknown``.
WhereTriedGroup = Literal["where", "comparable", "other", "unknown"]

#: A constraint judgement's verdict.
JudgementVerdict = Literal["passes", "breaks", "cannot_check"]

#: A reasoned guess's leaning.
GuessLeaning = Literal["likely_meets", "likely_falls_short", "cannot_say"]

#: A relation from this option's side: ``part_of`` (this option is a part of
#: the other, a package) or ``has_part`` (this option is the package).
OptionRelationKind = Literal["part_of", "has_part"]


class LonglistCountsOut(BaseModel):
    """The list view's header counts.

    ``options``, ``included``, ``excluded`` and ``no_in_scope`` are read from
    the option rows as they stand (a user exclusion counts at once);
    ``themes``, ``unclustered`` and ``not_an_option`` are the longlist run's.

    Args:
        options: Options on the longlist.
        themes: Themes.
        included: Options included.
        excluded: Options excluded.
        no_in_scope: Included options with no in-scope evidence.
        unclustered: Records assigned to no option.
        not_an_option: Records judged not to describe an actionable option.
        none_fits: Options no lever type fits.
    """

    options: int
    themes: int
    included: int
    excluded: int
    no_in_scope: int
    unclustered: int
    not_an_option: int
    none_fits: int


class LonglistThemeOut(BaseModel):
    """One theme: a generated grouping of options in the problem's own words.

    Args:
        theme_id: Stable theme identity.
        name: Theme name.
        description: One-line description.
        option_ids: The theme's options, in display order.
    """

    theme_id: uuid.UUID
    name: str
    description: str
    option_ids: list[uuid.UUID] = Field(default_factory=list)


class ExclusionOut(BaseModel):
    """Why an option is excluded.

    Args:
        constraint: The constraint it breaks, or "your decision".
        reason: The reason, in words.
        by: Who excluded it.
    """

    constraint: str
    reason: str
    by: ExclusionBy


class WhereTriedOut(BaseModel):
    """Documents per where-tried group (DOI-collapsed).

    Args:
        where: Studied in the plan's Where.
        comparable: Studied in a comparable system (OECD).
        other: Studied in another named country.
        unknown: No recognisable geography.
    """

    where: int = 0
    comparable: int = 0
    other: int = 0
    unknown: int = 0


class RelationOut(BaseModel):
    """A relation between two options, read from this option's side.

    Args:
        kind: ``part_of`` (this option is part of the other) or ``has_part``
            (the other is part of this one).
        other_option_id: The other option.
        other_name: The other option's name.
    """

    kind: OptionRelationKind
    other_option_id: uuid.UUID
    other_name: str


class OptionSummaryOut(BaseModel):
    """One option as the list view and the grid show it.

    Args:
        option_id: Stable option identity.
        name: Option name.
        description: One-sentence description.
        outcomes_served: The plan's outcomes the option serves.
        origin: Where it came from.
        state: Included or excluded.
        exclusion: Why it is excluded; `null` when included.
        no_in_scope_evidence: Included, but none of its documents passes the
            plan's evidence restriction.
        restriction_text: The restriction none of its documents passes, when
            `no_in_scope_evidence`.
        primary_lever_type: The primary lever type; `null` when none fits or
            the option is not typed yet.
        lever_none_fits_reason: Why no lever type fits.
        secondary_lever_types: The other lever types it also touches.
        ambition: `do_minimum` · `incremental` · `structural`, as described,
            not measured.
        ambition_reason: The one-line justification.
        taxonomy_version: The lever-type list version it was typed under.
        design_version: The specified design's version.
        document_count: Its documents (DOI-collapsed).
        evaluated_count: Documents that evaluate it.
        settings: The settings its documents name, most frequent first.
        where_tried: Documents per where-tried group.
        relations: Its relations to other options.
        abstract_only: Every one of its documents was read from an abstract only.
        is_entrant_with_no_documents: Suggested, drawn from the Evidence
            search or added by the user, and no document has joined it.
    """

    option_id: uuid.UUID
    name: str
    description: str
    outcomes_served: list[str] = Field(default_factory=list)
    origin: OptionOrigin
    state: OptionState
    exclusion: ExclusionOut | None = None
    no_in_scope_evidence: bool = False
    restriction_text: str | None = None
    primary_lever_type: str | None = None
    lever_none_fits_reason: str | None = None
    secondary_lever_types: list[str] = Field(default_factory=list)
    ambition: str | None = None
    ambition_reason: str | None = None
    taxonomy_version: str | None = None
    design_version: int
    document_count: int = 0
    evaluated_count: int = 0
    settings: list[str] = Field(default_factory=list)
    where_tried: WhereTriedOut
    relations: list[RelationOut] = Field(default_factory=list)
    abstract_only: bool = False
    is_entrant_with_no_documents: bool = False


class AmbitionBandOut(BaseModel):
    """One ambition band, a column of the reduced grid.

    Args:
        key: The stored value.
        label: The display label.
    """

    key: str
    label: str


class LonglistOut(BaseModel):
    """The `longlist` read model: the options grouped by theme, with their states.

    Args:
        run_id: The longlist component run the longlist came from.
        capability_run_id: The longlist walk that run belonged to.
        plan_version: The plan version the longlist was built from.
        built_from_plan_version: The same number, named for the plan
            document's "built from plan version N".
        current_plan_version: The task's current approved plan version.
        counts: The header counts.
        themes: The themes, in display order.
        unthemed_option_ids: Options in no theme (including options added
            since the build).
        options: Every option of the task, themed ones first in theme order.
        where_label: The words the `where` group is shown under (the plan's
            Where).
        lever_types: The lever-type list the options were typed against, in
            order (the grid's rows).
        ambition_bands: The ambition bands, in order (the grid's columns).
        taxonomy_version: The lever-type list version.
        depth_label: The depth label every longlist surface carries.
    """

    run_id: uuid.UUID
    capability_run_id: uuid.UUID | None = None
    plan_version: int
    built_from_plan_version: int
    current_plan_version: int | None = None
    counts: LonglistCountsOut
    themes: list[LonglistThemeOut] = Field(default_factory=list)
    unthemed_option_ids: list[uuid.UUID] = Field(default_factory=list)
    options: list[OptionSummaryOut] = Field(default_factory=list)
    where_label: str
    lever_types: list[str] = Field(default_factory=list)
    ambition_bands: list[AmbitionBandOut] = Field(default_factory=list)
    taxonomy_version: str | None = None
    depth_label: Literal["scoping pass"] = "scoping pass"


class EvidenceProfileOut(BaseModel):
    """An option's source-quality profile — what the evidence base holds so far.

    Every count is of documents, DOI-collapsed. Display only; never a verdict.

    Args:
        documents: Its documents.
        by_evidence_type: Documents per evidence type; "Unknown" and
            non-evidence documents are their own keys, "not rated" when unclassified.
        by_tier: Documents per quality tier label, "not rated" when unappraised.
        by_role: Documents per role.
        where_tried: Documents per where-tried group.
        populations: Populations its documents name, most frequent first.
        settings: Settings its documents name, most frequent first.
        outcomes: Outcomes its documents measure, most frequent first.
        flagged_not_stated: Documents that cover the intervention without
            stating the feature that defines this option.
        inherited_labels: Documents whose type and tier were read from a
            linked task.
        abstract_only: Documents read from an abstract only.
    """

    documents: int = 0
    by_evidence_type: dict[str, int] = Field(default_factory=dict)
    by_tier: dict[str, int] = Field(default_factory=dict)
    by_role: dict[str, int] = Field(default_factory=dict)
    where_tried: WhereTriedOut
    populations: list[str] = Field(default_factory=list)
    settings: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)
    flagged_not_stated: int = 0
    inherited_labels: int = 0
    abstract_only: int = 0


class JudgementOut(BaseModel):
    """One constraint judgement on the option's current design version.

    Args:
        constraint_id: The constraint's id (`req-N`, or a default screen:
            `relevant` · `distinct` · `in_scope`).
        constraint_text: The constraint, in words.
        verdict: Passes, breaks or cannot be checked.
        reason: Why.
    """

    constraint_id: str
    constraint_text: str
    verdict: JudgementVerdict
    reason: str


class GuessOut(BaseModel):
    """One reasoned guess on a preference: Policy Atlas's reasoning, not evidence.

    Args:
        constraint_id: The preference's id (`pref-N`).
        constraint_text: The preference, in words.
        guess: The guess, in words.
        leaning: Which way it leans.
    """

    constraint_id: str
    constraint_text: str
    guess: str
    leaning: GuessLeaning


class InScopeOut(BaseModel):
    """The in-scope check against the plan's evidence restriction.

    Args:
        restriction: The restriction, in words.
        in_scope_documents: Its documents that pass the restriction.
        documents: Its documents.
    """

    restriction: str
    in_scope_documents: int
    documents: int


class OptionDocumentOut(BaseModel):
    """One document behind an option ("Show the documents"), one per membership row.

    Args:
        task_source_snapshot_id: This task's document row, when the task holds one.
        title: The document's title.
        role: What the document does with the intervention.
        evidence_type: Its evidence type, when classified.
        tier: Its quality tier label, when appraised.
        design_feature_not_stated: It covers the intervention without stating
            the feature that defines this option.
        where_tried_group: Where it was studied, grouped against Where.
        source_task_id: The linked task the document or its labels came from,
            when inherited.
    """

    task_source_snapshot_id: uuid.UUID | None = None
    title: str
    role: OptionDocumentRole
    evidence_type: str | None = None
    tier: str | None = None
    design_feature_not_stated: bool = False
    where_tried_group: WhereTriedGroup
    source_task_id: uuid.UUID | None = None


class OptionOut(OptionSummaryOut):
    """The `option` read model: the option card, assembled (D15).

    Args:
        design: The specified design.
        design_features: The design's defining features.
        evidence: The source-quality profile.
        judgements: The constraint judgements on the current design version.
        guesses: The reasoned guesses on the current design version.
        transferability: "checked at assessment" when the plan carries the
            default transferability preference; `null` otherwise.
        in_scope: The in-scope check, when the plan restricts the evidence.
        documents: The documents behind it, one per membership row.
        run_id: The longlist component run its coverage came from; `null`
            before a longlist is built.
        capability_run_id: The longlist walk that run belonged to.
        plan_version: The plan version that longlist was built from.
        where_label: The words the `where` group is shown under.
        depth_label: The depth label every longlist surface carries.
    """

    design: OptionDesignOut
    design_features: list[str] = Field(default_factory=list)
    evidence: EvidenceProfileOut
    judgements: list[JudgementOut] = Field(default_factory=list)
    guesses: list[GuessOut] = Field(default_factory=list)
    transferability: Literal["checked at assessment"] | None = None
    in_scope: InScopeOut | None = None
    documents: list[OptionDocumentOut] = Field(default_factory=list)
    run_id: uuid.UUID | None = None
    capability_run_id: uuid.UUID | None = None
    plan_version: int | None = None
    where_label: str
    depth_label: Literal["scoping pass"] = "scoping pass"


class OptionAddIn(BaseModel):
    """Add an option by hand: the user's words (the button's path, D13).

    Args:
        text: The option, in the user's words.
    """

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=OPTION_TEXT_MAX)


class OptionExcludeIn(BaseModel):
    """Exclude an option, with the user's reason.

    Args:
        reason: Why, in the user's words.
    """

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=OPTION_TEXT_MAX)


class OptionIncludeIn(BaseModel):
    """Include an option again, optionally with the user's reason.

    Args:
        reason: Why, in the user's words.
    """

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=OPTION_TEXT_MAX)


class OptionAddedOut(BaseModel):
    """An option added by hand, and the option search it opened.

    Args:
        option: The new option's card.
        opened_run: The option search (a walk with no parent) it opened.
    """

    option: OptionOut
    opened_run: LatestRun
