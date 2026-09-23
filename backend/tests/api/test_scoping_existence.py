"""What exists and what is active, for an options-scoping task (task 045, S15).

Owner at the plan gate: "scoping readers see what exists and what is active".
``TaskOut`` gains ``active_run`` (any running or paused walk, children
included) and ``has_longlist``; ``latest_run`` stays as it was for the
Evidence search and, for a scoping task, skips child walks and option
searches. The admission fences consider parentless walks only, so a running
or finished child never becomes the task's latest run and never blocks a
user action.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.deps import get_executor, get_scoping_task_agent_backend
from policy_atlas.core.schema import (
    artefact,
    capability_run,
    evidence_scope,
    longlist_result,
    runs,
    task,
    task_link,
    task_plan,
)
from policy_atlas.runtime.task_agent_scoping import StubScopingTaskAgentBackend
from tests.api.resource_support import api_client, create_task
from tests.api.test_longlist_start import RecordingExecutor
from tests.helpers import delete_task_data


@pytest.fixture(autouse=True)
def _remove_committed_tasks(engine: Engine):  # type: ignore[no-untyped-def]
    """Hard-delete every task these tests commit (a left scoping walk blocks downgrades)."""
    before = _all_task_ids(engine)
    yield
    created = list(_all_task_ids(engine) - before)
    with engine.begin() as conn:
        conn.execute(task_link.delete().where(task_link.c.source_task_id.in_(created)))
        conn.execute(task_link.delete().where(task_link.c.target_task_id.in_(created)))
        for task_id in created:
            delete_task_data(conn, task_id)


def _all_task_ids(engine: Engine) -> set[uuid.UUID]:
    with engine.connect() as conn:
        return {row[0] for row in conn.execute(select(task.c.task_id))}


def _overrides() -> dict[Callable[..., object], Callable[..., object]]:
    # A confirm opens the longlist walk (task 045, S3); these tests are about
    # the plan versions, so the walk executor opens the walk's row and runs
    # nothing.
    executor = RecordingExecutor(status="succeeded")
    return {
        get_scoping_task_agent_backend: lambda: StubScopingTaskAgentBackend(),
        get_executor: lambda: executor,
    }


def _scoping_task(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "name": "Youth employment options",
            "question": "What could reduce the number of young people not in work?",
            "capability": "options_scoping",
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["task_id"])


_T0 = datetime(2026, 9, 22, 9, 0, tzinfo=UTC)


def _walk(
    engine: Engine,
    task_id: str,
    *,
    purpose: str | None,
    status: str,
    minutes: int,
    parent: uuid.UUID | None = None,
    capability: str = "options_scoping",
) -> uuid.UUID:
    """Commit an intent record of ``purpose`` and one walk under it."""
    tid = uuid.UUID(task_id)
    scope_id = uuid.uuid4()
    walk_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            evidence_scope.insert().values(
                evidence_scope_id=scope_id,
                task_id=tid,
                intent="intent",
                context={},
                created_at=_T0,
                purpose=purpose,
            )
        )
        conn.execute(
            capability_run.insert().values(
                capability_run_id=walk_id,
                task_id=tid,
                evidence_scope_id=scope_id,
                capability=capability,
                plan_id=uuid.uuid4(),
                plan_version=1,
                status=status,
                started_at=_T0 + timedelta(minutes=minutes),
                ended_at=None if status in ("running", "paused") else _T0,
                parent_capability_run_id=parent,
            )
        )
    return walk_id


def _get(client: TestClient, headers: dict[str, str], task_id: str) -> dict[str, Any]:
    response = client.get(f"/api/v1/tasks/{task_id}", headers=headers)
    assert response.status_code == 200, response.text
    return dict(response.json())


def _listed(client: TestClient, headers: dict[str, str], task_id: str) -> dict[str, Any]:
    response = client.get("/api/v1/tasks?page=1&page_size=100", headers=headers)
    assert response.status_code == 200, response.text
    return next(item for item in response.json()["data"] if item["task_id"] == task_id)


# --- latest_run, active_run, has_longlist ------------------------------------------


def test_a_child_walk_is_never_the_task_s_latest_run(engine: Engine, tmp_path: Path) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = _scoping_task(client, owner)
        baseline = _walk(engine, task_id, purpose="baseline", status="succeeded", minutes=0)
        longlist = _walk(engine, task_id, purpose="longlist", status="running", minutes=5)
        child = _walk(
            engine, task_id, purpose="targeted", status="running", minutes=6, parent=longlist
        )
        body = _get(client, owner, task_id)
        assert body["latest_run"]["capability_run_id"] == str(longlist)
        # Active: any running or paused walk, children included — the latest.
        assert body["active_run"]["capability_run_id"] == str(child)
        assert body["has_longlist"] is False

        # Finished, the child still never becomes "the task's run".
        with engine.begin() as conn:
            conn.execute(
                capability_run.update()
                .where(capability_run.c.capability_run_id.in_([child, longlist]))
                .values(status="succeeded", ended_at=_T0)
            )
        body = _get(client, owner, task_id)
        assert body["latest_run"]["capability_run_id"] == str(longlist)
        assert body["active_run"] is None
        # The listing reads the same way.
        listed = _listed(client, owner, task_id)
        assert listed["latest_run"]["capability_run_id"] == str(longlist)
        assert listed["active_run"] is None
        assert baseline != longlist


def test_a_parentless_option_search_is_never_the_latest_run(
    engine: Engine, tmp_path: Path
) -> None:
    """The chat verb *add* starts a targeted walk with no parent (ADR 0039 d5)."""
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = _scoping_task(client, owner)
        longlist = _walk(engine, task_id, purpose="longlist", status="succeeded", minutes=0)
        added = _walk(engine, task_id, purpose="targeted", status="running", minutes=5)
        body = _get(client, owner, task_id)
        assert body["latest_run"]["capability_run_id"] == str(longlist)
        assert body["active_run"]["capability_run_id"] == str(added)
        # The runs read says what each walk is, so the thread can tell an
        # option search from the task's own walks (task 045, S12).
        runs = client.get(f"/api/v1/tasks/{task_id}/runs", headers=owner)
        assert runs.status_code == 200
        by_id = {row["capability_run_id"]: row for row in runs.json()["data"]}
        assert by_id[str(longlist)]["purpose"] == "longlist"
        assert by_id[str(longlist)]["parent_capability_run_id"] is None
        assert by_id[str(added)]["purpose"] == "targeted"
        child = _walk(
            engine, task_id, purpose="targeted", status="running", minutes=6, parent=longlist
        )
        one = client.get(f"/api/v1/tasks/{task_id}/runs/{child}", headers=owner).json()
        assert one["parent_capability_run_id"] == str(longlist)
        assert one["purpose"] == "targeted"


def test_has_longlist_is_the_existence_of_a_longlist_result(
    engine: Engine, tmp_path: Path
) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = _scoping_task(client, owner)
        assert _get(client, owner, task_id)["has_longlist"] is False
        walk = _walk(engine, task_id, purpose="longlist", status="succeeded", minutes=0)
        tid = uuid.UUID(task_id)
        run_id = uuid.uuid4()
        with engine.begin() as conn:
            scope_id = conn.execute(
                select(capability_run.c.evidence_scope_id).where(
                    capability_run.c.capability_run_id == walk
                )
            ).scalar_one()
            conn.execute(
                runs.insert().values(
                    run_id=run_id,
                    task_id=tid,
                    status="succeeded",
                    started_at=_T0,
                    capability_run_id=walk,
                )
            )
            conn.execute(
                longlist_result.insert().values(
                    longlist_result_id=uuid.uuid4(),
                    task_id=tid,
                    evidence_scope_id=scope_id,
                    run_id=run_id,
                    plan_version=1,
                    themes=[],
                    coverage={},
                    judgements={},
                    guesses=[],
                    counts={},
                    provenance={},
                    created_at=_T0,
                )
            )
        assert _get(client, owner, task_id)["has_longlist"] is True
        assert _listed(client, owner, task_id)["has_longlist"] is True


def test_an_evidence_search_task_reads_as_before(engine: Engine, tmp_path: Path) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = create_task(client, owner)
        first = _walk(
            engine,
            task_id,
            purpose=None,
            status="succeeded",
            minutes=0,
            capability="evidence_search",
        )
        second = _walk(
            engine, task_id, purpose=None, status="paused", minutes=5, capability="evidence_search"
        )
        body = _get(client, owner, task_id)
        assert body["latest_run"]["capability_run_id"] == str(second)
        assert body["active_run"]["capability_run_id"] == str(second)
        assert body["has_longlist"] is False
        assert first != second


# --- the admission fences ------------------------------------------------------------


def _finished_parent_with_running_child(engine: Engine, task_id: str) -> None:
    parent = _walk(engine, task_id, purpose="longlist", status="succeeded", minutes=0)
    _walk(engine, task_id, purpose="targeted", status="running", minutes=1, parent=parent)


def test_a_running_child_does_not_fence_post_runs(engine: Engine, tmp_path: Path) -> None:
    """Past the fence: the refusal is the missing plan, not ``run_active``."""
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = _scoping_task(client, owner)
        _finished_parent_with_running_child(engine, task_id)
        response = client.post(f"/api/v1/tasks/{task_id}/runs", headers=owner, json={})
        assert response.status_code == 400, response.text

        # A parentless running walk still fences.
        _walk(engine, task_id, purpose="longlist", status="running", minutes=9)
        response = client.post(f"/api/v1/tasks/{task_id}/runs", headers=owner, json={})
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "run_active"


def test_a_running_child_does_not_fence_a_task_agent_turn(
    engine: Engine, tmp_path: Path
) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = _scoping_task(client, owner)
        _finished_parent_with_running_child(engine, task_id)
        response = client.post(
            f"/api/v1/tasks/{task_id}/task-agent-turns",
            headers=owner,
            json={
                "message": "Young people are not getting into work.",
                "client_turn_id": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 200, response.text


def _to_ready(client: TestClient, headers: dict[str, str], task_id: str) -> None:
    for message in (
        "Young people are not getting into work.",
        "16 to 24 year olds",
        "[confirm part=depth option=standard_pass]",
    ):
        response = client.post(
            f"/api/v1/tasks/{task_id}/task-agent-turns",
            headers=headers,
            json={"message": message, "client_turn_id": str(uuid.uuid4())},
        )
        assert response.status_code == 200, response.text


def test_a_running_child_does_not_fence_confirm_baseline(
    engine: Engine, tmp_path: Path
) -> None:
    with api_client(tmp_path, _overrides()) as (client, owner, _other):
        task_id = _scoping_task(client, owner)
        _to_ready(client, owner, task_id)
        artefact_id = uuid.uuid4()
        with engine.begin() as conn:
            conn.execute(
                artefact.insert().values(
                    artefact_id=artefact_id,
                    task_id=uuid.UUID(task_id),
                    capability_run_id=None,
                    title="Baseline",
                    created_at=_T0,
                )
            )
            plan_version = conn.execute(
                select(task_plan.c.version)
                .where(task_plan.c.task_id == uuid.UUID(task_id))
                .where(task_plan.c.status == "approved")
            ).scalar_one()
        _finished_parent_with_running_child(engine, task_id)
        response = client.post(
            f"/api/v1/tasks/{task_id}/plan/confirm-baseline",
            headers=owner,
            json={"artefact_id": str(artefact_id), "plan_version": plan_version},
        )
        assert response.status_code == 200, response.text
