"""Migration roundtrip for 0f4e2d8c9b1a (extract schema v2 columns).

Runs against the real Alembic migration chain, on the same test database as
the ``conn`` fixture (task 018 rider A5 precedent, mirrored from
test_effect_direction_migration.py / test_screen_step_rename_migration.py).
This migration is additive-only — no backfill (task 020 data-model rule): a
v1-shaped finding row and extraction record, seeded before the upgrade, must
survive untouched with their new columns NULL. Downgrade drops the new
columns/CHECKs cleanly and re-upgrade restores them.

Same coupling as the other migration tests: no row-holding transaction may be
open while alembic runs DDL on a second connection, so seeding happens
strictly after the DDL step it accompanies and every seed transaction is
rolled back (or committed-then-cleaned-up) before the next DDL step.
"""

import uuid

import pytest
from alembic import command
from sqlalchemy import inspect, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.schema import (
    intervention_outcome_finding,
    source_extraction_record,
    source_snapshot,
)
from tests.conftest import _alembic_cfg
from tests.core.legacy_catalog import legacy_table, seed_legacy_task_and_run
from tests.helpers import delete_task_data, now

# The revision below 0f4e2d8c9b1a (the task-020 v2 columns) — the pre-migration
# state this test exercises.
PRE_MIGRATION_REVISION = "b7f3d9a2c5e1"


