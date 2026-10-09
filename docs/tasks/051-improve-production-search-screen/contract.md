# Task contract: 051-improve-production-search-screen

> **Status:** drafted 2026-10-09; Codex contract-stage review (read-only, same day) returned
> 12 findings, all folded in: 2 blockers (the acceptance eval depended on the deleted loop
> constants, now in scope as D17; semantic-search filters were silently dropped, now
> fail-closed in D3/D13), 5 high (pre-persistence pool and provenance, D6/D7; fixtures and
> stubs grow the new verbs, § Surfaces; call budgets defined as logical operations with an
> HTTP ceiling, D12; the screening eval's vote helper in scope, D10; ADR supersession widened
> to ADR 0012 decisions 1, 3, 4 and 5, D16), 4 medium (title-dedup guard, D8; adaptive-vote
> truth table and confidence formula, D10; live-check spend as a range with a ceiling,
> § Constraints; policy-side replay tests, § Acceptance checks), 1 low (relevance-reserve
> wording in the write-up and the tutorial, corrected). Contract approved (before
> planning): 2026-10-09 · owner (go-ahead to plan, after the Codex review was folded in) · Plan approved (before implementation): 2026-10-09 · owner ·
> ADR: 0038 (step 4; supersedes ADR 0012 decisions 1, 3, 4 and 5; amends ADR 0011 decision 1).
> **Amendments at planning (2026-10-09, from the Codex plan-stage review, for the owner's
> re-confirmation at the plan gate):** D12 call accounting corrected (Overton pages inside
> one logical search as today, so 18 logical Overton calls, not 24; OpenAlex budget per
> filter variant); D13 states the variant rule for citation-found papers; D19 names the
> existing fixture backends (`OpenAlexFixtureBackend`, `OvertonFixtureBackend`) in place of
> a stub class that does not exist; § Deliverable names the exploration artefacts committed
> at the design-phase boundary, which are not build work. **Owner decision at the plan gate
> (2026-10-09):** the round loop's orchestration is deleted, but its last working commit is
> tagged `search-round-loop-last` as the restore point, and the reformulate and suggest
> prompt builders, wires, backend methods and their tests stay in the tree (D11).

## Goal

Make the app's search find more of the evidence a review would cite, at lower cost, with
one simpler mechanism. Today a Broad search finds 5% of a published review's reference
list on the 15-review mini ground truth (`scripts/evals/search/results/history.md`,
2026-10-05); the experiments of tasks 047, 049, 050 and 051 reached 20% at the same pool
size with a single search pass and no screening inside the search
(`scripts/evals/search/results/analyses/2026-10-09-design-experiments.md`). Screening
moves to a cheaper model and a better prompt that the task 050 eval measured at higher
recall for a fifth of the cost. The design is the one in
`docs/tutorials/search-and-screen/index.html`, Diagram D, with the decisions the owner
took on 2026-10-09 (`notes.md`).

## Problems

One number each. The rubric and the plan use the same numbers.

- **P1 — Overton results are sorted by date, not relevance.** `OvertonLiveBackend._search`
  sends no `sort`, and the service defaults to date. The 200 records kept are the newest
  above similarity 0.3, not the best. Measured: four times less paper recall than relevance
  order (1.7% against 7.7% at 200). Owner-confirmed bug (2026-10-07).
- **P2 — The search keeps what the queries return and cannot reach a paper no query
  matches.** Results are interleaved by rank and cut. Every OpenAlex record carries its
  reference list and citation count, and nothing reads them except a 40-record arm at
  Broadest. Citation chasing from the search results triples recall (3.1% to 10.3% from
  one raw query; 7.0% to 15.2% from the generated queries) and finds the seminal works
  (seminal-decile recall 7% to 42%).
- **P3 — The round loop is unmeasured, complex, and beaten by one pass.** Broad and
  Broadest repeat acquire and screen up to three times with four arms (reformulate,
  snowball, suggest, diversity) steered by screening verdicts. None of the four was ever
  measured on its own. The whole three-round Broadest measured 15.3% on four reviews; one
  pass of the new method measures 20.3% on fifteen at the same pool size. Screened seeds
  were tested and change nothing (experiment 3), so no part of the search needs a
  screening verdict.
- **P4 — Screening costs three calls per document on a model that is going away, with a
  prompt that over-applies criteria.** `gpt-5.4-mini` is not available after the Bedrock
  migration. The three-call majority adds 0.7 points of recall for three times the cost.
  With a plan's screening criteria present, `screen_v2` loses 4 to 7 points of recall
  because the model treats each criterion as a hard gate.
- **P5 — The key policy documents are cited by the results but not returned.** Overton's
  relevance order puts committee submissions first; the strategies and evidence reviews on
  a topic sit in the results' citation lists. A policy-to-policy snowball with specificity
  finds in 50 documents what relevance order finds in 200 (6.0% against 3.5% at 25 on the
  gov.uk instrument). Owner decision 2026-10-07: adopt it.
- **P6 — The same Overton document arrives twice under different sources.** Seen on every
  question tried in task 049 (a submission as "government" and as "think tank").
- **P7 — Query generation runs on `gpt-5.4-mini`.** Not available after Bedrock. Luna
  measured 2 points lower at 100 to 200 candidates and equal at 300 and 400.
