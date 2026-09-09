"""The options-scoping plan model: what it refuses, and what it fills in.

Contract § Acceptance checks "scoping plan validation" (task 044). The theme
throughout: a scoping plan is mostly *claims about a problem*, and the only
protection against a claim that reads as fact but was a guess is that the model
refuses to store one untagged, unpinned or unpaired.
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from policy_atlas.runtime.capability_registry import (
    EVIDENCE_SEARCH,
    OPTIONS_SCOPING,
    UnknownCapability,
    spec_for,
    steer_points_for,
    validate_plan,
)
from policy_atlas.runtime.scoping_plan import (
    BASELINE_CONFIRM,
    BASELINE_TIME_BAND,
    SCOPING_STEER_POINTS,
    SCOPING_STEPS,
    ScopingPlan,
    build_scoping_plan,
)
from policy_atlas.runtime.task_agent_scoping_prompt import (
    ScopingConstraintWire,
    ScopingPlanDraftWire,
    ScopingSteerPointDefaultDraft,
    TaggedText,
    YourContextWire,
)


def _ready_draft(**overrides: object) -> ScopingPlanDraftWire:
    values: dict[str, object] = {
        "title": "Youth employment options",
        "question": "What could reduce the number of young people not in work?",
        "intended_change": TaggedText(
            text="Reduce the number of 16 to 24 year olds not in education, "
            "employment or training",
            origin="from_your_question",
        ),
        "target_unit": TaggedText(text="16 to 24 year olds", origin="your_call"),
        "outcomes": [TaggedText(text="the NEET rate", origin="assumed")],
        "depth": "standard",
    }
    values.update(overrides)
    return ScopingPlanDraftWire.model_validate(values)


# --- readiness --------------------------------------------------------------


def test_a_draft_without_depth_is_not_a_plan() -> None:
    """Depth is the one field the user must choose (OS ruling 25)."""
    with pytest.raises(ValidationError):
        build_scoping_plan(_ready_draft(depth=None))


def test_a_draft_without_a_target_unit_is_not_a_plan() -> None:
    with pytest.raises(ValidationError):
        build_scoping_plan(_ready_draft(target_unit=None))


def test_a_draft_without_an_outcome_is_not_a_plan() -> None:
    with pytest.raises(ValidationError):
        build_scoping_plan(_ready_draft(outcomes=[]))


def test_deep_is_not_a_scoping_depth() -> None:
    """Two settings, not three (D6). 'deep' is Evidence search vocabulary."""
    with pytest.raises(ValidationError):
        build_scoping_plan(_ready_draft(depth="deep"))


def test_an_invented_origin_tag_is_refused() -> None:
    """A tag outside the three is a claim with no provenance the user can read."""
    with pytest.raises(ValueError, match="origin"):
        build_scoping_plan(
            _ready_draft(
                target_unit=TaggedText(text="16 to 24 year olds", origin="obviously")
            )
        )


# --- what code fills in -----------------------------------------------------


def test_where_defaults_to_the_united_kingdom_tagged_assumed() -> None:
    plan = build_scoping_plan(_ready_draft())
    assert plan.where.text == "United Kingdom"
    assert plan.where.origin == "assumed"


def test_the_steps_and_the_band_are_code_supplied() -> None:
    plan = build_scoping_plan(_ready_draft())
    assert [step.label for step in plan.steps] == [step.label for step in SCOPING_STEPS]
    assert plan.time_band == BASELINE_TIME_BAND


def test_the_plan_version_records_the_turn_that_produced_it() -> None:
    """Turn provenance is at version grain, not field grain (C16)."""
    plan = build_scoping_plan(_ready_draft(), source_turn_index=3)
    assert plan.source_turn_index == 3


def test_linked_task_ids_come_from_the_links_not_the_model() -> None:
    source = uuid.uuid4()
    plan = build_scoping_plan(_ready_draft(), linked_task_ids=[source])
    assert plan.linked_task_ids == [source]


# --- constraints ------------------------------------------------------------


def test_a_constraint_kind_pins_when_it_is_checked() -> None:
    with pytest.raises(ValidationError, match="checked at"):
        build_scoping_plan(
            _ready_draft(
                constraints=[
                    ScopingConstraintWire(
                        text="no benefit cuts",
                        kind="requirement",
                        origin="from_your_question",
                        checked_at="retrieval",
                    )
                ]
            )
        )


def test_an_unknown_constraint_kind_is_refused() -> None:
    with pytest.raises(ValueError, match="not a known kind"):
        build_scoping_plan(
            _ready_draft(
                constraints=[
                    ScopingConstraintWire(
                        text="cheap",
                        kind="nice_to_have",
                        origin="assumed",
                        checked_at="assessment",
                    )
                ]
            )
        )


def test_a_requirement_may_not_carry_retrieval_fields() -> None:
    """A design requirement that claimed to filter retrieval would not filter it."""
    with pytest.raises(ValidationError, match="evidence_restriction"):
        build_scoping_plan(
            _ready_draft(
                constraints=[
                    ScopingConstraintWire(
                        text="delivered through schools",
                        kind="requirement",
                        origin="from_your_question",
                        checked_at="longlist",
                        published_after="2015-01-01",
                    )
                ]
            )
        )


def test_a_language_restriction_is_stored_whole(  # C8
) -> None:
    """The search grammar has no language filter, so the plan keeps the ask."""
    plan = build_scoping_plan(
        _ready_draft(
            constraints=[
                ScopingConstraintWire(
                    text="English-language only",
                    kind="evidence_restriction",
                    origin="from_your_question",
                    checked_at="retrieval",
                    languages=["English"],
                )
            ]
        )
    )
    assert plan.constraints[0].languages == ["English"]
    assert plan.constraints[0].checked_at == "retrieval"


# --- your context -----------------------------------------------------------


def test_your_context_keeps_the_users_words_and_its_turn() -> None:
    plan = build_scoping_plan(
        _ready_draft(
            your_context=[
                YourContextWire(
                    text="  we already run a youth offer in every Jobcentre  ",
                    type="present_fact",
                )
            ]
        ),
        source_turn_index=2,
    )
    entry = plan.your_context[0]
    assert entry.text == "  we already run a youth offer in every Jobcentre  "
    assert entry.turn_index == 2
    assert entry.test_as_condition is False


# --- steering ---------------------------------------------------------------


def test_the_default_steering_mode_is_moderate() -> None:
    assert build_scoping_plan(_ready_draft()).steering_mode == "moderate"


def test_unattended_must_write_the_baseline_default_down() -> None:
    with pytest.raises(ValidationError, match="undeclared default"):
        build_scoping_plan(_ready_draft(steering_mode="unattended"))


def test_unattended_with_the_default_is_a_plan() -> None:
    plan = build_scoping_plan(
        _ready_draft(
            steering_mode="unattended",
            steer_point_defaults=[
                ScopingSteerPointDefaultDraft(
                    steer_point=BASELINE_CONFIRM, action="proceed_flag"
                )
            ],
        )
    )
    assert plan.steer_point_defaults[0].steer_point == BASELINE_CONFIRM


def test_an_attended_plan_refuses_the_baseline_default() -> None:
    """In attended modes the gate pauses; a standing rule there never fires."""
    with pytest.raises(ValidationError, match="only valid under"):
        build_scoping_plan(
            _ready_draft(
                steering_mode="moderate",
                steer_point_defaults=[
                    ScopingSteerPointDefaultDraft(
                        steer_point=BASELINE_CONFIRM, action="proceed_flag"
                    )
                ],
            )
        )


def test_an_evidence_search_steer_point_is_not_a_scoping_one() -> None:
    with pytest.raises(ValidationError):
        build_scoping_plan(
            _ready_draft(
                steering_mode="unattended",
                steer_point_defaults=[
                    ScopingSteerPointDefaultDraft(
                        steer_point="synthesis_shape", action="proceed_flag"
                    )
                ],
            )
        )


# --- the registry seam ------------------------------------------------------


def test_the_pinned_steer_points_match_the_registry() -> None:
    """The plan model cannot import the registry (cycle), so pin by test."""
    assert steer_points_for(OPTIONS_SCOPING) == SCOPING_STEER_POINTS


def test_the_scoping_lattice_holds_only_the_gate() -> None:
    lattice = spec_for(OPTIONS_SCOPING).lattice
    assert set(lattice) == {BASELINE_CONFIRM}
    assert lattice[BASELINE_CONFIRM].component == "synthesise"
    assert lattice[BASELINE_CONFIRM].boundary == "after_component"


def test_the_gate_is_absent_from_the_evidence_search_lattice() -> None:
    """A2: a flat table would fire the scoping pause on an ES walk."""
    assert BASELINE_CONFIRM not in spec_for(EVIDENCE_SEARCH).lattice
    assert BASELINE_CONFIRM not in steer_points_for(EVIDENCE_SEARCH)


def test_an_evidence_search_plan_rejects_a_baseline_confirm_default() -> None:
    """A18d, through the standing-default validator the ES plan already has."""
    with pytest.raises(ValidationError):
        validate_plan(
            EVIDENCE_SEARCH,
            {
                "title": "t",
                "question": "q",
                "backend_scope": "both",
                "search_effort": "standard",
                "analysis_depth": "landscape",
                "steering_mode": "unattended",
                "steer_point_defaults": [
                    {"steer_point": BASELINE_CONFIRM, "action": "proceed_flag"}
                ],
            },
        )


def test_a_scoping_payload_is_not_an_evidence_search_plan() -> None:
    payload = build_scoping_plan(_ready_draft()).model_dump(mode="json")
    with pytest.raises(ValidationError):
        validate_plan(EVIDENCE_SEARCH, payload)


def test_an_evidence_search_payload_is_not_a_scoping_plan() -> None:
    payload = {
        "title": "t",
        "question": "q",
        "backend_scope": "both",
        "search_effort": "standard",
        "analysis_depth": "landscape",
        "steering_mode": "moderate",
    }
    with pytest.raises(ValidationError):
        validate_plan(OPTIONS_SCOPING, payload)


def test_a_scoping_payload_round_trips_through_the_registry() -> None:
    plan = build_scoping_plan(_ready_draft())
    revalidated = validate_plan(OPTIONS_SCOPING, plan.model_dump(mode="json"))
    assert isinstance(revalidated, ScopingPlan)
    assert revalidated == plan


def test_an_unknown_capability_is_still_a_typed_error() -> None:
    with pytest.raises(UnknownCapability):
        validate_plan("options_appraisal", {})


def test_a_linked_plan_round_trips_through_its_stored_json_payload() -> None:
    """044 live check: the stored payload carries UUIDs as strings; a strict
    item type made every linked scoping plan unreadable (500 on ``GET /plan``)."""
    from policy_atlas.runtime.capability_registry import OPTIONS_SCOPING, validate_plan

    source = uuid.uuid4()
    plan = build_scoping_plan(_ready_draft(), linked_task_ids=[source])
    back = validate_plan(OPTIONS_SCOPING, plan.model_dump(mode="json"))
    assert isinstance(back, ScopingPlan)
    assert back.linked_task_ids == [source]
