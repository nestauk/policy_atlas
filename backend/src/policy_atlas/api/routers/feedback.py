"""In-app feedback routes: submit a record, list the caller's records, retract one.

One ``POST`` takes every feedback kind. Each kind is behind the feature flag of
its element: with the flag off the request is a 404, so the API surface is the
same as before the element.

Order of work for a submit. The Postgres row commits first, because Postgres
is the system of record. The Langfuse score is written after the commit. A
failure of the mirror is logged and does not fail the request.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from contextlib import suppress
from typing import Annotated, Any, NamedTuple

from fastapi import APIRouter, Depends, HTTPException, Response, status
from langfuse import Langfuse
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract.feedback import (
    CitationFlagIn,
    FeedbackIn,
    FeedbackKind,
    FeedbackListOut,
    FeedbackOut,
    MissingPaperIn,
    MissingPaperResolutionOut,
    ProblemReportIn,
    ScreeningOverrideIn,
)
from policy_atlas.api.deps import (
    get_current_user,
    get_engine,
    get_langfuse_client,
    get_paper_lookup,
    get_settings,
)
from policy_atlas.api.identity import provision_user
from policy_atlas.api.missing_paper import PaperLookup, resolve_and_store
from policy_atlas.api.read_models.repository import _effective_screens
from policy_atlas.api.routers.access import NOT_FOUND_DETAIL, accessible_task
from policy_atlas.api.settings import Settings
from policy_atlas.core import tracing
from policy_atlas.core.feedback import (
    record_feedback,
    retract_feedback,
    route_problem_report,
)
from policy_atlas.core.schema import (
    artefact,
    capability_run,
    feedback_event,
    missing_paper_resolution,
    source_snapshot,
    task_source_snapshot,
)

router = APIRouter(
    prefix="/api/v1/feedback",
    tags=["feedback"],
    dependencies=[Depends(get_current_user)],
)

#: The feature flag (``settings.FEEDBACK_ELEMENTS``) that each kind is behind.
ELEMENT_OF_KIND: dict[str, str] = {
    "citation_flag": "citation_flag",
    "problem_report": "problem_report",
    "missing_paper": "missing_paper",
    "screening_override": "missing_paper",
}
#: The Langfuse score values of a citation flag (the brief, element A).
CITATION_FLAG_SCORE = {"useful": 1.0, "not_relevant": -1.0}
#: A submit that loses a race on the toggle index is tried once more.
SUBMIT_ATTEMPTS = 2
#: The pipeline step that removes documents at each screening stage.
SCREEN_COMPONENT = {1: "screen_abstract", 2: "screen_full"}
#: The Langfuse score value of a screening override.
SCREENING_OVERRIDE_SCORE = 1.0
#: How long a missing-paper submit waits for its resolution, in seconds (the
#: brief: "synchronous if <1.5s, else async with a pending state").
RESOLVE_BUDGET_S = 1.5
#: Worker threads that resolve missing papers. Each one holds an OpenAlex
#: call, so a small pool is enough.
MISSING_PAPER_WORKERS = 2
_RESOLVER_POOL = ThreadPoolExecutor(
    max_workers=MISSING_PAPER_WORKERS, thread_name_prefix="missing-paper"
)


class _Prepared(NamedTuple):
    """What one kind adds to the envelope, and what its Langfuse score holds.

    Attributes:
        target_type: The type of artefact that the feedback is about.
        target_id: The id of that artefact, or ``None``.
        payload: The kind-specific fields to store.
        capability_run_id: The user-facing run, or ``None``.
        component: The pipeline step whose trace the record joins to, or
            ``None`` for the newest component run.
        score_value: The value of the mirrored score, or ``None`` when the
            score is written later (a missing paper, after its resolution).
        score_comment: Free text from the user for the score comment, if any.
        score_metadata: Fields for filters in Langfuse. No free text.
    """

    target_type: str
    target_id: str | None
    payload: dict[str, Any]
    capability_run_id: uuid.UUID | None
    component: str | None
    score_value: float | str | None
    score_comment: str | None
    score_metadata: dict[str, Any]


def _not_found() -> HTTPException:
    """Return the generic 404 that an unreadable or absent resource gets."""
    return HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)


def _require_element(settings: Settings, element: str) -> None:
    """Raise a 404 when a feedback element is off.

    Args:
        settings: The application settings.
        element: A name from ``settings.FEEDBACK_ELEMENTS``.

    Raises:
        HTTPException: 404 when the element's flag is off.
    """
    if element not in settings.feedback_elements:
        raise _not_found()


def _latest_run_id(conn: Connection, task_id: uuid.UUID) -> uuid.UUID | None:
    """Return the newest user-facing run of a task, or ``None`` when it has none."""
    return conn.execute(
        select(capability_run.c.capability_run_id)
        .where(capability_run.c.task_id == task_id)
        .order_by(capability_run.c.started_at.desc(), capability_run.c.capability_run_id.desc())
        .limit(1)
    ).scalar_one_or_none()


def _run_of_report(
    conn: Connection, task_id: uuid.UUID, artefact_id: uuid.UUID | None
) -> uuid.UUID | None:
    """Find the run that feedback on a task's report or sources belongs to.

    Args:
        conn: Open database connection.
        task_id: The task, which the caller can read.
        artefact_id: The report that the feedback was given on, or ``None``.

    Returns:
        The run that wrote the report. With no report, the task's newest run.

    Raises:
        HTTPException: 404 when the report is not a report of this task.
    """
    if artefact_id is None:
        return _latest_run_id(conn, task_id)
    row = conn.execute(
        select(artefact.c.capability_run_id).where(
            artefact.c.artefact_id == artefact_id, artefact.c.task_id == task_id
        )
    ).first()
    if row is None:
        raise _not_found()
    run_id: uuid.UUID | None = row.capability_run_id
    return run_id


def _document_identity(
    conn: Connection, task_id: uuid.UUID, source_id: uuid.UUID
) -> dict[str, Any]:
    """Read the external identity of one document of a task.

    The document id in a feedback record is ``task_source_snapshot_id``, which
    is internal and scoped to one task. The provider's own id and the DOI are
    copied into the payload, so that records for one paper join across tasks.

    Args:
        conn: Open database connection.
        task_id: The task.
        source_id: The document's ``task_source_snapshot_id``.

    Returns:
        ``backend`` (``openalex`` or ``overton``), ``backend_record_id`` and
        ``doi``, each only when the document has it.

    Raises:
        HTTPException: 404 when the document is not a document of this task.
    """
    row = conn.execute(
        select(source_snapshot.c.metadata)
        .select_from(
            task_source_snapshot.join(
                source_snapshot,
                source_snapshot.c.source_snapshot_id == task_source_snapshot.c.source_snapshot_id,
            )
        )
        .where(
            task_source_snapshot.c.task_source_snapshot_id == source_id,
            task_source_snapshot.c.task_id == task_id,
        )
    ).first()
    if row is None:
        raise _not_found()
    return {
        key: row.metadata[key]
        for key in ("backend", "backend_record_id", "doi")
        if row.metadata.get(key) is not None
    }


def _citation_flag(conn: Connection, body: CitationFlagIn, user_id: str) -> _Prepared:
    """Prepare a citation flag (element A). The trace is the synthesise step's."""
    accessible_task(conn, task_id=body.task_id, user_id=user_id)
    document = _document_identity(conn, body.task_id, body.source_id)
    choice = body.model_dump(include={"action", "reason"}, exclude_none=True)
    payload = {**choice, "document": document}
    if body.note:
        payload["note"] = body.note
    return _Prepared(
        target_type="document",
        target_id=str(body.source_id),
        payload=payload,
        capability_run_id=_run_of_report(conn, body.task_id, body.artefact_id),
        component="synthesise",
        score_value=CITATION_FLAG_SCORE[body.action],
        score_comment=body.note,
        score_metadata={**choice, "source_id": str(body.source_id), **document},
    )


