---
type: Convention
title: A new model field must sweep every site that rebuilds the model key-by-key — rebuild sites drop unknown keys silently
description: ScopeConstraints has seven mapping sites (model, API mirror, two flat↔nested fold lists, the steering-delta rebuild, the CLI render, the geography reset dict); the build found four. The silent ones are the hazard — a fold list, a wholesale rebuild, or a display switch shows nothing wrong until the field just isn't there.
tags: [model-fields, round-trip, fold-lists, steering, silent-drop]
timestamp: 2026-09-04
---

# Rule

Before adding a field to a model that other code rebuilds key-by-key, grep
for **every** rebuild site — not just the ones on the happy path. For
`ScopeConstraints` (as of 038) the inventory is seven:

1. `runtime/orchestration_plan.py` — the model itself (+ validators).
2. `api/contract/planning.py` `ScopeConstraintsDraft` — the API mirror;
   missing it means `PlanOut` drops the field and the UI can't render it.
3. `runtime/orchestrate.py build_plan` — flat→nested fold list.
4. `api/routers/planning.py _draft_from_wire` — the second fold list.
5. `runtime/steering.py _scope_constraints_from_filters` — steering deltas
   rebuild the whole constraints block; an unmapped field is silently
   dropped from the amended plan on the first acquire-filters Adjust.
6. `runtime/orchestrate.py _render_scope_constraints` — the CLI approval
   render; an unlisted field shows the plan as unrestricted.
7. `api/routers/planning.py _GEO_CONSTRAINT_RESET` — the geography compile
   returns a full reset dict because the caller merges via
   `constraints.update()`; an omitted key survives unrelated edits.

Sites 3–7 fail **silently** (key dropped or not shown), never loudly. The
loud layers (pydantic `extra="forbid"`, allowlists) don't cover them because
each rebuilds from its own literal key list.

# Why

038 threaded `publisher_source` through sites 1–4 (the plan's adversarial
pass had already caught 2–4) and recorded "four places" as the lesson. The
review stack then found site 5 live-droppable (a steered APO run lost
`source=apo` for every subsequent Overton call — the slice's core R2
requirement) and site 6 rendering an APO plan as unrestricted. The corrected
count is the concept: the number you found is a lower bound until you've
grepped for rebuilds, renders and resets.

# Watch out

- Generated-type fallout is part of the sweep: `openapi-typescript` emits an
  optional-nullable pydantic field as a *required*-nullable TS key, so every
  frontend fixture literal for the parent type needs a mechanical
  `new_field: null` line — budget for it, don't hand-edit generated files.
- A steering/delta layer that rebuilds state wholesale needs an explicit
  decision per new field: mappable, rejected, or carried over (038 chose
  carry-over — the field is tester-pinned, not steerable).
