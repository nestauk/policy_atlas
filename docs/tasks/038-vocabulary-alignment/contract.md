# Task contract: 038-vocabulary-alignment

One implementation slice. Keep it reviewable. Boundaries are in
[AGENTS.md](../../../AGENTS.md). Specs are in [docs/specs/](../../specs/index.md).

> **Status:** **approved 2026-09-04 · owner** (forks F1–F5 ruled in an
> interview the same day; rulings folded in below).
> Contract approved (before planning): 2026-09-04 · owner ·
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
> **Amendments 2026-09-04** (owner + colleague, folded into the living
> [vocabulary.md](../../specs/vocabulary.md); the same-day snapshot is frozen under
> `sources/vocabulary/`):
> the Agent tab hosts all of a Task's chats in a sidebar; chats stay **chats**;
> the primary (planning) chat is the **Task Agent**, pinned first and visually
> distinct. The mode labels are withdrawn. V5 and V8 are rewritten to this.
>
> **Contract-stage adversarial review (Codex, read-only) ran 2026-09-04** at
> `85931f3e`: 15 findings, verdict "material change needed". All 15 accepted and
> folded (§ Adversarial findings). Material folds — one more table in the
> migration (A1), a reversible-values rollback (A2), plan-deserialisation
> canonicalisation (A3), the public-sharing events (A4), V8 scoped to the
> owner with one Task Agent (A9, A10), the V11 seam pinned (A11), the live
> relevance annotator kept (A12) — reopened the 🛑; **re-approved as folded
> 2026-09-04 · owner** (A8 taken as option 2: the living vocabulary moved to
> `docs/specs/vocabulary.md`).
>
> **Owner forks F1–F5** are ruled (§ Forks). Two rulings bind the whole slice:
> **(R1)** like-for-like word swaps in prompt text need **no** version bump and
> **no** replay loop — the prompt hash guard is updated and the diff reviewed as
> words-only; **(R2)** the persona is renamed `orchestrator` → `agent` at every
> layer, including env vars, the `orchestration_plan` table and the prompt text.

## Goal

Make the words in the code, the schema, the API and the screen the same words the
team uses ([vocabulary.md](../../specs/vocabulary.md)).
Today three vocabularies coexist: the screen says Task/Project/Evidence search, the
code and database say `project`/`portfolio`/`evidence_base`, and the chat surface
has no name at all. Twelve numbered defects, V1–V12. **No product behaviour change**:
every row, route and screen does after the slice what it did before, under a new
name. V9 (traces group by Task), V10 (two riders from `deferred.md`), V11
(the post-sign-in landing fix) and V12 (repo hygiene) are the non-rename items,
each folded in by the owner on 2026-09-04.

## Deliverable

One PR on `task/038-vocabulary-alignment` that:

- Renames the `project` entity to `task` in the schema, the code, the API and the
  frontend (V1).
- Renames the `portfolio` entity to `project` in the same places (V2).
- Renames the Evidence search capability from `evidence_base` in the package, the
  capability key, the stored value and the user-visible copy (V3).
