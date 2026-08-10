"""NDJSON wire tests for chat-turn streaming and post-header failures."""

from __future__ import annotations

import json
import uuid
from typing import Any

import jwt
import pytest
from sqlalchemy.engine import Engine

from policy_atlas.api import chat_turns
from policy_atlas.api.deps import get_chat_backend, get_chat_embedding_backend
from policy_atlas.core.embeddings import StubEmbeddingBackend
from policy_atlas.runtime.chat_backend import StubChatBackend
from tests.api.resource_support import api_client
from tests.api.test_chat_turns import _chat, _citable_tools, _cleanup, _walk


class FailingChatBackend(StubChatBackend):
    """Stub whose answer emission fails after the NDJSON response has started."""

    def chat_turn(self, *args: Any, force_emit: bool, **kwargs: Any) -> Any:
        transcript = args[1] if len(args) > 1 else kwargs.get("transcript") or []
        if force_emit or transcript:
            raise RuntimeError("provider failed")
        return super().chat_turn(*args, force_emit=force_emit, **kwargs)


def _owner_id(headers: dict[str, str]) -> str:
    """Read the locally minted test subject without trusting it in production."""
    token = headers["Authorization"].removeprefix("Bearer ")
    return str(jwt.decode(token, options={"verify_signature": False})["sub"])


def _events(response: Any) -> list[dict[str, Any]]:
    """Decode the complete fetch-stream response as individual NDJSON records."""
    return [json.loads(line) for line in response.iter_lines() if line]


def test_turn_streams_progress_delta_and_one_completed_event(
    engine: Engine, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stub path emits the contract union and terminal durable payload."""
    project_id: uuid.UUID | None = None
    try:
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        with api_client(
            tmp_path,
            {
                get_chat_backend: StubChatBackend,
                get_chat_embedding_backend: StubEmbeddingBackend,
            },
        ) as (client, owner_headers, _):
            project_id, scope_id, conversation_id = _chat(engine, owner=_owner_id(owner_headers))
            _walk(engine, project_id=project_id, scope_id=scope_id, status="succeeded")
            response = client.post(
                f"/api/v1/conversations/{conversation_id}/turns",
                headers=owner_headers,
                json={
                    "message": "What does the evidence say?",
                    "client_turn_id": str(uuid.uuid4()),
                },
            )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/x-ndjson")
        events = _events(response)
        assert [event["type"] for event in events].count("completed") == 1
        assert events[0] == {"type": "progress", "label": "Searching the evidence…"}
        deltas = [event["text"] for event in events if event["type"] == "delta"]
        terminal = events[-1]
        assert terminal["type"] == "completed"
        assert terminal["turn"]["answer"] == "".join(deltas)
    finally:
        _cleanup(engine, project_id)


def test_turn_stream_failure_is_a_single_terminal_event(
    engine: Engine, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Provider errors after headers never become an HTTP error envelope."""
    project_id: uuid.UUID | None = None
    try:
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        with api_client(
            tmp_path,
            {
                get_chat_backend: FailingChatBackend,
                get_chat_embedding_backend: StubEmbeddingBackend,
            },
        ) as (client, owner_headers, _):
            project_id, scope_id, conversation_id = _chat(engine, owner=_owner_id(owner_headers))
            _walk(engine, project_id=project_id, scope_id=scope_id, status="succeeded")
            response = client.post(
                f"/api/v1/conversations/{conversation_id}/turns",
                headers=owner_headers,
                json={
                    "message": "What does the evidence say?",
                    "client_turn_id": str(uuid.uuid4()),
                },
            )
        events = _events(response)
        assert response.status_code == 200
        assert [event["type"] for event in events].count("failed") == 1
        assert events[-1]["type"] == "failed"
    finally:
        _cleanup(engine, project_id)
