# ADR 0038 — Single-pass search with citation chasing, and an adaptive screening vote

- **Status:** Accepted — 2026-10-12 (owner sign-off after the task 051 review; Proposed
  from 2026-10-09)
- **Date:** 2026-10-09
- **Task:** [051-improve-production-search-screen](../tasks/051-improve-production-search-screen/contract.md)
- **Supersedes:** [ADR 0012](0012-depth-graded-agentic-search.md) decisions 1 (the round
  cap and arms as depth constants), 3 (acquire↔screen rounds), 4 (fixed arm allocation)
  and 5 (screen-informed stopping and its stop vocabulary, which stays valid for
  historical rows only). ADR 0012 decisions 2, 6, 7 and 8 stand.
- **Amends:** [ADR 0011](0011-consensus-screening-two-stage.md) decision 1 (the
  three-sample majority becomes the adaptive vote below).

## Context

The task 015 search ran up to three rounds of acquire and screen at Broad and Broadest,
with four steering arms (reformulate, snowball, suggest, diversity) fed by screening
verdicts. None of the arms was measured on its own. The ground-truth evals of tasks 046
to 051 (recall of a published review's reference list, 15 reviews in the mini set)
measured the whole three-round Broadest at 15.3% on four reviews, and one pass of the
method below at 20.3% on fifteen reviews at the same pool size, with no screening inside
the search. Four defects were found on the way: Overton results were sorted by date, not
relevance (four times less paper recall); the search could not reach a paper no query
matched, although every OpenAlex record carries its reference list; the same Overton
document arrived twice under different sources; and stage-1 screening made three calls
per document on a model that is going away, with a prompt that treated every screening
criterion as a hard gate. The measurements are in
`scripts/evals/search/results/analyses/2026-10-09-design-experiments.md` and the write-ups
it cites; the owner's decisions are in the task's `notes.md`.

## Decisions

1. **One search pass at every scope; a scope is two caps.** Focused, Broad and Broadest
   run the same path once: query generation, seeds, citation chasing, ranking, cut,
   screen. They differ only in `papers_cap` and `policy_cap` (100/50, 200/100, 400/200)
   and share one call budget per backend (`DEPTH_CONSTANTS`, contract D1, D12).
2. **OpenAlex seeds are 15 keyword calls plus 8 semantic calls, interleaved by rank,
   first 200.** The five generated queries each as written and with the
   systematic-review and randomised-trial clauses, 200 results per call; the question,
   the two paraphrases and the five queries through `search.semantic`, 50 each. Query
   generation moves to `gpt-5.6-luna`; the prompt text is unchanged; `QUERY_MAX_CHARS`
   is 1,300 (contract D2, D3, D14).
3. **Backward snowball and forward chasing at every scope.** From the seeds' reference
   lists, the 200 works most cited by the seeds that are not seeds are resolved by id;
   for the 20 seeds with the most in-set citations (among seeds cited at most 300
   times) the works that cite them are fetched (`cites:` filter, 10 pages of 200 per
   100 ids) and scored by coupling and weighted coupling; the 200 best are kept
   (contract D4, D5).
4. **Papers are ranked by specificity, then cut.** `specificity = (in-set citations +
   coupling) / log10(cited_by_count + 10)`, ties by weighted coupling, in-set count, seed
   rank; the first `papers_cap` distinct works after task-level dedup are persisted and
   embedded. *Amended 2026-10-12 (task 052):* specificity alone let graph-found papers
   push the question's most direct matches past the Focused cap (one case: the target
   paper, returned by 9 of 33 queries, ranked 127 of 2,139). The pool is now first
   de-duplicated (same normalised title and same author names, the most cited copy
   kept, `pool.dedupe_papers`) and then ordered by `pool.rank_mix`: a round-robin over
   three strata, one paper from each in turn — *relevant* (reciprocal rank fusion,
   k = 60, over every keyword and semantic result list plus the pool ordered by
   weighted coupling, "cites the seeds", that order counted as three lists, so a paper
   that cites many seeds ranks as if a few queries had returned it), *seminal* (most
   cited by the seed set, then globally) and *novel* (published in the last five
   years, fused first). Papers the strata leave follow in
   specificity order. Every cut depth therefore holds all three kinds. Chosen over a
   single blended score because the guarantee holds at any cap, and over the
   relevance reserve (deferred D6) because a broad query's raw results carry
   off-topic papers into the reserve. Evidence: three pool re-orderings in
   `scripts/evals/search/experiments/manual/2026-10-12-rank-mix-*.md` (not scored
   against ground truth; the mini-set recall thresholds of task 051 have not been
   re-measured under the mix yet). The pool is built in memory before persistence; `acquire_sources` takes
   two ranked pools and two caps and keeps its count invariant; `source.acquired` and
   `search.executed` carry `query_origin` (contract D6, D7).
