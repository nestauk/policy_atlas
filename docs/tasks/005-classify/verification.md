# Verification: 005-classify

This slice went through two rounds: an initial implementation, then a Tier 3 review stack
that found and fixed real issues (idempotency, cross-project scope handling, per-document
fault isolation, and a reporting invariant), plus one deliberate architectural decision
(no FK from classification to screening result). This document reflects the final,
post-review state.

No schema change beyond the one originally approved landed: the review stack's schema-adjacent
finding (a possible FK from `source_classification_result` to `source_screening_result`) was
resolved by decision, not by adding a constraint — recorded in `docs/deferred.md` instead. The
table, its three composite FKs, and its two check constraints are exactly what `contract.md`
approved.

## `make verify` result

| Step | Result |
|---|---|
| `pytest tests/` | 84 passed, 0 failed |
| `mypy src tests` | Success: no issues found in 25 source files |
| `ruff check src tests` | All checks passed |
| `uv build` | Built dist/policy_atlas-0.1.0.tar.gz and .whl |

## Named test results (`test_classify.py`)

All 20 cases green:

| # | Test | Result |
|---|---|---|
| 1 | `test_table_count` | PASSED |
| 2 | `test_stub_default_unknown` | PASSED |
| 3 | `test_stub_non_evidence` | PASSED |
| 4 | `test_stub_policy_guidance` | PASSED |
| 5 | `test_stub_rct` | PASSED |
| 6 | `test_classify_sources_round_trip` | PASSED |
| 7 | `test_classify_sources_non_evidence_persists` | PASSED |
| 8 | `test_classify_sources_skips_not_relevant` | PASSED |
| 9 | `test_classify_sources_skips_failed` | PASSED |
| 10 | `test_classify_count_invariant` | PASSED |
| 11 | `test_classify_sources_idempotent_rerun` | PASSED |
| 12 | `test_classified_by_run_id` | PASSED |
| 13 | `test_ck_bad_primary_evidence_type` | PASSED |
| 14 | `test_ck_open_tags_must_be_array` | PASSED |
| 15 | `test_uq_scope_source_duplicate` | PASSED |
| 16 | `test_cross_project_fk_rejected` | PASSED |
| 17 | `test_classify_sources_doc_exception_isolated` | PASSED |
| 18 | `test_harness_classify_component` | PASSED |
| 19 | `test_source_classified_event_payload` | PASSED |
| 20 | `test_delete_project_data_removes_classification` | PASSED |

Six added during the review stack: `#7` (non-evidence persistence — contract verifier gap),
`#11` (idempotent re-run), `#17` (per-doc exception isolation), plus three
`test_screen.py` additions of the same shape (see below).

### `test_screen.py` (existing file, materially changed by this slice)

`screen.py` needed the same fixes as `classify.py` (idempotency guard, per-doc exception
isolation) since the harness fix generalized both components. All 25 cases green, including
two added during review: `test_screen_sources_idempotent_rerun`,
`test_screen_sources_doc_exception_isolated`. `seed_source`/`seed_scope` (previously
duplicated verbatim between `test_screen.py` and `test_classify.py`) were moved into
`tests/helpers.py`.

## Migration roundtrip

```
alembic downgrade -1  → Running downgrade b5d3e8f2a7c9 -> a8e3f1b2c5d9, classify table
alembic upgrade head  → Running upgrade a8e3f1b2c5d9 -> b5d3e8f2a7c9, classify table
```

