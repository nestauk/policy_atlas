"""HTTP coverage for owner-scoped project routes and task assignment."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.engine import Engine

from policy_atlas.api.read_models import history
from policy_atlas.core import events
from tests.api.resource_support import api_client, create_task
from tests.helpers import seed_walk


def test_create_project_returns_created_fields(tmp_path: Path) -> None:
    """Creating a project echoes its fields and starts with no tasks."""
    with api_client(tmp_path) as (client, owner, _):
        response = client.post(
            "/api/v1/projects",
            headers=owner,
            json={"name": "Housing", "description": "Housing policy work"},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["name"] == "Housing"
        assert body["description"] == "Housing policy work"
        assert body["project_id"]
        assert body["created_at"]
        assert body["task_count"] == 0


def test_create_project_without_description_reads_back_none(tmp_path: Path) -> None:
    """An omitted description reads back as None, not a missing key."""
    with api_client(tmp_path) as (client, owner, _):
        response = client.post("/api/v1/projects", headers=owner, json={"name": "Housing"})
        assert response.status_code == 201, response.text
        assert response.json()["description"] is None


def test_list_projects_derives_task_counts(tmp_path: Path) -> None:
    """Listing projects reports each one's derived, live task count."""
    with api_client(tmp_path) as (client, owner, _):
        first_response = client.post("/api/v1/projects", headers=owner, json={"name": "First"})
        second_response = client.post("/api/v1/projects", headers=owner, json={"name": "Second"})
        first = first_response.json()["project_id"]
        second = second_response.json()["project_id"]
        task_ids = [create_task(client, owner) for _ in range(3)]
        for task_id in task_ids[:2]:
            patched = client.patch(
                f"/api/v1/tasks/{task_id}",
                headers=owner,
                json={"project_ids": [first]},
            )
            assert patched.status_code == 200, patched.text
        patched = client.patch(
            f"/api/v1/tasks/{task_ids[2]}",
            headers=owner,
            json={"project_ids": [second]},
        )
        assert patched.status_code == 200, patched.text

        listed = client.get("/api/v1/projects", headers=owner)
        assert listed.status_code == 200
        body = listed.json()
        assert body["pagination"]["total_items"] == 2
        counts = {row["project_id"]: row["task_count"] for row in body["data"]}
        assert counts == {first: 2, second: 1}


def test_list_projects_is_owner_scoped(tmp_path: Path) -> None:
    """A project created by another owner does not leak into this list."""
    with api_client(tmp_path) as (client, owner, other):
        response = client.post("/api/v1/projects", headers=other, json={"name": "Not yours"})
        assert response.status_code == 201, response.text
        listed = client.get("/api/v1/projects", headers=owner)
        assert listed.status_code == 200
        assert listed.json()["data"] == []


def test_get_project_returns_derived_task_count(tmp_path: Path) -> None:
    """Fetching a single project reflects its currently assigned tasks."""
    with api_client(tmp_path) as (client, owner, _):
        created = client.post("/api/v1/projects", headers=owner, json={"name": "Housing"})
        project_id = created.json()["project_id"]
        task_id = create_task(client, owner)
        patched = client.patch(
            f"/api/v1/tasks/{task_id}",
            headers=owner,
            json={"project_ids": [project_id]},
        )
        assert patched.status_code == 200, patched.text

        fetched = client.get(f"/api/v1/projects/{project_id}", headers=owner)
        assert fetched.status_code == 200
        assert fetched.json()["task_count"] == 1


def test_patch_project_partial_update_leaves_omitted_fields(tmp_path: Path) -> None:
    """A PATCH with only name leaves description untouched (exclude_unset)."""
    with api_client(tmp_path) as (client, owner, _):
        created = client.post(
            "/api/v1/projects",
            headers=owner,
            json={"name": "Housing", "description": "Original"},
        )
        project_id = created.json()["project_id"]

        both = client.patch(
            f"/api/v1/projects/{project_id}",
            headers=owner,
            json={"name": "Renamed", "description": "Updated"},
        )
        assert both.status_code == 200, both.text
        assert both.json()["name"] == "Renamed"
        assert both.json()["description"] == "Updated"

        name_only = client.patch(
            f"/api/v1/projects/{project_id}",
            headers=owner,
            json={"name": "Renamed again"},
        )
        assert name_only.status_code == 200, name_only.text
        assert name_only.json()["name"] == "Renamed again"
        assert name_only.json()["description"] == "Updated"


