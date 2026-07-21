"""Task 024 Task 12 — Unattended = discretion-is-the-mode (ADR 0021 decision 4).

Covers the deterministic discretion structure the Phase-5 watch plugs into: the
standing-instructions vocabulary (option_id/delta, fail-closed validated), the
discretion path at every lattice boundary (pinned rule applied through the
existing apply machinery · hard stop always honoured · no-rule discretion floor
flagged loudest), the injected discretion-hook seam and the authority order
(declared rules > orchestrator), fired triggers riding every decision payload,
and the loudest-first collation ordering.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.core import events
from policy_atlas.core.schema import orchestration_plan, selection_result
from policy_atlas.runtime import runner as runner_module
from policy_atlas.runtime import steering_events
from policy_atlas.runtime.orchestration_plan import STEER_POINTS, SteerPointDefault
from policy_atlas.runtime.runner import (
    _DiscretionContext,
    _DiscretionOutcome,
    run_plan,
)
from policy_atlas.runtime.steering import LATTICE_POINTS
from tests.runtime.test_runner import _base_plan, _runner_backends, _seed_project
from tests.runtime.test_steering import _cleanup_project, _insert_plan_row

_STRONGEST_DELTA = {"selection": {"weight_emphasis": {"quality": 2.0}}}


def _standing_decisions(engine: Engine, project_id: uuid.UUID) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        return [
            entry["payload"]
            for entry in events.read(conn, project_id)
            if entry["event_type"] == steering_events.STEERING_DECISION
            and entry["payload"].get("decided_by") == "standing_default"
        ]


# --- Standing-instructions vocabulary validation (plan-validation time) -----


def test_steer_points_registry_matches_lattice() -> None:
    """The plan-side STEER_POINTS registry never drifts from the lattice."""
    assert set(STEER_POINTS) == set(LATTICE_POINTS)


def test_legacy_two_field_rule_still_validates() -> None:
    """The task-017 two-field rule stays valid unchanged (backward compatible)."""
    rule = SteerPointDefault(steer_point="deepening_selection", action="proceed_flag")
    assert rule.option_id is None
    assert rule.delta is None


def test_pinned_option_rule_validates_and_compiles() -> None:
    """A proceed_flag rule with a canonical option id + compiling delta is valid."""
    rule = SteerPointDefault(
        steer_point="deepening_selection",
        action="proceed_flag",
        option_id="strongest_evidence",
        delta=_STRONGEST_DELTA,
    )
    assert rule.option_id == "strongest_evidence"


def test_option_id_outside_vocabulary_fails_closed() -> None:
    with pytest.raises(ValidationError, match="not a canonical option"):
        SteerPointDefault(
            steer_point="deepening_selection",
            action="proceed_flag",
            option_id="not_an_option",
        )


def test_requires_input_option_without_supplied_delta_fails_closed() -> None:
    """scope_strata requires user input; a rule whose delta only carries the
    placeholder template supplies none — rejected at validation time."""
    with pytest.raises(ValidationError, match="requires user input"):
        SteerPointDefault(
            steer_point="deepening_selection",
            action="proceed_flag",
            option_id="scope_strata",
            delta={"selection": {"strata_scope": {"only": ["theme or stratum name"]}}},
        )


def test_requires_input_option_with_supplied_delta_validates() -> None:
    rule = SteerPointDefault(
        steer_point="deepening_selection",
        action="proceed_flag",
        option_id="scope_strata",
        delta={"selection": {"strata_scope": {"only": ["rural childcare"]}}},
    )
    assert rule.option_id == "scope_strata"


def test_non_compiling_delta_fails_closed() -> None:
    with pytest.raises(ValidationError):
        SteerPointDefault(
            steer_point="deepening_selection",
            action="proceed_flag",
            option_id="strongest_evidence",
            delta={"selection": {"weight_emphasis": {"quality": "not-a-number"}}},
        )


def test_option_binding_on_stop_rule_fails_closed() -> None:
    """A hard stop carries no option — a binding on a stop rule is rejected."""
    with pytest.raises(ValidationError, match="only 'proceed_flag'"):
        SteerPointDefault(
            steer_point="deepening_selection",
            action="stop",
            option_id="strongest_evidence",
            delta=_STRONGEST_DELTA,
        )


# --- Discretion path at the lattice boundaries ------------------------------


def test_pinned_rule_applies_reselect_without_pause(engine: Engine) -> None:
    """A P3 standing rule (strongest_evidence + its delta) re-runs select in
    Unattended: both selection rows persist, the reference moves to the re-run,
    the decision is decided_by=standing_default (rerun_mode=replacement, rule
    echoed), and the run never pauses."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(
            steering_mode="unattended",
            steer_point_defaults=[
                {
                    "steer_point": "deepening_selection",
                    "action": "proceed_flag",
                    "option_id": "strongest_evidence",
                    "delta": _STRONGEST_DELTA,
                }
            ],
        )
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        io = runner_module.NullIO()

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=io,
        )
        assert outcome.status == "succeeded"

        with engine.connect() as conn:
            selection_run_ids = (
                conn.execute(
                    select(selection_result.c.run_id).where(
                        selection_result.c.project_id == project_id
                    )
                )
                .scalars()
                .all()
            )
            compiled = [
                entry
                for entry in events.read(conn, project_id)
                if entry["event_type"] == "plan.compiled"
            ]
        compiled_select = [
            entry["run_id"] for entry in compiled if entry["payload"]["component"] == "select"
        ]
        # Both selection rows persist (immutable); the reference moved.
        assert len(selection_run_ids) == 2
        assert set(selection_run_ids) == set(compiled_select)
        extract_payload = next(
            entry["payload"] for entry in compiled if entry["payload"]["component"] == "extract"
        )
        assert extract_payload["selection_run_id"] == str(compiled_select[1])

        # The reselect decision is a standing-default replacement re-run.
        reselect = next(
            payload
            for payload in _standing_decisions(engine, project_id)
            if payload.get("rerun_mode") == "replacement"
        )
        assert reselect["decided_by"] == "standing_default"
        assert reselect["authored_by"] == "standing_default"
        assert reselect["standing_rule"]["option_id"] == "strongest_evidence"
    finally:
        _cleanup_project(engine, project_id)


