---
type: Convention
title: Every model-bearing surface carries its own literal model id — one pin must not move another
description: The agent's triage model defaulted to SCREEN_MODEL, so re-pinning stage-1 screening to gpt-5.6-luna would have silently moved triage too; each surface (screen, triage, query generation, planner) names its model as its own literal (env-overridable), and a pin change is checked by the routing-by-moment test, not by reading the constants.
tags: [models, configuration, routing]
timestamp: 2026-10-09
---

# Rules

- **No surface borrows another's model constant.** `AGENT_TRIAGE_MODEL` is the literal
  `gpt-5.4-mini`; `SCREEN_MODEL`, `SEARCH_QUERIES_MODEL`, `SEARCH_REFORMULATE_MODEL`
  and `SEARCH_SUGGEST_MODEL` are their own literals. A shared import is a hidden
  coupling that a pin on one surface pulls on.
- **The routing test is the guard.** `test_model_routing_by_moment` failed when the
  Phase 4 pin moved triage; it is the check to run after any model change, before the
  prompt-hash re-pin.
- **Prompt text and model id are pinned separately.** `scripts/prompt_hash_guard.py`
  pins the prompt modules' text; a model id change in the same module re-pins the hash
  and the verification record names the model change beside it.

# Why

Task 051 moved two surfaces to Luna under contract decisions D2 and D10 and almost
moved a third the contract did not name.

# Citations

- [051 verification § Diff summary, "Agent triage model"](../tasks/051-improve-production-search-screen/verification.md)
- `backend/src/policy_atlas/runtime/agent_backend.py`; `backend/tests/runtime/test_planner.py` (`test_model_routing_by_moment`)
