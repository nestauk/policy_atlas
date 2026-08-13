# Policy Atlas v3 — deployment

Operator runbook for `infra/`. Deploys are operator-run (`cdk deploy`, no CI/CD
pipeline in this slice) via `scripts/deploy.sh`.

## 1. Overview

Four CloudFormation stacks:

| Stack | Region | Contents |
| --- | --- | --- |
| `PaV3NetworkStack` | `eu-west-2` | VPC, fck-nat, shared ALB + wildcard ACM cert |
| `PaV3DatabaseStack` | `eu-west-2` | Aurora Postgres cluster, generated credentials secret, `load_secret` Lambda, SSM jumpbox |
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

> `scripts/deploy.sh` is the authoritative sequence — on any discrepancy between
> this file and the script, the script wins. Modes: `bootstrap` (first deploy,
> gates A/B) and `update` (steady state).
>
> **One operator at a time.** There is no deploy lock: two concurrent
> `deploy.sh` runs can interleave migrations and scale-ups. Coordinate
> human-to-human (deferred seam — see `docs/deferred.md`).

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

   (`us-east-1` is needed solely for `PaV3CertStack`.) Bootstrapping creates
   IAM roles, so it needs an IAM-capable principal — **PowerUserAccess cannot
   run it** (E.1 finding, 2026-07-28). Day-to-day deploys work under
   PowerUser because CloudFormation executes through the bootstrap roles.

3. **Deploying principal can pass the ECS task roles.** The migration step
   (`aws ecs run-task`) requires `iam:PassRole` on the task and execution
   roles, which PowerUserAccess denies. The operator's permission set needs
   (E.1 finding, same date):

   ```json
   {
     "Effect": "Allow",
     "Action": "iam:PassRole",
     "Resource": "arn:aws:iam::<ACCOUNT_ID>:role/PaV3AppStack-*",
     "Condition": { "StringEquals": { "iam:PassedToService": "ecs-tasks.amazonaws.com" } }
   }
   ```

4. **App secret provisioned.** Secrets Manager secret `policy_atlas_v3/app`
   must exist with exactly these JSON keys (see § 5 for consumers):
   - `LANGFUSE_HOST`
   - `LANGFUSE_PUBLIC_KEY`
   - `LANGFUSE_SECRET_KEY`
   - `OPENAI_API_KEY`
   - `OPENALEX_API_KEY`
   - `OPENALEX_EMAIL`
   - `OVERTON_API_KEY`

5. **`CDK_DEFAULT_ACCOUNT` exported** in the operator's shell:

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

3. **Gate B** (now satisfiable, since the buckets/pool exist). On a genuinely
   fresh account `deploy.sh bootstrap` deliberately fails loud at this gate —
   the bucket and pool cannot be populated before they exist. Perform the two
   actions below, then rerun `deploy.sh bootstrap` (the stack deploys are
   no-ops on the rerun):
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

     For test users day-to-day, `make staging-user EMAIL=<email-format-username>
     PASSWORD='<password>'` wraps this: invite email suppressed, permanent
     password set directly (the address needs no real inbox; recovery for fake
     addresses is `admin-set-user-password` again).

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

**`desired_count=0` is template-pinned.** A `cdk deploy` that changes the app
stack stops the API service as part of the CloudFormation update. **Exception
(E.2 finding):** CloudFormation only re-asserts a template value on a *changed*
deploy — a no-op deploy leaves the scaled-up service running, so the script
also scales to 0 explicitly before its stop-wait. The steady-state order
(`deploy.sh update`):

1. `cdk deploy` (new task definition registered; service → 0 if the stack changed)
2. resolve + validate the frontend publish config (SSM exports, production
   build guard) — fail-fast, *before* any outage-inducing step
3. explicit scale to 0, then wait for tasks stopped
4. migration task + fail-loud wait on exit code (`describe-tasks`)
5. scale to 1 (`aws ecs update-service --desired-count 1` — deliberate,
   documented drift from the template until the next deploy)
