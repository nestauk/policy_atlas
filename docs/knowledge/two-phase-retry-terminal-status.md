---
type: Invariant (verified)
title: Retry-in-place two-phase persistence must accept the retried row's terminal status in phase two
description: A phase-2 completion UPDATE guarded only by status='pending' 500s the moment a failed row is legitimately retried in place — the happy path never exercises this; the WHERE must accept pending|failed (planning.py phase two, Codex A.1 bug fixed by the lead, regression-tested).
tags: [two-phase, retry, idempotency, planning-transcript, sql]
timestamp: 2026-07-29
---

# Rule

In a two-phase write with retry-in-place semantics (phase 1 reserves a durable
row; phase 2 completes it; a failed attempt retries **the same row**), the
phase-2 `UPDATE ... WHERE status IN (...)` must include the retried row's
terminal status (`failed`), not just the fresh status (`pending`). The happy
path never sees the difference; the first real retry 500s.

`planning.py::create_planning_turn` is the shipped instance:
`WHERE status IN ('pending','failed')`, with the retry rules (latest-only, 409
`stale_turn`) enforced in phase one. Regression test:
`test_failed_turn_retries_in_place_and_stale_rules_are_honest`.

# Why

Found as a live bug in the Codex-built A.1 (027): phase two accepted only
`pending`, so every retry-in-place of a failed turn died at the completion
UPDATE. The general shape — a guard written for the fresh path that quietly
excludes the retry path — recurs anywhere two-phase + retry-in-place meet.