def _problem_report(conn: Connection, body: ProblemReportIn, user_id: str) -> _Prepared:
    """Prepare a problem report (element E). The trace is the newest component run's."""
    run_id = None
    if body.task_id is not None:
        accessible_task(conn, task_id=body.task_id, user_id=user_id, include_archived=True)
        run_id = _latest_run_id(conn, body.task_id)
    where = body.model_dump(
        include={"problem_kind", "page", "step_reached", "step_status"}, exclude_none=True
    )
    payload = {
        **where,
        "description": body.description,
        "client": body.client.model_dump(mode="json"),
    }
    if body.query_text:
        payload["query_text"] = body.query_text
    return _Prepared(
        target_type="run",
        target_id=str(run_id) if run_id is not None else None,
        payload=payload,
        capability_run_id=run_id,
        component=None,
        score_value=body.problem_kind,
        score_comment=body.description or None,
        score_metadata=where,
    )


def _missing_paper(conn: Connection, body: MissingPaperIn, user_id: str) -> _Prepared:
    """Prepare a missing-paper report (element B). The trace is the synthesise step's.

    The score is not written here: it needs the failure stage, which the
    resolver adds after the record is stored.
    """
    access = accessible_task(conn, task_id=body.task_id, user_id=user_id)
    run_id = _run_of_report(conn, body.task_id, body.artefact_id)
    if run_id is None:
        raise _not_found()
    payload = {"raw_input": body.raw_input.strip(), "query_text": access.row["question"]}
    if body.why:
        payload["why"] = body.why
    return _Prepared(
        target_type="run",
        target_id=str(run_id),
        payload=payload,
        capability_run_id=run_id,
        component="synthesise",
        score_value=None,
        score_comment=None,
        score_metadata={},
    )


