"""The longlist routes (task 045, S12; contract deliverable 11).

The reads, public-readable like the artefact (ADR 0033 / 0035: the graded
read or the narrow public leg, through ``_readable``), and the buttons — the
longlist's three and the shortlist's three (task 055, P9) — owner-only
(``accessible_task(write=True)``), each calling the apply function
the Task Agent's longlist verbs share (:mod:`policy_atlas.api.longlist_actions`).
A link grants no read of options: every read is keyed to the requested task
alone.
"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract import (
    LatestRun,
    LonglistOut,
    OptionAddedOut,
    OptionAddIn,
    OptionExcludeIn,
    OptionIncludeIn,
    OptionOut,
    OptionsOut,
    ShortlistOut,
)
from policy_atlas.api.deps import (
    get_agent_backend,
    get_conn,
    get_current_user,
    get_engine,
    get_executor,
    get_optional_user,
    get_runner_backends,
)
from policy_atlas.api.longlist_actions import (
    OptionNotFound,
    add_option,
    admit_longlist_action,
    current_plan_row,
    exclude_option,
    include_option,
    propose_design,
    shortlist_option,
    unshortlist_option,
)
from policy_atlas.api.longlist_start import (
    LonglistRefused,
    http_error,
    open_shortlist_walk,
    opened_run,
)
from policy_atlas.api.read_models import repository
from policy_atlas.api.routers.access import NOT_FOUND_DETAIL, accessible_task
from policy_atlas.api.routers.read_models import _readable
from policy_atlas.core import events, tracing
from policy_atlas.options_scoping.scoping_backend import StubLonglistBackend
from policy_atlas.options_scoping.shortlist.shortlist_note import (
    current_places,
    note_stale,
    write_shortlist_note,
)
from policy_atlas.options_scoping.shortlist.shortlist_note_prompt import (
    SHORTLIST_NOTE_PROMPT_VERSION,
)
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


@router.get("/{task_id}/options", response_model=OptionsOut)
def get_options(
    task_id: uuid.UUID,
    user: Annotated[AuthenticatedUser | None, Depends(get_optional_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> OptionsOut:
    """Return the task's option rows with each option's search (task 058, N22).

    Readable from the end of the suggest stage, before the longlist exists,
    under the same graded-or-public check as the longlist read. Empty before
    any option exists; never a 404 for a readable task.
    """
    _readable(conn, task_id, user)
    return repository.options_out(conn, task_id)


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
        except LonglistRefused as exc:
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
    except LonglistRefused as exc:
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
        except LonglistRefused as exc:
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
        except LonglistRefused as exc:
            raise http_error(exc) from None
        except OptionNotFound:
            raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL) from None
    return _card(engine, task_id, option_id)


@router.post("/{task_id}/options/{option_id}/shortlist", response_model=OptionOut)
def post_shortlist(
    task_id: uuid.UUID,
    option_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
) -> OptionOut:
    """Put an included option on the shortlist as the user's own place (task 055).

    Repeating it on a place the user already holds is a no-op. Refused with
    409 ``not_included`` for an excluded or merged option and 409
    ``run_active`` while a walk runs.
    """
    with engine.begin() as conn:
        accessible_task(conn, task_id=task_id, user_id=user.user_id, write=True, for_update=True)
        try:
            shortlist_option(conn, task_id=task_id, option_id=option_id, actor=user.user_id)
        except LonglistRefused as exc:
            raise http_error(exc) from None
        except OptionNotFound:
            raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL) from None
    return _card(engine, task_id, option_id)


@router.post("/{task_id}/options/{option_id}/unshortlist", response_model=OptionOut)
def post_unshortlist(
    task_id: uuid.UUID,
    option_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
) -> OptionOut:
    """Take an option off the shortlist (task 055).

    A Policy Atlas pick becomes set aside; the user's own place clears. No
    walk opens and nothing refills the place. An option with no place is a
    no-op. Refused with 409 ``run_active`` while a walk runs.
    """
    with engine.begin() as conn:
        accessible_task(conn, task_id=task_id, user_id=user.user_id, write=True, for_update=True)
        try:
            unshortlist_option(conn, task_id=task_id, option_id=option_id, actor=user.user_id)
        except LonglistRefused as exc:
            raise http_error(exc) from None
        except OptionNotFound:
            raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL) from None
    return _card(engine, task_id, option_id)


@router.post(
    "/{task_id}/shortlist/suggest",
    response_model=LatestRun,
    status_code=status.HTTP_202_ACCEPTED,
)
def post_suggest_more(
    task_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    executor: Annotated[ThreadPoolExecutor, Depends(get_executor)],
    backends: Annotated[RunnerBackends, Depends(get_runner_backends)],
) -> LatestRun:
    """Open a shortlist walk that fills the open places (Suggest more; task 055).

    The access check runs in its own short transaction, then the opener takes
    the dispatch lock and the task row itself (the order ``create_run``
    uses). Refused with 409 ``run_active``, ``capacity``, ``plan_stale`` or
    ``nothing_to_propose``, and 404 when the task has no longlist.
    """
    with engine.begin() as conn:
        accessible_task(conn, task_id=task_id, user_id=user.user_id, write=True)
    try:
        run_id = open_shortlist_walk(
            engine,
            task_id=task_id,
            backends=backends,
            executor=executor,
            user_id=user.user_id,
            suggest=True,
        )
    except LonglistRefused as exc:
        raise http_error(exc) from None
    return opened_run(engine, task_id=task_id, capability_run_id=run_id)


@router.post("/{task_id}/shortlist/note", response_model=ShortlistOut)
def post_shortlist_note(
    task_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    backends: Annotated[RunnerBackends, Depends(get_runner_backends)],
) -> ShortlistOut:
    """Rewrite the shortlist's not-covered note for the places as they stand (round 14).

    Owner only. Only when the note is stale (written against other places,
    or missing beside a proposal); otherwise the shortlist comes back as it
    is. The note's one writer (:func:`write_shortlist_note`) runs with no
    changes: it reads the plan's outcomes, the option list and the places,
    never a document line. History says "Policy Atlas updated the shortlist
    note".

    Raises:
        HTTPException: 404 with no longlist, 409 while a walk runs, 503 when
            the call fails (nothing is written).
    """
    with engine.begin() as conn:
        accessible_task(conn, task_id=task_id, user_id=user.user_id, write=True, for_update=True)
        try:
            admit_longlist_action(conn, task_id=task_id)
        except LonglistRefused as exc:
            raise http_error(exc) from None
        result = repository._latest_longlist_row(conn, task_id)
        if result is None:
            raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)
        plan = repository._scoping_plan_version(conn, task_id, None)
        current_plan = plan[1] if plan is not None else None
        stored = dict(result.shortlist) if isinstance(result.shortlist, dict) else {}
        places = current_places(conn, task_id)
        if not note_stale(stored, places):
            return repository._shortlist_out(stored, current_plan, places)
        # As the harness does: the stub when the bundle names none.
        writer = backends.longlist if backends.longlist is not None else StubLonglistBackend()
        try:
            with tracing.trace_scope(user_id=user.user_id):
                note = write_shortlist_note(
                    conn,
                    task_id,
                    writer,
                    outcomes=repository._plan_outcomes(current_plan),
                )
        except Exception as exc:
            log.warning("shortlist.note_failed", task_id=str(task_id), error=type(exc).__name__)
            raise HTTPException(status_code=503, detail=_NOTE_UNAVAILABLE) from None
        events.append(
            conn,
            task_id=task_id,
            run_id=None,
            event_type=repository.SHORTLIST_NOTE_UPDATED,
            payload={
                "actor": "agent",
                "note": note,
                "places": [str(place) for place in places],
                "prompt_version": SHORTLIST_NOTE_PROMPT_VERSION,
            },
        )
        refreshed = repository._latest_longlist_row(conn, task_id)
        shortlist = (
            dict(refreshed.shortlist)
            if refreshed is not None and isinstance(refreshed.shortlist, dict)
            else {}
        )
        return repository._shortlist_out(shortlist, current_plan, places)


_NOTE_UNAVAILABLE = "The note could not be updated. Try again."
