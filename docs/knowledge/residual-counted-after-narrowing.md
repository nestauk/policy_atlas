---
type: Invariant
title: Count the honest residual inside the loop over already-narrowed rows
description: Incrementing "Not reported" inside landscape_out's loop over base_rows — which the scope filter has already narrowed — makes "bars + residual = the population drawn" true at every scope with no per-scope branching. Placement, not extra conditionals, is what generalises it.
tags: [read-models, honest-absence, landscape, geography, scope, invariant]
timestamp: 2026-08-13
---

# Rule

A chart that drops the records it cannot label cannot add up. The fix is a named residual
bucket — but *where* you count it decides how many scopes it is correct for.

Count it in the same loop that counts the known values, over the row set the caller has
**already** narrowed. Then the identity "known buckets + residual = the population drawn"
holds at every scope by construction, because both sides read the same rows.

As built: `landscape_out` increments `GEOGRAPHY_NOT_REPORTED` inside its loop over
`base_rows`, which the `scope="cited"` filter has already reduced to the latest artefact's
citations. The default scope sums to the funnel's `relevant` count; the cited scope sums to
the cited count. Neither needed a branch.

# Why

Task 031's defect 3: `_geography` returns `None` whenever the provider sent no venue
country — which OpenAlex frequently does — and the chart silently dropped those sources.
A country chart summing to ~15 sat beside a funnel reporting 215 relevant.

The tempting implementation is to compute the residual as `population_total - sum(known)`.
That needs the right `population_total` for each scope, so it grows a branch per scope and
breaks the first time a scope is added. Counting in the loop needs none of that.

# Watch out

- **The payload adding up is not the chart adding up.** The renderers cut to a top-N
  (top 12 in `EvidenceDistributionChart`, top 8 in `ArtefactOutline`). The residual is
  typically large, so it consumes one of those slots and pushes a real value off the chart.
  Assert the identity where it holds — in the read model — and treat the drawn bars as a
  separate, weaker claim.
- **A residual makes the map unconditionally non-empty**, so `if map:` render gates that
  used to hide the chart now always pass. A corpus with no reported countries draws a
  single 100% "Not reported" bar. That is the intended honest absence, but it is a visible
  behaviour change on every render site — check them all, including the ones the diff
  doesn't touch.
- **Every render site needs the caption, or the residual reads as a data bug.** Task 031
  shipped the residual to three sites and updated two; the third still told the user the
  map included author-affiliation geography, which the code has never read.
- **Only the dimension you fixed gets the residual.** The evidence-type and year counters
  in the same loop still drop unlabelled rows, so two charts in one card now obey different
  rules. Say so, or the next reader reads the invariant as card-wide.
- Same family:
  [facet-grouping-exhaustive-partition](facet-grouping-exhaustive-partition.md) (the same
  flag-not-drop identity, enforced at write time),
  [citation-flag-dont-drop](citation-flag-dont-drop.md).
