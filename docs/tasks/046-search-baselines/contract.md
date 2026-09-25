# Task contract: 046-search-baselines

> **Status:** drafted, adversarial review folded in (2026-09-25); P2 deferred by owner
> (2026-09-25). Contract approved (before planning): _pending · owner_ · Plan approved
> (before implementation): _pending · owner_ · ADR: none.

## Goal

Find out what a good search recall number looks like, so we can judge the numbers our own
pipeline gets. Today the pipeline finds 5.6% of a review's reference list at rapid depth
and 15.3% at deep depth (see `scripts/evals/search/results/history.md`). We do not know if
that is bad, normal, or good, because we have nothing to compare it with.

The comparison is a set of **baselines**: the simplest possible search against three
services. One plain-text search per review, one service, no language model, no screening,
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
   Langfuse dataset and each arm (§ Arms), sends one search, fetches result pages up to a
   cap, maps the results to scoring keys, and scores recall. Uploads one Langfuse dataset
   run per arm and cap with the scores listed in D6. Prints a summary table. (P1, P3)
2. **`scripts/evals/search/history.py`** — a cost column, summed per run (D4). (P4)
3. **`scripts/evals/search/test_metrics.py`** — self-checks for the new pure functions
   (§ Acceptance checks).
4. **`scripts/evals/search/README.md`** — a section on the baselines, in plain language.
   **`results/history.md`** — the rows from one real run of every arm at every cap, with
   notes.
5. **`backend/.env.example`** — the two new key names, empty.

Shipped means: the numbers exist in Langfuse and in `history.md`, and a reader can see,
for the same four reviews, recall and cost per arm next to recall and cost for the
pipeline's existing rapid, standard and deep rows from 2026-09-22, which were measured on
the same ground truth.

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
| **HTTP request** | One round trip to a service over the web. One page of results. `n_api_calls` counts these, including failed ones. |
| **Cap** | How many results an arm keeps for one review. The baselines run at several caps so each can be compared with the pipeline at a similar number of candidates. |
| **Candidates kept** | The number of documents a run ended up with after removing duplicates. `n_candidates_kept` in Langfuse. Compare recall between runs with similar values of this, not between runs with similar numbers of HTTP requests. |
| **Langfuse** | The service where the eval stores its results. A **dataset** holds the ground truth. A **dataset run** is one setting (one arm at one cap, or one pipeline depth) scored over the selected reviews. A **trace** is the record of one review's run inside it, and carries that review's **scores** (numbers) and **metadata** (labels such as the arm name and the cap). |
| **Pipeline** | Policy Atlas's own search stage: a language model writes many queries, the app fans them out to OpenAlex and Overton, and later depths screen and re-query. Measured by `production_recall.py`. |
| **API** | Application programming interface. The way a program asks a service for records over the web. |
| **Semantic Scholar** | A free scholarly search service run by the Allen Institute for AI, with its own relevance ranking. |
| **Consensus** | A paid scholarly search service built on top of Semantic Scholar's corpus, with its own ranking and study-type filters. |

## Arms

Three arms. Each is one search request per review, fetched in pages. Every page is one
HTTP request and counts in `n_api_calls`. Verified against the live services on 2026-09-25
except where marked ❓.

| # | Arm name | Service | Search request | Paging | Cutoff filter | Key returned | Cost |
|---|---|---|---|---|---|---|---|
| 1 | `semantic-scholar` | Semantic Scholar Academic Graph | `GET https://api.semanticscholar.org/graph/v1/paper/search?query=<intent>&fields=externalIds,title,publicationDate` — relevance-ranked. | `limit=100`, `offset`; the response's `next` gives the next offset and is absent on the last page. At most 1,000 results in total. | `publicationDateOrYear=:<cutoff>` | `externalIds.DOI` | Free with a key (about 1 request per second). Without a key the shared pool answers 429 at once. |
| 2 | `consensus` | Consensus | `GET https://api.consensus.app/v1/search?query=<intent>`, header `x-api-key`. | `page`, `page_size`; the response's `is_end` is true on the last page. Default page size 20; ❓ largest allowed page size, confirmed by the lead before the live run. | `year_max` + `month_max` of the cutoff (month granularity; see D2) | `doi` | Paid: $0.05 per call above the plan's monthly credits, plus one credit per 100 papers (pricing page, 2026-09-25). |
| 3 | `openalex-raw` | OpenAlex | `GET https://api.openalex.org/works?search=<intent>&select=id,doi,display_name,publication_date` — OpenAlex's own relevance search over title, abstract and full text. Sent through `ground_truth.openalex_get`. | `per-page=200`, `page`; stop when a page returns fewer than 200. | `filter=to_publication_date:<cutoff>` | `doi` | Free. OpenAlex reports `meta.cost_usd` in every response; the script sums it. |

