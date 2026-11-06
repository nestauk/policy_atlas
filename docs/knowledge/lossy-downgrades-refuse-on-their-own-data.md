---
type: Invariant
title: Every lossy downgrade in a chain refuses on its own data; a refusal at the end of the chain comes too late
description: alembic/env.py commits each revision on its own (transaction_per_migration), so a downgrade from head runs the later revisions to completion before an early one refuses; any step that drops a column or folds values must check its own data first, and the refusal test asserts the rows and columns are intact afterwards.
tags: [alembic, migrations, rollback, theory-of-change, task-054]
timestamp: 2026-11-05
---

# Rule

- A chain of revisions downgrades one committed step at a time (`backend/alembic/env.py`,
  `transaction_per_migration=True`). A refusal in revision N does not undo revisions N+1 … head.
- So every downgrade that loses data (drops a column, folds a value list, deletes rows) checks
  its **own** data at its top and raises before any DDL. "The core revision refuses while a
  task exists" is not enough: by then the later revisions have already dropped their columns.
- The refusal test seeds data and asserts, after the refused downgrade from head, that the rows
  still exist and the later revisions' columns are still there — not only that the core tables
  exist.
- A revision whose columns hold no data may step down, and so may one whose downgrade is a
  designed value mapping that keeps every row and has a round-trip test; the remedy for a
  refusal is the operator script that deletes the tasks whole.

# Why

Task 054 landed ten revisions. Only the core and the upload revisions refused; four in the
middle dropped figures, titles, proposals and user decisions without a check (two others,
`7fbb` and `80f4`, fold values with a designed, round-trip-tested mapping and keep every row, so
they step down). A rollback with theories present would have committed those drops and then
stopped at the core revision with the data already gone. Found by the contract verifier reading
the chain (2026-11-05).

# Citations

- `backend/alembic/env.py` (`transaction_per_migration`)
- `backend/alembic/versions/72c3174734ea_*.py`, `3c2752811cce_*.py`, `9d1e4c7a2b10_*.py`,
  `b4e8a1f63c25_*.py` (the guards); `7fbb8bf487f2_*.py`, `80f4e6c430b0_*.py` (the mappings,
  with `test_migration_054_beam.py` and `test_migration_054_layers.py`)
- `backend/tests/core/test_migration_054_core.py::test_the_downgrade_refuses_while_a_theory_of_change_task_exists`
- [054 verification § Review findings](../tasks/054-toc-integration/verification.md);
  [ADR 0042 § Rollback](../adr/0042-theory-of-change-task-kind.md)
- Related: [alembic-roundtrip-explicit-revisions](alembic-roundtrip-explicit-revisions.md)
