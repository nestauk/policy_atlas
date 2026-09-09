# Plan: 043-scoping-shell-baseline

Deliverables 1–10, decisions D1–D13, the second-round amendments, the
adversarial folds A1–A18 and C1–C18, and every term are defined in
[contract.md](contract.md). The rename inventory is
[rename-manifest.md](rename-manifest.md) (drafted by a fast-worker, checked
by the lead in Phase 1.1). This plan cites them and adds nothing to scope.

> **Status:** drafted 2026-09-09 · lead. **Plan-stage adversarial review
> (fallback lane, `deep-reasoner`, read-only) ran 2026-09-09** on the first
> draft: 18 findings (3 blockers), verdict "material change needed", all 18
> folded (§ Plan-review folds P1–P18). **The Codex lane ran the same brief
> on the first draft:** 16 findings (5 blockers), verdict "material change
> needed"; seven restate P-findings, the rest are folded (§ Plan-review
> folds X1–X16). **Two folds change the contract's wording and need the owner
> at the plan gate:** P1/X1 (two migration revisions, one per phase, where
> the contract says one) and P9 (a `web-api.md` revision for the Task Agent
> turn at a pause) — **both ruled yes, 2026-09-09 · owner**; contract
> § Constraints, § Spec changes item 7 and rubric 10 amended. **Plan approved
> (before implementation): 2026-09-09 · owner.** **ADR 0037 is drafted in this design phase, after plan approval
> and before any build phase** (X15; the task-cycle's step 4); Phase 7 only
> adds evidence and the sign-off date.

Executor marks per AGENTS.md § Agent-side model routing; every `lead` mark
carries its reason. **Owner ruling 2026-09-04 (038) stands:** judgment-bearing
phases go to `deep-reasoner`, not `codex`; the family flip happens at step 7
when Codex reviews the diff. No phase is marked `codex`. Taste-bearing
frontend surfaces get a `lead` polish pass after a `fast-worker` lands the
structure (owner ruling 2026-09-05; P10).

**Verify gates.** Full `make verify` at Phase 0 (build-open baseline), Phase 1
(the rename revision — schema class), Phase 2 (the slice revision — schema
class), Phase 5 (the gate touches the runner and the fence) and Phase 7
(step-6 exit). Phases 3 and 4 close on `make verify-fast` **plus `make
prompt-guard` and `make drift-check`** (P7: `verify-fast` runs neither, and
both phases add a pinned prompt and change a contract model) plus `make
frontend-verify` where the frontend changed; `pnpm e2e` wherever a route or
the thread changed. **One green commit per phase.** Phase 1 gets its own
review pass before any feature code lands (contract deliverable 2).

**Spec changes already applied at contract time** (P18c): contract § Spec
changes items 1, 2, 3, 4 and 6 landed in commits `49a7996b` and `95da17be`.
Only item 5 (EB → ES) and the P9 `web-api.md` revision are build work.

## Decisions fixed here (lead seam design)

S1. **Capability registry** (C9, A2, A18d). `runtime/capability_registry.py`
holds one `CapabilitySpec` per capability: `plan_model` (`TaskPlan` /
`ScopingPlan`), `compose` (the chain builder), `task_agent_prompt` (the
prompt module), `steer_points` (the lattice names valid for its plans) and
`lattice` (name → `PausePoint`). Three functions replace the scattered calls:
`validate_plan(capability, payload)`, `compose_plan(capability, plan)`,
`lattice_for(capability)`. The **ten** `TaskPlan.model_validate` sites go
through it (P13a): `runtime/agent.py:653`, `continuation_state.py:153`,
`steering.py:1611`, `api/routers/runs.py:73,156`, `api/routers/sse.py:534`,
`api/routers/planning.py:281,617,804,832`; and the **seven direct `compose()`
readers** go through `compose_plan` (X13): `api/continuation.py:1231-1232`,
`continuation_state.py:154`, `steering.py:1594,1615`, `runner.py:664,3155`,
`api/routers/planning.py:161`. A test asserts no capability-dependent module
imports `TaskPlan.model_validate` or `compose` directly. Phase 2 installs the
registry with the ES entry only (a chassis); the scoping entry and the
reverse-validation tests land in Phase 3.2 when `ScopingPlan` exists (X3).
`steering.pause_points`,
`lattice_name_for` and `lattice_policy` take the capability's lattice, so
`baseline_confirm` never names an ES boundary. `SteerPointDefault`'s
validator checks against the capability's `steer_points`.
`_open_capability_run` (`runner.py:5018`; the literal at `:5035`) writes the
task's capability. ES behaviour is pinned by the existing steering and plan
tests, which must pass unchanged.

S2. **Scoping plan and chain.** `runtime/scoping_plan.py`: `ScopingPlan`
(`extra="forbid"`, the fields of contract § Plan object; `depth ∈ rapid |
standard`; `constraints[].kind ∈ requirement | preference |
evidence_restriction`; `your_context[]` with `turn_index`; `steering_mode`
default `moderate`; `steer_point_defaults` validated against the scoping
steer points; `baseline_confirmed: {artefact_id, plan_version} |
None` — S4) and `compose_scoping(plan) -> ComposedChain` producing exactly
`acquire → screen_abstract → classify → appraise → ingest_full_text →
synthesise`. Directive deltas: acquire carries the evidence restriction as
`ScopeConstraints` (country group, years; a language restriction is stored and
shown as *not yet applied at retrieval* — C8) and the **baseline acquisition
target** (a constant in `scoping_plan.py`; if the acquire directive grammar
has no per-backend cap key, one is added under the fail-closed grammar and
tested); screen carries target unit and Where in the intent context;
synthesise carries `{"synthesis": {"template": "baseline", "sections": [the
eight supplied specs], "section_budget": 2}}` — **one new directive key**,
`template`; `sections` and `section_budget` are the existing keys, with
`section_budget` meaning "proposals allowed" in template mode (P14).
`synthesis_tools._DIRECTIVE_KEYS` is fail-closed and gains `template`.
`COMPONENT_REGISTRY`, `compile`, `build_graph` and `_run_synthesise` need no
change. **Who writes the intent record's new fields** (X7): the scoping
branch of `persist_approved_plan` (`runtime/agent.py:855-917` inserts the
scope, then the plan) updates the scope with `purpose="baseline"` and the new
`plan_id` in the same transaction; a rebuild after a plan change inserts a
**new** scope row for the new plan version (the plan row's
`evidence_scope_id` is one-to-one) and `POST /runs` opens the walk on it.
Tests: first plan, amended plan, rebuild.

S3. **Baseline mode in synthesise** (A7, C7). The supplied-sections path at
`synthesise_scope` (`:5431`, `directive.sections is not None`) already
bypasses proposal. Baseline mode (`template == "baseline"`): the supplied
eight `SectionSpec`s (from `baseline_prompt.BASELINE_SECTIONS`, in the ruled
order) + up to `section_budget` proposals from `propose_sections`, validated
by `_validate_sections` with a baseline forbidden-title list (no duplicate of
a required title, no "conclusions", no "key findings"), inserted after "what
is contested". `SectionSpec` gains `instruction: str | None` and `turn_cap:
int | None`; `as_seed()` carries the instruction; the `run_section_loop`
call at `:5601` passes `turn_cap=section.turn_cap or SECTION_TURN_CAP`;
`generation_budget_max()` counts the per-section caps. One flag guards the
three ES-only passes at `:5499` (Conclusions), `:5718` (key findings),
`:5781` (case studies); the roll-up already tolerates their absence.
**Not-found is the existing gap claim**: a section with no support is written
as gap claims, which the template instructs and which
`available_claim_types_for_substrate` already admits; no new claim type. The
baseline's claim set is `{chunk, reasoning, gap}` by substrate absence —
nothing to code. The roll-up's provenance gains `depth_label: "scoping
pass"`. Sequential writing (C6). Section progress events already stream
(`ProgressEmitter` `artefact.section_started` / `section_completed`), but
`emit_skeleton` (`runtime/progress.py:38-62`) **unconditionally prepends a
"Key findings" entry** (X8); in baseline mode the skeleton is built from the
actual section list with no ES-only entries, and a test pins the eight-plus-
proposed order in the SSE stream and the Result view. "Shown as they finish"
then costs nothing further — Phase 4 takes it.

S4. **The gate** (A2, A9, A13, C1, C3, C5, P8, P13c). `baseline_confirm =
PausePoint("after_component", "synthesise")` in the **scoping** lattice only;
policy `always` in frequent, moderate and minimal. The after-boundary loop
already visits the last step (`runner.py:1211`, then `_finish_run`), so no
runner loop change. Options at the pause (`_pause_options_and_bundle`,
`runner.py:1931`), with **option ids distinct from durable response values**
(X10 — the only valid responses are `continue | adjust | abort |
mode_change`, `steering_events.py:47-50`): option `confirm_plan` → response
`continue` (the walk finishes `succeeded`; the decision payload records
`plan_version` and the baseline `artefact_id` — the schema and read model
carry an artefact id, not a version, X5); option `change_plan` → response
`abort` with payload `action: "change_plan"`, a **new end-walk disposition**:
like `_persist_abort` (`continuation.py:816`) it writes the decision, sets
`capability_run.status = "aborted"` and `run.finished{status: aborted}`, but
it **does not** flip the plan to `abandoned` — the plan stays `approved` and
editable, because `_load_editable_plan` (`planning.py:812`) reads only
`approved` rows. History shows the walk as aborted by the user's choice to
change the plan. The card render is deterministic: the baseline's
key-assumption block prose and the plan's Settings; `api/checkin_read.py`
gains the `baseline_confirm` branch and `api/stage_vocabulary.py` the name
(P11). **Unattended:** `_resolve_unattended_boundary` writes the decision
through the existing `_emit_standing_proceed_decision` shape
(`runner.py:4171`: `decided_by="standing_default"`, `response="continue"` —
the only valid responses are `continue | adjust | abort | mode_change`, so
"confirm" is the option's label, not the response value) and the flag rides
`flagged_events`; choosing unattended in the Task Agent writes the standing
default for `baseline_confirm` into `steer_point_defaults`. **After a
change** the plan document offers two start actions: `Rebuild baseline`
(`POST /runs` as today; the new walk's intent record `plan_id` and
`plan.evidence_scope_id` point at the new version) and `Confirm plan and
build longlist`. The latter cannot be a steering event — `emit_standalone`
raises without a `run_id` and `base_payload` requires a `capability_run_id`
(P8, X5) — so it is a **plan-scoped record**: a new route `POST
/tasks/{id}/plan/confirm-baseline` writes `baseline_confirmed =
{artefact_id, plan_version}` into the scoping plan as a new approved version
through the ordinary plan-edit path (one transaction; idempotent on the same
pair; 409 `run_active` while a walk is running or paused), visible in History
as a plan version. Task 2 replaces this with the longlist walk, whose opening decision
records the same pair on the new walk. The Task Agent states whether the
change touched the baseline's inputs (a deterministic diff of the six input
fields between plan versions, rendered in the reply).

S5. **Task Agent turn at a pause** (A4, A6, A12, C2, C5, P16, P18b). Fence (1)
in `planning.py:330-341` becomes: 409 `run_active` while `running`; while
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
`carried_text` is **one transcript turn, two commits** (X6, replacing the
follow-on-turn idea): the reserved row (its caller-minted `client_turn_id`)
first commits the end-walk decision in the check-in transaction, then
continues as an ordinary planning turn on the same row (the LLM call outside
any transaction, as today, then the reply commit). Replay of a completed row
returns its stored projection; a failure after the decision commit leaves
the decision durable and the row `failed`, and a retry with the same
`client_turn_id` re-runs only the planning half because the walk is already
ended. Tests: replay, partial failure, retry. A question that also carries a decision is answered, and the
reply offers the decision as an option to click — never applied. The
approving branch (fence 2, `:531-535`) and `patch_plan` (fence 3,
`:862-875`) keep `("running", "paused")`; since a sorted paused turn never
reaches the approving branch, the test for fence 2 drives the
`run_started_meanwhile` race (P16). This changes `web-api.md` § Planning
turns ("running or parked → 409") — P9, a spec revision quoting the owner's
D9 ruling, applied in Phase 5 and logged in Phase 7.

S6. **Answer core and turn projection** (C2, P4). Lift `chat_turns.py:824-961`
into `api/answer_core.py::answer_over_scope(engine, *, task_id, scope,
entry_artefact_id, window, question, backends…, trace_run_id, on_delta=None,
check_cancelled=None) -> (prose, AnswerPayload)`; `run_chat_turn` calls it
and keeps its reservation, locks, `chat_turn` row and fences. `chat_scope`
gains `resolve_run_components(engine, task_id, capability_run_id=…)` so a
**paused** walk's scope resolves (the existing function keeps its
`succeeded|degraded` filter). A shared `AnswerPayloadOut` (the `ChatTurnOut`
citation fields) is used by both. **Additive, not a union** (P4):
`TaskAgentTurnOut` and `TaskAgentTranscriptTurnOut` keep every existing field
and gain optional `kind: "reply" | "answer" | "decision" | None`, `answer:
AnswerPayloadOut | None` and `decision: DecisionOut | None`; the frontend
narrows on `kind`. The stored `response` re-validation at `planning.py:842`
accepts the new optional fields.

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

