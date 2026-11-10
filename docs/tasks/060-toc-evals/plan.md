# Task 060: theory of change evaluations (programme plan)

**Status:** draft for the owner, 2026-11-09. R&D task: it skips the task cycle and keeps light
notes here. No product code changes during the experiments; bugs found are noted, not fixed.

**Goal.** A clean, varied ground-truth dataset of at least 20 published theories of change (ToCs), a
fixed way to score the app against it, and a first set of experiments (baseline, models,
evidence-search depth) run on it.

**Why a fresh start.** The old pack (`scripts/evals/theory_of_change/archive_v1/`) has 4
theories (6 maps), all UK, 3 of them from one programme (Changing Futures). It was right for
building the capability. It is too small and too narrow to tell a real change from noise.

## Folder layout

```
scripts/evals/theory_of_change/
  archive_v1/          the old pack, scripts and run outputs, kept for reuse (not maintained)
  candidates/          the wide-net longlist and the triage scores
  cases/<case_id>/     one folder per accepted ToC: source.md (citation, URLs, licence),
                       case.json (the extracted record, schema below), notes.md
  schema.py            the case record schema (Pydantic), and its check
  ...                  run and score scripts, added in step 6 (reused from archive_v1/gt_eval.py)
docs/tasks/060-toc-evals/
  plan.md              this file
  research/            sourced research notes from the wide-net search (git-ignored by the
                       2026-10-14 ruling; what matters is merged into candidates/longlist.csv)
  notes.md             decisions and results as we go
```

No PDF or image is committed (as in v1). `source.md` gives the URL and page; a local cache of
downloads stays git-ignored.

## Step 1. Collect a longlist (wide net)

Sources, searched in parallel:

- UK government and What Works Centres (`research/candidates_uk.md`)
- International development and theory-based systematic reviews (3ie, Campbell)
  (`research/candidates_intl.md`)
- Other governments, international bodies, charities and foundations
  (`research/candidates_other.md`)
- Overton (policy documents) and OpenAlex (papers) (`research/candidates_overton_openalex.md`)
- Existing ToC datasets, LLM-and-ToC research and ToC quality rubrics
  (`research/existing_datasets.md`)

Target: 70–100 candidates, merged and deduplicated into `candidates/longlist.csv`.

## Step 2. Criteria

### 2a. Quality criteria (each ToC must pass)

A ToC enters the dataset only if every **must** holds.

| # | Criterion | Must / score |
|---|---|---|
| Q1 | **A diagram we can read**: boxes in an order that maps to the Magenta Book layers (inputs, outputs, outcomes, impact), with arrows. Columns-only diagrams pass, but are scored at layer level only. | must |
| Q2 | **Public and citable**: a stable URL, a named publisher, a date. A licence that allows a factual transcription (Open Government Licence, CC BY, or no licence with a short cited transcription, as in v1). | must |
| Q3 | **A real intervention**: a programme, policy, regulation, fund or service with a population and a place. Not a generic template or a teaching example. | must |
| Q4 | **Size**: record the box count; no fixed limits yet. We set a range after we see the spread in the longlist. Two reasons a range may be needed: (1) with very few boxes, one missed box moves recall a lot, so the scores are noisy; (2) the app draws about 11–19 boxes (v1 runs), so a 60-box map caps recall by size alone, unless we split it into levels (as for Changing Futures). Either way, we report metrics by size band. | score |
| Q5 | **Evidence fidelity**: A = a verdict on the evidence for individual links or assumptions; B = assumptions, risks or narrative evidence without per-link verdicts; C = diagram only. | score (A best) |
| Q6 | **Verdict independence**: the verdicts come from an evaluation or an evidence synthesis, not only from the designers' own expectations. | score |
| Q7 | **Conclusions**: the source states overall conclusions (does the theory hold, which links are weakest). | score |
| Q8 | **Transcription confidence**: arrows are clear at box level; few ambiguous links. | score |
| Q9 | **Timing** (recorded, not a filter): *prospective*: written before or at launch to design the intervention and plan its evaluation, with untested assumptions; *retrospective*: written or revised after delivery and tested by an evaluation (for example by contribution analysis), with verdicts; *reconstructed*: an evaluator built it afterwards because none existed; *synthesis*: a systematic review's model across many programmes. | record |

