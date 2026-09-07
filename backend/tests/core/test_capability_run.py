"""capability_run — cross-task FK guard + screen_generation coexistence (task 024)."""

import uuid

import pytest
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.schema import capability_run, runs, source_screening_result
from tests.helpers import now, seed_scope, seed_screening_result, seed_source, seed_task_and_run


def _seed_capability_run(
    conn: Connection, task_id: uuid.UUID, scope_id: uuid.UUID, *, status: str = "running"
) -> uuid.UUID:
    cap_run_id = uuid.uuid4()
    conn.execute(capability_run.insert().values(
        capability_run_id=cap_run_id,
        task_id=task_id,
        evidence_scope_id=scope_id,
        capability="evidence_search",
        plan_id=uuid.uuid4(),
        plan_version=1,
        status=status,
        session_id=None,
        started_at=now(),
        ended_at=None,
    ))
    return cap_run_id


def test_capability_run_insert_and_runs_reference(conn: Connection) -> None:
    """A runs row can reference a capability_run row in the same task."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    cap_run_id = _seed_capability_run(conn, task_id, scope_id)

    conn.execute(
        runs.update().where(runs.c.run_id == run_id).values(capability_run_id=cap_run_id)
    )
    fetched = conn.execute(
        runs.select().where(runs.c.run_id == run_id)
    ).one()
    assert fetched.capability_run_id == cap_run_id


def test_capability_run_cross_task_guard_rejected(conn: Connection) -> None:
    """A runs row must not reference a capability_run row from a different task
    (composite FK fk_runs_capability_run_task)."""
    task_a, _run_a = seed_task_and_run(conn)
    scope_a = seed_scope(conn, task_a)
    cap_run_a = _seed_capability_run(conn, task_a, scope_a)

    task_b, run_b = seed_task_and_run(conn)  # run_b belongs to task_b, not task_a

    with pytest.raises(IntegrityError, match="fk_runs_capability_run_task"):
        conn.execute(
            runs.update().where(runs.c.run_id == run_b).values(capability_run_id=cap_run_a)
        )


def test_screen_generation_different_generations_coexist(conn: Connection) -> None:
    """Two non-failed rows at the same (scope, source, stage) but different
    ``screen_generation`` coexist — a re-screen's fresh generation never collides
    with a prior generation's row."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _, tss_id = seed_source(conn, task_id)

    # generation 0 (the default — omitted, server_default applies)
    seed_screening_result(conn, task_id, run_id, scope_id, tss_id, status="relevant")

    # generation 1 — an explicit re-screen re-run's fresh row, same scope/source/stage
    conn.execute(source_screening_result.insert().values(
        source_screening_result_id=uuid.uuid4(),
        evidence_scope_id=scope_id,
        task_source_snapshot_id=tss_id,
        task_id=task_id,
        screened_by_run_id=run_id,
        status="relevant",
        screen_basis="title_abstract",
        screen_decision_confidence=0.9,
        screen_stage=1,
        screen_generation=1,
        screened_at=now(),
    ))

    rows = conn.execute(
        source_screening_result.select().where(
            source_screening_result.c.task_source_snapshot_id == tss_id
        )
    ).all()
    assert sorted(r.screen_generation for r in rows) == [0, 1]


def test_screen_generation_same_generation_collides(conn: Connection) -> None:
    """Two non-failed rows at the same (scope, source, stage, generation) still
    collide — uq_ssr_scope_source_stage."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _, tss_id = seed_source(conn, task_id)

    seed_screening_result(conn, task_id, run_id, scope_id, tss_id, status="relevant")

    with pytest.raises(IntegrityError, match="uq_ssr_scope_source_stage"):
        conn.execute(source_screening_result.insert().values(
            source_screening_result_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            task_source_snapshot_id=tss_id,
            task_id=task_id,
            screened_by_run_id=run_id,
            status="not_relevant",
            screen_basis="title_abstract",
            screen_decision_confidence=0.8,
            screen_stage=1,
            screen_generation=0,
            screened_at=now(),
        ))
