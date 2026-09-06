"""Roundtrip coverage for the task 029 conversation-model migration.

Two catalog generations (plan D9): below revision c1a7f4e9b0d2 the Task is the
table ``project``, its key is ``project_id`` and the plan table is
``orchestration_plan``, so the seeds reflect the live shape; at head the same
rows are addressed through ``core.schema``'s post-rename metadata.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import Connection, Engine, RowMapping
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.schema import (
    artefact,
    chat_turn,
    conversation,
    planning_transcript,
    task,
)
from tests.conftest import _alembic_cfg
from tests.core.legacy_catalog import legacy_table

PRE_029_REVISION = "f4a8c2d7e1b9"
_BASE_TIME = datetime(2026, 8, 1, tzinfo=UTC)


def _scratch_database(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> tuple[Engine, URL]:
    """Create and select an isolated database for a migration roundtrip."""
    base_url = make_url(os.environ["DATABASE_URL"])
    scratch_name = f"{base_url.database}_migr_{uuid.uuid4().hex[:8]}"
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
        admin.execute(text(f'CREATE DATABASE "{scratch_name}"'))
    scratch_url = base_url.set(database=scratch_name)
    monkeypatch.setenv("DATABASE_URL", scratch_url.render_as_string(hide_password=False))
    return create_engine(scratch_url), scratch_url


def _drop_scratch_database(engine: Engine, scratch: Engine, scratch_url: URL) -> None:
    """Dispose and remove an isolated migration database."""
    scratch.dispose()
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
        admin.execute(text(f'DROP DATABASE IF EXISTS "{scratch_url.database}" WITH (FORCE)'))


def _seed_task(
    conn: Connection, *, archived: bool = False, legacy: bool = True
) -> uuid.UUID:
    """Insert a pre-029 Task and return its id.

    Args:
        conn: Open connection on the revision being exercised.
        archived: Seed the archived lifecycle state.
        legacy: Seed BELOW revision c1a7f4e9b0d2, where the Task table is still
            named ``project`` and its key ``project_id`` (plan D9).

    Returns:
        The new Task's id.
    """
    task_id = uuid.uuid4()
    created_at = _BASE_TIME
    table = legacy_table(conn, "project") if legacy else task
    conn.execute(
        table.insert().values(**{
            "project_id" if legacy else "task_id": task_id,
            "created_at": created_at,
            "name": f"Task {task_id}",
            "question": None,
            "status": "archived" if archived else "active",
            "updated_at": created_at,
            "archived_at": created_at if archived else None,
            "owner_user_id": "migration-test-owner",
        })
    )
    return task_id


def _seed_planning_turn(
    conn: Connection,
    task_id: uuid.UUID,
    *,
    created_at: datetime,
    status: str = "completed",
) -> uuid.UUID:
    """Insert a pre-029 planning turn (below the 038 revision) and return its id."""
    turn_id = uuid.uuid4()
    conn.execute(
        legacy_table(conn, "planning_transcript").insert().values(
            id=turn_id,
            project_id=task_id,
            client_turn_id=uuid.uuid4(),
            turn_index=created_at.day,
            user_message="Legacy planning turn",
            reply="Legacy reply" if status == "completed" else None,
            planner_state=None,
            response=None,
            part=None,
            suggestions=[],
            status=status,
            created_at=created_at,
            completed_at=created_at if status == "completed" else None,
        )
    )
    return turn_id


def _seed_capability_run(
    conn: Connection,
    task_id: uuid.UUID,
    *,
    status: str,
    started_at: datetime,
    ended_at: datetime | None,
) -> uuid.UUID:
    """Insert a pre-029 capability run (below the 038 revision) and return its id."""
    scope_id = uuid.uuid4()
    run_id = uuid.uuid4()
    conn.execute(
        legacy_table(conn, "evidence_scope").insert().values(
            evidence_scope_id=scope_id,
            project_id=task_id,
            intent="Migration test scope",
            context={},
            created_at=started_at,
        )
    )
    conn.execute(
        legacy_table(conn, "capability_run").insert().values(
            capability_run_id=run_id,
            project_id=task_id,
            evidence_scope_id=scope_id,
            capability="evidence_base",
            plan_id=uuid.uuid4(),
            plan_version=1,
            status=status,
            session_id=None,
            started_at=started_at,
            ended_at=ended_at,
        )
    )
    return run_id


def _seed_plan(
    conn: Connection, task_id: uuid.UUID, *, status: str, version: int
) -> uuid.UUID:
    """Insert a pre-029 plan version (table ``orchestration_plan``) and return its id."""
    plan_id = uuid.uuid4()
    conn.execute(
        legacy_table(conn, "orchestration_plan").insert().values(
            plan_id=plan_id,
            project_id=task_id,
            evidence_scope_id=None,
            version=version,
            status=status,
            payload={},
            created_at=_BASE_TIME + timedelta(days=version),
            created_by="planner",
            approved_at=None,
        )
    )
    return plan_id


def _conversations_for(conn: Connection, task_id: uuid.UUID) -> list[RowMapping]:
    """Return a Task's migrated conversations in creation order (read at head)."""
    return list(
        conn.execute(
            select(conversation)
            .where(conversation.c.task_id == task_id)
            .order_by(conversation.c.created_at)
        ).mappings()
    )


