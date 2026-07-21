"""Router compile-and-apply tests (task 024, decision 3 — the router).

Free text typed at a pause is compiled by the orchestrator ``route`` backend
into a fan-out of bounded directive deltas, re-validated author-blind through
the same fail-closed grammars a canonical option choice takes, rendered for
confirmation, and — only on confirmation — applied through the EXISTING apply
paths (plan adjustment · replacement re-run · additive segment re-entry).

These drive the runner end-to-end against a real DB with the deterministic stub
orchestrator (zero egress) scripted to return specific fan-outs, plus a scripted
IO that types free text at one pause and answers the confirm gate.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.core import events
from policy_atlas.core.schema import evidence_scope, grouping_result, orchestration_plan
from policy_atlas.runtime import runner as runner_module
from policy_atlas.runtime import steering_events
from policy_atlas.runtime.orchestrator_backend import StubOrchestratorBackend
from policy_atlas.runtime.orchestrator_prompt import RouterCompileWire, RouterFragmentWire
from policy_atlas.runtime.runner import run_plan
from policy_atlas.runtime.steering import (
    CompiledFragment,
    Continue,
    FanOut,
    FreeText,
    RefusedFragment,
    SteeringAdjustmentError,
    SteeringResponse,
    render_fanout_confirmation,
)
from tests.runtime.test_runner import _base_plan, _runner_backends, _seed_project
from tests.runtime.test_steering import _cleanup_project, _insert_plan_row

# --- Scripted IO + wire builders -------------------------------------------


class _FreeTextIO:
    """Types free text once at the target pause, then continues; answers confirm.

    Args:
        utterance: The free-text prose returned once at the matching pause.
        target: Key/value pairs matched against the pause point (e.g.
            ``{"steer_point": "deepening_selection"}`` or ``{"component":
            "characterise", "boundary": "after_component"}``).
        confirm_result: What ``confirm`` returns for the rendered fan-out.
    """

    def __init__(
        self,
        *,
        utterance: str,
        target: dict[str, Any],
        confirm_result: bool = True,
    ) -> None:
        self.utterance = utterance
        self.target = target
        self.confirm_result = confirm_result
        self.fired = False
        self.check_ins: list[tuple[str, dict[str, Any]]] = []
        self.pauses: list[tuple[dict[str, Any], str]] = []
        self.confirm_renders: list[str] = []

    def check_in(self, component: str, payload: dict[str, Any]) -> None:
        self.check_ins.append((component, payload))

    def pause(self, point: dict[str, Any], render: str) -> SteeringResponse:
        self.pauses.append((dict(point), render))
        if not self.fired and all(point.get(key) == value for key, value in self.target.items()):
            self.fired = True
            return FreeText(self.utterance)
        return Continue()

    def confirm(self, render: str) -> bool:
        self.confirm_renders.append(render)
        return self.confirm_result


def _frag(
    text: str,
    *,
    compiles: bool = True,
    component: str | None = None,
    delta: dict[str, Any] | None = None,
    rerun_mode: str | None = None,
    refusal_reason: str | None = None,
) -> RouterFragmentWire:
    return RouterFragmentWire(
        fragment_text=text,
        compiles=compiles,
        component=component,
        delta=delta,
        rerun_mode=rerun_mode,
        refusal_reason=refusal_reason,
    )


def _compile(
    fragments: list[RouterFragmentWire], *, summary: str = "stub fan-out"
) -> RouterCompileWire:
    return RouterCompileWire(fragments=fragments, summary=summary)


# Reusable fan-out fragments.
_SELECT_RERUN = _frag(
    "favour the strongest evidence",
    component="select",
    delta={"selection": {"weight_emphasis": {"quality": 2.0}}},
    rerun_mode="replacement",
)
_GROUP_ADJUST = _frag(
    "group by population",
    component="group",
    delta={"grouping": {"facets": ["population"]}},
)
_REFUSED = _frag(
    "rank by author reputation",
    compiles=False,
    refusal_reason="ranking by author reputation is not yet expressible",
)
_ACQUIRE_ADDITIVE = _frag(
    "search more on rural areas",
    component="acquire",
    delta={"search": {"guidance": ["prioritise rural areas"]}},
    rerun_mode="additive",
)

_P3 = {"steer_point": "deepening_selection"}


def _read_events(engine: Engine, project_id: uuid.UUID, event_type: str) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        return [e for e in events.read(conn, project_id) if e["event_type"] == event_type]


def _plan_rows(engine: Engine, project_id: uuid.UUID) -> list[Any]:
    with engine.connect() as conn:
        return list(conn.execute(
            select(
                orchestration_plan.c.version,
                orchestration_plan.c.status,
                orchestration_plan.c.created_by,
                orchestration_plan.c.payload,
            )
            .where(orchestration_plan.c.project_id == project_id)
            .order_by(orchestration_plan.c.version)
        ).all())


def _count_select_runs(engine: Engine, project_id: uuid.UUID) -> int:
    with engine.connect() as conn:
        return sum(
            1
            for e in events.read(conn, project_id)
            if e["event_type"] == "plan.compiled" and e["payload"]["component"] == "select"
        )


# --- Happy fan-out ----------------------------------------------------------


def test_free_text_fanout_applies_confirmed_adjustment_and_rerun(engine: Engine) -> None:
    """FreeText → 2 compiling fragments (group adjustment + P3 select rerun) + 1
    refused → confirm=True → both apply, decision carries verbatim user_text +
    confirmed=true, one steering.refused with the fragment text, and the render
    declares the replacement re-run mode."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()  # moderate, deep chain: P3 pauses
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        utterance = "favour the strongest evidence, group by population, rank by author reputation"
        stub = StubOrchestratorBackend(
            route_responses=[_compile([_SELECT_RERUN, _GROUP_ADJUST, _REFUSED])]
        )
        io = _FreeTextIO(utterance=utterance, target=_P3, confirm_result=True)

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=io,
            orchestrator=stub,
        )
        assert outcome.status == "succeeded"

        # Select re-ran (replacement): two select runs.
        assert _count_select_runs(engine, project_id) == 2

        # The pending group adjustment applied and carries through to grouping.
        with engine.connect() as conn:
            facets = conn.execute(
                select(grouping_result.c.grouping_provenance).where(
                    grouping_result.c.project_id == project_id
                )
            ).scalar_one()["facets"]
        assert facets == ["population"]

        # New user-attributed plan versions record the fan-out (adjustment + rerun).
        rows = _plan_rows(engine, project_id)
        created_by = [r.created_by for r in rows]
        assert created_by[0] == "planner"
        assert created_by.count("user") == 2

        # A confirmed decision carries the verbatim utterance.
        decisions = _read_events(engine, project_id, steering_events.STEERING_DECISION)
        confirmed = [
            d
            for d in decisions
            if d["payload"].get("confirmed") is True
            and d["payload"].get("user_text") == utterance
        ]
        assert confirmed, "a confirmed decision must carry the verbatim user_text"
        # One of them stamps the replacement re-run mode.
        assert any(d["payload"].get("rerun_mode") == "replacement" for d in confirmed)
        # The plan-adjustment decision records the whole fan-out as its action.
        fanout_actions = [
            d["payload"]["interpreted_action"]
            for d in confirmed
            if isinstance(d["payload"].get("interpreted_action"), dict)
            and "compiled" in d["payload"]["interpreted_action"]
        ]
        assert fanout_actions, "the fan-out is stamped as interpreted_action"

        # Exactly one steering.refused, verbatim fragment text + reason.
        refused = _read_events(engine, project_id, steering_events.STEERING_REFUSED)
        assert len(refused) == 1
        assert refused[0]["payload"]["fragment_text"] == "rank by author reputation"
        assert refused[0]["payload"]["reason"]

        # The confirmation render declared the replacement re-run mode in plain language.
        assert io.confirm_renders
        assert any(
            "REDO selection, replacing the current one" in render
            for render in io.confirm_renders
        )
    finally:
        _cleanup_project(engine, project_id)


