.PHONY: setup dev dev-seed test test-fast typecheck lint build verify verify-fast okf-validate audit audit-paths prompt-guard frontend-install openapi-sync drift-check font-guard frontend-verify fe-api-smoke deploy-build-guard-test infra-setup deploy-check deploy-update deploy-bootstrap

# Root orchestrator (025 A.2 monorepo hoist): the Python project lives in
# backend/; this Makefile owns the shared db service + the root-level gates
# (OKF conformance, cross-tree path audit) and delegates everything else so
# every pre-hoist target name keeps working unchanged from repo root.

setup:
	docker compose up -d db
	@echo "Waiting for Postgres to be healthy..."
	@# The postgres image starts a temporary server during init, answers
	@# queries, then shuts down for the real start. One successful SELECT is
	@# not enough — require two in a row, then retry createdb until it sticks.
	@ready=0; \
	until [ $$ready -ge 2 ]; do \
	  if docker compose exec -T db psql -U policy_atlas -d policy_atlas -tc "SELECT 1" >/dev/null 2>&1; then \
	    ready=$$((ready + 1)); \
	  else \
	    ready=0; \
	  fi; \
	  sleep 1; \
	done
	@echo "DB ready."
	@until docker compose exec -T db psql -U policy_atlas -tc \
		"SELECT 1 FROM pg_database WHERE datname='policy_atlas_test'" 2>/dev/null | grep -q 1 \
		|| docker compose exec -T db createdb -U policy_atlas policy_atlas_test; do sleep 1; done
	@echo "Test DB ready (policy_atlas_test)."
	$(MAKE) -C backend setup

# Ops CLI wrappers (owner request, 2026-08-25). The old `staging-user` /
# `prod-user` / `cognito-user` targets stay deleted (they took a password on
# argv, suppressed the invitation, and left the account unenrolled — pinned by
# test_the_user_provisioning_make_targets_are_deleted). These wrappers avoid
# what killed them:
#   - no credential on argv or in a variable: scripts/ops_run.sh assembles
#     DATABASE_URL in-process from Secrets Manager, opens/reuses the § 6
#     tunnel, checks the AWS session, and fetches the pool id from SSM.
#     PA_OPS_ACCOUNT_<ENV> stays operator-exported — deriving it here would
#     make the environment guard's account leg a tautology;
#   - the targets only map VAR names to flag names and forward. The CLI's own
#     parser is the sole grammar authority: mutually exclusive pairs
#     (EMAIL/SUB, PROJECT/PORTFOLIO) are forwarded as given and ITS refusal is
#     the error you see;
#   - backend/tests/ops/test_make_wrappers.py dry-runs every target and parses the
#     assembled argv with the real parser, so Makefile↔CLI drift fails `make
#     verify`;
#   - the tty passes through, so the environment guard's typed day-zero
#     confirmation still reaches a human.
# Usage: make user-create ENV=staging EMAIL=a@b.org NAME="A Name" ORG="Org"
# Optional on every target: OPERATOR="ticket-123" (an annotation; the STS ARN
# is logged regardless).
# The wrappers forward through scripts/ops_run.sh to the real CLI
# (`uv run python -m policy_atlas.ops`); see that package for the command tree.
# OPS_COMMON rides immediately after ENV because --operator is a top-level
# flag: argparse refuses it after the subcommand (pinned by the wrapper tests).
ops-require = $(foreach v,$(1),$(if $($(v)),,$(error $(v)=... is required for this target)))
OPS_COMMON = $(if $(OPERATOR),--operator "$(OPERATOR)")

.PHONY: org-create user-create user-enrol user-resync user-de-enrol rows-assign admin-grant admin-revoke

org-create:
	@$(call ops-require,ENV NAME) scripts/ops_run.sh $(ENV) $(OPS_COMMON) org create --name "$(NAME)"
user-create:
	@$(call ops-require,ENV EMAIL NAME ORG) scripts/ops_run.sh $(ENV) $(OPS_COMMON) user create --email "$(EMAIL)" --display-name "$(NAME)" --org "$(ORG)" $(if $(INVITE),--invite "$(INVITE)")
