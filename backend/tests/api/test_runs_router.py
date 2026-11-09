"""HTTP coverage for run-dispatch preconditions and ownership opacity."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.engine import Engine

from policy_atlas.core import events
from policy_atlas.core.schema import artefact, capability_run, evidence_scope, runs
from tests.api.resource_support import api_client, create_task
from tests.helpers import delete_task_data, now


def test_runs_require_approved_plan_and_hide_cross_owner_tasks(tmp_path: Path) -> None:
    """Reject malformed dispatches before any executor work and preserve BOLA opacity."""
    with api_client(tmp_path) as (client, owner, other):
        task_id = create_task(client, owner)
        no_plan = client.post(f"/api/v1/tasks/{task_id}/runs", headers=owner, json={})
        assert no_plan.status_code == 400
        assert no_plan.json()["error"]["code"] == "malformed"

        absent = client.post(f"/api/v1/tasks/{uuid.uuid4()}/runs", headers=other, json={})
        cross_owner = client.post(f"/api/v1/tasks/{task_id}/runs", headers=other, json={})
        assert absent.status_code == cross_owner.status_code == 404
        assert absent.json() == cross_owner.json()


def test_a_run_reports_the_artefact_it_wrote(engine: Engine, tmp_path: Path) -> None:
    """``artefact_id`` is what the walk produced, not a guess from its status.

    The scoping start states and the baseline band read this field to decide
    whether a baseline exists, so a walk that has written nothing must say
    ``null`` and the same walk must name the artefact the moment one is
    attached — on the listing and on the single-run read alike.
    """
    with api_client(tmp_path) as (client, owner, _other):
        task_id = uuid.UUID(create_task(client, owner))
        try:
            scope_id = uuid.uuid4()
            run_id = uuid.uuid4()
            with engine.begin() as conn:
                conn.execute(
                    evidence_scope.insert().values(
                        evidence_scope_id=scope_id,
                        task_id=task_id,
                        intent="What works?",
                        context={},
                        created_at=now(),
                    )
                )
                conn.execute(
                    capability_run.insert().values(
                        capability_run_id=run_id,
                        task_id=task_id,
                        evidence_scope_id=scope_id,
                        capability="evidence_search",
                        plan_id=uuid.uuid4(),
                        plan_version=1,
                        status="running",
                        started_at=now(),
                    )
                )

            listed = client.get(f"/api/v1/tasks/{task_id}/runs", headers=owner)
            fetched = client.get(f"/api/v1/tasks/{task_id}/runs/{run_id}", headers=owner)
            assert listed.status_code == fetched.status_code == 200, listed.text
            assert listed.json()["data"][0]["artefact_id"] is None
            assert fetched.json()["artefact_id"] is None

            artefact_id = uuid.uuid4()
            with engine.begin() as conn:
                conn.execute(
                    artefact.insert().values(
                        artefact_id=artefact_id,
                        task_id=task_id,
                        capability_run_id=run_id,
                        title="Baseline",
                        created_at=now(),
                    )
                )

            listed_again = client.get(f"/api/v1/tasks/{task_id}/runs", headers=owner)
            fetched_again = client.get(
                f"/api/v1/tasks/{task_id}/runs/{run_id}", headers=owner
            )
            assert listed_again.json()["data"][0]["artefact_id"] == str(artefact_id)
            assert fetched_again.json()["artefact_id"] == str(artefact_id)
        finally:
            with engine.begin() as conn:
                delete_task_data(conn, task_id)


def test_a_walk_carries_its_own_steps_and_not_its_option_searches(
    engine: Engine, tmp_path: Path
) -> None:
    """Task 058, round 11: each run on the list and the one-run read carries its steps.

    The steps are the walk's own, folded from the frames the stream sends: the
    walk-level ``option_searches`` (no component run; its completion before
    round 11 named no walk) stays with the walk, a child's ``acquire`` with the
    child.
    """
    with api_client(tmp_path) as (client, owner, _other):
        task_id = uuid.UUID(create_task(client, owner))
        try:
            scope_id = uuid.uuid4()
            walk, child = uuid.uuid4(), uuid.uuid4()
            with engine.begin() as conn:
                conn.execute(
                    evidence_scope.insert().values(
                        evidence_scope_id=scope_id,
                        task_id=task_id,
                        intent="What works?",
                        context={},
                        created_at=now(),
                    )
                )
                for walk_id, parent in ((walk, None), (child, walk)):
                    conn.execute(
                        capability_run.insert().values(
                            capability_run_id=walk_id,
                            task_id=task_id,
                            evidence_scope_id=scope_id,
                            capability="options_scoping",
                            plan_id=uuid.uuid4(),
                            plan_version=1,
                            status="running",
                            started_at=now(),
                            parent_capability_run_id=parent,
                        )
                    )

                def component(walk_id: uuid.UUID) -> uuid.UUID:
                    run_id = uuid.uuid4()
                    conn.execute(
                        runs.insert().values(
                            run_id=run_id,
                            task_id=task_id,
                            status="running",
                            started_at=now(),
                            capability_run_id=walk_id,
                        )
                    )
                    return run_id

                def append(run_id: uuid.UUID | None, kind: str, payload: dict[str, object]) -> None:
                    events.append(
                        conn, task_id=task_id, run_id=run_id, event_type=kind, payload=payload
                    )

                suggest = component(walk)
                append(suggest, "run.started", {"component": "suggest"})
                append(suggest, "component.completed", {"component": "suggest", "suggested": 4})
                append(
                    None,
                    "run.started",
                    {"component": "option_searches", "capability_run_id": str(walk)},
                )
                own_search = component(walk)
                child_search = component(child)
                append(child_search, "run.started", {"component": "acquire"})
                append(own_search, "run.started", {"component": "acquire"})
                append(
                    own_search,
                    "component.completed",
                    {"component": "acquire", "acquired": 312, "wall_clock_s": 4.5},
                )
                # A completion written before round 11: no walk named.
                append(
                    None,
                    "component.completed",
                    {"component": "option_searches", "total": 4, "finished": 4, "sources": 9},
                )

            listed = client.get(f"/api/v1/tasks/{task_id}/runs", headers=owner)
            assert listed.status_code == 200, listed.text
            by_id = {row["capability_run_id"]: row for row in listed.json()["data"]}
            steps = by_id[str(walk)]["stages"]
            assert [(step["stage"], step["status"]) for step in steps] == [
                ("suggest", "completed"),
                ("option_searches", "completed"),
                ("acquire", "completed"),
            ]
            assert steps[0]["label"] == "Suggesting options"
            assert steps[0]["counts"] == [{"value": 4, "noun": "suggested"}]
            assert steps[0]["started_at"] is not None and steps[0]["ended_at"] is not None
            assert steps[1]["summary"] == {"total": 4, "finished": 4, "sources": 9}
            assert steps[2]["seconds"] == 4.5
            assert steps[2]["counts"] == [{"value": 312, "noun": "found"}]
            child_steps = by_id[str(child)]["stages"]
            assert [(step["stage"], step["status"]) for step in child_steps] == [
                ("acquire", "started")
            ]
            assert child_steps[0]["ended_at"] is None

            fetched = client.get(f"/api/v1/tasks/{task_id}/runs/{walk}", headers=owner)
            assert fetched.status_code == 200, fetched.text
            assert fetched.json()["stages"] == steps
        finally:
            with engine.begin() as conn:
                delete_task_data(conn, task_id)
