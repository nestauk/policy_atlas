---
type: Invariant
title: The characterise coverage base is project-pool-wide by design
description: Coverage at characterise counts the whole project pool, not the scope's own acquisitions — pool-wide per-question screening is the design; scope-isolation tests must assert the other scope's docs as `unscreened`, never as absent.
tags: [coverage, characterise, evidence-scope, screening, testing]
timestamp: 2026-07-12
---

# Rule

A project is a container for multiple EB questions; every question's screening pass
re-screens the **whole project pool** (extraction is what gets reused, keyed by memo).
So the coverage base at characterise is the project pool, not the scope's own
acquisitions: with two scopes in one project, each scope's coverage honestly reports
the other scope's documents as `unscreened` — they are real pool members this question
has not yet ruled on.

Test consequence: a scope-isolation test asserts the other scope's docs appear as
`unscreened` in the base, **not** that the base excludes them (asserting 0 pins the
wrong semantics and fails against correct code).

# Why

The 019 two-scopes-one-project fixture test's first draft asserted scope-local bases
and failed against the documented pool-wide semantics (owner-verified 2026-07-12); the
test now pins the pool-wide reading. This is design input for the workspace-cluster
contracts — pool-wide per-question screening has a cost-growth seam recorded in
deferred.md (multi-question-project reuse).

# Watch out

- Don't "fix" a characterise coverage count that exceeds the scope's acquisitions —
  that's the pool showing through, not a leak. A real cross-project leak shows as
  *another project's* docs, which the project-scoped harness lookup already guards.
- Reuse boundaries differ by artefact: screening rulings are per-scope; extraction
  reuse is memo-keyed; appraisal reuse is `rubric_version`-keyed (seam entries in
  deferred.md).

# Citations

- [019 verification.md § Diff summary](../tasks/019-folding-pass/verification.md)
  (flagged deviation 3 — the test-draft correction)
- `tests/test_characterise.py` (two-scopes-one-project coverage fixture)
- [deferred.md § Data model / evidence](../deferred.md) (multi-question-project reuse
  seam)
