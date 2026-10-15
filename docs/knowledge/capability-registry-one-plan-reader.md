---
type: Architecture
title: Every plan reader goes through the capability registry, and the AST seam guards both plan models
description: `runtime/capability_registry.py` is the one place that says which plan model validates a stored payload, which chain composes it, which prompt is the Task Agent's and which steer points exist, keyed by `task.capability`. Fourteen validate sites and seven compose sites route through it (task 044); `tests/runtime/test_capability_registry.py` scans `backend/src` by AST and fails on a bare `TaskPlan.model_validate`, `ScopingPlan.model_validate` or `compose(` outside the registry and the model's own factory. The registry cannot be imported from `task_plan.py` (registry → steering → task_plan), so each capability's validator holds its own steer-point set, pinned equal to the registry's by test.
tags: [architecture, capability, registry, plan, steering, task-044]
timestamp: 2026-09-17
---

# Rule

- A reader of a plan payload never names a plan model or a chain composer. It calls
  `validate_plan(capability, payload)` / `compose_plan(capability, plan)` /
  `lattice_for(capability)` / `steer_points_for(capability)`; an unknown capability is
  `UnknownCapability`, never a default (a row this build does not know is a row it must not run).
- Chassis code that carries a plan without knowing its kind (`runner.py`, `continuation_state.py`)
  is typed `AnyPlan = TaskPlan | ScopingPlan`; hand-offs into Evidence-search-only code narrow
  through `expect_task_plan`, which raises rather than guessing.
- The seam is enforced by AST, both directions: `tests/runtime/test_capability_registry.py` bans
  `TaskPlan.model_validate`, `ScopingPlan.model_validate` and bare `compose(` everywhere in
  `backend/src` except the registry and the model's own factory module, with a self-test that
  proves the scanner fires.
- The steering lattice is keyed by capability: `lattice_policy` returns `off` for a point outside
  the given lattice, so a scoping steer point never fires on an Evidence search walk in frequent
  mode (A2).

# Why

Before 044 one capability existed and every reader spelled `TaskPlan` directly. A second plan
model makes the guess a bug: validating a scoping payload against `TaskPlan`, or composing an
Evidence search chain for a scoping task. The registry made the second capability cost one dict
entry; the AST test is what keeps later readers honest — a reviewer counted 14 validate sites at
the review stack against the ADR's "ten", all routed, because the test made the bypass impossible
rather than merely discouraged.

# Watch out

- `capability_registry` imports `task_plan`, `scoping_plan` and `steering`; nothing those three
  import may import the registry back. Per-capability validators therefore keep their own
  steer-point frozensets (`STEER_POINTS`, `SCOPING_STEER_POINTS`), pinned equal to the registry's
  by test.
- A per-capability `_SteeringState.capability` default (`evidence_search`) exists so the
  pre-044 steering tests construct state unchanged; every production site passes it explicitly.
- Related: [baseline-gate-invariants-as-built](baseline-gate-invariants-as-built.md),
  [plan-lineage-by-fencing-not-custody](plan-lineage-by-fencing-not-custody.md).

# Citations

- [ADR 0037](../adr/0037-options-scoping-task-kind-links-and-baseline-gate.md) § Decisions 3
- `backend/src/policy_atlas/runtime/capability_registry.py`, `backend/tests/runtime/test_capability_registry.py`
- [044 verification.md](../tasks/044-scoping-shell-baseline/verification.md) § Phase 2, § Review findings
