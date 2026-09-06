---
type: Invariant
title: Compile-target parity is checked on the composed whole, with the real composer
description: Per-field caps are not parity — a plan whose fields all validate can still compose past a downstream cap and silently truncate (screen criteria vanished while provenance claimed they applied); and round-trip checks against a canonicalising composer must use containment, not byte equality.
tags: [plan, compile, fail-closed, parity, steering, agent]
timestamp: 2026-07-10
---

# Rule

Where a plan compiles into a downstream surface with its own bounds or
canonical shape, plan validation must exercise **the real composer** against
**the real bound** — not mirror per-field constants:

- `TaskPlan` composes the actual screen intent
  (`screen._compose_screen_intent(question, criteria)`) and rejects when it
  exceeds `SCREEN_INTENT_MAX` — per-criterion caps alone let a long question
  silently truncate every criterion at prompt assembly while the plan row
  claimed they governed screening (017 review stack; Codex + security lanes
  convergent, proven empirically).
- Round-trip checks against a composer that canonicalises (injects sibling
  keys like acquire's `depth`, screen_full's `stage` (step renamed from screen_stage2 in 019)) use **containment**
  (`steering._delta_contains`), not byte equality — raw `!=` rejected every
  legitimate partial-key adjustment while inexpressible requests still fail
  closed.
- Names that must match a runtime consumer are pinned to a **registry**
  (`STEER_POINTS`): the pin immediately exposed fixtures declaring
  `"deepening-selection"` against the runtime's `"deepening_selection"` — a
  default that could never match, silently indistinguishable from the
  fallback.

# Why

All three are the same failure class: the plan model and its compile target
each individually valid, with the mismatch living only in the composition —
where nothing errors. 017 paid for the per-field version live (a >200-char
criterion failed mid-run) and the review stack found the composed-whole,
containment, and registry variants within the same slice. Extends
[plan→config compile fails closed](plan-compile-fails-closed.md): fail-closed
at construction is only as strong as what construction actually checks.

# Watch out

The parity check must import the composer/constant from the compile target —
a mirrored constant is drift waiting to happen (the review found
`runner.SPINE_COMPONENTS` as an independent literal of `SPINE` for exactly
this reason).
