"""Round-trip coverage for the task 046 revision (``d8f3b6a2c4e1``).

Contract § Constraints, Schema, and § Acceptance checks, "migration
round-trip": three nullable text columns on ``intervention_profile_record``,
two of them closed by a check constraint; the downgrade drops them; the union
view is untouched. The ``engine`` fixture is session-scoped and the test
database shared, so the test leaves the chain at head.
"""

from __future__ import annotations

from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine

from tests.conftest import _alembic_cfg

PRE_REVISION = "c7e2a9f4b1d8"
# This revision, not head: a later revision renames ``population_tag`` and the
# view's column (task 046, amendment 3, R71).
REVISION = "d8f3b6a2c4e1"
_TAGS = ("population_tag", "outcome_tag", "object_tag")
_CHECKS = {"ck_ipr_population_tag", "ck_ipr_object_tag"}


def _columns(conn: Connection) -> dict[str, dict[str, object]]:
    return {
        str(column["name"]): dict(column)
        for column in inspect(conn).get_columns("intervention_profile_record")
    }


def _checks(conn: Connection) -> set[str]:
    return {
        str(check["name"])
        for check in inspect(conn).get_check_constraints("intervention_profile_record")
    }


def _view_definition(conn: Connection) -> str:
    query = text("SELECT pg_get_viewdef('finding_reference_union'::regclass)")
    return str(conn.execute(query).scalar_one())


def test_the_revision_round_trips(engine: Engine) -> None:
    cfg = _alembic_cfg()
    try:
        command.downgrade(cfg, REVISION)
        with engine.connect() as conn:
            view_at_revision = _view_definition(conn)
        command.downgrade(cfg, PRE_REVISION)
        with engine.connect() as conn:
            columns = _columns(conn)
            assert not set(_TAGS) & set(columns)
            assert not _CHECKS & _checks(conn)
            assert "study_geography" in columns
            assert _view_definition(conn) == view_at_revision

        command.upgrade(cfg, REVISION)
        with engine.connect() as conn:
            columns = _columns(conn)
            for name in _TAGS:
                assert name in columns
                assert columns[name]["nullable"] is True
            assert _checks(conn) >= _CHECKS
            assert _view_definition(conn) == view_at_revision

        command.downgrade(cfg, PRE_REVISION)
        command.upgrade(cfg, REVISION)
        with engine.connect() as conn:
            assert set(_TAGS) <= set(_columns(conn))
    finally:
        command.upgrade(cfg, "head")
