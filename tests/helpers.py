"""Shared test helpers — not fixtures, plain functions."""

import uuid
from datetime import UTC, datetime
from typing import Any

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
        characterisation_result,
        chunk_embedding,
        event_log,
        evidence_scope,
        project,
        project_source_snapshot,
        runs,
        search_coverage_record,
        selection_result,
        source_appraisal_result,
        source_classification_result,
        source_screening_result,
        source_snapshot,
        source_tag,
    )
    from policy_atlas.schema import (
        chunk as chunk_table,
    )
    from policy_atlas.schema import (
        citation as citation_table,
    )

    # Capture snapshot IDs associated with this project before any deletes.
    # Union of envelope + full-text snapshot ids (plan-review finding 5:
    # full-text snapshots are project-less rows reachable only through the
    # link; capturing only the envelope id orphans them).
    snapshot_ids_set: set[uuid.UUID] = set()
    for env_id, ft_id in conn.execute(
        select(
            project_source_snapshot.c.source_snapshot_id,
            project_source_snapshot.c.full_text_snapshot_id,
        ).where(project_source_snapshot.c.project_id == project_id)
    ).fetchall():
        snapshot_ids_set.add(env_id)
        if ft_id is not None:
            snapshot_ids_set.add(ft_id)
    snapshot_ids = list(snapshot_ids_set)

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
    # Task 009 rows first: tags/characterisation FK onto pss/runs; embeddings FK onto chunk
    conn.execute(delete(source_tag).where(source_tag.c.project_id == project_id))
    # Task 010 row: same FK class as characterisation_result (scope + runs guards).
    conn.execute(delete(selection_result).where(
        selection_result.c.project_id == project_id
    ))
    conn.execute(delete(characterisation_result).where(
        characterisation_result.c.project_id == project_id
    ))
    # source_appraisal_result → source_classification_result → source_screening_result
    # (FK-safe order)
    conn.execute(delete(source_appraisal_result).where(
        source_appraisal_result.c.project_id == project_id
    ))
    conn.execute(delete(source_classification_result).where(
        source_classification_result.c.project_id == project_id
    ))
    conn.execute(delete(source_screening_result).where(
        source_screening_result.c.project_id == project_id
    ))
    conn.execute(delete(search_coverage_record).where(
        search_coverage_record.c.project_id == project_id
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
    # project_source_snapshot before runs: acquired links carry run_id (FK to runs);
    # upload links carry run_id=NULL, which is why the old runs-first order never bit.
    conn.execute(delete(project_source_snapshot).where(
        project_source_snapshot.c.project_id == project_id
    ))
    conn.execute(delete(runs).where(runs.c.project_id == project_id))
    if snapshot_ids:
        conn.execute(delete(chunk_embedding).where(
            chunk_embedding.c.chunk_id.in_(
                select(chunk_table.c.chunk_id).where(
                    chunk_table.c.source_snapshot_id.in_(snapshot_ids)
                )
            )
        ))
        conn.execute(delete(chunk_table).where(
            chunk_table.c.source_snapshot_id.in_(snapshot_ids)
        ))
        conn.execute(delete(source_snapshot).where(
            source_snapshot.c.source_snapshot_id.in_(snapshot_ids)
        ))
    conn.execute(delete(evidence_scope).where(evidence_scope.c.project_id == project_id))
    conn.execute(delete(project).where(project.c.project_id == project_id))


def seed_source(
    conn: Connection, project_id: uuid.UUID, meta: dict[str, Any] | None = None
) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert source_snapshot + project_source_snapshot; return (source_snapshot_id, pss_id)."""
    from policy_atlas.schema import project_source_snapshot, source_snapshot

    snap_id = uuid.uuid4()
    pss_id = uuid.uuid4()
    conn.execute(source_snapshot.insert().values(
        source_snapshot_id=snap_id,
        content_hash=str(uuid.uuid4()),
        text_basis="full_text",
        source_locator="test.pdf",
        metadata=meta or {},
        created_at=now(),
    ))
    conn.execute(project_source_snapshot.insert().values(
        project_source_snapshot_id=pss_id,
        project_id=project_id,
        source_snapshot_id=snap_id,
        origin="uploaded",
        run_id=None,
        ingested_at=now(),
    ))
    return snap_id, pss_id


def seed_scope(
    conn: Connection, project_id: uuid.UUID, context: dict[str, Any] | None = None
) -> uuid.UUID:
    """Insert a evidence_scope; return scope_id."""
    from policy_atlas.schema import evidence_scope

    scope_id = uuid.uuid4()
    conn.execute(evidence_scope.insert().values(
        evidence_scope_id=scope_id,
        project_id=project_id,
        intent="Test intent",
        context=context or {},
        created_at=now(),
    ))
    return scope_id


def seed_screening_result(
    conn: Connection,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    pss_id: uuid.UUID,
    status: str = "relevant",
) -> None:
    """Insert a source_screening_result row."""
    from policy_atlas.schema import source_screening_result

    if status == "failed":
        basis = None
        confidence = None
    else:
        basis = "title_abstract"
        confidence = 0.9 if status == "relevant" else 0.95
    conn.execute(source_screening_result.insert().values(
        source_screening_result_id=uuid.uuid4(),
        evidence_scope_id=scope_id,
        project_source_snapshot_id=pss_id,
        project_id=project_id,
        screened_by_run_id=run_id,
        status=status,
        screen_basis=basis,
        screen_decision_confidence=confidence,
        screened_at=now(),
    ))


def seed_project_and_run(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert a project + running run; return (project_id, run_id)."""
    from policy_atlas.schema import project

    pid = uuid.uuid4()
    conn.execute(project.insert().values(project_id=pid, created_at=now()))
    return pid, seed_run(conn, pid)


def seed_run(conn: Connection, project_id: uuid.UUID) -> uuid.UUID:
    """Insert an additional running run for an existing project; return run_id."""
    from policy_atlas.schema import runs

    rid = uuid.uuid4()
    conn.execute(
        runs.insert().values(
            run_id=rid, project_id=project_id, status="running", started_at=now()
        )
    )
    return rid
