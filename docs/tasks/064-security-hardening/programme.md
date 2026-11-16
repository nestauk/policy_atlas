# Programme: 064 security hardening

> **Status:** drafted 2026-11-16. Source: the project review of 2026-10-19 (`dev` at
> `a31489d5`; 13 review lanes, 0 critical, 17 high, 30 medium, 30 low). The owner picked the
> priorities on 2026-11-16 and asked for one pull request per slice. Each slice has its own
> task folder (`064a-…`, `064b-…`) with a contract, rubric and plan. This file is the map.

## Why a programme

The review found no critical defect. The main risks are availability and cost control (one
server, no firewall, no quotas), data protection paperwork, and sign-in hardening. The owner
wants the quick wins first, then the changes that touch infrastructure, email or the identity
provider, because those need staging time and user communication.

## Findings and where they land

Finding ids are the review's (`H-nn`, `M-nn`). The review file is not in the repository; the
ids are kept so a later reader can match the two.

| Slice | Finding | Short name | Why here |
|---|---|---|---|
| **064a quick wins** | H-06 | Error logs show local variables | one processor swap |
| | M-30 | Waitlist 409 reveals who signed up | one return value |
| | M-11 | Raw library error text reaches the browser | one helper |
| | H-16 | Load balancer health check needs a database connection | one path string |
| | M-04 | Site also served over plain HTTP | one CDK setting per behaviour |
| | M-13 (part) | Minimum password length 8 | one number |
| | H-17 | One user can take every run slot | filter on the existing admission query |
| | H-04 (part) | No limit on tasks per user | one count at task creation |
| | H-14 | Screening query reads every task's rows | filter plus one index |
| | M-02 | Removing a user does not stop their sign-in | one ops command |
| | M-21 | Web server keep-alive and proxy headers cause 502s | one Dockerfile line |
| | M-17 | Cognito pool has no deletion protection | one setting |
| | L-01 | Default TLS policies | two settings |
| | H-11 | A run that fails between steps stays "running" | one call that already exists elsewhere |
| | L-22 | `confirm_expired` gives 500 instead of 409 | one string in two lists |
| | H-01, M-20 | Random key ids freeze sign-in; a failed key download signs everyone out | ten lines in the key provider |
| | M-16 | 7-day backups | one number per environment (production 35) |
| **064b WAF** | H-03, M-30 (CAPTCHA) | No firewall or rate limit; waitlist can be spammed | new web ACL on the load balancer, frontend token on the waitlist form |
| **064c CSP** | M-03 | No Content Security Policy | custom CloudFront response headers policy, built from config |
| **064d sign-in** | M-13 (rest) | No MFA, no threat protection | after SES exists (ops-portal step 1), so email MFA works |
| **later, own tasks** | H-07, H-08, M-14 | Privacy notice, erasure, data export | Data Protection Officer work after the ops portal |
| | M-25, M-27, M-19, M-26, M-29 | SSE polling, missing indexes, transactions held open during model calls, pages that load the whole task, chat stream thread pool | performance slices |
| | M-28 | Cannot scale past one server | after the performance slices; needs locks in the database |
| | H-04 (rest) | Spend caps, chat and planner turn limits, steering lock, per-user POST rate limit | needs a usage table; revisit after the task quota has run for a month |

**Already fixed before this programme** (checked 2026-11-16): H-10 (the test setup refuses
any database not named `*_test`, task 056), H-15 (retrieval in SQL, task 057), M-24 and
M-06 (parsing runs in a Lambda with its own memory cap in queued mode, task 057; the
laptop path keeps the old shape).

Findings the owner did not pick stay in the review (`original_review.md` in this folder):
H-05, H-12, H-13, M-01, M-05, M-07 to M-10, M-15, M-18, M-22, M-23 and the remaining lows.
They are not deferred items of this programme. L-20, the local dev key on an old branch,
is a branch deletion the owner can do at any time.

## Rules that apply to every slice

- **Every new control with an environment-specific value is a per-environment key in
  `infra/pa_config.json`** (or `db_config.json`), the way `theory_of_change` is. The deploy
  script fails when a key is missing, and the synth tests pin the production values. A
  setting with one right value everywhere (a health path, a TLS policy, a password length)
  is hard-coded, and the slice's contract says so.
- **Staging leads by one release.** Changes that can lock people out (HTTPS redirect,
  password policy, MFA, CSP enforcement, WAF block mode, CAPTCHA) go to staging first with a
  real sign-in test. Purely additive changes (logging, count-mode rules, quotas) can ride the
  normal `dev` → staging → `main` → production path with no special handling.
- **Staging and production share the same numbers** (quota 50 tasks per year, 3 concurrent
  runs per user) unless a slice says otherwise.
- **Admins have no task quota.** The concurrent-run cap applies to everyone, because it
  protects the server, not the budget.
- **Tier.** Every slice touches auth, production config or schema, so none is below Tier 3.
  064a and 064b are Tier 4 (migration, production config).

## Facts settled on 2026-11-16