def test_assign_task_to_project(tmp_path: Path) -> None:
    """Assigning a project to a task persists and is readable back."""
    with api_client(tmp_path) as (client, owner, _):
        created = client.post("/api/v1/projects", headers=owner, json={"name": "Housing"})
        project_id = created.json()["project_id"]
        task_id = create_task(client, owner)

        patched = client.patch(
            f"/api/v1/tasks/{task_id}",
            headers=owner,
            json={"project_ids": [project_id]},
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["project_ids"] == [project_id]

        fetched = client.get(f"/api/v1/tasks/{task_id}", headers=owner)
        assert fetched.status_code == 200
        assert fetched.json()["project_ids"] == [project_id]


def test_unassign_task_from_project_drops_task_count(tmp_path: Path) -> None:
    """Setting project_ids to [] clears membership and shrinks the count."""
    with api_client(tmp_path) as (client, owner, _):
        created = client.post("/api/v1/projects", headers=owner, json={"name": "Housing"})
        project_id = created.json()["project_id"]
        task_id = create_task(client, owner)
        assigned = client.patch(
            f"/api/v1/tasks/{task_id}",
            headers=owner,
            json={"project_ids": [project_id]},
        )
        assert assigned.status_code == 200, assigned.text

        unassigned = client.patch(
            f"/api/v1/tasks/{task_id}",
            headers=owner,
            json={"project_ids": []},
        )
        assert unassigned.status_code == 200, unassigned.text
        assert unassigned.json()["project_ids"] == []

        fetched = client.get(f"/api/v1/projects/{project_id}", headers=owner)
        assert fetched.status_code == 200
        assert fetched.json()["task_count"] == 0


def test_unknown_and_cross_owner_project_404s_are_indistinguishable(tmp_path: Path) -> None:
    """An unknown project and someone else's yield identical 404 bodies."""
    with api_client(tmp_path) as (client, owner, other):
        other_created = client.post("/api/v1/projects", headers=other, json={"name": "Not yours"})
        other_project_id = other_created.json()["project_id"]

        absent = client.get(f"/api/v1/projects/{uuid.uuid4()}", headers=owner)
        cross_owner = client.get(f"/api/v1/projects/{other_project_id}", headers=owner)
        assert cross_owner.status_code == absent.status_code == 404
        assert cross_owner.json() == absent.json()

        absent_patch = client.patch(
            f"/api/v1/projects/{uuid.uuid4()}", headers=owner, json={"name": "X"}
        )
        cross_owner_patch = client.patch(
            f"/api/v1/projects/{other_project_id}", headers=owner, json={"name": "X"}
        )
        assert cross_owner_patch.status_code == absent_patch.status_code == 404
        assert cross_owner_patch.json() == absent_patch.json()


def test_assign_task_to_unowned_project_is_404_and_does_not_write(tmp_path: Path) -> None:
    """Assigning someone else's project 404s and leaves the task untouched."""
    with api_client(tmp_path) as (client, owner, other):
        other_created = client.post("/api/v1/projects", headers=other, json={"name": "Not yours"})
        other_project_id = other_created.json()["project_id"]
        task_id = create_task(client, owner)

        response = client.patch(
            f"/api/v1/tasks/{task_id}",
            headers=owner,
            json={"project_ids": [other_project_id]},
        )
        assert response.status_code == 404

        fetched = client.get(f"/api/v1/tasks/{task_id}", headers=owner)
        assert fetched.status_code == 200
        assert fetched.json()["project_ids"] == []


def test_task_with_no_project_is_unaffected(tmp_path: Path) -> None:
    """A freshly created task reports no project in both get and list."""
    with api_client(tmp_path) as (client, owner, _):
        task_id = create_task(client, owner)

        fetched = client.get(f"/api/v1/tasks/{task_id}", headers=owner)
        assert fetched.status_code == 200
        assert fetched.json()["project_ids"] == []

        listed = client.get("/api/v1/tasks", headers=owner)
        assert listed.status_code == 200
        row = next(row for row in listed.json()["data"] if row["task_id"] == task_id)
        assert row["project_ids"] == []


def test_a_project_patch_body_of_explicit_null_name_is_refused(tmp_path: Path) -> None:
    """`{"name": null}` was written by the allow-list splat and 500d.

    `ProjectUpdate` already refused an explicit null `visibility`, and `name`
    needed the same guard for the same reason: the route's splat takes whatever
    the `exclude_unset` dump contains, so a null went to a NOT NULL column.
    `description` is different and stays different — that column is nullable,
    so a null clears it.
    """
    with api_client(tmp_path) as (client, owner, _):
        created = client.post(
            "/api/v1/projects",
            headers=owner,
            json={"name": "Housing", "description": "Housing policy work"},
        )
        assert created.status_code == 201, created.text
        project_id = created.json()["project_id"]

        refused = client.patch(
            f"/api/v1/projects/{project_id}", headers=owner, json={"name": None}
        )
        assert refused.status_code == 422, refused.text
        assert refused.json()["error"]["code"] == "validation_error"

        cleared = client.patch(
            f"/api/v1/projects/{project_id}", headers=owner, json={"description": None}
        )
        assert cleared.status_code == 200, cleared.text
        assert cleared.json()["description"] is None
        assert cleared.json()["name"] == "Housing"


def test_task_can_belong_to_many_projects(tmp_path: Path) -> None:
    """One task in two tasks counts in both task_counts and lists both ids."""
    with api_client(tmp_path) as (client, owner, _):
        first = client.post("/api/v1/projects", headers=owner, json={"name": "First"}).json()[
            "project_id"
        ]
        second = client.post("/api/v1/projects", headers=owner, json={"name": "Second"}).json()[
            "project_id"
        ]
        task_id = create_task(client, owner)
        patched = client.patch(
            f"/api/v1/tasks/{task_id}",
            headers=owner,
            json={"project_ids": [first, second, first]},
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["project_ids"] == [first, second]

        listed = client.get("/api/v1/projects", headers=owner)
        counts = {row["project_id"]: row["task_count"] for row in listed.json()["data"]}
        assert counts[first] == 1
        assert counts[second] == 1


def test_omitting_project_ids_leaves_membership_unchanged(tmp_path: Path) -> None:
    """A name-only PATCH does not drop existing memberships."""
    with api_client(tmp_path) as (client, owner, _):
        project_id = client.post(
            "/api/v1/projects", headers=owner, json={"name": "Housing"}
        ).json()["project_id"]
        task_id = create_task(client, owner)
        assigned = client.patch(
            f"/api/v1/tasks/{task_id}",
            headers=owner,
            json={"project_ids": [project_id]},
        )
        assert assigned.status_code == 200, assigned.text

        renamed = client.patch(
            f"/api/v1/tasks/{task_id}",
            headers=owner,
            json={"name": "Renamed only"},
        )
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()["name"] == "Renamed only"
        assert renamed.json()["project_ids"] == [project_id]


def test_an_archived_project_leaves_the_default_list_and_archives_its_solo_tasks(
    tmp_path: Path, engine: Engine
) -> None:
    """Task 058, round 11: archive hides a project by default. Round 14 (owner):
    its tasks in no other project are archived with it; one also in another
    project stays; each archived task's History says so."""
    with api_client(tmp_path) as (client, owner, other):
        kept = client.post("/api/v1/projects", headers=owner, json={"name": "Kept"}).json()
        gone = client.post("/api/v1/projects", headers=owner, json={"name": "Gone"}).json()
        assert gone["archived_at"] is None
        solo = create_task(client, owner)
        shared = create_task(client, owner)
        for task_id, project_ids in (
            (solo, [gone["project_id"]]),
            (shared, [gone["project_id"], kept["project_id"]]),
        ):
            patched = client.patch(
                f"/api/v1/tasks/{task_id}", headers=owner, json={"project_ids": project_ids}
            )
            assert patched.status_code == 200, patched.text
        # The confirm sentence's count, before archiving.
        before = client.get(f"/api/v1/projects/{gone['project_id']}", headers=owner).json()
        assert (before["task_count"], before["solo_task_count"]) == (2, 1)

        archived = client.post(f"/api/v1/projects/{gone['project_id']}/archive", headers=owner)
        assert archived.status_code == 200, archived.text
        stamp = archived.json()["archived_at"]
        assert stamp is not None
        assert archived.json()["archived_task_count"] == 1
        assert archived.json()["task_count"] == 1
        # Again: nothing changes, the first time stands, nothing more archived.
        again = client.post(f"/api/v1/projects/{gone['project_id']}/archive", headers=owner)
        assert again.status_code == 200 and again.json()["archived_at"] == stamp
        assert again.json()["archived_task_count"] == 0

        def names(status: str | None) -> list[str]:
            params = {} if status is None else {"status": status}
            listed = client.get("/api/v1/projects", headers=owner, params=params)
            assert listed.status_code == 200, listed.text
            return sorted(row["name"] for row in listed.json()["data"])

        assert names(None) == ["Kept"]
        assert names("active") == ["Kept"]
        assert names("archived") == ["Gone"]
        assert names("all") == ["Gone", "Kept"]
        assert kept["archived_at"] is None

        # Still readable by id; the solo task is archived and keeps its
        # membership, the shared one is untouched.
        assert client.get(f"/api/v1/projects/{gone['project_id']}", headers=owner).json()[
            "archived_at"
        ] == stamp
        archived_tasks = client.get(
            "/api/v1/tasks", headers=owner, params={"status": "archived"}
        ).json()["data"]
        [solo_read] = [row for row in archived_tasks if row["task_id"] == solo]
        assert solo_read["status"] == "archived"
        assert solo_read["project_ids"] == [gone["project_id"]]
        assert client.get(f"/api/v1/tasks/{shared}", headers=owner).json()["status"] == "active"
        # The task's History records it, naming the project.
        with engine.connect() as conn:
            [archive_event] = [
                entry["payload"]
                for entry in events.read(conn, uuid.UUID(solo))
                if entry["event_type"] == "task.archived"
            ]
        assert archive_event["project_id"] == gone["project_id"]
        assert archive_event["project_name"] == "Gone"
        assert (
            history.lifecycle_sentence("archived", archive_event, history.SYSTEM)
            == "Policy Atlas archived the project “Gone”, and this task with it."
        )

        # Someone who cannot read it gets the opaque 404 and changes nothing.
        refused = client.post(f"/api/v1/projects/{kept['project_id']}/archive", headers=other)
        assert refused.status_code == 404
        assert names(None) == ["Kept"]


def test_the_list_pages_by_last_activity_newest_first(tmp_path: Path) -> None:
    """Task 058, round 12: a project with recent task activity is on the first
    page even when it was created first; ``last_activity_at`` says why."""
    with api_client(tmp_path) as (client, owner, _):
        made = [
            client.post("/api/v1/projects", headers=owner, json={"name": name}).json()
            for name in ("Oldest", "Middle", "Newest")
        ]
        oldest, middle, newest = (project["project_id"] for project in made)
        task_id = create_task(client, owner)
        patched = client.patch(
            f"/api/v1/tasks/{task_id}", headers=owner, json={"project_ids": [oldest]}
        )
        assert patched.status_code == 200, patched.text
        task_updated = client.get(f"/api/v1/tasks/{task_id}", headers=owner).json()["updated_at"]

        first = client.get("/api/v1/projects?page_size=2", headers=owner).json()
        assert [row["project_id"] for row in first["data"]] == [oldest, newest]
        assert first["pagination"]["has_more"] is True
        second = client.get("/api/v1/projects?page_size=2&page=2", headers=owner).json()
        assert [row["project_id"] for row in second["data"]] == [middle]

        rows = {row["project_id"]: row for row in first["data"] + second["data"]}
        assert rows[oldest]["last_activity_at"] == task_updated
        assert rows[newest]["last_activity_at"] == rows[newest]["created_at"]
        single = client.get(f"/api/v1/projects/{oldest}", headers=owner).json()
        assert single["last_activity_at"] == task_updated


def test_archiving_a_project_leaves_a_task_that_is_mid_run(
    tmp_path: Path, engine: Engine
) -> None:
    """Task 058 review: as the single-task archive refuses ``run_active``, the
    project archive leaves a solo task whose latest walk is running."""
    with api_client(tmp_path) as (client, owner, _other):
        gone = client.post("/api/v1/projects", headers=owner, json={"name": "Gone"}).json()
        busy = create_task(client, owner)
        patched = client.patch(
            f"/api/v1/tasks/{busy}", headers=owner, json={"project_ids": [gone["project_id"]]}
        )
        assert patched.status_code == 200, patched.text
        with engine.begin() as conn:
            seed_walk(conn, uuid.UUID(busy), capability="evidence_search", status="running")

        archived = client.post(f"/api/v1/projects/{gone['project_id']}/archive", headers=owner)

        assert archived.status_code == 200, archived.text
        assert archived.json()["archived_at"] is not None
        assert archived.json()["archived_task_count"] == 0
        assert client.get(f"/api/v1/tasks/{busy}", headers=owner).json()["status"] == "active"
