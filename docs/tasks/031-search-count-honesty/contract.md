# Task contract: 031-search-count-honesty

One implementation slice. Keep it reviewable. Boundaries are in
[AGENTS.md](../../../AGENTS.md); specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted 2026-08-12. Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ · ADR: none expected (grain
> fix + honest residual; no new design fork).
>
> **Branching:** stacks on `37-hotfix-remove-quota` (tasks 029–030 search-volume /
> multi-round code). Re-target `dev` after that hotfix merges. The worst bugs
> show on **deep** (3 search rounds). The P1 zero-count bug also hits rapid and
> standard.

## Goal

Make every user-facing source count mean one clear thing. Make the numbers
match across chat check-ins, the journey pane, and the landscape.

Today the same run can show "70 sources found", "OpenAlex 0 · Overton 0",
"72 results · 200 relevant", and a country chart that sums to ~15 while the
funnel says 215 relevant. The plan-in-motion screen rows are the only surface
that already adds up.

## Deliverable

One PR that:

1. Fixes the P1 check-in backend line (no more permanent zeros).
2. Aligns "Where I looked" so `results` and `relevant` share one time grain.
3. Makes the publisher-country chart honest when country metadata is missing.
4. Locks the count vocabulary in copy and tests.
5. Leaves funnel totals and plan-in-motion stage metrics unchanged (they are
   already correct).

## Read first

- [web-api.md](../../specs/system/web-api.md) — read models; honest absence.
- [evidence-base components](../../specs/capabilities/evidence-base/components.md) —
  acquire coverage record; screen; characterise landscape.
- [027 read-model-additions.md](../027-frontend-uplift/read-model-additions.md)
  §2 item 2 — `backends_detail` wart (project-wide `relevant`).
- [030-multi-round-search/plan.md](../030-multi-round-search/plan.md) —
  accepted last-round-only blemish for coverage.
- [deferred.md](../../deferred.md) — multi-round blemishes (~313) and P1 sample
  titles (~1901).
- Code: `api/readmodels/repository.py` (`funnel_out`, `landscape_out`,
  `_geography`, `coverage_out`, `_backend_details`);
  `runtime/steering_bundles.py` (`p1_bundle`);
  `evidence_base/sourcing/acquire.py` (coverage row write);
  frontend `CheckInBundle.tsx`, `journey/JourneyPane.tsx`, `LandscapeView.tsx`.

## Audit (why the numbers disagree)

### Locked meanings (this slice)

| Term | Meaning | Grain |
|---|---|---|
| **Sources found** / funnel `found` | Unique `project_source_snapshot` rows | All rounds, project |
| **Acquired** (check-in chip) | New unique sources from **this** acquire run | One round |
| **Results** (per query) | Records returned by one provider call, before project dedupe | One call |
| **Results** (per backend, Where I looked) | Sum of that backend's query `result_count` values | **All rounds** after this fix (was: last round only) |
| **Relevant** | Unique sources with effective screen status `relevant` | All rounds, project |
| **Publisher country** | Country of the publishing venue when the provider sends it | Per source; often missing |

### Bug 1 — Check-in: "Sources found: 70" and "OpenAlex 0 · Overton 0"

**Cause:** `p1_bundle` reads `backends[].count` from every
`search_coverage_record`. Acquire never writes `count` — only `backend`,
`trust_class`, `mode`, `depth`. The sum is always 0.

Titles still list because they come from a separate PSS query. The query
line uses **all** `search.executed` events for the scope, so deep shows
"from 56 queries" next to a this-round chip of 70.

**Depth:** Broken on rapid, standard, and deep. Deep makes the mismatch
obvious.

### Bug 2 — Where I looked: "72 results · 200 relevant"

**Cause:** Two different grains in one line.

- `results` = sum of `search.executed.result_count` for the **latest**
  coverage row's acquire run only (last-write-wins; accepted in 030 /
  deferred.md).
- `relevant` = **all** effective relevant sources for that backend
  (project-wide; documented wart from 027 C.1).

After round 3 of deep, last-round hits can be ~72 while cumulative relevant
is ~200. That is not a screening bug. It is a mixed-grain display bug.

**Depth:** Rare on rapid (1 round). Common on standard (2). Worst on deep (3).

### Bug 3 — Country bars sum far below Relevant

**Cause:** `_geography` only reads publisher country:

- Overton: `provider_fields.source.country`
- OpenAlex: `provider_fields.primary_location.source.country_code`

