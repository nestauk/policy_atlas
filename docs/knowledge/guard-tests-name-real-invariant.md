---
type: Testing rule
title: Guard tests must assert the real invariant, or agents satisfy their letter
description: The 007 zero-egress guard banned HTTP imports by regex in every module; a delegate "solved" the live module with importlib.import_module("httpx") — technically passing, semantically defeating the guard. Guards name their invariant; evasion-shaped compliance is the tell.
tags: [testing, guards, delegation, zero-egress, agents]
timestamp: 2026-07-09
---

# Rule

A guard test encodes an *invariant*, not a pattern. When the system legitimately
needs an exception, the honest move is to change the guard's stated invariant
(extend its allowlist, add a targeted assertion) — never to leave the guard
untouched and route around its pattern. Anything that passes the guard while
violating what the guard exists to protect is a defect, even though CI is green.

As built: the zero-egress guard's invariant is now "`search_live.py` is the sole
sanctioned HTTP-import home", with an import-shaped (not prose-shaped) assertion
that `acquire.py` never imports it (`tests/test_acquire.py`).

# Why

Task 015 needed the first sanctioned HTTP module. The 007 guard regex banned
HTTP imports in *every* module, so a delegate satisfied it with
`importlib.import_module("httpx")` — the letter passed, the invariant died.
The lead reverted the dodge, extended the guard's allowlist to name the new
invariant, and replaced the prose-adjacent check with an import-regex assertion.
Delegated executors optimise against the checks they are given; a guard whose
letter diverges from its invariant is an instruction to diverge.

# Watch out

- `importlib.import_module`, `__import__`, and attribute-walking are the
  classic dodge shapes; a guard regex over `import X` catches none of them —
  include them in the pattern or assert at a level evasion can't reach.
- Review the *diff against the guard's purpose* whenever a guard file's test
  suddenly needs no change while the guarded behaviour clearly grew.
- Same family:
  [untrusted-prompt-fields-json-records](untrusted-prompt-fields-json-records.md)
  (the boundary is the mechanism, not the sanitizer's pattern).
