"""The options-scoping baseline gate at the runner boundary (task 044, S4).

The gate is the whole point of the baseline: a scoping walk stops after
synthesise so the user can question the plan *before* any option is generated.
Four properties carry that:

- it pauses in every attended mode, because it is structural and not a floor
  trigger — a plan nobody confirmed is the failure this slice exists to prevent;
- under Unattended it does not pause but is **recorded and flagged**, so review
  can see that nobody confirmed it;
- an Evidence search walk never reaches it, whatever the mode — the point lives
  on the scoping lattice alone (A2);
- the card states an absent key assumption instead of hiding it.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import update
from sqlalchemy.engine import Engine

from policy_atlas.core.schema import task, task_plan
from policy_atlas.runtime.baseline_gate import (
    GATE_HEADING,
    KEY_ASSUMPTION_ABSENT,
    render_baseline_gate,
)
from policy_atlas.runtime.capability_registry import (
    EVIDENCE_SEARCH,
    OPTIONS_SCOPING,
    lattice_for,
)
from policy_atlas.runtime.runner import RunPlanOutcome, run_plan
from policy_atlas.runtime.scoping_plan import (
    BASELINE_CONFIRM,
    ScopingPlan,
    build_scoping_plan,
)
from policy_atlas.runtime.steering import lattice_policy
from policy_atlas.runtime.task_agent_scoping_prompt import ScopingPlanDraftWire
from policy_atlas.runtime.task_plan import SteeringMode
from tests.helpers import now
from tests.runtime.test_runner import _base_plan, _cleanup, _runner_backends, _seed_task
from tests.runtime.test_steering import ScriptedIO, _insert_plan_row

ATTENDED_MODES: tuple[SteeringMode, ...] = ("frequent", "moderate", "minimal")


def scoping_plan(**overrides: Any) -> ScopingPlan:
    """Build a minimal valid scoping plan for a runner walk."""
    values: dict[str, Any] = {
        "title": "Youth employment options",
        "question": "What could reduce the number of young people not in work?",
        "intended_change": {
            "text": "Reduce the number of young people not in work",
            "origin": "from_your_question",
        },
        "target_unit": {"text": "16 to 24 year olds", "origin": "your_call"},
        "outcomes": [{"text": "the NEET rate", "origin": "assumed"}],
        "depth": "standard",
    }
    values.update(overrides)
    return build_scoping_plan(ScopingPlanDraftWire.model_validate(values))


def seed_scoping_task(engine: Engine) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed an evidence-bearing task and mark it an options-scoping task."""
    task_id, scope_id = _seed_task(engine)
    with engine.begin() as conn:
        conn.execute(
            update(task).where(task.c.task_id == task_id).values(capability=OPTIONS_SCOPING)
        )
    return task_id, scope_id


def insert_scoping_plan_row(
    engine: Engine, *, task_id: uuid.UUID, scope_id: uuid.UUID, plan: ScopingPlan
) -> uuid.UUID:
    """Insert one approved scoping plan row and return its id."""
    plan_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            task_plan.insert().values(
                plan_id=plan_id,
                task_id=task_id,
                evidence_scope_id=scope_id,
                version=1,
                status="approved",
                payload=plan.model_dump(mode="json"),
                created_at=now(),
                created_by="task_agent",
                approved_at=now(),
            )
        )
    return plan_id


def run_scoping_walk(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
    plan: ScopingPlan,
    io: Any,
) -> tuple[RunPlanOutcome, uuid.UUID]:
    """Run one scoping walk to completion with the stub backends."""
    plan_id = insert_scoping_plan_row(engine, task_id=task_id, scope_id=scope_id, plan=plan)
    outcome = run_plan(
        engine,
        task_id=task_id,
        evidence_scope_id=scope_id,
        plan=plan,
        plan_id=plan_id,
        plan_version=1,
        plan_row_id=plan_id,
        backends=_runner_backends(),
        io=io,
    )
    return outcome, plan_id


def _gate_pauses(io: ScriptedIO) -> list[tuple[dict[str, Any], str]]:
    return [entry for entry in io.pauses if entry[0].get("steer_point") == BASELINE_CONFIRM]


# --- the lattice ------------------------------------------------------------


def test_the_gate_is_registered_on_the_scoping_lattice_alone() -> None:
    """A2: the point exists for options scoping and for nothing else."""
    assert BASELINE_CONFIRM in lattice_for(OPTIONS_SCOPING)
    assert BASELINE_CONFIRM not in lattice_for(EVIDENCE_SEARCH)


@pytest.mark.parametrize("mode", ATTENDED_MODES)
def test_the_gate_is_off_on_the_evidence_search_lattice(mode: SteeringMode) -> None:
    """A2's protection is the lattice, not the mode table: keep it."""
    assert lattice_policy(mode, BASELINE_CONFIRM, lattice_for(EVIDENCE_SEARCH)) == "off"
    assert lattice_policy(mode, BASELINE_CONFIRM, lattice_for(OPTIONS_SCOPING)) == "always"


def test_the_gate_is_off_under_unattended() -> None:
    assert lattice_policy("unattended", BASELINE_CONFIRM, lattice_for(OPTIONS_SCOPING)) == "off"


# --- the pause --------------------------------------------------------------


