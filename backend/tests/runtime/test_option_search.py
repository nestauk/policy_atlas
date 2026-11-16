"""Option searches as child walks, the runner's barriers and the pool (task 045, S2).

The contract's option-search half of "suggest and option searches"
(deliverable 4) and the runner half of "start": every entrant gets one child
walk under its own targeted intent record with ``parent_capability_run_id``
set; at most 15 per longlist walk with the user's and the report's never
dropped; a rebuild searches only new entrants; the cross-walk bound holds at
width 4; a failing child degrades the parent; the join timeout marks
stragglers ``interrupted``; a child never closes the Task Agent conversation.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.routers import sse
from policy_atlas.core import events
from policy_atlas.core.schema import capability_run, conversation, evidence_scope, option, runs
from policy_atlas.evidence_search.assess import classify as classify_module
from policy_atlas.evidence_search.assess.classify import MAX_CONCURRENT_CLASSIFY
from policy_atlas.evidence_search.assess.classify_prompt import ClassifyWire
from policy_atlas.options_scoping.design import OptionDesign
from policy_atlas.runtime import option_search, walk_pool
from policy_atlas.runtime import runner as runner_module
from policy_atlas.runtime.conversation_lifecycle import ensure_active_task_agent_conversation
from policy_atlas.runtime.runner import NullIO, RunPlanOutcome, run_plan
from policy_atlas.runtime.scoping_plan import (
    OPTION_SEARCH_CAP,
    OPTION_SEARCH_WIDTH,
    ScopingPlan,
    YourOption,
)
from tests.helpers import now, seed_scope, seed_walk
from tests.runtime.test_baseline_gate import (
    insert_scoping_plan_row,
    scoping_plan,
    seed_scoping_task,
)
from tests.runtime.test_runner import _cleanup, _runner_backends

# --- fixtures and helpers ---------------------------------------------------


def _design(name: str) -> OptionDesign:
    return OptionDesign(
        name=name,
        description=f"{name} for 16 to 24 year olds.",
        design_features=[f"{name.lower()} offer"],
        outcomes_served=["the NEET rate"],
    )


def _longlist_plan(*own: str) -> ScopingPlan:
    return scoping_plan().model_copy(
        update={
            "your_options": [
                YourOption(text=name.lower(), design=_design(name), turn_index=0) for name in own
            ]
        }
    )


def _seed_longlist(engine: Engine, plan: ScopingPlan) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Seed a scoping task, its plan and a longlist intent record.

    Returns:
        ``(task_id, longlist_scope_id, plan_id)``.
    """
    task_id, baseline_scope = seed_scoping_task(engine)
    plan_id = insert_scoping_plan_row(engine, task_id=task_id, scope_id=baseline_scope, plan=plan)
    with engine.begin() as conn:
        scope_id = seed_scope(
            conn,
            task_id,
            {"capability": "options_scoping"},
            intent="longlist intent",
            purpose="longlist",
            plan_id=plan_id,
        )
    return task_id, scope_id, plan_id


def _run_longlist(
    engine: Engine,
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
    plan_id: uuid.UUID,
    plan: ScopingPlan,
) -> RunPlanOutcome:
    return run_plan(
        engine,
        task_id=task_id,
        evidence_scope_id=scope_id,
        plan=plan,
        plan_id=plan_id,
        plan_version=1,
        plan_row_id=plan_id,
        backends=_runner_backends(),
        io=NullIO(),
        session_id=task_id,
    )


def _children(engine: Engine, task_id: uuid.UUID, parent: uuid.UUID) -> list[Any]:
    with engine.connect() as conn:
        return list(
            conn.execute(
                select(
                    capability_run.c.capability_run_id,
                    capability_run.c.status,
                    evidence_scope.c.purpose,
                    evidence_scope.c.intent,
                    evidence_scope.c.context,
                    evidence_scope.c.plan_id,
                )
                .select_from(
                    capability_run.join(
                        evidence_scope,
                        evidence_scope.c.evidence_scope_id == capability_run.c.evidence_scope_id,
                    )
                )
                .where(capability_run.c.task_id == task_id)
                .where(capability_run.c.parent_capability_run_id == parent)
            )
        )


def _await_children_ended(engine: Engine, task_id: uuid.UUID) -> None:
    """Let every child walk of the task settle before its rows are torn down."""
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            active = conn.execute(
                select(capability_run.c.capability_run_id)
                .where(capability_run.c.task_id == task_id)
                .where(capability_run.c.parent_capability_run_id.is_not(None))
                .where(capability_run.c.status.in_(("running", "paused")))
            ).first()
        if active is None:
            return
        time.sleep(0.05)


def _seed_option(
    engine: Engine, task_id: uuid.UUID, name: str, origin: str
) -> uuid.UUID:
    option_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            option.insert().values(
                option_id=option_id,
                task_id=task_id,
                name=name,
                description=f"{name}.",
                design=_design(name).model_dump(mode="json"),
                outcomes=["the NEET rate"],
                origin=origin,
                state="included",
                secondary_lever_types=[],
                created_at=now(),
                updated_at=now(),
            )
        )
    return option_id


def _seed_suggest_summary(
    engine: Engine, task_id: uuid.UUID, parent: uuid.UUID, entrants: list[uuid.UUID]
) -> uuid.UUID:
    """Write a suggest run whose completed summary names the entrants (Phase 4.2)."""
    from policy_atlas.core.schema import runs

    run_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            runs.insert().values(
                run_id=run_id,
                task_id=task_id,
                status="succeeded",
                started_at=now(),
                capability_run_id=parent,
            )
        )
        events.append(
            conn,
            task_id=task_id,
            run_id=run_id,
            event_type="component.completed",
            payload={"component": "suggest", "entrants": [str(e) for e in entrants]},
        )
    return run_id


def _seed_walk(
    engine: Engine,
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
    plan_id: uuid.UUID,
    *,
    parent: uuid.UUID | None = None,
    status: str = "running",
) -> uuid.UUID:
    with engine.begin() as conn:
        return seed_walk(
            conn, task_id, scope_id=scope_id, plan_id=plan_id, parent=parent, status=status
        ).walk_id


