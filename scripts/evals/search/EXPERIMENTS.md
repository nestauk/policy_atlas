# Search experiments

This file records the research and development experiments on the search step. Each
experiment tries a change to how we find papers and measures it against the ground
truth. The experiments do not upload to Langfuse. They write their scores and candidate
tables under `results/` (git-ignored). The dated log of runs and decisions is in
`docs/tasks/047-search-rnd/notes.md`. This file holds the method, how to run it, and the
key results.

The measured baselines (`measure/baseline_recall.py`) and the production runs
(`measure/production_recall.py`) are described in the [README](README.md).

## Key results (as of 2026-10-06)

All numbers are on the `retrieval-ground-truth-mini` dataset: 15 reviews, each with a
list of the papers it cites. **Recall** is the share of that list we found. Unless stated,
we keep **200 candidates** per review, which is what the standard search depth screens.
Two runs of the same configuration differ by about one point, so a difference under one
point is not a difference.

### 1. The plain OpenAlex search misses most papers, and not because of the cap

| plain search, one query | recall |
|---|---:|
| first 200 results | 3.1% |
| first 1,000 results | 5.1% |

The missed papers are not sitting further down the list. They are never returned at all.
Every ground-truth paper exists in OpenAlex, so the problem is how we search, not what
OpenAlex holds.

### 2. Snowballing through reference lists is the big lever

The method: take the 200 search results as **seeds**. Read the reference list of each
seed (OpenAlex returns it with the record). Count how many seeds cite each paper. Add the
200 most-cited papers. Rank the combined set and keep the first 200.

| seeds | seeds alone | with snowball | ceiling |
|---|---:|---:|---:|
| one plain query | 3.1% | 10.3% | 12.6% |
| the production prompt's five queries | 7.0% | 15.2% | 18.1% |

