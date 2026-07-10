"""orchestration_plan schema round-trip tests (task 017)."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas.schema import orchestration_plan
from tests.helpers import now, seed_project_and_run, seed_scope


def _insert_plan(
    conn: Connection,
    project_id: uuid.UUID,
    *,
    version: int = 1,
    status: str = "proposed",
    evidence_scope_id: uuid.UUID | None = None,
    payload: object = None,
    created_by: str = "planner",
    approved_at: object = None,
) -> uuid.UUID:
    plan_id = uuid.uuid4()
    conn.execute(orchestration_plan.insert().values(
        plan_id=plan_id,
        project_id=project_id,
        evidence_scope_id=evidence_scope_id,
        version=version,
        status=status,
        payload=payload if payload is not None else {"intent": "test intent"},
        created_at=now(),
        created_by=created_by,
        approved_at=approved_at,
    ))
    return plan_id


def test_orchestration_plan_insert_and_read_back(conn: Connection) -> None:
    """A proposed plan row round-trips through insert + select."""
    pid, _ = seed_project_and_run(conn)
    plan_id = _insert_plan(conn, pid, payload={"intent": "test intent", "chains": []})

    row = conn.execute(
        select(orchestration_plan).where(orchestration_plan.c.plan_id == plan_id)
    ).one()
    assert row.project_id == pid
    assert row.version == 1
    assert row.status == "proposed"
    assert row.payload == {"intent": "test intent", "chains": []}
    assert row.created_by == "planner"
    assert row.evidence_scope_id is None
    assert row.approved_at is None


def test_orchestration_plan_amendment_version_inserts_alongside(conn: Connection) -> None:
    """A version-2 amendment row inserts alongside version 1 for the same project."""
    pid, _ = seed_project_and_run(conn)
    _insert_plan(conn, pid, version=1)
    _insert_plan(conn, pid, version=2, status="proposed")

    rows = conn.execute(
        select(orchestration_plan.c.version)
        .where(orchestration_plan.c.project_id == pid)
        .order_by(orchestration_plan.c.version)
    ).scalars().all()
    assert rows == [1, 2]


def test_orchestration_plan_duplicate_project_version_rejected(conn: Connection) -> None:
    """(project_id, version) must be unique — a duplicate version-1 row rejects."""
    pid, _ = seed_project_and_run(conn)
    _insert_plan(conn, pid, version=1)
    with pytest.raises(IntegrityError, match="uq_oplan_project_version"):
        _insert_plan(conn, pid, version=1)


def test_orchestration_plan_invalid_status_rejected(conn: Connection) -> None:
    """ck_oplan_status admits only proposed|approved|superseded|abandoned."""
    pid, _ = seed_project_and_run(conn)
    with pytest.raises(IntegrityError, match="ck_oplan_status"):
        _insert_plan(conn, pid, status="rejected")


def test_orchestration_plan_payload_must_be_object(conn: Connection) -> None:
    """ck_oplan_payload_object rejects a non-object JSONB payload (e.g. an array)."""
    pid, _ = seed_project_and_run(conn)
    with pytest.raises(IntegrityError, match="ck_oplan_payload_object"):
        _insert_plan(conn, pid, payload=[])


def test_orchestration_plan_cross_project_evidence_scope_rejected(conn: Connection) -> None:
    """fk_oplan_scope_project rejects an evidence_scope belonging to another project."""
    pid_a, _ = seed_project_and_run(conn)
    pid_b, _ = seed_project_and_run(conn)
    scope_b = seed_scope(conn, pid_b)
    with pytest.raises(IntegrityError, match="fk_oplan_scope_project"):
        _insert_plan(conn, pid_a, evidence_scope_id=scope_b)
