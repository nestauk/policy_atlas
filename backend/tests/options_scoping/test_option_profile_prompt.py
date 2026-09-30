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
    build_line_messages,
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


def test_the_line_questions_are_the_eight_line_keys_in_order() -> None:
    assert tuple(LINE_QUESTIONS) == PROFILE_LINE_KEYS
    assert tuple(LINE_NAMES) == PROFILE_LINE_KEYS


def test_six_lines_carry_a_mark() -> None:
    marked = {key for key in PROFILE_LINE_KEYS if line_is_marked(key)}
    assert marked == set(PROFILE_LINE_KEYS) - {"who_decides", "dependencies"}
    assert set(LINE_MARK_MEANING) == marked


@pytest.mark.parametrize("line_key", [k for k in PROFILE_LINE_KEYS if k != "who_decides"])
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
