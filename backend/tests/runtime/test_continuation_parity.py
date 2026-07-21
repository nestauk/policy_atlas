"""Durable parking and continuation parity coverage."""

from __future__ import annotations

import copy
import inspect
import json
import uuid
from dataclasses import dataclass, fields
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

import policy_atlas.runtime.runner as runner_module
from policy_atlas.core import events
from policy_atlas.core.schema import capability_run
from policy_atlas.evidence_base.corpus.characterise import CharacteriseFailure
from policy_atlas.runtime import harness, steering_events
from policy_atlas.runtime.continuation_state import ContinuationState, ResumeDecision, build
from policy_atlas.runtime.runner import NullIO, WalkParked, run_plan
from policy_atlas.runtime.steering import (
    Adjust,
    Continue,
    PausePoint,
    ReEnterSegment,
    render_collation,
)
from tests.runtime.test_runner import _base_plan, _cleanup, _runner_backends, _seed_project
from tests.runtime.test_segment_reentry import _AMENDMENT, _boundary_state
from tests.runtime.test_steering import _insert_plan_row, _walk_to_completion


class _ParkOnceIO:
    """Park one after-component boundary, then continue every later pause."""

    def __init__(self) -> None:
        self.parked = False
        self.pauses: list[tuple[dict[str, Any], str]] = []
        self.live_state: ContinuationState | None = None
        self.surface: dict[str, Any] | None = None

    def check_in(self, component: str, payload: dict[str, Any]) -> None:
        """Accept a check-in without changing the scripted disposition."""
        del component, payload

    def pause(self, point: dict[str, Any], render: str) -> Continue:
        """Raise once after a component so its pause event is already durable."""
        self.pauses.append((dict(point), render))
        if not self.parked and point["boundary"] == "after_component":
            self.live_state, self.surface = _capture_live_state(point)
            self.parked = True
            raise WalkParked()
        return Continue()


class _CaptureContinueIO:
    """Capture the first after-component loop state and answer Continue."""

    def __init__(self) -> None:
        self.live_state: ContinuationState | None = None
        self.surface: dict[str, Any] | None = None

    def check_in(self, component: str, payload: dict[str, Any]) -> None:
        """Accept the check-in used to reach the captured boundary."""
        del component, payload

    def pause(self, point: dict[str, Any], render: str) -> Continue:
        """Capture the in-memory boundary state before answering it."""
        del render
        if self.live_state is None and point["boundary"] == "after_component":
            self.live_state, self.surface = _capture_live_state(point)
        return Continue()


class _BoundaryResponseIO(_CaptureContinueIO):
    """Capture and answer one named after-component boundary."""

    def __init__(self, component: str, response: Any) -> None:
        super().__init__()
        self.component = component
        self.response = response
        self.answered = False

    def pause(self, point: dict[str, Any], render: str) -> Any:
        """Return the scripted boundary answer once and continue otherwise."""
        del render
        if point["boundary"] == "after_component" and point["component"] == self.component:
            if self.live_state is None:
                self.live_state, self.surface = _capture_live_state(point)
            if not self.answered:
                self.answered = True
                return self.response
        return Continue()


class _BoundaryParkIO(_ParkOnceIO):
    """Park every presentation of one named after-component boundary."""

    def __init__(self, component: str) -> None:
        super().__init__()
        self.component = component
        self.presentations = 0

    def pause(self, point: dict[str, Any], render: str) -> Continue:
        """Park at the scripted boundary, including a re-entry presentation."""
        self.pauses.append((dict(point), render))
        if point["boundary"] == "after_component" and point["component"] == self.component:
            self.live_state, self.surface = _capture_live_state(point)
            self.presentations += 1
            raise WalkParked()
        return Continue()


