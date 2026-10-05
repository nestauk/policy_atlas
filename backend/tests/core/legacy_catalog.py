"""Pre-038 catalog access for the historical migration round-trips (plan D9).

Revision ``c1a7f4e9b0d2`` renames the Task entity in the catalog: table
``project`` becomes ``task``, ``project_source_snapshot`` becomes
``task_source_snapshot``, ``orchestration_plan`` becomes ``plan`` and every
``project_id`` becomes ``task_id``. One SQLAlchemy ``Table`` object cannot name
both generations, and ``policy_atlas.core.schema`` names only the new one, so
the historical migration tests reach a *downgraded* catalog by reflection
instead — :func:`legacy_table` returns whatever shape the chain currently has.

Scope: only the seeds and reads that run BELOW revision ``c1a7f4e9b0d2`` use
this module. At head those tests keep using ``core.schema`` and
``tests.helpers`` unchanged, so nothing here duplicates the head-side seeds.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import MetaData, Table, inspect
from sqlalchemy.engine import Connection

from tests.helpers import now


def legacy_table(conn: Connection, name: str) -> Table:
    """Reflect one table from the live catalog under its pre-038 name.

    Args:
        conn: Connection open on a database downgraded below ``c1a7f4e9b0d2``.
        name: Table name as the pre-038 catalog spells it (``project``,
            ``project_source_snapshot``, ``orchestration_plan``, ...).

    Returns:
        A ``Table`` reflecting the live columns, in a private ``MetaData`` so it
        never collides with ``policy_atlas.core.schema.metadata``.
    """
    return Table(name, MetaData(), autoload_with=conn)


def seed_legacy_task_and_run(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert a Task (pre-038 table ``project``) plus a running run.

    Revision-aware in the same way as ``tests.helpers.seed_task_and_run``: the
    025 lifecycle columns are supplied only when the downgraded table carries
    them.

    Args:
        conn: Connection open below revision ``c1a7f4e9b0d2``.

    Returns:
        ``(project_id, run_id)`` — the Task id under its pre-038 column name.
    """
    project = legacy_table(conn, "project")
    project_id = uuid.uuid4()
    values: dict[str, Any] = {"project_id": project_id, "created_at": now()}
    live_columns = {column["name"] for column in inspect(conn).get_columns("project")}
    if "name" in live_columns:
        values.update(name="Test task", status="active", updated_at=now())
    conn.execute(project.insert().values(**values))
    return project_id, seed_legacy_run(conn, project_id)


def seed_legacy_run(conn: Connection, project_id: uuid.UUID) -> uuid.UUID:
    """Insert one running run for an existing pre-038 Task; return its run id."""
    runs = legacy_table(conn, "runs")
    run_id = uuid.uuid4()
    conn.execute(
        runs.insert().values(
            run_id=run_id, project_id=project_id, status="running", started_at=now()
        )
    )
    return run_id


def seed_legacy_scope(
    conn: Connection, project_id: uuid.UUID, context: dict[str, Any] | None = None
) -> uuid.UUID:
    """Insert an ``evidence_scope`` under the pre-038 column names; return its id."""
    evidence_scope = legacy_table(conn, "evidence_scope")
    scope_id = uuid.uuid4()
    conn.execute(
        evidence_scope.insert().values(
            evidence_scope_id=scope_id,
            project_id=project_id,
            intent="Test intent",
            context=context or {},
            created_at=now(),
        )
    )
    return scope_id


def seed_legacy_source(
    conn: Connection, project_id: uuid.UUID, meta: dict[str, Any] | None = None
) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert ``source_snapshot`` + ``project_source_snapshot``.

    Args:
        conn: Connection open below revision ``c1a7f4e9b0d2``.
        project_id: Task the snapshot belongs to.
        meta: Optional source metadata document.

    Returns:
        ``(source_snapshot_id, project_source_snapshot_id)``.
    """
    source_snapshot = legacy_table(conn, "source_snapshot")
    project_source_snapshot = legacy_table(conn, "project_source_snapshot")
    snapshot_id = uuid.uuid4()
    pss_id = uuid.uuid4()
    conn.execute(
        source_snapshot.insert().values(
            source_snapshot_id=snapshot_id,
            content_hash=str(uuid.uuid4()),
            text_basis="full_text",
            source_locator="test.pdf",
            metadata=meta or {},
            created_at=now(),
        )
    )
    conn.execute(
        project_source_snapshot.insert().values(
            project_source_snapshot_id=pss_id,
            project_id=project_id,
            source_snapshot_id=snapshot_id,
            origin="uploaded",
            run_id=None,
            ingested_at=now(),
        )
    )
    return snapshot_id, pss_id