def test_hard_stop_rule_aborts_and_cannot_be_overridden(engine: Engine) -> None:
    """A P2 stop rule aborts the walk before select, abandons the plan, and
    records response=abort decided_by=standing_default. A discretion hook that
    would proceed is never consulted (the stop is structural — nothing routes
    around it)."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(
            steering_mode="unattended",
            steer_point_defaults=[
                {"steer_point": "evidence_base_coverage", "action": "stop"}
            ],
        )
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)

        would_proceed_calls: list[str] = []

        def _would_proceed(context: _DiscretionContext) -> _DiscretionOutcome:
            would_proceed_calls.append(context.steer_point)
            return _DiscretionOutcome(interpreted_action="proceed", rule="watch_proceeded")

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=runner_module.NullIO(),
            discretion_hook=_would_proceed,
        )
        assert outcome.status == "aborted"

        # The plan was abandoned; select never ran.
        with engine.connect() as conn:
            status = conn.execute(
                select(orchestration_plan.c.status).where(
                    orchestration_plan.c.plan_id == plan_id
                )
            ).scalar_one()
            selection_rows = conn.execute(
                select(selection_result.c.run_id).where(
                    selection_result.c.project_id == project_id
                )
            ).all()
        assert status == "abandoned"
        assert selection_rows == []

        aborts = [
            payload
            for payload in _standing_decisions(engine, project_id)
            if payload.get("response") == "abort"
        ]
        assert len(aborts) == 1
        assert aborts[0]["standing_rule"]["action"] == "stop"
        # The hook never decided the P2 boundary (the pinned stop won).
        assert "evidence_base_coverage" not in would_proceed_calls
    finally:
        _cleanup_project(engine, project_id)


def test_unconfigured_default_proceeds_flags_loudest_and_evented(engine: Engine) -> None:
    """With no pinned rules the discretion floor proceeds at every always-on
    lattice boundary (P2/P3/P4): each emits unconfigured_default flags + a
    standing-default decision, the walk completes, and unconfigured_default is
    collated FIRST among auto-resolutions."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="unattended", steer_point_defaults=[])
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=runner_module.NullIO(),
        )
        assert outcome.status == "succeeded"

        auto = [
            event for event in outcome.flagged_events if event["status"] == "auto_resolved"
        ]
        floor_points = {
            event["steer_point"]
            for event in auto
            if event["rule"] == "unconfigured_default"
        }
        # The always-on decision points all fell to the loudest floor.
        assert {"evidence_base_coverage", "deepening_selection", "synthesis_shape"} <= floor_points

        # Every floor decision is evented decided_by=standing_default.
        decisions = _standing_decisions(engine, project_id)
        floor_decisions = [
            payload
            for payload in decisions
            if payload.get("standing_rule", {}).get("rule") == "unconfigured_default"
        ]
        assert len(floor_decisions) >= 3
        assert all(payload["response"] == "continue" for payload in floor_decisions)

        # Loudest-flag ordering: unconfigured_default precedes any pinned-rule
        # auto-resolution in the collation (none here, but the ordering holds).
        collation = outcome.collation_render
        assert "auto-resolutions:" in collation
        auto_block = collation.split("auto-resolutions:", 1)[1]
        assert "unconfigured_default" in auto_block
    finally:
        _cleanup_project(engine, project_id)


