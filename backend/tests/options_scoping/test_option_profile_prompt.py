"""The ``option_profile_v1`` prompts (task 046 amendment 2, Phase 12b; R36, R37).

The eight line keys are the plan's; six lines carry a mark; the plan's Where
reaches the ``who_decides`` line only; the marked and the plain line prompts
differ by the mark rules alone.
"""

from __future__ import annotations

import pytest

from policy_atlas.options_scoping.option_profile.option_profile_prompt import (
    _MARK_RULES,
    LINE_MARK_MEANING,
    LINE_NAMES,
    LINE_QUESTIONS,
    MARKED_LINE_SYSTEM_PROMPT,
    PLAIN_LINE_SYSTEM_PROMPT,
    POTENTIAL_IMPACT_BASELINE_MAX_CHARS,
    POTENTIAL_IMPACT_SYSTEM_PROMPT,
    WHO_DECIDES_CONSIDERATIONS_BLOCK,
    PotentialImpactWire,
    build_line_messages,
    build_potential_impact_messages,
    line_is_marked,
)
from policy_atlas.runtime.scoping_plan import PROFILE_LINE_KEYS

_PLAN: dict[str, object] = {
    "question": "What could reduce the number of young people not in work?",
    "intended_change": "Reduce the number of young people not in work",
    "target_unit": "16 to 24 year olds",
    "outcomes": ["the NEET rate"],
}
_OPTIONS: list[dict[str, object]] = [
    {
        "option_id": "o1",
        "label": "Youth guarantee",
        "description": "A guaranteed offer.",
        "design_features": ["an offer within four months"],
        "evidence_records": [],
    }
]

_OTHER_LINES = [k for k in PROFILE_LINE_KEYS if k not in ("who_decides", "potential_impact")]


def test_the_line_questions_are_the_nine_line_keys_in_order() -> None:
    assert tuple(LINE_QUESTIONS) == PROFILE_LINE_KEYS
    assert tuple(LINE_NAMES) == PROFILE_LINE_KEYS
    assert len(PROFILE_LINE_KEYS) == 9
    assert PROFILE_LINE_KEYS[-1] == "potential_impact"


def test_seven_lines_carry_a_mark() -> None:
    marked = {key for key in PROFILE_LINE_KEYS if line_is_marked(key)}
    assert marked == set(PROFILE_LINE_KEYS) - {"who_decides", "dependencies"}
    assert set(LINE_MARK_MEANING) == marked


@pytest.mark.parametrize("line_key", _OTHER_LINES)
def test_where_given_to_another_line_raises(line_key: str) -> None:
    with pytest.raises(ValueError, match="who_decides"):
        build_line_messages(
            line_key=line_key,
            plan=_PLAN,
            where="Powys",
            baseline_sections=[],
            options=_OPTIONS,
        )


def test_where_reaches_the_who_decides_line() -> None:
    messages = build_line_messages(
        line_key="who_decides",
        plan=_PLAN,
        where="Powys",
        baseline_sections=[],
        options=_OPTIONS,
    )
    assert "Powys" in str(messages[1]["content"])
    assert messages[0]["content"] == PLAIN_LINE_SYSTEM_PROMPT


def test_the_marked_and_plain_prompts_differ_only_by_the_mark_rules() -> None:
    assert MARKED_LINE_SYSTEM_PROMPT != PLAIN_LINE_SYSTEM_PROMPT
    assert MARKED_LINE_SYSTEM_PROMPT.replace(_MARK_RULES + "\n", "", 1) == (
        PLAIN_LINE_SYSTEM_PROMPT
    )


# --- task 046, amendment 4 (R89; S35; contract review C1) ----------------------------------

_WHO_CAN_ACT = "Only the council can act; it cannot change national law"


@pytest.mark.parametrize("line_key", _OTHER_LINES)
def test_considerations_given_to_another_line_raises(line_key: str) -> None:
    with pytest.raises(ValueError, match="who_decides"):
        build_line_messages(
            line_key=line_key,
            plan=_PLAN,
            where=None,
            baseline_sections=[],
            options=_OPTIONS,
            considerations=[_WHO_CAN_ACT],
        )


def test_the_considerations_reach_the_who_decides_user_message_as_a_json_list() -> None:
    messages = build_line_messages(
        line_key="who_decides",
        plan=_PLAN,
        where="Powys",
        baseline_sections=[],
        options=_OPTIONS,
        considerations=[_WHO_CAN_ACT, "Not the Treasury"],
    )
    user = str(messages[1]["content"])
    assert f'["{_WHO_CAN_ACT}", "Not the Treasury"]' in user
    assert WHO_DECIDES_CONSIDERATIONS_BLOCK.split("{")[0] in user


def test_no_considerations_leaves_the_who_decides_prompt_as_it_was() -> None:
    omitted = build_line_messages(
        line_key="who_decides",
        plan=_PLAN,
        where="Powys",
        baseline_sections=[],
        options=_OPTIONS,
    )
    none_given: list[str] | None
    for none_given in (None, []):
        assert (
            build_line_messages(
                line_key="who_decides",
                plan=_PLAN,
                where="Powys",
                baseline_sections=[],
                options=_OPTIONS,
                considerations=none_given,
            )
            == omitted
        )
    assert WHO_DECIDES_CONSIDERATIONS_BLOCK.split("{")[0] not in str(omitted[1]["content"])


# --- task 055, item 6: the Potential impact line --------------------------------------------


def test_potential_impact_is_a_marked_line() -> None:
    """Owner, 2026-10-27 (055 review): a lower/middle/higher mark and a grid column."""
    assert line_is_marked("potential_impact") is True
    assert "potential_impact" in LINE_MARK_MEANING
    assert "stands_out" in PotentialImpactWire.model_fields
    assert "The mark (stands_out)" in POTENTIAL_IMPACT_SYSTEM_PROMPT
    assert LINE_NAMES["potential_impact"] == "Potential impact"


def test_potential_impact_messages_carry_the_baseline_and_the_outcomes_as_written() -> None:
    plan = {**_PLAN, "where": "Powys"}
    messages = build_potential_impact_messages(
        plan=plan,
        baseline_sections=[("Drivers", "Employers hire few under-25s.")],
        options=_OPTIONS,
    )
    user = str(messages[1]["content"])
    assert "Employers hire few under-25s." in user
    assert "the NEET rate" in user
    assert "Powys" in user
    assert "cut at" not in user


def test_potential_impact_messages_name_a_cut_of_a_long_baseline() -> None:
    long_text = "x" * (POTENTIAL_IMPACT_BASELINE_MAX_CHARS + 500)
    messages = build_potential_impact_messages(
        plan=_PLAN, baseline_sections=[("Drivers", long_text)], options=_OPTIONS
    )
    user = str(messages[1]["content"])
    assert f"cut at {POTENTIAL_IMPACT_BASELINE_MAX_CHARS} characters" in user
    assert "x" * (POTENTIAL_IMPACT_BASELINE_MAX_CHARS + 1) not in user
