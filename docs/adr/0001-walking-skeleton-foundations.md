# ADR 0001 — Walking-skeleton foundations

- **Status:** Accepted — Tier-4 sign-off 2026-06-23 (task
  [001-walking-skeleton](../tasks/001-walking-skeleton/contract.md)). Includes the SQLAlchemy
  dependency (§4) and `make build = uv build` (§11), confirmed at sign-off.
- **Date:** 2026-06-23
- **Context doc:** [contract.md](../tasks/001-walking-skeleton/contract.md) · supersedes nothing.

## Context

Task 001 stands up the thinnest end-to-end backend thread that walks the Policy Atlas v3.0 spine
once. It is the first slice that introduces dependencies, an initial schema, and the public command
surface — **Tier 4, hard to reverse**. This ADR records the foundational choices in one place so
they are decided deliberately and not re-litigated per step. All seven approval gates in the
contract are cleared; this ADR is the artefact that gate-approval attaches to.

Binding disciplines (from [product.md](../specs/product.md) / the system contracts): *build light,
leave seams*; *model only what behaves*; *artefacts → blocks → units*; *audit plane ≠ telemetry
plane*. Each decision below is checked against them.

## Decisions

1. **Backend-first skeleton; frontend deferred.** The spine to prove is backend (plan → harness →
   grounding → persistence → event log). A UI proves nothing the thread doesn't. *Rejected:* a
   full-stack skeleton — drags in Next.js/pnpm and a second gate for no added proof.

2. **Python 3.12 · uv · `src/` layout · ruff + mypy (strict).** Matches the confirmed stack;
   `src/` layout avoids import-shadowing; strict typing from line one is cheap now, expensive later.

3. **Local Postgres via Docker Compose; plain `postgres:16` image — no pgvector extension this
   slice.** No table has a vector column, so the migration issues no `CREATE EXTENSION vector`. The
   pgvector-capable image is adopted when retrieval lands. *Rejected:* the `pgvector/pgvector` image
   now — carries an extension nothing uses (model only what behaves).

4. **SQLAlchemy 2.x (Core metadata) + Alembic; `psycopg` (v3) driver.** Alembic already depends on
   SQLAlchemy; using its typed table metadata gives autogenerate + a typed query substrate for the
   event-log/persistence repositories. **This adds SQLAlchemy as an explicit dependency beyond the
   originally-listed set — recorded here for sign-off.** *Rejected:* hand-written raw-SQL migrations
   — loses typed metadata and autogenerate for no benefit at seven tables.

5. **The seven-table initial schema with its constraints and deferrals**, as in the
   contract's *Initial schema*: `event_log` unique `(project_id, sequence)`; `addressable_unit`
   unique `(block_id, unit_id)`; `annotation` composite FK `(block_id, unit_id) →
   addressable_unit`. Deferred (not pre-added): block/artefact summary columns, `same_content_as`,
   block-lineage key, any source/findings table. Honours *model only what behaves*.
   - **Strengthening beyond the contract's shape (recorded retrospectively, review 2026-06-24):**
     the contract specified `event_log.run_id` as a single-column FK to `runs`. The build instead
     adds `runs` unique `(run_id, project_id)` and makes `event_log` FK on the composite
     `(run_id, project_id) → runs(run_id, project_id)`, so a run from project B cannot be appended
     into project A's audit log at the DB layer (proven by `test_cross_project_event_append_rejected`).
     This is an integrity *strengthening*, not a new table or a relaxation, and is accepted as part
     of this ADR. *Model only what behaves* still holds — the constraint changes behaviour.

6. **Canonical event log: append-only, separate from LangGraph checkpoints, ordered by
   `(project_id, sequence)`.** `sequence` is assigned **app-side as `max(sequence)+1` per project**,
   safe under the v3.0 **serial single-writer** model ([execution-orchestration §durability]).
   Append-only is **enforced at the repository layer** this slice (no update/delete code path); a DB
   trigger / `REVOKE` is a deferred hardening. Keeps the audit plane distinct from the telemetry
   plane. *Rejected:* ordering on `occurred_at` — ties and clock skew make it non-deterministic.

7. **Inference routing seam + a no-egress `StubEchoProvider`.** The routing interface ships now; the
   stub returns canned text with **zero runtime egress**. Real OpenAI→Bedrock wiring + Langfuse
   prompt registration are a separate, gated follow-on. Proves the future-proofing seam without
   tripping the egress gate.

8. **LangGraph as a fixed harness interpreting plan-as-data; in-process this slice.** The durable
   checkpointer is deferred; the block-boundary commit is modelled as **one event**, so the seam is
   visible without a durable-execution engine. *Rejected:* wiring the durable checkpointer now —
   premature; the thread is short and re-runnable.

9. **`produce-grounded-block`: deterministic leg only.** synthesise (stub) → cite → **verify by
   verbatim quote-presence** (normalised match against the synthetic source fixture) → write. A
   fabricated quote is a **hard fail**, recorded on the annotation (*flag, don't drop* — never
   promoted to a clean tier). The LLM-as-judge grounding classifier and summary faithfulness judge
   are deferred — which is why block/artefact summary columns are also deferred (they'd be inert).

10. **structlog for structured logging, repo-wide**, from this slice — already mandated in
    [engineering-considerations.md](../agentic-ops/engineering-considerations.md). No stdlib logging
    or print.

11. **`make build` = `uv build`.** The one verify target the contract left unmapped. Building the
    sdist/wheel keeps `make verify` honest end-to-end. *Alternative:* an explicit no-op success —
    rejected as it makes `build` vacuous.

## Consequences

- **Positive:** the spine is proven with real persistence + a real audit log; every deferred
  concern is a present interface or a registered seam, not an absence; the whole slice reverts
  cleanly (greenfield).
- **Costs / risks accepted:** SQLAlchemy enters the dependency set (decision 4); append-only is
  app-enforced, not yet DB-enforced (decision 6); the harness is not resumable this slice
  (decision 8). Each is a named seam with an upgrade path, not a silent shortcut.

## Reviewer notes (review stack, 2026-06-24)

Recorded so slice 2 inherits the caveats, not just the code. None block this slice; all are the
gap between the skeleton's shape and the spec's eventual target:

- **"Block-boundary commit" is modelled as an event, not a real commit** (decision 8). The whole
  thread runs in one outer transaction (`skeleton.py` `engine.begin()`); `block.written` is an
  audit event, not a `COMMIT`. The flag-don't-drop guarantee therefore holds only because the
  harness *swallows* `GroundingError` so the outer block exits cleanly — re-raising it past
  `engine.begin()` would roll the fail annotation back. Pinned by `test_fail_annotation_survives_commit`.
  Real per-block durability arrives with the deferred checkpointer.
- **"Plan-as-data" is currently a one-node graph.** `Config` is a scalar `{component, source_ref}`
  and the dispatch map is hardcoded `{"echo": "echo"}`. A second component or a multi-step plan
  forces `Config` to grow an ordered component list / DAG — expected, but the seam isn't exercised.
- **The `InferenceProvider` protocol (`complete(str) -> str`) is a stub injection point, not yet a
  routing seam.** It carries no model id/version/usage/trace identity, which eval-readiness and the
  OpenAI→Bedrock route will need. Widen it when the real provider lands (decision 7).
- **`event_log` ordering assumes a single writer per project** (decision 6) — now documented at the
  `events.append` call site; the concurrency-safe allocator stays a deferred seam.

## Rollback

Revert the PR; drop the initial Alembic migration. No production data, no consumers — blast radius
is the repo itself.
