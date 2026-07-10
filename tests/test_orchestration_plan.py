"""Pure tests for the 017 orchestration plan model and composer."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from policy_atlas.orchestration_plan import (
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
            "screen_stage2": "Useful when full-text confirmation is worth the extra pass",
            "characterise": "Maps themes and coverage for landscape questions",
            "select": "Narrows a characterised corpus when extraction is needed",
            "extract": "Captures intervention-outcome findings for deep questions",
            "group": "Organises extracted findings by an approved facet",
        },
        "grouping_facet": None,
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
    return [
        [],
        ["screen_stage2"],
        ["characterise"],
        ["screen_stage2", "characterise"],
        ["characterise", "select"],
        ["characterise", "select", "extract"],
        ["screen_stage2", "characterise", "select", "extract", "group"],
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
                        grouping_facet="outcome" if "group" in components else None,
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
        {"analysis_depth": "landscape", "components": ["screen_stage2"]},
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
        {"scope_constraints": {"publisher_country": "United Kingdom\x1b[2J"}},
        {
            "backend_scope": "academic_only",
            "scope_constraints": {"publisher_country": "United Kingdom"},
        },
    ],
)
def test_fail_closed_validation(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _plan(**overrides)


def test_intent_fit_can_strike_deep_chain_at_standard_depth() -> None:
    plan = _plan(search_effort="standard", analysis_depth="standard", components=["characterise"])

    chain = compose(plan)

    assert chain.components == [
        "acquire",
        "screen",
        "classify",
        "appraise",
        "ingest_full_text",
        "characterise",
        "synthesise",
    ]


def test_round_trip_payload_composes_to_identical_chain() -> None:
    plan = _plan(
        search_effort="deep",
        analysis_depth="standard",
        components=["screen_stage2", "characterise", "select", "extract", "group"],
        grouping_facet="outcome",
        scope_constraints={
            "published_after": "2020-01-01",
            "published_before": "2025-12-31",
            "publisher_country": "United Kingdom",
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
            "publisher_country": "United Kingdom",
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
                "overton": {"publisher_country": "United Kingdom"},
            },
        }
    }


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
        components=["screen_stage2", "characterise", "select", "extract", "group"],
        grouping_facet="intervention",
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
    assert "screen_stage2" not in horizon_chain.components


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
        components=["screen_stage2", "characterise", "select", "extract", "group"],
        grouping_facet="population",
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
