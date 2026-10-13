# Implementation plan

1. Record the staging-only contract, completion rubric and known authorization boundary.
2. Replace the draft CDK stack with a private, observable Fargate service, dedicated RDS PostgreSQL application database, retained runtime secrets, ALB rule and Route 53 record.
3. Wire the stack into `infra/app.py`, make enablement explicitly environment-scoped, and add deployment preflight validation.
4. Add CDK assertions for networking, secrets, health checks, logging, deployment safety and staging-only synthesis.
5. Run the repository Makefile verification targets and record evidence in `verification.md`.
6. Restrict only the Metabase listener rule with a source-IP condition resolved
   from a pre-provisioned SSM `StringList`; validate the parameter before AWS
   deployment and add focused synthesis coverage.

The owner asked on 2026-09-01 for the reviewed plan to be implemented in the same pass, so no separate pause follows this plan document.
