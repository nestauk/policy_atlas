"""Migration roundtrip for task 025 Task lifecycle and capability-run states.

The test deliberately walks the real Alembic chain from its task-024 head,
with committed pre-025 fixtures between DDL operations. It proves the exact
Task backfill and capability-run downgrade mappings, including deletion of
the new run-less lifecycle audit rows before ``event_log.run_id`` becomes
NOT NULL again.

Two catalog generations (plan D9): below revision c1a7f4e9b0d2 the Task is the
table ``project`` and the plan is ``orchestration_plan``, so the seeds reflect
the live shape; at head they use ``core.schema``'s post-rename metadata.
"""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, select, text, update
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.engine.url import make_url

from policy_atlas.core.schema import capability_run, event_log, task
from tests.conftest import _alembic_cfg
from tests.core.legacy_catalog import legacy_table

PRE_025_REVISION = "a3c6f9e2b7d4"


def _timestamp(offset: int) -> datetime:
    """Return a stable timezone-aware fixture timestamp."""
    return datetime(2026, 7, 21, tzinfo=UTC) + timedelta(minutes=offset)


def _seed_legacy_task(
    connection: Connection, task_id: uuid.UUID, created_at: datetime
) -> None:
    """Insert the pre-025 shape of a Task row (table ``project`` back there)."""
    connection.execute(
        legacy_table(connection, "project").insert().values(
            project_id=task_id, created_at=created_at
        )
    )


def _seed_capability_run(
    connection: Connection,
    *,
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
    status: str,
    ended_at: datetime | None,
    legacy: bool = False,
) -> uuid.UUID:
    """Insert a capability run with the supplied status and completion time.

    Args:
        connection: Open connection on the revision being exercised.
        task_id: Task the walk belongs to.
        scope_id: Evidence scope the walk opened on.
        status: Walk status to store.
        ended_at: Completion time, or ``None`` for an open walk.
        legacy: Seed BELOW revision c1a7f4e9b0d2 — the column is ``project_id``
            and the capability's stored value is still ``evidence_base``.

    Returns:
        The new walk's ``capability_run_id``.
    """
    capability_run_id = uuid.uuid4()
    table = legacy_table(connection, "capability_run") if legacy else capability_run
    values: dict[str, object] = {
        "capability_run_id": capability_run_id,
        "project_id" if legacy else "task_id": task_id,
        "evidence_scope_id": scope_id,
        "capability": "evidence_base" if legacy else "evidence_search",
        "plan_id": uuid.uuid4(),
        "plan_version": 1,
        "status": status,
        "session_id": None,
        "started_at": _timestamp(5),
        "ended_at": ended_at,
    }
    connection.execute(table.insert().values(**values))
    return capability_run_id


