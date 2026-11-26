---
type: Domain concept
title: A link's verdict is a weighted score over its judged documents; a pathway shows its lowest link
description: Each theory-of-change link gets one verdict from the judged documents (quality times relevance, weighted support). A pathway shows the lowest verdict of its links. When a canvas looks empty, read the judge's relevance scores before the search.
tags: [theory-of-change, judge, verdict, canvas]
generated:
  by: claude-opus/5.5
  at: 2026-11-20
sources:
  - id: grade
    resource: backend/src/policy_atlas/theory_of_change/check/grade.py
    title: link_verdict and lowest
  - id: adr-0042
    resource: docs/adr/0042-theory-of-change-task-kind.md
    title: ADR 0042, theory of change task kind
---

# Rule

- `check/grade.py` is the only place a verdict is decided. `link_verdict` weighs each judged
  document by quality times relevance, then reads the weighted support and the share that
  refutes. Below a minimum total weight the link is "Not enough evidence".
- A pathway's verdict in the report is the lowest verdict of its links (`lowest`).
- Diagnose an empty-looking canvas in this order: the judge's relevance scores (does a study
  done in the United Kingdom count for England?), then the search (did the policy source
  answer? see [missing-source-key-fails-open](missing-source-key-fails-open.md)), then the
  pool size.
- A change to the judge's rule is a prompt edit: re-pin the prompt hash and replay on fixed
  topics.

# Why

Low relevance makes each document weigh little, so many links fall below the minimum weight
and the canvas shows "Not enough evidence" everywhere. The cause is then the judge, not the
search.
