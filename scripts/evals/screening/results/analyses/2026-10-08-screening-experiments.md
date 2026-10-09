# Screening experiments

This file records the research and development experiments on the screening step, stage
1: the title-and-abstract screen that decides which search results the app keeps. Each
experiment changes one thing (the model, the number of calls, the prompt, the question
text) and measures it against human include/exclude labels. The dated log of runs and
decisions is in `docs/tasks/050-improve-screening/notes.md`; the headline rows are in
`results/history.md`. This file holds the method, how to run it, and the key results.
The illustrated version is `2026-10-08-screening-experiments.html` in this folder.

Nothing here changes the app. Every experiment overrides the model, the number of calls
or the prompt inside the eval process only; the production prompt (`screen_v2`) and its
hash pin are unchanged.

## Key results (as of 2026-10-08)

**Recall** is the share of human-included documents the screen kept. It is the number
that matters most for stage 1: a wrongly kept document is read in full later and can
still be dropped; a wrongly dropped one is gone. **Precision** is the share of kept
documents that humans included. **F1** weighs the two equally; **F2** counts recall twice
as much. On `mini` (144 included documents) a difference under about 5 points of recall
is within the noise; on `full` (954) under about 2.

| Setting | Data | Recall | Precision SYNERGY / all | F2 | Cost per run |
|---|---|---:|---|---:|---:|
| Today's setting: gpt-5.4-mini, 3 calls, `screen_v2`, published title + criteria | `mini` | 0.854 | 0.854 / 0.695 | 0.817 | $0.97 |
| **Recommended: gpt-5.6-luna, 3 calls, `screen_v4`, published title + criteria** | `mini` | **0.917** | 0.918 / 0.698 | **0.863** | **$0.19** |
| The same | `full` | **0.900** | **0.688 / 0.642** | **0.833** | $1.97 |
| Best non-AI method at the same workload (embeddings, same question and criteria) | `full` | 0.799 | 0.633 / 0.569 | 0.739 | about $0.02 |
| The same with one call in place of three (replayed) | `full` | 0.893 | 0.680 / 0.634 | 0.826 | about $0.66 |
| The same, adaptive: ask once more only after a "drop" (replayed) | `full` | 0.917 | 0.659 / 0.619 | 0.837 | about $1.00 |

**How the final setting was reached** (`mini`). Every row uses each review's published
title as the question. The first group adds the review's criteria, as the app does, one
change per row; the second group is the same without criteria, for comparison.

| Setting | Model | Prompt | Recall | Precision (all) | Cost |
|---|---|---|---:|---:|---:|
| *With criteria (as the app works)* | | | | | |
| Today's setting | gpt-5.4-mini | `screen_v2` | 0.854 | 0.695 | $0.97 |
| 1. Cheaper model | gpt-5.6-luna | `screen_v2` | 0.868 | 0.714 | $0.23 |
| **2. New prompt: final** | gpt-5.6-luna | **`screen_v4`** | **0.917** | 0.698 | $0.19 |
| *Without criteria (for comparison)* | | | | | |
| Today's model and prompt | gpt-5.4-mini | `screen_v2` | 0.896 | 0.620 | $0.91 |
| Cheaper model | gpt-5.6-luna | `screen_v2` | 0.938 | 0.659 | $0.23 |
| Cheaper model, new prompt | gpt-5.6-luna | `screen_v4` | 0.958 | 0.639 | $0.17 |

With today's prompt, criteria lower recall by 4 to 7 points: the model uses them as
strict rules. `screen_v4` restores most of that and keeps most of the precision gain.
The final setting keeps the criteria because the app passes them and precision matters
too. Against today's setting with criteria: 9 includes kept only by the final setting, 0
only by today's (exact McNemar p = 0.004).

Total spend on these experiments: about $9.

### 1. The ground truth: what we test against

