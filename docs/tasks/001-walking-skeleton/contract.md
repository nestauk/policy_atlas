# Task contract: 001-walking-skeleton

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md); specs in
[docs/specs/](../../specs/index.md).

> **Status: drafted, not started — gates cleared, ready to implement.** All approval gates in
> *Constraints & approval gates* are signed off (deps, schema, command surface, egress, inference
> seam, frontend-out, CI-out). Tier 4 still wants a human-approved implementation plan + ADR
> before code lands. Nothing is built yet.

## Goal

Stand up the **thinnest end-to-end backend thread** that exercises the Policy Atlas v3.0 spine
once, proving the architecture's seams are real — not a feature. One trivial input runs through
**plan → compile → LangGraph harness → inference routing seam → persisted artefact/block/unit +
annotation + canonical event-log entries**, and reads back. Everything expensive or out-of-scope
is a **stub behind an interface or a deferred seam**, never absent and never faked.

This is a *walking skeleton* (Cockburn): minimal, but it walks the whole spine. It is explicitly
**not** the Evidence Base capability, not real retrieval, not real egress, not real models.

## Deliverable

A PR landing: a backend package scaffold; a wired `make verify`; one durable end-to-end thread
through the spine; the smallest schema that thread needs; deterministic tests; and
[verification.md](verification.md) evidence. "Shipped" = `make verify` green, the thread runs and
persists, and every seam below is present as an interface with a no-egress/stub implementation.

## Read first

Route via [specs/index.md](../../specs/index.md). Read the source sections in depth, not headings:

- [product.md](../../specs/product.md) — what the product is; *artefacts over chat*, *build light
  leave seams*. The skeleton must not imply a workflow the tool doesn't yet drive.
- [system/execution-orchestration.md](../../specs/system/execution-orchestration.md) — orchestrator
  + sub-agent surface, **fixed LangGraph harness interpreting plan-as-data**, the universal core,
  durability (block-boundary commits, memoisation). The harness shape is the spine.
- [system/plan-as-object.md](../../specs/system/plan-as-object.md) — plan vs config; **robust
  compile by construction** (deterministic mapping, a config that doesn't validate is a caught
  error). The skeleton proves this with one trivial plan.
- [system/data-model.md](../../specs/system/data-model.md) — artefact / **block** (co-versioned
  summary column, content hash) / **addressable unit** / **annotation layer keyed by
  `(block, unit, type)`**. The minimum tables hang off this.
- [system/provenance-grounding.md](../../specs/system/provenance-grounding.md) —
  `produce-grounded-block` = synthesise → cite → verify → write; the **deterministic
  quote-presence check** (a fabricated quote on a real document is a hard fail). The skeleton
  exercises the deterministic leg only.
- [agentic-ops/engineering-considerations.md](../../agentic-ops/engineering-considerations.md) +
  [agentic-ops/readiness.md](../../agentic-ops/readiness.md) — stack direction, approval gates,
  the "no command surface until the scaffold exists" rule, eval-readiness as a persistence
  property.

## Scope / Out of scope

**In** (the spine, walked once, thinly):

- **Backend package scaffold** — uv project, `src/` layout, `pyproject.toml`. *(gated: deps)*
- **Wire `make verify`** to real `uv`/`pytest`/`ruff`/`mypy`, replacing the honest-red stubs in
  [Makefile](../../../Makefile). *(gated: command surface)*
- **Fixed LangGraph harness** that interprets one trivial **plan-as-data** and runs one component.
- **Plan → config compile** — deterministic mapping for that one plan; invalid config is a caught
  error, never a silent run.
- **Inference routing seam** — an interface + a **no-egress stub/echo provider**. Proves the seam
  (the future-proofing point) without any real model call.
- **Persistence** — seven tables (`project`, `artefact`, `block`, `addressable_unit`,
  `annotation`, `runs`, `event_log`) + one alembic migration. Full column shapes in
  *Initial schema* below; the **canonical project event log** is append-only and separate from
  LangGraph checkpoints.
- **`produce-grounded-block` — deterministic leg only**: synthesise (stub) → cite → **verify by
  verbatim quote-presence against a seeded synthetic source chunk** → write one block + unit +
  citation annotation (stores: stable synthetic `source_ref`, verbatim quote, verification result) +
  event-log entries. The LLM-as-judge leg is stubbed/deferred. The synthetic source chunk is a
  **test fixture**, not a persisted `source_snapshot` record — full source snapshot/chunk
  persistence is a deferred seam.
- **Deterministic tests** — schema validation, event-log append/read, plan→config compile,
  content-hash stability, quote-presence pass *and* fabricated-quote hard-fail.

**Out** (deferred seams — leave them as seams in [docs/deferred.md](../../deferred.md), not silent
omissions):

