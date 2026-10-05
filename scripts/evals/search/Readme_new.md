# Search evals

These scripts measure **search recall**: of the studies that a systematic review included, how many does a search find? We use published reviews as the "right answer" (the ground truth) and score different ways of searching against them.

All runs and scores are stored in [Langfuse](https://langfuse.com) (our tool for tracing and evaluating language-model apps). The headline numbers are copied into `results/history.md`, so the history lives in git next to the code.

---

# Part 1: Methodology

## 1. Ground truth

One item in the ground truth is one review:

- **Intent** (the input): a short text that says what the review is about. This is what a search receives.
- **Target** (the expected output): the list of studies that the review covers. Each study is identified by its DOI (Digital Object Identifier, the permanent ID of a published paper).
- **Cutoff date**: one month before the review was published. Studies published after this date cannot count, because the review could not include them.

**Recall** = the share of the target studies that the search found, before the cutoff date.

### Systematic review sources for the ground truth dataset

| Source | What one item is | Is the target clean? |
|---|---|---|
| **Hand-made** (4 reviews: parental leave, loneliness, adverse childhood experiences, social care) | One review. A person removed the off-topic citations in the [labelling repo](https://github.com/nestauk/policy_atlas_gt_labelling). | Yes |
| **3ie** evidence gap maps (development interventions in low- and middle-income countries) | One intervention row of a map | Yes. Screeners coded each study as on topic. |
| **YEF** (Youth Endowment Fund) evidence and gap map (preventing youth violence) | One strand of the map, for example mentoring | Yes, as above |
| **Campbell** Systematic Reviews (a social-policy review journal, read through OpenAlex) | One published review | No. See "Limits" below. |
| **SR4ALL** (a public corpus of 300,000 systematic reviews) | One social-science review | No. See "Limits" below. |

### How the intent is made

The intent is made by fixed rules, not by a language model. This makes it the same on every run.

- **Published review**: the title, with tails such as ": a systematic review" removed.
- **Gap-map row**: a question from a template: "What is the evidence on *intervention* in relation to *map theme*?"

Note: in the app, a Planner turns the user's text into an intent. The evals skip the Planner. They test the search only.

### Mini and full ground truth samples

`ground_truth/select_sample.py` picks the samples from the fetched collections. It keeps a review only if it:

1. asks one specific question (not a whole map),
2. has 20 to 300 references with a DOI,
3. has a DOI for at least 70% of its references (50% for YEF),
4. has a cutoff date in the past, and 2010 or later,
5. is not a protocol, editorial or guide.

Then it rotates across topics so that no single subject fills the sample. The same inputs always give the same sample.

| Langfuse dataset | Contents | Use it for |
|---|---|---|
| `retrieval-ground-truth` | The 4 hand-made reviews | Comparing with older rows in `history.md` |
| `retrieval-ground-truth-mini` | 11 hand-picked rows from the full sample, plus the 4 hand-made reviews (15) | Quick checks while you change code (about $20 per round) |
| `retrieval-ground-truth-full` | 30 Campbell + 30 3ie + 30 SR4ALL + 10 YEF (100) | A number you would quote (about $200 per round) |

### Limits

- **Only scholarly recall.** All targets are matched by DOI. A government report without a DOI cannot be found, so it is not counted.
- **Campbell and SR4ALL targets are not labelled.** A reference list mixes the studies a review is about with background and methods citations. We decided (2026-10-05) not to label them. So a perfect search probably scores only about **50%** on these rows (verificaiton needed). The `target_labelled` column (`yes` / `no`) tells you which rows have this ceiling. Do not compare the two kinds directly.
- **Small reviews are noisy.** With 20 references, one found study changes recall by 5 percentage points.

## 2. Measures

There are three kinds of run. Each answers a different question.

### Production runs: how good is the real pipeline?

`measure/production_recall.py` runs the search exactly as the app does, at each depth:

| Depth | What runs | Scores |
|---|---|---|
| `rapid` | One search round. A language model writes queries for OpenAlex and Overton. No screening. | Search recall |
| `standard`, `deep` | Search, then screen the new results with a language model, then search again (reformulated queries, citation snowballing and so on) until the depth's round limit, or until screening finds few new studies | Search recall and screen recall |

**Search recall** is measured on everything the search kept. **Screen recall** is measured on what the screening step kept as relevant.

Nothing is saved to the database. Each run is rolled back.

### Baselines: what does "good" look like?

A production recall of, say, 6% means nothing alone. The baselines give a number to compare it with. `measure/baseline_recall.py` sends each intent **once, unchanged**, to one search service. There is no language model, no screening and no second round. Each service is called an **arm**:

| Arm | Service | Notes |
|---|---|---|
| `openalex-raw` | OpenAlex, one plain search | The same service the pipeline uses. If this matches the pipeline, our query writing adds little. |
| `semantic-scholar` | Semantic Scholar keyword search | Every word must match, so long intents find little. Free. |
| `semantic-scholar-snippet` | Semantic Scholar semantic search (by meaning) | Free. Favours open-access papers. |
| `consensus` | Consensus | Paid: $0.05 per call. |

Each arm is scored at several caps (the first 50, 100, 200 and 1,000 results).

**How to compare**: put a baseline row next to a production row with a similar number of kept results (`n_candidates_kept`). For example, `rapid` keeps up to 50 per service, so compare it with the baselines at cap 50 and 100. 

### Record-cap sweep: an experiment

`measure/sweep_record_cap.py` asks a research question: does recall go up if the search keeps more results? It runs a `rapid` search many times. Each time it changes:

- the cap on results kept from each service (50, 100, 250, 500, 1,000, 2,000), and
- the query-writing method: `shared` (v3, one prompt writes queries for both services) or `per-provider` (v2, one prompt per service).

Keeping more results costs more later: every kept result is screened and stored for the synthesis step.

### Cost

`history.py` shows a **variable cost** for each run: money that grows with how much you search. `api` is the service price (baselines). `llm` is the language-model spend that Langfuse records (pipeline runs). Fixed subscriptions are not included.

---

# Part 2: How to run it

## Folder structure

```
scripts/evals/search/
├── evals_search_utils.py   shared helpers: DOI matching, intent from title, cutoff dates
├── history.py              prints one table row per Langfuse run
├── ground_truth/           builds the dataset
│   ├── getters/            get_campbell.py, get_3ie.py, get_yef.py, get_sr4all.py
│   ├── fetch_helpers.py    shared code for the getters
│   ├── select_sample.py    quality check, makes the mini and full samples
│   └── upload.py           CSV files -> Langfuse dataset
├── measure/                runs the measurements
│   ├── production_recall.py
│   ├── baseline_recall.py
│   ├── sweep_record_cap.py
│   ├── engine.py           runs one intent through the real search (no command line)
│   └── inspect_run.py      tables of one run's raw output (no command line)
├── tests/                  self-checks, no network and no database
├── input/                  the 4 hand-made reviews as CSV (git-ignored; from the labelling repo)
└── results/                outputs (git-ignored, except history.md)
    ├── history.md          the headline results, kept by hand
    ├── cache/              raw baseline results, one JSON file per arm and review
    └── ground_truth/       fetched collections and the two samples
```

Each script starts with `import _bootstrap`. This short file lets the script import its neighbours, so you can run any script directly.

## How data flows

```
getters ──> select_sample.py ──> upload.py ──> Langfuse dataset
                                                   │
                ┌──────────────────────────────────┼─────────────────────┐
                v                                  v                     v
       production_recall.py                baseline_recall.py    sweep_record_cap.py
                │                                  │                     │
                └──> engine.py (real search) <─────┼─────────────────────┘
                                                   v
                                Langfuse runs and scores ──> history.py ──> history.md
```

The measuring scripts read the ground truth from Langfuse, not from the CSV files. Upload the dataset first.

## Commands

All commands run from the repository root. Keys go in `backend/.env`: Langfuse keys, `SEMANTIC_SCHOLAR_API_KEY` and `CONSENSUS_API_KEY`. Most scripts have `--dry-run` (do everything, upload nothing) and `--reviews` (run only some reviews). Use `--help` to see all options.

### 1. Build and upload the ground truth

Do this only when the ground truth changes.

```
# Fetch the collections (each script caches its download; --refresh downloads again)
uv run --project backend --env-file backend/.env python scripts/evals/search/ground_truth/getters/get_campbell.py --min-refs 30
uv run --project backend --env-file backend/.env python scripts/evals/search/ground_truth/getters/get_3ie.py --min-studies 20
uv run --project backend --env-file backend/.env python scripts/evals/search/ground_truth/getters/get_yef.py --min-studies 20
# SR4ALL: first download sr4all_full.jsonl (1.6 GB, DOI 10.5281/zenodo.18431942) into results/ground_truth/raw/
uv run --project backend --env-file backend/.env python scripts/evals/search/ground_truth/getters/get_sr4all.py --limit 100

# Pick the samples (no network; --verbose says why each row was rejected)
uv run --project backend --env-file backend/.env python scripts/evals/search/ground_truth/select_sample.py --verbose

# Upload the mini dataset (the 11 sampled rows plus the 4 hand-made reviews)
uv run --project backend --env-file backend/.env python scripts/evals/search/ground_truth/upload.py \
    --reviews scripts/evals/search/results/ground_truth/sample_mini_reviews.csv \
    --references scripts/evals/search/results/ground_truth/sample_mini_references.csv \
    --dataset retrieval-ground-truth-mini --include-from retrieval-ground-truth

# Upload the full dataset: the same with sample_full and --dataset retrieval-ground-truth-full (no --include-from)
# Upload the 4 hand-made reviews: uv run --project backend --env-file backend/.env python scripts/evals/search/ground_truth/upload.py (reads input/)
```

An upload adds and updates items. It never deletes them. If a review drops out of a sample, delete its item in Langfuse by hand.

### 2. Measure

```
# Production: one Langfuse run per depth
uv run --project backend --env-file backend/.env python scripts/evals/search/measure/production_recall.py --dataset retrieval-ground-truth-mini --depths rapid
make eval-search-recall ARGS="--depths rapid"         # same, on the default dataset

# Baselines: one Langfuse run per arm and cap
uv run --project backend --env-file backend/.env python scripts/evals/search/measure/baseline_recall.py --dataset retrieval-ground-truth-mini

# Sweep: smoke test, then the full sweep
uv run --project backend --env-file backend/.env python scripts/evals/search/measure/sweep_record_cap.py --caps 50 --generation-backends shared --repeats 1
uv run --project backend --env-file backend/.env python scripts/evals/search/measure/sweep_record_cap.py
```

The baselines call each service **once** and save the raw results in `results/cache/`. Later runs score from the cache and cost nothing. Use `--refresh` only when you need fresh results: Consensus charges for every call.

Before you read recall, check `n_failed_calls`. If it is above 0, a service call failed, and recall for that review is too low.

### 3. Record the results

```
uv run --project backend --env-file backend/.env python scripts/evals/search/history.py --since 2026-10-01
```

This prints one markdown row per run. Copy the rows that matter into `results/history.md` and add a note: what changed, and anything that affects how to read the number.

### 4. Check the scripts

```
make eval-check
```

This runs the self-checks in `tests/` and ruff (the code linter) on this folder. `make verify` includes it.
