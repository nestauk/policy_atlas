---
type: Testing rule
title: Parity across independent walks must compare structure, not raw UUIDs
description: Two independently-produced walks (resumed-from-park vs. unbroken) can never be literally equal — every generated id differs. Canonicalise each walk's UUIDs to first-seen structural placeholders before comparing, and prefer snapshot read-back over re-derivation for parity-critical fields.
tags: [testing, continuation, parity, uuid, review-lesson]
timestamp: 2026-07-21
---

# Rule

When a test compares two independently-produced walks' composed state for
parity (a walk resumed from a park vs. an unbroken walk that never parked), the
comparison must be **structural**, not literal: canonicalise each walk's UUIDs to
first-seen placeholders (`<uuid-1>`, `<uuid-2>`, ...) via a fixed identity
traversal, then compare the canonicalised structures. Raw UUID equality between
two independently-generated walks can never hold — every `capability_run_id`,
`plan_id`, and component `run_id` is freshly minted by each walk.

`test_continuation_parity.py`'s `_WalkCanonicalizer` implements this:
`_register_walk_uuids` walks each state's fields in a fixed order to assign
placeholders before the general `_normalise_value` pass runs, and
`_assert_parity` compares both the sixteen continuation-annex fields and the
byte-level surface render after canonicalisation.

# Why

Build history for this test shows the broken (literal) comparison was written
**twice** before the canonicalisation was pinned — an easy trap, because the two
walks really are supposed to be identical in every way that matters, just not
byte-identical on generated identity.

Separately: prefer **snapshot read-back over re-derivation** for parity-critical
fields. `completed_components` is read directly from the `run.parked` JSONB
snapshot (the G2 pattern) rather than re-derived from `step_outcomes`; the
derived fallback exists only to cover snapshots written before the field
existed. Reading the persisted value is the primary source of truth for a field
that drives `remaining_steps` on resume.

# Watch out

The canonicalizer assigns placeholders in **first-seen order per walk** — if the
two walks' field-traversal order ever diverges (e.g. one code path visits
`successful_runs` before `attempted_runs` and the other doesn't), the same
logical UUID can get different placeholders and the comparison spuriously
fails. Both walks must traverse fields in identical order.

# Citations

- `backend/tests/runtime/test_continuation_parity.py` (`_WalkCanonicalizer`,
  `_register_walk_uuids`, `_canonicalise_parity`, `_assert_parity`)
- `backend/src/policy_atlas/runtime/continuation_state.py` (`completed_components`
  snapshot read-back)
