---
type: Convention
title: A new plan field must be carried from the previous version in the version builder, or the next approved version silently resets it
description: Task 055 added `risk_appetite` to the scoping plan and applied it from the Task Agent's wire draft only; `build_scoping_plan` carries `your_options` and `removed_defaults` from `previous` but knew nothing of the new field, so any later version the conversation produced (a depth change, a new Where) would have reset the appetite to its default without notice. Every optional wire field that lands on the plan needs the "else: previous" branch and a direct test of the builder with the field absent.
tags: [scoping-plan, task-agent, plan-versions, wire-models, task-055, review-findings]
timestamp: 2026-10-27
---

# Rule

When a field is added to the scoping plan and the Task Agent may omit it from a later wire
draft ("never pre-filled" fields especially), the plan builder must take the value from the
previous approved version when the wire has none. Test the builder directly with the field
absent and a previous version that holds a non-default value: the stub Task Agent recomputes
such fields from every user turn, so a route test through the stub passes even when the
builder forgets.

# Why

The 055 review (`/code-review`) found `_build_plan` in `runtime/task_agent_scoping.py`
applied `risk_appetite` only when the wire carried one of the three values. Each later version
is built against `previous`, which carries `your_options` and `removed_defaults` forward but
not the new field, so a user who chose "Ambitious" and then changed the depth would have had
a `mostly_tried` plan and a wrong shortlist mix. The route tests did not show it because the
stub reads the appetite from the whole transcript.

# Watch out

- The seed for a successor conversation is a different path (`_seed_draft`); fixing it does
  not fix in-conversation versions.
- The same shape applies to `depth`: the wire field is optional and nothing carries it from
  `previous`; today the model re-emits it every turn.
