"""`POST /tasks` with a capability, projects and Links, in one transaction.

Task 044 (C10, C11, C12, ADR 0037 decision 2). The three properties worth
owning at the HTTP level, because none of them can be seen from the database
alone:

- **Atomicity.** A refused Link leaves no task row behind. That is the whole
  reason create stopped being create-then-patch: a scoping task linked to
  nothing has lost the thing it was created for.
- **A Link grants nothing.** Someone who cannot read either task gets the same
  404 the tasks route already gives, and someone who cannot read the *source*
  cannot conjure a reference to it by naming it in a create.
- **Flagged, not broken.** When the two tasks stop sharing a project the link
  row stays and reads ``flagged: true``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.core.schema import (
    capability_run,
    evidence_scope,
    project,
    project_membership,
    task,
    task_link,
    task_plan,
)
from tests.api.org_support import make_org, ops_enrol, seeded, tenancy_client
from tests.helpers import delete_task_data


@pytest.fixture(autouse=True)
def _remove_committed_tasks(engine: Engine):  # type: ignore[no-untyped-def]
    """Hard-delete every task these tests commit, links and memberships first.

    These tests drive real routes, so they commit; the rolled-back ``conn``
    fixture cannot clean up after them. Leaving the rows behind is not merely
    untidy here — an ``options_scoping`` task committed by one test makes
    ``b5e1d7a4c026``'s downgrade **refuse**, which is exactly what it is
    supposed to do, and every historical migration round-trip in the suite
    fails behind it.
    """
    before = _all_task_ids(engine)
    yield
    created = list(_all_task_ids(engine) - before)
    with engine.begin() as conn:
        # Every link across the whole batch first: a link pins the SOURCE
        # task's walk, so deleting the source's rows while the target's link
        # still names them is a foreign-key violation.
        conn.execute(task_link.delete().where(task_link.c.source_task_id.in_(created)))
        conn.execute(task_link.delete().where(task_link.c.target_task_id.in_(created)))
        for task_id in created:
            conn.execute(
                project_membership.delete().where(project_membership.c.task_id == task_id)
            )
            delete_task_data(conn, task_id)


def _all_task_ids(engine: Engine) -> set[uuid.UUID]:
    with engine.connect() as conn:
        return {row[0] for row in conn.execute(select(task.c.task_id))}


def _make_project(conn: Connection, *, org_id: uuid.UUID, owner_user_id: str) -> uuid.UUID:
    project_id = uuid.uuid4()
    conn.execute(
        project.insert().values(
            project_id=project_id,
            name=f"Project {uuid.uuid4()}",
            description=None,
            created_at=datetime.now(UTC),
            owner_user_id=owner_user_id,
            org_id=org_id,
            visibility="org",
        )
    )
    return project_id


def _finish_walk(conn: Connection, task_id: uuid.UUID, *, status: str = "succeeded") -> uuid.UUID:
    """Give a task one walk in ``status``; return its ``capability_run_id``."""
    now = datetime.now(UTC)
    scope_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    run_id = uuid.uuid4()
    conn.execute(
        evidence_scope.insert().values(
            evidence_scope_id=scope_id,
            task_id=task_id,
            intent="es",
            context={},
            created_at=now,
        )
    )
    conn.execute(
        task_plan.insert().values(
            plan_id=plan_id,
            task_id=task_id,
            version=1,
            status="approved",
            payload={},
            created_at=now,
            created_by="user",
        )
    )
    conn.execute(
        capability_run.insert().values(
            capability_run_id=run_id,
            task_id=task_id,
            evidence_scope_id=scope_id,
            capability="evidence_search",
            plan_id=plan_id,
            plan_version=1,
            status=status,
            started_at=now,
            ended_at=now if status not in ("running", "paused") else None,
        )
    )
    return run_id


def _create(
    client: TestClient,
    headers: dict[str, str],
    **body: object,
) -> httpx.Response:
    payload: dict[str, object] = {"name": "A task", "question": "What works?"}
    payload.update(body)
    response: httpx.Response = client.post(
        "/api/v1/tasks", headers=headers, json=payload
    )
    return response


def _task_count(engine: Engine, name: str) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                select(func.count()).select_from(task).where(task.c.name == name)
            ).scalar_one()
        )


def test_a_scoping_task_is_created_with_its_capability_project_and_link(
    engine: Engine, tmp_path: Path
) -> None:
    with tenancy_client(tmp_path, count=1) as (client, [owner]):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id)
            project_id = _make_project(conn, org_id=org_id, owner_user_id=owner.user_id)
        source = _create(client, owner.headers, name="Source", project_ids=[str(project_id)])
        assert source.status_code == 201, source.text
        source_id = source.json()["task_id"]
        assert source.json()["capability"] == "evidence_search"
        with seeded(engine) as conn:
            run_id = _finish_walk(conn, uuid.UUID(source_id))

        created = _create(
            client,
            owner.headers,
            name="Scoping",
            capability="options_scoping",
            project_ids=[str(project_id)],
            from_task_ids=[source_id],
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["capability"] == "options_scoping"
        assert body["project_ids"] == [str(project_id)]
        assert body["from_task_ids"] == [source_id]
        assert body["links"] == [
            {
                "link_id": body["links"][0]["link_id"],
                "source_task_id": source_id,
                "source_task_name": "Source",
                "source_capability_run_id": str(run_id),
                "flagged": False,
            }
        ]
        # And the read route says the same thing.
        read = client.get(f"/api/v1/tasks/{body['task_id']}", headers=owner.headers)
        assert read.json()["links"] == body["links"]


def test_an_evidence_search_create_refuses_to_start_from_another_task(
    engine: Engine, tmp_path: Path
) -> None:
    """Links are for scoping tasks in this slice; the reverse lands with task 5."""
    with tenancy_client(tmp_path, count=1) as (client, [owner]):
        refused = _create(
            client, owner.headers, name="ES with a link", from_task_ids=[str(uuid.uuid4())]
        )
        # The envelope reports the location, not the model's sentence — the
        # 422 handler deliberately does not echo validator text back.
        assert refused.status_code == 422
        assert refused.json()["error"]["code"] == "validation_error"
        assert _task_count(engine, "ES with a link") == 0


def test_a_link_to_a_source_in_no_shared_project_is_refused_and_no_task_survives(
    engine: Engine, tmp_path: Path
) -> None:
    """C10 atomicity: the refusal rolls the whole create back."""
    with tenancy_client(tmp_path, count=1) as (client, [owner]):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id)
            one = _make_project(conn, org_id=org_id, owner_user_id=owner.user_id)
            two = _make_project(conn, org_id=org_id, owner_user_id=owner.user_id)
        source = _create(client, owner.headers, name="Elsewhere", project_ids=[str(one)])
        source_id = source.json()["task_id"]
        with seeded(engine) as conn:
            _finish_walk(conn, uuid.UUID(source_id))

        refused = _create(
            client,
            owner.headers,
            name="Orphan scoping",
            capability="options_scoping",
            project_ids=[str(two)],
            from_task_ids=[source_id],
        )
        assert refused.status_code == 409
        assert refused.json()["error"]["code"] == "link_project_mismatch"
        assert _task_count(engine, "Orphan scoping") == 0


def test_a_link_to_a_source_with_no_finished_walk_is_refused(
    engine: Engine, tmp_path: Path
) -> None:
    """C11: only a ``succeeded`` or ``degraded`` walk can be pinned."""
    with tenancy_client(tmp_path, count=1) as (client, [owner]):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id)
            project_id = _make_project(conn, org_id=org_id, owner_user_id=owner.user_id)
        source = _create(client, owner.headers, name="Unrun", project_ids=[str(project_id)])
        source_id = source.json()["task_id"]

        # No walk at all.
        refused = _create(
            client,
            owner.headers,
            name="Too early",
            capability="options_scoping",
            project_ids=[str(project_id)],
            from_task_ids=[source_id],
        )
        assert refused.status_code == 409
        assert refused.json()["error"]["code"] == "link_source_unfinished"
        assert _task_count(engine, "Too early") == 0

        # A walk that is still running is no better.
        with seeded(engine) as conn:
            _finish_walk(conn, uuid.UUID(source_id), status="running")
        still_refused = _create(
            client,
            owner.headers,
            name="Too early",
            capability="options_scoping",
            project_ids=[str(project_id)],
            from_task_ids=[source_id],
        )
        assert still_refused.json()["error"]["code"] == "link_source_unfinished"

        # A degraded walk is finished enough (C11).
        with seeded(engine) as conn:
            conn.execute(
                capability_run.update()
                .where(capability_run.c.task_id == uuid.UUID(source_id))
                .values(status="degraded")
            )
        accepted = _create(
            client,
            owner.headers,
            name="Late enough",
            capability="options_scoping",
            project_ids=[str(project_id)],
            from_task_ids=[source_id],
        )
        assert accepted.status_code == 201, accepted.text


def test_a_link_never_widens_what_the_caller_can_read(
    engine: Engine, tmp_path: Path
) -> None:
    """ADR 0033 style: naming an unreadable source is the ordinary 404."""
    with tenancy_client(tmp_path, count=2) as (client, principals):
        owner, stranger = principals
        with seeded(engine) as conn:
            owner_org = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=owner_org)
            ops_enrol(conn, user_id=stranger.user_id, org_id=make_org(conn))
            project_id = _make_project(conn, org_id=owner_org, owner_user_id=owner.user_id)
        source = _create(
            client, owner.headers, name="Private source", project_ids=[str(project_id)]
        )
        source_id = source.json()["task_id"]
        with seeded(engine) as conn:
            _finish_walk(conn, uuid.UUID(source_id))

        # The baseline the refusal must be indistinguishable from.
        absent = client.get(f"/api/v1/tasks/{uuid.uuid4()}", headers=stranger.headers)
        direct = client.get(f"/api/v1/tasks/{source_id}", headers=stranger.headers)
        assert direct.status_code == absent.status_code == 404
        assert direct.json() == absent.json()

        refused = _create(
            client,
            stranger.headers,
            name="Borrowed",
            capability="options_scoping",
            from_task_ids=[source_id],
        )
        assert refused.status_code == 404
        assert refused.json() == absent.json()
        assert _task_count(engine, "Borrowed") == 0


def test_a_link_whose_tasks_stop_sharing_a_project_is_flagged_not_deleted(
    engine: Engine, tmp_path: Path
) -> None:
    """C12: the inheritance already happened; the row says so, marked."""
    with tenancy_client(tmp_path, count=1) as (client, [owner]):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id)
            project_id = _make_project(conn, org_id=org_id, owner_user_id=owner.user_id)
        source = _create(
            client, owner.headers, name="Shared source", project_ids=[str(project_id)]
        )
        source_id = source.json()["task_id"]
        with seeded(engine) as conn:
            _finish_walk(conn, uuid.UUID(source_id))
        created = _create(
            client,
            owner.headers,
            name="Scoping",
            capability="options_scoping",
            project_ids=[str(project_id)],
            from_task_ids=[source_id],
        )
        target_id = created.json()["task_id"]
        assert created.json()["links"][0]["flagged"] is False

        # The source leaves the project they shared.
        moved = client.patch(
            f"/api/v1/tasks/{source_id}", headers=owner.headers, json={"project_ids": []}
        )
        assert moved.status_code == 200

        read = client.get(f"/api/v1/tasks/{target_id}", headers=owner.headers)
        links = read.json()["links"]
        assert len(links) == 1
        assert links[0]["flagged"] is True
        assert links[0]["source_task_id"] == source_id
        # Still one row, not zero.
        with engine.connect() as conn:
            assert (
                int(
                    conn.execute(
                        select(func.count())
                        .select_from(project_membership)
                        .where(project_membership.c.task_id == uuid.UUID(source_id))
                    ).scalar_one()
                )
                == 0
            )


def test_the_tasks_listing_carries_the_capability_and_the_links(
    engine: Engine, tmp_path: Path
) -> None:
    with tenancy_client(tmp_path, count=1) as (client, [owner]):
        with seeded(engine) as conn:
            org_id = make_org(conn)
            ops_enrol(conn, user_id=owner.user_id, org_id=org_id)
            project_id = _make_project(conn, org_id=org_id, owner_user_id=owner.user_id)
        source = _create(
            client, owner.headers, name="Listed source", project_ids=[str(project_id)]
        )
        source_id = source.json()["task_id"]
        with seeded(engine) as conn:
            _finish_walk(conn, uuid.UUID(source_id))
        _create(
            client,
            owner.headers,
            name="Listed scoping",
            capability="options_scoping",
            project_ids=[str(project_id)],
            from_task_ids=[source_id],
        )

        listed = client.get("/api/v1/tasks", headers=owner.headers)
        assert listed.status_code == 200
        rows = {row["name"]: row for row in listed.json()["data"]}
        assert rows["Listed source"]["capability"] == "evidence_search"
        assert rows["Listed source"]["links"] == []
        assert rows["Listed scoping"]["capability"] == "options_scoping"
        assert rows["Listed scoping"]["from_task_ids"] == [source_id]


def test_the_default_create_is_still_an_evidence_search_with_nothing_attached(
    tmp_path: Path,
) -> None:
    """Every pre-044 caller's body still means exactly what it meant."""
    with tenancy_client(tmp_path, count=1) as (client, [owner]):
        created = client.post(
            "/api/v1/tasks",
            headers=owner.headers,
            json={"name": "Plain", "question": "What works?"},
        )
        assert created.status_code == 201
        body = created.json()
        assert body["capability"] == "evidence_search"
        assert body["project_ids"] == []
        assert body["from_task_ids"] == []
        assert body["links"] == []
