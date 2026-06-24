---
type: Invariant
title: Event-log sequence is app-assigned under a single writer
description: event_log.sequence is assigned max+1 in app code; ordering and append-only live at the repo layer, safe only under a serial single writer.
tags: [event-log, persistence, invariant, concurrency]
timestamp: 2026-06-24
---

# Rule

The canonical `event_log` is append-only (no update/delete) and ordered by `(project_id, sequence)`,
**not** `occurred_at`. `sequence` is assigned application-side as `max(sequence)+1` per project, and
append-only is enforced at the repository layer.

# Why

`occurred_at` is not a sufficient order (ties, clock skew). A per-project monotonic sequence gives a
deterministic read-back order for the canonical audit log, which is kept separate from LangGraph
execution checkpoints (audit plane ≠ telemetry plane).

# Watch out

`max+1` is correct **only under a serial single writer**. If concurrent writers are ever introduced,
move to a DB-side sequence or locking strategy. DB-level append-only enforcement (`REVOKE` / trigger)
is deferred — today it is app-layer only.

# Citations

- [ADR 0001](../adr/0001-walking-skeleton-foundations.md) §6
- [001-walking-skeleton/contract.md](../tasks/001-walking-skeleton/contract.md) (event_log table)
- [docs/deferred.md](../deferred.md) (DB-level append-only enforcement)
