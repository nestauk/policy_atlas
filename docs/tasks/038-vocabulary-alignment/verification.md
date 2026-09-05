# Verification: 038-vocabulary-alignment

Evidence for one slice. Public-safe: no secrets, raw source text, credentials or
unredacted traces. Filled at step 6; **Review findings** and **Rubric status** are
added after the review stack (step 7). Defect ids V1–V12, invariants I1–I12 and
decisions D1–D9 are defined in [contract.md](contract.md) and [plan.md](plan.md).

## Build log (phase by phase)

### Phase 0 — build-open baseline (2026-09-04)

- Branch `task/038-vocabulary-alignment` at `0d4fa5ae` (plan approved).
- `make verify`: backend 2442 passed (8m06s); `make -C infra test` **red** on
  `test_dockerignore_covers_gitignored_backend_content`: the design phase added
  `.impeccable/` to `.gitignore` (V12) without the `backend/.dockerignore`
  counterpart. Fixed (one line, V12 scope); infra 46 passed; the remaining
  root gates (`audit-paths`, `prompt-guard`, `font-guard`, `drift-check`,
  `frontend-verify`) green. Baseline green.
- `scripts/schema_manifest.py | diff - schema-manifest.md`: **not empty on the
  first run** — two FK rows swapped between runs. Root cause: the constraint
  sort key used the raw `con.name`, which is `None` for PostgreSQL auto-named
  FKs, so their relative order depended on set iteration. Fixed by sorting on
  the resolved name; three consecutive runs are now byte-identical and the
  manifest was regenerated (content unchanged, 24 rows re-ordered). Flagged as
  a build-time tool fix outside the plan's file list (deterministic work must
  be deterministic — AGENTS.md).

### Phase 1 — V10 riders (`fast-worker`)

- `git rm` `frontend/src/views/workspace/RunPane.tsx`, `RunPane.test.tsx`,
  `journey/JourneyPane.tsx`. Pre-deletion grep: the only importers were
  RunPane's own test and RunPane itself (for JourneyPane). Rubric 5
  justification: dead code, imported by no route (deferred.md entry).
- `http_budget` → `call_budget` in `evidence_base/sourcing/search_loop.py`
  (field, three depth-constant keys, reader, comment) and the comment in
  `tests/evidence_base/sourcing/test_search_loop_deep.py`. `grep -rn
  http_budget backend` is empty (I10).
- Newly orphaned by the deletion, **not** removed here (Phase 8 knip pass):
  `journey/presentation.ts` exports `FUNNEL_STAGES`, `funnelBarWidth`,
  `completionCopy` are now referenced only by `presentation.test.ts`.
- Gates: ruff + mypy clean; `pnpm typecheck/lint/test/build` green (75 files,
  532 tests); `pnpm e2e` 11 passed. Backend `make verify-fast` run by the lead
  before commit (g).

### Phase 2 — sweep tool (`deep-reasoner`)

- `scripts/rename_038.py` (stdlib): word-sequence tokeniser with positional case
  transfer; step 1 / step 2 as disjoint rule sets; per-file collision check;
  a per-checkout ledger (`scripts/.rename_038_state.json`, gitignored) for
  idempotence plus a fresh-clone guard (`--apply` refuses on a tree that already
  looks swept unless `--force`). Unit test `backend/tests/scripts/test_rename_038.py`.
- Scan tables committed: `scan-backend.md` (290 files, 219 to change, 17,225
  replacements, 479 renames, 0 collisions), `scan-frontend.md` (210 files, 113 to
  change, 2,256 replacements, 75 renames, 2 collisions — below). **Both identifier
  tables reviewed and approved by the lead before Phase 3.**
- **Lead rulings on the scan (D1 unmapped list and D4):**
  - Two frontend collisions, one of them unpredicted by D4: `useCreatePortfolio →
    useCreateProject` (the dead `useCreateProject` still owns the name — its
    deletion moves from Phase 8 to a Phase 4 pre-step, so that one V12 item is no
    longer droppable; flagged deviation from P5) and `PortfoliosView.tsx`'s local
    `projects` → `tasks` (already declared; hand pre-renamed to `tasksQuery`).
  - `oplan` infix → `plan` added as a step-1 rule (contract V4 names the targets).
  - `Orchestration*` prose (64 comment/docstring sites): word table applied
    post-sweep — "orchestration plan" → "task plan" (matches `TaskPlan`),
    "orchestration step" → "plan step", "Runtime orchestration layer" → "Runtime
    layer", generic engineering uses (clustering engine, 3 sites) → "coordination".
  - Accepted tool divergences from D2's whole-file reading: copy modules and
    prompt files are exempt at the *string-literal* level (their identifiers and
    imports must still move or I4 fails and imports break); exact `Task`/`Tasks`/
    `Project`/`Projects` are never-mapped in the frontend (screen vocabulary in
    prose, verified 69 sites); a docstring-initial verb "Project a/the/…" guard,
    with the two determiner-less verb sites in `repository.py` reworded by hand
    to "Map …".
  - Prompt files: every string literal (incl. the `orchestrator_v1` family id) is
    left to the lead's 3.3 pass; the family id becomes `agent_v1` (A6: no stored
    row carries it).
  - File renames beyond the plan's six `git mv`s, found by the dry run:
    `api/contract/{projects,portfolios}.py`, `api/routers/{projects,portfolios}.py`,
    their router tests, `tests/runtime/test_orchestrat*.py`, `test_orchestration_plan*.py`,
    `frontend/src/views/PortfoliosView.{tsx,test.tsx}` — done in 3.1 / 4.1.

### Phase 3 — schema, backend sweep, compatibility, prompts (one green commit, b)

- **3.1 (lead, one command):** `rename_038.py --apply --phase 3 --step all` — 219
  files, 17,225 replacements (step 1: project→task 11,793 · pss→tss 1,964 ·
  project_source_snapshot 927 · evidence_base 555 · orchestrator→agent 388 ·
  orchestration_plan→task_plan 354 · orchestrate→agent 42 · oplan→plan 12 · the
  `"orchestration_plan"` table string → `"plan"` 1; step 2: portfolio→project
  1,166). `git mv` of the package, five runtime modules, the four contract/router
  modules and eight test modules (order: projects→tasks before
  portfolios→projects). `prompt_hashes.json` keys re-pathed. Post-sweep: `ruff
  --fix` re-sorted imports in 98 files; two lines re-wrapped.
