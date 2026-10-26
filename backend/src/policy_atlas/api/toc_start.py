"""Opening theory-of-change walks and following draft with check (task 054, S4, S7).

A theory of change runs two walks (C3), each under its own intent record with
``purpose = 'toc'`` and ``context.toc_walk``:

- the **draft walk** runs under the record ``persist_approved_plan`` wrote
  with the approved plan; Start (``POST /runs``) opens it through
  ``_dispatch_run``;
- the **check walk** starts by itself the moment the draft walk succeeds:
  :func:`run_toc_sequence` mints it with :func:`admit_and_mint` and runs it
  inline on the worker that ran the draft (one hop, never twice for the same
  draft).

Restart rule: Start on a task that already has a graph mints a full check
walk instead of drafting again (:func:`start_scope`), so a check that failed
or was cut off always has a way forward.

The Task Agent speaks twice, in code-authored lines with no model call (J3,
J5): when the draft lands and when the check ends.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.locks import task_lock
from policy_atlas.api.routers._common import active_parentless_walk
from policy_atlas.api.routers.runs import _dispatch_lock
from policy_atlas.api.run_io import ParkIO
from policy_atlas.core.schema import (
    capability_run,
    event_log,
    evidence_scope,
    runs,
    task_agent_transcript,
)
from policy_atlas.runtime.capability_registry import (
    THEORY_OF_CHANGE,
    expect_toc_plan,
    latest_approved_plan_row,
    validate_plan,
)
from policy_atlas.runtime.conversation_lifecycle import ensure_active_task_agent_conversation
from policy_atlas.runtime.runner import RunnerBackends, RunPlanOutcome, run_plan
from policy_atlas.runtime.toc_plan import (
    TOC_LINKS_KEY,
    TOC_PURPOSE,
    TOC_WALK_CHECK,
    TOC_WALK_DRAFT,
    TOC_WALK_KEY,
    TocPlan,
)
from policy_atlas.theory_of_change.store import TOC_CHANGED_EVENT, has_graph

log = structlog.get_logger()

#: The context key naming the draft walk a check walk follows (the duplicate guard).
DRAFT_WALK_KEY = "draft_capability_run_id"

#: J3: the Task Agent's line when the draft lands.
DRAFT_LANDED_MESSAGE = (
    "The draft is on the canvas. Policy Atlas is now checking each step against research "
    "and policy documents; you can read it while the check runs."
)

#: J7: the line that ends the check's message.
STRESS_TEST_MESSAGE = (
    "When you are ready, try a stress test: ask what would make the critical connection fail here."
)

_ENDED_WELL = ("succeeded", "degraded")


class TocRefused(Exception):
    """A theory-of-change walk could not be opened.

    Args:
        reason: ``not_toc`` · ``run_active`` · ``no_plan``.
        message: A sentence for the log or an error body.
    """

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass(frozen=True)
class AdmittedToc:
    """A theory-of-change walk admitted and minted, not yet running.

    Args:
        capability_run_id: The walk's identity, minted here.
        evidence_scope_id: Its intent record.
        plan_row: The approved plan version it runs.
    """

    capability_run_id: uuid.UUID
    evidence_scope_id: uuid.UUID
    plan_row: dict[str, Any]


def check_intent(plan: TocPlan) -> str:
    """The check walk's intent: the theory, never the place (S3)."""
    doing = plan.intervention or "the intervention"
    return (
        f"Evidence on whether {doing} brings about {plan.intended_change} "
        f"for {plan.target_population}, and on each step along the way."
    )


def mint_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    plan_row: dict[str, Any] | Any,
    toc_walk: str,
    links: list[str] | None = None,
    draft_run_id: uuid.UUID | None = None,
) -> uuid.UUID:
    """Insert one main theory-of-change intent record and return its id.

    Args:
        conn: Open transaction.
        task_id: The task.
        plan_row: The approved plan version (``plan_id``, ``payload``).
        toc_walk: ``draft`` or ``check``.
        links: The link ids a named-link check covers, or ``None``.
        draft_run_id: The draft walk a check follows, or ``None``.

    Returns:
        The new intent record's id.
    """
    plan = expect_toc_plan(validate_plan(THEORY_OF_CHANGE, plan_row["payload"]))
    context: dict[str, Any] = {"capability": THEORY_OF_CHANGE, TOC_WALK_KEY: toc_walk}
    if links:
        context[TOC_LINKS_KEY] = links
    if draft_run_id is not None:
        context[DRAFT_WALK_KEY] = str(draft_run_id)
    scope_id = uuid.uuid4()
    conn.execute(
        evidence_scope.insert().values(
            evidence_scope_id=scope_id,
            task_id=task_id,
            intent=plan.question if toc_walk == TOC_WALK_DRAFT else check_intent(plan),
            context=context,
            created_at=datetime.now(UTC),
            purpose=TOC_PURPOSE,
            plan_id=plan_row["plan_id"],
        )
    )
    return scope_id