### 2b. Corpus criteria (the set as a whole)

| # | Criterion | Target |
|---|---|---|
| C1 | Size | at least 20 ToCs (not counting levels of one programme separately); more if they pass the quality criteria and add variety |
| C1b | Timing | both prospective and retrospective ToCs, and some **pairs**: a programme's prospective ToC plus its later evaluation verdicts. Prospective ToCs match how the app is used (a person designs a new policy), so they suit the structure test (E1). Retrospective and synthesis ToCs carry verdicts, so they suit the evidence test (E3). A pair gives both on one case |
| C2 | Evidence fidelity | at least 12 at level A, the rest B; at most 3 at level C |
| C3 | Topics | at least 10 policy areas, no area more than 4 ToCs (health, education, early years, employment and skills, crime and justice, housing and homelessness, social care, environment and energy, transport, local growth and innovation, international development, public engagement, digital) |
| C4 | Geography | at least 40% outside the UK, but the UK is the largest single country |
| C5 | Intervention type | each of programme, policy or regulation, fund, service appears at least 3 times |
| C6 | Shape | a spread of sizes (small under 15 boxes, medium, large over 30) and of diagram styles (box-and-arrow, columns, nested) |
| C7 | Verdict direction | at least 5 ToCs where some links were found **not** to hold (evidence against), so we can test whether the app finds weak links and not only gaps |
| C8 | Recency | record the publication date; prefer recent sources. Most will be older than the models' training data, so step 5 (X0) tests whether the model already "knows" each ToC |
| C9 | Splits | a **development** set (about 8 ToCs) for iterating on prompts, and a **held-out test** set (the rest), fixed before the first experiment. Results on the test set are reported; we do not tune on it. |

## Step 3. What we evaluate

The app has three entry points. Each gives a different, fair comparison with a published ToC.

| Comparison | Task given to the app | What we compare | Main metrics |
|---|---|---|---|
| **E1 Structure (generate)** | an outcome-first and an intervention-first brief written from the source (intended change, population, place, time horizon, intervention) | the drafted diagram vs the published one | box recall by layer, layer agreement, link recall (strict, two-step, route), shape score, novel-box rate with a hand sample of plausible vs spurious (reuse `archive_v1/gt_eval.py`) |
| **E2 Import (existing theory)** | the published diagram (image or PDF page) | what the app read vs our transcription | box and link recall and precision (should be near 1.0); added items are labelled |
| **E3 Link evidence** | E2 (same boxes and links, so every link can be compared) and, secondarily, E1 on matched links | the app's grades (*worked elsewhere*, *holds here*) vs the source's verdicts, mapped to one scale: supports / mixed / insufficient / against | weak-link recall and precision, ordinal agreement (weighted kappa), "against" detection, confidence gradient along the chain |
| **E4 Evidence documents** | E2, for sources that name the studies behind each link (systematic reviews) | the app's evidence list per link vs the source's studies (by DOI) | per-link and per-theory document recall |
| **E5 Conclusions and report** | E1 and E2 | the app's header verdict, weakest links, critical connection and evaluation questions vs the source's conclusions | LLM-judge rubric (one strong model, fixed prompt), checked by hand on a sample; the quality checklist from v1 protocol § 4 |
| **Cost and time** | all | | USD and minutes per run |

**Leakage.** For a level-A source, the app's search can find the very evaluation that holds the
verdicts. That is not cheating for a synthesis (finding the same studies is the goal), but it is
for an ex-post evaluation of the same programme. Rule: for ex-post evaluations, run with an
evidence year cut-off before the evaluation's first report, and also report a run without the
cut-off, to see how much the app relies on the source. The app supports a year window
(`published_before`); it cannot exclude one document, so the scorer also reports which links
cited the source itself (`notes.md` § Settings).

