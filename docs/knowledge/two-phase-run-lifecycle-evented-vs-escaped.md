---
type: Convention
title: A runner above self-catching components must distinguish evented failure from escaped exception
description: LangGraph-harness components catch their own exceptions and commit "failed" state cleanly; an exception that escapes means the transaction rolled back — committing run identity before component work makes the fresh-transaction failure backstop's FK trivially valid.
tags: [runner, agent, transactions, failure-semantics, event-log]
timestamp: 2026-07-10
---

# Rule

Components that catch their own exceptions commit `component.failed` state
themselves; an exception that *escapes* to the runner means the transaction
**rolled back** and nothing was committed. `runner.py` (task 017) therefore
runs a two-phase per-component lifecycle: the run row + `run.started` +
`plan.compiled` events commit in their own transaction *before* component
work begins. When an escaped exception then triggers the fresh-transaction
`component.failed` backstop, the run row it references already exists — the
backstop's FK validity is trivial instead of racy.

# Why

Without the identity-first commit, the backstop event would reference a run
row that rolled back with the failure it is trying to record — the exact
DB-abort case (contract decision 8 rev 2.5) it exists for. Fault-injected
tests pin both lanes (`tests/test_runner.py`: DB-abort → `component.failed`
survives on a fresh transaction; evented failures pass through untouched).

# Watch out

The two lanes look identical in the collation ("failed" either way); only the
transaction history distinguishes them. Don't "simplify" the backstop into
the main transaction — it only exists because that transaction can die.
