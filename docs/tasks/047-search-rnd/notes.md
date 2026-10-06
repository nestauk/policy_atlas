# Task 047: search R&D notes

Light-touch R&D, outside the full task cycle by owner decision (2026-10-06). The aim is
better search recall, and in particular more of the **seminal works** on a topic, which
user feedback and the 046 miss diagnosis both said the pipeline lacks. Each experiment
gets a dated entry: what was tried, the numbers, what we learned, what is next.

Measurement set: `retrieval-ground-truth-mini` (15 reviews; 8 with a labelled target:
the 4 hand-made reviews, 3 3ie gap-map rows and 1 YEF strand). Recall is the share of a
review's reference list found, scored on DOIs, as in every other row of
`scripts/evals/search/results/history.md`. Unlabelled lists (Campbell, SR4ALL) have a
recall ceiling near 50%, so read them against that, not against 100%.

## 2026-10-06 — Frequency snowball on the raw OpenAlex baseline

Script: `scripts/evals/search/measure/snowball_recall.py` (docstring has the method).
Outputs: `scripts/evals/search/results/snowball/<date>-s<seeds>-k<expand>/` with
`scores.csv` (one row per review, ranking and cap) and `candidates/<review>.csv` (the
ranked union with every signal, so misses can be read). Git-ignored.

### Method in one paragraph

Take the first N results of the plain OpenAlex keyword search as **seeds**. Every
OpenAlex record carries its reference list, so one batched lookup per 50 seeds gives all
the works the seeds cite, plus each seed's citation count. Count how many seeds cite
each work (**in-set citations**). Add the K most-cited new works, resolved to records
and filtered to the review's cutoff date. Rank the union, cut at a cap, score recall.
Cost: about (N + K) / 50 free OpenAlex requests per review, 3 to 5 seconds. No language
model.

### Ranking rules compared

