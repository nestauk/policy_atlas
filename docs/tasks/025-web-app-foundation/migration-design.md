# B.1 — Schema migration design (lead brief for B.2/B.3)

Two migrations, both owner-approved gates (contract § Constraints). Alembic
head today: `a3c6f9e2b7d4`.

> **Gate expansion approved 2026-07-21 · owner** (build-time question, B.1):
> `event_log.run_id` becomes **nullable** in migration 1 — finding 12's
> `project.renamed`/`project.archived` audit events have no run to attach to
> (a fresh project has none; the 024 attachment invariant covers steering
> events only). The composite FK `fk_event_log_run_project` is MATCH SIMPLE,
> so NULL `run_id` skips it — the exact house pattern of
> `runs.capability_run_id`. Steering events keep their non-NULL attachment
> invariant unchanged. Downgrade: delete run-less event rows, restore
> NOT NULL (tested). Options considered and rejected: audit outside
> event_log (no durable/queryable record, invisible to SSE replay);
> events-only-when-runs-exist (unaudited fresh-project renames). House style: hand-written migrations in the
`d2f8a4c1e9b7_orchestration_plan.py` idiom (docstring with rationale, named
constraints, tested downgrade).

## Migration 1 — `project` lifecycle columns (revises `a3c6f9e2b7d4`)

Expand → backfill → constrain, one migration (all steps in `upgrade()`):

**Expand** — add to `project`:

| column | type | nullability |
|---|---|---|
| `name` | Text | added nullable, NOT NULL after backfill |
| `question` | Text | nullable (a project may predate a settled question) |
| `status` | Text | added nullable, NOT NULL after backfill |
| `updated_at` | DateTime(timezone=True) | added nullable, NOT NULL after backfill |
| `archived_at` | DateTime(timezone=True) | nullable |
| `owner_user_id` | Text | nullable — **stays NULL on pre-existing rows** (intentionally inaccessible via the API; documented DB-level recovery = manual UPDATE) |

**Backfill** (contract finding 10, tested against a populated pre-025 DB):
- `name` := latest **approved** `orchestration_plan` row's `payload->>'title'`
  (latest = max `version` with `status='approved'`), else `'Untitled project'`.
- `question` := same row's `payload->>'question'`, else NULL.
- `status` := `'active'`; `updated_at` := `created_at`.

**event_log widening (approved gate expansion, header note):**
- `ALTER event_log.run_id DROP NOT NULL`. Composite FK unchanged (MATCH
  SIMPLE skips NULL). Downgrade: `DELETE FROM event_log WHERE run_id IS NULL`
  then `SET NOT NULL` — asserted in tests (a lifecycle event row present →
  downgrade removes exactly those rows and restores the constraint).

**Constrain:**
- `ALTER ... SET NOT NULL` on `name`, `status`, `updated_at`.
- `ck_project_status`: `status IN ('active', 'archived')` — lifecycle ONLY
  (finding 6: run state is never cached on the project row).
- `ck_project_archived_at`: `(status = 'archived') = (archived_at IS NOT NULL)`
  (house paired-check idiom, cf. `ck_pss_full_text_*`).

**Downgrade:** drop the six columns + both checks (data-lossy by design —
lifecycle state has no pre-025 home; assert in the test that a
renamed+archived row downgrades to a bare row without error).

`core/schema.py` updated to match in the same change.

## Migration 2 — `capability_run` status widening (revises migration 1)

**Upgrade:** drop `ck_capr_status`, recreate as
`status IN ('running', 'paused', 'succeeded', 'degraded', 'failed', 'aborted', 'interrupted')`.
Update the schema.py comment (`# running|paused → succeeded/degraded/failed/aborted/interrupted`).

**Downgrade** (plan-pinned mappings, asserted row-by-row in tests):
1. `UPDATE capability_run SET status='aborted', ended_at=COALESCE(ended_at, now()) WHERE status='paused'`
2. `UPDATE capability_run SET status='failed',  ended_at=COALESCE(ended_at, now()) WHERE status='interrupted'`
3. Recreate the old five-value `ck_capr_status`.

Component-run disposition (contract §5 names it here): a **parked** walk has
no in-flight `runs` row by construction — parking happens at a component
boundary after the component's run reached a terminal status; an
**interrupted** walk may leave a `runs` row in `running` — that row is left
as-is by the migration (the C.3 orphan sweep owns marking it; `runs.status`
has no check constraint). Continuation/park events in `event_log` are JSONB
payloads with no constraint — inert under downgrade by construction.

## B.2 tests (real Postgres, migration-chain driven)

New `backend/tests/core/test_migrations_025.py` (or house-appropriate home):
build a **populated pre-025 fixture** by migrating a scratch DB to
`a3c6f9e2b7d4`... — practical realisation: run the full chain minus the two
new revisions via `alembic upgrade a3c6f9e2b7d4`, insert fixture rows
(projects with and without an approved plan; capability_runs across the five
legacy statuses), then:
- `upgrade +2` → assert: plan-backed project got plan title/question;
  planless project got `'Untitled project'`/NULL; `status='active'`;
  `updated_at = created_at`; `owner_user_id IS NULL`.
- Insert post-025 rows (`paused`, `interrupted` capability_runs; an archived
  project) → `downgrade -2` → assert exact mappings: paused→aborted,
  interrupted→failed, NULL `ended_at` got stamped, legacy-status rows
  untouched; project columns gone.
- `upgrade +2` again (chain re-entrant).

Use a dedicated scratch database/connection so the main test DB's
session-scoped schema setup is untouched (mirror however conftest provisions
DBs — inspect before writing).

## B.3 — transactional lifecycle audit events

`backend/src/policy_atlas/api/lifecycle.py` (new package `policy_atlas.api`,
**no FastAPI import in this module** — plain SQLAlchemy; D-phase routers call
it):

- `rename_project(conn, project_id, new_name, actor) -> None` — UPDATE name +
  `updated_at`, append `project.renamed` event **on the same conn/transaction**
  `{payload: {name_from, name_to, actor}}`.
- `archive_project(conn, project_id, actor) -> bool` — idempotent: already
  archived → no-op returning False (no second event); else set
  `status='archived'`, `archived_at=now()`, `updated_at`, append
  `project.archived` `{payload: {actor}}`; True.
- Both raise on unknown project (`LookupError`; the API layer maps to 404).
- Events append with `run_id=None` (the approved gate expansion above);
  `core/events.append` gains an optional `run_id: uuid.UUID | None` —
  steering emitters keep passing non-None (their invariant is theirs).
- Tests: rename persists + event in same transaction (roll back → neither);
  archive idempotence (double archive = one event); unknown project raises.

409-while-running semantics live in the D-phase routers (they need the run
read), not in B.3.
