# Overton search experiments

Task 049, 7 October 2026. Companion to [2026-10-06-search-experiments.md](2026-10-06-search-experiments.md)
(task 047), which lifted OpenAlex recall from 3% to 22% at 200 candidates with a
reference-list snowball, forward citation chasing and semantic seeds. This file asks
what carries over to Overton, the policy-document index, and what Overton can do that
OpenAlex cannot. Running notes: `docs/tasks/049-improve-overton-search/notes.md`. An illustrated
version of this file, with diagrams of the two routes:
[2026-10-07-overton-experiments.html](2026-10-07-overton-experiments.html).
Per-review tables are in the `scores.csv` files named under each experiment.

**How to read the numbers.** The product's target is both research papers and policy
documents. The current ground truth is the reference lists of 15 systematic reviews
and gap maps (`retrieval-ground-truth-mini`), keyed by DOI, so it measures the paper
side only. Every recall figure here is a paper recall unless it says "policy recall".
Recall is the share of a review's reference list found; unlabelled lists (Campbell,
SR4ALL) have a ceiling near 50%. Overton is a flat subscription, so Overton calls are
free; the whole day cost under 50 cents in OpenAlex and embedding calls.

## Key results

- **Overton reaches papers through the papers that policy documents cite.** One
  semantic search for 100 policy documents, then the papers they cite ranked by how
  many of the 100 cite each: 7.7% at 200 candidates, 18.1% ceiling, two free calls, no
  language model. With eight generated texts and 400 documents: 10.7% and 25.1%.
- **Merging Overton's papers with the OpenAlex pool does not move the 200 cut.** The
  union ceiling is 39%, but no ranking rule gets more than a point over OpenAlex alone
  (23.1% against 22.4%). The papers only Overton finds carry one policy citation each,
  among eleven thousand others like them. Nothing ranks them.
- **The DOI metric hides under a point on this sample.** Title matching finds 6 of the
  53 DOI-less references in the OpenAlex pool (five of them records that do carry a
  DOI the reference list lacks, one a DOI-less record) and none on 5,341 policy
  documents. The sample has no grey literature as evidence; the hand-made reviews do,
  and they are not in the file yet.
- **For the policy side, the policy-to-policy snowball with specificity is the
  method.** Counting how many retrieved documents cite each policy document, and
  fetching the most-cited ones the search missed, surfaces the canon of a topic. On
  obesity, seven of the top ten were not in the 200 search results. On a 15-strategy
  ground truth it finds in 50 documents more than the search order finds in 200.
- **For UK questions, three quarters of what Overton returns is from outside the UK.**
  A `source_country=UK` filter doubles what the snowball can reach on a UK-built
  target. By owner decision it is a user option, not a default, and the evaluation
  keeps a global and a UK-only measure side by side.
- **Two production bugs, not fixed here.** The pipeline's Overton calls default to
  `sort=date`, so the 50 documents kept per query are the newest above the similarity
  floor, not the most similar. And the same document can appear under two sources.

## 1. OpenAlex and Overton are different animals

| | OpenAlex | Overton |
|---|---|---|
| What a record is | a paper | a policy document (report, strategy, guidance, committee submission) |
| Identity | DOI on nearly every record | a DOI on about 5% (working papers, OECD, Cochrane); otherwise an Overton id |
| What a record cites | its reference list (papers) | the papers it cites (`cites.scholarly`, with DOIs) **and** the policy documents it cites (`cites.policy`, with ids and titles) |
| Who cites it | `cited_by_count`, papers citing the paper | `citation_count`, policy documents citing the document; no scholarly count anywhere |
| Search | keyword and semantic, both paid per call | semantic (`squery`) and keyword, flat subscription; **defaults to date order** unless `sort=relevance` is sent |
| Filters | date, type, many | date, source country (display value "UK"), source, source type; document series is a response field only |
| Rate | fast | one call per second |
| Paper lookup | by DOI, 50 per call | `articles.php?query=<doi>`: the policy documents citing one paper, one per call |

The consequence for recall: on OpenAlex the citation graph is paper-to-paper, so the
task-047 snowball finds the papers a topic keeps citing. On Overton the useful graphs
are policy-to-paper (which gives a second route to papers) and policy-to-policy
(which gives the key documents on the policy side, something OpenAlex has nothing to
say about).

## 2. The paper side: what carries over

### 2.1 Four one-request probes

`measure/overton_recall.py`, intent sent verbatim, cutoff server-side.

