"""End-to-end SSE replay, tail, ownership, heartbeat, and tick coverage."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.engine import Engine

from policy_atlas.api import continuation
from policy_atlas.api.app import create_app
from policy_atlas.api.dev_issuer import init, mint_token
from policy_atlas.api.routers.sse import _summary
from policy_atlas.api.settings import Settings
from policy_atlas.api.stage_vocabulary import stage_for_payload
from policy_atlas.core import events
from policy_atlas.core.liveness import tick_hub
from policy_atlas.core.schema import event_log, project
from policy_atlas.runtime import runner as runner_module
from policy_atlas.runtime.runner import NullIO, WalkParked, run_plan
from tests.helpers import delete_project_data
from tests.runtime.test_runner import _base_plan, _runner_backends, _seed_project
from tests.runtime.test_steering import _insert_plan_row


class _QueueStream(httpx.AsyncByteStream):
    """Response stream backed by an ASGI body's incremental byte queue."""

    def __init__(
        self,
        queue: asyncio.Queue[bytes | BaseException | None],
        task: asyncio.Task[None],
    ):
        self._queue = queue
        self._task = task

    async def __aiter__(self) -> AsyncIterator[bytes]:
        while True:
            item = await self._queue.get()
            if item is None:
                return
            if isinstance(item, BaseException):
                raise item
            yield item

    async def aclose(self) -> None:
        """Cancel the endpoint task when the test stops consuming an infinite stream."""
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task


