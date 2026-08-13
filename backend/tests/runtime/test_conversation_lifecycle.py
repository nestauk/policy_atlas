"""Database coverage for planning-conversation lifecycle helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.core.schema import conversation, project
from policy_atlas.runtime.conversation_lifecycle import (
    close_planning_conversation,
    ensure_active_planning_conversation,
)


def _seed_project(conn: Connection) -> uuid.UUID:
    """Insert the minimum project row required by lifecycle tests."""
    project_id = uuid.uuid4()
    now = datetime.now(UTC)
    conn.execute(
        project.insert().values(
            project_id=project_id,
            created_at=now,
            name="Conversation lifecycle test",
            question="What works?",
            status="active",
            updated_at=now,
            archived_at=None,
            owner_user_id="test-owner",
        )
    )
    return project_id


def test_ensure_reuses_active_conversation_and_close_is_idempotent(conn: Connection) -> None:
    """Active planning conversations are reused, closed, then cleanly succeeded."""
    project_id = _seed_project(conn)
    created_at = datetime.now(UTC)

    first_id = ensure_active_planning_conversation(
        conn, project_id=project_id, now=created_at
    )
    assert ensure_active_planning_conversation(
        conn, project_id=project_id, now=datetime.now(UTC)
    ) == first_id

    closed_at = datetime.now(UTC)
    close_planning_conversation(conn, project_id=project_id, closed_at=closed_at)
    close_planning_conversation(conn, project_id=project_id, closed_at=datetime.now(UTC))
    predecessor = conn.execute(
        select(conversation).where(conversation.c.id == first_id)
    ).one()
    assert predecessor.status == "closed"
    assert predecessor.closed_at == closed_at

    successor_id = ensure_active_planning_conversation(
        conn, project_id=project_id, now=datetime.now(UTC)
    )
    assert successor_id != first_id
    active_ids = conn.execute(
        select(conversation.c.id)
        .where(conversation.c.project_id == project_id)
        .where(conversation.c.kind == "planning")
        .where(conversation.c.status == "active")
    ).scalars().all()
    assert active_ids == [successor_id]


def test_finish_run_closes_planning_conversation_in_terminal_transaction(
    engine: Engine,
) -> None:
    """A succeeded run closes the active planning conversation atomically (B3).

    Drives the real ``_finish_run`` so the closure is proven at the runner's
    terminal transaction, not just at the helper: status, ``run.finished``
    event and conversation closure commit together; a failed run leaves the
    conversation active for replanning.
    """
    from policy_atlas.core.schema import capability_run, event_log, evidence_scope
    from policy_atlas.runtime.runner import _finish_run
    from tests.helpers import delete_project_data

    project_id = None
    try:
        with engine.begin() as conn:
            project_id = _seed_project(conn)
            conversation_id = ensure_active_planning_conversation(
                conn, project_id=project_id, now=datetime.now(UTC)
            )
            scope_id = uuid.uuid4()
            conn.execute(
                evidence_scope.insert().values(
                    evidence_scope_id=scope_id,
                    project_id=project_id,
                    intent="closure test",
                    context={},
                    created_at=datetime.now(UTC),
                )
            )

            def seed_run(status: str) -> uuid.UUID:
                run_id = uuid.uuid4()
                conn.execute(
                    capability_run.insert().values(
                        capability_run_id=run_id,
                        project_id=project_id,
                        evidence_scope_id=scope_id,
                        capability="evidence_base",
                        plan_id=uuid.uuid4(),
                        plan_version=1,
                        status="running",
                        started_at=datetime.now(UTC),
                    )
                )
                return run_id

            failed_run_id = seed_run("running")
            succeeded_run_id = seed_run("running")

        _finish_run(
            engine,
            [],
            [],
            status="failed",
            capability_run_id=failed_run_id,
            project_id=project_id,
        )
        with engine.connect() as conn:
            row = conn.execute(
                select(conversation.c.status).where(conversation.c.id == conversation_id)
            ).one()
            assert row.status == "active"

        _finish_run(
            engine,
            [],
            [],
            status="succeeded",
            capability_run_id=succeeded_run_id,
            project_id=project_id,
        )
        with engine.connect() as conn:
            closed = conn.execute(
                select(conversation.c.status, conversation.c.closed_at).where(
                    conversation.c.id == conversation_id
                )
            ).one()
            run_ended_at = conn.execute(
                select(capability_run.c.ended_at).where(
                    capability_run.c.capability_run_id == succeeded_run_id
                )
            ).scalar_one()
            finished_events = conn.execute(
                select(event_log.c.event_id)
                .where(event_log.c.project_id == project_id)
                .where(event_log.c.event_type == "run.finished")
            ).scalars().all()
        assert closed.status == "closed"
        assert closed.closed_at == run_ended_at
        assert len(finished_events) == 2
    finally:
        if project_id is not None:
            with engine.begin() as conn:
                delete_project_data(conn, project_id)
