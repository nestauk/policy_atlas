---
type: Invariant
title: Per-document fan-out isolates the decision call, not the persistence
description: Only the per-document classification/screening decision call is wrapped in try/except, falling back to an already constraint-valid outcome — never the insert — so one bad document can't abort the batch or poison the transaction.
tags: [harness, fan-out, error-handling, invariant]
timestamp: 2026-07-01
---

# Rule

In a per-document fan-out loop, wrap only the call that can genuinely fail per-document (the
classification/screening decision — today a deterministic stub, eventually an LLM call) in
try/except. On exception, fall back to a result value that is *already* valid under every DB
constraint (`"Unknown / Insufficient information"` for classify, `status="failed"` for screen —
both pre-existing closed values, not new ones). Then let the insert run unguarded.

Do **not** wrap the insert itself in the per-row try/except. If the insert can fail, the fallback
value is wrong (it should always satisfy the constraints), and catching an insert failure inside a
loop risks a poisoned-transaction state in Postgres — once one statement in a transaction errors,
every subsequent statement fails with "current transaction is aborted" until a rollback, so
"catch and continue looping" silently stops working exactly when you need it.

# Why

A fan-out over N documents where one throws (network timeout, malformed model output once a real
inference call replaces the stub) must not abort processing of the other N-1. Per
[system/execution-orchestration.md](../specs/system/execution-orchestration.md) and
[capabilities/evidence-search/components.md](../specs/capabilities/evidence-search/components.md),
screen/classify/appraise are all declared "per-document fan-out" — the harness-level exception
guard (see the harness's `_run_scope_component`) only stops the *run* from getting stuck; it does
not provide per-document isolation on its own. That has to live inside the fan-out loop itself.

# Watch out

This pattern only works because each component already has a genuine "I don't know" closed value
(`Unknown` / `failed`) to fall back to. A future per-document component without such a value would
need one before this pattern applies — don't invent a new sentinel column just to make the
try/except fit.

# Citations

- [005-classify/verification.md](../tasks/005-classify/verification.md) (Review findings — raised
  directly in conversation, not by an automated review pass)
- `classify_sources`/`screen_sources` in `src/policy_atlas/classify.py` / `src/policy_atlas/screen.py`
- Tests: `test_classify_sources_doc_exception_isolated`, `test_screen_sources_doc_exception_isolated`
