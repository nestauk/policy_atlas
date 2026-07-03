# Implementation Plan: 006-appraise

> **Status:** drafted — pending plan-phase adversarial review + human confirmation.
> Contract: [contract.md](contract.md) (approved 2026-07-03 · Shabeer Rauf).

## Overview

Add the `appraise` component to the Policy Atlas v3 harness. Per-document evidence-hierarchy
score (1–5, 5 = strongest) over the classified set, persisting results in
`source_appraisal_result`. The component mirrors `classify` almost exactly — same composite-FK
schema pattern, same `Context`/`Result` dataclass pair, same harness node shape, same fan-out
loop. Two structural differences from classify:
- **No stub, no sentinels** — the v3.0 light pass *is* the deterministic
  `DEFAULT_RUBRIC[primary_evidence_type]` lookup; tests steer it through classify's existing
  sentinels upstream.
- **Skip path** — Non-evidence and Unknown types are outside the rubric's domain: no appraisal
  row, no per-row event, counted in `skipped_non_evidence` / `skipped_unknown`.

## Architecture decisions (all fixed in the approved contract)

- Appraise reads `source_classification_result` for the scope (classification is the
  "routing/appraisal key"); relevant-but-unclassified rows only counted (`unclassified`).
- `quality_score` SMALLINT 1–5, 5 = strongest — v2 hierarchy verbatim (SR=5, RCT=4, Obs=3,
  Modelling/Policy/Qual=2, Expert=1); `rubric_version = "v2-hierarchy-v1"` on every row.
- `SCORE_LABELS` derived presentation copy — never persisted, never in events.
- No FK to `source_classification_result` (documented rejection — contract schema note).
- Sparse `by_score`; string keys in the JSONB event payload; rerun-stable counting invariant.

## Dependency graph

```
schema.py (source_appraisal_result)
    │
    ├── alembic migration        (depends on schema.py)
    ├── appraise.py              (depends on schema.py)
    ├── plan.py                  (no new deps — one registry entry)
    ├── harness.py               (depends on appraise.py + plan.py)
    ├── tests/helpers.py         (depends on schema.py)
    ├── test_schema.py           (depends on schema.py)
    ├── test_compile.py          (depends on plan.py)
    ├── test_appraise.py         (depends on all of the above)
    ├── skeleton.py              (depends on harness.py + schema.py)
    └── components.md §4 + log.md  (spec flow-back — no code deps)
```

One deliberate simplification vs classify: `appraise_sources` joins
`source_classification_result` → `project_source_snapshot` only (for `source_snapshot_id`
and the project guard). No `source_snapshot` join — appraise never reads metadata.

---

## Phase 1 — Schema foundation

### Task 1: Add `source_appraisal_result` to schema and migrate

**Files:**
- `src/policy_atlas/schema.py` — add `source_appraisal_result` after the classification
  section; update module docstring "fourteen tables, four alembic migrations" → "fifteen
  tables, five alembic migrations"
- `alembic/versions/<hash>_appraise_table.py` — new migration; `upgrade` creates the table,
  `downgrade` drops it (mirror `b5d3e8f2a7c9_classify_table.py`)

**Acceptance criteria:**
- [ ] Table with all 8 columns; composite FKs `fk_sar_scope_project`, `fk_sar_pss_project`,
      `fk_sar_run_project`; `uq_sar_scope_source`; `ix_sar_scope_score`;
      `ck_sar_quality_score` (`quality_score BETWEEN 1 AND 5`)
- [ ] Migration roundtrip clean: `upgrade head` → `downgrade -1` → `upgrade head`
- [ ] `len(metadata.tables) == 15`

**Estimated scope:** S (2 files)

### Task 2: Update the two existing table-count assertions

- `tests/test_screen.py:28` and `tests/test_classify.py:58` — `assert len(metadata.tables)
  == 14` → `== 15`. (`test_schema.py` checks a table-name subset, not a count — nothing to
  change there.) Nothing else.

**Estimated scope:** XS (2 files, 2 lines)

### Checkpoint — Phase 1
- [ ] `make verify` green; migration roundtrips clean.

---

## Phase 2 — Module and wiring

### Task 3: Write `appraise.py`

