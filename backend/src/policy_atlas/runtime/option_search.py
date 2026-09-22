"""The option search: a tool whose implementation is a child walk (task 045, S2).

ADR 0039 decision 3. :func:`run_option_search` takes one entrant's specified
design — **its only input** (D26): the queries are generated inside the walk by
the acquire component from the intent, as the Evidence search generates them —
inserts a ``targeted`` intent record whose intent is ``design.as_intent()``,
mints the child walk's ``capability_run_id`` and submits ``run_plan`` for it to
the option-search pool (:mod:`policy_atlas.runtime.walk_pool`). It returns the
id at once; nothing polls for the row (P2).

Two callers: the longlist walk's runner-level fan-out after ``suggest``
(:func:`dispatch_option_searches`, with the walk as parent) and the chat verb
*add* (task 045 Phase 7, ``parent_capability_run_id=None``).

The runner's two barriers live here beside the tool, because the runner holds
the engine, the backend bundle and the walk's identity and a harness component
holds none of them (P1):

- :func:`dispatch_option_searches` — after ``suggest``: read the entrants,
  apply the cap (the user's own and the report-derived first, never dropped;
  the model's suggestions fill the rest), skip on a rebuild every entrant that
  already has an option search (P12), dispatch one child walk each, and emit
  the ``option_searches`` stage's start.
- :func:`join_option_searches` — before ``longlist``: wait, outside any
  transaction, for every child to reach a terminal status, bounded by
  :data:`OPTION_SEARCH_JOIN_TIMEOUT`; stragglers are marked ``interrupted``
  and counted failed; emit the stage's completion with
  ``{total, finished, failed}``.

**Finding a walk's children** (for Phase 5 and any reader):
``capability_run.parent_capability_run_id = <the longlist walk>``; each
child's intent record is ``evidence_scope`` with ``purpose = 'targeted'`` and
``context->>'option_id'`` naming the option (:func:`child_walks`).
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Mapping
from concurrent.futures import Future
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.engine import Connection, Engine

from policy_atlas.core import events, tracing
from policy_atlas.core.schema import capability_run, event_log, evidence_scope, option
from policy_atlas.options_scoping.design import OptionDesign
from policy_atlas.runtime.capability_registry import OPTIONS_SCOPING, validate_plan
from policy_atlas.runtime.scoping_plan import (
    BASELINE_CONFIRM,
    OPTION_SEARCH_CAP,
    TARGETED_PURPOSE,
    ScopingPlan,
)
from policy_atlas.runtime.walk_pool import option_search_pool

if TYPE_CHECKING:
    from policy_atlas.runtime.runner import RunnerBackends

log = structlog.get_logger()

#: The stage key both barriers emit under (Phase 4.4 maps it to a frame).
OPTION_SEARCHES_STAGE = "option_searches"

#: How long the longlist walk waits for its option searches, counted from the
#: join (the parent's own broad chain has already run by then). Fifteen
#: option searches at width 4 are four waves of one small walk each (acquire
#: at 10 per backend → screen → classify → appraise → ingest → profile); half
#: an hour leaves room for a slow wave without letting a stuck child hold the
#: longlist forever. After it, the remaining children are marked
#: ``interrupted`` and counted as failed entrants.
OPTION_SEARCH_JOIN_TIMEOUT = 1800.0

#: How often the join re-reads the children's statuses.
OPTION_SEARCH_JOIN_POLL = 0.5

#: The entrant origins in the cap's keep order: these two are never dropped.
_KEPT_ORIGINS = ("added_by_you", "from_evidence_search")
_SUGGESTED_ORIGIN = "suggested"
_ENTRANT_ORIGINS = (*_KEPT_ORIGINS, _SUGGESTED_ORIGIN)

#: Child statuses that end a child walk, and which of them count as finished.
_TERMINAL = frozenset({"succeeded", "degraded", "failed", "aborted", "interrupted"})
_FINISHED = frozenset({"succeeded", "degraded"})

# The in-process handles on submitted children: a join that times out
# cancels a child still queued behind the pool's width, and a child the
# join abandoned before it opened its row never starts.
_futures: dict[uuid.UUID, Future[None]] = {}
_abandoned: set[uuid.UUID] = set()
_handles_lock = threading.Lock()


@dataclass(frozen=True)
class JoinOutcome:
    """What the join found.

    Args:
        total: Children the fan-out dispatched.
        finished: Children that ended ``succeeded`` or ``degraded``.
        failed: Children that ended any other way, stragglers included.
        interrupted: The stragglers the timeout marked ``interrupted``.
    """

    total: int
    finished: int
    failed: int
    interrupted: tuple[uuid.UUID, ...] = ()


def run_option_search(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    plan_row: Mapping[str, Any],
    design: OptionDesign,
    option_id: uuid.UUID,
    parent_capability_run_id: uuid.UUID | None,
    backends: RunnerBackends,
    user_id: str | None,
) -> uuid.UUID:
    """Start one option search and return its child walk's id at once.

    In one transaction, inserts the targeted intent record (``purpose =
    'targeted'``, ``intent = design.as_intent()``, ``plan_id`` = the confirmed
    version, ``context.option_id`` naming the option) and mints the child's
    ``capability_run_id``; then submits the child walk to the option-search
    pool. The walk's own row is written by the runner when the pool starts it.

    Args:
        engine: Database engine.
        task_id: The options-scoping task.
        plan_row: The confirmed plan version: ``plan_id``, ``version`` and
            ``payload`` (the scoping plan's dump).
        design: The entrant's specified design — the tool's only input (D26).
        option_id: The option the search is for.
        parent_capability_run_id: The longlist walk that asked, or ``None``
            for the chat verb *add* (a child walk with no parent).
        backends: The runner backend bundle the child walk runs with.
        user_id: The user to attribute traces to, or ``None`` to inherit the
            caller's trace context (the runner's fan-out).

    Returns:
        The child walk's ``capability_run_id``.
    """
    plan = unattended_plan(plan_row["payload"])
    plan_id = uuid.UUID(str(plan_row["plan_id"]))
    plan_version = int(plan_row["version"])
    scope_id = uuid.uuid4()
    child_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            evidence_scope.insert().values(
                evidence_scope_id=scope_id,
                task_id=task_id,
                intent=design.as_intent(),
                context={"capability": OPTIONS_SCOPING, "option_id": str(option_id)},
                created_at=datetime.now(UTC),
                purpose=TARGETED_PURPOSE,
                plan_id=plan_id,
            )
        )
    with _handles_lock:
        future = tracing.submit_with_context(
            option_search_pool(),
            _run_child,
            engine,
            task_id=task_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=plan_version,
            evidence_scope_id=scope_id,
            capability_run_id=child_id,
            parent_capability_run_id=parent_capability_run_id,
            backends=backends,
            user_id=user_id,
        )
        _futures[child_id] = future
    future.add_done_callback(lambda _done: _forget(child_id))
    log.info(
        "option_search.dispatched",
        task_id=str(task_id),
        option_id=str(option_id),
        capability_run_id=str(child_id),
        parent_capability_run_id=(
            str(parent_capability_run_id) if parent_capability_run_id is not None else None
        ),
    )
    return child_id


def unattended_plan(payload: Mapping[str, Any]) -> ScopingPlan:
    """Return the plan a longlist walk or an option search runs: unattended.

    Neither walk pauses (contract D1: "the walk does not pause"; ADR 0039
    decision 5: a child never opens or locks a tab). Run under the plan's
    attended mode, a
    fired floor trigger — a classification mix collapse on a ten-document
    search is the common one — would park the walk with the check-in IO (and
    ``frequent`` would park it after every step). Unattended, the same
    boundary is recorded and flagged as a standing proceed, and the walk runs
    on. The plan row itself is not changed; the baseline gate's standing
    default is declared only because an unattended scoping plan must carry
    one (neither chain reaches the gate). The baseline walk never runs under
    this plan.

    Args:
        payload: The confirmed plan version's payload.

    Returns:
        The validated plan with ``steering_mode = 'unattended'``.
    """
    data = dict(validate_plan(OPTIONS_SCOPING, payload).model_dump(mode="json"))
    data["steering_mode"] = "unattended"
    data["steer_point_defaults"] = [
        {"steer_point": BASELINE_CONFIRM, "action": "proceed_flag"}
    ]
    plan = validate_plan(OPTIONS_SCOPING, data)
    assert isinstance(plan, ScopingPlan)
    return plan


def _forget(child_id: uuid.UUID) -> None:
    with _handles_lock:
        _futures.pop(child_id, None)
        _abandoned.discard(child_id)


def _run_child(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    plan: Any,
    plan_id: uuid.UUID,
    plan_version: int,
    evidence_scope_id: uuid.UUID,
    capability_run_id: uuid.UUID,
    parent_capability_run_id: uuid.UUID | None,
    backends: RunnerBackends,
    user_id: str | None,
) -> None:
    """Run one child walk on an option-search pool worker."""
    with _handles_lock:
        if capability_run_id in _abandoned:
            log.info(
                "option_search.abandoned_before_start",
                capability_run_id=str(capability_run_id),
            )
            return
    # Imported here: the runner imports this module, and ``api.run_io``
    # imports the runner.
    from policy_atlas.api.run_io import ParkIO
    from policy_atlas.runtime.runner import run_plan

    try:
        with tracing.trace_scope(user_id=user_id):
            run_plan(
                engine,
                task_id=task_id,
                evidence_scope_id=evidence_scope_id,
                plan=plan,
                plan_id=plan_id,
                plan_version=plan_version,
                plan_row_id=plan_id,
                backends=backends,
                io=ParkIO(),
                session_id=task_id,
                capability_run_id=capability_run_id,
                parent_capability_run_id=parent_capability_run_id,
            )
    except Exception:
        # A raise outside the runner's own handling would leave the child
        # ``running`` forever and hold the join to its timeout.
        log.exception(
            "option_search.child_raised",
            task_id=str(task_id),
            capability_run_id=str(capability_run_id),
        )
        _end_child(engine, task_id=task_id, child_id=capability_run_id, status="failed")


def _end_child(
    engine: Engine, *, task_id: uuid.UUID, child_id: uuid.UUID, status: str
) -> bool:
    """Mark one still-active child walk terminal, with its lifecycle event.

    Returns:
        Whether a row changed (``False`` when the child has no row yet or has
        already ended).
    """
    with engine.begin() as conn:
        changed = conn.execute(
            update(capability_run)
            .where(capability_run.c.task_id == task_id)
            .where(capability_run.c.capability_run_id == child_id)
            .where(capability_run.c.status.in_(("running", "paused")))
            .values(status=status, ended_at=datetime.now(UTC))
        ).rowcount
        if changed:
            event_type = "run.interrupted" if status == "interrupted" else "run.finished"
            payload: dict[str, Any] = {"capability_run_id": str(child_id)}
            if event_type == "run.finished":
                payload["status"] = status
            events.append(
                conn, task_id=task_id, run_id=None, event_type=event_type, payload=payload
            )
    return bool(changed)


# --- the runner's two barriers ----------------------------------------------


def entrants_for_search(
    conn: Connection, *, task_id: uuid.UUID, suggest_run_id: uuid.UUID | None
) -> list[tuple[uuid.UUID, OptionDesign]]:
    """Return the entrants the fan-out searches for, capped, in keep order.

    The entrants are the ``suggest`` step's summary ``entrants`` (the user's
    own, then the report's, then the model's). When ``suggest`` failed there
    is no summary; the plan's own options (``origin = 'added_by_you'``) still
    exist and are the entrants. **Rebuild** (P12): an entrant that already has
    an option search on this task — a walk under a ``targeted`` record whose
    ``context.option_id`` names it — is not searched again. The cap
    (:data:`OPTION_SEARCH_CAP`, A16) keeps every ``added_by_you`` and
    ``from_evidence_search`` entrant and fills the rest with suggestions; an
    entrant whose stored design does not validate is skipped and logged.

    Args:
        conn: Open connection.
        task_id: The task.
        suggest_run_id: The walk's successful ``suggest`` run, or ``None``.

    Returns:
        ``(option_id, design)`` pairs to search for.
    """
    ordered: list[uuid.UUID] | None = None
    if suggest_run_id is not None:
        ordered = _summary_entrants(conn, task_id=task_id, suggest_run_id=suggest_run_id)
    if ordered is None:
        ordered = list(
            conn.execute(
                select(option.c.option_id)
                .where(option.c.task_id == task_id)
                .where(option.c.origin == "added_by_you")
                .order_by(option.c.created_at, option.c.option_id)
            ).scalars()
        )
    if not ordered:
        return []
    rows = {
        row.option_id: row
        for row in conn.execute(
            select(option.c.option_id, option.c.origin, option.c.design)
            .where(option.c.task_id == task_id)
            .where(option.c.option_id.in_(ordered))
            .where(option.c.origin.in_(_ENTRANT_ORIGINS))
        )
    }
    searched = searched_option_ids(conn, task_id=task_id)
    kept: list[tuple[uuid.UUID, OptionDesign]] = []
    suggested: list[tuple[uuid.UUID, OptionDesign]] = []
    for option_id in ordered:
        row = rows.get(option_id)
        if row is None or option_id in searched:
            continue
        try:
            design = OptionDesign.model_validate(row.design)
        except ValidationError:
            log.warning(
                "option_search.entrant_design_invalid",
                task_id=str(task_id),
                option_id=str(option_id),
            )
            continue
        (kept if row.origin in _KEPT_ORIGINS else suggested).append((option_id, design))
    return kept + suggested[: max(0, OPTION_SEARCH_CAP - len(kept))]


def _summary_entrants(
    conn: Connection, *, task_id: uuid.UUID, suggest_run_id: uuid.UUID
) -> list[uuid.UUID] | None:
    """Read ``entrants`` off the suggest run's completed summary (Phase 4.2)."""
    payload = next(
        (
            entry["payload"]
            for entry in reversed(events.read_for_run(conn, task_id, suggest_run_id))
            if entry["event_type"] == "component.completed"
            and isinstance(entry["payload"], dict)
            and entry["payload"].get("component") == "suggest"
        ),
        None,
    )
    if payload is None or not isinstance(payload.get("entrants"), list):
        return None
    return [uuid.UUID(str(value)) for value in payload["entrants"]]


