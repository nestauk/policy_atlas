"""Capability-run dispatch and read resource routes."""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.app import ApiConflict
from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract import RunCreate, RunOut
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
from policy_atlas.core.schema import capability_run, orchestration_plan
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
    deadline = time.monotonic() + 2.0
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


@router.get("/{project_id}/runs", response_model=list[RunOut])
def list_runs(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
) -> list[RunOut]:
    """List a project's walks from newest to oldest."""
    with engine.connect() as conn:
        owned_project(conn, project_id=project_id, user_id=user.user_id)
        rows = conn.execute(
            select(capability_run)
            .where(capability_run.c.project_id == project_id)
            .order_by(capability_run.c.started_at.desc(), capability_run.c.capability_run_id.desc())
        ).mappings().all()
    return [run_out(row) for row in rows]


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
