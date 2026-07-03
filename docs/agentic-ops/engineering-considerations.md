# Engineering considerations (non-binding)

**Status: optional, non-binding.** This file captures *likely* implementation considerations and
the *approval gates* implied by the architecture, so they aren't rediscovered later. It is **not
a set of implementation rules** and decides nothing — the canonical contracts are under
[../specs/](../specs/), and the binding boundaries live in [../../AGENTS.md](../../AGENTS.md).
Anything here is superseded by a real spec, a task contract, or a human decision.

## Stack (direction confirmed; walking skeleton landed a thin slice)

The backend stack direction is confirmed. The `001-walking-skeleton` slice implemented a **thin,
stubbed** slice of it ([ADR 0001](../adr/0001-walking-skeleton-foundations.md); `make verify` green):
Postgres via Docker Compose (plain `postgres:16`, no pgvector), the LangGraph harness in-process, the
inference **routing seam** behind a no-egress stub, the canonical `event_log` + a `runs` table, uv and
structlog. Everything below beyond that thin slice is **direction or a deferred seam**
([docs/deferred.md](../deferred.md)) — not yet built:

- **Postgres / Aurora** as the canonical store, with **FTS + pgvector** for hybrid retrieval
  (cross-encoder rerank behind a profile seam; a dedicated retrieval service only if the
  Aurora-native path fails on measured quality/latency/scale).
- **LangGraph** as the fixed reasoning harness + durable checkpointer; an **off-request worker
  tier**; a **runs table**; tool-result memoisation; block/component-boundary checkpoints.
- **Inference route**: OpenAI API under approved data controls first; target Amazon Bedrock —
  behind an in-house routing layer (the key future-proofing seam).
- **Langfuse** as the trace backbone and prompt registry.
- A **canonical Project event log** kept separate from LangGraph execution checkpoints; the
  decision log, change log, version history and catch-me-up are projections over it.

Likely frontend and tooling defaults (confirm before creating files or installing anything):
- Next.js + TypeScript, strict mode.
- pnpm.
- uv.
- Explicit schema validation at API, tool and event boundaries.
- **structlog** for structured logging throughout the application — **mandatory from the first scaffold slice onward**. Configure for structured JSON output in deployed environments and developer-friendly console output locally. Do not use stdlib logging or ad-hoc print statements; all application log calls go through structlog.
- CloudWatch for AWS runtime logs, metrics and alerts.
- GitHub Actions for CI once implementation begins.
- AWS-oriented deployment (not Heroku-first).

## Approval gates (from AGENTS.md + the architecture)

These require explicit human approval before an implementation task proceeds:

- **Schema / data model** — the canonical entity, annotation and findings-layer tables.
- **Auth / tenancy** — the cross-tenant boundary the shared acquired-snapshot store makes
  load-bearing; ownership/driver model.
- **External egress** — search backends, the inference route, and the governance-event logging
  that must accompany them.
- **Dependencies, CI, production config, public interfaces** — never changed without approval.
- **Frontend scaffold and package manager** — confirm before creating files or installing deps.

## Cross-cutting considerations

Drawn from the architecture's build implications — flagged so design choices don't quietly
violate them:

- Outputs are **artefacts → blocks → addressable units**, not flat markdown — provenance,
  comments, versions and evals all hang off units.
- The **plan is canonical**; machine config compiles from approved plan fields.
- **Tools are scoped per component**; agents see only declared tools + the small universal core.
- **Substance pauses in every steering mode**; method routes by mode + declared hatches.
- **Audit plane (event log) ≠ telemetry plane** (traces/metrics); eval results bridge by
  attaching to canonical units.
- **Build light but seamful** — use the v3.0 worker/checkpointer model; keep durable execution
  and inference behind interfaces for later swap-out.
- **Eval-readiness is a persistence property** — judge I/O, prompt/model version and
  segmentation/envelope versions are persisted; calibration is the eval workstream's, not a
  product commitment.

## Prompt management

