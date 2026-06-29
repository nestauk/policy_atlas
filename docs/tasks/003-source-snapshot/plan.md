# Plan: 003-source-snapshot

## Dependency graph

```
schema.py (4 new tables)
    │
    ▼
Alembic migration
    │
    ├──► ingest.py (new) ──► test_ingest.py (new)
    │
    └──► grounding.py (seam flip) ──► test_grounding.py (updated)
              │
              ▼
         plan.py / Config (source_ref → source_snapshot_id)
              │
              ▼
         harness.py + skeleton.py (updated callers)
              │
              ▼
         test_compile.py + test_harness.py (updated)
              │
         test_schema.py (updated: 7→11 tables + 3 new constraint tests)
         helpers.py (delete_project_data extended for new tables)
         docs/deferred.md (4 new seams recorded)
```

Ordering constraint: schema.py + migration must land before any runtime or test code can be
written. ingest.py before test_ingest.py. grounding.py seam flip before harness.py update.

---

## Steps

### Step 1 — Extend schema.py with 4 new tables

**Files:** `src/policy_atlas/schema.py`

Add four SQLAlchemy Core `Table` definitions to the existing `metadata`, in FK-safe order:
`source_snapshot` → `project_source_snapshot` + `chunk` (parallel) → `citation`.

**`source_snapshot`**
- `source_snapshot_id` UUID PK
- `content_hash` Text not-null
- `text_basis` Text not-null (`full_text` | `abstract_only`)
- `source_locator` Text not-null
- `metadata` JSONB not-null
- `created_at` DateTime(timezone=True) not-null
- **No `project_id` column** — rubric item 10

**`project_source_snapshot`**
- `id` UUID PK
- `project_id` UUID FK→project not-null
- `source_snapshot_id` UUID FK→source_snapshot not-null
- `origin` Text not-null (`uploaded` | `acquired`)
- `run_id` UUID FK→runs nullable
- `ingested_at` DateTime(timezone=True) not-null
- `UniqueConstraint("project_id", "source_snapshot_id", name="uq_project_source_snapshot")`

**`chunk`**
- `chunk_id` UUID PK
- `source_snapshot_id` UUID FK→source_snapshot not-null
- `sequence` Integer not-null
- `content` Text not-null
- `content_hash` Text not-null
- `locator` JSONB not-null (`{"sequence": n}` this slice — minimal, no parser)
- `segmentation_policy` Text not-null — fixed `"manual_v1"` this slice; **mandatory column, no server default** (rubric item 11)
- `created_at` DateTime(timezone=True) not-null
- `UniqueConstraint("source_snapshot_id", "sequence", name="uq_chunk_snapshot_sequence")`

**`citation`**
- `citation_id` UUID PK
- `annotation_id` UUID FK→annotation not-null
- `chunk_id` UUID FK→chunk not-null
- `quote` Text not-null
- `verification_result` Text not-null (`pass` | `fail`)
- `created_at` DateTime(timezone=True) not-null

**Verify:** `python -c "from policy_atlas.schema import metadata; assert len(metadata.tables) == 11"`

---

### Step 2 — Alembic migration

**Files:** `alembic/versions/<new_rev>_corpus_source_model.py`

`down_revision = '68afc1c2def1'`. `upgrade()` creates tables in FK-safe order: `source_snapshot`
first, then `project_source_snapshot` + `chunk`, then `citation`. `downgrade()` reverses.

Follow existing migration conventions (named FKs, `sa.UUID()` not `as_uuid=True`, JSONB import
from `sqlalchemy.dialects.postgresql`).

**Verify:** `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` clean.

---

### Step 3 — ingest.py (new module)

**Files:** `src/policy_atlas/ingest.py`

```python
def ingest_upload(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    chunks: list[str],
    source_locator: str,
    metadata: dict[str, Any],
    text_basis: str,  # "full_text" | "abstract_only"
) -> uuid.UUID:
```

