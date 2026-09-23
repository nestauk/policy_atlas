"""Capability-run dispatch and read resource routes."""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from policy_atlas.api.app import ApiConflict
from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract import RunCreate, RunOut
from policy_atlas.api.contract.common import PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX, Page, PageMeta
from policy_atlas.api.deps import (
    get_current_user,
    get_engine,
    get_executor,
    get_runner_backends,
    get_settings,
)
from policy_atlas.api.routers._access import accessible_task
from policy_atlas.api.routers._common import (
    ACTIVE_WALK_STATUSES,
    parentless_walk,
    run_artefact_id_column,
    run_out,
    run_purpose_column,
)
from policy_atlas.api.run_io import ParkIO
from policy_atlas.api.settings import Settings
from policy_atlas.core import tracing
from policy_atlas.core.schema import capability_run, task_agent_transcript, task_plan
from policy_atlas.runtime.capability_registry import validate_plan
from policy_atlas.runtime.option_search import unattended_plan
from policy_atlas.runtime.runner import RunnerBackends, run_plan
from policy_atlas.runtime.scoping_plan import LONGLIST_PURPOSE

log = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/tasks",
    tags=["runs"],
    dependencies=[Depends(get_current_user)],
)

_dispatch_lock = threading.Lock()
_dispatching_tasks: set[uuid.UUID] = set()


def dispatch_reserved(task_id: uuid.UUID) -> bool:
    """Whether a run admission for the task is in its pre-insert window.

    The reservation lives in process memory between run admission and the
    executor's capability-run insert; archive must consult it or it can win
    that window and archive a task whose run then executes hidden (review
    finding codex-9, 2026-07-21). Sound under the pinned one-instance posture —
    the same posture the reservation itself relies on.
    """
    with _dispatch_lock:
        return task_id in _dispatching_tasks


def _dispatch_run(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    capability: str,
    plan_row: dict[str, object],
    backends: RunnerBackends,
    user_id: str,
    evidence_scope_id: uuid.UUID | None = None,
    capability_run_id: uuid.UUID | None = None,
) -> None:
    """Run one approved walk on an executor worker and release its reservation.

    Args:
        engine: Database engine.
        task_id: The task.
        capability: The task's capability (decides the plan model).
        plan_row: The approved plan row the walk runs.
        backends: The runner backend bundle.
        user_id: The user traces are attributed to.
        evidence_scope_id: The intent record to run under, when it is not the
            plan row's own (task 045: a longlist walk runs under the longlist
            record the start surface minted). ``None`` uses the plan row's.
        capability_run_id: The walk's identity when the start surface minted
            it (task 045); ``None`` lets the runner mint one.
    """
    try:
        # Opened inside the executor worker: contextvars do not cross a plain
        # executor.submit. run_plan opens its own session scope per component.
        with tracing.trace_scope(user_id=user_id):
            outcome = run_plan(
                engine,
                task_id=task_id,
                evidence_scope_id=(
                    evidence_scope_id
                    if evidence_scope_id is not None
                    else plan_row["evidence_scope_id"]  # type: ignore[arg-type]
                ),
                # The task row's capability, read on the request path and carried
                # here rather than re-queried: it decides which model reads the
                # payload (C9). Whatever that model is, the runner takes it —
                # narrowing to the Evidence search plan here made a scoping walk
                # impossible to start (task 044). A longlist walk (its own
                # intent record passed in) runs unattended: it does not pause
                # (task 045, D1).
                plan=(
                    unattended_plan(plan_row["payload"])  # type: ignore[arg-type]
                    if evidence_scope_id is not None
                    else validate_plan(capability, plan_row["payload"])
                ),
                plan_id=plan_row["plan_id"],  # type: ignore[arg-type]
                plan_version=plan_row["version"],  # type: ignore[arg-type]
                plan_row_id=plan_row["plan_id"],  # type: ignore[arg-type]
                backends=backends,
                io=ParkIO(),
                session_id=task_id,
                capability_run_id=capability_run_id,
            )
            if outcome.follow_on == LONGLIST_PURPOSE:
                # Unattended (task 045, A2): the baseline recorded its standing
                # default at the gate, so the longlist walk opens here, inline
                # on this worker, the moment the baseline has ended.
                _run_follow_on_longlist(
                    engine,
                    task_id=task_id,
                    capability=capability,
                    backends=backends,
                )
    except Exception:
        log.exception("api.run_dispatch_failed", task_id=str(task_id))
    finally:
        with _dispatch_lock:
            _dispatching_tasks.discard(task_id)