A raw Overton arm was in the draft and is deferred with P2: with no Overton ids in the
ground truth it could only score DOI hits, and the sweep's `found_by_backend` already
shows Overton's DOI contribution inside the pipeline. Add it when P2 lands.

The pipeline's own rapid depth is the comparison row. It keeps up to 50 candidates per
backend per round, so its `n_candidates_kept` is at most 100.

## Decisions

- **D1 — One search, verbatim.** Each arm receives the dataset's `intent` text unchanged,
  once per review. No rewriting, no keyword extraction, no language model. This favours
  services with relevance ranking over keyword matching. That is the point of the test,
  and the notes say so.
- **D2 — Caps: 50, 100, 200 and 1,000.** 50, 100 and 200 match the pipeline's per-backend
  record caps at rapid, standard and deep. 1,000 is the most Semantic Scholar's relevance
  search returns and is the ceiling row. At a page size of 20, Consensus needs 3 + 5 + 10
  + 50 = 68 pages per review, 272 HTTP requests for four reviews: $13.60 in call charges
  above credits plus about 55 paper credits. The plan's preflight step confirms the money
  and the page size before anything runs. Consensus filters dates by month, so its cutoff
  is the cutoff's year and month. It can include papers from up to 30 days after the
  cutoff day. All of those are still before the review was published, so none can be the
  review itself. The notes say Consensus is helped by this by a small, unknown amount.
- **D3 — Same scoring, no title matching.** Results are mapped to scoring keys with
  `ground_truth.record_key` and scored with the same recall formula as the pipeline runs.
  Titles are never used to match a result to a reference. Because every key in the ground
  truth is a DOI today (P2), the notes say the numbers are scholarly recall, for the
  baselines and for the pipeline alike.
- **D4 — Cost is a dollar figure per review, summed per run, and labelled by what it
  counts.** Two figures, never mixed:
  - `api_cost_usd`, a Langfuse score on every baseline review trace: OpenAlex's
    `meta.cost_usd` summed over its responses; Consensus $0.05 per HTTP request plus one
    credit per 100 papers returned, with the credit price and the pricing date pinned in
    the script's price table; Semantic Scholar $0.00. Failed requests are counted as
    charged. Language-model cost is $0.00 because no baseline uses one.
  - `llm_cost_usd`, for pipeline runs: Langfuse's own `total_cost` per trace (the field
    exists in the installed SDK as `TraceWithFullDetails.total_cost`), which is the
    language-model spend Langfuse attributes to that review's run.
  `history.py` prints one cost column per run, as the **sum** over that run's reviews, and
  marks each figure `api` or `llm`. Neither figure includes the flat subscriptions
  (Overton, OpenAlex premium, the Consensus plan fee), compute, or Langfuse. The column
  header says "variable cost", and the README says what is left out.
- **D5 — ⏸ Deferred with P2.** Was: suggest missing scoring keys by title lookup. See P2.
- **D6 — Scores and run metadata match the existing runs.** Baseline traces carry exactly
  these scores: `search_recall`, `n_found`, `n_api_calls`, `n_failed_calls`,
  `n_api_records`, `n_candidates_kept` (the existing search-stage names, same meanings)
  and `api_cost_usd`. No screening scores, because nothing is screened. Run metadata uses
  the keys `history.py` already reads: `experiment=retrieval-baseline`,
  `depth=single-call`, `generation_backend=<arm name>`, `record_cap_per_backend=<cap>`,
  `git_commit`. So baseline rows appear in the history table, and the only change to
  `history.py` is the cost column.
- **D7 — No pipeline code changes.** Nothing under `backend/src` changes. The baselines
  call the services with plain `httpx`, reusing `ground_truth.openalex_get` for OpenAlex.
  A Semantic Scholar backend for the pipeline itself (the "swap") is a separate slice,
  decided on these results.
- **D8 — No pipeline re-run.** The ground truth does not change in this slice, so the
  pipeline rows from 2026-09-22 (commit `b16f859`) are on the same target and are the
  comparison rows. The notes name that commit.

## Read first

- `scripts/evals/search/README.md` — how the existing eval works, end to end.
- `scripts/evals/search/ground_truth.py` — `record_key`, `normalize_doi`, `GroundTruth`,
  `openalex_get`.
