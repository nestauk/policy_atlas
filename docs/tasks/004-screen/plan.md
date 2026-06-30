# Plan: 004-screen

Generated from [contract.md](contract.md). Implementation only begins after human approval of this plan.

## Dependency graph

```
schema.py
  ├── migration (requires schema updated first)
  ├── screen.py (imports new tables)
  │     └── harness.py (imports ScreenContext, screen_sources)
  ├── plan.py (independent of screen.py; must be done before harness.py)
  │     └── harness.py
  └── tests/helpers.py (imports new tables for delete_project_data)

All source changes → test_screen.py (new)
plan.py change → test_compile.py (update)
schema.py change → test_schema.py (update)
```

Vertical slicing: each step below delivers one complete, testable path. Steps 1–3 are the foundation; steps 4–6 add the runtime path; step 7 closes with tests and skeleton.

---

## Step 1 — Schema (`src/policy_atlas/schema.py`)

**Must be done first** — everything else imports from here.

**Changes:**
- Add `Index` to the SQLAlchemy imports.
- Add `UniqueConstraint("project_source_snapshot_id", "project_id", name="uq_pss_id_project")` to the existing `project_source_snapshot` table definition. This is the composite FK target for `source_screening_result`.
- Append `screening_scope` table:
  ```
  screening_scope_id  UUID  PK
  project_id          UUID  NOT NULL  FK → project
  intent              TEXT  NOT NULL
  context             JSONB NOT NULL  (default handled at insert; no server default needed)
  created_at          TIMESTAMPTZ NOT NULL
  UniqueConstraint("screening_scope_id", "project_id", name="uq_screening_scope_id_project")
  ```
- Append `source_screening_result` table with all columns, three `ForeignKeyConstraint`s (scope+project_id, pss+project_id, run+project_id), five check constraints, unique constraint on `(screening_scope_id, project_source_snapshot_id)`, and `Index("ix_ssr_scope_status", ...)`.

**Acceptance:** `from policy_atlas.schema import metadata; len(metadata.tables) == 13`

---

## Step 2 — Alembic migration

**Depends on Step 1.** New file in `alembic/versions/` following naming convention `{8-char-hex}_{slug}.py`. Revision ID is a new 12-char hex; `down_revision` = `c4f2a9b3e8d1`.

**`upgrade()` — three operations in FK-safe order:**
1. `op.create_unique_constraint('uq_pss_id_project', 'project_source_snapshot', ['project_source_snapshot_id', 'project_id'])` — ALTER TABLE on existing table.
2. `op.create_table('screening_scope', ...)` — all columns, FK to project, unique constraint on `(screening_scope_id, project_id)`.
3. `op.create_table('source_screening_result', ...)` — all columns, three composite FKs, five check constraints, unique on `(screening_scope_id, project_source_snapshot_id)`.
4. `op.create_index('ix_ssr_scope_status', 'source_screening_result', ['screening_scope_id', 'status'])`.

**`downgrade()` — reverse order:**
1. `op.drop_index('ix_ssr_scope_status', ...)`
2. `op.drop_table('source_screening_result')`
3. `op.drop_table('screening_scope')`
4. `op.drop_constraint('uq_pss_id_project', 'project_source_snapshot', type_='unique')`

**Acceptance:** `alembic downgrade -1` then `alembic upgrade head` both succeed; no error on re-run.

---

## Step 3 — `tests/helpers.py` — extend `delete_project_data`

**Depends on Step 1** (needs to import new tables). Independent of Steps 4–6.

**New imports:** `screening_scope`, `source_screening_result` from `policy_atlas.schema`.

**Updated FK-safe deletion order** (full sequence; new rows in **bold**):
1. `citation` (before annotation)
2. **`source_screening_result`** (before `project_source_snapshot`, `runs`, and `screening_scope`)
3. `annotation`
4. `addressable_unit`
5. `event_log`
6. `block`
7. `artefact`
8. `runs`
9. `project_source_snapshot`
10. `chunk`
11. `source_snapshot`
12. **`screening_scope`** (before `project`)
13. `project`

`source_screening_result` goes before step 8 (`runs`) because it has a composite FK to `runs(run_id, project_id)`. It goes before step 9 (`project_source_snapshot`) for the same reason. It goes before step 12 (`screening_scope`) for the same reason.

**Acceptance:** existing commit-survival tests (`test_harness.py`) still pass; no FK violation on cleanup.

---

## Step 4 — `plan.py` — component-scope registry

**Depends on Step 1** (no new schema imports, but logically follows schema). Must complete **before Step 5**.

**Changes:**
- Add `COMPONENT_REGISTRY: dict[str, dict[str, list[str]]] = {"echo": {"requires": ["source_snapshot_id"]}, "screen": {"requires": ["screening_scope_id"]}}`.
- Replace `VALID_COMPONENTS = {"echo"}` with `VALID_COMPONENTS = set(COMPONENT_REGISTRY.keys())`.
- Add `screening_scope_id: uuid.UUID | None = None` to both `Plan` and `Config`.
- Replace the echo-specific `if self.component not in VALID_COMPONENTS` validator with a two-part validator:
  1. Unknown component → `ValueError` (unchanged).
  2. For each field in `COMPONENT_REGISTRY[component]["requires"]`: if `getattr(self, field) is None` → `ValueError(f"{field} is required for component {component!r}")`.

