# Verification: 054 theory of change, increment 1 (the core)

Evidence for increment 1, steps 1.1 to 1.6 (first try). The iteration phase and the evals
(E1, E2, E6, step 1.7) have not started: they wait for the owner's review of this first
implementation. Fill **Review findings** and **Rubric status** after the review stack.

Branch: `task/054-1-core`, from `feat/theory-of-change` (from `task/054-integrate-toc`).
Commits: `7da99688` (1.1, 1.2), `782695da` (1.5 frontend), `53f31d4d` (frontend polish),
`fbdb7d97` (1.3, 1.4, 1.5 backend).

> **Stop condition overridden.** The contract (§ Stop conditions) says to halt when PR #84
> (task 053, Bedrock) has not merged when the build opens. PR #84 is still open. The owner asked
> for one full build with no check-ins, so the build went ahead on a branch that already holds
> the #84 code. When #84 merges, rebase this branch onto `dev` before the PR.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (build-open baseline) | 3640 pass, 1 fail | The fail was `test_rename_044_sweep`, caused by the 1.2 schema edit in progress, not by the base. Fixed in 1.2. |
| `make verify-fast` (after 1.3–1.5) | 3749 pass, 5 fail | Four were exact `PlanOut` dicts and a backend patch list (fixed); one was a Cognito test that passed on rerun (flaky, machine under load). |
| `make verify` (increment end, at `fbdb7d97`) | **pass** | Backend 3755 passed; lint, typecheck, prompt-guard, eval-check, drift-check green; frontend 906 tests in 89 files passed; `vite build` passed. |

## Checks beyond the build

- **Deterministic tests** (new):
  - `tests/theory_of_change/test_grade.py` (34 cases): the grade rule, `lower`, how web, modelling and unscored documents count.
  - `test_graph.py`: structure checks, `item_hash`, the C19 link-state table.
  - `test_walks.py`: draft walk, one retry, failure with reasons, draft → check in one hop, the restart rule.
  - `test_check_steps.py`: discover, merge, judge, choose, summarise, citation check, quote check.
  - `tests/api/test_task_agent_toc.py`: plan slot, turns during the draft and check, `patch_plan` 422.
  - `tests/api/test_toc_routes.py`: both reads, the public leg, `toc_not_found`.
  - `test_migration_054_core.py` (9), `test_toc_plan.py` (13), plus the registry and settings tests.
  - The branch-site guard `test_capability_branch_sites.py` records every new ToC branch.
- **Frontend** (vitest, from fixtures): `TocResult`, `TocCanvas`, `DetailPanel`, `DetailedInformation`, `Documents`, the ToC plan sections, the public view.
- **Evals:** none yet. E1, E2 and E6 belong to step 1.7 in the iteration phase.
- **Live, one topic** (1.6): see the next section.

## End-to-end command

Local app, `openai-direct` route (the default), real search sources:

```bash
cd backend && uv run --env-file .env alembic upgrade head
# API with the ToC server setting on
(cd backend && POLICY_ATLAS_THEORY_OF_CHANGE=1 uv run --env-file .env \
  uvicorn policy_atlas.api.app:create_app --factory --port 8000) &
# SPA with the ToC build flag on and a dev token (as `make dev` mints it)
token=$(cd backend && uv run python -m policy_atlas.api.dev_issuer mint --dir .dev-issuer \
  --sub dev-user --client-id policy-atlas-dev --ttl 14400 | tail -1)
(cd frontend && VITE_DEV_TOKEN="$token" VITE_OPTIONS_SCOPING=1 VITE_THEORY_OF_CHANGE=1 pnpm dev) &
# Then, with H="Authorization: Bearer $token":
curl -H "$H" -H 'content-type: application/json' localhost:8000/api/v1/tasks \
  -d '{"name":"ToC first try: unhealthy food advertising","question":"Restrictions on unhealthy food advertising to children","capability":"theory_of_change"}'
curl -H "$H" -H 'content-type: application/json' localhost:8000/api/v1/tasks/$TID/task-agent-turns \
  -d '{"message":"I want a theory of change for restricting adverts for less healthy food to children in England: the 9pm TV watershed and the ban on paid online adverts. The aim is fewer children living with obesity. I do not have an existing theory of change.","client_turn_id":"<uuid>"}'
curl -H "$H" -H 'content-type: application/json' localhost:8000/api/v1/tasks/$TID/runs -d '{}'
# Read: GET /api/v1/tasks/$TID/toc and /toc/evidence; open http://localhost:5173/tasks/$TID/result
```

