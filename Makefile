.PHONY: setup test test-fast typecheck lint build verify verify-fast okf-validate audit audit-paths prompt-guard frontend-install openapi-sync drift-check font-guard frontend-verify fe-api-smoke deploy-build-guard-test

# Root orchestrator (025 A.2 monorepo hoist): the Python project lives in
# backend/; this Makefile owns the shared db service + the root-level gates
# (OKF conformance, cross-tree path audit) and delegates everything else so
# every pre-hoist target name keeps working unchanged from repo root.

setup:
	docker compose up -d db
	@echo "Waiting for Postgres to be healthy..."
	@# pg_isready alone races the postgres image's init-phase temporary server
	@# (it answers ready, then shuts down for the real start — seen in CI).
	@# Probe the actual database with a real query instead.
	@until docker compose exec -T db psql -U policy_atlas -d policy_atlas -tc "SELECT 1" >/dev/null 2>&1; do sleep 1; done
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

# Installs frontend dependencies from the committed lockfile (task 025 F.1).
# A prerequisite for drift-check (and any other frontend gate) in CI, where
# node_modules doesn't already exist; separated from drift-check itself so
# CI can cache/install once and reuse it across steps.
frontend-install:
	cd frontend && pnpm install --frozen-lockfile

# Regenerates both committed schema-first artifacts from the Pydantic
# contract (task 025 F.1): the OpenAPI document, then the TypeScript types
# generated from it. Run this whenever `make drift-check` fails.
openapi-sync:
	$(MAKE) -C backend openapi
	cd frontend && pnpm run gen

# Schema-first drift gate (task 025 F.1): one schema generates both API
# ends, so this fails the build the moment either committed artifact
# (frontend/openapi.json, frontend/src/api/gen/types.ts) stops matching what
# the backend contract actually produces. Requires frontend/node_modules
# (`make frontend-install`).
drift-check:
	@tmp_openapi=$$(mktemp) && \
	uv run --project backend python -m policy_atlas.api.export_openapi "$$tmp_openapi" && \
	if ! diff -u frontend/openapi.json "$$tmp_openapi"; then \
		echo "ERROR: frontend/openapi.json is stale relative to the backend contract." >&2; \
		echo "Run 'make openapi-sync' to regenerate it, then commit the result." >&2; \
		rm -f "$$tmp_openapi"; exit 1; \
	fi; \
	rm -f "$$tmp_openapi"
	@tmp_types=$$(mktemp) && \
	(cd frontend && pnpm exec openapi-typescript openapi.json -o "$$tmp_types") && \
	if ! diff -u frontend/src/api/gen/types.ts "$$tmp_types"; then \
		echo "ERROR: frontend/src/api/gen/types.ts is stale relative to frontend/openapi.json." >&2; \
		echo "Run 'make openapi-sync' to regenerate it, then commit the result." >&2; \
		rm -f "$$tmp_types"; exit 1; \
	fi; \
	rm -f "$$tmp_types"
	@echo "drift-check: OK"

# Font-binary guard (task 025, contract strand 7): Averta/Zosia are licensed
# for the web app but their binaries must NEVER be committed to this
# open-source repo — locally they live untracked and load via @font-face;
# everything must render on the fallback stack without them. Catches an
# accidental `git add -f`.
font-guard:
	@if git ls-files | grep -E '\.(woff2?|otf|ttf|eot)$$'; then \
		echo "ERROR: font binaries must never be committed (licensed assets)." >&2; exit 1; \
	fi
	@echo "font-guard: no font binaries tracked"

# The frontend gate lane (task 025 H): typecheck · lint · vitest · build.
# Requires frontend/node_modules (make frontend-install).
frontend-verify:
	cd frontend && pnpm typecheck && pnpm lint && pnpm test && pnpm build

# Thin browser smoke against the real local API: fresh dev-issuer credentials,
# real Postgres, real CORS/base URL/auth transport, and the API SSE stream.
# The script owns process lifecycle and leaves its temporary issuer material
# behind only for the duration of the command.
fe-api-smoke:
	bash scripts/fe_api_smoke.sh

# Verifies deploy.sh's production VITE_* refusal directly once D.1 lands.
# It deliberately reports a clear skip while that documented interface is absent.
deploy-build-guard-test:
	bash scripts/test_deploy_build_guard.sh

verify:
	@if ! docker compose exec db pg_isready -U policy_atlas -q 2>/dev/null; then \
		echo "ERROR: Postgres is not running. Run 'make setup' first." >&2; exit 1; \
	fi
	$(MAKE) okf-validate
	$(MAKE) -C backend verify
	$(MAKE) -C infra test
	$(MAKE) audit-paths
	$(MAKE) prompt-guard
	$(MAKE) font-guard
	$(MAKE) drift-check
	$(MAKE) frontend-verify

# Intermediate phase-commit gate (011 retro): test-fast + typecheck + lint.
# Full `make verify` remains mandatory at the build-open baseline, any phase
# touching schema or ingest-adjacent code, and the step-6 exit.
verify-fast:
	$(MAKE) -C backend verify-fast
