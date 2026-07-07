---
type: Integration quirk
title: Postgres rejects NUL (U+0000) in TEXT/JSONB — scrub model output at the backend boundary
description: A model can emit strings containing NUL; psycopg raises UntranslatableCharacter at write time and aborts the transaction. Model output is untrusted data — strip NULs once, where records come off the wire, before validation and verification.
tags: [llm, postgres, psycopg, untrusted-output, extraction, sanitisation]
timestamp: 2026-07-07
---

# Rule

Postgres cannot store the NUL character (U+0000) in `TEXT` or `JSONB`; psycopg raises
`UntranslatableCharacter` at write time. LLMs *do* emit NUL-bearing strings (task 011's
second live run: a model-emitted NUL aborted the whole extract step — the outer transaction
rolled back atomically, no partial state). Since model output is untrusted data, NULs are
stripped **once, at the backend boundary** as records come off the wire
(`_scrub_nul` in `src/policy_atlas/extract.py`), before validation or quote verification —
not per-column at write time, and not in the stub path (a NUL cannot ride the DB-stored
stub sentinel for the same reason, so the regression test uses a misbehaving backend
double).

# Why

The failure is invisible until a live model emits one — no schema, pydantic or fixture test
catches it, because the wire models accept the string happily and the error only fires at
the INSERT. Scrubbing at the single seam keeps every downstream consumer (validators,
verifier, writes) working on storable text and keeps the fix at the right altitude: one
boundary, not N call sites.

# Watch out

- Any future backend seam that stores wire text (group, synthesise) needs the same scrub at
  its own boundary — grep for `_scrub_nul` and lift it if a second consumer appears.
- Quote verification runs on scrubbed text against frozen (never-scrubbed) basis text; a
  quote whose only mismatch was a NUL now verifies — that's correct (the NUL was model
  noise, not source text).

# Citations

- [011-extract/verification.md](../tasks/011-extract/verification.md) (§ Live-run evidence,
  run 2; § Diff summary deviation 3)
- `_scrub_nul` in `src/policy_atlas/extract.py`
- Test: `test_nul_bearing_model_output_is_scrubbed` in `tests/test_extract.py`
