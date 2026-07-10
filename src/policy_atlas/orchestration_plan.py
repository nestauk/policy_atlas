"""Orchestration-plan model and deterministic chain composer.

The orchestration plan is the approved user-facing run proposal. This module
keeps it fail-closed and compiles it into the fixed EB chain shape without
executing any component or widening any existing runtime directive grammar.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal, Self, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from policy_atlas.plan import COMPONENT_REGISTRY
from policy_atlas.schema import DIRECTIVE_STRING_MAX
from policy_atlas.screen import CRITERIA_LIST_MAX, _compose_screen_intent
from policy_atlas.screen_prompt import SCREEN_INTENT_MAX

BackendScope = Literal["academic_only", "grey_lit_only", "both"]
SearchEffort = Literal["rapid", "standard", "deep"]
AnalysisDepth = Literal["landscape", "standard", "deep"]
DiscretionaryComponent = Literal[
    "characterise",
    "screen_stage2",
    "select",
    "extract",
    "group",
]
GroupingFacet = Literal["intervention", "outcome", "population"]
SteeringMode = Literal["frequent", "moderate", "minimal", "unattended"]
SteerAction = Literal["proceed_flag", "stop"]

PUBLISHER_COUNTRY_MAX = 100

# Steer points a plan may pre-declare defaults for (steering.py's
# DEEPENING_SELECTION_STEER_POINT; the registry lives here so plan
# validation stays fail-closed without an import cycle).
STEER_POINTS: tuple[str, ...] = ("deepening_selection",)

SPINE: tuple[str, ...] = (
    "acquire",
    "screen",
    "classify",
    "appraise",
    "ingest_full_text",
    "synthesise",
)
DISCRETIONARY_COMPONENTS: tuple[DiscretionaryComponent, ...] = (
    "characterise",
    "screen_stage2",
    "select",
    "extract",
    "group",
)
DEEP_CHAIN_COMPONENTS: frozenset[DiscretionaryComponent] = frozenset(
    ("select", "extract", "group")
)

SEARCH_EFFORT_DIRECTIVES: dict[SearchEffort, dict[str, SearchEffort]] = {
    "rapid": {"depth": "rapid"},
    "standard": {"depth": "standard"},
    "deep": {"depth": "deep"},
}


class AnalysisDepthDirective(TypedDict):
    """Depth-row flags compiled by orchestration, not by component code."""

    screen_stage2: bool
    characterise: bool
    deep_chain: bool
    selection_budget: int | None


ANALYSIS_DEPTH_TABLE: dict[AnalysisDepth, AnalysisDepthDirective] = {
    "landscape": {
        "screen_stage2": False,
        "characterise": True,
        "deep_chain": False,
        "selection_budget": None,
    },
    "standard": {
        "screen_stage2": True,
        "characterise": True,
        "deep_chain": True,
        "selection_budget": 10,
    },
    "deep": {
        "screen_stage2": True,
        "characterise": True,
        "deep_chain": True,
        "selection_budget": 25,
    },
}

NAMED_PAIRINGS: dict[str, tuple[SearchEffort, AnalysisDepth]] = {
    "lighter": ("rapid", "landscape"),
    "standard": ("standard", "standard"),
    "deeper": ("deep", "deep"),
}

# Display bands are seeded from measured anchors, not from the target comments.
# 017 live check (2026-07-10, heat-pump question, standard x standard, budget
# 10, 22 full texts): acquire 21s + screen 63s + classify 36s + appraise 0.1s +
# ingest 107s + stage2 47s + characterise 53s + select 37s+38s + extract 393s +
# group 569s + synthesise 1047s = ~40 min end to end — the standard-depth rows
# below are seeded from that run. Landscape rows keep the 016 anchors (acquire
# 24s, screen 36s, ingest 134.8s; landscape-profile synthesis unmeasured live);
# deep-depth rows keep the demo deep prior (~95 min) + 015's full search
# episode (343s). Targets remain calibration notes only (lighter <= ~10 min,
# standard ~15-30 min, deeper ~90 min); the standard target-vs-measured gap
# (~40 min measured) is the recorded depth-seam calibration item for 018/eval.
TIME_BANDS: dict[tuple[SearchEffort, AnalysisDepth], str] = {
    ("rapid", "landscape"): "~10-15 min",
    ("standard", "landscape"): "~15-20 min",
    ("deep", "landscape"): "~20-25 min",
    ("rapid", "standard"): "~30-45 min",
    ("standard", "standard"): "~30-45 min",
    ("deep", "standard"): "~35-50 min",
    ("rapid", "deep"): "~75-90 min",
    ("standard", "deep"): "~80-95 min",
    ("deep", "deep"): "~90-100 min",
}

_DISCRETIONARY_COMPONENT_SET = set(DISCRETIONARY_COMPONENTS)
_REGISTRY_COMPONENT_BY_STEP: dict[str, str] = {
    "acquire": "acquire",
    "screen": "screen",
    "classify": "classify",
    "appraise": "appraise",
    "ingest_full_text": "ingest_full_text",
    "screen_stage2": "screen",
    "characterise": "characterise",
    "select": "select",
    "extract": "extract",
    "group": "group",
    "synthesise": "synthesise",
}
_REFERENCE_RULES: dict[str, str] = {
    "select": "characterisation_run_id <- characterise",
    "extract": "selection_run_id <- select",
    "group": "extraction_run_id <- extract",
    "synthesise": "deepest_successful_reference",
}


def _validate_iso_date(value: str, *, field_name: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid YYYY-MM-DD ISO date") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field_name} must be a YYYY-MM-DD ISO date")
    return value


def _require_clean_string(value: str, *, field_name: str) -> str:
    if not value.strip() or value != value.strip():
        raise ValueError(f"{field_name} must be a non-empty string without outer whitespace")
    return value


def _enabled_components(depth: AnalysisDepth) -> set[DiscretionaryComponent]:
    settings = ANALYSIS_DEPTH_TABLE[depth]
    enabled: set[DiscretionaryComponent] = set()
    if settings["screen_stage2"]:
        enabled.add("screen_stage2")
    if settings["characterise"]:
        enabled.add("characterise")
    if settings["deep_chain"]:
        enabled.update(("select", "extract", "group"))
    return enabled


def _validate_registry() -> None:
    missing = sorted(set(_REGISTRY_COMPONENT_BY_STEP.values()) - set(COMPONENT_REGISTRY))
    if missing:
        raise ValueError(f"orchestration references unknown registry component(s): {missing}")


def _derive_expected_artefact_shape(
    components: set[DiscretionaryComponent],
) -> str:
    if "extract" in components and "group" in components:
        return "facet-organised synthesis over extracted findings"
    if "characterise" in components and not components.intersection(DEEP_CHAIN_COMPONENTS):
        return "landscape coverage, themes and gaps"
    return "grounded answer over the screened corpus"


class ScopeConstraints(BaseModel):
    """Search-scope constraints compiled into the search filter grammar.

    Args:
        published_after: Optional lower publication-date bound as ``YYYY-MM-DD``.
        published_before: Optional upper publication-date bound as ``YYYY-MM-DD``.
        publisher_country: Optional Overton publisher-country filter.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    published_after: str | None = None
    published_before: str | None = None
    publisher_country: str | None = None

    @field_validator("published_after", "published_before")
    @classmethod
    def validate_date(cls, value: str | None, info: Any) -> str | None:
        """Validate optional ISO-date fields.

        Args:
            value: Candidate date string, or ``None``.
            info: Pydantic field metadata.

        Returns:
            The validated date string, or ``None``.

        Raises:
            ValueError: If the date is not an exact ``YYYY-MM-DD`` ISO date.
        """
        if value is None:
            return None
        return _validate_iso_date(value, field_name=info.field_name)

    @field_validator("publisher_country")
    @classmethod
    def validate_publisher_country(cls, value: str | None) -> str | None:
        """Validate the optional publisher-country filter.

        Args:
            value: Candidate publisher-country string, or ``None``.

        Returns:
            The validated country string, or ``None``.

        Raises:
            ValueError: If the value is empty or padded with whitespace.
        """
        if value is None:
            return None
        value = _require_clean_string(value, field_name="publisher_country")
        if len(value) > PUBLISHER_COUNTRY_MAX:
            raise ValueError(
                f"publisher_country must be at most {PUBLISHER_COUNTRY_MAX} characters"
            )
        if not all(ch.isalpha() or ch in " -'" for ch in value):
            raise ValueError(
                "publisher_country must contain only letters, spaces, hyphens or apostrophes"
            )
        return value

    @model_validator(mode="after")
    def validate_date_window(self) -> Self:
        """Validate chronological ordering for the optional recency window.

        Returns:
            The validated model.

        Raises:
            ValueError: If ``published_after`` is later than ``published_before``.
        """
        if (
            self.published_after is not None
            and self.published_before is not None
            and date.fromisoformat(self.published_after) > date.fromisoformat(self.published_before)
        ):
            raise ValueError("published_after must not be later than published_before")
        return self

    def to_filters(self) -> dict[str, dict[str, str]]:
        """Compile constraints into search-loop two-level filters.

        Returns:
            A ``filters`` object with recency under ``shared`` and publisher
            geography under ``overton``. Empty constraints compile to ``{}``.
        """
        filters: dict[str, dict[str, str]] = {}
        shared: dict[str, str] = {}
        if self.published_after is not None:
            shared["published_after"] = self.published_after
        if self.published_before is not None:
            shared["published_before"] = self.published_before
        if shared:
            filters["shared"] = shared
        if self.publisher_country is not None:
            filters["overton"] = {"publisher_country": self.publisher_country}
        return filters


