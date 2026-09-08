# Verification: 038-apo-mod

Evidence for the APO-only test mod (contract R1–R3). Filled at step 6;
Review findings + Rubric status filled at step 7 (fresh review conversation,
2026-09-04).

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (baseline, pre-build) | pass | clean base on `task038/apo-mod` |
| `make verify-fast` (phases 1–2 gate) | pass | 2456 backend tests, mypy, ruff |
| `make verify` (phase 3 + step-6 exit) | pass | exit 0; includes `drift-check`, `prompt-guard`, frontend build; frontend 538/538 vitest |
| `make verify` (step-7 pre-review baseline) | pass | exit 0, before any review lane ran |
| `make verify` (step-7 post-fix re-run) | pass | exit 0 with all review fixes + new tests; `make okf-validate` re-run after the step-8 knowledge records (131 concepts, 0 violations) |

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
   required-but-nullable key in the TS types, so six pre-existing frontend
   fixture/test lines across four files gained a mechanical
   `publisher_source: null` entry (count corrected at step 7; all pure
   insertions, no assertion weakened).
3. **Live-check shape:** the contract pinned "one plan edited through the UI +
   one acquire round". The plan edit was exercised through the PATCH `/plan`
   route (the exact call the UI makes) plus the frontend display unit test.
   The live leg was a direct `OvertonLiveBackend.search` call through the
   production filter chain — **not** a full acquire round — so "zero OpenAlex
   requests" (R1) is established statically (`scoped_search_backends` under
   `grey_lit_only`, unit-tested pre-existing behaviour), not observed
   (wording corrected at step 7). The owner's own Australian test run covers
   the full UI pass.

## Review findings (step 7)

Stack run 2026-09-04 in a fresh conversation; `make verify` green before any
lane ran. Four lanes on the slice diff (generated files and `docs/tasks/**`
excluded by pathspec): contract-verifier (pinned Opus, read-only) · security
audit (fresh subagent) · Codex adversarial (read-only, the heterogeneous
anchor for the Claude-built surfaces) · `/code-review medium` (the Claude
half). Plus the lead's live-trace content read (the surviving live-check
script matches the logged evidence exactly) and `make okf-validate` (inside
`make verify`).

**Adopted (fixes applied in this phase):**

1. **Steered runs silently lost the APO restriction** (contract-verifier;
   unique to that lane; the most serious finding). An acquire `filters`
   steering delta replaced `scope_constraints` wholesale via
   `_scope_constraints_from_filters`, which neither maps nor tolerates
   `publisher_source` — silent drop (every later Overton call without
   `source=apo`, R2 broken) or hard fail if the delta echoed the block.
   Fix: `_apply_acquire_delta` carries the field over (tester-pinned, not
   steerable; a conflicting delta fails the plan's re-validation, fail
   closed). Tests added in `test_steering.py`.
2. **Pagination could follow a `next_page_url` that dropped `source=apo`**
   (Codex adversarial, blocker; convergent with the lead's read — the
   contract-verifier's "params are built once so every page carries it" was
   wrong, follow-ups go out verbatim with `{}` params).
   `_validate_overton_next_page_url` now also requires every original wire
   filter param to survive in the next-page URL, else
   `SearchTransportError` (fail closed). Live next-page URLs echo the
   request's params (015 param-pinning §5), so real pagination is
   unaffected; one pre-existing test's stub next-page URL gained its filter
   param to stay realistic (justification for the test edit — rubric item 7).
3. **Planner-emitted junk `publisher_source` crashed the turn** (Codex
   adversarial major + security lane, convergent across families;
   contract-verifier F4 agreed). The field sits in the planner's
   structured-output schema (`PlanDraftWire` → `response_format`) with no
   prompt text behind it; a non-`"apo"` emission (e.g. `"APO"` after a user
   asks for APO in chat) passed the lenient wire model, then raised an
   uncaught ValidationError at `_draft_from_wire` (`planning.py:439`) — 500
   and a stuck pending transcript turn. Fix: a wire-model validator coerces
   any non-`"apo"` value to `None` — the chat doing nothing is the
   contract's accepted behaviour; a genuine `"apo"` emission still works.
   Second `prompt_hashes.json` bump (schema-only again; prompt text and
   `planner_v10` still byte-identical).
4. **CLI approval render omitted the constraint** (`/code-review` CONFIRMED;
   contract-verifier F8). `_render_scope_constraints` showed an APO plan as
   unrestricted on the CLI approval surface — the same silent-omission class
   R3 exists to prevent. Fix: a `publisher_source` render branch + test.
5. **The 422's "pick grey literature first" hint never reached the tester**
   (contract-verifier F2). The API wraps router 422 details in its error
   envelope, but `planStart.ts` discarded the message for non-conflict
   errors. Fix: for 422s the envelope message is shown verbatim; backend
   test now asserts the message text, frontend test asserts the envelope
   survives onto the thrown error. (Small frontend touch beyond the
   contract's listed files — same class as the plan-authorized additions;
   flagged here rather than silently landed.)
