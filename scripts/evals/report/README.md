# Evaluating the evidence report: answer relevance

This folder holds the first evaluation of the final evidence report. It measures one
criterion, **answer relevance** (does the report answer the research question it was
given?), on a 1 to 5 scale. A human scores a set of reports first. Then a large
language model (LLM) is asked to score the same reports with the same scale, and we
measure how closely it agrees with the human. Once it agrees well enough, the LLM
judge can score many more reports than a person could, which is what makes capability
evals (hard questions, where we expect low scores) and later regression evals (questions
that pass today, where a drop means something broke) affordable.

Everything is recorded in Langfuse, the tracing tool the app already sends its model
calls to, so each judge run can be compared with every earlier run.

## The files

| File | What it is | Who writes it |
|---|---|---|
| `input/questions.csv` | The research questions to run. Columns `question` and `depth` (`rapid`, `standard` or `deep`). | You |
| `input/answer_relevance.csv` | Your scores. Columns `task_id`, `answer_relevance` (1 to 5), `comment` (what, if anything, is wrong). | You |
| `judges/answer_relevance.md` | The judge prompt. The scale anchors in it are the ones you score by. Its git history is its version history. | Edited by pull request |
| `run_queries.py` | Runs every question through the pipeline unattended and records the task ids. | Script |
| `build_dataset.py` | Reads each report from the database, renders it to markdown, joins it with your scores and uploads a Langfuse dataset. | Script |
| `calibrate.py` | Runs the judge over the dataset as a Langfuse experiment and reports agreement with your scores. | Script |
| `test_metrics.py` | A self-check for the pieces that need no network: run it after changing any script. | Script |
| `results/` | Generated: `runs.csv`, `reports/<task_id>.md`, `items.json`. Not committed. | Scripts |

How the data flows:

```
input/questions.csv ──> run_queries.py ──> pipeline runs in the local database
                                             + results/runs.csv (task ids)
                                                      │
          you read results/reports/*.md and fill in input/answer_relevance.csv
                                                      │
                                                      v
                       build_dataset.py ──> Langfuse dataset evidence-report-answer-relevance
                                                      │
                       judges/answer_relevance.md ──> calibrate.py ──> Langfuse experiment run
                                                                        (judge score, your score,
                                                                         agreement per report and overall)
```

## Prerequisites

- `backend/.env` with the live keys: `OPENAI_API_KEY`, `OPENALEX_API_KEY`, `OPENALEX_EMAIL`,
  `OVERTON_API_KEY`, and the three Langfuse keys (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`,
  `LANGFUSE_HOST`).
- `DATABASE_URL` in that file pointing at your **local** Docker Postgres. The runs write real
  rows. Never point this at production.

Every command below is run from the repository root.

## Step 1: run the questions

Fill in `input/questions.csv`. Twenty to thirty questions is a good first batch; mix depths
and kinds of question. Then:

```
uv run --project backend --env-file backend/.env python scripts/evals/report/run_queries.py --limit 1
```

Check the one run worked (the last line shows `artefact=True`), then run the rest without
`--limit`. Each question is a full live pipeline run and costs what a user's run costs. A
`standard` run takes roughly forty minutes.

The script answers the planner's questions itself ("use your best judgement") and approves the
plan. If the planner refuses to settle on a plan, the row is recorded with a `no_run` status
and skipped.

`results/runs.csv` gets one line per question with the `task_id`. The `conversation_id` column
is the Langfuse session id, so you can find every trace of that run in Langfuse under
Sessions.

## Step 2: score the reports

Render the reports to files (this also works before you have any scores):

```
uv run --project backend --env-file backend/.env python scripts/evals/report/build_dataset.py --dry-run
```

Read each `results/reports/<task_id>.md` and add a line to `input/answer_relevance.csv`
with the task id, your 1 to 5 score and a comment. The scale is in
`judges/answer_relevance.md`; score by those anchors, because the judge will.

The `comment` column is the start of error analysis. Write what is wrong, not why you
think it happened.

## Step 3: upload the dataset

```
uv run --project backend --env-file backend/.env python scripts/evals/report/build_dataset.py --dry-run
uv run --project backend --env-file backend/.env python scripts/evals/report/build_dataset.py
```

The dry run writes `results/items.json` so you can see what will be uploaded. The live run
creates (or updates) the Langfuse dataset `evidence-report-answer-relevance`, one item per
scored report. Running it again after adding scores updates the items in place.

## Step 4: run the judge

First time, or after any change to `judges/answer_relevance.md`:

```
uv run --project backend --env-file backend/.env python scripts/evals/report/calibrate.py --push-prompt
```

`--push-prompt` copies the prompt file into Langfuse prompt management as a new version. The
file in the repository is the source of truth; the Langfuse copy exists so that every judge call
in Langfuse links to the exact prompt text that produced it. Without `--push-prompt`, the script
refuses to run when the file and the Langfuse copy differ, so a run never uses stale text.

After that, plain runs:

```
uv run --project backend --env-file backend/.env python scripts/evals/report/calibrate.py
uv run --project backend --env-file backend/.env python scripts/evals/report/calibrate.py --repeat 2
```

The script prints one line per report (your score, the judge's score, the start of its
reasoning) and a summary line, then the link to the run in Langfuse. In Langfuse, the
Experiments page for the dataset shows every run side by side.

`--dry-run` prints the fully compiled prompt for the first report and calls nothing. Use it to
read what the judge actually sees.

## Reading the numbers

Per report, and averaged over the run:

- `exact_match`: the judge gave your score.
- `within_one`: the judge was within one point of your score.
- `abs_error`: how far off it was.
- `mean_judge_minus_human`: above zero means the judge is more generous than you, below means
  harsher.
- `spearman`: rank correlation, from -1 to 1. It asks whether the judge orders the reports the
  way you do, even if its absolute numbers differ. Close to 1 is good.

`--repeat 2` runs the judge twice and prints how often it agrees with itself. This is the noise
floor. A judge cannot agree with you more reliably than it agrees with itself, so read the
human agreement against it.

What counts as "good enough" is your decision. A sensible first bar: `within_one` at least as
high as a second human rater would reach on the same reports.

## Changing the judge

1. Edit `judges/answer_relevance.md` in a branch. The block between the `---` lines sets the
   model (and `temperature`, if the model accepts one). The rest is the prompt. Keep the
   `{{question}}` and `{{report}}` placeholders.
2. Open a pull request so the change is reviewed as a diff.
3. Run `calibrate.py --push-prompt`. The run name carries the new Langfuse version number, so
   the Experiments page shows old and new side by side.

Tune on half the reports and keep the other half for the final figure once you have enough,
otherwise the judge is being graded on the examples it was tuned on.

## Glossary

- **LLM**: large language model, the kind of model that writes the report and acts as the judge.
- **LLM-as-a-judge**: asking a model to grade another model's output against a written rubric.
- **Langfuse**: the tracing and evaluation tool the app reports to. A *dataset* is a fixed set of
  inputs and expected outputs; an *experiment run* is one pass of some code over that dataset
  with scores attached; *prompt management* is Langfuse's versioned store of prompt text.
- **Task id**: the id of one evidence task (one question, one report) in the app's database.
- **Spearman correlation**: a measure of whether two sets of scores rank items in the same
  order, from -1 (opposite order) to 1 (same order).
- **Noise floor**: how much a judge disagrees with itself when run twice on identical input.