**Files:** `src/policy_atlas/appraise.py` — new module: `DEFAULT_RUBRIC`,
`DEFAULT_RUBRIC_VERSION`, `SCORE_LABELS`, `AppraiseContext`, `AppraiseResult`,
`appraise_sources`. Google-style docstrings on the public surface (per contract — don't
mirror classify's gap).

**Shape of `appraise_sources`:**
1. Select `(project_source_snapshot_id, source_snapshot_id, primary_evidence_type)` from
   `source_classification_result` join `project_source_snapshot` (on pss_id + project_id),
   filtered to scope + project, excluding already-appraised via `~exists()` (mirror classify's
   idempotency pattern).
2. Per row: `primary_evidence_type in DEFAULT_RUBRIC` → insert appraisal row + emit
   `source.appraised`; else count into `skipped_non_evidence` / `skipped_unknown`.
   ⚠️ skips must be counted on **every** call (recomputed), so count them from the full
   classification-row set for the scope, not only from the not-yet-appraised remainder —
   otherwise a rerun under-reports skips. Simplest: derive skip counts with one aggregate
   query over `source_classification_result` for the scope, independent of the insert loop.
3. `already_appraised` = direct count of existing `source_appraisal_result` rows for the
   scope, taken **before** this call's inserts. (Not derivable from step 1's fetch — that
   fetch includes skip-domain rows, so "appraisable minus fetched" is wrong.)
4. `unclassified` = anti-join count: relevant `source_screening_result` rows for the scope
   with `~exists()` a matching `source_classification_result` row. (Not raw count
   subtraction — no FK guarantees classification rows are a subset of screening rows;
   see `docs/deferred.md`.)
5. Return `{"appraised", "by_score" (sparse, int keys), "skipped_non_evidence",
   "skipped_unknown", "already_appraised", "unclassified"}`.

**Acceptance criteria:**
- [ ] Rubric domain = `EVIDENCE_TYPES` minus the two non-appraisable types; values 1–5
- [ ] Skip path produces no row and no event; counts recomputed per call
- [ ] Counting invariant holds: `appraised + already_appraised + skipped_non_evidence +
      skipped_unknown` = classification rows for scope
- [ ] `source.appraised` payload exactly per contract (`quality_score` int,
      `rubric_version` string)

**Estimated scope:** S (~90 lines, mirrors classify.py minus the stub)

### Task 4: Register `"appraise"` and wire harness node

**Files:**
- `src/policy_atlas/plan.py` — add `"appraise": {"requires": ["screening_scope_id"]}`
- `src/policy_atlas/harness.py` — `_run_appraise` (mirror `_run_classify`): load scope row,
  build `AppraiseContext`, `component.started` → `appraise_sources` → `component.completed`
  with `{component, appraised, by_score, skipped_non_evidence, skipped_unknown,
  already_appraised, unclassified}`. Graph wiring is **three** additions (match the existing
  per-component pattern in `build_graph`): `g.add_node("appraise", _run_appraise)`,
  `"appraise": "appraise"` in the `add_conditional_edges` map, and
  `g.add_edge("appraise", "finish")`

**Estimated scope:** S (2 files, ~25 lines)

### Task 5: Update `test_compile.py` and `tests/helpers.py`

- `tests/test_compile.py` — `"appraise"` valid with scope id; `Plan(component="appraise")`
  without `screening_scope_id` raises `ValidationError` (mirror the classify pair at
  `test_compile.py:55-64`); unknown component still rejected
- `tests/helpers.py` — delete `source_appraisal_result` before `source_classification_result`
  in `delete_project_data`

**Estimated scope:** S (2 files, ~5 lines)

### Checkpoint — Phase 2
- [ ] `make verify` green; `Plan(component="appraise", screening_scope_id=…)` compiles;
      graph includes appraise node.

---

## Phase 3 — Test suite, demo, spec flow-back

### Task 6: Write `test_appraise.py`

**Files:** `tests/test_appraise.py` — new file; copy/adapt seed helpers from
`test_classify.py` (don't import across test modules). Classification rows are seeded via
`classify_sources` with classify's existing metadata sentinels (e.g. `_stub_systematic_review`
→ SR&MA → score 5) or direct inserts where a specific type mix is clearer.

**Test cases (from the contract, 18):**
1. Table count 15
2. Rubric domain = `EVIDENCE_TYPES` − {Non-evidence, Unknown}; values ⊆ 1..5
3. Rubric matches v2 exactly (SR=5, RCT=4, Obs=3, Modelling=2, Policy=2, Qual=2, Expert=1)
4. `SCORE_LABELS` domain = {1..5}
5. Round-trip: appraisal rows for classified evidence sources, score per rubric
6. Non-evidence: no row, `skipped_non_evidence` counts it
7. Unknown: no row, `skipped_unknown` counts it
8. Relevant-but-unclassified: not appraised, `unclassified` counts it
9. Idempotency: second call `appraised == 0`, `already_appraised == n`, no duplicates
10. Mixed rerun: skip counts identical across calls; invariant holds both calls
11. `by_score` sparse (no zero-valued keys)
12. `rubric_version == "v2-hierarchy-v1"` on every row
13. `appraised_by_run_id` set correctly
14. Check constraint: `quality_score` 0 and 6 → `IntegrityError`
15. Cross-project FK → `IntegrityError`
16. Unique duplicate `(scope, pss)` → `IntegrityError`
17. Harness round-trip: `Plan(component="appraise")` → rows + events; `component.completed`
    payload has **string-keyed** `by_score`; no `source.appraised` event for skipped rows