**The test.** Stage 1 gets a research question and one document's title and abstract,
and answers keep or drop. The ground truth is a set of such pairs where we already know
the right answer, because human reviewers decided it when they wrote a published
systematic review or evidence gap map. We give the screen the same question and
document, and count how often it agrees with them.

**One test item** has four parts:

| Part | What it is | Example |
|---|---|---|
| Question | The published title of a review or map. With `--criteria`, the review's own published inclusion criteria are added under it | "Long-term Outcomes of Cognitive Behavioral Therapy for Anxiety-Related Disorders" |
| Document | One study's title and abstract, from that review's records | "Applied relaxation vs. cognitive therapy in the treatment of generalized anxiety disorder" |
| Human label | Include (1) or exclude (0), as the reviewers decided | 1 (include) |
| Screen's answer | Keep or drop, from the run being tested | — |

The same question also gets excludes, such as "Is Posttraumatic Benign Paroxysmal
Positional Vertigo Different From the Idiopathic Form?" (0, exclude).

**Where the labels come from.** Three public sources, ten questions each, 30 in total:

| Source | What it is | Include means | Exclude means | What it is good for |
|---|---|---|---|---|
| **SYNERGY** | A public set of 26 systematic reviews with every screening decision kept (psychology, medicine, software engineering) | The review included the study | A human screener excluded it on title and abstract | Recall, and the only clean precision |
| **CSMeD** | Cochrane health reviews, from a research collection of screening data; we use its full-text file | The review included the study after reading the full paper | A human **kept** it on title and abstract, then excluded it at full text | Recall. Its excludes passed human title-and-abstract screening, so stage 1 is right to keep many of them |
| **3ie** | Ten evidence gap maps from the International Initiative for Impact Evaluation, on development policy (climate, governance, migration, food systems, health, water, energy, land use, resilience) | The study is on the map | **Nobody judged it against this question.** It is a study from one of the other nine maps; studies whose title is also on the question's own map are left out | Recall on policy topics. Its excludes are easier than real search results |

**Two sizes**, drawn with one fixed seed, so `mini` is inside `full`:

| Dataset | Per question | Documents | Included | Use |
|---|---|---:|---:|---|
| `mini` | up to 5 included, 5 excluded | 288 | 144 | Trying ideas cheaply (under $1 a run) |
| `full` | up to 50 included; excluded up to 100, at most three per included | 2,949 | 954 | Confirming the winner |

**How the questions were made.** Without a language model: a script
(`build_targets.py`) copies each review's or map's published title and removes endings
such as ": a systematic review". The criteria are copied text too: the Cochrane
"Objectives" section, the eligibility criteria SYNERGY quotes from each paper, and the
3ie map's own intervention and outcome groups. (The first runs used an earlier set of
question summaries of unclear origin; they are recorded in the task notes and are not
used here.)

**What the ground truth cannot tell us:**

- **Precision reads far too high.** `mini` is half included and `full` a third. Real
  search results are a few per cent relevant, so the screen will keep many more
  irrelevant documents per relevant one in the app.
- **The excludes are mostly easy.** A random sample of a review's excludes is mostly far
  off topic (for the anxiety question above: knee injuries, vertigo), because the review's
  own search was broad. Real near-misses are rare in the sample.
- **Two thirds of it is health and psychology.** Only the 3ie third is close to the app's
  policy topics.
- **Labels are final decisions**, some doubtful: reading the 13 includes every model
  dropped found 3 that look wrongly labelled.
- **No full text**, so stage 2 is not tested.

**Checks before the first paid run.** An adversarial review (Codex) found that 3ie
excludes came mostly from the largest maps; checking that showed 8% of `mini`'s 3ie
excludes were also on the question's own map, so wrongly labelled. Both fixed: excludes
now come evenly from the other maps, and studies on the question's own map are left
out. It also showed the CSMeD folder only loaded on macOS (capitals in the folder name);
fixed.

### 2. Today's model against the cheaper model

`mini`, three calls, production prompt (`screen_v2`), published titles:

