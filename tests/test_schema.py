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
    runs,
)
from tests.helpers import now


def test_all_seven_tables_exist(conn: Connection) -> None:
    inspector = inspect(conn)
    tables = set(inspector.get_table_names())
    expected = {"project", "artefact", "block", "addressable_unit", "annotation", "runs", "event_log"}  # noqa: E501
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
            payload={"source_ref": "x", "quote": "q", "verification_result": "pass"},
            created_at=now(),
        ))
