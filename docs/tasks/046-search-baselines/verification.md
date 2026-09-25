# Verification: 046-search-baselines

Evidence for the build (step 6), written 2026-09-25 against commit `8b4a61b` plus the docs
commits that follow it. Public-safe: no keys, no cache content, no raw abstracts.
**Review findings** and **Rubric status** are added by the review conversation (step 7).

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (build-open baseline, commit `002d695`) | pass | backend 2583 tests, mypy 306 files, ruff, frontend 617 tests |
| `make verify-fast` (Phase 1 gate) | pass | 2583 tests, mypy, ruff |
| `make verify-fast` (paging-fix gate) | pass | 2583 tests, mypy, ruff |
| `make verify` (step-6 exit, working tree at `8b4a61b` + docs) | pass | okf-validate, backend 2583 tests, mypy 306 files, ruff, build, frontend 617 tests; one pre-existing eslint warning (`SplashField.tsx`), also in the baseline log |
| `make verify-fast` (Phase 5 gate, snippet arm) | pass | 2583 tests, mypy, ruff |
| `make verify` (step-6 exit after Phase 5, commit `af1c86e` + docs) | pass | same suites as above, exit 0, same pre-existing eslint warning |
| `uv run --project backend python scripts/evals/search/test_metrics.py` | pass (`ok`) | 11 new self-checks: `test_baseline_*` (10, incl. `test_baseline_snippet_arm`) and `test_history_cost_column` |
| `uv run --project backend ruff check scripts/evals/search/` | pass | scripts are outside the `make lint` scope (`src`, `tests`), so run by hand |

## Checks beyond the build

- **Deterministic self-checks** (all in `test_metrics.py`, no network): record-to-key mapping
  per arm; the three cutoff converters incl. Consensus month rounding; the Semantic Scholar
  hyphen rule and verbatim intent for the other two arms; paging per arm (Semantic Scholar
  stops on absent `next`, empty `data`, full last page, and at 1,000 after exactly 10
  requests with offsets 0..900; Consensus starts at page 0 with `page_size=1000`, switches
  to the echoed 300, stops on `is_end`, on empty `results`, and fetches positions 900-999
  as page 9 at size 100, or page 3 at 250 for a 750 plan; OpenAlex stops under 200 results
  and after page 5); the retry rule (429 with `retry-after: 3` sleeps 3 s and retries; four
  5xx sleep 1, 2, 4 s and hand back the last response; a failing getter gives
  `n_failed_calls=1`, `complete=False`, pages fetched before the failure kept, no raise);
  cache round trip (equal pages after write/read; incomplete file refetched; `refresh=True`
  refetched; exactly the nine pinned keys; no `x-api-key` in the file); cap slicing (first
  N then dedup, a match at position N+1 not found at cap N); cost per arm and cap (Consensus
  20/150/300 papers = 1/2/3 calls, OpenAlex sums `meta.cost_usd` over the pages for the cap,
  Semantic Scholar 0); **cache path scores identical to live path** at caps 1, 2, 50;
  `score_baseline` emits exactly the seven D6 scores; `history.py` sums cost (0.10 + 0.20 =
  0.30 `api`; 0.45 + 0.55 = 1.00 `llm`), still averages recall, never calls `trace.get` when
  `api_cost_usd` is present, prints `n/a` and four decimals under one cent.
- **AI evals:** none. No language model runs in this slice.
- **Live check (pinned scope: one full fetch, then scoring from the cache):** see below.

## End-to-end command

```
# 1. Consensus preflight probe: one review, fetch + cache + score, upload nothing
uv run --project backend --env-file backend/.env python scripts/evals/search/baseline_recall.py --arms consensus --reviews parental --dry-run

# 2. Full fetch of all arms and reviews, score at all caps, upload 12 Langfuse runs
uv run --project backend --env-file backend/.env python scripts/evals/search/baseline_recall.py

# 3. After the paging fix (commit 8b4a61b): refetch Consensus only, upload nothing
uv run --project backend --env-file backend/.env python scripts/evals/search/baseline_recall.py --arms consensus --refresh --dry-run

# 4. The run whose rows are in history.md: read every arm from the cache, zero requests, upload
uv run --project backend --env-file backend/.env python scripts/evals/search/baseline_recall.py

# 5. History rows with the new cost column
uv run --project backend --env-file backend/.env python scripts/evals/search/history.py --since 2026-09-22
```

### Consensus preflight (plan Phase 3 steps 1-2)

