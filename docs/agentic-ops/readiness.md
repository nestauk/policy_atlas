# Readiness

What the project has settled, what is still open, and the concerns that every slice must keep in
view. This file describes the repository as it is now. When a slice settles an open item, update
this file in the same pull request (PR).

The approval gates for each slice (schema, auth, runtime egress, dependencies, CI (continuous
integration), production config, public interfaces) are in [AGENTS.md](../../AGENTS.md) and the
hard gates of the [task-cycle](../../.claude/skills/task-cycle/SKILL.md) skill.

## Settled

- **Specs.** The sources under `docs/specs/sources/` are frozen
  ([ADR 0002](../adr/0002-spec-governance.md); an ADR is an architecture decision record). The
  living specs are under `docs/specs/system/` and `docs/specs/capabilities/`. Each capability's
  `components.md` gives each component's inputs, outputs, tools and gates. Open seams are
  registered in `docs/deferred.md`.
- **Backend stack.** Postgres with pgvector (Amazon Aurora in the cloud), LangGraph, and two model
  routes, `openai-direct` and `bedrock`
  ([ADR 0041](../adr/0041-bedrock-inference-route-and-model-route-file.md)). Document ingest in
  the cloud runs off the request path, through a queue and an AWS Lambda function
  ([ADR 0043](../adr/0043-queued-ingest-document-store-sql-retrieval-step-timeouts.md)).
- **Frontend.** Vite, React, TypeScript and pnpm, under `frontend/`
  ([ADR 0024](../adr/0024-web-app-architecture.md)).
- **Infrastructure.** AWS CDK (infrastructure as code) under `infra/`
  ([ADR 0026](../adr/0026-deployment-architecture.md)).
- **Auth and tenancy.** OpenID Connect (OIDC) sign-in through Amazon Cognito, and organisations
  as the tenant boundary ([ADR 0033](../adr/0033-organisation-tenancy-and-global-admin-read.md)).
- **Limits and the firewall.** A run cap and a yearly task quota for each user
  ([ADR 0045](../adr/0045-per-user-run-cap-task-quota-offboarding.md)). A web application
  firewall (WAF) on the load balancer, and a CAPTCHA on the waitlist form
  ([ADR 0047](../adr/0047-waf-on-the-load-balancer-and-waitlist-captcha.md)).
- **Accounts and operations.** An operations service behind the office allowlist, with its own
  pages and its own database login, and self-signup for one email domain
  ([ADR 0046](../adr/0046-ops-service-ops-pages-self-signup-and-ops-database-login.md)).
- **Command surface.** The root `Makefile` (see [harness.md](harness.md) § Tool layer).
- **Prompt governance.** The code is the source of truth for prompts. The app never fetches a
  prompt from Langfuse ([ADR 0038](../adr/0038-langfuse-observability-boundaries.md),
  decision 3). Prompt text is hash-pinned (`make prompt-guard`). Rules:
  `docs/specs/system/prompting.md`.
- **Observability.** structlog for application logs, the `event_log` table as the audit record,
  Langfuse for model-call traces (ADR 0038), CloudWatch for cloud logs (retention is set per log
  group in `infra/`).
- **Verification.** Each task has a `verification.md` from `docs/tasks/_templates/`, and the
  `task-cycle-review` skill runs the review stack.
- **Accessibility.** User-facing screens target WCAG 2.2 AA (Web Content Accessibility
  Guidelines; `PRODUCT.md` § Accessibility & Inclusion).

## Open decisions

- **Trace and telemetry governance.** No decision yet on:
  - Langfuse retention;
  - trace sampling;
  - masking and redaction in traces;
  - who can read traces and logs;
  - whether uploaded or acquired document text may appear in traces;
  - how trace examples become evaluation datasets.
- **Docstring check.** The Google-style docstring rule in AGENTS.md is not checked by a tool.
  `ruff` has no `D` (pydocstyle) rules enabled. The `google` convention would enforce it.

If a slice depends on an open item, resolve it, put it out of scope, or record the accepted risk
in the contract. Do not build on an unstated assumption.

## Concerns for every slice

- **Security.** A contract that touches these must say how it handles them:
  - prompt injection from uploaded and acquired documents;
  - tool-call injection;
  - retrieval poisoning;
  - leaks through prompts, traces, logs, search queries or model-provider calls;
  - secrets and credentials;
  - tenant and project boundaries;
  - least-privilege access to AWS, the database, Langfuse and model providers;
  - redaction and retention for logs and traces.

  Make security proportionate to the slice, but do not defer it by accident.
- **Tests and evaluations.** Deterministic tests cover ordinary code paths. AI evaluations
  (evals) start as visibility and regression aids. An eval blocks a merge only when its dataset,
  scorer, threshold and owner are agreed. Keep the system eval-ready: persist judge input and
  output, and prompt and model versions.
- **Nesta engineering guidance.** Use it for principles, not for the stack. Do not import Nesta
  stack defaults that conflict with this project's decisions (for example Rails, Heroku-first
  deployment, Qdrant or Pinecone, Airflow or Orbit).
