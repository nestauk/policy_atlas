# Rename manifest (task 043, phase one)

Deliverable 2 of the [043 contract](contract.md): the inventory the plan phase
works from for (A) `planning`/`planner` → `task_agent` and (B) the `EB` → `ES`
abbreviation sweep. Read-only research; no source file is changed by this
document. Modelled on 038's `schema-manifest.md` / `scan-backend.md` /
`scan-frontend.md` — same shape (identifier, file, count, new name), scoped to
this task's two renames rather than a full-codebase sweep.

File universe: `git ls-files <path>` (tracked files only). Two tracked
directories that mention "planning" heavily and are **not** in scope because
they are gitignored local artefacts, not repository content, are called out
in § Exclusions: `scripts/recordings/*.json` and `scripts/.rename_038_state.json`.

Commands used are named at each table. Counts are occurrences (`grep -o`),
not lines, unless stated.

---

## A. `planning` / `planner` → `task_agent`

### A.0 Scope and method

`grep -rl` file lists per directory, then a Python scan
(`[Pp][Ll][Aa][Nn][Nn]([Ii][Nn][Gg]|[Ee][Rr])[A-Za-z_]*` over
`git ls-files backend/src backend/tests frontend/src frontend/e2e scripts`)
for the full identifier appendix (§ A.6), plus targeted `grep -n` reads of
`backend/src/policy_atlas/core/schema.py` and the relevant `alembic/versions/`
files for the database group, and `docs/specs/system/web-api.md` /
`infra/DEPLOYMENT.md` / `docs/knowledge/*.md` for the docs group.

Files in scope carrying the token (`grep -rl -iE 'planning|planner'`):

| Directory | Files | Occurrences (`grep -ro -iE 'planning\|planner'`) |
|---|---|---|
| `backend/src` | 27 | 428 |
| `backend/tests` | 29 | 516 |
| `backend/alembic/versions` (report only, never edited) | 5 | 47 |
| `frontend/src` + `frontend/e2e` | 50 | 533 |
| `scripts` (tracked files only) | 4 | 6 |
| `infra/DEPLOYMENT.md` | 1 | 1 |
| `docs/specs/system/web-api.md` | 1 | 26 (line count; `grep -c`) |
| `docs/knowledge/**` (content only) | 13 | 46 |

`scripts` count of 4 files / 6 occurrences excludes the two gitignored
recordings files and `.rename_038_state.json` (§ Exclusions); the remaining
in-scope scripts are `scripts/prompt_hashes.json` (1), `scripts/rename_038.py`
(3, historical — § Exclusions), `scripts/feasibility_checks/options_scoping/draft_profiles.py`
(1, false positive — § Known false positives), `scripts/feasibility_checks/options_scoping/run_fresh_neet_search.py`
(1, genuine).

### A.1 Database

Source: `grep -n` over `backend/src/policy_atlas/core/schema.py` and the
alembic revisions that created each object. Migrations are report-only —
listed so the plan phase knows which revision the 043 migration must
reference, never edited themselves.

