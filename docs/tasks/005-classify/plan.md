# Implementation Plan: 005-classify

## Overview

Add the `classify` component to the Policy Atlas v3 harness. Per-document evidence-type
classification on the screened-in set, persisting results in `source_classification_result`.
The component mirrors `screen` almost exactly — same composite-FK schema pattern, same
`Context`/`Result` dataclass pair, same harness node shape, same fan-out loop. The primary
new element is the closed `primary_evidence_type` enum (9 v2-parity values) and the
`open_tags` JSONB column with an array-type check constraint.

## Architecture decisions

- **Scope-scoped results** — `source_classification_result` is keyed on
  `(screening_scope_id, project_source_snapshot_id)`, not just the snapshot. Same as
  `source_screening_result`. Classify reads only `status='relevant'` rows for the scope.
- **`ClassifyContext` through the interface** — `classify_sources` takes a `ClassifyContext`
  (not a bare `scope_id`), consistent with `screen_sources(context: ScreenContext)`. The
  harness node constructs it from the loaded `screening_scope` row.
- **Default stub result is `Unknown / Insufficient information`** — safe inclusive default;
  `_stub_classify` checks sentinels in order, falls through to Unknown.
- **`open_tags = []` in stub** — column exists for the LLM classify tool; stub never
  populates it.

## Dependency graph

```
schema.py (source_classification_result)
    │
    ├── alembic migration (depends on schema.py)
    ├── classify.py          (depends on schema.py)
    ├── plan.py              (no new deps — adds one registry entry)
    ├── harness.py           (depends on classify.py + plan.py)
    ├── tests/helpers.py     (depends on schema.py)
    ├── test_schema.py       (depends on schema.py)
    ├── test_compile.py      (depends on plan.py)
    ├── test_classify.py     (depends on all of the above)
    └── skeleton.py          (depends on harness.py + schema.py)
```

---

## Phase 1 — Schema foundation

### Task 1: Add `source_classification_result` to schema and migrate

**Description:** Add the new table to `schema.py` and generate the Alembic migration.
This is the foundation everything else imports from. Get it right before writing any
application code.

**Files:**
- `src/policy_atlas/schema.py` — add `source_classification_result` table (after the
  `# --- Screening model (task 004) ---` section block)
- `alembic/versions/<hash>_classify_table.py` — new migration; `upgrade` creates the
  table; `downgrade` drops it

**Acceptance criteria:**
- [ ] `source_classification_result` table defined with all columns, three composite FKs
      (`fk_scr_scope_project`, `fk_scr_pss_project`, `fk_scr_run_project`), unique
      (`uq_scr_scope_source`), index (`ix_scr_scope_type`), and two check constraints
      (`ck_scr_open_tags_array`, `ck_scr_primary_evidence_type`)
- [ ] Migration `upgrade` / `downgrade` roundtrip clean: `alembic upgrade head` then
      `alembic downgrade -1` then `alembic upgrade head` — no errors
- [ ] `len(metadata.tables) == 14`
- [ ] Docstring on `schema.py` updated: "thirteen tables" → "fourteen tables, four
      alembic migrations"

**Verification:** `make verify` — `test_schema.py` table-count assertion updated to 14.

**Estimated scope:** S (2 files)

---

### Task 2: Update `test_schema.py` table count

**Description:** Bump the table-count assertion from 13 to 14 so the existing test
reflects the new schema. This is the only change to `test_schema.py`.

**Files:**
- `tests/test_schema.py` — change `assert len(metadata.tables) == 13` to `== 14`

**Acceptance criteria:**
- [ ] `test_schema.py` passes with the Task 1 schema in place
- [ ] No other changes to `test_schema.py`

**Verification:** `pytest tests/test_schema.py` green.

**Estimated scope:** XS (1 file, 1 line)

### Checkpoint — Phase 1

- [ ] `make verify` green (schema tests pass, migration roundtrips clean)
- [ ] `len(metadata.tables) == 14` confirmed in test output

---

## Phase 2 — Module and wiring

### Task 3: Write `classify.py`

**Description:** New module with `ClassifyContext`, `ClassifyResult`, `_stub_classify`,
and `classify_sources`. Mirror `screen.py` structure exactly — same imports, same
docstring style, same fan-out loop shape. Key differences: reads from
`source_screening_result WHERE status='relevant'`, inserts into
`source_classification_result`, emits `source.classified` events.

**Files:**
- `src/policy_atlas/classify.py` — new file

**Acceptance criteria:**
- [ ] `_stub_classify` returns `ClassifyResult("Unknown / Insufficient information", [])`
      by default
- [ ] All 8 sentinel paths covered (`_stub_non_evidence`, `_stub_systematic_review`,
      `_stub_rct`, `_stub_observational`, `_stub_modelling`, `_stub_policy_guidance`,
      `_stub_qualitative`, `_stub_expert_opinion`)
- [ ] `classify_sources` queries `source_screening_result` filtered to `status='relevant'`
      AND `screening_scope_id=context.scope_id`, joins `project_source_snapshot` →
      `source_snapshot` to get `source_snapshot.c.metadata`
- [ ] Returns `{"classified": n, "by_type": {…}, "skipped": m}` where
      `classified + skipped == total screening result rows for the scope`
- [ ] `source.classified` event payload matches contract exactly (full canonical type
      string, not abbreviated)

**Verification:** Import succeeds; unit test stubs (Task 5) all pass.

**Estimated scope:** S (1 new file, ~80 lines, mirrors screen.py)

---

### Task 4: Register `"classify"` and wire harness node

