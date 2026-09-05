"""HTTP coverage for check-in ownership and empty durable-history projection."""

from __future__ import annotations

import uuid
from pathlib import Path

import jwt
from sqlalchemy import update
from sqlalchemy.engine import Engine

from policy_atlas.core.schema import capability_run, task
from tests.api.resource_support import api_client, create_task
from tests.api.test_continuation_protocol import _park_walk
from tests.runtime.test_runner import _cleanup


def test_check_ins_are_owner_scoped_and_empty_before_a_walk_parks(tmp_path: Path) -> None:
    """Expose no transport-memory check-ins for a task with no parked run."""
    with api_client(tmp_path) as (client, owner, other):
        task_id = create_task(client, owner)
        pending = client.get(f"/api/v1/tasks/{task_id}/check-ins", headers=owner)
        assert pending.status_code == 200
        assert pending.json()["data"] == []

        absent = client.get(f"/api/v1/tasks/{uuid.uuid4()}/check-ins", headers=other)
        cross_owner = client.get(f"/api/v1/tasks/{task_id}/check-ins", headers=other)
        assert absent.status_code == cross_owner.status_code == 404
        assert absent.json() == cross_owner.json()


def test_pending_requires_parked_walk_never_a_phantom_card(
    engine: Engine, tmp_path: Path
) -> None:
    """A pause on a walk the sweep marked `interrupted` is never rendered pending.

    A death between the pause event's emission and the walk's durable park
    (the runner writes the pause event, then persists the row as `paused`)
    leaves an undecided `steering.pause` event whose walk the startup sweep
    later marks `interrupted`. Rendering that pause as pending offers the user
    a card whose answer always 404s, because the answer path's pending-pause
    lookup has required `paused` status all along (fix pinned 2026-07-21:
    `pending` requires the latest walk to actually be `paused`). The durable
    `all` history must still carry the pause.
    """
    task_id: uuid.UUID | None = None
    try:
        with api_client(tmp_path) as (client, owner, _other):
            owner_sub = jwt.decode(
                owner["Authorization"].split(" ", 1)[1], options={"verify_signature": False}
            )["sub"]
            task_id, _scope_id, capability_run_id, _check_in_id = _park_walk(engine)
            with engine.begin() as conn:
                conn.execute(
                    update(task)
                    .where(task.c.task_id == task_id)
                    .values(owner_user_id=owner_sub)
                )
            # Simulate the sweep having classified this walk as interrupted
            # (death between pause-emit and park) without touching the
            # already-durable pause event.
            with engine.begin() as conn:
                conn.execute(
                    update(capability_run)
                    .where(capability_run.c.capability_run_id == capability_run_id)
                    .values(status="interrupted")
                )

            pending = client.get(
                f"/api/v1/tasks/{task_id}/check-ins", headers=owner
            )
            assert pending.status_code == 200
            assert pending.json()["data"] == []

            history = client.get(
                f"/api/v1/tasks/{task_id}/check-ins?status=all", headers=owner
            )
            assert history.status_code == 200
            assert len(history.json()["data"]) == 1
    finally:
        _cleanup(engine, task_id)
