# Implementation plan: 031-search-count-honesty

> **Status:** approved 2026-08-13 · owner. The contract is approved at the same
> date. The executor for each phase is below.

## Context

A deep search runs a maximum of three rounds. One round is one acquire run plus
one screen run. Several numbers in the UI count different populations, and one
number is always zero.

The contract names four defects. Read [contract.md](contract.md) § Audit for the
cause of each defect, and § Terms and screens for the vocabulary that this plan
uses. This plan does not repeat those definitions.

| Defect | Screen | Fixed in |
|---|---|---|
| 1a — the backend counts are always zero | P1 check-in | Phase 1 |
| 1b — the count covers one round, but the query list covers every round | P1 check-in | Phase 1 |
| 2 — `results` and `relevant` use different grains | Where I looked | Phase 2 |
| 3 — the country chart drops each source that has no country | Where sources were published | Phase 3 |

The funnel and the plan-in-motion screen already use coherent counts. This plan
changes neither of them.

## Decisions (locked in the contract)

| # | Decision | Choice |
|---|---|---|
| D1 | P1 backend counts | Calculate them at read time, from the PSS rows and the events of the **current** acquire run. Do not depend on `backends[].count` in the old rows. |
| D2 | P1 queries | Use the same acquire run only, from `successful_runs["acquire"]`. |
| D3 | Where I looked, `results` | Add up the query `result_count` values across **all** the acquire runs of the project. |
| D4 | Where I looked, `relevant` | Keep the unique project-wide count for each backend. The known defect from task 027 stays, but the grain now agrees more closely with the cumulative `results` count. |
| D5 | Geography gap | Add a residual **"Not reported"** count, over the population that the chart draws at each scope. Use the publisher country only. Do not substitute an authorship country. |
| D6 | Funnel and plan in motion | Change no code. |
| D7 | OpenAPI field names | Keep them. |

## Phases

### Phase 0 — Baseline

**Executor:** `lead`, inline. This is one verify command.

1. Confirm the base. **Settled 2026-08-13:** the branch is on `dev`, which
   already carries the multi-round code. The hotfix branch is not needed. See the
   corrected branching note in [contract.md](contract.md).
2. Run `make verify-fast`. Run the full `make verify` if the tree is cold.
3. Confirm that the multi-round tests exist, in
   `tests/runtime/test_search_rounds.py`.

**Gate:** the baseline is green.

### Phase 1 — P1 check-in counts (defects 1a and 1b)

**Executor:** `codex`. This phase needs judgment, and a machine can check the
result.
**Design brief:** `lead`. The interface passes the acquire `run_id` into
`p1_bundle`.

1. Change `_build_bundle`, so that `SEARCH_EXCEPTION` and P1 pass
   `successful_runs.get("acquire")` into `p1_bundle`.
2. Rewrite `p1_bundle` to do these four things:
   - require that acquire `run_id`;
   - count the **new** sources of that run, for each backend. Use the same
     population as the headline `acquired` count;
   - list the `search.executed` queries of that `run_id` only;
   - keep the current behaviour for the sample titles. The scope of the titles
     for more than one question stays deferred.
3. Optional: also set `count` on the new coverage rows, when acquire writes the
   row. The read path must still calculate the counts without this field.
4. Tests: run acquire and P1 with an `acquired` count of more than 0. The backend
   counts must add up to the `acquired` count. Then use a fixture with two
   rounds. The second P1 must show the queries and the counts of the second round
   only.

**Done when:** invariants 1 and 2 of the contract are true in the tests.

**Gate:** `make verify-fast`.

### Phase 2 — Where I looked grain (defect 2)

**Executor:** `codex`.

1. Change `_backend_details`, or its caller. Collect the query events for
   **all** the acquire run IDs that own a `search_coverage_record` of the
   project. Do not use only the `acquired_by_run_id` value of the latest row.
