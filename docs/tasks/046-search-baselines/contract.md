# Task contract: 046-search-baselines

> **Status:** drafted, adversarial review folded in (2026-09-25); P2 deferred and
> fetch-once cache added by owner (2026-09-25). Contract approved (before planning):
> 2026-09-25 · owner · Plan approved (before implementation): 2026-09-25 · owner · ADR: none.
> **Amendment (build, 2026-09-25, owner-approved):** a fourth arm, `semantic-scholar-snippet`,
> added after the live run showed arm 1 is a keyword engine (see § Arms).
> **Review note (2026-09-25):** D4's Consensus price model ("above the included monthly
> amount") is stale for our account, which is billed on every call. The `api_cost_usd`
> figure is the price of the result pages that cover the cap at the echoed page size, as
> plan S7 pins; the wording "fetching that cap on its own" was corrected in the README and
> `history.md` (see verification.md § Review findings).

## Goal

Find out what a good search recall number looks like, so we can judge the numbers our own
pipeline gets. Today the pipeline finds 5.6% of a review's reference list at rapid depth
and 15.3% at deep depth (see `scripts/evals/search/results/history.md`). We do not know if
that is bad, normal, or good, because we have nothing to compare it with.

The comparison is a set of **baselines**: the simplest possible search against three
services (four arms: Semantic Scholar offers two different search engines). One plain-text search per review, one service, no language model, no screening,
no second round. Score the results against the same ground truth, with the same recall
formula, and record them in the same place as the pipeline's own runs.

Two questions this answers:

1. **What does good look like?** If one search on Semantic Scholar finds 30% of the
   references, our 5.6% has a lot of room. If it finds 8%, the ground truth itself is hard
   and our number is near the ceiling.
2. **Should we consider swapping OpenAlex for another service?** The baselines give
   evidence on two things that are mixed together today: the *corpus* (which documents a
   service knows about) and the *retrieval method* (how the query is written and ranked).
   Arm 3 sends one plain search to OpenAlex with no language model. If it matches or beats
   the pipeline's rapid depth at the same number of candidates kept, that is a strong sign
   that our query generation is the weak part, not OpenAlex. It is a sign, not proof: the
   pipeline sends many generated queries and then trims, so the two are not a controlled
   pair. The notes say so.

This slice also puts a cost number on every run (P3), so "cheaper" and "better" can be
traded off.

## Problems

One number each. The rubric and the plan use the same numbers.

- **P1 — No baseline.** There is no simple, no-LLM search recall number to compare the
  pipeline against.
- **P2 — Grey literature cannot be scored. ⏸ Deferred (owner, 2026-09-25).** The ground
  truth has 232 references that count. 34 of them have no scoring key: no DOI and no
  Overton id. 31 of these 34 belong to one review, the loneliness review, which cites
  government reports and charity publications. A reference with no key is dropped from
  the target. So if Overton returned exactly that government report, we could not tell.
  This is not a limit of Overton or of the scoring code, which already accepts Overton
  ids (see `ground_truth.record_key`). It is a gap in the ground-truth data: the
  `overton_id` column was never filled. Fixing it means labelling work and a change to
  the ground truth. The owner plans a larger expansion of the ground truth to more
  reviews, and this fix belongs in that work, not here. Until then every eval, this one
  and the pipeline's, measures scholarly recall only. The design that was drafted for it
  (a suggest-only title lookup on OpenAlex and Overton, with a human accepting each key)
  is kept in git history at commit `37d496c` for that later slice.
- **P3 — Cost is not measured.** The eval records recall and call counts. It does not
  record what a run cost in money.
- **P4 — History table has no cost column.** `history.py` prints recall per run. It cannot
  show cost next to it, even for the pipeline runs that already exist.

## Deliverable

One pull request on `task/046-search-baselines` that lands:

1. **`scripts/evals/search/baseline_recall.py`** — new script. For each review in the
   Langfuse dataset and each arm (§ Arms), sends one search and fetches every result page
   up to the service's 1,000-result ceiling, **once**, and saves the raw pages to a local
   cache (D9). From the cache it scores recall at each cap, uploads one Langfuse dataset
   run per arm and cap with the scores listed in D6, and prints a summary table. A second
   run reads the cache and makes no service calls. (P1, P3)