user-enrol:
	@$(call ops-require,ENV EMAIL NAME ORG) scripts/ops_run.sh $(ENV) $(OPS_COMMON) user enrol --email "$(EMAIL)" --display-name "$(NAME)" --org "$(ORG)"
user-resync:
	@$(call ops-require,ENV EMAIL) scripts/ops_run.sh $(ENV) $(OPS_COMMON) user resync --email "$(EMAIL)"
user-de-enrol:
	@$(call ops-require,ENV) scripts/ops_run.sh $(ENV) $(OPS_COMMON) user de-enrol $(if $(EMAIL),--email "$(EMAIL)") $(if $(SUB),--sub "$(SUB)")
rows-assign:
	@$(call ops-require,ENV ORG) scripts/ops_run.sh $(ENV) $(OPS_COMMON) rows assign $(if $(PROJECT),--project "$(PROJECT)") $(if $(PORTFOLIO),--portfolio "$(PORTFOLIO)") --org "$(ORG)"
admin-grant:
	@$(call ops-require,ENV) scripts/ops_run.sh $(ENV) $(OPS_COMMON) admin grant $(if $(EMAIL),--email "$(EMAIL)") $(if $(SUB),--sub "$(SUB)")
admin-revoke:
	@$(call ops-require,ENV) scripts/ops_run.sh $(ENV) $(OPS_COMMON) admin revoke $(if $(EMAIL),--email "$(EMAIL)") $(if $(SUB),--sub "$(SUB)")

# Run the whole app locally: API on :8000 + Vite on :5173, one Ctrl-C stops
# both. Self-contained auth: initialises the dev issuer on first run
# (backend/.dev-issuer, gitignored), mints a fresh 4h token, and injects it
# as VITE_DEV_TOKEN so the SPA signs in by itself.
dev:
	@! lsof -ti :8000 -sTCP:LISTEN >/dev/null || \
	  { echo "port 8000 already in use:"; lsof -i :8000 -sTCP:LISTEN; exit 1; }
	@test -d backend/.dev-issuer || \
	  (cd backend && uv run python -m policy_atlas.api.dev_issuer init --dir .dev-issuer)
	@(trap 'kill 0' INT TERM EXIT; \
	  $(MAKE) -C backend dev & \
	  token=$$(cd backend && uv run python -m policy_atlas.api.dev_issuer mint \
	    --dir .dev-issuer --sub dev-user --client-id policy-atlas-dev \
	    --ttl 14400 2>/dev/null | tail -1); \
	  cd frontend && VITE_DEV_TOKEN="$$token" pnpm dev & \
	  wait)

# Seed the LOCAL dev DB with "Dev Org" + three enrolled identities so the 033
# tenancy UI is visible in `make dev` (which signs in as dev-user, the owner).
# Local-only: the script refuses non-localhost hosts and *_test databases.
dev-seed:
	uv run --project backend python scripts/dev_org_seed.py

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

# GitHub Actions and operators share these deployment entry points. DEPLOY_ENV
# selects one committed environment across infra/*_config.json; deploy-check is
# intentionally side-effect-free so workflows can fail before requesting OIDC.
infra-setup:
	$(MAKE) -C infra setup

deploy-check:
	@test -n "$(DEPLOY_ENV)" || \
		{ echo "usage: make deploy-check DEPLOY_ENV=<environment>" >&2; exit 2; }
	PA_DEPLOY_ENV_NAME="$(DEPLOY_ENV)" bash scripts/deploy.sh check

deploy-update: deploy-check infra-setup
	PA_DEPLOY_ENV_NAME="$(DEPLOY_ENV)" bash scripts/deploy.sh update

deploy-bootstrap: deploy-check infra-setup
	PA_DEPLOY_ENV_NAME="$(DEPLOY_ENV)" bash scripts/deploy.sh bootstrap

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
