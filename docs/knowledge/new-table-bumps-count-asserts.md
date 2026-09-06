---
type: Testing rule
title: A slice that adds a table must bump the metadata table-count asserts in the same PR
description: Six tests assert len(metadata.tables) == N. Task 036 added waitlist_entry without bumping them and handed 037 a red base; the fix rode the wrong slice's branch. grep 'metadata.tables) ==' belongs in any schema-adding checklist.
tags: [schema, testing, migrations]
timestamp: 2026-09-04
---

# Rule

Six tests pin the schema's table count (`assert len(metadata.tables) == N`,
across the metadata/migration round-trip suites). A slice that adds a table
must bump all six **in the same PR** — `grep -rn "metadata.tables) =="
backend/tests` is the checklist line.

Shipping without the bump does not fail the offending slice (its own run
is green before merge only if it ran the full suite); it fails the **next**
slice's build-open baseline, which then carries a fix that belongs to its
predecessor (036 → 037, commit `a95e1aa`).

See [column-churn-migrations-need-scratch-db](column-churn-migrations-need-scratch-db.md)
for the neighbouring migration-hygiene rule.
