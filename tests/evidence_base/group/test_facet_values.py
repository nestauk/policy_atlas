from __future__ import annotations

from typing import Any

import pytest

from policy_atlas.core.schema import DIRECTIVE_STRING_MAX, EFFECT_DIRECTIONS
from policy_atlas.evidence_base.group.facet_values import (
    COUNTERPART_CAP,
    AcceptedGroup,
    FacetDirectiveError,
    FindingFacetView,
    InvalidPartitionOutput,
    assert_grouping_invariants,
    build_groups_payload,
    direction_spread,
    extract_facet_values,
    normalize_value,
    parse_grouping_directive,
)


def finding(
    finding_id: str,
    facet_value: str | None,
    counterpart_value: str | None = None,
    effect_direction: str | None = "increase",
    kind: str = "iof",
) -> FindingFacetView:
    return FindingFacetView(
        finding_id=finding_id,
        facet_value=facet_value,
        counterpart_value=counterpart_value,
        effect_direction=effect_direction,
        kind=kind,
    )


def test_normalize_casefolds_and_collapses_whitespace_without_stemming() -> None:
    assert normalize_value("Housing  First\t") == "housing first"
    assert normalize_value("housing") != normalize_value("housings")

    values, _ = extract_facet_values(
        [
            finding("f1", "housing"),
            finding("f2", "housings"),
        ]
    )

    assert [(value.value_id, value.normalized) for value in values] == [
        ("v1", "housing"),
        ("v2", "housings"),
    ]


def test_surface_election_uses_frequency_then_lexicographic_tie_break() -> None:
    frequent_values, _ = extract_facet_values(
        [
            finding("f1", "Housing First"),
            finding("f2", "housing first"),
            finding("f3", "Housing First"),
        ]
    )
    tied_values, _ = extract_facet_values(
        [
            finding("f1", "zeta"),
            finding("f2", "Alpha"),
            finding("f3", "Alpha"),
            finding("f4", "zeta"),
        ]
    )

    assert frequent_values[0].surface == "Housing First"
    assert tied_values[0].surface == "Alpha"


def test_value_id_assignment_is_deterministic_for_shuffled_input() -> None:
    ordered, _ = extract_facet_values(
        [
            finding("f1", "Rapid rehousing"),
            finding("f2", "Housing First"),
            finding("f3", "Breakfast clubs"),
        ]
    )
    shuffled, _ = extract_facet_values(
        [
            finding("f3", "Breakfast clubs"),
            finding("f1", "Rapid rehousing"),
            finding("f2", "Housing First"),
        ]
    )

    assert [(value.value_id, value.normalized) for value in ordered] == [
        (value.value_id, value.normalized) for value in shuffled
    ]


def test_counterparts_are_deduped_ranked_and_capped() -> None:
    values, _ = extract_facet_values(
        [
            finding("f1", "Housing First", "Beta"),
            finding("f2", "housing first", "beta"),
            finding("f3", "HOUSING FIRST", "Alpha"),
            finding("f4", "Housing First", "alpha"),
            finding("f5", "Housing First", "alpha"),
            finding("f6", "Housing First", "Delta"),
            finding("f7", "Housing First", "Gamma"),
            finding("f8", "Housing First", "Epsilon"),
            finding("f9", "Housing First", "Zeta"),
            finding("f10", "Housing First", None),
            finding("f11", "Housing First", ""),
            finding("f12", "Housing First", "   "),
        ]
    )

    assert values[0].counterparts == ("alpha", "Beta", "Delta", "Epsilon", "Gamma")
    assert len(values[0].counterparts) == COUNTERPART_CAP


def test_parse_grouping_directive_defaults_and_valid_scope_context() -> None:
    assert parse_grouping_directive({}) == (["intervention"], "default")
    assert parse_grouping_directive({"grouping": {}}) == (["intervention"], "default")
    assert parse_grouping_directive({"grouping": {"facet": "outcome"}}) == (
        ["outcome"],
        "scope_context",
    )
    assert parse_grouping_directive(
        {"grouping": {"facets": ["outcome", "barrier_theme"]}}
    ) == (
        ["outcome", "barrier_theme"],
        "scope_context",
    )


@pytest.mark.parametrize(
    "context",
    [
        {"grouping": "outcome"},
        {"grouping": {"facet": "outcome", "extra": True}},
        {"grouping": {"facet": "outcome", "facets": ["outcome"]}},
        {"grouping": {"facet": 3}},
        {"grouping": {"facets": []}},
        {"grouping": {"facets": ["outcome", "outcome"]}},
        {"grouping": {"facets": ["outcome", 3]}},
        {"grouping": {"facet": "mechanism"}},
        {"grouping": {"facet": "out\ncome"}},
        {"grouping": {"facet": "x" * (DIRECTIVE_STRING_MAX + 1)}},
    ],
)
def test_parse_grouping_directive_rejects_malformed_directives(
    context: dict[str, Any]
) -> None:
    with pytest.raises(FacetDirectiveError):
        parse_grouping_directive(context)