def _screening_override(conn: Connection, body: ScreeningOverrideIn, user_id: str) -> _Prepared:
    """Prepare "Should have been kept" (element B). The trace is the screen step's."""
    accessible_task(conn, task_id=body.task_id, user_id=user_id)
    document = _document_identity(conn, body.task_id, body.source_id)
    # ponytail: reads every effective screening row of the task for one
    # document. Filter the helper's query by document if a click is slow.
    screen = _effective_screens(conn, body.task_id).get(body.source_id)
    if screen is None or screen.status == "relevant":
        raise HTTPException(status_code=422, detail="this document was not screened out")
    stage = f"s{screen.screen_stage}"
    return _Prepared(
        target_type="document",
        target_id=str(body.source_id),
        payload={"stage": stage, "document": document},
        capability_run_id=_latest_run_id(conn, body.task_id),
        component=SCREEN_COMPONENT[screen.screen_stage],
        score_value=SCREENING_OVERRIDE_SCORE,
        score_comment=None,
        score_metadata={"stage": stage, "source_id": str(body.source_id), **document},
    )


#: One prepare function per kind. Each checks access and builds the record.
_PREPARE: dict[str, Callable[[Connection, Any, str], _Prepared]] = {
    "citation_flag": _citation_flag,
    "problem_report": _problem_report,
    "missing_paper": _missing_paper,
    "screening_override": _screening_override,
}

#: Feedback records with the resolution of a missing paper beside them.
_FEEDBACK_ROWS = select(
    feedback_event,
    missing_paper_resolution.c.failure_stage,
    missing_paper_resolution.c.resolved_id,
    missing_paper_resolution.c.resolver_confidence,
    missing_paper_resolution.c.resolved_at,
).outerjoin(
    missing_paper_resolution,
    missing_paper_resolution.c.feedback_event_id == feedback_event.c.feedback_event_id,
)


def _feedback_out(row: Any) -> FeedbackOut:
    """Build the outbound model from a row mapping of :data:`_FEEDBACK_ROWS`."""
    resolution = (
        MissingPaperResolutionOut.model_validate(
            {key: row[key] for key in MissingPaperResolutionOut.model_fields}
        )
        if row["kind"] == "missing_paper"
        else None
    )
    record = {key: row[key] for key in FeedbackOut.model_fields if key != "resolution"}
    return FeedbackOut.model_validate({**record, "resolution": resolution})


