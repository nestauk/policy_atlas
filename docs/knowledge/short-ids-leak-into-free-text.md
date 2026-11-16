---
type: Convention
title: A listwise model call that gets short ids will use them in its free-text output unless told the reader never sees them
description: Task 055's shortlist call labels candidates o1…oN, kept places k1…, set-asides s1… so the model never sees or returns a real id; on the tuning set one note then read "o12 and o17 remain …". One prompt rule fixed it ("Name options by their names, never by their ids"); the staged check's 24 notes carried no id after it.
tags: [prompting, listwise, shortlist, ids, task-055]
timestamp: 2026-10-27
---

# Rule

When a prompt labels items with short ids for the model to pick from, and the same call also
writes free text the user reads (a note, a summary), the prompt must say that the ids are
for the answer's structured fields only and that the reader never sees them: "Name options by
their names, never by their ids." Check the free text for the id pattern in the readback
script (`\bo\d+\b` in 055's `run_shortlist_check.py`).

# Why

Short ids are the right design — the model never sees or can return a real UUID, and a
document title cannot forge an id line — but the model treats them as the names it was given.
Round 1 of 055's shortlist loop produced a note naming two changed places as "o12 and o17";
round 2 added the rule and the 24 proposals of the staged check had no id in any note.

# Watch out

- The same leak can appear in reasons, not only notes; the check covers every free-text
  field the call writes.
- See [a limit lives in the schema or in code](mini-model-limits-live-in-the-schema-and-code.md)
  for which prompt rules bind on small models; this one bound on the judgment model in one
  round.
