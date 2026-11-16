"""HTTP coverage for run-dispatch preconditions and ownership opacity."""

from __future__ import annotations

import time
import uuid
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select, update
from sqlalchemy.engine import Engine

from policy_atlas.api.app import ApiConflict
from policy_atlas.api.deps import get_settings
from policy_atlas.api.routers import runs as runs_router
from policy_atlas.api.settings import Settings
from policy_atlas.core import events
from policy_atlas.core.schema import (
    artefact,
    capability_run,
    evidence_scope,
    runs,
    task,
    task_plan,
)
from tests.api.org_support import make_task, seeded, tenancy_client
from tests.api.resource_support import api_client, create_task
from tests.helpers import delete_task_data, now, seed_scope, seed_walk


def test_runs_require_approved_plan_and_hide_cross_owner_tasks(tmp_path: Path) -> None:
    """Reject malformed dispatches before any executor work and preserve BOLA opacity."""
    with api_client(tmp_path) as (client, owner, other):
        task_id = create_task(client, owner)
        no_plan = client.post(f"/api/v1/tasks/{task_id}/runs", headers=owner, json={})
        assert no_plan.status_code == 400
        assert no_plan.json()["error"]["code"] == "malformed"

        absent = client.post(f"/api/v1/tasks/{uuid.uuid4()}/runs", headers=other, json={})
        cross_owner = client.post(f"/api/v1/tasks/{task_id}/runs", headers=other, json={})
        assert absent.status_code == cross_owner.status_code == 404
        assert absent.json() == cross_owner.json()


def test_a_run_reports_the_artefact_it_wrote(engine: Engine, tmp_path: Path) -> None:
    """``artefact_id`` is what the walk produced, not a guess from its status.

    The scoping start states and the baseline band read this field to decide
    whether a baseline exists, so a walk that has written nothing must say
    ``null`` and the same walk must name the artefact the moment one is
    attached — on the listing and on the single-run read alike.
    """
    with api_client(tmp_path) as (client, owner, _other):
        task_id = uuid.UUID(create_task(client, owner))
        try:
            scope_id = uuid.uuid4()
            run_id = uuid.uuid4()
            with engine.begin() as conn:
                conn.execute(
                    evidence_scope.insert().values(
                        evidence_scope_id=scope_id,
                        task_id=task_id,
                        intent="What works?",
                        context={},
                        created_at=now(),
                    )
                )
                conn.execute(
                    capability_run.insert().values(
                        capability_run_id=run_id,
                        task_id=task_id,
                        evidence_scope_id=scope_id,
                        capability="evidence_search",
                        plan_id=uuid.uuid4(),
                        plan_version=1,
                        status="running",
                        started_at=now(),
                    )
                )

            listed = client.get(f"/api/v1/tasks/{task_id}/runs", headers=owner)
            fetched = client.get(f"/api/v1/tasks/{task_id}/runs/{run_id}", headers=owner)
            assert listed.status_code == fetched.status_code == 200, listed.text
            assert listed.json()["data"][0]["artefact_id"] is None
            assert fetched.json()["artefact_id"] is None

            artefact_id = uuid.uuid4()
            with engine.begin() as conn:
                conn.execute(
                    artefact.insert().values(
                        artefact_id=artefact_id,
                        task_id=task_id,
                        capability_run_id=run_id,
                        title="Baseline",
                        created_at=now(),
                    )
                )

            listed_again = client.get(f"/api/v1/tasks/{task_id}/runs", headers=owner)
            fetched_again = client.get(
                f"/api/v1/tasks/{task_id}/runs/{run_id}", headers=owner
            )
            assert listed_again.json()["data"][0]["artefact_id"] == str(artefact_id)
            assert fetched_again.json()["artefact_id"] == str(artefact_id)
        finally:
            with engine.begin() as conn:
                delete_task_data(conn, task_id)


