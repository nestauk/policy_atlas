# Verification: 002-test-db-split

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make setup` | pass | Creates `policy_atlas_test` (idempotent); re-run is a no-op |
| `make verify` | pass | Suite runs against `policy_atlas_test`; typecheck/lint/build green |
| `make test` | pass | 26/26 against `policy_atlas_test` |
| `/okf validate docs/knowledge` | pass | 7 files, 0 errors, 0 lints |

## Acceptance checks (from contract.md)

1. [x] `make setup` brings the DB up and creates `policy_atlas_test`; re-running prints
   "Test DB ready" without error (the `pg_database` existence check guards the `createdb`).
2. [x] `make verify` green with the suite on `policy_atlas_test` (26 tests).
3. [x] **Dev DB isolation proven** — after a full `make verify`, the dev `policy_atlas` DB reports
   `project=0, event_log=0, block=0`. Test data never reaches dev.
4. [x] **Guard fires** — `DATABASE_URL=…/policy_atlas uv run pytest` fails closed with
   "Refusing to run tests against the dev database 'policy_atlas'…" on every DB-touching test.
5. [x] `testing-database.md` updated to the new convention; `/okf validate` clean.

## How it works

- One Postgres container, two databases: `policy_atlas` (dev / smoke) and `policy_atlas_test` (tests).
- `make test`/`make verify` set `DATABASE_URL="$(TEST_DATABASE_URL)"`; `conftest` reads it, migrates
  it (idempotent, once per session), and rolls back each test as before.
- `conftest._db_url()` refuses the dev DB name, so the split holds even for a bare `uv run pytest`.

## Diff summary

- `Makefile` — `TEST_DATABASE_URL` var; `setup` creates the test DB (idempotent); `test` targets it.
- `tests/conftest.py` — fail-closed guard against the dev DB name + clearer unset-hint.
- `.env.example` — documents `TEST_DATABASE_URL` (Makefile-defaulted).
- `docs/knowledge/testing-database.md` — flips the task-001 "no separate test DB" convention.
- `docs/tasks/002-test-db-split/{contract,verification}.md` — task packet.

No schema/migration, no dependency, no product code, no egress. Aurora/prod untouched.

## Public safety

Local dev only — the test DB uses the same throwaway `policy_atlas:policy_atlas` credentials already
in `docker-compose.yml`. No new secret, no real data, no runtime egress.

## Review findings

Fresh-eyes review (`agent-skills:code-reviewer`, did not write the change) — **APPROVE**, all 5
acceptance checks confirmed. The subtle trap (does a stale `.env` `DATABASE_URL` override the
make-set one?) was verified handled: `load_dotenv(override=False)` does not clobber the exported
var, so `make test` provably hits `policy_atlas_test`.

- **Fixed (MINOR):** the dev-DB guard **failed open on a trailing-slash URL** (`.../policy_atlas/`
  → empty db-name → allowed). Hardened to `url.rstrip("/").rsplit("/",1)[-1].split("?")[0].lower()`
  + a comment that the match is intentionally host-agnostic. Re-tested: the trailing-slash dev URL
  now fails closed; the legit test DB still runs (26 green).
- **Noted, no change:** the name-only match is host-agnostic by design (blocks the dev name on any
  host; a differently-named prod DB is out of scope — `make test` never targets it). `make setup`
  migrates the *dev* DB; the test DB is created empty and migrated by `conftest` at session start
  (matches the contract).
- **Scope (ponytail):** clean Tier-1 change, nothing over-built.
