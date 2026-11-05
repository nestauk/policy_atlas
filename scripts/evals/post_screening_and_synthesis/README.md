# Post-screening synthesis coverage eval

These scripts measure the stages **after screening**: classify, appraise, screen_full, characterise, select, extract, group and synthesise. The question is: given a published POST or CAPE briefing's own reference list as the corpus, does the Policy Atlas report capture the briefing's key facts?

The search and screening evals (`../search`, `../screening`) cover the earlier stages. This one starts where they stop, so search is bypassed and stage-1 screening is pre-filled.

---

## What is being measured

One item is one published briefing from `inputs/POST_test_set.csv` (19 briefings: 4 CAPE rapid evidence assessments, 6 POSTbriefs, 5 POSTnotes, 4 POST rapid responses). For each briefing:

1. **Ground truth.** A model extracts the briefing's reference list and 15 to 40 key facts, each fact tied to the references it cites. A human checks both lists and marks rows to keep.
2. **Corpus.** Each kept reference is resolved to text: OpenAlex by DOI or strict title match, then the production URL cascade, fetcher and parser. A reference with no full text but an OpenAlex abstract enters as `abstract_only`. One with neither is dropped and recorded.
3. **Run.** A task is seeded with an approved plan at the chosen analysis depth, the corpus is ingested as uploads, and every source gets a stage-1 `relevant` screen row. The plan walk then runs with no search backends, so acquire adds nothing and the walk's own stage-1 screen has nothing to do. `screen_full` (standard and deep) runs as in production; its demotions are recorded.
4. **Judge.** The report's markdown (citation markers stripped) is graded against each key fact by a model, one call per fact. Verdicts: `fully_represented`, `partially_represented`, `not_represented`, `misrepresented`, `uncertain`.

**Coverage** is the share of key facts judged `fully_represented`. It is reported with two denominators: all checked facts (`coverage_all`), and only facts with at least one reference that made it into the corpus (`coverage_ingested`). The gap between them is the cost of unfetchable sources, not of the pipeline.

The eval-side model for extraction and judging is `gpt-5.6-luna`. The pipeline runs with its production backends and models.

## Files

```
utils.py                   paths, CSV readers, parser and model helpers
ground_truth.py            extract | resolve
run_synthesis.py           seed, run, report, judge, score, run folder, Langfuse
upload.py                  key facts -> Langfuse dataset `synthesis-coverage` (dry run by default)
prompts/extract_v1.txt     references + key facts
prompts/judge_v1.txt       one fact vs report -> verdict
tests/test_synthesis.py    offline self-checks (part of `make eval-check`)
inputs/POST_test_set.csv   the 19 briefings (S3)
inputs/briefings/<id>.*    hand-downloaded briefings (S3)
ground_truth/<id>/         references.csv, key_facts.csv, corpus_resolution.csv (human-checked, S3)
datasets/<id>/refs/        resolved reference text cache (S3)
results/runs/<date>-<depth>-<label>/<id>/   report.md, facts.csv, corpus.csv, eval_results.json (gitignored, S3)
```

## Commands

All from the repo root. Keys come from `backend/.env`; the database is the local dev one.

No CSV is in git (the repo-wide `*.csv` rule), so a fresh checkout starts with `sync_s3.py synthesis download`, and edited ground truth is kept with `upload-datasets`.

```sh
# 0. Fetch the test set, briefings, ground truth and caches.
uv run --project backend python scripts/evals/sync_s3.py synthesis download

# 1. Download the briefing by hand into inputs/briefings/<Doc ID>.pdf (or .html for a
#    rapid response: save the page). parliament.uk blocks scripted fetches.

# 2. Extract references and key facts, then check the `keep` column by hand.
uv run --project backend --env-file backend/.env \
    python scripts/evals/post_screening_and_synthesis/ground_truth.py extract --docs 16 5

# 3. Resolve each kept reference to text (cached; a rerun is network-free).
uv run --project backend --env-file backend/.env \
    python scripts/evals/post_screening_and_synthesis/ground_truth.py resolve --docs 16 5

# 4. Push the key facts to Langfuse (dry run without --upload).
uv run --project backend --env-file backend/.env \
    python scripts/evals/post_screening_and_synthesis/upload.py --upload

# 5. Run. Without --no-langfuse the run is a Langfuse experiment on the dataset.
uv run --project backend --env-file backend/.env \
    python scripts/evals/post_screening_and_synthesis/run_synthesis.py \
    --docs 16 --depth deep --run-label mini

# 6. Keep the files.
uv run --project backend python scripts/evals/sync_s3.py synthesis upload-datasets
uv run --project backend python scripts/evals/sync_s3.py synthesis upload results/runs/<folder>
```

`extract` refuses to overwrite ground truth without `--force`, so human edits survive. If a reference was dropped because the briefing gives no DOI and the URL is paywalled, add the DOI to `references.csv` and rerun `resolve`.

Rapid responses cite by hyperlink and have no reference list. For an `.html` briefing the extract step marks each external link `[n]` in the text and appends a generated list, so those references have the link text as title and no authors or year.

## Outputs

Per briefing, the run folder holds `report.md`, `facts.csv` (one row per fact with verdict, supporting quote and rationale), `corpus.csv` (one row per ingested reference with text basis and stage-2 status) and `eval_results.json` (task, scope and capability-run ids, the Langfuse session id, git commit, judge model and prompt hash, token totals, and the scores).

The judge's cost is recorded as `judge_llm_cost_usd_computed`: computed from the price table in `../screening/metrics.py`, not spent. The pipeline's own spend is read from Langfuse by session id (see `docs/knowledge/eval-cost-figures-name-their-unit.md`).

When the Langfuse keys are set, the eval's own calls are traced too. Each judge call is a generation named `eval.synthesis.judge` in the same session as the briefing's pipeline walk; each extract call is a generation named `eval.synthesis.extract`. Both carry `experiment: synthesis-coverage` and the prompt version in their metadata, so they are filterable alongside the pipeline's traces and separate from user sessions, which carry a user id and no `experiment` key. `--no-langfuse` turns all of it off.

Task rows are kept in the database so a report can be opened in the app by task id.

## Limits

- The judge is a model. Spot-check its verdicts against `report.md` before trusting a number.
- A dropped reference lowers `coverage_all` but not `coverage_ingested`. Compare both.
- Resolution runs once and is cached by reference label. A changed `references.csv` row needs its cache file under `datasets/<id>/refs/` deleted.
- Two references with the same URL become two sources. Mark one `keep=n`.
