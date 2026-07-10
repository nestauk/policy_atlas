"""Migration roundtrip for 64ff33416d1a (effect_direction vocabulary rename).

Runs against the real Alembic migration chain, on the same test database as the
``conn`` fixture (task 018 rider A5). Downgrades to the pre-rename revision,
seeds a finding row with the old 'positive' value, proves the narrow (old)
CHECK constraint rejects 'increase', then upgrades back to head and proves the
seeded row's data was rewritten to 'increase' and the widened constraint now
rejects 'positive'.

Same coupling as ``test_search_migration.py`` (task 017/018 precedent): no
row-holding transaction may be open while alembic runs DDL on a second
connection, so seeding happens strictly after the DDL step it accompanies and
every seed transaction is rolled back before the next DDL step.
"""

import uuid

import pytest
from alembic import command
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from policy_atlas.schema import (
    intervention_outcome_finding,
    project_source_snapshot,
    source_extraction_record,
    source_snapshot,
)
from tests.conftest import _alembic_cfg
from tests.helpers import delete_project_data, now, seed_project_and_run, seed_run

# The revision below 64ff33416d1a (the effect_direction rename) — the narrow
# (old vocabulary) constraint state this test exercises.
PRE_RENAME_REVISION = "d2f8a4c1e9b7"


def _seed_finding(
    connection: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    effect_direction: str,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed the FK chain (abstract-basis doc -> extraction record -> finding).

    Returns (extraction_record_id, finding_id).
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
            source_locator="https://example.org/migration-test",
            metadata={"title": "Migration test doc", "abstract": "Abstract."},
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
            extraction_fingerprint="fp-migration-test",
            status="extracted",
            basis="abstract_only",
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
            effect_direction=effect_direction,
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


def test_effect_direction_rename_migration_roundtrip(engine: Engine) -> None:
    cfg = _alembic_cfg()
    try:
        command.downgrade(cfg, PRE_RENAME_REVISION)

        # Under the old (pre-rename) constraint: 'positive' inserts cleanly,
        # 'increase' is rejected. Seed lives in its own rolled-back transaction,
        # opened only after the downgrade DDL above completed.
        connection = engine.connect()
        trans = connection.begin()
        try:
            project_id, run_id = seed_project_and_run(connection)
            _seed_finding(
                connection, project_id=project_id, run_id=run_id, effect_direction="positive"
            )
            savepoint = connection.begin_nested()
            with pytest.raises(IntegrityError, match="ck_iof_direction"):
                _seed_finding(
                    connection,
                    project_id=project_id,
                    run_id=seed_run(connection, project_id),
                    effect_direction="increase",
                )
            savepoint.rollback()
        finally:
            trans.rollback()
            connection.close()
    finally:
        command.upgrade(cfg, "head")

    # Back at head: a fresh row proves the data UPDATE ran (the row seeded
    # under the old constraint would have been rewritten in place had it
    # survived the rollback above — here we seed anew and prove the widened
    # constraint's shape directly: 'increase' inserts, 'positive' is rejected).
    connection = engine.connect()
    trans = connection.begin()
    try:
        project_id, run_id = seed_project_and_run(connection)
        _seed_finding(
            connection, project_id=project_id, run_id=run_id, effect_direction="increase"
        )
        savepoint = connection.begin_nested()
        with pytest.raises(IntegrityError, match="ck_iof_direction"):
            _seed_finding(
                connection,
                project_id=project_id,
                run_id=seed_run(connection, project_id),
                effect_direction="positive",
            )
        savepoint.rollback()
    finally:
        trans.rollback()
        connection.close()


def test_effect_direction_rename_migration_rewrites_existing_data(engine: Engine) -> None:
    """A row seeded 'positive' pre-rename is rewritten to 'increase' post-upgrade,
    and downgrading rewrites it back to 'positive' — proving the data UPDATE,
    not just the constraint swap, in both directions.
    """
    cfg = _alembic_cfg()
    command.downgrade(cfg, PRE_RENAME_REVISION)

    connection = engine.connect()
    trans = connection.begin()
    project_id, run_id = seed_project_and_run(connection)
    _, finding_id = _seed_finding(
        connection, project_id=project_id, run_id=run_id, effect_direction="positive"
    )
    trans.commit()
    connection.close()

    try:
        command.upgrade(cfg, "head")

        connection = engine.connect()
        trans = connection.begin()
        try:
            row = connection.execute(
                select(intervention_outcome_finding.c.effect_direction).where(
                    intervention_outcome_finding.c.finding_id == finding_id
                )
            ).scalar_one()
            assert row == "increase"
        finally:
            trans.rollback()
            connection.close()

        command.downgrade(cfg, PRE_RENAME_REVISION)

        connection = engine.connect()
        trans = connection.begin()
        try:
            row = connection.execute(
                select(intervention_outcome_finding.c.effect_direction).where(
                    intervention_outcome_finding.c.finding_id == finding_id
                )
            ).scalar_one()
            assert row == "positive"
        finally:
            trans.rollback()
            connection.close()
    finally:
        # Clean up the committed seed row (outside any migration's own DDL
        # transaction, per delete_project_data's own doc) then restore head
        # for the rest of the suite. Runs at head so every FK-ordered table
        # delete_project_data touches exists.
        command.upgrade(cfg, "head")
        connection = engine.connect()
        trans = connection.begin()
        try:
            delete_project_data(connection, project_id)
            trans.commit()
        finally:
            connection.close()