def test_a_walk_carries_its_own_steps_and_not_its_option_searches(
    engine: Engine, tmp_path: Path
) -> None:
    """Task 058, round 11: each run on the list and the one-run read carries its steps.

    The steps are the walk's own, folded from the frames the stream sends: the
    walk-level ``option_searches`` (no component run; its completion before
    round 11 named no walk) stays with the walk, a child's ``acquire`` with the
    child.
    """
    with api_client(tmp_path) as (client, owner, _other):
        task_id = uuid.UUID(create_task(client, owner))
        try:
            scope_id = uuid.uuid4()
            walk, child = uuid.uuid4(), uuid.uuid4()
            with engine.begin() as conn:
                conn.execute(
                    evidence_scope.insert().values(
                        evidence_scope_id=scope_id,
                        task_id=task_id,
                        intent="What works?",
                        context={},
                        created_at=now(),
                    )
                )
                for walk_id, parent in ((walk, None), (child, walk)):
                    conn.execute(
                        capability_run.insert().values(
                            capability_run_id=walk_id,
                            task_id=task_id,
                            evidence_scope_id=scope_id,
                            capability="options_scoping",
                            plan_id=uuid.uuid4(),
                            plan_version=1,
                            status="running",
                            started_at=now(),
                            parent_capability_run_id=parent,
                        )
                    )

                def component(walk_id: uuid.UUID) -> uuid.UUID:
                    run_id = uuid.uuid4()
                    conn.execute(
                        runs.insert().values(
                            run_id=run_id,
                            task_id=task_id,
                            status="running",
                            started_at=now(),
                            capability_run_id=walk_id,
                        )
                    )
                    return run_id

                def append(run_id: uuid.UUID | None, kind: str, payload: dict[str, object]) -> None:
                    events.append(
                        conn, task_id=task_id, run_id=run_id, event_type=kind, payload=payload
                    )

                suggest = component(walk)
                append(suggest, "run.started", {"component": "suggest"})
                append(suggest, "component.completed", {"component": "suggest", "suggested": 4})
                append(
                    None,
                    "run.started",
                    {"component": "option_searches", "capability_run_id": str(walk)},
                )
                own_search = component(walk)
                child_search = component(child)
                append(child_search, "run.started", {"component": "acquire"})
                append(own_search, "run.started", {"component": "acquire"})
                append(
                    own_search,
                    "component.completed",
                    {"component": "acquire", "acquired": 312, "wall_clock_s": 4.5},
                )
                # A completion written before round 11: no walk named.
                append(
                    None,
                    "component.completed",
                    {"component": "option_searches", "total": 4, "finished": 4, "sources": 9},
                )

            listed = client.get(f"/api/v1/tasks/{task_id}/runs", headers=owner)
            assert listed.status_code == 200, listed.text
            by_id = {row["capability_run_id"]: row for row in listed.json()["data"]}
            steps = by_id[str(walk)]["stages"]
            assert [(step["stage"], step["status"]) for step in steps] == [
                ("suggest", "completed"),
                ("option_searches", "completed"),
                ("acquire", "completed"),
            ]
            assert steps[0]["label"] == "Suggesting options"
            assert steps[0]["counts"] == [{"value": 4, "noun": "suggested"}]
            assert steps[0]["started_at"] is not None and steps[0]["ended_at"] is not None
            assert steps[1]["summary"] == {"total": 4, "finished": 4, "sources": 9}
            assert steps[2]["seconds"] == 4.5
            assert steps[2]["counts"] == [{"value": 312, "noun": "found"}]
            child_steps = by_id[str(child)]["stages"]
            assert [(step["stage"], step["status"]) for step in child_steps] == [
                ("acquire", "started")
            ]
            assert child_steps[0]["ended_at"] is None

            fetched = client.get(f"/api/v1/tasks/{task_id}/runs/{walk}", headers=owner)
            assert fetched.status_code == 200, fetched.text
            assert fetched.json()["stages"] == steps
        finally:
            with engine.begin() as conn:
                delete_task_data(conn, task_id)


# --- task 064a: the per-person run cap (Q7) and the failed dispatch (Q14) ---------


def _wide_executor(request: Request) -> Settings:
    """The app's settings with a global cap no shared-database row can reach."""
    return replace(cast(Settings, request.app.state.settings), run_executor_max=1000)


def _seed_walks(engine: Engine, owner: str, statuses: list[str]) -> list[uuid.UUID]:
    """One task per status, owned by ``owner``, each holding one parentless walk."""
    task_ids = []
    with seeded(engine) as conn:
        for status in statuses:
            task_id = make_task(conn, owner_user_id=owner)
            seed_walk(conn, task_id, capability="evidence_search", status=status)
            task_ids.append(task_id)
    return task_ids


