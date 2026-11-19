# Task contract: 064d-mfa

Fourth slice of the [064 security hardening programme](../064-security-hardening/programme.md).
Boundaries are in [AGENTS.md](../../../AGENTS.md); specs in [docs/specs/](../../specs/index.md).

> **Status:** revision 3 (2026-11-19), rewritten from P0's results. Owner rulings, all
> 2026-11-19: Cognito managed login with our branding, not a custom sign-in page; an
> authenticator-app code (TOTP) every time a person types their password, **not an email
> code**, because P0 proved that no reset setting keeps self-service password reset with email
> codes (U2); password reset stays as today; a lost authenticator app is reset by a new ops
> command `user reset-app`, with the boto3 upgrade it needs approved; no forced sign-out at
> switch-on (the code phases in as sessions renew); **our own sign-in address**
> (`auth.<domain_name>`), which also names the entry in the authenticator app; both pools stay
> on the Essentials plan, threat protection moves to a later task; staging first; the build
> runs in the same conversation. Revision 1 approved 2026-11-19 · owner. Revision 2 (Codex
> contract-stage review F1 to F8 folded) approved 2026-11-19 · owner. Plan-stage review
> (Codex, 7 findings) folded into plan draft 2. P0 and P0b ran 2026-11-19 (§ P0 results).
> Revision 3 approved: _pending_ · Plan approved: _pending (draft 3)_ · ADR: 0049 (to write in
> the build).

## Goal

Today a password alone opens any account, including an admin account that can read every
organisation's rows (an accepted risk in
[ADR 0033](../../adr/0033-organisation-tenancy-and-global-admin-read.md)). This slice adds a
second step: after the password, the person types a six-digit code from an authenticator app
on their phone. The sign-in page changes from the plain AWS page to one with the Policy Atlas
logo and colours, on our own address.

Staging gets all of it in this slice. Production keeps its current sign-in until a later
config change, after the staging live checks pass (M6).

## Deliverable

One pull request on `task/064d-mfa` into `dev` that lands M1, M3, M4, M6 and M7 below: a
`sign_in` block per environment in `infra/pa_config.json`, the Cognito settings that read it,
the branding settings and logo, our own sign-in address with its certificate and DNS record,
the Content Security Policy update for that address, the `user reset-app` ops command with
its permission and the boto3 upgrade, synth and command tests, the deployment notes
(switch-on, user warning, rollback) and ADR 0049. Staging has the block. Production has none,
and its user pool template is unchanged.

## Terms

| Term | Meaning |
|---|---|
| **M1, M3, M4, M6, M7** | The problems of this slice, numbered in § The problems. M2 (threat protection) and M5 (a branded code email) were dropped; their numbers are not reused. The rubric and the plan use these numbers. |
| **P0, P0b** | Tests on throwaway user pools in the staging account before any product change. **U1 to U7** are the questions they answered (§ P0 results). |
| **Review id** (`M-13`) | The id in the 2026-10-19 project review (`original_review.md` in the programme folder). |
| **MFA** | Multi-factor authentication: a second proof after the password. |
| **TOTP**, **authenticator app** | Time-based one-time password: a six-digit code that an app on the phone (Google Authenticator, Microsoft Authenticator, 1Password and so on) makes every 30 seconds. The person links the app once by scanning a QR code at their first sign-in after the switch. Cognito calls it `SOFTWARE_TOKEN_MFA`. |
| **Email MFA** | Cognito's emailed code. Rejected in P0: with it, no reset setting keeps self-service password reset for people with no phone number. |
| **Feature plan** | Cognito's pricing tier for a user pool. Both pools are on Essentials (U1), which allows managed login. This slice does not change it. |
| **Account recovery** | How a person who forgot their password gets a reset code. `EMAIL_ONLY` today, and it stays. |
| **Hosted sign-in page** | The page where people type their password. The app redirects there and back (authorization code flow with `react-oidc-context`). Today it is on `https://<cognito_domain_prefix>.auth.eu-west-2.amazoncognito.com`. |
| **Our own sign-in address** | A Cognito *custom domain*: `auth.<domain_name>`, for example `auth.v3.policyatlas.uk` on staging. It needs a certificate in us-east-1 and a DNS record. The prefix address keeps working beside it. Cognito's discovery document then names our address for every sign-in endpoint (P0b), and the authenticator app names the entry after it. |
| **Session cookie** | After a person types their password and code on the hosted page, Cognito keeps a cookie for one hour. A new sign-in request in that hour (for example a new tab) gets tokens with no password and no code. |
| **Classic hosted UI** / **managed login** | Two versions of the hosted page. Classic (version 1) is what both pools use. Managed login (version 2) has branding. CloudFormation property `ManagedLoginVersion` on each domain. **Leaving the property out does not change a domain back**: a rollback must name version 1 (P0). |
| **Branding style** | A `CfnManagedLoginBranding` resource for the SPA client: a settings document and image assets. It cannot change the page's wording. |
| **`user reset-app`** | The new ops command: removes a person's authenticator link (`AdminDeleteSoftwareToken`) and signs them out everywhere (`AdminUserGlobalSignOut`), so their next sign-in shows the QR setup again. For a lost or replaced phone. |
| **`user reissue`** | The existing ops command for an account that has never signed in. Unchanged. |
| **All-off** | An environment with no `sign_in` block. Production is all-off in this slice. |
| **CDK, synth** | AWS Cloud Development Kit, the Python library our infrastructure is written in. *Synth* turns it into a CloudFormation template; `make -C infra test` asserts on it. |

