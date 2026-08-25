# Policy Atlas v3 — deployment

Operator runbook for `infra/`. `scripts/deploy.sh` remains the authoritative
deployment sequence. GitHub Actions invokes it for steady-state staging and
prod deploys; operators retain the Makefile entry points for first deploys
and recovery.

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
> this file and the script, the script wins. Modes: `check` (read-only committed
> config preflight), `bootstrap` (first deploy, gates A/B), and `update` (steady
> state). Use the Makefile entry points rather than invoking it directly.
>
> **One deploy at a time per environment.** GitHub Actions serializes each
> environment and never cancels an active deploy. There is no cross-system lock:
> a local `deploy.sh` can still interleave with Actions, so coordinate local
> recovery/bootstrap work human-to-human (deferred seam — see `docs/deferred.md`).

### GitHub Actions, Environments, and AWS OIDC

Two workflows automate only steady-state updates:

| Workflow | Trigger | Ref deployed | GitHub Environment |
| --- | --- | --- | --- |
| `deploy-staging.yml` | engineer runs `workflow_dispatch` | dispatch SHA, accepted only when the selected ref is `dev` | `staging` |
| `deploy-production.yml` | stable GitHub Release is published | immutable Release SHA, accepted only when it is in `dev` history | `prod` |

`release.published` includes prereleases; the workflow explicitly skips them. A
failed configuration/ref validation job never reaches the protected Environment
and never requests an OIDC token. Deploy jobs have only `contents: read` and
`id-token: write`. Concurrency queues a later deployment and deliberately does not
cancel the active stop→migrate→scale→publish sequence.

Create protected GitHub Environments named exactly `staging` and `prod`.
Each needs these Environment **secrets** (not repository variables or committed
values):

- `AWS_ROLE_ARN` — ARN of that environment's OIDC deployment role.
- `AWS_ACCOUNT_ID` — expected account; passed to CDK and used by the credential
  action's confused-deputy check. Account IDs are masked in logs.

Set each IAM role's maximum session duration to at least two hours. Workflows ask
for a two-hour credential and cap the job at 90 minutes, so a role left at AWS's
one-hour default fails during credential setup instead of expiring partway through
an outage-sensitive deploy.

Restrict `staging` deployment branches to `dev`. Restrict `prod` deployment
tags to the repository's release-tag pattern (for example `v*`) and require a
reviewer for prod. These restrictions are security controls, not just UI:
an environment-based GitHub OIDC token has a subject naming the Environment rather
than its branch/tag. The workflow performs a second ref check in code.

