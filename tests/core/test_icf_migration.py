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
    project_source_snapshot,
    source_extraction_record,
    source_snapshot,
)
from tests.conftest import _alembic_cfg
from tests.helpers import delete_project_data, now, seed_project_and_run

PRE_MIGRATION_REVISION = "0f4e2d8c9b1a"


def _seed_v2_finding(
    connection: Connection, *, project_id: uuid.UUID, run_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed a v2-shaped extraction record and IOF finding before the upgrade.

    Returns:
        ``(extraction_record_id, finding_id)``.
    """
    envelope_snap = uuid.uuid4()
    pss_id = uuid.uuid4()
    extraction_record_id = uuid.uuid4()
    finding_id = uuid.uuid4()

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
        project_source_snapshot.insert().values(
            project_source_snapshot_id=pss_id,
            project_id=project_id,
            source_snapshot_id=envelope_snap,
            origin="acquired",
            run_id=None,
            ingested_at=now(),
        )
    )
    connection.execute(
        source_extraction_record.insert().values(
            extraction_record_id=extraction_record_id,
            project_id=project_id,
            source_snapshot_id=envelope_snap,
            project_source_snapshot_id=pss_id,
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
        intervention_outcome_finding.insert().values(
            finding_id=finding_id,
            project_id=project_id,
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
    project_id: uuid.UUID,
    extraction_record_id: uuid.UUID,
    **overrides: object,
) -> dict[str, object]:
    values: dict[str, object] = {
        "finding_id": uuid.uuid4(),
        "project_id": project_id,
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
    project_id, run_id = seed_project_and_run(connection)
    extraction_record_id, finding_id = _seed_v2_finding(
        connection, project_id=project_id, run_id=run_id
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
                                project_id,
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
                        project_id,
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
            delete_project_data(connection, project_id)
            trans.commit()
        finally:
            connection.close()
