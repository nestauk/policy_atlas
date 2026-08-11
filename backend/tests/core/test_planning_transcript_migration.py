"""Migration roundtrip coverage for the durable planning transcript table."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from alembic import command
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from policy_atlas.core.schema import planning_transcript, project
from tests.conftest import _alembic_cfg

PRE_MIGRATION_REVISION = "c6e2b4f8a1d3"


def test_planning_transcript_migration_downgrade_roundtrip(engine: Engine) -> None:
    """Drop a populated transcript cleanly, then restore its exact table shape."""
    cfg = _alembic_cfg()
    project_id = uuid.uuid4()
    command.downgrade(cfg, PRE_MIGRATION_REVISION)
    assert "planning_transcript" not in set(inspect(engine).get_table_names())
    command.upgrade(cfg, "head")
    try:
        with engine.begin() as conn:
            now = datetime.now(UTC)
            conn.execute(project.insert().values(
                project_id=project_id,
                created_at=now,
                name="Transcript migration fixture",
                question=None,
                status="active",
                updated_at=now,
                archived_at=None,
                owner_user_id="migration-owner",
            ))
            conn.execute(planning_transcript.insert().values(
                id=uuid.uuid4(),
                project_id=project_id,
                client_turn_id=uuid.uuid4(),
                turn_index=0,
                user_message="Persisted before downgrade",
                reply="A durable reply",
                planner_state={"question": "Persisted before downgrade"},
                response={"reply": "A durable reply", "plan": {}, "suggestions": []},
                suggestions=[],
                status="completed",
                created_at=now,
                completed_at=now,
            ))
        command.downgrade(cfg, PRE_MIGRATION_REVISION)
        assert "planning_transcript" not in set(inspect(engine).get_table_names())
        command.upgrade(cfg, "head")
        columns = {column["name"] for column in inspect(engine).get_columns("planning_transcript")}
        assert columns == {
            "id", "project_id", "client_turn_id", "turn_index", "user_message", "reply",
            "planner_state", "response", "suggestions", "status", "created_at", "completed_at",
            "part",
        }
    finally:
        command.upgrade(cfg, "head")
        with engine.begin() as conn:
            conn.execute(project.delete().where(project.c.project_id == project_id))
