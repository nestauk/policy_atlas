"""ingest_upload — round-trip rows, no-dedup, schema shape."""

import uuid

from sqlalchemy import inspect, select
from sqlalchemy.engine import Connection

from policy_atlas.ingest import ingest_upload
from policy_atlas.schema import chunk as chunk_table
from policy_atlas.schema import project, project_source_snapshot, source_snapshot
from tests.helpers import now

_CHUNKS = [
    "Synthetic Policy Atlas test source. ",
    "Evidence suggests that structured provenance tracking improves "
    "audit trail quality in policy research systems.",
]


def _seed_project(conn: Connection) -> uuid.UUID:
    pid = uuid.uuid4()
    conn.execute(project.insert().values(project_id=pid, created_at=now()))
    return pid


def test_ingest_upload_creates_expected_rows(conn: Connection) -> None:
    pid = _seed_project(conn)
    snapshot_id = ingest_upload(
        conn,
        project_id=pid,
        chunks=_CHUNKS,
        source_locator="test-doc.pdf",
        metadata={"title": "Test"},
        text_basis="full_text",
    )

    # source_snapshot row
    row = conn.execute(
        select(source_snapshot).where(source_snapshot.c.source_snapshot_id == snapshot_id)
    ).one()
    assert row.text_basis == "full_text"
    assert row.source_locator == "test-doc.pdf"

    # chunk rows: correct count, segmentation_policy, sequence order
    chunks = conn.execute(
        select(chunk_table)
        .where(chunk_table.c.source_snapshot_id == snapshot_id)
        .order_by(chunk_table.c.sequence)
    ).fetchall()
    assert len(chunks) == 2
    assert chunks[0].sequence == 1
    assert chunks[1].sequence == 2
    assert all(c.segmentation_policy == "manual_v1" for c in chunks)

    # membership row
    mem = conn.execute(
        select(project_source_snapshot).where(
            project_source_snapshot.c.source_snapshot_id == snapshot_id
        )
    ).one()
    assert mem.project_id == pid
    assert mem.origin == "uploaded"
    assert mem.run_id is None


def test_ingest_upload_no_dedup(conn: Connection) -> None:
    """Two calls with identical content produce two distinct snapshots."""
    pid = _seed_project(conn)

    id_a = ingest_upload(
        conn,
        project_id=pid,
        chunks=_CHUNKS,
        source_locator="same.pdf",
        metadata={},
        text_basis="full_text",
    )
    id_b = ingest_upload(
        conn,
        project_id=pid,
        chunks=_CHUNKS,
        source_locator="same.pdf",
        metadata={},
        text_basis="full_text",
    )
    assert id_a != id_b


def test_source_snapshot_has_no_project_id_column(conn: Connection) -> None:
    """source_snapshot identity is content, not project — no project_id column."""
    inspector = inspect(conn)
    col_names = {c["name"] for c in inspector.get_columns("source_snapshot")}
    assert "project_id" not in col_names