| Model | Criteria | Recall | Precision (all) | F1 | F2 | Cost |
|---|---|---:|---:|---:|---:|---:|
| gpt-5.4-mini (today) | No | 0.896 | 0.620 | 0.733 | 0.823 | $0.91 |
| gpt-5.6-luna | No | 0.938 | 0.659 | 0.774 | 0.864 | $0.23 |
| gpt-5.4-mini (today) | Yes | 0.854 | 0.695 | 0.766 | 0.817 | $0.97 |
| gpt-5.6-luna | Yes | 0.868 | 0.714 | 0.784 | 0.832 | $0.23 |

Luna is not worse and costs a quarter. Two findings explain part of the gap:
gpt-5.4-mini spends **no** hidden reasoning tokens per screening call with the
production settings (Luna about 100), and both models give confidence 0.78–0.99 on
their wrong exclusions, the same range as on their right ones. The confidence number
carries no signal, so an "ask again when unsure" rule based on it never fires.

### 3. The vote: is calling three times worth it?

Production asks the model three times per document and keeps it on a majority (an
`unsure` counts as keep). Every run saves the three answers in order, so other rules
can be replayed on the same answers without new calls (`analyse_runs.py`). On `full`,
Luna, `screen_v4`, criteria (954 included, 1,995 excluded):

| Rule | Recall | Excludes dropped | Precision SYNERGY / all | F1 | F2 | Calls per document |
|---|---:|---:|---|---:|---:|---:|
| One call | 0.893 | 1,504 | 0.680 / 0.634 | 0.742 | 0.826 | 1.00 |
| Majority of three (production) | 0.900 | 1,515 | 0.688 / 0.642 | **0.749** | 0.833 | 3.00 |
| Keep if any of three keeps | 0.927 | 1,428 | 0.639 / 0.609 | 0.735 | **0.839** | 3.00 |
| Adaptive: after a "drop", ask twice more, majority | 0.905 | 1,485 | 0.672 / 0.629 | 0.742 | 0.832 | 2.09 |
| **Adaptive: after a "drop", ask once more, keep if it keeps** | **0.917** | 1,456 | 0.659 / 0.619 | 0.739 | 0.837 | **1.54** |

F1 and F2 move by about one point across all five rules: every rule trades a few points of precision for a few points of recall at almost the same balance. F1 favours the majority, F2 favours keeping more. The same pattern holds on `mini` for both models.

- **The majority vote buys almost nothing.** Against one call it keeps 7 more of 954
  included documents (0.7 points) and drops 11 more excludes, for three times the cost.
  A majority is symmetric: it corrects a stray "keep" as often as a stray "drop", so it
  does not serve a recall-first screen.
- **Repeats help when they are asymmetric.** Asking again only after a "drop", and
  keeping if the second answer keeps, gains 2.4 points over one call for 54% more calls;
  it keeps 48 more excludes, which stage 2 can still remove. "Keep if any of three" gains
  most but costs three calls.
- **The one real reason for repeats is stability.** Two separate one-call runs would
  decide differently on about 5% of documents (3.8% of included ones), estimated from
  the pairs of calls. The literature agrees: two identical GPT-5.4 runs differed on 8% of
  records and 29 eligible records were kept by only one run (Figalová et al. 2026,
  arXiv 2608.26885); repeat-run agreement for GPT-4o had a median kappa of 0.94
  (Sanghera et al., JAMIA 2025). Majority voting across models or runs is reported to
  beat single runs (medRxiv 2025.08.11.25333429), and a single run for high-recall work
  is called inadequate without other checks. The asymmetric rule addresses the risk that
  matters (losing an include) at half the cost of the majority.
- **Caveat:** every replayed rule applies the production title-only rule, so the
  majority row is exactly the run's own result. The replay treats the three saved calls
  as independent draws, which they are; production would also need a code change, because it needs at least two valid
  answers per document (`SCREEN_QUORUM = 2`) and has no second round of calls.

### 4. A shorter prompt costs recall