The snowball triples recall from a plain query and doubles it from generated queries. It
costs about eight free OpenAlex calls and no language model. It finds the important
older papers: recall on the most-cited tenth of each review's list went from 7% to 42%.
On a question with no ground truth ("avalanche criticality and edge of chaos in neural
networks"), the top of the ranked list is the field's canonical reading list.

Design choices that were tested and settled:

- **Add about 150 to 200 snowball papers**, or those cited by at least 4 seeds, capped
  at 200. The hit rate per 100 candidates falls from 5.7 in the first 50 to 0.9 past 300.
- **Do not add more seeds.** Going from 200 to 500 seeds lowered recall at a fixed cap.
  Search results past 200 are mostly off topic and add noise to the citation count. In
  production the seeds should be the papers that passed screening.
- **Rank by specificity**: in-set citations divided by log10 of global citations. This
  pushes down papers that everyone cites, such as PRISMA and the I² statistic, and keeps
  papers that this topic cites. Ranking by global citations alone found nothing new.
- **Keep the first 50 keyword results in their own order** as a relevance reserve.
  Citations only point to older papers, so a recent study has no in-set citations yet
  and only the keyword rank can keep it.
- Two reviews got worse under any citation ranking. One because its reference list is a
  list of included primary studies and does not contain the field's landmark papers,
  which the snowball found. One because its hits were 2020 to 2022 studies that nothing
  cites yet. The ground truth measures coverage of included studies, not importance.

### 3. Query generation: fourteen configurations, all within two points

The seeds come from five keyword queries that a language model writes from the research
question, each sent to OpenAlex as written and with a systematic-review variant and a
randomised-trial variant, as the production rapid search does. We compared the production
prompt, a boolean prompt from the owner, two "improved" prompts, a version where the
model lists concepts and the code builds the queries, three models, and four reasoning
settings.

| seed source | model | seeds alone | with snowball |
|---|---|---:|---:|
| production prompt (`search_queries_system_v3`) | gpt-5.4-mini, two runs | 7.0% / 5.9% | **15.2% / 14.1%** |
| production prompt | gpt-5.6-luna / gpt-5.6-terra | 5.4% / 5.8% | 14.3% / 14.7% |
| owner's boolean prompt plus no-wildcard line | mini / luna / terra | 6.5% / 8.9% / 9.0% | 14.8% / 15.1% / 14.1% |
| improved prompt (synonym blocks, two concepts, word bans) | mini / luna | 6.0% / 6.8% | 11.7% / 16.3% |
| improved prompt with five named query roles | mini / luna | 5.9% / 6.4% | 11.6% / 12.6% |
| concept blocks from the model, queries built in code | mini / luna | 4.2% / 4.5% | 9.1% / 10.9% |
| production prompt, reasoning effort none / low | mini | 6.0% / 6.6% | 15.1% / 15.3% |
| improved prompt, reasoning effort low | luna | 6.1% | 15.3% |

Lessons:

- **Short, specific queries beat wide synonym nets here.** This is the opposite of
  systematic-review practice, for a reason: OpenAlex returns at most 200 results per
  query, ranked by relevance. A wide net matches a huge pool of papers, and its first 200
  are the most generic ones. A short specific phrase matches a small pool, and its first
  200 are the topic's studies. A reviewer reads everything a query returns; we read the
  first 200. The improved prompts produced more queries with zero hits than the
  production prompt (36 and 39 of 75, against 21).
- **Lay vocabulary is useless on an academic index.** The "alternative vocabulary" role
  scored 14 hits across 15 reviews, the lowest of any query position. Abstracts use the
  technical term.
- **Bigger models give better seeds with a boolean prompt, but it does not carry
  through.** Their boolean queries run to 800 characters, and a tenth to a fifth of the
  calls fail OpenAlex's 1,500-character limit. Once the snowball is added, every model
  lands in the same band.
- **The 16.3% for the improved prompt on gpt-5.6-luna is not a reliable gain.** It is one
  run, it fell to 15.3% at low reasoning effort, and it costs 4 to 6 seconds more per
  search.
- **Reasoning effort changes nothing.** Recall is the same at none, low and default. On
  gpt-5.4-mini the default call already takes 1.4 seconds, so there is no latency to
  save. Writing search queries is a vocabulary task, not a reasoning task.

**Cost per search of the generation call.** List prices on 2026-10-06 (OpenAI cut Terra
and Luna on 2026-07-30), per million tokens: gpt-5.4-mini $0.75 in / $4.50 out;
gpt-5.6-luna $0.20 / $1.20; gpt-5.6-terra $2.00 / $12.00. Tokens are the medians measured
in these runs (one call per search; the per-provider path makes seven).

| configuration | tokens per search | cost per search | time | with snowball |
|---|---:|---:|---:|---:|
| production prompt, gpt-5.4-mini | 740 | $0.0010 | 1.4 s | 15.2% / 14.1% |
| production prompt, gpt-5.6-luna | 810 | $0.0004 | 3.0 s | 14.3% |
| production prompt, gpt-5.6-terra | 750 | $0.0028 | 2.7 s | 14.7% |
| improved prompt, gpt-5.6-luna | 1,440 | $0.0008 | 7.4 s | 16.3% (15.3% at low effort) |
| per-provider boolean prompt, gpt-5.4-mini (7 calls) | 3,300 | $0.0055 | ~30 s | 13.6% to 14.8% |
| per-provider boolean prompt, gpt-5.6-terra (7 calls) | 5,100 | $0.025 | ~65 s | 14.1% |

Every row is under three cents. Screening the 200 candidates costs about $1 to $2 per
search, so the generation model is not where the money is. On cost alone gpt-5.6-luna is
the cheapest option and matches gpt-5.4-mini within the noise, at about double the
generation time. The choice between them is latency, not money.

**All gpt-5.6-luna results in one place.** The pipeline will move to luna, so here is
every luna configuration measured, 200 seeds, 200 snowball, cap 200 unless stated.
Each row is one run; the noise floor is about one point.

| prompt | reasoning | forward stage | seeds only | with snowball | cap 400 | ceiling | generation / question | failed calls |
|---|---|---|---:|---:|---:|---:|---:|---:|
| production (`search_queries_system_v3`) | default | no | 5.4% | 14.3% | 16.6% | 16.6% | 3.3 s | 1 |
| production | default | yes | 5.4% | 14.4% | 19.2% | 21.0% | 3.3 s | 0 |
| owner's boolean prompt + no-wildcard line (`exp_c`, 7 calls) | default | no | 8.9% | 15.1% | - | - | - | 21 (over 1,500 chars) |
| improved production prompt, no roles (`exp_d`) | default | no | 6.8% | 16.3% | 18.5% | 20.1% | 7.9 s | 0 |
| improved production prompt, no roles (`exp_d`) | low | no | 6.1% | 15.3% | 17.4% | 18.8% | 5.4 s | 0 |
| **improved production prompt, no roles (`exp_d`)** | default | **yes** | 6.8% | **18.5%** | **23.7%** | **26.0%** | 7.9 s | 0 |
| improved prompt with five roles (`exp_e`) | default | no | 6.4% | 12.6% | 14.9% | 16.3% | 11.1 s | 0 |
| concept blocks composed in code (`exp_f`) | default | no | 4.5% | 10.9% | 12.6% | 13.7% | 4.2 s | 0 |

What the luna rows say:

- With the production prompt, luna's seeds are weaker than mini's (5.4% against 7.0% and
  5.9%), and everything downstream inherits that. Luna writes longer queries with more
  AND clauses from the same prompt (its queries for the manual question all had three
  AND-joined concepts), which is the shape that scored zero most often in the query
  analysis.
- With the synonym-block prompt (`exp_d`) the picture flips: luna's seeds improve to
  6.8% and the snowball on them reaches 16.3%, where mini on the same prompt managed
  only 11.7%. Luna can carry the structured instructions; mini cannot.
- Adding the forward stage to that pair gives the best configuration measured, 18.5% at
  cap 200 and 26.0% at the ceiling. One run; a repeat is needed before it is believed
  to the point.
- The roles prompt and the concept blocks do not help luna either. Low reasoning effort
  costs about one point and saves 2.5 seconds.
- Cost per search for generation on luna at $0.20 / $1.20 per million tokens: production
  prompt about $0.0004, `exp_d` prompt about $0.0008. Negligible against screening.

**Luna recommendation.** When the pipeline moves to luna, change the query prompt to
`exp_d` at the same time: on luna it is worth about two points at cap 200 over the
production prompt (16.3% against 14.3%), and with the forward stage about four (18.5%
against 14.4%). Do not carry `exp_d` to mini, where it loses four points. Keep default
reasoning unless the extra 2.5 seconds matter.

Conclusion: keep the production prompt on gpt-5.4-mini. Prompt wording is a one-point
lever inside the noise on mini, but on luna the prompt and model interact and `exp_d`
is the right prompt. The snowball is a five-point lever and forward chasing another
two to five. If generation cost ever
mattered, gpt-5.6-luna on the production prompt is the same recall for 40% of the price.

### 4. Two findings for the pipeline and the eval

- **OpenAlex refuses a search over 1,500 characters.** The pipeline's query cap
  (`QUERY_MAX_CHARS`) is 2,000. The production prompt's queries are short, so nothing
  breaks today, but any boolean-style prompt would send queries that fail. Recorded in
  the task notes for `docs/deferred.md`.
- **The ground truth limits what these experiments can show.** Nine of the 15 reviews
  are unlabelled reference lists (Campbell and SR4ALL). About half of each list is
  background and methods citations that no topic search can find, so recall on those
  rows has a ceiling near 50%. In those lists the most-cited references are methods
  papers, so a "seminal works" metric must use only the labelled reviews. The spread
  between prompts is smaller than the spread the labelling would remove.

### 5. Interim conclusion: the recommended configuration (2026-10-06)

1. Generate five keyword queries with the production prompt
   (`search_queries_system_v3`). Keep gpt-5.4-mini for now. gpt-5.6-luna gives the same
   recall within the noise at 40% of the price but takes about 1.5 seconds longer per
   call, and switching the model needs its own check across the pipeline's other
   prompts. The prompt wording matters in one direction only: the reasonable prompts
   (production, the owner's boolean prompt with the no-wildcard line, the improved prompt
   on luna) all land between 14% and 16%; the roles prompt, the concept blocks and any
   synonym-heavy prompt on mini lose three to six points. So "keep the production
   prompt", not "any prompt will do".
2. Send each query with its systematic-review and randomised-trial variants (15
   keyword calls), **and** send the question, the two paraphrases and the five queries
   to OpenAlex semantic search (8 calls, section 9). Merge round-robin, keep the first
   200 as seeds. The two routes find different papers; together they lift the whole
   configuration from 16.3% to 21.9% at cap 200. In production, use the screened-in set
   as seeds for the later stages; seed quality matters more than seed count.
3. Read the seeds' reference lists, count how many seeds cite each paper, and add the
   150 to 200 most-cited new papers, or those cited by at least 4 seeds, capped at 200.
4. **Forward chasing (added 2026-10-06, section 7).** Take the 20 seeds with the most
   in-set citations, fetch the papers that cite them (10 pages), score each by how many
   seeds it cites, add the top 200. This reaches the recent work the snowball cannot.
5. Rank the union by specificity: (in-set citations + coupling) / log10 of global
   citations, weighted coupling as tiebreak, with the first 50 keyword results held in
   their own order as a relevance reserve.
6. Screen the resulting 200 as normal.

This configuration measures **21.9% recall at 200 candidates and 28.1% at 400** on the
mini set with gpt-5.4-mini, against 3.1% for the plain search and about 5% for the
current rapid depth, for one generation call and about 42 OpenAlex calls, about
$0.011 as charged to our account, per search. The luna version with the `exp_d` prompt is being measured. The
remaining gains are in the ground truth and in affording a larger screened pool.

### 6. Where the misses are, and hypotheses for the next step (2026-10-06)

Every ground-truth paper of the 15 reviews (941 DOIs) was placed in one bucket against the
best configuration (production prompt, gpt-5.4-mini, 200 seeds, 200 snowball).

| bucket | papers | share |
|---|---:|---:|
| A. Found among the 200 seeds | 61 | 6.5% |
| B. Found among the 200 snowball papers | 110 | 11.7% |
| C. Cited by at least one seed, but ranked below the 200 cut | 245 | 26.0% |
| D. Cited by no seed | 521 | 55.4% |
| D1. ... but itself cites at least one seed | 139 | 14.8% |
| D2. ... cited by one of the 200 snowball papers (second hop) | 28 | 3.0% |
| D3. ... shares an author with a seed | 83 | 8.8% |
| D4. ... has the same primary topic as the seeds' top three | 213 | 22.6% |
| D5. ... published within two years of the cutoff | 127 | 13.5% |
| D6. ... no graph path at all from this seed set (none of D1 to D3) | 319 | 33.9% |
| Not in OpenAlex by DOI | 4 | 0.4% |

Other facts from the same analysis:

- Of the bucket-C misses, 64% are cited by exactly one seed and only 8% by three or
  more. The snowball's tail is long and weakly ranked: each review has 7,000 to 16,000
  distinct references, most cited once.
- Misses are newer than hits: median year 2016 against 2013. Citations point backwards,
  so the snowball cannot reach recent work.
- Counting A to D1, 262 ground-truth papers that are not seeds cite at least one seed.
  That is 28% of the ground truth, more than the whole set we find today, and it is
  reachable by following citations forward.
- About a third of the ground truth (D6) has no graph link to this seed set at all. No
  citation method from these seeds can reach it; only better seeds or more candidates can.

**Tested at zero cost and found not to help.** Weighting the reference count by the kind
of seed does not improve the top-200 expansion: review-type seeds doubled or tripled,
review seeds only, seeds weighted by their own in-set citations, or by keyword rank, all
score the same as or below the plain count (110 ground-truth papers in the top 200; the
best variant 109; review seeds only 78). Review-type seeds hold 1.7 times as many
ground-truth references per seed as other seeds, but only because they have longer
reference lists; the density per reference is the same (8.0 against 7.4 per 1,000). The
"pearl growing" idea of harvesting reviews first is therefore not a free gain here, and it
carries a leak risk (the target review's own protocol or update can appear as a seed).

**Hypotheses, ranked by expected gain per unit of cost.** All are free or nearly free on
OpenAlex; none adds more than one light language-model call.

1. **Forward citation chasing with bibliographic coupling.** Fetch the papers that cite
   the seeds (OpenAlex `cites:` filter accepts up to 100 seed ids joined by OR). Rank
   them by how many seeds they cite. Add the top 100 to 200. Why: 262 ground-truth
   papers (28%) cite a seed, and forward citations reach recent work, which is exactly
   the snowball's blind spot. The CoCites tool reports a median recall of 75% from two
   seed papers using co-citation plus forward coupling in health reviews. Cost: the
   seeds with 300 citations or fewer (about 180 of 200) have about 10,000 citing papers
   per review in total, so fetch the first 1,000 to 2,000 by relevance with the intent as
   the search text, 5 to 10 calls, or restrict to seeds with 100 citations or fewer.
   Expected gain: the largest of the list if the coupling rank concentrates the hits.
2. **A longer tail with a better tail ranker, affordable through re-ranking before
   screening.** Bucket C is 26% of the ground truth with almost no citation signal (one
   citing seed). Expanding to 500 gave +4.5 points at a cap of 400 in the sweep. The
   tail cannot be ranked by counts alone; the Inciteful-style score (shared references
   weighted by 1 / log of how widely each is cited, close to our specificity) and an
   embedding similarity to the intent are the two cheap signals. This is also where
   screening enters: an embedding re-rank over 500 to 1,000 candidates lets the screen
   see the top 200 of a much larger pool for the same screening bill. Cost: zero
   OpenAlex calls; embeddings are already computed on acquisition.
3. **Better seeds from semantic search.** OpenAlex now offers `search.semantic`
   (embedding search over titles and abstracts, 50 results per call, $0.001 per call,
   one request per second). The 046 baselines showed that dense retrieval returns far
   more on-topic candidates than keyword search at the same cap (18% against 6.5% at
   1,000). Since seed quality drives the snowball more than anything else measured, two
   to four semantic calls on the intent and its paraphrases, merged with the keyword
   seeds, is a cheap test. Expected gain: medium; it also feeds hypothesis 1 with better
   seeds to chase from.
4. **Topic-constrained search for the unreachable third.** 213 of the 521 no-path misses
   share one of the seeds' three dominant OpenAlex topics. The seeds tell us the topic
   ids for free; a second pass of the same queries, or a broader query, restricted by
   `primary_topic.id`, trades the generic noise that sank the wide-net prompts for a
   topic fence. Five calls. Expected gain: small to medium, and it is the only idea
   that addresses bucket D6.
5. **Second hop from the top candidates.** Tested here as a bucket: only 28 misses (3%)
   are cited by any of the 200 snowball papers, 11 by two or more. Low priority on this
   evidence; the literature's large second-hop gains come with candidate pools of
   thousands. Keep as a follow-on to hypothesis 2 once a bigger pool is affordable.

Background research (2026-10-06, see the task notes for sources): backward citation
checking adds 2.5% to 43% more included studies across Cochrane audits; Greenhalgh and
Peacock found 51% of sources through snowballing against 30% from database searches;
CoCites reaches a median 75% recall from two seeds in health; forward searching is used
by only 12% of Cochrane reviews, so evidence from social policy is thin; Connected Papers
and Inciteful score papers by co-citation and bibliographic coupling, which the
`referenced_works` field and the `cites:` filter make computable locally. OpenAlex
specifics checked live: `cites:`, `cited_by:` and `related_to:` filters work; at most 100
values per filter; `group_by` cannot count references, so co-citation is computed
locally; the documented page size is now 100, although 200 still returned; the free tier
is $1 per day with a key, and each list call costs $0.0001.

### 7. Forward citation chasing (2026-10-06, hypothesis 1 tested)

**What it does.** After the backward snowball, fetch the papers that **cite** the seeds
(OpenAlex `cites:` filter, up to 100 seed ids per call, filtered to the cutoff date).
Score each citing paper by **coupling**: how many seeds it cites, read from its own
reference list. Add the top 200 by coupling to the candidate set. Citations point
backwards in time, so the backward snowball finds older work; forward chasing finds the
newer work that builds on the seeds, which the miss analysis showed was 28% of the
ground truth.

**Settings tried**, production prompt, 200 seeds, 200 snowball, 200 forward, luna seeds
unless stated:

| variant | cap 200 | cap 400 | ceiling |
|---|---:|---:|---:|
| no forward stage (for reference) | 14.0% | 16.6% | 16.6% |
| chase every seed under 300 citations, citing papers must also match the question words | 13.7% | 16.4% | 17.6% |
| chase every seed under 300 citations, 5 pages | 13.2% | 18.3% | 20.1% |
| chase the 50 seeds with most in-set citations, 10 pages | 14.5% | 19.1% | 20.8% |
| chase the 20 seeds with most in-set citations, 10 pages | 14.4% | 19.2% | 21.0% |
| same, citing papers fetched in citation-count order | 14.4% | 18.7% | 20.7% |
| **same 20-seed chase, gpt-5.4-mini seeds instead of luna** | **16.3%** | **21.1%** | **22.8%** |

Adding the question words as a search filter on the citing papers was the worst option:
it returned only 12 to 1,400 citing papers per review and found almost nothing new.
Chasing only the 20 seeds with the most in-set citations, the topic's landmarks among
the seeds, was as good as chasing 50 or 180 and keeps the fetch small (10 pages of 200).

**Ranking the citing papers mattered more than which seeds to chase.** From the cached
citing sets (141 ground-truth papers among them, 15% of the ground truth), the number
of hits ranked into the top 200:

| ranking rule for citing papers | hits in top 100 | hits in top 200 |
|---|---:|---:|
| the service's default order | 16 | 26 |
| coupling (number of seeds cited) | 39 | 55 |
| **weighted coupling** (each cited seed weighted by log2 of its own in-set citations) | **53** | **66** |
| coupling, then newest first | 32 | 46 |
| newest first | 9 | 13 |
| most cited first | 16 | 26 |

Weighted coupling is used to order the citing papers. For the merged list, however, the
weighted value is on a different scale from the in-set count and, put into the
specificity score directly, floods the top 200 with citing papers (12.0% at cap 200).
So the specificity score adds the plain coupling count to the in-set count, and the
weighted coupling only breaks ties. Quota designs (a fixed 50 or 100 slots for citing
papers) scored the same or slightly lower.

**Result with gpt-5.4-mini seeds**, like for like on the same seed sample:

| | cap 200 | cap 400 | ceiling (594 candidates) |
|---|---:|---:|---:|
| snowball only | 13.6% | 16.8% | 16.8% |
| snowball plus forward | **16.3%** | **21.1%** | **22.8%** |
| hits per review from the forward stage | 2.7 | 3.9 | 4.1 |

Cost: 10 extra OpenAlex calls per search (two batches of up to 100 seed ids would need
20, but 20 chased seeds fit in one batch), free, about 5 seconds. No language-model call.
A surprise in passing: with the forward stage the gpt-5.4-mini seeds beat the luna
seeds (16.3% against 14.4% at cap 200), consistent with mini's slightly better seed
recall; the earlier "luna and mini are tied" reading stands, mini is simply not worse.

**Mini against luna, with and without the forward stage** (same settings: production
prompt, 200 seeds, 200 snowball, 200 forward from the 20 most in-set-cited seeds, 10
pages; each model is one seed sample):

| seeds from | stage | cap 200 | cap 400 | ceiling |
|---|---|---:|---:|---:|
| gpt-5.4-mini | snowball only | 13.6% | 16.8% | 16.8% |
| gpt-5.4-mini | snowball plus forward | **16.3%** | **21.1%** | **22.8%** |
| gpt-5.6-luna | snowball only | 14.0% | 16.6% | 16.6% |
| gpt-5.6-luna | snowball plus forward | 14.4% | 19.2% | 21.0% |
| gpt-5.6-luna, synonym-block prompt (`exp_d`) | snowball plus forward | **18.5%** | **23.7%** | **26.0%** |

The forward stage helps both, more for mini at cap 200 (+2.7 against +0.4) and about the
same at the ceiling (+6.0 against +4.4). Luna's seeds-only recall is lower (5.4% against
7.0% / 5.9% for mini), and that smaller base carries through every later stage. Since
the pipeline is moving to luna anyway, the practical reading is: expect about two points
less than mini at cap 200 with this prompt, and treat the prompt as the place to recover
it, because luna did better than mini with the synonym-block prompt (section 3). Testing
that prompt with the forward stage on luna was run next and is the best configuration
measured so far: 18.5% at cap 200, 23.7% at 400, 26.0% ceiling, one run. For the luna
migration this is the configuration to carry forward, with a repeat to confirm it.

**How the ranking score works.** Each candidate gets one number and the list is sorted
by it, highest first, before the cut at 200:

```
specificity = (in-set citations + coupling) / log10(global citations + 10)
```

- *In-set citations*: how many of the 200 seeds cite this paper. The backward signal; a
  paper cited by 60 seeds is a landmark of the topic. Seeds have it too.
- *Coupling*: how many of the 200 seeds this paper cites. The forward signal; a 2024
  paper that cites 13 seeds is about the topic even though nobody cites it yet. Known
  for seeds and forward candidates; backward candidates have none, since their
  reference lists were not fetched.
- *Global citations*: the paper's citation count across OpenAlex. Dividing by its
  logarithm pushes down papers everyone cites for any reason (PRISMA, a statistics
  method) and leaves papers this topic cites.

Examples: a seed cited by 60 seeds with 2,400 global citations scores 60 / 3.4 = 18.
PRISMA, cited by 30 seeds with 83,000 global citations, scores 30 / 4.9 = 6. A new paper
citing 13 seeds with 6 global citations scores 13 / 1.2 = 11. Ties are broken by the
weighted coupling (each cited seed weighted by log2 of its own in-set citations); it is
not in the score itself because it runs much larger than the counts and, added directly,
pushed too many citing papers to the top (12.0% at cap 200). The relevance reserve of the
recommended configuration, the first 50 keyword results kept in their own order, is not
yet in the script; every number above is the score alone.

**On the manual question** (criticality in neural networks), the forward candidates in
the top 30 are the recent syntheses and the newest work: "Theoretical foundations of
studying criticality in the brain" (2022), "The fractal brain" (2022), "Criticality,
connectivity and neural disorder" (2021), "Mechanisms of self-organized quasicriticality"
(2020), and several 2024 to 2025 papers with under ten citations that cite twelve or
more of the seeds. That is the "novel" half of the seminal-and-novel balance the owner
asked for. Whether a 2025 paper with six citations should sit at rank 5 because it cites
thirteen seeds is a display question; the signal itself is right.

### 8. A longer tail re-ranked before the cut, and a topic fence (2026-10-06, hypotheses 2 and 4)

Script: `measure/pool_rerank.py`. It builds a much larger pool than the base
configuration and asks whether a better ranking rule can pull the ground truth to the
top of it: 200 seeds, **800** backward snowball papers (against 200), 200 forward
papers, plus the **topic fence**: the five generated queries and the question rerun
on OpenAlex restricted to the seeds' three most common `primary_topic` ids. Each
candidate's title and abstract is embedded with the pipeline's own embedding model
(`text-embedding-3-small`) and compared with the question. Six ranking rules are
scored on the same pool. Cost on a fresh run, per review: about 54 free OpenAlex
calls and under a cent of embeddings.

**Pool and ceiling, production prompt on gpt-5.4-mini, 15 reviews.** The pool holds
about 1,900 candidates per review, of which about 700 come from the topic fence. The
ground truth inside the pool is **35.5%**, against 22.8% for the 594-candidate pool of
section 7 and 16.8% for the base 395. The longer tail is where the missing papers are.

| ranking rule on the 1,900 pool | cap 200 | cap 400 | cap 600 |
|---|---:|---:|---:|
| graph only: specificity (current rule) | 15.7% | 20.9% | 24.3% |
| graph only: Adamic-Adar weighting of the citing seeds | 14.4% | 20.1% | 24.4% |
| embedding similarity only | 12.1% | 15.9% | 20.5% |
| fusion: reciprocal rank of specificity and similarity | 17.4% | 22.6% | 25.2% |
| **product: (specificity + 0.5) x (normalised similarity + 0.2)** | **17.9%** | 22.3% | **26.0%** |
| shortlist 400 by specificity, re-ranked by similarity | 15.7% | 20.9% | 24.3% |

What the numbers say:

- **The embedding is a useful multiplier on the graph score, not a replacement.** Alone
  it is the weakest rule (12.1% at cap 200). Multiplied into the specificity score it
  adds about two points at cap 200 and at cap 600 over the graph alone, and the fusion
  rule adds a similar amount. The graph says "tied to the topic's literature", the
  embedding says "about the question", and the ground truth needs both.
- **Re-ranking a graph shortlist by embedding does nothing**: taking the top 400 by
  specificity and reordering it by similarity gives the same recall as the graph order
  at every cap. The embedding has to be in the score, not applied after the cut.
- **Adamic-Adar weighting does not help.** Weighting a citing seed by the length of its
  reference list is a wash. The plain count stays.
- **The longer tail pays only with a bigger cap.** With the 800-paper tail the graph rule
  at cap 200 is 15.7%, slightly below the 16.3% of the 200-paper tail, because more
  weak candidates compete for the same slots; at cap 600 it reaches 24.3%, and with the
  embedding product 26.0%. So the tail is for a pipeline that can afford to screen 400
  to 600 candidates, where it is worth five to eight points over today's 200.
- **The topic fence reaches little.** 716 extra candidates per review, of which the
  ground truth reachable only through them is 3.8% of the total, and under any ranking
  rule they contribute at most about one hit per review at cap 400. The seeds' top
  three topics are too coarse a fence: "Health and Social Care Interventions in the 80
  years Old and Over" gets a topic that covers all of geriatric care. Not worth 700
  candidates. Dropped.

**The same experiment on the luna configuration** (synonym-block prompt `exp_d`,
gpt-5.6-luna seeds; pool about 1,940 candidates, ground truth in pool **40.4%**):

| ranking rule on the pool | cap 200 | cap 400 | cap 600 |
|---|---:|---:|---:|
| graph only: specificity | 17.5% | 24.2% | 27.1% |
| embedding similarity only | 12.3% | 18.4% | 23.0% |
| fusion: reciprocal rank of specificity and similarity | 18.3% | 25.0% | **29.7%** |
| **product: specificity x normalised similarity** | **19.1%** | **25.7%** | 29.1% |

Same shape as on mini, two to three points higher throughout: the embedding product adds
about 1.5 points at every cap over the graph alone, and the whole pool holds 40% of the
ground truth. With the short tail (section 7) this configuration measured 18.5% at cap
200; the long tail with the product rule gives 19.1% at 200 and 25.7% at 400.

**What this means for screening.** The screen is the expensive step, about a cent per
document. Today it sees 200 candidates and finds about 16% of the ground truth. Three
options sit on the curve this experiment measured:

| candidates screened | ranking | recall | screening cost per search |
|---|---|---:|---:|
| 200 | graph (section 7 base) | 16.3% | about $2 |
| 400 | graph x embedding | 22.3% | about $4 |
| 600 | graph x embedding | 26.0% | about $6 |
| 1,900 (whole pool) | none | 35.5% | about $19 |
| 400, luna `exp_d` seeds | graph x embedding | 25.7% | about $4 |
| 600, luna `exp_d` seeds | graph x embedding | 29.1% | about $6 |
| 1,940 (whole pool), luna `exp_d` seeds | none | 40.4% | about $19 |

The embedding step itself is nearly free and already exists in the pipeline. The choice
is purely how many documents to pay to screen. A cheaper alternative, not tested here:
a language-model title-only triage over the pool at a fraction of a cent per paper
before the full screen.

### 9. Semantic seeds (2026-10-06, hypothesis 3 tested)

OpenAlex offers an embedding search over titles and abstracts (`search.semantic`): 50
results per call, about $0.001 per call, one request per second, no date filter but a
`publication_year` fence, so the exact cutoff is applied locally. The experiment sends
eight texts per review as separate semantic calls: the question, the production
prompt's two natural-language paraphrases (written for Overton and until now thrown
away on the OpenAlex side) and its five keyword queries. The results are merged
round-robin, as the keyword results are. Three seed sources were compared, all with
the same backward snowball (200) and forward stage (200 from the 20 most in-set-cited
seeds), production prompt on gpt-5.4-mini:

