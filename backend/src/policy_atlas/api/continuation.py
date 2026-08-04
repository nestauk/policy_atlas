"""Durable API-side continuation protocol for parked capability walks.

The module deliberately contains no HTTP framework code.  Callers translate its
domain exceptions and result objects into their transport contract, then dispatch
``execute_continuation`` on their own worker executor.
"""

from __future__ import annotations

import copy
import threading
import uuid
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

import structlog
from sqlalchemy import select, update
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.locks import project_lock
from policy_atlas.core import events
from policy_atlas.core.schema import capability_run, characterisation_result, orchestration_plan
from policy_atlas.runtime import runner as runner_module
from policy_atlas.runtime import steering_events
from policy_atlas.runtime.continuation_state import ResumeDecision, build
from policy_atlas.runtime.orchestration_plan import compose
from policy_atlas.runtime.orchestrator_backend import OrchestratorBackend
from policy_atlas.runtime.runner import RunPlanOutcome, run_plan
from policy_atlas.runtime.steering import (
    Adjust,
    FanOut,
    PausePoint,
    ReEnterSegment,
    RerunSurface,
    SteeringAdjustmentError,
    SteeringDeltaInvalid,
    SteeringValidationCtx,
    apply_adjustment,
    apply_replacement_rerun,
    apply_segment_reentry,
    compile_fanout,
    pause_points,
    render_fanout_confirmation,
    validate_steering_delta,
)

log = structlog.get_logger()

_COMPILE_CACHE_LIMIT = 128
_COMPILE_CACHE: OrderedDict[str, _PendingCompilation] = OrderedDict()
_COMPILE_CACHE_LOCK = threading.Lock()


class ConfirmTokenExpiredError(Exception):
    """A free-text confirm token was lost to restart/eviction — recompile to proceed.

    Distinct from ``LookupError`` so the router can surface the recovery action
    (409 ``confirm_expired``) instead of an opaque 404 (review finding m3).
    """


class AlreadyAnsweredError(Exception):
    """Raised when a check-in already has a durable decision."""


class InvalidResponseError(ValueError):
    """Raised when a response is outside the pause's durable affordances."""


@dataclass(frozen=True)
class AnswerResult:
    """The durable result of answering a parked check-in.

    Args:
        capability_run_id: Parked walk that received the answer.
        decision_event_id: Appended steering-decision event identity.
        continuation_requested: Whether a worker should be dispatched.
    """

    capability_run_id: uuid.UUID
    decision_event_id: uuid.UUID
    continuation_requested: bool


@dataclass(frozen=True)
class CompiledSteer:
    """A free-text fan-out awaiting explicit confirmation.

    Args:
        render: Deterministic confirmation render.
        confirm_token: Process-local opaque token for the compiled fan-out.
    """

    render: str
    confirm_token: str


@dataclass(frozen=True)
class ClaimedContinuation:
    """A continuation atomically claimed for execution.

    Args:
        project_id: Project owning the walk.
        capability_run_id: Walk to execute.
        requested_event_id: Durable continuation-request event.
        decision_event_id: Steering decision being resumed from.
    """

    project_id: uuid.UUID
    capability_run_id: uuid.UUID
    requested_event_id: uuid.UUID
    decision_event_id: uuid.UUID


@dataclass(frozen=True)
class SweepReport:
    """The work discovered during API startup recovery.

    Args:
        interrupted_capability_run_ids: Running walks honestly marked interrupted.
        redispatch: Unclaimed parked continuations, ordered for dispatch.
        reexecute: Walks whose continuation was claimed but never made component
            progress before the process died — the claim is durable, the walk sat
            at a clean boundary, so the sweep re-executes rather than interrupts
            (review finding, 2026-07-21: interrupting here discarded a
            just-answered multi-day park).
    """

    interrupted_capability_run_ids: tuple[uuid.UUID, ...]
    redispatch: tuple[ClaimedContinuation, ...]
    reexecute: tuple[ClaimedContinuation, ...] = ()


@dataclass(frozen=True)
class _Pause:
    """A pending durable pause and its event attachment."""

    capability_run_id: uuid.UUID
    event_id: uuid.UUID
    run_id: uuid.UUID
    sequence: int
    payload: dict[str, Any]


@dataclass(frozen=True)
class _PendingCompilation:
    """A process-local compiled fan-out awaiting confirmation."""

    project_id: uuid.UUID
    check_in_id: uuid.UUID
    capability_run_id: uuid.UUID
    fanout: FanOut
    user_text: str


def answer_check_in(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    check_in_id: uuid.UUID,
    response: Any,
    actor: str,
    orchestrator: OrchestratorBackend | None = None,
) -> AnswerResult:
    """Persist one canonical check-in response and its continuation request.

    Args:
        engine: Database engine.
        project_id: Project owning the parked walk.
        check_in_id: Durable ``steering.pause`` event identity.
        response: Transport response model or mapping with a ``kind`` field.
        actor: Authenticated actor recorded in logs.
        orchestrator: Present for API symmetry; free text uses
            :func:`compile_free_text` and is not applied here.

    Returns:
        The committed answer result.

    Raises:
        LookupError: If the project, check-in, or parked run is absent.
        AlreadyAnsweredError: If this pause was already decided.
        InvalidResponseError: If the response is not in the durable affordance set.
    """
    del orchestrator
    with engine.begin() as conn:
        project_lock(conn, project_id)
        pause = _pending_pause(conn, project_id=project_id, check_in_id=check_in_id)
        state = build(engine, project_id=project_id, capability_run_id=pause.capability_run_id)
        kind = _field(response, "kind")
        if kind == "free_text":
            raise InvalidResponseError("free text must be compiled before it is confirmed")
        if kind == "free_text_confirm":
            raise InvalidResponseError("free-text confirmation uses confirm_free_text")
        if kind == "abort":
            return _persist_abort(
                conn, project_id=project_id, pause=pause, state=state, actor=actor
            )
        if kind != "option":
            raise InvalidResponseError("check-in response kind is not supported")

        option = _offered_option(pause.payload, _require_str(response, "option_id"))
        params = _field(response, "params")
        _validate_offered_authored_delta(option, state=state, pause_payload=pause.payload)
        intent = _canonical_intent(option, params=params)
        renames = _theme_renames(params, pause.payload)
        try:
            result = _persist_intent(
                conn,
                project_id=project_id,
                pause=pause,
                state=state,
                intent=intent,
                actor=actor,
            )
            if renames:
                _apply_theme_renames(
                    conn, project_id=project_id, pause=pause, state=state, renames=renames
                )
            return result
        except SteeringAdjustmentError as exc:
            raise InvalidResponseError(str(exc)) from exc


