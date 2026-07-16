"""Additive segment re-entry tests (task 024, contract decision 7a).

Segment re-entry is a NEW bounded runner construct (plan-review finding M3): at
an ``after_component`` boundary the walk jumps back to ``acquire`` with an
amended directive, re-walks forward through every already-completed component up
to the boundary in chain order, then re-enters the boundary once. Additive by
construction — the re-walked components run their normal directives plus the
amendment, and each component's own memo/skip logic means nothing already
processed is reprocessed. One re-entry cycle per boundary.

These exercise the runner mechanics against a real DB with stub backends
(``search_backends=[]`` — the re-search adds no new docs in the stub env, so the
"nothing reprocessed" invariant shows as unchanged screen row counts and the
union is the original corpus; genuine doc-addition needs a search-backend stub,
recorded as a friction, not a mechanic under test here).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from policy_atlas.core import events
from policy_atlas.core.schema import (
    characterisation_result,
    orchestration_plan,
    runs,
    source_screening_result,
)
from policy_atlas.runtime import harness, steering_events
from policy_atlas.runtime.orchestration_plan import OrchestrationPlan, compose
from policy_atlas.runtime.runner import (
    NullIO,
    _run_segment_reentry,
    _SteeringState,
    run_plan,
)
from policy_atlas.runtime.steering import (
    Continue,
    ReEnterSegment,
    SteeringAdjustmentError,
    SteeringResponse,
    apply_segment_reentry,
)
from tests.runtime.test_runner import _base_plan, _runner_backends, _seed_project
from tests.runtime.test_steering import ScriptedIO, _cleanup_project, _insert_plan_row

# The re-walked segment at an after-characterise boundary in the deep chain.
_SEGMENT = [
    "acquire",
    "screen_abstract",
    "classify",
    "appraise",
    "ingest_full_text",
    "screen_full",
    "characterise",
]
_AMENDMENT = {"acquire": {"search": {"guidance": ["prioritise UK policy evaluations"]}}}


class _BoundaryIO:
    """IO that answers with scripted responses at one after_component boundary.

    Every other pause continues. At ``boundary_component``'s after_component
    boundary the next scripted response is returned (popped); once exhausted the
    boundary continues too — so a re-presentation after a re-walk sees Continue
    unless a response was scripted for it.
    """

    def __init__(
        self,
        *,
        boundary_component: str,
        boundary_responses: list[SteeringResponse],
    ) -> None:
        self.boundary_component = boundary_component
        self.boundary_responses = list(boundary_responses)
        self.check_ins: list[tuple[str, dict[str, Any]]] = []
        self.pauses: list[tuple[dict[str, Any], str]] = []

    def check_in(self, component: str, payload: dict[str, Any]) -> None:
        self.check_ins.append((component, payload))

    def pause(self, point: dict[str, Any], render: str) -> SteeringResponse:
        self.pauses.append((dict(point), render))
        at_boundary = (
            point.get("component") == self.boundary_component
            and point.get("boundary") == "after_component"
        )
        if at_boundary and self.boundary_responses:
            return self.boundary_responses.pop(0)
        return Continue()


def _plan_compiled(engine: Engine, project_id: uuid.UUID) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        return [
            entry
            for entry in events.read(conn, project_id)
            if entry["event_type"] == "plan.compiled"
        ]


def _runs_by_component(compiled: list[dict[str, Any]]) -> dict[str, list[uuid.UUID]]:
    by_component: dict[str, list[uuid.UUID]] = {}
    for entry in compiled:
        by_component.setdefault(entry["payload"]["component"], []).append(entry["run_id"])
    return by_component


def test_segment_reentry_happy_path_re_walks_segment_and_reenters_once(
    engine: Engine,
) -> None:
    """acquire..characterise re-run with fresh run ids; nothing already screened
    is reprocessed; a new additive plan version + decision land; the boundary is
    re-presented once; the reference moves to the re-walk characterise; every new
    run threads the capability_run."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="frequent")
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        io = _BoundaryIO(
            boundary_component="characterise",
            boundary_responses=[
                ReEnterSegment(segment_start="acquire", directive_deltas=_AMENDMENT)
            ],
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
        # The walk completed through synthesise.
        assert [step.component for step in outcome.steps][-1] == "synthesise"

        compiled = _plan_compiled(engine, project_id)
        runs_by_component = _runs_by_component(compiled)

        # Every segment component ran twice (original + re-walk) with fresh ids.
        for component in _SEGMENT:
            ids = runs_by_component[component]
            assert len(ids) == 2, f"{component} should have re-walked once"
            assert ids[0] != ids[1]
        # Components after the boundary ran once (only after the re-entry).
        for component in ("select", "extract", "group", "synthesise"):
            assert len(runs_by_component[component]) == 1

        # Nothing already processed is reprocessed: exactly one stage-1 row per
        # doc (a reprocessing re-walk would have written a second per doc).
        with engine.connect() as conn:
            stage1_rows = conn.execute(
                select(func.count()).select_from(source_screening_result).where(
                    source_screening_result.c.project_id == project_id,
                    source_screening_result.c.screen_stage == 1,
                )
            ).scalar_one()
            stage1_docs = conn.execute(
                select(
                    func.count(func.distinct(source_screening_result.c.project_source_snapshot_id))
                ).where(
                    source_screening_result.c.project_id == project_id,
                    source_screening_result.c.screen_stage == 1,
                )
            ).scalar_one()
        assert stage1_rows == stage1_docs

        # A new user-attributed plan version records the additive re-entry.
        with engine.connect() as conn:
            plan_rows = conn.execute(
                select(
                    orchestration_plan.c.version,
                    orchestration_plan.c.status,
                    orchestration_plan.c.created_by,
                )
                .where(orchestration_plan.c.project_id == project_id)
                .order_by(orchestration_plan.c.version)
            ).all()
        assert [(r.version, r.status, r.created_by) for r in plan_rows] == [
            (1, "superseded", "planner"),
            (2, "approved", "user"),
        ]

        # The decision event stamps rerun_mode=additive and names the segment.
        with engine.connect() as conn:
            additive = [
                entry
                for entry in events.read(conn, project_id)
                if entry["event_type"] == steering_events.STEERING_DECISION
                and entry["payload"].get("rerun_mode") == "additive"
            ]
        assert len(additive) == 1
        action = additive[0]["payload"]["interpreted_action"]
        assert action["segment_start"] == "acquire"
        assert action["boundary"] == "characterise"
        assert action["amended_directive_keys"] == ["acquire"]

        # The boundary was re-presented exactly once (two after-characterise pauses).
        char_pauses = [
            point
            for point, _ in io.pauses
            if point.get("component") == "characterise"
            and point.get("boundary") == "after_component"
        ]
        assert len(char_pauses) == 2

        # Union coverage / reference moves forward: select references the re-walk
        # characterise run, not the original.
        char_runs = runs_by_component["characterise"]
        select_payload = next(
            e["payload"] for e in compiled if e["payload"]["component"] == "select"
        )
        assert select_payload["characterisation_run_id"] == str(char_runs[1])
        assert select_payload["characterisation_run_id"] != str(char_runs[0])

        # Every new run threads the walk identity.
        with engine.connect() as conn:
            capability_run_ids = (
                conn.execute(
                    select(runs.c.capability_run_id).where(runs.c.project_id == project_id)
                )
                .scalars()
                .all()
            )
        assert set(capability_run_ids) == {outcome.capability_run_id}
    finally:
        _cleanup_project(engine, project_id)


def test_segment_reentry_second_request_at_reentry_boundary_rejected(
    engine: Engine,
) -> None:
    """A second ReEnterSegment at the re-presented boundary is rejected (one
    re-entry cycle per boundary); Continue then proceeds and the walk completes."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="frequent")
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        io = _BoundaryIO(
            boundary_component="characterise",
            boundary_responses=[
                # #1 triggers the re-walk; #2 (on re-presentation) is rejected;
                # #3 continues the re-presentation loop.
                ReEnterSegment(segment_start="acquire", directive_deltas=_AMENDMENT),
                ReEnterSegment(segment_start="acquire", directive_deltas=_AMENDMENT),
                Continue(),
            ],
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
            rejected = [
                entry
                for entry in events.read(conn, project_id)
                if entry["event_type"] == steering_events.STEERING_REJECTED
                and entry["payload"].get("component") == "characterise"
            ]
            additive = [
                entry
                for entry in events.read(conn, project_id)
                if entry["event_type"] == steering_events.STEERING_DECISION
                and entry["payload"].get("rerun_mode") == "additive"
            ]
        # Exactly one re-entry happened; the second request was rejected.
        assert len(additive) == 1
        assert len(rejected) == 1
        assert "not available" in rejected[0]["payload"]["reason"]
        # Still only one re-walk: characterise ran twice, not three times.
        runs_by_component = _runs_by_component(_plan_compiled(engine, project_id))
        assert len(runs_by_component["characterise"]) == 2
    finally:
        _cleanup_project(engine, project_id)


def test_segment_reentry_rejected_at_before_component_boundary(engine: Engine) -> None:
    """Segment re-entry stays OUT at P4 (before synthesise): a re-walk there would
    additively re-run the run-scoped select/extract/group, so a ReEnterSegment at
    moderate's before_synthesise pause is rejected (Task 15b narrows the old
    'all before_component' rule — P2 now ALLOWS segment re-entry)."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        # Moderate mode pauses at deepening_selection (after select) and
        # before_synthesise; drive the before_synthesise pause.
        plan = _base_plan(steering_mode="moderate")
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)

        class _BeforeSynthIO:
            def __init__(self) -> None:
                self.pauses: list[dict[str, Any]] = []
                self.fired = False

            def check_in(self, component: str, payload: dict[str, Any]) -> None:
                del component, payload

            def pause(self, point: dict[str, Any], render: str) -> SteeringResponse:
                del render
                self.pauses.append(dict(point))
                # Fire the (to-be-rejected) re-entry once, then continue on the
                # re-prompt so the pause loop terminates.
                if (
                    not self.fired
                    and point.get("component") == "synthesise"
                    and point.get("boundary") == "before_component"
                ):
                    self.fired = True
                    return ReEnterSegment(
                        segment_start="acquire", directive_deltas=_AMENDMENT
                    )
                return Continue()

        io = _BeforeSynthIO()
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
        # The rejected re-entry does not derail the walk.
        assert outcome.status == "succeeded"
        with engine.connect() as conn:
            rejected = [
                entry
                for entry in events.read(conn, project_id)
                if entry["event_type"] == steering_events.STEERING_REJECTED
                and entry["payload"].get("boundary") == "before_component"
            ]
            additive = [
                entry
                for entry in events.read(conn, project_id)
                if entry["event_type"] == steering_events.STEERING_DECISION
                and entry["payload"].get("rerun_mode") == "additive"
            ]
        assert len(rejected) == 1
        assert additive == []
    finally:
        _cleanup_project(engine, project_id)