6. fonts injection → `vite build` → `s3 sync` (no `--delete`) → CloudFront
   invalidation (waited) → pruning `s3 sync --delete`

Abort at the first non-zero step.

**Recovery from a failed deploy:** any failure between steps 3 and 5 leaves the
service at desired count 0 (the outage persists — ECS cannot self-heal to a
count the template pins at 0). Fix the cause and rerun `deploy.sh update`, or
restore service manually with
`aws ecs update-service --cluster policy-atlas-v3-cluster --service policy-atlas-v3-api-service --desired-count 1`
(only if the migration step had already passed).

**One-time pending step — encrypting the Aurora cluster (026 review hardening).**
The committed template sets `StorageEncrypted` (+ deletion protection, 7-day
backups), but the *live* cluster predates it and encryption cannot be enabled in
place; with the pinned cluster identifier, a plain deploy will fail on a name
collision rather than replace. Run once, **before real data lands** (the recreated
cluster starts empty — today it holds only smoke-run data; the destroy takes an
automatic final snapshot):

```bash
(cd infra && PATH="$PWD/.venv/bin:$PATH" npx cdk@2.1133.0 destroy \
   -c env_name=staging -c stage=all PaV3DatabaseStack)   # live cluster has no delete protection yet
(cd infra && PATH="$PWD/.venv/bin:$PATH" npx cdk@2.1133.0 deploy \
   -c env_name=staging -c stage=all --all --require-approval never)
   # recreates the cluster encrypted; the app stack is a no-op here
(cd infra && PATH="$PWD/.venv/bin:$PATH" npx cdk@2.1133.0 deploy \
   -c env_name=staging -c stage=all PaV3AppStack --force --require-approval never)
   # --force: the app stack template is unchanged, but it must re-resolve the
   # recreated DB security-group ID + secret name from SSM (SSM-coupling caveat
   # below) BEFORE anything scales the API up — its Aurora ingress rule still
   # points at the destroyed security group until this runs
bash scripts/deploy.sh update        # migrate → scale → publish on the fresh DB
```

**Operational caveats (verbatim from the contract):**

- Deploys interrupt executing runs — deploy in quiet windows. The hard-kill
  is recovered cleanly: the boot sweep marks interrupted runs `interrupted` on
  the next boot; this is not a data-loss condition.
- A crash means a brief outage until ECS restarts the task; the sweep recovers
  state cleanly in that case too.
- **Stale lookup context after resource replacement:** `cdk.context.json`
  caches `Vpc.from_lookup` results (VPC/subnet IDs). If the VPC is ever
  replaced under the same name, run `npx cdk context --reset` (or delete
  `infra/cdk.context.json`) before the next synth — a stale cache pins
  consumer stacks to deleted resource IDs without any error.
- **SSM-coupled stack references resolve at deploy time only.** The app stack
  consumes ALB/DB/SG identifiers via constant SSM parameter names. If a
  network/database resource is replaced (new physical ID, same parameter
  name), the app stack template is byte-identical and a `cdk deploy` of it is
  a no-op — redeploy the app stack with a forcing change (or `--force`) after
  any replacement of an SSM-exported resource.

## 5. Env & secret map

