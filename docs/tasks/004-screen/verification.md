# Verification: 004-screen

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make test` | **60 passed** | All tests deterministic |
| `make typecheck` | **pass** | No issues in 23 source files |
| `make lint` | **pass** | All checks passed |
| `make build` | **pass** | Wheel and sdist built |

## Checks beyond the build

**Deterministic tests — all pass:**

- `test_screen_table_count` — `len(metadata.tables) == 13` ✓
- `test_pss_has_composite_unique` — `uq_pss_id_project` present ✓
- `test_stub_relevant_with_abstract` — basis=title_abstract, confidence=0.9, status=relevant ✓
- `test_stub_relevant_without_abstract` — fail-open: basis=title_only, confidence=0.7, status=relevant ✓
- `test_stub_not_relevant` — sentinel → not_relevant, basis set, confidence=0.95 ✓
- `test_stub_failed` — sentinel → failed, basis=None, confidence=None ✓
- `test_ck_bad_status`, `test_ck_bad_basis`, `test_ck_confidence_out_of_range`,
  `test_ck_failed_with_non_null_basis`, `test_ck_relevant_with_null_confidence` — all five check
  constraints reject bad rows ✓
- `test_screen_sources_relevant_with_abstract`, `test_screen_sources_fail_open`,
  `test_screen_sources_not_relevant`, `test_screen_sources_failed` — single-source round-trips ✓
- `test_screen_sources_mixed_counts` — 3 sources, mixed results, counts verified ✓
- `test_screen_context_from_jsonb` — ScreenContext.context loaded from JSONB ✓
- `test_source_screened_event_payload` — all six payload keys/values match spec ✓
- `test_unique_constraint_scope_source` — duplicate (scope, source) → IntegrityError ✓
- `test_cross_project_fk_rejected` — scope from project A, pss from project B → IntegrityError ✓
- `test_harness_screen_component` — Plan(component="screen") → succeeded; two result rows;
  component.completed payload has all seven keys ✓

**Migration roundtrip:**

```
alembic downgrade -1   → INFO Running downgrade a8e3f1b2c5d9 -> c4f2a9b3e8d1, screen tables
alembic upgrade head   → INFO Running upgrade c4f2a9b3e8d1 -> a8e3f1b2c5d9, screen tables
```

Both clean. No errors.

**No AI evals, no manual/browser checks required** (all acceptance criteria are deterministic tests
per contract §Acceptance checks).

## End-to-end command

```bash
DATABASE_URL="postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas_test" \
  uv run pytest tests/test_screen.py -v
