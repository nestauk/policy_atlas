# Task contract: 030-github-deployment

> **Status:** approved. Contract approved: 2026-08-11 · owner request in task
> thread. Plan approved: 2026-08-11 · owner request plus fail-closed production
> boundary recorded below. ADR: none — this automates ADR 0026's existing deploy
> sequence without changing the runtime architecture.

## Goal

Deploy the CDK-managed Policy Atlas application through GitHub Actions without
long-lived AWS credentials: an engineer explicitly deploys `dev` to the shared
staging environment, while a published stable GitHub Release deploys its tagged
commit to production.

## Deliverable

- A manual staging workflow that accepts only `refs/heads/dev`.
- A production workflow triggered by a published, non-prerelease GitHub Release.
- Environment-scoped GitHub OIDC authentication to AWS with no static AWS keys.
- Makefile-owned deploy entry points and a side-effect-free configuration preflight.
- Operator documentation for GitHub Environments, AWS trust policy, first deploy,
  rollback, and the currently missing production CDK configuration.

## Read first

- [ADR 0026](../../adr/0026-deployment-architecture.md)
- [Deployment runbook](../../../infra/DEPLOYMENT.md)
- [Task 026 contract](../026-infra-deployment/contract.md)
- [Web API deployment posture](../../specs/system/web-api.md)

## Scope / Out of scope

**In:** `.github/workflows/`, deployment Makefile targets, environment selection in
`scripts/deploy.sh`, environment-derived Cognito callback/domain and tracing labels,
deployment documentation, and focused infra/deploy tests.

**Out:** creating GitHub Environments or AWS IAM resources from this repository;
inventing production domain, capacity, secret names, or account identifiers;
bootstrapping production automatically; changing the stop→migrate→scale→publish
sequence; application/schema/auth semantics; release generation.

## Constraints & approval gates

- The owner's request explicitly approves the CI, OIDC, and production-release
  workflow surfaces.
- `scripts/deploy.sh` remains the authoritative deployment sequence.
- Workflow jobs receive only `contents: read` and, for deploy jobs, `id-token: write`.
- Deployments are serialized per environment and are never cancelled mid-deploy.
- Staging checks out the workflow-dispatch SHA from `dev`; production checks out the
  Release tag SHA and rejects a tag outside `dev` history.
- `release.published` also fires for prereleases, so prereleases must be excluded
  explicitly.
- Environment configuration is committed IaC. The production workflow must fail in
  a read-only preflight until reviewed `production` entries exist in all three CDK
  config files.
- Staging and production must use separate AWS accounts while the CDK's fixed v3
  resource names and SSM namespace remain shared across logical environments.
- GitHub Environment deployment-branch/tag restrictions are part of the OIDC trust
  boundary because environment-based OIDC subjects do not contain the Git ref.

## Public / private boundary

Workflow and IAM trust-policy examples are public-safe. AWS account IDs, role ARNs,
credentials, secret values, and live resource identifiers remain in GitHub
Environment secrets or AWS. Workflows must mask the AWS account ID.

## Model route

n/a — no inference or prompt-bearing work.

## Stop conditions

Do not live-deploy, create a Release, configure GitHub/AWS remotely, guess production
configuration, weaken environment/ref gates, or broaden AWS permissions without
owner action/approval.

## Acceptance checks

- `make deploy-check DEPLOY_ENV=staging` passes without AWS access.
- An unknown/missing deployment environment fails before AWS authentication.
- `bash -n scripts/deploy.sh` passes and the existing production-build guard passes.
- Infra unit tests pass, including environment-derived Cognito URLs and trace label.
- Both workflow files parse as YAML and have the intended trigger, permission,
  environment, ref/release, and concurrency gates.
- `make verify` is run in proportion to the change; any environmental failure is
  recorded rather than hidden.

## Verification evidence expected

See [verification.md](verification.md): commands, workflow semantic inspection,
diff summary, missing production configuration, remote setup checklist, and public
safety confirmation.

## Risk tier & review focus

**Tier 4** — production config/release process and cloud deployment credentials.
Focus: wrong-ref deployment, prerelease behavior, OIDC subject conditions,
credential scope, environment isolation, cancellation/concurrency behavior,
fail-closed configuration, and rollback/recovery.

## Rollback

Disable the affected GitHub Environment or revoke the OIDC role trust first to stop
new deploys. Revert the workflow commit to remove automation. If an in-progress
deployment fails after service scale-down, follow `infra/DEPLOYMENT.md` recovery:
fix-forward by rerunning the same immutable ref, or restore desired count only after
confirming migrations completed. Application rollback is a new Release pointing at
a reviewed prior commit; never rewrite an existing Release tag.
