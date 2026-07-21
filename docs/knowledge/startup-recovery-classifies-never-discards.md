---
type: Invariant
title: Startup recovery classifies running walks — it never discards them
description: The API's boot-time sweep sorts every "running" capability_run three ways (claimed-but-no-progress → re-execute, genuine mid-execution death → honest interrupted, no event attachment at all → interrupted with a null attachment) and must never raise, since a raise inside the lifespan bricks every subsequent boot. Redispatch/re-execute must compose the same key-driven backends + IO seam as the request path.
tags: [continuation, startup, recovery, invariant, capability-run]
timestamp: 2026-07-21
---

# Rule

On every API boot, `startup_sweep` (`continuation.py`) classifies every `running`
capability_run row three ways, never two:

1. **Claimed but no progress** — a `continuation.claimed` event exists for the walk
   and nothing run-attached (`run_id is not None`, non-`continuation.*`) followed it
   in sequence (`_claimed_without_progress`). The claim committed before the process
   died at a clean boundary; the walk is returned in `reexecute` and the lifespan
   re-executes it directly (`claim_first=False`) — the claim is durable, so
   re-claiming would be redundant and interrupting would discard real state.
2. **Anything else `running`** — died mid-execution → honestly `interrupted`, with a
   `run.interrupted` event.
3. **No event attachment at all** (death between `run.opened` and the first
   component) — still interrupted, but with a **null** `run_id` attachment. The sweep
   logs a warning and moves on; it never raises. A raise here would brick every
   subsequent API boot, since the sweep runs unconditionally in the lifespan.

The lifespan's `_claim_and_execute` (`app.py`) composes the **same key-driven**
`get_runner_backends()` + `ParkIO()` as the request path for both redispatch and
re-execute — `execute_continuation`'s `backends`/`io` parameters are required, not
defaulted, because a `None` default previously fell through to `run_plan`'s stub
bundle and `NullIO`, which auto-continues every pause.

# Why

The first cut of this logic interrupted every claimed continuation unconditionally.
That discarded a walk that had just been answered — a multi-day park — purely
because the process died in the narrow window between claim and dispatch (review
finding, 2026-07-21). The claim is a durable event; the correct read is
"re-execute", not "the operator's steering answer is lost." Separately, a `None`
backends/io default silently redispatched real continuations onto deterministic
stubs that auto-continued every subsequent pause — invisible in tests, catastrophic
live (review finding codex-1).

# Watch out

"Progress" is defined narrowly: any run-attached, non-`continuation.*` event with a
higher sequence than the claim. Component-emission events always carry a `run_id`
once a walk is executing, and only one walk runs per project at a time, so this is
unambiguous — but getting the boundary wrong in either direction is bad: too loose
re-runs an already-committed component, too strict discards live work. Never widen
the raise-suppression to any OTHER exception class in the sweep loop; the null-
attachment case is the one documented exception to "loud on missing durable state."

# Citations

- `backend/src/policy_atlas/api/continuation.py` (`startup_sweep`,
  `_claimed_without_progress`)
- `backend/src/policy_atlas/api/app.py` (`_lifespan`, `_claim_and_execute`)
