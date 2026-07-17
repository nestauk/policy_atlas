"""Task-024 steering-event emission tests (walk lifecycle + Phase-1 paths).

Covers the walk-row lifecycle (capability_run open/thread/close) and the four
Phase-1-reachable emission paths (pause, user decision, rejected, skip) plus the
run-id attachment invariant. Orchestrator/router/watch paths are wired by later
tasks and are not exercised here.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.core import events
from policy_atlas.core.schema import capability_run, orchestration_plan, runs
from policy_atlas.evidence_base.corpus.characterise import CharacteriseFailure
from policy_atlas.runtime import harness, steering_events
from policy_atlas.runtime.runner import run_plan
from policy_atlas.runtime.steering import Abort, Adjust
from tests.runtime.test_runner import (
    _base_plan,
    _runner_backends,
    _seed_project,
)
from tests.runtime.test_steering import (
    ScriptedIO,
    _cleanup_project,
    _insert_plan_row,
)

# The pinned base-payload keys every steering event carries.
BASE_KEYS = {"capability_run_id", "plan_id", "plan_version", "boundary"}
# The pinned decision-payload keys.
DECISION_KEYS = {
    "decided_by",
    "authored_by",
    "response",
    "interpreted_action",
    "confirmed",
    "user_text",
    "rerun_mode",
}


def _events_of_type(engine: Engine, project_id: uuid.UUID, event_type: str) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        return [
            entry for entry in events.read(conn, project_id) if entry["event_type"] == event_type
        ]


# --- Walk lifecycle -------------------------------------------------------


def test_walk_opens_threads_and_closes_capability_run(engine: Engine) -> None:
    """A walk opens one capability_run row, threads it onto every run, closes it."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(
            analysis_depth="landscape",
            components=["characterise"],
            grouping_facets=None,
            steering_mode="unattended",
        )
        plan_id = uuid.uuid4()
        session_id = uuid.uuid4()

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=7,
            backends=_runner_backends(),
            io=ScriptedIO(),
            session_id=session_id,
        )

        assert outcome.capability_run_id is not None
        with engine.connect() as conn:
            row = conn.execute(
                select(
                    capability_run.c.capability,
                    capability_run.c.status,
                    capability_run.c.plan_id,
                    capability_run.c.plan_version,
                    capability_run.c.session_id,
                    capability_run.c.evidence_scope_id,
                    capability_run.c.started_at,
                    capability_run.c.ended_at,
                ).where(capability_run.c.capability_run_id == outcome.capability_run_id)
            ).one()
            run_walk_ids = conn.execute(
                select(runs.c.capability_run_id).where(runs.c.project_id == project_id)
            ).scalars().all()

        assert row.capability == "evidence_base"
        assert row.status == outcome.status  # running → final
        assert row.plan_id == plan_id
        assert row.plan_version == 7
        assert row.session_id == session_id
        assert row.evidence_scope_id == scope_id
        assert row.started_at is not None
        assert row.ended_at is not None
        # Every run created by the walk carries the walk id — none left NULL.
        assert run_walk_ids  # the walk did produce runs
        assert set(run_walk_ids) == {outcome.capability_run_id}
    finally:
        _cleanup_project(engine, project_id)


def test_two_walks_in_one_project_get_distinct_capability_runs(engine: Engine) -> None:
    """A second walk in the same project opens a distinct capability_run."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(
            analysis_depth="landscape",
            components=["characterise"],
            grouping_facets=None,
            steering_mode="unattended",
        )

        first = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=uuid.uuid4(),
            plan_version=1,
            backends=_runner_backends(),
            io=ScriptedIO(),
        )
        second = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=uuid.uuid4(),
            plan_version=1,
            backends=_runner_backends(),
            io=ScriptedIO(),
        )

        assert first.capability_run_id is not None
        assert second.capability_run_id is not None
        assert first.capability_run_id != second.capability_run_id
        with engine.connect() as conn:
            count = conn.execute(
                select(capability_run.c.capability_run_id).where(
                    capability_run.c.project_id == project_id
                )
            ).scalars().all()
        assert {first.capability_run_id, second.capability_run_id} <= set(count)
    finally:
        _cleanup_project(engine, project_id)


# --- Pause + continue decision -------------------------------------------


def test_pause_and_continue_decision_carry_full_base_and_decision_payloads(
    engine: Engine,
) -> None:
    """A moderate pause emits steering.pause + steering.decision(continue)."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()  # moderate, deep chain
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
            io=ScriptedIO(),  # no scripted responses → Continue at each pause
        )
        assert outcome.status == "succeeded"

        pauses = _events_of_type(engine, project_id, steering_events.STEERING_PAUSE)
        decisions = _events_of_type(engine, project_id, steering_events.STEERING_DECISION)
        assert pauses  # moderate = after-select steer point + before-synthesise
        assert decisions

        for pause in pauses:
            payload = pause["payload"]
            assert set(payload) >= BASE_KEYS
            assert payload["capability_run_id"] == str(outcome.capability_run_id)
            assert payload["plan_id"] == str(plan_id)
            assert payload["plan_version"] == 1
            assert payload["boundary"] in {"after_component", "before_component"}
            assert "component" in payload
            assert payload["kind"] in {"check_in", "steer_point"}
            assert pause["run_id"] is not None

        # The steer-point pause carries authored options + triggers.
        steer_pauses = [p for p in pauses if p["payload"]["kind"] == "steer_point"]
        assert steer_pauses
        assert isinstance(steer_pauses[0]["payload"]["options"], list)
        assert "triggers" in steer_pauses[0]["payload"]

        continue_decisions = [d for d in decisions if d["payload"]["response"] == "continue"]
        assert continue_decisions
        payload = continue_decisions[0]["payload"]
        assert set(payload) >= BASE_KEYS
        assert set(payload) >= DECISION_KEYS
        assert payload["decided_by"] == "user"
        assert payload["authored_by"] == "user"
        assert payload["confirmed"] is True
        assert payload["interpreted_action"] is None
        assert payload["user_text"] is None
        assert payload["rerun_mode"] is None
    finally:
        _cleanup_project(engine, project_id)


