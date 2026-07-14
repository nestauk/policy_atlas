---
type: Runbook
title: Per-run $ cost is recoverable from Langfuse by summing trace totalCost over the run's time window
description: No run-id key is needed — sum trace `totalCost` over the run's start/end window via the public API; 022's cost protocol used this for all three arms and it is the same source as the historical $15.45 baseline, keeping before/after comparisons like-for-like even when the price vector isn't checked in.
tags: [langfuse, cost, tracing, runbook, evaluation]
timestamp: 2026-07-14
---

# Rule

To attribute $ cost to a run that spans many model calls: record the run's
wall-clock window, then sum `totalCost` across Langfuse traces in that window
via the public API. No run-id correlation key is required — back-to-back runs
just need non-overlapping windows (022's cost protocol ran its three arms
sequentially, same day, for exactly this reason).

# Why

Token counts live in the app's own usage accumulators, but $ requires the
price vector, which lives in Langfuse's model config — summing there avoids
maintaining a second price table. Comparisons stay honest as long as both
sides of a before/after use the same source: 022's −49% ($7.95 vs $15.45) is
Langfuse-window vs Langfuse-window.

# Watch out

- Window sums are not reconstructable from retained token JSONs alone — if an
  audit must re-derive $, it needs the Langfuse window (record it with the run
  ids) or a checked-in price vector.
- Overlapping concurrent runs poison the window method; serialize cost-protocol
  arms or fall back to trace-level filtering.

# Citations

- [022 verification.md § Cost measurement](../tasks/022-synthesis-refinement/verification.md)
- 022 cost protocol harness (session scratchpad `live_check_022_synthesise.py`, retained locally)