1. Import `content_hash` from `grounding.py` (no circular dependency — grounding imports schema, not ingest).
2. Compute snapshot content hash: `content_hash("".join(chunks))`.
3. Insert `source_snapshot` — **always a new UUID; no content-hash dedup** (per spec: re-upload = new snapshot).
4. Insert `chunk` rows (sequence 1-indexed, `segmentation_policy="manual_v1"`, `locator={"sequence": i+1}`).
5. Insert `project_source_snapshot` (`origin="uploaded"`, `run_id=None`).
6. Return `source_snapshot_id`.

**Verify:** `python -c "from policy_atlas.ingest import ingest_upload"` clean.

---

### Step 4 — test_ingest.py (new)

**Files:** `tests/test_ingest.py`

Three tests (all use `conn` fixture — rolled-back transaction):

1. `test_ingest_upload_creates_expected_rows` — round-trip: correct row counts, `segmentation_policy="manual_v1"`, membership row has `origin="uploaded"`, `run_id IS NULL`.
2. `test_ingest_upload_no_dedup` — two calls with identical content produce **two distinct** `source_snapshot_id` values (rubric item 13).
3. `test_source_snapshot_has_no_project_id_column` — inspect table columns; assert `project_id` absent (rubric item 10).

**Verify:** `make test` green.

---

### Step 5 — grounding.py seam flip

**Files:** `src/policy_atlas/grounding.py`

