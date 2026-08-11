# Rubric: 030-github-deployment

- [x] Staging is manual-only and cannot deploy a non-`dev` ref.
- [x] Production deploys only a published stable Release tag contained in `dev`.
- [x] Each deploy uses its matching protected GitHub Environment.
- [x] OIDC uses no static AWS access keys and grants only `id-token: write` plus
      `contents: read` to deploy jobs.
- [x] Expected AWS account is checked and masked.
- [x] Concurrent deploys to one environment queue; an active deploy is not cancelled.
- [x] Workflows call Makefile targets, which call the authoritative deploy wrapper.
- [x] Missing production CDK configuration fails before OIDC authentication.
- [x] Environment-derived deploy/Cognito values preserve staging synth behavior.
- [x] Runbook covers GitHub/AWS setup, separate-account constraint, first deployment,
      recovery, and rollback.
- [x] Focused tests and workflow syntax/semantic checks pass.
- [x] No account IDs, role ARNs, credentials, or secret values are committed.
