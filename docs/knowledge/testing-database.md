---
type: Testing convention
title: Tests run against a dedicated test database, each test in a rolled-back transaction
description: Tests use a separate policy_atlas_test database on the same local container; the conn fixture also rolls back each test. conftest refuses to run against the dev DB.
tags: [testing, database, pitfall]
timestamp: 2026-06-24
---

# Rule

The test suite needs a live Postgres. It runs against a **dedicated `policy_atlas_test` database** on
the *same* local container as the dev `policy_atlas` DB (one container, two databases) — `make setup`
creates it, and `make test` / `make verify` point `DATABASE_URL` at it via the `TEST_DATABASE_URL`
Makefile variable. Within a run, the `conn` fixture still opens a transaction per test and rolls it
back; the migration is applied once per session (idempotent). `conftest._db_url()` **refuses to run
against the dev `policy_atlas` database** (fail-closed) so the split holds however pytest is launched.

# Why

Some tests now **commit** (e.g. `test_fail_annotation_survives_commit`, which proves flag-don't-drop
survives a real commit). A shared dev DB would let a failed teardown pollute dev data, so test data
lives in its own disposable database. Rollback-per-test still gives cheap isolation *within* a run;
the separate DB isolates the suite from dev. This flipped the task-001 convention (no separate DB).

# Watch out

Run tests via `make test` / `make verify`, not bare `uv run pytest` against a `.env` `DATABASE_URL`
that points at the dev DB — `conftest` will fail loudly with a hint if you do. The test database is
disposable: drop and let `make setup` recreate it if it gets into a bad state. Aurora/prod is never a
test target — it's a separate `DATABASE_URL` with secrets-manager credentials.

**The test DB is a shared resource — parallel-lane file fences must include it** (023, twice).
Concurrent DB-backed pytest runs contaminate each other: an interrupted migration roundtrip leaves
committed rows that break downgrades across *sessions* (conftest migrates but never wipes), and any
ad-hoc run that commits (e.g. the manual orchestrate smoke) re-contaminates it. Symptoms:
`CheckViolation` on downgrade in an apparently-clean session. Fix is `dropdb`+`createdb` (seconds);
prevention is one-DB-user-at-a-time — a build lane's "fence" covers done-check resources, not just
files. If parallel lanes become routine, see deferred.md's per-lane `DATABASE_URL` entry.

Corollary (026): any harness that *persists* real rows (the FE↔API smoke, manual poking) must own a
disposable per-harness DB (`policy_atlas_smoke`, recreated per run, dropped at teardown) — reusing
`policy_atlas_test` broke 4 migration round-trip tests and looked like a schema bug.

# Citations

- [tests/conftest.py](../../tests/conftest.py)
- The repo `Makefile` — `setup` (creates the test DB) and `test` (`TEST_DATABASE_URL`) targets.
- [environment.md](../agentic-ops/environment.md)
