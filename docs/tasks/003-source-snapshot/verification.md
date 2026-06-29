# Verification: 003-source-snapshot

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make test` | **32 passed** | 0 failed, 0 skipped |
| `make typecheck` | **pass** | 21 source files, no issues |
| `make lint` | **pass** | all checks passed |
| `make build` | **pass** | wheel + sdist built |

## Checks beyond the build

**Deterministic tests run (32):**
- `test_compile.py` (4) — Plan/Config validation; invalid component rejected; VALID_SOURCES removed
- `test_events.py` (3) — event-log append, ordering, cross-project FK rejection
- `test_grounding.py` (8) — content_hash stability, quote-presence pass/fail/boundary, grounded-block pass, fabricated-quote hard-fail, citation FK integrity
- `test_harness.py` (6) — run lifecycle succeeded/failed, project mismatch guard, component.failed event, event log ordering, commit-survival
- `test_ingest.py` (3) — round-trip rows, no-dedup (two identical calls → two distinct snapshots), source_snapshot has no project_id column
- `test_schema.py` (8) — 11 tables present, event-log unique constraint, addressable-unit constraint, block server default, annotation composite FK, citation chunk FK (phantom rejected), chunk unique constraint, project_source_snapshot unique constraint

**Migration roundtrip:**
```
alembic downgrade -1  → Running downgrade c4f2a9b3e8d1 -> 68afc1c2def1, corpus source model
alembic upgrade head  → Running upgrade 68afc1c2def1 -> c4f2a9b3e8d1, corpus source model
```
Both clean.

**Table count:**
```
python -c "from policy_atlas.schema import metadata; assert len(metadata.tables) == 11"
# → OK: ['project', 'artefact', 'block', 'addressable_unit', 'annotation', 'runs',
#         'event_log', 'source_snapshot', 'project_source_snapshot', 'chunk', 'citation']
```

## End-to-end command

```
DATABASE_URL="postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas" \
  uv run python -m policy_atlas.skeleton
