# Verification: 031-search-count-honesty

Evidence for one slice. Public-safe: no secrets, no raw source text, no credentials.
Filled at step 6. **Review findings** and **Rubric status** are added after the review
stack (step 7).

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (build-open baseline, `22f2bae`) | pass | Green before any code change, so no failure is misattributed to this slice. |
| `make verify-fast` (phase 1 gate, `1f36fb6`) | pass | 2132 backend tests, mypy 263 files, ruff. |
| `make verify` (phases 2–3 gate, `d461804`) | pass | 2134 backend, 243 frontend, mypy, ruff, eslint, `drift-check: OK`. |
| `make verify` (step-6 exit) | pass | See § Step-6 exit run. |
| `make verify` (step-7 baseline, before review fixes) | pass | exit 0 — 2134 backend, 243 frontend, mypy 263 files, ruff, eslint, `drift-check: OK`. Independently re-run by the contract-verifier lane with matching numbers. |
| `make verify` (step-7 exit, after the review fixes) | pass | exit 0. |

The plan's gate map allowed phases 2 and 3 to share one gate. Phase 1 gated on
`verify-fast` as planned. No gate was added or downgraded.

`drift-check: OK` is the evidence for the contract's "OpenAPI field *set* unchanged"
constraint: the read-model shapes are untouched, only how the numbers are filled.

## Checks beyond the build

**Deterministic tests** — six new, all passing:

| Test | Invariant |
|---|---|
| `tests/runtime/test_steering_lattice.py::test_p1_bundle_backend_counts_sum_to_the_acquired_headline` | 1 (defect 1a) |
| `tests/runtime/test_steering_lattice.py::test_p1_bundle_scopes_queries_to_one_run_while_p2_spans_every_round` | 2 (defect 1b) + P2 regression guard |
| `tests/runtime/test_steering_lattice.py::test_p1_bundle_without_an_acquire_run_reports_absence_not_zeros` | Honest absence when no acquire run is recorded |
| `tests/api/test_read_models.py::test_coverage_backend_results_sum_query_hits_across_every_round` | 3 (defect 2) |
| `tests/api/test_read_models.py::test_landscape_geography_residual_makes_every_scope_add_up` | 4 (defect 3), both scopes |
| `src/ui/charts/EvidenceDistributionChart.test.ts` → `normaliseGeographies` | 4 — the residual survives the frontend normaliser |

Added by the review stack (2026-08-13):

| Test | Finding it closes |
|---|---|
| `tests/runtime/test_search_rounds.py::test_p1_at_round_two_reports_only_that_round` | R3 — invariants 1 and 2 on a real two-round walk |
| `tests/runtime/test_steering_lattice.py::test_p1_bundle_is_empty_when_the_boundary_run_is_not_the_successful_acquire` | R1 — a failed round's P1 shows absence, not the previous round's numbers |

Invariant 5 ("unchanged") is covered by the existing suite: the read-model golden test
and the funnel/plan-in-motion assertions were not edited and stay green.

**Correction (review stack, 2026-08-13).** The step-6 draft named this assertion as the
check of the *by-construction* claim against real data:

```
assert real["acquired"] == sum(stats["acquired"] for stats in real["by_backend"].values())
```

The contract verifier ran that walk and found the payload is `acquired = 0`,
`by_backend = {}` — so the assertion evaluates `0 == sum(())` and would pass however
acquire computed its headline. The property is real (`acquire.py:911-921`) but that line
did not pin it. The evidence now comes from
`tests/runtime/test_search_rounds.py::test_p1_at_round_two_reports_only_that_round`, which
runs a genuine two-round standard walk (round 1: 9 queries / 18 acquired; round 2: 3 / 6)
and asserts a non-zero backend line on round 2.

**Manual / browser — NOT DONE.** See § Known unverified items. This is the one contract
acceptance check outstanding.

## End-to-end command

Backend, the two new read-model tests:

```
cd backend && make reset-test-db && \
  DATABASE_URL="postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas_test" \
  uv run pytest tests/api/test_read_models.py \
    -k "geography_residual or coverage_backend_results" -q
```

Full gate from the repo root: `make verify`.

