# Policy Atlas v3.0

An evidence-led policy-analysis workspace: capabilities run bounded, inspectable
pipelines over an acquired evidence corpus and produce grounded artefacts - evidence
syntheses whose significant claims carry citations, verbatim quotes and appraisal. 
The v3.0 backend ships one capability,
the **Evidence Base**: plan → acquire → screen → classify → appraise → ingest →
(characterise · select · extract · group, plan-selected) → synthesise.

Product intent and system contracts live in [`docs/specs/`](docs/specs/index.md);
architectural decisions in [`docs/adr/`](docs/adr/); per-task plans and evidence
in [`docs/tasks/`](docs/tasks/).

## Layout

```
backend/                     Python project (import-neutral hoist, task 025 A.2)
backend/src/policy_atlas/
  runtime/                   agent CLI, capability runner, LangGraph harness,
                             planner, steering, run-spec compile
  evidence_search/           the EB capability
    sourcing/                search backends + loop, acquisition, full-text ingest
    assess/                  screening, classification, appraisal
    corpus/                  characterise, select, ranking, theme grouping
    extract/                 Intervention, outcome and context findings extraction, vetters, quote verification
    group/                   multi-facet grouping over extracted findings
    synthesis/               artefact composition, section generation loop, grounding judge
  core/                      schema, db, events, logging, tracing, usage, model-client
                             plumbing, embeddings
backend/alembic/             database migrations
backend/tests/               mirrors the src tree; conftest runs migrations once per session;
                             backend/tests/data/ holds all fixtures (full-text corpus +
                             sanitized provider records)
frontend/                    web app — React 19 + TS strict + Vite + Tailwind (task 025)
infra/                       CDK (reserved)
docs/              specs, ADRs, task records, knowledge base, agentic-ops
```

## Setup

Requires Python ≥ 3.12, [uv](https://docs.astral.sh/uv/), Docker (Postgres), Node ≥ 20
and [pnpm](https://pnpm.io) 10+ (see `frontend/README.md` for pnpm install options).

```sh
docker compose up -d      # Postgres (dev + test databases)
make setup                # uv sync + test DB provisioning
make verify               # okf-validate · tests · mypy · ruff · build · frontend gates
make verify-fast          # inner-loop variant (skips the slow ingest suite)
```

## Running the web app (backend + frontend)

A fresh clone reaches a running app in the steps below (≤ 30 min budget). All
commands are given relative to the repo root unless noted; `backend/` commands
run from `backend/` (`make -C backend <target>` from the root works the same).

**1. Backend config.** Copy the example env file and fill in the dev-issuer
values (defaults are pre-filled and work as-is for local dev):

```sh
cp backend/.env.example backend/.env
```

`uv run` auto-loads `backend/.env` — nothing else to export. See the file for
what each variable does; `DATABASE_URL`/`APP_ORIGIN`/`OIDC_*` are required by
`make -C backend dev`.

**2. Dev-issuer bootstrap** (once — issues a local RSA keypair; never used in
production, where Cognito is the real issuer):

```sh
cd backend
uv run python -m policy_atlas.api.dev_issuer init --dir .dev-issuer
uv run python -m policy_atlas.api.dev_issuer mint --dir .dev-issuer \
  --sub dev-user --client-id policy-atlas-dev  # prints a bearer token — copy it
```

**3. Backend dev server** (from `backend/`, or `make -C backend dev` from root):

```sh
make -C backend dev       # uvicorn --reload on :8000
curl http://localhost:8000/healthz   # => {"status": "ok"}
```

The API composes **stub** planner/search backends by default and goes live
when `OPENAI_API_KEY` is set; `PA_BACKEND_MODE=live|stub|auto` makes the
posture explicit (see `backend/.env.example`).

**4. Frontend dev server** (from `frontend/`; installs once with `pnpm install`):

```sh
cd frontend
pnpm install
pnpm dev                  # Vite on :5173, proxying /api/* to :8000
```

Open <http://localhost:5173>. With no `VITE_OIDC_AUTHORITY` set (the default),
the app shows a dev-only "paste a dev token" panel — paste the token minted in
step 2 to sign in.

**5. Mock-mode journey** (no backend/Postgres/auth required — a scripted
fixture project + SSE narrative, used by the Playwright acceptance journey):

```sh
cd frontend
pnpm exec playwright install chromium   # once
VITE_MOCK=1 pnpm dev                    # or just `pnpm e2e` below, which starts its own server
pnpm e2e                                # runs playwright test against a VITE_MOCK=1 dev server
```

`pnpm e2e` starts its own `VITE_MOCK=1` dev server — but it will **reuse any
dev server already on :5173, including a plain (non-mock) one**, and every
spec then fails at the sign-in panel. If you had `pnpm dev` running for step
4, stop it before `pnpm e2e`.

## Running the agent CLI 

The capability-runner CLI is the non-web entry point:

```sh
uv run --project backend python -m policy_atlas.runtime.agent
```

## Licence

AGPL-3.0-only (see [LICENSE](LICENSE)).
