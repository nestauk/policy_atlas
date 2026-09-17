# Task contract: 044-scoping-shell-baseline

One implementation slice: the first of the five options-scoping build tasks
(PR #69 "Task 1 — the task shell and the baseline"). It lands the second task
kind, its plan and Task Agent chat, the link to an existing Evidence search,
the "do nothing" baseline, and the gate where the user confirms the plan
against the baseline before any option is generated.

> **Status:** **approved 2026-09-09 · owner** (decisions D1–D13 ruled one by
> one in an interview the same day, plus seven second-round amendments;
> rulings folded in below and quoted where they change a spec).
> **Contract-stage adversarial review ran 2026-09-09** (fallback lane,
> `deep-reasoner`, read-only, after the first Codex lane stalled; then the
> relaunched Codex lane, read-only, on the pre-fold commit): 18 + 18
> findings, both verdicts "material change needed", all accepted and folded
> (§ Adversarial findings; seven Codex findings restate fallback ones).
> The three Codex proposals were ruled 2026-09-09 (C1: after a plan change
> the user chooses rebuild or go on; C6: sequential writing, with a
> development-time feasibility check against a parallel version; C16: not
> built, spec revised to version grain) and the tasks-list depth chip was
> dropped. **Re-approved as folded 2026-09-09 · owner.** The material folds — the
> lattice gains a capability dimension (A2), the steering router is modified
> not reused (A3), a third prompt surface for the gate sort (A4), the gate
> built on the existing check-in response path (A12), the rollback predicate
> (A5), the complete rename list (A10), `evidence_scope.plan_id` (A16) —
> reopened the 🛑 and were re-approved.
> Plan approved (before implementation): _pending_ ·
> ADR: **[0037](../../adr/0037-options-scoping-task-kind-links-and-baseline-gate.md)**
> — Accepted 2026-09-09 (task kind, links, registry, the baseline gate, the
> end-walk disposition, the Task Agent rename, two revisions, rollback).
> **Plan approved 2026-09-09 · owner.** Design phase closed; the build runs in
> a fresh conversation with `task-cycle-build`.
>
> **Branching:** `task/044-scoping-shell-baseline` from `feat/options-scoping`
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
   list and the task header say "Options scoping" (D5). The tasks list shows
   no depth (owner, 2026-09-09: "we don't need depth in the tasks list";
   C17 dropped).
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
   string `planner_v11` stays** (its current value — A1) — it is a stored
   provenance value (038 rule R1); the pinned hash entry moves with the file
   and is re-pinned as a words-only diff. The rename is complete or it is
   not done (A10): it also takes the constraint and index names that carry
   the word (`ck_conversation_planning_never_archived`,
   `uq_conversation_one_active_planning`, the transcript's `uq_ptr_*` /
   `ck_ptr_*`), the transcript column `planner_state` → `task_agent_state`,
   the stored attribution value `plan.created_by = 'planner'` →
   `'task_agent'` (rewritten in the migration, reversed on downgrade, like
   the conversation kind), the wire role literal `"planner"` in transcript
   rehydration, and every frontend consumer (`src/api/*`, `src/mock/*`,
   `src/store/transcript.ts`, `src/views/workspace/**`, the e2e specs —
   about 25 files). **Kept as they are**, because they are stored
   fingerprints or legacy ids with read-side compatibility, never rewritten:
   `eb_iof_base_v1`, `eb_icf_base_v1`, the legacy steer-point id
   `evidence_base_coverage`. The plan phase produces a **rename manifest**
   like 038's (C13): the schema names from the catalog, and a repository
   token and path list covering `backend/src`, `backend/tests`,
   `frontend/src`, `frontend/e2e`, mocks, scripts, generated outputs and the
   content of `docs/knowledge/` (its filenames are concept ids and are never
   renamed), with the exclusions stated. The same phase sweeps the abbreviation **EB → ES** in
   the living specs (`docs/specs/**` except `sources/`), `AGENTS.md`, the
   skills and templates, `docs/agentic-ops/`, and code comments and
   docstrings. **Excluded, by path and by token** (A11): `docs/adr/**`,
   merged task docs under `docs/tasks/`, `docs/specs/log.md` (past entries
   are history), `docs/specs/sources/**` (frozen), any verbatim owner
   quotation inside a living spec, and the three literals above. First commit on the branch, reviewed
   as its own diff before any feature code lands (D9 rider). *Why now
   (owner):* "planning turn" named one job of a thread that now carries
   questions, instructions and decisions; "if we're doing an initial rename
   phase in this task, then might as well do this rename too".
3. **Start a scoping task.** The New task screen, with the same shape as the
   Evidence search's: the question and one scoping-specific control, **Starts
   from** — zero or more Evidence search tasks in the same project (links
   must exist before the first turn). Today the frontend creates the task,
   then patches its projects, then posts the first turn (C10); this slice
   makes `POST /tasks` take `project_ids` and `from_task_ids` in **one
   transaction**, so the same-project rule is checked when the link is
   written and a failed request leaves no half-made task. No depth control and no job control on
   the form (owner, second round: parity with ES, where depth is agreed in
   the conversation): depth is offered in the Task Agent conversation
   (deliverable 6); the scoping job (explore · sense-check) is not shown until
   sense-check exists (task 4 decides where it lives). Prepare plan → the
   Agent tab.
4. **Link and inherit.** Each "starts from" choice is a `task_link` row:
   many-to-many, same-project only, archive-not-delete, changes no access.
   The pinned source run is the source task's **`capability_run_id`** (C11):
   one walk, from which its plan version and component runs resolve; only a
   `succeeded` or `degraded` walk is eligible; one row per (source, target)
   pair; a link whose tasks stop sharing a project is flagged on read, never
   deleted (C12). `inherit` (task-1 part, D4) pins that run on the link and gives
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
   check-ins. One start action before the first baseline: **Confirm and
   build baseline**, with a coarse time band. After a plan change at the gate
   (deliverable 8) the document offers two: **Rebuild baseline** and
   **Confirm plan and build longlist** (owner ruling on C1, 2026-09-09: "the
   user should have the choice of whether they want to build another
   baseline after changing the plan or just go to the longlist").
6. **The Task Agent for a scoping task** (not a "planner": the thread carries
   through to the gate). Prompt surface `task_agent_scoping_v1` in
   `runtime/task_agent_scoping_prompt.py`, lead-authored, hash-pinned. It
   fills the plan from the question and the linked tasks, tags each field
   *from your question* / *assumed* / *your call*, asks who or what should
   change when the question leaves it open, defaults Where to the United
   Kingdom (assumed, please check), offers setting as an optional
   constraint, gives every plan section its **Edit** action as the ES plan
   has (C18), asks which kind a constraint sentence is when it is ambiguous
   ("limit the evidence I read, or the options you would consider?"), and
   says so before confirmation when an evidence restriction would exclude the
   plan's Where (D8). **Depth** is offered the way ES offers it: two labelled
   options in the conversation, every time, no default (ruling 25); the plan
   is not ready until one is chosen. The screen words follow the ES's
   pattern ("Rapid overview" / "Standard report" there; the scoping labels
   and subs are lead-authored in the prompt) and **never the internal keys**
   (A8); the internal key is one axis, `depth ∈ rapid | standard` — scoping
   has one dial (ruling 25), not the ES's effort × analysis pairing. **Steering mode** is not asked, as ES does not
   ask: the plan carries it as an editable setting, default "At the key
   decisions" (D11), and the user changes it in their own words.
7. **Baseline run.** Confirming the plan runs one walk: acquire (Overton and
   OpenAlex, a small acquisition target — D7) → screen (title and abstract;
   the plan compiled to carry target unit and Where) → classify → appraise →
   ingest → synthesise with the **baseline template** (§ Baseline). Its own
   intent record (purpose `baseline`, pointing at the plan version that
   created it — A16). Each empirical premise is sourced; the key assumption
   and what is contested are labelled reasoning; "not found" is a content
   state. The baseline's substrate carries **chunk, reasoning and gap claims
   only** (A7): no characterise, extract or group runs, so no pattern or
   theme claims and no coverage-denominator corpus claims appear in a
   baseline. Its own **Sources section** (required section 8) states what
   was searched and that live official statistics and departmental pages
   were not (A14); the Sources tab stays unchanged. Evidence restrictions
   apply to this acquire like any other (D8). The **baseline mode** of
   synthesise (C7) supplies the eight sections, admits zero to two validated
   proposals, carries a per-section instruction and turn cap on the section
   spec, orders the sections, renders the not-found state, and **disables
   the ES-only passes** — the injected Conclusions section, the key-findings
   pass and the case-study pass. The baseline carries the **`scoping pass`**
   depth label like every scoping profile (C18).
8. **The gate.** The walk pauses after the baseline in every attended
   steering mode; in unattended it does not pause: the runner writes the
   decision event at the boundary — `decided_by: standing_default`, flagged
   for the end-of-run review — and continues (A9). Choosing unattended makes
   the Task Agent write the standing default for this point into the plan as
   visible content ("confirm the plan against the baseline as it stands"), so
   an undeclared default cannot occur here (D11). **The Task Agent chat is
   open at the gate** (D9), built on what exists (A12): the thread's one
   composer posts to the Task Agent turn route; while the walk is paused the
   turn is admitted and **sorted** by a small lead-authored mini-class prompt
   (the third prompt surface, A4) into **question · decision** — a question
   goes to a **shared read-only answer core** (C2: the chat's grounded
   answer, lifted out of the chat-turn route so it can target the paused
   baseline's pinned scope; the chat route itself refuses paused walks and
   is unchanged), rendered in the thread with its citations; a decision in
   words goes to the check-in option response. The two decisions, **Confirm
   plan and build longlist** and **Change the plan**, are also options on
   the check-in card in the same thread; a decision from either surface
   lands in the **same check-in response transaction**, bound to the
   `capability_run_id`, the `check_in_id` and the plan version and
   re-validated under the task lock, so the second is 409 `already_answered`
   (A13, C5). **An instruction at the gate is the decision "Change the
   plan"** *(C1, ruled 2026-09-09)*: the existing
   steering path cannot take it, because at this gate every component has
   run and the stability rule refuses any change to a run component, and a
   change to Where or the outcomes would leave the baseline stale against
   the plan that did not produce it. So Change the plan **ends the walk**
   (decision recorded, walk `aborted` by the user's choice), the fence lifts
   because no walk is active, the instruction is applied as an ordinary Task
   Agent planning turn minting a new plan version, the baseline artefact
   stays visible marked *built from plan version N*, and the user chooses
   (owner ruling, C1): **Rebuild baseline** starts a new walk under the new
   version (a supersede-by-rerun; the new walk's intent record points at the
   new plan row, and so does `plan.evidence_scope_id` — C3), or **Confirm
   plan and build longlist** confirms the new plan against the existing
   baseline, the decision recording both versions (in this slice it records
   and ends; task 2 wires it to the longlist). The Task Agent says in the
   thread whether the change touched the baseline's inputs (question,
   intended change, target unit, Where, outcomes, evidence restriction) so
   the choice is informed. Rebuilding only the affected sections is open
   question 7 (deltas, not restarts), recorded in `docs/deferred.md`. The
   steering router is therefore **not used at the gate and not modified**
   (this retires fallback finding A3's modification). A turn that is a
   question and a decision at once is answered first and then asked to
   confirm the decision; a decision is never inferred. The **approving
   branch** of a Task Agent turn and `PATCH /plan` stay fenced while a walk
   is running or paused (A6). A turn while the walk is *running* stays 409
   `run_active`. The Task Agent turn's durable row and read model become a
   **discriminated projection** (C2): a planning reply, an answer with
   citations, or a decision. The card quotes the
   baseline's key assumption and the plan's Settings. Confirm records the
   decision and ends the walk (D12); the Result says the longlist arrives
   with the next stage. Routing hangs on the turn, not on the conversation
   kind, so a later slice can let any chat carry the same turns.
9. **Tabs and views.** Agent · Result · Sources · Share · History, the task's
   own. Result shows the baseline profile (an interim state: ruling 50 says
   the Result before assessment is the longlist, which does not exist until
   task 2 — A17) as linear text with a side outline
   and collapsible sections, under a band worded **the situation these
   options would change** and the run state (ready · awaiting your
   confirmation / plan confirmed). Sources is the Evidence search's Sources
   component over the baseline's documents, unchanged. Share and History
   unchanged.
10. **System records.** `task.capability`; `task_link`;
    `evidence_scope.purpose` and `evidence_scope.plan_id` (a foreign key to
    the plan version row, with the task guard — A16; `plan.evidence_scope_id`
    points at the baseline record for a scoping plan) (several intent
    records per plan, decision C4); the `baseline_confirm` steer point; the
    `options_scoping` capability on `capability_run`; the renamed
    conversation kind, transcript table and Task Agent module names (2). Declared once, in the ADR,
    for tasks 2–5 to build on.

## Deliverable

A PR on `task/044-scoping-shell-baseline` into `feat/options-scoping`: one
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
| **baseline** | The profile of "Do nothing": eight required sections at both depths, plus up to two the writer proposes at standard depth and none at rapid (§ Baseline, phase 8). The Result of this slice. |
| **the gate** | The pause after the baseline where the user confirms the plan. Steer point `baseline_confirm`; the first of the two structural gates (OS capability § Pipeline and gates). |
| **steer point** | A named pause on the steering lattice (`runtime/steering.py` `LATTICE_POINTS`). ES has five; this slice adds one and gives the lattice a **capability dimension** (A2): a point belongs to a capability's chain, so `baseline_confirm` never names an ES pause after synthesise. |
| **gate sort** | The mini-class prompt surface that sorts a Task Agent turn at a pause into question · decision (A4, C1); an instruction is the decision "Change the plan" carrying its text. Lead-authored, hash-pinned. Fails safe: an unsortable turn is asked back, never applied. The ES's boundary triage (`WatchTriageWire`, a notable-or-not verdict) is a different call and is reused unchanged. |
| **answer core** | The grounded read-only answer the chat produces over a task's artefact, lifted into a shared function so a Task Agent turn can call it against the paused baseline (C2). The chat-turn route keeps its own guards. |
| **capability registry** | One module that says, per capability, which plan model validates the payload, which chain composes, and which steer points exist (C9). Every reader of a plan goes through it. |
| **router** | The `agent_v1` moment that compiles a free-text instruction at a pause into plan deltas, each re-validated fail-closed and applied only after the user confirms (task 024). |
| **walk** | One run of a capability's chain: a `capability_run` row plus its component `runs`. |
| **depth** | The plan's one dial, internal key `rapid \| standard`; shown with screen labels in the ES's pattern, never the key (A8). Offered as options in the conversation, every time, no default (ruling 25). Deep is ⏸ later for scoping and is not shown (D6). |
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
| `depth` | rapid \| standard (D6), chosen from the Task Agent's offered options | *your call* | stored; tasks 2–3 read it; sets the baseline's acquisition target (20 · 10) and proposed-section allowance (two · none) (D7 as re-revised in phase 8) |
| `constraints[]` | `{text, kind, origin, checked_at}`; kind ∈ requirement \| preference \| evidence_restriction; checked_at ∈ longlist \| assessment \| retrieval | yes | evidence restrictions → the ES `ScopeConstraints` on every acquire, the baseline's included (D8) — **country group and publication years only**: the ES model has no language filter (C8), so a language restriction is stored, shown as *not yet applied at retrieval* and recorded as an ES gap; the other kinds are stored for tasks 2–3. Evidence restrictions sit in the plan's Constraints table, not in Settings — the placement the spec kept when it rejected "evidence restrictions as plan Settings" |
| `your_context[]` | `{text verbatim, type: present_fact \| commitment, turn_index, test_as_condition}` | — | stored; read by task 3 |
| `entry_branch` | `explore` (only value in this slice) | — | — |
| `linked_task_ids[]` | from `task_link` | — | plan "Starts from" |
| `steering_mode`, `steer_point_defaults` | as ES, not asked; the scoping default is moderate ("At the key decisions"), editable in the plan and in words; `baseline_confirm` accepts a standing default only under unattended (D11) | — | as ES |
| `steps[]` | Baseline · Longlist · Shortlist and assessment, each with one plain sentence | — | display; only Baseline runs here |
| `time_band` | coarse compute band for the baseline, "then a check-in" | — | display |
| `source_turn_index` | as ES | — | as ES |

**Turn provenance is at version grain** *(C16, owner ruling 2026-09-09:
"do we even really need that?" — no)*: nothing in the product reads a
per-field turn reference, the transcript is durable and ordered, and each plan
version records the turn that produced it (`source_turn_index`), so "when did
the user set X" is answerable between two versions. Per-field references are
not built; plan-as-object § Plan vs config is revised to version grain with
the ruling quoted (§ Spec changes). `your_context` entries keep their own
`turn_index` because the trust rules use it.

**Execution-bearing baseline parameters that are not plan fields** (C8) are
compile constants in the baseline template, named here so nothing hides: the
acquisition target per backend, the per-section turn cap, the proposed-section
limit (two), and the section order. ~~Depth does not change them in this
slice.~~ *Re-revised in phase 8 (owner ruling 2026-09-17, "Go with options 2
and 5, targets 20 and 10"): depth sets the acquisition target (20 · 10 per
backend) and the proposed-section allowance (two · none); the turn cap and
the section order stay constants. § Baseline and D7 carry the ruling; this
paragraph was folded at the review stack (verifier F2).*

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

**Re-revised in phase 8** (owner ruling 2026-09-17, task 044 phase 8: "Go with options 2 and 5, targets 20 and 10"), after the
three live baselines measured 389 s, 453 s and 259 s: depth sets two
execution values. **Standard** keeps the shape above, against an acquisition
target of 20 documents. **Rapid** writes the same eight sections, allows no
proposed sections, and acquires 10 documents. A five-section rapid merge (in
place + already changing; trend + cost of inaction) was built and measured
in this phase — 168 s and 189 s of writing against 183 s for the seven
sections, because the write turn is set by output tokens and a merged section
writes what two wrote — and reverted the same day (owner: "Revert the merge,
seven sections at both depths"). Classify runs 12 wide (the screen's width)
and ingest's parse workers follow the cores. A depth change counts as a
baseline input change (S4). Ruled out by the owner for this slice: wave or parallel
section writing, a writer model change, fewer screen replicates, a lower turn
cap or read window, and stage overlap; the writer-side levers are deferred to
a synthesis optimisation task (`docs/deferred.md` § Synthesis optimisation).

**Latency (D7).** The owner's expectation is a whole rapid path of about 15 to
20 minutes, so a baseline near 10 minutes is too long for its first step. The
levers in this slice:

- a small acquisition target for the baseline (a narrow question about the
  status quo, not a broad search) — a plan-time number, measured;
- a per-section tool-call cap in the template;
- **sequential writing, as the ES writes today** *(C6, owner ruling
  2026-09-09: "let's go with sequential, but we should also do some sort of
  test comparing it to a parallel version before finalising")*. The product
  ships one mode, sequential: the execution contract's durability section
  rules "never fan out the conclusion", the synthesiser writes sections in
  order over an accumulating claim ledger, and the owner's concern was
  consistency between sections. The comparison is a **feasibility check**,
  not product code: a script under `scripts/feasibility_checks/`, in the
  035 pattern, writes the same baseline sequentially and in parallel on the
  NEET question and one thin-evidence question, records compute time and a
  side-by-side consistency reading in `verification.md`, and nothing of it
  ships. A parallel mode in the product would then be an owner revision of
  the durability contract with a durable join design. Sections are **shown
  as they finish** so the user reads while the rest writes (perceived time,
  not compute) if the build finds it cheap; otherwise it stays on the
  deferred list.

Design target: as low as sequential writing over a small corpus allows,
measured on the NEET question during the build and reported honestly (the
3-to-4-minute aim assumed parallel writing and may not hold); never a run-time
cut-off; the plan shows a coarse band and promises no number (open question 3
stays open). Levers recorded for later in `docs/deferred.md`: starting the
longlist's retrieval while the user reads the baseline (task 2); a faster
model tier for the baseline sections when Bedrock lands, quality-tested
first; a parallel writing mode if the owner revises the durability contract.

Rules the template carries: empirical premises cited to sources (chunk
claims; the baseline has no pattern or theme claims — A7); the key assumption
and what is contested are tier-4 reasoning claims labelled as such; "not
found" is a content state, never a hedge; Policy Atlas does not forecast; the
baseline's Sources section names Overton and OpenAlex as searched and live
official statistics and departmental pages as not searched (A14); the
grey-literature skew is shown, not hidden, as a **visible source-tier skew**
line in the baseline's Sources section (C18). **Template mode** (A7, C7): the
required sections are supplied, not proposed; the ES section proposer runs
only for the up-to-two extra sections, bounded — if that needs a change to
its pinned prompt text, the change is versioned and re-pinned like any
prompt edit; the ES-only injected sections and passes are off.

## Surface map

Rows marked **keep** must not change behaviour. File paths are as built at
`7e31c373`; deliverable 2 renames some of them (new names in the row).

| # | Surface | Today | After this slice | Where |
|---|---|---|---|---|
| 1 | `task` row | no kind | `capability` text, check constraint, default `evidence_search` | `backend/src/policy_atlas/core/schema.py` (task); new alembic revision after `c1a7f4e9b0d2` |
| 1 | `capability_run.capability` | `evidence_search` only | + `options_scoping` | `schema.py` `ck_capr_capability`; `runtime/runner.py` `_open_capability_run` literal |
| 1 | Tasks list row | label from a key the API does not send | label from `TaskOut.capability`; no depth (owner) | `frontend/src/views/TaskListRow.tsx`, `lib/capabilities.ts` (key `options_scoping`, D5), `api/contract/tasks.py` |
| 2 | Conversation kind | `planning` \| `chat` | `task_agent` \| `chat`; stored values rewritten | `schema.py` (conversation), migration, `api/contract/conversations.py`, readers |
| 2 | Transcript table | `planning_transcript` | `task_agent_transcript` | `schema.py`, migration, `runtime/agent.py`, `api/routers/planning.py` |
| 2 | Turn routes | `/tasks/{id}/planning-turns` | `/tasks/{id}/task-agent-turns`; models `TaskAgentTurn*`; no redirect | `api/routers/planning.py` (renamed), `api/contract/planning.py`, `frontend/src/api/*`, `web-api.md` |
| 2 | Frontend pane | `PlanningPane` and friends | `TaskAgentPane` and friends | `frontend/src/views/workspace/PlanningPane.tsx` and its tests |
| 2 | ES Task Agent code names | `runtime/planner.py`, `planner_prompt.py`, `PlannerBackend`, `POLICY_ATLAS_PLANNER_MODEL`, `planner_state`, `created_by='planner'`, constraint names | `runtime/task_agent.py`, `task_agent_prompt.py`, `TaskAgentBackend`, `POLICY_ATLAS_TASK_AGENT_MODEL`, `task_agent_state`, `created_by='task_agent'`, renamed constraints; version string `planner_v11` unchanged | those modules, their tests, `schema.py`, migration, `scripts/prompt_hashes.json` (path), `infra/DEPLOYMENT.md`, the staging environment value |
| 2 | Abbreviation EB | "EB" in living specs, skills, templates, agentic-ops, code comments | "ES" | `docs/specs/**` except `sources/`; `AGENTS.md`; `.claude/skills/`; `docs/tasks/_templates/`; `docs/agentic-ops/`; five backend modules' comments. ADRs, merged task docs, past log entries and frozen sources untouched |
| 3 | New task screen | capability cards; scoping card keyed `scoping_policy_options`, `available: false`; `NewTaskView` hard-codes `capability === "evidence_search"` | card key renamed to `options_scoping` and selectable; the hard-coded check becomes a capability switch in the form; scoping form: question · Starts from (no depth or job control) | `frontend/src/views/NewTaskView.tsx`, `lib/capabilities.ts`, `api/mutations.ts` `useCreateTask` |
| 3 | `POST /tasks` | name, question; projects patched afterwards by the frontend | + `capability`, `project_ids[]`, `from_task_ids[]` in one transaction (additive; C10); `useCreateTask` drops its separate patch step | `api/routers/tasks.py`, `api/contract/tasks.py`, `frontend/src/api/mutations.ts` |
| 4 | `task_link` | does not exist | new table: `link_id`, `source_task_id`, `target_task_id`, `source_capability_run_id` (the pinned walk, C11), `created_by`, `created_at`; unique (source, target); no option id (D13); a link whose tasks stop sharing a project is **flagged, not broken** — a read-model check at render, no column (C12) | `schema.py`, migration; API read on the plan ("Starts from") and the tasks list |
| 4 | inherit | does not exist | task-1 part: pinned runs; linked plan, report body without citations, coverage statement as Task Agent context | new module under `backend/src/policy_atlas/runtime/` (name at plan time); read models in `api/readmodels/repository.py` |
| 5 | `plan` payload | `TaskPlan` only; `TaskPlan.model_validate` called from six readers (`runtime/agent.py`, `continuation_state.py`, `steering.py`, `api/routers/runs.py`, `sse.py`, `planning.py`) | `TaskPlan` or the scoping plan, chosen by `task.capability` through **one capability registry** (C9) that every reader uses for validation, composition and lattice membership; plan read/patch bodies gain `capability` | new `runtime/capability_registry.py` (name at plan time), `runtime/task_plan.py`, the six readers, `api/contract/planning.py` |
| 5 | Plan document | ES sections | scoping sections (§ Plan object) | `frontend/src/views/workspace/PlanDocument.tsx`, `planVocabulary.ts`, `planStart.ts` |
| 6 | Task Agent prompt | one prompt, `planner_v11` | prompt chosen by capability; new `task_agent_scoping_v1` offering the two depths as options | `runtime/task_agent.py` (renamed), new `runtime/task_agent_scoping_prompt.py`; `scripts/prompt_hashes.json` |
| 7 | Chain compile | `compose(TaskPlan)` | `compose` for the scoping plan → spine + synthesise(baseline) | `runtime/task_plan.py` `compose`, `runtime/run_spec.py` |
| 7 | synthesise | model-proposed sections validated against a cap; injects Conclusions, runs key-findings and case-study passes; one global turn cap; claim types gated by substrate | + **baseline mode** (C7): required section list supplied, proposer bounded to ≤2 extras, per-section instruction and turn cap on `SectionSpec`, fixed order, not-found state, sequential writing, ES-only passes off; chunk/reasoning/gap claims only for the baseline | `evidence_search/synthesis/synthesise.py` (`synthesise_scope`, `_validate_sections`, `SectionSpec`, `available_claim_types_for_substrate`), `synthesis_backend.py`; new `synthesis/baseline_prompt.py` |
| 7 | `evidence_scope` | intent + context; no plan pointer | + `purpose` (baseline \| longlist \| variant \| targeted; nullable) + `plan_id` (nullable FK to `plan`, composite with `task_id`) | `schema.py`, migration |
| 8 | Steering lattice | five points, one flat table; frequent pauses after every component; `STEER_POINTS` validates every plan's standing defaults | lattice keyed by capability (A2): `baseline_confirm` after synthesise exists only in the scoping chain; `always` in attended modes; a recorded non-pausing decision in unattended (A9); the standing-default validator is capability-aware (A18d) | `runtime/steering.py` `LATTICE_POINTS`, `pause_points`, `lattice_name_for`, `lattice_policy`; `runtime/task_plan.py` `STEER_POINTS`; `api/checkin_read.py`, `api/stage_vocabulary.py` |
| 8 | Task Agent turn at a pause | 409 `run_active` (both fences: turn and `PATCH /plan`); `PlanningTurnOut` carries a reply only | non-approving turns accepted while the walk is **paused**; sorted by the gate sort (new surface) into question · decision and dispatched to the **answer core** (C2) or the **existing check-in response** transaction bound to run, check-in and plan version (C5); the turn row and read model become a discriminated projection (reply · answer with citations · decision); the approving branch and `PATCH /plan` stay fenced; still 409 while **running** | `api/routers/planning.py` (renamed), new gate-sort prompt + `runtime/agent_backend.py` method, `api/chat_turns.py` (answer core lifted out; route unchanged), `api/continuation.py` (`answer_check_in`), `api/routers/check_ins.py`, `api/contract/planning.py` |
| 8 | Steering router | typed on `TaskPlan`; refuses changes to run components | **unchanged and not used at the gate** (C1 retires A3): Change the plan ends the walk and the plan is edited through the ordinary Task Agent turn | — |
| 8 | Check-in card | ES renders | baseline card: key assumption + Settings + two options, in the Task Agent thread | `frontend/src/views/workspace/CheckInCard.tsx`, `checkInPresentation.ts` |
| 9 | Result tab | ES artefact | baseline artefact with the band and run state | `frontend/src/views/ArtefactView.tsx`, `views/lifecycle.ts` `openTabs` |
| 9 | Sources tab | **keep** | unchanged; shows the baseline's documents | `frontend/src/views/Sources*.tsx` |
| 9 | Share, History tabs | **keep** | unchanged | `ShareView.tsx`, `HistoryView.tsx` |
| — | ES Task Agent prompt, ES walk, ES Result | **keep** | the prompt file moves **byte-identical** (C14): its hash is unchanged and only the pin entry's path changes; `planner_v11` stands; the ES chain composes as before; ES pauses keep their card-based steering | `runtime/task_agent_prompt.py` (renamed), `runner.py`, `harness.py` |
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
  depths (§ Baseline); a small acquisition target and a per-section cap; a
  measured compute target reported honestly; later levers recorded.
  **Re-revised in phase 8 (owner, 2026-09-17):** depth sets the target
  (20 · 10) and the proposed-section allowance (two · none); the eight
  sections are the same at both depths (§ Baseline). The
  writing mode is sequential (C6); the sequential-versus-parallel comparison
  the interview agreed runs as a development-time feasibility check, not as
  product code (owner, 2026-09-09).
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
   eight required sections plus up to two writer-proposed sections (phase 8:
   proposed sections at standard only).
2. plan-as-object § Thoroughness and OS capability § Depths: the baseline is
   not graded by depth (revises E12's baseline part); one measured target
   (phase 8 re-revises both: shaped by depth, a target per depth);
   the latency levers.
3. OS capability § Pipeline and gates and § Check-in points: the structural
   gates pass on standing defaults in unattended mode; unattended is never
   the default.
4. vocabulary.md: the Task Agent's code names after deliverable 2.
5. EB → ES across the living specs, in the rename phase (deliverable 2); the
   spec log gets one line when it lands.
6. plan-as-object § Plan vs config: plan-field ↔ chat-turn provenance is at
   **version grain** (C16 ruling), and § Thoroughness: the writing-mode trial
   sentence replaced by sequential writing plus a feasibility check (C6
   ruling). Applied with this re-approval.
7. web-api.md § Planning turns and § Check-ins: a sorted, non-approving Task
   Agent turn is admitted while a scoping walk is **paused**; the approving
   branch and `PATCH /plan` stay refused while a walk is running or paused
   (owner ruling at the plan gate, 2026-09-09, quoting D9). Applied in the
   build (plan Phase 5.6), logged in Phase 7.

## Adversarial findings (contract stage, 2026-09-09)

Fallback lane (`deep-reasoner`, read-only) after the Codex lane stalled at its
first command; a relaunched Codex lane is pending and its findings will be
appended. Eighteen findings, all accepted; the factual ones were re-verified
in the code before folding. Ids A1–A18 are cited above where folded.

| # | Finding | Severity | Fold |
|---|---|---|---|
| A1 | The ES prompt version string is `planner_v11`, not `planner_v1` | material | every mention corrected |
| A2 | `baseline_confirm` after synthesise collides with the ES lattice (frequent pauses after every component; the inverse map has no capability) | material | the lattice gains a capability dimension; ES regression test |
| A3 | The steering router is typed on `TaskPlan` and reads ES-only fields; it cannot be "reused unchanged" | material | marked modified, not reused; sized at plan time as the largest hidden item |
| A4 | No three-way triage exists; the boundary triage is a yes/no verdict | material | the gate sort is a third lead-authored prompt surface |
| A5 | Rollback refusal on "task exists, archive first" is self-defeating (archive keeps the row; `capability_run` rows also block the narrowing) | material | predicate over task and walk rows; operator hard-delete remedy |
| A6 | Relaxing the turn fence at a pause breaks the lineage invariant; `PATCH /plan` has its own fence | material | only non-approving turns admitted while paused; both fences kept |
| A7 | synthesise has no template mode; the baseline's substrate admits chunk, reasoning and gap claims only | material | template mode defined; claim types stated; proposer bounded |
| A8 | "Depth, the ES's words (rapid · standard)" — the ES forbids internal keys on screen and has two axes | material | screen labels in the ES pattern; one internal axis for scoping |
| A9 | In unattended, "off" means no pause and so no decision to record | material | a recorded non-pausing decision at the boundary; the standing default written into the plan when unattended is chosen |
| A10 | The rename misses constraint names, `planner_state`, `created_by='planner'`, the wire role literal and ~25 frontend files | material | complete list; fingerprints and legacy id excluded |
| A11 | The EB→ES exclusions contradict rubric 4 (`log.md` is under `docs/specs/`); quoted rulings and fingerprints unprotected | material fold | exclusions by path and token; rubric softened |
| A12 | The check-in response endpoint already does free-text compile → confirm → apply; build the gate on it | material, reduces code | adopted; the turn route dispatches to it |
| A13 | Two answer surfaces for one decision, different locks | minor | one transaction; concurrency test |
| A14 | "Sources unchanged" contradicts the baseline's not-searched statement | minor | the statement lives in the baseline's own Sources section |
| A15 | The "at a glance strip" exists only in the join step | minor | join step repairs only |
| A16 | `plan_version` is a weak pointer; `plan.evidence_scope_id` ambiguous | minor | `plan_id` FK; the plan row points at the baseline record |
| A17 | Ruling 50 (Result before assessment = longlist) and the restriction placement unflagged | minor | interim state noted; placement clause added |
| A18 | a) card key is a rename, `NewTaskView` hard-codes the capability; b) no flag for a link whose tasks stop sharing a project; c) "none changed" vs words-only re-pin; d) `STEER_POINTS` validates any plan; e) rubric item 1 collapses ten deliverables | minor | all folded; rubric split per deliverable |

Relaunched Codex lane (read-only, on commit `358e474d`, before the A-folds).
Eighteen findings; seven restate A-findings and are marked so. Three folds
are proposals pending the owner's ruling at re-approval (C1, C6, C16).

| # | Finding | Severity | Fold |
|---|---|---|---|
| C1 | A gate edit cannot use the steering path (the stability rule refuses changes to run components, and every component has run) and would leave the baseline stale | material | **ruled:** Change the plan ends the walk; the plan is edited by an ordinary Task Agent turn; the user then chooses Rebuild baseline or Confirm plan and build longlist; retires A3 |
| C2 | The chat answer path refuses paused walks; the Task Agent turn model has no citations | material | shared answer core; discriminated turn projection |
| C3 | `evidence_scope` has no plan FK; `_persist_new_plan_version` copies the old scope id | material | = A16, plus supersession: a rebuild's intent record and the plan row point at the new version |
| C4 | No three-way triage exists | material | = A4; the sort is question · decision under C1 |
| C5 | Task Agent turns race the check-in response endpoint | material | bind the turn to run, check-in and plan version; barrier test |
| C6 | Parallel section writing contradicts the durability contract ("never fan out the conclusion") | material | **ruled:** sequential ships; a development-time feasibility check compares the two; parallel in the product only by owner spec revision |
| C7 | synthesise cannot produce fixed-plus-optional sections; injects Conclusions and runs ES-only passes; one global cap | material | baseline mode defined with those passes off and per-section caps |
| C8 | `ScopeConstraints` has no language filter; acquisition target and writing mode absent from the plan | material | languages stored, not applied, recorded as an ES gap; constants named |
| C9 | Capability-specific validation is scattered over six readers; `STEER_POINTS` and `LATTICE_POINTS` are global | material | one capability registry; = A2/A18d mechanism |
| C10 | "Starts from" cannot be atomic with the create-then-patch flow | material | `project_ids` and `from_task_ids` on `POST /tasks` in one transaction |
| C11 | "Pinned source run ids" has no column, eligibility or selection rule | material | `source_capability_run_id`; succeeded or degraded only; one row per pair |
| C12 | Same-project invariant enforced only at creation | material | = A18b; flag on read, membership-change test |
| C13 | Rename inventory narrower than 038's | material | = A10 plus a rename manifest at plan time |
| C14 | `planner_v11`; a re-pin and an unchanged hash cannot both hold; the deployment guide omits the old variable | material | = A1; byte-identical move, hash unchanged; no fallback code, guide updated |
| C15 | The downgrade remedy cannot satisfy its predicate | material | = A5 |
| C16 | Per-field turn provenance deferred against the plan-as-object rule | material | **ruled:** not built; plan-as-object revised to version grain |
| C17 | Tasks-list depth has no API source | material | **dropped by the owner:** the tasks list shows no depth |
| C18 | Missing checks: Edit per plan section, `scoping pass` label, visible source-tier skew | minor | added to deliverables 6 and 7 and the acceptance checks |

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
  `evidence_scope.purpose`, `evidence_scope.plan_id`; widened
  `ck_capr_capability`; the deliverable-2 renames (conversation kind values,
  `plan.created_by` values, `planning_transcript` → `task_agent_transcript`,
  `planner_state` → `task_agent_state`, constraint and index names). **Two
  revisions, one per phase** (owner ruling at the plan gate, 2026-09-09,
  plan-review finding P1/X1): the rename revision lands with the fenced
  phase one, the slice revision with phase two; each reversible, values
  reversed on downgrade; rollback is two `downgrade -1` steps in reverse
  order (§ Rollback in ADR 0037).
- **Runtime egress:** a new walk kind reaches Overton, OpenAlex and the
  inference route with task data. Same backends, same transport, same
  `search` verb; no new host. Two new judgment-class call sites at the gate
  (triage, router) reuse the existing agent backend.
- **Public interface:** `capability` and `from_task_ids` on task create/read;
  `capability` on plan read/patch bodies with the scoping fields; check-in
  kind `baseline_confirm`; `project_ids` on task create (C10); the Task
  Agent turn response becomes
  a discriminated projection (reply · answer with citations · decision) as
  additive fields (C2); the path
  rename `/planning-turns` → `/task-agent-turns` with no redirect (the one
  non-additive change, the 038 pattern; the frontend is the only consumer).
  Everything else additive.
- **Prompts:** three new surfaces (`task_agent_scoping_v1`; the baseline
  template; the gate sort — A4); re-pin with
  `python3 scripts/prompt_hash_guard.py --update`. The ES Task Agent prompt's
  version string `planner_v11` is unchanged; the file moves byte-identical,
  so its hash is unchanged and only the pin's path changes (C14, replacing
  the earlier words-only allowance — the rename touches no prompt text). The ES section proposer's
  prompt changes only if template mode needs a bounded-extras instruction,
  versioned and re-pinned if so (A7). The router and boundary-triage prompts
  are reused unchanged. **The section writer's system prompt becomes
  template-keyed** *(owner ruling 2026-09-09, during the build: "For the
  synthesise, let's go with option 2")*: one writer, one shared core (tools,
  claim types, anchoring, honesty) plus one short preamble per output kind —
  the Evidence search report (the current text, so the assembled ES messages
  are **byte-identical** before and after, pinned by a test) and the baseline
  (its own version string); the profile and scoping-report preambles arrive
  with tasks 3 and 5. The `synthesis_backend.py` hash therefore changes once
  as a words-only re-pin recorded in `verification.md`. Rejected: one prompt
  with the baseline's rules carried in each section's seed focus (fights the
  report preamble and does not scale to the later templates); a separate
  prompt module per template (mirrors the writer). Every other pinned hash
  unchanged.