def test_025_migrations_roundtrip_with_populated_predecessor(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Backfill, exact downgrade mappings, and a second clean upgrade all work.

    Runs against a per-test SCRATCH database, never the shared test DB: each
    add/drop-column cycle permanently consumes tuple-descriptor slots
    (Postgres counts dropped columns toward its 1600-column table limit), and
    walking six Task columns up and down on the shared DB every suite
    run exhausted that limit in practice. The scratch DB is created from the
    shared engine, migrated from zero, and dropped afterwards.
    """
    shared = engine
    base_url = make_url(os.environ["DATABASE_URL"])
    scratch_name = f"{base_url.database}_migr_{uuid.uuid4().hex[:8]}"
    with shared.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
        admin.execute(text(f'CREATE DATABASE "{scratch_name}"'))
    scratch_url = base_url.set(database=scratch_name)
    monkeypatch.setenv("DATABASE_URL", scratch_url.render_as_string(hide_password=False))
    engine = create_engine(scratch_url)

    cfg = _alembic_cfg()
    plan_task_id = uuid.uuid4()
    planless_task_id = uuid.uuid4()
    scope_id = uuid.uuid4()
    paused_run_id: uuid.UUID | None = None
    interrupted_run_id: uuid.UUID | None = None
    legacy_run_ids: dict[str, uuid.UUID] = {}

    command.upgrade(cfg, PRE_025_REVISION)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        plan_created_at = _timestamp(1)
        planless_created_at = _timestamp(2)
        _seed_legacy_task(connection, plan_task_id, plan_created_at)
        _seed_legacy_task(connection, planless_task_id, planless_created_at)
        legacy_scope = legacy_table(connection, "evidence_scope")
        legacy_plan = legacy_table(connection, "orchestration_plan")
        connection.execute(
            legacy_scope.insert().values(
                evidence_scope_id=scope_id,
                project_id=plan_task_id,
                intent="Migration fixture",
                context={},
                created_at=_timestamp(3),
            )
        )
        connection.execute(
            legacy_plan.insert().values(
                plan_id=uuid.uuid4(),
                project_id=plan_task_id,
                evidence_scope_id=None,
                version=1,
                status="approved",
                payload={"title": "Older plan", "question": "Older question"},
                created_at=_timestamp(3),
                created_by="user",
                approved_at=_timestamp(3),
            )
        )
        connection.execute(
            legacy_plan.insert().values(
                plan_id=uuid.uuid4(),
                project_id=plan_task_id,
                evidence_scope_id=None,
                version=2,
                status="approved",
                payload={"title": "Latest plan", "question": "Latest question"},
                created_at=_timestamp(4),
                created_by="user",
                approved_at=_timestamp(4),
            )
        )
        for status, ended_at in {
            "running": None,
            "succeeded": _timestamp(6),
            "degraded": _timestamp(7),
            "failed": _timestamp(8),
            "aborted": _timestamp(9),
        }.items():
            legacy_run_ids[status] = _seed_capability_run(
                connection,
                task_id=plan_task_id,
                scope_id=scope_id,
                status=status,
                ended_at=ended_at,
                legacy=True,
            )
        transaction.commit()
    finally:
        connection.close()

    try:
        command.upgrade(cfg, "head")
        connection = engine.connect()
        transaction = connection.begin()
        try:
            plan_row = connection.execute(
                select(
                    task.c.name,
                    task.c.question,
                    task.c.status,
                    task.c.created_at,
                    task.c.updated_at,
                    task.c.owner_user_id,
                ).where(task.c.task_id == plan_task_id)
            ).one()
            assert plan_row.name == "Latest plan"
            assert plan_row.question == "Latest question"
            assert plan_row.status == "active"
            assert plan_row.updated_at == plan_row.created_at
            assert plan_row.owner_user_id is None

            planless_row = connection.execute(
                select(
                    task.c.name,
                    task.c.question,
                    task.c.status,
                    task.c.created_at,
                    task.c.updated_at,
                    task.c.owner_user_id,
                ).where(task.c.task_id == planless_task_id)
            ).one()
            assert planless_row.name == "Untitled project"
            assert planless_row.question is None
            assert planless_row.status == "active"
            assert planless_row.updated_at == planless_row.created_at
            assert planless_row.owner_user_id is None

            paused_run_id = _seed_capability_run(
                connection,
                task_id=plan_task_id,
                scope_id=scope_id,
                status="paused",
                ended_at=None,
            )
            interrupted_run_id = _seed_capability_run(
                connection,
                task_id=plan_task_id,
                scope_id=scope_id,
                status="interrupted",
                ended_at=None,
            )
            archived_at = _timestamp(10)
            connection.execute(
                update(task)
                .where(task.c.task_id == planless_task_id)
                .values(status="archived", archived_at=archived_at, updated_at=archived_at)
            )
            connection.execute(
                event_log.insert().values(
                    event_id=uuid.uuid4(),
                    run_id=None,
                    task_id=plan_task_id,
                    sequence=1,
                    event_type="task.archived",
                    occurred_at=archived_at,
                    payload={"actor": "user"},
                )
            )
            transaction.commit()
        finally:
            connection.close()

        command.downgrade(cfg, PRE_025_REVISION)
        assert paused_run_id is not None
        assert interrupted_run_id is not None
        connection = engine.connect()
        transaction = connection.begin()
        try:
            rows = {
                row.capability_run_id: row
                for row in connection.execute(
                    select(
                        capability_run.c.capability_run_id,
                        capability_run.c.status,
                        capability_run.c.ended_at,
                    ).where(
                        capability_run.c.capability_run_id.in_(
                            [paused_run_id, interrupted_run_id, *legacy_run_ids.values()]
                        )
                    )
                )
            }
            assert rows[paused_run_id].status == "aborted"
            assert rows[paused_run_id].ended_at is not None
            assert rows[interrupted_run_id].status == "failed"
            assert rows[interrupted_run_id].ended_at is not None
            for status, run_id in legacy_run_ids.items():
                assert rows[run_id].status == status
            assert rows[legacy_run_ids["running"]].ended_at is None
            assert rows[legacy_run_ids["succeeded"]].ended_at == _timestamp(6)
            assert rows[legacy_run_ids["degraded"]].ended_at == _timestamp(7)
            assert rows[legacy_run_ids["failed"]].ended_at == _timestamp(8)
            assert rows[legacy_run_ids["aborted"]].ended_at == _timestamp(9)
            assert connection.execute(select(event_log.c.event_id)).all() == []

            inspector = inspect(connection)
            # Below the 038 revision the Task table is still named `project`.
            task_columns = {column["name"] for column in inspector.get_columns("project")}
            assert task_columns == {"project_id", "created_at"}
            event_log_columns = {
                column["name"]: column for column in inspector.get_columns("event_log")
            }
            assert event_log_columns["run_id"]["nullable"] is False
        finally:
            transaction.rollback()
            connection.close()

        command.upgrade(cfg, "head")
        connection = engine.connect()
        transaction = connection.begin()
        try:
            assert connection.execute(
                select(task.c.name).where(task.c.task_id == plan_task_id)
            ).scalar_one() == "Latest plan"
            assert connection.execute(
                select(task.c.name).where(task.c.task_id == planless_task_id)
            ).scalar_one() == "Untitled project"
        finally:
            transaction.rollback()
            connection.close()
    finally:
        engine.dispose()
        with shared.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
            admin.execute(text(f'DROP DATABASE IF EXISTS "{scratch_name}" WITH (FORCE)'))
