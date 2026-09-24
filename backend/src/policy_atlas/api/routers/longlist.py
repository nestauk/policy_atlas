"""The longlist routes (task 045, S12; contract deliverable 11).

Two reads, public-readable like the artefact (ADR 0033 / 0035: the graded
read or the narrow public leg, through ``_readable``), and the three buttons,
owner-only (``accessible_task(write=True)``), each calling the apply function
the Task Agent's longlist verbs share (:mod:`policy_atlas.api.longlist_actions`).
A link grants no read of options: every read is keyed to the requested task
alone.
"""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract import (
    LonglistOut,
    OptionAddedOut,
    OptionAddIn,
    OptionExcludeIn,
    OptionIncludeIn,
    OptionOut,
)
from policy_atlas.api.deps import (
    get_agent_backend,
    get_conn,
    get_current_user,
    get_engine,
    get_optional_user,
    get_runner_backends,
)
from policy_atlas.api.longlist_actions import (
    LonglistActionRefused,
    OptionNotFound,
    add_option,
    admit_longlist_action,
    current_plan_row,
    exclude_option,
    http_error,
    include_option,
    propose_design,
)
from policy_atlas.api.longlist_start import opened_run
from policy_atlas.api.readmodels import repository
from policy_atlas.api.routers._access import NOT_FOUND_DETAIL, accessible_task
from policy_atlas.api.routers.read_models import _readable
from policy_atlas.core import tracing
from policy_atlas.runtime.agent_backend import AgentBackend
from policy_atlas.runtime.runner import RunnerBackends

log = structlog.get_logger()

router = APIRouter(prefix="/api/v1/tasks", tags=["longlist"])

_DESIGN_UNAVAILABLE = "Policy Atlas could not read a design from those words; try again"


def _card(engine: Engine, task_id: uuid.UUID, option_id: uuid.UUID) -> OptionOut:
    with engine.connect() as conn:
        card = repository.option_out(conn, task_id, option_id)
    if card is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)
    return card


@router.get("/{task_id}/longlist", response_model=LonglistOut)
def get_longlist(
    task_id: uuid.UUID,
    user: Annotated[AuthenticatedUser | None, Depends(get_optional_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> LonglistOut:
    """Return the task's longlist, or 404 before the first build."""
    _readable(conn, task_id, user)
    result = repository.longlist_out(conn, task_id)
    if result is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)
    return result


@router.get("/{task_id}/options/{option_id}", response_model=OptionOut)
def get_option(
    task_id: uuid.UUID,
    option_id: uuid.UUID,
    user: Annotated[AuthenticatedUser | None, Depends(get_optional_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> OptionOut:
    """Return one option's card, or an indistinguishable 404."""
    _readable(conn, task_id, user)
    result = repository.option_out(conn, task_id, option_id)
    if result is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)
    return result


@router.post(
    "/{task_id}/options", response_model=OptionAddedOut, status_code=status.HTTP_201_CREATED
)
def post_option(
    task_id: uuid.UUID,
    payload: OptionAddIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    agent: Annotated[AgentBackend, Depends(get_agent_backend)],
    backends: Annotated[RunnerBackends, Depends(get_runner_backends)],
) -> OptionAddedOut:
    """Add an option by hand: propose its design, mint it, open its option search.

    The design is proposed back from the user's words (``option_design_v1``)
    outside any transaction; the option is minted *added by you* and its
    option search opened as a walk with no parent (:func:`add_option`). The
    fence is read twice: before the model call, so a refused add costs no
    call, and again under the lock.
    """
    words = " ".join(payload.text.split())
    if not words:
        raise HTTPException(status_code=422, detail="an option needs words")
    with engine.begin() as conn:
        accessible_task(conn, task_id=task_id, user_id=user.user_id, write=True, for_update=True)
        try:
            admit_longlist_action(conn, task_id=task_id)
            plan_row = current_plan_row(conn, task_id=task_id)
        except LonglistActionRefused as exc:
            raise http_error(exc) from None
    try:
        with tracing.trace_scope(user_id=user.user_id):
            design = propose_design(
                agent, plan_payload=plan_row["payload"], words=words, session_id=task_id
            )
    except (RuntimeError, ValueError) as exc:
        log.warning("option.design_failed", error_type=type(exc).__name__)
        raise HTTPException(status_code=503, detail=_DESIGN_UNAVAILABLE) from None
    try:
        added = add_option(
            engine,
            task_id=task_id,
            words=words,
            design=design,
            backends=backends,
            user_id=user.user_id,
        )
    except LonglistActionRefused as exc:
        raise http_error(exc) from None
    return OptionAddedOut(
        option=_card(engine, task_id, added.option_id),
        # ``None`` while the search is still queued (A4): the card reads it
        # as search pending, and the run stream announces the walk.
        opened_run=(
            opened_run(engine, task_id=task_id, capability_run_id=added.capability_run_id)
            if added.run_open
            else None
        ),
    )


@router.post("/{task_id}/options/{option_id}/exclude", response_model=OptionOut)
def post_exclude(
    task_id: uuid.UUID,
    option_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    payload: Annotated[OptionExcludeIn | None, Body()] = None,
) -> OptionOut:
    """Exclude an option, with the user's reason when given; include again reverses it."""
    with engine.begin() as conn:
        accessible_task(conn, task_id=task_id, user_id=user.user_id, write=True, for_update=True)
        try:
            exclude_option(
                conn,
                task_id=task_id,
                option_id=option_id,
                reason=payload.reason if payload is not None else None,
                actor=user.user_id,
            )
        except LonglistActionRefused as exc:
            raise http_error(exc) from None
        except OptionNotFound:
            raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL) from None
    return _card(engine, task_id, option_id)


@router.post("/{task_id}/options/{option_id}/include", response_model=OptionOut)
def post_include(
    task_id: uuid.UUID,
    option_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    payload: Annotated[OptionIncludeIn | None, Body()] = None,
) -> OptionOut:
    """Include an option again; a rebuild's constrain will not exclude it."""
    with engine.begin() as conn:
        accessible_task(conn, task_id=task_id, user_id=user.user_id, write=True, for_update=True)
        try:
            include_option(
                conn,
                task_id=task_id,
                option_id=option_id,
                actor=user.user_id,
                reason=payload.reason if payload is not None else None,
            )
        except LonglistActionRefused as exc:
            raise http_error(exc) from None
        except OptionNotFound:
            raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL) from None
    return _card(engine, task_id, option_id)