- **Production config:** one environment-variable rename,
  `POLICY_ATLAS_PLANNER_MODEL` → `POLICY_ATLAS_TASK_AGENT_MODEL`, in
  `infra/DEPLOYMENT.md` and the staging environment (approved with this
  contract; the deploy-side value change is the owner's at merge time). The
  code default is the same model as today, so a deploy that still sets only
  the old name behaves as before; the guide says so, and no fallback code
  is added (C14).
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
fixtures policy. The three recorded baselines are public-safe once their
source quotes are checked against the fixtures policy.

## Model route

OpenAI under the approved controls, behind the existing routing seam (the
Bedrock migration is untouched). Prompt-bearing, lead-authored:

- `task_agent_scoping_v1` — the Task Agent for a scoping task (deliverable 6);
  `task_agent_scoping_v2` from phase 8 (depth shapes the baseline).
- The gate sort — question · decision on a Task Agent turn at a pause
  (deliverable 8, A4, C1). Mini-class, one narrow job, constrained output,
  asks back when unsure.
- The baseline template — required and proposed sections, per-section
  instructions and caps, the reasoning labels, the not-found rule
  (deliverable 7).

Reused unchanged: screen, classify, appraise, the synthesise section writer
and grounding judge, the boundary triage, the steering router (not used at
the gate — C1). Modified, not reused: synthesise's section selection and
passes (baseline mode, A7, C7) and the chat's answer, lifted into a shared
answer core (C2).
The intent record's text is compiled deterministically from the plan, not
written by a model.

## Disciplines binding this slice

- **Don't flatten status.** ❓ open question 3 (rapid latency) stays open: the
  plan shows a coarse band and promises no number. Deep stays ⏸.
- **Model only what behaves.** `evidence_scope.purpose` and `plan_id` are read by the run opener
  and the Sources header; `task_link.option_id` waits for task 2 (D13).
- **Honest absence.** Every baseline section may read "not found"; the
  coverage statement names what was not searched.
- **Flag, don't drop.** Below-policy sources are flagged per plan-as-object.
- **Substance is never silent.** An unattended pass through the gate is
  recorded and flagged (D11).
- **Generation is free, interpretation is labelled, assessment is grounded**
  (OS trust). The baseline asserts nothing about options.
- **No code bloat (owner).** One writing mode (sequential, C6); the
  comparison lives in `scripts/feasibility_checks/`, never in the product.
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
    conversation kinds and `plan.created_by` values read `task_agent` after
    upgrade and `planning` / `planner` after downgrade; the downgrade refuses
    while any `task` **or `capability_run`** row carries `options_scoping`,
    archived or not (A5), and proceeds once the operator has removed them.
  - rename: no reference to `planning_transcript`, `/planning-turns`,
    `PlanningTurn`, `PlannerBackend`, `planner_prompt` or
    `POLICY_ATLAS_PLANNER_MODEL` remains in `backend/src`, `frontend/src`,
    `infra/DEPLOYMENT.md` or `web-api.md`, and no `planner_state`,
    `created_by = 'planner'` or `planning`-named constraint remains in
    `schema.py` (a sweep test in the 038 style with an allow-list for
    `eb_iof_base_v1`, `eb_icf_base_v1`, `evidence_base_coverage`); the old
    path is 404; the version string `planner_v11` is still emitted.
    The EB → ES sweep is checked once by grep and recorded in
    `verification.md`, not as a permanent test.
  - `task_link`: source ≠ target; unique pair; same-project rule (409)
    checked inside the one-transaction create (C10); the pinned
    `source_capability_run_id` must be a `succeeded` or `degraded` walk of
    the source task (C11); archive of a task with inbound links keeps the
    row; a link whose tasks no longer share a project renders flagged and is
    not deleted (A18b, C12); a link grants no read (an org-scoped read test
    in the ADR 0033 style).
  - inherit context: the fenced documents carry the linked plan, the report
    body with no citation markers and no reference list, and the coverage
    statement; one block per linked task; stable position after the system
    instructions across turns.
  - scoping plan validation: not ready without depth; deep rejected; `where`
    defaults to United Kingdom tagged assumed; constraint kinds and
    `checked_at` closed; Your context entries keep verbatim text and turn
    index; an ES task rejects a scoping payload and the reverse; the default
    steering mode is moderate and is never asked; each plan version records
    its `source_turn_index` and Your context entries their `turn_index`
    (C16); a language restriction is stored and
    shown as not applied at retrieval (C8); every reader validates through
    the capability registry (C9 — a test that no caller imports
    `TaskPlan.model_validate` directly).
  - compile: the scoping plan composes acquire → screen → classify →
    appraise → ingest → synthesise(baseline) and nothing else; the intent
    record carries `purpose=baseline` and the `plan_id` of the approved
    version, and `plan.evidence_scope_id` points back at it; evidence
    restrictions land on acquire as `ScopeConstraints`.
  - template: the eight required sections are always present at both depths
    and are supplied, not proposed; at most two proposed sections at standard
    and none at rapid (phase 8), placed
    after "what is contested"; a section with no support renders the
    not-found state; the key assumption and what is contested carry the
    tier-4 label; the baseline's claims are chunk, reasoning or gap only
    (A7); the Conclusions injection, key-findings and case-study passes do
    not run in baseline mode (C7); the baseline carries the `scoping pass`
    label and a visible source-tier skew line (C18).
  - gate: `baseline_confirm` pauses under frequent, moderate and minimal;
    under unattended no pause occurs and a decision event with
    `decided_by: standing_default` and a flag is written at the boundary
    (A9); choosing unattended in the plan writes the standing default for
    this point; the card carries the two options; Confirm ends the walk
    `succeeded` with a decision event; Change the plan ends the walk
    `aborted` with the decision recorded and leaves the plan approved and
    editable (C1; the steering router is not involved).
  - lattice (A2): an ES walk in frequent mode still pauses generically after
    synthesise and `lattice_name_for` never returns `baseline_confirm` for
    it; an ES plan rejects a `baseline_confirm` standing default (A18d); the
    existing steering tests pass unchanged.
  - gate turns: a non-approving Task Agent turn while paused is accepted and
    sorted; a question produces a grounded answer citing baseline sources
    through the answer core, and the chat route still refuses a paused walk
    (C2); a decision in words lands in the check-in response transaction
    bound to run, check-in and plan version, and a barrier test racing it
    against `POST .../check-ins/{id}/response` yields exactly one durable
    decision (A13, C5); "Change the plan" (card or words) ends the walk
    `aborted` with the decision recorded, the next Task Agent turn is
    accepted and mints a new plan version, the plan document then offers
    Rebuild baseline and Confirm plan and build longlist; Rebuild starts a
    new walk whose intent record and `plan.evidence_scope_id` point at the
    new version, and Confirm records both versions and ends (C1, C3); a mixed turn answers first and never infers
    a decision; an unsortable turn is asked back; the approving branch and
    `PATCH /plan` are 409 `run_active` while paused (A6); a turn while
    running is 409 `run_active`; an ES task's pause still refuses turns (ES
    unchanged).
  - ES regression: `planner_v11` version string and prompt text unchanged; `compose(TaskPlan)` output
    unchanged (existing tests); ES steering tests unchanged.
  - frontend (vitest): New task form states (question and Starts from only,
    Starts from restricted to same-project Evidence search tasks; no depth
    or job control; one create request); plan document renders every scoping
    section with its Edit action (C18); the tasks list shows the kind and no
    depth; the Task Agent
    thread renders a gate question with citations, a Change-the-plan decision
    and the check-in card with two options; Result shows the band, the run
    state and the "built from plan version N" mark after a plan change.
