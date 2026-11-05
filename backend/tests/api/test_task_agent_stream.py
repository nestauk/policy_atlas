"""NDJSON wire tests for the streamed Task Agent turn (task 058, N9 and N10)."""

from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.deps import get_task_agent_backend
from policy_atlas.api.routers import task_agent as task_agent_router
from policy_atlas.core.schema import task_agent_transcript
from policy_atlas.runtime.capability_registry import TaskAgentProfile
from policy_atlas.runtime.task_agent import StubTaskAgentBackend, TaskAgentTurnWire
from tests.api.resource_support import api_client, create_task, post_turn

_FIRST_MESSAGE = "How can cities reduce heat risk?"


def _reset_turn_locks() -> None:
    with task_agent_router._turn_locks_guard:
        task_agent_router._turn_locks.clear()


def _url(task_id: str) -> str:
    return f"/api/v1/tasks/{task_id}/task-agent-turns"


def _body(message: str = _FIRST_MESSAGE, client_turn_id: str | None = None) -> dict[str, str]:
    return {"message": message, "client_turn_id": client_turn_id or str(uuid.uuid4())}


class PiecewiseTaskAgent(StubTaskAgentBackend):
    """The stub turn, its reply sent as several deltas."""

    def turn(
        self,
        profile: TaskAgentProfile,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        inputs: Any = None,
        session_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
        on_delta: Callable[[str], None] | None = None,
    ) -> TaskAgentTurnWire:
        turn = super().turn(profile, turns, previous_draft)
        if on_delta is not None:
            for start in range(0, len(turn.reply), 7):
                on_delta(turn.reply[start : start + 7])
        return turn


class FailingTaskAgent(StubTaskAgentBackend):
    """A planner that fails after its first piece of reply."""

    def turn(self, *args: Any, on_delta: Callable[[str], None] | None = None, **kwargs: Any) -> Any:
        if on_delta is not None:
            on_delta("Half a")
        raise RuntimeError("provider failed mid-reply")


class GatedTaskAgent(StubTaskAgentBackend):
    """Sends one delta, then waits for the test before finishing the turn."""

    def __init__(self) -> None:
        self.release = threading.Event()

    def turn(
        self,
        profile: TaskAgentProfile,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        inputs: Any = None,
        session_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
        on_delta: Callable[[str], None] | None = None,
    ) -> TaskAgentTurnWire:
        turn = super().turn(profile, turns, previous_draft)
        if on_delta is not None:
            on_delta(turn.reply[:5])
        assert self.release.wait(timeout=10), "the test never released the planner"
        if on_delta is not None:
            on_delta(turn.reply[5:])
        return turn


def _row(engine: Engine, task_id: str) -> Any:
    with engine.connect() as conn:
        return (
            conn.execute(
                select(task_agent_transcript).where(
                    task_agent_transcript.c.task_id == uuid.UUID(task_id)
                )
            )
            .mappings()
            .one()
        )


def test_the_stream_sends_progress_deltas_and_one_completed_turn(
    engine: Engine, tmp_path: Path
) -> None:
    _reset_turn_locks()
    with api_client(tmp_path, {get_task_agent_backend: PiecewiseTaskAgent}) as (
        client,
        owner,
        _,
    ):
        task_id = create_task(client, owner)
        turn_id = str(uuid.uuid4())
        body = _body(client_turn_id=turn_id)
        streamed = post_turn(client, _url(task_id), headers=owner, json=body)
        _reset_turn_locks()
        replay = post_turn(client, _url(task_id), headers=owner, json=body)

    assert streamed.status_code == 200
    assert streamed.headers["content-type"].startswith("application/x-ndjson")
    types = [event["type"] for event in streamed.events]
    assert types[0] == "progress"
    assert streamed.events[0]["label"] == "Drafting the plan"
    assert types[-1] == "completed"
    assert types.count("completed") == 1 and "failed" not in types
    deltas = [event["text"] for event in streamed.events if event["type"] == "delta"]
    assert len(deltas) > 1
    turn = streamed.events[-1]["turn"]
    assert "".join(deltas) == turn["reply"]
    # N10: the planner's clarifying question reaches the client beside its chips.
    assert turn["question"] == "What decision should this evidence review inform?"
    assert len(turn["suggestions"]) == 3
    # A replay is one completed line carrying the stored turn.
    assert [event["type"] for event in replay.events] == ["completed"]
    assert replay.events[0]["turn"] == turn


def test_a_planner_failure_is_one_failed_line_and_the_row_is_failed(
    engine: Engine, tmp_path: Path
) -> None:
    _reset_turn_locks()
    with api_client(tmp_path, {get_task_agent_backend: FailingTaskAgent}) as (client, owner, _):
        task_id = create_task(client, owner)
        response = post_turn(client, _url(task_id), headers=owner, json=_body())
        # The lock is released when the worker ends, so the next turn is admitted.
        follow_up = post_turn(client, _url(task_id), headers=owner, json=_body("Try again"))

    assert response.status_code == 200
    types = [event["type"] for event in response.events]
    assert types == ["progress", "delta", "failed"]
    assert response.events[-1] == {
        "type": "failed",
        "error": {"code": "task_agent_turn_failed", "message": "Task Agent turn failed"},
        "turn_index": 0,
    }
    # The provider's own message never reaches the caller.
    assert "provider failed" not in response.text
    assert follow_up.status_code == 200
    with engine.connect() as conn:
        statuses = conn.execute(
            select(task_agent_transcript.c.status)
            .where(task_agent_transcript.c.task_id == uuid.UUID(task_id))
            .order_by(task_agent_transcript.c.turn_index)
        ).scalars().all()
    assert statuses == ["failed", "failed"]


