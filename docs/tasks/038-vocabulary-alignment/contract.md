# Task contract: 038-vocabulary-alignment

One implementation slice. Keep it reviewable. Boundaries are in
[AGENTS.md](../../../AGENTS.md). Specs are in [docs/specs/](../../specs/index.md).

> **Status:** drafted 2026-09-04 — **awaiting owner approval**.
> Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ ·
> ADR: **0036** (to be written at step 4 — retires ADR 0031 decision 2; records the
> `/api/v1` path break and the rollback plan).
>
> **Branching:** `task/038-vocabulary-alignment` from `dev`; `origin/dev`
> merged in at `8626594f` (2026-09-04, after PRs #61 and #64). Not stacked.
>
> **Renumbered 2026-09-04:** drafted as 037 / ADR 0035; the colleague's
> `037-public-projects` (ADR 0035) merged first, so this slice is **038 / ADR
> 0036**. That merge added a public read leg and a public share link on the
> `project` row — both now inside this rename (§ Surface map, F3).
>
> **Prior ruling this slice discharges:** owner, 2026-08-24
> ([deferred.md § Task lifecycle IA](../../deferred.md)): *"this gets its own
> rename slice, scheduled after 033-organisations — `project` → `task`,
> `portfolio` → `project`, mechanical, no behaviour change … It breaks
> `/api/v1/projects/*` and every bookmarked URL; the frontend and the e2e specs are
> the only consumers."*
>
> **Amendments 2026-09-04** (owner + colleague, folded into the
> [definitions](../../specs/sources/vocabulary/policy-atlas-definitions.md) — the owner
> keeps that file current):
> the Agent tab hosts all of a Task's chats in a sidebar; chats stay **chats**;
> the primary (planning) chat is the **Task Agent**, pinned first and visually
> distinct. The mode labels are withdrawn. V5 and V8 are rewritten to this.
>
> **Owner forks F1–F5** (§ Forks) need a ruling at this gate. Each has a
> recommended default; the contract is written to the defaults.

## Goal

Make the words in the code, the schema, the API and the screen the same words the
team uses ([frozen definitions](../../specs/sources/vocabulary/policy-atlas-definitions.md)).
Today three vocabularies coexist: the screen says Task/Project/Evidence search, the
code and database say `project`/`portfolio`/`evidence_base`, and the chat surface
has no name at all. Eight numbered defects, V1–V8. **No behaviour change**: every
row, route and screen does after the slice what it did before, under a new name.

## Deliverable

One PR on `task/038-vocabulary-alignment` that:

- Renames the `project` entity to `task` in the schema, the code, the API and the
  frontend (V1).
- Renames the `portfolio` entity to `project` in the same places (V2).
- Renames the Evidence search capability from `evidence_base` in the package, the
  capability key, the stored value and the user-visible copy (V3).
- Names the orchestrator surface **Agent** on screen and on the wire (V4).
- Relabels the lifecycle tabs Agent · Result · Sources · Share · History (V5).
- Routes the leaked hard-coded Task/Project literals through the copy module (V6).
- Updates the living docs, writes the glossary spec, amends ADR 0031 (V7).
- Shows a Task's chats in the Agent tab with the **Task Agent** pinned first (V8).

Shipped = `make verify` green (which includes `drift-check` and `prompt-guard`),
the migration applied to staging, and one live smoke of the renamed chain
(§ Acceptance checks).

## Terms

Two meanings of "task" meet in this repo. The table fixes them.

| Term | Meaning |
|---|---|
| **Task** (product) | One use of a capability: a question, its plan, its runs, its artefacts. Today the code row `project` (`core/schema.py` table `project`). After this slice the code row `task`. |
| **task NNN** (process) | A numbered engineering slice (`docs/tasks/NNN-*`, "task 033"). Unchanged by this slice. In code comments "(task 022)" means this. The sweep must not touch these. |
| **Project** (product) | A collection of Tasks. Today the code row `portfolio`; after this slice the code row `project`. |
| **Capability** | A type of analysis. One exists: **Evidence search**, code key today `evidence_base`, after this slice `evidence_search`. |
| **Component** | A backend processing step of a capability (search, screen, extract, …). Unchanged. |
| **Agent** | The screen name for the planning/steering/Q&A surface. Backend name today `orchestrator`. See fork F2 for how far the code follows. |
| **Agent overlay** | The chat sidebar (`ChatSidePanel.tsx`), today `aria-label="Project chat"`, shown on every tab but Plan. After the slice: shown on every tab including Agent. |
| **Task Agent** | The primary chat of a Task — today the planning conversation (`kind = planning`, one active per Task, tab label "Planning"). After the slice: named "Task Agent", pinned first in the chat list, visually distinct. |
| **Chat** | Any other conversation with the Agent (`kind = chat`). The word stays "chat" on screen. |
| **Modes** | Withdrawn by the 2026-09-04 amendment. Planning / running / Q&A remain internal states (conversation `kind` + run status), never shown as words. |
| **Artefact** | Something a Task generates. Unchanged word; British spelling stays. |
| **Screen word / code word** | The split ADR 0031 decision 2 made deliberate; this slice ends it. After the slice the screen word and the code word are the same word. |
| **Stored-data vocabulary** | String values that live in rows (`capability_run.capability`, `event_log.event_type`, JSONB payload values). Renamed only where § V-rules say so. |
| **Frozen** | `docs/specs/sources/**` — not rewritten by the sweep (ADR 0002). The one exception is the owner-maintained definitions file, which the owner edits directly. |
| **Historical** | Merged task docs (`docs/tasks/001–034`), ADRs 0001–0034, `docs/verification/`. Not rewritten (012 precedent). |
| **V1–V8** | Defect ids. Goal, scope, invariants, plan phases and rubric items cite these. |
| **F1–F5** | Owner forks at this gate. |

## Read first

- [Definitions](../../specs/sources/vocabulary/policy-atlas-definitions.md) (owner-maintained; amended 2026-09-04) — the source of every target word.
- [ADR 0031](../../adr/0031-portfolio-layer-above-the-project.md) decision 2 — the split this slice retires, and why it was made (cost of the rename).
- [ADR 0032](../../adr/0032-portfolio-membership-many-to-many.md), [ADR 0033](../../adr/0033-organisation-tenancy-and-global-admin-read.md) — the membership and tenancy rows the rename carries.
- [ADR 0035](../../adr/0035-public-task-read-access.md) and [037-public-projects/contract.md](../037-public-projects/contract.md) — `project.is_public`, the 11-route public read leg and the public share link (`/projects/{id}/results`), all renamed here.
- [data-model.md](../../specs/system/data-model.md) § Entity hierarchy — the paragraph that must read `task`/`project` after the slice.
- [web-api.md](../../specs/system/web-api.md) — every route; § Deprecations, whose additive-only rule this slice breaks by ADR.
- [prompting.md](../../specs/system/prompting.md) — why prompt text is out (§ Out of scope).
- `docs/deferred.md` § Task lifecycle IA (the rename entry) and § Organisations (the ops CLI entry) — both discharged here.
- Precedent migration: `backend/alembic/versions/e7b4d2a1c8f3_evidence_scope_rename.py` — a pure rename with explicit constraint renames.
- Code spine: `core/schema.py` · `api/contract/{projects,portfolios,sse}.py` · `api/routers/*` · `api/lifecycle.py` · `api/readmodels/repository.py` · `runtime/steering_events.py` · `ops/cli.py` · `frontend/src/lib/vocabulary.ts` · `frontend/src/routes.tsx` · `frontend/src/views/lifecycle.ts`.

## Surface map

What the slice touches, with the size measured on `dev` at `8626594f`.

| Surface | Today | After | Size |
|---|---|---|---|
| DB table `project` (columns incl. 037's `is_public`; +24 `project_id` columns on 23 tables and 1 view; 5 CHECK · 11 UNIQUE · ~35 FK · 4 index names) | `project`, `project_id`, `*_project` | `task`, `task_id`, `*_task` | 1 migration revising head `b2f6a9d4c1e7`; constraint names listed in the plan |
| DB table `portfolio`, `portfolio_membership` (`portfolio_id` ×2) | | `project`, `project_membership`, `project_id` | same migration, second step |
| `capability_run.capability` value + `ck_capr_capability` | `'evidence_base'` | `'evidence_search'` | UPDATE + CHECK swap |
| `event_log.event_type` values | `project.renamed`, `project.archived` | `task.renamed`, `task.archived` on new writes; readers accept both | 2 writers, 3 readers |
| JSONB payload values `decided_by`/`authored_by` | `'orchestrator'` | `'agent'` on new writes; readers normalise | `steering_events.py`, `runner.py`, `continuation.py` |
| API paths | `/api/v1/projects/**` (22 paths, 11 of them with 037's conditionally-public leg) · `/api/v1/portfolios/**` (2) · `/api/v1/waitlist` (unchanged) | `/api/v1/tasks/**` · `/api/v1/projects/**` | 8 router prefixes (incl. `public_read_router`); `openapi.json` + `gen/types.ts` regenerated |
| API schemas | `Project*` (4) · `Portfolio*` (3) · fields `project_id`, `portfolio_id`, `portfolio_ids`, `from_project_id` | `Task*` · `Project*` · `task_id`, `project_id`, `project_ids`, `from_task_id` | `task_count` stays (already right) |
| SSE frame | `project.updated` / `ProjectUpdatedFrame` | `task.updated` / `TaskUpdatedFrame` | `contract/sse.py`, `routers/sse.py`, `sseFrame.ts` |
| Backend package | `policy_atlas.evidence_base` (+ `tests/evidence_base`) | `policy_atlas.evidence_search` | `git mv` + import rewrite; `prompt_hashes.json` keys re-pathed, values unchanged |
| Backend identifiers | `project*` 3,847 occ / 72 files · `portfolio*` 479 / 15 · tests ~9,400 / 110 + 689 / 23 (incl. 037's `test_public_access.py`, `test_public_flag.py`) | | mechanical sweep |
| Ops CLI + Makefile | `rows assign --project/--portfolio`; `PROJECT`/`PORTFOLIO` vars; "moved N project(s), M portfolio(s)" | `--task/--project`; `TASK`/`PROJECT`; "moved N task(s), M project(s)" | `ops/cli.py`, `ops/commands.py`, `Makefile:42,72` |
| Log / trace field | `project_id=` kwarg (454 sites); Langfuse metadata `project_id` | `task_id` | breaks saved Langfuse filters (§ Constraints) |
| Frontend routes (app router) | `/projects/:projectId[/results\|/sources\|/share\|/history]` · `/portfolios[/:portfolioId]` · 4 retired redirects | `/tasks/:taskId[/result\|/sources\|/share\|/history]` · `/projects[/:projectId]` · retired redirects dropped; legacy Task URLs per F3 | `routes.tsx`, `lifecycle.ts`, `LifecycleRoute.tsx`, 30 link sites |
| Frontend routes (public router, 037) | `/projects/:projectId[/results\|/sources/*]` in `PublicTaskShell`; `PUBLIC_TABS = [results, sources]` | `/tasks/:taskId[/result\|/sources/*]`; `PUBLIC_TABS = [result, sources]`; legacy `/projects/:id/results` redirects (F3) | `routes.tsx` `publicRouter`, `PublicTaskShell.tsx`, `publicView.tsx`, `StashAndSplashRedirect.tsx` |
| Public share link (037, **outward-facing**) | `ShareView.tsx:120` builds `${origin}/projects/${id}/results` | `${origin}/tasks/${id}/result` | links already copied by users break unless F3(b) |
| Frontend identifiers | `project*` 2,082 occ / 116 files · `portfolio*` 615 / 26 (incl. 037's `PublicTaskShell`, `publicView`, `publicAccess`, `PUBLIC_SHARE`) | `task*` · `project*` | collision audit first (§ Constraints) |
| `vocabulary.ts` | `TASK`/`PROJECT` objects + the split docstring | same exports; docstring says the words now match; `LIFECYCLE_LABELS.plan → agent: "Agent"`, `results → result: "Result"` | one file |
| User-visible "evidence base" copy | 17 production sites + `evidence-base.md` filename | per § V3 copy table | lead-owned |
| Leaked literals | 18 hard-coded Task/Project strings (§ V6 list) | routed through `vocabulary.ts` | |
| Agent overlay | `aria-label="Project chat"`, FAB "Open chat"/"Chat", tabs "Planning" + chats, library "Chats"; hidden on the Plan tab (`AppShell` `showChatPanel = … && !inWorkspace`) | § V8 copy table; shown on the Agent tab too, "Task Agent" pinned first and marked | `ChatSidePanel`, `ConversationTabs`, `ChatsLibrary`, `AppShell`, `WorkspaceView` |
| e2e | `/projects/`, "Results", "Read the evidence base", "evidence base" ×22 | new words | 6 specs |
| Living docs | `specs/capabilities/evidence-base/`, `data-model.md`, `web-api.md`, `index.md`, `deferred.md`, `knowledge/` | § V7 | |
| **Do not change** | `waitlist_entry` (036) · `is_public` column name and the `access` read field (037; only their table moves) · `evidence_scope` (already right) · `scope=all\|mine` listing param · `task_count` · `eb_iof_base_v1`/`eb_icf_base_v1` fingerprint ids · `evidence_base_coverage` stored steer-point id · every prompt's text · `orchestration_plan` table · `orchestrator_*` backend modules, env vars, span names (F2 default) · `docs/specs/sources/**` · historical docs | | |

## Defects

### V1 — The Task entity is called `project` in code and schema

- Schema: `project` → `task`; every `project_id` column → `task_id`; every
  constraint and index name carrying `project` → `task` (the plan lists them all,
  generated from `schema.py`, not typed). Composite FK guards (`fk_*_scope_project`
  → `fk_*_scope_task`) keep their shape. The view `finding_reference_union` is
  recreated with the new column name.
- Code: `core/schema.py`, every reader and writer, tests that match constraint
  names literally (`pytest.raises(IntegrityError, match="fk_grr_scope_project")`).
- API: `/api/v1/projects/**` → `/api/v1/tasks/**` on all eight routers,
  including 037's `public_read_router` (the conditionally-public leg keeps its
  auth semantics — ADR 0035 unchanged in behaviour); `ProjectCreate/Update/Out`
  → `TaskCreate/Update/Out`; `project_id` → `task_id` in every schema;
  `Page_TaskOut_`; `is_public` and `access` keep their names.
- Events: new writes emit `task.renamed`/`task.archived`; SSE frame `task.updated`.
  Readers (`readmodels/repository.py` `_EVENT_KINDS`, `routers/sse.py`) accept
  the old kinds too, because `event_log` is append-only and existing rows keep
  their words. Human text "Renamed the task." / "Archived the task.".
- Frontend: routes `/tasks/:taskId/**` in **both** routers (app and 037's
  public); the public share link builder (`ShareView.tsx:120`) emits
  `/tasks/{id}/result`; `useProject → useTask`, `ProjectOut →
  TaskOut`, `mockProject → mockTask`, `ProjectSettingsMenu → TaskSettingsMenu`,
  and so on; query-key prefix `"projects"` → `"tasks"`.
- Ops CLI and Makefile: `--task`, `TASK`.
- Logs and traces: kwarg `task_id`; Langfuse metadata key `task_id`.
- Invariant I1: after the migration no object in the live schema carries the
  word `project` in the old sense; `pg_class`/`pg_constraint`/`pg_indexes`
  greps for `project` return only V2's new objects. The `GET /api/v1/tasks/{id}`
  read of a pre-migration row equals the pre-migration `GET /api/v1/projects/{id}`
  read field-for-field, modulo renamed keys.

### V2 — The Project entity is called `portfolio`

- Schema: `portfolio` → `project`; `portfolio_membership` → `project_membership`;
  `portfolio_id` → `project_id` (2 columns); constraint/index names follow.
  **Order matters:** V1's renames run first in the same migration, so `project_id`
  is free when V2 claims it. The downgrade reverses in the opposite order.
- API: `/api/v1/portfolios/**` → `/api/v1/projects/**`; `Portfolio*` →
  `Project*`; `portfolio_ids` → `project_ids`; `from_project_id` →
  `from_task_id`; `task_count` unchanged.
- Frontend: `/projects[/:projectId]`; `usePortfolios → useProjects`,
  `PortfoliosView → ProjectsView`, `PortfolioDetailView → ProjectDetailView`,
  DOM ids `new-portfolio-name → new-project-name`, `new-task-portfolio →
  new-task-project`, search param `?portfolio=` → `?project=`; query-key prefix
  `"portfolios"` → `"projects"`.
- Ops CLI: `--project`, `PROJECT` now mean the Project entity.
- Invariant I2: membership, visibility inheritance and the one-organisation span
  rule (ADR 0033 § 6) behave identically — the 033 tenancy tests pass unchanged
  except for renamed identifiers.

### V3 — The capability is called `evidence_base`

- Package: `policy_atlas.evidence_base` → `policy_atlas.evidence_search`;
  `tests/evidence_base` → `tests/evidence_search`; `scripts/prompt_hashes.json`
  keys re-pathed with **identical hash values** (the guard proves no prompt text
  moved).
- Capability key: `'evidence_base'` → `'evidence_search'` in
  `capability_run.capability` (UPDATE in the migration), `ck_capr_capability`,
  `runner.py`, `frontend/src/lib/capabilities.ts`, the `/new?capability=` param.
- Spec bundle: `docs/specs/capabilities/evidence-base/` →
  `docs/specs/capabilities/evidence-search/`; frontmatter title "Evidence search";
  `index.md` links follow. The frozen `sources/evidence-base-ux/` and
  `backend-evidence-base-build-spec.md` do **not** move.
- **Kept, as stored-data vocabulary** (no user sees them; renaming changes
  fingerprints or model-facing schema): extraction profile ids `eb_iof_base_v1`,
  `eb_icf_base_v1`; steer-point id `evidence_base_coverage` (in
  `orchestration_plan.payload`, pause records and the planner's JSON-schema
  description). Recorded in `deferred.md` as accepted residue with the reason.
- User-visible copy. "Evidence base" is used in two senses today: the
  **capability** (→ "Evidence search") and the **body of evidence / the report**
  (→ "report" or "evidence", never "evidence search"). Lead-owned copy table,
  binding:

| Site | Today | After |
|---|---|---|
| `ArtefactView` heading, tab title, loading/failed copy | "Evidence base" / "Loading the evidence base" / "The evidence base couldn't be loaded." | "Report" / "Loading the report" / "The report couldn't be loaded." |
| `ArtefactView:148` sparsity note | "The evidence base is thin here — …" | "The evidence is thin here — …" |
| `ArtefactView:1128` partial banner | "…evidence base. Citations were never attached…" | "…report. Citations were never attached…" |
| `SourcesView`, `sourcesPresentation`, `journey/presentation:26` | "Cited in the evidence base" | "Cited in the report" |
| `journey/presentation:48,49`, `runProgress:49` | "The evidence base is ready [with gaps]" | "The report is ready [with gaps]" |
| `JourneyPane:204`, `runProgress:313` | "Read the evidence base" | "Read the report" |
| `ContextBar`, `ChatsLibrary` chip | "Evidence base" | "Report" |
| `ChatMessages:114`, backend `chat_backend.py:97`, `continuation.py:1113` | "The evidence base does not hold this." | "The evidence does not hold this." (same shape for the other two) |
| backend `stage_vocabulary.py:27` | "Writing the evidence base" | "Writing the report" |
| backend `steering.py:773` | "The evidence base looks right" | "The evidence looks right" |
| backend `steering.py:1338` | "this will ADD TO your evidence base" | "this will ADD TO your evidence" |
| backend `repository.py:1128–1138` | "…an evidence-base step." / "Opened an evidence-base run." | "…an evidence-search step." / "Opened an evidence-search run." |
| `mock/api.ts:751`, `mock/fixtures.ts:418` | "Preparing a decision-ready evidence base" | "Preparing a decision-ready report" |
| `artefactPresentation.ts:485` download fallback | `evidence-base.md` | `report.md` |
| `routes.tsx:102` retired redirect `/evidence-base` | exists | dropped with the other retired redirects |

- Invariant I3: `grep -ri "evidence base\|evidence_base\|evidence-base"` over
  `backend/src`, `frontend/src`, `frontend/e2e`, `docs/specs` (excluding
  `sources/`) returns only the kept ids above and `docs/specs/index.md`'s
  frozen-source lines.

### V4 — The orchestrator surface has no screen name

- Screen: the overlay is the **Agent** (`aria-label="Agent"`, FAB "Open the
  Agent"/"Agent"); the check-in attribution reads "The Agent decided"; the
  planning composer label "Message the Task Agent".
- Wire: `decided_by`/`authored_by` literal `"orchestrator"` → `"agent"` in
  `steering_events.py` (`DecidedBy`), the OpenAPI literal and `store/types.ts`.
  New writes store `agent`; the read path that projects check-ins and steering
  history normalises `orchestrator` → `agent` (one mapping, one place), because
  `event_log` payloads are not rewritten.
- **Default (fork F2): backend internals keep `orchestrator`** — modules
  `orchestrator_prompt.py`, `orchestrator_backend.py`, class
  `OpenAIOrchestratorBackend`, log event names `orchestrator.*`, Langfuse spans
  `orchestrator:*`, env vars `POLICY_ATLAS_ORCHESTRATOR_MODEL` /
  `_TRIAGE_MODEL`, and the `orchestration_plan` table. Reason: two of those
  are production config, "agent" is a generic word already used in the specs
  for any LLM actor, and the definitions doc records the backend name as a note,
  not a demand. Recorded in `deferred.md` § Vocabulary as an open seam.
- Invariant I4: no user-visible string says "orchestrator"; a pre-migration
  check-in decided by the orchestrator renders "The Agent decided".

### V5 — Tab labels differ from the definitions

- `LIFECYCLE_LABELS`: `plan: "Plan"` → `agent: "Agent"`; `results: "Results"`
  → `result: "Result"`. Sources · Share · History unchanged.
- Routes: the Agent tab stays the task's index route (`/tasks/:taskId`, empty
  segment — no `/agent` segment); Result's segment `/results` → `/result`.
  `taskDestination()`, `LifecycleRoute`, `LifecycleBar`'s `end` match and
  `RUN_FINISHED_MESSAGE` ("…in the Result tab") follow.
- The Agent tab keeps today's layout (planning pane + plan document rail) and
  additionally shows the chat list (§ V8); it is where the Task Agent lives.
- Invariant I5: the lifecycle bar reads Agent · Result · Sources · Share ·
  History in that order; tab locking by run status is unchanged.

### V6 — Eighteen literals leaked past `vocabulary.ts`

ADR 0031 already calls these defects. The rename makes the screen word and the
code word identical, so a literal no longer *mis*labels — but a literal still
bypasses the one place copy is maintained. Route each through `TASK`/`PROJECT`
or a named `COPY` key: `NotFoundView:10`, `AppShell:70,88,89,113,128,165,176,
186,349`, `ShareView:44`, `VisibilityControl:14`, `errors.ts:19,26,32`,
`historyPresentation:46,47`, `PlanningPane:98`, `ChatSidePanel:132`,
`decisionsPresentation:9`, `WorkspaceView:24` (tab title), `runProgress:280`,
and 037's `PUBLIC_SHARE.warning` ("this Task's results…" → `TASK.one`,
"results" → "result and sources" in prose) plus `AppShell`'s public-branch
`NavBar aria-label="Task"`.
Fixture prose (`mock/fixtures.ts:43,111`, `mock/api.ts:247`) is updated in
words only.

- Invariant I6: `grep -nE '"(Task|Tasks|Project|Projects)[ "\.]'` over
  `frontend/src` (excluding `vocabulary.ts` and tests) returns nothing.

### V7 — The living docs say the old words

- New spec `docs/specs/system/vocabulary.md` (type: System contract): the
  glossary distilled from the frozen definitions, plus the code-word table
  (entity → table → route → TS type) and the two-senses-of-task rule. Listed in
  `index.md` and its routing table.
- `data-model.md` § Entity hierarchy, `web-api.md` (every path, § Deprecations
  gains the 038 entry), `execution-orchestration.md` and `plan-as-object.md`
  where they name the row, `index.md`, `AGENTS.md`, `docs/agentic-ops/harness.md`
  where it names routes.
- `docs/deferred.md`: the rename entry and the ops-CLI entry marked discharged;
  new § Vocabulary holding the accepted residue (V3 kept ids, F2 internals,
  bookmarks per F3).
- ADR 0031: decision 2 marked **superseded by ADR 0036**; ADR 0036 written at
  step 4.
- `docs/knowledge/`: bodies that describe current code are updated in words;
  **filenames are OKF ids and do not change** (`coverage-base-project-pool-wide.md`,
  `harness-scope-lookup-project-scoped.md` keep their names; each gains one
  line saying the row is now `task`). `make okf-validate` green.
- Historical docs and frozen sources untouched (§ Terms).
- Invariant I7: `docs/specs/index.md` frozen-sources list carries a one-line
  mapping note (frozen `project`/`Evidence Base`/`orchestrator` → living
  `task`/`Evidence search`/`Agent`) so a cold reader can read a source.

### V8 — The Agent tab does not show the Task's chats, and the primary chat has no name

Today the chat sidebar is hidden on the Plan tab, the planning conversation is
labelled "Planning", and nothing marks it as the Task's primary chat. The
2026-09-04 amendment fixes all three. Lead-owned copy, binding once approved (fork F4):

| Surface | Today | After |
|---|---|---|
| Overlay region (`ChatSidePanel`) | "Project chat" | "Agent" |
| Closed-state button | "Open chat" / "Chat" | "Open the Agent" / "Agent" |
| Overlay on the Agent tab | hidden (`!inWorkspace`) | shown — the tab's chat list; the planning pane stays the main column |
| Primary chat tab and library chip | "Planning" | "Task Agent", pinned first, with a distinct marker (icon + tone; the plan picks the exact treatment from the brand layer) |
| Other chats — tabs, library, new button | "Chats" / "New chat" | unchanged: chats are chats |
| Planning composer label | "Message the planner" | "Message the Task Agent" |
| Running state eyebrow (`runProgress`) | "RUNNING" | unchanged |
| History category | "Planning" / "Question" | unchanged |

No new state is built: the Task Agent is the existing `kind = planning`
conversation; pinning is a sort rule in `ConversationTabs`/`ChatsLibrary`
(planning first, then chats by recency — today's order already places it first).
Showing the overlay on the Agent tab is one condition in `AppShell` plus the
layout check that the planning pane and the sidebar do not both render the
planning conversation at once (the sidebar's Task Agent entry focuses the main
pane instead of opening a second copy).

- Invariant I8: on the Agent tab the chat list is visible with "Task Agent"
  first and marked; no user-visible chat is named "Planning"; the word "chat"
  is unchanged everywhere else.

## Forks (owner rulings needed at this gate)

| # | Question | Options | Recommended default and why |
|---|---|---|---|
| **F1** | Rename the DB and code at all, or only the API + screen? | (a) full rename, schema included (this contract) · (b) API + frontend only, `vocabulary.ts` stays the mapping | **(a)** — the owner's 2026-08-24 ruling and this ask both say schema; (b) leaves the split ADR 0031 made and keeps every new reader learning it. |
| **F2** | How far does `orchestrator` → `agent` reach in the backend? | (a) screen + wire only (default) · (b) also modules, classes, log/span names · (c) also env vars + `orchestration_plan` table | **(a)** — (b) is 468 occurrences for no user gain and breaks Langfuse history; (c) is a production-config change. Upgrade later if the word keeps hurting. |
| **F3** | Old URLs: `/projects/:id` now means a Project; a bookmarked Task URL with the same shape lands on "not found". **Since 037, `/projects/{id}/results` is also the public share link people copy and send outside the app.** | (a) no redirect logic; users re-share · (b) legacy redirects: `/projects/:id/(results\|sources/*\|share\|history)` → `/tasks/:id/…` in both routers (these paths have no Project counterpart, so the redirect is unambiguous), and bare `/projects/:id` retries the id as a Task on a Project 404 | **(b)** — changed from (a) after 037 merged: a public link is outward-facing and may already be in someone's email. About 20 lines; recorded in ADR 0036 with a removal date. |
| **F4** | Copy tables: "Task Agent" as the pinned primary chat and its marker (V8), "Report" for the artefact page (V3), "Message the Task Agent" (V4). | approve the tables · edit words in place | approve — copy-text principle: labels over explainers. |
| **F5** | Open PRs #62 (Langfuse sessions, 7 src files) and #52 (in-app feedback, 19) will conflict with the sweep. (#61 merged 2026-09-04 and is now inside this branch.) | (a) merge them first, then re-merge `dev` here · (b) land 038 first; they rebase with the sweep script re-run | **(a)** if they are days away; otherwise (b) — the plan ships the sweep as a re-runnable script exactly so a rebase is one command. |

## Scope / Out of scope

- **In:** everything in § Surface map; one alembic revision (pure rename + one
  UPDATE); `make openapi-sync`; the sweep script committed under `scripts/`
  (re-runnable, so open branches can rebase); tests renamed in lockstep; e2e
  specs; `frontend/src/mock/*`; ops CLI; Makefile vars; living docs; ADR 0036.
- **Out:** **Links** and **Context** as data-model concepts (the definitions name
  them; nothing implements them — the chat's single `entry_artefact_id` is not a
  set; building either is a feature slice). Any new tab content (Share stays as
  033 left it). New capabilities and the options-scoping spec (PR #63 — it
  already uses "Evidence search"; it inherits the glossary). **Prompt text**: no
  prompt says a different word to the model after this slice (`prompt-guard`
  hash values identical); "You are the orchestrator of Policy Atlas" waits for a
  prompt slice with a version bump and the refine-replay loop. Backend
  `orchestrator` internals (F2 default). `eb_*` fingerprint ids and the stored
  steer-point id. Rewriting `event_log` rows. A mode enum. Historical docs,
  frozen sources, `docs/knowledge/` filenames. The workspace-cluster re-parenting
  (still deferred; unaffected). Metabase saved questions (owner-operated; see
  § Constraints). **Future direction from the definitions § Future direction, recorded as seams in
  `deferred.md` § Vocabulary, not built:** re-running a Task or part of it from
  any chat; active chats reachable app-wide from the round Agent icon; any
  Tasks or Projects as chat context (meta-analysis); "chat more functional" as
  its own task.

## Constraints & approval gates

**Gated changes this contract asks approval for** (Tier 4):

1. **Schema** — one migration: `rename_table` ×3, column renames ×27, constraint
   and index renames (listed in the plan), one `UPDATE capability_run SET
   capability='evidence_search'` with the CHECK swapped, the union view recreated.
   No shape change, no row lost. Downgrade reverses every step.
2. **Public interface** — `/api/v1` paths and schema names change without a
   deprecation window. `web-api.md` § Deprecations records the break by ADR
   0036; the only consumers are this repo's frontend and e2e (deferred.md).
3. **Production config** — none under F2(a). `Makefile` variable names for the
   ops CLI change (`PROJECT`→`TASK`, `PORTFOLIO`→`PROJECT`).
4. **Deploy posture** — public share links minted on production before this
   deploy change shape (F3). The migration task runs before the new backend image;
   between the two the old image errors on renamed tables. Accepted brief
   outage on staging then production, in that order; no dual-name window.
   Rollback = deploy the previous image and `alembic downgrade -1` (ADR 0036
   § Rollback names the exact commands).

**Mechanics the plan must honour:**

- **Collision-safe order.** `project`→`task` first, then `portfolio`→`project`,
  in the schema, the sweep and the docs. The sweep uses a placeholder token
  for step 2 so no `project` from step 1 is re-renamed. A pre-sweep **collision
  audit** lists every identifier that would become a duplicate (the frontend
  already has `TasksListView`, `NewTaskView`, `useCreateTask`, `TaskListRow`,
  `taskDestination`, `task_count`) and the plan resolves each before the sweep
  runs.
- **Exact tokens only.** The sweep matches word-bounded identifiers and path
  segments, never the substring "project" inside `uv run --project backend`
  (Makefile), "(task NNN)" comments, `.claude/agents`, or `docs/specs/sources/**`.
- **Generated files** — `frontend/openapi.json` and `frontend/src/api/gen/types.ts`
  are regenerated by `make openapi-sync`, never edited.
- **Prompt guard** — `scripts/prompt_hashes.json` keys are re-pathed; the
  values must not change. The build records the before/after diff of that file
  as evidence.
- **Analytics** — the Metabase dashboards on staging Aurora query `project` and
  `portfolio` by name and will break on migration. Owner action after merge;
  the PR names it.
- **No dependency, CI or infra change.** `infra/DEPLOYMENT.md`'s lock-monitoring
  SQL is updated in words.

## Public / private boundary

Everything in this slice is committable. No evidence text, traces or
credentials move. The frozen definitions doc is public-safe (product vocabulary).

## Model route

`n/a` — no inference-bearing change. Prompt text is out of scope by contract.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves** — no new column, flag or mode enum.
- **No behaviour change** — every test that fails after the sweep fails on a
  name, or the slice has done more than rename.
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md).

## Stop conditions

Halt and escalate when: a rename would need a shape change (a column that
cannot be renamed in place, a value that must be rewritten in `event_log`); a
collision the audit missed surfaces mid-sweep; a prompt hash value changes; an
open PR's merge order makes the branch unrebasable; or the budget is spent.

## Acceptance checks

- `make verify` green — includes `okf-validate`, backend tests, `drift-check`,
  `prompt-guard`, `audit-paths`, frontend typecheck/lint/test/build.
- Migration round-trip test: `upgrade` → `downgrade` → `upgrade` on the test DB
  against a seeded pre-migration fixture (a task in a project, one of them
  `is_public`, one
  `capability_run` with `'evidence_base'`, one `project.renamed` event, one
  check-in decided by `orchestrator`); after upgrade the read models return the
  same content under the new names (I1, I2, I4).
- Invariant greps I3 and I6 run as a script in `verification.md`.
- `pnpm e2e` (mock-mode journey) green with the new words and routes (I5, I8).
- **Live check, scoped:** on staging after the migration, one existing Task
  opens on `/tasks/{id}` with its report, sources and history intact; its
  Project lists it on `/projects/{id}`; one public Task opens signed-out on
  `/tasks/{id}/result` and its pre-rename link `/projects/{id}/results`
  redirects there (F3); the ops CLI `rows assign --task` dry-runs. One cheap full-chain smoke (`make fe-api-smoke`). No full live e2e.
- `pip-audit`/deps unchanged: `uv.lock` and `pnpm-lock.yaml` diff empty.

## Verification evidence expected

In [verification.md](verification.md): the `make verify` tail; the migration
round-trip output; the `prompt_hashes.json` diff (paths only); the collision
audit output and how each was resolved; the invariant-grep outputs; the e2e
summary; the staging live-check notes with the URLs opened; the Metabase note;
public-safety confirmation; the deferred-residue list.

## Risk tier & review focus

**Tier 4** — migration + public-API change + ADR + rollback plan +
human-approved plan. Adversarial review at contract and plan stage via
`codex-rescue` (read-only briefs); step-7 stack per the spine.

Review focus: a missed rename that still compiles (a `project_id` that now
means the Project but reads a Task — the two-step order makes this possible);
tenancy predicates renamed but not re-read (ADR 0033 tests are the guard);
readers of stored vocabulary that do not accept the old value; anything that
changed behaviour, not just a name.
