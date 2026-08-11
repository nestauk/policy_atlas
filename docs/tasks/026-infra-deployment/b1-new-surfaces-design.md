# B.1 design — Cognito · CloudFront/cert · SSM tunnel (task 026)

Lead-authored seam design (plan B.1). B.2/B.3 implement against this; the security
lane reviews the resulting diffs at step 7. References: contract scope items 4–6,
plan pins 3, 10, 12, 15.

## 1. Cognito (the one fresh auth surface)

**Placement:** new construct file `infra/infra/cognito_auth.py` (class `CognitoAuth`,
a `Construct`), instantiated by `PaV3AppStack`. Rationale: it wires directly into the
API task env and frontend build args (same stack's consumers); `RemovalPolicy.RETAIN`
makes stack membership safe — an app-stack destroy orphans the pool intact (rollback
plan already treats pool deletion as explicit-owner-sign-off-only).

**User pool** (smallest pool satisfying RS256/JWKS verification):
- `self_sign_up_enabled=False` (operator-created users only — contract pin)
- `sign_in_aliases=email`, `auto_verify=email` (operator-created accounts still
  need a verified email for recovery)
- `account_recovery=EMAIL_ONLY`; password policy: construct defaults; MFA off
- `removal_policy=RemovalPolicy.RETAIN` (contract pin — recreation mints new `sub`s
  and orphans owner-scoped projects)
- No federation, no custom attributes, no triggers, no advanced security add-ons

**SPA app client** (code + PKCE):
- `generate_secret=False` (public client)
- OAuth: authorization-code grant only; scopes `openid email profile`
- `callback_urls=["https://v3.policyatlas.uk", "https://v3.policyatlas.uk/"]`
  (frontend defaults `redirect_uri` to `window.location.origin` — no trailing
  slash — but both forms registered since Cognito string-matches exactly)
- `logout_urls` — same two values (hosted-UI sign-out returns to the app origin)
- Token validity: construct defaults (access/ID 60 min, refresh 30 days);
  `react-oidc-context` silent refresh covers the short access token
- No localhost URLs: local dev is the dev issuer, never the real pool

**Hosted UI domain:** Cognito prefix domain, `policy-atlas-v3` (globally unique
prefix; if taken at deploy time, fall back to `policy-atlas-v3-<account-suffix>` —
a config-time constant, not code)

**Outputs** (SSM `/policy_atlas_v3/auth/*` + direct same-stack wiring):
| Value | SSM key | Consumer |
|---|---|---|
| pool id | `user_pool_id` | ops/debug |
| issuer `https://cognito-idp.eu-west-2.amazonaws.com/{pool_id}` | `issuer` | API env `OIDC_ISSUER` (direct); frontend build arg `VITE_OIDC_AUTHORITY` (via deploy.sh) |
| JWKS URL `{issuer}/.well-known/jwks.json` | `jwks_url` | API env `OIDC_JWKS_URL` (direct) |
| app client id | `client_id` | API env `OIDC_CLIENT_ID` (direct); frontend build arg `VITE_OIDC_CLIENT_ID` (via deploy.sh) |
| hosted domain | `hosted_domain` | ops/debug |

## 2. PaV3CertStack + CloudFront (pins 3, 10)

**`infra/infra/cert_stack.py`** — `PaV3CertStack`, env region `us-east-1` (same
account): one DNS-validated `acm.Certificate` for `v3.policyatlas.uk` (apex only —
the ALB's regional wildcard `*.v3.policyatlas.uk` + apex SAN covers the API host),
hosted zone via `HostedZone.from_lookup`. App wires it with
`cross_region_references=True` on both stacks (CDK-managed SSM replication).

**Frontend hosting (in `PaV3AppStack`):**
- Private `s3.Bucket` (all public access blocked, no website hosting) for the SPA
- `cloudfront.Distribution` with `S3BucketOrigin.with_origin_access_control`
  (OAC, not legacy OAI), `default_root_object="index.html"`,
  `domain_names=["v3.policyatlas.uk"]`, certificate from `PaV3CertStack`
- SPA fallback: `error_responses` 403→`/index.html` 200 and 404→`/index.html` 200
- Caching: default behaviour `CACHING_OPTIMIZED`; additional behaviour for
  `/index.html` with a short-TTL cache policy (max 60 s) so deploys propagate even
  before the invalidation lands
- Route53: A + AAAA alias at the apex → CloudFront target (the API `ARecord` to the
  ALB is untouched)
- **Font bucket:** second private `s3.Bucket` (auto-named; `RemovalPolicy.DESTROY`,
  fonts are re-uploadable); never referenced by the distribution — fonts enter the
  SPA via deploy-time injection into `frontend/public/fonts/` before `vite build`
  (plan pin 10), so they ship inside the SPA bucket like any other asset

**Deploy SSM exports** (extends pin 12's `/policy_atlas_v3/deploy/*`):
`frontend_bucket_name` · `fonts_bucket_name` · `distribution_id` ·
`migration_task_def_arn` (B.3) — joining `private_subnet_ids`, `migration_sg_id`,
`cluster_arn` from Phase A.

## 3. SSM tunnel recipe (pin 15 — D.2 documents this verbatim)

> **Historical design:** task
> [`030-rds-jumpbox`](../030-rds-jumpbox/contract.md) superseded this fck-nat
> tunnel on 2026-08-11 with a dedicated fixed-target jumpbox.

Prereqs: AWS CLI + session-manager-plugin; IAM allowing `ssm:StartSession` on the
fck-nat instance; the fck-nat SSM role + fck-nat→Aurora 5432 ingress landed in A.2.

```bash
# 1. fck-nat instance id (the only EC2 instance in the v3 network stack)
INSTANCE_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:aws:cloudformation:stack-name,Values=PaV3NetworkStack" \
            "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)

# 2. DB endpoint + credentials from the generated cluster secret
DB_SECRET=$(aws ssm get-parameter --name /policy_atlas_v3/db/secret_name \
  --query Parameter.Value --output text)
aws secretsmanager get-secret-value --secret-id "$DB_SECRET" \
  --query SecretString --output text | python3 -m json.tool   # host, port, password

# 3. Port-forward through the fck-nat instance (no bastion, no inbound ports)
aws ssm start-session --target "$INSTANCE_ID" \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters host=<aurora-writer-endpoint>,portNumber=5432,localPortNumber=15432

# 4. In another shell
psql "postgresql://dbadmin:<password>@localhost:15432/policy_atlas_db?sslmode=require"
```

**Warning (documented beside the recipe, contract scope item 7):** a locally booted
API pointed at Aurora is a second instance sharing the DB — the orphan sweep has no
ownership lease and will interrupt the staging service's executing walks (and vice
versa). Tunnel for psql/inspection: always fine. Local API against Aurora: only with
the staging service stopped (`aws ecs update-service --desired-count 0`).
