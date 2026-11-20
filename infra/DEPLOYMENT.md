# Policy Atlas v3 — deployment

Operator runbook for `infra/`. `scripts/deploy.sh` remains the authoritative
deployment sequence. GitHub Actions invokes it for steady-state staging and
prod deploys; operators retain the Makefile entry points for first deploys
and recovery.

## 1. Overview

Four core CloudFormation stacks, plus a staging-only analytics stack:

| Stack | Region | Contents |
| --- | --- | --- |
| `PaV3NetworkStack` | `eu-west-2` | VPC, fck-nat, shared ALB + wildcard ACM cert, NAT traffic alarm |
| `PaV3DatabaseStack` | `eu-west-2` | Aurora Postgres cluster, generated credentials secret, `load_secret` Lambda, SSM jumpbox, writer CPU-credit alarm |
| `PaV3AppStack` | `eu-west-2` | ECS Fargate API service + migration task, document-ingest queue + Lambda function (§ 4, "The ingest function"), Cognito, S3 + CloudFront frontend, font bucket |
| `PaV3CertStack` | `us-east-1` | CloudFront's ACM certificate (AWS requires this region for CloudFront certs) |
| `PaV3AnalyticsStack` (staging only) | `eu-west-2` | Metabase Fargate service, dedicated RDS PostgreSQL application database, secrets, shared-ALB route + DNS |

The stacks synth from `infra/app.py`, driven by `-c env_name=<env>` and, on first
deploy only, `-c stage=network|all`. `scripts/deploy.sh` wraps `cdk deploy` of the
eu-west-2 stacks plus `PaV3CertStack`, and owns the imperative steps
CloudFormation can't: migration task invocation, frontend build/sync/invalidation,
font injection.

**Public/private boundary (repo is public, AGPL-3.0):** CDK code and the
`*_config.json` files (`network_config.json`, `db_config.json`, `pa_config.json`,
and `metabase_config.json`)
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
> recovery/bootstrap work human-to-human (deferred: see `docs/deferred.md` § Infrastructure and deployment).

### GitHub Actions, Environments, and AWS OIDC

Two workflows automate only steady-state updates:

| Workflow | Trigger | Ref deployed | GitHub Environment |
| --- | --- | --- | --- |
| `deploy-staging.yml` | automatically when `verify` passes on a push to `dev`, or an engineer runs `workflow_dispatch` from `dev` | the commit `verify` passed (or the dispatch SHA), accepted only from `dev` | `staging` |
| `deploy-production.yml` | engineer runs `workflow_dispatch` from `main` with a new `vX.Y.Z` version | the tip of `main`, accepted only when it is in `dev` history | `prod` |

`dev` remains the repository default branch. Pull requests, continuous
integration, and staging deploys stay on `dev`. Every merge to `dev` that passes
`verify` redeploys staging, which briefly stops the staging API while
migrations run.

`main` is the production branch only, and pushing to it deploys nothing. A
ruleset blocks force-pushes and deletion, so `main` only ever moves forward. To
release:

1. Pick the `dev` commit that is working on staging (usually the latest
   successful **deploy staging** run).
2. Move `main` forward to it: `git fetch origin && git push origin <commit>:main`.
   Pull requests into `main` are not used: every GitHub merge method creates a
   commit that is not in `dev` history, which the workflow would refuse.
3. Run **deploy production** from `main` in the Actions tab, entering a new
   version such as `v1.4.0`
   (`gh workflow run deploy-production.yml --ref main -f version=v1.4.0`).
4. A `prod` reviewer other than the person who started the run approves it.

The workflow refuses any other branch, any `main` commit that is not already in
`dev` history, and any version that is not `vX.Y.Z` or is already a tag. These
checks run before the deploy, so a mistake fails before the API is stopped.
After a successful deploy, a separate job tags the commit with the version and
publishes a GitHub Release with generated notes listing the merged pull
requests. If only that job fails, the deploy has already happened: re-run the
failed job rather than the whole workflow.

A failed configuration/ref validation job never reaches the protected Environment
and never requests an OIDC token. Deploy jobs have only `contents: read` and
`id-token: write`. The release job has only `contents: write` and never receives
AWS credentials. Concurrency queues a later deployment and deliberately does not
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
branches to `main`, require a reviewer for prod, and enable "prevent
self-review" so the person who starts a release cannot approve it. These restrictions are
security controls, not just UI: an environment-based GitHub OIDC token has a
subject naming the Environment rather than its branch or tag. The workflow
performs a second ref check in code.

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
sync the two deployment buckets; create/wait for the CloudFront invalidation;
list the account's WAF API keys (`wafv2:ListAPIKeys`, read-only; task 064b, so the
deploy can give the frontend its CAPTCHA settings, see § 4 "The firewall"); and
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
   - `AWS_BEARER_TOKEN_BEDROCK`: needed only once an environment's
     `backend.model_route` in `pa_config.json` is a Bedrock route (§ 5, Switching
     to Bedrock); ECS refuses to start a task that names a missing field.

5. **`CDK_DEFAULT_ACCOUNT` exported** in the operator's shell:

   ```bash
   export CDK_DEFAULT_ACCOUNT=<account-id>
   ```

6. **Metabase UI allowlist provisioned in Parameter Store (staging only).**
   Create `/policy_atlas_v3/metabase/allowed_cidrs` in `eu-west-2` as a standard
   `StringList` before deploying the analytics stack:

   ```bash
   aws ssm put-parameter \
     --region eu-west-2 \
     --name /policy_atlas_v3/metabase/allowed_cidrs \
     --type StringList \
     --value '<cidr-1>,<cidr-2>' \
     --overwrite
   ```

   Supply one to eight canonical **IPv4** CIDRs, separated by commas with no
   spaces. An ALB rule holds at most five condition values and the hostname
   takes one, so the deploy splits the list into one listener rule per four
   CIDRs (priorities 20 and 21). Changing the number of CIDRs takes effect on
   the next deploy, like any other allowlist edit. IPv6 entries are rejected: the shared ALB is IPv4-only (IPv4 security
   group ingress, an `A` alias record, default address type), so an IPv6 entry
   could never match a client and an IPv6-only list would lock everyone out
   with a silent 404. Universal `/0` ranges are rejected because they do not
   form an allowlist. The deployment validates the type and CIDRs without
   printing their values; failures name the entry's position, not its address.
   The ALB compares the address that connects directly to it, not
   `X-Forwarded-For`; for users behind a VPN or proxy, allowlist its egress
   CIDR.

   **How a change reaches the ALB rule.** The synthesized template carries only
   the parameter *name*, as an `AWS::SSM::Parameter::Value<List<String>>`
   template parameter; CloudFormation resolves the value at every stack
   create/update ("use previous value" keeps the key, not the value), and the
   pinned CDK CLI never skips a stack whose template carries an SSM-typed
   parameter, even when the template itself is unchanged. So editing the
   parameter alone changes nothing — a removed address keeps access until the
   next deploy — and the normal staging deployment (`make deploy-update
   DEPLOY_ENV=staging`) is what applies it. Rather than rely on that CLI
   behaviour, `deploy.sh` verifies it: after `cdk deploy` it reads the live rule
   on the shared HTTPS listener and fails the deploy if the rule's source-IP set
   differs from the parameter (`elasticloadbalancing:DescribeRules` is required
   by the deploy role). To confirm the effect by hand, look at the analytics
   stack's **Parameters** tab in CloudFormation: it shows the resolved value the
   rule was last deployed with.