| seed source | seeds only, hits per review | cap 200 | cap 400 | ceiling (about 590) | seminal recall at 200 |
|---|---:|---:|---:|---:|---:|
| keyword queries (15 calls) | 4.1 | 16.3% | 21.1% | 22.8% | 36.0% |
| semantic search (8 calls) | 5.6 | 17.9% | 24.7% | 27.4% | 34.9% |
| **keyword plus semantic (23 calls)** | **7.1** | **21.9%** | **28.1%** | **30.6%** | **46.0%** |

What the numbers say:

- **Semantic search finds different papers from keyword search, and better ones.** On its
  own it finds 5.6 ground-truth seeds per review against 4.1 for keywords. Together they
  find 7.1, so the overlap is small: each route reaches papers the other does not. This
  matches the September baseline, where the dense Semantic Scholar search also beat
  keyword search by a wide margin at the same cap.
- **Better seeds lift every later stage.** The snowball and the forward stage both count
  from the seeds, so a seed set that holds more of the topic's studies produces counts
  that point at more of them. The combined seeds add 5.6 points at cap 200 and 7.0 at
  cap 400 over keyword seeds alone, the largest single gain measured today after the
  snowball itself. Recall on the most-cited tenth of the labelled reviews goes from 36%
  to 46%.
- **Cost is about a cent per search, measured.** Test calls on our Member account on
  2026-10-06, reading the `x-ratelimit-cost-usd` header and `meta.cost_usd`: a keyword
  `search` page costs $0.0001 whatever its size (10, 50 or 200 results, page 1 or 2), a
  list-and-filter call $0.0001, a `search.semantic` call $0.001 whether it returns 10 or
  50 results. The published table says $1 per 1,000 for keyword search; we are charged
  a tenth of that. The whole configuration, 15 keyword calls, 8 semantic calls and
  about 19 list calls, is therefore about $0.011 per search. The Member plan gives a
  $20 daily budget (200,000 credits, reset at midnight UTC), so about 1,800 searches a
  day; the whole day of experiments used about $1.50 of it. Against about $2 to screen
  200 candidates, retrieval cost is noise.
