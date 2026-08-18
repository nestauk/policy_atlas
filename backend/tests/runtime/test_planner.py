"""Tests for the planner backend seam."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from types import TracebackType
from typing import Any, Literal, cast

import pytest

from policy_atlas.core import tracing
from policy_atlas.evidence_base.extract.extract import KNOWN_PROFILE_IDS
from policy_atlas.runtime.orchestration_plan import OrchestrationPlan, compose
from policy_atlas.runtime.planner import (
    OpenAIPlannerBackend,
    PlannerBackend,
    StubPlannerBackend,
    _degrade_suggestions,
)
from policy_atlas.runtime.planner_prompt import (
    PLANNER_PROMPT_VERSION,
    PLANNER_SYSTEM_PROMPT,
    PlanDraftWire,
    PlannerTurnWire,
)
from tests.helpers import fake_parse_client


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


def test_planner_prompt_version_pinned() -> None:
    # planner_v8: Analysis level screen words; report not review; search caps.
    assert PLANNER_PROMPT_VERSION == "planner_v8"


def test_planner_prompt_plain_language_and_ready_update() -> None:
    assert "## How to talk" in PLANNER_SYSTEM_PROMPT
    assert "Never name internals" in PLANNER_SYSTEM_PROMPT
    assert 'Never say "nothing runs until you start it"' in PLANNER_SYSTEM_PROMPT
    assert "on an update" in PLANNER_SYSTEM_PROMPT


def test_planner_prompt_thoroughness_screen_words_and_caps() -> None:
    assert 'label "Standard report"' in PLANNER_SYSTEM_PROMPT
    assert 'label "Detailed report"' in PLANNER_SYSTEM_PROMPT
    assert "up to 50 relevant results per database" in PLANNER_SYSTEM_PROMPT
    assert "up to 100 relevant results per database" in PLANNER_SYSTEM_PROMPT
    assert "up to 200 relevant results per database" in PLANNER_SYSTEM_PROMPT
    assert "Evidence overview / Full-text synthesis / Findings synthesis" in PLANNER_SYSTEM_PROMPT
    assert "Standard review" not in PLANNER_SYSTEM_PROMPT
    assert "Detailed review" not in PLANNER_SYSTEM_PROMPT


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
    assert draft.components == ["characterise", "screen_full", "select", "extract", "group"]
    assert draft.component_rationale is not None
    assert set(draft.component_rationale) == set(draft.components)
    assert draft.steering_mode == "unattended"
    assert draft.grouping_facets == ["outcome"]
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
    assert draft.grouping_facets is None


def test_stub_is_deterministic() -> None:
    backend = StubPlannerBackend()
    turns = [_turn("Do school meals improve attainment?")]

    first = backend.plan_turn(turns, None)
    second = backend.plan_turn(turns, None)

    assert first.model_dump() == second.model_dump()


def test_stub_satisfies_protocol() -> None:
    backend: PlannerBackend = StubPlannerBackend()
    assert isinstance(backend, StubPlannerBackend)


# --- Stub draft round-trips into a valid OrchestrationPlan -----------------


def test_stub_ready_draft_round_trips_into_orchestration_plan() -> None:
    backend = StubPlannerBackend()
    turns = [
        _turn("Do school meals improve attainment?"),
        _turn("A one-off briefing", role="planner"),
    ]
    turn = backend.plan_turn(turns, None)

    plan = _plan_from_draft(turn.plan_draft)

    assert plan.components == ["characterise", "screen_full", "select", "extract", "group"]
    assert plan.grouping_facets == ["outcome"]
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
    assert plan.grouping_facets is None


def test_planner_draft_with_select_at_standard_round_trips_into_orchestration_plan() -> None:
    """019 select-at-standard regrade: a planner draft may compose select at
    standard depth (without the findings chain) and still validate.
    """
    draft = PlanDraftWire(
        title="Evidence review",
        question="Do school meals improve attainment?",
        backend_scope="both",
        search_effort="standard",
        analysis_depth="standard",
        components=["characterise", "select"],
        component_rationale={
            "characterise": "Maps the corpus landscape before deeper analysis.",
            "select": "Selects the strongest-fit documents to guide synthesis emphasis.",
        },
        steering_mode="moderate",
    )

    plan = _plan_from_draft(draft)

    assert plan.analysis_depth == "standard"
    assert plan.components == ["characterise", "select"]
    assert "extract" not in plan.components
    assert "group" not in plan.components


def test_planner_draft_extract_profiles_round_trips_into_orchestration_plan() -> None:
    draft = PlanDraftWire(
        title="Evidence review",
        question="Do school meals improve attainment?",
        backend_scope="both",
        search_effort="standard",
        analysis_depth="deep",
        components=["characterise", "select", "extract"],
        component_rationale={
            "characterise": "Maps the corpus landscape before deeper analysis.",
            "select": "Selects the strongest-fit documents for extraction.",
            "extract": "Extracts structured effect findings from selected documents.",
        },
        extract_profiles=["iof"],
        steering_mode="moderate",
    )

    plan = _plan_from_draft(draft)
    extract_step = next(step for step in compose(plan).steps if step.component == "extract")

    assert plan.extract_profiles == ["iof"]
    assert extract_step.directive_delta == {"extraction": {"profiles": [KNOWN_PROFILE_IDS[0]]}}


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
    assert isinstance(backend, OpenAIPlannerBackend)


def test_openai_planner_backend_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIPlannerBackend()


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
    def start_as_current_observation(self, *, name: str, as_type: str) -> _FakeObservation:
        del name, as_type
        return _FakeObservation()


def test_openai_planner_turn_propagates_session_before_opening_the_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The installed SDK (4.13.0) has no ``update_current_trace`` — the real seam is
    ``propagate_attributes``, and the whole observation must open INSIDE its scope
    (attributes only reach observations opened while the scope is active)."""
    session_id = uuid.uuid4()
    events: list[str] = []

    @contextmanager
    def fake_propagate_attributes(*, session_id: str) -> Iterator[None]:
        events.append(f"session_enter:{session_id}")
        yield
        events.append("session_exit")

    monkeypatch.setattr(tracing, "propagate_attributes", fake_propagate_attributes)

    parsed = PlannerTurnWire(
        reply="Ready.",
        plan_draft=PlanDraftWire(title="Session test", question="Q?"),
        question=None,
        suggested_answers=None,
        ready=False,
    )
    backend: OpenAIPlannerBackend = object.__new__(OpenAIPlannerBackend)
    fake_langfuse = _FakeLangfuse()
    original_start = fake_langfuse.start_as_current_observation

    def recording_start(*, name: str, as_type: str) -> _FakeObservation:
        events.append(f"observation:{name}")
        return original_start(name=name, as_type=as_type)

    fake_langfuse.start_as_current_observation = recording_start  # type: ignore[method-assign]
    cast("Any", backend)._client = fake_parse_client(parsed=parsed)
    cast("Any", backend)._langfuse_client = fake_langfuse

    backend.plan_turn([_turn("Q?")], None, session_id=session_id)

    enter_index = events.index(f"session_enter:{session_id}")
    exit_index = events.index("session_exit")
    observation_indexes = [i for i, event in enumerate(events) if event.startswith("observation:")]
    assert observation_indexes
    assert all(enter_index < index < exit_index for index in observation_indexes)


