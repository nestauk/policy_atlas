---
type: Invariant (verified)
title: A sweep that retries every failure forever lets a poisoned public-form row drive unbounded calls
description: A background sweep over rows from a public form must treat deterministic refusals as terminal, and must count failed attempts against the hourly allowance. Otherwise one bad row is retried every minute, calling the external service each time.
tags: [sweep, retry, public-form, cost, security, "065"]
timestamp: 2026-11-17
---

# Rule

A background sweep reads rows that strangers can create through a public form. If it retries every failure, one row that can never succeed is retried every minute for ever, and each try calls an outside service.

Two rules:

1. **A refusal that will always repeat is terminal.** Mark the row, stop retrying, and show it to a person. Only transient errors (a timeout) stay retryable.
2. **A failed attempt spends the hour's allowance**, the same as a send. The allowance then bounds the calls however many rows are bad.

# Evidence

- `backend/src/policy_atlas/ops/sweep.py`: `TERMINAL_OUTCOMES`, the `_is_transient` split (`failed` versus `refused`), and `invited + failed >= budget`.
- `backend/tests/ops/test_sweep.py`: `test_sweep_refuses_for_good_a_request_the_command_rejects`, `test_sweep_retries_a_failed_row`, `test_sweep_stops_at_the_hourly_invitation_cap`.
- Related: [retry-layers-multiply](retry-layers-multiply.md).