S9. **Rename phase** (deliverable 2, A10, A11, C13, C14, P2, P5). The 038
engine reads its tables from module constants in every hot path
(`rename_038.py:483, 771-775, 874, 983, 1532-1537`), so "reuse" is a named
sub-task: extract `scripts/rename_engine.py` (identifier splitting, span-safe
editing, ledger, scan/apply, with rules, literals, exclusions and phases
**injected**), make `rename_038.py` a thin caller of it with its tables (its
tests must pass unchanged), and write `rename_043.py` with the 043 tables.
Rules (compound before bare): `planning_transcript` →
`task_agent_transcript`; `planner_state` → `task_agent_state`; `ptr`
constraint infix → `tat` (manifest proposal, confirmed here); `planning`
(conversation-kind sense: `planning_turn`, `PlanningTurn*`, `PlanningPane`,
`planning_conversation`, `/planning-turns`, `planning_turn_in_progress`,
the routers and contract modules `api/routers/planning.py` and
`api/contract/planning.py` → `task_agent.py`, per the manifest) →
`task_agent…`; `planner` (`PlannerBackend`, `OpenAIPlannerBackend`,
`StubPlannerBackend`, `PLANNER_MODEL`, `planner.py`,
`POLICY_ATLAS_PLANNER_MODEL`) → `task_agent…`. **The prompt module's interior
is excluded** (P2): `planner_prompt.py` moves to `task_agent_prompt.py` by
`git mv` and its contents are not edited — `PLANNER_SYSTEM_PROMPT`,
`build_planner_messages`, `PlannerTurnWire`, `PLANNER_PROMPT_VERSION` and the
wire role literal `"planner"` (`:747`, a stored transcript value whose
consumer is this file) stay as they are, listed in the manifest as kept, so
the hash is unchanged and only the pin's path moves; callers import the
old-named symbols from the new module. The producers of the role literal
(`agent.py:997`, `planning.py:256`) are likewise kept, so assistant turns are
never coerced to user turns. Never mapped: `plan`, `TaskPlan`, `PlanDraft`,
`PlanOut`, `plan_id`, `PATCH /plan`, `eb_iof_base_v1`, `eb_icf_base_v1`,
`evidence_base_coverage`, ordinary-English "planning" in fixtures (manifest).
Stored values rewritten in the rename revision and reversed on downgrade:
`conversation.kind` `planning` → `task_agent`; `plan.created_by` `planner` →
`task_agent` (production writes only `user` today — the manifest found the
value in tests and a schema comment; the one-line rewrite stays for safety).
The revision renames the table, the column and every constraint and index
in the manifest. The EB → ES sweep is `rename_043.py --docs` over the
manifest's file list, markdown-aware, skipping quoted owner rulings and the
two "EB handoff" citations of a frozen source the manifest flags.

