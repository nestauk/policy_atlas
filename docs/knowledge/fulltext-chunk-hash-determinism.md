---
type: Invariant
title: Full-text chunk content hashes are deterministic — currently via a pymupdf4llm source patch
description: Identical document bytes must produce byte-identical chunks and content_hash regardless of process or worker count; pymupdf4llm 0.3.4 breaks this with an id()-keyed cache, patched at import in ingest_full_text.
tags: [full-text, determinism, provenance, parsing, invariant]
timestamp: 2026-07-05
---

# Rule

Ingesting the same document bytes must produce byte-identical chunks — and therefore identical
`content_hash` values — in every process, at any worker count. Snapshot identity is
content-addressed (data-model: identity = content hash + governance event + locator), so
parse nondeterminism corrupts provenance: dedup, citation verification and the fan-out
determinism guarantee all rest on this. The invariant is test-enforced by
`test_fanout_determinism_workers_1_vs_4` (workers=1 vs 4 → identical normalized DB state).

It does **not** hold naturally today: pymupdf4llm 0.3.4 memoizes a block-in-background-rect
lookup keyed on `id()` (`helpers/multi_column.py`); freed `Rect` addresses are reused mid-loop,
so the cache can return a stale neighbour's answer, and the collision pattern follows
per-process allocation addresses (ASLR) — ~1-in-9 divergence per parse of the 233-page fixture,
serial or parallel alike. `PYTHONHASHSEED` is no fix (it salts str/bytes hashing, not `id()`).
`_install_deterministic_column_boxes()` in `ingest_full_text.py` rebuilds that one function
with a value-keyed cache at import time; proven byte-identical across 32/32 fresh interpreters,
no measurable cost.

# Why

Chunks written at ingest are the permanent content-of-record (no original bytes retained, so
re-parse is impossible by construction). If the same PDF can hash two ways, "same content"
stops being decidable — cross-run comparisons, retries and any future cross-task snapshot
reuse silently fracture.

# Watch out

- The patch is keyed to a byte-exact source string and **silently no-ops** if upstream's
  source changes; the pin floor is `pymupdf4llm>=0.3.4,<1` (raised at the 008 review — older
  floors let a lock regen land on unpatched code) and the determinism test is the backstop.
  On any pymupdf4llm bump: run `test_fanout_determinism_workers_1_vs_4` several times before
  trusting it, and check whether the upstream bug (report filed as a 008 follow-up) is fixed
  so the patch can be deleted.
- Any *new* parser tier (the docling escalation seam) must clear the same bar before its
  profile ships: same bytes, same chunks, every process.

# Citations

- [008-full-text/verification.md](../tasks/008-full-text/verification.md) (post-build
  amendment: root cause, measurement, 32/32 proof; § Review findings item 4: floor raise)
- [ADR 0004](../adr/0004-parse-profile-per-snapshot-pymupdf4llm.md) (parse profiles)
- `_install_deterministic_column_boxes` in `src/policy_atlas/ingest_full_text.py`
- Test: `test_fanout_determinism_workers_1_vs_4`
