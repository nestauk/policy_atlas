---
type: Runbook
title: PowerUserAccess runs day-to-day CDK deploys but not bootstrap or ecs run-task
description: CDK bootstrap creates IAM roles and ecs run-task needs iam:PassRole — both exceed PowerUserAccess; ordinary cdk deploy works because CloudFormation executes through the bootstrap roles. Scope PassRole to the stack's role prefix plus iam:PassedToService.
tags: [deployment, aws, iam, cdk, runbook]
timestamp: 2026-07-28
---

# Rule

Under a PowerUserAccess-shaped operator principal (the `pa-dev` posture):

- `cdk bootstrap` **fails** — it creates IAM roles; run it once per region with an
  IAM-capable principal (026: a failed PowerUser attempt left a `DELETE_FAILED`
  toolkit stack in us-east-1 that DevOps had to clean with admin creds).
- `aws ecs run-task` (the migration step) **fails** without an explicit `iam:PassRole`
  grant. Scope it, don't blanket it:
  `Resource: arn:aws:iam::<account>:role/PaV3AppStack-*` +
  `Condition: iam:PassedToService = ecs-tasks.amazonaws.com`.
- Plain `cdk deploy` **works** — CloudFormation assumes the bootstrap execution roles,
  so the operator principal never needs the resource-level permissions itself.

# Why

The boundary is *who executes*: deploys are proxied through bootstrap-created roles;
bootstrap and `run-task` act as the caller. Both failures present late (mid-deploy) and
read like stack bugs. Found live at 026 E.1; preconditions now in
`infra/DEPLOYMENT.md` § 2.
