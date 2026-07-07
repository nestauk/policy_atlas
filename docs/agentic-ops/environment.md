# Environment

How to bring up a working local environment and the gotchas that bite. Reflects the repo as it
stands (tasks 001–012 — backend only; setup unchanged since 002; task 007 adds two dev-time
fixture-recorder scripts needing `OVERTON_API_KEY`/optional OpenAlex vars in `.env` — see
`.env.example`; task 008 adds parsing deps (pymupdf/pymupdf4llm/trafilatura — arrive via
`make setup`/`uv sync`) and a keyless dev-time recorder using system `curl`; task 009 adds
`openai` + `langfuse` deps (via `uv sync`) and three **optional** live-route vars —
`OPENAI_API_KEY` makes the skeleton entrypoint go live (real embedding + grouping egress,
costs money), `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` **plus a required
`LANGFUSE_HOST`** enable full-I/O tracing; tasks 010–012 add **no new deps or env vars** —
the same `OPENAI_API_KEY` live route now also drives the select rerank, the extract step
(extraction is the deliberately-expensive Tier-1 call: full-document prompts, single calls
can run minutes — see the 011 verification cost note) and the group facet partition (cheap
— reference strings only); `make verify` and the
test suite need none of them — stub backends + socket-deny keep the suite egress-free).
Gotcha (bit the 012 live check): after pulling a schema-bearing slice, run
`uv run alembic upgrade head` against the **dev** DB — only the test DB migrates itself
(conftest); a stale dev DB fails mid-run with `UndefinedTable`.
Update it when the setup changes, not before.

## Prerequisites

- **uv** (Python toolchain + venv manager) · **Docker** (for the Postgres container) · **Python 3.12**.
- **direnv** optional — `.envrc` just runs `source .venv/bin/activate`, so run `make setup` first to
  create the venv.

## Setup commands

```
cp .env.example .env     # provides DATABASE_URL (see Local env vars)
make setup               # uv sync -> compose up db -> wait -> create policy_atlas_test -> alembic upgrade head
make verify              # test (against policy_atlas_test) -> typecheck -> lint -> build (pre-checks the DB is up)
```

`make setup` is idempotent. `make verify` refuses to run with a clear error if Postgres is down.

## Required services

- **Postgres 16** via Docker Compose (service `db`, plain `postgres:16` — **no pgvector** this slice).
- Published on **127.0.0.1:5432** only (not exposed beyond localhost).
- User / password are `policy_atlas` (local dev only — not secrets). **Two databases** on the one
  container: `policy_atlas` (dev / smoke) and `policy_atlas_test` (tests; created by `make setup`).

## Seed data

None. The only fixture data is **synthetic**, hand-written in `src/policy_atlas/fixtures.py`, loaded
by both the runtime entrypoint and the test suite. No seed step, no real/acquired source text.

## Test accounts

N/A — no auth or tenancy yet (deferred seam).

## Local env vars

- **`DATABASE_URL`** (required) — e.g.
  `postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas`.
  Canonical value is in `.env.example`; copy it to `.env`. The skeleton reads it; `conftest` calls
  `load_dotenv()` and fails loudly if it is unset.
- **`TEST_DATABASE_URL`** — defaulted by the Makefile to the `policy_atlas_test` DB. `make test` /
  `make verify` export it as `DATABASE_URL`, so tests never touch the dev DB. Override only to point
  tests at a different host/DB.
- No provider/API keys this slice (inference is the no-egress stub). Real keys arrive with the real
  inference provider (separately gated).

## Secret policy

- `.env` is gitignored **and** denied for read/write via `.claude/settings.json`. Only `.env.example`
  (a template with no secrets) is committed.
- When real provider credentials land, they go in `.env` (local) or a secret manager (deployed) —
  **never committed, never pasted into prompts/traces/logs**.

## Network policy

- **No runtime product egress** this slice — the inference provider is a stub; there is no `search`
  backend. Postgres is localhost-only. (Runtime egress is a per-slice approval gate; see
  [engineering-considerations.md](engineering-considerations.md).)
- Agent/dev-time network use is fine: `uv` package installs, Docker image pulls, doc fetches, MCP
  servers (e.g. codex for adversarial review).

## Browser verification

N/A — backend only; no frontend scaffold yet (deferred). Revisit when the Next.js surface lands.

## CI parity

CI ([.github/workflows/verify.yml](../../.github/workflows/verify.yml), 2026-07-03) runs the
**same `make setup` + `make verify`** against an ephemeral compose Postgres, and is a required
status check for merging to `dev`. Local and CI stay identical by construction — both go through
the Makefile; if they ever diverge, that's a bug in the workflow, not a fact to document.

## Known environment quirks

- **Tests need a live DB + `DATABASE_URL`.** `conftest.py` fails with a setup hint if it is unset.
- **Dedicated test database.** Tests run against `policy_atlas_test` (created by `make setup`), each
  test still wrapped in a rolled-back transaction (`conn` fixture). `make test` / `make verify` set
  `DATABASE_URL` to it, and `conftest` **refuses to run against the dev `policy_atlas` DB**
  (fail-closed), so the split holds however pytest is launched. The test DB is disposable — drop it
  and re-run `make setup` if it gets into a bad state.
- **`make verify` pre-checks the DB** and errors clearly (`Run 'make setup' first`) rather than
  failing deep in pytest.
- **Migration is idempotent** — `alembic upgrade head` runs in both `make setup` and the test
  session fixture; running twice is safe.