def admit_and_mint(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    toc_walk: str,
    links: list[str] | None = None,
    draft_run_id: uuid.UUID | None = None,
) -> AdmittedToc:
    """Admit a theory-of-change walk and mint its intent record, under the dispatch lock.

    For the walk that follows another on the same worker (the check after the
    draft): that worker is the capacity, so only the active-walk admission is
    taken, as the unattended longlist follow-on does. A walk another surface
    started in the gap wins.

    Args:
        engine: Database engine.
        task_id: The theory-of-change task.
        toc_walk: ``draft`` or ``check``.
        links: The link ids a named-link check covers.
        draft_run_id: The draft walk a check follows.

    Returns:
        The admitted walk.

    Raises:
        TocRefused: If the task is not a theory of change, has an active walk
            or has no approved plan.
    """
    with _dispatch_lock, engine.begin() as conn:
        task_row = task_lock(conn, task_id)
        if task_row["capability"] != THEORY_OF_CHANGE:
            raise TocRefused("not_toc", "this is not a theory-of-change task")
        if active_parentless_walk(conn, task_id) is not None:
            raise TocRefused("run_active", "the task already has an active run")
        plan_row = latest_approved_plan_row(conn, task_id)
        if plan_row is None:
            raise TocRefused("no_plan", "the task has no approved plan")
        scope_id = mint_scope(
            conn,
            task_id=task_id,
            plan_row=plan_row,
            toc_walk=toc_walk,
            links=links,
            draft_run_id=draft_run_id,
        )
    admitted = AdmittedToc(
        capability_run_id=uuid.uuid4(), evidence_scope_id=scope_id, plan_row=dict(plan_row)
    )
    log.info(
        "toc.walk_minted",
        task_id=str(task_id),
        toc_walk=toc_walk,
        capability_run_id=str(admitted.capability_run_id),
    )
    return admitted


def start_scope(engine: Engine, *, task_id: uuid.UUID, plan_row: dict[str, Any]) -> uuid.UUID:
    """The intent record Start runs: the draft's, or a full check once a graph exists.

    Args:
        engine: Database engine.
        task_id: The task.
        plan_row: The approved plan row ``POST /runs`` admitted.

    Returns:
        The intent record to run under.
    """
    with engine.begin() as conn:
        if not has_graph(conn, task_id):
            return uuid.UUID(str(plan_row["evidence_scope_id"]))
        return mint_scope(conn, task_id=task_id, plan_row=plan_row, toc_walk=TOC_WALK_CHECK)


def walk_kind(conn: Connection, *, task_id: uuid.UUID, capability_run_id: uuid.UUID) -> str | None:
    """Return a walk's ``toc_walk`` kind, or ``None`` for any other walk."""
    row = conn.execute(
        select(evidence_scope.c.purpose, evidence_scope.c.context)
        .select_from(
            capability_run.join(
                evidence_scope,
                (evidence_scope.c.evidence_scope_id == capability_run.c.evidence_scope_id)
                & (evidence_scope.c.task_id == capability_run.c.task_id),
            )
        )
        .where(capability_run.c.capability_run_id == capability_run_id)
        .where(capability_run.c.task_id == task_id)
    ).one_or_none()
    if row is None or row.purpose != TOC_PURPOSE:
        return None
    return (row.context or {}).get(TOC_WALK_KEY)


def _check_follows(conn: Connection, *, task_id: uuid.UUID, draft_run_id: uuid.UUID) -> bool:
    return (
        conn.execute(
            select(evidence_scope.c.evidence_scope_id)
            .where(evidence_scope.c.task_id == task_id)
            .where(evidence_scope.c.purpose == TOC_PURPOSE)
            .where(evidence_scope.c.context[DRAFT_WALK_KEY].astext == str(draft_run_id))
            .limit(1)
        ).first()
        is not None
    )


