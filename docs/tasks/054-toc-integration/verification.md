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

**Screenshots:** four PNG files (during the check, the checked result, the panel and the workspace),
attached to PR #114. Binary evidence is not committed (`docs/knowledge/binary-evidence-stays-off-the-tree.md`).

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
  - On the live theory, the outcomes now spread over 4 columns and the impact is visible at the right. Screenshot attached to PR #114.

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

The review stack ran on 2026-11-05 in a fresh conversation (task-cycle step 7), on the branch at
`d35ca7b4` against `origin/dev` `3d276c21`, after the owner's green `make verify`. All of the code
is Claude-written, so Codex anchored the adversarial pass.

### Lanes

| Lane | Reviewer | What it covered |
|---|---|---|
| Contract verifier | `contract-verifier` agent (pinned Opus, read-only) | every rubric item, the claims in this file and ADR 0042 against the code, deviations 1 to 23 |
| `/code-review medium` | the Claude half of the heterogeneous pair | product and test code |
| Security | `/security-review` (a finder and a false-positive filter; the Tier-3 `security-auditor` agent is not installed here) | the upload routes and store, the bucket, colleague access, the vision call, untrusted text in prompts |
| Adversarial | Codex through `codex-rescue`, read-only (job `task-mw3r25xr-wp8yyn`, 5 min) | concurrency, access, injection, migrations, cost, shared-code regressions, the simplification review's § 4 list |
| Design | `frontend-designer` agent, read-only, against the wireframes and the contract's rulings (no `design-annex.md` exists for this slice) | every changed frontend surface; then the fix pass below |
| Trace | the lead, from the persisted outputs | run `6322f259` (the owner's last feedback-round task) and the review's own live run (below) |
| `/simplify` | not run again | the simplification review and its five batches (`8f1ac86f` to `d35ca7b4`) were the reuse, simplification, efficiency and altitude pass; a second same-family pass would duplicate it |

Subagent tokens: contract verifier 226K, `/code-review` 246K, security 196K + 68K, design lane
272K + the fix pass 166K. That is above the 250K reasoning-class guideline, because the product
diff is 27K lines and the owner's 2026-11-04 rule adds the design lane for frontend-heavy slices.

### Findings and rulings

Convergent across lanes (high confidence): the owner's name on the public leg (security and
`/code-review`); the removal script's missing file delete (contract verifier and `/code-review`);
imported rows not flagged (Codex and contract verifier); stale rows counted as changed (Codex and
contract verifier). Unique to one lane: the lossy downgrades (contract verifier), the delete
race and the Bedrock prices (Codex), the queued-check order, the Stop-during-draft and the
critical-mark collision on Undo (`/code-review`), and every design item.

