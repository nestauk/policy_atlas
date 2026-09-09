"""Scripted-IO tests for the agent CLI (task 017, the public interface).

Everything is stubbed and egress-free: the stub planner, stub runner backends
(with empty search backends so acquire is a no-op over the seeded fixture
corpus) and a scripted console that feeds deterministic answers.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import delete, select
from sqlalchemy.engine import Engine

from policy_atlas.core.schema import (
    evidence_scope,
    grouping_result,
    runs,
    synthesis_result,
    task_plan,
)
from policy_atlas.runtime.agent import (
    _FRAME_OPTION_IDS,
    CliIO,
    UnattendedIO,
    _route_option_delta,
    main,
)
from policy_atlas.runtime.agent_backend import StubAgentBackend
from policy_atlas.runtime.agent_prompt import (
    AuthoredOptionWire,
    RouterCompileWire,
    RouterFragmentWire,
)
from policy_atlas.runtime.planner import _STUB_SUGGESTED_ANSWERS, StubPlannerBackend
from policy_atlas.runtime.planner_prompt import (
    PlanDraftWire,
    PlannerTurnWire,
    SteerPointDefaultDraft,
)
from policy_atlas.runtime.runner import RunnerBackends
from policy_atlas.runtime.steering import (
    Adjust,
    CompiledFragment,
    FanOut,
    FreeText,
    RefusedFragment,
    build_steer_point_options,
    render_authored_replacement_confirmation,
    render_check_in,
    render_collation,
    render_fanout_confirmation,
)
from policy_atlas.runtime.task_plan import TaskPlan
from tests.helpers import delete_task_data


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


def _cleanup(engine: Engine, task_id: uuid.UUID | None) -> None:
    if task_id is None:
        return
    with engine.begin() as conn:
        conn.execute(
            delete(task_plan).where(task_plan.c.task_id == task_id)
        )
        delete_task_data(conn, task_id)


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
                # Task 024 lattice: Continue ("1") at each lattice pause a
                # moderate deep run may present (P1 fires per search round —
                # task 029 runs the acquire+screen pair twice on zero-yield
                # stubs — P2 before select, P3 after select, P4 before
                # synthesise). Extra unused continues are harmless.
                "1",
                "1",
                "1",
                "1",
                "1",
                "1",
                "1",
            ]
        )
        result = main(console, engine=engine, backends=_stub_backends())

        assert result.exit_code == 0
        assert result.outcome is not None
        assert result.outcome.status == "succeeded"
        assert result.artefact_present is True
        assert _printed(console, "Flagged event collation")

        assert result.task_id is not None
        assert result.plan is not None
        with engine.connect() as conn:
            plan_row = conn.execute(
                select(task_plan).where(
                    task_plan.c.task_id == result.task_id
                )
            ).one()
            scope_row = conn.execute(
                select(evidence_scope).where(evidence_scope.c.task_id == result.task_id)
            ).one()
            run_rows = conn.execute(
                select(runs.c.run_id).where(runs.c.task_id == result.task_id)
            ).fetchall()
            synth_rows = conn.execute(
                select(synthesis_result.c.synthesis_result_id).where(
                    synthesis_result.c.task_id == result.task_id
                )
            ).fetchall()

        assert plan_row.version == 1
        assert plan_row.status == "approved"
        assert plan_row.created_by == "user"
        assert plan_row.approved_at is not None
        assert plan_row.evidence_scope_id == scope_row.evidence_scope_id
        # The persisted payload re-validates as an TaskPlan.
        TaskPlan.model_validate(plan_row.payload)
        # The scope intent is the refined question. (The context is created
        # empty by the CLI, then populated by the runner's directive deltas.)
        assert scope_row.intent == result.plan.question
        # One run row per composed step, and a synthesis artefact exists.
        assert len(run_rows) == len(result.outcome.steps)
        assert len(synth_rows) == 1
    finally:
        _cleanup(engine, result.task_id if result else None)


def test_landscape_sentinel_composes_without_deep_chain(engine: Engine) -> None:
    """A landscape-only answer yields a landscape plan with no select/extract/group."""
    result = None
    try:
        console = ScriptedConsole(
            [
                "Map the evidence base on childhood obesity (landscape only)",  # intent
                "landscape only",  # answer triggers the stub landscape draft
                "approve",
                # Landscape has no select, so no P2/P3; Continue at P1 (fired
                # per search round — two rounds on zero-yield stubs, task 029)
                # and P4 (before synthesise). Extra unused continues are
                # harmless.
                "1",
                "1",
                "1",
                "1",
                "1",
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
                select(runs.c.run_id).where(runs.c.task_id == result.task_id)
            ).fetchall()
        assert len(run_rows) == len(components)
    finally:
        _cleanup(engine, result.task_id if result else None)


def test_numbered_suggestion_pick_lands_in_turns(engine: Engine) -> None:
    """Answering '2' resolves to the stub's second suggested answer in the turn log."""
    result = None
    try:
        console = ScriptedConsole(
            [
                "What works to reduce childhood obesity?",
                "2",  # pick the second suggested answer
                "approve",
                # Continue at each lattice pause (see full-stub test).
                "1",
                "1",
                "1",
                "1",
                "1",
                "1",
                "1",
            ]
        )
        result = main(console, engine=engine, backends=_stub_backends())

        second_suggestion = _STUB_SUGGESTED_ANSWERS[1]
        user_texts = [turn["text"] for turn in result.turns if turn["role"] == "user"]
        assert second_suggestion in user_texts
    finally:
        _cleanup(engine, result.task_id if result else None)


