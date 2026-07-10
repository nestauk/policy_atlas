---
type: Convention
title: Structured-output prompts pin exact key vocabulary and state cross-field constraints as hard rules
description: A planner-class model invents compound dict keys ("select_extract_group") for grouped reasoning, and pairs fields the schema cannot cross-constrain (stage-2 with landscape) — the schema's extra="forbid" catches both, but the fix belongs in the prompt, and the fail-closed validation loop is the right recovery surface.
tags: [llm, prompting, structured-output, fail-closed, planner]
timestamp: 2026-07-10
---

# Rule

Two prompt disciplines for any structured-output surface whose schema is
validated fail-closed (`planner_prompt.py`, task 017 live check):

1. **Pin the exact key vocabulary.** Where a dict field has meaningful keys
   (`component_rationale`), name the allowed keys in the prompt and forbid
   combinations explicitly ("one entry per component, never a combined key
   like `select_extract_group`") — models invent compound keys to express
   grouped reasoning.
2. **State cross-field constraints as hard rules.** Constraints the schema
   cannot express (screen_stage2 fits standard/deep only, never landscape)
   must be prompt vocabulary ("ONLY available when…") — a soft "fits X"
   phrasing still gets paired wrongly.

# Why

Both failures happened live in 017's planner-only check: rationale under a
compound key, and stage-2 paired with landscape depth. `extra="forbid"` +
registry validation rejected both — never a silent run — and routing the
validation error back into the conversation recovered both on the re-turn.
The schema is the net; the prompt is the fix; the fail-closed loop is the
recovery surface.

# Watch out

Tightening the schema instead (e.g. enum-keyed dicts) is not always possible
under provider structured-output subset rules — which is exactly why the
prompt carries the vocabulary.
