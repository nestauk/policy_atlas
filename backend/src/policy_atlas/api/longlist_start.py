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

The shortlist walk (task 055, P8) takes the same admission through
:func:`open_shortlist_walk`: its intent record has ``purpose = 'shortlist'``
and composes the one ``shortlist`` step.
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
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.app import ApiConflict
from policy_atlas.api.contract import LatestRun
from policy_atlas.api.locks import task_lock
from policy_atlas.api.routers._common import ACTIVE_WALK_STATUSES, active_parentless_walk
from policy_atlas.api.routers.runs import (
    _await_new_run,
    _dispatch_lock,
    _dispatch_run,
    _dispatching_tasks,
    executor_full,
    release_when_open,
)
from policy_atlas.core.schema import (
    capability_run,
    evidence_scope,
    longlist_result,
    option,
    task_plan,
)
from policy_atlas.options_scoping.longlist_intent import compile_longlist_intent
from policy_atlas.runtime.capability_registry import (
    OPTIONS_SCOPING,
    expect_scoping_plan,
    latest_approved_plan_row,
    validate_plan,
)
from policy_atlas.runtime.runner import RunnerBackends
from policy_atlas.runtime.scoping_plan import (
    LONGLIST_PURPOSE,
    SHORTLIST_PURPOSE,
    ScopingPlan,
    compose_longlist_screen_intent,
    longlist_inputs,
    shortlist_proposal_stale,
)

log = structlog.get_logger()

#: When this process started. A longlist intent record with no walk row yet is
#: a walk still queued on this process's executor only if it was minted after
#: this moment: a queue does not survive a restart (B3).
_PROCESS_STARTED = datetime.now(UTC)


