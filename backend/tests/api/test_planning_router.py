"""HTTP coverage for planner-turn idempotence and approved-plan persistence."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.contract import PlanDraft
from policy_atlas.api.deps import get_planner_backend
from policy_atlas.api.routers import planning
from policy_atlas.core.schema import capability_run, evidence_scope, orchestration_plan
from policy_atlas.runtime.planner import StubPlannerBackend
from policy_atlas.runtime.planner_prompt import PlannerTurnWire
from tests.api.resource_support import api_client, create_project


class CountingPlanner(StubPlannerBackend):
    """Stub planner that exposes the route's idempotence behaviour."""

    def __init__(self) -> None:
        self.calls = 0

    def plan_turn(
        self,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        session_id: uuid.UUID | None = None,
    ) -> PlannerTurnWire:
        """Count and delegate deterministic planner turns."""
        self.calls += 1
        return super().plan_turn(turns, previous_draft, session_id=session_id)


def test_planning_session_cache_evicts_oldest_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep unapproved conversations honestly bounded and restartable after eviction."""
    planning._sessions.clear()
    monkeypatch.setattr(planning, "PLAN_SESSION_CACHE_MAX", 2)
    first, second, third = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    planning._session(first).draft = PlanDraft(question="old")
    planning._session(second)
    planning._session(third)
    assert first not in planning._sessions
    assert second in planning._sessions
    assert third in planning._sessions


def test_planning_turn_is_idempotent_and_ready_turn_persists_plan(
    engine: Engine, tmp_path: Path
) -> None:
    """Return an identical cached turn and persist the second ready proposal."""
    planning._sessions.clear()
    stub = CountingPlanner()
    with api_client(tmp_path, {get_planner_backend: lambda: stub}) as (client, owner, _):
        project_id = create_project(client, owner)
        turn_id = str(uuid.uuid4())
        first = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={"message": "How can cities reduce heat risk?", "client_turn_id": turn_id},
        )
        duplicate = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={"message": "How can cities reduce heat risk?", "client_turn_id": turn_id},
        )
        assert first.status_code == duplicate.status_code == 200
        assert first.json() == duplicate.json()
        assert stub.calls == 1

        ready = client.post(
            f"/api/v1/projects/{project_id}/planning-turns",
            headers=owner,
            json={
                "message": "A comparison of intervention options",
                "client_turn_id": str(uuid.uuid4()),
            },
        )
        assert ready.status_code == 200
        assert ready.json()["plan"]["ready"] is True
        persisted = client.get(f"/api/v1/projects/{project_id}/plan", headers=owner)
        assert persisted.status_code == 200
        assert persisted.json()["status"] == "approved"
    with engine.connect() as conn:
        assert conn.execute(
            select(orchestration_plan.c.plan_id).where(
                orchestration_plan.c.project_id == uuid.UUID(project_id)
            )
        ).one_or_none() is not None


def test_planning_turn_409s_while_walk_active_or_parked(
    engine: Engine, tmp_path: Path
) -> None:
    """409 `run_active` fences replanning while a walk is running or parked.

    A finished walk (status `succeeded`) leaves no active row, so the turn
    must proceed (adjudicated review decision codex-2, 2026-07-21: steering
    is the sanctioned mid-run plan channel, and fencing planning-turns here
    is what makes the continuation reducer's latest-approved plan selection
    provably the walk's own lineage).
    """
    planning._sessions.clear()
    stub = CountingPlanner()
    with api_client(tmp_path, {get_planner_backend: lambda: stub}) as (client, owner, _other):
        project_id = create_project(client, owner)
        run_id = uuid.uuid4()
        scope_id = uuid.uuid4()
        with engine.begin() as conn:
            conn.execute(
                evidence_scope.insert().values(
                    evidence_scope_id=scope_id,
                    project_id=uuid.UUID(project_id),
                    intent="planning-router fence sweep",
                    context={},
                    created_at=datetime.now(UTC),
                )
            )
            conn.execute(
                capability_run.insert().values(
                    capability_run_id=run_id,
                    project_id=uuid.UUID(project_id),
                    evidence_scope_id=scope_id,
                    capability="evidence_base",
                    plan_id=uuid.uuid4(),
                    plan_version=1,
                    status="paused",
                    session_id=None,
                    started_at=datetime.now(UTC),
                    ended_at=None,
                )
            )
        try:
            paused = client.post(
                f"/api/v1/projects/{project_id}/planning-turns",
                headers=owner,
                json={"message": "Steer this walk", "client_turn_id": str(uuid.uuid4())},
            )
            assert paused.status_code == 409
            assert paused.json()["error"]["code"] == "run_active"

            with engine.begin() as conn:
                conn.execute(
                    capability_run.update()
                    .where(capability_run.c.capability_run_id == run_id)
                    .values(status="running")
                )
            running = client.post(
                f"/api/v1/projects/{project_id}/planning-turns",
                headers=owner,
                json={"message": "Steer this walk again", "client_turn_id": str(uuid.uuid4())},
            )
            assert running.status_code == 409
            assert running.json()["error"]["code"] == "run_active"

            with engine.begin() as conn:
                conn.execute(
                    capability_run.update()
                    .where(capability_run.c.capability_run_id == run_id)
                    .values(status="succeeded", ended_at=datetime.now(UTC))
                )
            succeeded = client.post(
                f"/api/v1/projects/{project_id}/planning-turns",
                headers=owner,
                json={
                    "message": "Replan now the walk is done",
                    "client_turn_id": str(uuid.uuid4()),
                },
            )
            assert succeeded.status_code != 409
            assert succeeded.status_code == 200
        finally:
            # Leave no `running`/`paused` row behind: a later test's fresh app
            # lifespan runs the orphan-sweep startup check over every such row
            # in the shared test DB, and this row was inserted directly,
            # without an attaching event (mirrors test_api_conformance.py's
            # run_active conflict test).
            with engine.begin() as conn:
                conn.execute(
                    capability_run.update()
                    .where(capability_run.c.capability_run_id == run_id)
                    .values(status="aborted", ended_at=datetime.now(UTC))
                )