# --- Adjust decision (generic, not-yet-run component) --------------------


def test_adjust_emits_decision_paired_with_plan_version_row(engine: Engine) -> None:
    """An Adjust writes a plan-version row and a paired steering.decision(adjust)."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="minimal")  # pauses after select
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        io = ScriptedIO(
            [Adjust(directive_deltas={"group": {"grouping": {"facets": ["population"]}}})]
        )

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
            versions = conn.execute(
                select(orchestration_plan.c.version, orchestration_plan.c.status)
                .where(orchestration_plan.c.project_id == project_id)
                .order_by(orchestration_plan.c.version)
            ).all()
        assert [(r.version, r.status) for r in versions] == [
            (1, "superseded"),
            (2, "approved"),
        ]

        decisions = _events_of_type(engine, project_id, steering_events.STEERING_DECISION)
        adjust = [d for d in decisions if d["payload"]["response"] == "adjust"]
        assert len(adjust) == 1
        payload = adjust[0]["payload"]
        assert payload["decided_by"] == "user"
        assert payload["confirmed"] is True
        assert payload["rerun_mode"] is None
        assert payload["interpreted_action"] == {
            "directive_deltas": {"group": {"grouping": {"facets": ["population"]}}}
        }
        # The decision records the version decided-over (pre-adjustment).
        assert payload["plan_version"] == 1
    finally:
        _cleanup_project(engine, project_id)


def test_adjust_with_new_mode_surfaces_response_mode_change(engine: Engine) -> None:
    """An Adjust carrying new_mode emits response mode_change (review N3)."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="minimal")
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        io = ScriptedIO([Adjust(new_mode="moderate")])

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

        decisions = _events_of_type(engine, project_id, steering_events.STEERING_DECISION)
        mode_changes = [d for d in decisions if d["payload"]["response"] == "mode_change"]
        assert len(mode_changes) == 1
        assert mode_changes[0]["payload"]["interpreted_action"] == {"new_mode": "moderate"}
    finally:
        _cleanup_project(engine, project_id)


# --- Abort decision -------------------------------------------------------


def test_abort_emits_decision_and_abandons_plan(engine: Engine) -> None:
    """Abort emits steering.decision(abort) and flips the plan to abandoned."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="frequent")
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        io = ScriptedIO([Abort()])

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
        assert outcome.status == "aborted"

        with engine.connect() as conn:
            plan_status = conn.execute(
                select(orchestration_plan.c.status).where(
                    orchestration_plan.c.plan_id == plan_id
                )
            ).scalar_one()
        assert plan_status == "abandoned"

        decisions = _events_of_type(engine, project_id, steering_events.STEERING_DECISION)
        aborts = [d for d in decisions if d["payload"]["response"] == "abort"]
        assert len(aborts) == 1
        payload = aborts[0]["payload"]
        assert payload["decided_by"] == "user"
        assert payload["confirmed"] is True
        assert payload["interpreted_action"] is None
        assert payload["capability_run_id"] == str(outcome.capability_run_id)
    finally:
        _cleanup_project(engine, project_id)


# --- Rejected adjustment --------------------------------------------------


def test_rejected_adjustment_emits_reason_then_continue(engine: Engine) -> None:
    """An invalid Adjust emits steering.rejected, then a Continue decision lands."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="minimal")
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        # appraise has already run by the P2 (evidence_base_coverage) pause and no
        # steer point ever re-runs it (unlike characterise, which P2 re-runs since
        # Task 15b): an adjustment naming it fails closed and is rejected; the
        # reprompt then Continues (delivered by steer point, robust to which fire).
        io = ScriptedIO(
            by_steer_point={
                "evidence_base_coverage": [Adjust(directive_deltas={"appraise": {}})]
            }
        )

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

        rejected = _events_of_type(engine, project_id, steering_events.STEERING_REJECTED)
        assert len(rejected) == 1
        payload = rejected[0]["payload"]
        assert set(payload) >= BASE_KEYS
        assert "already-run component 'appraise'" in payload["reason"]
        assert payload["offending_delta"] == {"directive_deltas": {"appraise": {}}}
        assert rejected[0]["run_id"] is not None

        # No plan-version row was written (the rejected adjustment never applied).
        with engine.connect() as conn:
            versions = conn.execute(
                select(orchestration_plan.c.version, orchestration_plan.c.status)
                .where(orchestration_plan.c.project_id == project_id)
                .order_by(orchestration_plan.c.version)
            ).all()
        assert [(r.version, r.status) for r in versions] == [(1, "approved")]

        # A continue decision followed the rejection on the same pause.
        decisions = _events_of_type(engine, project_id, steering_events.STEERING_DECISION)
        assert any(d["payload"]["response"] == "continue" for d in decisions)
    finally:
        _cleanup_project(engine, project_id)


