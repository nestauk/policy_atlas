# Environment

How to start a working local environment, and the problems that are known to occur. This file
describes the repository as it is now. When the setup changes, change this file in the same pull
request (PR). It is not a change log: the history is in git and in each task's `verification.md`.

## Prerequisites

- **uv** (the Python package and virtual-environment manager) and **Python 3.12**.
- **Docker** (it runs the local Postgres database).
- **Node.js** 20 or later (continuous integration (CI) uses Node 24) and **pnpm** (the frontend
  package manager). `frontend/package.json` (`packageManager`) pins the pnpm version. Install pnpm
  as a standalone tool: Corepack is not in Node 25. CI installs pnpm the same way, from the
  `packageManager` field in `frontend/package.json`, so a standalone pnpm matches CI.
- **direnv** is optional. `.envrc` only runs `source .venv/bin/activate`, so run `make setup` first.

## Setup commands

```
cp backend/.env.example backend/.env   # the template; it gives DATABASE_URL
make setup                             # starts Postgres, waits for it, creates policy_atlas_test,
                                       # then runs `uv sync` and `alembic upgrade head` in backend/
make frontend-install                  # installs the frontend packages from the lockfile
make verify                            # the full check (see harness.md § Verification layer)
make dev                               # API on :8000 and web app on :5173, signed in as dev-user
make dev-seed                          # optional: adds "Dev Org" and two more users to the dev database
```

`make setup` is safe to run again. `make verify` stops with a clear error if Postgres is not
running. `make verify` needs `frontend/node_modules`, so run `make frontend-install` first.

After you pull a change:

- If it adds a database migration, run `uv run alembic upgrade head` in `backend/`. This updates
  the **dev** database. Only the test database is migrated by the tests.
- If it adds frontend packages, run `make frontend-install`.
- If the Postgres image changed, run `docker compose pull db`, then `make setup`.

## Required services

- **Postgres 17 with pgvector** (a vector-search extension) through Docker Compose: service `db`,
  image `pgvector/pgvector:pg17`. It matches the cloud database engine (Amazon Aurora), and the
  chunk-retrieval query uses the `vector` type.
- It listens on **127.0.0.1:5432** only.
- User and password are `policy_atlas`. These are local values, not secrets.
- Databases on the one container:
  - `policy_atlas`: the dev database (`make dev`, `make dev-seed`).
  - `policy_atlas_test`: the test base. `make test` and `make test-fast` drop and recreate it at
    the start of each run, then each test worker makes its own copy (`backend/tests/conftest.py`).
  - `policy_atlas_smoke`: a disposable database for `make fe-api-smoke`.

## Seed data

- `make dev-seed` adds the organisation "Dev Org" with `dev-user` (owner), `dev-colleague` and
  `dev-admin` to the local dev database. The script refuses any host other than localhost and any
  `*_test` database.
- Test fixtures live under `backend/tests/data/` (provider records, full-text documents and
  replay data) and `backend/tests/provider_fixtures.py`. A run with no keys uses this data.

## Test accounts

- Local: `make dev` starts a local sign-in issuer (`backend/.dev-issuer`, gitignored), creates a
  token for `dev-user` and gives it to the web app. A token lives 4 hours.
- Cloud (staging and production): accounts live in Amazon Cognito (the cloud sign-in service).
  Manage them with the `make user-*`, `org-create`, `rows-assign` and `admin-*` targets. The root
  `Makefile` comments explain the arguments.

## Local env vars

`backend/.env.example` is the template for a local run and gives each of its variables a
comment. The full list of server settings is `backend/src/policy_atlas/api/settings.py`. The
groups:

- **Database.** `DATABASE_URL` (required). `TEST_DATABASE_URL` defaults to `policy_atlas_test`;
  `make test` passes it to the tests as `DATABASE_URL`, so tests never touch the dev database.
- **Web API.** `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_JWKS_PATH` (or `OIDC_JWKS_URL`) and
  `APP_ORIGIN`.
- **Backend mode.** `PA_BACKEND_MODE=live|stub|auto`. `auto` goes live when the route's key is
  set. `live` fails at start if the route's key is missing.
- **Model route.** `POLICY_ATLAS_MODEL_ROUTE` picks the route; unset means `openai-direct`. The
  deployed environments use `bedrock` (`infra/pa_config.json`). Each route names its key:
  `OPENAI_API_KEY` for `openai-direct`, `AWS_BEARER_TOKEN_BEDROCK` for the Bedrock routes. Models,
  reasoning effort and cache mode per step come from `backend/src/policy_atlas/model_routes.toml`.
  The old `POLICY_ATLAS_*_MODEL` variables are ignored, with one warning.
- **Search.** `OPENALEX_API_KEY` and `OVERTON_API_KEY` turn on live search. Set both or neither.
- **Evaluation only.** `SEMANTIC_SCHOLAR_API_KEY` (free) and `CONSENSUS_API_KEY` (paid per call).
  Only `scripts/evals/search/` reads them, never the product.
