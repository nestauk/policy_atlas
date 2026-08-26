"""Authenticated replay-then-tail server-sent events for project activity."""

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

from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.checkin_read import _check_in
from policy_atlas.api.contract import (
    ArtefactSectionCompletedFrame,
    ArtefactSectionStartedFrame,
    ArtefactSkeletonFrame,
    CheckinPendingFrame,
    CheckinResolvedFrame,
    PlanUpdatedFrame,
    ProjectUpdatedFrame,
    RunStatus,
    RunStatusFrame,
    StageCompletedFrame,
    StageFailedFrame,
    StageKey,
    StageStartedFrame,
    TickFrame,
)
from policy_atlas.api.deps import get_current_user, get_engine, get_settings
from policy_atlas.api.routers._common import owned_project
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
from policy_atlas.core.schema import event_log, orchestration_plan
from policy_atlas.runtime.orchestration_plan import OrchestrationPlan

log = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/projects",
    tags=["events"],
    dependencies=[Depends(get_current_user)],
)

def _snapshot(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    user_id: str,
    cursor: int,
) -> tuple[int, list[dict[str, Any]]]:
    """Authorise then read a cursor-bounded durable backlog in one connection."""
    with engine.connect() as conn:
        owned_project(conn, project_id=project_id, user_id=user_id)
        snapshot = int(
            conn.execute(
                select(func.coalesce(func.max(event_log.c.sequence), 0)).where(
                    event_log.c.project_id == project_id
                )
            ).scalar_one()
        )
        rows = _event_rows(conn, project_id=project_id, after=cursor, through=snapshot)
        return snapshot, _map_rows(conn, project_id=project_id, rows=rows, through=snapshot)


def _tail(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    after: int,
) -> tuple[int, list[dict[str, Any]]]:
    """Read and map the next durable tail batch without blocking the event loop."""
    with engine.connect() as conn:
        rows = _event_rows(conn, project_id=project_id, after=after, through=None)
        last_sequence = rows[-1]["sequence"] if rows else after
        return last_sequence, _map_rows(conn, project_id=project_id, rows=rows, through=None)


def _event_rows(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    after: int,
    through: int | None,
) -> list[dict[str, Any]]:
    """Read ordered durable events in the inclusive/exclusive SSE sequence interval."""
    statement = select(event_log).where(event_log.c.project_id == project_id).where(
        event_log.c.sequence > after
    )
    if through is not None:
        statement = statement.where(event_log.c.sequence <= through)
    return [dict(row._mapping) for row in conn.execute(statement.order_by(event_log.c.sequence))]


def _map_rows(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    rows: Iterable[dict[str, Any]],
    through: int | None,
) -> list[dict[str, Any]]:
    """Map allowlisted durable event rows to validated public frame models."""
    all_rows = list(rows)
    if not all_rows:
        return []
    # The full-history context exists solely for the decided-pause check, so
    # fetch it only when this batch carries a pause, and fetch decisions only.
    # The previous unconditional after=0 read re-scanned the whole project log
    # (large JSONB payloads included) every poll interval per client, even
    # when idle (review finding backend-M1, 2026-07-21).
    decision_events: list[dict[str, Any]] = []
    if any(row["event_type"] == "steering.pause" for row in all_rows):
        decision_events = [
            row
            for row in events.read(conn, project_id, event_types=["steering.decision"])
            if through is None or row["sequence"] <= through
        ]
    frames: list[dict[str, Any]] = []
    for row in all_rows:
        frames.extend(
            _frames_for_row(conn, project_id=project_id, row=row, all_events=decision_events)
        )
    return frames