OpenAlex often omits venue country. Authorship countries are retained in
slim authorships but **must not** be treated as publisher country. Missing
country sources are dropped from the chart. There is no residual bucket.
The chart therefore cannot sum to Relevant.

**Depth:** Worse on deep because OpenAlex volume dominates.

### Bug 4 — Plan in motion looks right

**Not a bug.** Each Screening row reports new relevants for that screen run.
Summing those rows matches funnel `relevant`. Keep this surface as the
reference for per-round yield.

## Scope / Out of scope

### In

- `p1_bundle`: compute backend counts from durable data for the acquire run
  that just finished; scope queries to that run; keep chip and body aligned.
- `coverage_out` / `_backend_details`: aggregate query `results` across **all**
  acquire runs for the project (discharge the last-round-only blemish for this
  pane). Keep `relevant` as unique project-wide per backend.
- Copy: short labels so users can see the grain ("query hits" vs "kept after
  screening" if needed).
- Landscape / journey geography: add a residual **"Not reported"** count so
  known countries + not reported = Relevant. Keep publisher-country semantics.
- Tests for the four invariants below.
- Update `docs/deferred.md`: remove or rewrite the last-round-only coverage
  blemish for Where I looked / P1; keep the separate P1 sample-titles
  multi-question note.

### Out

- Schema migrations / new tables.
- Changing funnel math or screen stage summaries.
- Using authorship countries as publisher country.
- Study geography (finding-level) charts.
- Per-query relevance (still not recorded).
- Round labels on the timeline (stays deferred).
- Scoping P1 sample titles to the evidence scope (stays deferred until
  multi-question IA).
- Search volume caps, round caps, or provider behaviour.
- Prompt / model changes.

## Constraints & approval gates

- **No schema migration.** Counts come from existing events and snapshots.
- **Public read-model shapes stay.** Field names on `CoverageBackendDetailOut`
  and the P1 bundle stay. This slice changes **how numbers are filled**, not
  the OpenAPI field set. Owner approval at this contract gate covers that
  semantic fix.
- **No new deps, auth, egress, CI, or prod config.**
- Writing optional `count` onto future coverage JSON is allowed as a
  belt-and-braces aid; **read path must not require it** (old rows stay
  correct).

## Public / private boundary

Public-safe: count vocabulary, residual label, tests, deferred.md edits.
No raw source text in fixtures beyond existing patterns.

## Model route

`n/a` — no inference.

## Disciplines binding this slice

- Honest absence: missing publisher country → "Not reported", never invented.
- Don't flatten status.
- Flag, don't drop.
- Leave deferred seams in [docs/deferred.md](../../deferred.md).

## Count invariants (acceptance)

After this slice, for any project that has finished at least one acquire+screen
cycle:

1. **P1:** If the check-in chip shows `acquired = N` and N > 0, the backend
   line must not show all zeros. Sum of per-backend new-source counts for that
   run equals N.
2. **P1:** Queries listed are from that same acquire run only.
3. **Where I looked:** For each backend, `results` is the sum of that
   backend's query hits across **all** rounds. `relevant` stays unique
   project-wide for that backend. Copy must not imply `relevant ⊆ results`
   when query hits overlap or when hits are pre-dedupe.
4. **Geography:** Sum of country bars + "Not reported" = funnel `relevant`
   (same screened-in population the landscape already uses).
5. **Unchanged:** Funnel `found` / `relevant` and plan-in-motion screen
   `relevant` totals stay as today.

## Stop conditions

Halt if: a schema change seems required; OpenAPI field renames are proposed;
scope grows into authorship-as-publisher or timeline round labels; or the
hotfix base is not available and `dev` lacks multi-round.

## Acceptance checks

- `make verify` green.
- Unit/API tests for invariants 1–4 (multi-round fixture required for 2–3).
- Manual / browser: one **deep** (or standard multi-round) run — check-in,
  Where I looked, geography residual, funnel. Rapid smoke optional.
- Live full-chain e2e is **not** required; use a focused deep/standard check
  on the changed surfaces plus existing verify.

## Verification evidence expected

- Commands and test names in `verification.md`.
- Before/after notes for the four bugs (or fixture assertions that encode them).
- Confirmation funnel and plan-in-motion were not changed.
- deferred.md update listed.

## Risk tier & review focus

**Tier 2** — read-model / check-in projection fix; integration tests; human
review. Not Tier 3: no schema, auth, or egress change; OpenAPI field *set*
unchanged.

Focus: mixed grain, deep-search regressions, honest residual, copy clarity,
no silent authorship→publisher substitution.