Both clean (no errors). Re-verified after the review-stack fixes (schema.py's
`ck_scr_primary_evidence_type` construction changed cosmetically — see Review findings —
but the constraint's semantics and the migration file are unchanged).

## Table count

`assert len(metadata.tables) == 14` — verified by `test_table_count`.

## Check constraint coverage

- `test_ck_bad_primary_evidence_type` — inserts a non-allowlisted string → `IntegrityError` on `ck_scr_primary_evidence_type`.
- `test_ck_open_tags_must_be_array` — inserts Python dict `{}` (stored as JSON object) → `IntegrityError` on `ck_scr_open_tags_array`.

## Cross-project FK test

`test_cross_project_fk_rejected` — scope from project A, source from project B inserted with `project_id=pid_a` → `IntegrityError` from `fk_scr_pss_project`. The harness-level scope lookup also now filters by `project_id` directly (see Review findings) — a second, independent guard against cross-project scope use at the component-dispatch layer, not just the database layer.

## End-to-end command

```
DATABASE_URL="postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas_test" \
  python -m policy_atlas.skeleton
```

Exit 0. Output includes:
- `component.completed component=screen relevant=1 screened=1`
- `component.completed component=classify classified=1 already_classified=0 by_type={'Unknown / Insufficient information': 1} skipped=0`
- `classification_result evidence_type='Unknown / Insufficient information' open_tags=[]`
- 12 event log entries in sequence order, both runs logging `run.started` consistently (previously the classify run logged `classify_run.started`, an inconsistency fixed during review)

## Diff summary

Files changed (11 modified, 3 new) — includes both the original implementation and the review-stack fix round:

| File | Change |
|---|---|
| `src/policy_atlas/schema.py` | Added `source_classification_result` table + `EVIDENCE_TYPES` constant (single source of truth for the 9 evidence-type strings, used by the CHECK constraint and the stub); docstring 13→14 tables |
| `src/policy_atlas/classify.py` | New — `ClassifyContext`, `ClassifyResult`, `_stub_classify`, `classify_sources`; review-stack fixes: idempotency guard (`WHERE NOT EXISTS`), per-doc exception isolation, `already_classified` count, structured-logging correlation |
| `src/policy_atlas/screen.py` | Review-stack fixes only (pre-existing file): idempotency guard, per-doc exception isolation, structured-logging correlation — same fixes as classify.py, since the harness generalizes both |
| `src/policy_atlas/plan.py` | Added `"classify"` to `COMPONENT_REGISTRY` |
| `src/policy_atlas/harness.py` | Added `_run_classify`; review-stack refactor collapsed `_run_screen`/`_run_classify` into a shared `_run_scope_component` helper that filters the scope lookup by `project_id` (previously missing) and wraps the sources-function call in try/except (previously unhandled exceptions left runs stuck at `status='running'`); artefact-row creation moved into `_run_echo` only (`HarnessState.artefact_id` is now `Optional`, unused by screen/classify) |
| `src/policy_atlas/skeleton.py` | Added classify run after screen run; logs classification results; fixed a log-key inconsistency (`classify_run.started` → `run.started`) |
| `alembic/versions/b5d3e8f2a7c9_classify_table.py` | New migration — create/drop `source_classification_result` |
| `tests/test_classify.py` | New — 20 test cases (17 original + 3 review-stack additions) |
| `tests/test_screen.py` | Review-stack additions: 2 new isolation/idempotency tests; `seed_source`/`seed_scope` deduplicated into `tests/helpers.py` |
| `tests/test_compile.py` | Added `test_classify_requires_screening_scope_id`, `test_classify_valid_with_scope_id` |
| `tests/test_schema.py` | Renamed test, added `source_classification_result` to expected set |
| `tests/helpers.py` | Added `source_classification_result` deletion before `source_screening_result`; added shared `seed_source`/`seed_scope` helpers (deduplicated from the two test files) |
| `docs/deferred.md` | Added classify-related deferred seams; added the structured-logging `bind_contextvars` gap; added the deliberately-absent `source_classification_result → source_screening_result` FK, with the `origin`-based (uploaded vs. acquired) rationale |
| `docs/tasks/005-classify/contract.md` | Corrected the `open_tags` schema block — no DB-level `server_default` exists; `classify_sources` supplies `[]` at the application layer |

## Public-safety confirmation

- No source text, credentials, or egress in any committed file.
- No new LLM calls, no inference provider calls, no network I/O.
- Stub sentinels (`_stub_non_evidence`, etc.) are test infrastructure only; not exported.
- Durable public surface: table name, column names, `ClassifyResult`/`ClassifyContext` field names, event payload keys, `classify_sources`'s return dict (now includes `already_classified`).
- `/security-review` ran against the full diff and found no findings above the reporting threshold (see Review findings).

## Deferred seams recorded

In `docs/deferred.md`:
- LLM-based classify tool
- `open_tags` population
- Open tag namespace consolidation
- `Unknown` resolution on full text
- Grey-lit category granularity (expanded existing entry)
- `appraise` and subsequent EB components
- `structlog.contextvars.bind_contextvars` never called despite being wired into the processor chain (structured-logging correlation gap); exceptions logged without traceback/type and no `exc_info` renderer configured
- `source_classification_result → source_screening_result` FK deliberately absent — not merely deferred hardening, but a plausible-wrong direction long-term: `project_source_snapshot.origin` distinguishes `uploaded` from `acquired` sources, and a future slice may let uploaded sources skip `screen` entirely (upload is itself a relevance signal). Confirmed: `acquired` sources always screen. Whether `uploaded` sources skip screen is an open question needing its own spec refinement before any component is built against it.

## Review findings

Tier 3 review stack (all steps run; findings resolved or explicitly deferred with reasoning):

**Contract verifier** — 14/15 rubric items satisfied on first pass. Gap: item 8 (`Other`/`Unknown`
rows persist, flag-don't-drop) was verified only at the stub-unit level, not with a DB round-trip
test. Fixed: added `test_classify_sources_non_evidence_persists`.

**`/code-review`** (workflow-backed, high effort) — 10 confirmed findings, 3 critical:
1. No idempotency guard — re-running `classify_sources`/`screen_sources` for the same scope raised
   `IntegrityError` on the unique constraint, rolling back the caller's transaction. Fixed: `WHERE
   NOT EXISTS` guard excludes already-processed rows.
2. `_run_classify`/`_run_screen` had no exception handling — a DB error left the run permanently at
   `status='running'` with no `run.failed` event. Fixed: shared `_run_scope_component` wraps the
   sources-function call.
3. The `screening_scope` lookup didn't filter by `project_id` — a cross-project scope was silently
   accepted (classified 0 rows, no error). Fixed: added the filter.
4. `skipped` undercounted (excluded unscreened sources). Not directly fixed (contract-defined
   semantics); superseded by the `already_classified` fix below, which addresses the concrete
   invariant break this caused.
5–10. Test coverage gaps (no run-status assertion), an orphan-artefact-row bug (fixed by moving
   artefact creation into `_run_echo` only), duplicated harness logic (fixed via
   `_run_scope_component`), duplicated evidence-type strings (fixed via `EVIDENCE_TYPES`),
   duplicated test helpers (fixed via `tests/helpers.py`), and a log-key inconsistency (fixed).

**Per-document fan-out isolation** (raised in review, not by an automated pass) — the harness-level
exception fix (finding 2 above) only prevented a stuck run; it did not provide per-document fault
isolation as required by `docs/specs/system/execution-orchestration.md` ("per-doc fan-out... a
retryable `screen_failed` state") and `docs/specs/capabilities/evidence-base/components.md`. Fixed:
the per-row loop in both `classify_sources` and `screen_sources` now wraps only the
classification/screening decision call in try/except, falling back to the existing
constraint-valid outcomes (`"Unknown / Insufficient information"` / `status="failed"`) rather than
aborting the batch. Verified by `test_classify_sources_doc_exception_isolated` and
`test_screen_sources_doc_exception_isolated` (monkeypatched stub raises on one document; the
sibling document still processes).

**Structured logging** — the two new per-doc failure log lines initially omitted `run_id`/
`project_id`/`screening_scope_id`, making them uncorrelatable in production JSON logs. Fixed:
added all three. Separately identified and deferred: `bind_contextvars` is never called anywhere
despite being wired into the processor chain (see Deferred seams).

**Fresh Claude re-review** (independent `agent-skills:code-reviewer`, no inherited context) — 2
Important findings: the idempotency fix was unverified by any test (fixed: added re-run tests for
both components), and `classified + skipped` silently broke its invariant on a re-run because
`skipped` didn't account for already-classified rows (fixed: added the `already_classified` count,
`classified + skipped + already_classified == total` now holds unconditionally). Minor suggestions
(a redundant string-concat artifact in the CHECK constraint — fixed; loose `context_cls: type`
typing and duplicate table-count assertions — left as explicitly non-blocking per the reviewer's
own framing).

**`/security-review`** — no findings above the reporting threshold. Traced the CHECK-constraint
string interpolation (safe — `EVIDENCE_TYPES` is a fixed compile-time tuple, no external input
path), the `source_snapshot.metadata` JSONB flow (never reaches SQL/subprocess/eval/template), the
one raw `sa.text()` call in the diff (`skeleton.py`'s fixed `"SELECT 1"` literal, no
interpolation), and the new log lines (UUIDs and error messages only, no secrets/PII).

**Codex adversarial review** (`codex:codex-rescue`) — together with the fresh Claude re-review
above (`agent-skills:code-reviewer`), this satisfies the Tier 3 "two heterogeneous reviewers"
requirement (task-cycle's own example pairing: `/codex:adversarial-review` + an
`agent-skills:code-reviewer` subagent — different model families, not two of the same). 1
Medium, 1 Low, both resolved:
- Medium: no FK ties `source_classification_result` to `source_screening_result`, so "only
  relevant sources are classified" is enforced only in application code. Resolved by decision, not
  code: recorded in `docs/deferred.md` as deliberately absent (see Deferred seams) rather than
  added, since a hard FK could block a legitimate future data shape (uploaded sources classified
  without ever being screened).
- Low: `open_tags`'s contracted `DEFAULT '[]'` doesn't exist as a DB `server_default`. Resolved by
  correcting `contract.md` to describe the actual (sufficient) application-level guarantee, rather
  than adding a schema-level default with no behavioral effect.
- Independently confirmed a genuine concurrency race exists at the SQL level (concurrent writers
  could race past the `WHERE NOT EXISTS` check) but is out of scope under v3.0's documented
  single-active-writer, serial-execution architecture (`execution-orchestration.md`) — no action
  needed.
- Checked clean: `exists()` correlation correctness, the three composite FKs, CHECK-constraint
  safety, `Other`/`Unknown` persistence.

**`/code-simplify`** (4 parallel cleanup agents — reuse, simplification, efficiency, altitude) — 2
real findings, both fixed:
- The new `already_classified` count query duplicated `relevant_rows`'s filter set via an
  unnecessary join and an inverted `exists()`. Fixed: eliminated the second query entirely —
  `already_classified = total_relevant - len(relevant_rows)`, where `total_relevant` is a
  join-free count mirroring `skipped`'s existing style.
- `EVIDENCE_TYPES[-1]` was duplicated (with a repeated explanatory comment) in `_stub_classify`'s
  default fallback and the per-doc exception fallback. Fixed: extracted to
  `_UNKNOWN_EVIDENCE_TYPE`.
- Explicitly left alone, with reasoning: the idempotency-guard shape and the per-row try/except
  block are structurally similar between `classify.py`/`screen.py` but not unified — the altitude
  pass validated this as the correct depth (the fallback result types differ meaningfully;
  unifying would need ~7 pass-through parameters for ~10 lines and would erase fallback type
  safety). The `_run_scope_component` harness extraction was independently validated as the right
  level of generalization (not a bandaid, not over-abstracted).

**OKF validate** — confirmed not applicable; no `docs/specs/` or `docs/knowledge/` files touched by
this diff.
