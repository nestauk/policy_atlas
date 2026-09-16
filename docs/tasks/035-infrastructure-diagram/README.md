# Policy Atlas infrastructure diagram

Presentation assets for the Imagine Grant Round 2 application:

- [PDF](../../../output/pdf/policy-atlas-infrastructure.pdf)
- [High-resolution PNG, 3840 x 2160](../../../output/pdf/policy-atlas-infrastructure.png)
- [Editable SVG](../../../output/pdf/policy-atlas-infrastructure.svg)

The SVG keeps editable text, vector shapes, connectors and embedded official AWS
SVG icons. The PDF retains vector text and shapes, with AWS-supplied raster icons.
All exports use the same 16:9 composition. Insert the PNG directly into an
application document or presentation; use the SVG for layout changes.

## Suggested figure caption

Policy Atlas runs its core application and evidence database on AWS in London.
Researchers access a web application delivered through Amazon CloudFront and S3,
with Amazon Cognito authentication. An ECS Fargate service runs the research
engine in private subnets and stores evidence, findings and audit records in
Amazon Aurora PostgreSQL. Outbound connections support AI processing, evidence
discovery and tracing. The diagram represents the architecture configured in the
repository as reviewed on 8 September 2026.

## Proposed Bedrock variant

- [Bedrock proposal PDF](../../../output/pdf/policy-atlas-infrastructure-bedrock-proposed.pdf)
- [Bedrock proposal PNG](../../../output/pdf/policy-atlas-infrastructure-bedrock-proposed.png)
- [Bedrock proposal editable SVG](../../../output/pdf/policy-atlas-infrastructure-bedrock-proposed.svg)

This second version adds an official Amazon Bedrock icon and a teal dashed
connection, explicitly marked proposed and not deployed. The existing Fargate
research engine would invoke the Bedrock Runtime API through existing EC2 NAT
egress. The application would authenticate with temporary ECS task-role
credentials, with model-scoped invocation permissions added to that role.
The diagram retains OpenAI as the current route; it does not imply automatic
fallback or simultaneous use of both providers.

