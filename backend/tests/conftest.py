"""Test fixtures.

The `conn` fixture runs the real Alembic migration once per session, then gives
each test a connection inside a transaction that rolls back — clean isolation
without re-migrating on every test.
"""

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

load_dotenv()

# The suite is zero-egress by policy (socket-deny) and every live/stub switch
# keys off these variables — a developer's real backend/.env must never flip
# a test onto a live code path (task 025 live-check finding: the CLI pin
# test drove `orchestrate.main` straight into the OpenAI branch). Scrub the
# product-egress keys the .env may carry; DATABASE_URL and friends survive.
for _egress_key in (
    "OPENAI_API_KEY",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_HOST",
    "LANGFUSE_BASE_URL",
    "OVERTON_API_KEY",
    "OPENALEX_API_KEY",
):
    os.environ.pop(_egress_key, None)

# Fixture corpus moved out of the package (contract decision 12, task 016) — point
# FixtureFetcher's default resolution at the repo test-data home for the suite.
os.environ.setdefault("POLICY_ATLAS_FIXTURE_CORPUS", str(Path(__file__).parent / "data"))


def _alembic_cfg() -> AlembicConfig:
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", _db_url())
    return cfg


DEV_DB_NAME = "policy_atlas"  # the dev database; tests must not run here (they commit)


def _db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.fail(
            "DATABASE_URL is not set. Run 'make setup', then 'make test' "
            "(it targets the policy_atlas_test database)."
        )
    # Match is intentionally host-agnostic and name-based: block the dev DB name on any host.
    # (A differently-named prod/Aurora DB is out of scope — make test never targets it.)
    db_name = url.rstrip("/").rsplit("/", 1)[-1].split("?")[0].lower()
    if db_name == DEV_DB_NAME:
        pytest.fail(
            f"Refusing to run tests against the dev database {DEV_DB_NAME!r} — tests commit and "
            "would pollute it. Use 'make test' (targets policy_atlas_test), or point DATABASE_URL "
            "at a disposable *_test database."
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
