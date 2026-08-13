---
type: Invariant
title: A run id read from a success-only map is stale at a failure boundary
description: successful_runs is written only when a component succeeds, but the runner still presents that component's steer point when it fails — so a bundle built from successful_runs renders the *previous* round's numbers under the failed round's label. Gate the display on the boundary's own run id.
tags: [runner, steering, multi-round, honest-absence, read-models, invariant]
timestamp: 2026-08-13
---

# Rule

`successful_runs[component]` in the runner is written **only** on the success path
(`runner.py`, at the `final_attempt.status == "succeeded"` branch). The failure path
records `attempted_runs` instead — and then still presents the component's after-boundary,
because a failed acquire is exactly when a "search exception" steer point should fire.

So any display bundle built from `successful_runs` at a boundary is answering a different
question from the one the boundary asked. In a multi-round walk it answers it with real,
plausible, wrong data: round 1's counts and queries under round 2's label.

As built: `_build_bundle` takes the boundary's own `boundary_run_id` and passes the
acquire run id to `p1_bundle` **only when the two match**. Otherwise it passes `None`,
which the bundle already renders as honest absence — empty counts, empty queries.

# Why

Task 031 fixed a P1 check-in whose backend counts were permanently zero. The fix read the
acquire run's own `component.completed` payload via `successful_runs["acquire"]`, which is
correct on every success path and was verified as such. The adversarial review lane traced
the *failure* path and found the gap: on a round-2 acquire failure the card rendered round
1's numbers beside a blank headline chip.

The severity is in the direction of the change. Before the fix the card was *visibly*
broken — a row of zeros nobody would trust. After it, on this one path, it was plausibly
wrong. **A fix that converts a visible defect into an invisible one is a regression even
though the defect count went down**, and it is worst at a steer point whose entire purpose
is to tell the user that the search went badly.

# Watch out

- **The tell is a map keyed by outcome being read at a boundary keyed by event.**
  `successful_runs` is "the last run of each component that worked"; a boundary is "this
  specific run just ended, well or badly". Any time those two are used interchangeably,
  check the failure path explicitly — the success path will look fine.
- The runner already had this guard shape elsewhere: P3/P4 degrade to a generic pause when
  the boundary's run produced nothing persisted. New steer points should copy it rather
  than rediscover it.
- **Two review lanes can both be right about different paths.** Here the contract verifier
  traced the success path and correctly reported it sound; the adversarial lane traced the
  failure path and found the bug. Neither contradicted the other. When a lane certifies a
  behaviour, read *which path* it walked before treating the question as closed.
- Same family:
  [read-the-producing-components-summary](read-the-producing-components-summary.md)
  (where the number comes from),
  [two-phase-retry-terminal-status](two-phase-retry-terminal-status.md).
