"""Task Agent turns taken while a scoping walk is paused on its baseline gate.

Task 044, phase 5.4. The gate is the one place where the chat and the check-in
card speak about the same thing at the same time, so what these tests own is the
seam between them:

- a non-approving turn is **admitted** while the walk is paused, sorted, and
  dispatched — an answer over the paused walk's own evidence, a decision through
  the check-in transaction, or an honest ask-back;
- a decision lands **once**, whichever surface takes it (A13, C5);
- "Change the plan" carrying an instruction is **one turn with two commits**: the
  walk ends, and the same transcript row goes on to mint the next plan version
  (X6) — including when the second half fails and is retried;
- everything else about the fence is unchanged: the approving branch and
  ``PATCH /plan`` stay refused, a running walk stays refused, and an Evidence
  search pause refuses turns exactly as it always did (A6).
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.engine import Engine

from policy_atlas.api import gate_turns
from policy_atlas.api.continuation import answer_check_in
from policy_atlas.api.deps import (
    get_agent_backend,
    get_chat_backend,
    get_runner_backends,
    get_scoping_task_agent_backend,
)
from policy_atlas.api.routers import task_agent as task_agent_router
from policy_atlas.core import events
from policy_atlas.core.schema import (
    artefact,
    capability_run,
    evidence_scope,
    task_agent_transcript,
    task_plan,
)
from policy_atlas.runtime.agent_backend import StubAgentBackend
from policy_atlas.runtime.capability_registry import OPTIONS_SCOPING
from policy_atlas.runtime.chat_backend import StubChatBackend
from policy_atlas.runtime.gate_sort_prompt import GateSortWire
from policy_atlas.runtime.task_agent_scoping import (
    NO_BASELINE_STATE,
    StubScopingTaskAgentBackend,
)
from policy_atlas.runtime.task_agent_scoping_prompt import (
    LinkedTaskContext,
    ScopingPlanDraftWire,
    ScopingTurnWire,
)
from tests.api.resource_support import api_client, create_task
from tests.api.test_answer_core import _citing_tools, _first_seeded_chunk
from tests.api.test_baseline_gate_checkin import _own, _park_at_gate
from tests.helpers import now
from tests.runtime.test_runner import _cleanup, _runner_backends

_CHANGE_WHERE = "Change it to England only"


# --- doubles ----------------------------------------------------------------


class _ReadyScopingAgent:
    """A scoping Task Agent that approves a plan on every turn.

    The parked task has no planning conversation behind it (the runner seeded
    the walk), so the deterministic stub would need three turns to become
    ready. What these tests are about is the *row* that mints the version, not
    the conversation that reaches it.
    """

    def __init__(self, *, fail_first: bool = False) -> None:
        self.messages: list[str] = []
        self.baseline_states: list[str] = []
        self.fail_first = fail_first

    def scope_turn(
        self,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        linked_context: list[LinkedTaskContext] | None = None,
        baseline_state: str = NO_BASELINE_STATE,
        session_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> ScopingTurnWire:
        """Return one ready scoping turn, optionally failing the first call."""
        del previous_draft, linked_context, session_id, conversation_id
        self.messages.append(turns[-1]["text"] if turns else "")
        self.baseline_states.append(baseline_state)
        if self.fail_first and len(self.messages) == 1:
            raise RuntimeError("planned test failure after the decision commit")
        draft = ScopingPlanDraftWire.model_validate(
            {
                "title": "Youth employment options",
                "question": "What could reduce the number of young people not in work?",
                "intended_change": {
                    "text": "Reduce the number of young people not in work",
                    "origin": "from_your_question",
                },
                "target_unit": {"text": "16 to 24 year olds", "origin": "your_call"},
                "where": {"text": "England", "origin": "your_call"},
                "outcomes": [{"text": "the NEET rate", "origin": "assumed"}],
                "depth": "standard",
            }
        )
        return ScopingTurnWire(reply="Plan updated.", plan_draft=draft, ready=True)


class _RunStartsMeanwhileAgent(_ReadyScopingAgent):
    """A ready Task Agent that lets a walk start during the planner call (P16)."""

    def __init__(self, engine: Engine, task_id: uuid.UUID) -> None:
        super().__init__()
        self._engine = engine
        self._task_id = task_id

    def scope_turn(self, *args: Any, **kwargs: Any) -> ScopingTurnWire:
        """Open a paused walk, then return the ready turn the fence must refuse."""
        turn = super().scope_turn(*args, **kwargs)
        with self._engine.begin() as conn:
            row = conn.execute(
                select(task_plan)
                .where(task_plan.c.task_id == self._task_id)
                .where(task_plan.c.status == "approved")
                .order_by(task_plan.c.version.desc())
                .limit(1)
            ).mappings().one()
            conn.execute(
                capability_run.insert().values(
                    capability_run_id=uuid.uuid4(),
                    task_id=self._task_id,
                    evidence_scope_id=row["evidence_scope_id"],
                    capability=OPTIONS_SCOPING,
                    plan_id=row["plan_id"],
                    plan_version=row["version"],
                    status="paused",
                    started_at=datetime.now(UTC),
                )
            )
        return turn


# --- fixtures and helpers ---------------------------------------------------


def _sorts(*verdicts: GateSortWire) -> StubAgentBackend:
    return StubAgentBackend(gate_sort_responses=list(verdicts))


def _question() -> GateSortWire:
    return GateSortWire(kind="question", reason="It asks about the baseline.")


def _decision(option_id: str, carried_text: str | None = None) -> GateSortWire:
    return GateSortWire(
        kind="decision",
        option_id=option_id,
        carried_text=carried_text,
        reason="It chooses an offered option.",
    )


def _overrides(
    *,
    agent: StubAgentBackend | None = None,
    scoping_agent: object | None = None,
) -> dict[Callable[..., object], Callable[..., object]]:
    """Route every backend the turn route may reach to a deterministic double."""
    resolved_agent = agent if agent is not None else StubAgentBackend()
    resolved_scoping = (
        scoping_agent if scoping_agent is not None else StubScopingTaskAgentBackend()
    )
    return {
        get_agent_backend: lambda: resolved_agent,
        get_scoping_task_agent_backend: lambda: resolved_scoping,
        get_chat_backend: lambda: StubChatBackend(),
        get_runner_backends: _runner_backends,
    }


def _turn(
    client: TestClient,
    headers: dict[str, str],
    task_id: uuid.UUID,
    message: str,
    *,
    client_turn_id: uuid.UUID | None = None,
) -> Any:
    return client.post(
        f"/api/v1/tasks/{task_id}/task-agent-turns",
        headers=headers,
        json={
            "message": message,
            "client_turn_id": str(client_turn_id or uuid.uuid4()),
        },
    )


def _decision_events(engine: Engine, task_id: uuid.UUID) -> list[dict[str, Any]]:
    """Return the decisions taken *at the gate* — the walk's own boundaries aside."""
    with engine.connect() as conn:
        return [
            entry["payload"]
            for entry in events.read(conn, task_id)
            if entry["event_type"] == "steering.decision"
            and entry["payload"].get("component") == "synthesise"
        ]


