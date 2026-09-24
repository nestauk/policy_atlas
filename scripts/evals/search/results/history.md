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

## Runs

| date | commit | experiment | depth | backend | record cap | reviews | search recall | screen recall | failed calls | run | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-10 | 422bf39 | cap-prompt-sweep | rapid | shared | 250 | 4 | 9.3% | - | 0 | 2026-09-10-422bf39/shared-cap250-r1 | First full sweep, one repeat. Caps 50 and 100 were not run. |
| 2026-09-10 | 422bf39 | cap-prompt-sweep | rapid | shared | 500 | 4 | 17.6% | - | 0 | 2026-09-10-422bf39/shared-cap500-r1 |  |
| 2026-09-10 | 422bf39 | cap-prompt-sweep | rapid | shared | 1000 | 4 | 16.9% | - | 0 | 2026-09-10-422bf39/shared-cap1000-r1 |  |
| 2026-09-10 | 422bf39 | cap-prompt-sweep | rapid | shared | 2000 | 4 | 19.9% | - | 0 | 2026-09-10-422bf39/shared-cap2000-r1 |  |
| 2026-09-10 | 422bf39 | cap-prompt-sweep | rapid | per-provider | 250 | 3 | 15.7% | - | 0 | 2026-09-10-422bf39/per-provider-cap250-r1 | Only 3 reviews: the loneliness review failed. Average not comparable. |
| 2026-09-10 | 422bf39 | cap-prompt-sweep | rapid | per-provider | 500 | 4 | 14.3% | - | 0 | 2026-09-10-422bf39/per-provider-cap500-r1 |  |
| 2026-09-10 | 422bf39 | cap-prompt-sweep | rapid | per-provider | 1000 | 4 | 17.0% | - | 9 | 2026-09-10-422bf39/per-provider-cap1000-r1 | 9 provider calls failed after retries, so recall is an undercount. |
| 2026-09-11 | 422bf39 | cap-prompt-sweep | rapid | per-provider | 2000 | 4 | 37.2% | - | 0 | 2026-09-10-422bf39/per-provider-cap2000-r1 | Best recall so far. Per-provider prompt at cap 2000 nearly doubles the shared prompt. |
| 2026-09-22 | b16f859 | production-recall | rapid | shared | 50 | 4 | 5.6% | - | 0 | 2026-09-22-b16f859/rapid | First measurement at the real depth constants, all 4 reviews. |
| 2026-09-22 | b16f859 | production-recall | standard | shared | 100 | 4 | 10.7% | 10.7% | 0 | 2026-09-22-b16f859/standard | Screen recall equals search recall: screening lost nothing search found. |
| 2026-09-22 | b16f859 | production-recall | deep | shared | 200 | 4 | 15.3% | 15.3% | 0 | 2026-09-22-b16f859/deep | Same as standard: screening lost nothing. |
