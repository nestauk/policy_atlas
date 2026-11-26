---
type: Invariant
title: A queue query filters dead and waiting rows before its limit, not in the loop
description: A worker that takes the oldest N rows and then skips the ones it cannot serve lets N dead rows hide every live row behind them. Every rule that makes a row unservable belongs in the WHERE clause, before ORDER BY and LIMIT.
tags: [postgres, queue, sweep, starvation]
generated:
  by: agent:task-cycle-review
  at: 2026-11-26
---

# Rule

The self-signup sweep takes at most 200 requests in a run, oldest first. A request can be unservable for good (a refusal), for a while (it failed in the last 15 minutes), or until an operator acts (its invite code matches no usable link and its domain is not listed).

If these tests run in Python after the query, 200 old unservable rows fill the batch every run and a new, servable request never gets its turn. So each test is part of the query's `WHERE`, and the limit counts servable rows only.

The same rule has a second copy in Python (`invite_request_reason`), because the redemption checks it again under the row locks and the Requests page shows the reason. A change to one copy must change the other.

# Evidence

- `backend/src/policy_atlas/ops/sweep.py` (`_candidates`): the `held_back` and link conditions sit before `.limit(...)`.
- `backend/tests/ops/test_sweep.py::test_unknown_codes_never_crowd_out_a_redeemable_request` (250 dead rows older than one live row).
- `backend/tests/ops/test_sweep.py::test_a_request_that_always_fails_spends_at_most_four_of_the_hour`.
