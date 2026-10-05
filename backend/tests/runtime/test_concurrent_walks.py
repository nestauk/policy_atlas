"""Thread-safety audit test (task 025, C.4 — "the both-complete test").

parking-seam-design.md §7: components were built one-walk-at-a-time; the API
introduces concurrent walks (different tasks). This is the audit's
prescribed test: two concurrent stub walks on two different tasks, driven
from two threads over the same shared engine, must both complete
successfully with fully task-scoped state and no cross-task sequence
collision.

The correctness model this pins (core/events.py ``append`` docstring, ADR
0001 §6): the event-log sequence allocator assumes a **single writer per
task** — concurrent appenders to the *same* task would collide on the
``(task_id, sequence)`` unique constraint (a hard ``IntegrityError``,
never silent misordering). Task 025's concurrency model keeps that
invariant by construction: concurrent walks are always on *different*
tasks, each with exactly one writer (its own thread here). This test
proves that shape actually works end-to-end — both walks succeed, and
nothing about running them concurrently lets one task's state leak into
the other's.

Uses the walk-scripting idioms from tests/runtime/test_runner.py
(``_base_plan``, ``_seed_task``, ``_runner_backends``) — the same stub
backends and seeded fixture corpus every other runner test uses, so this
test is deterministic and egress-free.
"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.core import events
from policy_atlas.core.schema import capability_run, runs
from policy_atlas.runtime.runner import NullIO, RunPlanOutcome, run_plan
from policy_atlas.runtime.task_plan import compose
from tests.runtime.test_runner import (
    _base_plan,
    _cleanup,
    _runner_backends,
    _seed_task,
    _with_search_rounds,
)


def _run_walk(engine: Engine, task_id: uuid.UUID, scope_id: uuid.UUID) -> RunPlanOutcome:
    plan = _base_plan(search_effort="standard", analysis_depth="deep")
    return run_plan(
        engine,
        task_id=task_id,
        evidence_scope_id=scope_id,
        plan=plan,
        plan_id=uuid.uuid4(),
        plan_version=1,
        backends=_runner_backends(),
        io=NullIO(),
        session_id=uuid.uuid4(),
    )


def test_two_concurrent_walks_on_different_tasks_both_complete(engine: Engine) -> None:
    """Two threads each drive a full stub walk on their own task at the same
    time. Both must succeed, and every durable row each walk wrote must be
    scoped to its own task — no cross-task leakage, no sequence collision."""
    task_a: uuid.UUID | None = None
    task_b: uuid.UUID | None = None
    try:
        task_a, scope_a = _seed_task(engine)
        task_b, scope_b = _seed_task(engine)

        with ThreadPoolExecutor(max_workers=2) as pool:
            future_a = pool.submit(_run_walk, engine, task_a, scope_a)
            future_b = pool.submit(_run_walk, engine, task_b, scope_b)
            outcome_a = future_a.result()
            outcome_b = future_b.result()

        # --- both complete -------------------------------------------------
        assert outcome_a.status == "succeeded"
        assert outcome_b.status == "succeeded"
        expected_steps = _with_search_rounds(compose(_base_plan()).components)
        assert [step.component for step in outcome_a.steps] == expected_steps
        assert [step.component for step in outcome_b.steps] == expected_steps
        assert all(step.status == "succeeded" for step in outcome_a.steps)
        assert all(step.status == "succeeded" for step in outcome_b.steps)

        run_ids_a = {step.run_id for step in outcome_a.steps}
        run_ids_b = {step.run_id for step in outcome_b.steps}
        assert run_ids_a.isdisjoint(run_ids_b)

        with engine.connect() as conn:
            # --- runs/capability_run read-back is fully task-scoped -----
            rows_a = conn.execute(
                select(runs.c.run_id, runs.c.task_id).where(runs.c.task_id == task_a)
            ).fetchall()
            rows_b = conn.execute(
                select(runs.c.run_id, runs.c.task_id).where(runs.c.task_id == task_b)
            ).fetchall()
            assert {row.run_id for row in rows_a} == run_ids_a
            assert {row.run_id for row in rows_b} == run_ids_b
            assert all(row.task_id == task_a for row in rows_a)
            assert all(row.task_id == task_b for row in rows_b)

            cap_rows_a = conn.execute(
                select(capability_run.c.status, capability_run.c.task_id).where(
                    capability_run.c.task_id == task_a
                )
            ).fetchall()
            cap_rows_b = conn.execute(
                select(capability_run.c.status, capability_run.c.task_id).where(
                    capability_run.c.task_id == task_b
                )
            ).fetchall()
            assert len(cap_rows_a) == 1
            assert len(cap_rows_b) == 1
            assert cap_rows_a[0].status == "succeeded"
            assert cap_rows_b[0].status == "succeeded"

            # --- event_log is fully task-scoped; no cross-task rows ---
            log_a = events.read(conn, task_a)
            log_b = events.read(conn, task_b)

        assert log_a, "expected event_log rows for task A"
        assert log_b, "expected event_log rows for task B"
        # events.read scopes by task_id at the SQL WHERE, and the composite
        # FK (event_log(run_id, task_id) -> runs(run_id, task_id))
        # enforces this at the DB level; assert the walk's own run ids never
        # appear under the other task's log (belt-and-braces).
        run_ids_in_log_a = {entry["run_id"] for entry in log_a if entry["run_id"] is not None}
        run_ids_in_log_b = {entry["run_id"] for entry in log_b if entry["run_id"] is not None}
        assert run_ids_in_log_a <= run_ids_a
        assert run_ids_in_log_b <= run_ids_b
        assert run_ids_in_log_a.isdisjoint(run_ids_in_log_b)

        # --- no cross-task sequence collision: each task's sequence
        # column is a dense, strictly increasing, non-colliding run of its
        # own (1..N) — the single-writer-per-task invariant held under
        # concurrency because the two writers never touched the same task.
        sequences_a = [entry["sequence"] for entry in log_a]
        sequences_b = [entry["sequence"] for entry in log_b]
        assert sequences_a == sorted(sequences_a)
        assert sequences_b == sorted(sequences_b)
        assert len(sequences_a) == len(set(sequences_a))
        assert len(sequences_b) == len(set(sequences_b))
        assert sequences_a == list(range(1, len(sequences_a) + 1))
        assert sequences_b == list(range(1, len(sequences_b) + 1))
    finally:
        _cleanup(engine, task_a)
        _cleanup(engine, task_b)
