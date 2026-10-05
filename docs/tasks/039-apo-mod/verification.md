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
  `publisher_source: apo` (CLI plan render); re-planning turns see the field
  through the `PlanDraftWire` attachment (correction at step 7 — the build
  wrote "on re-planning turns" here, but the render branch feeds only the
  dev CLI approval prompt at `agent.py:1021`).
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

Four slice commits on `task/039-apo-mod` after the docs commit
(count corrected at step 7), plus the step-6 evidence commit:

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

## Review findings (step 7)

Stack run 2026-09-08 in a fresh conversation. Lanes: contract-verifier
(pinned Opus, read-only) · `/code-review medium` (Claude half of the
heterogeneous pair) · Codex adversarial (read-only rescue brief; anchored the
Claude-written S1/S3/S4 surfaces per the family flip — S2 was Codex-built, so
the Claude lanes anchored it) · security lane (`/security-review` flow — the
`agent-skills:security-auditor` agent type is not installed in this
environment; recorded as the fallback) · live-trace content review by the
lead (the live-check script drives the real chain
`TaskPlan → to_filters → validate_scope_filters → to_wire_params →
OvertonLiveBackend` with asserts matching the recorded log).

Gate note: the first step-7 `make verify` failed with 86 red tests in
untouched steering files — cross-checkout interference on the shared
`policy_atlas_test` DB (a second checkout ran pytest concurrently). Green on
an isolated `policy_atlas_039_test` DB (backend 2543 + frontend 583, exit 0).
This confirms the shared-test-DB knowledge candidate.

**Adopted (fixed in the review commit):**

- **Codex (major):** a PATCH that succeeded but a run start that failed left
  the applied overlay local; a later Start could replay it over newer
  server-side edits. Fixed: the overlay clears on PATCH success
  (`usePlanStart.onOverlayApplied`), not only on full start success.
- **/code-review (confirmed):** a planner-emitted `publisher_source` other
  than exactly `"apo"` (e.g. `"APO"`) 500'd the planning turn —
  `PlanDraftWire` is loose `str` but `ScopeConstraintsDraft` narrows to
  `Literal["apo"]` through an unguarded `model_validate`. Fixed:
  `_draft_from_wire` normalises the taught spellings and drops anything else.
- **/code-review (confirmed):** the dirty-only prune dropped an unchanged
  geography from a scope-changing save, so the backend nulled the
  now-incompatible constraint instead of recompiling it (silent loss of e.g.
  a GB restriction on an academic→grey switch). Fixed: a scope-changing
  patch always re-sends the displayed geography.
- **Convergent (/code-review confirmed + contract-verifier F2 as
  plausible):** the S2 prose-containment gate was vacuously true on an empty
  resolved list (returned an empty card instead of falling back) and treated
  a write-path `span: null` record (title-bound claim) as collision
  evidence, dropping the claim. Fixed: `if result and all(trusted)`, with
  explicit-null span entries trusted; three new DB-free unit tests, one of
  which also exercises the fallback's span sort (closing the verifier's
  untested-sort finding).
- **/code-review (confirmed minor):** a dirty overlay whose pruned body was
  empty still sent `PATCH {}`, minting a plan version. Fixed: empty body
  skips the PATCH and clears the stale keys.
- **Codex (minor):** the client cap mirror counted UTF-16 units where the
  backend counts code points; fixed (`charCount`), and the 50-rule list cap
  is now mirrored too (Codex's second minor).
- **Convergent (Codex-adjacent + /code-review + contract-verifier F9):**
  "Discard edits and start" rendered on every start notice, including ones
  with nothing to discard. Fixed: gated on a dirty overlay.
- **Contract-verifier F8:** `to_filters` wrote `filters["overton"]` twice in
  sequence (validator-guarded, not structural). Fixed with `elif`.
- **Contract-verifier F1/V1/V2 (medium, docs):** the claimed mechanism for
  planner visibility of `publisher_source` was wrong (CLI-only render branch
  vs the real `PlanDraftWire` path) — corrected above and in the knowledge
  candidate. **V4:** stale commit count corrected.
- **Contract-verifier F6:** the deferred.md removal note missed six
  surfaces — extended.

**Declined / deferred (with reasons):**

- **Contract-verifier F4** (ordinal rebinding also fires when
  `result_claim_id` is absent, vs the 034 "absent ⇒ null" note): declined —
  `result_ordinal` is the write side's source of truth (`result_claim_id`
  is derived from it at `synthesise.py:5026`), so ordinal recovery on
  absence matches write semantics. /code-review's verifier independently
  cut the same candidate as no-worse-than-before.