class LonglistRefused(Exception):
    """The longlist walk could not be opened, or a longlist action is not allowed.

    Args:
        reason: ``not_scoping`` · ``run_active`` · ``capacity`` ·
            ``plan_stale`` · ``plan_too_long`` · ``no_plan``; for a shortlist
            walk also ``no_longlist`` and ``nothing_to_propose``, and for the
            shortlist button ``not_included`` (task 055).
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
        (``run_active``, ``capacity``, ``plan_stale``, and for the shortlist
        ``nothing_to_propose`` and ``not_included``); a ``404`` for
        ``no_longlist``; a ``422`` for a plan the longlist cannot be built from
        (``plan_too_long``, ``not_scoping``, ``no_plan``).
    """
    if refusal.reason in {
        "run_active",
        "capacity",
        "plan_stale",
        "nothing_to_propose",
        "not_included",
    }:
        return ApiConflict(refusal.reason, refusal.message)
    if refusal.reason == "no_longlist":
        return HTTPException(status_code=404, detail=refusal.message)
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
    shortlist_suggest: bool | None = None,
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
        shortlist_suggest: ``None`` for a longlist walk. ``True`` or
            ``False`` mints a shortlist walk's intent record instead (task
            055, P8): Suggest more, or a re-proposal after an appetite change.

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
            if active_parentless_walk(conn, task_id) is not None or task_id in _dispatching_tasks:
                raise LonglistRefused("run_active", "the task already has an active run")
            if check_capacity and executor_full(conn, capacity):
                raise LonglistRefused("capacity", "the walk executor is at capacity")
            current = latest_approved_plan_row(conn, task_id)
            if current is None:
                raise LonglistRefused("no_plan", "the task has no approved plan")
            if plan_row is not None and current["plan_id"] != plan_row["plan_id"]:
                raise LonglistRefused(
                    "plan_stale",
                    "the plan moved on since it was confirmed — review it, then confirm",
                )
            plan = expect_scoping_plan(validate_plan(OPTIONS_SCOPING, current["payload"]))
            if shortlist_suggest is None:
                try:
                    compose_longlist_screen_intent(plan)
                except ValueError as exc:
                    raise LonglistRefused(
                        "plan_too_long",
                        "the plan's outcomes and requirements are too long to screen a "
                        f"longlist against — shorten them, then confirm ({exc})",
                    ) from exc
                purpose, intent = LONGLIST_PURPOSE, compile_longlist_intent(plan)
                context: dict[str, Any] = {"capability": OPTIONS_SCOPING}
            else:
                keep_places = _refuse_shortlist(
                    conn, task_id=task_id, plan=plan, suggest=shortlist_suggest
                )
                purpose, intent = SHORTLIST_PURPOSE, "shortlist"
                context = {"capability": OPTIONS_SCOPING}
                if keep_places:
                    context["suggest"] = True
            scope_id = uuid.uuid4()
            conn.execute(
                evidence_scope.insert().values(
                    evidence_scope_id=scope_id,
                    task_id=task_id,
                    intent=intent,
                    context=context,
                    created_at=datetime.now(UTC),
                    purpose=purpose,
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
        "longlist.opened" if shortlist_suggest is None else "shortlist.opened",
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


def longlist_pinned_plan(
    conn: Connection, *, task_id: uuid.UUID
) -> tuple[int, ScopingPlan | None] | None:
    """The plan version the task's newest longlist was built from (task 055, PR6).

    Args:
        conn: Open database connection.
        task_id: The task.

    Returns:
        ``None`` when the task has no longlist; otherwise the newest
        longlist's ``plan_version`` and that version's plan, or ``None`` for
        the plan when the version's row cannot be read.
    """
    built = conn.execute(
        select(longlist_result.c.plan_version)
        .where(longlist_result.c.task_id == task_id)
        .order_by(
            longlist_result.c.created_at.desc(), longlist_result.c.longlist_result_id.desc()
        )
        .limit(1)
    ).scalar_one_or_none()
    if built is None:
        return None
    pinned = conn.execute(
        select(task_plan.c.payload)
        .where(task_plan.c.task_id == task_id)
        .where(task_plan.c.version == built)
    ).scalar_one_or_none()
    if pinned is None:
        return int(built), None
    return int(built), expect_scoping_plan(validate_plan(OPTIONS_SCOPING, pinned))


def _refuse_shortlist(
    conn: Connection, *, task_id: uuid.UUID, plan: ScopingPlan, suggest: bool
) -> bool:
    """Refuse a shortlist walk that has nothing to work on (task 055, P8).

    Suggest more on a stale proposal (none yet, or made under another risk
    appetite: :func:`shortlist_proposal_stale`, the rule the longlist view
    serves as ``shortlist.stale``) opens a re-proposal instead: the screen
    asks for Suggest more after an appetite change, and keeping the old picks
    would only fill the gaps.

    Args:
        conn: The admission's connection, inside its transaction.
        task_id: The task.
        plan: The current approved plan.
        suggest: Whether the walk is Suggest more.

    Returns:
        Whether the walk keeps Policy Atlas's picks (Suggest more on a
        current proposal); ``False`` re-proposes.

    Raises:
        LonglistRefused: ``no_longlist`` when the task has no longlist;
            ``plan_stale`` when the plan changed in a field the longlist
            reads since it was built (a Rebuild is due, not a proposal);
            ``nothing_to_propose`` (Suggest more on a current proposal only)
            when every included option already holds a place or was set
            aside.
    """
    built = longlist_pinned_plan(conn, task_id=task_id)
    if built is None:
        raise LonglistRefused("no_longlist", "the task has no longlist to shortlist from")
    pinned_plan = built[1]
    if pinned_plan is None or longlist_inputs(plan) != longlist_inputs(pinned_plan):
        raise LonglistRefused(
            "plan_stale",
            "the plan changed since the longlist was built — rebuild the longlist first",
        )
    if not suggest:
        return False
    stored = conn.execute(
        select(longlist_result.c.shortlist)
        .where(longlist_result.c.task_id == task_id)
        .order_by(
            longlist_result.c.created_at.desc(), longlist_result.c.longlist_result_id.desc()
        )
        .limit(1)
    ).scalar_one_or_none()
    provenance = stored.get("provenance") if isinstance(stored, dict) else None
    if shortlist_proposal_stale(provenance if isinstance(provenance, dict) else {}, plan):
        return False
    open_option = conn.execute(
        select(option.c.option_id)
        .where(option.c.task_id == task_id)
        .where(option.c.state == "included")
        .where(option.c.merged_into_option_id.is_(None))
        .where(option.c.shortlist_state.is_(None))
        .limit(1)
    ).scalar_one_or_none()
    if open_option is None:
        raise LonglistRefused(
            "nothing_to_propose",
            "every included option already holds a place or was set aside",
        )
    return True


def open_shortlist_walk(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    backends: RunnerBackends,
    executor: ThreadPoolExecutor,
    user_id: str,
    suggest: bool,
) -> uuid.UUID:
    """Open a shortlist walk on the current approved plan (task 055, P8).

    The longlist walk's shape (:func:`open_longlist_walk`): the same
    admission under the dispatch lock, then a wait for the walk's row. The
    intent record has ``purpose = 'shortlist'`` and, for Suggest more, the
    context ``{"suggest": true}``.

    Args:
        engine: Database engine.
        task_id: The options-scoping task.
        backends: The runner backend bundle.
        executor: The walk executor.
        user_id: The user traces are attributed to.
        suggest: ``True`` for Suggest more (keep the places, fill up to five
            or one more), which re-proposes instead when the stored
            proposal is stale; ``False`` to release Policy Atlas's picks and
            propose again (an appetite change).

    Returns:
        The opened walk's ``capability_run_id``.

    Raises:
        LonglistRefused: ``run_active``, ``capacity``, ``no_plan``,
            ``no_longlist``, ``plan_stale`` or ``nothing_to_propose``.
    """
    admitted = admit_and_mint(
        engine,
        task_id=task_id,
        capacity=executor._max_workers,
        executor=executor,
        backends=backends,
        user_id=user_id,
        shortlist_suggest=suggest,
    )
    try:
        _await_new_run(
            engine,
            task_id=task_id,
            existing_ids=set(),
            capability_run_id=admitted.capability_run_id,
        )
    finally:
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
    """Whether a longlist exists, or is on its way, for one plan version (B3, F2).

    Read from the longlist intent records of that version, not from walk rows:
    a walk still queued on the executor has its record but no row yet, and a
    retried confirm must not mint a second walk beside it. A record counts
    when its walk is running or paused, when it has no walk row yet and was
    minted by this process (still queued), or when a longlist result was
    written under it. A walk that failed or was interrupted without a result
    does not count, so *Build longlist* opens a fresh one.

    Args:
        engine: Database engine.
        task_id: The task.
        plan_id: The plan version.

    Returns:
        ``True`` when that version's longlist is built, building or queued.
    """
    walk_row = (
        select(capability_run.c.capability_run_id)
        .where(capability_run.c.task_id == evidence_scope.c.task_id)
        .where(capability_run.c.evidence_scope_id == evidence_scope.c.evidence_scope_id)
    )
    with engine.connect() as conn:
        found = conn.execute(
            select(evidence_scope.c.evidence_scope_id)
            .where(evidence_scope.c.task_id == task_id)
            .where(evidence_scope.c.purpose == LONGLIST_PURPOSE)
            .where(evidence_scope.c.plan_id == plan_id)
            .where(
                walk_row.where(capability_run.c.status.in_(ACTIVE_WALK_STATUSES)).exists()
                | (
                    ~walk_row.exists()
                    & (evidence_scope.c.created_at >= _PROCESS_STARTED)
                )
                | select(longlist_result.c.longlist_result_id)
                .where(longlist_result.c.task_id == evidence_scope.c.task_id)
                .where(longlist_result.c.evidence_scope_id == evidence_scope.c.evidence_scope_id)
                .exists()
            )
            .limit(1)
        ).scalar_one_or_none()
    return found is not None


def plan_row_of_walk(
    engine: Engine, *, task_id: uuid.UUID, capability_run_id: uuid.UUID
) -> dict[str, Any] | None:
    """The plan version a walk ran, as the opener takes a confirmed version (A10).

    A gate's "Confirm plan and build longlist" confirms the version the
    baseline walk ran; the opener refuses (``plan_stale``) if a newer version
    has been minted since.

    Args:
        engine: Database engine.
        task_id: The task.
        capability_run_id: The walk (the baseline paused at the gate).

    Returns:
        The ``task_plan`` row, or ``None`` when the walk names no plan row.
    """
    with engine.connect() as conn:
        row = conn.execute(
            select(task_plan)
            .select_from(
                task_plan.join(capability_run, capability_run.c.plan_id == task_plan.c.plan_id)
            )
            .where(capability_run.c.task_id == task_id)
            .where(capability_run.c.capability_run_id == capability_run_id)
            .where(task_plan.c.task_id == task_id)
        ).mappings().one_or_none()
    return dict(row) if row is not None else None
