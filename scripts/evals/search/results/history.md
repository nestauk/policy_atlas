# Search eval history

The headline runs. Langfuse holds every run and all the
detail. This file holds only the headline numbers of the runs,
with a note on each, so the history of recall lives in git next to the code.
The run column is the run name. Search for it in the Langfuse dataset
`retrieval-ground-truth` to see the detail.

Smoke tests, partial runs and repeats of the same setting are left out unless
they tell you something.

## How to add a run

1. Print the rows for every run in Langfuse:

       uv run --project backend --env-file backend/.env python scripts/evals/search/history.py --since 2026-09-24

2. Copy the row(s) you want into the table below and fill in the notes cell:
   what changed, and any caveat that affects how the number should be read.

## How to read the table

- **Search recall** is the share of a review's reference list that the search
  stage found, averaged over the reviews in the run. **Screen recall** is the
  same after the screening stage. A dash means the run did not screen.
- **Reviews** is how many reviews the run covered. The dataset has 4. A run
  with fewer is not comparable with a full run.
- **Failed calls** above 0 means a provider call failed after all retries, so
  that run's recall is an undercount caused by the provider, not the code.
- **Variable cost** is the run's cost summed over its reviews, with a label for what it
  counts. `llm` is the language-model spend Langfuse attributes to the run's traces
  (pipeline runs). `api` is the **computed** price of the search-service calls for that
  cap, from the service's price table (baseline runs): the price of the result pages
  that cover the cap at the page size the service returned, not what the run spent,
  because the baselines call each service once and score every cap from the cached
  pages. Consensus returns 300 results per request, so its caps 50 to 200 all cost one
  request of three calls; a request sized to the cap would cost less. Neither includes flat subscriptions (Overton,
  OpenAlex premium, the Consensus plan), compute, or Langfuse itself.
- **Baseline rows** (`experiment` = `baseline`, `depth` = `single-call`) are one plain
  search of the review's intent on one service, no language model, no screening, no
  second round. `backend` is the service, `record cap` is how many of the service's
  ranked results were kept. See README section 5 for how to read them next to the
  pipeline rows.

## Runs

