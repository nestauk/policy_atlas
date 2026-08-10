"""Async grounding-judge enrichment coverage for durable chat turns."""

from __future__ import annotations

import copy
import threading
import uuid
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api import chat_enrichment, chat_turns
from policy_atlas.api.chat_enrichment import enrich_chat_turn
from policy_atlas.core.schema import chat_turn, source_snapshot
from policy_atlas.core.schema import chunk as chunk_table
from policy_atlas.evidence_base.synthesis.grounding_judge import StubGroundingJudgeBackend
from policy_atlas.runtime.chat_backend import StubChatBackend
from tests.api.test_chat_turns import _chat, _cleanup, _walk
from tests.helpers import now


class CountingJudge(StubGroundingJudgeBackend):
    """Stub judge that records calls without changing its deterministic verdicts."""

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def judge_block(self, envelope: dict[str, Any]) -> Any:
        self.calls += 1
        return super().judge_block(envelope)


class FailingJudge(CountingJudge):
    """Stub judge that fails every attempted call."""

    def judge_block(self, envelope: dict[str, Any]) -> Any:
        self.calls += 1
        raise RuntimeError("judge failure")


class BlockingJudge(CountingJudge):
    """Stub judge whose worker never completes inside a test timeout budget."""

    def __init__(self) -> None:
        super().__init__()
        self.gate = threading.Event()

    def judge_block(self, envelope: dict[str, Any]) -> Any:
        self.calls += 1
        self.gate.wait()
        return super().judge_block(envelope)


def _seed_chunk(engine: Engine) -> tuple[uuid.UUID, uuid.UUID]:
    """Create one frozen chunk suitable for a chat judge envelope."""
    snapshot_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            source_snapshot.insert().values(
                source_snapshot_id=snapshot_id,
                content_hash="chat-enrichment-source",
                text_basis="full_text",
                source_locator="test://chat-enrichment",
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
                content_hash="chat-enrichment-chunk",
                locator={},
                segmentation_policy="test_v1",
                created_at=now(),
            )
        )
    return snapshot_id, chunk_id


def _completed_turn(
    engine: Engine, *, enrichment_status: str = "pending"
) -> tuple[uuid.UUID, dict[str, Any]]:
    """Insert a completed cited chat turn and return its id and initial payload."""
    project_id, _scope_id, conversation_id = _chat(engine)
    snapshot_id, chunk_id = _seed_chunk(engine)
    prose = "Evidence text supports the answer.[1]"
    payload: dict[str, Any] = {
        "claims": [
            {
                "text": "Evidence text supports the answer.",
                "span": [0, len("Evidence text supports the answer.")],
                "citation_ns": [1],
            }
        ],
        "citations": [
            {
                "n": 1,
                "id": str(chunk_id),
                "kind": "chunk",
                "quote": "Evidence text supports the answer.",
                "state": "unchecked",
            }
        ],
        "enrichment": {"status": enrichment_status},
    }
    turn_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            chat_turn.insert().values(
                id=turn_id,
                conversation_id=conversation_id,
                turn_index=0,
                client_turn_id=uuid.uuid4(),
                user_message="What does the evidence say?",
                answer=prose,
                answer_payload=payload,
                capability_run_id=None,
                status="completed",
                created_at=now(),
                completed_at=now(),
            )
        )
    return project_id, {
        "turn_id": turn_id,
        "payload": payload,
        "conversation_id": conversation_id,
        "snapshot_id": snapshot_id,
    }


def _payload(engine: Engine, turn_id: uuid.UUID) -> dict[str, Any]:
    """Read a turn's JSON payload as an ordinary mutable dictionary."""
    with engine.connect() as conn:
        return dict(
            conn.execute(
                select(chat_turn.c.answer_payload).where(chat_turn.c.id == turn_id)
            ).scalar_one()
        )


def _cleanup_enrichment(
    engine: Engine, project_id: uuid.UUID | None, snapshot_id: uuid.UUID
) -> None:
    """Remove the detached frozen-source fixture as well as its project fixture."""
    with engine.begin() as conn:
        conn.execute(chunk_table.delete().where(chunk_table.c.source_snapshot_id == snapshot_id))
        conn.execute(
            source_snapshot.delete().where(source_snapshot.c.source_snapshot_id == snapshot_id)
        )
    _cleanup(engine, project_id)


def test_enrichment_attaches_verdicts_without_changing_prose_or_membership(engine: Engine) -> None:
    """A cited completed turn receives per-claim and per-citation judge verdicts."""
    project_id: uuid.UUID | None = None
    try:
        project_id, fixture = _completed_turn(engine)
        turn_id = fixture["turn_id"]
        initial = copy.deepcopy(fixture["payload"])

        enrich_chat_turn(engine, turn_id=turn_id, judge_backend=CountingJudge())

        payload = _payload(engine, turn_id)
        assert payload["claims"][0]["claim_id"] == "c1"
        assert payload["claims"][0]["verdict"] == "tier_1"
        assert payload["claims"][0]["weakly_grounded"] is False
        assert payload["claims"][0]["rationale"]
        assert payload["citations"][0]["state"] == "verdict:tier_1"
        assert payload["citations"][0]["verdict"] == "tier_1"
        assert payload["enrichment"]["status"] == "enriched"
        assert payload["enrichment"]["model_id"]
        assert payload["enrichment"]["prompt_version"]
        assert payload["enrichment"]["envelope_version"]
        assert {key: payload["claims"][0][key] for key in ("text", "span", "citation_ns")} == {
            key: initial["claims"][0][key] for key in ("text", "span", "citation_ns")
        }
        assert {key: payload["citations"][0][key] for key in ("n", "id", "kind", "quote")} == {
            key: initial["citations"][0][key] for key in ("n", "id", "kind", "quote")
        }
        with engine.connect() as conn:
            answer = conn.execute(
                select(chat_turn.c.answer).where(chat_turn.c.id == turn_id)
            ).scalar_one()
        assert answer == "Evidence text supports the answer.[1]"
    finally:
        _cleanup_enrichment(engine, project_id, fixture["snapshot_id"])


