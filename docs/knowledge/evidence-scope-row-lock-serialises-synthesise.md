---
type: Live behaviour
title: Writing the synthesis directive onto the shared evidence_scope row serialises concurrent synthesise runs
description: Feasibility check 7 (task 044) fanned seven one-section synthesise runs out over one scope and they ran one after another — the run opener writes the directive onto the `evidence_scope` row, and that Postgres row lock is held for the run. `synthesise_scope` reads the directive from its context, not the row, so the lock buys nothing and costs the whole fan-out.
tags: [synthesis, postgres, locking, concurrency, feasibility-check, task-044]
timestamp: 2026-09-17
---

# Rule

Two synthesise runs on the same `evidence_scope` cannot overlap today: whichever path writes the
directive onto the scope row before running holds the row lock until its transaction ends, and
the second run blocks on it. Any harness that measures parallel writing must give each arm its
own scope row (or its own transaction boundary) or it measures a queue.

# Why

Check 7's first parallel run summed its arms — 328 s "parallel" against 183 s sequential — until
the lock was found; with the arms unblocked the same fan-out measured 62.7 s. The number nearly
went into the owner's ruling the wrong way round.

# Watch out

- The shipped product runs one synthesise per walk, so the lock never bites in production; it
  bites feasibility checks, evals and any future parallel-writing mode (deferred — "never fan out
  the conclusion" stands by owner ruling C6).
- The directive travels in the run context; the scope-row copy is a record, not the input.

# Citations

- [044 verification.md](../tasks/044-scoping-shell-baseline/verification.md) § Phase 4.4, § Review handoff
- `scripts/feasibility_checks/options_scoping/run_check_7_writing_mode.py`
- `backend/src/policy_atlas/evidence_search/synthesis/synthesise.py::synthesise_scope`
