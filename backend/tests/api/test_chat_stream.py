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
from policy_atlas.api.app import ApiCapacity, ApiConflict
from policy_atlas.api.deps import (
    get_chat_backend,
    get_chat_embedding_backend,
    get_grounding_judge_backend,
)
from policy_atlas.api.routers import conversations as conversations_router
from policy_atlas.core.embeddings import StubEmbeddingBackend
from policy_atlas.core.schema import chat_turn, source_snapshot, task_source_snapshot
from policy_atlas.core.schema import chunk as chunk_table
from policy_atlas.evidence_search.synthesis.grounding_judge import StubGroundingJudgeBackend
from policy_atlas.runtime.chat_backend import StubChatBackend
from tests.api.resource_support import api_client
from tests.api.test_chat_turns import _chat, _citable_tools, _cleanup, _insert_pending_turn, _walk
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


def _stream_chunk(engine: Engine, task_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """Create a frozen chunk, ingested into ``task_id``, that survives the judge read.

    The task_source_snapshot row matters: enrichment's evidence reads are
    task-scoped (review-stack hardening), so a chunk without one resolves
    as missing — exactly like production chunks that always arrive via ingest.
    """
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
            task_source_snapshot.insert().values(
                task_source_snapshot_id=uuid.uuid4(),
                task_id=task_id,
                source_snapshot_id=snapshot_id,
                origin="uploaded",
                run_id=None,
                ingested_at=now(),
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
            task_source_snapshot.delete().where(
                task_source_snapshot.c.source_snapshot_id == snapshot_id
            )
        )
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
    task_id: uuid.UUID | None = None
    try:
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        with api_client(
            tmp_path,
            {
                get_chat_backend: StubChatBackend,
                get_chat_embedding_backend: StubEmbeddingBackend,
            },
        ) as (client, owner_headers, _):
            task_id, scope_id, conversation_id = _chat(engine, owner=_owner_id(owner_headers))
            _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
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
        _cleanup(engine, task_id)


def test_completed_stream_triggers_async_judge_enrichment(
    engine: Engine, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The completed NDJSON event is emitted without waiting for judge enrichment."""
    task_id: uuid.UUID | None = None
    snapshot_id: uuid.UUID | None = None
    try:
        judge = CountingJudge()
        with api_client(
            tmp_path,
            {
                get_chat_backend: StubChatBackend,
                get_chat_embedding_backend: StubEmbeddingBackend,
                get_grounding_judge_backend: lambda: judge,
            },
        ) as (client, owner_headers, _):
            task_id, scope_id, conversation_id = _chat(engine, owner=_owner_id(owner_headers))
            _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
            # Seed after the task exists: enrichment's evidence reads are
            # task-scoped, so the cited chunk must be ingested into it.
            snapshot_id, chunk_id = _stream_chunk(engine, task_id)
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
        _cleanup(engine, task_id)


def test_turn_stream_failure_is_a_single_terminal_event(
    engine: Engine, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Provider errors after headers never become an HTTP error envelope."""
    task_id: uuid.UUID | None = None
    try:
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        with api_client(
            tmp_path,
            {
                get_chat_backend: FailingChatBackend,
                get_chat_embedding_backend: StubEmbeddingBackend,
            },
        ) as (client, owner_headers, _):
            task_id, scope_id, conversation_id = _chat(engine, owner=_owner_id(owner_headers))
            _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
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
        _cleanup(engine, task_id)


def test_replay_of_completed_turn_over_the_stream_is_a_single_completed_event(
    engine: Engine, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Retrying a completed turn's client_turn_id replays once, with no deltas."""
    task_id: uuid.UUID | None = None
    try:
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        with api_client(
            tmp_path,
            {
                get_chat_backend: StubChatBackend,
                get_chat_embedding_backend: StubEmbeddingBackend,
            },
        ) as (client, owner_headers, _):
            task_id, scope_id, conversation_id = _chat(engine, owner=_owner_id(owner_headers))
            _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
            body = {
                "message": "What does the evidence say?",
                "client_turn_id": str(uuid.uuid4()),
            }
            first = client.post(
                f"/api/v1/conversations/{conversation_id}/turns",
                headers=owner_headers,
                json=body,
            )
            first_turn_id = _events(first)[-1]["turn"]["id"]

            replay = client.post(
                f"/api/v1/conversations/{conversation_id}/turns",
                headers=owner_headers,
                json=body,
            )
        assert replay.status_code == 200
        replay_events = _events(replay)
        assert len(replay_events) == 1
        assert replay_events[0]["type"] == "completed"
        assert replay_events[0]["turn"]["id"] == first_turn_id
    finally:
        _cleanup(engine, task_id)


def test_pre_header_envelope_errors_are_json_not_ndjson(
    engine: Engine, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reservation-time failures use the standard JSON error envelope, not the stream."""
    task_id: uuid.UUID | None = None
    cap_task_ids: list[uuid.UUID] = []
    try:
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        with api_client(
            tmp_path,
            {
                get_chat_backend: StubChatBackend,
                get_chat_embedding_backend: StubEmbeddingBackend,
            },
        ) as (client, owner_headers, _):
            owner = _owner_id(owner_headers)

            unknown = client.post(
                f"/api/v1/conversations/{uuid.uuid4()}/turns",
                headers=owner_headers,
                json={"message": "Hello", "client_turn_id": str(uuid.uuid4())},
            )
            assert unknown.status_code == 404
            assert unknown.headers["content-type"].startswith("application/json")
            assert unknown.json()["error"]["code"] == "not_found"

            task_id, _scope_id, conversation_id = _chat(engine, owner=owner)
            no_run = client.post(
                f"/api/v1/conversations/{conversation_id}/turns",
                headers=owner_headers,
                json={"message": "Hello", "client_turn_id": str(uuid.uuid4())},
            )
            assert no_run.status_code == 409
            assert no_run.headers["content-type"].startswith("application/json")
            assert no_run.json()["error"]["code"] == "no_completed_run"

            cap_task_a, _scope_a, conv_a = _chat(engine, owner=owner)
            cap_task_b, _scope_b, conv_b = _chat(engine, owner=owner)
            cap_task_ids = [cap_task_a, cap_task_b]
            _insert_pending_turn(engine, conversation_id=conv_a)
            _insert_pending_turn(engine, conversation_id=conv_b)
            cap_task_c, scope_c, conv_c = _chat(engine, owner=owner)
            cap_task_ids.append(cap_task_c)
            _walk(engine, task_id=cap_task_c, scope_id=scope_c, status="succeeded")
            capacity = client.post(
                f"/api/v1/conversations/{conv_c}/turns",
                headers=owner_headers,
                json={"message": "Hello", "client_turn_id": str(uuid.uuid4())},
            )
            assert capacity.status_code == 429
            assert capacity.headers["content-type"].startswith("application/json")
            assert capacity.json()["error"]["code"] == "chat_capacity"
    finally:
        _cleanup(engine, task_id)
        for cap_task_id in cap_task_ids:
            _cleanup(engine, cap_task_id)


def _always_run_active(*_args: Any, **_kwargs: Any) -> Any:
    """Simulate a capability run starting between route reservation and worker start."""
    raise ApiConflict("run_active", "finish the active run before starting a chat turn")


def test_worker_side_reservation_conflict_fails_the_reserved_row(
    engine: Engine, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pre-try worker conflict CASes the reserved row to failed, not left pending."""
    task_id: uuid.UUID | None = None
    try:
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        # Patches only chat_turns' own module-global lookup of _phase_one_turn,
        # which is what run_chat_turn's internal (worker-side) re-entry call
        # resolves at call time. The route's own reservation call above uses
        # a name bound at import time in conversations.py and is unaffected,
        # so the route still reserves the row normally before the worker's
        # re-entry call fails.
        monkeypatch.setattr(chat_turns, "_phase_one_turn", _always_run_active)
        with api_client(
            tmp_path,
            {
                get_chat_backend: StubChatBackend,
                get_chat_embedding_backend: StubEmbeddingBackend,
            },
        ) as (client, owner_headers, _):
            task_id, scope_id, conversation_id = _chat(engine, owner=_owner_id(owner_headers))
            _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
            response = client.post(
                f"/api/v1/conversations/{conversation_id}/turns",
                headers=owner_headers,
                json={"message": "Question", "client_turn_id": str(uuid.uuid4())},
            )
            events = _events(response)
            terminal = events[-1]
            assert terminal["type"] == "failed"
            turn_id = uuid.UUID(terminal["turn_id"])
            with engine.connect() as conn:
                status = conn.execute(
                    select(chat_turn.c.status).where(chat_turn.c.id == turn_id)
                ).scalar_one()
            assert status == "failed"
    finally:
        _cleanup(engine, task_id)


def test_capacity_failure_at_cancel_registration_rolls_back_the_reservation(
    engine: Engine, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A saturated cancel registry leaves no pending row behind."""
    task_id: uuid.UUID | None = None
    try:
        monkeypatch.setattr(
            conversations_router,
            "_register_cancel",
            lambda _turn_id: (_ for _ in ()).throw(
                ApiCapacity("chat_capacity", "too many chat turns are in progress")
            ),
        )
        with api_client(
            tmp_path,
            {
                get_chat_backend: StubChatBackend,
                get_chat_embedding_backend: StubEmbeddingBackend,
            },
        ) as (client, owner_headers, _):
            task_id, scope_id, conversation_id = _chat(engine, owner=_owner_id(owner_headers))
            _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
            response = client.post(
                f"/api/v1/conversations/{conversation_id}/turns",
                headers=owner_headers,
                json={"message": "Question", "client_turn_id": str(uuid.uuid4())},
            )
            assert response.status_code == 429
            assert response.json()["error"]["code"] == "chat_capacity"
            with engine.connect() as conn:
                remaining = conn.execute(
                    select(chat_turn.c.id).where(chat_turn.c.conversation_id == conversation_id)
                ).all()
            assert remaining == []
    finally:
        _cleanup(engine, task_id)
