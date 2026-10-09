# Screening eval

These scripts measure **screening**: given a research question and a document's title and abstract, does the app's relevance screen make the same include or exclude decision as the humans who labelled that document?

A run spends money on the language-model calls. There are two dataset sizes, both over the same thirty questions:

| Dataset | Documents | Included | Mix (CSMeD / SYNERGY / 3ie) | Estimated cost, production setting |
| --- | ---: | ---: | --- | ---: |
| `mini` (default) | 288 | 144 | 88 / 100 / 100 | about $0.90 |
| `full` | 2,949 | 954 | 281 / 1,168 / 1,500 | about $9 |

Try a setting on `mini` first. Run `full` only for a setting that already looks good and cheap on `mini`. The cost is gpt-5.4-mini with three replies, scaled from a one-question pilot on 2026-10-08. The same run on gpt-5.6-luna costs about a quarter as much. The run itself records the real cost.

---

## What is being measured

One item is one published review, or one evidence gap map (a map of which interventions have been studied). The question is the review's or map's published title, and it is passed to the screen as the scope intent: the description of what would count as relevant. The questions live in `targets.json`, which `build_targets.py` builds from the published sources (see "Where the questions come from").

The screen under test is the app's stage-1 screen (`screen_v2` in the product code). Stage 1 reads the title and abstract only. These datasets have no full text, so stage 2 is not run. The eval calls the app's own stage-1 code (the production screening backend and call loop), so the prompt, the order of calls, the number of calls in parallel and the retries are the app's. The model, the number of replies and the reasoning effort can be changed for one run; the app's settings are not edited. The model, the prompt, and the keep rule are the ones the app uses:

- The default model is `gpt-5.4-mini`.
- The default asks for three independent replies per document.
- `unsure` counts as a vote to keep the document. A tie keeps it. A document with no abstract is kept if any reply said `relevant`, even when the other replies said `not_relevant`.
- With three replies, at least two must parse. Fewer than that and the document counts as not kept.

A one-reply run (`--reps 1`) decides from that single reply. That is the main way to cut the cost: three calls become one.

**Recall** is the share of human-included documents the screen also kept. **Precision** is the share of kept documents that humans included. **F2** weights recall twice as heavily as precision.

### What one row is

A "document" in this eval is one row with four parts. The model sees the first two and answers keep or drop; the eval compares that answer with the third.

| Part | What it is |
| --- | --- |
| **Question** | The published title of the review or map, with an ending such as ": a systematic review" removed. It goes to the model as the scope intent, the same way a user's research question does in the app. With `--criteria`, the review's published criteria are added under it (see below). |
| **Title and abstract** | One study from that review's data. The median abstract is about 1,500 characters. In `mini`, 19 of the 288 rows have no abstract; those go through the title-only keep rule. |
| **Human label** | 1 = include, 0 = exclude. What "exclude" means depends on the source (see below). |
| **Model answer** | The stage-1 screen: three replies, then the vote, giving keep or drop. |

Each study belongs to one question only. `mini` and `full` use the same 30 questions; only the number of rows per question changes.

### What the questions cover