def compile_free_text(
    engine: Engine,
    orchestrator: OrchestratorBackend,
    *,
    project_id: uuid.UUID,
    check_in_id: uuid.UUID,
    text: str,
) -> CompiledSteer:
    """Compile free-text steering without changing durable state.

    Args:
        engine: Database engine.
        orchestrator: Router backend used for the bounded fan-out compile.
        project_id: Project owning the parked walk.
        check_in_id: Durable ``steering.pause`` event identity.
        text: User's free-text steering request.

    Returns:
        A deterministic confirmation render and process-local token.

    Raises:
        LookupError: If the pause is absent or already decided.
        InvalidResponseError: If ``text`` is empty.
    """
    if not text.strip():
        raise InvalidResponseError("free-text steering must not be empty")
    with engine.begin() as conn:
        project_lock(conn, project_id)
        pause = _pending_pause(conn, project_id=project_id, check_in_id=check_in_id)
        state = build(engine, project_id=project_id, capability_run_id=pause.capability_run_id)
    point = PausePoint(
        cast(Literal["after_component", "before_component"], pause.payload["boundary"]),
        cast(str, pause.payload["component"]),
    )
    router_state = runner_module._SteeringState(
        plan=state.plan,
        plan_id=state.plan_id,
        plan_version=state.plan_version,
        plan_row_id=state.plan_row_id,
        chain=state.chain,
        pause_points=state.pause_points,
        pending_overlays=state.pending_overlays,
    )
    context = runner_module._router_pause_context(
        point,
        state=router_state,
        steer_point_name=_optional_str(pause.payload.get("steer_point")),
        options=_options(pause.payload),
        completed_components=state.completed_components,
        rerun_component=_optional_str(pause.payload.get("rerun_component")),
        segment_reentry_allowed=_bool_affordance(pause.payload, "segment_reentry_allowed"),
    )
    compiled = orchestrator.route(text, context, session_id=state.session_id)
    fanout = compile_fanout(
        compiled,
        backend_scope=state.plan.backend_scope,
        current_components=set(state.chain.components),
        completed_components=state.completed_components,
        rerun_surface=RerunSurface(
            replacement_component=_optional_str(pause.payload.get("rerun_component")),
            segment_reentry_available=_bool_affordance(pause.payload, "segment_reentry_allowed"),
        ),
    )
    token = uuid.uuid4().hex
    _put_compilation(
        token,
        _PendingCompilation(
            project_id=project_id,
            check_in_id=check_in_id,
            capability_run_id=pause.capability_run_id,
            fanout=fanout,
            user_text=text,
        ),
    )
    return CompiledSteer(render=render_fanout_confirmation(fanout), confirm_token=token)


def confirm_free_text(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    check_in_id: uuid.UUID,
    confirm_token: str,
    apply: bool,
    actor: str,
) -> AnswerResult | None:
    """Confirm or discard one process-local free-text compilation.

    Args:
        engine: Database engine.
        project_id: Project owning the parked walk.
        check_in_id: Pause the compilation belongs to.
        confirm_token: Opaque token returned by :func:`compile_free_text`.
        apply: Whether to persist the compiled fan-out.
        actor: Authenticated actor recorded in logs.

    Returns:
        ``None`` when discarded, otherwise the committed answer result.

    Raises:
        ConfirmTokenExpiredError: If the token was lost on restart/eviction.
        LookupError: If the token has a different scope.
        AlreadyAnsweredError: If another answer resolved the pause first.
        InvalidResponseError: If the compilation contains no applicable fragment.
    """
    pending = _take_compilation(confirm_token)
    if pending is None:
        raise ConfirmTokenExpiredError(
            "the compiled preview is no longer available - compile the request again"
        )
    if pending.project_id != project_id or pending.check_in_id != check_in_id:
        raise LookupError("free-text confirmation does not belong to this check-in")
    if not apply:
        return None
    if not pending.fanout.compiled:
        raise InvalidResponseError("the compiled steering request has no applicable change")
    with engine.begin() as conn:
        project_lock(conn, project_id)
        pause = _pending_pause(conn, project_id=project_id, check_in_id=check_in_id)
        if pause.capability_run_id != pending.capability_run_id:
            raise LookupError("free-text confirmation no longer matches the parked walk")
        state = build(engine, project_id=project_id, capability_run_id=pause.capability_run_id)
        try:
            return _persist_fanout(
                conn,
                project_id=project_id,
                pause=pause,
                state=state,
                fanout=pending.fanout,
                user_text=pending.user_text,
                actor=actor,
            )
        except SteeringAdjustmentError as exc:
            raise InvalidResponseError(str(exc)) from exc


def claim_continuation(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    capability_run_id: uuid.UUID,
) -> ClaimedContinuation | None:
    """Atomically claim the first unclaimed continuation for a parked walk.

    Args:
        engine: Database engine.
        project_id: Project owning the parked walk.
        capability_run_id: Walk whose continuation should be claimed.

    Returns:
        The claim, or ``None`` when it is not currently claimable.

    Raises:
        LookupError: If the project does not exist.
    """
    with engine.begin() as conn:
        project_lock(conn, project_id)
        cap = (
            conn.execute(
                select(capability_run)
                .where(capability_run.c.project_id == project_id)
                .where(capability_run.c.capability_run_id == capability_run_id)
            )
            .mappings()
            .one_or_none()
        )
        if cap is None or cap["status"] != "paused":
            return None
        requested = _unclaimed_requests(
            conn, project_id=project_id, capability_run_id=capability_run_id
        )
        if not requested:
            return None
        request = requested[0]
        decision_event_id = _payload_uuid(request["payload"], "decision_event_id")
        if decision_event_id is None:
            raise LookupError("continuation request has no decision event identity")
        events.append(
            conn,
            project_id=project_id,
            run_id=request["run_id"],
            event_type="continuation.claimed",
            payload={
                "capability_run_id": str(capability_run_id),
                "decision_event_id": str(decision_event_id),
                "requested_event_id": str(request["event_id"]),
                "claimed_at": datetime.now(UTC).isoformat(),
            },
        )
        conn.execute(
            update(capability_run)
            .where(capability_run.c.project_id == project_id)
            .where(capability_run.c.capability_run_id == capability_run_id)
            .values(status="running")
        )
    claim = ClaimedContinuation(
        project_id=project_id,
        capability_run_id=capability_run_id,
        requested_event_id=request["event_id"],
        decision_event_id=decision_event_id,
    )
    log.info(
        "continuation.claimed",
        project_id=str(project_id),
        capability_run_id=str(capability_run_id),
    )
    return claim