2. **`scripts/evals/search/history.py`** — a cost column, summed per run (D4). (P4)
3. **`scripts/evals/search/test_metrics.py`** — self-checks for the new pure functions
   (§ Acceptance checks).
4. **`scripts/evals/search/README.md`** — a section on the baselines and the cache, in
   plain language. **`results/history.md`** — the rows from one real run of every arm at
   every cap, with notes.
5. **`backend/.env.example`** — the two new key names, empty.

Shipped means: the numbers exist in Langfuse and in `history.md`, the raw results sit in
the local cache, and a reader can see, for the same four reviews, recall and cost per arm
next to recall and cost for the pipeline's existing rapid, standard and deep rows from
2026-09-22, which were measured on the same ground truth.

## Terms

| Term | Meaning |
|---|---|
| **Ground truth** | Four published evidence reviews and, for each, the list of works it cites. Held as the Langfuse dataset `retrieval-ground-truth`. This slice reads it and does not change it. |
| **Review** | One of the four evidence reviews in the ground truth. Each gives one intent, one cutoff date and one reference list. |
| **Intent** | The search text. It is the review's title with the "a systematic review" tail removed, made by `ground_truth.clean_review_title`. Every arm and the pipeline receive this same text. |
| **Cutoff** | `published_before`: one month before the review was published. Nothing published after it counts, because the review could not have cited it. Each arm applies it with the service's own date filter (§ Arms). |
| **Reference** | One work a review cites. Only rows labelled `content` count; methodology citations do not. |
| **Scoring key** | The identity a found document is matched on: its DOI in lowercase, or `overton:<id>` for an Overton policy document with no DOI. Defined once in `ground_truth.record_key`. Today every key in the ground truth is a DOI (see P2). |
| **DOI** | Digital Object Identifier. The permanent id most published papers carry, e.g. `10.1016/s0140-6736(18)31612-x`. |
| **Overton id** | Overton's own id for a policy document, the `policy_document_id` field. The only stable id for grey literature. None are in the ground truth yet (P2). |
| **Grey literature** | Reports and publications from governments, charities and think tanks. Usually no DOI. Overton indexes them; the scholarly services mostly do not. |
| **Recall** | Found references that count ÷ all references that count, for one review. Reported per review and as the mean over the four reviews. This slice, like the existing eval, does not score precision. |
| **Arm** | One service searched in one fixed way (§ Arms). The word comes from experiments: one arm per treatment. |
| **Search request** | One query sent to one service for one review. A service answers in pages, so one search request is several HTTP requests. |
| **HTTP request** | One round trip to a service over the web. One page of results. |
| **Consensus call** | Consensus's billing unit. One request that returns up to 100 papers is one call; 101 to 200 papers is two calls, and so on, with a minimum of one call per request. This is not the same as an HTTP request. |
| **Cap** | How many results an arm keeps for one review: the first N results in the order the service ranked them. The baselines report every cap from one fetch (D9), so each can be compared with the pipeline at a similar number of candidates. |
| **Candidates kept** | The number of documents left after removing duplicates from the first N results. `n_candidates_kept` in Langfuse. Compare recall between runs with similar values of this, not between runs with similar numbers of HTTP requests. |
| **Cache** | One JSON file per arm and review under `scripts/evals/search/results/cache/`, holding the raw result pages exactly as the service returned them, the request that produced them, and the time. Git ignores everything under `results/` except `history.md`, so the cache never enters the repo. |
| **Langfuse** | The service where the eval stores its results. A **dataset** holds the ground truth. A **dataset run** is one setting (one arm at one cap, or one pipeline depth) scored over the selected reviews. A **trace** is the record of one review's run inside it, and carries that review's **scores** (numbers) and **metadata** (labels such as the arm name and the cap). |
| **Pipeline** | Policy Atlas's own search stage: a language model writes many queries, the app fans them out to OpenAlex and Overton, and later depths screen and re-query. Measured by `production_recall.py`. |
| **API** | Application programming interface. The way a program asks a service for records over the web. |
| **Semantic Scholar** | A free scholarly search service run by the Allen Institute for AI, with its own relevance ranking. |
| **Consensus** | A paid scholarly search service built on top of Semantic Scholar's corpus, with its own ranking and study-type filters. |