2. Keep the current attribution of `relevant`.
3. Frontend copy in `JourneyPane` and in the presentation layer: make the line
   honest. Use plain words. For example, `results` is the query hits of all the
   rounds, and `relevant` is the sources that the screen kept. Do not tell the
   user that `relevant` is less than or equal to `results`.
4. Tests: use a fixture with two or three rounds, where the hits of the last
   round are fewer than the cumulative relevant count. After the fix, `results`
   must be equal to or more than the last-round figure, and equal to the sum of
   the query hits of all the rounds.

**Done when:** invariant 3 of the contract is true.

**Gate:** `make verify-fast`. Phase 3 can share this gate, if both phases stay
local.

### Phase 3 — Geography residual (defect 3)

**Executor:** `codex`.

1. In `landscape_out`, increment a residual key when a source in the drawn
   population has no `_geography` value. Use a stable string, for example
   `Not reported`. Count the residual over the population that the function
   already selected, and do this **after** the `scope="cited"` narrowing. Then the
   total is correct at both scopes.
2. Confirm that `normaliseGeographies` does not rename that key, and does not
   drop it. The residual travels to all three render sites through the read model:
   `JourneyPane`, `LandscapeView` and `ArtefactOutline` (the `cited` scope).
3. Journey and Landscape headings: add one short line if the screen needs it. For
   example, "Publisher country, when the database reports it."
4. Tests: mix Overton sources that have a country with OpenAlex sources that do
   not. At the default scope, the sum of the geographies map must be equal to the
   relevant count. Add one `scope="cited"` case: the sum must be equal to the
   cited count, and not to the funnel `relevant` count.

**Done when:** invariant 4 of the contract is true.

**Gate:** `make verify-fast`.

### Phase 4 — Docs, deferred items and verification

**Executor:** `fast-worker` rewrites deferred.md. `lead` writes verification.md,
and updates the phase pointer in AGENTS.md at review time.

1. Edit `docs/deferred.md`. Clear the last-round-only defect for Where I looked
   and for the P1 query scope, for the screens that this slice fixes. Keep the
   timeline round labels and the P1 sample-title scope open.
2. Check whether the living spec still states that the coverage detail covers the
   last round. If it does, add one line to web-api.md or to components.md, and
   flow the correction back (`docs/specs/README`).
3. Write `verification.md`. Include the commands, the test names and the manual
   checklist for the deep run or the standard run.

**Done when:** the evidence can satisfy rubric items 7 and 9–14.

**Gate:** the full `make verify`, which is the exit class of step 6.

## Executor summary

| Phase | Executor | Why |
|---|---|---|
| 0 | lead, inline | One baseline verify |
| 1, design of the `run_id` interface | lead | The signature and the meaning of the interface |
| 1–3, implementation | codex | The default doer. The tests define "done". |
| 4, deferred sweep | fast-worker | A mechanical document change, against the list in the contract |
| 4, verification.md | lead | The evidence narrative needs judgment |

## Out of plan (do not do)

- Substitute an authorship country for a publisher country.
- Add relevance for each query.
- Add "round 2 of 3" labels to the timeline.
- Refactor the funnel or the screen summaries.
- Rename OpenAPI fields, for example `results` to `query_hits`. This stays
  deferred, unless the owner reopens the contract gate.

## Risks

| Risk | Mitigation |
|---|---|
| ~~The hotfix is not merged, and `dev` does not have the multi-round code~~ | **Closed 2026-08-13.** `dev` carries the multi-round code. The branch stays on `dev`. |
| `successful_runs["acquire"]` is absent at P1 | Return an empty bundle, and add a test. P1 occurs only after acquire. |
| "Not reported" is the largest bar in the chart | This is expected. The copy tells the user that the databases frequently omit the venue country. |
| The `results` query-hit count is still more than the count of unique sources | This is honest. The copy tells the user that the hits can overlap. |

## Live check (pinned by the contract)

Do one focused run with more than one round, at standard depth or deep depth, on
the four screens. A full wall-clock e2e test of the evidence base is not
necessary. A rapid run is optional, for the P1 zero-count fix only.
