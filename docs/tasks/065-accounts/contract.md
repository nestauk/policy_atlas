# Task contract: 065-accounts

One contract for the whole accounts programme, in three deployable steps (A, B, C). The
shape was agreed with the owner on 2026-11-16 and is recorded in the
[064 programme map](../064-security-hardening/programme.md) § "The ops portal is a separate
task (065)". That file is on the `task/064a-security-quick-wins` branch and reaches `dev` with
the 064a merge; this contract repeats what it needs, so it reads cold without it.
Boundaries are in [AGENTS.md](../../../AGENTS.md); specs in [docs/specs/](../../specs/index.md).

> **Status:** approved, revision 1. Contract approved (before planning): 2026-11-16 · owner,
> after discussing the six decisions in § The work (sweep in the ops service; page in the app;
> resend instead of reissue; domain table by CLI; templates before the sender flips; no lifespan
> jobs in ops mode) · Contract-stage adversarial review: _running_ ·
> Plan approved (before implementation): _pending_ · ADR: 0046 (to be written at step 4;
> 0045 belongs to 064a).

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
| **Ops service** | A second ECS Fargate service running the **same backend image** as the API, started in ops mode (§ B2). It mounts the ops routes and nothing that runs work. Hostname `ops.<domain>`. |
| **Allowlist** | The SSM Parameter Store `StringList` of up to 8 address ranges (CIDRs) that may reach a hostname, enforced by load-balancer listener rules on host header plus source address. Metabase uses `/policy_atlas_v3/metabase/allowed_cidrs`; the ops service gets its own parameter, same validator (`infra/metabase_allowlist.py`). |
| **Task role** | The IAM role an ECS task runs with. The public API's task role has no Cognito permission today and keeps none. The ops service's task role is the only one with Cognito write permissions. |
| **Command functions** | The plain functions in `backend/src/policy_atlas/ops/commands.py` (`create_organisation`, `create_user`, `enrol_user`, `de_enrol_user`, `assign_rows`, `set_admin`, and 064a's offboard) that both the CLI and the ops routes call. Their semantics do not change here. |
| **Waitlist row** | `waitlist_entry` (task 036): what the public "Request access" form writes. Today nothing reads it but a human with database access. |
| **Domain table** | New: `organisation_domain` (`domain` → `org_id`). A request whose address ends in a listed domain is turned into an account in that organisation. One row for now: `nesta.org.uk` → Nesta. |
| **Sweep** | A loop in the ops service that, every minute, turns waitlist rows with a listed domain into accounts. It exists so that the public API never needs a Cognito permission. |
| **Startup sweep, drainer, executor** | The API's lifespan jobs (`api/app.py` `_lifespan`): the orphan sweep, the continuation drainer and the run executor. Exactly one process may run them (web-api.md § Deployment posture). The ops service runs none of them. |
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

## The work

### Step A — SES wiring and branded email

| Id | Change | Detail |
|---|---|---|
| **A1** | Pool sends through SES | `cognito_auth.py` sets the pool email configuration from three new keys per environment in `pa_config.json`: `email.enabled` (bool), `email.sender_domain` (the SES identity, e.g. `v3.policyatlas.uk`), `email.from_address` (e.g. `no-reply@v3.policyatlas.uk`) and `email.from_name` (`Policy Atlas`). With `enabled` false the pool keeps `COGNITO_DEFAULT`, which is how staging deploys before its production access lands. The identity is referenced by ARN from the domain name; **nothing in CDK creates an SES identity or DNS record**, because both identities already exist and a create would fail on the duplicate. |
| **A2** | Branded templates | Invitation and verification subjects and HTML bodies live in `infra/email/` as files read at synth and set on the pool. The copy is owner-reviewed product voice: who we are, what to do next, the code or temporary password via `{####}`, the sign-in address, and a line saying to ignore the message if unexpected. The logo is served from the SPA bucket at `/brand/email-logo.png`, since email cannot embed assets. The same templates apply with `email.enabled` false (Cognito renders HTML from the default sender too), so staging sees the copy before the sender flips. |
| **A3** | Synth pins | `test_synth.py`: with `email.enabled` true the pool carries `EmailSendingAccount: DEVELOPER`, the identity ARN in the pool's own account and region, and the From address; with it false the pool has no email configuration; both templates contain `{####}`, the invitation contains `{username}`; the pool still has no Lambda triggers. |
| **A4** | Deployment notes | `infra/DEPLOYMENT.md`: how to check production access (`aws sesv2 get-account`), the order (identity verified → production access → `email.enabled` true), the sending quota now being SES's, and `--invite manual` demoted from workaround to fallback. |
| **A5** | Deferred ledger | `docs/deferred.md`: the SES entry is discharged with the date; the `--invite manual` path stays as a recorded fallback. |

### Step B — the ops service

| Id | Change | Detail |
|---|---|---|
| **B1** | Ops role | Migration adds `app_user.is_ops boolean not null default false`. CLI gains `ops grant` / `ops revoke` (`--email` or `--sub`) mirroring `admin grant` / `admin revoke`, including the post-commit admin trace. **No HTTP route writes `is_ops` or `is_admin`**; the ops routes' own dependency and the `/me` projection are the only readers, asserted the way 033 asserts the `is_admin` readers. `user offboard` clears `is_ops` as it clears `is_admin`. |
| **B2** | Ops mode | A new setting `POLICY_ATLAS_SERVICE_ROLE=api\|ops` (default `api`). In `ops` mode `create_app` mounts `/healthz`, `/readyz`, `/api/v1/me` and the `/api/v1/ops/*` routes **only**, and the lifespan starts **no** run executor, startup sweep, continuation drainer or ingest consumer. In `api` mode the ops routes are not mounted at all. Both facts are tests. This keeps the one-process invariant of web-api.md § Deployment posture. |
| **B3** | Infra | In `policy_atlas_stack.py`, following the Metabase shape: a Fargate service from the same image with the smallest task size, its own target group, listener rules on host header `ops.<domain>` plus source addresses from a new SSM parameter `/policy_atlas_v3/ops/allowed_cidrs` (validated and sized by `metabase_allowlist.py` given the parameter name; `scripts/deploy.sh` passes the count), and an A record. Config in `pa_config.json` under `ops`: `subdomain`, `cpu`, `memory_limit_mib`, `desired_count`, `allowed_cidrs_parameter_name`. Environment: the database secret and the OIDC values only; no model or search keys. **Its task role gets the Cognito actions the command functions need** (`AdminCreateUser`, `AdminGetUser`, `ListUsers`, `AdminDisableUser`, `AdminUserGlobalSignOut`) scoped to the pool ARN. The **public API task role gets none**, and a synth test asserts both. |
| **B4** | Ops routes | All under `/api/v1/ops`, bearer-authenticated, and refused with `403 forbidden` for a caller without the ops role (the caller is signed in, so the 404 rule for hidden rows does not apply). Each write calls the command function unchanged and emits one `ops.action` log line with the caller's subject, the action and the subject account or row. Routes: list and create organisations; list people (subject, display name, email, organisation, flags, created); create a person (`create_user`, invite by email; the `manual` mode is CLI-only); enrol or move (`enrol_user`), de-enrol, offboard; **resend invitation** (`AdminCreateUser` with `MessageAction=RESEND`, the web-safe replacement for the CLI's `reissue`, which prints a password and stays CLI-only); assign a task or project to an organisation; list waitlist rows; **approve** a waitlist row into an organisation (creates the account from the row's email and name, stamps the row, § C2). Reads carry emails: that is the ops-facing use `app_user.email` was stored for, and it is visible only to ops-role holders on the address-gated host. |
| **B5** | Image can import the commands | The `mypy_boto3_cognito_idp` imports in `ops/commands.py` and `ops/environment.py` move under `TYPE_CHECKING`, because the runtime image drops the `ops` dependency group while `boto3` itself is a main dependency. The CLI's environment check (`ops/environment.py`) stays CLI-only; the service takes the pool id from `OIDC_ISSUER`. |
| **B6** | Ops page | A `/ops` route in the SPA, listed in navigation only when `/me` says `is_ops`. It calls the ops host from a build-time `VITE_OPS_API_BASE_URL` (`https://ops.<domain>`), and the ops service's `APP_ORIGIN` is the SPA origin so the browser may call across hosts. Sections: organisations; people (with create, enrol or move, de-enrol, offboard, resend invitation); waitlist (approve into an organisation); reassign a row. Plain tables and forms in the existing design system; confirmation before offboard. No design annex: the page's value is function, not look; the `frontend-designer` agent still builds it. |
| **B7** | `/me` | `MeOut` gains `is_ops` (additive; `make openapi-sync`). The ops routes are in the OpenAPI document under an `ops` tag with a description saying they are served only on the ops host. |
| **B8** | Migration order | The migration is additive and is rebased after `dev`'s head, which will include 064a's index migration, before the PR (never edit `dev`'s migrations). |
| **B9** | Tests | Conformance: ops routes 401 without a token, 403 with a token and no ops role, 200 with the role; the `api`-mode app has no `/api/v1/ops` paths; the `ops`-mode app has no task, run or SSE paths. Unit: each route calls its command function and logs `ops.action`; the reader list for `is_ops` is closed. Synth: B3. |
| **B10** | ADR 0046 | Amends ADR 0033 decision 4 and the 033 Out list: an ops role separate from the admin flag; HTTP writes to `app_user` and `organisation` exist, on the ops service only; email is visible to ops-role holders there; "an admin surface" is no longer Out. Records the rejected shapes (in-app page; path rule on the public service; Cognito console; Retool-style tool) and why. |

### Step C — self-service for `nesta.org.uk`

| Id | Change | Detail |
|---|---|---|
| **C1** | Domain table | Migration adds `organisation_domain (domain text primary key, org_id uuid not null references organisation, created_at)`. CLI gains `org domain add --domain D --org ORG` and `org domain remove --domain D`. Domains are stored lower-cased. Deployment note: create the Nesta organisation and add `nesta.org.uk` in each environment. The ops page does not edit this table (deferred: adding a domain is a tenancy decision and rare). |
| **C2** | Waitlist row state | `waitlist_entry` gains `account_user_id text null` and `account_created_at timestamptz null`. The public `POST /api/v1/waitlist` route is **unchanged** in behaviour and response, so the form still reveals nothing (064a's M-30 rule). Only the ops service writes the two columns. |
| **C3** | Sweep | In ops mode the lifespan starts one loop: every 60 seconds, select waitlist rows with `account_created_at IS NULL` whose address domain (the part after `@`, lower-cased, exact match, no subdomains) is in the domain table; for each, call `create_user(email, display_name=row.name, org, invite="email")` and stamp the row. An address already in the pool is stamped with the existing subject and sends nothing. A failure is logged and the row is retried next tick; one failing row never blocks the others. The public API therefore never needs a Cognito permission. |
| **C4** | Abuse ceiling | At most one invitation per address ever (the waitlist email is unique and the stamp is permanent); the honeypot stays; volume protection is 064b's WAF rule. Stated in the ADR as the accepted ceiling. |
| **C5** | Ops page | Waitlist rows show "invited" with the time once stamped; the approve action is hidden for them. |
| **C6** | Tests | Unit: the domain match (exact, case-insensitive, no subdomain); the sweep stamps on success, skips already-stamped rows, retries after a failure, stamps without sending when the address exists. Conformance: the public waitlist response is byte-identical for a listed and an unlisted domain. |

## Scope / Out of scope

- **In:** A1 to C6 above; `pa_config.json`, `scripts/deploy.sh`, `infra/DEPLOYMENT.md`, `docs/deferred.md`, ADR 0046, `web-api.md` § Auth boundary and § Waitlist (additive paragraphs on the ops host and the sweep).
- **Out (⏸, recorded):** self-service for any domain but `nesta.org.uk` · Cognito self sign-up, Lambda triggers, passwordless sign-in and magic links · managed login or restyling the sign-in pages · MFA (064d, unblocked by A) · the privacy notice (H-07, after 065) · deleting a Cognito user and ownership transfer · multi-organisation membership and per-organisation roles · editing the domain table from the ops page · any email sent by the application itself (the only sender in this slice is Cognito) · a custom message Lambda · Metabase changes · the WAF rate rule (064b).

## Constraints & approval gates

Tier 4. Every gated class below needs the owner's approval at this contract, and the plan
names the rollback for each step.

- **Schema:** B1 (`is_ops`), C1 (`organisation_domain`), C2 (two waitlist columns). All additive with reversible downgrades.
- **Auth / tenancy:** the ops role and the ops routes (B1, B4); ADR 0046 amends ADR 0033.
- **Production config:** `pa_config.json` `email` and `ops` blocks; the pool email configuration; the new SSM parameter; IAM on the ops task role; a new ECS service, target group, listener rules and DNS record.
- **Public interface:** `MeOut.is_ops` (additive); the `/api/v1/ops/*` routes, served only on the ops host.
- **CI / deploy:** `scripts/deploy.sh` reads the ops allowlist size as it does Metabase's.
- **Dependencies:** none new. `boto3` is already a main dependency.
- **Frontend:** one new route and a build-time variable; no scaffold or package-manager change.
- **Egress:** none. Cognito and SES are AWS control-plane calls from the ops service, not product data leaving.
- **Rollback:** A: set `email.enabled` false and deploy (the pool returns to the default sender). B: `desired_count` 0 or remove the `ops` block; the migration downgrade drops `is_ops`. C: the sweep runs only in ops mode, so B's rollback stops it; the downgrade drops the table and columns.
- **Ordering:** A can deploy to production now and to staging once `aws sesv2 get-account` shows `ProductionAccessEnabled: true`; B needs A for invitations to arrive; C needs B (the sweep lives in the ops service) and the Nesta organisation and domain row.

## Public / private boundary

Committed: code, templates, config keys, the ADR. Never committed: the allowlist address
ranges (SSM only, as for Metabase), temporary passwords (never logged; the web surface never
shows one), email addresses in logs (the `ops.action` line carries subjects, not addresses),
the research notes (gitignored `research/`).

## Model route

n/a. No inference.

## Disciplines binding this slice

- **Don't flatten status.** ⏸ items above stay deferred, with their reopening condition in `docs/deferred.md`.
- **Model only what behaves.** `is_ops` exists because routes read it; the domain table exists because the sweep reads it. No other flag.
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
- **Live, on staging, scoped to the changed surfaces** (about 30 minutes): (1) with `email.enabled` true after production access: an ops-page "create person" sends an invitation from `no-reply@v3.policyatlas.uk` whose headers show DKIM pass, and the person signs in and sets a password; (2) "resend invitation" sends again; (3) a `nesta.org.uk` request on the splash form gets an invitation within two minutes and appears as "invited" on the ops page, and a non-listed address appears as a plain waitlist row with the same form response; (4) from a non-allowlisted address `https://ops.v3.policyatlas.uk` is refused by the load balancer; (5) a signed-in user without the ops role gets 403 on an ops route and sees no `/ops` navigation; (6) the public API task role shows no `cognito-idp` action in the deployed policy; (7) one full-chain smoke: a normal task run still completes, proving the ops service did not take over the executor.

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
run none of the API's lifespan jobs; `is_ops` and `is_admin` must have no HTTP writer; the
form response must stay identical for listed and unlisted domains; no email address or
temporary password reaches a log or the browser except on the ops host to an ops-role holder.
