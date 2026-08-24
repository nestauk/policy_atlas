---
type: Invariant
title: Claim coverage is per marker occurrence, never per citation number
description: A citation number can anchor several sentences ("Claim A [1]. Claim B [1]."); if coverage is keyed by number, the unclaimed sentence silently wears the judged claim's verdict at its marker. The floor derives a sentence-grain claim for every uncovered occurrence.
tags: [citations, claims, judge, enrichment, chat-floor, honesty, invariant]
timestamp: 2026-08-11
---

# Rule

`derive_claims_for_uncovered_citations` (runtime/chat_floor.py) scans every
`[n]` marker occurrence: a span-bearing claim covers an occurrence only when
its span overlaps that occurrence's anchoring sentence; a span-less claim
covers only the first still-uncovered occurrence of its number; every
occurrence left uncovered gets its own derived, marker-anchored claim (the
sentence ENDING at the marker — models place markers on either side of the
full stop). Enrichment shares the same function, so pre-derivation rows check
identically.

# Why

The verdict display resolves per citation marker; the judge rules per claim.
If those grains diverge, an unjudged assertion inherits a judged one's tier —
dishonest in exactly the way the floor exists to prevent. Found by the 029
Codex adversarial lane; the pre-fix tests only ever exercised one marker per
citation.

# Watch out

Any new surface that renders per-marker verdicts must keep judgment grain ==
display grain. If a claim can cover multiple markers legitimately (a span
spanning two sentences), the span-overlap check is the arbiter — not the
citation number.
