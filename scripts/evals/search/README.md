# Evaluating against ground truth

This folder contains scripts related to calculating evaluation metrics against a ground truth dataset. There are three components to the work here:
* uploading golden datasets to Langfuse
* Testing the recall of the current production rapid/standard/deep search methodology
* An experimental sweep across different record caps to see how these affect recall (basically seeing how lifting the cap on the number of records kept after deduplication affects recall)

## How the files fit together

The folder has nine Python files. You run five of them from the command line. The other four are helper modules that the scripts import.

**Scripts you run:**

| Script | What it does | When to run it |
|---|---|---|
| `ground_truth_dataset.py` | Reads the two CSV files in `input/` and uploads them to Langfuse as a dataset called `retrieval-ground-truth`. | Once at the start, and again each time `references.csv` or `gt_reviews.csv` changes. |
| `production_recall.py` | Measures how much of each review's reference list the pipeline finds when it runs exactly as it does in production. It makes one Langfuse run for each search depth (rapid, standard, deep). | By hand, from time to time, so that a history of production recall builds up. |
| `history.py` | Prints one markdown table row per dataset run in Langfuse: date, commit, settings, run name, mean recall and the run's variable cost. It writes nothing. | After each eval you can copy the rows worth keeping into `results/history.md` and add a note. |
| `baseline_recall.py` | The baselines. Sends each review's intent once, as plain text, to Semantic Scholar, Consensus and OpenAlex, caches the raw result pages locally, and scores recall at several result caps. One Langfuse run per service and cap. | When you want a "what does good look like" number to compare the pipeline's recall with. The services are called once; later runs read the cache. See section 5. |
| `sweep_record_cap.py` | The experiment. It runs a rapid search many times, each time with a different cap on the number of records kept and with one of the two query-generation methods. It records the recall for each combination. | When you want to know how the record cap or the prompting method changes recall. |

The two measuring scripts read the reviews and their reference lists from the Langfuse dataset. They do not read the CSV files. This means you must run `ground_truth_dataset.py` at least once before you run either of them.

**Helper modules (these have no command line):**

| Module | What it holds | Who uses it |
|---|---|---|
| `ground_truth.py` | Small building blocks that need no database and no pipeline code: the key used to match a found document to a reference (a lowercase DOI, or `overton:<id>` for documents without a DOI), the `GroundTruth` container, the function that turns a review title into a search intent, the date helpers, and one lookup to the OpenAlex API. | All the other files. |
| `search_eval.py` | The core of the evaluation. Its function `run_one_query` takes one search intent, runs the real search stage (and screening, if asked) and works out the recall. It runs inside a database transaction that is always rolled back, so nothing is saved to the database. It returns a `QueryResult` that holds the recall and the raw records each API call returned. | `sweep_record_cap.py` and `production_recall.py`. |
| `inspect_run.py` | Two functions that turn a `QueryResult` into tables: one row per API call, or one row per record returned. The tables show titles and DOIs, so in a notebook you can see which API call found which paper without paying for the calls again. | `sweep_record_cap.py` uses it to build its queries CSV and papers CSV. |
| `test_metrics.py` | A self-check for the functions that need no network and no database: scoring, CSV loading, the output tables and the OpenAlex retry logic. | Run it after you change any of the files above: `uv run --project backend python scripts/evals/search/test_metrics.py`. |

`production_recall.py` also imports the score names and the Langfuse upload code from `sweep_record_cap.py`. This means both scripts report the same set of scores, and you can compare their runs in Langfuse.

**How data flows through the files:**

```
input/gt_reviews.csv ─┐
input/references.csv ─┴─> ground_truth_dataset.py ──> Langfuse dataset
                                                          │
                              ┌───────────────────────────┴──────────────┐
                              v                                          v
                     production_recall.py                        sweep_record_cap.py
                              │                                          │
                              └────────> search_eval.run_one_query <─────┘
                                          (real search + screening,
                                           rolled back, never saved)
                                                     │
                                                     v
                                     Langfuse runs + scores
                                     results/*.csv (sweep only, built with inspect_run.py)
```

Abbreviations used above: CSV is a comma-separated values file. DOI is a Digital Object Identifier, the permanent ID of a published paper. API is an application programming interface, the way our code asks OpenAlex and Overton for records.

## Prerequisites

Two files in `scripts/evals/search/input/`:
- `gt_reviews.csv`
- `references.csv`

## 1. Uploading datasets to Langfuse

Key scripts/files: `ground_truth_dataset.py`

### What this does