- **P8 — A generated query between 1,300 and 2,000 characters passes validation and fails
  at OpenAlex** (`QUERY_MAX_CHARS` is 2,000; the service refuses searches over 1,500, and
  the review and trial variants add about 130). Found in task 047; no effect with today's
  short queries.
- **P9 — The app says "up to 50 relevant results per database".** The scope hint, the
  planner prompt and the frontend constant carry the old caps and one number per scope.

## Deliverable

One pull request on `task/051-improve-production-search-screen` that lands the search
and screen described in § Decisions, the deleted round loop, the model and prompt
changes, the app text, the tests, ADR 0038, the spec update, and `verification.md` with
the end-to-end measurement (§ Acceptance checks).

Committed before the build, as the design-phase commit, and not build work: the
exploration artefacts of 2026-10-09 (`docs/tutorials/search-and-screen/index.html`,
`docs/tasks/051-improve-production-search-screen/notes.md`,
`scripts/evals/search/results/analyses/2026-10-09-design-experiments.md`,
`scripts/evals/search/experiments/screened_seeds.py` and `reformulate_gain.py`, and the
owner-requested split of `scripts/evals/{search,screening}/measure/` into `checks/` and
`experiments/` with its path updates), plus this contract, rubric and plan.

Shipped means: a Focused, Broad or Broadest run searches once, screens once, and
`production_recall.py` on the mini set reports search recall within 3 points of the
experiment at each scope, screen recall at or above 90% of search recall, and the cost
and wall clock per review.

## Terms

| Term | Meaning |
|---|---|
| **Scope** | The app's "Search scope": Focused, Broad, Broadest. In the code `search_effort` with values `rapid`, `standard`, `deep`. This slice does not rename anything; the three values stay. |
| **Seeds** | The records the searches return before any citation chasing. OpenAlex: the first 200 after interleaving the keyword and semantic calls. Overton: the documents the three semantic searches return. |
| **Backward snowball** | Count how many seeds cite each work, using the seeds' reference lists (`referenced_works`, returned with the record). Resolve the most-cited works the seeds do not include. |
| **Forward chasing** | For the seeds with the most in-set citations, fetch the works that cite them (OpenAlex `cites:` filter) and score each by how many seeds it cites. |
| **In-set citations** | How many of the retrieved set cite a candidate. OpenAlex: seeds citing a paper. Overton: results citing a policy document. The field `inset` in the experiment tables. |
| **Coupling** | How many seeds a candidate cites. Known for seeds and forward candidates (their reference lists are fetched); zero for backward candidates. |
| **Specificity** | `(in-set citations + coupling) / log10(global citations + 10)` for papers; `in-set citations / log10(citation_count + 10)` for policy documents. Damps works everyone cites. The paper ranking is the one experiment 1 measured. |
| **Landmark** | A policy document cited by the Overton results that the search itself did not return, fetched by id. |
| **Paper pool, policy pool** | The two ranked candidate lists a scope cuts: papers from OpenAlex (seeds, backward, forward), policy documents from Overton (results, landmarks). Overton's cited papers do not enter the paper pool (D9). |
| **Papers cap, policy cap** | The two numbers a scope sets: how many papers and how many policy documents are kept after ranking and dedup. They replace `record_cap_per_backend`. |
| **Adaptive vote** | The stage-1 screening rule: one call per document; a second call only when the first says `not_relevant`; keep when the second says `relevant` or `unsure`. Measured on the labelled set at 0.917 recall and 1.54 calls per document (task 050); on real search candidates at 97% of ground-truth seeds kept and 1.3 calls per document (experiment 3). |
| **Luna** | `gpt-5.6-luna`, the OpenAI model the slice moves query generation and screening to. The screen prompt `screen_v4` was tuned on it. |
| **Mini set, full set** | `retrieval-ground-truth-mini` (15 reviews) and `retrieval-ground-truth-full` (100), Langfuse datasets. Recall is the share of a review's reference list found, scored on DOIs. Paper side only. |
| **gov.uk instrument** | The policy-side ground truth of task 049: 15 topic-specific government strategies, target = the policy documents each cites. For comparing orders, not for a level. |
| **Screened** | Stage-1 screened. Stage 2 (full text, demote-only) is unchanged by this slice. |

## Read first

- `docs/tutorials/search-and-screen/index.html` — the as-built map (Diagrams A to C) and the design (Diagram D).
- `scripts/evals/search/results/analyses/2026-10-09-design-experiments.md`,
  `2026-10-06-search-experiments.md` (sections 2, 5, 7, 9, 11), `2026-10-07-overton-experiments.md`
  (sections 2.1, 3, 4) and `scripts/evals/screening/results/analyses/2026-10-08-screening-experiments.md` (key results, section 3) — the measurements every decision below cites.
