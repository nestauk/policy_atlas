"""Schema validation — tables, columns, constraints."""

import uuid

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas.schema import (
    annotation,
    artefact,
    block,
    event_log,
    project,
    project_source_snapshot,
    runs,
    source_snapshot,
)
from policy_atlas.schema import (
    chunk as chunk_table,
)
from policy_atlas.schema import (
    citation as citation_table,
)
from tests.helpers import now


def test_all_thirteen_tables_exist(conn: Connection) -> None:
    inspector = inspect(conn)
    tables = set(inspector.get_table_names())
    expected = {
        "project", "artefact", "block", "addressable_unit", "annotation", "runs", "event_log",
        "source_snapshot", "project_source_snapshot", "chunk", "citation",
        "screening_scope", "source_screening_result",
    }
    assert expected <= tables


def test_event_log_unique_project_sequence(conn: Connection) -> None:
    pid = uuid.uuid4()
    rid = uuid.uuid4()
    conn.execute(project.insert().values(project_id=pid, created_at=now()))
    conn.execute(runs.insert().values(
        run_id=rid, project_id=pid, status="running", started_at=now()
    ))

    conn.execute(event_log.insert().values(
        event_id=uuid.uuid4(), run_id=rid, project_id=pid,
        sequence=1, event_type="run.started", occurred_at=now(), payload={},
    ))
    with pytest.raises(Exception, match="uq_event_log_project_sequence"):
        conn.execute(event_log.insert().values(
            event_id=uuid.uuid4(), run_id=rid, project_id=pid,
            sequence=1, event_type="duplicate", occurred_at=now(), payload={},
        ))


def test_addressable_unit_unique_block_unit_constraint_exists(conn: Connection) -> None:
    """uq_addressable_unit_block_unit backs the annotation composite FK — verify it's present.

    (block_id, unit_id) can't be violated independently of the PK since unit_id is already
    the PK; the constraint's purpose is to enable the annotation composite FK reference.)
    """
    inspector = inspect(conn)
    unique_names = {
        uc["name"] for uc in inspector.get_unique_constraints("addressable_unit")
    }
    assert "uq_addressable_unit_block_unit" in unique_names


def test_block_version_defaults_to_one(conn: Connection) -> None:
    """block.version has a DB server_default of 1 — an insert omitting it still gets 1."""
    pid = uuid.uuid4()
    aid = uuid.uuid4()
    bid = uuid.uuid4()
    conn.execute(project.insert().values(project_id=pid, created_at=now()))
    conn.execute(artefact.insert().values(
        artefact_id=aid, project_id=pid, title="t", created_at=now()
    ))
    conn.execute(block.insert().values(
        block_id=bid, artefact_id=aid, content="c", content_hash="h", created_at=now(),
    ))  # version intentionally omitted
    version = conn.execute(select(block.c.version).where(block.c.block_id == bid)).scalar_one()
    assert version == 1


def test_annotation_composite_fk_rejects_mismatch(conn: Connection) -> None:
    """annotation(block_id, unit_id) must match an existing addressable_unit row."""
    pid = uuid.uuid4()
    aid = uuid.uuid4()
    bid = uuid.uuid4()
    conn.execute(project.insert().values(project_id=pid, created_at=now()))
    conn.execute(artefact.insert().values(
        artefact_id=aid, project_id=pid, title="t", created_at=now()
    ))
    conn.execute(block.insert().values(
        block_id=bid, artefact_id=aid, version=1,
        content="c", content_hash="h", created_at=now(),
    ))
    # unit_id that does NOT exist in addressable_unit
    phantom_unit_id = uuid.uuid4()
    with pytest.raises(IntegrityError):
        conn.execute(annotation.insert().values(
            annotation_id=uuid.uuid4(),
            block_id=bid,
            unit_id=phantom_unit_id,
            annotation_type="citation",
            payload={"quote": "q", "verification_result": "pass"},
            created_at=now(),
        ))


def _seed_snapshot(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    """Return (source_snapshot_id, chunk_id) for a single-chunk snapshot."""
    sid = uuid.uuid4()
    cid = uuid.uuid4()
    conn.execute(source_snapshot.insert().values(
        source_snapshot_id=sid,
        content_hash="h",
        text_basis="full_text",
        source_locator="test.pdf",
        metadata={},
        created_at=now(),
    ))
    conn.execute(chunk_table.insert().values(
        chunk_id=cid,
        source_snapshot_id=sid,
        sequence=1,
        content="test content",
        content_hash="ch",
        locator={"sequence": 1},
        segmentation_policy="manual_v1",
        created_at=now(),
    ))
    return sid, cid


def test_citation_chunk_fk_fails_with_phantom_chunk_id(conn: Connection) -> None:
    """citation.chunk_id must reference an existing chunk row."""
    pid = uuid.uuid4()
    aid = uuid.uuid4()
    bid = uuid.uuid4()
    uid = uuid.uuid4()
    conn.execute(project.insert().values(project_id=pid, created_at=now()))
    conn.execute(artefact.insert().values(
        artefact_id=aid, project_id=pid, title="t", created_at=now()
    ))
    conn.execute(block.insert().values(
        block_id=bid, artefact_id=aid, version=1,
        content="c", content_hash="h", created_at=now(),
    ))
    from policy_atlas.schema import addressable_unit
    conn.execute(addressable_unit.insert().values(
        unit_id=uid, block_id=bid, unit_type="text_span",
        locator={"start": 0, "end": 1}, content="c", created_at=now(),
    ))
    ann_id = uuid.uuid4()
    conn.execute(annotation.insert().values(
        annotation_id=ann_id, block_id=bid, unit_id=uid,
        annotation_type="citation",
        payload={"quote": "q", "verification_result": "pass"},
        created_at=now(),
    ))
    with pytest.raises(IntegrityError):
        conn.execute(citation_table.insert().values(
            citation_id=uuid.uuid4(),
            annotation_id=ann_id,
            chunk_id=uuid.uuid4(),   # phantom — does not exist
            quote="q",
            verification_result="pass",
            created_at=now(),
        ))


def test_chunk_unique_snapshot_sequence_constraint(conn: Connection) -> None:
    """(source_snapshot_id, sequence) must be unique within a snapshot."""
    sid, _ = _seed_snapshot(conn)
    with pytest.raises(Exception, match="uq_chunk_snapshot_sequence"):
        conn.execute(chunk_table.insert().values(
            chunk_id=uuid.uuid4(),
            source_snapshot_id=sid,
            sequence=1,              # duplicate sequence for same snapshot
            content="other",
            content_hash="other_h",
            locator={"sequence": 1},
            segmentation_policy="manual_v1",
            created_at=now(),
        ))


def test_project_source_snapshot_unique_constraint(conn: Connection) -> None:
    """(project_id, source_snapshot_id) must be unique in project_source_snapshot."""
    pid = uuid.uuid4()
    sid, _ = _seed_snapshot(conn)
    conn.execute(project.insert().values(project_id=pid, created_at=now()))
    conn.execute(project_source_snapshot.insert().values(
        project_source_snapshot_id=uuid.uuid4(), project_id=pid, source_snapshot_id=sid,
        origin="uploaded", run_id=None, ingested_at=now(),
    ))
    with pytest.raises(Exception, match="uq_project_source_snapshot"):
        conn.execute(project_source_snapshot.insert().values(
            project_source_snapshot_id=uuid.uuid4(), project_id=pid, source_snapshot_id=sid,
            origin="uploaded", run_id=None, ingested_at=now(),
        ))