def searched_option_ids(conn: Connection, *, task_id: uuid.UUID) -> set[uuid.UUID]:
    """Return the options of a task that already have an option search.

    An option search is a walk under a ``targeted`` intent record whose
    ``context.option_id`` names the option, whatever the walk's status.

    Args:
        conn: Open connection.
        task_id: The task.

    Returns:
        The option ids.
    """
    values = conn.execute(
        select(evidence_scope.c.context["option_id"].astext)
        .select_from(
            evidence_scope.join(
                capability_run,
                (capability_run.c.evidence_scope_id == evidence_scope.c.evidence_scope_id)
                & (capability_run.c.task_id == evidence_scope.c.task_id),
            )
        )
        .where(evidence_scope.c.task_id == task_id)
        .where(evidence_scope.c.purpose == TARGETED_PURPOSE)
    ).scalars()
    found: set[uuid.UUID] = set()
    for value in values:
        try:
            found.add(uuid.UUID(str(value)))
        except (TypeError, ValueError):
            continue
    return found


def child_walks(
    conn: Connection, *, task_id: uuid.UUID, parent_id: uuid.UUID
) -> dict[uuid.UUID, str]:
    """Return a walk's child walks and their statuses.

    Args:
        conn: Open connection.
        task_id: The task.
        parent_id: The longlist walk.

    Returns:
        ``capability_run_id`` → status, for every child that has opened its row.
    """
    return {
        row.capability_run_id: row.status
        for row in conn.execute(
            select(capability_run.c.capability_run_id, capability_run.c.status)
            .where(capability_run.c.task_id == task_id)
            .where(capability_run.c.parent_capability_run_id == parent_id)
        )
    }


