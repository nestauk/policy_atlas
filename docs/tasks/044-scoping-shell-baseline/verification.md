# Verification: 044-scoping-shell-baseline

Evidence for the build phase (steps 5–6). Public-safe: no secrets, raw source
text, credentials or unredacted traces. Filled as each phase closes; **Review
findings** and **Rubric status** are added by the review conversation (step 7).

## Commands run

### Phase 0 — build-open baseline (2026-09-09)

| Command | Result | Notes |
|---|---:|---|
| `make verify` at `b4b1e93b` | fail | backend 2552 passed; typecheck, lint, build green; **`infra` test red**: `test_dockerignore_covers_gitignored_backend_content` — `b4b1e93b` added `PRODUCT.md` and `DESIGN.md` to `.gitignore` without the Docker-ignore mirror. Not this slice's change. |
| hotfix `5854676a` (`backend/.dockerignore` +2 lines) then `make audit-paths prompt-guard font-guard drift-check frontend-verify` | pass | frontend 79 files / 617 tests; the remaining stages that the infra failure had skipped |

The base was green before any 044 code landed. The hotfix is one commit on
this branch, outside the rename phase's reviewed diff.

### Phase 1 — Task Agent rename and EB → ES sweep (2026-09-09)

| Command | Result | Notes |
|---|---:|---|
| `scripts/rename_044.py --apply --phase 3 / 4 / 5` | pass | 46 / 49 / 31 files; 715 / 457 / 177 replacements; second `--apply` on each phase: 0 changes; `--scan --ignore-ledger`: 0 unmapped, 0 collisions |
| `make verify` (full) | pass after re-sync | backend 2615 passed (8:15); typecheck, lint, build green; infra 46 passed; audit-paths, prompt-guard (13 unchanged, one path moved), font-guard green; `drift-check` was red once because the docs sweep touched contract-model docstrings after the last `make openapi-sync` — re-synced, `drift-check: OK` |
| `cd frontend && pnpm e2e` | pass | 11 passed (13.4s), mock mode |
| `make okf-validate` | pass | 143 concepts, 0 violations |
| `backend/tests/scripts` (038 + 044 tool tests, sweep test) | pass | 121 tool tests; the sweep test's five docs paths green after 1.4 |

**Rename sweep result (contract § Acceptance checks):** no `planning_transcript`,
`/planning-turns`, `PlanningTurn`, `PlannerBackend`, `planner_prompt`,
`POLICY_ATLAS_PLANNER_MODEL` in `backend/src`, `frontend/src`, `frontend/e2e`,
`infra/DEPLOYMENT.md`, `web-api.md`; no `planner_state`, `created_by = 'planner'`
or `planning`-named constraint in `schema.py`; allow-list honoured
(`eb_iof_base_v1`, `eb_icf_base_v1`, `evidence_base_coverage`, `planner_v\d+`,
the `"role": "planner"` literal, `planner-proposed`, the kept prompt module's
symbols); the old path is 404; `PLANNER_PROMPT_VERSION == "planner_v11"`
(`backend/tests/scripts/test_rename_044_sweep.py`).

**EB → ES grep** (`grep -rn -w EB` over `docs/specs` minus `sources/` and
`log.md`, `docs/agentic-ops`, `docs/tasks/_templates`, `AGENTS.md`,
`.claude/skills`, `backend/src`, `frontend/src`, `docs/knowledge`): the only
remaining hits are the four "EB handoff" citations (`product.md:11`,
`index.md:15`, `plan-as-object.md:100`, `spec-authoring.md:14`), kept by
ruling (they name the frozen source document).

**Prompt-hash diff:** one key moved, `runtime/planner_prompt.py` →
`runtime/task_agent_prompt.py`, value `4e85172f…8ce2` unchanged; no other
entry changed.

**OpenAPI diff:** one path renamed, four schemas renamed (`TaskAgentTurnCreate`,
`TaskAgentTurnOut`, `TaskAgentTranscriptTurnOut`, `Page_TaskAgentTranscriptTurnOut_`),
two operation ids, the conversation `kind` enum value `planning` →
`task_agent`, docstring text; `planner-proposed` unchanged; nothing structural.

**Migration round-trip** (`test_migration_044_rename.py`): upgrade renames the
table, column and the ten catalog-named constraints and indexes, moves both
stored values; downgrade restores the seeded fixture byte-identically; upgrade
again.

### Phase 2 — task kind, links, registry, slice revision (2026-09-09)

| Command | Result | Notes |
|---|---:|---|
| `make verify` (full) | pass | backend 2674 passed (8:01); frontend 625 tests / 80 files; okf 143/0; mypy 320 files clean; ruff clean; infra 46; audit-paths 0; prompt-guard unchanged; `drift-check: OK`; build OK |

Revision `b5e1d7a4c026` (revises `a7d3f1c8e2b5`): `task.capability` +
`ck_task_capability`; `ck_capr_capability` widened; `uq_plan_id_task`;
`evidence_scope.purpose` + `ck_scope_purpose`; `evidence_scope.plan_id` +
composite `fk_scope_plan_task`; `task_link` with its primary key, the two plain FKs to `task` (source, target), `fk_task_link_source_run_task`,
`uq_task_link_pair`, `ck_task_link_distinct`, `ix_task_link_target_task_id`.
Downgrade refuses while any `task` or `capability_run` row carries
`options_scoping`, naming `scripts/ops_remove_scoping_tasks.py` (A5); the
round-trip test proves the refusal and the operator script's FK order.

**Registry (S1):** all validate sites (ten at this phase; fourteen by the step-6 exit — phases 3, 5.2, 5.4 and the live-check fixes added four, all routed; the AST seam test is what makes the count safe) and seven compose sites route through
`runtime/capability_registry.py`; `_open_capability_run` writes the task's
capability; `pause_points` / `lattice_name_for` / `lattice_policy` take the
capability's lattice (`lattice_policy` returns `off` for a name outside the
given lattice — A2's protection). **Deviation from S1 as written:**
`SteerPointDefault`'s validator was not routed through the registry —
`task_plan.py` cannot import the registry (cycle via `steering`); the ES
validator keeps checking `STEER_POINTS`, the registry's ES `steer_points` is
`frozenset(STEER_POINTS)` and a test pins the two together; the scoping plan
gets its own set the same way (Phase 3.2).

**Left for Phase 5, deliberately:** the four `lattice_name_for` /
`lattice_policy` calls inside the runner's boundary loop still take the ES
default because `_SteeringState` carries no capability; identical behaviour
today (`lattice_for("evidence_search") is LATTICE_POINTS`). Phase 5.2 must
put the capability on `_SteeringState` or `baseline_confirm` never fires.

**OpenAPI diff:** additive only — `TaskLinkOut`; `TaskCreate.capability`,
`.project_ids`, `.from_task_ids`; `TaskOut.capability`, `.from_task_ids`,
`.links`; three description strings replaced. No path or field removed or
retyped.

**Gotcha recorded:** the downgrade refusal bites the whole migration-test
family when any test commits a scoping task and leaves it — an autouse
cleanup in `test_task_links.py` deletes links then tasks. Any later test that
commits a scoping task must clean it up.

### Phase 3 (backend: 3.1 prompt, 3.2 plan/chain/router, 3.3 inherit) (2026-09-09)

| Command | Result | Notes |
|---|---:|---|
| `make verify-fast` | pass | backend 2740 passed (8:05); mypy 327 files clean; ruff clean |
| `make prompt-guard` | pass | 16 modules unchanged (the three new surfaces pinned at 91beec2a) |
| `make openapi-sync` + `make drift-check` | pass | `drift-check: OK` |
| `tests/runtime/test_inherit.py` | pass | 5 tests, rolled-back fixtures |

**Flagged deviations (3.2):**
7. **`PlanOut.plan`, `TaskAgentTurnOut.plan` and (found at the review stack, verifier F6) the SSE `PlanUpdatedFrame.plan` became nullable** — a scoping
   plan has no Evidence search payload. The contract asked for additive
   fields only; nullability of an existing field is a type widening the
   frontend must null-check (done in 3.4). Everything else in the diff is
   additive (`ScopingPlanDraft`, `ScopingPlanPatch`, `TaggedOut`,
   `ScopingConstraintOut`, `YourContextOut`, `ScopingSteerPointDefaultOut`,
   `BaselineConfirmedOut`, `ConfirmBaselineIn`; `capability`, `scoping`,
   `scoping_plan` fields).
8. **One new acquire directive key, `search.record_cap`** (plan S2 allowed
   it): the grammar had no per-backend cap key (caps came from
   `DEPTH_CONSTANTS`); fail-closed integer `1..200`, absent = today's
   behaviour; `BASELINE_ACQUISITION_TARGET = 25` per backend (measured in
   Phase 7; **superseded in phase 8** by `BASELINE_ACQUISITION_TARGETS` 20 · 10 per backend by depth).