- **On the luna configuration the same recipe did not help.** Luna with the
  synonym-block prompt `exp_d`, combined seeds, snowball and forward: 16.8% at cap 200,
  24.7% at 400, 27.2% ceiling, against 18.5% / 23.7% / 26.0% with keyword seeds alone.
  The seed set itself improved (5.9 ground-truth seeds per review against 4.6) but the
  cap-200 result fell. The likely cause: the texts sent to semantic search include the
  five generated queries, and `exp_d` queries are 250-character boolean blocks, which
  are poor input for an embedding search. Each bad semantic call still gets an equal
  share of the round-robin merge, so it dilutes the 200 seeds. A variant that sends only
  the question and the two paraphrases (`--semantic-texts intent`) is running. Until it
  reports, the combined-seed gain is established for the production prompt on mini and
  open for luna.
- **One caveat on the date fence.** The semantic endpoint only filters by year, so papers
  from the cutoff year but after the cutoff day are fetched and then dropped locally.
  Nothing leaks into the scores; the calls just return a few results fewer.

### 10. What to do next

1. All five hypotheses of section 6 are tested (sections 7 to 9): forward chasing and
   semantic seeds adopted; the embedding product adopted as the ranking rule when a
   400-plus pool is affordable; the topic fence and the second hop dropped. Next:
   repeat the best configuration on luna with the `exp_d` prompt, and run it on the
   full 100-review set.
