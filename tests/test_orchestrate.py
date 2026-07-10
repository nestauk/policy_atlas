"""Scripted-IO tests for the orchestrator CLI (task 017, the public interface).

Everything is stubbed and egress-free: the stub planner, stub runner backends
(with empty search backends so acquire is a no-op over the seeded fixture
corpus) and a scripted console that feeds deterministic answers.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.engine import Engine

from policy_atlas.orchestrate import UnattendedIO, main
from policy_atlas.orchestration_plan import OrchestrationPlan
from policy_atlas.planner import _STUB_SUGGESTED_ANSWERS, StubPlannerBackend
from policy_atlas.planner_prompt import PlanDraftWire, PlannerTurnWire
from policy_atlas.runner import RunnerBackends
from policy_atlas.schema import evidence_scope, orchestration_plan, runs, synthesis_result
from tests.helpers import delete_project_data


@pytest.fixture(autouse=True)
def _stub_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the egress-free stub path regardless of a local .env key."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


class ScriptedConsole:
    """Deterministic console double: feeds queued answers, records output."""

    def __init__(self, inputs: list[str]) -> None:
        self._inputs = list(inputs)
        self.output: list[str] = []

    def prompt(self, message: str) -> str:
        self.output.append(message)
        if not self._inputs:
            raise AssertionError(f"ScriptedConsole ran out of input at prompt: {message!r}")
        value = self._inputs.pop(0)
        self.output.append(value)
        return value

    def print(self, message: str) -> None:
        self.output.append(message)


def _stub_backends() -> RunnerBackends:
    # Empty search backends -> acquire adds nothing; the run walks the seeded
    # fixture corpus only, keeping the test fast and deterministic.
    return RunnerBackends(search_backends=[])


def _cleanup(engine: Engine, project_id: uuid.UUID | None) -> None:
    if project_id is None:
        return
    with engine.begin() as conn:
        conn.execute(
            delete(orchestration_plan).where(orchestration_plan.c.project_id == project_id)
        )
        delete_project_data(conn, project_id)


def _printed(console: ScriptedConsole, needle: str) -> bool:
    return any(needle in line for line in console.output)


def test_full_stub_end_to_end_mints_artefact(engine: Engine) -> None:
    """Intent -> pick suggestion 1 -> approve -> a full stub run mints an artefact."""
    result = None
    try:
        console = ScriptedConsole(
            [
                "What works to reduce childhood obesity?",  # intent
                "1",  # answer the shape question by picking suggestion 1
                "approve",  # plan review
                "1",  # deepening-selection steer point: continue
                "1",  # before-synthesise pause: continue
            ]
        )
        result = main(console, engine=engine, backends=_stub_backends())

        assert result.exit_code == 0
        assert result.outcome is not None
        assert result.outcome.status == "succeeded"
        assert result.artefact_present is True
        assert _printed(console, "Flagged event collation")

        assert result.project_id is not None
        assert result.plan is not None
        with engine.connect() as conn:
            plan_row = conn.execute(
                select(orchestration_plan).where(
                    orchestration_plan.c.project_id == result.project_id
                )
            ).one()
            scope_row = conn.execute(
                select(evidence_scope).where(evidence_scope.c.project_id == result.project_id)
            ).one()
            run_rows = conn.execute(
                select(runs.c.run_id).where(runs.c.project_id == result.project_id)
            ).fetchall()
            synth_rows = conn.execute(
                select(synthesis_result.c.synthesis_result_id).where(
                    synthesis_result.c.project_id == result.project_id
                )
            ).fetchall()

        assert plan_row.version == 1
        assert plan_row.status == "approved"
        assert plan_row.created_by == "user"
        assert plan_row.approved_at is not None
        assert plan_row.evidence_scope_id == scope_row.evidence_scope_id
        # The persisted payload re-validates as an OrchestrationPlan.
        OrchestrationPlan.model_validate(plan_row.payload)
        # The scope intent is the refined question. (The context is created
        # empty by the CLI, then populated by the runner's directive deltas.)
        assert scope_row.intent == result.plan.question
        # One run row per composed step, and a synthesis artefact exists.
        assert len(run_rows) == len(result.outcome.steps)
        assert len(synth_rows) == 1
    finally:
        _cleanup(engine, result.project_id if result else None)


def test_landscape_sentinel_composes_without_deep_chain(engine: Engine) -> None:
    """A landscape-only answer yields a landscape plan with no select/extract/group."""
    result = None
    try:
        console = ScriptedConsole(
            [
                "Map the evidence base on childhood obesity (landscape only)",  # intent
                "landscape only",  # answer triggers the stub landscape draft
                "approve",
                "1",  # before-synthesise pause (moderate, no select boundary): continue
            ]
        )
        result = main(console, engine=engine, backends=_stub_backends())

        assert result.exit_code == 0
        assert result.plan is not None
        assert result.plan.analysis_depth == "landscape"
        assert result.plan.components == ["characterise"]

        assert result.outcome is not None
        components = [step.component for step in result.outcome.steps]
        assert "characterise" in components
        assert "select" not in components
        assert "extract" not in components
        assert "group" not in components

        with engine.connect() as conn:
            run_rows = conn.execute(
                select(runs.c.run_id).where(runs.c.project_id == result.project_id)
            ).fetchall()
        assert len(run_rows) == len(components)
    finally:
        _cleanup(engine, result.project_id if result else None)


def test_numbered_suggestion_pick_lands_in_turns(engine: Engine) -> None:
    """Answering '2' resolves to the stub's second suggested answer in the turn log."""
    result = None
    try:
        console = ScriptedConsole(
            [
                "What works to reduce childhood obesity?",
                "2",  # pick the second suggested answer
                "approve",
                "1",
                "1",
            ]
        )
        result = main(console, engine=engine, backends=_stub_backends())

        second_suggestion = _STUB_SUGGESTED_ANSWERS[1]
        user_texts = [turn["text"] for turn in result.turns if turn["role"] == "user"]
        assert second_suggestion in user_texts
    finally:
        _cleanup(engine, result.project_id if result else None)


