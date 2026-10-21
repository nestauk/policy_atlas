"""HTTP coverage for run-dispatch preconditions and ownership opacity."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.engine import Engine

from policy_atlas.core.schema import artefact, capability_run, evidence_scope
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
