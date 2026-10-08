# Task 049: Overton search R&D notes

Light-touch R&D, outside the full task cycle, as task 047 was. The question: the
search experiments in task 047 lifted OpenAlex recall from 3% to about 22% at 200
candidates (seeds, reference-list snowball, forward chasing, specificity ranking). How
much of that carries over to Overton, the policy-document index, and how do the two
sources merge under one candidate cap?

Measurement set: `retrieval-ground-truth-mini` (15 reviews, 8 labelled), scored on
DOIs, as in task 047. Write-up with the numbers and the design reasoning:
`scripts/evals/search/results/analyses/2026-10-07-overton-experiments.md`.
Illustrated version: `2026-10-07-overton-experiments.html` in the same folder. Each
experiment gets a dated entry here: what was tried, the numbers, what we learned.

## 2026-10-07 — What the Overton API can do (verified live)

Probed by hand against `app.overton.io` with our key. Facts the design rests on:

1. **Policy documents carry the DOIs of the papers they cite.** Every record from
   `documents.php` has `cites.scholarly`, a list of `{doi, title, journal, publisher}`.
   In a 50-document page on parental leave, 37 documents cited at least one paper. This
   is the backward snowball, served for free with the search result, no second call.
2. **The pipeline's Overton results are sorted by date, not relevance.** `documents.php`
   defaults to `sort=date` when no `sort` is sent, and the pipeline sends none
   (`_PROTECTED_OVERTON_PARAMS` and `_OVERTON_ALLOWED_WIRE_KEYS` in `search_live.py`
   have no `sort`). So the 50 records we keep per query are the 50 *newest* documents
   above similarity 0.3, out of a 2,500-document match set. With `sort=relevance` the
   same query returns an `es_score` and a sensible top (for parental leave: a 2008
   "Family leave after childbirth and the health of new mothers" paper, a 2016 review of
   parental leave and child development). With the default, the first result was an
   Italian regional employment regulation. `sort=citations` also works.
3. **Overton has a scholarly-article search**: `articles.php?query=` is a keyword search
   over the 8.5 million papers that policy documents cite. Records carry `doi`, `title`,
   `abstract`, `citations` (the number of citing policy documents) and
   `cited_by_documents` (those documents, with their topics and classifications).
   `sort` takes `relevance`, `citations`, `date`; `published_before` and
   `published_after` work. Query words are AND-ed (three words gave 9 results, two gave
   768); `OR` and quoted phrases work. `squery` is ignored on this endpoint.
4. **Forward chasing from a paper to policy**: `documents.php?plain_dois_cited=<doi>`
   returns the policy documents citing one DOI. One DOI per call (a `|` list returns
   nothing), at one call per second, so it is for a handful of seeds, not hundreds.
5. The cutoff filter `published_before=YYYY-MM-DD` works on both endpoints.
6. Rate limit one call per second (the pipeline waits 1.2 s). Flat subscription, so
   the probes below cost nothing.

## 2026-10-07 — Four one-request probes on the mini set

Script: `scripts/evals/search/measure/overton_recall.py`. One request per review and
arm, intent sent verbatim (the `?` stripped for the keyword endpoint), cutoff applied
server-side, nothing uploaded. Cache under `results/cache/overton-<arm>/`, scores in
`results/overton/scores.csv` (git-ignored).

| arm | what it does |
|---|---|
| `articles` | `articles.php`, keyword, relevance order, first 200 papers |
| `articles-cited` | the same, ordered by policy citations |
| `docs-cites` | `documents.php` semantic search, relevance order, first 100 policy documents; the papers they cite ranked by how many of the 100 cite each ("in-set citations") |
| `docs-cites-date` | the same with Overton's default date order, which is what the pipeline gets today |

Mean recall, 15 reviews (full tables in the write-up, section 3):