9. **`synthesis_tools` grammar widened for template mode only:** `nav_label`
   accepted on supplied sections (it was read but unreachable); `section_budget`
   no longer caps the supplied list when `template` is present (P14: it means
   "proposals allowed"); `DIRECTIVE_TEMPLATE_FOCUS_MAX = 600` for template
   foci (lead-authored code, not untrusted directive text — the 200-char
   bound stays for everything else). Lead confirms all three.
10. **`tests/helpers.delete_task_data`** nulls `evidence_scope.plan_id`
    before deleting plans (the new composite FK); shared helper, additive.
11. **Inherit coverage statement** ports the existing `coverage_out`
    sentence ("Searching completed. Coverage was judged adequate."), not the
    spec's aspirational "documents retrieved and passed … not searched"
    wording, which no read model builds yet.

**Counts pinned:** the supplied baseline section list is seven model-written
sections plus the code-rendered Sources = 8 = `SECTION_CAP`.

### Phase 3 (frontend: 3.4) — commit f2c89752 (2026-09-09)

| Command | Result | Notes |
|---|---:|---|
| `make frontend-verify` | pass | 676 tests / 80 files; lint 0 errors; build clean |
| `cd frontend && pnpm e2e` | pass | 12/12 (new `scoping.spec.ts`: New task → Options scoping → Prepare plan → plan document) |

Start-action states are driven by the latest baseline walk's own status
(build · none while running or paused · confirmed · rebuild-or-confirm); the
lead corrected the worker's first "newer version" heuristic, which would have
offered `confirm-baseline` while the walk was paused (409). Commit gated by
the frontend lane only: the backend suite was under concurrent Phase 5
edits at the time; the full `make verify` follows at the Phase 5 boundary.

### Phase 4.2 — baseline mode — commit cd92b1e8 (2026-09-09)

| Command | Result | Notes |
|---|---:|---|
| `pytest tests/evidence_search/synthesis tests/runtime/test_scoping_compose.py tests/runtime/test_scoping_plan.py tests/runtime/test_runner.py tests/runtime/test_progress.py` (fresh DB) | pass | 331 passed; 15 baseline tests |
| `make prompt-guard` | pass | 16 unchanged after the `BASELINE_ARTEFACT_TITLE` re-pin |
| `make verify-fast` (shared DB, concurrent edits) | red, attributed | 45 failures, all from Phase 5.2's in-flight `ContinuationState(capability)` change and the stranded-row cascade it caused; none in synthesis. Full gate at the Phase 5 boundary |

**Lead rulings during 4.2:** the two further ES-shaped passes (most-relevant-
source notes, full-report intro) are off in baseline mode as well (five
passes total); `turn_cap` is emitted by the compiler so the grammar key is
live; the artefact title is the Baseline board's; `section_set.source`
unchanged. Sources counts come from the appraised set (grey vs academic by
acquisition backend — the only honest signal; no literature-kind column
exists) and the restrictions from the approved plan row, since the scope
context carries only target unit, where and outcomes.

### Phase 4.3 — Result view — commit 7fbc3778 (2026-09-09)

| Command | Result | Notes |
|---|---:|---|
| `make frontend-verify` | pass | 696 tests / 82 files |
| `cd frontend && pnpm e2e` | pass | 13/13 (new leg: Result shows the band, the depth label and Sources, no Executive summary) |
| `make openapi-sync` + `make drift-check` | pass | `ArtefactOut.template`, `.depth_label` additive |

### Phase 4.4 — feasibility check 7, writing mode (2026-09-09; nothing ships)

Script: `scripts/feasibility_checks/options_scoping/run_check_7_writing_mode.py`
(035 pattern; runs the product's own `synthesise_scope` in baseline mode
against dev-database screened scopes, every run rolled back). Corpora: the
035 NEET scope (59 screened-in / 53 appraised) and the thinnest screened
scope on the machine (36 / 27, social media and young people's mental health;
a substitution — no thinner 035 corpus was loaded). The parallel arm is a
naive fan-out of seven one-section runs with empty ledgers joined in the
ruled order; the extras proposer was stubbed off in both modes so the
comparison holds to the seven required sections. Numbers read back from
`check7/<corpus>/{sequential,parallel,compare}.json`:

| | NEET sequential | NEET parallel | thin sequential | thin parallel |
|---|---:|---:|---:|---:|
| wall clock, writing (s) | 183.0 | 62.7 | 139.9 | 32.2 |
| slowest section (s) | 36.4 | 62.6 | 26.7 | 32.1 |
| generation calls | 28 | 28 | 29 | 23 |
| tokens (total) | 273,250 | 296,180 | 228,246 | 182,013 |
| claims minted | 71 | 49 | 48 | 48 |
| repeated 8-word clauses | 20 | 29 | 56 | 19 |
| repeated figures | 6 | 8 | 0 | 1 |

