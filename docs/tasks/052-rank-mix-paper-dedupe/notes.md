# Task 052 — Rank the paper pool as a relevant / seminal / novel mix, and drop duplicate copies

- **Status:** built and merged into task 051's branch (PR 96) on 2026-10-12; measured on the mini set the same day (below).
- **Owner ask (2026-10-12):** "we still get THE MOST relevant papers upfront as well as a mix of prominent literature. The mix of relevant, novel and seminal is key." Plus duplicate papers removed before the cap, only when the title and the authors are the same.

## Why

While live testing task 051, the paper "Avalanche and edge-of-chaos criticality do not
necessarily co-occur in neural networks" was missing from a Focused search on exactly that
topic. It was returned by 9 of the 33 query calls but the production order (specificity,
a citation-graph score) put it at 127 of 2,139, past the Focused cap of 100. Specificity
rewards papers that cite many seeds, so a review that cites everything out-ranks the
paper the question is about.

## What was tried

`scripts/evals/search/experiments/rank_mix_probe.py` runs the real search once (OpenAlex
only, rolled back), caches the pool, and re-orders it seven ways offline. No ground truth:
the check is where named papers land and what the top 100 looks like. Three questions:

| question | result file |
|---|---|
| avalanche criticality and edge of chaos | `scripts/evals/search/experiments/manual/2026-10-12-rank-mix-avalanche.md` |
| erythropoietin, the brain and the GABAergic system | `…/2026-10-12-rank-mix-epo-gaba.md` |
| retail health targets and obesity | `…/2026-10-12-rank-mix-obesity-retail.md` |

Findings, the same on all three:

- **Specificity alone** fills the top 100 mostly with papers no query returned (66% to
  81%), and misses the question's own best matches (target paper 103, the one paper on
  EPO and GABAergic maturation 244, the retail scoping review 486).
- **The relevance reserve** (deferred D6) puts those first but carries a broad query's
  off-topic results in with them.
- **Query-hit count and reciprocal rank fusion alone** put the direct matches first but
  drop the citation-found seminal papers (Beggs and Plenz 2003 falls to 68 to 75).
- **The mix** (round-robin over relevant by rank fusion, seminal by in-set citations,
  novel from the last five years) keeps the direct matches at 1, the seminal papers
  near the top, and a third of the cut from recent years.
- Pools held duplicate copies of papers (preprint and journal copy; 5 to 18 per pool with the title-and-authors rule).

## What shipped

- `pool.paper_key`, `pool.dedupe_papers`: same normalised title and same author names,
  the most cited copy kept. A shared title with other authors stays two papers.
- `pool.query_fusion`, `pool.mix_strata`, `pool.rank_mix`: the mix above; papers the
  strata leave follow in specificity order. `pool.rank_papers` (specificity) stays as
  that fallback and as the policy-side model.
