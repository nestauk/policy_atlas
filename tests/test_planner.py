"""Tests for the planner backend seam."""

from __future__ import annotations

import uuid
from types import TracebackType
from typing import Any, Literal, cast

import pytest

from policy_atlas.orchestration_plan import OrchestrationPlan
from policy_atlas.planner import (
    OpenAIPlannerBackend,
    PlannerBackend,
    StubPlannerBackend,
    _degrade_suggestions,
)
from policy_atlas.planner_prompt import PlanDraftWire, PlannerTurnWire


def _turn(text: str, role: str = "user") -> dict[str, str]:
    return {"role": role, "text": text}


def _plan_from_draft(draft: PlanDraftWire) -> OrchestrationPlan:
    """Build an OrchestrationPlan from a stub draft's non-null fields.

    Unset draft fields fall back to OrchestrationPlan's own defaults (e.g.
    ``scoping_notes``); derived fields (``expected_artefact_shape``,
    ``time_band``) are always computed code-side by the model validator.
    """
    data = {key: value for key, value in draft.model_dump().items() if value is not None}
    return OrchestrationPlan(**data)


# --- Stub turn shapes -------------------------------------------------------


def test_stub_first_turn_asks_shape_question_with_three_suggestions() -> None:
    backend = StubPlannerBackend()
    turn = backend.plan_turn([_turn("Do school meals improve attainment?")], None)

    assert turn.ready is False
    assert turn.question == "What decision should this evidence review inform?"
    assert turn.suggested_answers is not None
    assert len(turn.suggested_answers) == 3
    assert turn.plan_draft.question == "Do school meals improve attainment?"
    assert turn.plan_draft.backend_scope == "both"


def test_stub_second_turn_returns_complete_ready_draft() -> None:
    backend = StubPlannerBackend()
    turns = [
        _turn("Do school meals improve attainment?"),
        _turn("A one-off briefing", role="planner"),
    ]
    turn = backend.plan_turn(turns, None)

    assert turn.ready is True
    assert turn.question is None
    assert turn.suggested_answers is None
    draft = turn.plan_draft
    assert draft.title == "Evidence review"
    assert draft.question == "Do school meals improve attainment?"
    assert draft.search_effort == "standard"
    assert draft.analysis_depth == "deep"
    assert draft.components == ["characterise", "screen_stage2", "select", "extract", "group"]
    assert draft.component_rationale is not None
    assert set(draft.component_rationale) == set(draft.components)
    assert draft.steering_mode == "moderate"
    assert draft.grouping_facet == "outcome"
    assert draft.assumptions == ["Stub planner: deterministic fixture proposal."]


def test_stub_landscape_sentinel_yields_landscape_draft() -> None:
    backend = StubPlannerBackend()
    turns = [
        _turn("Map the evidence base on school meals."),
        _turn("landscape only", role="user"),
    ]
    turn = backend.plan_turn(turns, None)

    assert turn.ready is True
    draft = turn.plan_draft
    assert draft.analysis_depth == "landscape"
    assert draft.components == ["characterise"]
    assert draft.grouping_facet is None


def test_stub_is_deterministic() -> None:
    backend = StubPlannerBackend()
    turns = [_turn("Do school meals improve attainment?")]

    first = backend.plan_turn(turns, None)
    second = backend.plan_turn(turns, None)

    assert first.model_dump() == second.model_dump()


def test_stub_satisfies_protocol() -> None:
    backend: PlannerBackend = StubPlannerBackend()
    assert backend.mode == "stub"


# --- Stub draft round-trips into a valid OrchestrationPlan -----------------


def test_stub_ready_draft_round_trips_into_orchestration_plan() -> None:
    backend = StubPlannerBackend()
    turns = [
        _turn("Do school meals improve attainment?"),
        _turn("A one-off briefing", role="planner"),
    ]
    turn = backend.plan_turn(turns, None)

    plan = _plan_from_draft(turn.plan_draft)

    assert plan.components == ["characterise", "screen_stage2", "select", "extract", "group"]
    assert plan.grouping_facet == "outcome"
    assert plan.time_band
    assert plan.expected_artefact_shape


def test_stub_landscape_draft_round_trips_into_orchestration_plan() -> None:
    backend = StubPlannerBackend()
    turns = [
        _turn("Map the evidence base on school meals."),
        _turn("landscape only", role="user"),
    ]
    turn = backend.plan_turn(turns, None)

    plan = _plan_from_draft(turn.plan_draft)

    assert plan.analysis_depth == "landscape"
    assert plan.components == ["characterise"]
    assert plan.grouping_facet is None


# --- Suggestion degrade ------------------------------------------------------