def execute_continuation(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    capability_run_id: uuid.UUID,
    backends: Any,
    io: Any,
    discretion_hook: Any = None,
    orchestrator: OrchestratorBackend | None = None,
) -> RunPlanOutcome:
    """Rebuild and execute an already-claimed parked continuation.

    ``backends`` and ``io`` are deliberately required (review finding codex-1,
    2026-07-21): a ``None`` default fell through to ``run_plan``'s stub bundle
    and ``NullIO`` — the startup drainer redispatched real continuations onto
    deterministic stubs that auto-continued every subsequent pause.

    Args:
        engine: Database engine.
        project_id: Project owning the walk.
        capability_run_id: Claimed walk to resume.
        backends: Runner component backends (the caller decides live vs stub).
        io: Runner IO seam (``ParkIO()`` on every API/drainer path).
        discretion_hook: Optional runner discretion hook.
        orchestrator: Optional router/watch backend.

    Returns:
        The resumed runner outcome.

    Raises:
        LookupError: If the walk or its claimed durable decision is absent.
    """
    state = build(engine, project_id=project_id, capability_run_id=capability_run_id)
    with engine.connect() as conn:
        cap = (
            conn.execute(
                select(capability_run)
                .where(capability_run.c.project_id == project_id)
                .where(capability_run.c.capability_run_id == capability_run_id)
            )
            .mappings()
            .one_or_none()
        )
        if cap is None:
            raise LookupError("capability run does not exist")
        decision = _claimed_decision(
            conn, project_id=project_id, capability_run_id=capability_run_id
        )
    resume = _resume_decision(state, decision)
    return run_plan(
        engine,
        project_id=project_id,
        evidence_scope_id=cap["evidence_scope_id"],
        plan=state.plan,
        plan_id=state.plan_id,
        plan_version=state.plan_version,
        plan_row_id=state.plan_row_id,
        backends=backends,
        io=io,
        discretion_hook=discretion_hook,
        orchestrator=orchestrator,
        resume_from=state,
        resume_decision=resume,
    )


def mark_interrupted_best_effort(
    engine: Engine, *, project_id: uuid.UUID, capability_run_id: uuid.UUID
) -> None:
    """Terminally mark a walk whose executor raised outside runner handling.

    Called from executor catch-blocks (review finding I1/codex-7, 2026-07-21):
    an exception between claim/dispatch commit and runner-owned status handling
    left the walk ``running`` forever with no thread. Best-effort by design —
    a failure here is logged and the startup sweep remains the backstop.
    """
    try:
        with engine.begin() as conn:
            project_lock(conn, project_id)
            updated = conn.execute(
                update(capability_run)
                .where(capability_run.c.project_id == project_id)
                .where(capability_run.c.capability_run_id == capability_run_id)
                .where(capability_run.c.status == "running")
                .values(status="interrupted", ended_at=datetime.now(UTC))
            )
            if updated.rowcount:
                events.append(
                    conn,
                    project_id=project_id,
                    run_id=_latest_attachment(
                        conn, project_id=project_id, capability_run_id=capability_run_id
                    ),
                    event_type="run.interrupted",
                    payload={"capability_run_id": str(capability_run_id)},
                )
    except Exception:
        log.exception(
            "continuation.interrupt_mark_failed",
            project_id=str(project_id),
            capability_run_id=str(capability_run_id),
        )


def startup_sweep(engine: Engine) -> SweepReport:
    """Recover walk state after a process death (idempotent, fires per boot).

    Classifies every ``running`` walk three ways (review findings, 2026-07-21):

    - claimed continuation with **no component progress** after the claim → the
      walk sat at a clean boundary with the full durable record intact; it is
      returned for direct re-execution, never interrupted;
    - anything else ``running`` → died mid-execution → honestly ``interrupted``.
      A walk with **no event attachment at all** (death between ``run.opened``
      and the first component) is interrupted with a null attachment rather
      than failing the sweep — raising here bricked every subsequent API boot.

    Args:
        engine: Database engine.

    Returns:
        Interrupted walks, unclaimed parked continuations, and claimed-but-
        unexecuted continuations, each in deterministic order.
    """
    interrupted: list[uuid.UUID] = []
    reexecute: list[ClaimedContinuation] = []
    with engine.begin() as conn:
        running = (
            conn.execute(
                select(capability_run)
                .where(capability_run.c.status == "running")
                .order_by(capability_run.c.project_id, capability_run.c.capability_run_id)
            )
            .mappings()
            .all()
        )
        for cap in running:
            project_lock(conn, cap["project_id"])
            claim = _claimed_without_progress(
                conn,
                project_id=cap["project_id"],
                capability_run_id=cap["capability_run_id"],
            )
            if claim is not None:
                reexecute.append(claim)
                continue
            attachment = _latest_attachment(
                conn,
                project_id=cap["project_id"],
                capability_run_id=cap["capability_run_id"],
            )
            if attachment is None:
                log.warning(
                    "continuation.sweep_orphan_without_attachment",
                    project_id=str(cap["project_id"]),
                    capability_run_id=str(cap["capability_run_id"]),
                )
            conn.execute(
                update(capability_run)
                .where(capability_run.c.capability_run_id == cap["capability_run_id"])
                .where(capability_run.c.status == "running")
                .values(status="interrupted", ended_at=datetime.now(UTC))
            )
            events.append(
                conn,
                project_id=cap["project_id"],
                run_id=attachment,
                event_type="run.interrupted",
                payload={"capability_run_id": str(cap["capability_run_id"])},
            )
            interrupted.append(cap["capability_run_id"])

        redispatch = _redispatchable_requests(conn)
    return SweepReport(tuple(interrupted), tuple(redispatch), tuple(reexecute))


