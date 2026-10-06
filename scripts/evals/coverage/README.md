# Evaluating the evidence report: coverage and prominence

This folder measures two things about a generated evidence report, using a published
systematic review on the same question as the answer key:

- **Coverage**: are the findings the review reports represented in the report at all?
- **Prominence**: are the findings a human marked as "must be in the summary" represented
  in the report's **Key findings** section?

A human first approves a list of expected findings taken from the review. A large language
model (LLM) judge then reads each saved report and labels how each expected finding is
represented. Plain code turns the labels into rates. The judge never fact-checks the report
and never looks for findings that are not on the list.

This is separate from the grounding judge that runs inside the pipeline. Nothing here calls
or changes it, and validating this evaluator says nothing about that one.

## The files

| Path | What it is | Who writes it |
|---|---|---|
| `cli.py` | The five commands (below). | Script |
| `coverage_lib.py` | The logic with no network or database: file shapes, gates, parsing, scoring, comparison. | Script |
| `judges/draft_reference.md` | Prompt that drafts findings from a review. Front matter sets `version` and the model. | Edited by pull request |
| `judges/align_findings.md` | The one alignment prompt the judge uses. Same front matter. | Edited by pull request |
| `cases/<case_id>/review.md` | Verified text of the review, with `[P12]` passage ids and `<!-- page 3 -->` markers. Keep the original PDF next to it. | You |
| `cases/<case_id>/reference.json` | The expected findings and the approval record. | Drafted by script, finished and approved by you |
| `cases/<case_id>/runs/<run_id>.json` | A saved report with its Key findings boundaries ("run package"). | `export` |
| `cases/<case_id>/annotations/*.csv` | Your labels, for checking the judge. | You |
| `cases/example_synthetic/` | A made-up review, reference, two reports, labels and a pre-filled judge cache. Everything in it is invented. | Committed |
| `results/<label>/` | Generated: `judgements.{json,csv}`, `scores.{json,csv}`, `summary.md`, `calls.jsonl`, `comparison.*`. Not committed. | `evaluate`, `compare` |
| `results/cache/` | Validated judge replies, keyed by a hash of the whole request. Not committed. | `evaluate` |

Real cases are not committed (review text is copyrighted). Only the synthetic example is.

Every command is run from the repository root:

```
uv run --project backend --env-file backend/.env python scripts/evals/coverage/cli.py <command> ...
```

Drop `--env-file` for anything that needs no keys (`approve`, `export --report-file`,
`evaluate --dry-run`, `evaluate --offline`, `compare`).

## The workflow

```
review.md + query ──> draft-reference ──> reference.json (status: draft)
                                              │
            you verify, add what the draft missed, merge duplicates,
            set priority and expected_in_key_findings on every finding
                                              │
                                              v
                                          approve ──> reference.json (approved, hashed)

runs.csv (case_id, task_id) ──> export ──> cases/<case>/runs/<run>.json

reference.json + runs ──> evaluate ──> results/<label>/judgements, scores, summary.md

judgements.json + your labels ──> compare ──> results/<label>/comparison.md
```

### Step 1: draft the reference

Put the verified review text in `cases/<case_id>/review.md`. Then:

```
... cli.py draft-reference --case scripts/evals/coverage/cases/<case_id> --query "<the research question>" --citation "<how to cite the review>"
```

The drafter sees only the review and the question, never a generated report. The result has
`approval.status: draft` and leaves `priority` and `expected_in_key_findings` empty on
purpose. The script is a starting point: you must also look for findings the draft missed.

### Step 2: finish and approve the reference

Edit `reference.json` by hand. For each finding set:

- `priority`: `essential` if leaving it out would materially impair the answer, otherwise
  `supporting`. Give the reason in `priority_rationale`.
- `expected_in_key_findings`: `true` only for the findings that must appear in the short
  Key findings section. This is a different question from priority. Give the reason.
- `necessary_qualifications`: the conditions a report must keep (population, comparison,
  timeframe, certainty) for the finding to stay true.
- `sources`: passage ids and exact excerpts from `review.md`.

Also fill in `evidence_cutoff`: the date of the last search whose results the review actually
used, not the publication date and not a top-up search that was not incorporated. Record
where the date comes from and how precise it is. Put anything you deliberately left out under
`exclusions` with a reason. Set `reference_version` (for example `v1`). Then:

```
... cli.py approve --case scripts/evals/coverage/cases/<case_id> --reviewer "Your name"
```