| arm | what it does | cap 200 | ceiling |
|---|---|---:|---:|
| `articles` | Overton's scholarly-article keyword search, relevance order | 0.3% | 0.3% |
| `articles-cited` | the same, ordered by policy citations | 0.3% | 0.3% |
| **`docs-cites`** | 100 policy documents by relevance; the papers they cite, ranked by how many of the 100 cite each | **7.7%** | **18.1%** |
| `docs-cites-date` | the same in Overton's default date order (what the pipeline gets today) | 1.7% | 6.0% |

For scale on the same reviews: plain OpenAlex search 3.1% at 200; OpenAlex snowball on
plain seeds 10.3%; the best task-047 configuration 21.9% at 200, 30.6% ceiling. The
article search is an AND keyword search; a full intent returns three papers.

Where the route helps: loneliness (28.6% at 200, above the whole OpenAlex configuration
at 17.9%), intimate partner violence, learning loss, youth violence. Where it does not:
civic education, social care, the 80-plus population, drug-abuse risk factors.
Pattern: topics governments write about gain; clinical topics do not.

### 2.2 Merged ranking

`measure/merge_rank.py`. The OpenAlex pool of the best task-047 run (about 600 papers
with in-set citations, coupling and citation counts) joined on DOI with the Overton
cited papers (about 1,000, with policy in-set citations). Fourteen rules: one
specificity for the union with policy citations weighted 0.5 to 3, reciprocal rank
fusion, interleaving, slot quotas, embedding similarity, and the task-047 product rule.

| ranking | cap 200 | cap 600 | all |
|---|---:|---:|---:|
| OpenAlex alone (control) | 22.4% | 30.6% | 30.6% |
| Overton alone (control) | 7.7% | 13.9% | 18.1% |
| best merge: product rule, policy weight 1 | 23.3% | 30.8% | 36.6% |
| every other rule | 16.1% to 23.0% | 26.4% to 31.6% | 36.6% |

Same result on the larger Overton seed set (2.3): union ceiling 39.3%, best rule at 200
23.1%. Why: of the 60 ground-truth papers only Overton found, 41 are cited by exactly
one of the 100 policy documents, among 11,185 other single-citation papers; their
median Overton rank is 504; the paper graph has nothing on them (no seed cites them,
they cite no seed). Embedding similarity finds 16 of them in a top 200 but drops five
points of OpenAlex hits to do it. The union is real; it pays only at a 1,500-candidate
pool, which is a screening-budget question.

### 2.3 Seed-set variants

Can better seeds raise the policy in-set counts above one?

| seed set | cap 200 | ceiling | hits with 2+ policy citations |
|---|---:|---:|---:|
| 1 text, 100 documents (probe) | 7.7% | 18.1% | 52% |
| 1 text, 200 documents | 8.9% | 22.3% | 57% |
| intent + 2 generated paraphrases, 200 | 9.3% | 22.8% | 57% |
| intent + paraphrases + 5 generated queries, 200 | 9.5% | 21.0% | 56% |
| the same 8 texts, 400 documents | 10.7% | 25.1% | 61% |

Modest, monotone gains. The single-citation crowd grows as fast as the hits. Also fixed
on the way: the probe ignored the policy documents' own DOIs (5% have one); they now
rank first, for two extra hits.

### 2.4 What the DOI metric hides

`measure/title_match.py`. The sample keeps a review only if 70% of its references have a
DOI (50% for YEF), leaving 53 of 797 references outside the measure. Normalised title
matching (strict, and a loose near-match rule with every match printed) of all 797
against 5,341 Overton policy documents, the Overton-cited works without a DOI, and the
DOI-less records of the OpenAlex pool:

| | found |
|---|---:|
| DOI-less references on Overton policy documents | 0 of 53 |
| DOI-less references on Overton-cited works without a DOI | 0 (there are none) |
| DOI-less references on any OpenAlex record in the pool | 6 of 53 |
| of those, on a record that itself has no DOI | 1 |
| DOI references found only by title on a DOI-less candidate | 3 (loose), 2 (strict) |

DOI recall over the 743 references that have a DOI, pooled: Overton route 24.0%,
OpenAlex pool 30.1%. Coverage over all 797 references with title matches added:
22.3% and 28.2%.

The blind spot is under a point on this sample and sits on the OpenAlex side. Five of
the six title matches are OpenAlex records that have a DOI the review's export does
not: the reference list is missing the DOI, not the record. The DOI-less references in
the gap-map rows are papers missing a DOI in the export, not grey literature. No review-included reference is an Overton policy document. The
four hand-made reviews, which cite grey literature as evidence, are not in the file;
add them before concluding anything about policy-document recall.

