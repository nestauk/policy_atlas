# Task contract: 031-search-count-honesty

One implementation slice. Keep it reviewable. The boundaries are in
[AGENTS.md](../../../AGENTS.md). The specs are in [docs/specs/](../../specs/index.md).

> **Status:** drafted 2026-08-12. Contract approved (before planning):
> 2026-08-13 · owner · Plan approved (before implementation): 2026-08-13 · owner ·
> ADR: none expected. This slice corrects counts and shows an honest residual. It
> opens no new design decision.
>
> **Branching:** `task/031-search-count-honesty` branches from `dev`.
> **Corrected 2026-08-13:** the draft said this branch stacks on
> `37-hotfix-remove-quota` for the multi-round code. It does not need to. `dev`
> already carries the deep-search and multi-round code (`a77c5f0` "Reinstate deep
> search", an ancestor of this branch, with
> `backend/tests/runtime/test_search_rounds.py`). The hotfix branch is ahead of
> `dev` only by a `dev` merge and task 029 (co-pilot chat), which this slice does
> not touch. The stop condition on the base therefore does not fire.
>
> The defects are most visible at **deep** depth, which runs three search rounds.
> Defect 1a, the zero counts on the P1 check-in, also occurs at rapid and standard
> depth.

## Goal

Give each source count that the user sees one clear meaning. Make the numbers
agree across the chat check-in, the journey pane and the landscape.

Today one deep run can show all of these numbers together:

| The user sees | The problem | Defect |
|---|---|---|
| "Sources found: 70", and below it "OpenAlex 0 · Overton 0" | The parts contradict the total | 1a |
| "from 56 queries", next to a count for one round | The count covers one round; the queries cover every round | 1b |
| "72 results · 200 relevant" | Two numbers on one line, with two different grains | 2 |
| A country chart that adds up to approximately 15, while the funnel reports 215 relevant | The chart drops each source that has no country | 3 |

Only the rows on the plan-in-motion screen add up correctly today.

After this slice, each of these numbers means one thing, and the parts add up to
the total.

## Terms and screens

Read these two tables first. The rest of the document uses these terms.

This table defines the machinery. The audit below defines the **counts**.

| Term | Meaning |
|---|---|
| **Acquire run** | One search pass. It sends the queries to the providers, and it stores the results. A deep run does a maximum of three. |
| **Screen run** | One relevance pass over the sources that an acquire run stored. |
| **Round** | One acquire run, plus the screen run that follows it. |
| **Backend** | One source provider, for example OpenAlex or Overton. |
| **P1** | The first steer point, `search_exception`. It is a check-in in the chat, and it can fire after an acquire run. See [execution-orchestration.md](../../specs/system/execution-orchestration.md). |
| **PSS** | A `project_source_snapshot` row. One row is one unique source in the project. |
| **Coverage record** | A `search_coverage_record` row. Acquire inserts one new row for each acquire run. The row carries a `backends` JSON list, with one entry for each backend that the run used, and an `acquired_by_run_id` column. |
| **Grain** | The records that a number counts, and the time span that it covers. Two numbers with different grains must not go on one line. |
| **Query hits** | The records that one provider call returns, before the project removes the duplicates. |

The counts appear on five screens. This slice changes three of them.

| Screen | Where | The numbers it shows | Status |
|---|---|---|---|
| **P1 check-in** | Chat, after acquire (`CheckInBundle.tsx`) | Sources found; a count for each backend; the query list; sample titles | **Broken** — defects 1a and 1b |
| **Where I looked** | Journey pane (`JourneyPane.tsx`) | `results` and `relevant`, for each backend | **Broken** — defect 2 |
| **Where sources were published** | Journey pane, Landscape (`LandscapeView.tsx`) and the artefact outline (`ArtefactOutline.tsx`, which draws the `cited` scope) | The source count for each publisher country | **Broken** — defect 3 |
| **Funnel** | Journey pane | `found` and `relevant`, for the whole project | Correct — do not change |
| **Plan in motion** | Journey pane | The new relevant sources of each screen run | Correct — do not change |

## Deliverable

One PR that does these five things:

1. It corrects the P1 check-in. The backend counts are no longer always zero, and
   the query list covers one acquire run. (Defects 1a and 1b.)
2. It aligns "Where I looked". The `results` count and the `relevant` count use
   one grain. (Defect 2.)
3. It makes the publisher-country chart honest when the country metadata is
   absent. (Defect 3.)
4. It sets the count vocabulary in the copy and in the tests.
5. It keeps the funnel totals and the plan-in-motion stage metrics unchanged.
   These numbers are already correct.

## Read first

- [web-api.md](../../specs/system/web-api.md) — read models; honest absence.
- [evidence-base components](../../specs/capabilities/evidence-base/components.md) —
  the acquire coverage record; screen; characterise landscape.
