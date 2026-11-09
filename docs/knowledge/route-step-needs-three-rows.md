---
type: Convention
title: A new model-call step needs three rows, and a missing cache-mode row fails silently inside a broad except
description: Every route step is declared in three places (the `[steps]` table and the per-route override in `model_routes.toml`, and `synthesis/cache_modes.py`); a step missing from `CACHE_MODES` raised inside the streamed call's catch-all so every streamed turn fell back to the forced tool call with no error, and a test now pins the cache table against the steps table.
tags: [model-routes, prompt-caching, streaming, synthesis, testing, "058"]
timestamp: 2026-11-09
---

# Rule

- A model-call step is three rows, not one: the `[steps]` row and the per-route override in
  `backend/src/policy_atlas/model_routes.toml`, and the cache-mode row in
  `evidence_search/synthesis/cache_modes.py` (ADR 0042; the table lives beside the route
  file, `docs/deferred.md` § Queued ingest names the seam).
- A step with no cache-mode row raises on lookup. Inside a call wrapped in a catch-all
  fallback (task 058's streamed write turn: "any failure re-runs the turn without
  streaming") that raise is swallowed as a fallback, so the feature is off and nothing is red.
- `tests/core/test_call_site_kwargs.py::test_every_step_has_a_cache_mode_and_sends_it` (058)
  pins `CACHE_MODES` against the steps table; add the row before the call site, and give any new catch-all fallback a
  counter that reaches a durable record (`stream_fallbacks` rides in the synthesis
  component's completed payload since the 058 review).

# Why

Task 058 built the streamed section turn, gated it green, and every streamed turn fell back
silently: the `synthesise_section_emit` step had its two route rows and no cache-mode row.
The owner saw no streaming on a live run; Langfuse showed the server streaming (the review of
the trace, not the tests, found it). The review then found the fallback count itself lived
only in memory and a warning log: one real fallback on 2026-11-06 (a 32 s read timeout) was
diagnosable from the trace alone, which the review rule forbids.