- Bedrock is the live model route in both environments (`model_route: bedrock`). The privacy
  notice's Bedrock sentence is now true; its "anonymised" claim is still false.
- H-15 (embeddings loaded into memory) is already fixed by task 057 (pgvector `<=>` in SQL).
- A run waiting at a check-in has status `paused`, so it does not count as running.
- Options scoping and theory of change each create one task row. "Tasks" in the quota
  means task rows of any capability.
- Email MFA needs the Cognito Essentials tier and the pool's own SES sender. It does not work
  with the default Cognito mailer. TOTP works on every tier today.
- AWS WAF CAPTCHA on a `fetch()` POST needs the WAF JavaScript SDK on the form; a request
  with no token gets HTTP 405 from the firewall. Rate rules need no frontend change.
- The ops portal will be a separate IP-gated service. Cognito write permissions go on that
  service's task role, never on the public API. 064a's offboard command runs from the
  operator's own credentials, and the portal reuses the same function later.

Sourced research notes live in `docs/tasks/064-security-hardening/research/` (gitignored).

## The ops portal is a separate task (065), not a slice of 064

The owner's notes of 2026-11-16 ask for three things: (1) non-technical team members can
create accounts and organisations and move people between organisations; (2) people who
meet a rule, such as an email address at a known domain, can get an account without an
operator; (3) the emails the system sends come from Amazon SES (Simple Email Service) and
look like Nesta's. This section records how that work is shaped and how it touches the
security programme, so the next conversation can write the 065 contracts from it. Nothing
here is built yet.

### How accounts work today

- Sign-in is one Amazon Cognito user pool per environment, with the classic hosted sign-in
  page. The API only ever reads the token's subject. The pool is bare on purpose: no self
  sign-up, no groups, no Lambda triggers, and the **default Cognito email sender**, which is
  capped at 50 messages a day and often lands in spam. That is why operators hand over
  temporary passwords by hand today.
- An account is two things: a Cognito user, and an `app_user` row holding display name,
  email, organisation and the admin flag. The row appears on the first `/me` call. Only the
  ops CLI (`backend/src/policy_atlas/ops/`) ever sets the organisation, the email or the
  admin flag: `user create`, `user enrol`, `user resync`, `user reissue`, `user de-enrol`,
  `rows assign`, `admin grant`, `admin revoke`, and after 064a `user offboard`. The CLI
  needs the operator's own AWS credentials and passes an environment check. Its logic is
  plain functions in `ops/commands.py`, so another caller can reuse them.
- The splash-page waitlist writes a row and nothing else. Nobody is notified, operators read
  the table by hand, and no account follows from it.
- ADR 0033 made the admin flag read-only and declared any admin surface or user directory
  out of scope. An ops portal reopens that decision and needs its own ADR.

### The shape, in three slices

**065a SES wiring.** Everything else depends on invitations arriving. Cognito cannot send
through another account's SES, so Nesta's shared SES account cannot carry this mail; each
project account owns an SES identity for its own domain. The slice: verify
`v3.policyatlas.uk` (staging) and `policyatlas.uk` (production) in SES with Easy DKIM through
the Route 53 zones the certificate stack already uses; point each pool's email
configuration at a sender such as `no-reply@` that domain, with the address in
`pa_config.json` per environment; put branded HTML templates for invitation, code and
password-reset messages in CDK (Cognito templates take HTML up to 20,000 characters, no
Lambda needed). The long pole is the **SES production-access request**, one per account,
with a first AWS answer within 96 hours. **Both accounts request it**: the owner ruled on
2026-11-16 that staging has real testers, so the SES sandbox (verified recipients only) is
not enough there. Start both requests before anything else in 065.

**065b the ops service.** A separate instance reachable only from allowlisted addresses,
the way Metabase is run today, rather than an ops page inside the public app. The Metabase
pattern transfers as is: a hostname on the shared load balancer (`ops.policyatlas.uk`,
`ops.v3.policyatlas.uk`), listener rules on host header plus source address, fed from an
SSM parameter of up to 8 address ranges (`infra/metabase_allowlist.py`). The service is the
**same backend image** as the API, started with a flag that mounts the ops routes, which
the public API never mounts; one codebase, nothing to keep in step. It gets the smallest
task size, because it does nothing heavy. Its page lists organisations and the waitlist
with a "create account in organisation X" button, and offers enrol, move, de-enrol,
offboard and reassign, each calling the existing command functions. What it needs beyond
the routes: an `ops` role on `app_user`, separate from the admin flag, so ADR 0033's "admin
never writes" rule stays true, with the grant CLI-only so no HTTP route can escalate; the
**Cognito admin permissions on the ops service's task role only**, so the public API keeps
no AWS write permission and a bug in a public route can never create or disable an account;
an audit line per action in the same shape as the CLI's trace; the type-stub imports in the
ops package moved under a type-checking guard, because the container image drops that
dependency group. Login and the ops role still apply inside the allowlist: the address
gate is a network boundary, not an identity. Costs to accept: one more ECS task, and ops
work only from allowlisted addresses, so the non-technical team members must be on the
office network or VPN when they use it. Rejected: the Cognito console (it cannot write
`app_user`), Metabase (read-only), a Retool-style tool (a second system with its own login),
and a path-pattern rule in front of ops routes on the public service (the public task role
would still hold the Cognito permission, which undoes the main benefit).