- `docs/tasks/051-improve-production-search-screen/notes.md` — the owner's decisions of 2026-10-09.
- `docs/specs/capabilities/evidence-search/components.md` §1 acquire and §2 screen, and ADR 0012 — what this slice supersedes (the "deep = acquire↔screen rounds" paragraph and decisions 3 and 4). ADR 0011 — the screening consensus this slice changes.
- Code: `sourcing/search_loop.py` (`DEPTH_CONSTANTS`, `run_search`, `_rapid_plans`, `evaluate_deep_stop`, `finalise_deep_stop`), `sourcing/acquire.py` (`_interleave`, `acquire_sources`, `_map_overton_document`, `_OVERTON_RETAIN_KEYS`), `sourcing/search_live.py` (`OpenAlexLiveBackend`, `OvertonLiveBackend._search`, `_PROTECTED_OVERTON_PARAMS`), `assess/screen.py` (`_run_stage1_reps`, `_run_stage1`), `assess/screen_prompt.py`, `runtime/runner.py` (`_search_round_continues` and the classify-pop gate), `runtime/task_plan.py` (`SEARCH_EFFORT_DIRECTIVES`), `runtime/planner_prompt.py` (the thoroughness section), `frontend/src/views/workspace/planVocabulary.ts`.
- Experiment code the production code mirrors: `scripts/evals/search/experiments/snowball_recall.py` (`expand`, `forward_chase`, `candidates`, `rank`, `semantic_page`, `interleave_ids`), `policy_rank.py` (`build`, `order`), `scripts/evals/screening/prompts/screen_v4.txt`, `scripts/evals/screening/vote.py`.

## Surfaces

What the slice touches, and what it must leave alone.

| Surface | File | Today | After |
|---|---|---|---|
| Scope constants | `sourcing/search_loop.py` `DEPTH_CONSTANTS` | per-call result cap, record cap per backend, round cap, call budgets, arms | papers cap, policy cap, call budgets (D1, D12) |
| Round 1 plan | `search_loop.py` `_rapid_plans`, `run_search` | keyword 5 × 3 forms; Overton question + 2 paraphrases | the same keyword calls plus 8 semantic calls; Overton the same texts, 400 documents, relevance (D3, D8) |
| Rounds 2–3 | `search_loop.py` (reformulate, snowball, suggest, diversity arms, exemplar reader, `evaluate_deep_stop`, `finalise_deep_stop`), `runner.py` `_search_round_continues` and the classify-pop gate | run at Broad and Broadest | deleted (D11) |
| Citation chasing | new code in `sourcing/` (D4, D5) | 40-record arm at Broadest | backward snowball and forward chasing at every scope |
| Merge and cut | `acquire.py` `_interleave`, `record_cap_per_backend` | interleave by rank, cut per backend | two ranked pools, two caps (D6, D7, D8) |
| Overton transport | `search_live.py` `OvertonLiveBackend` | no `sort`; no fetch by id | `sort=relevance` protected; `fetch_by_id`; dedup by title (P1, P6, D8) |
| OpenAlex transport | `search_live.py` `OpenAlexLiveBackend` | keyword search, `fetch_citations`, `fetch_references`, lookups | plus semantic search and a batched resolve by id (D3, D4) |
| Query generation | `sourcing/search_prompts.py` `SEARCH_QUERIES_MODEL`, `QUERY_MAX_CHARS` | `gpt-5.4-mini`, 2,000 | `gpt-5.6-luna`, 1,300 (D2, D14). Prompt text unchanged. |
| Screening | `assess/screen.py`, `assess/screen_prompt.py` | 3 calls, majority, quorum 2, `gpt-5.4-mini`, `screen_v2` | adaptive vote, `gpt-5.6-luna`, `screen_v4` (D10). Stage 2 unchanged. |
| Prompt pins | `scripts/prompt_hashes.json` | pins `screen_prompt.py`, `search_prompts.py`, `planner_prompt.py` | re-pinned for the three edited modules |
| App text | `runtime/planner_prompt.py` thoroughness section; `frontend/src/views/workspace/planVocabulary.ts` and its tests | "up to 50 / 100 / 200 relevant results per database" | two numbers per scope (D15) |
| Coverage record | `search_coverage_record.stop_condition` | `completed`, loop stops, thin overlay | `completed` or `error`; no schema change (D11) |
| Spec and ADR | `components.md` §1, §2; `docs/adr/0038-*.md`; `docs/specs/log.md` | describes the loop | describes the single pass (D16) |
| Tutorial page | `docs/tutorials/search-and-screen/index.html` | Diagrams A to C map the old design; Diagram D is a proposal | Diagrams and text describe the implemented design as built, with the measured numbers (D20) |
| Eval, search | `scripts/evals/search/checks/production_recall.py`, `checks/engine.py` (and its recording backend wrapper) | reads `record_cap_per_backend`, `result_cap_per_backend`, `round_cap`; screening off at `rapid`; `run_one_query` mirrors the round loop | reads `papers_cap`, `policy_cap`, `call_budget`; screening on at every depth; one search, one screen; the wrapper proxies the new verbs (D17) |
| Eval, screening | `scripts/evals/screening/vote.py`, `checks/run_screen.py` | majority vote, imports `SCREEN_QUORUM`, mutates `SCREEN_REPS` | imports the production decision function; `--reps` keeps its meaning for majority experiments, `--vote adaptive` runs the production rule (D10) |
| Fixtures | `OpenAlexFixtureBackend` and `OvertonFixtureBackend` in `backend/tests/provider_fixtures.py`, fixture mode in `run_search` | one verbatim call per backend; no semantic, resolve, chase or fetch-by-id | zero egress kept; the stubs and fixtures answer the new verbs deterministically; fixture mode runs the single pass (D19) |
| **Do not change** | stage-2 screening; `effective_screen_rows`; `screen_generation` and `uq_ssr_scope_source_stage`; classify, appraise and everything after screening; the plan directive grammar (`parse_search_directive`, `validate_scope_filters`); the schema; the embedding of persisted chunks; the zero-egress guarantee of the stubs and fixtures | | |

