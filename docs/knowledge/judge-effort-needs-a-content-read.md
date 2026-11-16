---
type: Live behaviour
title: A judge-effort decision needs a content read of the verdicts; the counts invert between offline and live
description: The grounding judge at low reasoning effort marked more claims unsupported than at medium on live runs (10.9% against 5.1%), the opposite of the offline experiment's lean; the verdicts read show the low judge flagging the writer's own hedges ("does not establish a causal effect", "remains unclear") as unsupported claims, so the repair pass removes caution rather than fixing citations. Decide effort from the verdicts' content, never from the unsupported count.
tags: [synthesis, judge, reasoning-effort, evaluation, "057"]
timestamp: 2026-11-03
---

# Rule

- Pull the judge's first-pass verdicts from the traces (the database keeps only the
  post-repair verdicts) and read a sample of the unsupported ones against their claims.
- Classify each: a mis-citation (the chunk does not say it), an extrapolation (the writer
  added a reach the chunk does not cover), or a hedge (the writer's epistemic caution with no
  citation to anchor). Only the first two are the judge's job; a judge that flags hedges
  makes the report less cautious through repair.
- An offline experiment's lean (E3: low marked fewer unsupported) can invert live; the
  count alone cannot tell leniency from strictness.

# Why

Task 057 moved the grounding judge to `low` for the wall time (half the per-call time). The
build recorded the counts and left the decision to the owner's content read; the review's
trace lane read five of the nine first-pass unsupported verdicts on one run and found four
hedges. The revisit with a labelled set is a deferred seam for the synthesis refinement task.
