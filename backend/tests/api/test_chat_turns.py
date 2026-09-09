"""Durable service coverage for the Phase C chat-turn engine."""

from __future__ import annotations

import threading
import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import event, func, select, update
from sqlalchemy.engine import Engine

from policy_atlas.api import chat_turns
from policy_atlas.api.app import ApiCapacity, ApiConflict
from policy_atlas.api.chat_turns import ChatTurnResult
from policy_atlas.core.schema import capability_run, chat_turn, conversation, task
from policy_atlas.evidence_search.synthesis.synthesis_tools import build_section_tools
from policy_atlas.runtime.chat_backend import StubChatBackend
from tests.helpers import now
from tests.runtime.test_runner import _cleanup as _cleanup
from tests.runtime.test_runner import _seed_task as _seed_task


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


def _chat(
    engine: Engine, *, owner: str = "chat-owner", created_by: str | None = None
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Create an active chat over a task fixture.

    ``created_by`` defaults to ``None``, the legacy pre-033 shape: an
    unattributed chat belongs to the task owner through the contract's NULL
    disjunct, so every case in this file that predates task 033 goes on
    exercising exactly what it always did. Pass it to make the chat somebody
    else's — a colleague's.
    """
    task_id, scope_id = _seed_task(engine)
    conversation_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            update(task).where(task.c.task_id == task_id).values(owner_user_id=owner)
        )
        conn.execute(
            conversation.insert().values(
                id=conversation_id,
                task_id=task_id,
                kind="chat",
                title="New chat",
                entry_artefact_id=None,
                status="active",
                created_at=now(),
                closed_at=None,
                archived_at=None,
                created_by=created_by,
            )
        )
    return task_id, scope_id, conversation_id


def _walk(engine: Engine, *, task_id: uuid.UUID, scope_id: uuid.UUID, status: str) -> None:
    """Persist the minimal capability-walk eligibility fixture."""
    with engine.begin() as conn:
        conn.execute(
            capability_run.insert().values(
                capability_run_id=uuid.uuid4(),
                task_id=task_id,
                evidence_scope_id=scope_id,
                capability="evidence_search",
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
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        backend = OutputCappedChatBackend()
        turn_id = uuid.uuid4()
        first = chat_turns.run_chat_turn(
            engine,
            task_id=task_id,
            conversation_id=conversation_id,
            user_id="chat-owner",
            message="What does the evidence say?",
            client_turn_id=turn_id,
            chat_backend=backend,
        )
        replay = chat_turns.run_chat_turn(
            engine,
            task_id=task_id,
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
        _cleanup(engine, task_id)


@pytest.mark.parametrize(
    ("walk_status", "code"), [(None, "no_completed_run"), ("running", "run_active")]
)
def test_turn_requires_completed_run(engine: Engine, walk_status: str | None, code: str) -> None:
    """Missing completion and an active walk produce named eligibility conflicts."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, conversation_id = _chat(engine)
        if walk_status is not None:
            _walk(engine, task_id=task_id, scope_id=scope_id, status=walk_status)
        with pytest.raises(ApiConflict) as raised:
            chat_turns.run_chat_turn(
                engine,
                task_id=task_id,
                conversation_id=conversation_id,
                user_id="chat-owner",
                message="Question",
                client_turn_id=uuid.uuid4(),
                chat_backend=StubChatBackend(),
            )
        assert raised.value.code == code
    finally:
        _cleanup(engine, task_id)


def test_active_walk_fences_chat(engine: Engine) -> None:
    """A running walk wins over an older completed walk at reservation time."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
        _walk(engine, task_id=task_id, scope_id=scope_id, status="running")
        with pytest.raises(ApiConflict) as raised:
            chat_turns.run_chat_turn(
                engine,
                task_id=task_id,
                conversation_id=conversation_id,
                user_id="chat-owner",
                message="Question",
                client_turn_id=uuid.uuid4(),
                chat_backend=StubChatBackend(),
            )
        assert raised.value.code == "run_active"
    finally:
        _cleanup(engine, task_id)


def test_stale_pending_is_failed_before_reservation(engine: Engine) -> None:
    """A ten-minute-old pending row no longer blocks a new turn."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
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
                task_id=task_id,
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
        _cleanup(engine, task_id)


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
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        cancel = threading.Event()
        result = chat_turns.run_chat_turn(
            engine,
            task_id=task_id,
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
        _cleanup(engine, task_id)


def _second_chat_in_same_task(
    engine: Engine, task_id: uuid.UUID, *, created_by: str | None = None
) -> uuid.UUID:
    """Insert an additional active chat conversation onto an existing task."""
    conversation_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            conversation.insert().values(
                id=conversation_id,
                task_id=task_id,
                kind="chat",
                title="New chat",
                entry_artefact_id=None,
                status="active",
                created_at=now(),
                closed_at=None,
                archived_at=None,
                created_by=created_by,
            )
        )
    return conversation_id


def _insert_pending_turn(
    engine: Engine,
    *,
    conversation_id: uuid.UUID,
    turn_index: int = 0,
    stale: bool = False,
) -> uuid.UUID:
    """Insert one pending chat_turn row directly and return its id.

    ``stale=True`` back-dates ``created_at`` past ``_PENDING_TTL``, which is
    how the sweeper cases simulate a turn whose process died — the same
    direct-timestamp trick `test_stale_pending_is_failed_before_reservation`
    uses.
    """
    turn_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            chat_turn.insert().values(
                id=turn_id,
                conversation_id=conversation_id,
                turn_index=turn_index,
                client_turn_id=uuid.uuid4(),
                user_message="in flight",
                answer=None,
                answer_payload=None,
                capability_run_id=None,
                status="pending",
                created_at=now() - timedelta(minutes=11) if stale else now(),
                completed_at=None,
            )
        )
    return turn_id


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
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        backend = FailOnceChatBackend()
        turn_id = uuid.uuid4()
        message = "What does the evidence say?"
        with pytest.raises(RuntimeError):
            chat_turns.run_chat_turn(
                engine,
                task_id=task_id,
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
            task_id=task_id,
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
        _cleanup(engine, task_id)


def test_retry_of_non_latest_failed_turn_is_stale(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the latest chat turn may be retried; an older failed turn is stale."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        turn_a, turn_b, turn_c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

        chat_turns.run_chat_turn(
            engine,
            task_id=task_id,
            conversation_id=conversation_id,
            user_id="chat-owner",
            message="Question one",
            client_turn_id=turn_a,
            chat_backend=StubChatBackend(),
        )
        with pytest.raises(RuntimeError):
            chat_turns.run_chat_turn(
                engine,
                task_id=task_id,
                conversation_id=conversation_id,
                user_id="chat-owner",
                message="Question two",
                client_turn_id=turn_b,
                chat_backend=AlwaysFailsChatBackend(),
            )
        chat_turns.run_chat_turn(
            engine,
            task_id=task_id,
            conversation_id=conversation_id,
            user_id="chat-owner",
            message="Question three",
            client_turn_id=turn_c,
            chat_backend=StubChatBackend(),
        )

        with pytest.raises(ApiConflict) as raised:
            chat_turns.run_chat_turn(
                engine,
                task_id=task_id,
                conversation_id=conversation_id,
                user_id="chat-owner",
                message="Question two",
                client_turn_id=turn_b,
                chat_backend=StubChatBackend(),
            )
        assert raised.value.code == "stale_turn"
    finally:
        _cleanup(engine, task_id)


def test_new_turn_while_pending_conflicts(engine: Engine) -> None:
    """A fresh pending row blocks a differently-keyed new turn as in-progress."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
        _insert_pending_turn(engine, conversation_id=conversation_id)

        with pytest.raises(ApiConflict) as raised:
            chat_turns.run_chat_turn(
                engine,
                task_id=task_id,
                conversation_id=conversation_id,
                user_id="chat-owner",
                message="a new question",
                client_turn_id=uuid.uuid4(),
                chat_backend=StubChatBackend(),
            )
        assert raised.value.code == "chat_turn_in_progress"
    finally:
        _cleanup(engine, task_id)


def test_owner_in_flight_cap(engine: Engine) -> None:
    """A third owner-scoped chat turn hits the process-wide in-flight cap."""
    owner = "cap-owner"
    task_ids: list[uuid.UUID] = []
    try:
        task_a, _scope_a, conv_a = _chat(engine, owner=owner)
        task_b, _scope_b, conv_b = _chat(engine, owner=owner)
        task_c, scope_c, conv_c = _chat(engine, owner=owner)
        task_ids = [task_a, task_b, task_c]
        _walk(engine, task_id=task_c, scope_id=scope_c, status="succeeded")
        _insert_pending_turn(engine, conversation_id=conv_a)
        _insert_pending_turn(engine, conversation_id=conv_b)

        with pytest.raises(ApiCapacity) as raised:
            chat_turns.run_chat_turn(
                engine,
                task_id=task_c,
                conversation_id=conv_c,
                user_id=owner,
                message="a third question",
                client_turn_id=uuid.uuid4(),
                chat_backend=StubChatBackend(),
            )
        assert raised.value.code == "chat_capacity"
    finally:
        for task_id in task_ids:
            _cleanup(engine, task_id)


def test_title_set_from_first_question_only(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The chat title derives from the first question only; later turns leave it alone."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        message = (
            "What does the evidence base say about the effectiveness of home "
            "visiting programmes for improving outcomes for families with young "
            "children overall, across the studies committed to this task?"
        )
        assert len(message) > 100
        expected_title = chat_turns._first_question_title(message)
        assert len(expected_title) <= 80

        chat_turns.run_chat_turn(
            engine,
            task_id=task_id,
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
            task_id=task_id,
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
        _cleanup(engine, task_id)


def test_cross_chat_concurrency_isolated(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two chats in one task run concurrently; the turn lock is conversation-scoped."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        with engine.begin() as conn:
            conn.execute(
                update(task)
                .where(task.c.task_id == task_id)
                .values(owner_user_id="cap-owner")
            )
        _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)

        conversation_one = _second_chat_in_same_task(engine, task_id)
        conversation_two = _second_chat_in_same_task(engine, task_id)

        results: dict[str, Any] = {}
        errors: dict[str, BaseException] = {}

        def _run(name: str, conversation_id: uuid.UUID, backend: BlockingChatBackend) -> None:
            try:
                results[name] = chat_turns.run_chat_turn(
                    engine,
                    task_id=task_id,
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
                    task_id=task_id,
                    conversation_id=conversation_one,
                    user_id="cap-owner",
                    message="A conflicting question",
                    client_turn_id=uuid.uuid4(),
                    chat_backend=StubChatBackend(),
                )
            assert raised.value.code == "chat_turn_in_progress"

            other_result = chat_turns.run_chat_turn(
                engine,
                task_id=task_id,
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
        _cleanup(engine, task_id)


def test_message_over_cap_rejected(engine: Engine) -> None:
    """A message beyond the contract cap is rejected before any reservation work."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
        with pytest.raises(ValueError):
            chat_turns.run_chat_turn(
                engine,
                task_id=task_id,
                conversation_id=conversation_id,
                user_id="chat-owner",
                message="x" * 10_001,
                client_turn_id=uuid.uuid4(),
                chat_backend=StubChatBackend(),
            )
    finally:
        _cleanup(engine, task_id)


def test_citation_sources_resolve_to_document_titles(engine: Engine) -> None:
    """Persisted citations carry the cited document's title and source id."""
    from policy_atlas.api.chat_turns import _resolve_citation_sources
    from policy_atlas.core.schema import chunk as chunk_table
    from tests.helpers import delete_task_data, seed_source

    task_id = None
    try:
        with engine.begin() as conn:
            import uuid as _uuid

            from policy_atlas.core.schema import task as task_table
            from tests.helpers import now as _now_helper

            task_id = _uuid.uuid4()
            conn.execute(
                task_table.insert().values(
                    task_id=task_id,
                    created_at=_now_helper(),
                    name="Citation resolution test",
                    question=None,
                    status="active",
                    updated_at=_now_helper(),
                    owner_user_id="chat-owner",
                )
            )
            snapshot_id, tss_id = seed_source(
                conn, task_id, {"title": "A real document title"}
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
            task_id=task_id,
        )
        assert resolved[0]["source_title"] == "A real document title"
        assert resolved[0]["source_id"] == str(tss_id)
        assert "source_title" not in resolved[1]
    finally:
        if task_id is not None:
            with engine.begin() as conn:
                delete_task_data(conn, task_id)


def test_citation_sources_are_scoped_to_the_calling_task(engine: Engine) -> None:
    """A snapshot shared by two tasks resolves to the calling task's own tss."""
    from policy_atlas.api.chat_turns import _resolve_citation_sources
    from policy_atlas.core.schema import chunk as chunk_table
    from policy_atlas.core.schema import source_snapshot, task_source_snapshot
    from policy_atlas.core.schema import task as task_table

    task_a, task_b = uuid.uuid4(), uuid.uuid4()
    snapshot_id, tss_a, tss_b, chunk_id = (
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
    )
    with engine.begin() as conn:
        for proj_id in (task_a, task_b):
            conn.execute(
                task_table.insert().values(
                    task_id=proj_id,
                    created_at=now(),
                    name="Shared-snapshot test task",
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
        for tss_id, proj_id in ((tss_a, task_a), (tss_b, task_b)):
            conn.execute(
                task_source_snapshot.insert().values(
                    task_source_snapshot_id=tss_id,
                    task_id=proj_id,
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
            task_id=task_b,
        )
        assert resolved[0]["source_id"] == str(tss_b)
        assert resolved[0]["source_id"] != str(tss_a)
    finally:
        with engine.begin() as conn:
            conn.execute(chunk_table.delete().where(chunk_table.c.chunk_id == chunk_id))
            conn.execute(
                task_source_snapshot.delete().where(
                    task_source_snapshot.c.task_source_snapshot_id.in_([tss_a, tss_b])
                )
            )
            conn.execute(
                source_snapshot.delete().where(
                    source_snapshot.c.source_snapshot_id == snapshot_id
                )
            )
            conn.execute(
                task_table.delete().where(task_table.c.task_id.in_([task_a, task_b]))
            )


def _seed_citation_chunk(engine: Engine, *, content: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Insert a task + source + chunk with the given content.

    Returns:
        ``(task_id, chunk_id, task_source_snapshot_id)``.
    """
    from policy_atlas.core.schema import chunk as chunk_table
    from policy_atlas.core.schema import task as task_table
    from tests.helpers import seed_source

    task_id, chunk_id = uuid.uuid4(), uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            task_table.insert().values(
                task_id=task_id,
                created_at=now(),
                name="Citation resolution test",
                question=None,
                status="active",
                updated_at=now(),
                owner_user_id="chat-owner",
            )
        )
        snapshot_id, tss_id = seed_source(conn, task_id)
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
    return task_id, chunk_id, tss_id


def test_citation_quote_snaps_to_verbatim_source_on_near_miss(engine: Engine) -> None:
    """A near-miss chunk quote (curly quotes/case/whitespace) snaps to verbatim source text."""
    from policy_atlas.api.chat_turns import _resolve_citation_sources
    from tests.helpers import delete_task_data

    raw_span = "The report found “Clear   Evidence”\nacross studies."
    content = "Before text. " + raw_span + " After text."
    task_id, chunk_id, _tss_id = _seed_citation_chunk(engine, content=content)
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
            task_id=task_id,
        )
        assert resolved[0]["quote"] == raw_span
        assert resolved[0]["quote_snapped"] is True
    finally:
        with engine.begin() as conn:
            delete_task_data(conn, task_id)


def test_citation_quote_exact_match_persists_unchanged_without_marker(engine: Engine) -> None:
    """An exact chunk quote persists verbatim, with no snap marker either way."""
    from policy_atlas.api.chat_turns import _resolve_citation_sources
    from tests.helpers import delete_task_data

    content = "Before text. The exact quoted span. After text."
    task_id, chunk_id, _tss_id = _seed_citation_chunk(engine, content=content)
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
            task_id=task_id,
        )
        assert resolved[0]["quote"] == "The exact quoted span."
        assert "quote_snapped" not in resolved[0]
    finally:
        with engine.begin() as conn:
            delete_task_data(conn, task_id)


def test_citation_quote_paraphrase_persists_untouched(engine: Engine) -> None:
    """A paraphrased chunk quote with no located span is left untouched, no marker."""
    from policy_atlas.api.chat_turns import _resolve_citation_sources
    from tests.helpers import delete_task_data

    content = "The report found clear evidence across studies."
    task_id, chunk_id, _tss_id = _seed_citation_chunk(engine, content=content)
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
            task_id=task_id,
        )
        assert resolved[0]["quote"] == "the studies broadly agreed the evidence was clear"
        assert "quote_snapped" not in resolved[0]
    finally:
        with engine.begin() as conn:
            delete_task_data(conn, task_id)


def test_citation_quote_ambiguous_persists_untouched(engine: Engine) -> None:
    """A chunk quote with two normalised occurrences is left untouched, no marker."""
    from policy_atlas.api.chat_turns import _resolve_citation_sources
    from tests.helpers import delete_task_data

    content = "The New York pilot launched first. A second NEW YORK rollout followed later."
    task_id, chunk_id, _tss_id = _seed_citation_chunk(engine, content=content)
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
            task_id=task_id,
        )
        assert resolved[0]["quote"] == "new york"
        assert "quote_snapped" not in resolved[0]
    finally:
        with engine.begin() as conn:
            delete_task_data(conn, task_id)


def test_citation_appraisal_score_and_evidence_type_resolve(engine: Engine) -> None:
    """A cited chunk resolves the appraisal SCORE (not a label) + evidence type.

    ``evidence_search.assess.appraise`` pins labels as read-time copy, never
    persisted — ``_resolve_citation_sources`` therefore persists the numeric
    score; ``chat_turns.apply_appraisal_labels`` is what derives the label,
    and only at read time (see the point-in-time test below)."""
    from policy_atlas.api.chat_turns import _resolve_citation_sources
    from policy_atlas.core.schema import (
        EVIDENCE_TYPES,
        evidence_scope,
        runs,
        source_appraisal_result,
        source_classification_result,
    )
    from tests.helpers import delete_task_data

    task_id, chunk_id, tss_id = _seed_citation_chunk(
        engine, content="Chunk content for appraisal resolution."
    )
    scope_id, run_id = uuid.uuid4(), uuid.uuid4()
    try:
        with engine.begin() as conn:
            conn.execute(
                evidence_scope.insert().values(
                    evidence_scope_id=scope_id,
                    task_id=task_id,
                    intent="test intent",
                    context={},
                    created_at=now(),
                )
            )
            conn.execute(
                runs.insert().values(
                    run_id=run_id,
                    task_id=task_id,
                    status="succeeded",
                    started_at=now(),
                )
            )
            conn.execute(
                source_appraisal_result.insert().values(
                    source_appraisal_result_id=uuid.uuid4(),
                    evidence_scope_id=scope_id,
                    task_source_snapshot_id=tss_id,
                    task_id=task_id,
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
                    task_source_snapshot_id=tss_id,
                    task_id=task_id,
                    classified_by_run_id=run_id,
                    primary_evidence_type=EVIDENCE_TYPES[0],
                    classified_at=now(),
                )
            )
        resolved = _resolve_citation_sources(
            engine,
            [{"n": 1, "id": str(chunk_id), "kind": "chunk", "quote": "", "state": "unchecked"}],
            task_id=task_id,
        )
        assert resolved[0]["appraisal_score"] == 4
        assert "appraisal_label" not in resolved[0]
        assert resolved[0]["evidence_type"] == EVIDENCE_TYPES[0]
    finally:
        with engine.begin() as conn:
            delete_task_data(conn, task_id)


def test_citation_missing_appraisal_leaves_fields_absent(engine: Engine) -> None:
    """A cited chunk with no appraisal/classification rows leaves those fields absent."""
    from policy_atlas.api.chat_turns import _resolve_citation_sources
    from tests.helpers import delete_task_data

    task_id, chunk_id, _tss_id = _seed_citation_chunk(
        engine, content="Unappraised chunk content."
    )
    try:
        resolved = _resolve_citation_sources(
            engine,
            [{"n": 1, "id": str(chunk_id), "kind": "chunk", "quote": "", "state": "unchecked"}],
            task_id=task_id,
        )
        assert "appraisal_score" not in resolved[0]
        assert "appraisal_label" not in resolved[0]
        assert "evidence_type" not in resolved[0]
    finally:
        with engine.begin() as conn:
            delete_task_data(conn, task_id)


def test_apply_appraisal_labels_maps_score_to_label() -> None:
    """The read-time helper maps a persisted score to its current label."""
    from policy_atlas.api.chat_turns import apply_appraisal_labels

    citations = [{"n": 1, "id": "chunk-1", "kind": "chunk", "appraisal_score": 4}]
    labelled = apply_appraisal_labels(citations)
    assert labelled[0]["appraisal_label"] == "Strong"
    assert "appraisal_score" not in labelled[0]
    # The input is untouched — the caller may still hold the persisted form.
    assert citations[0]["appraisal_score"] == 4
    assert "appraisal_label" not in citations[0]


def test_apply_appraisal_labels_absent_score_leaves_citation_untouched() -> None:
    """A citation carrying no score (id-only resolution failure) passes through."""
    from policy_atlas.api.chat_turns import apply_appraisal_labels

    citations = [{"n": 1, "id": "chunk-1", "kind": "chunk"}]
    labelled = apply_appraisal_labels(citations)
    assert "appraisal_label" not in labelled[0]
    assert "appraisal_score" not in labelled[0]


def test_appraisal_label_is_point_in_time_not_rewritten_by_a_later_reappraisal(
    engine: Engine,
) -> None:
    """An old turn's label still renders from ITS persisted score after a newer
    appraisal row lands — the point-in-time pin (task 029 delta-review, Fix 2).

    ``_resolve_citation_sources`` persists the score AT ANSWER TIME, like the
    judge verdicts; a later re-appraisal must not rewrite an old answer's
    chip. Since the label is derived fresh from the ALREADY-PERSISTED score
    (not by re-querying the appraisal table), this is true by construction —
    pinned here so a future change that re-resolves from the DB at read time
    would be caught.
    """
    from policy_atlas.api.chat_turns import _resolve_citation_sources, apply_appraisal_labels
    from policy_atlas.core.schema import (
        EVIDENCE_TYPES,
        evidence_scope,
        runs,
        source_appraisal_result,
        source_classification_result,
    )
    from tests.helpers import delete_task_data

    task_id, chunk_id, tss_id = _seed_citation_chunk(
        engine, content="Chunk content for point-in-time appraisal."
    )
    scope_id, run_id = uuid.uuid4(), uuid.uuid4()
    try:
        with engine.begin() as conn:
            conn.execute(
                evidence_scope.insert().values(
                    evidence_scope_id=scope_id,
                    task_id=task_id,
                    intent="test intent",
                    context={},
                    created_at=now(),
                )
            )
            conn.execute(
                runs.insert().values(
                    run_id=run_id, task_id=task_id, status="succeeded", started_at=now()
                )
            )
            conn.execute(
                source_appraisal_result.insert().values(
                    source_appraisal_result_id=uuid.uuid4(),
                    evidence_scope_id=scope_id,
                    task_source_snapshot_id=tss_id,
                    task_id=task_id,
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
                    task_source_snapshot_id=tss_id,
                    task_id=task_id,
                    classified_by_run_id=run_id,
                    primary_evidence_type=EVIDENCE_TYPES[0],
                    classified_at=now(),
                )
            )
        # This is what run_chat_turn persists into answer_payload at answer time.
        persisted_citations = _resolve_citation_sources(
            engine,
            [{"n": 1, "id": str(chunk_id), "kind": "chunk", "quote": "", "state": "unchecked"}],
            task_id=task_id,
        )
        assert persisted_citations[0]["appraisal_score"] == 4

        # A NEWER appraisal row lands (a rerun on a new scope with a different
        # rubric outcome — one (evidence_scope_id, tss) pair per row, so the
        # rerun is a fresh scope).
        newer_scope_id, newer_run_id = uuid.uuid4(), uuid.uuid4()
        with engine.begin() as conn:
            conn.execute(
                evidence_scope.insert().values(
                    evidence_scope_id=newer_scope_id,
                    task_id=task_id,
                    intent="rerun intent",
                    context={},
                    created_at=now(),
                )
            )
            conn.execute(
                runs.insert().values(
                    run_id=newer_run_id,
                    task_id=task_id,
                    status="succeeded",
                    started_at=now(),
                )
            )
            conn.execute(
                source_appraisal_result.insert().values(
                    source_appraisal_result_id=uuid.uuid4(),
                    evidence_scope_id=newer_scope_id,
                    task_source_snapshot_id=tss_id,
                    task_id=task_id,
                    appraised_by_run_id=newer_run_id,
                    quality_score=1,
                    rubric_version="v2",
                    appraised_at=now() + timedelta(minutes=5),
                )
            )

        # Rendering the OLD turn's already-persisted citations still shows the
        # OLD score's label, never the newer row's.
        rendered = apply_appraisal_labels(persisted_citations)
        assert rendered[0]["appraisal_label"] == "Strong"
    finally:
        with engine.begin() as conn:
            delete_task_data(conn, task_id)


def test_retry_same_client_turn_id_against_live_pending_conflicts(engine: Engine) -> None:
    """A live pending row under this client_turn_id refuses a stranger, not a re-run."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
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
                task_id=task_id,
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
        _cleanup(engine, task_id)


def test_retry_same_client_turn_id_after_ttl_expiry_succeeds(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ten-minute-stale pending row under its own client_turn_id retries in place."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
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
            task_id=task_id,
            conversation_id=conversation_id,
            user_id="chat-owner",
            message=message,
            client_turn_id=client_turn_id,
            chat_backend=StubChatBackend(),
        )
        assert result.status == "completed"
        assert result.id == turn_id
    finally:
        _cleanup(engine, task_id)


def test_run_chat_turn_reenters_its_own_reservation(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The caller's own reserved pending row is retried in place, not conflicted."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
        monkeypatch.setattr(chat_turns, "build_section_tools", _citable_tools)
        client_turn_id = uuid.uuid4()
        message = "Route-reserved question"
        with engine.begin() as conn:
            reserved = chat_turns._phase_one_turn(
                conn,
                task_id=task_id,
                conversation_id=conversation_id,
                user_id="chat-owner",
                message=message,
                client_turn_id=client_turn_id,
            )
        assert isinstance(reserved, uuid.UUID)
        result = chat_turns.run_chat_turn(
            engine,
            task_id=task_id,
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
        _cleanup(engine, task_id)


def test_durable_cancel_after_last_check_wins_at_terminal_commit(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cross-process cancel landing after the loop's last check stays cancelled."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
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
            task_id=task_id,
            conversation_id=conversation_id,
            user_id="chat-owner",
            message="Question",
            client_turn_id=uuid.uuid4(),
            chat_backend=StubChatBackend(),
        )
        assert result.status == "cancelled"
        assert result.answer == "stale partial"
    finally:
        _cleanup(engine, task_id)


def test_chat_call_site_pins_tool_allowlist_into_the_tool_loop(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mapping handed to run_tool_loop at the chat call site is exactly the allowlist."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
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
            task_id=task_id,
            conversation_id=conversation_id,
            user_id="chat-owner",
            message="Question",
            client_turn_id=uuid.uuid4(),
            chat_backend=StubChatBackend(),
        )
        assert set(captured["tools"]) == {"search_chunks", "query_findings", "lookup"}
    finally:
        _cleanup(engine, task_id)


# --- Task 033 phase 5: the cap, the sweeper and the reservation lock --------
#
# Both the pending cap and `_expire_stale_pending_turns` were keyed to
# `task.owner_user_id`. They re-key to the conversation's creator together,
# because re-keying either alone is a defect the contract names: a colleague
# whose turns die would be rate-limited permanently with no operator lever,
# and an owner's sweep would silently fail other people's in-flight turns.


def _owner_of(engine: Engine, task_id: uuid.UUID) -> str:
    """Read one task's owner subject."""
    with engine.connect() as conn:
        return str(
            conn.execute(
                select(task.c.owner_user_id).where(task.c.task_id == task_id)
            ).scalar_one()
        )


def _status_of(engine: Engine, turn_id: uuid.UUID) -> str:
    """Read one durable turn's status."""
    with engine.connect() as conn:
        return str(
            conn.execute(select(chat_turn.c.status).where(chat_turn.c.id == turn_id)).scalar_one()
        )


def _statements(conn: Any) -> list[str]:
    """Record every SQL statement the connection issues from now on."""
    recorded: list[str] = []

    def _record(
        _conn: Any, _cursor: Any, statement: str, *_rest: Any
    ) -> None:  # pragma: no cover - trivial
        recorded.append(statement)

    event.listen(conn, "before_cursor_execute", _record)
    return recorded


def test_pending_cap_is_keyed_to_the_acting_user_not_the_task_owner(engine: Engine) -> None:
    """Neither party's in-flight turns can exhaust the other's allowance.

    Before task 033 the cap counted every pending turn under a task the
    *owner* held, so the first colleague to open two chats would have locked
    the owner out of their own task — and vice versa. It now counts the
    turns of whoever is acting, over the conversations they created.
    """
    owner = f"cap-owner-{uuid.uuid4()}"
    colleague = f"cap-colleague-{uuid.uuid4()}"
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, owner_chat = _chat(engine, owner=owner)
        _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
        owner_second = _second_chat_in_same_task(engine, task_id)
        owner_third = _second_chat_in_same_task(engine, task_id)
        colleague_chat = _second_chat_in_same_task(engine, task_id, created_by=colleague)
        colleague_second = _second_chat_in_same_task(engine, task_id, created_by=colleague)
        colleague_third = _second_chat_in_same_task(engine, task_id, created_by=colleague)

        # The owner holds two pending turns, on chats that record no author —
        # the legacy disjunct is what makes them count as theirs.
        _insert_pending_turn(engine, conversation_id=owner_chat)
        _insert_pending_turn(engine, conversation_id=owner_second)

        def _reserve(conversation_id: uuid.UUID, user_id: str) -> uuid.UUID | ChatTurnResult:
            with engine.begin() as conn:
                return chat_turns._phase_one_turn(
                    conn,
                    task_id=task_id,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    message="a question",
                    client_turn_id=uuid.uuid4(),
                )

        with pytest.raises(ApiCapacity) as owner_capped:
            _reserve(owner_third, owner)
        assert owner_capped.value.code == "chat_capacity"

        # The colleague, at zero pending turns of their own, is unaffected by
        # the owner sitting at the cap on the very same task.
        assert isinstance(_reserve(colleague_chat, colleague), uuid.UUID)

        # And the reverse: the colleague's own two now cap the colleague...
        _insert_pending_turn(engine, conversation_id=colleague_second)
        with pytest.raises(ApiCapacity) as colleague_capped:
            _reserve(colleague_third, colleague)
        assert colleague_capped.value.code == "chat_capacity"

        # ...while the owner, whose two pending turns we now clear, is not.
        with engine.begin() as conn:
            conn.execute(
                update(chat_turn)
                .where(chat_turn.c.conversation_id.in_([owner_chat, owner_second]))
                .values(status="completed", answer="done", completed_at=now())
            )
        assert isinstance(_reserve(owner_third, owner), uuid.UUID)
    finally:
        _cleanup(engine, task_id)


def test_pending_cap_still_spans_every_task_the_acting_user_chats_in(engine: Engine) -> None:
    """The cap's *scope* is unchanged — only its subject was re-keyed.

    It has always been one allowance per person across the whole estate, not a
    per-task or per-conversation budget, and it stays that way: a colleague
    holding two pending turns on two different tasks is capped on a third.
    What changed is who "their" turns are — the conversations they created,
    rather than every conversation under a task someone else owns.
    """
    colleague = f"cap-colleague-{uuid.uuid4()}"
    task_ids: list[uuid.UUID] = []
    try:
        task_a, _scope_a, chat_a = _chat(
            engine, owner=f"cap-owner-a-{uuid.uuid4()}", created_by=colleague
        )
        task_b, _scope_b, chat_b = _chat(
            engine, owner=f"cap-owner-b-{uuid.uuid4()}", created_by=colleague
        )
        task_c, scope_c, chat_c = _chat(
            engine, owner=f"cap-owner-c-{uuid.uuid4()}", created_by=colleague
        )
        task_ids = [task_a, task_b, task_c]
        _walk(engine, task_id=task_c, scope_id=scope_c, status="succeeded")
        _insert_pending_turn(engine, conversation_id=chat_a)
        _insert_pending_turn(engine, conversation_id=chat_b)

        with pytest.raises(ApiCapacity) as raised, engine.begin() as conn:
            chat_turns._phase_one_turn(
                conn,
                task_id=task_c,
                conversation_id=chat_c,
                user_id=colleague,
                message="a third question",
                client_turn_id=uuid.uuid4(),
            )
        assert raised.value.code == "chat_capacity"

        # The owner of task C holds no pending turns of their own and is
        # not capped by a colleague's spend on two other people's tasks.
        owners_own = _second_chat_in_same_task(engine, task_c)
        with engine.begin() as conn:
            reserved = chat_turns._phase_one_turn(
                conn,
                task_id=task_c,
                conversation_id=owners_own,
                user_id=_owner_of(engine, task_c),
                message="the owner's own question",
                client_turn_id=uuid.uuid4(),
            )
        assert isinstance(reserved, uuid.UUID)
    finally:
        for task_id in task_ids:
            _cleanup(engine, task_id)


def test_stale_sweep_is_keyed_to_the_acting_user_not_the_task_owner(engine: Engine) -> None:
    """The sweep re-keys with the cap, and only ever touches the actor's own turns.

    Two halves, both named by the contract. The owner acting must **not** fail
    a colleague's in-flight turn — nor even a colleague's expired one, which
    is not theirs to close. And the colleague's own expired turn must be swept
    when *they* next act, or the re-keyed cap would count a dead turn against
    them for ever.
    """
    owner = f"sweep-owner-{uuid.uuid4()}"
    colleague = f"sweep-colleague-{uuid.uuid4()}"
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, owner_chat = _chat(engine, owner=owner)
        _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
        owner_second = _second_chat_in_same_task(engine, task_id)
        colleague_stale_chat = _second_chat_in_same_task(
            engine, task_id, created_by=colleague
        )
        colleague_live_chat = _second_chat_in_same_task(
            engine, task_id, created_by=colleague
        )
        colleague_next_chat = _second_chat_in_same_task(
            engine, task_id, created_by=colleague
        )

        owner_stale = _insert_pending_turn(engine, conversation_id=owner_chat, stale=True)
        colleague_stale = _insert_pending_turn(
            engine, conversation_id=colleague_stale_chat, stale=True
        )
        colleague_live = _insert_pending_turn(engine, conversation_id=colleague_live_chat)

        with engine.begin() as conn:
            chat_turns._phase_one_turn(
                conn,
                task_id=task_id,
                conversation_id=owner_second,
                user_id=owner,
                message="the owner acts",
                client_turn_id=uuid.uuid4(),
            )
        assert _status_of(engine, owner_stale) == "failed"
        # The owner's sweep reaches neither of the colleague's rows.
        assert _status_of(engine, colleague_live) == "pending"
        assert _status_of(engine, colleague_stale) == "pending"

        with engine.begin() as conn:
            chat_turns._phase_one_turn(
                conn,
                task_id=task_id,
                conversation_id=colleague_next_chat,
                user_id=colleague,
                message="the colleague acts",
                client_turn_id=uuid.uuid4(),
            )
        assert _status_of(engine, colleague_stale) == "failed"
        assert _status_of(engine, colleague_live) == "pending"
    finally:
        _cleanup(engine, task_id)


def test_two_simultaneous_reservations_by_one_user_cannot_both_pass_the_cap(
    engine: Engine,
) -> None:
    """The cap survives concurrency, on two real connections.

    The row lock this reservation takes is on the **conversation**, and the cap
    it has to enforce is on the **acting user across every conversation they
    created**. Two POSTs from one person to two different chats therefore lock
    two different rows: neither sees the other's uncommitted insert, both count
    one pending turn against a cap of two, and both proceed — three pending
    turns from an allowance of two, repeatable to any width.

    Written with an explicit hand-off rather than by racing two threads and
    hoping: the first transaction reserves and is **held open**, the second is
    started in a thread and must still be waiting when we look. Then the first
    commits, and the second — now able to see the row it was racing — is
    refused for capacity. Unserialized, it returns a turn id here instead.
    """
    actor = f"cap-race-{uuid.uuid4()}"
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, first_chat = _chat(engine, owner=actor)
        _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
        second_chat = _second_chat_in_same_task(engine, task_id)
        held_chat = _second_chat_in_same_task(engine, task_id)
        # One pending turn already in flight, so the cap of two allows exactly
        # one of the two reservations below.
        _insert_pending_turn(engine, conversation_id=held_chat)

        started = threading.Event()
        finished = threading.Event()
        outcome: list[Any] = []

        def second_reservation() -> None:
            started.set()
            try:
                with engine.begin() as conn:
                    outcome.append(
                        chat_turns._phase_one_turn(
                            conn,
                            task_id=task_id,
                            conversation_id=second_chat,
                            user_id=actor,
                            message="the simultaneous question",
                            client_turn_id=uuid.uuid4(),
                        )
                    )
            except BaseException as exc:  # noqa: BLE001 - reported to the test
                outcome.append(exc)
            finally:
                finished.set()

        with engine.begin() as conn:
            reserved = chat_turns._phase_one_turn(
                conn,
                task_id=task_id,
                conversation_id=first_chat,
                user_id=actor,
                message="the first question",
                client_turn_id=uuid.uuid4(),
            )
            assert isinstance(reserved, uuid.UUID)
            racer = threading.Thread(target=second_reservation)
            racer.start()
            assert started.wait(5.0)
            # Still blocked: the first transaction holds the per-user lock, so
            # the second cannot reach its count until this one commits.
            assert not finished.wait(0.5)

        racer.join(timeout=10.0)
        assert finished.is_set()
        assert len(outcome) == 1
        assert isinstance(outcome[0], ApiCapacity), outcome[0]
        assert outcome[0].code == "chat_capacity"

        with engine.connect() as conn:
            pending = conn.execute(
                select(func.count())
                .select_from(
                    chat_turn.join(
                        conversation, chat_turn.c.conversation_id == conversation.c.id
                    )
                )
                .where(conversation.c.task_id == task_id)
                .where(chat_turn.c.status == "pending")
            ).scalar_one()
        assert pending == chat_turns._USER_PENDING_CAP
    finally:
        _cleanup(engine, task_id)


def test_the_per_user_lock_is_taken_before_the_pending_turns_are_counted(
    engine: Engine,
) -> None:
    """Order, asserted structurally — a lock after the count serializes nothing.

    The concurrency case above is the behavioural proof; this is the one that
    stays readable when someone moves a line. The advisory lock has to be held
    *before* the count is read, or the two transactions still both count below
    the cap and only serialize the insert that follows.
    """
    actor = f"cap-order-{uuid.uuid4()}"
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, chat_id = _chat(engine, owner=actor)
        _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")

        with engine.begin() as conn:
            issued = _statements(conn)
            chat_turns._phase_one_turn(
                conn,
                task_id=task_id,
                conversation_id=chat_id,
                user_id=actor,
                message="a question",
                client_turn_id=uuid.uuid4(),
            )

        locks = [index for index, sql in enumerate(issued) if "pg_advisory_xact_lock" in sql]
        counts = [
            index
            for index, sql in enumerate(issued)
            if "count(*)" in sql.lower() and "chat_turn" in sql
        ]
        assert len(locks) == 1, issued
        assert counts, issued
        assert locks[0] < counts[0]
        # Transaction-scoped, not session-scoped: a `pg_advisory_lock` here
        # would outlive the reservation and leak into the pooled connection.
        assert "pg_advisory_lock(" not in issued[locks[0]]
    finally:
        _cleanup(engine, task_id)


def test_reservation_locks_the_conversation_row_never_the_owners_task(
    engine: Engine,
) -> None:
    """Contract § 4's lock rule, asserted structurally rather than by timing.

    The reservation used to take `SELECT … FOR UPDATE` on the owner's task
    row. A colleague doing that would block the owner's own rename, archive
    and run-start for the length of their transaction, so the lock moved to
    the `conversation` row — the row the reservation actually mutates.

    `OF conversation` is the load-bearing detail: the statement joins
    `task`, and a bare `FOR UPDATE` would lock the joined task row too,
    silently reinstating exactly what the contract forbids. Asserted for the
    colleague *and* the owner — the path is the same one for both, which is
    why there is no caller-dependent lock to get wrong.
    """
    owner = f"lock-owner-{uuid.uuid4()}"
    colleague = f"lock-colleague-{uuid.uuid4()}"
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, owner_chat = _chat(engine, owner=owner)
        _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
        colleague_chat = _second_chat_in_same_task(engine, task_id, created_by=colleague)

        for conversation_id, user_id in ((colleague_chat, colleague), (owner_chat, owner)):
            with engine.begin() as conn:
                issued = _statements(conn)
                chat_turns._phase_one_turn(
                    conn,
                    task_id=task_id,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    message="a question",
                    client_turn_id=uuid.uuid4(),
                )
            locking = [statement for statement in issued if "FOR UPDATE" in statement]
            assert len(locking) == 1, locking
            assert "FOR UPDATE OF conversation" in locking[0]
            # The lock target is named explicitly, so the joined task row
            # is read but never locked.
            assert "FOR UPDATE OF task" not in locking[0]
    finally:
        _cleanup(engine, task_id)
