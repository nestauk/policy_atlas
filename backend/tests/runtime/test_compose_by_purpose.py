"""Compose by purpose and the per-step spine flag (task 045 Phase 1, S1).

ADR 0039 decision 2: a chain is composed by capability *and* the purpose of
the intent record the walk runs under, so the purpose is recoverable on the
fresh path and on both resume paths; ``ComponentStep.spine`` lets a chain
declare which steps fail the walk, and ``None`` keeps the Evidence search's
global spine set so every Evidence search chain is unchanged.

The five options-scoping components are registered with stub handlers until
their phases land, which makes a longlist walk in this phase a real spine
test: ``inherit`` and ``suggest`` raise and degrade the walk; the spine step
``extract_interventions`` raises and fails it.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from sqlalchemy import update
from sqlalchemy.engine import Engine

from policy_atlas.api.continuation import _with_plan
from policy_atlas.api.run_io import ParkIO
from policy_atlas.core.schema import capability_run, evidence_scope
from policy_atlas.evidence_search.sourcing.search_loop import parse_search_directive
from policy_atlas.runtime import runner
from policy_atlas.runtime.capability_registry import (
    EVIDENCE_SEARCH,
    OPTIONS_SCOPING,
    compose_plan,
    purpose_of_walk,
)
from policy_atlas.runtime.continuation_state import build
from policy_atlas.runtime.harness import OPTIONS_SCOPING_STUBS, build_graph
from policy_atlas.runtime.run_spec import COMPONENT_REGISTRY, Plan, compile
from policy_atlas.runtime.runner import (
    NullIO,
    RunnerBackends,
    _reference_kwargs,
    _run_segment_reentry,
    _SteeringState,
    run_plan,
)
from policy_atlas.runtime.scoping_plan import (
    LONGLIST_ACQUISITION_TARGETS,
    LONGLIST_CHAIN,
    OPTION_SEARCH_CAP,
    OPTION_SEARCH_TARGET,
    OPTION_SEARCH_WIDTH,
    SCOPING_SPINE,
    SUGGEST_BOUND,
    TARGETED_CHAIN,
    ScopingPlan,
    compose_scoping,
)
from policy_atlas.runtime.task_plan import (
    SPINE,
    ComponentStep,
    ComposedChain,
    compose,
    registry_component_for,
)
from tests.runtime.test_baseline_gate import (
    insert_scoping_plan_row,
    scoping_plan,
    seed_scoping_task,
)
from tests.runtime.test_runner import _base_plan, _cleanup, _runner_backends

LONGLIST_COMPONENTS = [component for component, _spine in LONGLIST_CHAIN]


def _restricted_plan(**overrides: Any) -> ScopingPlan:
    """A scoping plan carrying one evidence restriction, so filters compile."""
    return scoping_plan(
        constraints=[
            {
                "text": "Published from 2015",
                "kind": "evidence_restriction",
                "checked_at": "retrieval",
                "origin": "your_call",
                "published_after": "2015-01-01",
            }
        ],
        **overrides,
    )


def _acquire(chain: ComposedChain) -> dict[str, Any]:
    step = next(step for step in chain.steps if step.component == "acquire")
    return cast(dict[str, Any], step.directive_delta["search"])


# --- the three chains --------------------------------------------------------


def test_no_purpose_and_baseline_compose_today_s_six_steps_unchanged() -> None:
    plan = scoping_plan()
    bare = compose_scoping(plan)
    assert compose_scoping(plan, "baseline") == bare
    assert bare.components == list(SCOPING_SPINE)
    # The baseline declares no spine of its own: the ES spine set applies.
    assert all(step.spine is None for step in bare.steps)


def test_the_longlist_chain_and_its_spine() -> None:
    chain = compose_scoping(scoping_plan(), "longlist")
    assert chain.components == [
        "inherit",
        "suggest",
        "acquire",
        "screen_abstract",
        "classify",
        "appraise",
        "ingest_full_text",
        "extract_interventions",
        "longlist",
        "constrain",
    ]
    # Owner at the plan gate: "inherit non-spine"; suggest degrades too.
    non_spine = [step.component for step in chain.steps if not step.is_spine]
    assert non_spine == ["inherit", "suggest"]
    assert all(step.spine is not None for step in chain.steps)


def test_the_targeted_chain_is_the_spine_to_the_profile() -> None:
    chain = compose_scoping(scoping_plan(), "targeted")
    assert chain.components == list(TARGETED_CHAIN) == [
        "acquire",
        "screen_abstract",
        "classify",
        "appraise",
        "ingest_full_text",
        "extract_interventions",
    ]
    assert all(step.spine is True for step in chain.steps)


def test_a_purpose_with_no_chain_is_refused() -> None:
    with pytest.raises(ValueError, match="variant"):
        compose_scoping(scoping_plan(), "variant")


def test_the_compile_constants_are_the_contract_s() -> None:
    """Contract § Plan object, "Compile constants": named so nothing hides."""
    assert LONGLIST_ACQUISITION_TARGETS == {"standard": 50, "rapid": 25}
    assert OPTION_SEARCH_TARGET == 10
    assert OPTION_SEARCH_CAP == 15
    assert OPTION_SEARCH_WIDTH == 4
    assert SUGGEST_BOUND == 10
    assert SUGGEST_BOUND <= OPTION_SEARCH_CAP


@pytest.mark.parametrize("depth", ["standard", "rapid"])
def test_the_longlist_acquire_carries_the_depth_target_and_the_restrictions(
    depth: str,
) -> None:
    plan = _restricted_plan(depth=depth)
    search = _acquire(compose_scoping(plan, "longlist"))
    assert search["record_cap"] == LONGLIST_ACQUISITION_TARGETS[depth]
    assert search["filters"] == _acquire(compose_scoping(plan))["filters"]
    # Parses under acquire's own fail-closed grammar.
    parse_search_directive({"search": search})


@pytest.mark.parametrize("depth", ["standard", "rapid"])
def test_an_option_search_acquires_its_own_target_at_either_depth(depth: str) -> None:
    plan = _restricted_plan(depth=depth)
    search = _acquire(compose_scoping(plan, "targeted"))
    assert search["record_cap"] == OPTION_SEARCH_TARGET
    assert "filters" in search
    parse_search_directive({"search": search})


def test_the_registry_passes_the_purpose_through() -> None:
    plan = scoping_plan()
    for purpose in (None, "baseline", "longlist", "targeted"):
        assert compose_plan(OPTIONS_SCOPING, plan, purpose=purpose) == compose_scoping(
            plan, purpose
        )


def test_the_evidence_search_ignores_the_purpose() -> None:
    plan = _base_plan()
    es = compose(plan)
    assert compose_plan(EVIDENCE_SEARCH, plan) == es
    assert compose_plan(EVIDENCE_SEARCH, plan, purpose="longlist") == es
    # No ES step declares a spine: the global set decides, as before.
    assert all(step.spine is None for step in es.steps)
    assert [step.component for step in es.steps if step.is_spine] == [
        component for component in es.components if component in SPINE
    ]


# --- the registries -----------------------------------------------------------


def test_the_five_components_are_registered_and_the_graph_builds() -> None:
    names = {"inherit", "suggest", "extract_interventions", "longlist", "constrain"}
    assert set(OPTIONS_SCOPING_STUBS) == names
    for name in names:
        assert COMPONENT_REGISTRY[name] == {"requires": ["evidence_scope_id"]}
        assert registry_component_for(name) == name
        # Compiles with a scope alone — no upstream run reference required.
        compile(Plan(component=name, evidence_scope_id=uuid.uuid4()))
    build_graph()


def test_the_intervention_profile_looks_up_no_selection() -> None:
    """The selection-free path (D24): no ``select`` run is threaded."""
    assert _reference_kwargs("extract_interventions", {"select": uuid.uuid4()}) == {}


# --- the spine flag ------------------------------------------------------------


def test_is_spine_falls_back_to_the_evidence_search_set() -> None:
    assert ComponentStep(component="acquire").is_spine is True
    assert ComponentStep(component="characterise").is_spine is False
    assert ComponentStep(component="acquire", spine=False).is_spine is False
    assert ComponentStep(component="characterise", spine=True).is_spine is True


def _failing_attempt(*args: Any, **kwargs: Any) -> runner._AttemptOutcome:
    del args, kwargs
    return runner._AttemptOutcome(
        run_id=uuid.uuid4(),
        status="failed",
        wall_clock_s=0.0,
        headline_counts={},
        error="boom",
    )


@pytest.mark.parametrize(
    ("spine", "component", "run_failed"),
    [
        (None, "acquire", True),  # ES spine set: acquire fails the walk
        (None, "characterise", False),  # ES discretionary: degrades
        (False, "acquire", False),  # a chain that says non-spine: degrades
        (True, "characterise", True),  # a chain that says spine: fails
    ],
)
def test_the_segment_re_entry_site_reads_the_step_s_flag(
    monkeypatch: pytest.MonkeyPatch, spine: bool | None, component: str, run_failed: bool
) -> None:
    """The second spine read (the additive segment re-walk), task 045 S1."""
    monkeypatch.setattr(runner, "_run_step_attempt", _failing_attempt)
    chain = ComposedChain(steps=[ComponentStep(component=component, spine=spine)])
    state = _SteeringState(
        plan=_base_plan(),
        plan_id=uuid.uuid4(),
        plan_version=1,
        plan_row_id=None,
        chain=chain,
        pause_points=set(),
    )
    blocked: dict[str, str] = {}
    result = _run_segment_reentry(
        cast(Engine, None),
        NullIO(),
        task_id=uuid.uuid4(),
        evidence_scope_id=uuid.uuid4(),
        state=state,
        segment_start=component,
        boundary_component=component,
        directive_deltas={},
        backends=RunnerBackends(),
        session_id=None,
        successful_runs={},
        blocked_discretionary=blocked,
        completed_components={component},
        step_outcomes=[],
        flagged_events=[],
        capability_run_id=uuid.uuid4(),
    )
    assert result.run_failed is run_failed
    assert (component in blocked) is not run_failed


# --- the fresh path and both resume paths ---------------------------------------


def _set_purpose(engine: Engine, scope_id: uuid.UUID, purpose: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            update(evidence_scope)
            .where(evidence_scope.c.evidence_scope_id == scope_id)
            .values(purpose=purpose)
        )


def test_a_walk_under_a_longlist_intent_record_runs_the_longlist_chain(
    engine: Engine,
) -> None:
    """The fresh path reads the purpose; ``spine=False`` degrades, spine fails.

    ``inherit`` and ``suggest`` raise (non-spine) and the walk carries on
    through the broad search; ``extract_interventions`` raises (spine) and the
    walk ends ``failed`` — nothing after it runs.
    """
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = seed_scoping_task(engine)
        _set_purpose(engine, scope_id, "longlist")
        plan = scoping_plan(steering_mode="moderate")
        plan_id = insert_scoping_plan_row(engine, task_id=task_id, scope_id=scope_id, plan=plan)
        outcome = run_plan(
            engine,
            task_id=task_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=NullIO(),
        )
        statuses = [(step.component, step.status) for step in outcome.steps]
        assert statuses == [
            ("inherit", "failed"),
            ("suggest", "failed"),
            ("acquire", "succeeded"),
            ("screen_abstract", "succeeded"),
            ("classify", "succeeded"),
            ("appraise", "succeeded"),
            ("ingest_full_text", "succeeded"),
            ("extract_interventions", "failed"),
        ]
        assert outcome.status == "failed"
    finally:
        _cleanup(engine, task_id)


def test_a_baseline_walk_still_runs_the_baseline_chain(engine: Engine) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = seed_scoping_task(engine)
        _set_purpose(engine, scope_id, "baseline")
        plan = scoping_plan(steering_mode="moderate")
        plan_id = insert_scoping_plan_row(engine, task_id=task_id, scope_id=scope_id, plan=plan)
        outcome = run_plan(
            engine,
            task_id=task_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=NullIO(),
        )
        assert [step.component for step in outcome.steps] == list(SCOPING_SPINE)
        assert outcome.status == "succeeded"
    finally:
        _cleanup(engine, task_id)


def _parked_scoping_walk(engine: Engine) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Park a scoping walk at its baseline gate; return task, scope and walk ids."""
    task_id, scope_id = seed_scoping_task(engine)
    plan = scoping_plan(steering_mode="moderate")
    plan_id = insert_scoping_plan_row(engine, task_id=task_id, scope_id=scope_id, plan=plan)
    outcome = run_plan(
        engine,
        task_id=task_id,
        evidence_scope_id=scope_id,
        plan=plan,
        plan_id=plan_id,
        plan_version=1,
        plan_row_id=plan_id,
        backends=_runner_backends(),
        io=ParkIO(),
    )
    assert outcome.status == "paused", outcome.status
    assert outcome.capability_run_id is not None
    return task_id, scope_id, outcome.capability_run_id