2. Promote the snowball and the forward stage into the pipeline: replace the current five-seed snowball arm
   with reference counting over the screened-in set, at standard depth as well as deep,
   ranked by specificity with a relevance reserve.
3. Add the seminal-decile recall to the eval scores, for labelled reviews only.
4. Label the ground truth (cents of language-model spend) so recall is measured against
   on-topic studies only.
5. Stop working on prompt wording.

## Terms used in the tables

- **Seeds alone.** Recall of the 200 keyword search results by themselves. This isolates
  the effect of the prompt and model.
- **With snowball.** Recall after reference counting, ranked by specificity, keeping the
  first 200. Same budget of 200 candidates, filled differently.
- **Ceiling.** Recall of the whole candidate set with no cap, about 395 papers (200 seeds
  plus the snowball papers that survive the date filter). It is the most any ranking of
  that set could reach. The gap between the ceiling and the cap-200 figure is what the
  ranking costs. In production it is what screening all 395 would give, at about twice
  the screening cost.
- **Noise floor.** The production prompt run twice gave 15.2% and 14.1%. The model writes
  different queries each time, and one paper found or lost moves a review by one or two
  points. Treat differences under one point as nothing.
- **Seminal-decile recall.** Recall on the most-cited tenth of a review's reference list
  (at least five papers), reported only for reviews whose list is a labelled set of
  included studies.

