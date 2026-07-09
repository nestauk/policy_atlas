"""Migration roundtrip for c9e4b7f2d1a8 (stop_condition widen).

Runs against the real Alembic migration chain, on the same test database as the
``conn`` fixture. Downgrades one step, proves the narrow CHECK constraint rejects
the deep loop's new stop values, then upgrades back to head and proves the widened
constraint accepts them (and still rejects 'saturated').

This mutates the shared test database's schema for the duration of the test, so it
cannot use the transactional ``conn`` fixture (DDL is not rolled back by a
transaction abort the way row inserts are); it opens its own connection/transaction
for row-level work and always restores head in a ``finally`` block.
"""

import uuid
from datetime import UTC, datetime

import pytest
from alembic import command
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from policy_atlas.schema import search_coverage_record
from tests.conftest import _alembic_cfg
from tests.helpers import seed_project_and_run, seed_run, seed_scope


def _insert_coverage_row(
    connection: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    stop_condition: str,
) -> None:
    connection.execute(
        search_coverage_record.insert().values(
            search_coverage_record_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            project_id=project_id,
            acquired_by_run_id=run_id,
            backends=[
                {
                    "backend": "openalex",
                    "trust_class": "academic_aggregator",
                    "mode": "fixture",
                }
            ],
            scope_filters={},
            stop_condition=stop_condition,
            adequacy_verdict="adequate",
            verdict_origin="model",
            created_at=datetime.now(UTC),
        )
    )


def test_stop_condition_widen_migration_roundtrip(engine: Engine) -> None:
    cfg = _alembic_cfg()
    connection = engine.connect()
    trans = connection.begin()
    try:
        project_id, run_id = seed_project_and_run(connection)
        scope_id = seed_scope(connection, project_id)

        try:
            command.downgrade(cfg, "-1")

            # Under the narrow (pre-015) constraint, the deep loop's stop value fails.
            savepoint = connection.begin_nested()
            with pytest.raises(IntegrityError, match="ck_scov_stop_condition"):
                _insert_coverage_row(
                    connection,
                    project_id=project_id,
                    run_id=run_id,
                    scope_id=scope_id,
                    stop_condition="short_circuit",
                )
            savepoint.rollback()
        finally:
            command.upgrade(cfg, "head")

        # Back at head: each new stop value inserts cleanly.
        for stop_condition in ("short_circuit", "budget_exhausted", "target_reached"):
            _insert_coverage_row(
                connection,
                project_id=project_id,
                run_id=seed_run(connection, project_id),
                scope_id=scope_id,
                stop_condition=stop_condition,
            )

        # 'saturated' still stays out — deliberately, per the migration's own docstring.
        savepoint = connection.begin_nested()
        with pytest.raises(IntegrityError, match="ck_scov_stop_condition"):
            _insert_coverage_row(
                connection,
                project_id=project_id,
                run_id=seed_run(connection, project_id),
                scope_id=scope_id,
                stop_condition="saturated",
            )
        savepoint.rollback()
    finally:
        trans.rollback()
        connection.close()
