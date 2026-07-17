"""Orchestration-plan model and deterministic chain composer.

The orchestration plan is the approved user-facing run proposal. This module
keeps it fail-closed and compiles it into the fixed EB chain shape without
executing any component or widening any existing runtime directive grammar.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal, Self, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from policy_atlas.core.schema import DIRECTIVE_STRING_MAX
from policy_atlas.evidence_base.assess.screen import (
    CRITERIA_LIST_MAX,
    ScreenDirectiveError,
    _compose_screen_intent,
)
from policy_atlas.evidence_base.assess.screen_prompt import SCREEN_INTENT_MAX
from policy_atlas.evidence_base.extract.extract import KNOWN_PROFILE_IDS
from policy_atlas.evidence_base.sourcing.country_filters import (
    TIER1_GROUPS,
    SearchDirectiveError,
    expand_tier1,
    overton_display_names,
    validate_iso_alpha2,
    validate_overton_display_name,
)
from policy_atlas.runtime.run_spec import COMPONENT_REGISTRY

BackendScope = Literal["academic_only", "grey_lit_only", "both"]
SearchEffort = Literal["rapid", "standard", "deep"]
AnalysisDepth = Literal["landscape", "standard", "deep"]
ExtractProfile = Literal["iof", "icf"]
DiscretionaryComponent = Literal[
    "characterise",
    "screen_full",
    "select",
    "extract",
    "group",
]
GroupingFacet = Literal[
    "intervention",
    "outcome",
    "population",
    "barrier_theme",
    "enabler_theme",
    "mechanism_theme",
]
SteeringMode = Literal["frequent", "moderate", "minimal", "unattended"]
SteerAction = Literal["proceed_flag", "stop"]
CountryGroupAuthorship = Literal["pinned-table", "planner-proposed", "user-amended"]

PUBLISHER_COUNTRY_MAX = 100

# Steer points a plan may pre-declare standing defaults for. The four names are
# the steering lattice points (steering.py's SEARCH_EXCEPTION /
# EVIDENCE_BASE_COVERAGE / DEEPENING_SELECTION / SYNTHESIS_SHAPE); the registry
# lives here as literal strings so plan validation stays fail-closed without an
# import cycle (steering.py imports this module). A guard test pins this tuple to
# steering.LATTICE_POINTS so the two never drift.
STEER_POINTS: tuple[str, ...] = (
    "search_exception",
    "evidence_base_coverage",
    "deepening_selection",
    "synthesis_shape",
)

SPINE: tuple[str, ...] = (
    "acquire",
    "screen_abstract",
    "classify",
    "appraise",
    "ingest_full_text",
    "synthesise",
)
DISCRETIONARY_COMPONENTS: tuple[DiscretionaryComponent, ...] = (
    "characterise",
    "screen_full",
    "select",
    "extract",
    "group",
)
ALL_STEPS: tuple[str, ...] = SPINE + DISCRETIONARY_COMPONENTS
DEEP_CHAIN_COMPONENTS: frozenset[DiscretionaryComponent] = frozenset(
    ("select", "extract", "group")
)
DEEP_GROUPING_FACETS: tuple[GroupingFacet, ...] = (
    "intervention",
    "outcome",
    "barrier_theme",
    "enabler_theme",
    "mechanism_theme",
)

SEARCH_EFFORT_DIRECTIVES: dict[SearchEffort, dict[str, SearchEffort]] = {
    "rapid": {"depth": "rapid"},
    "standard": {"depth": "standard"},
    "deep": {"depth": "deep"},
}

EXTRACT_PROFILE_IDS: dict[ExtractProfile, str] = {
    "iof": "eb_iof_base_v1",
    "icf": "eb_icf_base_v1",
}

if tuple(EXTRACT_PROFILE_IDS.values()) != KNOWN_PROFILE_IDS:
    raise AssertionError("EXTRACT_PROFILE_IDS values must match extract.KNOWN_PROFILE_IDS")


class AnalysisDepthDirective(TypedDict):
    """Depth-row flags compiled by orchestration, not by component code."""

    screen_full: bool
    characterise: bool
    select: bool
    findings_chain: bool
    selection_budget: int | None
    extract_profiles: tuple[ExtractProfile, ...] | None
    grouping_facets: tuple[GroupingFacet, ...] | None


ANALYSIS_DEPTH_TABLE: dict[AnalysisDepth, AnalysisDepthDirective] = {
    "landscape": {
        "screen_full": False,
        "characterise": True,
        "select": False,
        "findings_chain": False,
        "selection_budget": None,
        "extract_profiles": None,
        "grouping_facets": None,
    },
    "standard": {
        # 019 select-at-standard regrade: select now runs at standard too, so
        # synthesise gets the SELECTION_PRIOR_BOOST retrieval prior and
        # origin: selected|unselected_screened citation accounting over the
        # full-text corpus, without the findings-extraction layer (extract/
        # group stay deep-only).
        "screen_full": True,
        "characterise": True,
        "select": True,
        "findings_chain": False,
        # Plan-pinned standard selection budget; calibration is eval-slice
        # work (pre-eval-slice-plan.md), not decided here.
        "selection_budget": 15,
        "extract_profiles": None,
        "grouping_facets": None,
    },
    "deep": {
        "screen_full": True,
        "characterise": True,
        "select": True,
        "findings_chain": True,
        "selection_budget": 25,
        "extract_profiles": ("iof", "icf"),
        "grouping_facets": DEEP_GROUPING_FACETS,
    },
}

# findings_chain (extract+group) is only ever meaningful once select has run —
# a depth row that buys the findings chain without buying select is an
# incoherent table entry, checked once at import time rather than re-derived
# at every compose() call.
for _depth, _settings in ANALYSIS_DEPTH_TABLE.items():
    if _settings["findings_chain"] and not _settings["select"]:
        raise AssertionError(
            f"ANALYSIS_DEPTH_TABLE[{_depth!r}]: findings_chain requires select"
        )
del _depth, _settings

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
    # Re-seeded from the 019 Phase E measured run (2026-07-12, heat-pump
    # question, standard x standard WITH select-at-standard, 58 docs acquired,
    # 20 full-text screened): 805 s ≈ 13.4 min end to end incl. the planner
    # turn — acquire 12s + screen_abstract 14s + classify 58s + appraise 0.1s
    # + ingest 76s + screen_full 6s + characterise 8s + select 5s +
    # synthesise 602s. Displayed-band-is-measured; synthesise dominates, so
    # the band widens with corpus size, not composition.
    ("standard", "standard"): "~10-20 min",
    ("deep", "standard"): "~35-50 min",
    ("rapid", "deep"): "~75-90 min",
    ("standard", "deep"): "~80-95 min",
    ("deep", "deep"): "~90-100 min",
}

_DISCRETIONARY_COMPONENT_SET = set(DISCRETIONARY_COMPONENTS)
# The screening harness component is keyed "screen" in COMPONENT_REGISTRY
# (plan.py) regardless of which plan-vocabulary step invokes it: both
# screen_abstract (mandatory spine, stage 1) and screen_full (discretionary,
# stage 2) dispatch to it. Every other step name is its own registry
# component, so a function replaces what was previously a mostly-identity
# dict (task 019 item 10b).
_SCREENING_STEPS = frozenset(("screen_abstract", "screen_full"))


def registry_component_for(step: str) -> str:
    """Map a composed orchestration step name to its harness registry component.

    Args:
        step: Composed orchestration step name (plan vocabulary).

    Returns:
        The ``COMPONENT_REGISTRY`` key that step dispatches to.
    """
    if step in _SCREENING_STEPS:
        return "screen"
    return step


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
    if settings["screen_full"]:
        enabled.add("screen_full")
    if settings["characterise"]:
        enabled.add("characterise")
    if settings["select"]:
        enabled.add("select")
    if settings["findings_chain"]:
        enabled.update(("extract", "group"))
    return enabled


def _validate_registry() -> None:
    missing = sorted(
        {registry_component_for(step) for step in ALL_STEPS} - set(COMPONENT_REGISTRY)
    )
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


class CountryGroup(BaseModel):
    """Named country group compiled into backend-specific search filters.

    Args:
        label: Pinned Tier-1 label, or a user/planner label for an explicit
            Tier-2 country list.
        countries: Explicit ISO-3166 alpha-2 country list for Tier-2 groups.
            Must be ``None`` for pinned Tier-1 labels.
        authorship: Deterministic provenance of the group membership.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    label: str
    countries: list[str] | None = None
    authorship: CountryGroupAuthorship

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        """Validate the group label.

        Args:
            value: Candidate group label.

        Returns:
            The validated label.

        Raises:
            ValueError: If the label is empty or padded with whitespace.
        """
        return _require_clean_string(value, field_name="country_group.label")

    @field_validator("countries")
    @classmethod
    def validate_countries(cls, value: list[str] | None) -> list[str] | None:
        """Validate explicit Tier-2 country membership.

        Args:
            value: Candidate country list, or ``None``.

        Returns:
            The validated list, normalised to upper-case, or ``None``.

        Raises:
            ValueError: If the list is empty, duplicated, too long, or contains
                a non-ISO-3166 alpha-2 code.
        """
        if value is None:
            return None
        if len(value) > 200:
            raise ValueError("country_group.countries must contain at most 200 codes")
        try:
            return validate_iso_alpha2(value)
        except SearchDirectiveError as exc:
            raise ValueError(f"country_group.countries {exc}") from exc

    @model_validator(mode="after")
    def validate_group_shape(self) -> Self:
        """Validate pinned-vs-explicit group shape and authorship.

        Returns:
            The validated group.

        Raises:
            ValueError: If a pinned group carries inline countries, a custom
                group omits countries, or authorship does not match the group
                source.
        """
        if self.label in TIER1_GROUPS:
            if self.countries is not None:
                raise ValueError("pinned country_group labels must not carry countries")
            if self.authorship != "pinned-table":
                raise ValueError("pinned country_group labels require authorship 'pinned-table'")
            return self
        if self.countries is None:
            raise ValueError("custom country_group labels require countries")
        if self.authorship == "pinned-table":
            raise ValueError("custom country_group labels cannot use authorship 'pinned-table'")
        return self


