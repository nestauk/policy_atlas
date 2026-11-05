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
    TOC_REVIEW_FIRST_KEY,
    TOC_WALK_CHECK,
    TOC_WALK_DRAFT,
    TOC_WALK_KEY,
    TocPlan,
)
from policy_atlas.theory_of_change import store
from policy_atlas.theory_of_change.store import has_graph

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
    extra: dict[str, Any] | None = None,
) -> uuid.UUID:
    """Insert one main theory-of-change intent record and return its id.

    Args:
        conn: Open transaction.
        task_id: The task.
        plan_row: The approved plan version (``plan_id``, ``payload``).
        toc_walk: ``draft`` or ``check``.
        links: The link ids a named-link check covers, or ``None``.
        draft_run_id: The draft walk a check follows, or ``None``.
        extra: More context for a named check (C40): its mode, the studies the
            user added, who started it.

    Returns:
        The new intent record's id.
    """
    plan = expect_toc_plan(validate_plan(THEORY_OF_CHANGE, plan_row["payload"]))
    context: dict[str, Any] = {"capability": THEORY_OF_CHANGE, TOC_WALK_KEY: toc_walk}
    if links:
        context[TOC_LINKS_KEY] = links
    if draft_run_id is not None:
        context[DRAFT_WALK_KEY] = str(draft_run_id)
    context.update(extra or {})
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
    context = walk_context(conn, task_id=task_id, capability_run_id=capability_run_id)
    return None if context is None else context.get(TOC_WALK_KEY)


def walk_context(
    conn: Connection, *, task_id: uuid.UUID, capability_run_id: uuid.UUID
) -> dict[str, Any] | None:
    """A theory-of-change walk's intent-record context, or ``None`` for any other walk."""
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
    return dict(row.context or {})


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
    if walk_id is not None and first_outcome.status == "aborted":
        # The user's Stop (C48): say what stays and how to go on.
        post_agent_message(engine, task_id=task_id, text=STOPPED_MESSAGE)
        return None
    if walk_id is not None and first_outcome.status in _ENDED_BADLY:
        post_failure_message(engine, task_id=task_id, walk_id=walk_id)
        return None
    if walk_id is None or first_outcome.status not in _ENDED_WELL:
        return None
    with engine.connect() as conn:
        kind = walk_kind(conn, task_id=task_id, capability_run_id=walk_id)
    if kind == TOC_WALK_CHECK:
        post_check_message(engine, task_id=task_id, walk_id=walk_id)
        return None
    if kind != TOC_WALK_DRAFT:
        return None
    with engine.connect() as conn:
        context = walk_context(conn, task_id=task_id, capability_run_id=walk_id) or {}
    if context.get(TOC_REVIEW_FIRST_KEY):
        # An uploaded theory (increment 5): the user checks the reading first.
        post_agent_message(engine, task_id=task_id, text=_review_text(engine, task_id))
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
    elif outcome.status in _ENDED_BADLY:
        post_failure_message(engine, task_id=task_id, walk_id=admitted.capability_run_id)
    return outcome


def _review_text(engine: Engine, task_id: uuid.UUID) -> str:
    """The review message for an uploaded theory's draft: what came from the diagram."""
    from policy_atlas.theory_of_change.importing import latest_import, review_message
    from policy_atlas.theory_of_change.proposals import open_proposals

    with engine.connect() as conn:
        imported = latest_import(conn, task_id)
        graph, rows = store.load_graph(conn, task_id)
        completes = next(
            (p.summary for p in open_proposals(conn, task_id) if p.source == "draft"), None
        )
    if imported is None:
        return DRAFT_LANDED_MESSAGE
    codes = [row.code or key for key, row in rows.links.items() if row.origin != "imported"]
    suggested = sorted(codes, key=lambda c: int(c.lstrip("#")) if c.lstrip("#").isdigit() else 0)
    return review_message(
        imported,
        kept=len(rows.links) - len(suggested),
        suggested=suggested,
        boxes=len(graph.boxes),
        links=len(graph.links),
        completes=completes,
    )


def post_agent_message(
    engine: Engine, *, task_id: uuid.UUID, text: str, user_message: str = ""
) -> None:
    """Append one code-authored Task Agent line to the task's thread (no model call).

    Written as a completed transcript row, in the task's active Task Agent
    conversation; the user message is empty unless the line answers one.

    Args:
        engine: Database engine.
        task_id: The task.
        text: The line.
        user_message: The user's message it answers, if any.
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
                user_message=user_message,
                reply=text,
                task_agent_state=None,
                response=None,
                suggestions=[],
                status="completed",
                created_at=now,
                completed_at=now,
            )
        )


#: A check asked for while another walk runs waits as this event (task 054, round 5).
TOC_CHECK_QUEUED_EVENT = "toc.check_queued"
#: Which queued checks a walk took, or Stop cleared: ``{"sequences": [...]}``.
TOC_CHECK_DEQUEUED_EVENT = "toc.check_dequeued"


def queue_check(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    link_ids: list[str],
    mode: str,
    studies: dict[str, list[str]] | None,
    user_id: str,
) -> None:
    """Keep a named check to run when the task's current walk ends."""
    from policy_atlas.core import events

    events.append(
        conn,
        task_id=task_id,
        run_id=None,
        event_type=TOC_CHECK_QUEUED_EVENT,
        payload={"links": link_ids, "mode": mode, "studies": studies or {}, "by": user_id},
    )


