"""Pure grammar/pure-logic tests: search directive parsing, scope filter validation,
wire-param mapping, backend-scope compile, and the deep-loop stop decision matrix.

No database access — every function under test here is pure Python.
"""

import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from policy_atlas.core.schema import DIRECTIVE_STRING_MAX
from policy_atlas.evidence_base.sourcing.country_filters import (
    ISO_3166_ALPHA2,
    expand_tier1,
    validate_iso_alpha2,
)
from policy_atlas.evidence_base.sourcing.search_loop import (
    ROUND_CAP,
    SEARCH_TARGET_MAX,
    SEARCH_TARGET_MIN,
    TARGET_CONFIDENT_RELEVANT,
    SearchDirectiveError,
    StopDecision,
    _filter_variants,
    evaluate_deep_stop,
    parse_search_directive,
    to_wire_params,
    validate_scope_filters,
)
from policy_atlas.runtime.run_spec import Config, Plan, compile

# --- parse_search_directive: fail-closed matrix ---


def test_parse_search_directive_absent() -> None:
    assert parse_search_directive({}) == ("rapid", None, None, None)


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
    assert parse_search_directive({"search": {"depth": "deep"}}) == ("deep", None, None, None)


def test_parse_search_directive_depth_standard_ok() -> None:
    assert parse_search_directive({"search": {"depth": "standard"}}) == (
        "standard", None, None, None,
    )


def test_parse_search_directive_null_filters_rejected() -> None:
    with pytest.raises(SearchDirectiveError):
        parse_search_directive({"search": {"filters": None}})


# --- D5 search.target: fail-closed matrix ---


@pytest.mark.parametrize("target", [SEARCH_TARGET_MIN, 20, SEARCH_TARGET_MAX])
def test_parse_search_directive_accepts_valid_target(target: int) -> None:
    assert parse_search_directive({"search": {"target": target}}) == ("rapid", None, target, None)


@pytest.mark.parametrize(
    "target",
    [SEARCH_TARGET_MIN - 1, SEARCH_TARGET_MAX + 1, 0, -5],
)
def test_parse_search_directive_rejects_out_of_range_target(target: int) -> None:
    # Out-of-range values are refused, never silently clamped (honest refusal).
    with pytest.raises(SearchDirectiveError):
        parse_search_directive({"search": {"target": target}})


@pytest.mark.parametrize("target", [20.5, "20", True, None, [20]])
def test_parse_search_directive_rejects_malformed_target_type(target: object) -> None:
    with pytest.raises(SearchDirectiveError):
        parse_search_directive({"search": {"target": target}})


# --- B1 search.guidance: fail-closed matrix ---


def test_parse_search_directive_guidance_absent_is_none() -> None:
    assert parse_search_directive({"search": {"depth": "deep"}}) == ("deep", None, None, None)


@pytest.mark.parametrize(
    "guidance",
    [
        ["prioritise UK policy evaluations"],
        ["prioritise UK policy evaluations", "avoid clinical literature"],
        ["a", "b", "c", "d", "e"],
    ],
)
def test_parse_search_directive_accepts_valid_guidance(guidance: list[str]) -> None:
    assert parse_search_directive({"search": {"guidance": guidance}}) == (
        "rapid", None, None, guidance,
    )


@pytest.mark.parametrize(
    "guidance",
    [
        [],
        ["a", "b", "c", "d", "e", "f"],
        "not a list",
        [123],
        [""],
        ["   "],
        [None],
        ["x" * (DIRECTIVE_STRING_MAX + 1)],
        ["contains\x00control"],
        ["contains\x07bell"],
    ],
)
def test_parse_search_directive_rejects_malformed_guidance(guidance: object) -> None:
    with pytest.raises(SearchDirectiveError):
        parse_search_directive({"search": {"guidance": guidance}})


def test_parse_search_directive_guidance_at_max_chars_accepted() -> None:
    guidance = ["x" * DIRECTIVE_STRING_MAX]
    assert parse_search_directive({"search": {"guidance": guidance}})[3] == guidance


def test_parse_search_directive_guidance_combines_with_other_keys() -> None:
    assert parse_search_directive(
        {"search": {"depth": "deep", "target": 30, "guidance": ["prioritise UK evidence"]}}
    ) == ("deep", None, 30, ["prioritise UK evidence"])


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
            "publisher_country": "UK",
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
        "source_country": "UK",
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
        # openalex author countries: syntactic code, not ISO-3166 alpha-2
        ({"openalex": {"author_affiliation_countries": ["XX"]}}, ["openalex"]),
        # overton fields are single-valued: a list is rejected
        ({"overton": {"publisher_type": ["government", "igo"]}}, ["overton"]),
        # overton publisher_country is the probed display-name allowlist, not ISO/common aliases
        ({"overton": {"publisher_country": "GB"}}, ["overton"]),
        ({"overton": {"publisher_country": "United Kingdom"}}, ["overton"]),
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


# --- validate_iso_alpha2 / expand_tier1: additional fail-closed rows ---


@pytest.mark.parametrize(
    "codes",
    [
        # empty list
        [],
        # non-string element
        ["US", 123],
        # duplicate codes
        ["US", "US"],
    ],
)
def test_validate_iso_alpha2_fail_closed(codes: list[Any]) -> None:
    with pytest.raises(SearchDirectiveError):
        validate_iso_alpha2(codes)


def test_expand_tier1_rejects_unknown_label() -> None:
    with pytest.raises(SearchDirectiveError):
        expand_tier1("Atlantis")


def test_validate_scope_filters_publisher_country_hint_names_uk() -> None:
    with pytest.raises(SearchDirectiveError, match="UK"):
        validate_scope_filters(
            {"overton": {"publisher_country": "United Kingdom"}},
            backend_names=["overton"],
        )