def dispatched_children(
    conn: Connection, *, task_id: uuid.UUID, parent_id: uuid.UUID
) -> list[uuid.UUID] | None:
    """Return the children a walk's fan-out already dispatched, if it ran.

    The fan-out's stage-start event is the durable record that it ran (a
    parked-and-resumed walk must not fan out twice).

    Returns:
        The child ids in dispatch order, or ``None`` when no fan-out ran.
    """
    rows = conn.execute(
        select(event_log.c.payload)
        .where(event_log.c.task_id == task_id)
        .where(event_log.c.run_id.is_(None))
        .where(event_log.c.event_type == "run.started")
        .where(event_log.c.payload["component"].astext == OPTION_SEARCHES_STAGE)
        .where(event_log.c.payload["capability_run_id"].astext == str(parent_id))
        .order_by(event_log.c.sequence.desc())
        .limit(1)
    ).scalars()
    payload = next(iter(rows), None)
    if not isinstance(payload, dict):
        return None
    return [uuid.UUID(str(value)) for value in payload.get("child_capability_run_ids", [])]


def dispatch_option_searches(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    parent_id: uuid.UUID,
    plan_row: Mapping[str, Any],
    suggest_run_id: uuid.UUID | None,
    backends: RunnerBackends,
    session_id: uuid.UUID | None,
) -> list[uuid.UUID]:
    """The fan-out barrier: one child walk per entrant, after ``suggest``.

    Idempotent across a park: a fan-out that already ran returns the children
    it dispatched.

    Args:
        engine: Database engine.
        task_id: The task.
        parent_id: The longlist walk.
        plan_row: The walk's confirmed plan version (``plan_id``, ``version``,
            ``payload``).
        suggest_run_id: The walk's successful ``suggest`` run, or ``None``.
        backends: The runner backend bundle, passed to every child.
        session_id: The walk's tracing session, recorded on the stage event.

    Returns:
        The child walks' ids, in dispatch order.
    """
    with engine.connect() as conn:
        already = dispatched_children(conn, task_id=task_id, parent_id=parent_id)
        if already is not None:
            return already
        entrants = entrants_for_search(conn, task_id=task_id, suggest_run_id=suggest_run_id)
    child_ids = [
        run_option_search(
            engine,
            task_id=task_id,
            plan_row=plan_row,
            design=design,
            option_id=option_id,
            parent_capability_run_id=parent_id,
            backends=backends,
            user_id=None,
        )
        for option_id, design in entrants
    ]
    with engine.begin() as conn:
        events.append(
            conn,
            task_id=task_id,
            run_id=None,
            event_type="run.started",
            payload={
                "component": OPTION_SEARCHES_STAGE,
                "registry_component": OPTION_SEARCHES_STAGE,
                "plan_id": str(plan_row["plan_id"]),
                "plan_version": int(plan_row["version"]),
                "session_id": str(session_id) if session_id is not None else None,
                "capability_run_id": str(parent_id),
                "child_capability_run_ids": [str(child) for child in child_ids],
                "total": len(child_ids),
            },
        )
    log.info(
        "option_search.fan_out",
        task_id=str(task_id),
        capability_run_id=str(parent_id),
        total=len(child_ids),
    )
    return child_ids


