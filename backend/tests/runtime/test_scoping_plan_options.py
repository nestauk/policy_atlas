"""The scoping plan's task 045 slots (D19, D21, D22).

Contract § Acceptance checks, plan and intent: ``your_options`` validates, is
optional, keeps verbatim text and turn index; the design is proposed back and
re-proposed on a text change; every new scoping plan carries the default
transferability preference, assumed, checked at assessment, following Where
until edited, removable and not re-minted.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from policy_atlas.runtime.agent_backend import StubAgentBackend
from policy_atlas.runtime.capability_registry import OPTIONS_SCOPING, validate_plan
from policy_atlas.runtime.option_design_prompt import OptionDesignWire
from policy_atlas.runtime.scoping_plan import (
    LONGLIST_PURPOSE,
    SCOPING_STEPS,
    TARGETED_PURPOSE,
    TRANSFERABILITY_DEFAULT,
    ScopingConstraint,
    ScopingPlan,
    YourOption,
    build_scoping_plan,
    compose_scoping,
    ensure_option_designs,
    find_default,
    settle_patched_defaults,
    wire_draft_from_plan,
)
from policy_atlas.runtime.task_agent_scoping_prompt import (
    ScopingConstraintWire,
    ScopingPlanDraftWire,
    TaggedText,
    YourOptionWire,
)


def _draft(**overrides: object) -> ScopingPlanDraftWire:
    values: dict[str, object] = {
        "title": "Youth employment options",
        "question": "What could reduce the number of young people not in work?",
        "intended_change": TaggedText(text="Fewer young people out of work", origin="assumed"),
        "target_unit": TaggedText(text="16 to 24 year olds", origin="your_call"),
        "outcomes": [TaggedText(text="the NEET rate", origin="assumed")],
        "depth": "standard",
    }
    values.update(overrides)
    return ScopingPlanDraftWire.model_validate(values)


def _options(*texts: str) -> list[YourOptionWire]:
    return [YourOptionWire(text=text) for text in texts]


def _default(plan: ScopingPlan) -> ScopingConstraint | None:
    return find_default(plan, TRANSFERABILITY_DEFAULT)


# --- your_options -------------------------------------------------------------


def test_your_options_is_optional() -> None:
    assert build_scoping_plan(_draft()).your_options == []


def test_your_options_keep_the_users_words_and_the_approving_turn() -> None:
    plan = build_scoping_plan(
        _draft(your_options=_options("  a youth guarantee, like Finland's  ")),
        source_turn_index=4,
    )
    [option] = plan.your_options
    assert option.text == "  a youth guarantee, like Finland's  "
    assert option.turn_index == 4
    assert option.design is None


def test_a_blank_option_is_refused() -> None:
    with pytest.raises(ValidationError):
        build_scoping_plan(_draft(your_options=_options("   ")))
    with pytest.raises(ValidationError):
        YourOption.model_validate({"text": "x", "turn_index": 0, "extra": 1})


def test_the_design_is_proposed_back_once_per_option() -> None:
    agent = StubAgentBackend()
    plan = build_scoping_plan(_draft(your_options=_options("a youth guarantee", "wage subsidies")))
    designed = ensure_option_designs(plan, agent)
    assert [o.design.name for o in designed.your_options if o.design] == [
        "a youth guarantee",
        "wage subsidies",
    ]
    assert agent.option_design_calls == 2
    # Nothing left to propose: no further call.
    assert ensure_option_designs(designed, agent) is designed
    assert agent.option_design_calls == 2


def test_a_reworded_option_loses_its_design_and_is_proposed_again() -> None:
    agent = StubAgentBackend()
    first = ensure_option_designs(
        build_scoping_plan(
            _draft(your_options=_options("a youth guarantee", "wage subsidies")),
            source_turn_index=2,
        ),
        agent,
    )
    second = build_scoping_plan(
        _draft(your_options=_options("wage subsidies", "a youth guarantee for under 25s")),
        source_turn_index=5,
        previous=first,
    )
    kept, reworded = second.your_options
    assert kept == first.your_options[1]
    assert kept.turn_index == 2
    assert reworded.design is None and reworded.turn_index == 5
    again = ensure_option_designs(second, agent)
    assert agent.option_design_words[-1] == "a youth guarantee for under 25s"
    assert all(o.design is not None for o in again.your_options)


def test_a_draft_that_leaves_options_null_keeps_the_previous_ones() -> None:
    first = build_scoping_plan(_draft(your_options=_options("a youth guarantee")))
    assert build_scoping_plan(_draft(), previous=first).your_options == first.your_options
    assert build_scoping_plan(_draft(your_options=[]), previous=first).your_options == []


def test_a_failed_proposal_leaves_the_option_without_a_design() -> None:
    class _Failing(StubAgentBackend):
        def propose_option_design(self, *args: object, **kwargs: object) -> OptionDesignWire:
            raise RuntimeError("provider down")

    plan = build_scoping_plan(_draft(your_options=_options("a youth guarantee")))
    assert ensure_option_designs(plan, _Failing()).your_options[0].design is None


def test_options_with_designs_round_trip_through_the_stored_payload() -> None:
    plan = ensure_option_designs(
        build_scoping_plan(_draft(your_options=_options("a youth guarantee"))),
        StubAgentBackend(),
    )
    again = validate_plan(OPTIONS_SCOPING, plan.model_dump(mode="json"))
    assert again == plan


def test_the_wire_draft_carries_the_options_words_only() -> None:
    plan = ensure_option_designs(
        build_scoping_plan(_draft(your_options=_options("a youth guarantee"))),
        StubAgentBackend(),
    )
    wire = wire_draft_from_plan(plan)
    assert wire["your_options"] == [{"text": "a youth guarantee"}]
    ScopingPlanDraftWire.model_validate(wire)


# --- the setting flag -----------------------------------------------------------


def test_only_a_requirement_may_name_a_setting() -> None:
    with pytest.raises(ValidationError):
        build_scoping_plan(
            _draft(
                constraints=[
                    ScopingConstraintWire(
                        text="Cheap to run",
                        kind="preference",
                        origin="your_call",
                        checked_at="assessment",
                        setting=True,
                    )
                ]
            )
        )


def test_the_setting_flag_survives_the_wire_round_trip() -> None:
    plan = build_scoping_plan(
        _draft(
            constraints=[
                ScopingConstraintWire(
                    text="Delivered through schools",
                    kind="requirement",
                    origin="your_call",
                    checked_at="longlist",
                    setting=True,
                )
            ]
        )
    )
    again = build_scoping_plan(ScopingPlanDraftWire.model_validate(wire_draft_from_plan(plan)))
    assert [c.setting for c in again.constraints if c.kind == "requirement"] == [True]


# --- the default transferability preference -------------------------------------


def test_every_new_plan_carries_the_default_preference() -> None:
    default = _default(build_scoping_plan(_draft()))
    assert default is not None
    assert default.text == "Transferable to United Kingdom"
    assert default.kind == "preference"
    assert default.origin == "assumed"
    assert default.checked_at == "assessment"


def test_the_default_follows_where_across_versions() -> None:
    first = build_scoping_plan(_draft())
    second = build_scoping_plan(
        _draft(where=TaggedText(text="Wales", origin="your_call")), previous=first
    )
    default = _default(second)
    assert default is not None and default.text == "Transferable to Wales"


def test_an_edited_default_stops_following_where() -> None:
    first = build_scoping_plan(_draft())
    data = first.model_dump(mode="json")
    for c in data["constraints"]:
        if c["default"]:
            c["text"] = "Transferable to rural areas"
    edited = settle_patched_defaults(ScopingPlan.model_validate(data), first)
    moved = build_scoping_plan(
        _draft(where=TaggedText(text="Wales", origin="your_call")), previous=edited
    )
    default = _default(moved)
    assert default is not None and default.text == "Transferable to rural areas"


def test_a_removed_default_is_recorded_and_not_minted_again() -> None:
    first = build_scoping_plan(_draft())
    data = first.model_dump(mode="json")
    data["constraints"] = [c for c in data["constraints"] if not c["default"]]
    removed = settle_patched_defaults(ScopingPlan.model_validate(data), first)
    assert _default(removed) is None
    assert removed.removed_defaults == [TRANSFERABILITY_DEFAULT]
    later = build_scoping_plan(
        _draft(where=TaggedText(text="Wales", origin="your_call")), previous=removed
    )
    assert _default(later) is None
    assert later.removed_defaults == [TRANSFERABILITY_DEFAULT]


def test_a_removed_default_cannot_be_carried() -> None:
    first = build_scoping_plan(_draft())
    data = first.model_dump(mode="json")
    data["removed_defaults"] = ["transferability"]
    with pytest.raises(ValidationError):
        ScopingPlan.model_validate(data)


def test_the_task_agent_cannot_author_the_default() -> None:
    plan = build_scoping_plan(
        _draft(
            constraints=[
                ScopingConstraintWire(
                    text="Transferable to the UK",
                    kind="preference",
                    origin="assumed",
                    checked_at="assessment",
                )
            ]
        )
    )
    preferences = [c for c in plan.constraints if c.kind == "preference"]
    assert [c.default for c in preferences] == [TRANSFERABILITY_DEFAULT]
    # And the Task Agent never sees it as its own on the next turn.
    wire = wire_draft_from_plan(plan)
    assert all(not c["text"].startswith("Transferable") for c in wire["constraints"])


def test_the_default_is_a_preference_only() -> None:
    with pytest.raises(ValidationError):
        ScopingConstraint(
            text="Transferable to Wales",
            kind="requirement",
            origin="assumed",
            checked_at="longlist",
            default=TRANSFERABILITY_DEFAULT,
        )


def test_a_plan_from_before_the_default_gets_one_on_its_next_version() -> None:
    legacy = build_scoping_plan(_draft())
    data = legacy.model_dump(mode="json")
    data["constraints"] = []
    older = ScopingPlan.model_validate(data)
    assert _default(build_scoping_plan(_draft(), previous=older)) is not None


# --- steps and directives ----------------------------------------------------------


def test_the_longlist_step_describes_the_walk() -> None:
    longlist = next(step for step in SCOPING_STEPS if step.label == "Longlist")
    assert longlist.blurb == (
        "Suggest options, search widely, read every abstract for the interventions "
        "it covers, cluster them into options, apply your constraints."
    )


@pytest.mark.parametrize("purpose", [LONGLIST_PURPOSE, TARGETED_PURPOSE])
def test_the_longlist_and_targeted_screens_carry_the_criteria_without_where(
    purpose: str,
) -> None:
    plan = build_scoping_plan(_draft(where=TaggedText(text="Northumberland", origin="your_call")))
    [screen] = [s for s in compose_scoping(plan, purpose).steps if s.component == "screen_abstract"]
    criteria = screen.directive_delta["screening"]["criteria"]
    assert any("16 to 24 year olds" in c for c in criteria)
    assert any("the NEET rate" in c for c in criteria)
    assert all("Northumberland" not in c for c in criteria)
