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
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api import continuation
from policy_atlas.api.analytics import Sender, capture_run_started
from policy_atlas.api.app import ApiConflict
from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract import RunCreate, RunOut, RunStageOut
from policy_atlas.api.contract.common import PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX, Page, PageMeta
from policy_atlas.api.deps import (
    get_analytics_sender,
    get_current_user,
    get_engine,
    get_executor,
    get_runner_backends,
    get_settings,
    get_title_backend,
)
from policy_atlas.api.routers.access import accessible_task
from policy_atlas.api.routers.common import (
    active_parentless_walk,
    effective_limits,
    executor_walk,
    parentless_walk,
    run_artefact_id_column,
    run_out,
    run_purpose_column,
    run_scope_context_column,
    walk_pauses,
)
from policy_atlas.api.run_io import ParkIO
from policy_atlas.api.settings import Settings
from policy_atlas.api.titles import TitleWriter, in_background, name_task_from_question
from policy_atlas.core import tracing
from policy_atlas.core.schema import capability_run, task, task_agent_transcript
from policy_atlas.runtime.capability_registry import (
    THEORY_OF_CHANGE,
    expect_toc_plan,
    latest_approved_plan_row,
    validate_plan,
)
from policy_atlas.runtime.option_search import unattended_plan
from policy_atlas.runtime.runner import RunnerBackends, run_plan
from policy_atlas.runtime.scoping_plan import LONGLIST_PURPOSE
from policy_atlas.theory_of_change.store import has_graph

log = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/tasks",
    tags=["runs"],
    dependencies=[Depends(get_current_user)],
)

_dispatch_lock = threading.Lock()
_dispatching_tasks: set[uuid.UUID] = set()
#: The reservations an *add*'s option search holds: they fence
#: their task like any reservation but occupy no executor worker (the search
#: runs on the option-search pool), so capacity leaves them out.
_search_reservations: set[uuid.UUID] = set()


def executor_reservation_tasks() -> set[uuid.UUID]:
    """The reserved tasks whose walk will occupy a worker. Call under ``_dispatch_lock``."""
    return _dispatching_tasks - _search_reservations


def executor_reservations() -> int:
    """The reservations that will occupy an executor worker. Call under ``_dispatch_lock``."""
    return len(executor_reservation_tasks())


def executor_full(conn: Connection, capacity: int | None) -> bool:
    """Whether the walk executor has no free worker. Call under ``_dispatch_lock``.

    Counts running parentless executor walks plus the pending reservations
    against ``capacity`` (``None`` reads as full).
    """
    running = conn.execute(
        select(func.count())
        .select_from(capability_run)
        .where(capability_run.c.status == "running")
        .where(parentless_walk())
        .where(executor_walk())
    ).scalar_one()
    return capacity is None or int(running) + executor_reservations() >= capacity


