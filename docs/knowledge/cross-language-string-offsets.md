---
type: Invariant (verified)
title: String offsets crossing the Python→JS boundary are code-point indices — slice by code points client-side
description: Python str indexing counts Unicode code points; JS string indexing counts UTF-16 code units, so any astral character (emoji, some CJK) before a server-computed span shifts it client-side. AnnotatedProse slices Array.from(prose) (code points), unit-tested with an astral fixture.
tags: [unicode, offsets, annotations, frontend, python, javascript]
timestamp: 2026-07-29
---

# Rule

Annotation span offsets are computed in Python (`str` slicing → **code
points**) and consumed in the browser (JS strings → **UTF-16 code units**).
The two agree only on BMP-only text. Client code that applies server offsets
must slice by code points: `Array.from(prose)` once, slice the array, join —
see `ArtefactView.tsx::AnnotatedProse` and its astral-character unit test
("🌍🌍 policy works", span `[3, 9]`).

# Why

027 review (security lane): every claim span after an emoji in the prose would
have highlighted shifted text — plausible-looking, silently wrong provenance.
The mismatch is invisible in ASCII fixtures, so only a deliberate astral test
pins it.