def test_free_text_confirmed_fanout_apply_error_rejects_and_re_presents(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FIX 3a: a CONFIRMED fan-out whose apply raises SteeringAdjustmentError no
    longer crashes the run — it emits steering.rejected (reason + verbatim
    utterance) and re-presents the canonical menu, from which the user continues."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()  # moderate, deep chain: P3 pauses
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        utterance = "group by population"
        stub = StubOrchestratorBackend(route_responses=[_compile([_GROUP_ADJUST])])
        io = _FreeTextIO(utterance=utterance, target=_P3, confirm_result=True)

        # Force the confirmed adjustment apply to fail loudly at apply time.
        def _boom(*a: Any, **k: Any) -> Any:
            raise SteeringAdjustmentError("apply blew up")

        monkeypatch.setattr(runner_module, "_apply_runner_adjustment", _boom)

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=io,
            orchestrator=stub,
        )
        # The run did NOT crash.
        assert outcome.status in {"succeeded", "degraded"}

        # steering.rejected was emitted with the reason + verbatim utterance.
        rejected = _read_events(engine, project_id, steering_events.STEERING_REJECTED)
        assert rejected, "the failed confirmed-fan-out apply must emit steering.rejected"
        assert any(
            "apply blew up" in r["payload"].get("reason", "")
            and r["payload"].get("user_text") == utterance
            for r in rejected
        ), rejected

        # The P3 menu was re-presented (the same pause appears again after the
        # free-text; the IO continues on that re-presentation).
        p3_pauses = [
            point for point, _ in io.pauses if point.get("steer_point") == "deepening_selection"
        ]
        assert len(p3_pauses) >= 2, "the canonical menu must be re-presented after the reject"
    finally:
        _cleanup_project(engine, project_id)


