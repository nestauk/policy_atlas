---
type: Invariant
title: Harness scope lookups must filter by project_id, not just by ID
description: A harness node that loads a scope-like row (e.g. evidence_scope) by its own ID must also filter by the run's task_id, or a scope belonging to another task is silently accepted.
tags: [harness, cross-task, security, invariant]
timestamp: 2026-07-01
---

**The row this concept calls `project` is `task` as of task 038** — the filename (an OKF
concept id) keeps the pre-038 word, but the column and every example below are `task_id`.

# Rule

Any harness node that looks up a row by an ID carried on `Config` (e.g. `evidence_scope_id`)
must filter that lookup by `task_id` as well as the ID:

```python
select(evidence_scope)
    .where(evidence_scope.c.evidence_scope_id == config.evidence_scope_id)
    .where(evidence_scope.c.task_id == task_id)   # required, not optional
```

An ID-only lookup finds the row regardless of which task it belongs to.

# Why

`Config.evidence_scope_id` is caller-supplied. If it references a scope from a different
task, an ID-only lookup succeeds, constructs a context from another task's data, and the
downstream fan-out function's own `task_id` filters happen to return zero rows — so the run
silently "succeeds" with `classified=0`/`screened=0` instead of failing loudly. The database-level
composite FKs on the result tables (`fk_scr_scope_task` etc.) guard the *write* path; they do
nothing for a read-only scope lookup that never gets that far.

# Watch out

This bug shipped once already (`_run_screen`'s original scope lookup had no `task_id` filter)
and was only caught by review, not by a test targeting this exact path — the existing
cross-task tests (`test_cross_task_fk_rejected`) exercise the FK on *insert*, not the
harness's own scope lookup. Any new harness node added for a future component (`appraise` is
next) that loads a scope/plan-referenced row by ID needs this filter from the start.

# Citations

- [005-classify/verification.md](../tasks/005-classify/verification.md) (Review findings —
  `/code-review` finding 3)
- `_run_scope_component` in `src/policy_atlas/harness.py`