| date | commit | experiment | depth | backend | record cap | reviews | search recall | screen recall | failed calls | variable cost | run | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-10 | 422bf39 | cap-prompt-sweep | rapid | shared | 250 | 4 | 9.3% | - | 0 | $0.0037 llm | 2026-09-10-422bf39/shared-cap250-r1 | First full sweep, one repeat. Caps 50 and 100 were not run. |
| 2026-09-10 | 422bf39 | cap-prompt-sweep | rapid | shared | 500 | 4 | 17.6% | - | 0 | $0.0037 llm | 2026-09-10-422bf39/shared-cap500-r1 |  |
| 2026-09-10 | 422bf39 | cap-prompt-sweep | rapid | shared | 1000 | 4 | 16.9% | - | 0 | $0.0036 llm | 2026-09-10-422bf39/shared-cap1000-r1 |  |
| 2026-09-10 | 422bf39 | cap-prompt-sweep | rapid | shared | 2000 | 4 | 19.9% | - | 0 | $0.0036 llm | 2026-09-10-422bf39/shared-cap2000-r1 |  |
| 2026-09-10 | 422bf39 | cap-prompt-sweep | rapid | per-provider | 250 | 3 | 15.7% | - | 0 | $0.02 llm | 2026-09-10-422bf39/per-provider-cap250-r1 | Only 3 reviews: the loneliness review failed. Average not comparable. |
| 2026-09-10 | 422bf39 | cap-prompt-sweep | rapid | per-provider | 500 | 4 | 14.3% | - | 0 | $0.02 llm | 2026-09-10-422bf39/per-provider-cap500-r1 |  |
| 2026-09-10 | 422bf39 | cap-prompt-sweep | rapid | per-provider | 1000 | 4 | 17.0% | - | 9 | $0.02 llm | 2026-09-10-422bf39/per-provider-cap1000-r1 | 9 provider calls failed after retries, so recall is an undercount. |
| 2026-09-11 | 422bf39 | cap-prompt-sweep | rapid | per-provider | 2000 | 4 | 37.2% | - | 0 | $0.02 llm | 2026-09-10-422bf39/per-provider-cap2000-r1 | Best recall so far. Per-provider prompt at cap 2000 nearly doubles the shared prompt. |
| 2026-09-22 | b16f859 | production-recall | rapid | shared | 50 | 4 | 5.6% | - | 0 | $0.0037 llm | 2026-09-22-b16f859/rapid | First measurement at the real depth constants, all 4 reviews. |
| 2026-09-22 | b16f859 | production-recall | standard | shared | 100 | 4 | 10.7% | 10.7% | 0 | $4.00 llm | 2026-09-22-b16f859/standard | Screen recall equals search recall: screening lost nothing search found. |
| 2026-09-22 | b16f859 | production-recall | deep | shared | 200 | 4 | 15.3% | 15.3% | 0 | $6.99 llm | 2026-09-22-b16f859/deep | Same as standard: screening lost nothing. |
| 2026-09-25 | 8b4a61b | baseline | single-call | semantic-scholar | 50 | 4 | 0.9% | - | 0 | $0.00 api | 2026-09-25-8b4a61b/semantic-scholar-cap50 | Notes shared by all baseline rows below. One fetch per arm and review to 1,000 results, cached 2026-09-25 (Semantic Scholar 14:56 UTC, OpenAlex 14:57 UTC, Consensus 15:00 UTC), scored at every cap from the cache. Compare with the 2026-09-22 pipeline rows at commit b16f859 (same ground truth). The target is scholarly only: every ground-truth key is a DOI, so grey literature cannot be found by any arm or by the pipeline. Same intent text, cutoff, scoring key, cap rule (first N in the service's order, then dedup) and recall formula for every arm. Three differences favour one side and are deliberate: Semantic Scholar receives hyphens as spaces (D1; no intent had a hyphen); Consensus filters by month, so it may include papers up to 30 days past the cutoff day (D2; in the cache, 1 and 9 such papers in two reviews); the snippet arm collapses snippets to papers before the cap, so its cap of N is N distinct papers drawn from a deeper list, where the other arms take the first N results and then remove duplicates. The raw-versus-pipeline comparison is a sign, not a controlled test: the pipeline sends many generated queries and trims, the baselines send one. The cost is computed, not spent. No request failed. |
| 2026-09-25 | 8b4a61b | baseline | single-call | semantic-scholar | 100 | 4 | 1.2% | - | 0 | $0.00 api | 2026-09-25-8b4a61b/semantic-scholar-cap100 | Semantic Scholar's search needs every word of the intent to match. It reported totals of 0, 1, 22 and 29,628 results for the four reviews, so three reviews had almost nothing to rank and only the loneliness review reached the 1,000 ceiling. A plain title-length query is the wrong shape for this service; its number says more about the query than the corpus. |
| 2026-09-25 | 8b4a61b | baseline | single-call | semantic-scholar | 200 | 4 | 1.5% | - | 0 | $0.00 api | 2026-09-25-8b4a61b/semantic-scholar-cap200 |  |
| 2026-09-25 | 8b4a61b | baseline | single-call | semantic-scholar | 1000 | 4 | 1.5% | - | 0 | $0.00 api | 2026-09-25-8b4a61b/semantic-scholar-cap1000 | Ceiling row. Loneliness 6% (5/84), the other three 0%. |
| 2026-09-25 | 8b4a61b | baseline | single-call | consensus | 50 | 4 | 7.6% | - | 0 | $0.60 api | 2026-09-25-8b4a61b/consensus-cap50 | Best baseline at every cap and above the pipeline's rapid depth (5.6% at cap 50, similar candidates kept) with one plain search and no language model. The month-granularity cutoff helps it by a small unknown amount (D2). |
| 2026-09-25 | 8b4a61b | baseline | single-call | consensus | 100 | 4 | 8.6% | - | 0 | $0.60 api | 2026-09-25-8b4a61b/consensus-cap100 | Pipeline standard depth: 10.7% at cap 100, with screening and re-querying. |
| 2026-09-25 | 8b4a61b | baseline | single-call | consensus | 200 | 4 | 10.4% | - | 0 | $0.60 api | 2026-09-25-8b4a61b/consensus-cap200 | Pipeline deep depth: 15.3% at cap 200. |
| 2026-09-25 | 8b4a61b | baseline | single-call | consensus | 1000 | 4 | 13.6% | - | 0 | $2.00 api | 2026-09-25-8b4a61b/consensus-cap1000 | Ceiling row. Per review: adverse childhood experiences 20% (11/55), parental leave 15% (8/52), loneliness 19% (16/84), social care 0% (0/7). Page size echoed as 300 (a Pro or Teams plan); the last request fetches positions 900-999 at size 100 because the service rejects a page that would pass 1,000. Cost is 10 calls per review at $0.05, billed on every call on our account. At caps 50 to 200 the cost column is one 300-result request (three calls, $0.15 per review); a request sized to the cap would be one call for 50 or 100 results. |
| 2026-09-25 | 8b4a61b | baseline | single-call | openalex-raw | 50 | 4 | 3.5% | - | 0 | $0.0004 api | 2026-09-25-8b4a61b/openalex-raw-cap50 | One plain OpenAlex search of the intent, no language model. Below the pipeline's rapid depth (5.6%) at a similar number of candidates kept. So the pipeline's 18 generated queries do add recall over one raw search on the same corpus, but Consensus beats both with one search, which points at ranking and query shape rather than at the corpus. |
| 2026-09-25 | 8b4a61b | baseline | single-call | openalex-raw | 100 | 4 | 4.6% | - | 0 | $0.0004 api | 2026-09-25-8b4a61b/openalex-raw-cap100 |  |
| 2026-09-25 | 8b4a61b | baseline | single-call | openalex-raw | 200 | 4 | 4.6% | - | 0 | $0.0004 api | 2026-09-25-8b4a61b/openalex-raw-cap200 |  |
| 2026-09-25 | 8b4a61b | baseline | single-call | openalex-raw | 1000 | 4 | 6.5% | - | 0 | $0.0020 api | 2026-09-25-8b4a61b/openalex-raw-cap1000 | Ceiling row. OpenAlex reports its own cost in every response, a hundredth of a cent per page, so the figure is shown at four decimals. |
| 2026-09-25 | af1c86e | baseline | single-call | semantic-scholar-snippet | 50 | 4 | 4.3% | - | 0 | $0.00 api | 2026-09-25-af1c86e/semantic-scholar-snippet-cap50 | Semantic Scholar's **semantic** engine (`snippet/search`), added as arm 1b by owner amendment after arm 1 turned out to be a keyword engine. Same intent, cutoff, key and formula as the other baseline rows; the shared notes on the first 2026-09-25 row apply. Results are snippets, not papers: a cap of N is the first N unique papers in snippet rank order, and 1,000 snippets gave 417-638 unique papers per review, so the ceiling row holds about 550 candidates. Body-text snippets (69-92% of them) exist only for open-access papers, so the arm leans towards them. DOIs come from a second lookup call; 7 of the 2,204 unique papers had none and cannot match. `n_api_records` counts snippets; the lookup replies are id resolutions, not results. Free; two or three requests per review (the search plus one lookup per 500 papers), counted at every cap. No request failed. |
| 2026-09-25 | af1c86e | baseline | single-call | semantic-scholar-snippet | 100 | 4 | 10.0% | - | 0 | $0.00 api | 2026-09-25-af1c86e/semantic-scholar-snippet-cap100 | Pipeline standard depth: 10.7% at cap 100, with a language model, screening and a second round. |
| 2026-09-25 | af1c86e | baseline | single-call | semantic-scholar-snippet | 200 | 4 | 12.9% | - | 0 | $0.00 api | 2026-09-25-af1c86e/semantic-scholar-snippet-cap200 | Pipeline deep depth: 15.3% at cap 200. |
| 2026-09-25 | af1c86e | baseline | single-call | semantic-scholar-snippet | 1000 | 4 | 18.1% | - | 0 | $0.00 api | 2026-09-25-af1c86e/semantic-scholar-snippet-cap1000 | Ceiling row and the best baseline: above the pipeline's deep depth (15.3%) with one request and no language model, on about 550 candidates per review. Per review: loneliness 32% (27/84), adverse childhood experiences 15% (8/55), social care 14% (1/7, the only hit on that review by any arm or depth), parental leave 12% (6/52). Strong evidence that retrieval method, not corpus, is the pipeline's weak part. |
| 2026-10-05 | d848515 | baseline | single-call | openalex-raw | 50 | 15 | 1.6% | - | 0 | $0.0015 api | mini-2026-10-05/openalex-raw-cap50 |  |
| 2026-10-05 | d848515 | baseline | single-call | openalex-raw | 100 | 15 | 2.5% | - | 0 | $0.0015 api | mini-2026-10-05/openalex-raw-cap100 |  |
| 2026-10-05 | d848515 | baseline | single-call | openalex-raw | 200 | 15 | 3.2% | - | 0 | $0.0015 api | mini-2026-10-05/openalex-raw-cap200 |  |
| 2026-10-05 | d848515 | baseline | single-call | openalex-raw | 1000 | 15 | 5.2% | - | 0 | $0.0072 api | mini-2026-10-05/openalex-raw-cap1000 | Split: gap-map rows 1.4%, lists 6.7%, originals 6.5% (identical to 2026-09-25). |
| 2026-10-05 | d848515 | baseline | single-call | semantic-scholar | 50 | 15 | 0.4% | - | 1 | $0.00 api | mini-2026-10-05/semantic-scholar-cap50 | **Mini dataset** (`retrieval-ground-truth-mini`, 15 reviews: 11 sampled from the fetched collections plus the 4 hand-made reviews; README section 7). Notes shared by every `mini-2026-10-05` row: title-shaped intents; the 7 Campbell/SR4ALL rows are unlabelled reference lists with a recall ceiling near 50%, the 4 gap-map rows and the 4 originals are labelled; compare within a kind, not across. Per-review scores are in Langfuse. Same arms, caps, cutoff, key and formula as the 2026-09-25 rows. |
| 2026-10-05 | d848515 | baseline | single-call | semantic-scholar | 100 | 15 | 0.5% | - | 1 | $0.00 api | mini-2026-10-05/semantic-scholar-cap100 |  |
| 2026-10-05 | d848515 | baseline | single-call | semantic-scholar | 200 | 15 | 1.0% | - | 1 | $0.00 api | mini-2026-10-05/semantic-scholar-cap200 |  |
| 2026-10-05 | d848515 | baseline | single-call | semantic-scholar | 1000 | 15 | 1.9% | - | 1 | $0.00 api | mini-2026-10-05/semantic-scholar-cap1000 | One request failed after retries (energy-efficiency review, 786 of 1,000 positions): small undercount on that row. |
| 2026-10-05 | d848515 | baseline | single-call | semantic-scholar-snippet | 50 | 15 | 3.0% | - | 1 | $0.00 api | mini-2026-10-05/semantic-scholar-snippet-cap50 |  |
| 2026-10-05 | d848515 | baseline | single-call | semantic-scholar-snippet | 100 | 15 | 6.0% | - | 1 | $0.00 api | mini-2026-10-05/semantic-scholar-snippet-cap100 |  |
| 2026-10-05 | d848515 | baseline | single-call | semantic-scholar-snippet | 200 | 15 | 8.0% | - | 1 | $0.00 api | mini-2026-10-05/semantic-scholar-snippet-cap200 |  |
| 2026-10-05 | d848515 | baseline | single-call | semantic-scholar-snippet | 1000 | 15 | 11.7% | - | 1 | $0.00 api | mini-2026-10-05/semantic-scholar-snippet-cap1000 | Best baseline again. Split: gap-map rows 4.5%, reference lists 12.0%, the 4 originals 18.6% (18.1% on 2026-09-25 from a fresh fetch). |
| 2026-10-05 | d848515 | baseline | single-call | consensus | 50 | 15 | 5.0% | - | 0 | $2.25 api | mini-2026-10-05/consensus-cap50 |  |
| 2026-10-05 | d848515 | baseline | single-call | consensus | 100 | 15 | 6.7% | - | 0 | $2.25 api | mini-2026-10-05/consensus-cap100 |  |
| 2026-10-05 | d848515 | baseline | single-call | consensus | 200 | 15 | 8.1% | - | 0 | $2.25 api | mini-2026-10-05/consensus-cap200 |  |
| 2026-10-05 | d848515 | baseline | single-call | consensus | 1000 | 15 | 10.7% | - | 0 | $7.50 api | mini-2026-10-05/consensus-cap1000 | Split: gap-map rows 3.1%, lists 13.4%, originals 13.6% (identical to 2026-09-25). |
| 2026-10-05 | d848515 | production-recall | rapid | shared | 50 | 15 | 2.5% | - | 1 | $0.01 llm | mini-2026-10-05/rapid | On the 4 originals rapid scored 4.4% against 5.6% on 2026-09-22 with identical inputs: run-to-run variance of the generated queries, of the order of the gaps between arms. One provider call failed (whole-school map row). |
| 2026-10-05 | d848515 | production-recall | standard | shared | 100 | 15 | 5.0% | 5.0% | 0 | $15.85 llm | mini-2026-10-05/standard | Screen recall equals search recall again: screening removed nothing the search found. $15.85 for the pass ($1.06 per review), 99% of it abstract screening. On the 4 originals 8.1% against 10.7% on 2026-09-22 (variance, see the rapid row). |
| 2026-10-05 | 8e7ea2a | baseline | single-call | semantic-scholar | 50 | 15 | 0.4% | - | 0 | $0.00 api | mini-q-2026-10-05/semantic-scholar-cap50 | **Question-shaped intents for the 4 gap-map rows** (contract D18; the other 11 rows unchanged and read from the cache). Notes shared by every `mini-q-2026-10-05` row: identical to `mini-2026-10-05` except the 4 gap-map intents, now "What is the evidence on <intervention> in relation to <map theme>?". New service rule: OpenAlex reads `?` as a wildcard (HTTP 400), so that arm drops the trailing question mark; the first OpenAlex attempt failed on all 4 rows and was re-run over all 15 under this label, which replaced the failed scores. |
| 2026-10-05 | 8e7ea2a | baseline | single-call | semantic-scholar | 100 | 15 | 0.5% | - | 0 | $0.00 api | mini-q-2026-10-05/semantic-scholar-cap100 |  |
| 2026-10-05 | 8e7ea2a | baseline | single-call | semantic-scholar | 200 | 15 | 1.0% | - | 0 | $0.00 api | mini-q-2026-10-05/semantic-scholar-cap200 |  |
| 2026-10-05 | 8e7ea2a | baseline | single-call | semantic-scholar | 1000 | 15 | 1.9% | - | 0 | $0.00 api | mini-q-2026-10-05/semantic-scholar-cap1000 | Keyword engine: 0 results for every question-shaped intent, as for the titles. |
| 2026-10-05 | 8e7ea2a | baseline | single-call | semantic-scholar-snippet | 50 | 15 | 3.0% | - | 0 | $0.00 api | mini-q-2026-10-05/semantic-scholar-snippet-cap50 |  |
| 2026-10-05 | 8e7ea2a | baseline | single-call | semantic-scholar-snippet | 100 | 15 | 5.7% | - | 0 | $0.00 api | mini-q-2026-10-05/semantic-scholar-snippet-cap100 |  |
| 2026-10-05 | 8e7ea2a | baseline | single-call | semantic-scholar-snippet | 200 | 15 | 7.9% | - | 0 | $0.00 api | mini-q-2026-10-05/semantic-scholar-snippet-cap200 |  |
| 2026-10-05 | 8e7ea2a | baseline | single-call | semantic-scholar-snippet | 1000 | 15 | 11.7% | - | 0 | $0.00 api | mini-q-2026-10-05/semantic-scholar-snippet-cap1000 | On the 4 gap-map rows: 4.5% before, 4.5% after, the same studies found on every row. The question shape did not move the semantic engine. |
| 2026-10-05 | 8e7ea2a | baseline | single-call | consensus | 50 | 15 | 5.2% | - | 0 | $2.25 api | mini-q-2026-10-05/consensus-cap50 |  |
| 2026-10-05 | 8e7ea2a | baseline | single-call | consensus | 100 | 15 | 7.3% | - | 0 | $2.25 api | mini-q-2026-10-05/consensus-cap100 |  |
| 2026-10-05 | 8e7ea2a | baseline | single-call | consensus | 200 | 15 | 8.9% | - | 0 | $2.25 api | mini-q-2026-10-05/consensus-cap200 |  |
| 2026-10-05 | 8e7ea2a | baseline | single-call | consensus | 1000 | 15 | 11.7% | - | 0 | $7.50 api | mini-q-2026-10-05/consensus-cap1000 | On the 4 gap-map rows: 3.1% before, 6.7% after (7 to 16 studies found). The only arm the question shape helped. |
| 2026-10-05 | 8e7ea2a | baseline | single-call | openalex-raw | 50 | 15 | 1.6% | - | 0 | $0.0015 api | mini-q-2026-10-05/openalex-raw-cap50 |  |
| 2026-10-05 | 8e7ea2a | baseline | single-call | openalex-raw | 100 | 15 | 2.5% | - | 0 | $0.0015 api | mini-q-2026-10-05/openalex-raw-cap100 |  |
| 2026-10-05 | 8e7ea2a | baseline | single-call | openalex-raw | 200 | 15 | 3.1% | - | 0 | $0.0015 api | mini-q-2026-10-05/openalex-raw-cap200 |  |
| 2026-10-05 | 8e7ea2a | baseline | single-call | openalex-raw | 1000 | 15 | 5.1% | - | 0 | $0.0074 api | mini-q-2026-10-05/openalex-raw-cap1000 | On the 4 gap-map rows: 1.4% before, 0.9% after (question mark stripped). |
| 2026-10-05 | 8e7ea2a | production-recall | rapid | shared | 50 | 15 | 2.2% | - | 0 | $0.01 llm | mini-q-2026-10-05/rapid | All 15 re-run (two cents). 2.2% against 2.5% on the same day with title intents; on the 4 gap-map rows 0.0% against 1.0%. The pipeline rewrites the intent into its own queries, so the intent shape matters less to it; the difference is within its run-to-run variance. |
| 2026-10-05 | 8e7ea2a | production-recall | standard | shared | 100 | 4 | 0.0% | 0.0% | 0 | $4.09 llm | mini-q-2026-10-05/standard | **4 reviews only** (the gap-map rows, $4.09): 0.0% against 0.5% on those rows with title intents. Spliced with the 11 unchanged rows of `mini-2026-10-05/standard`, the fifteen-row figure is **4.8%** (5.0% before). Not a full run; see the previous standard row for the pass over all 15. |
