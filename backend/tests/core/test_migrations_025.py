"""Migration roundtrip for task 025 project lifecycle and capability-run states.

The test deliberately walks the real Alembic chain from its task-024 head,
with committed pre-025 fixtures between DDL operations. It proves the exact
project backfill and capability-run downgrade mappings, including deletion of
the new run-less lifecycle audit rows before ``event_log.run_id`` becomes
NOT NULL again.
"""

import uuid
from datetime import UTC, datetime, timedelta

from alembic import command
from sqlalchemy import inspect, select, update
from sqlalchemy.engine import Connection, Engine

from policy_atlas.core.schema import (
    capability_run,
    event_log,
    evidence_scope,
    orchestration_plan,
    project,
)
from tests.conftest import _alembic_cfg
from tests.helpers import delete_project_data

PRE_025_REVISION = "a3c6f9e2b7d4"


def _timestamp(offset: int) -> datetime:
    """Return a stable timezone-aware fixture timestamp."""
    return datetime(2026, 7, 21, tzinfo=UTC) + timedelta(minutes=offset)


def _seed_project(connection: Connection, project_id: uuid.UUID, created_at: datetime) -> None:
    """Insert the pre-025 shape of a project row."""
    connection.execute(project.insert().values(project_id=project_id, created_at=created_at))


def _seed_capability_run(
    connection: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    status: str,
    ended_at: datetime | None,
) -> uuid.UUID:
    """Insert a capability run with the supplied status and completion time."""
    capability_run_id = uuid.uuid4()
    connection.execute(
        capability_run.insert().values(
            capability_run_id=capability_run_id,
            project_id=project_id,
            evidence_scope_id=scope_id,
            capability="evidence_base",
            plan_id=uuid.uuid4(),
            plan_version=1,
            status=status,
            session_id=None,
            started_at=_timestamp(5),
            ended_at=ended_at,
        )
    )
    return capability_run_id


def test_025_migrations_roundtrip_with_populated_predecessor(engine: Engine) -> None:
    """Backfill, exact downgrade mappings, and a second clean upgrade all work."""
    cfg = _alembic_cfg()
    plan_project_id = uuid.uuid4()
    planless_project_id = uuid.uuid4()
    scope_id = uuid.uuid4()
    paused_run_id: uuid.UUID | None = None
    interrupted_run_id: uuid.UUID | None = None
    legacy_run_ids: dict[str, uuid.UUID] = {}

    command.downgrade(cfg, PRE_025_REVISION)
    connection = engine.connect()
    transaction = connection.begin()
    try:
        plan_created_at = _timestamp(1)
        planless_created_at = _timestamp(2)
        _seed_project(connection, plan_project_id, plan_created_at)
        _seed_project(connection, planless_project_id, planless_created_at)
        connection.execute(
            evidence_scope.insert().values(
                evidence_scope_id=scope_id,
                project_id=plan_project_id,
                intent="Migration fixture",
                context={},
                created_at=_timestamp(3),
            )
        )
        connection.execute(
            orchestration_plan.insert().values(
                plan_id=uuid.uuid4(),
                project_id=plan_project_id,
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
            orchestration_plan.insert().values(
                plan_id=uuid.uuid4(),
                project_id=plan_project_id,
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
                project_id=plan_project_id,
                scope_id=scope_id,
                status=status,
                ended_at=ended_at,
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
                    project.c.name,
                    project.c.question,
                    project.c.status,
                    project.c.created_at,
                    project.c.updated_at,
                    project.c.owner_user_id,
                ).where(project.c.project_id == plan_project_id)
            ).one()
            assert plan_row.name == "Latest plan"
            assert plan_row.question == "Latest question"
            assert plan_row.status == "active"
            assert plan_row.updated_at == plan_row.created_at
            assert plan_row.owner_user_id is None

            planless_row = connection.execute(
                select(
                    project.c.name,
                    project.c.question,
                    project.c.status,
                    project.c.created_at,
                    project.c.updated_at,
                    project.c.owner_user_id,
                ).where(project.c.project_id == planless_project_id)
            ).one()
            assert planless_row.name == "Untitled project"
            assert planless_row.question is None
            assert planless_row.status == "active"
            assert planless_row.updated_at == planless_row.created_at
            assert planless_row.owner_user_id is None

            paused_run_id = _seed_capability_run(
                connection,
                project_id=plan_project_id,
                scope_id=scope_id,
                status="paused",
                ended_at=None,
            )
            interrupted_run_id = _seed_capability_run(
                connection,
                project_id=plan_project_id,
                scope_id=scope_id,
                status="interrupted",
                ended_at=None,
            )
            archived_at = _timestamp(10)
            connection.execute(
                update(project)
                .where(project.c.project_id == planless_project_id)
                .values(status="archived", archived_at=archived_at, updated_at=archived_at)
            )
            connection.execute(
                event_log.insert().values(
                    event_id=uuid.uuid4(),
                    run_id=None,
                    project_id=plan_project_id,
                    sequence=1,
                    event_type="project.archived",
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
            project_columns = {column["name"] for column in inspector.get_columns("project")}
            assert project_columns == {"project_id", "created_at"}
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
                select(project.c.name).where(project.c.project_id == plan_project_id)
            ).scalar_one() == "Latest plan"
            assert connection.execute(
                select(project.c.name).where(project.c.project_id == planless_project_id)
            ).scalar_one() == "Untitled project"
        finally:
            transaction.rollback()
            connection.close()
    finally:
        command.upgrade(cfg, "head")
        connection = engine.connect()
        transaction = connection.begin()
        try:
            delete_project_data(connection, plan_project_id)
            delete_project_data(connection, planless_project_id)
            transaction.commit()
        finally:
            connection.close()
