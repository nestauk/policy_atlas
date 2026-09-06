"""HTTP coverage for run-dispatch preconditions and ownership opacity."""

from __future__ import annotations

import uuid
from pathlib import Path

from tests.api.resource_support import api_client, create_task


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
