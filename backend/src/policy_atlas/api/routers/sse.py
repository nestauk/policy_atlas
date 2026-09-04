"""Authenticated replay-then-tail server-sent events for task activity."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Iterable
from functools import partial
from typing import Annotated, Any, cast

import anyio
import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.sql.elements import ColumnElement

from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.checkin_read import _check_in
from policy_atlas.api.contract import (
    ArtefactSectionCompletedFrame,
    ArtefactSectionStartedFrame,
    ArtefactSkeletonFrame,
    CheckinPendingFrame,
    CheckinResolvedFrame,
    PlanUpdatedFrame,
    RunStatus,
    RunStatusFrame,
    StageCompletedFrame,
    StageFailedFrame,
    StageKey,
    StageStartedFrame,
    TaskUpdatedFrame,
    TickFrame,
)
from policy_atlas.api.deps import get_current_user, get_engine, get_settings
from policy_atlas.api.lifecycle import both_generations
from policy_atlas.api.routers._access import (
    accessible_task,
    may_read_task,
    readable_task_exists,
    trace_admin_stream_read,
)
from policy_atlas.api.routers.planning import _draft_from_plan
from policy_atlas.api.settings import Settings

# Shared with the check-in read model — one vocabulary, one leak surface.
from policy_atlas.api.stage_vocabulary import (
    STAGE_PRESENTATION as _STAGE_PRESENTATION,
)
from policy_atlas.api.stage_vocabulary import (
    presentation as _presentation,
)
from policy_atlas.api.stage_vocabulary import (
    stage_for_payload as _stage,
)
from policy_atlas.core import events
from policy_atlas.core.liveness import Tick, tick_hub
from policy_atlas.core.schema import event_log, task_plan
from policy_atlas.runtime import steering_events
from policy_atlas.runtime.task_plan import TaskPlan

log = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/tasks",
    tags=["events"],
    dependencies=[Depends(get_current_user)],
)

def _snapshot(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    user_id: str,
    cursor: int,
) -> tuple[int, list[dict[str, Any]]]:
    """Authorise then read a cursor-bounded durable backlog in one connection.

    This is also the **subscribe** half of contract § 3a's SSE trace grain:
    the grade resolves through `accessible_task`, so a stream opened on the
    admin leg emits exactly one `admin_read` line for the task row here,
    and the tail emits one `admin_stream_read` per re-authorised batch after
    it. Nothing extra is logged for a caller who was entitled to the task
    anyway.
    """
    with engine.connect() as conn:
        accessible_task(conn, task_id=task_id, user_id=user_id, write=False)
        snapshot = int(
            conn.execute(
                select(func.coalesce(func.max(event_log.c.sequence), 0)).where(
                    event_log.c.task_id == task_id
                )
            ).scalar_one()
        )
        rows = _event_rows(conn, task_id=task_id, after=cursor, through=snapshot)
        return snapshot, _map_rows(conn, task_id=task_id, rows=rows, through=snapshot)


def _tail(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    user_id: str,
    after: int,
) -> tuple[int, list[dict[str, Any]]] | None:
    """Re-authorise, then read and map the next durable tail batch.

    Contract § 5: the stream authorised once at ``_snapshot`` and then looped
    indefinitely, so none of this slice's four revocation events — de-enrolment,
    a visibility flip, an i.4 project cascade, an admin revoke — reached an
    already-open stream. The re-check happens **before** the batch is read, so a
    caller whose access has gone is never handed the events of the interval in
    which they lost it.

    **The batch select carries the grade too, in its own statement.** Checking
    first and reading second is two statements, and a revocation committing
    between them was still worth one batch of frames to the caller who had just
    lost access. So the event read is gated by
    :func:`_access.readable_task_exists` — the same legs, expressed as a
    predicate rather than a value — and the two do different jobs: the gate
    makes the batch empty, ``may_read_task`` ends the response. Neither
    alone is the fix; the reason both exist is that the response must *close*,
    not merely go quiet.

    **The fourth revocation event is now real.** The re-check resolves through
    `_access._read_legs`, which carries the admin leg, so clearing `is_admin`
    on a streaming administrator closes their stream on the next batch — no
    second tenancy predicate here, and no edit to this function when the leg
    landed.

    **One trace line per admin-carried batch**, not per frame (contract
    § 3a). `may_read_task` reports the leg in the same query that answers
    the grade, so the line costs nothing beyond the call.

    Args:
        engine: Application engine; this runs in a worker thread.
        task_id: The task being streamed.
        user_id: The caller's token subject, re-checked every batch.
        after: Exclusive lower bound on the durable sequence to read.

    Returns:
        The batch's last sequence and its mapped frames, or ``None`` when the
        caller's read grade has gone and the stream must close.
    """
    with engine.connect() as conn:
        check = may_read_task(conn, task_id=task_id, user_id=user_id)
        if not check.allowed:
            return None
        if check.via_admin:
            trace_admin_stream_read(user_id=user_id, task_id=task_id)
        rows = _event_rows(
            conn,
            task_id=task_id,
            after=after,
            through=None,
            guard=readable_task_exists(task_id, user_id),
        )
        last_sequence = rows[-1]["sequence"] if rows else after
        return last_sequence, _map_rows(conn, task_id=task_id, rows=rows, through=None)


def _event_rows(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    after: int,
    through: int | None,
    guard: ColumnElement[bool] | None = None,
) -> list[dict[str, Any]]:
    """Read ordered durable events in the inclusive/exclusive SSE sequence interval.

    Args:
        conn: Open database connection.
        task_id: The task whose log is read.
        after: Exclusive lower bound on the durable sequence.
        through: Inclusive upper bound, or ``None`` for "everything since".
        guard: An access predicate to AND into **this** statement, so the grade
            and the rows are decided together. The tail passes one (see
            :func:`_tail`); ``_snapshot`` does not, because it has just
            resolved the row through ``accessible_task`` in the same
            connection and nothing has been yielded yet.
    """
    statement = select(event_log).where(event_log.c.task_id == task_id).where(
        event_log.c.sequence > after
    )
    if through is not None:
        statement = statement.where(event_log.c.sequence <= through)
    if guard is not None:
        statement = statement.where(guard)
    return [dict(row._mapping) for row in conn.execute(statement.order_by(event_log.c.sequence))]


def _map_rows(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    rows: Iterable[dict[str, Any]],
    through: int | None,
) -> list[dict[str, Any]]:
    """Map allowlisted durable event rows to validated public frame models."""
    all_rows = list(rows)
    if not all_rows:
        return []
    # The full-history context exists solely for the decided-pause check, so
    # fetch it only when this batch carries a pause, and fetch decisions only.
    # The previous unconditional after=0 read re-scanned the whole task log
    # (large JSONB payloads included) every poll interval per client, even
    # when idle (review finding backend-M1, 2026-07-21).
    decision_events: list[dict[str, Any]] = []
    if any(row["event_type"] == "steering.pause" for row in all_rows):
        decision_events = [
            row
            for row in events.read(conn, task_id, event_types=["steering.decision"])
            if through is None or row["sequence"] <= through
        ]
    frames: list[dict[str, Any]] = []
    for row in all_rows:
        frames.extend(
            _frames_for_row(conn, task_id=task_id, row=row, all_events=decision_events)
        )
    return frames


def _frames_for_row(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    row: dict[str, Any],
    all_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return zero or more public frames for one allowlisted event row."""
    payload = row["payload"]
    if not isinstance(payload, dict):
        return []
    event_type = row["event_type"]
    persisted = _persisted_kwargs(row)
    if event_type in {
        "run.opened",
        "run.parked",
        "run.interrupted",
        "run.finished",
        # The claim IS the durable paused→running transition of a boundary
        # continuation — without this frame, replay and the live store show a
        # continuing walk as still paused (live-check finding, 2026-07-21).
        "continuation.claimed",
    }:
        capability_run_id = _uuid(payload.get("capability_run_id"))
        status = {
            "run.opened": "running",
            "run.parked": "paused",
            "run.interrupted": "interrupted",
            "continuation.claimed": "running",
        }.get(event_type, payload.get("status"))
        if capability_run_id is None or status not in {
            "running", "paused", "succeeded", "degraded", "failed", "aborted", "interrupted"
        }:
            return []
        run_frame = RunStatusFrame(
            type="run.status",
            capability_run_id=capability_run_id,
            status=cast(RunStatus, status),
            **persisted,
        )
        return [run_frame.model_dump(mode="json")]
    if event_type == "run.started":
        stage = _stage(payload)
        if stage is None:
            return []
        label, blurb = _presentation(stage)
        stage_frame = StageStartedFrame(
            type="stage.started", stage=stage, label=label, blurb=blurb, **persisted
        )
        return [stage_frame.model_dump(mode="json")]
    if event_type == "component.completed":
        stage = _stage(payload)
        if stage is None:
            return []
        label, _ = _presentation(stage)
        return [
            StageCompletedFrame(
                type="stage.completed",
                stage=stage,
                label=label,
                summary=_summary(payload),
                seconds=_seconds(conn, task_id=task_id, row=row, payload=payload),
                **persisted,
            ).model_dump(mode="json")
        ]
    if event_type in {"component.failed", "component.skipped"}:
        stage = _stage(payload)
        if stage is None:
            return []
        label, _ = _presentation(stage)
        reason = (
            payload.get("reason")
            if event_type == "component.skipped"
            else payload.get("error")
        )
        return [
            StageFailedFrame(
                type="stage.failed",
                stage=stage,
                label=label,
                reason=str(reason or "The stage did not complete."),
                skipped=event_type == "component.skipped",
                **persisted,
            ).model_dump(mode="json")
        ]
    if event_type == "artefact.skeleton":
        try:
            return [
                ArtefactSkeletonFrame(
                    type="artefact.skeleton", **payload, **persisted
                ).model_dump(mode="json")
            ]
        except (TypeError, ValueError):
            return []
    if event_type == "artefact.section_started":
        try:
            return [
                ArtefactSectionStartedFrame(
                    type="artefact.section_started", **payload, **persisted
                ).model_dump(mode="json")
            ]
        except (TypeError, ValueError):
            return []
    if event_type == "artefact.section_completed":
        try:
            return [
                ArtefactSectionCompletedFrame(
                    type="artefact.section_completed", **payload, **persisted
                ).model_dump(mode="json")
            ]
        except (TypeError, ValueError):
            return []
    if event_type == "steering.pause":
        decided = _is_decided_pause(row, all_events)
        try:
            check_in = _check_in(row, decided=decided)
        except LookupError:
            return []
        checkin_frame = CheckinPendingFrame(
            type="checkin.pending", check_in=check_in, **persisted
        )
        return [checkin_frame.model_dump(mode="json")]
    if event_type == "steering.decision":
        frames = _decision_frames(conn, task_id=task_id, payload=payload, persisted=persisted)
        return [frame.model_dump(mode="json") for frame in frames]
    if event_type == "plan.approved":
        plan_frame = _plan_frame(conn, task_id=task_id, payload=payload, persisted=persisted)
        return [plan_frame.model_dump(mode="json")] if plan_frame is not None else []
    # Both generations: pre-038 rows say `project.*` (task 038, contract V1).
    if event_type in both_generations("renamed", "archived"):
        task_frame = _task_frame(
            conn,
            task_id=task_id,
            event_type=event_type,
            payload=payload,
            persisted=persisted,
        )
        return [task_frame.model_dump(mode="json")]
    return []


