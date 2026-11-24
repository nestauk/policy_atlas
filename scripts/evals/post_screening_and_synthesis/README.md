# Post-screening and synthesis evaluation

## Overview

These scripts measure the evidence search stages **after search & screening**: classify, appraise, screen_full, characterise, select, extract, group and synthesise.

The grounding judge in the production pipeline provides a measure of whether every claim in the report is justified. This eval goes in the opposite direction: given a set of facts that comprise the essential information that a policymaker would need in order to understand a policy question, is each and every one of these facts represented in the Policy Atlas report? This complements the separate [search](../search) and [screening](../screening) evaluations.

The approach is based on the method of checking summary completeness via atomic facts of [FineSurE](https://aclanthology.org/2024.acl-long.51/) and [factscore](https://aclanthology.org/2023.emnlp-main.741/).

## Ground truth dataset

We use as our ground truth a set of 15 [POST briefings](https://post.parliament.uk/type/postbrief/) covering various policy domains. Our assumption is that each of these briefing covers the most important and up-to-date information on a given policy topic, and that this information is summarised in a way that makes it digestible and presents the most important information to a policy audience.

### Dataset details

* Number of briefings: 15

* Editable ground truth metadata stored in Google Sheets [here](https://docs.google.com/spreadsheets/d/1ysmdUcOXGLjtse5KgsGlYIpdpQ8vwf1YSOToevAAhns/edit?gid=1489018505#gid=1489018505) This file includes a research question that the briefing could plausibly answer, and that can be used as the input to a Policy Atlas search.

* Source briefing files: `eval/datasets/synthesis/inputs/briefings/` (S3)

* Langfuse dataset: `synthesis-coverage`

## Methodology

The experiment comprises four steps.

**1. Ground truth generation**

For each briefing, an LLM:

* Extracts its reference list.

* Identifies the briefing's key points and their supporting references.

* Decomposes these points into individual, self-contained facts.

The extracted references and facts are manually reviewed before inclusion in the evaluation.

The extraction prompts can be found in `scripts/evals/post_screening_and_synthesis/prompts/`

**2. Corpus construction**

The cited references are retrieved using OpenAlex and the production document-fetching pipeline.

Full-text documents are preferred, with abstracts used where full text is unavailable. References that cannot be retrieved are recorded and excluded from the ingested corpus.

**3. Pipeline execution**

Policy Atlas runs using the briefing's research question and the constructed corpus.

Search and initial screening are bypassed, allowing the evaluation to isolate the downstream stages, including full-text screening, extraction and synthesis.

**4. Evaluation**

An LLM judge compares the generated Policy Atlas report against each ground-truth fact, assigning one of five verdicts: fully_represented / partially_represented / not_represented / misrepresented / uncertain

TODO: dig into how well this judge is doing!

The judge prompt can be found at `scripts/evals/post_screening_and_synthesis/prompts/judge_v1.txt`

## Evaluation metrics

The primary metric is **fact coverage**: the proportion of ground-truth atomic facts represented in the generated Policy Atlas evidence report.

| Metric | Description |
|---|---|
| `coverage_all` | Proportion of all ground-truth facts fully represented. "All" = regardless of whether or not the sources for these facts could be obtained; it's therefore not guaranteed that the PA pipeline actually had access to the information needed to reproduce these facts. |
| `coverage_ingested` | Proportion of facts fully represented, restricted to facts supported by at least one ingested reference i.e. facts that the PA pipeline had access to. |
| `coverage_all_lenient` | As `coverage_all`, also counting partially represented facts |
| `coverage_ingested_lenient` | As `coverage_ingested`, also counting partially represented facts |

The ingested-denominator metrics help distinguish failures of evidence synthesis from failures to retrieve source material.

## Running the experiment

All commands should be run from the repository root.

### Prerequisites

- Python dependencies installed via `uv`
- OpenAI and Langfuse credentials in `backend/.env`
- Google Sheets service-account credentials
- Access to the evaluation S3 bucket
- Local development database

### 1. Download the dataset

```bash
uv run --project backend python scripts/evals/sync_s3.py synthesis download
```

### 2. Update ground truth

After adding any new briefings to the Google Sheet and S3, run:

```bash
uv run --project backend python scripts/evals/post_screening_and_synthesis/00_update_ground_truth.py
```

Manually review the generated references and key facts, then upload the approved data:

```bash
uv run --project backend --env-file backend/.env \
  python scripts/evals/post_screening_and_synthesis/01_upload_to_langfuse.py --upload
```

### 3. Run the evaluation

```bash
uv run --project backend --env-file backend/.env \
  python scripts/evals/post_screening_and_synthesis/02_run_evals.py \
  --docs airports_health_impacts \
  --depth deep \
  --run-label example
```

Replace `airports_health_impacts` with the desired briefing ID.

[TODO: Document standard experiment configuration, including analysis depth, model versions and which briefings to include.]

### 4. Visualise results

```bash
uv run --project backend python \
  scripts/evals/post_screening_and_synthesis/plot_coverage.py \
  --run <run-directory>
```

This produces coverage visualisations for the specified evaluation run.

## Outputs

Results are saved under:

`results/runs/<run-id>/<briefing-id>/`

| File | Contents |
|---|---|
| `report.md` | Generated Policy Atlas report |
| `facts.csv` | Ground-truth facts, judge verdicts and explanations |
| `corpus.csv` | Ingested references and processing status |
| `eval_results.json` | Coverage scores, run metadata and costs |

Evaluation runs and model calls are also tracked in Langfuse.

## TODOs

* Move the judge LLM calls from OpenAI to Bedrock and use a different model family, e.g. an Anthropic model, llama etc

* Detailed error analysis - which facts were not captured by the Policy Atlas synthesis?

* Inspect the performance of the LLM judge. Is it consistently labelling fully represented vs. partially represented etc?