Tests refuse to run against the dev database by design (`tests/conftest.py`), so the
`DATABASE_URL` above is required when invoking pytest directly rather than via `make`.

## Diff summary

Four defects, three code areas. No schema change, no new dependency, no public field
renamed.

**Defect 1a — P1 backend counts always zero.** `p1_bundle` summed `backends[].count` on
the coverage record, a key acquire never writes (`acquire.py:959` writes only `backend`,
`trust_class`, `mode`, `depth`), so the sum was structurally 0. It now reads the acquire
run's own `component.completed` payload. Chosen over recomputing from PSS rows because
`acquire.py:911` *defines* the headline `acquired` as `sum(by_backend[*]["acquired"])` —
reading it makes invariant 1 hold by construction instead of by a parallel count that
could drift. It also matches the module's own stated rule ("no recomputation of anything
a component already computed").

**Defect 1b — one-round headline beside every round's queries.** `_executed_queries`
filters by scope only. `p1_bundle` now passes the acquire run id and gets that round's
queries. The run id threads in from `successful_runs["acquire"]`, which the walk moves to
the newest run (`runner.py:1072` — the step-6 draft cited `runner.py:192`, which is the
unrelated `REPLACEMENT_RERUNS` comment). The seam already existed: P2 next door does the
same with `characterise`. **Review-stack addition:** `successful_runs` is written *only*
on the success path, so `p1_bundle` now also gates on the boundary's own run id — see
finding R1 below.

**Defect 2 — mixed grain in "Where I looked".** `coverage_out` read the newest coverage
record and passed its `acquired_by_run_id` alone. It now passes every acquire run that
wrote a coverage record for the project (`_acquire_run_ids`), so `results` is cumulative
like `relevant`. `relevant` attribution is deliberately untouched. Copy changed from
"72 results · 200 relevant" to "query hits" / "kept after screening" plus one line saying
hits are per call and pre-dedupe — the contract forbids implying a subset relation.

**Defect 3 — country bars summed below relevant.** Sources with no publisher country were
dropped. They now land in a `"Not reported"` residual, counted inside the loop over
`base_rows`, which `landscape_out` has *already* narrowed by scope. That placement is why
the cited scope is correct with no special-casing. Authorship countries are still never
substituted. Both charts now state they show publisher country.

**Docs.** `docs/deferred.md`: the display half of the multi-round blemish is discharged;
the `re_searched_still_thin` **trigger** and the timeline round labels stay open and are
now called out as separate from the display bundle. The P1 sample-titles note is
untouched, as the contract required.

### Deviations to adjudicate

1. **Phase 1 executor was `lead`, not `codex`** (plan gate marked `codex`). Changed by
   the owner on 2026-08-13 mid-build. Recorded in `plan.md`. **Family-flip consequence:
   phases 1–3 have no non-Claude author, so the review stack carries the whole
   heterogeneous-peer burden for this slice.**
2. **Counts read from the `component.completed` payload**, where plan D1 said "PSS rows
   or the events of the current acquire run". The event payload is durable data for that
   run, so this sits inside D1, but it is narrower than what D1's wording implies and is
   flagged rather than folded in silently.