def test_refusals_before_the_stream_are_json_errors(engine: Engine, tmp_path: Path) -> None:
    _reset_turn_locks()
    agent = GatedTaskAgent()
    with api_client(tmp_path, {get_task_agent_backend: lambda: agent}) as (client, owner, _):
        task_id = create_task(client, owner)
        unknown = post_turn(client, _url(str(uuid.uuid4())), headers=owner, json=_body())
        assert unknown.status_code == 404
        assert unknown.headers["content-type"].startswith("application/json")
        assert unknown.events == []

        results: dict[str, Any] = {}
        first = threading.Thread(
            target=lambda: results.setdefault(
                "first", post_turn(client, _url(task_id), headers=owner, json=_body())
            )
        )
        first.start()
        try:
            deadline = time.monotonic() + 10
            while _pending(engine, task_id) == 0 and time.monotonic() < deadline:
                time.sleep(0.02)
            second = post_turn(client, _url(task_id), headers=owner, json=_body("Second"))
        finally:
            agent.release.set()
            first.join(timeout=10)

    assert second.status_code == 409
    assert second.headers["content-type"].startswith("application/json")
    assert second.json()["error"]["code"] == "task_agent_turn_in_progress"
    assert results["first"].events[-1]["type"] == "completed"


def _pending(engine: Engine, task_id: str) -> int:
    with engine.connect() as conn:
        return len(
            conn.execute(
                select(task_agent_transcript.c.id)
                .where(task_agent_transcript.c.task_id == uuid.UUID(task_id))
                .where(task_agent_transcript.c.status == "pending")
            ).all()
        )


async def _read_then_disconnect(
    app: Any, path: str, headers: dict[str, str]
) -> list[dict[str, Any]]:
    """Post a turn over raw ASGI, read up to the first delta, then disconnect."""
    body = json.dumps(_body()).encode()
    lines: list[dict[str, Any]] = []
    saw_delta = asyncio.Event()
    request_sent = False

    async def receive() -> dict[str, Any]:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        await saw_delta.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            assert message["status"] == 200
        elif message["type"] == "http.response.body":
            for line in message.get("body", b"").decode().splitlines():
                if line.strip():
                    lines.append(json.loads(line))
            if any(line["type"] == "delta" for line in lines):
                saw_delta.set()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"content-type", b"application/json"),
            *((key.lower().encode(), value.encode()) for key, value in headers.items()),
        ],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }
    await asyncio.wait_for(app(scope, receive, send), timeout=10)
    return lines


def test_a_client_that_stops_reading_still_gets_the_turn_stored(
    engine: Engine, tmp_path: Path
) -> None:
    _reset_turn_locks()
    agent = GatedTaskAgent()
    with api_client(tmp_path, {get_task_agent_backend: lambda: agent}) as (client, owner, _):
        task_id = create_task(client, owner)
        # The test client buffers a whole response, so the disconnect is driven
        # at the ASGI level: read until the first delta, then hang up.
        # Not asyncio.run: it would wait for the stream's queue reader thread,
        # which only wakes when the worker posts again, after the release below.
        loop = asyncio.new_event_loop()
        try:
            first_two = loop.run_until_complete(
                _read_then_disconnect(client.app, _url(task_id), owner)
            )
        finally:
            agent.release.set()
            loop.close()
        # The reader has gone; the planner finishes and the worker stores the turn.
        agent.release.set()
        deadline = time.monotonic() + 10
        while _row(engine, task_id)["status"] == "pending" and time.monotonic() < deadline:
            time.sleep(0.02)
        listed = client.get(_url(task_id), headers=owner)

    assert [event["type"] for event in first_two] == ["progress", "delta"]
    row = _row(engine, task_id)
    assert row["status"] == "completed"
    assert row["reply"].startswith(first_two[1]["text"])
    stored = listed.json()["data"][0]
    assert stored["status"] == "completed"
    assert stored["question"] == "What decision should this evidence review inform?"
    assert len(stored["suggestions"]) == 3


@pytest.mark.parametrize("message", ["A comparison of intervention options"])
def test_a_ready_turn_streams_and_approves_the_plan(
    engine: Engine, tmp_path: Path, message: str
) -> None:
    _reset_turn_locks()
    with api_client(tmp_path, {get_task_agent_backend: PiecewiseTaskAgent}) as (
        client,
        owner,
        _,
    ):
        task_id = create_task(client, owner)
        post_turn(client, _url(task_id), headers=owner, json=_body())
        ready = post_turn(client, _url(task_id), headers=owner, json=_body(message))
        plan = client.get(f"/api/v1/tasks/{task_id}/plan", headers=owner)

    assert ready.json()["plan"]["ready"] is True
    assert ready.json()["question"] is None
    assert plan.json()["status"] == "approved"
