"""task_plan schema round-trip tests (task 017)."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.schema import task_plan
from policy_atlas.runtime.task_plan import TaskPlan
from tests.helpers import now, seed_scope, seed_task_and_run


def _insert_plan(
    conn: Connection,
    task_id: uuid.UUID,
    *,
    version: int = 1,
    status: str = "proposed",
    evidence_scope_id: uuid.UUID | None = None,
    payload: object = None,
    created_by: str = "planner",
    approved_at: object = None,
) -> uuid.UUID:
    plan_id = uuid.uuid4()
    conn.execute(task_plan.insert().values(
        plan_id=plan_id,
        task_id=task_id,
        evidence_scope_id=evidence_scope_id,
        version=version,
        status=status,
        payload=payload if payload is not None else {"intent": "test intent"},
        created_at=now(),
        created_by=created_by,
        approved_at=approved_at,
    ))
    return plan_id


def test_task_plan_insert_and_read_back(conn: Connection) -> None:
    """A proposed plan row round-trips through insert + select."""
    pid, _ = seed_task_and_run(conn)
    plan_id = _insert_plan(conn, pid, payload={"intent": "test intent", "chains": []})

    row = conn.execute(
        select(task_plan).where(task_plan.c.plan_id == plan_id)
    ).one()
    assert row.task_id == pid
    assert row.version == 1
    assert row.status == "proposed"
    assert row.payload == {"intent": "test intent", "chains": []}
    assert row.created_by == "planner"
    assert row.evidence_scope_id is None
    assert row.approved_at is None


def test_task_plan_country_group_round_trips_all_fields(
    conn: Connection,
) -> None:
    """A plan payload preserves country_group label, countries and authorship."""
    pid, _ = seed_task_and_run(conn)
    plan = TaskPlan.model_validate(
        {
            "title": "Nordic review",
            "question": "What evidence exists on Nordic housing policy outcomes?",
            "backend_scope": "both",
            "scope_constraints": {
                "country_group": {
                    "label": "Nordic countries",
                    "countries": ["NO", "SE", "DK", "FI", "IS"],
                    "authorship": "user-amended",
                }
            },
            "search_effort": "rapid",
            "analysis_depth": "landscape",
            "components": ["characterise"],
            "steering_mode": "moderate",
        }
    )
    plan_id = _insert_plan(conn, pid, payload=plan.model_dump(mode="json"))

    row = conn.execute(
        select(task_plan.c.payload).where(task_plan.c.plan_id == plan_id)
    ).one()
    reloaded = TaskPlan.model_validate(row.payload)

    assert reloaded == plan
    assert reloaded.scope_constraints.country_group is not None
    assert reloaded.scope_constraints.country_group.label == "Nordic countries"
    assert reloaded.scope_constraints.country_group.countries == [
        "NO",
        "SE",
        "DK",
        "FI",
        "IS",
    ]
    assert reloaded.scope_constraints.country_group.authorship == "user-amended"


def test_task_plan_amendment_version_inserts_alongside(conn: Connection) -> None:
    """A version-2 amendment row inserts alongside version 1 for the same task."""
    pid, _ = seed_task_and_run(conn)
    _insert_plan(conn, pid, version=1)
    _insert_plan(conn, pid, version=2, status="proposed")

    rows = conn.execute(
        select(task_plan.c.version)
        .where(task_plan.c.task_id == pid)
        .order_by(task_plan.c.version)
    ).scalars().all()
    assert rows == [1, 2]


def test_task_plan_duplicate_task_version_rejected(conn: Connection) -> None:
    """(task_id, version) must be unique — a duplicate version-1 row rejects."""
    pid, _ = seed_task_and_run(conn)
    _insert_plan(conn, pid, version=1)
    with pytest.raises(IntegrityError, match="uq_plan_task_version"):
        _insert_plan(conn, pid, version=1)


def test_task_plan_invalid_status_rejected(conn: Connection) -> None:
    """ck_plan_status admits only proposed|approved|superseded|abandoned."""
    pid, _ = seed_task_and_run(conn)
    with pytest.raises(IntegrityError, match="ck_plan_status"):
        _insert_plan(conn, pid, status="rejected")


def test_task_plan_payload_must_be_object(conn: Connection) -> None:
    """ck_plan_payload_object rejects a non-object JSONB payload (e.g. an array)."""
    pid, _ = seed_task_and_run(conn)
    with pytest.raises(IntegrityError, match="ck_plan_payload_object"):
        _insert_plan(conn, pid, payload=[])


def test_task_plan_cross_task_evidence_scope_rejected(conn: Connection) -> None:
    """fk_plan_scope_task rejects an evidence_scope belonging to another task."""
    pid_a, _ = seed_task_and_run(conn)
    pid_b, _ = seed_task_and_run(conn)
    scope_b = seed_scope(conn, pid_b)
    with pytest.raises(IntegrityError, match="fk_plan_scope_task"):
        _insert_plan(conn, pid_a, evidence_scope_id=scope_b)