| rule | order |
|---|---|
| raw | keyword results in the service's order, then snowball works by in-set citations (the control: at a cap below N it *is* the baseline) |
| inset | in-set citations, ties by global citations |
| specific | specificity = in-set citations / log10(global citations + 10). Damps works everyone cites (PRISMA, the I² statistic, Egger's test) in favour of works *this topic* cites |
| global | global citation count |
| interleave | one keyword result, one snowball work, alternating |

Reciprocal rank fusion of the keyword order and the specificity order was also tried and
dropped: a seed appears on both lists and a snowball work on one, so seeds crowded the
top (on the manual question, one-citation papers at ranks 12 and 13 above the field's
landmarks). Not worth a parameter.

### Results, seeds 200 and expand 200, 15 reviews

Mean recall; "seminal" is recall on the most-cited tenth of the reference list (floor
five), on the 8 labelled reviews.

| ranking | cap 50 | cap 100 | cap 200 | cap 400 (all) | seminal @200 | seminal @400 |
|---|---:|---:|---:|---:|---:|---:|
| raw (= baseline) | 1.6% | 2.5% | 3.1% | 12.6% | 6.6% | 44.2% |
| inset | 3.8% | 6.1% | 10.5% | 12.6% | 41.7% | 44.2% |
| **specific** | **4.4%** | **7.4%** | 10.3% | 12.6% | 41.7% | 44.2% |
| global | 2.1% | 3.9% | 9.4% | 12.6% | 44.2% | 44.2% |
| interleave | 3.3% | 5.0% | 7.9% | 12.6% | 29.6% | 44.2% |

For scale, the other single-call baselines on the same 15 reviews at cap 200 (history
rows `mini-q-2026-10-05`): OpenAlex raw 3.1%, Semantic Scholar snippet 7.9%, Consensus
8.9%; the pipeline's rapid depth at cap 50 is 2.2% and standard at cap 100 about 4.8%.
So the snowball on top of the **weakest** arm beats every other arm at the same cap, for
free, and the seminal-decile recall goes from 6.6% to about 42%.

Where the hits come from at cap 400: 2.4 per review from the seeds, 6.3 from the
snowball. The keyword results contribute little recall of their own on this set; the
snowball contributes most of it.

### Per review, cap 200 (raw -> specific)

| review | labelled | raw | specific | seminal raw -> specific |
|---|---|---:|---:|---|
| Tackling loneliness | yes | 7.1% | 29.8% | 12% -> 100% (n=8) |
| Parental leave and parents' mental health | yes | 5.8% | 15.4% | 0% -> 40% |
| Social care privatisation | yes | 0.0% | 14.3% | 0% -> 20% |
| Adverse childhood experiences, homeless youth | yes | 7.3% | 18.2% | 40% -> 80% |
| YEF: preventing involvement in violence | yes | 0.0% | 4.1% | 0% -> 40% |
| 3ie: civic and legal education | yes | 0.0% | 0.0% | 0% -> 0% |
| 3ie: nutrition-sensitive agriculture | yes | 0.0% | 2.9% | 0% -> 33% |
| 3ie: learning-to-earning | yes | 0.0% | 3.7% | 0% -> 20% |
| Sleep duration and obesity | no | 0.0% | 19.0% | |
| Intimate partner violence and health | no | 1.5% | 10.8% | |
| Residential energy efficiency | no | 6.7% | 10.4% | |
| Whole-school mental health interventions | no | 2.7% | 16.4% | |
| Health and social care, 80+ | no | 3.2% | 6.3% | |
| **Drug abuse risk and protective factors** | no | 8.6% | **1.4%** | |
| **Learning loss during school closures** | no | 3.7% | **1.9%** | |

Two reviews get worse under any citation ranking. The reasons are instructive:

- **Drug abuse.** The snowball's top works are the field's real landmarks: Hawkins,
  Catalano and Miller 1992 on risk and protective factors, Monitoring the Future, Jessor
  1977, Resnick 1997, Rutter 1987 on resilience. None is in this review's reference
  list, which is a list of included primary studies. The method found what a user would
  call seminal; the ground truth does not reward it. The 6 keyword hits had zero in-set
  citations and dropped below the cap. **The ground truth measures coverage of included
  studies, not seminality; the two can pull apart.**
- **Learning loss.** The seeds are COVID-era systematic reviews, so the most-cited
  references are PRISMA (five variants), the I² statistic and Egger's test, then
  COVID mental-health papers. Specificity damps PRISMA but cannot rescue the keyword
  hits, which are 2020 to 2022 primary studies that nothing in the seed set cites yet.
  **Citations point backwards in time; recent primary work needs the relevance signal**
  (keyword or semantic rank, and in production the screen). The snowball is an
  addition to those, not a replacement.

### Manual benchmark (no ground truth)

Question: "What is the relationship between avalanche criticality and edge of chaos
criticality in neural networks", cutoff today. Exports, one CSV per ranking, in
`scripts/evals/search/results/snowball/manual/what-is-the-relationship-between-avalanche-criticality-and-e/`.
Columns: rank, source (seed or snowball), inset, specificity, cited_by_count, year,
title, doi, openalex_id, raw_rank.

Under `specific`, the top of the list is Beggs and Plenz 2003 (neuronal avalanches),
Kinouchi and Copelli 2006 (optimal dynamic range at criticality), Shew et al. 2009,
Friedman et al. 2012, Bertschinger and Natschläger 2004 (edge of chaos in recurrent
networks), Chialvo 2010, Shew and Plenz 2013, Haldeman and Beggs 2005, then Levina 2007,
Muñoz 2018, Langton 1990 and the 2017 and 2019 reviews. The raw keyword top ten holds
mostly one-to-forty-citation papers. Owner to comment on what is missing or misplaced.

### Parameter sweep (seeds N, expand K)

Ranking `specific`, 15 reviews. "All" is the whole union, so it is the recall ceiling for
that pair; the candidate count is in brackets. Seminal is at "all", 8 labelled reviews.

| N seeds | K expand | cap 100 | cap 200 | cap 400 | all | seminal |
|---:|---:|---:|---:|---:|---|---:|
| 100 | 100 | 5.9% | 7.6% | 7.6% | 7.6% (197) | 25.9% |
| 100 | 200 | 6.5% | 9.0% | 10.5% | 10.5% (293) | 32.1% |
| 200 | 100 | 6.3% | 8.1% | 8.4% | 8.4% (297) | 29.6% |
| 200 | 200 | 7.4% | 10.3% | 12.6% | 12.6% (395) | 44.2% |
| 200 | 500 | 6.4% | **10.6%** | 14.5% | 17.1% (684) | 44.2% |
| 500 | 200 | 6.2% | 9.1% | 11.1% | 11.6% (693) | 36.7% |
| 500 | 500 | 6.5% | 8.8% | 14.6% | **18.0%** (983) | 49.2% |

Three readings:

- **The expansion K does the work.** At 200 seeds, going from 100 to 200 to 500 new
  works raises the ceiling from 8.4% to 12.6% to 17.1%. The snowball tail keeps paying.
- **More seeds dilute the count.** At a fixed cap of 200, 500 seeds score below 200
  seeds for the same K (9.1% against 10.3%; 8.8% against 10.6%). Seeds 201 to 500 of a
  weak keyword ranking are off topic, and their references add noise to the frequency
  count. Seed quality beats seed quantity, which argues for **screened** seeds in
  production, where the screen is already paid for.
- **Cap is the cost.** Every candidate is screened downstream at about a cent each, so
  the useful comparison is at a fixed cap. There, 200 seeds and 500 new works is the
  best pair tried, and the gain from 200 to 500 new works is small at cap 200 (10.3% to
  10.6%) but large at cap 400 (12.6% to 14.5%).

### Decisions and caveats

- Fifteen reviews, one run, raw unscreened seeds. The production seeds would be the
  screened-in set, which should give cleaner counts than this test.
- Citation counts and reference lists are read live from OpenAlex and cached; they move
  over time, so a rerun in a year will not reproduce these numbers exactly. The cache
  files carry `fetched_at`.
- Seminal-decile recall is reported for labelled reviews only, because in an unlabelled
  list the most-cited tenth is mostly review-methods papers (see the 046 citation probe).
- `--expand` returns slightly fewer than K works because references published after the
  cutoff are dropped at resolve time (189 to 198 of 200 here).

### Next

1. Owner reads the manual export and comments.
2. Query generation on top of the snowball (the next R&D step the owner named).
3. If promoted to production: replace the five-seed snowball arm with this counting over
   the screened-in set, at standard depth as well as deep; add seminal-decile recall to
   the eval scores; and decide the ranking rule the Sources view uses (specificity is the
   current pick).

## 2026-10-06 — Generated queries as the seed source

Same script, `--queries shared`. Instead of one plain query, the seeds come from the
pipeline's own rapid-search query generation, run through the backend's class
(`OpenAISearchGenerationBackend`, prompt file `search_queries_system_v3.txt`, model
`gpt-5.4-mini`): five keyword queries per intent, each sent with its systematic-review
and randomised-trial variants as rapid does, 15 OpenAlex calls, one page of 200 each,
merged round-robin like acquire's rank-interleave. Only the OpenAlex side is used;
Overton is not part of this experiment. Generated queries are cached per intent and
prompt hash, so a prompt edit (pass `--prompt-file` with an edited copy; the committed,
hash-pinned prompt files are never touched) produces a new label and a new cache entry.
Per-query results and ground-truth hits are written to `queries.csv` in the run folder,
so a prompt change can be read query by query.

Cost: 15 generation calls, about 11,000 tokens in total; 225 free OpenAlex calls.

### Results, seeds 200 and expand 200, 15 reviews

| seed source | ranking | cap 50 | cap 100 | cap 200 | cap 400 (all) | seminal @200 |
|---|---|---:|---:|---:|---:|---:|
| one raw query | raw (= baseline) | 1.6% | 2.5% | 3.1% | 12.6% | 6.6% |
| one raw query | specific | 4.4% | 7.4% | 10.3% | 12.6% | 41.7% |
| generated (shared) | raw (= seeds only) | 3.2% | 4.5% | 7.0% | 18.1% | 18.3% |
| generated (shared) | specific | **7.6%** | **11.3%** | **15.3%** | **18.1%** | 45.1% |

Three readings:

- **Generated queries double the seed recall on their own** (3.1% to 7.0% at cap 200),
  which matches what the pipeline's rapid depth gains over the raw baseline.
- **Better seeds make a better snowball.** With the same N and K, the snowball on
  generated seeds reaches 15.3% at cap 200 against 10.3% on raw seeds, and the ceiling
  rises from 12.6% to 18.1% at the same candidate count. Seed quality, again.
- **At cap 200 this is the best number on the mini set so far**: the pipeline's deep
  depth measured 15.3% on the four hand-made reviews in September, and here a
  single-round, screen-free configuration reaches the same on fifteen, for about a cent
  of language-model spend.

Per review the picture is mixed in the same way as before. Nine reviews improve, some
a lot (learning loss 1.9% to 29.6%, sleep and obesity 19.0% to 32.1%, YEF violence 4.1%
to 14.3%). Loneliness drops from 29.8% to 21.4%: the raw query was already a very good
seed for that review and five diverse queries dilute the citation count. Drug abuse goes
to 0%, for the reason recorded above (the ground truth does not contain the landmarks).

### A transport detail worth keeping

The generated queries contain wildcards (`infant*`) even though the prompt forbids them,
and OpenAlex answers 400 to a wildcard. The pipeline strips them in its transport layer
(`search_live.sanitize_openalex_query`); the first version of this experiment did not,
so 9 of 225 calls failed. The script now reuses the pipeline's sanitiser, and a failed
page is never served from the cache, so a rerun fetches it again. One further 400 was
transient: the same query answered 200 on replay and the rerun reports 0 failed calls
(specific at cap 200 then reads 15.2%, within rounding of the table).

Manual question: the five generated queries and the new ranked tables are in the same
manual folder, files prefixed `2026-10-06-shared-c6e320-s200-k200-`. The top of the list
is close to the raw-seed version, with Beggs and Plenz 2003 first; in-set counts are
lower (45 against 105 for the top paper) because the seeds are spread over five queries,
and the two self-organised criticality papers of Bak (1987, 1988) rise into the top 25.

**Per-provider prompt: stopped** (owner, 2026-10-06). Its boolean queries contained
wildcards in most calls, so the first run lost 40 of 225 calls to HTTP 400 before the
sanitiser was wired in; the run folder is unreliable and is not reported. Focus is the
production (shared) prompt. An editable copy for experiments is
`scripts/evals/search/prompts/search_queries_exp_a.txt`, byte-identical to the committed
`search_queries_system_v3.txt` at the start, run with `--queries shared --prompt-file`.

## 2026-10-06 — Are the generated keyword queries good search practice?

Read against how a systematic-review information specialist builds a search: concept
blocks (population, exposure or intervention, setting), each block a group of synonyms
joined by OR, blocks joined by AND, both spellings, no outcome words, no words that
describe a document type, no date or language filters in the query text.

The 75 queries the production prompt (`search_queries_system_v3.txt`) wrote for the
mini set are in `results/snowball/2026-10-06-shared-c6e320-s200-k200/queries.csv`.
Findings:

1. **Document-type words copied from the title.** "loneliness evidence review",
   "loneliness main report", "COVID-19 learning evidence systematic review meta-analysis".
   These describe the review, not the studies it includes. One scored well by accident.
2. **No synonym blocks.** Most queries are a bare noun phrase; only 9 of 75 use OR, and
   usually for a single pair. A specialist would write (loneliness OR "social isolation")
   AND (older OR elderly OR "later life") and so on. The five queries vary the words but
   each one is narrow, so the set is five narrow probes rather than one wide net.
3. **AND and OR mixed without brackets.** "sleep duration AND BMI AND infant OR child OR
   adolescent" is read by OpenAlex as a loose OR. It scored 17 hits by that accident.
4. **Generic outcome words.** "intervention effectiveness", "health outcomes",
   "healthcare utilization", "determinants" scored zero or one. The pipeline's older
   per-provider prompt forbids these words explicitly; the production prompt does not.
5. **Wildcards despite the rule** (`child*`, `infant*`) in 4 of 75. The transport strips
   them, so the cost is a weaker stem, not a failure.
6. **Three or more AND clauses mostly score zero.** Every one of the YEF violence queries
   and most 3ie queries chain three concepts with AND and return nothing useful; the
   short two-concept queries are the ones that hit.
7. **The best queries are two-concept noun phrases on population and exposure:**
   "school closures learning loss", "maternity leave OR paternity leave mental health",
   "residential energy efficiency interventions", "whole-school intervention
   health-promoting schools framework".

Verdict: the production prompt produces reasonable *ad hoc* searches, not systematic-review
searches. It would be marked down by a specialist on points 1, 2 and 4. The owner's
earlier finding that prompt wording moves query quality a lot is consistent with this.

**Comparison under way** (`prompts/openalex_boolean_exp_b.txt` is the owner's prompt,
which asks for one professionally structured boolean query and forbids outcome words; it
runs through the pipeline's per-provider path, which calls the prompt five times):
per-provider with the committed v2 prompt; the owner's prompt on gpt-5.4-mini,
gpt-5.6-luna and gpt-5.6-terra; and the production prompt on gpt-5.6-luna and
gpt-5.6-terra. Results follow in the next entry.

### Finding for the pipeline: OpenAlex refuses searches over 1,500 characters

Seen in the gpt-5.6-luna run of the owner's boolean prompt (21 of 213 calls failed with
HTTP 400). OpenAlex's message: "Your search is too long (1558 characters; the limit is
1500)". The pipeline's `QUERY_MAX_CHARS` is 2,000, derived from the URL length limit, so
a generated query between 1,500 and 2,000 characters passes `validated_queries` and
fails at the service; the SR and RCT variants add about 110 to 130 characters on top, so
the effective limit for a generated query is about 1,370. Not a problem for the
production prompt (its queries are short) but it would be for any boolean-style prompt.
Suggested fix, not made here (backend change, needs approval): lower `QUERY_MAX_CHARS`
to about 1,300, or have the OpenAlex transport skip the variant when the composed query
would exceed 1,500. Recorded for `docs/deferred.md`.

