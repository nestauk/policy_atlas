.PHONY: setup test test-fast typecheck lint build verify verify-fast okf-validate audit audit-paths prompt-guard

# Root orchestrator (025 A.2 monorepo hoist): the Python project lives in
# backend/; this Makefile owns the shared db service + the root-level gates
# (OKF conformance, cross-tree path audit) and delegates everything else so
# every pre-hoist target name keeps working unchanged from repo root.

setup:
	docker compose up -d db
	@echo "Waiting for Postgres to be healthy..."
	@until docker compose exec db pg_isready -U policy_atlas -q; do sleep 1; done
	@echo "DB ready."
	@docker compose exec -T db psql -U policy_atlas -tc \
		"SELECT 1 FROM pg_database WHERE datname='policy_atlas_test'" | grep -q 1 \
		|| docker compose exec -T db createdb -U policy_atlas policy_atlas_test
	@echo "Test DB ready (policy_atlas_test)."
	$(MAKE) -C backend setup

test:
	$(MAKE) -C backend test

test-fast:
	$(MAKE) -C backend test-fast

typecheck:
	$(MAKE) -C backend typecheck

lint:
	$(MAKE) -C backend lint

build:
	$(MAKE) -C backend build

okf-validate:
	uv run --project backend python scripts/okf_validate.py

# Dependency-vulnerability audit (016 contract rev 2.2) — delegates to backend,
# where the locked dependency set actually lives.
audit:
	$(MAKE) -C backend audit

# Cross-tree path audit (025 A.2): fails if a tracked file references a
# hoisted backend/ path as repo-root-relative instead of backend/-relative.
audit-paths:
	uv run --project backend python scripts/audit_paths.py

# Prompt-family content-hash guard (task 025 C.4): fails if any prompt-bearing
# module drifted from its committed hash (scripts/prompt_hashes.json) — prompt
# surfaces change only as named, deliberate slice work.
prompt-guard:
	uv run --project backend python scripts/prompt_hash_guard.py

verify:
	@if ! docker compose exec db pg_isready -U policy_atlas -q 2>/dev/null; then \
		echo "ERROR: Postgres is not running. Run 'make setup' first." >&2; exit 1; \
	fi
	$(MAKE) okf-validate
	$(MAKE) -C backend verify
	$(MAKE) audit-paths
	$(MAKE) prompt-guard

# Intermediate phase-commit gate (011 retro): test-fast + typecheck + lint.
# Full `make verify` remains mandatory at the build-open baseline, any phase
# touching schema or ingest-adjacent code, and the step-6 exit.
verify-fast:
	$(MAKE) -C backend verify-fast