## The script: `measure/snowball_recall.py`

Started 2026-10-06 (task 047). Not promoted to the pipeline yet.

**Method, step by step.**

1. Seeds: the first N results of a keyword search. With `--queries raw` this is the one
   plain query of the `openalex-raw` baseline (read from its cache). With `--queries
   shared` the pipeline's own query generator writes five queries, each sent with the
   systematic-review and randomised-trial variants that rapid search adds, one page of
   200 results per call, merged round-robin as the pipeline's acquire step does.
2. Reference lists: one batched OpenAlex lookup per 50 seeds returns every work each
   seed cites, plus the seed's own citation count.
3. Count: how many seeds cite each work. This is its **in-set citations**.
4. Expand: resolve the K most-cited works that are not already seeds, filtered to the
   review's cutoff date. A few fewer than K come back, because references published
   after the cutoff are dropped.
5. Rank the combined set by one rule and cut at each cap.

| ranking rule | order |
|---|---|
| `raw` | keyword results in the service's order, then snowball works by in-set citations. Below a cap of N this is the keyword search itself, so it is the control. |
| `inset` | in-set citations, ties by global citations |
| `specific` | in-set citations / log10(global citations + 10). The recommended rule. |
| `global` | global citation count |
| `interleave` | one keyword result, one snowball work, alternating |