- Any real **Evidence Base** component (`acquire → … → synthesise`), and all other capabilities.
- Real **`search` egress** / OpenAlex / Overton / open-web — no external egress in this slice.
- Real **retrieval** / pgvector tuning / rank fusion / rerank — adapter seam present, not exercised.
- Real **models** (OpenAI / Bedrock), the **LLM-as-judge** grounding classifier, summary
  faithfulness judge, **appraisal**, the **findings layer** + extraction.
- **Frontend** scaffold (Next.js), **CI** (GitHub Actions), **Langfuse** wiring, **auth/tenancy**,
  the shared acquired-snapshot substrate, **AI evals**.
- Don't flatten any 🟡/❓/⏸ status; model only what behaves (no inert flags/types in the schema).

## Constraints & approval gates

**Needs human approval before any work starts** (from [AGENTS.md](../../../AGENTS.md) +
[engineering-considerations.md](../../agentic-ops/engineering-considerations.md)). This slice is
**unusual**: its whole purpose is to cross gates, so they must be cleared *up front*, not avoided.

| Gate | What this slice proposes | Decision needed |
|---|---|---|
| **Dependencies** | uv + Python; langgraph, pydantic, a Postgres driver, pytest/ruff/mypy, alembic, structlog | ✅ approved |
| **Schema / data model** | 7 tables (see *Initial schema*) + one alembic migration | ✅ approved |
| **Command surface** | wire `make {setup,test,typecheck,lint,build,verify}`; `make setup` starts/prepares Docker Compose DB; `make verify` starts test DB or fails with clear error | ✅ approved |
| **External egress** | **none** — stub inference provider, no `search` | ✅ approved (no Policy Atlas runtime egress this slice) |
| **Inference route** | routing **seam** present; stub provider behind it (see *Model route*) | ✅ approved (seam shape; real provider deferred) |
| **Frontend scaffold + package manager** | **deferred** — backend-first skeleton | ✅ approved (frontend out of this slice) |
| **CI / production config** | **deferred** — local `make verify` only | ✅ approved (CI out of this slice) |

## Proposed stack / scaffold defaults — ⚠️ PROPOSED, NEEDS HUMAN APPROVAL

Aligned to the confirmed stack ([engineering-considerations.md](../../agentic-ops/engineering-considerations.md)
§Stack); the *direction* is confirmed, the *scaffold* is not. None of this is created yet.

- **Language/runtime:** Python, **uv**-managed, `src/` layout, strict `mypy`, `ruff`.
- **Harness:** **LangGraph** as the fixed graph interpreting plan-as-data; durable checkpointer
  deferred (in-process for the skeleton), block-boundary commit modelled as one event.
- **Store:** **Postgres** (local dev via **Docker Compose**; Aurora-shaped). `make setup` starts or
  prepares the local database; `make verify` must either start the test database or fail with a
  clear setup error. **pgvector seam declared, not used** this
  slice. Migration tool: **alembic** (approved).
- **Inference:** routing interface with a **no-egress stub/echo provider**; real OpenAI→Bedrock
  wiring is a follow-on, separately gated.
- **Observability:** **structlog** for structured logging (mandatory throughout the codebase; see
  [engineering-considerations.md](../../agentic-ops/engineering-considerations.md)); **Langfuse
  deferred**.
- **Scope discipline:** backend only; **no Next.js, no CI, no real egress, no real models** in
  this slice.

## Initial schema (approved)

Seven tables, one alembic migration. Grounded in [data-model.md](../../specs/system/data-model.md);
**model only what behaves** — columns a future concern needs but this slice doesn't exercise are
**deferred**, not pre-added.

**`project`** — scoping root (everything is within a project).
`project_id` uuid pk · `created_at` timestamptz.

**`artefact`** — unit of value.
`artefact_id` uuid pk · `project_id` uuid fk→project · `title` text · `created_at` timestamptz.
*Deferred: the artefact-summary field + `pending/verified/failed` marker (summary judge not run).*

**`block`** — unit of storage/versioning; the thread writes one.
`block_id` uuid pk (the version instance units bind to) · `artefact_id` uuid fk→artefact ·
`version` int default 1 · `content` text · `content_hash` text (normalised hash of `content`) ·
`created_at` timestamptz.
*Deferred: the co-versioned `summary` + `summary_status` marker — the summary faithfulness judge
isn't run this slice, so the marker would be inert (same call as the artefact summary); deferring
it makes `content_hash`'s summary-exclusion trivially true. Also deferred: block-lineage key
grouping versions (needed only at regeneration); structured-content blocks.*

**`addressable_unit`** — what citations/comments hang off; ID bound to the block version.
`unit_id` uuid pk · `block_id` uuid fk→block · `unit_type` text (`text_span` this slice) ·
`locator` jsonb (span position, e.g. `{start, end}`) · `content` text (the span text) ·
`created_at` timestamptz. **Unique** `(block_id, unit_id)` — the target for the annotation
composite FK below.
*Deferred: `same_content_as` link (no regeneration this slice).*

