"""Shared dev-issuer client support for API resource-router tests."""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.app import create_app
from policy_atlas.api.dev_issuer import init, mint_token
from policy_atlas.api.settings import Settings
from policy_atlas.core.schema import (
    capability_run,
    option_membership,
    project_membership,
    task,
    task_link,
    task_source_snapshot,
)
from tests.helpers import delete_task_data, now

#: The scoping question the stub scoping Task Agent is driven with.
SCOPING_TASK_NAME = "Youth employment options"
SCOPING_TASK_QUESTION = "What could reduce the number of young people not in work?"


@contextmanager
def api_client(
    tmp_path: Path,
    overrides: dict[Callable[..., object], Callable[..., object]] | None = None,
) -> Iterator[tuple[TestClient, dict[str, str], dict[str, str]]]:
    """Yield an application client and bearer headers for two distinct users.

    Args:
        tmp_path: Per-test temporary directory for a development issuer key.

    Yields:
        Client plus owner and other-user authorization headers.
    """
    key_dir = tmp_path / "issuer"
    settings = Settings(
        "http://dev-issuer.local",
        "resource-router-test",
        None,
        init(key_dir),
        "http://app.example.test",
        os.environ["DATABASE_URL"],
    )
    # Unique subs per client: the test DB is shared across the suite, and
    # owner-scoped listings would otherwise see other tests' tasks.
    owner = mint_token(
        f"owner-{uuid.uuid4()}", settings.oidc_issuer, settings.oidc_client_id, 60, key_dir
    )
    other = mint_token(
        f"other-{uuid.uuid4()}", settings.oidc_issuer, settings.oidc_client_id, 60, key_dir
    )
    app = create_app(settings=settings)
    if overrides:
        app.dependency_overrides.update(overrides)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, {"Authorization": f"Bearer {owner}"}, {"Authorization": f"Bearer {other}"}


