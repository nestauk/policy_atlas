---
type: Review lens
title: Tested-in-isolation is not wired — integration claims need a runtime call-site check
description: A reader/aggregator can carry a full green test suite and still be dead code — its tests exercise the function, not the runner reaching it. Task 024's trigger floor shipped 35 green trigger tests while two of its classes had zero runtime call sites and a third was blind to its input. Review rule — for every "X is wired" claim, grep the call sites and check what the caller actually passes.
tags: [review, verification, integration, dead-code, trigger-floor, task-024]
timestamp: 2026-07-17
---

# The lens

Isolation suites prove behaviour; they prove nothing about **reachability**.
024 shipped "floor triggers over seeded rows, all decision-8 classes
(35 tests)" — true of the readers, false of the system: `floor_triggers` had
exactly one runtime call site (P2), so the screen-quality and
extraction-spike classes never ran, and the one wired class received
`successful_runs` where its docstring asked for *attempted* run ids — blind
to precisely the failures it existed to surface. A shipped test even
enshrined a second inert path (the watch's `promoted` verdict) by asserting
the event existed and nothing about its effect.

Review moves that catch this class cheaply:
- For each "wired" claim, **grep the symbol's call sites in `src/`** — a
  function whose only callers are its own tests is a finding, whatever the
  suite says.
- At each call site, **diff the arguments against the docstring/contract**
  (`successful_runs` vs "attempted run ids" was the whole bug).
- Distrust tests that assert an *event/record exists* without asserting its
  *effect* — "emitted and discarded" passes those.
- **For every option a steering floor offers, one test must ANSWER a pause
  with it through the real apply path** (028 M1): the finding-groups
  regroup options shipped dead — the coverage matrix asserted option *ids*
  and that deltas *compile in the grammar*, but no test answered an FG
  pause end-to-end, so nobody noticed the pause's re-run surface was wired
  for P3 only and both apply paths refused the delta. Offered + compiles ≠
  appliable.
