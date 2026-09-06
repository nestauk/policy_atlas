"""Migration roundtrip for task-021 ICF domain core and IOF setting rider."""

import uuid

import pytest
from alembic import command
from sqlalchemy import inspect, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.schema import (
    implementation_context_finding,
    intervention_outcome_finding,
    source_snapshot,
)
from tests.conftest import _alembic_cfg
from tests.core.legacy_catalog import legacy_table, seed_legacy_task_and_run
from tests.helpers import delete_task_data, now

PRE_MIGRATION_REVISION = "0f4e2d8c9b1a"


def _seed_v2_finding(
    connection: Connection, *, task_id: uuid.UUID, run_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed a v2-shaped extraction record and IOF finding before the upgrade.

    Runs only BELOW revision c1a7f4e9b0d2, where the catalog still says
    ``project_id`` / ``project_source_snapshot``, so the renamed tables are
    reflected rather than taken from ``core.schema`` (plan D9).

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
            source_locator="https://example.org/icf-migration-test",
            metadata={"title": "V2 shaped doc", "abstract": "Abstract."},
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
            extraction_fingerprint="fp-icf-migration-test",
            status="extracted",
            basis="abstract_only",
            primary_evidence_type=None,
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
            study_geography="England",
            stratum_qualifiers=[],
            statistics={},
            causality_by_design=None,
            effect_basis="observed",
            is_primary=None,
            is_prevalence_only=None,
            field_coverage={},
            grounding=[],
            created_at=now(),
        )
    )
    return extraction_record_id, finding_id


def _icf_values(
    task_id: uuid.UUID,
    extraction_record_id: uuid.UUID,
    **overrides: object,
) -> dict[str, object]:
    values: dict[str, object] = {
        "finding_id": uuid.uuid4(),
        "task_id": task_id,
        "extraction_record_id": extraction_record_id,
        "context_type": "barrier",
        "claim": "Training gaps slowed delivery.",
        "intervention": "Coaching",
        "outcome": None,
        "population": None,
        "setting": "primary care",
        "study_geography": "England",
        "study_design": "process evaluation",
        "claim_level": "study",
        "claim_basis": "studied",
        "level": "provider",
        "resource_requirements": None,
        "workforce_requirements": "staff training",
        "field_coverage": {},
        "grounding": [],
        "created_at": now(),
    }
    values.update(overrides)
    return values


def test_icf_migration_roundtrip(engine: Engine) -> None:
    """The ICF table and IOF setting rider upgrade and downgrade cleanly."""
    cfg = _alembic_cfg()
    command.downgrade(cfg, PRE_MIGRATION_REVISION)

    inspector = inspect(engine)
    assert "implementation_context_finding" not in set(inspector.get_table_names())
    finding_columns = {
        c["name"] for c in inspector.get_columns("intervention_outcome_finding")
    }
    assert "setting" not in finding_columns

    connection = engine.connect()
    trans = connection.begin()
    task_id, run_id = seed_legacy_task_and_run(connection)
    extraction_record_id, finding_id = _seed_v2_finding(
        connection, task_id=task_id, run_id=run_id
    )
    trans.commit()
    connection.close()

    try:
        command.upgrade(cfg, "head")

        inspector = inspect(engine)
        assert "implementation_context_finding" in set(inspector.get_table_names())
        finding_columns = {
            c["name"] for c in inspector.get_columns("intervention_outcome_finding")
        }
        assert "setting" in finding_columns

        connection = engine.connect()
        trans = connection.begin()
        try:
            iof_row = connection.execute(
                select(intervention_outcome_finding).where(
                    intervention_outcome_finding.c.finding_id == finding_id
                )
            ).one()
            assert iof_row.intervention == "Coaching"
            assert iof_row.outcome == "Test scores"
            assert iof_row.study_geography == "England"
            assert iof_row.effect_basis == "observed"
            assert iof_row.setting is None

            for column, value, constraint in (
                ("context_type", "not-a-context", "ck_icf_context_type"),
                ("claim_level", "claim", "ck_icf_claim_level"),
                ("claim_basis", "guessed", "ck_icf_claim_basis"),
                ("level", "team", "ck_icf_level"),
            ):
                savepoint = connection.begin_nested()
                with pytest.raises(IntegrityError, match=constraint):
                    connection.execute(
                        implementation_context_finding.insert().values(
                            **_icf_values(
                                task_id,
                                extraction_record_id,
                                **{column: value},
                            )
                        )
                    )
                savepoint.rollback()

            valid_id = uuid.uuid4()
            connection.execute(
                implementation_context_finding.insert().values(
                    **_icf_values(
                        task_id,
                        extraction_record_id,
                        finding_id=valid_id,
                    )
                )
            )
            stored_icf = connection.execute(
                select(implementation_context_finding).where(
                    implementation_context_finding.c.finding_id == valid_id
                )
            ).one()
            assert stored_icf.context_type == "barrier"
        finally:
            trans.rollback()
            connection.close()

        command.downgrade(cfg, PRE_MIGRATION_REVISION)
        inspector = inspect(engine)
        assert "implementation_context_finding" not in set(inspector.get_table_names())
        finding_columns = {
            c["name"] for c in inspector.get_columns("intervention_outcome_finding")
        }
        assert "setting" not in finding_columns

        command.upgrade(cfg, "head")
        inspector = inspect(engine)
        assert "implementation_context_finding" in set(inspector.get_table_names())
        finding_columns = {
            c["name"] for c in inspector.get_columns("intervention_outcome_finding")
        }
        assert "setting" in finding_columns

        connection = engine.connect()
        trans = connection.begin()
        try:
            iof_row = connection.execute(
                select(intervention_outcome_finding).where(
                    intervention_outcome_finding.c.finding_id == finding_id
                )
            ).one()
            assert iof_row.setting is None
        finally:
            trans.rollback()
            connection.close()
    finally:
        command.upgrade(cfg, "head")
        connection = engine.connect()
        trans = connection.begin()
        try:
            delete_task_data(connection, task_id)
            trans.commit()
        finally:
            connection.close()