def user_at_run_cap(conn: Connection, *, user_id: str | None, cap: int | None) -> bool:
    """Whether one person's tasks already hold ``cap`` executor walks (task 064a, Q7).

    Call under ``_dispatch_lock``, right after :func:`executor_full`. Counts
    the running parentless executor walks on tasks the person owns, plus the
    person's tasks in the reservation set. Reservations count because a start
    writes its walk row only after the lock is released: counting rows alone
    would admit any number of simultaneous starts. Call it before the
    caller's own task joins the reservation set, so that task is not counted.
    The cap is on the owner's tasks, so the sites pass the task's owner and a
    collaborator with write access cannot lift it. An administrator owner's
    task-quota exemption and an unlimited run override are resolved by
    :func:`policy_atlas.api.routers.common.effective_limits` before this call.

    Args:
        conn: Open database connection.
        user_id: The task's owner, matched on ``task.owner_user_id``;
            ``None`` (an ownerless task, never reachable from the product)
            is never capped.
        cap: The resolved per-person limit; ``None`` means unlimited.

    Returns:
        ``True`` when the person is at or over the limit.
    """
    if user_id is None or cap is None:
        return False
    running = conn.execute(
        select(func.count())
        .select_from(capability_run.join(task, task.c.task_id == capability_run.c.task_id))
        .where(task.c.owner_user_id == user_id)
        .where(capability_run.c.status == "running")
        .where(parentless_walk())
        .where(executor_walk())
    ).scalar_one()
    reserved_tasks = executor_reservation_tasks()
    reserved = (
        conn.execute(
            select(func.count())
            .select_from(task)
            .where(task.c.task_id.in_(reserved_tasks))
            .where(task.c.owner_user_id == user_id)
        ).scalar_one()
        if reserved_tasks
        else 0
    )
    return int(running) + int(reserved) >= cap


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
            it (task 045); ``None`` lets the runner mint one. A walk whose
            dispatch raises is marked ``interrupted`` by this id only.
    """
    try:
        # Opened inside the executor worker: contextvars do not cross a plain
        # executor.submit. run_plan opens its own session scope per component.
        with tracing.trace_scope(user_id=user_id):
            if capability == THEORY_OF_CHANGE and evidence_scope_id is None:
                # Imported here: the opener imports this module.
                from policy_atlas.api.toc_start import start_scope

                # Start drafts, or (a graph already on the canvas) checks it
                # again in full: the restart rule.
                evidence_scope_id = start_scope(engine, task_id=task_id, plan_row=plan_row)
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
                # payload. Whatever that model is, the runner takes it —
                # narrowing to the Evidence search plan here made a scoping walk
                # impossible to start. A longlist walk (its own
                # intent record passed in) runs unattended: it does not pause.
                # A theory-of-change plan is unattended by its model.
                plan=(
                    unattended_plan(plan_row["payload"])  # type: ignore[arg-type]
                    if evidence_scope_id is not None and capability != THEORY_OF_CHANGE
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
                # Unattended: the baseline recorded its standing
                # default at the gate, so the longlist walk opens here, inline
                # on this worker, the moment the baseline has ended.
                _run_follow_on_longlist(
                    engine,
                    task_id=task_id,
                    capability=capability,
                    backends=backends,
                )
            if capability == THEORY_OF_CHANGE:
                from policy_atlas.api.toc_start import run_toc_sequence

                # Draft → check, inline on this worker.
                run_toc_sequence(
                    engine, task_id=task_id, first_outcome=outcome, backends=backends
                )
    except Exception:
        log.exception("api.run_dispatch_failed", task_id=str(task_id))
        # Only the id this dispatch minted, never a lookup by task: the
        # reservation is dropped once the row exists, and another surface can
        # start a walk on the task in that gap.
        if capability_run_id is not None:
            continuation.mark_interrupted_best_effort(
                engine, task_id=task_id, capability_run_id=capability_run_id
            )
    finally:
        queued = None
        next_id = uuid.uuid4()
        with _dispatch_lock:
            if capability == THEORY_OF_CHANGE:
                # A check queued while this walk ran starts now, on this worker.
                from policy_atlas.api.toc_start import take_queued_check

                try:
                    with engine.begin() as conn:
                        queued = take_queued_check(conn, task_id)
                except Exception:
                    log.exception("api.toc_queue_failed", task_id=str(task_id))
            if queued is None:
                _dispatching_tasks.discard(task_id)
            else:
                # This walk's reservation was given back when its row appeared;
                # the chained check has its own
                # pre-insert window, so reserve again and release on its row.
                _dispatching_tasks.add(task_id)
    if queued is not None:
        scope_id, next_plan_row, next_user = queued
        release_when_open(engine, task_id=task_id, capability_run_id=next_id)
        _dispatch_run(
            engine,
            task_id=task_id,
            capability=capability,
            plan_row=next_plan_row,
            backends=backends,
            user_id=next_user or user_id,
            evidence_scope_id=scope_id,
            capability_run_id=next_id,
        )


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
        # The longlist walk does not pause.
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
    # . The walk still starts either way; the
    # longer window keeps the response truthful for the transient case.
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            rows = conn.execute(
                select(
                    capability_run,
                    run_artefact_id_column(),
                    run_purpose_column(),
                    run_scope_context_column(),
                )
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
    titles: Annotated[TitleWriter, Depends(get_title_backend)],
    analytics: Annotated[Sender | None, Depends(get_analytics_sender)],
) -> RunOut:
    """Dispatch an approved plan off the request path and return its walk row.

    Starting a theory of change also names the task from the plan's question,
    unless the user has named it (task 058, round 14, as Evidence search and
    options scoping name theirs when the question part is confirmed). Its
    Task Agent has no question part: Start is where the user confirms the
    question, and the plan is fixed once the draft exists (S7).
    """
    toc_question: str | None = None
    with _dispatch_lock:
        with engine.begin() as conn:
            access = accessible_task(
                conn, task_id=task_id, user_id=user.user_id, write=True, for_update=True
            )
            # Parentless walks only: a longlist walk's option
            # searches never fence a user action — their parent does. No
            # option search counts against the executor, whose workers they
            # do not occupy (they run on the option-search pool) — not even
            # an *add*'s parentless one, which still fences its task.
            if active_parentless_walk(conn, task_id) is not None or task_id in _dispatching_tasks:
                raise ApiConflict("run_active", "the task already has an active run")
            if executor_full(conn, settings.run_executor_max):
                raise ApiConflict("capacity", "the walk executor is at capacity")
            cap = effective_limits(
                conn, access.row["owner_user_id"], settings=settings
            ).runs
            if user_at_run_cap(conn, user_id=access.row["owner_user_id"], cap=cap):
                raise ApiConflict(
                    "user_capacity", f"you already have {cap} runs in progress"
                )
            plan_row = latest_approved_plan_row(conn, task_id)
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
            # Once a theory of change has a graph, no turn changes its plan
            # , so a later turn does not make it stale.
            if (
                approved_plan.source_turn_index is not None
                and latest_completed_turn is not None
                and approved_plan.source_turn_index < latest_completed_turn
                and not (
                    access.row["capability"] == THEORY_OF_CHANGE and has_graph(conn, task_id)
                )
            ):
                raise ApiConflict(
                    "plan_stale",
                    "the plan predates your latest Task Agent message — review it, then start",
                )
            if access.row["capability"] == THEORY_OF_CHANGE:
                toc_question = expect_toc_plan(approved_plan).question
            _dispatching_tasks.add(task_id)
        walk_id = uuid.uuid4()
        executor.submit(
            _dispatch_run,
            engine,
            task_id=task_id,
            capability=access.row["capability"],
            plan_row=dict(plan_row),
            backends=backends,
            user_id=user.user_id,
            capability_run_id=walk_id,
        )
    try:
        created = _await_new_run(
            engine, task_id=task_id, existing_ids=set(), capability_run_id=walk_id
        )
    finally:
        # Once the runtime row exists, the database's ``running`` count owns
        # capacity accounting; keeping the launch reservation would double-count.
        # A Start whose row never came gives it back too, so the task is not
        # fenced until the server restarts.
        with _dispatch_lock:
            _dispatching_tasks.discard(task_id)
    if toc_question is not None:
        question = toc_question

        def _name_task() -> None:
            # Under the user's scope, opened in the new thread as the Task
            # Agent turn's naming does (context variables do not cross a
            # thread start). A restart with the same question makes no call.
            with tracing.trace_scope(user_id=user.user_id):
                name_task_from_question(engine, titles, task_id=task_id, question=question)

        # Only once the walk's row exists: a Start that fails names nothing.
        in_background(_name_task, name=f"policy-atlas-task-title-{task_id}")
    # In-app feedback analytics: only once the run exists.
    capture_run_started(analytics, user_id=user.user_id, task_id=task_id)
    return created


@router.get("/{task_id}/runs", response_model=Page[RunOut])
def list_runs(
    task_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
    parentless: bool = False,
) -> Page[RunOut]:
    """List a task's walks from newest to oldest (paginated — runs accumulate).

    ``parentless`` (task 045, A13) keeps only the walks with no parent that
    are not option searches — the baseline and longlist walks — so a reader
    looking for the baseline never pages through option searches.
    """
    where = [capability_run.c.task_id == task_id]
    if parentless:
        where += [parentless_walk(), executor_walk()]
    with engine.connect() as conn:
        accessible_task(conn, task_id=task_id, user_id=user.user_id, write=False)
        total = conn.execute(
            select(func.count()).select_from(capability_run).where(*where)
        ).scalar_one()
        rows = conn.execute(
            select(
                capability_run,
                run_artefact_id_column(),
                run_purpose_column(),
                run_scope_context_column(),
            )
            .where(*where)
            .order_by(capability_run.c.started_at.desc(), capability_run.c.capability_run_id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).mappings().all()
        walk_ids = [row["capability_run_id"] for row in rows]
        stages = _walk_stages(conn, task_id, walk_ids)
        pauses = walk_pauses(conn, task_id=task_id, walk_ids=walk_ids)
    return Page(
        data=[
            run_out(row).model_copy(
                update={
                    "stages": stages.get(row["capability_run_id"], []),
                    "paused_seconds": pauses.get(row["capability_run_id"], 0),
                }
            )
            for row in rows
        ],
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
            select(
                capability_run,
                run_artefact_id_column(),
                run_purpose_column(),
                run_scope_context_column(),
            )
            .where(capability_run.c.task_id == task_id)
            .where(capability_run.c.capability_run_id == run_id)
        ).mappings().one_or_none()
        stages = _walk_stages(conn, task_id, [run_id]) if row is not None else {}
        pauses = walk_pauses(conn, task_id=task_id, walk_ids=[run_id]) if row is not None else {}
    if row is None:
        raise HTTPException(status_code=404, detail="resource not found")
    return run_out(row).model_copy(
        update={"stages": stages.get(run_id, []), "paused_seconds": pauses.get(run_id, 0)}
    )


def _walk_stages(
    conn: Connection, task_id: uuid.UUID, walk_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[RunStageOut]]:
    """Each walk's own steps, as the stream told them (task 058, round 11)."""
    # Imported here: the stream router imports the task-agent router, which
    # reaches this module through the longlist start.
    from policy_atlas.api.routers.sse import walk_stages

    return walk_stages(conn, task_id=task_id, walk_ids=walk_ids)


