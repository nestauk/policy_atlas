"""Round trip and stored-row guards for the invite-link revision."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from alembic import command
from sqlalchemy import insert, inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.invite_code import new_code
from policy_atlas.core.schema import invite_link, organisation
from tests.conftest import _alembic_cfg

_PARENT = "a3c9e1f7b2d4"


def _catalogue(conn: Connection) -> dict[str, Any]:
    inspector = inspect(conn)
    return {
        table: (
            sorted(column["name"] for column in inspector.get_columns(table)),
            sorted(str(index["name"]) for index in inspector.get_indexes(table)),
            sorted(str(check["name"]) for check in inspector.get_check_constraints(table)),
        )
        for table in ("invite_link", "invite_link_cohort", "waitlist_entry")
    }


def _ops_grants(conn: Connection) -> set[tuple[str, str]]:
    rows = conn.execute(
        text(
            "SELECT table_name, privilege_type FROM information_schema.role_table_grants "
            "WHERE grantee = 'pa_ops' AND table_name IN ('invite_link', 'invite_link_cohort') "
            "UNION SELECT table_name || '.' || column_name, privilege_type "
            "FROM information_schema.column_privileges WHERE grantee = 'pa_ops' "
            "AND table_name = 'waitlist_entry' AND column_name = 'invite_link_id'"
        )
    )
    return {(str(table), str(privilege)) for table, privilege in rows}


def test_invite_link_round_trip_restores_the_fresh_upgrade_schema(engine: Engine) -> None:
    """Downgrade removes the tables, columns, indexes and grants; upgrade restores them."""
    cfg = _alembic_cfg()
    try:
        with engine.connect() as conn:
            before = _catalogue(conn)
            grants_before = _ops_grants(conn)
        assert grants_before
        command.downgrade(cfg, _PARENT)
        with engine.connect() as conn:
            names = inspect(conn).get_table_names()
            assert "invite_link" not in names
            assert "invite_link_cohort" not in names
            columns = {c["name"] for c in inspect(conn).get_columns("waitlist_entry")}
            assert not columns & {"invite_code", "invite_link_id"}
            assert _ops_grants(conn) == set()
        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            assert _catalogue(conn) == before
            assert _ops_grants(conn) == grants_before
    finally:
        command.upgrade(cfg, "head")


def _link(org_id: uuid.UUID, **override: Any) -> dict[str, Any]:
    now = datetime.now(UTC)
    row: dict[str, Any] = {
        "invite_link_id": uuid.uuid4(),
        "code": new_code(),
        "label": "Pilot",
        "org_id": org_id,
        "allowed_domains": ["example.org"],
        "max_uses": 10,
        "expires_at": now + timedelta(days=7),
        "created_at": now,
        "created_by": "operator",
    }
    return row | override


@pytest.mark.parametrize(
    ("override", "constraint"),
    [
        ({"code": "ABCD-EFGH-JK"}, "ck_invite_link_code_format"),
        ({"code": "ABCDEFGHJKM0"}, "ck_invite_link_code_format"),
        ({"code": "abcdefghjkmn"}, "ck_invite_link_code_format"),
        ({"code": "ABCDEFGHJKM"}, "ck_invite_link_code_format"),
        ({"allowed_domains": []}, "ck_invite_link_domain_count"),
        ({"allowed_domains": [f"d{i}.org" for i in range(11)]}, "ck_invite_link_domain_count"),
        ({"max_uses": 0}, "ck_invite_link_max_uses_positive"),
        ({"label": ""}, "ck_invite_link_label_length"),
        ({"label": "x" * 201}, "ck_invite_link_label_length"),
    ],
)
def test_invite_link_refuses_a_row_outside_its_checks(
    engine: Engine, override: dict[str, Any], constraint: str
) -> None:
    """A valid row stores; each out-of-bounds value is refused by its named check."""
    with engine.connect() as conn:
        org_id = uuid.uuid4()
        conn.execute(insert(organisation).values(
            org_id=org_id, name=f"org-{org_id}", created_at=datetime.now(UTC)
        ))
        conn.execute(insert(invite_link).values(**_link(org_id)))
        with pytest.raises(IntegrityError) as error, conn.begin_nested():
            conn.execute(insert(invite_link).values(**_link(org_id, **override)))
        assert constraint in str(error.value)
        conn.rollback()