def _capture_live_state(point: dict[str, Any]) -> tuple[ContinuationState, dict[str, Any]]:
    """Read the runner's loop locals at the IO seam without mutating the walk."""
    frame = inspect.currentframe()
    assert frame is not None
    frame = frame.f_back
    while frame is not None and frame.f_code.co_name != "_run_plan_impl":
        frame = frame.f_back
    assert frame is not None
    local = frame.f_locals
    steering_state = local["steering_state"]
    state = ContinuationState(
        capability_run_id=local["capability_run_id"],
        plan=copy.deepcopy(steering_state.plan),
        plan_id=steering_state.plan_id,
        plan_version=steering_state.plan_version,
        plan_row_id=steering_state.plan_row_id,
        chain=copy.deepcopy(steering_state.chain),
        pause_points=set(steering_state.pause_points),
        pending_overlays=copy.deepcopy(steering_state.pending_overlays),
        remaining_steps=copy.deepcopy(local["remaining_steps"]),
        step_outcomes=copy.deepcopy(local["step_outcomes"]),
        flagged_events=copy.deepcopy(local["flagged_events"]),
        successful_runs=dict(local["successful_runs"]),
        attempted_runs=dict(local["attempted_runs"]),
        blocked_discretionary=dict(local["blocked_discretionary"]),
        completed_components=set(local["completed_components"]),
        last_check_in_payload=copy.deepcopy(local["last_check_in_payload"]),
        most_recent_attempted_run_id=local["most_recent_attempted_run_id"],
        session_id=local["session_id"],
    )
    runner_state = runner_module._SteeringState(
        plan=state.plan,
        plan_id=state.plan_id,
        plan_version=state.plan_version,
        plan_row_id=state.plan_row_id,
        chain=state.chain,
        pause_points=state.pause_points,
        pending_overlays=state.pending_overlays,
    )
    surfaces = {
        "pause_header": runner_module._watch_header(runner_state),
        "digest": runner_module._watch_digest(
            local["engine"],
            project_id=local["project_id"],
            capability_run_id=state.capability_run_id,
        ),
        "canonical_options": point.get("options", []),
        "authored_options": point.get("authored_options"),
        "router": runner_module._router_pause_context(
            PausePoint(point["boundary"], point["component"]),
            state=runner_state,
            steer_point_name=point.get("steer_point"),
            options=point.get("options"),
            completed_components=state.completed_components,
            rerun_component=point.get("rerun_component"),
            segment_reentry_allowed=point["segment_reentry_allowed"],
        ),
        # Lazily-resolvable only: the real walk computes reference kwargs at
        # execution time, when the upstream run exists — a downstream component
        # whose upstream hasn't run yet has no reference surface to compare.
        "references": {
            component: kwargs
            for component in state.chain.components
            if (kwargs := _reference_kwargs_or_none(component, state.successful_runs))
            is not None
        },
        "pending_overlays": state.pending_overlays,
        "collation_render": render_collation(state.flagged_events),
        "bundle": point.get("bundle"),
    }
    return state, surfaces


def _reference_kwargs_or_none(
    component: str, successful_runs: dict[str, uuid.UUID]
) -> dict[str, uuid.UUID] | None:
    """Reference kwargs when the upstream run exists, else None (not yet resolvable)."""
    try:
        return runner_module._reference_kwargs(component, successful_runs)
    except KeyError:
        return None


@dataclass
class _WalkCanonicalizer:
    """Map one walk's generated UUIDs to first-seen structural placeholders."""

    values: dict[uuid.UUID, str]

    def uuid(self, value: uuid.UUID) -> str:
        """Return this walk's stable placeholder for one generated UUID."""
        if value not in self.values:
            self.values[value] = f"<uuid-{len(self.values) + 1}>"
        return self.values[value]


