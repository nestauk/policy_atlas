---
type: Convention
title: Wire models in prompt modules are model-facing schema — a schema-only edit is an LLM-visible change
description: PlanDraftWire is the planner's response_format schema, so adding a field changes what the model sees every turn even with zero prompt text; an undescribed field invites junk emissions that crash downstream Literal-pinned layers. Pin or coerce at the wire model, and expect the prompt-hash bump.
tags: [prompting, structured-output, wire-models, planner, fail-closed]
timestamp: 2026-09-04
---

# Rule

A pydantic model that is passed as `response_format` (e.g. `PlanDraftWire`
inside `PlannerTurnWire`, `runtime/planner.py`) is part of the model-facing
contract. Two consequences when such a model gains a field:

1. **"No prompt text change" does not mean "no LLM-visible change."** The
   model sees the new key in its output schema every turn. If the prompt
   never describes the field, the model may still fill it — with plausible
   junk ("APO", "Australian Policy Online") the moment a user's message
   gestures at it.
2. **The field needs its validity pinned or coerced at the wire model
   itself.** Downstream layers pin `Literal[...]` and re-validate strictly;
   a lenient `str | None` wire field lets junk through to a projection
   (`_draft_from_wire`) that raises *outside* the planner-call failure
   handler — a 500 and a stuck pending transcript turn. As built for 038:
   a `field_validator` coerces any non-`"apo"` `publisher_source` to `None`,
   because "the chat does nothing" was the contracted behaviour.

Also budget for the mechanical consequence: wire models live in `*prompt*.py`
modules, so a schema-only line still trips the prompt-hash guard — name the
`prompt_hashes.json` bump in the plan up front.

# Why

038's build added `publisher_source: str | None` to `PlanDraftWire` and the
contract declared "Model route: n/a — no LLM-bearing step changes". Three
review lanes independently converged on the gap: the field sat undescribed in
the planner's structured-output schema, and a planner emission of `"APO"`
(wrong case) validated at the wire, survived the caught `build_plan` failure
(`ready=False`), then crashed uncaught at the draft projection
(`api/routers/planning.py`), leaving the phase-one transcript row pending
until TTL expiry.

# Watch out

- The coercion belongs on the *wire* model, not the fold lists — the wire is
  the single entry point for LLM output (both fold lists and the API
  projection consume it).
- Coerce-to-None vs `Literal` on the wire is a product decision: `Literal`
  hard-fails the planner turn (handled, but user-visible); coercion degrades
  to "nothing happened". Match the contract's stated behaviour.
- `seed_draft_from_executed_plan` round-trips executed plans into wire
  drafts — a coercion validator must keep the legitimate value.
