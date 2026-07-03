.PHONY: setup test typecheck lint build verify okf-validate

# Tests run against a dedicated database on the same local container, so committing
# tests can't pollute the dev DB. Override for a different host/DB.
TEST_DATABASE_URL ?= postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas_test

setup:
	uv sync
	docker compose up -d db
	@echo "Waiting for Postgres to be healthy..."
	@until docker compose exec db pg_isready -U policy_atlas -q; do sleep 1; done
	@echo "DB ready."
	@docker compose exec -T db psql -U policy_atlas -tc \
		"SELECT 1 FROM pg_database WHERE datname='policy_atlas_test'" | grep -q 1 \
		|| docker compose exec -T db createdb -U policy_atlas policy_atlas_test
	@echo "Test DB ready (policy_atlas_test)."
	uv run alembic upgrade head

test:
	DATABASE_URL="$(TEST_DATABASE_URL)" uv run pytest

typecheck:
	uv run mypy src tests

lint:
	uv run ruff check src tests

build:
	uv build

okf-validate:
	uv run python scripts/okf_validate.py

verify:
	@if ! docker compose exec db pg_isready -U policy_atlas -q 2>/dev/null; then \
		echo "ERROR: Postgres is not running. Run 'make setup' first." >&2; exit 1; \
	fi
	$(MAKE) okf-validate
	$(MAKE) test
	$(MAKE) typecheck
	$(MAKE) lint
	$(MAKE) build
