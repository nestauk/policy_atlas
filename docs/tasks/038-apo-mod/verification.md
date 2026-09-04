# Verification: 038-apo-mod

Evidence for the APO-only test mod (contract R1–R3). Filled at step 6;
Review findings + Rubric status follow at step 7.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (baseline, pre-build) | pass | clean base on `task038/apo-mod` |
| `make verify-fast` (phases 1–2 gate) | pass | 2456 backend tests, mypy, ruff |
| `make verify` (phase 3 + step-6 exit) | pass | exit 0; includes `drift-check`, `prompt-guard`, frontend build; frontend 538/538 vitest |

## Checks beyond the build

- **Deterministic tests added** (all pass inside the suites above):
  - `test_orchestration_plan.py` — `publisher_source` compiles to
    `{"overton": {"publisher_source": "apo"}}`; fail-closed matrix rejects it
    with `publisher_country`, with `backend_scope` `academic_only` and `both`,
    and rejects any value other than `"apo"`.
  - `test_orchestrate_country_group.py` — draft→plan round trip keeps the
    field (`build_plan` fold).
  - `test_search_directives.py` — `validate_scope_filters` accepts
    `{"publisher_source": "apo"}` and maps it to wire `{"source": "apo"}`;
    rejects `"xyz"`; unknown keys still raise.
  - `test_planning_router.py` — PATCH `/plan` geography "APO" and
    "Australian Policy Online" set the constraint (200); 422 unless Sources is
    grey literature only; a later country edit clears it; a later scope flip
    to "both" clears it (adversarial finding 1).
  - `planVocabulary.test.ts` — a plan with the constraint renders the chip
    "Geography: APO"; display prefers `publisher_source` over a stray country.
- **Manual / API — live check (contract-pinned scope):** one real Overton
  call through the production chain (plan → `to_filters` →
  `validate_scope_filters` → `to_wire_params` → `OvertonLiveBackend.search`,
  real transport). Logged request (key redacted):
  `GET https://app.overton.io/documents.php?source=apo&squery=What+does+the+evidence+say+about+social+housing+policy+outcomes%3F&min_similarity=0.3&format=json&pp=50&api_key=REDACTED "HTTP/1.1 200 OK"`.
  All 5 returned records carry `source.source_id = "apo"`,
  `source.title = "Australian Policy Online"`, country Australia (sample ids:
  `apo-1effca7d…`, `apo-8a4a7fe4…`). No OpenAlex request was made
  (`backend_scope="grey_lit_only"` filters the backend list —
  `scoped_search_backends`, unit-tested pre-existing behaviour).

## End-to-end command

```
set -a && source backend/.env && set +a && \
uv run --project backend python <scratchpad>/apo_live_check.py
```
(Script content is reproduced in the PR if needed; it only composes public
package functions and prints redacted output.)

## Diff summary

Four commits on `task038/apo-mod` (`be245da` docs, `e1598fc` backend,
`b193d1c` frontend + generated types + prompt-hash, plus this file):

- `ScopeConstraints.publisher_source: Literal["apo"] | None` — mutually
  exclusive with the geography constraints; plan-level guard requires
  `backend_scope="grey_lit_only"`; compiles to the `overton` filter block.
- The key is carried through both flat↔nested fold lists
  (`orchestrate.build_plan`, routers/planning `_draft_from_wire`), the API
  mirror `ScopeConstraintsDraft`, the directive allowlist + validation
  (value pinned to `"apo"`), the wire mapping (`→ source`), and the transport
  allowlist.
- Geography box token "APO" / "Australian Policy Online" sets it (422
  otherwise); any other geography or scope edit clears it.
- `scopeChips` shows "Geography: APO"; `openapi.json`/`types.ts` regenerated
  via `make openapi-sync`.

**Flagged deviations (visible, not drift):**

1. **`prompt_hashes.json` updated for `planner_prompt.py`.** The guard hashes
   the whole module; the change is one schema line in `PlanDraftWire`
   (verified: single added line), named in the approved plan (Phase 1 item 2).
   Prompt text and `planner_v10` are byte-untouched.
2. **Generated-type fallout:** regeneration made `publisher_source` a
   required-but-nullable key in the TS types, so five pre-existing frontend
   fixtures/tests gained a mechanical `publisher_source: null` line.
3. **Live-check shape:** the contract pinned "one plan edited through the UI +
   one acquire round". The plan edit was exercised through the PATCH `/plan`
   route (the exact call the UI makes) plus the frontend display unit test,
   and the acquire leg ran live via script — no browser drive. The owner's
   own Australian test run covers the full UI pass.

## Rubric status

Filled at step 7 (review conversation).

## Intent & assumptions

Test mod only (contract § Goal). `source=apo` is assumed to be the stable
Overton slug for APO — confirmed live 2026-09-04.

## Known unverified items

- No browser-driven UI pass (deviation 3 above).
- The APO token is not understood by the planning chat (`planner_v10`
  untouched — contract § Design, accepted limit).

## Public safety

The request log above is redacted (`api_key=REDACTED`). Record titles/ids are
public Overton metadata. No source text, credentials or traces in evidence.

## Review handoff (step-7/8 inputs)

- Executor provenance: phases 1–3 built by `fast-worker` delegates from
  lead-written briefs; lead reviewed both diffs before commit; adversarial
  contract/plan pass ran via Codex (one light combined pass, owner-ruled) —
  4 findings, all folded in pre-build (see plan.md header).
- Adjudication items: the three flagged deviations above.
- **Knowledge candidates:**
  - The prompt-hash guard fires on *any* edit to a `*prompt*.py` module, and
    wire-schema models (`PlanDraftWire`) live inside one — schema-only changes
    to prompt modules need the hash bump named in the plan up front.
  - A new `ScopeConstraints` field must be added in **four** places to
    round-trip (model, `ScopeConstraintsDraft`, and the two flat↔nested fold
    lists) — the fold lists fail silently (key dropped), not loudly.
  - `openapi-typescript` emits optional-nullable pydantic fields as
    *required*-nullable TS keys, so every fixture literal in the frontend
    breaks on any new constraint field — budget for that sweep.

## Deferred work

- Removal note recorded in [docs/deferred.md](../../deferred.md) § APO test
  mod: on removal, stored plans carrying `publisher_source` must be tolerated
  or re-saved.
