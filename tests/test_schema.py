"""Schema validation — tables, columns, constraints."""

import os
import re
import uuid
from typing import get_args

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from policy_atlas import iof_prompt
from policy_atlas.iof_records import EffectBasis
from policy_atlas.schema import (
    EFFECT_BASES,
    EVIDENCE_TYPES,
    METHODOLOGICAL_STRUCTURAL,
    annotation,
    artefact,
    block,
    event_log,
    project,
    project_source_snapshot,
    runs,
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
from policy_atlas.tags import insert_source_tags
from tests.helpers import now, seed_project_and_run, seed_scope, seed_source


def test_all_fourteen_tables_exist(conn: Connection) -> None:
    inspector = inspect(conn)
    tables = set(inspector.get_table_names())
    expected = {
        "project", "artefact", "block", "addressable_unit", "annotation", "runs", "event_log",
        "source_snapshot", "project_source_snapshot", "chunk", "citation",
        "evidence_scope", "source_screening_result", "source_classification_result",
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


def test_migration_roundtrip_screen_stage_and_classify_tags(engine: Engine) -> None:
    """``downgrade -1`` then ``upgrade head`` for e5c2a7f4b9d1 succeeds and restores
    all four changes.

    Runs on its own connection outside the rolled-back ``conn`` fixture transaction
    (the migration itself needs a connection it fully controls) and always leaves
    the session-scoped engine's database back at head — ``downgrade``/``upgrade``
    run back-to-back with no test logic in between, and each migration step is
    itself one transaction, so a failure there leaves the DB at its prior revision
    rather than stuck mid-migration.
    """
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

    command.downgrade(cfg, "-1")
    command.upgrade(cfg, "head")

    with engine.connect() as verify_conn:
        trans = verify_conn.begin()
        try:
            inspector = inspect(verify_conn)
            cols = {c["name"] for c in inspector.get_columns("source_screening_result")}
            assert "screen_stage" in cols

            pid, rid = seed_project_and_run(verify_conn)
            scope_id = seed_scope(verify_conn, pid)
            _, pss_id = seed_source(verify_conn, pid)

            # ck_ssr_basis admits 'full_text' (a stage-2 row).
            verify_conn.execute(source_screening_result.insert().values(
                source_screening_result_id=uuid.uuid4(),
                evidence_scope_id=scope_id,
                project_source_snapshot_id=pss_id,
                project_id=pid,
                screened_by_run_id=rid,
                status="relevant",
                screen_basis="full_text",
                screen_decision_confidence=0.9,
                screen_stage=2,
                screened_at=now(),
            ))

            # uq_ssr_scope_source_stage: a second non-failed stage-2 row for the
            # same (scope, source) conflicts with the one above.
            with pytest.raises(IntegrityError), verify_conn.begin_nested():
                verify_conn.execute(source_screening_result.insert().values(
                    source_screening_result_id=uuid.uuid4(),
                    evidence_scope_id=scope_id,
                    project_source_snapshot_id=pss_id,
                    project_id=pid,
                    screened_by_run_id=rid,
                    status="not_relevant",
                    screen_basis="full_text",
                    screen_decision_confidence=0.8,
                    screen_stage=2,
                    screened_at=now(),
                ))

            # ... but a failed row at the same stage never conflicts with it.
            verify_conn.execute(source_screening_result.insert().values(
                source_screening_result_id=uuid.uuid4(),
                evidence_scope_id=scope_id,
                project_source_snapshot_id=pss_id,
                project_id=pid,
                screened_by_run_id=rid,
                status="failed",
                screen_basis=None,
                screen_decision_confidence=None,
                screen_stage=2,
                screened_at=now(),
            ))

            # ck_stag_tag_type admits 'methodological_structural'.
            insert_source_tags(
                verify_conn,
                project_id=pid,
                run_id=rid,
                now=now(),
                assertions=[(pss_id, "rct", "test")],
                tag_type=METHODOLOGICAL_STRUCTURAL,
            )
            tag_row = verify_conn.execute(
                select(source_tag.c.tag_type).where(
                    source_tag.c.project_source_snapshot_id == pss_id
                )
            ).one()
            assert tag_row.tag_type == METHODOLOGICAL_STRUCTURAL
        finally:
            trans.rollback()


# --- CHECK-vocabulary agreement (task 020) ---------------------------------


def _check_constraint_allowed_values(conn: Connection, constraint_name: str) -> set[str]:
    """Read a live CHECK's ``= ANY (ARRAY[...])`` string vocabulary from Postgres.

    Args:
        conn: Open database connection.
        constraint_name: The CHECK constraint's name.

    Returns:
        The set of string literals the constraint's ``ARRAY[...]`` admits.
    """
    definition = conn.execute(
        text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = :name"),
        {"name": constraint_name},
    ).scalar_one()
    return set(re.findall(r"'([^']*)'::text", definition))


def test_ck_ser_evidence_type_matches_schema_and_prompt_vocabulary(conn: Connection) -> None:
    """ck_ser_evidence_type's live allowed set is exactly EVIDENCE_TYPES plus the
    prompt's UNCLASSIFIED_EVIDENCE_TYPE sentinel — the two modules deliberately
    never import each other (schema.py keeps the literal in sync by comment),
    so this test is the drift guard."""
    allowed = _check_constraint_allowed_values(conn, "ck_ser_evidence_type")
    assert allowed == {*EVIDENCE_TYPES, iof_prompt.UNCLASSIFIED_EVIDENCE_TYPE}


def test_ck_iof_effect_basis_matches_effect_bases(conn: Connection) -> None:
    """ck_iof_effect_basis's live allowed set is exactly schema.EFFECT_BASES."""
    allowed = _check_constraint_allowed_values(conn, "ck_iof_effect_basis")
    assert allowed == set(EFFECT_BASES)


def test_effect_basis_literal_matches_effect_bases() -> None:
    """The wire/stored EffectBasis Literal agrees with schema.EFFECT_BASES —
    also asserted at iof_records import time; restated here as an
    explicit, independently discoverable test (not just a collection-time
    side effect)."""
    assert get_args(EffectBasis) == EFFECT_BASES
