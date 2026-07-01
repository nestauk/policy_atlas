---
type: Invariant
title: Per-document fan-out functions must exclude already-processed rows
description: classify_sources/screen_sources exclude rows already having a result for the scope via WHERE NOT EXISTS, so re-running the same call is safe.
tags: [harness, fan-out, idempotency, invariant]
timestamp: 2026-07-01
---

# Rule

A per-document fan-out function (`classify_sources`, `screen_sources`) must filter its candidate
row set with a `WHERE NOT EXISTS` correlated subquery against its own result table, scoped by
the same key the unique constraint uses (`screening_scope_id` + `project_source_snapshot_id`).
Without it, calling the function twice for the same scope re-processes already-done rows and
raises `IntegrityError` on the unique constraint — which rolls back the caller's whole
transaction, including unrelated writes made earlier in the same `run_harness` call.

# Why

Runs can legitimately be retried or re-invoked against the same scope (a duplicate plan
submission, a manual retry). A fan-out component that isn't safe to call twice turns any retry
into a hard failure instead of a no-op-on-already-done-rows continuation.

# Watch out

The guard only prevents the *same session* from double-processing sequentially. Under a genuine
concurrent writer (two overlapping transactions racing on the same scope), both can see "not yet
processed" before either commits, and the loser still raises `IntegrityError` on insert — this is
out of scope under v3.0's single-active-writer, serial-execution architecture (see
[system/execution-orchestration.md](../specs/system/execution-orchestration.md)), not something
this guard is meant to solve.

If a fan-out function reports counts that are meant to sum to the scope's total (e.g. "done" +
"not eligible" == total), adding this guard changes what "done" means on a re-run — it now
excludes previously-done rows, so the invariant needs an explicit "already done" bucket, not just
the original two counts. `classify_sources` learned this the hard way: `already_classified` was
added after a re-run silently broke `classified + skipped == total`.

# Citations

- [005-classify/verification.md](../tasks/005-classify/verification.md) (Review findings —
  `/code-review` finding 1; fresh re-review findings on the `already_classified` count)
- `classify_sources`/`screen_sources` in `src/policy_atlas/classify.py` / `src/policy_atlas/screen.py`
- Tests: `test_classify_sources_idempotent_rerun`, `test_screen_sources_idempotent_rerun`