S10. **Two revisions, one per phase** (P1 — owner to confirm at the plan
gate; contract § Constraints and rubric 10 say "one migration"). Phase 1
must be a green, separately reviewed commit, and its schema names cannot
match the database without its own revision; so the rename revision lands
in Phase 1 and the slice revision in Phase 2, each reversible, downgrade
chain rename ← slice. The slice revision: `task.capability TEXT NOT NULL
DEFAULT 'evidence_search'` + `ck_task_capability`; widen
`ck_capr_capability`; `task_link` (S7 columns; FKs to `task`;
`(source_capability_run_id, source_task_id)` → `capability_run` via
`uq_capr_id_task` (`schema.py:1311`); unique `(source_task_id,
target_task_id)`; check source ≠ target); `evidence_scope.purpose TEXT NULL`
+ check on the four values; `evidence_scope.plan_id UUID NULL` with a
composite FK `(plan_id, task_id)` → `plan(plan_id, task_id)` over a new
`uq_plan_id_task`. Downgrade refuses (raises) while any `task` or
`capability_run` row carries `options_scoping`; the ADR names the operator
script that removes them.

S11. **ADR 0037** records: the task kind; `task_link` and what a link pins;
the capability registry and the capability-keyed lattice; `baseline_confirm`
as a structural gate with the unattended standing-default rule; the end-walk
disposition that keeps the plan approved and the plan-scoped confirmation
record; the Task Agent rename including the environment variable and the
kept prompt interior; two revisions and their rollback commands and the
operator remedy.

