# Policy Atlas v3 — deployment

Operator runbook for `infra/`. Deploys are operator-run (`cdk deploy`, no CI/CD
pipeline in this slice) via `scripts/deploy.sh`.

## 1. Overview

Four CloudFormation stacks:

| Stack | Region | Contents |
| --- | --- | --- |
| `PaV3NetworkStack` | `eu-west-2` | VPC, fck-nat, shared ALB + wildcard ACM cert, Cloud Map namespace exports |
| `PaV3DatabaseStack` | `eu-west-2` | Aurora Postgres cluster, generated credentials secret, `load_secret` Lambda |
| `PaV3AppStack` | `eu-west-2` | ECS Fargate API service + migration task, Cognito, S3 + CloudFront frontend, font bucket |
| `PaV3CertStack` | `us-east-1` | CloudFront's ACM certificate (AWS requires this region for CloudFront certs) |

All four synth from `infra/app.py`, driven by `-c env_name=<env>` and, on first
deploy only, `-c stage=network|all`. `scripts/deploy.sh` wraps `cdk deploy` of the
three eu-west-2 stacks plus `PaV3CertStack`, and owns the imperative steps
CloudFormation can't: migration task invocation, frontend build/sync/invalidation,
font injection.

**Public/private boundary (repo is public, AGPL-3.0):** CDK code and the
`*_config.json` files (`network_config.json`, `db_config.json`, `pa_config.json`)
are committed. The AWS account id is never committed — `app.py` reads it from
`CDK_DEFAULT_ACCOUNT` at synth/deploy time. `infra/cdk.context.json` is gitignored
(it caches `from_lookup` results, including the account id). Secrets live only in
AWS Secrets Manager, referenced by name — never in code, config JSON, or CDK
context. No IP allowlists or similar operationally sensitive values are committed
anywhere.

> `scripts/deploy.sh` did not exist at the time this document was written (a
> parallel task authors it). The flow below describes the pinned sequence from
> the plan; once the script lands, follow its actual mode names/output — this
> file should be re-checked against it.

## 2. First-deploy preconditions (gate A)

Before the first `cdk deploy` of any kind, all of the following must hold.

1. **NS delegation live.**

   ```bash
   dig NS v3.policyatlas.uk +short
   ```

   Must return the Route53 nameservers for the `v3.policyatlas.uk` hosted zone
   (looked up by name, never created by the stack). This gates **both**
   DNS-validated ACM certificates: the ALB's regional wildcard cert in
   `eu-west-2` and the CloudFront cert in `us-east-1` each wait on public
   resolution of their validation CNAMEs and hang without it.

2. **`cdk bootstrap` present in both regions used:**

   ```bash
   cdk bootstrap aws://$CDK_DEFAULT_ACCOUNT/eu-west-2
   cdk bootstrap aws://$CDK_DEFAULT_ACCOUNT/us-east-1
   ```

   (`us-east-1` is needed solely for `PaV3CertStack`.)

3. **App secret provisioned.** Secrets Manager secret `policy_atlas_v3/app`
   must exist with exactly these JSON keys (see § 5 for consumers):
   - `LANGFUSE_BASE_URL`
   - `LANGFUSE_PUBLIC_KEY`
   - `LANGFUSE_SECRET_KEY`
   - `OPENAI_API_KEY`
   - `OPENALEX_API_KEY`
   - `OPENALEX_EMAIL`
   - `OVERTON_API_KEY`

4. **`CDK_DEFAULT_ACCOUNT` exported** in the operator's shell:

   ```bash
   export CDK_DEFAULT_ACCOUNT=<account-id>
   ```

## 3. First deploy (staged bootstrap)

Bootstrap is staged, not circular: `Vpc.from_lookup` in the consumer stacks is a
synth-time context query and must not run before the VPC exists.

1. **Network stack alone:**

   ```bash
   cdk deploy -c env_name=staging -c stage=network PaV3NetworkStack
   ```

2. **All remaining stacks:**

   ```bash
   cdk deploy -c env_name=staging -c stage=all --all
   ```

   The API service is created at `desired_count=0` — nothing serves traffic yet.

3. **Gate B** (now satisfiable, since the buckets/pool exist):
   - Upload font binaries to the fonts bucket (never commit them — see § 7).
   - Create at least one operator Cognito user:

     ```bash
     POOL_ID=$(aws ssm get-parameter --name /policy_atlas_v3/auth/user_pool_id \
       --query Parameter.Value --output text)
     aws cognito-idp admin-create-user \
       --user-pool-id "$POOL_ID" \
       --username <user-email> \
       --user-attributes Name=email,Value=<user-email> Name=email_verified,Value=true \
       --desired-delivery-mediums EMAIL
     ```

     (Self-signup is disabled — operator-created users only, for the migration
     window.)

