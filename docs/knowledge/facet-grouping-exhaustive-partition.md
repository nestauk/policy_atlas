---
type: Invariant
title: Facet grouping is an exhaustive partition with honest residuals, enforced at write
description: The grouped set is exactly the referenced extraction run's finding set (resolved via docs[].extraction_record_id, count cross-checked); every finding lands in exactly one of group/ungrouped/no_value; sum identities — including the overall direction spread — are re-asserted on the payload immediately before the single row write.
tags: [group, facet-grouping, exhaustiveness, flag-not-drop, invariant, provenance]
timestamp: 2026-07-07
---

# Rule

`group_findings` (`group.py`) writes one `grouping_result` row per run, and the payload it
writes is an **exhaustive partition** of the referenced extraction run's findings:

- The finding set is resolved via the roll-up's own `docs[].extraction_record_id` entries
  (fresh and memo-reused alike), project-guarded, and cross-checked against
  `counts.findings.total` — a mismatch is a structural `GroupError`, no row.
- The LLM's only job is partitioning **distinct facet values**; finding membership derives
  in code (finding → its value → the value's group). Values the model misses or that fail
  validation land in a counted `ungrouped` bucket; findings with a NULL facet land in
  `no_value`. Nothing is dropped, nothing is forced into a catch-all (forbidden-generic
  labels reject the response).
- `assert_grouping_invariants` (`facet_values.py`) re-checks the built payload immediately
  before the insert: every finding id covered exactly once across
  groups/`ungrouped`/`no_value`, `Σ sizes + residuals == findings_total`, per-group and
  per-residual direction spreads sum to their bucket sizes, and the **overall** direction
  spread sums to the finding count. Validation at the model seam
  (`validate_partition`) is necessary but not trusted alone — the write path re-verifies.

# Why

Group sits on the trust path: synthesise (013) grounds its sections in these memberships by
`grouping_run_id`. V2's aggregation silently zeroed `mixed`/`unclear` findings and collapsed
leftovers into "General Theme" — the invariant closes both defect classes in code, not
prompt rules. Re-asserting at write (belt-and-braces after the seam validation) means no
code path — repair merges, residual bookkeeping, payload assembly — can ship a row that
under- or double-counts a finding. Direction spreads are counts, never verdicts; the
consensus roll-up stays a deferred seam.

Related: [plan-compile-fails-closed](plan-compile-fails-closed.md) (the fail-closed
posture), [citation-flag-dont-drop](citation-flag-dont-drop.md) (flag-don't-drop
precedent), [assert-on-row-not-summary](assert-on-row-not-summary.md) (how a gap in this
payload was caught).