S12. **Feasibility check 7 — writing mode** (C6, P17). `scripts/
feasibility_checks/options_scoping/run_check_7_writing_mode.py`, in the 035
pattern, writes the same baseline sequentially and as a parallel fan-out
with a naive join, on the NEET question and one thin-evidence question, and
records compute time and a side-by-side consistency reading. **Bound:** if
the parallel driver needs a concurrent claim ledger to work at all, that is
the finding and the check stops there. Runs before Phase 5 closes. Nothing
from it ships.

## Phase 0 — Build-open baseline — `lead` (inline)

Full `make verify` on the branch. Never build on a red base.

## Phase 1 — Task Agent rename and EB → ES sweep (deliverable 2) — one green commit, own review

1.1 **Manifest and rule table — `lead`.** Reason: the rule table is the
seam; a wrong rule is a silent rename. Check `rename-manifest.md`'s schema
section against the live metadata (`scripts/schema_manifest.py` refuses any
post-038 checkout — X2 — so the check is a one-off inline iteration over
`schema.metadata`, not that script); confirm the manifest's open items (the
`tat` infix; the two router/contract module renames; the kept prompt
interior and role literal; the two "EB handoff" citations kept); write the
043 rule table and literal list; decide every unmapped `--scan` hit.

1.2 **Engine extraction and sweep tool — `deep-reasoner`.** Brief: S9's
`rename_engine.py` extraction with tables injected; `rename_038.py` becomes a
thin caller and its existing tests pass unchanged; `rename_043.py` with the
043 tables; `--scan` lists identifiers, literals, unmapped hits and
collisions; `--apply` refuses on collisions and is idempotent; `--docs` does
the EB → ES sweep. Done when `--scan` on the branch reports zero unmapped
hits after the lead's table, `--apply` twice reports zero changes the second
time, and the engine's and both scripts' tests pass.