4. **Migration task** — one-shot ECS task running the backend image
   (`alembic upgrade head`), invoked with a fail-loud wait on the task's exit
   code via `describe-tasks`.

5. **Scale service to 1:**

   ```bash
   aws ecs update-service --cluster policy-atlas-v3-cluster \
     --service policy-atlas-v3-api-service --desired-count 1
   ```

6. **Frontend publish** — `vite build` (with `VITE_*` baked at build time) →
   `aws s3 sync` → CloudFront invalidation.

## 4. Steady-state deploys + the deploy invariant

**`desired_count=0` is template-pinned, permanently.** Every `cdk deploy`
therefore stops the API service as part of the CloudFormation update — stop-old
is CloudFormation-enforced, not script-hoped. The steady-state order:

1. `cdk deploy` (service → 0, new task definition registered)
2. wait for tasks stopped
3. migration task + fail-loud wait on exit code (`describe-tasks`)
4. scale to 1 (`aws ecs update-service --desired-count 1` — deliberate,
   documented drift from the template until the next deploy)
5. production build guard → fonts injection → `vite build` → `s3 sync` →
   invalidation

Abort at the first non-zero step.

**Operational caveats (verbatim from the contract):**

- Deploys interrupt executing runs — deploy in quiet windows. The hard-kill
  is recovered cleanly: the boot sweep marks interrupted runs `interrupted` on
  the next boot; this is not a data-loss condition.
- A crash means a brief outage until ECS restarts the task; the sweep recovers
  state cleanly in that case too.

## 5. Env & secret map

Generated from `settings.py`'s required/optional calls plus the direct
`os.environ` readers (`api/deps.py`, `core/tracing.py`,
`evidence_base/sourcing/search_live.py`). `LANGFUSE_HOST` is an accepted tracing
alias; deployment deliberately supplies the canonical `LANGFUSE_BASE_URL` field
instead. `POLICY_ATLAS_*` tuning and the fixture corpus are intentionally
omitted from the deployed task.

| Var | Source | Consumer file |
| --- | --- | --- |
| `APP_ORIGIN` | config value: `https://{domain_name}` | `api/settings.py` |
| `DATABASE_URL` | Secrets Manager field: DB secret `db_connection_string` | `api/settings.py`, `core/db.py` |
| `DB_MAX_OVERFLOW` | config value: `backend.db_max_overflow` | `api/settings.py` |
| `DB_POOL_SIZE` | config value: `backend.db_pool_size` | `api/settings.py` |
| `LANGFUSE_BASE_URL` | Secrets Manager field: `policy_atlas_v3/app` `LANGFUSE_BASE_URL` | `core/tracing.py` |
| `LANGFUSE_HOST` | omitted (accepted alias for `LANGFUSE_BASE_URL`) | `core/tracing.py` |
| `LANGFUSE_PUBLIC_KEY` | Secrets Manager field: `policy_atlas_v3/app` `LANGFUSE_PUBLIC_KEY` | `core/tracing.py` |
| `LANGFUSE_SECRET_KEY` | Secrets Manager field: `policy_atlas_v3/app` `LANGFUSE_SECRET_KEY` | `core/tracing.py` |
| `LOG_LEVEL` | config value: `INFO` | container runtime (no current backend reader) |
| `OIDC_CLIENT_ID` | config value: Cognito SPA client ID | `api/settings.py` |
| `OIDC_ISSUER` | config value: Cognito issuer | `api/settings.py` |
| `OIDC_JWKS_CACHE_TTL_SECONDS` | omitted (application default: 300) | `api/settings.py` |
| `OIDC_JWKS_PATH` | omitted (development issuer only; mutually exclusive with JWKS URL) | `api/settings.py` |
| `OIDC_JWKS_URL` | config value: Cognito JWKS URL | `api/settings.py` |
| `OPENAI_API_KEY` | Secrets Manager field: `policy_atlas_v3/app` `OPENAI_API_KEY` | `api/deps.py`, `core/openai_client.py`, `runtime/orchestrate.py` |
| `OPENALEX_API_KEY` | Secrets Manager field: `policy_atlas_v3/app` `OPENALEX_API_KEY` | `api/deps.py`, `evidence_base/sourcing/search_live.py` |
| `OPENALEX_EMAIL` | Secrets Manager field: `policy_atlas_v3/app` `OPENALEX_EMAIL` | `evidence_base/sourcing/search_live.py` |
| `OVERTON_API_KEY` | Secrets Manager field: `policy_atlas_v3/app` `OVERTON_API_KEY` | `api/deps.py`, `evidence_base/sourcing/search_live.py` |
| `PA_BACKEND_MODE` | config value: `live` | `api/deps.py` |
| `POLICY_ATLAS_FIXTURE_CORPUS` | omitted (development/test fixture override) | `evidence_base/sourcing/ingest_full_text.py` |
| `POLICY_ATLAS_ORCHESTRATOR_MODEL` | omitted (development tuning; application default) | `runtime/orchestrator_backend.py` |
| `POLICY_ATLAS_ORCHESTRATOR_TRIAGE_MODEL` | omitted (development tuning; application default) | `runtime/orchestrator_backend.py` |
| `POLICY_ATLAS_PLANNER_MODEL` | omitted (development tuning; application default) | `runtime/planner.py` |
| `POLICY_ATLAS_RELEVANCE_MODEL` | omitted (development tuning; application default) | `evidence_base/extract/relevance_annotator.py` |
| `POLICY_ATLAS_SEARCH_CACHE_TTL_S` | omitted (development tuning; application default) | `evidence_base/sourcing/search_live.py` |
| `RUN_EXECUTOR_MAX` | config value: `backend.run_executor_max` | `api/settings.py` |
| `SSE_HEARTBEAT_SECONDS` | omitted (application default: 15) | `api/settings.py` |
| `SSE_POLL_INTERVAL_SECONDS` | omitted (application default: 0.4) | `api/settings.py` |

