.PHONY: setup test typecheck lint build verify

setup:
	uv sync
	docker compose up -d db
	@echo "Waiting for Postgres to be healthy..."
	@until docker compose exec db pg_isready -U policy_atlas -q; do sleep 1; done
	@echo "DB ready."
	uv run alembic upgrade head

test:
	uv run pytest

typecheck:
	uv run mypy src tests

lint:
	uv run ruff check src tests

build:
	uv build

verify:
	@if ! docker compose exec db pg_isready -U policy_atlas -q 2>/dev/null; then \
		echo "ERROR: Postgres is not running. Run 'make setup' first." >&2; exit 1; \
	fi
	$(MAKE) test
	$(MAKE) typecheck
	$(MAKE) lint
	$(MAKE) build
