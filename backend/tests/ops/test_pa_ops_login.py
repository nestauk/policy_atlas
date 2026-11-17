"""The ``pa_ops`` login has only task 065's intended database privileges."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from psycopg import sql
from psycopg.errors import InsufficientPrivilege
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import ProgrammingError

from policy_atlas.core.schema import app_user
from tests.api.org_support import seeded

_PASSWORD = "p@ss:w/rd#1"


@pytest.fixture(scope="module")
def pa_ops_engine(engine: Engine) -> Generator[Engine, None, None]:
    """Yield a local second engine authenticated as the constrained ops role."""
    master_url = engine.url
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        driver_connection = conn.connection.driver_connection
        assert driver_connection is not None
        driver_connection.execute(
            sql.SQL("ALTER ROLE pa_ops LOGIN PASSWORD {}").format(sql.Literal(_PASSWORD))
        )
    role_url = URL.create(
        drivername=master_url.drivername,
        username="pa_ops",
        password=_PASSWORD,
        host=master_url.host,
        port=master_url.port,
        database=master_url.database,
    )
    role_engine = create_engine(role_url)
    try:
        yield role_engine
    finally:
        role_engine.dispose()
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("ALTER ROLE pa_ops NOLOGIN"))


@pytest.fixture
def seeded_user(engine: Engine) -> str:
    """Commit an unprivileged row visible to the second login and return its subject."""
    return _seed_user(engine, is_admin=False)


@pytest.fixture
def seeded_admin_user(engine: Engine) -> str:
    """Commit an admin row that the constrained login may clear."""
    return _seed_user(engine, is_admin=True)


def _seed_user(engine: Engine, *, is_admin: bool) -> str:
    """Commit one account row with the requested existing admin state."""
    user_id = f"pa-ops-{uuid.uuid4()}"
    with seeded(engine) as conn:
        conn.execute(
            app_user.insert().values(
                user_id=user_id,
                org_id=None,
                display_name="Ops test person",
                email=f"{user_id}@example.test",
                is_admin=is_admin,
                is_ops=False,
                created_at=datetime.now(UTC),
            )
        )
    return user_id


def _assert_refused(statement: str, pa_ops_engine: Engine) -> None:
    """Assert that PostgreSQL denies the statement to the constrained login."""
    with pa_ops_engine.connect() as conn, pytest.raises(ProgrammingError) as error:
        conn.execute(text(statement))
    original = error.value.orig
    assert isinstance(original, InsufficientPrivilege)
    assert original.sqlstate == "42501"


@pytest.mark.parametrize(
    "statement",
    [
        "DELETE FROM app_user",
        "DELETE FROM task",
        "SELECT 1 FROM capability_run",
        "SELECT 1 FROM alembic_version",
        "UPDATE task SET name = name",
        "CREATE TABLE pa_ops_probe (x int)",
        "INSERT INTO capability_run DEFAULT VALUES",
    ],
)
def test_pa_ops_refuses_ungranted_statements(pa_ops_engine: Engine, statement: str) -> None:
    """The ops login cannot read or write outside its precise grant list."""
    _assert_refused(statement, pa_ops_engine)


def test_pa_ops_cannot_grant_admin_or_ops(pa_ops_engine: Engine, seeded_user: str) -> None:
    """The trigger rejects each privilege escalation with SQLSTATE 42501."""
    for column in ("is_admin", "is_ops"):
        with pa_ops_engine.connect() as conn, pytest.raises(ProgrammingError) as error:
            conn.execute(
                text(f"UPDATE app_user SET {column} = true WHERE user_id = :user_id"),
                {"user_id": seeded_user},
            )
        original = error.value.orig
        assert isinstance(original, InsufficientPrivilege)
        assert original.sqlstate == "42501"


def test_pa_ops_allows_the_current_positive_smoke(
    pa_ops_engine: Engine, seeded_admin_user: str
) -> None:
    """The role may clear a privilege, audit an action, and delete memberships."""
    with pa_ops_engine.begin() as conn:
        conn.execute(
            text("UPDATE app_user SET is_admin = false WHERE user_id = :user_id"),
            {"user_id": seeded_admin_user},
        )
        conn.execute(
            text(
                "INSERT INTO ops_action "
                "(action_id, at, actor_user_id, action, target, outcome) "
                "VALUES (:action_id, :at, 'operator', 'test', NULL, 'ok')"
            ),
            {"action_id": uuid.uuid4(), "at": datetime.now(UTC)},
        )
        conn.execute(text("DELETE FROM project_membership WHERE false"))
