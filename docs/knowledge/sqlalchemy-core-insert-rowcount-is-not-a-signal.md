---
type: Testing rule
title: A Core INSERT's rowcount is not a "did it insert" signal; use RETURNING
description: SQLAlchemy Core reported rowcount -1 for an INSERT ... ON CONFLICT DO NOTHING on this stack, so `rowcount == 1` read every first insert as "already there". Use `.returning(...).first()` and test the first-insert branch as well as the repeat.
tags: [sqlalchemy, postgres, testing, review-lesson]
generated:
  by: process:okf-migrate
  at: 2026-11-18
sources:
  - resource: "backend/src/policy_atlas/ops/commands.py"
    title: "`backend/src/policy_atlas/ops/commands.py` `add_to_cohort` (task 065 review stack, 2026-11-18)."
  - resource: "docs/tasks/065-accounts/verification.md \u00a7 Review stack on the post-review delta."
    title: "docs/tasks/065-accounts/verification.md \u00a7 Review stack on the post-review delta."
---

# Rule

To learn whether an `INSERT` (including `ON CONFLICT DO NOTHING`) wrote a row, add
`.returning(<key column>)` and check `.first() is not None`. Do not read `rowcount`.

# Why

On this stack (SQLAlchemy Core, psycopg, Postgres) `rowcount` came back -1 for the cohort-add
insert. `add_to_cohort` compared it to 1, so every first add told the operator "already in;
nothing changed" while the row was written. The tests checked the row and the idempotent
repeat, so both stayed green; the wrong branch showed only in the summary text.

# Watch out

Test both branches by what the caller is told, not only by the table: a first insert says it
changed something, a repeat says it did not. A test that runs every write as the restricted
login (`pa_ops`) found this one, because it asserted the result object.
