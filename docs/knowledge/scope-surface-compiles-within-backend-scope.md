---
type: Invariant
title: A scope surface that compiles per-backend must compile within the plan's backend scope
description: country_group compiles filter blocks for both backends; the acquire directive drops the block for a backend the plan's backend_scope excludes — otherwise acquire-time directive validation rejects a plan that already passed approval.
tags: [plan, compile, backend-scope, scope-filters, country-filters]
timestamp: 2026-07-12
---

# Rule

Plan-time validation and acquire-time directive validation must agree about backend
scope. Scalar scope filters are *rejected* at plan validation when they target an
excluded backend (`publisher_country` × `academic_only`). A surface that compiles for
**both** backends (`country_group`) can't be rejected that way — the ask is legitimate
for the in-scope backend — so the compile (`_directive_delta`) drops the out-of-scope
backend's block instead. Without that, `validate_scope_filters` ("Overton filters
supplied outside backend scope") kills an **approved** plan at acquire time: approval
theatre, runtime funeral.

The general form: every new plan surface × `backend_scope` combination needs either a
plan-time rejection rule or a compile-time scoping rule, and a compose test pinning
which.

# Why

Found by the 019 review stack (Codex adversarial MAJOR): `academic_only` +
`country_group` passed plan validation and approval, then failed at acquire. The fix
lives at the compile seam because the intent is honest — filter the backends actually
searched; a backend that isn't searched needs no filter. Two compose tests pin both
scope directions.

# Watch out

- The next scope surface (venue/funder/topic — deferred filter-vocabulary growth) must
  add its own scope-parity test at compose time, not discover it live.
- This complements, not replaces, [plan-compile-fails-closed](plan-compile-fails-closed.md):
  invalid plans still die at construction; this rule is about *valid* plans staying
  runnable.

# Citations

- `src/policy_atlas/orchestration_plan.py` (`_directive_delta` backend_scope pops)
- `tests/test_orchestration_plan.py`
  (`test_country_group_compile_drops_overton_block_for_academic_only_scope` + grey-lit twin)
- [019 verification.md § Review findings](../tasks/019-folding-pass/verification.md)
  (adversarial lane, adopted MAJOR)