@pytest.fixture
def child_run_plan(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[Any], None]]:
    """Replace the run_plan a child walk calls; the parent keeps the real one.

    ``_run_child`` imports ``run_plan`` from the runner module at call time, so
    patching the module attribute reaches the children only (the test module
    and the runner's own loop hold the original).
    """

    def install(fake: Any) -> None:
        monkeypatch.setattr(runner_module, "run_plan", fake)

    yield install


@pytest.fixture(autouse=True)
def _no_progress_poll_outlives_its_test() -> Iterator[None]:
    """Stop any fan-out progress poll a test left running (round 12)."""
    yield
    for parent in list(option_search._progress_polls):
        option_search._stop_progress_poll(parent)


# --- the walk end to end on the stub backends -------------------------------


def test_a_stub_longlist_walk_fans_out_after_suggest_and_joins_before_the_screen(
    engine: Engine,
) -> None:
    """inherit → suggest → [fan-out] → acquire → [join] → screen_abstract … shortlist.

    Every entrant (the user's two, the stub's one suggestion) gets one child
    walk under its own targeted record naming the option, with the design's
    ``as_intent()`` as its intent, the confirmed plan version and
    ``acquire_only`` (task 046, S1, S2); both barriers emit under
    ``option_searches`` and the stream maps them to stage frames with the
    join's counts.
    """
    task_id: uuid.UUID | None = None
    try:
        plan = _longlist_plan("Youth guarantee", "Wage subsidy")
        task_id, scope_id, plan_id = _seed_longlist(engine, plan)
        outcome = _run_longlist(engine, task_id, scope_id, plan_id, plan)
        parent = outcome.capability_run_id
        assert parent is not None
        steps = [step.component for step in outcome.steps]
        assert steps == [
            "inherit",
            "suggest",
            "acquire",
            "screen_abstract",
            "classify",
            "appraise",
            "extract_interventions",
            "longlist",
            "option_profile",
            "constrain",
            "theme",
            "shortlist",
        ]

        children = _children(engine, task_id, parent)
        assert len(children) == 3
        assert all(child.status == "succeeded" for child in children)
        assert all(child.purpose == "targeted" for child in children)
        assert all(child.plan_id == plan_id for child in children)
        assert all(child.context["acquire_only"] is True for child in children)
        with engine.connect() as conn:
            options = {
                row.option_id: row
                for row in conn.execute(select(option).where(option.c.task_id == task_id))
            }
        searched = {uuid.UUID(child.context["option_id"]) for child in children}
        assert searched == set(options)
        for child in children:
            row = options[uuid.UUID(child.context["option_id"])]
            assert child.intent == OptionDesign.model_validate(row.design).as_intent()

        with engine.connect() as conn:
            log = events.read(conn, task_id)
        own = [
            entry
            for entry in log
            if entry["run_id"] in {step.run_id for step in outcome.steps}
            or entry["payload"].get("component") == "option_searches"
        ]
        order = [
            (entry["event_type"], entry["payload"].get("component"))
            for entry in own
            if entry["event_type"] in {"run.started", "component.completed"}
        ]
        fan_out = order.index(("run.started", "option_searches"))
        join = order.index(("component.completed", "option_searches"))
        assert order.index(("component.completed", "suggest")) < fan_out
        assert fan_out < order.index(("run.started", "acquire"))
        assert order.index(("component.completed", "acquire")) < join
        assert join < order.index(("run.started", "screen_abstract"))

        # The stream maps both barriers to the option_searches stage.
        with engine.connect() as conn:
            rows = [
                entry
                for entry in log
                if entry["payload"].get("component") == "option_searches"
            ]
            frames = sse._map_rows(conn, task_id=task_id, rows=rows, through=None)
        assert [(frame["type"], frame["stage"]) for frame in frames] == [
            ("stage.started", "option_searches"),
            ("stage.completed", "option_searches"),
        ]
        # Both name the walk (task 058, round 11): the events have no component
        # run, so a null id would let them through any run filter.
        assert {frame["capability_run_id"] for frame in frames} == {
            str(outcome.capability_run_id)
        }
        # The join's row also counts the sources the children acquired (task
        # 058, N2): the children's own acquire rows, never the parent's.
        parent_runs = {step.run_id for step in outcome.steps}
        child_acquired = sum(
            int(entry["payload"].get("acquired", 0))
            for entry in log
            if entry["event_type"] == "component.completed"
            and entry["payload"].get("component") == "acquire"
            and entry["run_id"] not in parent_runs
        )
        assert frames[1]["summary"] == {
            "total": 3,
            "finished": 3,
            "failed": 0,
            "sources": child_acquired,
        }
    finally:
        if task_id is not None:
            _await_children_ended(engine, task_id)
        _cleanup(engine, task_id)


# --- the entrants: the cap and the rebuild ----------------------------------


def test_the_cap_keeps_the_users_and_the_reports_entrants(engine: Engine) -> None:
    """A16: at most 15; the user's own and the report's are never the ones dropped."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, plan_id = _seed_longlist(engine, _longlist_plan())
        parent = _seed_walk(engine, task_id, scope_id, plan_id)
        own = [_seed_option(engine, task_id, f"Own {i}", "added_by_you") for i in range(3)]
        report = [
            _seed_option(engine, task_id, f"Report {i}", "from_evidence_search") for i in range(2)
        ]
        suggested = [_seed_option(engine, task_id, f"Model {i}", "suggested") for i in range(14)]
        suggest_run = _seed_suggest_summary(engine, task_id, parent, own + report + suggested)
        with engine.connect() as conn:
            chosen = option_search.entrants_for_search(
                conn, task_id=task_id, suggest_run_id=suggest_run
            )
        ids = [option_id for option_id, _design in chosen]
        assert len(ids) == OPTION_SEARCH_CAP
        assert ids[:5] == own + report
        assert ids[5:] == suggested[: OPTION_SEARCH_CAP - 5]
    finally:
        _cleanup(engine, task_id)


def test_the_users_and_the_reports_entrants_run_even_past_the_cap(engine: Engine) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, plan_id = _seed_longlist(engine, _longlist_plan())
        parent = _seed_walk(engine, task_id, scope_id, plan_id)
        kept = [_seed_option(engine, task_id, f"Own {i}", "added_by_you") for i in range(16)]
        model = _seed_option(engine, task_id, "Model", "suggested")
        suggest_run = _seed_suggest_summary(engine, task_id, parent, [*kept, model])
        with engine.connect() as conn:
            chosen = option_search.entrants_for_search(
                conn, task_id=task_id, suggest_run_id=suggest_run
            )
        assert [option_id for option_id, _design in chosen] == kept
    finally:
        _cleanup(engine, task_id)


def test_without_a_suggest_summary_the_users_options_are_the_entrants(engine: Engine) -> None:
    """A failed suggest (non-spine) leaves no summary; the user's own rows still stand."""
    task_id: uuid.UUID | None = None
    try:
        task_id, _scope_id, _plan_id = _seed_longlist(engine, _longlist_plan())
        own = _seed_option(engine, task_id, "Own", "added_by_you")
        _seed_option(engine, task_id, "Model", "suggested")
        _seed_option(engine, task_id, "Cluster", "clustered")
        with engine.connect() as conn:
            chosen = option_search.entrants_for_search(conn, task_id=task_id, suggest_run_id=None)
        assert [option_id for option_id, _design in chosen] == [own]
    finally:
        _cleanup(engine, task_id)


