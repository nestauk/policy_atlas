---
type: Testing rule
title: Historical migration tests cannot share one `Table` object across a rename revision — reflect old names below it, use current metadata at head
description: Once a revision renames tables and columns, a test that downgrades below it and inserts through `policy_atlas.core.schema` metadata addresses names that do not exist there. Below the rename, address the old catalog by reflection (`tests/core/legacy_catalog.py` `legacy_table(conn, name)`) or textual SQL; at head use current metadata. Eleven pre-038 migration tests and three `test_schema.py` round-trips were reshaped this way (038 D9).
tags: [testing, migration, alembic, schema, task-038]
timestamp: 2026-09-05
---

# Rule

A migration test that walks through a renaming revision has two catalogs to
talk to:

- **Below the rename:** `legacy_table(conn, "project")` reflects the table
  as it exists at that revision (`Table(..., autoload_with=conn)`), so
  inserts and selects use the old column names; textual SQL is the other
  honest option.
- **At head:** the current `schema.metadata` objects (`task`,
  `task_plan`, …).
- **Never** one `Table` object for both: the metadata's `task` table does
  not exist below the rename, and a reflected `project` table does not
  exist above it.

The round-trip fixture is snapshotted through the *reflected* tables before
and after (`_fixture_snapshot`), which is what makes "byte-identical after
downgrade" a real assertion.

# Why

038's D9 found eleven older migration tests that inserted through metadata
after downgrading below the new revision; each would have failed on the
renamed columns, and the fix could not be a rename in the tests (they
address the old catalog on purpose).

# Citations

- `backend/tests/core/legacy_catalog.py`, `backend/tests/core/test_migration_038.py`
- [038-vocabulary-alignment/verification.md](../tasks/038-vocabulary-alignment/verification.md) (§ Phase 3.2 "D9")
- [038-vocabulary-alignment/plan.md](../tasks/038-vocabulary-alignment/plan.md) (D9)
- Same family: [alembic-roundtrip-explicit-revisions](alembic-roundtrip-explicit-revisions.md)
