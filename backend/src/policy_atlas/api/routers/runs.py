"""Capability-run dispatch and read resource routes."""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from policy_atlas.api.app import ApiConflict
from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract import RunCreate, RunOut
from policy_atlas.api.contract.common import PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX, Page, PageMeta
from policy_atlas.api.deps import (
    get_current_user,
    get_engine,
    get_executor,
    get_runner_backends,
    get_settings,
)
from policy_atlas.api.routers._common import owned_project, run_out
from policy_atlas.api.run_io import ParkIO
from policy_atlas.api.settings import Settings
from policy_atlas.core.schema import capability_run, orchestration_plan, planning_transcript
from policy_atlas.runtime.orchestration_plan import OrchestrationPlan
from policy_atlas.runtime.runner import RunnerBackends, run_plan

log = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/projects",
    tags=["runs"],
    dependencies=[Depends(get_current_user)],
)

_dispatch_lock = threading.Lock()
_dispatching_projects: set[uuid.UUID] = set()


def dispatch_reserved(project_id: uuid.UUID) -> bool:
    """Whether a run admission for the project is in its pre-insert window.

    The reservation lives in process memory between run admission and the
    executor's capability-run insert; archive must consult it or it can win
    that window and archive a project whose run then executes hidden (review
    finding codex-9, 2026-07-21). Sound under the pinned one-instance posture —
    the same posture the reservation itself relies on.
    """
    with _dispatch_lock:
        return project_id in _dispatching_projects


def _dispatch_run(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    plan_row: dict[str, object],
    backends: RunnerBackends,
) -> None:
    """Run one approved walk on an executor worker and release its reservation."""
    try:
        run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=plan_row["evidence_scope_id"],  # type: ignore[arg-type]
            plan=OrchestrationPlan.model_validate(plan_row["payload"]),
            plan_id=plan_row["plan_id"],  # type: ignore[arg-type]
            plan_version=plan_row["version"],  # type: ignore[arg-type]
            plan_row_id=plan_row["plan_id"],  # type: ignore[arg-type]
            backends=backends,
            io=ParkIO(),
        )
    except Exception:
        log.exception("api.run_dispatch_failed", project_id=str(project_id))
    finally:
        with _dispatch_lock:
            _dispatching_projects.discard(project_id)


def _await_new_run(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    existing_ids: set[uuid.UUID],
) -> RunOut:
    """Wait briefly for the executor's runtime-owned capability-run insertion."""
    # 10s, not 2s: with both executor workers momentarily busy the submitted
    # dispatch can queue past 2s, turning a successful launch into a client 500
    # (review finding I3, 2026-07-21). The walk still starts either way; the
    # longer window keeps the response truthful for the transient case.
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            rows = conn.execute(
                select(capability_run)
                .where(capability_run.c.project_id == project_id)
                .order_by(
                    capability_run.c.started_at.desc(),
                    capability_run.c.capability_run_id.desc(),
                )
            ).mappings().all()
        for row in rows:
            if row["capability_run_id"] not in existing_ids:
                return run_out(row)
        time.sleep(0.01)
    raise RuntimeError("executor did not create a capability run")


@router.post("/{project_id}/runs", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def create_run(
    project_id: uuid.UUID,
    _: RunCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
    executor: Annotated[ThreadPoolExecutor, Depends(get_executor)],
    backends: Annotated[RunnerBackends, Depends(get_runner_backends)],
) -> RunOut:
    """Dispatch an approved plan off the request path and return its walk row."""
    with _dispatch_lock:
        with engine.begin() as conn:
            owned_project(conn, project_id=project_id, user_id=user.user_id, for_update=True)
            active = conn.execute(
                select(capability_run.c.capability_run_id)
                .where(capability_run.c.project_id == project_id)
                .where(capability_run.c.status.in_(("running", "paused")))
                .limit(1)
            ).scalar_one_or_none()
            if active is not None or project_id in _dispatching_projects:
                raise ApiConflict("run_active", "the project already has an active run")
            running = conn.execute(
                select(capability_run.c.capability_run_id)
                .where(capability_run.c.status == "running")
            ).all()
            if len(running) + len(_dispatching_projects) >= settings.run_executor_max:
                raise ApiConflict("capacity", "the walk executor is at capacity")
            plan_row = conn.execute(
                select(orchestration_plan)
                .where(orchestration_plan.c.project_id == project_id)
                .where(orchestration_plan.c.status == "approved")
                .order_by(orchestration_plan.c.version.desc())
                .limit(1)
            ).mappings().one_or_none()
            if plan_row is None:
                raise HTTPException(status_code=400, detail="no approved plan")
            approved_plan = OrchestrationPlan.model_validate(plan_row["payload"])
            latest_completed_turn = conn.execute(
                select(func.max(planning_transcript.c.turn_index))
                .where(planning_transcript.c.project_id == project_id)
                .where(planning_transcript.c.status == "completed")
            ).scalar_one()
            if (
                approved_plan.source_turn_index is not None
                and latest_completed_turn is not None
                and approved_plan.source_turn_index < latest_completed_turn
            ):
                raise ApiConflict(
                    "plan_stale",
                    "the plan predates your latest planning message — review it, then start",
                )
            existing_ids = {
                row[0]
                for row in conn.execute(
                    select(capability_run.c.capability_run_id).where(
                        capability_run.c.project_id == project_id
                    )
                )
            }
            _dispatching_projects.add(project_id)
        executor.submit(
            _dispatch_run,
            engine,
            project_id=project_id,
            plan_row=dict(plan_row),
            backends=backends,
        )
    created = _await_new_run(engine, project_id=project_id, existing_ids=existing_ids)
    # Once the runtime row exists, the database's ``running`` count owns
    # capacity accounting; keeping the launch reservation would double-count.
    with _dispatch_lock:
        _dispatching_projects.discard(project_id)
    return created


@router.get("/{project_id}/runs", response_model=Page[RunOut])
def list_runs(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
) -> Page[RunOut]:
    """List a project's walks from newest to oldest (paginated — runs accumulate)."""
    with engine.connect() as conn:
        owned_project(conn, project_id=project_id, user_id=user.user_id)
        total = conn.execute(
            select(func.count())
            .select_from(capability_run)
            .where(capability_run.c.project_id == project_id)
        ).scalar_one()
        rows = conn.execute(
            select(capability_run)
            .where(capability_run.c.project_id == project_id)
            .order_by(capability_run.c.started_at.desc(), capability_run.c.capability_run_id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).mappings().all()
    return Page(
        data=[run_out(row) for row in rows],
        pagination=PageMeta(page=page, page_size=page_size, total_items=int(total)),
    )


@router.get("/{project_id}/runs/{run_id}", response_model=RunOut)
def get_run(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
) -> RunOut:
    """Return one owned project's capability run, or the opaque 404."""
    with engine.connect() as conn:
        owned_project(conn, project_id=project_id, user_id=user.user_id)
        row = conn.execute(
            select(capability_run)
            .where(capability_run.c.project_id == project_id)
            .where(capability_run.c.capability_run_id == run_id)
        ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="resource not found")
    return run_out(row)
