# Post-screening synthesis coverage eval

These scripts measure the stages **after screening**: classify, appraise, screen_full, characterise, select, extract, group and synthesise. The question is: given a published POST or CAPE briefing's own reference list as the corpus, does the Policy Atlas report capture the briefing's key facts?

The search and screening evals (`../search`, `../screening`) cover the earlier stages. This one starts where they stop, so search is bypassed and stage-1 screening is pre-filled.

---

## What is being measured

One item is one published briefing from the team's test-set Google Sheet (tab `POST_test_set`; 19 briefings at the time of writing: 4 CAPE rapid evidence assessments, 6 POSTbriefs, 5 POSTnotes, 4 POST rapid responses). The sheet is the source of truth: add a row there to add a briefing. Each briefing has a slug in the `Doc ID` column, such as `effects_artificial_light`; the slug names its briefing file, its ground-truth and cache folders, its run folder and its Langfuse dataset item. For each briefing:

1. **Ground truth.** Three model calls. The first extracts the briefing's reference list. The second is given that list and the briefing and returns the briefing's key points, each tied to the references it cites. The third sees only the key points, not the briefing, and breaks each into atomic facts: one claim per fact, self-contained, so the judge can grade it alone. Withholding the briefing from the third call stops detail the point does not state from leaking into the facts. The model chooses how many points and how many facts per point. Each fact row carries its point's id and text. A human checks both lists and marks rows to keep.
2. **Corpus.** Each kept reference is resolved to text: OpenAlex by DOI or strict title match, then the production URL cascade, fetcher and parser. A reference with no full text but an OpenAlex abstract enters as `abstract_only`. One with neither is dropped and recorded.
3. **Run.** A task is seeded with an approved plan at the chosen analysis depth, the corpus is ingested as uploads, and every source gets a stage-1 `relevant` screen row. The plan walk then runs with no search backends, so acquire adds nothing and the walk's own stage-1 screen has nothing to do. `screen_full` (standard and deep) runs as in production; its demotions are recorded.
4. **Judge.** The report's markdown (citation markers stripped) is graded against each key fact by a model, one call per fact. Verdicts: `fully_represented`, `partially_represented`, `not_represented`, `misrepresented`, `uncertain`.

**Coverage** is the share of key facts judged `fully_represented`. It is reported with two denominators: all checked facts (`coverage_all`), and only facts with at least one reference that made it into the corpus (`coverage_ingested`). The gap between them is the cost of unfetchable sources, not of the pipeline. Each has a lenient twin (`coverage_all_lenient`, `coverage_ingested_lenient`) whose numerator also counts `partially_represented`. The gap between strict and lenient is the share of facts the report touches but states incompletely.

The eval-side model for extraction and judging is `gpt-5.6-luna`. The pipeline runs with its production backends and models.

## Data

The important raw data is:

* [Google Sheets] `05. Evals >> synthesis >> Post test set`: this is a reference sheet that records: the short slug for each briefing; its title; when it was published; the corresponding RQ that will be run through the Policy Atlas pipeline.

* [s3] `eval/datasets/synthesis/inputs/briefings/` This folder contains the downloaded pdf/html files for the briefings used in this experiment. They were downloaded by hand because the POST domain blocks bots.

## Files

```
00_update_ground_truth.py  sheet vs Langfuse -> extract + resolve the new briefings
01_upload_to_langfuse.py   ground truth -> S3 and Langfuse dataset `synthesis-coverage` (dry run by default)
02_run_evals.py            seed, run, report, judge, score, run folder, Langfuse experiment
utils.py                   paths, sheet and CSV readers, parser and model helpers
google_utils.py            Google Sheets read with a service account
plot_coverage.py           ingested-denominator coverage per briefing -> html and png in the run folder (--run <folder>)
prompts/extract_references_v1.txt   reference list
prompts/extract_key_points_v1.txt   key points with reference labels
prompts/decompose_facts_v1.txt      key points -> atomic facts (no briefing)
prompts/judge_v1.txt                one fact vs report -> verdict
tests/test_synthesis.py    offline self-checks (part of `make eval-check`)
inputs/briefings/<slug>.*  hand-downloaded briefings (S3)
ground_truth/<slug>/       references.csv, key_facts.csv, corpus_resolution.csv (human-checked, S3)
datasets/<slug>/refs/      resolved reference text cache (S3)
results/runs/<date>-<depth>-<label>/<slug>/   report.md, facts.csv, corpus.csv, eval_results.json (gitignored, S3)
```

