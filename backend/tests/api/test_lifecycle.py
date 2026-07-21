"""Project lifecycle service tests."""

import uuid

import pytest
from sqlalchemy import select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas.api.lifecycle import archive_project, rename_project
from policy_atlas.core import events
from policy_atlas.core.schema import project
from tests.helpers import now


def _seed_project(conn: Connection, *, name: str = "Original name") -> uuid.UUID:
    """Insert one active project suitable for lifecycle operations."""
    project_id = uuid.uuid4()
    timestamp = now()
    conn.execute(
        project.insert().values(
            project_id=project_id,
            created_at=timestamp,
            name=name,
            question=None,
            status="active",
            updated_at=timestamp,
            archived_at=None,
            owner_user_id=None,
        )
    )
    return project_id


def test_rename_is_transactional_with_its_audit_event(conn: Connection) -> None:
    """A rollback removes both the renamed value and its event."""
    project_id = _seed_project(conn)
    savepoint = conn.begin_nested()
    rename_project(conn, project_id, "Renamed", "user-1")
    assert conn.execute(
        select(project.c.name).where(project.c.project_id == project_id)
    ).scalar_one() == "Renamed"
    assert [event["event_type"] for event in events.read(conn, project_id)] == ["project.renamed"]

    savepoint.rollback()
    assert conn.execute(
        select(project.c.name).where(project.c.project_id == project_id)
    ).scalar_one() == "Original name"
    assert events.read(conn, project_id) == []


def test_archive_is_idempotent_and_honors_paired_columns(conn: Connection) -> None:
    """Archiving twice yields one event and an archived timestamp only when archived."""
    project_id = _seed_project(conn)

    assert archive_project(conn, project_id, "user-1") is True
    assert archive_project(conn, project_id, "user-1") is False

    row = conn.execute(
        select(project.c.status, project.c.archived_at).where(project.c.project_id == project_id)
    ).one()
    assert row.status == "archived"
    assert row.archived_at is not None
    assert [event["event_type"] for event in events.read(conn, project_id)] == ["project.archived"]

    savepoint = conn.begin_nested()
    with pytest.raises(IntegrityError, match="ck_project_archived_at"):
        conn.execute(
            update(project)
            .where(project.c.project_id == project_id)
            .values(status="active", archived_at=row.archived_at)
        )
    savepoint.rollback()


@pytest.mark.parametrize("operation", ["rename", "archive"])
def test_unknown_project_raises_lookup_error(conn: Connection, operation: str) -> None:
    """Lifecycle services expose missing project identity as ``LookupError``."""
    unknown_project_id = uuid.uuid4()
    with pytest.raises(LookupError):
        if operation == "rename":
            rename_project(conn, unknown_project_id, "Renamed", "user-1")
        else:
            archive_project(conn, unknown_project_id, "user-1")
