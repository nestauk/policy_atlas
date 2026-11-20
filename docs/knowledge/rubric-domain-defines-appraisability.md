---
type: Invariant
title: The rubric's domain defines which evidence types get a score; the rest are written as Unrated
description: appraise_sources scores only the types in DEFAULT_RUBRIC. The two types outside it (Non-evidence, Unknown) get an Unrated appraisal row with no score, so they stay citable. A domain test ties the rubric to the closed EVIDENCE_TYPES list.
tags: [appraise, rubric, unrated, invariant]
generated:
  by: claude-opus/5.5
  at: 2026-11-20
sources:
  - id: appraise
    resource: backend/src/policy_atlas/evidence_search/assess/appraise.py
    title: DEFAULT_RUBRIC, UNRATED_TYPES, appraise_sources
  - id: appraise-tests
    resource: backend/tests/evidence_search/assess/test_appraise.py
---

# Rule

- `DEFAULT_RUBRIC` maps the seven evidence types that have a place in the hierarchy to scores
  1 to 5. `Other (Non-evidence documents)` and `Unknown / Insufficient information`
  (`UNRATED_TYPES`) are outside it. They get an appraisal row with no score and
  `unrated = true`, shown as "Unrated".
- `test_rubric_domain_is_evidence_types_minus_the_unrated_types` pins
  `set(DEFAULT_RUBRIC) == set(EVIDENCE_TYPES) - UNRATED_TYPES`, so a new evidence type forces
  the rubric decision in CI.

# Watch out

- The counts have two lifetimes. `appraised` and `appraised_unrated` count rows written by this
  call; the skip counts and `unclassified` are recomputed from the current state on every call,
  so a rerun reports the same skip counts with `appraised == 0`
  (`test_mixed_rerun_skip_counts_stable_and_invariant_holds`).
- `by_score` has integer keys in Python and string keys once stored as JSONB in an event
  payload. Tests on the payload assert the string keys.
