---
type: Integration quirk
title: Schema-valid LLM output can still be empty — enforce count/coverage invariants in code
description: gpt-5-nano returned a schema-perfect `{"assignments":[]}` for realistic 25-doc batches at every reasoning effort; strict structured outputs guarantee shape, never completeness — code must validate counts against the input set.
tags: [llm, structured-output, grouping, characterise, validation, model-choice]
timestamp: 2026-07-06
---

# Rule

Strict structured outputs (JSON-schema-constrained generation) guarantee *shape*, not
*completeness*. A model can satisfy the schema perfectly while doing none of the work: on
task 009's first live run, `gpt-5-nano` (the plan-pinned assignment model) burned 16.5K
reasoning tokens, finished with `finish_reason=stop`, and returned `{"assignments":[]}` for
a realistic 25-document batch — on both the first call and the targeted repair, at every
reasoning effort (11/25 at minimal; invented/duplicate ids at low). `gpt-5-mini` assigned
25/25 cleanly on the identical prompt.

Every LLM seam therefore validates **coverage in code**, never trusting the schema:
characterise computes the exact expected id set per batch, classifies deviations by case
(invented → dropped in code; missing ∪ unknown-theme → one targeted repair call; repair
exhaustion → honest `CharacteriseFailure`, nothing persisted), and asserts
`screened_in == grouped + unclustered` in the component itself, not just in tests.

# Why

The failure is silent by construction: no exception, no refusal, a 200 response that parses
and validates. Without count invariants the run would have persisted an empty grouping as if
the corpus had no themes. It also means **model right-sizing needs live evidence per task
shape** — nano-class handled the schema fine and the task not at all, and no stub or
fixture test can catch that.

# Watch out

- When pinning a cheaper model for a bulk stage, the pin is plan-gate detail — flip it on
  live evidence without ceremony, but flag the deviation (verification.md records the
  nano→mini flip and the standalone reproduction).
- Repair loops must receive the *residue*, not the whole batch, and be call-capped —
  a model that returns empty twice must fail the component, not loop.

# Citations

- [009-characterise/verification.md](../tasks/009-characterise/verification.md)
  (§ Live-check failure that shaped the build)
- `_validate_assignments` / `_resolve_assignment_batch` in `src/policy_atlas/characterise.py`
- Tests: validation/repair case tests in `tests/test_characterise.py`
