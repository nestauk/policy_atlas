# Task contract: 043-scoping-shell-baseline

One implementation slice: the first of the five options-scoping build tasks
(PR #69 "Task 1 — the task shell and the baseline"). It lands the second task
kind, its plan and Task Agent chat, the link to an existing Evidence search,
the "do nothing" baseline, and the gate where the user confirms the plan
against the baseline before any option is generated.

> **Status:** **approved 2026-09-09 · owner** (decisions D1–D13 ruled one by
> one in an interview the same day; rulings folded in below and quoted where
> they change a spec). Contract-stage adversarial review (Codex, read-only):
> _next_ · Plan approved (before implementation): _pending_ ·
> ADR: **0037** (to be written at step 4 — task kind, `task_link`, the
> baseline gate, the Task Agent rename, rollback).
>
> **Branching:** `task/043-scoping-shell-baseline` from `feat/options-scoping`
> at `7e31c373` (dev merged in after tasks 039–042; issue #74 fix included).
> PR target: `feat/options-scoping`, merge commit (not squash), per PR #69.
>
> **Prior decisions this slice builds on:** the sixteen decision-sheet rows
> decided 2026-09-09 (`docs/tasks/035-options-scoping/checks/decision-sheet.md`
> rows A4 reduced, A5 bug, A6, A7, A8 deferred, B3, C1, C2 dissolved, C3, C4,
> D3 dissolved, E12, E13 part, E16, F1). They are applied in the specs and are
> **context, not targets**. Three of them are revised by this contract's
> interview (E12 on the baseline's depth grading; the structural gates in
> unattended mode; the baseline's fixed structure) — see § Spec changes.
> The task number is a reservation id (035 note).

## Goal

A user can start an **Options scoping** task, agree its plan in the Task Agent
chat, and receive a sourced profile of "Do nothing" that the run pauses on.
In the same chat the user questions the baseline, changes the plan if needed,
and confirms it. Nothing after the baseline runs in this slice: the longlist
is task 2.

Ten numbered deliverables, one numbering used by the rubric, the plan and the
ADR:

1. **Task kind.** A task carries its capability (`evidence_search` or
   `options_scoping`), written at creation, never changed and never derived
   (D2). Existing tasks are Evidence search. The New task card, the tasks
   list and the task header say "Options scoping" (D5); the list shows a
   scoping task's depth.
2. **Task Agent rename (phase one, fenced).** The conversation kind
   `planning` becomes `task_agent`; `planning_transcript` becomes
   `task_agent_transcript`; `/planning-turns` becomes `/task-agent-turns`;
   `PlanningTurn*` models become `TaskAgentTurn*`; the frontend `PlanningPane`
   and friends follow. Stored `kind` values are rewritten in the migration
   and reversed on downgrade; no redirect from the old path (the 038 rule).
   The ES code's `planner` names follow (owner, second round): module
   `runtime/planner.py` → `task_agent.py`, `planner_prompt.py` →
   `task_agent_prompt.py`, `PlannerBackend` and its OpenAI and stub classes
   → `TaskAgentBackend`, and the environment variable
   `POLICY_ATLAS_PLANNER_MODEL` → `POLICY_ATLAS_TASK_AGENT_MODEL` (a
   deployment config change: `infra/DEPLOYMENT.md` and the staging
   environment value, approved with this contract). The prompt **version
   string `planner_v1` stays** — it is a stored provenance value (038 rule
   R1); the pinned hash entry moves with the file and is re-pinned as a
   words-only diff. The same phase sweeps the abbreviation **EB → ES** in
   the living specs (`docs/specs/**` except `sources/`), `AGENTS.md`, the
   skills and templates, `docs/agentic-ops/`, and code comments and
   docstrings; never ADRs, merged task docs, the spec log's past entries or
   frozen sources (AGENTS.md landmine). First commit on the branch, reviewed
   as its own diff before any feature code lands (D9 rider). *Why now
   (owner):* "planning turn" named one job of a thread that now carries
   questions, instructions and decisions; "if we're doing an initial rename
   phase in this task, then might as well do this rename too".
3. **Start a scoping task.** The New task screen, with the same shape as the
   Evidence search's: the question and one scoping-specific control, **Starts
   from** — zero or more Evidence search tasks in the same project (links
   must exist before the first turn). No depth control and no job control on
   the form (owner, second round: parity with ES, where depth is agreed in
   the conversation): depth is offered in the Task Agent conversation
   (deliverable 6); the scoping job (explore · sense-check) is not shown until
   sense-check exists (task 4 decides where it lives). Prepare plan → the
   Agent tab.
4. **Link and inherit.** Each "starts from" choice is a `task_link` row:
   many-to-many, same-project only, archive-not-delete, changes no access.
   `inherit` (task-1 part, D4) pins the source run ids on the link and gives
   the Task Agent, as context: the linked task's **whole plan**, its
   **report body with citations stripped**, and its **coverage statement**,
   each fenced once after the system instructions and rehydrated on every
   turn. Proposals drawn from them are tagged *assumed*. The user's own ask
   stays primary (decision A6). Document rows and longlist suggestions enter
   with the longlist (task 2).
5. **Scoping plan.** A plan object with the scoping slots (§ Plan object),
   versioned in the existing `plan` table (D1), shown as the navy plan
   document beside the Task Agent exactly like the Evidence search plan:
   Starts from · Question and intended change · Settings (who or what should
   change · where · outcomes · depth) · Constraints and preferences (a table:
   what you asked for · what happens · checked at) · Your context · Steps and
   check-ins. One start action: **Confirm and build baseline**, with a coarse
   time band.
6. **The Task Agent for a scoping task** (not a "planner": the thread carries
   through to the gate). Prompt surface `task_agent_scoping_v1` in
   `runtime/task_agent_scoping_prompt.py`, lead-authored, hash-pinned. It
   fills the plan from the question and the linked tasks, tags each field
   *from your question* / *assumed* / *your call*, asks who or what should
   change when the question leaves it open, defaults Where to the United
   Kingdom (assumed, please check), offers setting as an optional
   constraint, asks which kind a constraint sentence is when it is ambiguous
   ("limit the evidence I read, or the options you would consider?"), and
   says so before confirmation when an evidence restriction would exclude the
   plan's Where (D8). **Depth** is offered the way ES offers it: two labelled
   options in the conversation (rapid · standard, each with what it buys and
   an honest time band), every time, no default (ruling 25); the plan is not
   ready until one is chosen. **Steering mode** is not asked, as ES does not
   ask: the plan carries it as an editable setting, default "At the key
   decisions" (D11), and the user changes it in their own words.
7. **Baseline run.** Confirming the plan runs one walk: acquire (Overton and
   OpenAlex, a small acquisition target — D7) → screen (title and abstract;
   the plan compiled to carry target unit and Where) → classify → appraise →
   ingest → synthesise with the **baseline template** (§ Baseline). Its own
   intent record (purpose `baseline`, plan version). Each empirical premise is
   sourced; the key assumption and what is contested are labelled reasoning;
   "not found" is a content state; the coverage statement names live official
   statistics and departmental pages as not searched. Evidence restrictions
   apply to this acquire like any other (D8).
8. **The gate.** The walk pauses after the baseline in every attended
   steering mode; in unattended it passes on a standing default, recorded and
   flagged (D11). **The Task Agent chat is open at the gate** (D9): each turn
   is sorted (question · instruction · decision) and routed — a question gets
   a grounded answer over the baseline artefact in the thread; an instruction
   goes through the existing steering router to compiled plan deltas the user
   confirms, writing a new plan version; the two decisions, **Confirm plan
   and build longlist** and **Change the plan**, are also options on the
   check-in card in the same thread. The card quotes the baseline's key
   assumption and the plan's Settings. Confirm records the decision and ends
   the walk (D12); the Result says the longlist arrives with the next stage.
   Routing hangs on the turn, not on the conversation kind, so a later slice
   can let any chat carry the same turns.
9. **Tabs and views.** Agent · Result · Sources · Share · History, the task's
   own. Result shows the baseline profile as linear text with a side outline
   and collapsible sections, under a band worded **the situation these
   options would change** and the run state (ready · awaiting your
   confirmation / plan confirmed). Sources is the Evidence search's Sources
   component over the baseline's documents, unchanged. Share and History
   unchanged.
10. **System records.** `task.capability`; `task_link`;
    `evidence_scope.purpose` and `evidence_scope.plan_version` (several intent
    records per plan, decision C4); the `baseline_confirm` steer point; the
    `options_scoping` capability on `capability_run`; the renamed
    conversation kind, transcript table and Task Agent module names (2). Declared once, in the ADR,
    for tasks 2–5 to build on.

## Deliverable

A PR on `task/043-scoping-shell-baseline` into `feat/options-scoping`: one
alembic migration, the rename phase, the scoping plan model and planner, the
baseline template and walk, the gate with its routed turns, the frontend
shell, tests, `verification.md`, ADR 0037, the spec changes in § Spec changes,
and the decisions below quoted where they are applied.

## Terms

| Term | Meaning |
|---|---|
| **capability** | The kind of work a task does. Code: `task.capability`, values `evidence_search` \| `options_scoping`; the same words as `capability_run.capability` (`backend/src/policy_atlas/core/schema.py`). User-facing: "Evidence search", "Options scoping". |
| **Evidence search (ES)** | The first capability. Its components are reused here, never mirrored (owner ruling 2026-09-07). Older documents, ADRs and the frozen sources say "EB" (Evidence Base, the pre-038 name); deliverable 2 sweeps the living specs to ES. |
| **task 1 … task 5** | The five options-scoping build tasks in PR #69. This slice is task 1. Not the product Task. |
| **Task Agent** | The primary chat of a task, pinned first in the Agent tab (`docs/specs/vocabulary.md`); the conversation the user plans, steers and questions the task through. After deliverable 2 its code names are `task_agent` (conversation kind), `task_agent_transcript`, `/task-agent-turns`, `runtime/task_agent.py`, `TaskAgentBackend`, `POLICY_ATLAS_TASK_AGENT_MODEL`. Before it: `planning`, `planning_transcript`, `/planning-turns`, `runtime/planner.py`, `PlannerBackend`, `POLICY_ATLAS_PLANNER_MODEL`. |
| **Agent tab** | The task tab that hosts every chat of the task: the Task Agent first, then ordinary chats. Not the same thing as the Task Agent. |
| **agent persona** | The same actor as the Task Agent, seen from the code: the prompt family `agent_v1` (`runtime/agent_prompt.py`; "orchestrator" before 038) that plans in the conversation, routes free text at pauses and watches boundaries. The Task Agent is the thread the user has with it. One actor, one thread; two names because one is a prompt family and the other a product surface. |
| **plan** | The user-approved object the run compiles from. Table `plan` (`task_plan` in `schema.py`), payload JSONB, versioned per task. |
| **intent record** | An `evidence_scope` row: the question a run is answering plus its settings; every result row points at one. Decision C4: several per plan. |
| **Link** | A `task_link` row: source task, target task, pinned source run ids, created by/at. Declared in `data-model.md` § Links between tasks (decision A6). |
| **inherit** | The shared component that reads across a Link. Its task-1 part seeds the Task Agent and pins the source runs. Its document part lands in task 2. |
| **baseline** | The profile of "Do nothing": eight required sections plus up to two the writer proposes (§ Baseline). The Result of this slice. |
| **the gate** | The pause after the baseline where the user confirms the plan. Steer point `baseline_confirm`; the first of the two structural gates (OS capability § Pipeline and gates). |
| **steer point** | A named pause on the steering lattice (`runtime/steering.py` `LATTICE_POINTS`). ES has five; this slice adds one. |
| **router** | The `agent_v1` moment that compiles a free-text instruction at a pause into plan deltas, each re-validated fail-closed and applied only after the user confirms (task 024). |
| **walk** | One run of a capability's chain: a `capability_run` row plus its component `runs`. |
| **depth** | The plan's rapid \| standard, the ES's words. Offered as options in the conversation, every time, no default (ruling 25). Deep is ⏸ later for scoping and is not shown (D6). |
| **origin tag** | Per plan field: *from your question* \| *assumed* \| *your call*. |
| **constraint kind** | **requirement** — about the option's design; checked at the longlist; excludes with the reason shown ("scope-shaped" in the specs) \| **preference** — about what the option does or costs; checked after assessment; until then a labelled guess that sorts and never excludes; after, a failed one is shown on the option and the user decides ("effect- or cost-shaped" in the specs) \| **evidence restriction** — where evidence may come from; applied at retrieval as the ES's search directive filters (decision C1). Owner naming 2026-09-09, from the Frame board's heading "Constraints and preferences". |
| **Your context** | The plan section of the user's transferability context: entries typed *present fact* \| *commitment*, verbatim words, the turn that produced them, an optional *test this as a condition* flag (decisions C3, E13). |
| **Sources component** | The ES Sources tab: coverage header, filter chips, document table, Landscape and All sources views (`frontend/src/views/Sources*.tsx`). |
| **standing default** | The pre-declared answer an unattended run gives at a steer point, recorded with `decided_by: standing_default` and flagged in the end-of-run review (execution-orchestration § Steering modes). |

## Read first

- [OS capability](../../specs/capabilities/options-scoping/capability.md) —
  § Artefact & scope, § Depths and modes, § Pipeline and gates (plan,
  baseline), § Output structure (baseline profile), § Product surface,
  § Check-in points.
- [OS components](../../specs/capabilities/options-scoping/components.md) —
  § 0 inherit, § 1 plan, § 2–5, ⟨baseline⟩ composition, § 11 synthesise(baseline).
- [OS trust](../../specs/capabilities/options-scoping/trust.md) — § Principle,
  § Provenance labels, § What is structurally impossible.
- [plan-as-object](../../specs/system/plan-as-object.md) — § What a plan
  contains (Your context; several intent records per plan), § Thoroughness
  (time and depth for options scoping), § Source / evidence policy.
- [data-model](../../specs/system/data-model.md) — § Corpus & source snapshots
  (inherited documents), § Links between tasks.
- [execution-orchestration](../../specs/system/execution-orchestration.md) —
  § Steering modes & the routing rule (the lattice; substance is never silent).
- [web-api](../../specs/system/web-api.md) — § Planning turns, § Conversations,
  § Runs, § Check-ins (the routes deliverables 2 and 8 change).
- [ES components § 0](../../specs/capabilities/evidence-search/components.md)
  — the reverse inherit direction (task 5), for symmetry only.
- [prompting](../../specs/system/prompting.md) — the two new prompt surfaces.
- The boards `Ask`, `Frame`, `Baseline`, `BaselineGenerating`, `TasksList`
  under `docs/specs/sources/options-scoping/boards/` — product intent only;
  every figure is placeholder; rulings win.
- `docs/tasks/035-options-scoping/checks/check-6-contract-trace.md` § What
  this means for task 1 (superseded where the decision sheet ruled otherwise).
- `docs/tasks/038-vocabulary-alignment/contract.md` § Mechanics and ADR 0036
  § Rollback — the rename pattern deliverable 2 follows.

## Plan object

The scoping plan is stored in the existing `plan` table and lineage; the
payload is validated by the task's capability (D1). Fields (spec § 1 plan;
the Frame board):

| Field | Content | Origin tag | Compiles to |
|---|---|---|---|
| `title` | short name | — | task name |
| `question` | the user's ask | — | baseline and longlist intent text |
| `intended_change` | what we are trying to change | yes | intent text |
| `target_unit` | who or what should change (people, firms, places, organisations, systems) | yes | intent context; screen prompt input |
| `where` | the jurisdiction the policy applies to; default "United Kingdom" tagged *assumed* | yes | intent context; screen prompt input |
| `outcomes[]` | the outcomes evidence is read against | yes | intent context |
| `depth` | rapid \| standard (D6), chosen from the Task Agent's offered options | *your call* | stored; tasks 2–3 read it; the baseline has one shape at both (D7) |
| `constraints[]` | `{text, kind, origin, checked_at}`; kind ∈ requirement \| preference \| evidence_restriction; checked_at ∈ longlist \| assessment \| retrieval | yes | evidence restrictions → the ES `ScopeConstraints` (country group · years · languages) on every acquire, the baseline's included (D8); the other kinds are stored for tasks 2–3 |
| `your_context[]` | `{text verbatim, type: present_fact \| commitment, turn_index, test_as_condition}` | — | stored; read by task 3 |
| `entry_branch` | `explore` (only value in this slice) | — | — |
| `linked_task_ids[]` | from `task_link` | — | plan "Starts from" |
| `steering_mode`, `steer_point_defaults` | as ES, not asked; the scoping default is moderate ("At the key decisions"), editable in the plan and in words; `baseline_confirm` accepts a standing default only under unattended (D11) | — | as ES |
| `steps[]` | Baseline · Longlist · Shortlist and assessment, each with one plain sentence | — | display; only Baseline runs here |
| `time_band` | coarse compute band for the baseline, "then a check-in" | — | display |
| `source_turn_index` | as ES | — | as ES |

Per-field turn provenance beyond `your_context` and `source_turn_index` is not
built in this slice (the ES plan does not carry it either) — a deferred seam,
recorded in `docs/deferred.md`.

## Baseline

**Shape (owner ruling 2026-09-09, option 2 of three):** eight required
sections — what is in place · trend if nothing changes · who is affected ·
what is already changing · what is contested · cost of inaction · key
assumption · sources — **plus up to two problem-specific sections the writer
proposes**, labelled and placed after "what is contested" (a regional problem
may want "how this varies by place"; a regulatory one "what the law currently
requires"). Owner's reason: a fixed list may miss what a domain needs, while
the eight are questions any status quo can answer. The two sections the gate
quotes, the key assumption and who is affected, are always present.

**One shape at both depths** (owner ruling 2026-09-09, revising decision
E12's rapid subset): dropping two sections saves about 95 s of a roughly
380 s sequential write (measured proxy, check 5) against a retrieval spine of
about 4.6 min that does not change with depth — not a difference a user
feels, so the section count is not the latency lever.

**Latency (D7).** The owner's expectation is a whole rapid path of about 15 to
20 minutes, so a baseline near 10 minutes is too long for its first step. The
levers in this slice:

- a small acquisition target for the baseline (a narrow question about the
  status quo, not a broad search) — a plan-time number, measured;
- a per-section tool-call cap in the template;
- the **writing mode**, chosen from a build-time trial: sequential (as the ES
  writes today) against parallel sections with a **join step** that writes
  the "at a glance" strip last and repairs any statement that conflicts with
  another section, in the section where it sits (genuine disagreement between
  sources belongs in "what is contested" and nowhere else; no
  labelled-disagreement device). The trial runs on the NEET question and one
  thin-evidence question; compute time and a side-by-side consistency
  reading go in `verification.md`; the owner picks at step 6; **the losing
  mode is deleted before the PR**.

Design target: about 3 to 4 minutes of compute, verified on the NEET question
during the build, never a run-time cut-off; the plan shows a coarse band and
promises no number (open question 3 stays open). Levers recorded for later in
`docs/deferred.md`: showing sections as they finish; starting the longlist's
retrieval while the user reads the baseline (task 2); a faster model tier for
the baseline sections when Bedrock lands, quality-tested first.

Rules the template carries: empirical premises cited to sources; the key
assumption and what is contested are tier-4 reasoning claims labelled as such;
"not found" is a content state, never a hedge; Policy Atlas does not forecast;
the coverage statement (in Sources) names Overton and OpenAlex as searched and
live official statistics and departmental pages as not searched; the
grey-literature skew is shown, not hidden.

## Surface map

Rows marked **keep** must not change behaviour. File paths are as built at
`7e31c373`; deliverable 2 renames some of them (new names in the row).

| # | Surface | Today | After this slice | Where |
|---|---|---|---|---|
| 1 | `task` row | no kind | `capability` text, check constraint, default `evidence_search` | `backend/src/policy_atlas/core/schema.py` (task); new alembic revision after `c1a7f4e9b0d2` |
| 1 | `capability_run.capability` | `evidence_search` only | + `options_scoping` | `schema.py` `ck_capr_capability`; `runtime/runner.py` `_open_capability_run` literal |
| 1 | Tasks list row | label from a key the API does not send | label from `TaskOut.capability`; depth chip for scoping | `frontend/src/views/TaskListRow.tsx`, `lib/capabilities.ts` (key `options_scoping`, D5) |
| 2 | Conversation kind | `planning` \| `chat` | `task_agent` \| `chat`; stored values rewritten | `schema.py` (conversation), migration, `api/contract/conversations.py`, readers |
| 2 | Transcript table | `planning_transcript` | `task_agent_transcript` | `schema.py`, migration, `runtime/agent.py`, `api/routers/planning.py` |
| 2 | Turn routes | `/tasks/{id}/planning-turns` | `/tasks/{id}/task-agent-turns`; models `TaskAgentTurn*`; no redirect | `api/routers/planning.py` (renamed), `api/contract/planning.py`, `frontend/src/api/*`, `web-api.md` |
| 2 | Frontend pane | `PlanningPane` and friends | `TaskAgentPane` and friends | `frontend/src/views/workspace/PlanningPane.tsx` and its tests |
| 2 | ES Task Agent code names | `runtime/planner.py`, `planner_prompt.py`, `PlannerBackend`, `POLICY_ATLAS_PLANNER_MODEL` | `runtime/task_agent.py`, `task_agent_prompt.py`, `TaskAgentBackend`, `POLICY_ATLAS_TASK_AGENT_MODEL`; version string `planner_v1` unchanged | those modules, their tests, `scripts/prompt_hashes.json` (path), `infra/DEPLOYMENT.md`, the staging environment value |
| 2 | Abbreviation EB | "EB" in living specs, skills, templates, agentic-ops, code comments | "ES" | `docs/specs/**` except `sources/`; `AGENTS.md`; `.claude/skills/`; `docs/tasks/_templates/`; `docs/agentic-ops/`; five backend modules' comments. ADRs, merged task docs, past log entries and frozen sources untouched |
| 3 | New task screen | capability cards; scoping card `available: false` | scoping card selectable; scoping form: question · Starts from (no depth or job control) | `frontend/src/views/NewTaskView.tsx`, `api/mutations.ts` `useCreateTask` |
| 3 | `POST /tasks` | name, question | + `capability`, `from_task_ids[]` (additive) | `api/routers/tasks.py`, `api/contract/tasks.py` |
| 4 | `task_link` | does not exist | new table (no option id, D13) | `schema.py`, migration; API read on the plan and the tasks list |
| 4 | inherit | does not exist | task-1 part: pinned runs; linked plan, report body without citations, coverage statement as Task Agent context | new module under `backend/src/policy_atlas/runtime/` (name at plan time); read models in `api/readmodels/repository.py` |
| 5 | `plan` payload | `TaskPlan` only | `TaskPlan` or the scoping plan, chosen by `task.capability`; plan read/patch bodies gain `capability` | `runtime/task_plan.py`, `api/routers/planning.py`, `api/contract/planning.py` |
| 5 | Plan document | ES sections | scoping sections (§ Plan object) | `frontend/src/views/workspace/PlanDocument.tsx`, `planVocabulary.ts`, `planStart.ts` |
| 6 | Task Agent prompt | one prompt, `planner_v1` | prompt chosen by capability; new `task_agent_scoping_v1` offering the two depths as options | `runtime/task_agent.py` (renamed), new `runtime/task_agent_scoping_prompt.py`; `scripts/prompt_hashes.json` |
| 7 | Chain compile | `compose(TaskPlan)` | `compose` for the scoping plan → spine + synthesise(baseline) | `runtime/task_plan.py` `compose`, `runtime/run_spec.py` |
| 7 | synthesise | intent-led sections | + template mode: required section list, optional proposed sections, per-section instruction and tool cap, not-found state, the chosen writing mode | `evidence_search/synthesis/synthesise.py`, `synthesis_backend.py`; new `synthesis/baseline_prompt.py` |
| 7 | `evidence_scope` | intent + context | + `purpose` (baseline \| longlist \| variant \| targeted; nullable) + `plan_version` (nullable) | `schema.py`, migration |
| 8 | Steering lattice | five points | + `baseline_confirm` after synthesise; `always` in attended modes, standing default in unattended, for scoping walks | `runtime/steering.py` `LATTICE_POINTS`, `runtime/task_plan.py` `STEER_POINTS`, `api/checkin_read.py`, `api/stage_vocabulary.py` |
| 8 | Task Agent turn at a pause | 409 `run_active` | accepted while the walk is **paused**; sorted (question · instruction · decision) and routed; still 409 while **running** | `api/routers/planning.py` (renamed), `runtime/agent_backend.py` (triage), `api/continuation.py` (`compile_free_text`, `answer_check_in`), the chat answer path |
| 8 | Check-in card | ES renders | baseline card: key assumption + Settings + two options, in the Task Agent thread | `frontend/src/views/workspace/CheckInCard.tsx`, `checkInPresentation.ts` |
| 9 | Result tab | ES artefact | baseline artefact with the band and run state | `frontend/src/views/ArtefactView.tsx`, `views/lifecycle.ts` `openTabs` |
| 9 | Sources tab | **keep** | unchanged; shows the baseline's documents | `frontend/src/views/Sources*.tsx` |
| 9 | Share, History tabs | **keep** | unchanged | `ShareView.tsx`, `HistoryView.tsx` |
| — | ES planner prompt, ES walk, ES Result | **keep** | word-for-word unchanged (`planner_v1` hash unchanged); the ES chain composes as before; ES pauses keep their card-based steering | `runtime/planner_prompt.py`, `runner.py`, `harness.py` |
| — | Generated | via `make openapi-sync` only | OpenAPI diff: additive except the deliverable-2 path rename | `frontend/openapi.json`, `frontend/src/api/gen/types.ts` |

## Decisions (ruled by the owner, 2026-09-09)

- **D1 — one plan table, two payload shapes. Accepted.** The scoping plan is a
  second Pydantic model stored in the same `plan` table and lineage; the
  task's capability decides which model validates the payload. *Rejected:* a
  second table (mirrors the ES plan machinery); one union model (forces ES
  fields onto scoping and vice versa).
- **D2 — capability on the task, not inferred from runs. Accepted.**
  Written at creation and never changed; turning one task into another is
  what a Link is for.
- **D3 — a capability switch. Dropped (owner).** The feature branch is the
  switch: `feat/options-scoping` merges into `dev` only when the capability
  is ready for users, and production deploys from `dev`. No setting, no
  `/me` change. Consequence: staging sees the capability only when the
  feature branch merges to `dev` or is deployed there directly; this slice's
  live check runs locally.
- **D4 — inherit lands in two parts. Accepted, widened (owner).** Task 1: the
  Link, the pinned source run ids, and the Task Agent's context — the linked
  task's whole plan, its report body with citation markers and the reference
  list removed, and its coverage statement, each fenced once after the system
  instructions and rehydrated every turn (the planner has no memory between
  turns; the stable position lets the provider's prompt cache serve it). No
  size cap (owner: the reports are nowhere near long enough). The planner
  proposes from them and never re-summarises them into the plan's own text.
  Several linked tasks: one fenced document each; the user's own ask stays
  primary (A6). Not pulled: extracted findings (task 3), steering history,
  chat transcripts (never). Task 2: the document rows and the longlist
  suggestions, created when the longlist scope re-screens them.
- **D5 — key `options_scoping`, label "Options scoping". Accepted.**
- **D6 — depth offers rapid and standard. Amended (owner): deep is not shown
  at all** on the New task screen, in the plan document or in the planner's
  offer until scoping deep exists. Deferred seam.
- **D7 — the baseline's depth grading. Replaced (owner):** one shape at both
  depths (§ Baseline); the writing mode chosen from a build-time trial with
  the loser deleted; a small acquisition target and a per-section cap; a
  measured target aimed at 3 to 4 minutes; later levers recorded.
- **D8 — evidence restrictions apply to the baseline's acquire. Accepted
  (owner: "for simplicity … a user who applied a restriction at planning time
  would expect it applied throughout the task").** Plus the planner warns
  before confirmation when a restriction would exclude the plan's Where.
- **D9 — the gate is answered in the Task Agent chat. Re-shaped (owner):**
  the Task Agent thread is open at the gate; a turn is sorted by a mini-class
  triage call into question · instruction · decision and routed to the
  grounded chat answer, the steering router (compile → confirm → new plan
  version) or the check-in option. A turn while the walk is *running* stays
  409 `run_active`. Routing hangs on the turn, not the conversation kind, so
  a later slice can let ordinary chats carry the same turns (owner's
  direction: any chat should eventually plan, edit artefacts and answer with
  citations). The Evidence search keeps its card-based steering in this
  slice; the owner's view that the Task Agent chat should be the surface a
  task is controlled from is recorded in `docs/deferred.md` as the direction
  for a later Evidence search slice. **Rider:** the `planning` → `task_agent`
  rename is done now, as the fenced first phase (deliverable 2); `task_agent`
  and not `agent`, because "agent" already means the Agent tab and the 038
  persona. Triage and router latency are measured in the build and recorded.
- **D10 — "Search further" at the gate. Deferred (owner).** The gate offers
  Confirm and Change the plan; a request in words is refused honestly as not
  yet available. Recorded for task 2 or later.
- **D11 — the gates and the steering mode. Amended (owner):** "allow the user
  to have an unattended mode where it goes all the way to the assessed
  shortlist and report without input, however this shouldn't be the
  default." The two structural gates pause in every attended mode; in
  unattended they pass on standing defaults, recorded as
  `decided_by: standing_default` and flagged in the end-of-run review;
  unattended is never the default. Task 3 inherits this for "Assess these N".
- **D12 — after Confirm the walk ends. Accepted.** The decision is a steering
  event; the plan version is unchanged unless the user changed it; the Result
  shows the confirmed baseline and says the longlist arrives with the next
  stage.
- **D13 — the option id column on `task_link` lands in task 2. Accepted.**

### Second-round amendments (owner, 2026-09-09, after the interview)

1. **EB → ES** in the contract, and the living specs swept in the rename
   phase (deliverable 2).
2. **Parity with the ES conversation:** no depth or job control on the New
   task form; depth offered as options in the Task Agent conversation;
   steering mode not asked, carried as an editable plan setting. Fact
   recorded for the owner: the ES prompt's own default is unattended
   ("check-ins are requested, not offered") while the execution contract
   names moderate — an existing ES inconsistency, out of this slice. The
   scoping default is moderate (D11).
3. **"Task Agent for a scoping task", not "scoping planner"**; prompt
   surface `task_agent_scoping_v1`; the ES `planner` module, class and
   environment-variable names renamed in the rename phase, version string
   kept.
4. **`evidence_scope.purpose`**, not `role`.
5. Terms row for the agent persona rewritten: one actor, one thread.
6. `intended_change` / "what we are trying to change" kept (an "intended
   outcome" field would collide with `outcomes[]`).
7. The constraint kinds are **requirement · preference · evidence
   restriction** (owner: "sounds good"); the specs' "scope-shaped" and
   "effect- or cost-shaped" stay as the older wording in Terms.

## Spec changes (owner rulings applied with this contract)

Applied to the specs with the owner's words quoted and a line in
`docs/specs/log.md`; sources stay frozen (ADR 0002):

1. OS capability § Output structure (baseline profile) and OS components § 11:
   eight required sections plus up to two writer-proposed sections.
2. plan-as-object § Thoroughness and OS capability § Depths: the baseline is
   not graded by depth (revises E12's baseline part); one measured target;
   the latency levers.
3. OS capability § Pipeline and gates and § Check-in points: the structural
   gates pass on standing defaults in unattended mode; unattended is never
   the default.
4. vocabulary.md: the Task Agent's code names after deliverable 2.
5. EB → ES across the living specs, in the rename phase (deliverable 2); the
   spec log gets one line when it lands.

## Scope / Out of scope

- **In:** the surface-map rows above; the migration; ADR 0037; the spec
  changes above; tests (§ Acceptance checks); `verification.md`;
  `docs/deferred.md` deltas.
- **Out:** the longlist and everything after the gate (tasks 2–3); the
  sense-check branch (task 4; shown as not available); Sources tab
  additions and export (task 4); the full run and the reverse inherit
  direction (task 5); document rows for inherited documents (task 2, D4);
  per-field turn provenance beyond Your context; "Search further" (D10); any
  change to the ES planner prompt text, the ES chain, the ES Result or the
  ES's card-based steering; deep depth; setting as a mandatory slot; any
  prompt edit to `screen`, `classify`, `appraise`; corpus-level document
  identity (#75); a capability switch (D3).

## Constraints & approval gates

Hard gates this slice touches — approval is this contract's sign-off:

- **Schema / data model:** `task.capability`; `task_link`;
  `evidence_scope.purpose`, `evidence_scope.plan_version`; widened
  `ck_capr_capability`; the deliverable-2 renames (conversation kind values,
  `planning_transcript` → `task_agent_transcript`). One migration, reversible
  (§ Rollback in ADR 0037), values reversed on downgrade.
- **Runtime egress:** a new walk kind reaches Overton, OpenAlex and the
  inference route with task data. Same backends, same transport, same
  `search` verb; no new host. Two new judgment-class call sites at the gate
  (triage, router) reuse the existing agent backend.
- **Public interface:** `capability` and `from_task_ids` on task create/read;
  `capability` on plan read/patch bodies with the scoping fields; check-in
  kind `baseline_confirm`; the path rename `/planning-turns` →
  `/task-agent-turns` with no redirect (the one non-additive change, the 038
  pattern; the frontend is the only consumer). Everything else additive.
- **Prompts:** two new surfaces (`task_agent_scoping_v1`, the baseline
  template); re-pin with `python3 scripts/prompt_hash_guard.py --update`.
  The ES Task Agent prompt's version string `planner_v1` and text are
  unchanged; its hash entry moves with the renamed file (a words-only diff
  under 038 rule R1 if identifiers inside the file change). Every other
  pinned hash unchanged. The router and triage prompts are reused unchanged.
- **Production config:** one environment-variable rename,
  `POLICY_ATLAS_PLANNER_MODEL` → `POLICY_ATLAS_TASK_AGENT_MODEL`, in
  `infra/DEPLOYMENT.md` and the staging environment (approved with this
  contract; the deploy-side value change is the owner's at merge time; the
  code default is unchanged, so a missing value behaves as today).
  **Dependencies, CI, auth:** none. Tenancy (ADR
  0033) and public read (ADR 0035) predicates are untouched; a scoping task
  reads and shares like any task.
- Generated files change only via `make openapi-sync`; `make drift-check`
  green.

## Public / private boundary

Contract, rubric, plan, ADR and `verification.md` are public-safe. Live-check
evidence: screenshots of the plan and baseline on the NEET question are
public-safe (the question is the design reference); raw acquired text, traces
and credentials stay private. Recorded provider fixtures follow the sanitized
fixtures policy. The writing-mode trial's sample baselines are public-safe
once their source quotes are checked against the fixtures policy.

## Model route

OpenAI under the approved controls, behind the existing routing seam (the
Bedrock migration is untouched). Prompt-bearing, lead-authored:

- `task_agent_scoping_v1` — the Task Agent for a scoping task (deliverable 6).
- The baseline template — required and proposed sections, per-section
  instructions and caps, the reasoning labels, the not-found rule, the join
  step if parallel writing ships (deliverable 7).

Reused unchanged: screen, classify, appraise, the synthesise section writer
and grounding judge, the steering router and triage, the chat answer path.
The intent record's text is compiled deterministically from the plan, not
written by a model.

## Disciplines binding this slice

- **Don't flatten status.** ❓ open question 3 (rapid latency) stays open: the
  plan shows a coarse band and promises no number. Deep stays ⏸.
- **Model only what behaves.** `evidence_scope.purpose` is read by the run opener
  and the Sources header; `task_link.option_id` waits for task 2 (D13).
- **Honest absence.** Every baseline section may read "not found"; the
  coverage statement names what was not searched.
- **Flag, don't drop.** Below-policy sources are flagged per plan-as-object.
- **Substance is never silent.** An unattended pass through the gate is
  recorded and flagged (D11).
- **Generation is free, interpretation is labelled, assessment is grounded**
  (OS trust). The baseline asserts nothing about options.
- **No code bloat (owner).** The writing-mode trial ships one mode; the other
  is deleted, with the samples kept in `verification.md`.
- Deferred seams go to [docs/deferred.md](../../deferred.md): per-field turn
  provenance; Search further; inherited document rows (task 2 pointer);
  `task_link.option_id`; scoping deep; the later latency levers; the Task
  Agent as the Evidence search's control surface; any chat carrying Task
  Agent turns.

## Stop conditions

Halt and escalate when: a gate above needs more than this sign-off (a new
host, a second non-additive API change, a second migration); the router or
the chat answer path cannot be called from a Task Agent turn at a pause
without changing the Evidence search's behaviour; the baseline cannot reach
a compute time the owner will accept without cutting a required section
(report the measurement, do not cut); scope would grow into task 2; or the
turn/token budget is spent.

## Acceptance checks

- `make verify` green (okf-validate · test · typecheck · lint · build ·
  drift-check · prompt-guard).
- **Deterministic tests** (backend unless stated):
  - migration round-trip: upgrade, downgrade, upgrade; existing tasks read
    `evidence_search`; `ck_capr_capability` accepts both values; stored
    conversation kinds read `task_agent` after upgrade and `planning` after
    downgrade; the downgrade refuses while an `options_scoping` task exists.
  - rename: no reference to `planning_transcript`, `/planning-turns`,
    `PlanningTurn`, `PlannerBackend`, `planner_prompt` or
    `POLICY_ATLAS_PLANNER_MODEL` remains in `backend/src`, `frontend/src`,
    `infra/DEPLOYMENT.md` or `web-api.md` (a sweep test in the 038 style);
    the old path is 404; the version string `planner_v1` is still emitted.
    The EB → ES sweep is checked once by grep and recorded in
    `verification.md`, not as a permanent test.
  - `task_link`: source ≠ target; unique pair; same-project rule (409);
    archive of a task with inbound links keeps the row; a link grants no read
    (an org-scoped read test in the ADR 0033 style).
  - inherit context: the fenced documents carry the linked plan, the report
    body with no citation markers and no reference list, and the coverage
    statement; one block per linked task; stable position after the system
    instructions across turns.
  - scoping plan validation: not ready without depth; deep rejected; `where`
    defaults to United Kingdom tagged assumed; constraint kinds and
    `checked_at` closed; Your context entries keep verbatim text and turn
    index; an ES task rejects a scoping payload and the reverse; the default
    steering mode is moderate and is never asked.
  - compile: the scoping plan composes acquire → screen → classify →
    appraise → ingest → synthesise(baseline) and nothing else; the intent
    record carries `purpose=baseline` and the plan version; evidence
    restrictions land on acquire as `ScopeConstraints`.
  - template: the eight required sections are always present at both depths;
    at most two proposed sections, placed after "what is contested"; a
    section with no support renders the not-found state; the key assumption
    and what is contested carry the tier-4 label; if parallel ships, the join
    step's repair changes a conflicting section and never emits a
    disagreement label.
  - gate: `baseline_confirm` pauses under frequent, moderate and minimal;
    under unattended it records `decided_by: standing_default` and a flag and
    continues; the card carries the two options; Confirm ends the walk
    `succeeded` with a decision event; Change the plan writes a new plan
    version and keeps the walk paused.
  - gate turns: a Task Agent turn while paused is accepted and sorted; a
    question produces a grounded answer citing baseline sources; an
    instruction produces compiled deltas and a confirm token and applies only
    on confirm; a turn while running is 409 `run_active`; an ES task's
    pause still refuses turns (ES unchanged).
  - ES regression: `planner_v1` hash unchanged; `compose(TaskPlan)` output
    unchanged (existing tests); ES steering tests unchanged.
  - frontend (vitest): New task form states (question and Starts from only,
    Starts from restricted to same-project Evidence search tasks; no depth
    or job control); plan document
    renders every scoping section; tasks list shows kind and depth; the Task
    Agent thread renders a gate question, an instruction's confirm render and
    the check-in card with two options; Result shows the band and run state.
- **No AI eval in this slice.** Baseline quality is judge behaviour and goes
  to the eval slice. `verification.md` records the writing-mode trial (two
  questions, both modes, compute times, consistency reading) and three live
  baselines (NEET; one thin-evidence structural question; one linked start)
  read against the trust rules as a qualitative note, not a pass/fail gate.
- **Live check (pinned scope, ~25 minutes):** local app, real egress.
  (a) Seed one Evidence search task on NEET with a completed report.
  (b) New task → Options scoping → question · Starts from the seeded task →
  Prepare plan. (c) Three Task Agent turns: it proposes from the linked plan
  and report, asks who should change, offers the two depths as options and
  the user picks standard; "OECD evidence only" gets the kind question; the plan shows
  Starts from, the constraints table, Your context, the steps. (d) Confirm
  and build baseline: the walk runs, Result opens on the baseline with the
  band, Sources lists the documents with the coverage statement; compute
  time recorded. (e) In the same thread: one question about the baseline
  answered with citations; one instruction ("change Where to England")
  compiled, confirmed, new plan version, still paused. (f) Confirm → History
  shows the decision; the Result says the longlist arrives with the next
  stage. (g) ES smoke: New task → Evidence search → two Task Agent turns →
  an approved plan (no run; the shared turn path is what this slice
  touches; the ES walk is covered by tests). No full ES live e2e.

## Verification evidence expected

Command tails; the migration round-trip output; the rename sweep result; the
OpenAPI diff (additive except the path rename); the prompt-hash diff (two new
entries, none changed); the writing-mode trial record and the owner's pick;
measured triage and router latency at the gate; live-check notes and
screenshots for (a)–(g); the three baselines' qualitative note; the spec
diffs with quoted rulings; the `docs/deferred.md` delta; known gaps.

## Risk tier & review focus

**Tier 4** — migration with value rewrites, runtime egress for a new walk
kind, a public API path change, two prompt surfaces: ADR 0037 with a rollback
plan, human-approved plan, adversarial review at the contract and plan stages
(`codex-rescue`, read-only briefs), the step-7 stack per the spine (contract
verifier · `/code-review medium` · one security lane scoped to the new
endpoints, the gate turn routing and `task_link` · `/simplify` · human deep
review). The rename phase gets its own review pass before feature code lands.

Rollback shape (ADR 0037 names the commands): quiesce the API; `alembic
downgrade -1` refuses while any `options_scoping` task exists (the operator
archives them first) and otherwise drops `task_link`, the two `evidence_scope`
columns and `task.capability`, narrows `ck_capr_capability`, and reverses the
rename (table and stored kind values); deploy the previous image.

Review focus: the ES planner prompt, chain and steering byte-for-byte
unchanged; the rename diff contains nothing but the rename; the gate passes
only in unattended and always records and flags (D11); no scoping payload
validates on an ES task or the reverse (D1); a link never widens access (A6);
a gate turn never applies an unconfirmed delta and never lands a plan under a
running walk; the baseline asserts nothing about options and labels its two
reasoning sections; the not-found state is a content state, not a hedge; the
losing writing mode is gone; the additive-only OpenAPI diff outside the
rename; `where` never silently stays empty.
