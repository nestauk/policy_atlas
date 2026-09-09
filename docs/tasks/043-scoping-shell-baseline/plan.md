# Plan: 043-scoping-shell-baseline

Deliverables 1–10, decisions D1–D13, the second-round amendments, the
adversarial folds A1–A18 and C1–C18, and every term are defined in
[contract.md](contract.md). The rename inventory is
[rename-manifest.md](rename-manifest.md). This plan cites them and adds
nothing to scope.

> **Status:** drafted 2026-09-09 · lead. Plan-stage adversarial review
> (read-only): _next_ · **Plan approved (before implementation):** _pending ·
> owner_.

Executor marks per AGENTS.md § Agent-side model routing; every `lead` mark
carries its reason. **Owner ruling 2026-09-04 (038) stands:** judgment-bearing
phases go to `deep-reasoner`, not `codex`; the family flip happens at step 7
when Codex reviews the diff. No phase is marked `codex`.

**Verify gates.** Full `make verify` at Phase 0 (build-open baseline), Phase 1
(the rename migration — schema class), Phase 2 (the slice migration — schema
class), Phase 5 (the gate touches the runner and the fence) and Phase 7
(step-6 exit). Phases 3, 4 and 6 close on `make verify-fast` plus
`make frontend-verify` where the frontend changed, and `pnpm e2e` where a
route or the thread changed. **One green commit per phase.** Phase 1 gets its
own review pass before any feature code lands (contract deliverable 2).

## Decisions fixed here (lead seam design)

S1. **Capability registry** (C9, A2, A18d). `runtime/capability_registry.py`
holds one `CapabilitySpec` per capability: `plan_model` (`TaskPlan` /
`ScopingPlan`), `compose` (the chain builder), `task_agent_prompt` (the
prompt module), `steer_points` (the lattice names valid for its plans) and
`lattice` (name → `PausePoint`). Three functions replace the scattered calls:
`validate_plan(capability, payload)`, `compose_plan(capability, plan)`,
`lattice_for(capability)`. The **eight** `TaskPlan.model_validate` sites go
through it (`runtime/agent.py:653`, `continuation_state.py:153`,
`steering.py:1611`, `api/routers/runs.py:73,156`, `api/routers/sse.py:534`,
`api/routers/planning.py:281,617,804,832`; the contract counted six readers,
the map found eight sites). `steering.pause_points`, `lattice_name_for` and
`lattice_policy` take the capability's lattice, so `baseline_confirm` never
names an ES boundary. `SteerPointDefault`'s validator checks against the
capability's `steer_points`. `_open_capability_run` (`runner.py:5035`) writes
the task's capability. ES behaviour is pinned by the existing steering and
plan tests, which must pass unchanged.

S2. **Scoping plan and chain.** `runtime/scoping_plan.py`: `ScopingPlan`
(`extra="forbid"`, the fields of contract § Plan object; `depth ∈ rapid |
standard`; `constraints[].kind ∈ requirement | preference |
evidence_restriction`; `your_context[]` with `turn_index`; `steering_mode`
default `moderate`; `steer_point_defaults` validated against the scoping
steer points) and `compose_scoping(plan) -> ComposedChain` producing exactly
`acquire → screen_abstract → classify → appraise → ingest_full_text →
synthesise`. Directive deltas: acquire carries the evidence restriction as
`ScopeConstraints` (country group, years; a language restriction is stored and
shown as *not yet applied at retrieval* — C8) and the **baseline acquisition
target** (a constant in `scoping_plan.py`; if the acquire directive grammar
has no per-backend cap key, one is added under the fail-closed grammar and
tested); screen carries target unit and Where in the intent context;
synthesise carries `{"synthesis": {"template": "baseline", "proposed_max":
2}}`. `synthesis_tools._DIRECTIVE_KEYS` is fail-closed and gains `template`
and `proposed_max`. `COMPONENT_REGISTRY`, `compile`, `build_graph` and
`_run_synthesise` need no change (the harness dispatches one component at a
time and passes the whole scope context to synthesise).