`screen_short_v1` keeps every rule of `screen_v2` in 59% fewer characters. This test ran
before the questions were rebuilt, so both arms used the earlier question set; the
comparison is between prompts on the same questions. On `mini`,
recall fell on both models (mini 0.868 → 0.840, Luna 0.896 → 0.861; together 10
includes lost, 1 gained). The models stopped answering `unsure` (mini: 33 → 12 times):
the long prompt's "unsure is an honest answer" and "a wrongly excluded document is gone
for good" do work. The saving was small (mini −22%) and zero on Luna, which lost the
cache discount (it needs a prompt of at least 1,024 tokens). Do not shorten for cost.

### 5. The questions, and why criteria hurt with today's prompt

The questions are built **deterministically, without a language model**
(`build_targets.py` → `targets.json`): the published title (a fixed rule removes ": a
systematic review" and the like), plus published criteria for `--criteria` runs (Cochrane
"Objectives", SYNERGY's quoted eligibility criteria, the 3ie map's intervention and
outcome groups), added by the product's own `_compose_screen_intent`.

| Recall on `mini`, `screen_v2` | Title only | Title + criteria |
|---|---:|---:|
| gpt-5.4-mini | 0.896 | 0.854 |
| gpt-5.6-luna | 0.938 | 0.868 |

