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

# One test database per pytest-xdist worker (task 056, owner 2026-11-02). `make test`
# runs the suite on every core; the workers would otherwise share one Postgres
# database and trip over each other's rows. Each worker takes the database named in
# DATABASE_URL, appends its worker id and process id (``policy_atlas_test_gw3_8123``),
# creates that database fresh, and rewrites DATABASE_URL for its own process, so every later
# reader of the variable (the engine fixture, the migration and API tests) sees the
# worker's copy. The engine fixture then runs the migrations on it as before. The
# copies are dropped when the worker finishes. A run without xdist (``-p no:xdist``,
# or ``-n 0``) has no worker id and keeps the plain database.
_WORKER = os.environ.get("PYTEST_XDIST_WORKER")
if _WORKER and os.environ.get("DATABASE_URL"):
    import psycopg

    _base_url = os.environ["DATABASE_URL"]
    _head, _name = _base_url.rstrip("/").rsplit("/", 1)
    _name, _, _query = _name.partition("?")
    if not _name.lower().endswith("_test"):
        raise RuntimeError(f"refusing to copy a test database not named *_test: {_name!r}")
    # The process id keeps two suites running at once on one Postgres apart (their
    # workers share the names gw0, gw1, ...).
    _worker_name = f"{_name}_{_WORKER}_{os.getpid()}"
    # psycopg wants the plain scheme, not SQLAlchemy's "postgresql+psycopg".
    _base_dsn = _base_url.replace("postgresql+psycopg://", "postgresql://", 1)
    # The base database already exists (make reset-test-db); connect to it in
    # autocommit mode, because CREATE DATABASE cannot run inside a transaction.
    with psycopg.connect(_base_dsn, autocommit=True) as _c:
        _c.execute(f'DROP DATABASE IF EXISTS "{_worker_name}" WITH (FORCE)')
        _c.execute(f'CREATE DATABASE "{_worker_name}"')
    # Task 057: the chunk-retrieval query needs the pgvector extension in every database
    # the tests use. The compose user is a superuser; harmless where it already exists.
    _plain_head = _head.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(f"{_plain_head}/{_worker_name}", autocommit=True) as _c:
        _c.execute("CREATE EXTENSION IF NOT EXISTS vector")
    os.environ["DATABASE_URL"] = f"{_head}/{_worker_name}" + (f"?{_query}" if _query else "")

    import atexit

    def _drop_worker_db() -> None:
        try:
            with psycopg.connect(_base_dsn, autocommit=True) as c:
                c.execute(f'DROP DATABASE IF EXISTS "{_worker_name}" WITH (FORCE)')
        except Exception:  # noqa: BLE001 - best effort at interpreter exit
            pass

    atexit.register(_drop_worker_db)


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


@pytest.fixture(scope="session", autouse=True)
def _migrated_database() -> None:
    """Bring the worker's database to the current schema before any test.

    Tests that build their own client (``api_client``) never ask for the
    ``engine`` fixture, so they used to depend on an earlier test in the same
    worker having run the migrations: whichever test landed first on a fresh
    worker failed with a missing table. Task 058 added enough tests to change
    the order and expose it; the migration now runs once per worker, first.
    """
    # Idempotent: alembic checks the current head.
    command.upgrade(_alembic_cfg(), "head")


@pytest.fixture(scope="session")
def engine(_migrated_database: None) -> Generator[Engine, None, None]:
    e = create_engine(_db_url())
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
