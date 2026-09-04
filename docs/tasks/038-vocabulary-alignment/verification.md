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