def test_a_merged_duplicate_is_no_entrant(engine: Engine) -> None:
    """Owner ruling 2026-09-24: a duplicate constrain merged stays merged."""
    task_id: uuid.UUID | None = None
    try:
        task_id, _scope_id, _plan_id = _seed_longlist(engine, _longlist_plan())
        own = _seed_option(engine, task_id, "Own", "added_by_you")
        twin = _seed_option(engine, task_id, "Own twin", "added_by_you")
        with engine.begin() as conn:
            conn.execute(
                option.update().where(option.c.option_id == twin).values(merged_into_option_id=own)
            )
        with engine.connect() as conn:
            chosen = option_search.entrants_for_search(conn, task_id=task_id, suggest_run_id=None)
        assert [option_id for option_id, _design in chosen] == [own]
    finally:
        _cleanup(engine, task_id)


def _targeted_walk(
    engine: Engine,
    task_id: uuid.UUID,
    plan_id: uuid.UUID,
    option_id: uuid.UUID,
    *,
    parent: uuid.UUID | None,
    status: str,
) -> uuid.UUID:
    targeted = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            evidence_scope.insert().values(
                evidence_scope_id=targeted,
                task_id=task_id,
                intent="an option",
                context={"option_id": str(option_id)},
                created_at=now(),
                purpose="targeted",
                plan_id=plan_id,
            )
        )
    return _seed_walk(engine, task_id, targeted, plan_id, parent=parent, status=status)


def test_a_rebuild_searches_only_entrants_without_a_search(engine: Engine) -> None:
    """P12: an entrant already searched on this task (a finished walk under a
    targeted record naming it) is not searched again; a new entrant is."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, plan_id = _seed_longlist(engine, _longlist_plan())
        parent = _seed_walk(engine, task_id, scope_id, plan_id, status="succeeded")
        old = _seed_option(engine, task_id, "Old", "added_by_you")
        new = _seed_option(engine, task_id, "New", "suggested")
        targeted = uuid.uuid4()
        with engine.begin() as conn:
            conn.execute(
                evidence_scope.insert().values(
                    evidence_scope_id=targeted,
                    task_id=task_id,
                    intent="old option",
                    context={"option_id": str(old)},
                    created_at=now(),
                    purpose="targeted",
                    plan_id=plan_id,
                )
            )
        _seed_walk(engine, task_id, targeted, plan_id, parent=parent, status="succeeded")
        suggest_run = _seed_suggest_summary(engine, task_id, parent, [old, new])
        with engine.connect() as conn:
            assert option_search.searched_option_ids(conn, task_id=task_id) == {old}
            chosen = option_search.entrants_for_search(
                conn, task_id=task_id, suggest_run_id=suggest_run
            )
        assert [option_id for option_id, _design in chosen] == [new]
    finally:
        _cleanup(engine, task_id)


def test_a_rebuild_retries_a_search_that_did_not_finish(engine: Engine) -> None:
    """B2: only a succeeded or degraded search counts as done; a failed,
    aborted or interrupted one (of a build or of the verb add) is retried."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, plan_id = _seed_longlist(engine, _longlist_plan())
        parent = _seed_walk(engine, task_id, scope_id, plan_id, status="degraded")
        names = ("Done", "Degraded", "Failed", "Interrupted", "Aborted")
        statuses = ("succeeded", "degraded", "failed", "interrupted", "aborted")
        ids = [_seed_option(engine, task_id, name, "added_by_you") for name in names]
        for option_id, status in zip(ids, statuses, strict=True):
            _targeted_walk(
                engine,
                task_id,
                plan_id,
                option_id,
                parent=None if status == "aborted" else parent,
                status=status,
            )
        suggest_run = _seed_suggest_summary(engine, task_id, parent, ids)
        with engine.connect() as conn:
            assert option_search.searched_option_ids(conn, task_id=task_id) == set(ids[:2])
            chosen = option_search.entrants_for_search(
                conn, task_id=task_id, suggest_run_id=suggest_run
            )
        assert [option_id for option_id, _design in chosen] == ids[2:]
    finally:
        _cleanup(engine, task_id)


