---
type: Convention
title: A mutation that commits and then waits for async work never errors after the commit — it returns what it made
description: The verb add committed the option, then waited 10 s for its option search's walk row and raised on timeout — a 500 for a mutation that had happened, and the chat's pending action stayed pending, so confirming again minted a second option and search. As built, add answers with the option and run_open false, and the pending action is consumed inside the option's own transaction.
tags: [api, idempotency, two-phase, longlist, chat, task-045, convention]
timestamp: 2026-09-24
---

# Rule

Once a mutation's transaction has committed, nothing after it may turn the response into an
error. A wait for follow-on async work (a walk row appearing, a job starting) degrades to "made,
still queued" — the response names what was made and says the follow-on is pending.

And anything that marks the request as done (a chat's pending action, an idempotency record) is
written **in the same transaction as the thing made**, never after it.

As built (`longlist_actions.add_option`): on `_await_new_run` timeout the handler logs
`option.add_search_queued`, hands the reservation release to `_release_when_search_settles`, and
returns `OptionAdded(..., run_open=False)`; the chat path passes `in_commit` so the pending action
is completed inside the option's commit.

# Why

Found by three lanes of the 045 review stack (code-review A4, adversarial, contract deviation 48).
The failure compounds: a post-commit 500 tells the caller nothing was done, and a retry path that
reads "still pending" makes the duplicate certain.

# Watch out

- "Queued" still fences: the task's search reservation is held until the queued search settles,
  so a second add during the wait 409s (`test_longlist_routes.py`, the A4 test stubs
  `_await_new_run` to raise and asserts 201, `opened_run: null`, then 409, then release).
- Same family: [two-phase-retry-terminal-status](two-phase-retry-terminal-status.md),
  [db-row-is-the-single-flight-authority](db-row-is-the-single-flight-authority.md).

# Citations

- `backend/src/policy_atlas/api/longlist_actions.py` (`add_option`, the `_await_new_run` branch)
- `backend/src/policy_atlas/api/longlist_turns.py` (`complete_in_commit`)
- [045 verification.md](../tasks/045-scoping-longlist/verification.md) § Review findings (A4, deviation 48)
