"""Task-scoped Task Agent turns backed by a durable transcript."""

from __future__ import annotations

import json
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, cast

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.engine import Connection, Engine, RowMapping

from policy_atlas.api import continuation, gate_turns, transcript_rows
from policy_atlas.api.answer_core import apply_appraisal_labels
from policy_atlas.api.app import ApiConflict
from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract import (
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_MAX,
    AnswerPayloadOut,
    ConfirmBaselineIn,
    Page,
    PageMeta,
    PartProposalOut,
    PlanDraft,
    PlanOut,
    PlanPatchIn,
    ScopingPlanDraft,
    TaskAgentTranscriptTurnOut,
    TaskAgentTurnCreate,
    TaskAgentTurnOut,
    TurnDecisionOut,
)
from policy_atlas.api.contract.tasks import LatestRun
from policy_atlas.api.deps import (
    get_agent_backend,
    get_chat_backend,
    get_chat_embedding_backend,
    get_current_user,
    get_engine,
    get_executor,
    get_runner_backends,
    get_task_agent_backend,
)
from policy_atlas.api.gate_turns import PausedGate, read_paused_gate
from policy_atlas.api.longlist_start import (
    LonglistRefused,
    http_error,
    longlist_walk_exists,
    open_longlist_walk,
    opened_run,
    plan_row_of_walk,
)
from policy_atlas.api.longlist_turns import (
    LonglistSurface,
    dispatch_longlist_turn,
    is_longlist_state,
    read_longlist_surface,
)
from policy_atlas.api.routers._access import accessible_task
from policy_atlas.api.routers._common import (
    active_parentless_walk,
)
from policy_atlas.api.routers.check_ins import execute_claimed
from policy_atlas.core import tracing
from policy_atlas.core.embeddings import EmbeddingBackend
from policy_atlas.core.schema import (
    artefact,
    capability_run,
    conversation,
    task_agent_transcript,
    task_plan,
)
from policy_atlas.evidence_search.sourcing.country_filters import (
    ISO_3166_ALPHA2,
    OVERTON_COUNTRY_DISPLAY,
    TIER1_GROUPS,
    SearchDirectiveError,
    overton_display_names,
    validate_iso_alpha2,
)
from policy_atlas.options_scoping.design import OptionDesign
from policy_atlas.runtime.agent import build_plan, persist_approved_plan
from policy_atlas.runtime.agent_backend import AgentBackend
from policy_atlas.runtime.capability_registry import (
    EVIDENCE_SEARCH,
    OPTIONS_SCOPING,
    AnyPlan,
    TaskAgentProfile,
    capability_of_task,
    expect_scoping_plan,
    expect_task_plan,
    latest_approved_plan_row,
    spec_for,
    validate_plan,
)
from policy_atlas.runtime.chat_backend import ChatBackend
from policy_atlas.runtime.conversation_lifecycle import (
    ensure_active_task_agent_conversation,
)
from policy_atlas.runtime.runner import RunnerBackends
from policy_atlas.runtime.scoping_plan import (
    LONGLIST_PURPOSE,
    BaselineConfirmed,
    ScopingPlan,
    compose_longlist_screen_intent,
    merge_your_options,
    propose_option_designs,
    settle_patched_defaults,
    with_option_designs,
)
from policy_atlas.runtime.task_agent import TaskAgentTurnBackend
from policy_atlas.runtime.task_agent_prompt import PlanDraftWire
from policy_atlas.runtime.task_agent_scoping import (
    approved_scoping_plan,
    latest_approved_scoping_plan,
)
from policy_atlas.runtime.task_plan import TaskPlan, _enabled_components

log = structlog.get_logger()

# The client's confirm-marker regex (`option=([a-z0-9_]+)`) — enforced
# server-side so a card never ships an id the marker grammar can't round-trip.
_OPTION_ID_RE = re.compile(r"[a-z][a-z0-9_]*")

router = APIRouter(
    prefix="/api/v1/tasks",
    tags=["task_agent"],
    dependencies=[Depends(get_current_user)],
)

_PENDING_TTL = timedelta(minutes=10)
_turn_locks_guard = threading.Lock()
_turn_locks: dict[uuid.UUID, threading.Lock] = {}
# The registry is keyed by caller-supplied task ids BEFORE authz resolves,
# so it must stay bounded (the _sessions cache it replaced was LRU-128; the
# bound was lost in the 027 port — security review, 2026-07-29). Evicting an
# unheld lock is safe: correctness rests on the phase-1 task row lock and
# the transcript unique constraints, this lock only single-flights the
# task_agent spend.
_TURN_LOCKS_MAX = 256


def _turn_lock(task_id: uuid.UUID) -> threading.Lock:
    """Return the process-local concurrency guard for one task's Task Agent turn."""
    with _turn_locks_guard:
        if task_id not in _turn_locks and len(_turn_locks) >= _TURN_LOCKS_MAX:
            for key in [k for k, v in _turn_locks.items() if not v.locked()]:
                del _turn_locks[key]
        return _turn_locks.setdefault(task_id, threading.Lock())


def _now() -> datetime:
    """Return a timezone-aware persistence timestamp."""
    return datetime.now(UTC)


def _expire_stale_pending_turns(conn: Connection, task_id: uuid.UUID) -> None:
    """Terminally fail pending transcript rows older than the retry window."""
    now = _now()
    conn.execute(
        update(task_agent_transcript)
        .where(task_agent_transcript.c.task_id == task_id)
        .where(task_agent_transcript.c.status == "pending")
        .where(task_agent_transcript.c.created_at < now - _PENDING_TTL)
        .values(status="failed", completed_at=now)
    )


def plan_slot(draft: BaseModel, *, scoping_slot: str = "scoping") -> dict[str, Any]:
    """Put a projected draft in its capability's slot.

    The contracts keep one slot per capability (``plan`` for Evidence search,
    ``scoping`` — ``scoping_plan`` on a turn — for options scoping), so this is
    the one place the draft's type picks the field.

    Args:
        draft: A ``PlanDraft`` or ``ScopingPlanDraft``.
        scoping_slot: The field a scoping draft goes in.

    Returns:
        The keyword arguments that place the draft.
    """
    if isinstance(draft, ScopingPlanDraft):
        return {scoping_slot: draft}
    return {"plan": draft}


def _plan_out(capability: str, plan: AnyPlan, row: RowMapping) -> PlanOut:
    """Return one approved plan version as ``PlanOut``."""
    return PlanOut(
        **plan_slot(spec_for(capability).task_agent.draft_from_plan(plan)),
        capability=capability,
        version=row["version"],
        status=row["status"],
    )


def _load_approved_scoping_plan(
    conn: Connection, task_id: uuid.UUID
) -> tuple[ScopingPlan, RowMapping]:
    """Return the current approved scoping plan and its row.

    Raises:
        HTTPException: 404 when the task has no approved plan yet.
    """
    found = approved_scoping_plan(conn, task_id)
    if found is None:
        raise HTTPException(status_code=404, detail="resource not found")
    return found


def _scoping_plan_out(conn: Connection, task_id: uuid.UUID) -> PlanOut:
    """Return the scoping task's plan as ``GET /plan`` shows it.

    Approved rows win; before one exists the latest completed turn's own
    projection stands in, exactly as the Evidence search path does.
    """
    found = approved_scoping_plan(conn, task_id)
    if found is not None:
        return _plan_out(OPTIONS_SCOPING, *found)
    latest = conn.execute(
        select(task_agent_transcript.c.response)
        .where(task_agent_transcript.c.task_id == task_id)
        .where(task_agent_transcript.c.status == "completed")
        .order_by(task_agent_transcript.c.turn_index.desc())
        .limit(1)
    ).mappings().one_or_none()
    if latest is None or latest["response"] is None:
        raise HTTPException(status_code=404, detail="resource not found")
    response = TaskAgentTurnOut.model_validate(latest["response"])
    if response.scoping_plan is None:
        raise HTTPException(status_code=404, detail="resource not found")
    return PlanOut(
        scoping=response.scoping_plan,
        capability=OPTIONS_SCOPING,
        version=0,
        status="draft",
    )


