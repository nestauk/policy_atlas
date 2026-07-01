# Task contract: 005-classify

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted — pending human approval.  
> Contract approved (before planning): _date · who_  
> Plan approved (before implementation): _date · who_  
> ADR: none.

## Goal

Add the `classify` component — per-document evidence-type classification on the
screened-in set. For each source that passed screen (`status='relevant'`), produce a
`primary_evidence_type` (closed column, routing/appraisal key) and an `open_tags`
list (open methodological/structural tags; empty in the v3.0 deterministic stub).
Results are persisted scope-scoped in `source_classification_result`, so multiple EB
runs within one project can classify the same corpus against different screening scopes.

## Deliverable

A PR on `task/005-classify` → `dev` that:
- Adds a `source_classification_result` table + Alembic migration.
- Ships `classify.py` with `ClassifyContext`, `ClassifyResult`, `_stub_classify()`,
  and `classify_sources()`.
- Registers `"classify"` in `COMPONENT_REGISTRY` (no new Plan/Config fields needed —
  `screening_scope_id` already exists).
- Wires `classify` into the harness; updates `skeleton.py` to demonstrate it.
- Passes `make verify` (test · typecheck · lint · build) — all green.

## Read first

- [EB components §3 — classify](../../specs/capabilities/evidence-base/components.md)
- [EB capability](../../specs/capabilities/evidence-base/capability.md) — Non-evidence exclusion, Unknown eligibility
- [System data-model](../../specs/system/data-model.md) — tag model, open tags
- [System execution-orchestration](../../specs/system/execution-orchestration.md) — per-doc fan-out
- [System plan-as-object](../../specs/system/plan-as-object.md) — Plan/Config compile
- [docs/deferred.md](../../deferred.md) — grey-lit granularity and open tag namespace already recorded

## Scope

### Schema

**New table: `source_classification_result`**

```
source_classification_result_id   UUID         PK
screening_scope_id                UUID         NOT NULL
project_source_snapshot_id        UUID         NOT NULL
project_id                        UUID         NOT NULL   -- denormalized; cross-project guard
classified_by_run_id              UUID         NOT NULL
primary_evidence_type             TEXT         NOT NULL
open_tags                         JSONB        NOT NULL   -- classify_sources always supplies '[]';
                                                           -- no DB-level server_default (no other
                                                           -- writer path exists for this column)
classified_at                     TIMESTAMPTZ  NOT NULL
```

Three composite FKs (same pattern as `source_screening_result`):

```
ForeignKeyConstraint(
    ["screening_scope_id", "project_id"],
    ["screening_scope.screening_scope_id", "screening_scope.project_id"],
    name="fk_scr_scope_project",
)
ForeignKeyConstraint(
    ["project_source_snapshot_id", "project_id"],
    ["project_source_snapshot.project_source_snapshot_id",
     "project_source_snapshot.project_id"],
    name="fk_scr_pss_project",
)
ForeignKeyConstraint(
    ["classified_by_run_id", "project_id"],
    ["runs.run_id", "runs.project_id"],
    name="fk_scr_run_project",
)
```

Additional constraints:

```
UniqueConstraint("screening_scope_id", "project_source_snapshot_id",
                 name="uq_scr_scope_source")
Index("ix_scr_scope_type", "screening_scope_id", "primary_evidence_type")
CheckConstraint("jsonb_typeof(open_tags) = 'array'",
                name="ck_scr_open_tags_array")
CheckConstraint(
    "primary_evidence_type IN ("
    " 'Systematic Review and Meta-Analysis',"
    " 'RCTs and Quasi-Experimental Studies',"
    " 'Observational Research Studies',"
    " 'Modelling & Simulation',"
    " 'Policy Syntheses & Guidance Documents',"
    " 'Qualitative & Contextual Evidence',"
    " 'Expert Opinion and Commentary',"
    " 'Other (Non-evidence documents)',"
    " 'Unknown / Insufficient information'"
    ")",
    name="ck_scr_primary_evidence_type",
)
```

V2 ordering (evidence strength) carried forward:
1. `Systematic Review and Meta-Analysis`
2. `RCTs and Quasi-Experimental Studies`
3. `Observational Research Studies`
4. `Modelling & Simulation`
5. `Policy Syntheses & Guidance Documents` — grey-lit (coarse; splitting is ⏸)
6. `Qualitative & Contextual Evidence`
7. `Expert Opinion and Commentary` — grey-lit (coarse; splitting is ⏸)
8. `Other (Non-evidence documents)` — excludes from `select`/`extract` downstream
9. `Unknown / Insufficient information` — kept-and-eligible

