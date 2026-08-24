# Verification: 033-organisations

> **Status: IN PROGRESS — build phase (steps 5–6).** Assembled incrementally at each
> phase commit; complete only at the Phase 12 exit gate.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (baseline, Phase 0) | pass | Third run; see the baseline note below. |
| `make verify` (Phase 0b in tree) | pass | Backend 2170 passed · typecheck · lint · frontend build green. |

**Baseline note (Phase 0).** The first two full-verify runs were red (45, then 4
failures) from *test contention*, not the tree: a delegated agent ran pytest against the
shared `policy_atlas_test` database while the main suite was mid-run. A quiet-machine
run of the affected subset on the clean tree passed (294/294). The remaining 4
order-dependent failures were caused by Phase 0b itself and fixed (see Deviations).

## Phase evidence

### Phase 0 — Baseline
- Full `make verify` green (see above). Alembic head confirmed `b3c7d914e0a2` — the one
  revision never referenced as a `down_revision`.
- Route inventory captured from the tree: **39 route decorators**;
  `conversations.py` mounts two routers (`/api/v1/conversations` ×7 routes,
  `/api/v1/projects` ×2); `chat_turns.py` has no router (service module).
  Evidence: [route-inventory.md](route-inventory.md).

### Phase 0b — Structured logging at the API entrypoint (owner call (k))
- `create_app` calls `configure_logging()` first; test
  `test_create_app_configures_json_logging_and_httpx_guard` asserts the **rendered JSON
  shape** under `LOG_FORMAT=json` (event, key, level, timestamp) and the httpx
  WARNING guard on the deployed path.
- **Staging httpx INFO check (rubric 15a): pending — scheduled with the Phase 12 live
  checks.**

### Phase 1 — Schema, migration and `created_by` writes (gate: schema)
- Migration `a4f1c8e3b6d2` (sole head, off `b3c7d914e0a2`): `organisation`, `app_user`,
  `org_id`+`visibility` on `project`/`portfolio` with CHECKs and the two org-leg
  indexes, `conversation.created_by` backfilled from the owning project's owner.
  `lock_timeout='5s'` set in both directions (no value named anywhere in the repo;
  5s chosen and commented against the runbook's blocker preflight).
- `create_conversation` writes `created_by` on insert.
- **Full `make verify` green** (2172 backend · mypy 267 files · ruff · infra 45 ·
  drift-check OK · frontend 61 files/407 tests · build ✓). Named tests:
  `test_migration_roundtrip_organisation_tenancy`,
  `test_downgrade_erases_chat_authorship_exposing_colleague_chats` (rubric 32 — also
  proves a re-upgrade misattributes the colleague's chat to the owner, so re-upgrade
  does not undo the exposure).
- Test repairs, justified inline: six `metadata.tables` counts 33→35; the portfolio
  column-set equality gains the two columns; **the `downgrade -1` roundtrip test had
  been vacuous for fifteen revisions** — repaired to name its revision explicitly.
- Handed forward: `planning.py` also creates `conversation` rows and does not yet set
  `created_by` — Phase 4/5 decides deliberately (contract grades planning
  conversations by project ownership, so it is not load-bearing there).

## Diff summary

(Assembled per phase; final pass at Phase 12.)

- Phase 0b: `create_app` wires `configure_logging()`; one new test.

## Deviations flagged (minor, resolved within the contract's vocabulary)

1. **`cache_logger_on_first_use=True` dropped from `configure_logging()`** (Phase 0b).
   The contract pins "one call, nothing else about logging changes". The one call was
   not shippable as-is: with caching on, any test that builds an app freezes every
   module-level logger's config, and `structlog.testing.capture_logs()` — used by 5
   assertions in `test_ingest_full_text.py` — silently stops intercepting for every
   suite that runs later. Four ingest tests failed order-dependently. Caching off makes
   the entrypoint call safe process-wide; the cost is one config lookup per log call.

## Intent & assumptions

## Known unverified items

- Staging httpx INFO line check (rubric 15a) — deferred to Phase 12 live checks.

## Public safety

Nothing sensitive added so far: no real subs, no addresses, no org names.

## Review handoff (step-7/8 inputs)

Executor provenance so far: Phase 0 route inventory — fast-worker; Phase 0b — fast-worker
(lead root-caused and fixed the capture_logs interaction); Phase 1 — deep-reasoner.

- **Knowledge candidates** (running list, one bullet per durable-seeming lesson):
  - `structlog.configure(cache_logger_on_first_use=True)` and
    `structlog.testing.capture_logs()` are mutually exclusive across a test suite: once
    any code path configures with caching and a module-level logger fires, capture_logs
    in *later* tests silently sees nothing. Symptom: order-dependent failures in suites
    alphabetically after the configuring one.
  - Delegated agents must never run pytest while another suite is mid-run — the test
    database is shared and the collision presents as dozens of scattered, unreproducible
    failures. Serialize all DB-touching test runs across agents; the delegation brief
    must say so explicitly.
  - A red baseline at build-open is not always the tree: check Docker/Postgres first
    (`make setup`), then contention, before reading test bodies.
  - `alembic downgrade -1` in a roundtrip test rots silently: once any newer migration
    lands, `-1` reverts *that* instead of the revision the test is about, and the
    assertions pass vacuously. Name the target revision explicitly. (Found wrong for
    fifteen revisions in `test_migration_roundtrip_screen_stage_and_classify_tags`.)
  - A single-file `mypy tests/core/test_schema.py` run poisons `.mypy_cache` and the
    next full run reports a spurious `attr-defined` error; `rm -rf backend/.mypy_cache`
    clears it. Pre-existing harness quirk.
  - Alembic roundtrip tests run on their own connection, so the `conn` fixture's
    rollback cannot clean their seeds — commit outside the fixture and delete in
    `finally`, then verify zero residue.

## Deferred work

(Collected at Phase 11 into docs/deferred.md.)
