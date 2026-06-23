# Verification: 001-walking-skeleton

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make test` | pass | 20/20 deterministic tests |
| `make typecheck` | pass | mypy strict, 18 source files |
| `make lint` | pass | ruff check, 0 errors |
| `make build` | pass | sdist + wheel in `dist/` |
| `make verify` | pass | all four targets green |

## Checks beyond the build

- **Deterministic tests** — all ran, all passed:
  - [x] schema validation — 7 tables, 3 constraints present via inspector
  - [x] event-log append / read-back — ordering by `(project_id, sequence)`, per-project isolation
  - [x] plan → config compile + invalid-config-is-caught — `CompileError` raised, harness never runs
  - [x] content-hash stability — stable + whitespace-insensitive
  - [x] `produce-grounded-block` quote-presence **pass** — including boundary-spanning quote
  - [x] `produce-grounded-block` fabricated-quote **hard-fail** — `GroundingError` raised; annotation written with `verification_result="fail"`; not promoted to clean tier
  - [x] run record created, reaches `succeeded`/`failed` deterministically, reads back
- **AI evals** — none this slice.
- **Manual / end-to-end thread** — exact command:
  ```
  export DATABASE_URL="postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas"
  python -m policy_atlas.skeleton
  ```
  - persisted IDs:
    - `artefact_id: 57432e43-0fee-4724-870a-dd7232ac647e`
    - `block_id:    5fc7fba3-e52f-4c80-8bb0-b6843786649b`
    - `unit_id:     62323f35-757c-408b-83d0-10c65b9f398b`
    - `annotation_id: cfdba74e-e004-4c37-9f59-3519c3ce275e`
  - event-log entries (ordered by sequence):
    - `[1] run.started`
    - `[2] plan.compiled`
    - `[3] component.started`
    - `[4] component.completed`
    - `[5] block.written`
    - `[6] run.completed`

## Diff summary

Greenfield scaffold from zero. Added:
- `pyproject.toml`, `docker-compose.yml`, `.env.example`, updated `Makefile` (wired from honest-red stubs to real commands) + `.gitignore` (Python ignores appended).
- `src/policy_atlas/`: `__init__`, `logging`, `db`, `schema`, `fixtures`, `inference`, `events`, `grounding`, `plan`, `harness`, `skeleton`.
- `alembic/` + `alembic.ini` + one migration (`68afc1c2def1_initial.py`) creating the seven tables.
- `tests/`: `conftest`, `test_schema`, `test_events`, `test_compile`, `test_grounding`, `test_harness`.

The spine is walked once. Every seam is present as an interface with a stub/no-egress implementation.

## Intent & assumptions

The spine walked once; seams stubbed per ADR 0001 (signed off 2026-06-23):
- `StubEchoProvider` is the inference seam; no model call, no egress.
- `sequence = max+1` app-side, safe under serial single-writer (ADR §6).
- Migration uses plain `postgres:16`; no `CREATE EXTENSION` (ADR §3).
- `make build = uv build` (ADR §11).
- Approval gates: deps ✅ schema ✅ command surface ✅ egress (none) ✅ inference seam ✅ frontend out ✅ CI out ✅.

## Known unverified items

None. All rubric items checked.

## Public safety

Confirmed:
- **Synthetic fixtures only** — `src/policy_atlas/fixtures.py` contains only hand-written synthetic text; no real uploaded or acquired source text in the repo or this evidence.
- **No credentials committed** — `.env` is gitignored; `.env.example` contains only a local dev URL template.
- **No Policy Atlas runtime egress occurred** — `StubEchoProvider` makes no network calls; toolchain install traffic (`uv sync`, Docker image pull) is not runtime egress.
- **No traces to redact** — stub provider means no provider call and no trace.

## Deferred work

All deferred seams remain in `docs/deferred.md` unchanged. Nothing newly deferred this slice. Open seams to note:

- Real inference provider (OpenAI→Bedrock) — behind `InferenceProvider` interface.
- Real retrieval / pgvector — adapter seam present, not exercised.
- Durable LangGraph checkpointer — in-process only this slice.
- LLM-as-judge grounding classifier + summary faithfulness judge — deferred, no inert columns pre-added.
- DB-level append-only enforcement (`REVOKE` / trigger) — app-layer only this slice (`ponytail:` comment in `events.py`).
- Frontend, CI, Langfuse, auth/tenancy, source-snapshot persistence.
