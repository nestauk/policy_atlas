## What / why

Task: `docs/tasks/051-improve-production-search-screen/`

Production search found 5% of a review's reference list at Broad, for about $1 a review. This PR replaces the three-round search loop with one search pass and makes screening cheaper.

What changed:

- **One search pass at every scope.** Generated queries on OpenAlex and Overton, OpenAlex semantic seeds, a backward citation snowball (the papers our results cite) and a forward citation chase (the papers that cite our results). Results are ranked and cut at two caps per scope: papers 100 / 200 / 400 and policy documents 50 / 100 / 200.
- **Overton searched properly.** Relevance order instead of date order, duplicates removed by title, and the 15 most-cited documents the search missed fetched as "landmarks".
- **Cheaper screening.** Stage 1 runs on `gpt-5.6-luna` with the `screen_v4` prompt. It makes one call, and a second call only if the first says "not relevant". Before: three calls and a majority vote.
- **Faster.** The two database legs run in parallel. Search takes about 45 seconds a review at every scope. Before: about 130 seconds.
- **Design record.** ADR 0038 (Accepted). The old loop's last commit is tagged `search-round-loop-last` with a restore recipe.
- **Task 052, added after live testing (2026-10-12).** The paper pool now drops duplicate copies of a paper (same title and same authors, most cited copy kept) and is ordered as a mix: one paper in turn from three lists, relevant (rank fusion over the query results and "cites the seeds"), seminal (most cited by the seeds) and novel (last five years). Ranking by the citation-graph score alone had cut the question's own best match at 127 of 2,139 on a Focused search. Evidence: offline re-orderings of three captured pools and a live search plus screen per topic, in `scripts/evals/search/experiments/manual/`; notes in `docs/tasks/052-rank-mix-paper-dedupe/notes.md`. ADR 0038 decision 4 is amended.