def _queued(conn: Connection, task_id: uuid.UUID) -> list[Any]:
    """The queued checks no walk has taken yet, oldest first."""
    rows = conn.execute(
        select(event_log.c.sequence, event_log.c.event_type, event_log.c.payload)
        .where(event_log.c.task_id == task_id)
        .where(event_log.c.event_type.in_([TOC_CHECK_QUEUED_EVENT, TOC_CHECK_DEQUEUED_EVENT]))
        .order_by(event_log.c.sequence)
    ).all()
    taken = {
        int(seq)
        for row in rows
        if row.event_type == TOC_CHECK_DEQUEUED_EVENT
        for seq in (row.payload or {}).get("sequences", [])
    }
    return [
        row
        for row in rows
        if row.event_type == TOC_CHECK_QUEUED_EVENT and int(row.sequence) not in taken
    ]


def queued_link_ids(conn: Connection, task_id: uuid.UUID) -> list[str]:
    """The links a queued check names, for the canvas's Queued state."""
    out: list[str] = []
    for row in _queued(conn, task_id):
        out += [key for key in (row.payload or {}).get("links", []) if key not in out]
    return out


def clear_queue(conn: Connection, task_id: uuid.UUID) -> None:
    """Drop every queued check (the user's Stop)."""
    from policy_atlas.core import events

    pending = _queued(conn, task_id)
    if pending:
        events.append(
            conn,
            task_id=task_id,
            run_id=None,
            event_type=TOC_CHECK_DEQUEUED_EVENT,
            payload={"sequences": [int(row.sequence) for row in pending], "reason": "stopped"},
        )


def take_queued_check(
    conn: Connection, task_id: uuid.UUID
) -> tuple[uuid.UUID, dict[str, Any], str] | None:
    """Mint one walk for the oldest queued check and every queued check of its mode.

    Returns:
        ``(scope_id, plan_row, user_id)``, or ``None`` when nothing waits.
    """
    from policy_atlas.core import events
    from policy_atlas.runtime.toc_plan import (
        TOC_CHECK_MODE_KEY,
        TOC_STARTED_BY_KEY,
        TOC_STUDIES_KEY,
    )

    pending = _queued(conn, task_id)
    if not pending:
        return None
    mode = pending[0].payload["mode"]
    batch = [row for row in pending if row.payload["mode"] == mode]
    links: list[str] = []
    studies: dict[str, list[str]] = {}
    for row in batch:
        links += [key for key in row.payload.get("links", []) if key not in links]
        for key, dois in (row.payload.get("studies") or {}).items():
            kept = studies.setdefault(key, [])
            kept += [doi for doi in dois if doi not in kept]
    events.append(
        conn,
        task_id=task_id,
        run_id=None,
        event_type=TOC_CHECK_DEQUEUED_EVENT,
        payload={"sequences": [int(row.sequence) for row in batch]},
    )
    plan_row = latest_approved_plan_row(conn, task_id)
    if plan_row is None:
        return None
    user_id = str(batch[0].payload.get("by") or "")
    scope_id = mint_scope(
        conn,
        task_id=task_id,
        plan_row=plan_row,
        toc_walk=TOC_WALK_CHECK,
        links=links,
        extra={
            TOC_CHECK_MODE_KEY: mode,
            TOC_STARTED_BY_KEY: user_id,
            **({TOC_STUDIES_KEY: studies} if studies else {}),
        },
    )
    return scope_id, dict(plan_row), user_id


#: Posted when the user stops a check (C48).
STOPPED_MESSAGE = (
    "The check stopped. What it finished stays on the canvas. Connections it did not "
    "reach show Needs evidence: use Find evidence in the toolbar to check them."
)


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 'es' if noun.endswith('h') else 's'}"