- **Dashboard step not done by the agent.** The plan asked to read the plan name, included
  calls remaining and the "additional usage" switch from the Consensus dashboard. The agent
  has no browser. Mid-build the owner stated the account is an **API beta account billed
  $0.05 on every call with no included amount**, which settles the stop condition (there is
  no "included calls remaining" to run out of) and makes the price table's $0.05 the price
  of every call, not only the overage.
- **Probe result** (step 1 above, parental-leave review): echoed `page_size` **300** (the
  Pro/Teams size); every result carries `doi`, `title`, `publish_year`, `publish_date`
  (no `paper_id`, so `backend_record_id` is None and the DOI is the key); 3 pages in 10.1 s;
  894 results; **1 failed request** (see the anomaly below).
- **Calls used, whole build:** probe 9 calls; first full fetch 36 calls (4 reviews x 3 pages
  x 3 calls); one hand `curl` of the failing page, answered 400 (not billed as a search);
  refetch after the fix 40 calls (4 x [3 x 3 + 1]). **About 85 calls, about $4.25.** All
  remaining steps read the cache; the upload run in step 4 made zero requests.

### Live fetch (step 2, then step 3 for Consensus)

| Arm | Requests | Results per review | Time | Failed |
|---|---:|---|---:|---:|
| semantic-scholar | 13 | 22, 0, 1, 1000 (the service's own totals: 22, 0, 1, 29,628) | 22 s | 0 |
| consensus (first fetch) | 12 | 899, 893, 894, 894 | 45 s | 0 (stopped at position 900, see anomaly) |
| consensus (refetch, fixed) | 16 | 998, 993, 994, 992 | 27 s | 0 |
| openalex-raw | 20 | 1000, 989, 1000, 1000 | 16 s | 0 |

Whole first run 102 s; the refetch 28 s; the upload run from cache 19 s. The contract expected
Semantic Scholar 40 requests: three of the four intents matched almost nothing, so the
service returned one page each. **No request failed after retries in any run that produced
the rows below.**

### Summary table printed by step 4 (rows copied to `results/history.md`, label `2026-09-25-8b4a61b`)

| arm | cap | mean recall | kept | requests | api cost |
|---|---:|---:|---:|---:|---:|
| semantic-scholar | 50 | 0.9% | 73 | 4 | $0.00 |
| semantic-scholar | 100 | 1.2% | 123 | 4 | $0.00 |
| semantic-scholar | 200 | 1.5% | 222 | 5 | $0.00 |
| semantic-scholar | 1000 | 1.5% | 1015 | 13 | $0.00 |
| consensus | 50 | 7.6% | 200 | 4 | $0.60 |
| consensus | 100 | 8.6% | 400 | 4 | $0.60 |
| consensus | 200 | 10.4% | 798 | 4 | $0.60 |
| consensus | 1000 | 13.6% | 3952 | 16 | $2.00 |
| openalex-raw | 50 | 3.5% | 200 | 4 | $0.0004 |
| openalex-raw | 100 | 4.6% | 400 | 4 | $0.0004 |
| openalex-raw | 200 | 4.6% | 799 | 4 | $0.0004 |
| openalex-raw | 1000 | 6.5% | 3984 | 20 | $0.0020 |

Comparison rows (same ground truth, commit `b16f859`, 2026-09-22): pipeline rapid 5.6% at
cap 50 ($0.0037 llm), standard 10.7% at cap 100 ($4.00 llm), deep 15.3% at cap 200 ($6.99 llm).

Langfuse: dataset `retrieval-ground-truth`, runs `2026-09-25-8b4a61b/<arm>-cap<cap>` (12
runs, 4 items each). Checked on one run: exactly the seven D6 scores (`api_cost_usd`,
`n_api_calls`, `n_api_records`, `n_candidates_kept`, `n_failed_calls`, `n_found`,
`search_recall`) and exactly the six metadata keys (`depth`, `experiment`, `fetched_at`,
`generation_backend`, `git_commit`, `record_cap_per_backend`). Run URLs are in the step-4
log; the dataset page lists them by name. **Twelve earlier runs** under label
`2026-09-25-2815a59` (the first full fetch, Consensus at 900 positions) also exist in
Langfuse; they are superseded and not in `history.md`.

### Zero-request check

Step 4 printed `0 review(s) need a fetch` for every arm and no fetch line; the run took 19 s
and made no service request. It is the run whose rows are kept, so the rubric's "second run
with no flags made zero service requests" is that run, not a separate dry run.

### Cache files (git-ignored, not committed)

`scripts/evals/search/results/cache/<arm>/<sha256(item id)[:16]>.json`, four files per arm:
`547ee5e73d97fbd3` (loneliness), `6c94b3539f1fb287` (parental leave), `c39a9062fe58ffa8`
(adverse childhood experiences), `e03a5992dd8c78ce` (social care). Sizes: consensus 11 MB
(2.4-2.8 MB each, abstracts included), openalex-raw 1.2 MB, semantic-scholar 444 KB. All
`complete: true`; `fetched_at` 14:56 (Semantic Scholar), 14:57 (OpenAlex), 15:00 UTC
(Consensus refetch). Substring audit: neither key value and no `x-api-key` string occurs
in any cache file. `git check-ignore` confirms the rule at `.gitignore:34`.

### Phase 5 addendum: arm 1b `semantic-scholar-snippet` (owner amendment, 2026-09-25)

Commit `af1c86e`; gate `make verify-fast` green (2583 tests, mypy, ruff); `test_metrics.py`
gained `test_baseline_snippet_arm`. Live: `--arms semantic-scholar-snippet`, 11 requests
(four searches, seven id lookups), 42 s, 0 failed, free; four Langfuse runs
`2026-09-25-af1c86e/semantic-scholar-snippet-cap<cap>` with the seven D6 scores and six
metadata keys (checked on the cap-1000 run). Re-run with `--dry-run` made zero requests.
Cache: four files, 4.7 MB, all complete, no key substring, no `x-api-key`. Per review: 1,000
snippets each (title 7-122, abstract 72-191, body 687-921), 417-635 unique papers, every one
with a DOI from the lookup.

| cap | mean recall | kept | pipeline row at the same cap |
|---:|---:|---:|---|
| 50 | 4.3% | 199 | rapid 5.6% |
| 100 | 10.0% | 397 | standard 10.7% |
| 200 | 12.9% | 794 | deep 15.3% |
| 1000 | 18.1% | 2182 | none; best baseline |

Deviation to adjudicate: the arm was added after the plan gate. The owner asked for it in
this conversation after the report on the Semantic Scholar docs (`paper/search` requires
every query word; `snippet/search` ranks by meaning). Contract § Arms, plan Phase 5 and
rubric item 3 carry the amendment. Two design points the reviewer should weigh: for this
arm `n_api_calls` counts the search plus its id lookups at every cap (three, not one), and
`n_candidates_kept` at cap 1,000 is about 550 because snippets collapse to papers.

## Diff summary

- **`scripts/evals/search/baseline_recall.py`** (new, Codex-authored from the lead's brief;
  lead edits listed under Review handoff). Three `fetch_*` functions with one signature,
  three pure cutoff converters, one price table, one rate-limited retrying getter, the S7
  cache (`cache_path`, `write_cache`, `read_cache`, `load_or_fetch`), `records_of`,
  `slice_at_cap`, `pages_for_cap`, `cost_usd`, `score_arm`, `score_baseline`,
  `run_baseline` (Langfuse upload in the `production_recall._run_depth` shape) and the CLI.
- **`scripts/evals/search/history.py`** (fast-worker, S6): `variable cost` column, summed
  per run, labelled `api` or `llm`; four decimals under one cent.
- **`scripts/evals/search/test_metrics.py`**: ten new self-checks.
- **`scripts/evals/search/README.md`**: section 5 (baselines, cache, `--refresh`, reading the
  rows), the cost-column paragraph in section 4, the scripts table.
- **`scripts/evals/search/results/history.md`**: the cost column on every row (old rows
  filled from `history.py`), twelve baseline rows with notes.
- **`backend/.env.example`**: the two key names, empty.
- **`docs/deferred.md`**: § Search recall baselines (task 046 seams), four entries.

### Flagged deviations (minor, resolved within the contract's vocabulary)

1. **Consensus last page (plan S1).** S1 said stop when `(page + 1) x page_size` would exceed
   1,000. Live, at the echoed size 300 that stops at position 900, and Consensus also sends
   no `next_page` there and answers **400** to page 3 at size 300 (probe: 1 failed request,
   `complete: false`). The contract's D2 and deliverable 1 say every arm fetches to the
   1,000 ceiling, so the last request now asks for the remaining slice at a smaller size
   (page 9 at size 100; 750 -> page 3 at 250), computed from positions covered rather than
   results returned, because pages hold a few results fewer than their size (297, 299, 294).
   Test added. Cost unchanged at 10 calls per review. Recall at cap 1,000 was 13.6% before
   and after; the extra 100 positions found nothing new.
2. **Zero-request check via the upload run**, not a third run (see above). A third run with
   no flags would append duplicate items to the same Langfuse run names.
3. **Dashboard preflight replaced by the owner's statement** about the billing model (see
   Consensus preflight). Nothing in the run depended on the included-calls figure.
