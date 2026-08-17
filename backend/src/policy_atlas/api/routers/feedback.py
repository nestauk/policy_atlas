"""Owner-scoped user-feedback write routes.

Human-authored feedback only: no LLM is invoked on either path, and neither
write changes what the pipeline selects, reads or cites.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract import (
    IssueReportCreate,
    IssueReportOut,
    SourceFeedbackOut,
    SourceFeedbackUpdate,
)
from policy_atlas.api.deps import get_conn, get_current_user
from policy_atlas.api.routers._common import owned_project
from policy_atlas.core.schema import project_source_snapshot, user_feedback

router = APIRouter(
    prefix="/api/v1/projects",
    tags=["feedback"],
    dependencies=[Depends(get_current_user)],
)


@router.patch("/{project_id}/sources/{source_id}", response_model=SourceFeedbackOut)
def set_source_feedback(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    payload: SourceFeedbackUpdate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> SourceFeedbackOut:
    """Set or clear the caller's not-relevant flag on one source.

    Idempotent in both directions: setting an already-set flag leaves the one
    row alone (the partial unique index makes that a database guarantee), and
    clearing an absent flag is a no-op.
    """
    owned_project(conn, project_id=project_id, user_id=user.user_id)
    # The source must belong to this project — otherwise a caller could flag a
    # source they cannot see, and the pair-FK would accept it as a bare id.
    belongs = conn.execute(
        select(project_source_snapshot.c.project_source_snapshot_id).where(
            project_source_snapshot.c.project_id == project_id,
            project_source_snapshot.c.project_source_snapshot_id == source_id,
        )
    ).scalar_one_or_none()
    if belongs is None:
        raise HTTPException(status_code=404, detail="resource not found")
    if payload.not_relevant:
        conn.execute(
            pg_insert(user_feedback)
            .values(
                user_feedback_id=uuid.uuid4(),
                project_id=project_id,
                kind="source_not_relevant",
                user_id=user.user_id,
                project_source_snapshot_id=source_id,
                body=None,
                page_path=None,
                created_at=datetime.now(UTC),
            )
            # Targets ux_ufb_source_flag — index_where must match the partial
            # index's predicate for Postgres to infer it.
            .on_conflict_do_nothing(
                index_elements=["project_source_snapshot_id", "user_id"],
                index_where=user_feedback.c.kind == "source_not_relevant",
            )
        )
    else:
        conn.execute(
            delete(user_feedback).where(
                user_feedback.c.project_id == project_id,
                user_feedback.c.kind == "source_not_relevant",
                user_feedback.c.project_source_snapshot_id == source_id,
                user_feedback.c.user_id == user.user_id,
            )
        )
    return SourceFeedbackOut(source_id=source_id, not_relevant=payload.not_relevant)


@router.post(
    "/{project_id}/issue-reports",
    response_model=IssueReportOut,
    status_code=status.HTTP_201_CREATED,
)
def create_issue_report(
    project_id: uuid.UUID,
    payload: IssueReportCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> IssueReportOut:
    """Record one free-text issue report against the project."""
    owned_project(conn, project_id=project_id, user_id=user.user_id)
    feedback_id = uuid.uuid4()
    created_at = datetime.now(UTC)
    conn.execute(
        user_feedback.insert().values(
            user_feedback_id=feedback_id,
            project_id=project_id,
            kind="issue_report",
            user_id=user.user_id,
            project_source_snapshot_id=None,
            body=payload.body,
            page_path=payload.page_path,
            created_at=created_at,
        )
    )
    return IssueReportOut(feedback_id=feedback_id, created_at=created_at)
