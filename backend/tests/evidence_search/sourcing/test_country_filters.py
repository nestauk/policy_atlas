"""Pure tests for static country-filter tables and helpers."""

import pytest

from policy_atlas.evidence_search.sourcing.country_filters import (
    TIER1_GROUPS,
    SearchDirectiveError,
    expand_tier1,
    overton_display_names,
    validate_iso_alpha2,
)


def test_tier1_group_expansion_is_sorted_and_deterministic() -> None:
    first = expand_tier1("Europe")
    second = expand_tier1("Europe")

    assert first == second
    assert first == tuple(sorted(first))
    assert "GB" in first
    assert "GB" not in expand_tier1("EU27")


def test_tier1_group_counts_are_pinned() -> None:
    assert {label: len(countries) for label, countries in TIER1_GROUPS.items()} == {
        "OECD members": 38,
        "G7": 7,
        "G20": 19,
        "EU27": 27,
        "EEA": 30,
        "Europe": 51,
        "North America": 41,
        "Oceania": 29,
    }


def test_validate_iso_alpha2_rejects_unknown_code() -> None:
    with pytest.raises(SearchDirectiveError):
        validate_iso_alpha2(["GB", "ZZ"])


def test_overton_display_names_skips_unmapped_valid_codes() -> None:
    assert overton_display_names(["GB", "AX", "US"]) == {"UK", "USA"}
