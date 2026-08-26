"""HTTP coverage for owner-scoped portfolio routes and project assignment."""

from __future__ import annotations

import uuid
from pathlib import Path

from tests.api.resource_support import api_client, create_project


def test_create_portfolio_returns_created_fields(tmp_path: Path) -> None:
    """Creating a portfolio echoes its fields and starts with no tasks."""
    with api_client(tmp_path) as (client, owner, _):
        response = client.post(
            "/api/v1/portfolios",
            headers=owner,
            json={"name": "Housing", "description": "Housing policy work"},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["name"] == "Housing"
        assert body["description"] == "Housing policy work"
        assert body["portfolio_id"]
        assert body["created_at"]
        assert body["task_count"] == 0


def test_create_portfolio_without_description_reads_back_none(tmp_path: Path) -> None:
    """An omitted description reads back as None, not a missing key."""
    with api_client(tmp_path) as (client, owner, _):
        response = client.post("/api/v1/portfolios", headers=owner, json={"name": "Housing"})
        assert response.status_code == 201, response.text
        assert response.json()["description"] is None


def test_list_portfolios_derives_task_counts(tmp_path: Path) -> None:
    """Listing portfolios reports each one's derived, live task count."""
    with api_client(tmp_path) as (client, owner, _):
        first_response = client.post("/api/v1/portfolios", headers=owner, json={"name": "First"})
        second_response = client.post("/api/v1/portfolios", headers=owner, json={"name": "Second"})
        first = first_response.json()["portfolio_id"]
        second = second_response.json()["portfolio_id"]
        project_ids = [create_project(client, owner) for _ in range(3)]
        for project_id in project_ids[:2]:
            patched = client.patch(
                f"/api/v1/projects/{project_id}",
                headers=owner,
                json={"portfolio_ids": [first]},
            )
            assert patched.status_code == 200, patched.text
        patched = client.patch(
            f"/api/v1/projects/{project_ids[2]}",
            headers=owner,
            json={"portfolio_ids": [second]},
        )
        assert patched.status_code == 200, patched.text

        listed = client.get("/api/v1/portfolios", headers=owner)
        assert listed.status_code == 200
        body = listed.json()
        assert body["pagination"]["total_items"] == 2
        counts = {row["portfolio_id"]: row["task_count"] for row in body["data"]}
        assert counts == {first: 2, second: 1}


def test_list_portfolios_is_owner_scoped(tmp_path: Path) -> None:
    """A portfolio created by another owner does not leak into this list."""
    with api_client(tmp_path) as (client, owner, other):
        response = client.post("/api/v1/portfolios", headers=other, json={"name": "Not yours"})
        assert response.status_code == 201, response.text
        listed = client.get("/api/v1/portfolios", headers=owner)
        assert listed.status_code == 200
        assert listed.json()["data"] == []


def test_get_portfolio_returns_derived_task_count(tmp_path: Path) -> None:
    """Fetching a single portfolio reflects its currently assigned tasks."""
    with api_client(tmp_path) as (client, owner, _):
        created = client.post("/api/v1/portfolios", headers=owner, json={"name": "Housing"})
        portfolio_id = created.json()["portfolio_id"]
        project_id = create_project(client, owner)
        patched = client.patch(
            f"/api/v1/projects/{project_id}",
            headers=owner,
            json={"portfolio_ids": [portfolio_id]},
        )
        assert patched.status_code == 200, patched.text

        fetched = client.get(f"/api/v1/portfolios/{portfolio_id}", headers=owner)
        assert fetched.status_code == 200
        assert fetched.json()["task_count"] == 1


def test_patch_portfolio_partial_update_leaves_omitted_fields(tmp_path: Path) -> None:
    """A PATCH with only name leaves description untouched (exclude_unset)."""
    with api_client(tmp_path) as (client, owner, _):
        created = client.post(
            "/api/v1/portfolios",
            headers=owner,
            json={"name": "Housing", "description": "Original"},
        )
        portfolio_id = created.json()["portfolio_id"]

        both = client.patch(
            f"/api/v1/portfolios/{portfolio_id}",
            headers=owner,
            json={"name": "Renamed", "description": "Updated"},
        )
        assert both.status_code == 200, both.text
        assert both.json()["name"] == "Renamed"
        assert both.json()["description"] == "Updated"

        name_only = client.patch(
            f"/api/v1/portfolios/{portfolio_id}",
            headers=owner,
            json={"name": "Renamed again"},
        )
        assert name_only.status_code == 200, name_only.text
        assert name_only.json()["name"] == "Renamed again"
        assert name_only.json()["description"] == "Updated"


def test_assign_project_to_portfolio(tmp_path: Path) -> None:
    """Assigning a portfolio to a project persists and is readable back."""
    with api_client(tmp_path) as (client, owner, _):
        created = client.post("/api/v1/portfolios", headers=owner, json={"name": "Housing"})
        portfolio_id = created.json()["portfolio_id"]
        project_id = create_project(client, owner)

        patched = client.patch(
            f"/api/v1/projects/{project_id}",
            headers=owner,
            json={"portfolio_ids": [portfolio_id]},
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["portfolio_ids"] == [portfolio_id]

        fetched = client.get(f"/api/v1/projects/{project_id}", headers=owner)
        assert fetched.status_code == 200
        assert fetched.json()["portfolio_ids"] == [portfolio_id]


def test_unassign_project_from_portfolio_drops_task_count(tmp_path: Path) -> None:
    """Setting portfolio_ids to [] clears membership and shrinks the count."""
    with api_client(tmp_path) as (client, owner, _):
        created = client.post("/api/v1/portfolios", headers=owner, json={"name": "Housing"})
        portfolio_id = created.json()["portfolio_id"]
        project_id = create_project(client, owner)
        assigned = client.patch(
            f"/api/v1/projects/{project_id}",
            headers=owner,
            json={"portfolio_ids": [portfolio_id]},
        )
        assert assigned.status_code == 200, assigned.text

        unassigned = client.patch(
            f"/api/v1/projects/{project_id}",
            headers=owner,
            json={"portfolio_ids": []},
        )
        assert unassigned.status_code == 200, unassigned.text
        assert unassigned.json()["portfolio_ids"] == []

        fetched = client.get(f"/api/v1/portfolios/{portfolio_id}", headers=owner)
        assert fetched.status_code == 200
        assert fetched.json()["task_count"] == 0


def test_unknown_and_cross_owner_portfolio_404s_are_indistinguishable(tmp_path: Path) -> None:
    """An unknown portfolio and someone else's yield identical 404 bodies."""
    with api_client(tmp_path) as (client, owner, other):
        other_created = client.post("/api/v1/portfolios", headers=other, json={"name": "Not yours"})
        other_portfolio_id = other_created.json()["portfolio_id"]

        absent = client.get(f"/api/v1/portfolios/{uuid.uuid4()}", headers=owner)
        cross_owner = client.get(f"/api/v1/portfolios/{other_portfolio_id}", headers=owner)
        assert cross_owner.status_code == absent.status_code == 404
        assert cross_owner.json() == absent.json()

        absent_patch = client.patch(
            f"/api/v1/portfolios/{uuid.uuid4()}", headers=owner, json={"name": "X"}
        )
        cross_owner_patch = client.patch(
            f"/api/v1/portfolios/{other_portfolio_id}", headers=owner, json={"name": "X"}
        )
        assert cross_owner_patch.status_code == absent_patch.status_code == 404
        assert cross_owner_patch.json() == absent_patch.json()


def test_assign_project_to_unowned_portfolio_is_404_and_does_not_write(tmp_path: Path) -> None:
    """Assigning someone else's portfolio 404s and leaves the project untouched."""
    with api_client(tmp_path) as (client, owner, other):
        other_created = client.post("/api/v1/portfolios", headers=other, json={"name": "Not yours"})
        other_portfolio_id = other_created.json()["portfolio_id"]
        project_id = create_project(client, owner)

        response = client.patch(
            f"/api/v1/projects/{project_id}",
            headers=owner,
            json={"portfolio_ids": [other_portfolio_id]},
        )
        assert response.status_code == 404

        fetched = client.get(f"/api/v1/projects/{project_id}", headers=owner)
        assert fetched.status_code == 200
        assert fetched.json()["portfolio_ids"] == []


def test_project_with_no_portfolio_is_unaffected(tmp_path: Path) -> None:
    """A freshly created project reports no portfolio in both get and list."""
    with api_client(tmp_path) as (client, owner, _):
        project_id = create_project(client, owner)

        fetched = client.get(f"/api/v1/projects/{project_id}", headers=owner)
        assert fetched.status_code == 200
        assert fetched.json()["portfolio_ids"] == []

        listed = client.get("/api/v1/projects", headers=owner)
        assert listed.status_code == 200
        row = next(row for row in listed.json()["data"] if row["project_id"] == project_id)
        assert row["portfolio_ids"] == []


def test_task_can_belong_to_many_portfolios(tmp_path: Path) -> None:
    """One task in two projects counts in both task_counts and lists both ids."""
    with api_client(tmp_path) as (client, owner, _):
        first = client.post("/api/v1/portfolios", headers=owner, json={"name": "First"}).json()[
            "portfolio_id"
        ]
        second = client.post("/api/v1/portfolios", headers=owner, json={"name": "Second"}).json()[
            "portfolio_id"
        ]
        project_id = create_project(client, owner)
        patched = client.patch(
            f"/api/v1/projects/{project_id}",
            headers=owner,
            json={"portfolio_ids": [first, second, first]},
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["portfolio_ids"] == [first, second]

        listed = client.get("/api/v1/portfolios", headers=owner)
        counts = {row["portfolio_id"]: row["task_count"] for row in listed.json()["data"]}
        assert counts[first] == 1
        assert counts[second] == 1


def test_omitting_portfolio_ids_leaves_membership_unchanged(tmp_path: Path) -> None:
    """A name-only PATCH does not drop existing memberships."""
    with api_client(tmp_path) as (client, owner, _):
        portfolio_id = client.post(
            "/api/v1/portfolios", headers=owner, json={"name": "Housing"}
        ).json()["portfolio_id"]
        project_id = create_project(client, owner)
        assigned = client.patch(
            f"/api/v1/projects/{project_id}",
            headers=owner,
            json={"portfolio_ids": [portfolio_id]},
        )
        assert assigned.status_code == 200, assigned.text

        renamed = client.patch(
            f"/api/v1/projects/{project_id}",
            headers=owner,
            json={"name": "Renamed only"},
        )
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()["name"] == "Renamed only"
        assert renamed.json()["portfolio_ids"] == [portfolio_id]