### First try: what happened (2026-10-26, task `07e278fe`)

**Timeline:**

| Time | Event |
|---|---|
| 22:15:11 | Start |
| 22:15:19 | Draft walk running |
| about 22:16 | Draft on the canvas: 11 boxes, 11 links, 2 success and 2 failure pathways |
| 22:16 | Check walk opened by itself |
| 22:21 | Discover added pathways: 16 boxes, 20 links |
| 22:31:06 | Checked: all 20 links checked, summary written. About 16 minutes from Start. |

**Task Agent:**
- It asked no questions, because the first message answered both allowed questions (J2). It marked the plan ready.
- The plan was good: intervention first, a measurable change, England, "within five years".
- It guessed the time horizon but left `assumptions` empty.
- It posted the J3 line when the draft landed, and the J5 + J7 message when the check ended.

**Pathways:**
- Discover proposed 8 pathways (7 success, 1 failure). Merge set aside 4 of them as the same mechanism.
- The theory ended with 5 success and 3 failure pathways, within the limits.
- Choose added 2 conditions recorded by the evidence and kept the drafted critical connection: "restricted adverts absent → children see fewer adverts".

**Evidence:**
- 152 judged (link, document) rows and 73 case studies.
- Links by grade:

  | Worked elsewhere | Holds here | Links |
  |---|---|---:|
  | strong | strong | 3 |
  | strong | none | 4 |
  | medium | medium | 2 |
  | medium | none | 5 |
  | weak | medium | 2 |
  | weak | none | 3 |
  | none | none | 1 |

**Summary:** the header paragraphs read well. They name the critical connection and say that narrow restrictions can leave exposure unchanged. There are 6 evaluation questions; the critical connection comes first.

**Cost:** about 1.41M input and 0.24M output tokens over the walk.

| Step | Input tokens | Output tokens |
|---|---:|---:|
| judge | 0.78M | 0.15M |
| screen and classify (fast model) | 0.54M | 0.07M |
| discover | 0.05M | — |
| summarise | 0.02M | — |
| draft, merge, choose | under 0.01M each | — |

This is well under the owner's $30 limit for the try. The Consensus API was not used; there is no Consensus client in product code.

**Screenshots:** `screenshots/live-checking-result.png` (during the check), `live-checked-result.png`,
`live-checked-panel.png`, `live-checked-workspace.png`.

### Findings for the iteration phase (the owner reads these first)

1. **Overton returned 401 (unauthorised) on every call.** The local Overton key is missing or expired. It is not a code fault, but this run had no Overton policy documents, which are the main source of England evidence.
2. **The judge is too strict on "holds here".**
   - A 2012 UK study of children's exposure under the UK TV rules is `challenges` for worked elsewhere but `not_about` for holds here. It is England evidence and should count.
   - 12 of 20 links have no holds-here evidence. Because a link is coloured by its lower grade, most of the canvas is grey.
   - First target: the judge prompt's holds-here definition (lead-only, re-pin).
3. **The grade rule allows "medium" with more evidence against than for.** The critical link has 3 supports and 4 challenges and is graded medium. Owner decision: should counted evidence against lower the grade, or only show as a count?
4. **The J5 end message is noisy.** It lists 8 "added a pathway" lines and then 4 "merged" lines for the same pathways. It should report the net change.
5. **The first query of each item search is the whole item text** (sentence, From/To, IF/FOR/THEN/BECAUSE, conditions, the question). This follows the brief; the generated queries after it are short. Check how well the long one retrieves before changing it.
6. **The canvas puts all outcomes in one tall column** (8 boxes after discover), so the text is small at fit-to-view. This is a layout target.
7. **Wording from Explore Evidence on a ToC task:**
   - the activity bar shows "DONE · Appraising";
   - the composer says "Describe a change to the plan to run again.";
   - kept pathways show no reason (only set-aside ones carry one).
8. The Result page asks for `GET /artefact` on a ToC task and gets 404. Harmless, but a wasted request.

## Iteration log

Short loops after the owner's first review (plan § Iteration phase).

**Loop 1 (2026-10-27, commits `944ec427` and the layout commit)**

The owner's review, finding by finding:
- Finding 1: the Overton key was renewed. A single search returned 200.
- Finding 2: fix the judge.
- Finding 3: keep "medium". The owner ruled that a link with 3 supports and 4 challenges stays medium.
- Finding 4: make the end message less noisy.
- Most important, in the owner's words: "I can't even see in the canvas where the last outcome ends and connects to". Work on the layout ("multiple Outcome columns are fine") and the connections.