def start_toc_check(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    link_ids: list[uuid.UUID],
    user_id: str,
    settings: Settings,
    executor: ThreadPoolExecutor,
    backends: RunnerBackends,
    mode: str = "new_items",
    studies: dict[str, list[str]] | None = None,
) -> uuid.UUID | None:
    """Start a check walk named on links (task 054, C40), as Start does for a whole walk.

    The caller has checked the write grade. While the task has a walk, the
    check is queued and starts when that walk ends (``_dispatch_run``).

    Returns:
        The new walk's id, or ``None`` when the check was queued.

    Raises:
        ApiConflict: ``capacity`` or ``user_capacity``.
        HTTPException: 400 when the task has no approved plan.
    """
    # Imported here: the opener imports this module.
    from policy_atlas.api.toc_start import mint_scope, queue_check
    from policy_atlas.runtime.toc_plan import TOC_WALK_CHECK

    walk_id = uuid.uuid4()
    with _dispatch_lock:
        with engine.begin() as conn:
            plan_row = latest_approved_plan_row(conn, task_id)
            if plan_row is None:
                raise HTTPException(status_code=400, detail="no approved plan")
            if active_parentless_walk(conn, task_id) is not None or task_id in _dispatching_tasks:
                # A walk is running: this check waits and starts when it ends.
                queue_check(
                    conn,
                    task_id=task_id,
                    link_ids=[str(link_id) for link_id in link_ids],
                    mode=mode,
                    studies=studies,
                    user_id=user_id,
                )
                return None
            if executor_full(conn, settings.run_executor_max):
                raise ApiConflict("capacity", "the walk executor is at capacity")
            owner = conn.execute(
                select(task.c.owner_user_id).where(task.c.task_id == task_id)
            ).scalar_one()
            cap = effective_limits(conn, owner, settings=settings).runs
            if user_at_run_cap(conn, user_id=owner, cap=cap):
                raise ApiConflict(
                    "user_capacity", f"you already have {cap} runs in progress"
                )
            scope_id = mint_scope(
                conn,
                task_id=task_id,
                plan_row=plan_row,
                toc_walk=TOC_WALK_CHECK,
                links=[str(link_id) for link_id in link_ids],
                mode=mode,
                started_by=user_id,
                studies=studies,
            )
            _dispatching_tasks.add(task_id)
        executor.submit(
            _dispatch_run,
            engine,
            task_id=task_id,
            capability=THEORY_OF_CHANGE,
            plan_row=dict(plan_row),
            backends=backends,
            user_id=user_id,
            evidence_scope_id=scope_id,
            capability_run_id=walk_id,
        )
    # Give the reservation back once the row exists, as the other start
    # surfaces do; held for the whole check it counted twice against both
    # caps.
    release_when_open(engine, task_id=task_id, capability_run_id=walk_id)
    return walk_id
