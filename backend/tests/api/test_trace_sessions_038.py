"""Task 038 V9: one Langfuse session per Task, not per conversation.

Covers invariant I9 across the three call sites the slice touches (planning
turn, chat turn, run start) plus the steering-continuation path the runner
already threaded ``session_id`` through unmodified: with a stub Langfuse
client, every trace groups under ``session_id == str(task_id)``, and the chat
(and planning) turn's metadata still carries its ``conversation_id``.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from types import TracebackType
from typing import Any, Literal, cast

import pytest
from sqlalchemy.engine import Engine

from policy_atlas.core import tracing
from policy_atlas.runtime.continuation_state import ResumeDecision, build
from policy_atlas.runtime.planner import OpenAIPlannerBackend
from policy_atlas.runtime.planner_prompt import PlanDraftWire, PlannerTurnWire
from policy_atlas.runtime.runner import NullIO, RunnerBackends, run_plan
from tests.helpers import fake_parse_client
from tests.runtime.test_continuation_parity import _ParkOnceIO
from tests.runtime.test_runner import _base_plan, _seed_task
from tests.runtime.test_steering import _cleanup_task, _insert_plan_row


class _RecordingSpan:
    """Fake Langfuse span that records every ``update(...)`` call verbatim."""

    def __init__(self, sink: list[dict[str, Any]]) -> None:
        self._sink = sink

    def update(self, **payload: Any) -> None:
        self._sink.append(payload)


class _RecordingObservation:
    def __init__(self, sink: list[dict[str, Any]]) -> None:
        self._sink = sink

    def __enter__(self) -> _RecordingSpan:
        return _RecordingSpan(self._sink)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        del exc_type, exc, traceback
        return False


class _RecordingLangfuse:
    """Fake Langfuse client: every observation shares one update sink."""

    def __init__(self, sink: list[dict[str, Any]]) -> None:
        self._sink = sink

    def start_as_current_observation(self, *, name: str, as_type: str) -> _RecordingObservation:
        del name, as_type
        return _RecordingObservation(self._sink)


def _patch_propagate_attributes(
    monkeypatch: pytest.MonkeyPatch, sink: list[str]
) -> None:
    """Record every ``session_id`` a traced call propagates onto its scope.

    ``core.tracing._session_scope`` always converts to ``str`` before calling
    ``propagate_attributes`` (the installed Langfuse SDK has no
    ``update_current_trace``); patching it here is the same seam
    ``tests/runtime/test_planner.py`` uses for the planner alone.
    """

    @contextmanager
    def fake_propagate_attributes(*, session_id: str) -> Iterator[None]:
        sink.append(session_id)
        yield

    monkeypatch.setattr(tracing, "propagate_attributes", fake_propagate_attributes)


def test_planning_turn_session_is_task_id_and_metadata_carries_conversation_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The planning-turn generation span groups by task id, not conversation id."""
    task_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    session_events: list[str] = []
    _patch_propagate_attributes(monkeypatch, session_events)

    updates: list[dict[str, Any]] = []
    fake_langfuse = _RecordingLangfuse(updates)

    parsed = PlannerTurnWire(
        reply="Ready.",
        plan_draft=PlanDraftWire(title="Trace test", question="Q?"),
        question=None,
        suggested_answers=None,
        ready=False,
    )
    backend: OpenAIPlannerBackend = object.__new__(OpenAIPlannerBackend)
    cast("Any", backend)._client = fake_parse_client(parsed=parsed)
    cast("Any", backend)._langfuse_client = fake_langfuse

    backend.plan_turn(
        [{"role": "user", "text": "Q?"}],
        None,
        session_id=task_id,
        conversation_id=conversation_id,
    )

    assert session_events == [str(task_id)]
    assert updates
    assert updates[-1]["metadata"]["conversation_id"] == str(conversation_id)


def test_chat_component_span_session_is_task_id_and_metadata_carries_conversation_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``component_span`` (the chat turn's root span) groups by task id.

    Mirrors the call at ``api/chat_turns.py`` line ~927: ``session_id`` is now
    the task id and ``conversation_id`` rides in the root span's metadata next
    to ``task_id``.
    """
    task_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    run_id = uuid.uuid4()
    session_events: list[str] = []
    _patch_propagate_attributes(monkeypatch, session_events)

    updates: list[dict[str, Any]] = []
    fake_langfuse = _RecordingLangfuse(updates)

    with tracing.component_span(
        cast("Any", fake_langfuse),
        run_id=run_id,
        task_id=task_id,
        component="chat_v1",
        session_id=task_id,
        conversation_id=conversation_id,
    ):
        pass

    assert session_events == [str(task_id)]
    assert updates[0]["metadata"] == {
        "task_id": str(task_id),
        "run_id": str(run_id),
        "conversation_id": str(conversation_id),
    }


def test_run_start_and_steering_continuation_session_is_task_id(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run's component spans, before and after a steering park, group by task id.

    The runner already threads ``session_id`` through ``ContinuationState``
    (``cap["session_id"]``) unmodified; this exercises that path end to end
    with the new call site (``routers/runs.py`` now passes
    ``session_id=task_id`` into ``run_plan``) to confirm both the initial
    walk and its resumed continuation still open every component span under
    the task's session.
    """
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        plan = _base_plan(steering_mode="frequent", search_effort="standard")
        plan_id = _insert_plan_row(engine, task_id=task_id, scope_id=scope_id, plan=plan)

        session_events: list[str] = []
        _patch_propagate_attributes(monkeypatch, session_events)
        backends = RunnerBackends(
            search_backends=[], langfuse_client=cast("Any", _RecordingLangfuse([]))
        )

        parked_io = _ParkOnceIO()
        parked = run_plan(
            engine,
            task_id=task_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=backends,
            io=parked_io,
            session_id=task_id,
        )
        assert parked.status == "paused"
        assert parked.capability_run_id is not None
        state = build(engine, task_id=task_id, capability_run_id=parked.capability_run_id)
        assert state.session_id == task_id

        resumed = run_plan(
            engine,
            task_id=task_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=backends,
            io=NullIO(),
            resume_from=state,
            resume_decision=ResumeDecision(response="continue"),
        )
        assert resumed.status == "succeeded"

        # At least one component span opened on each side of the park, and
        # every one of them groups under the task id.
        assert session_events
        assert set(session_events) == {str(task_id)}
    finally:
        _cleanup_task(engine, task_id)