def _canonicalise_parity(
    state: ContinuationState, surface: dict[str, Any]
) -> tuple[dict[str, Any], bytes]:
    """Canonicalise one walk while retaining all continuation and surface structure.

    UUID placeholders are assigned in the annex's fixed identity traversal. Wall
    clocks are the only non-deterministic scalar observed in this capture path.
    """
    canonicalizer = _WalkCanonicalizer(values={})
    _register_walk_uuids(state, canonicalizer)
    canonical = {
        "plan": _normalise_value(state.plan.model_dump(mode="json"), canonicalizer),
        "capability_run_id": canonicalizer.uuid(state.capability_run_id),
        "plan_id": canonicalizer.uuid(state.plan_id),
        "plan_version": state.plan_version,
        "plan_row_id": (
            canonicalizer.uuid(state.plan_row_id) if state.plan_row_id is not None else None
        ),
        "chain": _normalise_value(state.chain.model_dump(mode="json"), canonicalizer),
        "pause_points": [
            {"boundary": point.boundary, "component": point.component}
            for point in sorted(
                state.pause_points, key=lambda point: (point.boundary, point.component)
            )
        ],
        "pending_overlays": _normalise_value(state.pending_overlays, canonicalizer),
        "remaining_steps": _normalise_value(
            [step.model_dump(mode="json") for step in state.remaining_steps], canonicalizer
        ),
        "successful_runs": {
            component: canonicalizer.uuid(state.successful_runs[component])
            for component in sorted(state.successful_runs)
        },
        "attempted_runs": {
            component: canonicalizer.uuid(state.attempted_runs[component])
            for component in sorted(state.attempted_runs)
        },
        "step_outcomes": [
            _normalise_outcome(outcome, canonicalizer) for outcome in state.step_outcomes
        ],
        "most_recent_attempted_run_id": (
            canonicalizer.uuid(state.most_recent_attempted_run_id)
            if state.most_recent_attempted_run_id is not None
            else None
        ),
    }
    canonical.update(
        {
            "flagged_events": _normalise_value(state.flagged_events, canonicalizer),
            "blocked_discretionary": _normalise_value(
                state.blocked_discretionary, canonicalizer
            ),
            "completed_components": sorted(state.completed_components),
            "last_check_in_payload": _normalise_value(
                state.last_check_in_payload, canonicalizer
            ),
        }
    )
    canonical_surface = _normalise_value(surface, canonicalizer)
    return canonical, json.dumps(canonical_surface, sort_keys=True, separators=(",", ":")).encode()


def _register_walk_uuids(state: ContinuationState, canonicalizer: _WalkCanonicalizer) -> None:
    """Assign UUID placeholders in the continuation annex's fixed traversal order."""
    canonicalizer.uuid(state.capability_run_id)
    canonicalizer.uuid(state.plan_id)
    if state.plan_row_id is not None:
        canonicalizer.uuid(state.plan_row_id)
    for component in sorted(state.successful_runs):
        canonicalizer.uuid(state.successful_runs[component])
    for component in sorted(state.attempted_runs):
        canonicalizer.uuid(state.attempted_runs[component])
    for outcome in state.step_outcomes:
        if outcome.run_id is not None:
            canonicalizer.uuid(outcome.run_id)
        for run_id in outcome.attempt_run_ids:
            canonicalizer.uuid(run_id)
    if state.most_recent_attempted_run_id is not None:
        canonicalizer.uuid(state.most_recent_attempted_run_id)


def _normalise_outcome(outcome: Any, canonicalizer: _WalkCanonicalizer) -> dict[str, Any]:
    """Normalise one ordered step outcome without hiding status or retry structure."""
    values = {
        field.name: getattr(outcome, field.name)
        for field in fields(outcome)
    }
    normalised: dict[str, Any] = _normalise_value(values, canonicalizer)
    return normalised


def _normalise_value(value: Any, canonicalizer: _WalkCanonicalizer) -> Any:
    """Replace generated IDs and the captured path's wall-clock scalar only."""
    if isinstance(value, uuid.UUID):
        return canonicalizer.uuid(value)
    if isinstance(value, str):
        try:
            return canonicalizer.uuid(uuid.UUID(value))
        except ValueError:
            return value
    if isinstance(value, dict):
        return {
            key: _normalise_scalar(key, item, canonicalizer)
            for key, item in sorted(value.items())
        }
    if isinstance(value, list):
        return [_normalise_value(item, canonicalizer) for item in value]
    if isinstance(value, tuple):
        return tuple(_normalise_value(item, canonicalizer) for item in value)
    if isinstance(value, set):
        return sorted(_normalise_value(item, canonicalizer) for item in value)
    return value


