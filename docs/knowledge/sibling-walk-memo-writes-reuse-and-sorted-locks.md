---
type: Invariant
title: Sibling walks writing one memo key reuse each other's row in a savepoint, behind advisory locks taken in sorted key order
description: The extraction memo is keyed per (task, snapshot, fingerprint), so two option searches profiling a shared document race on uq_ser_memo. As built, each document's writes run in a savepoint and a memo conflict becomes "reused" of the sibling's row, and one pg_advisory_xact_lock per memo key is taken in sorted order before the first write, so overlapping siblings serialise instead of deadlocking — without reordering the writes themselves.
tags: [extract, memo, concurrency, savepoint, advisory-lock, deadlock, task-045, invariant]
timestamp: 2026-09-24
---

# Rule

In `extract._write_docs` (shared by the ES extract profiles and the scoping profile):

1. **Lock first, sorted.** Before any write, `_lock_memo_keys` takes a transaction-scoped
   `pg_advisory_xact_lock` per memo key (sha256 of `ser_memo:{task}:{snapshot}:{fingerprint}` →
   signed 64-bit), in sorted key order. Two siblings with overlapping documents block on their
   first shared key instead of each holding one unique-index entry the other needs.
2. **Write per document in a savepoint.** On an `IntegrityError` that is a `uq_ser_memo` conflict,
   only that document's savepoint rolls back and the document becomes `reused` of the sibling's
   row — never `failed`, never an aborted component transaction. Any other integrity error re-raises.

# Why

- The race was live (045 Phase 8, child `61291f72…`): two children hit `uq_ser_memo`, and the
  harness appended `component.failed` on the aborted transaction, so the event log said
  `InFailedSqlTransaction` instead of the cause ([fail-loud-before-first-write](fail-loud-before-first-write.md)).
- The deadlock was the review stack's (code-review L7, adversarial): the savepoint catches only
  `IntegrityError`, and siblings inserting shared keys in different orders can deadlock.
  **Sorting the write loop broke the ES write-order contract test** — hence locks in sorted order
  and writes in their original order.

# Watch out

- The savepoint path changed ES extraction too (IOF/ICF share it; contract verifier F9): a memo
  clash there is now reuse, not failure. Benign, but not "scoping only".
- Advisory keys are a hash; a collision costs a needless wait, never correctness (same trade as
  [tenancy-predicates-in-sql](tenancy-predicates-in-sql.md) rule 4).
- Siblings still serialise on the task's event-log sequence
  ([event-log-sequence](event-log-sequence.md)).

# Citations

- `backend/src/policy_atlas/evidence_search/extract/extract.py` (`_write_docs`, `_lock_memo_keys`, `_memo_lock_key`, `_reuse_sibling_row`)
- Test `test_a_sibling_walk_s_memo_row_is_reused_not_a_failed_transaction`
- [045 verification.md](../tasks/045-scoping-longlist/verification.md) § Phase 8 live-check fixes; § Review findings (L7, F9)