### Python

**`classify.py`** — new module:

```python
@dataclass
class ClassifyContext:
    scope_id: uuid.UUID
    intent: str
    context: dict          # from screening_scope.context JSONB

@dataclass
class ClassifyResult:
    primary_evidence_type: str   # one of the 9 closed values
    open_tags: list[str]         # empty in v3.0 stub; LLM-populated later
```

`_stub_classify(metadata: dict) -> ClassifyResult` — deterministic, zero egress.
Checks sentinels in this order; first match wins:
- `metadata.get("_stub_non_evidence")` → `ClassifyResult("Other (Non-evidence documents)", [])`
- `metadata.get("_stub_systematic_review")` → `ClassifyResult("Systematic Review and Meta-Analysis", [])`
- `metadata.get("_stub_rct")` → `ClassifyResult("RCTs and Quasi-Experimental Studies", [])`
- `metadata.get("_stub_observational")` → `ClassifyResult("Observational Research Studies", [])`
- `metadata.get("_stub_modelling")` → `ClassifyResult("Modelling & Simulation", [])`
- `metadata.get("_stub_policy_guidance")` → `ClassifyResult("Policy Syntheses & Guidance Documents", [])`
- `metadata.get("_stub_qualitative")` → `ClassifyResult("Qualitative & Contextual Evidence", [])`
- `metadata.get("_stub_expert_opinion")` → `ClassifyResult("Expert Opinion and Commentary", [])`
- else → `ClassifyResult("Unknown / Insufficient information", [])`

`classify_sources(conn, *, project_id, run_id, context: ClassifyContext) -> dict` — loads
all `source_screening_result` rows with `screening_scope_id=context.scope_id` and
`status='relevant'` for the project, joined to `project_source_snapshot` and
`source_snapshot` to select `source_snapshot.c.metadata` (the same join as
`screen_sources`), calls `_stub_classify(metadata)` per row, inserts into
`source_classification_result`, emits one `source.classified` event per row, returns:
`{"classified": n, "by_type": {"Unknown / Insufficient information": k, "Other (Non-evidence documents)": k, …}, "skipped": m}`

`skipped` is the count of `source_screening_result` rows for this scope whose `status` is
`'not_relevant'` or `'failed'` — both are skipped; the field uses the exact status strings
from `source_screening_result.status`'s check constraint (`'relevant'` · `'not_relevant'` ·
`'failed'`).

**`source.classified` event payload** (one per document):

```json
{
  "source_snapshot_id": "<uuid>",
  "project_source_snapshot_id": "<uuid>",
  "screening_scope_id": "<uuid>",
  "primary_evidence_type": "Unknown / Insufficient information",
  "open_tags": []
}
```

**`plan.py`** — add `"classify"` to `COMPONENT_REGISTRY`:

```python
COMPONENT_REGISTRY: dict[str, dict[str, list[str]]] = {
    "echo":     {"requires": ["source_snapshot_id"]},
    "screen":   {"requires": ["screening_scope_id"]},
    "classify": {"requires": ["screening_scope_id"]},
}
```

No new fields on `Plan`/`Config` — `screening_scope_id` already exists.

**`harness.py`** — add `_run_classify` node:
1. Load `screening_scope` row from DB using `config.screening_scope_id`.
2. Construct `ClassifyContext(scope_id=row.screening_scope_id, intent=row.intent, context=dict(row.context))`.
3. Emit `component.started(component="classify")`.
4. Call `classify_sources(conn, project_id=project_id, run_id=run_id, context=ctx)`.
5. Emit `component.completed` payload: `{component, classified, by_type, skipped}`.

Wire into graph: add `"classify"` to conditional edges.

**`skeleton.py`** — run screen first (to have relevant rows), then run classify with the
same `screening_scope_id`.

**`helpers.py`** — extend `delete_project_data`: add `source_classification_result`
(before `source_screening_result`) in FK-safe order.

**`test_classify.py`** — new file, covering:
- Table count is 14 (one new table).
- `_stub_classify` default → `Unknown / Insufficient information`, empty tags.
- `_stub_classify` with `_stub_non_evidence` → `Other (Non-evidence documents)`.
- `_stub_classify` with `_stub_policy_guidance` → `Policy Syntheses & Guidance Documents`.
- `classify_sources` round-trip: result rows present for relevant sources.
- `classify_sources` skips `source_screening_result` rows with `status='not_relevant'` and `status='failed'`.
- `classify_sources` count: `classified` + `skipped` = total screening result rows for the scope.
- Check constraint: `open_tags` set to a JSON object `{}` → `IntegrityError`.
- `classified_by_run_id` is set correctly.
- Cross-project FK: classifying with scope from project A, source from project B → `IntegrityError`.
- Check constraint: bad `primary_evidence_type` → `IntegrityError`.
- Unique constraint: duplicate `(screening_scope_id, project_source_snapshot_id)` → `IntegrityError`.
- Harness round-trip: `Plan(component="classify")` → result rows in DB, events emitted.
- `source.classified` event payload: keys and values match spec.
- `delete_project_data` removes `source_classification_result` rows before `source_screening_result`
  (FK-safe order); no rows remain after deletion.

