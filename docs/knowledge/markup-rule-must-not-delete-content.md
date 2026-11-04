---
type: Invariant
title: The markup-strip rule removes marks, never content; every content loss found so far is a test case and the byte-identity digest is the detector
description: A regex rule that strips markdown and HTML from parsed text has deleted content five times before anyone looked: significance stars after digits (0.50**), escaped markers (\*literal\*), tag-shaped maths (x<y and y>z), one-letter tag names taking free text as attributes (a<b and c>d), and identifiers with underscores (Situation_report_-_the). Each is now an assertion; the fixture corpus's byte-identity digest moves on any new loss, so a moved digest is read before it is re-pinned.
tags: [parsing, markup, regex, fixtures, "057"]
timestamp: 2026-11-03
---

# Rule

- Tag names are a fixed set; a one-letter name (`a`, `b`, `i`, `p`, `q`, `s`, `u`) is a tag
  only before `>` or with an `=` attribute. Known remaining loss: `<b disabled>`.
- Emphasis needs a non-alphanumeric before its opening marker and no backslash before
  either marker; stray `**` runs stay after a digit, another star or a backslash.
- Unescaping (`\*` → `*`) runs last, after the emphasis passes that must not see the escape
  as a marker.
- When the byte-identity digest moves, diff the one differing chunk and decide whether the
  change is a loss before re-pinning; two of the five losses above were found that way.
- The quote verifier shares the same patterns through `markup_deletions`, so a rule change
  moves both sides at once and the offset map stays correct.

# Why

Task 057's parse profile v2 is the markup rule. The owner's post-build rulings closed two
losses, the gate found the third in a statistics table, and the review's Codex and
contract-verifier lanes found the fourth and fifth in the test file's own "quirk" assertion
and a deferred note.
