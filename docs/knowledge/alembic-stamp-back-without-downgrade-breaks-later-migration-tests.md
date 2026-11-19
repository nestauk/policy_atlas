---
type: Testing rule
title: A test that stamps Alembic back without downgrading must step down to that revision first, or later migration tests on the worker break
description: A migration test that uses command.stamp to move the recorded revision back leaves the schema at head. Once a newer revision exists, every later migration test on that worker fails. Downgrade to the revision first; stamp only afterwards.
tags: [testing, alembic, migrations, pitfall, "065"]
timestamp: 2026-11-17
---

# Rule

Alembic keeps a note of which revision the database is at. `command.stamp` only changes that note. It does not change the tables.

A test that stamps back to an old revision (to re-run an upgrade) leaves the tables at the newest revision. The note and the tables now disagree. Later migration tests on the same worker then fail in odd places, because they trust the note.

This stays hidden until a newer revision exists. On 065 it appeared when `c6d4e2f1a9b8` landed after `b1e7c3a9d5f2`.

# What to do

Step down with `command.downgrade` to the revision first. Then stamp or upgrade. Finish with `command.upgrade(cfg, "head")` in a `finally` block.

# Evidence

- `backend/tests/core/test_migration_064a_ssr_index.py` stamps back to `PRE_REVISION` on purpose, to keep an invalid index in place. It ends with `upgrade(cfg, "head")`. Any test like it needs the same care.
- Related: [alembic-roundtrip-explicit-revisions](alembic-roundtrip-explicit-revisions.md), [testing-database](testing-database.md).