- **Tracing.** `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and `LANGFUSE_HOST` (all three)
  send traces to Langfuse.
- **Features.** `POLICY_ATLAS_THEORY_OF_CHANGE=1` lets the API create theory-of-change tasks.
  The web app reads `VITE_THEORY_OF_CHANGE=1` and `VITE_OPTIONS_SCOPING=1` when it is built or
  started.
  `make dev` sets all three. `VITE_MOCK=1` runs the web app against mock data, with no API.
- **Limits.** `RUNS_PER_USER` (default 3) is the number of runs one user can have at the same
  time. `TASK_QUOTA_PER_YEAR` (default 50) is the number of tasks one user can create in 365
  days; administrators are exempt. `make dev` sets the quota to 100000, so the local user is
  never refused.
- **Uploads.** Uploaded files go to `POLICY_ATLAS_UPLOAD_BUCKET` in the cloud, or to
  `POLICY_ATLAS_UPLOAD_DIR` locally (default `backend/.uploads`, gitignored).
- **Ingest.** `POLICY_ATLAS_INGEST_MODE` is `in_process` (the default) or `queued`. `queued` also
  needs `POLICY_ATLAS_INGEST_QUEUE_URL`. Only the cloud uses `queued`.

Where the variables are read:

- `make dev` and `make -C backend dev` load `backend/.env` through `uv run --env-file`. The
  application settings read only the process environment.
- The tests load `backend/.env` (for `DATABASE_URL`), then remove the model, search and Langfuse
  keys (`backend/tests/conftest.py`). So a key in your `.env` never turns a test live.

## Secret policy

- `.env` is gitignored, and `.claude/settings.json` denies agents read and write access to it.
  Only `.env.example` (a template with no secrets) is committed.
- Real credentials go in `.env` (local) or a secret manager (deployed). Never commit them. Never
  paste them into prompts, traces or logs.

## Network policy

- **Runtime egress** means the running product sends data to an outside service. The product
  calls:
  - the model provider of the selected route (OpenAI or Amazon Bedrock). Uploaded files are sent
    to it for reading;
  - the search services (OpenAlex and Overton) when their keys are set;
  - document hosts, to fetch full text (Europe PMC at `www.ebi.ac.uk` receives only a PubMed
    Central id);
  - Langfuse, when its keys are set.
- A slice that adds runtime egress needs approval (the hard gates in the `task-cycle` skill).
- The tests make no network calls. `pytest-socket` blocks every socket except loopback.
- Agent and developer network use is not gated: package installs, image pulls, documentation
  fetches, Model Context Protocol (MCP) servers.

## Browser verification

- `make dev`, then open `http://localhost:5173`. For screenshots, use Playwright against the live
  dev app (see `docs/knowledge/` for the method).
- `make fe-api-smoke`: a short browser test of the built web app against the real local API and
  the `policy_atlas_smoke` database.
- `cd frontend && pnpm e2e`: the mock-data browser journey (`VITE_MOCK=1`, no backend).

## CI parity

CI ([.github/workflows/verify.yml](../../.github/workflows/verify.yml)) runs the same Makefile
targets as a local run, so the two stay the same. Jobs on every PR and every push to `dev`:

- `verify`: `make setup`, `make frontend-install`, `make verify`. This job is a required check
  for a merge to `dev`.
- `fe-api-smoke`: `make fe-api-smoke` and `make deploy-build-guard-test`.
- `mock-journey`: `pnpm e2e`.
- `audit`: `make audit` (known vulnerabilities in the locked Python packages).

`deploy-staging.yml` deploys `dev` to staging after `verify` passes on a push to `dev`.
`deploy-production.yml` runs only when started by hand. If local and CI results differ, fix the
workflow, not the Makefile.

## Known environment quirks

- **The dev database does not migrate itself.** A stale dev database fails mid-run with
  `UndefinedTable`. Run `uv run alembic upgrade head` in `backend/`.
- **Some migration downgrades refuse while their data exists.** The ADR (architecture decision
  record) § Rollback for that migration names the clean-up script, for example
  `scripts/ops_remove_toc_tasks.py` or `scripts/ops_remove_scoping_tasks.py`.
- **The tests refuse the dev database.** `conftest` stops if `DATABASE_URL` names
  `policy_atlas`, because the tests commit rows.
- **One test run per test database name.** `make test` drops its base database with
  `dropdb --force` at the start, so a second run on the same Postgres breaks the first. Give the
  second run its own `TEST_DATABASE_URL`, with a name that ends in `_test`.
- **The backend runs as one worker process.** The start and add reservations are held in the API
  process ([ADR 0039](../adr/0039-options-scoping-longlist-option-searches-and-option-records.md)).
- **A script that runs the live chain needs an `if __name__ == "__main__":` guard.** The
  full-text parse workers are child processes that import the entry module again. Without the
  guard, each worker runs the whole live chain again and spends money.
- **Git worktrees do not find the shared dev Postgres.** `docker compose` takes its project name
  from the directory. In a worktree, set `COMPOSE_PROJECT_NAME=policy_atlas` (for example
  `COMPOSE_PROJECT_NAME=policy_atlas make verify`).
- **Check a red baseline with an isolated rerun.** Another process on the same Postgres can leave
  rows that fail tests. Run `make test` alone before you blame the slice.
- **A dev token lives 4 hours.** To make a new one, run this from `backend/`:
  `uv run python -m policy_atlas.api.dev_issuer mint --dir .dev-issuer --sub dev-user --client-id policy-atlas-dev --ttl 14400`.
- **One vitest timeout on a busy machine is load, not a fault.** Rerun when the machine is quiet.
- **A page with an open event stream never reaches Playwright's `networkidle`.** Wait for
  `domcontentloaded` and a fixed time.
- **A new run-stage key changes the OpenAPI document** (the generated API description).
  `make drift-check` fails until you run `make openapi-sync`.
- **A session restart stops a background `make verify` and leaves no record.** If the log shows
  the earlier steps green, rerun only the step that was running.