## 2026-10-06 — Prompt and model comparison for the seed queries

Full table and reading in `scripts/evals/search/EXPERIMENTS.md` § Results so far. In one
line: the production prompt on gpt-5.4-mini remains the best seed source (15.2% / 14.1%
with the snowball, two runs); the systematic-review-style prompts (synonym blocks, roles,
code-composed concept blocks) lowered it by three to six points, because OpenAlex caps a
query at 200 results and a wide net's top 200 are generic; stronger models help a boolean
prompt's seeds but not the production prompt's, and land inside the noise once the
snowball is added. Lay-register vocabulary scored near zero everywhere. Run folders:
`shared-c6e320` (production, r1 and r2), `shared-db9280` (exp_d), `shared-f8180a`
(exp_e), `concepts-732ac8` (exp_f), `per-provider-fdc90d` (exp_c, three models),
`shared-c6e320-gpt-5.6-*` (production on luna and terra). Queued: concept blocks and
the improved prompts on gpt-5.6-luna; reasoning effort none and low on the production
prompt (gpt-5.4-mini rejects `minimal`).

**Luna set (same day, later).** Concept blocks 10.9%, roles prompt 12.6%, and the
improved prompt without roles **16.3% with a 20.1% ceiling**, the best single run so far,
on gpt-5.6-luna; the same prompt on gpt-5.4-mini had scored 11.7%. Prompt and model
interact: the smaller model cannot follow the synonym-block instructions, the larger one
can. One run, needs a repeat. Two "minimal reasoning" runs in this set were invalid (the
effort was missing from the generated-query cache key, so they reused cached queries);
their artifacts were deleted, the key fixed, and the reasoning runs relaunched.

