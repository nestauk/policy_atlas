"""Owner-only `is_public` PATCH: 200/404/401/422, and its audit event (task 037)."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.engine import Engine

from policy_atlas.core import events
from tests.api.resource_support import api_client, create_task


def test_owner_flips_is_public_on_and_reads_it_back(tmp_path: Path) -> None:
    """Owner PATCH `{is_public: true}` returns the flag and `access: "full"`."""
    with api_client(tmp_path) as (client, owner, _other):
        task_id = create_task(client, owner)

        patched = client.patch(
            f"/api/v1/tasks/{task_id}", headers=owner, json={"is_public": True}
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["is_public"] is True
        assert patched.json()["access"] == "full"

        fetched = client.get(f"/api/v1/tasks/{task_id}", headers=owner)
        assert fetched.status_code == 200
        assert fetched.json()["is_public"] is True


def test_non_owner_patch_of_is_public_is_the_indistinguishable_404(tmp_path: Path) -> None:
    """A private row is unreadable to another user, so write grade resolves 404."""
    with api_client(tmp_path) as (client, owner, other):
        task_id = create_task(client, owner)

        response = client.patch(
            f"/api/v1/tasks/{task_id}", headers=other, json={"is_public": True}
        )
        assert response.status_code == 404, response.text


def test_anonymous_patch_of_is_public_is_401(tmp_path: Path) -> None:
    """No `Authorization` header at all is refused before any grade is resolved."""
    with api_client(tmp_path) as (client, owner, _other):
        task_id = create_task(client, owner)

        response = client.patch(f"/api/v1/tasks/{task_id}", json={"is_public": True})
        assert response.status_code == 401, response.text


def test_explicit_null_is_public_is_refused_422_not_500(tmp_path: Path) -> None:
    """`is_public` backs a NOT NULL column — explicit null is a caller error."""
    with api_client(tmp_path) as (client, owner, _other):
        task_id = create_task(client, owner)

        response = client.patch(
            f"/api/v1/tasks/{task_id}", headers=owner, json={"is_public": None}
        )
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "validation_error"


def test_flip_writes_one_audit_event_and_a_repeated_flip_writes_none(
    engine: Engine, tmp_path: Path
) -> None:
    """`task.shared_publicly` / `task.unshared` on a real flip, never on a no-op."""
    with api_client(tmp_path) as (client, owner, _other):
        task_id = create_task(client, owner)
        pid = uuid.UUID(task_id)

        on = client.patch(
            f"/api/v1/tasks/{task_id}", headers=owner, json={"is_public": True}
        )
        assert on.status_code == 200, on.text

        # A no-op PATCH (same value) writes neither the column nor the event.
        repeat = client.patch(
            f"/api/v1/tasks/{task_id}", headers=owner, json={"is_public": True}
        )
        assert repeat.status_code == 200, repeat.text

        off = client.patch(
            f"/api/v1/tasks/{task_id}", headers=owner, json={"is_public": False}
        )
        assert off.status_code == 200, off.text

        with engine.begin() as conn:
            event_types = [event["event_type"] for event in events.read(conn, pid)]
        assert event_types == ["task.shared_publicly", "task.unshared"]
