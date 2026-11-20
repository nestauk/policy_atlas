---
type: Convention
title: Bound search volume at acquisition, never with a time budget inside the fan-out
description: Each search depth caps the records kept from the ranked pool (papers_cap, policy_cap) and the planned provider calls (call_budget). No depth has a wall clock, because a time budget over an ordered fan-out silently drops its tail.
tags: [search, budgets, fan-out]
generated:
  by: claude-opus/5.5
  at: 2026-11-20
sources:
  - id: search-loop
    resource: backend/src/policy_atlas/evidence_search/sourcing/search_loop.py
    title: DEPTH_CONSTANTS
---

# Rule

- `DEPTH_CONSTANTS` in `evidence_search/sourcing/search_loop.py` holds, per depth, two caps on
  the records persisted from the ranked pool (`papers_cap`, `policy_cap`) and a budget of
  logical calls per provider (`call_budget`). A logical call is one planned provider request,
  even when it pages or retries.
- Bound volume where records are persisted, after every query has had its turn. Do not divide
  one total across the fan-out (it shrinks as the fan-out grows) or let calls consume a shared
  total in order (the first call can take it all and the rest are skipped).
- Do not add a wall clock inside the fan-out. Providers run in order, so a time budget cuts a
  specific tail of queries and providers, and the run still looks adequate. If a latency bound
  is needed, it belongs at the runner as a step timeout.

# Why

Each of these shapes once dropped searches with no error: a serial shared cap, a cap divided
by the fan-out width, and a wall clock that cost a whole policy source. Persisting a record
also commits to screening and embedding it, so acquisition is the place where the bound has
to bite.
