# Task contract: 006-appraise

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** review complete; PR open ([#9](https://github.com/nestauk/policy_atlas/pull/9), 2026-07-03) — awaiting human review + merge.  
> Contract approved (before planning): 2026-07-03 · Shabeer Rauf (design decisions 1–4 + rubric
> mapping + SCORE_LABELS set confirmed in review).  
> Plan approved (before implementation): 2026-07-03 · Shabeer Rauf ("run task 006
> implementation" after plan-phase adversarial review adjudicated).  
> ADR: none.

## Goal

Add the `appraise` component — per-document evidence-hierarchy score over the classified set.
For each source whose `source_classification_result.primary_evidence_type` has a standing in
the evidence hierarchy, derive a `quality_score` (1–5, **5 = strongest** — v2's expert-calibrated
five-point rating carried forward) via the **default document-type rubric**, and persist it with the
**`rubric_version`** that produced it (provenance travels with each appraisal, per spec).
Results are scope-scoped in `source_appraisal_result`, same shape as screen/classify.

Unlike screen and classify, the v3.0 light pass is **not a stub standing in for an LLM tool**:
the spec defines it as a cheap, document-type-based tier (≈ v2's evidence-strength stage carried
forward), which is inherently deterministic — the appraisal checks the document's classification
against its standing in the evidence hierarchy and maps accordingly. The deferred seams are the
*steerable* rubric (plan-compiled, user-adjustable hierarchy) and the full-text second pass —
not "the real appraise".

## Deliverable

A PR on `task/006-appraise` → `dev` that:
- Adds a `source_appraisal_result` table + Alembic migration.
- Ships `appraise.py` with `AppraiseContext`, `AppraiseResult`,
  `DEFAULT_RUBRIC` / `DEFAULT_RUBRIC_VERSION`, `SCORE_LABELS`, and `appraise_sources()`.
- Registers `"appraise"` in `COMPONENT_REGISTRY` (no new Plan/Config fields —
  `screening_scope_id` already exists).
- Wires `appraise` into the harness; updates `skeleton.py` to demonstrate
  screen → classify → appraise.
- One-line spec clarification in EB components §4 (appraisal coverage — see decision 2)
  + `log.md` entry.
- Passes `make verify` (test · typecheck · lint · build) — all green.

## Read first

- [EB components §4 — appraise](../../specs/capabilities/evidence-base/components.md)
- [EB capability](../../specs/capabilities/evidence-base/capability.md) — component chain, per-doc fan-out
- [System data-model](../../specs/system/data-model.md) — quality tier as derived structured column
- [System plan-as-object](../../specs/system/plan-as-object.md) — appraisal tier read by the use-face policy (context, later slice)
- [System execution-orchestration](../../specs/system/execution-orchestration.md) — per-doc fan-out
- [docs/deferred.md](../../deferred.md) — appraisal seams already recorded (two-stage pass, relative-to-feasible, modifier-tag dimensions)

## Scope

### Design decisions embedded here (approve or flip at this gate)

1. **Appraise reads the classified set.** The rubric is document-type-based;
   `primary_evidence_type` *is* its input (classify spec names it the "routing/appraisal
   key"). `screening_scope_id` remains the scoping key because classification rows are per
   `(scope, source)` — selecting by scope *is* selecting the classified set; chain continuity,
   not screening semantics. Relevant-but-unclassified rows are not appraised — counted and
   reported as `unclassified`.
2. **Non-evidence and Unknown are skipped-and-counted, not appraised.** A 1–5 hierarchy score
   has no honest value for a document that isn't evidence or whose type is unknown — any number
   would pollute tier-threshold queries (the use-face policy's "must meet tier X"). The
   mechanism: **the rubric's domain defines appraisability** — `DEFAULT_RUBRIC` maps only the
   7 evidence types with a hierarchy standing; types absent from it are skipped and reported
   (`skipped_non_evidence`, `skipped_unknown`). Unknown stays kept-and-eligible; the deferred
   "resolve Unknowns on full text" seam re-classifies and then appraises them. Spec flow-back:
   components.md §4 "over all screened-in" gets a one-line clarification (appraisal covers
   classified evidence types; Non-evidence/Unknown skipped-and-counted) + a `log.md` line —
   approved together with this contract.
3. **Score vocabulary: integers 1–5, 5 = strongest** — v2's five-point evidence-hierarchy
   rating carried forward unchanged (human decision, 2026-07-03: the tiers were
   expert-calibrated in v2; migrating v2 → v3, don't churn them; named labels rejected for
   now). Mapping confirmed against the v2 hierarchy (user, 2026-07-03; public reference:
   [Nesta blog — five lessons from building evidence-strength scoring](https://www.nesta.org.uk/blog/five-lessons-from-building-evidence-strength-scoring-into-an-ai-policy-tool/)):
   - 5 — Systematic Review and Meta-Analysis
   - 4 — RCTs and Quasi-Experimental Studies
   - 3 — Observational Research Studies
   - 2 — Modelling & Simulation · Policy Syntheses & Guidance Documents · Qualitative & Contextual Evidence
   - 1 — Expert Opinion and Commentary

   v2 also applied a **−1 penalty for causal studies with sample size < 100**; that needs
   sample size, which is not in v3.0's acquire-stage metadata — deferred with the richer
   appraisal pass (recorded in `docs/deferred.md`), not silently dropped.
4. **One appraisal per (scope, source) in v3.0.** The unique constraint blocks re-appraisal
   under a new rubric version; the re-runnable second-pass seam relaxes it to
   `(scope, source, rubric_version)` when it lands — recorded in `docs/deferred.md`.

### Schema

**New table: `source_appraisal_result`**

```
source_appraisal_result_id   UUID         PK
screening_scope_id           UUID         NOT NULL
project_source_snapshot_id   UUID         NOT NULL
project_id                   UUID         NOT NULL   -- denormalized; cross-project guard
appraised_by_run_id          UUID         NOT NULL
quality_score                SMALLINT     NOT NULL   -- 1..5, 5 = strongest (v2 rating)
rubric_version               TEXT         NOT NULL   -- provenance: rubric travels with each appraisal
appraised_at                 TIMESTAMPTZ  NOT NULL
```

Three composite FKs (same pattern as `source_classification_result`):

```
ForeignKeyConstraint(
    ["screening_scope_id", "project_id"],
    ["screening_scope.screening_scope_id", "screening_scope.project_id"],
    name="fk_sar_scope_project",
)
ForeignKeyConstraint(
    ["project_source_snapshot_id", "project_id"],
    ["project_source_snapshot.project_source_snapshot_id",
     "project_source_snapshot.project_id"],
    name="fk_sar_pss_project",
)
ForeignKeyConstraint(
    ["appraised_by_run_id", "project_id"],
    ["runs.run_id", "runs.project_id"],
    name="fk_sar_run_project",
)
```

Additional constraints:

```
UniqueConstraint("screening_scope_id", "project_source_snapshot_id",
                 name="uq_sar_scope_source")
Index("ix_sar_scope_score", "screening_scope_id", "quality_score")
CheckConstraint("quality_score BETWEEN 1 AND 5", name="ck_sar_quality_score")
```

**Deliberately no FK to `source_classification_result`** (adversarial-review finding 1,
adjudicated): a composite FK onto classification's `(screening_scope_id,
project_source_snapshot_id)` unique key would DB-enforce "only classified rows are appraised",
but it would harden the schema against the recorded re-run relaxation seams (both result
tables' unique constraints are slated to gain `rubric_version`-style columns when re-run
passes land) and would break the established pattern — classify likewise has no FK onto
`source_screening_result` (rationale in `docs/deferred.md`). The invariant is guaranteed by
the read path (`appraise_sources` *selects from* `source_classification_result`) and covered
by the round-trip tests.

### Python

**`appraise.py`** — new module:

```python
DEFAULT_RUBRIC_VERSION = "v2-hierarchy-v1"

# The v3.0 default rubric: primary_evidence_type → quality_score (5 = strongest),
# v2's expert-calibrated five-point evidence-hierarchy rating carried forward.
# Its domain defines appraisability: types absent from it (Other/Non-evidence,
# Unknown) are skipped-and-counted, never scored. Keys come from EVIDENCE_TYPES
# (schema.py); a test enforces the domain is exactly EVIDENCE_TYPES minus the two
# non-appraisable types.
DEFAULT_RUBRIC: dict[str, int] = {
    "Systematic Review and Meta-Analysis":   5,
    "RCTs and Quasi-Experimental Studies":   4,
    "Observational Research Studies":        3,
    "Modelling & Simulation":                2,
    "Policy Syntheses & Guidance Documents": 2,
    "Qualitative & Contextual Evidence":     2,
    "Expert Opinion and Commentary":         1,
}

# Presentation copy only — applied at read time (UI, reports, exports); never persisted,
# never in event payloads (a stored label could drift from its score; rewording is a
# one-dict change with no migration). Policy team owns the wording — retune freely.
SCORE_LABELS: dict[int, str] = {
    5: "Very strong",
    4: "Strong",
    3: "Moderate",
    2: "Limited",
    1: "Weak",
}

@dataclass
class AppraiseContext:
    scope_id: uuid.UUID
    intent: str
    context: dict          # from screening_scope.context JSONB

@dataclass
class AppraiseResult:
    quality_score: int           # 1..5, 5 = strongest
    rubric_version: str          # always DEFAULT_RUBRIC_VERSION in v3.0
```

Public module/classes/functions carry Google-style docstrings per AGENTS.md (do not mirror
classify's docstring gap on its dataclasses).

No `_stub_appraise` and no metadata sentinels: the score is a direct `DEFAULT_RUBRIC` lookup on
`primary_evidence_type` (tests steer it through the existing classify sentinels). Types outside
the rubric's domain are the skip path, not an error; for types inside it the DB check constraint
on `primary_evidence_type` plus the rubric-domain test make the lookup infallible.

`appraise_sources(conn, *, project_id, run_id, context: AppraiseContext) -> dict` — loads all
`source_classification_result` rows with `screening_scope_id=context.scope_id` for the project,
joined to `project_source_snapshot` (for `source_snapshot_id` and the project guard), excluding
rows already appraised for the scope (idempotency, same `~exists()` pattern as classify). Per
row: if `primary_evidence_type in DEFAULT_RUBRIC`, insert into `source_appraisal_result` and
emit one `source.appraised` event; otherwise count the skip. Returns:

```
{"appraised": n,
 "by_score": {5: k, 3: k},        # sparse — only observed scores, matching classify's by_type
 "skipped_non_evidence": a,
 "skipped_unknown": b,
 "already_appraised": m,
 "unclassified": u}
```

Counting semantics (rerun-stable): `appraised` counts rows inserted *this call*;
`already_appraised` counts pre-existing appraisal rows for the scope; `skipped_non_evidence`,
`skipped_unknown`, and `unclassified` are recomputed from current state on every call (a rerun
reports the same skip counts, `appraised == 0`). Invariant:
`appraised + already_appraised + skipped_non_evidence + skipped_unknown` = total
`source_classification_result` rows for the scope.

`unclassified` is the count of `source_screening_result` rows for the scope with
`status='relevant'` that have no `source_classification_result` row — appraise does not process
them; it reports them so a skipped-classify misconfiguration is visible.

JSON representation note: `by_score` has **int keys in the Python return** but **string keys
once serialized into the JSONB `component.completed` payload** (JSON object keys are strings —
`{"5": 2}`); the harness test asserts the string-keyed form.

**`source.appraised` event payload** (one per appraised document):

```json
{
  "source_snapshot_id": "<uuid>",
  "project_source_snapshot_id": "<uuid>",
  "screening_scope_id": "<uuid>",
  "quality_score": 5,
  "rubric_version": "v2-hierarchy-v1"
}
```

No event for skipped rows — the component-level `component.completed` payload carries the
skip counts.

**`plan.py`** — add `"appraise"` to `COMPONENT_REGISTRY`:

```python
COMPONENT_REGISTRY: dict[str, dict[str, list[str]]] = {
    "echo":     {"requires": ["source_snapshot_id"]},
    "screen":   {"requires": ["screening_scope_id"]},
    "classify": {"requires": ["screening_scope_id"]},
    "appraise": {"requires": ["screening_scope_id"]},
}
```

No new fields on `Plan`/`Config`. The spec's plan-carried steerable rubric is a deferred seam —
v3.0 uses the code-level default only, identified by `rubric_version`.

**`harness.py`** — add `_run_appraise` node (mirror `_run_classify`):
1. Load `screening_scope` row from DB using `config.screening_scope_id`.
2. Construct `AppraiseContext(scope_id=..., intent=..., context=...)`.
3. Emit `component.started(component="appraise")`.
4. Call `appraise_sources(conn, project_id=project_id, run_id=run_id, context=ctx)`.
5. Emit `component.completed` payload: `{component, appraised, by_score,
   skipped_non_evidence, skipped_unknown, already_appraised, unclassified}`.

Wire into graph: add `"appraise"` to conditional edges.

**`skeleton.py`** — run screen, then classify, then appraise with the same
`screening_scope_id`.

**`tests/helpers.py`** — extend `delete_project_data`: add `source_appraisal_result` (before
`source_classification_result`) in FK-safe order.

**Spec flow-back** — `docs/specs/capabilities/evidence-base/components.md` §4: clarify
"over all screened-in" to state the v3.0 pass scores classified **evidence** types;
Non-evidence and Unknown are skipped-and-counted (Unknown re-enters via the deferred
full-text resolution seam). One line + a `log.md` entry.

**`test_appraise.py`** — new file, covering:
- Table count is 15 (one new table).
- Rubric domain: `set(DEFAULT_RUBRIC) == set(EVIDENCE_TYPES) - {"Other (Non-evidence documents)",
  "Unknown / Insufficient information"}`; every value in `range(1, 6)`; mapping monotone with
  the v2 ordering (SR&MA = 5, Expert Opinion = 1).
- `SCORE_LABELS` domain is exactly `{1, 2, 3, 4, 5}` (wording itself is untested — it's copy).
- `appraise_sources` round-trip: appraisal rows present for classified evidence sources; score
  matches the rubric for each seeded `primary_evidence_type` (via classify's existing stub
  sentinels).
- Non-evidence source: no appraisal row; `skipped_non_evidence` counts it.
- Unknown source (classify's default): no appraisal row; `skipped_unknown` counts it.
- Relevant-but-unclassified rows are not appraised; `unclassified` counts them.
- Idempotency: second call → `appraised == 0`, `already_appraised == n`, no duplicate rows.
- Mixed rerun: with Non-evidence/Unknown rows present, a second call reports the **same**
  `skipped_non_evidence`/`skipped_unknown` counts (recomputed, not accumulated); the counting
  invariant (`appraised + already_appraised + skipped_* = classification rows for scope`) holds
  on both calls.
- `by_score` is sparse (no zero-valued keys for unobserved scores); in the harness event payload
  its keys are strings.
- `rubric_version == "v2-hierarchy-v1"` on every persisted row.
- `appraised_by_run_id` is set correctly.
- Check constraint: `quality_score = 0` (and `6`) → `IntegrityError`.
- Cross-project FK: appraising with scope from project A, source from project B → `IntegrityError`.
- Unique constraint: duplicate `(screening_scope_id, project_source_snapshot_id)` → `IntegrityError`.
- Harness round-trip: `Plan(component="appraise")` → result rows in DB, events emitted.
- `source.appraised` event payload: keys and values match spec; no event for skipped rows.
- `delete_project_data` removes `source_appraisal_result` rows; no rows remain after deletion.

Updates to existing tests:
- `tests/test_screen.py` and `tests/test_classify.py` — table-count assertions 14 → 15
  (the active count assertions live in those files, not `test_schema.py` — plan-review
  finding, 2026-07-03).
- `test_compile.py` — `"appraise"` valid with a scope id; `Plan(component="appraise")`
  without `screening_scope_id` rejected; unknown component still rejected.

### Out of scope

- Steerable / plan-carried rubric (orchestrator compiles a provisional hierarchy into the plan,
  user inspects/adjusts) — deferred seam; v3.0 is default-rubric-only.
- Typed dimensions (`dimensions` column/bag) — nothing populates or reads it in v3.0; it arrives
  with the full-text second pass (methods quality / risk-of-bias, modifier-tag-driven) — ⏸.
- Full-text second appraisal pass on the selected subset — ⏸.
- v2's small-sample penalty (−1 for causal studies with n < 100) — needs sample size, not in
  v3.0 metadata; deferred with the richer pass — ⏸.
- Relative-to-feasible tier — ⏸.
- Cross-document roll-up (weighted strength, single-study caps) — stays out of EB's appraise.
- `Unknown` resolution on full text (re-classify → appraise) — ⏸.
- Full-text ingestion (post-appraise in the chain) and `characterise`+ — subsequent slices.
- Any LLM call or egress.

### Contract-stage adversarial review — findings & adjudication (Codex, 2026-07-03)

Six findings; none challenged the human-settled design decisions. Adjudicated by the lead:
1. No FK → classification: **documented rejection** (schema note above) — precedent-consistent,
   seam-preserving; invariant held by the read path + tests.
2. `by_score` dense vs sparse: **adopted** — sparse, matching classify's `by_type`.
3. Int keys vs JSONB: **adopted** — string keys specified/tested in the event payload.
4. Rerun skip-count semantics: **adopted** — counting semantics + invariant + mixed-rerun test.
5. `helpers.py` path: **adopted** — `tests/helpers.py`.
6. Docstring gap: **adopted** — Google-style docstrings required on the public surface.

## Constraints & approval gates

**One gated change:**

1. **Schema** — new `source_appraisal_result` table with composite FKs and check constraint
   on `quality_score`; new Alembic migration.

Plus one spec clarification (components.md §4 coverage line) — approved with this contract per
the spec-refinement flow.

No auth, egress, secrets, new pip packages, or Plan/Config interface changes (beyond adding
`"appraise"` to the existing registry).

## Public / private boundary

- Table name, column names, `AppraiseContext`/`AppraiseResult` field names, `DEFAULT_RUBRIC`,
  `DEFAULT_RUBRIC_VERSION`, `SCORE_LABELS` (structure durable; wording is tune-freely
  presentation copy), event payload keys — durable/committable.
- No source text, credentials, or egress in any committed file.

## Model route

`n/a` — deterministic rubric lookup only. No LLM call, no inference provider, no network I/O.
(The v3.0 light pass is deterministic *by design*, not as a stub — see Goal.)

## Disciplines binding this slice

- **Rubric version travels with each appraisal** — `rubric_version` NOT NULL on every row;
  the event payload carries it too.
- **Only classified rows are appraised** — `appraise_sources` reads from
  `source_classification_result` for the scope; unclassified relevant rows are counted in
  `unclassified`, never silently dropped.
- **Skip is visible, never silent** — Non-evidence and Unknown produce no score but are
  always counted (`skipped_non_evidence`, `skipped_unknown`) in the return value and the
  `component.completed` payload.
- **`Unknown` evidence type is kept-and-eligible** — skipping it here is "no hierarchy
  standing yet", not exclusion; it remains in the corpus and downstream-eligible.
- **Model only what behaves** — no `dimensions` bag, no `appraisal_rationale`, no
  per-dimension columns. The steerable-rubric machinery goes in `docs/deferred.md`, not a
  half-built column.
- **Scope-scoped** — appraisal is per `(screening_scope, source)`, consistent with
  screen/classify.

## Stop conditions

- Schema approval gate hit and not yet approved.
- Schema change beyond the one gated item above is needed.
- Scope would grow past the contract (e.g. rubric-in-plan, dimensions, full-text ingestion,
  `characterise`).
- `make verify` red with unclear root cause.
- Any code path would require a new LLM or egress call.

## Acceptance checks

- `make verify` (test · typecheck · lint · build) — green.
- All checks deterministic (no LLM, no egress). Every check is a test.
- No manual / browser checks required.

## Verification evidence expected

`verification.md` must include:
- `make verify` table with pass counts.
- Named test results from `test_appraise.py`.
- Migration roundtrip (`alembic downgrade -1` / `alembic upgrade head`) — both clean.
- Table count: `assert len(metadata.tables) == 15`.
- Check constraint coverage: at least one test for `ck_sar_quality_score`.
- Cross-project FK test: one test confirming cross-project insert is rejected.
- End-to-end command: harness invoked with `component="appraise"`, result rows visible in DB.
- Diff summary.
- Public-safety confirmation.
- Deferred seams recorded in `docs/deferred.md` (steerable rubric; unique-constraint relaxation
  for re-appraisal; typed dimensions with the second pass; v2's small-sample −1 penalty;
  appraisal→classification FK deliberately absent — mirror the existing classify→screen entry).

## Risk tier & review focus

**Tier 3** — schema change (new table + check constraint + composite FKs).

Review focus:
- **Correctness:** appraise reads the classified set; score comes from `DEFAULT_RUBRIC`;
  rubric domain (7 appraisable types) and v2-ordering monotonicity are test-enforced;
  Non-evidence/Unknown skipped-and-counted, never scored.
- **Provenance:** `rubric_version` persisted on every row and carried in every event.
- **Cross-project integrity:** three composite FKs enforce same-project; cross-project insert
  test covers it.
- **Migration:** new table with composite FKs and check constraint roundtrips clean.
- **Registry:** `"appraise"` in `COMPONENT_REGISTRY` with correct `requires`; unknown component
  still rejected.
- **Scope:** no LLM, no rubric-in-plan, no dimensions column, no full-text pass, no roll-up.
