---
type: Frontend rule
title: A frontend list of backend label values is tested against the labels the API sends
description: A ranking or ordering list in the frontend that enumerates backend label values drifts silently when the backend vocabulary changes (lowercase tier keys outlived the "Very strong" to "Weak" labels), and adding one new value to a stale list inverts the order; such lists are written from the backend's vocabulary and their test uses the real labels.
tags: [frontend, vocabulary, appraisal, ranking, "056"]
timestamp: 2026-11-02
---

# Rule

When the frontend orders or ranks by a backend label (appraisal strength, evidence type,
status), the list it compares against is the backend's current vocabulary
(`appraise.SCORE_LABELS` for appraisal), written once as a comment-linked copy and tested
with the real label strings, not with placeholder keys. A value outside the list may sort
last without throwing, but every value the API sends today must be in it; a test with a
made-up label proves nothing about the real ones.

# Why

`artefactPresentation.ts` ranked tied sources with `["high", "moderate", "low", "very_low"]`
while the API had sent "Very strong" … "Weak" for several tasks, so every real label ranked
as unknown and the tie-break was by title. Task 056 added `"unrated"` to the stale list,
which made an Unrated source sort ahead of a Very strong one. The Codex adversarial lane found
it at review (unique to that lane); the fix was the list and a test with the real labels.