| Theme | Questions | Rows in `mini` | Source |
| --- | ---: | ---: | --- |
| Clinical medicine (for example statins, heart failure, delirium, Alzheimer's drugs, Wilson disease) | 11 | about 100 | CSMeD 8, SYNERGY 3 |
| Psychology and mental health (for example therapy for anxiety, PTSD, support for cancer patients) | 6 | about 56 | CSMeD 2, SYNERGY 4 |
| Criminal justice (drug-using offenders) | 1 | 8 | CSMeD |
| Software engineering (predicting faults in code) | 2 | 20 | SYNERGY |
| International development (for example climate, governance, migration, water and sanitation, anaemia) | 10 | 100 | 3ie |

About two thirds of the rows are health and psychology. Only the 3ie third, and the drug-offenders question, are close to the policy topics the app is for. The 3ie questions are also broad (the scope of a whole gap map), not narrow review questions.

### The three labelled sources, and what "exclude" means in each

| Source | Include means | Exclude means | Recall | Precision |
| --- | --- | --- | --- | --- |
| **SYNERGY** (a public set of screening decisions from systematic reviews) | The review included the study | A human screener excluded it on title and abstract | Good | **Good: the only clean precision in this eval** |
| **CSMeD** (Cochrane reviews; the file is `CSMeD-FT`, the full-text stage) | The review included the study after reading the full paper | A human **kept** it on title and abstract, then excluded it after reading the full paper | Good | **Not fair to stage 1** (see below) |
| **3ie** (evidence gap maps of development programmes) | The study is on the named map | A study from one of the other nine maps, the same number from each map | Good | **Weak** (see below) |

Why the precision numbers differ:

- **SYNERGY.** Every exclude is a real title-and-abstract decision by a human, against this question. One small caveat: the include label is the review's final decision, so a few includes were dropped later, at full text.
- **CSMeD.** Every study in this file already passed human screening on title and abstract. Its excludes are studies a human also kept at that stage. Stage 1 is built to keep studies like these, so when it does, the eval counts a false positive. Read CSMeD precision as "how often stage 1 already spots what a full-text reader would drop", not as an error rate. This is also why some Cochrane questions have very few excludes (Rosuvastatin has one).
- **3ie.** Nobody judged the excludes against this question. 3ie gives no excluded studies, so the eval borrows studies from the other nine maps, the same number from each, and labels them "not relevant". Most are easy (a water study for a governance question). Two safeguards:
  - The maps overlap: one study can be on both the climate map and the food-systems map. A borrowed study whose title is also on the question's own map is left out, because 3ie's own coders count it as relevant. Before this rule, 4 of the 50 3ie excludes in `mini` had the wrong label.
  - Equal numbers from each map stop the largest maps (food systems, anaemia) from supplying most of the excludes.

  A borrowed study can still be relevant without being on the map (for example a fortification study from the anaemia map for the food-systems question). So some 3ie "false positives" may be right answers.

How to report a run:

- **Recall on included documents is the main number.** It is sound in all three sources.
- **Report precision per source, never pooled.** Use SYNERGY for the precision level. Use CSMeD and 3ie precision only to compare one setting with another.
- **For the policy side, look at 3ie.** It was also the weakest source for recall in the earlier prototype (0.73).

### How rows are sampled

Every source goes through the same sample, per question:

| Dataset | Most included | Most excluded |
| --- | ---: | ---: |
| `mini` | 5 | 5 |
| `full` | 50 | 100, and at most three per included |

The draw uses a fixed seed, so the same files always produce the same sample, and every `mini` document is also in `full`. `mini` has as many included as excluded documents, so its precision reads higher than on real search results, where only a few per cent are relevant. A few Cochrane questions have fewer than five included or excluded studies, so `mini` has 288 documents, not 300.

With 144 included documents, `mini` recall has a margin of about ±5 points (for a recall near 0.90). It can show a large drop, but not a difference of one or two points; that needs `full`.

---

## Folder structure

```
scripts/evals/screening/
├── targets.py          the catalogue: which review or map each question is
├── targets.json        the questions and criteria, built from published text (in git)
├── targets_sources.json fingerprints of the source files targets.json was built from (in git)
├── build_targets.py    builds targets.json; no language model involved
├── adapter.py          load the three sources and sample them (mini or full)
├── vote.py             the app's keep rule
├── metrics.py          recall, precision, F2, and the dollar cost
├── sync_s3.py          download the datasets and upload a run, via the AWS command line
├── measure/run_screen.py     one run: screen, score, write a folder
├── measure/analyse_runs.py   summarise and compare saved runs (no model calls)
├── measure/rank_baselines.py non-AI baselines: BM25, embeddings, hybrid
├── prompts/            replacement system prompts for prompt experiments
├── tests               self-checks, no network and no model calls
├── datasets/           the downloaded files (not in git)
└── results/
    ├── history.md      headline numbers, kept by hand
    ├── analyses/       dated write-ups of an experiment (kept in git)
    └── runs/           one folder per run (not in git)
```

## How data flows

```
s3://discovery-policy-atlas/eval/datasets/screening/
        │  aws s3 sync  (sync_s3.py download)
        v
    datasets/  ──>  adapter.py  ──>  run_screen.py  ──>  results/runs/<folder>/
        ^                                              │
        │                                              │  aws s3 sync  (sync_s3.py upload)
        └── targets.py                                 v
                         s3://discovery-policy-atlas/eval/results/screening/<folder>/
```

The bucket is the same one the earlier prototype used. The results prefix is new, so an upload does not mix with the datasets.

---

## Commands

All commands run from the repository root.

The language-model key is `OPENAI_API_KEY` in `backend/.env`. The AWS command-line tool uses your default profile. Log in the way you usually do first. This should print your account, not an error:

```
aws sts get-caller-identity
```

### 1. Download the ground truth

Do this once, or again when the files on S3 change. The folder name `CESMeD` is the spelling in the bucket (capitals matter on Linux); the source itself is called CSMeD.

```
uv run --project backend python scripts/evals/screening/sync_s3.py download
```

### Where the questions come from

`build_targets.py` copies text from the published sources and picks it by fixed rules. No language model writes any of it, and running the script again gives the same file. Each entry in `targets.json` records where its text came from.

| Source | Question (`query`) | Criteria (`criteria`, used with `--criteria`) |
| --- | --- | --- |
| CSMeD | The Cochrane review title (from the CSMeD metadata file) | The "Objectives" section of the review's abstract |
| SYNERGY | The review title on OpenAlex, found by the DOI SYNERGY gives | The eligibility criteria SYNERGY quotes from the paper (`datasets.toml` at a fixed commit), one per line |
| 3ie | The map title, from the 3ie portal or publication page | The map's own top-level intervention and outcome groups, from 3ie's map data |

Rules:

- The ending of a title that names the kind of publication (": a systematic review", ": an evidence gap map") is removed.
- Criteria are added under the question by the product's own code (`_compose_screen_intent`), exactly as when a plan in the app carries screening criteria. The product refuses more than 2,000 characters in total, and more than 1,000 for one criterion. A longer criterion is split into sentences. If the total is still too long, the last criteria are dropped, and `criteria_dropped` records how many.
- Two 3ie maps (climate, anaemia) are not on the 3ie portal's open map data, so they have no criteria.
- For portal maps, the script checks that at least 90% of the local file's studies are on that map.

Rebuild after a source changes (downloads go to `datasets/sources/`):

```
uv run --project backend python scripts/evals/screening/build_targets.py
```

OpenAlex and 3ie can change their records, so the build also writes `targets_sources.json`: a SHA-256 fingerprint (a code computed from a file's content) of every source file it read. If a rebuild changes `targets.json` or a fingerprint, a source changed. Each run records which `targets.json` it used (`questions`, a hash) and whether criteria were added (`criteria`). Runs before 2026-10-08 13:00 used hand-written questions (`query_v1` in `targets.py`); `analyse_runs.py` labels them "v1 (hand-written)".

### 2. Score

```
# mini dataset, production settings: gpt-5.4-mini, three replies per document
uv run --project backend --env-file backend/.env python scripts/evals/screening/measure/run_screen.py

# The same, with each question's published criteria added under it
uv run --project backend --env-file backend/.env python scripts/evals/screening/measure/run_screen.py --criteria

# One reply per document (about a third of the calls)
uv run --project backend --env-file backend/.env python scripts/evals/screening/measure/run_screen.py --reps 1

# The same one-reply run on gpt-5.6-luna
uv run --project backend --env-file backend/.env python scripts/evals/screening/measure/run_screen.py --reps 1 --model gpt-5.6-luna

# full dataset (about 3,000 documents), only for a setting that looks good on mini
uv run --project backend --env-file backend/.env python scripts/evals/screening/measure/run_screen.py --dataset full
```

`--targets Name1 Name2` scores a chosen subset, for example a pilot of a few cents. `--reasoning-effort low` sets the reasoning effort; leaving it off matches the app. `--system-prompt scripts/evals/screening/prompts/<file>.txt` replaces the stage-1 system prompt for this run only. The production prompt is hash-pinned and is never edited by the eval; the run JSON records the file name and a hash of the text (`system_prompt`).

Each run writes `results/runs/<date>-<dataset>-<model>-r<replies>/`:

- `result_<target>.csv` — one row per document, with the human label and the screen's decision
- `eval_results.json` — recall, precision, F2, token counts, the dollar cost, and `dataset_files`: a fingerprint (SHA-256 hash) of every downloaded dataset file. Two runs with the same `dataset_files` used the same inputs. The download does not delete local files that were removed on S3, so compare this before comparing two runs from different machines.

The cost is tokens times the published OpenAI rate stored in `metrics.py` (checked 2026-10-08). A model that is not in that table still records its tokens, and prints the cost as unknown.

### 3. Upload the run

```
uv run --project backend python scripts/evals/screening/sync_s3.py upload \
    scripts/evals/screening/results/runs/<folder name>
```

### 4. Summarise and compare runs

`analyse_runs.py` reads saved run folders and prints Markdown. It makes no model calls, so the same folders always give the same numbers. Every number in `results/history.md` and the task notes comes from it.

```
uv run --project backend python scripts/evals/screening/measure/analyse_runs.py \
    scripts/evals/screening/results/runs/<run A> scripts/evals/screening/results/runs/<run B>
```

For each run and each source it prints:

- recall on included documents, with a 95% interval;
- excludes dropped;
- precision, F1 and F2, for SYNERGY and for all sources together only (F1 weighs precision and recall equally; F2 counts recall twice as much);
- the expected one-call recall: a document's chance of being kept by one call is the share of its calls that voted keep;
- how often all calls agree, and the count of `unsure` answers.

For a run with three calls per document it also replays other ways of combining the same answers (one call, keep if any keeps, ask again only after a "drop"), with recall, excludes dropped and calls per document, and estimates how often two one-call runs would disagree. With two runs it also lists the included documents only one run kept, and gives an exact McNemar test (is the split bigger than chance?). With two or more runs it lists the included documents every run dropped.

### 5. Compare with non-AI baselines

`rank_baselines.py` ranks each question's documents without a language model, so a language-model run has something fair to beat:

- **BM25**: the classic search-engine keyword score. Standard library only, fully deterministic.
- **Embeddings**: cosine similarity between the question and each document, with the product's own embedding model (`text-embedding-3-small`). No training. Vectors are cached in `results/cache/`, so a rerun gives the same numbers. A full `mini` run costs under one cent.
- **Hybrid**: reciprocal rank fusion of the two rankings.

A ranking is not a keep-or-drop decision. The report says whether the rankers got the same scope text as the run (question only, or question and criteria); match it with `--criteria` for a like-for-like comparison. With `--match <run folder>`, each ranker keeps, for every question, as many documents as that language-model run kept. Both then spend the same reading effort, and the table compares recall, excludes dropped, precision, F1 and F2, with an exact McNemar test on the included documents. A "chance" row gives what a random pick of the same size would reach on average. Without `--match` it prints only ranking quality (AUC and average precision, per question).

```
uv run --project backend --env-file backend/.env python scripts/evals/screening/measure/rank_baselines.py \
    --criteria --match scripts/evals/screening/results/runs/<run folder>
```

Outputs go to `results/baselines/` (scores per document, and the report).

### 6. Record the headline

Copy the row that matters into `results/history.md`, with a note on what changed. A longer comparison of several settings belongs in `results/analyses/`, dated, the same way the search experiments are written up.

### 7. Check the scripts

`make eval-check` runs these, together with the search eval's checks:

```
uv run --project backend python scripts/evals/screening/tests/test_screening.py
uv run --project backend ruff check scripts/evals/screening
uv run --project backend ruff format --check scripts/evals/screening
```
