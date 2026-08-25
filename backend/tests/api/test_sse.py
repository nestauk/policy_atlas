"""End-to-end SSE replay, tail, ownership, heartbeat, and tick coverage."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import false, select, update
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.schema import Table
from structlog.testing import capture_logs

from policy_atlas.api import continuation
from policy_atlas.api.app import create_app
from policy_atlas.api.dev_issuer import init, mint_token
from policy_atlas.api.routers import _access, sse
from policy_atlas.api.routers.sse import _tail
from policy_atlas.api.settings import Settings
from policy_atlas.core import events
from policy_atlas.core.liveness import tick_hub
from policy_atlas.core.schema import app_user, event_log, portfolio, project
from policy_atlas.ops import commands as ops_commands
from policy_atlas.runtime import runner as runner_module
from policy_atlas.runtime.runner import NullIO, WalkParked, run_plan
from tests.api.org_support import (
    make_org,
    make_portfolio,
    make_project,
    ops_enrol,
    ops_set_admin,
    seeded,
    unique_email,
)
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

    async def drain_until_closed(
        self, *, timeout: float = 5.0
    ) -> tuple[bool, list[_SseItem]]:
        """Consume whatever remains, reporting closure **and what arrived**.

        The revocation cases' assertion, in two halves. A closed stream is the
        *absence* of further output plus a completed HTTP body, so this drains
        until the body ends (``StopAsyncIteration``) and calls a stream that is
        merely quiet a failure rather than a pass.

        It returns the drained items rather than discarding them because
        "closes eventually" is the weaker half of the property. A stream that
        emits one more frame about the project and *then* closes passes
        "closed" and still disclosed the frame — which is exactly what the
        pre-fix loop did with a tick, having yielded it before the tail
        re-authorised. The caller asserts on the list.
        """
        items: list[_SseItem] = []
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return False, items
            try:
                items.append(await self.next(timeout=remaining))
            except StopAsyncIteration:
                return True, items
            except TimeoutError:
                return False, items

    async def closed(self, *, timeout: float = 5.0) -> bool:
        """Report whether the response ends in time, ignoring what it carried."""
        closed, _ = await self.drain_until_closed(timeout=timeout)
        return closed

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
    other_id: str

    async def open_stream(
        self,
        project_id: uuid.UUID,
        *,
        cursor: int = 0,
        headers: dict[str, str] | None = None,
    ) -> _SseStream:
        """Open an authenticated SSE response and return its incremental parser.

        Defaults to the owner. The phase-6 revocation cases pass
        ``other_headers`` to hold a *colleague's* stream open, which is the
        only stream any of the four revocation events can close.
        """
        context = self.client.stream(
            "GET",
            f"/api/v1/projects/{project_id}/events?cursor={cursor}",
            headers=headers if headers is not None else self.owner_headers,
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
    other_id = f"other-{uuid.uuid4()}"
    owner = mint_token(owner_id, settings.oidc_issuer, settings.oidc_client_id, 60, key_dir)
    other = mint_token(other_id, settings.oidc_issuer, settings.oidc_client_id, 60, key_dir)
    app = create_app(settings=settings)
    async with app.router.lifespan_context(app), httpx.AsyncClient(
        transport=_StreamingAsgiTransport(app), base_url="http://testserver"
    ) as client:
        yield _ApiSession(
            client=client,
            owner_headers={"Authorization": f"Bearer {owner}"},
            other_headers={"Authorization": f"Bearer {other}"},
            owner_id=owner_id,
            other_id=other_id,
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
                        for event in events.read(conn, project_id)
                    )
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


# --- Phase 6: the tail re-authorises, and revocation closes the stream -------
#
# Contract § 5. The stream used to authorise once in `_snapshot` and then loop
# indefinitely, so none of this slice's four revocation events reached an open
# stream. Three of them are exercised here for real: de-enrolment, a
# visibility flip, and the i.4 portfolio cascade (simulated by the direct
# `project.visibility` update, and again through the real PATCH lever).
#
# The fourth — admin revoke — was pinned only structurally while the admin
# read leg did not exist. Phase 8 shipped the leg, so it is now exercised for
# real too, under the "--- Phase 8" heading at the end of this file, along
# with the SSE half of the admin trace grain. The structural case is kept:
# it is the one that fails if the tail ever grows a tenancy predicate of its
# own instead of resolving through `_read_legs`.


def _org_seed(
    engine: Engine,
    *,
    owner_id: str,
    colleague_id: str,
    in_portfolio: bool = False,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID | None]:
    """Seed one organisation, two enrolled members, and an org-visible project.

    Deliberately not `_owned_seed`: a revocation case needs no evidence
    fixtures and no walk, only a project row a colleague can read and a tail
    loop running over it. Nothing is cleaned up afterwards, for the reason
    `org_support` documents — every subject and organisation name here is
    UUID-unique, so leftover rows are unreachable from any other test.

    Args:
        engine: The session engine; writes here commit, because the
            application reads through its own connection.
        owner_id: The project owner's subject.
        colleague_id: A second subject enrolled in the same organisation.
        in_portfolio: Whether to put the project in a portfolio, which the
            i.4 cascade case needs and the others do not.

    Returns:
        The organisation, the project, and the portfolio if one was made.
    """
    with seeded(engine) as conn:
        org_id = make_org(conn)
        ops_enrol(conn, user_id=owner_id, org_id=org_id, display_name="Owner")
        ops_enrol(conn, user_id=colleague_id, org_id=org_id, display_name="Colleague")
        portfolio_id = (
            make_portfolio(conn, owner_user_id=owner_id, org_id=org_id, visibility="org")
            if in_portfolio
            else None
        )
        project_id = make_project(
            conn,
            owner_user_id=owner_id,
            org_id=org_id,
            visibility="org",
            portfolio_id=portfolio_id,
        )
    return org_id, project_id, portfolio_id


async def _live(stream: _SseStream) -> None:
    """Require one keep-alive, proving the tail loop is running.

    Asserting only that the response opened would let a stream that never
    reached its loop pass the "closed after revocation" cases vacuously.
    """
    assert (await stream.next(timeout=2.0)).comment == "keep-alive"


def _frames(items: list[_SseItem]) -> list[_SseItem]:
    """Every item that is a frame — durable or tick — and not a keep-alive.

    A keep-alive is the literal comment `: keep-alive` and says nothing about
    the project; a frame is content. So "no further frames" is the disclosure
    property, and it does not become flaky because a heartbeat happened to fire
    in the same millisecond as a revocation.
    """
    return [item for item in items if item.event is not None]


async def _colleague_stream_closes_when(
    api: _ApiSession,
    project_id: uuid.UUID,
    revoke: Callable[[], Awaitable[None]],
) -> None:
    """Hold a colleague's stream open, revoke, require closure **and silence**.

    The revocation is an awaitable rather than a statement, so a case can
    revoke by writing the database *or* by calling the real route that does
    it — which is what phase 7's cascade case does now that the lever exists.

    **A tick is published immediately after the revocation commits**, and no
    frame may follow it. That is what turns every revocation case into a
    disclosure assertion rather than only a liveness one: the loop used to
    yield `_encode_tick(tick)` — the project's current stage and progress
    note — *before* the tail re-authorised, so a revoked caller received one
    more frame about the project on their way out. Draining and discarding, as
    these cases did before, cannot see that: the stream still closes.

    The tick is the deterministic probe for it. Ticks are queued per
    subscriber and delivered on the next pass of the loop, so a tick published
    after the revocation is guaranteed to reach the iteration that also
    discovers the revocation — it escapes on every run against the old order
    and on none against the new one.
    """
    stream = await api.open_stream(project_id, headers=api.other_headers)
    try:
        await _live(stream)
        await revoke()
        tick_hub.publish(project_id, stage="acquire", note="After the revocation")
        closed, drained = await stream.drain_until_closed(timeout=5.0)
        assert closed
        assert _frames(drained) == []
    finally:
        await stream.aclose()


async def _colleague_stream_closes_on(
    api: _ApiSession,
    engine: Engine,
    project_id: uuid.UUID,
    revoke: Callable[[Connection], None],
) -> None:
    """:func:`_colleague_stream_closes_when` for the direct-write revocations."""

    async def apply() -> None:
        with seeded(engine) as conn:
            revoke(conn)

    await _colleague_stream_closes_when(api, project_id, apply)


def test_sse_stream_closes_when_the_colleague_is_de_enrolled(
    engine: Engine, tmp_path: Path
) -> None:
    """Revocation 1: ops clears `app_user.org_id` while the stream is open."""

    async def exercise() -> None:
        async with _api_session(tmp_path, heartbeat_seconds=0.05) as api:
            _, project_id, _ = _org_seed(
                engine, owner_id=api.owner_id, colleague_id=api.other_id
            )

            def revoke(conn: Connection) -> None:
                conn.execute(
                    update(app_user)
                    .where(app_user.c.user_id == api.other_id)
                    .values(org_id=None)
                )

            await _colleague_stream_closes_on(api, engine, project_id, revoke)

    asyncio.run(exercise())


def test_sse_stream_closes_when_the_real_ops_cli_de_enrols_the_colleague(
    engine: Engine, tmp_path: Path
) -> None:
    """Revocation 1, driven by the actual operator command instead of a write.

    The case above writes ``app_user.org_id = NULL`` itself, because in phase 6
    that was the only lever there was. Phase 9b ships the real one, so this runs
    it: ``policy_atlas.ops.commands.de_enrol_user`` against the test database,
    while a colleague holds a stream open on an org-visible project.

    Two things this catches that the simulated version cannot. The stream reacts
    to whatever the **real** command writes, so a de-enrolment that ever stopped
    clearing ``org_id`` — or started clearing something else instead — fails
    here while the simulation keeps passing. And it pins that the two halves of
    the slice agree about the same column: SSE re-authorisation reads the org
    leg, the CLI writes it, and nothing in between translates.

    No Cognito client appears, which is not an omission: ``de-enrol`` resolves
    its subject by the stored address in the database and makes no AWS call at
    all (contract § 9's operator IAM is ``ListUsers`` and ``AdminCreateUser``
    only, and this command needs neither).
    """

    async def exercise() -> None:
        async with _api_session(tmp_path, heartbeat_seconds=0.05) as api:
            _, project_id, _ = _org_seed(
                engine, owner_id=api.owner_id, colleague_id=api.other_id
            )
            # `_org_seed` enrols without an address; the CLI resolves by one.
            email = unique_email("colleague")
            with seeded(engine) as conn:
                conn.execute(
                    update(app_user)
                    .where(app_user.c.user_id == api.other_id)
                    .values(email=email)
                )

            async def de_enrol() -> None:
                with seeded(engine) as conn:
                    result = ops_commands.de_enrol_user(conn, email=email)
                assert result.user_id == api.other_id

            await _colleague_stream_closes_when(api, project_id, de_enrol)

    asyncio.run(exercise())


def test_sse_stream_closes_when_the_project_flips_org_to_private(
    engine: Engine, tmp_path: Path
) -> None:
    """Revocation 2: the owner unshares the project while a colleague watches."""

    async def exercise() -> None:
        async with _api_session(tmp_path, heartbeat_seconds=0.05) as api:
            _, project_id, _ = _org_seed(
                engine, owner_id=api.owner_id, colleague_id=api.other_id
            )

            def revoke(conn: Connection) -> None:
                conn.execute(
                    update(project)
                    .where(project.c.project_id == project_id)
                    .values(visibility="private")
                )

            await _colleague_stream_closes_on(api, engine, project_id, revoke)

    asyncio.run(exercise())


def test_sse_stream_closes_when_a_portfolio_cascade_privatises_the_member(
    engine: Engine, tmp_path: Path
) -> None:
    """Revocation 3: the i.4 cascade — the portfolio flips and its member follows.

    Written before the cascade existed, so it writes exactly what the cascade
    writes: the portfolio's `visibility`, and the member project's with it.
    Kept alongside the real-lever case below rather than replaced by it,
    because the two answer different questions — this one pins the *effect* a
    stream must react to, whatever produces it, so a future revocation path
    that reaches the same row state is covered without a new SSE case.

    Kept as its own case rather than folded into the flip above because the
    contract's acceptance list names it separately: it is the revocation whose
    trigger is on a *different row* from the one the caller is streaming, and
    a re-auth that watched only the project it was handed would still be
    correct here only by accident.
    """

    async def exercise() -> None:
        async with _api_session(tmp_path, heartbeat_seconds=0.05) as api:
            _, project_id, portfolio_id = _org_seed(
                engine,
                owner_id=api.owner_id,
                colleague_id=api.other_id,
                in_portfolio=True,
            )

            def revoke(conn: Connection) -> None:
                conn.execute(
                    update(portfolio)
                    .where(portfolio.c.portfolio_id == portfolio_id)
                    .values(visibility="private")
                )
                conn.execute(
                    update(project)
                    .where(project.c.portfolio_id == portfolio_id)
                    .values(visibility="private")
                )

            await _colleague_stream_closes_on(api, engine, project_id, revoke)

    asyncio.run(exercise())


def test_sse_stream_closes_when_the_real_portfolio_cascade_runs(
    engine: Engine, tmp_path: Path
) -> None:
    """Revocation 3, driven by the actual route instead of a simulated write.

    Phase 6 could only write what it believed the cascade would write. Phase 7
    shipped the lever, so this runs it: the owner sends `PATCH
    /api/v1/portfolios/{id} {"visibility": "private"}` while a colleague
    watches a member project's stream, and the colleague's stream ends.

    This is the case that fails if the cascade ever stops carrying its
    members — the simulated version above would keep passing, because it
    writes both rows itself.
    """

    async def exercise() -> None:
        async with _api_session(tmp_path, heartbeat_seconds=0.05) as api:
            _, project_id, portfolio_id = _org_seed(
                engine,
                owner_id=api.owner_id,
                colleague_id=api.other_id,
                in_portfolio=True,
            )

            async def cascade() -> None:
                response = await api.client.patch(
                    f"/api/v1/portfolios/{portfolio_id}",
                    headers=api.owner_headers,
                    json={"visibility": "private"},
                )
                assert response.status_code == 200, response.text
                assert response.json()["visibility"] == "private"

            await _colleague_stream_closes_when(api, project_id, cascade)

    asyncio.run(exercise())


def test_a_batch_read_after_the_grade_check_discloses_nothing_once_access_is_gone(
    engine: Engine, monkeypatch: Any
) -> None:
    """The tail's batch select carries the grade, not just the check before it.

    `_tail` asks `may_read_project` in one statement and reads the event batch
    in another, so a revocation committing *between* the two was still worth
    one batch of frames: the check had already answered "yes". The window is
    small and unhittable on purpose in a test, so it is simulated exactly —
    `may_read_project` is forced to answer "yes" while the row itself has been
    privatised — and the assertion is that the batch comes back empty anyway,
    because the select that reads the events applies the same read legs in the
    same statement.

    The two are not redundant. This gate makes the batch empty; the check is
    what ends the response. Forced true here, the stream would poll for ever
    and disclose nothing, which is the failure mode worth having.
    """
    owner_id = f"owner-{uuid.uuid4()}"
    colleague_id = f"colleague-{uuid.uuid4()}"
    _, project_id, _ = _org_seed(engine, owner_id=owner_id, colleague_id=colleague_id)
    with seeded(engine) as conn:
        events.append(
            conn,
            project_id=project_id,
            run_id=None,
            event_type="project.renamed",
            payload={"name_to": "A name the colleague may still read"},
        )

    readable = _tail(engine, project_id=project_id, user_id=colleague_id, after=0)
    assert readable is not None
    assert [frame["type"] for frame in readable[1]] == ["project.updated"]

    monkeypatch.setattr(
        sse,
        "may_read_project",
        lambda *_args, **_kwargs: _access.ReadCheck(allowed=True, via_admin=False),
    )
    with seeded(engine) as conn:
        conn.execute(
            update(project)
            .where(project.c.project_id == project_id)
            .values(visibility="private")
        )

    revoked = _tail(engine, project_id=project_id, user_id=colleague_id, after=0)
    assert revoked is not None
    assert revoked[1] == []


def test_sse_owner_stream_survives_every_revocation_event(
    engine: Engine, tmp_path: Path
) -> None:
    """The owner leg never revokes: all three levers at once, stream still open.

    De-enrolling the *owner*, privatising the project, and running the
    portfolio cascade over it are each enough to close a colleague's stream,
    and not one of them touches `owner_user_id`. The owner keeps watching
    their own run throughout — the colleague's stream closing in the same
    breath is what makes that a statement about the legs rather than about
    nothing having happened.
    """

    async def exercise() -> None:
        async with _api_session(tmp_path, heartbeat_seconds=0.05) as api:
            _, project_id, portfolio_id = _org_seed(
                engine,
                owner_id=api.owner_id,
                colleague_id=api.other_id,
                in_portfolio=True,
            )
            owner_stream = await api.open_stream(project_id)
            colleague_stream = await api.open_stream(project_id, headers=api.other_headers)
            try:
                await _live(owner_stream)
                await _live(colleague_stream)
                with seeded(engine) as conn:
                    conn.execute(
                        update(app_user)
                        .where(app_user.c.user_id == api.owner_id)
                        .values(org_id=None)
                    )
                    conn.execute(
                        update(portfolio)
                        .where(portfolio.c.portfolio_id == portfolio_id)
                        .values(visibility="private")
                    )
                    conn.execute(
                        update(project)
                        .where(project.c.project_id == project_id)
                        .values(visibility="private")
                    )
                assert await colleague_stream.closed(timeout=5.0)
                await _live(owner_stream)
            finally:
                await owner_stream.aclose()
                await colleague_stream.aclose()

    asyncio.run(exercise())


def test_sse_reauthorisation_resolves_through_the_same_legs_as_the_snapshot(
    engine: Engine, tmp_path: Path, monkeypatch: Any
) -> None:
    """The tail asks the same question the snapshot did, whatever the legs are.

    The admin read leg is a third disjunct inside `_access._read_legs` — the
    single function `_snapshot`'s `accessible_project` resolves through. This
    pins that the **tail** resolves through that same function and honours
    whatever it returns, which is why phase 8 widened the live stream at the
    same line it widened the snapshot and needed no edit to `sse.py`'s grade.
    A second tenancy predicate written out in the tail — the drifted copy the
    closed-helper design exists to prevent — fails here.

    Kept alongside the real admin-revoke case below rather than replaced by
    it: that one proves the behaviour for today's legs, this one proves the
    *mechanism* for whatever legs come next.

    Two things are asserted: that the tail asks `_read_legs` the same question
    the snapshot did (same table, same subject, at least once per batch), and
    that flipping only that function's verdict is enough to end the stream.
    """
    calls: list[tuple[str, str]] = []
    real = _access._read_legs
    state = {"revoked": False}

    def recording(table: Table, user_id: str) -> ColumnElement[bool]:
        calls.append((table.name, user_id))
        return false() if state["revoked"] else real(table, user_id)

    monkeypatch.setattr(_access, "_read_legs", recording)

    async def exercise() -> None:
        async with _api_session(tmp_path, heartbeat_seconds=0.05) as api:
            _, project_id, _ = _org_seed(
                engine, owner_id=api.owner_id, colleague_id=api.other_id
            )
            stream = await api.open_stream(project_id, headers=api.other_headers)
            try:
                await _live(stream)
                # One call authorised the snapshot; the rest are the tail
                # re-authorising per batch. All of them ask about the same row
                # for the same subject.
                assert len(calls) >= 2
                assert set(calls) == {("project", api.other_id)}
                state["revoked"] = True
                assert await stream.closed(timeout=5.0)
            finally:
                await stream.aclose()

    asyncio.run(exercise())


# --- Phase 8: the admin leg on an open stream, and its trace grain -----------
#
# Contract § 3a's SSE clause, in two halves. The **subscribe** is an ordinary
# graded row read — `_snapshot` calls `accessible_project` — so it emits one
# `admin_read` line and nothing special happens here. The **tail** owes one
# `admin_stream_read` line per re-authorisation batch, which is the grain that
# keeps an unbounded stream from becoming an unbounded log: a line per event
# frame would be neither.
#
# Revocation 4 lands here too. `is_admin` is cleared by the row write the
# phase-9b `admin revoke` command performs, exactly as the de-enrolment case
# above writes `app_user.org_id` directly.


def _admin_seed(engine: Engine, *, owner_id: str, admin_id: str) -> uuid.UUID:
    """Seed a **private** project in one organisation and an admin in another.

    Private, and cross-organisation, on purpose: every other leg is closed, so
    a stream that opens at all opened on `is_admin` and nothing else.

    Args:
        engine: The session engine; writes here commit, because the
            application reads through its own connection.
        owner_id: The project owner's subject, enrolled in organisation A.
        admin_id: The administrator's subject, enrolled in organisation B.

    Returns:
        The project the administrator will stream.
    """
    with seeded(engine) as conn:
        org_a = make_org(conn, name="Owner Org")
        org_b = make_org(conn, name="Support Org")
        ops_enrol(conn, user_id=owner_id, org_id=org_a, display_name="Owner")
        ops_enrol(
            conn,
            user_id=admin_id,
            org_id=org_b,
            display_name="Support",
            is_admin=True,
        )
        return make_project(
            conn, owner_user_id=owner_id, org_id=org_a, visibility="private"
        )


def test_an_administrator_stream_on_an_ownerless_project_survives_its_polls(
    engine: Engine, tmp_path: Path
) -> None:
    """The re-check must reach the rows only the admin leg reaches (contract § 11).

    A `runtime/orchestrate.py` project has no owner and no organisation, so an
    administrator is the only caller who can read it at all — and the own-leg
    boolean the re-check selects beside its answer is **SQL NULL** on such a
    row, because every disjunct of it compares a NULL column. Read through
    `scalar_one_or_none()` that NULL was indistinguishable from "no row", so
    this stream opened (the snapshot selects the row itself) and then closed as
    revoked on its very first re-authorisation.

    Two keep-alives is the assertion: the first proves the tail loop ran, the
    second proves it ran again with the grade intact. Nothing is revoked here.
    """

    async def exercise() -> None:
        async with _api_session(tmp_path, heartbeat_seconds=0.05) as api:
            with seeded(engine) as conn:
                ops_enrol(
                    conn,
                    user_id=api.other_id,
                    org_id=make_org(conn, name="Support Org"),
                    display_name="Support",
                    is_admin=True,
                )
                project_id = make_project(
                    conn, owner_user_id=None, org_id=None, visibility="org"
                )
            stream = await api.open_stream(project_id, headers=api.other_headers)
            try:
                await _live(stream)
                await _live(stream)
            finally:
                await stream.aclose()

    asyncio.run(exercise())


def test_sse_administrator_stream_traces_the_subscribe_and_every_reauthorisation(
    engine: Engine, tmp_path: Path, monkeypatch: Any
) -> None:
    """One `admin_read` at subscribe, then one `admin_stream_read` per batch.

    The grain assertion is made against the re-authorisations themselves
    rather than against a wall-clock count: `may_read_project` is wrapped to
    record every call the admin leg carried, and the number of
    `admin_stream_read` lines must equal it exactly. That is "one per
    re-authorisation batch" stated as an equality — a per-frame
    implementation, or a per-connection one, fails it in opposite directions.

    The subscribe line is deliberately *not* a fourth event name: it is a
    direct row read on the graded helper like any other, so it carries the
    same `admin_read` shape and the same project id.
    """

    carried: list[str] = []
    real = _access.may_read_project

    def recording(
        conn: Connection, *, project_id: uuid.UUID, user_id: str
    ) -> _access.ReadCheck:
        check = real(conn, project_id=project_id, user_id=user_id)
        if check.allowed and check.via_admin:
            carried.append(user_id)
        return check

    monkeypatch.setattr(sse, "may_read_project", recording)

    async def exercise() -> None:
        async with _api_session(tmp_path, heartbeat_seconds=0.05) as api:
            project_id = _admin_seed(
                engine, owner_id=api.owner_id, admin_id=api.other_id
            )
            with capture_logs() as captured:
                stream = await api.open_stream(project_id, headers=api.other_headers)
                try:
                    await _live(stream)
                    await _live(stream)
                finally:
                    await stream.aclose()
                batches = list(carried)
                lines = [
                    entry
                    for entry in captured
                    if entry.get("event") == "admin_stream_read"
                ]
                subscribes = [
                    entry for entry in captured if entry.get("event") == "admin_read"
                ]

            # The private, cross-organisation project opened at all, which is
            # the leg doing its job; and every re-check ran on the admin leg.
            assert batches
            assert set(batches) == {api.other_id}
            assert len(lines) == len(batches)
            assert {entry["row_id"] for entry in lines} == {str(project_id)}
            assert {entry["user_id"] for entry in lines} == {api.other_id}
            assert [(entry["kind"], entry["row_id"]) for entry in subscribes] == [
                ("project", str(project_id))
            ]

    asyncio.run(exercise())


def test_sse_stream_closes_when_the_administrators_flag_is_revoked(
    engine: Engine, tmp_path: Path
) -> None:
    """Revocation 4, for real. Clearing `is_admin` ends an open admin stream.

    The last of contract § 5's four revocation events, and the one phase 6
    could only pin structurally. The project is private and in another
    organisation, so the admin leg is the *only* thing holding the stream
    open — when the flag goes, there is nothing left to fall back to, and the
    tail's next re-authorisation ends the response.

    The owner's own stream on the same project is untouched by the same write,
    which is what makes this a statement about the leg rather than about the
    tail closing whenever anything is written.

    A tick published after the revoke must reach the owner and **not** the
    former administrator, for the reason `_colleague_stream_closes_when`
    documents: the revoked stream closing is the weaker half of the property,
    and one last frame on the way out is the half that leaks.
    """

    async def exercise() -> None:
        async with _api_session(tmp_path, heartbeat_seconds=0.05) as api:
            project_id = _admin_seed(
                engine, owner_id=api.owner_id, admin_id=api.other_id
            )
            owner_stream = await api.open_stream(project_id)
            admin_stream = await api.open_stream(project_id, headers=api.other_headers)
            try:
                await _live(owner_stream)
                await _live(admin_stream)
                with seeded(engine) as conn:
                    ops_set_admin(conn, user_id=api.other_id, is_admin=False)
                tick_hub.publish(
                    project_id, stage="acquire", note="After the revocation"
                )
                closed, drained = await admin_stream.drain_until_closed(timeout=5.0)
                assert closed
                assert _frames(drained) == []
                # The owner is still watching, and receives the same tick the
                # revoked administrator did not. Collected rather than read as
                # the next item: the owner's stream has been idling through
                # both `_live` waits, so keep-alives are queued ahead of it.
                owner_items = await owner_stream.collect_until(
                    lambda item: item.event == "tick", timeout=5.0
                )
                assert _frames(owner_items)[-1].event == "tick"
            finally:
                await owner_stream.aclose()
                await admin_stream.aclose()

    asyncio.run(exercise())
