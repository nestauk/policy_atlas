# Verification: 005-classify

## `make verify` result

| Step | Result |
|---|---|
| `pytest tests/` | 79 passed, 0 failed |
| `mypy src tests` | Success: no issues found in 25 source files |
| `ruff check src tests` | All checks passed |
| `uv build` | Built dist/policy_atlas-0.1.0.tar.gz and .whl |

## Named test results (`test_classify.py`)

All 17 cases green:

| # | Test | Result |
|---|---|---|
| 1 | `test_table_count` | PASSED |
| 2 | `test_stub_default_unknown` | PASSED |
| 3 | `test_stub_non_evidence` | PASSED |
| 4 | `test_stub_policy_guidance` | PASSED |
| 5 | `test_stub_rct` | PASSED |
| 6 | `test_classify_sources_round_trip` | PASSED |
| 7 | `test_classify_sources_skips_not_relevant` | PASSED |
| 8 | `test_classify_sources_skips_failed` | PASSED |
| 9 | `test_classify_count_invariant` | PASSED |
| 10 | `test_classified_by_run_id` | PASSED |
| 11 | `test_ck_bad_primary_evidence_type` | PASSED |
| 12 | `test_ck_open_tags_must_be_array` | PASSED |
| 13 | `test_uq_scope_source_duplicate` | PASSED |
| 14 | `test_cross_project_fk_rejected` | PASSED |
| 15 | `test_harness_classify_component` | PASSED |
| 16 | `test_source_classified_event_payload` | PASSED |
| 17 | `test_delete_project_data_removes_classification` | PASSED |

## Migration roundtrip

```
alembic downgrade -1  → Running downgrade b5d3e8f2a7c9 -> a8e3f1b2c5d9, classify table
alembic upgrade head  → Running upgrade a8e3f1b2c5d9 -> b5d3e8f2a7c9, classify table
```

Both clean (no errors).

## Table count

`assert len(metadata.tables) == 14` — verified by `test_table_count`.

## Check constraint coverage

- `test_ck_bad_primary_evidence_type` — inserts a non-allowlisted string → `IntegrityError` on `ck_scr_primary_evidence_type`.
- `test_ck_open_tags_must_be_array` — inserts Python dict `{}` (stored as JSON object) → `IntegrityError` on `ck_scr_open_tags_array`.

## Cross-project FK test

`test_cross_project_fk_rejected` — scope from project A, source from project B inserted with `project_id=pid_a` → `IntegrityError` from `fk_scr_pss_project`.

## End-to-end command

```
DATABASE_URL="postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas_test" \
  python -m policy_atlas.skeleton
```

Exit 0. Output includes:
- `component.completed component=screen relevant=1 screened=1`
- `component.completed component=classify classified=1 by_type={'Unknown / Insufficient information': 1} skipped=0`
- `classification_result evidence_type='Unknown / Insufficient information' open_tags=[]`
- 12 event log entries in sequence order

## Diff summary

Files changed (8 modified, 3 new):

| File | Change |
|---|---|
| `src/policy_atlas/schema.py` | Added `source_classification_result` table; docstring 13→14 tables |
| `src/policy_atlas/classify.py` | New — `ClassifyContext`, `ClassifyResult`, `_stub_classify`, `classify_sources` |
| `src/policy_atlas/plan.py` | Added `"classify"` to `COMPONENT_REGISTRY` |
| `src/policy_atlas/harness.py` | Added `_run_classify` node; wired into `build_graph()` |
| `src/policy_atlas/skeleton.py` | Added classify run after screen run; logs classification results |
| `alembic/versions/b5d3e8f2a7c9_classify_table.py` | New migration — create/drop `source_classification_result` |
| `tests/test_classify.py` | New — 17 test cases |
| `tests/test_compile.py` | Added `test_classify_requires_screening_scope_id`, `test_classify_valid_with_scope_id` |
| `tests/test_schema.py` | Renamed test, added `source_classification_result` to expected set |
| `tests/test_screen.py` | Bumped table count assertion 13→14 |
| `tests/helpers.py` | Added `source_classification_result` deletion before `source_screening_result` |

## Public-safety confirmation

- No source text, credentials, or egress in any committed file.
- No new LLM calls, no inference provider calls, no network I/O.
- Stub sentinels (`_stub_non_evidence`, etc.) are test infrastructure only; not exported.
- Durable public surface: table name, column names, `ClassifyResult`/`ClassifyContext` field names, event payload keys.

## Deferred seams recorded

Added to `docs/deferred.md`:
- LLM-based classify tool
- `open_tags` population
- Open tag namespace consolidation
- `Unknown` resolution on full text
- Grey-lit category granularity (expanded existing entry)
- `appraise` and subsequent EB components

## Review findings

_To be filled after the review stack runs._
