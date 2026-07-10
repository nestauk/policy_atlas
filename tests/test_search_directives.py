"""Pure grammar/pure-logic tests: search directive parsing, scope filter validation,
wire-param mapping, backend-scope compile, and the deep-loop stop decision matrix.

No database access — every function under test here is pure Python.
"""

import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from policy_atlas.plan import Config, Plan, compile
from policy_atlas.search_loop import (
    ROUND_CAP,
    SearchDirectiveError,
    StopDecision,
    evaluate_deep_stop,
    parse_search_directive,
    to_wire_params,
    validate_scope_filters,
)

# --- parse_search_directive: fail-closed matrix ---


def test_parse_search_directive_absent() -> None:
    assert parse_search_directive({}) == ("rapid", None)


def test_parse_search_directive_unknown_key() -> None:
    with pytest.raises(SearchDirectiveError):
        parse_search_directive({"search": {"depth": "rapid", "bogus": 1}})


def test_parse_search_directive_non_dict() -> None:
    with pytest.raises(SearchDirectiveError):
        parse_search_directive({"search": "oops"})


def test_parse_search_directive_bad_depth() -> None:
    with pytest.raises(SearchDirectiveError):
        parse_search_directive({"search": {"depth": "turbo"}})


def test_parse_search_directive_depth_deep_ok() -> None:
    assert parse_search_directive({"search": {"depth": "deep"}}) == ("deep", None)


def test_parse_search_directive_depth_standard_ok() -> None:
    assert parse_search_directive({"search": {"depth": "standard"}}) == ("standard", None)


def test_parse_search_directive_null_filters_rejected() -> None:
    with pytest.raises(SearchDirectiveError):
        parse_search_directive({"search": {"filters": None}})


# --- validate_scope_filters + to_wire_params: full valid example ---


def test_validate_scope_filters_full_example_both_backends() -> None:
    raw = {
        "shared": {
            "published_after": "2020-01-01",
            "published_before": "2023-01-01",
            "sdgs": [3],
        },
        "openalex": {
            "types": ["article", "report"],
            "languages": ["en", "fr"],
            "exclude_retracted": True,
            "exclude_paratext": True,
            "oa_status": ["gold", "green"],
            "author_affiliation_countries": ["US", "GB"],
        },
        "overton": {
            "publisher_type": "government",
            "publisher_country": "United Kingdom",
            "publisher_region": "Europe",
            "language": "eng",
        },
    }
    validated = validate_scope_filters(raw, backend_names=["openalex", "overton"])

    oa_wire = to_wire_params("openalex", validated["openalex"])
    assert oa_wire == {
        "filter": (
            "from_publication_date:2020-01-01,"
            "to_publication_date:2023-01-01,"
            "sustainable_development_goals.id:https://metadata.un.org/sdg/3,"
            "type:article|report,"
            "language:en|fr,"
            "is_retracted:false,"
            "is_paratext:false,"
            "oa_status:gold|green,"
            "authorships.countries:US|GB"
        )
    }

    ov_wire = to_wire_params("overton", validated["overton"])
    assert ov_wire == {
        "published_after": "2020-01-01",
        "published_before": "2023-01-01",
        "sdgcategories": "SDG 3: Good Health and Well-being",
        "source_type": "government",
        "source_country": "United Kingdom",
        "source_region": "Europe",
        "language": "eng",
    }


# --- validate_scope_filters: fail-closed matrix ---


@pytest.mark.parametrize(
    ("raw", "backend_names"),
    [
        # unknown top-level key
        ({"bogus": {}}, ["openalex", "overton"]),
        # unknown block key
        ({"shared": {"nope": 1}}, ["openalex", "overton"]),
        # bad ISO date: invalid calendar date
        ({"shared": {"published_after": "2026-13-01"}}, ["openalex", "overton"]),
        # bad ISO date: non-string
        ({"shared": {"published_after": 20260101}}, ["openalex", "overton"]),
        # sdgs out of range low
        ({"shared": {"sdgs": [0]}}, ["openalex", "overton"]),
        # sdgs out of range high
        ({"shared": {"sdgs": [18]}}, ["openalex", "overton"]),
        # sdgs bool disguised as int
        ({"shared": {"sdgs": [True]}}, ["openalex", "overton"]),
        # openalex types: unknown value
        ({"openalex": {"types": ["not_a_real_type"]}}, ["openalex"]),
        # openalex languages: uppercase not accepted
        ({"openalex": {"languages": ["EN"]}}, ["openalex"]),
        # openalex languages: 3-letter code not accepted (must be 2)
        ({"openalex": {"languages": ["eng"]}}, ["openalex"]),
        # openalex author countries: lowercase not accepted (must be uppercase)
        ({"openalex": {"author_affiliation_countries": ["us"]}}, ["openalex"]),
        # overton fields are single-valued: a list is rejected
        ({"overton": {"publisher_type": ["government", "igo"]}}, ["overton"]),
        # overton unknown region
        ({"overton": {"publisher_region": "Mars"}}, ["overton"]),
        # overton unknown publisher type
        ({"overton": {"publisher_type": "nonprofit"}}, ["overton"]),
        # backend block supplied outside declared backend scope
        ({"overton": {"publisher_type": "government"}}, ["openalex"]),
        ({"openalex": {"types": ["article"]}}, ["overton"]),
        # shared sdgs must be single-valued when Overton is in scope
        ({"shared": {"sdgs": [3, 4]}}, ["openalex", "overton"]),
    ],
)
def test_validate_scope_filters_fail_closed(
    raw: dict[str, Any], backend_names: list[str]
) -> None:
    with pytest.raises(SearchDirectiveError):
        validate_scope_filters(raw, backend_names=backend_names)