- **Contract-verifier F5** (live-check script not in the repo): declined
  committing it — one-off test-mod tooling the removal path would have to
  carry; the recorded URL is independently corroborated (param order is
  byte-identical to `search_live.py`) and the script was content-reviewed
  by the lead this stack.
- **Contract-verifier F7** (raw Pydantic validation dumps can surface
  verbatim in the Start-failure notice): contract-satisfying ("the API's
  real message"); left as an owner call — named in the PR's review focus.
- **/code-review cleanup** (consolidate the three key-lists in
  `planOverlay.ts`): declined the refactor — the per-key `undefined` guards
  are TypeScript narrowing, and the dirty logic is already shared via
  `dirty()`/`serverDisplayedValue`; noted as a seam in deferred.md.
- **/code-review low** (mid-year dates display as bare years and prune as
  no-ops, so the day component can't be seen or reset): deferred —
  deferred.md entry.
- **Security lane:** no findings above threshold (APO value is a hardcoded
  literal behind three validation layers, an allowlist and percent-encoding;
  React text nodes only; parameterized SQL; fail-closed caps).

Unique-to-one-lane catches that justify each lane: the 500 and the
geography-loss regression (`/code-review` only), the overlay-replay state
bug (Codex only), the false-mechanism docs claim and the vacuous-guard seed
(contract-verifier). Fake-done check on the review fixes: no tests
relaxed/deleted (all changes additive; 119 backend + 50 frontend targeted
tests green, full gate re-run below).

## Rubric status

Adjudicated at step 7:

1. **Holds, as amended** — the 038 rubric holds at the renamed paths with
   two 039-contract supersessions (F10 adjudication): 038.3 "no prompt
   change" is superseded by S4 (owner-approved `planner_v11`), and 038.10's
   review stack is this one. Live `source=apo` evidence recorded (run
   2026-09-08); allowlists widened by exactly one key each (verifier-checked,
   with a negative test).
2. **Holds** — uniqueness composition test; collision recovery + healthy
   alias tests; hardened this step (empty-resolution fallback, explicit-null
   trust, sort test).
3. **Holds** — merge/prune tests incl. the APO Sources-only save; honest
   Start copy (negative-asserted); Discard (now gated on dirty); screening
   +/− list; 1000/1001 boundary both sides; 50 and 2000 caps unchanged and
   now client-mirrored.
4. **Holds** — v11 pinned (hash recomputed independently by the verifier);
   prompt content tests; geography-token router tests green.
5. **Holds** — `make verify` green at exit and re-confirmed at step 7 on an
   isolated DB; `make drift-check` OK (verifier-run).
6. **Holds** — zero stale-vocabulary hits in added lines (lead + verifier,
   independent greps).
7. **Holds** — this file; removal + v11 notes in deferred.md (extended at
   step 7).
8. **Holds** — this stack: fresh conversation, three Tier-3 lanes plus
   security and live-trace; no design-stage adversarial pass (owner ruling
   in the contract Status block).

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
  - The planner sees current constraints on re-planning turns via the
    `PlanDraftWire` attachment (`planner_prompt.py`), NOT via
    `_render_scope_constraints` (`agent.py`) — that render branch feeds only
    the dev CLI approval prompt. A new `ScopeConstraints` field needs the
    wire field to be visible to re-planning turns; the CLI render branch is
    a separate, optional surface. (Mechanism corrected by the step-7
    contract verifier; the build had recorded the CLI renderer as the
    planner-visible path.)
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
