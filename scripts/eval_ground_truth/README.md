# Evaluating against ground truth

This folder contains scripts related to calculating evaluation metrics against a ground truth dataset. There are three components to the work here:
* uploading golden datasets to Langfuse
* Testing the recall of the current production rapid/standard/deep search methodology
* An experimental sweep across different record caps to see how these affect recall (basically seeing how lifting the cap on the number of records kept after deduplication affects recall)

## Prerequisites

Two files in `scripts/eval_ground_truth/input/`:
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
uv run --project backend --env-file backend/.env python scripts/eval_ground_truth/ground_truth_dataset.py --dry-run
```

Run it for real:
```
uv run --project backend --env-file backend/.env python scripts/eval_ground_truth/ground_truth_dataset.py
```

### Methodology details

- A list of a handful of systematic reviews to use as the ground truth has been collected in `input/gt_reviews.csv`. Each must have either a DOI or a URL (as policy papers will not have a DOI) - this is the key that is used to match the target to the references returned by the Policy Atlas search. Each also has a cutoff date, either specified in gt_reviews.csv or the publication date - 1 month.

- These systematic reviews have been collected because they represent a range of policy areas: universal basic income, parental leave, loneliness and so on.

- A separate repo, [policy_atlas_gt_labelling](https://github.com/nestauk/policy_atlas_gt_labelling), handles getting the reference lists for these systematic reviews and curating them so that our recall target is only on-topic/"content" citations (rather than e.g. methodology citations about how to conduct a systematic review).

- For each of the systematic reviews listed in `gt_reviews.csv`, we infer a Policy Atlas query. We deterministically extract "intent" from the title of the systematic review. Because the reviews chosen are ones with "systematic review" or similar in the title, we use deterministic rules to strip the ": a systematic review" part from the end of the title. On the assumption that the title accurately defines the scope of the research, what remains is treated as the "intent". This is important because it means **we're bypassing the Planner/Agent**, so it's not totally faithful to how a real search in Policy Atlas happens. In the app, the Planner turns the user's raw text into an "intent".

Some other points worth knowing:

- The date cut off as recorded in `gt_reviews.csv` is `<date review published> - 1 month`. The OpenAlex date cut off is inclusive so if the date of publication is used directly, you can end up accidentally including the source review itself. We put the cut off 1 month behind that to be on the safe side, as anything published less than a month before the review's publication is highly unlikely to make it into te systematic review.

## 2. Establishing the recall of current roduction rapid/standard/deep search types

Key scripts/files: `production_recall.py`

### What this does

This calculates recall at the search/retrieval and, if applicable, screening stages for a rapid/standard/deep search.

Ultimately this should be built into a regression test.

### Usage

```
make production-recall                                            # all depths, all reviews
make production-recall ARGS="--depths rapid"                      # run it just for a rapid search (all reviews)
```

## 3. Experiment to see how lifting the cap on records kept from the two APIs affects recall

Key scripts/files: `sweep_record_cap.py`

### What this does

The search stage fetches far more records than it keeps. This experiment tests how just using the rapid search paradigm (i.e. one search round, and no reformulation, citation snowballing etc) and varying the cap on records kept affects recall.

It also compares v2-style and v3 prompting methods. v2 comes with higher latency (aysncio or similar was used in the v2 repo to manage this?) but better recall.

### Usage

```
uv run --project backend --env-file backend/.env python scripts/eval_ground_truth/sweep_record_cap.py --caps 50 --generation-backends shared --repeats 1   # smoke test
uv run --project backend --env-file backend/.env python scripts/eval_ground_truth/sweep_record_cap.py                                                     # full sweep

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