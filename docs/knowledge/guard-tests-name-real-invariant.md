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
- **The guard's SELECTOR is part of its invariant** (028): the prompt-hash
  guard pins files whose *name* contains "prompt", so
  `synthesise_sections_v3`/`synthesise_key_findings_v2` — prompt constants
  living in `synthesis_backend.py` — are invisible to it; their only guard
  is version-pin tests. A guard that selects by filename convention guards
  the convention, not the surface: widen the glob or move the constants
  when a gated surface lands outside the selector.
- **A guard can also die by evaluating to nothing** (031). A test named as pinning
  "acquire's headline is the sum of its per-backend counts" asserted
  `real["acquired"] == sum(stats["acquired"] for stats in real["by_backend"].values())`
  against a walk whose payload was `acquired = 0, by_backend = {}` — i.e. `0 == sum(())`.
  It would have passed however acquire computed its headline. Sibling shape in the same
  slice: a scope-narrowing test whose fixture never put a record in the narrowed scope, so
  it passed whether or not the narrowing ran. **Ask of every guard: what value would make
  this fail?** If the fixture cannot produce one, the guard is decorative. The cheap check
  is a mutation — break the production line deliberately and confirm the test goes red.
- Related fixture trap (031): the runtime walk's stub search acquires **0 new** sources,
  because the seeded project already holds the records the stub returns. `assert
  headline > 0` off a plain walk fails; a non-zero headline has to be seeded, or the test
  has to use a backend that yields fresh records per call.
- Same family:
  [untrusted-prompt-fields-json-records](untrusted-prompt-fields-json-records.md)
  (the boundary is the mechanism, not the sanitizer's pattern),
  [assert-on-row-not-summary](assert-on-row-not-summary.md).
