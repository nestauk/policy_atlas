# Plan: 038-apo-mod

Contract: [contract.md](contract.md). Terms and requirement ids (R1–R3) live
there. R1 is free (existing `backend_scope="grey_lit_only"`); this plan builds
R2 and R3.

The shape of the change: thread one new key, `publisher_source`, through the
existing fail-closed filter chain, and let the Source geography box set it.
Every gate below currently rejects unknown keys, so each one needs its single
entry — that is the whole backend.

## Phase 0 — baseline

Run `make verify` on `task038/apo-mod` before any edit. Never build on red.
**Executor: lead** (one command, inline).

## Phase 1 — backend filter chain (R2)

One precise sweep; every touch point is known:

| # | File | Change |
|---|---|---|
| 1 | `runtime/orchestration_plan.py` | `ScopeConstraints.publisher_source: str \| None = None`; emit `{"publisher_source": ...}` into the `overton` block in `to_filters()` (mirror `publisher_country` at ~L546); cross-field validator rejects it under `backend_scope="academic_only"` (mirror the existing guard at ~L873). |
| 2 | `runtime/planner_prompt.py` | `PlanDraftWire` gains the optional field so stored plans round-trip through the draft↔plan projections. **No prompt text change** — `planner_v10` stays. |
| 3 | `sourcing/search_loop.py` | Add `publisher_source` to `_OVERTON_FILTER_KEYS` (~L244); accept it in `_validate_overton_block` (value must be a non-empty string, ~L681); map it in `overton_wire_params` → `params["source"] = value` (~L526). |
| 4 | `sourcing/search_live.py` | Add `"source"` to `_OVERTON_ALLOWED_WIRE_KEYS` (~L95). |

Tests (same commit): `to_filters` emits the overton block; wire params contain
`source=apo`; the academic-only guard raises; an unknown wire key still raises.

Gate: `make verify-fast`. **Executor: fast-worker** — mechanical transcription
of an exact spec; every file, line and guard shape is named above.

## Phase 2 — geography token (R2 entry point)

`api/routers/planning.py`:

- `_geography_constraints`: before token resolution, if the trimmed input
  case-insensitively equals `"APO"` or `"Australian Policy Online"`: require
  `backend_scope == "grey_lit_only"`, else raise `ValueError` with the message
  "APO restriction needs Sources set to grey literature only" (the route
  already converts `ValueError` to 422); on success return constraints with
  `publisher_source="apo"` and the three geography fields cleared.
- `_drop_scope_incompatible_geo`: clear `publisher_source` when
  `backend_scope == "academic_only"`.
- `_apply_plan_patch`: confirm a later plain-geography edit (for example
  "France") clears `publisher_source` — the token branch returns a full
  constraints dict, so this should already hold; add the test.

Tests: PATCH with the token → plan carries the constraint (both casings);
PATCH with wrong scope → 422; PATCH with a country afterwards clears it.

Gate: `make verify-fast`. **Executor: fast-worker** — exact spec above.

## Phase 3 — display round-trip (R3) + generated types

- `frontend/src/views/workspace/planVocabulary.ts` (`scopeChips`) /
  `planOverlay.ts`: when `scope_constraints.publisher_source === "apo"`, the
  geography chip reads "APO", so `displayedGeography` shows "APO" in the
  Source geography box after a reload.
- `make openapi-sync` regenerates `frontend/openapi.json` and
  `frontend/src/api/gen/types.ts` (never edit these by hand).
- Frontend test: a plan with the constraint renders "APO" in the geography
  display.

Gate: full `make verify` (includes `drift-check`). **Executor: fast-worker.**

## Phase 4 — live check + verification (step 6)

The contract's pinned live check: edit one plan through the UI (Sources =
grey literature only, geography = APO), run one acquire round, capture the
Overton request URL (`source=apo` present), confirm zero OpenAlex requests and
that the returned documents are APO records. Write `verification.md`; add the
removal note to `docs/deferred.md`.

Gate: full `make verify` (step-6 exit). **Executor: lead** — the live check
needs credentials and judgment on the evidence; not delegable as a brief.

## Gate consolidation

Phases 1–2 are new-key threading with no schema or reader contact: they gate
on `verify-fast`. The two full `make verify` runs sit where the mandatory
classes are — the generated-types phase and the step-6 exit — plus the Phase 0
baseline.

## Out of plan

Planner prompt text, orchestrator/runner, backend selection, any new UI
control, schema. If Overton rejects `source=apo` live, stop and report
(contract § Stop conditions).