def join_option_searches(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    parent_id: uuid.UUID,
    child_ids: list[uuid.UUID],
    timeout: float | None = None,
) -> JoinOutcome:
    """The join barrier: wait for every child, outside any transaction.

    Polls the children's statuses (each read is its own short connection)
    until every child is terminal or the timeout passes. A child with no row
    counts as ended when its pool job is no longer pending (it raised before
    opening, or the process that submitted it is gone). At the timeout, a
    straggler with a row is marked ``interrupted``; one still queued is
    cancelled or abandoned so it never starts. Emits the stage's completion.

    Args:
        engine: Database engine.
        task_id: The task.
        parent_id: The longlist walk.
        child_ids: The children the fan-out dispatched.
        timeout: Seconds to wait; ``None`` uses :data:`OPTION_SEARCH_JOIN_TIMEOUT`.

    Returns:
        The counts.
    """
    deadline = time.monotonic() + (OPTION_SEARCH_JOIN_TIMEOUT if timeout is None else timeout)
    statuses: dict[uuid.UUID, str] = {}
    pending: list[uuid.UUID] = list(child_ids)
    while True:
        with engine.connect() as conn:
            statuses = child_walks(conn, task_id=task_id, parent_id=parent_id)
        pending = [child for child in child_ids if not _ended(child, statuses.get(child))]
        if not pending or time.monotonic() >= deadline:
            break
        time.sleep(OPTION_SEARCH_JOIN_POLL)
    interrupted: list[uuid.UUID] = []
    for child in pending:
        with _handles_lock:
            future = _futures.get(child)
            if future is not None and not future.cancel():
                _abandoned.add(child)
        if _end_child(engine, task_id=task_id, child_id=child, status="interrupted"):
            interrupted.append(child)
        statuses[child] = "interrupted"
    finished = sum(1 for child in child_ids if statuses.get(child) in _FINISHED)
    outcome = JoinOutcome(
        total=len(child_ids),
        finished=finished,
        failed=len(child_ids) - finished,
        interrupted=tuple(interrupted),
    )
    with engine.begin() as conn:
        events.append(
            conn,
            task_id=task_id,
            run_id=None,
            event_type="component.completed",
            payload={
                "component": OPTION_SEARCHES_STAGE,
                "total": outcome.total,
                "finished": outcome.finished,
                "failed": outcome.failed,
            },
        )
    log.info(
        "option_search.joined",
        task_id=str(task_id),
        capability_run_id=str(parent_id),
        total=outcome.total,
        finished=outcome.finished,
        failed=outcome.failed,
        interrupted=len(outcome.interrupted),
    )
    return outcome


def _ended(child: uuid.UUID, status: str | None) -> bool:
    if status is not None:
        return status in _TERMINAL
    with _handles_lock:
        future = _futures.get(child)
    return future is None or future.done()
