---
type: Invariant
title: Event-log sequence is app-assigned under a single writer
description: event_log.sequence is assigned max+1 in app code; ordering and append-only live at the repo layer. Since 025, two unserialized writer families exist (the walk executor and task-locked API mutations), so a sequence collision retries under a SAVEPOINT rather than failing the caller's transaction; run_id became nullable for run-less task lifecycle audit events. Since 045 a third family (a longlist walk's concurrent child walks) raised the retry bound 5 → 32 and retired ADR 0001's "one writer per task" — children on one task serialise on each other's uncommitted events.
tags: [event-log, persistence, invariant, concurrency]
timestamp: 2026-09-24
---

# Rule

The canonical `event_log` is append-only (no update/delete) and ordered by `(task_id, sequence)`,
**not** `occurred_at`. `sequence` is assigned application-side as `max(sequence)+1` per task, and
append-only is enforced at the repository layer.

Since 025, `events.append` retries under a **SAVEPOINT** on `(task_id, sequence)` collision: two
unserialized writer families now exist per task — the walk executor and the API's task-locked
mutations — so two appenders can legitimately read the same max concurrently. The unique constraint
turns a race into an `IntegrityError`, which `append` catches, rolls back the nested savepoint, re-reads
the max, and retries (bounded at 5 attempts, hard error after). Collisions re-read; they never fail a
component's outer commit, and misordering remains impossible — the constraint is what makes a collision
loud instead of silent.

Also since 025: `event_log.run_id` is **nullable** (owner-approved gate expansion). Run-less task
lifecycle audit events (`task.renamed`, `task.archived`) attach no run — they happen outside any
capability walk, so there is no run to attach them to.

Since 045: a **third writer family** — a longlist walk's option searches, child walks running
concurrently on the same task (width 4) beside the parent and the API. Five attempts were
exhausted on the stub longlist walk (a child's `run.started`), so `APPEND_ATTEMPTS = 32`, roughly
the number of writers one task can have at once. Ordering is unchanged. ADR 0001 § 6's "one
writer per task" no longer holds; the constraint + retry is what keeps the log ordered.

# Why

`occurred_at` is not a sufficient order (ties, clock skew). A per-task monotonic sequence gives a
deterministic read-back order for the canonical audit log, which is kept separate from LangGraph
execution checkpoints (audit plane ≠ telemetry plane).

# Watch out

`max+1` is correct **only under a serial single writer** for any one task — the 025 SAVEPOINT retry
is what makes "single writer per task at a time" hold under two writer families that aren't
otherwise coordinated, not a relaxation of the ordering guarantee. The third family arrived in 045 and
the bound moved to 32 — any wider fan-out re-checks it.

**The retry is not free** (045 deviation 16, adversarial B8): each collision waits for the
competing writer's commit, and acquire, screen, classify and appraise append events inside long
component transactions — so concurrent child walks on one task wait on each other's uncommitted
rows, and effective concurrency can sit well below the pool width. A per-walk sequence would
remove it (deferred.md § Options scoping longlist).

DB-level append-only enforcement (`REVOKE` / trigger) is deferred — today it is app-layer only.

# Citations

- [ADR 0001](../adr/0001-walking-skeleton-foundations.md) §6
- [001-walking-skeleton/contract.md](../tasks/001-walking-skeleton/contract.md) (event_log table)
- [docs/deferred.md](../deferred.md) (DB-level append-only enforcement)
- `backend/src/policy_atlas/core/events.py` (`append`, SAVEPOINT retry; 025 as-built; `APPEND_ATTEMPTS`, 045)
- [045 verification.md](../tasks/045-scoping-longlist/verification.md) (deviation 16; § Review findings B8)