def _normalise_scalar(key: str, value: Any, canonicalizer: _WalkCanonicalizer) -> Any:
    """Normalise a keyed value when the key names an observed wall clock."""
    if key == "wall_clock_s" and isinstance(value, int | float) and not isinstance(value, bool):
        return "<wall-clock-seconds>"
    return _normalise_value(value, canonicalizer)


def _assert_16_fields_equal(expected: dict[str, Any], actual: dict[str, Any]) -> None:
    """Assert every continuation annex field, excluding session identity."""
    assert expected["capability_run_id"] == actual["capability_run_id"]
    assert expected["plan"] == actual["plan"]
    assert expected["plan_id"] == actual["plan_id"]
    assert expected["plan_version"] == actual["plan_version"]
    assert expected["plan_row_id"] == actual["plan_row_id"]
    assert expected["chain"] == actual["chain"]
    assert expected["pause_points"] == actual["pause_points"]
    assert expected["pending_overlays"] == actual["pending_overlays"]
    assert expected["remaining_steps"] == actual["remaining_steps"]
    assert expected["step_outcomes"] == actual["step_outcomes"]
    assert expected["flagged_events"] == actual["flagged_events"]
    assert expected["successful_runs"] == actual["successful_runs"]
    assert expected["attempted_runs"] == actual["attempted_runs"]
    assert expected["blocked_discretionary"] == actual["blocked_discretionary"]
    assert expected["completed_components"] == actual["completed_components"]
    assert expected["last_check_in_payload"] == actual["last_check_in_payload"]
    assert expected["most_recent_attempted_run_id"] == actual["most_recent_attempted_run_id"]


def _assert_parity(
    expected_state: ContinuationState,
    expected_surface: dict[str, Any],
    actual_state: ContinuationState,
    actual_surface: dict[str, Any],
) -> None:
    """Assert structural continuation and byte-level surface parity across walks."""
    expected_fields, expected_bytes = _canonicalise_parity(expected_state, expected_surface)
    actual_fields, actual_bytes = _canonicalise_parity(actual_state, actual_surface)
    _assert_16_fields_equal(expected_fields, actual_fields)
    assert expected_bytes == actual_bytes


def test_parked_continue_rebuilds_the_runner_state_from_durable_rows(engine: Engine) -> None:
    """A parked walk resumes with the same component outcomes as an unbroken walk."""
    parked_project_id: uuid.UUID | None = None
    unbroken_project_id: uuid.UUID | None = None
    try:
        parked_project_id, parked_scope_id = _seed_project(engine)
        unbroken_project_id, unbroken_scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="frequent", search_effort="standard")
        parked_plan_id = _insert_plan_row(
            engine,
            project_id=parked_project_id,
            scope_id=parked_scope_id,
            plan=plan,
        )
        unbroken_plan_id = _insert_plan_row(
            engine,
            project_id=unbroken_project_id,
            scope_id=unbroken_scope_id,
            plan=plan,
        )
        parked_io = _ParkOnceIO()
        parked = run_plan(
            engine,
            project_id=parked_project_id,
            evidence_scope_id=parked_scope_id,
            plan=plan,
            plan_id=parked_plan_id,
            plan_version=1,
            plan_row_id=parked_plan_id,
            backends=_runner_backends(),
            io=parked_io,
        )
        assert parked.status == "paused"
        assert parked.capability_run_id is not None
        state = build(
            engine,
            project_id=parked_project_id,
            capability_run_id=parked.capability_run_id,
        )
        assert state.step_outcomes == parked.steps
        assert state.flagged_events == parked.flagged_events
        assert state.remaining_steps == [
            step for step in state.chain.steps if step.component not in state.completed_components
        ]
        assert parked_io.live_state is not None
        assert parked_io.surface is not None
        _assert_parity(parked_io.live_state, parked_io.surface, state, parked_io.surface)
        resumed = run_plan(
            engine,
            project_id=parked_project_id,
            evidence_scope_id=parked_scope_id,
            plan=plan,
            plan_id=parked_plan_id,
            plan_version=1,
            plan_row_id=parked_plan_id,
            backends=_runner_backends(),
            io=NullIO(),
            resume_from=state,
            resume_decision=ResumeDecision(response="continue"),
        )
        unbroken_io = _CaptureContinueIO()
        unbroken = run_plan(
            engine,
            project_id=unbroken_project_id,
            evidence_scope_id=unbroken_scope_id,
            plan=plan,
            plan_id=unbroken_plan_id,
            plan_version=1,
            plan_row_id=unbroken_plan_id,
            backends=_runner_backends(),
            io=unbroken_io,
        )
        assert [outcome.status for outcome in resumed.steps] == [
            outcome.status for outcome in unbroken.steps
        ]
        assert resumed.collation_render == unbroken.collation_render
        assert unbroken_io.live_state is not None
        assert unbroken_io.surface is not None
        _assert_parity(unbroken_io.live_state, unbroken_io.surface, state, parked_io.surface)
        with engine.connect() as conn:
            status = conn.execute(
                select(capability_run.c.status).where(
                    capability_run.c.capability_run_id == parked.capability_run_id
                )
            ).scalar_one()
        assert status == resumed.status
    finally:
        _cleanup(engine, parked_project_id)
        _cleanup(engine, unbroken_project_id)


