"""Project-scoped planner turns backed by a durable transcript."""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import func, select, update
from sqlalchemy.engine import Connection, Engine, RowMapping

from policy_atlas.api.app import ApiConflict
from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract import (
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_MAX,
    Page,
    PageMeta,
    PlanDraft,
    PlanningTranscriptTurnOut,
    PlanningTurnCreate,
    PlanningTurnOut,
    PlanOut,
    PlanStep,
)
from policy_atlas.api.deps import get_current_user, get_engine, get_planner_backend
from policy_atlas.api.routers._common import owned_project
from policy_atlas.api.stage_vocabulary import STAGE_BY_REGISTRY, STAGE_PRESENTATION
from policy_atlas.core.schema import capability_run, orchestration_plan, planning_transcript
from policy_atlas.runtime.orchestrate import build_plan, persist_approved_plan
from policy_atlas.runtime.orchestration_plan import (
    TIME_BANDS,
    OrchestrationPlan,
    compose,
    registry_component_for,
)
from policy_atlas.runtime.planner import PlannerBackend
from policy_atlas.runtime.planner_prompt import PlanDraftWire

router = APIRouter(
    prefix="/api/v1/projects",
    tags=["planning"],
    dependencies=[Depends(get_current_user)],
)

_PENDING_TTL = timedelta(minutes=10)
_turn_locks_guard = threading.Lock()
_turn_locks: dict[uuid.UUID, threading.Lock] = {}


def _turn_lock(project_id: uuid.UUID) -> threading.Lock:
    """Return the process-local concurrency guard for one project's planner turn."""
    with _turn_locks_guard:
        return _turn_locks.setdefault(project_id, threading.Lock())


def _now() -> datetime:
    """Return a timezone-aware persistence timestamp."""
    return datetime.now(UTC)


def _expire_stale_pending_turns(conn: Connection, project_id: uuid.UUID) -> None:
    """Terminally fail pending transcript rows older than the retry window."""
    now = _now()
    conn.execute(
        update(planning_transcript)
        .where(planning_transcript.c.project_id == project_id)
        .where(planning_transcript.c.status == "pending")
        .where(planning_transcript.c.created_at < now - _PENDING_TTL)
        .values(status="failed", completed_at=now)
    )


def _draft_from_wire(draft: PlanDraftWire, *, ready: bool) -> PlanDraft:
    """Translate the runtime planner wire into the standalone API draft model."""
    values = draft.model_dump(exclude_none=True)
    constraints: dict[str, Any] = {}
    for key in (
        "published_after",
        "published_before",
        "publisher_country",
        "author_affiliation_countries",
        "country_group",
    ):
        value = values.pop(key, None)
        if value is not None:
            constraints[key] = value
    if constraints:
        values["scope_constraints"] = constraints
    values.pop("steer_point_defaults", None)
    effort, depth = values.get("search_effort"), values.get("analysis_depth")
    if effort in {"rapid", "standard", "deep"} and depth in {"landscape", "standard", "deep"}:
        values["time_band"] = TIME_BANDS[(effort, depth)]
    values["ready"] = ready
    return PlanDraft.model_validate(values)


def _draft_from_plan(plan: OrchestrationPlan) -> PlanDraft:
    """Project a validated runtime plan into the API's approved draft shape."""
    values = plan.model_dump(mode="json")
    values.pop("steer_point_defaults", None)
    steps: list[PlanStep] = []
    seen_stages: set[str] = set()
    for step in compose(plan).steps:
        registry_component = registry_component_for(step.component)
        stage = STAGE_BY_REGISTRY[registry_component]
        if stage in seen_stages:
            continue
        seen_stages.add(stage)
        label, blurb = STAGE_PRESENTATION[stage]
        steps.append(PlanStep(label=label, blurb=blurb, stage=stage))
    values["steps"] = steps
    values["ready"] = True
    return PlanDraft.model_validate(values)


def _response_from_row(row: RowMapping) -> PlanningTurnOut:
    """Return a completed turn's stored projected response without recomputing it."""
    response = row["response"]
    if response is None:
        raise RuntimeError("completed planning transcript row has no response")
    return PlanningTurnOut.model_validate(response)


