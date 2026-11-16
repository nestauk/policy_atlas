---
type: Integration quirk
title: A scoped pgvector search keeps its chunk list NOT MATERIALIZED, fuses on ranks, and sizes its latency claim to the scope
description: A MATERIALIZED CTE for the scope's chunk list makes the planner scan the whole chunk_embedding table (60 s a query on 7.5 GB); NOT MATERIALIZED keeps the probe by chunk id at about 100 ms a leg. pgvector sums in float32, so the SQL order can differ from a float64 Python order on near-ties; fuse on ranks and parity holds. A tokens rule must match [0-9A-Za-z]+ before lowering (lower-then-match differs on the Kelvin sign and the dotted capital I). "Under 100 ms" measured on 900-unit scopes does not carry to 9,000-unit scopes on a 128 MB buffer pool; compare search timings only across sessions with the same concurrent write load.
tags: [retrieval, postgres, pgvector, planner, parity, "057"]
timestamp: 2026-11-03
---

# Rule

- **`NOT MATERIALIZED` on the scope's chunk list.** The planner then repeats the chunk join
  once per leg (about 100 ms each on the dev corpus) instead of scanning the whole table.
  Write the reason on the statement.
- **Fuse on ranks, not scores.** pgvector's distance is a float32 sum; the deleted Python
  retriever summed in float64; ties below 1e-6 reorder. Reciprocal-rank fusion over each
  leg's rank is identical on both sides.
- **Tokens: match, then lower.** `[0-9A-Za-z]+` on the raw text and then `lower()`, in SQL
  and in Python alike; the other order is not the same function.
- **Size the latency claim to the scope and the box.** Docker Postgres with 128 MB of shared
  buffers re-reads about 50 MB of vectors per large-scope search; 250 to 600 ms warm on 3,400
  to 9,000-unit scopes, 2 s cold, and 2 to 3 × that under a concurrent run's embedding
  writes. A contract figure measured on a small scope is not a figure for a large one.
- **`EXPLAIN (ANALYZE, BUFFERS)`** per leg is the fastest way to see where a slow statement
  spends its time (32,000 buffers from disk on the first materialised attempt).

# Why

Task 057 moved chunk retrieval into one SQL statement (ADR 0043). The first draft
materialised the scope list and took 60 s a query; the fix was one keyword. Parity against
the Python retriever on 88 recorded queries held only after fusing on ranks. The contract's
"under 100 ms" (N8) was measured on the plan's small scopes and is not met on the fixed
questions' scopes; the owner rules on it at the review (deviation 7).