- **"Cites the seeds" fused in (owner ask, 2026-10-12).** The pool ordered by weighted
  coupling joins the rank fusion as one more ranked list, counted three times
  (`pool.COUPLING_LISTS`). Offline on the three pools: counted once it changes almost
  nothing (the fusion has 23 query lists); counted three times it brings back the
  graph-found papers that are on topic (the Dutch healthy-checkout experiments 321 →
  87, "Erythropoietin: a multimodal neuroprotective agent" 263 → 91, "Being critical of
  criticality" 103 → 73) while the direct matches stay at 1 and the top 100 keeps about
  half its papers from two or more queries. An additive version outside the fusion
  (`mix_c` in the probe) pulled harder toward the graph and dropped the novel nanowire
  paper out of the cut, so it was not adopted. Columns `mix_q` (no coupling), `mix_f1`
  (once) and `mix` (three times, production) in the result files.
- `search_loop._openalex_leg` step 7 uses both; `counts["search"]["duplicate_papers"]`
  reports how many copies were dropped.
- ADR 0038 decision 4 amended; deferred D6 closed; tutorial page updated.
- The probe script calls the shipped functions for its `mix` column, so re-running it
  from the cached pools checks production against the experiment.

## Mini-set recall under the mix (2026-10-12)

One Broadest run over the 15 reviews (`mini-052-2026-10-12/deep`, commit `3dcfebe`), with
the Focused and Broad figures read from the same run's pool: the scopes differ only in
where the ranked pools are cut, and the screen judges each document on its own, so the
first 100 + 50 and 200 + 100 documents of the Broadest order are what the smaller scopes
would have kept with the same queries (`engine.recall_at_smaller_caps`, written to
Langfuse as `search_recall_at_rapid` and so on). This replaces three passes with one,
about 50 minutes instead of 90, and makes the three scopes directly comparable
(same generated queries). The small-scope figures count positions among persisted
documents, so a duplicate the task-level dedupe dropped inside the cut is not counted
against the cap; rare, and a slight overcount if anything.

| scope | search recall | after screen | task 051 run (search / screen) | threshold |
|---|---:|---:|---:|---:|
| Focused (derived) | 15.3% | 14.8% | 12.9% / 12.5% | 12.5% met |
| Broad (derived) | 19.7% | 19.0% | 17.8% / 17.3% | 17.3% met |
| Broadest (measured) | **25.3%** | 24.3% | 22.3% / 21.3% | **24.6% met** |

Broadest is above the task 051 run on 10 of 15 reviews, below on 3, ties 2. One failed
Overton call (human rights row, transport error, no status code); 34 OpenAlex 429 replies,
all recovered. Cost $10.96 at the Langfuse rate (Luna still priced at five times list):
about $2.19 at list price.

Per review (search / screen):

| review | Focused | Broad | Broadest |
|---|---:|---:|---:|
| Tackling loneliness | 11% / 11% | 13% / 13% | 24% / 24% (20 of 84) |
| Parental leave and parents' mental health | 38% / 38% | 40% / 40% | 52% / 52% (27 of 52) |
| Social care privatisation | 29% / 29% | 43% / 43% | 43% / 43% (3 of 7) |
| Adverse childhood experiences | 24% / 18% | 31% / 25% | 33% / 27% (18 of 55) |
| Youth violence interventions | 18% / 18% | 20% / 20% | 33% / 33% (16 of 49) |
| Sleep duration and obesity | 29% / 26% | 37% / 35% | 50% / 45% (42 of 84) |
| Adolescent drug abuse | 0% / 0% | 1% / 1% | 1% / 1% (1 of 70) |
| Learning (meta-analysis) | 37% / 37% | 46% / 44% | 54% / 50% (29 of 54) |
| Intimate partner violence and health | 3% / 3% | 5% / 5% | 8% / 8% (5 of 65) |
| Human rights education (gap map) | 0% / 0% | 0% / 0% | 0% / 0% (0 of 22) |
| Nutrition-sensitive agriculture (gap map) | 0% / 0% | 3% / 3% | 4% / 4% (3 of 69) |
| Learning to earning (gap map) | 19% / 19% | 22% / 22% | 26% / 26% (7 of 27) |
| Residential energy efficiency | 9% / 9% | 13% / 13% | 17% / 16% (23 of 135) |
| Whole-school interventions (gap map) | 14% / 14% | 21% / 21% | 32% / 32% (23 of 73) |
| Health and social care, 80 and over | 0% / 0% | 0% / 0% | 4% / 4% (4 of 95) |

Reading: the gain is on the paper side at every scope (about 2 to 3 points), and it is
largest where the specificity order had been filling the cut with graph-found papers
no query returned. The reviews that score near zero (drug abuse, human rights, the
80-year-olds) are the same ones as before; the mix does not change what the queries
reach, only what survives the cut.

## Not done

- The stratum a paper came from is not persisted on `source.acquired`; `query_origin`
  still says which call first returned it. `mix_screen_probe.py` replays the strata
  offline for the screening check instead.
- "Being critical of criticality in the brain" (a seminal review) sits at 103 under the
  mix on the avalanche question: it has few in-set citations in that pool. The seminal
  stratum reads in-set citations first; global citations only break ties.