**Description:** Two small changes to existing files. `plan.py` gains one registry entry.
`harness.py` gains `_run_classify` (mirroring `_run_screen`) and the conditional edge.

**Files:**
- `src/policy_atlas/plan.py` — add `"classify": {"requires": ["screening_scope_id"]}` to
  `COMPONENT_REGISTRY`
- `src/policy_atlas/harness.py` — import `ClassifyContext`, `classify_sources`; add
  `_run_classify` node; add `"classify"` to `add_conditional_edges` map and `add_edge`
  chain

**Acceptance criteria:**
- [ ] `Plan(component="classify", screening_scope_id=<uuid>)` compiles without error
- [ ] `Plan(component="classify")` (no scope_id) raises `ValidationError`
- [ ] `build_graph()` includes `"classify"` node
- [ ] `_run_classify` emits `component.started`, calls `classify_sources`, emits
      `component.completed` with `{component, classified, by_type, skipped}`

**Verification:** `pytest tests/test_compile.py` green after adding `"classify"` to valid
components test; `test_harness.py` unchanged (existing harness tests still pass).

**Estimated scope:** S (2 files, ~25 lines total)

---

### Task 5: Update `test_compile.py` and `tests/helpers.py`

**Description:** Two existing-file updates. `test_compile.py` needs `"classify"` added as
a valid component. `tests/helpers.py` needs `source_classification_result` inserted before
`source_screening_result` in `delete_project_data`.

**Files:**
- `tests/test_compile.py` — add `"classify"` to the valid-component parametrize list (or
  equivalent assertion)
- `tests/helpers.py` — import `source_classification_result`; add
  `conn.execute(delete(source_classification_result).where(...project_id...))` before the
  `source_screening_result` delete

**Acceptance criteria:**
- [ ] `"classify"` is a valid component in the compile tests
- [ ] `delete_project_data` removes `source_classification_result` before
      `source_screening_result` (FK-safe)
- [ ] All existing `test_compile.py` tests still pass

**Verification:** `pytest tests/test_compile.py` green.

**Estimated scope:** S (2 files, ~5 lines total)

### Checkpoint — Phase 2

- [ ] `make verify` green
- [ ] `Plan(component="classify", screening_scope_id=...)` compiles
- [ ] Harness graph includes classify node

---

## Phase 3 — Test suite and demo

### Task 6: Write `test_classify.py`

**Description:** Full test file covering all rubric items. Follows `test_screen.py`
structure. Needs a `_seed_screening_result` helper (in addition to the `_seed_source` and
`_seed_scope` helpers already in `test_screen.py` — copy and adapt, don't import from
test_screen).

**Files:**
- `tests/test_classify.py` — new file

**Test cases (15 total):**
1. Table count is 14
2. `_stub_classify` default → `Unknown / Insufficient information`, `[]`
3. `_stub_classify` `_stub_non_evidence` → `Other (Non-evidence documents)`
4. `_stub_classify` `_stub_policy_guidance` → `Policy Syntheses & Guidance Documents`
5. `_stub_classify` `_stub_rct` → `RCTs and Quasi-Experimental Studies`
6. `classify_sources` round-trip: result rows present for relevant sources only
7. `classify_sources` skips `not_relevant` rows
8. `classify_sources` skips `failed` rows
9. `classified + skipped == total` count invariant
10. `classified_by_run_id` is set correctly on result rows
11. Cross-project FK: scope from project A, source from project B → `IntegrityError`
12. Check constraint: bad `primary_evidence_type` → `IntegrityError`
13. Check constraint: `open_tags = {}` (object, not array) → `IntegrityError`
14. Unique constraint: duplicate `(screening_scope_id, project_source_snapshot_id)` → `IntegrityError`
15. Harness round-trip: `Plan(component="classify")` → rows in DB, events in order
16. `source.classified` event payload matches contract spec exactly
17. `delete_project_data` removes `source_classification_result`; no rows remain

**Verification:** `pytest tests/test_classify.py -v` — all 17 cases green.

**Estimated scope:** M (1 new file, ~220 lines)

---

### Task 7: Update `skeleton.py`

**Description:** Extend the demo script to run `classify` after `screen`, then print
classification results. Adds a second harness invocation with a fresh run row.

**Files:**
- `src/policy_atlas/skeleton.py`

**Acceptance criteria:**
- [ ] After the screen run, a second run is created and `Plan(component="classify", …)` is
      compiled and executed
- [ ] `source_classification_result` rows are queried and logged
- [ ] `python -m policy_atlas.skeleton` exits 0 with classification results visible in output

**Verification:** `python -m policy_atlas.skeleton` — no errors, classify results printed.

**Estimated scope:** S (1 file, ~25 new lines)

### Checkpoint — Phase 3 (final)

- [ ] `make verify` fully green (all test suites including `test_classify.py`)
- [ ] `python -m policy_atlas.skeleton` exits 0 showing classify results
- [ ] Migration roundtrip clean: `alembic downgrade -1` / `alembic upgrade head`
- [ ] All 15 rubric boxes checkable

---

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| `jsonb_typeof` check constraint syntax varies across Postgres versions | Med | Use the same syntax as the existing JSONB constraints in schema.py; test against the project's pinned Postgres version |
| `classify_sources` joins `source_screening_result` — if no screen has been run for the scope, returns 0 rows silently | Low | Correct behaviour (no relevant sources = nothing to classify); document in docstring |
| Harness `component.completed` payload with nested `by_type` dict — `**counts` spread doesn't flatten nested keys | Low | `payload={"component": ..., **counts}` is correct; `by_type` stays nested in the payload dict as-is |

## Open questions

None — enum values confirmed, schema pattern settled, interface aligned with screen.
