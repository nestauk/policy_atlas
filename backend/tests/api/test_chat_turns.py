"""Durable service coverage for the Phase C chat-turn engine."""

from __future__ import annotations

import threading
import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.engine import Engine

from policy_atlas.api import chat_turns
from policy_atlas.api.app import ApiCapacity, ApiConflict
from policy_atlas.core.schema import capability_run, chat_turn, conversation, project
from policy_atlas.evidence_base.synthesis.synthesis_tools import build_section_tools
from policy_atlas.runtime.chat_backend import StubChatBackend
from tests.helpers import now
from tests.runtime.test_runner import _cleanup as _cleanup
from tests.runtime.test_runner import _seed_project as _seed_project


class CountingChatBackend(StubChatBackend):
    """Stub backend that exposes duplicate generation through a call count."""

    def __init__(self) -> None:
        self.calls = 0

    def chat_turn(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        return super().chat_turn(*args, **kwargs)


class OutputCappedChatBackend(CountingChatBackend):
    """Counting stub whose adapter-compatible signature records output caps."""

    def __init__(self) -> None:
        super().__init__()
        self.output_caps: list[int | None] = []

    def chat_turn(self, *args: Any, max_output_tokens: int | None = None, **kwargs: Any) -> Any:
        self.output_caps.append(max_output_tokens)
        return super().chat_turn(*args, **kwargs)


class CancellingChatBackend(StubChatBackend):
    """Stub that asks the caller to stop after its first visible prose fragment."""

    def chat_turn(self, *args: Any, on_delta: Any = None, **kwargs: Any) -> Any:
        transcript = args[1] if len(args) > 1 else kwargs.get("transcript") or []
        if transcript and on_delta is not None:
            on_delta("Partial answer")
        return super().chat_turn(*args, on_delta=on_delta, **kwargs)


def _chat(engine: Engine, *, owner: str = "chat-owner") -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Create an owned active chat over a project fixture."""
    project_id, scope_id = _seed_project(engine)
    conversation_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            update(project).where(project.c.project_id == project_id).values(owner_user_id=owner)
        )
        conn.execute(
            conversation.insert().values(
                id=conversation_id,
                project_id=project_id,
                kind="chat",
                title="New chat",
                entry_artefact_id=None,
                status="active",
                created_at=now(),
                closed_at=None,
                archived_at=None,
            )
        )
    return project_id, scope_id, conversation_id


def _walk(engine: Engine, *, project_id: uuid.UUID, scope_id: uuid.UUID, status: str) -> None:
    """Persist the minimal capability-walk eligibility fixture."""
    with engine.begin() as conn:
        conn.execute(
            capability_run.insert().values(
                capability_run_id=uuid.uuid4(),
                project_id=project_id,
                evidence_scope_id=scope_id,
                capability="evidence_base",
                plan_id=uuid.uuid4(),
                plan_version=1,
                status=status,
                started_at=now(),
                ended_at=now() if status in {"succeeded", "degraded"} else None,
            )
        )


def _citable_tools(**_: Any) -> dict[str, Any]:
    """Provide a deterministic appraised chunk without widening the real tool set."""
    return {
        "search_chunks": lambda _arguments: {
            "chunks": [
                {
                    "chunk_record_id": "test-chunk",
                    "content": "Evidence text.",
                    "appraised": True,
                }
            ]
        },
        "query_findings": lambda _arguments: {"findings": []},
        "lookup": lambda _arguments: {"result": {}},
    }


def test_stub_turn_completes_durably_and_replays(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A completed idempotent turn is read back verbatim without regeneration."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, project_id=project_id, scope_id=scope_id, status="succeeded")
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        backend = OutputCappedChatBackend()
        turn_id = uuid.uuid4()
        first = chat_turns.run_chat_turn(
            engine,
            project_id=project_id,
            conversation_id=conversation_id,
            user_id="chat-owner",
            message="What does the evidence say?",
            client_turn_id=turn_id,
            chat_backend=backend,
        )
        replay = chat_turns.run_chat_turn(
            engine,
            project_id=project_id,
            conversation_id=conversation_id,
            user_id="chat-owner",
            message="What does the evidence say?",
            client_turn_id=turn_id,
            chat_backend=backend,
        )
        assert first.status == "completed"
        assert first.answer_payload is not None
        assert first.answer_payload["citations"][0]["id"] == "test-chunk"
        assert first.answer_payload["model_id"]
        assert first.answer_payload["prompt_version"] == "chat_v1"
        assert first.answer_payload["trace_id"] is None
        assert replay.replayed is True
        assert replay.answer_payload == first.answer_payload
        assert backend.calls == 2
        assert backend.output_caps == [4096, 4096]
        with engine.connect() as conn:
            durable = (
                conn.execute(select(chat_turn).where(chat_turn.c.id == first.id)).mappings().one()
            )
            title = conn.execute(
                select(conversation.c.title).where(conversation.c.id == conversation_id)
            ).scalar_one()
        assert durable["answer_payload"] == first.answer_payload
        assert title == "What does the evidence say?"
    finally:
        _cleanup(engine, project_id)


@pytest.mark.parametrize(
    ("walk_status", "code"), [(None, "no_completed_run"), ("running", "run_active")]
)
def test_turn_requires_completed_run(engine: Engine, walk_status: str | None, code: str) -> None:
    """Missing completion and an active walk produce named eligibility conflicts."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id, conversation_id = _chat(engine)
        if walk_status is not None:
            _walk(engine, project_id=project_id, scope_id=scope_id, status=walk_status)
        with pytest.raises(ApiConflict) as raised:
            chat_turns.run_chat_turn(
                engine,
                project_id=project_id,
                conversation_id=conversation_id,
                user_id="chat-owner",
                message="Question",
                client_turn_id=uuid.uuid4(),
                chat_backend=StubChatBackend(),
            )
        assert raised.value.code == code
    finally:
        _cleanup(engine, project_id)


def test_active_walk_fences_chat(engine: Engine) -> None:
    """A running walk wins over an older completed walk at reservation time."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, project_id=project_id, scope_id=scope_id, status="succeeded")
        _walk(engine, project_id=project_id, scope_id=scope_id, status="running")
        with pytest.raises(ApiConflict) as raised:
            chat_turns.run_chat_turn(
                engine,
                project_id=project_id,
                conversation_id=conversation_id,
                user_id="chat-owner",
                message="Question",
                client_turn_id=uuid.uuid4(),
                chat_backend=StubChatBackend(),
            )
        assert raised.value.code == "run_active"
    finally:
        _cleanup(engine, project_id)


def test_stale_pending_is_failed_before_reservation(engine: Engine) -> None:
    """A ten-minute-old pending row no longer blocks a new turn."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, project_id=project_id, scope_id=scope_id, status="succeeded")
        with engine.begin() as conn:
            conn.execute(
                chat_turn.insert().values(
                    id=uuid.uuid4(),
                    conversation_id=conversation_id,
                    turn_index=0,
                    client_turn_id=uuid.uuid4(),
                    user_message="old",
                    answer=None,
                    answer_payload=None,
                    capability_run_id=None,
                    status="pending",
                    created_at=now() - timedelta(minutes=11),
                    completed_at=None,
                )
            )
            reserved = chat_turns._phase_one_turn(
                conn,
                project_id=project_id,
                conversation_id=conversation_id,
                user_id="chat-owner",
                message="new",
                client_turn_id=uuid.uuid4(),
            )
            assert isinstance(reserved, uuid.UUID)
            statuses = (
                conn.execute(
                    select(chat_turn.c.status).where(chat_turn.c.conversation_id == conversation_id)
                )
                .scalars()
                .all()
            )
        assert sorted(statuses) == ["failed", "pending"]
    finally:
        _cleanup(engine, project_id)


def test_chat_tool_allowlist_is_closed() -> None:
    """The chat construction point exposes exactly the three read-only tools."""
    tools = build_section_tools(
        retriever=object(),  # type: ignore[arg-type]
        findings_reader=lambda _arguments: {"findings": []},
        lookup_reader=lambda _arguments: {"result": {}},
    )
    assert set(tools) == {"search_chunks", "query_findings", "lookup"}


def test_explicit_cancel_keeps_partial_prose_without_citations(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cancel observed between deltas commits the partial with the stopped marker."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, project_id=project_id, scope_id=scope_id, status="succeeded")
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        cancel = threading.Event()
        result = chat_turns.run_chat_turn(
            engine,
            project_id=project_id,
            conversation_id=conversation_id,
            user_id="chat-owner",
            message="Question",
            client_turn_id=uuid.uuid4(),
            chat_backend=CancellingChatBackend(),
            cancel_event=cancel,
            on_delta=lambda _text: cancel.set(),
        )
        assert result.status == "cancelled"
        assert result.answer == "Partial answer"
        assert result.answer_payload == {
            "claims": [],
            "citations": [],
            "warning_not_evidence_checked": False,
            "handoff": None,
            "stopped_before_evidence_check": True,
        }
    finally:
        _cleanup(engine, project_id)


def _second_chat_in_same_project(engine: Engine, project_id: uuid.UUID) -> uuid.UUID:
    """Insert an additional active chat conversation onto an existing project."""
    conversation_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            conversation.insert().values(
                id=conversation_id,
                project_id=project_id,
                kind="chat",
                title="New chat",
                entry_artefact_id=None,
                status="active",
                created_at=now(),
                closed_at=None,
                archived_at=None,
            )
        )
    return conversation_id


def _insert_pending_turn(engine: Engine, *, conversation_id: uuid.UUID) -> None:
    """Insert a fresh (non-stale) pending chat_turn row directly."""
    with engine.begin() as conn:
        conn.execute(
            chat_turn.insert().values(
                id=uuid.uuid4(),
                conversation_id=conversation_id,
                turn_index=0,
                client_turn_id=uuid.uuid4(),
                user_message="in flight",
                answer=None,
                answer_payload=None,
                capability_run_id=None,
                status="pending",
                created_at=now(),
                completed_at=None,
            )
        )


class FailOnceChatBackend(StubChatBackend):
    """Stub backend whose first call raises; later calls behave like the stub."""

    def __init__(self) -> None:
        self.calls = 0

    def chat_turn(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("stub chat failure")
        return super().chat_turn(*args, **kwargs)


class AlwaysFailsChatBackend(StubChatBackend):
    """Stub backend that always raises, used to fail exactly one turn."""

    def chat_turn(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("stub chat failure")


class BlockingChatBackend(StubChatBackend):
    """Stub backend whose first tool-call turn blocks on a per-instance gate."""

    def __init__(self, gate: threading.Event, *, started: threading.Event | None = None) -> None:
        self.gate = gate
        self.started = started

    def chat_turn(
        self,
        messages: list[dict[str, str]],
        transcript: list[Any],
        *,
        force_emit: bool,
        max_output_tokens: int | None = None,
        **kwargs: Any,
    ) -> Any:
        if not transcript and not force_emit:
            if self.started is not None:
                self.started.set()
            self.gate.wait(timeout=5)
        return super().chat_turn(
            messages,
            transcript,
            force_emit=force_emit,
            max_output_tokens=max_output_tokens,
            **kwargs,
        )


def test_failed_turn_retries_in_place(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed turn keeps its row; retrying with the same ids completes it in place."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, project_id=project_id, scope_id=scope_id, status="succeeded")
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        backend = FailOnceChatBackend()
        turn_id = uuid.uuid4()
        message = "What does the evidence say?"
        with pytest.raises(RuntimeError):
            chat_turns.run_chat_turn(
                engine,
                project_id=project_id,
                conversation_id=conversation_id,
                user_id="chat-owner",
                message=message,
                client_turn_id=turn_id,
                chat_backend=backend,
            )
        with engine.connect() as conn:
            failed_row = (
                conn.execute(select(chat_turn).where(chat_turn.c.client_turn_id == turn_id))
                .mappings()
                .one()
            )
        assert failed_row["status"] == "failed"

        retried = chat_turns.run_chat_turn(
            engine,
            project_id=project_id,
            conversation_id=conversation_id,
            user_id="chat-owner",
            message=message,
            client_turn_id=turn_id,
            chat_backend=backend,
        )
        assert retried.status == "completed"
        assert retried.replayed is False
        assert retried.id == failed_row["id"]
        assert retried.turn_index == failed_row["turn_index"]
    finally:
        _cleanup(engine, project_id)


def test_retry_of_non_latest_failed_turn_is_stale(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the latest chat turn may be retried; an older failed turn is stale."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, project_id=project_id, scope_id=scope_id, status="succeeded")
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        turn_a, turn_b, turn_c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

        chat_turns.run_chat_turn(
            engine,
            project_id=project_id,
            conversation_id=conversation_id,
            user_id="chat-owner",
            message="Question one",
            client_turn_id=turn_a,
            chat_backend=StubChatBackend(),
        )
        with pytest.raises(RuntimeError):
            chat_turns.run_chat_turn(
                engine,
                project_id=project_id,
                conversation_id=conversation_id,
                user_id="chat-owner",
                message="Question two",
                client_turn_id=turn_b,
                chat_backend=AlwaysFailsChatBackend(),
            )
        chat_turns.run_chat_turn(
            engine,
            project_id=project_id,
            conversation_id=conversation_id,
            user_id="chat-owner",
            message="Question three",
            client_turn_id=turn_c,
            chat_backend=StubChatBackend(),
        )

        with pytest.raises(ApiConflict) as raised:
            chat_turns.run_chat_turn(
                engine,
                project_id=project_id,
                conversation_id=conversation_id,
                user_id="chat-owner",
                message="Question two",
                client_turn_id=turn_b,
                chat_backend=StubChatBackend(),
            )
        assert raised.value.code == "stale_turn"
    finally:
        _cleanup(engine, project_id)


def test_new_turn_while_pending_conflicts(engine: Engine) -> None:
    """A fresh pending row blocks a differently-keyed new turn as in-progress."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, project_id=project_id, scope_id=scope_id, status="succeeded")
        _insert_pending_turn(engine, conversation_id=conversation_id)

        with pytest.raises(ApiConflict) as raised:
            chat_turns.run_chat_turn(
                engine,
                project_id=project_id,
                conversation_id=conversation_id,
                user_id="chat-owner",
                message="a new question",
                client_turn_id=uuid.uuid4(),
                chat_backend=StubChatBackend(),
            )
        assert raised.value.code == "chat_turn_in_progress"
    finally:
        _cleanup(engine, project_id)


def test_owner_in_flight_cap(engine: Engine) -> None:
    """A third owner-scoped chat turn hits the process-wide in-flight cap."""
    owner = "cap-owner"
    project_ids: list[uuid.UUID] = []
    try:
        project_a, _scope_a, conv_a = _chat(engine, owner=owner)
        project_b, _scope_b, conv_b = _chat(engine, owner=owner)
        project_c, scope_c, conv_c = _chat(engine, owner=owner)
        project_ids = [project_a, project_b, project_c]
        _walk(engine, project_id=project_c, scope_id=scope_c, status="succeeded")
        _insert_pending_turn(engine, conversation_id=conv_a)
        _insert_pending_turn(engine, conversation_id=conv_b)

        with pytest.raises(ApiCapacity) as raised:
            chat_turns.run_chat_turn(
                engine,
                project_id=project_c,
                conversation_id=conv_c,
                user_id=owner,
                message="a third question",
                client_turn_id=uuid.uuid4(),
                chat_backend=StubChatBackend(),
            )
        assert raised.value.code == "chat_capacity"
    finally:
        for project_id in project_ids:
            _cleanup(engine, project_id)


def test_title_set_from_first_question_only(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The chat title derives from the first question only; later turns leave it alone."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, project_id=project_id, scope_id=scope_id, status="succeeded")
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        message = (
            "What does the evidence base say about the effectiveness of home "
            "visiting programmes for improving outcomes for families with young "
            "children overall, across the studies committed to this project?"
        )
        assert len(message) > 100
        expected_title = chat_turns._first_question_title(message)
        assert len(expected_title) <= 80

        chat_turns.run_chat_turn(
            engine,
            project_id=project_id,
            conversation_id=conversation_id,
            user_id="chat-owner",
            message=message,
            client_turn_id=uuid.uuid4(),
            chat_backend=StubChatBackend(),
        )
        with engine.connect() as conn:
            title = conn.execute(
                select(conversation.c.title).where(conversation.c.id == conversation_id)
            ).scalar_one()
        assert title == expected_title

        chat_turns.run_chat_turn(
            engine,
            project_id=project_id,
            conversation_id=conversation_id,
            user_id="chat-owner",
            message="A follow-up question that should not touch the title.",
            client_turn_id=uuid.uuid4(),
            chat_backend=StubChatBackend(),
        )
        with engine.connect() as conn:
            title_after = conn.execute(
                select(conversation.c.title).where(conversation.c.id == conversation_id)
            ).scalar_one()
        assert title_after == expected_title
    finally:
        _cleanup(engine, project_id)


def test_cross_chat_concurrency_isolated(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two chats in one project run concurrently; the turn lock is conversation-scoped."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        with engine.begin() as conn:
            conn.execute(
                update(project)
                .where(project.c.project_id == project_id)
                .values(owner_user_id="cap-owner")
            )
        _walk(engine, project_id=project_id, scope_id=scope_id, status="succeeded")
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)

        conversation_one = _second_chat_in_same_project(engine, project_id)
        conversation_two = _second_chat_in_same_project(engine, project_id)

        results: dict[str, Any] = {}
        errors: dict[str, BaseException] = {}

        def _run(name: str, conversation_id: uuid.UUID, backend: BlockingChatBackend) -> None:
            try:
                results[name] = chat_turns.run_chat_turn(
                    engine,
                    project_id=project_id,
                    conversation_id=conversation_id,
                    user_id="cap-owner",
                    message=f"Question for {name}",
                    client_turn_id=uuid.uuid4(),
                    chat_backend=backend,
                )
            except BaseException as exc:  # noqa: BLE001 - surfaced via errors, not raised here
                errors[name] = exc

        gate_one, gate_two = threading.Event(), threading.Event()
        backend_one, backend_two = BlockingChatBackend(gate_one), BlockingChatBackend(gate_two)
        thread_one = threading.Thread(target=_run, args=("one", conversation_one, backend_one))
        thread_two = threading.Thread(target=_run, args=("two", conversation_two, backend_two))
        thread_one.start()
        thread_two.start()
        gate_one.set()
        gate_two.set()
        thread_one.join(timeout=10)
        thread_two.join(timeout=10)

        assert not errors
        assert results["one"].status == "completed"
        assert results["two"].status == "completed"
        assert results["one"].conversation_id == conversation_one
        assert results["two"].conversation_id == conversation_two
        assert results["one"].id != results["two"].id

        # Same-conversation single-flight: a blocked turn holds the conversation's
        # lock, but the other conversation is never blocked by it.
        started_three, gate_three = threading.Event(), threading.Event()
        backend_three = BlockingChatBackend(gate_three, started=started_three)
        blocked_thread = threading.Thread(
            target=_run, args=("three", conversation_one, backend_three)
        )
        blocked_thread.start()
        assert started_three.wait(timeout=5)
        try:
            with pytest.raises(ApiConflict) as raised:
                chat_turns.run_chat_turn(
                    engine,
                    project_id=project_id,
                    conversation_id=conversation_one,
                    user_id="cap-owner",
                    message="A conflicting question",
                    client_turn_id=uuid.uuid4(),
                    chat_backend=StubChatBackend(),
                )
            assert raised.value.code == "chat_turn_in_progress"

            other_result = chat_turns.run_chat_turn(
                engine,
                project_id=project_id,
                conversation_id=conversation_two,
                user_id="cap-owner",
                message="An unrelated question",
                client_turn_id=uuid.uuid4(),
                chat_backend=StubChatBackend(),
            )
            assert other_result.status == "completed"
            assert other_result.conversation_id == conversation_two
        finally:
            gate_three.set()
            blocked_thread.join(timeout=10)
        assert not errors.get("three")
        assert results["three"].status == "completed"
    finally:
        _cleanup(engine, project_id)


def test_message_over_cap_rejected(engine: Engine) -> None:
    """A message beyond the contract cap is rejected before any reservation work."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, project_id=project_id, scope_id=scope_id, status="succeeded")
        with pytest.raises(ValueError):
            chat_turns.run_chat_turn(
                engine,
                project_id=project_id,
                conversation_id=conversation_id,
                user_id="chat-owner",
                message="x" * 10_001,
                client_turn_id=uuid.uuid4(),
                chat_backend=StubChatBackend(),
            )
    finally:
        _cleanup(engine, project_id)


def test_citation_sources_resolve_to_document_titles(engine: Engine) -> None:
    """Persisted citations carry the cited document's title and source id."""
    from policy_atlas.api.chat_turns import _resolve_citation_sources
    from policy_atlas.core.schema import chunk as chunk_table
    from tests.helpers import delete_project_data, seed_source

    project_id = None
    try:
        with engine.begin() as conn:
            import uuid as _uuid

            from policy_atlas.core.schema import project as project_table
            from tests.helpers import now as _now_helper

            project_id = _uuid.uuid4()
            conn.execute(
                project_table.insert().values(
                    project_id=project_id,
                    created_at=_now_helper(),
                    name="Citation resolution test",
                    question=None,
                    status="active",
                    updated_at=_now_helper(),
                    owner_user_id="chat-owner",
                )
            )
            snapshot_id, pss_id = seed_source(
                conn, project_id, {"title": "A real document title"}
            )
            chunk_id = _uuid.uuid4()
            conn.execute(
                chunk_table.insert().values(
                    chunk_id=chunk_id,
                    source_snapshot_id=snapshot_id,
                    sequence=0,
                    content="Chunk content.",
                    content_hash="hash",
                    locator={"start": 0, "end": 14},
                    segmentation_policy="manual_v1",
                    created_at=_now_helper(),
                )
            )
        resolved = _resolve_citation_sources(
            engine,
            [
                {"n": 1, "id": str(chunk_id), "kind": "chunk", "quote": "q", "state": "unchecked"},
                {"n": 2, "id": "not-a-uuid", "kind": "chunk", "quote": "q", "state": "unchecked"},
            ],
            project_id=project_id,
        )
        assert resolved[0]["source_title"] == "A real document title"
        assert resolved[0]["source_id"] == str(pss_id)
        assert "source_title" not in resolved[1]
    finally:
        if project_id is not None:
            with engine.begin() as conn:
                delete_project_data(conn, project_id)


def test_citation_sources_are_scoped_to_the_calling_project(engine: Engine) -> None:
    """A snapshot shared by two projects resolves to the calling project's own pss."""
    from policy_atlas.api.chat_turns import _resolve_citation_sources
    from policy_atlas.core.schema import chunk as chunk_table
    from policy_atlas.core.schema import project as project_table
    from policy_atlas.core.schema import project_source_snapshot, source_snapshot

    project_a, project_b = uuid.uuid4(), uuid.uuid4()
    snapshot_id, pss_a, pss_b, chunk_id = (
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
    )
    with engine.begin() as conn:
        for proj_id in (project_a, project_b):
            conn.execute(
                project_table.insert().values(
                    project_id=proj_id,
                    created_at=now(),
                    name="Shared-snapshot test project",
                    question=None,
                    status="active",
                    updated_at=now(),
                    owner_user_id="chat-owner",
                )
            )
        conn.execute(
            source_snapshot.insert().values(
                source_snapshot_id=snapshot_id,
                content_hash="shared-snapshot-hash",
                text_basis="full_text",
                source_locator="test://shared-document",
                metadata={"title": "Shared document"},
                created_at=now(),
            )
        )
        for pss_id, proj_id in ((pss_a, project_a), (pss_b, project_b)):
            conn.execute(
                project_source_snapshot.insert().values(
                    project_source_snapshot_id=pss_id,
                    project_id=proj_id,
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
                content="Shared chunk content.",
                content_hash="shared-chunk-hash",
                locator={"start": 0, "end": 21},
                segmentation_policy="manual_v1",
                created_at=now(),
            )
        )
    try:
        resolved = _resolve_citation_sources(
            engine,
            [{"n": 1, "id": str(chunk_id), "kind": "chunk", "quote": "q", "state": "unchecked"}],
            project_id=project_b,
        )
        assert resolved[0]["source_id"] == str(pss_b)
        assert resolved[0]["source_id"] != str(pss_a)
    finally:
        with engine.begin() as conn:
            conn.execute(chunk_table.delete().where(chunk_table.c.chunk_id == chunk_id))
            conn.execute(
                project_source_snapshot.delete().where(
                    project_source_snapshot.c.project_source_snapshot_id.in_([pss_a, pss_b])
                )
            )
            conn.execute(
                source_snapshot.delete().where(
                    source_snapshot.c.source_snapshot_id == snapshot_id
                )
            )
            conn.execute(
                project_table.delete().where(project_table.c.project_id.in_([project_a, project_b]))
            )


def _seed_citation_chunk(engine: Engine, *, content: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Insert a project + source + chunk with the given content.

    Returns:
        ``(project_id, chunk_id, project_source_snapshot_id)``.
    """
    from policy_atlas.core.schema import chunk as chunk_table
    from policy_atlas.core.schema import project as project_table
    from tests.helpers import seed_source

    project_id, chunk_id = uuid.uuid4(), uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            project_table.insert().values(
                project_id=project_id,
                created_at=now(),
                name="Citation resolution test",
                question=None,
                status="active",
                updated_at=now(),
                owner_user_id="chat-owner",
            )
        )
        snapshot_id, pss_id = seed_source(conn, project_id)
        conn.execute(
            chunk_table.insert().values(
                chunk_id=chunk_id,
                source_snapshot_id=snapshot_id,
                sequence=0,
                content=content,
                content_hash=str(uuid.uuid4()),
                locator={"start": 0, "end": len(content)},
                segmentation_policy="manual_v1",
                created_at=now(),
            )
        )
    return project_id, chunk_id, pss_id


def test_citation_quote_snaps_to_verbatim_source_on_near_miss(engine: Engine) -> None:
    """A near-miss chunk quote (curly quotes/case/whitespace) snaps to verbatim source text."""
    from policy_atlas.api.chat_turns import _resolve_citation_sources
    from tests.helpers import delete_project_data

    raw_span = "The report found “Clear   Evidence”\nacross studies."
    content = "Before text. " + raw_span + " After text."
    project_id, chunk_id, _pss_id = _seed_citation_chunk(engine, content=content)
    try:
        resolved = _resolve_citation_sources(
            engine,
            [
                {
                    "n": 1,
                    "id": str(chunk_id),
                    "kind": "chunk",
                    "quote": 'the report found "clear evidence" across studies.',
                    "state": "unchecked",
                }
            ],
            project_id=project_id,
        )
        assert resolved[0]["quote"] == raw_span
        assert resolved[0]["quote_snapped"] is True
    finally:
        with engine.begin() as conn:
            delete_project_data(conn, project_id)


def test_citation_quote_exact_match_persists_unchanged_without_marker(engine: Engine) -> None:
    """An exact chunk quote persists verbatim, with no snap marker either way."""
    from policy_atlas.api.chat_turns import _resolve_citation_sources
    from tests.helpers import delete_project_data

    content = "Before text. The exact quoted span. After text."
    project_id, chunk_id, _pss_id = _seed_citation_chunk(engine, content=content)
    try:
        resolved = _resolve_citation_sources(
            engine,
            [
                {
                    "n": 1,
                    "id": str(chunk_id),
                    "kind": "chunk",
                    "quote": "The exact quoted span.",
                    "state": "unchecked",
                }
            ],
            project_id=project_id,
        )
        assert resolved[0]["quote"] == "The exact quoted span."
        assert "quote_snapped" not in resolved[0]
    finally:
        with engine.begin() as conn:
            delete_project_data(conn, project_id)


def test_citation_quote_paraphrase_persists_untouched(engine: Engine) -> None:
    """A paraphrased chunk quote with no located span is left untouched, no marker."""
    from policy_atlas.api.chat_turns import _resolve_citation_sources
    from tests.helpers import delete_project_data

    content = "The report found clear evidence across studies."
    project_id, chunk_id, _pss_id = _seed_citation_chunk(engine, content=content)
    try:
        resolved = _resolve_citation_sources(
            engine,
            [
                {
                    "n": 1,
                    "id": str(chunk_id),
                    "kind": "chunk",
                    "quote": "the studies broadly agreed the evidence was clear",
                    "state": "unchecked",
                }
            ],
            project_id=project_id,
        )
        assert resolved[0]["quote"] == "the studies broadly agreed the evidence was clear"
        assert "quote_snapped" not in resolved[0]
    finally:
        with engine.begin() as conn:
            delete_project_data(conn, project_id)


def test_citation_quote_ambiguous_persists_untouched(engine: Engine) -> None:
    """A chunk quote with two normalised occurrences is left untouched, no marker."""
    from policy_atlas.api.chat_turns import _resolve_citation_sources
    from tests.helpers import delete_project_data

    content = "The New York pilot launched first. A second NEW YORK rollout followed later."
    project_id, chunk_id, _pss_id = _seed_citation_chunk(engine, content=content)
    try:
        resolved = _resolve_citation_sources(
            engine,
            [
                {
                    "n": 1,
                    "id": str(chunk_id),
                    "kind": "chunk",
                    "quote": "new york",
                    "state": "unchecked",
                }
            ],
            project_id=project_id,
        )
        assert resolved[0]["quote"] == "new york"
        assert "quote_snapped" not in resolved[0]
    finally:
        with engine.begin() as conn:
            delete_project_data(conn, project_id)


def test_citation_appraisal_label_and_evidence_type_resolve(engine: Engine) -> None:
    """A cited chunk resolves the appraisal label + evidence type the ARTEFACT read model shows."""
    from policy_atlas.api.chat_turns import _resolve_citation_sources
    from policy_atlas.core.schema import (
        EVIDENCE_TYPES,
        evidence_scope,
        runs,
        source_appraisal_result,
        source_classification_result,
    )
    from tests.helpers import delete_project_data

    project_id, chunk_id, pss_id = _seed_citation_chunk(
        engine, content="Chunk content for appraisal resolution."
    )
    scope_id, run_id = uuid.uuid4(), uuid.uuid4()
    try:
        with engine.begin() as conn:
            conn.execute(
                evidence_scope.insert().values(
                    evidence_scope_id=scope_id,
                    project_id=project_id,
                    intent="test intent",
                    context={},
                    created_at=now(),
                )
            )
            conn.execute(
                runs.insert().values(
                    run_id=run_id,
                    project_id=project_id,
                    status="succeeded",
                    started_at=now(),
                )
            )
            conn.execute(
                source_appraisal_result.insert().values(
                    source_appraisal_result_id=uuid.uuid4(),
                    evidence_scope_id=scope_id,
                    project_source_snapshot_id=pss_id,
                    project_id=project_id,
                    appraised_by_run_id=run_id,
                    quality_score=4,
                    rubric_version="v2",
                    appraised_at=now(),
                )
            )
            conn.execute(
                source_classification_result.insert().values(
                    source_classification_result_id=uuid.uuid4(),
                    evidence_scope_id=scope_id,
                    project_source_snapshot_id=pss_id,
                    project_id=project_id,
                    classified_by_run_id=run_id,
                    primary_evidence_type=EVIDENCE_TYPES[0],
                    classified_at=now(),
                )
            )
        resolved = _resolve_citation_sources(
            engine,
            [{"n": 1, "id": str(chunk_id), "kind": "chunk", "quote": "", "state": "unchecked"}],
            project_id=project_id,
        )
        assert resolved[0]["appraisal_label"] == "Strong"
        assert resolved[0]["evidence_type"] == EVIDENCE_TYPES[0]
    finally:
        with engine.begin() as conn:
            delete_project_data(conn, project_id)


def test_citation_missing_appraisal_leaves_fields_absent(engine: Engine) -> None:
    """A cited chunk with no appraisal/classification rows leaves those fields absent."""
    from policy_atlas.api.chat_turns import _resolve_citation_sources
    from tests.helpers import delete_project_data

    project_id, chunk_id, _pss_id = _seed_citation_chunk(
        engine, content="Unappraised chunk content."
    )
    try:
        resolved = _resolve_citation_sources(
            engine,
            [{"n": 1, "id": str(chunk_id), "kind": "chunk", "quote": "", "state": "unchecked"}],
            project_id=project_id,
        )
        assert "appraisal_label" not in resolved[0]
        assert "evidence_type" not in resolved[0]
    finally:
        with engine.begin() as conn:
            delete_project_data(conn, project_id)


def test_retry_same_client_turn_id_against_live_pending_conflicts(engine: Engine) -> None:
    """A live pending row under this client_turn_id refuses a stranger, not a re-run."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, project_id=project_id, scope_id=scope_id, status="succeeded")
        turn_id = uuid.uuid4()
        client_turn_id = uuid.uuid4()
        message = "In-flight question"
        with engine.begin() as conn:
            conn.execute(
                chat_turn.insert().values(
                    id=turn_id,
                    conversation_id=conversation_id,
                    turn_index=0,
                    client_turn_id=client_turn_id,
                    user_message=message,
                    answer=None,
                    answer_payload=None,
                    capability_run_id=None,
                    status="pending",
                    created_at=now(),
                    completed_at=None,
                )
            )
        backend = CountingChatBackend()
        with pytest.raises(ApiConflict) as raised:
            chat_turns.run_chat_turn(
                engine,
                project_id=project_id,
                conversation_id=conversation_id,
                user_id="chat-owner",
                message=message,
                client_turn_id=client_turn_id,
                chat_backend=backend,
            )
        assert raised.value.code == "chat_turn_in_progress"
        assert backend.calls == 0
        with engine.connect() as conn:
            status = conn.execute(
                select(chat_turn.c.status).where(chat_turn.c.id == turn_id)
            ).scalar_one()
        assert status == "pending"
    finally:
        _cleanup(engine, project_id)


def test_retry_same_client_turn_id_after_ttl_expiry_succeeds(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ten-minute-stale pending row under its own client_turn_id retries in place."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, project_id=project_id, scope_id=scope_id, status="succeeded")
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        turn_id = uuid.uuid4()
        client_turn_id = uuid.uuid4()
        message = "Stale question"
        with engine.begin() as conn:
            conn.execute(
                chat_turn.insert().values(
                    id=turn_id,
                    conversation_id=conversation_id,
                    turn_index=0,
                    client_turn_id=client_turn_id,
                    user_message=message,
                    answer=None,
                    answer_payload=None,
                    capability_run_id=None,
                    status="pending",
                    created_at=now() - timedelta(minutes=11),
                    completed_at=None,
                )
            )
        result = chat_turns.run_chat_turn(
            engine,
            project_id=project_id,
            conversation_id=conversation_id,
            user_id="chat-owner",
            message=message,
            client_turn_id=client_turn_id,
            chat_backend=StubChatBackend(),
        )
        assert result.status == "completed"
        assert result.id == turn_id
    finally:
        _cleanup(engine, project_id)


def test_run_chat_turn_reenters_its_own_reservation(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The caller's own reserved pending row is retried in place, not conflicted."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, project_id=project_id, scope_id=scope_id, status="succeeded")
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        client_turn_id = uuid.uuid4()
        message = "Route-reserved question"
        with engine.begin() as conn:
            reserved = chat_turns._phase_one_turn(
                conn,
                project_id=project_id,
                conversation_id=conversation_id,
                user_id="chat-owner",
                message=message,
                client_turn_id=client_turn_id,
            )
        assert isinstance(reserved, uuid.UUID)
        result = chat_turns.run_chat_turn(
            engine,
            project_id=project_id,
            conversation_id=conversation_id,
            user_id="chat-owner",
            message=message,
            client_turn_id=client_turn_id,
            chat_backend=StubChatBackend(),
            reserved_turn_id=reserved,
        )
        assert result.status == "completed"
        assert result.id == reserved
    finally:
        _cleanup(engine, project_id)


def test_durable_cancel_after_last_check_wins_at_terminal_commit(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cross-process cancel landing after the loop's last check stays cancelled."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, project_id=project_id, scope_id=scope_id, status="succeeded")
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        real_floor = getattr(chat_turns, "apply_citation_floor")  # noqa: B009

        def _sneaky_floor(*args: Any, **kwargs: Any) -> Any:
            """Apply the real floor, then simulate a racing durable cancel."""
            floored = real_floor(*args, **kwargs)
            with engine.begin() as conn:
                conn.execute(
                    update(chat_turn)
                    .where(chat_turn.c.conversation_id == conversation_id)
                    .values(status="cancelled", completed_at=now(), answer="stale partial")
                )
            return floored

        monkeypatch.setattr(chat_turns, "apply_citation_floor", _sneaky_floor)
        result = chat_turns.run_chat_turn(
            engine,
            project_id=project_id,
            conversation_id=conversation_id,
            user_id="chat-owner",
            message="Question",
            client_turn_id=uuid.uuid4(),
            chat_backend=StubChatBackend(),
        )
        assert result.status == "cancelled"
        assert result.answer == "stale partial"
    finally:
        _cleanup(engine, project_id)


def test_chat_call_site_pins_tool_allowlist_into_the_tool_loop(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mapping handed to run_tool_loop at the chat call site is exactly the allowlist."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, project_id=project_id, scope_id=scope_id, status="succeeded")
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        captured: dict[str, Any] = {}
        real_run_tool_loop = getattr(chat_turns, "run_tool_loop")  # noqa: B009

        def _capturing_run_tool_loop(*args: Any, tools: dict[str, Any], **kwargs: Any) -> Any:
            """Record the tool mapping the call site hands to the kernel loop."""
            captured["tools"] = tools
            return real_run_tool_loop(*args, tools=tools, **kwargs)

        monkeypatch.setattr(chat_turns, "run_tool_loop", _capturing_run_tool_loop)
        chat_turns.run_chat_turn(
            engine,
            project_id=project_id,
            conversation_id=conversation_id,
            user_id="chat-owner",
            message="Question",
            client_turn_id=uuid.uuid4(),
            chat_backend=StubChatBackend(),
        )
        assert set(captured["tools"]) == {"search_chunks", "query_findings", "lookup"}
    finally:
        _cleanup(engine, project_id)
