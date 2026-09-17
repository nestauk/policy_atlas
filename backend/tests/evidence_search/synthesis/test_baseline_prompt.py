"""Pins for the ``baseline_template_v2`` surface (task 044, deliverable 7; A7, A14, C7, C18)."""

from __future__ import annotations

from policy_atlas.evidence_search.synthesis.baseline_prompt import (
    BASELINE_BAND,
    BASELINE_DEPTH_LABEL,
    BASELINE_PROMPT_VERSION,
    BASELINE_PROPOSED_INSERT_AFTER,
    BASELINE_PROPOSED_SECTIONS_MAX,
    BASELINE_RAPID_SECTIONS,
    BASELINE_SECTION_PREAMBLE,
    BASELINE_SECTIONS,
    BASELINE_SECTIONS_BY_DEPTH,
    SOURCES_NOT_SEARCHED_LINE,
    SOURCES_SECTION_TITLE,
    compile_intent,
    is_forbidden_proposed_title,
    required_titles,
)


def test_version_and_constants_pinned() -> None:
    assert BASELINE_PROMPT_VERSION == "baseline_template_v2"
    assert BASELINE_PROPOSED_SECTIONS_MAX == 2
    assert BASELINE_PROPOSED_INSERT_AFTER == "What is contested"
    assert BASELINE_BAND == "the situation these options would change"
    assert BASELINE_DEPTH_LABEL == "scoping pass"


def test_eight_required_sections_in_the_ruled_order() -> None:
    assert required_titles() == (
        "What is in place",
        "Trend if nothing changes",
        "Who is affected",
        "What is already changing",
        "What is contested",
        "Cost of inaction",
        "Key assumption",
        SOURCES_SECTION_TITLE,
    )
    assert required_titles("standard") == required_titles()
    assert len(BASELINE_SECTIONS) == 7  # the eighth, Sources, is rendered by code
    assert all(section.turn_cap >= 1 for section in BASELINE_SECTIONS)


def test_rapid_writes_five_sections_merging_two_pairs() -> None:
    """Owner ruling 2026-09-17 (phase 8): in place + already changing, trend + cost."""
    assert required_titles("rapid") == (
        "What is in place and already changing",
        "Trend and cost if nothing changes",
        "Who is affected",
        "What is contested",
        "Key assumption",
        SOURCES_SECTION_TITLE,
    )
    assert len(BASELINE_RAPID_SECTIONS) == 5
    assert BASELINE_SECTIONS_BY_DEPTH == {
        "standard": BASELINE_SECTIONS,
        "rapid": BASELINE_RAPID_SECTIONS,
    }
    by_title = {section.title: section.focus for section in BASELINE_RAPID_SECTIONS}
    merged_in_place = by_title["What is in place and already changing"]
    assert "policies, programmes, entitlements and services" in merged_in_place
    assert "announced reforms, pilots, funding changes" in merged_in_place
    merged_trend = by_title["Trend and cost if nothing changes"]
    assert "never converted or summed across sources" in merged_trend
    assert "gap claim" in merged_trend
    # The three carried sections are the standard objects, not copies.
    assert BASELINE_RAPID_SECTIONS[2:] == (
        BASELINE_SECTIONS[2],
        BASELINE_SECTIONS[4],
        BASELINE_SECTIONS[6],
    )
    assert all(len(section.focus) <= 600 for section in BASELINE_RAPID_SECTIONS)


def test_reasoning_sections_are_labelled_and_not_found_is_a_gap() -> None:
    by_title = {section.title: section.focus for section in BASELINE_SECTIONS}
    assert "labelled as reasoning" in by_title["Key assumption"]
    assert "label that sentence as reasoning" in by_title["What is contested"]
    assert "gap claim" in by_title["Trend if nothing changes"]
    assert "does not forecast" in BASELINE_SECTION_PREAMBLE
    assert "never propose, compare or evaluate interventions" in BASELINE_SECTION_PREAMBLE


def test_sources_wording_names_what_was_not_searched() -> None:
    assert "Live official statistics and departmental pages were not searched" in (
        SOURCES_NOT_SEARCHED_LINE
    )


def test_forbidden_proposed_titles() -> None:
    assert is_forbidden_proposed_title("Conclusions")
    assert is_forbidden_proposed_title("key findings")
    assert is_forbidden_proposed_title("Who is affected")
    assert is_forbidden_proposed_title("Trend and cost if nothing changes")  # a rapid title
    assert not is_forbidden_proposed_title("How this varies by place")


def test_compile_intent_is_deterministic_and_carries_the_four_inputs() -> None:
    text = compile_intent(
        target_unit="young people aged 16 to 24 who are NEET",
        where="United Kingdom",
        intended_change="Reduce the number of 16 to 24 year olds who are NEET.",
        outcomes=["NEET rate", "sustained employment at 12 months"],
    )
    assert text == compile_intent(
        target_unit="young people aged 16 to 24 who are NEET",
        where="United Kingdom",
        intended_change="Reduce the number of 16 to 24 year olds who are NEET.",
        outcomes=["NEET rate", "sustained employment at 12 months"],
    )
    for piece in ("young people aged 16 to 24", "United Kingdom", "Reduce the number", "NEET rate"):
        assert piece in text
