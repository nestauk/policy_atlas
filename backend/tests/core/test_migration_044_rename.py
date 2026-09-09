"""Round-trip coverage for the task 044 Task Agent rename (``a7d3f1c8e2b5``).

Seeds a populated pre-044 database at ``c1a7f4e9b0d2`` under the old names,
upgrades, and asserts the catalog and both stored values moved; then downgrades
and asserts the fixture comes back exactly as it was seeded. The revision is a
pure rename, so "exactly" is the whole test.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from alembic import command
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Connection, Engine

from policy_atlas.core.schema import conversation, task, task_agent_transcript, task_plan
from tests.conftest import _alembic_cfg
from tests.core.legacy_catalog import legacy_table

PRE_044_REVISION = "c1a7f4e9b0d2"

# The catalog exactly as ``a7d3f1c8e2b5`` leaves it, and exactly as it found it.
_AFTER_CONSTRAINTS = {
    "task_agent_transcript_pkey",
    "task_agent_transcript_task_id_fkey",
    "fk_task_agent_transcript_conversation",
    "uq_tat_task_client_turn",
    "uq_tat_task_turn_index",
    "ck_tat_status",
    "ck_tat_suggestions_array",
}
_BEFORE_CONSTRAINTS = {
    "planning_transcript_pkey",
    "planning_transcript_task_id_fkey",
    "fk_planning_transcript_conversation",
    "uq_ptr_task_client_turn",
    "uq_ptr_task_turn_index",
    "ck_ptr_status",
    "ck_ptr_suggestions_array",
}

_TRANSCRIPT_STATE = {"question": "What works for NEET outreach?"}
_TRANSCRIPT_RESPONSE = {"reply": "A durable reply", "plan": {}, "suggestions": []}


def _catalog(conn: Connection, table: str) -> tuple[set[str], set[str], set[str]]:
    """Return ``(constraint names, index names, column names)`` for one table."""
    constraints = {
        row[0]
        for row in conn.execute(
            text(
                "SELECT conname FROM pg_constraint WHERE conrelid = to_regclass(:t)"
            ),
            {"t": table},
        )
    }
    indexes = {
        row[0]
        for row in conn.execute(
            text("SELECT indexname FROM pg_indexes WHERE tablename = :t"), {"t": table}
        )
    }
    columns = {column["name"] for column in inspect(conn).get_columns(table)}
    return constraints, indexes, columns


def _kind_check(conn: Connection) -> str:
    """The live ``ck_conversation_kind`` expression."""
    return str(
        conn.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_conversation_kind'"
            )
        ).scalar_one()
    )


def _conversation_indexes(conn: Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            text("SELECT indexname FROM pg_indexes WHERE tablename = 'conversation'")
        )
    }


def _seed(engine: Engine, ids: dict[str, uuid.UUID], now: datetime) -> None:
    """Commit the pre-044 fixture at ``c1a7f4e9b0d2``, under the old names."""
    with engine.begin() as conn:
        conn.execute(
            legacy_table(conn, "task").insert().values(
                task_id=ids["task_id"],
                created_at=now,
                name="A pre-044 Task",
                question="What works?",
                status="active",
                updated_at=now,
                archived_at=None,
                owner_user_id="owner-044",
                org_id=None,
                visibility="private",
                is_public=False,
            )
        )
        conn.execute(
            legacy_table(conn, "conversation").insert().values(
                id=ids["conversation_id"],
                task_id=ids["task_id"],
                kind="planning",
                title="Planning",
                entry_artefact_id=None,
                status="active",
                created_at=now,
                closed_at=None,
                archived_at=None,
                created_by="owner-044",
            )
        )
        conn.execute(
            legacy_table(conn, "planning_transcript").insert().values(
                id=ids["turn_id"],
                task_id=ids["task_id"],
                conversation_id=ids["conversation_id"],
                client_turn_id=ids["client_turn_id"],
                turn_index=0,
                user_message="Seeded before the rename",
                reply="A durable reply",
                planner_state=_TRANSCRIPT_STATE,
                response=_TRANSCRIPT_RESPONSE,
                part=None,
                suggestions=[],
                status="completed",
                created_at=now,
                completed_at=now,
            )
        )
        conn.execute(
            legacy_table(conn, "plan").insert().values(
                plan_id=ids["plan_id"],
                task_id=ids["task_id"],
                conversation_id=ids["conversation_id"],
                evidence_scope_id=None,
                version=1,
                status="approved",
                payload={"title": "Pre-044 plan"},
                created_at=now,
                created_by="planner",
                approved_at=now,
            )
        )


def _delete(engine: Engine, ids: dict[str, uuid.UUID]) -> None:
    """Remove the committed fixture at head, FK-ordered."""
    with engine.begin() as conn:
        conn.execute(task_plan.delete().where(task_plan.c.task_id == ids["task_id"]))
        conn.execute(
            task_agent_transcript.delete().where(
                task_agent_transcript.c.task_id == ids["task_id"]
            )
        )
        conn.execute(conversation.delete().where(conversation.c.task_id == ids["task_id"]))
        conn.execute(task.delete().where(task.c.task_id == ids["task_id"]))


def test_044_renames_the_catalog_and_moves_both_stored_values(engine: Engine) -> None:
    """Upgrade renames every object and both values; downgrade puts them all back."""
    cfg = _alembic_cfg()
    now = datetime.now(UTC)
    ids = {
        key: uuid.uuid4()
        for key in ("task_id", "conversation_id", "turn_id", "client_turn_id", "plan_id")
    }
    command.downgrade(cfg, PRE_044_REVISION)
    _seed(engine, ids, now)

    try:
        # --- before -------------------------------------------------------
        with engine.connect() as conn:
            constraints, indexes, columns = _catalog(conn, "planning_transcript")
            assert constraints >= _BEFORE_CONSTRAINTS
            assert "planner_state" in columns
            assert "uq_ptr_task_client_turn" in indexes
            assert "uq_conversation_one_active_planning" in _conversation_indexes(conn)
            assert "'planning'" in _kind_check(conn)

        command.upgrade(cfg, "head")

        # --- after --------------------------------------------------------
        with engine.connect() as conn:
            tables = set(inspect(conn).get_table_names())
            assert "task_agent_transcript" in tables
            assert "planning_transcript" not in tables

            constraints, indexes, columns = _catalog(conn, "task_agent_transcript")
            assert constraints >= _AFTER_CONSTRAINTS
            assert not _BEFORE_CONSTRAINTS & constraints
            assert "task_agent_state" in columns
            assert "planner_state" not in columns
            # Renaming a UNIQUE/PK constraint renames its backing index with it.
            assert {
                "task_agent_transcript_pkey",
                "uq_tat_task_client_turn",
                "uq_tat_task_turn_index",
            } <= indexes

            conversation_indexes = _conversation_indexes(conn)
            assert "uq_conversation_one_active_task_agent" in conversation_indexes
            assert "uq_conversation_one_active_planning" not in conversation_indexes
            conversation_constraints = {
                row[0]
                for row in conn.execute(
                    text(
                        "SELECT conname FROM pg_constraint "
                        "WHERE conrelid = to_regclass('conversation')"
                    )
                )
            }
            assert "ck_conversation_task_agent_never_archived" in conversation_constraints
            assert "ck_conversation_planning_never_archived" not in conversation_constraints
            assert "'task_agent'" in _kind_check(conn)
            assert "'planning'" not in _kind_check(conn)

            # The two stored values.
            assert conn.execute(
                select(conversation.c.kind).where(
                    conversation.c.id == ids["conversation_id"]
                )
            ).scalar_one() == "task_agent"
            assert conn.execute(
                select(task_plan.c.created_by).where(task_plan.c.plan_id == ids["plan_id"])
            ).scalar_one() == "task_agent"

            # The transcript row reads back identically through the new name.
            row: dict[str, Any] = dict(
                conn.execute(
                    select(task_agent_transcript).where(
                        task_agent_transcript.c.id == ids["turn_id"]
                    )
                ).mappings().one()
            )
            assert row["user_message"] == "Seeded before the rename"
            assert row["reply"] == "A durable reply"
            assert row["task_agent_state"] == _TRANSCRIPT_STATE
            assert row["response"] == _TRANSCRIPT_RESPONSE
            assert row["client_turn_id"] == ids["client_turn_id"]
            assert row["conversation_id"] == ids["conversation_id"]

        # --- and back -----------------------------------------------------
        command.downgrade(cfg, PRE_044_REVISION)
        with engine.connect() as conn:
            tables = set(inspect(conn).get_table_names())
            assert "planning_transcript" in tables
            assert "task_agent_transcript" not in tables

            constraints, indexes, columns = _catalog(conn, "planning_transcript")
            assert constraints >= _BEFORE_CONSTRAINTS
            assert not _AFTER_CONSTRAINTS & constraints
            assert "planner_state" in columns
            assert "uq_conversation_one_active_planning" in _conversation_indexes(conn)
            assert "'planning'" in _kind_check(conn)

            legacy_conversation = legacy_table(conn, "conversation")
            legacy_transcript = legacy_table(conn, "planning_transcript")
            legacy_plan = legacy_table(conn, "plan")
            assert conn.execute(
                select(legacy_conversation.c.kind).where(
                    legacy_conversation.c.id == ids["conversation_id"]
                )
            ).scalar_one() == "planning"
            assert conn.execute(
                select(legacy_plan.c.created_by).where(
                    legacy_plan.c.plan_id == ids["plan_id"]
                )
            ).scalar_one() == "planner"
            back = dict(
                conn.execute(
                    select(legacy_transcript).where(legacy_transcript.c.id == ids["turn_id"])
                ).mappings().one()
            )
            assert back["planner_state"] == _TRANSCRIPT_STATE
            assert back["user_message"] == "Seeded before the rename"

        # The chain is re-runnable: upgrading again is the deploy path.
        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            assert "task_agent_transcript" in set(inspect(conn).get_table_names())
    finally:
        command.upgrade(cfg, "head")
        _delete(engine, ids)
