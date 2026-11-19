---
type: Invariant
title: A column constant within a window partition can lead the partition key at no cost, and lets PostgreSQL push a caller's filter below the window
description: effective_screen_rows partitioned by scope and snapshot; every caller filtered by task, but the planner cannot push a filter on a column the window does not partition by, so every task's rows were ranked on every call. task_id is constant within a scope (fk_ssr_scope_task), so adding it first to partition_by changes no ranking and lets the task filter reach the scan, with an index to match (37 ms to 2 ms on 40,000 rows; 064a Q9).
tags: [postgres, window-function, query-plan, index, screening, invariant]
timestamp: 2026-11-16
---

# Rule

A window function's result depends only on the rows inside each partition and their
order. A column that is constant within every partition can therefore be added to
`partition_by` without changing a single row number — and once it is part of the key,
PostgreSQL may push an equality filter on that column **below** the window node, so the
scan reads only the matching partition instead of ranking the whole table and filtering
afterwards.

`effective_screen_rows` partitioned by `(evidence_scope_id, task_source_snapshot_id)`.
Every one of its 22 call sites filtered the result by `task_id`, but the planner cannot
move that filter under the window, so each call ranked every task's screening rows. The
task list page calls it once per row every 15 seconds. `fk_ssr_scope_task` ties each
scope to one task, so `task_id` is constant within a partition; it now leads the key,
and migration `b1e7c3a9d5f2` adds `ix_ssr_task_scope_snapshot` on
`(task_id, evidence_scope_id, task_source_snapshot_id)` to match it.

Measured on the development database (39,682 rows across 87 tasks, the task with the
most rows at 1,221): sequential scan of every row and an on-disk sort, 37 ms, became a
bitmap index scan of 1,221 rows and an in-memory sort, 2 ms, with the task filter shown
as the index condition under the window node. The parity test proves the row set is
unchanged on a two-task, two-scope, two-generation, both-stages fixture with failed rows.

The general check before adding a column this way: find the constraint that makes it
constant per partition (here a foreign key from the partition's entity to the column's),
and keep a parity test, because the planner benefit is invisible to a correctness test.

# Citations

- `backend/src/policy_atlas/evidence_search/assess/screen.py` — `effective_screen_rows`.
- `backend/alembic/versions/b1e7c3a9d5f2_ssr_task_scope_snapshot_index.py` — built
  `CONCURRENTLY` with invalid-index recovery.
- `backend/tests/evidence_search/assess/test_screen_partition_parity.py`;
  `backend/tests/core/test_migration_064a_ssr_index.py`.
- [task 064a verification](../tasks/064a-security-quick-wins/verification.md) — the
  `EXPLAIN ANALYZE` pair.
- Related: [effective-screen-row-read-rule](effective-screen-row-read-rule.md).
