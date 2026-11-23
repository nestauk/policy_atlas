---
type: Testing rule
title: Tests that commit fixed subjects or addresses collide on a kept database and on a shared worker
description: Tests that commit rows with fixed subjects or email addresses collide with leftovers on a kept database and with other tests on the same worker. Suffix them with a UUID. A module that reads a whole table gets its own listed domain and an autouse cleanup.
tags: [testing, database, isolation, xdist, "065"]
generated:
  by: process:okf-migrate
  at: 2026-11-17
---

# Rule

A test that commits a row stays in the database after the test ends. A fixed name such as `ops-user` or `a@example.test` then collides in two ways. A re-run on a kept database hits the old row. Two tests on the same pytest worker hit each other.

So:

1. Put a UUID suffix in every committed subject and address.
2. A module that reads a whole table, such as the sweep that looks at every waitlist row, must not see other modules' rows. Give it its own domain, listed in the test and unique per run. Add an autouse fixture that deletes its rows before and after each test.

# Evidence

- `backend/tests/ops/test_sweep.py`: `_DOMAIN = f"sweep-{uuid.uuid4().hex[:8]}.test"` and an autouse fixture at line 45.
- Related: [testing-database](testing-database.md), [parallel-agent-test-databases](parallel-agent-test-databases.md).