1.3 **Apply, revision, readers — `deep-reasoner`.** `--apply`; `git mv
planner_prompt.py task_agent_prompt.py` with no interior edit; the rename
revision (table, column, constraints, indexes, the two stored-value
rewrites, reversed on downgrade); the round-trip test; the sweep test (no
old name in `backend/src`, `frontend/src`, `frontend/e2e`, `scripts`,
`infra/DEPLOYMENT.md`, `web-api.md`, with the manifest's kept list as the
allow-list); update `infra/DEPLOYMENT.md` (the variable rename; the code
default is unchanged so an old-only deploy behaves as before);
`scripts/prompt_hashes.json` path entry via `--update`, asserting the hash
value did not change; `make openapi-sync` for the path rename. Done when
full `make verify` and `pnpm e2e` are green.

1.4 **Docs sweep — `fast-worker`, quotations adjudicated by `lead`.**
`rename_043.py --docs` over the manifest's file list for **both** renames:
the Task Agent tokens in `docs/knowledge/**` content, `web-api.md` and
`infra/DEPLOYMENT.md` (filenames of knowledge concepts never change), and
EB → ES; `make okf-validate`. The fast-worker runs the deterministic sweep
and the greps; the lead reads every skipped quotation and citation and
decides each (X14: attribution is judgment). Done when a repository grep for
the old Task Agent tokens and whole-word `EB` outside the excluded paths
returns only the kept items listed in the manifest.

Gate: **full `make verify`** + `pnpm e2e`. Commit. **Review pass:** the
`code-review` skill at medium on this commit's diff, findings adjudicated by
the lead, before Phase 2 starts.

## Phase 2 — Task kind, links, registry, slice revision (deliverables 1, 4 backend, 10) — `deep-reasoner`

Brief (S1, S7, S10): the slice revision; `capability_registry.py` as a
chassis with the ES entry, routing the ten validate sites and the seven
compose sites through it (X3, X13 — the scoping entry arrives in 3.2);
`_open_capability_run` from the task row;
`TaskCreate`/`TaskOut` (`capability`, `project_ids`, `from_task_ids`);
`assign_projects` extraction; `task_link` writes, read model and flag;
`lib/capabilities.ts` key rename and `NewTaskView` capability switch;
`useCreateTask` two requests; the operator script ADR 0037 names for the
downgrade remedy (`scripts/ops_remove_scoping_tasks.py`: lists, then on
`--apply` hard-deletes every `options_scoping` task with its links, walks,
runs, scopes and result rows; refuses on a task with inbound links from an
ES task), with a test on a seeded scoping task. Tests: migration round-trip with the downgrade
refusal; registry routing for ES (every reader resolves through the
registry; the no-direct-import test); ES steering tests unchanged; `task_link` rules (S7) and the ADR 0033-style
no-access test; create atomicity (a failed link leaves no task row). Done
when full `make verify` is green and `make drift-check` after
`openapi-sync` is green (additive diff).