- **3.1b (lead ruling on D1's unmapped `Orchestration*` prose):** word table over
  backend comments/docstrings (excluding prompt files and the sweep's own test).
  My generic fallback also reached three of the eleven hand-edited migration
  tests; reverted them to HEAD so 3.2 gets them in a consistent old vocabulary.
- **Sweep misses found and fixed:** `tests/api/test_contract_models.py` `data=[project]`
  survived because the never-map pattern for the pyproject `[project]` table
  header also matched a list literal — pattern tightened to a line-initial match,
  one unit-test case added (`rows = [task]` vs a `[project]` header line).
  Two `:mod:` docstring paths in `synthesis_backend.py` (string-exempt file)
  fixed by hand.
- **3.3 (lead, prompt-bearing, R1):** the enumerated swaps applied by `sed` and
  recorded in [prompt-diff.md](prompt-diff.md): "You are the orchestrator of Policy
  Atlas" → "…the agent of…"; "to the orchestrator, flagged" → "to the agent…";
  "the orchestrator handles those" → "the agent handles those"; "project's
  committed evidence" ×2 and "the project frame" ×2 → task; the steer-point list
  `evidence_base_coverage` → `evidence_search_coverage`; "draft of the
  orchestration plan" → "…task plan"; "One orchestrator agent" / "orchestrator
  agent pointed at" → "agent" (the qualifier drops, no meaning change); the
  family id `orchestrator_v1[_router|_watch]` → `agent_v1[…]` (A6: no stored
  row carries it); `synthesis_backend.py` inline prompt: "this project's tag set"
  and "canonical project state / scoped to this project" → task. No version
  suffix moved. `prompt_hash_guard.py --update` re-pinned 13 hashes.
  **Minor deviation flagged:** contract V3 says the component prompt hashes stay
  identical after the package move; seven of the ten changed because their
  `import` lines moved. The diff shows those hunks are imports only.
- **3.2 (`deep-reasoner`) — migration `c1a7f4e9b0d2_vocabulary_alignment.py`** on
  head `b2f6a9d4c1e7`: 126 rename statements (step 1: 3 tables · 30 columns · 79
  constraints · 2 indexes; step 2: 2 tables · 2 columns · 6 constraints · 2
  indexes; 85 constraint renames = 60 FK · 11 UNIQUE · 9 CHECK · 5 PK), the union
  view dropped first and recreated with `task_id`, `ck_capr_capability` swapped
  around the `capability_run` UPDATE, `SET LOCAL lock_timeout='5s'` both ways
  (P13). `downgrade()` reverses the five stored values under the new names, then
  step 2, then step 1 (D6). Verified: after downgrade the `pg_constraint`,
  `pg_indexes`, `pg_attribute`, `pg_tables` dumps are byte-identical to the
  pre-migration catalog.
  - **Manifest correction (flagged):** six FK rows in `schema-manifest.md` carried
    SQLAlchemy auto-names (`<table>_<col>_fkey`) for FKs that earlier migrations
    created under explicit names (`screening_scope_project_id_fkey`,
    `fk_orchestration_plan_conversation`, `fk_project_org_id`,
    `fk_portfolio_org_id`, `fk_portfolio_membership_{portfolio,project}_id`). The
    migration renames the real catalog names (renaming to the auto-names would
    break older revisions' `downgrade()`). `scripts/schema_manifest.py` gained an
    `EXPLICIT_FK_NAMES` map and the manifest was regenerated **from the pre-sweep
    metadata** (commit `6c9e0621` in a temporary worktree — on the swept tree the
    generator's old→new mapping is meaningless); the diff is exactly those six rows.
  - D5 helpers: `steering_events.canonical_actor()` applied at `routers/sse.py`
    (check-in frame), `readmodels/repository.py` (decisions read model) and
    `runtime/runner.py` `_watch_digest` (a stored-actor projection the contract's
    list missed); `task_plan.canonical_steer_point()` as a `mode="before"`
    validator on `SteerPointDefault.steer_point` and in `checkin_read.py` and
    `continuation.py` (two sites); `lifecycle.both_generations()` /
    `LIFECYCLE_EVENT_KINDS` feeding `_EVENT_KINDS`, the decision text map and the
    two `routers/sse.py` event-type checks. `steering.py` `EVIDENCE_SEARCH_COVERAGE`
    value corrected to the new id. Tests: `tests/api/test_pre_038_vocabulary_compatibility.py`
    (7 tests, old value in → new value out through the real read paths).
  - **Flagged deviations (resolved within the contract's vocabulary):** (i) the
    contract named `checkin_read.py` and `continuation.py` as `canonical_actor`
    sites; neither projects a *stored* actor (`continuation.py:991` constructs
    `authored_by="agent"` from a boolean) — the helper went to the three real
    projections instead. (ii) `_EVENT_KINDS` never included the two sharing
    kinds; adding them to the decisions read model would be a behaviour change,
    so only `renamed`/`archived` are paired there; `both_generations` accepts all
    four so the pairing is available. (iii) The 025 migration backfilled planless
    Tasks with the literal name `"Untitled project"` — user-editable data, not
    one of the five reversible values; left as is → `deferred.md` § Vocabulary.
  - D9: new `tests/core/legacy_catalog.py` (reflection helpers used only below
    the 038 revision); the eleven migration tests reflect old names below the
    revision and use current metadata at head (per-file notes in the agent
    report; assertions unchanged in meaning). Spillover: three round-trips in
    `tests/core/test_schema.py` had the same shape and were fixed the same way.
  - New `tests/core/test_migration_038.py` (2 tests: catalog equals the manifest
    at head with no retired name surviving except the Project entity's reuse of
    `project*`; populated pre-migration DB round-trips byte-identically with each
    of the five reversals asserted independently). `uv run pytest tests/core -k
    migration`: 24 passed.
  - Hand list: ops CLI (`--task`/`--project`), `Makefile` 3/42/72 + wrapper test,
    `infra/DEPLOYMENT.md` env rows, source paths, lock SQL and § 8 prose,
    `README.md`, `scripts/fe_api_smoke.sh`; `docker-compose.yml` nothing;
    Langfuse metadata already `task_id`; `scripts/scratchpad/run_live_deep.py`
    imports fixed (deleted in Phase 8 anyway).
  - **Unpredicted collision, mid-sweep (contract stop condition, resolved and
    flagged):** in `ops/cli.py` both `rows assign` flags became `--project`. Root
    cause: the tool's never-map pattern for `uv run --project` matched *any*
    `--project`, so step 1 left the Task flag alone and step 2 renamed
    `--portfolio` onto it; the sweep's collision check sees declared symbols, not
    argparse strings. Resolution is unambiguous — the contract names `--task` /
    `--project` — restored by hand (plus the `commands.py` error string "give
    exactly one of --task or --project"), covered by the 19 ops tests and the
    Makefile wrapper dry-run test. Tool pattern tightened to `(?<=uv run )--project`
    with a unit-test case.
- **3.4 done check:** the residual grep (`orchestrat|evidence_base|portfolio` over
  `backend/src backend/tests scripts Makefile infra/DEPLOYMENT.md README.md
  docker-compose.yml`) returns only accepted residue: the two D5 compatibility
  maps (`steering_events._LEGACY_ACTORS`, `task_plan._LEGACY_STEER_POINTS`) whose
  data *is* the retired word; the eleven D9 tests, `legacy_catalog.py`,
  `test_migration_038.py`, `test_pre_038_vocabulary_compatibility.py` and the 038
  migration (they must name the pre-038 catalog and values); the sweep tool, its
  test, the manifest generator and the ignored ledger; recorded fixtures and
  `tests/data/`. **I4 is read as "no live use of the retired word", not zero bytes.**

- **Screen-sense prose (found at the Phase 3 gate, fixed):** 033/037-era
  docstrings and comments already used the *screen* words ("an owner setting a
  Project private and leaving its Tasks readable"). The backend sweep maps
  `Project`→`Task` in the code-word sense, so those 24 lines read "a Task inside a
  Task" after the sweep. Found by pairing every removed line carrying title-case
  `Project(s)` with its replacement and filtering for lines that also name Tasks,
  portfolios or a visibility phrase; restored positionally (`app.py`, the two
  ex-portfolio contract/router modules, `routers/tasks.py`, four test modules),
  and the two module docstrings that explained the ADR 0031 split rewritten to
  say the words now agree. The frontend sweep is immune (exact `Project`/`Task`
  are never-mapped there).
- **Phase 3 gate:** `make verify` = backend 2517 passed (8m16s) · infra 46 passed
  · `audit-paths`, `prompt-guard`, `font-guard` green · **`drift-check` red by
  construction** — the plan assigns `make openapi-sync` and `drift-check` to
  Phase 4 (the generated client cannot be regenerated before the frontend sweep
  without breaking `frontend-verify`), so the API rename is atomic across (b)+(c)
  and (b) closes on everything except drift-check; `frontend-verify` is
  unchanged since Phase 1's green run. After the screen-sense fixes: ruff, mypy
  and the touched test modules re-run green (see Commands run).

### Phase 4 — API paths, generated client, frontend sweep, copy (review commit c)

- **4.1 (lead, inline):** pre-steps for the two predicted collisions — deleted the
  dead `useCreateProject` (moved forward from Phase 8; the only V12 item no longer
  droppable) and renamed both `projects` query handles in the two components of
  `PortfoliosView.tsx` to `tasksQuery`; three comment lines there reworded because
  the tool's collision check also counts prose occurrences of the source word.
  `rename_038.py --apply --phase 4 --step all`: 113 files, 2,308 replacements
  (step 1: project→task 1,775 · evidence-base 13 · evidence_base 12 ·
  orchestrator→agent 3; step 2: portfolio→project 505). `git mv PortfoliosView.*`
  → `ProjectsView.*`. `make openapi-sync` regenerated `openapi.json` and
  `gen/types.ts`. Post-sweep `pnpm typecheck`: 3 errors, all sense errors, not
  omissions (below).
- **Screen-sense identifiers (frontend counterpart of the Phase 3 finding):** a
  few frontend identifiers were *already* named in the screen sense and the
  code-word sweep inverted them: `ProjectPicker` (picks Projects, ex-portfolios)
  → wrongly `TaskPicker`; `showProjectPrefix` (shows the Project prefix on a task
  row) → wrongly `showTaskPrefix`; `COPY.noProject` ("No project") → wrongly
  `COPY.noTask`. Restored in 4.2. The generic identifiers (`useProject`,
  `ProjectOut`, `allProjects = useProjects()`, `projectName` …) were all
  code-word sense and are correct as `task`. `landingPresentation.ts` referenced
  `"ProjectOut"` inside a string literal (copy-exempt file) → `"TaskOut"` by hand.
- 4.2 (`fast-worker`): see below.

- **Follow-on (owner ruling 2026-09-05, after seeing the build) — the Agent
  tab is a two-column page.** The owner's intent for "the Agent tab hosts all
  of a Task's chats in a sidebar" is a persistent sidebar with the conversation
  list and the *selected* conversation in the main view — not the collapsible
  overlay launcher the first cut left in place (5b judgment call 1, resolved the
  other way). As built: `WorkspaceView` = `ConversationSidebar` (new; `aside
  "Chats"`, New chat action + `ConversationList`, always visible, `lg:w-80`,
  stacks above on narrow viewports) + main column = today's planning layout
  (`PlanningPane` + `PlanDocument` rail) when the Task Agent is selected, else
  `ChatPane` in the shared reading column with the rail shut. Selection is the
  existing `?chat=` param (deep links and the other tabs' overlay share it;
  choosing the Task Agent clears it; a planning id in the param reads as the
  Task Agent, never a second thread). `ConversationList` is the list body
  extracted verbatim from `ChatsLibrary`, which is now only the dialog frame —
  one list component in two frames. The overlay is back to every tab but Agent
  (`AppShell.showChatPanel` has `!inWorkspace` again); `planningInMainPane`,
  `focusTaskAgent` and the launcher backstop were deleted. Owner-only mutation
  gating unchanged (A9 test: a non-owner sees the same rows, read-only).
- **Bug the always-on sidebar exposed (fixed, flagged):** `seedCreatedConversation`
  wrote a newly created active conversation into every cached list under the
  task's conversations key, the archived list included — invisible before
  because nothing kept the archived list cached; now a `predicate` skips the
  archived leg, with a unit guard. A behaviour fix, not a rename.
- Tests: `WorkspaceView.test.tsx` (10: sidebar with one Task Agent first,
  planning pane by default, chat swaps the main column and shuts the rail,
  `?chat=` deep link, Task Agent restores and clears the param, planning id
  reads as the Task Agent, New chat creates and opens, non-owner A9);
  `AppShell.test.tsx` overlay never on the Agent tab, on the other task tabs,
  never outside a task; `journey.spec.ts` step (b) drives the sidebar and a
  chat round trip. Gates: typecheck clean · lint 0 errors · `pnpm test` 75 files
  / 549 passed · build OK · `pnpm e2e` 11 passed (journey re-run 3× clean).
- Open owner calls surfaced by the permanent sidebar: the pinned row shows
  "Task Agent" as both name and chip (dropping the kind chip for planning rows
  is one line); a brand-new chat is titled "New chat" under the "New chat"
  action (inherited from the create title); the sidebar is fixed-width where
  the overlay is resizable.

- **Polish pass (owner requests 2026-09-05, lead-built with the impeccable
  `polish` playbook; refinement, incumbent Nesta world kept):**
  - Chips gone: the "Task Agent" kind chip, the Open/Closed status chip and the
    Report chip — rows are a title only, truncated to one line, the Task Agent
    marked by the brand mark; rename/archive/restore surface on hover or focus
    (same `aria-label`s, so every test selector held).
  - Sidebar collapsible: a toggle (`aria-expanded`, "Hide chats"/"Show chats")
    shrinks it to a 48px rail carrying the toggle, New chat and the Task Agent
    (current-marked); the choice persists per browser in `localStorage`
    (try/catch; wide viewports default open, narrow ones shut).
  - Archived chats behind a native `<details>` disclosure, shut by default,
    with a count and a rotating chevron.
  - Footer: `WorkspaceView` now renders `AppFooter` under both columns, so the
    sidebar never overhangs it; `PlanningPane`'s reveal-on-scroll footer (and
    its measurement/hysteresis code) is deleted — the overlay's planning
    duplicate no longer carries a footer inside a 416px panel either.
  - Consistency: the selected row uses the Result tab contents nav's marker (a
    2px blue left rule + bold), the tinted `paper-2` surface and caption-scale
    uppercase group labels; the overlay's `ConversationTabs` strip and
    `ChatsLibrary` dialog take the same surface, brand mark, icon set and list
    body (`icons.tsx` replaces the inline SVGs and the `+`/`×` glyphs).
  - Inspection: before/after screenshots at 1440 and 390 (Agent tab open,
    chat selected, rail, mobile shut/open; Result tab overlay and library);
    one round of fixes (rail marker resolved through the Task Agent id).
  - Tests: `ChatsLibrary` (title-only rows, disclosure opened before the
    restore), `WorkspaceView` (footer under both columns, collapse round
    trip), `PlanningPane` footer test retired, `journey.spec.ts` (row order
    after the two header actions; opens the Archived disclosure). Gates:
    typecheck clean · lint 0 errors · `pnpm test` 75 files / 550 · build OK ·
    `pnpm e2e` 11 passed.

- **Second pass (owner requests 2026-09-05, lead-built):**
  - **Overlay ≡ sidebar.** `ChatSidePanel`'s tab strip (`ConversationTabs`) and
    floating library dialog (`ChatsLibrary`) are retired; the panel header is
    the sidebar's folded: a list toggle (`aria-pressed`) that swaps the body for
    the same `ConversationList`, the conversation's name with the brand mark
    for the Task Agent, New chat, close. The session-tab state
    (`openChatTabs`/`addOpenChatTab`/`removeOpenChatTab`) is deleted with it.
  - **Task Agent always listed.** On a completed task the run closes the
    planning lineage and the active listing carries no planning row, so the
    sidebar showed none. `ConversationList` now pins a synthetic Task Agent row
    (`PLANNING_TAB_ID`, which every consumer already resolves to the planning
    thread). Test: "still lists the Task Agent when the listing carries no
    planning row at all".
  - **Drafts.** New chat (sidebar, rail, overlay header) and "Ask about this
    analysis" open `?chat=new[&entry=<artefact>]`: `DraftChatPane` shows the
    empty state, the starters, the entry-artefact chip and a live composer; the
    row is created on the first message, the message is handed to the real
    `ChatPane` via `stashFirstMessage`/`takeFirstMessage`, and the URL moves
    onto the new id. Abandoning a draft leaves nothing behind. The overlay
    launcher opens the latest chat or the Task Agent — it never creates.
  - **No chats before a result.** `lifecycle.hasResult(status)` (succeeded or
    degraded — a run still writing is not a result, even though the Result tab
    already opens) gates New chat everywhere: offered, disabled, with the reason
    in `COPY.newChatUnavailable`.
  - **Sidebar shut by default;** the stored choice still wins.
  - **Scroll and footer.** The planning pane's and the chat pane's scroll
    regions now span the whole main column (the reading column sits inside),
    so the scrollbar is at the pane's edge like every other tab; both panes
    report "flush with the end" with hysteresis (`onAtBottomChange`) and
    `WorkspaceView` reveals the site footer under both columns only then,
    animated on `grid-template-rows`.
  - Tests: `ConversationList.test.tsx` (from the library tests; synthetic Task
    Agent, draft row), `ChatSidePanel.test.tsx` rewritten (launcher opens the
    Task Agent, header/list toggle, draft, gating), `WorkspaceView.test.tsx`
    (shut-by-default, draft flow, gating, footer under both columns);
    `journey.spec.ts` follows (New chat disabled before the run; the chat
    round trip and the completed-task sidebar after it; the draft from "Ask
    about this analysis"; the overlay's list). Gates: lint 0 errors ·
    typecheck clean · `pnpm test` 74 files / 549 · build OK · `pnpm e2e` 11.

- **List scope default (owner request 2026-09-05):** the Tasks and Projects
  lists open on **Mine**; the switcher leads with Mine. UI default only — the
  API's `scope=all` default (033: "a `mine` default would hide the whole
  feature behind a switcher") is unchanged, and the admin wide-list notice
  still appears under Organisation. Tests updated in `TasksListView.test.tsx`
  and `ProjectsView.test.tsx`; gates: typecheck · lint 0 errors · 549 tests ·
  build · e2e 11.

- **Motion pass (owner request 2026-09-05, `emil-design-eng` skill, lead):**
  the codebase was already clean of `transition: all`, `ease-in` and
  `scale(0)` entrances; hover states are gated by Tailwind v4's `hover:` media
  query and reduced motion is handled globally. Changes: theme easing tokens
  `--ease-out-strong` (0.23, 1, 0.32, 1) and `--ease-drawer` (0.32, 0.72, 0, 1);
  a `pressable` utility (`scale(0.97)` on press at 160ms, colours at 150ms) on
  `Button` and every icon button in the sidebar, rail, overlay header, list
  rows and the launcher; Radix popover and tooltip now scale in from their
  trigger's `--radix-*-transform-origin` (150ms / 125ms) via `starting:`;
  the sheet's inert `animate-in fade-in` classes (no plugin was installed)
  replaced by a real 200ms overlay fade and a 260ms slide on the drawer curve;
  toasts enter from below at 200ms; `anim-rise` 420ms → 300ms. Left as is:
  `anim-glow` 900ms marks a check-in arriving (rare), `anim-breathe` is a
  loading pulse. Verified in the built CSS (`ease-out-strong` ×5, `pressable`,
  `@starting-style` rules present). Gates: lint 0 errors · 549 tests · build ·
  e2e 11.

- **Footer reveal, stickier (owner request 2026-09-05):** arriving at the
  transcript's end no longer opens the footer, so the composer can rest at the
  bottom of the screen. `useFooterReveal` (shared by the planning pane and the
  chat pane) opens it only after 80px of further wheel travel while already at
  the end, and closes it on any wheel up or a 120px scroll back; it starts
  hidden. The planning pane's pin observer now also watches the scroll
  container, so the footer opening does not leave the newest turn a footer's
  height above the true bottom. Unit test on the hook (three cases); gates
  green (typecheck · lint · 552 tests · build · e2e 11).

### Phase 6 — one Langfuse session per Task (V9, review commit e) — `fast-worker`

- `routers/planning.py` planning turn, `chat_turns.py` chat turn and
  `routers/runs.py` `_dispatch_run` → `run_plan(...)` all pass
  `session_id=task_id` (the runner already threads it through steering, watch
  and continuation state). `conversation_id` added to trace metadata:
  `core/tracing.component_span()` gained a `conversation_id` keyword (chat turn);
  `runtime/planner.plan_turn()` (Protocol + both backends) gained the same and
  puts it in the `planner:turn{N}` generation metadata.
- Test `tests/api/test_trace_sessions_038.py` (3 tests, recording Langfuse fake):
  planning turn, chat turn, and a run parked at a steering point then resumed —
  every span on both sides of the park carries `session_id == str(task_id)`; the
  chat and planning turns carry `conversation_id` (I9).
- Test-double fallout (rubric 5: signature widening only): three assertions in
  `test_planning_router.py` encoded the old per-conversation session and now
  expect the task id; nine `plan_turn` test doubles across
  `test_planning_router.py` and `test_agent.py` accept the new keyword. The CLI
  planning loop in `runtime/agent.py` is a fourth `plan_turn` caller outside V9's
  three sites and is unchanged (default `None`).
- Gate: ruff + mypy clean; 82 targeted tests green; the backend suite ran again
  inside Phase 4's full `make verify` (the plan allows consecutive phases to
  share one full gate).

### Phase 9 — living docs, specs, verification (V7; step 6)

- **Lead (specs and ADR cross-references):** two-step word pass over the living
  system specs, `product.md` and `capabilities/evidence-search/*` (code-word
  `project`→`task` then `portfolio`→`project`; persona `orchestrator`→Agent;
  "orchestration plan"→"task plan"; steer-point id; API paths and schema names),
  `log.md` and `sources/**` untouched (history and frozen). Hand rewrites:
  `data-model.md` § Entity hierarchy names both rows and ADR 0036;
  `web-api.md` additive-only rule points at the one recorded break and
  § Deprecations carries the dated 038 entry (paths, schemas, fields, SSE frame,
  wire literal, no redirects, rollback pointer); `index.md` routing table gains
  `vocabulary.md`, the Agent wording, "Evidence search run", and the I7
  frozen-source mapping note; `vocabulary.md` § Code words is the as-built table
  (entity → table → route → TS type/key → pre-038 word) plus the read-side
  stored values and the kept `eb_*` ids, and the owner's three "at the moment"
  notes now say "until task 038"; ADR 0031 decision 2 marked superseded by ADR
  0036 (status bullet + in-place note; decision 1 stands). `make okf-validate`
  green.
- **I4 residue in docs/specs (accepted):** the spec file id and title
  `system/execution-orchestration.md` / "Execution & orchestration" and its
  `orchestration` tag name the engineering concept (coordinating components),
  not the persona; links to it from other specs; `log.md` (changelog, history).
  Everything that named the persona says Agent.
- `fast-worker` (docs/knowledge bodies, deferred.md words): see below.

### Phase 8 — repo hygiene (V12, review commit h, last and droppable) — `fast-worker`

- **Part 1 (deletions and moves):** `git rm` `frontend/e2e/live-027.spec.ts`,
  `live-027b.spec.ts`, `live-028.spec.ts`, `playwright.live-027.config.ts`,
  `playwright.live-028.config.ts` (rubric 5: slice-specific live checks of merged
  work, referenced by nothing — `Makefile`, `package.json`, `scripts/`, `.github/`
  grep clean; `playwright.fe-api-smoke.config.ts` kept). Dead backend functions
  `chat_floor._sentence_around` and `steering.resolve_unattended` deleted (zero
  references in src and tests; `OpenAIRelevanceAnnotatorBackend` kept, A12).
  `git rm -r scripts/scratchpad docs/tasks/029-search-volume-cap
  docs/tasks/030-multi-round-search` (repo-wide referrer grep clean). `git mv
  JUMPBOX.md infra/JUMPBOX.md`; referrers updated: `infra/DEPLOYMENT.md` (the
  one real link) and the bare filename mentions in
  `docs/tasks/030-rds-jumpbox/verification.md`, `033-organisations/plan.md`,
  `033-organisations/verification.md` (rubric 15 exception). One further bare
  mention in `docs/tasks/033-organisations/contract.md` (lines 95, 417) left
  untouched — historical doc, not in the rubric's list.
- Ignore entries confirmed: `.gitignore` carries `.cursor/hooks.json`,
  `.github/hooks/`, `.impeccable/`, `scripts/.rename_038_state.json`;
  `backend/.dockerignore` carries `.impeccable/`.
- `uvx vulture src/policy_atlas --min-confidence 80`: 17 lines, all the known
  false-positive classes — `cls` on pydantic validators (`contract/waitlist.py`
  ×2, `runtime/task_plan.py` ×13) and `exc_type`/`traceback` context-manager
  args (`sourcing/fetch_live.py` ×2). `wc -l AGENTS.md` = 51, no phase state.
  `git ls-files scripts/scratchpad docs/tasks/029-search-volume-cap
  docs/tasks/030-multi-round-search JUMPBOX.md` empty (I12).
- Gates: ruff + mypy clean; `tests/runtime/test_chat_floor.py`,
  `test_steering.py`, `test_steering_unattended.py` 120 passed.
- Part 2 (knip dispositions, D8): see below.

### Phase 7 — post-sign-in landing (V11, review commit f) — `deep-reasoner`

- `App.tsx` (+20/−1): one `useEffect` in `AppRouter`, unconditional, runs when
  `status === "authenticated"`; compares `authenticatedRouter.state.location`
  (pathname+search+hash) with `window.location` and, only on mismatch, calls
  `authenticatedRouter.navigate(target, { replace: true })` once. Nothing else
  changed: `OidcAuthProvider.onSigninCallback` stays the sole reader/remover of
  `AUTH_RETURN_TO_KEY` (writers: `StashAndSplashRedirect`, `RequireAuth`,
  `PublicTaskShell.onSignIn`, `onUnauthenticated`, `retrySignIn`; verified by
  grep); `StashAndSplashRedirect` and `routes.tsx` untouched.
- Tests (`App.test.tsx`, real `App` + real module-level routers, auth via the
  existing `VITE_MOCK` seam; no new test seam): (1) router/URL mismatch after the
  callback → navigates exactly once to `/tasks/<id>/sources`; (2) already
  synchronised → no navigation; (3) the 036 stash-and-splash flow end to end
  (signed-out deep link → stash → callback restores → lands). Anti-vacuity:
  with `App.tsx` stashed, tests 1 and 3 fail. StrictMode probe: exactly one
  `navigate` call (no ref guard needed).
- react-router 7.18.1 facts relied on (from the installed package):
  `createBrowserRouter` initialises immediately, so both singletons are pinned
  to the `window.location` at import; `history.replaceState` fires no
  `popstate`, so the router cannot observe the callback's rewrite;
  `router.navigate(to, { replace: true })` → `REPLACE`. **For the security
  lane:** `router.state` is annotated `@private` in the `Router` type (as is
  `subscribe`); `navigate` is public. The contract pinned `state.location` and
  `routes.test.tsx` already reads it — precedent, but an officially-private read.
- Security reasoning (for the lane): the target is same-origin by construction
  (pathname/search/hash only, no scheme or host, nothing from storage or query);
  the effect runs only once auth is `authenticated`, behind the unchanged
  `RequireAuth`; a second stash consumer was deliberately not added.
- Note: the V11 transition is a *mount* of `AppRouter` (the OIDC adapter renders
  a loading paragraph until auth settles, and the Cognito round trip is a full
  page load), so the tests mount fresh per phase rather than re-render.
- Gate: the worker's 3 tests pass; `pnpm lint` 0 errors; whole-suite gate run
  by the lead after Phase 5a (concurrent) lands — see Commands run.

### Phase 5b — Task Agent (V8, review commit d) — `deep-reasoner`

- Copy (binding table): overlay `aria-label` "Agent"; launcher "Open the Agent" /
  "Agent"; pinned tab and library chip "Task Agent"; "Message the Task Agent";
  "The Agent decided" (key already `agent`; the backend canonicalises stored
  `orchestrator` on read); `store/types.ts` already `"agent"`. New `COPY` keys
  `agentAriaLabel`, `openAgent`, `agent`, `taskAgent`, `earlierPlan`,
  `messageTaskAgent`.
- Pinning rule (no new state, no query change — A9): `conversationState.
  taskAgentConversationId(rows)` = open planning row, else newest closed, else
  the planning tab id; `ConversationTabs` renders it first and it is the only row
  with the label (A10); `ChatsLibrary` hoists it above the date groups, names and
  chips every planning row by label so the stored title "Planning" never
  surfaces; older lineages read "Earlier plan", unpinned.
- Overlay on the Agent tab: `AppShell.showChatPanel` drops `!inWorkspace` and
  passes `planningInMainPane`; every in-overlay path to the planning conversation
  routes through one `focusTaskAgent` (focus `#planning-message` in the main
  pane, close the overlay); backstop: with `?chat=` naming a planning row on that
  tab the panel renders the collapsed launcher, never a second transcript.
  Verified in a real browser: one `#planning-message`, one "Planning
  conversation" region.
- **Flagged deviation (defect found and fixed):** the shared `Composer`
  hard-coded `id="planning-message"`, a pre-existing duplicate id whenever the
  overlay was open, which also made the hand-off focus the *chat's* composer and
  would have put "Message the Task Agent" on every chat. `Composer` now takes
  `id`/`label` (Task Agent defaults); `ChatComposer` passes
  `chat-message-<id>` and **"Message the Agent"** — one new copy string outside
  the binding table (the persona is the Agent in every chat; A10 kept).
- I8 grep `'"Planning"'` over `src` (non-test): `mock/api.ts:156` (the mock's
  stored title, mirroring the backend — kept so the mapping is exercised),
  `historyPresentation.ts:83` (History category, unchanged by contract), one
  comment. "Task Agent" rendered only via `COPY.taskAgent` in four components.
- Judgment calls for the reviewer: the overlay still rests collapsed on the Agent
  tab unless `?chat=` is set (I8's "list is visible" = when open); a planning row
  is named twice (title + chip, mirroring today's shape); **"Earlier plan" is
  unreachable in production** (closed planning rows are filtered out by the
  library queries — backend; → `deferred.md`); `ChatMessages` "Open planning"
  and the "Planning conversation" region label are not in the copy table and
  were left.
- Gates: typecheck clean · lint 0 errors · `pnpm test` 75 files / 547 passed ·
  build OK · `pnpm e2e` 11 passed.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (Phase 0 baseline) | pass | backend 2442 passed; infra green after the `.dockerignore` fix; remaining root gates green |
| `make verify-fast` (Phase 1 gate) | pass | 2442 passed, mypy 299 files, ruff clean |
| `make frontend-verify` + `pnpm e2e` (Phase 1) | pass | 75 files / 532 tests; e2e 11 passed |
| `make verify-fast` (Phase 2 gate) | pass | 2508 passed (+66 tool tests), mypy 301 files, ruff clean |
| `make verify` (Phase 3 gate) | pass except `drift-check` | backend 2517 passed (8m16s), infra 46, audit-paths/prompt-guard/font-guard green; `drift-check` red by the plan's phase split (openapi-sync is Phase 4); ruff/mypy/147 touched tests re-run green after the screen-sense fixes |
| `make verify` (Phase 4 gate) | pass | okf 129/0 · backend 2520 (incl. Phase 6) · infra 46 · drift-check OK · frontend 75 files / 530 tests · build OK; worker `pnpm e2e` 11 passed |
| `make frontend-verify` + `pnpm e2e` (Phases 5a + 7 gate) | pass | 533 tests; e2e 11 passed after two spec labels caught up with V6 |
| `pnpm typecheck/lint/test/build/e2e` (Phase 5b, worker) | pass | 547 tests; e2e 11 passed |
| `pnpm typecheck/lint/test/build/e2e` (Phase 8 knip, worker) | pass | 545 tests; e2e 11 passed; knip 52→0 exports, 47→2 types (generated) |
| `make okf-validate` (Phase 9 docs) | pass | 129 concepts, 0 violations |
| `alembic upgrade head` on the dev DB (52 real Tasks) | pass | e7a1b5c3d9f2 → c1a7f4e9b0d2; counts under the new names match |
| Live Playwright check against `make dev` | pass | 4 passed — [live-check.md](live-check.md) |
| `make fe-api-smoke` | pass | 3 passed (built frontend, real API, own DB: list · create · stub run over SSE) |
| **`make verify` (step-6 exit, final tree: Agent-tab passes, Mine default, motion pass)** | **pass** | one uninterrupted run: okf 129/0 · backend **2520 passed** (7m50s) · infra 46 · audit-paths 116 files / 0 · prompt-guard 13 unchanged · font-guard · drift-check OK · frontend 74 files / **549 tests** · build OK. `pnpm e2e` 11 passed on this frontend, plus the live checks above. |

## Checks beyond the build

- **Migration on real local data (the local "deploy").** The dev database
  (`policy_atlas`, 52 Task rows from live runs, 1 Project, head `e7a1b5c3d9f2`)
  was backed up (`pg_dump`, 782 MB, kept outside the repo) and upgraded
  `alembic upgrade head`: `e7a1b5c3d9f2 → a8c3e1f5b9d2 → b2f6a9d4c1e7 →
  c1a7f4e9b0d2`, no lock timeout, no error. After: `task` 52 · `project` 1 ·
  `plan` 36 · `task_source_snapshot` 1,132 · `capability_run` with
  `evidence_search` 18 and `evidence_base` 0 · `pg_class` names matching
  `portfolio|pss|oplan|orchestration` 0 (I1, I2, V3).
- **Migration round trip on a seeded pre-migration database**
  (`tests/core/test_migration_038.py`, 2 tests): catalog equals the manifest at
  head; populated fixture (Task in a Project, `is_public`, run, `evidence_base`
  capability run, all four old `project.*` events, an `orchestrator` decision,
  plan payload and pause record with `evidence_base_coverage`) reads back
  identically under the new names, the old steer point validates through
  `TaskPlan`, downgrade restores the fixture byte-identically with each of the
  five stored values reversed independently, upgrade again succeeds.
- **Pre-038 stored-value compatibility**
  (`tests/api/test_pre_038_vocabulary_compatibility.py`, 7 tests): old value in
  → new value out through the real read paths (SSE check-in frame, decisions
  read model, `TaskPlan.model_validate`, `checkin_read`, both event-kind readers).
- **Trace sessions** (`tests/api/test_trace_sessions_038.py`, 3 tests): planning
  turn, chat turn, run start + steering continuation all emit `session_id ==
  str(task_id)`; planning and chat carry `conversation_id` (I9).
- **Sweep tool** (`tests/scripts/test_rename_038.py`, 66 tests): case forms,
  compound-before-bare, path literals vs prose, never-map contexts, collision
  refusal, step ordering, idempotence, fresh-clone guard.

## End-to-end command

Local live check (contract § Acceptance, pre-merge half), recorded in full with
the spec text and results in [live-check.md](live-check.md):

```bash
make dev                                                 # API :8000 + Vite :5173 (dev token), dev DB at c1a7f4e9b0d2
cd frontend && pnpm dev --port 5174 --strictPort         # token-less frontend for the signed-out leg
cd frontend && TASK_ID=fdfe3811-cea5-4d8e-91c3-e6435fdb3a56 PROJECT_ID=97a96376-92d9-48ae-a19e-78efb23e3f58 \
  npx playwright test --config live-038.config.ts        # 4 passed: five tabs · its Project · old URL unavailable · signed-out public URL
make fe-api-smoke                                        # real API, own DB, browser: list → create → stub run over SSE
```

The Chrome extension was not connected in this session, so the browser leg ran
as a Playwright spec against the same running app a hand-driven browser would
have used. One real Task (Childhood Obesity, run succeeded 2026-07-29) opened on
`/tasks/{id}` with the bar Agent · Result · Sources · Share · History (no Plan,
no Results), Result at `/result` with the report contents, Share with the
public-link region and "this Task's result and sources", History listing the
pre-migration events under the new copy; its Project on `/projects/{id}` lists
it; `/projects/{taskId}/results` lands on "This task is unavailable" (F3); a
signed-out visitor opens `/tasks/{id}/result` and sees Result · Sources only.
API: `GET /api/v1/tasks` (20 rows with `project_ids`), `GET /api/v1/projects`
(`task_count` 3), `/api/v1/portfolios` 404, signed-out `GET /api/v1/tasks/{id}`
200 once public, the old `/api/v1/projects/{taskId}` 401.

## Diff summary

One PR, eight review commits plus the docs commit (contract A15 isolation):
(g) Phase 1 V10 riders · Phase 2 sweep tool + scan tables · (b) Phase 3 schema
migration + backend sweep + compatibility readers + prompt word swaps · (c)
Phase 4 API paths, generated client, frontend sweep, copy table, spec bundle
move · (e) Phase 6 Langfuse session per Task · Phase 5a tabs and literals ·
(d) Phase 5b Task Agent · (f) Phase 7 post-sign-in landing · (h) Phase 8 repo
hygiene · Phase 9 living docs. **No product behaviour change** except the
enumerated deltas: routes/URLs (`/tasks/**`, `/projects/**`, `/result`, no
redirects — F3), labels (Agent · Result tabs; Report; Task Agent; the Agent
overlay copy), trace grouping (V9) and the post-sign-in landing (V11).

**Flagged deviations, resolved within the contract's vocabulary** (each also
in the phase log above): the `.dockerignore` counterpart of the V12 gitignore
entry · deterministic manifest sort · six manifest FK rows corrected to the
catalog's explicit names · `useCreateProject` deleted in Phase 4, not 8 ·
string-level (not whole-file) exemption of copy/prompt modules · component
prompt hashes changed by import lines only · `canonical_actor` applied at the
three real stored-actor projections (one the contract missed, two it named
that do not project a stored value) · sharing event kinds not added to the
decisions read model · the ops CLI flag collision (mid-sweep) · screen-sense
prose and identifiers restored after both sweeps · Phase 3's gate closes
without `drift-check` by the plan's own phase split · "Untitled project"
backfill name left as data (→ deferred).

## Review findings

## Rubric status

## Intent & assumptions

- The contract's I4 ("no `orchestrat` token remains") is read as *no live use
  of the retired word*: compatibility maps whose data is the retired value,
  tests that seed pre-038 rows, the migration itself, the sweep tool and its
  test, and the engineering-concept spec id `execution-orchestration.md` are
  accepted residue and listed where each occurs.
- Contract V3's "identical hash values" for the component prompt modules could
  not hold once their `import` lines moved packages; the words-only proof is
  [prompt-diff.md](prompt-diff.md), reviewed as such.
- Rebase path for open PRs (#62, #52 — owner F5): run the committed
  `scripts/rename_038.py --apply --phase {3,4} --step all` on the PR's own
  pre-038 branch before merging `dev`; the fresh-clone guard refuses a
  post-038 tree.

## Known unverified items

- The staging half of the live check (contract P11): one existing Task on
  `/tasks/{id}` with report, sources and history intact after the staging
  migration; its Project on `/projects/{id}`; one public Task from a freshly
  copied link; **one real Cognito sign-in round trip from a Task deep link
  (V11)**; `rows assign --task` dry run; `make fe-api-smoke` against staging.
  Recorded post-merge as a dated addendum before the production promote.
- "One staging Task shows as one Langfuse session" (rubric 19) — verifiable only
  on staging; the stub-client test proves the ids.
- Operators must rename any `POLICY_ATLAS_ORCHESTRATOR_*` override in the task
  definition before deploying (the stack sets neither); the PR says so.
- `knip` and `vulture` were run once, on this branch; neither is wired into
  `make verify` (out of scope — a hygiene pass would decide).

## Public safety

Everything in this slice is committable: identifier and copy renames, one
migration, tests with synthetic ids, the scan tables (identifier names and
counts only), the prompt diff (product prompt text is already public in this
AGPL repo). No traces, credentials, evidence text or account ids. The Langfuse
and Metabase follow-ups are named, not linked to any private dashboard.

## Review handoff (step-7/8 inputs)

- **Knowledge candidates:**
  - `schema_manifest.py` sort-key gotcha: sorting SQLAlchemy constraints by
    `con.name` is non-deterministic for auto-named FKs (`name is None`);
    resolve the PostgreSQL default name first.
  - **Metadata is not the catalog.** Six FKs that SQLAlchemy metadata leaves
    unnamed were created by earlier migrations under explicit names; a manifest
    generated from metadata alone lists names that never existed. Any rename
    migration must be checked against `pg_constraint`, and the manifest generator
    now carries the explicit-name map.
  - **A code-word sweep inverts screen-sense prose and identifiers.** Comments,
    docstrings and a few identifiers written after ADR 0031 already used the
    *screen* words ("a Task inside a Project", `ProjectPicker`,
    `showProjectPrefix`, `COPY.noProject`); a `project→task` sweep turns them into
    "a Task inside a Task". Detect by pairing removed/added lines and filtering
    for lines that also name the other entity; the frontend was protected by
    never-mapping exact `Task`/`Project`.
  - **Two-step rename idempotence needs a ledger or a sentinel.** When step 2
    produces step 1's source word (`portfolio→project` after `project→task`), no
    tokeniser can tell a swept tree from an unswept one; the tool keeps a
    per-checkout hash ledger and refuses a tree that already looks swept.
  - **Never-map patterns must be anchored.** `[project]` (pyproject table) matched
    a list literal `data=[project]`; `--project` (the uv flag) matched the ops CLI
    flag and caused a mid-sweep collision (`--portfolio` → `--project` landed on
    an unrenamed `--project`). Anchor to the line start / the `uv run` prefix.
  - **Historical migration tests cannot share one `Table` object across the
    rename boundary.** Below the renaming revision, address old names by
    reflection (`Table(..., autoload_with=conn)`) or textual SQL; at head use
    current metadata (`tests/core/legacy_catalog.py`).
  - **A phase split can make one gate structurally red.** Regenerating the
    OpenAPI client belongs with the frontend sweep, so the backend-only commit
    cannot be `drift-check` clean; the plan's gate map must say so up front.
  - **Prompt hash guard hashes the whole module**, so a package move changes
    component prompt hashes via their `import` lines even when no prompt text
    moved; the words-only proof is the diff, not the hash equality.
  - **Compatibility maps are legitimate I4 residue.** A "no retired word remains"
    invariant must exempt the readers whose data *is* the retired value.
  - **react-router data routers are pinned to `window.location` at import.**
    `history.replaceState` fires no `popstate`; a freshly mounted singleton
    router starts from its captured location. `router.state` is `@private` in
    the type (precedent exists in `routes.test.tsx`).
  - **The collision check counts prose occurrences.** A comment saying "the
    global projects page" blocks `projects→tasks` in a file that declares
    `tasks`; reword the comment first or teach the tool to skip comments.
  - **BSD `sed` has no `\b`.** Word-boundary edits on macOS need
    `[[:<:]]…[[:>:]]` or Python.
  - `docs/knowledge/run-component-driver-for-scoped-live-checks.md` describes
    `skeleton._run_component`, which no longer exists — retire or rewrite at
    step 8.

## Deferred work

→ [docs/deferred.md](../../deferred.md) § Vocabulary (task 038 residue and seams) and
the "Earlier plan is unreachable in production" entry; eight earlier entries
discharged or corrected in place (Phase 9 log above). Judgment-bearing hygiene
(production code only tests call, the `run_harness(provider=…)` seam, the
`useComposerSeed` listener whose dispatcher went) → a Tier 1 `/ponytail-audit`
pass after 038 (contract § Out of scope).