class _StreamingAsgiTransport(httpx.AsyncBaseTransport):
    """ASGI transport that exposes body chunks before an infinite response completes.

    httpx's built-in ``ASGITransport`` buffers all body chunks.  SSE never
    completes, so the test-only transport mirrors its request handling while
    queueing response chunks as they are emitted.
    """

    def __init__(self, app: Any) -> None:
        self._app = app

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Run one ASGI request until headers are ready, then stream its body queue."""
        assert isinstance(request.stream, httpx.AsyncByteStream)
        scope: dict[str, Any] = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": request.method,
            "headers": [(key.lower(), value) for key, value in request.headers.raw],
            "scheme": request.url.scheme,
            "path": request.url.path,
            "raw_path": request.url.raw_path.split(b"?")[0],
            "query_string": request.url.query,
            "server": (request.url.host, request.url.port),
            "client": ("127.0.0.1", 123),
            "root_path": "",
        }
        request_chunks = request.stream.__aiter__()
        request_complete = False
        response_started = asyncio.Event()
        response_complete = asyncio.Event()
        body_queue: asyncio.Queue[bytes | BaseException | None] = asyncio.Queue()
        status_code: int | None = None
        response_headers: list[tuple[bytes, bytes]] | None = None

        async def receive() -> dict[str, Any]:
            nonlocal request_complete
            if request_complete:
                await response_complete.wait()
                return {"type": "http.disconnect"}
            try:
                body = await anext(request_chunks)
            except StopAsyncIteration:
                request_complete = True
                return {"type": "http.request", "body": b"", "more_body": False}
            return {"type": "http.request", "body": body, "more_body": True}

        async def send(message: dict[str, Any]) -> None:
            nonlocal status_code, response_headers
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                response_headers = list(message.get("headers", []))
                response_started.set()
                return
            if message["type"] == "http.response.body":
                body = message.get("body", b"")
                if body and request.method != "HEAD":
                    await body_queue.put(body)
                if not message.get("more_body", False):
                    response_complete.set()
                    await body_queue.put(None)

        async def run_app() -> None:
            nonlocal response_headers, status_code
            try:
                await self._app(scope, receive, send)
            except asyncio.CancelledError:
                raise
            except BaseException as exc:
                if not response_started.is_set():
                    status_code = 500
                    response_headers = []
                    response_started.set()
                await body_queue.put(exc)
                response_complete.set()
                await body_queue.put(None)

        task = asyncio.create_task(run_app())
        await response_started.wait()
        assert status_code is not None
        assert response_headers is not None
        return httpx.Response(
            status_code,
            headers=response_headers,
            stream=_QueueStream(body_queue, task),
            request=request,
        )


@dataclass(frozen=True)
class _SseItem:
    """One parsed SSE frame or comment line."""

    event: str | None
    data: dict[str, Any] | None
    sequence: int | None
    comment: str | None = None


class _SseStream:
    """Incremental SSE parser with bounded collection and deterministic closure."""

    def __init__(self, response_context: Any, response: httpx.Response) -> None:
        self._response_context = response_context
        self._response = response
        self._lines = response.aiter_lines()

    async def next(self, *, timeout: float = 3.0) -> _SseItem:
        """Read the next complete frame or keep-alive comment within ``timeout`` seconds."""
        fields: dict[str, str] = {}
        while True:
            line = await asyncio.wait_for(anext(self._lines), timeout=timeout)
            if line.startswith(":"):
                return _SseItem(event=None, data=None, sequence=None, comment=line[1:].strip())
            if not line:
                if not fields:
                    continue
                data = json.loads(fields["data"])
                sequence = int(fields["id"]) if "id" in fields else None
                return _SseItem(event=fields.get("event"), data=data, sequence=sequence)
            key, _, value = line.partition(":")
            fields[key] = value.lstrip()

    async def collect_until(
        self,
        predicate: Callable[[_SseItem], bool],
        *,
        timeout: float = 5.0,
    ) -> list[_SseItem]:
        """Collect frames through the first item satisfying ``predicate``."""
        items: list[_SseItem] = []
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError("SSE predicate was not reached")
            item = await self.next(timeout=remaining)
            items.append(item)
            if predicate(item):
                return items

    async def aclose(self) -> None:
        """Stop consumption and cancel the app-side generator."""
        await self._response_context.__aexit__(None, None, None)


@dataclass(frozen=True)
class _ApiSession:
    """Lifespan-managed app and authenticated clients for an SSE scenario."""

    client: httpx.AsyncClient
    owner_headers: dict[str, str]
    other_headers: dict[str, str]
    owner_id: str

    async def open_stream(self, project_id: uuid.UUID, *, cursor: int = 0) -> _SseStream:
        """Open an owner-authenticated SSE response and return its incremental parser."""
        context = self.client.stream(
            "GET",
            f"/api/v1/projects/{project_id}/events?cursor={cursor}",
            headers=self.owner_headers,
        )
        response = await context.__aenter__()
        assert response.status_code == 200, await response.aread()
        return _SseStream(context, response)


@asynccontextmanager
async def _api_session(
    tmp_path: Path, *, heartbeat_seconds: float = 15.0
) -> AsyncIterator[_ApiSession]:
    """Create a dev-issuer app under its lifespan with an incremental ASGI client."""
    key_dir = tmp_path / "issuer"
    owner_id = f"owner-{uuid.uuid4()}"
    settings = Settings(
        "http://dev-issuer.local",
        "sse-test",
        None,
        init(key_dir),
        "http://app.example.test",
        os.environ["DATABASE_URL"],
        sse_poll_interval_seconds=0.01,
        sse_heartbeat_seconds=heartbeat_seconds,
    )
    owner = mint_token(owner_id, settings.oidc_issuer, settings.oidc_client_id, 60, key_dir)
    other = mint_token(
        f"other-{uuid.uuid4()}", settings.oidc_issuer, settings.oidc_client_id, 60, key_dir
    )
    app = create_app(settings=settings)
    async with app.router.lifespan_context(app), httpx.AsyncClient(
        transport=_StreamingAsgiTransport(app), base_url="http://testserver"
    ) as client:
        yield _ApiSession(
            client=client,
            owner_headers={"Authorization": f"Bearer {owner}"},
            other_headers={"Authorization": f"Bearer {other}"},
            owner_id=owner_id,
        )


def _owned_seed(engine: Engine, owner_id: str) -> tuple[uuid.UUID, uuid.UUID]:
    """Create the fixture corpus project and attach it to the API-session owner."""
    project_id, scope_id = _seed_project(engine)
    with engine.begin() as conn:
        conn.execute(
            update(project)
            .where(project.c.project_id == project_id)
            .values(owner_user_id=owner_id)
        )
    return project_id, scope_id


def _plan_walk(
    engine: Engine,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    *,
    steering: str,
) -> tuple[Any, uuid.UUID]:
    """Build a small approved fixture plan and persist its plan row."""
    plan = _base_plan(
        analysis_depth="landscape",
        components=["characterise"],
        grouping_facets=None,
        steering_mode=steering,
    )
    plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
    return plan, plan_id


def _run_walk(
    engine: Engine,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    plan: Any,
    plan_id: uuid.UUID,
    *,
    io: Any = None,
) -> Any:
    """Run one fixture walk through the real runner seam."""
    return run_plan(
        engine,
        project_id=project_id,
        evidence_scope_id=scope_id,
        plan=plan,
        plan_id=plan_id,
        plan_version=1,
        plan_row_id=plan_id,
        backends=_runner_backends(),
        io=io,
    )


def _cleanup(engine: Engine, project_id: uuid.UUID | None) -> None:
    """Delete committed fixture data after a streaming test."""
    if project_id is not None:
        with engine.begin() as conn:
            delete_project_data(conn, project_id)


def _persisted(items: list[_SseItem]) -> list[_SseItem]:
    """Return durable frames while excluding comments and ephemeral ticks."""
    return [item for item in items if item.sequence is not None]


def _sequence(item: _SseItem) -> int:
    """Return a persisted item's non-null cursor sequence."""
    assert item.sequence is not None
    return item.sequence


