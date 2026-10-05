---
type: Integration quirk
title: A rename manifest generated from SQLAlchemy metadata is not the catalog — check `pg_constraint` for explicit names and sort auto-named FKs by their resolved name
description: SQLAlchemy metadata leaves an unnamed `ForeignKey` with `name=None`; the live catalog holds whatever the creating migration named it. Six 038 FKs carried explicit names (`fk_project_org_id`, `screening_scope_project_id_fkey`, …) that the metadata-derived manifest rendered as `<table>_<col>_fkey`; renaming those would break older revisions' `downgrade()`. Sorting constraints by raw `con.name` is also non-deterministic for auto-named FKs.
tags: [migration, schema, sqlalchemy, postgres, manifest, task-038]
timestamp: 2026-09-05
---

# Rule

When a migration is written from a generated list of catalog objects:

- **Verify the list against `pg_constraint` / `pg_indexes` on a migrated
  database**, not against `metadata` alone. `scripts/schema_manifest.py`
  carries `EXPLICIT_FK_NAMES` (metadata auto-name → live name) for the six
  FKs earlier migrations created under explicit names; the round-trip test
  (`tests/core/test_migration_038.py`) compares `(table, name)` pairs at
  head with the manifest, so a name that never existed fails loudly.
- **Sort on the resolved name.** `con.name` is `None` for auto-named FKs, so
  a sort keyed on it depends on set iteration order and the manifest
  differs between runs; resolve PostgreSQL's default
  (`<table>_<column>_fkey`) first. Deterministic work must be deterministic
  (AGENTS.md).
- **Generate from the pre-rename checkout.** At head the old word already
  names a different entity; the generator refuses when the metadata carries
  the new table (`task`) and says which worktree to use.

# Why

The manifest is the migration's source of truth for 126 rename statements.
Two of its inputs (constraint names, their order) are not properties of the
metadata but of the catalog and of the generator's traversal, and both
drifted silently until the round-trip test and a repeated run caught them.

# Citations

- [038-vocabulary-alignment/verification.md](../tasks/038-vocabulary-alignment/verification.md) (§ Phase 0 "manifest not empty on the first run", § Phase 3.2 "Manifest correction", § Review findings R13–R14)
- `scripts/schema_manifest.py`, `backend/tests/core/test_migration_038.py`
- Same family: [alembic-roundtrip-explicit-revisions](alembic-roundtrip-explicit-revisions.md)
