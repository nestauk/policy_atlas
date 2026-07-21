"""HTTP coverage for owner-scoped project lifecycle routes."""

from __future__ import annotations

import uuid
from pathlib import Path

from tests.api.resource_support import api_client, create_project


def test_projects_create_list_get_archive_and_owner_404(tmp_path: Path) -> None:
    """Exercise lifecycle reads, pagination, archive idempotence, and BOLA opacity."""
    with api_client(tmp_path) as (client, owner, other):
        project_id = create_project(client, owner)
        listed = client.get("/api/v1/projects?page=1&page_size=1", headers=owner)
        assert listed.status_code == 200
        assert listed.json()["pagination"] == {"page": 1, "page_size": 1, "total_items": 1}
        assert listed.json()["data"][0]["project_id"] == project_id
        assert client.get(f"/api/v1/projects/{project_id}", headers=owner).status_code == 200

        renamed = client.patch(
            f"/api/v1/projects/{project_id}", headers=owner, json={"name": "Renamed"}
        )
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "Renamed"

        absent = client.get(f"/api/v1/projects/{uuid.uuid4()}", headers=other)
        cross_owner = client.get(f"/api/v1/projects/{project_id}", headers=other)
        assert cross_owner.status_code == absent.status_code == 404
        assert cross_owner.json() == absent.json()
        assert client.get(f"/api/v1/projects/{project_id}").status_code == 401

        assert (
            client.post(f"/api/v1/projects/{project_id}/archive", headers=owner).status_code
            == 200
        )
        assert (
            client.post(f"/api/v1/projects/{project_id}/archive", headers=owner).status_code
            == 200
        )
        assert client.get("/api/v1/projects", headers=owner).json()["data"] == []
        assert client.get("/api/v1/projects?status=archived", headers=owner).status_code == 200


def test_projects_reject_page_sizes_over_contract_cap(tmp_path: Path) -> None:
    """Keep the server pagination cap at the documented contract boundary."""
    with api_client(tmp_path) as (client, owner, _):
        response = client.get("/api/v1/projects?page_size=201", headers=owner)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