Create GitHub's OIDC provider in each AWS account with URL
`https://token.actions.githubusercontent.com` and audience `sts.amazonaws.com`.
Use one role per account/environment. Its trust policy must bind both audience and
the exact Environment subject (replace placeholders; do not commit the result):

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub": "repo:nestauk/policy_atlas:environment:<staging-or-prod>"
      }
    }
  }]
}
```

The example shows this existing repository's default subject shape. If the GitHub
organisation opts into immutable organisation/repository IDs or a custom OIDC
subject template, inspect the issued claims and bind the role to that exact subject
instead. Do not replace the exact match with a repository-wide wildcard.

The role needs the permissions already required by this runbook: use the CDK
bootstrap deploy/file/image roles; read the named deploy SSM parameters and app
secret metadata; run/inspect the migration task; update/inspect the ECS service;
sync the two deployment buckets; create/wait for the CloudFront invalidation; and
the tightly conditioned `iam:PassRole` grant below. Scope these permissions to the
environment's account and v3 resources. Do not add static AWS access-key secrets.

**Account isolation:** current v3 stack names, physical resource names, and
`/policy_atlas_v3/*` SSM namespace are fixed. Staging and prod therefore
must target separate AWS accounts. Supporting both in one account requires a
separate namespacing design, not a workflow-variable change.

**Prod is intentionally fail-closed today.** Add reviewed `prod`
entries to `network_config.json`, `db_config.json`, and `pa_config.json` before
enabling releases. The values include its domain, globally unique Cognito domain
prefix, app-secret name, region, and capacity. Until then:

```bash
make deploy-check DEPLOY_ENV=prod
```

fails before GitHub requests prod approval or AWS credentials. Never point
the prod workflow at the `staging` config as a workaround.

## 2. First-deploy preconditions (gate A)

Before the first `cdk deploy` of any kind, all of the following must hold.

The first deployment is intentionally not release-triggered: satisfy this section
and run `make deploy-bootstrap DEPLOY_ENV=<environment>` from an attended operator
session. Once gate B passes, GitHub Actions owns steady-state `deploy-update` runs.

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

     Day-to-day, use the operator CLI instead of the raw call — it creates the
     account **and enrols it**, which the raw call does not (task 033). The
     make wrappers own the setup (session check, pool id from SSM, DB
     credentials, the § 6 tunnel opened or reused):

     ```bash
     export PA_OPS_ACCOUNT_STAGING=<account id>   # operator-asserted, never derived
     make user-create ENV=staging EMAIL=<user-email> NAME="<name>" ORG="<organisation>"
     ```

     The direct form remains equivalent (the wrappers only forward to it):

     ```bash
     export PA_OPS_USER_POOL_STAGING=$(aws ssm get-parameter \
       --name /policy_atlas_v3/auth/user_pool_id --query Parameter.Value --output text)
     # DATABASE_URL points at the § 6 tunnel
     uv run python -m policy_atlas.ops --env staging user create \
       --email <user-email> --display-name "<name>" --org "<organisation>"
     ```

     The CLI verifies that the AWS account and user pool it resolved match the
     database on the far end of the tunnel before it writes anything, and it
     takes **no password**: Cognito emails the invitation. The former
     `make staging-user` / `make prod-user` / `make cognito-user` targets are
     **deleted** — they suppressed the invitation, set a password from argv, and
     left the account unenrolled. For prod, use `--env prod`, the
     `PA_OPS_*_PROD` variables and prod-account credentials, not
     `AWS_PROFILE=pa-dev`.

     The invitation goes through the `COGNITO_DEFAULT` sender (the pool has no
     `EmailConfiguration`), which is capped at 50 messages a day and needs a
     real deliverable mailbox.

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

For normal operator recovery use
`make deploy-update DEPLOY_ENV=<environment>` so local and GitHub execution stay on
the same interface. A GitHub rerun uses the same event SHA. For prod code
rollback, publish a new reviewed Release pointing at the chosen prior commit; do
not move or republish an existing Release tag.

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
- **Blocker preflight before the 033 migration.** The 033 migration takes
  `ACCESS EXCLUSIVE` on `project`, `portfolio` and `conversation` with
  `lock_timeout = '5s'`, so any held lock aborts the migration rather than
  queueing behind it (safe to re-run). With the API at zero, the only
  realistic blocker is an idle-in-transaction jumpbox session. Run this over
  the § 6 tunnel immediately before the migrate step:

  ```sql
  SELECT a.pid, a.usename, a.state, a.query_start, l.relation::regclass, l.mode
  FROM pg_locks l JOIN pg_stat_activity a ON a.pid = l.pid
  WHERE l.relation IN ('project'::regclass, 'portfolio'::regclass,
                       'conversation'::regclass)
    AND a.pid <> pg_backend_pid();
  ```

  Any row is a blocker: confirm the session is yours or stale, end it
  (`SELECT pg_terminate_backend(<pid>)`), and re-run until the result is
  empty. Note the limit: `lock_timeout` bounds lock *acquisition*, not how
  long the migration then holds the lock — the `created_by` backfill runs
  inside that exclusive lock, and its duration at production scale is what
  the pending backfill rehearsal measures.
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
the existing NAT route in staging. In prod, `NetworkStack` creates
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

**The ops CLI (task 033) runs over this same tunnel** — the operator's
laptop, `uv run python -m policy_atlas.ops --env staging|prod ...` with
`DATABASE_URL` pointing at `localhost:15432`, or the equivalent make
wrappers (`make user-create ENV=... EMAIL=... NAME=... ORG=...` — see the
Makefile's ops block; `scripts/ops_run.sh` performs this section's setup
and tunnel automatically, reusing an already-open one), under the operator's own IAM
(Cognito `cognito-idp:ListUsers` + `cognito-idp:AdminCreateUser`, nothing
more — see `JUMPBOX.md` § Security notes). It is **not** run as an ECS
task: Cognito permission belongs to the human operator, not to a task
role, and the API task role gains no Cognito permission. Every command
verifies the resolved AWS account and user pool against the connected
database before acting and refuses on a mismatch (§ 3 has the commands).
One consequence of that guard to plan for: against a **fresh deployment**
(empty `app_user` — exactly the post-033-migration state) the database's
identity cannot be proven, so the first command requires an interactive
terminal for a typed confirmation. No flag lifts it and no piped or
scripted invocation can make that first write.

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

- **Task 033 (organisations): roll forward, not back.** The 033 migration's
  downgrade is schema-reversible but **data-destructive and chat-exposing**:
  it drops `conversation.created_by`, so every colleague's chat authorship
  is lost and pre-033 code lists *all* conversations on a project to its
  owner — a rollback after adoption exposes colleagues' private chats to
  the project owner (evidenced by
  `test_downgrade_erases_chat_authorship_exposing_colleague_chats`, which
  also proves a re-upgrade misattributes the rows rather than undoing the
  exposure). It also drops both `visibility` columns, so a later re-upgrade
  resets every row to `org` and no private choice can be reconstructed. The
  real safety net is the dark launch: with no organisations enrolled the
  behaviour is byte-identical to pre-033, and **de-enrolling an
  organisation reverts it without a deploy**. A schema downgrade is a last
  resort requiring a backup restore first (Aurora keeps 7 days).
- **Manual downgrade procedure (last resort — the ECS migration task runs
  `alembic upgrade head` only and has no downgrade path):** scale the API
  to zero → restore or snapshot the cluster → open the § 6 tunnel → from
  `backend/` run `DATABASE_URL=<tunnel-url> uv run alembic downgrade
  b3c7d914e0a2` → deploy the pre-033 image → scale up. Do not do this on a
  database that has enrolled organisations without owner sign-off on the
  chat-exposure consequence above.
- **Automation:** disable the GitHub Environment or revoke its OIDC role trust to
  stop new deploys, then revert the workflow change. This does not repair an
  already interrupted stop→migrate→scale sequence; use the recovery procedure in
  § 4 against the exact deployed SHA.

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