class SteerPointDefault(BaseModel):
    """Pre-declared default action for a steering point.

    Args:
        steer_point: Name of the steer point the rule applies to.
        action: Pre-declarable action. Runtime-data-specific actions are not
            representable in this schema.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    steer_point: str
    action: SteerAction

    @field_validator("steer_point")
    @classmethod
    def validate_steer_point(cls, value: str) -> str:
        """Validate the steer-point name.

        Args:
            value: Candidate steer-point name.

        Returns:
            The validated steer-point name.

        Raises:
            ValueError: If the name is not a known steer point.
        """
        value = _require_clean_string(value, field_name="steer_point")
        if value not in STEER_POINTS:
            raise ValueError(f"steer_point must be one of {sorted(STEER_POINTS)}")
        return value


class OrchestrationPlan(BaseModel):
    """Approved orchestration proposal compiled into an EB component chain.

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
        component_rationale: Visible intent-fit rationale keyed by discretionary
            component.
        grouping_facet: Optional grouping facet, valid only when ``group`` runs.
        steering_mode: Steering mode for the later runner.
        steer_point_defaults: Pre-declared steering defaults.
        expected_artefact_shape: Deterministic forecast derived from components.
        assumptions: Visible assumptions and open guesses.
        time_band: Deterministic wall-clock band derived from the two axes.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    title: str
    question: str
    scoping_notes: list[str] = Field(default_factory=list)
    screening_criteria: list[str] = Field(default_factory=list)
    backend_scope: BackendScope
    scope_constraints: ScopeConstraints = Field(default_factory=ScopeConstraints)
    search_effort: SearchEffort
    analysis_depth: AnalysisDepth
    components: list[DiscretionaryComponent] = Field(default_factory=list)
    component_rationale: dict[str, str] = Field(default_factory=dict)
    grouping_facet: GroupingFacet | None = None
    steering_mode: SteeringMode
    steer_point_defaults: list[SteerPointDefault] = Field(default_factory=list)
    expected_artefact_shape: str = ""
    assumptions: list[str] = Field(default_factory=list)
    time_band: str = ""

    @field_validator("title", "question")
    @classmethod
    def validate_required_text(cls, value: str, info: Any) -> str:
        """Validate required text fields.

        Args:
            value: Candidate field value.
            info: Pydantic field metadata.

        Returns:
            The validated string.

        Raises:
            ValueError: If the string is empty or padded with whitespace.
        """
        return _require_clean_string(value, field_name=info.field_name)

    @field_validator("scoping_notes", "screening_criteria", "assumptions")
    @classmethod
    def validate_text_lists(cls, values: list[str], info: Any) -> list[str]:
        """Validate plan text-list fields.

        Args:
            values: Candidate list of strings.
            info: Pydantic field metadata.

        Returns:
            The validated list.

        Raises:
            ValueError: If any item is empty or padded with whitespace, or —
                for ``screening_criteria`` — breaches the screen directive
                grammar's caps (the compile target must accept every valid
                plan by construction; live check 017 caught a >200-char
                criterion validating here and rejecting at the screen
                boundary).
        """
        if info.field_name == "screening_criteria":
            if len(values) > CRITERIA_LIST_MAX:
                raise ValueError(
                    f"screening_criteria must have at most {CRITERIA_LIST_MAX} entries"
                )
            for value in values:
                if len(value) > DIRECTIVE_STRING_MAX:
                    raise ValueError(
                        "screening_criteria entries must be at most "
                        f"{DIRECTIVE_STRING_MAX} characters"
                    )
        return [_require_clean_string(value, field_name=info.field_name) for value in values]

    @field_validator("components")
    @classmethod
    def validate_unique_components(
        cls,
        values: list[DiscretionaryComponent],
    ) -> list[DiscretionaryComponent]:
        """Validate that discretionary components are not repeated.

        Args:
            values: Candidate discretionary component list.

        Returns:
            The validated component list.

        Raises:
            ValueError: If a component appears more than once.
        """
        if len(set(values)) != len(values):
            raise ValueError("components must not contain duplicates")
        return values

    @field_validator("component_rationale")
    @classmethod
    def validate_component_rationale(cls, value: dict[str, str]) -> dict[str, str]:
        """Validate visible intent-fit rationale keys and text.

        Args:
            value: Rationale keyed by discretionary component.

        Returns:
            The validated rationale mapping.

        Raises:
            ValueError: If a key is not a discretionary component or text is
                empty/padded.
        """
        for key, rationale in value.items():
            if key not in _DISCRETIONARY_COMPONENT_SET:
                raise ValueError(f"component_rationale has unknown component {key!r}")
            _require_clean_string(rationale, field_name=f"component_rationale[{key}]")
        return value

    @model_validator(mode="after")
    def validate_component_structure_and_derivations(self) -> Self:
        """Validate depth/dependency rules and fill derived fields.

        Returns:
            The validated model with deterministic derived fields populated.

        Raises:
            ValueError: If a component is disabled by the selected depth, a
                dependency is missing, a grouping facet is unattached, or a
                supplied derived field does not match the deterministic value.
        """
        _validate_registry()
        component_set = set(self.components)
        enabled = _enabled_components(self.analysis_depth)
        disabled = sorted(component_set - enabled)
        if disabled:
            raise ValueError(
                f"components not enabled by analysis_depth {self.analysis_depth!r}: {disabled}"
            )
        if "select" in component_set and "characterise" not in component_set:
            raise ValueError("select requires characterise in components")
        if "extract" in component_set and "select" not in component_set:
            raise ValueError("extract requires select in components")
        if "group" in component_set and "extract" not in component_set:
            raise ValueError("group requires extract in components")
        if self.grouping_facet is not None and "group" not in component_set:
            raise ValueError("grouping_facet requires group in components")

        expected_shape = _derive_expected_artefact_shape(component_set)
        if self.expected_artefact_shape and self.expected_artefact_shape != expected_shape:
            raise ValueError("expected_artefact_shape does not match the composed chain")
        self.expected_artefact_shape = expected_shape

        expected_time_band = TIME_BANDS[(self.search_effort, self.analysis_depth)]
        if self.time_band and self.time_band != expected_time_band:
            raise ValueError("time_band does not match search_effort and analysis_depth")
        self.time_band = expected_time_band

        if (
            self.scope_constraints.publisher_country is not None
            and self.backend_scope == "academic_only"
        ):
            raise ValueError(
                "publisher_country filters the grey-literature backend, which "
                "backend_scope 'academic_only' excludes"
            )

        # Compile-target parity for the screen prompt: the composed intent
        # (question + criteria block, via the real composer) must fit the
        # prompt-assembly cap, or criteria would be silently truncated away
        # while the plan row claims they governed screening.
        composed_intent = _compose_screen_intent(self.question, self.screening_criteria)
        if len(composed_intent) > SCREEN_INTENT_MAX:
            raise ValueError(
                f"question plus screening_criteria compose to {len(composed_intent)} "
                f"characters; the screen prompt caps its intent input at "
                f"{SCREEN_INTENT_MAX}, so later criteria would be silently dropped"
            )
        return self