def test_scrub_turn_removes_nul_from_nested_plan_draft() -> None:
    from policy_atlas.runtime.planner import _scrub_turn
    from policy_atlas.runtime.planner_prompt import PlanDraftWire, PlannerTurnWire

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


def test_scrub_turn_removes_nul_from_part() -> None:
    import json

    from policy_atlas.runtime.planner import _scrub_turn
    from policy_atlas.runtime.planner_prompt import (
        PartChipWire,
        PartOptionWire,
        PartProposalWire,
        PlanDraftWire,
        PlannerTurnWire,
    )

    turn = PlannerTurnWire(
        reply="ok",
        plan_draft=PlanDraftWire(title="Title", question="Q?"),
        question=None,
        suggested_answers=None,
        ready=False,
        part=PartProposalWire(
            id="scope",
            step_label="Plan \x00· 2 of 3",
            title="Focus\x00 on the UK",
            chips=[
                PartChipWire(label="Since\x00 2016", kind="date_range", value='{"after": "2016"}')
            ],
            options=[
                PartOptionWire(id="confirm", label="Use\x00 this scope", primary=True),
                PartOptionWire(id="refine", label="Refine it", primary=False),
            ],
        ),
    )
    scrubbed = _scrub_turn(turn)
    assert scrubbed.part is not None
    assert "\\u0000" not in json.dumps(scrubbed.part.model_dump())