## Decisions

- **D1 — One search pass at every scope; a scope is two caps.** Focused, Broad and
  Broadest run the same code path once: query generation, seeds, citation chasing,
  ranking, cut, screen. They differ only in the two numbers below. Measured paper recall
  is experiment 1 with Luna on the mini set.

  | scope | papers cap | policy cap | paper recall measured | documents screened, about |
  |---|---:|---:|---:|---:|
  | Focused (`rapid`) | 100 | 50 | 15.5% | 150 |
  | Broad (`standard`) | 200 | 100 | 20.3% | 300 |
  | Broadest (`deep`) | 400 | 200 | 27.6% | 600 |

- **D2 — Query generation on Luna, prompt unchanged.** `SEARCH_QUERIES_MODEL` becomes
  `gpt-5.6-luna`. `search_queries_system_v3.txt` is not edited: fourteen prompt variants
  landed within two points (task 047). The task 047 write-up's "Luna recommendation"
  (switch to the synonym-block prompt `exp_d` with Luna) predates the semantic seeds
  and does not hold for the final configuration: on the mini set at 200 / 400
  candidates, Luna with the production prompt measures 20.3% / 27.6%; Luna with `exp_d`
  measures 19.6% / 24.0% with semantic seeds from the question and paraphrases and
  16.8% / 24.7% with all texts, because `exp_d`'s boolean blocks are poor input for the
  semantic engine (run folders `2026-10-09-shared+semantic-c6e320-gpt-5.6-luna-*` and
  `2026-10-06-shared+semantic-db9280-gpt-5.6-luna-*`). One run each; checked
  2026-10-09 at the owner's request. `SEARCH_REFORMULATE_MODEL` and
  `SEARCH_SUGGEST_MODEL` go with their arms (D11).
- **D3 — OpenAlex seeds: 15 keyword calls plus 8 semantic calls, 200 seeds.** The 5
  generated queries, each as written and with the systematic-review and randomised-trial
  clauses, 200 results per call (the experiments' size; today's 50 to 100 per call was
  sized for a smaller cut). Plus the question, the 2 paraphrases and the 5 queries sent
  to OpenAlex semantic search (`search.semantic`), 50 results each, one call per second.
  The 23 result lists are interleaved by rank as `_interleave` does today; the first 200
  distinct works are the seeds. Keyword searches carry the plan's OpenAlex filters as
  today. The semantic endpoint accepts some filters (the experiment sent
  `publication_year`) and rejects others (`to_publication_date`); which of the plan's
  OpenAlex filter keys it accepts is settled by the pre-build probe, and the rule for
  the rest is fail-closed (D13). Measured: keyword-only seeds 16.3%, with semantic 22.2%
  (current model) at 200.
- **D4 — Backward snowball.** From the seeds' `referenced_works` (requested in the
  search `select`, so no extra call) count how many seeds cite each work; drop works
  that are seeds; resolve the 200 most-cited by `openalex_id` filter, 50 per call (4
  calls), with the same `select` as a search. `OA_SELECT` already returns
  `referenced_works` and `cited_by_count`; no new field is requested. The persisted `provider_fields` keep
  `referenced_works` capped at `REFERENCED_WORKS_RETAIN_CAP` as today; the full lists are
  used in memory only.
- **D5 — Forward chasing.** Take the 20 seeds with the most in-set citations among seeds
  cited at most 300 times (a seed with thousands of citations floods the result); fetch
  the works that cite them with the `cites:` filter, 100 ids per call, 10 pages of 200;
  for each citing work compute coupling (how many seeds it cites) and weighted coupling
  (`sum of log2(1 + in-set count of each cited seed)`); keep the 200 best by weighted
  coupling, then coupling, that are not seeds and not backward candidates. Measured gain
  at 200: 15.2% to 16.3% (keyword seeds, current model).
- **D6 — Paper ranking: specificity, then cut.** Every paper candidate (seed, backward,
  forward) is scored `specificity = (inset + coupling) / log10(cited_by_count + 10)`,
  ties broken by weighted coupling, then in-set count, then seed rank. The first
  `papers cap` distinct works after task-level dedup (record id, DOI, text hash, as
  `is_new` does today) are persisted. The experiment's "relevance reserve" (the first 50
  keyword results held in their own order) was never implemented or measured and is not
  built; recorded as a seam in `docs/deferred.md`.
