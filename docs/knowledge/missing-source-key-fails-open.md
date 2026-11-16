---
type: Pitfall
title: A missing or expired search-source key fails open: the run succeeds with the other sources and the owner does not see it
description: Overton returned 401 on every call in task 054's first live run; the search fell back to OpenAlex and the walk succeeded with much less England policy evidence, visible only in the logs. Check the source keys before a live try, and treat a source that answers 401 on every call as a visible run-level warning, not a log line.
tags: [search, overton, api-keys, ops, task-054]
timestamp: 2026-11-05
---

# Rule

- Before a live try, confirm each source key answers 200 on one search (Overton keys expire).
- A source that answers 401 on every call in a walk is a run-level condition the owner should
  see (the run's own events or the chat), not only `search.executed` rows with zero results.
- Read a thin policy-document leg as "was the key valid?" before "is the topic thin?".

# Why

Task 054's first live run (2026-10-26) had no Overton documents at all: the key had expired. The
walk succeeded, the canvas looked thin on England evidence, and the cause was in the logs only.
The key was renewed in iteration loop 1.

# Citations

- [054 verification § Findings for the iteration phase, 1](../tasks/054-toc-integration/verification.md)
- `backend/src/policy_atlas/evidence_search/sourcing/search_live.py` (the Overton client)
