---
type: Invariant
title: Same-run re-execution fails loud before the first write — failure events need a healthy transaction
description: synthesise_scope checks for an existing (scope, run) roll-up before writing anything; a UNIQUE-constraint failure at the end of a run poisons the transaction, so the harness's component.failed event write itself fails and no audit record survives.
tags: [harness, events, transactions, synthesise, invariant]
timestamp: 2026-07-08
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
