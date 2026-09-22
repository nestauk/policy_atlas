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
from policy_atlas.core.schema import capability_run, conversation, evidence_scope, option
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
from tests.helpers import now
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
    scope_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            evidence_scope.insert().values(
                evidence_scope_id=scope_id,
                task_id=task_id,
                intent="longlist intent",
                context={"capability": "options_scoping"},
                created_at=now(),
                purpose="longlist",
                plan_id=plan_id,
            )
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
    walk_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            capability_run.insert().values(
                capability_run_id=walk_id,
                task_id=task_id,
                evidence_scope_id=scope_id,
                capability="options_scoping",
                plan_id=plan_id,
                plan_version=1,
                status=status,
                started_at=now(),
                parent_capability_run_id=parent,
            )
        )
    return walk_id


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


# --- the walk end to end on the stub backends -------------------------------


def test_a_stub_longlist_walk_fans_out_after_suggest_and_joins_before_longlist(
    engine: Engine,
) -> None:
    """inherit → suggest → [fan-out] → acquire … extract_interventions → [join] → longlist.

    Every entrant (the user's two, the stub's one suggestion) gets one child
    walk under its own targeted record naming the option, with the design's
    ``as_intent()`` as its intent and the confirmed plan version; both
    barriers emit under ``option_searches`` and the stream maps them to stage
    frames with the join's counts.
    """
    task_id: uuid.UUID | None = None
    try:
        plan = _longlist_plan("Youth guarantee", "Wage subsidy")
        task_id, scope_id, plan_id = _seed_longlist(engine, plan)
        outcome = _run_longlist(engine, task_id, scope_id, plan_id, plan)
        parent = outcome.capability_run_id
        assert parent is not None
        steps = [step.component for step in outcome.steps]
        assert steps[:8] == [
            "inherit",
            "suggest",
            "acquire",
            "screen_abstract",
            "classify",
            "appraise",
            "ingest_full_text",
            "extract_interventions",
        ]
        assert "longlist" in steps

        children = _children(engine, task_id, parent)
        assert len(children) == 3
        assert all(child.status == "succeeded" for child in children)
        assert all(child.purpose == "targeted" for child in children)
        assert all(child.plan_id == plan_id for child in children)
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
        assert order.index(("component.completed", "extract_interventions")) < join
        assert join < order.index(("run.started", "longlist"))

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
        assert frames[1]["summary"] == {"total": 3, "finished": 3, "failed": 0}
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


def test_a_rebuild_searches_only_entrants_without_a_search(engine: Engine) -> None:
    """P12: an entrant already searched on this task (any walk under a targeted
    record naming it) is not searched again; a new entrant is."""
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
        _seed_walk(engine, task_id, targeted, plan_id, parent=parent, status="failed")
        suggest_run = _seed_suggest_summary(engine, task_id, parent, [old, new])
        with engine.connect() as conn:
            assert option_search.searched_option_ids(conn, task_id=task_id) == {old}
            chosen = option_search.entrants_for_search(
                conn, task_id=task_id, suggest_run_id=suggest_run
            )
        assert [option_id for option_id, _design in chosen] == [new]
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


# --- failure, the timeout and the conversation ------------------------------


def _open_row(engine: Engine, kwargs: dict[str, Any]) -> None:
    """Open a child walk's row as the runner would, from ``run_plan``'s kwargs."""
    with engine.begin() as conn:
        conn.execute(
            capability_run.insert().values(
                capability_run_id=kwargs["capability_run_id"],
                task_id=kwargs["task_id"],
                evidence_scope_id=kwargs["evidence_scope_id"],
                capability="options_scoping",
                plan_id=kwargs["plan_id"],
                plan_version=kwargs["plan_version"],
                status="running",
                started_at=now(),
                parent_capability_run_id=kwargs["parent_capability_run_id"],
            )
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
        if kwargs["step"].component in {"longlist", "constrain"}:
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


def test_option_searches_run_at_width_four(engine: Engine, child_run_plan: Any) -> None:
    """The cross-walk bound: eight searches, never more than four at once."""
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
        for i in range(8):
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
        assert len(children) == 8
        deadline = time.monotonic() + 10
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
    """Each parse job holds one slot while it runs and gives it back."""
    from policy_atlas.evidence_search.sourcing.ingest_full_text import (
        DEFAULT_MAX_WORKERS,
        _run_parse_jobs,
    )
    from tests.evidence_search.sourcing.test_ingest_full_text import _sleep_by_marker_parse

    results = _run_parse_jobs(
        [(0, b"fast", "text/plain"), (1, b"fast", "text/plain")],
        max_workers=2,
        parse_timeout=20.0,
        thin_min=0,
        parse_fn=_sleep_by_marker_parse,
    )
    assert set(results) == {0, 1}
    assert walk_pool.INGEST_SLOTS._value == DEFAULT_MAX_WORKERS