def _seed_v1_finding(
    connection: Connection, *, task_id: uuid.UUID, run_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed the FK chain (abstract-basis doc -> extraction record -> finding).

    Values are deliberately v1-shaped: the new ``study_geography``,
    ``effect_basis`` and ``primary_evidence_type`` columns are never passed to
    ``.values()``, so the generated INSERT never references them and this
    seed works identically pre- and post-migration.

    Runs only BELOW revision c1a7f4e9b0d2, where the catalog still says
    ``project_id`` / ``project_source_snapshot`` — so the three renamed tables
    are reflected rather than taken from ``core.schema`` (plan D9).

    Args:
        connection: Open connection on the pre-migration revision.
        task_id: Task the chain hangs off (stored in ``project_id`` there).
        run_id: Run that produced the extraction record.

    Returns:
        ``(extraction_record_id, finding_id)``.
    """
    envelope_snap = uuid.uuid4()
    tss_id = uuid.uuid4()
    extraction_record_id = uuid.uuid4()
    finding_id = uuid.uuid4()
    snapshots = legacy_table(connection, "project_source_snapshot")
    records = legacy_table(connection, "source_extraction_record")
    findings = legacy_table(connection, "intervention_outcome_finding")

    connection.execute(
        source_snapshot.insert().values(
            source_snapshot_id=envelope_snap,
            content_hash=str(uuid.uuid4()),
            text_basis="abstract_only",
            source_locator="https://example.org/v2-migration-test",
            metadata={"title": "V1 shaped doc", "abstract": "Abstract."},
            created_at=now(),
        )
    )
    connection.execute(
        snapshots.insert().values(
            project_source_snapshot_id=tss_id,
            project_id=task_id,
            source_snapshot_id=envelope_snap,
            origin="acquired",
            run_id=None,
            ingested_at=now(),
        )
    )
    connection.execute(
        records.insert().values(
            extraction_record_id=extraction_record_id,
            project_id=task_id,
            source_snapshot_id=envelope_snap,
            project_source_snapshot_id=tss_id,
            extraction_fingerprint="fp-v2-migration-test",
            status="extracted",
            basis="abstract_only",
            error=None,
            finding_count=1,
            run_id=run_id,
            created_at=now(),
        )
    )
    connection.execute(
        findings.insert().values(
            finding_id=finding_id,
            project_id=task_id,
            extraction_record_id=extraction_record_id,
            intervention="Coaching",
            outcome="Test scores",
            population=None,
            comparator=None,
            effect_direction="increase",
            estimate_level="study",
            study_design=None,
            stratum_qualifiers=[],
            statistics={},
            causality_by_design=None,
            is_primary=None,
            is_prevalence_only=None,
            field_coverage={},
            grounding=[],
            created_at=now(),
        )
    )
    return extraction_record_id, finding_id


def test_extract_schema_v2_migration_roundtrip(engine: Engine) -> None:
    """A v1-shaped row survives the upgrade untouched, with new columns NULL;
    the new CHECKs are live post-upgrade; downgrade drops the columns/CHECKs
    cleanly and re-upgrade restores them.
    """
    cfg = _alembic_cfg()
    command.downgrade(cfg, PRE_MIGRATION_REVISION)

    inspector = inspect(engine)
    finding_columns = {c["name"] for c in inspector.get_columns("intervention_outcome_finding")}
    record_columns = {c["name"] for c in inspector.get_columns("source_extraction_record")}
    assert "study_geography" not in finding_columns
    assert "effect_basis" not in finding_columns
    assert "primary_evidence_type" not in record_columns

    connection = engine.connect()
    trans = connection.begin()
    task_id, run_id = seed_legacy_task_and_run(connection)
    extraction_record_id, finding_id = _seed_v1_finding(
        connection, task_id=task_id, run_id=run_id
    )
    trans.commit()
    connection.close()

    try:
        command.upgrade(cfg, "head")

        inspector = inspect(engine)
        finding_columns = {
            c["name"] for c in inspector.get_columns("intervention_outcome_finding")
        }
        record_columns = {c["name"] for c in inspector.get_columns("source_extraction_record")}
        assert {"study_geography", "effect_basis"} <= finding_columns
        assert "primary_evidence_type" in record_columns

        connection = engine.connect()
        trans = connection.begin()
        try:
            finding_row = connection.execute(
                select(intervention_outcome_finding).where(
                    intervention_outcome_finding.c.finding_id == finding_id
                )
            ).one()
            # The v1-era fields are untouched.
            assert finding_row.intervention == "Coaching"
            assert finding_row.outcome == "Test scores"
            assert finding_row.effect_direction == "increase"
            # The new columns arrive NULL — no backfill (task 020 data-model rule).
            assert finding_row.study_geography is None
            assert finding_row.effect_basis is None

            record_row = connection.execute(
                select(source_extraction_record).where(
                    source_extraction_record.c.extraction_record_id == extraction_record_id
                )
            ).one()
            assert record_row.status == "extracted"
            assert record_row.basis == "abstract_only"
            assert record_row.primary_evidence_type is None

            # The new CHECKs are live: an invalid effect_basis is rejected...
            savepoint = connection.begin_nested()
            with pytest.raises(IntegrityError, match="ck_iof_effect_basis"):
                connection.execute(
                    intervention_outcome_finding.update()
                    .where(intervention_outcome_finding.c.finding_id == finding_id)
                    .values(effect_basis="guessed")
                )
            savepoint.rollback()

            # ...a valid one is accepted...
            connection.execute(
                intervention_outcome_finding.update()
                .where(intervention_outcome_finding.c.finding_id == finding_id)
                .values(effect_basis="observed", study_geography="United Kingdom")
            )

            # ...and the same holds for the evidence-type CHECK.
            savepoint = connection.begin_nested()
            with pytest.raises(IntegrityError, match="ck_ser_evidence_type"):
                connection.execute(
                    source_extraction_record.update()
                    .where(
                        source_extraction_record.c.extraction_record_id
                        == extraction_record_id
                    )
                    .values(primary_evidence_type="Not A Real Evidence Type")
                )
            savepoint.rollback()

            connection.execute(
                source_extraction_record.update()
                .where(
                    source_extraction_record.c.extraction_record_id == extraction_record_id
                )
                .values(primary_evidence_type="Unclassified")
            )
        finally:
            trans.rollback()
            connection.close()

        # Downgrade drops the new columns/CHECKs cleanly...
        command.downgrade(cfg, PRE_MIGRATION_REVISION)
        inspector = inspect(engine)
        finding_columns = {
            c["name"] for c in inspector.get_columns("intervention_outcome_finding")
        }
        record_columns = {c["name"] for c in inspector.get_columns("source_extraction_record")}
        assert "study_geography" not in finding_columns
        assert "effect_basis" not in finding_columns
        assert "primary_evidence_type" not in record_columns

        # ...and re-upgrading restores them (NULL — the update above was rolled
        # back with the transaction, so nothing survives the downgrade to backfill).
        command.upgrade(cfg, "head")
        inspector = inspect(engine)
        finding_columns = {
            c["name"] for c in inspector.get_columns("intervention_outcome_finding")
        }
        record_columns = {c["name"] for c in inspector.get_columns("source_extraction_record")}
        assert {"study_geography", "effect_basis"} <= finding_columns
        assert "primary_evidence_type" in record_columns

        connection = engine.connect()
        trans = connection.begin()
        try:
            finding_row = connection.execute(
                select(intervention_outcome_finding).where(
                    intervention_outcome_finding.c.finding_id == finding_id
                )
            ).one()
            assert finding_row.study_geography is None
            assert finding_row.effect_basis is None
        finally:
            trans.rollback()
            connection.close()
    finally:
        # Clean up the committed seed rows (outside any migration's own DDL
        # transaction) then restore head for the rest of the suite.
        command.upgrade(cfg, "head")
        connection = engine.connect()
        trans = connection.begin()
        try:
            delete_task_data(connection, task_id)
            trans.commit()
        finally:
            connection.close()
