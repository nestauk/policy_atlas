---
type: Frontend rule
title: Replacing a native form control with a styled widget forfeits its built-in accessibility — enumerate and rebuild it, or the swap is a regression
description: 040 swapped a native `<select>` for a Radix-Popover listbox for visual reasons; every review lane independently flagged the same loss — arrow-key/Home/End navigation, label-click activation, and announcement of the current value all came free with the native control and vanished with it. Before shipping such a swap, list what the native control did for free and rebuild each item (or record the gap); JSDOM tests won't catch the loss unless they assert focus and accessible names.
tags: [frontend, accessibility, radix, forms, task-040, review-lesson]
timestamp: 2026-09-08
---

# Rule

A native control is a bundle of behaviours, not a look. For `<select>` the
free bundle is at least:

| Native behaviour | What a styled replacement must rebuild |
|---|---|
| Arrow/Home/End moves the highlighted option | `onKeyDown` moving focus across `role="option"` items |
| Opening focuses the current selection | `onOpenAutoFocus` → focus the `aria-selected` option |
| Clicking the `<label>` activates the control | real `<label htmlFor={triggerId}>`, not a text span |
| AT announces label **and** current value | `aria-labelledby="{labelId} {valueId}"` on the trigger (a bare `aria-label` masks the value) |
| Type-ahead to an option | rebuild or record as a known gap |

Radix Popover supplies only Esc/outside-dismiss/focus-return — it is a
positioning primitive, not a listbox.

# Why

In 040 the swap was owner-directed for styling; the a11y loss shipped
unnoticed because all 568 unit tests stayed green (they asserted options
existed, not how focus reached them). Three independent review lanes (Codex
adversarial, `/code-review`, contract verifier) each surfaced the same
regression — the strongest convergence of the review stack — and the fix was
~30 lines once enumerated. A keyboard test (`open → focus lands on current
option → ArrowDown → Enter picks`) now pins the behaviour.

# Watch out

- The repo hand-rolls this Popover-as-listbox pattern in three places
  (`SourcesView` FilterSelect, `NewTaskView` ProjectPicker,
  `workspace/PlanDocument` pickers) and they drift; only FilterSelect has the
  keyboard model. The shared-component seam is recorded in
  `docs/deferred.md`.

# Citations

- `frontend/src/views/SourcesView.tsx` (`FilterSelect`), `frontend/src/views/SourcesView.test.tsx` (keyboard test)
- `docs/tasks/040-mobile-layout/verification.md` § Review findings (convergent finding)