- **D7 — A pool phase before persistence, and provenance.** Today `acquire_sources`
  interleaves the `search` calls, dedups, cuts, and persists the targeted verbs
  (snowball, suggest) untrimmed; it cannot rank one pool across seeds, backward and
  forward candidates. After this slice `run_search` builds the two ranked pools (each
  candidate with its origin and its ranking signals) and hands `acquire_sources` two
  ordered candidate lists; `acquire_sources` maps, dedups in that order with `is_new`
  as today, cuts each pool at its cap, and persists and embeds only the kept records.
  The `search.executed` event per call carries `query_origin` as today, extended with
  `semantic`; `source.acquired` gains `query_origin` (it has none today) with the
  values `generated`, `variant_sr`, `variant_rct`, `verbatim`, `paraphrase`,
  `semantic`, `snowball_backward`, `snowball_forward`, `landmark`. The coverage
  record's `by_backend` counts keep `results_returned`, `acquired`, `already_acquired`,
  `skipped_unusable`, `dropped_over_cap` and their sum invariant. No new table or
  column. Tests: mixed-origin dedup keeps the best-ranked copy; the cap counts each
  pool; only kept candidates are embedded and persisted; both events carry the origin.
- **D8 — Overton: relevance order, 400 documents, title dedup, policy snowball, cut.**
  `_search` sends `sort=relevance`, and `sort` joins `_PROTECTED_OVERTON_PARAMS`. The
  three texts (question, 2 paraphrases) fetch 400 documents in total, interleaved by
  rank (3 pages of 50 per text, 9 calls at 1.2 s). Duplicates by normalised title
  (lower-case, punctuation and whitespace collapsed) are dropped, keeping the best-ranked
  copy; the dedup key is the normalised title when it is non-empty, else the
  `policy_document_id`, so titleless records never collapse into one. Records the
  mapper already marks unusable (no native and no translated title) stay skipped and
  counted; records whose title is a placeholder string are kept (D18, parked). From every result's `cites.policy` count how many results cite each policy
  document; fetch the 15 most-cited that are not results by `policy_document_id` (15
  calls); rank results and landmarks by `inset / log10(citation_count + 10)`, ties by
  Overton's order (`es_score`); keep the first `policy cap`. The plan's Overton filters
  apply to the three searches; the `source_country` post-filter also applies to the
  landmarks. Measured: the 400-document pool with paraphrases is experiment 5's.
  **Similarity damping** (the embedding term the owner agreed in principle on
  2026-10-07) is not built in this slice: it needs about 5 embedding calls before the
  cut, its one side effect has an untested fix, and the measured policy numbers are
  without it. Recorded as a seam with its measured by-eye effect.
- **D9 — Overton's cited papers stay out of the paper pool** (owner, 2026-10-09).
  `cites` stays in `_OVERTON_RETAIN_KEYS`; nothing resolves `cites.scholarly`.
- **D10 — Screening: Luna, `screen_v4`, adaptive vote.** `SCREEN_MODEL` becomes
  `gpt-5.6-luna`. `SCREEN_SYSTEM_PROMPT` becomes the text of
  `scripts/evals/screening/prompts/screen_v4.txt` (the three measured changes to
  `screen_v2`: a clearly different population excludes only when the intent names one;
  a partial match on another element is `relevant` or `unsure`; a criterion the abstract
  does not report never excludes), version label `screen_v4`, hash re-pinned. The decision is one pure function,
  `decide_stage1(first, second)`, used by production and imported by the screening
  eval's `vote.py` (which drops its `SCREEN_QUORUM` import). Stage 1 makes one call per
  document in parallel as today, with the existing one-retry rule per call; then one
  more call, in a second parallel batch, for every document whose first valid reply is
  `not_relevant`. Truth table:

  | first call | second call | status |
  |---|---|---|
  | `relevant` or `unsure` | none | `relevant` |
  | `not_relevant` | `relevant` or `unsure` | `relevant` (flag `second_call_kept`) |
  | `not_relevant` | `not_relevant` | `not_relevant` |
  | `not_relevant` | failed after retry | `not_relevant` on the first call alone (flag `second_call_failed`) |
  | failed after retry | not made | `failed` (retried on the next screen run, as today) |
  | malformed reply | counts as failed | as the row above |

  Confidence: `mean_p` over the valid calls made, where `p` is the call's confidence
  for `relevant`, one minus it for `not_relevant`, and 0.5 for `unsure`; stored as
  `mean_p` when the status is `relevant` and `1 - mean_p` when `not_relevant` (the
  ADR 0011 formula over one or two calls; a reversal such as `not_relevant` 0.9 then
  `unsure` stores 0.3, kept-but-shaky). Title-only documents follow the same table.
  `SCREEN_REPS` and `SCREEN_QUORUM` go; the `reps` payload of the `source.screened`
  event lists the calls made in order, failures included. Stage 2 is untouched. Measured: 0.917
  recall on the labelled mini set with criteria, 0.900 on the full set; on real
  candidates 97% of ground-truth seeds kept at 1.3 calls per document.
