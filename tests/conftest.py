"""Test fixtures.

The `conn` fixture runs the real Alembic migration once per session, then gives
each test a connection inside a transaction that rolls back — clean isolation
without re-migrating on every test.
"""

import os
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

load_dotenv()


def _alembic_cfg() -> AlembicConfig:
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", _db_url())
    return cfg


def _db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.fail(
            "DATABASE_URL is not set. Run 'make setup' to start Postgres, "
            "then set DATABASE_URL=postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas"
        )
    return url


@pytest.fixture(scope="session")
def engine() -> Generator[Engine, None, None]:
    e = create_engine(_db_url())
    # Apply migration (idempotent — alembic checks current head)
    command.upgrade(_alembic_cfg(), "head")
    yield e
    e.dispose()


@pytest.fixture
def conn(engine: Engine) -> Generator[Connection, None, None]:
    with engine.connect() as connection:
        trans = connection.begin()
        try:
            yield connection
        finally:
            trans.rollback()
