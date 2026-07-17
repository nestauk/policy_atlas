# ADR 0022 — Screen generation supersession

**Status:** Accepted — 2026-07-16 (Shabeer Rauf; task 024 plan gate — the
owner expanded the slice's schema gate after plan-review finding B1 proved
the no-schema design infeasible).

## Context

A criteria-changed re-screen (024's P2 steer option) must let fresh
screening verdicts supersede prior ones at the document grain. As-built
this was impossible: `uq_ssr_scope_source_stage` is a partial UNIQUE on
`(evidence_scope_id, project_source_snapshot_id, screen_stage)` for
non-failed rows — a second non-failed stage-1 row cannot be inserted —
and `effective_screen_rows` orders by stage only, so even with an insert
path a fresh stage-1 row would lose to a stale stage-2 confirmation. A
read-ordering-only fix was reviewed and rejected (plan-review B1); row
mutation violates the replacement-never-deletes discipline.

## Decision

**Generations.** `source_screening_result` gains `screen_generation INT
NOT NULL DEFAULT 0`; the partial unique index widens to include it. A
re-screen (a replacement-mode re-run, declared as such in its
confirmation and event) writes fresh rows at `generation = max+1`; prior
rows persist immutably. `effective_screen_rows` orders **generation DESC,
stage DESC**: the stage-1→stage-2 flow and the demote-only invariant hold
*within* a generation (their real meaning); across generations, the
newest criteria win by design. The stage-1 doc-skip is bypassed only
under an explicit re-screen re-run; stage 2 re-runs at the new generation
only where asked. Consumers (`characterise`, select eligibility, screen
skip logic) read through the unchanged `effective_screen_rows` interface.

## Consequences

- Any future doc-grain re-assessment (re-classify, re-appraise) has its
  pattern: generation columns + generation-first effective reads, not row
  mutation.
- The generation column is inert at 0 for every existing and non-steered
  run — the feature is a clean sub-slice toggle (024's de-scope lever #2)
  without unwinding the migration.
- Cross-generation history remains queryable (nothing deleted): "what did
  screening say before the user tightened the criteria" is a projection.