def create_task(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Test task",
    question: str = "What works?",
    capability: str | None = None,
) -> str:
    """Create one task through the route and return its public identity.

    ``capability`` absent leaves the route's default (an Evidence search).
    """
    body: dict[str, str] = {"name": name, "question": question}
    if capability is not None:
        body["capability"] = capability
    response = client.post("/api/v1/tasks", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return cast(str, response.json()["task_id"])


def create_scoping_task(client: TestClient, headers: dict[str, str]) -> str:
    """Create one options-scoping task on the stub conversation's question."""
    return create_task(
        client,
        headers,
        name=SCOPING_TASK_NAME,
        question=SCOPING_TASK_QUESTION,
        capability="options_scoping",
    )


def task_agent_turn(
    client: TestClient,
    headers: dict[str, str],
    task_id: uuid.UUID | str,
    message: str,
    *,
    client_turn_id: uuid.UUID | None = None,
) -> httpx.Response:
    """Post one Task Agent turn and return the raw response."""
    response = client.post(
        f"/api/v1/tasks/{task_id}/task-agent-turns",
        headers=headers,
        json={"message": message, "client_turn_id": str(client_turn_id or uuid.uuid4())},
    )
    return cast(httpx.Response, response)


def task_agent_turn_ok(
    client: TestClient, headers: dict[str, str], task_id: uuid.UUID | str, message: str
) -> dict[str, Any]:
    """Post one Task Agent turn, require a 200 and return its body."""
    response = task_agent_turn(client, headers, task_id, message)
    assert response.status_code == 200, response.text
    return dict(response.json())


def to_ready(
    client: TestClient,
    headers: dict[str, str],
    task_id: uuid.UUID | str,
    *,
    fresh: bool = True,
) -> dict[str, Any]:
    """Drive the stub scoping conversation to a ready plan in three turns.

    Args:
        fresh: The conversation starts here, so each turn's part (settings,
            then depth) is checked; pass ``False`` after earlier turns.

    Returns:
        The third turn's body, whose plan is ready.
    """
    first = task_agent_turn_ok(client, headers, task_id, "Young people are not getting into work.")
    second = task_agent_turn_ok(client, headers, task_id, "16 to 24 year olds")
    if fresh:
        assert first["scoping_plan"]["ready"] is False
        assert first["part"]["id"] == "settings"
        assert second["scoping_plan"]["ready"] is False
        assert second["part"]["id"] == "depth"
    ready = task_agent_turn_ok(
        client, headers, task_id, "[confirm part=depth option=standard_pass]"
    )
    assert ready["scoping_plan"]["ready"] is True
    return ready


# --- cleanup of committed tasks ---------------------------------------------------


def all_task_ids(engine: Engine) -> set[uuid.UUID]:
    """Every task id in the database."""
    with engine.connect() as conn:
        return {row[0] for row in conn.execute(select(task.c.task_id))}


def await_walks_ended(engine: Engine, task_ids: list[uuid.UUID]) -> None:
    """Let any walk a test opened (an option search, say) finish before its task is deleted."""
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            active = conn.execute(
                select(capability_run.c.capability_run_id)
                .where(capability_run.c.task_id.in_(task_ids))
                .where(capability_run.c.status.in_(("running", "paused")))
            ).first()
        if active is None:
            return
        time.sleep(0.1)


@pytest.fixture(autouse=True)
def remove_committed_tasks(engine: Engine) -> Iterator[None]:
    """Hard-delete every task the test commits. Autouse wherever it is imported.

    Route tests commit, so the rolled-back ``conn`` fixture cannot clean up
    after them. Leaving the rows behind is not merely untidy: an
    ``options_scoping`` task left behind makes the slice revisions' downgrades
    **refuse**, which is exactly what they are for, and every migration
    round-trip in the suite fails behind it.
    """
    before = all_task_ids(engine)
    yield
    delete_committed_tasks(engine, list(all_task_ids(engine) - before))


@pytest.fixture(autouse=True)
def remove_committed_tasks_after_walks(engine: Engine) -> Iterator[None]:
    """:func:`remove_committed_tasks`, once the walks the test started have ended.

    For tests whose routes start real background walks (option searches): the
    rows are deleted only after those threads stop writing.
    """
    before = all_task_ids(engine)
    yield
    created = list(all_task_ids(engine) - before)
    await_walks_ended(engine, created)
    delete_committed_tasks(engine, created)


def delete_committed_tasks(engine: Engine, created: list[uuid.UUID]) -> None:
    """Hard-delete ``created`` tasks and everything that names them, links first."""
    with engine.begin() as conn:
        conn.execute(
            capability_run.update()
            .where(capability_run.c.task_id.in_(created))
            .where(capability_run.c.status.in_(("running", "paused")))
            .values(status="aborted", ended_at=now())
        )
        # Every link across the whole batch first: a link pins the SOURCE
        # task's walk, so deleting the source's rows while the target's link
        # still names them is a foreign-key violation.
        conn.execute(task_link.delete().where(task_link.c.source_task_id.in_(created)))
        conn.execute(task_link.delete().where(task_link.c.target_task_id.in_(created)))
        conn.execute(
            project_membership.delete().where(project_membership.c.task_id.in_(created))
        )
        # A linked finding's membership names its source task.
        conn.execute(option_membership.delete().where(option_membership.c.task_id.in_(created)))
        # A target's row for a snapshot its source also holds (inherit copied
        # it) goes first, so each task's delete removes only its own snapshots.
        other = task_source_snapshot.alias("other")
        conn.execute(
            task_source_snapshot.delete()
            .where(task_source_snapshot.c.task_id.in_(created))
            .where(
                select(other.c.task_source_snapshot_id)
                .where(other.c.source_snapshot_id == task_source_snapshot.c.source_snapshot_id)
                .where(other.c.task_id != task_source_snapshot.c.task_id)
                .where(other.c.origin == "acquired")
                .where(other.c.ingested_at < task_source_snapshot.c.ingested_at)
                .exists()
            )
        )
        for task_id in created:
            delete_task_data(conn, task_id)