5. **Overton: relevance order, 400 documents, title dedup, policy snowball, cut.**
   Every search sends `sort=relevance` (a protected parameter). The three texts fetch
   400 documents interleaved by rank; duplicates by normalised title are dropped,
   keeping the best-ranked copy (titleless records keep their id as key); the 15 policy
   documents most cited by the results and not among them are fetched by id
   (landmarks); results and landmarks are ranked by `in-set / log10(citation_count +
   10)` and cut at `policy_cap`. Overton's cited papers do not enter the paper pool
   (contract D8, D9).
6. **Filters fail closed.** The plan's OpenAlex wire filters go on every OpenAlex call.
   The semantic endpoint accepts only `type`, `language` and `is_retracted` of the
   directive's filters and a `publication_year` fence (probe of 2026-10-09). A filter
   the endpoint rejects is applied locally to the semantic results instead (the date
   range over `publication_date`, with a year fence on the wire; SDG ids, the paratext
   flag, OA status and authorship countries over the fetched fields), and the coverage
   record lists the locally applied keys as `semantic_local_filters` (owner amendment
   of contract D13 at build, 2026-10-09: the rule as written would have skipped the
   semantic leg on every dated plan and every eval item). The resolve and forward calls
   carry every wire filter except the
   affiliation-country filter, which is applied locally to citation-found papers. The
   Overton filters go on the searches and the `source_country` post-filter on the
   landmarks (contract D13).
7. **Stage-1 screening is one adaptive vote on `gpt-5.6-luna` with `screen_v4`.** One
   call per document; a second call only when the first says `not_relevant`; keep when
   the second says `relevant` or `unsure`; two `not_relevant` drop; a failed second call
   keeps the first call's verdict with a flag; a failed first call is `failed` and
   retried on the next run. Confidence is the consensus probability over the calls made
   (the ADR 0011 formula over one or two calls). Title-only documents follow the same
   table. The decision is one pure function, `decide_stage1`, which the screening eval
   imports. Stage 2 is unchanged (contract D10).
8. **The round loop's orchestration is deleted; its restore point is tagged; its prompt
   pieces stay.** Gone: the round-2 branch of `run_search`, the exemplar reader, the
   four arms, the stop evaluation and the runner's round gate, with the tests that pin
   them. Kept, tested and unreachable from the runner: the reformulate and suggest
   prompt builders, wires and backend methods, because the prompts are the expensive
   part to recreate. The coverage record's `stop_condition` is now written as
   `completed` or `error` only; `re_searched_still_thin`, `short_circuit`,
   `budget_exhausted` and `target_reached` remain valid for historical rows. Restore
   recipe: the tag `search-round-loop-last` marks the last commit on which the loop
   runs end to end (`5d5c044`); `git checkout search-round-loop-last -- <path>` for
   `search_loop.py`, `runner.py`, `test_search_loop_deep.py` and `test_search_rounds.py`,
   then re-wire the arm's output to the pool hand-off of decision 4 (contract D11).
9. **The two legs run in parallel and the OpenAlex calls in concurrent batches**
   (owner amendment, plan Phase 3c, 2026-10-09). Each backend leg runs on its own
   thread with its own call budget; the seed, resolve and forward-page calls of a leg
   are submitted together to a pool of `SEARCH_CONCURRENCY` (8) workers and recorded
   in plan order whatever the thread timing. The live transport paces admissions
   behind one lock per backend instance (the interval sleep inside the lock, the
   request outside), and a 429 reply pushes every later admission on that backend out
   by `RATE_LIMIT_PAUSE_S` (1 s), coalesced so a burst of refusals pauses once. Measured
   on the mini set: about 41 to 47 s of search per review at every scope against about
   130 s sequential.

## Consequences

- Egress per search rises to 37 logical OpenAlex calls per filter variant (budget 45)
  and 18 Overton calls (budget 30), all through `search_live.py` with its timeouts,
  limiters, retry cap and redaction; two new OpenAlex request shapes (semantic search,
  `cites:` chase) and two Overton changes (`sort=relevance`, fetch by id). Screening
  calls per document fall from 3 to about 1.3 while documents per run rise to about
  150 / 300 / 600.
- No schema change. The historical stop values stay in the check constraint for old
  rows.
- Parked, with their measurements, in `docs/deferred.md`: the relevance reserve, the
  similarity damping of the policy ranking, the reformulation contingency for Broadest
  (+3.9 points at the ceiling in experiment 4), seminal-decile scoring in the eval,
  Overton records with a removed title, and the `source_country` plan option.
- The agent's triage model no longer borrows the screening model: it keeps its own
  literal default, so this slice changes only the two model ids the contract names.

## Rejected

- **Screened seeds** (screening the 200 seeds before chasing): changes nothing
  measurable (experiment 3), so no part of the search needs a screening verdict.
- **Keeping the loop behind a flag**: an unmeasured code path that every change must
  carry; the tag is the cheaper restore point.
- **A one-call screen with no second call**: 0.7 points of recall below the adaptive
  vote on the labelled set for the same cost class; the second call on a
  `not_relevant` is where the recall is.
