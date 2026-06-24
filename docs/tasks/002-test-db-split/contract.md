# Task contract: 002-test-db-split

One small slice. Boundaries: [AGENTS.md](../../../AGENTS.md).

> **Status: drafted. Tier 1.** Scope agreed with the user. No hard gate crossed — no schema/migration,
> deps, egress, prod/Aurora config; Makefile target *names and promises* are unchanged.

## Goal

Run the test suite against a **dedicated `policy_atlas_test` database** on the *same* local Postgres
container, so committing/integration tests (introduced in task 001's
`test_fail_annotation_survives_commit`) can never pollute the dev database. This **flips** the
task-001 convention that tests share the dev DB ([docs/knowledge/testing-database.md](../../knowledge/testing-database.md)).

## Scope

**In:**
- `make setup` creates `policy_atlas_test` if absent (idempotent), alongside the dev `policy_atlas`.
- `make test` / `make verify` point `DATABASE_URL` at the test DB (Makefile var, defaulted).
- `conftest.py` **refuses to run against the dev `policy_atlas` DB** (fail-closed guard) so the split
  holds however pytest is launched, not only via `make`.
- Update the `testing-database.md` knowledge concept to the new convention.
- `.env.example` documents the test-DB variable.

**Out (unchanged / deferred):**
- No second container, no second Postgres server — one container, two databases.
- No schema/migration change; the test DB is migrated by `conftest` at session start, as today.
- The per-test rollback isolation model stays; this only changes *which* DB it runs in.
- Aurora / prod untouched — it is just another `DATABASE_URL`, never targeted by `make test`/smoke.

## Constraints / gates

No hard gate crossed. Local dev credentials only (the same throwaway `policy_atlas:policy_atlas`); no
new egress; no new dependency. Aurora credentials remain a future secrets-manager concern, not `.env`.

## Acceptance checks (this is the rubric)

1. `make setup` brings the DB up and creates `policy_atlas_test` (idempotent on re-run).
2. `make verify` green, running the suite against `policy_atlas_test`.
3. The dev `policy_atlas` DB holds **no test rows** after a full `make verify` (isolation proven).
4. `conftest` fails with a clear hint if pointed at the dev DB.
5. `testing-database.md` reflects the new convention; `/okf validate` clean.

## Risk tier & rollback

**Tier 1.** Rollback = revert the PR; drop the `policy_atlas_test` database. No data, no consumers,
greenfield. Verification evidence → [verification.md](verification.md).
