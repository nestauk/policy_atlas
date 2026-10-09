# Task 051: improve the production search and screen

Exploratory step first (owner, 2026-10-09), then the task cycle with a contract.

## 2026-10-09 — Map of today's design, and the proposal

`docs/tutorials/search-and-screen/index.html`: how search (Focused / Broad / Broadest)
and stage-1 screening work today, with diagrams; what tasks 047, 049 and 050 found; a
proposed design (one search method, three pool sizes, one cheap screen); the owner's
open questions answered; the experiments to run before the contract; and the production
change list for the contract.

Steer in one line: rebuild Focused as the strong single-round method (generated queries,
semantic seeds, both snowballs, specificity ranking, Luna screen), make Broad and
Broadest the same method with bigger caps, delete the round loop and its arms unless a
small reformulation experiment earns one back. Pin the caps from the cached cap curve
before the contract.

## 2026-10-09 — Owner decisions on the proposal

- De-duplicate Overton results by title. Records with a removed title: parked.
- Query generation (and the reformulate call, if it survives) on `gpt-5.6-luna`, not
  `gpt-5.4-mini`: mini will not be available after the Bedrock migration.
- Overton's cited papers (`cites.scholarly`) stay out of the paper pool. Reading them
  costs nothing, but resolving the Overton-only papers on OpenAlex is about 20 batched
  calls per search, and the measured gain at 200 was 0.9 points, inside the noise.
  Experiment 2 is dropped with it.
- The Overton snowball is the full one: count the policy documents the results cite,
  fetch the most-cited ones the search did not return, rank with specificity. It is
  what Diagram D in the tutorial proposes.
- Screening: `gpt-5.6-luna`, prompt `screen_v4`, one call per document and a second
  call only after a drop (keep if the second call keeps). Experiment 7 (a real run of
  that rule on the labelled set) is not needed.
- Experiment 8 (end to end in the app) runs after the build.
- Housekeeping done the same day: `scripts/evals/{search,screening}/measure/` split
  into `checks/` (the app as built: `production_recall.py`, `baseline_recall.py`,
  `run_screen.py`, `analyse_runs.py`) and `experiments/` (research scripts). Paths in
  docstrings, READMEs, write-ups and the Makefile updated; `make eval-check` passes.

## 2026-10-09 — Experiment 5: the policy-document cap

`experiments/policy_gt.py --set specific --docs 400 --paraphrases`, with and without
`--source-country UK`. Cached, free. Same numbers as the 2026-10-08 rebuild; read here
for the cap, not the level (the instrument is built from gov.uk strategies and
favours the snowball by design).

| order | @25 | @50 | @100 | @200 | pool ceiling |
|---|---:|---:|---:|---:|---:|
| relevance, global | 3.5% | 3.7% | 4.8% | 7.3% | 8.8% |
| snowball + specificity, global | 6.0% | 8.0% | 8.5% | 8.8% | 8.8% |
| relevance, UK-only | 4.6% | 5.4% | 8.8% | 13.3% | 15.4% |
| snowball + specificity, UK-only | 9.0% | 12.7% | 13.7% | 14.8% | 15.4% |

What we learned: the snowball order reaches 90% of its pool ceiling by 50 documents
and 97% by 100, in both settings. The policy-document cap can be smaller than the
paper cap: 50 / 100 / 200 for Focused / Broad / Broadest would lose almost nothing
that the 400-document pool holds. The pool itself is the limit (section 3.3 of the
Overton write-up: 77% of the targets are cited by no retrieved document).

## 2026-10-09 — Experiment 1: the cap curve for the final configuration, Luna and mini

`experiments/snowball_recall.py --queries shared+semantic --seeds 200 --expand 200
--forward 200 --forward-top 20 --forward-pages 10 --caps 100 150 200 300 400`, once
with `--model gpt-5.6-luna` (the model the production slice will use) and once with
the current `gpt-5.4-mini`. 15 reviews, specificity ranking, 0 failed calls. Run
folders `results/snowball/2026-10-09-shared+semantic-c6e320[-gpt-5.6-luna]-s200-k200-f200p10c300t20`.

| query model | @100 | @150 | @200 | @300 | @400 | seminal decile @200 (8 labelled) | generation time |
|---|---:|---:|---:|---:|---:|---:|---:|
| gpt-5.4-mini (today) | 16.7% | 20.1% | 22.2% | 25.3% | 28.0% | 46.0% | 1.8 s |
| **gpt-5.6-luna** | 15.5% | 18.5% | 20.3% | 25.2% | 27.6% | 44.9% | 2.9 s |
| control: raw order (seeds first, no ranking), Luna | 8.3% | 10.1% | 11.2% | 19.7% | 24.1% | 25.8% | |

What we learned:

1. Luna as the query model costs about two points at 100 to 200 and nothing at 300
   and 400. One run each; the mini-set noise is about a point, so the gap at 200 is
   probably real but small. The seeds differ (Luna's 75 queries scored 636 query-level
   hits against 645), and the snowball closes most of the difference. Acceptable for
   the Bedrock migration; the 300 and 400 caps are unaffected.
2. The curve is steep below 200: from 100 to 150 buys 3 points, 150 to 200 another 2,
   200 to 300 another 5, 300 to 400 another 2.5. There is no knee; every 100 papers
   buys 2 to 5 points. The cap is a budget choice, not a threshold.
3. Specificity ranking against the raw order: +7 points at 100, +9 at 200, +3.5 at
   400. The ranking matters most at the small caps the product will use most.

## 2026-10-09 — Experiment 3: screened seeds against raw seeds