def _persisted_kwargs(row: dict[str, Any]) -> dict[str, Any]:
    """Extract the common persisted-frame fields from one event row."""
    return {"sequence": row["sequence"], "occurred_at": row["occurred_at"]}


def _uuid(value: Any) -> uuid.UUID | None:
    """Parse a UUID payload value without letting malformed historical rows leak."""
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _summary(payload: dict[str, Any]) -> dict[str, int | float | str]:
    """Keep only scalar terminal counts; never expose nested raw component payloads."""
    hidden = {"component", "registry_component", "plan_id", "plan_version", "session_id"}
    summary: dict[str, int | float | str] = {
        key: value
        for key, value in payload.items()
        if key not in hidden
        and isinstance(value, (int, float, str))
        and not isinstance(value, bool)
    }
    # Search-loop round index is nested under ``search`` today; flatten it
    # so the running card can label Searching (Round 2) without seeing the
    # raw component payload.
    if "round_index" not in summary:
        for value in payload.values():
            if isinstance(value, dict):
                round_index = value.get("round_index")
                if isinstance(round_index, int):
                    summary["round_index"] = round_index
                    break
    return summary


def _seconds(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    row: dict[str, Any],
    payload: dict[str, Any],
) -> float | None:
    """Read an adjacent timing record when available, then use terminal payload time."""
    wall_clock = payload.get("wall_clock_s")
    if isinstance(wall_clock, int | float) and not isinstance(wall_clock, bool):
        return float(wall_clock)
    run_id = row.get("run_id")
    if not isinstance(run_id, uuid.UUID):
        return None
    timing = conn.execute(
        select(event_log.c.payload)
        .where(event_log.c.task_id == task_id)
        .where(event_log.c.run_id == run_id)
        .where(event_log.c.event_type == "component.timing")
        .order_by(event_log.c.sequence.asc())
        .limit(1)
    ).scalar_one_or_none()
    if not isinstance(timing, dict):
        return None
    seconds = timing.get("wall_clock_s")
    if isinstance(seconds, int | float) and not isinstance(seconds, bool):
        return float(seconds)
    return None