```

Output (condensed):
```
skeleton.start
project.created         project_id=94059672-...
run.started             run_id=2d19c18d-...
source.ingested         source_snapshot_id=8745244a-...
plan.compiled           component=echo
component.started       component=echo
block.written           block_id=0dc45d15-...
run.completed           run_id=2d19c18d-...
persisted_id            artefact_id=55dd27c9-...
persisted_id            block_id=0dc45d15-...
persisted_id            unit_id=1622ce69-...
persisted_id            annotation_id=fd5e01cc-...
persisted_id            citation_id=6afe30a8-...
event log: run.started → plan.compiled → component.started → component.completed → block.written → run.completed
skeleton.done
```

Grounding pass: `citation_id` persisted (new this slice); `annotation.payload` has no `source_ref` key; citation row has `chunk_id` FK and `verification_result=pass`.

## Diff summary

**New tables (4):** `source_snapshot`, `project_source_snapshot`, `chunk`, `citation`. One Alembic migration (`c4f2a9b3e8d1`). Migration roundtrip clean.

**New module `ingest.py`:** `ingest_upload()` — creates source_snapshot + chunk rows + corpus membership in one call. No content-hash dedup for uploaded sources (per spec: each re-upload is a new snapshot).

**Seam flip in `grounding.py`:** `source_ref: str` → `source_snapshot_id: uuid.UUID`. Chunks now resolved from DB via `SELECT … FROM chunk WHERE source_snapshot_id = … ORDER BY sequence`. Citation row inserted in `citation` table after annotation (FK integrity). annotation.payload loses `source_ref` key. Return dict gains `citation_id`. `fixtures.get_source` removed from grounding runtime.

**`plan.py`:** `VALID_SOURCES` allowlist removed; `source_ref: str` → `source_snapshot_id: uuid.UUID`. DB FK on `citation.chunk_id` is the new enforcement boundary.

**`harness.py`:** passes `source_snapshot_id=config.source_snapshot_id` to `produce_grounded_block`.

**`skeleton.py`:** calls `ingest_upload` to seed synthetic source before constructing Plan.

**Tests:** `test_ingest.py` (new, 3 tests); `test_grounding.py`, `test_harness.py`, `test_compile.py`, `test_schema.py` updated. One test removed: `test_invalid_source_ref_raises_at_plan_construction` — its subject (VALID_SOURCES compile-time check) was removed per the contract.

**`helpers.py`:** `delete_project_data` extended to clean up citation, project_source_snapshot, chunk, source_snapshot in FK-safe order.

**`docs/deferred.md`:** 5 new seams recorded (supersedes edge, acquired dedup, search_coverage_record, LLM-as-judge grounding, boundary-spanning citation_chunk join table).

## Review findings

- **Contract verifier** (`agent-skills:code-reviewer`, fresh context): CONDITIONAL PASS — all 17 rubric items satisfied except Item 8 (review stack not yet recorded). One minor fix applied: stale comment on `annotation.payload` in schema.py (`{source_ref, quote, verification_result}` → `{quote, verification_result}`). Additional observations: `test_compile.py` VALID_SOURCES coverage claim slightly overstated in verification.md (corrected here); `test_ingest_upload_no_dedup` unique-constraint note (non-issue, assertion fires first).

- **`/code-review`** (inline, independent pass): No correctness bugs. No injection paths — all writes via SQLAlchemy parameterized `insert().values()`. Minor: `text_basis` not validated against allowed values (info/acceptable v3.0). Test payload assertion only checks absence of `source_ref`, not presence of expected keys (low coverage gap, not a bug).

- **`/security-review`** (inline): No SQL injection. No cross-project enforcement that `source_snapshot_id` belongs to the project owning `artefact_id` — by design (auth/tenancy deferred for v3.0, greenfield no real data). Flag-don't-drop invariant depends on harness catching `GroundingError` before transaction boundary — tested in `test_fail_annotation_survives_commit`, acceptable.

- **Adversarial review** (inline design challenge): VALID_SOURCES removal — failure mode shifts from compile-time `ValidationError` to runtime `ValueError`; acceptable for v3.0 controlled callers. `chunk_ids[0]` fallback — documented in deferred.md and contract, stub never triggers; acceptable. Metadata unvalidated — greenfield trusted callers, acceptable.

- **`/simplify`**: Applied one cleanup — removed redundant `chunk_ids` list in `produce_grounded_block`; replaced `zip(chunk_ids, chunk_texts)` boundary scan with direct iteration over `rows`. `make verify` still 32/32 green.

- **`/okf validate docs/knowledge`:** **0 errors, 0 lints** (no new concept files this slice — pass as expected)

## Rubric status

1. [x] Implementation satisfies contract.md — confirmed by contract verifier (CONDITIONAL PASS; all slice-specific behaviours built)
2. [x] `make verify` passes (32 tests, typecheck, lint, build)
3. [x] No approval-gated change snuck in unapproved — schema, public interface change on `produce_grounded_block` and `Plan`/`Config` both approved in contract
4. [x] No generated files or secrets edited by hand
5. [x] No tests deleted, skipped or weakened without written justification — one test removed (`test_invalid_source_ref_raises_at_plan_construction`) because its subject (VALID_SOURCES allowlist) was removed per the contract; replacement enforcement is DB FK
6. [x] Verification evidence recorded here
7. [x] Known gaps and deferred seams in docs/deferred.md (5 new seams)
8. [x] Review stack ran — contract verifier, code review, security review, adversarial review, simplify; findings above
9. [x] `/okf validate docs/knowledge` clean (0 errors, 0 lints)

### Slice-specific checks

10. [x] `source_snapshot` has no `project_id` column — confirmed by `test_source_snapshot_has_no_project_id_column`
11. [x] `chunk.segmentation_policy` column exists and is populated with `"manual_v1"` — confirmed by `test_ingest_upload_creates_expected_rows`
12. [x] `source_locator` lives on `source_snapshot`, not chunk — no `source_locator` column on chunk
13. [x] Upload ingest creates a new `source_snapshot` row on each call — confirmed by `test_ingest_upload_no_dedup`
14. [x] Every `annotation_type='citation'` annotation has a `citation` row with non-null `chunk_id` — confirmed by `test_citation_annotation_fk_integrity`
15. [x] `produce_grounded_block` no longer calls `fixtures.get_source()` — confirmed by code inspection; import removed
16. [x] Fabricated-quote hard-fail fires: `GroundingError` raised, `citation.verification_result='fail'`, `chunk_id` still set — confirmed by `test_produce_grounded_block_fabricated_quote_hard_fail`
17. [x] `citation.verification_result` values are `pass` | `fail` only — LLM-as-judge deferred seam recorded

## Intent & assumptions

- `ingest_upload` accepts pre-parsed chunk strings (no text-parsing library this slice).
- Boundary-spanning quote: when no single chunk contains the normalised quote, `citation.chunk_id` falls back to `chunk_ids[0]` (first chunk by sequence). The stub provider never triggers this in tests. Recorded in deferred.md.
- `fixtures.py` stays in the repo (not deleted) — retired from grounding runtime only; available for any test that doesn't need DB chunks.

## Known unverified items

- Boundary-spanning quote fallback path is untriggered in tests (stub provider always produces a quote fitting within chunk 2).
- `alembic downgrade` behaviour on a DB with real data is untested (greenfield — no real data).

## Public safety

All test chunks are hand-written synthetic sentences. No real source text, no uploaded/acquired document content, no egress, no credentials in any committed file.

## Deferred work

See [docs/deferred.md](../../deferred.md). New seams this slice:
- `supersedes` edge on `source_snapshot`
- Content-hash dedup for acquired cross-project snapshots
- `search_coverage_record` table
- LLM-as-judge grounding tier on `citation`
- Boundary-spanning quote → `citation_chunk` join table