6. **Cleanups** (`/code-review`): the `_validate_overton_block` branch now
   uses the existing `_single_enum_value` helper with a declared
   `OVERTON_PUBLISHER_SOURCES` constant (audit-greppable like its
   siblings); `_geography_constraints`' six return points now spread one
   `_GEO_CONSTRAINT_RESET` dict (an omitted key silently survived the
   caller's `constraints.update()` merge); the two byte-identical
   clear-tests are parametrized.
7. **Coverage gaps** (Codex minor + contract-verifier): added
   PATCH → GET `/plan` persistence test, planner-wire coercion tests, and
   the pagination fail-closed pair.

**Adjudicated, no code change:**

- **Flagged deviation 1** (prompt-hash bump): adopted as-is — verified the
  diff is exactly one schema line, no prompt text. The review noted the
  sharper framing (contract-verifier F3): `PlanDraftWire` is the model-facing
  `response_format` schema, so "no LLM-bearing change" in the contract was
  too strong — the planner sees the field name every turn. Recorded as a
  knowledge candidate; made safe by fix 3.
- **Flagged deviation 2**: adopted; count corrected (6 lines, 4 files).
- **Flagged deviation 3**: adopted with corrected wording (see above); the
  contract's pinned browser pass remains with the owner's Australian run.
- **Contract § Scope text vs diff** (contract-verifier F6): `orchestrate.py`
  (fold list) and `api/contract/planning.py` (API mirror) are outside the
  contract's file list but were explicitly authorized by the approved plan's
  adversarial findings 2–3; amendment note added to contract.md.
- **`to_filters` overwrite shape** (contract-verifier F9, Codex sound-note):
  `filters["overton"] = {...}` clobbers a sibling block but the
  mutual-exclusivity validator forbids the only co-occurring case — declined
  as consistent with the file's existing `publisher_country` line.
- **Single-point value pin** (security lane, info): the `"apo"` value
  allowlist lives in `_validate_overton_block` only; noted in the
  deferred.md removal entry for any graduation slice.
- **`/code-review` PLAUSIBLE on the 422-swallow being "silent not-ready"**:
  superseded — the actual failure was the crash in fix 3; its schema-exposure
  point is folded into the deviation-1 adjudication above.
- **`/simplify` not run separately**: `/code-review`'s cleanup angles ran and
  their fixes were applied (item 6); a second same-family cleanup pass would
  duplicate it.

**Refuted by the lanes themselves** (recorded for lane accounting):
`/code-review` killed three of its own candidates (steering path
unreachability claim, `_drop_scope_incompatible_geo` duplication,
`scopeChips` ternary); the security lane returned clean bills on fail-closed
integrity, injection, egress scope, error-path leaks and secrets (evidence
doc greps clean, `api_key=REDACTED` confirmed).

Post-fix: `make verify` re-run green (see Commands run).

## Rubric status

1. ☑ R1/R2/R3 — R2 now holds on steered runs and follow-up pages too
   (fixes 1–2); R3 on both the web plan document and the CLI render (fix 4).
2. ☑ `make verify` green (pre-review baseline + post-fix re-run); live check
   evidence above (scope corrected in deviation 3).
3. ☑ No approval-gated change beyond the contract (review fixes stay inside
   the same surfaces; no new deps/CI/schema/prompt text; the second hash
   bump is schema-only).
4. ☑ `openapi.json` / `types.ts` regenerated, `drift-check` green (no API
   shape change in the review fixes).
5. ☑ Allowlists: still exactly one key each; the value pin moved into the
   declared `OVERTON_PUBLISHER_SOURCES` constant (same single value).
6. ☑ 422 with a clear message — now asserted in test and surfaced in the UI.
7. ☑ No tests deleted/skipped/weakened; the one modified stub is justified
   in finding 2 above; fake-done sweep of the review fixes: none introduce
   relaxed tests, swallowed errors, stubs or fake renames.
8. ☑ This document.
9. ☑ deferred.md removal note (inventory completed at step 7).
10. ☑ The Tier-3 stack ran (this section); no waiver needed.

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
  - A new `ScopeConstraints` field must be added in **seven** places to
    round-trip everywhere (count corrected at step 7 — the build's "four"
    missed three): the model, `ScopeConstraintsDraft`, the two flat↔nested
    fold lists, `steering._scope_constraints_from_filters` (steering deltas
    rebuild the block wholesale), `orchestrate._render_scope_constraints`
    (CLI display), and the geography reset dict in `routers/planning.py`.
    The fold lists, the steering mapper and the render all fail silently
    (key dropped / not shown), not loudly.
  - Any field on `PlanDraftWire` is **model-facing**: the wire model is the
    planner's `response_format` schema, so "no prompt change" does not mean
    "no LLM-visible change" — an undescribed field invites junk emissions;
    pin or coerce at the wire model.
  - `openapi-typescript` emits optional-nullable pydantic fields as
    *required*-nullable TS keys, so every fixture literal in the frontend
    breaks on any new constraint field — budget for that sweep.

## Deferred work

- Removal note recorded in [docs/deferred.md](../../deferred.md) § APO test
  mod: on removal, stored plans carrying `publisher_source` must be tolerated
  or re-saved.
