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
  graph-found papers that are on topic (the Dutch healthy-checkout experiments 565 →
  160, "Erythropoietin: a multimodal neuroprotective agent" 257 → 91, "Being critical of
  criticality" 110 → 82) while the direct matches stay at 1 and the top 100 keeps 41%
  to 49% of its papers from two or more queries. An additive version outside the
  fusion (`mix_c` in the probe) pulled harder toward the graph (about half of its top
  100 never returned by any query), so it was not adopted. These ranks are from the
  regenerated results with the production novelty year (2021); the first pass of the
  experiment used 2020, which put the 2020 checkout paper in the novel stratum. Columns `mix_q` (no coupling), `mix_f1`
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
(same generated queries). Since the review of 2026-10-12 the derivation reads each
document's rank in its backend's pool from the `source.acquired` event (`pool_rank`,
counting every pool entry, duplicates and unusable records included), so "rank within
the cap" is exactly what a run at that scope would have kept. The 12 October figures
below were computed before that fix, from positions among persisted documents only: a
duplicate or unusable record inside the cut did not take its slot, so the derived
Focused and Broad figures may be slightly high (by at most the number of such records
in the first 100 or 200 ranks of each review). The Broadest figures are measured
directly and unaffected. The next run writes the exact figures.

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

## Review findings (2026-10-12, Codex adversarial lane, read-only)

Run on the task 052 delta (commits `472d6e0` to `d1428f7`) at the owner's request, with
the Claude author adjudicating in the build conversation (the task-cycle skill asks for a
fresh conversation; the owner chose otherwise, as in task 051). Verify gate green before
and after the fixes.

| # | severity | finding | decision |
|---|---|---|---|
| 1 | MAJOR | `pool.dedupe_papers` merged two different titled papers when both had no author names (both keys became `title|`). | **Adopted.** `paper_key` now falls back to the work id when the title or the author list is empty, so such records are never merged. Test extended. |
| 2 | MAJOR | `engine.recall_at_smaller_caps` counted positions among persisted documents, so any non-persisted pool entry inside the cut (unusable record, task-level duplicate) let a lower-ranked document into the simulated cap. The notes' caveat named only the duplicate case. | **Adopted at the root.** `acquire` now writes `pool_rank` (1-based, every entry counted) on each `source.acquired` event; the engine reads that rank, so the derivation is exact. Tests pin the rank in `test_acquire_pools.py` and the payload keys in `test_acquire.py`. The 12 October derived figures carry the old caveat (see above). |
| 3 | MINOR | `rank_mix_probe.py` fixed novelty at 2020 while production uses today's year minus five (2021 in 2026), so the committed evidence could describe a different cut from the shipped code. | **Adopted.** The probe derives the year from `pool.NOVEL_YEARS`; the three result files were regenerated from the cached pools. |
| 4 | NIT | ADR 0038 said every cut "holds all three kinds", stronger than the code guarantees when a stratum is empty. | **Adopted.** Wording qualified in the ADR and the `mix_strata` docstring; a unit test covers the empty-stratum case. |

Checked and found sound by the lane: fusion ignores records without an OpenAlex id;
the coupling order is genuinely fused three times; the round-robin places every
candidate exactly once; the experiment scripts persist no abstracts or credentials.
Named as unreviewed by the lane and checked by the author: the final order is
deterministic across processes (every sort key is a number or a stable tuple, and the
fusion sums floats in list order); records with no DOI cannot count toward recall at
any scope, derived or measured, which is the existing rule of the eval. The lane noted
that backward-found papers have zero weighted coupling by construction (their
reference lists are not loaded), so they enter the relevant stratum only through
query hits; they remain eligible through the seminal stratum and the specificity
tail. Recorded, not changed.