Gate: **full `make verify`**. Commit.

## Phase 3 — Scoping plan, Task Agent for scoping, inherit context (deliverables 3, 4, 5, 6)

Order (P6): the lead's prompt module first, so the delegate's brief imports a
real artefact.

3.1 **`task_agent_scoping_v1` — `lead`.** Reason: prompt-bearing, lead-only.
The Task Agent for a scoping task per deliverable 6; the two depth options
in the ES pattern with honest bands; steering mode not asked; the Where
warning; the constraint-kind question; the standing default written when
unattended is chosen; the "did the change touch the baseline's inputs"
sentence. Re-pin. A stub backend for tests.

3.2 **Plan model and chain — `deep-reasoner`.** `ScopingPlan`,
`compose_scoping`, directive deltas, the `template` key, the
acquisition-target key if needed (S2); the planning router's capability
branch (prompt selection through the registry, validation through the
registry, `capability` on plan read/patch bodies); the
`confirm-baseline` route and `baseline_confirmed` field (S4); the scoping
registry entry (X3) and the intent-record writes in the scoping
`persist_approved_plan` branch (X7). Tests per contract § Acceptance checks
(validation, compile, evidence-restriction landing, language
stored-not-applied) plus: an ES plan rejects a scoping payload and the
reverse; an ES plan rejects a `baseline_confirm` standing default; first
plan, amended plan and rebuild each leave the right `purpose` and `plan_id`.
Done on `make verify-fast` + `prompt-guard` + `drift-check`.

3.3 **Inherit context — `fast-worker`.** Exact spec S8; unit tests for the
markdown build (citation markers gone, references gone, one block per link,
byte-stable across two calls).

3.4 **Plan document and New task form — `fast-worker`, then `lead` polish.**
Scoping sections in `PlanDocument` (structure mirrors the ES document, D5
words, the constraints table, Your context, two start actions after a
change), New task form (question + Starts from, same-project ES tasks),
the tasks list label and the **task header** (X12: the workspace header's
capability word, with a rendering test). Reason for the `lead` pass: the plan document is a
taste-bearing surface; the fast-worker lands the structure, the lead
adjusts copy and spacing only. Tests per contract.

Gate: `make verify-fast` + `make prompt-guard` + `make drift-check` +
`make frontend-verify` + `pnpm e2e` (the New task route changed). Commit.

## Phase 4 — Baseline mode, the walk and the Result view (deliverables 7, 9)

4.1 **Baseline template — `lead`.** Reason: prompt-bearing. `synthesis/
baseline_prompt.py`: the eight `SectionSpec`s with instruction and cap, the
proposal instruction (bounded, problem-specific), the reasoning labels for
the key assumption and what is contested, the not-found rule, the Sources
section wording (Overton and OpenAlex searched; live official statistics and
departmental pages not searched; the source-tier skew line). Re-pin.

4.2 **Baseline mode — `deep-reasoner`.** S3 exactly: `SectionSpec` fields,
the merge of supplied and proposed sections, the three guards, per-section
turn caps, `depth_label`, the baseline forbidden-title rule. Tests: eight
required always present at both depths; ≤2 proposals after "what is
contested"; the three passes do not run; claim set `{chunk, reasoning, gap}`;
a section with no support is gap claims.

4.3 **Result view (deliverable 9) — `deep-reasoner`, then `lead` polish**
(X16: live-progress presentation is state logic, not transcription). The
band ("the situation these options would change"), the run state, the "built
from plan version N" mark, the `scoping pass` label; the skeleton built from
the actual section list with the eight-plus-proposed order pinned in SSE and
the view (S3, X8). Sources, Share and History untouched. Tests.

4.4 **Feasibility check 7, writing mode (C6) — `deep-reasoner` script, `lead`
adjudication.** Before this phase closes (X9: the comparison precedes
finalising the baseline; plan-as-object § Thoroughness). The script (S12,
bounded) and its two runs; the lead reads the two baselines side by side,
records numbers and the consistency reading in `verification.md`, and
adjudicates: sequential stays the shipped mode unless the owner, shown the
reading, revises the durability contract. Nothing from the check ships.

Gate: `make verify-fast` + `make prompt-guard` + `make frontend-verify`.
Commit.

## Phase 5 — The gate (deliverable 8)

5.1 **Gate sort — `lead`.** Reason: prompt-bearing. `gate_sort_prompt.py`
and `AgentBackend.sort_gate_turn`; re-pin; stub for tests.

