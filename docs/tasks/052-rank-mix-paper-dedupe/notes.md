# Task 052 — Rank the paper pool as a relevant / seminal / novel mix, and drop duplicate copies

- **Status:** built on branch `task/052-rank-mix-paper-dedupe` (from task 051's branch, 2026-10-12); not yet measured on the mini set.
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

## Not done

- The task 051 mini-set recall thresholds (Focused 12.9%, Broad 17.8%, Broadest 22.3%)
  are not re-measured under the mix. The owner asked for no new eval runs for now. Run
  `scripts/evals/search/checks/production_recall.py` before merging to `dev`.
- The stratum a paper came from is not persisted on `source.acquired`; `query_origin`
  still says which call first returned it. `mix_screen_probe.py` replays the strata
  offline for the screening check instead.
- "Being critical of criticality in the brain" (a seminal review) sits at 103 under the
  mix on the avalanche question: it has few in-set citations in that pool. The seminal
  stratum reads in-set citations first; global citations only break ties.