def _boundary_state(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    plan: OrchestrationPlan,
    plan_id: uuid.UUID,
) -> tuple[Any, dict[str, uuid.UUID], _SteeringState, set[str]]:
    """Walk a plan to completion, then reconstruct the state at the after-
    characterise boundary (completed = acquire..characterise) for isolated
    segment-re-walk tests."""
    outcome = run_plan(
        engine,
        project_id=project_id,
        evidence_scope_id=scope_id,
        plan=plan,
        plan_id=plan_id,
        plan_version=1,
        plan_row_id=plan_id,
        backends=_runner_backends(),
        io=NullIO(),
    )
    assert outcome.status == "succeeded"
    successful_runs = {
        step.component: step.run_id
        for step in outcome.steps
        if step.status == "succeeded" and step.run_id is not None and step.component in _SEGMENT
    }
    state = _SteeringState(
        plan=plan,
        plan_id=plan_id,
        plan_version=1,
        plan_row_id=plan_id,
        chain=compose(plan),
        pause_points=set(),
    )
    return outcome, successful_runs, state, set(_SEGMENT)


def test_segment_reentry_spine_failure_mid_segment_degrades_and_does_not_reenter(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A spine-component (screen) failure mid re-walk ends the run and never
    re-enters the boundary — normal component-failure semantics."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        outcome, successful_runs, state, completed = _boundary_state(
            engine, project_id=project_id, scope_id=scope_id, plan=plan, plan_id=plan_id
        )

        def failing_screen(*args: Any, **kwargs: Any) -> dict[str, Any]:
            del args, kwargs
            raise RuntimeError("forced re-walk screen failure")

        monkeypatch.setattr(harness, "screen_sources", failing_screen)

        step_outcomes: list[Any] = []
        flagged_events: list[dict[str, Any]] = []
        result = _run_segment_reentry(
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
            blocked_discretionary={},
            completed_components=completed,
            step_outcomes=step_outcomes,
            flagged_events=flagged_events,
            capability_run_id=outcome.capability_run_id,
        )

        # Spine failure ends the run; the boundary is not re-entered.
        assert result.run_failed is True
        assert result.reenter_boundary is False
        # acquire re-walked (spine, ok), screen_abstract failed and stopped it.
        failed = [flag for flag in flagged_events if flag["status"] == "failed"]
        assert any(flag["component"] == "screen_abstract" for flag in failed)
        assert [o.component for o in step_outcomes][-1] == "screen_abstract"
        assert step_outcomes[-1].status == "failed"
    finally:
        _cleanup_project(engine, project_id)