5.2 **Lattice, options, unattended, end-walk — `deep-reasoner`.** S4: the
scoping lattice and `baseline_confirm`; `_pause_options_and_bundle` options
and the deterministic card render; `api/checkin_read.py` and
`api/stage_vocabulary.py` branches (P11); the unattended recorded decision;
the end-walk disposition that keeps the plan approved. Tests: pauses in three
modes; recorded non-pausing decision in unattended; ES frequent walk still
pauses generically after synthesise and never names `baseline_confirm`;
Change the plan leaves the plan `approved` and the walk `aborted`; the card
renders the two options.

5.3 **Answer core and turn projection — `deep-reasoner`.** S6: the lift, the
pinned-scope resolver, `AnswerPayloadOut`, the additive optional fields, the
widened stored-response validation. Tests: the answer core returns citations
for a paused walk's scope with no conversation row; the chat route still
refuses a paused walk; the OpenAPI diff is additive.

5.4 **Turn route at a pause — `deep-reasoner`.** S5: fence (1) narrowed for
sorted turns while paused; sort → answer core or `answer_check_in` (bound to
run, check-in and plan version); `change_plan` with carried text → end walk
→ the same row continues as a planning turn (X6); mixed and unsure
handling. Tests: the contract's gate-turns list, the replay / partial-failure
/ retry trio (X6) (the folded bullet; the earlier
"through the steering path, keeps the walk paused" wording is superseded —
P12, folded in the contract), the barrier test racing a chat decision
against the card endpoint (exactly one durable decision), fence 2 driven by
the meanwhile race (P16), `patch_plan` still 409 while paused.

5.5 **Thread rendering — `deep-reasoner`, then `lead` polish** (X16). `store/
thread.ts` item variants and their chronological ordering with decisions and
the gate card; `DurableTurn` branches for answer-with-citations and decision;
`CheckInCard` moved into thread order for the gate; the two start actions
after a change. Named ordering tests. Reason for the `lead` pass: the thread
is the product's primary chat surface (owner ruling 2026-09-05).