def _apply_scoping_patch(
    plan: ScopingPlan,
    patch: Any,
    *,
    turn_index: int = 0,
    designs: dict[str, OptionDesign] | None = None,
) -> ScopingPlan:
    """Merge a typed scoping patch onto an approved plan and re-validate.

    ``your_options`` merge by the user's words (unchanged words keep their
    design; changed or new words get ``designs[text]`` when one was proposed
    before the transaction, else none), and the default preference is settled
    against the plan the patch applied to (task 045, D19, D22).
    """
    data = plan.model_dump(mode="json")
    supplied = patch.model_dump(mode="json", exclude_unset=True)
    options = supplied.pop("your_options", None)
    for field, value in supplied.items():
        if value is not None:
            data[field] = value
    if options is not None:
        data["your_options"] = [
            option.model_dump(mode="json")
            for option in merge_your_options(
                [o["text"] for o in options], plan.your_options, turn_index=turn_index
            )
        ]
    # A patch that carries a removed default back restores it (settled
    # below); its marker leaves ``removed_defaults`` first, or the plan model
    # refuses the constraint as a revival before the restore is reached (L4).
    resent = {c.get("default") for c in data.get("constraints", []) if c.get("default")}
    data["removed_defaults"] = [d for d in data.get("removed_defaults", []) if d not in resent]
    validated = expect_scoping_plan(validate_plan(OPTIONS_SCOPING, data))
    settled = settle_patched_defaults(validated, plan)
    return with_option_designs(settled, designs or {})


def _labelled_answer(payload: AnswerPayloadOut | None) -> AnswerPayloadOut | None:
    """Apply the read-time appraisal labels to one turn's citations (C2).

    ``appraise`` pins its labels as read-time copy and never persists them —
    a stored label could drift from its score — so a citation persists the
    numeric ``appraisal_score`` and every read boundary derives
    ``appraisal_label`` from it fresh, dropping the score. The chat route does
    this at ``conversations.py``'s projection; a Task Agent answer carries the
    same payload and owes the same boundary, or the raw score reaches the wire
    and the chip has nothing to render.

    Args:
        payload: The turn's citation half, or ``None`` on a turn with no answer.

    Returns:
        A copy with labelled citations, or the argument unchanged when there
        is no answer to label.
    """
    if payload is None:
        return None
    return payload.model_copy(
        update={"citations": apply_appraisal_labels(payload.citations)}
    )


def _labelled(turn: TaskAgentTurnOut) -> TaskAgentTurnOut:
    """Return one turn as the wire carries it: citations labelled, scores gone.

    Applied to what is **returned**, never to what is stored: the durable row
    keeps the score, which is what makes the label derivable at all.
    """
    if turn.answer is None:
        return turn
    return turn.model_copy(update={"answer": _labelled_answer(turn.answer)})


def _response_from_row(row: RowMapping) -> TaskAgentTurnOut:
    """Return a completed turn's stored projected response without recomputing it."""
    response = row["response"]
    if response is None:
        raise RuntimeError("completed task_agent transcript row has no response")
    return _labelled(TaskAgentTurnOut.model_validate(response))


def _validated_part(raw_part: object, profile: TaskAgentProfile) -> PartProposalOut | None:
    """Validate one task_agent part proposal, degrading malformed cards to prose.

    Args:
        raw_part: The optional runtime wire proposal returned by the task_agent.
        profile: The task's capability profile: its part vocabulary, and the
            parts whose options carry no primary.

    Returns:
        A standalone API proposal when it meets the card rules, else ``None``.
    """
    if raw_part is None:
        return None

    try:
        if isinstance(raw_part, BaseModel):
            raw_part = raw_part.model_dump(mode="json")
        part = PartProposalOut.model_validate(raw_part)
    except ValidationError:
        log.warning("task_agent_part_dropped", reason="invalid_shape")
        return None
    if part.id not in profile.part_ids:
        log.warning("task_agent_part_dropped", reason="invalid_part_id")
        return None
    if not 2 <= len(part.options) <= 4:
        log.warning("task_agent_part_dropped", reason="invalid_option_count")
        return None
    expected_primaries = 0 if part.id in profile.no_primary_parts else 1
    if sum(option.primary for option in part.options) != expected_primaries:
        log.warning("task_agent_part_dropped", reason="invalid_primary_count")
        return None
    # The confirm-marker grammar the client derives ✓-state from admits only
    # snake_case option ids; the rule lived in prompt text alone, so a
    # task_agent-emitted id like "quick-look" broke marker parsing after refresh
    # (review 028: security lane + Codex lane convergent finding).
    if any(_OPTION_ID_RE.fullmatch(option.id) is None for option in part.options):
        log.warning("task_agent_part_dropped", reason="invalid_option_id")
        return None
    for chip in part.chips or []:
        if chip.kind not in {"date_range", "country_list"}:
            continue
        try:
            decoded = json.loads(chip.value)
        except (TypeError, ValueError):
            log.warning("task_agent_part_dropped", reason="invalid_chip_json")
            return None
        if not isinstance(decoded, dict):
            log.warning("task_agent_part_dropped", reason="invalid_chip_json")
            return None
    return part