## Read first

- `infra/infra/cognito_auth.py`, its call site in `infra/infra/policy_atlas_stack.py` (around
  line 175), and the ops task role's Cognito permissions (around line 410).
- `infra/infra/cert_stack.py` and `infra/app.py` (the us-east-1 certificate stack and its
  cross-region reference).
- `infra/infra/components/security_headers.py` and its call site (the 064c CSP, which builds
  the Cognito hosted domain from `cognito_domain_prefix`).
- `infra/pa_config.json`, `infra/network_config.json`.
- `backend/src/policy_atlas/ops/commands.py` (`deactivate_user`, `reissue_temporary_password`,
  `_find_user_by_email`, the `ops_action` record) and `ops/cli.py`.
- `frontend/src/auth/OidcAuthProvider.tsx`.
- `infra/DEPLOYMENT.md` § "Pool email through SES" and § 4 "Security headers".
- This task's gitignored `research/` notes: `cognito-facts.md`, `sign-in-ui-options.md`,
  `p0-results.md`.

## What sign-in looks like today

| Part | Today | After this slice (staging) | Do not change |
|---|---|---|---|
| Second factor | none | authenticator-app code each time the password is typed | — |
| Password reset | email, self-service | unchanged | all of it |
| Feature plan | Essentials (U1) | Essentials | both |
| Sign-in page | classic, AWS look | managed login, our logo and colours, light and dark | the app's redirect flow |
| Sign-in address | `<prefix>.auth.eu-west-2.amazoncognito.com` | `auth.<domain_name>`; the prefix address stays | — |
| App client | code flow, 60-minute access token, 30-day refresh token, no user-existence errors | unchanged | all of it |
| Invitation and verification emails | branded, SES | unchanged | all of it |
| CSP (064c) | lists the prefix address in `connect-src` and `frame-src` | also lists our sign-in address | every other source |
| Frontend code | `OidcAuthProvider` | unchanged (discovery names the new address, P0b) | — |
| Ops commands | invite, reissue, deactivate and so on | plus `user reset-app` | the others |

## The problems

