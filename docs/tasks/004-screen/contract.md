# Task contract: 004-screen

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** approved.  
> Contract approved: 2026-06-30 · Shabeer Rauf  
> Plan approved (before implementation): _date · who_  
> ADR: none.

## Goal

Add the `screen` component — a per-document metadata-based relevance filter — persisting each
result against a named **screening scope** (a research question / intent within the project). Two
new tables (`screening_scope`, `source_screening_result`) keep relevance state scope-scoped so
that multiple EB runs within one project can screen the same corpus against different questions
without clobbering each other.

## Deliverable

A PR on `task/004-screen` → `dev` that:
- Adds `screening_scope` and `source_screening_result` tables + an Alembic migration (including
  a composite unique constraint added to the existing `project_source_snapshot` table to support
  the cross-project FK pattern).
- Ships `screen.py` with `ScreenContext`, `ScreenResult`, `_stub_screen()`, and `screen_sources()`.
- Registers `"screen"` in a component-scope registry replacing the echo-specific Plan/Config validator.
- Wires `screen` into the harness; updates `skeleton.py` to demonstrate it.
- Passes `make verify` (test · typecheck · lint · build) — all green.

## Read first

- [EB components §2 — screen](../../specs/capabilities/evidence-base/components.md)
- [EB capability](../../specs/capabilities/evidence-base/capability.md) — fail-open rule, thin-base trigger
- [System data-model](../../specs/system/data-model.md) — corpus/source snapshot design, `text_basis`
- [System execution-orchestration](../../specs/system/execution-orchestration.md) — per-doc fan-out, event log
- [System plan-as-object](../../specs/system/plan-as-object.md) — Plan/Config compile, Frame/intent field
- [docs/deferred.md](../../deferred.md) — thin-base re-search and `search_coverage_record` already recorded

## Scope

### Schema

**Existing table `project_source_snapshot` — one additional unique constraint (new migration step):**

```
UniqueConstraint("project_source_snapshot_id", "project_id",
                 name="uq_pss_id_project")
```

Required to serve as the composite FK target from `source_screening_result`. Logically redundant
(the PK already guarantees uniqueness of `project_source_snapshot_id`) but Postgres requires a
unique constraint or PK to target with a composite FK.

**New table: `screening_scope`**

```
screening_scope_id  UUID         PK
project_id          UUID         NOT NULL  FK → project
intent              TEXT         NOT NULL  -- research question / EB frame text
context             JSONB        NOT NULL  DEFAULT '{}'  -- generic structured scope metadata
created_at          TIMESTAMPTZ  NOT NULL
UniqueConstraint("screening_scope_id", "project_id", name="uq_screening_scope_id_project")
```

The composite unique on `(screening_scope_id, project_id)` is the FK target for
`source_screening_result`. No unique constraint on `(project_id, intent)` — same question
string may serve as multiple distinct scopes; scope identity is the UUID.

**New table: `source_screening_result`**

```
source_screening_result_id    UUID         PK
screening_scope_id            UUID         NOT NULL
project_source_snapshot_id    UUID         NOT NULL
project_id                    UUID         NOT NULL   -- denormalized; FK + cross-project guard
screened_by_run_id            UUID         NOT NULL
status                        TEXT         NOT NULL
screen_basis                  TEXT         nullable
screen_decision_confidence    FLOAT        nullable
screened_at                   TIMESTAMPTZ  NOT NULL
```

Three composite FKs (same pattern as `event_log → runs`):

```
ForeignKeyConstraint(
    ["screening_scope_id", "project_id"],
    ["screening_scope.screening_scope_id", "screening_scope.project_id"],
)
ForeignKeyConstraint(
    ["project_source_snapshot_id", "project_id"],
    ["project_source_snapshot.project_source_snapshot_id",
     "project_source_snapshot.project_id"],
)
ForeignKeyConstraint(
    ["screened_by_run_id", "project_id"],
    ["runs.run_id", "runs.project_id"],          -- reuses existing uq_runs_run_project
)
```

These three constraints together enforce that `screening_scope`, `project_source_snapshot`, and
the producing `run` all belong to the same project. No cross-project result row is possible.

Additional constraints:

```
UNIQUE (screening_scope_id, project_source_snapshot_id)   -- one result per source per scope
INDEX  (screening_scope_id, status)                        -- efficient filtered reads
```

Valid state combinations enforced by check constraints:

| status         | screen_basis | screen_decision_confidence |
|----------------|--------------|---------------------------|
| `relevant`     | non-null     | non-null                   |
| `not_relevant` | non-null     | non-null                   |
| `failed`       | NULL         | NULL                       |

```sql
CONSTRAINT ck_ssr_status
    CHECK (status IN ('relevant', 'not_relevant', 'failed'))
CONSTRAINT ck_ssr_basis
    CHECK (screen_basis IS NULL OR screen_basis IN ('title_abstract', 'title_only'))
CONSTRAINT ck_ssr_confidence_range
    CHECK (screen_decision_confidence IS NULL
           OR (screen_decision_confidence >= 0.0 AND screen_decision_confidence <= 1.0))
CONSTRAINT ck_ssr_non_null_when_decided
    CHECK (status = 'failed'
           OR (screen_basis IS NOT NULL AND screen_decision_confidence IS NOT NULL))
CONSTRAINT ck_ssr_null_when_failed
    CHECK (status != 'failed'
           OR (screen_basis IS NULL AND screen_decision_confidence IS NULL))
```

