# Verification: 030-rds-jumpbox

Public-safe evidence for the jumpbox hardening slice.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make -C infra test` | pass | 43 passed in 2.71 s. |
| `git diff --check` | pass | No whitespace errors. |

## Checks beyond the build

- **Deterministic synth tests:** fixed-target Session document, security-group
  edges, IMDSv2/no-public-IP posture, local-only mode, imported-cluster SG
  override, invalid ports, backend-to-Aurora route independence, staging NAT
  selection, production endpoint ownership, private DNS, SG attachment, and
  fail-closed connectivity validation.
- **Manual AWS checks:** not run; this task does not deploy. The owner must
  verify managed-node registration, document acceptance, tunnel establishment,
  least-privilege IAM, and database client connectivity after deployment.
- **AI evals:** n/a.

## End-to-end command

Not run against AWS. The generated `PortForwardingCommand` CloudFormation
output is the operator entry point documented in `JUMPBOX.md`.

## Diff summary

The construct now uses a stack-generated, fixed-target Session document; a
dedicated deny-by-default jumpbox SG; a private ARM instance with IMDSv2; and
explicit support for local-only/imported-resource modes. A separate
`SsmVpcEndpoints` construct owns the production endpoints plus both sides of
their SG relationship; the jumpbox receives typed connectivity and only
attaches the managed-node SG. Aurora's fck-nat rule is removed while migration,
jumpbox, and BackendSG rules remain. Operator docs describe both environment
paths and the independent backend route.

## Review findings

- **Contract verifier:** pending human review.
- **Code review:** iterative review found and addressed arbitrary remote-target
  parameters, missing source egress, local-mode endpoint dereference, document
  name collisions, imported-resource SG assumptions, invalid `t4a.nano`, subnet
  ambiguity, and missing IMDSv2 enforcement.
- **Security review:** fck-nat database trust removed; custom document and IAM
  boundary documented; port-forward contents explicitly not claimed as logged.
- **Adversarial review:** pending human review/live initial test.

## Rubric status

All deterministic implementation criteria pass. The task remains pre-deploy
because live AWS and IAM verification intentionally stays with the owner.

## Intent & assumptions

- Staging private subnets keep their existing default route through fck-nat for
  public SSM endpoints; production uses PrivateLink with private DNS.
- VPC-local routing remains preferred for Aurora private addresses, independent
  of the default NAT route.
- The owning identity layer will restrict `ssm:StartSession` to the generated
  document and jumpbox instance.

## Known unverified items

- CloudFormation creation and update of the custom Session document in the
  target AWS account.
- SSM Agent registration and a real remote-host port-forward session.
- The final engineer IAM role and database credential privilege level.
- The deployed production SSM Agent version (the endpoint design assumes the
  current `ssmmessages` path and deliberately omits legacy `ec2messages`).
- Concrete production entries are not yet present in the three environment
  config files; their account-specific domain and capacity values were not
  inferred by this slice. The production-like synth fixture exercises
  `ssm_connectivity: interface_endpoints` directly.

## Public safety

No live identifiers, endpoints, credentials, secrets, or session output are
recorded here.

## Deferred work

Live deployment and IAM identity isolation are owner-operated follow-up checks,
not silently claimed by this implementation slice.
