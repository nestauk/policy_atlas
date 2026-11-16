"""Round-trip coverage for the task 055 revision (``b33ffb8c3a16``).

Contract § Constraints and § Acceptance checks (item 1; A1, A15, A22): the
upgrade adds ``option.shortlist_state`` (checked), ``option.shortlist_reason``
and ``longlist_result.shortlist`` (NOT NULL, default ``{}`` kept), and admits
``shortlist`` as an intent-record purpose; the downgrade clears shortlist
purposes, restores the old check, drops the three columns and strips
``risk_appetite`` from every stored plan payload (lossy, A15).

The ``engine`` fixture is session-scoped and the test database shared, so the
test leaves the chain at head and removes the task it wrote.
"""

from __future__ import annotations

import uuid

import pytest
from alembic import command
from sqlalchemy import inspect, select, text, update
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.schema import (
    OPTION_SHORTLIST_STATES,
    evidence_scope,
    longlist_result,
    option,
    task,
    task_plan,
)
from tests.conftest import _alembic_cfg
from tests.helpers import delete_task_data, now, seed_scope, seed_task_and_run

PRE_REVISION = "f1b6d3a8c2e5"
_APPETITES = ("tried_only", "mostly_tried", "open_to_untested")


def _columns(conn: Connection, table: str) -> dict[str, dict[str, object]]:
    return {str(c["name"]): dict(c) for c in inspect(conn).get_columns(table)}


def _checks(conn: Connection, table: str) -> dict[str, str]:
    return {
        str(c["name"]): str(c["sqltext"]) for c in inspect(conn).get_check_constraints(table)
    }


def _seed(conn: Connection) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """A scoping task at head: three plan versions, a placed option, a shortlist scope.

    Returns:
        ``(task_id, option_id, shortlist_scope_id, run_id)``.
    """
    task_id, run_id = seed_task_and_run(conn)
    conn.execute(
        update(task).where(task.c.task_id == task_id).values(capability="options_scoping")
    )
    for version, appetite in enumerate(_APPETITES, start=1):
        conn.execute(
            task_plan.insert().values(
                plan_id=uuid.uuid4(),
                task_id=task_id,
                version=version,
                status="approved" if version == len(_APPETITES) else "superseded",
                payload={"title": f"v{version}", "risk_appetite": appetite},
                created_at=now(),
                created_by="test",
            )
        )
    option_id = uuid.uuid4()
    conn.execute(
        option.insert().values(
            option_id=option_id,
            task_id=task_id,
            name="Youth guarantee",
            description="An offer of work or training within four months.",
            design={"features": ["offer within four months"]},
            outcomes=["the NEET rate"],
            origin="suggested",
            secondary_lever_types=[],
            shortlist_state="proposed",
            shortlist_reason="Tried at scale in three countries.",
            created_at=now(),
            updated_at=now(),
        )
    )
    scope_id = seed_scope(conn, task_id, purpose="shortlist")
    return task_id, option_id, scope_id, run_id


def test_the_revision_round_trips(engine: Engine) -> None:
    cfg = _alembic_cfg()
    task_id: uuid.UUID | None = None
    try:
        command.upgrade(cfg, "head")
        with engine.begin() as conn:
            task_id, option_id, scope_id, run_id = _seed(conn)

        command.downgrade(cfg, PRE_REVISION)
        with engine.begin() as conn:
            option_columns = _columns(conn, "option")
            assert "shortlist_state" not in option_columns
            assert "shortlist_reason" not in option_columns
            assert "shortlist" not in _columns(conn, "longlist_result")
            assert "ck_option_shortlist_state" not in _checks(conn, "option")
            assert "shortlist" not in _checks(conn, "evidence_scope")["ck_scope_purpose"]
            # The shortlist scope survives with its purpose cleared.
            purpose = conn.execute(
                text("SELECT purpose FROM evidence_scope WHERE evidence_scope_id = :s"),
                {"s": scope_id},
            ).scalar_one()
            assert purpose is None
            # A15: the key is stripped from every plan version; the rest stays.
            payloads = [
                p
                for (p,) in conn.execute(
                    text("SELECT payload FROM plan WHERE task_id = :t ORDER BY version"),
                    {"t": task_id},
                )
            ]
            assert payloads == [{"title": "v1"}, {"title": "v2"}, {"title": "v3"}]
            # A longlist row written in the old shape, to read after the upgrade.
            row_id = uuid.uuid4()
            conn.execute(
                text(
                    "INSERT INTO longlist_result (longlist_result_id, task_id, "
                    "evidence_scope_id, run_id, plan_version, themes, coverage, judgements, "
                    "guesses, option_profile, counts, provenance, created_at) VALUES "
                    "(:l, :t, :s, :r, 3, '[]', '{}', '{}', '[]', '{}', '{}', '{}', :c)"
                ),
                {"l": row_id, "t": task_id, "s": scope_id, "r": run_id, "c": now()},
            )

        command.upgrade(cfg, "head")
        with engine.begin() as conn:
            option_columns = _columns(conn, "option")
            assert option_columns["shortlist_state"]["nullable"] is True
            assert option_columns["shortlist_reason"]["nullable"] is True
            shortlist = _columns(conn, "longlist_result")["shortlist"]
            assert shortlist["nullable"] is False
            # The default is kept (plan PR1): the longlist insert does not name it.
            assert shortlist["default"] is not None
            assert "shortlist" in _checks(conn, "evidence_scope")["ck_scope_purpose"]
            # The old option reads as "no place"; the old longlist row as "no proposal".
            assert conn.execute(
                select(option.c.shortlist_state, option.c.shortlist_reason).where(
                    option.c.option_id == option_id
                )
            ).one() == (None, None)
            assert conn.execute(
                select(longlist_result.c.shortlist).where(
                    longlist_result.c.longlist_result_id == row_id
                )
            ).scalar_one() == {}
            # The purpose is admitted again.
            conn.execute(
                update(evidence_scope)
                .where(evidence_scope.c.evidence_scope_id == scope_id)
                .values(purpose="shortlist")
            )
    finally:
        command.upgrade(cfg, "head")
        if task_id is not None:
            with engine.begin() as conn:
                delete_task_data(conn, task_id)


def test_the_check_admits_the_three_states_and_nothing_else(conn: Connection) -> None:
    task_id, option_id, _scope, _run = _seed(conn)
    for state in OPTION_SHORTLIST_STATES:
        conn.execute(
            update(option).where(option.c.option_id == option_id).values(shortlist_state=state)
        )
    with pytest.raises(IntegrityError, match="ck_option_shortlist_state"):
        conn.execute(
            update(option)
            .where(option.c.option_id == option_id)
            .values(shortlist_state="ranked_first")
        )
    assert task_id is not None