**Cost and speed.** About (N + K) / 50 OpenAlex requests per review, free, 3 to 5
seconds. With generated queries, one language-model call per review (about 1.4 seconds
on gpt-5.4-mini) plus 15 OpenAlex calls. Everything fetched is cached under
`results/cache/` (snowball payloads, generated queries, query pages, ground-truth
citation counts), so a second run makes no requests. A failed page is never served from
the cache.

**Run.**

```
# raw query seeds, with the manual question exported for hand review
uv run --project backend --env-file backend/.env python scripts/evals/search/measure/snowball_recall.py \
    --seeds 200 --expand 200 --caps 50 100 200 400 \
    --manual "What is the relationship between avalanche criticality and edge of chaos criticality in neural networks"

# generated-query seeds with the production prompt
uv run --project backend --env-file backend/.env python scripts/evals/search/measure/snowball_recall.py \
    --queries shared --rankings raw specific --caps 100 200 400

# an edited prompt, a different model, a reasoning setting, a repeat
uv run --project backend --env-file backend/.env python scripts/evals/search/measure/snowball_recall.py \
    --queries shared --prompt-file scripts/evals/search/prompts/search_queries_exp_d.txt \
    --model gpt-5.6-luna --reasoning-effort low --repeat 2
```

**Options.**

