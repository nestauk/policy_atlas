---
type: Frontend rule
title: A strict "desktop unchanged" invariant is cheap when every mobile change is an additive max-md: class — and provable from the compiled cascade
description: 040 restyled the whole app below 768px while holding ≥768px pixel-identical by allowing only additive `max-md:`/`md:hidden` classes (or mobile-only elements). The invariant is then checkable mechanically — every `max-md:` rule postdates its base utility in the compiled CSS — instead of by eyeballing screenshots. The failure mode is the one *unconditional* class that rides along (040's `gap-x-5`): grep the diff for class edits without a breakpoint prefix.
tags: [frontend, tailwind, responsive, mobile, task-040, review-lesson]
timestamp: 2026-09-08
---

# Rule

To change mobile rendering without risking desktop, permit exactly two shapes
of change:

1. **Additive variant classes** on existing elements — `max-md:*` to restyle
   below the breakpoint, `md:hidden` / `block md:hidden` to swap elements per
   width. Never edit or remove a base utility.
2. **Mobile-only elements** (`md:hidden` subtree) rendered next to the desktop
   one — both mounted, CSS picks one per viewport (no JS viewport logic).

Verification then splits cleanly:

- **Mechanical:** in the compiled CSS (`frontend/dist/assets/index-*.css`),
  every `max-md:` rule must appear *after* the base utility it overrides —
  tailwindcss v4 orders variants after bases, so this holds for every pair,
  including stacked variants like `max-md:starting:translate-y-full` (which is
  how 040's Radix Dialog side-sheet became a bottom sheet with classes alone —
  no `side="bottom"` variant, both consumers inherited).
- **Visual:** screenshots only need to catch the *deliberate* all-width
  exceptions, not to prove the whole invariant.

# Watch out

- The invariant dies silently to one class **without a breakpoint prefix**.
  040 shipped `gap-x-5` (not `max-md:gap-x-5`) on the shared NavBar: invisible
  at 390px checks, but it moved the ≥768px task-bar truncation point. The
  review greps the diff for class-attribute edits lacking `max-md:`/`md:`
  before trusting the invariant.
- JSDOM applies no responsive CSS, so unit tests can only assert class tokens
  and DOM duplication — the compiled-cascade check plus a live viewport check
  are the compensating controls, and the tests should say so.
- Mobile-only twins of a stateful control fork its logic unless the data is
  computed once and rendered twice (040: one lifecycle tab list feeds both the
  task NavBar and the bottom bar, keeping the pending-check-in marker single).

# Citations

- `docs/tasks/040-mobile-layout/` (contract § Constraints; verification § Review findings — the `gap-x-5` finding F3)
- `frontend/src/ui/radix/Sheet.tsx` (bottom-sheet conversion), `frontend/src/views/AppShell.tsx` (one tab list, two placements)