The script numbers are the steps a person takes, in order.

## Quickstart

Run all commands from the repo root. The OpenAI and Langfuse keys come from `backend/.env`. The Google service-account key that the sheet is shared with lives at `infra/.credentials/afsmumsnet-454163761a82.json` (gitignored); set `GOOGLE_SHEETS_CREDENTIALS` in `backend/.env` only to point somewhere else. The database is the local dev one.

To download the reference data and the extracted key facts and references for each one:
```sh
# Once per checkout: fetch the briefings, ground truth and caches.
uv run --project backend python scripts/evals/sync_s3.py synthesis download
```

To add a new briefing to the dataset:

1. Add details in the Google Sheet and add the pdf/html to the s3 bucket at `eval/datasets/synthesis/inputs/briefings/`

2. Run `uv run --project backend python scripts/evals/post_screening_and_synthesis/00_update_ground_truth.py`. This will extract the references and key facts for the new briefing.

3. Check the LLM outputs (key facts; references)

4. Push the ground truth to S3 and the key facts to Langfuse: `uv run --project backend --env-file backend/.env \
    python scripts/evals/post_screening_and_synthesis/01_upload_to_langfuse.py --upload`

To run the evals (one by one for each briefing - in the example, we just specify `airports_health_impacts`. List all of them in the command to run the evals for all 15):
```
uv run --project backend --env-file backend/.env \
    python scripts/evals/post_screening_and_synthesis/02_run_evals.py \
    --docs airports_health_impacts --depth deep --run-label mini
```

Rapid responses cite by hyperlink and have no reference list. For an `.html` briefing the extract step marks each external link `[n]` in the text and appends a generated list, so those references have the link text as title and no authors or year.

## Outputs

Per briefing, the run folder holds `report.md`, `facts.csv` (one row per fact with its point id, verdict, supporting quote and rationale), `corpus.csv` (one row per ingested reference with text basis and stage-2 status) and `eval_results.json` (task, scope and capability-run ids, the Langfuse session id, git commit, judge model and prompt hash, token totals, and the scores).

The judge's cost is recorded as `judge_llm_cost_usd_computed`: computed from the price table in `../screening/metrics.py`, not spent. The pipeline's own spend is read from Langfuse by session id (see `docs/knowledge/eval-cost-figures-name-their-unit.md`).

When the Langfuse keys are set, the eval's own calls are traced too. Each judge call is a generation named `eval.synthesis.judge` in the same session as the briefing's pipeline walk; the three extract calls are generations named `eval.synthesis.extract_references`, `eval.synthesis.extract_key_points` and `eval.synthesis.decompose_facts`. All carry `experiment: synthesis-coverage` and the prompt version in their metadata, so they are filterable alongside the pipeline's traces and separate from user sessions, which carry a user id and no `experiment` key. `--no-langfuse` turns all of it off.

Task rows are kept in the database so a report can be opened in the app by task id.

## Limits

- The judge is a model. Spot-check its verdicts against `report.md` before trusting a number.
- Coverage is a mean over facts, so a key point split into five facts weighs five times one split into one. `point_id` in `facts.csv` lets you regroup by point.
- The judge runs once per fact, so its cost scales with how finely the extractor splits the points.
- A dropped reference lowers `coverage_all` but not `coverage_ingested`. Compare both.
- Resolution runs once and is cached by reference label. A changed `references.csv` row needs its cache file under `datasets/<slug>/refs/` deleted.
- Two references with the same URL become two sources. Mark one `keep=n`.