def test_the_park_resume_path_recomposes_the_walk_s_own_purpose(engine: Engine) -> None:
    """``continuation_state.build`` reads the intent record, not a default.

    A parked walk is rebuilt from the plan on resume, so a longlist walk must
    come back as a longlist walk. The baseline gate is the only park a walk can
    reach in this phase, so the test parks there and then marks the walk's
    intent record ``longlist``: what is under test is the read, not the gate.
    """
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, walk_id = _parked_scoping_walk(engine)
        assert build(engine, task_id=task_id, capability_run_id=walk_id).chain.components == (
            list(SCOPING_SPINE)
        )
        _set_purpose(engine, scope_id, "longlist")
        state = build(engine, task_id=task_id, capability_run_id=walk_id)
        assert state.chain.components == LONGLIST_COMPONENTS
        assert [step.spine for step in state.chain.steps] == [
            spine for _component, spine in LONGLIST_CHAIN
        ]
    finally:
        _cleanup(engine, task_id)


class _MinimalState:
    """Stands in for the state ``_with_plan`` rebuilds with ``type(state)(...)``.

    ``_with_plan`` passes the minimal field set; the real
    ``ContinuationState`` also requires ``parked_boundary`` and
    ``parked_component``, which ``_with_plan`` does not pass (a pre-existing
    gap, reported with this phase, not fixed here). The purpose read is what
    is under test.
    """

    def __init__(self, **fields: Any) -> None:
        self.__dict__.update(fields)