def _is_decided_pause(pause: dict[str, Any], all_events: list[dict[str, Any]]) -> bool:
    """Determine whether the pause has a later decision for the same walk."""
    payload = pause["payload"]
    if not isinstance(payload, dict):
        return False
    capability_run_id = payload.get("capability_run_id")
    return any(
        event["event_type"] == "steering.decision"
        and event["sequence"] > pause["sequence"]
        and isinstance(event["payload"], dict)
        and event["payload"].get("capability_run_id") == capability_run_id
        for event in all_events
    )


def _decision_frames(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    payload: dict[str, Any],
    persisted: dict[str, Any],
) -> list[CheckinResolvedFrame | PlanUpdatedFrame]:
    """Map a decision and, when it created one, its superseding plan version."""
    check_in_id = _uuid(payload.get("check_in_id"))
    # Steering decisions identify the preceding pause by capability walk rather
    # than duplicating its event id. Resolve that relationship deterministically.
    if check_in_id is None:
        capability_run_id = payload.get("capability_run_id")
        pause = conn.execute(
            select(event_log.c.event_id)
            .where(event_log.c.task_id == task_id)
            .where(event_log.c.event_type == "steering.pause")
            .where(event_log.c.sequence < cast(int, persisted["sequence"]))
            .order_by(event_log.c.sequence.desc())
        ).mappings().all()
        for candidate in pause:
            event_payload = conn.execute(
                select(event_log.c.payload).where(event_log.c.event_id == candidate["event_id"])
            ).scalar_one()
            if (
                isinstance(event_payload, dict)
                and event_payload.get("capability_run_id") == capability_run_id
            ):
                check_in_id = candidate["event_id"]
                break
    if check_in_id is None:
        return []
    response = payload.get("interpreted_action")
    # Pre-038 rows carry the old actor word; the set below would drop them.
    decided_by = steering_events.canonical_actor(payload.get("decided_by"))
    frame: list[CheckinResolvedFrame | PlanUpdatedFrame] = [
        CheckinResolvedFrame(
            type="checkin.resolved",
            check_in_id=check_in_id,
            response=(
                response if isinstance(response, dict) else {"response": payload.get("response")}
            ),
            decided_by=(
                cast(Any, decided_by)
                if decided_by in {"user", "agent", "standing_default"}
                else None
            ),
            **persisted,
        )
    ]
    if (
        payload.get("response") in {"adjust", "mode_change"}
        or payload.get("rerun_mode") is not None
    ):
        version = payload.get("plan_version")
        if isinstance(version, int):
            plan_frame = _plan_frame(
                conn,
                task_id=task_id,
                payload={"version": version + 1},
                persisted=persisted,
            )
            if plan_frame is not None:
                frame.append(plan_frame)
    return frame