def test_abandon_at_review_creates_no_rows(engine: Engine) -> None:
    """Abandoning at the approval prompt leaves no task/scope/plan rows."""
    console = ScriptedConsole(
        [
            "What works to reduce childhood obesity?",
            "1",
            "abandon",  # abandon at review, before anything is created
        ]
    )
    result = main(console, engine=engine, backends=_stub_backends())

    # Nothing was created: task/scope/plan rows only ever exist on approval,
    # so an abandoned session leaves nothing to clean up.
    assert result.exit_code == 4
    assert result.task_id is None
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
        *,
        session_id: uuid.UUID | None = None,
    ) -> PlannerTurnWire:
        del self, previous_draft, session_id
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
    assert result.task_id is None
    assert _printed(console, "failed validation")


class _UnattendedPlanner:
    """Planner double that proposes a ready, valid, unattended plan immediately."""

    mode = "stub"

    def plan_turn(
        self,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        session_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> PlannerTurnWire:
        del previous_draft, session_id, conversation_id
        return PlannerTurnWire(
            reply="Unattended plan proposed.",
            plan_draft=PlanDraftWire(
                title="Unattended review",
                question=turns[0]["text"],
                backend_scope="both",
                search_effort="standard",
                # 018 regrade: select/extract/group are deep-only now.
                analysis_depth="deep",
                components=["characterise", "screen_full", "select", "extract", "group"],
                grouping_facets=["outcome"],
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
        _cleanup(engine, result.task_id if result else None)


def test_turn_cap_exhaustion_exits_no_plan_not_abandoned(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A planner that never converges is a system failure, not user abandonment."""

    def never_ready(
        self: StubPlannerBackend,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        session_id: uuid.UUID | None = None,
    ) -> PlannerTurnWire:
        del self, previous_draft, session_id
        return PlannerTurnWire(
            reply="Stub: still thinking.",
            plan_draft=PlanDraftWire(question=turns[0]["text"]),
            question="What is the scope?",
            suggested_answers=None,
            ready=False,
        )

    monkeypatch.setattr(StubPlannerBackend, "plan_turn", never_ready)

    console = ScriptedConsole(["What works to reduce childhood obesity?"] + ["anything"] * 10)
    result = main(console, engine=engine, backends=_stub_backends())

    assert result.exit_code == 2
    assert result.plan is None
    assert result.task_id is None
    assert _printed(console, "turn cap")


def test_planner_declared_steer_point_defaults_reach_the_plan(engine: Engine) -> None:
    """The wire model carries steer_point_defaults through to the validated plan."""

    class _DefaultsPlanner:
        mode = "stub"

        def plan_turn(
            self,
            turns: list[dict[str, str]],
            previous_draft: dict[str, object] | None,
            *,
            session_id: uuid.UUID | None = None,
            conversation_id: uuid.UUID | None = None,
        ) -> PlannerTurnWire:
            del previous_draft, session_id, conversation_id
            return PlannerTurnWire(
                reply="Unattended plan with pre-declared defaults.",
                plan_draft=PlanDraftWire(
                    title="Unattended review",
                    question=turns[0]["text"],
                    backend_scope="both",
                    search_effort="standard",
                    # 018 regrade: select/extract/group are deep-only now.
                    analysis_depth="deep",
                    components=["characterise", "screen_full", "select", "extract", "group"],
                    grouping_facets=["outcome"],
                    steering_mode="unattended",
                    steer_point_defaults=[
                        SteerPointDefaultDraft(steer_point="deepening_selection", action="stop")
                    ],
                    assumptions=["Stub: unattended proposal."],
                ),
                question=None,
                suggested_answers=None,
                ready=True,
            )

    result = None
    try:
        console = ScriptedConsole(["What works to reduce childhood obesity?", "approve"])
        result = main(
            console,
            engine=engine,
            planner=_DefaultsPlanner(),
            backends=_stub_backends(),
        )

        assert result.plan is not None
        assert [d.model_dump() for d in result.plan.steer_point_defaults] == [
            {
                "steer_point": "deepening_selection",
                "action": "stop",
                "option_id": None,
                "delta": None,
            }
        ]
        assert _printed(console, "steer_point_defaults")
    finally:
        _cleanup(engine, result.task_id if result else None)


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
            *,
            session_id: uuid.UUID | None = None,
            conversation_id: uuid.UUID | None = None,
        ) -> PlannerTurnWire:
            del previous_draft, session_id, conversation_id
            return PlannerTurnWire(
                reply="Plan scoped to GB/US author affiliations.",
                plan_draft=PlanDraftWire(
                    title="Scoped review",
                    question=turns[0]["text"],
                    backend_scope="both",
                    search_effort="standard",
                    analysis_depth="landscape",
                    components=["characterise"],
                    steering_mode="unattended",
                    author_affiliation_countries=["gb", "us"],
                    assumptions=["Stub: scoped proposal."],
                ),
                question=None,
                suggested_answers=None,
                ready=True,
            )

    result = None
    try:
        console = ScriptedConsole(["What works to reduce childhood obesity?", "approve"])
        result = main(
            console,
            engine=engine,
            planner=_ScopedPlanner(),
            backends=_stub_backends(),
        )

        assert result.plan is not None
        assert result.plan.scope_constraints.author_affiliation_countries == ["GB", "US"]
    finally:
        _cleanup(engine, result.task_id if result else None)


def test_std_console_strips_terminal_control_sequences(capsys: pytest.CaptureFixture[str]) -> None:
    from policy_atlas.runtime.agent import StdConsole

    StdConsole().print("Title\x1b]0;pwned\x07\x1b[2J\nsafe\tline")
    captured = capsys.readouterr()
    assert captured.out == "Title]0;pwned[2J\nsafe\tline\n"


# --- Task 17: free text, confirmation, option routing, authored options -----


def _steer_point_payload(
    point_name: str,
    *,
    boundary: str,
    component: str,
    triggers: list[dict[str, Any]] | None = None,
    bundle: dict[str, Any] | None = None,
    authored_options: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """A pause payload shaped exactly as the runner assembles it (renderer input)."""
    payload: dict[str, Any] = {
        "kind": "steer_point",
        "steer_point": point_name,
        "boundary": boundary,
        "component": component,
        "options": build_steer_point_options(plan=None, point=point_name),
    }
    if triggers is not None:
        payload["triggers"] = triggers
    if bundle is not None:
        payload["bundle"] = bundle
    if authored_options is not None:
        payload["authored_options"] = authored_options
        payload["authored_by"] = "agent"
    return payload


def _canonical_number(payload: dict[str, Any], option_id: str) -> str:
    """The rendered menu number of a canonical option (1 = Continue, then floor)."""
    canonical = [o for o in payload["options"] if o["id"] not in _FRAME_OPTION_IDS]
    for index, option in enumerate(canonical):
        if option["id"] == option_id:
            return str(2 + index)
    raise AssertionError(f"{option_id!r} not a canonical option at this point")


def test_free_text_at_a_pause_returns_freetext() -> None:
    """Prose that is not a number or a menu keyword is returned as FreeText."""
    console = ScriptedConsole(["favour the strongest UK evidence"])
    io = CliIO(console)
    payload = _steer_point_payload(
        "deepening_selection", boundary="after_component", component="select"
    )
    response = io.pause(payload, "select: succeeded")
    assert isinstance(response, FreeText)
    assert response.text == "favour the strongest UK evidence"


def test_canonical_option_deltas_route_by_component() -> None:
    """Each point's non-input option maps to a component-keyed directive_deltas;
    bare selection/synthesis deltas keep the select/synthesise wrap."""
    cases = [
        (
            "search_review",
            "after_component",
            "acquire",
            "deepen_search",
            {"acquire": {"search": {"depth": "deep"}}},
        ),
        (
            "deepening_selection",
            "after_component",
            "select",
            "strongest_evidence",
            {"select": {"selection": {"weight_emphasis": {"quality": 2.0}}}},
        ),
        (
            "finding_groups",
            "after_component",
            "group",
            "regroup_granularity",
            {"group": {"grouping": {"granularity": "coarser"}}},
        ),
        (
            "synthesis_shape",
            "before_component",
            "synthesise",
            "emphasis_boosts",
            {"synthesise": {"synthesis": {"retrieval_boosts": {"appraisal_tier": {"5": 2.0}}}}},
        ),
    ]
    for point_name, boundary, component, option_id, expected in cases:
        payload = _steer_point_payload(point_name, boundary=boundary, component=component)
        console = ScriptedConsole([_canonical_number(payload, option_id)])
        response = CliIO(console).pause(payload, "check-in")
        assert isinstance(response, Adjust), option_id
        assert response.directive_deltas == expected, option_id


def test_route_option_delta_wraps_only_bare_selection_and_synthesis() -> None:
    """The routing helper wraps bare selection/synthesis; leaves component keys alone."""
    assert _route_option_delta({"selection": {"budget": 10}}) == {
        "select": {"selection": {"budget": 10}}
    }
    assert _route_option_delta({"synthesis": {"sections": []}}) == {
        "synthesise": {"synthesis": {"sections": []}}
    }
    assert _route_option_delta({"acquire": {"search": {"depth": "deep"}}}) == {
        "acquire": {"search": {"depth": "deep"}}
    }
    assert _route_option_delta({"group": {"grouping": {"granularity": "finer"}}}) == {
        "group": {"grouping": {"granularity": "finer"}}
    }


def test_confirm_yes_no_and_default() -> None:
    """confirm() prints the render, is True only on an explicit yes, else False."""
    render = "Steering interpretation — confirm to apply:\n- 'x' -> group"
    assert CliIO(ScriptedConsole(["y"])).confirm(render) is True
    assert CliIO(ScriptedConsole(["yes"])).confirm(render) is True
    assert CliIO(ScriptedConsole(["n"])).confirm(render) is False
    console = ScriptedConsole([""])  # bare Enter defaults to no
    assert CliIO(console).confirm(render) is False
    assert _printed(console, "confirm to apply")


def test_pause_render_shows_point_triggers_and_bundle() -> None:
    """The pause render carries the steer-point name, fired triggers and a compact
    bundle (headline numbers only — never a full document list)."""
    console = ScriptedConsole(["1"])
    payload = _steer_point_payload(
        "deepening_selection",
        boundary="after_component",
        component="select",
        triggers=[{"trigger": "excluded_large_stratum", "detail": {"n": 14}}],
        bundle={"selected": 12, "pool": 40, "dropped_strata": ["a", "b", "c"]},
    )
    CliIO(console).pause(payload, "select: succeeded")
    assert _printed(console, "Steer point: deepening_selection")
    assert _printed(console, "excluded_large_stratum")
    assert _printed(console, "selected: 12")
    assert _printed(console, "pool: 40")
    assert _printed(console, "dropped_strata: 3 items")  # count, not the ids


def test_authored_options_rendered_and_pickable() -> None:
    """Watch-authored options render in a 'Suggested for this run' block and pick
    into a bounded adjustment keyed by the option's component."""
    authored = [
        AuthoredOptionWire(
            label="Re-group by population — 14 findings",
            why="population splits the corpus more usefully here",
            component="group",
            delta={"grouping": {"facets": ["population"]}},
        ).model_dump()
    ]
    payload = _steer_point_payload(
        "synthesis_shape",
        boundary="before_component",
        component="synthesise",
        authored_options=authored,
    )
    canonical = [o for o in payload["options"] if o["id"] not in _FRAME_OPTION_IDS]
    authored_number = str(2 + len(canonical))  # first authored option, after the floor
    console = ScriptedConsole([authored_number])
    response = CliIO(console).pause(payload, "group: succeeded")
    assert isinstance(response, Adjust)
    assert response.directive_deltas == {"group": {"grouping": {"facets": ["population"]}}}
    assert _printed(console, "suggested by the agent")
    assert _printed(console, "Re-group by population — 14 findings")
    assert _printed(console, "population splits the corpus more usefully here")


def test_mode_labels_appear_in_the_plan_render(engine: Engine) -> None:
    """All four delegation-posture labels are shown at the plan-approval surface."""
    result = None
    try:
        console = ScriptedConsole(
            [
                "What works to reduce childhood obesity?",
                "1",
                "approve",
                # spare continues cover every lattice pause incl. per-round P1
                "1", "1", "1", "1", "1", "1", "1",
            ]
        )
        result = main(console, engine=engine, backends=_stub_backends())
        for label in (
            "Often — walk me through it",
            "At the key decisions (default)",
            "Only if something needs my judgment",
            "Never — here are my standing instructions",
        ):
            assert _printed(console, label), label
    finally:
        _cleanup(engine, result.task_id if result else None)


def _frag(**kwargs: Any) -> RouterFragmentWire:
    return RouterFragmentWire(**kwargs)


def _compile(
    fragments: list[RouterFragmentWire], summary: str = "stub fan-out"
) -> RouterCompileWire:
    return RouterCompileWire(fragments=fragments, summary=summary)


class _ModerateStubPlanner(StubPlannerBackend):
    """Stub planner variant for tests that deliberately exercise check-ins."""

    def plan_turn(
        self,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        session_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> PlannerTurnWire:
        turn = super().plan_turn(
            turns, previous_draft, session_id=session_id, conversation_id=conversation_id
        )
        return turn.model_copy(
            update={"plan_draft": turn.plan_draft.model_copy(update={"steering_mode": "moderate"})}
        )


# A known-good pending-component fan-out fragment (group is not yet run at the
# first pause of a deep chain), mirroring tests/runtime/test_router_compile.py.
_GROUP_FACET_FRAGMENT = _frag(
    fragment_text="group by population",
    compiles=True,
    component="group",
    delta={"grouping": {"facets": ["population"]}},
)


def test_free_text_refusal_re_presents_the_menu(engine: Engine) -> None:
    """Free text the (default refuse-all) router cannot compile prints an honest
    re-presentation note; the user then continues from the canonical menu."""
    result = None
    try:
        console = ScriptedConsole(
            [
                "What works to reduce childhood obesity?",
                "1",
                "approve",
                "make the report rhyme",  # first pause: refused by the stub router
                "1",  # re-presented menu → continue
                "1",
                "1",
                "1",
                # Wired floor triggers (review fix, MAJOR-1) can fire collapse
                # classes on this degenerate 2-doc fixture at the after_classify/
                # after_appraise boundaries — continue through any extra pauses.
                "1",
                "1",
                "1",
            ]
        )
        # main() constructs the deterministic StubAgentBackend (refuse-all).
        result = main(
            console, engine=engine, planner=_ModerateStubPlanner(), backends=_stub_backends()
        )
        assert result.exit_code == 0
        assert _printed(console, "None of that could be applied")
    finally:
        _cleanup(engine, result.task_id if result else None)


def test_confirmed_free_text_steer_applies_in_a_full_run(engine: Engine) -> None:
    """Extend the full-stub e2e: a free-text steer at the first pause compiles to a
    pending group adjustment, is confirmed (y), applies, and the run still mints an
    artefact — grouping runs on the steered facet."""
    result = None
    try:
        console = ScriptedConsole(
            [
                "What works to reduce childhood obesity?",
                "1",
                "approve",
                "group by population",  # first pause: free-text steer
                "y",  # confirm the rendered fan-out
                "1",  # remaining lattice pauses continue
                "1",
                "1",
                # Wired floor triggers (review fix, MAJOR-1) can fire collapse
                # classes on this degenerate 2-doc fixture at the after_classify/
                # after_appraise boundaries — continue through any extra pauses.
                "1",
                "1",
                "1",
            ]
        )
        agent = StubAgentBackend(route_responses=[_compile([_GROUP_FACET_FRAGMENT])])
        result = main(
            console,
            engine=engine,
            planner=_ModerateStubPlanner(),
            backends=_stub_backends(),
            agent=agent,
        )
        assert result.exit_code == 0
        assert result.outcome is not None
        assert result.outcome.status == "succeeded"
        assert result.artefact_present is True
        assert _printed(console, "confirm to apply")

        with engine.connect() as conn:
            facets = conn.execute(
                select(grouping_result.c.grouping_provenance).where(
                    grouping_result.c.task_id == result.task_id
                )
            ).scalar_one()["facets"]
        assert facets == ["population"]
    finally:
        _cleanup(engine, result.task_id if result else None)


class _StandingInstructionsPlanner:
    """Unattended planner that authors a standing default per steer point across
    turns via its suggested-answers (the Task 5 authoring flow).

    One point per turn: it asks about ``evidence_search_coverage`` then
    ``deepening_selection``, folding each answered point into
    ``steer_point_defaults`` (the second answer pins an option_id + delta), and
    only reports ``ready`` once both are authored.
    """

    mode = "stub"
    _POINTS = ("evidence_search_coverage", "deepening_selection")

    def _default_for(self, point: str, answer: str) -> SteerPointDefaultDraft:
        if answer.startswith("stop"):
            return SteerPointDefaultDraft(steer_point=point, action="stop")
        if "strongest" in answer:
            # The wire carries the delta JSON-encoded (strict response-format
            # schemas cannot carry open objects); _build_plan decodes it.
            return SteerPointDefaultDraft(
                steer_point=point,
                action="proceed_flag",
                option_id="strongest_evidence",
                delta_json='{"selection": {"weight_emphasis": {"quality": 2.0}}}',
            )
        return SteerPointDefaultDraft(steer_point=point, action="proceed_flag")

    def plan_turn(
        self,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        session_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> PlannerTurnWire:
        del previous_draft, session_id, conversation_id
        answers = [turn["text"] for turn in turns if turn["role"] == "user"][1:]
        defaults = [self._default_for(self._POINTS[i], answer) for i, answer in enumerate(answers)]
        draft = PlanDraftWire(
            title="Unattended review",
            question=turns[0]["text"],
            backend_scope="both",
            search_effort="standard",
            analysis_depth="deep",
            components=["characterise", "screen_full", "select", "extract", "group"],
            grouping_facets=["outcome"],
            steering_mode="unattended",
            steer_point_defaults=defaults or None,
            assumptions=["Stub: unattended standing-instructions authoring."],
        )
        if len(answers) < len(self._POINTS):
            return PlannerTurnWire(
                reply="Let's set your standing instructions.",
                plan_draft=draft,
                question=f"Standing instruction for {self._POINTS[len(answers)]}?",
                suggested_answers=["proceed and flag", "favour the strongest evidence", "stop"],
                ready=False,
            )
        return PlannerTurnWire(
            reply="Standing instructions set.",
            plan_draft=draft,
            question=None,
            suggested_answers=None,
            ready=True,
        )


def test_standing_instructions_authoring_flow_two_points(engine: Engine) -> None:
    """A multi-turn unattended plan authors standing defaults for two steer points
    (one bare proceed_flag, one option_id+delta) that round-trip into the plan."""
    result = None
    try:
        console = ScriptedConsole(
            [
                "What works to reduce childhood obesity?",
                "1",  # evidence_search_coverage -> "proceed and flag"
                "2",  # deepening_selection -> "favour the strongest evidence"
                "approve",
            ]
        )
        result = main(
            console,
            engine=engine,
            planner=_StandingInstructionsPlanner(),
            backends=_stub_backends(),
        )
        assert result.plan is not None
        assert [d.model_dump() for d in result.plan.steer_point_defaults] == [
            {
                "steer_point": "evidence_search_coverage",
                "action": "proceed_flag",
                "option_id": None,
                "delta": None,
            },
            {
                "steer_point": "deepening_selection",
                "action": "proceed_flag",
                "option_id": "strongest_evidence",
                "delta": {"selection": {"weight_emphasis": {"quality": 2.0}}},
            },
        ]
        assert _printed(console, "steer_point_defaults")
    finally:
        _cleanup(engine, result.task_id if result else None)


# --- FIX E3: cost-of-inference language never reaches a user-facing surface ---

# The SELECTION budget is legitimate user vocabulary ("Change how many documents
# are selected" / "the selection budget"), so it is deliberately NOT banned; the
# guard is scoped to cost-of-inference language a policy maker must never see.
_COST_TERMS = ["cost", "token", "price", "$", "spend", "quota"]


def _assert_no_cost_language(surface: str, text: str) -> None:
    lowered = text.lower()
    for term in _COST_TERMS:
        assert term not in lowered, f"cost language {term!r} leaked into {surface}: {text!r}"


def test_no_cost_language_on_any_user_facing_surface() -> None:
    """Render every user-facing steering surface from representative fixtures and
    assert none carries cost-of-inference language (FIX E3). Covers the check-in
    and collation renders, the fan-out confirmation (incl. the FIX-A bounded delta
    render and a refusal line), the FIX-C authored-replacement confirmation, and
    the canonical + watch-authored option menus rendered through the CLI."""
    surfaces: dict[str, str] = {}

    # 1. Check-in + collation renders (deterministic runner surfaces).
    surfaces["check_in"] = render_check_in(
        {
            "component": "select",
            "status": "succeeded",
            "wall_clock_s": 1.234,
            "headline_counts": {"selected": 15, "candidates": 40},
            "reason": "budget applied to the candidate pool",
        }
    )
    surfaces["collation"] = render_collation(
        [
            {"component": "extract", "status": "retrying", "reason": "transient backend error"},
            {"component": "group", "status": "skipped", "reason": "upstream extract failed"},
            {
                "component": "select",
                "status": "auto_resolved",
                "rule": "unconfigured_default",
                "reason": "no pinned rule; proceeded at standard depth",
            },
        ]
    )

    # 2. Fan-out confirmation, incl. the FIX-A bounded delta render + a refusal.
    fanout = FanOut(
        compiled=[
            CompiledFragment(
                "drop any section about methodology",
                "replacement_rerun",
                "synthesise",
                {"synthesis": {"sections": [{"title": "What works", "focus": "outcomes"}]}},
                "replacement",
            ),
            CompiledFragment(
                "select fewer documents",
                "replacement_rerun",
                "select",
                {"selection": {"budget": 15}},
                "replacement",
            ),
        ],
        refused=[
            RefusedFragment(
                "rank by author reputation", "ranking by author reputation is not yet expressible"
            )
        ],
        summary="Two changes; one refusal.",
    )
    surfaces["fanout_confirmation"] = render_fanout_confirmation(fanout)

    # 3. FIX-C authored-replacement confirmation (mode declaration + bounded delta).
    surfaces["authored_replacement_confirmation"] = render_authored_replacement_confirmation(
        CompiledFragment(
            "", "replacement_rerun", "select", {"selection": {"budget": 15}}, "replacement"
        )
    )

    # 4. Canonical + watch-authored option menus, rendered through the real CLI.
    authored = [
        AuthoredOptionWire(
            label="Change how many documents are selected — 14 dropped at the current budget",
            why="a smaller selection focuses the evidence base",
            component="select",
            delta={"selection": {"budget": 15}},
        ).model_dump()
    ]
    for point_name, boundary, component in (
        ("search_review", "after_component", "acquire"),
        ("evidence_search_coverage", "after_component", "characterise"),
        ("deepening_selection", "after_component", "select"),
        ("finding_groups", "after_component", "group"),
        ("synthesis_shape", "before_component", "synthesise"),
    ):
        payload = _steer_point_payload(
            point_name,
            boundary=boundary,
            component=component,
            authored_options=authored if point_name == "deepening_selection" else None,
        )
        console = ScriptedConsole(["1"])  # render the full menu, then Continue
        CliIO(console).pause(payload, f"{component}: succeeded")
        surfaces[f"menu:{point_name}"] = "\n".join(console.output)

    for surface, text in surfaces.items():
        _assert_no_cost_language(surface, text)