## Arms

Four arms. Each is one search request per review, fetched in pages to the service's
1,000-result ceiling and cached (D9). Arm 1b was added during the build (owner, 2026-09-25):
the live run showed arm 1 is Semantic Scholar's **keyword** engine (the docs for its bulk
variant say "all terms in the query must be present in the paper"; it returned 0, 1 and 22
papers for three intents), while the same API offers a **semantic** engine, `snippet/search`,
which "returns the text snippets that most closely match the query". Both are kept: arm 1
shows what a verbatim intent does to a keyword engine, arm 1b what Semantic Scholar's own
semantic retrieval does with it. Facts below come from the services' own
documentation, read on 2026-09-25 (Consensus: `docs.consensus.app`, API plans and access
page and the search endpoint's parameter table; Semantic Scholar: the published API
specification at `api.semanticscholar.org/graph/v1/swagger.json`), and from live probes
the same day.

| # | Arm name | Service | Search request | Paging | Cutoff filter | Key returned | Cost |
|---|---|---|---|---|---|---|---|
| 1 | `semantic-scholar` | Semantic Scholar Academic Graph | `GET https://api.semanticscholar.org/graph/v1/paper/search?query=<intent>&fields=externalIds,title,publicationDate`, header `x-api-key`. Relevance-ranked. The spec says hyphenated terms match nothing, so hyphens in the intent are sent as spaces (the one allowed change to the text; D1). | `limit=100` (the maximum), `offset`; the response's `next` is the next offset and is absent on the last page. At most 1,000 results per query. | `publicationDateOrYear=:<cutoff>` (inclusive) | `externalIds.DOI` | Free with a key, about 1 request per second. Without a key the shared pool answers 429 at once. |
| 1b | `semantic-scholar-snippet` | Semantic Scholar snippet search | `GET https://api.semanticscholar.org/graph/v1/snippet/search?query=<intent>&limit=1000&fields=snippet.snippetKind`, header `x-api-key`. Ranked by meaning over passages from title, abstract and body text (`retrievalVersion` `pa1-v1` on 2026-09-25). Intent verbatim, no hyphen rule. Each snippet names its paper by `corpusId` only, so a second step maps the unique papers, in order of first appearance, to DOIs with `POST /graph/v1/paper/batch?fields=externalIds,title` (500 ids per call). | No paging: one request returns up to 1,000 snippets. About 550 unique papers per 1,000 snippets, so the cap-1000 row holds fewer than 1,000 candidates; a cap of N is the first N unique papers. | `publicationDateOrYear=:<cutoff>` (inclusive) | `externalIds.DOI` from the lookup | Free with a key. Three requests per review. Body-text snippets exist only for open-access papers, so the arm leans towards them (the notes say so). |
| 2 | `consensus` | Consensus | `GET https://api.consensus.app/v1/search?query=<intent>`, header `x-api-key`. Relevance-ranked over about 220 million papers. Every result carries `doi`, `title`, `publish_year`, `publish_date`. | `page` is **zero-indexed**; `page_size` defaults to 20 and is silently capped to the plan's maximum (Pro and Teams 300, Deep 750), so the script reads the `page_size` echoed back. `is_end` is true on the last page; `next_page` gives the next. At most 1,000 results per query. Pages after the first need a paid plan. | `year_max` + `month_max` of the cutoff (inclusive, month granularity; see D2) | `doi` | Included calls per month: Pro and Teams 500, Deep 2,000. One call per 100 papers returned, rounded up. Above the included amount, $0.05 per call, only if "additional usage" is switched on in the dashboard. Rate limit 1 request per second; a faster request gets 429 with a `retry-after` header. |
| 3 | `openalex-raw` | OpenAlex | `GET https://api.openalex.org/works?search=<intent>&select=id,doi,display_name,publication_date` — OpenAlex's own relevance search over title, abstract and full text. Sent through `ground_truth.openalex_get`. | `per-page=200`, `page` from 1; stop when a page returns fewer than 200, or after page 5 (1,000 results, to match the other two). | `filter=to_publication_date:<cutoff>` (inclusive) | `doi` | Free. OpenAlex reports `meta.cost_usd` in every response; the script records it. |