def test_the_api_resume_path_recomposes_the_walk_s_own_purpose(engine: Engine) -> None:
    """The API path: the caller reads the purpose and ``_with_plan`` composes it."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, walk_id = _parked_scoping_walk(engine)
        _set_purpose(engine, scope_id, "longlist")
        built = build(engine, task_id=task_id, capability_run_id=walk_id)
        state = _MinimalState(
            **{
                name: getattr(built, name)
                for name in (
                    "capability_run_id",
                    "plan",
                    "plan_id",
                    "plan_version",
                    "plan_row_id",
                    "chain",
                    "pause_points",
                    "pending_overlays",
                    "remaining_steps",
                    "step_outcomes",
                    "flagged_events",
                    "successful_runs",
                    "attempted_runs",
                    "blocked_discretionary",
                    "completed_components",
                    "last_check_in_payload",
                    "most_recent_attempted_run_id",
                    "session_id",
                )
            }
        )
        with engine.connect() as conn:
            purpose = purpose_of_walk(conn, task_id=task_id, capability_run_id=walk_id)
        assert purpose == "longlist"
        rebuilt = _with_plan(
            state, built.plan, built.plan_id, built.plan_version, OPTIONS_SCOPING, purpose=purpose
        )
        assert rebuilt.chain.components == LONGLIST_COMPONENTS
        unchanged = _with_plan(
            state, built.plan, built.plan_id, built.plan_version, OPTIONS_SCOPING
        )
        assert unchanged.chain.components == list(SCOPING_SPINE)
    finally:
        _cleanup(engine, task_id)


def test_purpose_of_walk_reads_none_for_an_evidence_search_walk(engine: Engine) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, _scope_id, walk_id = _parked_scoping_walk(engine)
        with engine.begin() as conn:
            conn.execute(
                update(evidence_scope)
                .where(evidence_scope.c.task_id == task_id)
                .values(purpose=None)
            )
            assert purpose_of_walk(conn, task_id=task_id, capability_run_id=walk_id) is None
            with pytest.raises(LookupError):
                purpose_of_walk(conn, task_id=task_id, capability_run_id=uuid.uuid4())
            assert (
                conn.execute(
                    capability_run.select().where(capability_run.c.capability_run_id == walk_id)
                ).one()
                is not None
            )
    finally:
        _cleanup(engine, task_id)