- **No AI eval in this slice.** Baseline quality is judge behaviour and goes
  to the eval slice. `verification.md` records three live baselines (NEET;
  one thin-evidence structural question; one linked start) with their
  compute times, read against the trust rules as a qualitative note, not a
  pass/fail gate — plus the sequential-versus-parallel feasibility check's
  numbers and reading (C6).
- **Live check (pinned scope, ~25 minutes):** local app, real egress.
  (a) Seed one Evidence search task on NEET with a completed report.
  (b) New task → Options scoping → question · Starts from the seeded task →
  Prepare plan. (c) Three Task Agent turns: it proposes from the linked plan
  and report, asks who should change, offers the two depths as options and
  the user picks standard; "OECD evidence only" gets the kind question; the plan shows
  Starts from, the constraints table, Your context, the steps. (d) Confirm
  and build baseline: the walk runs, Result opens on the baseline with the
  band and its Sources section naming what was not searched, the Sources tab
  lists the documents; compute time recorded. (e) In the same thread: one question about the baseline
  answered with citations; then "change Where to England" → the walk ends,
  the Task Agent applies the change as a new plan version and says the
  baseline's inputs changed; Rebuild baseline (second compute time recorded).
  (f) Confirm → History shows both decisions; the Result says the longlist
  arrives with the next stage. Then one more change that does not touch the
  baseline's inputs (add a preference) → Confirm plan and build longlist
  without a rebuild. (g) ES smoke: New task → Evidence search → two Task Agent turns →
  an approved plan (no run; the shared turn path is what this slice
  touches; the ES walk is covered by tests). No full ES live e2e.

