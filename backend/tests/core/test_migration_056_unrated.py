"""Round-trip and admission coverage for the task 056 revision (``152a234e2391``).

Contract D7 and S3; plan P6: the upgrade lets ``quality_score`` be NULL, adds
``unrated`` (NOT NULL, default false) and the check
``ck_sar_unrated_consistent``; the 1 to 5 check stays for scored rows. The
downgrade deletes Unrated rows (lossy), drops the check and the column and
restores NOT NULL.

The ``engine`` fixture is session-scoped and the test database shared, so the
round-trip test leaves the chain at head and removes the task it wrote.
"""

from __future__ import annotations

import uuid

import pytest
from alembic import command
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.schema import source_appraisal_result
from tests.conftest import _alembic_cfg
from tests.helpers import delete_task_data, now, seed_scope, seed_source, seed_task_and_run

PRE_REVISION = "b33ffb8c3a16"


def _columns(conn: Connection) -> dict[str, dict[str, object]]:
    return {
        str(c["name"]): dict(c) for c in inspect(conn).get_columns("source_appraisal_result")
    }


def _checks(conn: Connection) -> set[str]:
    return {
        str(c["name"]) for c in inspect(conn).get_check_constraints("source_appraisal_result")
    }


def _insert(
    conn: Connection,
    ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
    *,
    score: int | None,
    unrated: bool | None,
) -> uuid.UUID:
    """Insert one appraisal row for a fresh source; ``unrated=None`` leaves it to the default."""
    task_id, run_id, scope_id = ids
    _snap, tss_id = seed_source(conn, task_id)
    row_id = uuid.uuid4()
    values: dict[str, object] = {
        "source_appraisal_result_id": row_id,
        "evidence_scope_id": scope_id,
        "task_source_snapshot_id": tss_id,
        "task_id": task_id,
        "appraised_by_run_id": run_id,
        "quality_score": score,
        "rubric_version": "test-rubric",
        "appraised_at": now(),
    }
    if unrated is not None:
        values["unrated"] = unrated
    conn.execute(source_appraisal_result.insert().values(**values))
    return row_id


def test_the_revision_round_trips(engine: Engine) -> None:
    cfg = _alembic_cfg()
    task_id: uuid.UUID | None = None
    try:
        command.upgrade(cfg, "head")
        with engine.begin() as conn:
            task_id, run_id = seed_task_and_run(conn)
            scope_id = seed_scope(conn, task_id)
            ids = (task_id, run_id, scope_id)
            scored = _insert(conn, ids, score=4, unrated=False)
            unrated = _insert(conn, ids, score=None, unrated=True)

        command.downgrade(cfg, PRE_REVISION)
        with engine.begin() as conn:
            columns = _columns(conn)
            assert "unrated" not in columns
            assert columns["quality_score"]["nullable"] is False
            assert "ck_sar_unrated_consistent" not in _checks(conn)
            assert "ck_sar_quality_score" in _checks(conn)
            # Lossy: the Unrated row is gone, the scored row survives.
            remaining = {
                r
                for (r,) in conn.execute(
                    text(
                        "SELECT source_appraisal_result_id FROM source_appraisal_result "
                        "WHERE task_id = :t"
                    ),
                    {"t": task_id},
                )
            }
            assert remaining == {scored}
            assert unrated not in remaining

        command.upgrade(cfg, "head")
        with engine.begin() as conn:
            columns = _columns(conn)
            assert columns["quality_score"]["nullable"] is True
            assert columns["unrated"]["nullable"] is False
            assert columns["unrated"]["default"] is not None
            assert {"ck_sar_unrated_consistent", "ck_sar_quality_score"} <= _checks(conn)
            # The surviving row reads as an ordinary scored row.
            assert conn.execute(
                select(
                    source_appraisal_result.c.quality_score, source_appraisal_result.c.unrated
                ).where(source_appraisal_result.c.source_appraisal_result_id == scored)
            ).one() == (4, False)
    finally:
        command.upgrade(cfg, "head")
        if task_id is not None:
            with engine.begin() as conn:
                delete_task_data(conn, task_id)


@pytest.mark.parametrize(
    ("score", "unrated", "refused_by"),
    [
        (None, False, "ck_sar_unrated_consistent"),  # a scored row with no score
        (3, True, "ck_sar_unrated_consistent"),  # an Unrated row with a score
        (6, False, "ck_sar_quality_score"),  # out of the 1 to 5 range
    ],
)
def test_the_checks_refuse_inconsistent_rows(
    conn: Connection, score: int | None, unrated: bool, refused_by: str
) -> None:
    task_id, run_id = seed_task_and_run(conn)
    ids = (task_id, run_id, seed_scope(conn, task_id))
    with pytest.raises(IntegrityError, match=refused_by):
        _insert(conn, ids, score=score, unrated=unrated)


def test_the_checks_admit_unrated_and_scored_rows(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    ids = (task_id, run_id, seed_scope(conn, task_id))
    unrated = _insert(conn, ids, score=None, unrated=True)
    scored = _insert(conn, ids, score=3, unrated=False)
    defaulted = _insert(conn, ids, score=5, unrated=None)
    rows = {
        row.source_appraisal_result_id: row.unrated
        for row in conn.execute(
            select(
                source_appraisal_result.c.source_appraisal_result_id,
                source_appraisal_result.c.unrated,
            ).where(source_appraisal_result.c.task_id == task_id)
        )
    }
    assert rows == {unrated: True, scored: False, defaulted: False}
