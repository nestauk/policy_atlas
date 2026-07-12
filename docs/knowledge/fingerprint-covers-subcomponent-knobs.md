---
type: Invariant
title: The extraction fingerprint covers sub-backend knobs too — model and effort, not just prompt version
description: "Every output-affecting knob enters the memo fingerprint" includes attached sub-backends' own model and reasoning-effort settings — the vetter filters which findings persist, so a vetter model/effort change with an unchanged fingerprint would reuse stale records. Latent since 018 C5, caught by the 020 review stack; per-knob sensitivity is test-pinned.
tags: [fingerprint, memoisation, extraction, vetter, provenance]
timestamp: 2026-07-12
---

# Rule

The extraction memo fingerprint must hash **every** knob that can change what
gets persisted — and when a sub-backend rides the run (the finding vetter),
that includes the sub-backend's *own* model, reasoning effort, prompt version
and output cap, not just a flag that it was active. The test discipline is
per-knob: `test_fingerprint_changes_on_any_single_component` monkeypatches
each knob individually and asserts the hash moves;
`test_fingerprint_change_extracts_fresh_alongside` pins the consequence (memo
miss → fresh records alongside, old rows byte-untouched).

# Why

018 C5 added the vetter as a fingerprint component carrying only
`{prompt, max_output_tokens}`. A later `FINDING_VETTER_MODEL` or
`FINDING_VETTER_REASONING_EFFORT` change would have changed which findings
survive vetting while the memo silently served records filtered under the old
settings — exactly the stale-reuse class the fingerprint exists to prevent.
The gap rode two slices unnoticed because the component *looked* covered (it
had a version in it); the 020 Codex adversarial lane caught it by asking the
knob-enumeration question rather than trusting the component's presence.

# Watch out

- The tell is a fingerprint sub-dict that names fewer knobs than the
  sub-backend's module constants — diff the component's keys against the
  `*_MODEL` / `*_REASONING_EFFORT` / `*_MAX_OUTPUT_TOKENS` constants at the
  call site whenever either side changes.
- Adding a knob to the fingerprint invalidates all existing memo entries by
  design (one-time re-extract); do it in a slice that already bumps versions.
- Same family: [judge-envelope-defines-verdicts](judge-envelope-defines-verdicts.md)
  (settings changes redefine outputs; comparisons across them are dishonest).
