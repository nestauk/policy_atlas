# Verification: 039-apo-mod (re-apply)

Evidence for the combined slice (contract S1–S4). Filled at step 6; Review
findings + Rubric status follow at step 7.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (baseline, fresh branch) | pass | dev tip `a3c1c28` clean |
| `make verify` (Phase 2 gate) | pass* | *green except prompt-guard on the schema-only `PlanDraftWire` line; adjudicated and re-pinned (see deviations) — every other gate green individually (backend 2537, frontend 565, drift-check OK) |
| targeted pytest (S2 + planner files, test DB) | pass | 100 passed (`test_synthesise.py`, `test_read_models.py`, `test_planner.py`) |
| `make verify-fast` (Phase 4 gate) | pass | exit 0 |
| `make verify` (step-6 exit) | pass | exit 0 — includes prompt-guard (v11 pinned), drift-check, frontend build |

## Checks beyond the build

- **S1 (APO chain)** — same deterministic test set as the original 038 build,
  ported to the renamed modules: `to_filters` compiles the overton block;
  fail-closed matrix (mutual exclusion, `academic_only`/`both` rejected, value
  `"xyz"` rejected); `build_plan` round trip; wire mapping → `{"source":
  "apo"}`; PATCH `/api/v1/tasks/{task_id}/plan` token set (both spellings, 422
  off grey-lit-only, cleared by a later country or scope edit); scopeChips /
  `displayedGeography` "APO"; NEW: `_render_scope_constraints` shows
  `publisher_source: apo` on re-planning turns.
- **S2 (case studies)** — composition test asserts claim ids unique across
  cards; read-model tests: colliding-alias recovery (prose substring,
  span-sorted, `result_claim_id` rebound via `result_ordinal`) and
  healthy-alias preservation.
- **S3 (overlay/Start/screening)** — `mergeOverlayChanges` keeps APO geography
  on a Sources-only save and drops keys equal to server values;
  `overlayToPlanPatch` prunes no-ops; Start failure copy carries the API
  message, no false "start without them"; Discard-edits-and-start clears the
  overlay and starts without a PATCH; screening +/− list; 1000-char rule
  accepted, 1001 rejected (backend directive + plan grammar + client mirror);
  list max 50 and composed 2000 unchanged.
- **S4 (planner_v11)** — version pin test; prompt-content asserts (APO rule,
  `grey_lit_only`, never-`publisher_country`-for-APO, no stale "under 200
  characters" wording).
- **Live check (contract-pinned scope, run 2026-09-08):** real Overton call
  through the production chain. Logged request (key redacted):
  `GET https://app.overton.io/documents.php?source=apo&squery=What+does+the+evidence+say+about+social+housing+policy+outcomes%3F&min_similarity=0.3&format=json&pp=50&api_key=REDACTED "HTTP/1.1 200 OK"`.
  5/5 records: `source.source_id="apo"`, "Australian Policy Online",
  country Australia. No OpenAlex request (grey-lit-only backend scoping is
  pre-existing, unit-tested behaviour).

## End-to-end command

```
set -a && source backend/.env && set +a && \
uv run --project backend python <scratchpad>/apo_live_check_039.py
```

## Diff summary

Six commits on `task/039-apo-mod` after the docs commit:

- `3a04952` S1 — APO chain re-applied at renamed paths (`task_plan.py`,
  `agent.py`, `ScopeConstraintsDraft`, planning router token, Overton
  allowlists, scopeChips, openapi regen). Design identical to the reviewed
  038 build (its four adversarial findings included).
- `b617176` S2 — case-study citation fix (Codex-built, lead-reviewed).
- `a911043` S4 — `planner_v11` (lead-written prompt) + hash re-pin.
- `368b467` S3 — dirty-only overlay, honest Start failures + Discard,
  screening list UX + `SCREENING_CRITERION_MAX = 1000`.

**Flagged deviations (visible, not drift):**

1. **Two prompt-hash re-pins.** Phase 1's `PlanDraftWire` field is a
   schema-only line in `planner_prompt.py` (verified single-line diff; prompt
   text untouched at that commit); Phase 5's v11 is a real prompt change.
   Both named in the approved plan.
2. **Render style choice:** `_render_scope_constraints` shows
   `publisher_source: apo` (field-name style of its siblings) rather than a
   prose label, so the constraint maps 1:1 to what `planner_v11` teaches.
3. **Live-check shape** as in the original build: PATCH-route tests + scripted
   live acquire, no browser drive. The owner's own Australian test run covers
   the full UI pass. The old bug-diagnosis task (`11241c21-…`) was not
   re-checked — that database belonged to the abandoned branch's environment;
   the seeded read-model fixtures stand in (named in the contract).
4. **`screeningOverlayError` client mirror** duplicates the backend caps as
   constants (1000/2000) — noted in code comments pointing at the backend
   owners.

## Rubric status

Filled at step 7 (review conversation).

## Intent & assumptions

Test mod + bug fixes per contract. `source=apo` confirmed live again
2026-09-08.

## Known unverified items

- No browser-driven UI pass (deviation 3).
- Backend screening-cap tests were written by the Phase 4 delegate but first
  executed by the lead in the Phase 4 `make verify-fast` gate (the delegate
  was barred from the shared test DB) — they pass there and in the exit gate.
- Codex's own pytest run failed on DB provisioning in its sandbox; the lead
  re-ran the S2 test files against the proper test DB (100 passed).

## Public safety

Request log redacted; record titles/ids are public Overton metadata. No
source text, credentials or traces in evidence.

## Review handoff (step-7/8 inputs)

- Executor provenance: S1 + S3 fast-worker (lead briefs, lead-reviewed
  diffs); S2 Codex (write-capable brief, lead-reviewed diff, lead-run tests);
  S4 prompt text lead-only. Design-stage adversarial review NOT re-run
  (owner-approved re-apply of reviewed designs — recorded in the contract);
  the four original 038 findings are baked into the S1 spec.
- Adjudication items: the four flagged deviations above.
- **Knowledge candidates:**
  - Re-apply slices should carry a rename table in the contract; the 038→039
    tree moved four things the old plans cited (`task_plan.py`, `agent.py`,
    `evidence_search/`, `_task_card_claims`) and two agents would have edited
    ghosts without it.
  - The planner sees current constraints via `_render_scope_constraints`
    (`agent.py`) — any new `ScopeConstraints` field is invisible to
    re-planning turns until that renderer gains a branch; the original 038
    plan missed it and only the re-apply scout caught it.
  - `geographyFromConstraints` derives the overlay's geography by
    string-slicing a `scopeChips` chip — display edits silently change edit
    behaviour; pin with a paired `displayedGeography` test.
  - Delegates cannot share the single Postgres test DB (repo landmine): brief
    exactly one agent as the DB owner and run everyone else's backend tests
    serially at the phase gate.
  - Direct `uv run pytest` on api tests fails by design — the conftest guards
    against the dev DB; use `make test`/`verify-fast` (which reset and target
    `policy_atlas_test`) or export the Makefile's `TEST_DATABASE_URL`.

## Deferred work

Recorded in [docs/deferred.md](../../deferred.md): the APO removal path
(unchanged from 038, updated names) and that planning chat now teaches APO
via `planner_v11`.
