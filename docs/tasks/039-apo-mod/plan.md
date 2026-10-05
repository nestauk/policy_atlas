# Plan: 039-apo-mod (re-apply)

Contract: [contract.md](contract.md) (steps S1–S4; rename table there).
Sources: `old_contracts/038-apo-mod/plan.md` (APO chain, incl. the four
adversarial findings already folded in) and
`old_contracts/039-planning-artefact-bugs/plan.md` (bugs 1–3). This plan only
maps them onto the current tree and sets executors/gates.

## Phase 0 — baseline

`make verify` on the fresh branch before any edit. **Executor: lead.**

## Phase 1 — S1 backend: APO filter chain (fast-worker)

Re-apply `old_contracts/038-apo-mod/plan.md` Phase 1–2 at the new paths:

| Old path | New path |
|---|---|
| `runtime/orchestration_plan.py` | `runtime/task_plan.py` (`ScopeConstraints` ~L421, exclusivity validator ~L534, `to_filters` ~L543; `TaskPlan` backend_scope guards ~L915) |
| `runtime/planner_prompt.py` `PlanDraftWire` | same file, flat fields ~L240 (schema field only in this phase) |
| `runtime/orchestrate.py` `build_plan` fold | `runtime/agent.py` ~L623 |
| `api/contract/planning.py` `ScopeConstraintsDraft` | same ~L95 |
| `api/routers/planning.py` `_draft_from_wire` / `_geography_constraints` / `_drop_scope_incompatible_geo` | same, ~L116 / ~L671 / ~L731 |
| `evidence_base/sourcing/search_loop.py` | `evidence_search/sourcing/search_loop.py` (`_OVERTON_FILTER_KEYS` ~L244, `_validate_overton_block` ~L681, `overton_wire_params` ~L526) |
| `evidence_base/sourcing/search_live.py` | `evidence_search/sourcing/search_live.py` (`_OVERTON_ALLOWED_WIRE_KEYS` ~L95) |

Unchanged design (all four old adversarial findings): `Literal["apo"]`,
mutual exclusion with the three geography fields, `backend_scope ==
"grey_lit_only"` required (cleared on any other scope by
`_drop_scope_incompatible_geo`), value allowlisted to `"apo"` in
`_validate_overton_block`, wire key `source`.

**New-tree addition:** `agent.py _render_scope_constraints` (~L680) gains a
`publisher_source` render branch ("Overton source collection: APO"), so the
planner sees the constraint on re-planning turns.

Tests: port the old 038 test set to `test_task_plan.py`,
`test_agent_country_group.py` (round trip), `test_search_directives.py`,
`test_planning_router.py` (geography-token PATCH set, against `/tasks/{id}`).
Gate: `make verify-fast`.

## Phase 2 — S1 frontend: display + types (fast-worker)

`planVocabulary.ts scopeChips` prefers `publisher_source` → "Geography: APO"
(this also feeds `displayedGeography` via the private
`geographyFromConstraints` string-slice — add the paired overlay test);
`make openapi-sync`; tests as in the old Phase 3 (plus the fixture fallout
sweep the old build hit: regenerated TS types make the field
required-nullable). Gate: full `make verify`.

## Phase 3 — S2: case-study citations (codex — judgment-bearing,
machine-verifiable done; the read-path recovery threads through the renamed
`_task_card_claims` alias logic)

Per `old_contracts/039-planning-artefact-bugs/plan.md` Bug 1, at new paths:

- Write: `evidence_search/synthesis/synthesise.py _ground_case_study_card`
  (~L4784) passes explicit `claim_ids = [f"s{section_index}c{idx}" for idx in
  claim_indices]` into `validate_claims` (param exists, ~L696).
- Read: `api/readmodels/repository.py _task_card_claims` (~L1636) — if any
  alias-resolved claim's text is not a substring of the card prose, fall
  through to substring matching; rebind `result_claim_id` via
  `result_ordinal` when the alias misses the card's claims.
- Tests: uniqueness across cards in `test_synthesise.py`
  (`test_case_studies_present_composition` ~L3595); new colliding-alias
  recovery + keep-alias-when-healthy tests in `test_read_models.py` (no
  card-claims test exists today — coverage hole confirmed).

Gate: `make verify-fast`.

## Phase 4 — S3: overlay, Start UX, screening (fast-worker)

Per old plan Bug 2, paths unchanged (frontend) + renamed backend:

- `planOverlay.ts`: `mergeOverlayChanges(overlay, plan, changes)` (dirty-only
  writes; drop keys equal to server display values), prune/`overlayToPlanPatch`
  emits only real diffs; `SCREENING_CRITERION_MAX = 1000`,
  `SCREEN_INTENT_MAX = 2000`, `screeningOverlayError`.
- `PlanDocument.tsx`: section saves use `mergeOverlayChanges` (today they
  spread all fields — confirmed at ~L441/465/549/647); screening becomes a
  list of inputs with + Add rule / − remove, trims empties, soft-rejects
  overlong rules.
- `planStart.ts` + `PlanCard.tsx` + `WorkspaceView`/`PlanningPane`: failure
  copy uses the API message; remove the false "or start without them"; clear
  the notice when the overlay changes; add **Discard edits and start** wired
  to the existing `setPlanOverlay({})` clearer, then start without a PATCH.
- Backend: `SCREENING_CRITERION_MAX = 1000` beside `CRITERIA_LIST_MAX` in
  `evidence_search/assess/screen.py` (~L58), used in `_parse_screen_directive`
  per-entry check (~L269) and the `task_plan.py screening_criteria` validator
  (~L764). `DIRECTIVE_STRING_MAX` stays 200.
- Tests: old plan's list (overlay merge keeps APO; prune omits no-ops;
  screening 1000/1001; +/− UI; dirty-only section saves).

Gate: `make verify-fast`.

## Phase 5 — S4: planner_v11 (lead — prompt-bearing, never delegated)

`runtime/planner_prompt.py`: version → `planner_v11` with a version note;
scope-constraints prose gains the APO rule (set `publisher_source: "apo"` +
`backend_scope: grey_lit_only`, clear country geography, say so in the reply;
never `publisher_country` for APO); screening wording "strictly under 200
characters" → the 1000-char cap; `PlanDraftWire` keeps the strict field from
Phase 1. Re-pin `python3 scripts/prompt_hash_guard.py --update`. Tests:
version assert, prompt-content asserts, 038 router tests still green.
Gate: `make verify-fast`.

## Phase 6 — verify + live checks (lead)

Full `make verify` (step-6 exit). Live: re-run the 038 scripted Overton check
(chain → `source=apo` → APO records). App-level manual passes (screening
edit → Start; APO via chat) recorded if the dev stack is up, else flagged.
`verification.md` + `docs/deferred.md` notes (removal path; chat now teaches
APO via v11).

## Gate consolidation

Full `make verify`: baseline, Phase 2 (generated types), step-6 exit.
All other boundaries: `make verify-fast`. Commit per phase.
