"""Project-scoped planner turns backed by a bounded process-local session cache."""

from __future__ import annotations

import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.app import ApiConflict
from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract import (
    PlanDraft,
    PlanningTurnCreate,
    PlanningTurnOut,
    PlanOut,
    PlanStep,
)
from policy_atlas.api.deps import get_current_user, get_engine, get_planner_backend
from policy_atlas.api.routers._common import owned_project
from policy_atlas.core.schema import orchestration_plan
from policy_atlas.runtime.orchestrate import build_plan, persist_approved_plan
from policy_atlas.runtime.orchestration_plan import OrchestrationPlan, compose
from policy_atlas.runtime.planner import PlannerBackend
from policy_atlas.runtime.planner_prompt import PlanDraftWire

router = APIRouter(
    prefix="/api/v1/projects",
    tags=["planning"],
    dependencies=[Depends(get_current_user)],
)

# This is deliberately process-local: approved plans are durable, while a
# pre-approval conversation honestly vanishes on restart or bounded eviction.
PLAN_SESSION_CACHE_MAX = 128
_cache_lock = threading.Lock()
_sessions: OrderedDict[uuid.UUID, _PlanningSession] = OrderedDict()


@dataclass
class _PlanningSession:
    """One project's ephemeral planner conversation and idempotent responses."""

    turns: list[dict[str, str]] = field(default_factory=list)
    previous_draft: dict[str, object] | None = None
    draft: PlanDraft | None = None
    results: OrderedDict[uuid.UUID, PlanningTurnOut] = field(default_factory=OrderedDict)
    session_id: uuid.UUID = field(default_factory=uuid.uuid4)
    lock: threading.Lock = field(default_factory=threading.Lock)


def _session(project_id: uuid.UUID) -> _PlanningSession:
    """Return an LRU-bounded session, evicting only unrecoverable drafts."""
    with _cache_lock:
        cached = _sessions.get(project_id)
        if cached is not None:
            _sessions.move_to_end(project_id)
            return cached
        cached = _PlanningSession()
        _sessions[project_id] = cached
        while len(_sessions) > PLAN_SESSION_CACHE_MAX:
            _sessions.popitem(last=False)
        return cached


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
    values["ready"] = ready
    return PlanDraft.model_validate(values)


def _draft_from_plan(plan: OrchestrationPlan) -> PlanDraft:
    """Project a validated runtime plan into the API's approved draft shape."""
    values = plan.model_dump(mode="json")
    values.pop("steer_point_defaults", None)
    values["steps"] = [
        PlanStep(label=step.component.replace("_", " ").title(), blurb="", stage=step.component)
        for step in compose(plan).steps
    ]
    values["ready"] = True
    return PlanDraft.model_validate(values)


@router.post("/{project_id}/planning-turns", response_model=PlanningTurnOut)
def create_planning_turn(
    project_id: uuid.UUID,
    payload: PlanningTurnCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    planner: Annotated[PlannerBackend, Depends(get_planner_backend)],
) -> PlanningTurnOut:
    """Advance one project's real planner conversation once per client turn id."""
    session = _session(project_id)
    existing = session.results.get(payload.client_turn_id)
    if existing is not None:
        return existing
    if not session.lock.acquire(blocking=False):
        raise ApiConflict("planning_turn_in_progress", "a planning turn is already running")
    try:
        existing = session.results.get(payload.client_turn_id)
        if existing is not None:
            return existing
        with engine.begin() as conn:
            owned_project(conn, project_id=project_id, user_id=user.user_id, for_update=True)
            session.turns.append({"role": "user", "text": payload.message})
            turn = planner.plan_turn(
                session.turns,
                session.previous_draft,
                session_id=session.session_id,
            )
            session.turns.append({"role": "planner", "text": turn.reply})
            session.previous_draft = turn.plan_draft.model_dump()
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
            if approved is not None:
                persist_approved_plan(conn, project_id=project_id, plan=approved)
            result = PlanningTurnOut(
                reply=turn.reply,
                plan=draft,
                suggestions=turn.suggested_answers or [],
            )
            session.draft = draft
            session.results[payload.client_turn_id] = result
            while len(session.results) > PLAN_SESSION_CACHE_MAX:
                session.results.popitem(last=False)
            return result
    finally:
        session.lock.release()


@router.get("/{project_id}/plan", response_model=PlanOut)
def get_plan(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
) -> PlanOut:
    """Return the durable approved plan or the surviving local draft session."""
    with engine.connect() as conn:
        owned_project(conn, project_id=project_id, user_id=user.user_id)
        row = conn.execute(
            select(orchestration_plan)
            .where(orchestration_plan.c.project_id == project_id)
            .where(orchestration_plan.c.status == "approved")
            .order_by(orchestration_plan.c.version.desc())
            .limit(1)
        ).mappings().one_or_none()
    if row is not None:
        return PlanOut(
            plan=_draft_from_plan(OrchestrationPlan.model_validate(row["payload"])),
            version=row["version"],
            status=row["status"],
        )
    session = _sessions.get(project_id)
    if session is None or session.draft is None:
        raise HTTPException(status_code=404, detail="resource not found")
    return PlanOut(plan=session.draft, version=0, status="draft")
