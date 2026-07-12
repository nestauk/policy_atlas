---
type: Prompting
title: An earlier prompt honesty rule can silently defeat a new capability line
description: A capability line teaching a new filter vocabulary was routed around by an EARLIER honesty rule (study-geography ≠ source-geography reasoning) until the prompt said which reading selects which surface; only replay rounds catch this class — unit tests can't.
tags: [prompting, planner, capability-line, replay, country-filters]
timestamp: 2026-07-12
---

# Rule

When a prompt gains a capability line (a new surface the model may use), audit the
**existing** rules for one that legitimately routes asks *away* from it. The model can
be principled-but-inconsistent: in 019's round 1, the planner correctly reasoned that
an author-affiliation filter drops foreign-authored studies ABOUT a region — an honesty
rule — and so fired the new `country_group` filter on only 1/5 group phrasings. The fix
is not to weaken the honesty rule but to state the routing explicitly: which *reading*
of the ask selects which surface (study/programme-setting phrasings → screening
criterion; source-origin phrasings → `country_group`).

Only refine-replay rounds catch this class: the capability compiles, the schema
validates, unit tests pass — the defeat is behavioural, visible only across phrasings.

# Why

Round 1 of the 019 planner replay exposed the routing conflict; the refined line
codified the setting-vs-origin split and round 2 fired correctly across Tier-1 labels,
Tier-2 explicit lists, and the honest-decline case. The D1 live run then showed the
routing working unprompted ("UK homes" handled as study setting during screening, no
geography filter). Same lesson family as 018's judge-envelope work: prompt rules
interact as a system; a new rule's failure mode is usually an old rule's success mode.

# Watch out

- Budget a replay round specifically for rule-interaction, not just for the new
  capability's happy path — include phrasings the OLD rule should win on.
- If the model applies a rule "inconsistently", first ask whether two rules overlap on
  those inputs; inconsistency is often unstated precedence.

# Citations

- [019 verification.md § Planner replay](../tasks/019-folding-pass/verification.md)
  (two rounds, 15 probes; round-1 routing conflict, round-2 clean)
- `src/policy_atlas/planner_prompt.py` (planner_v3 setting-vs-origin routing text)
- [prompting.md](../specs/system/prompting.md) (refine-replay loop method)
