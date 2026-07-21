---
type: Invariant
title: The continuation reducer's plan selection is correct by fencing, not by custody
description: continuation_state.build() picks the latest APPROVED plan project-wide with no join to the specific walk — that is only the parked walk's own lineage because steering amendments supersede within-lineage and planning turns 409 run_active while a walk is running/parked. Remove the fence and plans cross-contaminate silently.
tags: [continuation, planning, invariant, review-lesson]
timestamp: 2026-07-21
---

# Rule

`continuation_state.build()` selects the latest `orchestration_plan` row with
`status == "approved"` (`ORDER BY version DESC LIMIT 1`) for the project — with
**no join or filter tying that row to the specific parked capability_run**. This
query is only correct because two invariants fence it, enforced in two different
files with no code-level link between them:

1. Steering amendments always supersede plan versions **within the parked walk's
   own lineage** — never branch to an unrelated plan (`continuation.py`'s
   `apply_adjustment` / `apply_replacement_rerun` paths).
2. `planning.py`'s `create_planning_turn` returns 409 `run_active` whenever a walk
   is `running` or `paused` for the project, so no unrelated planning conversation
   can approve a new plan version while a walk is parked.

Together, these make "latest approved" provably equal to "this walk's lineage."
Neither invariant alone is sufficient.

# Why

This coupling was surfaced and adjudicated at 025 review (codex finding codex-2)
specifically because it is invisible from either file in isolation: the reducer
looks like a plain "give me the current plan" read, and the planning-turn gate
looks like an unrelated UX guard against concurrent edits. Nothing in the code
comments the dependency without this concept naming it.

# Watch out

Relaxing the `run_active` 409 gate (e.g. "let users plan ahead while a walk
runs") silently breaks continuation: the reducer would then pick up whatever plan
an unrelated, concurrent planning conversation happened to approve, instead of
the parked walk's own lineage — with no error raised anywhere, because the
reducer's query has no way to notice. Any change to the planning-turn gate must
re-examine this invariant first.

# Citations

- `backend/src/policy_atlas/runtime/continuation_state.py` (`build()`, latest-
  approved plan selection)
- `backend/src/policy_atlas/api/routers/planning.py` (`create_planning_turn`,
  the `run_active` 409 check)