`approve` refuses duplicate ids, unfilled fields and excerpts that are not in `review.md`. On
success it stamps your name, the date and a content hash. From then on every other command
refuses the file if it is not approved or if anything outside the approval block has changed.
To correct a finding, change `reference_version`, approve again, and re-score every run.

### Step 3: export the reports

Run the questions through the pipeline with `scripts/evals/report/run_queries.py` (see that
folder's README). Then write a CSV with columns `case_id,task_id` (optional: `run_id`,
`depth`, `condition`) and:

```
... cli.py export --runs my_runs.csv
```

Each report is read from the local database, rendered to markdown and saved with the exact
character positions of its Key findings section. The section is marked:

- `present` when the database says the section exists and exactly one `## Key findings`
  heading is found;
- `absent` when the database says no section was produced and no heading is found;
- `unresolved` otherwise, with the reason. An unresolved section is never scored as absent.

A markdown report from somewhere else can be imported with
`export --report-file report.md --case-id <case_id> --run-id <run_id>`. With no database to
confirm, a missing heading is `unresolved` unless you pass `--no-key-findings`.

The pipeline cannot yet filter searches by date or exclude the reference review, so the run
package records both controls as `unknown` unless you pass `--date-filter` and
`--reference-review-excluded`. The evaluator never gives the approved findings to the
pipeline.

### Step 4: evaluate

```
... cli.py evaluate --dry-run              # prints the compiled prompt; calls nothing
... cli.py evaluate --label first-try      # runs the judge
```

For every run the judge returns one `full_report` judgement per finding and one
`key_findings` judgement per finding marked `expected_in_key_findings`. When the Key findings
section is absent, code assigns `absent` to those pairs without asking the judge. When it is
unresolved, the prominence rate is `null` and the reason is shown.

Before any score is issued, code checks the reply: exactly the expected pairs, no duplicates,
allowed labels, no quote on an `absent` label, at least one quote on `adequate`, `partial`
and `misrepresented`, and every quote found verbatim in the right text (the whole report, or
only the Key findings slice). Quotes are matched after a documented normalisation
(Unicode NFC, then the repository's `qv_v1` matcher: straight and curly quotes, dash
variants, non-breaking spaces, soft hyphens, whitespace runs and letter case). That never
changes a word, number or negation. A quote must be at least 25 characters. A bad reply is
retried once with the problems listed; a second bad reply makes that run a **failed run**,
listed in the summary with no scores. A reply cut off by the token limit is also an error.

Validated replies are cached under `results/cache/` by a hash of the full request (prompt
text, report, section boundaries, findings, model settings and the reply schema). Any change
to any of those misses the cache. `--offline` uses the cache only. `calls.jsonl` records
tokens, latency, cache hits and failures per call. If Langfuse keys are set, each call is also
traced as a generation named `judge:coverage_alignment`.

If a report plus all findings would exceed `--max-input-chars` (default 600,000), the run
fails with a clear message. Use `--findings-per-call N` to send the findings in batches; the
full report goes with every batch. Nothing is ever truncated.

### Reading the scores

Labels (the same ones you use when annotating):

| Label | Meaning |
|---|---|
| `adequate` | The finding's meaning and all material qualifications are represented in that section. Different wording, or several findings in one sentence, is fine. |
| `partial` | Some substantive content is there but detail is missing. What is there does not change the finding's meaning. |
| `absent` | Not substantively represented. A citation or a mention of the topic is not enough. |
| `misrepresented` | Related text materially changes the finding: direction, population, comparison, magnitude, timeframe, or certainty. |
| `uncertain` | The text or the finding is too ambiguous to choose a defensible label. |

Rates, with F = all findings, E = the essential ones, K = those marked for Key findings:

| Rate | Numerator | Denominator |
|---|---|---|
| `full_report_coverage` | findings labelled `adequate` for the full report | F |
| `essential_full_report_coverage` | essential findings labelled `adequate` for the full report | E |
| `key_findings_coverage` | K findings labelled `adequate` in Key findings | K |

Only `adequate` counts. `partial` and `uncertain` stay in the denominator and earn nothing.
A zero denominator gives `null` with a reason, never 100%. Every rate comes with its
numerator, denominator, label counts and the finding ids behind each label.

Also reported per run: `essential_absent_ids` (essential findings absent from the whole
report), `prominence_gap_ids` (findings in K that are adequate in the full report but
partial, absent or misrepresented in Key findings) and `unresolved` (any `uncertain` label,
listed so uncertainty is never described as a demonstrated omission).