def _walk_status(engine: Engine, capability_run_id: uuid.UUID) -> str:
    with engine.connect() as conn:
        return str(
            conn.execute(
                select(capability_run.c.status).where(
                    capability_run.c.capability_run_id == capability_run_id
                )
            ).scalar_one()
        )


def _await_walk_ended(
    engine: Engine, capability_run_id: uuid.UUID, *, transient: tuple[str, ...] = ("running",)
) -> str:
    """Wait for a background walk to settle before the test tears its rows down."""
    deadline = time.monotonic() + 30.0
    status = _walk_status(engine, capability_run_id)
    while status in transient and time.monotonic() < deadline:
        time.sleep(0.05)
        status = _walk_status(engine, capability_run_id)
    return status


def _await_quiet(engine: Engine, task_id: uuid.UUID | None) -> None:
    """Let a longlist walk a decision opened, and its option searches, stop running.

    The walk may end, or park at a fired check-in; its children run on their
    own pool and must not be writing while the test tears the task down.
    """
    if task_id is None:
        return
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            running = conn.execute(
                select(capability_run.c.capability_run_id)
                .where(capability_run.c.task_id == task_id)
                .where(capability_run.c.status == "running")
            ).first()
        if running is None:
            return
        time.sleep(0.05)


def _rows(engine: Engine, task_id: uuid.UUID) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        return [
            dict(row)
            for row in conn.execute(
                select(task_agent_transcript)
                .where(task_agent_transcript.c.task_id == task_id)
                .order_by(task_agent_transcript.c.turn_index.asc())
            ).mappings()
        ]


def _plans(engine: Engine, task_id: uuid.UUID) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        return [
            dict(row)
            for row in conn.execute(
                select(task_plan)
                .where(task_plan.c.task_id == task_id)
                .order_by(task_plan.c.version.asc())
            ).mappings()
        ]


def _baseline_artefact_id(engine: Engine, task_id: uuid.UUID) -> str:
    with engine.connect() as conn:
        pause = next(
            entry
            for entry in reversed(events.read(conn, task_id))
            if entry["event_type"] == "steering.pause"
        )
    return str(pause["payload"]["bundle"]["artefact_id"])


# --- a question -------------------------------------------------------------


