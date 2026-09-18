"""Pins for the ``baseline_template_v1`` surface (task 044, deliverable 7; A7, A14, C7, C18)."""

from __future__ import annotations

from policy_atlas.evidence_search.synthesis.baseline_prompt import (
    BASELINE_BAND,
    BASELINE_DEPTH_LABEL,
    BASELINE_PROMPT_VERSION,
    BASELINE_PROPOSED_INSERT_AFTER,
    BASELINE_PROPOSED_SECTIONS_MAX,
    BASELINE_SECTION_PREAMBLE,
    BASELINE_SECTIONS,
    SOURCES_NOT_SEARCHED_LINE,
    SOURCES_SECTION_TITLE,
    compile_intent,
    is_forbidden_proposed_title,
    required_titles,
)


def test_version_and_constants_pinned() -> None:
    assert BASELINE_PROMPT_VERSION == "baseline_template_v1"
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
    assert len(BASELINE_SECTIONS) == 7  # the eighth, Sources, is rendered by code
    assert all(section.turn_cap >= 1 for section in BASELINE_SECTIONS)


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