- **D11 — The round loop's orchestration is deleted; its restore point is tagged; its
  prompt pieces stay.** Gone: the round-2 branch of `run_search`, the exemplar reader
  and `ExemplarRecord` use in search, the reformulate, snowball, suggest and diversity
  arms, `ArmName`, `evaluate_deep_stop`, `finalise_deep_stop`,
  `new_confident_relevant_for_run`, the runner's `_search_round_continues` and its
  classify-pop gate, and the tests that pin them (`test_search_loop_deep.py` deep-round
  tests, `test_search_rounds.py`). Kept, tested and unreachable from the runner: the
  reformulate and suggest prompt builders and wires in `search_prompts.py`, the
  `reformulate` and `suggest` methods of the generation backends, `ExemplarRecord`,
  `SEARCH_REFORMULATE_MODEL` and `SEARCH_SUGGEST_MODEL` (set to `gpt-5.6-luna` with
  the query model), and their unit tests, because the prompts are the expensive part to
  recreate and they have no coupling to acquire or the database. **Restore point:** the
  design-phase commit (Phase 0a), the last commit on which the loop runs end to end, is
  tagged `search-round-loop-last`; the tag is named in ADR 0038 and `docs/deferred.md`
  with the restore recipe (`git checkout search-round-loop-last -- <path>` for
  `search_loop.py`, `runner.py` and the two test files, then re-wire the arm's output to
  the pool hand-off of D7). The owner's condition (2026-10-09): deletion only because
  restoring is one command per file plus a small re-wiring slice. The
  `search_coverage_record` stop vocabulary is unchanged (no schema change);
  acquire writes `completed`, or `error`, as it does for a rapid run today;
  `re_searched_still_thin`, `short_circuit`, `budget_exhausted` and `target_reached`
  remain valid for historical rows and are no longer written.
  `confident_relevant_count` stays as a helper. Reformulation, the one arm with
  measured value (+3.9 points at the ceiling, experiment 4), is recorded in
  `docs/deferred.md` as a parked contingency for Broadest: search, screen, reformulate
  from screened exemplars, one more search, screen the new documents. Its prompt
  builder stays in the tree; its orchestration is at the tag.
- **D12 — `DEPTH_CONSTANTS` becomes three rows of `papers_cap`, `policy_cap`,
  `call_budget`.** A call budget counts logical operations as `execute_call` counts
  them today, one per planned query, resolve batch, forward page or landmark fetch:
  OpenAlex 37 planned per filter variant (15 keyword, 8 semantic, 4 resolve, 10 forward
  pages), budget 45 per variant (`_filter_variants` yields 1 variant, or 2 when the plan
  names 101 to 200 affiliation countries; the budget is `45 × variants`); Overton 18
  planned (3 searches, each paging inside the backend to its share of 400 documents as
  `_search` pages today, plus 15 landmark fetches), budget 30. The HTTP ceiling is the
  transport's: one page per keyword call at 200 per page, one per semantic call, one per
  resolve batch, one per forward page, up to 3 pages per Overton search and one per
  landmark fetch, each with the retry cap of `_request_json` (4 attempts), so at most
  4 × (OpenAlex budget) and 4 × (3 × 3 + 15) Overton HTTP attempts per run; the
  `search.executed` event of an Overton search records its page count; the coverage record keeps the logical count and the
  `search.executed` events carry one row per logical call. A backend at its budget
  skips the remaining calls and the coverage record says so, as today.
  `parse_search_directive` and the directive grammar are unchanged. Tests: a full-page
  call, a retried call and a provider page smaller than requested each count as one
  logical call.
- **D13 — Filters, fail-closed.** The plan's OpenAlex wire filters go on every OpenAlex
  call: keyword searches, the backward resolve, the forward chase, and the semantic
  calls for the filter keys the pre-build probe shows the semantic endpoint accepts
  (the probe tries every key `_OPENALEX_FILTER_KEYS` can emit). Filter variants (two
  when the plan names more than 100 affiliation countries) multiply the keyword and
  semantic seed calls as they multiply searches today; the resolve and forward calls
  carry every wire filter except the affiliation-country filter, which is applied to
  citation-found papers locally over `authorships[].countries` (in `OA_SELECT`), one
  predicate for both variants, so the directive holds without doubling those calls. When a run's directive
  carries an OpenAlex filter the semantic endpoint rejects, the semantic calls are
  skipped for that run, the coverage record records `semantic_skipped: <keys>` in its
  `scope_filters` payload, and the seeds come from the keyword calls alone. The
  directive is never weakened silently. The Overton filters go on the searches and the `source_country`
  post-filter on the landmarks. `search_backend_scope` still selects the backends: with
  one backend absent, its pool is empty and the other runs unchanged.
- **D14 — `QUERY_MAX_CHARS` 1,300.** A generated query above it is dropped at
  validation with the existing `queries_zero_result` style of count.
- **D15 — App text.** The scope hint reads "Focused: up to 100 papers and 50 policy
  documents", and so on; `SEARCH_SCOPE_RECORD_CAP` becomes a pair per scope; the planner
  prompt's thoroughness section carries the same numbers and its hash is re-pinned. The
  three presets and their timing bands are unchanged in wording; the bands are re-read
  against the measured wall clock in `verification.md` and corrected in a follow-up if
  they are wrong by more than a band.
- **D16 — Spec and ADR.** `components.md` §1 acquire: the as-built paragraph is replaced
  by the single-pass description; §2 screen: the "deep loop's judge" sentence goes and
  the consensus sentence says adaptive vote. ADR 0038 records the design and supersedes ADR 0012
  decisions 1 (the round cap and arms as depth constants), 3 (acquire↔screen rounds),
  4 (fixed arm allocation) and 5 (screen-informed stopping and its stop vocabulary,
  which stays valid for historical rows only), and amends ADR 0011 decision 1 (the
  three-rep majority becomes the adaptive vote). One line in
  `docs/specs/log.md`.
