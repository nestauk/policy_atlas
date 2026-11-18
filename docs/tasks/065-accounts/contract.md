# Task contract: 065-accounts

One contract for the whole accounts programme, in three deployable steps (A, B, C). The
shape was agreed with the owner on 2026-11-16 and is recorded in the
[064 programme map](../064-security-hardening/programme.md) § "The ops portal is a separate
task (065)". That file is on the `task/064a-security-quick-wins` branch and reaches `dev` with
the 064a merge; this contract repeats what it needs, so it reads cold without it.
Boundaries are in [AGENTS.md](../../../AGENTS.md); specs in [docs/specs/](../../specs/index.md).

> **Status:** revision 4 (B14 cohorts added by the owner, 2026-11-18, after the build) on revision 3.1, approved 2026-11-16 · owner (plan gate). Revision 1 approved 2026-11-16 · owner, after
> discussing six decisions (sweep in the ops service; page in the app; resend instead of
> reissue; domain table by CLI; templates before the sender flips; no lifespan jobs in ops
> mode). Contract-stage adversarial review 2026-11-16: Codex, 10 findings (record in the
> gitignored `research/`). Revision 2 folds them: no `/me` on the ops host (F1); the real abuse
> ceiling, a sweep cap and a resend cooldown (F2); one idempotent account command instead of
> reusing `create_user` for existing accounts (F3); a self-signup flag and a deploy order that
> stops both services before migrating (F4); a split lifespan with a patched test (F5); a
> separate OpenAPI document for the ops host (F6); templates applied only with the SES sender,
> which retires the "templates before the sender flips" decision (F7); a durable `ops_action`
> table (F8); browser-created accounts always have an organisation (F9). **Revision 3
> (2026-11-16, owner, after the explainer and wireframes):** the ops pages are served from the
> ops address itself, not from the public app (this adopts F10, which revision 2 had declined;
> B2, B3, B6, B7, B9, B10); quota controls on the ops pages, including simultaneous tasks with a
> warning (B12); the people list acts on several people at once (B6); and a least-privilege
> database login for the ops service (B13). **Revision 3 approved 2026-11-16 · owner** (B13
> included).
> Re-approval: 2026-11-16 · owner. **Revision 3.1 (2026-11-16, from the plan-stage Codex review,
> approved by the owner at the plan gate, 2026-11-16):** B13's grant list follows what the command
> functions already do (one `DELETE`, on `project_membership`; column-level `UPDATE`s; a trigger
> so the ops login can clear but never set `is_admin` or `is_ops`); B6's bulk offboard shows every
> person and takes the count as the typed confirmation; B1 states that de-enrol and offboard
> clear the flags through the ops host. · Plan approved: 2026-11-16 · owner (draft 2) · ADR:
> [0046](../../adr/0046-ops-service-ops-pages-self-signup-and-ops-database-login.md), Accepted
> 2026-11-16 (0045 belongs to 064a).

## Goal

Three outcomes, in the order they must land:

- **A. Email that arrives, from our domain, on brand.** Every message the Cognito user pool
  sends (invitation, verification code, password reset) leaves through Amazon SES from
  `no-reply@` the product domain, with Nesta branding, instead of the default Cognito sender
  that is capped at 50 a day and lands in spam.
- **B. Non-technical team members manage accounts in a browser.** Create organisations, create
  accounts, enrol, move, de-enrol and offboard people, approve waitlist requests and reassign
  rows, from a page that is reachable only from allowlisted network addresses, the way
  Metabase is run today. The operator CLI stays for the two privilege grants.
- **C. A person with a `nesta.org.uk` address gets an account without an operator.** They use
  the existing "Request access" form; the system creates the account in the Nesta
  organisation and Cognito sends the invitation. Everyone else lands on the waitlist as now.

## Deliverable

One pull request on `task/065-accounts` into `dev` landing steps A, B and C with tests, the
new keys in `infra/pa_config.json`, the additive migration, ADR 0046, and the deployment
notes. Each step is switchable on its own (§ Constraints, rollback), so staging can run A
before its SES production access is granted and B before C.

## Terms

