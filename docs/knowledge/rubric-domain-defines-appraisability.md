---
type: Invariant
title: The rubric's domain defines appraisability — absence means skip-and-count, never score or error
description: appraise_sources scores only evidence types present in DEFAULT_RUBRIC; types absent from it (Non-evidence, Unknown) are skipped and counted, and a domain test against the closed EVIDENCE_TYPES vocabulary makes the lookup infallible.
tags: [appraise, rubric, skip-and-count, invariant, counting]
timestamp: 2026-07-03
---

# Rule

A deterministic scoring component keys eligibility off its mapping's **domain**, not off a
separate eligibility list. `DEFAULT_RUBRIC` maps the 7 evidence types with a hierarchy standing
to scores 1–5; `Other (Non-evidence documents)` and `Unknown / Insufficient information` are
simply absent from it, so they take the skip path (`skipped_non_evidence`, `skipped_unknown`) —
no sentinel scores, no error path. Two guards make the in-domain lookup infallible: the DB check
constraint restricts `primary_evidence_type` to the closed `EVIDENCE_TYPES` vocabulary, and a
domain test pins `set(DEFAULT_RUBRIC) == set(EVIDENCE_TYPES) - {the two non-appraisable types}`,
so adding an evidence type forces the rubric decision at CI time, before it can reach runtime.

# Why

A 1–5 hierarchy score has no honest value for a document that isn't evidence or whose type is
unknown — any number would pollute tier-threshold queries ("must meet tier X"). Keeping
eligibility inside the mapping means there is exactly one place where "appraisable" is defined,
and the skip is visible in every return value and `component.completed` payload rather than
silently dropped.

# Watch out

- **Counting buckets have two different lifetimes.** `appraised` counts rows inserted *this
  call*; `already_appraised` is a pre-insert count; the skip counts and `unclassified` are
  **recomputed from full current state on every call**, so a rerun reports identical skip
  numbers with `appraised == 0`. Mixing the two styles breaks the invariant
  `appraised + already_appraised + skipped_* = classification rows for the scope`
  (test-pinned on both calls of a mixed rerun).
- **Int-keyed dicts become string-keyed in JSONB.** `by_score` is `{5: 2}` in the Python
  return but `{"5": 2}` once serialised into the `component.completed` payload — harness
  tests must assert the string-keyed form.
- The invariant partitions only while classifications are immutable per `(scope, source)`;
  the re-appraisal relaxation seam must revisit `already_appraised`
  (see [deferred](../deferred.md), re-appraisal entry).

# Citations

- [006-appraise/contract.md](../tasks/006-appraise/contract.md) (design decision 2; counting
  semantics) and [verification.md](../tasks/006-appraise/verification.md) (review findings)
- `DEFAULT_RUBRIC` / `appraise_sources` in `src/policy_atlas/appraise.py`
- Tests: `test_rubric_domain_is_evidence_types_minus_non_appraisable`,
  `test_mixed_rerun_skip_counts_stable_and_invariant_holds`, `test_harness_appraise_component`
