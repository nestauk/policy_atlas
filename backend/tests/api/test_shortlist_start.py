"""Opening a shortlist walk (task 055, P8).

The opener takes the longlist walk's admission: its intent record has
``purpose = 'shortlist'``, the current approved ``plan_id`` and, for Suggest
more, the context ``{"suggest": true}``. It refuses ``run_active``,
``no_longlist``, ``plan_stale`` (a longlist input changed since the build; an
appetite-only change is not stale) and, for Suggest more only,
``nothing_to_propose``.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api import longlist_start
from policy_atlas.api.routers import runs as runs_router
from policy_atlas.core.schema import evidence_scope, longlist_result, option, runs, task_plan
from policy_atlas.runtime.scoping_plan import ScopingPlan
from tests.api.test_longlist_start import RecordingExecutor, _scope_of
from tests.helpers import now, seed_walk
from tests.runtime.test_baseline_gate import (
    insert_scoping_plan_row,
    scoping_plan,
    seed_scoping_task,
)
from tests.runtime.test_runner import _cleanup, _runner_backends


def _seed(engine: Engine, *, plan: ScopingPlan | None = None) -> tuple[uuid.UUID, uuid.UUID]:
    """A scoping task with an approved plan (version 1), no longlist yet."""
    task_id, scope_id = seed_scoping_task(engine)
    plan_id = insert_scoping_plan_row(
        engine, task_id=task_id, scope_id=scope_id, plan=plan or scoping_plan()
    )
    return task_id, plan_id


def _longlist(engine: Engine, task_id: uuid.UUID, plan_id: uuid.UUID, version: int = 1) -> None:
    """A finished longlist walk's result, built from one plan version.

    It holds a proposal made under the default appetite, so Suggest more on it
    keeps the places (a stale proposal re-proposes instead).
    """
    run_id = uuid.uuid4()
    with engine.begin() as conn:
        scope_id = uuid.uuid4()
        conn.execute(
            evidence_scope.insert().values(
                evidence_scope_id=scope_id,
                task_id=task_id,
                intent="longlist",
                context={},
                created_at=now(),
                purpose="longlist",
                plan_id=plan_id,
            )
        )
        walk_id = seed_walk(
            conn, task_id, scope_id=scope_id, plan_id=plan_id, status="succeeded"
        ).walk_id
        conn.execute(
            runs.insert().values(
                run_id=run_id,
                task_id=task_id,
                status="succeeded",
                started_at=now(),
                capability_run_id=walk_id,
            )
        )
        conn.execute(
            longlist_result.insert().values(
                longlist_result_id=uuid.uuid4(),
                task_id=task_id,
                evidence_scope_id=scope_id,
                run_id=run_id,
                plan_version=version,
                themes=[],
                coverage={},
                judgements={},
                guesses=[],
                option_profile={},
                counts={},
                provenance={},
                shortlist={"note": "A note.", "provenance": {"appetite": "mostly_tried"}},
                created_at=now(),
            )
        )


def _option(engine: Engine, task_id: uuid.UUID, **values: Any) -> uuid.UUID:
    option_id = uuid.uuid4()
    row: dict[str, Any] = {
        "option_id": option_id,
        "task_id": task_id,
        "name": f"Option {option_id.hex[:6]}",
        "description": "An option.",
        "design": {"name": "x", "description": "x", "design_features": []},
        "outcomes": [],
        "origin": "suggested",
        "state": "included",
        "secondary_lever_types": [],
        "created_at": now(),
        "updated_at": now(),
    }
    row.update(values)
    with engine.begin() as conn:
        conn.execute(option.insert().values(**row))
    return option_id


def _new_version(engine: Engine, task_id: uuid.UUID, plan: ScopingPlan) -> None:
    with engine.begin() as conn:
        conn.execute(
            task_plan.insert().values(
                plan_id=uuid.uuid4(),
                task_id=task_id,
                version=2,
                status="approved",
                payload=plan.model_dump(mode="json"),
                created_at=now(),
                created_by="task_agent",
                approved_at=now(),
            )
        )


def _open(engine: Engine, task_id: uuid.UUID, *, suggest: bool) -> tuple[uuid.UUID, Any]:
    executor = RecordingExecutor()
    walk_id = longlist_start.open_shortlist_walk(
        engine,
        task_id=task_id,
        backends=_runner_backends(),
        executor=executor,  # type: ignore[arg-type]
        user_id="dev-user",
        suggest=suggest,
    )
    return walk_id, executor


def _refused(engine: Engine, task_id: uuid.UUID, *, suggest: bool) -> str:
    with pytest.raises(longlist_start.LonglistRefused) as caught:
        _open(engine, task_id, suggest=suggest)
    assert runs_router._dispatching_tasks.isdisjoint({task_id})
    return caught.value.reason


@pytest.mark.parametrize("suggest", [True, False])
def test_the_opener_mints_a_shortlist_intent_record(engine: Engine, suggest: bool) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, plan_id = _seed(engine)
        _longlist(engine, task_id, plan_id)
        _option(engine, task_id)
        walk_id, executor = _open(engine, task_id, suggest=suggest)
        record = _scope_of(engine, walk_id)
        assert record["purpose"] == "shortlist"
        assert record["plan_id"] == plan_id
        assert record["context"].get("suggest") is (True if suggest else None)
        assert [call["evidence_scope_id"] for call in executor.submitted] == [
            record["evidence_scope_id"]
        ]
        assert runs_router._dispatching_tasks.isdisjoint({task_id})
        # A second open while the walk runs is refused.
        assert _refused(engine, task_id, suggest=suggest) == "run_active"
    finally:
        _cleanup(engine, task_id)


def test_no_longlist_is_refused(engine: Engine) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, _ = _seed(engine)
        assert _refused(engine, task_id, suggest=False) == "no_longlist"
        with engine.connect() as conn:
            minted = conn.execute(
                select(evidence_scope.c.evidence_scope_id)
                .where(evidence_scope.c.task_id == task_id)
                .where(evidence_scope.c.purpose == "shortlist")
            ).all()
        assert minted == []
    finally:
        _cleanup(engine, task_id)


def test_a_longlist_input_change_is_plan_stale_an_appetite_change_is_not(
    engine: Engine,
) -> None:
    task_id: uuid.UUID | None = None
    other_id: uuid.UUID | None = None
    try:
        task_id, plan_id = _seed(engine)
        _longlist(engine, task_id, plan_id)
        _option(engine, task_id)
        changed = scoping_plan(outcomes=[{"text": "earnings at 25", "origin": "assumed"}])
        _new_version(engine, task_id, changed)
        assert _refused(engine, task_id, suggest=False) == "plan_stale"

        other_id, other_plan = _seed(engine)
        _longlist(engine, other_id, other_plan)
        _option(engine, other_id)
        _new_version(
            engine, other_id, scoping_plan().model_copy(update={"risk_appetite": "tried_only"})
        )
        walk_id, _ = _open(engine, other_id, suggest=False)
        assert _scope_of(engine, walk_id)["purpose"] == "shortlist"
    finally:
        _cleanup(engine, task_id)
        _cleanup(engine, other_id)


def test_nothing_to_propose_is_refused_for_suggest_more_only(engine: Engine) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, plan_id = _seed(engine)
        _longlist(engine, task_id, plan_id)
        _option(engine, task_id, shortlist_state="proposed", shortlist_reason="r")
        _option(engine, task_id, shortlist_state="added_by_you")
        _option(engine, task_id, shortlist_state="set_aside")
        _option(engine, task_id, state="excluded")  # not a candidate either
        assert _refused(engine, task_id, suggest=True) == "nothing_to_propose"
        walk_id, _ = _open(engine, task_id, suggest=False)
        assert _scope_of(engine, walk_id)["context"].get("suggest") is None
    finally:
        _cleanup(engine, task_id)