What changed:
- **Judge (`toc_judge_v2`, re-pinned).** A study done in the stated place now answers "holds here" the same way it answers "worked elsewhere". The UK counts for England, and older or narrower versions of the intervention there count too. The place may come from the title. Not yet measured: the next live run shows the effect.
- **J5 message.** Pathways found in the evidence are listed once, as one line naming those kept. A found pathway that the same check merged or set aside is left out. There are two new tests.
- **Canvas layout.**
  - An outcome now sits one column after the outcome that leads to it, so a chain reads left to right and the impact comes after the last outcome.
  - Each box takes the average row of the boxes that lead into it, so a chain stays on one row.
  - Connections are right-angled. Each turns in the gaps between columns and runs along the empty lanes between rows, so no connection crosses a box. A fan-out reads as one trunk with branches.
  - The critical-connection dot sits on the connection's own last stretch.
  - No layout library was added.
  - On the live theory, the outcomes now spread over 4 columns and the impact is visible at the right. See `screenshots/iter1-canvas-layout.png`.

## Diff summary

**What was built:**
- **1.1 Prompts** (lead): draft, judge, discover, merge, choose, summary, the ToC Task Agent, and the item-search guidance. Hash-pinned.
- **Grade and graph code:** `evidence/grade.py` is the only place a grade is decided. `graph.py` holds the structure checks, `item_hash` and the link-state table.
- **1.2 Schema and setup:** revision 1 migration (six tables), registry entry, `TocPlan`, the server setting with 422 `capability_not_enabled`, and an ops removal script.
- **1.3 Draft walk and Task Agent:** the draft walk, the ToC Task Agent and its plan slot, and the plan panel sections.
- **1.4 Check walk:** item searches through a generalised `run_child_search` (pool width 8), then discover, merge, judge, choose and summarise. Each step writes one `toc.changed` event.
- **1.5 Read routes and frontend:** `GET /toc` and `GET /toc/evidence`, and the read-only Result page (canvas, reading guide, detail panel, detailed information, documents), also in the public view.

**Deviations, all minor and inside the contract's vocabulary:**
1. Built while PR #84 is open (see the top of this file).
2. The planned `/pathways` and `/summary` reads are folded into `GET /toc`. Two public routes instead of four.
3. The header paragraphs live in the `toc_summarise` step's `component.completed` payload. No new table.
4. An indicator shares `case_box_id` with its case study. An indicator that names the other box is dropped.
5. 1.2 schema additions beyond the contract text:
   - extra indexes;
   - `revision` on every table;
   - the case-box foreign key is `ON DELETE SET NULL (case_box_id)`, which needs PostgreSQL 15 or later;
   - a new `ApiUnprocessable` handler.
6. Draft retries can reach four calls: the step retries once, and the runner retries a failed component once. A test pins this.
7. Start on a task that already has a graph always runs a full check. There is no "Check again" route in this increment. The judge skips (link, document, hash) rows it already has.
8. A new theory-state value for the Task Agent prompt: "the draft is on the canvas and its evidence check did not finish". This is data only; the prompt text is unchanged.
9. Code-authored Task Agent lines (J3, J5, J7):
   - They are completed transcript rows with an empty user message.
   - `create_run`'s plan-stale fence skips ToC tasks that already have a graph, so these lines do not block a restart.
   - The frontend hides the empty user bubble.
10. `patch_plan` on a ToC task returns 422. In increment 1 the plan is set through the Task Agent only.
11. The schema has no "merged" status, so a merged pathway is `set_aside` with the reason "Merged into “X”: …".
12. Choose sets aside only pathways over the limits. Within the limits, the model's set-asides are ignored.
13. A link's "own search" documents come from `task_source_snapshot.run_id` of the child's acquire run. A document that two searches found is filed under the first search only (`ponytail:` comment).
14. Rerank uses select's `RankingBackend`. In stub runs, with no ranking backend, candidates keep their order.
15. Discovered boxes have `result_criteria` with a null definition and timing.
16. The ToC item-search dispatcher copies about 40 lines of `dispatch_option_searches`, so the Options Scoping path is unchanged in behaviour.
17. `TocTurnWire` has no `part` field. `runtime/task_agent.py` tolerates a turn without one.

## Review findings

(After the review stack.)

## Rubric status

(After the review stack.)

## Intent & assumptions

