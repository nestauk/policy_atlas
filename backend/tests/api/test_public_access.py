"""Conditionally-public Task read access (task 037, Phase 2)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.engine import Engine
from structlog.testing import capture_logs

from policy_atlas.core.schema import project
from tests.api.org_support import make_org, make_project, ops_enrol, seeded, tenancy_client
from tests.api.resource_support import api_client, create_project


def _share(client: TestClient, project_id: str, owner: dict[str, str]) -> None:
    """Turn on public sharing through the owner-only HTTP surface."""
    response = client.patch(
        f"/api/v1/projects/{project_id}", headers=owner, json={"is_public": True}
    )
    assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    "headers",
    [None, {"Authorization": "Bearer garbage"}, {"Authorization": "Basic eA=="},
     {"Authorization": "Bearer"}, {"Authorization": "Token x"}],
    ids=["absent", "garbage-bearer", "basic", "bare-bearer", "wrong-scheme"],
)
def test_optional_auth_uses_the_raw_authorization_header(
    tmp_path: Path, headers: dict[str, str] | None
) -> None:
    """Only a missing header is anonymous; every malformed present one is 401."""
    with api_client(tmp_path) as (client, owner, _other):
        project_id = create_project(client, owner)
        _share(client, project_id, owner)

        response = client.get(f"/api/v1/projects/{project_id}/funnel", headers=headers)
        assert response.status_code == (200 if headers is None else 401), response.text


def test_unsharing_revokes_anonymous_access_with_the_standard_404(tmp_path: Path) -> None:
    """A public flag flip is checked on the next anonymous request."""
    with api_client(tmp_path) as (client, owner, _other):
        project_id = create_project(client, owner)
        _share(client, project_id, owner)
        assert client.get(f"/api/v1/projects/{project_id}/funnel").status_code == 200

        revoked = client.patch(
            f"/api/v1/projects/{project_id}", headers=owner, json={"is_public": False}
        )
        assert revoked.status_code == 200, revoked.text
        denied = client.get(f"/api/v1/projects/{project_id}/funnel")
        unknown = client.get(f"/api/v1/projects/{uuid.uuid4()}/funnel")
        assert denied.status_code == unknown.status_code == 404
        assert denied.content == unknown.content


def test_archiving_a_public_project_revokes_all_anonymous_reads(tmp_path: Path) -> None:
    """Public access is limited to rows whose status remains active."""
    with api_client(tmp_path) as (client, owner, _other):
        project_id = create_project(client, owner)
        _share(client, project_id, owner)
        archived = client.post(f"/api/v1/projects/{project_id}/archive", headers=owner)
        assert archived.status_code == 200, archived.text

        assert client.get(f"/api/v1/projects/{project_id}").status_code == 404
        assert client.get(f"/api/v1/projects/{project_id}/funnel").status_code == 404


def test_public_project_response_is_redacted_for_anonymous_and_outside_users(
    tmp_path: Path,
) -> None:
    """Public-leg project reads remove owner and membership details for every outsider."""
    with api_client(tmp_path) as (client, owner, other):
        project_id = create_project(client, owner)
        _share(client, project_id, owner)

        anonymous = client.get(f"/api/v1/projects/{project_id}")
        assert anonymous.status_code == 200, anonymous.text
        outsider = client.get(f"/api/v1/projects/{project_id}", headers=other)
        assert outsider.status_code == 200, outsider.text
        for body in (anonymous.json(), outsider.json()):
            assert body["access"] == "public"
            assert body["is_owner"] is False
            assert body["owner_display"] is None
            assert body["portfolio_ids"] == []

        owner_read = client.get(f"/api/v1/projects/{project_id}", headers=owner)
        assert owner_read.status_code == 200
        assert owner_read.json()["access"] == "full"
        assert client.get(f"/api/v1/projects/{project_id}/funnel", headers=other).status_code == 200


def test_public_projects_do_not_widen_listings(tmp_path: Path) -> None:
    """A direct public link does not create a public index or listing entry."""
    with api_client(tmp_path) as (client, owner, other):
        project_id = create_project(client, owner)
        _share(client, project_id, owner)

        listed = client.get("/api/v1/projects", headers=other)
        assert listed.status_code == 200, listed.text
        assert project_id not in {row["project_id"] for row in listed.json()["data"]}


def test_admin_read_of_a_public_project_emits_no_admin_trace(
    engine: Engine, tmp_path: Path
) -> None:
    """A public-leg read is not served by the administrator privilege leg."""
    with tenancy_client(tmp_path, count=2) as (client, (owner, admin)):
        with seeded(engine) as conn:
            owner_org = make_org(conn, name="Owner Org")
            admin_org = make_org(conn, name="Admin Org")
            ops_enrol(conn, user_id=owner.user_id, org_id=owner_org, display_name="Owner")
            ops_enrol(
                conn, user_id=admin.user_id, org_id=admin_org, display_name="Admin", is_admin=True
            )
            project_id = make_project(
                conn, owner_user_id=owner.user_id, org_id=owner_org, visibility="private"
            )
            conn.execute(
                update(project).where(project.c.project_id == project_id).values(is_public=True)
            )

        with capture_logs() as captured:
            response = client.get(f"/api/v1/projects/{project_id}", headers=admin.headers)

        assert response.status_code == 200, response.text
        assert response.json()["access"] == "public"
        assert not [line for line in captured if line.get("event") == "admin_read"]