def _run_follow_on_longlist(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    capability: str,
    backends: RunnerBackends,
) -> None:
    """Open and run the unattended follow-on longlist walk on this worker.

    The opener's mint-and-run without its capacity gate: this worker is the
    capacity the baseline already held. The admission still stands — a walk
    another surface started in the gap wins, and this one is not opened.
    """
    # Imported here: the opener imports this module.
    from policy_atlas.api.longlist_start import LonglistRefused, admit_and_mint

    try:
        admitted = admit_and_mint(engine, task_id=task_id, check_capacity=False)
    except LonglistRefused as exc:
        log.warning(
            "api.follow_on_longlist_refused", task_id=str(task_id), reason=exc.reason
        )
        return
    release_when_open(
        engine, task_id=task_id, capability_run_id=admitted.capability_run_id
    )
    run_plan(
        engine,
        task_id=task_id,
        evidence_scope_id=admitted.evidence_scope_id,
        # The longlist walk does not pause (task 045, D1).
        plan=unattended_plan(admitted.plan_row["payload"]),
        plan_id=admitted.plan_row["plan_id"],
        plan_version=admitted.plan_row["version"],
        plan_row_id=admitted.plan_row["plan_id"],
        backends=backends,
        io=ParkIO(),
        session_id=task_id,
        capability_run_id=admitted.capability_run_id,
    )


def release_when_open(
    engine: Engine, *, task_id: uuid.UUID, capability_run_id: uuid.UUID
) -> None:
    """Release a task's launch reservation once its walk row exists.

    The start paths that do not wait for the row (the check-in card, the
    unattended follow-on) still hold the reservation across the pre-insert
    window; a short daemon thread gives it back as soon as the runner has
    written the row, which then owns capacity accounting — the same hand-over
    ``create_run`` makes after ``_await_new_run``. Bounded like that wait.

    Args:
        engine: Database engine.
        task_id: The reserved task.
        capability_run_id: The walk whose row ends the window.
    """

    def wait_then_release() -> None:
        try:
            _await_new_run(
                engine, task_id=task_id, existing_ids=set(), capability_run_id=capability_run_id
            )
        except Exception:  # noqa: BLE001 - the release below is the point
            log.warning("api.reservation_release_unobserved", task_id=str(task_id))
        finally:
            with _dispatch_lock:
                _dispatching_tasks.discard(task_id)

    threading.Thread(
        target=wait_then_release, name="policy-atlas-reservation", daemon=True
    ).start()


def _await_new_run(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    existing_ids: set[uuid.UUID],
    capability_run_id: uuid.UUID | None = None,
) -> RunOut:
    """Wait briefly for the executor's runtime-owned capability-run insertion.

    With ``capability_run_id`` (a walk whose identity the caller minted, task
    045) it waits for that row; otherwise for any row not in ``existing_ids``.
    """
    # 10s, not 2s: with both executor workers momentarily busy the submitted
    # dispatch can queue past 2s, turning a successful launch into a client 500
    # (review finding I3, 2026-07-21). The walk still starts either way; the
    # longer window keeps the response truthful for the transient case.
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            rows = conn.execute(
                select(capability_run, run_artefact_id_column(), run_purpose_column())
                .where(capability_run.c.task_id == task_id)
                .order_by(
                    capability_run.c.started_at.desc(),
                    capability_run.c.capability_run_id.desc(),
                )
            ).mappings().all()
        for row in rows:
            if capability_run_id is not None:
                if row["capability_run_id"] == capability_run_id:
                    return run_out(row)
            elif row["capability_run_id"] not in existing_ids:
                return run_out(row)
        time.sleep(0.01)
    raise RuntimeError("executor did not create a capability run")


