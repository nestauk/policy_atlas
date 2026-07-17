---
type: Invariant
title: Every directive key is explicitly plan-mappable or commit-layer — an unclassified key is a silent drop or a crash
description: Steering directive keys split into plan-mappable (rewrite the plan payload) and commit-layer (overlay onto the pending component's executed directive). The split must be explicit per component (_MIXED_COMMIT_LAYER_KEYS); compile-time grammar acceptance without an apply-time classification produced first a silent drop (build, 15d) and then a confirmed-steer crash (review, MAJOR).
tags: [steering, directive-grammar, pending-overlay, commit-layer, fail-closed, task-024]
timestamp: 2026-07-17
---

# Rule

A steering delta for a **not-yet-run** component reaches it one of two ways:
plan-mappable keys rewrite the plan payload (`_apply_<component>_delta`);
commit-layer keys fold into the **pending overlay** and merge into the
component's executed directive at its run (`_MIXED_COMMIT_LAYER_KEYS` in
`runtime/steering.py`; `plan.compiled` events echo the overlay).

The invariant: **when a component's grammar gains a key, classify it in the
split — compile-time acceptance is not enough.** The same gap shipped twice
in task 024: the build found `extract.refresh`/`relevance_emphasis` recorded
then silently discarded at plan-mapping (fix 15d created the split); the
review stack found `select` never joined it — the router compiled
`selection.strata_scope`/`exclude_ids` at P2, the user confirmed, and
apply-time raised through an unguarded path (run crash, no event). Both fixes
are the same move: name the component's commit-layer keys, let the overlay
carry them, and keep the apply-time raise as the loud guard for genuinely
unknown keys (now caught and evented by the fan-out apply's
`SteeringAdjustmentError` guard).