Implementation would require a Bedrock inference adapter, model selection,
appropriate invocation/streaming permissions and regression evaluation before
migrating workloads. Embedding changes would also require a compatibility and
re-embedding plan. London has a Bedrock Runtime endpoint, but model availability
and inference-profile routing must be checked for the chosen models; the diagram
does not promise London-only inference. The configured main platform remains
in London. See [Bedrock endpoint availability](https://docs.aws.amazon.com/bedrock/latest/userguide/endpoints-region-availability.html),
[IAM authentication](https://docs.aws.amazon.com/bedrock/latest/userguide/security-iam.html)
and [inference permissions](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-prereq.html).

An optional later design could use a Bedrock Runtime interface VPC endpoint with
AWS PrivateLink to avoid NAT for Bedrock requests. That endpoint is not part of
this minimal proposed hookup; evidence providers would still need outbound
connectivity. See [Bedrock private connectivity](https://docs.aws.amazon.com/bedrock/latest/userguide/vpc-interface-endpoints.html).

Suggested caption: **Policy Atlas's existing AWS platform with a proposed Amazon
Bedrock integration. The research engine would access foundation models and
embedding models through an IAM-authorized Bedrock API connection. The teal
dashed route represents planned work, subject to model selection and evaluation;
OpenAI is the current inference provider.**

Rebuild this version using the `render-bedrock` Makefile target. The original
PDF, PNG and SVG are preserved separately.

## Source traceability

| Diagram element | Repository evidence |
|---|---|
| AWS London; environment selection | `infra/app.py`, `infra/pa_config.json`, `infra/network_config.json`, `infra/db_config.json` |
| Separate staging and production accounts | ADR 0026, 2026-08-11 automation amendment; fixed resource names require account separation |
| Route 53, CloudFront and private S3 origin with OAC | `infra/infra/policy_atlas_stack.py` |
| React / Vite static frontend | `frontend/package.json`, ADR 0026 decision 5; the stack's old Next.js header comment is stale |
| Cognito authorization-code sign-in | `infra/infra/cognito_auth.py`, `frontend/src/auth/OidcAuthProvider.tsx`; PKCE provided by the OIDC client |
| VPC, subnet groups, shared ALB and EC2 NAT | `infra/infra/network_stack.py`, `infra/network_config.json` |
| Private Fargate task, 2 vCPU and 8 GiB | `infra/infra/policy_atlas_stack.py`, `infra/pa_config.json` |
| Exactly one API task after deployment | `scripts/deploy.sh` scale-up step; ADR 0026 decision 3; `docs/specs/system/web-api.md` deployment posture |
| Aurora PostgreSQL, one provisioned writer, zero readers | `infra/infra/database_stack.py`, `infra/db_config.json` |
| Database encryption and seven-day backup retention | `infra/infra/database_stack.py` |
| Evidence, findings, durable audit records | `docs/specs/system/data-model.md`, `docs/specs/system/web-api.md` |
| OpenAI and Langfuse integration | `infra/infra/policy_atlas_stack.py`, `backend/src/policy_atlas/core/tracing.py` |
| OpenAlex and Overton | `backend/src/policy_atlas/evidence_base/sourcing/search_live.py` |
| Source-document retrieval | `backend/src/policy_atlas/evidence_base/sourcing/fetch_live.py` |
| Secrets injection and CloudWatch logging | `infra/infra/policy_atlas_stack.py` |
| IAM, SSM configuration and database administration | Infrastructure stacks; `infra/infra/components/nesta_db_jumpbox.py` |
| GitHub Actions, OIDC, CDK and migration sequence | `.github/workflows/deploy-staging.yml`, `.github/workflows/deploy-production.yml`, `scripts/deploy.sh` |

## Scope and interpretation

This is a repository-based architecture view, not a live AWS inventory or a
deployment-health assessment. The checkout was based on `91d275d` and contained
pre-existing uncommitted staging analytics work. No AWS account or secret was
queried. Configuration expresses encryption and backup settings; this task did
not verify their application in a running account.

CloudFront and Route 53 are shown as global services; the regional workload is
London. The CloudFront TLS certificate is provisioned in `us-east-1`; the ALB
certificate is regional. External providers have independent hosting locations:
the figure does not claim all data processing remains in the UK.

Subnet boxes group logical roles and do not enumerate resources per Availability
Zone. CDK sets a maximum of three AZs. NAT uses EC2 instances via `fck-nat`, not
the managed NAT Gateway service. The diagram does not infer a NAT count from a
stale code comment. Internet gateways, route tables and security-group edges are
abstracted. Backend ingress is restricted to the ALB; database ingress is
restricted to explicitly permitted security groups.

The runtime is one Fargate task, with concurrency inside that process. Aurora has
one writer and no read replicas. The figure therefore makes no claim of active
application replicas, automatic horizontal scaling or a standby database
compute instance. Core application data lives in PostgreSQL; S3 here holds static
web assets, not an invented evidence lake. There is no separate queue or worker
fleet in the configured design.

The backend validates Cognito access tokens using issuer/JWKS configuration.
OAuth token exchange and JWKS retrieval are abstracted from the visual. Secrets
Manager injects credentials through the ECS execution role; the application
does not need a runtime secret-read role. SSM administration uses an EC2
database jumpbox; it is not the NAT instance.

Supporting details omitted for presentation clarity: AWS Certificate Manager,
CDK container-image assets in ECR, the one-shot Fargate migration task, a private
font-staging bucket, deployment-time secret-composition Lambda, and the SSM
jumpbox. Licensed font binaries are not included in these artefacts.

### Staging-only analytics extension

The current checkout also configures Metabase on private ECS Fargate behind the
shared ALB, with a separate encrypted RDS PostgreSQL application database. It is
enabled only for staging. Network access to the Policy Atlas database is allowed,
but the task contract does not establish source credentials, grants or a working
analytics connection. It is therefore omitted from the core platform figure.
Sources: `infra/app.py`, `infra/infra/analytics_stack.py`,
`docs/tasks/034-metabase-staging/contract.md`.

### Future AWS AI integration

Amazon Bedrock is recorded as deferred in `docs/deferred.md`. It is absent from
the original current-architecture figure and explicitly proposed in the variant
requested by the owner. This visual proposal does not change system intent or
authorize deployment changes.

## Icon provenance

Icons are unmodified assets extracted from the official
[AWS Architecture Icons package](https://aws.amazon.com/architecture/icons/),
release `07312026`. AWS permits these assets in architecture diagrams and
presentations. AWS icons and marks belong to Amazon Web Services.

Download source:
`https://d1.awsstatic.com/onedam/marketing-channels/website/public/shared/architecture-icon-release/Icon-package_07312026.5846e92413caa21490223536cc97f1269e44fa92.zip`.
`assets/manifest.json` records the original archive paths for each included icon.

## Rebuild

Run `make -C docs/tasks/035-infrastructure-diagram render` from the repository
root. Set `PYTHON` to a runtime containing ReportLab and `PDFTOPPM` to Poppler if
they are not available on PATH. No application dependencies are changed.

If a bundled Poppler reports a missing Fontconfig configuration or unwritable
cache, set `FONTCONFIG_FILE` to a local Fontconfig file that points to the
runtime's fonts and a writable temporary cache directory. This is a renderer
environment setting, not a product configuration change.