3. **The contract's branching note was wrong** and was corrected before building: `dev`
   already carried the multi-round code, and has since absorbed the hotfix (PR #46) and
   task 029 (#47). No stacking was needed.

## Intent & assumptions

- "One acquire run" is `successful_runs["acquire"]`, on the documented assumption that
  the walk's reference moves to the newest run. Pinned by the P1 scoping test.
- `_acquire_run_ids` is project-wide, not scope-filtered, matching the contract's wording
  ("all the acquire runs of the project"). `coverage_out` itself takes only a project id.
- Query hits can exceed unique sources. That is honest and the copy now says so.

## Known unverified items

- **The contract's manual browser check has not been run.** It asks for one deep run, or
  one standard run with more than one round, checking the check-in, "Where I looked", the
  geography residual and the funnel. It needs the app running against a live model route,
  and `AGENTS.md` records staging's OpenAI quota as exhausted since 2026-07-28. Local
  stub backends would not exercise a real multi-round walk, so running one would not be
  the evidence the contract asked for. **This is a genuine gap in acceptance, not a
  waiver — the owner should decide whether to run it before merge or accept the
  automated evidence.** Everything else in the contract's acceptance list is green.
- The `"Not reported"` share on a real deep run is unmeasured. The contract expects it to
  be large; nothing here proves how large.

## Public safety

Safe. No secrets, credentials, traces or raw source text. Test fixtures use invented
titles ("No country reported", "Selected trial") in the existing pattern. The new copy
strings are user-facing product text.

## Review findings (step 7, 2026-08-13)

### Lanes run

| Lane | Result |
|---|---|
| Contract verifier (`contract-verifier`, pinned Opus, read-only) | 1 MAJOR, 7 MINOR, 3 NOTE. Re-ran `make verify` independently: green |
| `/code-review` at `medium`, scoped to `backend/src backend/tests frontend/src` | 5 findings (1 medium, 4 low) |
| `/security-review` | **No HIGH/MEDIUM findings** |
| Adversarial (`deep-reasoner`, read-only) | 1 MAJOR, 4 MINOR, 6 NOTE |
| `make verify` after fixes | green |
| `/simplify` | **Not re-run.** `/code-review` ran the reuse/simplification/efficiency/altitude angles and their findings were adjudicated below; a second same-family cleanup pass over the same diff duplicates it |

**⚠️ Family-flip gap — the heterogeneous pair did not happen.** The Codex CLI is not
installed in this environment, so `/codex:adversarial-review` and a `codex-rescue` brief
both failed. Combined with deviation 1 (the owner moved phases 1–3 from `codex` to
`lead`), **no non-Claude reviewer has read any line of this slice** — neither as author
nor as reviewer. The adversarial lane was substituted with a same-family
`deep-reasoner` given an explicitly anti-deferential brief; it found the MAJOR below, so
the lane earned its place, but it is reviewer *count*, not family diversity. The owner
should weigh this when deciding review depth at step 9.

### Adjudication

**Adopted and fixed:**

- **R1 (MAJOR, adversarial) — P1 showed the previous round's numbers when acquire failed
  on round ≥2.** `successful_runs[component]` is written only on the success path
  (`runner.py:1072`), but the failure path still presents the boundary
  (`runner.py:1211`). So a round-2 acquire failure rendered **round 1's** counts and
  queries beside a blank chip. Pre-slice the card was visibly broken (all zeros);
  post-slice it was plausibly wrong, which is worse at the steer point named
  "search exception". Fixed by threading `boundary_run_id` into `_build_bundle` and
  falling back to the already-tested honest-absence branch when the boundary is about a
  different run. Convergence note: the contract verifier traced the *success* path and
  correctly found it sound — the two lanes do not disagree, they covered different paths.
- **R2 (medium, `/code-review`; MINOR-4, contract verifier) — non-deterministic query
  order.** The `search.executed` select in `_backend_details` had no `ORDER BY`. Spanning
  several runs made that load-bearing, and the slice's own new test asserted an exact
  order that only held by accident of physical row order. Added
  `.order_by(event_log.c.sequence)`; corrected the `_acquire_run_ids` docstring, which
  claimed a determinism the consuming query did not deliver.
- **R3 (MAJOR-1, contract verifier) — the multi-round P1 leg had no empirical evidence.**
  `plan.md` § Phase 1 step 4 asked for a two-round fixture; the shipped test handed
  `p1_bundle` a run id directly and used a *screen* run as its foil. Added
  `test_p1_at_round_two_reports_only_that_round`, a genuine two-round standard walk. It
  asserts the two cards **partition** the scope's calls rather than being disjoint —
  disjointness is wrong, because the base query is legitimately re-issued each round.
  Mutation-checked: disabling the `run_id` filter makes it fail.
- **R4 (MINOR-3, contract verifier; MINOR-3, adversarial) — the cited-scope assertion was
  tautological.** The countryless source was never cited, so the test would have passed
  had the residual been skipped at `scope="cited"` entirely. Inverted the fixture: the
  cited source is now the countryless one, so the cited scope must draw the residual.
- **R5 (MINOR-6, contract verifier) — a render site contradicted the contract.**
  `ArtefactOutline.tsx` told the user the map showed "Publisher and author-affiliation
  geography". `_geography` has never read an affiliation, and the contract's review focus
  names exactly this substitution. Rewritten to match the other two sites.
- **R6 (low, `/code-review`) — `_executed_queries` rebound its loop variable.** Harmless
  before; now the new `run_id` guard reads `entry["run_id"]` off the raw row, so
  correctness depended on staying above the rebind. Removed the rebind.
- **R7 (MINOR-2, contract verifier) — verification.md overstated its own evidence**, and
  **R8 (MINOR-8 / adversarial 4) — mis-anchored line cite.** Both corrected in place
  above; the original claims are quoted so the change is auditable.
- **R9 (MINOR-5, contract verifier) — rubric item 7 was not satisfied.** The
  authorship-country deferral was admitted in verification.md but never written to
  `docs/deferred.md`. Now entered.
- **R10 (MINOR-7, contract verifier) — deferred.md over-claimed.** "The display half is
  DISCHARGED" was too broad: `coverage_out` still reads only the newest coverage row for
  the pane's `sentence`, `base` and `backends` name list. Entry narrowed to "the
  per-round *counts* are discharged" with the remainder itemised.

**Adopted as deferred (recorded in `docs/deferred.md`, not fixed here):**

- **R11 (low, `/code-review`; MINOR-2, adversarial; NOTE-11, contract verifier) —
  `_acquire_run_ids` is project-wide, not scope-filtered.** Three lanes converged. A
  re-planned project mints a new `evidence_scope`, so the pane would sum a superseded
  question's rounds beside a sentence from the current question's row. **Declined as a
  code fix here** because the contract's own § Scope wording is "all the acquire runs of
  the **project**" — changing the grain is a contract decision, not a review-stack fix.
  Deferred with the one-clause fix named.
- **R12 (low, `/code-review`; NOTE-9, contract verifier) — the drawn chart truncates.**
  Invariant 4 holds in the payload, where the tests assert it; the renderers cut to the
  top 12 / top 8. Pre-existing, but the residual is typically large and now takes a slot.
  Deferred.

**Adopted as accepted behaviour (no change):**

- **R13 (NOTE-10, contract verifier; 9, adversarial; low, `/code-review`) — a chart now
  renders where none did.** `geographies` is non-empty whenever any relevant source
  exists, so a corpus with no reported venue countries draws a single "Not reported" bar,
  and `ArtefactOutline`'s section can appear where it previously returned `null`. This is
  the contract's intended honest absence, not a blemish. `landscape_out` still returns an
  empty `LandscapeOut()` before the loop on an empty population, so the key is never
  present at population 0. Worth naming because **no pre-existing test asserted
  `geographies` at all** — `make verify` green was not evidence of no regression here
  before this slice's tests.
- **R14 (11, adversarial) — `_acquired_by_backend` re-implements `runner.py`'s
  `_find_component_payload`.** `runner` imports `steering_bundles`, so direct reuse would
  cycle. Declined. Related lead observation: `events.read_for_run` materialises every row
  of the run to extract one payload, where the sibling `steering_triggers.py` does the
  same job with `order_by(sequence.desc()).limit(1)` in SQL. Left as-is — one bundle
  build per steer point is not a hot path — but noted as the cheaper idiom.

**Deviations from the build, re-examined (each confirmed explicitly):**

1. **Phase 1 executor `lead`, not `codex`** — confirmed recorded in `plan.md`. Adopted as
   the owner's mid-build call. Its consequence is the family-flip gap flagged above, which
   is now the slice's main residual review risk.
2. **Counts read from `component.completed`, narrower than plan D1** — confirmed as-built
   and inside D1's hard constraint ("do not depend on `backends[].count`"). One
   consequence the build did not state, surfaced by the contract verifier: for an acquire
   run whose payload carries no `by_backend` (older event rows), the card shows **no
   backend line**, where a PSS-based recount would have worked retroactively. Adopted —
   honest absence is the right failure mode — but named for the owner.
3. **Contract branching note corrected before the build** — confirmed: `dev` is an
   ancestor of HEAD and carries the multi-round code. No stacking was needed.

**Convergence summary.** R2, R4 and R11 were found independently by two or three lanes —
highest confidence. R1 was unique to the adversarial lane and R3, R5, R9 and R10 unique to
the contract verifier; those two lanes each justified their cost. `/code-review` uniquely
caught R6 and the truncation reach of R12. The security lane found nothing, which is the
expected result for a read-model slice with no schema, auth or egress change — it is
recorded as a negative result, not skipped.

## Review handoff (step-7/8 inputs)

- **Executor provenance:** phases 1–3 authored by the Claude lead. See deviation 1 — the
  family flip has not happened yet for any product code in this slice.
- **Adjudication items:** the three deviations above.
- **Design-doc corrections made before the build** (contract/plan/rubric, commit
  `844b51f`): the contract's stated cause for defect 2 was wrong (it claimed acquire
  overwrites the coverage row; acquire inserts one row per run and `coverage_out` reads
  only the newest); a Terms row described coverage records as one-per-backend rather than
  one-per-run; defect 3 listed two country sources where `_geography` checks three; and
  invariant 4 was unachievable as written because `landscape_out` has a `cited` scope
  that cannot sum to the funnel. A reviewer comparing the built code to the *original*
  contract text will find these as apparent divergences — they are corrections.

### Knowledge candidates

- **Prefer the producing component's persisted summary over re-deriving a count in a read
  model.** Acquire defines its headline as the sum of its per-backend counts, so reading
  that payload makes the display invariant hold by construction. A parallel recount would
  have been a second source of truth for the same number — the exact shape of the bug
  being fixed. Generalises well beyond this slice.
- **A shared read helper can be right for one caller and wrong for another.**
  `_executed_queries` spanning every round is correct for P2's coverage picture and wrong
  for P1's one-round card. The fix is an opt-in narrowing plus a test asserting *both*
  halves, or a later change quietly narrows the other caller.
- **Count a residual after the population is narrowed, not before.** Putting the
  `"Not reported"` increment inside the loop over the already-scoped rows made the "adds
  up" invariant true at the `cited` scope for free. Placement, not extra branching, was
  what made it general.
- **Design docs drift from code in ways that survive careful proofreading.** Four factual
  errors — including an invariant that no implementation could satisfy — were only found
  by reading the code the docs described. Prose review would not have caught any of them.
- **Fixture gotcha:** the runtime walk's stub search acquires 0 *new* sources, because the
  seeded project already holds the records the stub returns. An assertion needing a
  non-zero acquire headline must seed one; `assert headline > 0` off a plain walk fails.

## Rubric status (after step 7)

| # | Status |
|---|---|
| 1 contract satisfied | ✅ code · ⚠️ the manual browser check is outstanding (below) |
| 2 `make verify` + declared checks | ✅ automated (re-run green after fixes) · ⚠️ manual outstanding |
| 3 no ungated approval-gated change | ✅ `drift-check: OK`, no migration, no dep/CI/config change |
| 4 no generated file or secret hand-edited | ✅ `git diff dev...HEAD -- frontend/src/api/gen` empty |
| 5 no test deleted, skipped or weakened | ✅ — and the two tests the stack *strengthened* (R3, R4) are recorded above with the reason |
| 6 verification evidence recorded | ✅ |
| 7 gaps and deferred items listed | ✅ after R9 (was ✗ at step 6 — the authorship-country deferral was admitted here but absent from `docs/deferred.md`) |
| 8 review stack ran | ✅ with one recorded exception: the heterogeneous half could not run (Codex CLI absent). See the ⚠️ above |
| 9 P1 counts and query scoping | ✅ after R1 and R3 |
| 10 Where I looked cumulative, honest copy | ✅ after R2 |
| 11 geography residual, both scopes, no authorship country | ✅ after R4 and R5 |
| 12 funnel and plan-in-motion unchanged | ✅ nothing in the diff can move them |
| 13 multi-round fixture covers 9 and 10 | ✅ after R3 (was partial — item 10 only) |
| 14 deferred.md rewrite | ✅ after R10 |

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md): the `re_searched_still_thin` P1
trigger's boundary visibility, timeline round labels, P1 sample-title scoping, per-query
relevance, authorship-country geography (**now written up**, R9), and two seams the review
stack added — the project-wide vs question-scoped grain of `_acquire_run_ids` (R11) and
the top-12 / top-8 chart truncation that lets the *drawn* bars sum below the population
even though the payload adds up (R12).
