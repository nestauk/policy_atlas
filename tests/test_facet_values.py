from __future__ import annotations

from typing import Any

import pytest

from policy_atlas.facet_grouping import (
    DESCRIPTION_MAX,
    FORBIDDEN_GROUP_LABELS,
    LABEL_MAX,
    PartitionResult,
)
from policy_atlas.facet_values import (
    COUNTERPART_CAP,
    AcceptedGroup,
    FacetDirectiveError,
    FindingFacetView,
    InvalidPartitionOutput,
    assert_grouping_invariants,
    build_groups_payload,
    extract_facet_values,
    merge_repair,
    normalize_value,
    parse_grouping_directive,
    validate_partition,
    value_records,
)
from policy_atlas.schema import DIRECTIVE_STRING_MAX


def finding(
    finding_id: str,
    facet_value: str | None,
    counterpart_value: str | None = None,
    effect_direction: str = "positive",
) -> FindingFacetView:
    return FindingFacetView(
        finding_id=finding_id,
        facet_value=facet_value,
        counterpart_value=counterpart_value,
        effect_direction=effect_direction,
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


def test_value_records_use_surface_count_and_counterparts() -> None:
    values, _ = extract_facet_values(
        [
            finding("f1", "Housing First", "rough sleeping"),
            finding("f2", "housing first", "rough sleeping"),
        ]
    )

    assert value_records(values) == [
        {
            "id": "v1",
            "value": "Housing First",
            "finding_count": 2,
            "counterparts": ["rough sleeping"],
        }
    ]


def test_parse_grouping_directive_defaults_and_valid_scope_context() -> None:
    assert parse_grouping_directive({}) == ("intervention", "default")
    assert parse_grouping_directive({"grouping": {}}) == ("intervention", "default")
    assert parse_grouping_directive({"grouping": {"facet": "outcome"}}) == (
        "outcome",
        "scope_context",
    )


@pytest.mark.parametrize(
    "context",
    [
        {"grouping": "outcome"},
        {"grouping": {"facet": "outcome", "extra": True}},
        {"grouping": {"facet": 3}},
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


def test_validate_partition_accepts_strips_and_returns_missing_ids() -> None:
    validated = validate_partition(
        {
            "groups": [
                {
                    "label": " Housing-led support ",
                    "description": " Housing interventions. ",
                    "member_ids": ["v1", "v2"],
                }
            ],
            "ungroupable": ["v3"],
        },
        value_ids={"v1", "v2", "v3", "v4"},
    )

    assert validated.groups == (
        AcceptedGroup(
            label="Housing-led support",
            description="Housing interventions.",
            member_ids=("v1", "v2"),
        ),
    )
    assert validated.ungroupable_ids == ("v3",)
    assert validated.missing_ids == frozenset({"v4"})


@pytest.mark.parametrize(
    "result",
    [
        {
            "groups": [{"label": "A", "description": "B", "member_ids": ["v9"]}],
            "ungroupable": [],
        },
        {
            "groups": [
                {"label": "A", "description": "B", "member_ids": ["v1"]},
                {"label": "C", "description": "D", "member_ids": ["v1"]},
            ],
            "ungroupable": [],
        },
        {
            "groups": [{"label": "A", "description": "B", "member_ids": ["v1", "v2"]}],
            "ungroupable": ["v2"],
        },
        {
            "groups": [{"label": "A", "description": "B", "member_ids": ["v1", "v1"]}],
            "ungroupable": [],
        },
        {
            "groups": [{"label": "A", "description": "B", "member_ids": ["v1"]}],
            "ungroupable": ["v1"],
        },
        {
            "groups": [{"label": "A", "description": "B", "member_ids": []}],
            "ungroupable": [],
        },
        {
            "groups": [{"label": "  ", "description": "B", "member_ids": ["v1"]}],
            "ungroupable": [],
        },
        {
            "groups": [{"label": "A", "description": "  ", "member_ids": ["v1"]}],
            "ungroupable": [],
        },
        {
            "groups": [{"label": "x" * (LABEL_MAX + 1), "description": "B", "member_ids": ["v1"]}],
            "ungroupable": [],
        },
        {
            "groups": [
                {
                    "label": "A",
                    "description": "x" * (DESCRIPTION_MAX + 1),
                    "member_ids": ["v1"],
                }
            ],
            "ungroupable": [],
        },
        {
            "groups": [{"label": "Bad\nLabel", "description": "B", "member_ids": ["v1"]}],
            "ungroupable": [],
        },
        {
            "groups": [
                {"label": "A", "description": "B", "member_ids": ["v1"]},
                {"label": "a", "description": "C", "member_ids": ["v2"]},
            ],
            "ungroupable": [],
        },
    ],
)
def test_validate_partition_rejects_invalid_output(result: PartitionResult) -> None:
    with pytest.raises(InvalidPartitionOutput):
        validate_partition(result, value_ids={"v1", "v2", "v3"})


@pytest.mark.parametrize("label", sorted(FORBIDDEN_GROUP_LABELS) + ["General", "OTHER"])
def test_validate_partition_rejects_forbidden_labels(label: str) -> None:
    with pytest.raises(InvalidPartitionOutput):
        validate_partition(
            {
                "groups": [{"label": label, "description": "B", "member_ids": ["v1"]}],
                "ungroupable": [],
            },
            value_ids={"v1"},
        )


def test_merge_repair_merges_casefold_label_matches_and_appends_new_groups() -> None:
    accepted = [
        AcceptedGroup("Housing First", "Original description.", ("v1",)),
        AcceptedGroup("School meals", "Meals.", ("v2",)),
    ]
    repair = [
        AcceptedGroup("housing first", "Replacement ignored.", ("v3",)),
        AcceptedGroup("Rapid rehousing", "Rapid.", ("v4",)),
    ]

    assert merge_repair(accepted, repair) == [
        AcceptedGroup("Housing First", "Original description.", ("v1", "v3")),
        AcceptedGroup("School meals", "Meals.", ("v2",)),
        AcceptedGroup("Rapid rehousing", "Rapid.", ("v4",)),
    ]


def test_build_groups_payload_and_invariants_cover_all_buckets_and_directions() -> None:
    findings = [
        finding("f1", "Housing First", "rough sleeping", "positive"),
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
        values=values,
        groups=groups,
        ungrouped_value_ids={"v3"},
        no_value_finding_ids=no_value,
    )

    assert payload["groups"] == [
        {
            "label": "School breakfast clubs",
            "description": "School provision.",
            "member_values": ["Breakfast clubs"],
            "member_finding_ids": ["f4"],
            "size": 1,
            "direction_spread": {
                "positive": 0,
                "negative": 0,
                "no_effect": 0,
                "mixed": 0,
                "unclear": 1,
            },
        },
        {
            "label": "Housing-led support",
            "description": "Housing interventions.",
            "member_values": ["Housing First"],
            "member_finding_ids": ["f1", "f2"],
            "size": 2,
            "direction_spread": {
                "positive": 1,
                "negative": 0,
                "no_effect": 0,
                "mixed": 1,
                "unclear": 0,
            },
        },
    ]
    assert payload["ungrouped"] == {
        "values": ["Rapid rehousing"],
        "finding_ids": ["f3"],
        "direction_spread": {
            "positive": 0,
            "negative": 0,
            "no_effect": 0,
            "mixed": 0,
            "unclear": 1,
        },
    }
    assert payload["no_value"] == {
        "finding_ids": ["f5", "f6"],
        "direction_spread": {
            "positive": 0,
            "negative": 0,
            "no_effect": 1,
            "mixed": 1,
            "unclear": 0,
        },
    }

    assert_grouping_invariants(payload, finding_ids=[finding.finding_id for finding in findings])

    duplicated = {
        **payload,
        "groups": [
            {
                **payload["groups"][0],
                "member_finding_ids": ["f4", "f4"],
                "size": 2,
                "direction_spread": {
                    "positive": 0,
                    "negative": 0,
                    "no_effect": 0,
                    "mixed": 0,
                    "unclear": 2,
                },
            },
            payload["groups"][1],
        ],
    }
    with pytest.raises(InvalidPartitionOutput):
        assert_grouping_invariants(
            duplicated, finding_ids=[finding.finding_id for finding in findings]
        )

    dropped = {
        **payload,
        "no_value": {
            **payload["no_value"],
            "finding_ids": ["f5"],
            "direction_spread": {
                "positive": 0,
                "negative": 0,
                "no_effect": 1,
                "mixed": 0,
                "unclear": 0,
            },
        },
    }
    with pytest.raises(InvalidPartitionOutput):
        assert_grouping_invariants(
            dropped, finding_ids=[finding.finding_id for finding in findings]
        )
