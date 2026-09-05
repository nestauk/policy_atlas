"""Task lifecycle service tests."""

import uuid

import pytest
from sqlalchemy import select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas.api.lifecycle import archive_task, rename_task
from policy_atlas.core import events
from policy_atlas.core.schema import task
from tests.helpers import now


def _seed_task(conn: Connection, *, name: str = "Original name") -> uuid.UUID:
    """Insert one active task suitable for lifecycle operations."""
    task_id = uuid.uuid4()
    timestamp = now()
    conn.execute(
        task.insert().values(
            task_id=task_id,
            created_at=timestamp,
            name=name,
            question=None,
            status="active",
            updated_at=timestamp,
            archived_at=None,
            owner_user_id=None,
        )
    )
    return task_id


def test_rename_is_transactional_with_its_audit_event(conn: Connection) -> None:
    """A rollback removes both the renamed value and its event."""
    task_id = _seed_task(conn)
    savepoint = conn.begin_nested()
    rename_task(conn, task_id, "Renamed", "user-1")
    assert conn.execute(
        select(task.c.name).where(task.c.task_id == task_id)
    ).scalar_one() == "Renamed"
    assert [event["event_type"] for event in events.read(conn, task_id)] == ["task.renamed"]

    savepoint.rollback()
    assert conn.execute(
        select(task.c.name).where(task.c.task_id == task_id)
    ).scalar_one() == "Original name"
    assert events.read(conn, task_id) == []


def test_archive_is_idempotent_and_honors_paired_columns(conn: Connection) -> None:
    """Archiving twice yields one event and an archived timestamp only when archived."""
    task_id = _seed_task(conn)

    assert archive_task(conn, task_id, "user-1") is True
    assert archive_task(conn, task_id, "user-1") is False

    row = conn.execute(
        select(task.c.status, task.c.archived_at).where(task.c.task_id == task_id)
    ).one()
    assert row.status == "archived"
    assert row.archived_at is not None
    assert [event["event_type"] for event in events.read(conn, task_id)] == ["task.archived"]

    savepoint = conn.begin_nested()
    with pytest.raises(IntegrityError, match="ck_task_archived_at"):
        conn.execute(
            update(task)
            .where(task.c.task_id == task_id)
            .values(status="active", archived_at=row.archived_at)
        )
    savepoint.rollback()


@pytest.mark.parametrize("operation", ["rename", "archive"])
def test_unknown_task_raises_lookup_error(conn: Connection, operation: str) -> None:
    """Lifecycle services expose missing task identity as ``LookupError``."""
    unknown_task_id = uuid.uuid4()
    with pytest.raises(LookupError):
        if operation == "rename":
            rename_task(conn, unknown_task_id, "Renamed", "user-1")
        else:
            archive_task(conn, unknown_task_id, "user-1")