def _frames_for_row(
    conn: Connection,
    *,
    project_id: uuid.UUID,
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
                seconds=_seconds(conn, project_id=project_id, row=row, payload=payload),
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
        frames = _decision_frames(conn, project_id=project_id, payload=payload, persisted=persisted)
        return [frame.model_dump(mode="json") for frame in frames]
    if event_type == "plan.approved":
        plan_frame = _plan_frame(conn, project_id=project_id, payload=payload, persisted=persisted)
        return [plan_frame.model_dump(mode="json")] if plan_frame is not None else []
    if event_type in {"project.renamed", "project.archived"}:
        project_frame = _project_frame(
            conn,
            project_id=project_id,
            event_type=event_type,
            payload=payload,
            persisted=persisted,
        )
        return [project_frame.model_dump(mode="json")]
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
    project_id: uuid.UUID,
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
        .where(event_log.c.project_id == project_id)
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
    project_id: uuid.UUID,
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
            .where(event_log.c.project_id == project_id)
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
    frame: list[CheckinResolvedFrame | PlanUpdatedFrame] = [
        CheckinResolvedFrame(
            type="checkin.resolved",
            check_in_id=check_in_id,
            response=(
                response if isinstance(response, dict) else {"response": payload.get("response")}
            ),
            decided_by=(
                payload.get("decided_by")
                if payload.get("decided_by") in {"user", "orchestrator", "standing_default"}
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
                project_id=project_id,
                payload={"version": version + 1},
                persisted=persisted,
            )
            if plan_frame is not None:
                frame.append(plan_frame)
    return frame


def _plan_frame(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    payload: dict[str, Any],
    persisted: dict[str, Any],
) -> PlanUpdatedFrame | None:
    """Load the versioned plan row and project it through the public contract."""
    version = payload.get("version")
    if not isinstance(version, int):
        return None
    row = conn.execute(
        select(orchestration_plan)
        .where(orchestration_plan.c.project_id == project_id)
        .where(orchestration_plan.c.version == version)
    ).mappings().one_or_none()
    if row is None or not isinstance(row["payload"], dict):
        return None
    plan = _draft_from_plan(OrchestrationPlan.model_validate(row["payload"]))
    return PlanUpdatedFrame(type="plan.updated", plan=plan, version=version, **persisted)


def _project_frame(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
    persisted: dict[str, Any],
) -> ProjectUpdatedFrame:
    """Project a lifecycle audit event without leaking its actor or old values."""
    del conn, project_id
    if event_type == "project.renamed":
        name = payload.get("name_to")
        return ProjectUpdatedFrame(
            type="project.updated", name=name if isinstance(name, str) else None, **persisted
        )
    return ProjectUpdatedFrame(type="project.updated", status="archived", **persisted)


def _encode_frame(frame: dict[str, Any]) -> str:
    """Serialize one validated persisted SSE frame with the protocol envelope."""
    payload = json.dumps(frame, separators=(",", ":"))
    return f"id: {frame['sequence']}\nevent: {frame['type']}\ndata: {payload}\n\n"


def _encode_tick(tick: Tick) -> str:
    """Serialize a validated ephemeral frame without an SSE id line."""
    stage = cast(StageKey | None, tick.stage) if tick.stage in _STAGE_PRESENTATION else None
    frame = TickFrame(type="tick", stage=stage, note=tick.note, occurred_at=tick.occurred_at)
    return f"event: tick\ndata: {frame.model_dump_json()}\n\n"


@router.get("/{project_id}/events")
async def stream_events(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
    cursor: Annotated[int, Query(ge=0)] = 0,
) -> StreamingResponse:
    """Stream an owner-scoped durable replay followed by a non-blocking live tail."""
    snapshot, replay = await anyio.to_thread.run_sync(
        partial(_snapshot, engine, project_id=project_id, user_id=user.user_id, cursor=cursor)
    )

    async def body() -> AsyncIterator[str]:
        queue = await tick_hub.subscribe(project_id)
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
                if tick is not None:
                    yield _encode_tick(tick)
                last_sequence, tail = await anyio.to_thread.run_sync(
                    partial(_tail, engine, project_id=project_id, after=next_sequence - 1)
                )
                for frame in tail:
                    yield _encode_frame(frame)
                next_sequence = last_sequence + 1
                now = asyncio.get_running_loop().time()
                if now - last_heartbeat >= settings.sse_heartbeat_seconds:
                    yield ": keep-alive\n\n"
                    last_heartbeat = now
        finally:
            await tick_hub.unsubscribe(project_id, queue)
            log.debug("api.sse_closed", project_id=str(project_id))

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"},
    )