def test_abandon_at_review_creates_no_rows(engine: Engine) -> None:
    """Abandoning at the approval prompt leaves no project/scope/plan rows."""
    console = ScriptedConsole(
        [
            "What works to reduce childhood obesity?",
            "1",
            "abandon",  # abandon at review, before anything is created
        ]
    )
    result = main(console, engine=engine, backends=_stub_backends())

    # Nothing was created: project/scope/plan rows only ever exist on approval,
    # so an abandoned session leaves nothing to clean up.
    assert result.exit_code == 4
    assert result.project_id is None
    assert result.outcome is None
    assert result.plan is None


def test_validation_failure_is_fail_closed_and_runs_nothing(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An invalid ready draft never runs a chain; the surfaced error then abandons."""

    def invalid_plan_turn(
        self: StubPlannerBackend,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
    ) -> PlannerTurnWire:
        del self, previous_draft
        return PlannerTurnWire(
            reply="Stub: emitting an intentionally invalid draft.",
            plan_draft=PlanDraftWire(
                title="Invalid",
                question=turns[0]["text"],
                backend_scope="both",
                search_effort="standard",
                analysis_depth="standard",
                components=["not_a_real_component"],
                steering_mode="moderate",
            ),
            question=None,
            suggested_answers=None,
            ready=True,
        )

    monkeypatch.setattr(StubPlannerBackend, "plan_turn", invalid_plan_turn)

    console = ScriptedConsole(
        [
            "What works to reduce childhood obesity?",
            "abandon",  # surfaced validation error -> abandon
        ]
    )
    result = main(console, engine=engine, backends=_stub_backends())

    assert result.exit_code == 4
    assert result.outcome is None
    assert result.project_id is None
    assert _printed(console, "failed validation")


class _UnattendedPlanner:
    """Planner double that proposes a ready, valid, unattended plan immediately."""

    mode = "stub"

    def plan_turn(
        self,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
    ) -> PlannerTurnWire:
        del previous_draft
        return PlannerTurnWire(
            reply="Unattended plan proposed.",
            plan_draft=PlanDraftWire(
                title="Unattended review",
                question=turns[0]["text"],
                backend_scope="both",
                search_effort="standard",
                # 018 regrade: select/extract/group are deep-only now.
                analysis_depth="deep",
                components=["characterise", "screen_stage2", "select", "extract", "group"],
                grouping_facet="outcome",
                steering_mode="unattended",
                assumptions=["Stub: unattended proposal."],
            ),
            question=None,
            suggested_answers=None,
            ready=True,
        )


def test_unattended_run_never_pauses(engine: Engine) -> None:
    """An unattended plan runs end-to-end with UnattendedIO and never pauses."""
    result = None
    try:
        console = ScriptedConsole(
            [
                "What works to reduce childhood obesity?",
                "approve",  # no shape question from this planner double
            ]
        )
        result = main(
            console,
            engine=engine,
            planner=_UnattendedPlanner(),
            backends=_stub_backends(),
        )

        assert result.exit_code == 0
        assert result.outcome is not None
        assert result.outcome.status in {"succeeded", "degraded"}
        assert isinstance(result.runner_io, UnattendedIO)
        assert result.runner_io.pause_calls == 0
        assert result.plan is not None
        assert result.plan.steering_mode == "unattended"
    finally:
        _cleanup(engine, result.project_id if result else None)


def test_turn_cap_exhaustion_exits_no_plan_not_abandoned(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A planner that never converges is a system failure, not user abandonment."""

    def never_ready(
        self: StubPlannerBackend,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
    ) -> PlannerTurnWire:
        del self, previous_draft
        return PlannerTurnWire(
            reply="Stub: still thinking.",
            plan_draft=PlanDraftWire(question=turns[0]["text"]),
            question="What is the scope?",
            suggested_answers=None,
            ready=False,
        )

    monkeypatch.setattr(StubPlannerBackend, "plan_turn", never_ready)

    console = ScriptedConsole(
        ["What works to reduce childhood obesity?"] + ["anything"] * 10
    )
    result = main(console, engine=engine, backends=_stub_backends())

    assert result.exit_code == 2
    assert result.plan is None
    assert result.project_id is None
    assert _printed(console, "turn cap")


def test_planner_declared_steer_point_defaults_reach_the_plan(engine: Engine) -> None:
    """The wire model carries steer_point_defaults through to the validated plan."""

    class _DefaultsPlanner:
        mode = "stub"

        def plan_turn(
            self,
            turns: list[dict[str, str]],
            previous_draft: dict[str, object] | None,
        ) -> PlannerTurnWire:
            del previous_draft
            return PlannerTurnWire(
                reply="Unattended plan with pre-declared defaults.",
                plan_draft=PlanDraftWire(
                    title="Unattended review",
                    question=turns[0]["text"],
                    backend_scope="both",
                    search_effort="standard",
                    # 018 regrade: select/extract/group are deep-only now.
                    analysis_depth="deep",
                    components=["characterise", "screen_stage2", "select", "extract", "group"],
                    grouping_facet="outcome",
                    steering_mode="unattended",
                    steer_point_defaults=[
                        {"steer_point": "deepening_selection", "action": "stop"}
                    ],
                    assumptions=["Stub: unattended proposal."],
                ),
                question=None,
                suggested_answers=None,
                ready=True,
            )

    result = None
    try:
        console = ScriptedConsole(
            ["What works to reduce childhood obesity?", "approve"]
        )
        result = main(
            console,
            engine=engine,
            planner=_DefaultsPlanner(),
            backends=_stub_backends(),
        )

        assert result.plan is not None
        assert [d.model_dump() for d in result.plan.steer_point_defaults] == [
            {"steer_point": "deepening_selection", "action": "stop"}
        ]
        assert _printed(console, "steer_point_defaults")
    finally:
        _cleanup(engine, result.project_id if result else None)


def test_planner_draft_author_affiliation_countries_reach_the_plan(engine: Engine) -> None:
    """The draft's flat author_affiliation_countries folds into scope_constraints,
    mirroring how publisher_country already folds via _build_plan.
    """

    class _ScopedPlanner:
        mode = "stub"

        def plan_turn(
            self,
            turns: list[dict[str, str]],
            previous_draft: dict[str, object] | None,
        ) -> PlannerTurnWire:
            del previous_draft
            return PlannerTurnWire(
                reply="Plan scoped to GB/US author affiliations.",
                plan_draft=PlanDraftWire(
                    title="Scoped review",
                    question=turns[0]["text"],
                    backend_scope="both",
                    search_effort="standard",
                    analysis_depth="landscape",
                    components=["characterise"],
                    steering_mode="moderate",
                    author_affiliation_countries=["gb", "us"],
                    assumptions=["Stub: scoped proposal."],
                ),
                question=None,
                suggested_answers=None,
                ready=True,
            )

    result = None
    try:
        console = ScriptedConsole(
            ["What works to reduce childhood obesity?", "approve"]
        )
        result = main(
            console,
            engine=engine,
            planner=_ScopedPlanner(),
            backends=_stub_backends(),
        )

        assert result.plan is not None
        assert result.plan.scope_constraints.author_affiliation_countries == ["GB", "US"]
    finally:
        _cleanup(engine, result.project_id if result else None)


def test_std_console_strips_terminal_control_sequences(capsys: pytest.CaptureFixture[str]) -> None:
    from policy_atlas.orchestrate import StdConsole

    StdConsole().print("Title\x1b]0;pwned\x07\x1b[2J\nsafe\tline")
    captured = capsys.readouterr()
    assert captured.out == "Title]0;pwned[2J\nsafe\tline\n"