Updates to existing tests:
- `test_schema.py` — table count 13 → 14.
- `test_compile.py` — `"classify"` is a valid component; unknown component still rejected.

### Out of scope

- LLM-based `classify` tool — stub only; model route = n/a.
- `open_tags` population — stub returns `[]`; LLM classify tool will populate.
- Open tag namespace consolidation, dedup, type management — deferred.
- Grey-lit category granularity — splitting `Policy Guidance` / `Expert Opinion` is ⏸.
- `Unknown` resolution on full text — ⏸ (mirroring the appraisal seam).
- `appraise` and all subsequent components — subsequent slices.

## Constraints & approval gates

**One gated change:**

1. **Schema** — new `source_classification_result` table with composite FKs and check
   constraint on `primary_evidence_type`; new Alembic migration.

No auth, egress, secrets, new pip packages, or Plan/Config interface changes (beyond adding
`"classify"` to the existing registry).

## Public / private boundary

- Table name, column names, `ClassifyResult`/`ClassifyContext` field names, event payload
  keys — durable/committable.
- Stub sentinels (`_stub_non_evidence`, `_stub_rct`, etc.) — test infrastructure only.
- No source text, credentials, or egress in any committed file.

## Model route

`n/a` — deterministic stub only. No LLM call, no inference provider, no network I/O.
Real classify tool (LLM-based) is a deferred seam.

## Disciplines binding this slice

- **Only classify relevant sources** — `classify_sources` reads from `source_screening_result`
  where `status='relevant'`; it must not process `not_relevant` or `failed` rows.
- **`Non-evidence` is a closed label** — it excludes from `select`/`extract` downstream;
  its presence must be persisted faithfully, not silently dropped.
- **`Unknown` is kept-and-eligible** — do not treat it as `Non-evidence`; it is a valid
  document awaiting richer classification.
- **`open_tags` is always a list** — `[]` in the stub, never null.
- **Model only what behaves** — no `classify_rationale`, `classify_version`, or inert
  label columns. Grey-lit splitting goes in `docs/deferred.md`, not a half-built column.
- **Scope-scoped** — classification result is per `(screening_scope, source)`, consistent
  with the screen pattern. The same source can carry different results under different scopes
  (though the stub is deterministic and they'd be identical in practice).

## Stop conditions

- Schema approval gate hit and not yet approved.
- Schema change beyond the one gated item above is needed.
- Scope would grow past the contract (e.g. `appraise` wiring, open tag namespace work).
- `make verify` red with unclear root cause.
- Any code path would require a new LLM or egress call.

## Acceptance checks

- `make verify` (test · typecheck · lint · build) — green.
- All checks deterministic (no LLM, no egress). Every check is a test.
- No manual / browser checks required.

## Verification evidence expected

`verification.md` must include:
- `make verify` table with pass counts.
- Named test results from `test_classify.py`.
- Migration roundtrip (`alembic downgrade -1` / `alembic upgrade head`) — both clean.
- Table count: `assert len(metadata.tables) == 14`.
- Check constraint coverage: at least one test for the `primary_evidence_type` constraint.
- Cross-project FK test: one test confirming cross-project insert is rejected.
- End-to-end command: harness invoked with `component="classify"`, result rows visible in DB.
- Diff summary.
- Public-safety confirmation.
- Deferred seams recorded in `docs/deferred.md`.

## Risk tier & review focus

**Tier 3** — schema change (new table + check constraint + composite FKs).

Review focus:
- **Correctness:** only `status='relevant'` rows from `source_screening_result` are classified.
- **Cross-project integrity:** three composite FKs enforce same-project; cross-project insert test covers it.
- **Migration:** new table with composite FKs and check constraint roundtrips clean.
- **Registry:** `"classify"` in `COMPONENT_REGISTRY` with correct `requires`; unknown component still rejected.
- **Event payload:** `source.classified` payload matches the spec above.
- **Scope:** no LLM, no tags population, no `appraise` wiring, no grey-lit splitting.