| # | Lane | Finding | Ruling |
|---|---|---|---|
| 1 | security, code-review | `GET /toc` and `/toc/evidence` returned real display names (`edited_by`, `scored_by`, `removed_by`, `added_by`) to anonymous readers of a public task, against task 037 D5 | **Fixed.** `_readable_toc` returns whether the caller came through the public leg; the two builders skip `names_of` then. Test: `test_the_public_leg_carries_no_editor_names`. |
| 2 | verifier H1, code-review | `scripts/ops_remove_toc_tasks.py` called `UploadStore.delete`, which the simplification batch had removed; the error was swallowed, so a rollback never emptied the bucket | **Fixed.** `delete` restored on the protocol and both stores. Test: `test_apply_removes_the_uploaded_files_too`. |
| 3 | verifier H2 | Six of the ten revisions dropped or folded data on downgrade without refusing; with `transaction_per_migration` a rollback with theories present would commit those drops before the core revision refused | **Fixed** for the four that drop data (`72c3`, `3c27`, `9d1e`, `b4e8`): each refuses while its own data exists. `7fbb` and `80f4` fold values with a designed mapping that keeps every row and has its own round-trip test (`test_migration_054_beam`, `test_migration_054_layers`), so they step down; a first version of the guards covered them too and those tests caught it. The refusal test now asserts no row is lost on the way to the core revision's refusal. |
| 4 | Codex 1 | `store.delete` had no revision check: a delete based on an older revision could remove a row someone had just edited (C10) | **Fixed.** `store.delete(observed_revision=…)` locks the row and compares; `delete_link` and `delete_box` raise `toc_stale_revision` on a mismatch. |
| 5 | Codex 2, verifier M2 | `_flag_values` flagged only origin `user`, `_user_written` counted `imported` too, so a merge or choose change to an adopted sketch was not flagged | **Fixed.** One predicate. |
| 6 | Codex 3 | `cost.PRICES` keys are OpenAI ids; the Bedrock route names them `global.openai.…`, so every step read as unpriced | **Fixed.** The prefix is stripped at the lookup; test added. Folded into the Bedrock knowledge concept. |
| 7 | Codex 4, verifier L3 | Reset layout and Keep the evidence counted rows whose update was skipped as stale | **Fixed.** Only truthy updates count. |
| 8 | Codex 6 | The consolidate call routes as `toc_merge` (frontier) but its tokens land in `toc_discover` (standard price) | **Deferred** (`docs/deferred.md`): one call per walk; needs a component per model call. |
| 9 | Codex 5 | A run that starts and ends between two 15 s polls never alerts (every task kind) | **Deferred**: alert on the latest run's identity. |
| 10 | code-review | `check_status` reads "checking" for a succeeded draft whose follow-on check was refused | **Deferred**: persist the refusal as an event. |
| 11 | code-review | Stop during the draft walk aborted it and posted "The check stopped…" | **Fixed.** Stop refuses (409 `toc_not_running`) unless the running walk is a check. |
| 12 | code-review | `take_queued_check` wrote the dequeue event before learning there was no plan, losing the queue | **Fixed.** Plan first. |
| 13 | code-review | The chat's decision list showed every child item search's `component.started` ("Started an evidence-search step.") | **Fixed.** Only the task's own walks; the text says "Started a step." |
| 14 | code-review | Undo re-inserted a deleted critical link while another was critical: `uq_toc_link_one_critical` raised a 500 | **Fixed.** The restored link comes back without the mark when another holds it. |
| 15 | code-review | An upload that the vision call refused (`upload_not_theory`) left its row and object behind, unlisted | **Fixed.** Row and file are removed before the 422. |
| 16 | code-review | `_patch_toc_plan` turns an empty required field into `None` and the 422 carries pydantic's text | **Declined**: an empty required field is a client error and 422 is right; the message shape is cosmetic. |
| 17 | code-review | `ApiUnprocessable`, `ApiNotFound` and `ApiConflict` are copy-paste twins | **Declined for this PR**: shared error plumbing on `dev`; a cleanup of its own. |
| 18 | verifier M1 | Ten revisions against a contract of three (C51 asked one per slice; the contract contradicts itself) | **Escalated to the owner**, recorded in ADR 0042 § Amendment 2026-11-05. The review did not squash them: the owner's and the test databases have run the chain. |
| 19 | verifier M3 | The theory-level evidence label is the verdict call's, not `grade.py`'s | **Escalated**, ADR amended: per-link grades and the whole-programme judgement still come only from `grade.py`; the theory label is the verdict's reading of them. |
| 20 | verifier M4 | The Download menu rendered on the public view (C17: exports are authenticated only) | **Fixed** (frontend item 18): hidden on the public view. |
| 21 | verifier M2 | C9 and C11 in part: flags stored, never surfaced; no Undo of merge or choose changes, no Keep mine, no Restore, no Redraft-or-keep choice | **Deferred** (`docs/deferred.md`) and recorded in the ADR amendment. |
| 22 | verifier M6, rubric 13 | No same-organisation route tests on the write and upload routes; no race tests with barriers; no DELETE preflight test | **Deferred** (`docs/deferred.md`): the public reads have the full matrix; the writers are tested through 409s and skipped rows. |
| 23 | verifier 1, 16 | E1, E2 and E6 as the contract specifies did not run; no dataset licence was recorded | **Deferred** (evals); **fixed** (licence note in the ground-truth README). |
| 24 | verifier 18 | `docs/specs/log.md` had no entry after 2026-10-30; `components.md` still listed `python-pptx` and server export routes | **Fixed.** Log entry, components and capability rulings updated. |
| 25 | verifier L1 | ADR 0042 stale: three revisions, four widened constraints, the same-meaning call, "imported theory files" | **Fixed** by the amendment. |
| 26 | verifier L2, L5, L6 | The upload docstring said "edit rights"; a test comment's counts; the end message offered a stress test that does not exist | **Fixed.** The end message now says "ask in the chat what would make the critical connection fail here". |
| 27 | verifier L4 | `toc_proposal`, `task_upload`, `toc_figure` lack `UNIQUE(id, task_id)` | **Deferred**: nothing points at them by foreign key. |
| 28 | verifier L7 | One branch and one draft PR instead of `feat/theory-of-change` with a PR per increment (C15) | **Recorded**; the owner steered the build this way. |
| 29 | design 1 | An unchecked connection drew as "Not enough evidence" and said "Checking the evidence…" | **Fixed**: its own solid line, "Needs evidence" tip and legend line. |
| 30 | design 2 | Find evidence was offered before any plan existed (the canvas bar withheld it) | **Fixed**: gated on `check_status`. The backend already refused (`no_plan`). |
| 31 | design 3 | The canvas could not be used from the keyboard | **Fixed**: Enter or Space selects a box or connection; edges focusable; focus ring per DESIGN. |
| 32 | design 4 to 12, 14 to 16 | Contrast on navy, the live-region timer, the 16px floor, errors in the verdict colour, blue section labels, the Undo toast, rounded controls, the narrow-screen panel, the Suggestions copy, the More menu, report codes, reduced motion | **Fixed** (frontend items 4 to 16). |
| 33 | design 13, 14, 17 | Restore for set-aside pathways; "Your original" from the Result page; Stop on the chat's progress line; the History list on the Result page | **For the owner** (`docs/deferred.md`): annex and build disagree. |
| 34 | design 17 | "Start drafting yourself" dropped an attached file | **Fixed**: the link hides while a file is attached. |
| 35 | design 15 | The "question" alert opened the Result tab | **Fixed**: a paused walk opens the Agent tab. |
| 36 | design, fix-pass proposals | Chat and code copy said "Suggestions above the canvas"; "Your original couldn't be loaded." failed contrast; a box's Find more hint said "this connection" | **Fixed** in code strings and the frontend. The Task Agent prompt still says "above the canvas" (a re-pin; deferred). |

Codex's approach-level challenges (one revision-aware write primitive including deletes; a graph
snapshot per check or proposal; imported rows as a first-class provenance category everywhere; a
canonical billable model id at the provider boundary; an explicit queue row) were read and not
adopted now: the delete guard and the one user-written predicate answer the first and third in
part; the rest are recorded with the seams.

### Deviations 1 to 23, re-examined

