---
type: Convention
title: Removing a persisted-shape tolerance must sweep every reader of the shape
description: When a fallback for an old persisted shape is removed (021 amendment — old flat roll-up), the sweep is defined by readers of the shape, not by the module named in the decision; a twin fallback in a parallel module (synthesise's _extraction_profile_ids beside synthesis_tools' _load_extraction_docs) survived the amendment and turned "raise loudly" into "silently degrade" on one of two paths.
tags: [persisted-shapes, fail-closed, migration, review-stack, extraction-rollup]
timestamp: 2026-07-13
---

# Rule

A decision to drop tolerance for an old persisted shape ("greenfield — old rows
need not stay readable") is only implemented when **every reader of that shape
fails closed**. Enumerate readers by grepping for the shape's access pattern
(here: `extraction_provenance` → `profiles`), not by editing the module the
decision was phrased about. Parallel consumers of the same table routinely
carry twin fallbacks: group, synthesise and the synthesis tools each read
`extraction_result` independently, and the 021 amendment converted two of the
three — the third kept silently projecting `{IOF_PROFILE_ID}`.

# Why

The miss produced the worst of both worlds: group raised the contracted
corrupt-reference error while synthesise proceeded on the same row into an
internally inconsistent run (substrate loaded real IOF findings while
`query_findings` reported every kind unavailable) — no error anywhere. Found
by the 021 review stack (removed-behavior finder + security lane convergent);
fixed by mirroring group's loud `corrupt_reference` raise in both synthesise
readers.

# Watch out

- The reader set includes test fixtures: five hand-built rows seeded the flat
  shape and only failed after the guard landed — fixture seeds are readers too.
- "Fail-safe degradation" (empty availability, zero findings) is not
  fail-closed when a sibling path raises: two consumers disagreeing on
  loud-vs-silent for the same corrupt state is itself the defect.
- Same family: [fail-loud-before-first-write](fail-loud-before-first-write.md).