```

Harness end-to-end: `test_harness_screen_component` invokes `run_harness` with
`Plan(component="screen", screening_scope_id=...)`, seeds two sources, and verifies result rows in
DB + event log.

## Diff summary

**New files:**
- `src/policy_atlas/screen.py` — `ScreenContext`, `ScreenResult`, `_stub_screen`, `screen_sources`
- `alembic/versions/a8e3f1b2c5d9_screen_tables.py` — migration for two new tables + one new
  unique constraint on `project_source_snapshot`
- `tests/test_screen.py` — 22 tests covering schema, stub logic, check constraints, round-trips,
  harness integration

**Edited files:**
- `src/policy_atlas/schema.py` — add `uq_pss_id_project` to `project_source_snapshot`; add
  `screening_scope` and `source_screening_result` tables (three composite FKs, five check
  constraints, unique constraint, index)
- `src/policy_atlas/plan.py` — component-scope registry (`COMPONENT_REGISTRY`); `screening_scope_id`
  field added to `Plan` and `Config`; `source_snapshot_id` made optional with required-field check
- `src/policy_atlas/harness.py` — `_run_screen` node; graph wiring for `"screen"` component
- `src/policy_atlas/skeleton.py` — replaced echo demo with screen demo
- `tests/helpers.py` — `delete_project_data` extended with `source_screening_result` and
  `screening_scope` in FK-safe order
- `tests/test_compile.py` — 3 new tests for component-scope registry; existing tests updated
- `tests/test_schema.py` — table count 11 → 13; new table names in assertion

## Review findings

- **Contract verifier:** PASS WITH NOTES. All 23 rubric items satisfied. One gap found:
  `test_screen_context_from_jsonb` tested the caller-supplied value instead of the DB load path —
  fixed: test now goes through `run_harness` and reads back `dict(row.context)`.

- **`/code-review`:** 9 findings raised; all confirmed to be false positives against plan.md/contract.md
  pseudocode rather than the implementation (compile() forwarding, edge map, screened_at, etc.).
  One real finding: AGENTS.md had stale column/table names from pre-design — fixed.

- **`/security-review`:** No findings. All SQL parameterised; no PII/secrets logged; cross-project
  isolation enforced at DB layer; no new attack surface introduced.

- **Adversarial review:** Two actionable findings:
  1. `screen.py:37` — `.strip()` on abstract (whitespace-only → `title_only`) diverged from contract
     wording "non-empty". Contract updated to say "non-blank"; code behaviour confirmed correct.
  2. `screen_sources` N+1 query — fixed: single JOIN replaces per-row metadata SELECT.
  Noted (deferred): Plan/Config duplicate validators; `component.started` ordering asymmetry in
  scope-not-found path; `provider` arg unused by screen component.

- **`/simplify`:** Six fixes applied:
  - `plan.py` — `_ValidatedRunSpec` base class eliminates copy-pasted validator
  - `harness.py` — bare `assert` → `if/raise` for mypy narrowing + runtime reliability
  - `harness.py _run_screen` — `component.started` moved before scope lookup (consistent with echo)
  - `screen.py` — `counts["screened"] = len(rows)` before loop
  - `test_screen.py _ssr_insert` — raw SQL string → `insert().values(**defaults)` (13 lines → 1)
  - `skeleton.py` — read-back moved inside first `engine.begin()` block; second connection removed

- **`/okf validate`:** n/a — no docs/specs/ or docs/knowledge/ changes this slice

## Rubric status

1. ✓ Implementation satisfies contract.md (all deliverables present, all acceptance checks pass)
2. ✓ `make verify` passes; all checks are deterministic tests
3. ✓ Both gated changes (schema + Plan/Config interface) were pre-approved in contract §Constraints
4. ✓ No generated files or secrets edited by hand
5. ✓ No tests deleted, skipped, or weakened
6. ✓ Verification evidence in this file
7. ✓ Deferred seams recorded in docs/deferred.md
8. ✓ Review stack ran — contract verifier · `/code-review` · `/security-review` · adversarial review · `/simplify`; all findings addressed or explicitly deferred
9. ✓ `/okf validate` not required (no spec/knowledge changes)
10. ✓ `len(metadata.tables) == 13` — test_screen_table_count
11. ✓ Migration roundtrip clean (see above)
12. ✓ `uq_pss_id_project` present — test_pss_has_composite_unique
13. ✓ All five check constraints, unique constraint, and index — test_ssr_columns + constraint tests
14. ✓ Cross-project insert rejected — test_cross_project_fk_rejected
15. ✓ Fail-open enforced — test_stub_relevant_without_abstract
16. ✓ `status=failed` → null basis and confidence — test_stub_failed + test_screen_sources_failed
17. ✓ `screened_by_run_id` set on every result row — test_screen_sources_relevant_with_abstract
18. ✓ `ScreenContext.context` loaded from JSONB — test_screen_context_from_jsonb
19. ✓ `source.screened` payload matches spec — test_source_screened_event_payload
20. ✓ `component.completed` has all seven keys — test_harness_screen_component
21. ✓ Component-scope registry covers both echo and screen; unknown still rejected — test_compile.py
22. ✓ No relevance state on `project_source_snapshot` (no new column added)
23. ✓ `delete_project_data` order correct — tests/helpers.py updated

## Intent & assumptions

- `screen_decision_confidence` is eval/audit data, not a relevance signal (per contract §Note).
- Stub sentinels (`_stub_failed`, `_stub_not_relevant`) are test infrastructure only; not a public
  contract; safe to change when the real LLM screen lands.
- `context: {}` default on `screening_scope` is set at insert time, not via server default, to keep
  schema migrations simple.

## Known unverified items

- `SAWarning: transaction already deassociated from connection` on 7 constraint tests — this is a
  known artifact of the rollback/begin pattern used to restore transaction state after an
  `IntegrityError`. The tests are correct; the warning is cosmetic.

## Public safety

No source text, credentials, or secrets in any committed file. Stub sentinels are internal test
keys only. All test data is synthetic UUIDs and placeholder strings.

## Deferred work

Seams added to `docs/deferred.md`:
- Thin-base re-search trigger
- Re-screening (second result row for same scope+source pair)
- LLM-based screen tool
- `screen_failed` recovery loop
