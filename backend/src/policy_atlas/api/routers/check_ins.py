"""Durable steering check-in reads and response dispatch routes."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Any, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api import continuation
from policy_atlas.api.app import ApiConflict
from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.checkin_read import _check_in
from policy_atlas.api.contract import CheckInOut, CheckInResponse, FreeTextCompileOut
from policy_atlas.api.contract.common import PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX, Page, PageMeta
from policy_atlas.api.deps import (
    get_current_user,
    get_engine,
    get_executor,
    get_orchestrator_backend,
    get_runner_backends,
)
from policy_atlas.api.routers._common import owned_project
from policy_atlas.api.run_io import ParkIO
from policy_atlas.core import events
from policy_atlas.core.schema import capability_run
from policy_atlas.runtime.orchestrator_backend import OrchestratorBackend
from policy_atlas.runtime.runner import RunnerBackends
from policy_atlas.runtime.steering_history import steering_history

log = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/projects",
    tags=["check-ins"],
    dependencies=[Depends(get_current_user)],
)


def _walk_pause_rows(conn: Connection, project_id: uuid.UUID) -> list[dict[str, Any]]:
    """Read pauses through the steering-history projection with event identities attached."""
    history = steering_history(conn, project_id)
    walk_ids = {str(story["capability_run_id"]) for story in history}
    return [
        event
        for event in events.read(conn, project_id)
        if event["event_type"] == "steering.pause"
        and isinstance(event["payload"], dict)
        and event["payload"].get("capability_run_id") in walk_ids
    ]


@router.get("/{project_id}/check-ins", response_model=Page[CheckInOut])
def list_check_ins(
    project_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    status_filter: Annotated[Literal["pending", "all"], Query(alias="status")] = "pending",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
) -> Page[CheckInOut]:
    """Return a latest pending card or the durable steering history projection.

    Paginated (rubric item 17 — check-ins accumulate over a project's life);
    the pending view is at most one card by construction.
    """
    with engine.connect() as connection:
        owned_project(connection, project_id=project_id, user_id=user.user_id)
        pauses = _walk_pause_rows(connection, project_id)
        all_events = events.read(connection, project_id)
        latest_walk = next(
            (
                story["capability_run_id"]
                for story in reversed(steering_history(connection, project_id))
            ),
            None,
        )
        # Pending means answerable: the walk must actually be parked. A death
        # between pause-emit and park leaves an undecided pause on a walk the
        # sweep marks interrupted — rendering that as pending shows a card
        # whose answer always 404s (review finding, 2026-07-21; the answer
        # path's _pending_pause has required paused status all along).
        latest_walk_paused = latest_walk is not None and (
            connection.execute(
                select(capability_run.c.status)
                .where(capability_run.c.project_id == project_id)
                .where(capability_run.c.capability_run_id == latest_walk)
            ).scalar_one_or_none()
            == "paused"
        )
    def decided(pause: dict[str, Any]) -> bool:
        """Whether the pause has its later decision in the same capability walk."""
        payload = pause["payload"]
        return any(
            event["event_type"] == "steering.decision"
            and event["sequence"] > pause["sequence"]
            and isinstance(event["payload"], dict)
            and event["payload"].get("capability_run_id") == payload.get("capability_run_id")
            for event in all_events
        )

    def _page(items: list[CheckInOut], total: int) -> Page[CheckInOut]:
        return Page(
            data=items,
            pagination=PageMeta(page=page, page_size=page_size, total_items=total),
        )

    if status_filter == "pending":
        if not latest_walk_paused:
            return _page([], 0)
        candidates = [
            pause
            for pause in pauses
            if pause["payload"].get("capability_run_id") == str(latest_walk)
            and not decided(pause)
        ]
        if not candidates:
            return _page([], 0)
        return _page([_check_in(candidates[-1], decided=False)], 1)
    window = pauses[(page - 1) * page_size : page * page_size]
    return _page(
        [_check_in(pause, decided=decided(pause)) for pause in window],
        len(pauses),
    )


def _execute_claimed(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    capability_run_id: uuid.UUID,
    backends: RunnerBackends,
    orchestrator: OrchestratorBackend,
) -> None:
    """Execute one already-claimed continuation on the walk executor."""
    try:
        continuation.execute_continuation(
            engine,
            project_id=project_id,
            capability_run_id=capability_run_id,
            backends=backends,
            io=ParkIO(),
            orchestrator=orchestrator,
        )
    except Exception:
        log.exception(
            "api.continuation_dispatch_failed",
            project_id=str(project_id),
            capability_run_id=str(capability_run_id),
        )
        # Without this the walk stays `running` forever with no thread attached
        # (review finding I1/codex-7, 2026-07-21): the user sees a permanently
        # running run and every new dispatch 409s until the next restart's sweep.
        continuation.mark_interrupted_best_effort(
            engine, project_id=project_id, capability_run_id=capability_run_id
        )


@router.post("/{project_id}/check-ins/{check_in_id}/response", response_model=FreeTextCompileOut)
def respond_to_check_in(
    project_id: uuid.UUID,
    check_in_id: uuid.UUID,
    response: CheckInResponse,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    executor: Annotated[ThreadPoolExecutor, Depends(get_executor)],
    backends: Annotated[RunnerBackends, Depends(get_runner_backends)],
    orchestrator: Annotated[OrchestratorBackend, Depends(get_orchestrator_backend)],
) -> FreeTextCompileOut | Response:
    """Compile or durably answer one check-in, dispatching continuations after commit."""
    with engine.connect() as conn:
        owned_project(conn, project_id=project_id, user_id=user.user_id)
    try:
        if response.kind == "free_text":
            compiled = continuation.compile_free_text(
                engine,
                orchestrator,
                project_id=project_id,
                check_in_id=check_in_id,
                text=response.text,
            )
            body = FreeTextCompileOut(render=compiled.render, confirm_token=compiled.confirm_token)
            return JSONResponse(status_code=202, content=jsonable_encoder(body.model_dump()))
        if response.kind == "free_text_confirm":
            result = continuation.confirm_free_text(
                engine,
                project_id=project_id,
                check_in_id=check_in_id,
                confirm_token=response.confirm_token,
                apply=response.apply,
                actor=user.user_id,
            )
            if result is None:
                return Response(status_code=204)
        else:
            result = continuation.answer_check_in(
                engine,
                project_id=project_id,
                check_in_id=check_in_id,
                response=response,
                actor=user.user_id,
            )
    except continuation.AlreadyAnsweredError as exc:
        raise ApiConflict("already_answered", str(exc)) from None
    except continuation.ConfirmTokenExpiredError as exc:
        # 409, not an opaque 404: the recovery action (recompile) must reach the
        # user (review finding m3, 2026-07-21).
        raise ApiConflict("confirm_expired", str(exc)) from None
    except continuation.InvalidResponseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except LookupError:
        raise HTTPException(status_code=404, detail="resource not found") from None

    if result.continuation_requested:
        claim = continuation.claim_continuation(
            engine,
            project_id=project_id,
            capability_run_id=result.capability_run_id,
        )
        if claim is not None:
            executor.submit(
                _execute_claimed,
                engine,
                project_id=claim.project_id,
                capability_run_id=claim.capability_run_id,
                backends=backends,
                orchestrator=orchestrator,
            )
    return Response(status_code=204)
