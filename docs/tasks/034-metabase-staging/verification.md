# Verification

Verified locally on 2026-09-01.

Allowlist extension verified locally on 2026-09-16.

## Evidence

- `make -C infra test` — **pass**, 52 CDK tests. The assertions cover the
  application database, TLS request, Secrets Manager injection, network rules,
  private ECS networking, migration-safe deployment settings, health check,
  listener rule, DNS and log retention.
- `make deploy-check DEPLOY_ENV=staging` — **pass**; configuration is complete
  and internally consistent.
- Staging `infra/app.py` entrypoint synthesis with an isolated JSII cache and
  dummy account context — **pass**; all enabled staging stacks synthesized.
- `make verify` — **pass** after starting the documented local Postgres
  prerequisite: 2,179 backend tests, mypy, Ruff, package build, 51 CDK tests,
  repository guards, 415 frontend tests, frontend typecheck/lint and production
  build. A post-gate focused rerun added the staging-only config assertion and
  passed all 52 CDK tests.
- `git diff --check` — **pass**.
- `make -C infra test` after the allowlist extension — **pass**, 65 tests. The
  synthesized rule requires the Metabase hostname plus an SSM-resolved
  `source-ip` condition; the Policy Atlas application rule remains unchanged.
  Validator tests cover valid IPv4/IPv6 lists, wrong SSM type, empty and
  over-limit lists, whitespace, invalid CIDRs, non-canonical networks, and
  universal `/0` ranges.
- `make deploy-check DEPLOY_ENV=staging` after the allowlist extension —
  **pass**. Live AWS validation remains a pre-CDK deployment gate because the
  offline check intentionally does not require credentials.
- `make deploy-build-guard-test` after the allowlist extension — **pass**;
  guard-only builds still exit before any live AWS lookup.
- `git diff --check` after the allowlist extension — **pass**.

The final build emitted only the repository's existing font-resolution and
frontend chunk-size warnings.

## Source checks

- Metabase's current documentation recommends PostgreSQL for the application
  database and distinguishes it from connected data sources.
- Metabase documents `MB_ENCRYPTION_SECRET_KEY` as the supported key for
  encrypting stored connection details and requires at least 16 base64
  characters; this stack generates 64 alphanumeric characters and retains the
  secret.
- The exact Docker image tag `v0.63.15.7` existed when checked on 2026-09-01.

## Live evidence still required

- No AWS deployment was performed. Deploy through the attended staging runbook,
  immediately claim the first administrator account, and confirm target health
  plus CloudWatch logs.
- Policy Atlas source onboarding remains outside this slice pending approval of
  curated analytics views and a least-privilege database role.