**Reasoning effort (same day, last set).** No effect on recall; no effect on latency for
gpt-5.4-mini (1.4 to 1.7 s per question at any effort); on gpt-5.6-luna low effort saved
2.5 s and lost one point. The exp_d-on-luna "best" did not hold at low effort (15.3%), so
it is the top of its noise rather than a real gain. **Conclusion of the query-generation
work:** fourteen configurations land between 14% and 16% with the snowball at cap 200;
the production prompt on gpt-5.4-mini is as good as any and the cheapest. Stop here on
prompts; next levers are the snowball itself (second hop, screened seeds) and the
ground-truth labelling. Table in `EXPERIMENTS.md`.

## 2026-10-06 — Miss analysis and hypotheses

Bucketed all 941 ground-truth papers against the best configuration; table and the five
ranked hypotheses are in `EXPERIMENTS.md` § 6. Headlines: 26% of the ground truth is
cited by a seed but falls below the 200 cut (mostly single citations); 28% cites a seed
and is reachable by forward citation chasing; a third has no graph path from the seeds.
Zero-cost test: weighting the count by seed type (review seeds, keyword rank, seed
in-set citations) does not beat the plain count, so review-first harvesting is not a
free gain. Analysis script: scratchpad `miss_analysis.py` (throwaway; the production
prompt's queries were regenerated for 11 reviews because the generated-query cache key
changed mid-day when the model was added to it, so the analysis is on a fresh sample of
the same configuration, not the exact r1 run).