- Renames the orchestrator persona to **Agent** on screen, on the wire, and throughout the backend, its config and its prompts (V4).
- Relabels the lifecycle tabs Agent · Result · Sources · Share · History (V5).
- Routes the leaked hard-coded Task/Project literals through the copy module (V6).
- Updates the living docs, writes the glossary spec, amends ADR 0031 (V7).
- Shows a Task's chats in the Agent tab with the **Task Agent** pinned first (V8).
- Groups every Langfuse trace of a Task under one session id, the task id (V9).
- Renames the search loop's `http_budget` to `call_budget` and deletes the dead `RunPane`/`JourneyPane` views (V10).
- Makes the app land on the stashed deep link after a sign-in round trip (V11).
- Trims AGENTS.md to protocol, landmines and a phase pointer, and deletes the dead files and exports the tools found (V12).

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
| **Evidence base** | The collection of documents an Evidence search collects. **The phrase stays on screen in that sense** (owner ruling 2026-09-04). It stops being used for the capability and for the report. |
| **Report** | The synthesised artefact on the Result tab (034's word). Copy that says "evidence base" but means this page changes to "report". |
| **Component** | A backend processing step of a capability (search, screen, extract, …). Unchanged. |
| **Agent** | The one persona users talk to: on screen, on the wire and in code. Backend name today `orchestrator` — one prompt preamble ("You are the orchestrator of Policy Atlas") serves the planning, steering, watch and chat moments. Renamed at every layer (F2). |
| **Agent overlay** | The chat sidebar (`ChatSidePanel.tsx`), today `aria-label="Project chat"`, shown on every tab but Plan. After the slice: shown on every tab including Agent. |
| **Task Agent** | The primary chat of a Task — today the planning conversation (`kind = planning`, one active per Task, tab label "Planning"). After the slice: labelled "Task Agent", pinned first in the chat list. **Which row:** the active planning conversation; if none is active (the run closed it), the most recently closed one. The stored `kind` value stays `planning`. |
| **Chat** | Any other conversation with the Agent (`kind = chat`). The word stays "chat" on screen. |
| **Modes** | Withdrawn by the 2026-09-04 amendment. Planning / running / Q&A remain internal states (conversation `kind` + run status), never shown as words. |
| **Artefact** | Something a Task generates. Unchanged word; British spelling stays. |
| **Screen word / code word** | The split ADR 0031 decision 2 made deliberate; this slice ends it. After the slice the screen word and the code word are the same word. |
| **Stored-data vocabulary** | String values that live in rows (`capability_run.capability`, `event_log.event_type`, JSONB payload values). Renamed only where § V-rules say so. |
| **Frozen** | `docs/specs/sources/**` — never edited, not rewritten by the sweep (ADR 0002). The definitions snapshot there is frozen; the living vocabulary is `docs/specs/vocabulary.md`. |
| **Historical** | Merged task docs (`docs/tasks/001–034`), ADRs 0001–0034, `docs/verification/`. Not rewritten (012 precedent). |
| **V1–V12** | Defect ids. Goal, scope, invariants, plan phases and rubric items cite these. |
| **Session** | Langfuse's grouping of traces. Set by passing `session_id` into the tracing helpers (`core/tracing.py` `_session_scope`). Today: the conversation id for planning and chat turns, nothing for runs. |
| **F1–F5** | Owner forks at this gate. |

## Read first

- [vocabulary.md](../../specs/vocabulary.md) (living, owner-maintained; the 2026-09-04 snapshot is frozen under `sources/vocabulary/`) — the source of every target word.
- [ADR 0031](../../adr/0031-portfolio-layer-above-the-project.md) decision 2 — the split this slice retires, and why it was made (cost of the rename).
- [ADR 0032](../../adr/0032-portfolio-membership-many-to-many.md), [ADR 0033](../../adr/0033-organisation-tenancy-and-global-admin-read.md) — the membership and tenancy rows the rename carries.
- [ADR 0035](../../adr/0035-public-task-read-access.md) and [037-public-projects/contract.md](../037-public-projects/contract.md) — `project.is_public`, the 11-route public read leg and the public share link (`/projects/{id}/results`), all renamed here.
- [data-model.md](../../specs/system/data-model.md) § Entity hierarchy — the paragraph that must read `task`/`project` after the slice.
- [web-api.md](../../specs/system/web-api.md) — every route; § Deprecations, whose additive-only rule this slice breaks by ADR.
- [prompting.md](../../specs/system/prompting.md) — the versioning discipline that ruling R1 sets aside for like-for-like word swaps in this slice only.
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
| JSONB steer-point id (plan payload, pause records, planner schema description) | `evidence_base_coverage` | `evidence_search_coverage` on new writes and in the planner prompt; readers accept both | `orchestration_plan.py`, `steering.py`, `continuation.py`, `checkin_read.py`, `planner_prompt.py` |
| DB table `orchestration_plan` | `orchestration_plan` | `plan` (constraints `uq_oplan_*`, `fk_oplan_*` → `uq_plan_*`, `fk_plan_*`) | same migration |
| Backend persona identifiers | `orchestrator_prompt.py`, `orchestrator_backend.py`, `orchestrate.py`, `orchestration_plan.py`, `OrchestratorBackend`, `OpenAIOrchestratorBackend`, `StubOrchestratorBackend`, `OrchestrationPlan`, log events `orchestrator.*`/`orchestrate.start`, spans `orchestrator:*`, 468 occ / 31 files | `agent_prompt.py`, `agent_backend.py`, `agent.py`, `task_plan.py`, `AgentBackend`, `OpenAIAgentBackend`, `StubAgentBackend`, `TaskPlan` (`Plan` is taken by the wire shape), `agent.*`/`agent.start`, `agent:*` | mechanical sweep; breaks saved Langfuse span filters (§ Constraints) |
| Env vars (read in code, documented in `infra/DEPLOYMENT.md`; not set by the CDK stack) | `POLICY_ATLAS_ORCHESTRATOR_MODEL`, `POLICY_ATLAS_ORCHESTRATOR_TRIAGE_MODEL` | `POLICY_ATLAS_AGENT_MODEL`, `POLICY_ATLAS_AGENT_TRIAGE_MODEL` | code default + docs; any operator override must be renamed by hand before deploy |
| Prompt text (model-facing) | "You are the orchestrator of Policy Atlas…", "attributed to the orchestrator", "the orchestrator handles those", "the project's committed evidence", "the project frame", steer-point list incl. `evidence_base_coverage` | same sentences with `agent`, `task`, `evidence_search_coverage`; "evidence base" meaning the collection stays | 13 hash-guarded prompt files + 2 inline prompt strings; `prompt_hashes.json` values updated (R1) |
| API paths | `/api/v1/projects/**` (22 paths, 11 of them with 037's conditionally-public leg) · `/api/v1/portfolios/**` (2) · `/api/v1/waitlist` (unchanged) | `/api/v1/tasks/**` · `/api/v1/projects/**` | 8 router prefixes (incl. `public_read_router`); `openapi.json` + `gen/types.ts` regenerated |
| API schemas | `Project*` (4) · `Portfolio*` (3) · fields `project_id`, `portfolio_id`, `portfolio_ids`, `from_project_id` | `Task*` · `Project*` · `task_id`, `project_id`, `project_ids`, `from_task_id` | `task_count` stays (already right) |
| SSE frame | `project.updated` / `ProjectUpdatedFrame` | `task.updated` / `TaskUpdatedFrame` | `contract/sse.py`, `routers/sse.py`, `sseFrame.ts` |
| Backend package | `policy_atlas.evidence_base` (+ `tests/evidence_base`) | `policy_atlas.evidence_search` | `git mv` + import rewrite; `prompt_hashes.json` keys re-pathed, values unchanged |
| Backend identifiers | `project*` 3,847 occ / 72 files · `portfolio*` 479 / 15 · tests ~9,400 / 110 + 689 / 23 (incl. 037's `test_public_access.py`, `test_public_flag.py`) | | mechanical sweep |
| Ops CLI + Makefile | `rows assign --project/--portfolio`; `PROJECT`/`PORTFOLIO` vars; "moved N project(s), M portfolio(s)" | `--task/--project`; `TASK`/`PROJECT`; "moved N task(s), M project(s)" | `ops/cli.py`, `ops/commands.py`, `Makefile:42,72` |
| Log / trace field | `project_id=` kwarg (454 sites); Langfuse metadata `project_id` | `task_id` | breaks saved Langfuse filters (§ Constraints) |
| Langfuse session id (V9) | planning turns → planning conversation id (`routers/planning.py:419`); chat turns → chat conversation id (`chat_turns.py:927`); run start → none (`routers/runs.py` `run_plan(...)` omits `session_id`) | all three → the task id; the conversation id moves to trace metadata `conversation_id` | 3 call sites + 1 metadata key; the runner already threads `session_id` through steering, watch and continuation state |
| Frontend routes (app router) | `/projects/:projectId[/results\|/sources\|/share\|/history]` · `/portfolios[/:portfolioId]` · 4 retired redirects | `/tasks/:taskId[/result\|/sources\|/share\|/history]` · `/projects[/:projectId]` · retired redirects dropped; no legacy redirects (F3) | `routes.tsx`, `lifecycle.ts`, `LifecycleRoute.tsx`, 30 link sites |
| Frontend routes (public router, 037) | `/projects/:projectId[/results\|/sources/*]` in `PublicTaskShell`; `PUBLIC_TABS = [results, sources]` | `/tasks/:taskId[/result\|/sources/*]`; `PUBLIC_TABS = [result, sources]`; old public URLs stop resolving (F3) | `routes.tsx` `publicRouter`, `PublicTaskShell.tsx`, `publicView.tsx`, `StashAndSplashRedirect.tsx` |
| Public share link (037, **outward-facing**) | `ShareView.tsx:120` builds `${origin}/projects/${id}/results` | `${origin}/tasks/${id}/result` | links copied before the deploy stop working; staging-only today, users copy a new link (F3) |
| Frontend identifiers | `project*` 2,082 occ / 116 files · `portfolio*` 615 / 26 (incl. 037's `PublicTaskShell`, `publicView`, `publicAccess`, `PUBLIC_SHARE`) | `task*` · `project*` | collision audit first (§ Constraints) |
| `vocabulary.ts` | `TASK`/`PROJECT` objects + the split docstring | same exports; docstring says the words now match; `LIFECYCLE_LABELS.plan → agent: "Agent"`, `results → result: "Result"` | one file |
| User-visible "evidence base" copy | 17 production sites + `evidence-base.md` filename | per § V3 copy table | lead-owned |
| Leaked literals | 18 hard-coded Task/Project strings (§ V6 list) | routed through `vocabulary.ts` | |
| Agent overlay | `aria-label="Project chat"`, FAB "Open chat"/"Chat", tabs "Planning" + chats, library "Chats"; hidden on the Plan tab (`AppShell` `showChatPanel = … && !inWorkspace`) | § V8 copy table; shown on the Agent tab too, "Task Agent" pinned first and marked | `ChatSidePanel`, `ConversationTabs`, `ChatsLibrary`, `AppShell`, `WorkspaceView` |
| e2e | `/projects/`, "Results", "Read the evidence base", "evidence base" ×22 | new words | 6 specs |
| Living docs | `specs/capabilities/evidence-base/`, `data-model.md`, `web-api.md`, `index.md`, `deferred.md`, `knowledge/` | § V7 | |
| **Do not change** | `waitlist_entry` (036) · `is_public` column name and the `access` read field (037; only their table moves) · `evidence_scope` (already right) · `scope=all\|mine` listing param · `task_count` · `eb_iof_base_v1`/`eb_icf_base_v1` fingerprint ids · the stored `kind = planning` value · prompt *meaning* (only the words in the row above change) · `docs/specs/sources/**` · historical docs | | |

## Defects

### V1 — The Task entity is called `project` in code and schema

- Schema: `project` → `task`; every `project_id` column → `task_id`;
  **`project_source_snapshot` → `task_source_snapshot`** with its six
  `project_source_snapshot_id` columns → `task_source_snapshot_id` and the
  `uq_pss_*`/`fk_*_pss_*`/`uq_project_source_snapshot` names (A1); every
  constraint and index name carrying `project` → `task`. The plan checks in a
  **catalog-derived manifest** (`schema-manifest.md`, generated from
  `schema.py` by script, not typed) listing every table, column, constraint,
  index and view the migration touches; the migration and the round-trip test
  are written from it. Composite FK guards (`fk_*_scope_project` →
  `fk_*_scope_task`) keep their shape. The view `finding_reference_union` is
  recreated with the new column name. UUID keys: no sequences;
  `alembic_version` untouched.
- Code: `core/schema.py`, every reader and writer, tests that match constraint
  names literally (`pytest.raises(IntegrityError, match="fk_grr_scope_project")`).
- API: `/api/v1/projects/**` → `/api/v1/tasks/**` on all eight routers,
  including 037's `public_read_router` (the conditionally-public leg keeps its
  auth semantics; ADR 0036 amends ADR 0035's concrete `/projects/{id}/…` paths
  and keeps only its relational invariant — signed-in and public viewers share
  the *new* URL, A7); `ProjectCreate/Update/Out`
  → `TaskCreate/Update/Out`; `project_id` → `task_id` in every schema;
  `Page_TaskOut_`; `is_public` and `access` keep their names.
- Events: new writes emit `task.renamed`, `task.archived`,
  **`task.shared_publicly`, `task.unshared`** (037's public-sharing PATCH,
  `routers/projects.py`; A4); SSE frame `task.updated`. Readers
  (`readmodels/repository.py` `_EVENT_KINDS` and its human text,
  `routers/sse.py`) accept both generations of all four kinds, because
  `event_log` is append-only and existing rows keep their words. The
  round-trip fixture seeds all four old kinds. Human text "Renamed the task." /
  "Archived the task." / the sharing lines likewise.
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
  fingerprints): extraction profile ids `eb_iof_base_v1`, `eb_icf_base_v1`.
  Recorded in `deferred.md` as accepted residue with the reason.
- **Steer-point id** `evidence_base_coverage` → `evidence_search_coverage` in
  code and in the planner prompt (R1). Stored plan payloads and pause records
  are not rewritten. **Canonicalisation happens at deserialisation, not in
  two readers** (A3): `OrchestrationPlan.model_validate` runs at ten sites
  (run start, planning, SSE, continuation state, steering) and
  `validate_steer_point` rejects anything outside `STEER_POINTS`, so an old
  payload would fail before any reader saw it. Fix: a `mode="before"`
  validator on the steer-point field maps the old id to the new one, and the
  pause-record reader does the same through one shared helper. The round-trip
  test seeds an old `steer_point_defaults` payload and exercises run start.
- User-visible copy. "Evidence base" is used in three senses today. **Owner
  ruling 2026-09-04: the phrase stays for the collection of documents.** So:
  the **collection** keeps "evidence base"; the **report page** says "report";
  the **capability / run** says "evidence search". Lead-owned copy table,
  binding (rows marked *keep* change nothing):

| Site | Today | After |
|---|---|---|
| `ArtefactView` heading, tab title, loading/failed copy | "Evidence base" / "Loading the evidence base" / "The evidence base couldn't be loaded." | "Report" / "Loading the report" / "The report couldn't be loaded." |
| `ArtefactView:149` sparsity note | "The evidence base is thin here — …" | *keep* (collection) |
| `ArtefactView:1128` partial banner | "…evidence base. Citations were never attached…" | "…report. Citations were never attached…" |
| `SourcesView`, `sourcesPresentation`, `journey/presentation:26` | "Cited in the evidence base" | "Cited in the report" |
| `journey/presentation:48,49`, `runProgress:49` | "The evidence base is ready [with gaps]" | *keep* (collection; the run's output as a whole) |
| `JourneyPane:204`, `runProgress:313` | "Read the evidence base" | "Read the report" |
| `ContextBar`, `ChatsLibrary` chip (the chat's entry artefact) | "Evidence base" / "Clear evidence base context" | "Report" / "Clear report context" |
| `ChatMessages:114`, backend `chat_backend.py:97`, `continuation.py:1113` | "The evidence base does not hold this." / "…material on this question." / "theme is not in this evidence base" | *keep* (collection) |
| backend `stage_vocabulary.py:27` (synthesise stage) | "Writing the evidence base" | "Writing the report" |
| backend `steering.py:773`, `:1338` | "The evidence base looks right" / "this will ADD TO your evidence base" | *keep* (collection) |
| backend `repository.py:1128–1138` | "…an evidence-base step." / "Opened an evidence-base run." | "…an evidence-search step." / "Opened an evidence-search run." |
| `mock/api.ts:751`, `mock/fixtures.ts:418` | "Preparing a decision-ready evidence base" | *keep* (collection) |
| `artefactPresentation.ts:485` download fallback | `evidence-base.md` | `report.md` |
| `routes.tsx:102` retired redirect `/evidence-base` | exists | dropped with the other retired redirects |

- Invariant I3: `grep -r "evidence_base\|evidence-base"` over `backend/src`,
  `frontend/src`, `frontend/e2e`, `docs/specs` (excluding `sources/`) returns
  only the kept ids above and `docs/specs/index.md`'s frozen-source lines; and
  every remaining "evidence base" in user-visible copy is a *keep* row of the
  table (the build lists them in `verification.md`).

### V4 — The persona is called `orchestrator` in code and has no screen name

One persona, three names today: nothing on screen, `orchestrator` in the
backend, and "the orchestrator" in the prompts. After the slice it is **Agent**
everywhere (owner ruling F2, all three layers).

- Screen: the overlay is the **Agent** (`aria-label="Agent"`, FAB "Open the
  Agent"/"Agent"); the check-in attribution reads "The Agent decided"; the
  planning composer label "Message the Task Agent".
- Wire: `decided_by`/`authored_by` literal `"orchestrator"` → `"agent"` in
  `steering_events.py` (`DecidedBy`), the OpenAPI literal and `store/types.ts`.
  New writes store `agent`. **One typed helper** `canonical_actor()` in
  `steering_events.py` maps `orchestrator` → `agent` on read, and every
  projection of a stored `decided_by`/`authored_by` goes through it: the SSE
  steering frame (`routers/sse.py:486`), the decisions read model
  (`readmodels/repository.py:1176`), `checkin_read.py` and `continuation.py`
  (A5 — the first two were missing from the earlier list; both today
  filter on a literal set that would drop `agent`). Tested through SSE and
  REST with both values. `event_log` payloads are not rewritten.
- Backend: modules, classes, log event names and Langfuse span names per the
  surface map (`orchestrator_*` → `agent_*`; `OrchestrationPlan` → `TaskPlan`;
  `orchestration_plan.py` → `task_plan.py`; `orchestrate.py` → `agent.py`).
  The collision audit confirms `agent`/`Agent` is free in `backend/src` (today
  it appears only in docstrings) and that `.claude/agents/` is outside the sweep.
- Schema: table `orchestration_plan` → `plan`, with its constraint and index
  names (`*_oplan_*` → `*_plan_*`).
- Config: `POLICY_ATLAS_ORCHESTRATOR_MODEL` → `POLICY_ATLAS_AGENT_MODEL`,
  `POLICY_ATLAS_ORCHESTRATOR_TRIAGE_MODEL` → `POLICY_ATLAS_AGENT_TRIAGE_MODEL`
  in code defaults and `infra/DEPLOYMENT.md`. The CDK stack sets neither; the
  PR tells operators to rename any override in the task definition before
  deploying.
- Prompts (R1): "You are the orchestrator of Policy Atlas" → "You are the agent
  of Policy Atlas" and the other word swaps in the surface map row. No version
  suffix changes; `scripts/prompt_hash_guard.py --update` re-pins the hashes and
  the build records the diff. Prompt *meaning* is unchanged: the review checks
  the diff is words only.
- Invariant I4: `grep -ri orchestrat` over `backend/src`, `backend/tests`,
  `frontend/src`, `frontend/e2e`, `infra/DEPLOYMENT.md`, `Makefile`, `scripts`
  and `docs/specs` (excluding `sources/`) returns nothing; a pre-migration
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

- `docs/specs/vocabulary.md` (type: Product spec; created at the design
  phase, A8 option 2): the owner's living definitions plus § Code words. The
  build fills § Code words with the as-built table (entity → table → route →
  TS type) and keeps the two-senses-of-task rule. Listed in `index.md`; add it
  to the routing table.
- `data-model.md` § Entity hierarchy, `web-api.md` (every path, § Deprecations
  gains the 038 entry), `execution-orchestration.md` and `plan-as-object.md`
  where they name the row, `index.md`, `AGENTS.md`, `docs/agentic-ops/harness.md`
  where it names routes.
- `docs/deferred.md`: six entries marked discharged or corrected — the
  code-word/screen-word split (V1/V2) · the ops CLI reports in code words
  (V1/V2) · Langfuse trace grouping, second half: "accept the session view" (V9;
  turn-span consolidation stays open) · `capability_run.session_id` now filled
  from the API path (V9) · the workspace-cluster wording that says the cluster
  slice resolves the split (038 does, without re-parenting) · "rename/archive
  controls — no view exposes them yet" (stale since 032) · `http_budget` naming
  (V10) · `RunPane`/`JourneyPane` dead code (V10). New § Vocabulary holds the
  accepted residue (`eb_*` fingerprint ids, regenerated public links, Metabase
  and Langfuse filters, the Task Agent phase model).
- ADR 0036 must record (A6, A7, A8): the narrow supersession of `prompting.md`
  rule 12 for the enumerated word substitutions of this slice, with the hash
  changes and the semantic-equivalence check, and that it sets no general
  words-only precedent; the amendment of ADR 0035's concrete paths and of
  `web-api.md`'s additive-only rule for this one break. (A8 needs no ADR
  exception: the living vocabulary moved out of `sources/`, owner option 2.)
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
| Primary chat tab and library chip | "Planning" | "Task Agent", pinned first; the visible label is the marker — no extra icon (F4) |
| Other chats — tabs, library, new button | "Chats" / "New chat" | unchanged: chats are chats |
| Planning composer label | "Message the planner" | "Message the Task Agent" |
| Running state eyebrow (`runProgress`) | "RUNNING" | unchanged |
| History category | "Planning" / "Question" | unchanged |

No new state is built: the Task Agent is the existing `kind = planning`
conversation — the active one, else the most recently closed (§ Terms);
pinning is a sort rule in `ConversationTabs`/`ChatsLibrary` (that row first,
then chats by recency — today's order already places it first). **Exactly one
row carries the label "Task Agent"** (A10). Older closed planning lineages
stay in the library where they are today, with the chip "Earlier plan" (copy
under F4) and no pin. **No authorization change** (A9): the conversation
listing is owner-relative (`web-api.md` § Conversations — each caller sees the
conversations they created, plus legacy NULL rows if they own the Task), so a
colleague or admin sees what they see today, under the new labels.
Showing the overlay on the Agent tab is one condition in `AppShell` plus the
layout check that the planning pane and the sidebar do not both render the
planning conversation at once (the sidebar's Task Agent entry focuses the main
pane instead of opening a second copy).

- Invariant I8: for the **owner**, on the Agent tab the chat list is visible
  with exactly one "Task Agent" pinned first (active planning row, else the
  newest closed; a Task with several closed lineages is a test case); no
  user-visible chat is named "Planning"; the word "chat" is unchanged
  everywhere else. For a **non-owner** a test asserts the listed rows equal
  today's (only labels differ).

### V9 — A Task's traces are split across sessions

Owner observation 2026-09-04: in Langfuse the planning chat is one session and
everything after it is separate. Cause: the run start never passes a session
id, and planning and chat turns each pass their own conversation id. The task
row exists before the first planning turn (`POST /api/v1/tasks` at `/new`), so
the task id is available to every trace from the start.

- `routers/planning.py` planning turn, `chat_turns.py` chat turn and
  `routers/runs.py` `run_plan(...)` all pass `session_id=<task id>`. The runner
  needs no change: it already carries `session_id` into steering, watch and the
  continuation state (`continuation_state.py` `cap["session_id"]`).
- The conversation id is kept as trace metadata (`conversation_id`) next to the
  renamed `task_id`, so one chat can still be filtered.
- Product behaviour unchanged; observability only. Not a rename — recorded as
  the slice's one rider, folded in by the owner.
- Invariant I9: with a stub Langfuse client, one task's planning turn, run
  start, steering continuation and chat turn all emit `session_id` equal to the
  task id, and the chat turn's metadata carries its `conversation_id`.

### V10 — Two riders from `deferred.md` (owner, 2026-09-04)

Both are naming or deletion only; neither changes what a user sees or what a
run does.

- **`http_budget` → `call_budget`** (`evidence_base/sourcing/search_loop.py`,
  the per-depth constants dict and its one reader; deferred entry "counts
  logical calls, not HTTP requests — OPEN 2026-08-04"). The entry's own fix:
  "rename the budget to say what it counts". Not stored, not in a prompt; the
  unread `_TransportMixin.http_calls` counter is left as it is.
- **Delete `RunPane.tsx` and `journey/JourneyPane.tsx`** (deferred entry "dead
  code — imported by no route; re-wire or delete"). Nothing imports either
  except their own tests, which go with them. `journey/presentation.ts` and
  its tests **stay** — `runProgress.ts` imports it (A14); the plan's collision
  audit lists any other orphan. Owner chose delete over re-wire, so the
  journey cards are not coming back in this shape. Removes four of V3's copy
  sites before the sweep.
- Invariant I10: `grep -rn http_budget backend` is empty; `RunPane` and
  `JourneyPane` do not exist; `make verify` frontend lane green with no test
  weakened beyond the deleted files' own tests (rubric 5 justification: dead
  code).

### V11 — After a sign-in round trip the app shows the deep link but renders the landing route

Deferred entry "Post-re-auth return-to renders the landing route" (026 live
check, 2026-07-28; owner folded in 2026-09-04). Mechanism, from the code:
`OidcAuthProvider.onSigninCallback` restores the stashed path with
`window.history.replaceState`, which react-router does not observe. `App.tsx`
then swaps from `publicRouter` to `authenticatedRouter` (`key={status}`), but
both routers are module-level singletons created at import time, so the
freshly mounted authenticated router starts from the location its history
captured before the redirect, not from the rewritten URL. A reload recovers.

- **Seam, pinned (A11):** the callback stays the single consumer of the
  stash — it already removes the key and rewrites the address bar with
  `replaceState`, so by the time auth status flips the browser URL *is* the
  stashed path. `App.tsx`, at the moment status becomes `authenticated`,
  calls `authenticatedRouter.navigate(window.location.pathname + search +
  hash, { replace: true })` once. No second reader of the stash, no import
  cycle (`App.tsx` already imports both routers), and the destination is
  same-origin by construction because it comes from `window.location`, not
  from storage. 036's stash-and-splash path (`StashAndSplashRedirect` writes
  the same key) keeps working unchanged: a signed-out visitor hitting a deep
  link, signing in, lands on it.
- Auth-adjacent, so it is reviewed as such: the step-7 security lane reads V11
  explicitly, and the live check includes one real sign-in round trip on
  staging.
- Behaviour change, deliberately: the only one in the slice that a user can
  see. Recorded here so the "no product behaviour change" rule has exactly one
  named exception.
- Invariant I11: a unit test mounts the app with a stashed return path, flips
  auth status to `authenticated`, and asserts the authenticated router's
  location equals the stashed path; the staging live check confirms it from a
  task deep link (`/tasks/{id}/sources`) through Cognito and back.

### V12 — Repo hygiene (owner, 2026-09-04)

The manual (`docs/agentic-ops/references/advanced-agentic-engineering-manual.md`
§ 4.1) says AGENTS.md is a protocol and landmine list, not a diary; and dead
files make the sweep larger than it needs to be. Everything here is mechanical
and verified by the existing gates. Local, ignored leftovers (`demo/`, `dist/`,
the impeccable state directory, the `c4-demo` worktree and `demo-live-run`
branch, the private `docs/verification/`) are removed by the owner outside git
and are not part of the diff.

- **AGENTS.md** rewritten at the design phase (done, `d3d7a47e`): the protocol
  as it was and a landmine list where every line names its source. The
  § Current phase section is gone with its 266-line slice history: the branch
  name and this file's Status line are the pointer, and git and `docs/tasks/`
  hold the history. 51 lines.
- **Stale live e2e** — `frontend/e2e/live-027.spec.ts`, `live-027b.spec.ts`,
  `live-028.spec.ts` and `playwright.live-027.config.ts`,
  `playwright.live-028.config.ts` deleted (1,439 lines; slice-specific live
  checks for merged work, referenced by nothing). `playwright.fe-api-smoke.config.ts`
  stays: `scripts/fe_api_smoke.sh` runs it. Rubric 5 justification: the specs
  test 027/028's build, not the product, and their invariants live in
  `journey.spec.ts`.
- **Unused frontend exports and types** per `pnpm dlx knip@5` on `dev`
  `8626594f`: 23 exports (incl. the dead `useCreateProject` hook and the
  duplicate `App` export), 22 exported types. **The plan enumerates every
  candidate with a disposition** (un-export · delete · keep, with the
  reference search that justifies it — tests, e2e and the dynamic imports in
  `routes.tsx`/`main.tsx` count as consumers), pins the exact knip version
  used (no new dependency: `pnpm dlx` and the version recorded in
  `verification.md`), and re-runs knip, the build and `pnpm e2e` afterwards
  (A13).
- **Dead backend functions** (vulture ≥ 60 %, reference-checked against
  `src` and `tests`): `chat_floor._sentence_around` and
  `steering.resolve_unattended`. Deleted. **`OpenAIRelevanceAnnotatorBackend`
  stays** (A12): it is the deliberate live B2′ implementation of the
  relevance-annotator seam (ADR 0023), unwired but documented, so it is a
  "seam on purpose?" question for the separate hygiene pass, not debris.
  Everything else vulture flagged is either a FastAPI/pydantic false positive
  or production code that only tests call — also the separate pass.
- **`scripts/scratchpad/`** (five tracked files: README, a standalone HTML
  mock, `run_live_deep.py`, two notebooks) deleted — scratch state is ignored,
  not committed (manual § 6.4). Git keeps them.
- **`docs/tasks/029-search-volume-cap/`** and **`030-multi-round-search/`**
  (plan-only leftovers that never went through the cycle and collide by name
  with real slices) deleted; the AGENTS.md paragraph that explained them goes
  with them.
- **`JUMPBOX.md`** moves to `infra/JUMPBOX.md`; its four referrers
  (`infra/DEPLOYMENT.md`, three task docs) are updated.
- **`.gitignore`** gains `.cursor/hooks.json`, `.github/hooks/`, `.impeccable/`
  (a local plugin's runtime state; it must not be committed).
- Invariant I12: AGENTS.md ≤ 60 lines with no phase state; knip reports no unused files, exports or
  types outside `src/api/gen/`; vulture at 80 % reports only the known
  pydantic/`cls` false positives; `git ls-files scripts/scratchpad
  docs/tasks/029-search-volume-cap docs/tasks/030-multi-round-search JUMPBOX.md`
  is empty; `make verify` green.

## Forks — ruled 2026-09-04 (owner, by interview)

| # | Question | Options | **Ruling** and why |
|---|---|---|---|
| **F1** | Rename the DB and code at all, or only the API + screen? | (a) full rename, schema included (this contract) · (b) API + frontend only, `vocabulary.ts` stays the mapping | **(a) full rename, schema included.** "The goal of this task is consistency." |
| **F2** | How far does `orchestrator` → `agent` reach in the backend? | (a) screen + wire only (default) · (b) also modules, classes, log/span names · (c) also env vars + `orchestration_plan` table | **(c), all three layers, prompt text included** — the orchestrator persona *is* the Agent (one preamble serves planning, steering, watch and chat), so one word to one word. Ruling R1: prompt word swaps are like-for-like, no bump, no replay. |
| **F3** | Old URLs: `/projects/:id` now means a Project; a bookmarked Task URL with the same shape lands on "not found". **Since 037, `/projects/{id}/results` is also the public share link people copy and send outside the app.** | (a) no redirect logic; users re-share · (b) legacy redirects: `/projects/:id/(results\|sources/*\|share\|history)` → `/tasks/:id/…` in both routers (these paths have no Project counterpart, so the redirect is unambiguous), and bare `/projects/:id` retries the id as a Task on a Project 404 | **(a) no redirects.** 037's public sharing is on staging only, not production; links are regenerated. |
| **F4** | Copy tables: "Task Agent" as the pinned primary chat and its marker (V8), "Report" for the artefact page (V3), "Message the Task Agent" (V4). | approve the tables · edit words in place | **Approved:** "Report", "Message the Task Agent"; the Task Agent is marked by its short visible label only, no icon. |
| **F5** | Open PRs #62 (Langfuse sessions, 7 src files) and #52 (in-app feedback, 19) will conflict with the sweep. (#61 merged 2026-09-04 and is now inside this branch.) | (a) merge them first, then re-merge `dev` here · (b) land 038 first; they rebase with the sweep script re-run | **(b) 038 lands first.** Both PRs are still being worked on; they rebase with the sweep script. |

## Scope / Out of scope

- **In:** everything in § Surface map; one alembic revision (pure rename + one
  UPDATE); `make openapi-sync`; the sweep script committed under `scripts/`
  (re-runnable, so open branches can rebase); tests renamed in lockstep; e2e
  specs; `frontend/src/mock/*`; ops CLI; Makefile vars; living docs; ADR 0036.
- **Out:** **Links** and **Context** as data-model concepts (the definitions name
  them; nothing implements them — the chat's single `entry_artefact_id` is not a
  set; building either is a feature slice). Any new tab content (Share stays as
  033 left it). New capabilities and the options-scoping spec (PR #63 — it
  already uses "Evidence search"; it inherits the glossary). **Prompt
  behaviour**: prompts change words only (R1); any edit that is not a
  one-to-one word swap is out and needs a versioned prompt slice. `eb_*`
  fingerprint ids. Rewriting `event_log` rows or stored plan payloads. A mode
  enum or a new conversation kind. **The judgment-bearing hygiene items** —
  production code only tests call (`select_document_fetcher`,
  `compile_synthesis_directive`, `validate_themes`, `apply_reselect`, the six
  `*_score_summary` renderers), the `run_harness(provider=…)` seam — go to a
  separate Tier 1 pass after 038 (`/ponytail-audit`), each with its own
  "seam on purpose?" ruling. Historical docs,
  frozen sources, `docs/knowledge/` filenames. The workspace-cluster re-parenting
  (still deferred; unaffected). Metabase saved questions (owner-operated; see
  § Constraints). **Future direction from the definitions § Future direction, recorded as seams in
  `deferred.md` § Vocabulary, not built:** re-running a Task or part of it from
  any chat; active chats reachable app-wide from the round Agent icon; any
  Tasks or Projects as chat context (meta-analysis); "chat more functional" as
  its own task.

## Constraints & approval gates

**Gated changes this contract asks approval for** (Tier 4):

1. **Schema** — one migration: `rename_table` ×5 (`project`→`task`,
   `project_source_snapshot`→`task_source_snapshot`, `portfolio`→`project`,
   `portfolio_membership`→`project_membership`, `orchestration_plan`→`plan`),
   every column, constraint and index rename listed in the checked-in
   [schema-manifest.md](schema-manifest.md) (generated by
   `scripts/schema_manifest.py`; 33 column rows, 51 named constraints and
   indexes on `dev` `8626594f`), one `UPDATE capability_run SET capability='evidence_search'`
   with the CHECK swapped, the union view recreated. No shape change, no row
   lost. **The downgrade reverses every step *and* every stored value the new
   image can write in the window** (A2): `capability` back to
   `evidence_base`; `event_type` `task.*` → `project.*`; payload
   `decided_by`/`authored_by` `agent` → `orchestrator`; steer-point id
   `evidence_search_coverage` → `evidence_base_coverage` in plan payloads and
   pause records. Every value is losslessly reversible, so there is no point
   of no return in the data; the only irreversible artefact is a public link
   copied in the window, which is regenerated (F3).
2. **Public interface** — `/api/v1` paths and schema names change without a
   deprecation window. `web-api.md` § Deprecations records the break by ADR
   0036; the only consumers are this repo's frontend and e2e (deferred.md).
3. **Production config** — two env var names (`POLICY_ATLAS_AGENT_MODEL`,
   `POLICY_ATLAS_AGENT_TRIAGE_MODEL`); the stack sets neither, so this is a
   code-default and docs change plus a PR note for operators. `Makefile`
   variable names for the ops CLI change (`PROJECT`→`TASK`,
   `PORTFOLIO`→`PROJECT`).
5. **Prompt text** — word swaps only, under ruling R1; `prompt_hashes.json`
   values change and the diff is a review artefact.
4. **Deploy posture** — the migration task runs before the new backend image;
   between the two the old image errors on renamed tables. Accepted brief
   outage on staging then production, in that order; no dual-name window.
   Rollback (ADR 0036 § Rollback names the exact commands): quiesce — scale
   the API to zero so no run or turn is in flight; verify with the manifest
   queries; `alembic downgrade -1` (which also reverses the stored values,
   above); deploy the previous image; re-run the verification queries. Any
   public link copied in the window is dead after rollback too and is
   regenerated.

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
- **Prompt guard** — `scripts/prompt_hashes.json` keys are re-pathed (package
  move) **and** values change (R1 word swaps). The build records the prompt
  diff itself, not just the hash file, so the review can confirm words only.
- **Analytics and traces** — the Metabase dashboards on staging Aurora query
  `project` and `portfolio` by name and will break on migration; saved Langfuse
  filters on `orchestrator:*` spans and `project_id` metadata stop matching new
  traces. Owner action after merge; the PR names both.
- **No dependency, CI or infra change.** `infra/DEPLOYMENT.md`'s lock-monitoring
  SQL is updated in words.

## Public / private boundary

Everything in this slice is committable. No evidence text, traces or
credentials move. The frozen definitions doc is public-safe (product vocabulary).

## Model route

No route change. Prompt text changes are **word swaps only** under owner
ruling R1 (2026-09-04): `orchestrator`→`agent`, `project`→`task`,
`evidence_base_coverage`→`evidence_search_coverage`; "evidence base" meaning the
collection stays. No version suffix moves, no replay loop. Anything beyond a
one-to-one swap is a stop condition.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves** — no new column, flag or mode enum.
- **No product behaviour change, one named exception** — every test that
  fails after the sweep fails on a name, or the slice has done more than
  rename. Prompt diffs are words only. V9 changes trace grouping and nothing
  the user sees. V11 is the one user-visible fix, reviewed as auth code.
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md).

## Stop conditions

Halt and escalate when: a rename would need a shape change (a column that
cannot be renamed in place, a value that must be rewritten in `event_log`); a
collision the audit missed surfaces mid-sweep; a prompt edit that is not a
one-to-one word swap; an
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
- **Live check, scoped, in two parts** (staging deploys only on merge, so
  the staging half cannot precede the PR — plan-review P11). *Pre-merge,
  local:* `make dev` + `make fe-api-smoke` against the local API — one Task
  through Agent → Result → Sources → Share → History, its Project, one
  signed-out public Task URL, one sign-in round trip from a deep link (V11).
  *Post-merge, before the production promote, on staging:* one existing Task
  opens on `/tasks/{id}` with report, sources and history intact; its Project
  lists it on `/projects/{id}`; one public Task opens signed-out from a
  freshly copied link (F3: no redirects); one sign-in round trip; the ops CLI
  `rows assign --task` dry-runs; `make fe-api-smoke` against staging.
  Recorded as a dated addendum to `verification.md` in a docs-only commit on
  `dev`. No full live e2e.
- `pip-audit`/deps unchanged: `uv.lock` and `pnpm-lock.yaml` diff empty.

## Verification evidence expected

In [verification.md](verification.md): the `make verify` tail; the V9 stub-tracing
test output; the migration
round-trip output; the prompt text diff (words only) and the re-pinned
`prompt_hashes.json`; the collision
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
readers of stored vocabulary that do not accept the old value; a prompt edit
that changed more than a word; anything that changed behaviour beyond the
enumerated deltas (routes and URLs · labels · trace grouping · sign-in landing).

**Review load (A15).** Twelve items in one Tier 4 slice are reviewable only if
the plan isolates them. The plan must give each of these its own phase and
commit, so a reviewer can read one concern at a time: (a) ADR 0036 + the
schema manifest · (b) the migration + the compatibility readers (A3, A4, A5) ·
(c) the API, generated client and frontend rename · (d) V8 · (e) V9 · (f) V11 ·
(g) V10 · (h) V12. The security lane reads (b)'s tenancy predicates and public
read leg, and (f), as small diffs on their own. The reviewer recommended moving
V12 to its own slice; the owner folded it, so it ships as the last, separable
phase and can be dropped from the PR without touching the rest.

## Adversarial findings (2026-09-04, Codex, contract stage)

All fifteen accepted. A1 schema manifest incomplete (`project_source_snapshot`)
· A2 rollback insufficient · A3 steer-point canonicalisation must sit at plan
deserialisation · A4 `project.shared_publicly`/`unshared` events missing · A5
two `decided_by` projections missing · A6 ADR 0036 must narrowly supersede
`prompting.md` rule 12 and note that no stored value carries the
`orchestrator_v1` family id (checked: `prompt_version` rows are component
prompts only) · A7 contradictory redirect rows + ADR 0035 paths + `web-api.md`
additive-only rule · A8 ADR 0002 vs an owner-edited source — resolved by moving
the living definitions to `docs/specs/vocabulary.md` and freezing the snapshot
(owner option 2) · A9 V8 scoped to owner, no authorization
change · A10 exactly one Task Agent · A11 V11 seam pinned · A12 keep the live
relevance annotator · A13 knip candidates enumerated with dispositions · A14
keep `journey/presentation.ts` · A15 defect count, rubric 3/5/18 wording,
phase isolation. Each is folded where it lands; this list is the index.