## 3. The policy side: finding the key documents

### 3.1 Signals and orders

`measure/policy_rank.py`. 200 policy documents by relevance, then:

| order | what it is | calls |
|---|---|---:|
| `relevance` | the search order (control) | 4 |
| `inset` | **policy snowball**: how many retrieved documents cite this one; the 15 most-cited documents the search missed are fetched and added | +15 |
| `specific` | in-set citations / log10(citation_count + 10): the snowball damped by how widely the document is cited overall | 0 |
| `coupling` | how many of the 50 core papers (most cited by the retrieved documents) this document cites | 0 |
| `forward` | for the 10 most-cited core papers, the policy documents citing them; score = how many of the 10 a document cites; 15 new ones fetched | +25 |
| `combined` | coupling + in-set + forward | 0 |
| `specific-sim` | (specificity + 0.5) x (embedding similarity of title + excerpt to the question + 0.2) | one embedding call per 100 documents |

**The similarity damper, in words.** The snowball ranks by citations alone, so a
document cited by many results on every topic (a carbon budget, a ten-year health
plan) can sit high on a question it has little to do with, and the landmarks it
fetches arrive with no search score at all. The damper turns each document's title
and excerpt, and the question, into embeddings with the pipeline's embedding model,
takes the cosine between them scaled 0 to 1 across the set (the document's
*similarity* to the question), and multiplies the citation score by it. The two
constants keep a zero on one side from wiping out the other. A document that many
results cite and that is about the question keeps its place; one that many results
cite but is off the question drops.

### 3.2 Three checks

**Against the paper ground truth**, by the paper recall of the papers the first 100
documents cite: the snowball keeps 7.5% at 200 and lifts the ceiling to 20.9%
(relevance 7.7% / 18.1%); coupling and forward reach 25 to 26% ceilings. The 200 cut
does not move.

**By eye**, on obesity, decarbonising heating and early years attainment (top-25
tables under `results/overton/policy/`):

- The search order puts committee evidence submissions and individual submissions
  first on all three questions.
- The snowball surfaces the canon. Obesity: Obesity statistics, the childhood obesity
  plan (both chapters), the sugar reduction reports, the 2007 Foresight report, the
  OECD and CMO reports; seven of the ten were not in the 200 search results. Heating:
  Next Steps for UK Heat Policy, the Renewable Heat Incentive, the hydrogen and
  pathways reports. Early years: the SEED study, the RAND review, the EYFS framework,
  Starting Strong, Head Start.