@pytest.mark.parametrize("mode", ATTENDED_MODES)
def test_a_scoping_walk_pauses_at_the_gate_in_every_attended_mode(
    engine: Engine, mode: str
) -> None:
    """D11: the baseline gate is structural — it stops the walk however the
    user set the cadence, including Minimal, where every Evidence search point
    is fired-only."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = seed_scoping_task(engine)
        io = ScriptedIO()
        outcome, _plan_id = run_scoping_walk(
            engine,
            task_id=task_id,
            scope_id=scope_id,
            plan=scoping_plan(steering_mode=mode),
            io=io,
        )
        assert outcome.status == "succeeded"
        gates = _gate_pauses(io)
        assert len(gates) == 1
        point, render = gates[0]
        assert (point["boundary"], point["component"]) == ("after_component", "synthesise")
        assert [option["id"] for option in point["options"]] == ["confirm_plan", "change_plan"]
        assert point["bundle"]["settings"] == {
            "target_unit": "16 to 24 year olds",
            "where": "United Kingdom",
            "outcomes": ["the NEET rate"],
            "depth": "standard",
        }
        assert point["bundle"]["artefact_id"] is not None
        assert render.startswith(GATE_HEADING)
        assert "Target unit: 16 to 24 year olds" in render
    finally:
        _cleanup(engine, task_id)


def test_the_gate_options_are_not_the_durable_response_values(engine: Engine) -> None:
    """X10: an option id names the user's decision, never the walk's response."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = seed_scoping_task(engine)
        io = ScriptedIO()
        run_scoping_walk(
            engine,
            task_id=task_id,
            scope_id=scope_id,
            plan=scoping_plan(steering_mode="moderate"),
            io=io,
        )
        ids = {option["id"] for option in _gate_pauses(io)[0][0]["options"]}
        assert ids.isdisjoint({"continue", "adjust", "abort", "mode_change"})
    finally:
        _cleanup(engine, task_id)


# --- unattended -------------------------------------------------------------


def test_unattended_records_the_gate_instead_of_pausing(engine: Engine) -> None:
    """A9: no pause, one standing-default decision, one flag for the review."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = seed_scoping_task(engine)
        io = ScriptedIO()
        plan = scoping_plan(
            steering_mode="unattended",
            steer_point_defaults=[{"steer_point": BASELINE_CONFIRM, "action": "proceed_flag"}],
        )
        outcome, _plan_id = run_scoping_walk(
            engine, task_id=task_id, scope_id=scope_id, plan=plan, io=io
        )
        assert outcome.status == "succeeded"
        assert io.pauses == []

        from policy_atlas.core import events

        with engine.connect() as conn:
            decisions = [
                entry
                for entry in events.read(conn, task_id)
                if entry["event_type"] == "steering.decision"
            ]
        assert len(decisions) == 1
        payload = decisions[0]["payload"]
        assert payload["decided_by"] == "standing_default"
        assert payload["response"] == "continue"
        assert payload["component"] == "synthesise"
        assert payload["standing_rule"] == {
            "steer_point": BASELINE_CONFIRM,
            "action": "proceed_flag",
        }
        flags = [
            flag
            for flag in outcome.flagged_events
            if flag.get("steer_point") == BASELINE_CONFIRM
        ]
        assert flags == [
            {
                "component": "synthesise",
                "status": "auto_resolved",
                "steer_point": BASELINE_CONFIRM,
                "rule": BASELINE_CONFIRM,
                "action": "proceed_flag",
            }
        ]
        assert BASELINE_CONFIRM in outcome.collation_render
    finally:
        _cleanup(engine, task_id)


# --- the Evidence search walk is untouched ----------------------------------


def test_an_evidence_search_walk_pauses_generically_after_synthesise(engine: Engine) -> None:
    """A2: frequent still pauses after synthesise, and never names the gate."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        plan = _base_plan(steering_mode="frequent")
        plan_id = _insert_plan_row(engine, task_id=task_id, scope_id=scope_id, plan=plan)
        io = ScriptedIO()
        outcome = run_plan(
            engine,
            task_id=task_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=io,
        )
        assert outcome.status == "succeeded"
        assert all(point.get("steer_point") != BASELINE_CONFIRM for point, _ in io.pauses)
        after_synthesise = [
            point
            for point, _ in io.pauses
            if point["boundary"] == "after_component" and point["component"] == "synthesise"
        ]
        assert len(after_synthesise) == 1
        assert after_synthesise[0].get("steer_point") is None
        assert {option["id"] for option in after_synthesise[0]["options"]} == {
            "continue",
            "change_mode",
            "abort",
        }
    finally:
        _cleanup(engine, task_id)


# --- the card ---------------------------------------------------------------


def test_the_card_quotes_the_key_assumption_when_the_artefact_has_one() -> None:
    render = render_baseline_gate(
        {
            "key_assumption": "The current offer does not reach the group driving the trend.",
            "settings": {
                "target_unit": "16 to 24 year olds",
                "where": "United Kingdom",
                "outcomes": ["the NEET rate", "youth wages"],
                "depth": "rapid",
            },
        }
    )
    assert render.splitlines()[0] == GATE_HEADING
    assert "Key assumption: The current offer does not reach" in render
    assert "Outcomes: the NEET rate; youth wages" in render
    assert "Depth: rapid" in render


def test_the_card_states_an_absent_key_assumption(engine: Engine) -> None:
    """A stub or degraded artefact has no key-assumption block: say so."""
    del engine
    assert KEY_ASSUMPTION_ABSENT in render_baseline_gate({"settings": {}})
    assert KEY_ASSUMPTION_ABSENT in render_baseline_gate({"key_assumption": "   "})
