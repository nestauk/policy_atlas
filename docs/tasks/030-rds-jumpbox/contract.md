# Task contract: 030-rds-jumpbox

One hardening slice for the developer database-access path.

> **Status:** approved. Contract and implementation direction approved
> 2026-08-11 · owner, through the requested review/fix iterations · ADR:
> [0030](../../adr/0030-fixed-target-ssm-database-jumpbox.md).

## Goal

Give engineers IAM-gated GUI/CLI access to Aurora without public ingress or
permission to choose an arbitrary remote forwarding target. Staging reaches
SSM through NAT; production uses VPC interface endpoints. Keep Policy Atlas
backend and migration database routes independent.

## Deliverable

- A reusable CDK jumpbox construct in a private-with-egress subnet.
- A VPC-scoped endpoint construct that exposes a pre-wired managed-node SG.
- A generated Session document that fixes the Aurora hostname and remote port.
- Least-purpose jumpbox networking and removal of fck-nat database ingress.
- Synth tests and operator guidance covering the security and routing invariants.

## Read first

- [`infra/DEPLOYMENT.md`](../../../infra/DEPLOYMENT.md), especially developer DB
  access and the deploy invariant.
- Task 026's original infrastructure intent in
  [`contract.md`](../026-infra-deployment/contract.md).

## Scope / Out of scope

- **In:** jumpbox and SSM endpoint constructs, environment-selected SSM
  connectivity, Aurora/fck-nat security-group wiring, infra synth tests,
  jumpbox/deployment documentation.
- **Out:** engineer IAM role ownership, live deployment, optional S3/KMS/logs or
  legacy `ec2messages` endpoints, database credentials/rotation, schema,
  backend application behaviour.

## Constraints & approval gates

- Preserve the existing VPC and private-subnet topology.
- Keep endpoint lifecycle in `NetworkStack`; the jumpbox accepts connectivity
  and must not create or mutate VPC endpoint resources.
- Do not alter the independent `BackendSG` or migration SG Aurora access.
- Do not grant engineer IAM permissions in this reusable construct; document
  the required resource scoping for the owning stack/identity layer.
- No dependency, schema, auth, CI, or application public-interface changes.
- The owner explicitly requested the production-infrastructure fixes in this
  task; deployment remains a separate human-controlled action.

## Public / private boundary

CDK, synthesized-shape assertions, and generic commands are public-safe. AWS
account IDs, physical resource IDs, credentials, endpoints, and live session
evidence stay out of the repository.

## Model route

n/a — no inference or prompt surface.

## Stop conditions

Stop before a live deploy or IAM identity mutation, or if the fix would require
changing the VPC topology, backend task networking, database schema, or auth.

## Acceptance checks

- `make -C infra test` passes.
- Synth proves the Session document exposes only `localPortNumber`; its remote
  host and port are fixed.
- Synth proves Aurora allows exactly migration SG, jumpbox SG, and BackendSG on
  5432, with no fck-nat rule.
- Synth proves backend and Aurora use the same VPC/private subnet set and the
  Fargate service retains `BackendSG` with no public IP.
- Local-only and imported-cluster construct shapes synthesize.
- Staging synth contains no interface endpoints and retains NAT HTTPS egress.
- Endpoint synth contains `ssm` and `ssmmessages` with private DNS, attaches the
  managed-node SG to the jumpbox, and contains no public HTTPS fallback.
- No live deployment is claimed.

## Verification evidence expected

Record command results, synthesized invariants, diff scope, and the remaining
manual IAM/deployment checks in [`verification.md`](verification.md).

## Risk tier & review focus

**Tier 4** — this changes production security-group configuration. Focus on
fixed-target enforcement, environment-specific SSM reachability, endpoint
ownership, reusability with imported RDS resources, and non-regression of
backend routing.