def test_the_fan_out_runs_once_across_a_resume(engine: Engine, child_run_plan: Any) -> None:
    """A parked-and-resumed walk finds the fan-out's record and does not re-dispatch."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, plan_id = _seed_longlist(engine, _longlist_plan("Own"))
        parent = _seed_walk(engine, task_id, scope_id, plan_id)
        _seed_option(engine, task_id, "Own", "added_by_you")
        child_run_plan(lambda *args, **kwargs: None)
        plan_row = {
            "plan_id": plan_id,
            "version": 1,
            "payload": _longlist_plan("Own").model_dump(mode="json"),
        }
        first = option_search.dispatch_option_searches(
            engine,
            task_id=task_id,
            parent_id=parent,
            plan_row=plan_row,
            suggest_run_id=None,
            backends=_runner_backends(),
            session_id=task_id,
        )
        again = option_search.dispatch_option_searches(
            engine,
            task_id=task_id,
            parent_id=parent,
            plan_row=plan_row,
            suggest_run_id=None,
            backends=_runner_backends(),
            session_id=task_id,
        )
        assert len(first) == 1
        assert again == first
    finally:
        _cleanup(engine, task_id)


def test_a_resume_past_the_join_publishes_no_count(
    engine: Engine, child_run_plan: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Task 058 review: a finished stage's count is not sent again on a resume."""
    task_id: uuid.UUID | None = None
    ticks: list[dict[str, Any]] = []

    class FakeHub:
        def publish_tick(self, task_id: uuid.UUID, **payload: Any) -> None:
            ticks.append(payload)

    monkeypatch.setattr(option_search, "tick_hub", FakeHub())
    monkeypatch.setattr(option_search, "OPTION_SEARCH_JOIN_POLL", 0.05)
    try:
        child_run_plan(lambda *args, **kwargs: None)
        plan = _longlist_plan("Own")
        task_id, scope_id, plan_id = _seed_longlist(engine, plan)
        parent = _seed_walk(engine, task_id, scope_id, plan_id)
        _seed_option(engine, task_id, "Own", "added_by_you")
        plan_row = {"plan_id": plan_id, "version": 1, "payload": plan.model_dump(mode="json")}
        children = option_search.dispatch_option_searches(
            engine,
            task_id=task_id,
            parent_id=parent,
            plan_row=plan_row,
            suggest_run_id=None,
            backends=_runner_backends(),
            session_id=task_id,
        )
        option_search.join_option_searches(
            engine, task_id=task_id, parent_id=parent, child_ids=children, timeout=10
        )
        ticks.clear()

        again = option_search.dispatch_option_searches(
            engine,
            task_id=task_id,
            parent_id=parent,
            plan_row=plan_row,
            suggest_run_id=None,
            backends=_runner_backends(),
            session_id=task_id,
        )

        assert again == children
        assert ticks == []
        assert parent not in option_search._progress_polls
    finally:
        _cleanup(engine, task_id)


# --- failure, the timeout and the conversation ------------------------------


def _open_row(engine: Engine, kwargs: dict[str, Any]) -> None:
    """Open a child walk's row as the runner would, from ``run_plan``'s kwargs."""
    with engine.begin() as conn:
        seed_walk(
            conn,
            kwargs["task_id"],
            walk_id=kwargs["capability_run_id"],
            scope_id=kwargs["evidence_scope_id"],
            plan_id=kwargs["plan_id"],
            plan_version=kwargs["plan_version"],
            status="running",
            parent=kwargs["parent_capability_run_id"],
        )


