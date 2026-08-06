# Replace the wall clock with a per-round acquisition cap

## Context

The hotfix on `37-hotfix-remove-quota` fixed a real bug: the run-wide result quota was
being divided across the fan-out, so 75 results ÷ 15 OpenAlex queries gave 5 results per
query. Caps are now per-call.

That fix moved the failure rather than removing it. The wall clock
(`RAPID/STANDARD/DEEP_WALL_CLOCK_S`) is checked before every call at
`search_loop.py:1321`, and the only thing that ever sets `stop_all` is that check —
verified, it is the sole cause of skipped calls. The fan-out runs `for backend` outer,
`for plan` inner, with `live_search_backends` always returning `[OpenAlex, Overton]`, so
a clock breach during the OpenAlex leg costs the *entire* Overton leg: zero grey
literature, and the run still reports `adequate`. That is exactly the crowding-out that
task 015 contract decision 6 was written to prevent.

Two further consequences, from the review in `lead-findings.md`: the run-level result cap
was the only bound between search volume and paid LLM screening (finding L3, still an
open seam), and at deep the clock makes `ROUND_CAP = 3` unreachable — round 2 cannot
finish inside 150 s, so raising the recall knob *reduced* the number of search rounds.

**Intended outcome:** remove the time budget from standard and deep, and replace it with
a volume budget applied at acquisition. Time stops being the thing that decides which
queries run; an explicit document cap becomes the thing that bounds screening spend.
Rapid keeps its clock — it is the interactive path where latency is the actual
requirement.

The reference implementation is v2 (`nestauk/discovery_policy_atlas` `origin/dev`), which
has no wall clock at all: it fires every query through one `asyncio.gather`, then trims
the merged set at `analysis/references.py:855-890`. This plan adopts the trim-at-merge
idea; it does not adopt the concurrency rewrite.

## The target pipeline

```
fetch          all fan-out queries run to completion (no clock)
merge          rank-interleave records across queries, per backend
dedupe         drop unusable + already-acquired
trim           top 200 per backend
save + embed   400 rows, 400 embeddings
screen         400 documents
```

Dedupe **before** trim, so a round always yields a full 200 new documents per backend
however many repeats the queries returned.

## Decisions taken

| Decision | Choice |
|---|---|
| Ordering for the trim | Rank-interleave across queries (round-robin by position) |
| Per-round cap | 200 per backend — OpenAlex and Overton alike |
| Rapid | Unchanged — keeps its 30 s clock and its 50-per-call cap |