class ComponentStep(BaseModel):
    """One deterministic component invocation in a composed chain.

    Args:
        component: Orchestration component step name.
        directive_delta: Context directive delta for the component.
        reference_rule: Optional reference-threading rule for the runner.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    component: str
    directive_delta: dict[str, Any] = Field(default_factory=dict)
    reference_rule: str | None = None


class ComposedChain(BaseModel):
    """Ordered composed chain emitted by ``compose``.

    Args:
        steps: Ordered component steps.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    steps: list[ComponentStep]

    def __len__(self) -> int:
        """Return the number of composed steps.

        Returns:
            The chain length.
        """
        return len(self.steps)

    @property
    def components(self) -> list[str]:
        """Return component names in execution order.

        Returns:
            Ordered component names.
        """
        return [step.component for step in self.steps]


def _directive_delta(component: str, plan: OrchestrationPlan) -> dict[str, Any]:
    if component == "acquire":
        search: dict[str, Any] = dict(SEARCH_EFFORT_DIRECTIVES[plan.search_effort])
        filters = plan.scope_constraints.to_filters()
        if filters:
            search["filters"] = filters
        return {"search": search}
    if component == "screen" and plan.screening_criteria:
        return {"screening": {"criteria": list(plan.screening_criteria)}}
    if component == "screen_stage2":
        screening: dict[str, Any] = {"stage": 2}
        if plan.screening_criteria:
            screening["criteria"] = list(plan.screening_criteria)
        return {"screening": screening}
    if component == "select":
        budget = ANALYSIS_DEPTH_TABLE[plan.analysis_depth]["selection_budget"]
        if budget is None:
            raise ValueError("select cannot compile without a selection budget")
        return {"selection": {"budget": budget}}
    if component == "group" and plan.grouping_facet is not None:
        return {"grouping": {"facet": plan.grouping_facet}}
    return {}


def compose(plan: OrchestrationPlan) -> ComposedChain:
    """Compose an approved orchestration plan into a fixed EB chain.

    Args:
        plan: Validated orchestration plan.

    Returns:
        A composed chain whose mandatory spine is present in order and whose
        discretionary steps are inserted only at their structural positions.

    Raises:
        ValueError: If the component registry no longer contains a referenced
            underlying component.
    """
    _validate_registry()
    selected = set(plan.components)
    ordered_components: list[str] = [
        "acquire",
        "screen",
        "classify",
        "appraise",
        "ingest_full_text",
    ]
    if "screen_stage2" in selected:
        ordered_components.append("screen_stage2")
    if "characterise" in selected:
        ordered_components.append("characterise")
    if "select" in selected:
        ordered_components.append("select")
    if "extract" in selected:
        ordered_components.append("extract")
    if "group" in selected:
        ordered_components.append("group")
    ordered_components.append("synthesise")

    return ComposedChain(
        steps=[
            ComponentStep(
                component=component,
                directive_delta=_directive_delta(component, plan),
                reference_rule=_REFERENCE_RULES.get(component),
            )
            for component in ordered_components
        ]
    )