def _plan_frame(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    payload: dict[str, Any],
    persisted: dict[str, Any],
) -> PlanUpdatedFrame | None:
    """Load the versioned plan row and task it through the public contract."""
    version = payload.get("version")
    if not isinstance(version, int):
        return None
    row = conn.execute(
        select(task_plan)
        .where(task_plan.c.task_id == task_id)
        .where(task_plan.c.version == version)
    ).mappings().one_or_none()
    if row is None or not isinstance(row["payload"], dict):
        return None
    plan = _draft_from_plan(TaskPlan.model_validate(row["payload"]))
    return PlanUpdatedFrame(type="plan.updated", plan=plan, version=version, **persisted)


def _task_frame(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
    persisted: dict[str, Any],
) -> TaskUpdatedFrame:
    """Project a lifecycle audit event without leaking its actor or old values."""
    del conn, task_id
    if event_type in both_generations("renamed"):
        name = payload.get("name_to")
        return TaskUpdatedFrame(
            type="task.updated", name=name if isinstance(name, str) else None, **persisted
        )
    return TaskUpdatedFrame(type="task.updated", status="archived", **persisted)


def _encode_frame(frame: dict[str, Any]) -> str:
    """Serialize one validated persisted SSE frame with the protocol envelope."""
    payload = json.dumps(frame, separators=(",", ":"))
    return f"id: {frame['sequence']}\nevent: {frame['type']}\ndata: {payload}\n\n"