Rank-interleave rather than a relevance sort: OpenAlex is queried with
`title_and_abstract.search` and no `sort` param (`search_live.py:380-386`) and Overton
with `squery` + `min_similarity` (`search_live.py:497-504`), so each call's records
already arrive in rank order. Taking rank 1 from every query, then rank 2, and so on
needs no new API field and no schema change, and guarantees every query in the fan-out is
represented. A merged sort by `relevance_score` (v2's approach) would need the field
added to `OA_SELECT` and persisted, and OpenAlex relevance scores are not comparable
between query variants — one verbose query could take most of the 200.

A symmetric per-backend cap rather than exempting Overton: each backend gets its own
floor, which protects grey literature as well as an exemption does, and it leaves no
unbounded backend. At deep, Overton returns roughly 7 calls × 100 ≈ 700 raw records per
round, so the cap does bite.

### On the number 200

It is a starting figure sized from purpose, not from measurement:
`TARGET_CONFIDENT_RELEVANT = 20`, `SCREEN_REPS = 3`, three deep rounds → ~1,200 documents
and ~3,600 screening calls to find 20.

`scripts/eval_ground_truth/` already measures the thing that should set it. Its current
report (15 reviews, 45 queries, ground truth from published systematic reviews) shows
search recall mean 2.4% / max 9.1%, screen recall 2.3% — near-identical, meaning
documents are lost at *search*, not at screening — with a median of 26 candidates per
query, which is the divided-quota bug being measured at rapid depth. Re-run that harness
after this change and set the cap from where recall stops improving. Treat 200 as
provisional.

## Changes

### 1. Turn the clock off for standard and deep

`backend/src/policy_atlas/evidence_base/sourcing/search_loop.py`

- `DepthConstants.wall_clock_s` becomes `int | None`; `STANDARD_WALL_CLOCK_S` and
  `DEEP_WALL_CLOCK_S` become `None`. `RAPID_WALL_CLOCK_S = 30` untouched.
  Use `None`, not a large sentinel — `None` reads honestly in stop attribution and logs;
  a 10,000 s budget lies about what the code is doing.
- Guard the check at `search_loop.py:1321`: skip when the budget is `None`.
- `run_deep_rounds` reads `DEEP_WALL_CLOCK_S` directly at `search_loop.py:1892` and
  `:1929` — guard both. The deep loop then stops on `round_cap` or `target_reached` only.
- `acquire.py:820`'s `wall_clock_exceeded` branch stays as-is: still live for rapid,
  simply never fires for standard/deep. No schema-enum change.

### 2. Merge, dedupe, trim, then save

`backend/src/policy_atlas/evidence_base/sourcing/acquire.py`

`acquire_sources` currently walks `executed_calls` and, for each record in turn, maps it,
checks it against the dedupe sets, and immediately writes `source_snapshot` + `chunk` +
`project_source_snapshot` rows (`acquire.py:602-720`). Split that single pass in two:

- **Pass 1 — select.** Map each record (`_MAPPERS`, pure), apply the three existing
  identity guards (`seen_record_ids` / `seen_dois` / `seen_hashes`, preloaded from the
  project at `acquire.py:556-577`), and collect the survivors per call, preserving each
  record's rank position within its call. Updating the seen-sets as it goes keeps
  within-batch dedupe working exactly as today. Counts `skipped_unusable` and
  `already_acquired` are attributed here, unchanged.
- **Interleave and trim.** Round-robin the surviving candidates across the `verb ==
  "search"` calls of each backend by rank position, take the first N per backend. Calls
  of other verbs (`fetch_citations`, `fetch_references`, `lookup_dois`, `lookup_title`)
  pass through untrimmed — the snowball, suggest, reformulate and diversity arms are
  already small and separately bounded (`SNOWBALL_RESULTS = 40` over `SNOWBALL_CALL_CAP =
  6` calls; `SUGGEST_CALL_CAP = 6`; `REFORMULATE_CALL_CAP = 4`; `DIVERSITY_FRACTION =
  0.15`), contributing tens of records per round rather than hundreds.
- **Pass 2 — persist.** Write the survivors exactly as the current code does, in
  interleaved order. `embed_pending_chunks` (`acquire.py:868-880`) stays where it is and
  now only ever sees the trimmed set.
- Add an `openalex_record_cap` / `overton_record_cap` keyword — or one
  `record_cap_per_backend: int | None = None` — to `acquire_sources`. Policy stays in
  `DEPTH_CONSTANTS`; `acquire` stays dumb and directly testable. A `None` default keeps
  the existing test callers (`test_acquire.py`, `test_characterise.py`,
  `test_acquire_mapping_deltas.py`) working unchanged.
- Keep `counts["results_returned"]` sourced from the untrimmed `call.records` — it means
  "what the provider returned" and must stay honest. Add a `dropped_over_cap` count per
  backend, rolled into `totals`, so the trim is visible rather than silent, matching the
  existing `skipped_unusable` / `already_acquired` honesty pattern.

### 3. Wire the constants

`search_loop.py` — add the cap to `DepthConstants` and to each depth in
`DEPTH_CONSTANTS`: rapid `None`, standard `150`, deep `200`. Pass it at the
`acquire.acquire_sources` call site (`search_loop.py:1794-1806`).

`result_cap_per_backend` stays as it is (50/75/100) — it governs pagination and latency
per call, which is a different job from the per-round volume cap.

### 4. Docs

This is the same class of change as review finding L1 — a contract decision reversed in
code. It must be written down, not shipped silently:

- `docs/tasks/015-live-search/contract.md` decision 6 — amend: caps are per-call, and the
  run-level brake is now a per-round acquisition cap, not a shared result total.
- `docs/tasks/019-*` item 5 / stop attribution — `wall_clock_exceeded` is now rapid-only.
- `docs/knowledge/result-caps-need-distribution-rule.md` + `docs/knowledge/index.md` +
  `docs/knowledge/log.md` — the concept becomes "cap acquisition, not calls".
- `docs/deferred.md` — L3's total-volume ceiling is discharged, with the new bound and
  the fact that 200 is provisional pending the eval re-run.

## Consequences to expect

- **Deep runs get materially longer.** With no clock the search legs run to completion:
  roughly 2–4 min of searching per round (Overton's 1.2 s enforced inter-request gap
  dominates), three rounds, plus screening between them. Realistically tens of minutes.
  There is no step timeout in `runtime/runner.py` — I grepped, there isn't one — so the
  search stage's own clock was the only bound on stage duration. After this change there
  is none.
- **`ROUND_CAP = 3` becomes reachable at deep** for the first time. The ~1,200-document
  figure already assumes this.
- `budget_exhausted` and `wall_clock_exceeded` become unreachable for standard/deep, so
  any test pinning them at those depths needs updating.

## Verification

1. `make verify` green.
2. New unit tests in `backend/tests/evidence_base/sourcing/`:
   - interleave order — three calls of ranked records produce `A1 B1 C1 A2 B2 C2 …`;
   - dedupe runs before the trim: a batch where half the top-200 candidates are repeats
     still yields 200 saved documents;
   - the cap is per backend, and non-search verbs are never trimmed;
   - `results_returned` still reflects the untrimmed provider response, and
     `dropped_over_cap` accounts for the difference;
   - standard/deep never set `stop_all` however far the fake clock is advanced;
   - rapid still breaches and still reports `wall_clock_exceeded`.
3. Update the deep-loop tests that assume a 150 s budget (`test_search_loop_deep.py`),
   including the stale comments at `:670-671` and `:963-964` already noted in the review.
4. One live deep run against a real scope. Confirm from the event log: Overton executed a
   non-zero number of calls in every round; ≤200 acquisitions per backend per round;
   `dropped_over_cap` reconciles with `results_returned`; the run reaches round 3 and
   stops on `round_cap` or `target_reached`. Record wall-clock duration and screened-
   document count.
5. Re-run `scripts/eval_ground_truth/run_and_score.py` and compare search recall against
   the current baseline (mean 2.4%, max 9.1%). This is the number the change exists to
   move, and the basis for replacing the provisional 200.
