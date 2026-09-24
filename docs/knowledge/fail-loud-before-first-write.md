---
type: Invariant
title: Same-run re-execution fails loud before the first write — failure events need a healthy transaction
description: synthesise_scope checks for an existing (scope, run) roll-up before writing anything; a UNIQUE-constraint failure at the end of a run poisons the transaction, so the harness's component.failed event write itself fails and no audit record survives.
tags: [harness, events, transactions, synthesise, invariant]
timestamp: 2026-09-24
---

# Rule

`synthesise_scope` guards same-run re-execution with a `SELECT` **before any write**
(artefact mint included), raising `SynthesiseFailure("same_run_reexecution: …")` while
the transaction is still healthy. The `uq_synr_scope_run` UNIQUE constraint remains as
the concurrent-writer backstop only.

# Why

Every `run_harness` node's exception handler appends the `component.failed` event **on
the same connection**. If the failure is itself a DB error (IntegrityError at the
roll-up insert), Postgres has aborted the transaction: the event insert fails, the
handler dies, a confusing `InFailedSqlTransaction` escapes `run_harness`, and no audit
record of the failure exists anywhere. Found by the 013 review stack's Codex lane; the
original test bypassed the harness entirely and asserted only the raw IntegrityError.

# Watch out

The general seam is still open (deferred.md § Execution): any component whose failure
mode is a DB error hits the same event-write-on-aborted-transaction hole. Until the
harness gets a savepoint (or writes events after rollback), new components should follow
this pattern — validate loudly against the DB **before** the first write, so their
declared failure modes never surface as constraint violations.

**045 recurrence (the harness layer is still open).** Task 017 moved the product path's failure
record onto a fresh transaction (`runner.py::_record_failure_backstop`), but
`harness._run_scope_component`'s generic `except` still appends `component.failed` on the
component's own transaction without rolling back. In 045's live check a `uq_ser_memo` race
between two child walks surfaced in the event log as `InFailedSqlTransaction`, hiding the cause
until the memo writes moved into savepoints
([sibling-walk-memo-writes-reuse-and-sorted-locks](sibling-walk-memo-writes-reuse-and-sorted-locks.md)).
Any component whose failure is a DB error still reads that way (deferred.md § Options scoping
longlist, "Component failure events land on an aborted transaction").