**Acceptance:** `Plan(component="echo", source_snapshot_id=uuid4())` still valid; `Plan(component="screen", screening_scope_id=uuid4())` valid; `Plan(component="screen")` raises `ValueError`; unknown component raises `ValueError`.

---

## Step 5 — `screen.py` (new module `src/policy_atlas/screen.py`)

**Depends on Steps 1 and 2** (imports tables; migration must have run for tests to pass).

**`ScreenContext` dataclass:**
```python
scope_id: uuid.UUID
intent: str
context: dict
```

**`ScreenResult` dataclass:**
```python
status: Literal["relevant", "not_relevant", "failed"]
basis: str | None              # None iff status == "failed"
decision_confidence: float | None  # None iff status == "failed"
```

**`_stub_screen(metadata: dict) -> ScreenResult`:**
- `metadata.get("_stub_failed")` → `ScreenResult("failed", None, None)`
- else derive `basis`: `"title_abstract"` if `metadata.get("abstract", "").strip()` else `"title_only"`
- `metadata.get("_stub_not_relevant")` → `ScreenResult("not_relevant", basis, 0.95)`
- else → `ScreenResult("relevant", basis, 0.9 if basis == "title_abstract" else 0.7)`

**`screen_sources(conn, *, project_id, run_id, context: ScreenContext) -> dict`:**
1. `SELECT * FROM project_source_snapshot WHERE project_id = project_id` — load all membership rows.
2. For each row: load `source_snapshot.metadata`; call `_stub_screen(metadata)`.
3. `INSERT INTO source_screening_result(...)` — all fields including `project_id` (denormalized), `screened_by_run_id=run_id`, and the result fields.
4. Emit `source.screened` event (via `events.append`) with payload:
   ```json
   {
     "source_snapshot_id": "<uuid>",
     "project_source_snapshot_id": "<uuid>",
     "screening_scope_id": "<context.scope_id>",
     "status": "...",
     "screen_basis": "..." | null,
     "screen_decision_confidence": 0.9 | null
   }
   ```
5. Accumulate counters; return `{"screened": n, "relevant": r, "not_relevant": nr, "failed": f, "title_abstract": ta, "title_only": to}`.

**Note on event field names:** event payload uses `screen_basis` / `screen_decision_confidence` (DB column names), not the `ScreenResult` field names (`basis` / `decision_confidence`). Keep them distinct.

**Acceptance:** unit-testable without DB (stub logic only); full round-trip tested in Step 7.

---

## Step 6 — `harness.py` — `_run_screen` node

**Depends on Steps 4 and 5.**

**New imports:** `ScreenContext`, `screen_sources` from `policy_atlas.screen`; `screening_scope` from `policy_atlas.schema`.

**`_run_screen(state: HarnessState) -> HarnessState`:**
1. Load `screening_scope` row from DB: `SELECT * FROM screening_scope WHERE screening_scope_id = config.screening_scope_id`. If not found, set `state["error"]` and return early (same pattern as `GroundingError` in `_run_echo`).
2. Build `context = ScreenContext(scope_id=row.screening_scope_id, intent=row.intent, context=dict(row.context))`.
3. Emit `component.started(component="screen")`.
4. Call `counts = screen_sources(conn, project_id=project_id, run_id=run_id, context=context)`.
5. Emit `component.completed` with payload `{component: "screen", **counts}` — seven keys total.
6. Return updated state (no `block_ids` for this component; screen writes to its own table).

**`build_graph()` changes:**
- Add `g.add_node("screen", _run_screen)`.
- Extend conditional edge map: `{"echo": "echo", "screen": "screen"}`.
- Add `g.add_edge("screen", "finish")`.

**Acceptance:** harness dispatches to `_run_screen` for `component="screen"`; `component.completed` payload has all seven keys.

---

## Step 7 — Tests and skeleton

**Depends on all preceding steps.**

### `tests/test_screen.py` (new)

Tests are grouped below; each group is independent (uses the `conn` fixture which rolls back):

**Schema / structure (no screen_sources call):**
- `test_screen_table_count` — `len(metadata.tables) == 13`
- `test_pss_has_composite_unique` — `uq_pss_id_project` in inspector constraints for `project_source_snapshot`
- `test_screening_scope_columns` — `context`, `intent`, `project_id` all present
- `test_ssr_columns` — all expected columns present including `screened_by_run_id` and `project_id`

**Stub logic (pure Python, no DB):**
- `test_stub_relevant_with_abstract` — basis=`title_abstract`, confidence=0.9, status=`relevant`
- `test_stub_relevant_without_abstract` — basis=`title_only`, confidence=0.7, status=`relevant` (fail-open)
- `test_stub_not_relevant` — sentinel → status=`not_relevant`, basis set, confidence=0.95
- `test_stub_failed` — sentinel → status=`failed`, basis=None, confidence=None