- `scripts/evals/search/sweep_record_cap.py` — `SCORE_KEYS`, `score_summary`, and how a
  run is uploaded.
- `scripts/evals/search/production_recall.py` — `_run_depth` (run naming and metadata),
  `select_items`, `_ground_truth_from_item`.
- `scripts/evals/search/history.py` — the metadata keys it prints and how it averages.
- No product spec owns the evals. `docs/deferred.md` § record cap notes that the eval is
  the acceptance test for the caps.

## Scope / Out of scope

- **In:** the five files under § Deliverable. New environment variables
  `SEMANTIC_SCHOLAR_API_KEY` and `CONSENSUS_API_KEY`, read from `backend/.env`.
- **Out:** anything under `backend/src`. Any change to the ground truth or to
  `ground_truth_dataset.py` (P2, deferred). A raw Overton arm. Screening, multi-round
  search, query rewriting, citation snowballing. A Semantic Scholar or Consensus backend
  for the pipeline. Precision. Re-running any pipeline depth. A per-reference CSV
  (Langfuse traces and the printed summary answer both questions). The parked GitHub
  Actions workflow stays parked.

## Constraints & approval gates

- **Dependencies:** none added. `httpx`, `pandas` and `langfuse` are already in the
  backend project.
- **Egress:** these are developer-run scripts, not the running product. Not gated.
  Consensus is a paid service; the plan's preflight states the expected spend before any
  live call.
- **Secrets:** the two keys live in `backend/.env` only. `.env.example` gets the names.
- **Schema, auth, CI, production config, public interfaces:** untouched.
- **Inputs:** the Langfuse dataset only. The ground-truth CSVs are not needed.
- **Rate limits and retries:** Semantic Scholar about 1 request per second with a key.
  OpenAlex 0.2 s between requests (the pipeline's interval). Consensus ❓ not documented.
  Every arm retries 429 and 5xx with a doubling wait, four attempts, then counts the
  request as failed and continues; a failed request never stops the run.

## Public / private boundary

- Public: the scripts, tests, README, `history.md` rows (mean recall, counts, cost).
- Private: API keys; Langfuse traces.

## Model route

n/a. No language model runs in this slice.

## Disciplines binding this slice

- **Honest absence.** A run with failed requests says so, and its recall is marked as an
  undercount. The notes say the target is scholarly only (P2).
- **Don't flatten status.** ❓ and ⏸ items stay as marked until settled.
- **Flag, don't drop.** Differences between arms that favour one side (D1, D2) are written
  into the history notes.

## Stop conditions

Halt and escalate when: a service changes its API shape so an arm cannot be built as
specified; the Consensus preflight puts the full run above £30; or scope would grow past
this slice.

## Acceptance checks

- `make verify` green (no backend code changes, so this confirms nothing broke).
- `uv run --project backend python scripts/evals/search/test_metrics.py` green, with new
  self-checks for: each arm's record-to-key mapping from a saved sample response; each
  arm's cutoff filter (including Consensus month rounding); each arm's paging (stops at
  the cap, stops on the service's end signal, handles a full last page with no
  continuation and an empty page); 429 retried then counted as failed without raising;
  the cost sum per arm including the OpenAlex `meta.cost_usd` path; the baseline
  evaluator emits `api_cost_usd`; duplicates on key count once; `history.py` sums cost
  across a run's reviews rather than averaging.
- Deterministic vs AI eval: all checks here are deterministic. The recall numbers are
  measurements, not pass/fail thresholds.
- **Live check (pinned):** one full run of `baseline_recall.py` over all three arms, all
  four caps, all four reviews, preceded by the spend and page-size preflight. Expected
  wall time under 15 minutes; the Consensus part is unknown until its rate limit is seen
  in the preflight.

## Verification evidence expected

In `verification.md`: the commands run and their results; the summary table the script
printed; the Langfuse run URLs; the `history.md` rows added; the Consensus preflight and
spend; a note on any failed requests; the diff summary; confirmation that no key is
committed.

## Risk tier & review focus

**Tier 2.** New developer scripts, no product code, no gated surface. The owner asked for
adversarial review of the contract and the plan, so both ran (read-only Codex briefs,
2026-09-25); their findings are folded in. The P2 deferral came after those reviews and
removes scope; it adds none.

Review focus: is the comparison fair (same intent, same cutoff, same key, same formula);
does anything favour one arm silently; is the cost number labelled honestly; scope creep
into pipeline code or into the ground truth.