| Id | Problem | Required after the slice |
|---|---|---|
| **M1** | A password alone signs in (review M-13, MFA part). | With `sign_in.mfa` = `"app"`, the pool has `MfaConfiguration` ON and `EnabledMfas` exactly `["SOFTWARE_TOKEN_MFA"]`. Each sign-in where the password is typed asks for the app code; a person with no app linked gets the QR setup first. The one-hour session cookie skips both (accepted). SMS and email codes are never enabled; no SMS role is created. Account recovery stays `EMAIL_ONLY`. Existing sessions are not ended: a refresh token from before the switch keeps working (P0, U6), so each person meets the code at their next full sign-in, at most 30 days later (owner ruling). |
| **M3** | A person who loses or replaces their phone can no longer sign in, and changing their MFA preference does not help (P0). | `user reset-app --email E` (or `--sub`) finds the account, calls `AdminDeleteSoftwareToken` and `AdminUserGlobalSignOut`, and writes one `ops_action` row. It refuses an unknown address and a deactivated account with a clear message and changes nothing. The ops task role gets `cognito-idp:AdminDeleteSoftwareToken` on the pool and nothing else new. boto3 and boto3-stubs move to ≥ 1.44.6 (the first versions P0 found with the call). |
| **M4** | The sign-in page is the plain AWS page on an AWS address. | With `sign_in.page` = `"managed"`, every domain of the pool uses managed login (version 2) and one branding style exists for the SPA client, built from committed files in `infra/branding/`: the settings document (brand colours from `DESIGN.md`, header on, light and dark following the browser) and the assets (the wordmark outlined from Zosia Display, light and dark, ratio within 1:1 to 4:1; the diamond favicon). With `sign_in.page` = `"classic"`, every domain names version 1 and no branding exists (the rollback). With `sign_in.domain` set, a second, custom domain on that name, a us-east-1 certificate for it, and a DNS alias record; the CSP lists it in `connect-src` and `frame-src`. |
| **M6** | A switch-on with no plan can lock people out or surprise them. | The `sign_in` block is validated: unknown key or value fails synth; `domain` must be `auth.<domain_name>`. **No block adds nothing**: no new property or resource on the pool, client or domains, no certificate, record or CSP change, so the production template is byte-for-byte the same as today's, proven by a committed test against a committed baseline. The runbook covers: the user warning (what an authenticator app is, the QR step, that the code is asked at each password sign-in, that existing sessions continue); the first deploy's timing (certificate and custom domain, about 8 minutes); code problems and a lost phone (`user reset-app`); rollback in the order P0 tested, with abort criteria and an operator sign-in check after each step; the production prerequisites. |
| **M7** | The authenticator entry is named after the AWS address (`<prefix>.auth.eu-west-2.amazoncognito.com`), which people do not recognise. | With `sign_in.domain` set, sign-in runs on our address, and the entry carries it (P0b). |

## P0 results

Run 2026-11-19 on throwaway pools `Pa064dP0` and `Pa064dP0b` in the staging account, both
destroyed. Detail in `research/p0-results.md` (gitignored).

| Id | Question | Answer |
|---|---|---|
| **U1** | Live pools' plan, MFA, SMS, recovery, page version | Both Essentials, MFA off, no SMS configuration, `EMAIL_ONLY`, classic. Staging email through SES, production `COGNITO_DEFAULT`. 26 and 100 users. |
| **U2** | A recovery setting that keeps self-service reset with **email** MFA | **None.** `EMAIL_ONLY` is refused at deploy; "email, then SMS" deploys but reset fails for a person with no phone; no-recovery is admin-only. → app codes. With app codes, `EMAIL_ONLY` and self-service reset work unchanged. |
| **U3** | Invited user's first sign-in | Temporary password → new password → QR setup → app code. Works. |
| **U4** | Branding through the CDK resource | Works. No font setting; wording fixed; logo ratio 1:1 to 4:1; the AWS default has the header off and light mode only, so both are switched on in the settings. Domain and branding update in the same deploy without an ordering problem. |
| **U6** | Sessions, sign-out, refresh | Sign-in, sign-out and the one-hour new tab work. A refresh token issued before the switch still refreshes after it. |
| **U7** | Lost phone; rollback; our own address | `AdminSetUserMFAPreference` does nothing; `AdminDeleteSoftwareToken` plus global sign-out brings back the QR setup. Rollback: classic page with app codes on works; MFA off in one deploy works; **removing `ManagedLoginVersion` leaves version 2 in place with no branding**, so rollback names version 1. Our own address: the discovery document names it for every endpoint, the app needs no change, and the authenticator entry takes its name. A pool holds a prefix and a custom domain at once. |

## Scope / Out of scope

- **In:** `infra/infra/cognito_auth.py`, `cert_stack.py`, `app.py`, `policy_atlas_stack.py`
  (call site, ops role permission, CSP input), `components/security_headers.py`,
  `infra/pa_config.json`, `infra/branding/` (new), `infra/tests/unit/`; `backend` ops command,
  CLI, tests, `pyproject.toml` and `uv.lock` (boto3); `infra/DEPLOYMENT.md`, ADR 0049,
  `docs/deferred.md`, the programme map, the knowledge bundle where it records sign-in facts.
