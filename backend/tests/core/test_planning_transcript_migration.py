"""Migration roundtrip coverage for the durable transcript table (task 027).

The table was created as ``planning_transcript``; task 044 renamed it to
``task_agent_transcript``, so at head the roundtrip reads the new names while
the revision under test is still the 027 one.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from alembic import command
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from policy_atlas.core.schema import task, task_agent_transcript
from tests.conftest import _alembic_cfg

PRE_MIGRATION_REVISION = "c6e2b4f8a1d3"


def test_planning_transcript_migration_downgrade_roundtrip(engine: Engine) -> None:
    """Drop a populated transcript cleanly, then restore its exact table shape."""
    cfg = _alembic_cfg()
    task_id = uuid.uuid4()
    command.downgrade(cfg, PRE_MIGRATION_REVISION)
    tables = set(inspect(engine).get_table_names())
    assert "planning_transcript" not in tables and "task_agent_transcript" not in tables
    command.upgrade(cfg, "head")
    try:
        with engine.begin() as conn:
            now = datetime.now(UTC)
            conn.execute(task.insert().values(
                task_id=task_id,
                created_at=now,
                name="Transcript migration fixture",
                question=None,
                status="active",
                updated_at=now,
                archived_at=None,
                owner_user_id="migration-owner",
            ))
            conn.execute(task_agent_transcript.insert().values(
                id=uuid.uuid4(),
                task_id=task_id,
                client_turn_id=uuid.uuid4(),
                turn_index=0,
                user_message="Persisted before downgrade",
                reply="A durable reply",
                task_agent_state={"question": "Persisted before downgrade"},
                response={"reply": "A durable reply", "plan": {}, "suggestions": []},
                suggestions=[],
                status="completed",
                created_at=now,
                completed_at=now,
            ))
        command.downgrade(cfg, PRE_MIGRATION_REVISION)
        dropped = set(inspect(engine).get_table_names())
        assert "planning_transcript" not in dropped and "task_agent_transcript" not in dropped
        command.upgrade(cfg, "head")
        columns = {
            column["name"] for column in inspect(engine).get_columns("task_agent_transcript")
        }
        assert columns == {
            "id", "task_id", "client_turn_id", "turn_index", "user_message", "reply",
            "task_agent_state", "response", "suggestions", "status", "created_at", "completed_at",
            "part",
            # 029: the unified conversation model additively attaches turns to
            # their Task Agent conversation (approved schema gate, strand 1).
            "conversation_id",
        }
    finally:
        command.upgrade(cfg, "head")
        with engine.begin() as conn:
            conn.execute(task.delete().where(task.c.task_id == task_id))