def test_029_backfill_follows_the_approved_truth_table(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Backfill every required Task/run state into its planning conversation(s)."""
    shared = engine
    scratch, scratch_url = _scratch_database(shared, monkeypatch)
    cfg = _alembic_cfg()

    try:
        command.upgrade(cfg, PRE_029_REVISION)
        with scratch.begin() as conn:
            no_run_task = _seed_task(conn)
            no_run_turns = [
                _seed_planning_turn(conn, no_run_task, created_at=_BASE_TIME),
                _seed_planning_turn(
                    conn, no_run_task, created_at=_BASE_TIME + timedelta(days=1)
                ),
            ]

            running_task = _seed_task(conn)
            _seed_planning_turn(conn, running_task, created_at=_BASE_TIME)
            _seed_capability_run(
                conn,
                running_task,
                status="running",
                started_at=_BASE_TIME + timedelta(days=2),
                ended_at=None,
            )

            completed_task = _seed_task(conn)
            _seed_planning_turn(conn, completed_task, created_at=_BASE_TIME)
            completed_ended_at = _BASE_TIME + timedelta(days=3)
            _seed_capability_run(
                conn,
                completed_task,
                status="succeeded",
                started_at=_BASE_TIME + timedelta(days=2),
                ended_at=completed_ended_at,
            )

            mid_replan_task = _seed_task(conn)
            pre_run_turn = _seed_planning_turn(
                conn, mid_replan_task, created_at=_BASE_TIME
            )
            mid_replan_ended_at = _BASE_TIME + timedelta(days=3)
            post_run_turns = [
                _seed_planning_turn(
                    conn,
                    mid_replan_task,
                    created_at=_BASE_TIME + timedelta(days=4),
                ),
                _seed_planning_turn(
                    conn,
                    mid_replan_task,
                    created_at=_BASE_TIME + timedelta(days=5),
                ),
            ]
            _seed_capability_run(
                conn,
                mid_replan_task,
                status="succeeded",
                started_at=_BASE_TIME + timedelta(days=2),
                ended_at=mid_replan_ended_at,
            )

            # Edge (contract-verifier + /code-review, rev fix): a succeeded run with
            # no completed turn after it, but where EVERY turn postdates the run's
            # own ended_at (no turns exist before the boundary at all) — the
            # mid-replan split's pre-run half would own zero turns.
            no_pre_run_split_task = _seed_task(conn)
            no_pre_run_split_ended_at = _BASE_TIME + timedelta(days=3)
            _seed_capability_run(
                conn,
                no_pre_run_split_task,
                status="succeeded",
                started_at=_BASE_TIME + timedelta(days=2),
                ended_at=no_pre_run_split_ended_at,
            )
            post_only_turn = _seed_planning_turn(
                conn,
                no_pre_run_split_task,
                created_at=_BASE_TIME + timedelta(days=4),
            )

            # Edge: a succeeded run whose ended_at is NULL (data-integrity smell) —
            # closing honestly must not leave closed_at NULL too.
            succeeded_null_ended_task = _seed_task(conn)
            succeeded_null_ended_started_at = _BASE_TIME + timedelta(days=2)
            _seed_planning_turn(conn, succeeded_null_ended_task, created_at=_BASE_TIME)
            _seed_capability_run(
                conn,
                succeeded_null_ended_task,
                status="succeeded",
                started_at=succeeded_null_ended_started_at,
                ended_at=None,
            )

            failed_task = _seed_task(conn)
            _seed_planning_turn(conn, failed_task, created_at=_BASE_TIME)
            _seed_capability_run(
                conn,
                failed_task,
                status="failed",
                started_at=_BASE_TIME + timedelta(days=2),
                ended_at=_BASE_TIME + timedelta(days=3),
            )

            abandoned_task = _seed_task(conn)
            _seed_planning_turn(conn, abandoned_task, created_at=_BASE_TIME)
            _seed_capability_run(
                conn,
                abandoned_task,
                status="failed",
                started_at=_BASE_TIME + timedelta(days=2),
                ended_at=_BASE_TIME + timedelta(days=3),
            )
            _seed_plan(conn, abandoned_task, status="abandoned", version=1)

            archived_task = _seed_task(conn, archived=True)
            _seed_planning_turn(conn, archived_task, created_at=_BASE_TIME)

            zero_turn_task = _seed_task(conn)

        command.upgrade(cfg, "head")
        with scratch.connect() as conn:
            no_run_conversation = _conversations_for(conn, no_run_task)
            assert len(no_run_conversation) == 1
            assert no_run_conversation[0]["status"] == "active"
            assert set(
                conn.execute(
                    select(planning_transcript.c.id).where(
                        planning_transcript.c.conversation_id == no_run_conversation[0]["id"]
                    )
                ).scalars()
            ) == set(no_run_turns)

            assert _conversations_for(conn, running_task)[0]["status"] == "active"

            completed_conversation = _conversations_for(conn, completed_task)
            assert len(completed_conversation) == 1
            assert completed_conversation[0]["status"] == "closed"
            assert completed_conversation[0]["closed_at"] == completed_ended_at

            mid_replan_conversations = _conversations_for(conn, mid_replan_task)
            assert [row["status"] for row in mid_replan_conversations] == ["closed", "active"]
            assert mid_replan_conversations[0]["closed_at"] == mid_replan_ended_at
            assert set(
                conn.execute(
                    select(planning_transcript.c.id).where(
                        planning_transcript.c.conversation_id == mid_replan_conversations[0]["id"]
                    )
                ).scalars()
            ) == {pre_run_turn}
            assert set(
                conn.execute(
                    select(planning_transcript.c.id).where(
                        planning_transcript.c.conversation_id == mid_replan_conversations[1]["id"]
                    )
                ).scalars()
            ) == set(post_run_turns)
            assert sum(row["status"] == "active" for row in mid_replan_conversations) == 1

            no_pre_run_split_conversations = _conversations_for(conn, no_pre_run_split_task)
            assert len(no_pre_run_split_conversations) == 1
            assert no_pre_run_split_conversations[0]["status"] == "active"
            assert set(
                conn.execute(
                    select(planning_transcript.c.id).where(
                        planning_transcript.c.conversation_id
                        == no_pre_run_split_conversations[0]["id"]
                    )
                ).scalars()
            ) == {post_only_turn}

            succeeded_null_ended_conversation = _conversations_for(
                conn, succeeded_null_ended_task
            )
            assert len(succeeded_null_ended_conversation) == 1
            assert succeeded_null_ended_conversation[0]["status"] == "closed"
            assert (
                succeeded_null_ended_conversation[0]["closed_at"]
                == succeeded_null_ended_started_at
            )

            assert _conversations_for(conn, failed_task)[0]["status"] == "active"
            abandoned_conversation = _conversations_for(conn, abandoned_task)[0]
            assert abandoned_conversation["status"] == "closed"
            assert abandoned_conversation["closed_at"] is not None

            archived_conversation = _conversations_for(conn, archived_task)[0]
            assert archived_conversation["status"] == "active"
            assert archived_conversation["archived_at"] is None

            assert _conversations_for(conn, zero_turn_task) == []
    finally:
        _drop_scratch_database(shared, scratch, scratch_url)


def test_029_migration_roundtrip_preserves_legacy_rows_and_enforces_new_invariants(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Roundtrip legacy rows and exercise the new chat and planning constraints."""
    shared = engine
    scratch, scratch_url = _scratch_database(shared, monkeypatch)
    cfg = _alembic_cfg()
    artefact_id = uuid.uuid4()
    transcript_id = uuid.uuid4()

    try:
        command.upgrade(cfg, PRE_029_REVISION)
        with scratch.begin() as conn:
            task_id = _seed_task(conn)
            conn.execute(
                legacy_table(conn, "artefact").insert().values(
                    artefact_id=artefact_id,
                    project_id=task_id,
                    title="Legacy artefact",
                    created_at=_BASE_TIME,
                    summary=None,
                    summary_status=None,
                )
            )
            transcript_id = _seed_planning_turn(
                conn, task_id, created_at=_BASE_TIME, status="pending"
            )

        command.upgrade(cfg, "head")
        with scratch.begin() as conn:
            inspector = inspect(conn)
            assert {"conversation", "chat_turn"} <= set(inspector.get_table_names())
            assert {"conversation_id"} <= {
                column["name"] for column in inspector.get_columns("planning_transcript")
            }
            assert {"conversation_id"} <= {
                column["name"] for column in inspector.get_columns("plan")
            }
            assert {"capability_run_id"} <= {
                column["name"] for column in inspector.get_columns("artefact")
            }
            assert {
                "uq_chat_turn_conv_index",
                "uq_chat_turn_conv_client",
            } <= {
                constraint["name"]
                for constraint in inspector.get_unique_constraints("chat_turn")
            }

            constraint_task_id = _seed_task(conn, legacy=False)
            planning_id = uuid.uuid4()
            conn.execute(
                conversation.insert().values(
                    id=planning_id,
                    task_id=constraint_task_id,
                    kind="planning",
                    title="Planning",
                    entry_artefact_id=None,
                    status="active",
                    created_at=_BASE_TIME + timedelta(days=1),
                    closed_at=None,
                    archived_at=None,
                )
            )
            with pytest.raises(IntegrityError), conn.begin_nested():
                conn.execute(
                    conversation.insert().values(
                        id=uuid.uuid4(),
                        task_id=constraint_task_id,
                        kind="planning",
                        title="Second planning conversation",
                        entry_artefact_id=None,
                        status="active",
                        created_at=_BASE_TIME + timedelta(days=2),
                        closed_at=None,
                        archived_at=None,
                    )
                )

            chat_id = uuid.uuid4()
            turn_id = uuid.uuid4()
            client_turn_id = uuid.uuid4()
            conn.execute(
                conversation.insert().values(
                    id=chat_id,
                    task_id=task_id,
                    kind="chat",
                    title="A chat",
                    entry_artefact_id=artefact_id,
                    status="active",
                    created_at=_BASE_TIME + timedelta(days=1),
                    closed_at=None,
                    archived_at=None,
                )
            )
            conn.execute(
                chat_turn.insert().values(
                    id=turn_id,
                    conversation_id=chat_id,
                    turn_index=0,
                    client_turn_id=client_turn_id,
                    user_message="What does the artefact say?",
                    answer="It says this.",
                    answer_payload={"claims": []},
                    capability_run_id=None,
                    status="completed",
                    created_at=_BASE_TIME + timedelta(days=1),
                    completed_at=_BASE_TIME + timedelta(days=1),
                )
            )
            assert conn.execute(
                select(
                    chat_turn.c.conversation_id,
                    chat_turn.c.client_turn_id,
                    chat_turn.c.answer_payload,
                ).where(chat_turn.c.id == turn_id)
            ).one() == (chat_id, client_turn_id, {"claims": []})

        command.downgrade(cfg, PRE_029_REVISION)
        with scratch.connect() as conn:
            inspector = inspect(conn)
            assert {"conversation", "chat_turn"}.isdisjoint(inspector.get_table_names())
            assert "conversation_id" not in {
                column["name"] for column in inspector.get_columns("planning_transcript")
            }
            assert "conversation_id" not in {
                column["name"] for column in inspector.get_columns("orchestration_plan")
            }
            assert "capability_run_id" not in {
                column["name"] for column in inspector.get_columns("artefact")
            }
            assert conn.execute(
                select(planning_transcript.c.user_message).where(
                    planning_transcript.c.id == transcript_id
                )
            ).scalar_one() == "Legacy planning turn"
            assert conn.execute(
                select(artefact.c.title).where(artefact.c.artefact_id == artefact_id)
            ).scalar_one() == "Legacy artefact"
    finally:
        _drop_scratch_database(shared, scratch, scratch_url)
