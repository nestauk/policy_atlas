"""Pure tests for the 017 orchestration plan model and composer."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from policy_atlas.country_filters import ISO_3166_ALPHA2
from policy_atlas.extract import KNOWN_PROFILE_IDS
from policy_atlas.orchestration_plan import (
    ANALYSIS_DEPTH_TABLE,
    DEEP_GROUPING_FACETS,
    EXTRACT_PROFILE_IDS,
    SPINE,
    TIME_BANDS,
    AnalysisDepth,
    OrchestrationPlan,
    SearchEffort,
    compose,
)

SEARCH_EFFORTS: tuple[SearchEffort, ...] = ("rapid", "standard", "deep")
ANALYSIS_DEPTHS: tuple[AnalysisDepth, ...] = ("landscape", "standard", "deep")


def _payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "title": "Housing retrofit evidence",
        "question": "What evidence exists on housing retrofit policy outcomes?",
        "scoping_notes": ["Focus on policy-relevant evidence"],
        "screening_criteria": ["Include empirical or policy-analysis sources"],
        "backend_scope": "both",
        "scope_constraints": {},
        "search_effort": "rapid",
        "analysis_depth": "landscape",
        "components": ["characterise"],
        "component_rationale": {
            "screen_full": "Useful when full-text confirmation is worth the extra pass",
            "characterise": "Maps themes and coverage for landscape questions",
            "select": "Narrows a characterised corpus when extraction is needed",
            "extract": "Captures intervention-outcome findings for deep questions",
            "group": "Organises extracted findings by an approved facet",
        },
        "grouping_facets": None,
        "steering_mode": "moderate",
        "steer_point_defaults": [
            {"steer_point": "deepening_selection", "action": "proceed_flag"}
        ],
        "assumptions": ["Publisher geography is publication geography"],
    }
    base.update(overrides)
    return base


def _plan(**overrides: Any) -> OrchestrationPlan:
    return OrchestrationPlan.model_validate(_payload(**overrides))


def _valid_component_sets(depth: AnalysisDepth) -> list[list[str]]:
    if depth == "landscape":
        return [[], ["characterise"]]
    if depth == "standard":
        # 019 select-at-standard regrade: select is now legal at standard
        # (findings_chain — extract/group — stays deep-only), so standard's
        # valid sets add characterise+select and screen_full+characterise+
        # select to the pre-019 screen_full/characterise-only sets.
        return [
            [],
            ["screen_full"],
            ["characterise"],
            ["screen_full", "characterise"],
            ["characterise", "select"],
            ["screen_full", "characterise", "select"],
        ]
    return [
        [],
        ["screen_full"],
        ["characterise"],
        ["screen_full", "characterise"],
        ["characterise", "select"],
        ["characterise", "select", "extract"],
        ["screen_full", "characterise", "select", "extract", "group"],
    ]


def _matrix_plans() -> list[OrchestrationPlan]:
    plans: list[OrchestrationPlan] = []
    for search_effort in SEARCH_EFFORTS:
        for analysis_depth in ANALYSIS_DEPTHS:
            for components in _valid_component_sets(analysis_depth):
                plans.append(
                    _plan(
                        search_effort=search_effort,
                        analysis_depth=analysis_depth,
                        components=components,
                        grouping_facets=["outcome"] if "group" in components else None,
                    )
                )
    return plans


def _assert_spine_in_order(components: list[str]) -> None:
    spine_index = 0
    for component in components:
        if component == SPINE[spine_index]:
            spine_index += 1
            if spine_index == len(SPINE):
                break
    assert spine_index == len(SPINE)


def test_spine_is_present_in_order_for_valid_plan_matrix() -> None:
    for plan in _matrix_plans():
        chain = compose(plan)
        _assert_spine_in_order(chain.components)
        assert chain.components[-1] == "synthesise"


@pytest.mark.parametrize(
    "overrides",
    [
        {"components": ["unknown"]},
        {"unexpected": "field"},
        {"analysis_depth": "standard", "components": ["characterise", "extract"]},
        {"analysis_depth": "standard", "components": ["characterise", "select", "group"]},
        {"analysis_depth": "standard", "components": ["select"]},
        {"analysis_depth": "landscape", "components": ["screen_full"]},
        {"grouping_facets": ["outcome"]},
        {
            "analysis_depth": "deep",
            "components": ["characterise", "select", "extract", "group"],
            "grouping_facets": [],
        },
        {
            "analysis_depth": "deep",
            "components": ["characterise", "select", "extract", "group"],
            "grouping_facets": ["outcome", "outcome"],
        },
        {
            "analysis_depth": "deep",
            "components": ["characterise", "select", "extract", "group"],
            "grouping_facets": ["mechanism"],
        },
        {"extract_profiles": ["iof"]},
        {
            "analysis_depth": "deep",
            "components": ["characterise", "select", "extract"],
            "extract_profiles": ["iof", "iof"],
        },
        {
            "analysis_depth": "deep",
            "components": ["characterise", "select", "extract"],
            "extract_profiles": ["iof", "xyz"],
        },
        {
            "steer_point_defaults": [
                {"steer_point": "deepening-selection", "action": "continue"}
            ]
        },
        {
            "steer_point_defaults": [
                {"steer_point": "not-a-steer-point", "action": "proceed_flag"}
            ]
        },
        # Compile-target parity: question + criteria must fit the screen
        # prompt's intent cap, or criteria would silently truncate mid-run.
        {"question": "q" * 1_990, "screening_criteria": ["Exclude opinion pieces."]},
        {"scope_constraints": {"publisher_country": "x" * 101}},
        {"scope_constraints": {"publisher_country": "United Kingdom"}},
        {"scope_constraints": {"publisher_country": "GB"}},
        {"scope_constraints": {"publisher_country": "United Kingdom\x1b[2J"}},
        {
            "backend_scope": "academic_only",
            "scope_constraints": {"publisher_country": "UK"},
        },
        {"scope_constraints": {"author_affiliation_countries": []}},
        {"scope_constraints": {"author_affiliation_countries": ["gbr"]}},
        {"scope_constraints": {"author_affiliation_countries": ["g"]}},
        {"scope_constraints": {"author_affiliation_countries": ["g1"]}},
        {"scope_constraints": {"author_affiliation_countries": ["XX"]}},
        {"scope_constraints": {"author_affiliation_countries": ["gb", "GB"]}},
        {
            "scope_constraints": {
                "country_group": {
                    "label": "Nordic countries",
                    "countries": ["NO", "SE", "ZZ"],
                    "authorship": "planner-proposed",
                }
            }
        },
        {
            "scope_constraints": {
                "publisher_country": "UK",
                "country_group": {"label": "G7", "authorship": "pinned-table"},
            }
        },
        {
            "scope_constraints": {
                "country_group": {
                    "label": "Large custom group",
                    "countries": list(ISO_3166_ALPHA2)[:201],
                    "authorship": "planner-proposed",
                }
            }
        },
        {
            "backend_scope": "grey_lit_only",
            "scope_constraints": {"author_affiliation_countries": ["GB"]},
        },
    ],
)
def test_fail_closed_validation(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _plan(**overrides)


def test_intent_fit_can_strike_findings_chain_at_standard_depth() -> None:
    plan = _plan(search_effort="standard", analysis_depth="standard", components=["characterise"])

    chain = compose(plan)

    assert chain.components == [
        "acquire",
        "screen_abstract",
        "classify",
        "appraise",
        "ingest_full_text",
        "characterise",
        "synthesise",
    ]


def test_standard_depth_composes_without_findings_chain_components() -> None:
    """018 regrade: extract/group are deep-only; standard keeps ingest plus
    full-text screening and characterisation, so synthesise grounds in
    full-text chunks and characterisation without the findings layer.
    """
    plan = _plan(
        search_effort="standard",
        analysis_depth="standard",
        components=["screen_full", "characterise"],
    )

    chain = compose(plan)

    assert chain.components == [
        "acquire",
        "screen_abstract",
        "classify",
        "appraise",
        "ingest_full_text",
        "screen_full",
        "characterise",
        "synthesise",
    ]
    assert "select" not in chain.components
    assert "extract" not in chain.components
    assert "group" not in chain.components

    # extract/group are not merely absent when unselected — they are disabled
    # outright at standard depth (deep-only; unchanged by the 019 select
    # regrade below).
    with pytest.raises(ValidationError):
        _plan(
            search_effort="standard",
            analysis_depth="standard",
            components=["screen_full", "characterise", "extract"],
        )


def test_standard_depth_composes_select_after_characterise_before_synthesise() -> None:
    """019 select-at-standard regrade: select now runs at standard too, ordered
    after characterise (its reference rule) and before synthesise, still
    without the findings chain.
    """
    plan = _plan(
        search_effort="standard",
        analysis_depth="standard",
        components=["screen_full", "characterise", "select"],
    )

    chain = compose(plan)

    assert chain.components == [
        "acquire",
        "screen_abstract",
        "classify",
        "appraise",
        "ingest_full_text",
        "screen_full",
        "characterise",
        "select",
        "synthesise",
    ]
    assert "extract" not in chain.components
    assert "group" not in chain.components
    select_step = next(step for step in chain.steps if step.component == "select")
    assert select_step.directive_delta == {"selection": {"budget": 15}}
    assert select_step.reference_rule == "characterisation_run_id <- characterise"


def test_extract_without_select_and_group_without_extract_rejected_at_deep() -> None:
    """The findings-chain both-or-neither rule still requires select first."""
    with pytest.raises(ValidationError):
        _plan(
            search_effort="deep",
            analysis_depth="deep",
            components=["characterise", "extract"],
        )
    with pytest.raises(ValidationError):
        _plan(
            search_effort="deep",
            analysis_depth="deep",
            components=["characterise", "select", "group"],
        )


def test_depth_rows_pin_findings_chain_defaults() -> None:
    """Pin the depth table rows, including Phase-D extract profile defaults."""
    assert ANALYSIS_DEPTH_TABLE["landscape"] == {
        "screen_full": False,
        "characterise": True,
        "select": False,
        "findings_chain": False,
        "selection_budget": None,
        "extract_profiles": None,
        "grouping_facets": None,
    }
    assert ANALYSIS_DEPTH_TABLE["deep"] == {
        "screen_full": True,
        "characterise": True,
        "select": True,
        "findings_chain": True,
        "selection_budget": 25,
        "extract_profiles": ("iof", "icf"),
        "grouping_facets": DEEP_GROUPING_FACETS,
    }
    assert ANALYSIS_DEPTH_TABLE["standard"]["select"] is True
    assert ANALYSIS_DEPTH_TABLE["standard"]["findings_chain"] is False
    assert ANALYSIS_DEPTH_TABLE["standard"]["selection_budget"] == 15
    assert ANALYSIS_DEPTH_TABLE["standard"]["extract_profiles"] is None
    assert ANALYSIS_DEPTH_TABLE["standard"]["grouping_facets"] is None
    assert DEEP_GROUPING_FACETS == (
        "intervention",
        "outcome",
        "barrier_theme",
        "enabler_theme",
        "mechanism_theme",
    )
    assert TIME_BANDS[("rapid", "landscape")] == "~10-15 min"
    assert TIME_BANDS[("standard", "landscape")] == "~15-20 min"
    assert TIME_BANDS[("deep", "landscape")] == "~20-25 min"
    assert TIME_BANDS[("rapid", "deep")] == "~75-90 min"
    assert TIME_BANDS[("standard", "deep")] == "~80-95 min"
    assert TIME_BANDS[("deep", "deep")] == "~90-100 min"


def test_extract_profile_id_mapping_matches_extract_registry() -> None:
    assert tuple(EXTRACT_PROFILE_IDS.values()) == KNOWN_PROFILE_IDS


def test_deep_extract_default_compiles_both_profiles_iof_first() -> None:
    plan = _plan(
        search_effort="deep",
        analysis_depth="deep",
        components=["characterise", "select", "extract"],
    )

    extract_step = next(step for step in compose(plan).steps if step.component == "extract")

    assert extract_step.directive_delta == {
        "extraction": {"profiles": list(KNOWN_PROFILE_IDS)}
    }


def test_deep_group_default_compiles_named_facet_set() -> None:
    plan = _plan(
        search_effort="deep",
        analysis_depth="deep",
        components=["characterise", "select", "extract", "group"],
    )

    group_step = next(step for step in compose(plan).steps if step.component == "group")

    assert group_step.directive_delta == {"grouping": {"facets": list(DEEP_GROUPING_FACETS)}}


def test_explicit_grouping_facets_compile_to_list_directive() -> None:
    plan = _plan(
        search_effort="deep",
        analysis_depth="deep",
        components=["characterise", "select", "extract", "group"],
        grouping_facets=["outcome", "barrier_theme"],
    )

    group_step = next(step for step in compose(plan).steps if step.component == "group")

    assert group_step.directive_delta == {
        "grouping": {"facets": ["outcome", "barrier_theme"]}
    }


def test_explicit_iof_only_extract_profile_compiles_narrowly() -> None:
    plan = _plan(
        search_effort="deep",
        analysis_depth="deep",
        components=["characterise", "select", "extract"],
        extract_profiles=["iof"],
    )

    extract_step = next(step for step in compose(plan).steps if step.component == "extract")

    assert extract_step.directive_delta == {
        "extraction": {"profiles": [EXTRACT_PROFILE_IDS["iof"]]}
    }


@pytest.mark.parametrize(
    ("analysis_depth", "components"),
    [
        ("landscape", ["characterise"]),
        ("standard", ["characterise", "select"]),
    ],
)
def test_non_findings_depths_have_no_extraction_directive(
    analysis_depth: AnalysisDepth,
    components: list[str],
) -> None:
    plan = _plan(
        search_effort="standard",
        analysis_depth=analysis_depth,
        components=components,
    )

    chain = compose(plan)

    assert "extract" not in chain.components
    assert all("extraction" not in step.directive_delta for step in chain.steps)


def test_icf_only_extract_profile_rejected_plainly() -> None:
    with pytest.raises(ValidationError, match="ICF-only extraction is unsupported"):
        _plan(
            search_effort="deep",
            analysis_depth="deep",
            components=["characterise", "select", "extract"],
            extract_profiles=["icf"],
        )


def test_round_trip_payload_composes_to_identical_chain() -> None:
    plan = _plan(
        search_effort="deep",
        analysis_depth="deep",
        components=["screen_full", "characterise", "select", "extract", "group"],
        grouping_facets=["outcome", "barrier_theme"],
        scope_constraints={
            "published_after": "2020-01-01",
            "published_before": "2025-12-31",
            "publisher_country": "UK",
        },
    )

    round_tripped = OrchestrationPlan.model_validate(plan.model_dump())

    assert compose(round_tripped).model_dump() == compose(plan).model_dump()


def test_scope_constraints_compile_into_two_level_search_filters() -> None:
    plan = _plan(
        search_effort="standard",
        scope_constraints={
            "published_after": "2021-01-01",
            "published_before": "2024-12-31",
            "publisher_country": "UK",
        },
    )

    acquire = compose(plan).steps[0]

    assert acquire.directive_delta == {
        "search": {
            "depth": "standard",
            "filters": {
                "shared": {
                    "published_after": "2021-01-01",
                    "published_before": "2024-12-31",
                },
                "overton": {"publisher_country": "UK"},
            },
        }
    }


def test_author_affiliation_countries_normalised_to_upper_case() -> None:
    plan = _plan(scope_constraints={"author_affiliation_countries": ["gb", "us"]})

    assert plan.scope_constraints.author_affiliation_countries == ["GB", "US"]


def test_tier1_country_group_compiles_to_openalex_and_native_overton_region() -> None:
    plan = _plan(
        scope_constraints={
            "country_group": {"label": "OECD members", "authorship": "pinned-table"}
        }
    )

    filters = plan.scope_constraints.to_filters()

    assert len(filters["openalex"]["author_affiliation_countries"]) == 38
    assert filters["overton"] == {"publisher_region": "OECD members"}


def test_tier2_country_group_compiles_to_openalex_and_overton_post_filter() -> None:
    plan = _plan(
        scope_constraints={
            "country_group": {
                "label": "Nordic countries",
                "countries": ["no", "se", "dk", "fi", "is"],
                "authorship": "planner-proposed",
            }
        }
    )

    filters = plan.scope_constraints.to_filters()

    assert filters["openalex"] == {
        "author_affiliation_countries": ["NO", "SE", "DK", "FI", "IS"]
    }
    assert filters["overton"] == {
        "source_country_post_filter": [
            "Denmark",
            "Finland",
            "Iceland",
            "Norway",
            "Sweden",
        ]
    }


def test_country_group_compile_drops_overton_block_for_academic_only_scope() -> None:
    """country_group compiles blocks for both backends; the acquire directive
    must drop the block for a backend the plan's scope excludes, or acquire-time
    directive validation rejects the approved plan as out of scope."""
    plan = _plan(
        backend_scope="academic_only",
        scope_constraints={"country_group": {"label": "G7", "authorship": "pinned-table"}},
    )

    acquire_step = next(step for step in compose(plan).steps if step.component == "acquire")
    filters = acquire_step.directive_delta["search"]["filters"]

    assert len(filters["openalex"]["author_affiliation_countries"]) == 7
    assert "overton" not in filters


def test_country_group_compile_drops_openalex_block_for_grey_lit_only_scope() -> None:
    plan = _plan(
        backend_scope="grey_lit_only",
        scope_constraints={"country_group": {"label": "G7", "authorship": "pinned-table"}},
    )

    acquire_step = next(step for step in compose(plan).steps if step.component == "acquire")
    filters = acquire_step.directive_delta["search"]["filters"]

    assert filters["overton"] == {"publisher_region": "G7"}
    assert "openalex" not in filters


def test_scope_constraints_compile_openalex_block_alongside_shared_and_overton() -> None:
    plan = _plan(
        search_effort="standard",
        scope_constraints={
            "published_after": "2021-01-01",
            "published_before": "2024-12-31",
            "publisher_country": "UK",
            "author_affiliation_countries": ["gb", "us"],
        },
    )

    acquire = compose(plan).steps[0]

    assert acquire.directive_delta == {
        "search": {
            "depth": "standard",
            "filters": {
                "shared": {
                    "published_after": "2021-01-01",
                    "published_before": "2024-12-31",
                },
                "overton": {"publisher_country": "UK"},
                "openalex": {"author_affiliation_countries": ["GB", "US"]},
            },
        }
    }


def test_author_affiliation_countries_flow_to_openalex_wire_filter_string() -> None:
    """End-to-end wire pin: plan constraints -> validate_scope_filters ->
    openalex_wire_params, lower-case input normalised upper on the plan.
    """
    from policy_atlas.search_loop import openalex_wire_params, validate_scope_filters

    plan = _plan(scope_constraints={"author_affiliation_countries": ["gb", "us"]})

    filters = plan.scope_constraints.to_filters()
    validated = validate_scope_filters(filters, backend_names=["openalex"])
    wire = openalex_wire_params(validated.get("openalex"))

    assert wire == {"filter": "authorships.countries:GB|US"}


def test_empty_scope_constraints_omit_filters_key() -> None:
    acquire = compose(_plan()).steps[0]

    assert acquire.directive_delta == {"search": {"depth": "rapid"}}


def test_synthesise_never_receives_directive_delta() -> None:
    for plan in _matrix_plans():
        synthesise = compose(plan).steps[-1]
        assert synthesise.component == "synthesise"
        assert synthesise.directive_delta == {}


def test_off_diagonal_plans_compose_validly() -> None:
    narrow_and_deep = _plan(
        search_effort="rapid",
        analysis_depth="deep",
        components=["screen_full", "characterise", "select", "extract", "group"],
        grouping_facets=["intervention"],
    )
    horizon_scan = _plan(
        search_effort="deep",
        analysis_depth="landscape",
        components=["characterise"],
    )

    narrow_chain = compose(narrow_and_deep)
    horizon_chain = compose(horizon_scan)

    assert narrow_chain.steps[0].directive_delta["search"]["depth"] == "rapid"
    assert "group" in narrow_chain.components
    assert horizon_chain.steps[0].directive_delta["search"]["depth"] == "deep"
    assert "screen_full" not in horizon_chain.components


def test_expected_artefact_shape_and_time_band_are_deterministic() -> None:
    landscape = _plan(
        search_effort="rapid",
        analysis_depth="landscape",
        components=["characterise"],
    )
    grounded = _plan(
        search_effort="standard",
        analysis_depth="standard",
        components=[],
    )
    facet = _plan(
        search_effort="deep",
        analysis_depth="deep",
        components=["screen_full", "characterise", "select", "extract", "group"],
        grouping_facets=["population"],
    )

    assert landscape.expected_artefact_shape == "landscape coverage, themes and gaps"
    assert landscape.time_band == TIME_BANDS[("rapid", "landscape")]
    assert grounded.expected_artefact_shape == "grounded answer over the screened corpus"
    assert grounded.time_band == TIME_BANDS[("standard", "standard")]
    assert facet.expected_artefact_shape == "facet-organised synthesis over extracted findings"
    assert facet.time_band == TIME_BANDS[("deep", "deep")]


def test_screening_criteria_caps_mirror_screen_directive_grammar() -> None:
    """Plan-model caps match screen.py's directive caps by construction.

    Live check 017: a >200-char criterion validated on the plan, composed,
    and rejected at the screen boundary mid-run. The plan model must reject
    anything its compile target rejects.
    """
    with pytest.raises(ValidationError, match="at most 200 characters"):
        _plan(screening_criteria=["x" * 201])
    with pytest.raises(ValidationError, match="at most 50 entries"):
        _plan(screening_criteria=[f"criterion {i}" for i in range(51)])
    ok = _plan(screening_criteria=["x" * 200] + [f"criterion {i}" for i in range(49)])
    assert len(ok.screening_criteria) == 50
