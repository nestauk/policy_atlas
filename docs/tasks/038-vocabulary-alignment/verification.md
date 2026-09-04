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

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (Phase 0 baseline) | pass | backend 2442 passed; infra green after the `.dockerignore` fix |

## Checks beyond the build

## End-to-end command

## Diff summary

## Review findings

## Rubric status

## Intent & assumptions

## Known unverified items

## Public safety

## Review handoff (step-7/8 inputs)

- **Knowledge candidates:**
  - `schema_manifest.py` sort-key gotcha: sorting SQLAlchemy constraints by
    `con.name` is non-deterministic for auto-named FKs (`name is None`);
    resolve the PostgreSQL default name first.

## Deferred work
