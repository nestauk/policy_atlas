---
paths:
  - "backend/alembic/**"
  - "backend/tests/**/*migration*.py"
---

# Database migrations: facts the code does not show

Each line is a fact about this repository that is easy to miss when you read one file.
Use your own judgement for everything else. Remove a line when a test enforces it.

- A revision keeps its own copy of any SQL it runs (a view, a function, a seed row). It
  does not import from `policy_atlas`, because that code changes later and a fresh
  `upgrade head` then runs the new text against the old schema.
- `backend/alembic/env.py` commits each revision on its own (`transaction_per_migration`).
  A downgrade from head therefore finishes the later revisions before an early one can
  refuse. A downgrade that loses data checks its own data first and raises before it
  changes anything.
- A migration test names its downgrade target as a revision id, not `-1`: the relative
  form points at a different revision when a later migration lands.
- A migration test commits or rolls back its seed rows before alembic changes the schema
  on another connection. An open transaction on a seeded table blocks the change with no
  error, and the suite hangs.
- `command.stamp` changes the recorded revision, not the tables. A migration test that
  stamps back without downgrading first leaves the two out of step, and later migration
  tests on the same worker fail, though only once a newer revision lands.