`key_findings_coverage` is a proxy for prominence: it says whether the predesignated findings
made it into the summary. It says nothing about ranking, conciseness, or whether the
summary's other bullets deserve to be there.

`summary.md` shows per run, per case (mean over that case's runs) and per group (cases
weighted equally). A group is one reference version under one control condition; groups are
never averaged together. Failed runs and nulls are shown, not hidden. These rates are not
converted to the 1 to 5 human scales and not combined into one quality score.

### Step 5: check the judge against your own labels

Label some runs yourself in a CSV with columns
`case_id,run_id,reference_version,finding_id,section,label,report_quote,explanation,annotator,status`
(`status` is `final`; use `adjudicated` with `annotator` = `adjudication` for an agreed label
after two annotators disagree, in the same or another file; original rows are never changed).
Then:

```
... cli.py compare --judgements scripts/evals/coverage/results/<label>/judgements.json --annotations my_labels.csv [adjudicated.csv]
```

Separately for `full_report` and `key_findings` you get a confusion matrix, agreement, and
per-label precision and recall, plus detection rates for essential omissions and prominence
gaps with the missed cases and false alarms listed. Rows with a mismatched reference version,
duplicates, unadjudicated disagreements and pairs missing on either side are flagged, not
dropped. `uncertain` is its own label in the matrices; in the detection counts it means "not
flagged", and the abstention counts say how often each side abstained. Rows assigned by rule
(Key findings section absent) are skipped because they are not judge output.

Findings from one review are related, so do not read the per-label numbers as if each finding
were an independent test. The mocked tests in `backend/tests/scripts/test_coverage_eval.py`
prove the plumbing; only this comparison, on enough real cases, says anything about the
judge. Hold some reviews back if you tune the prompt.

## The synthetic example

`cases/example_synthetic/` is entirely invented: a fake review about breakfast clubs in a
country that does not exist, a reference approved by "synthetic example (not a real
reviewer)", two reports (one with a Key findings section that drops a qualification and omits
a limitation, one with no Key findings section, a misrepresented headline and two absent
findings), a human label file, and a judge cache holding **hand-written replies, not model
output**. It runs without any keys:

```
uv run --project backend python scripts/evals/coverage/cli.py evaluate --cache-dir scripts/evals/coverage/cases/example_synthetic/cache --offline --label example
uv run --project backend python scripts/evals/coverage/cli.py compare --judgements scripts/evals/coverage/results/example/judgements.json --annotations scripts/evals/coverage/cases/example_synthetic/annotations/human.csv
```

Editing `judges/align_findings.md` changes the cache keys, so the shipped cache stops matching.
Delete `cases/example_synthetic/cache/` and run `evaluate` with keys to see real model output
on the example.

## Changing the judge

1. Edit `judges/align_findings.md` in a branch and bump `version` in its front matter. The
   block between the `---` lines sets `model`, `reasoning_effort` and
   `max_completion_tokens`; the rest is the prompt. Keep the `{{query}}`, `{{findings}}`,
   `{{report}}`, `{{key_findings}}` and `{{required_pairs}}` placeholders.
2. Open a pull request so the change is reviewed as a diff.
3. Re-run `evaluate` (old cache entries are simply not matched) and `compare`.

## Limitations and deferred work

Out of scope here: general factual accuracy of the report; calibrating the pipeline's
grounding judge; judging whether the report's extra key findings deserve inclusion or their
order; synthesis-only experiments; checking primary papers; and diagnosing whether a gap came
from retrieval, screening or synthesis (a missing finding counts as an output shortfall
whatever the cause). The pipeline has no date filter or reference-review exclusion yet, so
historical reconstruction is approximate and both controls are recorded as `unknown`.
Pushing the prompt to Langfuse prompt management and uploading judgements as a Langfuse
dataset are deferred; the prompt version in the file is recorded in every output.

## Glossary

- **LLM**: large language model, the kind of model that writes the report and acts as judge.
- **LLM-as-a-judge**: asking a model to label another model's output against a written rubric.
- **Reference**: the human-approved list of expected findings for one review (the answer key).
- **Run package**: one saved report plus the positions of its Key findings section.
- **Pair**: one finding and one section (`full_report` or `key_findings`) the judge labels.
- **Prominence gap**: a finding the report contains but leaves out of its Key findings.
- **Content hash**: a fingerprint of the reference file; if it changes, the approval no longer applies.
- **NFC**: a standard way of writing accented characters so two spellings of the same letter compare equal.
- **Langfuse**: the tracing tool the app sends model calls to; works offline when no keys are set.
