# Evaluating against ground truth

This folder contains scripts related to calculating evaluation metrics against a ground truth dataset. There are three components to the work here:
* uploading golden datasets to Langfuse
* Testing the recall of the current production rapid/standard/deep search methodology
* An experimental sweep across different record caps to see how these affect recall (basically seeing how lifting the cap on the number of records kept after deduplication affects recall)

## How the files fit together

The folder is split by purpose:

| Folder or file | Purpose |
|---|---|
| `evals_search_utils.py` | Shared building blocks that need no database and no pipeline code: the key used to match a found document to a reference (a lowercase DOI, Digital Object Identifier, or an Overton id), the `GroundTruth` container, the function that turns a review title into a search intent, the date helpers for a review's cutoff, the OpenAlex getter with retries, the dataset name, the `--reviews` item selector and the dollar formatter. Both halves import it. |
| `ground_truth/` | Building the dataset: the fetchers in `getters/` (`get_campbell.py`, `get_3ie.py`, `get_yef.py`, `get_sr4all.py`) with their shared `fetch_helpers.py`, `select_sample.py` (the quality check and the two samples) and `upload.py` (the CSV files to a Langfuse dataset). |
| `measure/` | Running measurements: `engine.py` (runs one intent through the real search stage; no command line), `production_recall.py`, `sweep_record_cap.py`, `baseline_recall.py`, and `inspect_run.py` (tables over one run's raw provider output; no command line). |
| `history.py` | Reading results: one markdown row per Langfuse dataset run. |
| `tests/` | Self-checks that need no network and no database: `test_ground_truth.py` and `test_measure.py`. `make eval-check` runs them with ruff, and `make verify` and `make verify-fast` include it. |
| `results/` | Outputs: the curated `history.md` (tracked) and the git-ignored caches, sweep files and ground-truth CSV files. |

Every script below the root starts with `import _bootstrap`, a short file that puts the folder's siblings on Python's import path, so each script runs directly with `uv run --project backend python scripts/evals/search/<folder>/<script>.py`.


**Scripts you run:**

| Script | What it does | When to run it |
|---|---|---|
| `ground_truth/upload.py` | Reads the two CSV files in `input/` and uploads them to Langfuse as a dataset called `retrieval-ground-truth`. | Once at the start, and again each time `references.csv` or `gt_reviews.csv` changes. |
| `measure/production_recall.py` | Measures how much of each review's reference list the pipeline finds when it runs exactly as it does in production. It makes one Langfuse run for each search depth (rapid, standard, deep). | By hand, from time to time, so that a history of production recall builds up. |
| `history.py` | Prints one markdown table row per dataset run in Langfuse: date, commit, settings, run name, mean recall and the run's variable cost. It writes nothing. | After each eval you can copy the rows worth keeping into `results/history.md` and add a note. |
| `measure/baseline_recall.py` | The baselines. Sends each review's intent once, as plain text, to Semantic Scholar (keyword and semantic search), Consensus and OpenAlex, caches the raw result pages locally, and scores recall at several result caps. One Langfuse run per service and cap. | When you want a "what does good look like" number to compare the pipeline's recall with. The services are called once; later runs read the cache. See section 5. |
| `ground_truth/getters/get_campbell.py`, `ground_truth/getters/get_3ie.py`, `ground_truth/getters/get_yef.py`, `ground_truth/getters/get_sr4all.py` | The ground-truth fetchers, in their own folder. Each downloads one public source of "review plus the studies it covers", keeps the raw download under `results/ground_truth/raw/`, and writes two CSVs in the same shape as `input/gt_reviews.csv` and `input/references.csv` into `results/ground_truth/`. | When you want to grow the ground truth beyond the four hand-made reviews. See section 6. |
| `ground_truth/select_sample.py` | Picks the ground-truth sample from the fetched collections: a simple quality check, a spread across topics, 30 Campbell + 30 3ie + 30 SR4ALL + 10 YEF rows (`sample_full`) and eleven hand-chosen rows out of those (`sample_mini`; with the four original reviews, the fifteen-item mini dataset). Writes the two CSV pairs next to the fetched files. No network. | After the fetchers have run, or after changing a rule in the quality check. See section 7. |
| `measure/sweep_record_cap.py` | The experiment. It runs a rapid search many times, each time with a different cap on the number of records kept and with one of the two query-generation methods. It records the recall for each combination. | When you want to know how the record cap or the prompting method changes recall. |

The two measuring scripts read the reviews and their reference lists from the Langfuse dataset. They do not read the CSV files. This means you must run `ground_truth/upload.py` at least once before you run either of them.

`measure/production_recall.py` also imports the score names and the Langfuse upload code from `measure/sweep_record_cap.py`. This means both scripts report the same set of scores, and you can compare their runs in Langfuse.

**How data flows through the files:**

```
input/gt_reviews.csv ─┐
input/references.csv ─┴─> ground_truth/upload.py ──> Langfuse dataset
                                                          │
                              ┌───────────────────────────┴──────────────┐
                              v                                          v
                     measure/production_recall.py                        measure/sweep_record_cap.py
                              │                                          │
                              └────────> engine.run_one_query <─────┘
                                          (real search + screening,
                                           rolled back, never saved)
                                                     │
                                                     v
                                     Langfuse runs + scores
                                     results/*.csv (sweep only, built with measure/inspect_run.py)
```

Abbreviations used above: CSV is a comma-separated values file. JSON is a plain-text data format (JavaScript Object Notation) that programs read and write. DOI is a Digital Object Identifier, the permanent ID of a published paper. API is an application programming interface, the way our code asks OpenAlex and Overton for records.

## Prerequisites

Two files in `scripts/evals/search/input/`:
- `gt_reviews.csv`
- `references.csv`

## 1. Uploading datasets to Langfuse

Key scripts/files: `ground_truth/upload.py`

### What this does

This uploads curated systematic reviews to Langfuse as a dataset (the dataset `retrieval-ground-truth`). Each systematic review becomes an input ("intent", derived from the review's title -- see more below) and an output (the list of references in that review).

### Usage

This should be run whenever new reviews have been curated, i.e. if the local `references.csv` has been updated.

Dry-run first, since it uploads nothing and needs no Langfuse keys:

```
uv run --project backend --env-file backend/.env python scripts/evals/search/ground_truth/upload.py --dry-run
```

Run it for real:
```
uv run --project backend --env-file backend/.env python scripts/evals/search/ground_truth/upload.py
```

### Methodology details

- A list of a handful of systematic reviews to use as the ground truth has been collected in `input/gt_reviews.csv`. Each must have either a DOI or a URL (as policy papers will not have a DOI) - this is the key that is used to match the target to the references returned by the Policy Atlas search. Each also has a cutoff date, either specified in gt_reviews.csv or the publication date - 1 month.

- These systematic reviews have been collected because they represent a range of policy areas: universal basic income, parental leave, loneliness and so on.

- A separate repo, [policy_atlas_gt_labelling](https://github.com/nestauk/policy_atlas_gt_labelling), handles getting the reference lists for these systematic reviews and curating them so that our recall target is only on-topic/"content" citations (rather than e.g. methodology citations about how to conduct a systematic review).

- For each of the systematic reviews listed in `gt_reviews.csv`, we infer a Policy Atlas query. We deterministically extract "intent" from the title of the systematic review. Because the reviews chosen are ones with "systematic review" or similar in the title, we use deterministic rules to strip the ": a systematic review" part from the end of the title. On the assumption that the title accurately defines the scope of the research, what remains is treated as the "intent". This is important because it means **we're bypassing the Planner/Agent**, so it's not totally faithful to how a real search in Policy Atlas happens. In the app, the Planner turns the user's raw text into an "intent".

Some other points worth knowing:

- The date cut off as recorded in `gt_reviews.csv` is `<date review published> - 1 month`. The OpenAlex date cut off is inclusive so if the date of publication is used directly, you can end up accidentally including the source review itself. We put the cut off 1 month behind that to be on the safe side, as anything published less than a month before the review's publication is highly unlikely to make it into te systematic review.

## 2. Establishing the recall of current production rapid/standard/deep search types

Key scripts/files: `measure/production_recall.py`

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

Key scripts/files: `measure/sweep_record_cap.py`

### What this does

The search stage fetches far more records than it keeps. This experiment tests how just using the rapid search paradigm (i.e. one search round, and no reformulation, citation snowballing etc) and varying the cap on records kept affects recall.

It also compares v2-style and v3 prompting methods. v2 comes with higher latency (aysncio or similar was used in the v2 repo to manage this?) but better recall.

### Usage

```
uv run --project backend --env-file backend/.env python scripts/evals/search/measure/sweep_record_cap.py --caps 50 --generation-backends shared --repeats 1   # smoke test
uv run --project backend --env-file backend/.env python scripts/evals/search/measure/sweep_record_cap.py                                                     # full sweep

```

### Methodology details

- In the Policy Atlas searches, we are at present just trying to calculate a recall metric on search i.e. the very first component of the pipeline. To this end, we just use the rapid search methodology i.e. generating 18 API queries across OpenAlex and Overton, but just one round of queries, and no reformulation, citation snowballing etc. The reason for this is that running multiple rounds would involve relevance screening, and that needs to be evaluated separately. (There is actually already code ready to turn screening on and this is in `measure/sweep_record_cap.py`)

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

- `api` — baseline runs. The **computed** price of the result pages needed to reach that
  cap, at the page size the service returned, from the service's own price table (Consensus
  $0.05 per call, one call per 100 papers returned; OpenAlex reports its own `cost_usd`;
  Semantic Scholar is free). Consensus answers up to 300 results per request on our plan,
  so caps 50, 100 and 200 all cost one request of three calls ($0.15 per review); a request
  sized to the cap would cost less (one call for 50 results). It is not what the run spent:
  with the cache, the services are called once and every cap is scored from the same pages.
- `llm` — pipeline runs. The language-model spend that Langfuse attributes to that review's
  trace (`total_cost`), summed over the reviews.

Neither figure includes flat subscriptions (Overton, OpenAlex premium, the Consensus plan
fee), compute, or Langfuse itself. `n/a` means neither source had a number.

## 5. Search recall baselines: what does good look like?

Key scripts/files: `measure/baseline_recall.py`, `results/cache/`

### What this does

The pipeline's recall numbers (section 2) have nothing to be compared with. Is 5.6% at rapid
depth bad, normal, or as good as this ground truth allows? The baselines answer that with
the simplest possible search: each review's intent text is sent **once, unchanged**, to one
search service. No language model writes queries, nothing is screened, there is no second
round. Three services are tried in four ways, each called an **arm** (as in an experiment):

| Arm | Service | What it is |
|---|---|---|
| `semantic-scholar` | Semantic Scholar, keyword search (`paper/search`) | Free. Every word of the query must appear in the paper, then a ranker orders the matches. A title-length intent matches almost nothing, and that is what this arm shows. Needs a free key. |
| `semantic-scholar-snippet` | Semantic Scholar, semantic search (`snippet/search`) | Free, same key. Ranks passages from title, abstract and body text by meaning. Returns snippets, not papers: 1,000 snippets are about 550 unique papers, and each names its paper by an internal id, so the script looks the DOIs up in a second step. Body text exists only for open-access papers, so this arm leans towards them. |
| `consensus` | Consensus | Paid scholarly search built on Semantic Scholar's corpus with its own ranking. Calls are metered. |
| `openalex-raw` | OpenAlex | The service the pipeline already uses, but with one plain search instead of many generated queries. Free. |

The results are scored exactly like the pipeline runs: same ground truth, same cutoff date
(nothing published after the review's cutoff counts), same scoring key (a lowercase DOI) and
same recall formula. Because every key in the ground truth is a DOI today, all these numbers,
the baselines' and the pipeline's, are **scholarly recall**: a government report the review
cites cannot be found by anyone.

Three things differ between arms on purpose and are written into the notes in `history.md`:
Semantic Scholar matches nothing on hyphenated words, so hyphens are sent as spaces for that
arm only; OpenAlex reads `?` and `*` as wildcards and answers HTTP 400 to them in a normal
search, so a question-shaped intent loses its trailing question mark for that arm only; and
Consensus filters dates by month, so it may include papers from up to 30 days after the
cutoff day.

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
uv run --project backend --env-file backend/.env python scripts/evals/search/measure/baseline_recall.py --arms consensus --reviews parental --dry-run

# All arms, all reviews, all caps; one Langfuse run per arm and cap:
uv run --project backend --env-file backend/.env python scripts/evals/search/measure/baseline_recall.py

# Later, re-score after a code change without calling the services:
uv run --project backend --env-file backend/.env python scripts/evals/search/measure/baseline_recall.py
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

## 6. Growing the ground truth: the `get_*.py` fetchers

### What this does

The four hand-made reviews in `input/` are too few to tell a real improvement from noise. Each `get_<dataset>.py` script pulls one public collection of "a review question plus the studies that answer it" and writes it in the same two-CSV shape that `ground_truth/upload.py` already reads, so nothing downstream changes. Raw downloads go to `results/ground_truth/raw/` and the CSVs to `results/ground_truth/`; git ignores both.

| Script | Source | What one "review" is | Studies per review | `label` column |
|---|---|---|---|---|
| `get_campbell.py` | Campbell Systematic Reviews (a social-policy review journal), listed through OpenAlex | One published review; the title is the intent, the reference list the target | 30 to several hundred | **empty** — needs the labelling pass |
| `get_3ie.py` | 3ie Development Evidence Portal evidence gap maps (development interventions in low- and middle-income countries) | One intervention row of a map (`level = intervention`), or a whole map (`level = map`) | 20 to a few thousand | `content` |
| `get_yef.py` | Youth Endowment Fund Programmes Evidence and Gap Map (preventing youth violence, mostly UK and US studies) | One toolkit strand such as mentoring or hot-spots policing, or the whole map | 20 to a few hundred | `content` |
| `get_sr4all.py` | Webis-SR4ALL-26, a Zenodo corpus of 300,000 systematic reviews found in OpenAlex | One review in a social-science field with a stated research question | 30 or more | **empty** — needs the labelling pass |

Two kinds of target, and they are not equally clean:

- **Gap-map rows** (3ie, YEF) list studies that screeners coded as being about that intervention. Every one is on topic, so the rows are labelled `content` and are scorable straight away. About a quarter to a third have no DOI (grey literature). Those rows keep a URL but cannot be scored until an Overton id is filled in.
- **Reference lists** (Campbell, SR4ALL) mix the studies a review is about with background and methods citations. The `label` column is left empty, so `ground_truth/upload.py` counts none of them until the labelling repo ([policy_atlas_gt_labelling](https://github.com/nestauk/policy_atlas_gt_labelling)) has marked the `content` rows, exactly as was done for the first four reviews.

Columns beyond the ones the loaders read (`dataset`, `review_id`, `level`, `n_references`, `n_with_doi`, `research_questions`, `url`, `year`, `ref_id`) are there for the person choosing and labelling reviews. The loaders ignore them.

### Usage

```
# Each script caches its raw download; add --refresh to download again.
uv run --project backend --env-file backend/.env python scripts/evals/search/get_campbell.py --min-refs 30
uv run --project backend python scripts/evals/search/get_3ie.py --min-studies 20
uv run --project backend python scripts/evals/search/get_yef.py --min-studies 20
# SR4ALL: first download sr4all_full.jsonl (1.6 GB, doi 10.5281/zenodo.18431942) into results/ground_truth/raw/
uv run --project backend --env-file backend/.env python scripts/evals/search/get_sr4all.py --limit 100

# Then pick rows, label where needed, and upload as usual:
uv run --project backend --env-file backend/.env python scripts/evals/search/ground_truth/upload.py \
    --reviews scripts/evals/search/results/ground_truth/3ie_reviews.csv \
    --references scripts/evals/search/results/ground_truth/3ie_references.csv --dataset retrieval-ground-truth-3ie --dry-run
```

### Methodology details

- **Intent.** For a published review the `title` column becomes the intent through `clean_review_title`, which now also strips "an evidence gap map" and "a systematic map" tails. A gap-map row's title is "<map title>: <intervention row>", for example "The effects of rule of law interventions on justice outcomes: Diversion", but that shape suits no search engine, so the getters also write an **`intent` column** built by one fixed template: "What is the evidence on <intervention> in relation to <map theme>?" (`gap_map_question` in `fetch_helpers.py`; every word lower-cased except acronyms, " / " read as " or ", " + " as " and "). The uploader sends the `intent` column when it is filled and the cleaned title otherwise, so the question is deterministic and visible in the CSV before anything is uploaded. Overwrite the cell by hand if a row deserves a better question. (Added 2026-10-05 after the first mini-dataset run scored the gap-map rows near zero on every engine.)
- **Cutoff.** A Campbell or SR4ALL review is identified by its DOI and gets `published_before` one month before its OpenAlex publication date, as before. A gap-map row is identified by a URL, so it needs an explicit date: the script uses 31 December of the latest publication year among the row's studies, the last date a study could carry and still be in the map.
- **3ie's review records are not used.** The portal lists 1,700 systematic reviews, but a review record links to at most four "related" studies, not its included-study list. Only the maps carry full study lists. The maps are read through the two JSON calls the map page itself makes; there is no documented API. 3ie's terms allow non-commercial use with attribution.
- **SR4ALL selection** is repeatable: English reviews with a DOI, at least one stated research question, at least `--min-refs` references, a non-protocol title and a `field` in `--fields` (default: Social Sciences, Psychology, Economics, Business), then the `--limit` most cited. The stated research questions are kept in the `research_questions` column for a later eval that starts from a question instead of a title.
- **Duplicate titles** (an updated review with the same title as the original) are dropped after the first, because the title is the join key between the two CSVs.

## 7. The ground-truth sample: 100 reviews, and a cheap 15

Key script: `ground_truth/select_sample.py`. Outputs: `results/ground_truth/sample_full_*.csv` and
`sample_mini_*.csv` (git-ignored like everything under `results/`; the script rebuilds them
from the fetched files in a second, and the same inputs always give the same sample).

### Why two sizes

A full pipeline run costs about $1.75 per review at deep depth and $1 at standard; a
Consensus baseline costs $0.50 per review; Semantic Scholar is free. So one round over the
100 costs about $200 and one round over the 10 about $20. Use the 10 for quick checks while
changing code, and the 100 for a number you would quote.

### The quality check (owner decisions, 2026-10-05)

A candidate review from any collection is kept only if:

1. It is **one specific question**: an intervention row of a gap map or a single published
   review, not a whole map, and its title appears once in its collection (the title is the
   join key between the two CSV files).
2. It has **between 20 and 300 references with a DOI**. Below 20, one hit moves recall by
   whole tens of a percent (the hand-made social-care review has 7). Above 300, one list
   dominates a run.
3. **At least 70% of its references carry a DOI** (YEF: 50%, because it cites many
   evaluation reports and only seven strands would pass at 70%). Every recall number is
   scholarly recall until the grey-literature keys exist (P2), so a list that is mostly
   grey literature would measure the gap in the ground truth, not the search.
4. Its **cutoff date is in the past and 2010 or later**. Four 3ie rows and one YEF strand
   have a cutoff of 31 December 2026 because the map still gains studies; they wait.
5. Its title is **not a protocol, an editorial or a guide**. Those have a reference list
   but no included studies, so there is nothing for a search to find. (Campbell publishes
   protocols as articles; nine of its 349 candidates are protocols, guides or editorials.)

Then the script takes the collection's quota by rotating across groups so no single
subject fills it: for gap maps the group is the map (3ie rows share their map's title),
for Campbell and SR4ALL it is a coarse keyword topic (education, crime and justice, mental
health, families and children, welfare and work, health, development and environment,
organisations and innovation, other). Inside a group the rows with the highest DOI share
come first. The `topic` column in the reviews file records the tag; it is only used to
spread the picks, never to score.

On the collections fetched on 2026-09-25 the check keeps 250 of 349 Campbell reviews, 88
of 197 3ie rows, 91 of 100 SR4ALL reviews and 13 of 20 YEF strands. `--verbose` prints
why each rejected row failed.

### The cheap 15

Eleven rows are chosen by hand from the hundred (`SAMPLE_MINI_TITLES` in the script; the
script refuses a title that is not in the hundred, so the mini set is always a subset of the
full one), plus the four hand-made reviews. They lean towards Nesta's missions (a healthy
life, a fairer start, a sustainable future). The **intent** column is the exact text every
baseline arm receives and the pipeline's query generator starts from: the review title with
its "a systematic review" tail removed by `clean_review_title`, or for a gap-map row the map
title followed by the intervention.

| Source | Intent sent to the services | Why |
|---|---|---|
| Campbell | Health and Social Care Interventions in the 80 years Old and Over Population | health and social care |
| Campbell | Evidence and Gap Map of Whole-School Interventions Promoting Mental Health and Preventing Risk Behaviours in Adolescence: Programme Component Mapping Within the Health-Promoting Schools Framework | schools, a fairer start |
| Campbell | Residential energy efficiency interventions | home energy, a sustainable future |
| 3ie | What is the evidence on core skills training in relation to improving labour market outcomes through learning to earning interventions in low- and middle-income countries? | jobs and skills |
| 3ie | What is the evidence on consumption or provision of large-scale fortified foods in relation to nutrition-sensitive agriculture? | food and health |
| 3ie | What is the evidence on civic and legal education in relation to human rights? | a non-social-policy control |
| SR4ALL | Recent intimate partner violence against women and health | violence and health |
| SR4ALL | A systematic review and meta-analysis of the evidence on learning during the COVID-19 pandemic | learning loss |
| SR4ALL | Risk and protective factors of drug abuse among adolescents | young people |
| SR4ALL | Sleep duration and incidence of obesity in infants, children, and adolescents | child health, early years |
| YEF | What is the evidence on trauma-specific therapies in relation to interventions to prevent children and young people's involvement in violence? | the one gap-map strand |
| hand-made | The effect of parental leave on parents' mental health | the original four, labelled |
| hand-made | Tackling loneliness evidence review: main report | the original four, labelled; mostly grey literature |
| hand-made | Adverse childhood experiences in children and youth experiencing homelessness | the original four, labelled |
| hand-made | Social care shows that privatisation will not be the answer to NHS inequality | the original four, labelled; only 7 references |

The four gap-map intents are question-shaped by the template described in section 6
(since 2026-10-05; the first mini run used the "map title: row" form and scored them near
zero on every engine). Two intents keep a title tail the cleaner does not strip: the Campbell whole-school map ends
in "An evidence and gap map" inside a longer colon-separated title, and the SR4ALL learning
review *starts* with "A systematic review and meta-analysis of the evidence on", which the
cleaner only removes from the end. Both are sent as shown.

To change them, edit `SAMPLE_MINI_TITLES`, re-run the script, re-upload the dataset and
delete the items that dropped out (an upload upserts and never deletes).

### The mini dataset also carries the four hand-made reviews

`retrieval-ground-truth-mini` holds the eleven rows above **plus the four original reviews**
(parental leave, loneliness, adverse childhood experiences, social care), fifteen items in
all, so a number measured on it can be read next to the rows already in `history.md`. The
originals have no CSV files in this repo; `upload.py --include-from retrieval-ground-truth`
copies them out of their own Langfuse dataset, re-keyed for the target and marked
`copied_from` in their metadata. `retrieval-ground-truth-full` holds the hundred only.

### Labels: no labelling pass, and what that does to the numbers

The owner decided on 2026-10-05 to **skip the labelling pass**. Every reference in the
sample is written `label = content`, including the Campbell and SR4ALL reference lists
that nobody has read. A reference list mixes the studies a review is about with background
and methods citations, so perhaps half of its rows are off topic, and a search that found
every on-topic study would still score near **50%** on those rows. Read Campbell and
SR4ALL recall against that ceiling, not against 100%. Gap-map rows (3ie, YEF) were coded
by the map's screeners and have no such ceiling. The reviews file says which is which in
`target_labelled` (`yes` for gap maps, `no` for lists); keep the two kinds apart when you
compare numbers. This revises D11 of the task 046 contract for these two samples.

### Usage

```
uv run --project backend python scripts/evals/search/ground_truth/select_sample.py --verbose

# Upload the mini dataset: the 11 sampled rows plus the 4 original reviews (drop --dry-run to upload):
uv run --project backend --env-file backend/.env python scripts/evals/search/ground_truth/upload.py \
    --reviews scripts/evals/search/results/ground_truth/sample_mini_reviews.csv \
    --references scripts/evals/search/results/ground_truth/sample_mini_references.csv \
    --dataset retrieval-ground-truth-mini --include-from retrieval-ground-truth --dry-run
# The full dataset: the same with sample_full and --dataset retrieval-ground-truth-full (no --include-from)

# Then measure against a sample instead of the four hand-made reviews:
uv run --project backend --env-file backend/.env python scripts/evals/search/measure/baseline_recall.py --dataset retrieval-ground-truth-mini
uv run --project backend --env-file backend/.env python scripts/evals/search/measure/production_recall.py --dataset retrieval-ground-truth-mini --depths rapid
```

The four hand-made reviews stay in `retrieval-ground-truth`, so the rows already in
`results/history.md` keep their meaning. Rows measured on a sample say which dataset in
the `run` column.
