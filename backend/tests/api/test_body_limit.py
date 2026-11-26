"""The request body size limit, through the real app and at the middleware."""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from starlette.types import Message, Receive, Scope, Send

from policy_atlas.api.app import create_app
from policy_atlas.api.body_limit import DEFAULT_LIMIT, BodyLimitMiddleware, _BodyTooLarge
from policy_atlas.api.dev_issuer import init
from policy_atlas.api.settings import Settings
from tests.api.resource_support import api_client

ORIGIN = "http://app.example.test"
TOO_BIG = b"x" * (DEFAULT_LIMIT + 1)


def _assert_too_large(response: httpx.Response) -> None:
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_a_declared_body_over_the_limit_is_refused_before_sign_in_with_cors_headers(
    tmp_path: Path, engine: Engine
) -> None:
    del engine
    with api_client(tmp_path) as (client, _owner, _other):
        response = client.post(
            "/api/v1/waitlist",
            content=TOO_BIG,
            headers={"Content-Type": "application/json", "Origin": ORIGIN},
        )
    _assert_too_large(response)
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert response.headers["x-content-type-options"] == "nosniff"


def test_a_streamed_body_over_the_limit_is_refused_and_a_small_one_passes(
    tmp_path: Path, engine: Engine
) -> None:
    del engine

    def chunks() -> Iterator[bytes]:
        for _ in range(3):
            yield b"x" * (DEFAULT_LIMIT // 2)

    with api_client(tmp_path) as (client, _owner, _other):
        streamed = client.post(
            "/api/v1/waitlist", content=chunks(), headers={"Content-Type": "application/json"}
        )
        small = client.post(
            "/api/v1/waitlist",
            json={
                "email": f"limit-{uuid.uuid4().hex[:12]}@example.com",
                "name": "Small Body",
                "role_or_reason": "A normal request",
            },
        )
    assert "content-length" not in streamed.request.headers
    _assert_too_large(streamed)
    assert small.status_code == 201, small.text


def test_only_a_post_to_the_exact_upload_path_gets_the_larger_limit(
    tmp_path: Path, engine: Engine
) -> None:
    del engine
    task_id = uuid.uuid4()
    two_megabytes = b"x" * 2_000_000
    with api_client(tmp_path) as (client, _owner, _other):
        upload = client.post(f"/api/v1/tasks/{task_id}/toc/uploads", content=two_megabytes)
        lookalike = client.post(
            f"/api/v1/tasks/{task_id}/toc/uploads/extra", content=two_megabytes
        )
        wrong_method = client.request(
            "GET", f"/api/v1/tasks/{task_id}/toc/uploads", content=two_megabytes
        )
    # The real upload route reads past the limit and reaches sign-in.
    assert upload.status_code == 401
    _assert_too_large(lookalike)
    _assert_too_large(wrong_method)


def test_the_ops_app_refuses_a_body_over_the_limit(tmp_path: Path, engine: Engine) -> None:
    del engine
    settings = Settings(
        "http://dev-issuer.local",
        "body-limit-test",
        None,
        init(tmp_path / "issuer"),
        ORIGIN,
        os.environ["DATABASE_URL"],
        service_role="ops",
        ops_ui_dir=None,
    )
    with TestClient(create_app(settings=settings), raise_server_exceptions=False) as client:
        response = client.post("/api/v1/ops/organisations", content=TOO_BIG)
    _assert_too_large(response)


def test_the_app_is_not_called_when_the_declared_length_is_over_the_limit() -> None:
    calls = 0

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal calls
        calls += 1

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": True}

    async def send(message: Message) -> None:
        del message

    scope: Scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/waitlist",
        "headers": [(b"content-length", str(DEFAULT_LIMIT + 1).encode())],
    }
    asyncio.run(BodyLimitMiddleware(app)(scope, receive, send))
    assert calls == 0


def test_a_body_that_arrives_in_several_messages_is_counted_as_one() -> None:
    chunk = b"x" * (DEFAULT_LIMIT // 2)
    body_seen = 0

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal body_seen
        while (message := await receive())["type"] == "http.request":
            body_seen += len(message["body"])
        # What an app does when the client has gone: it tries to reply anyway.
        await send({"type": "http.response.start", "status": 400, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def receive() -> Message:
        return {"type": "http.request", "body": chunk, "more_body": True}

    sent: list[Message] = []

    async def send(message: Message) -> None:
        sent.append(message)

    scope: Scope = {"type": "http", "method": "POST", "path": "/api/v1/waitlist", "headers": []}
    asyncio.run(BodyLimitMiddleware(app)(scope, receive, send))

    assert body_seen == 2 * len(chunk)
    assert [message["status"] for message in sent if "status" in message] == [413]


def test_a_reply_that_had_started_is_cut_off_with_an_error_not_ended_as_complete() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        while (await receive())["type"] == "http.request":
            pass
        await send({"type": "http.response.body", "body": b"the rest"})

    async def receive() -> Message:
        return {"type": "http.request", "body": TOO_BIG, "more_body": True}

    sent: list[Message] = []

    async def send(message: Message) -> None:
        sent.append(message)

    scope: Scope = {"type": "http", "method": "POST", "path": "/api/v1/waitlist", "headers": []}
    with pytest.raises(_BodyTooLarge):
        asyncio.run(BodyLimitMiddleware(app)(scope, receive, send))

    assert [message["type"] for message in sent] == ["http.response.start"]