- `--queries raw | shared | per-provider | concepts`. The seed source. `shared` is the
  production prompt. `per-provider` is the pipeline's older one-prompt-per-service path
  (seven calls per question). `concepts` asks the model for concept blocks and builds
  the queries in code.
- `--prompt-file`. An edited copy of the generator's system prompt. The committed prompt
  files are never changed. The run label and the cache key carry the prompt's hash, so
  two prompts never share a cache. Editable copies live in `prompts/`.
- `--model`, `--reasoning-effort`, `--repeat`. Each becomes part of the label and the
  cache key. `--repeat 2` asks the model again to measure variance.
- `--no-variants`, `--per-call`. Drop the review and trial variants; results per query.

**Outputs**, under `results/snowball/<label>/`:

- `scores.csv`: one row per review, ranking and cap, with `n_from_seed` and
  `n_from_snowball` saying where the hits came from.
- `candidates/<review>.csv`: the ranked set with every signal (`inset`, `specificity`,
  `cited_by_count`, `year`, `source`, `raw_rank`, `in_ground_truth`), so misses can be
  read.
- `queries.csv`: every generated query, its result count and its ground-truth hits. Read
  this when changing a prompt.
- `manual/<question slug>/`: for a `--manual` question with no ground truth, one ranked
  table per rule, for hand review.

**Full results tables** with every configuration, the parameter sweep over seeds and
expansion, the per-review tables and the two reviews that got worse are in
`docs/tasks/047-search-rnd/notes.md`.
