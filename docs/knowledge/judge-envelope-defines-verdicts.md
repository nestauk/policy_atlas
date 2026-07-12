---
type: Invariant
title: Judge verdicts are a function of the envelope — re-baseline on change, inspect flags before recalibrating
description: Adding anchor chunk text to the judge envelope moved tier_3 mass to tier_2 and net-raised unsupported; tier distributions are not comparable across envelope versions. High first-contact flag volume from an asymmetric report-when-in-doubt rule is usually the writer, not the judge — hand-inspect before recalibrating.
tags: [grounding-judge, envelopes, verdicts, calibration, evaluation]
timestamp: 2026-07-11
---

# Rule

A grounding-judge verdict tier is a function of **what the envelope lets the judge
see**, not just of the claim. 018's envelope v2 A/B (recorded v1 verdicts vs live v2
re-judge on the same claims): giving the judge each finding's anchor quote *in its
chunk context* moved tier_3 mass to tier_2 (single-document support recognised) and
net-raised unsupported (over-synthesis caught) — 14/68 and 15/38 flips on the two
pinned projects. Consequences:

1. **Tier distributions are NOT comparable across envelope versions.** Any envelope
   change re-baselines every downstream consumer of verdict counts (quality bars,
   eval metrics, dashboards).
2. **Envelope changes get verification-grade evidence, not output-taste review**:
   verdict-distribution diff on a replayed claim set, every flip hand-inspected
   (watching for intent-induced leniency when the envelope gains the question), a
   stratified sample of UNchanged verdicts (flips alone miss unchanged-but-wrong),
   and an adversarial fixture when the envelope feeds the judge more untrusted text
   (the 013 chunk-self-certification case).
3. **Inspect flags before recalibrating the judge.** An asymmetric
   report-when-in-doubt rule produces high flag volume on first contact (49 unspanned
   flags / 83 claims at the 018 B smoke) — hand-sampling showed the judge was RIGHT;
   the writer under-anchored. Render such flags quietly on user surfaces and fix the
   generator, not the detector.

# Why

Without rule 1, a model/envelope refresh silently reads as a quality regression or
improvement. Without rule 2, an envelope change that makes the judge lenient toward
question-relevant claims ships unnoticed (relevance is not support). Without rule 3,
the calibration pass tunes away a working detector.

# Watch out

- The same claim set + same judge + different envelope = different verdicts is
  *expected*, not a flake.
- The self-certification fixture is mandatory whenever an envelope change feeds the
  judge MORE chunk text.

# Citations

- [018 verification.md § B3](../tasks/018-dress-rehearsal/verification.md)
  (judge-envelope A/B, self-cert fixture PASS; § B4 unspanned-flag calibration)
- `build_envelope`, `grounding_judge_v2` in `src/policy_atlas/grounding_judge.py`
