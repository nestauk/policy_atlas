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

Invariant 5 ("unchanged") is covered by the existing suite: the read-model golden test
and the funnel/plan-in-motion assertions were not edited and stay green.

One assertion is worth naming because it checks the *by-construction* claim against real
data rather than a fixture: in the first test,

```
assert real["acquired"] == sum(stats["acquired"] for stats in real["by_backend"].values())
```

runs against a genuine walk's acquire payload. It pins the property that makes invariant 1
hold — acquire's headline **is** the sum of its per-backend counts.

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
the newest run (`runner.py:192`) — exactly the round that just finished. The seam already
existed: P2 next door does the same with `characterise`.

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

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md): the `re_searched_still_thin` P1
trigger's boundary visibility, timeline round labels, P1 sample-title scoping, per-query
relevance, and authorship-country geography (not yet written up — see the closing note in
the task conversation; the data is retained in the slim authorships, so a later slice
needs no migration).