- **D17 — The acceptance eval follows the pipeline.** `checks/engine.py` and
  `checks/production_recall.py` read the loop constants and skip screening at `rapid`,
  so they are in scope: `run_one_query` becomes one search and one screen at every
  depth, the run metadata records `papers_cap`, `policy_cap`, `call_budget` and
  `screening=True`, the recording wrapper proxies the new backend verbs, and a test
  proves a `rapid` run screens. `history.py` and `history.md` keep their columns. The
  live check runs it at `rapid`, `standard` and `deep` on the mini set, and at
  `standard` on the full set on the owner's go (§ Constraints). Seminal-decile recall
  as a Langfuse score is deferred (the experiment script reports it).
- **D20 — The tutorial page follows the implementation** (owner, 2026-10-09). After the
  build, `docs/tutorials/search-and-screen/index.html` is rewritten so its diagrams and
  text describe the search and screen as built: the single pass as the main diagrams,
  with the real constants, verbs, call counts and the adaptive vote read from the code;
  the old design kept only as a short "what it replaced" section; the measured recall,
  cost and wall clock from the live check in place of the experiment numbers; the
  proposal sections removed. Written in the same style as the experiment pages.
- **D19 — Fixtures grow the new verbs; egress stays zero.** The zero-egress doubles are
  `OpenAlexFixtureBackend` and `OvertonFixtureBackend` in `backend/tests/provider_fixtures.py`
  (there is no product stub class); they answer semantic search, batched resolve,
  forward chase and Overton fetch-by-id deterministically from fixture data; fixture mode in `run_search`
  runs the single pass (not one verbatim call per backend); the eval's recording wrapper
  proxies the same verbs. Tests: a fixture-mode single-pass run; a one-backend run
  (`search_backend_scope` with OpenAlex only and with Overton only).
- **D18 — Out of this slice, recorded.** Overton records with a removed title (parked
  by the owner); the `source_country` filter as a user-facing plan option (the directive
  exists; exposing it is a plan-document change); similarity damping (D8); the relevance
  reserve (D6); the reformulation contingency (D11); seminal-decile scoring (D17).

## Scope / Out of scope

- **In:** the surfaces table (the eval checks, the screening vote helper, the stubs and
  fixtures included); new unit tests for the ranking, the caps, the title
  dedup, the adaptive vote and the Overton `sort` parameter; the deleted tests replaced
  by single-pass tests of the same provenance invariants (no screening rows written by
  acquire; coverage record per run; `dropped_over_cap` visible); the frontend constant
  and hint text with their tests; prompt pins; ADR 0038; the spec update;
  `docs/deferred.md` entries for D6, D8, D11, D17, D18; the tutorial page rewrite (D20);
  `verification.md`.