def _turn_wire(
    *,
    question: str | None,
    suggested_answers: list[str] | None,
) -> PlannerTurnWire:
    return PlannerTurnWire(
        reply="reply",
        plan_draft=PlanDraftWire(),
        question=question,
        suggested_answers=suggested_answers,
        ready=False,
    )


def test_degrade_one_suggestion_forces_none() -> None:
    turn = _turn_wire(question="q?", suggested_answers=["only one"])

    result = _degrade_suggestions(turn)

    assert result.suggested_answers is None
    assert result.question == "q?"


def test_degrade_six_suggestions_forces_none() -> None:
    turn = _turn_wire(question="q?", suggested_answers=[f"answer {i}" for i in range(6)])

    result = _degrade_suggestions(turn)

    assert result.suggested_answers is None


def test_degrade_empty_string_entry_forces_none() -> None:
    turn = _turn_wire(question="q?", suggested_answers=["a", "", "b"])

    result = _degrade_suggestions(turn)

    assert result.suggested_answers is None


def test_degrade_three_good_suggestions_kept() -> None:
    turn = _turn_wire(question="q?", suggested_answers=["a", "b", "c"])

    result = _degrade_suggestions(turn)

    assert result.suggested_answers == ["a", "b", "c"]


def test_degrade_no_question_forces_suggestions_none() -> None:
    turn = _turn_wire(question=None, suggested_answers=["a", "b", "c"])

    result = _degrade_suggestions(turn)

    assert result.suggested_answers is None
    assert result.question is None


# --- OpenAI backend key resolution (no network) -----------------------------


def test_openai_planner_backend_satisfies_protocol(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    backend: PlannerBackend = OpenAIPlannerBackend(api_key="sk-test")
    assert backend.mode == "live"


def test_openai_planner_backend_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIPlannerBackend()


class _FakeParsedMessage:
    def __init__(self, parsed: PlannerTurnWire) -> None:
        self.parsed = parsed


class _FakeChoice:
    def __init__(self, parsed: PlannerTurnWire) -> None:
        self.message = _FakeParsedMessage(parsed)


class _FakeResponse:
    usage = None

    def __init__(self, parsed: PlannerTurnWire) -> None:
        self.choices = [_FakeChoice(parsed)]


class _FakeCompletions:
    def __init__(self, parsed: PlannerTurnWire) -> None:
        self._parsed = parsed

    def parse(self, **kwargs: Any) -> _FakeResponse:
        del kwargs
        return _FakeResponse(self._parsed)


class _FakeChat:
    def __init__(self, parsed: PlannerTurnWire) -> None:
        self.completions = _FakeCompletions(parsed)


class _FakeOpenAIClient:
    def __init__(self, parsed: PlannerTurnWire) -> None:
        self.chat = _FakeChat(parsed)


class _FakeSpan:
    def update(self, **payload: Any) -> None:
        del payload


class _FakeObservation:
    def __enter__(self) -> _FakeSpan:
        return _FakeSpan()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        del exc_type, exc, traceback
        return False


class _FakeLangfuse:
    def __init__(self) -> None:
        self.sessions: list[str] = []

    def start_as_current_observation(self, *, name: str, as_type: str) -> _FakeObservation:
        del name, as_type
        return _FakeObservation()

    def update_current_trace(self, *, session_id: str) -> None:
        self.sessions.append(session_id)


def test_openai_planner_turn_sets_langfuse_session() -> None:
    session_id = uuid.uuid4()
    parsed = PlannerTurnWire(
        reply="Ready.",
        plan_draft=PlanDraftWire(title="Session test", question="Q?"),
        question=None,
        suggested_answers=None,
        ready=False,
    )
    backend: OpenAIPlannerBackend = object.__new__(OpenAIPlannerBackend)
    fake_langfuse = _FakeLangfuse()
    cast("Any", backend)._client = _FakeOpenAIClient(parsed)
    cast("Any", backend)._langfuse_client = fake_langfuse

    backend.plan_turn([_turn("Q?")], None, session_id=session_id)

    assert fake_langfuse.sessions == [str(session_id)]


def test_scrub_turn_removes_nul_from_nested_plan_draft() -> None:
    from policy_atlas.planner import _scrub_turn
    from policy_atlas.planner_prompt import PlanDraftWire, PlannerTurnWire

    turn = PlannerTurnWire(
        reply="ok\x00",
        plan_draft=PlanDraftWire(
            title="T\x00itle",
            scoping_notes=["a\x00b"],
            component_rationale={"characterise": "c\x00d"},
        ),
        question=None,
        suggested_answers=None,
        ready=False,
    )
    scrubbed = _scrub_turn(turn)
    assert scrubbed.reply == "ok"
    assert scrubbed.plan_draft.title == "Title"
    assert scrubbed.plan_draft.scoping_notes == ["ab"]
    assert scrubbed.plan_draft.component_rationale == {"characterise": "cd"}