**`annotation`** — the layer keyed by `(block, unit, type)`; **polymorphic** so claims/comments/
gaps/patterns land later without reshaping.
`annotation_id` uuid pk · `block_id` uuid · `unit_id` uuid · `annotation_type` text
(`citation` this slice) · `payload` jsonb · `created_at` timestamptz. **Composite FK**
`(block_id, unit_id)` → `addressable_unit(block_id, unit_id)` — so an annotation's `block_id`
can never disagree with its unit's `block_id` (and block→artefact→project integrity rides along
via the unit). No separate single-column FKs needed.
For `citation` the payload is `{source_ref, quote, verification_result}` — stable synthetic
`source_ref`, the verbatim quote, the quote-presence result.

**`runs`** — run record; lifecycle is tested.
`run_id` uuid pk · `project_id` uuid fk→project · `status` text
(`running` → `succeeded`/`failed`, deterministic) · `started_at` timestamptz · `ended_at` timestamptz null.
*Deferred: persisting the plan/config on the run; the compiled config travels in the
`plan.compiled` event payload this slice.*

**`event_log`** — canonical, **append-only** (no update/delete), separate from LangGraph checkpoints.
`event_id` uuid pk · `run_id` uuid fk→runs · `project_id` uuid fk→project · `sequence` bigint
not null · `event_type` text · `occurred_at` timestamptz · `payload` jsonb. **Unique**
`(project_id, sequence)` — the deterministic ordering key for canonical append/read-back
(`occurred_at` is informative but not a sufficient order — ties and clock skew).
**Minimum event types the manual thread must emit:** `run.started` · `plan.compiled` ·
`component.started` · `component.completed` · `block.written` · `run.completed` (or `run.failed`).

## Public / private boundary

- **Public-safe (committable):** all scaffold code, the migration, tests, `make verify` wiring,
  this packet, and the [verification.md](verification.md) evidence.
- **Synthetic only:** any seeded source chunk / fixture used by the quote-presence check must be
  **synthetic** — no real uploaded or acquired source text enters the repo or the evidence.
- **Private (never committed):** credentials/secrets, real source text, raw traces, prompts
  carrying data. The stub provider means no provider call and so no trace to leak this slice.
- Default: private unless cleared.

## Model route

Inference route for the one LLM-bearing step (`produce-grounded-block`'s synthesise): the v3.0
target is **OpenAI under approved controls → Bedrock, behind the in-house routing seam**
([project-stack]; arch route). **This slice does not call a real model** — it ships the routing
**interface** with a **no-egress stub/echo provider** so the seam is proven without triggering the
egress gate. Real provider wiring + prompt registration (Langfuse) is a separate, gated follow-on.
Prompt-bearing changes are high-leverage — none are introduced here beyond a placeholder.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves** — no label/type/flag in the schema that doesn't change v3.0 behaviour
  (no inert sensitivity column, no `Library` class, no strand entity).
- **Flag, don't drop** — a failed quote-presence check flags, it never silently promotes to a clean
  tier.
- **Honest absence** — the skeleton makes no coverage/gap claim; if it did it would carry its base.
- **Seams stay seams** — egress, retrieval, models, frontend, CI are interfaces/records in
  [docs/deferred.md](../../deferred.md), not silent omissions.

## Stop conditions

Halt and escalate when: any gate above is unapproved (do **not** scaffold around it); the schema
needs a table beyond the seven listed; the slice tempts a real model call, real egress, or a real EB
component; scope would grow past "the spine, walked once"; or the turn/token budget is spent.
Report the blocker; don't push through.

## Acceptance checks

- `make verify` (test · typecheck · lint · build) — **green** (the point of wiring the Makefile).
- **Deterministic tests** (all that apply here; **no AI eval this slice**): schema validation,
  event-log append/read-back, plan→config compile + invalid-config-is-caught, content-hash
  stability, `produce-grounded-block` quote-presence **pass** and fabricated-quote **hard-fail**.
- **Manual end-to-end thread:** run the one input through the spine; observe the persisted
  artefact/block/unit + annotation and the appended event-log entries. **The exact command used
  must be documented in [verification.md](verification.md) or the PR.**

## Verification evidence expected

In [verification.md](verification.md) (or the PR), enough to call this done: `make verify` +
named-test results; the end-to-end thread output (persisted row IDs + the event-log entries it
appended); **the exact command used for the thread**; a one-read diff summary; public-safety
confirmation (**synthetic fixtures only, no real source text, no credentials, no Policy Atlas
runtime egress**); and known gaps → [docs/deferred.md](../../deferred.md).

## Risk tier & review focus

**Tier 4** — first scaffold introducing dependencies, an initial schema/migration, and the public
command surface (highest-impact, hard-to-reverse foundations).

Review: **human-approved plan + ADR** for the stack/scaffold/schema choices; **rollback** = revert
the PR / drop the initial migration (greenfield, low blast radius). Focus: scope creep (does it
stay "the spine, walked once"?), seams-are-really-seams (no real egress/models snuck in), schema
models-only-what-behaves, and the quote-presence hard-fail actually fails.
