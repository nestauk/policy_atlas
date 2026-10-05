---
type: Invariant
title: A new ScopeConstraints field must touch every projection surface — and the planner sees it via the wire draft, not the CLI render
description: publisher_source (039) mapped the full surface set — PlanDraftWire (re-planning visibility, with normalisation at the API fold), the CLI-only _render_scope_constraints, scopeChips (whose text the overlay's geography derivation string-slices), and the deferred removal note. Missing one leaves the field invisible, a 500 path, or a silent edit-behaviour change.
tags: [plan, scope-constraints, planner, frontend, wire-models]
timestamp: 2026-09-08
---

# Rule

A field added to `ScopeConstraints` (`runtime/task_plan.py`) is not one change.
Each projection surface below must be touched, or the field fails in a
different, quiet way:

| Surface | What it does | Failure if missed |
|---|---|---|
| `PlanDraftWire` (`runtime/planner_prompt.py`) | The planner's ONLY view of current constraints on re-planning turns (the draft attachment). | The planner cannot see or preserve the field. NB `_render_scope_constraints` (`runtime/agent.py`) does NOT reach the planner — its only consumer is the dev CLI approval prompt (`agent.py` `console.print(_render_full_plan(...))`). The 039 build recorded the CLI renderer as the mechanism; the step-7 contract verifier corrected it. |
| `_draft_from_wire` (`api/routers/planning.py`) | Folds the loose wire (`str`) into the strict API draft (`Literal[...]`). | An unguarded `model_validate` 500s the whole planning turn on a sloppy planner value (e.g. `"APO"` for `"apo"`) — normalise the taught spellings and drop anything else so the turn degrades (`ready=false`) instead (039 review stack, confirmed). |
| `build_plan` fold list (`runtime/agent.py`) | Copies wire values into the validated plan. | Field silently dropped at approval. |
| `scopeChips` (`frontend/.../planVocabulary.ts`) | Plan-document display. | Invisible to the user — AND the overlay's `geographyFromConstraints` derives edit state by string-slicing the `Geography:` chip, so a display-only wording change silently changes edit behaviour. Pin with a paired `displayedGeography` test. |
| Removal note (`docs/deferred.md`) | The field's exit path. | Orphaned validation branches on removal. |

# Why

039's `publisher_source` needed all five; the original 038 plan missed the
renderer surface and the re-apply scout initially attributed the wrong
mechanism to it. The loose-wire→strict-draft 500 was found (and fixed with a
normaliser + test) only by the review stack.

# Citations

- `backend/src/policy_atlas/runtime/planner_prompt.py` (`PlanDraftWire`)
- `backend/src/policy_atlas/api/routers/planning.py` (`_draft_from_wire` normaliser)
- `backend/tests/api/test_planning_router.py::test_draft_from_wire_normalises_loose_publisher_source`
- `frontend/src/views/workspace/planVocabulary.test.ts` (chip pins), `planOverlay.test.ts` ("reads APO from publisher_source")
- [docs/tasks/039-apo-mod/verification.md](../tasks/039-apo-mod/verification.md) § Review findings
- Related: [wire-field-additions-break-all-construction-sites](wire-field-additions-break-all-construction-sites.md)
