# Implementation Plan: 007-acquire

> **Status:** confirmed — 2026-07-05 · Shabeer Rauf (plan-phase adversarial review
> adjudicated, 7/7 findings adopted; go given via "Commit the plan, and I'll start
> implementation in a new chat").
> Contract: [contract.md](contract.md) (approved 2026-07-05 · Shabeer Rauf; all three gated
> changes signed off; contract-stage adversarial findings adjudicated).

## Overview

Two mechanically separable stages on one branch:
1. **The rename** — `screening_scope` → `evidence_scope`, clean and total (schema, migration,
   code, event payload keys, tests). Lands first so all acquire code is born under the new name.
2. **The acquire component** — `SearchBackend` seam with fixture-backed OpenAlex + Overton,
   per-backend envelope mappings, text-in-hand snapshots, `search.executed` governance events,
   `search_coverage_record`, project-scoped three-guard dedup, sanitized committed fixtures +
   dev-time recorder scripts.

Unlike 004–006 this slice **creates** sources rather than deriving results over them, so it has
no result table; its durable rows are snapshots + project links + the coverage record.

## Architecture decisions (all fixed in the approved contract)

- Backends: `OpenAlexFixtureBackend` / `OvertonFixtureBackend` behind the `SearchBackend`
  protocol (`name`, `trust_class`, `mode`, `search()`); trust classes `academic_aggregator` /
  `grey_literature_aggregator`; fixed order OpenAlex → Overton.
- Per-backend error isolation inside `acquire_sources`; `search.executed` per attempted call
  with `status`/`error`; coverage record always written; `component.failed` reserved for
  infrastructure errors.
- Adequacy: any backend error → `inadequate`; `acquired + already_acquired == 0` →
  `inadequate`; empty-but-successful backend ≠ inadequate. `verdict_origin="model"`.
- Dedup (project-scoped): `backend_record_id` | normalized DOI (lowercase bare) | content
  hash, via `source_snapshot.metadata` JSONB lookups joined through `project_source_snapshot`.
- Snapshots: one chunk (title + best summary), `text_basis="abstract_only"`,
  `segmentation_policy="metadata_envelope_v1"`, `source_locator` (OpenAlex `id` URL; Overton
  `document_url` → `overton_url`), envelope + retained provider fields + `abstract_source`
  in metadata.
- Fixtures: sanitized `{"_meta": …, "records": […]}` package data; leak guard = `10.99999/`
  DOI prefix + `example.org` URLs, test-enforced.

## Dependency graph

```
Stage 1 (rename)                     Stage 2 (acquire)
schema.py + migration 6              schema.py (search_coverage_record) + migration 7
  └── code sweep: plan.py, harness,    ├── fixtures: data/*.json  ← recorder scripts (dev-time)
      screen/classify/appraise,        ├── acquire.py            (schema + fixtures)
      skeleton, tests, helpers         ├── plan.py registry      (1 entry)
                                       ├── harness.py            (acquire.py + run_harness param)
                                       ├── tests/helpers.py, test_compile.py
                                       ├── test_acquire.py       (all of the above)
                                       ├── skeleton.py           (harness)
                                       └── components.md §1 + specs log.md (flow-back)
```

---

## Phase 1 — The rename (separable commit)

### Task 1: Rename migration + schema.py

**Files:** `src/policy_atlas/schema.py`, `alembic/versions/<hash>_evidence_scope_rename.py`

- `schema.py`: table `screening_scope` → `evidence_scope`; column `screening_scope_id` →
  `evidence_scope_id` on `evidence_scope`, `source_screening_result`,
  `source_classification_result`, `source_appraisal_result`;
  `uq_screening_scope_id_project` → `uq_evidence_scope_id_project`. FK/index names keep
  their generic `_scope_` fragments (`fk_ssr_scope_project`, `ix_ssr_scope_status`, …) — no
  rename needed (contract). Module docstring: "fifteen tables, six alembic migrations" here;
  Phase 2 bumps it to "sixteen tables, seven" (keeps each commit's claim true —
  plan-review finding 5).
- Migration 6: `op.rename_table("screening_scope", "evidence_scope")`;
  `op.alter_column(..., new_column_name="evidence_scope_id")` ×4; constraint renames via
  `ALTER TABLE … RENAME CONSTRAINT` for `uq_screening_scope_id_project` **and the
  `screening_scope_pkey` primary-key name → `evidence_scope_pkey`** (plan-review finding 6 —
  Postgres does not rename it with the table). Downgrade reverses all. ⚠️ Postgres
  auto-renames nothing else; FK constraints referencing the renamed table/columns keep
  working by OID — no touch needed.

**Acceptance:** migration roundtrip clean; `make verify` red only on code still using the old
name (fixed in Task 2 before the phase commit).

**Estimated scope:** M (2 files)

### Task 2: Code + test sweep

**Files:** `plan.py` (`Plan`/`Config` field `screening_scope_id` → `evidence_scope_id`;
registry `requires` values ×3), `harness.py` (import, scope query, config attr, error
message), `screen.py`/`classify.py`/`appraise.py` (imports, column refs, **event payload key
`"screening_scope_id"` → `"evidence_scope_id"`** in source.screened/classified/appraised),
`skeleton.py`, `tests/helpers.py`, `test_screen.py`, `test_classify.py`, `test_appraise.py`,
`test_compile.py`, **`test_schema.py` (hard-codes `"screening_scope"` in its
schema-existence test — plan-review finding 2)**, `test_harness.py` (if it references the
name), `ingest.py`/`fixtures.py` (check — likely untouched). Sweep check:
`grep -ri screening_scope src/ tests/` returns nothing — **`alembic/` is exempt**
(pre-rename migrations legitimately contain the old name; plan-review finding 4 — only the
new migration is reviewed by intent).

**Estimated scope:** M (mechanical, ~12 files)

### Checkpoint — Phase 1
- [ ] `make verify` green; `grep -ri screening_scope src/ tests/` returns nothing
      (`alembic/` and historical `docs/tasks/**` exempt); **commit** ("rename, no
      behaviour change").

---

## Phase 2 — Coverage-record schema

### Task 3: `search_coverage_record` + migration 7

**Files:** `schema.py` (new table per the contract block: 10 columns, `fk_scov_scope_project`
+ `fk_scov_run_project` composite FKs, `uq_scov_run`, five named check constraints incl.
`ck_scov_filters_object`), `alembic/versions/<hash>_search_coverage_record.py`.

### Task 4: Table-count assertions 15 → 16

`tests/test_screen.py`, `tests/test_classify.py`, **and `tests/test_appraise.py`** (006's
"two files" precedent is stale — 006 itself added a third count assertion at
`test_appraise.py:77-78`; plan-review finding 1). Also bump the schema.py module docstring
to "sixteen tables, seven alembic migrations" here (staged from Phase 1).

### Checkpoint — Phase 2
- [ ] `make verify` green; both migrations roundtrip clean (downgrade -2 / upgrade head).

**Estimated scope:** S

---

## Phase 3 — Fixtures + recorders (dev-time network, keys from `.env`)

### Task 5: Recorder scripts + committed sanitized fixtures

**Files:** `scripts/record_openalex_fixtures.py`, `scripts/record_overton_fixtures.py`
(stdlib-only: `urllib` + `json`; each fetches raw → gitignored
`scripts/recordings/` → sanitizes → writes `src/policy_atlas/data/openalex_works.json` /
`overton_documents.json`), `.gitignore` (+ `scripts/recordings/`).

- OpenAlex: keyword form `filter=title_and_abstract.search:<query>` (+ key if
  `OPENALEX_API_KEY` set — anonymous search is rate-limited under load, observed
  2026-07-05); Overton: semantic `squery` (v2 production mode), 1 req/s honoured.
- Sanitizer (inline in each script): keep structure/nesting/nullability; fabricate values;
  DOIs → `10.99999/…`; URLs → `https://example.org/…`; inverted-index tokens fabricated but
  positions/multi-position structure preserved; `_meta` block written (query, date, backend,
  mode, sanitizer version, quirk-coverage list).
- **Run both once** (dev-time, manual — needs `OVERTON_API_KEY` in `.env`); verify quirk
  coverage per rubric item 9; commit only the sanitized files.
- Package data: `src/policy_atlas/data/` ships in the wheel — hatchling includes package-dir
  files by default; **verify with `make build` + a wheel listing** (risk table).

**Estimated scope:** M (2 scripts ~120 lines each + 2 data files)

---

## Phase 4 — `acquire.py`

### Task 6: Module

**Files:** `src/policy_atlas/acquire.py` — `AcquireContext`, `SearchBackend` (Protocol),
`OpenAlexFixtureBackend`, `OvertonFixtureBackend` (load package data via
`importlib.resources`), private mapping helpers (`_reconstruct_abstract`,
`_map_openalex_work`, `_map_overton_document`, `_normalize_doi`), `acquire_sources`.
Google-style docstrings on the public surface.

**Shape of `acquire_sources`** (contract §Python, adversarial-adjudicated):
1. Pre-load the project's existing identity keys in one query (backend_record_ids, DOIs,
   content hashes from `source_snapshot.metadata` + `content_hash` joined through
   `project_source_snapshot` for this project) — dedup lookups are then in-memory set
   checks; also dedup **within** the call's own result stream.
2. Per backend (fixed order), error-isolated `backend.search(intent)`; `search.executed`
   event per attempt (`status`/`error`/`result_count`).
3. Per usable record: envelope + chunk text; three-guard skip check → `already_acquired`;
   else insert `source_snapshot` + one `chunk` + `project_source_snapshot`
   (`origin="acquired"`, `run_id`) — reuse `ingest.py`'s hashing conventions
   (`grounding.content_hash`) but not `ingest_upload` itself (different locator/origin/
   metadata semantics; a shared private helper only if the plan-reviewer finds real
   duplication).
4. Coverage record (always); verdict per the adequacy rule.
5. Return the contracted counts dict (totals + `by_backend` with `status`/`error`).

**Estimated scope:** L (~250 lines; the two mappings are most of it)

### Checkpoint — Phase 4
- [ ] Module imports clean; unit-level mapping tests (part of Task 9, may be written first
      TDD-style against the committed fixtures).

---

## Phase 5 — Wiring

### Task 7: Registry, harness, skeleton

**Files:**
- `plan.py` — `"acquire": {"requires": ["evidence_scope_id"]}`.
- `harness.py` — `run_harness` gains `search_backends: list[SearchBackend] | None = None`
  (approved gated change 3), default `[OpenAlexFixtureBackend(), OvertonFixtureBackend()]`
  resolved inside `run_harness`, carried in `HarnessState` (the `provider` pattern);
  `_run_acquire` binds it: build the partial `sources_fn` from state, then delegate to
  `_run_scope_component` (its existing scope-load / started / completed / failed shape fits
  acquire unchanged). Graph wiring: `add_node("acquire", …)` + `"acquire"` conditional edge
  + `add_edge("acquire", "finish")`.
- `skeleton.py` — acquire runs **first** (before screen) on the same scope; log per-backend
  counts + screen-basis distribution after screen. The existing synthetic upload stays (mixed
  corpus); acquired fixture records classify as Unknown → `skipped_unknown` at appraise
  (honest, logged).

### Task 8: `test_compile.py` + `tests/helpers.py`

- Compile: `"acquire"` valid with scope id; rejected without; unknown component still
  rejected (mirror 006's pair).
- `delete_project_data`: add `search_coverage_record` early (it FKs scope + runs), **and
  fix the existing FK-unsafe ordering** (plan-review finding 3): the helper currently
  deletes `runs` before `project_source_snapshot`, but `project_source_snapshot.run_id`
  FKs `runs.run_id` — upload rows carry `run_id=NULL` so it never bit; acquired rows set
  `run_id` and would make cleanup explode. New order: result tables →
  `search_coverage_record` → `event_log` → `project_source_snapshot` → `runs` →
  `evidence_scope` → … (exact order verified against schema FKs at implement time; a test
  seeds acquired rows then deletes).

**Estimated scope:** M

### Checkpoint — Phase 5
- [ ] `make verify` green; `python -m policy_atlas.skeleton` shows
      acquire → screen → classify → appraise with per-backend counts.

---

## Phase 6 — Test suite + spec flow-back

### Task 9: `test_acquire.py`

The contract's test list, grouped (~28 cases): table count 16 · abstract reconstruction
(structurally real inverted index; empty/missing) · per-backend envelope mapping (incl.
snippet→llm_description fallback, `keyed_other_identifiers.doi[0]`, string-or-list
authors/topics, empty-string-as-absent, no-title → `skipped_unusable`) · `abstract_source`
four cases · retained provider fields (URL/OA block presence) · snapshot round-trip
(origin/run_id/text_basis/one chunk/segmentation_policy/content-hash/`source_locator`) ·
three identity guards separately + DOI normalization forms · rerun idempotency + counting
invariant (per backend and total, both calls) · cross-project isolation · coverage record
(one per run; four verdict cases incl. throwaway raising/empty backends; five named check
constraints; cross-project FK; `uq_scov_run`) · error isolation (`status="error"` event,
healthy backend ingests, `component.completed`) · `search.executed` + `source.acquired`
payloads · harness round-trip (`Plan(component="acquire")`) · downstream full-chain over
fixtures (screen `title_only` fail-open on abstract-less; classify Unknown; appraise
`skipped_unknown`) · `delete_project_data` removes coverage records · fixture leak guard
(`10.99999/`, `example.org`, `_meta` present) · zero-egress guard (acquire.py source text
contains no http-client import; recorder scripts not imported by the package).

**Estimated scope:** L (~400 lines)

### Task 10: Spec flow-back (approved with the contract)

- `components.md` §1 — one line: v3.0 acquire snapshots the metadata envelope as
  text-in-hand (`text_basis="abstract_only"`); full-text fetch + Tier-0 ingestion remain
  post-screen.
- `docs/specs/log.md` — dated entry referencing task 007.
- `make okf-validate` green.

### Checkpoint — Phase 6 (final)
- [ ] `make verify` fully green; skeleton exits 0; both migrations roundtrip;
      `/verify` drives the end-to-end flow (exact command into verification.md).

### Step-8 obligations (after the review stack, in the PR)

`docs/deferred.md` entries per the contract's list (live backends + v2-lesson requirements ·
Arm-B agentic loop with R&D pointers · backend-scope selection seam · Overton semantic/filters
· thin-base re-search · cross-project dedup + fuzzy near-dup · injection-screening posture ·
slice-008 full-text notes) · `docs/knowledge/` learning if any survives review ·
`docs/agentic-ops/` point-in-time claims (environment.md header, readiness.md line) ·
**living-doc rename + landing sweep** (plan-review finding 7): update `screening_scope`
mentions in `docs/deferred.md` and `docs/knowledge/*` (they describe the *current* system;
historical `docs/tasks/**` artifacts stay untouched), and rewrite `docs/deferred.md`'s
"`search_coverage_record` — deferred to the acquire slice" entry, which this slice lands ·
**downstream-component seams surfaced by the API exploration** (user prompt, 2026-07-05):
LLM-screen tool should read `abstract_source` (lower confidence on provider-LLM summaries;
decide non-English handling) · classify tool should consume structured provider priors
(`record_type`, Overton `source.type`/`organisation_type`, provider topics) to cut
Unknowns on acquired docs — classification quality gates appraisal coverage ·
`is_retracted` retained-but-unread: lands as a visible flag in the deferred appraisal
second pass (flag-not-block) · small-sample penalty deferral now evidence-backed (neither
API ships sample size).

---

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Recorder can't fetch (rate limits, key issues) at fixture-creation time | Blocks Phase 3 | OpenAlex: key from `.env` or retry off-peak (anonymous limit observed 2026-07-05); Overton key already in `.env`; recorders are re-runnable; fixtures committed once, then network never needed again |
| Package data not shipped in wheel (hatchling config) | Import error in built dist | Verify with `make build` + wheel listing at Phase 3; add explicit `[tool.hatch.build]` include only if default misses it |
| Rename sweep misses a payload key or test string | Red verify or silent old key | `grep -ri screening_scope src/ tests/` gate at the Phase-1 checkpoint; event-payload tests assert the new key |
| `ALTER TABLE … RENAME CONSTRAINT` syntax/support | Migration failure | Postgres-native since 9.2; roundtrip-tested both directions |
| Dedup preload query shape (JSONB `->>` over all project snapshots) | Slow only at scale | Fine for v3.0 corpus sizes; `ponytail:` comment naming the index-later upgrade path |
| `_run_scope_component` fit for acquire | Wiring churn | Verified against as-built code: its scope-load/events shape fits; only `sources_fn` binding differs (state-bound partial) |

## Plan-phase adversarial review — findings & adjudication (Codex, 2026-07-05)

Seven findings, all verified against the repo; all adopted:
1. `test_appraise.py` also holds a table-count assertion (006's "two files" precedent was
   stale): **adopted** — Task 4 lists three files.
2. `test_schema.py` hard-codes `"screening_scope"`: **adopted** — added to the Task-2 sweep.
3. `delete_project_data` deletes `runs` before `project_source_snapshot`, FK-unsafe once
   acquired rows set `run_id` (uploads carry NULL, so it never bit): **adopted** — Task 8
   reorders the helper + a seeded-delete test.
4. The `grep` gate over `alembic/` is impossible (pre-rename migrations legitimately carry
   the old name): **adopted** — gate scoped to `src/ tests/`; new migration reviewed by
   intent.
5. Docstring count "set once" contradicted the separable rename commit: **adopted** —
   staged (six migrations at Phase 1, seven at Phase 2).
6. `screening_scope_pkey` not renamed by `rename_table`: **adopted** — explicit
   `RENAME CONSTRAINT` → `evidence_scope_pkey` in migration 6.
7. Living docs (`docs/deferred.md`, `docs/knowledge/*`) still use the old name, and
   deferred.md still lists `search_coverage_record` as deferred-to-acquire: **adopted** —
   step-8 living-doc sweep added; historical `docs/tasks/**` exempt.

## Open questions

None — all design decisions fixed in the approved contract; recorder runs need the
`OVERTON_API_KEY` already present in `.env` (confirmed 2026-07-05).
