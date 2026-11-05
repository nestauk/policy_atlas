"""Uploading your own theory of change: the routes (task 054, increment 5, C8)."""

from __future__ import annotations

import base64
import uuid
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from policy_atlas.api.deps import get_runner_backends, get_task_agent_backend, get_upload_store
from policy_atlas.core.uploads import LocalUploadStore
from policy_atlas.runtime.runner import RunnerBackends
from policy_atlas.runtime.task_agent import StubTaskAgentBackend
from policy_atlas.theory_of_change import store
from policy_atlas.theory_of_change.backend import stub_draft
from tests.api.resource_support import (
    api_client,
    create_task,
    remove_committed_tasks,  # noqa: F401 — autouse
    task_agent_turn_ok,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _overrides(folder: Path) -> dict[Callable[..., object], Callable[..., object]]:
    return {
        get_task_agent_backend: lambda: StubTaskAgentBackend(),
        get_runner_backends: lambda: RunnerBackends(),
        get_upload_store: lambda: LocalUploadStore(folder),
    }


def _toc_task(client: TestClient, owner: dict[str, str]) -> str:
    client.app.state.settings = replace(  # type: ignore[attr-defined]
        client.app.state.settings,  # type: ignore[attr-defined]
        theory_of_change_enabled=True,
    )
    return create_task(
        client, owner, name="Mine", question="My own theory", capability="theory_of_change"
    )


def _upload(
    client: TestClient,
    headers: dict[str, str],
    task_id: str,
    data: bytes = PNG,
    content_type: str = "image/png",
) -> object:
    return client.post(
        f"/api/v1/tasks/{task_id}/toc/uploads",
        headers=headers,
        json={
            "file_name": "theory.png",
            "content_type": content_type,
            "data_base64": base64.b64encode(data).decode(),
        },
    )


def test_an_upload_is_read_shown_back_and_becomes_the_plan(tmp_path: Path) -> None:
    with api_client(tmp_path, _overrides(tmp_path / "store")) as (client, owner, other):
        task_id = _toc_task(client, owner)
        response = _upload(client, owner, task_id)
        assert response.status_code == 201, response.text  # type: ignore[attr-defined]
        body = response.json()  # type: ignore[attr-defined]
        assert body["counts"] == {
            "boxes": 3,
            "drawn": 2,
            "inferred": 0,
            "groups": 0,
            "unconnected": 0,
        }
        original = client.get(
            f"/api/v1/tasks/{task_id}/toc/uploads/{body['upload_id']}", headers=owner
        )
        assert original.status_code == 200 and original.content == PNG
        assert original.headers["content-type"] == "image/png"
        assert original.headers["x-content-type-options"] == "nosniff"
        assert original.headers["content-disposition"] == 'inline; filename="theory.png"'
        # Someone who cannot read the task gets the same 404 as for no upload at all.
        hidden = client.get(
            f"/api/v1/tasks/{task_id}/toc/uploads/{body['upload_id']}", headers=other
        )
        assert hidden.status_code == 404
        # The next turn's plan is the uploaded theory, word for word.
        turn = task_agent_turn_ok(client, owner, task_id, "Here is my theory of change.")
        plan = turn["toc_plan"]
        assert plan["entry_point"] == "existing_theory"
        assert plan["upload_id"] == body["upload_id"]
        assert plan["existing_theory_text"].startswith("The user's own theory of change")
        assert "“Fund the programme” → “People take part”" in plan["existing_theory_text"]


def test_a_renamed_or_foreign_file_is_refused(tmp_path: Path) -> None:
    with api_client(tmp_path, _overrides(tmp_path / "store")) as (client, owner, other):
        task_id = _toc_task(client, owner)
        renamed = _upload(client, owner, task_id, data=b"%PDF-1.7 not a png")
        assert renamed.status_code == 422  # type: ignore[attr-defined]
        assert renamed.json()["error"]["code"] == "upload_type"  # type: ignore[attr-defined]
        # Only an editor uploads.
        assert _upload(client, other, task_id).status_code == 404  # type: ignore[attr-defined]
        missing = client.get(f"/api/v1/tasks/{task_id}/toc/uploads/{uuid.uuid4()}", headers=owner)
        assert missing.status_code == 404


def test_no_upload_once_the_theory_is_drafted(engine: Engine, tmp_path: Path) -> None:
    with api_client(tmp_path, _overrides(tmp_path / "store")) as (client, owner, _other):
        task_id = _toc_task(client, owner)
        with engine.begin() as conn:
            store.write_draft(conn, task_id=uuid.UUID(task_id), run_id=None, draft=stub_draft({}))
        refused = _upload(client, owner, task_id)
        assert refused.status_code == 409  # type: ignore[attr-defined]
        assert refused.json()["error"]["code"] == "toc_plan_fixed"  # type: ignore[attr-defined]
