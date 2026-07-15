---
type: Performance convention
title: Pure-Python vector maths on hot paths — math.sumprod + norms precomputed at construction
description: math.sumprod (py>=3.12) is the stdlib answer to hand-rolled dot-product loops on hot paths (~50-100x, C speed, zero deps); precompute unit norms once when the vector set is frozen for the object's lifetime. Caveat, extended-precision accumulation can reorder near-ties, so it is observable-change class, not output-identical.
tags: [performance, stdlib, embeddings, retrieval, pitfall]
timestamp: 2026-07-14
---

# Rule

When a hot path needs a dot product / cosine over embedding-sized vectors, use
**`math.sumprod`** (stdlib, requires-python ≥3.12 — this repo qualifies) instead of a
per-element Python loop, and **precompute norms once at construction** when the vector
set is frozen for the object's lifetime (compute the query-side norm once per call, not
per pair). That is the whole optimisation: same formula, C-speed arithmetic, zero new
dependencies — no numpy for one hot loop.

# Why

`ChunkRetriever._cosine` hand-rolled the dot product over 1536-dim vectors with a Python
loop + `zip(strict=True)`, recomputing *both* norms per pair, and ran it against every
filtered unit in the pool on every `search_chunks` call from the synthesis writer —
plausibly tens of seconds of interpreter arithmetic per run. The fix (023 WP10c,
`synthesis_tools.py::ChunkRetriever`) precomputes unit norms in `__init__` (the class
already did exactly this for lexical tokens — follow the existing pattern) and computes
the query norm once per search. ~50–100× on the arithmetic; verified correct by two
independent review lanes.

# Watch out

`math.sumprod` accumulates in **extended precision** — results can differ from the naive
loop in the last ulp, which can *reorder a near-tie* in a score ranking. This is why the
change is **observable-change class, not output-identical**: name it as an explicit
exception when a slice is otherwise behaviour-preserving (023's contract did), keep ties
themselves stabilised by a deterministic key (`_ranked_pool` sorts ties by `unit_id`),
and preserve any zero-norm guard when refactoring.

# Citations

- [src/policy_atlas/evidence_base/synthesis/synthesis_tools.py](../../src/policy_atlas/evidence_base/synthesis/synthesis_tools.py) — `ChunkRetriever` (`__init__` norm precompute; `search`)
- docs/tasks/023-codebase-health/review-findings.md § Lane 7 #7 (the finding + precision analysis)
