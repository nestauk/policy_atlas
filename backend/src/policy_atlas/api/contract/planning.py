"""Planning-turn and plan-draft contract.

`PlanDraft` mirrors the runtime `OrchestrationPlan`
(`policy_atlas.runtime.orchestration_plan`) field-by-field, but this package
never imports that module — the contract is standalone. The enum
vocabularies below (`BackendScope`, `SearchEffort`, `AnalysisDepth`,
`SteeringMode`, `GroupingFacet`, `ExtractProfile`,
`DiscretionaryComponent`) are copies of the runtime's string values, pinned
here independently; a guard test should keep the two from drifting.

Every field on `PlanDraft` except `steps`/`ready` may be `None`/absent while
the planner conversation is still converging (spec § Planning turns) — never
trust an optional field as "finalised".
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: Search backend scope. Mirrors `orchestration_plan.BackendScope`.
PLANNING_MESSAGE_MAX = 10_000

BackendScope = Literal["academic_only", "grey_lit_only", "both"]

#: Acquisition effort rung. Mirrors `orchestration_plan.SearchEffort`.
SearchEffort = Literal["rapid", "standard", "deep"]

#: Analysis component/budget rung. Mirrors `orchestration_plan.AnalysisDepth`.
AnalysisDepth = Literal["landscape", "standard", "deep"]

#: Finding profile short name. Mirrors `orchestration_plan.ExtractProfile`.
ExtractProfile = Literal["iof", "icf"]

#: Discretionary chain component. Mirrors `orchestration_plan.DiscretionaryComponent`.
DiscretionaryComponent = Literal[
    "characterise",
    "screen_full",
    "select",
    "extract",
    "group",
]

#: Grouping facet. Mirrors `orchestration_plan.GroupingFacet`.
GroupingFacet = Literal[
    "intervention",
    "outcome",
    "population",
    "barrier_theme",
    "enabler_theme",
    "mechanism_theme",
]

#: Steering mode. Mirrors `orchestration_plan.SteeringMode`.
SteeringMode = Literal["frequent", "moderate", "minimal", "unattended"]

# Mirrors ``sse.StageKey`` without importing it: the SSE module itself carries
# ``PlanDraft`` frames, so a direct import would make the standalone contract
# package circular.
PlanStageKey = Literal[
    "acquire",
    "screen",
    "classify",
    "appraise",
    "characterise",
    "select",
    "extract",
    "group",
    "synthesise",
]

#: Country-group membership provenance. Mirrors
#: `orchestration_plan.CountryGroupAuthorship`.
CountryGroupAuthorship = Literal["pinned-table", "planner-proposed", "user-amended"]


class CountryGroupDraft(BaseModel):
    """Draft mirror of the runtime `CountryGroup`.

    Args:
        label: Pinned Tier-1 label, or a user/planner label for an explicit
            Tier-2 country list. `None` while undecided.
        countries: Explicit ISO-3166 alpha-2 country list for Tier-2 groups.
        authorship: Provenance of the group membership, when settled.
    """

    label: str | None = None
    countries: list[str] | None = None
    authorship: CountryGroupAuthorship | None = None


class ScopeConstraintsDraft(BaseModel):
    """Draft mirror of the runtime `ScopeConstraints`.

    Args:
        published_after: Optional lower publication-date bound (`YYYY-MM-DD`).
        published_before: Optional upper publication-date bound (`YYYY-MM-DD`).
        publisher_country: Optional Overton publisher-country filter.
        author_affiliation_countries: Optional OpenAlex author-affiliation
            country filter (2-letter alpha codes).
        country_group: Optional named group applied to both search backends.
    """

    published_after: str | None = None
    published_before: str | None = None
    publisher_country: str | None = None
    author_affiliation_countries: list[str] | None = None
    country_group: CountryGroupDraft | None = None


class PlanStep(BaseModel):
    """One user-visible step in the composed chain, for progress display.

    Args:
        label: Short user-visible step label (presentation; may change).
        blurb: Longer user-visible step description (presentation; may
            change).
        stage: Composed-chain stage name the step corresponds to.
    """

    label: str
    blurb: str
    stage: PlanStageKey


class PlanDraft(BaseModel):
    """Draft or approved orchestration plan, as surfaced to the client.

    Mirrors the runtime `OrchestrationPlan` field-by-field. Every field
    except `steps`/`ready` may be `None`/absent while drafting.

    Args:
        title: Short user-visible title for the run.
        question: Refined evidence question.
        scoping_notes: User-expressed scoping notes.
        screening_criteria: Visible inclusion/exclusion criteria for screening.
        backend_scope: Search backend scope.
        scope_constraints: Optional recency and publisher-geography constraints.
        search_effort: Acquisition effort rung.
        analysis_depth: Analysis component and budget rung.
        components: Discretionary orchestration components only.
        component_rationale: Visible intent-fit rationale keyed by
            discretionary component.
        grouping_facets: Optional grouping facets, valid only when `group`
            runs.
        extract_profiles: Optional finding profile short names, valid only
            when `extract` runs.
        steering_mode: Steering mode for the run.
        assumptions: Visible assumptions and open guesses.
        expected_artefact_shape: Deterministic forecast derived from components.
        time_band: Deterministic wall-clock band derived from the two axes.
        section_budget: Optional future synthesis cap for ordinary sections.
        steps: The composed chain, presentation-labelled, in execution order.
        ready: Whether the draft has validated fail-closed into an
            executable plan.
    """

    title: str | None = None
    question: str | None = None
    scoping_notes: list[str] | None = None
    screening_criteria: list[str] | None = None
    backend_scope: BackendScope | None = None
    scope_constraints: ScopeConstraintsDraft | None = None
    search_effort: SearchEffort | None = None
    analysis_depth: AnalysisDepth | None = None
    components: list[DiscretionaryComponent] | None = None
    component_rationale: dict[str, str] | None = None
    grouping_facets: list[GroupingFacet] | None = None
    extract_profiles: list[ExtractProfile] | None = None
    steering_mode: SteeringMode | None = None
    assumptions: list[str] | None = None
    expected_artefact_shape: str | None = None
    time_band: str | None = None
    section_budget: int | None = Field(default=None, ge=2, le=8)
    steps: list[PlanStep] = Field(default_factory=list)
    ready: bool = False


class PlanningTurnCreate(BaseModel):
    """Inbound body for `POST /api/v1/projects/{id}/planning-turns`.

    Args:
        message: The user's chat message for this planner turn.
        client_turn_id: Caller-minted UUID making double-submit idempotent —
            resubmitting the same `client_turn_id` returns the same turn
            rather than re-running the planner.
    """

    model_config = ConfigDict(extra="forbid")

    # Turns are durable and every prior message re-enters each planner call
    # (rehydration), so an unbounded message inflates storage AND every future
    # turn's prompt forever (security review, 2026-07-29).
    message: str = Field(min_length=1, max_length=PLANNING_MESSAGE_MAX)
    client_turn_id: uuid.UUID


class PartOptionOut(BaseModel):
    """One selectable option on a sequential planning part.

    Args:
        id: Stable option identifier within the part.
        label: Short user-visible option label.
        sub: Optional outcome and time-band sub-label.
        primary: Whether this is the single recommended option.
        reason: Optional explanation for the recommendation.
    """

    id: str
    label: str
    sub: str | None = None
    primary: bool
    reason: str | None = None


class PartChipOut(BaseModel):
    """One typed, editable chip attached to a planning part.

    Args:
        label: Short user-visible chip label.
        kind: Editor type for the chip value.
        value: Machine-readable value consumed by that editor.
    """

    label: str
    kind: Literal["text", "date_range", "country_list"]
    value: str


class PartProposalOut(BaseModel):
    """One structured proposal in the sequential planning conversation.

    Args:
        id: The proposed planning part.
        step_label: User-visible position and context for the proposal.
        title: Plain-language proposal heading.
        body: Optional supporting explanation.
        chips: Optional typed scope chips.
        options: The available response options.
    """

    id: str
    step_label: str
    title: str
    body: str | None = None
    chips: list[PartChipOut] | None = None
    options: list[PartOptionOut]


class PlanningTurnOut(BaseModel):
    """Response body for one planner turn.

    Args:
        reply: The planner's conversational reply for this turn.
        plan: The full current draft plan.
        suggestions: The planner's suggested answers to its clarifying
            question, rendered as tappable quick replies. Empty when none.
        part: Structured sequential-planning proposal, when this turn carries one.
    """

    reply: str
    plan: PlanDraft
    suggestions: list[str] = Field(default_factory=list)
    part: PartProposalOut | None = None


class PlanningTranscriptTurnOut(BaseModel):
    """One durable planning-transcript turn shown in chronological order.

    Args:
        turn_index: Monotonic per-project conversation coordinate.
        client_turn_id: The caller's idempotency key for this turn — returned
            so a reloaded client can retry its own incomplete latest turn.
        user_message: Submitted user message.
        reply: Planner reply, absent until a pending turn completes.
        suggestions: Planner quick-reply suggestions, if the turn completed.
        part: Structured sequential-planning proposal, absent for legacy turns.
        status: Durable execution state for this turn.
        created_at: Receipt timestamp, retained as display metadata.
        completed_at: Terminal timestamp, absent while still pending.
    """

    turn_index: int
    client_turn_id: uuid.UUID
    user_message: str
    reply: str | None
    suggestions: list[str] = Field(default_factory=list)
    part: PartProposalOut | None = None
    status: Literal["pending", "completed", "failed"]
    created_at: datetime
    completed_at: datetime | None


class PlanOut(BaseModel):
    """Response body for `GET /api/v1/projects/{id}/plan`.

    Args:
        plan: The current plan (draft or approved).
        version: Plan row version.
        status: Plan status (e.g. `draft`, `approved`).
    """

    plan: PlanDraft
    version: int
    status: str