# --- Plan/Config search_backend_scope ---


@pytest.mark.parametrize("scope", ["academic_only", "grey_lit_only", "both"])
def test_search_backend_scope_accepted_and_copied_by_compile(scope: str) -> None:
    scope_id = uuid.uuid4()
    # model_validate (not the constructor) keeps this parametrized over plain `str`
    # without narrowing to the Literal at the call site.
    plan = Plan.model_validate(
        {"component": "acquire", "evidence_scope_id": scope_id, "search_backend_scope": scope}
    )
    assert plan.search_backend_scope == scope
    config = compile(plan)
    assert config.search_backend_scope == scope


def test_search_backend_scope_unknown_value_rejected_on_plan() -> None:
    with pytest.raises(ValidationError):
        Plan.model_validate(
            {
                "component": "acquire",
                "evidence_scope_id": uuid.uuid4(),
                "search_backend_scope": "unknown_scope",
            }
        )


def test_search_backend_scope_unknown_value_rejected_on_config() -> None:
    with pytest.raises(ValidationError):
        Config.model_validate(
            {
                "component": "acquire",
                "evidence_scope_id": uuid.uuid4(),
                "search_backend_scope": "unknown_scope",
            }
        )


# --- evaluate_deep_stop: pure stop-decision matrix ---


def test_deep_stop_target_reached() -> None:
    decision = evaluate_deep_stop(
        round_index=1,
        confident_relevant=20,
        new_confident_relevant=20,
        docs_screened_this_round=100,
        wall_clock_breached=False,
    )
    assert decision == StopDecision(True, "target_reached", False)


def test_deep_stop_target_reached_above_target() -> None:
    decision = evaluate_deep_stop(
        round_index=2,
        confident_relevant=25,
        new_confident_relevant=5,
        docs_screened_this_round=10,
        wall_clock_breached=False,
    )
    assert decision.stop is True
    assert decision.stop_condition == "target_reached"


def test_deep_stop_short_circuit_low_rate_round_2() -> None:
    decision = evaluate_deep_stop(
        round_index=2,
        confident_relevant=5,
        new_confident_relevant=1,
        docs_screened_this_round=1000,  # 1/1000 < 1/50
        wall_clock_breached=False,
    )
    assert decision == StopDecision(True, "short_circuit", False)


def test_deep_stop_short_circuit_zero_docs_round_2() -> None:
    decision = evaluate_deep_stop(
        round_index=2,
        confident_relevant=5,
        new_confident_relevant=0,
        docs_screened_this_round=0,
        wall_clock_breached=False,
    )
    assert decision == StopDecision(True, "short_circuit", False)


def test_deep_stop_round_1_never_short_circuits() -> None:
    """Round 1 is the rapid leg; the discovery-rate floor only applies from round 2."""
    decision = evaluate_deep_stop(
        round_index=1,
        confident_relevant=5,
        new_confident_relevant=0,
        docs_screened_this_round=1000,
        wall_clock_breached=False,
    )
    assert decision == StopDecision(False, None, False)


def test_deep_stop_budget_on_round_cap() -> None:
    decision = evaluate_deep_stop(
        round_index=ROUND_CAP,
        confident_relevant=5,
        new_confident_relevant=5,
        docs_screened_this_round=10,  # healthy rate, no short-circuit
        wall_clock_breached=False,
    )
    assert decision == StopDecision(True, "budget_exhausted", False)


def test_deep_stop_budget_on_wall_clock_breach() -> None:
    decision = evaluate_deep_stop(
        round_index=2,
        confident_relevant=5,
        new_confident_relevant=5,
        docs_screened_this_round=10,
        wall_clock_breached=True,
    )
    assert decision == StopDecision(True, "budget_exhausted", False)


def test_deep_stop_no_stop_otherwise() -> None:
    decision = evaluate_deep_stop(
        round_index=2,
        confident_relevant=5,
        new_confident_relevant=5,
        docs_screened_this_round=10,
        wall_clock_breached=False,
    )
    assert decision == StopDecision(False, None, False)


def test_deep_stop_custom_round_cap() -> None:
    decision = evaluate_deep_stop(
        round_index=2,
        confident_relevant=5,
        new_confident_relevant=5,
        docs_screened_this_round=10,
        wall_clock_breached=False,
        round_cap=2,
    )
    assert decision == StopDecision(True, "budget_exhausted", False)