# --- Skip -----------------------------------------------------------------


def test_skip_emits_component_skipped_with_reason_and_resolved_run(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A discretionary failure emits component.skipped for each skipped step."""
    project_id: uuid.UUID | None = None

    def failing_characterise_scope(*args: Any, **kwargs: Any) -> dict[str, Any]:
        del args, kwargs
        raise CharacteriseFailure(coverage={"base_counts": {}}, error="forced characterise failure")

    monkeypatch.setattr(harness, "characterise_scope", failing_characterise_scope)
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(
            steering_mode="minimal",
            components=["characterise", "select", "extract", "group"],
        )

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=uuid.uuid4(),
            plan_version=1,
            backends=_runner_backends(),
            io=ScriptedIO(),
        )
        assert outcome.status == "degraded"

        skipped = _events_of_type(engine, project_id, steering_events.COMPONENT_SKIPPED)
        components = {e["payload"]["component"] for e in skipped}
        assert components == {"select", "extract", "group"}
        for event in skipped:
            payload = event["payload"]
            assert set(payload) >= BASE_KEYS
            assert payload["boundary"] == "after_component"
            assert payload["reason"].startswith("requires skipped/failed discretionary component")
            # A skip can never precede the first run: the attachment resolves.
            assert event["run_id"] is not None
            assert payload["capability_run_id"] == str(outcome.capability_run_id)
    finally:
        _cleanup_project(engine, project_id)


# --- Reselect (replacement re-run) ---------------------------------------


def test_reselect_decision_stamps_replacement_and_pairs_with_plan_version(
    engine: Engine,
) -> None:
    """A steer-point select Adjust emits a replacement decision + a new version."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()  # moderate, deep chain, after-select steer point
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        # Reselect lands at the P3 deepening_selection pause; other lattice
        # pauses Continue (robust to which of P1/P2/P4 fire on the stub seed).
        io = ScriptedIO(
            by_steer_point={
                "deepening_selection": [
                    Adjust(
                        directive_deltas={
                            "select": {"selection": {"weight_emphasis": {"quality": 2.0}}}
                        }
                    )
                ]
            }
        )

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
            versions = conn.execute(
                select(orchestration_plan.c.version, orchestration_plan.c.created_by)
                .where(orchestration_plan.c.project_id == project_id)
                .order_by(orchestration_plan.c.version)
            ).all()
        assert [(r.version, r.created_by) for r in versions] == [
            (1, "planner"),
            (2, "user"),
        ]

        decisions = _events_of_type(engine, project_id, steering_events.STEERING_DECISION)
        reselects = [d for d in decisions if d["payload"]["rerun_mode"] == "replacement"]
        assert len(reselects) == 1
        payload = reselects[0]["payload"]
        assert payload["response"] == "adjust"
        assert payload["decided_by"] == "user"
        assert payload["confirmed"] is True
        assert payload["interpreted_action"] == {
            "directive_deltas": {"select": {"selection": {"weight_emphasis": {"quality": 2.0}}}}
        }
    finally:
        _cleanup_project(engine, project_id)


# --- Run-id attachment invariant -----------------------------------------


def test_emit_raises_on_none_run_id(engine: Engine) -> None:
    """The chassis asserts a resolved run_id on every emission."""
    base = steering_events.base_payload(
        capability_run_id=uuid.uuid4(),
        plan_id=uuid.uuid4(),
        plan_version=1,
        boundary="walk",
    )
    with pytest.raises(ValueError, match="no steering event is emitted before the first"):
        steering_events.emit_standalone(
            engine,
            project_id=uuid.uuid4(),
            run_id=None,
            event_type=steering_events.STEERING_PAUSE,
            payload=base,
        )


def test_emit_on_connection_raises_on_none_run_id(conn: Connection) -> None:
    """The connection-scoped emit enforces the same invariant."""
    base = steering_events.base_payload(
        capability_run_id=uuid.uuid4(),
        plan_id=uuid.uuid4(),
        plan_version=1,
        boundary="walk",
    )
    with pytest.raises(ValueError, match="has no attachable run_id"):
        steering_events.emit(
            conn,
            project_id=uuid.uuid4(),
            run_id=None,
            event_type=steering_events.STEERING_DECISION,
            payload=base,
        )