**Ex-ante vs ex-post.** A published verdict from an evaluation says what happened in that
programme. The app says what the wider evidence predicts. Some disagreement is expected and is
reviewed by hand, not counted as a plain error (v1 protocol § 4).

## Step 4. One schema for every case

`case.json`, one per ToC, checked by `schema.py`. It extends the v1 format
(`archive_v1/datasets/ground_truth_v1/tools/gt_data.py`):

- `meta`: id, title, organisation, year, country, topic, intervention type, URLs, licence,
  figure page, evidence fidelity (A/B/C), verdict source, split (dev/test)
- `brief`: intended change, population, place, time horizon, intervention (with dosage),
  context; the outcome-first and intervention-first brief texts made from them
- `boxes`: id, label (source words), layer (canonical), container
- `links`: from, to, two-way, transcription confidence (high/medium/low), source verdict (raw
  words and mapped scale), the assumptions on it, studies cited (DOIs)
- `assumptions` and `risks`: text, location (link or layer transition), source verdict
- `context`: external factors
- `conclusions`: overall verdict (raw words), weakest links, strongest links, recommendations,
  quoted with page numbers
- `transcription`: who and how (model-assisted, then checked by hand), date, open questions

Extraction: a strong model reads the figure and the text and fills the schema; a person checks
every box and link against the figure. The check is the slow part (about 20–30 minutes per ToC).

**Provenance** (owner, 2026-11-09: "a very clear chain of provenance" first, an easy way to
explore later): longlist row → `source.json` (URL, retrieval date, PDF pages) → PDF checksum →
model draft (model, prompt checksum, cost) → checked record (draft and checked copies both
committed, so a diff shows every hand correction) → each verdict's quote and page. Details in
`scripts/evals/theory_of_change/README.md`. **Later:** a review page per case (the figure image
beside its boxes, links and verdicts), built from these files once the dataset is compiled.

## Step 5. Experiments

| ID | What changes | Why |
|---|---|---|
| X0 | **Plain-model baseline**: one prompt to the drafting model, no search, asked for the same output | Is the app better than asking a model directly? Also shows how much the model already knows the published ToC (leakage through training) |
| X1 | **App, production settings** (the current route and depth) | The baseline the rest are compared with |
| X2 | Model tiers for the draft and judge steps (Luna, Terra, Sol) | Quality per dollar |
| X3 | Evidence search depth: (a) draft only, no check; (b) production (10 documents per link, automatic second search for thin links); (c) plus "Find more evidence" on every link (40 documents per link) | Does more searching change the grades? Depths are code constants, so (b) and (c) use the app's own API modes; other depths would need a patch in the eval's server process |
| X4 | Entry point: outcome-first vs intervention-first vs existing theory | Which comparison is most informative, and where the app is weakest |
| X5 | Repeats: 3 runs of X1 on the development set | Run-to-run noise, so we know what size of change is real |

Order: X5 and X1 on the development set first (it sets the noise level), then X0 and X1 on all
cases, then X2 and X3 on the development set, then the winners on the test set.

**Cost guide.** A v1 run cost about 0.40–0.50 USD in the app and 0.05 USD to score, and took
about 6 minutes. Roughly: X1 on 25 cases × 3 entry points = 75 runs (about 40 USD); X5 = 16
extra runs; X2 and X3 on 8 dev cases × 4 settings = 32 runs; X0 is cheap. Total about 80–100
USD. The owner approves the budget before step 6.

## Step 6. Run and report

Results go to `docs/tasks/060-toc-evals/notes.md` and a short report per experiment, with the
per-case tables. Large outputs stay git-ignored under the eval folder.

## Open questions for the owner

1. Budget for step 6 (about 80–100 USD; see step 5).
2. The leakage rule for ex-post evaluations (year cut-off), if the app supports it.
3. Keep the 4 v1 ToCs in the new set (re-extracted into the new schema)? Proposal: yes; they
   are UK, checked, and Changing Futures is level A.
4. Who checks transcriptions by hand: the owner, or the lead with a second model as checker?