Background sources (research agent, 2026-10-06): Greenhalgh & Peacock 2005
(https://pubmed.ncbi.nlm.nih.gov/21833989/ and the ResearchGate copy); Horsley et al.,
Cochrane review of checking reference lists (https://pmc.ncbi.nlm.nih.gov/articles/PMC7006380/);
Hinde & Spackman 2015 (https://link.springer.com/article/10.1007/s40273-014-0205-3);
Briscoe 2020 (https://onlinelibrary.wiley.com/doi/10.1002/jrsm.1355); Wohlin 2022
(https://onlinelibrary.wiley.com/doi/full/10.1002/jrsm.1563); CoCites
(https://pmc.ncbi.nlm.nih.gov/articles/PMC4048585/); Sahu et al. 2026
(https://arxiv.org/abs/2605.29234); PaSa (https://arxiv.org/html/2501.10120v2); LitLLM
(https://arxiv.org/abs/2412.15249); Inciteful / Connected Papers
(https://www.connectedpapers.com/about); OpenAlex docs on citations, semantic search,
corpus and pricing (https://help.openalex.org/).

## 2026-10-06 — Forward citation chasing

Built into `snowball_recall.py` (`--forward N --forward-top 20 --forward-pages 10`,
optional `--forward-search`, `--forward-sort`, `--forward-max-cites`). Results and the
ranking study are in `EXPERIMENTS.md` § 7. Headline: snowball plus forward on the
production prompt with gpt-5.4-mini reaches 16.3% at cap 200, 21.1% at 400 and a 22.8%
ceiling, against 13.6% / 16.8% / 16.8% for the snowball alone on the same seeds. Ten free
OpenAlex calls. Weighted coupling (cited seeds weighted by their in-set citations) ranks
the citing papers; plain coupling enters the specificity score, weighted as tiebreak,
because the weighted value on the raw scale floods the top 200. Adding the question
words as a search filter on citing papers, sorting the fetch by citation count, and
chasing more than 20 seeds all did not help. Two mistakes caught on the way: a first
"forward-top" run silently used every seed because the knob was not passed through the
cached branch, and a local harness compared mini seeds against luna's official run
because it never set the model; both are fixed, and the mini result was then confirmed
on the official path. Run folders end in `-f200p10c300t20`.

## 2026-10-06 — Longer tail with re-ranking, and topic fence (hypotheses 2 and 4)

Script `measure/pool_rerank.py`; results in `EXPERIMENTS.md` § 8. Pool of about 1,900
candidates (200 seeds, 800 backward, 200 forward, 700 topic-fenced) holds 35.5% of the
ground truth. Best ranking rule is the graph specificity multiplied by the normalised
embedding similarity: 17.9% at cap 200, 22.3% at 400, 26.0% at 600 (graph alone 15.7 /
20.9 / 24.3; embedding alone 12.1 / 15.9 / 20.5). Re-ranking a graph shortlist by
embedding after the cut does nothing; Adamic-Adar weighting does nothing; the topic
fence adds 700 candidates for 3.8% of reachable ground truth and about one hit per
review, dropped. Luna variant (`exp_d` prompt): pool ceiling 40.4%; graph 17.5 / 24.2 / 27.1; product 19.1 / 25.7 / 29.1; fusion best at 600 (29.7%). Run
folder: `results/snowball/pool/2026-10-06-shared-c6e320-s200-k800-f200`.

## 2026-10-06 — Semantic seeds (hypothesis 3)

`--queries semantic` and `--queries shared+semantic` in `snowball_recall.py`: OpenAlex
`search.semantic`, eight texts per review (question, two paraphrases, five queries),
50 results each, year fence server-side and the exact cutoff applied locally (the
endpoint rejects date filters; first attempt failed on that and on the one-per-second
rate limit, both handled). Results in `EXPERIMENTS.md` § 9. Keyword plus semantic seeds
with snowball and forward on mini: 21.9% at cap 200, 28.1% at 400, 30.6% ceiling,
against 16.3 / 21.1 / 22.8 for keyword seeds alone; the two routes overlap little (7.1
ground-truth seeds per review together against 4.1 and 5.6 apart). Under a cent per
search. Luna `exp_d` with combined seeds: 16.8 / 24.7 / 27.2, below keyword-only at cap 200 (18.5); suspected cause is sending boolean-block queries to semantic search; `--semantic-texts intent` variant running. Run folders:
`shared+semantic-c6e320-s200-k200-f200p10c300t20` and `semantic-c6e320-...`.
