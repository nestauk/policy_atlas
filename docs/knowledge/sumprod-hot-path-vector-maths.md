---
type: Performance convention
title: Vector maths runs in the database; the one Python cosine uses math.sumprod
description: Chunk retrieval for synthesis is one SQL statement using the pgvector cosine distance operator. The remaining pure-Python cosine (theory-of-change selecting) uses math.sumprod. Do not add a Python loop over embeddings on a hot path.
tags: [performance, embeddings, retrieval]
generated:
  by: claude-opus/5.5
  at: 2026-11-20
sources:
  - id: synthesis-tools
    resource: backend/src/policy_atlas/evidence_search/synthesis/synthesis_tools.py
    title: ChunkRetriever
  - id: selecting
    resource: backend/src/policy_atlas/theory_of_change/check/selecting.py
---

# Rule

- `ChunkRetriever` (`evidence_search/synthesis/synthesis_tools.py`) ranks chunks in one SQL
  statement with the pgvector cosine distance operator (`<=>`). Keep vector ranking in the
  database rather than loading embeddings into Python.
- Where Python must compute a cosine (`theory_of_change/check/selecting.py`), use
  `math.sumprod` and guard a zero norm. It is much faster than a per-element loop.

# Watch out

`math.sumprod` adds up in extended precision, so a result can differ from a plain loop in the
last digit and reorder a near-tie. Break ties in a ranking with a fixed key.
