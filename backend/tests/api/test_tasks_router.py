"""HTTP coverage for owner-scoped task lifecycle routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import Engine

from policy_atlas.core.schema import capability_run, evidence_scope
from tests.api.resource_support import api_client, create_task
from tests.helpers import seed_run, seed_screening_result, seed_source


def test_tasks_create_list_get_archive_and_owner_404(engine: Engine, tmp_path: Path) -> None:
    """Exercise lifecycle reads, pagination, archive idempotence, and BOLA opacity."""
    with api_client(tmp_path) as (client, owner, other):
        task_id = create_task(client, owner)
        listed = client.get("/api/v1/tasks?page=1&page_size=1", headers=owner)
        assert listed.status_code == 200
        assert listed.json()["pagination"] == {"page": 1, "page_size": 1, "total_items": 1}
        assert listed.json()["data"][0]["task_id"] == task_id
        assert client.get(f"/api/v1/tasks/{task_id}", headers=owner).status_code == 200

        renamed = client.patch(
            f"/api/v1/tasks/{task_id}", headers=owner, json={"name": "Renamed"}
        )
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "Renamed"

        absent = client.get(f"/api/v1/tasks/{uuid.uuid4()}", headers=other)
        cross_owner = client.get(f"/api/v1/tasks/{task_id}", headers=other)
        assert cross_owner.status_code == absent.status_code == 404
        assert cross_owner.json() == absent.json()
        # Task 037: GET /tasks/{id} is conditionally public — a tokenless
        # read of a non-public row gets the same indistinguishable 404 as an
        # unknown id, never a 401 that would disclose the row exists.
        anonymous = client.get(f"/api/v1/tasks/{task_id}")
        assert anonymous.status_code == 404
        assert anonymous.json() == absent.json()

        assert (
            client.post(f"/api/v1/tasks/{task_id}/archive", headers=owner).status_code
            == 200
        )
        assert (
            client.post(f"/api/v1/tasks/{task_id}/archive", headers=owner).status_code
            == 200
        )
        assert client.get("/api/v1/tasks", headers=owner).json()["data"] == []
        assert client.get("/api/v1/tasks?status=archived", headers=owner).status_code == 200


def test_tasks_reject_page_sizes_over_contract_cap(engine: Engine, tmp_path: Path) -> None:
    """Keep the server pagination cap at the documented contract boundary."""
    with api_client(tmp_path) as (client, owner, _):
        response = client.get("/api/v1/tasks?page_size=201", headers=owner)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"


def test_task_with_no_run_reports_source_count_as_none(engine: Engine, tmp_path: Path) -> None:
    """No capability_run at all: `source_count` is `None`, not `0` — the question is unasked."""
    with api_client(tmp_path) as (client, owner, _other):
        task_id = create_task(client, owner)

        detail = client.get(f"/api/v1/tasks/{task_id}", headers=owner)
        assert detail.status_code == 200
        assert detail.json()["source_count"] is None

        listed = client.get("/api/v1/tasks", headers=owner)
        assert listed.status_code == 200
        assert listed.json()["data"][0]["source_count"] is None


def test_task_with_a_run_reports_source_count_as_included_screens(
    engine: Engine, tmp_path: Path
) -> None:
    """A capability_run makes `source_count` real: Included screens, not snapshots."""
    with api_client(tmp_path) as (client, owner, _other):
        task_id = create_task(client, owner)
        pid = uuid.UUID(task_id)
        with engine.begin() as conn:
            scope_id = uuid.uuid4()
            conn.execute(
                evidence_scope.insert().values(
                    evidence_scope_id=scope_id,
                    task_id=pid,
                    intent="source count coverage",
                    context={},
                    created_at=datetime.now(UTC),
                )
            )
            conn.execute(
                capability_run.insert().values(
                    capability_run_id=uuid.uuid4(),
                    task_id=pid,
                    evidence_scope_id=scope_id,
                    capability="evidence_search",
                    plan_id=uuid.uuid4(),
                    plan_version=1,
                    status="succeeded",
                    session_id=None,
                    started_at=datetime.now(UTC),
                    ended_at=datetime.now(UTC),
                )
            )
            run_id = seed_run(conn, pid)

        zero_included = client.get(f"/api/v1/tasks/{task_id}", headers=owner)
        assert zero_included.status_code == 200
        assert zero_included.json()["source_count"] == 0

        with engine.begin() as conn:
            _, included_a = seed_source(conn, pid)
            _, included_b = seed_source(conn, pid)
            _, excluded = seed_source(conn, pid)
            seed_screening_result(conn, pid, run_id, scope_id, included_a, status="relevant")
            seed_screening_result(conn, pid, run_id, scope_id, included_b, status="relevant")
            seed_screening_result(conn, pid, run_id, scope_id, excluded, status="not_relevant")

        two_included = client.get(f"/api/v1/tasks/{task_id}", headers=owner)
        assert two_included.status_code == 200
        assert two_included.json()["source_count"] == 2

        listed = client.get("/api/v1/tasks", headers=owner)
        assert listed.status_code == 200
        assert listed.json()["data"][0]["source_count"] == 2


def test_a_patch_body_of_explicit_nulls_is_refused_rather_than_written(
    tmp_path: Path,
) -> None:
    """A malformed body is the caller's error, not an internal one.

    Both fields back NOT NULL columns and the route dumps with
    `exclude_unset`, so an explicit null was *in* the changes: `visibility`
    went to the UPDATE and `name` went to `rename_task`, and each request
    ended as **500 internal** on a constraint violation. `visibility` needed a
    task with no project to get that far — with one it is refused 409
    first (i.5), which is why the crash was reachable only on the plainer row.

    The row is unchanged afterwards, which is the half that says the refusal
    happened before the write rather than in the middle of it.
    """
    with api_client(tmp_path) as (client, owner, _):
        task_id = create_task(client, owner)

        for body in ({"visibility": None}, {"name": None}):
            response = client.patch(
                f"/api/v1/tasks/{task_id}", headers=owner, json=body
            )
            assert response.status_code == 422, (body, response.text)
            assert response.json()["error"]["code"] == "validation_error"

        # `question: null` is not the same thing — the column is nullable, so
        # clearing the question is a real instruction and still works.
        cleared = client.patch(
            f"/api/v1/tasks/{task_id}", headers=owner, json={"question": None}
        )
        assert cleared.status_code == 200
        assert cleared.json()["question"] is None
        # untouched: the column default ('private', owner amendment 2026-08-26)
        assert cleared.json()["visibility"] == "private"
        assert cleared.json()["name"] == "Test task"


def test_rename_and_membership_while_run_is_active_leave_the_run_running(
    engine: Engine, tmp_path: Path
) -> None:
    """PATCH name and project_ids during a running walk return 200 and stay running."""
    with api_client(tmp_path) as (client, owner, _):
        task_id = create_task(client, owner)
        pid = uuid.UUID(task_id)
        housing = client.post("/api/v1/projects", headers=owner, json={"name": "Housing"})
        project_id = housing.json()["project_id"]
        with engine.begin() as conn:
            scope_id = uuid.uuid4()
            conn.execute(
                evidence_scope.insert().values(
                    evidence_scope_id=scope_id,
                    task_id=pid,
                    intent="running walk lock",
                    context={},
                    created_at=datetime.now(UTC),
                )
            )
            conn.execute(
                capability_run.insert().values(
                    capability_run_id=uuid.uuid4(),
                    task_id=pid,
                    evidence_scope_id=scope_id,
                    capability="evidence_search",
                    plan_id=uuid.uuid4(),
                    plan_version=1,
                    status="running",
                    session_id=None,
                    started_at=datetime.now(UTC),
                    ended_at=None,
                )
            )

        renamed = client.patch(
            f"/api/v1/tasks/{task_id}",
            headers=owner,
            json={"name": "Still walking"},
        )
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()["name"] == "Still walking"
        assert renamed.json()["latest_run"]["status"] == "running"

        assigned = client.patch(
            f"/api/v1/tasks/{task_id}",
            headers=owner,
            json={"project_ids": [project_id]},
        )
        assert assigned.status_code == 200, assigned.text
        assert assigned.json()["project_ids"] == [project_id]
        assert assigned.json()["latest_run"]["status"] == "running"

        fetched = client.get(f"/api/v1/tasks/{task_id}", headers=owner)
        assert fetched.status_code == 200
        assert fetched.json()["latest_run"]["status"] == "running"
