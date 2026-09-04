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
