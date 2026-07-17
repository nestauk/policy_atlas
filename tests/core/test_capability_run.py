"""capability_run — cross-project FK guard + screen_generation coexistence (task 024)."""

import uuid

import pytest
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.schema import capability_run, runs, source_screening_result
from tests.helpers import now, seed_project_and_run, seed_scope, seed_screening_result, seed_source


def _seed_capability_run(
    conn: Connection, project_id: uuid.UUID, scope_id: uuid.UUID, *, status: str = "running"
) -> uuid.UUID:
    cap_run_id = uuid.uuid4()
    conn.execute(capability_run.insert().values(
        capability_run_id=cap_run_id,
        project_id=project_id,
        evidence_scope_id=scope_id,
        capability="evidence_base",
        plan_id=uuid.uuid4(),
        plan_version=1,
        status=status,
        session_id=None,
        started_at=now(),
        ended_at=None,
    ))
    return cap_run_id


def test_capability_run_insert_and_runs_reference(conn: Connection) -> None:
    """A runs row can reference a capability_run row in the same project."""
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    cap_run_id = _seed_capability_run(conn, project_id, scope_id)

    conn.execute(
        runs.update().where(runs.c.run_id == run_id).values(capability_run_id=cap_run_id)
    )
    fetched = conn.execute(
        runs.select().where(runs.c.run_id == run_id)
    ).one()
    assert fetched.capability_run_id == cap_run_id


def test_capability_run_cross_project_guard_rejected(conn: Connection) -> None:
    """A runs row must not reference a capability_run row from a different project
    (composite FK fk_runs_capability_run_project)."""
    project_a, _run_a = seed_project_and_run(conn)
    scope_a = seed_scope(conn, project_a)
    cap_run_a = _seed_capability_run(conn, project_a, scope_a)

    project_b, run_b = seed_project_and_run(conn)  # run_b belongs to project_b, not project_a

    with pytest.raises(IntegrityError, match="fk_runs_capability_run_project"):
        conn.execute(
            runs.update().where(runs.c.run_id == run_b).values(capability_run_id=cap_run_a)
        )


def test_screen_generation_different_generations_coexist(conn: Connection) -> None:
    """Two non-failed rows at the same (scope, source, stage) but different
    ``screen_generation`` coexist — a re-screen's fresh generation never collides
    with a prior generation's row."""
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    _, pss_id = seed_source(conn, project_id)

    # generation 0 (the default — omitted, server_default applies)
    seed_screening_result(conn, project_id, run_id, scope_id, pss_id, status="relevant")

    # generation 1 — an explicit re-screen re-run's fresh row, same scope/source/stage
    conn.execute(source_screening_result.insert().values(
        source_screening_result_id=uuid.uuid4(),
        evidence_scope_id=scope_id,
        project_source_snapshot_id=pss_id,
        project_id=project_id,
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
            source_screening_result.c.project_source_snapshot_id == pss_id
        )
    ).all()
    assert sorted(r.screen_generation for r in rows) == [0, 1]


def test_screen_generation_same_generation_collides(conn: Connection) -> None:
    """Two non-failed rows at the same (scope, source, stage, generation) still
    collide — uq_ssr_scope_source_stage."""
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    _, pss_id = seed_source(conn, project_id)

    seed_screening_result(conn, project_id, run_id, scope_id, pss_id, status="relevant")

    with pytest.raises(IntegrityError, match="uq_ssr_scope_source_stage"):
        conn.execute(source_screening_result.insert().values(
            source_screening_result_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            project_source_snapshot_id=pss_id,
            project_id=project_id,
            screened_by_run_id=run_id,
            status="not_relevant",
            screen_basis="title_abstract",
            screen_decision_confidence=0.8,
            screen_stage=1,
            screen_generation=0,
            screened_at=now(),
        ))