**065c self-service by email domain.** The lazy version needs no Cognito change. The
"Request access" form stays as it is. The backend checks the address's domain against an
organisation-to-domain table that the ops page manages. A match calls the same create-user
function with that organisation, and Cognito sends the branded invitation with a temporary
password valid for 30 days; reading it proves ownership of the mailbox, which is the
"token link with expiry" the owner described. No match writes a waitlist row as now, and
an operator approves it from the ops page. The response to the form is the same in both
cases, so nothing about which domains are known is revealed. Auto-enrolment is safe
because every new row defaults to private. Two alternatives not taken now: Cognito native
self sign-up with a Lambda that rejects domains (moves access policy into the identity
provider, which ADR 0033 avoided), and passwordless sign-in (needs the Essentials tier,
three custom-auth Lambdas and a custom sign-in page; no native magic link exists).

### Open questions for the 065 contracts

- Which `gov.uk` and other domains map to which organisation, and whether a domain maps to
  one shared organisation or several. Colleagues in one organisation see each other's
  org-visible work, so this is a tenancy decision, not a config detail.
- Whether the Tech Team accepts the project accounts owning SES identities. Nesta's
  guidance points to the shared SES account; Cognito forces this one.
- The 8-address-range cap on the allowlist, and whether every ops user is covered by the
  office network or VPN.

### How 065 and 064 depend on each other

One-way, and only through 065a:

- **064a, 064b, 064c need nothing from 065.** They run now.
- **064d waits for 065a**, because email MFA needs the pool's own SES sender; TOTP is the
  fallback if SES slips.
- **The H-07 privacy notice waits for all of 065**, because it must describe self-service
  sign-up, the ops role and the ops service.
- **065b reuses 064a's work**: `user offboard`, and the pattern of Cognito permissions
  living on an operator's credentials rather than on the public API.
- 065a can start in parallel with 064a; the SES access requests should go in first.

## Later slices in brief

### 064b WAF and CAPTCHA

- `aws_wafv2.CfnWebACL` in the network stack, regional scope in eu-west-2, associated to
  the load balancer with `CfnWebACLAssociation`. CDK has only L1 constructs for WAF.
- Rules: rate rule per IP on `POST /api/v1/waitlist` (10 per 5 minutes), a loose general
  rate rule, the three AWS managed groups (common, known bad inputs, IP reputation) in
  **count mode first**, a CAPTCHA rule on the waitlist path.
- The common group blocks bodies over 8 KB and can match pasted HTML. Chat and plan bodies
  can exceed 8 KB. Count for a week on staging, exclude the body-size rule, then block.
  Production runs its own count week.
- Frontend: load the WAF CAPTCHA script, get a token, send it in `x-aws-waf-token`. CORS
  must allow that header. The API hostname goes on the web ACL token domain list. The
  waitlist API must never itself return 405, or the form will mistake it for a CAPTCHA.
- Per-env config: `waf.enabled`, `waf.managed_mode` (count or block), `waf.captcha`.
  Per-env `VITE_WAF_*` values injected by the deploy script.
- Cost: about $11 a month (web ACL $5, six rules at $1) plus $0.60 per million requests and
  $0.40 per 1,000 puzzles.

### 064c Content Security Policy

- A custom `ResponseHeadersPolicy` replacing the managed `SECURITY_HEADERS`, keeping its
  headers and adding CSP, `Permissions-Policy` and `includeSubDomains` on HSTS.
- Sources: `default-src 'self'`; `connect-src 'self' <api origin> <cognito domain>
  https://*.awswaf.com`; `script-src 'self' https://*.awswaf.com`; `img-src 'self' data:
  blob:` (the theory-of-change upload preview uses blob URLs); `frame-ancestors 'none'`;
  `object-src 'none'`; `base-uri 'self'`. The ops hostname is added when the ops page lands.
- Built in CDK from `pa_config.json` values, never hand-written. A per-env flag chooses
  `Content-Security-Policy-Report-Only` or enforce. Order: staging report-only, staging
  enforce, production enforce. There is no report collector, so report-only means one
  person opens the browser console on staging and uses every page once.
- Written after 064b so the WAF script source is listed once.

### 064d MFA and threat protection

- Depends on the SES slice of the ops-portal work (branded email from the pool's own SES
  identity, one per account, production access requested for both accounts).
- Email MFA for all users (every user has a verified address, no app to install). TOTP is
  the fallback if SES slips. CDK trap: when MFA is turned on, the default second factor is
  SMS, which can never be removed from a pool afterwards. The setting must name the factor.
- Threat protection needs the Plus tier (about $2 a month at this user count): leaked
  password block, risk-based sign-in checks.
- Staging first with one real sign-in; warn production users before their next sign-in asks
  for a code.
