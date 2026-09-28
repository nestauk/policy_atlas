"""The longlist's PICO-shaped intent and screening criteria (task 045, D20, D21).

Contract § Acceptance checks, plan and intent: the compiled longlist intent
contains the target unit and outcomes and never Where; it contains the setting
only when a setting requirement exists; the screening criteria carry no place
and compose under the screen's ceiling.
"""

from __future__ import annotations

import pytest

from policy_atlas.evidence_search.assess.screen_prompt import SCREEN_INTENT_MAX
from policy_atlas.options_scoping.longlist_intent import (
    compile_longlist_intent,
    longlist_screening_criteria,
    setting_requirements,
)
from policy_atlas.runtime.scoping_plan import (
    ScopingPlan,
    build_scoping_plan,
    compose_longlist_screen_intent,
)
from policy_atlas.runtime.task_agent_scoping_prompt import (
    ScopingConstraintWire,
    ScopingPlanDraftWire,
    TaggedText,
)

_WHERE = "Northumberland"


def _plan(*constraints: ScopingConstraintWire, outcomes: list[str] | None = None) -> ScopingPlan:
    return build_scoping_plan(
        ScopingPlanDraftWire(
            question="What could reduce the number of young people not in work?",
            intended_change=TaggedText(text="Fewer young people out of work", origin="assumed"),
            target_unit=TaggedText(text="16 to 24 year olds", origin="your_call"),
            where=TaggedText(text=_WHERE, origin="your_call"),
            outcomes=[
                TaggedText(text=o, origin="assumed")
                for o in (outcomes or ["the NEET rate", "earnings at 25"])
            ],
            depth="standard",
            constraints=list(constraints),
        )
    )


def _setting() -> ScopingConstraintWire:
    return ScopingConstraintWire(
        text="Delivered through schools",
        kind="requirement",
        origin="your_call",
        checked_at="longlist",
        setting=True,
    )


def _requirement() -> ScopingConstraintWire:
    return ScopingConstraintWire(
        text="No new legislation",
        kind="requirement",
        origin="your_call",
        checked_at="longlist",
    )


def test_the_intent_carries_the_target_unit_and_outcomes_and_never_where() -> None:
    plan = _plan()
    intent = compile_longlist_intent(plan)
    assert "16 to 24 year olds" in intent
    assert "the NEET rate" in intent and "earnings at 25" in intent
    assert _WHERE not in intent
    # The default transferability preference names Where; it stays out too.
    assert "Transferable" not in intent


def test_the_intent_is_deterministic() -> None:
    assert compile_longlist_intent(_plan()) == compile_longlist_intent(_plan())


def test_the_setting_enters_only_as_a_stated_requirement() -> None:
    assert "Setting" not in compile_longlist_intent(_plan())
    assert "Setting" not in compile_longlist_intent(_plan(_requirement()))
    with_setting = _plan(_requirement(), _setting())
    assert setting_requirements(with_setting) == ["Delivered through schools"]
    assert "Setting: Delivered through schools." in compile_longlist_intent(with_setting)
    assert "No new legislation" not in compile_longlist_intent(with_setting)


def test_the_criteria_carry_target_unit_and_outcomes_and_no_place() -> None:
    criteria = longlist_screening_criteria(_plan())
    joined = " ".join(criteria)
    assert "16 to 24 year olds" in joined
    assert "the NEET rate" in joined
    assert _WHERE not in joined
    assert len(criteria) == 2


def test_the_criteria_carry_the_setting_only_when_required() -> None:
    criteria = longlist_screening_criteria(_plan(_setting()))
    assert len(criteria) == 3
    assert "Delivered through schools" in criteria[-1]
    assert _WHERE not in " ".join(criteria)


def test_the_criteria_compose_under_the_screen_ceiling() -> None:
    composed = compose_longlist_screen_intent(_plan(_setting()))
    assert len(composed) <= SCREEN_INTENT_MAX
    assert _WHERE not in composed


def test_an_over_long_plan_is_refused_not_truncated() -> None:
    plan = _plan(outcomes=[f"outcome number {i} " + "x" * 80 for i in range(12)])
    with pytest.raises(ValueError, match="cap"):
        compose_longlist_screen_intent(plan)