The likely direction is **repo-first prompt governance** with Langfuse as the runtime prompt
registry and analysis surface. Future specs should decide:

- where production prompts live in the repo;
- how prompts are deployed to Langfuse;
- which labels/environments are used;
- what prompt/version/model/route identifiers are stored at runtime;
- which prompt changes require strongest-model review;
- how emergency Langfuse prompt edits are reconciled back into the repo.

Prompt-bearing changes are high-leverage engineering changes. Treat them as such, especially
for orchestration, grounding, citation verification, summary faithfulness, appraisal,
extraction and LLM-as-judge behaviour.

## Security considerations

Task contracts and implementation specs should account for:

- prompt injection from uploaded and acquired documents;
- tool-call injection;
- retrieval poisoning;
- leakage through prompts, traces, logs, search queries or model-provider calls;
- secrets and credential handling;
- tenant and project boundaries (made load-bearing by the shared acquired-snapshot substrate);
- least-privilege access to AWS, database, Langfuse and model providers;
- redaction and retention for logs and traces.

Security requirements should be proportionate to the phase, but not deferred accidentally.

## Testing and eval posture

Implementation specs should distinguish **deterministic tests** from **AI evals**.

Deterministic tests should cover ordinary code paths: schema validation, event-log writes,
plan-to-config compilation, quote-presence checks, idempotency and adapter behaviour.

AI evals should begin as visibility and regression aids, then become merge-blocking only when
the dataset, scorer, threshold and owner are agreed. The architecture should stay eval-ready
(persisted judge I/O, prompt and model versions) without pretending the full eval workstream
is solved.

## Data and telemetry governance

Implementation specs should define how to avoid observability becoming a shadow data lake.
Open decisions to resolve before sensitive tracing:

- Langfuse retention policy.
- CloudWatch retention policy.
- Trace sampling strategy.
- Masking/redaction policy.
- Access control for traces and logs.
- Whether uploaded document text may appear in traces.
- Whether acquired source text may appear in traces.
- How trace examples can be promoted into eval datasets.

## Local development and CI

The backend command surface exists (task 001): `Makefile` — setup / test / typecheck / lint /
build / verify (see [harness.md](harness.md) § Tool layer). Extend it — don't fork a second
surface — when the frontend scaffold lands (a `dev` target is still expected then). CI, when
approved, must run the same `make verify` (see [environment.md](environment.md) § CI parity).

## Code style

Google-style docstrings (`Args:`/`Returns:`/`Raises:`) for public modules, classes and
functions, kept concise; trivial helpers and test functions need none. This is the binding
convention in [../../AGENTS.md](../../AGENTS.md) — repeated here only as a pointer. When the lint
surface firms up, enforce it via ruff's `pydocstyle` `google` convention rather than by review.

## Accessibility

User-facing implementation should target WCAG 2.2 AA unless explicitly scoped otherwise.
Specs should cover keyboard navigation, focus states, accessible names, semantic HTML,
contrast and non-colour-only status indicators.

## Nesta alignment

Use Nesta engineering guidance as a source of reusable principles, not as a stack prescription.

For Policy Atlas v3.0 this means:

- keep security, privacy and data-handling risks visible from the first implementation slice;
- separate local, staging and production environments rather than relying on ad hoc configuration;
- prefer reproducible setup, CI checks and documented verification commands once the scaffold exists;
- use proportionate maturity: early slices may be lightweight, but should not create paths that are hard to secure, monitor or maintain later;
- design logging, tracing and observability deliberately, without turning traces or logs into canonical product audit state;
- maintain accessibility expectations for user-facing UI, targeting WCAG 2.2 AA unless explicitly scoped otherwise;
- keep maintenance in view: avoid unnecessary abstractions, hidden stack assumptions, orphaned tools and undocumented operational dependencies.

Do not import Nesta stack defaults that conflict with Policy Atlas decisions. In particular, do not assume Rails, Heroku-first deployment, Qdrant/Pinecone, Airflow/Orbit, or any generic template where the Policy Atlas architecture has already chosen a different direction.