def run_toc_sequence(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    first_outcome: RunPlanOutcome,
    backends: RunnerBackends,
) -> RunPlanOutcome | None:
    """Follow a finished theory-of-change walk: draft → check, one hop.

    After a successful draft walk: post the J3 line, mint the check walk
    (unless one already follows this draft) and run it inline. After a check
    walk (this one or a Start that restarted one): post the change list.

    Args:
        engine: Database engine.
        task_id: The task.
        first_outcome: The walk that just ended.
        backends: The runner backend bundle.

    Returns:
        The check walk's outcome when one ran here, else ``None``.
    """
    walk_id = first_outcome.capability_run_id
    if walk_id is None or first_outcome.status not in _ENDED_WELL:
        return None
    with engine.connect() as conn:
        kind = walk_kind(conn, task_id=task_id, capability_run_id=walk_id)
    if kind == TOC_WALK_CHECK:
        post_check_message(engine, task_id=task_id, walk_id=walk_id)
        return None
    if kind != TOC_WALK_DRAFT:
        return None
    post_agent_message(engine, task_id=task_id, text=DRAFT_LANDED_MESSAGE)
    with engine.connect() as conn:
        if _check_follows(conn, task_id=task_id, draft_run_id=walk_id):
            log.info("toc.check_already_follows", task_id=str(task_id))
            return None
    try:
        admitted = admit_and_mint(
            engine, task_id=task_id, toc_walk=TOC_WALK_CHECK, draft_run_id=walk_id
        )
    except TocRefused as exc:
        log.warning("toc.check_refused", task_id=str(task_id), reason=exc.reason)
        return None
    outcome = run_plan(
        engine,
        task_id=task_id,
        evidence_scope_id=admitted.evidence_scope_id,
        # Validated through the registry: a ToC plan is always unattended (C12).
        plan=validate_plan(THEORY_OF_CHANGE, admitted.plan_row["payload"]),
        plan_id=admitted.plan_row["plan_id"],
        plan_version=admitted.plan_row["version"],
        plan_row_id=admitted.plan_row["plan_id"],
        backends=backends,
        io=ParkIO(),
        session_id=task_id,
        capability_run_id=admitted.capability_run_id,
    )
    if outcome.status in _ENDED_WELL:
        post_check_message(engine, task_id=task_id, walk_id=admitted.capability_run_id)
    return outcome


def post_agent_message(engine: Engine, *, task_id: uuid.UUID, text: str) -> None:
    """Append one code-authored Task Agent line to the task's thread (no model call).

    Written as a completed transcript row with an empty user message, in the
    task's active Task Agent conversation.

    Args:
        engine: Database engine.
        task_id: The task.
        text: The line.
    """
    now = datetime.now(UTC)
    with engine.begin() as conn:
        task_lock(conn, task_id)
        conversation_id = ensure_active_task_agent_conversation(conn, task_id=task_id, now=now)
        last = conn.execute(
            select(func.coalesce(func.max(task_agent_transcript.c.turn_index), -1)).where(
                task_agent_transcript.c.task_id == task_id
            )
        ).scalar_one()
        conn.execute(
            task_agent_transcript.insert().values(
                id=uuid.uuid4(),
                task_id=task_id,
                conversation_id=conversation_id,
                client_turn_id=uuid.uuid4(),
                turn_index=int(last) + 1,
                user_message="",
                reply=text,
                task_agent_state=None,
                response=None,
                suggestions=[],
                status="completed",
                created_at=now,
                completed_at=now,
            )
        )


def check_changes(conn: Connection, *, task_id: uuid.UUID, walk_id: uuid.UUID) -> list[str]:
    """The plain-language changes a check walk's steps recorded (J5)."""
    payloads = conn.execute(
        select(event_log.c.payload)
        .select_from(
            event_log.join(
                runs,
                (runs.c.run_id == event_log.c.run_id) & (runs.c.task_id == event_log.c.task_id),
            )
        )
        .where(event_log.c.task_id == task_id)
        .where(runs.c.capability_run_id == walk_id)
        .where(event_log.c.event_type == TOC_CHANGED_EVENT)
        .order_by(event_log.c.sequence)
    ).scalars()
    return [str(line) for payload in payloads for line in (payload or {}).get("changes", [])]


def post_check_message(engine: Engine, *, task_id: uuid.UUID, walk_id: uuid.UUID) -> None:
    """Post the check's end message: what changed, then the stress-test suggestion (J5, J7)."""
    with engine.connect() as conn:
        changes = check_changes(conn, task_id=task_id, walk_id=walk_id)
    if changes:
        body = "The evidence check is done. What it changed:\n" + "\n".join(
            f"- {line}" for line in changes
        )
    else:
        body = "The evidence check is done. It did not change any pathway."
    post_agent_message(engine, task_id=task_id, text=f"{body}\n\n{STRESS_TEST_MESSAGE}")