7. **WAF CAPTCHA API key created (task 064b; only where `backend.waf.captcha` is
   `true` in `pa_config.json`).** The firewall's CAPTCHA puzzle needs a public
   key that belongs to the AWS account and region, not to the stack, and that
   is created once by hand:

   ```bash
   aws wafv2 create-api-key --scope REGIONAL --region eu-west-2 \
     --token-domains <domain_name>
   ```

   `<domain_name>` is the environment's `domain_name` in `pa_config.json`
   (`v3.policyatlas.uk` on staging, `policyatlas.uk` in production). A key
   cannot be changed afterwards; a new domain needs a new key. The deploy
   script only *lists* keys and takes the one whose token domains equal
   `[<domain_name>]`; with none it stops before touching AWS state and prints
   this command. The key and the script URL it comes with are public by
   design (they ship in the browser bundle), so they are not secrets. See § 4
   "The firewall".

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

     Day-to-day, use the operator CLI instead of the raw call. With `ORG` it
     creates the account and enrols it (task 033). Without `ORG` it creates the
     account and an identity row in no organisation, including the address, so
     the person can be found later. A later `user enrol` places them. The make
     wrappers own the setup (session
     check, pool id from SSM, DB credentials, the § 6 tunnel opened or reused):

     ```bash
     export PA_OPS_ACCOUNT_STAGING=<account id>   # operator-asserted, never derived
     make user-create ENV=staging EMAIL=<user-email> NAME="<name>" ORG="<organisation>"
     make user-create ENV=staging EMAIL=<user-email> NAME="<name>"   # no organisation
     ```

     The direct form remains equivalent (the wrappers only forward to it):

     ```bash
     export PA_OPS_USER_POOL_STAGING=$(aws ssm get-parameter \
       --name /policy_atlas_v3/auth/user_pool_id --query Parameter.Value --output text)
     # DATABASE_URL points at the § 6 tunnel
     uv run python -m policy_atlas.ops --env staging user create \
       --email <user-email> --display-name "<name>" [--org "<organisation>"]
     ```

     The CLI verifies that the AWS account and user pool it resolved match the
     database on the far end of the tunnel before it writes anything, and it
     takes **no password**: Cognito emails the invitation. The former
     `make staging-user` / `make prod-user` / `make cognito-user` targets are
     **deleted** — they suppressed the invitation, set a password from argv, and
     left the account unenrolled. For prod, use `--env prod`, the
     `PA_OPS_*_PROD` variables and prod-account credentials, not
     `AWS_PROFILE=pa-dev`.

     **When the invitation email does not arrive**, add `INVITE=manual` (CLI:
     `--invite manual`): the email is
     suppressed and the CLI **mints** a single-use temporary password, printed
     once for out-of-band handover — the person sets their own at first
     sign-in (`FORCE_CHANGE_PASSWORD`, 30-day validity). The CLI still accepts
     no password from anyone, and the mode needs no IAM beyond
     `AdminCreateUser`. If that password expires or is lost before first
     sign-in, `make user-reissue ENV=<env> EMAIL=<user-email>` mints and prints
     a replacement on the same terms (it refuses any account that has already
     signed in; needs `AdminSetUserPassword`). SES-backed pool email is now in
     place through task 065; see [Pool email through SES (task 065)](#pool-email-through-ses-task-065).

     **Removing a person's access (task 064a, Q10; task 066).** `user de-enrol`
     changes the database only: the person's Cognito account still signs in and
     their public links stay public. `user deactivate` is the command to use when
     someone leaves (it replaced `user offboard` in task 066). The ops pages have
     the same action as "Deactivate…" on People.

     ```bash
     uv run python -m policy_atlas.ops --env staging user deactivate --email <user-email>
     # or: ... user deactivate --sub <cognito-subject>
     # to undo: ... user reactivate --email <user-email>
     ```

     Deactivate runs these steps in this order and prints each one: (1) in Cognito,
     disable the account and revoke its refresh tokens (`AdminDisableUser`,
     `AdminUserGlobalSignOut`), so the person cannot sign in again or renew a
     session; (2) in the database, set `app_user.deactivated_at`, clear the
     admin and ops roles (each removal writes the same trace line as `admin
     revoke`), and set every task they own to not public, so their share links
     stop working. **The person keeps their organisation, tasks, projects and
     cohorts** (owner ruling, 2026-11-19), so `user reactivate` is a clean undo:
     it turns the login back on (`AdminEnableUser`) and clears the mark, but does
     not give back a role or a public link. No role can be granted while a person
     is deactivated. Adding a deactivated address again from the ops pages
     reactivates it; approving their waitlist request, or the self-signup sweep,
     refuses instead. Cognito goes first on purpose: if the database step fails,
     the account is already disabled and running the command again finishes the
     rest. Two things it cannot do: an access token already issued stays valid
     for up to 60 minutes (and, with the organisation kept, can read the
     organisation's shared work in that window), and a progress stream that is
     open when the command runs stays open until the run ends.

     **Deleting an organisation (task 066).** `org delete --org <name>` or
     "Delete…" on the Organisations page. It works only when no person, task,
     project or signup domain points at the organisation, and otherwise says
     what is still there.

     With `email.enabled` false the invitation goes through the `COGNITO_DEFAULT`
     sender, which is capped at 50 messages a day; with it true it goes through
     SES (see [Pool email through SES (task 065)](#pool-email-through-ses-task-065)).
     Either way it needs a real deliverable mailbox.

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

### Staging Metabase first-admin setup

`pa_config.json` enables `PaV3AnalyticsStack` only for staging. Its application
database is deliberately separate from the Policy Atlas database. The service
runs one task in private subnets and is exposed only through the shared ALB at
`https://metabase.v3.policyatlas.uk`.

That hostname's listener rule also requires a source match from the SSM-backed
allowlist. This restriction applies only to the Metabase route; the Policy Atlas
web application and API listener rules are unchanged. A non-matching address
falls through to the shared listener's default response and is never forwarded
to the Metabase target group.

Treat the initial setup as an attended operation: open that address as soon as
the analytics stack reports healthy and create the staging administrator. Until
that account exists, Metabase's first-user setup surface is reachable through the
public staging hostname. Do not leave a first deployment unattended.

Do **not** add the Policy Atlas production/application database with its owner
credentials. This stack creates network reachability only. Source onboarding
requires a separately reviewed, least-privilege login restricted to curated
owner-safe analytics views (or equivalent row-level controls), stored in Secrets
Manager. Configure that connection with SSL after the data-access change is
approved. The Metabase connection-details encryption key is retained in Secrets
Manager because losing or replacing it makes stored source credentials
unreadable. The secret has a CloudFormation-generated name (no fixed name), so
`cdk destroy` followed by a redeploy creates a fresh key rather than failing on
a name collision with the retained one. That fresh key cannot read a database
restored from the destroyed instance's snapshot: to restore, copy the retained
secret's value into the new secret (`aws secretsmanager put-secret-value`)
before the service first starts against the restored database, then delete the
orphaned secret. With no data source connected yet, a lost key costs only the
re-entry of source credentials.

### Pool email through SES (task 065)

Check production access before enabling the sender:

```bash
aws sesv2 get-account --region eu-west-2
```

Confirm `ProductionAccessEnabled` is true. Verify the SES identity first,
then obtain production access, set `email.enabled` to true in
`pa_config.json`, and deploy. The daily sending limit is SES's own
`SendQuota`, returned by the same command. Use `--invite manual` only as
the fallback when an invitation email does not arrive.

### The ops service (task 065)

The ops service is a second ECS (Elastic Container Service) service built from
the same image as the API. It serves the ops pages and the `/api/v1/ops/*`
routes, and nothing else. The load balancer lets in only allowlisted addresses.

**The ops address.** `https://ops.<domain>`, from `ops.subdomain` in
`pa_config.json` (staging: `https://ops.v3.policyatlas.uk`).

**The allowlist parameter.** `/policy_atlas_v3/ops/allowed_cidrs` in Parameter
Store (the AWS settings store). A CIDR (Classless Inter-Domain Routing) range is
an address block such as `203.0.113.0/24`. The parameter is a `StringList` of up
to 8 IPv4 CIDRs, checked by the same validator as Metabase's. Create it by hand
before the first deploy; the deploy fails loudly if it is missing or invalid.

**The ops database secret.** `policy_atlas_v3/ops_db` in Secrets Manager.
CDK (Cloud Development Kit) generates it with the username `pa_ops` and a random
password. The migration task writes `db_connection_string` into it after every
migration, so the ops service always logs in as the restricted `pa_ops`
database role.

**First-deploy order.**

1. Create the allowlist parameter.
2. Deploy with `ops.desired_count` set to 0. The service exists but runs no
   tasks.
3. Grant the first ops role from your machine:

   ```bash
   make ops-grant ENV=staging EMAIL=<email>
   ```

   Only the CLI can grant `is_ops`; no web page can.
4. Set `ops.desired_count` to 1 and deploy again.

   The committed staging config already has `desired_count` 1. On an
   environment where the ops service has never run, set it to 0 for step 2,
   then back to 1.

**Self-signup.** `self_signup.enabled` in `pa_config.json` is false by default
(`max_per_hour` caps the invitations the sweep sends, and its failed attempts, per hour; an enrolment of an existing account sends nothing and is not capped). Before switching it on, make sure the
Nesta organisation exists and has its domain:

```bash
uv run python -m policy_atlas.ops --env staging org create --name Nesta
uv run python -m policy_atlas.ops --env staging org domain add --domain nesta.org.uk --org Nesta
```

Then set `enabled` to true and deploy. On production, do this only after the
WAF (web application firewall) rate rule from task 064b is live.

**Rollback, one step at a time.**

- Email (SES): set `email.enabled` to false and deploy. The pool goes back to
  the default sender and templates.
- Ops service: set `ops.desired_count` to 0 and deploy. If the schema must go
  too, stop both services first, then run `alembic downgrade b1e7c3a9d5f2` (the
  revision before task 065). It removes all three 065 migrations, newest first:
  the first-sign-in and rejected-request columns, the cohort tables, then
  `is_ops`, `invited_at`, the four quota columns, `ops_action`, the domain table,
  the waitlist stamp columns, the trigger and the `pa_ops` role. The public API
  reads the quota and cohort tables and writes the first-sign-in column, so it
  must be stopped, and the API image you start afterwards must be one from
  before task 065.
- Self-signup: set `self_signup.enabled` to false and deploy. The sweep stops.
  Its schema is removed only by the full downgrade above.

A rollback never drops a table while a service that reads it is running.

## 4. Steady-state deploys + the deploy invariant

**`desired_count=0` is template-pinned.** A `cdk deploy` that changes the app
stack stops the API service as part of the CloudFormation update. **Exception
(E.2 finding):** CloudFormation only re-asserts a template value on a *changed*
deploy — a no-op deploy leaves the scaled-up service running, so the script
also scales to 0 explicitly before its stop-wait. The steady-state order
(`deploy.sh update`):

0. when the environment's `backend.waf.captcha` is on: look up the CAPTCHA
   script URL and API key in the account (`aws wafv2 list-api-keys`) and fail
   if the key is missing — *before* `cdk deploy`, so a missing key or
   permission changes nothing (task 064b; see "The firewall" below)
1. `cdk deploy` (new task definition registered; service → 0 if the stack changed)
2. resolve + validate the frontend publish config (SSM exports, production
   build guard, which also requires the two CAPTCHA values when the CAPTCHA is
   on) — fail-fast, *before* any outage-inducing step
3. explicit scale to 0, then wait for tasks stopped
4. migration task + fail-loud wait on exit code (`describe-tasks`, polled every
   15 s up to `MIGRATION_WAIT_MAX_S`; see "Waiting for the migration task" below)
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

**Waiting for the migration task (task 057).** `deploy.sh` asks ECS for the
migration task's status (`aws ecs describe-tasks`) every 15 seconds until it
reports `STOPPED`, then fails the deploy unless the container exited with code 0,
printing the exit code and ECS's `stoppedReason`. It gives up after
`MIGRATION_WAIT_MAX_S` seconds, 5,400 (90 minutes) by default; set the variable
in the environment that runs `deploy.sh` to change it (the deploy role's session
lasts 7,200 s and the GitHub deploy job 90 minutes, so a larger value only helps
a run from a laptop). On that timeout it prints the last status and the task
ARN and **leaves the task running**: a migration stopped half-way is safe to
rerun, but whether to stop it is the operator's call. A failed `describe-tasks`
call counts as one more poll, not a failure. The previous
`aws ecs wait tasks-stopped` gave up after about 10 minutes, too short for task
057's backfill. `make deploy-migration-wait-test` checks the loop against a
stubbed `aws`.

**Readiness check after the service is stable (task 064a, Q4).** The load
balancer's health check now asks the API only "is the process alive"
(`/healthz`), not "can you reach the database" (`/readyz`). That is deliberate:
with the old check a short database outage made ECS replace the only container
and kill every run on it. The price is that a deploy with a broken database
secret would look healthy. So after `services-stable`, `deploy.sh` calls
`/readyz` once (up to ten tries, 15 seconds apart) and fails the deploy if it
never returns 200. `/readyz` stays available for diagnosis.

**Before each deploy: who is at the task quota (task 064a, Q8).** Each person
may create at most `backend.task_quota_per_year` tasks (50) in any rolling
365-day window; administrators are exempt. Someone already at or over the limit
sees the quota banner and cannot create tasks from the moment the slice is
deployed. Run this over the § 6 tunnel before the deploy so the owner knows who
that is (it is informational; nothing in the deploy depends on it):

```sql
SELECT owner_user_id, count(*) AS tasks_in_last_365_days
FROM task
WHERE created_at >= now() - interval '365 days'
GROUP BY owner_user_id
HAVING count(*) >= 50
ORDER BY tasks_in_last_365_days DESC;
```

**After task 064a's first deploy: search the old logs once (review finding
H-06).** Until task 064a, every JSON error log carried the local variables of
each stack frame, so user text and the first characters of a secret could have
reached CloudWatch. The fix stops new leaks; it does nothing about lines already
stored (CloudWatch keeps them 30 days). Someone with console access opens
CloudWatch Logs Insights, selects the API service's log group for the
environment, and runs:

```
fields @timestamp, @message
| filter @message like /"locals"/ or @message like /api_key/ or @message like /password/ or @message like /dbadmin/
| sort @timestamp desc
| limit 200
```

If a real secret value appears, rotate the database password (the cluster
secret) and the provider keys in `policy_atlas_v3/app`, then force a new
deployment. Record the result, found or not found, in the task's
`verification.md`. Do this on both environments.

**Task 057 release: run its two migrations before the deploy (recommended).**
Task 057 adds two revisions that are safe to run while the service is up:

- `a3d8f6c1e2b4` (expand) only adds nullable columns, the `queued` status and the
  `vector` extension, takes each brief table lock with a 10-second
  `lock_timeout` (if it times out, run it again), and builds its two indexes
  `CONCURRENTLY`, which does not block the app's writes.
- `b7e2c4a9d1f3` (backfill) copies every stored embedding into the new
  `chunk_embedding.embedding` column and fills `tokens`, 2,000 rows per
  committed batch. On the production writer it is expected to take **tens of
  minutes**, which is why it should not run inside the deploy's outage window.

Because the deploy stops the service before it migrates, run both first, while
the old service still serves, then deploy as usual; the deploy's migration task
finds them applied and runs only what remains. Run them over the § 6 tunnel from
a checkout of the commit being released (the migration ECS task cannot do this
before the deploy: its task definition still holds the image that is running
now, which does not contain these revisions, and `cdk deploy` registers the new
one only as it stops the service). The command has the same shape as the manual
downgrade in § 8:

```bash
# Tunnel open (§ 6). From backend/ in a checkout of the release commit:
DATABASE_URL=<tunnel-url> uv run alembic upgrade b7e2c4a9d1f3
# <tunnel-url> = postgresql+psycopg://dbadmin:<password>@localhost:15432/policy_atlas_db?sslmode=require
```

**It resumes.** Each batch commits on its own and only rows whose `embedding`
is still empty are picked up, so if the tunnel drops, the laptop sleeps or the
command fails, run the same command again: it carries on where it stopped and
redoes nothing. Progress is logged every 25 batches. When it finishes,
`SELECT count(*) FROM chunk_embedding WHERE embedding IS NULL;` returns 0.
Rows the old service writes after that moment (it writes only the JSON column)
are left empty: the third revision fills them.

- `0914321f8de4` (drop the JSON column) runs **inside the deploy's migration
  task**, not before: it first runs the same fill over any rows the old service
  wrote after the pre-run (seconds, as batches), then, under a short table lock
  (10-second lock timeout), checks that no row lacks an embedding and drops the
  old JSON `vector` column. If the check fails it stops with a message that says
  how many rows are missing and why, and drops nothing; fix or delete those rows
  and run the deploy's migration again. Its downgrade rebuilds the JSON column
  from the binary one at float32 precision (approximate).

For normal operator recovery use
`make deploy-update DEPLOY_ENV=<environment>` so local and GitHub execution stay on
the same interface. A GitHub rerun uses the same event SHA. For prod code
rollback, revert the bad change on `dev` (so staging redeploys it first), move
`main` forward to that revert commit, then run **deploy production** from `main`
with a new version. `main` cannot be moved backwards or force-pushed.

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
  `ACCESS EXCLUSIVE` on `task`, `project` and `conversation` with
  `lock_timeout = '5s'`, so any held lock aborts the migration rather than
  queueing behind it (safe to re-run). With the API at zero, the only
  realistic blocker is an idle-in-transaction jumpbox session. Run this over
  the § 6 tunnel immediately before the migrate step:

  ```sql
  SELECT a.pid, a.usename, a.state, a.query_start, l.relation::regclass, l.mode
  FROM pg_locks l JOIN pg_stat_activity a ON a.pid = l.pid
  WHERE l.relation IN ('task'::regclass, 'project'::regclass,
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
- **SSM-coupled stack references resolve at deploy time only.** The app and
  analytics stacks consume ALB/DB/SG identifiers via constant SSM parameter
  names. If a network/database resource is replaced (new physical ID, same
  parameter name), the consumer template is byte-identical; the pinned CDK CLI
  still submits it because it never skips a stack carrying SSM-typed template
  parameters, and CloudFormation re-resolves the new IDs. Nothing outside a
  deploy re-resolves them, though, so always redeploy the consumer stacks after
  replacing an SSM-exported resource; `--force` is a harmless belt-and-braces
  on that path and the Aurora encryption runbook above keeps it.

### The ingest function (task 057)

**What it is.** When a run needs the full text of its documents, the API can
hand the reading out instead of doing it itself. It puts one message per
document on a queue, and AWS starts a small worker for each message: the
**ingest function** (`policy-atlas-v3-ingest`, an AWS Lambda function). The
function downloads the document, parses it into passages and writes them to the
database. It makes no AI calls and holds no AI key; the run embeds the passages
itself once they land.

The words, one line each:

- **SQS queue** (Amazon Simple Queue Service): a managed to-do list of messages,
  here `policy-atlas-v3-ingest`. Messages are kept 4 days, encrypted at rest.
- **Visibility timeout** (210 s): once a worker takes a message, the message is
  hidden from other workers for this long. If the worker has not finished by
  then, the message reappears for another try. It is the function's 180 s time
  limit plus 30 s.
- **Retry delay** (30 to 60 s): when a page fetch fails in a way worth trying again
  (a timeout or a network error), the function does not wait for the 210 s above.
  Before it hands the message back, it asks the queue to show it again after a
  random 30 to 60 s (`ChangeMessageVisibility`, a call that resets the timer on one
  message). The first try has ended by then, so the message cannot arrive twice at
  once. The function's role already holds this permission. If the call fails, the
  message still comes back, only after the full 210 s.
- **Dead-letter queue** (`policy-atlas-v3-ingest-dlq`): where a message goes
  after its second failed try, so it stops being retried and a person can look
  at it. Kept 14 days. The function writes the failure reason on the
  document's row before giving up (on its second try, an unexpected error is
  written as `worker_error`), so the run is not waiting on it. The two cases
  it cannot write are a platform kill at the 180 s limit and a database that
  refuses the write; the run's own 600 s deadline then records the document
  as `not_ready`.
- **Event-source mapping**: the AWS-managed poller that reads the queue and
  starts the function, one message per start, at most 20 at once (raise only
  after a staging measurement: the database writer is a small burstable
  instance).

Sizing: 1,769 MB of memory (one full CPU core), 180 s time limit, 512 MB of
scratch disk, in the private subnets with its own security group, which the
database security group admits on port 5432. Its logs go to
`/policy_atlas_v3/ingest`, kept 30 days. Its only environment variables are
`POLICY_ATLAS_DB_SECRET_ARN` (where the database password lives; the function
reads the secret itself at start-up, through its role), `POLICY_ATLAS_MODEL_ROUTE`
and `LOG_FORMAT=json`. It runs the same container image as the API (built once
per deploy), started with
`python -m awslambdaric policy_atlas.ops.ingest_worker.handler` instead of the
web server.

**Which environments use it.** `backend.ingest_mode` in `pa_config.json`, per
environment: `queued` sends documents to the function, `in_process` reads them
inside the API task as before. Today staging is `queued` and production is
`in_process`. The queue and function exist in both; in `in_process` mode nothing
is sent to them. Changing the value is a config edit plus a deploy.

**Alarms.** Three CloudWatch alarms watch this work. None sends a notification
yet (the stacks have no alarm topic); check their state in the CloudWatch
console, Alarms page.

| Alarm | Stack | Fires when |
| --- | --- | --- |
| `policy-atlas-v3-ingest-dlq-depth` | app | at least 1 message in the dead-letter queue (5-minute check) |
| `policy-atlas-v3-nat-network-out` | network | the busiest fck-nat instance sends over 1 GB per 5 minutes, 3 periods in a row (about 27 Mbit/s, near a `t4g.nano`'s 32 Mbit/s baseline). **A first guess: review on staging** after a few queued runs and adjust `NAT_NETWORK_OUT_ALARM_BYTES` in `network_stack.py`. |
| `policy-atlas-v3-db-writer-cpu-credits` | database | the Aurora writer's CPU credit balance drops below 50 (at zero the writer is slowed to its baseline) |

**Draining and inspecting the dead-letter queue.** A message there carries only
two ids and a schema version (no URL, no user). The reason the document failed
is on its row in the database (`task_source_snapshot.full_text_status` and its
reason), so the message is mainly a pointer. With the environment's AWS profile
logged in:

```bash
export AWS_PROFILE=<the environment's profile>   # e.g. the staging SSO profile
DLQ_URL=$(aws sqs get-queue-url --queue-name policy-atlas-v3-ingest-dlq \
  --query QueueUrl --output text)

# How many are waiting:
aws sqs get-queue-attributes --queue-url "$DLQ_URL" \
  --attribute-names ApproximateNumberOfMessages

# Look at up to 10 (they stay in the queue; each reappears after 60 s):
aws sqs receive-message --queue-url "$DLQ_URL" --max-number-of-messages 10 \
  --visibility-timeout 60 --attribute-names All

# Remove one you have dealt with (ReceiptHandle from the receive above):
aws sqs delete-message --queue-url "$DLQ_URL" --receipt-handle '<ReceiptHandle>'

# Or empty the whole dead-letter queue (cannot be undone):
aws sqs purge-queue --queue-url "$DLQ_URL"
```

Nothing needs re-sending by hand: the run has already recorded the document as
not read and carried on without it.

**Deploys and messages in flight.** On every deploy after the first,
`cdk deploy` updates the function to the new image *before* `deploy.sh` runs the
migration task. A message the new function picks up in that gap meets the old
database schema, may fail twice and land in the dead-letter queue (the alarm
fires). This is expected around a deploy: the run records the document as not
read and carries on. Deploy in quiet windows, as for the API.

### The firewall (task 064b)

**What it is.** A firewall (AWS WAF, Web Application Firewall) sits on the
shared load balancer and looks at every request before the API sees it. Its
rules live in one object, the **web ACL** (`policy-atlas-v3-api`, built by
`infra/infra/components/waf.py` in the app stack and attached to the load
balancer). Each rule can **count** a request (note that it matched and let it
through), **block** it (answer 403), or ask for a **CAPTCHA** (answer 405 until
the browser presents a solved-puzzle token). Every rule is scoped to the API
host or to the waitlist path, so Metabase traffic on the same load balancer
matches nothing. ADR 0047 has the reasoning.

**The rules, in order.** `waitlist-captcha` (only when the CAPTCHA is on: a
`POST` to `/api/v1/waitlist` without a valid token is refused with 405 and the
header `x-amzn-waf-action: captcha`); `waitlist-rate` (more than 50 waitlist
posts in 5 minutes from one address are blocked, always); `general-rate` (more
than 6,000 requests in 5 minutes from one address to the API host);
`managed-common`, `managed-known-bad-inputs`, `managed-ip-reputation` (AWS's
own rule groups for common web attacks, known bad inputs and bad-reputation
addresses, applied to the API host except `/healthz` and `/readyz`, so the
load balancer's health check and the deploy's readiness call can never be
refused by them). The common group's `SizeRestrictions_BODY` rule (a body over
8 KB) is always counted and never blocks, because chat messages, plan edits
and theory-of-change imports are often larger. The exclusion list is
hard-coded in the component (`COMMON_RULES_ALWAYS_COUNTED`); a second name goes
there too, and becomes a config key only if the list keeps growing.

**The three keys** under `backend.waf` in `pa_config.json`, per environment:

| Key | Values | Effect |
| --- | --- | --- |
| `enabled` | `true` / `false` | `false` synthesises no firewall at all (the rollback). |
| `mode` | `"count"` / `"block"` | Whether `general-rate` and the three managed groups block or only count. The waitlist rules are not governed by it. |
| `captcha` | `true` / `false` | Adds the CAPTCHA rule and makes the deploy give the frontend its CAPTCHA settings. `true` needs `enabled: true`. |

A missing key, a wrong value or `captcha` without `enabled` fails both `cdk
synth` and `deploy.sh check`.

**The count week.** A new environment, and any environment after a rule change,
runs with `mode: count` for a week so the rules show what they *would* block
without blocking anyone. Right after the deploy, do the deliberate pass: sign
in, open the task list, send one chat message over 8 KB, edit a plan, import a
theory-of-change image, open a public task view, and submit the waitlist form.
Then run the report:

```bash
AWS_PROFILE=<profile> scripts/waf_report.sh <staging|prod> [days] [--addresses]
```

It prints, per rule, the counted, blocked and CAPTCHA totals for the last
`days` days (default 7) from CloudWatch metrics, then one query over the
firewall log giving the request count per **rule inside a group** (the metrics
only name the group) and the paths it matched. Client addresses are printed
only with `--addresses`; do not paste them into a public record. The script
reads and never writes. After the week, decide per rule: a rule that matched
only normal use is excluded (below); everything else is ready to block.

**Switching to block.** Set `mode` to `"block"` in `pa_config.json` for that
environment, merge and deploy the normal way. **Repeat the deliberate pass at
once**, because a managed group in count mode stops at its first matching rule,
so a second rule can only surface after the first is excluded. If anything is
refused, set `mode` back to `"count"` (or use the emergency switch below),
exclude the rule, and try again. Staging leads by one release: staging blocks
before production does.

**Excluding one rule.** Add its name to `COMMON_RULES_ALWAYS_COUNTED` in
`infra/infra/components/waf.py` (for a rule in another group, give that group
its own `rule_action_overrides` the same way) and deploy. The rule then reports
`EXCLUDED_AS_COUNT` in the log, which the report shows.

**Turning the firewall off.** `enabled: false` and a deploy removes the web
ACL, its association, the log group and the logging configuration; the deploy
then resolves no CAPTCHA values and the form shows no puzzle. Nothing has to
be restored. `captcha: false` alone removes the CAPTCHA rule and the puzzle at
the next deploy.

**Emergency off switch (production, a false positive that cannot wait for a
release).** Detach the web ACL from the load balancer in seconds, no deploy:

```bash
aws wafv2 disassociate-web-acl --region eu-west-2 \
  --resource-arn "$(aws ssm get-parameter --region eu-west-2 \
    --name /policy_atlas_v3/shared_alb/arn --query Parameter.Value --output text)"
```

**A deploy does not re-attach it**: CloudFormation updates only what changed in
the template and does not see a detached association, so the firewall stays
off until someone puts it back. Make the config change (`mode: count` or an
exclusion), deploy, and then re-attach by hand:

```bash
aws wafv2 associate-web-acl --region eu-west-2 \
  --web-acl-arn "$(aws wafv2 list-web-acls --scope REGIONAL --region eu-west-2 \
    --query "WebACLs[?Name=='policy-atlas-v3-api'].ARN" --output text)" \
  --resource-arn "$(aws ssm get-parameter --region eu-west-2 \
    --name /policy_atlas_v3/shared_alb/arn --query Parameter.Value --output text)"
```

`scripts/waf_report.sh` is the quick check that the firewall is attached and
counting again. A deploy-time check of the association is a deferred seam.

**The token domain and where the CAPTCHA values come from.** The CAPTCHA
puzzle runs on the splash page (`<domain_name>`) and its token is spent on the
API (`api.<domain_name>`). The web ACL's token domain list therefore holds the
environment's `domain_name`, which covers both as subdomains. The page needs
two public values to show the puzzle: the account's CAPTCHA script URL and its
API key (§ 2, precondition 7). `deploy.sh` reads them with `aws wafv2
list-api-keys` before `cdk deploy` and passes them to the frontend build as
`VITE_WAF_CAPTCHA_SCRIPT_URL` and `VITE_WAF_CAPTCHA_API_KEY`; the production
build guard refuses a build without them while the CAPTCHA is on. They are
not secrets and may appear in the deploy log. When the CAPTCHA is off neither
is set and the form behaves as before.

**The log.** Matched requests only (counted, blocked, CAPTCHA'd or
counted-by-override) go to the CloudWatch log group
`aws-waf-logs-policy-atlas-v3` (the `aws-waf-logs-` prefix is AWS's rule),
kept for one month. Ordinary traffic is never logged. The records hold client
addresses and request headers; the `authorization`, `cookie` and
`x-aws-waf-token` headers are redacted before writing, so a signed-in
person's bearer token never reaches the log. The log group is private to the
account.

**Capacity, and the dry run.** A web ACL may use 1,500 capacity units; these
rules use 987 (`aws wafv2 check-capacity`, 2026-11-18). The same command is the
dry run for any rule change: it validates every statement against the WAF
service without creating anything (the synth tests cannot, see
`docs/knowledge/cdk-any-typed-property-takes-cloudformation-dict.md`). Take the
`Rules` list from the synthesised `PaV3AppStack.template.json`, base64-encode
each `SearchString`, and pass it as `--rules file://rules.json`.

**Cost.** About $11 a month per environment (the web ACL, six rules), plus
$0.60 per million requests and $0.40 per thousand CAPTCHA puzzles.

### Security headers (task 064c)

**What it is.** CloudFront adds a set of security headers to every response
of the web app: the pages, the scripts, the fonts, and the deep links that
the error responses answer with `/index.html`. A **response headers policy**
(`policy-atlas-v3-security-headers`, built by
`infra/infra/components/security_headers.py` in the app stack) holds them and
is attached to both cache behaviours (the default one and `/index.html`). It
replaced AWS's managed `SECURITY_HEADERS` policy, which cannot be changed.
The API's responses come from the load balancer and the ops pages (task 065)
from the backend, so neither gets these headers. ADR 0048 has the reasoning.

**The headers.**

| Header | Value | Why |
| --- | --- | --- |
| `Strict-Transport-Security` (HSTS) | `max-age=31536000; includeSubDomains` | Browsers use only HTTPS for this host and every subdomain, for one year. |
| `X-Frame-Options` | `SAMEORIGIN` | Only our own pages may show the app in a frame (older browsers). |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Other sites see only our host name, never the page path. |
| `X-XSS-Protection` | `1; mode=block` | Kept from the managed policy; modern browsers ignore it. |
| `X-Content-Type-Options` | `nosniff` | The browser trusts the declared file type. |
| `Permissions-Policy` | eight features off: accelerometer, camera, geolocation, gyroscope, magnetometer, microphone, payment, usb | The app uses none of them, so nothing on the page may. |
| `Content-Security-Policy` or `Content-Security-Policy-Report-Only` | the CSP below | The browser refuses scripts, network calls and frames from any source not listed. |

The first five have the managed policy's values and override flags (only
`X-Content-Type-Options` replaces a value sent by the origin), with one
change: HSTS adds `includeSubDomains`. The two new headers always replace an
origin value, so a header from S3 can never weaken them.

**HSTS `includeSubDomains` has a long tail.** A browser that saw it forces
HTTPS on every subdomain of the domain for up to a year, even after a
rollback. Every web name under `policyatlas.uk` and `v3.policyatlas.uk`
served HTTPS on 2026-11-18. Do not add a plain-HTTP subdomain under either.

**The CSP (Content Security Policy).** The component builds it from
`pa_config.json`; it is never written by hand. Each directive lists the
sources the browser may use for one kind of resource. `'self'` means the
app's own host.

| Directive | Sources | Where each source comes from |
| --- | --- | --- |
| `default-src` | `'self'` | Anything not listed below. |
| `script-src` | `'self'`, plus `https://*.captcha-sdk.awswaf.com` when the CAPTCHA is on | The app bundle; the WAF CAPTCHA script, which loads from `<id>.<region>.captcha-sdk.awswaf.com` (`backend.waf.captcha`). Never `'unsafe-inline'` or `'unsafe-eval'`. |
| `style-src` | `'self' 'unsafe-inline'` | The app CSS; Radix (dialogs, sheets) adds a `<style>` element at run time. Inline styles cannot run code. |
| `img-src` | `'self' data: blob:` | Upload previews (`blob:`) and theory-of-change image exports (`data:`). |
| `font-src` | `'self'` | The self-hosted fonts under `/fonts/`. |
| `connect-src` | `'self'`, `https://<backend_subdomain>.<domain_name>`, `https://cognito-idp.<aws_region>.amazonaws.com`, `https://<cognito_domain_prefix>.auth.<aws_region>.amazoncognito.com`, plus `https://*.awswaf.com` when the CAPTCHA is on | The API (including the progress stream); the Cognito sign-in settings; the Cognito token exchange and refresh; the CAPTCHA's own calls. |
| `frame-src` | `'self'`, the Cognito hosted domain | The sign-in library's hidden-frame fallback: the frame opens the Cognito domain, which sends it back to our own address. |
| `frame-ancestors` | `'self'` | Who may show our page in a frame (same as `X-Frame-Options`). |
| `form-action` | `'self'` | Where a form may post. |
| `object-src` | `'none'` | No plug-ins. |
| `base-uri` | `'self'` | No `<base>` tag pointing elsewhere. |

Sign-in and sign-out are page redirects to Cognito, which a CSP does not
govern. CloudFront allows at most 1,783 characters in the header; synth fails
above that.

**The key** `csp_mode` in `policy_atlas_config`, per environment:

| Value | Effect |
| --- | --- |
| `"report-only"` | The policy goes in `Content-Security-Policy-Report-Only`. The browser blocks nothing and prints a "[Report Only]" line in the console for each violation. |
| `"enforce"` | The policy goes in `Content-Security-Policy`. The browser blocks every violation. |

Never both headers at once. A missing key or any other value fails `cdk
synth`, which the deploy runs before it changes anything in AWS.
`deploy.sh` does not read the key.

**The manual pass.** There is no report collector, so the browser console is
the only place a violation shows. Run the pass after the first deploy in
report-only mode, again after the switch to enforce, and again whenever a
change adds a third-party library, script or host. In Chrome, open the
developer console, turn on "Preserve log", and sign in.

1. **First, the proof.** In the console, run `fetch("https://example.com")`.
   In report-only mode it must print a "[Report Only]" line naming
   `connect-src`; in enforce mode, a refusal line. If no line appears, stop:
   console silence then proves nothing.
2. Use every surface once: the splash page and the waitlist puzzle including
   its audio option (where the CAPTCHA is on); sign-in; sign-out; a token
   refresh (keep a signed-in tab open past the access token's one-hour
   lifetime, then use the app); the task list; a new task with an image upload
   preview; a running task with its progress stream; a side sheet; the
   sources view and its CSV and JSON downloads; the map view; a theory of
   change with its PNG, SVG and draw.io exports and print; a report's print;
   a public task view; the legal page; a deep link opened directly in a new
   tab (for example `/tasks/<id>`).
3. Record each console line that names the Content Security Policy, with the
   page and the blocked address. Never record tokens or user data.

Check the headers themselves with `curl`; the deep link proves the policy
reaches the error-response path:

```bash
for p in / /index.html /tasks/x; do
  echo "== $p"; curl -sI "https://<domain_name>$p" \
    | grep -iE 'content-security|permissions-policy|strict-transport|x-frame|referrer|x-content-type|x-xss'
done
```

**Switching to enforce.** After a report-only pass with no unexplained line,
set `csp_mode` to `"enforce"` for that environment, merge and deploy the
normal way, run the `curl` check, and repeat the manual pass at once: apart
from the refusal of the deliberate `fetch` in step 1, it must show zero CSP
lines. Staging leads by one release: staging enforces before
production does.

**Adding a source.** When a pass shows a real need (for example the CAPTCHA
script loading an image from `awswaf.com`), add the source in
`security_headers.py`, update its literal expected string in
`infra/tests/unit/test_security_headers.py`, and deploy. Never edit the policy
in the CloudFront console as a fix. CloudFormation rewrites the policy only
when the code's version of it changes, so a console edit can stay in place,
unseen, through many deploys, and then disappear at an unrelated policy
change. Never add `'unsafe-inline'` or `'unsafe-eval'` to `script-src`; a
library that needs either is a design question, not a header change.

**Rollback.** Set `csp_mode` back to `"report-only"` and deploy. CloudFormation
updates the policy in place; CloudFront applies it within minutes, and
`index.html` has a 60-second cache. For an emergency that cannot wait for a
deploy, edit the policy in the CloudFront console (Policies → Response headers
→ `policy-atlas-v3-security-headers`): move the CSP out of the security headers
or delete it. Then make the config change and deploy at once: that deploy
changes the policy, so it puts the code's version back. A deploy that does not
change the policy leaves a console edit in place. A full revert of the 064c change restores the managed policy. The
HSTS subdomain setting stays in browsers that saw it (above).

**Cost.** Nil. Response headers policies are free (20 custom policies per
account; this is the first).

## 5. Env & secret map

Generated from `settings.py`'s required/optional calls plus the direct
`os.environ` readers (`api/deps.py`, `core/tracing.py`,
`evidence_search/sourcing/search_live.py`). `LANGFUSE_HOST` is what the provisioned
secret carries (v2's key name); tracing accepts it natively, so deployment injects it
instead. Which AI models the backend uses is not set here: it comes from the
committed file `backend/src/policy_atlas/model_routes.toml`, and the deployment
passes only the route name (task 053). Other `POLICY_ATLAS_*` tuning and the
fixture corpus are intentionally omitted from the deployed task.

| Var | Source | Consumer file |
| --- | --- | --- |
| `APP_ORIGIN` | config value: `https://{domain_name}` | `api/settings.py` |
| `DATABASE_URL` | Secrets Manager field: DB secret `db_connection_string` | `api/settings.py`, `core/db.py` |
| `DB_MAX_OVERFLOW` | config value: `backend.db_max_overflow` | `api/settings.py` |
| `DB_POOL_SIZE` | config value: `backend.db_pool_size` | `api/settings.py` |
| `FORWARDED_ALLOW_IPS` | stack value: the VPC's address range (`vpc_cidr_block` from the app stack's VPC lookup; task 064a, Q11) | uvicorn (not the application): only a proxy inside the VPC, which is the load balancer, may set the client address in `X-Forwarded-For`; `*` would let any client write it |
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
| `AWS_BEARER_TOKEN_BEDROCK` | Secrets Manager field: `policy_atlas_v3/app` `AWS_BEARER_TOKEN_BEDROCK`, passed only on a Bedrock route | `core/model_routes.py` (via the route's key variable), `boto3` |
| `OPENAI_API_KEY` | Secrets Manager field: `policy_atlas_v3/app` `OPENAI_API_KEY` | `core/model_routes.py` (read on `openai-direct`), `core/openai_client.py` |
| `OPENALEX_API_KEY` | Secrets Manager field: `policy_atlas_v3/app` `OPENALEX_API_KEY` | `api/deps.py`, `evidence_search/sourcing/search_live.py` |
| `OPENALEX_EMAIL` | Secrets Manager field: `policy_atlas_v3/app` `OPENALEX_EMAIL` | `evidence_search/sourcing/search_live.py` |
| `OVERTON_API_KEY` | Secrets Manager field: `policy_atlas_v3/app` `OVERTON_API_KEY` | `api/deps.py`, `evidence_search/sourcing/search_live.py` |
| `PA_BACKEND_MODE` | config value: `live` | `api/deps.py` |
| `POLICY_ATLAS_MODEL_ROUTE` | config value: `backend.model_route` (`bedrock` on staging and production) | `core/model_routes.py` |
| `POLICY_ATLAS_INGEST_MODE` | config value: `backend.ingest_mode` (`queued` on staging and production since 2026-11-04; `in_process` is the laptop mode) | backend ingest stage (task 057) |
| `POLICY_ATLAS_INGEST_QUEUE_URL` | stack value: the ingest queue's URL | backend ingest stage (task 057) |
| `POLICY_ATLAS_FIXTURE_CORPUS` | omitted (development/test fixture override) | `evidence_search/sourcing/ingest_full_text.py` |
| `POLICY_ATLAS_SEARCH_CACHE_TTL_S` | omitted (development tuning; application default) | `evidence_search/sourcing/search_live.py` |
| `RUN_EXECUTOR_MAX` | config value: `backend.run_executor_max` | `api/settings.py` |
| `RUNS_PER_USER` | config value: `backend.runs_per_user` (3 in both environments; task 064a, Q7): how many runs one person may have running at once; administrators are exempt | `api/settings.py` |
| `TASK_QUOTA_PER_YEAR` | config value: `backend.task_quota_per_year` (50 in both environments; task 064a, Q8): how many tasks one person may create in a rolling 365 days; administrators are exempt | `api/settings.py` |
| `SSE_HEARTBEAT_SECONDS` | omitted (application default: 15) | `api/settings.py` |
| `SSE_POLL_INTERVAL_SECONDS` | omitted (application default: 0.4) | `api/settings.py` |

**Renamed in task 044:** `POLICY_ATLAS_PLANNER_MODEL` became
`POLICY_ATLAS_TASK_AGENT_MODEL`. No fallback read of the old name was added, and
the application default is unchanged, so a deployment that still sets only the
old name behaves exactly as before — the variable is simply ignored and the
built-in default applies.

**Retired in task 053:** the per-step model settings (`POLICY_ATLAS_CHAT_MODEL`,
`POLICY_ATLAS_SYNTHESIS_MODEL`, `POLICY_ATLAS_AGENT_MODEL` and the rest) are
ignored with a warning; models are chosen in the route file.

**Switching to Bedrock** (task 053; diagrams in
`docs/tasks/053-bedrock-local-route/model-routing.html`):

1. Add a long-term Bedrock API key to `policy_atlas_v3/app` as the field
   `AWS_BEARER_TOKEN_BEDROCK`. Do this first: the stack asks ECS for the field as
   soon as the route is a Bedrock one, and a task naming a missing field fails to
   start.
2. Set `backend.model_route` to `bedrock` for that environment in
   `pa_config.json`, and merge.
3. Deploy. Existing projects were embedded with OpenAI; their chat search finds
   nothing on Bedrock until they are ingested again.

To switch back, set the route to `openai-direct` and deploy; the Bedrock field can
stay in the secret. Rotating the Bedrock key is a secret edit plus a forced new
deployment, like any other secret.

**Capacity values** (sized together for a 10-concurrent-run ceiling):
`RUN_EXECUTOR_MAX=10`, `DB_POOL_SIZE=15`, `DB_MAX_OVERFLOW=10`, task 2 vCPU /
8 GB (initial hypothesis — measured under load, not just arithmetic). Within
that ceiling one person may hold at most `RUNS_PER_USER=3` running runs (task
064a, Q7); administrators are exempt, like the task quota. No single ordinary user can take every slot.
A run waiting at a check-in is paused and does not count.

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
[`JUMPBOX.md`](./JUMPBOX.md) for the full operator and IAM guidance.

Prereqs: AWS CLI + session-manager-plugin; IAM allowing `ssm:StartSession` on the
jumpbox instance **and only its generated custom Session document**; permission
to read the database secret. Do not grant the engineer role access to the
AWS-managed remote-host port-forwarding document, which would let the caller
choose a different remote target.

**The ops CLI (task 033) runs over this same tunnel** — the operator's
laptop, `uv run python -m policy_atlas.ops --env staging|prod ...` with
`DATABASE_URL` pointing at `localhost:15432`, or the equivalent make
wrappers (`make user-create ENV=... EMAIL=... NAME=... [ORG=...]` — see the
Makefile's ops block; `scripts/ops_run.sh` performs this section's setup
and tunnel automatically, reusing an already-open one), under the operator's own IAM
(Cognito `cognito-idp:ListUsers` + `cognito-idp:AdminCreateUser` +
`cognito-idp:AdminSetUserPassword`, plus `cognito-idp:AdminDisableUser` and
`cognito-idp:AdminUserGlobalSignOut` for `user deactivate` since task 064a, and
`cognito-idp:AdminGetUser` plus `cognito-idp:AdminEnableUser` for `user reactivate`
since task 066, nothing
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
  is lost and pre-033 code lists *all* conversations on a task to its
  owner — a rollback after adoption exposes colleagues' private chats to
  the task owner (evidenced by
  `test_downgrade_erases_chat_authorship_exposing_colleague_chats`, which
  also proves a re-upgrade misattributes the rows rather than undoing the
  exposure). It also drops both `visibility` columns, so a later re-upgrade
  resets every row to `org` and no private choice can be reconstructed. The
  real safety net is the dark launch: with no organisations enrolled the
  behaviour is byte-identical to pre-033, and **de-enrolling an
  organisation reverts it without a deploy**. A schema downgrade is a last
  resort requiring a backup restore first (Aurora keeps automatic backups for
  7 days on staging and 35 days on production, `backup_retention_days` in
  `db_config.json` since task 064a).
- **Manual downgrade procedure (last resort — the ECS migration task runs
  `alembic upgrade head` only and has no downgrade path):** scale the API
  to zero → restore or snapshot the cluster → open the § 6 tunnel → from
  `backend/` run `DATABASE_URL=<tunnel-url> uv run alembic downgrade
  b3c7d914e0a2` → deploy the pre-033 image → scale up. Do not do this on a
  database that has enrolled organisations without owner sign-off on the
  chat-exposure consequence above.
- **Task 057 (queued ingest, document store, SQL retrieval):** two independent
  rollbacks. *The reading stage:* set `backend.ingest_mode` to `in_process` in
  `pa_config.json` and deploy; the queue and function stay but receive nothing.
  Messages already in flight finish or dead-letter harmlessly (the row guard
  ignores a result for a row the new run has re-queued). *Retrieval and the
  store:* deploy the previous image, then (last resort, § 6 tunnel, API scaled to
  zero) `uv run alembic downgrade 152a234e2391`, which drops the three task 057
  revisions in order: the JSON vector column is rebuilt from the binary vectors
  at float32 precision (the pre-057 JSON held float64; search order can differ on
  near-ties), the backfilled `tokens` and `embedding` columns are dropped, the
  `queued` status and the two link-row columns (`ingested_by_run_id`,
  `fetched_from`) are dropped (rows in `queued` are set to `not_attempted`
  first). Snapshots stored by the body-hash key stay valid rows for the old
  code. Tested on the test database
  (`tests/core/test_migration_057_document_store.py`); not rehearsed on staging.
- **Each migration commits on its own (task 057):** Alembic now runs one transaction
  per revision. A downgrade that is refused part-way (a guard that stops it) leaves the
  revisions above the refusal already undone and committed; check `alembic current`
  afterwards and decide whether to upgrade back to head or carry on. Before task 057 a
  refusal rolled the whole downgrade back.
- **Task 064a (security quick wins):** every change reverts by deploying the
  previous image and CDK state, with four notes. The one migration adds an
  index only; its downgrade drops the index. The Cognito pool now has deletion
  protection: a deliberate pool replacement must turn it off first, which is
  the point. Lowering `backup_retention_days` again discards the backups older
  than the new value. The 12-character password minimum cannot be undone for
  people who already set a longer password, which is harmless.
- **Task 064b (firewall and CAPTCHA):** three levels, no data to restore.
  `waf.mode: count` undoes a block without removing anything; `waf.captcha:
  false` removes the CAPTCHA rule and the puzzle; `waf.enabled: false` removes
  the whole firewall, its log group included. Each is a config change and a
  normal deploy. The emergency switch in § 4 "The firewall" detaches the
  firewall in seconds without a deploy. The WAF API key is harmless to leave
  behind.
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
  orphans owner-scoped tasks. NB `RETAIN` protects the *pool and its
  users* from stack deletion, **not** identity continuity across a
  destroy/redeploy: a redeployed stack creates a *new* pool (new issuer, new
  `sub`s) and the retained pool is orphaned outside CloudFormation. To keep
  the same identities after a destroy, re-import the retained pool
  (`cdk import`) instead of letting the redeploy mint a fresh one.
- **Blast radius:** no rollback step can touch a v2-managed resource (v2 is
  read-only from this repo, structurally). v3 DNS records live only in the v3
  zone; worst case is the v3 domain going dark — v2 is never affected.