4. **Consensus price wording.** The contract's "above the included monthly amount" became
   "billed on every call" in the script's fetch-plan line and the README, per the owner.

## Intent & assumptions

- The Semantic Scholar numbers are a measurement of D1 (verbatim intent), not a bug: the
  service's own `total` for three intents was 0, 1 and 22. Its search requires every word to
  match. This is written into the history notes and the deferred "swap" entry.
- `n_candidates_kept` can be below the cap (199 at cap 200) because a duplicate DOI inside
  the first N counts once (D3).
- The 2026-09-24 pipeline rows in `history.py` output (single-review smoke runs) were not
  copied to `history.md`, per its own rule on partial runs.

## Known unverified items

- The Consensus dashboard figures (plan name, remaining calls, additional-usage switch) were
  not read. The echoed page size 300 implies a Pro or Teams size table.
- Ranking stability across repeat fetches (deferred, D9).
- The Semantic Scholar 429 path was exercised only in the self-check; live, every request
  with the key answered 200 at one request per second.

## Public safety

`history.md` holds mean recall, counts and computed dollar figures only. The cache (abstracts
and publisher metadata from a paid service) is git-ignored and stays on this laptop. Keys
live in `backend/.env` only; the substring audit above shows none in the cache. Langfuse
traces carry the intent text, scores and metadata, no service payloads.

