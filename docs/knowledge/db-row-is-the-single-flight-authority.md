---
type: Invariant
title: Cross-process turn correctness lives in the DB row, never in process-local state
description: Chat-turn single-flight, cancel, and capacity are all decided by the chat_turn row's status under the task row lock. Process-local locks and registries are latency optimisations only — every one of the 029 review stack's race findings was a path where local state was treated as the authority.
tags: [chat, concurrency, single-flight, cancel, idempotency, two-phase, invariant]
timestamp: 2026-08-11
---

# Rule

For `chat_turn` (and any future durable turn surface):

- **Single-flight**: a live `pending` row for a conversation IS the in-flight
  turn. `_phase_one_turn` evaluates it inside the locked, TTL-swept section; a
  same-`client_turn_id` request against a fresh pending row 409s
  (`chat_turn_in_progress`) unless it is the worker re-entering its own
  reservation (`reserved_turn_id`). The process-local `_turn_locks` only
  short-circuits same-process contention.
- **Cancel**: a durable `pending → cancelled` CAS beats everything. The
  terminal commit's predicate is `status == "pending"` only; on rowcount 0 the
  row is re-read and a `cancelled` status is returned as the cancelled
  outcome, never overwritten to `completed` (and the failure-path UPDATE
  carries the same guard).
- **Reservation leaks**: anything that can refuse a turn after reservation
  (cancel-registry capacity) runs INSIDE the reservation transaction so
  refusal rolls the row back; anything that can fail before the service's
  managed path (worker-side fences) CASes its own reserved row
  `pending → failed` with the real error code.

# Why

The 029 review stack converged on this from three families independently:
Codex + the security lane found the cancel-overwrite window; the security
lane's TOCTOU analysis showed the route pre-check and the threading.Lock
coordinate nothing across processes (double provider spend); `/code-review`
found the two reservation-leak paths (pre-`try` fences, registry capacity
post-commit) and the orphaned-pending-can-never-retry dead end. Single-process
uvicorn masks all of it today; `--workers` or ECS scale-out flips every one on.

# Watch out

Every process-local registry in the chat path (`_turn_locks`, `_live_cancels`)
is a hint, not a fence. When the workspace-cluster work multiplies API tasks,
audit anything new that keeps per-process state about a durable row — the row
must already tell the whole story without it.
