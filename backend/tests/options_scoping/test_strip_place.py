"""The place strip and the sub-national table (task 046, S6, PA11, item 26).

The longlist must never reject evidence because of a place, and must never
remove a nationality that defines a population: the strip removes the plan's
Where and a known place only when a preposition leads it.
"""

from __future__ import annotations

import pytest

from policy_atlas.options_scoping.longlist.where_tried import (
    SUBNATIONAL_PLACES,
    names_place,
    strip_place,
)


def test_the_refugee_target_unit_loses_its_place_and_the_removal_is_recorded() -> None:
    cleaned, removed = strip_place(
        "refugees and asylum seekers living in Greater Manchester", "United Kingdom"
    )
    assert cleaned == "refugees and asylum seekers"
    assert removed == ["living in Greater Manchester"]
    assert not names_place(cleaned)


def test_in_the_uk_is_removed_with_its_article() -> None:
    cleaned, removed = strip_place("Reduce obesity among children in the UK.", None)
    assert cleaned == "Reduce obesity among children."
    assert removed == ["in the UK"]


def test_a_text_with_no_place_is_returned_unchanged() -> None:
    text = "young people  not in education, employment or training"
    assert strip_place(text, "United Kingdom") == (text, [])


def test_a_nationality_is_never_removed() -> None:
    assert strip_place("Polish migrant workers", "United Kingdom") == (
        "Polish migrant workers",
        [],
    )
    # Led by a preposition, a nationality adjective is still not a place.
    assert strip_place("children in Polish schools", None) == ("children in Polish schools", [])


def test_the_where_text_is_removed_where_it_appears_verbatim() -> None:
    assert strip_place("UK adults who are inactive", "UK") == (
        "adults who are inactive",
        ["UK"],
    )
    cleaned, removed = strip_place("adults in the United Kingdom, aged 60 to 70", "United Kingdom")
    assert cleaned == "adults, aged 60 to 70"
    assert removed == ["in the United Kingdom"]


def test_an_unled_place_that_is_not_where_stays() -> None:
    assert strip_place("UK adults", "France") == ("UK adults", [])


def test_a_list_of_known_places_goes_whole() -> None:
    cleaned, removed = strip_place("families across England and Wales, on low incomes", None)
    assert cleaned == "families, on low incomes"
    assert removed == ["across England and Wales"]


def test_us_the_pronoun_is_not_a_place() -> None:
    text = "services that work for us"
    assert strip_place(text, None) == (text, [])


@pytest.mark.parametrize(
    ("place", "code"),
    [
        ("Greater Manchester", "GB"),
        ("the West Midlands", "GB"),
        ("Ontario", "CA"),
        ("Queensland", "AU"),
        ("West Virginia", "US"),
    ],
)
def test_the_sub_national_table_resolves_a_place_to_its_country(place: str, code: str) -> None:
    assert names_place(place)
    assert SUBNATIONAL_PLACES[place.removeprefix("the ").casefold()] == code


def test_georgia_is_not_read_as_a_us_state() -> None:
    assert not names_place("Georgia")


def test_an_origin_is_part_of_the_population_and_stays() -> None:
    """PA11: "from" leads no removal; the origin defines the group."""
    assert strip_place("migrants from India", "United Kingdom") == ("migrants from India", [])


def test_a_removal_leaves_no_dangling_conjunction() -> None:
    """Found by the 046 replay on the stored refugee plan."""
    cleaned, removed = strip_place(
        "Adults granted refugee status in the last two years and living in Greater Manchester",
        "Greater Manchester",
    )
    assert cleaned == "Adults granted refugee status in the last two years"
    assert removed == ["living in Greater Manchester"]


def test_a_removed_where_leaves_no_dangling_of() -> None:
    """Found by the 046 planning replay on the obesity intended change."""
    cleaned, removed = strip_place(
        "Reduce childhood obesity in the most deprived areas of England.", "England"
    )
    assert cleaned == "Reduce childhood obesity in the most deprived areas."
    assert removed == ["England"]
