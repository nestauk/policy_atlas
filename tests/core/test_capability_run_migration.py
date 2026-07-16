"""Migration roundtrip for a3c6f9e2b7d4 (capability_run table + screen_generation).

Runs against the real Alembic migration chain, on the same test database as
the ``conn`` fixture (task 018 rider A5 precedent, mirrored from
test_extract_schema_v2_migration.py). ``screen_generation`` is additive-only
(server_default "0", task 020 no-backfill rule): a v1-shaped screening row
seeded before the upgrade survives untouched, with the new column defaulting
to 0. Downgrade drops capability_run / runs.capability_run_id /
screen_generation cleanly (restoring the narrow partial-unique index) and
re-upgrade restores them.

Same coupling as the other migration tests: no row-holding transaction may be
open while alembic runs DDL on a second connection, so seeding happens
strictly after the DDL step it accompanies and every seed transaction is
rolled back (or committed-then-cleaned-up) before the next DDL step.
"""

import uuid

import pytest
from alembic import command
from sqlalchemy import inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.schema import capability_run, runs, source_screening_result
from tests.conftest import _alembic_cfg
from tests.helpers import (
    delete_project_data,
    now,
    seed_project_and_run,
    seed_scope,
    seed_source,
)

# The revision below a3c6f9e2b7d4 (the task-024 schema gate) — the
# pre-migration state this test exercises.
PRE_MIGRATION_REVISION = "7a4d9c2e1f6b"


def test_capability_run_and_screen_generation_migration_roundtrip(engine: Engine) -> None:
    cfg = _alembic_cfg()
    command.downgrade(cfg, PRE_MIGRATION_REVISION)

    inspector = inspect(engine)
    assert "capability_run" not in set(inspector.get_table_names())
    runs_columns = {c["name"] for c in inspector.get_columns("runs")}
    ssr_columns = {c["name"] for c in inspector.get_columns("source_screening_result")}
    assert "capability_run_id" not in runs_columns
    assert "screen_generation" not in ssr_columns

    connection = engine.connect()
    trans = connection.begin()
    project_id, run_id = seed_project_and_run(connection)
    scope_id = seed_scope(connection, project_id)
    _, pss_id = seed_source(connection, project_id)
    # Seed the v1-shaped row inline: the shared seed_screening_result helper now
    # names screen_generation in its INSERT (task 024 generation supersession),
    # which the downgraded table does not have yet.
    connection.execute(source_screening_result.insert().values(
        source_screening_result_id=uuid.uuid4(),
        evidence_scope_id=scope_id,
        project_source_snapshot_id=pss_id,
        project_id=project_id,
        screened_by_run_id=run_id,
        status="relevant",
        screen_basis="title_abstract",
        screen_decision_confidence=0.9,
        screen_stage=1,
        screened_at=now(),
    ))
    trans.commit()
    connection.close()

    try:
        command.upgrade(cfg, "head")

        inspector = inspect(engine)
        assert "capability_run" in set(inspector.get_table_names())
        runs_columns = {c["name"] for c in inspector.get_columns("runs")}
        ssr_columns = {c["name"] for c in inspector.get_columns("source_screening_result")}
        assert "capability_run_id" in runs_columns
        assert "screen_generation" in ssr_columns

        connection = engine.connect()
        trans = connection.begin()
        try:
            # The v1-shaped screening row survives, new column arrives at its
            # server_default (0) — no backfill.
            generation = connection.execute(
                select(source_screening_result.c.screen_generation).where(
                    source_screening_result.c.project_source_snapshot_id == pss_id
                )
            ).scalar_one()
            assert generation == 0

            # The new CHECK is live.
            savepoint = connection.begin_nested()
            with pytest.raises(IntegrityError, match="ck_ssr_generation_nonneg"):
                connection.execute(
                    source_screening_result.update()
                    .where(source_screening_result.c.project_source_snapshot_id == pss_id)
                    .values(screen_generation=-1)
                )
            savepoint.rollback()

            # A capability_run row + a runs row referencing it via the new
            # composite FK.
            cap_run_id = uuid.uuid4()
            connection.execute(capability_run.insert().values(
                capability_run_id=cap_run_id,
                project_id=project_id,
                evidence_scope_id=scope_id,
                capability="evidence_base",
                plan_id=uuid.uuid4(),
                plan_version=1,
                status="running",
                session_id=None,
                started_at=now(),
                ended_at=None,
            ))
            connection.execute(
                runs.update().where(runs.c.run_id == run_id).values(capability_run_id=cap_run_id)
            )
            fetched = connection.execute(
                select(runs.c.capability_run_id).where(runs.c.run_id == run_id)
            ).scalar_one()
            assert fetched == cap_run_id
        finally:
            trans.rollback()
            connection.close()

        # Downgrade drops the new table/columns/CHECK cleanly, restoring the
        # narrow partial-unique index...
        command.downgrade(cfg, PRE_MIGRATION_REVISION)
        inspector = inspect(engine)
        assert "capability_run" not in set(inspector.get_table_names())
        runs_columns = {c["name"] for c in inspector.get_columns("runs")}
        ssr_columns = {c["name"] for c in inspector.get_columns("source_screening_result")}
        assert "capability_run_id" not in runs_columns
        assert "screen_generation" not in ssr_columns

        # ...and re-upgrading restores them.
        command.upgrade(cfg, "head")
        inspector = inspect(engine)
        assert "capability_run" in set(inspector.get_table_names())
        runs_columns = {c["name"] for c in inspector.get_columns("runs")}
        ssr_columns = {c["name"] for c in inspector.get_columns("source_screening_result")}
        assert "capability_run_id" in runs_columns
        assert "screen_generation" in ssr_columns
    finally:
        # Clean up the committed seed rows (outside any migration's own DDL
        # transaction) then restore head for the rest of the suite. Null the
        # runs->capability_run link and drop capability_run rows first — both
        # would otherwise block delete_project_data's runs/project deletes
        # under fk_runs_capability_run_project / fk_capr_scope_project.
        command.upgrade(cfg, "head")
        connection = engine.connect()
        trans = connection.begin()
        try:
            connection.execute(
                runs.update()
                .where(runs.c.project_id == project_id)
                .values(capability_run_id=None)
            )
            connection.execute(
                capability_run.delete().where(capability_run.c.project_id == project_id)
            )
            delete_project_data(connection, project_id)
            trans.commit()
        finally:
            connection.close()