def test_a_question_at_the_gate_is_answered_from_the_baseline(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The turn is admitted while paused and answered with resolved citations."""
    task_id: uuid.UUID | None = None
    try:
        task_id, walk_id, _check_in_id, _plan_id = _park_at_gate(engine)
        chunk_id, title = _first_seeded_chunk(engine, task_id)
        monkeypatch.setattr(gate_turns, "build_section_tools", _citing_tools(chunk_id))
        with api_client(tmp_path, _overrides(agent=_sorts(_question()))) as (
            client,
            owner,
            _other,
        ):
            _own(engine, task_id, owner)
            response = _turn(client, owner, task_id, "Is the rise in the baseline real?")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["kind"] == "answer"
        assert body["answer"]["citations"][0]["id"] == chunk_id
        assert body["answer"]["citations"][0]["source_title"] == title
        assert body["decision"] is None
        # The decision stays the user's to take — never inferred from a question.
        assert body["suggestions"] == [
            "Confirm plan and build longlist",
            "Change the plan",
        ]
        assert gate_turns.OFFER_SENTENCE in body["reply"]
        assert _walk_status(engine, walk_id) == "paused"
        assert _decision_events(engine, task_id) == []
        stored = _rows(engine, task_id)[-1]
        assert stored["status"] == "completed"
        assert stored["response"]["kind"] == "answer"
        assert stored["task_agent_state"] is None
    finally:
        _cleanup(engine, task_id)


def test_the_answer_turn_reloads_from_the_transcript_as_an_answer(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reloaded thread renders the citations, not a bare reply."""
    task_id: uuid.UUID | None = None
    try:
        task_id, _walk_id, _check_in_id, _plan_id = _park_at_gate(engine)
        chunk_id, _title = _first_seeded_chunk(engine, task_id)
        monkeypatch.setattr(gate_turns, "build_section_tools", _citing_tools(chunk_id))
        with api_client(tmp_path, _overrides(agent=_sorts(_question()))) as (
            client,
            owner,
            _other,
        ):
            _own(engine, task_id, owner)
            _turn(client, owner, task_id, "Which sources say the offer works?")
            listed = client.get(
                f"/api/v1/tasks/{task_id}/task-agent-turns", headers=owner
            )
        assert listed.status_code == 200, listed.text
        turn = listed.json()["data"][-1]
        assert turn["kind"] == "answer"
        assert turn["answer"]["citations"][0]["id"] == chunk_id
        assert turn["decision"] is None
    finally:
        _cleanup(engine, task_id)


def test_a_gate_answer_carries_the_appraisal_label_not_the_score(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C2: the score is the durable fact; the wire carries the derived label.

    ``appraise`` pins its labels as read-time copy, so a citation persists the
    numeric score and every read boundary derives the chip's label from it.
    The chat route already does this; a Task Agent answer carries the same
    payload and owes the same boundary — on the POST and on the transcript.
    """
    task_id: uuid.UUID | None = None
    try:
        task_id, _walk_id, _check_in_id, _plan_id = _park_at_gate(engine)
        chunk_id, _title = _first_seeded_chunk(engine, task_id)
        monkeypatch.setattr(gate_turns, "build_section_tools", _citing_tools(chunk_id))
        with api_client(tmp_path, _overrides(agent=_sorts(_question()))) as (
            client,
            owner,
            _other,
        ):
            _own(engine, task_id, owner)
            posted = _turn(client, owner, task_id, "How good is that source?")
            listed = client.get(
                f"/api/v1/tasks/{task_id}/task-agent-turns", headers=owner
            )

        assert posted.status_code == 200, posted.text
        stored = _rows(engine, task_id)[-1]["response"]["answer"]["citations"][0]
        assert stored["appraisal_score"] is not None
        assert "appraisal_label" not in stored
        on_the_wire = (
            posted.json()["answer"]["citations"][0],
            listed.json()["data"][-1]["answer"]["citations"][0],
        )
        for citation in on_the_wire:
            assert "appraisal_score" not in citation
            assert citation["appraisal_label"]
    finally:
        _cleanup(engine, task_id)


def test_a_question_that_loses_the_race_to_the_card_is_not_a_500(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C7: the walk was resumed mid-sort, so there is nothing to answer over.

    The turn is the user's and it is durable either way; what it must not be
    is an internal error.
    """
    task_id: uuid.UUID | None = None
    try:
        task_id, walk_id, _check_in_id, _plan_id = _park_at_gate(engine)
        monkeypatch.setattr(
            gate_turns, "resolve_run_components", lambda *_args, **_kwargs: None
        )
        with api_client(tmp_path, _overrides(agent=_sorts(_question()))) as (
            client,
            owner,
            _other,
        ):
            _own(engine, task_id, owner)
            response = _turn(client, owner, task_id, "Is the rise real?")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["kind"] == "reply"
        assert body["reply"] == gate_turns.ALREADY_ANSWERED_REPLY
        assert body["answer"] is None and body["decision"] is None
        assert _rows(engine, task_id)[-1]["status"] == "completed"
        # Nothing was applied: the walk is where the card left it.
        assert _walk_status(engine, walk_id) == "paused"
        assert _decision_events(engine, task_id) == []
    finally:
        _cleanup(engine, task_id)


# --- a decision in words ----------------------------------------------------


def test_a_decision_in_words_lands_in_the_check_in_transaction(
    engine: Engine, tmp_path: Path
) -> None:
    """Bound to the run, the check-in and the plan version (C5) — it ends the walk
    and opens the longlist walk."""
    task_id: uuid.UUID | None = None
    try:
        task_id, walk_id, check_in_id, _plan_id = _park_at_gate(engine)
        with api_client(tmp_path, _overrides(agent=_sorts(_decision("confirm_plan")))) as (
            client,
            owner,
            _other,
        ):
            _own(engine, task_id, owner)
            response = _turn(client, owner, task_id, "Looks right, go ahead")
            assert response.status_code == 200, response.text
            ended = _await_walk_ended(engine, walk_id, transient=("paused", "running"))

        body = response.json()
        assert body["kind"] == "decision"
        assert body["reply"] == gate_turns.CONFIRM_REPLY
        opened = body["decision"].pop("opened_run")
        assert body["decision"] == {
            "option_id": "confirm_plan",
            "label": "Confirm plan and build longlist",
            "check_in_id": str(check_in_id),
            "capability_run_id": str(walk_id),
            "plan_version": 1,
        }
        decision = _decision_events(engine, task_id)[-1]
        assert decision["response"] == "continue"
        assert decision["plan_version"] == 1
        # The decision ends the baseline walk (task 045) ...
        assert ended == "succeeded"
        # ... and opens the longlist walk on the confirmed version, returned on
        # the decision (task 045, S3; P7).
        assert opened is not None
        with engine.connect() as conn:
            record = conn.execute(
                select(evidence_scope.c.purpose, evidence_scope.c.plan_id)
                .select_from(
                    capability_run.join(
                        evidence_scope,
                        evidence_scope.c.evidence_scope_id
                        == capability_run.c.evidence_scope_id,
                    )
                )
                .where(
                    capability_run.c.capability_run_id
                    == uuid.UUID(opened["capability_run_id"])
                )
            ).one()
        assert record.purpose == "longlist"
        assert record.plan_id == _plan_id
    finally:
        _await_quiet(engine, task_id)
        _cleanup(engine, task_id)


def test_a_confirm_whose_longlist_did_not_open_says_so(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F12: the decision stands, but no walk opened — the reply must not say
    the longlist is being built."""
    from policy_atlas.api.longlist_start import LonglistRefused
    from policy_atlas.api.routers import task_agent as task_agent_router

    def refuse(*args: Any, **kwargs: Any) -> uuid.UUID:
        raise LonglistRefused("capacity", "the walk executor is at capacity")

    monkeypatch.setattr(task_agent_router, "open_longlist_walk", refuse)
    task_id: uuid.UUID | None = None
    try:
        task_id, walk_id, _check_in_id, _plan_id = _park_at_gate(engine)
        with api_client(tmp_path, _overrides(agent=_sorts(_decision("confirm_plan")))) as (
            client,
            owner,
            _other,
        ):
            _own(engine, task_id, owner)
            response = _turn(client, owner, task_id, "Looks right, go ahead")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["decision"]["opened_run"] is None
        assert body["reply"] == gate_turns.CONFIRM_NOT_STARTED_REPLY
        assert _decision_events(engine, task_id)[-1]["response"] == "continue"
    finally:
        _await_quiet(engine, task_id)
        _cleanup(engine, task_id)


def test_one_decision_survives_a_race_between_the_chat_and_the_card(
    engine: Engine, tmp_path: Path
) -> None:
    """A13: two surfaces, one durable decision — and the losing turn stays durable.

    The barrier holds the chat turn *after* it has been admitted and its gate
    read — the window in which both surfaces believe the check-in is open —
    while the card commits on another thread against the same engine. The chat
    then meets the durable decision under the task lock.
    """
    task_id: uuid.UUID | None = None
    try:
        task_id, walk_id, check_in_id, _plan_id = _park_at_gate(engine)
        admitted = threading.Barrier(2)
        card_committed = threading.Event()
        card: dict[str, Any] = {}

        class _RacingSort(StubAgentBackend):
            """Hold the admitted turn open until the card has committed."""

            def sort_gate_turn(self, *args: Any, **kwargs: Any) -> GateSortWire:
                admitted.wait(timeout=30)
                card_committed.wait(timeout=30)
                return _decision("change_plan")

        def answer_from_the_card() -> None:
            admitted.wait(timeout=30)
            try:
                card["result"] = answer_check_in(
                    engine,
                    task_id=task_id,
                    check_in_id=check_in_id,
                    response={"kind": "option", "option_id": "change_plan"},
                    actor="card-user",
                )
            except Exception as exc:  # noqa: BLE001 — the race's loser is the point
                card["error"] = exc
            finally:
                card_committed.set()

        with api_client(tmp_path, _overrides(agent=_RacingSort())) as (
            client,
            owner,
            _other,
        ):
            _own(engine, task_id, owner)
            thread = threading.Thread(target=answer_from_the_card)
            thread.start()
            response = _turn(client, owner, task_id, "Change the plan")
            thread.join(timeout=30)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["kind"] == "decision"
        # One durable decision, one durable turn saying what happened to it.
        assert len(_decision_events(engine, task_id)) == 1
        assert "error" not in card
        assert _walk_status(engine, walk_id) == "aborted"
        assert body["decision"] is None
        assert body["reply"] == gate_turns.ALREADY_ANSWERED_REPLY
        assert _rows(engine, task_id)[-1]["status"] == "completed"
    finally:
        _cleanup(engine, task_id)


# --- change the plan: one turn, two commits (X6) -----------------------------


def test_change_the_plan_with_an_instruction_ends_the_walk_and_replans(
    engine: Engine, tmp_path: Path
) -> None:
    """The same row records the decision and mints the next plan version."""
    task_id: uuid.UUID | None = None
    try:
        task_id, walk_id, check_in_id, plan_id = _park_at_gate(engine)
        agent = _ReadyScopingAgent()
        with api_client(
            tmp_path,
            _overrides(
                agent=_sorts(_decision("change_plan", _CHANGE_WHERE)),
                scoping_agent=agent,
            ),
        ) as (client, owner, _other):
            _own(engine, task_id, owner)
            response = _turn(client, owner, task_id, f"No — {_CHANGE_WHERE}")
            plan_read = client.get(f"/api/v1/tasks/{task_id}/plan", headers=owner)

        assert response.status_code == 200, response.text
        body = response.json()
        # Both halves are this one turn's.
        assert body["kind"] == "decision"
        assert body["decision"]["option_id"] == "change_plan"
        assert body["decision"]["capability_run_id"] == str(walk_id)
        assert body["decision"]["check_in_id"] == str(check_in_id)
        assert body["scoping_plan"]["ready"] is True
        assert body["reply"].startswith("Plan updated.")
        # S4: the code-authored sentence names the baseline input that moved.
        assert "built from plan version 1) was built from: Where" in body["reply"]
        # The planner answered the carried instruction, not the whole utterance.
        assert agent.messages == [_CHANGE_WHERE]

        assert _walk_status(engine, walk_id) == "aborted"
        plans = _plans(engine, task_id)
        assert [plan["version"] for plan in plans] == [1, 2]
        assert plans[0]["plan_id"] == plan_id
        assert plans[1]["status"] == "approved"
        assert plans[1]["payload"]["where"]["text"] == "England"
        assert plan_read.status_code == 200, plan_read.text
        assert plan_read.json()["version"] == 2
        # One transcript row carries the decision and the reply.
        assert len(_rows(engine, task_id)) == 1
    finally:
        _cleanup(engine, task_id)


def test_a_carried_instruction_the_user_never_typed_falls_back_to_the_utterance(
    engine: Engine, tmp_path: Path
) -> None:
    """S2: the planner's message is the user's own words, not the sort's.

    ``carried_text`` is the one piece of the sort's output treated as the user
    speaking, so a paraphrase is refused and the whole utterance stands in.
    """
    task_id: uuid.UUID | None = None
    try:
        task_id, _walk_id, _check_in_id, _plan_id = _park_at_gate(engine)
        agent = _ReadyScopingAgent()
        utterance = "No — make it England only"
        with api_client(
            tmp_path,
            _overrides(
                # A paraphrase: nothing the user typed.
                agent=_sorts(
                    _decision("change_plan", "Restrict the geography to England")
                ),
                scoping_agent=agent,
            ),
        ) as (client, owner, _other):
            _own(engine, task_id, owner)
            response = _turn(client, owner, task_id, utterance)

        assert response.status_code == 200, response.text
        assert agent.messages == [utterance]
    finally:
        _cleanup(engine, task_id)


def test_a_carried_instruction_is_kept_when_it_is_the_user_s_own_words() -> None:
    """The accepting branch, including the spellings a quote legitimately changes."""
    check_in_id = uuid.uuid4()
    kept = gate_turns.verbatim_carried_text(
        # Quoted across a line break and lowercased at the sentence start.
        "change it\nto  England only",
        utterance="No — Change it to England only",
        check_in_id=check_in_id,
    )
    assert kept == "change it\nto  England only"
    assert (
        gate_turns.verbatim_carried_text(
            None, utterance="No", check_in_id=check_in_id
        )
        is None
    )
    assert (
        gate_turns.verbatim_carried_text(
            "   ", utterance="No", check_in_id=check_in_id
        )
        is None
    )


def test_a_replayed_gate_turn_returns_its_stored_projection(
    engine: Engine, tmp_path: Path
) -> None:
    """The idempotency key still replays, sort or no sort (X6)."""
    task_id: uuid.UUID | None = None
    try:
        task_id, _walk_id, _check_in_id, _plan_id = _park_at_gate(engine)
        agent = _ReadyScopingAgent()
        client_turn_id = uuid.uuid4()
        with api_client(
            tmp_path,
            _overrides(
                agent=_sorts(_decision("change_plan", _CHANGE_WHERE)),
                scoping_agent=agent,
            ),
        ) as (client, owner, _other):
            _own(engine, task_id, owner)
            first = _turn(
                client, owner, task_id, "Change it", client_turn_id=client_turn_id
            )
            second = _turn(
                client, owner, task_id, "Change it", client_turn_id=client_turn_id
            )

        assert first.status_code == second.status_code == 200, second.text
        assert first.json() == second.json()
        # The replay re-ran nothing: one planner call, one decision, one row.
        assert len(agent.messages) == 1
        assert len(_decision_events(engine, task_id)) == 1
        assert len(_rows(engine, task_id)) == 1
        assert len(_plans(engine, task_id)) == 2
    finally:
        _cleanup(engine, task_id)


def test_a_failure_after_the_decision_leaves_it_durable_and_the_retry_replans(
    engine: Engine, tmp_path: Path
) -> None:
    """Partial failure, then a retry that re-runs only the planning half (X6)."""
    task_id: uuid.UUID | None = None
    try:
        task_id, walk_id, check_in_id, _plan_id = _park_at_gate(engine)
        agent = _ReadyScopingAgent(fail_first=True)
        client_turn_id = uuid.uuid4()
        with api_client(
            tmp_path,
            _overrides(
                agent=_sorts(_decision("change_plan", _CHANGE_WHERE)),
                scoping_agent=agent,
            ),
        ) as (client, owner, _other):
            _own(engine, task_id, owner)
            failed = _turn(
                client, owner, task_id, "Change it", client_turn_id=client_turn_id
            )
            assert failed.status_code == 500, failed.text
            assert _walk_status(engine, walk_id) == "aborted"
            assert len(_decision_events(engine, task_id)) == 1
            assert _rows(engine, task_id)[-1]["status"] == "failed"
            assert len(_plans(engine, task_id)) == 1

            retried = _turn(
                client, owner, task_id, "Change it", client_turn_id=client_turn_id
            )

        assert retried.status_code == 200, retried.text
        # Only the planning half re-ran: the walk was already ended, so the
        # fence saw no gate and the sort was not consulted again.
        assert len(_decision_events(engine, task_id)) == 1
        assert len(_plans(engine, task_id)) == 2
        assert _rows(engine, task_id)[-1]["status"] == "completed"
        # And the completed turn still reports the decision that ended the
        # walk, read back off the half this row recorded before the crash
        # (X6) — not a bare planning reply that loses it.
        body = retried.json()
        assert body["kind"] == "decision"
        # "Change the plan" opens no walk (task 045: only the confirm does).
        assert body["decision"].pop("opened_run") is None
        assert body["decision"] == {
            "option_id": "change_plan",
            "label": "Change the plan",
            "check_in_id": str(check_in_id),
            "capability_run_id": str(walk_id),
            "plan_version": 1,
        }
    finally:
        _cleanup(engine, task_id)


# --- the two actions the plan document then offers (C1, C3) ------------------


def test_rebuilding_after_a_change_runs_the_new_version(
    engine: Engine, tmp_path: Path
) -> None:
    """Rebuild opens a walk on the new plan version's own scope row (C3)."""
    task_id: uuid.UUID | None = None
    try:
        task_id, _walk_id, _check_in_id, _plan_id = _park_at_gate(engine)
        with api_client(
            tmp_path,
            _overrides(
                agent=_sorts(_decision("change_plan", _CHANGE_WHERE)),
                scoping_agent=_ReadyScopingAgent(),
            ),
        ) as (client, owner, _other):
            _own(engine, task_id, owner)
            _turn(client, owner, task_id, f"No — {_CHANGE_WHERE}")
            started = client.post(
                f"/api/v1/tasks/{task_id}/runs", headers=owner, json={}
            )
            assert started.status_code == 201, started.text
            rebuilt_id = uuid.UUID(started.json()["capability_run_id"])
            _await_walk_ended(engine, rebuilt_id)

        plans = _plans(engine, task_id)
        with engine.connect() as conn:
            walk = conn.execute(
                select(capability_run).where(
                    capability_run.c.capability_run_id == rebuilt_id
                )
            ).mappings().one()
            scope = conn.execute(
                select(evidence_scope).where(
                    evidence_scope.c.evidence_scope_id == plans[1]["evidence_scope_id"]
                )
            ).mappings().one()
        assert walk["plan_version"] == 2
        assert walk["evidence_scope_id"] == plans[1]["evidence_scope_id"]
        assert scope["plan_id"] == plans[1]["plan_id"]
        assert scope["purpose"] == "baseline"
        assert scope["context"]["where"] == "England"
    finally:
        _cleanup(engine, task_id)


def test_confirming_without_rebuilding_records_both_versions(
    engine: Engine, tmp_path: Path
) -> None:
    """Confirm after a change records the artefact and the version it came from."""
    task_id: uuid.UUID | None = None
    try:
        task_id, _walk_id, _check_in_id, _plan_id = _park_at_gate(engine)
        artefact_id = _baseline_artefact_id(engine, task_id)
        with api_client(
            tmp_path,
            _overrides(
                agent=_sorts(_decision("change_plan", _CHANGE_WHERE)),
                scoping_agent=_ReadyScopingAgent(),
            ),
        ) as (client, owner, _other):
            _own(engine, task_id, owner)
            _turn(client, owner, task_id, f"No — {_CHANGE_WHERE}")
            confirmed = client.post(
                f"/api/v1/tasks/{task_id}/plan/confirm-baseline",
                headers=owner,
                # The user confirms the version on screen (2, the changed plan)
                # against the baseline built from version 1.
                json={"artefact_id": artefact_id, "plan_version": 2},
            )

        assert confirmed.status_code == 200, confirmed.text
        body = confirmed.json()
        assert body["version"] == 3
        # The record is minted as version 3 and names it (044 live-check fix);
        # the baseline's own version (1) is on the walk it points at.
        assert body["scoping"]["baseline_confirmed"] == {
            "artefact_id": artefact_id,
            "plan_version": 3,
        }
        assert body["scoping"]["where"]["text"] == "England"
        # The confirm opened the longlist walk on version 3 (task 045, S3).
        assert body["opened_run"] is not None
    finally:
        _await_quiet(engine, task_id)
        _cleanup(engine, task_id)


# --- the honest refusals ----------------------------------------------------


def test_an_unsortable_turn_is_asked_back_and_applies_nothing(
    engine: Engine, tmp_path: Path
) -> None:
    """The stub's default verdict is unsure; the product says what is available."""
    task_id: uuid.UUID | None = None
    try:
        task_id, walk_id, _check_in_id, _plan_id = _park_at_gate(engine)
        with api_client(tmp_path, _overrides()) as (client, owner, _other):
            _own(engine, task_id, owner)
            response = _turn(client, owner, task_id, "Search for more evidence first")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["kind"] == "reply"
        assert body["reply"] == gate_turns.ASK_BACK_REPLY
        assert body["suggestions"] == [
            "Confirm plan and build longlist",
            "Change the plan",
        ]
        assert body["decision"] is None and body["answer"] is None
        assert _walk_status(engine, walk_id) == "paused"
        assert _decision_events(engine, task_id) == []
    finally:
        _cleanup(engine, task_id)


def test_a_decision_naming_an_unoffered_option_is_asked_back(
    engine: Engine, tmp_path: Path
) -> None:
    """Fail safe: an option the card never offered is never applied."""
    task_id: uuid.UUID | None = None
    try:
        task_id, walk_id, _check_in_id, _plan_id = _park_at_gate(engine)
        with api_client(
            tmp_path, _overrides(agent=_sorts(_decision("start_the_longlist")))
        ) as (client, owner, _other):
            _own(engine, task_id, owner)
            response = _turn(client, owner, task_id, "Start the assessment")

        assert response.json()["reply"] == gate_turns.ASK_BACK_REPLY
        assert _walk_status(engine, walk_id) == "paused"
        assert _decision_events(engine, task_id) == []
    finally:
        _cleanup(engine, task_id)


def test_a_turn_while_the_walk_is_running_is_still_refused(
    engine: Engine, tmp_path: Path
) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, walk_id, _check_in_id, _plan_id = _park_at_gate(engine)
        with api_client(tmp_path, _overrides(agent=_sorts(_question()))) as (
            client,
            owner,
            _other,
        ):
            _own(engine, task_id, owner)
            # After the client's startup sweep, which honestly interrupts any
            # walk it finds running.
            with engine.begin() as conn:
                conn.execute(
                    update(capability_run)
                    .where(capability_run.c.capability_run_id == walk_id)
                    .values(status="running")
                )
            response = _turn(client, owner, task_id, "Is the rise real?")
        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "run_active"
    finally:
        _cleanup(engine, task_id)


def test_patching_the_plan_while_paused_is_still_refused(
    engine: Engine, tmp_path: Path
) -> None:
    """A6: the fence the gate does not lift."""
    task_id: uuid.UUID | None = None
    try:
        task_id, _walk_id, _check_in_id, _plan_id = _park_at_gate(engine)
        with api_client(tmp_path, _overrides()) as (client, owner, _other):
            _own(engine, task_id, owner)
            refused = client.patch(
                f"/api/v1/tasks/{task_id}/plan",
                headers=owner,
                json={"scoping": {"depth": "rapid"}},
            )
        assert refused.status_code == 409, refused.text
        assert refused.json()["error"]["code"] == "run_active"
    finally:
        _cleanup(engine, task_id)


def test_an_evidence_search_pause_still_refuses_turns(
    engine: Engine, tmp_path: Path
) -> None:
    """ES is unchanged: its pause is answered on the card, never in the chat."""
    with api_client(tmp_path, _overrides(agent=_sorts(_question()))) as (
        client,
        owner,
        _other,
    ):
        task_id = uuid.UUID(create_task(client, owner))
        try:
            first = _turn(client, owner, task_id, "What works for youth employment?")
            assert first.status_code == 200, first.text
            second = _turn(client, owner, task_id, "A one-off briefing")
            assert second.status_code == 200, second.text
            with engine.begin() as conn:
                row = conn.execute(
                    select(task_plan)
                    .where(task_plan.c.task_id == task_id)
                    .where(task_plan.c.status == "approved")
                    .order_by(task_plan.c.version.desc())
                    .limit(1)
                ).mappings().one()
                conn.execute(
                    capability_run.insert().values(
                        capability_run_id=uuid.uuid4(),
                        task_id=task_id,
                        evidence_scope_id=row["evidence_scope_id"],
                        capability="evidence_search",
                        plan_id=row["plan_id"],
                        plan_version=row["version"],
                        status="paused",
                        started_at=now(),
                    )
                )
            refused = _turn(client, owner, task_id, "Is the rise real?")
            assert refused.status_code == 409, refused.text
            assert refused.json()["error"]["code"] == "run_active"
        finally:
            _cleanup(engine, task_id)


def test_the_approving_branch_refuses_a_run_that_started_meanwhile(
    engine: Engine, tmp_path: Path
) -> None:
    """P16: fence 2 is driven by the race it exists for, not by a paused gate."""
    task_id: uuid.UUID | None = None
    try:
        task_id, walk_id, check_in_id, _plan_id = _park_at_gate(engine)
        with api_client(
            tmp_path,
            _overrides(scoping_agent=_RunStartsMeanwhileAgent(engine, task_id)),
        ) as (client, owner, _other):
            _own(engine, task_id, owner)
            # End the parked walk first, so the turn below is an ordinary
            # planning turn — the only kind that reaches the approving branch.
            answer_check_in(
                engine,
                task_id=task_id,
                check_in_id=check_in_id,
                response={"kind": "option", "option_id": "change_plan"},
                actor="user-1",
            )
            assert _walk_status(engine, walk_id) == "aborted"
            refused = _turn(client, owner, task_id, "Make it England")

        assert refused.status_code == 409, refused.text
        assert refused.json()["error"]["code"] == "run_active"
        assert len(_plans(engine, task_id)) == 1
        assert _rows(engine, task_id)[-1]["status"] == "failed"
    finally:
        _cleanup(engine, task_id)


# --- the sort's own fail-safe -----------------------------------------------


def _bare_gate() -> gate_turns.PausedGate:
    return gate_turns.PausedGate(
        capability_run_id=uuid.uuid4(),
        check_in_id=uuid.uuid4(),
        plan_version=1,
        options=(("confirm_plan", "Confirm plan and build longlist"),),
        artefact_id=None,
    )


def test_a_backend_failure_sorts_as_unsure() -> None:
    """A sort that cannot be read asks back; it never guesses a decision."""

    class _Broken(StubAgentBackend):
        def sort_gate_turn(self, *args: Any, **kwargs: Any) -> GateSortWire:
            raise RuntimeError("no verdict")

    verdict = gate_turns.sort_turn(_Broken(), utterance="Confirm", gate=_bare_gate())
    assert verdict.kind == "unsure"


def test_a_decision_without_an_option_sorts_as_unsure() -> None:
    verdict = gate_turns.sort_turn(
        _sorts(GateSortWire(kind="decision", reason="No option named.")),
        utterance="Do it",
        gate=_bare_gate(),
    )
    assert verdict.kind == "unsure"


# --- the prompt's view of a paused walk -------------------------------------


def test_an_aborted_walk_that_wrote_nothing_is_not_a_baseline(engine: Engine) -> None:
    """C5: the artefact is the evidence a baseline exists, not the walk's status.

    A walk aborted at a floor pause after acquire never wrote a baseline. Told
    one existed, the Task Agent would announce an artefact the user has never
    seen and the S4 sentence would fire about it.
    """
    from tests.runtime.test_baseline_gate import (
        insert_scoping_plan_row,
        scoping_plan,
        seed_scoping_task,
    )

    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = seed_scoping_task(engine)
        plan_id = insert_scoping_plan_row(
            engine, task_id=task_id, scope_id=scope_id, plan=scoping_plan()
        )
        walk_id = uuid.uuid4()
        with engine.begin() as conn:
            conn.execute(
                capability_run.insert().values(
                    capability_run_id=walk_id,
                    task_id=task_id,
                    evidence_scope_id=scope_id,
                    capability=OPTIONS_SCOPING,
                    plan_id=plan_id,
                    plan_version=1,
                    status="aborted",
                    started_at=now(),
                    ended_at=now(),
                )
            )
        with engine.connect() as conn:
            assert task_agent_router._baseline_state(conn, task_id) == NO_BASELINE_STATE

        # The same walk, once it has an artefact against its name.
        with engine.begin() as conn:
            conn.execute(
                artefact.insert().values(
                    artefact_id=uuid.uuid4(),
                    task_id=task_id,
                    capability_run_id=walk_id,
                    title="Baseline",
                    created_at=now(),
                )
            )
        with engine.connect() as conn:
            line = task_agent_router._baseline_state(conn, task_id)
        assert line == "a baseline exists, built from plan version 1"
    finally:
        _cleanup(engine, task_id)


def test_the_baseline_state_line_says_the_walk_is_paused(engine: Engine) -> None:
    """The planner must never propose starting a run that is already parked."""
    task_id: uuid.UUID | None = None
    try:
        task_id, _walk_id, _check_in_id, _plan_id = _park_at_gate(engine)
        with engine.connect() as conn:
            line = task_agent_router._baseline_state(conn, task_id)
        assert line.startswith("paused on the baseline")
        assert "plan version 1" in line
    finally:
        _cleanup(engine, task_id)