5.6 **Spec revision — `lead` (inline).** `web-api.md` § Planning turns and
§ Check-ins: a sorted, non-approving Task Agent turn is admitted while a
scoping walk is paused; the approving branch and `PATCH /plan` stay fenced
(P9, quoting the owner's D9 ruling). Reason: a spec edit with the owner's
words is not delegable.

Gate: **full `make verify`** + `pnpm e2e`. Commit.

## Phase 6 — (merged into Phase 4.4 by X9; number kept so the rubric's phase references hold)

## Phase 7 — Live check, evidence, ADR evidence, step-6 exit — `lead`

Reason: browser-driving the pinned live check, writing the evidence and the
ADR are adjudication-adjacent.

1. The contract's live check (a)–(g), with both compute times and the
   gate-sort latency recorded; screenshots.
2. `verification.md`: command tails; migration round-trips (both
   revisions); the rename sweep result and the EB grep; the OpenAPI diff;
   the prompt-hash diff (three new, one path moved, hash unchanged); the
   three baselines' qualitative note; check 7's record; review-lane
   dispositions; deferred deltas; known gaps.
3. ADR 0037 (S11, drafted at step 4 of the design phase): add the evidence
   links and the measured numbers; the owner's sign-off date is already on it
   (X15).
4. `docs/deferred.md` and `docs/specs/log.md` (P15): the EB → ES sweep
   line; the `web-api.md` revision line; the language-filter gap; and the
   contract's deferred list confirmed present — per-field turn provenance
   (resolved, noted) · Search further · inherited document rows · `task_link
   .option_id` · scoping deep · the later latency levers · the Task Agent as
   the ES control surface and any chat carrying Task Agent turns · open
   question 7 (rebuild only the touched sections).
5. Full `make verify` (step-6 exit).

Gate: **full `make verify`**. Commit. **Stop.** Review runs in a fresh
conversation with `task-cycle-review`.

## Plan-review folds (2026-09-09, fallback lane)

| # | Finding | Fold |
|---|---|---|
| P1 | Two migrations where the contract says one; the plan silently re-read the stop condition | S10 states two revisions, one per phase, and asks the owner at the plan gate; contract § Constraints and rubric 10 amended on approval |
| P2 | The prompt file cannot move byte-identical if its interior identifiers and the role literal are renamed | S9 excludes the prompt module's interior and the role literal (kept, like fingerprints); callers import old-named symbols from the new module |
| P3 | The manifest did not exist | committed at `ce93df5a` before this fold; Phase 1.1 checks it |
| P4 | A discriminated union is a second non-additive API change | S6: optional `kind`, `answer`, `decision` fields on the existing models |
| P5 | The 038 engine reads module constants; "reuse" is a refactor | S9/1.2: named engine extraction with tables injected; 038 becomes a thin caller |
| P6 | 3.1 and 4.1 needed the lead's prompt built in 3.2/4.2 | prompt sub-phases now run first in Phases 3 and 4 |
| P7 | `verify-fast` runs neither `prompt-guard` nor `drift-check` | added to the Phase 3 and 4 gates |
| P8 | A run-less steering decision is impossible (`emit_standalone` requires a run) | S4: a plan-scoped `baseline_confirmed` record via a `confirm-baseline` route |
| P9 | S5 contradicts `web-api.md` and no phase revised it | Phase 5.6 spec revision; owner to confirm at the plan gate |
| P10 | Taste-bearing frontend delegated without a lead pass | 4.3 and 5.5 gain the lead polish pass |
| P11 | `checkin_read.py` / `stage_vocabulary.py` unowned | named in 5.2 |
| P12 | Contract still carried the pre-C1 gate check | contract bullet folded |
| P13 | Ten validate sites, not eight; `runner.py:5018`; unattended response is `continue` | corrected in S1 and S4 |
| P14 | `proposed_max` duplicates `section_budget` | S2: only `template` is new |
| P15 | Phase 7.4 named two deferred lines of nine | enumerated |
| P16 | The approving-branch-while-paused test was unreachable | test drives the meanwhile race |
| P17 | Phase 6 unbounded and late | bound stated; runs before Phase 5 closes |
| P18 | Deliverable 9 had no phase; the follow-on turn needs a `client_turn_id`; spec changes already applied not said | Phase 4 header; server-minted id; note under Verify gates |

### Codex lane (on the first draft, `051548ce`)

| # | Finding | Fold |
|---|---|---|
| X1 | Two migrations violate the one-migration gate; `downgrade -1` reverses only one | = P1; owner at the plan gate; rollback names two steps |
| X2 | Manifest absent; `schema_manifest.py` refuses post-038 checkouts | manifest committed `ce93df5a`; Phase 1.1 checks against live metadata inline |
| X3 | Phase 2 cannot register scoping before Phase 3 creates it | Phase 2 = registry chassis with ES; scoping entry and reverse tests in 3.2 |
| X4 | Byte-identical prompt file vs interior renames | = P2 |
| X5 | Run-less confirm has no durability model; artefact id, not version | = P8 with `artefact_id`; route semantics stated |
| X6 | Follow-on turn has no retry or partial-failure contract | one transcript turn, two commits; replay / partial-failure / retry tests |
| X7 | No phase writes `purpose` / `plan_id` | S2 and 3.2: the scoping `persist_approved_plan` branch; rebuild inserts a new scope |
| X8 | `emit_skeleton` always prepends "Key findings" | S3 and 4.3: skeleton from the actual list; order test |
| X9 | The feasibility check ran after the baseline was final | Phase 4.4, before Phase 4 closes, with lead adjudication |
| X10 | `change_plan` / `confirm` are not valid response values | option ids vs responses: `continue` / `abort` + `action` |
| X11 | Gates omit prompt-guard, drift-check, openapi-sync, e2e | = P7 plus `openapi-sync` in 1.3 and e2e in Phase 3 |
| X12 | Task header has no phase | 3.4 |
| X13 | Ten validate sites; seven direct `compose()` readers | S1 table; no-direct-import test |
| X14 | Knowledge content omitted from the Task Agent rename; quotation checks given to fast-worker | 1.4 covers both renames in docs; lead adjudicates quotations |
| X15 | ADR written after the seams it governs | ADR 0037 drafted at step 4, before Phase 0 |
| X16 | Thread and Result work routed as mechanical | 4.3 and 5.5 → deep-reasoner + lead polish |

## Out-of-plan reminders

- Stop conditions (contract § Stop conditions): a second non-additive API
  change; a third migration; the answer core or the gate needing a change to
  the ES's own behaviour; a compute time the owner will not accept without
  cutting a required section.
- The steering router is not touched (C1). If a phase finds it must be, stop
  and report.
- Codex stalled twice today; if a Codex lane is used anywhere, wait with
  `scripts/codex_job.sh wait` and fall back to `deep-reasoner` after one
  relaunch.