**Capacity values** (sized together for a 10-concurrent-run ceiling):
`RUN_EXECUTOR_MAX=10`, `DB_POOL_SIZE=15`, `DB_MAX_OVERFLOW=10`, task 2 vCPU /
8 GB (initial hypothesis — measured under load, not just arithmetic).

**Shared-provider-rate-limit caveat:** OpenAI rate limits are shared across all
concurrent runs on the one instance. At full concurrency, runs degrade to
slower — never to wrong.

## 6. Developer DB access

Local dev stays on docker-compose Postgres, untouched. Direct Aurora access from
a laptop is an SSM port-forward tunnel through the fck-nat instance (no bastion,
no inbound ports, IAM-gated) — the inspection replacement for v2's deleted
Supabase Studio. Recipe (verbatim):

Prereqs: AWS CLI + session-manager-plugin; IAM allowing `ssm:StartSession` on the
fck-nat instance; the fck-nat SSM role + fck-nat→Aurora 5432 ingress rule.

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

**Warning:** a locally booted API pointed at Aurora is a second instance
sharing the DB — the orphan sweep has no ownership lease and will interrupt the
staging service's executing walks (and vice versa). Tunnel for psql/inspection:
always fine. Local API against Aurora: only with the staging service stopped
(`aws ecs update-service --desired-count 0`).

## 7. Fonts

Averta/Zosia are licensed fonts served from a private S3 bucket
(`RemovalPolicy.DESTROY` — fonts are re-uploadable, never referenced directly by
the CloudFront distribution). `scripts/deploy.sh` fetches them into
`frontend/public/fonts/` before `vite build` so they ship inside the SPA bucket
like any other static asset. Binaries never enter the repo or the CDK asset tree
in committable form — CI's font-guard stays green.

## 8. Rollback

- **Repo:** single squash-revert removes `infra/` plus the two named backend
  touches (auth congruence edit, pool sizing) — both regression-tested by the
  suites they ship with.
- **Cloud (non-prod):** `cdk destroy PaV3AppStack PaV3DatabaseStack` — Aurora
  takes a final snapshot via its removal policy on delete. `PaV3CertStack` /
  `PaV3NetworkStack` destroy cleanly.
- **Cognito pool:** `RemovalPolicy.RETAIN` — deletion is owner-sign-off-only,
  never automatic, since recreating the pool mints new `sub`s and silently
  orphans owner-scoped projects.
- **Blast radius:** no rollback step can touch a v2-managed resource (v2 is
  read-only from this repo, structurally). v3 DNS records live only in the v3
  zone; worst case is the v3 domain going dark — v2 is never affected.