A raw Overton arm was in the draft and is deferred with P2: with no Overton ids in the
ground truth it could only score DOI hits, and the sweep's `found_by_backend` already
shows Overton's DOI contribution inside the pipeline. Add it when P2 lands.

The pipeline's own rapid depth is the comparison row. It keeps up to 50 candidates per
backend per round, so its `n_candidates_kept` is at most 100.

## Decisions

- **D1 — One search, verbatim.** Each arm receives the dataset's `intent` text unchanged,
  once per review. No rewriting, no keyword extraction, no language model. The single
  exception is documented by the service: Semantic Scholar matches nothing on hyphenated
  terms, so hyphens become spaces for that arm only. This favours services with
  relevance ranking over keyword matching. That is the point of the test, and the notes
  say so.
- **D2 — Caps: 50, 100, 200 and 1,000, all from one fetch.** 50, 100 and 200 match the
  pipeline's per-backend record caps at rapid, standard and deep. 1,000 is every service's
  ceiling and is the ceiling row. Because each arm is fetched once to 1,000 and cached
  (D9), the caps cost nothing extra. Consensus filters dates by month, so its cutoff is
  the cutoff's year and month. It can include papers from up to 30 days after the cutoff
  day. All of those are still before the review was published, so none can be the review
  itself. The notes say Consensus is helped by this by a small, unknown amount.
- **D3 — Same scoring, no title matching.** Results are mapped to scoring keys with
  `ground_truth.record_key` and scored with the same recall formula as the pipeline runs.
  Titles are never used to match a result to a reference. A cap of N means the first N
  results in the service's own order, then duplicates on key are removed. Because every
  key in the ground truth is a DOI today (P2), the notes say the numbers are scholarly
  recall, for the baselines and for the pipeline alike.
- **D4 — Cost is a dollar figure per review, summed per run, and labelled by what it
  counts.** Two figures, never mixed:
  - `api_cost_usd`, a Langfuse score on every baseline review trace. It is the **computed
    price of fetching that cap on its own**, from the arm's page size and price table,
    whether the cache or the service supplied the results. Consensus: one call per 100
    papers returned, rounded up, at $0.05 per call, the price above the included monthly
    amount; the pricing date is pinned in the price table. OpenAlex: the `meta.cost_usd`
    of the pages needed to reach the cap, read from the cache. Semantic Scholar: $0.00.
    Language-model cost is $0.00 because no baseline uses one. The money the run actually
    spent is separate and goes in `verification.md`; with the cache it is spent once.
  - `llm_cost_usd`, for pipeline runs: Langfuse's own `total_cost` per trace (the field
    exists in the installed SDK as `TraceWithFullDetails.total_cost`), which is the
    language-model spend Langfuse attributes to that review's run.
  `history.py` prints one cost column per run, as the **sum** over that run's reviews, and
  marks each figure `api` or `llm`. Neither figure includes the flat subscriptions
  (Overton, OpenAlex premium, the Consensus plan fee), compute, or Langfuse. The column
  header says "variable cost", and the README says what is left out.
- **D5 — ⏸ Deferred with P2.** Was: suggest missing scoring keys by title lookup. See P2.
- **D6 — Scores and run metadata match the existing runs.** Baseline traces carry exactly
  these scores: `search_recall`, `n_found`, `n_api_calls` (HTTP requests needed to reach
  the cap), `n_failed_calls`, `n_api_records` (results returned in those requests),
  `n_candidates_kept` (the existing search-stage names, same meanings) and `api_cost_usd`.
  No screening scores, because nothing is screened. Run metadata uses the keys
  `history.py` already reads: `experiment=retrieval-baseline`, `depth=single-call`,
  `generation_backend=<arm name>`, `record_cap_per_backend=<cap>`, `git_commit`, plus
  `fetched_at` (when the cache was filled) so a reader knows how old the results are. So
  baseline rows appear in the history table, and the only change to `history.py` is the
  cost column.