| Term | Meaning |
|---|---|
| **SES** | Amazon Simple Email Service, the AWS service that sends email. Each AWS account has its own SES setup per region. |
| **SES identity** | A domain (or address) that SES has verified as ours. Ours: `v3.policyatlas.uk` in the staging account, `policyatlas.uk` in the production account, both region `eu-west-2`. They already exist; this slice never creates them. |
| **DKIM** | DomainKeys Identified Mail: a signature that proves a message came from our domain. SES "Easy DKIM" published the three DNS records into Route 53 when the identities were created. |
| **SES sandbox / production access** | A new SES account may only email verified addresses (200 a day). "Production access" lifts that. Both accounts have it as of 2026-11-16. Cognito refuses to send through a sandboxed account. |
| **Pool email configuration** | The Cognito user pool setting that names the sender. Today it is `COGNITO_DEFAULT` (`no-reply@verificationemail.com`). Step A sets it to `DEVELOPER` mode with the SES identity's ARN and a From address. CDK: `UserPoolEmail.with_ses`. |
| **Invitation** | The email Cognito sends on `AdminCreateUser`: a temporary password valid 30 days. The person sets their own password at first sign-in (`FORCE_CHANGE_PASSWORD`). This is the "expiring link" of the programme: reading it proves the mailbox is theirs. |
| **Message templates** | The pool's `UserInvitationConfig` and `UserVerificationConfig`: subject and body (HTML allowed, up to 20,000 characters) with the placeholders `{username}` and `{####}` (the code or temporary password). The verification template also serves password resets. No Lambda is involved. |
| **Hosted UI** | Cognito's sign-in pages at `policy-atlas-v3*.auth.eu-west-2.amazoncognito.com`. Unchanged by this slice. |
| **`app_user`** | The identity row (`core/schema.py`): `user_id` (the token subject), `display_name`, `email`, `org_id`, `is_admin`. Email is stored for ops use only and is never shown to another user (contract 033 § 3b). |
| **Admin flag** | `app_user.is_admin`: read every row, write nothing, set only by the CLI (ADR 0033 decision 4). Unchanged here. |
| **Ops role** | New: `app_user.is_ops`. Holders may call the ops routes on the ops service. Granted and revoked only by the CLI (`ops grant` / `ops revoke`). It grants no read of product rows. |
| **Ops service** | A second ECS Fargate service running the **same backend image** as the API, started in ops mode (§ B2). It serves the ops routes and the ops pages, and nothing that runs work. Hostname `ops.<domain>` (`ops.v3.policyatlas.uk` on staging, `ops.policyatlas.uk` on production). |
| **Ops pages** | The web pages for operators: a second build of the frontend project (its `ops` entry) shipped inside the backend image and served by the ops service at `https://ops.<domain>`. The public app at `<domain>` carries none of it. |
| **Ops database login** | New: a Postgres role `pa_ops` with table-by-table grants, used only by the ops service. The master login stays with the API and the migration task. |
| **Allowlist** | The SSM Parameter Store `StringList` of up to 8 address ranges (CIDRs) that may reach a hostname, enforced by load-balancer listener rules on host header plus source address. Metabase uses `/policy_atlas_v3/metabase/allowed_cidrs`; the ops service gets its own parameter, same validator (`infra/metabase_allowlist.py`). |
| **Task role** | The IAM role an ECS task runs with. The public API's task role has no Cognito permission today and keeps none. The ops service's task role is the only one with Cognito write permissions. |
| **Command functions** | The plain functions in `backend/src/policy_atlas/ops/commands.py` (`create_organisation`, `create_user`, `enrol_user`, `de_enrol_user`, `assign_rows`, `set_admin`, and 064a's offboard) that both the CLI and the ops routes call. Their semantics do not change here; one function is added (next row). |
| **Ensure-account command** | New: `ensure_account_enrolled(conn, cognito, *, email, display_name, org)`. Idempotent: when the address is not in the pool it creates the Cognito account and sends the invitation, then enrols; when the address exists and is unenrolled it enrols without sending; when it exists and is enrolled elsewhere it refuses with a reason. A retry after "Cognito created, database write failed" therefore lands on the second branch. The sweep and the ops page's create and approve actions use it; the CLI's `create_user` is unchanged. |
| **Ops action record** | New table `ops_action`: one row per write on the ops host (time, actor subject, action, target subject or row id, outcome). The durable audit trail; the log line is the live one. |
| **Self-signup flag** | `self_signup.enabled` in `pa_config.json` (env `POLICY_ATLAS_SELF_SIGNUP`), default false. The sweep runs only when it is true and the service is in ops mode. |
| **Waitlist row** | `waitlist_entry` (task 036): what the public "Request access" form writes. Today nothing reads it but a human with database access. |
| **Domain table** | New: `organisation_domain` (`domain` → `org_id`). A request whose address ends in a listed domain is turned into an account in that organisation. One row for now: `nesta.org.uk` → Nesta. |
| **Sweep** | A loop in the ops service that, every minute, turns waitlist rows with a listed domain into accounts. It exists so that the public API never needs a Cognito permission. |
| **Startup sweep, drainer, executor** | The API's lifespan jobs (`api/app.py` `_lifespan`): the orphan sweep, the continuation drainer and the run executor. Exactly one process may run them (web-api.md § Deployment posture). The ops service runs none of them. |
| **Quota override** | New: nullable integer columns `task_quota_per_year` and `runs_per_user` on `app_user` and on `organisation`. Null means inherit; `0` means no limit. One resolver gives a person's effective limits: their own override, else their organisation's, else the settings value (`task_quota_per_year` 50, `runs_per_user` 3). Administrators stay exempt from the task quota. |
| **A1 to C6** | The numbered items below. The rubric and the plan use these ids. |

## Read first

- [ADR 0033](../../adr/0033-organisation-tenancy-and-global-admin-read.md) decisions 2, 4 and 7
  and § Consequences; [contract 033](../033-organisations/contract.md) § 3a (closed list of
  `is_admin` readers), § 3b (never name a person by email), § 9 (the CLI accepts no password),
  § Out (what this slice reopens).
- [web-api.md](../../specs/system/web-api.md) § Auth boundary, § Waitlist, § Deployment posture
  (the one-process invariant).
- [data-model.md](../../specs/system/data-model.md) § Tenancy.
- [Contract 036](../036-splash-page/contract.md) (the waitlist) and the 064a contract Q10
  (`user offboard`) and Q8 (the admin-reader list test) on the 064a branch.
- Infra: `infra/infra/cognito_auth.py`; `infra/infra/analytics_stack.py` lines 280 to 372 (the
  Metabase service, target group, allowlist rules and record); `infra/metabase_allowlist.py`;
  `infra/infra/policy_atlas_stack.py` (task definition, environment, task-role grants);
  `infra/tests/unit/test_synth.py` (the Cognito and Metabase pins); `infra/DEPLOYMENT.md` step 3
  (the invitation workaround to retire).
- Backend: `ops/commands.py`, `ops/cli.py`, `ops/environment.py`; `api/routers/me.py`;
  `api/routers/waitlist.py`; `api/app.py` `_lifespan` and `include_router` block;
  `api/settings.py`; `backend/Dockerfile` (`--no-group ops`); `backend/pyproject.toml` the
  `ops` dependency group.
- Frontend: `frontend/src/auth/README.md`; `frontend/src/api/client.ts` (`VITE_API_BASE_URL`);
  `frontend/src/views/splash/WaitlistForm.tsx`; `DESIGN.md`.
- `docs/deferred.md`: "SES-backed pool email" (discharged by A), "An admin dashboard / admin
  surface" (reopened by B), "Waitlist spam: WAF rate rule" (unchanged; 064b), "MFA on the pool"
  (064d, unblocked by A).
- Research with sources, gitignored: `research/cognito-signup.md`, `research/cognito-ses.md`.

## Facts settled on 2026-11-16 (owner)

1. SES: the production account is fully set up. The staging identity `v3.policyatlas.uk` was
   verified and its production access granted the same day (owner report, 2026-11-16; the
   build confirms it with `aws sesv2 get-account` before setting `email.enabled`).
2. Cognito cannot send through an SES identity in another AWS account, so Nesta's shared SES
   account cannot carry this mail. The Tech Team accepts the project accounts owning their
   own identities.
3. Self-service sign-up is for `nesta.org.uk` only. `gov.uk` and every other domain are
   deferred; the domain table makes adding one a row, not a deploy.
4. Every person who will use the ops page is covered by the allowlist (office network or VPN).
5. The ops surface is a separate address-gated service, not a page in the public app, so the
   public API keeps no AWS write permission.
6. The ops pages are served from the ops address itself (`https://ops.<domain>`), not from the
   public app: one address, one allowlist, no ops code on the public site (owner, 2026-11-16,
   after the explainer and wireframes).
7. Quotas, including simultaneous tasks, are editable on the ops pages, with a warning on the
   runs field (owner, 2026-11-16).
8. The ops service uses a database login that can only touch the tables it needs (B13; owner,
   2026-11-16).

## The work

### Step A — SES wiring and branded email

| Id | Change | Detail |
|---|---|---|
| **A1** | Pool sends through SES | `cognito_auth.py` sets the pool email configuration from three new keys per environment in `pa_config.json`: `email.enabled` (bool), `email.sender_domain` (the SES identity, e.g. `v3.policyatlas.uk`), `email.from_address` (e.g. `no-reply@v3.policyatlas.uk`) and `email.from_name` (`Policy Atlas`). With `enabled` false the pool keeps `COGNITO_DEFAULT`, which is how staging deploys before its production access lands. The identity is referenced by ARN from the domain name; **nothing in CDK creates an SES identity or DNS record**, because both identities already exist and a create would fail on the duplicate. |
| **A2** | Branded templates | Invitation and verification subjects and HTML bodies live in `infra/email/` as files read at synth and set on the pool **only when `email.enabled` is true**, together with the SES sender (Cognito's API reference ties custom subjects and bodies to the SES sending mode; the research could not confirm they work with the default sender, so the contract does not rely on it). The copy is owner-reviewed product voice: who we are, what to do next, the code or temporary password via `{####}`, the sign-in address, and a line saying to ignore the message if unexpected. The owner reviews the copy by opening the HTML files in a browser before the build ends, and sees the real message on staging once the sender is on, which both accounts now allow. The logo is served from the SPA bucket at `/brand/email-logo.png`, since email cannot embed assets. |
| **A3** | Synth pins | `test_synth.py`: with `email.enabled` true the pool carries `EmailSendingAccount: DEVELOPER`, the identity ARN in the pool's own account and region, the From address, and both templates (each containing `{####}`, the invitation containing `{username}`); with it false the pool carries no email configuration and no templates; the pool still has no Lambda triggers. |
| **A4** | Deployment notes | `infra/DEPLOYMENT.md`: how to check production access (`aws sesv2 get-account`), the order (identity verified → production access → `email.enabled` true), the sending quota now being SES's, and `--invite manual` demoted from workaround to fallback. |
| **A5** | Deferred ledger | `docs/deferred.md`: the SES entry is discharged with the date; the `--invite manual` path stays as a recorded fallback. |

### Step B — the ops service

| Id | Change | Detail |
|---|---|---|
| **B1** | Ops role | Migration adds `app_user.is_ops boolean not null default false`. CLI gains `ops grant` / `ops revoke` (`--email` or `--sub`) mirroring `admin grant` / `admin revoke`, including the post-commit admin trace. **No HTTP route sets `is_ops` or `is_admin`**: de-enrol and offboard clear both through the command functions, and a database trigger (B13) refuses any statement from the ops login that sets either to true; the ops routes' own dependency and the `/me` projection are the only readers, asserted the way 033 asserts the `is_admin` readers. `user offboard` clears `is_ops` as it clears `is_admin`. |
| **B2** | Ops mode | A new setting `POLICY_ATLAS_SERVICE_ROLE=api\|ops` (default `api`). In `ops` mode `create_app` mounts `/healthz`, `/readyz`, the `/api/v1/ops/*` routes, and the **ops pages**: the static bundle the image carries (B3, B6), with every path that is not `/api/*` or a health check answered by its `index.html` so the browser router works. `/api/v1/me` is **not** mounted there: it creates an `app_user` row on first call, and a signed-in non-ops person on the allowlisted network must be able to create nothing through the ops host. Every `/api/v1/ops/*` route carries the ops-role dependency; the static files carry no data and need none. The lifespan is split into an API variant and an ops variant: the ops variant creates no run executor, runs no startup sweep, no continuation drainer and no ingest consumer, and starts only the database engine, the authenticator and (with the self-signup flag) the sweep. In `api` mode neither the ops routes nor the static bundle is mounted. Tests: the route tables of both modes; and, with the executor constructor and `continuation.startup_sweep` patched, an ops-mode start calls neither. This keeps the one-process invariant of web-api.md § Deployment posture. |
| **B3** | Infra and image | In `policy_atlas_stack.py`, following the Metabase shape: a Fargate service from the same image with the smallest task size, its own target group, listener rules on host header `ops.<domain>` plus source addresses from a new SSM parameter `/policy_atlas_v3/ops/allowed_cidrs` (validated and sized by `metabase_allowlist.py` given the parameter name; `scripts/deploy.sh` passes the count), and an A record. Config in `pa_config.json` under `ops`: `subdomain`, `cpu`, `memory_limit_mib`, `desired_count`, `allowed_cidrs_parameter_name`. Environment: the ops database login (B13) and the OIDC values only; no model or search keys; `APP_ORIGIN` is `https://ops.<domain>`, so page and API share one origin and the browser makes no cross-origin call. `cognito_auth.py` adds `https://ops.<domain>` and `https://ops.<domain>/` to the app client's callback and logout URLs (synth-pinned). **Its task role gets the Cognito actions the command functions need** (`AdminCreateUser`, `AdminGetUser`, `ListUsers`, `AdminDisableUser`, `AdminUserGlobalSignOut`) scoped to the pool ARN. The **public API task role gets none**, and a synth test asserts both. **Image:** `backend/Dockerfile` gains a Node build stage that builds the frontend's `ops` entry (B6) and copies the result into the runtime image at `/app/ops-ui`; the API runs the same image and leaves the directory unmounted. `.dockerignore` admits the frontend sources that build needs and nothing else. |
| **B4** | Ops routes | All under `/api/v1/ops`, bearer-authenticated, and refused with `403 forbidden` for a caller without the ops role (the caller is signed in, so the 404 rule for hidden rows does not apply). Each write calls a command function and records one `ops_action` row (B11) plus one `ops.action` log line, both with the caller's subject, the action, the target and the outcome. Routes: list and create organisations; list people (subject, display name, email, organisation, flags, created, last invited); **create a person in an organisation** (the ensure-account command; the organisation is required on the web, so a browser-created account is never unenrolled; the CLI keeps its no-organisation form and `manual` mode); enrol or move (`enrol_user`), de-enrol, offboard; **resend invitation** (`AdminCreateUser` with `MessageAction=RESEND`, the web-safe replacement for the CLI's `reissue`, which prints a password and stays CLI-only), refused with 429 within one hour of the last send, recorded in new column `app_user.invited_at`, which the ensure-account command also sets; assign a task or project to an organisation; list waitlist rows; **set or clear quota overrides** for a person or an organisation (B12); **approve** a waitlist row into an organisation (the ensure-account command with the row's email and name, then the stamp of § C2). Reads carry emails: that is the ops-facing use `app_user.email` was stored for, and it is visible only to ops-role holders on the address-gated host. |
| **B5** | Image can import the commands | The `mypy_boto3_cognito_idp` imports in `ops/commands.py` and `ops/environment.py` move under `TYPE_CHECKING`, because the runtime image drops the `ops` dependency group while `boto3` itself is a main dependency. The CLI's environment check (`ops/environment.py`) stays CLI-only; the service takes the pool id from `OIDC_ISSUER`. |
| **B6** | Ops pages | A second entry in the same frontend project (`frontend/ops.html` → `src/ops/main.tsx`, `pnpm build:ops` → `frontend/dist-ops/`), sharing the design system, the auth code and the generated types, and shipped inside the backend image (B3), served only in ops mode (B2) at `https://ops.<domain>`. It signs in with the same Cognito client. The public SPA gains **no route, no link and no code**; ops users bookmark the address, and a signed-in person whose first ops call returns 403 sees "Your account does not have the ops role" and nothing else. The shell is the ops pages' own: a top bar with the wordmark, an "Ops" tag, the sections People, Organisations and Requests, and the signed-in person's menu; the product's New, Tasks and Projects do not appear, because ops work is separate from using the product (owner, 2026-11-16). Sections: organisations (with quota defaults, B12); people (create in an organisation; enrol or move; de-enrol; offboard; resend invitation; set quota), where several people can be selected and one action applied to all of them, the confirmation naming every person and the route running the command function once per person with its own `ops_action` row, so one failure leaves the others recorded; requests (approve into an organisation); move a task or project to an organisation. Plain tables and forms in the existing design system; offboard confirms by typing the address for one person, and for several the dialog lists every person's name and address and takes the count as the typed confirmation (revision 3.1). No design annex: the owner's explainer and wireframes (an artifact, not committed) settled the direction; the `frontend-designer` agent builds it. (Supersedes revision 2's in-app `/ops` route and the F10 decline: with one address the allowlist covers the pages as well as the routes, and the public app stays untouched. The security boundary, the host, is unchanged.) |
| **B7** | Ops OpenAPI document | The ops routes are **not** in the public OpenAPI document, because the public app never mounts them. `export_openapi.py` gains an ops-mode export to a second document, `frontend/openapi-ops.json`, from which `frontend/src/api/gen/types-ops.ts` is generated; `make openapi-sync` and `make drift-check` cover both documents. The ops document's server entry names the ops host. `MeOut` is **unchanged**: the public app has no ops surface and needs no `is_ops` projection (revision 2's addition is withdrawn). |
| **B8** | Migration order | The migration is additive and is rebased after `dev`'s head, which will include 064a's index migration, before the PR (never edit `dev`'s migrations). |
| **B9** | Tests | Conformance: ops routes 401 without a token, 403 with a token and no ops role, 200 with the role; a non-ops token creates no `app_user` row through any ops-host route; the `api`-mode app has no `/api/v1/ops` paths and serves no static file; the `ops`-mode app has no `/me`, task, run or SSE paths, answers `/` and `/people` with the pages' `index.html`, and answers `/api/v1/tasks` with 404. Unit: each write calls its command function, records an `ops_action` row and logs `ops.action`; a bulk action records one row per person and continues past one failure; the resend cooldown; the ensure-account command's three branches and the Cognito-created-then-database-failed retry; the reader list for `is_ops` is closed. Synth: B3, including the ops callback URLs and `APP_ORIGIN`. |
| **B10** | ADR 0046 | Amends ADR 0033 decision 4 and the 033 Out list: an ops role separate from the admin flag; HTTP writes to `app_user` and `organisation` exist, on the ops service only; email is visible to ops-role holders there; "an admin surface" is no longer Out. Records the rejected shapes (page inside the public app, including revision 2's in-app route; path rule on the public service; Cognito console; Retool-style tool) and why, the accepted abuse ceiling of C4, and the least-privilege database login of B13. |
| **B11** | Audit record | Migration adds `ops_action (action_id uuid primary key, at timestamptz, actor_user_id text, action text, target text, outcome text)`. Every ops-host write and every sweep invitation inserts one row in the same transaction as its database effect (a Cognito call that succeeded before a failed transaction is recorded by a second attempt's row). Append-only: no route updates or deletes it. The ops page does not show it in this slice; it is queryable by an operator. This replaces the one-month log retention as the audit trail that ADR 0033 decision 4 left as the sole control. |
| **B12** | Quota controls | Migration adds the four nullable integer override columns of § Terms "Quota override" with `CHECK (>= 0)`. A resolver `effective_limits(conn, user_id)` in `routers/common.py` returns the pair (task quota, run cap) by the order in § Terms; the task-create check (064a Q8), the run-cap check (064a Q7) and `GET /api/v1/me` call it and nothing else reads the columns. `MeOut.task_quota` is null when the effective task quota is "no limit", as it already is for administrators, so the quota band hides itself. New command function `set_quota(conn, *, user_id or org_id, task_quota_per_year, runs_per_user)` writes the overrides (null clears); the CLI gains `user quota` and `org quota` subcommands and the ops routes call the same function, one `ops_action` row per call. On the ops pages the fields are "Tasks per year" and "Simultaneous tasks"; the second carries a warning that raising it takes shared run capacity from other people, and is editable there all the same (owner, 2026-11-16). Tests: resolver precedence (person over organisation over settings), `0` means unlimited, administrators stay exempt, a cleared override falls back, the route 403s without the role. |
| **B13** | Ops database login | The ops service connects as its own Postgres role `pa_ops`; the API and the migration task keep the master login. A migration creates the role (idempotent, `NOLOGIN` until the deploy step below) and grants exactly what the command functions and the sweep do, read from `ops/commands.py` and pinned by a test: `USAGE` on schema `public` (no `CREATE`); `SELECT, INSERT` and column-level `UPDATE` on `app_user` (`org_id`, `email`, `display_name`, `is_admin`, `is_ops`, `invited_at`, the two quota columns), `organisation` (`name`, the two quota columns), `organisation_domain`, `waitlist_entry` (the two stamp columns); `SELECT, INSERT` on `ops_action`; `SELECT` and `UPDATE (org_id, visibility, is_public, updated_at)` on `task`; `SELECT` and `UPDATE (org_id, visibility)` on `project`; `SELECT, DELETE` on `project_membership` (the one delete: moving a person severs their cross-owner memberships, `_sever_cross_owner_memberships`); nothing on `capability_run`, `alembic_version` or any other table. A `BEFORE UPDATE` trigger on `app_user` raises when `current_user = 'pa_ops'` and the statement sets `is_admin` or `is_ops` from false to true, so the ops host can clear a privilege but never grant one (B1). A later migration that gives the ops service a new table or column extends the grant in the same migration. CDK creates a Secrets Manager secret for the role's password (generated, never in the repository) and the ops task's `DATABASE_URL` comes from it (plan P4). `scripts/deploy.sh` runs, after migrations and before starting the ops service, a sync that sets `LOGIN` and the password (plan P4). Tests: in the test database, connected **as `pa_ops` with a password** (not `SET ROLE`), every ops write of the conformance suite succeeds, and `DELETE FROM app_user`, `DELETE FROM task`, `SELECT FROM capability_run`, `SELECT FROM alembic_version`, `UPDATE task SET title`, `UPDATE app_user SET is_admin = true` and `CREATE TABLE` are each refused. Staging check (11) repeats the refusals over the real secret. Rollback: stop the ops service; the downgrade revokes, drops the trigger and drops the role. |
| **B14** | Cohorts (revision 4, owner 2026-11-18) | A cohort is a named group of people for pilots and research: a label, separate from the organisation, which still decides who sees whose work. A person can be in several cohorts. A second migration adds `cohort (cohort_id, name unique, description, starts_on, ends_on with ends_on >= starts_on, links text[], created_at)` and `cohort_member (cohort_id, user_id, added_at)`, both rows removed with the cohort. Links are optional web addresses of any kind (at most 10, each starting with `http://` or `https://`), not only research plans. The ops pages gain a Cohorts section (list, add, edit, delete, show people) and, on the People list, a Cohorts column, cohort names in the search, and "Add to cohort…" / "Remove from cohort…" for one person or many. Every create, edit, delete, add and remove writes one `ops_action` row. `pa_ops` gets `SELECT, INSERT, DELETE` on both tables and `UPDATE` on the five cohort detail columns. Out of scope here, for the next task: feature versions per cohort, numbers per cohort, CSV import, onboarding answers, a CLI for cohorts. |

### Step C — self-service for `nesta.org.uk`

| Id | Change | Detail |
|---|---|---|
| **C1** | Domain table | Migration adds `organisation_domain (domain text primary key, org_id uuid not null references organisation, created_at)`. CLI gains `org domain add --domain D --org ORG` and `org domain remove --domain D`. Domains are stored lower-cased. Deployment note: create the Nesta organisation and add `nesta.org.uk` in each environment. The ops page does not edit this table (deferred: adding a domain is a tenancy decision and rare). |
| **C2** | Waitlist row state | `waitlist_entry` gains `account_user_id text null` and `account_created_at timestamptz null`. The public `POST /api/v1/waitlist` route is **unchanged** in behaviour and response, so the form still reveals nothing (064a's M-30 rule). Only the ops service writes the two columns. |
| **C3** | Sweep | With the self-signup flag true, the ops-mode lifespan starts one loop: every 60 seconds, select waitlist rows with `account_created_at IS NULL` whose address domain (the part after `@`, lower-cased, exact match, no subdomains) is in the domain table, oldest first, **at most `self_signup.max_per_hour` rows per hour (default 20)**; for each, call the ensure-account command with the row's email and name and the domain's organisation, then stamp the row with the subject and time and record an `ops_action` row with actor `sweep`. An address already in the pool and unenrolled is enrolled and stamped without a send; one enrolled elsewhere is left unstamped, logged once, and shown on the ops page for an operator. A failure is logged and the row is retried next tick; one failing row never blocks the others. The public API therefore never needs a Cognito permission. |
| **C4** | Abuse ceiling, stated honestly | The form is public, so anyone can submit addresses they do not own, and the invitation is sent **before** mailbox ownership is proved; ownership is proved only when the invitation is used. The ceiling: one invitation per distinct address ever (unique email, permanent stamp), at most `max_per_hour` per hour across all rows, only to addresses in a listed domain (one domain for now), and a 429 cooldown of one hour on resend. The honeypot stays. **Ordering rule:** the self-signup flag is not set true on production before 064b's WAF rate rule is live; staging may run it earlier for testing. The ceiling and the ordering rule are recorded in ADR 0046. |
| **C5** | Ops page | Waitlist rows show "invited" with the time once stamped; the approve action is hidden for them. |
| **C6** | Tests | Unit: the domain match (exact, case-insensitive, no subdomain); the sweep stamps on success, skips already-stamped rows, retries after a failure, enrols without sending when the address exists unenrolled, leaves an address enrolled elsewhere for an operator, stops at the hourly cap, and does not start with the flag false. Conformance: the public waitlist response is byte-identical for a listed and an unlisted domain. |

## Scope / Out of scope

- **In:** A1 to C6 above; `pa_config.json`, `scripts/deploy.sh`, `infra/DEPLOYMENT.md`, `docs/deferred.md`, ADR 0046, `web-api.md` § Auth boundary and § Waitlist (additive paragraphs on the ops host and the sweep).
- **Out (⏸, recorded):** self-service for any domain but `nesta.org.uk` · Cognito self sign-up, Lambda triggers, passwordless sign-in and magic links · managed login or restyling the sign-in pages · MFA (064d, unblocked by A) · the privacy notice (H-07, after 065) · deleting a Cognito user and ownership transfer · multi-organisation membership and per-organisation roles · editing the domain table from the ops page · any email sent by the application itself (the only sender in this slice is Cognito) · a custom message Lambda · Metabase changes · the WAF rate rule (064b).

## Constraints & approval gates

Tier 4. Every gated class below needs the owner's approval at this contract, and the plan
names the rollback for each step.

- **Schema:** B1 (`is_ops`), B4 (`app_user.invited_at`), B11 (`ops_action`), B12 (four quota override columns), B13 (the `pa_ops` role and its grants), C1 (`organisation_domain`), C2 (two waitlist columns). All additive with reversible downgrades.
- **Auth / tenancy:** the ops role and the ops routes (B1, B4); ADR 0046 amends ADR 0033.
- **Production config:** `pa_config.json` `email`, `ops` and `self_signup` blocks; the pool email configuration and the app client's callback URLs; the new SSM parameter; the ops database secret; IAM on the ops task role; a new ECS service, target group, listener rules and DNS record.
- **Public interface:** `MeOut.task_quota` null for "no limit" (the admin case already exists); the `/api/v1/ops/*` routes in their own OpenAPI document, served only on the ops host.
- **CI / deploy:** `backend/Dockerfile` gains a Node build stage for the ops pages (B3) and `.dockerignore` changes with it; `scripts/deploy.sh` gains the `db-role sync` step (B13), reads the ops allowlist size as it does Metabase's, and its stop → migrate → start sequence now **stops both the API and the ops service before migrating** and starts the API, then the ops service, after. The same order applies to a downgrade.
- **Dependencies:** none new. `boto3` is already a main dependency.
- **Frontend:** a second Vite entry and build (`ops.html`, `build:ops`) and a second generated types file; the public bundle is unchanged; no scaffold or package-manager change.
- **Egress:** none. Cognito and SES are AWS control-plane calls from the ops service, not product data leaving.
- **Rollback, each exercised once on staging:** A: set `email.enabled` false and deploy (the pool returns to the default sender and default templates). B: `desired_count` 0, deploy; then, if the schema must go, the downgrade drops `is_ops`, `invited_at`, the four quota columns and `ops_action` with both services stopped, because the public API reads the quota columns. C: set `self_signup.enabled` false and deploy (the sweep stops); then, if the schema must go, stop the ops service and run the downgrade that drops the domain table and the waitlist columns. A rollback never drops a table while a service that reads it runs.
- **Ordering:** A can deploy to both environments now (both have SES production access; the build confirms with `aws sesv2 get-account`); B needs A for invitations to arrive; C needs B (the sweep lives in the ops service), the Nesta organisation and domain row, and on production 064b's rate rule (C4).

## Public / private boundary

Committed: code, templates, config keys, the ADR. Never committed: the allowlist address
ranges (SSM only, as for Metabase), temporary passwords (never logged; the web surface never
shows one), email addresses in logs (the `ops.action` line and the `ops_action` row carry
subjects and row ids, not addresses), the research notes and review records (gitignored
`research/`).

## Model route

n/a. No inference.

## Disciplines binding this slice

- **Don't flatten status.** ⏸ items above stay deferred, with their reopening condition in `docs/deferred.md`.
- **Model only what behaves.** `is_ops` exists because routes read it; `invited_at` because the cooldown reads it; the domain table because the sweep reads it; `ops_action` because an investigation reads it. No other flag.
- **Reuse, do not re-implement.** Every ops write goes through the command functions; a route that re-implements one is a defect.
- **Leave deferred seams as seams** in [docs/deferred.md](../../deferred.md).

## Stop conditions

Halt and escalate when: any gate above is reached without approval; the ops service turns out
to need a lifespan job the API also runs; the sweep would need a Cognito permission on the
public API; staging's SES production access is refused; scope grows past A1 to C6; the budget
is spent.

## Acceptance checks

- `make verify` green; `make openapi-sync` and `make drift-check` clean; infra synth tests green.
- Deterministic tests as listed in A3, B9 and C6. No AI eval applies.
- **Live, on staging, scoped to the changed surfaces** (about 40 minutes): (1) with `email.enabled` true: an ops-page "create person" sends an invitation from `no-reply@v3.policyatlas.uk` whose headers show DKIM pass, and the person signs in and sets a password; (2) "resend invitation" sends again, and a second resend within the hour gets 429; (3) with the self-signup flag true, a `nesta.org.uk` request on the splash form gets an invitation within two minutes and appears as "invited" on the ops page, and a non-listed address appears as a plain waitlist row with the same form response; (4) from a non-allowlisted address `https://ops.v3.policyatlas.uk` is refused by the load balancer; (5) a signed-in user without the ops role opens `https://ops.v3.policyatlas.uk` from the office, sees the ops shell with "Your account does not have the ops role", and gets 403 on every ops route; `GET /api/v1/me` on the ops host is 404; `https://v3.policyatlas.uk/ops` is the public app's not-found page and its bundle contains no ops code; (6) the deployed task-role policies: no `cognito-idp` action on the API's, the five on the ops service's; (7) each action above has an `ops_action` row; (8) on the ops page, set a person's task quota to 0 and their account page shows no quota band, then set it to 1 and a second task creation is refused with `task_quota`; (9) one full-chain smoke: a normal task run still completes, proving the ops service did not take over the executor; (10) each rollback in § Constraints exercised once; (11) on staging, connected as `pa_ops`, `DELETE FROM app_user` and `SELECT FROM capability_run` are refused.

## Verification evidence expected

In `verification.md`: the command results; the staging checks above with timestamps and the
invitation's `Authentication-Results` header (address redacted); the deployed task-role
policies for both services; the diff summary; confirmation that no address range, password or
address is in the committed diff or the logs quoted; known gaps and deferred seams.

## Risk tier & review focus

**Tier 4**: schema, auth, production config, IAM, a new service, a public-interface addition.
Review stack: contract verifier · code review · security review · adversarial review at the
contract, plan and code · human deep review · ADR 0046 · rollback plan above.

Focus: the public API's task role must end with no Cognito permission; the ops service must
run none of the API's lifespan jobs and serve no `/me`; `is_ops` and `is_admin` must have no
HTTP writer; the form response must stay identical for listed and unlisted domains; the
sweep and resend must respect their caps; every ops write must leave an `ops_action` row; no
email address or temporary password reaches a log or the browser except on the ops host to an
ops-role holder.
