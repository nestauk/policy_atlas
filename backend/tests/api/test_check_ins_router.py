"""HTTP coverage for check-in ownership and empty durable-history projection."""

from __future__ import annotations

import uuid
from pathlib import Path

from tests.api.resource_support import api_client, create_project


def test_check_ins_are_owner_scoped_and_empty_before_a_walk_parks(tmp_path: Path) -> None:
    """Expose no transport-memory check-ins for a project with no parked run."""
    with api_client(tmp_path) as (client, owner, other):
        project_id = create_project(client, owner)
        pending = client.get(f"/api/v1/projects/{project_id}/check-ins", headers=owner)
        assert pending.status_code == 200
        assert pending.json() == []

        absent = client.get(f"/api/v1/projects/{uuid.uuid4()}/check-ins", headers=other)
        cross_owner = client.get(f"/api/v1/projects/{project_id}/check-ins", headers=other)
        assert absent.status_code == cross_owner.status_code == 404
        assert absent.json() == cross_owner.json()