This uploads curated systematic reviews to Langfuse as a dataset (the dataset `retrieval-ground-truth`). Each systematic review becomes an input ("intent", derived from the review's title -- see more below) and an output (the list of references in that review).

### Usage

This should be run whenever new reviews have been curated, i.e. if the local `references.csv` has been updated.

Dry-run first, since it uploads nothing and needs no Langfuse keys:

```
uv run --project backend --env-file backend/.env python scripts/evals/search/ground_truth_dataset.py --dry-run
```

Run it for real:
```
uv run --project backend --env-file backend/.env python scripts/evals/search/ground_truth_dataset.py
```

### Methodology details

- A list of a handful of systematic reviews to use as the ground truth has been collected in `input/gt_reviews.csv`. Each must have either a DOI or a URL (as policy papers will not have a DOI) - this is the key that is used to match the target to the references returned by the Policy Atlas search. Each also has a cutoff date, either specified in gt_reviews.csv or the publication date - 1 month.

- These systematic reviews have been collected because they represent a range of policy areas: universal basic income, parental leave, loneliness and so on.

- A separate repo, [policy_atlas_gt_labelling](https://github.com/nestauk/policy_atlas_gt_labelling), handles getting the reference lists for these systematic reviews and curating them so that our recall target is only on-topic/"content" citations (rather than e.g. methodology citations about how to conduct a systematic review).

- For each of the systematic reviews listed in `gt_reviews.csv`, we infer a Policy Atlas query. We deterministically extract "intent" from the title of the systematic review. Because the reviews chosen are ones with "systematic review" or similar in the title, we use deterministic rules to strip the ": a systematic review" part from the end of the title. On the assumption that the title accurately defines the scope of the research, what remains is treated as the "intent". This is important because it means **we're bypassing the Planner/Agent**, so it's not totally faithful to how a real search in Policy Atlas happens. In the app, the Planner turns the user's raw text into an "intent".

Some other points worth knowing:

- The date cut off as recorded in `gt_reviews.csv` is `<date review published> - 1 month`. The OpenAlex date cut off is inclusive so if the date of publication is used directly, you can end up accidentally including the source review itself. We put the cut off 1 month behind that to be on the safe side, as anything published less than a month before the review's publication is highly unlikely to make it into te systematic review.

## 2. Establishing the recall of current production rapid/standard/deep search types

Key scripts/files: `production_recall.py`

### What this does

This calculates recall at the search/retrieval and, if applicable, screening stages for a rapid/standard/deep search.

Ultimately this should be built into a regression test.

A GitHub Actions workflow for this exists but is parked in `.github/workflows-disabled/`, so it is not live. Move it back to `.github/workflows/` to enable it once the cost and gating questions are settled.

### Usage

```
make eval-search-recall                                            # all depths, all reviews
make eval-search-recall ARGS="--depths rapid"                      # run it just for a rapid search (all reviews)
```

## 3. Experiment to see how lifting the cap on records kept from the two APIs affects recall

Key scripts/files: `sweep_record_cap.py`

### What this does

The search stage fetches far more records than it keeps. This experiment tests how just using the rapid search paradigm (i.e. one search round, and no reformulation, citation snowballing etc) and varying the cap on records kept affects recall.

It also compares v2-style and v3 prompting methods. v2 comes with higher latency (aysncio or similar was used in the v2 repo to manage this?) but better recall.

### Usage

```
uv run --project backend --env-file backend/.env python scripts/evals/search/sweep_record_cap.py --caps 50 --generation-backends shared --repeats 1   # smoke test
uv run --project backend --env-file backend/.env python scripts/evals/search/sweep_record_cap.py                                                     # full sweep

```

### Methodology details

- In the Policy Atlas searches, we are at present just trying to calculate a recall metric on search i.e. the very first component of the pipeline. To this end, we just use the rapid search methodology i.e. generating 18 API queries across OpenAlex and Overton, but just one round of queries, and no reformulation, citation snowballing etc. The reason for this is that running multiple rounds would involve relevance screening, and that needs to be evaluated separately. (There is actually already code ready to turn screening on and this is in `sweep_record_cap.py`)

- We run a Langfuse Experiment to compare: prompt version (v2 vs v3) x cap on the number of records kept from each API (50, 100, 250, 500, 1000, 2000). We expect that raising the cap -> better recall. There is a cost to raising this cap in the real PA workflow though because records passed to the relevance screening step also get stored and are available for RAG retrieval during the synthesis step. Therefore there is a tradeoff of search recall against documents kept.


#### Comparison of v2 and v3 API query generation

The two generation backends are:

| version | value | class | prompt files |
|---|---|---|---|
| v3 | `shared` | `OpenAISearchGenerationBackend` | `search_queries_system_v3.txt` — one prompt writes both the OpenAlex keyword queries and the Overton paraphrases |
| v2 | `per-provider` | `V2SearchGenerationBackend` | `search_queries_openalex_system_v2.txt` and `search_queries_overton_system_v2.txt` — one prompt per provider, called once per query |

## 4. Keeping a history of the headline results

Key scripts/files: `history.py`, `results/history.md`

### What this does

Langfuse holds every run and all the detail. `results/history.md` holds only the headline numbers of the runs that matter (mean recall per run, with a note on each), so the history of recall lives in git next to the code. `history.py` prints one markdown table row per run in Langfuse so you can pick the rows to keep.

### Usage

Print a row for every run, oldest first:

```
uv run --project backend --env-file backend/.env python scripts/evals/search/history.py
```

Print only recent runs:

```
uv run --project backend --env-file backend/.env python scripts/evals/search/history.py --since 2026-09-24
```

Then copy the row(s) worth keeping into the table in `results/history.md` and fill in the notes cell. Leave out smoke tests and partial runs unless they tell you something.

### The variable cost column

Each row also shows the run's **variable cost**: the money that changes with how much you
search, summed over the reviews in the run. The label after the number says what it counts.

- `api` — baseline runs. The **computed** price of fetching that many results from the
  service, from the service's own price table (Consensus $0.05 per call, one call per 100
  papers; OpenAlex reports its own `cost_usd`; Semantic Scholar is free). It is what that cap
  would cost on its own. It is not what the run spent: with the cache, the services are
  called once and every cap is scored from the same pages.
- `llm` — pipeline runs. The language-model spend that Langfuse attributes to that review's
  trace (`total_cost`), summed over the reviews.

Neither figure includes flat subscriptions (Overton, OpenAlex premium, the Consensus plan
fee), compute, or Langfuse itself. `n/a` means neither source had a number.

## 5. Search recall baselines: what does good look like?

Key scripts/files: `baseline_recall.py`, `results/cache/`

### What this does

The pipeline's recall numbers (section 2) have nothing to be compared with. Is 5.6% at rapid
depth bad, normal, or as good as this ground truth allows? The baselines answer that with
the simplest possible search: each review's intent text is sent **once, unchanged**, to one
search service. No language model writes queries, nothing is screened, there is no second
round. Three services are tried, each called an **arm** (as in an experiment):

| Arm | Service | What it is |
|---|---|---|
| `semantic-scholar` | Semantic Scholar Academic Graph | Free scholarly search with its own relevance ranking. Needs a free key. |
| `consensus` | Consensus | Paid scholarly search built on Semantic Scholar's corpus with its own ranking. Calls are metered. |
| `openalex-raw` | OpenAlex | The service the pipeline already uses, but with one plain search instead of many generated queries. Free. |

The results are scored exactly like the pipeline runs: same ground truth, same cutoff date
(nothing published after the review's cutoff counts), same scoring key (a lowercase DOI) and
same recall formula. Because every key in the ground truth is a DOI today, all these numbers,
the baselines' and the pipeline's, are **scholarly recall**: a government report the review
cites cannot be found by anyone.

Two things differ between arms on purpose and are written into the notes in `history.md`:
Semantic Scholar matches nothing on hyphenated words, so hyphens are sent as spaces for that
arm only; and Consensus filters dates by month, so it may include papers from up to 30 days
after the cutoff day.

### How it runs: fetch once, score from the cache

1. **Fetch.** For each arm and review the script sends one search and reads every result
   page up to the service's 1,000-result ceiling. The raw pages are saved to the **cache**:
   one JSON file per arm and review under `results/cache/<arm>/`. The file holds the pages
   as the service returned them, the request parameters (never the key) and the fetch time.
   Git ignores it.
2. **Score.** For each **cap** (50, 100, 200 and 1,000 by default) the script keeps the
   first N results in the service's own order, removes duplicates, and counts how many of
   the review's references are among them. Each arm and cap becomes one Langfuse dataset
   run with the same score names as the pipeline runs plus `api_cost_usd`.

A second run with no flags reads the cache and makes **no service calls**. Pass `--refresh`
only when you want fresh results from the services (Consensus calls cost money). A fetch that
failed part-way is saved with `complete: false` and is fetched again on the next run.

### Usage

Keys go in `backend/.env`: `SEMANTIC_SCHOLAR_API_KEY` and `CONSENSUS_API_KEY`. OpenAlex
needs none. The dataset must already be in Langfuse (section 1).

```
# Try one arm on one review, score and print, upload nothing (still fills the cache):
uv run --project backend --env-file backend/.env python scripts/evals/search/baseline_recall.py --arms consensus --reviews parental --dry-run

# All arms, all reviews, all caps; one Langfuse run per arm and cap:
uv run --project backend --env-file backend/.env python scripts/evals/search/baseline_recall.py

# Later, re-score after a code change without calling the services:
uv run --project backend --env-file backend/.env python scripts/evals/search/baseline_recall.py
```

Before any request the script prints how many reviews need a fetch per arm and the ceiling
of requests. Consensus needs at most 10 calls per review (1,000 papers at 100 per call), and
our API beta account pays $0.05 on every call with no free amount: a full fetch of four
reviews is about $2.00. Use `--refresh` sparingly.

### How to read the rows next to the pipeline rows

Compare a baseline row with a pipeline row that has a **similar number of candidates kept**
(`n_candidates_kept` in Langfuse), not a similar number of requests. The pipeline's rapid
depth keeps up to 50 candidates per backend, so its cap-50 row is the neighbour of the
baselines' cap-50 and cap-100 rows. If one plain OpenAlex search matches or beats the
pipeline's rapid recall at a similar number of candidates, the weak part is probably our
query generation, not OpenAlex's corpus. That is a sign, not proof: the pipeline sends many
generated queries and then trims, so the two are not a controlled pair.