def _new_task(engine: Engine, owner: str) -> uuid.UUID:
    with seeded(engine) as conn:
        return make_task(conn, owner_user_id=owner)


def _start(client: TestClient, headers: dict[str, str], task_id: uuid.UUID) -> Response:
    return cast(Response, client.post(f"/api/v1/tasks/{task_id}/runs", headers=headers, json={}))


def _past_the_cap(response: Response) -> bool:
    """The task has no plan, so a start the cap admits stops at the next check (400)."""
    return response.status_code == 400 and response.json()["error"]["code"] == "malformed"


def _drop(engine: Engine, task_ids: list[uuid.UUID]) -> None:
    with engine.begin() as conn:
        for task_id in task_ids:
            delete_task_data(conn, task_id)


def test_a_fourth_start_is_refused_and_another_persons_start_is_not(
    engine: Engine, tmp_path: Path
) -> None:
    """Three running walks fill one person's allowance; it is theirs alone."""
    with tenancy_client(tmp_path, count=2, overrides={get_settings: _wide_executor}) as (
        client,
        (a, b),
    ):
        created = _seed_walks(engine, a.user_id, ["running"] * 3)
        try:
            created += [fourth := _new_task(engine, a.user_id), bs := _new_task(engine, b.user_id)]
            refused = _start(client, a.headers, fourth)
            assert refused.status_code == 409, refused.text
            assert refused.json()["error"]["code"] == "user_capacity"
            assert _past_the_cap(_start(client, b.headers, bs))
        finally:
            _drop(engine, created)


