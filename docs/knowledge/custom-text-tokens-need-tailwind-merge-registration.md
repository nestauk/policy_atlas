---
type: Frontend rule
title: Custom text-<size> theme tokens must be registered with tailwind-merge, or colours get silently stripped
description: tailwind-merge classifies an unknown `text-<x>` utility as a text COLOUR, so once 028's named type scale (text-meta, text-body, …) landed on shared components, twMerge("… text-white … text-meta") dropped text-white and every primary button rendered ink-on-blue in production — with all tests green. Register custom scale tokens as font-size class groups via extendTailwindMerge at the cn() seam.
tags: [frontend, tailwind, tailwind-merge, type-scale, task-028, review-lesson]
timestamp: 2026-08-05
---

# Rule

`tailwind-merge` resolves conflicts by classifying utilities into groups,
and an unrecognised `text-<x>` value falls into the text-**colour** group.
Any custom `@theme` font-size token (`--text-meta` → `text-meta`) is
unrecognised, so a class list carrying both a real colour and a scale
token — exactly what `cva` variant+size composition produces — keeps only
the later one: `twMerge("text-white … text-meta")` → `text-meta`, colour
gone.

Register the scale where `cn()` is defined, once:

```ts
const twMerge = extendTailwindMerge({
  extend: { classGroups: { "font-size": [{ text: ["caption", "meta", ...] }] } },
});
```

Any new named text token must be added to this list in the same commit
that adds it to `@theme`.

# Why

028 batch 13 moved shared components onto the named scale; from that
commit every brand primary button (`New project`, send, part-card
presets) rendered near-black text on blue in the deployed app. Nothing
failed: typecheck, lint, 185 vitests and the mock e2e were all green —
class-string stripping is invisible to every gate that doesn't assert the
merged class output. The owner caught it by eye on the live demo.

# Watch out

- Arbitrary-value sizes (`text-[11.5px]`) parse as lengths and are safe;
  it's the NAMED custom tokens that misclassify.
- The failure needs both halves through `cn()`/`twMerge` — raw
  `className` strings that never pass through the merge (plain string
  interpolation) are unaffected, which makes the breakage look
  inconsistent across surfaces.
- Regression guard: one test asserting a composed component keeps both
  its colour and its size class (`Button.test.tsx`).

# Citations

- `frontend/src/ui/brand/cn.ts` (the registration)
- `frontend/src/ui/brand/Button.test.tsx` (regression test)