- [027 read-model-additions.md](../027-frontend-uplift/read-model-additions.md)
  §2 item 2 — the known defect in `backends_detail`, where `relevant` is
  project-wide.
- [030-multi-round-search/plan.md](../030-multi-round-search/plan.md) — the
  accepted defect where coverage reports only the last round.
- [deferred.md](../../deferred.md) — the multi-round defects (approximately line
  313) and the P1 sample titles (approximately line 1901).
- Code: `api/readmodels/repository.py` (`funnel_out`, `landscape_out`,
  `_geography`, `coverage_out`, `_backend_details`);
  `runtime/steering_bundles.py` (`p1_bundle`);
  `evidence_base/sourcing/acquire.py` (the coverage row write);
  frontend `CheckInBundle.tsx`, `journey/JourneyPane.tsx`, `LandscapeView.tsx`.

## Audit: why the numbers disagree

### Locked meanings (this slice)

This table locks the meaning of each count that the user sees. The grain column
uses the definition in **Terms and screens** above.

| Term | Meaning | Grain |
|---|---|---|
| Funnel `found` | Unique `project_source_snapshot` rows | All rounds, project |
| **Acquired** (check-in chip) | New unique sources from **this** acquire run. The chip field is `acquired`, but the label that the user reads is "Sources found" (`checkInPresentation.ts`). The two names are one number. | One round |
| **Results** (per query) | Records that one provider call returns, before the project dedupe | One call |
| **Results** (per backend, Where I looked) | Sum of the `result_count` values of the queries of that backend | **All rounds** after this fix (before the fix: the last round only) |
| **Relevant** | Unique sources with the effective screen status `relevant` | All rounds, project |
| **Publisher country** | Country of the publishing venue, when the provider sends it | Per source; frequently absent |

### Defect 1a — the backend counts on the check-in are always zero

The check-in shows "Sources found: 70". Below it, the backend line shows
"OpenAlex 0 · Overton 0".

**Cause:** `p1_bundle` reads `backends[].count` from each coverage record.
Acquire never writes `count`. It writes only `backend`, `trust_class`, `mode`
and `depth`. The field is always absent, so the sum is always 0.

The sample titles are still correct, because a separate PSS query supplies them.
Only the counts are wrong.

**Depth:** the defect occurs at rapid, standard and deep depth.

### Defect 1b — the check-in counts one round, but lists the queries of every round

The headline count covers the acquire run that has just finished. The line below
it says "from 56 queries", which is every query of the whole scope.

**Cause:** the query line reads **all** the `search.executed` events of the
scope. It does not limit them to the acquire run that has just finished.

**Depth:** invisible at rapid depth, which runs one round. Visible at standard
depth and deep depth.

### Defect 2 — Where I looked shows "72 results · 200 relevant"

**Cause:** the line puts two different grains together.

- `results` is the sum of `search.executed.result_count` for **one** acquire run.
  `coverage_out` reads the newest coverage record row only (`created_at desc`,
  `limit 1`), and it passes that row's `acquired_by_run_id` to
  `_backend_details`. That function then filters the events by that single
  `run_id`. The earlier rows still exist, but this read path ignores them.
  Therefore the count covers the last round only. Task 030 and deferred.md accept
  this behaviour.
- `relevant` is the count of **all** the effective relevant sources of that
  backend, for the whole project. Task 027 §C.1 records this defect.

After round 3 at deep depth, the hits of the last round can be approximately 72,
while the cumulative relevant count is approximately 200. This is not a
screening defect. It is a display defect that mixes two grains.

**Depth:** rare at rapid depth (1 round). Frequent at standard depth (2 rounds).
Worst at deep depth (3 rounds).

### Defect 3 — the country bars add up to much less than Relevant

**Cause:** `_geography` reads only the publisher country. It tries three sources,
in this order:

- the direct `publication_country` metadata field, which uploaded sources can
  carry;
- Overton: `provider_fields.source.country`
- OpenAlex: `provider_fields.primary_location.source.country_code`

Each of the three can be absent, and then the function returns `None`. OpenAlex
frequently omits the venue country. The slim authorships keep the
authorship countries, but the code must **not** use an authorship country as the
publisher country. The chart drops each source that has no country. There is no
residual bucket. Therefore the chart cannot add up to Relevant.

**Depth:** worse at deep depth, because the OpenAlex volume is dominant.

### Defect 4 — none. Plan in motion is correct

Each Screening row reports the new relevant sources of that screen run. The sum
of these rows is equal to the funnel `relevant` count. Keep this screen as the
reference for the yield of each round.

## Scope / Out of scope

### In

- **Defects 1a and 1b** — `p1_bundle`: calculate the backend counts from durable
  data, for the acquire run that has just finished. Limit the queries to that
  run. Keep the headline count and the body in agreement.
- **Defect 2** — `coverage_out` and `_backend_details`: add up the query
  `results` values across **all** the acquire runs of the project. This clears
  the last-round-only defect for this pane. Keep `relevant` as the unique
  project-wide count for each backend.