| Ruling | Deviations |
|---|---|
| Adopt as is | 5, 6, 9, 11, 12, 14, 17, 18, 22, 23 |
| Text overtaken by later increments (the code is right; the text stands as history) | 1 (dev was merged in, not rebased); 2 (three public reads now, with `/evidence/{id}/context`); 3 (the header comes from the `toc_report` payload); 7 (`POST /toc/check` with `check_again` exists); 10 (`patch_plan` edits a ToC plan until the draft exists); 13 (documents come from `source.acquired` and `source.seen_again` events); 16 (the dispatcher shares `_fan_out`) |
| Escalated | 19 (it leaves out increment 4 and C9's Undo all and Keep mine; see findings 18 to 21); 20 (the verdict step; ADR amended); 21 (matches the code; its flag gap is finding 5, fixed) |
| Not verified by the stack | 4, 8, 15 |

### Trace lane

- **Run `6322f259` (the owner's, 2026-11-05).** The plan-stage sense check found 12 documents
  from two OpenAlex queries and said "too little"; the programme judge called 9 of 10 documents
  "not about". Two of those abstracts were read: an Australian RCT protocol (no results) and a
  review of digital delivery of obesity care, so the calls are defensible. The verdict read
  "plausible, mixed" with the one weak support named, consistent with the links.
- **The review's own live run** (task `091c3d13`, "Review run: universal free school meals",
  `openai-direct`, 16:23 to 16:29). The opening turn produced a ready plan and the sense check's
  note ("Before you start: a secondary-school pilot found no measurable effect on hunger or food
  insecurity…", one source named), which did not block. Draft walk 25 s; check walk 4 min 2 s
  with 17 item searches (16 links and the programme). Result: 15 boxes (1 input, 1 output,
  4 short and 4 long outcomes, 2 impacts, 3 failure outcomes), 16 connections, 7 pathways;
  verdicts: 4 confident, 4 leaning supports, 1 leaning against (the critical connection, #16
  "School meals and attendance"), 7 not sure. Report verdict: mechanism plausible, evidence
  mixed; headline "Evaluations suggest universal free school meals can improve primary
  attainment in England, but do not establish a reduction in family food insecurity." Tokens:
  judge 474K prompt (327K cached) and 14K output; select 94K; figures 76K (48K cached);
  classify 75K; discover 56K; the rest under 20K each. About $0.60 by the price table.
  Observations: the critical connection (#16, from the draft) and the verdict's carrying step
  (#2) are different notions on one page; the end message still offered a stress test (the
  wording was changed after this run, finding 26).

### Fake-done check

No test was relaxed, skipped or deleted. The refusal test's assertion was corrected once during
the stack: its first version assumed every revision refuses, the contract says each refuses only
while its own data exists, and the seeded judgement stops the chain at `7fbb`. The upload
cleanup re-raises the 422 after removing the row and the file; no error is swallowed.

### Gates after the fixes

- Backend: the touched files, 146 passed (`test_cost`, `test_edits`, `test_check_steps`,
  `test_check_queue`, `test_proposals`, `test_uploads`, `test_toc_uploads`, `test_toc_routes`,
  `test_ops_remove_toc_tasks`, `test_migration_054_core`, `test_embeddings`,
  `test_task_agent_toc`); `mypy` clean (244 files); `ruff` clean.
- Frontend (the fix pass): 1,032 tests passed, typecheck clean, lint 0 errors and one pre-existing
  warning. Screenshots from the running `make dev` after the fixes are attached to PR #114
  (1280 and 400 px, a connection selected from the keyboard, the legend, the panel scrolled into
  view on a phone width).
- `make okf-validate`: 211 concepts, 0 violations.
- Full `make verify`: see § Final gate below.

## Rubric status

| # | Status | Note |
|---|---|---|
| 1 Core | Built; evals partial | E1, E2, E6 as specified did not run (deferred); the plausibility and ground-truth evals did. The owner built increments 2 to 6 on it, which is the "good enough to build on" word in practice. |
| 2 Editing | Built in part | Flags stored, not surfaced; no Undo of automatic changes, Keep mine, Restore or the plan-change choice; no barrier race tests (deferred, findings 21 and 22). |
| 3 Web search | Not built | Owner-steered; its own slice. |
| 4 Stress test | Not built | The Task Agent chat discusses the theory. |
| 5 Upload | Built | Type and size checks, the page cap, the audit event, task-scoped reads; the bucket is not yet deployed. |
| 6 Export | Built in part | Browser exports; PowerPoint parked; no export opened in its target tool (deferred). |
| 7 From option | Not built | No W12 ruling recorded; owner-steered. |
| 8 Gates | Holds | Owner's green `make verify` before the stack; the stack's own below. |
| 9 Schema | Holds as amended | Ten reversible revisions, each refusing on its own data; round trips tested for the core chain; the rest step down losslessly when empty. |
| 10 OpenAPI | Holds | Additive only; generated files through `make openapi-sync`; drift check OK. |
| 11 Prompt hashes | Holds | 14 ToC entries added; nothing else changed; 55 files unchanged. |
| 12 Dependencies | Holds | `@xyflow/react`, `html-to-image@1.11.11`; no `python-pptx`. |
| 13 Access | Holds in part | Full matrix on the three public reads; write and upload routes tested for owner, outsider and anonymous (deferred: same-org on every writer). |
| 14 Infra | Holds as amended | Private, encrypted, TLS-only, retained; the backend task role only. The setting is on in staging and off in production (owner, 2026-11-05, below). |
| 15 Tests | Holds | No test deleted, skipped or weakened. |
| 16 Evidence | Holds | This file; the licence note; the evals that ran; exports by tool deferred. |
| 17 Seams | Holds | `docs/deferred.md` § Theory of change. |
| 18 Spec changes | Holds | Five changes present; the build rulings logged 2026-11-05; frozen sources untouched. |
| 19 ADR | Holds | Accepted 2026-10-26, amended 2026-11-05 with the as-built rollback. |
| 20 Review stack | Holds | This section. |

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

## Increment 2: editing, slices A to D (2026-10-30, lead)

Built on `task/054-1-core` from the approved design (contract C40 to C51, `wireframes-editing.html`).
Live checks ran on run 10 (task `f7bb283e`), through a temporary server on port 8001, on the
`openai-6x` route.

| Slice | What was tried live | Result |
|---|---|---|
| A | Add a box, connect it, move it, a stale move (409), History, Undo of the move, Find evidence for the new link | All worked. The named check took 71 s: 10 documents picked and judged, a title written. |
| B | Add a study by DOI (Boyland 2016), a non-DOI address, override its scores, edit #7 then Check again | All worked. OpenAlex and Crossref had no abstract for Boyland, so the judge saw the title only and said "not about"; the override put it in the verdict at once. Check again turned #7 from pending to checked: 4 documents, Confident. |
| C | Find more evidence on #20; Find more on 6 links, then Stop | Find more found 8 documents, all "not about"; fix: only on-topic results now wait as pending. Stop ended the walk before its next step; the page shows "stopped". |
| D | Review the theory; accept its suggestion; a chat request for a failure route and a clarification; Update the report | The review (21 s) found #22 and #23 on no pathway and proposed the full pathway; accepted, it appears in the pathway list. The Task Agent proposed reworking F1 and #16 and said the under-16s change needs a new plan. Update the report (67 s) added "Fruit instead of sweets" and closed the review's suggestion. |

**Deviations from the design, for the owner:**
- Suggestions show in a panel above the canvas; the Task Agent posts a message that points to it
  (the wireframe put the card inside the chat).
- Add a study takes a DOI or a doi.org address; other web addresses wait for web search
  (increment 3), and the user is told so.
- Find more evidence leaves out documents already judged for the link, rather than raising the
  search's record cap (the cap is set per plan step, not per link).
- Check again and Find evidence for new items count their results at once; only Find more
  evidence waits for Accept (a re-check of an edited link moves the counted wording, so pending
  results would leave it with none).
- A merge the user accepts may fold a box the user wrote (the automatic merge still never does).

**Gates:** the full `make verify` for slices A and B found 7 failures, all fixed: five table-count
tests pinned at 49 since iteration 3, a chain test expecting a named check to write the report,
and a route test that needs the local signing key (it passes in the main checkout). The full
`make verify` for slices A to D: 3,869 passed, 2 failed: the same route test (passes in the main
checkout) and a model-route test that lists every step (now includes `toc_review`); both pass.

## Increments 3 to 6 in part, and owner feedback rounds (2026-11-03 to 2026-11-05, lead)

Commits `ec58032d`, `795bd710`, `559a4713` and the commit after them, on `task/054-1-core` (draft PR #114).
These came from the owner's live feedback rounds, not from a separate contract revision. The
review should check them against the rulings below, which the owner gave in the chat.

**What was built:**

| Area | What it does | Owner ruling |
|---|---|---|
| Sense check and verdict | `toc_sense_check` warns in the chat at the plan stage and never blocks. `toc_verdict` leads the report and the end-of-check message. Two axes: the mechanism (plausible or implausible) and the evidence (supported, mixed, too little or against). A whole-programme search and judge runs with every check. | 2026-11-03, after red-team runs where nonsense theories ended "Not enough evidence". There is no "doubtful" level (experiment `plausibility_axes.py`: 93 of 93 judgements right). |
| Queued checks | A check started while a walk runs waits in a queue. It starts when the walk ends. | — |
| Chat code links | Box and connection codes in the chat link to the Result tab. | — |
| Upload your own theory (increment 5, C8) | You can upload a PNG, JPEG or PDF from the new-task page or the chat. A vision call reads it. The canvas shows the diagram as drawn. What would complete it waits as suggestions, route by route. | 2026-11-04: there is no "as drawn or expand" choice. One uploads bucket per environment. The `task_upload` table. Files are kept. Colleagues may see the original, but not on the public leg. |
| Later uploads | After a draft, an upload becomes one suggestion. The suggestion has the boxes and connections that the canvas does not have yet. You can upload more than once, and the chat shows each file at its own message. | 2026-11-05 (items 10 and 11 in part) |
| Draw your own | The Result tab opens from the start. Boxes that you draw before any draft are your own sketch. The draft keeps a sketch that has connections and suggests the rest. "Start drafting yourself" on the new-task page opens the empty canvas. | 2026-11-05 (item 9) |
| Report v7 | The report has these sections: summary, pathways, how it could fail, what to test first, supporting activities, how it could be expanded, and an assumptions table. | 2026-11-04 |
| Exports (increment 6, in part) | The Download menu exports PDF, PNG, SVG, draw.io, CSV and JSON. All exports are made in the browser. | 2026-11-04: PowerPoint is parked, so there is no `python-pptx` (C16 and plan S14 are overtaken; the contract text is not amended, see ADR 0042 § Amendment 2026-11-05). |
| Evidence years, seminal works | Each plan has a year range, from 2000 onwards by default. The most-cited works of the pool are offered to every connection. | 2026-11-04 |
| Editing polish | You can undo an accepted route in one step. Review progress shows in the chat, and you can run Review again. Evidence checks start at once for connections you accept. Suggestions show faded on the canvas. The progress line names the right walk. | 2026-11-05 (items 1 to 8) |

**Migrations:** `c7f2a9d41e08_task_upload`, `e3b9d27c5a14_toc_proposal_discover`, `f5a1c8e93b27_toc_proposal_draft`.
**Infra:** an uploads bucket and its wiring (`infra/infra/policy_atlas_stack.py`, `infra/pa_config.json`).
**Prompts changed (lead-only; hashes in `scripts/prompt_hashes.json`):** `task_agent_toc_prompt`,
`choose_prompt`, `draft_prompt`, `import_prompt` (new), `plausibility_prompt` (new), `report_prompt`.
**Evals:** `scripts/evals/theory_of_change/{plausibility,plausibility_axes,import_diagrams,import_experiment}.py`
and the `import_synthetic` dataset.

**Deviations, for adjudication:**
18. Exports are made in the browser, so there are no export routes on the server. PowerPoint is not built.
19. Web search (increment 3, C7) and links to option tasks (increment 7) are not built.
20. The sense check and the verdict are new steps. They are not in the approved contract; the owner ruled on them in the chat.
21. A box drawn before any draft has `origin "user"`. When the draft adopts the sketch, the box becomes `origin "imported"`, so the box is not flagged as the user's own edit.
22. A later upload never changes the canvas. It only makes one suggestion.
23. Multiple uploads are supported in the chat only (one file at a time). The new-task page still takes one file.

**Gates:**
- Frontend at `559a4713` and after: 971 tests passed. The typecheck and lint are clean.
- Backend: mypy is clean, and the drift check is OK. Before the last fix, the targeted backend tests had 596 passed and 1 failed. After the fix, that test file passed.
- The full `make verify` has not run since 2026-10-30.

**Known unverified:**
- These features have not been tried in the browser: draw your own, later uploads, and "Start drafting yourself".
- The draw.io file has not been opened by hand in diagrams.net or Miro.
- The uploads bucket has not been deployed.

**Review handoff:** the review covers `fba53321..HEAD` together with the merge of `dev`. Leave
these out of the diff: `frontend/openapi.json`, `frontend/src/api/gen/types.ts`, the eval PNG and
SVG files. The two example diagrams used for the import try are not committed. Run
`/security-review` on the upload route, the bucket, and colleague access to originals. Use the
Codex family for the adversarial pass: the lead (Claude) wrote all of this code.

## Merge of `dev` (2026-11-05, lead)

`dev` brought tasks 055 (shortlist), 056 (GPT-6, per-step effort, prompt caching) and 057
(queued full-text ingest, per-step timeouts, module renames). Where the two sides clashed, dev's
design was kept and the ToC code was moved onto it:

- **Model routes:** the `openai-6x` route and the `bedrock-local` ToC overrides were dropped:
  `openai-direct` and `bedrock` now run the same GPT-6 models. The 14 ToC steps are in `[steps]`
  with the tier, effort and timeout they had on this branch. The effort is "none" on Terra and
  "medium" (the provider default) elsewhere. The timeout is 300 s (180 s for the planner).
  `CACHE_MODES` has them too: the planner uses "auto" and the other steps use "breakpoint".
  `OpenAITocBackend` sends the step's effort, timeout and cache mode, and its client no longer
  sets its own timeout or retries.
- **Migrations (rebased, owner's choice):** the ToC chain hung off `f1b6d3a8c2e5`, beside
  dev's 055 to 057 chain. Both re-created `ck_scope_purpose` with only their own new value.
  Dev's migrations stay exactly as written. The first ToC revision `9127f849697f` now follows
  dev's head `0914321f8de4`, and it widens dev's list (with `shortlist`) by `toc`. There is one
  head (`f5a1c8e93b27`) and no merge revision.
  - Checked on Postgres 17: a staging-like database (dev's own migrations, plus a shortlist
    row) upgrades through the ToC chain, and the row survives. A fresh build has the same
    schema as the owner's local database.
  - **One-time step for a local database that ran the old order** (it has the ToC tables but
    not dev's 055 to 057): before the rebase, upgrade it with the merge-revision version of
    this branch. Then run `uv run alembic stamp --purge f5a1c8e93b27`. The owner's database
    and `policy_atlas_test` were done this way on 2026-11-05.
- **ToC evidence read:** task 057 dropped the JSON column `chunk_embedding.vector`. The ToC
  check's document vectors (`check.py`, `_document_vectors`) now read the pgvector column
  `embedding`. mypy did not catch this, because SQLAlchemy looks up table columns by name only
  when the code runs.
- **Renames from dev:** `api.readmodels` became `read_models`. `routers._access` and
  `routers._common` became `access` and `common`. `test_rename_044_sweep.py` was deleted.
- **Tests:** the route tests now count 70 steps. The timeout-site scan counts 22 clients. The
  ingest-queue permission test finds the SQS statement among the API role's statements, because
  the uploads bucket is on the same role. Two migration tests were changed:
  `test_migration_054_core` now starts from `0914321f8de4`, and the 057 round trip upgrades to
  `0914321f8de4` instead of "head".

**Gates after the merge:**
- The backend lint and mypy are clean. The route and timeout tests pass (65). The prompt-hash
  guard reports 55 files unchanged. The drift check is OK.
- The infra unit tests pass (115). The frontend tests pass (1,032).
- **Local database:** moved to `pgvector/pgvector:pg17` (dev's compose file). Steps:
  `pg_dumpall` from Postgres 16, a new container with a new volume, then a restore. All 141
  tables match row for row (726,323 rows). The old Postgres 16 volume
  (`87c995eafd8e…`) and the dump (session scratchpad) are kept as backups.
- **Database tests:** on a clean test database, 288 passed: the migration tests for 046 and
  054 to 057, the route and timeout tests, all ToC tests and the ToC API tests. On the shared
  `policy_atlas_test`, the dev migration round trips refuse: 2 ToC tasks from 2026-11-04 remain
  there, and the ToC downgrade refuses while ToC tasks exist. `make test` resets that database
  first. The full suite has not run.

## Final gate (2026-11-05, after the review stack's fixes)

Full `make verify`, three runs on the same tree:

1. **Fail, 2 of 4,405.** `test_migration_054_beam` and `test_migration_054_layers`: the first
   version of the downgrade guards also covered `7fbb` and `80f4`, whose downgrades are
   designed, round-trip-tested value mappings. The guards were kept on the four revisions that
   drop data (finding 3).
2. **Fail, 1 of 4,405.** `test_each_link_reads_at_most_k_documents_of_its_own_search`: one of six
   child item searches failed under `-n auto` load, with no reason in the output. It passed alone
   three times and in runs 1 and 3. The assertion now prints the failed children's events, so the
   next flake carries its reason.
3. **Pass.** Backend 4,405 passed, 1 skipped (6 min 43 s); mypy clean (525 files); ruff clean;
   prompt-hash guard 55 files unchanged; drift check OK; okf-validate 211 concepts, 0 violations;
   frontend 1,032 tests in 94 files; `vite build` passed.

## The sense check cites its sources (2026-11-05, owner request after the review stack)

The plan-stage sense check's chat line listed its sources as plain titles. It now cites them
as the Evidence search does:

- **Prompt** `toc_sense_check_v3` (lead; re-pinned): the warning or note puts `[id]` after the
  sentence each document supports, and the response gives one quote per cited document, copied
  from its title or abstract.
- **Code** keeps only quotes the shared quote matcher finds in their document, numbers the
  markers `[1]`, `[2]`, moves a marker written after a full stop to before it, and drops a marker
  with no checked quote. A check stored before this keeps the old "What this rests on" line.
- **Wire**: the Task Agent turn gains `sources` (number, title, link, year, quote), additive;
  `make openapi-sync` regenerated the types.
- **Chat**: each marker opens the citation sidebar with the quote and "Open the source"; a
  numbered, linked source list sits under the line.

Tests: `test_a_note_cites_its_sources_by_number_with_checked_quotes` (backend) and "renders a
cited reply with markers that open the citation sidebar and linked sources" (frontend).
Live, on the `openai-direct` route: a Scared Straight plan got "Before you start: A review of US
trials found that prison visits increased offending compared with doing nothing. [1] …", citing
the 2013 Campbell systematic review with a quote found in its abstract. That run came before the
marker move; the unit test covers the moved form. A free school meals plan
the same evening was judged "supports" and, correctly, got no note.

## Switched on in staging (2026-11-05, owner)

The owner asked for the deploy configuration in this PR, so the merge to `dev` makes the
capability usable on staging. Rubric 14 and C15 said the setting stays off in both environments;
this is the owner's ruling over them, for staging only.

- `infra/pa_config.json`: `theory_of_change` is `true` for staging and `false` for production.
  The stack sets `POLICY_ATLAS_THEORY_OF_CHANGE` to `"1"` or `"0"` from it.
- `scripts/deploy.sh`: the staging build exports `VITE_THEORY_OF_CHANGE=1`, beside
  `VITE_OPTIONS_SCOPING=1`. Production builds leave it unset.
- Tests: the API's environment map includes the setting (`"1"` on the staging template), and
  `test_theory_of_change_is_on_in_staging_only` pins the two config values. Infra tests 116
  passed; the deploy build-guard test passed.

## Tidy of the `theory_of_change` package (2026-11-06, owner request)

A restructure with no behaviour change. `check.py` (2,805 lines, six chain steps behind comment
banners) became the package `theory_of_change/check/`: one module per step (`selecting` for
`toc_select` and `toc_search_new`, `discover`, `merge`, `judge`, `figures`, `choose`,
`summarise`), `shared.py` for the reads every step uses and `grade.py` for the verdict rule.
The half-home `evidence/` folder was dissolved into `check/`, and each step's prompt now sits
beside it. The module is called `selecting`, not `select`, so it never shadows SQLAlchemy's
`select` in an importer. Nothing in `runtime/` moved (owner ruling: that is a later sweep
across all three capabilities).

Evidence:

- Every one of the 85 top-level definitions of the old `check.py` is AST-identical to its copy
  in the new modules (a script compared `ast.dump` of each; none missing, none extra, none
  changed). `ruff format --diff` on the old module reports zero lines, so the moved text keeps
  its formatting.
- `scripts/prompt_hashes.json` re-pinned: path keys moved, every hash value unchanged;
  `make prompt-guard` reports 55 prompt files unchanged.
- `make -C backend lint` and `make -C backend typecheck` clean (531 files).
- `make okf-validate`: 211 concepts, 0 violations (one path updated in
  `lower-grade-colours-the-canvas.md`).
- Targeted run: `tests/theory_of_change`, `test_toc_plan`, `test_capability_registry`,
  `test_task_agent_toc`, `test_toc_uploads`, `test_toc_routes`: 230 passed.
- Full run: `make -C backend test-fast`: 4,366 passed, 1 skipped, 2 failed under `-n auto` (`test_figures.py::test_the_step_stores_checked_figures_and_the_read_attaches_them_to_the_box`, `test_walks.py::test_a_check_already_following_the_draft_is_not_minted_twice`, a duplicate `event_log` sequence and a missing row). Both pass 3 of 3 re-runs alone and in the targeted run above; the moved code is AST-identical, so this is the shared-database race class in `failure-log.md` (2026-07-11), not the restructure.
- Adversarial review (Codex, read-only brief: surviving old paths, monkeypatch targets, import
  cycles, run-time name lookups, structure judgement): one low finding, stale `evidence/` paths in living docs, fixed in `components.md`, `lower-grade-colours-the-canvas.md` and `beam-method.html`; the `judge_prompt.py` docstring (line 12) was fixed on the owner's request and its hash re-pinned (the only change in that module is the path in the docstring; the prompt text is untouched). The eval prompt drafts keep the old path. Nothing found for surviving imports, monkeypatch targets, import cycles or run-time name lookups. Structure verdict: keep the split and the `selecting` name; keep the underscore helpers package-private, except that `report.py` imports `_ask` and `_year` from `shared.py`, which the reviewer suggests making public in the later runtime sweep.

### Live runs after the tidy (2026-11-06, lead; port-8002 server on this checkout, `openai-direct`)

Two full runs, draft then check, started through the API as the end-to-end command above does,
one with the usual opening message and one on a new topic. Both completed every step on the
restructured code.

| Run | Task | Topic | Time | Cost | Boxes / links | Confidence | Links with no on-topic evidence |
|---|---|---|---|---|---|---|---|
| A | `5ef199d8` | unhealthy food advertising (the usual message) | 4 min 50 s | $0.53 | 20 / 22 | not sure, insufficient | 7 |
| B | `1c53c120` | universal free school meals in primary schools | 7 min 0 s | $0.55 | 22 / 26 | leaning against | 7 |

Cost is the `run.finished` cost payload (model cost of the check walk). The higher cost than runs
4 to 7 ($0.37) is the route and the later prompt versions (judge v8, figures, report v7), not the
move: the code is AST-identical.

One artefact to know about: at 12:38:52 run B's check walk received a `run.interrupted` event
from the API's boot-time sweep (`continuation.startup_sweep`), which another backend process on
the same dev database wrote when it restarted (the owner's `make dev` on port 8000 runs with
`--reload`, and a second server sat on port 8001). The walk kept running in its own process and
finished `succeeded` ten seconds later; the row's final status is `succeeded` and the page reads
`checked`. The poller showed `failed` for those ten seconds. This is the multi-process hazard of
one shared dev database, not the restructure.

### The `confidence` field removed (2026-11-06, owner ruling)

The graph read returned `confidence`, the lowest verdict among the critical links, as the theory's
overall confidence. No screen, export or prompt read it, and in live run B it contradicted the
report (the critical link #21 leaned against while the report's two-axis verdict read "Evidence
supports it"). The owner ruled that the report's verdict is the overall judgement and the critical
link is a pointer, so the field is removed from `TocGraphOut` and the router; `grade.lowest` stays
for the report's per-pathway verdicts. `make openapi-sync` regenerated the types; `drift-check`
OK; lint and mypy clean; 91 backend tests and 70 frontend ToC tests pass.

### Verdict values renamed (2026-11-06, owner ruling)

The two ends of the link verdict scale were `confident` and `not_confident`, while their labels
read "Supported" and "Evidence against". The values are now `supported` and `against`; the four
middle values and every label are unchanged. Nothing is deployed, so no compatibility shim. Touched:
the contract enum, `grade.py`, the report's supported set, three backend test files, the
ground-truth scorer and the judge-context rescorer under `scripts/evals`, the eval scheme note,
and in the frontend the CSS edge and text classes keyed by value, the model, reading guide,
documents view, draw.io export styles, fixture and one test. CSS colour variable names and prose
stay. No prompt carries the values: `make prompt-guard` unchanged. `openapi-sync` and
`drift-check` OK; lint and mypy clean; 203 backend ToC tests and the full frontend suite (1,033)
pass.

### Find more evidence: twice the results, and a busy button (2026-11-06, owner request)

- **Search.** A find-more check now dispatches its item searches with `link_scale: 2` in the
  child context (`TOC_FIND_MORE_SCALE`). The compose seam puts it in the acquire directive, the
  search loop's parser admits it (1 to 4, link depth only), and the five link calls ask for twice
  their results (40 / 20 / 20 / 20 on OpenAlex, 20 on Overton) under twice the cap (120). The
  select step already drops the documents judged before, so the extra results are new candidates.
  Tests: `test_toc_plan.py::test_find_more_evidence_doubles_the_item_search`,
  `test_search_link_depth.py::test_find_more_evidence_asks_every_call_for_twice_the_results`.
- **Button.** `CheckButton` reads "Finding evidence…" and is inactive while every link it names is
  in the `checking` state (the running walk names them); test in `TocResult.test.tsx`.
- Checks: ruff, mypy, frontend typecheck and lint clean; 61 backend tests on the plan, link
  depth, acquire-only walk, option search and light check; 71 frontend ToC tests.
- Not tried live: a find-more run on a checked theory. The sizes are unit-tested; the live cost
  of one find-more check is about twice a link search's share of the $0.53 runs above.
- **Picked and judged documents (owner, same day).** Doubling the search alone still judged ten
  new documents per link, because `toc_select` picks `PICK_N` (10) and `toc_judge` reads
  `JUDGE_TOP_K` (10). Both now come from one rule (`selecting.documents_per_link`): a find-more walk picks
  and judges up to `TOC_FIND_MORE_PER_LINK` = 40 per link (owner, 2026-11-06), and the
  shared-pool and seminal candidates offered to the pick call grow with it. The pick prompt's size is filled at call time; for the ordinary 10 the
  rendered prompt is byte-identical. `pick_prompt.py` re-pinned: the diff is the `n` parameter,
  one comment line and the `{n}` fill moving from import time to call time; no prompt wording
  changed. Test: `test_check_steps.py::test_find_more_evidence_picks_and_asks_for_twice_the_documents`.
  Checks after this: ruff and mypy clean; 213 backend tests across the ToC suites, the plan,
  link depth, acquire-only walk and option search.

### A smarter second search (2026-11-06, owner request)

The find-more live run on task `bca650b2` showed why doubling the page found nothing: the same
five queries returned 62 of 83 documents the task already held, and the judge read handouts from
the shared pool. Two changes, both ruled by the owner on the day:

- **Reformulated search.** A find-more item search carries the link's earlier queries (read from
  its earlier child walks' `search.executed` events, clauses stripped, four at most) in the
  guidance channel, with a brief to write in the vocabulary of the research that would test the
  step. The searches by meaning and the Overton call run on the writer's research-style paraphrase
  instead of the step's sentence (`search.reformulate` in the directive; `REFORMULATE_GUIDANCE` in
  `item_search_prompt.py`, re-pinned: new text added, the first-search guidance untouched).
- **One automatic second round.** A new check step, `toc_search_again`, after the judge and
  before figures: the runner dispatches one reformulated search per link whose verdict is *Not
  enough evidence* (`selecting.links_without_evidence`, stage `toc_retry_searches`), the step picks
  each link's new documents (already-judged ones left out) and judges them; they count. Full
  checks and new-items checks run it; Check again and Find more skip it (the user is steering).
  The judge gained an `only` subset; the whole-programme judgements are not repeated. Priced at
  the judge's rate in `cost.py`. The running card and the trace name both stages.
- Tests: compose (`test_a_reformulated_item_search_carries_the_earlier_queries`,
  `test_check_again_and_find_more_skip_the_second_search`), the link depth
  (`test_a_reformulated_search_searches_by_meaning_on_the_paraphrase`), the chain and walk order,
  and the unverified-quote test now counts both rounds. Checks: ruff and mypy clean; the ToC,
  plan, link-depth, acquire-only, option-search, run-spec, task-plan, branch-sites and harness
  suites pass; frontend typecheck, lint and workspace tests pass.
- Prior evidence (2026-10-27) found a second round with the *same* queries added nothing; this
  one changes the words, and the live run below is its first measurement.

**Live run C** (2026-11-06 15:05, task `731ddd03`, the usual advertising message, port-8002 server on
this checkout, `openai-direct`): draft and full check in 7 min 24 s, $0.67 (run A, before the second
round: 4 min 50 s, $0.53). After the judge, 11 of 22 links had *Not enough evidence*; each got one
reformulated search (stage `toc_retry_searches`, 11 children, all `reformulated`), and
`toc_search_again` picked and judged 110 new documents, 48 on topic.

| | Searches | Results | New to the task | Already held |
|---|---|---|---|---|
| First round | 23 | 983 | 424 | 395 |
| Second round (reformulated) | 11 | 472 | 96 | 263 |

The earlier same-words find-more on task `bca650b2` returned 1 new document in 83. After the second
round, 6 of the 11 thin links moved up (#2, #3, #7, #9, #22 to *Leaning supports*; #12 to
*Supported*) and 5 stay thin (#5, #8, #14, #17, #19); the theory ends with 9 supported, 7 leaning
supports, 5 not enough evidence, 1 against. The new queries are research questions ("Do
restrictions on paid online advertising of less healthy foods reduce children's exposure to that
marketing in practice…") and new keyword queries ("children digital food marketing exposure
restriction evaluation"); for #9 the keyword query was close to the first round's with two words
dropped, so the writer does not always move far. One topic, one run: a measurement, not a result.
- **Adversarial review (Codex, read-only, same day).** One finding: the walk clean-up that ends a
  parent's children on abort (`option_search.abandon_children`) listed the first two item-search
  stages only, so retry children of an aborted walk would have kept acquiring. Fixed by adding
  `TOC_RETRY_SEARCHES_STAGE` to that list. Nothing found on double judging, the judge's `only`
  subset, the empty-retry fallback (an empty pick stays an explicit empty set, so the judge does
  not fall back to the pool), earlier-query leakage across links or tasks, directive parsing,
  duplicate dispatch on resume, or the frontend stage names and counts.

### Draft on Sol against Terra (2026-11-06, owner request)

`toc_draft` moved from `standard` / effort `none` (gpt-6.1-terra) to `frontier` / `medium`
(gpt-6.1-sol) in `model_routes.toml`, and the usual advertising message ran again (run D, task
`ee2a6abb`) against run C (task `731ddd03`, same message, Terra draft, 11 minutes earlier).

| | Run C, Terra | Run D, Sol |
|---|---|---|
| Draft latency | 54 s | 87 s |
| Draft tokens | 14,237 | 8,789 |
| Drafted boxes / links / pathways | 15 / 15 / 5 | 15 / 17 / 6 |
| Boxes marked as the user's words | 0 | 3 (the two interventions, the impact) |
| Whole run | 7 min 24 s, $0.67 | 7 min 53 s, $0.66 |
| Judge: documents, not about | 220, 77 | 220, 89 |
| Second round: links, judged, not about | 11, 110, 62 | 10, 100, 69 |
| End verdicts | 9 supported, 7 leaning supports, 5 not enough, 1 against | 7 supported, 8 leaning supports, 5 not enough, 2 mixed |
| Report headline | Evidence supports it | Evidence supports it |

Quality, by reading the two drafts: Sol's draft has three mechanisms Terra's lacks (suppliers
reformulating and advertising healthier replacements; children buying less themselves; the
compensation failure route "other foods replace the calories"), its failure outcomes are more
specific (older children's exposure unchanged; unpaid promotion replacing paid adverts), and it
tags the user's own interventions as theirs. Terra's draft is plainer and closer to the owner's
wording ("Children ask less often for advertised less healthy foods"). Both reports reach the same
verdict with the same caveats (online exposure uncertain, obesity reductions modelled, not
measured). One topic, one run each. The route file keeps Sol until the owner rules; the
2026-11-04 ruling put the draft on the middle tier.
- **CI failure after the push (2026-11-06 15:42, `make verify`):**
  `test_classify_reads_only_what_the_judge_found_on_topic` failed: four documents judged on topic
  were not classified. Cause: the judge screened out every pool document without an on-topic
  evidence row, but the whole programme's on-topic judgements live in the programme event, not in
  evidence rows, so a judge that skips the programme (the second search, and any named-link check,
  C40) screened the programme's documents out and classify never read them. The stub judge's
  verdicts follow random ids, so the second search did not always fire locally. Fix: the judge
  screens out only the documents it read in this call. Regression test:
  `test_the_second_search_keeps_the_programme_s_documents_classified` (every link thin, the
  programme on topic). The ToC suite passed three times in a row after the fix; one unrelated
  seminal-lookup test failed once in the first run and passed alone and in ten further runs.
