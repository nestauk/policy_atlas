---
type: Convention
title: Reject model output at the grain of the fault — and persist the rejection reason
description: Style/text-rule violations reject only the offending unit (group, claim), routing its inputs to the repair; only structural corruption (id integrity, unparseable envelope) rejects a whole response. Every persisted rejection/repair decision carries its reason.
tags: [validation, repair, grouping, synthesise, flag-dont-drop, convention]
timestamp: 2026-07-08
---

# Rule

When validating model output that has sub-units (groups in a partition, claims in an
emission):

- A **text/style-rule violation** (over-long or forbidden label, empty description,
  malformed single claim) rejects **only that unit**; its inputs flow to the repair
  (`missing_ids`, per-claim salvage). Implemented in `facet_values.validate_partition`
  (group grain, 012 fix) and `synthesis_backend._salvage_claims` (claim grain, 013).
- **Structural corruption** — unknown or double-assigned ids, an unparseable envelope —
  still rejects the whole response: the output has desynchronized from the input, and
  cherry-picking from it would trust broken bookkeeping.
- Whatever is rejected, the **reason persists** with the run
  (`grouping_provenance.rejection_reasons`, `claims_rejected_structural` + flags) —
  a decision diagnosable only from a Langfuse trace is itself a defect.

# Why

The 013 live check lost both intervention-facet grouping runs to whole-response
rejection: the model proposed 16 coherent, id-clean groups four times and every call was
discarded for one 89–92-char label, landing 0 groups from 179 findings. Outcome runs
survived at 78 chars — the cliff was one string budget wide. And because only
`repair_count` persisted, the cause lived solely in the trace; the build guessed "model
drift" and was wrong (failure-log 2026-07-08).

# Watch out

Unit-grain rejection must not weaken invariants that are response-global: id integrity
is still checked across rejected units (a stripped group's ids still count as assigned),
and the final result must still satisfy partition exactness / the claim-validation
gates. The repair prompt contract matters too — rejected units' inputs must re-enter the
repair with the accepted units pinned, or the repair can contradict what was kept.