- **Out:**
  - Threat protection and the Plus plan (later task).
  - A custom sign-in page in our app (only way to change the wording, for example "Sign in
    to your Policy Atlas account."; deferred).
  - A `reset-app` button on the ops pages (the CLI is the operator surface for this slice).
  - Forced sign-out at switch-on.
  - Production switch-on.
  - Remembered devices, passkeys, email codes, SMS.
  - Token storage and the 30-day refresh token.
  - Frontend code.

## Deferred work this slice takes in

From [docs/deferred.md](../../deferred.md):

- § Accounts, organisations and administration, **Planned** "the Cognito pool has no MFA":
  taken in; closes for staging; rewritten to name the production switch.
- § Infrastructure and deployment, "Sign-in tokens stay in `sessionStorage` with a 30-day
  refresh token": read and left. A code at each password sign-in makes a shorter refresh token
  more costly for users.

New entries: production switch-on; threat protection (rest of review M-13); a custom sign-in
page (wording); `reset-app` on the ops pages; retiring the prefix address once nothing uses it.

## Constraints & approval gates

- **Auth (hard gate):** the whole slice. Owner rulings 2026-11-19 (§ Status).
- **Dependency (hard gate):** boto3 and boto3-stubs ≥ 1.44.6, approved 2026-11-19.
- **Production config (hard gate):** production has no `sign_in` block; its template must not
  change (M6).
- **Public interface:** a new ops CLI command (operator-facing, not the public API).
- **New AWS resources on staging:** one certificate in us-east-1, one custom domain (a
  CloudFront distribution AWS runs for Cognito), one DNS record. No cost beyond today's plan.
- No schema change. No frontend change. No live AWS call in `make verify`.

## Public / private boundary

Public-safe: the CDK code, config, branding settings and logo (outlined letter shapes, not the
font file; owner approved 2026-11-19), the ops command, the runbook. Private: P0 notes with
pool ids, test users' passwords, codes and tokens, sign-in event logs.

## Model route

n/a. No inference.

## Disciplines binding this slice

- **Model only what behaves:** three keys (`mfa`, `page`, `domain`), each changes the pool.
- **Flag, don't drop:** the email-MFA dead end, the rollback trap and the 30-day phase-in are
  written into the runbook and ADR, not left in the notes.
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md).

## Stop conditions

Halt and escalate when:

- The production template would change with no `sign_in` block.
- The first staging deploy fails in a way the runbook's rollback does not cover.
- Any change would need SMS, a phone number, email codes or a plan change.
- The frontend turns out to need a change after all.

## Acceptance checks

- `make verify` and `make -C infra test` green; the ops command's tests pass.
- Synth and command tests (rubric item 6).
- `cdk diff` (dry run) against both accounts: production shows no change to Cognito, the
  certificate stack or the CSP; staging shows only the expected changes.
- **Staging live checks** after the owner deploys (the changed surfaces plus one cheap
  full-chain smoke):
  1. The address bar shows `auth.v3.policyatlas.uk`; the page is branded in light and dark.
  2. An existing user with an open session keeps working; after sign-out, sign-in asks for the
     password, then the QR setup, then the code; the authenticator entry shows our address.
  3. A newly invited user: temporary password, new password, QR setup, code.
  4. Forgot password works by email as today.
  5. `user reset-app` on a test user: their next sign-in shows the QR setup.
  6. The ops pages sign in the same way.
  7. A new tab within the hour signs in silently; sign-out then sign-in asks password and code.
  8. Full-chain smoke: start one task run and see its progress stream.
- The owner approves the look on staging.

## Verification evidence expected

In [verification.md](verification.md): the P0 summary; `make verify` output; the all-off
baseline test; the dry-run summaries; each staging live check with date and result;
screenshots of the page in light and dark mode; the warning text sent to staging testers;
known gaps.

## Risk tier & review focus

**Tier 4**: auth, a dependency, a production config file and a rollback plan. Review focus:
the SMS and email-code traps, the production template staying unchanged, the rollback naming
version 1, the custom domain's certificate and DNS, the CSP update, and `user reset-app`
acting on the right person and refusing the wrong ones.
