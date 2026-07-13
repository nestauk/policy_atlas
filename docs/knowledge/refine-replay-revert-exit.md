---
type: Prompting
title: The refine-replay loop's revert-not-iterate exit is load-bearing
description: 021's extract_icf_v1 round 3 REGRESSED against round 2 (protocol-shaped records returned, 42 vs 30) after adding a more specific rule to a surface that round 2 had fixed; single-sample mini-model variance plus an over-specific present-tense rule means more words is not more control — the loop's bounded-rounds/revert exit is what ships the better prompt.
tags: [prompting, refine-replay, extraction, regression, prompt-economy]
timestamp: 2026-07-13
---

# Rule

When a refine-replay round regresses against the previous round, **revert and
ship the earlier text** — do not iterate further on the failing addition. The
018-pattern loop's bounds (≤3 rounds per surface, revert on regression) are
not budget ceremony: they are the mechanism that stops a plausible-looking
tightening from shipping. Treat a single replay per round as a noisy
measurement: a rule added to fix the last residual can re-open the previous
defect (021 round 3 re-admitted protocol-specification `delivery_process`
records that round 2 had eliminated, 42 findings vs 30).

# Why

Two forces make round-N+1 regressions likely: single-sample variance on
mini-model extraction (the same document legitimately yields different record
counts across calls), and rule interaction — an over-specific rule gives the
model a new reading that routes around an earlier constraint
([prompt-honesty-rules-route-around-new-capability](prompt-honesty-rules-route-around-new-capability.md)
is the same family). 021 shipped round 2's text; the residual
(Methods-heavy protocol leakage, ~a dozen records) is bounded by flag-not-drop
and owned by the eval slice's ground truth, which is the right place to
measure whether more prompt text would ever pay.

# Watch out

- "One more clause will fix it" after a regression is the loop's failure mode;
  the exit criterion exists precisely because the urge is strongest there.
- Log the regression and the revert in verification.md — the reverted text is
  evidence about the surface's sensitivity, not wasted work.
