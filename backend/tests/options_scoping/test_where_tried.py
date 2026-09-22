"""Where tried (task 045, D20): study geography grouped against the plan's Where."""

from __future__ import annotations

import pytest

from policy_atlas.options_scoping.longlist.coverage import normalise_doi
from policy_atlas.options_scoping.longlist.where_tried import (
    countries_in,
    where_codes,
    where_group,
    where_labels,
)

UK = where_codes("United Kingdom")


@pytest.mark.parametrize(
    ("geography", "group"),
    [
        ("England", "where"),
        ("the UK", "where"),
        ("Northern Ireland", "where"),
        ("Denmark", "comparable"),
        ("Danish municipalities", "comparable"),
        ("12 OECD countries", "comparable"),
        ("New South Wales", "comparable"),
        ("Kenya", "other"),
        ("a large city", "unknown"),
        (None, "unknown"),
        ("English-language studies", "unknown"),
    ],
)
def test_a_geography_is_grouped_against_where(geography: str | None, group: str) -> None:
    assert where_group([geography], UK) == group


def test_a_document_in_where_and_elsewhere_is_in_where() -> None:
    assert where_group(["Kenya", "Wales"], UK) == "where"


def test_us_the_pronoun_is_not_the_united_states() -> None:
    assert countries_in("studies that told us little") == (frozenset(), False)
    assert countries_in("US states")[0] == frozenset({"US"})


def test_a_where_outside_the_mapping_leaves_the_where_group_empty() -> None:
    assert where_codes("Atlantis") == frozenset()
    assert where_group(["England"], frozenset()) == "comparable"


def test_the_labels_name_where_in_its_own_words() -> None:
    assert where_labels("Scotland")["where"] == "Scotland"
    assert where_labels("Scotland")["comparable"] == "comparable systems (OECD)"


@pytest.mark.parametrize(
    ("metadata", "doi"),
    [
        ({"doi": "https://doi.org/10.1/ABC"}, "10.1/abc"),
        ({"doi": " doi:10.1/abc "}, "10.1/abc"),
        ({"doi": ""}, None),
        ({}, None),
    ],
)
def test_the_doi_is_normalised_for_counting(metadata: dict[str, str], doi: str | None) -> None:
    assert normalise_doi(metadata) == doi