class ScopeConstraints(BaseModel):
    """Search-scope constraints compiled into the search filter grammar.

    Args:
        published_after: Optional lower publication-date bound as ``YYYY-MM-DD``.
        published_before: Optional upper publication-date bound as ``YYYY-MM-DD``.
        publisher_country: Optional Overton publisher-country filter.
        author_affiliation_countries: Optional OpenAlex author-affiliation
            country filter, as 2-letter alpha codes normalised to upper-case.
        country_group: Optional named group applied to both search backends.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    published_after: str | None = None
    published_before: str | None = None
    publisher_country: str | None = None
    author_affiliation_countries: list[str] | None = None
    country_group: CountryGroup | None = None

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
        try:
            return validate_overton_display_name(value, field_name="publisher_country")
        except SearchDirectiveError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("author_affiliation_countries")
    @classmethod
    def validate_author_affiliation_countries(
        cls, value: list[str] | None
    ) -> list[str] | None:
        """Validate the optional OpenAlex author-affiliation country filter.

        Args:
            value: Candidate list of 2-letter country codes, or ``None``.

        Returns:
            The validated list, normalised to upper-case, or ``None``.

        Raises:
            ValueError: If the list is empty, contains a non-2-letter or
                non-alphabetic entry, or contains duplicate entries.
        """
        if value is None:
            return None
        if not value:
            raise ValueError(
                "author_affiliation_countries must not be empty; omit the field instead"
            )
        try:
            return validate_iso_alpha2(value)
        except SearchDirectiveError as exc:
            raise ValueError(f"author_affiliation_countries {exc}") from exc

    @model_validator(mode="after")
    def validate_scope_shape(self) -> Self:
        """Validate cross-field scope rules.

        Returns:
            The validated model.

        Raises:
            ValueError: If ``published_after`` is later than ``published_before``.
            ValueError: If ``country_group`` is combined with single-country
                geography filters.
        """
        if (
            self.published_after is not None
            and self.published_before is not None
            and date.fromisoformat(self.published_after) > date.fromisoformat(self.published_before)
        ):
            raise ValueError("published_after must not be later than published_before")
        if self.country_group is not None and (
            self.publisher_country is not None
            or self.author_affiliation_countries is not None
        ):
            raise ValueError(
                "country_group is mutually exclusive with publisher_country "
                "and author_affiliation_countries"
            )
        return self

    def to_filters(self) -> dict[str, dict[str, Any]]:
        """Compile constraints into search-loop two-level filters.

        Returns:
            A ``filters`` object with recency under ``shared``, publisher
            geography under ``overton``, and author-affiliation geography
            under ``openalex``. Empty constraints compile to ``{}``.
        """
        filters: dict[str, dict[str, Any]] = {}
        shared: dict[str, str] = {}
        if self.published_after is not None:
            shared["published_after"] = self.published_after
        if self.published_before is not None:
            shared["published_before"] = self.published_before
        if shared:
            filters["shared"] = shared
        if self.country_group is not None:
            group = self.country_group
            if group.label in TIER1_GROUPS:
                countries = list(expand_tier1(group.label))
                filters["openalex"] = {"author_affiliation_countries": countries}
                filters["overton"] = {"publisher_region": group.label}
                return filters
            countries = group.countries or []
            filters["openalex"] = {"author_affiliation_countries": countries}
            filters["overton"] = {
                "source_country_post_filter": sorted(overton_display_names(countries)),
            }
            return filters
        if self.publisher_country is not None:
            filters["overton"] = {"publisher_country": self.publisher_country}
        if self.author_affiliation_countries is not None:
            filters["openalex"] = {
                "author_affiliation_countries": self.author_affiliation_countries
            }
        return filters


class SteerPointDefault(BaseModel):
    """Pre-declared standing-instruction rule for a steering lattice point.

    The two-field form (``steer_point`` + ``action``) is the task-017 shape and
    stays valid unchanged. Task 024 (Unattended = discretion-is-the-mode) widens
    it with an optional canonical ``option_id`` at that point and its compiled
    directive ``delta``, so a standing rule can pre-declare *which* option the
    Unattended walk applies — not merely proceed/stop. When present, the pair is
    validated fail-closed at plan-validation time (:func:`steering
    .validate_steer_point_default`): the option id must belong to the point's
    canonical vocabulary and the delta must compile through the component grammar;
    an option that requires user input whose delta supplies none is rejected.

    Args:
        steer_point: Lattice point the rule applies to (one of ``STEER_POINTS``).
        action: Pre-declarable action — ``proceed_flag`` or ``stop`` (a hard stop
            is always honoured; discretion can never override it).
        option_id: Optional canonical option id at the point (proceed_flag only).
        delta: Optional compiled directive delta for that option (proceed_flag
            only), validated against the point's option grammar.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    steer_point: str
    action: SteerAction
    option_id: str | None = None
    delta: dict[str, Any] | None = None

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

    @model_validator(mode="after")
    def validate_option_binding(self) -> Self:
        """Fail-closed validation of the optional option_id/delta binding.

        The check lives in steering.py (the option grammar and the per-point
        vocabulary are its concern) and is imported lazily here to avoid the
        import cycle (steering.py imports this module at load). A bare
        two-field rule (no option_id, no delta) skips it and stays valid.

        Returns:
            The validated model.

        Raises:
            ValueError: If option_id/delta are present on a stop rule, the option
                id is not canonical at the point, the delta does not compile, or a
                requires-user-input option's delta supplies no input.
        """
        if self.option_id is None and self.delta is None:
            return self
        from policy_atlas.runtime.steering import validate_steer_point_default

        validate_steer_point_default(
            steer_point=self.steer_point,
            action=self.action,
            option_id=self.option_id,
            delta=self.delta,
        )
        return self


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
        grouping_facets: Optional grouping facets, valid only when ``group`` runs.
        extract_profiles: Optional finding profile short names, valid only
            when ``extract`` runs. ``None`` compiles from depth defaults.
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
    grouping_facets: list[GroupingFacet] | None = None
    extract_profiles: list[ExtractProfile] | None = None
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

    @field_validator("extract_profiles")
    @classmethod
    def validate_extract_profiles(
        cls,
        values: list[ExtractProfile] | None,
    ) -> list[ExtractProfile] | None:
        """Validate optional extraction profile composition.

        Args:
            values: Candidate short profile names, or ``None``.

        Returns:
            The validated profile list, or ``None``.

        Raises:
            ValueError: If a profile appears more than once.
        """
        if values is None:
            return None
        if len(set(values)) != len(values):
            raise ValueError("extract_profiles must not contain duplicates")
        return values

    @field_validator("grouping_facets")
    @classmethod
    def validate_grouping_facets(
        cls,
        values: list[GroupingFacet] | None,
    ) -> list[GroupingFacet] | None:
        """Validate optional grouping facet composition.

        Args:
            values: Candidate grouping facets, or ``None`` for depth defaults.

        Returns:
            The validated facet list, or ``None``.

        Raises:
            ValueError: If the list is empty or contains duplicates.
        """
        if values is None:
            return None
        if not values:
            raise ValueError("grouping_facets must not be empty")
        if len(set(values)) != len(values):
            raise ValueError("grouping_facets must not contain duplicates")
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
        if self.grouping_facets is not None and "group" not in component_set:
            raise ValueError("grouping_facets requires group in components")
        if self.extract_profiles is not None:
            if "extract" not in component_set:
                raise ValueError("extract_profiles requires extract in components")
            if "iof" not in self.extract_profiles:
                raise ValueError(
                    "extract_profiles must include 'iof'; ICF-only extraction "
                    "is unsupported in this slice"
                )

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

        if (
            self.scope_constraints.author_affiliation_countries is not None
            and self.backend_scope == "grey_lit_only"
        ):
            raise ValueError(
                "author_affiliation_countries filters the academic backend, "
                "which backend_scope 'grey_lit_only' excludes"
            )

        # Compile-target parity for the screen prompt: the composed intent
        # (question + criteria block, via the real composer) must fit the
        # prompt-assembly cap, or criteria would be silently truncated away
        # while the plan row claims they governed screening. The composer
        # enforces the cap itself (fail-closed, review fix); translate its
        # error into the plan grammar's ValueError so pydantic wraps it.
        try:
            _compose_screen_intent(self.question, self.screening_criteria)
        except ScreenDirectiveError as exc:
            raise ValueError(
                f"question plus screening_criteria exceed the screen prompt's "
                f"{SCREEN_INTENT_MAX}-character intent cap, so later criteria "
                f"would be silently dropped ({exc})"
            ) from exc
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
        # country_group compiles blocks for both backends; drop the block for
        # a backend the plan's scope excludes, or acquire-time directive
        # validation rejects the whole (approved) plan as out of scope.
        if plan.backend_scope == "academic_only":
            filters.pop("overton", None)
        elif plan.backend_scope == "grey_lit_only":
            filters.pop("openalex", None)
        if filters:
            search["filters"] = filters
        return {"search": search}
    if component == "screen_abstract" and plan.screening_criteria:
        return {"screening": {"criteria": list(plan.screening_criteria)}}
    if component == "screen_full":
        screening: dict[str, Any] = {"stage": 2}
        if plan.screening_criteria:
            screening["criteria"] = list(plan.screening_criteria)
        return {"screening": screening}
    if component == "select":
        budget = ANALYSIS_DEPTH_TABLE[plan.analysis_depth]["selection_budget"]
        if budget is None:
            raise ValueError("select cannot compile without a selection budget")
        return {"selection": {"budget": budget}}
    if component == "extract":
        profiles = plan.extract_profiles
        if profiles is None:
            profiles = list(ANALYSIS_DEPTH_TABLE[plan.analysis_depth]["extract_profiles"] or ())
        if not profiles:
            raise ValueError("extract cannot compile without extraction profiles")
        requested = set(profiles)
        return {
            "extraction": {
                "profiles": [
                    profile_id
                    for profile, profile_id in EXTRACT_PROFILE_IDS.items()
                    if profile in requested
                ]
            }
        }
    if component == "group":
        facets = plan.grouping_facets
        if facets is None:
            facets = list(ANALYSIS_DEPTH_TABLE[plan.analysis_depth]["grouping_facets"] or ())
        if not facets:
            raise ValueError("group cannot compile without grouping facets")
        return {"grouping": {"facets": list(facets)}}
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
        "screen_abstract",
        "classify",
        "appraise",
        "ingest_full_text",
    ]
    if "screen_full" in selected:
        ordered_components.append("screen_full")
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