- **Out:** everything in D18; stage-2 screening; classify and later components; the
  plan directive grammar; the schema; the stub and fixture backends beyond what the
  tests need; the eval scripts; the experiment scripts; the Bedrock route itself (this
  slice changes model ids on the OpenAI route; the route seam is task 045's).

## Constraints & approval gates

- **Runtime egress (gated, Tier 3):** two new OpenAlex request shapes (semantic search;
  batched id resolve and `cites:` chase, which reuse the existing Works endpoint) and
  two Overton changes (`sort=relevance`; `documents.php?policy_document_id=`). All through
  `search_live.py`, the sole sanctioned HTTP home, with its timeouts, limiters, retry
  cap and redaction. Call volume per search: OpenAlex 37 logical calls per filter variant
  (was 15 to 50), Overton 18 (was 3 to 15); HTTP ceiling per D12. Overton's 1.2 s limiter makes its leg about 30 s.
- **Inference route (gated):** model ids `gpt-5.6-luna` for query generation and
  stage-1 screening, on the existing OpenAI route. Screening calls per document fall
  from 3 to about 1.3; documents per run rise from 100 / 400 / 1,200 at most to about
  150 / 300 / 600. Prompt edits: `screen_prompt.py` text (D10), `planner_prompt.py`
  numbers (D15); both re-pinned with `scripts/prompt_hash_guard.py --update` and the
  diffs recorded in `verification.md`.
- **Schema:** none. **Dependencies:** none. **CI, production config, auth:** untouched.
- **Public interfaces:** the search directive values are unchanged; `DEPTH_CONSTANTS`
  changes shape (internal); the frontend constant changes shape (internal).
- **Generated files:** none touched (`openapi.json` unaffected: no API change).
- **Cost of the live check:** a range, not a figure. Documents screened: mini set
  about 15 × (150 + 300 + 600) = 15,750; full set at Broad about 100 × 300 = 30,000; at
  1.3 calls per document about 59,000 Luna calls. Per-call cost from the two measured
  runs: experiment 3 (real candidates, $0.30 for 3,863 calls) gives about $5; the
  labelled full set ($1.97 for 8,847 calls, longer inputs with criteria) gives about
  $13. **Spend ceiling $25; the build stops and reports if the mini-set runs exceed
  $10.** The full-set run starts only on the owner's go after the mini-set numbers are
  in. Wall clock: about 2 minutes of search per review plus screening at 12 calls in
  parallel, about 6 hours in all, in the background. `verification.md` records
  documents, calls, tokens, cache share and cost per scope.

## Public / private boundary

Public: code, tests, docs, ADR, `verification.md` with recall, cost and timing numbers.
Private: API keys; Langfuse traces; the eval caches (git-ignored).

## Model route

OpenAI route, `gpt-5.6-luna` for `search_queries_v3` generation and `screen_v4` stage-1
screening; stage 2 unchanged (`screen_fulltext_v1` on its current model). Bedrock
migration is task 045's; this slice picks the model that migration can carry.

## Disciplines binding this slice

- **Don't flatten status.** D8 similarity damping and D11 reformulation are 🟡 leaning
  (measured, parked); D18 items are ⏸.
- **Honest absence.** Coverage records keep `dropped_over_cap` and per-backend counts;
  a backend at its call budget says so. The recall numbers are paper-side only.
- **Flag, don't drop.** `unsure` keeps; a failed second call keeps the first call's
  `failed` status, never a silent drop.
- **Model only what behaves.** No new column, label or flag; `query_origin` values are
  the existing vocabulary plus `semantic`.

## Stop conditions

Halt and escalate when: the OpenAlex semantic endpoint or the Overton `sort` or id fetch
does not behave as the experiments recorded (a live probe is the plan's first step); the
screening change needs a schema change (it must not: `uq_ssr_scope_source_stage` and the
generation column are untouched); scope would grow past this slice; the live check shows
search recall more than 3 points below the experiment at any scope and the cause is not
found within the build.

## Acceptance checks

- `make verify` green. `make prompt-guard` green after the re-pin.
- Unit tests (deterministic): paper specificity ranking order on a fixed candidate set;
  backward count ignores seeds and takes the top 200; forward chase picks the 20 seeds
  by in-set count under the 300 ceiling and ranks by weighted coupling; the two caps cut
  the two pools independently and `dropped_over_cap` counts each; Overton title dedup
  keeps the best-ranked copy; `sort=relevance` is sent and protected; landmarks are the
  15 most-cited non-results; adaptive vote: one call keeps on `relevant` and `unsure`,
  a `not_relevant` triggers exactly one more call, the second call's `relevant` or
  `unsure` keeps, two `not_relevant` drops, a failed second call leaves `failed` only
  when the first also failed; confidence equals the consensus probability over the calls
  made; the `source.screened` event lists one or two reps; no screening row written by
  acquire; one coverage record per acquire run with `completed`; a run at `standard` or
  `deep` makes exactly one acquire and one screen run (the runner test that replaces
  `test_search_rounds.py`); `search_backend_scope` with one backend leaves the other's
  pool empty without error; `QUERY_MAX_CHARS` 1,300 drops a 1,400-character query.
- Deterministic vs AI eval: all of the above are tests. The recall, cost and timing
  numbers are measurements against thresholds, below.
- **Live check (pinned):** one live probe per new request shape before the build
  (semantic search with each OpenAlex filter key the directive grammar can emit, to fix
  the D13 accepted set; Overton `sort=relevance`; Overton fetch by id), recorded in
  `verification.md`. Then `production_recall.py --depths rapid standard
  deep` on the mini set with screening, and `--depths standard` on the full set.
  Thresholds: mini-set search recall at least 12.5% / 17.3% / 24.6% at Focused / Broad /
  Broadest (the experiment's 15.5 / 20.3 / 27.6 minus 3 points of noise and production
  differences); screen recall at least 90% of search recall at each scope; 0 failed
  provider calls, or the undercount named; cost and wall clock per review recorded, no
  threshold. Full set at Broad: recorded, compared with the mini-set figure, no
  threshold. Policy side, deterministic: replay tests built from recorded Overton responses of
  the task 049 experiment (three questions) assert relevance order, title dedup, the
  15 landmarks, the specificity order, the `source_country` post-filter on landmarks,
  and the policy cap. One manual run in the app at Focused on the obesity question of
  task 049 is a transport and UI smoke check only: the run completes and the Sources
  view shows at least one landmark; it does not validate policy recall (no Overton ids
  in the ground truth).

## Verification evidence expected

In `verification.md`: the live probes; the eval commands and the printed tables; the
Langfuse run names; the `history.md` rows added; the prompt hash diffs; the cost and
wall clock per review per scope; the manual app run; the list of deleted code and
tests with the replacing tests named; the deferred entries added; the ADR and spec
diff; public-safety confirmation.

## Risk tier & review focus

**Tier 3.** Runtime egress changes (new request shapes on both backends), inference
route model changes, prompt edits, and deletion of a runner control path. Review focus:
the egress hardening holds on the new calls (timeouts, limiter, retry cap, redaction,
no credential in logs or caches); the adaptive vote cannot silently drop a document;
provenance invariants after the loop deletion (one coverage record per run, no shadow
relevance judgment in acquire); the two caps bound volume; the filters reach every
call they should; scope creep into stage 2, classify or the schema.