def _planner_inputs(
    conn: Connection, project_id: uuid.UUID
) -> tuple[list[dict[str, str]], dict[str, object] | None]:
    """Rehydrate the exact planner context from completed transcript rows."""
    rows = conn.execute(
        select(planning_transcript)
        .where(planning_transcript.c.project_id == project_id)
        .where(planning_transcript.c.status == "completed")
        .order_by(planning_transcript.c.turn_index.asc())
    ).mappings()
    turns: list[dict[str, str]] = []
    previous_draft: dict[str, object] | None = None
    for row in rows:
        reply = row["reply"]
        planner_state = row["planner_state"]
        if reply is None or planner_state is None:
            raise RuntimeError("completed planning transcript row is incomplete")
        turns.extend((
            {"role": "user", "text": row["user_message"]},
            {"role": "planner", "text": reply},
        ))
        previous_draft = cast("dict[str, object]", planner_state)
    return turns, previous_draft


def _transcript_out(row: RowMapping) -> PlanningTranscriptTurnOut:
    """Project one durable transcript row into its honest read representation."""
    return PlanningTranscriptTurnOut(
        turn_index=row["turn_index"],
        client_turn_id=row["client_turn_id"],
        user_message=row["user_message"],
        reply=row["reply"],
        suggestions=row["suggestions"],
        status=row["status"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
    )


def _phase_one_turn(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    user_id: str,
    payload: PlanningTurnCreate,
) -> PlanningTurnOut | uuid.UUID:
    """Authenticate, fence, and either replay or durably reserve one turn."""
    owned_project(conn, project_id=project_id, user_id=user_id)
    _expire_stale_pending_turns(conn, project_id)
    existing = conn.execute(
        select(planning_transcript)
        .where(planning_transcript.c.project_id == project_id)
        .where(planning_transcript.c.client_turn_id == payload.client_turn_id)
    ).mappings().one_or_none()
    if existing is not None:
        if existing["user_message"] != payload.message:
            raise ApiConflict(
                "stale_turn", "client turn id is already bound to a different message"
            )
        if existing["status"] == "completed":
            return _response_from_row(existing)

    active = conn.execute(
        select(capability_run.c.status)
        .where(capability_run.c.project_id == project_id)
        .where(capability_run.c.status.in_(("running", "paused")))
        .limit(1)
    ).scalar_one_or_none()
    if active is not None:
        raise ApiConflict(
            "run_active",
            "finish or stop the current run before replanning; "
            "use the run's check-ins to steer it",
        )

    if existing is not None:
        latest_id = conn.execute(
            select(planning_transcript.c.id)
            .where(planning_transcript.c.project_id == project_id)
            .order_by(planning_transcript.c.turn_index.desc())
            .limit(1)
        ).scalar_one()
        if latest_id != existing["id"]:
            raise ApiConflict("stale_turn", "only the latest planning turn may be retried")
        return cast(uuid.UUID, existing["id"])

    pending = conn.execute(
        select(planning_transcript.c.id)
        .where(planning_transcript.c.project_id == project_id)
        .where(planning_transcript.c.status == "pending")
        .limit(1)
    ).scalar_one_or_none()
    if pending is not None:
        raise ApiConflict("planning_turn_in_progress", "a planning turn is already running")

    max_turn_index = conn.execute(
        select(func.coalesce(func.max(planning_transcript.c.turn_index), -1)).where(
            planning_transcript.c.project_id == project_id
        )
    ).scalar_one()
    transcript_id = uuid.uuid4()
    conn.execute(
        planning_transcript.insert().values(
            id=transcript_id,
            project_id=project_id,
            client_turn_id=payload.client_turn_id,
            turn_index=int(max_turn_index) + 1,
            user_message=payload.message,
            reply=None,
            planner_state=None,
            response=None,
            suggestions=[],
            status="pending",
            created_at=_now(),
            completed_at=None,
        )
    )
    return transcript_id


@router.post("/{project_id}/planning-turns", response_model=PlanningTurnOut)
def create_planning_turn(
    project_id: uuid.UUID,
    payload: PlanningTurnCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    planner: Annotated[PlannerBackend, Depends(get_planner_backend)],
) -> PlanningTurnOut:
    """Advance one project's durable planner conversation once per client turn id."""
    lock = _turn_lock(project_id)
    if not lock.acquire(blocking=False):
        raise ApiConflict("planning_turn_in_progress", "a planning turn is already running")
    try:
        # Phase 1 is deliberately short. The planner call below must remain
        # OUTSIDE any transaction: holding the project row lock (and a pool
        # connection) across a live LLM call blocked every mutation on the
        # project — and via the global dispatch lock, run creation process-wide
        # (review finding I2, 2026-07-21).
        with engine.begin() as conn:
            phase_one = _phase_one_turn(
                conn,
                project_id=project_id,
                user_id=user.user_id,
                payload=payload,
            )
        if isinstance(phase_one, PlanningTurnOut):
            return phase_one

        with engine.connect() as conn:
            turns, previous_draft = _planner_inputs(conn, project_id)
        turns.append({"role": "user", "text": payload.message})
        try:
            turn = planner.plan_turn(turns, previous_draft, session_id=uuid.uuid4())
        except Exception:
            with engine.begin() as conn:
                conn.execute(
                    update(planning_transcript)
                    .where(planning_transcript.c.id == phase_one)
                    .where(planning_transcript.c.project_id == project_id)
                    .where(planning_transcript.c.status.in_(("pending", "failed")))
                    .values(status="failed", completed_at=_now())
                )
            raise

        ready = turn.ready
        approved: OrchestrationPlan | None = None
        if ready:
            try:
                approved = build_plan(turn.plan_draft)
            except ValidationError:
                ready = False
        draft = _draft_from_plan(approved) if approved is not None else _draft_from_wire(
            turn.plan_draft, ready=ready
        )
        result = PlanningTurnOut(
            reply=turn.reply,
            plan=draft,
            suggestions=turn.suggested_answers or [],
        )
        phase_two_values = {
            "reply": turn.reply,
            "planner_state": turn.plan_draft.model_dump(mode="json"),
            "response": result.model_dump(mode="json"),
            "suggestions": result.suggestions,
            "status": "completed",
            "completed_at": _now(),
        }
        # Phase 2 joins plan approval in the same transaction, so an approved
        # plan can never commit without the transcript turn that approved it.
        with engine.begin() as conn:
            if approved is not None:
                owned_project(conn, project_id=project_id, user_id=user.user_id, for_update=True)
            completed = conn.execute(
                update(planning_transcript)
                .where(planning_transcript.c.id == phase_one)
                .where(planning_transcript.c.project_id == project_id)
                # A fresh turn completes from "pending"; a retried latest turn
                # re-runs in place from "failed" (retry rules, plan pin 2).
                .where(planning_transcript.c.status.in_(("pending", "failed")))
                .values(**phase_two_values)
            )
            if completed.rowcount != 1:
                raise RuntimeError("planning transcript turn was not open at phase two")
            if approved is not None:
                persist_approved_plan(conn, project_id=project_id, plan=approved)
        return result
    finally:
        lock.release()


@router.get("/{project_id}/planning-turns", response_model=Page[PlanningTranscriptTurnOut])
def list_planning_turns(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
) -> Page[PlanningTranscriptTurnOut]:
    """Return the durable planning transcript in ascending conversation order."""
    with engine.begin() as conn:
        owned_project(conn, project_id=project_id, user_id=user.user_id)
        _expire_stale_pending_turns(conn, project_id)
        total_items = conn.execute(
            select(func.count())
            .select_from(planning_transcript)
            .where(planning_transcript.c.project_id == project_id)
        ).scalar_one()
        rows = conn.execute(
            select(planning_transcript)
            .where(planning_transcript.c.project_id == project_id)
            .order_by(planning_transcript.c.turn_index.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).mappings().all()
    return Page(
        data=[_transcript_out(row) for row in rows],
        pagination=PageMeta(page=page, page_size=page_size, total_items=total_items),
    )


@router.get("/{project_id}/plan", response_model=PlanOut)
def get_plan(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
) -> PlanOut:
    """Return the durable approved plan or latest completed durable draft."""
    with engine.begin() as conn:
        owned_project(conn, project_id=project_id, user_id=user.user_id)
        _expire_stale_pending_turns(conn, project_id)
        row = conn.execute(
            select(orchestration_plan)
            .where(orchestration_plan.c.project_id == project_id)
            .where(orchestration_plan.c.status == "approved")
            .order_by(orchestration_plan.c.version.desc())
            .limit(1)
        ).mappings().one_or_none()
        if row is None:
            draft_row = conn.execute(
                select(planning_transcript.c.response)
                .where(planning_transcript.c.project_id == project_id)
                .where(planning_transcript.c.status == "completed")
                .order_by(planning_transcript.c.turn_index.desc())
                .limit(1)
            ).mappings().one_or_none()
        else:
            draft_row = None
    if row is not None:
        return PlanOut(
            plan=_draft_from_plan(OrchestrationPlan.model_validate(row["payload"])),
            version=row["version"],
            status=row["status"],
        )
    if draft_row is None or draft_row["response"] is None:
        raise HTTPException(status_code=404, detail="resource not found")
    response = PlanningTurnOut.model_validate(draft_row["response"])
    return PlanOut(plan=response.plan, version=0, status="draft")