# --- Unconfirmed: nothing applies ------------------------------------------


def test_free_text_unconfirmed_applies_nothing_but_events_the_offer(engine: Engine) -> None:
    """confirm=False → NOTHING applies (no new select run, no plan version, group
    unchanged); a steering.decision records confirmed=false with the fan-out; the
    refusals are still evented."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        utterance = "favour the strongest evidence, group by population, rank by author reputation"
        stub = StubOrchestratorBackend(
            route_responses=[_compile([_SELECT_RERUN, _GROUP_ADJUST, _REFUSED])]
        )
        io = _FreeTextIO(utterance=utterance, target=_P3, confirm_result=False)

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=io,
            orchestrator=stub,
        )
        assert outcome.status == "succeeded"

        # Nothing applied: one select run, no user plan versions, group unchanged.
        assert _count_select_runs(engine, project_id) == 1
        rows = _plan_rows(engine, project_id)
        assert [r.created_by for r in rows] == ["planner"]
        with engine.connect() as conn:
            facets = conn.execute(
                select(grouping_result.c.grouping_provenance).where(
                    grouping_result.c.project_id == project_id
                )
            ).scalar_one()["facets"]
        assert facets == ["outcome"]  # the base plan's default facet

        # The decline is on the record: confirmed=false, decided_by user, fan-out attached.
        declined = [
            d
            for d in _read_events(engine, project_id, steering_events.STEERING_DECISION)
            if d["payload"].get("confirmed") is False
        ]
        assert len(declined) == 1
        payload = declined[0]["payload"]
        assert payload["decided_by"] == "user"
        assert payload["user_text"] == utterance
        assert "compiled" in payload["interpreted_action"]

        # Refusals still emitted.
        refused = _read_events(engine, project_id, steering_events.STEERING_REFUSED)
        assert len(refused) == 1
    finally:
        _cleanup_project(engine, project_id)


# --- Author-blind demotion --------------------------------------------------


def test_free_text_out_of_grammar_fragment_demoted_to_refused(engine: Engine) -> None:
    """A fragment the model claims compiles but whose delta fails the grammar is
    demoted to refused (validation_failed); the rest of the fan-out still applies."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        bad_select = _frag(
            "do something clever to selection",
            component="select",
            delta={"selection": {"bogus": 1}},
            rerun_mode="replacement",
        )
        stub = StubOrchestratorBackend(route_responses=[_compile([bad_select, _GROUP_ADJUST])])
        io = _FreeTextIO(utterance="clever selection, group by population", target=_P3)

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=io,
            orchestrator=stub,
        )
        assert outcome.status == "succeeded"

        # The bad select fragment was refused (validation_failed); select did NOT re-run.
        refused = _read_events(engine, project_id, steering_events.STEERING_REFUSED)
        assert len(refused) == 1
        assert "validation_failed" in refused[0]["payload"]["reason"]
        assert _count_select_runs(engine, project_id) == 1

        # The valid group adjustment still applied.
        with engine.connect() as conn:
            facets = conn.execute(
                select(grouping_result.c.grouping_provenance).where(
                    grouping_result.c.project_id == project_id
                )
            ).scalar_one()["facets"]
        assert facets == ["population"]
    finally:
        _cleanup_project(engine, project_id)