**Check constraints (each inserts a bad row via raw SQL; expects `IntegrityError`):**
- `test_ck_bad_status`
- `test_ck_bad_basis`
- `test_ck_confidence_out_of_range`
- `test_ck_failed_with_non_null_basis`
- `test_ck_relevant_with_null_confidence`

**Round-trip (uses DB via `conn`):**
- `test_screen_sources_relevant_with_abstract` — single source with abstract; result row has status=`relevant`, basis=`title_abstract`, `screened_by_run_id` set
- `test_screen_sources_fail_open` — single source with no abstract; status=`relevant`, basis=`title_only`
- `test_screen_sources_not_relevant` — sentinel in metadata; status=`not_relevant`
- `test_screen_sources_failed` — sentinel; status=`failed`, both nullable columns null
- `test_screen_sources_mixed_counts` — 3 sources with different sentinels; verify all six count keys
- `test_screen_context_from_jsonb` — `screening_scope.context = {"theme": "housing"}`; verify `ScreenContext.context == {"theme": "housing"}`
- `test_source_screened_event_payload` — verify all six event payload keys and values after `screen_sources`
- `test_unique_constraint_scope_source` — inserting the same `(scope, source)` pair twice → `IntegrityError`
- `test_cross_project_fk_rejected` — create two projects; try inserting a result row with scope from project A and source from project B → `IntegrityError`

**Harness integration:**
- `test_harness_screen_component` — `Plan(component="screen", screening_scope_id=...)` → harness runs to `succeeded`; result rows in DB; `component.completed` payload has all seven keys

**Pattern for constraint tests:** use `conn.execute(sa.text("INSERT INTO source_screening_result ..."))` directly; wrap in `pytest.raises(sqlalchemy.exc.IntegrityError)`; then `conn.rollback()` and `conn.begin()` to restore the transaction (same pattern used in `test_schema.py`).

### `tests/test_compile.py` (update)

- Update `test_plan_compile_valid` — pass `source_snapshot_id` explicitly (still required for echo).
- Update `test_invalid_component_rejected` — still valid; no logic change needed if it tests unknown component.
- Add `test_screen_requires_screening_scope_id` — `Plan(component="screen")` raises `ValueError`.
- Add `test_screen_valid_with_scope_id` — `Plan(component="screen", screening_scope_id=uuid4())` compiles cleanly.
- Add `test_echo_requires_source_snapshot_id` — `Plan(component="echo")` raises `ValueError`.
- Remove or update any test asserting `VALID_SOURCES` (already removed in task 003) if any remnant exists.

### `tests/test_schema.py` (update)

- Change table-count assertion from 11 to 13.

### `src/policy_atlas/skeleton.py` (update)

Replace the existing echo demo with a screen demo:
1. Create project (unchanged).
2. Ingest upload (unchanged — seeding the corpus).
3. Create `screening_scope` row: `INSERT INTO screening_scope(scope_id, project_id, intent, context, created_at)`.
4. Create run (unchanged).
5. Emit `run.started`, `plan.compiled` (unchanged pattern; payload updated to carry `screening_scope_id`).
6. `Plan(component="screen", screening_scope_id=scope_id)` → `compile(plan)` → `run_harness(...)`.
7. Print result: result rows from `source_screening_result` instead of `block_ids`.

`StubEchoProvider` import can be removed if echo is no longer invoked; keep if it's still needed elsewhere (check before deleting).

---

## Checkpoints

| After step | Verify before continuing |
|---|---|
| 1 (schema) | `python -c "from policy_atlas.schema import metadata; assert len(metadata.tables) == 13"` |
| 2 (migration) | `make verify` green (migration applied, all existing tests pass) |
| 3 (helpers) | existing commit-survival tests in test_harness.py still pass |
| 4 (plan.py) | `Plan(component="screen", screening_scope_id=uuid4())` does not raise; `Plan(component="echo")` raises |
| 5 (screen.py) | stub unit tests pass without DB |
| 6 (harness.py) | `make typecheck` clean |
| 7 (tests + skeleton) | `make verify` fully green |

---

## Files changed

| File | Change type |
|---|---|
| `src/policy_atlas/schema.py` | Edit — add UniqueConstraint to pss; add 2 new tables |
| `alembic/versions/{rev}_screen_tables.py` | New — migration |
| `tests/helpers.py` | Edit — extend delete_project_data |
| `src/policy_atlas/plan.py` | Edit — component-scope registry |
| `src/policy_atlas/screen.py` | New — ScreenContext, ScreenResult, _stub_screen, screen_sources |
| `src/policy_atlas/harness.py` | Edit — _run_screen node + graph wiring |
| `src/policy_atlas/skeleton.py` | Edit — demonstrate screen component |
| `tests/test_screen.py` | New — ~20 tests |
| `tests/test_compile.py` | Edit — 3 new tests, 1–2 updated |
| `tests/test_schema.py` | Edit — table count 11 → 13 |
