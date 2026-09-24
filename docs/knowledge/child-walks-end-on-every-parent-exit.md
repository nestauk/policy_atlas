---
type: Invariant
title: A walk that fans out child walks ends them on every exit, not only at the join
description: A longlist walk dispatches its option searches before acquire and joins them only at the longlist step, so every earlier exit (spine failure, abort, a raise) used to leave children running with no reader. The as-built rule is that each end of the parent abandons its unjoined children, a straggler that opens its row after being abandoned ends itself, and the parent's finish and the join's child-end never both write a terminal status (row lock).
tags: [runner, option-search, child-walks, concurrency, fan-out, task-045]
timestamp: 2026-09-24
---

# Rule

When a walk runs child walks concurrently (045: a longlist walk's option searches, width 4):

1. **Every end of the parent ends its children.** `_finish_run` on a `longlist` walk calls
   `option_search.abandon_children` before writing the parent's status, and the runner's outer
   `except` does the same before re-raising. After a join it changes nothing; before one, queued
   children are cancelled and started ones are ended `interrupted`. A child's end never fails the
   parent, and neither does the cleanup.
2. **A straggler ends itself.** A child still between "submitted" and "row committed" has no row
   for the parent to end, so the parent records it as abandoned and the runner calls
   `end_if_abandoned` right after the child's row commits: it finishes `interrupted` instead of
   running a whole walk nobody reads.
3. **One terminal write per walk.** `_finish_run` reads the walk row `with_for_update(of=capability_run)`;
   a child whose row is no longer `running`/`paused` (the join or the parent's end already ended it)
   keeps that record and appends no second `run.finished`. A check-then-write on a status needs a row
   lock or a conditional update — same family as
   [db-row-is-the-single-flight-authority](db-row-is-the-single-flight-authority.md).

# Why

Three lanes of the 045 review stack found the orphan independently (code-review A2, adversarial,
contract verifier F10/F13): the fan-out sits before acquire and the join at step `longlist`, and
seven failure/abort returns in `_run_plan_impl` skipped the join. The straggler (A11) and the
double terminal write (A6) were the two holes left once the obvious fix was in.

# Watch out

- A new early return in the runner is covered only because the cleanup sits in `_finish_run` and
  the outer `except`, not beside the join — keep it there.
- The abandoned set is process-local; it is enough because a child and its parent run in one
  executor process (see [db-row-is-the-single-flight-authority](db-row-is-the-single-flight-authority.md)
  § Watch out on scale-out).

# Citations

- `backend/src/policy_atlas/runtime/option_search.py` (`abandon_children`, `end_if_abandoned`, `_interrupt_children`)
- `backend/src/policy_atlas/runtime/runner.py` (`_finish_run`, the outer `except` in `run_plan`, the `end_if_abandoned` call after `_open_capability_run`)
- [045 verification.md](../tasks/045-scoping-longlist/verification.md) § Review findings (A2, A6, A11, F10, F13, L5)
