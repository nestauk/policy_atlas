# Implementation plan: 039-planning-artefact-bugs

Re-apply guide for a **fresh branch from current `dev`**. The fixes below
were implemented and tested once on a conflicted branch; recreate them from
this plan rather than merging.

> Paths use the pre-vocabulary-alignment layout (`evidence_base/…`). On a
> tree that already renamed the package to `evidence_search`, substitute
> that path. Frontend paths are unchanged.

---

## Bug 1 — Case studies all share one reference

### Cause

`_ground_case_study_card` called `validate_claims` **once per card**. Default
claim ids are `s{section}c{offset}` with `offset` restarting at 0 each call,
so every card stored `claim_ids: ["s9c0","s9c1",…]`. The read model’s alias
map kept one ClaimOut per alias → every card projected the same citations.

### Write path

File: `backend/src/policy_atlas/evidence_base/synthesis/synthesise.py`
(function `_ground_case_study_card`)

- Already passes `claim_indices = range(claim_index_start, …)`.
- Also pass **explicit** `claim_ids`:

```python
claim_ids = [f"s{section_index}c{idx}" for idx in claim_indices]
# …
initial = validate_claims(
    …,
    claim_ids=claim_ids,
    claim_indices=claim_indices,
    …
)
```

So card 0 gets `sNc0…`, card 1 gets `sNc3…`, etc.

### Read path (recover already-written artefacts)

File: `backend/src/policy_atlas/api/readmodels/repository.py`

- `_project_card_claims`: after resolving via stored `claim_ids`, if **any**
  projected claim’s `text` is **not** a substring of `card.prose`, fall
  through to substring matching against block claims (then sort by span
  start). Healthy rollups (text matches) keep the alias path.
- Add `_resolve_card_result_claim_id`: if the rollup’s `result_claim_id`
  alias does not land in the projected card’s claims, rebind via
  `result_ordinal` into `card_claims`.

### Tests

- `test_case_studies_present_composition`: assert `claim_ids` are **unique
  across cards**.
- `test_project_card_claims_recovers_from_colliding_aliases` (+ keep-alias
  when text matches) in `tests/api/test_read_models.py`.

---

## Bug 2 — Plan edits fail apply / Start blocked + screening UX

### Cause

1. Saving **Search filters** always wrote `geography` (and years) into the
   overlay even when unchanged → later Start PATCHed a stale empty /
   invalid geography and 422’d the whole apply (screening looked “guilty”).
2. Failure copy promised “start without them” with **no** discard action.
3. Per-criterion cap of **200** (`DIRECTIVE_STRING_MAX`) was too short for
   real screening rules.

### Overlay: dirty-only saves + patch-against-plan

File: `frontend/src/views/workspace/planOverlay.ts`

- `mergeOverlayChanges(overlay, plan, changes)` — only put keys that
  **differ** from the server display values; delete keys that match
  (so Sources-only save cannot blank APO geography).
- `pruneOverlayToPlanDiff` / `overlayToPlanPatch(overlay, plan?)` — emit
  only fields that still differ from the live plan.
- `SCREENING_CRITERION_MAX = 1000`, `SCREEN_INTENT_MAX = 2000`.
- `screeningOverlayError(criteria, question)` — client check mirroring
  backend `_compose_screen_intent` format before PATCH.

`PlanDocument.tsx` section Saves: use `mergeOverlayChanges`, not
`{ ...overlay, …allFields }`.

### Start failure UX

File: `frontend/src/views/workspace/planStart.ts` (+ `PlanCard.tsx`,
`PlanDocument.tsx`)

- Prefer API `message`: `Those plan edits couldn't be saved: ${message}`.
- Drop the lying “or start without them” unless a real path exists.
- `useEffect` on `overlay` clears `startNotice`.
- **Discard edits and start**: `onDiscardOverlay()` then start against the
  last saved server plan (no PATCH).
- Wire `onDiscardOverlay` from `WorkspaceView` / `PlanningPane` (same
  clearer as `setPlanOverlay({})`).

### Screening UI

`PlanDocument.tsx` Screening rules section:

- List of text inputs; **+ Add rule** / **−** remove (allow a single empty
  field while editing; save trims empties).
- Soft reject on save if any rule `> SCREENING_CRITERION_MAX`.

### Backend screening cap

- Add `SCREENING_CRITERION_MAX = 1000` next to `CRITERIA_LIST_MAX` in
  `…/assess/screen.py`.
- Use it in `_parse_screen_directive` criteria entry length (not
  `DIRECTIVE_STRING_MAX`).
- `orchestration_plan.py` `screening_criteria` validator: same 1000 cap.
- Do **not** raise global `DIRECTIVE_STRING_MAX`.

### Tests

- `planOverlay.test.ts`: merge does not blank APO geography; prune/patch
  omit no-ops; overlong screening error.
- `PlanDocument.test.tsx`: screening +/- save; settings save only dirty
  keys; APO geography display when `publisher_source: "apo"`.
- Backend: plan + screen directive accept 1000 / reject 1001; list max 50
  unchanged; composed intent 2000 still enforced.

---

## Bug 3 — APO shows in Source geography + chat can set it

### Display (overlay must not shadow)

Already covered by dirty-only overlay: server
`scope_constraints.publisher_source === "apo"` → `scopeChips` →
`displayedGeography` → **"APO"**. A Filters save that only changes Sources
must not write `geography: ""` into the overlay.

038 geography box tokens (`APO` / `Australian Policy Online` → PATCH
`geography` → `_geography_constraints` → `publisher_source: "apo"`,
requires `grey_lit_only`) stay as-is.

### Planner chat

File: `backend/src/policy_atlas/runtime/planner_prompt.py`

- Bump `PLANNER_PROMPT_VERSION` to **`planner_v11`**.
- Under scope constraints, add: when user asks for APO / Australian Policy
  Online (or planner chooses that collection), set
  `publisher_source: "apo"`, `backend_scope: grey_lit_only`, clear country
  geography fields; say so in `reply`. Never use `publisher_country` for
  APO.
- Update screening prompt wording from “under 200 characters” to “at most
  1000 characters”.
- Keep wire validator: only literal `"apo"` survives on `PlanDraftWire`.
- Re-pin: `python3 scripts/prompt_hash_guard.py --update`.

### Tests

- Planner version assert `planner_v11`.
- Prompt contains APO / `publisher_source` / 1000-character wording.
- Existing 038 planning-router geography token tests still green.

---

## Suggested implementation order

1. Case-study write + read recovery + tests (independent).
2. Overlay merge/prune + Start UX + PlanDocument save handlers + tests.
3. Screening +/- UI + `SCREENING_CRITERION_MAX` backend + tests.
4. `planner_v11` + prompt hash + APO display tests.

## Manual checks

1. Artefact with multiple case studies → each card’s citations match that
   programme’s source (re-check project `11241c21-…` if still available,
   or any multi-card artefact).
2. Edit only screening → Start succeeds.
3. Force a bad geography apply → specific message → fix or Discard → Start
   runs.
4. Ask for APO in planning chat (Sources grey lit) → Source geography shows
   **APO** without typing it; Overton calls carry `source=apo`.
5. Manually type APO / Australian Policy Online with grey lit → same.

## Out of scope on re-apply

- Resolving the abandoned merge on `task038/apo-mod`.
- Rewriting 038 docs (optional one-liner in `deferred.md` that chat now
  teaches APO via v11 is enough if you touch deferred at all).
