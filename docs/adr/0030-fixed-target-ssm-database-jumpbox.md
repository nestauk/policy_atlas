# ADR 0030 — Fixed-target SSM database jumpbox

**Status:** Accepted — 2026-08-11 (owner-requested hardening). Contract:
`docs/tasks/030-rds-jumpbox/contract.md`.

## Context

ADR 0026 used the fck-nat EC2 instance for both NAT and engineer database
access. That made Aurora trust an internet-egress appliance and required the
AWS-managed remote-host forwarding document, whose caller chooses the hostname
and port. Dedicated SSM interface endpoints are not cost-effective for staging,
but production requires PrivateLink. Nesta isolates the environments in
separate AWS accounts, so identical physical names remain account-scoped.

## Decision

1. Provision a dedicated, no-ingress `t4g.nano` jumpbox in a
   `PRIVATE_WITH_EGRESS` subnet, with no public IP and IMDSv2 required.
2. Give its security group only database-port egress to Aurora. Staging adds
   public HTTPS egress through NAT. Production attaches a managed-node SG that
   can reach only the private SSM endpoint SG. Aurora trusts the jumpbox SG; it
   no longer trusts the fck-nat SG.
3. Create a stack-unique custom Session document. Its content fixes the Aurora
   endpoint and remote database port and exposes only `localPortNumber` as a
   caller parameter. Engineer IAM must allow `StartSession` only on this
   document and instance; identity policies remain outside the reusable
   construct.
4. Keep application and migration connectivity unchanged. Their ENIs reach
   Aurora over the VPC's implicit local route and their independent SG rules;
   the NAT route is only for internet-bound traffic.
5. Keep interface endpoints VPC-scoped in a separate `SsmVpcEndpoints`
   construct owned by `NetworkStack`. It creates `ssm` and `ssmmessages`, their
   endpoint SG, and a pre-wired managed-node SG. The jumpbox accepts a typed
   connectivity policy and never creates or mutates endpoints.

## Consequences

- Staging depends on the NAT instance for SSM registration and session control.
  Production depends on two interface endpoint services in each selected AZ
  and has no public SSM fallback from the jumpbox.
- The jumpbox cannot be used to forward to arbitrary VPC hosts unless an
  operator grants access to another Session document.
- Session lifecycle API calls are auditable, but Session Manager cannot log the
  contents of port-forwarded database traffic; database audit controls remain
  the query-level evidence source.
- A stack deploy and least-privilege identity-policy test remain required before
  the path is called live-verified.

## Rollback

Before deployment, rollback is a code revert. After deployment, restore the
previous fck-nat-to-Aurora rule only if emergency access is required, then remove
the jumpbox/document through a normal CloudFormation update. Backend and
migration access do not need to change in either direction.
