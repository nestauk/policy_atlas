"""Opening the longlist walk (task 045, S3; ADR 0039 decision 1).

"Confirm plan and build longlist" opens a **second walk** on the confirmed
plan version: a new ``capability_run`` under its own intent record
(``purpose = 'longlist'``, ``plan_id`` = the confirmed version, the intent
compiled from the plan by :func:`compile_longlist_intent`). Three surfaces
open it:

- the chat gate (``_dispatch_gate_turn``, after the decision's commit; the
  opened walk rides the decision) and the check-in card (``204``, not awaited);
- ``POST /plan/confirm-baseline`` (after its own transaction has committed —
  the lock order is the task-row transaction closed, then ``_dispatch_lock``,
  as ``create_run`` takes them);
- the unattended follow-on, inline on the worker that ran the baseline
  (``runs._run_follow_on_longlist``).

Every surface takes the admission ``POST /runs`` takes — the dispatch lock,
no ``running | paused`` parentless walk, the pre-insert reservation — so two
walks can never race into existence (A23).
"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.app import ApiConflict
from policy_atlas.api.contract import LatestRun
from policy_atlas.api.locks import task_lock
from policy_atlas.api.routers._common import ACTIVE_WALK_STATUSES, parentless_walk
from policy_atlas.api.routers.runs import (
    _await_new_run,
    _dispatch_lock,
    _dispatch_run,
    _dispatching_tasks,
    release_when_open,
)
from policy_atlas.core.schema import capability_run, evidence_scope, task_plan
from policy_atlas.options_scoping.longlist_intent import compile_longlist_intent
from policy_atlas.runtime.capability_registry import OPTIONS_SCOPING, validate_plan
from policy_atlas.runtime.runner import RunnerBackends
from policy_atlas.runtime.scoping_plan import (
    LONGLIST_PURPOSE,
    ScopingPlan,
    compose_longlist_screen_intent,
)

log = structlog.get_logger()


class LonglistRefused(Exception):
    """The longlist walk could not be opened.

    Args:
        reason: ``not_scoping`` · ``run_active`` · ``capacity`` ·
            ``plan_stale`` · ``plan_too_long`` · ``no_plan``.
        message: A sentence for the error body.
    """

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


def http_error(refusal: LonglistRefused) -> Exception:
    """Map a refusal onto the error a route raises.

    Args:
        refusal: The opener's refusal.

    Returns:
        ``ApiConflict`` for a state the user can wait out or refresh past
        (``run_active``, ``capacity``, ``plan_stale``); a ``422`` for a plan the
        longlist cannot be built from (``plan_too_long``, ``not_scoping``,
        ``no_plan``).
    """
    if refusal.reason in {"run_active", "capacity", "plan_stale"}:
        return ApiConflict(refusal.reason, refusal.message)
    return HTTPException(status_code=422, detail=refusal.message)


@dataclass(frozen=True)
class AdmittedLonglist:
    """A longlist walk admitted and minted, not yet running.

    Args:
        capability_run_id: The walk's identity, minted here.
        evidence_scope_id: Its longlist intent record.
        plan_row: The confirmed plan version it runs.
    """

    capability_run_id: uuid.UUID
    evidence_scope_id: uuid.UUID
    plan_row: dict[str, Any]


def admit_and_mint(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    plan_row: dict[str, Any] | None = None,
    check_capacity: bool = True,
    capacity: int | None = None,
    executor: ThreadPoolExecutor | None = None,
    backends: RunnerBackends | None = None,
    user_id: str | None = None,
) -> AdmittedLonglist:
    """Admit a longlist walk and mint its intent record, under the dispatch lock.

    The admission ``create_run`` makes: no ``running | paused`` parentless walk
    and no reservation for the task, and (unless ``check_capacity`` is false)
    fewer running parentless walks plus reservations than the executor's
    width. Then, in the same transaction, the longlist intent record is
    inserted and the reservation taken. With ``executor``, the walk is
    submitted under the lock too, exactly as ``create_run`` submits.

    Args:
        engine: Database engine.
        task_id: The options-scoping task.
        plan_row: The confirmed plan version, re-read by the caller after its
            own commit; ``None`` takes the current approved version. It must
            still be the current approved version.
        check_capacity: ``False`` for the unattended follow-on, which runs on
            the worker the baseline already held.
        capacity: The executor's width; required when ``check_capacity``.
        executor: The walk executor to submit to, or ``None`` to submit nothing
            (the follow-on runs the walk inline).
        backends: The runner backend bundle (with ``executor``).
        user_id: The user traces are attributed to (with ``executor``).

    Returns:
        The admitted walk.

    Raises:
        LonglistRefused: If the admission or the plan refuses.
    """
    with _dispatch_lock:
        with engine.begin() as conn:
            task_row = task_lock(conn, task_id)
            if task_row["capability"] != OPTIONS_SCOPING:
                raise LonglistRefused(
                    "not_scoping", "a longlist is built for options-scoping tasks only"
                )
            active = conn.execute(
                select(capability_run.c.capability_run_id)
                .where(capability_run.c.task_id == task_id)
                .where(capability_run.c.status.in_(ACTIVE_WALK_STATUSES))
                .where(parentless_walk())
                .limit(1)
            ).scalar_one_or_none()
            if active is not None or task_id in _dispatching_tasks:
                raise LonglistRefused("run_active", "the task already has an active run")
            if check_capacity:
                running = conn.execute(
                    select(capability_run.c.capability_run_id)
                    .where(capability_run.c.status == "running")
                    .where(parentless_walk())
                ).all()
                if capacity is None or len(running) + len(_dispatching_tasks) >= capacity:
                    raise LonglistRefused("capacity", "the walk executor is at capacity")
            current = conn.execute(
                select(task_plan)
                .where(task_plan.c.task_id == task_id)
                .where(task_plan.c.status == "approved")
                .order_by(task_plan.c.version.desc())
                .limit(1)
            ).mappings().one_or_none()
            if current is None:
                raise LonglistRefused("no_plan", "the task has no approved plan")
            if plan_row is not None and current["plan_id"] != plan_row["plan_id"]:
                raise LonglistRefused(
                    "plan_stale",
                    "the plan moved on since it was confirmed — review it, then confirm",
                )
            plan = validate_plan(OPTIONS_SCOPING, current["payload"])
            assert isinstance(plan, ScopingPlan)
            try:
                compose_longlist_screen_intent(plan)
            except ValueError as exc:
                raise LonglistRefused(
                    "plan_too_long",
                    "the plan's outcomes and requirements are too long to screen a "
                    f"longlist against — shorten them, then confirm ({exc})",
                ) from exc
            scope_id = uuid.uuid4()
            conn.execute(
                evidence_scope.insert().values(
                    evidence_scope_id=scope_id,
                    task_id=task_id,
                    intent=compile_longlist_intent(plan),
                    context={"capability": OPTIONS_SCOPING},
                    created_at=datetime.now(UTC),
                    purpose=LONGLIST_PURPOSE,
                    plan_id=current["plan_id"],
                )
            )
            _dispatching_tasks.add(task_id)
        admitted = AdmittedLonglist(
            capability_run_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            plan_row=dict(current),
        )
        if executor is not None:
            if backends is None or user_id is None:
                _dispatching_tasks.discard(task_id)
                raise ValueError("submitting a walk needs its backends and user")
            try:
                executor.submit(
                    _dispatch_run,
                    engine,
                    task_id=task_id,
                    capability=OPTIONS_SCOPING,
                    plan_row=admitted.plan_row,
                    backends=backends,
                    user_id=user_id,
                    evidence_scope_id=admitted.evidence_scope_id,
                    capability_run_id=admitted.capability_run_id,
                )
            except BaseException:
                _dispatching_tasks.discard(task_id)
                raise
    log.info(
        "longlist.opened",
        task_id=str(task_id),
        capability_run_id=str(admitted.capability_run_id),
        plan_version=admitted.plan_row["version"],
    )
    return admitted


def open_longlist_walk(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    plan_row: dict[str, Any] | None,
    backends: RunnerBackends,
    executor: ThreadPoolExecutor,
    user_id: str,
    await_run: bool = True,
) -> uuid.UUID:
    """Open the longlist walk on the confirmed plan version.

    Called outside any transaction. Admits and mints under the dispatch lock
    (:func:`admit_and_mint`), submits the walk to the walk executor, and then
    either waits for the walk's row (``await_run``, so the caller can return
    it) or hands the reservation's release to a short waiter (the card path
    answers ``204`` at once).

    Args:
        engine: Database engine.
        task_id: The options-scoping task.
        plan_row: The confirmed version as the caller re-read it, or ``None``
            for the current approved version.
        backends: The runner backend bundle.
        executor: The walk executor.
        user_id: The user traces are attributed to.
        await_run: Whether to wait for the walk's row before returning.

    Returns:
        The opened walk's ``capability_run_id``.

    Raises:
        LonglistRefused: If the admission or the plan refuses.
    """
    admitted = admit_and_mint(
        engine,
        task_id=task_id,
        plan_row=plan_row,
        # The executor's own width: the number ``settings.run_executor_max``
        # built it with, the one ``create_run`` compares against.
        capacity=executor._max_workers,
        executor=executor,
        backends=backends,
        user_id=user_id,
    )
    if not await_run:
        release_when_open(engine, task_id=task_id, capability_run_id=admitted.capability_run_id)
        return admitted.capability_run_id
    try:
        _await_new_run(
            engine,
            task_id=task_id,
            existing_ids=set(),
            capability_run_id=admitted.capability_run_id,
        )
    finally:
        # Once the row exists the database's ``running`` count owns capacity.
        with _dispatch_lock:
            _dispatching_tasks.discard(task_id)
    return admitted.capability_run_id


def opened_run(engine: Engine, *, task_id: uuid.UUID, capability_run_id: uuid.UUID) -> LatestRun:
    """Read an opened walk as the optional ``opened_run`` field carries it.

    Args:
        engine: Database engine.
        task_id: The task.
        capability_run_id: The walk the opener returned.

    Returns:
        The walk's identity, status and times.
    """
    with engine.connect() as conn:
        row = conn.execute(
            select(capability_run)
            .where(capability_run.c.task_id == task_id)
            .where(capability_run.c.capability_run_id == capability_run_id)
        ).mappings().one()
    return LatestRun(
        capability_run_id=row["capability_run_id"],
        status=row["status"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
    )


def longlist_walk_exists(engine: Engine, *, task_id: uuid.UUID, plan_id: uuid.UUID) -> bool:
    """Whether a longlist walk exists for one plan version.

    Args:
        engine: Database engine.
        task_id: The task.
        plan_id: The plan version.

    Returns:
        ``True`` when a walk runs (or ran) under a longlist intent record of
        that version.
    """
    with engine.connect() as conn:
        found = conn.execute(
            select(capability_run.c.capability_run_id)
            .select_from(
                capability_run.join(
                    evidence_scope,
                    (evidence_scope.c.evidence_scope_id == capability_run.c.evidence_scope_id)
                    & (evidence_scope.c.task_id == capability_run.c.task_id),
                )
            )
            .where(capability_run.c.task_id == task_id)
            .where(evidence_scope.c.purpose == LONGLIST_PURPOSE)
            .where(evidence_scope.c.plan_id == plan_id)
            .limit(1)
        ).scalar_one_or_none()
    return found is not None