Changes:
1. Remove `from policy_atlas.fixtures import get_source`.
2. Add imports: `chunk as chunk_table, citation` from `policy_atlas.schema`.
3. Signature: `source_ref: str` → `source_snapshot_id: uuid.UUID`.
4. Replace fixture lookup with DB query — `SELECT chunk_id, content FROM chunk WHERE source_snapshot_id = ? ORDER BY sequence`.
5. Raise `ValueError` if no chunks found.
6. Pass `chunk_texts` (tuple of `content` strings) to `quote_present`.
7. After inserting `annotation`, insert `citation` row — find the chunk whose content contains the normalised quote (fall back to first chunk if quote spans boundary); `chunk_id` FK always set, even on fail (flag-don't-drop).
8. `annotation.payload` shape: `{"quote": ..., "verification_result": ...}` — remove `source_ref` key (now canonical in `citation` FK).
9. Return dict gains `"citation_id"` key.
10. Update `GroundingError` message.

**Verify:** `make typecheck` on grounding.py; signature confirmed.

---

### Step 6 — test_grounding.py (updated)

**Files:** `tests/test_grounding.py`

Add `_seed_snapshot(conn, project_id) -> uuid.UUID` helper that calls `ingest_upload` with the
same two-sentence synthetic source used by the walking skeleton.

Update `test_produce_grounded_block_pass`:
- Seed snapshot; pass `source_snapshot_id`.
- Remove `row.payload["source_ref"] == "syn-001"` assertion.
- Add: assert returned dict has `"citation_id"`; query `citation` table, assert `chunk_id IS NOT NULL`, `verification_result == "pass"`.

Update `test_produce_grounded_block_fabricated_quote_hard_fail`:
- Seed snapshot; pass `source_snapshot_id`.
- Assert `GroundingError` raised.
- Add: query `citation` row, assert `verification_result == "fail"`, `chunk_id IS NOT NULL` (rubric item 16).

New `test_citation_annotation_fk_integrity`:
- After a successful grounding call, assert every `annotation_type='citation'` row has a matching `citation` row (rubric item 14).

**Verify:** `make test` green.

---

### Step 7 — plan.py / harness.py / skeleton.py (signature cascade)

**Files:** `src/policy_atlas/plan.py`, `src/policy_atlas/harness.py`, `src/policy_atlas/skeleton.py`,
`tests/test_compile.py`, `tests/test_harness.py`

`Plan` and `Config`: replace `source_ref: str` with `source_snapshot_id: uuid.UUID`; remove the
`VALID_SOURCES` allowlist (no longer a static compile-time check — the DB enforces referential
integrity). Update `compile()` accordingly.

`harness.py`: `_run_echo` passes `source_snapshot_id=config.source_snapshot_id`.

`skeleton.py`: call `ingest_upload` to seed the synthetic source before constructing `Plan`;
pass returned UUID as `source_snapshot_id`.

`test_compile.py`: all `Plan(component="echo", source_ref="syn-001")` → `Plan(component="echo", source_snapshot_id=uuid.uuid4())`.

`test_harness.py`: seed a snapshot before each test that constructs a Plan with a snapshot ID; reuse `_seed_snapshot` helper.

**Verify:** `make test && make typecheck` green.

---

### Step 8 — test_schema.py (updated)

**Files:** `tests/test_schema.py`

1. Rename `test_all_seven_tables_exist` → `test_all_eleven_tables_exist`; update expected set.
2. Add `test_citation_chunk_fk_fails_with_phantom_chunk_id` — FK violation check.
3. Add `test_chunk_unique_snapshot_sequence_constraint`.
4. Add `test_project_source_snapshot_unique_constraint`.

**Verify:** `make test` green.

---

### Step 9 — helpers.py (delete_project_data extended)

**Files:** `tests/helpers.py`

Extend `delete_project_data` to clean up new tables in FK-safe order:

1. Capture snapshot IDs via `project_source_snapshot` before deleting.
2. Delete `citation` rows where `annotation_id` belongs to this project's blocks.
3. Delete existing `annotation` / `addressable_unit` / `block` (existing).
4. Delete `project_source_snapshot` where `project_id = ?`.
5. Delete `chunk` where `source_snapshot_id IN (captured IDs)`.
6. Delete `source_snapshot` where `source_snapshot_id IN (captured IDs)`.

**Verify:** `test_fail_annotation_survives_commit` passes without FK violation.

---

### Step 10 — docs/deferred.md (4 new seams)

**Files:** `docs/deferred.md`

Add under "Data model / evidence":
- `supersedes` edge on `source_snapshot` (human-asserted, not built this slice).
- Content-hash dedup for acquired cross-project snapshots (shape present; dedup logic follow-on).
- `search_coverage_record` table (required for absence claims; deferred to `acquire` slice).
- LLM-as-judge grounding tier on `citation` (`verification_result` is deterministic quote-presence only; full tier classification deferred).

---

## Files touched per step

| Step | Files |
|---|---|
| 1 | `src/policy_atlas/schema.py` |
| 2 | `alembic/versions/<new_rev>_corpus_source_model.py` |
| 3 | `src/policy_atlas/ingest.py` (new) |
| 4 | `tests/test_ingest.py` (new) |
| 5 | `src/policy_atlas/grounding.py` |
| 6 | `tests/test_grounding.py` |
| 7 | `src/policy_atlas/plan.py`, `src/policy_atlas/harness.py`, `src/policy_atlas/skeleton.py`, `tests/test_compile.py`, `tests/test_harness.py` |
| 8 | `tests/test_schema.py` |
| 9 | `tests/helpers.py` |
| 10 | `docs/deferred.md` |

---

## Known boundary / design decisions to keep in mind during implementation

1. **No `VALID_SOURCES` replacement** — static compile-time source validation goes away. The DB FK on `citation.chunk_id` is the new enforcement boundary.

2. **Boundary-spanning quote → chunk_id selection** — when the quote's normalised form spans chunk boundaries, no single chunk contains it. Rule: scan chunks in sequence order; use the first chunk whose content contains the normalised quote; fall back to `chunk_ids[0]` (first chunk by sequence). Add a `# ponytail: boundary-spanning quote uses first-chunk fallback; replace with citation_chunk join table when real provider lands` comment at the fallback site in `grounding.py`. Record in `verification.md` (§ Known gaps) and in `docs/deferred.md`. The stub provider never triggers this path in tests.

3. **`annotation.payload` loses `source_ref`** — no other code path may depend on `payload.source_ref`. `test_grounding.py` is the only known assert; it is removed in Step 6.

4. **`fixtures.py` stays** — it is retired from the grounding runtime path but not deleted. Any test that doesn't need DB chunks may still import from it (none currently do after Step 6–7 updates). Clean it up in a later slice.