S3. **Baseline mode in synthesise** (A7, C7). The supplied-sections path at
`synthesise_scope` (`:5431`, `directive.sections is not None`) already
bypasses proposal. Baseline mode (`template == "baseline"`): sections =
`baseline_prompt.BASELINE_SECTIONS` (eight `SectionSpec`s in the ruled order)
+ up to `proposed_max` proposals from `propose_sections`, validated by
`_validate_sections` with `section_budget=proposed_max` and a baseline
forbidden-title list (no duplicate of a required title, no "conclusions",
no "key findings"), inserted after "what is contested". `SectionSpec` gains
`instruction: str | None` and `turn_cap: int | None`; `as_seed()` carries the
instruction; the `run_section_loop` call at `:5601` passes
`turn_cap=section.turn_cap or SECTION_TURN_CAP`; `generation_budget_max()`
counts the per-section caps. One flag guards the three ES-only passes at
`:5499` (Conclusions), `:5718` (key findings), `:5781` (case studies); the
roll-up already tolerates their absence. **Not-found is the existing gap
claim**: a section with no support is written as gap claims, which the
template instructs and which `available_claim_types_for_substrate` already
admits; no new claim type. The baseline's claim set is `{chunk, reasoning,
gap}` by substrate absence — nothing to code. The roll-up's provenance gains
`depth_label: "scoping pass"`. Sequential writing (C6). Section progress
events already stream (`ProgressEmitter` `artefact.section_started` /
`section_completed`), so "shown as they finish" is the skeleton carrying the
eight titles — Phase 4 takes it if the Result view already renders progress
events; otherwise it stays deferred.

S4. **The gate** (A2, A9, A13, C1, C3, C5). `baseline_confirm =
PausePoint("after_component", "synthesise")` in the **scoping** lattice only;
policy `always` in frequent, moderate and minimal. The after-boundary loop
already visits the last step, so no runner loop change. Options at the pause
(`_pause_options_and_bundle`): `confirm_plan` (response `continue` → the walk
finishes `succeeded`; the decision payload records `plan_version` and the
baseline artefact version) and `change_plan` (a **new end-walk disposition**:
like `_persist_abort` it writes the decision, sets `capability_run.status =
"aborted"` and `run.finished{status: aborted}`, but it **does not** flip the
plan to `abandoned` — the plan stays `approved` and editable, because
`_load_editable_plan` reads only `approved` rows; response `change_plan`).
The card render is deterministic: the baseline's key-assumption block prose
and the plan's Settings. **Unattended:** `_resolve_unattended_boundary` writes
the decision through the existing `_emit_standing_proceed_decision` shape
(`decided_by="standing_default"`, `response="confirm"`, flagged) and
continues; choosing unattended in the Task Agent writes the standing default
for `baseline_confirm` into `steer_point_defaults`. **After a change:** the
plan document offers two start actions — `Rebuild baseline` (`POST /runs` as
today, a new walk under the new plan version; its intent record's `plan_id`
and `plan.evidence_scope_id` point at the new version) and `Confirm plan and
build longlist` (a new route or a run-less decision: writes a standalone
steering decision `baseline_confirm` with `response="continue"` naming the
new plan version and the existing baseline artefact version; in this slice
it ends there). The Task Agent states whether the change touched the
baseline's inputs (a deterministic diff of the six input fields between plan
versions, rendered in the reply).

S5. **Task Agent turn at a pause** (A4, A6, A12, C2, C5). Fence (1) in
`planning.py:330-341` becomes: 409 `run_active` while `running`; while
`paused`, the turn is admitted and **sorted** before any planner call. The
sort is `AgentBackend.sort_gate_turn(utterance, offered_options) ->
GateSortWire{kind: "question" | "decision" | "unsure", option_id: str |
None, carried_text: str | None}` with prompt `gate_sort_v1` in
`runtime/gate_sort_prompt.py` (lead-authored, mini-class model, constrained
output; `unsure` asks back). `question` → the **answer core** (S6) over the
paused walk's pinned scope. `decision` → `answer_check_in` in the same
request, bound to `capability_run_id`, `check_in_id` and `plan_version`,
under the task lock (the existing `_pending_pause` latest-pause check gives
409 `already_answered` to the loser of a race); `change_plan` with
`carried_text` ends the walk and then applies the text as the next ordinary
Task Agent turn in the same request (the fence has lifted, no walk is
active). A question that also carries a decision is answered, and the reply
offers the decision as an option to click — never applied. The approving
branch (fence 2, `:531-535`) and `patch_plan` (fence 3, `:862-875`) keep
`("running", "paused")`.

S6. **Answer core and turn projection** (C2). Lift `chat_turns.py:824-961`
into `api/answer_core.py::answer_over_scope(engine, *, task_id, scope,
entry_artefact_id, window, question, backends…, trace_run_id, on_delta=None,
check_cancelled=None) -> (prose, AnswerPayload)`; `run_chat_turn` calls it
and keeps its reservation, locks, `chat_turn` row and fences. `chat_scope`
gains `resolve_run_components(engine, task_id, capability_run_id=…)` so a
**paused** walk's scope resolves (the existing function keeps its
`succeeded|degraded` filter). A shared `AnswerPayloadOut` (the `ChatTurnOut`
citation fields) is used by both. `TaskAgentTurnOut` /
`TaskAgentTranscriptTurnOut` become a discriminated union on `kind ∈ reply |
answer | decision`; the stored `response` re-validation at `planning.py:842`
accepts all three.

S7. **Create in one transaction** (C10, C11, C12). `TaskCreate` gains
`capability` (default `evidence_search`), `project_ids: list[UUID] = []`,
`from_task_ids: list[UUID] = []`. The project-assignment branch of
`update_task` (`tasks.py:308-399`: dedupe, `assignable_project`, multi-org
409, visibility derivation, membership rewrite) is extracted to
`assign_projects(conn, task_id, project_ids, user)` and called from both
routes. `task_link` rows are written in the same transaction: each source
must share at least one project with the new task (409
`link_project_mismatch`), be readable by the user, and have a latest
`succeeded|degraded` walk (its `capability_run_id` is pinned; 409
`link_source_unfinished` otherwise). The read model marks a link whose tasks
no longer share a project as `flagged`. `useCreateTask` becomes two requests.

S8. **Inherit context** (D4). `runtime/inherit.py::linked_context(conn,
task_id) -> list[LinkedTaskContext]`, one per `task_link`: the source plan
payload (whole), the report body as markdown built from the pinned walk's
artefact blocks (section title + block prose, citation markers stripped by
the same pattern the frontend's `artefactMarkdown` uses, the references
section dropped), and the coverage statement from the pinned walk's coverage
record. The scoping Task Agent prompt assembly places each as one fenced
block after the system instructions and before the transcript, identical
bytes every turn.

S9. **Rename phase** (deliverable 2, A10, A11, C13, C14). `scripts/rename_043.py`
reuses the 038 engine (`scripts/rename_038.py`: identifier splitting,
span-safe editing, ledger, `--scan` / `--apply`) with a 043 rule table and
literal list; if the engine reads its tables from module constants, the
smallest refactor that lets a second script supply them is made, and no
second engine is written. Rules (compound before bare): `planning_transcript`
→ `task_agent_transcript`; `planner_state` → `task_agent_state`; `ptr`
constraint infix → `tat`; `planning` (conversation-kind sense: `planning_turn`,
`PlanningTurn*`, `PlanningPane`, `planning_conversation`, `/planning-turns`,
`planning_turn_in_progress`) → `task_agent…`; `planner` (`PlannerBackend`,
`OpenAIPlannerBackend`, `StubPlannerBackend`, `PLANNER_MODEL`,
`planner_prompt`, `planner.py`, `POLICY_ATLAS_PLANNER_MODEL`, the wire role
literal) → `task_agent…`. Never mapped: `plan`, `TaskPlan`, `PlanDraft`,
`PlanOut`, `plan_id`, `PATCH /plan`, `PLANNER_PROMPT_VERSION`'s **value**
`planner_v11`, `eb_iof_base_v1`, `eb_icf_base_v1`, `evidence_base_coverage`.
`planner_prompt.py` moves **byte-identical** to `task_agent_prompt.py`
(`git mv`; the pin's path updates, hash unchanged). Stored values rewritten
in the migration and reversed on downgrade: `conversation.kind` `planning` →
`task_agent`; `plan.created_by` `planner` → `task_agent`. The migration
renames the table, the column and every constraint and index in the
manifest. The EB → ES sweep is a separate `--docs` mode over the manifest's
file list, markdown-aware, skipping quoted owner rulings; excluded paths per
the manifest. The rename manifest is the checklist for the sweep test.

S10. **The slice migration** (one revision after Phase 1's). `task.capability
TEXT NOT NULL DEFAULT 'evidence_search'` + `ck_task_capability`; widen
`ck_capr_capability`; `task_link` (S7 columns; composite FK `(source_task_id)`
and `(target_task_id)` to `task`; `(source_capability_run_id,
source_task_id)` → `capability_run(capability_run_id, task_id)` — the
existing `uq_capr_id_task` is the target; unique `(source_task_id,
target_task_id)`; check source ≠ target); `evidence_scope.purpose TEXT NULL`
+ check on the four values; `evidence_scope.plan_id UUID NULL` with a
composite FK `(plan_id, task_id)` → `plan(plan_id, task_id)`, which needs a
new `uq_plan_id_task` unique on `plan`. Downgrade refuses (raises) while any
`task` or `capability_run` row carries `options_scoping`; the ADR names the
operator script that removes them.

S11. **ADR 0037** records: the task kind; `task_link` and what a link pins;
the capability registry and the capability-keyed lattice; `baseline_confirm`
as a structural gate with the unattended standing-default rule; the end-walk
disposition that keeps the plan approved; the Task Agent rename including the
environment variable; the rollback commands and the operator remedy.

S12. **Feasibility check 7 — writing mode** (C6). `scripts/feasibility_checks/
options_scoping/run_check_7_writing_mode.py`, in the 035 pattern, writes the
same baseline sequentially and as a parallel fan-out with a naive join, on
the NEET question and one thin-evidence question, and records compute time
and a side-by-side consistency reading. Nothing from it ships.

## Phase 0 — Build-open baseline — `lead` (inline)

Full `make verify` on the branch. Never build on a red base.

## Phase 1 — Task Agent rename and EB → ES sweep (deliverable 2) — one green commit, own review

1.1 **Manifest and rule table — `lead`.** Reason: the rule table is the
seam; a wrong rule is a silent rename. Finalise `rename-manifest.md` from the
fast-worker draft against `scripts/schema_manifest.py` output; write the 043
rule table and literal list; decide every unmapped `--scan` hit.

1.2 **Sweep tool — `deep-reasoner`.** Brief: `scripts/rename_043.py` reusing
the 038 engine (S9); `--scan` lists identifiers, literals, unmapped hits and
collisions; `--apply` refuses on collisions and is idempotent; `--docs` does
the EB → ES sweep. Done when `--scan` on the branch reports zero unmapped
hits after the lead's table, `--apply` twice reports zero changes the second
time, and the tool's own tests pass.

1.3 **Apply, migration, readers — `deep-reasoner`.** `--apply`; `git mv
planner_prompt.py task_agent_prompt.py` (byte-identical); the rename
revision (table, column, constraints, indexes, the two stored-value
rewrites, reversed on downgrade); the round-trip test; the sweep test (no
old name in `backend/src`, `frontend/src`, `frontend/e2e`, `scripts`,
`infra/DEPLOYMENT.md`, `web-api.md`; allow-list per S9); update
`infra/DEPLOYMENT.md`; `scripts/prompt_hashes.json` path entry via
`--update`, asserting the hash value did not change. Done when full `make
verify` and `pnpm e2e` are green.

1.4 **EB → ES docs sweep — `fast-worker`.** `rename_043.py --docs` over the
manifest's file list; hand-check every skipped quotation; `make
okf-validate`. Done when a repository grep for whole-word `EB` outside the
excluded paths returns only the quotations listed in the manifest.

Gate: **full `make verify`** + `pnpm e2e`. Commit. **Review pass:** the
`code-review` skill at medium on this commit's diff, findings adjudicated by
the lead, before Phase 2 starts.

## Phase 2 — Task kind, links, registry, migration (deliverables 1, 4 backend, 10) — `deep-reasoner`

Brief (S1, S7, S10): the slice migration; `capability_registry.py` and the
eight validate sites; `_open_capability_run` from the task row;
`TaskCreate`/`TaskOut` (`capability`, `project_ids`, `from_task_ids`);
`assign_projects` extraction; `task_link` writes, read model and flag;
`lib/capabilities.ts` key rename and `NewTaskView` capability switch;
`useCreateTask` two requests. Tests: migration round-trip with the downgrade
refusal; registry routing (an ES plan rejects a scoping payload and the
reverse; an ES plan rejects a `baseline_confirm` standing default); ES
steering tests unchanged; `task_link` rules (S7) and the ADR 0033-style
no-access test; create atomicity (a failed link leaves no task row). Done
when full `make verify` is green and `make drift-check` after
`openapi-sync` is green (additive diff).

Gate: **full `make verify`**. Commit.

## Phase 3 — Scoping plan, Task Agent for scoping, inherit context (deliverables 3, 4, 5, 6)

3.1 **Plan model and chain — `deep-reasoner`.** `ScopingPlan`,
`compose_scoping`, directive deltas, `_DIRECTIVE_KEYS` widening, the
acquisition-target key if needed (S2); the planning router's capability
branch (prompt selection, validation through the registry, `capability` on
plan read/patch bodies). Tests per contract § Acceptance checks
(validation, compile, evidence-restriction landing, language stored-not-
applied). Done on `make verify-fast`.

3.2 **`task_agent_scoping_v1` — `lead`.** Reason: prompt-bearing, lead-only.
The Task Agent for a scoping task per deliverable 6; the two depth options
in the ES pattern with honest bands; steering mode not asked; the Where
warning; the constraint-kind question; the standing default written when
unattended is chosen; the "did the change touch the baseline's inputs"
sentence. Re-pin. A stub backend for tests.

3.3 **Inherit context — `fast-worker`.** Exact spec S8; unit tests for the
markdown build (citation markers gone, references gone, one block per link,
byte-stable across two calls).

3.4 **Plan document and New task form — `fast-worker`, then `lead` polish.**
Scoping sections in `PlanDocument` (structure mirrors the ES document, D5
words, the constraints table, Your context, two start actions after a
change), New task form (question + Starts from, same-project ES tasks),
tasks list label. Reason for the `lead` pass: the plan document is a
taste-bearing surface (owner ruling 2026-09-05); the fast-worker lands the
structure, the lead adjusts copy and spacing only. Tests per contract.

Gate: `make verify-fast` + `make frontend-verify`. Commit.

## Phase 4 — Baseline mode and the walk (deliverable 7)

4.1 **Baseline mode — `deep-reasoner`.** S3 exactly: `SectionSpec` fields,
the merge of supplied and proposed sections, the three guards, per-section
turn caps, `depth_label`, the baseline forbidden-title rule. Tests: eight
required always present at both depths; ≤2 proposals after "what is
contested"; the three passes do not run; claim set `{chunk, reasoning, gap}`;
a section with no support is gap claims. Done on `make verify-fast`.

4.2 **Baseline template — `lead`.** Reason: prompt-bearing. `synthesis/
baseline_prompt.py`: the eight sections with instruction and cap, the
proposal instruction (bounded to two, problem-specific), the reasoning
labels for the key assumption and what is contested, the not-found rule, the
Sources section wording (Overton and OpenAlex searched; live official
statistics and departmental pages not searched; the source-tier skew line).
Re-pin.

4.3 **Result view — `fast-worker`.** The band ("the situation these options
would change"), the run state, the "built from plan version N" mark, the
`scoping pass` label; if the Result already renders section progress
events, the eight titles appear as the skeleton (S3). Tests.

Gate: `make verify-fast` + `make frontend-verify`. Commit.

## Phase 5 — The gate (deliverable 8)

5.1 **Lattice, options, unattended, end-walk — `deep-reasoner`.** S4: the
scoping lattice and `baseline_confirm`; `_pause_options_and_bundle` options
and the deterministic card render; the unattended recorded decision; the
end-walk disposition that keeps the plan approved; the `Confirm plan and
build longlist` decision after a change (S4). Tests: pauses in three modes;
recorded non-pausing decision in unattended; ES frequent walk still pauses
generically after synthesise and never names `baseline_confirm`; Change the
plan leaves the plan `approved` and the walk `aborted`.

5.2 **Answer core and turn projection — `deep-reasoner`.** S6: the lift, the
pinned-scope resolver, `AnswerPayloadOut`, the discriminated turn
projection, the widened stored-response validation. Tests: the answer core
returns citations for a paused walk's scope with no conversation row; the
chat route still refuses a paused walk.

5.3 **Gate sort — `lead`.** Reason: prompt-bearing. `gate_sort_prompt.py`
and `AgentBackend.sort_gate_turn`; re-pin; stub for tests.

5.4 **Turn route at a pause — `deep-reasoner`.** S5: fence (1) narrowed for
non-approving turns while paused; sort → answer core or `answer_check_in`
(bound to run, check-in and plan version); `change_plan` with carried text
→ end walk → ordinary turn; mixed and unsure handling. Tests: the contract's
gate-turns list, including the barrier test racing a chat decision against
the card endpoint (exactly one durable decision) and the approving branch
and `patch_plan` still 409 while paused.

5.5 **Thread rendering — `fast-worker`.** `store/thread.ts` item variants;
`DurableTurn` branches for answer-with-citations and decision; `CheckInCard`
moved into thread order for the gate; the two start actions after a change.
Tests per contract.

Gate: **full `make verify`** + `pnpm e2e`. Commit.

## Phase 6 — Feasibility check 7, writing mode (C6) — `deep-reasoner` script, `lead` reading

Runs once Phase 4 exists, in parallel with Phase 5. The script (S12) and its
two runs; the lead reads the two baselines side by side and records numbers
and the consistency reading in `verification.md`. Nothing ships. Reason for
the `lead` reading: it is the qualitative judgement the owner asked for.

## Phase 7 — Live check, evidence, ADR, step-6 exit — `lead`

Reason: browser-driving the pinned live check, writing the evidence and the
ADR are adjudication-adjacent.

1. The contract's live check (a)–(g), with both compute times and the
   gate-sort latency recorded; screenshots.
2. `verification.md`: command tails; migration round-trips (both
   revisions); the rename sweep result and the EB grep; the OpenAPI diff;
   the prompt-hash diff (three new, one path moved, hash unchanged); the
   three baselines' qualitative note; check 7's record; review-lane
   dispositions; deferred deltas; known gaps.
3. ADR 0037 (S11), Accepted with sign-off date.
4. `docs/deferred.md` and `docs/specs/log.md` lines the build owes (the EB →
   ES sweep line; the language-filter gap).
5. Full `make verify` (step-6 exit).

Gate: **full `make verify`**. Commit. **Stop.** Review runs in a fresh
conversation with `task-cycle-review`.

## Out-of-plan reminders

- Stop conditions (contract § Stop conditions): a second non-additive API
  change; a second migration beyond the two planned; the answer core or the
  gate needing a change to the ES's own behaviour; a compute time the owner
  will not accept without cutting a required section.
- The steering router is not touched (C1). If a phase finds it must be, stop
  and report.
- Codex stalls twice today; if a Codex lane is used anywhere, wait with
  `scripts/codex_job.sh wait` and fall back to `deep-reasoner` after one
  relaunch.
