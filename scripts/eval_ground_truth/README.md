# Ground-truth eval pilot

Measures the search pipeline's recall (and optionally screening's) against
real systematic reviews' reference lists, hand-curated in `input/` and run as a
Langfuse experiment.

## Methodology

- A list of a handful of systematic reviews to use as the ground truth has been collected in `input/gt_reviews.csv`. Each must have either a DOI or a URL (as policy papers will not have a DOI) - this is the key that is used to match the target to the references returned by the Policy Atlas search. Each also has a cutoff date, either specified in gt_reviews.csv or the publication date - 1 month.

- A separate repo, [policy_atlas_gt_labelling](https://github.com/nestauk/policy_atlas_gt_labelling), handles getting the reference lists for these systematic reviews and curating them so that our recall target is only on-topic/"content" citations (rather than e.g. methodology citations about how to conduct a systematic review).

- For each of the systematic reviews listed in gt_reviews.csv, we infer a Policy Atlas query. We deterministically extract "intent" from the title of the systematic review. Because the reviews chosen are ones with "systematic review" or similar in the title, we use deterministic rules to strip the ": a systematic review" part from the end of the title. On the assumption that the title accurately defines the scope of the research, what remains is treated as the "intent". This is important because it means **we're bypassing the Planner/Agent**, so it's not totally faithful to how a real search in Policy Atlas happens. In the app, the Planner turns the user's raw text into an "intent".

- In the Policy Atlas searches, we are at present just trying to calculate a recall metric on search i.e. the very first component of the pipeline. To this end, we just use the rapid search methodology i.e. generating 18 API queries across OpenAlex and Overton, but just one round of queries, and no reformulation, citation snowballing etc. The reason for this is that running multiple rounds would involve relevance screening, and that needs to be evaluated separately. (There is actually already code ready to turn screening on and this is in `sweep_record_cap.py`)

- We run a Langfuse Experiment to compare: prompt version (v2 vs v3) x cap on the number of records kept from each API (50, 100, 250, 500, 1000, 2000). We expect that raising the cap -> better recall. There is a cost to raising this cap in the real PA workflow though because records passed to the relevance screening step also get stored and are available for RAG retrieval during the synthesis step. Therefore there is a tradeoff of search recall against documents kept.

Some other points worth knowing:

- The date cut off is `<date review published> - 1 month`. The OpenAlex date cut off is inclusive so if the date of publication is used directly, you can end up accidentally including the source review itself. We put the cut off 1 month behind that to be on the safe side, as anything published less than a month before the review's publication is highly unlikely to make it into te systematic review.

### Comparison of v2 and v3 API query generation

The two generation backends are:

| version | value | class | prompt files |
|---|---|---|---|
| v3 | `shared` | `OpenAISearchGenerationBackend` | `search_queries_system_v3.txt` — one prompt writes both the OpenAlex keyword queries and the Overton paraphrases |
| v2 | `per-provider` | `V2SearchGenerationBackend` | `search_queries_openalex_system_v2.txt` and `search_queries_overton_system_v2.txt` — one prompt per provider, called once per query |

## How to run

**See [policy_atlas_gt_labelling](https://github.com/nestauk/policy_atlas_gt_labelling) - this is where the ground truth data was generated**

### Prerequisites

Two files in `scripts/eval_ground_truth/input/`:
- `gt_reviews.csv`
- `references.csv`

### Usage

#### 1. Upload the ground truth (once, and again whenever a CSV changes)

The recall target is two hand-curated CSVs under `input/`, mirrored into a
Langfuse dataset (a saved set of test cases, one per review) by
`ground_truth_dataset.py`:

| file | one row per | columns used |
|---|---|---|
| `gt_reviews.csv` | review to search for | `title` (cleaned into the search intent), `doi` or `url` (the review's identifier), `published_before` (ISO `YYYY-MM-DD` search cutoff; when empty on a DOI row it is derived from OpenAlex as one month before publication and printed for you to paste in; a URL row must give it), `exclude` (any value skips the row) |
| `references.csv` | work a review cites | `review_title` (must equal `title` above exactly), `ref_title`, `label` (only `content` rows count toward recall), and the scoring key: `doi` (bare or `https://doi.org/...`) or `overton_id` (for a policy document with no DOI) |

```
uv run --project backend --env-file backend/.env \
    python scripts/eval_ground_truth/ground_truth_dataset.py --dry-run   # check the join; uploads nothing
uv run --project backend --env-file backend/.env \
    python scripts/eval_ground_truth/ground_truth_dataset.py             # upsert into Langfuse
```

#### 2. Run the sweep

Test the experiment with a cap of 50, only the v3 ("shared") query generation, and 1x repeat:
```
uv run --project backend --env-file backend/.env \
    python scripts/eval_ground_truth/sweep_record_cap.py \
    --caps 50 --generation-backends shared --repeats 1
```

Then run the full experiment (every cap [50, 100, 250, 500, 1000, 2000], v2 and v3 query generation; still 1x repeat)
```
uv run --project backend --env-file backend/.env \
    python scripts/eval_ground_truth/sweep_record_cap.py
```

NB `--repeats` runs each combination more than once, which averages out the fact that query generation is an LLM call and gives slightly different queries every time. So far, this has not been used because it increases the time and cost of the experiment.