def _task_agent_inputs(
    conn: Connection, task_id: uuid.UUID, conversation_id: uuid.UUID, capability: str
) -> tuple[list[dict[str, str]], dict[str, object] | None]:
    """Rehydrate the exact task_agent context for one task_agent conversation."""
    rows = conn.execute(
        select(task_agent_transcript)
        .where(task_agent_transcript.c.task_id == task_id)
        .where(task_agent_transcript.c.conversation_id == conversation_id)
        .where(task_agent_transcript.c.status == "completed")
        .order_by(task_agent_transcript.c.turn_index.asc())
    ).mappings().all()
    turns: list[dict[str, str]] = []
    previous_draft: dict[str, object] | None = None
    for row in rows:
        reply = row["reply"]
        task_agent_state = row["task_agent_state"]
        if reply is None:
            raise RuntimeError("completed task_agent transcript row is incomplete")
        turns.extend((
            {"role": "user", "text": row["user_message"]},
            {"role": "planner", "text": reply},
        ))
        # A gate turn — an answer, an ask-back, a recorded decision — is part
        # of the conversation but carries no plan draft (task 044), so it adds
        # its exchange and leaves the draft where the last planning turn left
        # it. Only a row missing its *reply* is incomplete. A longlist turn's
        # state is its pending action (task 045), never a draft either.
        if task_agent_state is not None and not is_longlist_state(task_agent_state):
            previous_draft = cast("dict[str, object]", task_agent_state)
    if turns:
        return turns, previous_draft

    closed_predecessor = conn.execute(
        select(conversation.c.id)
        .where(conversation.c.task_id == task_id)
        .where(conversation.c.kind == "task_agent")
        .where(conversation.c.status == "closed")
        .order_by(conversation.c.closed_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if closed_predecessor is None:
        return turns, previous_draft

    plan_row = latest_approved_plan_row(conn, task_id)
    if plan_row is not None:
        # The successor is seeded from the plan that ran (task 044).
        executed = validate_plan(capability, plan_row["payload"])
        return [], spec_for(capability).task_agent.seed_draft(executed)
    return turns, previous_draft


def _transcript_out(row: RowMapping, capability: str) -> TaskAgentTranscriptTurnOut:
    """Project one durable transcript row into its honest read representation.

    A completed turn's ``kind``, ``answer`` and ``decision`` are read back off
    the response it stored, so a reloaded thread renders an answer with its
    citations and a decision as a decision — not as a bare reply (task 044).
    """
    stored = row["response"] if isinstance(row["response"], dict) else {}
    projected = TaskAgentTurnOut.model_validate(stored) if stored else None
    return TaskAgentTranscriptTurnOut(
        capability=capability,
        turn_index=row["turn_index"],
        conversation_id=row["conversation_id"],
        client_turn_id=row["client_turn_id"],
        user_message=row["user_message"],
        reply=row["reply"],
        suggestions=row["suggestions"],
        part=row["part"],
        status=row["status"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
        kind=projected.kind if projected is not None else None,
        # Read-time label mapping (C2), the same boundary the chat read model
        # applies: the durable payload carries ``appraisal_score``, the wire
        # carries ``appraisal_label``.
        answer=_labelled_answer(projected.answer) if projected is not None else None,
        decision=projected.decision if projected is not None else None,
        action=projected.action if projected is not None else None,
    )


@dataclass(frozen=True)
class _Reserved:
    """A durably reserved transcript row and the pause it arrived at.

    Args:
        transcript_id: The reserved (or retried) transcript row.
        gate: The baseline gate this turn must be sorted against, when the
            task's scoping walk is paused on one; ``None`` for an ordinary
            planning turn.
        retried: Whether this is a re-run of a row that was already reserved —
            the only case in which the row may already carry a durable half
            (X6), so the only case worth a query to look.
        longlist: The longlist this turn is sorted against, when the task is
            an options-scoping task with a longlist and no parentless walk is
            active (task 045, S11); ``None`` for every other turn.
    """

    transcript_id: uuid.UUID
    gate: PausedGate | None
    retried: bool = False
    longlist: LonglistSurface | None = None


def _paused_gate(
    conn: Connection, *, task_id: uuid.UUID, capability: str, active: RowMapping
) -> PausedGate | None:
    """Return the gate an admitted turn is sorted against, or ``None``.

    A turn is admitted at a pause only when every part of the affordance is
    there: an options-scoping task (an Evidence search pause refuses turns, as
    it always has), a *paused* walk, and an undecided pause offering options.
    Anything else keeps the ``run_active`` refusal — the fence narrows for one
    known shape, it does not open (A6).
    """
    if active["status"] != "paused":
        return None
    if capability != OPTIONS_SCOPING:
        return None
    return read_paused_gate(
        conn,
        task_id=task_id,
        capability_run_id=active["capability_run_id"],
        plan_version=int(active["plan_version"]),
    )


def _phase_one_turn(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    user_id: str,
    payload: TaskAgentTurnCreate,
) -> TaskAgentTurnOut | _Reserved:
    """Authenticate, fence, and either replay or durably reserve one turn."""
    # The row lock serialises phase one across processes: without it, two
    # processes can both read "no pending turn" / the same max turn_index and
    # the loser's INSERT dies on a unique constraint as a raw 500 (review
    # finding, 2026-07-29). The transaction is short — the LLM call stays
    # outside it (finding I2 rule).
    access = accessible_task(
        conn, task_id=task_id, user_id=user_id, write=True, for_update=True
    )
    capability = access.row["capability"]
    _expire_stale_pending_turns(conn, task_id)
    existing = conn.execute(
        select(task_agent_transcript)
        .where(task_agent_transcript.c.task_id == task_id)
        .where(task_agent_transcript.c.client_turn_id == payload.client_turn_id)
    ).mappings().one_or_none()
    if existing is not None:
        if existing["user_message"] != payload.message:
            raise ApiConflict(
                "stale_turn", "client turn id is already bound to a different message"
            )
        if existing["status"] == "completed":
            return _response_from_row(existing)

    # Parentless walks only (task 045, S15): a longlist walk's option searches
    # never fence the thread; their parent does.
    active = active_parentless_walk(conn, task_id)
    # The Task Agent chat is open at the baseline gate (D9): a turn taken while
    # a scoping walk is *paused* is admitted and sorted. A running walk, and
    # every other capability's pause, keep the refusal they always had.
    gate = (
        _paused_gate(conn, task_id=task_id, capability=capability, active=active)
        if active is not None
        else None
    )
    if active is not None and gate is None:
        raise ApiConflict(
            "run_active",
            "finish or stop the current run before replanning; "
            "use the run's check-ins to steer it",
        )
    # With no walk active, a scoping task that has a longlist sorts the turn
    # into the longlist verbs (task 045, S11), read under the same row lock.
    longlist = (
        read_longlist_surface(conn, task_id=task_id, capability=capability)
        if active is None
        else None
    )

    if existing is not None:
        latest_id = conn.execute(
            select(task_agent_transcript.c.id)
            .where(task_agent_transcript.c.task_id == task_id)
            .order_by(task_agent_transcript.c.turn_index.desc())
            .limit(1)
        ).scalar_one()
        if latest_id != existing["id"]:
            raise ApiConflict("stale_turn", "only the latest Task Agent turn may be retried")
        return _Reserved(cast(uuid.UUID, existing["id"]), gate, retried=True, longlist=longlist)

    pending = conn.execute(
        select(task_agent_transcript.c.id)
        .where(task_agent_transcript.c.task_id == task_id)
        .where(task_agent_transcript.c.status == "pending")
        .limit(1)
    ).scalar_one_or_none()
    if pending is not None:
        raise ApiConflict("task_agent_turn_in_progress", "a Task Agent turn is already running")

    conversation_id = ensure_active_task_agent_conversation(conn, task_id=task_id, now=_now())
    max_turn_index = conn.execute(
        select(func.coalesce(func.max(task_agent_transcript.c.turn_index), -1)).where(
            task_agent_transcript.c.task_id == task_id
        )
    ).scalar_one()
    transcript_id = uuid.uuid4()
    conn.execute(
        task_agent_transcript.insert().values(
            id=transcript_id,
            task_id=task_id,
            conversation_id=conversation_id,
            client_turn_id=payload.client_turn_id,
            turn_index=int(max_turn_index) + 1,
            user_message=payload.message,
            reply=None,
            task_agent_state=None,
            response=None,
            suggestions=[],
            status="pending",
            created_at=_now(),
            completed_at=None,
        )
    )
    return _Reserved(transcript_id, gate, longlist=longlist)


@dataclass(frozen=True)
class _ContinuedTurn:
    """A gate decision whose turn is only half over.

    Args:
        carried_text: The user's instruction, which the planner half of this
            same row now answers.
        decision: The decision already committed, carried into the row's final
            projection so one turn reports both halves.
    """

    carried_text: str
    decision: TurnDecisionOut


def _complete_gate_turn(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    transcript_id: uuid.UUID,
    result: TaskAgentTurnOut,
) -> None:
    """Commit one gate turn's durable projection.

    ``task_agent_state`` stays null: a gate turn carries no plan draft, and
    :func:`_task_agent_inputs` reads that as "this exchange happened, but it
    did not move the draft" — the planner still sees the conversation.
    """
    with engine.begin() as conn:
        transcript_rows.complete(
            conn, task_id=task_id, transcript_id=transcript_id, result=result
        )


def _persist_half_turn(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    transcript_id: uuid.UUID,
    half: TaskAgentTurnOut,
) -> None:
    """Record the durable half of a turn that is only half over (X6).

    A "change the plan" decision carrying an instruction commits the decision
    and *then* calls the planner. If that call crashes, the decision is
    already durable but the row is failed, and the retry sees no gate — the
    walk is gone — so it completes as an ordinary planning reply and the
    thread never shows the decision that ended the run.

    So the decision is written onto the reserved row the moment it is durable,
    with the row still ``pending``: a projection that is valid on its own (the
    transcript renders it as the decision it is) and that phase two reads back
    when it no longer has the decision in hand.
    """
    with engine.begin() as conn:
        conn.execute(
            transcript_rows.open_row(task_id, transcript_id).values(
                response=half.model_dump(mode="json")
            )
        )


def _stored_decision(conn: Connection, transcript_id: uuid.UUID) -> TurnDecisionOut | None:
    """Read back the decision a half-committed turn already recorded (X6).

    Returns ``None`` when the row carries no projection, or one that is not a
    decision — a retry of an ordinary planning turn, which is the common case.
    """
    stored = conn.execute(
        select(task_agent_transcript.c.response).where(
            task_agent_transcript.c.id == transcript_id
        )
    ).scalar_one_or_none()
    if not isinstance(stored, dict):
        return None
    try:
        projected = TaskAgentTurnOut.model_validate(stored)
    except ValidationError:
        log.warning("task_agent_stored_half_unreadable", transcript_id=str(transcript_id))
        return None
    return projected.decision if projected.kind == "decision" else None


def _dispatch_gate_turn(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    transcript_id: uuid.UUID,
    conversation_id: uuid.UUID,
    gate: PausedGate,
    utterance: str,
    user_id: str,
    agent: AgentBackend,
    chat_backend: ChatBackend,
    embedding_backend: EmbeddingBackend,
    executor: ThreadPoolExecutor,
    runner_backends: RunnerBackends,
) -> TaskAgentTurnOut | _ContinuedTurn:
    """Sort one turn taken at the gate and carry out what it turned out to be.

    Args:
        engine: Database engine.
        task_id: Task owning the paused walk.
        transcript_id: The reserved transcript row this turn completes.
        conversation_id: The owning Task Agent conversation.
        gate: The pause the turn arrived at.
        utterance: The user's verbatim turn text (what the row stores).
        user_id: Authenticated actor for the decision record.
        agent: Backend carrying the gate sort.
        chat_backend: Chat writer seam for an answer.
        embedding_backend: Retrieval embedder seam for an answer.
        executor: Walk executor, for a decision that resumes the walk.
        runner_backends: Runner bundle for that resumed walk.

    Returns:
        The completed turn, or the instruction the planning half of this same
        row now answers.

    Raises:
        Exception: Anything the sort's dispatch raises, with the row failed
            first so the caller may retry it.
    """

    def finish(result: TaskAgentTurnOut) -> TaskAgentTurnOut:
        _complete_gate_turn(engine, task_id=task_id, transcript_id=transcript_id, result=result)
        return result

    try:
        sort = gate_turns.sort_turn(
            agent, utterance=utterance, gate=gate, session_id=task_id
        )
        if sort.kind == "question":
            with engine.connect() as conn:
                window = transcript_rows.answer_window(conn, task_id, conversation_id)
            answer = gate_turns.answer_at_gate(
                engine,
                task_id=task_id,
                gate=gate,
                question=utterance,
                window=window,
                chat_backend=chat_backend,
                embedding_backend=embedding_backend,
                langfuse_client=tracing.get_langfuse(),
                trace_run_id=transcript_id,
                conversation_id=conversation_id,
            )
            if answer is None:
                # The card resumed the walk while the sort was running (C7):
                # there is no longer a paused walk to answer over. The turn is
                # still the user's and still durable — it says what happened,
                # the same way the loser of a decision race does.
                return finish(
                    TaskAgentTurnOut(
                        reply=gate_turns.ALREADY_ANSWERED_REPLY,
                        kind="reply",
                        capability=OPTIONS_SCOPING,
                        conversation_id=conversation_id,
                    )
                )
            answered = finish(TaskAgentTurnOut(
                reply=answer.prose,
                kind="answer",
                answer=AnswerPayloadOut.model_validate(answer.payload.as_payload()),
                capability=OPTIONS_SCOPING,
                # The decision stays the user's to take, on a turn that asked
                # and decided at once as much as on any other.
                suggestions=gate.option_labels,
                conversation_id=conversation_id,
            ))
            # Stored raw, returned labelled (C2): the score is the durable
            # fact and the label is derived on every read.
            return _labelled(answered)

        if sort.kind == "decision":
            option_id = cast(str, sort.option_id)
            outcome = gate_turns.commit_decision(
                engine,
                task_id=task_id,
                gate=gate,
                option_id=option_id,
                carried_text=sort.carried_text,
                # The utterance the carried instruction must be part of (S2):
                # what the planner is told is the user's own words, never the
                # sort's paraphrase of them.
                utterance=utterance,
                actor=user_id,
            )
            decision = TurnDecisionOut(
                option_id=option_id,
                label=cast(str, gate.label_for(option_id)),
                check_in_id=gate.check_in_id,
                capability_run_id=gate.capability_run_id,
                plan_version=gate.plan_version,
                opened_run=(
                    _open_follow_on_longlist(
                        engine,
                        task_id=task_id,
                        gate_run_id=gate.capability_run_id,
                        executor=executor,
                        runner_backends=runner_backends,
                        user_id=user_id,
                    )
                    if outcome.recorded and outcome.follow_on == LONGLIST_PURPOSE
                    else None
                ),
            )
            if outcome.carried_text is not None:
                # Durable now, because the planner call below can crash after
                # it and the decision must not be lost with it (X6).
                _persist_half_turn(
                    engine,
                    task_id=task_id,
                    transcript_id=transcript_id,
                    half=TaskAgentTurnOut(
                        reply=outcome.reply,
                        kind="decision",
                        decision=decision,
                        capability=OPTIONS_SCOPING,
                        conversation_id=conversation_id,
                    ),
                )
                return _ContinuedTurn(carried_text=outcome.carried_text, decision=decision)
            reply = outcome.reply
            if outcome.follow_on == LONGLIST_PURPOSE and decision.opened_run is None:
                # The decision stands but no walk opened (F12): say so.
                reply = gate_turns.CONFIRM_NOT_STARTED_REPLY
            result = finish(TaskAgentTurnOut(
                reply=reply,
                kind="decision",
                # A turn that lost the race records no decision of its own: the
                # durable one is the other surface's, and this turn may have
                # asked for the other option.
                decision=decision if outcome.recorded else None,
                capability=OPTIONS_SCOPING,
                conversation_id=conversation_id,
            ))
            if outcome.continue_walk is not None:
                _resume_walk(
                    engine,
                    task_id=task_id,
                    capability_run_id=outcome.continue_walk,
                    executor=executor,
                    runner_backends=runner_backends,
                    agent=agent,
                    user_id=user_id,
                )
            return result

        return finish(TaskAgentTurnOut(
            reply=gate_turns.ASK_BACK_REPLY,
            kind="reply",
            capability=OPTIONS_SCOPING,
            suggestions=gate.option_labels,
            conversation_id=conversation_id,
        ))
    except Exception:
        # A failure after the decision commit leaves the decision durable and
        # the row failed; the retry re-runs only the half that is still owed,
        # because the fence then sees no active walk (X6).
        transcript_rows.fail(engine, task_id=task_id, transcript_id=transcript_id)
        raise


def _open_follow_on_longlist(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    gate_run_id: uuid.UUID,
    executor: ThreadPoolExecutor,
    runner_backends: RunnerBackends,
    user_id: str,
) -> LatestRun | None:
    """Open the longlist walk a gate decision asked for (task 045, S3; P7).

    After the decision's commit and outside any transaction, on the version
    the gate's walk ran — the one the decision confirmed (A10). A refusal (the
    executor at capacity, a plan too long to screen against, a newer version
    minted meanwhile) does not undo
    the decision, which is durable, nor fail the turn: the turn records the
    decision without an opened walk, and the plan document's confirm action
    opens the walk later ("confirmed but no walk" is resolved there).

    Returns:
        The opened walk, or ``None`` when the opener refused.
    """
    try:
        run_id = open_longlist_walk(
            engine,
            task_id=task_id,
            plan_row=plan_row_of_walk(engine, task_id=task_id, capability_run_id=gate_run_id),
            backends=runner_backends,
            executor=executor,
            user_id=user_id,
        )
    except LonglistRefused as exc:
        log.warning("gate_turn_longlist_refused", task_id=str(task_id), reason=exc.reason)
        return None
    return opened_run(engine, task_id=task_id, capability_run_id=run_id)


def _resume_walk(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    capability_run_id: uuid.UUID,
    executor: ThreadPoolExecutor,
    runner_backends: RunnerBackends,
    agent: AgentBackend,
    user_id: str,
) -> None:
    """Claim and dispatch the walk a gate decision asked to continue.

    The same claim-then-execute the card route runs (``check_ins``): a decision
    taken in words must move the walk exactly as the same decision taken on the
    card does, or a confirmed walk would sit paused forever.
    """
    claim = continuation.claim_continuation(
        engine, task_id=task_id, capability_run_id=capability_run_id
    )
    if claim is None:
        return
    executor.submit(
        execute_claimed,
        engine,
        task_id=claim.task_id,
        capability_run_id=claim.capability_run_id,
        backends=runner_backends,
        agent=agent,
        user_id=user_id,
    )


@router.post("/{task_id}/task-agent-turns", response_model=TaskAgentTurnOut)
def create_task_agent_turn(
    task_id: uuid.UUID,
    payload: TaskAgentTurnCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    task_agent: Annotated[TaskAgentTurnBackend, Depends(get_task_agent_backend)],
    agent: Annotated[AgentBackend, Depends(get_agent_backend)],
    chat_backend: Annotated[ChatBackend, Depends(get_chat_backend)],
    embedding_backend: Annotated[EmbeddingBackend, Depends(get_chat_embedding_backend)],
    executor: Annotated[ThreadPoolExecutor, Depends(get_executor)],
    runner_backends: Annotated[RunnerBackends, Depends(get_runner_backends)],
) -> TaskAgentTurnOut:
    """Advance one task's durable task_agent conversation once per client turn id.

    Two capabilities share this route, and everything durable about it — the
    phase-one reservation, the idempotency key, the run fences, the transaction
    that joins the turn to the plan it approved — is shared with them. What the
    capability picks is which Task Agent is called, which plan model validates
    what it returns, and which of the two draft projections the turn carries
    back (task 044, C9).

    A turn that arrives while an options-scoping walk is paused on its baseline
    gate is admitted, sorted, and dispatched to an answer or a decision before
    any planner call (task 044, S5). One shape crosses back into the ordinary
    path: "change the plan" carrying an instruction commits the decision and
    then continues, on the *same* reserved row, as an ordinary planning turn.
    """
    lock = _turn_lock(task_id)
    if not lock.acquire(blocking=False):
        raise ApiConflict("task_agent_turn_in_progress", "a Task Agent turn is already running")
    try:
        # Phase 1 is deliberately short. The task_agent call below must remain
        # OUTSIDE any transaction: holding the task row lock (and a pool
        # connection) across a live LLM call blocked every mutation on the
        # task — and via the global dispatch lock, run creation process-wide
        # (review finding I2, 2026-07-21).
        with engine.begin() as conn:
            phase_one = _phase_one_turn(
                conn,
                task_id=task_id,
                user_id=user.user_id,
                payload=payload,
            )
        if isinstance(phase_one, TaskAgentTurnOut):
            return phase_one
        transcript_id = phase_one.transcript_id

        with engine.connect() as conn:
            conversation_id, reserved_turn_index = conn.execute(
                select(
                    task_agent_transcript.c.conversation_id,
                    task_agent_transcript.c.turn_index,
                ).where(task_agent_transcript.c.id == transcript_id)
            ).one()
        if conversation_id is None:
            raise RuntimeError("task_agent transcript turn has no conversation")

        planner_message = payload.message
        carried_decision: TurnDecisionOut | None = None
        if phase_one.gate is not None:
            # The gate sort and the answer core trace under the user too.
            with tracing.trace_scope(user_id=user.user_id):
                sorted_turn = _dispatch_gate_turn(
                    engine,
                    task_id=task_id,
                    transcript_id=transcript_id,
                    conversation_id=conversation_id,
                    gate=phase_one.gate,
                    utterance=payload.message,
                    user_id=user.user_id,
                    agent=agent,
                    chat_backend=chat_backend,
                    embedding_backend=embedding_backend,
                    executor=executor,
                    runner_backends=runner_backends,
                )
            if isinstance(sorted_turn, TaskAgentTurnOut):
                return sorted_turn
            # "Change the plan" with an instruction: the decision is already
            # durable, the walk has ended, and this same row now continues as
            # an ordinary planning turn on the user's own words (X6).
            planner_message = sorted_turn.carried_text
            carried_decision = sorted_turn.decision
        elif phase_one.longlist is not None:
            # While a longlist exists and no walk is active, the turn is
            # sorted into the longlist verbs and never reaches the planner:
            # a verb is proposed back and applied on a confirming turn
            # (task 045, S11). Stored raw, returned labelled (C2).
            with tracing.trace_scope(user_id=user.user_id):
                return _labelled(
                    dispatch_longlist_turn(
                        engine,
                        task_id=task_id,
                        transcript_id=transcript_id,
                        conversation_id=conversation_id,
                        surface=phase_one.longlist,
                        utterance=payload.message,
                        user_id=user.user_id,
                        agent=agent,
                        chat_backend=chat_backend,
                        embedding_backend=embedding_backend,
                        runner_backends=runner_backends,
                    )
                )
        elif phase_one.retried:
            # A retry of the *second* half of such a turn: the walk is already
            # gone, so there is no gate to sort against and the decision lives
            # only on the row. Read it back, or the thread would render this
            # turn as an ordinary reply and lose the decision that ended the
            # run (X6).
            with engine.connect() as conn:
                carried_decision = _stored_decision(conn, transcript_id)

        with engine.connect() as conn:
            capability = capability_of_task(conn, task_id)
            profile = spec_for(capability).task_agent
            turns, previous_draft = _task_agent_inputs(conn, task_id, conversation_id, capability)
            inputs = profile.load_inputs(conn, task_id)
        turns.append({"role": "user", "text": planner_message})
        try:
            # The Task Agent's own session scope nests under this user scope
            # (ADR 0038; ported from the pre-rename planning router at the
            # dev merge of 2026-09-18).
            with tracing.trace_scope(user_id=user.user_id):
                turn = task_agent.turn(
                    profile,
                    turns,
                    previous_draft,
                    inputs=inputs,
                    session_id=task_id,
                    conversation_id=conversation_id,
                )
        except Exception:
            transcript_rows.fail(engine, task_id=task_id, transcript_id=transcript_id)
            raise

        ready = turn.ready
        approved: AnyPlan | None = None
        if ready:
            try:
                approved = profile.build_plan(turn.plan_draft, inputs, int(reserved_turn_index))
            except (ValidationError, ValueError):
                ready = False
        reply_text = turn.reply
        if approved is not None and profile.after_approve is not None:
            # Outside any transaction, like the Task Agent call: options
            # scoping proposes option designs here (D19) and adds the
            # "did this touch the baseline's inputs" sentence (S4, C1).
            with tracing.trace_scope(user_id=user.user_id):
                approved, note = profile.after_approve(engine, task_id, approved, agent)
            if note is not None:
                reply_text = f"{turn.reply.rstrip()}\n\n{note}"
        part = _validated_part(turn.part, profile)
        draft = (
            profile.draft_from_plan(approved)
            if approved is not None
            else profile.draft_from_wire(turn.plan_draft, ready, inputs)
        )
        result = TaskAgentTurnOut(
            reply=reply_text,
            **plan_slot(draft, scoping_slot="scoping_plan"),
            capability=capability,
            suggestions=turn.suggested_answers or [],
            part=part,
            conversation_id=conversation_id,
            # One turn, two halves: the decision that ended the walk and
            # the planning reply that followed it are both this row's (X6).
            kind="decision" if carried_decision is not None else None,
            decision=carried_decision,
        )
        # Phase 2 joins plan approval in the same transaction, so an approved
        # plan can never commit without the transcript turn that approved it.
        run_started_meanwhile = False
        with engine.begin() as conn:
            if approved is not None:
                accessible_task(
                    conn, task_id=task_id, user_id=user.user_id, write=True, for_update=True
                )
                # Re-check the run fence under the task row lock: a run may
                # have started during the out-of-transaction task_agent call, and
                # persisting a new approved plan under a live walk would hand
                # continuation an unrelated plan (adversarial review,
                # 2026-07-29). Mirror phase one: fail the turn, same conflict.
                # The same parentless fence as phase one (task 045).
                run_started_meanwhile = active_parentless_walk(conn, task_id) is not None
            if run_started_meanwhile:
                conn.execute(
                    transcript_rows.open_row(task_id, transcript_id).values(
                        status="failed", completed_at=_now()
                    )
                )
            else:
                # A fresh turn completes from "pending"; a retried latest turn
                # re-runs in place from "failed" (retry rules, plan pin 2).
                transcript_rows.complete(
                    conn,
                    task_id=task_id,
                    transcript_id=transcript_id,
                    result=result,
                    extra={
                        "task_agent_state": turn.plan_draft.model_dump(mode="json"),
                        "part": part.model_dump(mode="json") if part is not None else None,
                    },
                )
                if approved is not None:
                    approved.source_turn_index = int(reserved_turn_index)
                    persist_approved_plan(
                        conn,
                        task_id=task_id,
                        plan=approved,
                        conversation_id=conversation_id,
                    )
                    conn.execute(
                        update(conversation)
                        .where(conversation.c.id == conversation_id)
                        .where(conversation.c.task_id == task_id)
                        .values(title=approved.title)
                    )
        if run_started_meanwhile:
            raise ApiConflict(
                "run_active",
                "a run started while this turn was being planned; "
                "finish or stop it, then retry the turn",
            )
        return result
    finally:
        lock.release()


@router.get("/{task_id}/task-agent-turns", response_model=Page[TaskAgentTranscriptTurnOut])
def list_task_agent_turns(
    task_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
) -> Page[TaskAgentTranscriptTurnOut]:
    """Return the durable task_agent transcript in ascending conversation order.

    **Read-graded, and the sweep is owner-only.** The grade here is the read
    grade — owner ∪ same-org colleague ∪ administrator — but
    :func:`_expire_stale_pending_turns` is a *write*, and contract § 3 makes
    the admin leg read-only: a support read that fails somebody else's pending
    Task Agent turn is a mutation nobody asked for and nothing records. So the
    sweep runs only for the owner, whose own turn it is. Nothing is lost: the
    owner's own GET sweeps, and every mutating task_agent path sweeps under the
    write grade before it does anything.
    """
    with engine.begin() as conn:
        access = accessible_task(
            conn, task_id=task_id, user_id=user.user_id, write=False
        )
        if access.is_owner:
            _expire_stale_pending_turns(conn, task_id)
        total_items = conn.execute(
            select(func.count())
            .select_from(task_agent_transcript)
            .where(task_agent_transcript.c.task_id == task_id)
        ).scalar_one()
        rows = conn.execute(
            select(task_agent_transcript)
            .where(task_agent_transcript.c.task_id == task_id)
            .order_by(task_agent_transcript.c.turn_index.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).mappings().all()
    return Page(
        data=[_transcript_out(row, access.row["capability"]) for row in rows],
        pagination=PageMeta(page=page, page_size=page_size, total_items=total_items),
    )


@router.get("/{task_id}/plan", response_model=PlanOut)
def get_plan(
    task_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
) -> PlanOut:
    """Return the durable approved plan or latest completed durable draft.

    Owner-only sweep, for the reason :func:`list_task_agent_turns` states: a
    colleague's or an administrator's read must not write the owner's rows.
    """
    with engine.begin() as conn:
        access = accessible_task(
            conn, task_id=task_id, user_id=user.user_id, write=False
        )
        if access.is_owner:
            _expire_stale_pending_turns(conn, task_id)
        capability = access.row["capability"]
        if capability == OPTIONS_SCOPING:
            return _scoping_plan_out(conn, task_id)
        row, plan, latest = _current_es_plan(conn, task_id, capability)
    if row is not None and plan is not None:
        return _plan_out(EVIDENCE_SEARCH, plan, row)
    if latest is None or latest["response"] is None:
        raise HTTPException(status_code=404, detail="resource not found")
    response = TaskAgentTurnOut.model_validate(latest["response"])
    return PlanOut(plan=response.plan, capability=EVIDENCE_SEARCH, version=0, status="draft")


def _current_es_plan(
    conn: Connection, task_id: uuid.UUID, capability: str
) -> tuple[RowMapping | None, TaskPlan | None, RowMapping | None]:
    """Return what an Evidence search task's plan currently is.

    The approved plan stands unless a newer Task Agent turn completed after
    it was approved; then the latest completed turn's draft stands instead.

    Returns:
        The latest approved row, its plan when it still stands (else
        ``None``), and the latest completed turn (``turn_index``,
        ``response``, ``conversation_id``).
    """
    row = latest_approved_plan_row(conn, task_id)
    latest = conn.execute(
        select(
            task_agent_transcript.c.turn_index,
            task_agent_transcript.c.response,
            task_agent_transcript.c.conversation_id,
        )
        .where(task_agent_transcript.c.task_id == task_id)
        .where(task_agent_transcript.c.status == "completed")
        .order_by(task_agent_transcript.c.turn_index.desc())
        .limit(1)
    ).mappings().one_or_none()
    if row is None:
        return None, None, latest
    plan = expect_task_plan(validate_plan(capability, row["payload"]))
    stale = (
        plan.source_turn_index is not None
        and latest is not None
        and plan.source_turn_index < latest["turn_index"]
    )
    return row, None if stale else plan, latest


def _latest_completed_turn(conn: Connection, task_id: uuid.UUID) -> int | None:
    """Return the task's latest completed Task Agent turn index, or ``None``."""
    value = conn.execute(
        select(func.max(task_agent_transcript.c.turn_index))
        .where(task_agent_transcript.c.task_id == task_id)
        .where(task_agent_transcript.c.status == "completed")
    ).scalar_one()
    return int(value) if value is not None else None


def _persist_version(
    conn: Connection, task_id: uuid.UUID, plan: AnyPlan, conversation_id: uuid.UUID | None
) -> RowMapping:
    """Persist ``plan`` as the next approved version, stamped with the latest turn.

    Returns:
        The new approved ``task_plan`` row.
    """
    latest_turn = _latest_completed_turn(conn, task_id)
    if latest_turn is not None:
        plan.source_turn_index = latest_turn
    if conversation_id is None:
        conversation_id = ensure_active_task_agent_conversation(
            conn, task_id=task_id, now=_now()
        )
    persist_approved_plan(conn, task_id=task_id, plan=plan, conversation_id=conversation_id)
    return cast(RowMapping, latest_approved_plan_row(conn, task_id))


_DISCRETIONARY_ORDER = (
    "characterise",
    "screen_full",
    "select",
    "extract",
    "group",
)


def _runtime_plan_from_draft(draft: PlanDraft) -> TaskPlan:
    """Build an executable plan from the GET-plan draft projection."""
    values = draft.model_dump(mode="json", exclude_none=True)
    values.pop("steps", None)
    values.pop("ready", None)
    values.pop("time_band", None)
    values.pop("expected_artefact_shape", None)
    constraints = values.pop("scope_constraints", None)
    if isinstance(constraints, dict):
        for key, value in constraints.items():
            if value is not None:
                values[key] = value
    return build_plan(PlanDraftWire.model_validate(values))


def _iso_from_geography_token(token: str) -> str | None:
    compact = token.strip()
    if compact == "":
        return None
    try:
        return validate_iso_alpha2([compact])[0]
    except SearchDirectiveError:
        pass
    overton_to_iso = {name.casefold(): code for code, name in OVERTON_COUNTRY_DISPLAY.items()}
    matched = overton_to_iso.get(compact.casefold())
    if matched is not None:
        return matched
    iso_name_to_code = {name.casefold(): code for code, name in ISO_3166_ALPHA2.items()}
    return iso_name_to_code.get(compact.casefold())


#: Every geography constraint field, cleared.
_NO_GEO: dict[str, Any] = {
    "publisher_country": None,
    "author_affiliation_countries": None,
    "country_group": None,
    "publisher_source": None,
}


def _geography_constraints(geography: str, backend_scope: str) -> dict[str, Any]:
    """Compile a geography overlay string into scope-constraint fields."""
    if geography == "":
        return dict(_NO_GEO)
    if geography.strip().casefold() in {"apo", "australian policy online"}:
        if backend_scope != "grey_lit_only":
            raise ValueError(
                "the APO restriction needs Sources set to policy literature only"
            )
        return {**_NO_GEO, "publisher_source": "apo"}
    if geography in TIER1_GROUPS:
        return {
            **_NO_GEO,
            "country_group": {
                "label": geography,
                "countries": None,
                "authorship": "pinned-table",
            },
        }
    tokens = [part.strip() for part in geography.split(",") if part.strip() != ""]
    codes: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        code = _iso_from_geography_token(token)
        if code is None:
            raise ValueError(f"unknown geography {token!r}")
        if code not in seen:
            seen.add(code)
            codes.append(code)
    if not codes:
        raise ValueError("geography must name a country or a known group")
    constraints = dict(_NO_GEO)
    if len(codes) == 1:
        if backend_scope != "grey_lit_only":
            constraints["author_affiliation_countries"] = codes
        if backend_scope != "academic_only":
            names = overton_display_names(codes)
            if names:
                constraints["publisher_country"] = next(iter(names))
        return constraints
    if backend_scope == "academic_only":
        constraints["author_affiliation_countries"] = codes
        return constraints
    if backend_scope == "grey_lit_only":
        names = overton_display_names(codes)
        if len(names) == 1:
            constraints["publisher_country"] = next(iter(names))
            return constraints
        raise ValueError("policy literature geography must resolve to one Overton country")
    constraints["country_group"] = {
        "label": geography,
        "countries": codes,
        "authorship": "user-amended",
    }
    return constraints


def _drop_scope_incompatible_geo(constraints: dict[str, Any], backend_scope: str) -> None:
    if backend_scope == "academic_only":
        constraints["publisher_country"] = None
    elif backend_scope == "grey_lit_only":
        constraints["author_affiliation_countries"] = None
    if backend_scope != "grey_lit_only":
        constraints["publisher_source"] = None


def _apply_plan_patch(plan: TaskPlan, patch: PlanPatchIn) -> TaskPlan:
    """Merge a user patch onto an executable plan and re-validate."""
    fields = patch.model_fields_set
    data = plan.model_dump(mode="json")
    for name in (
        "question",
        "backend_scope",
        "search_effort",
        "analysis_depth",
        "steering_mode",
        "screening_criteria",
    ):
        value = getattr(patch, name)
        if name in fields and value is not None:
            data[name] = value
    if "analysis_depth" in fields and patch.analysis_depth is not None:
        enabled = _enabled_components(patch.analysis_depth)
        data["components"] = [name for name in _DISCRETIONARY_ORDER if name in enabled]
        data["expected_artefact_shape"] = ""
        data["time_band"] = ""
        if "extract" not in enabled:
            data["extract_profiles"] = None
        if "group" not in enabled:
            data["grouping_facets"] = None
    constraints = dict(data.get("scope_constraints") or {})
    if "published_after" in fields:
        constraints["published_after"] = (
            None if patch.published_after == "" else patch.published_after
        )
    if "published_before" in fields:
        constraints["published_before"] = (
            None if patch.published_before == "" else patch.published_before
        )
    if "geography" in fields and patch.geography is not None:
        constraints.update(_geography_constraints(patch.geography, data["backend_scope"]))
    _drop_scope_incompatible_geo(constraints, data["backend_scope"])
    data["scope_constraints"] = constraints
    if "search_effort" in fields or "analysis_depth" in fields:
        data["time_band"] = ""
        data["expected_artefact_shape"] = ""
    # Constant capability: the patch shape and the plan it amends are both
    # Evidence search (the caller passed a ``TaskPlan``). Through the registry
    # all the same (C9).
    return expect_task_plan(validate_plan(EVIDENCE_SEARCH, data))


def _load_editable_plan(
    conn: Connection, task_id: uuid.UUID, capability: str
) -> tuple[TaskPlan, uuid.UUID | None]:
    """Return the plan GET would show, as an executable TaskPlan."""
    row, plan, latest = _current_es_plan(conn, task_id, capability)
    if row is not None and plan is not None:
        return plan, row["conversation_id"]
    if latest is None or latest["response"] is None:
        raise HTTPException(status_code=404, detail="resource not found")
    response = TaskAgentTurnOut.model_validate(latest["response"])
    if response.plan is None:
        raise HTTPException(status_code=422, detail="plan is not ready to edit")
    conversation_id = row["conversation_id"] if row is not None else None
    if conversation_id is None:
        conversation_id = latest["conversation_id"]
    try:
        return _runtime_plan_from_draft(response.plan), conversation_id
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="plan is not ready to edit") from exc


@router.patch("/{task_id}/plan", response_model=PlanOut)
def patch_plan(
    task_id: uuid.UUID,
    payload: PlanPatchIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    agent: Annotated[AgentBackend, Depends(get_agent_backend)],
) -> PlanOut:
    """Apply typed edits to the current plan and persist a new approved version."""
    designs: dict[str, OptionDesign] = {}
    if payload.scoping is not None and payload.scoping.your_options is not None:
        # Model calls stay outside the locked transaction below (review
        # finding I2): propose designs for the new or reworded options first.
        designs = _propose_patch_designs(engine, task_id, user.user_id, payload.scoping, agent)
    with engine.begin() as conn:
        # The task row lock, for the reason ``POST /runs`` and the turn route
        # take it (X5): the "no running/paused walk" check below and the new
        # version's insert must be one atomic decision, or two concurrent
        # edits both read the same latest version and the loser surfaces
        # ``uq_plan_task_version`` as a raw 500.
        access = accessible_task(
            conn, task_id=task_id, user_id=user.user_id, write=True, for_update=True
        )
        _expire_stale_pending_turns(conn, task_id)
        run_active = (
            conn.execute(
                select(capability_run.c.status)
                .where(capability_run.c.task_id == task_id)
                .where(capability_run.c.status.in_(("running", "paused")))
                .limit(1)
            ).scalar_one_or_none()
            is not None
        )
        if run_active:
            raise ApiConflict(
                "run_active",
                "a run is in progress; finish or stop it, then edit the plan",
            )
        capability = access.row["capability"]
        es_fields = payload.model_fields_set - {"scoping"}
        if capability == OPTIONS_SCOPING:
            if es_fields:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"{sorted(es_fields)} are Evidence search plan fields; "
                        "edit an options-scoping plan through 'scoping'"
                    ),
                )
            if payload.scoping is None:
                raise HTTPException(status_code=422, detail="scoping edits are required")
            return _patch_scoping_plan(conn, task_id, payload.scoping, designs=designs)
        if payload.scoping is not None:
            raise HTTPException(
                status_code=422,
                detail="'scoping' edits an options-scoping plan, not an Evidence search one",
            )
        current, conversation_id = _load_editable_plan(conn, task_id, capability)
        try:
            patched = _apply_plan_patch(current, payload)
        except (ValidationError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        row = _persist_version(conn, task_id, patched, conversation_id)
    return _plan_out(EVIDENCE_SEARCH, patched, row)


def _persist_new_scoping_version(
    conn: Connection, task_id: uuid.UUID, plan: ScopingPlan
) -> PlanOut:
    """Write one new approved scoping plan version and return it.

    The version is minted through ``persist_approved_plan``, which for a
    scoping plan inserts a **new** scope row carrying ``purpose='baseline'``
    and the new ``plan_id`` (C3) — never a copy of the previous version's
    scope id, so "which plan version was this baseline built from" keeps one
    answer per version.
    """
    conversation_id = conn.execute(
        select(task_plan.c.conversation_id)
        .where(task_plan.c.task_id == task_id)
        .order_by(task_plan.c.version.desc())
        .limit(1)
    ).scalar_one_or_none()
    return _plan_out(OPTIONS_SCOPING, plan, _persist_version(conn, task_id, plan, conversation_id))


def _propose_patch_designs(
    engine: Engine,
    task_id: uuid.UUID,
    user_id: str,
    patch: Any,
    agent: AgentBackend,
) -> dict[str, OptionDesign]:
    """Propose designs for a patch's new or reworded options, before its transaction.

    Keyed by the options' words; the transaction applies them to whichever
    options still lack a design (task 045, D19). Returns nothing when the
    caller may not write the task or it has no approved scoping plan — the
    locked transaction then refuses the patch as it always has.
    """
    with engine.connect() as conn:
        accessible_task(conn, task_id=task_id, user_id=user_id, write=True)
        if capability_of_task(conn, task_id) != OPTIONS_SCOPING:
            return {}
        current = latest_approved_scoping_plan(conn, task_id)
    if current is None:
        return {}
    texts = [o.text for o in patch.your_options]
    missing = [
        o.text
        for o in merge_your_options(texts, current.your_options, turn_index=0)
        if o.design is None
    ]
    if not missing:
        return {}
    target_unit = patch.target_unit.text if patch.target_unit is not None else None
    outcomes = [o.text for o in patch.outcomes] if patch.outcomes is not None else None
    with tracing.trace_scope(user_id=user_id):
        return propose_option_designs(
            missing,
            question=current.question,
            target_unit=target_unit or current.target_unit.text,
            outcomes=outcomes or [o.text for o in current.outcomes],
            backend=agent,
            session_id=task_id,
        )


def _patch_scoping_plan(
    conn: Connection,
    task_id: uuid.UUID,
    patch: Any,
    *,
    designs: dict[str, OptionDesign] | None = None,
) -> PlanOut:
    """Apply typed scoping edits and persist a new approved version."""
    current, _row = _load_approved_scoping_plan(conn, task_id)
    latest_turn = _latest_completed_turn(conn, task_id)
    try:
        patched = _apply_scoping_patch(
            current,
            patch,
            turn_index=latest_turn if latest_turn is not None else 0,
            designs=designs,
        )
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _persist_new_scoping_version(conn, task_id, patched)


@router.post("/{task_id}/plan/confirm-baseline", response_model=PlanOut)
def confirm_baseline(
    task_id: uuid.UUID,
    payload: ConfirmBaselineIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    executor: Annotated[ThreadPoolExecutor, Depends(get_executor)],
    backends: Annotated[RunnerBackends, Depends(get_runner_backends)],
) -> PlanOut:
    """Record that a plan version was confirmed, and open the longlist walk.

    "Confirm plan and build longlist" cannot be a steering event: by the time
    the user presses it the walk has ended, and a steering event needs a
    ``capability_run`` to hang on (S4, X5). So the confirmation is
    **plan-scoped** — a new approved plan version carrying
    ``baseline_confirmed`` — which History already renders and which task 2's
    longlist walk will read as its opening decision.

    Idempotent by construction: confirming the same ``(artefact_id,
    plan_version)`` pair that the current version already records returns that
    version unchanged rather than minting an identical one, so a double-tap
    does not fill the plan's history with duplicates.

    **The longlist walk** (task 045, S3): once the confirmed version has
    committed, the route re-reads it and opens the longlist walk on it outside
    any transaction (P6: the task-row transaction is closed before the opener
    takes the dispatch lock, the order ``create_run`` uses), returning the walk
    in ``opened_run``. On the idempotent path a version already confirmed but
    without a longlist walk — the opener refused, or the process died between
    the two — opens one now rather than returning unchanged. A confirm on a
    newer version than the last longlist's is a **rebuild** (D14): it opens a
    longlist walk too, whose fan-out searches only entrants without a search.
    """
    idempotent = False
    with engine.begin() as conn:
        # Locked for the same reason :func:`patch_plan` locks (X5): the walk
        # check and the new version's insert are one decision, and two
        # simultaneous confirms must serialise rather than race the plan's
        # version unique constraint into a 500.
        access = accessible_task(
            conn, task_id=task_id, user_id=user.user_id, write=True, for_update=True
        )
        if access.row["capability"] != OPTIONS_SCOPING:
            raise HTTPException(
                status_code=422,
                detail="confirm-baseline applies to options-scoping tasks only",
            )
        # Parentless walks only (task 045, S15).
        if active_parentless_walk(conn, task_id) is not None:
            raise ApiConflict(
                "run_active",
                "a run is in progress; finish or stop it, then confirm the plan",
            )
        current, row = _load_approved_scoping_plan(conn, task_id)
        is_baseline_artefact = conn.execute(
            select(artefact.c.artefact_id)
            .where(artefact.c.artefact_id == payload.artefact_id)
            .where(artefact.c.task_id == task_id)
            .limit(1)
        ).scalar_one_or_none()
        if is_baseline_artefact is None:
            raise HTTPException(status_code=404, detail="resource not found")
        # The record is minted as a NEW approved version and names THAT version
        # (its content is the confirmed version's), so "the record names the
        # current version" holds until the next edit mints a version without
        # it. Found by the 044 live check: stamping the previous number left the
        # plan document and the Result band saying "awaiting your confirmation".
        # A double-tap — the same body again, whether it still names the
        # version it read or the one the first tap minted — returns the current
        # version unchanged.
        current_version = int(row["version"])
        if (
            current.baseline_confirmed is not None
            and current.baseline_confirmed.artefact_id == payload.artefact_id
            and current.baseline_confirmed.plan_version == current_version
            and payload.plan_version in (current_version, current_version - 1)
        ):
            idempotent = True
            out = _plan_out(OPTIONS_SCOPING, current, row)
        else:
            if payload.plan_version != current_version:
                raise ApiConflict(
                    "plan_stale",
                    "the plan moved on since you read it — review the current version, "
                    "then confirm",
                )
            try:
                # Refused before a version is minted: a plan the longlist
                # cannot screen against must not read as confirmed.
                compose_longlist_screen_intent(current)
            except ValueError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "the plan's outcomes and requirements are too long to screen a "
                        f"longlist against — shorten them, then confirm ({exc})"
                    ),
                ) from exc
            next_version = int(
                conn.execute(
                    select(func.coalesce(func.max(task_plan.c.version), 0)).where(
                        task_plan.c.task_id == task_id
                    )
                ).scalar_one()
            ) + 1
            record = BaselineConfirmed(
                artefact_id=payload.artefact_id, plan_version=next_version
            )
            confirmed = current.model_copy(update={"baseline_confirmed": record})
            out = _persist_new_scoping_version(conn, task_id, confirmed)
    # Committed. The opener takes the dispatch lock and the task row itself.
    if idempotent and longlist_walk_exists(engine, task_id=task_id, plan_id=row["plan_id"]):
        return out
    return _open_confirmed_longlist(
        engine, task_id=task_id, out=out, executor=executor, backends=backends, user=user
    )


def _open_confirmed_longlist(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    out: PlanOut,
    executor: ThreadPoolExecutor,
    backends: RunnerBackends,
    user: AuthenticatedUser,
) -> PlanOut:
    """Open the longlist walk on the committed confirmed version (P6).

    Re-reads exactly the version the route committed (``out.version``) and
    hands it to the opener, which refuses if another version has been minted
    since (A10). Called outside any transaction.

    Returns:
        ``out`` with ``opened_run`` set.

    Raises:
        ApiConflict: The opener's ``run_active``, ``capacity`` or
            ``plan_stale``.
        HTTPException: 422 when the plan cannot be screened against.
    """
    with engine.connect() as conn:
        plan_row = conn.execute(
            select(task_plan)
            .where(task_plan.c.task_id == task_id)
            .where(task_plan.c.version == out.version)
        ).mappings().one()
    try:
        run_id = open_longlist_walk(
            engine,
            task_id=task_id,
            plan_row=dict(plan_row),
            backends=backends,
            executor=executor,
            user_id=user.user_id,
        )
    except LonglistRefused as exc:
        raise http_error(exc) from None
    return out.model_copy(
        update={"opened_run": opened_run(engine, task_id=task_id, capability_run_id=run_id)}
    )
