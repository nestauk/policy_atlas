---
type: Convention
title: A periodic job's advisory lock lives on its own autocommit connection
description: A session-level PostgreSQL advisory lock that keeps one run of a periodic job at a time belongs on a separate connection in autocommit mode. On the job's working connection the holder sits idle in a transaction for the whole run, and a transaction-mode pooler would break the lock.
tags: [postgres, advisory-lock, sweep, concurrency]
generated:
  by: agent:task-cycle-review
  at: 2026-11-26
---

# Rule

To let only one run of a periodic job work at a time, take `pg_try_advisory_lock` on a connection that does nothing else, in autocommit mode, and release it in `finally`. A second run that does not get the lock does nothing.

Why a separate connection: the job's own transactions open and close many times in a run, and a session lock on a connection that also holds a transaction leaves it "idle in transaction" between steps. Why autocommit: the lock connection then holds no transaction at all.

The lock is session-level, so it needs a direct database session. A pooler in transaction mode (RDS Proxy, pgbouncer) gives each statement a different session and the lock stops working. The ops service connects directly.

# Evidence

- `backend/src/policy_atlas/ops/sweep.py` (`run_once`): the tick lock on its own `AUTOCOMMIT` connection.
- `backend/tests/ops/test_sweep.py::test_a_tick_that_finds_another_running_does_nothing`.
- A mutation check in the build turned the lock off and that test failed.
