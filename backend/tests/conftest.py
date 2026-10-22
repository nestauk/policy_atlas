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
# test drove `agent.main` straight into the OpenAI branch). Scrub the
# product-egress keys the .env may carry; DATABASE_URL and friends survive.
for _egress_key in (
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "AWS_BEARER_TOKEN_BEDROCK",
    "POLICY_ATLAS_MODEL_ROUTE",
    "POLICY_ATLAS_MODEL_ROUTE_FILE",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_HOST",
    "LANGFUSE_BASE_URL",
    "OVERTON_API_KEY",
    "OPENALEX_API_KEY",
):
    os.environ.pop(_egress_key, None)

# boto3 resolves credentials when a client is built. With none configured (CI), the
# chain ends by asking the EC2 instance-metadata address, which socket-deny turns
# into an HTTPClientError at construction (task 053 CI failure). A developer's
# machine has ~/.aws credentials, so the probe never ran locally. Disable it: the
# Cohere and Claude clients are then built with no credentials, which only matters
# at request time, and the suite never sends one.
os.environ["AWS_EC2_METADATA_DISABLED"] = "true"

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


@pytest.fixture(autouse=True)
def _empty_search_cache() -> Generator[None, None, None]:
    """Start every test with an empty provider-response cache.

    The live transport caches responses in a module-level store keyed by URL
    and parameters (the key never carries the API key), with a one-hour life.
    Two tests that build a live backend around a scripted fetch and ask for
    the same page share that store, so one test's reply answered the other's
    request (found at the task 051 review, 2026-10-09: an Overton page-2 reply
    without a next page cut a later test's search to two pages).
    """
    from policy_atlas.evidence_search.sourcing import search_live

    with search_live._SEARCH_CACHE_LOCK:
        search_live._SEARCH_CACHE.clear()
    yield