def _read_feedback(conn: Connection, feedback_event_id: uuid.UUID, user_id: str) -> FeedbackOut:
    """Read one of the caller's records.

    Raises:
        HTTPException: 404 when the caller has no record with this id.
    """
    row = conn.execute(
        _FEEDBACK_ROWS.where(
            feedback_event.c.feedback_event_id == feedback_event_id,
            feedback_event.c.user_id == user_id,
        )
    ).mappings().first()
    if row is None:
        raise _not_found()
    return _feedback_out(row)


def _same_report(conn: Connection, user_id: str, prepared: _Prepared) -> uuid.UUID | None:
    """Find the caller's earlier report of the same missing paper in the same run.

    The same paper reported in another run is a separate record: only a
    repeat within one run is the same report.
    """
    return conn.execute(
        select(feedback_event.c.feedback_event_id)
        .where(
            feedback_event.c.user_id == user_id,
            feedback_event.c.kind == "missing_paper",
            feedback_event.c.capability_run_id == prepared.capability_run_id,
            feedback_event.c.payload["raw_input"].astext == prepared.payload["raw_input"],
            feedback_event.c.retracted_at.is_(None),
        )
        .limit(1)
    ).scalar_one_or_none()


@router.post("", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    body: FeedbackIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
    langfuse: Annotated[Langfuse | None, Depends(get_langfuse_client)],
    lookup: Annotated[PaperLookup | None, Depends(get_paper_lookup)],
) -> FeedbackOut:
    """Store one feedback record, then mirror it as a Langfuse score.

    For a toggle kind, a second submit for the same target replaces the first:
    the earlier record is retracted and its score is deleted.

    A missing-paper report is resolved on a worker thread. The request waits
    for the answer up to :data:`RESOLVE_BUDGET_S`; after that the response has
    a pending resolution, and ``GET /api/v1/feedback/{id}`` has the answer
    when the resolver is done.

    Args:
        body: The validated record of one kind.
        user: The authenticated caller.
        engine: The process engine. The route owns its transaction, so that
            the mirror runs after the commit.
        settings: The application settings (feature flags, version).
        langfuse: The Langfuse client, or ``None`` when tracing is off.
        lookup: The OpenAlex lookups for a missing paper, or ``None``.

    Returns:
        The stored record.

    Raises:
        HTTPException: 404 when the element is off, or when the task, the
            report or the document is absent or not readable by the caller.
            422 for an override of a document that was not screened out.
    """
    _require_element(settings, ELEMENT_OF_KIND[body.kind])
    for attempt in range(SUBMIT_ATTEMPTS):
        try:
            with engine.begin() as conn:
                provision_user(conn, user.user_id)
                prepared = _PREPARE[body.kind](conn, body, user.user_id)
                if isinstance(body, MissingPaperIn):
                    earlier = _same_report(conn, user.user_id, prepared)
                    if earlier is not None:
                        return _read_feedback(conn, earlier, user.user_id)
                recorded = record_feedback(
                    conn,
                    user_id=user.user_id,
                    surface=body.surface,
                    kind=body.kind,
                    target_type=prepared.target_type,
                    target_id=prepared.target_id,
                    payload=prepared.payload,
                    capability_run_id=prepared.capability_run_id,
                    component=prepared.component,
                    pa_version=settings.pa_version,
                )
                if isinstance(body, MissingPaperIn):
                    # The pending state: a resolution row with no stage yet.
                    conn.execute(
                        missing_paper_resolution.insert().values(
                            feedback_event_id=recorded.feedback_event_id
                        )
                    )
            break
        except IntegrityError:
            # Two submits for one toggle at the same time: the index refused
            # the second. The retry finds the first one's row and replaces it.
            if attempt == SUBMIT_ATTEMPTS - 1:
                raise

    if recorded.replaced_id is not None:
        tracing.delete_feedback_score(langfuse, recorded.replaced_id)
    if prepared.score_value is not None:
        tracing.score_feedback(
            langfuse,
            feedback_event_id=recorded.feedback_event_id,
            trace_id=recorded.trace_id,
            name=body.kind,
            value=prepared.score_value,
            comment=prepared.score_comment,
            metadata={"surface": body.surface, **prepared.score_metadata},
        )
    if isinstance(body, ProblemReportIn):
        route_problem_report(
            langfuse,
            feedback_event_id=recorded.feedback_event_id,
            problem_kind=body.problem_kind,
            trace_id=recorded.trace_id,
        )
    if isinstance(body, MissingPaperIn):
        resolving = _RESOLVER_POOL.submit(
            resolve_and_store,
            engine,
            langfuse,
            lookup,
            feedback_event_id=recorded.feedback_event_id,
        )
        # Over the budget, the response says pending and the thread goes on.
        with suppress(FutureTimeout):
            resolving.result(timeout=RESOLVE_BUDGET_S)
    with engine.connect() as conn:
        return _read_feedback(conn, recorded.feedback_event_id, user.user_id)