def test_segment_reentry_invariant_rejects_completed_component_after_boundary(
    engine: Engine,
) -> None:
    """Downstream-invalidation guard (point 6): a boundary pause means nothing
    beyond it ran, so a completed component after the boundary is a bug — asserted,
    not handled."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        outcome, successful_runs, state, completed = _boundary_state(
            engine, project_id=project_id, scope_id=scope_id, plan=plan, plan_id=plan_id
        )
        # "select" sits after the characterise boundary — an impossible completed set.
        bad_completed = completed | {"select"}
        with pytest.raises(AssertionError, match="downstream of boundary"):
            _run_segment_reentry(
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
                blocked_discretionary={},
                completed_components=bad_completed,
                step_outcomes=[],
                flagged_events=[],
                capability_run_id=outcome.capability_run_id,
            )
    finally:
        _cleanup_project(engine, project_id)


def test_apply_segment_reentry_rejects_unshipped_segment_start(engine: Engine) -> None:
    """Fail-closed: only ``acquire`` is a shipped re-entry segment."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        with engine.begin() as conn:
            plan_row = conn.execute(
                select(orchestration_plan).where(orchestration_plan.c.plan_id == plan_id)
            ).one()
            with pytest.raises(SteeringAdjustmentError, match="not shipped"):
                apply_segment_reentry(
                    conn,
                    project_id=project_id,
                    plan_row=plan_row,
                    plan=plan,
                    segment_start="classify",
                    directive_deltas={},
                )
    finally:
        _cleanup_project(engine, project_id)