@router.post("/{task_id}/runs", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def create_run(
    task_id: uuid.UUID,
    _: RunCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
    executor: Annotated[ThreadPoolExecutor, Depends(get_executor)],
    backends: Annotated[RunnerBackends, Depends(get_runner_backends)],
) -> RunOut:
    """Dispatch an approved plan off the request path and return its walk row."""
    with _dispatch_lock:
        with engine.begin() as conn:
            access = accessible_task(
                conn, task_id=task_id, user_id=user.user_id, write=True, for_update=True
            )
            # Parentless walks only (task 045, S15): a longlist walk's option
            # searches never fence a user action — their parent does — and
            # they never count against the executor, whose workers they do
            # not occupy (they run on the option-search pool).
            active = conn.execute(
                select(capability_run.c.capability_run_id)
                .where(capability_run.c.task_id == task_id)
                .where(capability_run.c.status.in_(ACTIVE_WALK_STATUSES))
                .where(parentless_walk())
                .limit(1)
            ).scalar_one_or_none()
            if active is not None or task_id in _dispatching_tasks:
                raise ApiConflict("run_active", "the task already has an active run")
            running = conn.execute(
                select(capability_run.c.capability_run_id)
                .where(capability_run.c.status == "running")
                .where(parentless_walk())
            ).all()
            if len(running) + len(_dispatching_tasks) >= settings.run_executor_max:
                raise ApiConflict("capacity", "the walk executor is at capacity")
            plan_row = conn.execute(
                select(task_plan)
                .where(task_plan.c.task_id == task_id)
                .where(task_plan.c.status == "approved")
                .order_by(task_plan.c.version.desc())
                .limit(1)
            ).mappings().one_or_none()
            if plan_row is None:
                raise HTTPException(status_code=400, detail="no approved plan")
            # Only ``source_turn_index`` is read here, and both plan models
            # carry it; the staleness rule is capability-neutral.
            approved_plan = validate_plan(access.row["capability"], plan_row["payload"])
            latest_completed_turn = conn.execute(
                select(func.max(task_agent_transcript.c.turn_index))
                .where(task_agent_transcript.c.task_id == task_id)
                .where(task_agent_transcript.c.status == "completed")
            ).scalar_one()
            if (
                approved_plan.source_turn_index is not None
                and latest_completed_turn is not None
                and approved_plan.source_turn_index < latest_completed_turn
            ):
                raise ApiConflict(
                    "plan_stale",
                    "the plan predates your latest Task Agent message — review it, then start",
                )
            existing_ids = {
                row[0]
                for row in conn.execute(
                    select(capability_run.c.capability_run_id).where(
                        capability_run.c.task_id == task_id
                    )
                )
            }
            _dispatching_tasks.add(task_id)
        executor.submit(
            _dispatch_run,
            engine,
            task_id=task_id,
            capability=access.row["capability"],
            plan_row=dict(plan_row),
            backends=backends,
            user_id=user.user_id,
        )
    created = _await_new_run(engine, task_id=task_id, existing_ids=existing_ids)
    # Once the runtime row exists, the database's ``running`` count owns
    # capacity accounting; keeping the launch reservation would double-count.
    with _dispatch_lock:
        _dispatching_tasks.discard(task_id)
    return created


@router.get("/{task_id}/runs", response_model=Page[RunOut])
def list_runs(
    task_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
) -> Page[RunOut]:
    """List a task's walks from newest to oldest (paginated — runs accumulate)."""
    with engine.connect() as conn:
        accessible_task(conn, task_id=task_id, user_id=user.user_id, write=False)
        total = conn.execute(
            select(func.count())
            .select_from(capability_run)
            .where(capability_run.c.task_id == task_id)
        ).scalar_one()
        rows = conn.execute(
            select(capability_run, run_artefact_id_column(), run_purpose_column())
            .where(capability_run.c.task_id == task_id)
            .order_by(capability_run.c.started_at.desc(), capability_run.c.capability_run_id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).mappings().all()
    return Page(
        data=[run_out(row) for row in rows],
        pagination=PageMeta(page=page, page_size=page_size, total_items=int(total)),
    )


@router.get("/{task_id}/runs/{run_id}", response_model=RunOut)
def get_run(
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
) -> RunOut:
    """Return one readable task's capability run, or the opaque 404."""
    with engine.connect() as conn:
        accessible_task(conn, task_id=task_id, user_id=user.user_id, write=False)
        row = conn.execute(
            select(capability_run, run_artefact_id_column(), run_purpose_column())
            .where(capability_run.c.task_id == task_id)
            .where(capability_run.c.capability_run_id == run_id)
        ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="resource not found")
    return run_out(row)
