# Implementation plan: 031-search-count-honesty

> **Status:** draft for plan gate — **do not build until the contract is
> approved**. Executor marks below. Language aims for short, clear sentences
> (ASD-STE100 style).

## Context

Deep search runs up to three acquire+screen rounds. Several UI numbers use
different grains (one round vs all rounds; query hits vs unique sources;
present country vs missing country). One hard bug always shows zero backend
counts on the P1 check-in because a field is never written.

Funnel and plan-in-motion already use coherent counts. This plan fixes the
broken and mixed-grain surfaces only.

## Decisions (locked in the contract)

| # | Decision | Choice |
|---|---|---|
| D1 | P1 backend counts | Compute at read time from PSS / events for the **current** acquire run. Do not depend on `backends[].count` in old rows. |
| D2 | P1 queries | Same acquire run only (use `successful_runs["acquire"]`). |
| D3 | Where I looked `results` | Sum query `result_count` across **all** acquire runs for the project. |
| D4 | Where I looked `relevant` | Keep unique project-wide per backend (027 wart stays; grain now matches cumulative `results` better). |
| D5 | Geography gap | Residual **"Not reported"**; publisher country only; no authorship substitute. |
| D6 | Funnel / plan-in-motion | No code change. |
| D7 | OpenAPI field names | Unchanged. |

## Phases

### Phase 0 — Baseline

**Executor:** `lead` inline (one-command verify).

- Branch is on `37-hotfix-remove-quota` (or `dev` after merge).
- Run `make verify-fast` (or full `make verify` if the tree is cold).
- Confirm multi-round tests exist (`tests/runtime/test_search_rounds.py`).

**Gate:** green baseline.

### Phase 1 — P1 check-in counts

**Executor:** `codex` (judgment-bearing; machine-checkable done).  
**Brief design:** `lead` (seam: pass acquire `run_id` into `p1_bundle`).

1. Change `_build_bundle` so `SEARCH_EXCEPTION` / P1 passes
   `successful_runs.get("acquire")` into `p1_bundle`.
2. Rewrite `p1_bundle` to:
   - require that acquire `run_id`;
   - count **new** sources for that run per backend (same population as
     headline `acquired`);
   - list `search.executed` queries for that `run_id` only;
   - keep sample titles behaviour as today (multi-question title scope stays
     deferred).
3. Optional: when acquire writes the coverage row, also set `count` for new
   rows. Read path must still compute without it.
4. Tests: acquire+P1 with non-zero acquired → backend counts sum to acquired;
   two-round fixture → second P1 shows only second-round queries and counts.

**Done when:** invariant contract §1–2 hold in tests.

**Gate:** `make verify-fast`.

### Phase 2 — Where I looked grain

**Executor:** `codex`.

1. Change `_backend_details` (or its caller) so query events are collected for
   **all** acquire run ids that own a `search_coverage_record` for the
   project (not only `row["acquired_by_run_id"]` of the latest row).
2. Keep `relevant` attribution as today.
3. Frontend copy in `JourneyPane` / presentation: make the line honest.
   Prefer plain words, e.g. results = query hits (all rounds); relevant =
   kept after screening. Do not claim relevant ≤ results.
4. Tests: two-or-three-round fixture where last-round hits < cumulative
   relevant; after fix, `results` ≥ last-round-only figure and equals the
   all-rounds query-hit sum.

**Done when:** contract invariant 3 holds.

**Gate:** `make verify-fast` (shared with phase 3 if both stay local).

### Phase 3 — Geography residual

**Executor:** `codex`.

1. In `landscape_out`, when a relevant source has no `_geography`, increment
   a residual key (stable string, e.g. `Not reported`).
2. Ensure `normaliseGeographies` does not rename or drop that key.
3. Journey + Landscape headings: one short clarifying line if needed —
   "Publisher country when the database reports it."
4. Tests: mix of Overton-with-country, OpenAlex-without-country; sum of
   geographies map = relevant count.

**Done when:** contract invariant 4 holds.

**Gate:** `make verify-fast`.

### Phase 4 — Docs + deferred + verification

**Executor:** `fast-worker` for deferred.md rewrite; `lead` for verification.md
and AGENTS.md phase pointer close-out at review time.

1. Edit `docs/deferred.md`: discharge last-round-only Where I looked / P1
   query scope for the surfaces this slice fixed; leave timeline round
   labels and P1 sample-title scope as open.
2. Note in web-api or a one-line components caveat only if the living spec
   still claims last-round coverage detail — flow back if wrong
   (`docs/specs/README`).
3. Write `verification.md` with commands, test names, manual deep/standard
   checklist.

**Done when:** rubric items 7, 9–14 can be checked with evidence.

**Gate:** full `make verify` (step-6 exit class).

## Executor summary

| Phase | Executor | Why |
|---|---|---|
| 0 | lead inline | Baseline verify |
| 1 design (run_id seam) | lead | Seam signature / meaning |
| 1–3 implementation | codex | Default doer; tests define done |
| 4 deferred sweep | fast-worker | Mechanical doc edit against contract list |
| 4 verification.md | lead | Taste-bearing evidence narrative |

## Out of plan (do not do)

- Authorship → publisher country.
- Per-query relevance.
- Timeline "round 2 of 3" labels.
- Funnel or screen summary refactors.
- OpenAPI renames (`results` → `query_hits`, etc.) — defer unless the
  contract gate reopens.

## Risks

| Risk | Mitigation |
|---|---|
| Hotfix not merged; `dev` lacks multi-round | Stack on hotfix; state that in the PR. |
| `successful_runs["acquire"]` missing at P1 | Fail-soft empty bundle + test; P1 only fires after acquire. |
| "Not reported" dominates the chart | Expected; copy says databases often omit venue country. |
| Query-hit `results` still > unique sources | Honest; copy says hits can overlap. |

## Live check (contract pin)

Focused: one multi-round run (standard or deep) on the four surfaces. Not a
full EB e2e wall-clock. Rapid optional for the P1 zero fix only.
