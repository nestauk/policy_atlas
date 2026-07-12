---
type: Prompting
title: Replay-diff a guidance line to learn whether it is prophylactic or corrective — and record which
description: A pre/post replay of a prompt guidance line can show 0 verdict flips — the old prompt already behaved; the line pins behaviour against an identified text risk rather than fixing an observed failure. Recording "prophylactic, not corrective" honestly beats claiming the line fixed anything (task 020 vetter v3).
tags: [prompting, replay, evidence, honesty, vetter]
timestamp: 2026-07-12
---

# Rule

When a review identifies a *text* risk in a prompt (a rule that could
plausibly misfire on a class of inputs), the fix line's replay evidence must
be read for what it shows: if the pre-change prompt already handled the probe
set (0 flips), the line is **prophylactic** — it pins behaviour against the
identified gap — and the record must say so. Claiming a fix "corrected" a
behaviour nobody observed inflates the evidence and mis-trains future
adjudication about what adversarial text findings mean.

# Why

Task 020's adversarial review flagged that the vetter's aspiration rule
("rather than something that happened") textually catches exactly the
modelled findings v6 deliberately extracts. The v3 guidance line was added —
and the pre/post replay on 14 modelled findings showed 0 flagged either side,
0 flips: v2's verdict reasons already called a projected decrease "a
substantive result". The adversarial finding was real (about text risk), the
line is right (it pins the behaviour), and the honest record is
"prophylactic, not corrective" — all three statements coexist.

# Watch out

- 0 flips on a small probe set is non-regression evidence, not proof the risk
  was unreal — the protective value stays untested until a document the old
  prompt *would* have mis-flagged appears.
- Same family: [judge-envelope-defines-verdicts](judge-envelope-defines-verdicts.md)
  (the verification-grade A/B protocol this replay method belongs to);
  [prompt-honesty-rules-route-around-new-capability](prompt-honesty-rules-route-around-new-capability.md)
  (only replay catches how prompt rules actually interact).
