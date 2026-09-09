# Plan: 038-apo-mod

Contract: [contract.md](contract.md). Terms and requirement ids (R1–R3) live
there. R1 is free (existing `backend_scope="grey_lit_only"`); this plan builds
R2 and R3.

> **Adversarial review (one light combined pass, Codex, 2026-09-04) — four
> findings, all accepted and folded into the phases below:**
> (1) `publisher_source` must require `backend_scope="grey_lit_only"` and be
> cleared on *every* other scope — rejecting only `academic_only` would let a
> later "Sources = All" edit keep the constraint while OpenAlex runs,
> violating R1. (2) The API projection model `ScopeConstraintsDraft`
> (`api/contract/planning.py`) also needs the field, or `PlanOut` drops it and
> R3 cannot render. (3) The two flat↔nested fold lists (`orchestrate.py`
> `build_plan`, `planning.py` `_draft_from_wire`) must carry the key or the
> round trip silently loses it. (4) The value is pinned to the literal
> `"apo"` everywhere (`Literal["apo"]` in the models, an allowlist in the
> directive validator) — never an arbitrary passthrough string.

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
| 1 | `runtime/orchestration_plan.py` | `ScopeConstraints.publisher_source: Literal["apo"] \| None = None`; mutually exclusive with `publisher_country`, `author_affiliation_countries` and `country_group` (extend the existing exclusivity validator — the APO token replaces geography, and `to_filters()` early-returns on `country_group`); `to_filters()` emits `filters["overton"] = {"publisher_source": self.publisher_source}` when set; `OrchestrationPlan` cross-field validator **requires `backend_scope == "grey_lit_only"`** when the field is set (finding 1). |
| 2 | `runtime/planner_prompt.py` + fold lists | `PlanDraftWire` gains the optional field (**no prompt text change** — `planner_v10` stays); add `"publisher_source"` to the flat→nested fold in `orchestrate.py build_plan` (~L622) and to the fold list in `api/routers/planning.py _draft_from_wire` (~L120) (finding 3). |
| 3 | `api/contract/planning.py` | `ScopeConstraintsDraft.publisher_source: Literal["apo"] \| None = None` so `PlanOut` carries it to the frontend (finding 2). |
| 4 | `sourcing/search_loop.py` | Add `publisher_source` to `_OVERTON_FILTER_KEYS`; accept it in `_validate_overton_block` with the value allowlisted to `"apo"` only (finding 4); map it in `overton_wire_params` → `params["source"] = value`. |
| 5 | `sourcing/search_live.py` | Add `"source"` to `_OVERTON_ALLOWED_WIRE_KEYS`. |

Tests (same commit): `to_filters` emits the overton block; wire params contain
`source=apo`; the grey-lit-only guard raises for `academic_only` **and**
`both`; the exclusivity guard raises; `_validate_overton_block` rejects any
value other than `"apo"`; an unknown wire key still raises; a
draft→plan→draft round trip keeps the field.

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
- `_drop_scope_incompatible_geo`: clear `publisher_source` whenever
  `backend_scope != "grey_lit_only"` (finding 1 — a later "Sources = All" edit
  silently drops the APO restriction, same as the existing incompatible-geo
  behaviour).
- Every non-APO return path of `_geography_constraints` includes
  `"publisher_source": None`, so editing geography to a country clears APO.
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
