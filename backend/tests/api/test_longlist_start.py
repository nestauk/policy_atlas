"""Opening the longlist walk from its three start surfaces (task 045, S3).

The contract's "start (D1, A2, A23)" checks: the gate's ``confirm_plan`` records
the decision, ends the baseline walk and opens a longlist walk whose intent
record has ``purpose = longlist``, the confirmed ``plan_id`` and the PICO text;
the confirm-baseline route does the same on its new version and returns the
walk in an optional field; both hold the dispatch lock and the reservation, so
a race with ``POST /runs`` yields one walk; a second confirm while the walk
runs is ``run_active`` and a second decision is ``already_answered``;
unattended records and flags the standing default and opens the second walk;
an Evidence search task has no opener path.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import Future
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api import longlist_start
from policy_atlas.api.continuation import answer_check_in
from policy_atlas.api.deps import get_executor, get_runner_backends
from policy_atlas.api.routers import runs as runs_router
from policy_atlas.core import events
from policy_atlas.core.schema import (
    artefact,
    capability_run,
    conversation,
    evidence_scope,
    task_plan,
)
from policy_atlas.options_scoping.longlist_intent import compile_longlist_intent
from policy_atlas.runtime.capability_registry import OPTIONS_SCOPING, validate_plan
from policy_atlas.runtime.conversation_lifecycle import ensure_active_task_agent_conversation
from policy_atlas.runtime.scoping_plan import ScopingPlan
from tests.api.resource_support import api_client, create_task
from tests.api.test_baseline_gate_checkin import _option, _own, _park_at_gate
from tests.helpers import now
from tests.runtime.test_baseline_gate import (
    insert_scoping_plan_row,
    scoping_plan,
    seed_scoping_task,
)
from tests.runtime.test_runner import _cleanup, _runner_backends


class RecordingExecutor:
    """A walk executor that opens each submitted walk's row and runs nothing.

    The row is what the admission and ``_await_new_run`` read, so the start
    surfaces behave exactly as with a real worker up to the walk itself.

    Args:
        status: The status each opened row is written with.
    """

    _max_workers = 2

    def __init__(self, status: str = "running") -> None:
        self.status = status
        self.submitted: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future[None]:
        """Record the dispatch and write its walk row."""
        engine: Engine = args[0]
        plan_row = kwargs["plan_row"]
        run_id = kwargs.get("capability_run_id") or uuid.uuid4()
        with self._lock:
            self.submitted.append({"capability_run_id": run_id, **kwargs})
        with engine.begin() as conn:
            conn.execute(
                capability_run.insert().values(
                    capability_run_id=run_id,
                    task_id=kwargs["task_id"],
                    evidence_scope_id=kwargs.get("evidence_scope_id")
                    or plan_row["evidence_scope_id"],
                    capability=kwargs["capability"],
                    plan_id=plan_row["plan_id"],
                    plan_version=plan_row["version"],
                    status=self.status,
                    started_at=now(),
                )
            )
        future: Future[None] = Future()
        future.set_result(None)
        return future


def _overrides(executor: RecordingExecutor) -> dict[Callable[..., object], Callable[..., object]]:
    return {get_executor: lambda: executor, get_runner_backends: _runner_backends}


def _scope_of(engine: Engine, capability_run_id: uuid.UUID) -> Any:
    with engine.connect() as conn:
        return conn.execute(
            select(evidence_scope)
            .select_from(
                evidence_scope.join(
                    capability_run,
                    capability_run.c.evidence_scope_id == evidence_scope.c.evidence_scope_id,
                )
            )
            .where(capability_run.c.capability_run_id == capability_run_id)
        ).mappings().one()


def _approved(engine: Engine, task_id: uuid.UUID) -> Any:
    with engine.connect() as conn:
        return conn.execute(
            select(task_plan)
            .where(task_plan.c.task_id == task_id)
            .where(task_plan.c.status == "approved")
            .order_by(task_plan.c.version.desc())
            .limit(1)
        ).mappings().one()


def _seed_confirmable(engine: Engine, owner: dict[str, str]) -> tuple[uuid.UUID, uuid.UUID]:
    """A scoping task with an approved plan and a baseline, owned by ``owner``.

    Returns:
        ``(task_id, artefact_id)``.
    """
    task_id, scope_id = seed_scoping_task(engine)
    insert_scoping_plan_row(engine, task_id=task_id, scope_id=scope_id, plan=scoping_plan())
    _own(engine, task_id, owner)
    artefact_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            artefact.insert().values(
                artefact_id=artefact_id,
                task_id=task_id,
                capability_run_id=None,
                title="Baseline",
                created_at=now(),
            )
        )
    return task_id, artefact_id


def _confirm(
    client: TestClient,
    owner: dict[str, str],
    task_id: uuid.UUID,
    artefact_id: uuid.UUID,
    version: int = 1,
) -> Any:
    return client.post(
        f"/api/v1/tasks/{task_id}/plan/confirm-baseline",
        headers=owner,
        json={"artefact_id": str(artefact_id), "plan_version": version},
    )


def _walks(engine: Engine, task_id: uuid.UUID) -> list[Any]:
    with engine.connect() as conn:
        return list(
            conn.execute(
                select(capability_run.c.capability_run_id, capability_run.c.status)
                .where(capability_run.c.task_id == task_id)
                .order_by(capability_run.c.started_at)
            )
        )


# --- the confirm-baseline route ---------------------------------------------


def test_confirm_baseline_opens_the_longlist_walk_on_the_new_version(
    engine: Engine, tmp_path: Path
) -> None:
    """The record: ``purpose = longlist``, the confirmed ``plan_id``, the PICO text."""
    task_id: uuid.UUID | None = None
    executor = RecordingExecutor()
    try:
        with api_client(tmp_path, _overrides(executor)) as (client, owner, _other):
            task_id, artefact_id = _seed_confirmable(engine, owner)
            response = _confirm(client, owner, task_id, artefact_id)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["version"] == 2
        opened = body["opened_run"]
        assert opened is not None
        assert opened["status"] == "running"
        run_id = uuid.UUID(opened["capability_run_id"])
        confirmed = _approved(engine, task_id)
        record = _scope_of(engine, run_id)
        assert record["purpose"] == "longlist"
        assert record["plan_id"] == confirmed["plan_id"]
        plan = validate_plan(OPTIONS_SCOPING, confirmed["payload"])
        assert isinstance(plan, ScopingPlan)
        assert record["intent"] == compile_longlist_intent(plan)
        assert [call["evidence_scope_id"] for call in executor.submitted] == [
            record["evidence_scope_id"]
        ]
        assert runs_router._dispatching_tasks.isdisjoint({task_id})
    finally:
        _cleanup(engine, task_id)


def test_a_second_confirm_while_the_longlist_walk_runs_is_run_active(
    engine: Engine, tmp_path: Path
) -> None:
    task_id: uuid.UUID | None = None
    try:
        with api_client(tmp_path, _overrides(RecordingExecutor())) as (client, owner, _other):
            task_id, artefact_id = _seed_confirmable(engine, owner)
            first = _confirm(client, owner, task_id, artefact_id)
            second = _confirm(client, owner, task_id, artefact_id, version=2)
        assert first.status_code == 200, first.text
        assert second.status_code == 409, second.text
        assert second.json()["error"]["code"] == "run_active"
    finally:
        _cleanup(engine, task_id)


def test_the_idempotent_confirm_reopens_a_missing_walk(engine: Engine, tmp_path: Path) -> None:
    """A version confirmed without a longlist walk opens one; with one, it is unchanged."""
    task_id: uuid.UUID | None = None
    executor = RecordingExecutor(status="succeeded")
    try:
        with api_client(tmp_path, _overrides(executor)) as (client, owner, _other):
            task_id, artefact_id = _seed_confirmable(engine, owner)
            first = _confirm(client, owner, task_id, artefact_id)
            assert first.status_code == 200, first.text
            # Lose the walk: the version stays confirmed, the walk never existed.
            with engine.begin() as conn:
                conn.execute(
                    capability_run.delete().where(capability_run.c.task_id == task_id)
                )
            reopened = _confirm(client, owner, task_id, artefact_id, version=2)
            again = _confirm(client, owner, task_id, artefact_id, version=2)
        assert reopened.status_code == 200, reopened.text
        assert reopened.json()["version"] == 2
        assert reopened.json()["opened_run"] is not None
        assert again.status_code == 200, again.text
        assert again.json()["opened_run"] is None
        assert len(executor.submitted) == 2
        with engine.connect() as conn:
            versions = conn.execute(
                select(task_plan.c.version).where(task_plan.c.task_id == task_id)
            ).scalars().all()
        assert sorted(versions) == [1, 2]
    finally:
        _cleanup(engine, task_id)


def test_a_confirm_on_a_newer_version_opens_a_rebuild(engine: Engine, tmp_path: Path) -> None:
    """D14: a confirm on a version newer than the last longlist's opens another walk."""
    task_id: uuid.UUID | None = None
    executor = RecordingExecutor(status="succeeded")
    try:
        with api_client(tmp_path, _overrides(executor)) as (client, owner, _other):
            task_id, artefact_id = _seed_confirmable(engine, owner)
            assert _confirm(client, owner, task_id, artefact_id).status_code == 200
            edited = client.patch(
                f"/api/v1/tasks/{task_id}/plan",
                headers=owner,
                json={"scoping": {"depth": "rapid"}},
            )
            assert edited.status_code == 200, edited.text
            rebuilt = _confirm(client, owner, task_id, artefact_id, version=3)
        assert rebuilt.status_code == 200, rebuilt.text
        assert rebuilt.json()["version"] == 4
        assert len(executor.submitted) == 2
        latest = _approved(engine, task_id)
        record = _scope_of(engine, uuid.UUID(rebuilt.json()["opened_run"]["capability_run_id"]))
        assert record["plan_id"] == latest["plan_id"]
    finally:
        _cleanup(engine, task_id)