def _claimed_without_progress(
    conn: Connection, *, project_id: uuid.UUID, capability_run_id: uuid.UUID
) -> ClaimedContinuation | None:
    """Return the walk's claimed continuation if nothing executed after the claim.

    The claim commits ``status=running`` in the request thread before the
    executor takes over, so a death in that window leaves a fully recoverable
    walk. "Progress" is any run-attached non-continuation event after the
    claim: component emissions (``run.started`` …) carry no
    ``capability_run_id`` in their payload, but they always carry a ``run_id``
    attachment, and one active walk per project means any such event after the
    claim belongs to this walk's execution. Missing real progress here would
    silently re-run an already-committed component — err toward interruption.
    """
    rows = events.read(conn, project_id)
    claim_row: dict[str, Any] | None = None
    for row in rows:
        if (
            row["event_type"] == "continuation.claimed"
            and _payload_uuid(row["payload"], "capability_run_id") == capability_run_id
        ):
            claim_row = row
    if claim_row is None:
        return None
    for row in rows:
        if (
            row["sequence"] > claim_row["sequence"]
            and not str(row["event_type"]).startswith("continuation.")
            and row["run_id"] is not None
        ):
            return None
    requested_event_id = _payload_uuid(claim_row["payload"], "requested_event_id")
    decision_event_id = _payload_uuid(claim_row["payload"], "decision_event_id")
    if requested_event_id is None or decision_event_id is None:
        return None
    return ClaimedContinuation(
        project_id=project_id,
        capability_run_id=capability_run_id,
        requested_event_id=requested_event_id,
        decision_event_id=decision_event_id,
    )


