# Plan: 030-github-deployment

1. Preserve task 026's authoritative deploy sequence and expose environment-aware,
   Makefile-owned `deploy-check`, `deploy-update`, and `deploy-bootstrap` commands.
2. Derive deploy region, public/API domains, app-secret name, Cognito URLs/domain
   prefix, and tracing label from the selected committed CDK configuration while
   preserving the live staging template.
3. Add a manual staging workflow with a pre-auth `dev`-ref/config validation job,
   then a protected `staging` deploy job using OIDC.
4. Add a stable published-Release workflow with a pre-auth ancestry/config
   validation job, then a protected `production` deploy job using OIDC.
5. Use environment-scoped secrets `AWS_ROLE_ARN` and `AWS_ACCOUNT_ID`, mask the
   account, restrict GitHub token permissions, and serialize without cancellation.
6. Document GitHub Environment restrictions, AWS OIDC trust subjects, deployment
   permissions, production-config/first-deploy preconditions, and rollback.
7. Run syntax, focused deployment, infra, and repository verification; inspect the
   composed workflow semantics and record evidence.
