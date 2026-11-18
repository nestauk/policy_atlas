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
    ProblemReportIn,
)
from policy_atlas.api.deps import get_current_user, get_engine, get_langfuse_client, get_settings
from policy_atlas.api.identity import provision_user
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
}
#: The Langfuse score values of a citation flag (the brief, element A).
CITATION_FLAG_SCORE = {"useful": 1.0, "not_relevant": -1.0}
#: A submit that loses a race on the toggle index is tried once more.
SUBMIT_ATTEMPTS = 2


class _Prepared(NamedTuple):
    """What one kind adds to the envelope, and what its Langfuse score holds.

    Attributes:
        target_type: The type of artefact that the feedback is about.
        target_id: The id of that artefact, or ``None``.
        payload: The kind-specific fields to store.
        capability_run_id: The user-facing run, or ``None``.
        component: The pipeline step whose trace the record joins to, or
            ``None`` for the newest component run.
        score_value: The value of the mirrored score.
        score_comment: Free text from the user for the score comment, if any.
        score_metadata: Fields for filters in Langfuse. No free text.
    """

    target_type: str
    target_id: str | None
    payload: dict[str, Any]
    capability_run_id: uuid.UUID | None
    component: str | None
    score_value: float | str
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


#: One prepare function per kind. Each checks access and builds the record.
_PREPARE: dict[str, Callable[[Connection, Any, str], _Prepared]] = {
    "citation_flag": _citation_flag,
    "problem_report": _problem_report,
}


def _feedback_out(row: Any) -> FeedbackOut:
    """Build the outbound model from a ``feedback_event`` row mapping."""
    return FeedbackOut.model_validate({key: row[key] for key in FeedbackOut.model_fields})


@router.post("", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    body: FeedbackIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    engine: Annotated[Engine, Depends(get_engine)],
    settings: Annotated[Settings, Depends(get_settings)],
    langfuse: Annotated[Langfuse | None, Depends(get_langfuse_client)],
) -> FeedbackOut:
    """Store one feedback record, then mirror it as a Langfuse score.

    For a toggle kind, a second submit for the same target replaces the first:
    the earlier record is retracted and its score is deleted.

    Args:
        body: The validated record of one kind.
        user: The authenticated caller.
        engine: The process engine. The route owns its transaction, so that
            the mirror runs after the commit.
        settings: The application settings (feature flags, version).
        langfuse: The Langfuse client, or ``None`` when tracing is off.

    Returns:
        The stored record.

    Raises:
        HTTPException: 404 when the element is off, or when the task, the
            report or the document is absent or not readable by the caller.
    """
    _require_element(settings, ELEMENT_OF_KIND[body.kind])
    for attempt in range(SUBMIT_ATTEMPTS):
        try:
            with engine.begin() as conn:
                provision_user(conn, user.user_id)
                prepared = _PREPARE[body.kind](conn, body, user.user_id)
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
                row = conn.execute(
                    select(feedback_event).where(
                        feedback_event.c.feedback_event_id == recorded.feedback_event_id
                    )
                ).mappings().one()
            break
        except IntegrityError:
            # Two submits for one toggle at the same time: the index refused
            # the second. The retry finds the first one's row and replaces it.
            if attempt == SUBMIT_ATTEMPTS - 1:
                raise

    if recorded.replaced_id is not None:
        tracing.delete_feedback_score(langfuse, recorded.replaced_id)
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
    return _feedback_out(row)


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
            select(feedback_event)
            .join(
                capability_run,
                capability_run.c.capability_run_id == feedback_event.c.capability_run_id,
            )
            .where(
                capability_run.c.task_id == task_id,
                feedback_event.c.user_id == user.user_id,
                feedback_event.c.kind == kind,
                feedback_event.c.retracted_at.is_(None),
            )
            .order_by(feedback_event.c.created_at.desc())
        ).mappings().all()
    return FeedbackListOut(data=[_feedback_out(row) for row in rows])


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
