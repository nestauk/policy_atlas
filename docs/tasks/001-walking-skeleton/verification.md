# Verification: 001-walking-skeleton

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make test` | pass | 26/26 deterministic tests |
| `make typecheck` | pass | mypy strict, 19 source files |
| `make lint` | pass | ruff check, 0 errors |
| `make build` | pass | sdist + wheel in `dist/` |
| `make verify` | pass | all four targets green |

## Checks beyond the build

- **Deterministic tests** — all ran, all passed:
  - [x] schema validation — 7 tables, 3 constraints present via inspector
  - [x] event-log append / read-back — ordering by `(project_id, sequence)`, per-project isolation
  - [x] plan → config compile + invalid-config-is-caught — invalid plan rejected with pydantic `ValidationError` at construction; harness never runs
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

## Review findings

Review stack run **2026-06-24** (retrospective — the build predated the codified `task-cycle`
skill, which mandates this step). `make verify` re-run independently from a clean DB: **green** —
26 tests, mypy 19 files, ruff clean, sdist+wheel built. Reviewers: a fresh-context
`agent-skills:code-reviewer` (contract-verify + correctness), an `agent-skills:security-auditor`
(data-integrity), and a heterogeneous **Codex** adversarial design pass (different model family) —
none wrote the code.

**Fixed in this pass (evidence accuracy + hygiene, non-gated):**
- `CompileError` did not exist — it was named in this file, `plan.md`, the `plan.py` docstring and
  two `docs/knowledge/` concepts, but the code rejects an invalid plan with pydantic
  `ValidationError` at construction. Corrected the current-truth records (this file, knowledge
  bundle, `plan.py`); `plan.md` left as the historical accepted plan (deviation noted here).
- Test/file counts corrected: 24 tests (not 20), 19 mypy source files (not 18).
- `plan.py` duplicate validator collapsed to one `_validate_refs` helper.
- Two unreachable `conn.execute(text("SELECT 1"))` "flush" lines removed from `test_schema.py`
  (the failing insert raises first — they never executed).
- Stray `>>>>>>> dev` merge-conflict marker removed from `AGENTS.md` (introduced by the harness merge).

**Confirmed sound (called out by reviewers):** composite-FK cross-project isolation
(`event_log(run_id, project_id) → runs`, `annotation(block_id, unit_id) → addressable_unit`); zero
runtime egress; no secrets/real-source committed; SQL fully parameterised; flag-don't-drop annotation
written *before* the `GroundingError` raise; tests assert contract properties, not just code paths.

**Actioned in the follow-up pass (gated changes, human-approved 2026-06-24):**
- **Schema strengthening recorded** — ADR 0001 §5 now documents `runs` unique `(run_id, project_id)`
  + the `event_log` composite FK as an accepted integrity strengthening beyond the contract's
  single-column FK (no longer claims "exactly as in the contract").
- **Flag-don't-drop now proven across a commit** — `test_fail_annotation_survives_commit` commits a
  failed-grounding run, reopens a fresh connection, and asserts the `fail` annotation + `run.failed`
  persist. Guards against a future re-raise past `engine.begin()` that the rolled-back tests miss.
- **`component.failed` added to the contract's event taxonomy** (failure-path event carrying the
  persisted `block_id`).
- **`sequence = max+1` single-writer contract documented** at the `events.append` call site; the
  concurrency-safe allocator stays a registered deferred seam.
- **`python-dotenv` moved to runtime `dependencies`** (was dev-only while imported by
  `alembic/env.py`); `uv.lock` regenerated.
- **`block.version` now has a DB `server_default='1'`** (schema + initial migration); pinned by
  `test_block_version_defaults_to_one`. DB recreated so the fresh migration applied.

**Still open (registered seams — not for this slice):**
- **`quote_present` joins chunks with `""`**, so a quote could match across a non-existent seam —
  fine for the single synthetic source, a false-positive vector for real multi-chunk sources.
  Address when real chunked retrieval lands.
- **Design caveats (Codex)** — block-boundary commit modelled as an event not a real commit;
  plan-as-data is a one-node graph; the `InferenceProvider` protocol is thin for eval-readiness.
  Now recorded in ADR 0001 *Reviewer notes* so slice 2 inherits them.

## Known unverified items

The `make verify` green state is re-confirmed. The grounding **failure** path is proven by tests
(`test_grounding`, `test_harness`) but not by the documented smoke command, which runs the success
path only. See *Review findings → Open* for items deferred to follow-up.

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
