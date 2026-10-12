---
type: Convention
title: On a mini model, a worked example moves behaviour where a rule does not, and a loop past two targeted rounds measures noise
description: In the task 046 record-prompt loops the only round that moved the hospital-as-place family was the one that added a second few-shot example; a "never X" rule about an edge case was read as "leave X out" (not-stated faults rose and the round was reverted); each added rule moved faults between families; a screen model quoted the criterion's own words back ("not in Greater Manchester") whatever the rule beside it said; asking for the reason before the label, and closing both exits of a two-way rule, bound better than more words.
tags: [prompting, mini-model, refine-loop, few-shot, extraction, screening, task-046]
timestamp: 2026-10-12
---

# Rule

When tuning a prompt that runs on the mini model:

1. **Prefer a worked example to a rule.** The record prompt's hospital-name family fell only
   on the round that added a before-and-after example whose record carries the town
   (caregiving faults 50 → 32); the rule with examples and the schema description each moved
   other families and left this one (046 amendment 4, loop 27).
2. **Write positive rules; a negative rule about an edge case is read as an omission.** "Never
   a place cited only for another study" made the model drop documents' own place names
   (not-stated faults 21 → 38 and 34 → 56); the round was reverted (amendment 3, loop 16R).
3. **Ask for the reason before the label or verdict**, and close every exit of a rule with two
   ways out: with only "ungroupable" closed, class-level reviews moved to "not an option"
   (base build, assignment and constrain prompts).
4. **A phrase inside the input is a criterion whatever the prose says.** The screen's
   mini reps wrote "not in Greater Manchester" as the reason while the rule beside the
   text said the place is not a criterion; naming the place as "the user's place" cut the
   faults from 10 to 1, not to 0, so the place strip stays in code (amendment 3, loop 18P).
5. **Stop after two targeted rounds.** Beyond them the folds and the records varied more
   between runs of one text than between rounds of the text; the next lever is the model
   tier, which is a contract decision, not a wording one (loops 16R, 20L, 27, 28).

# Why

Five loops of task 046 ran four or five rounds each and ended without their stop measure;
the owner accepted the residuals (2026-10-12) once the record showed the pattern above.
See [the refine loop's revert-not-iterate exit](refine-replay-revert-exit.md) and
[limits live in the schema and code](mini-model-limits-live-in-the-schema-and-code.md).