| arm | cap 50 | cap 100 | cap 200 | cap 400 | ceiling |
|---|---:|---:|---:|---:|---:|
| `articles` and `articles-cited` | 0.3% | 0.3% | 0.3% | 0.3% | 0.3% |
| **`docs-cites`** | **3.4%** | **5.8%** | **7.7%** | **10.5%** | **18.1%** |
| `docs-cites-date` (today's order) | 0.9% | 1.5% | 1.7% | 2.6% | 6.0% |

What we learned:

- Two free Overton calls with the raw intent reach 7.7% at 200, between the plain
  OpenAlex snowball (10.3%) and the plain search (3.1%), with an 18.1% ceiling from
  about a thousand cited papers per review.
- Date order costs most of it: the same route in the pipeline's current order gives
  1.7% at 200. **Owner confirmed the date default is a bug (2026-10-07) and asked that
  it is not fixed during R&D**; it is recorded as production finding 1 in the write-up.
- The scholarly-article endpoint is an AND keyword search; the full intent returns
  three papers on average. Only worth retrying with short generated queries.
- Against the best task-047 configuration (22.4% at 200 on the same candidate tables):
  union 25.0% at 200 + 200, union of pools 36.6% against 30.6%. The new papers are on
  loneliness (+13 at 200), intimate partner violence (+7), and at pool level the
  gap-map rows: youth violence +7, fortified foods +7, learning-to-earning +2,
  whole-school +9. Civic education, social care, 80+ and drug-abuse risk factors get
  nothing.
- So the prior was half right. Gap-map rows gain, but below rank 200 on Overton's own
  ranking; the gain needs a merged ranking. "Academic" topics split by whether
  governments write about them: loneliness, partner violence and learning loss gain,
  clinical topics do not.

## 2026-10-07 — Merged ranking, offline

Script: `scripts/evals/search/measure/merge_rank.py`. Union of the best task-047
OpenAlex pool (about 600 per review) and the Overton cited papers (about 1,000),
joined on DOI, Overton-only papers resolved on OpenAlex for citation counts and
dates. Fourteen rankings: one specificity score with policy citations weighted 0.5 to
3, reciprocal rank fusion, interleaving, slot quotas, embedding similarity, and the
task-047 product rule on the union. Full tables in the write-up, section 3.

| ranking | cap 200 | cap 600 | all |
|---|---:|---:|---:|
| OpenAlex pool alone (control) | 22.4% | 30.6% | 30.6% |
| Overton alone (control) | 7.7% | 13.9% | 18.1% |
| best merged: product rule, policy weight 1 | 23.3% | 30.8% | 36.6% |
| every other merged rule | 16.1% to 23.0% | 26.4% to 31.6% | 36.6% |

What we learned:

- The union's 36.6% ceiling cannot be brought under a 200 cap by ranking. Best gain
  0.9 points, inside the noise. Rules that push Overton papers up lose more OpenAlex
  hits than they gain.
- Cause: of the 60 ground-truth papers only Overton found, 41 have exactly one
  citing policy document, among 11,185 other such papers; their median Overton rank
  is 504; the paper graph has nothing on them (no seed cites them, they cite no
  seed). Embedding similarity finds 16 of them in a top 200 but drops five points of
  OpenAlex hits to do it.
- The merge pays on single reviews: loneliness 18% to 24% at 200, and at 600
  loneliness and intimate partner violence gain 4 to 7 points. Elsewhere nothing.
- Keeping Overton's different tail is a screening-budget question (a larger pool)
  or a seed-quality question (generated queries, 200 documents, so that policy
  in-set counts rise above one), not a ranking question.

Cost of the run: free OpenAlex list calls plus about 13 cents of embeddings, all
cached.

## 2026-10-07 — Seed-set variants: more documents, generated texts

Four variants of the Overton route (`overton_recall.py --arms ...`), to see whether
policy in-set counts rise above one when the seed set is built like the OpenAlex one:
200 documents instead of 100; the intent plus the two generated paraphrases; plus the
five generated keyword queries; the eight texts with 400 documents. Tables in the
write-up, section 3.

| seed set | cap 200 | ceiling | hits with 2+ policy citations |
|---|---:|---:|---:|
| 1 text, 100 documents (probe) | 7.7% | 18.1% | 52% |
| 1 text, 200 | 8.9% | 22.3% | 57% |
| intent + 2 paraphrases, 200 | 9.3% | 22.8% | 57% |
| 8 texts, 200 | 9.5% | 21.0% | 56% |
| 8 texts, 400 | 10.7% | 25.1% | 61% |

What we learned: modest, monotone gains; the single-citation crowd grows as fast as
the hits, so the in-set count still cannot rank them. Merge on the 8-text, 400-
document set: union ceiling 39.3%, best rule at 200 still 23.1% against 22.4%. The
owner asked (2026-10-07) to keep the ranking by citations, as the OpenAlex route
does, rather than weighting by the semantic score; done so throughout.

Also fixed on the way: the probe ignored the policy documents' own DOIs (about 5% of
documents have one, in `keyed_other_identifiers`; the API call was right, the script
was not). They now go first in the list: 2 extra hits on the mini set. And the Overton
transport can drop a connection mid-body; the probe now retries transport errors as
well as status codes.

## 2026-10-07 — What the DOI-only metric hides: title matching

Owner's question: we score DOIs only, but the product wants relevant publications
without DOIs too; does that matter here? Script `measure/title_match.py`: normalised
title matching (strict, and a loose near-match rule with every match printed) of all
797 references in the 11 sampled mini reviews, 53 of them without a DOI, against the
5,341 Overton policy documents of the 8-text, 400-document arm, the Overton-cited
works without a DOI, and the DOI-less records of the OpenAlex pool.

| | strict | loose |
|---|---:|---:|
| DOI-less references found on Overton policy documents | 0 of 53 | 0 |
| found on DOI-less OpenAlex records | 6 of 53 | 6 |
| DOI references found only by title on a DOI-less candidate | 2 | 3 |