def test_validate_scope_filters_accepts_probed_overton_country_names() -> None:
    validated = validate_scope_filters(
        {"overton": {"publisher_country": "USA"}},
        backend_names=["overton"],
    )

    assert to_wire_params("overton", validated["overton"]) == {"source_country": "USA"}


def test_source_country_post_filter_validates_but_never_maps_to_wire() -> None:
    validated = validate_scope_filters(
        {"overton": {"source_country_post_filter": ["UK", "France"]}},
        backend_names=["overton"],
    )

    assert validated["overton"] == {"source_country_post_filter": ["UK", "France"]}
    assert to_wire_params("overton", validated["overton"]) == {}


def test_openalex_country_filter_variants_split_after_100_codes() -> None:
    countries = [f"C{i:03d}" for i in range(101)]
    validated = {"author_affiliation_countries": countries}

    variants = _filter_variants("openalex", validated)

    assert [len(variant["author_affiliation_countries"]) for variant in variants] == [100, 1]
    wires = [to_wire_params("openalex", variant)["filter"] for variant in variants]
    assert all(
        len(wire.removeprefix("authorships.countries:").split("|")) <= 100
        for wire in wires
    )
    union = [
        country
        for variant in variants
        for country in variant["author_affiliation_countries"]
    ]
    assert union == countries


def test_openalex_country_filter_variants_pass_through_at_100_codes() -> None:
    countries = [f"C{i:03d}" for i in range(100)]

    assert _filter_variants("openalex", {"author_affiliation_countries": countries}) == [
        {"author_affiliation_countries": countries}
    ]


def test_openalex_country_filter_rejects_more_than_200_codes() -> None:
    with pytest.raises(SearchDirectiveError):
        validate_scope_filters(
            {
                "openalex": {
                    "author_affiliation_countries": list(ISO_3166_ALPHA2)[:201],
                }
            },
            backend_names=["openalex"],
        )


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
    assert decision == StopDecision(True, "target_reached")


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
    assert decision == StopDecision(True, "short_circuit")


def test_deep_stop_short_circuit_zero_docs_round_2() -> None:
    decision = evaluate_deep_stop(
        round_index=2,
        confident_relevant=5,
        new_confident_relevant=0,
        docs_screened_this_round=0,
        wall_clock_breached=False,
    )
    assert decision == StopDecision(True, "short_circuit")


def test_deep_stop_round_1_never_short_circuits() -> None:
    """Round 1 is the rapid leg; the discovery-rate floor only applies from round 2."""
    decision = evaluate_deep_stop(
        round_index=1,
        confident_relevant=5,
        new_confident_relevant=0,
        docs_screened_this_round=1000,
        wall_clock_breached=False,
    )
    assert decision == StopDecision(False, None)


def test_deep_stop_budget_on_round_cap() -> None:
    decision = evaluate_deep_stop(
        round_index=ROUND_CAP,
        confident_relevant=5,
        new_confident_relevant=5,
        docs_screened_this_round=10,  # healthy rate, no short-circuit
        wall_clock_breached=False,
    )
    assert decision == StopDecision(True, "budget_exhausted")


def test_deep_stop_budget_on_wall_clock_breach() -> None:
    decision = evaluate_deep_stop(
        round_index=2,
        confident_relevant=5,
        new_confident_relevant=5,
        docs_screened_this_round=10,
        wall_clock_breached=True,
    )
    assert decision == StopDecision(True, "budget_exhausted")


def test_deep_stop_no_stop_otherwise() -> None:
    decision = evaluate_deep_stop(
        round_index=2,
        confident_relevant=5,
        new_confident_relevant=5,
        docs_screened_this_round=10,
        wall_clock_breached=False,
    )
    assert decision == StopDecision(False, None)


def test_deep_stop_custom_round_cap() -> None:
    decision = evaluate_deep_stop(
        round_index=2,
        confident_relevant=5,
        new_confident_relevant=5,
        docs_screened_this_round=10,
        wall_clock_breached=False,
        round_cap=2,
    )
    assert decision == StopDecision(True, "budget_exhausted")


# --- D5 search.target: evaluate_deep_stop override ---


def test_deep_stop_default_target_is_as_built_constant() -> None:
    """Absent target ≡ as-built: default param equals TARGET_CONFIDENT_RELEVANT."""
    decision = evaluate_deep_stop(
        round_index=1,
        confident_relevant=TARGET_CONFIDENT_RELEVANT,
        new_confident_relevant=TARGET_CONFIDENT_RELEVANT,
        docs_screened_this_round=100,
        wall_clock_breached=False,
    )
    assert decision == StopDecision(True, "target_reached")


def test_deep_stop_custom_target_honours_lower_override() -> None:
    # Below the as-built target, but the D5 override of 10 is reached.
    decision = evaluate_deep_stop(
        round_index=1,
        confident_relevant=10,
        new_confident_relevant=10,
        docs_screened_this_round=100,
        wall_clock_breached=False,
        target=10,
    )
    assert decision == StopDecision(True, "target_reached")


def test_deep_stop_custom_target_not_yet_reached() -> None:
    # confident_relevant (15) is below the as-built default (20) but WOULD
    # trip the as-built target; a raised override (40) means it hasn't
    # stopped on the target check, honouring the override rather than the
    # module constant.
    decision = evaluate_deep_stop(
        round_index=1,
        confident_relevant=15,
        new_confident_relevant=15,
        docs_screened_this_round=100,
        wall_clock_breached=False,
        target=40,
    )
    assert decision == StopDecision(False, None)