def _encode_tick(tick: Tick) -> str:
    """Serialize a validated ephemeral frame without an SSE id line."""
    stage = cast(StageKey | None, tick.stage) if tick.stage in _STAGE_PRESENTATION else None
    frame = TickFrame(type="tick", stage=stage, note=tick.note, occurred_at=tick.occurred_at)
    return f"event: tick\ndata: {frame.model_dump_json()}\n\n"


@router.get("/{task_id}/events")
async def stream_events(
    task_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
    cursor: Annotated[int, Query(ge=0)] = 0,
) -> StreamingResponse:
    """Stream a read-graded durable replay followed by a re-authorising live tail.

    The replay is authorised once by ``_snapshot``; the tail re-authorises on
    every batch through the same read legs and ends the response the moment the
    caller's access is gone (contract § 5). **Re-authorisation precedes every
    frame of its iteration, ephemeral ticks included** — see the loop.
    """
    snapshot, replay = await anyio.to_thread.run_sync(
        partial(_snapshot, engine, task_id=task_id, user_id=user.user_id, cursor=cursor)
    )

    async def body() -> AsyncIterator[str]:
        queue = await tick_hub.subscribe(task_id)
        next_sequence = max(snapshot + 1, cursor + 1)
        last_heartbeat = asyncio.get_running_loop().time()
        try:
            for frame in replay:
                yield _encode_frame(frame)
            while True:
                now = asyncio.get_running_loop().time()
                heartbeat_remaining = max(
                    0.0, settings.sse_heartbeat_seconds - (now - last_heartbeat)
                )
                timeout = min(settings.sse_poll_interval_seconds, heartbeat_remaining)
                try:
                    tick = await asyncio.wait_for(queue.get(), timeout=timeout)
                except TimeoutError:
                    tick = None
                # The tick is **held**, not yielded, until the tail has
                # re-authorised. A tick carries the task's current stage and
                # its progress note — task-derived content — so yielding it
                # first handed a caller whose access had just gone one more
                # frame about work they may no longer read. Re-authorisation is
                # the first thing every iteration does; nothing is written to
                # the response before it answers.
                pending_tick = _encode_tick(tick) if tick is not None else None
                batch = await anyio.to_thread.run_sync(
                    partial(
                        _tail,
                        engine,
                        task_id=task_id,
                        user_id=user.user_id,
                        after=next_sequence - 1,
                    )
                )
                # Access revoked mid-stream. Ending the generator completes the
                # HTTP response and the client's `EventSource` sees a normal
                # close; the protocol carries no error frame and inventing one
                # here would be a new public frame type.
                if batch is None:
                    log.info("api.sse_revoked", task_id=str(task_id))
                    return
                last_sequence, tail = batch
                # Order within the iteration is unchanged: the ephemeral tick
                # still precedes the durable frames it was observed alongside.
                if pending_tick is not None:
                    yield pending_tick
                for frame in tail:
                    yield _encode_frame(frame)
                next_sequence = last_sequence + 1
                now = asyncio.get_running_loop().time()
                if now - last_heartbeat >= settings.sse_heartbeat_seconds:
                    yield ": keep-alive\n\n"
                    last_heartbeat = now
        finally:
            await tick_hub.unsubscribe(task_id, queue)
            log.debug("api.sse_closed", task_id=str(task_id))

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"},
    )