def test_an_evidence_search_task_has_no_opener_path(engine: Engine, tmp_path: Path) -> None:
    task_id: uuid.UUID | None = None
    try:
        with api_client(tmp_path, _overrides(RecordingExecutor())) as (client, owner, _other):
            task_id = uuid.UUID(create_task(client, owner))
            refused = _confirm(client, owner, task_id, uuid.uuid4())
        assert refused.status_code == 422, refused.text
        with pytest.raises(longlist_start.LonglistRefused) as caught:
            longlist_start.admit_and_mint(engine, task_id=task_id, capacity=99)
        assert caught.value.reason == "not_scoping"
        error = longlist_start.http_error(caught.value)
        assert getattr(error, "status_code", None) == 422
    finally:
        _cleanup(engine, task_id)


def test_a_plan_too_long_to_screen_is_refused_before_anything_is_minted(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    task_id: uuid.UUID | None = None

    def too_long(plan: ScopingPlan) -> str:
        raise ValueError("composed screen intent exceeds 2000 characters")

    try:
        task_id, scope_id = seed_scoping_task(engine)
        insert_scoping_plan_row(engine, task_id=task_id, scope_id=scope_id, plan=scoping_plan())
        monkeypatch.setattr(longlist_start, "compose_longlist_screen_intent", too_long)
        with pytest.raises(longlist_start.LonglistRefused) as caught:
            longlist_start.admit_and_mint(engine, task_id=task_id, capacity=99)
        assert caught.value.reason == "plan_too_long"
        with engine.connect() as conn:
            purposes = conn.execute(
                select(evidence_scope.c.purpose).where(evidence_scope.c.task_id == task_id)
            ).scalars().all()
        assert "longlist" not in purposes
        assert task_id not in runs_router._dispatching_tasks
    finally:
        _cleanup(engine, task_id)


def test_the_capacity_rule_counts_parentless_walks_only(engine: Engine) -> None:
    """Children never count against the executor: they run on their own pool."""
    task_id: uuid.UUID | None = None
    other_id: uuid.UUID | None = None
    try:
        task_id, scope_id = seed_scoping_task(engine)
        plan_id = insert_scoping_plan_row(
            engine, task_id=task_id, scope_id=scope_id, plan=scoping_plan()
        )
        other_id, other_scope = seed_scoping_task(engine)
        other_plan = insert_scoping_plan_row(
            engine, task_id=other_id, scope_id=other_scope, plan=scoping_plan()
        )
        with engine.connect() as conn:
            running = len(
                conn.execute(
                    select(capability_run.c.capability_run_id)
                    .where(capability_run.c.status == "running")
                    .where(capability_run.c.parent_capability_run_id.is_(None))
                ).all()
            )
        capacity = running + len(runs_router._dispatching_tasks) + 1
        parent = uuid.uuid4()
        with engine.begin() as conn:
            conn.execute(
                capability_run.insert().values(
                    capability_run_id=parent,
                    task_id=other_id,
                    evidence_scope_id=other_scope,
                    capability=OPTIONS_SCOPING,
                    plan_id=other_plan,
                    plan_version=1,
                    status="succeeded",
                    started_at=now(),
                )
            )
            for _ in range(4):
                conn.execute(
                    capability_run.insert().values(
                        capability_run_id=uuid.uuid4(),
                        task_id=other_id,
                        evidence_scope_id=other_scope,
                        capability=OPTIONS_SCOPING,
                        plan_id=other_plan,
                        plan_version=1,
                        status="running",
                        started_at=now(),
                        parent_capability_run_id=parent,
                    )
                )
        admitted = longlist_start.admit_and_mint(engine, task_id=task_id, capacity=capacity)
        with runs_router._dispatch_lock:
            runs_router._dispatching_tasks.discard(task_id)
        assert admitted.plan_row["plan_id"] == plan_id

        with engine.begin() as conn:
            conn.execute(
                capability_run.insert().values(
                    capability_run_id=uuid.uuid4(),
                    task_id=other_id,
                    evidence_scope_id=other_scope,
                    capability=OPTIONS_SCOPING,
                    plan_id=other_plan,
                    plan_version=1,
                    status="running",
                    started_at=now(),
                )
            )
        with pytest.raises(longlist_start.LonglistRefused) as caught:
            longlist_start.admit_and_mint(engine, task_id=task_id, capacity=capacity)
        assert caught.value.reason == "capacity"
    finally:
        _cleanup(engine, other_id)
        _cleanup(engine, task_id)


# --- the gate: the card and the race ----------------------------------------


def test_the_confirm_branch_ends_the_walk_and_closes_the_conversation(engine: Engine) -> None:
    """P3: the 029 invariant ``_finish_run`` keeps, kept by the path that bypasses it."""
    task_id: uuid.UUID | None = None
    try:
        task_id, walk_id, check_in_id, _plan_id = _park_at_gate(engine)
        with engine.begin() as conn:
            conversation_id = ensure_active_task_agent_conversation(
                conn, task_id=task_id, now=now()
            )
        answer = answer_check_in(
            engine,
            task_id=task_id,
            check_in_id=check_in_id,
            response=_option("confirm_plan"),
            actor="user-1",
        )
        assert answer.continuation_requested is False
        assert answer.follow_on == "longlist"
        with engine.connect() as conn:
            walk = conn.execute(
                select(capability_run.c.status, capability_run.c.ended_at).where(
                    capability_run.c.capability_run_id == walk_id
                )
            ).one()
            thread = conn.execute(
                select(conversation.c.status).where(conversation.c.id == conversation_id)
            ).scalar_one()
            log = events.read(conn, task_id)
        assert walk.status == "succeeded"
        assert walk.ended_at is not None
        assert thread == "closed"
        finished = [e["payload"] for e in log if e["event_type"] == "run.finished"]
        assert finished[-1] == {
            "capability_run_id": str(walk_id),
            "status": "succeeded",
            "reason": "confirm_plan",
        }
        decision = next(
            e["payload"]
            for e in reversed(log)
            if e["event_type"] == "steering.decision"
            and e["payload"].get("component") == "synthesise"
        )
        assert decision["response"] == "continue"
        assert decision["action"] == "confirm_plan"
        assert decision["plan_version"] == 1
        uuid.UUID(decision["artefact_id"])
        assert not any(e["event_type"] == "continuation.requested" for e in log)
    finally:
        _cleanup(engine, task_id)


def test_the_card_opens_the_walk_without_waiting_and_stays_204(
    engine: Engine, tmp_path: Path
) -> None:
    """An executor that never opens the row cannot hold the card's response."""
    task_id: uuid.UUID | None = None

    class _NeverStarts(RecordingExecutor):
        def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future[None]:
            self.submitted.append(kwargs)
            return Future()

    executor = _NeverStarts()
    try:
        with api_client(tmp_path, _overrides(executor)) as (client, owner, _other):
            task_id, walk_id, check_in_id, plan_id = _park_at_gate(engine)
            _own(engine, task_id, owner)
            response = client.post(
                f"/api/v1/tasks/{task_id}/check-ins/{check_in_id}/response",
                headers=owner,
                json={"kind": "option", "option_id": "confirm_plan"},
            )
            second = client.post(
                f"/api/v1/tasks/{task_id}/check-ins/{check_in_id}/response",
                headers=owner,
                json={"kind": "option", "option_id": "confirm_plan"},
            )
        assert response.status_code == 204, response.text
        assert second.status_code == 409, second.text
        assert second.json()["error"]["code"] == "already_answered"
        assert len(executor.submitted) == 1
        call = executor.submitted[0]
        record = _approved(engine, task_id)
        assert call["plan_row"]["plan_id"] == record["plan_id"] == plan_id
        with engine.connect() as conn:
            scope = conn.execute(
                select(evidence_scope).where(
                    evidence_scope.c.evidence_scope_id == call["evidence_scope_id"]
                )
            ).mappings().one()
        assert scope["purpose"] == "longlist"
        assert scope["plan_id"] == plan_id
        assert _walks(engine, task_id) == [(walk_id, "succeeded")]
    finally:
        with runs_router._dispatch_lock:
            if task_id is not None:
                runs_router._dispatching_tasks.discard(task_id)
        _cleanup(engine, task_id)


def test_the_gate_the_route_and_post_runs_racing_yield_one_walk(
    engine: Engine, tmp_path: Path
) -> None:
    """A23: the pre-insert window is held by the reservation on every start path."""
    task_id: uuid.UUID | None = None
    executor = RecordingExecutor()
    try:
        with api_client(tmp_path, _overrides(executor)) as (client, owner, _other):
            task_id, walk_id, check_in_id, _plan_id = _park_at_gate(engine)
            _own(engine, task_id, owner)
            with engine.begin() as conn:
                artefact_id = conn.execute(
                    select(artefact.c.artefact_id).where(artefact.c.task_id == task_id)
                ).scalars().one()
            start = threading.Barrier(3)
            results: dict[str, Any] = {}

            def card() -> None:
                start.wait(timeout=10)
                results["card"] = client.post(
                    f"/api/v1/tasks/{task_id}/check-ins/{check_in_id}/response",
                    headers=owner,
                    json={"kind": "option", "option_id": "confirm_plan"},
                )

            def route() -> None:
                start.wait(timeout=10)
                for _ in range(20):
                    results["route"] = _confirm(client, owner, task_id, artefact_id)
                    if results["route"].status_code != 409:
                        break

            def post_runs() -> None:
                start.wait(timeout=10)
                for _ in range(20):
                    results["runs"] = client.post(
                        f"/api/v1/tasks/{task_id}/runs", headers=owner, json={}
                    )
                    if results["runs"].status_code != 409:
                        break

            threads = [threading.Thread(target=fn) for fn in (card, route, post_runs)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=60)

        assert results["card"].status_code == 204, results["card"].text
        new_walks = [row for row in _walks(engine, task_id) if row.capability_run_id != walk_id]
        assert len(new_walks) == 1
        assert len(executor.submitted) == 1
    finally:
        with runs_router._dispatch_lock:
            if task_id is not None:
                runs_router._dispatching_tasks.discard(task_id)
        _cleanup(engine, task_id)


# --- unattended -------------------------------------------------------------


def test_unattended_records_the_standing_default_and_opens_the_second_walk(
    engine: Engine,
) -> None:
    """A2: the gate records and flags the standing default; the worker that ran the
    baseline opens the longlist walk inline once the baseline has ended."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = seed_scoping_task(engine)
        plan = scoping_plan(
            steering_mode="unattended",
            steer_point_defaults=[{"steer_point": "baseline_confirm", "action": "proceed_flag"}],
        )
        insert_scoping_plan_row(engine, task_id=task_id, scope_id=scope_id, plan=plan)
        plan_row = dict(_approved(engine, task_id))
        runs_router._dispatch_run(
            engine,
            task_id=task_id,
            capability=OPTIONS_SCOPING,
            plan_row=plan_row,
            backends=_runner_backends(),
            user_id="user-1",
        )
        with engine.connect() as conn:
            walks = list(
                conn.execute(
                    select(
                        capability_run.c.capability_run_id,
                        capability_run.c.status,
                        capability_run.c.parent_capability_run_id,
                        evidence_scope.c.purpose,
                        evidence_scope.c.plan_id,
                    )
                    .select_from(
                        capability_run.join(
                            evidence_scope,
                            evidence_scope.c.evidence_scope_id
                            == capability_run.c.evidence_scope_id,
                        )
                    )
                    .where(capability_run.c.task_id == task_id)
                    .where(capability_run.c.parent_capability_run_id.is_(None))
                    .order_by(capability_run.c.started_at)
                )
            )
            log = events.read(conn, task_id)
        assert [walk.purpose for walk in walks] == [None, "longlist"]
        baseline, longlist = walks
        assert baseline.status in {"succeeded", "degraded"}
        assert longlist.plan_id == plan_row["plan_id"]
        assert longlist.status in {"succeeded", "degraded", "failed"}
        standing = [
            e["payload"]
            for e in log
            if e["event_type"] == "steering.decision"
            and e["payload"].get("component") == "synthesise"
        ]
        assert len(standing) == 1
        assert standing[0]["decided_by"] == "standing_default"
        assert standing[0]["standing_rule"] == {
            "steer_point": "baseline_confirm",
            "action": "proceed_flag",
        }
        # The baseline ended before the longlist walk opened.
        sequence = {
            e["payload"].get("capability_run_id"): e["sequence"]
            for e in log
            if e["event_type"] in {"run.finished", "run.opened"}
        }
        finished_at = next(
            e["sequence"]
            for e in log
            if e["event_type"] == "run.finished"
            and e["payload"].get("capability_run_id") == str(baseline.capability_run_id)
        )
        assert finished_at < sequence[str(longlist.capability_run_id)]
        assert task_id not in runs_router._dispatching_tasks
    finally:
        _cleanup(engine, task_id)


@pytest.mark.parametrize(
    ("mode", "defaults", "follow_on"),
    [
        ("unattended", [{"steer_point": "baseline_confirm", "action": "proceed_flag"}], "longlist"),
        # No declared default and an IO that cannot ask anybody: nobody
        # confirmed the plan, so nothing opens.
        ("moderate", [], None),
    ],
)
def test_the_follow_on_is_asked_for_only_by_a_standing_default(
    engine: Engine, mode: str, defaults: list[dict[str, str]], follow_on: str | None
) -> None:
    from policy_atlas.runtime.runner import NullIO, run_plan

    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = seed_scoping_task(engine)
        plan = scoping_plan(steering_mode=mode, steer_point_defaults=defaults)
        plan_id = insert_scoping_plan_row(engine, task_id=task_id, scope_id=scope_id, plan=plan)
        outcome = run_plan(
            engine,
            task_id=task_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            backends=_runner_backends(),
            io=NullIO(),
        )
        assert outcome.follow_on == follow_on
        assert any(
            flag.get("steer_point") == "baseline_confirm" and flag["status"] == "auto_resolved"
            for flag in outcome.flagged_events
        )
    finally:
        _cleanup(engine, task_id)


def test_a_task_row_is_required(engine: Engine) -> None:
    with pytest.raises(LookupError):
        longlist_start.admit_and_mint(engine, task_id=uuid.uuid4(), capacity=99)



# --- the longlist walk does not pause (D1) ------------------------------------


def test_a_longlist_walk_never_parks_even_under_frequent(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D1: the longlist walk runs unattended whatever the plan's mode; its
    boundaries are recorded as standing proceeds, never put to the user."""
    from policy_atlas.runtime import runner as runner_module

    original_attempt = runner_module._run_step_attempt

    def phase_five_stands_in(engine_: Engine, **kwargs: Any) -> Any:
        # The Phase 5 steps succeed here, so the walk's end is about pausing.
        if kwargs["step"].component in {"longlist", "constrain"}:
            return runner_module._AttemptOutcome(
                run_id=uuid.uuid4(),
                status="succeeded",
                wall_clock_s=0.0,
                headline_counts={},
                error=None,
            )
        return original_attempt(engine_, **kwargs)

    monkeypatch.setattr(runner_module, "_run_step_attempt", phase_five_stands_in)
    original_finish = runner_module._finish_run
    finished: dict[uuid.UUID, list[dict[str, Any]]] = {}

    def recording_finish(engine_: Engine, outcomes: Any, flagged: Any, **kwargs: Any) -> Any:
        finished[kwargs["capability_run_id"]] = list(flagged)
        return original_finish(engine_, outcomes, flagged, **kwargs)

    monkeypatch.setattr(runner_module, "_finish_run", recording_finish)
    task_id: uuid.UUID | None = None
    try:
        with api_client(tmp_path, {get_runner_backends: _runner_backends}) as (
            client,
            owner,
            _other,
        ):
            task_id, scope_id = seed_scoping_task(engine)
            plan = scoping_plan(steering_mode="frequent")
            insert_scoping_plan_row(engine, task_id=task_id, scope_id=scope_id, plan=plan)
            _own(engine, task_id, owner)
            artefact_id = uuid.uuid4()
            with engine.begin() as conn:
                conn.execute(
                    artefact.insert().values(
                        artefact_id=artefact_id,
                        task_id=task_id,
                        capability_run_id=None,
                        title="Baseline",
                        created_at=now(),
                    )
                )
            response = _confirm(client, owner, task_id, artefact_id)
            assert response.status_code == 200, response.text
            run_id = uuid.UUID(response.json()["opened_run"]["capability_run_id"])
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                with engine.connect() as conn:
                    active = conn.execute(
                        select(capability_run.c.capability_run_id)
                        .where(capability_run.c.task_id == task_id)
                        .where(capability_run.c.status == "running")
                    ).first()
                if active is None:
                    break
                time.sleep(0.05)
        with engine.connect() as conn:
            walks = {
                row.capability_run_id: row.status
                for row in conn.execute(
                    select(capability_run.c.capability_run_id, capability_run.c.status).where(
                        capability_run.c.task_id == task_id
                    )
                )
            }
            log = events.read(conn, task_id)
        assert walks[run_id] in {"succeeded", "degraded"}
        assert "paused" not in walks.values()
        assert not any(e["event_type"] == "steering.pause" for e in log)
        assert not any(
            e["event_type"] == "steering.decision" and e["payload"].get("decided_by") == "user"
            for e in log
        )
        # A boundary whose floor trigger fired (the classification mix
        # collapse on the two-document stub corpus) is recorded the unattended
        # way — a collation flag the review sees — instead of a check-in.
        fired = [flag for flag in finished[run_id] if flag.get("status") == "triggers_fired"]
        assert fired, finished[run_id]
        assert {flag["component"] for flag in fired} >= {"classify"}
        # The plan row keeps the user's mode.
        assert _approved(engine, task_id)["payload"]["steering_mode"] == "frequent"
    finally:
        _cleanup(engine, task_id)