- Increment 1 is the core only: no editing, no "Check again", no stress test, no export, no original-theory view. These belong to increments 2 to 7.
- The owner reviews and live-tests this first implementation before the iteration phase starts.

## Known unverified items

- Not asserted by any test, because increment 1 has no user-made content:
  - the T1 `pa_changed` flags on user work;
  - the judge storing a case study and an indicator.

  Both paths ran in the live try (73 case studies were stored).
- The live try covered one topic, on one route, without Overton.
- The `/code-review` on the S5 change to `option_search.py` that the plan calls for has not been run. It belongs to the review stack.
- The Cognito conformance test failed once under load and passed on rerun, and it passed in the final full `make verify`.

## Public safety

- The screenshots show a generated theory and titles of published documents. They show no tokens, keys or personal data.
- No raw document text is in this file. The quotes above are short extracts from published abstracts.
- The dev token stays in the session scratchpad and is not committed.

## Review handoff (step-7/8 inputs)

- **Adjudication items:** deviations 1 to 17 above, and iteration findings 2, 3 and 4. Findings 2 and 3 are owner decisions, not review fixes.
- **Executor provenance (for the model-family flip):**
  - Lead: prompts (1.1), grade and graph code, the frontend polish.
  - `deep-reasoner` delegate: 1.2 schema and setup; 1.3, 1.4 and the 1.5 backend (`fbdb7d97`).
  - `fast-worker`: the 1.5 frontend (`782695da`).
  - All of it is Claude, so an adversarial review should use the other family (Codex).
- **Diff-scoping exclusions:** `frontend/openapi.json` and `frontend/src/api/gen/types.ts` are generated by `make openapi-sync`.
- **Knowledge candidates:**
  - Two layers of retry multiply: a step that retries once inside a component that the runner also retries once makes up to four model calls. Count both before sizing a budget.
  - xyflow's own CSS overrides edge stroke styles unless the rules are scoped under `.react-flow`.
  - The vitest jsdom setup needs a `DOMMatrix` stub for `@xyflow/react`.
  - A Task Agent line posted without a model call had no precedent. An empty `user_message` row works, but the plan-stale fence and the history view both had to learn about it.
  - The colour of a link is its lower grade, so one strict judge question (holds here) can turn the whole canvas grey. Watch the holds-here rate first when a canvas looks empty.
  - With Overton down, the search falls back to academic sources without failing. The run "succeeds" with much less England evidence. A missing-key 401 should be visible to the owner, not only in the logs.
  - Two checkouts and a running `make verify` share one test database. Delegates must check `pgrep` before running database tests.
  - Under heavy machine load, vitest setup can take 15 minutes and time out. Kill stray vite servers and rerun before treating a failure as real.

## Deferred work

- The owner chooses the iteration targets from the findings above.
- Then E1, E2 and E6 (step 1.7).
- Rebase onto `dev` after PR #84 merges.

## Live runs 4–7: the light link check (2026-10-27, lead)

Same opening message each time; openai-6x route (gpt-6-luna / gpt-6.1-terra / gpt-6.1-sol).
Cost is the model cost from `toc_check.cost` (draft + check walks).

| Run | Task | Build | Time | Cost | Boxes / links / kept pathways | Links with no evidence |
|---|---|---|---|---|---|---|
| 4 | `0bd0e121` | light search, pick call, consolidate, merge v2 | ~5 min | $0.36 | 13 / 17 / 6 | 5 |
| 5 | `560bee1f` | + design keyword pair, shared pool, classify after judge, Crossref limit | 4 min | $0.31 | 12 / 15 / 4 | 4 (merge v2 over-merged) |
| 6 | `07e88cc7` | + merge v3 (keep the general route) | 5 min | $0.36 | 13 / 16 / 7 | 2 (both discovered links) |
| 7 | `3e357c2b` | + discovered links get their own light search (C32) | **5 min** | **$0.37** | 12 / 14 / 6 | **0** |

Run 7 grades (worked elsewhere / holds here): strong/strong 4, strong/medium 1, medium/medium 5,
weak/medium 2, weak/weak 1, medium/none 1. Lower excess energy → obesity: medium/medium (weak in
run 4). Critical connection: fewer requests → households buy fewer requested foods (medium/none).

Before the light check (runs 1–3): 16 min (run 1), and 50+ min (runs 2–3, stopped) with full
Evidence searches per link and an LLM rerank.

Not built, by evidence: a second search round for empty links (eval and live test on run 6's
empty links found nothing new; the gap came from discovered links having no search of their own).
