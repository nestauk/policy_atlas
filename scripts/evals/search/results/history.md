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
  cap, from the service's price table (baseline runs); it is what that cap would cost
  on its own, not what the run spent, because the baselines call each service once and
  score every cap from the cached pages. Neither includes flat subscriptions (Overton,
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
| 2026-09-25 | 8b4a61b | baseline | single-call | semantic-scholar | 50 | 4 | 0.9% | - | 0 | $0.00 api | 2026-09-25-8b4a61b/semantic-scholar-cap50 | Notes shared by all baseline rows below. One fetch per arm and review to 1,000 results, cached 2026-09-25 (Semantic Scholar 14:56 UTC, OpenAlex 14:57 UTC, Consensus 15:00 UTC), scored at every cap from the cache. Compare with the 2026-09-22 pipeline rows at commit b16f859 (same ground truth). The target is scholarly only: every ground-truth key is a DOI, so grey literature cannot be found by any arm or by the pipeline. Same intent text, cutoff, scoring key, cap rule (first N in the service's order, then dedup) and recall formula for every arm. Two differences favour one side and are deliberate: Semantic Scholar receives hyphens as spaces (D1; no intent had a hyphen); Consensus filters by month, so it may include papers up to 30 days past the cutoff day (D2). The raw-versus-pipeline comparison is a sign, not a controlled test: the pipeline sends many generated queries and trims, the baselines send one. The cost is computed, not spent. No request failed. |
| 2026-09-25 | 8b4a61b | baseline | single-call | semantic-scholar | 100 | 4 | 1.2% | - | 0 | $0.00 api | 2026-09-25-8b4a61b/semantic-scholar-cap100 | Semantic Scholar's search needs every word of the intent to match. It reported totals of 0, 1, 22 and 29,628 results for the four reviews, so three reviews had almost nothing to rank and only the loneliness review reached the 1,000 ceiling. A plain title-length query is the wrong shape for this service; its number says more about the query than the corpus. |
| 2026-09-25 | 8b4a61b | baseline | single-call | semantic-scholar | 200 | 4 | 1.5% | - | 0 | $0.00 api | 2026-09-25-8b4a61b/semantic-scholar-cap200 |  |
| 2026-09-25 | 8b4a61b | baseline | single-call | semantic-scholar | 1000 | 4 | 1.5% | - | 0 | $0.00 api | 2026-09-25-8b4a61b/semantic-scholar-cap1000 | Ceiling row. Loneliness 6% (5/84), the other three 0%. |
| 2026-09-25 | 8b4a61b | baseline | single-call | consensus | 50 | 4 | 7.6% | - | 0 | $0.60 api | 2026-09-25-8b4a61b/consensus-cap50 | Best baseline at every cap and above the pipeline's rapid depth (5.6% at cap 50, similar candidates kept) with one plain search and no language model. The month-granularity cutoff helps it by a small unknown amount (D2). |
| 2026-09-25 | 8b4a61b | baseline | single-call | consensus | 100 | 4 | 8.6% | - | 0 | $0.60 api | 2026-09-25-8b4a61b/consensus-cap100 | Pipeline standard depth: 10.7% at cap 100, with screening and re-querying. |
| 2026-09-25 | 8b4a61b | baseline | single-call | consensus | 200 | 4 | 10.4% | - | 0 | $0.60 api | 2026-09-25-8b4a61b/consensus-cap200 | Pipeline deep depth: 15.3% at cap 200. |
| 2026-09-25 | 8b4a61b | baseline | single-call | consensus | 1000 | 4 | 13.6% | - | 0 | $2.00 api | 2026-09-25-8b4a61b/consensus-cap1000 | Ceiling row. Per review: adverse childhood experiences 20% (11/55), parental leave 15% (8/52), loneliness 19% (16/84), social care 0% (0/7). Page size echoed as 300 (a Pro or Teams plan); the last request fetches positions 900-999 at size 100 because the service rejects a page that would pass 1,000. Cost is 10 calls per review at $0.05, billed on every call on our account. |
| 2026-09-25 | 8b4a61b | baseline | single-call | openalex-raw | 50 | 4 | 3.5% | - | 0 | $0.0004 api | 2026-09-25-8b4a61b/openalex-raw-cap50 | One plain OpenAlex search of the intent, no language model. Below the pipeline's rapid depth (5.6%) at a similar number of candidates kept. So the pipeline's 18 generated queries do add recall over one raw search on the same corpus, but Consensus beats both with one search, which points at ranking and query shape rather than at the corpus. |
| 2026-09-25 | 8b4a61b | baseline | single-call | openalex-raw | 100 | 4 | 4.6% | - | 0 | $0.0004 api | 2026-09-25-8b4a61b/openalex-raw-cap100 |  |
| 2026-09-25 | 8b4a61b | baseline | single-call | openalex-raw | 200 | 4 | 4.6% | - | 0 | $0.0004 api | 2026-09-25-8b4a61b/openalex-raw-cap200 |  |
| 2026-09-25 | 8b4a61b | baseline | single-call | openalex-raw | 1000 | 4 | 6.5% | - | 0 | $0.0020 api | 2026-09-25-8b4a61b/openalex-raw-cap1000 | Ceiling row. OpenAlex reports its own cost in every response, a hundredth of a cent per page, so the figure is shown at four decimals. |
| 2026-09-25 | af1c86e | baseline | single-call | semantic-scholar-snippet | 50 | 4 | 4.3% | - | 0 | $0.00 api | 2026-09-25-af1c86e/semantic-scholar-snippet-cap50 | Semantic Scholar's **semantic** engine (`snippet/search`), added as arm 1b by owner amendment after arm 1 turned out to be a keyword engine. Same intent, cutoff, key and formula as the other baseline rows; the shared notes on the first 2026-09-25 row apply. Results are snippets, not papers: a cap of N is the first N unique papers in snippet rank order, and 1,000 snippets gave 417-635 unique papers per review, so the ceiling row holds about 550 candidates. Body-text snippets (69-92% of them) exist only for open-access papers, so the arm leans towards them. DOIs come from a second lookup call; every unique paper had one. Free; three requests per review. No request failed. |
| 2026-09-25 | af1c86e | baseline | single-call | semantic-scholar-snippet | 100 | 4 | 10.0% | - | 0 | $0.00 api | 2026-09-25-af1c86e/semantic-scholar-snippet-cap100 | Pipeline standard depth: 10.7% at cap 100, with a language model, screening and a second round. |
| 2026-09-25 | af1c86e | baseline | single-call | semantic-scholar-snippet | 200 | 4 | 12.9% | - | 0 | $0.00 api | 2026-09-25-af1c86e/semantic-scholar-snippet-cap200 | Pipeline deep depth: 15.3% at cap 200. |
| 2026-09-25 | af1c86e | baseline | single-call | semantic-scholar-snippet | 1000 | 4 | 18.1% | - | 0 | $0.00 api | 2026-09-25-af1c86e/semantic-scholar-snippet-cap1000 | Ceiling row and the best baseline: above the pipeline's deep depth (15.3%) with one request and no language model, on about 550 candidates per review. Per review: loneliness 32% (27/84), adverse childhood experiences 15% (8/55), social care 14% (1/7, the only hit on that review by any arm or depth), parental leave 12% (6/52). Strong evidence that retrieval method, not corpus, is the pipeline's weak part. |
