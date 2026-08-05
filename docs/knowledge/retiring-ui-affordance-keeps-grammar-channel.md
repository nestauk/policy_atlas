---
type: Design rule
title: Retiring a UI affordance is not retiring its grammar channel
description: A contract line that retires a BUTTON retires a rendering, not the submission channel behind it — 028's "retype-everything" P4 button was retired, but its edit_sections requires-input option IS how an edited section list submits; a literal reading dropped both and left the frontend with no way to submit an edit. Separate the affordance (how it renders) from the channel (how the answer travels) before deleting either.
tags: [steering, contracts, ui, grammar, task-028, review-lesson]
timestamp: 2026-08-05
---

# Rule

A steering option has two separable identities: the **affordance** (how the
card renders it — a button, inline row-editing, a chip) and the **channel**
(the requires-input option + delta grammar through which the answer
travels). A contract that retires the affordance says nothing about the
channel — and if the channel is the only way a class of answer submits,
deleting it silently removes the capability.

When a contract retires a UI element, ask: *what still needs to travel
through the grammar this element fronted?* If anything does, the option
stays in the floor and the new UI renders it differently.

# Why

028's contract retired P4's "retype everything" button. Phase D read that
literally and dropped the `edit_sections` requires-input option too — but
that option is the submission channel for the new inline row-editing; with
it gone the frontend had no way to submit an edited section list at all.
The lead-adjudicated restoration keeps the grammar channel (`{title,
focus[, group_ids]}` rows, same confirm ladder) and renders it as per-row
✎ editing, never a button.

# Watch out

- The inverse also holds: adding a new editing UI does not need a new
  channel if a grammar-equivalent option already exists — reuse it.
- Same family:
  [tested-in-isolation-is-not-wired](tested-in-isolation-is-not-wired.md)
  (an offered option must also be appliable — the channel must be WIRED,
  not just present).

# Citations

- `backend/src/policy_atlas/runtime/steering.py` (`_p4_options`,
  `edit_sections`)
- 028 verification.md § Flagged deviations (3)