- Specificity demotes the documents cited on everything (the 10 Year Health Plan,
  cited by 516 documents). Similarity damping removes the remaining generic landmarks
  (a carbon budget, a building regulation, Ofsted's annual report) on all three. Its
  one cost: single-citation documents with very high similarity, mostly committee
  submissions, climb when landmarks run out. Applying the damper only to documents
  cited by two or more results would stop that; untested.
- Coupling is topic-dependent: on obesity and heating it ranks committee submissions
  that cite many core papers; on early years it produces the best list of the day
  (the SEED series, Starting Strong III, the systematic reviews). Held, pending a
  document-type filter. Forward added little the snowball lacked. Held.

**Against a policy ground truth built from Overton** (`measure/policy_gt.py`). The
paper ground truth holds no policy documents, so a second instrument: the target is
the policy documents a gov.uk document cites, the cutoff its own date, itself
excluded. Caveats first: every target is in Overton by construction, a strategy's
references are selective and skew to the department's own earlier documents, and the
snowball is favoured by design. For comparing orders, not for a headline.

A first pass selected the 15 gov.uk documents citing the most policy documents. The
rule picked omnibus publications (an SDG review, Net Zero, Levelling Up); their pools
held 4% of the target. Not a result, and not rerun after the fixes below. The second
pass is 15 hand-picked topic-specific
documents with written questions (`ground_truth/policy_gt_specific.csv`: women's
health, prevention, ageing, smoking, SEND, children's social care, the 1,001 days,
adult skills, violence against women, serious violence, work and disability, rough
sleeping, heat and transport decarbonisation, gambling), 400 documents from the
question plus two generated paraphrases. Policy recall, mean over the 15:

| order | @25 | @50 | @100 | @200 | pool ceiling |
|---|---:|---:|---:|---:|---:|
| `relevance` | 3.5% | 3.7% | 4.8% | 7.3% | 8.8% |
| **`inset`** | **6.0%** | **8.0%** | **8.5%** | 8.8% | 8.8% |
| **`specific`** | **6.0%** | **8.0%** | **8.5%** | 8.8% | 8.8% |
| `coupling` | 1.0% | 3.1% | 7.6% | 8.8% | 8.8% |
| `forward` | 0.6% | 2.7% | 4.4% | 6.9% | 8.8% |
| `combined` | 1.3% | 4.7% | 8.5% | 8.8% | 8.8% |

The snowball finds in 50 documents more than relevance finds in 200. Gambling 16% at 25 against 0%,
children's social care 12% against 3%, serious violence 11% against 5%.

### 3.3 Why the ceiling is 9%: a structural mismatch

Of the 580 targets, 23% are cited by at least one retrieved document, 9% by two or
more (the snowball's landmarks already take those), 77% by none. Two causes.

**Cause one: where the documents come from.**

| | retrieved documents (3,797) | strategy targets (580) |
|---|---|---|
| UK sources | 23% | about 85% (gov.uk 64%, then ONS, legislation, NHS England, the Climate Change Committee, NICE) |
| elsewhere | USA 23%, intergovernmental 14%, Japan 8%, Australia 5% | a few OECD, WHO, EU items |

For questions about UK policy, three quarters of what the semantic search returns is
from outside the UK. The Government of Japan supplied more documents than the UK
Government and Parliament together.

**Cause two: what a strategy cites.** A sample of 60 unreached targets splits evenly.
Half are on the topic and findable: the e-cigarettes evidence review, "What works for
whom in helping disabled people into work", the Rape Review, Hydrogen in a low-carbon
economy. Half are the strategy's wider footprint, which no topic search should return:
the Equality Act, the Licensing Act, a NICE drug appraisal, a G7 communiqué. The honest
ceiling for a topic search on this instrument is nearer half the target than all of it.

**The filter test.** Overton's `source_country=UK` (display value "UK"; the pipeline
already has the wire parameter) applied to the same 15 pools:

| | global | UK only |
|---|---:|---:|
| targets among the 400 search results | 6% | 11% |
| targets cited by at least one retrieved document | 23% | 33% |
| targets cited by two or more (what the snowball ranks) | 9% | 17% |

One parameter doubles what the snowball can reach. **Owner decision:** the product
wants to widen exposure to thinking from other countries, so the filter is a user
option ("restrict to UK sources"), not a default, and the evaluation keeps two
measures. The full order comparison under both settings:

| order | global @25 | global @100 | UK-only @25 | UK-only @100 | pool ceiling, global / UK-only |
|---|---:|---:|---:|---:|---:|
| `relevance` | 3.5% | 4.8% | 4.6% | 8.8% | 8.8% / 15.4% |
| **`inset`** | **6.0%** | **8.5%** | **9.6%** | **13.7%** | 8.8% / 15.4% |
| **`specific`** | **6.0%** | **8.5%** | **9.0%** | **13.7%** | 8.8% / 15.4% |
| `coupling` | 1.0% | 7.6% | 3.3% | 13.7% | 8.8% / 15.4% |
| `forward` | 0.6% | 4.4% | 2.5% | 8.6% | 8.8% / 15.4% |
| `combined` | 1.3% | 8.5% | 5.9% | 13.7% | 8.8% / 15.4% |

Under the UK filter the ceiling nearly doubles (15.4%) and the snowball keeps its
lead: 9.6% at 25 against 4.6% for the search order, well above the global snowball. Gambling 23% at 25,
the 1,001 days 19%, smoking 13%, transport decarbonisation 13%. The UK pools are
smaller (190 to 310 documents after de-duplication, from the same 24 calls), because
fewer UK documents pass the similarity floor; the search is working with less and
finding more.

Two honesty notes: this instrument is built from gov.uk strategies, so it rewards the
UK-only setting by construction; a fair global measure needs an international target
(OECD, WHO, EU, or several countries' strategies on one topic). And the non-UK share
of the global pool is not noise for the product: a Japanese obesity strategy may be
exactly the exposure wanted, even though no UK strategy cites it.

## 4. Production findings, not fixed here

1. **Overton date order.** `OvertonLiveBackend._search` sends no `sort`; the service
   defaults to `sort=date`. Every Overton candidate kept so far is "the newest
   document above similarity 0.3". Fix: `sort=relevance`, and add `sort` to the
   protected parameters. Owner confirmed as a bug.
2. **Duplicates.** The same document appears under different sources (a submission as
   "government" and as "think tank"; "Lifting Our Game" twice). De-duplicate by
   normalised title.
3. **A removed-title record** reached a top 15 ("[THIS TITLE IS BROKEN AND HAS BEEN
   REMOVED]"). Drop records without a usable title.
4. **`cites` is already retained** in `provider_fields` but nothing reads it. Both
   snowballs need no new fetch.
5. **Policy documents' own DOIs** (`keyed_other_identifiers.doi`) are read by the
   mapper already; the eval probes now count them too.
6. **Date fences and a code review, 2026-10-08.** OpenAlex forward chasing and the
   backward resolve are fenced server-side (`to_publication_date`); Overton searches
   by `published_before`; no review's own DOI appears in any candidate list. A Codex
   review of the eval scripts found eight issues, all fixed and the policy runs
   rebuilt from scratch: documents fetched by id in `policy_rank.py` had no date
   fence (22% of the forward step's documents were after the cutoff) and citing
   documents after the cutoff were counted in scores; the held-out strategy was only
   removed after the signals were built (checked: it never appeared in a search
   result, since the cutoff is its own date, so this was a safeguard); the probe
   cache was keyed without the request shape; title matching compared against every
   OpenAlex record while the write-up said DOI-less ones, and divided DOI recall by
   all references; the specific target set was not committed. The tables in this
   file are the rebuilt numbers; every change was under a point, and the snowball
   gained slightly. The targets are now a committed snapshot,
   `ground_truth/policy_gt_specific_targets.json`.

## 5. Suggested course of action

1. **Production slice for Overton** (one slice, small): `sort=relevance`; the
   question plus its two paraphrases as the Overton searches, 200 documents; the
   policy-to-policy snowball with specificity and similarity damping as the
   document order; the documents' own DOIs and cited papers into the paper pool;
   de-duplication by title; `source_country` exposed as a user option. The eval
   records global and UK-only measures.
2. **Do not spend more on the paper cut.** No route, seed set or ranking moved it
   beyond a point today. The union's extra papers need a larger screened pool, which
   is a budget decision, not a search one.
3. **Measure the policy side where it matters.** Add the four hand-made reviews'
   grey-literature references (with Overton ids or titles) to the ground truth. Build
   a small international target set so the global measure stands on its own
   instrument.
4. **Cheap untested levers, in order:** stop the similarity damper promoting documents
   that only one result cites (apply it to documents cited by two or more results,
   leave the rest in citation order); ranking the single-citation tail of `cites.policy` by title similarity (the
   titles come with the record, no calls); a document-type filter in front of coupling.
5. Run the paper route on the full 100-review set, where the gap-map rows weigh more.

## Scripts

All under `scripts/evals/search/measure/`, all dev-only, all cached, none uploads to
Langfuse. Run from the repository root with
`uv run --project backend --env-file backend/.env python <script> --help`.

| script | what it measures | output |
|---|---|---|
| `overton_recall.py` | the four probes and the seed-set variants (`--arms`) | `results/overton/scores.csv`, cache `cache/overton-<arm>/` |
| `merge_rank.py` | merged OpenAlex + Overton paper rankings (`--arm`, `--embed`) | `results/overton/merge/scores.csv` |
| `title_match.py` | the DOI blind spot by title matching (`--loose`, `--show`) | printed table |
| `policy_rank.py` | policy-document orders; `--manual QUESTION` writes top-25 tables; `--embed`, `--paraphrases`, `--source-country` | `results/overton/policy/` |
| `policy_gt.py` | the gov.uk ground truth, `--set omnibus` or `specific`, same options | `results/overton/policy_gt*/scores.csv` |

The specific set is the committed `ground_truth/policy_gt_specific.csv`.

## Terms

- **cap N**: the first N candidates of a ranked list. **ceiling**: every candidate, no cut.
- **in-set citations**: how many of the retrieved items cite a candidate (papers citing
  a paper on OpenAlex; policy documents citing a paper or a policy document on Overton).
- **specificity**: in-set citations divided by log10 of the global citation count plus
  ten; damps items everyone cites.
- **landmark**: a document cited by the retrieved set that the search itself did not
  return, fetched by id.
- **similarity damper**: multiplying a document's citation score by its embedding
  similarity to the question, so documents cited widely but off the question drop.
- **labelled**: a target that is a coded set of included studies (hand-made, 3ie, YEF);
  unlabelled targets (Campbell, SR4ALL) are whole reference lists, ceiling near 50%.