def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def _pending_found(conn: Connection, *, task_id: uuid.UUID, walk_id: uuid.UUID) -> str | None:
    """The message for a named check (C40 to C45), or ``None`` for a full check.

    It says what the check searched, read and set aside, then one line per
    connection: how many documents test the step and the verdict now.
    """
    from policy_atlas.core.schema import toc_item_evidence, toc_link
    from policy_atlas.runtime.toc_plan import TOC_CHECK_MODE_KEY
    from policy_atlas.theory_of_change.review import _theory

    context = conn.execute(
        select(evidence_scope.c.context)
        .select_from(
            capability_run.join(
                evidence_scope,
                (evidence_scope.c.evidence_scope_id == capability_run.c.evidence_scope_id)
                & (evidence_scope.c.task_id == capability_run.c.task_id),
            )
        )
        .where(capability_run.c.capability_run_id == walk_id)
    ).scalar_one_or_none()
    mode = (context or {}).get(TOC_CHECK_MODE_KEY)
    if mode == "report":
        return "The report is updated for the theory as it is now."
    if mode not in ("new_items", "check_again", "add_study", "find_more"):
        return None
    link_ids = [uuid.UUID(key) for key in (context or {}).get("links") or []]
    code_of = {
        row.link_id: row.code
        for row in conn.execute(
            select(toc_link.c.link_id, toc_link.c.code).where(toc_link.c.link_id.in_(link_ids))
        )
    }
    judged: dict[uuid.UUID, list[str]] = {}
    for row in conn.execute(
        select(toc_item_evidence.c.link_id, toc_item_evidence.c.support)
        .where(toc_item_evidence.c.task_id == task_id)
        .where(toc_item_evidence.c.capability_run_id == walk_id)
    ):
        judged.setdefault(row.link_id, []).append(row.support)
    verdicts = {link["code"]: link["verdict"] for link in _theory(conn, task_id)["links"]}
    done = {
        "new_items": "Finding evidence",
        "check_again": "Checking again",
        "add_study": "Adding the study",
        "find_more": "Finding more evidence",
    }[mode]
    codes = [code_of[key] for key in link_ids if code_of.get(key)]
    lines = [f"{done} for {_and(codes) if codes else 'the connection'} is done."]
    for key in link_ids:
        code = code_of.get(key)
        if not code:
            continue
        supports = judged.get(key, [])
        testing = sum(1 for support in supports if support != "not_about")
        verdict = verdicts.get(code, "Not enough evidence")
        prefix = f"{code}: " if len(codes) > 1 else ""
        if not supports:
            lines.append(
                f"{prefix}It found no new documents to judge. The verdict stays {verdict}."
            )
        elif testing == 0:
            lines.append(
                f"{prefix}It judged {_plural(len(supports), 'new document')}, but none tests "
                f"this step, so they are listed as not about it. The verdict stays {verdict}."
            )
        elif mode == "find_more":
            lines.append(
                f"{prefix}{_plural(testing, 'new document')} of {len(supports)} test this step. "
                "They wait for you to accept them in its sidebar."
            )
        else:
            lines.append(
                f"{prefix}{testing} of {_plural(len(supports), 'document')} test this step. "
                f"The verdict is now {verdict}."
            )
    return "\n".join(lines)


#: A walk that ended with an error: the chat says so and how to try again.
_ENDED_BADLY = frozenset({"failed", "interrupted"})


def failure_reason(error: str | None) -> str:
    """A walk's error in plain words for the chat; the full error stays in the logs."""
    text = error or ""
    if text.startswith("the draft failed its structure checks:"):
        return "the draft did not pass its structure check (" + text.split(":", 1)[1].strip() + ")"
    if "json_invalid" in text or "validation error" in text:
        return "the model's answer could not be read"
    return "something went wrong on our side"


def post_failure_message(engine: Engine, *, task_id: uuid.UUID, walk_id: uuid.UUID) -> None:
    """Say a walk failed, why in plain words, and how to try again (owner, 2026-11-04)."""
    with engine.connect() as conn:
        kind = walk_kind(conn, task_id=task_id, capability_run_id=walk_id)
        error = conn.execute(
            select(event_log.c.payload["error"].astext)
            .where(
                event_log.c.task_id == task_id,
                # The error is on the failing step's own run, which belongs to the walk.
                event_log.c.run_id.in_(
                    select(runs.c.run_id).where(runs.c.capability_run_id == walk_id)
                ),
                event_log.c.event_type == "run.failed",
            )
            .order_by(event_log.c.sequence.desc())
            .limit(1)
        ).scalar_one_or_none()
    reason = failure_reason(error)
    text = (
        f"I couldn't draft the theory: {reason}. Press “Draft the theory” to try again."
        if kind == TOC_WALK_DRAFT
        else f"The evidence check stopped: {reason}. What it finished stays on the canvas. "
        "Press “Check the evidence” on the Result tab to try again."
    )
    post_agent_message(engine, task_id=task_id, text=text)


def post_check_message(engine: Engine, *, task_id: uuid.UUID, walk_id: uuid.UUID) -> None:
    """Post the check's end message: where the results are, then the stress-test suggestion.

    The verdict and the findings are on the Result tab; the chat only points
    there (owner, 2026-11-04: the longer summary read as bitty). A Find more
    evidence walk (C44) says instead how many new documents wait for the user,
    and where.
    """
    with engine.connect() as conn:
        found = _pending_found(conn, task_id=task_id, walk_id=walk_id)
    if found is not None:
        post_agent_message(engine, task_id=task_id, text=found)
        return
    post_agent_message(
        engine,
        task_id=task_id,
        text="The evidence check is done. Read the full report in the Result tab. "
        + STRESS_TEST_MESSAGE,
    )
