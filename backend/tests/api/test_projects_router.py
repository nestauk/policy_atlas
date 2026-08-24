"""HTTP coverage for owner-scoped project lifecycle routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import Engine

from policy_atlas.core.schema import capability_run, evidence_scope
from tests.api.resource_support import api_client, create_project
from tests.helpers import seed_source


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


def test_project_with_no_run_reports_source_count_as_none(tmp_path: Path) -> None:
    """No capability_run at all: `source_count` is `None`, not `0` — the question is unasked."""
    with api_client(tmp_path) as (client, owner, _other):
        project_id = create_project(client, owner)

        detail = client.get(f"/api/v1/projects/{project_id}", headers=owner)
        assert detail.status_code == 200
        assert detail.json()["source_count"] is None

        listed = client.get("/api/v1/projects", headers=owner)
        assert listed.status_code == 200
        assert listed.json()["data"][0]["source_count"] is None


def test_project_with_a_run_reports_source_count_as_the_snapshot_row_count(
    engine: Engine, tmp_path: Path
) -> None:
    """A capability_run makes `source_count` real: 0 reads `0`, not `None`; N sources reads `N`."""
    with api_client(tmp_path) as (client, owner, _other):
        project_id = create_project(client, owner)
        with engine.begin() as conn:
            scope_id = uuid.uuid4()
            conn.execute(
                evidence_scope.insert().values(
                    evidence_scope_id=scope_id,
                    project_id=uuid.UUID(project_id),
                    intent="source count coverage",
                    context={},
                    created_at=datetime.now(UTC),
                )
            )
            conn.execute(
                capability_run.insert().values(
                    capability_run_id=uuid.uuid4(),
                    project_id=uuid.UUID(project_id),
                    evidence_scope_id=scope_id,
                    capability="evidence_base",
                    plan_id=uuid.uuid4(),
                    plan_version=1,
                    status="succeeded",
                    session_id=None,
                    started_at=datetime.now(UTC),
                    ended_at=datetime.now(UTC),
                )
            )

        zero_sources = client.get(f"/api/v1/projects/{project_id}", headers=owner)
        assert zero_sources.status_code == 200
        assert zero_sources.json()["source_count"] == 0

        with engine.begin() as conn:
            for _ in range(3):
                seed_source(conn, uuid.UUID(project_id))

        three_sources = client.get(f"/api/v1/projects/{project_id}", headers=owner)
        assert three_sources.status_code == 200
        assert three_sources.json()["source_count"] == 3

        listed = client.get("/api/v1/projects", headers=owner)
        assert listed.status_code == 200
        assert listed.json()["data"][0]["source_count"] == 3
