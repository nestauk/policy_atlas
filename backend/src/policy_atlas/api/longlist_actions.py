"""The user's three direct actions on the longlist (task 045, S11, S12; D13).

*Add an option*, *exclude* and *include again* are one set of apply
functions with two callers: the buttons (``api/routers/longlist.py``) and the
Task Agent's longlist verbs (Phase 7), which confirm a verb in the thread and
then call the same function. Each writes the option's state **and one History
event as the user's turn** (contract deliverable 9, ruling 1): an
``event_log`` row with ``run_id = None`` and the actor in the payload, which
``GET /decisions`` renders with ``decided_by = "user"`` beside the lifecycle
events (the precedent is the rename and share audit events).

**User state always wins** (5.3's rule, ``options_scoping.constrain.constrain.
user_holds_state``): both *exclude* and *include again* write an
``exclusion`` record with ``by = "user"`` — on an included row it is the
marker that stops a rebuild's ``constrain`` from excluding it again, and the
read models show ``exclusion`` only while the option is excluded. Nothing
here is an annotation row.

**The fence.** Every action refuses while a parentless walk is running or
paused (``run_active``, the admission rule of ``POST /runs``): a longlist walk
building or rebuilding owns the option rows, and an *add*'s own option search
is a parentless walk, so one add blocks the next until its search ends. A
child walk never blocks (ADR 0039 decision 5).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.app import ApiConflict
from policy_atlas.api.locks import task_lock
from policy_atlas.api.readmodels.repository import (
    OPTION_ADDED,
    OPTION_EXCLUDED,
    OPTION_INCLUDED,
)
from policy_atlas.api.routers._common import ACTIVE_WALK_STATUSES, parentless_walk
from policy_atlas.api.routers.runs import (
    _await_new_run,
    _dispatch_lock,
    _dispatching_tasks,
)
from policy_atlas.core import events
from policy_atlas.core.schema import capability_run, option, task_plan
from policy_atlas.options_scoping.design import OptionDesign
from policy_atlas.runtime.agent_backend import AgentBackend
from policy_atlas.runtime.capability_registry import (
    OPTIONS_SCOPING,
    capability_of_task,
    validate_plan,
)
from policy_atlas.runtime.option_search import run_option_search
from policy_atlas.runtime.runner import RunnerBackends
from policy_atlas.runtime.scoping_plan import ScopingPlan

log = structlog.get_logger()

#: The ``constraint`` a user's exclusion names (the card reads "excluded:
#: your decision").
USER_DECISION = "your decision"


class LonglistActionRefused(Exception):
    """A longlist action the task's state does not allow.

    Args:
        reason: ``not_scoping`` (an Evidence search task) · ``run_active`` (a
            parentless walk is running or paused) · ``no_plan`` (no approved
            scoping plan to search an added option against).
        message: A sentence for the error body.
    """

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


class OptionNotFound(LookupError):
    """The task holds no such option."""


def http_error(refusal: LonglistActionRefused) -> Exception:
    """Map a refusal onto the error a route raises.

    Args:
        refusal: The action's refusal.

    Returns:
        ``ApiConflict("run_active")`` for a walk the user can wait out; a
        ``422`` for a task the action does not apply to.
    """
    if refusal.reason == "run_active":
        return ApiConflict("run_active", refusal.message)
    return HTTPException(status_code=422, detail=refusal.message)


def _refuse_unless_open(conn: Connection, *, task_id: uuid.UUID, reserved: bool) -> None:
    if capability_of_task(conn, task_id) != OPTIONS_SCOPING:
        raise LonglistActionRefused(
            "not_scoping", "options belong to options-scoping tasks only"
        )
    active = conn.execute(
        select(capability_run.c.capability_run_id)
        .where(capability_run.c.task_id == task_id)
        .where(capability_run.c.status.in_(ACTIVE_WALK_STATUSES))
        .where(parentless_walk())
        .limit(1)
    ).scalar_one_or_none()
    if active is not None or reserved:
        raise LonglistActionRefused(
            "run_active", "a run is in progress; wait for it to finish, then change the longlist"
        )


def admit_longlist_action(conn: Connection, *, task_id: uuid.UUID) -> None:
    """Refuse an action on an Evidence search task or while a parentless walk is active.

    Call under the task row lock (the caller's transaction).

    Args:
        conn: The caller's open transaction, holding the task row lock.
        task_id: The task.

    Raises:
        LonglistActionRefused: ``not_scoping`` or ``run_active``.
    """
    # Read without ``_dispatch_lock``: the caller holds the task row lock, and
    # the openers take the dispatch lock *then* the row lock — taking it here
    # would invert that order. A set-membership read is atomic under the GIL,
    # and a reservation is only ever held while its walk's row is on the way.
    _refuse_unless_open(conn, task_id=task_id, reserved=task_id in _dispatching_tasks)


def _locked_option(conn: Connection, *, task_id: uuid.UUID, option_id: uuid.UUID) -> Any:
    row = conn.execute(
        select(option)
        .where(option.c.task_id == task_id, option.c.option_id == option_id)
        .with_for_update()
    ).one_or_none()
    if row is None:
        raise OptionNotFound(f"unknown option: {option_id}")
    return row


def _clean_reason(reason: str | None) -> str | None:
    if reason is None:
        return None
    text = " ".join(reason.split())
    return text or None


def _event(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    event_type: str,
    actor: str,
    row: Any,
    verb: str,
    reason: str | None,
    extra: dict[str, Any] | None = None,
) -> None:
    events.append(
        conn,
        task_id=task_id,
        run_id=None,
        event_type=event_type,
        payload={
            "actor": actor,
            "verb": verb,
            "option_id": str(row.option_id),
            "option_name": row.name,
            "reason": reason,
            **(extra or {}),
        },
    )


def exclude_option(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    option_id: uuid.UUID,
    reason: str | None,
    actor: str,
    require_reason: bool = True,
) -> None:
    """Exclude an option with the user's reason, and log it as the user's turn.

    Writes ``state = "excluded"`` and ``exclusion = {constraint: "your
    decision", reason, by: "user"}`` — reversible by :func:`include_option`,
    and never overridden by a rebuild's ``constrain``.

    Args:
        conn: The caller's open transaction, holding the task row lock.
        task_id: The options-scoping task.
        option_id: The option.
        reason: Why, in the user's words.
        actor: The user (token subject) the History event names.
        require_reason: ``False`` for the Task Agent's verb *exclude*, whose
            proposal the user confirmed with "Reason: none given" showing —
            the reason is then recorded empty (the shape *include again*
            writes), never invented. The button always requires one.

    Raises:
        LonglistActionRefused: ``not_scoping`` or ``run_active``.
        OptionNotFound: If the task holds no such option.
        ValueError: If the reason is blank and one is required.
    """
    admit_longlist_action(conn, task_id=task_id)
    row = _locked_option(conn, task_id=task_id, option_id=option_id)
    text = _clean_reason(reason)
    if text is None and require_reason:
        raise ValueError("an exclusion needs a reason")
    conn.execute(
        option.update()
        .where(option.c.task_id == task_id, option.c.option_id == option_id)
        .values(
            state="excluded",
            exclusion={"constraint": USER_DECISION, "reason": text or "", "by": "user"},
            updated_at=datetime.now(UTC),
        )
    )
    _event(
        conn,
        task_id=task_id,
        event_type=OPTION_EXCLUDED,
        actor=actor,
        row=row,
        verb="exclude",
        reason=text,
    )
    log.info("option.excluded", task_id=str(task_id), option_id=str(option_id))


def include_option(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    option_id: uuid.UUID,
    actor: str,
    reason: str | None = None,
) -> None:
    """Include an option again, and log it as the user's turn.

    Writes ``state = "included"`` and keeps an ``exclusion`` record with
    ``by = "user"`` as the marker that the user decided (constrain's
    ``user_holds_state``), so a rebuild's ``constrain`` never excludes it
    again. The read models show no exclusion on an included option.

    Args:
        conn: The caller's open transaction, holding the task row lock.
        task_id: The options-scoping task.
        option_id: The option.
        actor: The user (token subject) the History event names.
        reason: Why, in the user's words, when given.

    Raises:
        LonglistActionRefused: ``not_scoping`` or ``run_active``.
        OptionNotFound: If the task holds no such option.
    """
    admit_longlist_action(conn, task_id=task_id)
    row = _locked_option(conn, task_id=task_id, option_id=option_id)
    text = _clean_reason(reason)
    conn.execute(
        option.update()
        .where(option.c.task_id == task_id, option.c.option_id == option_id)
        .values(
            state="included",
            exclusion={"constraint": USER_DECISION, "reason": text or "", "by": "user"},
            updated_at=datetime.now(UTC),
        )
    )
    _event(
        conn,
        task_id=task_id,
        event_type=OPTION_INCLUDED,
        actor=actor,
        row=row,
        verb="include",
        reason=text,
    )
    log.info("option.included", task_id=str(task_id), option_id=str(option_id))


def current_plan_row(conn: Connection, *, task_id: uuid.UUID) -> dict[str, Any]:
    """The task's current approved plan version, as the option search takes it.

    Args:
        conn: Open database connection.
        task_id: The options-scoping task.

    Returns:
        ``{"plan_id", "version", "payload"}``.

    Raises:
        LonglistActionRefused: ``no_plan`` when there is no approved scoping plan.
    """
    row = conn.execute(
        select(task_plan.c.plan_id, task_plan.c.version, task_plan.c.payload)
        .where(task_plan.c.task_id == task_id)
        .where(task_plan.c.status == "approved")
        .order_by(task_plan.c.version.desc())
        .limit(1)
    ).mappings().one_or_none()
    if row is None:
        raise LonglistActionRefused("no_plan", "the task has no approved plan to search against")
    return dict(row)


def propose_design(
    agent: AgentBackend, *, plan_payload: Any, words: str, session_id: uuid.UUID
) -> OptionDesign:
    """Propose a specified design back from the user's words (``option_design_v1``, A14).

    One judgment-model call, outside any transaction. The verb *add* proposes
    in its sorting turn and applies on the confirming one; the button proposes
    and applies in one request.

    Args:
        agent: The agent backend.
        plan_payload: The current approved plan's payload.
        words: The option, in the user's words.
        session_id: The Langfuse session (the task id).

    Returns:
        The design at version 1.

    Raises:
        RuntimeError: If the backend cannot produce a usable design.
        ValueError: If the proposal carries no usable name, description or feature.
    """
    plan = validate_plan(OPTIONS_SCOPING, plan_payload)
    assert isinstance(plan, ScopingPlan)
    wire = agent.propose_option_design(
        words,
        question=plan.question,
        target_unit=plan.target_unit.text,
        outcomes=[outcome.text for outcome in plan.outcomes],
        session_id=session_id,
    )
    return OptionDesign.from_wire(wire)


@dataclass(frozen=True)
class OptionAdded:
    """An option added by hand and the option search it opened.

    Args:
        option_id: The new option (``origin = "added_by_you"``).
        capability_run_id: Its option search: a child walk with no parent.
    """

    option_id: uuid.UUID
    capability_run_id: uuid.UUID


def add_option(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    words: str,
    design: OptionDesign,
    backends: RunnerBackends,
    user_id: str,
) -> OptionAdded:
    """Mint an option as *added by you* and open its option search (no parent).

    Called outside any transaction. Under the dispatch lock (the order
    ``create_run`` and the longlist opener take: the lock, then the task row),
    one transaction admits the action, mints the option row
    (``created_by_run_id = None``) and its History event and takes the
    dispatch reservation; then :func:`run_option_search` opens the child walk
    with ``parent_capability_run_id = None`` under the current approved plan,
    and the call waits for the walk's row before releasing the reservation —
    so no second walk can race in between. The records the search finds are
    assigned against the existing options by the next build's seeded
    clustering.

    Args:
        engine: Database engine.
        task_id: The options-scoping task.
        words: The option, in the user's words (recorded in the History event).
        design: The design ``option_design_v1`` proposed back.
        backends: The runner backend bundle the option search runs with.
        user_id: The user (token subject): the History event's actor and the
            trace attribution.

    Returns:
        The option and its option search.

    Raises:
        LonglistActionRefused: ``not_scoping``, ``run_active`` or ``no_plan``.
    """
    option_id = uuid.uuid4()
    with _dispatch_lock:
        with engine.begin() as conn:
            task_lock(conn, task_id)
            _refuse_unless_open(conn, task_id=task_id, reserved=task_id in _dispatching_tasks)
            plan_row = current_plan_row(conn, task_id=task_id)
            now = datetime.now(UTC)
            conn.execute(
                option.insert().values(
                    option_id=option_id,
                    task_id=task_id,
                    name=design.name,
                    description=design.description,
                    design=design.model_dump(mode="json"),
                    design_version=design.version,
                    outcomes=list(design.outcomes_served),
                    origin="added_by_you",
                    state="included",
                    secondary_lever_types=[],
                    created_by_run_id=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            row = conn.execute(
                select(option.c.option_id, option.c.name).where(option.c.option_id == option_id)
            ).one()
            _event(
                conn,
                task_id=task_id,
                event_type=OPTION_ADDED,
                actor=user_id,
                row=row,
                verb="add",
                reason=None,
                extra={"words": words, "design_version": design.version},
            )
            _dispatching_tasks.add(task_id)
        try:
            child_id = run_option_search(
                engine,
                task_id=task_id,
                plan_row=plan_row,
                design=design,
                option_id=option_id,
                parent_capability_run_id=None,
                backends=backends,
                user_id=user_id,
            )
        except BaseException:
            _dispatching_tasks.discard(task_id)
            log.exception("option.add_search_failed", task_id=str(task_id))
            raise
    try:
        _await_new_run(engine, task_id=task_id, existing_ids=set(), capability_run_id=child_id)
    finally:
        # Once the walk's row exists the database's `running` row is the fence.
        with _dispatch_lock:
            _dispatching_tasks.discard(task_id)
    log.info(
        "option.added",
        task_id=str(task_id),
        option_id=str(option_id),
        capability_run_id=str(child_id),
    )
    return OptionAdded(option_id=option_id, capability_run_id=child_id)