With today's prompt, criteria made the screen stricter (Luna: 11 includes lost, 1
gained, p = 0.006) and raised precision. The models applied every criterion as a gate,
excluding on details an abstract rarely settles ("not based on routinely collected
healthcare data", "no concurrent comparison group"). This matches Behrouzian et al. 2026
(doi 10.3390/info17050449). **It is also a product finding:** the app adds a plan's
criteria the same way, and the prompt never says how to use them. Section 6 fixes this
in the prompt, and the final setting keeps the criteria.

### 6. Three wording changes: `screen_v3` and `screen_v4`

Each is `screen_v2` plus targeted rules (files in `prompts/`):

- **v3:** exclusion needs a clearly different *subject* ("population" removed); a document
  matching the main subject but differing in one element is `relevant` or `unsure`; a
  criterion excludes only when the title or abstract clearly contradicts it, never when
  it is unreported.
- **v4:** v3 with the owner's population rule: a population the scope names is a
  requirement, so a **clearly different** population is excluded; a **related** one
  (overlap, subgroup, wider group including it) is kept; no named population, no
  exclusion on population.

| Luna, `mini`, with criteria | Recall | Precision SYNERGY / all | F1 | F2 | Cost |
|---|---:|---|---:|---:|---:|
| `screen_v2` (production text) | 0.868 | 0.909 / 0.714 | 0.784 | 0.832 | $0.23 |
| `screen_v3` | 0.910 | 0.863 / 0.701 | 0.792 | 0.858 | $0.24 |
| **`screen_v4`** | **0.917** | **0.918** / 0.698 | **0.793** | **0.863** | $0.19 |

The criteria rule recovered exactly the full-text-only cases (v3 against v2: 6 gained,
0 lost, p = 0.03). gpt-5.4-mini did not follow it (no change with criteria): a nuanced
rule seems to need a model that reasons.

### 7. Confirmation on `full`, against non-AI baselines

A fair non-AI comparison (`rank_baselines.py`): rank each question's documents without a
language model, then keep, per question, **as many documents as Luna kept**, so both
spend the same reading effort. BM25 (keyword score), embedding similarity with the
product's own model (`text-embedding-3-small`), and their rank fusion. This is the
standard zero-shot set in the literature (CSMeD, Kusa et al. 2023; Wang et al. 2022); no
published zero-shot numbers on policy reviews were found.

| `full`, 1,339 of 2,949 kept | Recall [95%] | Excludes dropped | Precision SYNERGY / all | F1 | F2 |
|---|---|---:|---|---:|---:|
| **Luna + `screen_v4` + criteria** | **0.900** [0.88–0.92] | **1,515** | **0.688 / 0.642** | **0.749** | **0.833** |
| Embeddings, question + criteria (like for like) | 0.799 [0.77–0.82] | 1,418 | 0.633 / 0.569 | 0.665 | 0.739 |
| Hybrid, question + criteria | 0.773 | 1,393 | 0.611 / 0.550 | 0.643 | 0.715 |
| BM25, question + criteria | 0.689 | 1,313 | 0.535 / 0.491 | 0.573 | 0.637 |
| Embeddings, question only (the baseline's best variant) | 0.811 [0.79–0.83] | 1,430 | 0.628 / 0.578 | 0.675 | 0.751 |
| Chance (random pick, same size) | 0.467 | — | — / 0.333 | — | — |

Like for like (the rankers get the same question and criteria as Luna), Luna keeps 137
includes the embeddings miss, and they keep 40 Luna misses (p < 0.001): +10 points. Given
the question only, which suits the rankers better, embeddings reach 0.811: still 9
points behind. The gap is largest on policy data: 3ie 0.884 against 0.750 (0.772 with the
question only); SYNERGY 0.904 against 0.831; CSMeD 0.964 against 0.918 (every method does
well there). `mini`'s result held up (0.917, inside its interval). As in CSMeD's own
baselines, criteria text did not help the rankers.

### 8. Findings for the app (not fixed; for a production slice)

1. Stage 1 gets stricter whenever a plan carries screening criteria: the prompt does not
   say how to use them (section 5).
2. gpt-5.4-mini does no hidden reasoning in screening calls; the `reason` field comes
   after the `decision`.
3. The confidence number does not separate right from wrong answers.
4. One call per document is impossible today: `SCREEN_QUORUM = 2` would fail every
   document.

### 9. Recommendation and next steps

- **Model and prompt:** move stage 1 to gpt-5.6-luna with the `screen_v4` text. On `full`
  it reaches 0.900 recall with criteria, at about a fifth of today's cost per run.
- **Calls:** replace the majority of three with the adaptive rule (one call; after a
  "drop", one more; keep if it keeps): about 0.917 recall at about half of three calls.
  Confirm with a real run on `full` before the production slice.
- **Before the slice:** a real adaptive run on `full`; a look at what stage 2 does with
  the extra kept documents (these datasets have no full text, so it needs real search
  results); a small hand-labelled sample of our own search candidates, where relevant
  documents are a few per cent, not a third.

## Terms used in the tables

- **Recall**: included documents kept, divided by included documents.
- **Excludes dropped**: excluded documents the screen dropped. Higher is better.
- **Precision**: included documents kept, divided by all documents kept. `mini` is half
  included and `full` a third, so precision reads far higher than in real use.
- **F1 / F2**: one number combining precision and recall; F2 counts recall twice.
- **p**: exact McNemar test on included documents one setting kept and the other did not.
  Under 0.05: unlikely to be chance.
- **Question**: the review's or map's published title, built by `build_targets.py`.
  **Criteria**: the review's published inclusion criteria, added below the question.

## The scripts

All from the repository root. The model calls use `OPENAI_API_KEY` in `backend/.env`.

```
# a run (defaults: mini, gpt-5.4-mini, three calls, production prompt, title only)
uv run --project backend --env-file backend/.env python scripts/evals/screening/checks/run_screen.py \
    --model gpt-5.6-luna --criteria --system-prompt scripts/evals/screening/prompts/screen_v4.txt

# summarise and compare saved runs, including the vote-rule replay (no model calls)
uv run --project backend python scripts/evals/screening/checks/analyse_runs.py \
    scripts/evals/screening/results/runs/<run A> [<run B> ...]

# non-AI baselines matched to a run
uv run --project backend --env-file backend/.env python scripts/evals/screening/experiments/rank_baselines.py \
    --dataset full --match scripts/evals/screening/results/runs/<run>

# rebuild the questions from the published sources
uv run --project backend python scripts/evals/screening/build_targets.py
```
