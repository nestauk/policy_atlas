---
type: Domain concept
title: A connection is coloured by the lower of its two grades, so a strict "holds here" judge greys the whole canvas
description: Each link answers worked elsewhere and holds here; the canvas shows the lower grade. When a canvas looks empty, read the holds-here rate first: in task 054's first live run 12 of 20 links had no holds-here evidence because the judge did not count a UK study as England evidence, and the judge prompt, not the search, was the fix.
tags: [theory-of-change, judge, grades, canvas, task-054]
timestamp: 2026-11-05
---

# Rule

- The link's colour is `min(worked_elsewhere, holds_here)` (`evidence/grade.py`, the only
  place a grade is decided).
- Diagnose an empty-looking canvas in this order: the holds-here rate per link, then the
  search (did the policy source answer: an Overton 401 falls back to academic sources without
  failing, see [missing-source-key-fails-open](missing-source-key-fails-open.md)), then the
  pool size.
- A judge rule change is a prompt edit: re-pin the hash and replay on the fixed topics.

# Why

Task 054's first live run (2026-10-26): a 2012 UK study was `challenges` for worked elsewhere
and `not_about` for holds here, and 12 of 20 links had no holds-here evidence. The judge's
holds-here definition was the target (`toc_judge_v2`: a study done in the stated place, or in
the UK for England, answers holds here as it answers worked elsewhere).

# Citations

- `backend/src/policy_atlas/theory_of_change/evidence/grade.py`;
  `evidence/judge_prompt.py`
- [054 verification § First try, findings 2](../tasks/054-toc-integration/verification.md)
  and § Iteration log, loop 1