### Python

**`screen.py`** — new module:

```python
@dataclass
class ScreenContext:
    scope_id: uuid.UUID
    intent: str
    context: dict          # from screening_scope.context JSONB

@dataclass
class ScreenResult:
    status: Literal["relevant", "not_relevant", "failed"]
    basis: str | None              # "title_abstract" | "title_only" | None (iff failed)
    decision_confidence: float | None  # None iff failed
```

`_stub_screen(metadata: dict) -> ScreenResult` — deterministic, zero egress:
- `metadata.get("_stub_failed")` → `ScreenResult(status="failed", basis=None, decision_confidence=None)`
- else: `basis = "title_abstract"` if abstract non-empty, else `"title_only"` (fail-open)
- `metadata.get("_stub_not_relevant")` → `ScreenResult(status="not_relevant", basis=basis, decision_confidence=0.95)`
- else → `ScreenResult(status="relevant", basis=basis, decision_confidence=0.9 if title_abstract else 0.7)`

`screen_sources(conn, *, project_id, run_id, context: ScreenContext) -> dict` — loads all
`project_source_snapshot` rows for the project, calls `_stub_screen(row.metadata)` per row,
inserts into `source_screening_result` (with `project_id`, `screened_by_run_id=run_id`, and
all result fields), emits one `source.screened` event per row, returns:
`{"screened": n, "relevant": r, "not_relevant": nr, "failed": f, "title_abstract": ta, "title_only": to}`

**`source.screened` event payload** (one per document, emitted inside `screen_sources`):

```json
{
  "source_snapshot_id": "<uuid>",
  "project_source_snapshot_id": "<uuid>",
  "screening_scope_id": "<uuid>",
  "status": "relevant" | "not_relevant" | "failed",
  "screen_basis": "title_abstract" | "title_only" | null,
  "screen_decision_confidence": 0.9 | null
}
```

Field names match DB column names. `screen_basis` and `screen_decision_confidence` are null when
`status = "failed"`.

**`plan.py`** — replace echo-specific field validator with a component-scope registry:

```python
COMPONENT_REGISTRY: dict[str, dict[str, list[str]]] = {
    "echo":   {"requires": ["source_snapshot_id"]},
    "screen": {"requires": ["screening_scope_id"]},
}
VALID_COMPONENTS = set(COMPONENT_REGISTRY.keys())
```

`Plan` and `Config` gain `screening_scope_id: uuid.UUID | None = None`. Validator iterates
`COMPONENT_REGISTRY[component]["requires"]` and asserts each is non-None.

**`harness.py`** — add `_run_screen` node:
1. Load `screening_scope` row from DB using `config.screening_scope_id`.
2. Construct `ScreenContext(scope_id=..., intent=..., context=...)`.
3. Emit `component.started(component="screen")`.
4. Call `screen_sources(conn, project_id=project_id, run_id=run_id, context=context)`.
5. Emit `component.completed` payload:
   `{component, screened, relevant, not_relevant, failed, title_abstract, title_only}`.

Wire into graph: `"screen": "screen"` conditional edge.

**`skeleton.py`** — create `screening_scope` row (intent + context) → `Plan(component="screen", screening_scope_id=...)` → `run_harness`.

**`helpers.py`** — extend `delete_project_data`: add `source_screening_result` (before `project_source_snapshot`) and `screening_scope` (before `project`) in FK-safe order.

**`test_screen.py`** — new file, covering:
- Table count is 13 (two new tables).
- `_stub_screen` with abstract → `relevant`, `title_abstract`, `decision_confidence=0.9`.
- `_stub_screen` without abstract → `relevant`, `title_only`, `decision_confidence=0.7` (fail-open).
- `_stub_screen` with `_stub_not_relevant` → `not_relevant`, basis set, `decision_confidence=0.95`.
- `_stub_screen` with `_stub_failed` → `failed`, `basis=None`, `decision_confidence=None`.
- `screen_sources` round-trip: result rows present, counts correct, `screened_by_run_id` set.
- `screen_sources` with multiple sources: mixed results; counts match.
- `ScreenContext.context` loaded from `screening_scope.context` JSONB.
- Cross-project FK: creating a result with scope from project A and source from project B → `IntegrityError`.
- Check constraint: bad `status` value → `IntegrityError`.
- Check constraint: bad `screen_basis` value → `IntegrityError`.
- Check constraint: `decision_confidence` out of range → `IntegrityError`.
- Check constraint: `status='failed'` + non-null `screen_basis` → `IntegrityError`.
- Check constraint: `status='relevant'` + null `decision_confidence` → `IntegrityError`.
- Unique constraint: duplicate `(screening_scope_id, project_source_snapshot_id)` → `IntegrityError`.
- Harness round-trip: `Plan(component="screen")` → result rows in DB, events emitted in order.
- `source.screened` event payload: keys and values match spec above.