Generated from `settings.py`'s required/optional calls plus the direct
`os.environ` readers (`api/deps.py`, `core/tracing.py`,
`evidence_base/sourcing/search_live.py`). `LANGFUSE_HOST` is what the provisioned
secret carries (v2's key name); tracing accepts it natively, so deployment injects it
instead. `POLICY_ATLAS_*` tuning and the fixture corpus are intentionally
omitted from the deployed task.

| Var | Source | Consumer file |
| --- | --- | --- |
| `APP_ORIGIN` | config value: `https://{domain_name}` | `api/settings.py` |
| `DATABASE_URL` | Secrets Manager field: DB secret `db_connection_string` | `api/settings.py`, `core/db.py` |
| `DB_MAX_OVERFLOW` | config value: `backend.db_max_overflow` | `api/settings.py` |
| `DB_POOL_SIZE` | config value: `backend.db_pool_size` | `api/settings.py` |
| `LANGFUSE_HOST` | Secrets Manager field: `policy_atlas_v3/app` `LANGFUSE_HOST` | `core/tracing.py` |
| `LANGFUSE_BASE_URL` | omitted (equivalent alias of `LANGFUSE_HOST`) | `core/tracing.py` |
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
| `POLICY_ATLAS_CHAT_MODEL` | omitted (development tuning; application default `gpt-5.6-terra`) | `runtime/chat_prompt.py` |
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
a laptop is an SSM port-forward tunnel through a dedicated, no-ingress jumpbox
in a private subnet — the inspection replacement for v2's deleted Supabase
Studio. The jumpbox reaches the public Systems Manager services over HTTPS via
the existing NAT route in staging. In production, `NetworkStack` creates
private `ssm` and `ssmmessages` interface endpoints and the jumpbox attaches
their pre-wired managed-node SG; it has no public HTTPS fallback. The selection
is explicit in `network_config.json` as `ssm_connectivity: nat` or
`ssm_connectivity: interface_endpoints`. See
[`JUMPBOX.md`](../JUMPBOX.md) for the full operator and IAM guidance.

Prereqs: AWS CLI + session-manager-plugin; IAM allowing `ssm:StartSession` on the
jumpbox instance **and only its generated custom Session document**; permission
to read the database secret. Do not grant the engineer role access to the
AWS-managed remote-host port-forwarding document, which would let the caller
choose a different remote target.

```bash
# 1. DB credentials from the generated cluster secret
DB_SECRET=$(aws ssm get-parameter --name /policy_atlas_v3/db/secret_name \
  --query Parameter.Value --output text)
aws secretsmanager get-secret-value --secret-id "$DB_SECRET" \
  --query SecretString --output text | python3 -m json.tool   # host, port, password

# 2. Retrieve and run the fixed-target command emitted by DatabaseStack
aws cloudformation describe-stacks --stack-name PaV3DatabaseStack \
  --query "Stacks[0].Outputs[?contains(OutputKey, 'PortForwardingCommand')].OutputValue | [0]" \
  --output text
# Run the returned command. The generated document defaults localhost to 15432.

# 3. In another shell
psql "postgresql://dbadmin:<password>@localhost:15432/policy_atlas_db?sslmode=require"
```

The document pins the Aurora writer endpoint and port 5432. To select a
different local port, append
`--parameters '{"localPortNumber":["15433"]}'`; callers cannot override the
remote target.

This change does not put backend-to-Aurora traffic through the jumpbox or NAT.
The Fargate task ENIs and Aurora ENIs remain in the same VPC private subnets,
where AWS's implicit `local` route applies, and Aurora independently allows
`BackendSG` on port 5432. The NAT route is used only for internet-bound traffic.

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
  takes a final snapshot via its removal policy on delete. Two manual
  preconditions: disable the cluster's deletion protection first
  (`aws rds modify-db-cluster --db-cluster-identifier policy-atlas-v3-db-cluster --no-deletion-protection`),
  and empty the fonts bucket (CloudFormation cannot delete a non-empty
  bucket). `PaV3CertStack` / `PaV3NetworkStack` destroy cleanly.
- **Cognito pool:** `RemovalPolicy.RETAIN` — deletion is owner-sign-off-only,
  never automatic, since recreating the pool mints new `sub`s and silently
  orphans owner-scoped projects. NB `RETAIN` protects the *pool and its
  users* from stack deletion, **not** identity continuity across a
  destroy/redeploy: a redeployed stack creates a *new* pool (new issuer, new
  `sub`s) and the retained pool is orphaned outside CloudFormation. To keep
  the same identities after a destroy, re-import the retained pool
  (`cdk import`) instead of letting the redeploy mint a fresh one.
- **Blast radius:** no rollback step can touch a v2-managed resource (v2 is
  read-only from this repo, structurally). v3 DNS records live only in the v3
  zone; worst case is the v3 domain going dark — v2 is never affected.
