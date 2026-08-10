"""NDJSON wire tests for chat-turn streaming and post-header failures."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import jwt
import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api import chat_turns
from policy_atlas.api.deps import (
    get_chat_backend,
    get_chat_embedding_backend,
    get_grounding_judge_backend,
)
from policy_atlas.core.embeddings import StubEmbeddingBackend
from policy_atlas.core.schema import chat_turn, source_snapshot
from policy_atlas.core.schema import chunk as chunk_table
from policy_atlas.evidence_base.synthesis.grounding_judge import StubGroundingJudgeBackend
from policy_atlas.runtime.chat_backend import StubChatBackend
from tests.api.resource_support import api_client
from tests.api.test_chat_turns import _chat, _citable_tools, _cleanup, _walk
from tests.helpers import now


class FailingChatBackend(StubChatBackend):
    """Stub whose answer emission fails after the NDJSON response has started."""

    def chat_turn(self, *args: Any, force_emit: bool, **kwargs: Any) -> Any:
        transcript = args[1] if len(args) > 1 else kwargs.get("transcript") or []
        if force_emit or transcript:
            raise RuntimeError("provider failed")
        return super().chat_turn(*args, force_emit=force_emit, **kwargs)


class CountingJudge(StubGroundingJudgeBackend):
    """Judge stub used to prove the stream trigger runs asynchronously."""

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def judge_block(self, envelope: dict[str, Any]) -> Any:
        self.calls += 1
        return super().judge_block(envelope)


def _stream_chunk(engine: Engine) -> tuple[uuid.UUID, uuid.UUID]:
    """Create a frozen chunk whose id can survive the post-stream judge read."""
    snapshot_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            source_snapshot.insert().values(
                source_snapshot_id=snapshot_id,
                content_hash="chat-stream-enrichment-source",
                text_basis="full_text",
                source_locator="test://chat-stream-enrichment",
                metadata={},
                created_at=now(),
            )
        )
        conn.execute(
            chunk_table.insert().values(
                chunk_id=chunk_id,
                source_snapshot_id=snapshot_id,
                sequence=0,
                content="Evidence text supports the answer.",
                content_hash="chat-stream-enrichment-chunk",
                locator={},
                segmentation_policy="test_v1",
                created_at=now(),
            )
        )
    return snapshot_id, chunk_id


def _cleanup_stream_chunk(engine: Engine, snapshot_id: uuid.UUID) -> None:
    """Delete the detached frozen-source fixture after an endpoint test."""
    with engine.begin() as conn:
        conn.execute(chunk_table.delete().where(chunk_table.c.source_snapshot_id == snapshot_id))
        conn.execute(
            source_snapshot.delete().where(source_snapshot.c.source_snapshot_id == snapshot_id)
        )


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


def test_completed_stream_triggers_async_judge_enrichment(
    engine: Engine, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The completed NDJSON event is emitted without waiting for judge enrichment."""
    project_id: uuid.UUID | None = None
    snapshot_id: uuid.UUID | None = None
    try:
        snapshot_id, chunk_id = _stream_chunk(engine)
        judge = CountingJudge()
        monkeypatch.setattr(
            chat_turns,
            "build_section_tools",
            lambda **_: {
                "search_chunks": lambda _arguments: {
                    "chunks": [
                        {
                            "chunk_record_id": str(chunk_id),
                            "content": "Evidence text supports the answer.",
                            "appraised": True,
                        }
                    ]
                },
                "query_findings": lambda _arguments: {"findings": []},
                "lookup": lambda _arguments: {"result": {}},
            },
        )
        with api_client(
            tmp_path,
            {
                get_chat_backend: StubChatBackend,
                get_chat_embedding_backend: StubEmbeddingBackend,
                get_grounding_judge_backend: lambda: judge,
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
            terminal = events[-1]
            assert terminal["type"] == "completed"
            assert terminal["turn"]["enrichment"] == {"status": "pending"}
            turn_id = uuid.UUID(terminal["turn"]["id"])
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                with engine.connect() as conn:
                    payload = conn.execute(
                        select(chat_turn.c.answer_payload).where(chat_turn.c.id == turn_id)
                    ).scalar_one()
                if payload["enrichment"]["status"] == "enriched":
                    break
                time.sleep(0.01)
        assert judge.calls == 1
        assert payload["enrichment"]["status"] == "enriched"
        assert payload["citations"][0]["state"] == "verdict:tier_1"
    finally:
        if snapshot_id is not None:
            _cleanup_stream_chunk(engine, snapshot_id)
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
