# Design experiments for the production search and screen (task 051, 9 October 2026)

Five small experiments to settle the open questions of the task 051 proposal (the
tutorial page `docs/tutorials/search-and-screen/index.html`), before the production
slice is contracted. All on the `retrieval-ground-truth-mini` set (15 reviews, DOI
recall of each review's reference list) unless stated; the policy side on the gov.uk
instrument of task 049. Nothing here changes the app. The dated log with the decisions
is `docs/tasks/051-improve-production-search-screen/notes.md`.

Two things were fixed by owner decision before the experiments and are not tested
here: query generation and screening move to `gpt-5.6-luna` (the current
`gpt-5.4-mini` is not available after the Bedrock migration), and Overton's cited
papers stay out of the paper pool (resolving them costs about 20 calls per search for
a gain inside the noise). Experiment 2 was dropped with the second decision;
experiment 6 (the 100-review set) was stopped at 16 reviews, to be run once the whole
configuration is built; experiment 7 (a real one-call screening run) was judged
unnecessary.

## Key results

| question | answer | experiment |
|---|---|---|
| What does Luna cost as the query model? | About 2 points at 100 to 200 candidates, nothing at 300 and 400 | 1 |
| Where is the knee of the cap curve? | There is none: every 100 papers buys 2 to 5 points up to 400 | 1 |
| Do screened seeds improve the snowball? | No. Same recall at 200 and above, half a point lower at 100 | 3 |
| How good is the screen on real search candidates? | Keeps 97% of the ground-truth papers among the seeds, drops 28% of the pool, 1.3 calls per document | 3 |
| Does query reformulation find papers the citation graph cannot? | Yes: +3.9 points at the ceiling, four times a bigger snowball; the gain at the cut is not measured | 4 |
| How many policy documents per scope? | The policy snowball reaches 90% of its pool by 50 documents and 97% by 100 | 5 |

## 1. The cap curve for the final configuration (`experiments/snowball_recall.py`)

The task 047 best configuration (5 generated keyword queries sent three ways plus
8 semantic calls as seeds, 200 seeds; reference-frequency snowball of 200; forward
chasing of 200 from the 20 most-cited seeds; specificity ranking), scored at five
caps, once with Luna as the query model and once with the current model.

| query model | @100 | @150 | @200 | @300 | @400 | seminal decile @200 | generation |
|---|---:|---:|---:|---:|---:|---:|---:|
| gpt-5.4-mini (today) | 16.7% | 20.1% | 22.2% | 25.3% | 28.0% | 46.0% | 1.8 s |
| **gpt-5.6-luna** | 15.5% | 18.5% | 20.3% | 25.2% | 27.6% | 44.9% | 2.9 s |
| raw order, Luna (control: no ranking) | 8.3% | 10.1% | 11.2% | 19.7% | 24.1% | 25.8% | |

One run each, 0 failed calls. The mini-set noise between two runs of one setting is
about a point. Run folders: `results/snowball/2026-10-09-shared+semantic-c6e320[-gpt-5.6-luna]-s200-k200-f200p10c300t20`.

## 3. Screened seeds against raw seeds (`experiments/screened_seeds.py`, new)

Each of the 200 seeds of the Luna run was screened through the production stage-1
code path (via the screening harness) with Luna, the `screen_v4` prompt and the
adaptive rule: one call, a second call only after a drop, keep if the second call
keeps. The snowball and forward chasing were then rebuilt from the kept seeds only.

| list | @100 | @150 | @200 | @300 | @400 | ceiling |
|---|---:|---:|---:|---:|---:|---:|
| raw: the experiment-1 list, unscreened | 15.5% | 18.5% | 20.3% | 25.2% | 27.6% | 29.2% |
| raw with the dropped seeds removed (what production keeps) | 15.3% | 18.2% | 20.1% | 24.9% | 27.2% | 28.9% |
| snowball rebuilt from the kept seeds | 14.9% | 18.0% | 20.3% | 25.2% | 27.6% | 29.3% |

The screen on the 2,966 seeds: 72% kept (49% to 85% per review); 98 of the 101
ground-truth papers among the seeds kept (the three lost are on one review); 3,863
calls, 1.3 per seed, about 30 cents. Run folder
`results/snowball/2026-10-09-screened-seeds-gpt-5.6-luna-s200-k200-f200` (per-seed
verdicts under `verdicts/`).

Reading: the off-topic seeds the screen drops cite the same landmark papers as the
kept ones, so the citation counts do not change. There is no reason for a second
search pass that depends on screening verdicts. As a by-product this is the first
measurement of the screen on the documents it will see in production: 97% recall on
title-shaped intents without criteria.

## 4. Reformulation against a bigger snowball (`experiments/reformulate_gain.py`, new)

The production reformulate call on Luna, with the exemplars production would choose
from the experiment-3 verdicts, its first 4 queries sent to OpenAlex (200 each), and
the ground-truth papers they return that the pool does not hold. Against the same
budget spent on 200 more snowball papers.

| addition to the pool | @200 | @400 | ceiling |
|---|---:|---:|---:|
| nothing (experiment 1, Luna) | 20.3% | 27.6% | 29.2% |
| 200 more snowball papers | 20.5% | 27.4% | 30.2% |
| 4 reformulated queries (60 queries, 119 ground-truth hits, 32 new) | not ranked | not ranked | 33.1% |

Of the 32 new papers, 21 are cited by at least one seed, 11 by none. The gains sit on
the reviews the snowball already serves (learning loss +5, whole-school +6, energy
efficiency +6, loneliness +3); the gap-map rows gain 0 to 1. Run folders
`results/snowball/2026-10-09-shared+semantic-c6e320-gpt-5.6-luna-s200-k400-f200p10c300t20`
and `results/snowball/2026-10-09-reformulate-gpt-5.6-luna` (`queries.csv`: every query
with its hits).

Reading: the reformulated queries reach papers the citation graph cannot, and a
bigger snowball reaches almost nothing new. What is not measured is how many of the
32 land inside a 200 or 400 cut once ranked; with 21 carrying an in-set count, one to
two points is plausible. The cost is structural: production's reformulation needs
screened exemplars, so it needs a screen between two search passes.

## 5. The policy-document cap (`experiments/policy_gt.py --set specific --docs 400 --paraphrases`)

| order | @25 | @50 | @100 | @200 | pool ceiling |
|---|---:|---:|---:|---:|---:|
| relevance, global | 3.5% | 3.7% | 4.8% | 7.3% | 8.8% |
| snowball + specificity, global | 6.0% | 8.0% | 8.5% | 8.8% | 8.8% |
| relevance, UK-only | 4.6% | 5.4% | 8.8% | 13.3% | 15.4% |
| snowball + specificity, UK-only | 9.0% | 12.7% | 13.7% | 14.8% | 15.4% |

The instrument favours the snowball by construction and its level is low for
structural reasons (task 049, section 3.3); read it for the cap. The snowball order
reaches 90% of its pool ceiling by 50 documents and 97% by 100, in both settings.

## The design these numbers support

One single-pass search method at every scope: Luna writes the queries; OpenAlex
keyword and semantic seeds; backward snowball and forward chasing; Overton by
relevance with the policy-to-policy snowball and landmark fetching; specificity
ranking for papers (the "relevance reserve" of the task 047 write-up was never
implemented or measured and is not part of the design); two caps per scope; one Luna screen with
the adaptive rule. The round loop, the exemplar reader and the reformulate, suggest,
snowball and diversity arms are deleted.

| scope | papers kept | policy documents kept | paper recall measured (Luna, mini) | documents screened |
|---|---:|---:|---:|---:|
| Focused | 100 | 50 | 15.5% | about 150 |
| Broad | 200 | 100 | 20.3% | about 300 |
| Broadest | 400 | 200 | 27.6% | about 600 |

Today's measured recall for comparison: Focused 2.2%, Broad 5.0% on the same 15
reviews. The screen keeps about 72% of what it reads, at 1.3 Luna calls per document.

One design call stays open: reformulation. It is the only addition that measurably
reaches papers the graph cannot (+3.9 at the ceiling), and the only one that needs a
second pass. Recommendation: not in the first slice; park it as a measured option for
Broadest, to be revisited after the end-to-end check of the built configuration.

## Scripts

All under `scripts/evals/search/experiments/`, run from the repository root with
`uv run --project backend --env-file backend/.env python <script> --help`. All cached
under `results/cache/`; none uploads to Langfuse.

| script | what it measures | output |
|---|---|---|
| `snowball_recall.py` | experiment 1 and the expand-400 run (`--model`, `--caps`, `--expand`) | `results/snowball/<label>/scores.csv` |
| `screened_seeds.py` | experiment 3: seeds screened with the production code path, snowball rebuilt from the kept ones | `results/snowball/<date>-screened-seeds-*/scores.csv`, `seeds.csv`, `verdicts/` |
| `reformulate_gain.py` | experiment 4: the production reformulate call from those verdicts, new ground-truth papers | `results/snowball/<date>-reformulate-*/scores.csv`, `queries.csv` |
| `policy_gt.py` | experiment 5 | `results/overton/policy_gt_specific[-UK]/scores.csv` |
