"""Round-trip coverage for task 065's account-management revision."""

from __future__ import annotations

import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from tests.conftest import _alembic_cfg


def test_065_round_trip_restores_the_fresh_upgrade_schema(engine: Engine) -> None:
    """Upgrade, step down to before 065 (both its revisions), and upgrade to the same catalog."""
    cfg = _alembic_cfg()
    try:
        with engine.connect() as conn:
            before = {
                table: tuple(sorted(column["name"] for column in inspect(conn).get_columns(table)))
                for table in (
                    "app_user",
                    "organisation",
                    "waitlist_entry",
                    "ops_action",
                    "organisation_domain",
                    "cohort",
                    "cohort_member",
                )
            }
        # By name: 065 has two revisions (the cohorts one came later).
        command.downgrade(cfg, "b1e7c3a9d5f2")
        with engine.connect() as conn:
            assert "ops_action" not in inspect(conn).get_table_names()
            assert "organisation_domain" not in inspect(conn).get_table_names()
            assert "cohort" not in inspect(conn).get_table_names()
        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            after = {
                table: tuple(sorted(column["name"] for column in inspect(conn).get_columns(table)))
                for table in before
            }
        assert after == before
    finally:
        command.upgrade(cfg, "head")


def test_065_checks_trigger_and_nologin_role(engine: Engine) -> None:
    """The quota constraints, privilege trigger, and role exist after upgrade."""
    with engine.begin() as conn:
        with pytest.raises(IntegrityError), conn.begin_nested():
            conn.execute(
                text(
                    "INSERT INTO app_user "
                    "(user_id, display_name, is_admin, is_ops, created_at, task_quota_per_year) "
                    "VALUES ('negative-quota', 'Negative quota', false, false, "
                    "CURRENT_TIMESTAMP, -1)"
                )
            )
        assert (
            conn.execute(
                text(
                    "SELECT 1 FROM pg_trigger WHERE tgname = 'trg_app_user_refuse_privilege_grant'"
                )
            ).scalar_one()
            == 1
        )
        # The role is cluster-wide: another test database's login fixture may
        # hold LOGIN on it at this moment, so only its existence is asserted.
        assert conn.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = 'pa_ops'")
        ).scalar_one() == 1