def test_class9_sees_failed_replacement_rerun_from_runner_attempted_map(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G3: a failed replacement re-run feeds class 9 at the next boundary scan."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        outcome, successful_runs, state = _walk_to_completion(
            engine, project_id=project_id, scope_id=scope_id, plan=plan, plan_id=plan_id
        )
        base = steering_events.base_payload(
            capability_run_id=outcome.capability_run_id,
            plan_id=plan_id,
            plan_version=1,
            boundary="after_component",
            component="characterise",
        )
        rerun_state, directive = runner_module._apply_replacement_rerun(
            engine,
            project_id=project_id,
            state=state,
            adjustment=Adjust(
                directive_deltas={"characterise": {"characterise": {"themes": "more"}}}
            ),
            base=base,
            event_run_id=successful_runs["characterise"],
            component="characterise",
        )

        def fail_characterise(*args: Any, **kwargs: Any) -> dict[str, Any]:
            del args, kwargs
            raise CharacteriseFailure(coverage={"base_counts": {}}, error="forced rerun failure")

        monkeypatch.setattr(harness, "characterise_scope", fail_characterise)
        attempted_runs = runner_module._registry_run_ids(successful_runs)
        outcomes: list[Any] = []
        flags: list[dict[str, Any]] = []
        _, failed_run_id = runner_module._run_component_rerun(
            engine,
            NullIO(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            state=rerun_state,
            component="characterise",
            directive_delta=directive,
            backends=_runner_backends(),
            session_id=None,
            successful_runs=successful_runs,
            attempted_runs=attempted_runs,
            blocked_discretionary={},
            step_outcomes=outcomes,
            flagged_events=flags,
            capability_run_id=outcome.capability_run_id,
        )
        assert attempted_runs["characterise"] == failed_run_id
        triggers = runner_module._floor_boundary_triggers(
            engine,
            boundary="after_screen",
            project_id=project_id,
            evidence_scope_id=scope_id,
            attempted_runs=attempted_runs,
        )
        assert any(
            trigger["trigger"] == "downstream_capability_reduced"
            and trigger["detail"].get("event_type") == "component.failed"
            for trigger in triggers
        )
    finally:
        _cleanup(engine, project_id)


def test_class9_sees_failed_segment_rewalk_from_runner_attempted_map(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G3: a failed segment re-walk feeds class 9 at the next boundary scan."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        outcome, successful_runs, state, completed = _boundary_state(
            engine, project_id=project_id, scope_id=scope_id, plan=plan, plan_id=plan_id
        )

        def fail_screen(*args: Any, **kwargs: Any) -> dict[str, Any]:
            del args, kwargs
            raise RuntimeError("forced segment re-walk failure")

        monkeypatch.setattr(harness, "screen_sources", fail_screen)
        attempted_runs = runner_module._registry_run_ids(successful_runs)
        result = runner_module._run_segment_reentry(
            engine,
            NullIO(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            state=state,
            segment_start="acquire",
            boundary_component="characterise",
            directive_deltas=_AMENDMENT,
            backends=_runner_backends(),
            session_id=None,
            successful_runs=successful_runs,
            attempted_runs=attempted_runs,
            blocked_discretionary={},
            completed_components=completed,
            step_outcomes=[],
            flagged_events=[],
            capability_run_id=outcome.capability_run_id,
        )
        assert result.run_failed is True
        assert attempted_runs["screen"] == result.most_recent_attempted_run_id
        triggers = runner_module._floor_boundary_triggers(
            engine,
            boundary="after_screen",
            project_id=project_id,
            evidence_scope_id=scope_id,
            attempted_runs=attempted_runs,
        )
        assert any(
            trigger["trigger"] == "downstream_capability_reduced"
            and trigger["detail"].get("event_type") == "component.failed"
            for trigger in triggers
        )
    finally:
        _cleanup(engine, project_id)


def test_segment_reentry_parity_reparks_at_the_represented_boundary(engine: Engine) -> None:
    """G3 parity: additive resume re-walks and parks at its one re-presentation."""
    parked_project_id: uuid.UUID | None = None
    unbroken_project_id: uuid.UUID | None = None
    amendment = {"acquire": {"search": {"guidance": ["focus on UK policy"]}}}
    try:
        parked_project_id, parked_scope_id = _seed_project(engine)
        unbroken_project_id, unbroken_scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="frequent")
        parked_plan_id = _insert_plan_row(
            engine, project_id=parked_project_id, scope_id=parked_scope_id, plan=plan
        )
        unbroken_plan_id = _insert_plan_row(
            engine, project_id=unbroken_project_id, scope_id=unbroken_scope_id, plan=plan
        )
        unbroken_io = _BoundaryResponseIO(
            "characterise", ReEnterSegment(segment_start="acquire", directive_deltas=amendment)
        )
        unbroken = run_plan(
            engine,
            project_id=unbroken_project_id,
            evidence_scope_id=unbroken_scope_id,
            plan=plan,
            plan_id=unbroken_plan_id,
            plan_version=1,
            plan_row_id=unbroken_plan_id,
            backends=_runner_backends(),
            io=unbroken_io,
        )
        parked_io = _BoundaryParkIO("characterise")
        parked = run_plan(
            engine,
            project_id=parked_project_id,
            evidence_scope_id=parked_scope_id,
            plan=plan,
            plan_id=parked_plan_id,
            plan_version=1,
            plan_row_id=parked_plan_id,
            backends=_runner_backends(),
            io=parked_io,
        )
        assert parked.capability_run_id is not None
        initial = build(
            engine, project_id=parked_project_id, capability_run_id=parked.capability_run_id
        )
        assert unbroken_io.live_state is not None
        assert unbroken_io.surface is not None
        assert parked_io.live_state is not None
        assert parked_io.surface is not None
        _assert_parity(unbroken_io.live_state, unbroken_io.surface, initial, parked_io.surface)
        reparking = run_plan(
            engine,
            project_id=parked_project_id,
            evidence_scope_id=parked_scope_id,
            plan=initial.plan,
            plan_id=initial.plan_id,
            plan_version=initial.plan_version,
            plan_row_id=initial.plan_row_id,
            backends=_runner_backends(),
            io=parked_io,
            resume_from=initial,
            resume_decision=ResumeDecision(
                response="segment_reentry",
                component="characterise",
                segment_start="acquire",
                directive_deltas=amendment,
                boundary="after_component",
            ),
        )
        assert unbroken.status == "succeeded"
        assert reparking.status == "paused"
        assert parked_io.presentations == 2
        reparking_state = build(
            engine,
            project_id=parked_project_id,
            capability_run_id=parked.capability_run_id,
        )
        assert reparking_state.attempted_runs["characterise"] != initial.attempted_runs[
            "characterise"
        ]
    finally:
        _cleanup(engine, parked_project_id)
        _cleanup(engine, unbroken_project_id)


def test_adjust_answer_parity_reads_the_amended_plan(engine: Engine) -> None:
    """An adjust persisted at the parked answer is read as the next plan version."""
    parked_project_id: uuid.UUID | None = None
    unbroken_project_id: uuid.UUID | None = None
    delta = {"screen_abstract": {"screening": {"criteria": ["Include policy trials"]}}}
    try:
        parked_project_id, parked_scope_id = _seed_project(engine)
        unbroken_project_id, unbroken_scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="frequent")
        parked_plan_id = _insert_plan_row(
            engine, project_id=parked_project_id, scope_id=parked_scope_id, plan=plan
        )
        unbroken_plan_id = _insert_plan_row(
            engine, project_id=unbroken_project_id, scope_id=unbroken_scope_id, plan=plan
        )
        unbroken_io = _BoundaryResponseIO("acquire", Adjust(directive_deltas=delta))
        unbroken = run_plan(
            engine,
            project_id=unbroken_project_id,
            evidence_scope_id=unbroken_scope_id,
            plan=plan,
            plan_id=unbroken_plan_id,
            plan_version=1,
            plan_row_id=unbroken_plan_id,
            backends=_runner_backends(),
            io=unbroken_io,
        )
        parked_io = _BoundaryParkIO("acquire")
        parked = run_plan(
            engine,
            project_id=parked_project_id,
            evidence_scope_id=parked_scope_id,
            plan=plan,
            plan_id=parked_plan_id,
            plan_version=1,
            plan_row_id=parked_plan_id,
            backends=_runner_backends(),
            io=parked_io,
        )
        assert parked.capability_run_id is not None
        state = build(
            engine, project_id=parked_project_id, capability_run_id=parked.capability_run_id
        )
        assert unbroken_io.live_state is not None
        assert unbroken_io.surface is not None
        assert parked_io.surface is not None
        _assert_parity(unbroken_io.live_state, unbroken_io.surface, state, parked_io.surface)
        base = steering_events.base_payload(
            capability_run_id=state.capability_run_id,
            plan_id=state.plan_id,
            plan_version=state.plan_version,
            boundary="after_component",
            component="acquire",
        )
        runner_state = runner_module._SteeringState(
            plan=state.plan,
            plan_id=state.plan_id,
            plan_version=state.plan_version,
            plan_row_id=state.plan_row_id,
            chain=state.chain,
            pause_points=state.pause_points,
            pending_overlays=state.pending_overlays,
        )
        runner_module._apply_runner_adjustment(
            engine,
            project_id=parked_project_id,
            state=runner_state,
            adjustment=Adjust(directive_deltas=delta),
            completed_components=state.completed_components,
            base=base,
            event_run_id=state.most_recent_attempted_run_id,
        )
        amended = build(
            engine, project_id=parked_project_id, capability_run_id=state.capability_run_id
        )
        resumed = run_plan(
            engine,
            project_id=parked_project_id,
            evidence_scope_id=parked_scope_id,
            plan=amended.plan,
            plan_id=amended.plan_id,
            plan_version=amended.plan_version,
            plan_row_id=amended.plan_row_id,
            backends=_runner_backends(),
            io=NullIO(),
            resume_from=amended,
            resume_decision=ResumeDecision(response="adjust"),
        )
        assert amended.plan.screening_criteria == delta["screen_abstract"]["screening"]["criteria"]
        assert resumed.status == unbroken.status == "succeeded"
    finally:
        _cleanup(engine, parked_project_id)
        _cleanup(engine, unbroken_project_id)


