"""The user's direct actions on the longlist (task 045, S11, S12; D13; task 055, P9).

*Add an option*, *exclude* and *include again* are one set of apply
functions with two callers: the buttons (``api/routers/longlist.py``) and the
Task Agent's longlist verbs (Phase 7), which confirm a verb in the thread and
then call the same function. Task 055 adds the two shortlist buttons, *add
to shortlist* and *remove from shortlist*, on the same pattern. Each writes
the option's state **and one History event as the user's turn** (contract
deliverable 9, ruling 1): an ``event_log`` row with ``run_id = None`` and
the actor in the payload, which ``GET /decisions`` renders with
``decided_by = "user"`` beside the lifecycle events (the precedent is the
rename and share audit events).

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
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.locks import task_lock
from policy_atlas.api.longlist_start import LonglistRefused
from policy_atlas.api.readmodels.repository import (
    OPTION_ADDED,
    OPTION_EXCLUDED,
    OPTION_INCLUDED,
    OPTION_SHORTLISTED,
    OPTION_UNSHORTLISTED,
    clean_text,
)
from policy_atlas.api.routers._common import active_parentless_walk
from policy_atlas.api.routers.runs import (
    _await_new_run,
    _dispatch_lock,
    _dispatching_tasks,
    _search_reservations,
)
from policy_atlas.core import events
from policy_atlas.core.schema import option
from policy_atlas.options_scoping.design import OptionDesign
from policy_atlas.runtime.agent_backend import AgentBackend
from policy_atlas.runtime.capability_registry import (
    OPTIONS_SCOPING,
    capability_of_task,
    expect_scoping_plan,
    latest_approved_plan_row,
    validate_plan,
)
from policy_atlas.runtime.option_search import _futures, _handles_lock, run_option_search
from policy_atlas.runtime.runner import RunnerBackends

log = structlog.get_logger()

#: The ``constraint`` a user's exclusion names (the card reads "excluded:
#: your decision").
USER_DECISION = "your decision"


class OptionNotFound(LookupError):
    """The task holds no such option."""


def admit_longlist_action(conn: Connection, *, task_id: uuid.UUID) -> None:
    """Refuse an action on an Evidence search task or while a parentless walk is active.

    Call under the task row lock (the caller's transaction).

    Args:
        conn: The caller's open transaction, holding the task row lock.
        task_id: The task.

    Raises:
        LonglistRefused: ``not_scoping`` or ``run_active``.
    """
    if capability_of_task(conn, task_id) != OPTIONS_SCOPING:
        raise LonglistRefused("not_scoping", "options belong to options-scoping tasks only")
    # Read without ``_dispatch_lock``: the caller holds the task row lock, and
    # the openers take the dispatch lock *then* the row lock — taking it here
    # would invert that order. A set-membership read is atomic under the GIL,
    # and a reservation is only ever held while its walk's row is on the way.
    if active_parentless_walk(conn, task_id) is not None or task_id in _dispatching_tasks:
        raise LonglistRefused(
            "run_active", "a run is in progress; wait for it to finish, then change the longlist"
        )


def _locked_option(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    option_id: uuid.UUID,
    with_merged: bool = False,
) -> Any:
    query = select(option).where(option.c.task_id == task_id, option.c.option_id == option_id)
    if not with_merged:
        # A merged duplicate has left the longlist: no verb reaches it (045 review P1).
        query = query.where(option.c.merged_into_option_id.is_(None))
    row = conn.execute(query.with_for_update()).one_or_none()
    if row is None:
        raise OptionNotFound(f"unknown option: {option_id}")
    return row


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
) -> None:
    """Exclude an option with the user's reason, and log it as the user's turn.

    Writes ``state = "excluded"`` and ``exclusion = {constraint: "your
    decision", reason, by: "user"}`` — reversible by :func:`include_option`,
    and never overridden by a rebuild's ``constrain``. An excluded option holds
    no shortlist place, so its place is cleared too, whatever it was (task
    055, PR10); including it again does not restore the place.

    Args:
        conn: The caller's open transaction, holding the task row lock.
        task_id: The options-scoping task.
        option_id: The option.
        reason: Why, in the user's words.
        actor: The user (token subject) the History event names.

    Raises:
        LonglistRefused: ``not_scoping`` or ``run_active``.
        OptionNotFound: If the task holds no such option.
    """
    admit_longlist_action(conn, task_id=task_id)
    row = _locked_option(conn, task_id=task_id, option_id=option_id)
    # A reason is optional on the button and the verb alike (owner, 2026-09-24):
    # a blank one is recorded empty, never invented.
    text = clean_text(reason)
    conn.execute(
        option.update()
        .where(option.c.task_id == task_id, option.c.option_id == option_id)
        .values(
            state="excluded",
            exclusion={"constraint": USER_DECISION, "reason": text or "", "by": "user"},
            shortlist_state=None,
            shortlist_reason=None,
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
        LonglistRefused: ``not_scoping`` or ``run_active``.
        OptionNotFound: If the task holds no such option.
    """
    admit_longlist_action(conn, task_id=task_id)
    row = _locked_option(conn, task_id=task_id, option_id=option_id)
    text = clean_text(reason)
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


def shortlist_option(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    option_id: uuid.UUID,
    actor: str,
) -> None:
    """Put an option on the shortlist as the user's own place, and log it.

    Writes ``shortlist_state = "added_by_you"``. A Policy Atlas pick on the
    same option becomes the user's place, and its reason is cleared: the user
    has now chosen it. Repeating the action on a place the user already holds
    changes nothing and writes no event.

    Args:
        conn: The caller's open transaction, holding the task row lock.
        task_id: The options-scoping task.
        option_id: The option.
        actor: The user (token subject) the History event names.

    Raises:
        LonglistRefused: ``not_scoping``, ``run_active``, or ``not_included``
            for an excluded or merged option.
        OptionNotFound: If the task holds no such option.
    """
    admit_longlist_action(conn, task_id=task_id)
    row = _locked_option(conn, task_id=task_id, option_id=option_id, with_merged=True)
    if row.state != "included" or row.merged_into_option_id is not None:
        raise LonglistRefused(
            "not_included", "only an included option can be put on the shortlist"
        )
    if row.shortlist_state == "added_by_you":
        return
    conn.execute(
        option.update()
        .where(option.c.task_id == task_id, option.c.option_id == option_id)
        .values(
            shortlist_state="added_by_you", shortlist_reason=None, updated_at=datetime.now(UTC)
        )
    )
    _event(
        conn,
        task_id=task_id,
        event_type=OPTION_SHORTLISTED,
        actor=actor,
        row=row,
        verb="shortlist",
        reason=None,
        extra={"previous_state": row.shortlist_state},
    )
    log.info("option.shortlisted", task_id=str(task_id), option_id=str(option_id))


def unshortlist_option(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    option_id: uuid.UUID,
    actor: str,
) -> None:
    """Take an option off the shortlist, and log it.

    A Policy Atlas pick becomes ``set_aside`` (so Suggest more does not offer
    it again); the user's own place clears to no state. Nothing refills the
    place and no walk opens (S7). An option with no place, or one already set
    aside, is left as it is with no event.

    Args:
        conn: The caller's open transaction, holding the task row lock.
        task_id: The options-scoping task.
        option_id: The option.
        actor: The user (token subject) the History event names.

    Raises:
        LonglistRefused: ``not_scoping`` or ``run_active``.
        OptionNotFound: If the task holds no such option.
    """
    admit_longlist_action(conn, task_id=task_id)
    row = _locked_option(conn, task_id=task_id, option_id=option_id)
    after = {"proposed": "set_aside", "added_by_you": None}
    if row.shortlist_state not in after:
        return
    conn.execute(
        option.update()
        .where(option.c.task_id == task_id, option.c.option_id == option_id)
        .values(
            shortlist_state=after[row.shortlist_state],
            shortlist_reason=None,
            updated_at=datetime.now(UTC),
        )
    )
    _event(
        conn,
        task_id=task_id,
        event_type=OPTION_UNSHORTLISTED,
        actor=actor,
        row=row,
        verb="unshortlist",
        reason=None,
        extra={"previous_state": row.shortlist_state},
    )
    log.info("option.unshortlisted", task_id=str(task_id), option_id=str(option_id))


def current_plan_row(conn: Connection, *, task_id: uuid.UUID) -> dict[str, Any]:
    """The task's current approved plan row, as the option search takes it.

    Args:
        conn: Open database connection.
        task_id: The options-scoping task.

    Returns:
        The ``task_plan`` row as a dict.

    Raises:
        LonglistRefused: ``no_plan`` when there is no approved scoping plan.
    """
    row = latest_approved_plan_row(conn, task_id)
    if row is None:
        raise LonglistRefused("no_plan", "the task has no approved plan to search against")
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
    plan = expect_scoping_plan(validate_plan(OPTIONS_SCOPING, plan_payload))
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
        run_open: Whether the search's walk row existed when the call
            returned; ``False`` while the search is still queued on the
            option-search pool (A4).
    """

    option_id: uuid.UUID
    capability_run_id: uuid.UUID
    run_open: bool = True


def _release_search_reservation(task_id: uuid.UUID) -> None:
    with _dispatch_lock:
        _dispatching_tasks.discard(task_id)
        _search_reservations.discard(task_id)


def _release_when_search_settles(task_id: uuid.UUID, child_id: uuid.UUID) -> None:
    """Hold an *add*'s reservation until its queued search has run (A4).

    The search's walk row is written only when the option-search pool starts
    it; until then the reservation is the task's fence. It is given back when
    the search's future settles (the row then exists, or the search ended
    without one) — in process memory, so a restart cannot strand it.
    """
    with _handles_lock:
        future = _futures.get(child_id)
    if future is None:
        _release_search_reservation(task_id)
        return
    future.add_done_callback(lambda _done: _release_search_reservation(task_id))


def add_option(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    words: str,
    design: OptionDesign,
    backends: RunnerBackends,
    user_id: str,
    in_commit: Callable[[Connection, uuid.UUID], None] | None = None,
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

    Once the option has committed, the call does not fail for a slow pool: if
    the walk's row has not appeared within the wait, it returns the option
    with ``run_open = False`` and keeps the reservation until the search
    settles (A4).

    Args:
        engine: Database engine.
        task_id: The options-scoping task.
        words: The option, in the user's words (recorded in the History event).
        design: The design ``option_design_v1`` proposed back.
        backends: The runner backend bundle the option search runs with.
        user_id: The user (token subject): the History event's actor and the
            trace attribution.
        in_commit: Called with the transaction and the new option's id just
            before the option commits — the chat verb consumes its pending
            action there, so a retried turn cannot mint a second option (A4).

    Returns:
        The option and its option search.

    Raises:
        LonglistRefused: ``not_scoping``, ``run_active`` or ``no_plan``.
    """
    option_id = uuid.uuid4()
    with _dispatch_lock:
        with engine.begin() as conn:
            task_lock(conn, task_id)
            admit_longlist_action(conn, task_id=task_id)
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
            if in_commit is not None:
                in_commit(conn, option_id)
            _dispatching_tasks.add(task_id)
            _search_reservations.add(task_id)
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
            _search_reservations.discard(task_id)
            log.exception("option.add_search_failed", task_id=str(task_id))
            raise
    try:
        _await_new_run(engine, task_id=task_id, existing_ids=set(), capability_run_id=child_id)
    except RuntimeError:
        # The option has committed: answer with it, its search still queued.
        log.warning(
            "option.add_search_queued", task_id=str(task_id), capability_run_id=str(child_id)
        )
        _release_when_search_settles(task_id, child_id)
        run_open = False
    else:
        # Once the walk's row exists the database's `running` row is the fence.
        _release_search_reservation(task_id)
        run_open = True
    log.info(
        "option.added",
        task_id=str(task_id),
        option_id=str(option_id),
        capability_run_id=str(child_id),
    )
    return OptionAdded(option_id=option_id, capability_run_id=child_id, run_open=run_open)
