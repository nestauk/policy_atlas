# Verification: 006-appraise

Evidence for one slice. Filled at verify (step 6); **Review findings** + **Rubric status**
added after the review stack (step 7).

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make test` | pass | 106 passed (84 baseline + 22 new/updated), 17 warnings (pre-existing SAWarning) |
| `make typecheck` | pass | mypy: no issues in 27 source files |
| `make lint` | pass | ruff: all checks passed |
| `make build` | pass | sdist + wheel built |
| `make okf-validate` | pass | runs inside `make verify`; spec frontmatter untouched |

`make verify` runs all of the above — fully green on the final tree.

## Checks beyond the build

- **Deterministic tests** — `tests/test_appraise.py` (19 test functions, 20 cases with the
  parametrized check constraint; count corrected by the contract verifier, step 7), all passing:
  - Table count 15 (`test_table_count`).
  - Rubric domain = `EVIDENCE_TYPES` − {Non-evidence, Unknown}; values ⊆ 1..5
    (`test_rubric_domain_is_evidence_types_minus_non_appraisable`).
  - Rubric matches the v2 hierarchy exactly — SR=5, RCT=4, Obs=3, Modelling/Policy/Qual=2,
    Expert=1 (`test_rubric_matches_v2_hierarchy_exactly`).
  - `SCORE_LABELS` domain = {1..5}; wording untested (presentation copy)
    (`test_score_labels_domain`).
  - Full-chain round-trip via classify sentinels; scores match rubric
    (`test_appraise_sources_round_trip_via_classify`).
  - Non-evidence / Unknown skipped-and-counted, no rows
    (`test_non_evidence_skipped_and_counted`, `test_unknown_skipped_and_counted`).
  - Relevant-but-unclassified counted, not appraised (`test_unclassified_counted_not_appraised`).
  - Idempotent rerun: `appraised == 0`, `already_appraised == n`, no duplicates
    (`test_appraise_sources_idempotent_rerun`).
  - Mixed rerun: skip counts recomputed (identical across calls); counting invariant
    `appraised + already_appraised + skipped_* = classification rows` holds on both calls
    (`test_mixed_rerun_skip_counts_stable_and_invariant_holds`).
  - `by_score` sparse — no zero-valued keys (`test_by_score_is_sparse`).
  - `rubric_version == "v2-hierarchy-v1"` on every row (`test_rubric_version_persisted_on_every_row`).
  - `appraised_by_run_id` set (`test_appraised_by_run_id`).
  - Check constraint `ck_sar_quality_score`: scores 0 and 6 → `IntegrityError`
    (`test_ck_quality_score_bounds[0]`, `[6]`).
  - Cross-project composite FK: scope from project A + source from project B → `IntegrityError`
    (`test_cross_project_fk_rejected`).
  - Unique `(scope, source)` duplicate → `IntegrityError` (`test_uq_scope_source_duplicate`).
  - Harness round-trip: `Plan(component="appraise")` → row in DB, `component.completed` payload
    with **string-keyed** `by_score` (`{"5": 1}`) and all skip counts; no `source.appraised`
    event for the skipped row; run `succeeded` (`test_harness_appraise_component`).
  - `source.appraised` payload exact-match: keys and values per contract, `quality_score` int,
    `rubric_version` string (`test_source_appraised_event_payload`).
  - `delete_project_data` removes appraisal rows (`test_delete_project_data_removes_appraisal`).
  - `tests/test_compile.py`: `"appraise"` valid with scope id; missing `screening_scope_id`
    rejected; unknown component still rejected (pre-existing tests).
- **Migration roundtrip** — `uv run alembic upgrade head` → `downgrade -1` → `upgrade head`:
  all three clean; `alembic current` = `d6a1c4e9b2f7 (head)`.
- **AI evals** — none (deterministic rubric lookup; no LLM, no egress — per contract).
- **Manual** — skeleton end-to-end (below): screen → classify → appraise over one scope;
  observed `appraisal_result quality_score=5 rubric_version=v2-hierarchy-v1`,
  `appraise_counts appraised=1 by_score={'5': 1} skipped_non_evidence=0 skipped_unknown=0
  already_appraised=0 unclassified=0`, `source.appraised` event in the log, exit 0.

## End-to-end command

```bash
set -a; source .env; set +a; uv run python -m policy_atlas.skeleton
```

(Loads `DATABASE_URL` for the dev DB; the harness is invoked three times — screen, classify,
appraise — with the same `screening_scope_id`; appraisal rows are queried back from
`source_appraisal_result` and logged.)

## Diff summary

Adds the `appraise` component (task 006), mirroring the classify pattern:

- `src/policy_atlas/schema.py` — new `source_appraisal_result` table (8 columns; three composite
  FKs `fk_sar_*` guarding same-project; `uq_sar_scope_source`; `ck_sar_quality_score BETWEEN 1
  AND 5`; `ix_sar_scope_score`). Deliberately **no FK** to `source_classification_result`
  (contract-adjudicated; seam-preserving — comment at the table, entry due in `docs/deferred.md`
  at step 8).
- `alembic/versions/d6a1c4e9b2f7_appraise_table.py` — migration, mirrors the classify one.
- `src/policy_atlas/appraise.py` — new module: `DEFAULT_RUBRIC` (7 evidence types → 1..5, v2
  hierarchy verbatim; domain defines appraisability), `DEFAULT_RUBRIC_VERSION = "v2-hierarchy-v1"`,
  `SCORE_LABELS` (read-time copy, never persisted), `AppraiseContext`/`AppraiseResult`,
  `appraise_sources()` (idempotent via `~exists()`; skip counts + `unclassified` recomputed per
  call; per-row `source.appraised` events; sparse `by_score`). Google-style docstrings on the
  public surface.
- `src/policy_atlas/plan.py` — `"appraise": {"requires": ["screening_scope_id"]}` in the registry.
- `src/policy_atlas/harness.py` — `_run_appraise` via the existing `_run_scope_component`
  helper; node + conditional edge + finish edge in `build_graph`.
- `src/policy_atlas/skeleton.py` — third run (appraise) over the same scope; seed metadata gains
  `_stub_systematic_review` so the demo exercises the scored path; logs appraisal rows and the
  skip counts.
- `tests/` — new `test_appraise.py`; table-count 14→15 in `test_screen.py`/`test_classify.py`;
  appraise pair in `test_compile.py`; `source_appraisal_result` first in `delete_project_data`.
- Spec flow-back (approved with the contract): coverage clarification in EB components §4 +
  dated `docs/specs/log.md` entry.
- Task artifacts: contract/plan status lines stamped (plan approved 2026-07-03).

### Review-driven changes (step 7, after the stack below)

- `appraise.py` — `project_id` added to both `~exists()` anti-join subqueries (defense-in-depth:
  previously airtight only via the composite FKs the schema comment contemplates relaxing);
  unused `structlog` logger removed.
- `skeleton.py` — the triplicated ~35-line run-bookkeeping block extracted into
  `_run_component()`; the default-less `next()` over the event log (bare `StopIteration` if the
  appraise run failed, hiding diagnostics) now defaults to `None` and warns.
- `tests/helpers.py` — `seed_screening_result` promoted from duplicated per-file helpers
  (`test_classify.py` + `test_appraise.py`).
- `tests/test_appraise.py` — mixed-rerun test now seeds a relevant-but-unclassified row and
  asserts `unclassified == 1` on both calls (rerun stability was previously unpinned).
- Net: −68 lines across `src` + `tests`; `make verify` green and skeleton e2e re-run clean
  after the changes (appraisal row `quality_score=5 rubric_version=v2-hierarchy-v1`, exit 0).

## Review findings

Review stack run 2026-07-03 in a fresh conversation (step 7, Tier 3). All reviewers read-only;
findings adjudicated by the lead. **No critical or high findings anywhere in the stack.**

- **Contract verifier** (fresh pinned agent; independently re-ran `make verify`): 16/18 rubric
  items PASS; items 16–17 pending by design (step-7/8 work). Two lows, both addressed:
  (1) verification.md over-counted `test_appraise.py` (claimed 20 functions/21 cases; actual
  19/20) — corrected above; (2) branch carries process-doc changes beyond the contract
  deliverable (`.claude/skills/task-cycle/SKILL.md` rework, `AGENTS.md` phase pointer) —
  **accepted deviation**: the AGENTS.md pointer ships with the slice by task-cycle design; the
  SKILL.md changes are process learning from running this cycle, committed separately on the
  branch, not approval-gated. Confirmed migration↔schema parity and the counting-invariant
  reasoning; noted the four deferred.md entries owed at step 8.
- **`/code-review`** (workflow, high effort; 16 agents, findings independently verified):
  one CONFIRMED bug — `skeleton.py` default-less `next()` → bare `StopIteration` when the
  appraise run fails — **fixed**. Two PLAUSIBLE latent items **recorded, not fixed** (both
  pre-existing patterns shared with screen/classify, out of slice scope): the harness
  `except` handler appends `component.failed` on a possibly-aborted transaction (run left
  `running`, root cause masked); `already_appraised` counts all appraisal rows for the scope,
  which double-counts if a source is ever re-classified under the deferred re-run seam — noted
  for that seam's deferred.md entry. Cleanup findings: skeleton triplication **fixed**;
  test-seeder duplication **fixed**; per-row insert/event round trips (**rejected** —
  precedent-consistent, serial single-writer model, v3.0 scale), shared `ScopeContext`
  dataclass (**rejected** — `AppraiseContext` is contract-named public surface; consolidation
  would touch screen/classify public interfaces, a gated change), `AppraiseResult` ceremony
  (**rejected** — contract-named deliverable), triplicated table-count assertion (**rejected**
  — contract-pinned test list; plan-review already placed the active assertions).
- **`/security-review`**: no findings (SQL injection, tenant boundary, code execution,
  secrets, data exposure, egress all clean; the one raw `sa.text()` is a parameterized
  test-only FK-violation probe).
- **Adversarial review** (Tier 3, two heterogeneous reviewers):
  - *Codex (read-only rescue brief)*: no runtime/logic defects in scoring, skip-and-count,
    the counting invariant, migration↔schema, or event payloads. Two lows duplicating the
    contract verifier: deferred.md entries owed (step 8) and the process-doc ride-along
    (adjudicated above).
  - *Claude code-reviewer subagent (five-axis; independently re-ran tests + migration
    roundtrip)*: APPROVE, no critical. Applied: unused logger removed; mixed-rerun
    `unclassified` coverage added. Rejected: runtime assert on unexpected skip types (the
    rubric-domain test + `ck_scr_primary_evidence_type` force reconciliation at CI time — a
    new type cannot reach runtime with tests green); deriving the skip-type constants from
    `EVIDENCE_TYPES` (literals are readable; a rename fails tests + check constraint loudly);
    `ORDER BY` on `appraisable_rows` (classify precedent is unordered; event-log `sequence`
    totally orders emissions). Recorded as hygiene debt outside this slice: the
    `conn.rollback(); conn.begin()` pattern in constraint tests fights the fixture
    (pre-existing SAWarnings, inherited from test_classify).
  - *Security auditor subagent (Tier 3 audit)*: 0 critical/high/medium. Applied: `project_id`
    in both `exists()` subqueries. Recorded, not fixed (pre-existing, shared with
    screen/classify): `appraise_sources` is a silent no-op on a scope/project mismatch when
    called outside the harness (the harness validates; no write possible cross-project);
    `str(exc)` persisted in `component.failed` payloads (harness-wide pattern). Info-level:
    TOCTOU race loses loudly via `uq_sar_scope_source` (documented single-writer model);
    `rubric_version` validation belongs to the steerable-rubric seam.
- **`ponytail-review` → `/simplify`**: one candidate (`AppraiseResult` built per row then
  unpacked) — rejected, contract-mandated public surface; otherwise lean. The simplification
  actually applied came from the review stack (skeleton dedup, seeder dedup, dead logger):
  net −68 lines.

Post-fix gate: `make verify` fully green (106 passed · mypy 27 files · ruff · build ·
okf-validate) and skeleton e2e re-run clean.

**Process finding (harness):** this stack cost ≈850K subagent tokens — the `/code-review`
high-effort workflow alone 552K for one extra low-severity finding, and the two security lanes
fully overlapped. Recorded in `docs/agentic-ops/failure-log.md` (2026-07-03); step-7 economy
rules tightened in the task-cycle skill + harness.md (`/code-review` medium-only, one security
lane, ≤250K target).

## Rubric status

All 18 boxes hold. Boxes 1–15 and 18 post-review (contract verifier PASS on all, re-checked
green after the review-driven fixes; box 6's test count corrected). Box 17 (this review stack)
— done, findings above. Box 16 (deferred.md seams) — landed at step 8 against the
review-finalised code, in this PR: steerable/plan-carried rubric; `uq_sar_scope_source`
relaxation for re-appraisal (with the `already_appraised`-vs-reclassification counting
interaction flagged by `/code-review`); typed dimensions with the full-text second pass; v2's
small-sample −1 penalty; appraisal→classification FK deliberately absent; stale "appraise —
subsequent slices" line updated. Knowledge:
`docs/knowledge/rubric-domain-defines-appraisability.md` + index/log.

## Intent & assumptions

- The v3.0 light pass is deterministic **by design** (document-type-based tier), not a stub —
  no `_stub_appraise`, no metadata sentinels in `appraise.py`; tests steer via classify's
  existing sentinels upstream.
- One appraisal per `(scope, source)`; re-appraisal under a new rubric version is blocked by
  `uq_sar_scope_source` until the recorded relaxation seam lands.
- `already_appraised` is a direct pre-insert count; skip counts and `unclassified` are
  recomputed from current state every call (rerun-stable).

## Known unverified items

- `SCORE_LABELS` wording is deliberately untested (presentation copy, policy-team-owned).
- No concurrency test for two simultaneous appraise runs on one scope — the unique constraint
  makes the race lose loudly (IntegrityError), same posture as classify.

## Public safety

- No secrets, credentials, source text, or egress in any committed file. The rubric, labels,
  table/column names, and event payload keys are durable/committable per the contract.
- Skeleton output logs synthetic data only.

## Deferred work

Due at step 8 (against review-finalised code) → `docs/deferred.md`: steerable/plan-carried
rubric; unique-constraint relaxation for re-appraisal; typed dimensions with the full-text
second pass; v2's small-sample −1 penalty; appraisal→classification FK deliberately absent.