# --- Backend error degrades to the canonical menu --------------------------


class _RaisingRouteBackend:
    """A backend whose ``route`` raises; triage/decide delegate to the stub floor."""

    def __init__(self) -> None:
        self._stub = StubOrchestratorBackend()

    def route(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("router backend is down")

    def triage(self, *args: Any, **kwargs: Any) -> Any:
        return self._stub.triage(*args, **kwargs)

    def decide(self, *args: Any, **kwargs: Any) -> Any:
        return self._stub.decide(*args, **kwargs)


def test_free_text_backend_error_re_presents_menu_and_completes(engine: Engine) -> None:
    """A route backend error degrades to the canonical menu (watch_error evented);
    the re-presented pause continues and the run completes with nothing applied."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        io = _FreeTextIO(utterance="favour the strongest evidence", target=_P3)

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=io,
            orchestrator=_RaisingRouteBackend(),
        )
        assert outcome.status == "succeeded"

        # Nothing applied.
        assert _count_select_runs(engine, project_id) == 1
        assert [r.created_by for r in _plan_rows(engine, project_id)] == ["planner"]

        # A watch_error-style degrade is on the record.
        routed = _read_events(engine, project_id, steering_events.AGENT_JUDGEMENT_ROUTED)
        degrades = [r for r in routed if r["payload"].get("verdict") == "watch_error"]
        assert any("router compile failed" in r["payload"]["reason"] for r in degrades)
    finally:
        _cleanup_project(engine, project_id)


# --- All-refused: nothing applies, menu re-presented -----------------------


def test_free_text_all_refused_events_refusals_and_changes_nothing(engine: Engine) -> None:
    """When every fragment is refused, refusals are evented, nothing applies, and
    the menu is re-presented (the run completes)."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        stub = StubOrchestratorBackend(
            route_responses=[
                _compile(
                    [
                        _frag("verify the findings differently", compiles=False,
                              refusal_reason="the verifier is closed to steering"),
                        _REFUSED,
                    ]
                )
            ]
        )
        io = _FreeTextIO(utterance="verify differently and rank by author", target=_P3)

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=io,
            orchestrator=stub,
        )
        assert outcome.status == "succeeded"

        refused = _read_events(engine, project_id, steering_events.STEERING_REFUSED)
        assert len(refused) == 2
        # No confirmed fan-out decision, no confirm gate reached, nothing applied.
        assert io.confirm_renders == []
        assert _count_select_runs(engine, project_id) == 1
        assert [r.created_by for r in _plan_rows(engine, project_id)] == ["planner"]
    finally:
        _cleanup_project(engine, project_id)


# --- Additive + replacement collision (one-cycle rule) ---------------------