@router.get("", response_model=FeedbackListOut)
def list_feedback(
    task_id: uuid.UUID,
    kind: FeedbackKind,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FeedbackListOut:
    """List the caller's active records of one kind on one task.

    The frontend reads this to show a flag again after a reload.

    Args:
        task_id: The task.
        kind: The feedback kind.
        user: The authenticated caller.
        engine: The process engine.
        settings: The application settings (feature flags).

    Returns:
        The caller's records that are not retracted, newest first.

    Raises:
        HTTPException: 404 when the kind's element is off, or the task is
            absent or not readable by the caller.
    """
    _require_element(settings, ELEMENT_OF_KIND.get(kind, ""))
    with engine.connect() as conn:
        accessible_task(conn, task_id=task_id, user_id=user.user_id)
        rows = conn.execute(
            _FEEDBACK_ROWS.join(
                capability_run,
                capability_run.c.capability_run_id == feedback_event.c.capability_run_id,
            ).where(
                capability_run.c.task_id == task_id,
                feedback_event.c.user_id == user.user_id,
                feedback_event.c.kind == kind,
                feedback_event.c.retracted_at.is_(None),
            )
            .order_by(feedback_event.c.created_at.desc())
        ).mappings().all()
    return FeedbackListOut(data=[_feedback_out(row) for row in rows])


@router.get("/{feedback_event_id}", response_model=FeedbackOut)
def get_feedback(
    feedback_event_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FeedbackOut:
    """Return one of the caller's records.

    The frontend polls this while a missing paper's resolution is pending.

    Args:
        feedback_event_id: The record.
        user: The authenticated caller.
        engine: The process engine.
        settings: The application settings (feature flags).

    Returns:
        The record, with its resolution for a missing paper.

    Raises:
        HTTPException: 404 when no feedback kind is on, or when the caller has
            no record with this id.
    """
    if not settings.feedback_elements & set(ELEMENT_OF_KIND.values()):
        raise _not_found()
    with engine.connect() as conn:
        return _read_feedback(conn, feedback_event_id, user.user_id)


@router.delete("/{feedback_event_id}", status_code=status.HTTP_204_NO_CONTENT)
def retract(
    feedback_event_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
    langfuse: Annotated[Langfuse | None, Depends(get_langfuse_client)],
) -> Response:
    """Retract one of the caller's records. The row is kept; its score is deleted.

    Args:
        feedback_event_id: The record.
        user: The authenticated caller.
        engine: The process engine.
        settings: The application settings (feature flags).
        langfuse: The Langfuse client, or ``None`` when tracing is off.

    Returns:
        An empty 204 response.

    Raises:
        HTTPException: 404 when no feedback kind is on, or when the caller has
            no active record with this id.
    """
    if not settings.feedback_elements & set(ELEMENT_OF_KIND.values()):
        raise _not_found()
    with engine.begin() as conn:
        retracted = retract_feedback(
            conn, feedback_event_id=feedback_event_id, user_id=user.user_id
        )
    if not retracted:
        raise _not_found()
    tracing.delete_feedback_score(langfuse, feedback_event_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
