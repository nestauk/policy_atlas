---
type: Integration
title: Facet partitioning has a hard value-list scale limit on the current prompt/model
description: group_facet_v1 on gpt-5.4-mini reliably emits duplicate value ids at ~184 distinct facet values (4/4 live attempts including repairs, persisted rejection_reasons "partition: duplicate id"), degrading honestly to the all-ungrouped residual; kind-spanning membership doubles the value list, so Slice C's facet redesign must treat value-list scale as a first-class constraint (batching or id-scheme change), not a retry problem.
tags: [group, facet-grouping, model-capacity, gpt-5-mini, slice-c, scale]
timestamp: 2026-07-13
---

# Rule

Do not retry your way past partition-validation failures at large value
counts: at ~184 distinct `intervention` values (021's both-profiles live run —
333 findings across two kinds), `group_facet_v1` on `gpt-5.4-mini` emitted
duplicate value ids in **every** call and repair (4/4 runs), and the
fail-closed validator correctly rejected each partition. The runs degraded
honestly to the all-ungrouped residual with the reasons persisted on the row
(`rejection_reasons: ["partition: duplicate id v126", …]`). This is a capacity
limit of the current prompt+model at that list size, verified live and
diagnosable from durable data alone.

# Why

021's kind-spanning membership widened grouping's reach to both finding
schemas, roughly doubling the value list a single partition call must cover —
the failure is structural, not stochastic. Recorded at the 021 review stack as
a REQUIRED input to Slice C's multi-facet redesign: the design must bound the
per-call value list (batched partitioning, hierarchical merge, or a
shorter/duplicate-proof id scheme) before any facet beyond `intervention`
lands.

# Watch out

- The degradation path is working as designed
  ([facet-grouping-exhaustive-partition](facet-grouping-exhaustive-partition.md));
  the residual still carries per-kind member counts, so downstream synthesise
  runs remain honest — but grouped-run envelope carriage at this scale is only
  stub-pinned, not live-evidenced.
- Persisting the rejection reason is what made this diagnosable without
  traces — keep that property in any redesign (013 lesson).
