---
type: Convention
title: Copy that tells the user how to recover must be backed by a route that performs that recovery, and tested end to end
description: Task 055's shortlist view said "Press Suggest more to re-propose" when the stored proposal's appetite differed from the plan's, but the Suggest more route kept the old picks and only filled gaps, and the button was disabled when every option held a place — so the stale state was unrecoverable. Two unit tests (one for the sentence, one for the disabled button) each passed. The remedy a stale flag names is a behaviour to test from the flag to the write, not a sentence to render.
tags: [frontend, copy, staleness, shortlist, testing, task-055, review-findings]
timestamp: 2026-10-27
---

# Rule

When a derived flag (`stale`, `plan_inputs_changed`, "could not propose") is shown with a
remedy ("Press X to re-propose", "Rebuild the longlist"), the route behind X must do what
the sentence says **in that state**, and one test must drive the flag → the action → the
stored result. Testing the sentence and the button separately proves nothing about the path.

# Why

The 055 plan-gate amendment PG1 replaced a server flag with a derived `shortlist.stale` and
the words "Press Suggest more to re-propose". The build rendered the words and kept Suggest
more's fill-the-gaps semantics; with five picks under the old appetite the button was
disabled. The Codex adversarial lane found it; the fix makes the opener treat a stale
appetite as a re-proposal (release the picks, fill to five around the user's places) and the
view enable the button when stale. See [plan-field additions carry from previous](plan-field-additions-carry-from-previous.md)
for the other review-found gap on the same field.

# Watch out

- A degraded one-component walk is a failure of the thing it does: the run card's generic
  "DONE" wording for `degraded` read "The shortlist is proposed" when nothing was. Status
  words need the walk kind.
- A stale-view test that asserts a disabled button is a test that pins the defect.