def test_a_failing_child_degrades_the_parent(
    engine: Engine, child_run_plan: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed child is a skipped entrant: the parent ends ``degraded``, never ``failed``."""
    task_id: uuid.UUID | None = None

    def failing_child(*args: Any, **kwargs: Any) -> None:
        _open_row(engine, kwargs)
        raise RuntimeError("the option search broke")

    original_attempt = runner_module._run_step_attempt

    def phase_five_stands_in(engine_: Engine, **kwargs: Any) -> Any:
        # The Phase 5 steps are not what this test is about: they succeed, so
        # the only thing that can degrade the walk is the children.
        if kwargs["step"].component in {"longlist", "option_profile", "constrain"}:
            return runner_module._AttemptOutcome(
                run_id=uuid.uuid4(),
                status="succeeded",
                wall_clock_s=0.0,
                headline_counts={},
                error=None,
            )
        return original_attempt(engine_, **kwargs)

    try:
        child_run_plan(failing_child)
        monkeypatch.setattr(runner_module, "_run_step_attempt", phase_five_stands_in)
        plan = _longlist_plan("Youth guarantee")
        task_id, scope_id, plan_id = _seed_longlist(engine, plan)
        outcome = _run_longlist(engine, task_id, scope_id, plan_id, plan)
        assert outcome.status == "degraded"
        skipped = [step for step in outcome.steps if step.component == "option_searches"]
        assert len(skipped) == 1
        assert skipped[0].status == "skipped"
        assert skipped[0].reason == "2 of 2 option searches did not finish"
        assert {"component": "option_searches", "status": "skipped",
                "reason": skipped[0].reason} in outcome.flagged_events
        parent = outcome.capability_run_id
        assert parent is not None
        children = _children(engine, task_id, parent)
        assert sorted(child.status for child in children) == ["failed", "failed"]
        with engine.connect() as conn:
            walk = conn.execute(
                select(capability_run.c.status).where(capability_run.c.capability_run_id == parent)
            ).scalar_one()
        assert walk == "degraded"
    finally:
        if task_id is not None:
            _await_children_ended(engine, task_id)
        _cleanup(engine, task_id)


def test_the_join_timeout_marks_stragglers_interrupted(
    engine: Engine, child_run_plan: Any
) -> None:
    """After the timeout a child still running is ``interrupted`` and counted failed;
    its late finish keeps that record."""
    task_id: uuid.UUID | None = None
    release = threading.Event()
    opened = threading.Event()

    def stuck_child(*args: Any, **kwargs: Any) -> None:
        _open_row(engine, kwargs)
        opened.set()
        release.wait(timeout=30)
        runner_module._finish_run(
            engine,
            [],
            [],
            status="succeeded",
            capability_run_id=kwargs["capability_run_id"],
            task_id=kwargs["task_id"],
        )

    try:
        child_run_plan(stuck_child)
        plan = _longlist_plan("Own")
        task_id, scope_id, plan_id = _seed_longlist(engine, plan)
        parent = _seed_walk(engine, task_id, scope_id, plan_id)
        _seed_option(engine, task_id, "Own", "added_by_you")
        children = option_search.dispatch_option_searches(
            engine,
            task_id=task_id,
            parent_id=parent,
            plan_row={"plan_id": plan_id, "version": 1, "payload": plan.model_dump(mode="json")},
            suggest_run_id=None,
            backends=_runner_backends(),
            session_id=task_id,
        )
        assert opened.wait(timeout=10)
        joined = option_search.join_option_searches(
            engine, task_id=task_id, parent_id=parent, child_ids=children, timeout=0.3
        )
        assert (joined.total, joined.finished, joined.failed) == (1, 0, 1)
        assert joined.interrupted == tuple(children)
        with engine.connect() as conn:
            assert option_search.child_walks(conn, task_id=task_id, parent_id=parent) == {
                children[0]: "interrupted"
            }
        release.set()
        _await_children_ended(engine, task_id)
        time.sleep(0.2)
        with engine.connect() as conn:
            assert option_search.child_walks(conn, task_id=task_id, parent_id=parent) == {
                children[0]: "interrupted"
            }
    finally:
        release.set()
        _cleanup(engine, task_id)


def test_the_join_publishes_finished_searches_and_acquired_sources(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    task_id: uuid.UUID | None = None
    ticks: list[tuple[uuid.UUID, dict[str, Any]]] = []

    class FakeHub:
        def publish_tick(self, task_id: uuid.UUID, **payload: Any) -> None:
            ticks.append((task_id, payload))

    monkeypatch.setattr(option_search, "tick_hub", FakeHub())
    try:
        task_id, scope_id, plan_id = _seed_longlist(engine, _longlist_plan())
        parent = _seed_walk(engine, task_id, scope_id, plan_id)
        statuses = ("succeeded", "degraded", "failed")
        acquired = (7, 5, 2)
        children: list[uuid.UUID] = []
        with engine.begin() as conn:
            for status, count in zip(statuses, acquired, strict=True):
                child = seed_walk(
                    conn,
                    task_id,
                    scope_id=scope_id,
                    plan_id=plan_id,
                    parent=parent,
                    status=status,
                ).walk_id
                children.append(child)
                run_id = uuid.uuid4()
                conn.execute(
                    runs.insert().values(
                        run_id=run_id,
                        task_id=task_id,
                        status="succeeded",
                        started_at=now(),
                        capability_run_id=child,
                    )
                )
                events.append(
                    conn,
                    task_id=task_id,
                    run_id=run_id,
                    event_type="component.completed",
                    payload={"component": "acquire", "acquired": count},
                )

        outcome = option_search.join_option_searches(
            engine,
            task_id=task_id,
            parent_id=parent,
            child_ids=children,
            timeout=0,
        )

        assert (outcome.finished, outcome.total) == (2, 3)
        assert ticks[-1] == (
            task_id,
            {
                "stage": "option_searches",
                "activity": "2 of 3 searches done · 14 sources",
                "done": 2,
                "total": 3,
                "unit": "searches",
                "run_id": parent,
            },
        )
        with engine.connect() as conn:
            completed = next(
                entry["payload"]
                for entry in events.read(conn, task_id)
                if entry["event_type"] == "component.completed"
                and entry["payload"].get("component") == "option_searches"
            )
        assert completed == {
            "component": "option_searches",
            "capability_run_id": str(parent),
            "total": 3,
            "finished": 2,
            "failed": 1,
            "sources": 14,
        }
    finally:
        _cleanup(engine, task_id)


def test_the_count_shows_from_the_fan_out_and_stays_current_until_the_join(
    engine: Engine, child_run_plan: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Round 12: the first tick goes out at the fan-out, before the walk's own
    search, and a poll keeps it current; the join takes over and stops it."""
    task_id: uuid.UUID | None = None
    release = threading.Event()
    opened = threading.Event()
    ticks: list[dict[str, Any]] = []

    class FakeHub:
        def publish_tick(self, task_id: uuid.UUID, **payload: Any) -> None:
            ticks.append(payload)

    def stuck_child(*args: Any, **kwargs: Any) -> None:
        _open_row(engine, kwargs)
        opened.set()
        release.wait(timeout=30)
        runner_module._finish_run(
            engine,
            [],
            [],
            status="succeeded",
            capability_run_id=kwargs["capability_run_id"],
            task_id=kwargs["task_id"],
        )

    monkeypatch.setattr(option_search, "tick_hub", FakeHub())
    monkeypatch.setattr(option_search, "OPTION_SEARCH_JOIN_POLL", 0.05)
    try:
        child_run_plan(stuck_child)
        plan = _longlist_plan("Own")
        task_id, scope_id, plan_id = _seed_longlist(engine, plan)
        parent = _seed_walk(engine, task_id, scope_id, plan_id)
        _seed_option(engine, task_id, "Own", "added_by_you")
        children = option_search.dispatch_option_searches(
            engine,
            task_id=task_id,
            parent_id=parent,
            plan_row={"plan_id": plan_id, "version": 1, "payload": plan.model_dump(mode="json")},
            suggest_run_id=None,
            backends=_runner_backends(),
            session_id=task_id,
        )
        # At the fan-out itself, before anything else runs.
        assert ticks[0] == {
            "stage": "option_searches",
            "activity": "0 of 1 searches done · 0 sources",
            "done": 0,
            "total": 1,
            "unit": "searches",
            "run_id": parent,
        }
        assert opened.wait(timeout=10)
        deadline = time.monotonic() + 5
        while len(ticks) < 3 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert len(ticks) >= 3, "the poll keeps the count current while the walk searches"
        assert parent in option_search._progress_polls
        release.set()
        joined = option_search.join_option_searches(
            engine, task_id=task_id, parent_id=parent, child_ids=children, timeout=10
        )
        assert (joined.total, joined.finished) == (1, 1)
        assert parent not in option_search._progress_polls
        assert ticks[-1]["activity"] == "1 of 1 searches done · 0 sources"
    finally:
        release.set()
        _cleanup(engine, task_id)


def test_the_progress_poll_ends_by_itself_once_every_search_has_ended(
    engine: Engine, child_run_plan: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A walk resumed past its join never joins again: the poll still stops."""
    task_id: uuid.UUID | None = None
    monkeypatch.setattr(option_search, "OPTION_SEARCH_JOIN_POLL", 0.05)
    try:
        plan = _longlist_plan("Own")
        task_id, scope_id, plan_id = _seed_longlist(engine, plan)
        parent = _seed_walk(engine, task_id, scope_id, plan_id)
        _seed_option(engine, task_id, "Own", "added_by_you")

        def quick_child(*args: Any, **kwargs: Any) -> None:
            _open_row(engine, kwargs)
            runner_module._finish_run(
                engine,
                [],
                [],
                status="succeeded",
                capability_run_id=kwargs["capability_run_id"],
                task_id=kwargs["task_id"],
            )

        child_run_plan(quick_child)
        option_search.dispatch_option_searches(
            engine,
            task_id=task_id,
            parent_id=parent,
            plan_row={"plan_id": plan_id, "version": 1, "payload": plan.model_dump(mode="json")},
            suggest_run_id=None,
            backends=_runner_backends(),
            session_id=task_id,
        )
        deadline = time.monotonic() + 10
        while parent in option_search._progress_polls and time.monotonic() < deadline:
            time.sleep(0.02)
        assert parent not in option_search._progress_polls
    finally:
        _cleanup(engine, task_id)


def test_a_finished_child_never_closes_the_task_agent_conversation(
    engine: Engine,
) -> None:
    """P3: the thread the user is watching belongs to the parent, not its children."""
    task_id: uuid.UUID | None = None
    try:
        plan = _longlist_plan("Own")
        task_id, scope_id, plan_id = _seed_longlist(engine, plan)
        parent = _seed_walk(engine, task_id, scope_id, plan_id)
        option_id = _seed_option(engine, task_id, "Own", "added_by_you")
        with engine.begin() as conn:
            conversation_id = ensure_active_task_agent_conversation(
                conn, task_id=task_id, now=now()
            )
        child = option_search.run_option_search(
            engine,
            task_id=task_id,
            plan_row={"plan_id": plan_id, "version": 1, "payload": plan.model_dump(mode="json")},
            design=_design("Own"),
            option_id=option_id,
            parent_capability_run_id=parent,
            backends=_runner_backends(),
            user_id="user-1",
        )
        joined = option_search.join_option_searches(
            engine, task_id=task_id, parent_id=parent, child_ids=[child], timeout=30
        )
        assert joined.finished == 1
        with engine.connect() as conn:
            status = conn.execute(
                select(capability_run.c.status).where(
                    capability_run.c.capability_run_id == child
                )
            ).scalar_one()
            thread = conn.execute(
                select(conversation.c.status).where(conversation.c.id == conversation_id)
            ).scalar_one()
        assert status in {"succeeded", "degraded"}
        assert thread == "active"
    finally:
        _cleanup(engine, task_id)


# --- the pool and the semaphores --------------------------------------------


def test_option_searches_run_at_the_configured_width(engine: Engine, child_run_plan: Any) -> None:
    """The cross-walk bound: more searches than the width, never more at once than it.

    The width is ``OPTION_SEARCH_WIDTH`` (4 until task 057, 10 since); the test seeds two
    more options than the width so the pool's ceiling, not the option count, sets the peak.
    """
    task_id: uuid.UUID | None = None
    lock = threading.Lock()
    live = 0
    peak = 0

    def counted_child(*args: Any, **kwargs: Any) -> None:
        nonlocal live, peak
        with lock:
            live += 1
            peak = max(peak, live)
        time.sleep(0.2)
        with lock:
            live -= 1

    try:
        child_run_plan(counted_child)
        plan = _longlist_plan()
        task_id, scope_id, plan_id = _seed_longlist(engine, plan)
        parent = _seed_walk(engine, task_id, scope_id, plan_id)
        option_count = OPTION_SEARCH_WIDTH + 2
        for i in range(option_count):
            _seed_option(engine, task_id, f"Own {i}", "added_by_you")
        children = option_search.dispatch_option_searches(
            engine,
            task_id=task_id,
            parent_id=parent,
            plan_row={"plan_id": plan_id, "version": 1, "payload": plan.model_dump(mode="json")},
            suggest_run_id=None,
            backends=_runner_backends(),
            session_id=task_id,
        )
        assert len(children) == option_count
        # 30 s, not 10 (task 056, 2026-11-02): under the eight-worker suite the child
        # runs' rows and statuses arrive later than on an idle core; the assertions below
        # are unchanged, only the wait is longer.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not all(
            option_search._ended(child, None) for child in children
        ):
            time.sleep(0.05)
        assert peak == OPTION_SEARCH_WIDTH
        assert walk_pool.option_search_pool()._max_workers == OPTION_SEARCH_WIDTH
    finally:
        _cleanup(engine, task_id)


def test_the_classify_slots_bound_every_walk_together() -> None:
    """Three concurrent classify fan-outs share one budget of provider calls."""
    lock = threading.Lock()
    live = 0
    peak = 0

    class _SlowBackend:
        mode = "stub"

        def classify(self, payload: Any) -> tuple[ClassifyWire, dict[str, int]]:
            nonlocal live, peak
            with lock:
                live += 1
                peak = max(peak, live)
            time.sleep(0.05)
            with lock:
                live -= 1
            raise RuntimeError("not needed: the bound is what is measured")

    docs = [
        classify_module._ClassifyDoc(
            tss_id=uuid.uuid4(),
            source_snapshot_id=uuid.uuid4(),
            metadata={},
            payload=None,  # type: ignore[arg-type]
        )
        for _ in range(MAX_CONCURRENT_CLASSIFY)
    ]
    threads = [
        threading.Thread(
            target=classify_module._run_classification_calls,
            args=(docs,),
            kwargs={"classification_backend": _SlowBackend()},
        )
        for _ in range(3)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert peak == MAX_CONCURRENT_CLASSIFY
    assert walk_pool.CLASSIFY_SLOTS._value == MAX_CONCURRENT_CLASSIFY


def test_the_ingest_slots_are_all_returned() -> None:
    """Each parse job holds one slot while it runs and gives it back, including
    a job killed at its timeout (task 057: one process per document)."""
    from policy_atlas.evidence_search.sourcing.ingest_full_text import (
        DEFAULT_MAX_WORKERS,
        run_parse_worker,
    )
    from tests.evidence_search.sourcing.test_ingest_full_text import _sleep_by_marker_parse

    fast = run_parse_worker(
        _sleep_by_marker_parse, b"fast", "text/plain", thin_min=0, timeout=20.0
    )
    slow = run_parse_worker(
        _sleep_by_marker_parse, b"slow", "text/plain", thin_min=0, timeout=1.0
    )
    assert fast["status"] == "ok"
    assert slow == {"status": "error", "reason": "timeout"}
    assert walk_pool.INGEST_SLOTS._value == DEFAULT_MAX_WORKERS


# --- the parent's end cleans up its children (A2, A6, A11) -------------------


def _stuck_until(
    release: threading.Event, engine: Engine, opened: threading.Event | None = None
) -> Callable[..., None]:
    """A child that opens its row as the runner does, then waits to be released.

    Like the runner it ends itself at once when abandoned before its row
    existed; released, it finishes ``succeeded`` through ``_finish_run``.
    ``opened`` (when given) is set once the row exists, for a test that must
    not race the pool: a child cancelled before it starts never opens a row.
    """

    def child(*args: Any, **kwargs: Any) -> None:
        _open_row(engine, kwargs)
        if opened is not None:
            opened.set()
        if option_search.end_if_abandoned(
            engine, task_id=kwargs["task_id"], child_id=kwargs["capability_run_id"]
        ):
            return
        release.wait(timeout=30)
        runner_module._finish_run(
            engine,
            [],
            [],
            status="succeeded",
            capability_run_id=kwargs["capability_run_id"],
            task_id=kwargs["task_id"],
        )

    return child


def _await_statuses(
    engine: Engine, task_id: uuid.UUID, children: list[uuid.UUID], want: str
) -> dict[uuid.UUID, str]:
    # 30 s, not 10: see test_option_searches_run_at_width_four (the parallel suite).
    deadline = time.monotonic() + 30.0
    found: dict[uuid.UUID, str] = {}
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            found = {
                row.capability_run_id: row.status
                for row in conn.execute(
                    select(capability_run.c.capability_run_id, capability_run.c.status).where(
                        capability_run.c.capability_run_id.in_(children)
                    )
                )
            }
        if len(found) == len(children) and set(found.values()) == {want}:
            break
        time.sleep(0.05)
    return found


def _terminal_events(engine: Engine, task_id: uuid.UUID, child: uuid.UUID) -> list[str]:
    with engine.connect() as conn:
        return [
            entry["event_type"]
            for entry in events.read(conn, task_id)
            if entry["event_type"] in {"run.finished", "run.interrupted"}
            and entry["payload"].get("capability_run_id") == str(child)
        ]


def _fan_out_children(engine: Engine, task_id: uuid.UUID) -> list[uuid.UUID]:
    with engine.connect() as conn:
        parent = conn.execute(
            select(capability_run.c.capability_run_id)
            .where(capability_run.c.task_id == task_id)
            .where(capability_run.c.parent_capability_run_id.is_(None))
            .where(capability_run.c.capability == "options_scoping")
            .order_by(capability_run.c.started_at.desc())
        ).first()
        assert parent is not None
        children = option_search.dispatched_children(
            conn, task_id=task_id, parent_id=parent.capability_run_id
        )
    assert children
    return children


@pytest.mark.parametrize("how", ["spine_failure", "raise"])
def test_a_walk_that_ends_before_its_join_interrupts_its_children(
    engine: Engine, child_run_plan: Any, monkeypatch: pytest.MonkeyPatch, how: str
) -> None:
    """A2: a spine failure (any ``_finish_run``) or a raise after the fan-out
    leaves no child running; each ends ``interrupted`` with one terminal event,
    and its late finish changes nothing (A6)."""
    task_id: uuid.UUID | None = None
    release = threading.Event()
    original_attempt = runner_module._run_step_attempt

    def acquire_breaks(engine_: Engine, **kwargs: Any) -> Any:
        if kwargs["step"].component == "acquire":
            if how == "raise":
                raise RuntimeError("the walk broke")
            return runner_module._AttemptOutcome(
                run_id=uuid.uuid4(),
                status="failed",
                wall_clock_s=0.0,
                headline_counts={},
                error="acquire failed",
            )
        return original_attempt(engine_, **kwargs)

    try:
        child_run_plan(_stuck_until(release, engine))
        monkeypatch.setattr(runner_module, "_run_step_attempt", acquire_breaks)
        plan = _longlist_plan("Youth guarantee")
        task_id, scope_id, plan_id = _seed_longlist(engine, plan)
        if how == "raise":
            with pytest.raises(RuntimeError, match="the walk broke"):
                _run_longlist(engine, task_id, scope_id, plan_id, plan)
        else:
            outcome = _run_longlist(engine, task_id, scope_id, plan_id, plan)
            assert outcome.status == "failed"
        children = _fan_out_children(engine, task_id)
        assert len(children) == 2
        statuses = _await_statuses(engine, task_id, children, "interrupted")
        assert statuses == dict.fromkeys(children, "interrupted")
        release.set()
        _await_children_ended(engine, task_id)
        time.sleep(0.2)
        assert _await_statuses(engine, task_id, children, "interrupted") == statuses
        for child in children:
            assert _terminal_events(engine, task_id, child) == ["run.interrupted"]
    finally:
        release.set()
        if task_id is not None:
            _await_children_ended(engine, task_id)
        _cleanup(engine, task_id)


def test_a_fan_out_that_raises_part_way_interrupts_the_children_it_sent(
    engine: Engine, child_run_plan: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A2/L5: a child submitted before the fan-out raised (so no fan-out record
    names it) is still ended."""
    task_id: uuid.UUID | None = None
    release = threading.Event()
    opened = threading.Event()
    sent: list[uuid.UUID] = []
    original = option_search.run_option_search

    def second_breaks(*args: Any, **kwargs: Any) -> uuid.UUID:
        if sent:
            # Let the first child open its row before the fan-out raises: a child
            # the pool has not started yet is cancelled and leaves no row to end
            # (that path is the join's own test). Under a loaded suite the pool
            # thread can lag the raise by seconds, which read as a flake at 10 s
            # and again at 30 s.
            assert opened.wait(timeout=30), "the first child never opened its row"
            raise RuntimeError("the second dispatch broke")
        sent.append(original(*args, **kwargs))
        return sent[-1]

    try:
        child_run_plan(_stuck_until(release, engine, opened))
        monkeypatch.setattr(option_search, "run_option_search", second_breaks)
        plan = _longlist_plan()
        task_id, scope_id, plan_id = _seed_longlist(engine, plan)
        parent = _seed_walk(engine, task_id, scope_id, plan_id)
        _seed_option(engine, task_id, "One", "added_by_you")
        _seed_option(engine, task_id, "Two", "added_by_you")
        with pytest.raises(RuntimeError, match="second dispatch"):
            option_search.dispatch_option_searches(
                engine,
                task_id=task_id,
                parent_id=parent,
                plan_row={
                    "plan_id": plan_id,
                    "version": 1,
                    "payload": plan.model_dump(mode="json"),
                },
                suggest_run_id=None,
                backends=_runner_backends(),
                session_id=task_id,
            )
        assert len(sent) == 1
        assert _await_statuses(engine, task_id, sent, "interrupted") == {sent[0]: "interrupted"}
    finally:
        release.set()
        if task_id is not None:
            _await_children_ended(engine, task_id)
        _cleanup(engine, task_id)


def test_interrupting_a_still_queued_child_does_not_deadlock(engine: Engine) -> None:
    """A queued child's cancel runs its done callback (``_forget``) in the
    calling thread; with the handles lock held there, the thread waited on
    itself forever (the intermittent CI hang)."""
    from concurrent.futures import Future

    child = uuid.uuid4()
    queued: Future[None] = Future()
    with option_search._handles_lock:
        option_search._futures[child] = queued
    queued.add_done_callback(lambda _done: option_search._forget(child))
    worker = threading.Thread(
        target=option_search._interrupt_children,
        args=(engine,),
        kwargs={"task_id": uuid.uuid4(), "child_ids": [child]},
        daemon=True,
    )
    worker.start()
    worker.join(timeout=10)
    assert not worker.is_alive(), "interrupting a queued child deadlocked"
    assert queued.cancelled()
    assert child not in option_search._futures


def test_a_child_abandoned_before_its_row_ends_interrupted_on_opening(engine: Engine) -> None:
    """A11: the join abandoned the child before its row existed; the child
    ends ``interrupted`` as soon as it opens the row and runs no step."""
    task_id: uuid.UUID | None = None
    child = uuid.uuid4()
    try:
        plan = _longlist_plan("Own")
        task_id, scope_id, plan_id = _seed_longlist(engine, plan)
        parent = _seed_walk(engine, task_id, scope_id, plan_id)
        option_id = _seed_option(engine, task_id, "Own", "added_by_you")
        targeted = uuid.uuid4()
        with engine.begin() as conn:
            conn.execute(
                evidence_scope.insert().values(
                    evidence_scope_id=targeted,
                    task_id=task_id,
                    intent=_design("Own").as_intent(),
                    context={"capability": "options_scoping", "option_id": str(option_id)},
                    created_at=now(),
                    purpose="targeted",
                    plan_id=plan_id,
                )
            )
        with option_search._handles_lock:
            option_search._abandoned.add(child)
        outcome = run_plan(
            engine,
            task_id=task_id,
            evidence_scope_id=targeted,
            plan=option_search.unattended_plan(plan.model_dump(mode="json")),
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=NullIO(),
            session_id=task_id,
            capability_run_id=child,
            parent_capability_run_id=parent,
        )
        assert outcome.steps == []
        with engine.connect() as conn:
            assert option_search.child_walks(conn, task_id=task_id, parent_id=parent) == {
                child: "interrupted"
            }
        assert _terminal_events(engine, task_id, child) == ["run.interrupted"]
    finally:
        with option_search._handles_lock:
            option_search._abandoned.discard(child)
        _cleanup(engine, task_id)


@pytest.mark.parametrize("parented", [True, False])
def test_a_late_finish_never_overwrites_an_ended_option_search(
    engine: Engine, parented: bool
) -> None:
    """A6: an option search already ended by the join (or its parent's end) —
    a child or the verb add's parentless one — keeps that status, and its late
    finish appends no second terminal event."""
    task_id: uuid.UUID | None = None
    try:
        plan = _longlist_plan("Own")
        task_id, scope_id, plan_id = _seed_longlist(engine, plan)
        parent = _seed_walk(engine, task_id, scope_id, plan_id)
        option_id = _seed_option(engine, task_id, "Own", "added_by_you")
        child = _targeted_walk(
            engine,
            task_id,
            plan_id,
            option_id,
            parent=parent if parented else None,
            status="running",
        )
        assert option_search._end_child(
            engine, task_id=task_id, child_id=child, status="failed"
        )
        runner_module._finish_run(
            engine, [], [], status="succeeded", capability_run_id=child, task_id=task_id
        )
        with engine.connect() as conn:
            status = conn.execute(
                select(capability_run.c.status).where(capability_run.c.capability_run_id == child)
            ).scalar_one()
        assert status == "failed"
        assert _terminal_events(engine, task_id, child) == ["run.finished"]
    finally:
        _cleanup(engine, task_id)


# --- the fan-out's stage (task 054's 058 alignment, A3) ---------------------


@pytest.mark.parametrize(
    ("stage", "line"),
    [
        (option_search.OPTION_SEARCHES_STAGE, "1 of 2 searches done · 1,234 sources"),
        (option_search.TOC_ITEM_SEARCHES_STAGE, "1 of 2 searches done · 1,234 found"),
        (option_search.TOC_NEW_LINK_SEARCHES_STAGE, "1 of 2 searches done · 1,234 found"),
        (option_search.TOC_RETRY_SEARCHES_STAGE, "1 of 2 searches done · 1,234 found"),
    ],
)
def test_the_progress_tick_names_the_fan_outs_stage(
    monkeypatch: pytest.MonkeyPatch, stage: str, line: str
) -> None:
    """A theory of change's fan-outs tick under their own key, Options scoping's as before."""
    from contextlib import nullcontext
    from typing import cast

    ticks: list[dict[str, Any]] = []
    done, running = uuid.uuid4(), uuid.uuid4()

    class FakeHub:
        def publish_tick(self, task_id: uuid.UUID, **payload: Any) -> None:
            ticks.append(payload)

    class FakeEngine:
        def connect(self) -> Any:
            return nullcontext(None)

    monkeypatch.setattr(option_search, "tick_hub", FakeHub())
    monkeypatch.setattr(
        option_search, "child_walks", lambda conn, **_: {done: "succeeded", running: "running"}
    )
    monkeypatch.setattr(option_search, "child_acquired_total", lambda conn, **_: 1234)
    parent = uuid.uuid4()
    # Options scoping passes no stage: its call is unchanged.
    options = stage == option_search.OPTION_SEARCHES_STAGE
    kwargs: dict[str, Any] = {} if options else {"stage": stage}
    option_search._publish_progress(
        cast(Any, FakeEngine()),
        task_id=uuid.uuid4(),
        parent_id=parent,
        child_ids=[done, running],
        **kwargs,
    )
    [tick] = ticks
    assert tick == {
        "stage": stage,
        "activity": line,
        "done": 1,
        "total": 2,
        "unit": "searches",
        "run_id": parent,
    }
