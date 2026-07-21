---
type: Testing rule
title: Column-churning migration tests need a per-test scratch database
description: Postgres counts DROPPED columns toward a table's 1600-column tuple-descriptor limit, so a migration-roundtrip test that adds/drops columns on the shared test DB permanently consumes slots every run until CREATEs start failing. Provision a scratch database instead.
tags: [testing, migrations, postgres, alembic, review-lesson]
timestamp: 2026-07-21
---

# Rule

Postgres counts **dropped** columns toward a table's 1600-column
tuple-descriptor limit — a dropped column is marked, not physically removed,
until the table is rewritten. A migration-roundtrip test whose DDL adds and
drops columns (025's `project` lifecycle columns: expand → backfill →
constrain, walked up and down) permanently consumes descriptor slots on the
SHARED test database every time it runs, forever, until eventually `CREATE
TABLE` / `ALTER TABLE ADD COLUMN` fails with "tables can have at most 1600
columns."

`test_025_migrations_roundtrip_with_populated_predecessor` provisions a
**per-test scratch database** instead: `CREATE DATABASE` off the shared engine
under `AUTOCOMMIT`, points `DATABASE_URL` at it (`monkeypatch.setenv`), migrates
from `PRE_025_REVISION` through `head` and back down and up again, then `DROP
DATABASE ... WITH (FORCE)` in a `finally`.

# Why

Walking six `project` columns up and down on the shared DB on every suite run
would exhaust the 1600-column limit in practice, within the lifetime of this
repo's CI history at its test cadence — not a theoretical edge case.

# Watch out

This applies specifically to migration tests whose DDL **churns columns**
(add/drop), not to migration-roundtrip tests generally — most existing
roundtrip tests (see
[alembic-roundtrip-explicit-revisions](alembic-roundtrip-explicit-revisions.md))
run fine on the shared DB because they don't repeatedly add/drop the same
columns. Reach for a scratch database only when the migration under test
churns columns.

# Citations

- `backend/tests/core/test_migrations_025.py`