def _finished(item: _SseItem) -> bool:
    """Identify the terminal public run-status frame."""
    return item.event == "run.status" and item.data is not None and item.data["status"] in {
        "succeeded",
        "degraded",
        "failed",
        "aborted",
    }


def test_stage_completed_summary_flattens_nested_round_index() -> None:
    """Search-loop round_index is nested; the public summary must surface it."""
    summary = _summary(
        {
            "component": "acquire",
            "registry_component": "acquire",
            "search": {"round_index": 2, "queries_run": 4},
        }
    )
    assert summary["round_index"] == 2
    assert "search" not in summary
    assert "component" not in summary


def test_sse_replay_idempotence_and_cursor_suffix(engine: Engine, tmp_path: Path) -> None:
    """Replay rebuilds the same durable narrative and cursors select its exact suffix."""

    async def exercise() -> None:
        project_id: uuid.UUID | None = None
        try:
            async with _api_session(tmp_path) as api:
                project_id, scope_id = _owned_seed(engine, api.owner_id)
                plan, plan_id = _plan_walk(engine, project_id, scope_id, steering="unattended")
                outcome = await asyncio.to_thread(
                    _run_walk, engine, project_id, scope_id, plan, plan_id
                )
                assert outcome.status == "succeeded"

                first_stream = await api.open_stream(project_id)
                first = _persisted(await first_stream.collect_until(_finished))
                await first_stream.aclose()
                second_stream = await api.open_stream(project_id)
                second = _persisted(await second_stream.collect_until(_finished))
                await second_stream.aclose()

                assert [(item.sequence, item.event, item.data) for item in second] == [
                    (item.sequence, item.event, item.data) for item in first
                ]
                assert [_sequence(item) for item in first] == sorted(
                    _sequence(item) for item in first
                )
                assert first[0].data is not None and first[0].data["status"] == "running"
                assert first[-1].data is not None and first[-1].data["status"] == "succeeded"
                with engine.connect() as conn:
                    started = sum(
                        event["event_type"] == "run.started"
                        and isinstance(event["payload"], dict)
                        and stage_for_payload(event["payload"]) is not None
                        for event in events.read(conn, project_id)
                    )
                # ingest_full_text (and screen_full) still write run.started but
                # are not public stages, so the counts match the mapped subset.
                assert sum(item.event == "stage.started" for item in first) == started

                cursor = first[len(first) // 2].sequence
                assert cursor is not None
                suffix_stream = await api.open_stream(project_id, cursor=cursor)
                suffix = _persisted(await suffix_stream.collect_until(_finished))
                await suffix_stream.aclose()
                assert [(item.sequence, item.event, item.data) for item in suffix] == [
                    (item.sequence, item.event, item.data)
                    for item in first
                    if _sequence(item) > cursor
                ]
        finally:
            _cleanup(engine, project_id)

    asyncio.run(exercise())


def test_sse_backlog_to_tail_has_no_duplicate_or_missing_mapped_sequences(
    engine: Engine, tmp_path: Path, monkeypatch: Any
) -> None:
    """A stream crossing its snapshot cutoff observes every mapped durable event once."""

    async def exercise() -> None:
        project_id: uuid.UUID | None = None
        original = runner_module._run_step_attempt
        entered = threading.Event()

        def slow_attempt(*args: Any, **kwargs: Any) -> Any:
            entered.set()
            threading.Event().wait(0.15)
            return original(*args, **kwargs)

        monkeypatch.setattr(runner_module, "_run_step_attempt", slow_attempt)
        try:
            async with _api_session(tmp_path) as api:
                project_id, scope_id = _owned_seed(engine, api.owner_id)
                plan, plan_id = _plan_walk(engine, project_id, scope_id, steering="unattended")
                walk = asyncio.create_task(
                    asyncio.to_thread(_run_walk, engine, project_id, scope_id, plan, plan_id)
                )
                assert await asyncio.to_thread(entered.wait, 2.0)
                stream = await api.open_stream(project_id)
                observed = _persisted(await stream.collect_until(_finished, timeout=10.0))
                await stream.aclose()
                assert (await walk).status == "succeeded"

                with engine.connect() as conn:
                    rows = events.read(conn, project_id)
                    from policy_atlas.api.routers import sse

                    expected = [
                        frame["sequence"]
                        for frame in sse._map_rows(
                            conn, project_id=project_id, rows=rows, through=None
                        )
                    ]
                observed_ids = [_sequence(item) for item in observed]
                assert observed_ids == sorted(observed_ids)
                assert len(observed_ids) == len(set(observed_ids))
                assert set(observed_ids) == set(expected)
        finally:
            _cleanup(engine, project_id)

    asyncio.run(exercise())


class _ParkOnceIO:
    """Park the first after-component pause of a real fixture walk."""

    def check_in(self, component: str, payload: dict[str, Any]) -> None:
        """Discard deterministic check-in chatter before the parked boundary."""
        del component, payload

    def pause(self, point: dict[str, Any], render: str) -> Any:
        """Park at the first after-component decision point."""
        del render
        if point["boundary"] == "after_component":
            raise WalkParked()
        from policy_atlas.runtime.steering import Continue

        return Continue()


def test_sse_parked_pending_then_resolved_history(engine: Engine, tmp_path: Path) -> None:
    """A parked replay ends pending; after continuation it replays pending then resolved."""

    async def exercise() -> None:
        project_id: uuid.UUID | None = None
        try:
            async with _api_session(tmp_path) as api:
                project_id, scope_id = _owned_seed(engine, api.owner_id)
                plan, plan_id = _plan_walk(engine, project_id, scope_id, steering="frequent")
                parked = await asyncio.to_thread(
                    _run_walk, engine, project_id, scope_id, plan, plan_id, io=_ParkOnceIO()
                )
                assert parked.status == "paused"
                assert parked.capability_run_id is not None

                stream = await api.open_stream(project_id)
                before = _persisted(
                    await stream.collect_until(
                        lambda item: item.event == "run.status"
                        and item.data is not None
                        and item.data["status"] == "paused"
                    )
                )
                await stream.aclose()
                pending = [item for item in before if item.event == "checkin.pending"]
                assert len(pending) == 1
                assert not [item for item in before if item.event == "checkin.resolved"]
                assert pending[0].data is not None
                check_in_id = uuid.UUID(pending[0].data["check_in"]["check_in_id"])

                answer = await asyncio.to_thread(
                    continuation.answer_check_in,
                    engine,
                    project_id=project_id,
                    check_in_id=check_in_id,
                    response={"kind": "option", "option_id": "continue"},
                    actor=api.owner_id,
                )
                claim = await asyncio.to_thread(
                    continuation.claim_continuation,
                    engine,
                    project_id=project_id,
                    capability_run_id=answer.capability_run_id,
                )
                assert claim is not None
                assert (
                    await asyncio.to_thread(
                        continuation.execute_continuation,
                        engine,
                        project_id=project_id,
                        capability_run_id=answer.capability_run_id,
                        backends=_runner_backends(),
                        io=NullIO(),
                    )
                ).status == "succeeded"

                history_stream = await api.open_stream(project_id)
                history = _persisted(await history_stream.collect_until(_finished, timeout=10.0))
                await history_stream.aclose()
                pending_index = next(
                    index
                    for index, item in enumerate(history)
                    if item.event == "checkin.pending"
                    and item.data is not None
                    and item.data["check_in"]["check_in_id"] == str(check_in_id)
                )
                resolved_index = next(
                    index
                    for index, item in enumerate(history)
                    if item.event == "checkin.resolved"
                    and item.data is not None
                    and item.data["check_in_id"] == str(check_in_id)
                )
                assert pending_index < resolved_index
                response = await api.client.get(
                    f"/api/v1/projects/{project_id}/check-ins", headers=api.owner_headers
                )
                assert response.status_code == 200
                assert response.json()["data"] == []
        finally:
            _cleanup(engine, project_id)

    asyncio.run(exercise())


def test_sse_idle_stream_emits_a_heartbeat(engine: Engine, tmp_path: Path) -> None:
    """The injectable heartbeat interval produces an SSE comment for an idle project."""

    async def exercise() -> None:
        project_id: uuid.UUID | None = None
        try:
            async with _api_session(tmp_path, heartbeat_seconds=0.05) as api:
                project_id, _ = _owned_seed(engine, api.owner_id)
                stream = await api.open_stream(project_id)
                item = await stream.next(timeout=1.0)
                await stream.aclose()
                assert item.comment == "keep-alive"
        finally:
            _cleanup(engine, project_id)

    asyncio.run(exercise())


def test_sse_requires_authentication_and_owner_scope(engine: Engine, tmp_path: Path) -> None:
    """The stream rejects missing credentials and hides another owner's project."""

    async def exercise() -> None:
        project_id: uuid.UUID | None = None
        try:
            async with _api_session(tmp_path) as api:
                project_id, _ = _owned_seed(engine, api.owner_id)
                unauthenticated = await api.client.get(f"/api/v1/projects/{project_id}/events")
                cross_owner = await api.client.get(
                    f"/api/v1/projects/{project_id}/events", headers=api.other_headers
                )
                assert unauthenticated.status_code == 401
                assert cross_owner.status_code == 404
        finally:
            _cleanup(engine, project_id)

    asyncio.run(exercise())


def test_sse_tick_is_ephemeral_and_has_no_cursor_id(engine: Engine, tmp_path: Path) -> None:
    """A liveness tick reaches a live stream without adding an event-log row."""

    async def exercise() -> None:
        project_id: uuid.UUID | None = None
        try:
            async with _api_session(tmp_path) as api:
                project_id, _ = _owned_seed(engine, api.owner_id)
                with engine.connect() as conn:
                    before = conn.execute(
                        select(event_log.c.event_id).where(event_log.c.project_id == project_id)
                    ).all()
                stream = await api.open_stream(project_id)
                await asyncio.sleep(0.02)
                tick_hub.publish(project_id, stage="acquire", note="Test tick")
                item = await stream.next(timeout=1.0)
                await stream.aclose()
                with engine.connect() as conn:
                    after = conn.execute(
                        select(event_log.c.event_id).where(event_log.c.project_id == project_id)
                    ).all()
                assert item.event == "tick"
                assert item.sequence is None
                assert item.data is not None and item.data["note"] == "Test tick"
                assert after == before
        finally:
            _cleanup(engine, project_id)

    asyncio.run(exercise())
