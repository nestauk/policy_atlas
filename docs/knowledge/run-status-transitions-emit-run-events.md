---
type: Invariant
title: Every run-status transition needs a matching run event, or SSE desyncs from the DB
description: SSE replay/tail and the frontend run store derive run.status purely from a curated event-type map; two shipped desyncs (continuation.claimed missing, run.finished-on-abort missing) each left a live run showing the wrong status indefinitely.
tags: [sse, continuation, run-status, event-log, invariant]
timestamp: 2026-07-21
---

# Rule

SSE replay/tail (`routers/sse.py::_frames_for_row`) and the frontend run-status
store derive `run.status` **only** from a curated event-type map: `run.opened` →
running, `run.parked` → paused, `run.interrupted` → interrupted,
`continuation.claimed` → running, plus terminal statuses carried on `run.finished`.
Any code path that flips a `capability_run.status` column value must emit a
matching run event in the **same transaction**, or the SSE-derived view desyncs
from the database — durably, until the next status flip papers over it.

# Why

Two shipped desyncs prove the fragility, both from the 025 slice:

- Resuming a claimed continuation flips `capability_run.status` to `running`
  (`claim_continuation`'s UPDATE) but nothing mapped that to a frame until
  `continuation.claimed` was added to the map — SSE and the live store showed a
  continuing walk as still paused (025 live check).
- `_persist_abort` flips status to `aborted` and the plan to `abandoned`, but
  without a paired `run.finished` event the store had no signal to move the run
  off `paused` — an aborted run showed paused forever (025 review finding).

# Watch out

The map is exhaustive by construction, not by convention. A new status-affecting
path (executor crash handling, a future terminal state) needs its event added
here in the SAME commit that changes the status column. Before trusting this
invariant on a new code path, grep every writer of `capability_run.c.status` and
confirm each one has a corresponding entry in the `sse.py` map.

# Citations

- `backend/src/policy_atlas/api/routers/sse.py` (`_frames_for_row`, the
  `run.status` event-type map)
- `backend/src/policy_atlas/api/continuation.py` (`_persist_abort`,
  `claim_continuation`)