def _pending_pause(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    check_in_id: uuid.UUID,
) -> _Pause:
    """Return the project's latest undecided pause or raise its domain error."""
    rows = events.read(conn, project_id)
    pause_row = next(
        (
            row
            for row in rows
            if row["event_id"] == check_in_id and row["event_type"] == "steering.pause"
        ),
        None,
    )
    if pause_row is None:
        raise LookupError("check-in does not exist")
    payload = pause_row["payload"]
    capability_run_id = _payload_uuid(payload, "capability_run_id")
    if capability_run_id is None or not isinstance(pause_row["run_id"], uuid.UUID):
        raise LookupError("check-in has malformed durable identity")
    pauses = [
        row
        for row in rows
        if row["event_type"] == "steering.pause"
        and _payload_uuid(row["payload"], "capability_run_id") == capability_run_id
    ]
    if not pauses or pauses[-1]["event_id"] != check_in_id:
        raise LookupError("check-in is not the latest pause for this walk")
    if any(
        row["event_type"] == steering_events.STEERING_DECISION
        and row["sequence"] > pause_row["sequence"]
        and _payload_uuid(row["payload"], "capability_run_id") == capability_run_id
        for row in rows
    ):
        raise AlreadyAnsweredError("check-in has already been answered")
    cap_status = conn.execute(
        select(capability_run.c.status)
        .where(capability_run.c.project_id == project_id)
        .where(capability_run.c.capability_run_id == capability_run_id)
    ).scalar_one_or_none()
    if cap_status != "paused":
        raise LookupError("check-in is not parked")
    latest_run_id = conn.execute(
        select(capability_run.c.capability_run_id)
        .where(capability_run.c.project_id == project_id)
        .order_by(capability_run.c.started_at.desc(), capability_run.c.capability_run_id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest_run_id != capability_run_id:
        raise LookupError("check-in does not belong to the project's latest walk")
    return _Pause(
        capability_run_id=capability_run_id,
        event_id=check_in_id,
        run_id=pause_row["run_id"],
        sequence=pause_row["sequence"],
        payload=payload,
    )


def _persist_intent(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    pause: _Pause,
    state: Any,
    intent: tuple[str, Any],
    actor: str,
) -> AnswerResult:
    """Persist one validated canonical-menu intent in the caller transaction."""
    kind, value = intent
    if kind == "abort":
        return _persist_abort(conn, project_id=project_id, pause=pause, state=state, actor=actor)
    if kind == "continue":
        decision_id = _append_decision(
            conn, project_id=project_id, pause=pause, state=state, response="continue", action=None
        )
        return _request_continuation(
            conn, project_id=project_id, pause=pause, decision_event_id=decision_id, actor=actor
        )
    if kind == "adjust":
        adjustment = cast(Adjust, value)
        plan_row = _current_plan_row(conn, project_id=project_id, state=state)
        apply_adjustment(
            conn,
            project_id=project_id,
            plan_row=plan_row,
            plan=state.plan,
            adjustment=adjustment,
            completed_components=state.completed_components,
        )
        decision_response: Literal["adjust", "mode_change"] = (
            "mode_change" if adjustment.new_mode is not None else "adjust"
        )
        decision_id = _append_decision(
            conn,
            project_id=project_id,
            pause=pause,
            state=state,
            response=decision_response,
            action=runner_module._interpreted_action(adjustment),
        )
        return _request_continuation(
            conn, project_id=project_id, pause=pause, decision_event_id=decision_id, actor=actor
        )
    if kind == "rerun":
        component, raw_delta = cast(tuple[str, dict[str, Any]], value)
        directive = _merged_rerun_directive(state, component, raw_delta)
        plan_row = _current_plan_row(conn, project_id=project_id, state=state)
        apply_replacement_rerun(
            conn,
            project_id=project_id,
            plan_row=plan_row,
            plan=state.plan,
            component=component,
            directive=directive,
        )
        adjustment = Adjust(directive_deltas=raw_delta)
        decision_id = _append_decision(
            conn,
            project_id=project_id,
            pause=pause,
            state=state,
            response="adjust",
            action=runner_module._interpreted_action(adjustment),
            rerun_mode="replacement",
        )
        return _request_continuation(
            conn, project_id=project_id, pause=pause, decision_event_id=decision_id, actor=actor
        )
    if kind == "segment_reentry":
        reentry = cast(ReEnterSegment, value)
        _validate_segment_bounds(state, reentry, pause.payload)
        plan_row = _current_plan_row(conn, project_id=project_id, state=state)
        apply_segment_reentry(
            conn,
            project_id=project_id,
            plan_row=plan_row,
            plan=state.plan,
            segment_start=reentry.segment_start,
            directive_deltas=reentry.directive_deltas,
        )
        decision_id = _append_decision(
            conn,
            project_id=project_id,
            pause=pause,
            state=state,
            response="adjust",
            action=runner_module._reentry_interpreted_action(reentry, pause.payload["component"]),
            rerun_mode="additive",
        )
        return _request_continuation(
            conn, project_id=project_id, pause=pause, decision_event_id=decision_id, actor=actor
        )
    raise AssertionError(f"unknown validated intent {kind!r}")


def _persist_abort(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    pause: _Pause,
    state: Any,
    actor: str,
) -> AnswerResult:
    """Record an abort and terminally mark the parked capability run.

    Mirrors the runner's in-process ``_abort_and_record`` semantics (review
    finding, 2026-07-21): the plan flips to ``abandoned`` in the same
    transaction, and a ``run.finished`` event carries the terminal status so
    SSE replay and the live store see the walk end — without it the workspace
    showed an aborted run as still paused forever.
    """
    decision_id = _append_decision(
        conn, project_id=project_id, pause=pause, state=state, response="abort", action=None
    )
    if state.plan_row_id is not None:
        conn.execute(
            orchestration_plan.update()
            .where(orchestration_plan.c.plan_id == state.plan_row_id)
            .where(orchestration_plan.c.project_id == project_id)
            .values(status="abandoned")
        )
    conn.execute(
        update(capability_run)
        .where(capability_run.c.project_id == project_id)
        .where(capability_run.c.capability_run_id == pause.capability_run_id)
        .values(status="aborted", ended_at=datetime.now(UTC))
    )
    events.append(
        conn,
        project_id=project_id,
        run_id=pause.run_id,
        event_type="run.finished",
        payload={"capability_run_id": str(pause.capability_run_id), "status": "aborted"},
    )
    log.info("continuation.aborted", project_id=str(project_id), actor=actor)
    return AnswerResult(pause.capability_run_id, decision_id, False)


def _persist_fanout(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    pause: _Pause,
    state: Any,
    fanout: FanOut,
    user_text: str,
    actor: str,
) -> AnswerResult:
    """Persist the in-process fan-out decision shapes in one API transaction."""
    action = fanout.as_interpreted_action()
    current_state = state
    decision_id: uuid.UUID | None = None
    adjustments = fanout.plan_adjustments
    if adjustments:
        adjustment = Adjust(
            directive_deltas={fragment.component: fragment.delta for fragment in adjustments}
        )
        plan_row = _current_plan_row(conn, project_id=project_id, state=current_state)
        amended, plan_id, version = apply_adjustment(
            conn,
            project_id=project_id,
            plan_row=plan_row,
            plan=current_state.plan,
            adjustment=adjustment,
            completed_components=current_state.completed_components,
        )
        decision_id = _append_decision(
            conn,
            project_id=project_id,
            pause=pause,
            state=current_state,
            response="adjust",
            action=action,
            user_text=user_text,
        )
        current_state = _with_plan(current_state, amended, plan_id, version)
    rerun = fanout.rerun
    if rerun is not None:
        if rerun.kind == "replacement_rerun":
            directive = _merged_rerun_directive(current_state, rerun.component, rerun.delta)
            plan_row = _current_plan_row(conn, project_id=project_id, state=current_state)
            apply_replacement_rerun(
                conn,
                project_id=project_id,
                plan_row=plan_row,
                plan=current_state.plan,
                component=rerun.component,
                directive=directive,
            )
            # current_state, not state: after a preceding adjustment fragment the
            # decision must record the post-amendment plan identity or SSE derives
            # the wrong plan.updated version (review finding m1, 2026-07-21).
            decision_id = _append_decision(
                conn,
                project_id=project_id,
                pause=pause,
                state=current_state,
                response="adjust",
                action=action,
                user_text=user_text,
                rerun_mode="replacement",
            )
        else:
            segment = ReEnterSegment(directive_deltas={rerun.component: rerun.delta})
            _validate_segment_bounds(current_state, segment, pause.payload)
            plan_row = _current_plan_row(conn, project_id=project_id, state=current_state)
            apply_segment_reentry(
                conn,
                project_id=project_id,
                plan_row=plan_row,
                plan=current_state.plan,
                segment_start=segment.segment_start,
                directive_deltas=segment.directive_deltas,
            )
            decision_id = _append_decision(
                conn,
                project_id=project_id,
                pause=pause,
                state=current_state,
                response="adjust",
                action=action,
                user_text=user_text,
                rerun_mode="additive",
            )
    if decision_id is None:
        raise InvalidResponseError("the compiled steering request has no applicable change")
    return _request_continuation(
        conn, project_id=project_id, pause=pause, decision_event_id=decision_id, actor=actor
    )


def _canonical_intent(option: dict[str, Any], *, params: Any) -> tuple[str, Any]:
    """Translate one offered option into a fail-closed runner intent."""
    option_id = _optional_str(option.get("id"))
    if option_id == "abort":
        if params is not None:
            raise InvalidResponseError("abort does not accept parameters")
        return "abort", None
    if option.get("requires_user_input") is True and not isinstance(params, Mapping):
        raise InvalidResponseError("this option requires parameters")
    allowed_rename_params = isinstance(params, Mapping) and set(params) == {"renames"}
    if (
        option.get("requires_user_input") is not True
        and params is not None
        and not allowed_rename_params
    ):
        raise InvalidResponseError("this option does not accept parameters")
    if option_id == "change_mode":
        mode = _optional_str(params.get("new_mode") if isinstance(params, Mapping) else None)
        if mode not in {"frequent", "moderate", "minimal", "unattended"}:
            raise InvalidResponseError("change_mode requires a supported new_mode")
        return "adjust", Adjust(new_mode=mode)
    delta = copy.deepcopy(option.get("delta", {}))
    if not isinstance(delta, dict):
        raise InvalidResponseError("offered option has malformed delta")
    if option.get("requires_user_input") is True:
        supplied = params.get("delta", params) if isinstance(params, Mapping) else None
        if not isinstance(supplied, Mapping) or not supplied:
            raise InvalidResponseError("this option requires a non-empty delta parameter")
        delta = copy.deepcopy(dict(supplied))
    if not delta:
        return "continue", None
    rerun_component = _optional_str(option.get("_rerun_component"))
    segment_allowed = option.get("_segment_reentry_allowed") is True
    if rerun_component is not None:
        matched = runner_module._match_replacement_delta(rerun_component, delta)
        if matched is not None:
            return "rerun", (rerun_component, matched)
    if segment_allowed and set(delta) == {"acquire"}:
        return "segment_reentry", ReEnterSegment(directive_deltas=delta)
    return "adjust", Adjust(
        directive_deltas=delta,
        authored_by="orchestrator" if option.get("authored") is True else None,
    )


def _validate_offered_authored_delta(
    option: dict[str, Any], *, state: Any, pause_payload: dict[str, Any]
) -> None:
    """Revalidate a persisted authored option immediately before application."""
    if option.get("authored") is not True:
        return
    delta = option.get("delta")
    if not isinstance(delta, dict) or len(delta) != 1:
        raise InvalidResponseError("authored option has malformed delta")
    component, local = next(iter(delta.items()))
    if not isinstance(component, str) or not isinstance(local, dict):
        raise InvalidResponseError("authored option has malformed delta")
    try:
        validate_steering_delta(
            local,
            component,
            SteeringValidationCtx(
                backend_scope=state.plan.backend_scope,
                current_components=set(state.chain.components),
                completed_components=set(state.completed_components),
                rerun_surface=RerunSurface(
                    replacement_component=_optional_str(pause_payload.get("rerun_component")),
                    segment_reentry_available=_bool_affordance(
                        pause_payload, "segment_reentry_allowed"
                    ),
                ),
            ),
        )
    except SteeringDeltaInvalid as exc:
        raise InvalidResponseError(f"authored option refused: {exc}") from exc


def _offered_option(pause_payload: dict[str, Any], option_id: str) -> dict[str, Any]:
    """Return a durable offered option, including its presentation affordances.

    ``continue`` and ``abort`` are the universal floor at every pause (the
    in-process path accepts them regardless of the rendered option list, and
    a generic ``check_in`` pause may carry no explicit options at all) — they
    validate even when absent from the stored list.
    """
    options = pause_payload.get("options") or []
    if not isinstance(options, list) or not all(isinstance(option, dict) for option in options):
        raise InvalidResponseError("check-in has malformed options")
    option = next((item for item in options if item.get("id") == option_id), None)
    if option is None and option_id in ("continue", "abort"):
        option = {"id": option_id}
    if option is None:
        raise InvalidResponseError("option was not offered at this check-in")
    selected = dict(option)
    selected["_rerun_component"] = _optional_str(pause_payload.get("rerun_component"))
    selected["_segment_reentry_allowed"] = _bool_affordance(
        pause_payload, "segment_reentry_allowed"
    )
    return selected


def _theme_renames(params: Any, pause_payload: dict[str, Any]) -> list[tuple[str, str]]:
    """Validate P2-only card-local theme-name edits from one option response."""
    if not isinstance(params, Mapping) or "renames" not in params:
        return []
    if pause_payload.get("steer_point") != "evidence_base_coverage":
        raise InvalidResponseError("rename_theme is only available at evidence_base_coverage")
    raw = params["renames"]
    if not isinstance(raw, list):
        raise InvalidResponseError("rename_theme requires a renames list")
    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, Mapping):
            raise InvalidResponseError("each rename must be an object")
        theme_id, name = item.get("theme_id"), item.get("name")
        if not isinstance(theme_id, str) or not isinstance(name, str) or not name.strip():
            raise InvalidResponseError("each rename requires theme_id and a non-empty name")
        if theme_id in seen:
            raise InvalidResponseError("each theme may be renamed once")
        seen.add(theme_id)
        result.append((theme_id, name.strip()))
    return result


def _apply_theme_renames(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    pause: _Pause,
    state: Any,
    renames: list[tuple[str, str]],
) -> None:
    """Update P2's persisted theme display names and append their audit event."""
    row = (
        conn.execute(
            select(characterisation_result)
            .where(characterisation_result.c.project_id == project_id)
            .order_by(characterisation_result.c.created_at.desc())
        )
        .mappings()
        .first()
    )
    if row is None or not isinstance(row["themes"], dict):
        raise InvalidResponseError("rename_theme refused: no current theme map exists")
    payload = dict(row["themes"])
    themes = payload.get("themes")
    if not isinstance(themes, list):
        raise InvalidResponseError("rename_theme refused: current theme map is malformed")
    by_id = {item.get("theme_id"): item for item in themes if isinstance(item, dict)}
    for theme_id, name in renames:
        target = by_id.get(theme_id)
        if target is None:
            raise InvalidResponseError("rename_theme refused: theme is not in this evidence base")
        target["name"] = name
    conn.execute(
        update(characterisation_result)
        .where(characterisation_result.c.characterisation_id == row["characterisation_id"])
        .values(themes=payload)
    )
    events.append(
        conn,
        project_id=project_id,
        run_id=pause.run_id,
        event_type="steering.theme_renamed",
        payload={
            "capability_run_id": str(pause.capability_run_id),
            "plan_id": str(state.plan_id),
            "plan_version": state.plan_version,
            "renames": [{"theme_id": theme_id, "name": name} for theme_id, name in renames],
        },
    )


def _append_decision(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    pause: _Pause,
    state: Any,
    response: Literal["continue", "adjust", "abort", "mode_change"],
    action: Any,
    rerun_mode: Literal["replacement", "additive"] | None = None,
    user_text: str | None = None,
) -> uuid.UUID:
    """Use the shared steering payload builder for one durable decision."""
    base = steering_events.base_payload(
        capability_run_id=pause.capability_run_id,
        plan_id=state.plan_id,
        plan_version=state.plan_version,
        boundary=cast(Literal["after_component", "before_component"], pause.payload["boundary"]),
        component=_optional_str(pause.payload.get("component")),
    )
    payload = steering_events.decision_payload(
        base,
        decided_by="user",
        authored_by="user",
        response=response,
        interpreted_action=action,
        confirmed=True,
        user_text=user_text,
        rerun_mode=rerun_mode,
    )
    return steering_events.emit(
        conn,
        project_id=project_id,
        run_id=pause.run_id,
        event_type=steering_events.STEERING_DECISION,
        payload=payload,
    )


def _request_continuation(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    pause: _Pause,
    decision_event_id: uuid.UUID,
    actor: str,
) -> AnswerResult:
    """Append the durable-before-executable request paired to a decision."""
    events.append(
        conn,
        project_id=project_id,
        run_id=pause.run_id,
        event_type="continuation.requested",
        payload={
            "capability_run_id": str(pause.capability_run_id),
            "decision_event_id": str(decision_event_id),
            "requested_at": datetime.now(UTC).isoformat(),
        },
    )
    log.info(
        "continuation.requested",
        project_id=str(project_id),
        capability_run_id=str(pause.capability_run_id),
        actor=actor,
    )
    return AnswerResult(pause.capability_run_id, decision_event_id, True)


def _current_plan_row(conn: Connection, *, project_id: uuid.UUID, state: Any) -> Any:
    """Read the durable plan row currently represented by continuation state.

    Returns the SQLAlchemy row itself — the steering persistence helpers
    (`_plan_row_value`) read it by ATTRIBUTE access, exactly as the in-process
    runner passes it; a dict here 500s the confirm-apply path (live-check
    finding, 2026-07-21).
    """
    if state.plan_row_id is None:
        raise LookupError("parked walk has no persisted plan row")
    row = conn.execute(
        select(orchestration_plan)
        .where(orchestration_plan.c.project_id == project_id)
        .where(orchestration_plan.c.plan_id == state.plan_row_id)
    ).one_or_none()
    if row is None:
        raise LookupError("parked walk plan row does not exist")
    return row


def _with_plan(state: Any, plan: Any, plan_id: uuid.UUID, version: int) -> Any:
    """Return minimal continuation state with the just-persisted plan identity."""
    return type(state)(
        capability_run_id=state.capability_run_id,
        plan=plan,
        plan_id=plan_id,
        plan_version=version,
        plan_row_id=plan_id,
        chain=compose(plan),
        pause_points=pause_points(plan.steering_mode, compose(plan)),
        pending_overlays=state.pending_overlays,
        remaining_steps=state.remaining_steps,
        step_outcomes=state.step_outcomes,
        flagged_events=state.flagged_events,
        successful_runs=state.successful_runs,
        attempted_runs=state.attempted_runs,
        blocked_discretionary=state.blocked_discretionary,
        completed_components=state.completed_components,
        last_check_in_payload=state.last_check_in_payload,
        most_recent_attempted_run_id=state.most_recent_attempted_run_id,
        session_id=state.session_id,
    )


def _merged_rerun_directive(state: Any, component: str, delta: dict[str, Any]) -> dict[str, Any]:
    """Reuse the runner's component mapping to derive its persisted fine directive."""
    matched = runner_module._match_replacement_delta(component, delta)
    if matched is None:
        raise InvalidResponseError("replacement re-run delta does not target this pause")
    step = next((item for item in state.chain.steps if item.component == component), None)
    if step is None:
        raise InvalidResponseError("replacement re-run component is not in the chain")
    key = runner_module.REPLACEMENT_RERUNS[component].context_key
    base = step.directive_delta.get(key, {})
    supplied = matched[component].get(key)
    if not isinstance(base, dict) or not isinstance(supplied, dict):
        raise InvalidResponseError("replacement re-run directive has malformed context")
    return {key: {**base, **supplied}}


def _validate_segment_bounds(state: Any, response: ReEnterSegment, payload: dict[str, Any]) -> None:
    """Enforce the durable additive affordance and its exact re-walk segment."""
    if not _bool_affordance(payload, "segment_reentry_allowed"):
        raise InvalidResponseError("segment re-entry was not offered at this check-in")
    boundary = _optional_str(payload.get("component"))
    if boundary is None:
        raise InvalidResponseError("segment re-entry pause has no boundary component")
    segment = set(
        runner_module._segment_components(
            state.chain,
            segment_start=response.segment_start,
            boundary_component=boundary,
            completed_components=state.completed_components,
        )
    )
    if any(component not in segment for component in response.directive_deltas):
        raise InvalidResponseError("segment re-entry delta names a component outside the re-walk")


def _unclaimed_requests(
    conn: Connection, *, project_id: uuid.UUID, capability_run_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Return unclaimed requests for one walk in event sequence order."""
    rows = events.read(conn, project_id)
    claimed = {
        _payload_uuid(row["payload"], "requested_event_id")
        for row in rows
        if row["event_type"] == "continuation.claimed"
    }
    return [
        row
        for row in rows
        if row["event_type"] == "continuation.requested"
        and _payload_uuid(row["payload"], "capability_run_id") == capability_run_id
        and row["event_id"] not in claimed
    ]


def _claimed_decision(
    conn: Connection, *, project_id: uuid.UUID, capability_run_id: uuid.UUID
) -> dict[str, Any]:
    """Read the decision referenced by the walk's durable claim."""
    rows = events.read(conn, project_id)
    claim = next(
        (
            row
            for row in reversed(rows)
            if row["event_type"] == "continuation.claimed"
            and _payload_uuid(row["payload"], "capability_run_id") == capability_run_id
        ),
        None,
    )
    if claim is None:
        raise LookupError("capability run has no continuation claim")
    decision_id = _payload_uuid(claim["payload"], "decision_event_id")
    decision = next((row for row in rows if row["event_id"] == decision_id), None)
    if decision is None or decision["event_type"] != steering_events.STEERING_DECISION:
        raise LookupError("continuation claim references no steering decision")
    return decision


def _resume_decision(state: Any, decision: dict[str, Any]) -> ResumeDecision:
    """Reconstruct runner continuation instructions from a durable decision."""
    payload = decision["payload"]
    response = payload.get("response")
    rerun_mode = payload.get("rerun_mode")
    action = payload.get("interpreted_action")
    if response == "continue":
        return ResumeDecision(response="continue")
    if rerun_mode == "replacement":
        if not isinstance(action, dict):
            raise LookupError("replacement decision has no interpreted action")
        deltas = action.get("directive_deltas")
        if isinstance(deltas, dict) and len(deltas) == 1:
            component = next(iter(deltas))
            component_delta = deltas.get(component)
        else:
            fragment = _fanout_rerun_fragment(action, "replacement")
            component = fragment.get("component") if fragment is not None else None
            component_delta = fragment.get("delta") if fragment is not None else None
        if not isinstance(component, str) or not isinstance(component_delta, dict):
            raise LookupError("replacement decision has malformed component delta")
        return ResumeDecision(
            response="rerun",
            component=component,
            directive_delta=_merged_rerun_directive(state, component, {component: component_delta}),
        )
    if rerun_mode == "additive":
        if not isinstance(action, dict):
            raise LookupError("segment decision has no interpreted action")
        start = _optional_str(action.get("segment_start"))
        boundary = _optional_str(action.get("boundary"))
        deltas = action.get("directive_deltas")
        if not isinstance(deltas, dict):
            fragment = _fanout_rerun_fragment(action, "additive")
            component = fragment.get("component") if fragment is not None else None
            delta = fragment.get("delta") if fragment is not None else None
            if isinstance(component, str) and isinstance(delta, dict):
                deltas = {component: delta}
                start = "acquire"
                boundary = _optional_str(payload.get("component"))
        if start is None or boundary is None or not isinstance(deltas, dict):
            raise LookupError("segment decision has malformed interpreted action")
        return ResumeDecision(
            response="segment_reentry",
            component=boundary,
            segment_start=start,
            directive_deltas=deltas,
            boundary=cast(Literal["after_component", "before_component"], payload.get("boundary")),
        )
    if response in {"adjust", "mode_change"}:
        return ResumeDecision(response=cast(Literal["adjust", "mode_change"], response))
    raise LookupError("continuation decision cannot resume a parked walk")


def _fanout_rerun_fragment(action: dict[str, Any], mode: str) -> dict[str, Any] | None:
    """Return the one persisted fan-out re-run fragment for a continuation mode."""
    compiled = action.get("compiled")
    if not isinstance(compiled, list):
        return None
    fragment = next(
        (item for item in compiled if isinstance(item, dict) and item.get("rerun_mode") == mode),
        None,
    )
    return fragment if isinstance(fragment, dict) else None


def _latest_attachment(
    conn: Connection, *, project_id: uuid.UUID, capability_run_id: uuid.UUID
) -> uuid.UUID | None:
    """Find the latest non-null run attachment for a capability walk."""
    for row in reversed(events.read(conn, project_id)):
        if _payload_uuid(row["payload"], "capability_run_id") == capability_run_id and isinstance(
            row["run_id"], uuid.UUID
        ):
            return row["run_id"]
    return None


def _redispatchable_requests(conn: Connection) -> list[ClaimedContinuation]:
    """Return every unclaimed request on a still-parked walk deterministically."""
    rows = (
        conn.execute(
            select(capability_run)
            .where(capability_run.c.status == "paused")
            .order_by(capability_run.c.project_id, capability_run.c.capability_run_id)
        )
        .mappings()
        .all()
    )
    redispatch: list[ClaimedContinuation] = []
    for cap in rows:
        for request in _unclaimed_requests(
            conn,
            project_id=cap["project_id"],
            capability_run_id=cap["capability_run_id"],
        ):
            decision_id = _payload_uuid(request["payload"], "decision_event_id")
            if decision_id is not None:
                redispatch.append(
                    ClaimedContinuation(
                        project_id=cap["project_id"],
                        capability_run_id=cap["capability_run_id"],
                        requested_event_id=request["event_id"],
                        decision_event_id=decision_id,
                    )
                )
    return redispatch


def _put_compilation(token: str, pending: _PendingCompilation) -> None:
    """Add a compilation to the bounded process-local confirmation cache."""
    with _COMPILE_CACHE_LOCK:
        _COMPILE_CACHE[token] = pending
        _COMPILE_CACHE.move_to_end(token)
        while len(_COMPILE_CACHE) > _COMPILE_CACHE_LIMIT:
            _COMPILE_CACHE.popitem(last=False)


def _take_compilation(token: str) -> _PendingCompilation | None:
    """Consume a one-shot compilation token (honest loss on process restart)."""
    with _COMPILE_CACHE_LOCK:
        return _COMPILE_CACHE.pop(token, None)


def _field(value: Any, name: str) -> Any:
    """Read one field from a transport model or mapping."""
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _require_str(value: Any, name: str) -> str:
    """Return a required non-empty response field."""
    field = _field(value, name)
    if not isinstance(field, str) or not field:
        raise InvalidResponseError(f"{name} must be a non-empty string")
    return field


def _optional_str(value: Any) -> str | None:
    """Return a string value or ``None`` without coercion."""
    return value if isinstance(value, str) else None


def _options(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Read an options list fail-closed from a pause payload."""
    options = payload.get("options", [])
    if not isinstance(options, list) or not all(isinstance(option, dict) for option in options):
        raise InvalidResponseError("check-in has malformed options")
    return options


def _bool_affordance(payload: dict[str, Any], name: str) -> bool:
    """Read required boolean affordances fail-closed from a pause payload."""
    value = payload.get(name)
    if not isinstance(value, bool):
        raise InvalidResponseError(f"check-in has no valid {name} affordance")
    return value


def _payload_uuid(payload: Any, name: str) -> uuid.UUID | None:
    """Decode a UUID field from an event payload without coercing malformed data."""
    if not isinstance(payload, dict):
        return None
    value = payload.get(name)
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str):
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None