def test_a_collaborator_cannot_lift_the_owners_cap(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cap is counted for the task's owner, whoever presses Start.

    Write is owner-only today (``access.py``), so the collaborator's write
    grade is granted here by hand: the test pins what a future write share
    would meet.
    """
    from policy_atlas.api.routers.access import accessible_task as real


    def grant_write(conn: Any, *, task_id: uuid.UUID, user_id: str, **kwargs: Any) -> Any:
        with seeded(engine) as read:
            owner = read.execute(
                select(task.c.owner_user_id).where(task.c.task_id == task_id)
            ).scalar_one()
        return real(conn, task_id=task_id, user_id=owner, **kwargs)

    monkeypatch.setattr(runs_router, "accessible_task", grant_write)
    with tenancy_client(tmp_path, count=2, overrides={get_settings: _wide_executor}) as (
        client,
        (a, collaborator),
    ):
        created = _seed_walks(engine, a.user_id, ["running"] * 3)
        try:
            created.append(fourth := _new_task(engine, a.user_id))
            refused = _start(client, collaborator.headers, fourth)
            assert refused.status_code == 409, refused.text
            assert refused.json()["error"]["code"] == "user_capacity"
        finally:
            _drop(engine, created)


def test_a_paused_walk_does_not_count_against_the_cap(engine: Engine, tmp_path: Path) -> None:
    with tenancy_client(tmp_path, count=1, overrides={get_settings: _wide_executor}) as (
        client,
        (a,),
    ):
        created = _seed_walks(engine, a.user_id, ["running", "running", "paused"])
        try:
            created.append(fourth := _new_task(engine, a.user_id))
            assert _past_the_cap(_start(client, a.headers, fourth))
        finally:
            _drop(engine, created)


def test_reservations_count_against_the_cap(engine: Engine, tmp_path: Path) -> None:
    """Two starts whose rows are not written yet plus one running walk fill a cap of three."""
    with tenancy_client(tmp_path, count=1, overrides={get_settings: _wide_executor}) as (
        client,
        (a,),
    ):
        created = _seed_walks(engine, a.user_id, ["running"])
        reserved = [_new_task(engine, a.user_id), _new_task(engine, a.user_id)]
        created += reserved
        try:
            with runs_router._dispatch_lock:
                runs_router._dispatching_tasks.update(reserved)
            created.append(fourth := _new_task(engine, a.user_id))
            refused = _start(client, a.headers, fourth)
            assert refused.status_code == 409, refused.text
            assert refused.json()["error"]["code"] == "user_capacity"
        finally:
            with runs_router._dispatch_lock:
                runs_router._dispatching_tasks.difference_update(reserved)
            _drop(engine, created)


def _approved_plan(engine: Engine, task_id: uuid.UUID) -> None:
    """An approved plan row; its payload is never validated (the tests stub that)."""
    with seeded(engine) as conn:
        conn.execute(
            task_plan.insert().values(
                plan_id=uuid.uuid4(),
                task_id=task_id,
                evidence_scope_id=seed_scope(conn, task_id),
                version=1,
                status="approved",
                payload={},
                created_at=now(),
                created_by="user",
                approved_at=now(),
            )
        )


def test_a_theory_of_change_check_takes_the_same_cap(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``start_toc_check``, the second admission site in this module."""
    from policy_atlas.api import toc_start

    settings = Settings("i", "c", None, None, "o", "db", run_executor_max=1000)
    a, b = f"user-{uuid.uuid4()}", f"user-{uuid.uuid4()}"
    created = _seed_walks(engine, a, ["running"] * 3)
    created += [fourth := _new_task(engine, a), bs := _new_task(engine, b)]
    submitted: list[dict[str, object]] = []

    class Recording:
        def submit(self, _fn: object, *_args: object, **kwargs: object) -> None:
            submitted.append(kwargs)

    def start(task_id: uuid.UUID, user_id: str) -> uuid.UUID | None:
        return runs_router.start_toc_check(
            engine,
            task_id=task_id,
            link_ids=[],
            user_id=user_id,
            settings=settings,
            executor=Recording(),  # type: ignore[arg-type]
            backends=None,  # type: ignore[arg-type]
        )

    monkeypatch.setattr(toc_start, "mint_scope", lambda *_a, **_k: uuid.uuid4())
    # Paused walks do not count: two running and one paused leave c one slot.
    c = f"user-{uuid.uuid4()}"
    created += _seed_walks(engine, c, ["running", "running", "paused"])
    created += [cs := _new_task(engine, c)]
    # Reservations count: one running row plus two tasks in the reservation
    # set put d at three.
    d = f"user-{uuid.uuid4()}"
    created += _seed_walks(engine, d, ["running"])
    created += (reserved := [_new_task(engine, d), _new_task(engine, d)])
    created += [ds := _new_task(engine, d)]
    try:
        for task_id in (fourth, bs, cs, ds):
            _approved_plan(engine, task_id)
        with pytest.raises(ApiConflict) as caught:
            start(fourth, a)
        assert caught.value.code == "user_capacity"
        assert start(bs, b) is not None
        assert submitted and submitted[0]["task_id"] == bs
        assert start(cs, c) is not None
        with runs_router._dispatch_lock:
            runs_router._dispatching_tasks.update(reserved)
        with pytest.raises(ApiConflict) as caught:
            start(ds, d)
        assert caught.value.code == "user_capacity"
    finally:
        with runs_router._dispatch_lock:
            runs_router._dispatching_tasks.difference_update({bs, cs, ds, *reserved})
        _drop(engine, created)


def test_a_theory_of_change_check_gives_its_reservation_back_once_the_row_exists(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Held for the whole check, the reservation counted twice against both caps.

    Once the row exists the database count owns the slot. A check queued while
    the walk runs is chained on the same worker and takes its own reservation
    for its own pre-insert window.
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from policy_atlas.api import toc_start

    settings = Settings("i", "c", None, None, "o", "db", run_executor_max=1000)
    owner = f"user-{uuid.uuid4()}"
    task_id = _new_task(engine, owner)
    hold = threading.Event()

    def write_row_then_wait(engine_: Engine, **kwargs: Any) -> SimpleNamespace:
        with engine_.begin() as conn:
            seed_walk(
                conn,
                kwargs["task_id"],
                capability="theory_of_change",
                status="running",
                walk_id=kwargs["capability_run_id"],
                scope_id=kwargs["evidence_scope_id"],
                plan_id=kwargs["plan_id"],
            )
        hold.wait(10)
        return SimpleNamespace(follow_on=None)

    def rows() -> dict[uuid.UUID, str]:
        with engine.connect() as conn:
            return dict(
                conn.execute(
                    select(capability_run.c.capability_run_id, capability_run.c.status).where(
                        capability_run.c.task_id == task_id
                    )
                ).tuples().all()
            )

    def wait_for(condition: Any) -> bool:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if condition():
                return True
            time.sleep(0.02)
        return False

    monkeypatch.setattr(
        runs_router, "validate_plan", lambda *_a: SimpleNamespace(source_turn_index=None)
    )
    monkeypatch.setattr(runs_router, "run_plan", write_row_then_wait)
    monkeypatch.setattr(toc_start, "run_toc_sequence", lambda *_a, **_k: None)
    monkeypatch.setattr(
        toc_start, "mint_scope", lambda conn, *, task_id, **_k: seed_scope(conn, task_id)
    )
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        _approved_plan(engine, task_id)

        def start() -> uuid.UUID | None:
            return runs_router.start_toc_check(
                engine,
                task_id=task_id,
                link_ids=[],
                user_id=owner,
                settings=settings,
                executor=executor,
                backends=None,  # type: ignore[arg-type]
            )

        walk_id = start()
        assert walk_id is not None
        assert wait_for(lambda: not runs_router.dispatch_reserved(task_id))
        assert rows() == {walk_id: "running"}  # released while the walk still runs
        assert start() is None  # a running walk: the second check is queued
        hold.set()
        assert wait_for(lambda: len(rows()) == 2 and not runs_router.dispatch_reserved(task_id))
    finally:
        hold.set()
        executor.shutdown(wait=True)
        with runs_router._dispatch_lock:
            runs_router._dispatching_tasks.discard(task_id)
        _drop(engine, [task_id])


def test_a_failed_dispatch_interrupts_only_the_walk_it_minted(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Q14: the walk row exists, the dispatch raises, and only that id is interrupted.

    The other ``running`` row is a parentless walk on the same task, the
    shape another surface would leave by starting in the gap after the
    reservation is dropped (the contract's hazard); it is left alone. Once
    it ends, the task can be started again (no ``run_active``).
    """
    others: list[uuid.UUID] = []

    def fail_after_the_row(engine: Engine, **kwargs: Any) -> None:
        with engine.begin() as conn:
            seed_walk(
                conn,
                kwargs["task_id"],
                capability="evidence_search",
                status="running",
                walk_id=kwargs["capability_run_id"],
                scope_id=kwargs["evidence_scope_id"],
                plan_id=kwargs["plan_id"],
            )
            other = seed_walk(
                conn,
                kwargs["task_id"],
                capability="evidence_search",
                status="running",
                scope_id=kwargs["evidence_scope_id"],
                plan_id=kwargs["plan_id"],
            )
            others.append(other.walk_id)
        raise RuntimeError("between pipeline steps")

    monkeypatch.setattr(
        runs_router, "validate_plan", lambda *_a: SimpleNamespace(source_turn_index=None)
    )
    monkeypatch.setattr(runs_router, "run_plan", fail_after_the_row)
    with tenancy_client(tmp_path, count=1, overrides={get_settings: _wide_executor}) as (
        client,
        (a,),
    ):
        task_id = _new_task(engine, a.user_id)
        try:
            _approved_plan(engine, task_id)
            first = _start(client, a.headers, task_id)
            assert first.status_code == 201, first.text
            walk_id = uuid.UUID(first.json()["capability_run_id"])
            # `create_run` drops the reservation as soon as the row exists,
            # before the executor thread reaches its failure branch, so wait
            # for the minted walk itself to leave `running` (review stack).
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                with engine.connect() as conn:
                    statuses = dict(
                        conn.execute(
                            select(capability_run.c.capability_run_id, capability_run.c.status)
                            .where(capability_run.c.task_id == task_id)
                        ).tuples().all()
                    )
                if statuses.get(walk_id) != "running":
                    break
                time.sleep(0.02)
            assert statuses == {walk_id: "interrupted", others[0]: "running"}
            with engine.begin() as conn:
                conn.execute(
                    update(capability_run)
                    .where(capability_run.c.capability_run_id == others[0])
                    .values(status="succeeded", ended_at=now())
                )
            again = _start(client, a.headers, task_id)
            assert again.status_code == 201, again.text
        finally:
            deadline = time.monotonic() + 10
            while runs_router.dispatch_reserved(task_id) and time.monotonic() < deadline:
                time.sleep(0.02)
            _drop(engine, [task_id])
