---
type: Invariant
title: Citation row written before GroundingError — fail evidence survives
description: The citation row (and annotation) are inserted before GroundingError is raised, so a fabricated-quote failure leaves a durable DB record with verification_result='fail'.
tags: [grounding, citation, flag-dont-drop, invariant]
timestamp: 2026-06-29
---

# Status: RETIRED (2026-07-15, task 023 step-9 rider)

The mechanism this concept describes was deleted: `produce_grounded_block` (and the
deterministic grounding leg around it) was production-caller-less after 023's echo-chain
cut, and the owner directed dissolving `grounding.py` at the step-9 gate (`content_hash`
moved to `core/hashing.py`; the dead leg and its tests deleted, including
`test_fail_annotation_survives_commit`, which had already gone with the echo cut). The
**flag-don't-drop principle itself is not retired** — it is spec-level
([provenance-grounding.md](../specs/system/provenance-grounding.md)) and lives on in the
extract-side verification chain (`quote_verify.py`, the vetters' persisted verdicts).
The text below is the historical record of the original mechanism.

# Rule

In `produce_grounded_block`, the `annotation` and `citation` rows are both written
**before** `GroundingError` is raised. A fabricated-quote failure therefore always leaves:
- `annotation.payload["verification_result"] = "fail"`
- `citation.verification_result = "fail"` with a non-null `chunk_id` FK

The failure is flagged and persisted — never silently dropped or retried.

# Why

Provenance requires a durable audit trail of what was attempted, including failures. A rollback
that erases the failed citation would destroy the evidence that a fabricated quote was produced.

# Watch out

This invariant **depends on the harness catching `GroundingError`** before the transaction boundary.
The LangGraph harness (`_run_echo`) catches `GroundingError` and returns a failed-state result
without re-raising — the `engine.begin()` block in `skeleton.py` exits cleanly and commits.

A direct caller of `produce_grounded_block` outside the harness that lets `GroundingError`
propagate past its own `engine.begin()` boundary will roll back the annotation and citation rows,
losing the fail evidence. Verified by `test_fail_annotation_survives_commit` (committed transaction,
fresh connection read-back).

# Citations

- [system/provenance-grounding.md](../specs/system/provenance-grounding.md) (flag, don't drop)
- [003-source-snapshot/contract.md](../tasks/003-source-snapshot/contract.md) (Fabricated quote → hard-fail; flag-don't-drop)
- [003-source-snapshot/verification.md](../tasks/003-source-snapshot/verification.md) (test_fail_annotation_survives_commit, test_produce_grounded_block_fabricated_quote_hard_fail)