What we learned, honestly: on this sample the blind spot is under one point and sits
on the OpenAlex side (journal papers OpenAlex holds without a DOI). The DOI-less
references in the gap-map rows are papers missing a DOI in the export, not grey
literature. No review-included reference is an Overton policy document, so a
policy-document recall would read zero here. The caveat is the sample: the four
hand-made reviews, which cite grey literature as evidence, are not in the references
file and their non-DOI entries are not uploaded as keys. Rerun after adding them from
the labelling repository before concluding anything about policy-document recall.

## 2026-10-07 — Key policy documents from Overton's own citation graph

Owner's question: can Overton's existing fields identify the key policy documents?
Script `measure/policy_rank.py`: policy-to-policy snowball (`cites.policy`, landmarks
fetched by id), specificity (damped by `citation_count`), coupling with the 50 core
papers, modest forward chasing from the 10 most-cited papers (`articles.php?query=doi`),
and with `--embed` the task-047 product rule with similarity as a damping term.
Write-up section 3 ("Ranking policy documents").

- Against the paper ground truth (paper recall of the papers the first 100 documents
  cite): snowball keeps 7.5% at 200 and lifts the ceiling to 20.9% (relevance 7.7 /
  18.1); coupling and forward reach 25 to 26% ceilings. The 200 cut does not move.
- By eye on obesity, decarbonising heating and early years attainment: the snowball
  surfaces the topic's canon, most of it documents the search never returned;
  specificity demotes the documents cited on everything; similarity damping removes
  the remaining generic landmarks (10 Year Health Plan, Sixth Carbon Budget, Ofsted
  annual report) on all three, at the cost of a few high-similarity single-citation
  committee submissions creeping in around rank 12. Coupling is topic-dependent
  (submissions on obesity and heating, evidence syntheses on early years).
- **Decision (owner, 2026-10-07): adopt the policy snowball with specificity; hold
  coupling and forward.** Similarity damping: agreed in principle, tested on three
  questions, looks right; a floor of two in-set citations would remove its one side
  effect.
- Production findings: duplicate documents under different sources (de-duplicate by
  normalised title); a record with a removed title.

## 2026-10-07 — A policy-side ground truth from Overton

Script `measure/policy_gt.py`. Target = the policy documents a gov.uk document cites,
cutoff = its date. Honest take recorded in the write-up: Overton-built target,
selective references, snowball favoured by design; for comparing orders only.

- `--set omnibus` (15 most-citing documents by rule, title as intent, 200 docs): the
  rule picked omnibus publications; pools held 4.1% of the target. Snowball 2.9% at 25
  against relevance 1.2%. A diagnosis of the rule, not a result.
- `--set specific` (15 hand-picked topic-specific documents with written questions,
  `ground_truth/policy_gt_specific.csv`, 400 docs, intent plus two paraphrases, caps
  25/50/100/200): snowball and specificity 5.8% at 25, 7.8% at 50, 8.3% at 100
  against relevance 3.5 / 3.7 / 4.8; pool ceiling 8.9%. Coupling and forward below
  relevance at 25. The snowball finds at 25 what relevance finds at 200.
- Where the rest of the target is (580 cited documents): 23% are cited by at least one
  retrieved document, 9% by two or more (the snowball's landmarks already take those),
  77% by none. The single-citation tail is the paper-side haystack again; untested
  lever: `cites.policy` carries titles, so that tail could be ranked by title
  similarity with no extra calls. The instrument is fit for comparing orders, not
  for an absolute number.

## 2026-10-07 — Why the policy ceiling is 9%: composition, and the country filter

Owner's question: structural? Yes, in two parts (write-up section 3, "Why the ceiling
is low"). For UK policy questions, 77% of what Overton's semantic search returns is
from outside the UK (Japan alone 8%), while 85% of what the strategies cite is UK
public bodies. And about half the unreached targets are the strategy's wider footprint
(acts, drug appraisals, a G7 communiqué), which no topic search should return.

`source_country=UK` (display value "UK"; the pipeline already has the wire parameter)
doubles the reachable ceiling on the specific set: targets cited by two or more
retrieved documents 9% to 17%, by one or more 23% to 33%, in the 400 results 6% to
11%. **Owner decision (2026-10-07): two measures, global and UK-only, kept side by
side; the country filter is a user option ("restrict to UK sources"), not a default,
because the product wants to widen exposure to global thinking.** Order comparison
under both settings (`policy_gt.py --set specific --docs 400 --paraphrases
[--source-country UK]`): snowball 5.8% at 25 global, 9.9% UK-only; relevance 3.5%
and 4.6%; pool ceiling 8.9% and 16.0%. Caveat: this instrument is built from gov.uk
strategies, so it rewards UK-only by construction; a fair global measure needs an
international target set (OECD, WHO, EU, or several countries' strategies on one
topic).

Next (write-up section 8): the hand-made reviews' non-DOI references into the file
and a rerun; a cheap title-only screen of the Overton tail; `articles.php` with the
short generated queries; the full 100-review set; then the production slice
(relevance sort, paraphrases plus 200 documents as the Overton seed set, the
documents' own DOIs and cited papers into the paper pool, policy documents under
their own cap).
