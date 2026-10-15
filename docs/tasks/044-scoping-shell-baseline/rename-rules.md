# Rename rules (task 044, phase one) — lead, Phase 1.1

The rule table `scripts/rename_044.py` runs from. Derived from
[rename-manifest.md](rename-manifest.md), checked against the live
`schema.metadata` on 2026-09-09 (inline iteration; `scripts/schema_manifest.py`
refuses post-038 checkouts — X2). Every open item the manifest flagged is
decided here.

## Live-metadata check (2026-09-09)

`schema.metadata` at `b4b1e93b` carries exactly the objects the manifest § A.1
lists: `ck_conversation_kind` (value only), `ck_conversation_planning_never_archived`,
`uq_conversation_one_active_planning` (predicate value too), table
`planning_transcript`, column `planner_state`, `uq_ptr_task_client_turn`,
`uq_ptr_task_turn_index`, `ck_ptr_status`, `ck_ptr_suggestions_array`. Two
names live only in the catalog, not the metadata (auto- or migration-named), and
the revision must rename what the catalog holds: `fk_planning_transcript_conversation`
(explicitly named in `d8e4a1c7f2b9`) and `planning_transcript_task_id_fkey`
(auto-named, follows the table). The revision verifies both against
`pg_constraint` before renaming.

## Identifier rules (one step; compound before bare)

| # | Source words | Target words | Note |
|---|---|---|---|
| 1 | `planning_transcript` | `task_agent_transcript` | table, module refs, test names |
| 2 | `planner_state` | `task_agent_state` | column |
| 3 | `ptr` | `tat` | constraint infix; the only `ptr` identifiers in the repo are the four constraint names (checked by grep) |
| 4 | `planning` | `task_agent` | conversation-kind sense: `planning_turn`, `PlanningTurn*`, `PlanningPane`, `planning_conversation`, `planning_turn_in_progress`, `planning_router`, stored value `'planning'` |
| 5 | `planner` | `task_agent` | `PlannerBackend`, `OpenAIPlannerBackend`, `StubPlannerBackend`, `PLANNER_MODEL`, `POLICY_ATLAS_PLANNER_MODEL`, `get_planner_backend`, stored value `'planner'` |

Casing follows the engine (snake, camel, Pascal, SCREAMING): `PlanningPane` →
`TaskAgentPane`, `planningComposerPlaceholder` → `taskAgentComposerPlaceholder`,
`PLANNER_MODEL` → `TASK_AGENT_MODEL`. The manifest's ⚠ rows need no manual
casing pass under the 038 engine's word splitter.

## Literal rules

| Pattern | Replacement | Scope |
|---|---|---|
| `planning-turns` (hyphenated route segment) | `task-agent-turns` | every file in the set (route decorators, frontend client, e2e, `web-api.md`) |

## Never mapped (exact identifiers)

| Identifier | Why |
|---|---|
| `planner_v11` and every `planner_vN` version string (a `planner_v\d+` context) | stored provenance values (038 rule R1); the token splits as `planner` + `v11`, so it needs an explicit exclusion; `agent_prompt.py` cites `planner_v5` |
| `eb_iof_base_v1`, `eb_icf_base_v1` | fingerprints |
| `evidence_base_coverage` | legacy steer-point id |
| `planner-proposed` | stored `country_group.authorship` value inside plan payloads (`CountryGroupAuthorship`); not in the contract's rewrite list — found by the lead in the 1.3 OpenAPI diff |

## Never mapped (text contexts)

| Context | Pattern | Why |
|---|---|---|
| wire role literal | `"role": "planner"` (the value only) | the transcript rehydration role (P2); consumers `agent.py:997`, `api/routers/planning.py:256` (moves to `task_agent.py`), and the kept prompt module |
| ordinary English `Replanning` / `replanning` | whole word | UI copy and a 409 detail string; not the code concept. Phase 5 rewrites the paused-composer placeholder anyway |

Ordinary-English `planning` in fixture prose (`"Environmental planning"`,
`"Planning delays…"`, `draft_profiles.py:28`) is a distinct word from the
identifier `planning` only by context; the engine cannot tell them apart, so
these five sites are listed as never-mapped contexts too:
`"Environmental planning"`, `"Strategic planning"`, `Planning delays`,
`planning requirements`.

## File sets

- Code: `backend/src` (`.py`), `backend/tests` (`.py`), `backend/alembic/env.py`,
  `frontend/src` (`.ts`, `.tsx`, `.md`), `frontend/e2e` (`.ts`),
  `scripts/feasibility_checks/options_scoping/run_fresh_neet_search.py`.