18. `source.appraised` per-row event payload: keys and values match the contract spec exactly
    (`source_snapshot_id`, `project_source_snapshot_id`, `screening_scope_id`,
    `quality_score` int, `rubric_version`)
19. `delete_project_data` removes appraisal rows; none remain

**Estimated scope:** M (~260 lines)

### Task 7: Update `skeleton.py`

Third run after screen and classify: `Plan(component="appraise", …)` with the same
`screening_scope_id`; query and log appraisal rows.

⚠️ The current seed metadata (`skeleton.py:55-62`) carries no classify sentinel, so the
source classifies as `Unknown` — which appraise *skips*, and the demo would show zero
appraisal rows. Add a sentinel to the seed metadata (e.g. `"_stub_systematic_review": True`
→ SR&MA → score 5) so the demo exercises the scored path end-to-end; the appraise log line
should also surface the skip counts so both paths are visible.

**Estimated scope:** S (~30 lines)

### Task 8: Spec flow-back (approved with the contract)

- `docs/specs/capabilities/evidence-base/components.md` §4 — one-line clarification: the
  v3.0 light pass scores classified **evidence** types; Non-evidence and Unknown are
  skipped-and-counted (Unknown re-enters via the deferred full-text resolution seam)
- `docs/specs/log.md` — one dated entry referencing task 006 (the repo-level spec update
  log; the evidence-base bundle has no per-bundle `log.md`)
- `make okf-validate` green after the edit (frontmatter untouched)

**Estimated scope:** XS (2 files, 2 lines)

### Checkpoint — Phase 3 (final)
- [ ] `make verify` fully green (incl. `test_appraise.py`)
- [ ] `python -m policy_atlas.skeleton` exits 0 showing screen → classify → appraise with
      at least one scored appraisal row
- [ ] Migration roundtrip clean

### Step-8 obligations (after the review stack, in the PR — not implement-phase tasks)

Named here so they can't be silently dropped: `docs/deferred.md` entries per the contract
(steerable rubric · uq relaxation for re-appraisal · typed dimensions · small-sample −1
penalty · appraisal→classification FK deliberately absent), plus any `docs/knowledge/`
learning. Authored against the review-finalised code, per the task cycle.

---

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| ~~Dev DB `make setup` fails~~ **RESOLVED 2026-07-03**: stale dev DB (stamped `c4f2a9b3` but holding an older draft of that migration's schema) dropped and recreated with human approval; all migrations apply clean; `skeleton.py` runs end-to-end | — | Root cause noted for the future: rewriting an already-applied migration file strands any DB that ran the old draft — avoid editing applied migrations |
| Rerun under-reports skips if counted only in the not-yet-appraised loop | Med | Contract pins recompute-per-call semantics; dedicated aggregate query + mixed-rerun test (case 10) |
| `by_score` int keys silently become strings in JSONB | Low | Contract pins string-keyed payload; harness test asserts it (case 17) |
| Seeding via classify sentinels couples test_appraise to classify's stub | Low | Acceptable — sentinels are stable test infra from 005; direct-insert fallback where clearer |

## Plan-phase adversarial review — findings & adjudication (Codex, 2026-07-03)

Nine findings, all verified against the repo before adjudication:
1. Table-count test targets wrong file (**blocker**): **adopted** — assertions live in
   `test_screen.py:28` + `test_classify.py:58`, not `test_schema.py`; Task 2 retargeted and
   the contract's test-update list corrected.
2. Spec log path doesn't exist: **adopted** — `docs/specs/log.md` (repo-level), Task 8 fixed.
3. Harness wiring incomplete: **adopted** — Task 4 now names `add_node` + conditional-edge
   map entry + `add_edge(..., "finish")`.
4. False `already_appraised` equivalence: **adopted** — direct pre-insert count only.
5. `unclassified` needs anti-join: **adopted** — `~exists()`, not count subtraction.
6. Missing `source.appraised` payload test: **adopted** — test case 18 added.
7. Skeleton would show zero appraisal rows (seed classifies Unknown → skipped): **adopted** —
   Task 7 adds a classify sentinel to the seed metadata.
8. deferred.md not a plan task: **partially adopted** — deliberate (step-8 authoring per the
   task cycle); now an explicit "Step-8 obligations" section instead of a checkpoint aside.
9. Missing-scope compile rejection test: **adopted** — Task 5 mirrors the classify pair.

## Open questions

None — all design decisions fixed in the approved contract; the dev-DB environment blocker
was resolved 2026-07-03 (recreated with human approval).
