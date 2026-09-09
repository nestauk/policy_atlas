# Task contract: 043-scoping-shell-baseline

One implementation slice: the first of the five options-scoping build tasks
(PR #69 "Task 1 — the task shell and the baseline"). It lands the second task
kind, its plan and planning chat, the link to an existing Evidence search, the
"do nothing" baseline, and the gate where the user confirms the plan against
the baseline before any option is generated.

> **Status:** drafted 2026-09-09 · lead. Contract approved (before planning):
> _pending · owner_ · Contract-stage adversarial review (Codex, read-only):
> _after approval_ · Plan approved (before implementation): _pending_ ·
> ADR: **0037** (to be written at step 4 — task kind, `task_link`, the
> baseline gate, the capability switch, rollback).
>
> **Branching:** `task/043-scoping-shell-baseline` from `feat/options-scoping`
> at `7e31c373` (dev merged in after tasks 039–042; issue #74 fix included).
> PR target: `feat/options-scoping`, merge commit (not squash), per PR #69.
>
> **Prior decisions this slice builds on:** the sixteen decision-sheet rows
> decided 2026-09-09 (`docs/tasks/035-options-scoping/checks/decision-sheet.md`
> rows A4 reduced, A5 bug, A6, A7, A8 deferred, B3, C1, C2 dissolved, C3, C4,
> D3 dissolved, E12, E13 part, E16, F1). They are applied in the specs and are
> **context, not targets**. The task number is a reservation id (035 note).

## Goal

A user can start an **Options scoping** task, agree its plan in the Agent tab,
and receive a sourced profile of "Do nothing" that the run pauses on. The user
questions the baseline in chat, changes the plan if needed, and confirms it.
Nothing after the baseline runs in this slice: the longlist is task 2.

Ten numbered deliverables, one numbering used by the rubric, the plan and the
ADR:

1. **Task kind.** A task carries its capability (`evidence_search` or
   `options_scoping`). Existing tasks are Evidence search. The tasks list
   shows the kind and, for a scoping task, its depth.
2. **Capability switch.** Options scoping is off unless the deployment enables
   it. Off = the New task screen shows the card as not available (as today)
   and the API refuses to create a scoping task. Production stays off.
3. **Start a scoping task.** The New task screen, with the switch on: the
   question, the scoping job (explore the option space; sense-check one
   option is shown but not available — task 4), an optional depth (rapid ·
   standard; deep shown as later), and **Starts from**: zero or more Evidence
   search tasks in the same project. Prepare plan → the Agent tab.
4. **Link record.** Each "starts from" choice is a `task_link` row. Links are
   many-to-many, same-project only, archive-not-delete, and change no access.
   `inherit` (task-1 part) reads the linked task's approved question and
   screened-document count into the planning conversation and pins the source
   run ids on the link. Document rows enter the receiving task with the
   longlist (task 2), where they are re-screened (D4).
5. **Scoping plan.** A plan object with the scoping slots (§ Plan object),
   versioned in the existing `plan` table, shown as the navy plan document
   beside the Task Agent exactly like the Evidence search plan: Starts from ·
   Question and intended change · Settings (who or what should change · where
   · outcomes · depth) · Constraints and preferences (a table: what you asked
   for · what happens · checked at) · Your context · Steps and check-ins. One
   start action: **Confirm and build baseline**, with a coarse time band.
6. **Scoping planner.** The planning conversation for a scoping task: fills
   the plan from the question and the linked tasks, tags each field *from
   your question* / *assumed* / *your call*, asks depth every time (no
   default), asks who or what should change when the question leaves it
   open, defaults Where to the United Kingdom (assumed, please check), offers
   setting as an optional constraint, and asks which kind a constraint
   sentence is when it is ambiguous ("limit the evidence I read, or the
   options you would consider?"). Lead-authored prompt, hash-pinned.
7. **Baseline run.** Confirming the plan runs one walk: acquire (Overton and
   OpenAlex) → screen (title and abstract; the plan compiled to carry target
   unit and Where) → classify → appraise → ingest → synthesise with the
   **baseline template** (§ Baseline). Its own intent record (baseline role,
   plan version). Each empirical premise is sourced; the key assumption and
   what is contested are labelled reasoning; "not found" is a content state;
   the coverage statement names live official statistics and departmental
   pages as not searched.
8. **The gate.** The walk pauses after the baseline in every steering mode
   (a structural gate, never a mode-dependent one). The check-in card quotes
   the baseline's key assumption and the plan's Settings and offers two
   options: **Confirm plan and build longlist** and **Change the plan**
   (free text through the existing router; the plan gets a new version; the
   walk stays paused until Confirm). Confirm records the decision and ends
   the walk. Nothing after the gate runs in this slice; the Result says the
   longlist arrives with the next stage.
9. **Tabs and views.** Agent · Result · Sources · Share · History, the task's
   own. Result shows the baseline profile as linear text with a side outline
   and collapsible sections, under a band worded **the situation these
   options would change** and the run state (ready · awaiting your
   confirmation / plan confirmed). Sources is the Evidence search's Sources
   component over the baseline's documents, unchanged. Share and History
   unchanged. The chat answers questions about the baseline while the walk is
   paused (❓ D9).
10. **System records.** `task.capability`; `task_link`;
    `evidence_scope.role` and `evidence_scope.plan_version` (several intent
    records per plan, decision C4); the `baseline_confirm` steer point; the
    `options_scoping` capability on `capability_run`. Declared once, in the
    ADR, for tasks 2–5 to build on.

## Deliverable

A PR on `task/043-scoping-shell-baseline` into `feat/options-scoping`: one
alembic migration, the scoping plan model and planner, the baseline template
and walk, the gate, the frontend shell, tests, `verification.md`, ADR 0037,
and the decisions below quoted where they are applied.

## Terms

| Term | Meaning |
|---|---|
| **capability** | The kind of work a task does. Code: `task.capability`, values `evidence_search` \| `options_scoping`; the same words as `capability_run.capability` (`backend/src/policy_atlas/core/schema.py`). User-facing: "Evidence search", "Options scoping". |
| **Evidence search (EB)** | The first capability. Its components are reused here, never mirrored (owner ruling 2026-09-07). "EB" in older documents. |
| **task 1 … task 5** | The five options-scoping build tasks in PR #69. This slice is task 1. Not the product Task. |
| **Task Agent** | The primary planning chat of a task, pinned first in the Agent tab (`docs/specs/vocabulary.md`). Backend: planning turns, `backend/src/policy_atlas/api/routers/planning.py`. |
| **plan** | The user-approved object the run compiles from. Table `plan` (`task_plan` in `schema.py`), payload JSONB, versioned per task. |
| **intent record** | An `evidence_scope` row: the question a run is answering plus its settings; every result row points at one. Decision C4: several per plan. |
| **Link** | A `task_link` row: source task, target task, pinned source run ids, created by/at. Declared in `data-model.md` § Links between tasks (decision A6). |
| **inherit** | The shared component that reads across a Link. Its task-1 part seeds the planning conversation and pins the source runs. Its document part lands in task 2. |
| **baseline** | The profile of "Do nothing": eight ruled sections (§ Baseline). The Result of this slice. |
| **the gate** | The pause after the baseline where the user confirms the plan. Steer point `baseline_confirm`; the first of the two structural gates (OS capability § Pipeline and gates). |
| **steer point** | A named pause on the steering lattice (`runtime/steering.py` `LATTICE_POINTS`). EB has five; this slice adds one. |
| **walk** | One run of a capability's chain: a `capability_run` row plus its component `runs`. |
| **depth** | The plan's rapid \| standard \| deep, the EB's words. Asked every time, no default (ruling 25). Deep is ⏸ later for scoping. |
| **origin tag** | Per plan field: *from your question* \| *assumed* \| *your call*. |
| **constraint kind** | *scope-shaped* (checked at the longlist) \| *effect- or cost-shaped* (checked after assessment) \| *evidence restriction* (applied at retrieval as the EB's search directive filters — decision C1). |
| **Your context** | The plan section of the user's transferability context: entries typed *present fact* \| *commitment*, verbatim words, the turn that produced them, an optional *test this as a condition* flag (decisions C3, E13). |
| **switch** | The deployment setting that enables capabilities (deliverable 2). |
| **Sources component** | The EB Sources tab: coverage header, filter chips, document table, Landscape and All sources views (`frontend/src/views/Sources*.tsx`). |

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
- [EB components § 0](../../specs/capabilities/evidence-search/components.md)
  — the reverse inherit direction (task 5), for symmetry only.
- [prompting](../../specs/system/prompting.md) — the two new prompt surfaces.
- The boards `Ask`, `Frame`, `Baseline`, `BaselineGenerating`, `TasksList`
  under `docs/specs/sources/options-scoping/boards/` — product intent only;
  every figure is placeholder; rulings win.
- `docs/tasks/035-options-scoping/checks/check-6-contract-trace.md` § What
  this means for task 1 (superseded where the decision sheet ruled otherwise).

## Plan object

The scoping plan is stored in the existing `plan` table and lineage; the
payload is validated by the task's capability. Fields (spec § 1 plan; the
Frame board):

| Field | Content | Origin tag | Compiles to |
|---|---|---|---|
| `title` | short name | — | task name |
| `question` | the user's ask | — | baseline and longlist intent text |
| `intended_change` | what we are trying to change | yes | intent text |
| `target_unit` | who or what should change (people, firms, places, organisations, systems) | yes | intent context; screen prompt input |
| `where` | the jurisdiction the policy applies to; default "United Kingdom" tagged *assumed* | yes | intent context; screen prompt input |
| `outcomes[]` | the outcomes evidence is read against | yes | intent context |
| `depth` | rapid \| standard (deep listed, not selectable — D6) | *your call* | baseline section subset (§ Baseline); tasks 2–3 read it later |
| `constraints[]` | `{text, kind, origin, checked_at}`; kind ∈ scope \| effect_cost \| evidence_restriction; checked_at ∈ longlist \| assessment \| retrieval | yes | evidence restrictions → the EB `ScopeConstraints` (country group · years · languages) on acquire; the other kinds are stored for tasks 2–3 |
| `your_context[]` | `{text verbatim, type: present_fact \| commitment, turn_index, test_as_condition}` | — | stored; read by task 3 |
| `entry_branch` | `explore` (only value in this slice) | — | — |
| `linked_task_ids[]` | from `task_link` | — | plan "Starts from" |
| `steering_mode`, `steer_point_defaults` | as EB | — | as EB; the gate ignores the mode |
| `steps[]` | Baseline · Longlist · Shortlist and assessment, each with one plain sentence | — | display; only Baseline runs here |
| `time_band` | coarse compute band for the baseline, "then a check-in" | — | display |
| `source_turn_index` | as EB | — | as EB |

Per-field turn provenance beyond `your_context` and `source_turn_index` is not
built in this slice (the EB plan does not carry it either) — a deferred seam,
recorded in `docs/deferred.md`.

## Baseline

Eight ruled sections (OS capability § Output structure): what is in place ·
trend if nothing changes · who is affected · what is already changing · what is
contested · cost of inaction · key assumption · sources. Graded by depth
(decision E12, design targets verified during development, never run-time
cut-offs):

| Depth | Sections | Target compute |
|---|---|---|
| rapid | what is in place · trend if nothing changes · who is affected · what is contested · key assumption · sources (D7) | about two minutes |
| standard | all eight | about five minutes |

Rules the template carries: empirical premises cited to sources; the key
assumption and what is contested are tier-4 reasoning claims labelled as such;
"not found" is a content state, never a hedge; Policy Atlas does not forecast;
the coverage statement (in Sources) names Overton and OpenAlex as searched and
live official statistics and departmental pages as not searched; the
grey-literature skew is shown, not hidden. Evidence restrictions apply to the
baseline's acquire like any other (D8).

## Surface map

Rows marked **keep** must not change behaviour. File paths are as built at
`7e31c373`.

| # | Surface | Today | After this slice | Where |
|---|---|---|---|---|
| 1 | `task` row | no kind | `capability` text, check constraint, default `evidence_search` | `backend/src/policy_atlas/core/schema.py` (task, line ~101); new alembic revision after `c1a7f4e9b0d2` |
| 1 | `capability_run.capability` | `evidence_search` only | + `options_scoping` | `schema.py` `ck_capr_capability`; `runtime/runner.py` `_open_capability_run` literal |
| 1 | Tasks list row | label from a key the API does not send | label from `TaskOut.capability`; depth chip for scoping | `frontend/src/views/TaskListRow.tsx`, `lib/capabilities.ts` |
| 2 | Deployment settings | no capability switch | `enabled_capabilities` (default: evidence search only) read by `GET /me` and by `POST /tasks` | `backend/src/policy_atlas/api/settings.py`, `api/routers/me.py`, `api/routers/tasks.py` |
| 3 | New task screen | capability cards; scoping card `available: false` | card enabled by the switch; scoping form: job · depth · Starts from | `frontend/src/views/NewTaskView.tsx`, `api/mutations.ts` `useCreateTask` |
| 3 | `POST /tasks` | name, question | + `capability`, `from_task_ids[]` (additive) | `api/routers/tasks.py`, `api/contract/tasks.py` |
| 4 | `task_link` | does not exist | new table | `schema.py`, migration; API read on the plan and the tasks list |
| 4 | inherit | does not exist | task-1 part: plan seeding + pinned runs | new module under `backend/src/policy_atlas/runtime/` (name at plan time) |
| 5 | `plan` payload | `TaskPlan` only | `TaskPlan` or the scoping plan, chosen by `task.capability`; `GET/PATCH /plan` bodies gain `capability` | `runtime/task_plan.py`, `api/routers/planning.py`, `api/contract/planning.py` |
| 5 | Plan document | EB sections | scoping sections (§ Plan object) | `frontend/src/views/workspace/PlanDocument.tsx`, `planVocabulary.ts`, `planStart.ts` |
| 6 | Planner | one prompt, `planner_v1` | prompt chosen by capability; new `scoping_planner_v1` | `runtime/planner.py`, new `runtime/scoping_planner_prompt.py`; `scripts/prompt_hashes.json` |
| 7 | Chain compile | `compose(TaskPlan)` | `compose` for the scoping plan → spine + synthesise(baseline) | `runtime/task_plan.py` `compose`, `runtime/run_spec.py` |
| 7 | synthesise | intent-led sections | + template mode: fixed section list, per-section instruction, not-found state | `evidence_search/synthesis/synthesise.py`, `synthesis_backend.py`; new `synthesis/baseline_prompt.py` |
| 7 | `evidence_scope` | intent + context | + `role` (baseline \| longlist \| variant \| targeted; nullable) + `plan_version` (nullable) | `schema.py`, migration |
| 8 | Steering lattice | five points | + `baseline_confirm` after synthesise, policy `always` in every mode for scoping walks | `runtime/steering.py` `LATTICE_POINTS`, `runtime/task_plan.py` `STEER_POINTS`, `api/checkin_read.py`, `api/stage_vocabulary.py` |
| 8 | Check-in card | EB renders | baseline card: key assumption + Settings + two options | `frontend/src/views/workspace/CheckInCard.tsx`, `checkInPresentation.ts` |
| 9 | Result tab | EB artefact | baseline artefact with the band and run state | `frontend/src/views/ArtefactView.tsx`, `views/lifecycle.ts` `openTabs` |
| 9 | Sources tab | **keep** | unchanged; shows the baseline's documents | `frontend/src/views/Sources*.tsx` |
| 9 | Share, History tabs | **keep** | unchanged | `ShareView.tsx`, `HistoryView.tsx` |
| — | EB planner prompt, EB walk, EB Result | **keep** | word-for-word unchanged (`planner_v1` hash unchanged); the EB chain composes as before | `runtime/planner_prompt.py`, `runner.py`, `harness.py` |
| — | Generated | via `make openapi-sync` only | additive OpenAPI diff | `frontend/openapi.json`, `frontend/src/api/gen/types.ts` |

## Decisions pinned here (owner confirms at the contract gate)

- **D1 — one plan table, two payload shapes.** The scoping plan is a second
  Pydantic model stored in the same `plan` table and lineage; the task's
  capability decides which model validates the payload. *Rejected:* a second
  table (mirrors the EB plan machinery); one union model (forces EB fields
  onto scoping and vice versa).
- **D2 — capability on the task, not inferred from runs.** `task.capability`
  is written at creation and never changes. *Rejected:* deriving it from
  `capability_run` (a task with no run yet has no kind).
- **D3 — the switch is a deployment setting**, `enabled_capabilities`, default
  Evidence search only, surfaced through `GET /me`. The frontend enables the
  card from it; the API refuses `POST /tasks` for a disabled capability with
  403. Enabling it on staging is a deployment config change (gated, owner).
- **D4 — inherit lands in two parts.** Task 1: the Link, the pinned source
  run ids, and the planning conversation's seed (the linked question and
  screened-document count, offered as context; the user's own ask stays
  primary — decision A6). Task 2: the document rows, created when the
  longlist scope re-screens them. *Why:* rows nothing reads would be model
  without behaviour, and the Sources component assumes screening rows exist.
- **D5 — the key `options_scoping` and the label "Options scoping".** The
  frontend key `scoping_policy_options` / "Scoping policy options" is renamed;
  it is stored nowhere.
- **D6 — depth offers rapid and standard.** Deep is listed as later and not
  selectable (OS capability § Depths: deep ⏸). The plan is not ready until a
  depth is chosen.
- **D7 — the rapid baseline subset** is six sections: what is in place ·
  trend if nothing changes · who is affected · what is contested · key
  assumption · sources. Dropped at rapid: what is already changing · cost of
  inaction. *Why:* who is affected is where the target unit is checked
  against the data, and what is contested is how newcomers are served.
- **D8 — evidence restrictions apply to the baseline's acquire** exactly as
  to any acquire (the EB filters, decision C1). *Alternative:* exempt the
  baseline because it describes the problem in the plan's Where. Owner's call.
- **D9 — chat over the paused baseline.** The requirement stands (the user
  questions the baseline in chat at the gate). Whether the as-built chat is
  blocked while a walk is paused is checked at plan time; if it is, lifting
  the block for paused walks is in scope, and a run-active block on planning
  turns stays (steering is the plan channel mid-run).
- **D10 — "Search further" is deferred.** The gate offers Confirm and Change
  the plan only. An additive re-acquire for the baseline is recorded in
  `docs/deferred.md` for task 2 or later.
- **D11 — the gate ignores the steering mode.** `baseline_confirm` pauses in
  frequent, moderate, minimal and unattended alike, because the spec makes it
  structural (OS components: "two gates are structural, not discretionary").
  A standing instruction cannot answer it.
- **D12 — after Confirm the walk ends.** The decision is recorded as a
  steering event; the plan version is unchanged unless the user changed it;
  the Result shows the confirmed baseline and says the longlist arrives with
  the next stage. Task 2 replaces this end with the longlist chain.
- **D13 — the option id column on `task_link` lands in task 2** with the
  option table it references. Nothing in this slice could write it.

## Scope / Out of scope

- **In:** the surface-map rows above; the migration; ADR 0037; tests
  (§ Acceptance checks); `verification.md`; `docs/deferred.md` deltas.
- **Out:** the longlist and everything after the gate (tasks 2–3); the
  sense-check branch (task 4; shown as not available); Sources tab
  additions and export (task 4); the full run and the reverse inherit
  direction (task 5); document rows for inherited documents (task 2, D4);
  per-field turn provenance beyond Your context; "Search further" (D10); any
  change to the EB planner prompt text, the EB chain or the EB Result; deep
  depth; setting as a mandatory slot; any prompt edit to `screen`, `classify`,
  `appraise`; corpus-level document identity (#75).

## Constraints & approval gates

Hard gates this slice touches — approval is this contract's sign-off:

- **Schema / data model:** `task.capability`; `task_link`;
  `evidence_scope.role`, `evidence_scope.plan_version`; widened
  `ck_capr_capability`. One migration, reversible (§ Rollback in ADR 0037).
- **Runtime egress:** a new walk kind reaches Overton, OpenAlex and the
  inference route with task data. Same backends, same transport, same
  `search` verb; no new host.
- **Public interface (additive):** `capability` and `from_task_ids` on task
  create/read; `capability` on plan read/patch bodies with the scoping
  fields; `enabled_capabilities` on `/me`; check-in kind `baseline_confirm`.
  Nothing removed or renamed; the OpenAPI diff must be additive only.
- **Prompts:** two new surfaces (`scoping_planner_v1`, the baseline template);
  re-pin with `python3 scripts/prompt_hash_guard.py --update`; every other
  pinned hash unchanged.
- **Production config:** none in this slice. The switch defaults off.
- Generated files change only via `make openapi-sync`; `make drift-check`
  green. No dependency, CI or auth change. Tenancy (ADR 0033) and public read
  (ADR 0035) predicates are untouched; a scoping task reads and shares like
  any task.

## Public / private boundary

Contract, rubric, plan, ADR and `verification.md` are public-safe. Live-check
evidence: screenshots of the plan and baseline on the NEET question are
public-safe (the question is the design reference); raw acquired text, traces
and credentials stay private. Recorded provider fixtures follow the sanitized
fixtures policy.

## Model route

OpenAI under the approved controls, behind the existing routing seam (the
Bedrock migration is untouched). Prompt-bearing, lead-authored:

- `scoping_planner_v1` — the Task Agent for a scoping task (deliverable 6).
- The baseline template — section list, per-section instructions, the
  reasoning labels and the not-found rule, inside synthesise (deliverable 7).

Reused unchanged: screen, classify, appraise, the synthesise section writer
and grounding judge, the steering router. The intent record's text is compiled
deterministically from the plan, not written by a model.

## Disciplines binding this slice

- **Don't flatten status.** ❓ open question 3 (rapid latency) stays open: the
  plan shows a coarse band and promises no number. Deep stays ⏸.
- **Model only what behaves.** `evidence_scope.role` is read by the run opener
  and the Sources header; `task_link.option_id` waits for task 2 (D13).
- **Honest absence.** Every baseline section may read "not found"; the
  coverage statement names what was not searched.
- **Flag, don't drop.** Below-policy sources are flagged per plan-as-object.
- **Generation is free, interpretation is labelled, assessment is grounded**
  (OS trust). The baseline asserts nothing about options.
- Deferred seams go to [docs/deferred.md](../../deferred.md): per-field turn
  provenance; Search further; inherited document rows (task 2 pointer).

## Stop conditions

Halt and escalate when: a gate above needs more than this sign-off (a new
host, a non-additive API change, a second migration); the as-built chat
cannot serve the paused baseline without touching the run fence beyond D9;
the baseline template cannot meet its compute target at standard depth on the
NEET question without cutting a section (report the measurement, do not cut);
scope would grow into task 2; or the turn/token budget is spent.

## Acceptance checks

- `make verify` green (okf-validate · test · typecheck · lint · build ·
  drift-check · prompt-guard).
- **Deterministic tests** (backend unless stated):
  - migration round-trip: upgrade, downgrade, upgrade; existing tasks read
    `evidence_search`; `ck_capr_capability` accepts both values.
  - `task_link`: source ≠ target; unique pair; same-project rule (409);
    archive of a task with inbound links keeps the row; a link grants no read
    (an org-scoped read test in the ADR 0033 style).
  - scoping plan validation: not ready without depth; `where` defaults to
    United Kingdom tagged assumed; constraint kinds and `checked_at` closed;
    Your context entries keep verbatim text and turn index; an EB task
    rejects a scoping payload and the reverse.
  - compile: the scoping plan composes acquire → screen → classify →
    appraise → ingest → synthesise(baseline) and nothing else; the intent
    record carries `role=baseline` and the plan version; evidence
    restrictions land on acquire as `ScopeConstraints`.
  - template: rapid produces exactly the six D7 sections, standard all eight;
    a section with no support renders the not-found state; the key
    assumption and what is contested carry the tier-4 label.
  - gate: `baseline_confirm` pauses under all four modes; the card carries the
    two options; Confirm ends the walk `succeeded` with a decision event;
    Change the plan writes a new plan version and keeps the walk paused; a
    planning turn during the pause is 409 `run_active`.
  - switch: `POST /tasks` with a disabled capability is 403; `/me` lists the
    enabled set.
  - EB regression: `planner_v1` hash unchanged; `compose(TaskPlan)` output
    unchanged (existing tests).
  - frontend (vitest): New task form states (switch off/on, job, depth,
    Starts from); plan document renders every scoping section; tasks list
    shows kind and depth; check-in card renders the two options; Result
    shows the band and run state.
- **No AI eval in this slice.** Baseline quality is judge behaviour and goes
  to the eval slice. `verification.md` records three live baselines (NEET;
  one thin-evidence structural question; one linked start) read against the
  trust rules — sourced premises, labelled reasoning, not-found states — as a
  qualitative note, not a pass/fail gate.
- **Live check (pinned scope, ~25 minutes):** local app, switch on, real
  egress. (a) Seed one Evidence search task on NEET with an approved plan.
  (b) New task → Options scoping → question · explore · standard · Starts
  from the seeded task → Prepare plan. (c) Three planning turns: the planner
  asks who should change and depth; "OECD evidence only" gets the
  kind question; the plan shows Starts from, the constraints table, Your
  context, the steps. (d) Confirm and build baseline: the walk runs (about
  five minutes compute at standard), Result opens on the baseline with the
  band, Sources lists the documents with the coverage statement. (e) One chat
  question about the baseline answered with citations (D9). (f) Change the
  plan by free text → new plan version, still paused. (g) Confirm → History
  shows the decision; the Result says the longlist arrives with the next
  stage. (h) EB smoke: New task → Evidence search → two planning turns → an
  approved plan (no run; the shared planning path is what this slice
  touches; the EB walk is covered by tests). No full EB live e2e.

## Verification evidence expected

Command tails; the migration round-trip output; the OpenAPI diff (additive
only); the prompt-hash diff (two new entries, none changed); live-check notes
and screenshots for (a)–(h); the three baselines' qualitative note; the
`docs/deferred.md` delta; known gaps.

## Risk tier & review focus

**Tier 4** — migration, runtime egress for a new walk kind, public API
change, two prompt surfaces: ADR 0037 with a rollback plan, human-approved
plan, adversarial review at the contract and plan stages (`codex-rescue`,
read-only briefs), the step-7 stack per the spine (contract verifier ·
`/code-review medium` · one security lane scoped to the new endpoints, the
switch and `task_link` · `/simplify` · human deep review).

Rollback shape (ADR 0037 names the commands): switch off hides the
capability without a deploy of data changes; `alembic downgrade -1` refuses
while any `options_scoping` task exists (the operator archives them first) and
otherwise drops `task_link`, the two `evidence_scope` columns and
`task.capability`, and narrows `ck_capr_capability`.

Review focus: the EB planner prompt and chain byte-for-byte unchanged; the
gate pauses in unattended mode (D11); no scoping payload validates on an EB
task or the reverse (D1); a link never widens access (A6); the baseline
asserts nothing about options and labels its two reasoning sections; the
not-found state is a content state, not a hedge; the additive-only OpenAPI
diff; the switch cannot be bypassed by a direct API call; `where` never
silently stays empty.