**Lead reading.** Parallel writing is about three times faster on wall
clock (two minutes saved on the NEET baseline) at the same call count. The
consistency reading is mixed, not one-sided: on the rich corpus the parallel
arm repeats more clauses across sections and mints fewer claims (the Key
assumption section fell from 6 claims to 2); on the thin corpus it repeats
less. Both modes restate figures across sections; neither is free of
repetition, so the ledger is not what prevents it. **Sequential stays the
shipped mode** (owner ruling C6; the durability contract's "never fan out
the conclusion"). The two-minute saving is recorded here as the case the
owner would weigh in a future revision of that contract; a real parallel
mode would need a durable join and the extras proposer decided once, not
per arm. The bound (a concurrent ledger) did not fire.

### Phase 5.2 — the gate — commit 234a4f79; 5.3 — answer core — commit b4650560 (2026-09-09)

| Command | Result | Notes |
|---|---:|---|
| 5.2 `make verify-fast` | pass | 2779 passed; mypy 333 files clean; ruff clean; 18 new tests |
| 5.3 targeted suites | pass | `tests/api` 472 passed (the one failure was 5.2's in-flight `ContinuationState(capability)`); 32/32 on the final targeted re-run; `make openapi-sync` + `drift-check: OK` (additive: `AnswerPayloadOut`, `TurnDecisionOut`, three optional turn fields) |

**Deviations (5.2):** the runner chassis and continuation reducer were typed
Evidence-search-only (`expect_task_plan` narrowing in `ContinuationState.build`;
`plan.backend_scope` and `plan.search_effort` reads on the hot path), so a
scoping walk could not reach the gate code at all — they were made
capability-agnostic (`AnyPlan`; ES-only hand-offs narrow and fail loudly).
`capability` on the two state dataclasses carries an ES default so the
existing steering tests construct them unchanged (every production site passes
it). `stage_vocabulary` maps `baseline_confirm` → stage `synthesise` rather
than adding a `StageKey` member (a contract enum change). The CLI/stub
Continue at the gate does not attach `artefact_id` (only the API path does).
**Deviations (5.3):** `answer_over_scope` gained `on_progress`,
`conversation_id` and an `AnswerBackends` bundle to keep the chat route
byte-for-byte; `DecisionOut` → `TurnDecisionOut` (name collision with the
decision-log model); two chat tests' monkeypatch targets moved with the lifted
code; the core still traces as `component="chat_v1"` (5.4 may relabel).

### Phase 5.4 — the turn at a pause — commit 5c6335d1; 5.5 — the thread — commit 1ba6350d; copy pass 3ea1053e; 5.6 spec revision ab4e1ada (2026-09-09)

| Command | Result | Notes |
|---|---:|---|
| 5.4 `make verify-fast` | pass | 2797 passed; mypy 335 files clean; ruff clean; 18 new tests incl. the barrier race and the replay / partial-failure / retry trio |
| 5.4 `make prompt-guard` / `make openapi-sync` + `drift-check` | pass | 16 unchanged; the only generated delta is a route docstring |
| 5.5 `make frontend-verify` | pass | 715 tests / 82 files |
| 5.5 `cd frontend && pnpm e2e` | pass | 15/15 (gate card + cited answer; Change the plan → decision → Rebuild / Confirm) |
| copy pass `make frontend-verify` | pass | 715 / 82 |

**Dispatch at the gate (5.4):** question → answer core, walk stays paused,
the decision offered back after every answer (the sort has no "mixed" flag,
so every answer at the gate offers it; never applied); decision → the
check-in response transaction (confirm resumes the walk to `succeeded`;
change_plan ends it `aborted`, plan stays `approved`); change_plan with text →
one row, two commits; the loser of a chat-versus-card race keeps a durable
turn saying the check-in was already answered (HTTP 200, `decision = null` —
the durable decision is the other surface's); unsure → asked back with the
two options. **Deviations:** `POST /runs` stopped narrowing to the ES plan
(a scoping rebuild could not start otherwise); `_task_agent_inputs` accepts a
null `task_agent_state` (a gate turn moves no draft). **5.5:** the plan
document is read-only only while a walk is *active* for a scoping task (the
ES rule — any run — stays), which the e2e showed was needed for
rebuild-or-confirm to be reachable at all; `already_answered` keeps the
existing copy and joins `stale_turn` on the Refresh affordance; the gate's
two thread items are placed by time among turn-ordered items (a pause and
the turns a paused walk accepts genuinely interleave).

**Gate-sort latency:** not measurable on the stub path; the live check times
it from the Langfuse span `agent:gate_sort` (usage event
`agent.gate_sort.usage`, label `agent-gate-sort`).

### Phase 5 boundary — full gate at 5c6335d1 (2026-09-09)

| Command | Result | Notes |
|---|---:|---|
| `make verify` (full) | pass | backend 2797 passed (8:25); typecheck, lint, build green; infra 46; audit-paths, prompt-guard, font-guard, drift-check green; frontend 715 tests / 82 files |
| `cd frontend && pnpm e2e` | pass | 15/15 |

### Phase 7 — live check (a)–(g), local app, real egress (2026-09-09/10)

Driven through the local API with a dev-issuer token (the Chrome extension
was not connected, so the drive is scripted; screenshots were taken
afterwards with headless Playwright against the live frontend). Dev DB at
`b5e1d7a4c026`. Evidence files (task and run ids, turn payloads, artefacts,
check-ins, decisions, coverage, screenshots) are in the session scratchpad;
`docs/tasks/*/evidence/` is gitignored, so they travel as the PR's evidence
zip, as 027/028 did.

| Step | What happened | Measured |
|---|---|---|
| (a) seed | The dev DB's completed NEET Evidence search (task `1e03e719…`, succeeded walk, one artefact) — given an owner and a project by two dev-DB rows so it is linkable (it had neither) | — |
| (b) create | `POST /tasks` with `capability: options_scoping`, the project and `from_task_ids: [NEET]` → 201, one link pinned to the source walk, `flagged: false` | — |
| (c) turns | Turn 1 proposed from the linked plan (Where "England" assumed from the linked task, three outcomes tagged), asked who should change with three options. Turn 2 (the Frame board's compound message) typed all four constraints — requirement (longlist), evidence restriction (retrieval, OECD members pinned), two preferences (assessment) — set depth standard and became ready; it did **not** ask the kind question because "Only evidence from OECD countries" is unambiguous. An ambiguous "Also: Nordic countries only." got the kind question verbatim plus the Where warning (D8). `GET /plan` showed every section with origin tags | turn latencies 13.7 s · 19.2 s · 13.6 s · 6.3 s |
| (d) baseline 1 | `POST /runs` on plan v2 (the Nordic exchange had made v1 `plan_stale`; one closing turn re-approved). Acquire hit the baseline cap (25 per backend, 50 acquired, 22 s search; phase 8 lowered the cap to 20 · 10 per backend by depth). Paused on `baseline_confirm`. Result: "Do nothing: current policy and trajectory", `scoping pass`, seven required + **two proposed** sections after "What is contested" + code-rendered Sources ("32 sources from Overton and OpenAlex … Live official statistics and departmental pages were not searched … 18 grey literature and 14 academic articles. The profile leans on grey-literature sources."). Card: two options, key assumption, Settings | **389 s** from `POST /runs` to `paused` (15 s poll) |
| (e) gate | Question "Is the rise in NEET real, or did the survey change?" → `kind: answer`, 4 citations, the two decisions offered back, walk still paused. Instruction "Change Where to the whole United Kingdom" → `kind: decision` (change_plan, bound to run · check-in · plan version 2), walk `aborted`, plan **v3** with Where = United Kingdom `from_your_question` — one row, two commits. Rebuild (`POST /runs` on v3) → paused on the gate again, 10 sections | answer turn 33.5 s (gate sort + answer); change turn 6.8 s; **rebuild 453 s** to `paused` |
| (f) confirm | "Looks right. Confirm the plan and build the longlist." → `kind: decision` (confirm_plan, plan version 3), walk `succeeded`; `/decisions` lists both recorded steering decisions. A preference added afterwards → plan v5 with the code-authored sentence "This change does not touch what the baseline (built from plan version 3) was built from…"; `POST /plan/confirm-baseline` → v6 recording `{baseline artefact, plan_version 5}`, idempotent on repeat | confirm turn **2.3 s** (the gate sort is bounded by this: about one to two seconds) |
| (g) ES smoke | New Evidence search task → two Task Agent turns → approved ES plan v1 (`search_effort standard`, `analysis_depth standard`) on the shared turn path | 19.6 s · 10.8 s |

**Defects the live check found and fixed on the branch** (each with a test):
`GET /plan` 500 on a linked scoping plan (strictness on the list, not the
UUID item — `352ad7ca`); the S4 "inputs changed" sentence was not implemented
and a baseline no longer counted as existing after an aborted walk
(`a9404d23`); the successor Task Agent conversation after a finished walk was
seeded through the ES-only path (500 — `8e17ed6a`); the gate card of record
printed the depth key; a scoping walk continued past a triggered generic
pause crashed at the next boundary in the agent watch, and `GET /events` 500d
on a scoping plan (both `e063a69b`: a non-ES walk is routed past the agent
watch with a recorded verdict; the `plan.updated` frame carries a scoping
plan); the gate's check-in was written with the generic kind so the thread
never opened the composer at the gate (`ed0fbde5`: the read model reports
`baseline_confirm`). **Frontend, from the screenshots:** the band said
"awaiting your confirmation" after Confirm — the confirm record is minted as
a new version but stamped with the previous version number, so the "record
names the current version" rule never held (fixed by stamping the minted
version, below); the ES "Most relevant sources" block rendered on a baseline
(hidden for the baseline template).

**Screenshots** (scratchpad `live-evidence/shots*`): the Agent tab with the
decision line, the appended sentence and the open composer at the gate; the
Result with the band reading "plan confirmed · the longlist arrives with the
next stage · built from plan version 3", the `scoping pass` eyebrow and the
flat outline; Sources; History.

**Observed, not a defect:** a failed turn between reservation and the
planner call leaves a `pending` row that blocks new turns for ten minutes
(`task_agent_turn_in_progress`) — the pre-existing ES rule; the thread shows
"This turn didn't complete." The thin-evidence walk in moderate mode paused
generically after `appraise` on a structural trigger (a non-evidence document
skipped) before reaching the gate — the ES structural floor applying to a
scoping walk, as designed.

**Third baseline — a thin-evidence structural question, no link** ("What could
reduce the number of long-term empty homes in coastal towns in England?",
rapid, Where England stated). The first two attempts ended `interrupted`: the
walk paused generically after `appraise` on the ES structural floor (a
non-evidence document skipped) and, on `continue`, crashed in the agent watch
(`expect_task_plan`) — fixed in `e063a69b` (a non-ES walk is routed past the
agent watch). The third attempt paused after `appraise`, was continued, and
reached the gate; **259 s** from `POST /runs` to the gate including the
structural pause. Ten sections (seven required, two proposed, Sources); 12
sources, 2 references; six of eight model-written sections open with a gap
claim ("No source found reports the current number or rate of long-term
empty homes specifically in coastal towns…") — the not-found content state
working as designed. Several sections carry `unspanned_assertion` flags
(prose asserting without an anchored claim); the roll-up flags them, and the
eval slice should read them.

**Three-baseline qualitative note** (read against the trust rules; not a
pass/fail gate). Rich corpus (NEET, twice): every empirical premise is a
cited chunk claim; the key assumption and the contested points are tier-4
reasoning labelled as such; both proposed sections were problem-specific
("NEET status among 16 to 24 year olds in England", "Participation pathways
and projected NEET trends"); the Sources section states the two databases,
the not-searched line and the grey-literature skew (18 grey / 14 academic).
Rebuild under the new Where (United Kingdom) produced a materially different
Trend section (UK rate 13.0 % in April–June 2026 versus England figures).
Thin corpus: gap claims dominate honestly, no hedging, no forecast; the
writer still proposed two sections, both restating absence — a template
refinement candidate (propose none when the corpus is thin). Compute: 389 s
and 453 s on the rich corpus, 259 s on the thin one — above the 3-to-4-minute
aim that assumed parallel writing (check 7: sequential writing is 183 s of
the NEET wall clock); the plan shows a coarse band and promises no number.

### Step-6 exit gate — final tree (2026-09-10)

| Command | Result | Notes |
|---|---:|---|
| `make verify` (full) | pass | backend 2802 passed (10:10); typecheck 335 files clean; lint clean; build OK; infra 46 passed; okf-validate 143/0; audit-paths, prompt-guard (16 modules), font-guard, `drift-check: OK`; frontend 715 tests / 82 files |
| `cd frontend && pnpm e2e` | pass | 15/15 (mock mode) |
| `make verify` (full, phase 8 gate, 2026-09-17; rerun green after the merge revert) | pass | backend 2805 passed (8:39; the first write of this row said 2806 — the suite collects 2805, corrected at the review stack); typecheck clean; lint clean; build OK; infra 46 passed; prompt-hash-guard 16 unchanged (two re-pinned); openapi-sync + drift-check OK; frontend 715 passed (82 files). e2e not rerun: no frontend change in phase 8 |

Every plan checkpoint is committed on `task/044-scoping-shell-baseline`; the
live check ran at the contract's pinned scope; this file is complete for the
review conversation (`task-cycle-review`, fresh conversation).

### Step-7 gates — review conversation (2026-09-17)

| Command | Result | Notes |
|---|---|---|
| `make verify` (full) on the entry tree, before any lane ran | pass | okf 143/0; backend 2805 passed (8:54); infra 46; audit-paths, prompt-guard 16, font-guard, `drift-check: OK`; frontend 715 tests / 82 files |
| `cd frontend && pnpm e2e` (entry tree; not rerun in phase 8) | pass | 15/15 |
| `make verify` (full) after the review fixes, first run | fail at `drift-check` | okf 148/0; backend **2826 passed** (8:58); infra 46; prompt-guard 16 unchanged (one re-pin); `drift-check` red because the lead narrowed a wire model after the API fixer's `make openapi-sync` — re-synced (`drift-check: OK`), then `make frontend-verify` 719 tests / 82 files, font-guard and audit-paths green individually |
| `make verify` (full) after the re-sync, one run | pass | okf 148/0; backend **2826 passed** (8:38); infra 46; audit-paths, prompt-guard 16 unchanged, font-guard, `drift-check: OK`; frontend **719 tests / 82 files**; build OK |
| `cd frontend && pnpm e2e` after the fixes | pass | 15/15 |
| `make prompt-guard` after the re-pin | pass | 16 unchanged; `task_agent_scoping_prompt.py` re-pinned once — code-only (`_fence_safe`) plus the dead `stop` value removed from the wire description; version string `task_agent_scoping_v2` unchanged, no behavioural instruction changed (038 R1 words-only ruling) |

### Phase 8 — latency levers before the review (2026-09-17, lead)

Added after step 6 at the owner's request ("Add them to 044 as phase 8 before
the review"). Owner rulings, from the latency reading of the three live
baselines (389 s, 453 s, 259 s; synthesise 51–76 % of wall clock, classify
42–86 s at 4 workers, ingest 47–89 s): "Go with options 2 and 5, targets 20
and 10"; classify and ingest widening "easy wins". Ruled out: waves, a writer
model change, fewer screen reps, turn cap or read window, stage overlap. The
writer-side levers (emit payload, judge concurrency, quote bound, reasoning)
are deferred to a synthesis optimisation task (`docs/deferred.md`
§ Synthesis optimisation), with the owner's concern that claims still
unsupported after the one repair stay in the prose.

| Change | Where | Pinned by |
|---|---|---|
| Classify 4 → 12 workers (the screen's width; provider-bound threads) | `assess/classify.py` | comment names the ruling |
| Ingest parse workers follow the cores: `max(4, min(8, cpu_count))` — 4 on the 2-vCPU staging task, 8 locally; fetch threads unchanged at 10 | `sourcing/ingest_full_text.py` | `test_fanout_determinism_workers_1_vs_4` still green |
| Acquisition target by depth: `{standard: 20, rapid: 10}` (was one constant, 25) | `runtime/scoping_plan.py` | `test_acquire_carries_the_depths_acquisition_target` |
| Rapid section list — **built, measured, reverted the same day** (owner: "Revert the merge, seven sections at both depths"): a five-section merge (`baseline_template_v2`, commit `6db623ce`) wrote no faster than seven (below); the template is back to `baseline_template_v1`, byte-identical to the phase 4 module, and both depths write the same eight sections | `baseline_prompt.py` unchanged from `3966b0fd` | `test_rapid_supplies_the_same_seven_sections_and_no_proposal_budget`, `test_rapid_writes_the_seven_sections_and_never_calls_the_proposer` |
| Proposed sections at standard only: the rapid synthesise directive carries no `section_budget`; synthesise makes no proposal call without one (the budget now travels in the directive, not the constant) | `scoping_plan.py`, `synthesise.py` | the two tests above |
| A depth change is a baseline input change (S4 sentence names "the depth") | `baseline_inputs_changed` | `test_baseline_inputs_changed_names_only_the_inputs_that_moved` |
| Task Agent prompt says depth shapes the baseline (reading set and proposed sections); option subs reworded (`task_agent_scoping_v2`) | `task_agent_scoping_prompt.py` | prompt pins; hash re-pinned |
| Specs applied with the ruling quoted: OS capability § Output structure, OS components § 11, plan-as-object § Thoroughness, log 2026-09-17; contract § Baseline + D7 + template bullet; rubric 7 and new 20; plan Phase 8 | docs | — |

**Measured (check-7 driver, `--depth` flag added; the NEET corpus, 53 appraised
documents, writing only, rolled back). The rapid rows are the five-section
merge as built at `6db623ce`, before the revert:**

| Run | Sections written | Wall (s) | Section walls (s) | Calls | Tokens |
|---|---|---:|---|---|---:|
| standard, 2026-09-09 (check 7, proposer stubbed) | 7 | 183.0 | slowest 36.4 | 28 | 273,250 |
| rapid, run 1 (machine under `make verify` load) | 5 | 168.1 | 39 · 47 · 39 · 25 · 14 | 18 (10 turns, 5 judge, 2 repair, 1 rejudge) | 187,524 |
| rapid, run 2 (idle machine) | 5 | 189.3 | 25 · 32 · 53 · 57 · 20 | 20 (11 turns, 5 judge, 2 repair, 2 rejudge) | 222,923 |
| standard, run 3 (same day) — **void**: the laptop slept with the lid closed (power log: 377 s + 32 s, on battery) mid-run; the monotonic timer under-reported 339 s against a 926 s log span | 7 | — | — | 33 (14 turns, 7 judge, 6 repair, 6 rejudge) | 294,711 |

**Where the writing time goes** (per call, from the log timelines; the
Sept 9 row is the live NEET baseline's Langfuse trace, 9 sections):

| Run | Write turns | Judge + re-judge | Repair | Read turns | Total |
|---|---:|---:|---:|---:|---:|
| live standard, 2026-09-09 (9 sections) | 110 s / 9 | 30 s / 10 | 5 s / 2 | 22 s / 9 | 180 s |
| rapid, run 2 (5 sections) | 97 s / 5 | 38 s / 7 | 29 s / 2 | 17 s / 6 | 182 s |

**Lead reading, flagged for the owner.** Two clean data points say the
five-section merge did **not** shorten the write on this corpus: 168 s and
189 s against the seven-section 183 s of 2026-09-09. The write turn is set
by output tokens and a merged section writes what two sections wrote (rapid
write turns averaged 19 s against 12 s for a standard section), so the merge
is a cost lever (tokens down 18–31 %) more than a latency one. The reliable
rapid savings are the acquisition target of 10 (ingest, screen and classify
shrink with the document count), no proposed sections (the live NEET
standard baseline wrote two, about 25 s each with their judge calls), and two
fewer judge exposures. The grounding judge on gpt-5.4-mini takes 4 to 12 s a
call on 5–13k prompt tokens and a repair 3 to 24 s; judge plus repair was
19 % of the Sept 9 write and 37 % of the rapid run 2 write — the second
bucket after the write turns, not the first. On this reading the owner
reverted the merge the same day ("if it makes not much of a difference, then
is there much of a point in having a difference in sections"): both depths
write the seven sections; rapid differs by its target of 10 and no proposed
sections. The writer-side lever that would make rapid faster is a length
bound per section (fewer claims, so fewer output tokens), deferred to the
synthesis optimisation task with the judge levers.

No full walk was re-run through the API in this phase (the dev API was down;
the walk-level effect of the target and the fan-out is arithmetic on the
phase 7 component times: about 190 s → 70 s before synthesis on the NEET
run). Cost of the three writes: about $2.5.

## Checks beyond the build

_(filled per phase)_

## End-to-end command

_(Phase 7)_

## Diff summary

_(filled per phase; flagged deviations listed here as they arise)_

### Flagged deviations (minor, resolved within the contract's vocabulary)

1. **`planning_turn_in_progress` → `task_agent_turn_in_progress`** (a 409
   error code, wire-visible). The contract names the path rename as the one
   non-additive change; the manifest (§ A.2, the deliverable-2 checklist per
   C13) lists this code, and A10 says the rename is complete or not done. The
   frontend is the only consumer. Renamed; recorded here next to the path.
2. **`runtime/agent_prompt.py` docstring keeps `planner_prompt.py` /
   `planner_v5`**: the module is hash-pinned and rubric 13 keeps every other
   hash unchanged, so the stale pointer stays until the next `agent_v` edit.
3. **`docs/tasks/_templates/contract.md:32` link** `capabilities/evidence-base/`
   → `evidence-search/`: a dead link since 038, fixed in the docs sweep.
4. **EB → ES in three `docs/knowledge/` files** (`index.md` line 117 and the
   two concept files it names, `synthesise-is-run-terminus.md` and
   `coverage-base-project-pool-wide.md`): `docs/knowledge/` content was
   outside the EB → ES scope in the manifest; the index line was swept by
   the tool and the two files were then swept by hand so the index and the
   titles agree. Filenames unchanged. Every "EB handoff" phrase is kept.
5. **Stored conversation title `"Planning"`** (`conversation_lifecycle.py`)
   and the History category `"Planning"` are kept: the screen never shows the
   stored title for the Task Agent (the vocabulary label does) and the
   category is ordinary English. The pane's aria label "Planning conversation"
   became "Task Agent conversation".

6. **The frontend URL token `?chat=planning` became `?chat=task_agent` with
   no alias** (review finding on `conversationState.ts`): a tab opened before
   the deploy that still carries `?chat=planning` shows "This chat couldn't be
   opened." until the user clicks the Task Agent. The token is transient view
   state, not a durable link, and the 038 rule (no redirect, no fallback code)
   applies to it as to the route. Recorded as a deliberate break.
12. **Phase 8 measurement contradicted one of its own levers** (see Phase 8):
    the rapid five-section merge saved no writing time on the NEET corpus in
    two clean runs (a third, same-day standard run is void: the machine
    slept). The owner reverted the merge the same day; seven sections at both
    depths.
13. **`frontend/src/views/workspace/PlanningPane.test.tsx` (329 lines) was
    deleted, not renamed** (review stack, verifier F5): its successor is
    `TaskAgentPane.test.tsx` (543 lines), which covers the same pane under the
    new name plus the gate thread; git pairs the two only as delete + add
    because more than half the file changed. No assertion was dropped —
    rubric 14's justification, recorded here.
14. **The Task Agent rename keeps two live symbols with the old word**
    (verifier F7): `PlannerTurnWire` and `PLANNER_SYSTEM_PROMPT` in
    `runtime/task_agent_prompt.py` (byte-identical, hash-pinned — C14 forbids
    the edit) and the alias `TaskAgentTurn = PlannerTurnWire` in
    `runtime/task_agent.py` that names it. The sweep test's allow-list covers
    the prompt module's symbols; this line names them.
15. **"Steps and check-ins" is the one plan section without an Edit action**
    (verifier F9): Evidence search parity — that section is compiled, not
    edited; `PlanDocument.test.tsx` asserts `sections − 1` Edit buttons.
17. **The Result's baseline band came off and its eyebrow reads "Baseline"**
    (owner ruling 2026-09-18, after seeing the live Result: remove "Baseline ·
    the situation these options would change · plan confirmed · … · built from
    plan version N" under the title, and replace the "scoping pass" eyebrow
    with "Baseline"). Supersedes the Result half of contract A17/C18 and the
    rubric-9 wording "Result shows the baseline with the band and run state":
    the walk's state and the "built from plan version N" mark live on the plan
    document (`useScopingPlanStart`, `SCOPING_CONFIRMED_LINE`), which keeps the
    same rule. The roll-up's `depth_label` ("scoping pass") stays on the wire
    for the later per-row surfaces the trust rules name; the Result no longer
    shows it. `baselineBand.ts` shrinks to `isBaselineArtefact`; the band
    tests go, the plan-document tests keep the walk-status regression.
16. **`scripts/rename_038.py` was refactored onto the new
    `scripts/rename_engine.py`** (verifier F12): outside the contract's In
    list; done because the 038 tool was the engine 044's sweep needed and
    phase-1 review finding 8 required the 038 behaviour carried as table
    fields. Covered by `tests/scripts/test_rename_044.py` and the 038 tests.

### Phase 1 review pass (`/code-review medium` on e4128528, 2026-09-09)

Eight findings, none against the schema change (the reviewer confirmed the
revision, its round-trip and the hand-edited historical tests). Dispositions:

| # | Finding | Disposition |
|---|---|---|
| 1 | `?chat=planning` URL token renamed with no alias | recorded (deviation 6) |
| 2 | Backend wire-visible strings still said `task_agent` (422 details on the conversations router, the `run_active`/`stale_turn` details, the stub replies) | **fixed** by hand → "Task Agent" |
| 3 | Sweep + disclosed hand edits do not reproduce the commit | **fixed in the tool** (phrase rules for string/comment spans, `TaskAgent` → `Task Agent` joiner, `ruff --fix` post-step); the residual hand-edit list is recorded below |
| 4 | Two regex edges (unanchored role-union protector; `[Pp]lanning turn` without the hyphen lookbehind) | **fixed in the tool** |
| 5 | Kept `"planner"` role literal protected only for `:` / `=` / `==` shapes | **fixed in the tool**; engine test added |
| 6 | Ordinary English swept: `planning delays` (a fixture), `fan-out planning` (a docstring) | **fixed** by hand; contexts added to the tool |
| 7 | Migration docstring claimed a `pg_constraint` pre-check that did not exist | **fixed**: the check is implemented (upgrade and downgrade), with a test |
| 8 | Engine extraction changed the 038 tool's scan headings, refusal text and `is_dir` sentinel | **fixed**: carried as table fields with the 038 values |

### Phase 1 hand-edit record (replay of the sweep against the commit)

Replayed from `5854676a` (the last commit with `planner.py`) with the fixed
tools (`fed7622f`): `git mv` list → `--apply` phases 3, 4, 5 → `ruff --fix` →
`make openapi-sync`, diffed against `e4128528`. Thirty-two files differ only
where the fixed tool now writes "Task Agent <noun>" in prose that the commit
had left as `task_agent <noun>` — the replay is the better text and those
strings were hand-fixed afterwards (`fed7622f` and the Phase 2 commit). The
edits the sweep does not reproduce, by design:

| File | Hand edit |
|---|---|
| `tests/core/test_migration_038.py` | catalog assertion moved to `c1a7f4e9b0d2`; deploy-window write `created_by="task_agent"` |
| `tests/core/test_migrations_029.py`, `test_migrations_028.py`, `test_planning_transcript_migration.py` | head-side reads on the new table and kind; `legacy_table` below the revision |
| `tests/api/test_api_conformance.py` | the `agent` leaked-name invariant strips the product words `task-agent`/`task_agent`/`taskagent` first |
| `infra/DEPLOYMENT.md` | the "Renamed in task 044" note (old name written by hand after the sweep mangled it) |
| `frontend/src/views/workspace/chat/conversationState.ts` | `const taskAgent` (a snake-case TS local) |
| `docs/knowledge/synthesise-is-run-terminus.md`, `coverage-base-project-pool-wide.md` | EB → ES (outside the manifest's 13-file list; deviation 4) |
| `docs/specs/capabilities/options-scoping/{components,capability}.md` | EB → ES inside fenced ASCII diagrams (the tool skips code fences) |
| `frontend/src/views/historyPresentation.{ts,test.ts}`, `chat/ChatMessages.{tsx,test.tsx}` | "The Task Agent replied", "Open Task Agent" |
| `tests/api/test_task_agent_router.py` | one signature wrapped for the line limit |
| `runtime/task_agent.py` | module docstring "``planner_v1`` planning call" |

### Phase 4.1 — the template-keyed section writer (2026-09-09, lead)

`synthesis_backend.py`'s `SECTION_SYSTEM_PROMPT` is now `SECTION_REPORT_PREAMBLE
+ SECTION_CORE`; `SECTION_PREAMBLES` maps `report` and `baseline`;
`_section_system_prompt(seed)` selects by the seed's `template` and fails
closed on an unknown one. The Evidence search assembly is byte-identical to
`synthesise_section_v10` before the split: sha256 `87126525…9a42` without and
`e38e6c1e…17fb` with the priority block, pinned by
`test_section_prompt_templates.py`. **Fact found while re-pinning:**
`scripts/prompt_hash_guard.py` pins files whose *name* contains "prompt", so
`synthesis_backend.py`'s inline section prompt was never hash-pinned; the
contract's "re-pinned once as a words-only diff" therefore has nothing to
re-pin, and the byte-identity test is the pin. Recorded as a knowledge
candidate and a deferred item (add the inline-prompt modules to the guard).

### Owner rulings taken during the build

- **2026-09-09 — the section writer's prompt becomes template-keyed** ("For
  the synthesise, let's go with option 2"): one writer, a shared core plus a
  preamble per output kind; the Evidence search preamble renders byte-identical
  messages (pinned by a test); the baseline preamble has its own version; the
  `synthesis_backend.py` hash is re-pinned once as a words-only diff. Contract
  § Constraints (prompts), rubric 13 and plan S3 / 4.1 amended with the quote.

## Review findings

Step 7 ran on 2026-09-17 in a fresh conversation (`task-cycle-review`), on
`git diff feat/options-scoping...HEAD` with the generated files, the task
docs and the three declared non-slice commits (`5854676a`, `b4b1e93b`,
`27a41a2b` — read once by the adjudicator, each is what it claims) excluded
from the reviewer lanes. `make verify` was green on the entry tree (backend
2805 · infra 46 · frontend 715 / 82 files · prompt-guard 16 unchanged ·
drift-check OK) and `pnpm e2e` 15/15 before any lane ran. The whole product
diff is Claude-written (no phase was marked `codex`), so Codex anchored the
adversarial pass over the whole diff and `/code-review medium` was the Claude
half of the pair.

**Lanes and cost.** Contract verifier (`contract-verifier`, Opus, 213K) ·
security (`agent-skills:security-auditor`, 174K) · Codex adversarial
(`codex-rescue`, read-only brief, job `task-mu5pgjaw-k2thzs`) ·
`/code-review medium` (474K) · live-trace content lane (lead, dev DB +
Langfuse — the build's scratchpad evidence was gone, so the traces and rows
were read at source) · `make okf-validate` (in the gate) · `/simplify` (see
below). Reasoning-class spend was 387K against the ≤250K guide; recorded,
not excused — a 31K-line Tier-4 diff with three review dimensions (rename ·
schema · gate) cost what it cost, and the two costliest lanes each found
things the others did not.

### Convergent findings (two or more lanes)

| Finding | Lanes | Disposition |
|---|---|---|
| A scoping task may start from a scoping task — `_write_task_links` never checked the source's capability | security S6 · Codex X4 | **fixed** (B1): 409 `link_source_capability` (registered in `app.py`'s closed conflict list, copy in `frontend/src/lib/errors.ts`, wire doc line); `test_a_scoping_task_cannot_start_from_another_scoping_task` |
| A Link names a source the reader cannot open — `links_for_tasks` joined `task.name` with no read grade (ADR 0037 d2 "grants no read") | security S3 · verifier F11 | **fixed** (B2): `readable_task_leg(user_id)` decides the name inside the existing join (no extra query); `source_task_name` null for an unreadable source; the plan document says "a task you can't open"; `test_a_reader_who_cannot_open_the_source_is_not_told_its_name` (ADR 0033 style) + PlanDocument test |
| `confirm-baseline` and the scoping `PATCH /plan` wrote a plan version without the task row lock — a walk could start from N while N+1 is minted; two concurrent confirms surfaced `uq_plan_task_version` as a 500 | security S4 · Codex X5 | **fixed** (B3): `for_update=True` on both; existing idempotency tests green (a thread-barrier test was judged not worth its cost) |
| "A baseline exists" was a status guess — any `aborted` walk counted (backend S4 sentence, frontend Confirm posting the task's latest artefact against a rebuild that aborted before writing) | `/code-review` C5 + C6 | **fixed** (B5, C-b): `RunOut.artefact_id` (scalar subquery, additive); `_baseline_built_from` joins `artefact` (`test_an_aborted_walk_that_wrote_nothing_is_not_a_baseline`); the frontend's `scopingWalkStatus` gains `baselineRun` (latest walk with an artefact), Confirm posts its artefact, the band's mark reads its plan version — regression "a rebuild that aborted with no artefact of its own" in planStart and baselineBand tests; mock runs carry `artefact_id` |
| The reasoning label is prompt-borne: no test asserts `tier_label`, no output invariant on the two reasoning sections | verifier F18 · Codex X8 · trace lane T1 | **fixed** (A6): `reasoning_label_missing` section flag + `reasoning_label_missing_present` roll-up flag (flag, not drop); the two section titles are derived from `BASELINE_SECTIONS` by focus text (the prompt module is hash-pinned, `# ponytail:`) and pinned by test; `tier_label == "tier_4_reasoning"` asserted on every reasoning claim; the visible-label question goes to the eval slice (deferred.md) |
| "A mixed turn answers first" rests on the sort prompt; the code only guarantees "never infers a decision" | verifier · Codex X12 | **recorded** (deferred.md; contract "No AI eval in this slice") |
| Repo-root `scripts/` (incl. the destructive operator script) are outside mypy | security S8 · verifier N2 | **recorded** (knowledge concept + deferred.md § Codebase health) |

### Unique to one lane

**Codex adversarial** (the heterogeneous reviewer; 1 blocker, 11 majors):
- X1 **blocker** — an attended `baseline_confirm` was silently treated as Continue whenever the IO could not pause (`NullIO`, the CLI): the walk ended `succeeded` with no human and the frontend read it as confirmed. **Fixed** (A2): at the gate an IO that cannot ask a human — no `pause` method, or `NullIO`, whose own `pause` returns Continue (the brief's premise was corrected by the fixer: `NullIO` *is* `_PauseCapable`) — records a `standing_default` decision and the auto-resolved flag before any pause event, the unattended shape, never a fabricated user Continue (`_can_ask_a_human`; `test_a_non_pausing_io_records_the_gate_instead_of_auto_confirming`). No production path used `NullIO` (the web dispatcher passes `ParkIO`, the CLI its own IO), so this closed a latent seam rather than a live defect.
- X2 — an unattended plan could declare `baseline_confirm: stop`, aborting at the gate against D11/A9. **Fixed** (A3): `ScopingSteerPointDefault.action` is `Literal["proceed_flag"]` (the Out model too); the dead `stop` branch in `_resolve_baseline_gate_unattended` deleted; the scoping prompt's wire description no longer offers `stop` (words-only re-pin); `test_an_unattended_plan_cannot_declare_a_hard_stop_at_the_gate`.
- X3 — the gate's two options could be bypassed with the generic `abort` response or the universal `continue`/`abort` option ids, marking the plan `abandoned`. **Fixed** (B9): at a baseline-gate pause `kind == "abort"` and any option id outside the stored two are refused (`_offered_option(allow_floor=False)`); `test_the_gate_refuses_everything_but_its_own_two_options`.
- X6 — a change-plan-with-text decision was lost if the planner call then crashed (retry saw no gate and completed a plain reply). **Fixed** (B7): a complete `TaskAgentTurnOut` projection (`kind="decision"`, the decision, `CHANGE_REPLY`) is persisted on the reserved row while it stays `pending`, before the planner runs; a retry reads it back (`_Reserved.retried`) — `test_a_failure_after_the_decision_leaves_it_durable_and_the_retry_replans` now asserts the decision survives (it previously asserted `kind is None`, which was the bug).
- X7 — the widened synthesis grammar let an ES steering delta select `template: "baseline"`, silencing the report passes on an Evidence search walk. **Fixed** (A4): `template` refused in a steering delta at the validation site with a plain sentence (compile-only key; `section_budget` was steerable before 044 and stays); `test_a_synthesis_delta_cannot_switch_the_report_template`.
- X9 — inherited coverage was read latest-per-scope, not per pinned walk. **Fixed** (A7): `search_coverage_record` joined to `runs` on `acquired_by_run_id` and filtered by the pinned `capability_run_id`; `""` when none matches; `test_coverage_is_the_pinned_walks_not_the_scopes_latest`.
- X10 — inherit fell back to the source's latest approved plan when the pinned plan row was missing. **Fixed** (A8): fail closed — `{}` and `inherit.plan_row_missing` logged, the fallback query deleted; `test_a_missing_pinned_plan_row_inherits_nothing`. (0 of 25 walks in the dev DB lack a `plan_id`, so the fallback only ever fired on a data fault.)
- X11 — no aggregate bound on linked context (60,000 chars per link per turn). **Fixed** (B10): `TaskCreate.from_task_ids` `max_length=3` at the stack, raised to **10** on the owner's ruling of 2026-09-18 (an accident guard, not a design limit — the context window is not the constraint and the prefix is prompt-cached); deferred.md notes the ceiling; `test_a_create_naming_more_than_ten_sources_is_refused`.
- Could not break: ES composition and `planner_v11` unchanged (R100 move), the ES section-writer assembly byte-identical, fences while running/paused, the chat-versus-card race lock, `POST /tasks` one transaction, `record_cap` 1..200 per backend, classify order under 12 workers, `cpu_count() is None`, the operator script's FK order, both downgrade refusals, the frontend nullable-plan consumers, no weakened tests.

**`/code-review medium`** (10):
- C1 — the gate paused over a **failed** synthesise (no `successful_runs["synthesise"]` guard, unlike the two ES points). **Fixed** (A1): the same degradation to a generic pause; `test_the_gate_does_not_pause_over_a_failed_synthesise` (synthesise raises → walk `failed`, no card).
- C2 — gate answers put the raw `appraisal_score` on the wire and never the label. **Fixed** (B4): stored raw; `apply_appraisal_labels` at the read boundary on the fresh turn, the transcript projection and the replay path; `test_a_gate_answer_carries_the_appraisal_label_not_the_score` (verified red without the fix).
- C3 — suggestion chips gated on `!runActive`, so the gate's quick replies never rendered while paused. **Fixed** (C-a): `!composerFenced`; TaskAgentPane test "renders an ask-back turn's suggestions as chips at the gate".
- C4 — the Sources section never stated the origin restriction (`country_group` read as `str`, stored as a dict). **Fixed** (A5): `country_group` read as a Mapping (`label`); `test_baseline_sources_block_states_the_origin_restriction` seeds the plan through the real `build_scoping_plan` and asserts ", limited to sources from OECD members".
- C7 — a question racing a card click became a 500. **Fixed** (B6): `answer_at_gate` returns `None` and the turn completes with `ALREADY_ANSWERED_REPLY`, `kind="reply"`, walk still paused; `test_a_question_that_loses_the_race_to_the_card_is_not_a_500`.
- C8 dead type bridge · C9 the disabled Starts-from picker fetched and polled the whole task list · C10 dead `!baseline` guard. **Fixed** (C-c, C-d, C-e).

**Security lane** (5 minors, 4 notes; no blocker):
- S1 — the inherit fence was not escape-safe (`</report>` inside a report body closes the fence). **Fixed** (lead): `_fence_safe` in `task_agent_scoping_prompt.py::render_linked_context` turns every `</` in the fenced title, plan JSON, report and coverage into `<\/` — inert in Markdown and a legal JSON escape, so the plan stays parseable; `test_fenced_data_cannot_close_its_own_fence`. Code-only diff in a hash-pinned module, re-pinned as a words-only change together with the dead `stop` value's removal from the wire description (below); no version bump — no behavioural instruction changed.
- S2 — the sort's `carried_text` (model output) became the planner's message unvalidated. **Fixed** (B8): verbatim-substring check, else the whole utterance.
- S5 per-run fan-out has no cross-run bound · S7 422 bodies echo the pydantic error (pre-existing pattern) · S9 the rename downgrade rewrites post-upgrade rows (lossless). **Recorded** (deferred.md / this file).
- Clean bill: `POST /tasks` (closed `capability`, links refused on an ES create, read grade + same-project + server-side run pin in one transaction, cross-org link unconstructible); gate turns owner-only; the decision barrier is `SELECT … FOR UPDATE` plus the undecided check in one transaction; SSE grade unchanged; no secret, token or raw trace in the diff or the task docs.

**Contract verifier** (rubric 1–10, 12, 13, 16, 17, 18, 20 pass; 11 partial → resolved; 14 pass with one unrecorded deletion → recorded; 15, 19 this phase):
- F1 ADR "ten validate sites" is fourteen · F2 contract § Plan object still said "depth does not change them" · F4 the acquisition target is per backend and three documents read as totals · F5 `PlanningPane.test.tsx` deletion unrecorded · F6 `PlanUpdatedFrame.plan` nullable undeclared · F7 two kept `Planner*` symbols · F9 one plan section without Edit · F12 038 tool refactor beyond the In list · F13 lowercase `task_agent <noun>` prose residue · F14 a new test with a retired name · F15 superseded "25 per backend" without a pointer · F16 the constraint list read as exhaustive · F17 two constraints are drop+recreate. **All folded**: ADR 0037 (F1, F17), contract (F2), this file (F5, F6, F7, F9, F12, F15, F16, deviations 13–16), code (F8 the AST seam now guards `ScopingPlan.model_validate` too — `test_capability_registry.py`; F13 the eight runtime lines by the lead, the six API lines by the API fixer; F14 renamed). **F4 is the owner's decision item** (see § Owner decision items).
- F3 gate-sort latency unmeasured → measured by the trace lane (below). F10 the D8 warning and the kind question are pinned as prompt strings only → the live check (c) is the behavioural evidence; eval slice.

**Live-trace content lane** (lead; dev DB rows + Langfuse session of the NEET task, 22 traces):
- Gate sort: three `agent:gate_sort` spans, 0.82 / 1.13 / 1.35 s, kinds correct (`question`; `decision change_plan` carrying "Change Where to the whole United Kingdom, not just England."; `decision confirm_plan`), no `unsure`. **Known unverified item 3 closed.**
- Inherit: turn 1 and turn 3 prompts carry the linked block as message [1] (user role), 21,321 chars, **byte-identical** (`sha256 9a1f6db1…`) across turns; turn 1 tagged England `assumed` and asked who should change — rubric 4 holds live, not only by test.
- Baselines: all five `synthesis_result` rows are `template: baseline`, 10 sections (7 required + 2 proposed after "What is contested" + Sources), claim types chunk / reasoning / gap only (A7 holds on every live artefact). "Key assumption" opens "Reasoning: …"; "What is contested" carries its reasoning at claim grain (T1, above). The judge's `unspanned_assertions` (3, 3, 3, 0, 8) are absence statements written as prose without a gap claim — correct judge behaviour, a writer habit on thin corpora; eval-slice material.
- The gate answer traces as `run:chat_v1:<id>` (31 s) — the lifted core still carries `component="chat_v1"` (5.3 said 5.4 may relabel; it did not). Recorded, harmless.
- Seven `evidence_scope` baseline rows for seven NEET plan versions, two of which ran (T3) — by design (C3), noted in deferred.md.
- Historical rows show the pre-fix states the live check reported (the card printing `Depth: standard`; two `interrupted` empty-homes walks that crashed at the gate boundary after a full synthesise) — consistent with the fixes `e063a69b` recorded.

### Fake-done check on the phase-7 fixes
No test relaxed, skipped or deleted (verifier: zero `skip`/`xfail`/`todo` in the diff; one true deletion, recorded as deviation 13). Every code fix above lands with a test that fails without it; the post-fix gate is in § Commands run.

### `/simplify`
`/code-review medium` ran the reuse · simplification · efficiency · altitude angles (C8, C9, C10 are its cleanup findings) and their fixes are applied; a separate same-family `/simplify` pass would read the same diff a third time — recorded as satisfied, not re-run (task-cycle-review § Step 7).

### Owner decision items (from the stack; nothing applied without a ruling)
1. **Acquisition target wording** (verifier F4): `search.record_cap` applies **per backend**, so standard acquires up to 20 from Overton **and** 20 from OpenAlex (about 40 documents; the live check acquired 50 at 25). The contract § Baseline, the OS capability spec § Output structure, plan-as-object § Thoroughness and the spec log of 2026-09-17 say "20 documents" / "10 documents". Either (a) keep the code and add "per backend" to the four documents, or (b) halve the per-backend cap so the totals read as written. The lead recommends (a): the measured baselines and the phase-8 arithmetic are per-backend numbers. **Ruled 2026-09-18 (owner: "Add per backend to the docs"): (a) — the four documents amended, code unchanged.**
2. **Linked sources capped per create** (Codex X11) — a bound the contract did not name. **Ruled 2026-09-18:** ten, as an accident guard; inline inherit stays for task 1, retrieval-shaped inherit recorded as the path for many links (deferred.md).
3. **Inherit fence** (security S1) — accepted as defence in depth for this slice; escape-neutralising the fenced body is a one-line change if the owner wants it now rather than at task 2.

## Rubric status

| # | Holds | Evidence |
|---|---|---|
| 1 | ✅ | contract/tasks.py `TaskCreate.capability`, no `capability` on `TaskUpdate` (immutable by construction); `TaskListRow.test.tsx` no depth; `AppShell.test.tsx` header |
| 2 | ✅ | `test_rename_044_sweep.py` (code, docs, schema, 404, `planner_v11`); one commit `e4128528` before feature code; EB→ES grep reproduced (four kept "EB handoff" hits); deviations 14 (kept symbols) |
| 3 | ✅ | `NewTaskView.test.tsx` (no depth/job control; same-project ES tasks only; one request); `test_task_links.py` task count 0 after a 409; + B1 source capability |
| 4 | ✅ | `test_migration_044_slice.py` link constraints; `test_task_links.py` (finished walk, flagged not deleted, no read widening; + B2 unreadable source unnamed); `test_inherit.py` (plan + coverage, no markers, byte-stable; + A7 pinned coverage, A8 fail-closed plan); live: block byte-identical across turns |
| 5 | ✅ | `test_scoping_plan.py` (depth, deep, Where default, kinds, `checked_at`, Your context, cross-capability rejection, moderate default, `source_turn_index`, language); `test_capability_registry.py` AST seam (both models after B11); `PlanDocument.test.tsx` Edit actions (deviation 15) |
| 6 | ✅ | `test_task_agent_scoping_prompt.py` (labels, no primary), `test_task_agent_scoping.py` (no recommendation); D8 warning + kind question: prompt pin + live check (c) (verifier F10) |
| 7 | ✅ | `test_scoping_compose.py` (chain, 7+Sources at both depths, proposals 2 · 0); `test_synthesise_baseline.py` (order, gap state, claim types, no ES passes, Sources block + A5 restriction clause, `scoping pass`, + A6 label flag / `tier_label`); check 7 ships nothing; compute 389 / 453 / 259 s |
| 8 | ✅ | `test_baseline_gate.py` (lattice, modes, unattended, ES generic pause, label; + A1 failed synthesise, A2 non-pausing IO, A3 `proceed_flag` only); `test_baseline_gate_checkin.py` (confirm, change_plan, second answer refused, plan editable; + B9 no `abort` floor); `test_task_agent_gate_turns.py` (answer, race, change+replan, rebuild, confirm both versions, ask-back, fences; + B4 labels, B6 race reply, B7 durable decision, B8 carried text) |
| 9 | ✅ | `ArtefactView.baseline.test.tsx` (headed "Baseline", no band — owner ruling 2026-09-18, deviation 17; the walk-status rule lives in `planStart.test.ts`); Sources/Share unchanged (empty diff); History hook rename only |
| 10 | ✅ | `b5e1d7a4c026` exactly the named objects (deviation list completed, F16); `a7d3f1c8e2b5` rewrites + reverses; round-trips, refusals (task or `capability_run`), operator FK order tested |
| 11 | ✅ | `make verify` green at entry and after fixes (§ Commands run); deterministic list located item by item (verifier); live check (a)–(g) with times; gate-sort latency 0.82–1.35 s (trace lane) |
| 12 | ✅ | structural JSON comparison: four renamed schemas + one path removed, `/plan/confirm-baseline` added; nullable widenings declared (deviation 7 incl. `PlanUpdatedFrame.plan`); + `RunOut.artefact_id`, `source_task_name` nullable, `from_task_ids` max 3 — additive, via `make openapi-sync`, `drift-check: OK` |
| 13 | ✅ | three new keys; `planner_prompt.py` → `task_agent_prompt.py` hash unchanged (R100); `task_agent_scoping_v2` re-pinned; `baseline_prompt.py` byte-identical to `3966b0fd`; `synthesis_backend.py` unpinned by the name-based guard, byte-identity test is the pin; ES compose comment-only diff |
| 14 | ✅ | zero skip/xfail/todo added; one true deletion justified (deviation 13); phase-7 fixes add tests only |
| 15 | ✅ | this file: three-baseline note, compute times, deviations 1–16, review lanes and dispositions |
| 16 | ✅ | deferred.md § task 044 seams (seven required seams + the review-stack seams) · § Synthesis optimisation · § Codebase health (scripts typecheck) |
| 17 | ✅ | seven spec changes logged (2026-09-09 ×3, 2026-09-17); `docs/specs/sources/` diff empty |
| 18 | ✅ | ADR 0037 Accepted 2026-09-09; rollback verified against the code (list default, `--apply`, ES-link refusal, FK order, both refusals); counts corrected at the stack (F1, F17) |
| 19 | ✅ | contract verifier · `/code-review medium` · security lane · adversarial at contract, plan and code (Codex) · `/simplify` (satisfied by the cleanup angles, recorded) · human deep review = step 9 |
| 20 | ✅ | `test_scoping_compose.py` (20 · 10 `record_cap`; rapid no `section_budget`); `test_synthesise_baseline.py` rapid never calls the proposer; depth in `baseline_inputs_changed`; classify 12; ingest `max(4, min(8, cpu_count or 4))`; `task_agent_scoping_v2`; `baseline_template_v1` |

## Intent & assumptions

- The live check was driven through the API (the Chrome extension was not
  connected); screenshots came from headless Playwright against the live
  frontend afterwards. The behaviour checked is the contract's (a)–(g); the
  screen surfaces were verified by screenshot rather than by hand-driving.
- The seeded NEET task had no owner and no project in the dev DB; two dev-DB
  rows (owner, project membership) made it linkable. Dev-only data.
- `BASELINE_TIME_BAND` stays the coarse "A few minutes · then a check-in";
  the measured 4.3 to 7.5 minutes are recorded here, not promised on screen.

## Known unverified items

- Unattended mode's recorded standing-default decision at `baseline_confirm`
  is pinned by tests, not driven live (the live plans were moderate).
- The chat-versus-card decision race is pinned by the barrier test only.
- ~~Gate-sort latency is bounded by the whole confirm turn (2.3 s); the
  Langfuse span `agent:gate_sort` gives the exact number when read.~~ **Read at
  the review stack:** 0.82 s (question), 1.13 s (change_plan), 1.35 s
  (confirm_plan) on gpt-5.4-mini — the three live gate turns' `agent:gate_sort`
  spans.
- The frontend's live thread at the gate was verified by screenshot of the
  transcript after the fact, not by typing into the composer in a browser.

## Public safety

Contract, plan, rubric, ADR and this file carry no secrets. Screenshots
show the NEET question (the design reference), plan fields and baseline
prose built from published sources; they are public-safe once the source
quotes are checked against the sanitized-fixtures policy (they cite ONS and
published reports by title). Raw turn payloads, the dev token and the API log
stay in the local scratchpad and are not committed.

## Review handoff (step-7/8 inputs)

- **Knowledge candidates** (raw; step 8 authors `docs/knowledge/` from these
  against the final code):
  - The 038 rename engine's separator/casing logic only handled equal-length
    word rules; the first one-to-two expansion (`planner` → `task_agent`)
    produced `TASKAGENT_MODEL` and `_ModerateStubTask_Agent` until the joiner
    was derived from the identifier's own inter-word separator (a leading
    underscore is not one). `rename_engine.infer_separator`.
  - A gitignore line without its `.dockerignore` mirror turns `make verify`
    red at the next build-open baseline (infra image-hygiene test); the
    failure surfaces one commit later than its cause.
  - A table-driven identifier sweep renames stored enum literals as happily
    as code names: `planner-proposed` (a `country_group.authorship` value in
    plan payloads) went through the 044 sweep and surfaced only as an enum
    change in the OpenAPI diff. Review every changed quoted literal in the
    sweep diff against the migration's rewrite list before the gate.
  - A killed concurrent test run can leave an `idle in transaction` Postgres
    backend holding locks; the next suite on the shared test DB hangs on it
    for hours (5.2 lost 2h16m). Check `pg_stat_activity` before blaming the
    code.
  - Writing the synthesis directive onto the shared `evidence_scope` row
    before a run takes a Postgres row lock that serialises concurrent
    synthesise runs perfectly (check 7's first parallel run summed its arms:
    328 s); `synthesise_scope` reads the directive from its context, not the
    row.
  - The slice revision's downgrade refusal (A5) turns every migration
    round-trip test red behind any test that commits an `options_scoping`
    task and leaves it; shared-Postgres suites need the scoping fixtures
    cleaned up in the test that made them.
  - `capability_registry` cannot be imported from `task_plan.py` (registry →
    steering → task_plan); per-capability validators therefore hold their own
    steer-point sets, pinned equal to the registry's by test.
  - `make -C backend typecheck` runs `mypy src tests` from `backend/`, so
    repo-root `scripts/*.py` (now including a destructive operator script)
    is never typechecked.
  - `scripts/prompt_hash_guard.py` pins by filename (`*prompt*`), so the two
    inline prompt carriers (`synthesis_backend.py`, `finding_vetter.py`) are
    outside the guard; a prompt edit there is invisible to `make prompt-guard`.
  - Hash-pinned prompt modules must be excluded from any identifier sweep
    whole, not just their string literals: a docstring rename is a hash
    change (rubric "every other hash unchanged").

## Deferred work

`docs/deferred.md` § "Options scoping shell and baseline (task 044 seams)":
per-field turn provenance (resolved at version grain) · Search further ·
inherited document rows · `task_link.option_id` · scoping deep · the later
latency levers (check 7's reading) · the Task Agent as the ES control surface
· rebuild only the touched sections · the language evidence restriction ·
the ES prompt's unattended default · the name-based prompt-hash guard · the
`?chat=planning` token · the `agent_prompt.py` docstring. Spec log lines in
`docs/specs/log.md` (2026-09-09). Phase 8 adds `docs/deferred.md`
§ Synthesis optimisation (emit payload, judge concurrency, quote bound,
reasoning on the writer, unsupported claims kept in prose) and the log line
of 2026-09-17.