def test_freetext_multifragment_overlay_parity_replays_compiled_deltas(engine: Engine) -> None:
    """G5 replays the exact confirmed fan-out ``compiled[].delta`` event shape."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="frequent")
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        parked = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=_BoundaryParkIO("acquire"),
        )
        assert parked.capability_run_id is not None
        state = build(engine, project_id=project_id, capability_run_id=parked.capability_run_id)
        fragments = [
            {
                "fragment_text": "focus rural themes",
                "kind": "plan_adjustment",
                "component": "characterise",
                "delta": {"characterise": {"guidance": ["focus on rural areas"]}},
                "rerun_mode": None,
            },
            {
                "fragment_text": "strengthen synthesis",
                "kind": "plan_adjustment",
                "component": "synthesise",
                "delta": {"synthesis": {"boosts": ["equity"]}},
                "rerun_mode": None,
            },
        ]
        with engine.begin() as conn:
            events.append(
                conn,
                project_id=project_id,
                run_id=state.most_recent_attempted_run_id,
                event_type=steering_events.STEERING_DECISION,
                payload={
                    **steering_events.base_payload(
                        capability_run_id=state.capability_run_id,
                        plan_id=state.plan_id,
                        plan_version=state.plan_version,
                        boundary="after_component",
                        component="acquire",
                    ),
                    "decided_by": "user",
                    "authored_by": "user",
                    "response": "adjust",
                    "confirmed": True,
                    "user_text": "focus rural themes and strengthen synthesis",
                    "rerun_mode": None,
                    "interpreted_action": {"compiled": fragments, "refused": [], "summary": ""},
                },
            )
        rebuilt = build(engine, project_id=project_id, capability_run_id=state.capability_run_id)
        expected: dict[str, dict[str, Any]] = {}
        for fragment in fragments:
            component_name = fragment["component"]
            fragment_delta = fragment["delta"]
            assert isinstance(component_name, str)
            assert isinstance(fragment_delta, dict)
            expected = runner_module._extend_overlays(
                expected, {component_name: fragment_delta}
            )
        assert rebuilt.pending_overlays == expected
    finally:
        _cleanup(engine, project_id)


def test_failed_then_successful_rerun_parity_clears_stale_discretion_block(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G4 replacement rerun moves the reference and clears its old failure block."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        outcome, successful_runs, state = _walk_to_completion(
            engine, project_id=project_id, scope_id=scope_id, plan=plan, plan_id=plan_id
        )
        base = steering_events.base_payload(
            capability_run_id=outcome.capability_run_id,
            plan_id=plan_id,
            plan_version=1,
            boundary="after_component",
            component="characterise",
        )
        rerun_state, directive = runner_module._apply_replacement_rerun(
            engine,
            project_id=project_id,
            state=state,
            adjustment=Adjust(
                directive_deltas={"characterise": {"characterise": {"themes": "more"}}}
            ),
            base=base,
            event_run_id=successful_runs["characterise"],
            component="characterise",
        )
        original = getattr(harness, "characterise_scope")  # noqa: B009 — implicit re-export

        def fail_characterise(*args: Any, **kwargs: Any) -> dict[str, Any]:
            del args, kwargs
            raise CharacteriseFailure(coverage={"base_counts": {}}, error="forced rerun failure")

        monkeypatch.setattr(harness, "characterise_scope", fail_characterise)
        attempted: dict[str, uuid.UUID] = {}
        blocked: dict[str, str] = {}
        steps: list[Any] = []
        flags: list[dict[str, Any]] = []
        runner_module._run_component_rerun(
            engine,
            NullIO(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            state=rerun_state,
            component="characterise",
            directive_delta=directive,
            backends=_runner_backends(),
            session_id=None,
            successful_runs=successful_runs,
            attempted_runs=attempted,
            blocked_discretionary=blocked,
            step_outcomes=steps,
            flagged_events=flags,
            capability_run_id=outcome.capability_run_id,
        )
        failed_run_id = attempted["characterise"]
        assert "characterise" in blocked
        monkeypatch.setattr(harness, "characterise_scope", original)
        _, successful_run_id = runner_module._run_component_rerun(
            engine,
            NullIO(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            state=rerun_state,
            component="characterise",
            directive_delta=directive,
            backends=_runner_backends(),
            session_id=None,
            successful_runs=successful_runs,
            attempted_runs=attempted,
            blocked_discretionary=blocked,
            step_outcomes=steps,
            flagged_events=flags,
            capability_run_id=outcome.capability_run_id,
        )
        assert successful_run_id != failed_run_id
        assert attempted["characterise"] == successful_run_id
        assert successful_runs["characterise"] == successful_run_id
        assert "characterise" not in blocked
    finally:
        _cleanup(engine, project_id)