def test_free_text_rerun_collision_applies_leader_refuses_second(engine: Engine) -> None:
    """A fan-out with both a replacement re-run and an additive segment re-entry
    applies the one the utterance leads with and refuses the second (one re-run
    per pause)."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        # Select replacement leads; the additive re-search is the trailing re-run.
        stub = StubOrchestratorBackend(
            route_responses=[_compile([_SELECT_RERUN, _ACQUIRE_ADDITIVE])]
        )
        io = _FreeTextIO(
            utterance="favour the strongest evidence and also search more on rural areas",
            target=_P3,
        )

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=io,
            orchestrator=stub,
        )
        assert outcome.status == "succeeded"

        # The leading replacement re-run applied (two select runs); the additive
        # re-search was refused for the one-cycle rule.
        assert _count_select_runs(engine, project_id) == 2
        refused = _read_events(engine, project_id, steering_events.STEERING_REFUSED)
        assert len(refused) == 1
        assert "one re-run" in refused[0]["payload"]["reason"]
        # No additive re-run decision was recorded.
        additive = [
            d
            for d in _read_events(engine, project_id, steering_events.STEERING_DECISION)
            if d["payload"].get("rerun_mode") == "additive"
        ]
        assert additive == []
    finally:
        _cleanup_project(engine, project_id)


# --- Additive segment re-entry via the router ------------------------------


def test_free_text_additive_re_search_runs_segment_reentry(engine: Engine) -> None:
    """An additive re-search fragment at an after_component boundary drives the
    segment-re-entry path: acquire..boundary re-walks, an additive decision is
    recorded with the verbatim user_text, and the run completes."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="frequent")  # every after_component pauses
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        utterance = "search more on rural areas"
        stub = StubOrchestratorBackend(route_responses=[_compile([_ACQUIRE_ADDITIVE])])
        io = _FreeTextIO(
            utterance=utterance,
            target={"component": "characterise", "boundary": "after_component", "kind": "check_in"},
        )

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=io,
            orchestrator=stub,
        )
        assert outcome.status == "succeeded"

        # characterise ran twice (original + segment re-walk).
        with engine.connect() as conn:
            char_runs = sum(
                1
                for e in events.read(conn, project_id)
                if e["event_type"] == "plan.compiled"
                and e["payload"]["component"] == "characterise"
            )
        assert char_runs == 2

        # An additive decision recorded the verbatim utterance.
        additive = [
            d
            for d in _read_events(engine, project_id, steering_events.STEERING_DECISION)
            if d["payload"].get("rerun_mode") == "additive"
        ]
        assert len(additive) == 1
        assert additive[0]["payload"]["user_text"] == utterance
        assert additive[0]["payload"]["confirmed"] is True
    finally:
        _cleanup_project(engine, project_id)


# --- P2 / P4 before-boundary re-run surface (Task 15b) ---------------------


def test_free_text_p2_additive_re_search_runs_segment_reentry(engine: Engine) -> None:
    """At P2 (before select) an additive re-search fragment drives a segment
    re-walk of acquire→characterise, re-presents P2 once, records an additive
    decision with the verbatim utterance, and the walk proceeds into select."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()  # moderate: P2 pauses (before select)
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        utterance = "search more on rural areas before selecting"
        stub = StubOrchestratorBackend(route_responses=[_compile([_ACQUIRE_ADDITIVE])])
        io = _FreeTextIO(utterance=utterance, target={"steer_point": "evidence_base_coverage"})

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=io,
            orchestrator=stub,
        )
        assert outcome.status == "succeeded"

        # characterise re-walked once (original + segment re-walk).
        with engine.connect() as conn:
            char_runs = sum(
                1
                for e in events.read(conn, project_id)
                if e["event_type"] == "plan.compiled"
                and e["payload"]["component"] == "characterise"
            )
        assert char_runs == 2

        # Additive decision at a before_component boundary, verbatim user_text.
        additive = [
            d
            for d in _read_events(engine, project_id, steering_events.STEERING_DECISION)
            if d["payload"].get("rerun_mode") == "additive"
        ]
        assert len(additive) == 1
        assert additive[0]["payload"]["boundary"] == "before_component"
        assert additive[0]["payload"]["user_text"] == utterance

        # P2 was re-presented exactly once (two evidence_base_coverage pauses).
        p2_pauses = [
            point
            for point, _ in io.pauses
            if point.get("steer_point") == "evidence_base_coverage"
        ]
        assert len(p2_pauses) == 2
    finally:
        _cleanup_project(engine, project_id)


def test_free_text_p4_section_edit_applies_as_plan_adjustment(engine: Engine) -> None:
    """At P4 (before synthesise) a synthesis section-edit fragment is a
    plan-adjustment delta on the not-yet-run synthesise component: confirmed, it
    writes a user plan version and records the fan-out; the run completes."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()  # moderate: P4 pauses (before synthesise)
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        utterance = "drop the methodology section, keep policy relevance"
        section_fragment = _frag(
            "keep only the policy-relevance section",
            component="synthesise",
            delta={
                "synthesis": {
                    "sections": [
                        {
                            "title": "Policy relevance of the evidence",
                            "focus": "What the evidence says for the decision",
                        }
                    ]
                }
            },
        )
        stub = StubOrchestratorBackend(route_responses=[_compile([section_fragment])])
        io = _FreeTextIO(utterance=utterance, target={"steer_point": "synthesis_shape"})

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=io,
            orchestrator=stub,
        )
        assert outcome.status == "succeeded"

        # A user plan version records the section-edit adjustment.
        rows = _plan_rows(engine, project_id)
        assert [r.created_by for r in rows] == ["planner", "user"]

        # The confirmed decision carries the fan-out (with the synthesis fragment).
        confirmed = [
            d
            for d in _read_events(engine, project_id, steering_events.STEERING_DECISION)
            if d["payload"].get("confirmed") is True
            and d["payload"].get("user_text") == utterance
        ]
        assert confirmed
        action = confirmed[0]["payload"]["interpreted_action"]
        assert any(
            frag["component"] == "synthesise" and "synthesis" in frag["delta"]
            for frag in action["compiled"]
        )
    finally:
        _cleanup_project(engine, project_id)