## Verification evidence expected

Command tails; the migration round-trip output; the rename sweep result; the
OpenAPI diff (additive except the path rename); the prompt-hash diff (three
new entries; the ES Task Agent entry's path moved, hash unchanged); the
rename manifest (C13); measured gate-sort latency; live-check notes and
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

Rollback shape (ADR 0037 names the commands): quiesce the API; the slice
revision's `alembic downgrade -1` refuses while any `task` or `capability_run` row carries
`options_scoping`, archived or not (A5 — archiving keeps the row, so it is
not a remedy); the remedy is an operator script that hard-deletes those
scoping tasks and their walks (pre-merge, staging-only data — the only rows
the widened constraint would block), after which the downgrade drops
`task_link`, the two `evidence_scope` columns and `task.capability`, narrows
`ck_capr_capability`; a second `downgrade -1` reverses the rename revision
(tables, columns, constraint names, stored kind and `created_by` values);
deploy the previous image.

Review focus: the ES planner prompt, chain and steering byte-for-byte
unchanged; the rename diff contains nothing but the rename; the gate passes
only in unattended and always records and flags (D11); no scoping payload
validates on an ES task or the reverse (D1); a link never widens access (A6);
a gate turn never applies an unconfirmed delta and never lands a plan under a
running walk; the baseline asserts nothing about options and labels its two
reasoning sections; the not-found state is a content state, not a hedge; the
losing writing mode is gone; the additive-only OpenAPI diff outside the
rename; `where` never silently stays empty.