- **D7 — No pipeline code changes.** Nothing under `backend/src` changes. The baselines
  call the services with plain `httpx`, reusing `ground_truth.openalex_get` for OpenAlex.
  A Semantic Scholar backend for the pipeline itself (the "swap") is a separate slice,
  decided on these results.
- **D8 — No pipeline re-run.** The ground truth does not change in this slice, so the
  pipeline rows from 2026-09-22 (commit `b16f859`) are on the same target and are the
  comparison rows. The notes name that commit.
- **D9 — Fetch once, cache locally, score offline.** For each arm and review the script
  makes one search request, pages to 1,000 results, and writes the raw pages to
  `results/cache/<arm>/<review id hash>.json` with the request parameters (never the
  key), the echoed page size, and the fetch time. Every later run, and every cap, reads
  that file; the service is not called again unless `--refresh` is passed. Reasons: the
  results are worth keeping (they show which papers each service ranks where), the
  Consensus spend happens once, and re-scoring after a code fix is free. Two things are
  deliberately not in this slice and go to `docs/deferred.md`: uploading the cache to S3
  so it outlives one laptop, and a stability test that fetches the same query several
  times to see how much the ranking moves.

## Read first

- `scripts/evals/search/README.md` — how the existing eval works, end to end.
- `scripts/evals/search/ground_truth.py` — `record_key`, `normalize_doi`, `GroundTruth`,
  `openalex_get`.
- `scripts/evals/search/sweep_record_cap.py` — `SCORE_KEYS`, `score_summary`, and how a
  run is uploaded.
- `scripts/evals/search/production_recall.py` — `_run_depth` (run naming and metadata),
  `select_items`, `_ground_truth_from_item`.
- `scripts/evals/search/history.py` — the metadata keys it prints and how it averages.
- Consensus: `https://docs.consensus.app/api-plans-and-access` and the endpoint reference
  `https://docs.consensus.app/api-reference/query-for-relevant-papers`. The site blocks
  plain fetchers; `https://docs.consensus.app/llms-full.txt` is the same content as text.
- Semantic Scholar: `https://api.semanticscholar.org/graph/v1/swagger.json`, path
  `/paper/search`.
- No product spec owns the evals. `docs/deferred.md` § record cap notes that the eval is
  the acceptance test for the caps.

## Scope / Out of scope

- **In:** the five files under § Deliverable. New environment variables
  `SEMANTIC_SCHOLAR_API_KEY` and `CONSENSUS_API_KEY`, read from `backend/.env`. The
  local cache directory.
- **Out:** anything under `backend/src`. Any change to the ground truth or to
  `ground_truth_dataset.py` (P2, deferred). A raw Overton arm. Screening, multi-round
  search, query rewriting, citation snowballing. A Semantic Scholar or Consensus backend
  for the pipeline. Precision. Re-running any pipeline depth. Uploading the cache to S3.
  Repeat fetches to test ranking stability. A per-reference CSV (the cache holds the raw
  results, Langfuse holds the scores). The parked GitHub Actions workflow stays parked.

## Constraints & approval gates

- **Dependencies:** none added. `httpx`, `pandas` and `langfuse` are already in the
  backend project.
- **Egress:** these are developer-run scripts, not the running product. Not gated.
  Consensus is a paid service; the plan's preflight states the expected calls before any
  live request, and the fetch happens once.
- **Secrets:** the two keys live in `backend/.env` only. `.env.example` gets the names.
  The cache stores request parameters without the key.