| Object | Kind | Name today | Proposed name | Created in revision | Note |
|---|---|---|---|---|---|
| Table | table | `planning_transcript` | `task_agent_transcript` | `e9a7c3d1f6b4` (task 027, as `project_id`-keyed; renamed to `task_id` at 038's `c1a7f4e9b0d2`) | |
| Column | column | `planning_transcript.planner_state` | `task_agent_transcript.task_agent_state` | `e9a7c3d1f6b4` | raw prior-turn dump used as the next planner call's context |
| Column comment | value | `plan.created_by` comment `'user'\|'planner'` | `'user'\|'task_agent'` | `d2f8a4c1e9b7` (plan/`orchestration_plan` table) | column itself (`created_by`) is unchanged; only the literal value renames (§ stored values below) |
| CHECK | constraint | `ck_conversation_kind` on `conversation.kind IN ('planning', 'chat')` | name unchanged; expression becomes `kind IN ('task_agent', 'chat')` | `d8e4a1c7f2b9` (task 029, conversation model) | constraint **name** has no token — kept; only the **stored value** `'planning'` inside it renames |
| CHECK | constraint | `ck_conversation_planning_never_archived` | `ck_conversation_task_agent_never_archived` | `d8e4a1c7f2b9` | |
| UNIQUE (partial) | constraint | `uq_conversation_one_active_planning` (`postgresql_where="kind = 'planning' AND status = 'active'"`) | `uq_conversation_one_active_task_agent` (`kind = 'task_agent' AND status = 'active'`) | `d8e4a1c7f2b9` | partial-index predicate carries the stored value too |
| FK | constraint | `fk_planning_transcript_conversation` | `fk_task_agent_transcript_conversation` | `d8e4a1c7f2b9` | |
| FK (auto-named) | constraint | `planning_transcript_task_id_fkey` (originally `..._project_id_fkey`, renamed at 038) | `task_agent_transcript_task_id_fkey` | `e9a7c3d1f6b4`, renamed `c1a7f4e9b0d2` | Postgres auto-name follows the table rename |
| UNIQUE | constraint | `uq_ptr_task_client_turn` (originally `uq_ptr_project_client_turn`) | `uq_tat_task_client_turn` *(proposed abbreviation — see note)* | created `e9a7c3d1f6b4`, renamed 038 `c1a7f4e9b0d2` | |
| UNIQUE | constraint | `uq_ptr_task_turn_index` (originally `uq_ptr_project_turn_index`) | `uq_tat_task_turn_index` *(proposed)* | `e9a7c3d1f6b4`, renamed 038 | |
| CHECK | constraint | `ck_ptr_status` | `ck_tat_status` *(proposed)* | `e9a7c3d1f6b4` | |
| CHECK | constraint | `ck_ptr_suggestions_array` | `ck_tat_suggestions_array` *(proposed)* | `e9a7c3d1f6b4` | |
| Stored value | value | `conversation.kind = 'planning'` | `'task_agent'` | written from `d8e4a1c7f2b9` on | rewritten on upgrade, reversed on downgrade — same treatment as 038's `capability_run.capability` rewrite |
| Stored value | value | `plan.created_by = 'planner'` | `'task_agent'` | schema comment since `d2f8a4c1e9b7`; the only production write site found (`runtime/agent.py:906`, `runtime/steering.py:1681`) currently writes `'user'` only — the `'planner'` value is exercised by 8 test files (`test_screen_step_rename_migration.py`, `test_migration_038.py` ×2, `test_migrations_029.py`, `test_steering.py`, `test_task_plan_schema.py` ×2, `test_router_compile.py` ×5, `test_route_grades.py`) but its production writer was not located in this scan — **flag for the plan/build phase** to confirm the write path before assuming the migration's rewrite set is complete |
| Wire role literal | value | `"planner"` role label in transcript rehydration dicts | `"task_agent"` | n/a (application-level, not stored) | 4 sites: `backend/src/policy_atlas/runtime/agent.py:997` (`{"role": "planner", ...}`), `backend/src/policy_atlas/api/routers/planning.py:256` (same), `backend/src/policy_atlas/runtime/planner.py:173` (`label="planner"`), `backend/src/policy_atlas/runtime/planner_prompt.py:747` (`if turn["role"] == "planner":`) — plus docstring mentions of the `"user"\|"planner"` role union at `planner.py:64,191` and `planner_prompt.py:709,711,717,725` |

Abbreviation note: 038's precedent coined `ptr` for `planning_transcript`
(not a literal first-letter acronym). This manifest proposes `tat` for
`task_agent_transcript` by the same non-literal convention; it is not fixed
by the contract text and should be confirmed (or replaced) at plan time.

### A.2 API

Source: `grep -n` over `backend/src/policy_atlas/api/{app.py,deps.py,routers/planning.py,routers/_access.py,routers/conversations.py,contract/planning.py,contract/__init__.py}` plus `frontend/openapi.json` for operation ids.

| Identifier | Kind | File | Count | New name | Note |
|---|---|---|---|---|---|
| `POST /api/v1/tasks/{id}/planning-turns` | route | `api/routers/planning.py:390` | 1 | `POST /api/v1/tasks/{id}/task-agent-turns` | no redirect from the old path (038 rule, contract deliverable 2) |
| `GET /api/v1/tasks/{id}/planning-turns` | route | `api/routers/planning.py:541` | 1 | `GET /api/v1/tasks/{id}/task-agent-turns` | |
| `planning_router` | symbol | `api/app.py:210,227` | 2 | `task_agent_router` | import alias and router variable, both sites |
| `create_planning_turn` | function | `api/routers/planning.py:391` | 1 | `create_task_agent_turn` | route handler |
| `list_planning_turns` (+ internal helper split as `list_planning_turns`) | function | `api/routers/planning.py` | 3 | `list_task_agent_turns` | |
| `PlanningTurnCreate` | contract model | `api/contract/planning.py`, `api/contract/__init__.py`, `api/routers/planning.py`, `frontend/src/api/gen/types.ts` | 9 | `TaskAgentTurnCreate` | request body |
| `PlanningTurnOut` | contract model | same files | 17 | `TaskAgentTurnOut` | response body |
| `PlanningTranscriptTurnOut` | contract model | same files + `frontend/src/{mock/api.ts,mock/fixtures.ts,store/thread.ts,store/transcript.ts,views/workspace/PartCard.tsx}` | 19 | `TaskAgentTranscriptTurnOut` | transcript row read model |
| `Page_PlanningTranscriptTurnOut_` | generated type | `frontend/src/api/gen/types.ts` | 2 | `Page_TaskAgentTranscriptTurnOut_` | regenerated by `make openapi-sync`, never hand-edited (§ Exclusions) |
| `PLANNING_MESSAGE_MAX` | constant | `api/contract/planning.py` | 2 | `TASK_AGENT_MESSAGE_MAX` | |
| `planning_turn_in_progress` | error code | `api/app.py:36`, `api/routers/planning.py:2` (raise sites), `frontend/src/lib/errors.ts` | 6 | `task_agent_turn_in_progress` | 409 code; web-api.md's error table (line 115) lists it alongside `chat_turn_in_progress` and `stale_turn` — those two keep their names |
| `list_planning_turns_api_v1_tasks__task_id__planning_turns_get` | OpenAPI operationId | `frontend/openapi.json:8284`, mirrored in `frontend/src/api/gen/types.ts` | 1 (+1 generated) | `list_task_agent_turns_api_v1_tasks__task_id__task_agent_turns_get` | auto-generated by FastAPI from the route path + function name; regenerates once both rename (§ Exclusions on `openapi.json`/`gen/types.ts`) |
| `create_planning_turn_api_v1_tasks__task_id__planning_turns_post` | OpenAPI operationId | `frontend/openapi.json:8354` | 1 (+1 generated) | `create_task_agent_turn_api_v1_tasks__task_id__task_agent_turns_post` | same |
| `ensure_active_planning_conversation` | function | `api/routers/_access.py`, `api/routers/planning.py`, `runtime/conversation_lifecycle.py`, tests | 12 | `ensure_active_task_agent_conversation` | conversation-kind lifecycle helper |
| `close_planning_conversation` | function | `runtime/conversation_lifecycle.py`, `runtime/runner.py`, tests | 8 | `close_task_agent_conversation` | |
| `get_planner_backend` | function | `api/deps.py`, `api/routers/planning.py`, tests | 24 | `get_task_agent_backend` | FastAPI dependency |
| `planner` (dependency param name) | symbol | `api/routers/planning.py:392` (`planner: Annotated[PlannerBackend, Depends(get_planner_backend)]`) | 1 of the 16 `planner` occurrences in that file | `task_agent` | |

Contract models in `api/contract/planning.py` that **do not** carry the token
(kept, listed here so the sweep does not touch them): `CountryGroupDraft`,
`ScopeConstraintsDraft`, `PlanStep`, `PlanDraft`, `PartOptionOut`,
`PartChipOut`, `PartProposalOut`, `PlanOut`, `PlanPatchIn` — see § Not part of
the rename.

### A.3 Runtime

Source: `grep -n` over `backend/src/policy_atlas/runtime/{planner.py,planner_prompt.py,agent.py,agent_backend.py,agent_prompt.py,deps.py}` and `scripts/prompt_hashes.json`.

| Identifier | Kind | File | Count | New name | Note |
|---|---|---|---|---|---|
| `runtime/planner.py` | module (file) | — | — | `runtime/task_agent.py` | named explicitly in contract deliverable 2 |
| `runtime/planner_prompt.py` | module (file) | — | — | `runtime/task_agent_prompt.py` | named explicitly |
| `api/routers/planning.py` | module (file) | — | — | `api/routers/task_agent.py` *(proposed — not explicitly named in the contract; follows the same convention)* | flag for plan-phase confirmation |
| `api/contract/planning.py` | module (file) | — | — | `api/contract/task_agent.py` *(proposed)* | same flag |
| `PlannerBackend` | class | `runtime/planner.py`, `api/deps.py`, `api/routers/planning.py`, `runtime/agent.py`, tests | 12 | `TaskAgentBackend` | protocol/base class |
| `OpenAIPlannerBackend` | class | `runtime/planner.py`, `runtime/agent.py`, tests | 13 | `OpenAITaskAgentBackend` | |
| `StubPlannerBackend` | class | `runtime/planner.py`, `api/deps.py`, `runtime/agent.py`, tests | 29 | `StubTaskAgentBackend` | |
| `PlannerTurnWire` | class | `runtime/planner.py`, `runtime/planner_prompt.py`, tests | 48 | `TaskAgentTurnWire` | wire schema for a turn |
| `PlannerTurn` | class | `runtime/planner.py` | 1 | `TaskAgentTurn` | distinct from `PlanningTurn` (frontend, § A.4) and `PlannerTurnWire` above — three different symbols, all rename |
| `PLANNER_MODEL` | constant | `runtime/agent_backend.py`, `runtime/planner.py` | 4 | `TASK_AGENT_MODEL` | |
| `PLANNER_PROMPT_VERSION` | constant | `runtime/planner.py`, `runtime/planner_prompt.py`, tests | 5 | `TASK_AGENT_PROMPT_VERSION` | the version **string value** it holds, `planner_v11`, is **kept** (§ Exclusions) |
| `PLANNER_SYSTEM_PROMPT` | constant | `runtime/planner_prompt.py`, tests | 30 | `TASK_AGENT_SYSTEM_PROMPT` | |
| `PLANNER_TURN_MAX` / `PLANNER_INTENT_MAX` / `PLANNER_HISTORY_TURNS_MAX` / `PLANNER_MAX_OUTPUT_TOKENS` / `PLANNER_LATEST_TURN_TEMPLATE` / `PLANNER_DRAFT_ONLY_TEMPLATE` / `MAX_PLANNER_TURNS` | constants | `runtime/planner_prompt.py`, `runtime/agent.py`, tests | 6+4+9+3+2+2+3 = 29 | `TASK_AGENT_TURN_MAX` etc. | |
| `POLICY_ATLAS_PLANNER_MODEL` | env var | `runtime/planner.py:1`, `infra/DEPLOYMENT.md:421` | 2 | `POLICY_ATLAS_TASK_AGENT_MODEL` | deployment config change — contract approves the staging value change with this contract |
| `build_planner_messages` | function | `runtime/planner.py`, `runtime/planner_prompt.py`, tests | 14 | `build_task_agent_messages` | |
| `get_planner_backend` / `live_planner_and_backends` / `default_planner` | functions | `runtime/agent.py`, `api/deps.py` | 24 + 7 + 3 | `get_task_agent_backend` / `live_task_agent_and_backends` / `default_task_agent` | |
| `PLANNING` constant | constant | `runtime/agent_prompt.py:1` (module docstring: "the PLANNING moment lives in ``planner_prompt.py``") | 1 | `TASK_AGENT` | this is prose in a docstring naming the moment, not a code constant — reword rather than mechanically substitute |
| `planner_v11` prompt-hash entry | data | `scripts/prompt_hashes.json` (key `backend/src/policy_atlas/runtime/planner_prompt.py`) | 1 | key path becomes `backend/src/policy_atlas/runtime/task_agent_prompt.py`; **value (the hash) is re-pinned as a words-only diff**, not carried over blind | the pinned **version string** `planner_v11` itself is unchanged (§ Exclusions) — only the file path key moves |

### A.4 Frontend

Source: `grep -rl -iE 'planning|planner' frontend/src frontend/e2e` (50 files), then per-file `grep -o -iE 'planning|planner' <file> | wc -l`.

| File | Count | Renamed to | Note |
|---|---|---|---|
| `frontend/src/views/workspace/PlanningPane.tsx` | 51 | `TaskAgentPane.tsx` | primary chat surface |
| `frontend/src/views/workspace/PlanningPane.test.tsx` | 36 | `TaskAgentPane.test.tsx` | |
| `frontend/src/api/gen/types.ts` | 59 | unchanged path; regenerated (§ Exclusions) | |
| `frontend/src/mock/api.ts` | 28 | — | mock API surface |
| `frontend/src/views/workspace/chat/conversationState.test.ts` | 25 | — | |
| `frontend/src/store/thread.ts` | 23 | — | |
| `frontend/src/store/transcript.ts` | 21 | — | |
| `frontend/src/views/workspace/chat/conversationState.ts` | 19 | — | |
| `frontend/src/views/workspace/chat/ConversationList.tsx` | 19 | — | |
| `frontend/src/views/workspace/chat/ConversationList.test.tsx` | 20 | — | |
| `frontend/src/views/WorkspaceView.test.tsx` | 20 | — | |
| `frontend/src/views/workspace/chat/ChatSidePanel.tsx` | 16 | — | |
| `frontend/src/views/workspace/chat/ChatSidePanel.test.tsx` | 14 | — | |
| `frontend/src/store/thread.test.ts` | 13 | — | |
| `frontend/src/mock/fixtures.ts` | 12 | — | |
| `frontend/e2e/journey.spec.ts` | 11 | — | |
| `frontend/src/views/WorkspaceView.tsx` | 9 | — | |
| `frontend/src/views/workspace/chat/ChatMessages.tsx` | 9 | — | |
| `frontend/src/views/workspace/PartCard.tsx` | 8 | — | |
| `frontend/src/store/transcript.test.ts` | 8 | — | |
| `frontend/src/views/workspace/chat/ChatMessages.test.tsx` | 8 | — | |
| (remaining 31 files, 1–7 occurrences each) | 132 (sum) | — | see § A.6 raw appendix for the full per-identifier breakdown |

Total frontend occurrences: 533 across 50 files (25 implementation + 25 test,
matching the contract's "about 25 files" when counting implementation files
only).

Key symbols (all in the files above): `PlanningPane`, `usePlanningTurns`,
`usePlanningTurn`, `usePlanningTranscript`, `PlanningTurn`,
`PlanningTranscriptTurn`, `PlanningThreadTurn`, `PlanningThreadDecision`,
`PlanningThreadRun`, `PlanningThreadItem`, `OptimisticPlanningTurn`,
`composePlanningThread`, `isPlanningConversation`, `isPlanning`,
`onOpenPlanning`, `openPlanning`, `planningOpen`, `MOCK_PLANNING_CONVERSATION_ID`,
`MOCK_PLANNING_TURN_IDS`, `seedPlanningTurns`, `PLANNING_TAB_ID`,
`planningComposerPlaceholder`, `plannerText`, `PlannerBubble`,
`Replanning`/`replanning`. New names follow the `planning→taskAgent`/
`Planning→TaskAgent`/`planner→taskAgent`/`Planner→TaskAgent` substitution
(§ A.6), except the irregular cases flagged there (`Replanning`,
`planningComposerPlaceholder`-style camelCase joins, `planningOpen`,
`plannerText`, `planningTurn`/`planningTurns`) which need a human casing pass,
not a mechanical one.

Mock/store/API-client files specifically named in the contract:
`frontend/src/mock/api.ts` (28), `frontend/src/mock/api.test.ts` (7),
`frontend/src/mock/fixtures.ts` (12), `frontend/src/store/transcript.ts` (21),
`frontend/src/store/transcript.test.ts` (8), `frontend/src/store/thread.ts`
(23) — `thread.ts`/`thread.test.ts` are in scope too even though not named in
the contract text, because they hold `PlanningThread*` types.

### A.5 Docs

| File | Count | Method | Note |
|---|---|---|---|
| `infra/DEPLOYMENT.md` | 1 (line 421) | `grep -n -iE 'planning\|planner' infra/DEPLOYMENT.md` | the `POLICY_ATLAS_PLANNER_MODEL` env-var row |
| `docs/specs/system/web-api.md` | 26 lines (`grep -c -i -E 'planning\|planner'`) | — | § Planning turns (lines 271–332) and the `## Conversations` section's references to the `planning` conversation kind (lines 336–391); the error-envelope table (line 115) |
| `docs/knowledge/plan-lineage-by-fencing-not-custody.md` | 8 | `grep -c -i -E 'planning\|planner' <file>` | content only — filename is a concept id, never renamed |
| `docs/knowledge/scope-constraint-fields-projection-surfaces.md` | 8 | same | |
| `docs/knowledge/prompt-honesty-rules-route-around-new-capability.md` | 5 | same | |
| `docs/knowledge/log.md` | 4 | same | |
| `docs/knowledge/overton-filter-values-display-names.md` | 4 | same | |
| `docs/knowledge/structured-output-prompts-pin-key-vocabulary.md` | 4 | same | |
| `docs/knowledge/index.md` | 3 | same | |
| `docs/knowledge/two-phase-retry-terminal-status.md` | 3 | same | |
| `docs/knowledge/live-check-drive-runbook.md` | 2 | same | |
| `docs/knowledge/silent-sdk-guards-and-stub-shaped-tests.md` | 2 | same | |
| `docs/knowledge/jointly-compiled-fields-patch-together.md` | 1 | same | |
| `docs/knowledge/model-output-nul-scrub.md` | 1 | same | |
| `docs/knowledge/orchestrate-stub-smoke.md` | 1 | same | |

No `.claude/skills/**` file names the `/planning-turns` route or `PlanningPane`
(`grep -rniIl -E 'planning-turns|planning_transcript|planner|PlanningPane' .claude/skills` → no matches).

### A.6 Raw identifier appendix (auto-generated draft)

Full output of the token scan (126 distinct identifiers matching
`[Pp][Ll][Aa][Nn][Nn]([Ii][Nn][Gg]|[Ee][Rr])[A-Za-z_]*` across
`backend/src`, `backend/tests`, `frontend/src`, `frontend/e2e`, `scripts`),
with a mechanical `planning→task_agent`/`Planning→TaskAgent`/
`PLANNING→TASK_AGENT`/`planner→task_agent`/`Planner→TaskAgent`/
`PLANNER→TASK_AGENT` substitution applied to produce the "new name" column.
**This is a draft, not a ruling**: rows flagged ⚠ below need a manual casing
or semantic fix before use; everything else is a direct substitution
consistent with the per-kind tables above.

| Identifier | Proposed target | Count | Files (first 3, +more) |
|---|---|---|---|
| `planning` | `task_agent` | 404 | `api/app.py`:2, `api/contract/__init__.py`:1, `api/contract/chat.py`:3 (+77 more) |
| `planner` | `task_agent` | 193 | `api/contract/planning.py`:9, `api/deps.py`:5, `api/routers/planning.py`:16 (+37 more) |
| `planning_transcript` | `task_agent_transcript` | 121 | `api/routers/conversations.py`:6, `api/routers/planning.py`:56, `api/routers/runs.py`:4 (+8 more) |
| `PlannerTurnWire` | `TaskAgentTurnWire` | 48 | `runtime/planner.py`:15, `runtime/planner_prompt.py`:1, `test_planning_router.py`:5 (+4 more) |
| `Planning` | `TaskAgent` | 39 | `api/contract/planning.py`:3, `api/routers/_access.py`:1, `runtime/agent.py`:1 (+19 more) |
| `PLANNER_SYSTEM_PROMPT` | `TASK_AGENT_SYSTEM_PROMPT` | 30 | `runtime/planner_prompt.py`:2, `test_planner.py`:25, `test_planner_prompt.py`:3 |
| `StubPlannerBackend` | `StubTaskAgentBackend` | 29 | `api/deps.py`:2, `runtime/agent.py`:2, `runtime/planner.py`:1 (+3 more) |
| `PlanningPane` | `TaskAgentPane` | 27 | `lib/vocabulary.ts`:1, `views/AppShell.test.tsx`:1, `views/AppShell.tsx`:1 (+8 more) |
| `get_planner_backend` | `get_task_agent_backend` | 24 | `api/deps.py`:2, `api/routers/planning.py`:2, `test_planning_router.py`:20 |
| `onOpenPlanning` | `onOpenTaskAgent` | 22 | `views/WorkspaceView.tsx`:1, `chat/ChatMessages.test.tsx`:4, `chat/ChatMessages.tsx`:7 (+3 more) |
| `PlanningTranscriptTurnOut` | `TaskAgentTranscriptTurnOut` | 19 | `api/contract/__init__.py`:2, `api/contract/planning.py`:1, `api/routers/planning.py`:5 (+6 more) |
| `planner_state` | `task_agent_state` | 19 | `api/routers/planning.py`:6, `core/schema.py`:2, `test_conversations_router.py`:1 (+5 more) |
| `PlanningTurnOut` | `TaskAgentTurnOut` | 17 | `api/contract/__init__.py`:2, `api/contract/planning.py`:1, `api/routers/planning.py`:11 (+1 more) |
| `planner_prompt` | `task_agent_prompt` | 16 | `api/routers/planning.py`:1, `runtime/agent.py`:1, `runtime/agent_prompt.py`:1 (+11 more) |
| `PlanningThreadDecision` | `TaskAgentThreadDecision` | 15 | `store/index.ts`:1, `store/thread.test.ts`:2, `store/thread.ts`:4 (+2 more) |
| `build_planner_messages` | `build_task_agent_messages` | 14 | `runtime/planner.py`:2, `runtime/planner_prompt.py`:1, `test_planner_prompt.py`:11 |
| `_seed_planning_turn` | `_seed_task_agent_turn` | 14 | `test_migrations_029.py`:14 |
| `Planner` | `TaskAgent` | 13 | `api/contract/planning.py`:2, `runtime/agent.py`:3, `runtime/planner.py`:1 (+4 more) |
| `OpenAIPlannerBackend` | `OpenAITaskAgentBackend` | 13 | `runtime/agent.py`:2, `runtime/planner.py`:2, `test_trace_sessions_038.py`:3 (+1 more) |
| `PlanningThreadTurn` | `TaskAgentThreadTurn` | 13 | `store/index.ts`:1, `store/thread.test.ts`:2, `store/thread.ts`:3 (+2 more) |
| ⚠ `planningComposerPlaceholder` | `taskAgentComposerPlaceholder` (not `task_agentComposerPlaceholder`) | 13 | `PlanningPane.test.tsx`:11, `PlanningPane.tsx`:2 |
| `PLANNING_TAB_ID` | `TASK_AGENT_TAB_ID` | 13 | `chat/ConversationList.test.tsx`:3, `chat/ConversationList.tsx`:3, `chat/conversationState.test.ts`:3 (+1 more) |
| `PlannerBackend` | `TaskAgentBackend` | 12 | `api/deps.py`:2, `api/routers/planning.py`:2, `runtime/agent.py`:4 (+2 more) |
| `ensure_active_planning_conversation` | `ensure_active_task_agent_conversation` | 12 | `api/routers/_access.py`:1, `api/routers/planning.py`:3, `runtime/conversation_lifecycle.py`:1 (+2 more) |
| `usePlanningTurns` | `useTaskAgentTurns` | 12 | `api/README.md`:1, `api/queries.ts`:1, `store/transcript.ts`:2 (+3 more) |
| `planning_id` | `task_agent_id` | 11 | `test_conversations_router.py`:9, `test_migrations_029.py`:2 |
| `CountingPlanner` | `CountingTaskAgent` | 11 | `test_planning_router.py`:11 |
| `PlanningThreadRun` | `TaskAgentThreadRun` | 11 | `store/index.ts`:1, `store/thread.test.ts`:2, `store/thread.ts`:3 (+2 more) |
| `isPlanningConversation` | `isTaskAgentConversation` | 11 | `views/WorkspaceView.tsx`:2, `chat/ChatSidePanel.tsx`:2, `chat/conversationState.test.ts`:6 (+1 more) |
| `OptimisticPlanningTurn` | `OptimisticTaskAgentTurn` | 10 | `store/index.ts`:1, `store/transcript.test.ts`:2, `store/transcript.ts`:5 (+1 more) |
| `PlanningTurnCreate` | `TaskAgentTurnCreate` | 9 | `api/contract/__init__.py`:2, `api/contract/planning.py`:1, `api/routers/planning.py`:3 (+1 more) |
| `PLANNER_HISTORY_TURNS_MAX` | `TASK_AGENT_HISTORY_TURNS_MAX` | 9 | `runtime/agent.py`:2, `runtime/planner_prompt.py`:3, `test_planner_prompt.py`:4 |
| `planner_v` (fragment of `planner_v11`) | n/a — **excluded**, see § Exclusions | 9 | `runtime/agent_prompt.py`:1, `runtime/planner.py`:1, `runtime/planner_prompt.py`:4 (+2 more) |
| `planning_part_dropped` | `task_agent_part_dropped` | 8 | `api/routers/planning.py`:7, `test_planning_router.py`:1 |
| `close_planning_conversation` | `close_task_agent_conversation` | 8 | `runtime/conversation_lifecycle.py`:1, `runtime/runner.py`:2, `test_planning_router.py`:2 (+1 more) |
| ⚠ `planningTurns` | `taskAgentTurns` | 8 | `api/queries.ts`:2, `mock/api.ts`:6 |
| `composePlanningThread` | `composeTaskAgentThread` | 8 | `store/index.ts`:1, `store/thread.test.ts`:4, `store/thread.ts`:1 (+1 more) |
| `live_planner_and_backends` | `live_task_agent_and_backends` | 7 | `api/deps.py`:3, `runtime/agent.py`:2, `test_rename_038.py`:2 |
| ⚠ `planning_turn` (local var, distinct from the table/route names above) | `task_agent_turn` | 7 | `store/thread.test.ts`:2, `store/thread.ts`:3, `PlanningPane.tsx`:2 |
| `planning_turn_in_progress` | `task_agent_turn_in_progress` | 6 | `api/app.py`:1, `api/routers/planning.py`:2, `test_planning_router.py`:1 (+1 more) |
| `PLANNER_TURN_MAX` | `TASK_AGENT_TURN_MAX` | 6 | `runtime/planner_prompt.py`:2, `test_planner_prompt.py`:4 |
| `usePlanningTurn` | `useTaskAgentTurn` | 6 | `api/mutations.ts`:1, `store/transcript.ts`:2, `PlanningPane.test.tsx`:3 |
| `MOCK_PLANNING_CONVERSATION_ID` | `MOCK_TASK_AGENT_CONVERSATION_ID` | 6 | `mock/api.test.ts`:3, `mock/api.ts`:2, `mock/fixtures.ts`:1 |
| ⚠ `latestPlanning` | `latestTaskAgent` | 6 | `mock/api.ts`:6 |
| `PlanningThreadItem` | `TaskAgentThreadItem` | 6 | `store/index.ts`:1, `store/thread.ts`:3, `PlanningPane.tsx`:2 |
| `PlanningTurn` | `TaskAgentTurn` | 6 | `PartCard.test.tsx`:4, `PartCard.tsx`:2 |
| ⚠ `planningOpen` | `taskAgentOpen` | 6 | `chat/ChatSidePanel.tsx`:6 |
| `planning_conversation` | `task_agent_conversation` | 5 | `runtime/conversation_lifecycle.py`:2, `test_planning_router.py`:3 |
| `PLANNER_PROMPT_VERSION` | `TASK_AGENT_PROMPT_VERSION` | 5 | `runtime/planner.py`:2, `runtime/planner_prompt.py`:1, `test_planner.py`:2 |
| `seedPlanningTurns` | `seedTaskAgentTurns` | 5 | `mock/api.ts`:3, `mock/fixtures.ts`:2 |
| `PlanningTranscriptTurn` | `TaskAgentTranscriptTurn` | 5 | `store/transcript.test.ts`:2, `store/transcript.ts`:3 |
| ⚠ `Replanning` (UI microcopy symbol) | needs a real name, not `Retask_agent` — e.g. `RevisingPlan` or similar, owner/plan-phase call | 5 | `PlanningPane.test.tsx`:4, `PlanningPane.tsx`:1 |
| ⚠ `replanning` | same as above, lower-case | 4 | `api/routers/planning.py`:1, `test_planning_router.py`:1, `test_conversation_lifecycle.py`:1 (+1 more) |
| `PLANNER_MODEL` | `TASK_AGENT_MODEL` | 4 | `runtime/agent_backend.py`:1, `runtime/planner.py`:3 |
| `PLANNER_INTENT_MAX` | `TASK_AGENT_INTENT_MAX` | 4 | `runtime/planner_prompt.py`:2, `test_planner_prompt.py`:2 |
| `PartPlanner` | `PartTaskAgent` | 4 | `test_planning_router.py`:4 |
| `MOCK_PLANNING_TURN_IDS` | `MOCK_TASK_AGENT_TURN_IDS` | 4 | `mock/fixtures.ts`:4 |
| `usePlanningTranscript` | `useTaskAgentTranscript` | 4 | `store/index.ts`:1, `store/transcript.ts`:1, `PlanningPane.tsx`:2 |
| ⚠ `planningTurn` | `taskAgentTurn` | 4 | `store/transcript.ts`:4 |
| `isPlanning` | `isTaskAgent` | 4 | `chat/ConversationList.tsx`:4 |
| `list_planning_turns` | `list_task_agent_turns` | 3 | `api/routers/planning.py`:2, `api/gen/types.ts`:1 |
| `MAX_PLANNER_TURNS` | `MAX_TASK_AGENT_TURNS` | 3 | `runtime/agent.py`:3 |
| `default_planner` | `default_task_agent` | 3 | `runtime/agent.py`:3 |
| `PLANNER_MAX_OUTPUT_TOKENS` | `TASK_AGENT_MAX_OUTPUT_TOKENS` | 3 | `runtime/planner.py`:2, `runtime/planner_prompt.py`:1 |
| `_ModerateStubPlanner` | `_ModerateStubTaskAgent` | 3 | `test_agent.py`:3 |
| ⚠ `plannerText` | `taskAgentText` | 3 | `PlanningPane.tsx`:3 |
| ⚠ `openPlanning` | `openTaskAgent` | 3 | `chat/ChatMessages.test.tsx`:3 |
| `planning_router` | `task_agent_router` | 2 | `api/app.py`:2 |
| `PLANNING_MESSAGE_MAX` | `TASK_AGENT_MESSAGE_MAX` | 2 | `api/contract/planning.py`:2 |
| `_planner_inputs` | `_task_agent_inputs` | 2 | `api/routers/planning.py`:2 |
| `PLANNER_LATEST_TURN_TEMPLATE` | `TASK_AGENT_LATEST_TURN_TEMPLATE` | 2 | `runtime/planner_prompt.py`:2 |
| `PLANNER_DRAFT_ONLY_TEMPLATE` | `TASK_AGENT_DRAFT_ONLY_TEMPLATE` | 2 | `runtime/planner_prompt.py`:2 |
| `_planning_turn` | `_task_agent_turn` | 2 | `test_conversations_router.py`:2 |
| `FailOncePlanner` | `FailOnceTaskAgent` | 2 | `test_planning_router.py`:2 |
| `RunStartsMidPlanner` | `RunStartsMidTaskAgent` | 2 | `test_planning_router.py`:2 |
| `planning_turns` | `task_agent_turns` | 2 | `test_route_grades.py`:2 |
| `_UnattendedPlanner` / `_DefaultsPlanner` / `_ScopedPlanner` / `_StandingInstructionsPlanner` | `_UnattendedTaskAgent` / `_DefaultsTaskAgent` / `_ScopedTaskAgent` / `_StandingInstructionsTaskAgent` | 2 each | `test_agent.py` | stub subclasses |
| `list_planning_turns_api_v` / `_tasks__task_id__planning_turns_get` / `create_planning_turn_api_v` / `_tasks__task_id__planning_turns_post` / `Page_PlanningTranscriptTurnOut_` | generated TS identifiers (fragments of the full generated names — see § A.2) | 2 each | `api/gen/types.ts` | regenerated, never hand-edited |
| ⚠ `PlannerBubble` | `TaskAgentBubble` | 2 | `PlanningPane.tsx`:2 |
| Remaining 33 identifiers (count 1 each) | mechanical substitution, mostly `test_*` function names | 33 | see backend `test_planning_router.py`, `test_route_grades.py`, `test_trace_sessions_038.py`, `test_planning_transcript_migration.py`, `test_agent.py`, `test_planner.py`, `test_planner_prompt.py`, plus `core/schema.py`'s two constraint names and `runtime/planner.py`'s `POLICY_ATLAS_PLANNER_MODEL`/`PlannerTurn` (all covered individually in §§ A.1–A.3) | |

### Exclusions (kept) — group A

| Item | Where | Why kept |
|---|---|---|
| `planner_v11` | `runtime/planner_prompt.py` → `runtime/task_agent_prompt.py`, `scripts/prompt_hashes.json` value | stored provenance value (038 rule R1); only the file-path **key** moves, the version string is unchanged |
| `eb_iof_base_v1`, `eb_icf_base_v1` | fingerprints | stored fingerprints, read-side compatibility |
| `evidence_base_coverage` | legacy steer-point id | superseded name kept for back-compat |
| `docs/adr/**` | all files | never edited |
| Merged task docs under `docs/tasks/` other than 043 | e.g. `docs/tasks/038-vocabulary-alignment/**`, `docs/tasks/027-frontend-port/**` | historical record |
| `docs/specs/sources/**` | frozen | never edited |
| `docs/specs/log.md` | past entries | history |
| `frontend/openapi.json`, `frontend/src/api/gen/types.ts` | generated | regenerated by `make openapi-sync` once the backend route/model renames land; never hand-edited |
| `infra/cdk.out` | generated | not touched |
| `scripts/rename_038.py` (3 occurrences: `test_planning_transcript_migration.py` filename ref, `planner_prompt.py` path ref, a comment) | historical 038 rename tooling | frozen artefact of a closed, merged task; not re-run or edited for 043 |
| `scripts/recordings/overton_raw.json`, `scripts/recordings/openalex_raw.json`, `scripts/.rename_038_state.json` | gitignored, not tracked (`git check-ignore -v` confirms) | not repository content at all — out of scope by definition, not by exemption |

### Known false positives (ordinary-English "planning", not the rename target)

Found while scanning; excluded from the identifier tables above because they
are document content or domain prose, not code:

| File | Line(s) | Text |
|---|---|---|
| `backend/tests/data/provider_records/overton_documents.json` | 1847, 1854 | `"Environmental planning"`, `"Strategic planning"` — sanitized document subject tags |
| `backend/tests/evidence_search/group/test_group_clustering.py` | 40–42 | `"Planning delays slowed the heat-pump rollout."` — fixture finding text (policy-domain content) |
| `backend/tests/evidence_search/synthesis/test_synthesise.py` | 587–588, 719, 1086 | `"Planning delays"` / `"Planning delays slow delivery."` fixture text (587–588, 719); **but** line 1085's `kind="planning"` in the same file **is genuine** (a real conversation-kind literal) — file needs a line-level pass, not a blanket skip |
| `scripts/feasibility_checks/options_scoping/draft_profiles.py` | 28 | `"set or change rules, standards, bans, licensing or planning requirements"` — a verb-family description of regulatory planning, not the code concept |

`scripts/feasibility_checks/options_scoping/run_fresh_neet_search.py:38`
(`"Answers the planning conversation deterministically..."`) is the one
occurrence in that directory that **is** genuine — it names the conversation
kind.

### Not part of the rename (plan-family tokens) — group A

These contain "plan" but are a different concept (the `TaskPlan`/`plan`
object, not the Task Agent conversation) and must not be touched by this
sweep:

| Token | Kind | Where |
|---|---|---|
| `plan`, `task_plan` (table) | table/concept | `core/schema.py`, everywhere |
| `TaskPlan` | class | `runtime/task_plan.py` and consumers |
| `plan_id`, `evidence_scope.plan_id`, `plan.evidence_scope_id` | column | schema, contract deliverable 10 |
| `PlanDraft`, `PlanOut`, `PlanPatchIn`, `PlanStep` | contract models | `api/contract/planning.py` (do not carry the token — § A.2) |
| `PartOptionOut`, `PartChipOut`, `PartProposalOut`, `CountryGroupDraft`, `ScopeConstraintsDraft` | contract models | same file, same reason |
| `PlanCard.tsx`, `PlanDocument.tsx`, `PlanDocument.test.tsx`, `planVocabulary.ts` | frontend files | plan-document surface, distinct from the Task Agent pane |
| `GET/PATCH /plan` route | route | unchanged |
| `plan_stale` | error code | unchanged |
| `source_turn_index` | column | unchanged (turn tracking on the plan row, not a planning-token) |
| `ck_plan_status`, `ck_plan_payload_object`, `uq_plan_task_version`, `fk_plan_scope_task`, `fk_plan_conversation`, `plan_pkey`, `plan_task_id_fkey` | constraints | 038-renamed already; no further change here |
| `docs/knowledge/plan-lineage-by-fencing-not-custody.md` | doc filename | names the plan concept, not the Task Agent; filename never renamed anyway (concept id) |

### Totals — group A

- Files carrying the token across all in-scope directories: **~112** (27 + 29 + 5 report-only + 50 + 4 + 1 + 1 + 13 web-api.md counted separately above; some files counted once here overlap the per-group tables above).
- Distinct identifiers found by the token scan: **126** (§ A.6).
- Total occurrences (backend/src + backend/tests + backend/alembic (report-only) + frontend/src + frontend/e2e + in-scope scripts + web-api.md line-count + DEPLOYMENT.md + docs/knowledge): 428 + 516 + 47 + 533 + 6 + 26 + 1 + 46 = **1603**.
- Known false positives netted out of the above: 6 (2 in `overton_documents.json`, 3 in `test_group_clustering.py`/`test_synthesise.py` fixture text, 1 in `draft_profiles.py`).
- Excluded by path (never touched): `docs/adr/**`, `docs/tasks/**` (other than 043), `docs/specs/sources/**`, `docs/specs/log.md`, `frontend/openapi.json`, `frontend/src/api/gen/types.ts`, `infra/cdk.out`, `scripts/rename_038.py`, three gitignored files.

---

## B. `EB` → `ES` (abbreviation, word-boundary, case-sensitive)

### B.0 Method

`grep -c -w "EB" <file>` (case-sensitive, word-boundary) per file, over:
`docs/specs/**` except `docs/specs/sources/**` and `docs/specs/log.md`;
`AGENTS.md`; `.claude/skills/**`; `docs/tasks/_templates/**`;
`docs/agentic-ops/**`; `backend/src` (any line — comments/docstrings, since
`EB` cannot be a live Python identifier); `frontend/src`.

### B.1 `docs/specs/**` (excluding `sources/` and `log.md`)

15 of 28 tracked `.md` files under `docs/specs/` are in scope (13 excluded:
12 under `sources/` + `log.md`).

| File | Count | Note |
|---|---|---|
| `docs/specs/capabilities/options-scoping/components.md` | 34 | this task's own capability spec |
| `docs/specs/capabilities/evidence-search/capability.md` | 23 | |
| `docs/specs/capabilities/options-scoping/capability.md` | 14 | |
| `docs/specs/capabilities/evidence-search/components.md` | 10 | |
| `docs/specs/capabilities/evidence-search/provenance.md` | 8 | |
| `docs/specs/index.md` | 3 | one occurrence names the frozen source doc informally as "the EB handoff" — see flag below |
| `docs/specs/capabilities/options-scoping/trust.md` | 2 | |
| `docs/specs/product.md` | 2 | one occurrence in a heading, "the EB journey" |
| `docs/specs/system/data-model.md` | 2 | |
| `docs/specs/system/execution-orchestration.md` | 2 | |
| `docs/specs/system/provenance-grounding.md` | 2 | |
| `docs/specs/system/plan-as-object.md` | 1 | inside a `*(...)*` parenthetical — see flag below |

Files with zero occurrences (in scope, checked, nothing to change):
`docs/specs/capabilities/evidence-search/...` — none beyond the four listed;
remaining `docs/specs/system/*.md` and `docs/specs/capabilities/*/*.md` not
listed above returned 0.

**Flagged occurrences** (per the instruction to flag anything inside a
verbatim owner quotation or a `*(...)*` ruling parenthetical): none of the
103 occurrences sit inside quotation marks attributed to the owner
(`grep` for `"..EB.."` inside quotes found nothing). Two sit inside informal
naming of the frozen source document, which the rename must not accidentally
retitle:

- `docs/specs/index.md:19` — `"the doc these EB specs distil"` and the
  general "EB handoff" usage (`index.md:15`, `spec-authoring.md:14`,
  `backlog.md:235` — § B.2) name
  `docs/specs/sources/backend/backend-evidence-base-build-spec.md`
  informally. That source file is itself frozen and out of the EB→ES sweep's
  scope; whether the *informal name* "EB handoff" used in living specs should
  become "ES handoff" or stay as a historical label is a call for the plan
  phase / owner, not decided here.
- `docs/specs/system/plan-as-object.md:100` — `*(...EB handoff §7.1.)*`, the
  same informal citation, inside a `*(...)*` parenthetical. Flagged per the
  instruction; not a ruling attributed to the owner, but matches the
  parenthetical pattern literally, so it is called out rather than swept
  silently.

Command: `grep -n -w "EB" $(cat specs_files.txt)` where `specs_files.txt` is
`find docs/specs -type f -name "*.md" ! -path "docs/specs/sources/*" ! -name "log.md"`.

### B.2 `AGENTS.md`, `.claude/skills/**`, `docs/tasks/_templates/**`, `docs/agentic-ops/**`

| File | Count | Note |
|---|---|---|
| `AGENTS.md` | 0 | none found |
| `.claude/skills/**` (all files) | 0 | none found |
| `docs/tasks/_templates/contract.md` | 3 | line 31 "EB slices commonly touch", line 32 a markdown link path `../../specs/capabilities/evidence-base/capability.md` (note: this path already predates 038's folder rename to `evidence-search/` — likely already stale independent of this task; flag for the plan phase), line 34 "for a non-EB slice" |
| `docs/agentic-ops/spec-authoring.md` | 1 | line 14, "ratified from the EB handoff §2" |
| `docs/agentic-ops/backlog.md` | 1 | line 235, "the architecture + EB specs" |

### B.3 `backend/src` (comments/docstrings) and `frontend/src`

| File | Count | Line(s) | Note |
|---|---|---|---|
| `backend/src/policy_atlas/runtime/runner.py` | 2 | 1 (module docstring "EB capability-runner"), 547 (comment "a future EB-expert agent") | |
| `backend/src/policy_atlas/runtime/task_plan.py` | 3 | 4, 693, 1076 | all docstring/comment prose ("EB chain", "EB component chain") |
| `backend/src/policy_atlas/runtime/agent.py` | 1 | 5 | module docstring |
| `backend/src/policy_atlas/evidence_search/synthesis/synthesise.py` | 1 | 174 | comment, "(EB scope)" |
| `backend/src/policy_atlas/evidence_search/extract/iof_records.py` | 1 | 35 | comment, `("EB's base IOF extraction")` — inside a quoted phrase in a comment, **not** an owner attribution; still in scope for the sweep |
| `frontend/src` (all files) | 0 | — | none found |

Command: `grep -rn -w "EB" backend/src` / `grep -rn -w "EB" frontend/src`.

### Exclusions (kept) — group B

| Item | Why |
|---|---|
| `docs/adr/**` | never edited |
| `docs/tasks/**` other than `_templates/` and `043-scoping-shell-baseline/` | historical record |
| `docs/specs/sources/**` (12 files, incl. `sources/backend/backend-evidence-base-build-spec.md`) | frozen origin |
| `docs/specs/log.md` | past entries are history |
| `docs/knowledge/**` filenames | concept ids, never renamed (note: group B's scope per the contract does not include `docs/knowledge` content either — that sweep is group A's docs group only) |
| Any verbatim owner quotation inside a living spec | none found in this scan (§ B.1) — table kept for completeness per the instruction |

### Totals — group B

- Files in scope with ≥1 occurrence: **12** (`docs/specs`) + 3 (`docs/tasks/_templates` + `docs/agentic-ops` ×2) + 5 (`backend/src`) = **20**.
- Files in scope with zero occurrences (checked, confirmed clean): `AGENTS.md`, `.claude/skills/**`, `frontend/src`, and 3 of the 15 in-scope `docs/specs` files.
- Total occurrences: 103 (`docs/specs`) + 3 (`_templates/contract.md`) + 2 (`agentic-ops`) + 8 (`backend/src`) + 0 (`frontend/src`) = **116**.
- Flagged for plan-phase/owner judgment rather than swept automatically: 2 ("EB handoff" informal citations in `docs/specs/index.md` and `docs/specs/system/plan-as-object.md`) + 1 stale link path in `docs/tasks/_templates/contract.md:32` (pre-existing issue, not introduced by this rename).
