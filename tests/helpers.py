"""Shared test helpers — not fixtures, plain functions."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.engine import Connection


def now() -> datetime:
    return datetime.now(UTC)


def seed_project_and_run(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert a project + running run; return (project_id, run_id)."""
    from policy_atlas.schema import project, runs

    pid = uuid.uuid4()
    rid = uuid.uuid4()
    conn.execute(project.insert().values(project_id=pid, created_at=now()))
    conn.execute(
        runs.insert().values(run_id=rid, project_id=pid, status="running", started_at=now())
    )
    return pid, rid
