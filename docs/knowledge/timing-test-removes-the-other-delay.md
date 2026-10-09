---
type: Testing rule
title: A test of one delay must switch the other delays off — a retry back-off satisfied the rate-limit pause assertion with the pause deleted
description: When a code path has two sleeps (a retry back-off and a pacing pause), an assertion that the next request landed "at least a pause later" is met by the back-off alone; set the other delay to zero (monkeypatch the constant) and assert equality with the pause, then prove the test fails with the pause stubbed out; the same shape applies to a shared list of recorded sleeps across two halves of one test.
tags: [testing, timing, rate-limit, tautology]
timestamp: 2026-10-09
---

# Rules

- **Zero the other delay.** `test_a_429_pauses_every_threads_admission` sets
  `RETRY_BACKOFF_S` to 0 and asserts the retry's admission stamp equals
  `100 + RATE_LIMIT_PAUSE_S`; with the pause stubbed to a no-op the stamp is
  `100 + interval` and the test fails. Before the fix it passed either way.
- **Clear recorded sleeps between halves.** `test_semantic_retry_and_interval` recorded
  the retry half's 1 s back-off and then asserted "some sleep >= 1 s" for the interval
  half; `sleeps.clear()` between the halves makes the second assertion mean something.
- **Coalesce, do not stack, a shared pause.** `_pause_admission` sets the next admission
  to `max(current, now + pause - interval)`; eight threads refused in the same instant
  pause once (`test_rate_limit_pauses_coalesce`). The stacking form added a pause per
  refusal.

# Why

Two lanes of the 051 review found the stacking pause; one found that the test meant to
guard the pause guarded nothing. A rate-limit pause under concurrency is exactly the
code that only a correct test can keep honest, since no live run exercises it on demand.

# Citations

- [051 verification § Review findings](../tasks/051-improve-production-search-screen/verification.md)
- `backend/tests/evidence_search/sourcing/test_search_wire.py`;
  `backend/src/policy_atlas/evidence_search/sourcing/search_live.py` (`_pause_admission`)
