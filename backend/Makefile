.PHONY: setup test test-fast typecheck lint build verify verify-fast okf-validate audit

# Tests run against a dedicated database on the same local container, so committing
# tests can't pollute the dev DB. Override for a different host/DB.
TEST_DATABASE_URL ?= postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas_test

# DB is the root Makefile's job (docker compose lives at repo root); this target
# only provisions the Python side.
setup:
	uv sync
	uv run alembic upgrade head

test:
	DATABASE_URL="$(TEST_DATABASE_URL)" uv run pytest

# Inner-loop convenience: everything except the ingest integration tests (~11 real
# document-ingest runs, minutes). Full `make test` / `make verify` remain the gate.
test-fast:
	DATABASE_URL="$(TEST_DATABASE_URL)" uv run pytest --ignore=tests/test_ingest_full_text.py

typecheck:
	uv run mypy src tests

lint:
	uv run ruff check src tests

build:
	uv build

# Dependency-vulnerability audit (016 contract rev 2.2): PyPA/OSV advisories over
# the locked dependency set. Audits the synced environment (= the uv.lock closure;
# the editable first-party project is the one expected skip) rather than an
# exported requirements file: pip-audit's `-r` mode builds a throwaway venv via
# ensurepip, which SIGABRTs under uv-managed CPython on macOS — environment mode
# audits the same pinned set with no venv, identically local and CI.
# Ignore-list policy: an accepted advisory is an explicit `--ignore-vuln <ID>`
# argument here, each carrying an adjacent comment justifying it. Currently none.
audit:
	uv run --with pip-audit pip-audit --skip-editable --progress-spinner=off

# DB pre-check: CWD is backend/ here, so `docker compose` must resolve the root
# compose file from the parent dir. Compose v2 walks up looking for
# docker-compose.yml, which finds it in most setups; if it doesn't on a given
# machine, point it explicitly with `-f ../docker-compose.yml`.
verify:
	@if ! docker compose exec db pg_isready -U policy_atlas -q 2>/dev/null; then \
		if ! docker compose -f ../docker-compose.yml exec db pg_isready -U policy_atlas -q 2>/dev/null; then \
			echo "ERROR: Postgres is not running. Run 'make setup' from repo root first." >&2; exit 1; \
		fi \
	fi
	$(MAKE) test
	$(MAKE) typecheck
	$(MAKE) lint
	$(MAKE) build

# Intermediate phase-commit gate (011 retro): test-fast + typecheck + lint.
# Full `make verify` remains mandatory at the build-open baseline, any phase
# touching schema or ingest-adjacent code, and the step-6 exit.
verify-fast:
	@if ! docker compose exec db pg_isready -U policy_atlas -q 2>/dev/null; then \
		if ! docker compose -f ../docker-compose.yml exec db pg_isready -U policy_atlas -q 2>/dev/null; then \
			echo "ERROR: Postgres is not running. Run 'make setup' from repo root first." >&2; exit 1; \
		fi \
	fi
	$(MAKE) test-fast
	$(MAKE) typecheck
	$(MAKE) lint