Measured on the 15-review ground-truth mini set (share of the review's reference list found by search / after screening / cost per review at list price):

| scope | search recall | after screening | cost per review | search time |
|---|---:|---:|---:|---:|
| Focused | 15.3% (was 12.9%) | 14.8% | $0.03 | 47 s |
| Broad | 19.7% (was 17.8%) | 19.0% | $0.07 | 41 s |
| Broadest | 25.3% (was 22.3%) | 24.3% | $0.14 | 44 s |

The "was" figures are the task 051 run of 2026-10-09; the current figures are the task 052 run of 2026-10-12 with the new paper order (one Broadest run, the two smaller scopes read from its pool at their caps). All three targets are met (Broadest 24.6% by 0.7 points; before task 052 it was 2.3 points short and the owner had accepted that).

## Size of the diff

121 files, +31,970 / −4,028 lines. Two thirds of the added lines are recorded test data, not code:

| what | files | added | removed |
|---|---:|---:|---:|
| product code (`backend/src`, `frontend/src`) | 12 | 1,876 | 1,416 |
| tests (`backend/tests`, frontend tests) | 24 | 2,675 | 2,263 |
| test fixtures (`backend/tests/data`: the ranking fixture and three recorded Overton replays) | 7 | 20,533 | 0 |
| eval and experiment scripts (`scripts/evals`) | 52 | 3,806 | 318 |
| docs (`docs/`, task records, ADR, tutorial) | 24 | 3,077 | 30 |
| other (`.gitignore`, `Makefile`) | 2 | 3 | 1 |

The product-code change to review is about 1,900 lines added and 1,400 removed. The fixtures are JSON the replay and ranking tests read; the eval scripts are dev-only tooling, not part of the runtime package. Experiment output JSON is git-ignored; only the Markdown write-ups are in the tree.

## Proof it works

Evidence: `docs/tasks/051-improve-production-search-screen/verification.md`.

- **`make verify`:** pass, at the build exit and again after the review fixes (backend 2,614 tests, frontend 617, typecheck, lint, build, eval check, OKF).
- **Manual / end-to-end:** the live check on the mini set at all three scopes, with the command below. History rows are in `scripts/evals/search/results/history.md`. One app run at Focused on the obesity question completed, with 13 landmarks in the Sources view.

```
scripts/evals/search/checks/production_recall.py --dataset retrieval-ground-truth-mini --depths rapid standard deep
```

- **Cost note:** Langfuse prices Luna at five times the list price, so its cost figures for this run are five times too high. At list price the mini set cost about $4. The Langfuse price row needs correcting before the next eval run.

## Risk tier

Tier 3. The running product makes four new kinds of request to the search providers, the legs run in parallel, two model ids change, one prompt moves, and the round loop is deleted.

| Tier | Review |
|---|---|
| 0–1 | tests + AI review or human skim |
| 2 | contract verifier + tests + human review |
| 3 | + security + adversarial review + human deep review |
| 4 | + human-approved plan + ADR + rollback plan |

## AI role

Claude designed the pass, ran the experiments, built the search, the eval changes and the records, and ran the live check. Codex built the ranking module, the transport verbs and the adaptive vote, and reviewed the plan and the parallel-search phase. The owner decided the filter design (D13), the parallel-search phase, the prompt and model pins, the spend ceiling, the "no new evals at review" rule, the Broadest acceptance and the ADR sign-off. The review stack ran as fresh agents; Claude adjudicated the findings in the build conversation at the owner's instruction.

## Review focus

**Start with the tutorial page**, which explains the method with diagrams and the measured numbers: [`docs/tutorials/search-and-screen/index.html`](https://github.com/nestauk/policy_atlas/blob/task/051-improve-production-search-screen/docs/tutorials/search-and-screen/index.html) (GitHub shows the source; open the file from a checkout in a browser to read it rendered).

**Where to look** (product code, in reading order; sizes are lines added / removed against `dev`):

1. [`search_loop.py`](https://github.com/nestauk/policy_atlas/blob/task/051-improve-production-search-screen/backend/src/policy_atlas/evidence_search/sourcing/search_loop.py) (+708 / −928) — the single search pass: query generation, the OpenAlex leg (`_openalex_leg`: seeds, backward snowball, forward chase, de-duplicate, mix), the Overton leg (`_overton_leg`: relevance search, title dedup, landmarks), the two legs run in parallel in `run_search`, the call budgets and the 429 pause. The old round loop is removed from here.
2. [`pool.py`](https://github.com/nestauk/policy_atlas/blob/task/051-improve-production-search-screen/backend/src/policy_atlas/evidence_search/sourcing/pool.py) (+630, new) — pure ranking rules with no I/O: `interleave`, `count_references`, `backward_targets`, `forward_seeds`, `score_forward`, `paper_candidates`, `rank_papers` (specificity), `dedupe_papers`, `query_fusion`, `mix_strata`, `rank_mix` (task 052), and the policy side `dedupe_policy`, `landmark_targets`, `rank_policy`.
3. [`acquire.py`](https://github.com/nestauk/policy_atlas/blob/task/051-improve-production-search-screen/backend/src/policy_atlas/evidence_search/sourcing/acquire.py) (+108 / −84) — `acquire_sources` now takes two ranked pools and two caps, cuts by position, and keeps the count invariant; `source.acquired` carries `query_origin`.
4. [`search_live.py`](https://github.com/nestauk/policy_atlas/blob/task/051-improve-production-search-screen/backend/src/policy_atlas/evidence_search/sourcing/search_live.py) (+188 / −14) — the new provider verbs: OpenAlex `search_semantic`, `lookup_ids`, `fetch_citing`; Overton `fetch_by_id` and `sort=relevance` on every search; the per-backend pacing and the 429 pause.
5. [`screen.py`](https://github.com/nestauk/policy_atlas/blob/task/051-improve-production-search-screen/backend/src/policy_atlas/evidence_search/assess/screen.py) (+160 / −180) — stage 1 as the adaptive vote: `decide_stage1` (one call, a second only after "not relevant"), the stored confidence, the per-document event.
6. [`screen_prompt.py`](https://github.com/nestauk/policy_atlas/blob/task/051-improve-production-search-screen/backend/src/policy_atlas/evidence_search/assess/screen_prompt.py) (+39 / −17) — prompt `screen_v4` (hash-pinned) and the model pin to `gpt-5.6-luna`.
7. [`runner.py`](https://github.com/nestauk/policy_atlas/blob/task/051-improve-production-search-screen/backend/src/policy_atlas/runtime/runner.py) (−144) — the round-loop orchestration deleted; [`agent_backend.py`](https://github.com/nestauk/policy_atlas/blob/task/051-improve-production-search-screen/backend/src/policy_atlas/runtime/agent_backend.py), [`planner_prompt.py`](https://github.com/nestauk/policy_atlas/blob/task/051-improve-production-search-screen/backend/src/policy_atlas/runtime/planner_prompt.py) and [`search_prompts.py`](https://github.com/nestauk/policy_atlas/blob/task/051-improve-production-search-screen/backend/src/policy_atlas/evidence_search/sourcing/search_prompts.py) carry small follow-on edits (model id, scope wording, query length).

The tests that pin each piece: `backend/tests/evidence_search/sourcing/test_search_single_pass.py` (the whole pass on scripted backends, call plan and caps), `test_pool.py` (ranking rules, replay of the recorded fixture), `test_acquire_pools.py` (two pools, two caps, count invariant), `test_search_wire.py` (filters on the wire and locally), and `backend/tests/evidence_search/assess/test_screen.py` for the vote.

**Questions for the reviewer:**

- The local filters on semantic and citation-found records: the review fixed a case where a second country in a plan was dropped. Check the combined predicate.
- The pool cap is a cut by position. A repeat inside the cut is not refilled. Confirm this is the wanted behaviour on a re-run of the same task.
- Egress: the pause after a 429 reply, the per-run concurrency, the call budgets.

## Reviews run

Findings recorded in `verification.md` § Review findings.

- [x] Contract verifier
- [x] `/code-review` (fresh Claude agent, medium)
- [x] `/security-review` (fresh Claude agent)
- [x] Adversarial review (Codex, read-only)
- [x] `/simplify` (covered by the code-review cleanup lenses; recorded)

## Known gaps & deferred seams

- Broadest is under its target by 2.3 points. Accepted by the owner. A re-run costs about $2 at list price.
- The three scopes' figures come from one Broadest run; the Focused and Broad rows are its pool cut at their caps, not separate runs (`engine.recall_at_smaller_caps`). The run-to-run variance of query generation is of the order of the gaps between scopes, so "met by 0.7 points" is "met, not comfortably".
- The full-set Broad run (100 reviews, about $6.50 at list price) is not made yet.
- Deferred seams are in `docs/deferred.md` under task 051: similarity damping, reformulation contingency, seminal-decile score, removed-title records, partial backend failure and the coverage verdict, landmarks without wire filters, per-run pacing under concurrent runs.

## Public safety

- [x] No secrets, credentials, or real/acquired source text in the diff or evidence. Fixtures hold ids, titles, dates and counts only. Probe error excerpts have keys redacted.
- [x] Logs / traces / screenshots are public-safe. Langfuse links go to the private project. The app screenshot shows public policy document titles.
- [x] No approval-gated change beyond those the contract names. The new request shapes, the model ids and the prompt edits are the contract's D2, D8, D10, D12 and D13. No schema, auth, dependency, CI or production-config change.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
