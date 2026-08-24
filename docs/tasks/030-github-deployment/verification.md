# Verification: 030-github-deployment

## Commands run

| Command | Result | Notes |
| --- | ---: | --- |
| `make verify` | pass | 2,007 backend tests; mypy; ruff; package build; 30 CDK tests; OKF/path/prompt/font/schema-drift gates; 186 frontend tests; production frontend build |
| `make -C infra test` | pass | 30 tests, including configurable Cognito domains |
| `make deploy-check DEPLOY_ENV=staging` | pass | side-effect-free, no AWS credentials |
| `make deploy-check DEPLOY_ENV=production` | expected fail | fail-closed because production entries are intentionally absent from committed CDK config |
| `bash -n scripts/deploy.sh` | pass | shell syntax |
| `make deploy-build-guard-test` | pass | existing production `VITE_*` refusal preserved |
| Ruby `YAML.load_file` over both new workflows | pass | both files parse |
| Python/PyYAML workflow assertions | pass | triggers, permissions, Environments, concurrency, account secret, prerelease gate, and full-SHA pins |
| full-SHA action-reference scan | pass | every action in the privileged workflows is immutable-SHA pinned |
| `git diff --check` | pass | no whitespace errors |

The first `make verify` attempt failed because local Postgres was not running.
`make setup` was run against the documented local `DATABASE_URL`; the complete
gate then passed. This was an environmental prerequisite, not a code failure.

`uvx zizmor` was attempted as an extra workflow-security lint, but the locally
installed uv 0.9.9 runtime panicked in macOS system-configuration code under the
sandbox before the tool ran. Workflow security was therefore checked directly as
recorded below; this unavailable optional lint is not represented as a pass.

## Checks beyond the build

- **Workflow triggers:** staging has only `workflow_dispatch`; production has only
  `release: published` and excludes prereleases.
- **Immutable refs:** staging deploys the dispatch event SHA after requiring
  `refs/heads/dev`; production deploys the Release event SHA after a full-history
  `merge-base --is-ancestor` check against `origin/dev`.
- **Credential boundary:** validation jobs have only `contents: read`; deploy jobs
  add only `id-token: write`, use the matching protected Environment, check/mask the
  expected account, and use two-hour short-lived credentials. No static keys.
- **Supply chain:** every action used by either privileged workflow is pinned to a
  full commit SHA; checkout persistence is disabled.
- **Concurrency/recovery:** each environment has a fixed concurrency group with
  `cancel-in-progress: false`; local/Actions cross-system locking remains explicitly
  deferred and documented.
- **Configuration:** the wrapper derives region/domain/API URL/app secret from the
  selected committed config; Cognito callbacks, logout URLs, hosted domain prefix,
  and Langfuse environment label are environment-derived. Staging synth stays
  byte-semantically equivalent for these values.
- **Production safety:** no account, role, domain, secret, or capacity was guessed.
  Missing production config fails in the validation job before Environment approval
  or OIDC.

## End-to-end command

No live deployment was authorized or run. The local side-effect-free boundary was:

```bash
make deploy-check DEPLOY_ENV=staging
```

## Diff summary

- Added manual staging and stable-Release production workflows with validation,
  protected Environments, serialized deploys, immutable action pins, and AWS OIDC.
- Added Makefile deploy/setup/check entry points and made the authoritative wrapper
  select/validate committed CDK environments.
- Replaced staging-only Cognito/tracing constants with committed config values while
  preserving live staging output.
- Updated ADR/runbook/deferred intent with OIDC setup, separate-account constraint,
  first-deploy/recovery/rollback, and the remaining lock seam.

## Review findings

- **Contract verifier:** production CDK config does not exist; resolved by a
  pre-auth fail-closed validation gate and explicit owner setup, never a staging
  fallback.
- **Code review:** the staging-only wrapper also hard-coded the API domain, app
  secret, Cognito URLs, and trace label; resolved from committed config with focused
  synth coverage.
- **Security review:** environment OIDC subjects no longer carry ref identity, so
  exact trust subjects, GitHub Environment branch/tag restrictions, and independent
  workflow ref checks are all required. All privileged actions were SHA-pinned;
  token permissions and checkout credentials were minimized.
- **Adversarial review:** covered wrong-branch dispatch, prerelease publication,
  arbitrary/off-`dev` Release tags, mutable tags/action tags, wrong AWS account,
  cancellation mid-migration, credential expiry mid-deploy, absent production
  config, and same-account resource collisions. Each now fails closed or is an
  explicit operational precondition.
- **Simplify:** kept two small explicit workflows rather than a reusable workflow;
  this avoids GitHub Environment secret-forwarding ambiguity and keeps each trigger
  and promotion boundary readable in one file.
- **OKF validate:** pass, 110 concepts and 0 violations.

## Rubric status

All repository-side rubric items are satisfied. Remote GitHub/AWS setup and the
production config/first deploy are intentionally operational preconditions, listed
below rather than claimed as verified.

## Intent & assumptions

- Staging and production target separate AWS accounts because the existing CDK has
  fixed v3 stack/resource names and SSM namespace.
- A production promotion is a published stable GitHub Release. A prerelease is not
  production, even though GitHub emits `published` for it.
- Production rollback is a new reviewed Release at a chosen prior commit, not a
  moved/reused tag.

## Known unverified items

- GitHub Environments, reviewer/branch/tag protections, and Environment secrets.
- AWS OIDC providers, exact issued claims, trust policies, role max-session duration,
  and least-privilege permissions.
- Reviewed `production` entries in all three CDK config files.
- Production bootstrap preconditions and first attended deployment.
- Live staging or production Actions run.
- Optional `zizmor` lint (local uv runtime crash described above).

## Public safety

Pass. No account IDs, role ARNs, credentials, secret values, live resource IDs, or
licensed font files were added. IAM examples contain placeholders only.

## Review handoff

- Confirm actual GitHub OIDC `sub` claims before creating each exact AWS trust rule;
  organisation immutable-ID/custom claim templates can change the default shape.
- Confirm production's domain, capacity, app-secret name, unique Cognito domain
  prefix, and separate AWS account before adding config.
- Validate the role policy against a CDK diff and one attended staging workflow run.
- After bootstrap, exercise one no-op production update before relying on a Release.
- **Knowledge candidates:** Environment-based OIDC replaces ref in `sub`, so ref
  authorization must be enforced by Environment protection plus workflow logic;
  job concurrency is not a distributed deploy lock; credential lifetime should
  exceed the job timeout so invalid role configuration fails before deployment.

## Deferred work

- Remote Environment/IAM provisioning and production configuration remain
  owner-led operational setup.
- A real cross-system deploy lease plus Alembic advisory lock remains in
  `docs/deferred.md`.