def test_judge_failure_is_terminal_unchecked_after_one_retry(engine: Engine) -> None:
    """Two judge failures leave a completed turn honestly unchecked."""
    project_id: uuid.UUID | None = None
    try:
        project_id, fixture = _completed_turn(engine)
        judge = FailingJudge()
        enrich_chat_turn(engine, turn_id=fixture["turn_id"], judge_backend=judge)
        payload = _payload(engine, fixture["turn_id"])
        assert judge.calls == 2
        assert payload["enrichment"]["status"] == "failed"
        assert payload["citations"][0]["state"] == "unchecked"
        with engine.connect() as conn:
            status = conn.execute(
                select(chat_turn.c.status).where(chat_turn.c.id == fixture["turn_id"])
            ).scalar_one()
        assert status == "completed"
    finally:
        _cleanup_enrichment(engine, project_id, fixture["snapshot_id"])


def test_judge_timeout_is_terminal_unchecked_after_one_retry(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Timed-out judge workers use the same terminal honesty path as failures."""
    project_id: uuid.UUID | None = None
    try:
        project_id, fixture = _completed_turn(engine)
        monkeypatch.setattr(chat_enrichment, "JUDGE_TIMEOUT_SECONDS", 0.01)
        judge = BlockingJudge()
        enrich_chat_turn(engine, turn_id=fixture["turn_id"], judge_backend=judge)
        payload = _payload(engine, fixture["turn_id"])
        assert judge.calls == 2
        assert payload["enrichment"]["status"] == "failed"
        assert payload["citations"][0]["state"] == "unchecked"
    finally:
        _cleanup_enrichment(engine, project_id, fixture["snapshot_id"])


def test_zero_citation_turn_is_not_judged(engine: Engine) -> None:
    """A not-applicable zero-citation payload never reaches the judge seam."""
    project_id: uuid.UUID | None = None
    try:
        project_id, fixture = _completed_turn(engine)
        turn_id = fixture["turn_id"]
        with engine.begin() as conn:
            conn.execute(
                chat_turn.update()
                .where(chat_turn.c.id == turn_id)
                .values(
                    answer_payload={
                        "claims": [],
                        "citations": [],
                        "enrichment": {"status": "not_applicable"},
                    }
                )
            )
        judge = CountingJudge()
        enrich_chat_turn(engine, turn_id=turn_id, judge_backend=judge)
        assert judge.calls == 0
        assert _payload(engine, turn_id)["enrichment"]["status"] == "not_applicable"
    finally:
        _cleanup_enrichment(engine, project_id, fixture["snapshot_id"])


def test_cas_loser_never_calls_the_judge(engine: Engine) -> None:
    """An already enriched payload is a no-op rather than a duplicate judge call."""
    project_id: uuid.UUID | None = None
    try:
        project_id, fixture = _completed_turn(engine, enrichment_status="enriched")
        judge = CountingJudge()
        enrich_chat_turn(engine, turn_id=fixture["turn_id"], judge_backend=judge)
        assert judge.calls == 0
        assert _payload(engine, fixture["turn_id"])["enrichment"]["status"] == "enriched"
    finally:
        _cleanup_enrichment(engine, project_id, fixture["snapshot_id"])


def test_replay_preserves_an_enriched_payload(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Idempotent service replay returns the exact payload written by enrichment."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, project_id=project_id, scope_id=scope_id, status="succeeded")
        snapshot_id, chunk_id = _seed_chunk(engine)
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
        client_turn_id = uuid.uuid4()
        first = chat_turns.run_chat_turn(
            engine,
            project_id=project_id,
            conversation_id=conversation_id,
            user_id="chat-owner",
            message="What does the evidence say?",
            client_turn_id=client_turn_id,
            chat_backend=StubChatBackend(),
        )
        enrich_chat_turn(engine, turn_id=first.id, judge_backend=CountingJudge())
        enriched = _payload(engine, first.id)
        replay = chat_turns.run_chat_turn(
            engine,
            project_id=project_id,
            conversation_id=conversation_id,
            user_id="chat-owner",
            message="What does the evidence say?",
            client_turn_id=client_turn_id,
            chat_backend=StubChatBackend(),
        )
        assert replay.replayed is True
        assert replay.answer_payload == enriched
    finally:
        if "snapshot_id" in locals():
            _cleanup_enrichment(engine, project_id, snapshot_id)
        else:
            _cleanup(engine, project_id)
