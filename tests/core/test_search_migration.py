"""Migration roundtrip for c9e4b7f2d1a8 (stop_condition widen).

Runs against the real Alembic migration chain, on the same test database as the
``conn`` fixture. Downgrades to the pre-widen revision, proves the narrow CHECK
constraint rejects the deep loop's new stop values, then upgrades back to head
and proves the widened constraint accepts them (and still rejects 'saturated').

Two couplings this test carries deliberately (both bitten once, task 017):

- The downgrade target is the explicit pre-widen revision, never ``"-1"`` —
  "-1" meant "one step below c9e4b7f2d1a8" only while that migration was head,
  and any later migration silently broke the narrow-constraint assertion.
- No row-holding transaction may be open while alembic runs DDL on a second
  connection: later migrations create/drop tables whose foreign keys reference
  ``project``/``evidence_scope``, and that DDL blocks forever behind this
  test's own uncommitted seed rows (lock-order deadlock). Seeding therefore
  happens strictly after the DDL step it accompanies, and every seed
  transaction is rolled back before the next DDL step.
"""

import uuid
from datetime import UTC, datetime

import pytest
from alembic import command
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.schema import search_coverage_record, source_screening_result
from tests.conftest import _alembic_cfg
from tests.helpers import seed_project_and_run, seed_run, seed_scope, seed_source

# The revision below c9e4b7f2d1a8 (the stop_condition widen) — the narrow-
# constraint state this test exercises.
PRE_WIDEN_REVISION = "e5c2a7f4b9d1"

# The revision below 921d3a781f3f (task 019 Phase D: stop-grain + retraction
# widen) — the narrow-constraint state test_stop_grain_and_retraction_widen_
# migration_roundtrip exercises. This is also 921d3a781f3f's own
# ``down_revision``, so it stays the correct explicit target for as long as
# 921d3a781f3f remains head (same "-1" trap the module docstring warns about).
PRE_FOLDING_PASS_WIDEN_REVISION = "64ff33416d1a"


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
    try:
        command.downgrade(cfg, PRE_WIDEN_REVISION)

        # Under the narrow (pre-015) constraint, the deep loop's stop value
        # fails. Seeds live in their own rolled-back transaction, opened only
        # after the DDL above completed.
        connection = engine.connect()
        trans = connection.begin()
        try:
            project_id, run_id = seed_project_and_run(connection)
            scope_id = seed_scope(connection, project_id)
            with pytest.raises(IntegrityError, match="ck_scov_stop_condition"):
                _insert_coverage_row(
                    connection,
                    project_id=project_id,
                    run_id=run_id,
                    scope_id=scope_id,
                    stop_condition="short_circuit",
                )
        finally:
            trans.rollback()
            connection.close()
    finally:
        command.upgrade(cfg, "head")

    # Back at head: each new stop value inserts cleanly, in a fresh
    # rolled-back transaction (the upgrade DDL above ran unblocked).
    connection = engine.connect()
    trans = connection.begin()
    try:
        project_id, run_id = seed_project_and_run(connection)
        scope_id = seed_scope(connection, project_id)
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


def _insert_screening_row(
    connection: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    pss_id: uuid.UUID,
    status: str,
) -> None:
    connection.execute(
        source_screening_result.insert().values(
            source_screening_result_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            project_source_snapshot_id=pss_id,
            project_id=project_id,
            screened_by_run_id=run_id,
            status=status,
            screen_basis="title_abstract",
            screen_decision_confidence=1.0,
            screen_stage=1,
            screened_at=datetime.now(UTC),
        )
    )


def test_stop_grain_and_retraction_widen_migration_roundtrip(engine: Engine) -> None:
    """Downgrade/upgrade roundtrip for 921d3a781f3f (task 019 Phase D).

    Proves the narrow (pre-921d3a781f3f) CHECKs reject 'completed' /
    'wall_clock_exceeded' on ``search_coverage_record`` and 'excluded_retracted'
    on ``source_screening_result``, then proves the widened CHECKs accept them
    at head (and 'saturated' still stays out of stop_condition, unaffected by
    this migration).
    """
    cfg = _alembic_cfg()
    try:
        command.downgrade(cfg, PRE_FOLDING_PASS_WIDEN_REVISION)

        connection = engine.connect()
        trans = connection.begin()
        try:
            project_id, run_id = seed_project_and_run(connection)
            scope_id = seed_scope(connection, project_id)
            _, pss_id = seed_source(connection, project_id)

            for stop_condition in ("completed", "wall_clock_exceeded"):
                savepoint = connection.begin_nested()
                with pytest.raises(IntegrityError, match="ck_scov_stop_condition"):
                    _insert_coverage_row(
                        connection,
                        project_id=project_id,
                        run_id=seed_run(connection, project_id),
                        scope_id=scope_id,
                        stop_condition=stop_condition,
                    )
                savepoint.rollback()

            savepoint = connection.begin_nested()
            with pytest.raises(IntegrityError, match="ck_ssr_status"):
                _insert_screening_row(
                    connection,
                    project_id=project_id,
                    run_id=run_id,
                    scope_id=scope_id,
                    pss_id=pss_id,
                    status="excluded_retracted",
                )
            savepoint.rollback()
        finally:
            trans.rollback()
            connection.close()
    finally:
        command.upgrade(cfg, "head")

    # Back at head: both new values insert cleanly, in a fresh rolled-back
    # transaction (the upgrade DDL above ran unblocked).
    connection = engine.connect()
    trans = connection.begin()
    try:
        project_id, run_id = seed_project_and_run(connection)
        scope_id = seed_scope(connection, project_id)
        _, pss_id = seed_source(connection, project_id)

        for stop_condition in ("completed", "wall_clock_exceeded"):
            _insert_coverage_row(
                connection,
                project_id=project_id,
                run_id=seed_run(connection, project_id),
                scope_id=scope_id,
                stop_condition=stop_condition,
            )

        # 'breadth_truncated' remains valid — historical rows are never
        # rejected by a widening CHECK.
        _insert_coverage_row(
            connection,
            project_id=project_id,
            run_id=seed_run(connection, project_id),
            scope_id=scope_id,
            stop_condition="breadth_truncated",
        )

        _insert_screening_row(
            connection,
            project_id=project_id,
            run_id=run_id,
            scope_id=scope_id,
            pss_id=pss_id,
            status="excluded_retracted",
        )

        # 'saturated' still stays out — unaffected by this migration.
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