def test_build_groups_payload_and_invariants_cover_all_buckets_and_directions() -> None:
    findings = [
        finding("f1", "Housing First", "rough sleeping", "increase"),
        finding("f2", "housing first", "tenancy", "mixed"),
        finding("f3", "Rapid rehousing", "homelessness", "unclear"),
        finding("f4", "Breakfast clubs", "attendance", "unclear"),
        finding("f5", None, "wellbeing", "no_effect"),
        finding("f6", "  ", "wellbeing", "mixed"),
    ]
    values, no_value = extract_facet_values(findings)
    groups = [
        AcceptedGroup("School breakfast clubs", "School provision.", ("v1",)),
        AcceptedGroup("Housing-led support", "Housing interventions.", ("v2",)),
    ]

    payload = build_groups_payload(
        findings,
        facet="intervention",
        values=values,
        groups=groups,
        ungrouped_value_ids={"v3"},
        no_value_finding_ids=no_value,
    )
    facet_payload = payload["intervention"]

    assert facet_payload["groups"] == [
        {
            "group_id": "intervention:g01",
            "facet": "intervention",
            "label": "School breakfast clubs",
            "description": "School provision.",
            "member_values": ["Breakfast clubs"],
            "member_finding_ids": ["f4"],
            "member_finding_kinds": ["iof"],
            "member_counts": {"iof": 1, "icf": 0},
            "size": 1,
            "direction_spread": {
                "increase": 0,
                "decrease": 0,
                "no_effect": 0,
                "mixed": 0,
                "unclear": 1,
            },
        },
        {
            "group_id": "intervention:g02",
            "facet": "intervention",
            "label": "Housing-led support",
            "description": "Housing interventions.",
            "member_values": ["Housing First"],
            "member_finding_ids": ["f1", "f2"],
            "member_finding_kinds": ["iof", "iof"],
            "member_counts": {"iof": 2, "icf": 0},
            "size": 2,
            "direction_spread": {
                "increase": 1,
                "decrease": 0,
                "no_effect": 0,
                "mixed": 1,
                "unclear": 0,
            },
        },
    ]
    assert facet_payload["ungrouped"] == {
        "values": ["Rapid rehousing"],
        "finding_ids": ["f3"],
        "member_finding_ids": ["f3"],
        "finding_kinds": ["iof"],
        "member_counts": {"iof": 1, "icf": 0},
        "direction_spread": {
            "increase": 0,
            "decrease": 0,
            "no_effect": 0,
            "mixed": 0,
            "unclear": 1,
        },
    }
    assert facet_payload["no_value"] == {
        "finding_ids": ["f5", "f6"],
        "member_finding_ids": ["f5", "f6"],
        "finding_kinds": ["iof", "iof"],
        "member_counts": {"iof": 2, "icf": 0},
        "direction_spread": {
            "increase": 0,
            "decrease": 0,
            "no_effect": 1,
            "mixed": 1,
            "unclear": 0,
        },
    }

    assert_grouping_invariants(payload, finding_ids=[finding.finding_id for finding in findings])

    duplicated = {
        "intervention": {
            **facet_payload,
            "groups": [
                {
                    **facet_payload["groups"][0],
                    "member_finding_ids": ["f4", "f4"],
                    "size": 2,
                    "direction_spread": {
                        "increase": 0,
                        "decrease": 0,
                        "no_effect": 0,
                        "mixed": 0,
                        "unclear": 2,
                    },
                },
                facet_payload["groups"][1],
            ],
        }
    }
    with pytest.raises(InvalidPartitionOutput):
        assert_grouping_invariants(
            duplicated, finding_ids=[finding.finding_id for finding in findings]
        )

    dropped = {
        "intervention": {
            **facet_payload,
            "no_value": {
                **facet_payload["no_value"],
                "finding_ids": ["f5"],
                "direction_spread": {
                    "increase": 0,
                    "decrease": 0,
                    "no_effect": 1,
                    "mixed": 0,
                    "unclear": 0,
                },
            },
        }
    }
    with pytest.raises(InvalidPartitionOutput):
        assert_grouping_invariants(
            dropped, finding_ids=[finding.finding_id for finding in findings]
        )


def test_build_groups_payload_counts_kinds_and_spreads_iof_only() -> None:
    findings = [
        finding("iof-1", "Alpha", "Outcome", "increase", kind="iof"),
        finding("icf-1", "Alpha", "Outcome", None, kind="icf"),
        finding("icf-2", None, "Outcome", None, kind="icf"),
    ]
    values, no_value = extract_facet_values(findings)
    payload = build_groups_payload(
        findings,
        facet="intervention",
        values=values,
        groups=[AcceptedGroup("Alpha", "Alpha members.", ("v1",))],
        ungrouped_value_ids=set(),
        no_value_finding_ids=no_value,
    )
    facet_payload = payload["intervention"]

    group = facet_payload["groups"][0]
    assert group["group_id"] == "intervention:g01"
    assert group["facet"] == "intervention"
    assert group["member_finding_ids"] == ["iof-1", "icf-1"]
    assert group["member_finding_kinds"] == ["iof", "icf"]
    assert group["member_counts"] == {"iof": 1, "icf": 1}
    assert sum(group["direction_spread"].values()) == 1
    assert facet_payload["no_value"]["finding_ids"] == ["icf-2"]
    assert facet_payload["no_value"]["finding_kinds"] == ["icf"]
    assert facet_payload["no_value"]["member_counts"] == {"iof": 0, "icf": 1}
    assert facet_payload["no_value"]["direction_spread"] == dict.fromkeys(EFFECT_DIRECTIONS, 0)
    assert_grouping_invariants(payload, finding_ids=[finding.finding_id for finding in findings])


def test_direction_spread_keys_come_from_the_schema_tuple_not_hardcoded_strings() -> None:
    """direction_spread must zero-fill from EFFECT_DIRECTIONS, never a literal list —
    otherwise a future vocabulary change (as in task 018 rider A5) silently
    stops flowing through this reader.
    """
    assert set(direction_spread([]).keys()) == set(EFFECT_DIRECTIONS)
    assert direction_spread([]) == dict.fromkeys(EFFECT_DIRECTIONS, 0)