def test_fired_triggers_ride_the_standing_decision_payload(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fired floor trigger at a lattice boundary rides the standing decision
    payload (discipline 1 — the floor is never suppressible; discretion can add
    nothing to it and remove nothing from it)."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        fired = [{"trigger": "thin_base", "detail": {"selected": 1}}]
        # Force P3's floor trigger to fire regardless of the corpus.
        monkeypatch.setattr(
            runner_module, "steer_point_triggers", lambda *a, **k: fired
        )
        plan = _base_plan(steering_mode="unattended", steer_point_defaults=[])
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=runner_module.NullIO(),
        )
        assert outcome.status == "succeeded"

        p3_decision = next(
            payload
            for payload in _standing_decisions(engine, project_id)
            if payload.get("component") == "select"
            and payload.get("boundary") == "after_component"
        )
        assert p3_decision["triggers"] == fired
    finally:
        _cleanup_project(engine, project_id)


def test_discretion_hook_only_consulted_when_no_pinned_rule(engine: Engine) -> None:
    """Authority order (declared rules > orchestrator): the injected hook is
    consulted at a boundary only when no pinned rule exists. With rules for every
    always-on point the hook is never called; without them it is."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)

        consulted: list[str] = []

        def _spy(context: _DiscretionContext) -> _DiscretionOutcome:
            consulted.append(context.steer_point)
            return _DiscretionOutcome(interpreted_action="proceed", rule="unconfigured_default")

        # Every lattice point carries a bare proceed_flag rule (search_exception
        # too, since P1 fires on this corpus) so no boundary reaches the floor.
        ruled = _base_plan(
            steering_mode="unattended",
            steer_point_defaults=[
                {"steer_point": "search_exception", "action": "proceed_flag"},
                {"steer_point": "evidence_base_coverage", "action": "proceed_flag"},
                {"steer_point": "deepening_selection", "action": "proceed_flag"},
                {"steer_point": "synthesis_shape", "action": "proceed_flag"},
            ],
        )
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=ruled)
        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=ruled,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=runner_module.NullIO(),
            discretion_hook=_spy,
        )
        assert outcome.status == "succeeded"
        # Every always-on point had a rule → the hook decided nothing.
        assert consulted == []
    finally:
        _cleanup_project(engine, project_id)


def test_discretion_hook_consulted_without_rules(engine: Engine) -> None:
    """The control for the authority test: with no rules the hook IS consulted at
    the always-on lattice boundaries."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        consulted: list[str] = []

        def _spy(context: _DiscretionContext) -> _DiscretionOutcome:
            consulted.append(context.steer_point)
            return _DiscretionOutcome(interpreted_action="proceed", rule="unconfigured_default")

        plan = _base_plan(steering_mode="unattended", steer_point_defaults=[])
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=runner_module.NullIO(),
            discretion_hook=_spy,
        )
        assert {"evidence_base_coverage", "deepening_selection", "synthesis_shape"} <= set(
            consulted
        )
    finally:
        _cleanup_project(engine, project_id)