# --- Pending overlay: P4 synthesis section-edit reaches the run (Task 15c) --


def test_free_text_p4_section_edit_overlay_reaches_synthesise_run(engine: Engine) -> None:
    """A confirmed P4 section-edit is a commit-layer overlay (no plan field): it
    reaches the synthesise run — the scope-context row carries the sections and
    the synthesise plan.compiled event echoes the executed overlay."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()  # moderate: P4 (synthesis_shape) pauses
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        sections = [
            {
                "title": "Policy relevance of the evidence",
                "focus": "What the evidence says for the decision",
            }
        ]
        section_fragment = _frag(
            "keep only the policy-relevance section",
            component="synthesise",
            delta={"synthesis": {"sections": sections}},
        )
        stub = StubOrchestratorBackend(route_responses=[_compile([section_fragment])])
        io = _FreeTextIO(
            utterance="prune to policy relevance",
            target={"steer_point": "synthesis_shape"},
        )

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=io,
            orchestrator=stub,
        )
        assert outcome.status == "succeeded"

        # The overlay reached the run: it was written to the scope-context row.
        with engine.connect() as conn:
            context = conn.execute(
                select(evidence_scope.c.context).where(
                    evidence_scope.c.evidence_scope_id == scope_id
                )
            ).scalar_one()
        assert context.get("synthesis", {}).get("sections") == sections

        # Provenance: the synthesise plan.compiled event echoes the executed overlay.
        with engine.connect() as conn:
            synth_payloads = [
                e["payload"]
                for e in events.read(conn, project_id)
                if e["event_type"] == "plan.compiled"
                and e["payload"]["component"] == "synthesise"
            ]
        assert synth_payloads
        assert synth_payloads[0]["pending_overlay"] == {"synthesis": {"sections": sections}}
    finally:
        _cleanup_project(engine, project_id)


# --- render_fanout_confirmation (deterministic, declares modes) ------------


def test_render_fanout_confirmation_declares_modes_in_plain_language() -> None:
    """The confirmation render names each fragment's component and declares its
    re-run mode in plain language, and lists refusals by name."""
    fanout = FanOut(
        compiled=[
            CompiledFragment(
                "search more on rural areas",
                "segment_reentry",
                "acquire",
                {"search": {"guidance": ["prioritise rural areas"]}},
                "additive",
            ),
            CompiledFragment(
                "favour the strongest evidence",
                "replacement_rerun",
                "select",
                {"selection": {"weight_emphasis": {"quality": 2.0}}},
                "replacement",
            ),
        ],
        refused=[RefusedFragment("rank by author reputation", "not yet expressible")],
        summary="Two changes; one refusal.",
    )
    render = render_fanout_confirmation(fanout)
    # The two mode sentences, in plain language.
    assert "ADD TO your evidence base" in render
    assert "REDO selection, replacing the current one" in render
    # The refusal is named.
    assert "rank by author reputation" in render
    assert "not yet expressible" in render
    # Deterministic: same input, same output.
    assert render == render_fanout_confirmation(fanout)
