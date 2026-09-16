# 034 — Metabase staging deployment

Status: implemented and verified on 2026-09-01. The owner approved implementation through the request to review, plan and implement the staging deployment.

## Outcome

Deploy a staging-only Metabase service at `metabase.v3.policyatlas.uk`. Metabase has a dedicated PostgreSQL application database and can reach the Policy Atlas database over private networking, without receiving database credentials or table grants in this slice.

## In scope

- A private ECS Fargate Metabase service behind the existing HTTPS ALB.
- Route 53 routing and an ALB health check for Metabase.
- An ALB source-IP allowlist loaded from an existing SSM `StringList` parameter.
- A dedicated encrypted RDS PostgreSQL instance for Metabase state.
- Secrets Manager-backed database credentials and encryption secret.
- CloudWatch application logs and conservative one-task deployment settings.
- A network-only path to the Policy Atlas database for a later curated read role.
- Staging configuration, deployment preflight checks, CDK tests and operator notes.

## Out of scope

- Production enablement.
- Cognito, SSO, embedding or changes to Policy Atlas authentication.
- Policy Atlas schema changes, analytics views, row-level security or database grants.
- Automatic creation of a Policy Atlas analytics user or source connection.
- Dependency, CI or public Policy Atlas API changes.
- Any IP restriction on the Policy Atlas application or its API.

## Constraints and decisions

- Metabase's application database is separate from the Policy Atlas source database.
- The service runs in private subnets and receives traffic only from the shared ALB.
- The Metabase listener rule requires both its hostname and a source CIDR from
  `/policy_atlas_v3/metabase/allowed_cidrs`; the Policy Atlas listener rule is
  unchanged.
- The allowlist contains one to three IPv4 and/or IPv6 CIDRs. AWS evaluates the
  address that connects to the ALB, not `X-Forwarded-For`, so proxied users must
  allowlist the proxy's egress range. Universal `/0` ranges are rejected.
- The Metabase database receives traffic only from the Metabase service security group.
- The Metabase application database requires TLS and the client explicitly requests it.
- The Policy Atlas database receives a port-5432 rule from the Metabase service security group, but no credentials or permissions are created.
- First-admin setup is an attended staging operation immediately after deployment.
- Removing the stack snapshots the database and retains the encryption secret.

## Known follow-up

Before adding Policy Atlas as a Metabase data source, design and approve curated owner-safe analytics views (or equivalent row-level controls), create a least-privilege login, store it in Secrets Manager, and complete the connection through Metabase administration.