- **Defect 2** — copy: use short labels that show the grain. For example, "query
  hits" and "kept after screening".
- **Defect 3** — geography: add a residual **"Not reported"** count in
  `landscape_out`. Then the known countries plus the residual add up to the
  population that the chart draws, at each scope. Keep the publisher-country
  meaning. The residual reaches all three render sites, because they share the
  read model.
- Tests for the five invariants below.
- Update `docs/deferred.md`. Remove or rewrite the last-round-only coverage
  defect for Where I looked and for P1. Keep the separate note about the P1
  sample titles.

### Out

- Schema migrations and new tables.
- Changes to the funnel calculations or to the screen stage summaries.
- Use of an authorship country as the publisher country.
- Study geography charts at finding level.
- Relevance for each query. The system still does not record it.
- Round labels on the timeline. They stay deferred.
- Limitation of the P1 sample titles to the evidence scope. This stays deferred
  until the multi-question IA.
- Search volume caps, round caps and provider behaviour.
- Prompt changes and model changes.

## Constraints & approval gates

- **No schema migration.** The counts come from the events and the snapshots
  that exist today.
- **The public read-model shapes stay.** The field names on
  `CoverageBackendDetailOut` and on the P1 bundle do not change. This slice
  changes **how the numbers are calculated**, not the OpenAPI field set. Owner
  approval at this contract gate covers that change of meaning.
- **No new dependencies, auth, egress, CI or production config.**
- Acquire may also write the optional `count` field onto new coverage JSON, as
  an additional safeguard. The read path must not need this field, so that the
  old rows stay correct.

## Public / private boundary

Public-safe: the count vocabulary, the residual label, the tests and the
deferred.md changes. The fixtures must contain no raw source text, except in the
patterns that exist today.

## Model route

`n/a` — this slice does no inference.

## Disciplines binding this slice

- Honest absence: if the publisher country is absent, show "Not reported". Never
  invent a country.
- Do not flatten status.
- Flag, do not drop.
- Keep the deferred items in [docs/deferred.md](../../deferred.md).

## Count invariants (acceptance)

These five statements must be true after this slice, for each project that has
completed a minimum of one acquire cycle and one screen cycle:

1. **P1, closes defect 1a:** if the check-in chip shows `acquired = N`, and N is
   more than 0, the backend line must not show only zeros. The per-backend counts
   of new sources for that run must add up to N.
2. **P1, closes defect 1b:** the bundle lists the queries of that same acquire
   run only.
3. **Where I looked, closes defect 2:** for each backend, `results` is the sum of the query hits
   of that backend across **all** the rounds. `relevant` stays the unique
   project-wide count for that backend. The copy must not tell the user that
   `relevant` is a subset of `results`. The query hits can overlap, and the
   system counts them before the dedupe.
4. **Geography, closes defect 3:** the country bars plus "Not reported" add up to
   the population that the chart draws, and never to less than it.
   - At the default scope, that population is every relevant source, so the total
     is equal to the funnel `relevant` count.
   - At `scope="cited"`, `landscape_out` narrows the population to the sources
     that the latest artefact cites. The total is then equal to that cited count,
     **not** to the funnel `relevant` count. Do not "correct" the cited scope to
     match the funnel.
5. **Unchanged:** the funnel `found` and `relevant` counts, and the
   plan-in-motion screen `relevant` totals, stay as they are today.

## Stop conditions

Stop the work if one of these conditions occurs:

- A schema change appears to be necessary.
- Someone proposes to rename OpenAPI fields.
- The scope grows to use an authorship country as the publisher country, or to
  add round labels to the timeline.
- The hotfix base is not available, and `dev` does not have the multi-round
  code.

## Acceptance checks

- `make verify` is green.
- Unit tests and API tests cover invariants 1–4. Invariants 2 and 3 need a
  multi-round fixture. Invariant 4 needs one default-scope case and one
  `scope="cited"` case.
- Manual check in the browser: do one **deep** run, or one standard run with
  more than one round. Then check the check-in, Where I looked, the geography
  residual and the funnel. A rapid smoke test is optional.
- A live full-chain e2e test is **not** necessary. Do a focused deep check or
  standard check on the changed screens, together with the existing verify.

## Verification evidence expected

- The commands and the test names, in `verification.md`.
- Notes before and after for defects 1a, 1b, 2 and 3, or fixture assertions that
  record them.
- Confirmation that the funnel and the plan-in-motion screen did not change.
- A list of the changes to deferred.md.

## Risk tier & review focus

**Tier 2** — this slice fixes a read model and a check-in projection. It needs
integration tests and a human review. It is not Tier 3, because it changes no
schema, no auth and no egress, and because the OpenAPI field *set* stays the
same.

Review focus: mixed grain; regressions at deep depth; the honest residual; clear
copy; no silent substitution of an authorship country for a publisher country.