New script `experiments/screened_seeds.py`. For each of the 15 reviews: the 200 seeds
of the experiment-1 Luna run, their abstracts fetched from OpenAlex (cached), each seed
screened through the production stage-1 code path via the screening harness with
`gpt-5.6-luna`, prompt `screen_v4`, and the adaptive rule (one call; a second call
only after a drop; keep if it keeps). Then the snowball and forward chasing rebuilt
from the kept seeds only. Three lists scored, specificity ranking:

| list | @100 | @150 | @200 | @300 | @400 | ceiling |
|---|---:|---:|---:|---:|---:|---:|
| raw: the experiment-1 list, no screen | 15.5% | 18.5% | 20.3% | 25.2% | 27.6% | 29.2% |
| raw, dropped seeds removed (what production keeps) | 15.3% | 18.2% | 20.1% | 24.9% | 27.2% | 28.9% |
| **screened: snowball rebuilt from the kept seeds** | 14.9% | 18.0% | 20.3% | 25.2% | 27.6% | 29.3% |

The screen on real search candidates: kept 72% of the 2,966 seeds (49% to 85% per
review); kept 98 of the 101 ground-truth papers among them (the 3 lost are all on
the adverse childhood experiences review); 3,863 calls, 1.3 per seed, about 30 cents.

What we learned:

1. **Screened seeds do not help.** Same recall at 200 and above, half a point lower
   at 100. The off-topic seeds the screen drops cite the same landmark papers as the
   kept ones, so the citation counts barely change. Seed *quality* mattered in task
   047 because seeds 201 to 500 of a weak ranking are noise; the first 200 are not.
2. **So there is no second pass.** The design stays single-round at every scope:
   search, snowball, rank, cut, screen once. Nothing in the search depends on a
   screening verdict.
3. **A screening recall on real candidates, as a by-product: 97%** (98 of 101) with
   Luna, `screen_v4` and the adaptive rule, on title-shaped intents with no criteria.
   Consistent with the labelled-set result (0.917 on `mini`, 0.900 on `full`), and
   the first measurement of the screen on the kind of document it will see.
4. The screen removes 28% of the pool before classify and the rest of the chain, so
   the cost of the downstream steps scales with 0.72 of the cap, not the cap.

## 2026-10-09 — Experiment 4: reformulation against a bigger snowball

New script `experiments/reformulate_gain.py`. Per review: the production reformulate
call (`OpenAISearchGenerationBackend.reformulate`, `gpt-5.6-luna`) with the exemplars
production would pick from experiment 3's verdicts (up to 8 kept seeds with
confidence at least 0.7, 4 dropped), its first 4 queries sent to OpenAlex (200 results
each), and the ground-truth papers they return that the experiment-1 pool (seeds,
snowball, forward chasing; ceiling 29.2%) does not hold. The comparison is the same
budget spent on the snowball: `snowball_recall.py --expand 400` on the same seeds.

| addition to the experiment-1 pool | @200 | @400 | ceiling |
|---|---:|---:|---:|
| nothing (experiment 1, Luna) | 20.3% | 27.6% | 29.2% |
| 200 more snowball papers (`--expand 400`) | 20.5% | 27.4% | 30.2% (at 600 candidates) |
| 4 reformulated queries (60 queries, 119 ground-truth hits, 32 new) | not ranked | not ranked | 33.1% (+3.9) |

Run folders `results/snowball/2026-10-09-shared+semantic-c6e320-gpt-5.6-luna-s200-k400-f200p10c300t20`
and `results/snowball/2026-10-09-reformulate-gpt-5.6-luna` (`queries.csv` has every query with its hits).

What we learned:

1. **Reformulation reaches papers the citation graph does not**: 32 new ground-truth
   papers over 15 reviews, 21 of them cited by at least one seed (so the specificity
   ranking has a signal for them), 11 with no graph signal at all. The gains sit on
   the reviews the snowball already serves (learning loss +5, whole-school +6, energy
   efficiency +6, loneliness +3); the gap-map rows gain 0 to 1.
2. **A bigger snowball reaches almost nothing new**: +1 point at the ceiling, nothing
   at 200 or 400. The 200 most-cited new papers already hold what the reference lists
   can give; papers 201 to 400 are single-citation noise.
3. **Not measured: the gain at the cut.** The reformulated results were not ranked into
   the pool. With 21 of 32 carrying an in-set count, a gain of one to two points at
   200 is plausible, not shown.
4. **The cost is structural, not monetary.** One Luna call and four free OpenAlex calls
   are cheap. But production's reformulation needs screened exemplars, so it needs a
   screen between two search passes: exactly the round structure the proposal
   removes. The question for the design is whether +3.9 points of ceiling (and an
   unmeasured amount at the cut) is worth keeping a second pass at Broadest.

## 2026-10-09 — Experiments 2, 6 and 7 not run

- 2 (Overton's cited papers merged in): dropped with the owner's decision to leave
  them out of the paper pool.
- 6 (the 100-review set): started and stopped at 16 of 100 reviews on the owner's
  call (2026-10-09, 12:15): the full check runs once the whole configuration,
  Overton included, is built. The 16 reviews' pages are cached and cost nothing.
- 7 (a real one-call run on the labelled set): not needed; the replayed rule stands.

## 2026-10-09 — The design after the experiments

Write-up with all the tables: `scripts/evals/search/results/analyses/2026-10-09-design-experiments.md`.
The tutorial page (`docs/tutorials/search-and-screen/index.html`) carries the final
diagram and numbers. Summary: one single-pass search method at every scope; the
three scopes are three pairs of caps (papers + policy documents: 100 + 50, 200 + 100,
400 + 200); Luna for query generation; Overton by relevance with the policy snowball;
no Overton-cited papers; one Luna screen with the adaptive rule; the round loop and
its arms deleted. Reformulation is the one open design call: parked as a measured
option for Broadest, not built in the first slice.
