"""Persistence helpers for planning-conversation lineage."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import cast

import structlog
from sqlalchemy import select, update
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import conversation
from policy_atlas.runtime.orchestration_plan import OrchestrationPlan
from policy_atlas.runtime.planner_prompt import PlanDraftWire

log = structlog.get_logger()


def seed_draft_from_executed_plan(plan: OrchestrationPlan) -> PlanDraftWire:
    """Map an executed plan into the first draft of its successor lineage.

    Args:
        plan: Validated approved plan stored for the completed lineage.

    Returns:
        The equivalent planner draft, without execution-only fields.
    """
    values = plan.model_dump(
        mode="json",
        exclude={"expected_artefact_shape", "time_band", "source_turn_index"},
    )
    constraints = values.pop("scope_constraints", None) or {}
    values.update({key: value for key, value in constraints.items() if value is not None})
    return PlanDraftWire.model_validate(values)


def ensure_active_planning_conversation(
    conn: Connection, *, project_id: uuid.UUID, now: datetime
) -> uuid.UUID:
    """Return or create the project's active planning conversation.

    The caller owns the project's phase-one row lock, which serializes first
    conversation creation. The partial unique index remains the database
    backstop for this invariant.

    Args:
        conn: Open transaction holding the project row lock.
        project_id: Project whose planning lineage is being advanced.
        now: Creation timestamp for a new conversation.

    Returns:
        The active planning conversation id.
    """
    active_id = conn.execute(
        select(conversation.c.id)
        .where(conversation.c.project_id == project_id)
        .where(conversation.c.kind == "planning")
        .where(conversation.c.status == "active")
    ).scalar_one_or_none()
    if active_id is not None:
        return cast(uuid.UUID, active_id)

    conversation_id = uuid.uuid4()
    conn.execute(
        conversation.insert().values(
            id=conversation_id,
            project_id=project_id,
            kind="planning",
            title="Planning",
            status="active",
            created_at=now,
            closed_at=None,
            archived_at=None,
        )
    )
    log.info("planning_conversation.created", project_id=str(project_id))
    return conversation_id


def close_planning_conversation(
    conn: Connection, *, project_id: uuid.UUID, closed_at: datetime
) -> None:
    """Close the project's active planning conversation, if one exists.

    Args:
        conn: Open transaction that owns the terminal-run write.
        project_id: Project whose current planning lineage is closing.
        closed_at: Terminal-run timestamp to persist as the closure time.
    """
    result = conn.execute(
        update(conversation)
        .where(conversation.c.project_id == project_id)
        .where(conversation.c.kind == "planning")
        .where(conversation.c.status == "active")
        .values(status="closed", closed_at=closed_at)
    )
    if result.rowcount:
        log.info("planning_conversation.closed", project_id=str(project_id))