Updates to existing tests:
- `test_compile.py` — reflect component-scope registry; unknown component still rejected.
- `test_schema.py` — table count 11 → 13.

### Out of scope

- LLM-based `screen` tool — stub only; model route = n/a.
- Thin-base re-search trigger — confidence is stored; the re-`search` escape hatch hits the egress hard gate; deferred.
- `screen_failed` recovery loop — `"failed"` state is representable; no retry logic.
- Tiered content peek — spec marks it ⏸.
- `search_coverage_record` table — still deferred.
- Re-screening (a second result row for the same `(scope, source)` pair) — unique constraint enforces one; follow-on seam.
- Any change to `echo` component behaviour.
- `classify`, `appraise`, `characterise` — subsequent slices.

## Note on `screen_decision_confidence`

V2 surfaced two problems with per-document screening confidence:

1. **Not cross-corpus calibrated.** Each document is screened in a separate inference call. The
   model's confidence score has no shared reference point across documents. You cannot rank-order
   documents by this value within a project.

2. **Direction asymmetry.** `confidence=0.9` for `not_relevant` and `confidence=0.9` for
   `relevant` are numerically identical. Displaying them as one measure misleads users into
   treating it as a degree-of-relevance.

`screen_decision_confidence` is **eval/audit data**, not a relevance signal. The `status` field
drives all downstream filtering. `decision_confidence` feeds calibration work owned by the eval
workstream and (when it lands) the thin-base re-search trigger — both internal, never user-facing.
Do not surface it as a relevance metric or use it for corpus ordering.

## Constraints & approval gates

**Approved. Two gated changes:**

1. **Schema** — `UniqueConstraint` added to existing `project_source_snapshot`; two new tables
   (`screening_scope`, `source_screening_result`) with composite FKs and check constraints;
   new Alembic migration.
2. **Plan/Config interface** — `source_snapshot_id` becomes optional; `screening_scope_id` added;
   component-scope registry replaces inline validator.

No auth, egress, secrets, or new pip packages.

## Public / private boundary

- Table names, column names, `ScreenResult`/`ScreenContext` field names, event payload keys — durable/committable.
- Stub sentinels (`_stub_not_relevant`, `_stub_failed`) in source metadata — test infrastructure only; not a public contract.
- No source text, credentials, or egress in any committed file.

## Model route

`n/a` — deterministic stub only. No LLM call, no inference provider, no network I/O.
Real screen tool (LLM-based) is a deferred seam.

## Disciplines binding this slice

- **Fail-open** — missing abstract must produce `basis="title_only"` + `status="relevant"`. The only paths to `not_relevant` are an explicit stub sentinel or a real LLM decision.
- **Three statuses, not two** — a `source_screening_result` row always has one of `relevant` / `not_relevant` / `failed`; null (unscreened) is the absence of a row.
- **`screen_decision_confidence` is eval/audit data** — not a relevance proxy; not surfaced to users.
- **Relevance is scope-scoped** — `project_source_snapshot` carries no relevance state; the same source can have different results under different `screening_scope` rows.
- **Model only what behaves** — no `screen_rationale`, `screen_version`, or inert label columns.
- **Flag, don't drop** — `not_relevant` rows persist; downstream components filter by `status = 'relevant'`.
- Thin-base trigger, re-screening, and LLM screen go in `docs/deferred.md`.

## Stop conditions

- Either approval gate hit and not yet approved.
- Schema or interface change beyond the two gated items above is needed.
- `make verify` red with unclear root cause.
- Any code path would require a new `search`/egress call.

## Acceptance checks

- `make verify` (test · typecheck · lint · build) — green.
- All checks deterministic (no LLM, no egress). Every check is a test.
- No manual / browser checks required.

## Verification evidence expected

`verification.md` must include:
- `make verify` table with pass counts.
- Named test results from `test_screen.py`.
- Migration roundtrip (`alembic downgrade -1` / `alembic upgrade head`) — both clean.
- Table count: `assert len(metadata.tables) == 13`.
- Check constraint coverage: at minimum one test per constraint.
- Cross-project FK test: one test confirming cross-project insert is rejected.
- End-to-end command: harness invoked with `component="screen"`, result rows visible in DB.
- Diff summary.
- Public-safety confirmation.
- Deferred seams recorded in `docs/deferred.md`.

## Risk tier & review focus

**Tier 3** — schema change (new tables + check constraints + composite FKs) + fan-out execution over corpus rows.

Review focus:
- **Correctness:** fail-open logic; `failed` produces null basis/confidence; all check constraints are correct Postgres syntax.
- **Cross-project integrity:** three composite FKs on `source_screening_result` enforce same-project; cross-project insert test covers it.
- **Migration:** `ALTER TABLE project_source_snapshot ADD CONSTRAINT uq_pss_id_project` is in the migration and roundtrips clean.
- **Interface change:** component-scope registry covers both echo and screen; unknown component still rejected.
- **Event payload:** `source.screened` payload matches the spec in §Python above.
- **Scope:** no relevance state on `project_source_snapshot`; no egress; no classify/appraise.