def test_apply_segment_reentry_rejects_malformed_amendment(engine: Engine) -> None:
    """Fail-closed: each amendment delta validates through the component parser
    (an empty B1 guidance list is malformed)."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        with engine.begin() as conn:
            plan_row = conn.execute(
                select(orchestration_plan).where(orchestration_plan.c.plan_id == plan_id)
            ).one()
            with pytest.raises(SteeringAdjustmentError):
                apply_segment_reentry(
                    conn,
                    project_id=project_id,
                    plan_row=plan_row,
                    plan=plan,
                    segment_start="acquire",
                    directive_deltas={"acquire": {"search": {"guidance": []}}},
                )
    finally:
        _cleanup_project(engine, project_id)


def test_no_new_characterisation_row_leak_and_both_persist(engine: Engine) -> None:
    """Union coverage at the row grain: after an additive re-entry both the
    original and re-walk characterisation rows persist (replacement-never-deletes
    holds for the re-walked outputs too)."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="frequent")
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        io = _BoundaryIO(
            boundary_component="characterise",
            boundary_responses=[
                ReEnterSegment(segment_start="acquire", directive_deltas=_AMENDMENT)
            ],
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
        runs_by_component = _runs_by_component(_plan_compiled(engine, project_id))
        char_runs = set(runs_by_component["characterise"])
        with engine.connect() as conn:
            row_runs = set(
                conn.execute(
                    select(characterisation_result.c.run_id).where(
                        characterisation_result.c.project_id == project_id
                    )
                )
                .scalars()
                .all()
            )
        # Both characterisation runs left an immutable row behind.
        assert char_runs == row_runs
        assert len(row_runs) == 2
    finally:
        _cleanup_project(engine, project_id)


# --- P2 (before select) segment re-entry (Task 15b) ------------------------


def test_p2_segment_reentry_re_presents_once_and_second_request_rejected(
    engine: Engine,
) -> None:
    """At P2 an additive re-search re-walks acquire→characterise and re-presents
    P2 once; a second ReEnterSegment on the re-presentation is rejected (the
    one-cycle rule), then Continue proceeds into select."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()  # moderate: P2 (evidence_base_coverage) pauses
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        io = ScriptedIO(
            by_steer_point={
                "evidence_base_coverage": [
                    ReEnterSegment(segment_start="acquire", directive_deltas=_AMENDMENT),
                    ReEnterSegment(segment_start="acquire", directive_deltas=_AMENDMENT),
                    Continue(),
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
            additive = [
                entry
                for entry in events.read(conn, project_id)
                if entry["event_type"] == steering_events.STEERING_DECISION
                and entry["payload"].get("rerun_mode") == "additive"
            ]
            rejected = [
                entry
                for entry in events.read(conn, project_id)
                if entry["event_type"] == steering_events.STEERING_REJECTED
                and entry["payload"].get("boundary") == "before_component"
            ]
        # Exactly one re-walk; the second request rejected (one cycle).
        assert len(additive) == 1
        assert additive[0]["payload"]["boundary"] == "before_component"
        assert len(rejected) == 1
        assert "not available" in rejected[0]["payload"]["reason"]
        # characterise re-walked once (original + one re-walk), not twice.
        runs_by_component = _runs_by_component(_plan_compiled(engine, project_id))
        assert len(runs_by_component["characterise"]) == 2
    finally:
        _cleanup_project(engine, project_id)


def test_p2_criteria_rescreen_writes_new_generation(engine: Engine) -> None:
    """A P2 criteria re-screen rides the segment-re-entry path with a screening
    amendment: the acquire→characterise re-walk re-screens abstracts at new
    criteria, minting a fresh screen generation (supersession, ADR 0022)."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()  # moderate: P2 pauses
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        io = ScriptedIO(
            by_steer_point={
                "evidence_base_coverage": [
                    ReEnterSegment(
                        segment_start="acquire",
                        directive_deltas={
                            "screen_abstract": {
                                "screening": {
                                    "criteria": ["Include only randomised controlled trials"],
                                    "rescreen": True,
                                }
                            }
                        },
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
            generations = set(
                conn.execute(
                    select(source_screening_result.c.screen_generation).where(
                        source_screening_result.c.project_id == project_id
                    )
                )
                .scalars()
                .all()
            )
        # The re-screen minted a fresh generation coexisting with the original.
        assert 0 in generations
        assert max(generations) >= 1
    finally:
        _cleanup_project(engine, project_id)