- Docs (`--docs`): `infra/DEPLOYMENT.md`, `docs/specs/system/web-api.md`, the
  thirteen `docs/knowledge/*.md` files the manifest § A.5 lists (content only;
  filenames never change), plus the EB → ES file list in manifest § B.
- Excluded: everything 038 excluded (`docs/specs/sources/`, `docs/tasks/`,
  `docs/adr/`, `frontend/src/api/gen/`, `frontend/openapi.json`,
  `.github/workflows/`, `scripts/rename_038.py`, `scripts/schema_manifest.py`,
  `backend/tests/scripts/test_rename_038.py`, `docs/agentic-ops/failure-log.md`),
  **every hash-pinned prompt module** (the keys of `scripts/prompt_hashes.json`,
  read at table-build time — rubric 13 keeps every other pinned hash unchanged;
  `runtime/agent_prompt.py`'s docstring keeps its stale `planner_prompt.py` /
  `planner_v5` mentions, flagged in `verification.md`),
  the historical migration tests (038's `MIGRATION_TESTS` list plus
  `backend/tests/core/test_migration_038.py`, hand-edited to the dual-schema
  strategy where the head catalog is read), `scripts/rename_044.py` and its
  test, and **the prompt module** `runtime/planner_prompt.py` → moved by
  `git mv` to `task_agent_prompt.py` with no interior edit (P2, C14).

## Files moved by `git mv` (not by the sweep)

| From | To |
|---|---|
| `backend/src/policy_atlas/runtime/planner.py` | `runtime/task_agent.py` |
| `backend/src/policy_atlas/runtime/planner_prompt.py` | `runtime/task_agent_prompt.py` (byte-identical) |
| `backend/src/policy_atlas/api/routers/planning.py` | `api/routers/task_agent.py` (manifest proposal, confirmed) |
| `backend/src/policy_atlas/api/contract/planning.py` | `api/contract/task_agent.py` (confirmed) |
| `backend/tests/api/test_planning_router.py` | `test_task_agent_router.py` |
| `backend/tests/runtime/test_planner.py`, `test_planner_prompt.py` | `test_task_agent.py`, `test_task_agent_prompt.py` |
| `frontend/src/views/workspace/PlanningPane.tsx`, `.test.tsx` | `TaskAgentPane.tsx`, `.test.tsx` |
| `backend/tests/core/test_planning_transcript_migration.py` | **kept** (historical migration test, names the old table by construction) |

Callers import the kept symbols (`PLANNER_SYSTEM_PROMPT`, `build_planner_messages`,
`PlannerTurnWire`, `PLANNER_PROMPT_VERSION`, `PlanDraftWire`) from
`runtime.task_agent_prompt`; the sweep rewrites the module path in imports and
leaves those symbol names alone because the prompt module is excluded and its
declared symbols are added to the never-mapped set by the tool (declared-symbol
scan of the excluded file).

## Decisions on the manifest's open items

1. `tat` infix — **confirmed**.
2. Router and contract module renames to `task_agent.py` — **confirmed** (plan S9).
3. Prompt module interior and the wire role literal — **kept** (P2, C14).
4. `"EB handoff"` — the phrase names the frozen source document; **kept**
   wherever it appears (`docs/specs/index.md`, `spec-authoring.md`,
   `backlog.md`, `plan-as-object.md`). Every other whole-word `EB` in the § B
   file list becomes `ES`.
5. `docs/tasks/_templates/contract.md:32` stale link
   `capabilities/evidence-base/capability.md` → `evidence-search/capability.md`
   — fixed in the docs sweep (a dead link, pre-existing; flagged in
   `verification.md` as a minor deviation).
6. `runtime/agent_prompt.py` docstring "the PLANNING moment lives in
   `planner_prompt.py` … the pinned `planner_v5`" — **left as it is**: the
   module is hash-pinned and rubric 13 keeps every other hash unchanged; the
   stale pointer is flagged in `verification.md` for the next `agent_v`
   prompt edit.
7. `planning_turn_in_progress` → `task_agent_turn_in_progress` — renamed
   (manifest § A.2; the frontend is the only consumer). A wire-visible rename
   inside deliverable 2, flagged in `verification.md` next to the path rename.
8. `label="planner"` in `runtime/planner.py:173` (a tracing label) and
   `usage_event="planner.turn.usage"` — renamed with the module (038 renamed
   log and span names with the persona).
9. Knowledge and `web-api.md` prose: code spans (backticks) are swept by the
   identifier pass; prose phrases are rewritten by three phrase rules applied
   in `--docs` mode and read by the lead: `planning turn` → `Task Agent turn`,
   `planning conversation` → `Task Agent conversation`, `the planner` →
   `the Task Agent`. Other prose uses of "planner"/"planning" (for example
   "re-planning visibility", "planner-class model") are left and listed.
