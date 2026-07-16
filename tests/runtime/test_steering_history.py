"""Steering-history read-model tests (task 024, task 3).

Drives two real ``run_plan`` walks in one project — a moderate-mode walk with
a steer-point Adjust then a Continue, and a minimal-mode walk with a single
Continue — then rebuilds the project's steering history from a fresh
connection and checks the per-walk projection: story identity, event
sequencing, payload-key partitioning and vocabulary filtering.
"""

from __future__ import annotations

import uuid

from sqlalchemy.engine import Engine

from policy_atlas.runtime import steering_events
from policy_atlas.runtime.runner import run_plan
from policy_atlas.runtime.steering import Adjust
from policy_atlas.runtime.steering_history import steering_history
from tests.runtime.test_runner import _base_plan, _runner_backends, _seed_project
from tests.runtime.test_steering import ScriptedIO, _cleanup_project, _insert_plan_row

NON_STEERING_EVENT_TYPES = {"run.started", "plan.compiled", "component.timing"}


def _drive_walk_a(engine: Engine, *, project_id: uuid.UUID, scope_id: uuid.UUID) -> uuid.UUID:
    """Moderate-mode walk: steer-point pause -> Adjust, then a pause -> Continue."""
    plan = _base_plan()  # moderate steering mode, deep chain (default)
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
    assert outcome.capability_run_id is not None
    return outcome.capability_run_id


def _drive_walk_b(engine: Engine, *, project_id: uuid.UUID, scope_id: uuid.UUID) -> uuid.UUID:
    """Minimal-mode walk: a single steer-point pause resolved with Continue."""
    plan = _base_plan(steering_mode="minimal")

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
    assert outcome.status == "succeeded"
    assert outcome.capability_run_id is not None
    return outcome.capability_run_id


def test_two_walk_rebuild_from_fresh_connection(engine: Engine) -> None:
    """steering_history rebuilds both walks' stories, in order, from scratch."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        walk_a_id = _drive_walk_a(engine, project_id=project_id, scope_id=scope_id)
        walk_b_id = _drive_walk_b(engine, project_id=project_id, scope_id=scope_id)

        with engine.connect() as fresh_conn:
            stories = steering_history(fresh_conn, project_id)

        assert len(stories) == 2
        story_a, story_b = stories
        assert story_a["capability_run_id"] == walk_a_id
        assert story_b["capability_run_id"] == walk_b_id
        assert story_a["status"] == "succeeded"
        assert story_b["status"] == "succeeded"

        # Walk A: steer-point pause -> decision(adjust), then pause -> decision(continue).
        a_types = [event["event_type"] for event in story_a["events"]]
        assert a_types == [
            steering_events.STEERING_PAUSE,
            steering_events.STEERING_DECISION,
            steering_events.STEERING_PAUSE,
            steering_events.STEERING_DECISION,
        ]
        a_responses = [
            event["payload"]["response"]
            for event in story_a["events"]
            if event["event_type"] == steering_events.STEERING_DECISION
        ]
        assert a_responses == ["adjust", "continue"]

        # Walk B: a single steer-point pause -> decision(continue).
        b_types = [event["event_type"] for event in story_b["events"]]
        assert b_types == [steering_events.STEERING_PAUSE, steering_events.STEERING_DECISION]
        assert story_b["events"][1]["payload"]["response"] == "continue"

        # No event appears in both stories — payload-key partitioning holds.
        a_ids = {event["payload"]["capability_run_id"] for event in story_a["events"]}
        b_ids = {event["payload"]["capability_run_id"] for event in story_b["events"]}
        assert a_ids == {str(walk_a_id)}
        assert b_ids == {str(walk_b_id)}
        assert a_ids.isdisjoint(b_ids)
    finally:
        _cleanup_project(engine, project_id)


def test_payload_partition_matches_story_walk(engine: Engine) -> None:
    """Every event's payload capability_run_id matches its own story's id."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        _drive_walk_a(engine, project_id=project_id, scope_id=scope_id)
        _drive_walk_b(engine, project_id=project_id, scope_id=scope_id)

        with engine.connect() as conn:
            stories = steering_history(conn, project_id)

        assert stories
        for story in stories:
            for event in story["events"]:
                assert event["payload"]["capability_run_id"] == str(story["capability_run_id"])
    finally:
        _cleanup_project(engine, project_id)


def test_single_walk_filter_returns_only_that_walk(engine: Engine) -> None:
    """A specific capability_run_id returns only that walk's story."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        _drive_walk_a(engine, project_id=project_id, scope_id=scope_id)
        walk_b_id = _drive_walk_b(engine, project_id=project_id, scope_id=scope_id)

        with engine.connect() as conn:
            only_b = steering_history(conn, project_id, capability_run_id=walk_b_id)
            missing = steering_history(conn, project_id, capability_run_id=uuid.uuid4())

        assert len(only_b) == 1
        assert only_b[0]["capability_run_id"] == walk_b_id
        assert {event["payload"]["capability_run_id"] for event in only_b[0]["events"]} == {
            str(walk_b_id)
        }
        assert missing == []
    finally:
        _cleanup_project(engine, project_id)


def test_non_steering_events_excluded(engine: Engine) -> None:
    """Walk stories never surface run.started/plan.compiled/component.timing."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        _drive_walk_a(engine, project_id=project_id, scope_id=scope_id)
        _drive_walk_b(engine, project_id=project_id, scope_id=scope_id)

        with engine.connect() as conn:
            stories = steering_history(conn, project_id)

        assert stories
        for story in stories:
            event_types = {event["event_type"] for event in story["events"]}
            assert event_types.isdisjoint(NON_STEERING_EVENT_TYPES)
    finally:
        _cleanup_project(engine, project_id)