## Review handoff (step-7/8 inputs)

- **Executor provenance (family flip):** Phase 1 product code and tests by Codex (GPT family)
  from the lead's brief; Phase 2 by `fast-worker` (Sonnet); Phase 3-5 by the lead (Phase 5,
  the snippet arm, is lead-authored product code and tests: weigh review attention there). Lead edits
  to Codex's output, for the reviewer to weigh: three added tests (cache-equals-live scores,
  match at N+1 not found, pages kept before a failure), the zero page-size guard, the
  Consensus last-page rule (deviation 1), `_usd` formatting, argparse help strings and the
  module docstring. Codex's tests were the weaker half (three contract-listed checks
  missing), consistent with the 022 lesson in `harness.md`.
- **Adjudication items:** deviations 1-4 above; the twelve superseded Langfuse runs under
  label `2026-09-25-2815a59` (leave or delete); whether `history.md` should keep both
  Semantic Scholar cap-100 and cap-200 rows given the flat numbers.
- **Diff-scoping:** `scripts/evals/search/results/cache/` is untracked and ignored; no diff.
- **Live-trace pointers:** Langfuse dataset `retrieval-ground-truth`, runs
  `2026-09-25-8b4a61b/*`.
- **Knowledge candidates:**
  - Consensus rejects (400) any page where `(page + 1) x page_size > 1000` and sends
    `next_page: null` one page early; to reach position 999 at size 300 the last request
    must be page 9 at size 100. Pages return a few results fewer than `page_size`, so paging
    arithmetic must use positions, not counts.
  - Semantic Scholar's `paper/search` is an all-words match: a title-length intent returns
    the service's `total` of 0-22 for most reviews. The same API's `snippet/search` is a
    semantic (dense) retriever over passages: verbatim intents work, it returns snippets
    keyed by `corpusId` (no DOI; map with `paper/batch`, 500 ids per call), 1,000 snippets
    collapse to about 550 papers, and body-text snippets exist only for open-access papers.
    Its free-tier rate limit is stricter than one request per second in practice; a 3 s
    interval plus the retry rule fetched four reviews cleanly.
  - OpenAlex reports `meta.cost_usd` = 0.0001 per page (with the key), so any 2-decimal cost
    display shows $0.00; both tables switch to 4 decimals under one cent.
  - The Consensus API beta account is billed $0.05 on every call with no included amount
    (owner, 2026-09-25); the contract's "above the included amount" price model was wrong
    for this account.
  - Re-running `run_experiment` with the same `run_name` appends items to the existing
    Langfuse run, so "run it again" checks should use `--dry-run` or a new label.
  - A background `make verify-fast` shares the test database with anything else that runs
    pytest; delegated briefs must say "do not run the gate" while one is in flight.
  - Committing one phase's slice of a shared test file while a sibling phase has already
    edited it: snapshot the file at gate time and stage the snapshot blob with
    `git update-index --cacheinfo`.
  - Codex-authored tests missed three contract-listed checks while the product code was
    clean; the lead's review budget belongs on delegated tests.

## Deferred work

`docs/deferred.md` § Search recall baselines (task 046 seams): P2 grey-literature keys with
the raw Overton arm (design at `37d496c`), the "swap" slice, S3 upload of the cache, the
ranking-stability test.