- **Schema, auth, CI, production config, public interfaces:** untouched.
- **Inputs:** the Langfuse dataset only. The ground-truth CSVs are not needed.
- **Rate limits and retries:** Semantic Scholar and Consensus 1 request per second with a
  key. OpenAlex 0.2 s between requests (the pipeline's interval). On 429 the script waits
  the `retry-after` header when present, else 1, 2, 4 s; 5xx the same waits; four attempts,
  then the request counts as failed and the fetch for that review stops, never raises. A
  partial fetch is cached with a `complete: false` flag and is refetched next run.

## Public / private boundary

- Public: the scripts, tests, README, `history.md` rows (mean recall, counts, cost).
- Private: API keys; Langfuse traces; the cache (git-ignored; contains abstracts and
  publisher metadata from paid services).

## Model route

n/a. No language model runs in this slice.

## Disciplines binding this slice

- **Honest absence.** A run with failed requests says so, and its recall is marked as an
  undercount. The notes say the target is scholarly only (P2).
- **Don't flatten status.** ⏸ items stay as marked until settled.
- **Flag, don't drop.** Differences between arms that favour one side (D1, D2) are written
  into the history notes.

## Stop conditions

Halt and escalate when: a service changes its API shape so an arm cannot be built as
specified; the Consensus preflight shows fewer included calls remaining than the fetch
needs and "additional usage" is off; or scope would grow past this slice.

## Acceptance checks

- `make verify` green (no backend code changes, so this confirms nothing broke).
- `uv run --project backend python scripts/evals/search/test_metrics.py` green, with new
  self-checks for: each arm's record-to-key mapping from a saved sample response; each
  arm's cutoff filter (including Consensus month rounding); each arm's paging (stops at
  1,000, stops on the service's end signal, handles a full last page with no
  continuation and an empty page; Consensus pages start at 0 and the echoed `page_size`
  is used); the Semantic Scholar hyphen rule; 429 with `retry-after` waited and retried,
  then counted as failed without raising; cache round trip (write, read, same scores as
  the live path; `complete: false` triggers a refetch; `--refresh` refetches); cap slicing
  (first N in order, then dedup); the cost computation per arm and cap including the
  OpenAlex `meta.cost_usd` path and the Consensus call rounding; the baseline evaluator
  emits `api_cost_usd`; `history.py` sums cost across a run's reviews rather than
  averaging.
- Deterministic vs AI eval: all checks here are deterministic. The recall numbers are
  measurements, not pass/fail thresholds.
- Arm 1b self-checks: one search request with `limit=1000` and the cutoff; unique papers in
  snippet order; lookups in batches of 500 with `CorpusId:<id>` ids; a paper missing from
  the lookup has no key; every cap counts all requests (search plus lookups); a failing
  lookup counts as failed and leaves the fetch incomplete; cost 0.
- **Live check (pinned):** one full fetch of all three arms over all four reviews to
  1,000 results, then scoring at all four caps from the cache, preceded by the Consensus
  preflight. Expected: Semantic Scholar 40 requests, about 1 minute; OpenAlex 20 requests,
  under 1 minute; Consensus 16 requests at page size 300 (or 8 at 750), 40 calls, about 1
  minute; well under 15 minutes in total. A second run of the script with no flags makes
  zero requests.

## Verification evidence expected

In `verification.md`: the commands run and their results; the summary table the script
printed; the Langfuse run URLs; the `history.md` rows added; the Consensus preflight
(plan, included calls remaining, echoed page size) and the calls the fetch used; a note
on any failed requests; the cache files' names and sizes; the diff summary; confirmation
that no key or cache file is committed.

## Risk tier & review focus

**Tier 2.** New developer scripts, no product code, no gated surface. The owner asked for
adversarial review of the contract and the plan, so both ran (read-only Codex briefs,
2026-09-25); their findings are folded in. Two owner changes came after those reviews:
the P2 deferral removes scope, and D9 (fetch once, cache) replaces repeated fetching with
one fetch and offline slicing. Neither adds a new external surface.

Review focus: is the comparison fair (same intent, same cutoff, same key, same formula);
does anything favour one arm silently; is the cost number labelled honestly; does the
cache path score identically to the live path; scope creep into pipeline code or into
the ground truth.
