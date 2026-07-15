---
type: Architecture
title: Two-stage clustering (open discovery + validated batch assignment) closes the exhaustive-partition capacity cliff
description: The ~184-value duplicate-id failure was the one-call exhaustive-partition RESPONSE FORMAT, not raw model capacity — open discovery (labels only, never ids) plus batched assignment validated against the deterministically known unit-id list ran 0/9 replay arms with id fabrication on the exact corpus that failed 4/4; the same framing change also removed the over-fragmentation pressure (25 values→12 groups became 30→5 with no lower bound). Component sentinel words must be forbidden in discovery.
tags: [clustering-engine, group, characterise, model-capacity, scale, prompt-design, slice-c]
timestamp: 2026-07-14
---

# Rule

When a model must organise N units, never ask one response to emit an
exhaustive id partition. Split the job (`clustering_engine.py`, task 022):

1. **Open discovery** — the model sees id-keyed unit records but emits ONLY
   labels + descriptions (the output schema has no id fields to fabricate).
2. **Batched assignment** — bounded batches (50) of known units are assigned
   to the fixed label set and validated in code against the deterministically
   known unit-id list: invented ids dropped and counted, double assignments
   routed to residue, missing ids folded back, unplaced units land in the
   counted residual. Discovery stays open; validation binds assignment.

On the exact corpus where the one-call shape failed 4/4 (184 distinct
intervention values, duplicate-id rejections every attempt), the two-stage
shape ran 9/9 replay arms + live checks with **zero id fabrication** — the
cliff was the response format, not model capacity per se.

# Why

The same exhaustive framing was also the **over-fragmentation** driver:
"every value must land" pressure produced 25 values → 12 groups on old rows;
removing it (open discovery under a corpus-relative ceiling, no lower bound)
gave 30 → 5 and 184 → 18–20 with 0–1 singletons — no code-side merges, no
catch-all buckets. One framing defect, two symptom classes.

# Watch out

- **Forbid the component's own sentinel vocabulary in discovery** (`ungroupable`
  wire word, `__ungrouped__` residual label): a corpus-seeded label equal to a
  sentinel either silently misfiles its members into the residual or trips the
  partition invariants — a corpus-triggerable facet failure. Characterise
  guards its `UNCLUSTERED` sentinel; group gained the guard at the 022 review
  stack (`group.py::_forbidden_group_label_reason`).
- Scale pressure moves to batch size and the pre-computable call budget — the
  budget math must match what the repair loop actually spends
  (`assignment_repair_cap` is honoured per batch since the 022 review stack).

# Citations

- [ADR 0018](../adr/0018-multi-facet-clustering-engine.md) (decisions 1, 5)
- [022 verification.md § replay evidence](../tasks/022-synthesis-refinement/verification.md)
- [The failure this closes](facet-partition-value-list-scale-limit.md)
- `cluster_units`, `validate_assignments` in `src/policy_atlas/clustering_engine.py`
