"""Shared test helpers — not fixtures, plain functions."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.engine import Connection


def now() -> datetime:
    return datetime.now(UTC)


def delete_project_data(conn: Connection, project_id: uuid.UUID) -> None:
    """Delete every row belonging to a project, FK-ordered.

    Used by tests that must genuinely commit (e.g. commit-survival) and then clean up,
    since the rolled-back ``conn`` fixture can't isolate committed rows.

    Args:
        conn: Open database connection.
        project_id: Project whose rows to remove.
    """
    from policy_atlas.schema import (
        addressable_unit,
        annotation,
        artefact,
        block,
        event_log,
        project,
        project_source_snapshot,
        runs,
        screening_scope,
        source_classification_result,
        source_screening_result,
        source_snapshot,
    )
    from policy_atlas.schema import (
        chunk as chunk_table,
    )
    from policy_atlas.schema import (
        citation as citation_table,
    )

    # Capture snapshot IDs associated with this project before any deletes
    snapshot_ids = [
        row[0] for row in conn.execute(
            select(project_source_snapshot.c.source_snapshot_id)
            .where(project_source_snapshot.c.project_id == project_id)
        ).fetchall()
    ]

    block_ids_subq = select(block.c.block_id).where(
        block.c.artefact_id.in_(
            select(artefact.c.artefact_id).where(artefact.c.project_id == project_id)
        )
    )
    annotation_ids_subq = select(annotation.c.annotation_id).where(
        annotation.c.block_id.in_(block_ids_subq)
    )

    # citation → annotation → addressable_unit → block (then event_log, artefact, runs)
    conn.execute(delete(citation_table).where(
        citation_table.c.annotation_id.in_(annotation_ids_subq)
    ))
    conn.execute(delete(annotation).where(annotation.c.block_id.in_(block_ids_subq)))
    conn.execute(delete(addressable_unit).where(addressable_unit.c.block_id.in_(block_ids_subq)))
    # source_classification_result before source_screening_result (FK-safe order)
    conn.execute(delete(source_classification_result).where(
        source_classification_result.c.project_id == project_id
    ))
    conn.execute(delete(source_screening_result).where(
        source_screening_result.c.project_id == project_id
    ))
    conn.execute(delete(event_log).where(event_log.c.project_id == project_id))
    conn.execute(
        delete(block).where(
            block.c.artefact_id.in_(
                select(artefact.c.artefact_id).where(artefact.c.project_id == project_id)
            )
        )
    )
    conn.execute(delete(artefact).where(artefact.c.project_id == project_id))
    conn.execute(delete(runs).where(runs.c.project_id == project_id))
    conn.execute(delete(project_source_snapshot).where(
        project_source_snapshot.c.project_id == project_id
    ))
    if snapshot_ids:
        conn.execute(delete(chunk_table).where(
            chunk_table.c.source_snapshot_id.in_(snapshot_ids)
        ))
        conn.execute(delete(source_snapshot).where(
            source_snapshot.c.source_snapshot_id.in_(snapshot_ids)
        ))
    conn.execute(delete(screening_scope).where(screening_scope.c.project_id == project_id))
    conn.execute(delete(project).where(project.c.project_id == project_id))


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
