"""Conditionally-public Task read access (task 037, Phase 2)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.engine import Engine
from structlog.testing import capture_logs

from policy_atlas.core.schema import task
from tests.api.org_support import make_org, make_task, ops_enrol, seeded, tenancy_client
from tests.api.resource_support import api_client, create_task


def _share(client: TestClient, task_id: str, owner: dict[str, str]) -> None:
    """Turn on public sharing through the owner-only HTTP surface."""
    response = client.patch(
        f"/api/v1/tasks/{task_id}", headers=owner, json={"is_public": True}
    )
    assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    "headers",
    [None, {"Authorization": "Bearer garbage"}, {"Authorization": "Basic eA=="},
     {"Authorization": "Bearer"}, {"Authorization": "Token x"}],
    ids=["absent", "garbage-bearer", "basic", "bare-bearer", "wrong-scheme"],
)
# Two routes because they live on two routers: the bare task read sits on
# the tokenless `public_read_router`, funnel on the read-models router.
@pytest.mark.parametrize("suffix", ["", "/funnel"], ids=["task", "funnel"])
def test_optional_auth_uses_the_raw_authorization_header(
    tmp_path: Path, suffix: str, headers: dict[str, str] | None
) -> None:
    """Only a missing header is anonymous; every malformed present one is 401."""
    with api_client(tmp_path) as (client, owner, _other):
        task_id = create_task(client, owner)
        _share(client, task_id, owner)

        response = client.get(f"/api/v1/tasks/{task_id}{suffix}", headers=headers)
        assert response.status_code == (200 if headers is None else 401), response.text


def test_unsharing_revokes_anonymous_access_with_the_standard_404(tmp_path: Path) -> None:
    """A public flag flip is checked on the next anonymous request."""
    with api_client(tmp_path) as (client, owner, _other):
        task_id = create_task(client, owner)
        _share(client, task_id, owner)
        assert client.get(f"/api/v1/tasks/{task_id}/funnel").status_code == 200

        revoked = client.patch(
            f"/api/v1/tasks/{task_id}", headers=owner, json={"is_public": False}
        )
        assert revoked.status_code == 200, revoked.text
        denied = client.get(f"/api/v1/tasks/{task_id}/funnel")
        unknown = client.get(f"/api/v1/tasks/{uuid.uuid4()}/funnel")
        assert denied.status_code == unknown.status_code == 404
        assert denied.content == unknown.content


def test_archiving_a_public_task_revokes_all_anonymous_reads(tmp_path: Path) -> None:
    """Public access is limited to rows whose status remains active."""
    with api_client(tmp_path) as (client, owner, _other):
        task_id = create_task(client, owner)
        _share(client, task_id, owner)
        archived = client.post(f"/api/v1/tasks/{task_id}/archive", headers=owner)
        assert archived.status_code == 200, archived.text

        unknown = client.get(f"/api/v1/tasks/{uuid.uuid4()}")
        for path in (f"/api/v1/tasks/{task_id}", f"/api/v1/tasks/{task_id}/funnel"):
            denied = client.get(path)
            assert denied.status_code == 404, path
            # Archived is byte-identical to unknown (rubric 9).
            assert denied.content == unknown.content, path


def test_public_task_response_is_redacted_for_anonymous_and_outside_users(
    tmp_path: Path,
) -> None:
    """Public-leg task reads remove owner and membership details for every outsider."""
    with api_client(tmp_path) as (client, owner, other):
        task_id = create_task(client, owner)
        _share(client, task_id, owner)

        anonymous = client.get(f"/api/v1/tasks/{task_id}")
        assert anonymous.status_code == 200, anonymous.text
        outsider = client.get(f"/api/v1/tasks/{task_id}", headers=other)
        assert outsider.status_code == 200, outsider.text
        for body in (anonymous.json(), outsider.json()):
            assert body["access"] == "public"
            assert body["is_owner"] is False
            assert body["owner_display"] is None
            assert body["project_ids"] == []

        owner_read = client.get(f"/api/v1/tasks/{task_id}", headers=owner)
        assert owner_read.status_code == 200
        assert owner_read.json()["access"] == "full"
        assert client.get(f"/api/v1/tasks/{task_id}/funnel", headers=other).status_code == 200


def test_public_tasks_do_not_widen_listings(tmp_path: Path) -> None:
    """A direct public link does not create a public index or listing entry."""
    with api_client(tmp_path) as (client, owner, other):
        task_id = create_task(client, owner)
        _share(client, task_id, owner)

        listed = client.get("/api/v1/tasks", headers=other)
        assert listed.status_code == 200, listed.text
        assert task_id not in {row["task_id"] for row in listed.json()["data"]}


def test_admin_read_of_a_public_task_keeps_the_graded_leg_and_trace(
    engine: Engine, tmp_path: Path
) -> None:
    """The graded legs win before the public leg (contract D4).

    An entitled admin keeps today's full read — and its audit trace — even
    when the row happens to be public. Review-stack ruling on the 037 build's
    leg order, which served admins the redacted public shape.
    """
    with tenancy_client(tmp_path, count=2) as (client, (owner, admin)):
        with seeded(engine) as conn:
            owner_org = make_org(conn, name="Owner Org")
            admin_org = make_org(conn, name="Admin Org")
            ops_enrol(conn, user_id=owner.user_id, org_id=owner_org, display_name="Owner")
            ops_enrol(
                conn, user_id=admin.user_id, org_id=admin_org, display_name="Admin", is_admin=True
            )
            task_id = make_task(
                conn, owner_user_id=owner.user_id, org_id=owner_org, visibility="private"
            )
            conn.execute(
                update(task).where(task.c.task_id == task_id).values(is_public=True)
            )

        with capture_logs() as captured:
            response = client.get(f"/api/v1/tasks/{task_id}", headers=admin.headers)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["access"] == "full"
        assert body["is_owner"] is False
        assert [line for line in captured if line.get("event") == "admin_read"]


def test_decisions_stay_hidden_from_a_signed_in_outsider_on_a_public_task(
    tmp_path: Path,
) -> None:
    """`decisions` is outside the public surface for every non-graded caller.

    Review-stack regression pin: the built public leg briefly covered
    `decisions` for signed-in callers. A signed-in outsider must get the
    byte-identical 404 on a public row, exactly as on a private or unknown one.
    """
    with api_client(tmp_path) as (client, owner, other):
        task_id = create_task(client, owner)
        _share(client, task_id, owner)

        denied = client.get(f"/api/v1/tasks/{task_id}/decisions", headers=other)
        unknown = client.get(f"/api/v1/tasks/{uuid.uuid4()}/decisions", headers=other)
        assert denied.status_code == unknown.status_code == 404
        assert denied.content == unknown.content


def test_only_the_owner_may_flip_is_public(engine: Engine, tmp_path: Path) -> None:
    """A same-org colleague's `PATCH {is_public}` is 403, not a silent flip (R1)."""
    with tenancy_client(tmp_path, count=2) as (client, (owner, colleague)):
        with seeded(engine) as conn:
            org = make_org(conn, name="Shared Org")
            ops_enrol(conn, user_id=owner.user_id, org_id=org, display_name="Owner")
            ops_enrol(conn, user_id=colleague.user_id, org_id=org, display_name="Colleague")
            task_id = make_task(
                conn, owner_user_id=owner.user_id, org_id=org, visibility="org"
            )

        response = client.patch(
            f"/api/v1/tasks/{task_id}",
            headers=colleague.headers,
            json={"is_public": True},
        )
        assert response.status_code == 403, response.text
