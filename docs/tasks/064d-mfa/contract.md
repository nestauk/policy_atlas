# Task contract: 064d-mfa

Fourth slice of the [064 security hardening programme](../064-security-hardening/programme.md).
Boundaries are in [AGENTS.md](../../../AGENTS.md); specs in [docs/specs/](../../specs/index.md).

> **Status:** revision 2 (2026-11-19). Owner rulings (2026-11-19): Cognito managed login with
> our branding, not a custom sign-in page; the sign-in page stays on the Cognito address for
> now; an email code every time a person types their password; the password-reset setting is
> decided by a test on a throwaway pool (P0), and if no self-service reset works the slice
> stops for an owner decision; staging first; **both pools stay on the Essentials plan, threat
> protection moves to a later task**. Contract approved: revision 1 on 2026-11-19 · owner.
> Contract-stage adversarial review 2026-11-19 (Codex, 8 findings; raw record in the gitignored
> `research/`): F1 the one-hour sign-in cookie (M1 wording, U6, live check 6); F2 adaptive
> authentication against required MFA (gone with threat protection); F3 `user reissue` cannot
> reset an active account (M3 fallback replaced by a stop condition); F4 an exact
> production-template test (M6, rubric 5); F5 branding deployed through the CDK resource in P0
> (U4); F6 ordered rollback (M6); F7 code limits and lock-out (M6, live check 4); F8 rubric 6
> split per configuration. Revision 2 approved: 2026-11-19 · owner ("go ahead"), with the build
> to start in the same conversation (owner ruling). · Plan approved (before implementation):
> 2026-11-19 · owner (pre-approved with revision 2) · ADR: 0049 (to write at step 4).

## Goal

Today a password alone opens any account, including an admin account that can read every
organisation's rows (an accepted risk in
[ADR 0033](../../adr/0033-organisation-tenancy-and-global-admin-read.md)). This slice adds a
second step: after the password, Cognito emails a one-time code, and the person types it in.
The sign-in page itself changes from the plain AWS page to one that carries the Policy Atlas
logo and colours.

Staging gets all of it in this slice. Production keeps its current sign-in until a later
config change, after the staging live checks pass (M6).

## Deliverable

One pull request on `task/064d-mfa` into `dev` that lands M1 and M3 to M6 below: two new
per-environment keys under `sign_in` in `infra/pa_config.json`, the Cognito settings that read
them, the branding settings and logo, a branded code email, synth tests, the deployment notes
(switch-on, user warning, rollback) and ADR 0049. Staging has the keys on. Production has them
off, and its user pool template is unchanged.

## Terms

| Term | Meaning |
|---|---|
| **M1, M3 to M6** | The problems of this slice, numbered in § The problems. M2 (threat protection) was dropped in revision 2; the number is not reused. The rubric and the plan use these numbers. |
| **P0** | The test on a throwaway user pool that comes before any product change (§ P0). **U1 to U6** are the open questions it answers (U5 dropped with M2). |
| **Review id** (`M-13`) | The id in the 2026-10-19 project review (`original_review.md` in the programme folder). |
| **MFA** | Multi-factor authentication: a second proof after the password. Here the second proof is a code sent by email. |
| **Email MFA**, `EMAIL_OTP` | Cognito's email one-time-password factor. Cognito sends a code to the account's email address at sign-in. It needs the pool to send email through our own SES account and the Essentials or Plus feature plan. |
| **SES** | Amazon Simple Email Service. The pool sends its email (invitation, verification code and now the MFA code) through SES in the same AWS account. |
| **Feature plan** | Cognito's pricing tier for a user pool: Lite, Essentials or Plus (CloudFormation `UserPoolTier`). Both pools are on Essentials (U1), which allows email MFA and managed login. This slice does not change it. |
| **Threat protection** | Cognito's leaked-password and risk checks on sign-in. Plus plan only. Out of scope (owner ruling, revision 2). |
| **Account recovery** | How a person who forgot their password gets a reset code. Today `EMAIL_ONLY`. AWS does not allow email MFA when email is the only recovery channel (M3). |
| **Hosted sign-in page** | The page on `https://<cognito_domain_prefix>.auth.eu-west-2.amazoncognito.com` where people type their password. The app redirects there and back (authorization code flow with `react-oidc-context`). |
| **Session cookie** | After a person types their password (and code) on the hosted page, Cognito keeps a cookie for one hour. A new sign-in request in that hour (for example a new tab) gets tokens with no password and no code. A change to the pool's factors does not end it. |
| **Classic hosted UI** / **managed login** | Two versions of the hosted sign-in page. Classic (version 1) is what both pools use (U1). Managed login (version 2) is the newer page with branding. Both live on the same Cognito address. CloudFormation property `ManagedLoginVersion` on the domain. Switching version ends every open hosted-page session once. |
| **Branding style** | A `CfnManagedLoginBranding` resource: one per app client. It holds a settings document (colours, spacing, dark mode) and image assets (logo, favicon). Managed login does not work for a CDK-made client without one. It cannot change the page's wording. |
| **`user reissue`** | The ops command that sets a new temporary password, **only** for an account that has never signed in (`FORCE_CHANGE_PASSWORD`). It refuses an active account on purpose, so an operator never holds a working password for someone else (`backend/src/policy_atlas/ops/commands.py`, `reissue_temporary_password`). It is not a reset path for active users. |
| **All-off** | An environment whose `sign_in` keys are all off (or absent). Production is all-off in this slice. |
| **CDK, synth** | AWS Cloud Development Kit, the Python library our infrastructure is written in. *Synth* turns it into a CloudFormation template; `make -C infra test` asserts on it. |

## Read first

- `infra/infra/cognito_auth.py`: the whole construct (user pool, SPA client, hosted domain,
  the email templates and their placeholder check).
- `infra/infra/policy_atlas_stack.py` around line 175: where `CognitoAuth` is built from
  `pa_config.json`.
- `infra/pa_config.json` (`email` per environment: on in staging, **off in production**).
- `infra/email/` (the invitation and verification templates M5 matches).
- `frontend/src/auth/OidcAuthProvider.tsx` (sign-in, silent refresh and sign-out against the
  hosted domain).
- `infra/DEPLOYMENT.md` § "Pool email through SES" and § 4 "Security headers" (the runbook
  shape to follow).
- `docs/tasks/064-security-hardening/original_review.md` § M-13 and the programme's
  § "064d MFA and threat protection".
- This task's gitignored `research/cognito-facts.md` and `research/sign-in-ui-options.md`
  (AWS, CDK and pricing facts with URLs, gathered 2026-11-19). ADR 0049 repeats the URLs that
  matter.

## What sign-in looks like today

| Part | Today | After this slice (staging) | Do not change |
|---|---|---|---|
| Second factor | none (`MfaConfiguration` OFF) | email code each time the password is typed | — |
| Feature plan | Essentials in both (U1) | Essentials | both |
| Threat protection | off | off | both |
| Account recovery | `EMAIL_ONLY` | the P0 result (M3) | production |
| Sign-in page | classic hosted UI, AWS look | managed login, our logo and colours | the Cognito address; the app's redirect flow |
| Code email | — | branded, same look as the invitation | invitation and verification emails |
| App client | code flow, 60-minute access token, 30-day refresh token, no user-existence errors | unchanged | all of it |
| Self sign-up, sign-in alias, password policy, deletion protection | as built in 064a and 065 | unchanged | all of it |
| Our CSP (064c) | lists the hosted domain in `connect-src` and `frame-src` | unchanged (same domain) | all of it |
| Frontend and backend code | `OidcAuthProvider`; ops commands | unchanged, unless P0 shows a break (stop condition) | — |

## The problems

| Id | Problem | Required after the slice |
|---|---|---|
| **M1** | A password alone signs in (review M-13, MFA part). | With `sign_in.mfa` = `"email"`, the pool has `MfaConfiguration` ON and `EnabledMfas` exactly `["EMAIL_OTP"]`. Every sign-in where the person types their password asks for an emailed code. A sign-in through the one-hour session cookie asks for neither (accepted; same as the password today). SMS and TOTP are never enabled (the CDK default turns SMS on, and SMS can then only be removed by turning MFA off). No SMS role is created. |
| **M3** | Email MFA cannot work with `EMAIL_ONLY` recovery: AWS refuses it, or every email-only user fails sign-in. | Whenever email MFA is on, the recovery setting is the one P0 proves keeps **self-service** reset working for an email-only user. If P0 finds none, the slice stops (§ Stop conditions); `user reissue` is not a fallback. |
| **M4** | The sign-in page is the plain AWS page. | With `sign_in.managed_login` true, the hosted domain uses managed login and a branding style exists for the SPA client, built from committed files: one settings document and the logo (plus favicon). The owner approves the look on staging before the slice closes. |
| **M5** | The code email would use Cognito's plain default text. | With email MFA on, the pool's email MFA subject and body come from new files in `infra/email/`, in the same style as the invitation. The body must contain `{####}`; synth fails if it does not (the existing placeholder check). |
| **M6** | A switch-on with no plan can lock people out or surprise them. | Keys are per environment and validated: a missing `sign_in` block means all-off, an unknown key or value fails synth, and `mfa` = `"email"` with pool email off fails synth. **All-off adds nothing**: no new property or resource on the user pool, client or domain (no explicit plan, MFA, recovery, email-MFA or managed-login value, no branding), so the production template is byte-for-byte the same as today's. A committed test proves it against a committed baseline. The runbook covers: the P0 record; the user warning before switch-on; the one forced re-sign-in when the page changes version; code limits and lock-out (who helps, and that operators do not trigger repeat codes); rollback in a tested order for branding and for MFA with recovery, with abort criteria and an operator sign-in check after each step; and the production prerequisites (pool email on first). |

## P0 — test on a throwaway pool (before any product change)

The AWS documents leave open points. Each can change the design, so they are tested first, on
a **new, throwaway user pool in the staging account** (not the live staging pool), on the
Essentials plan, with email through the staging SES identity. Then the pool is deleted. Results
go to `research/p0-results.md` (gitignored) and into § P0 results and ADR 0049.

| Id | Question | Changes |
|---|---|---|
| **U1** | Plan, MFA, SMS, recovery and page version of the live pools. **Answered** (§ P0 results). | M6 |
| **U2** | Which recovery setting lets an email-only user sign in with email MFA required **and** reset their own password from the hosted page: `EMAIL_ONLY` (AWS says no), "email, then SMS" (`EMAIL_AND_PHONE_WITHOUT_MFA`), or none? | M3 |
| **U3** | Does an invited user (temporary password) get the new-password step and then the email code, in that order, on managed login? Does a never-signed-in account still work with `user reissue`'s `AdminSetUserPassword` under MFA? | M1, M6 runbook |
| **U4** | Does a `CfnManagedLoginBranding` deployed through the CDK resource (not only the console editor) carry our logo, colours and dark mode? Is a brand font possible? What are the asset and template size limits? Export the settings document. | M4 |
| **U6** | Against a managed-login domain, using a local frontend pointed at the throwaway pool: do the app's sign-in, silent refresh (hidden frame) and sign-out still work? Does a new tab within the hour sign in with no code (the session cookie)? Does a refresh token issued under classic survive the switch to managed login? | the frontend "unchanged" row; M1 wording; M6 runbook |

P0 writes to AWS (creates and deletes one pool in the staging account); the owner approved it
on 2026-11-19 with the build. It changes nothing in the repository but the gitignored notes.

## Scope / Out of scope

- **In:** `infra/infra/cognito_auth.py`, its call site, `infra/pa_config.json`, new files in
  `infra/email/` and a branding folder under `infra/`, `infra/tests/unit/`,
  `infra/DEPLOYMENT.md`, ADR 0049, `docs/deferred.md`, the programme map's 064d paragraph, the
  knowledge bundle where it records sign-in facts.
- **Out:**
  - Threat protection and the Plus plan (owner ruling, revision 2): a later task.
  - A custom sign-in page in our app. Managed login cannot change its wording; if that is not
    acceptable after the owner sees staging, a custom page is its own task.
  - A custom sign-in address such as `auth.policyatlas.uk` (owner ruling: later).
  - An operator password-reset command for active accounts.
  - Production switch-on: a later config change, after the staging live checks and with
    production email turned on first.
  - Remembered devices (neither hosted page supports them), TOTP or passkeys.
  - Token storage, the 30-day refresh token, and step-up sign-in within the cookie hour.
  - Backend and frontend code, unless P0 finds a break (stop condition).

## Deferred work this slice takes in

From [docs/deferred.md](../../deferred.md):

- § Accounts, organisations and administration, **Planned** "the Cognito pool has no MFA": taken
  in. It closes for staging with this slice; the entry is rewritten to name the production
  switch as the remaining step.
- § Infrastructure and deployment, "Sign-in tokens stay in `sessionStorage` with a 30-day
  refresh token": read and left as it is. A code at each password sign-in makes a shorter
  refresh token more costly for users, so the condition stays a product decision.

New entries this slice adds: the production switch-on; threat protection (Plus plan, the rest
of review M-13); the custom sign-in address; a custom sign-in page if the fixed wording is not
acceptable.

## Constraints & approval gates

- **Auth (hard gate):** the whole slice. Approved by the owner on 2026-11-19 (§ Status).
- **Production config (hard gate):** production keys stay off; its pool template must not
  change (M6). Turning them on is later work with its own approval.
- **AWS writes outside a deploy:** P0 creates and deletes one throwaway pool in the staging
  account. Approved with the build.
- **Cost:** none beyond today's plan; SES email at $0.10 per 1,000 codes.
- **No new dependency, no schema change, no change to public interfaces.** The app client's
  settings and the hosted domain address stay as they are.
- Synth tests use the existing infra test harness; no live AWS call in `make verify`.

## Public / private boundary

Public-safe: the CDK code, config keys, email templates, branding settings and logo (already
public on the site), the runbook. Private: P0 notes with pool ids and user names, the test
users' passwords and codes, sign-in event logs. P0 uses test email addresses the owner
controls, never a real user's.

## Model route

n/a. No inference.

## Disciplines binding this slice

- **Model only what behaves:** two keys, each changes the pool. The recovery setting and the
  code email are derived from `mfa`, not separate keys.
- **Flag, don't drop:** any P0 answer that weakens the design is written into the contract and
  the runbook, not hidden in the notes.
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md).

## Stop conditions

Halt and escalate when:

- P0 shows no recovery setting keeps self-service reset with email MFA (U2). The owner then
  chooses: an operator reset command (its own design), TOTP instead of email, or something
  else.
- P0 shows email MFA does not work on managed login, or an invited user cannot finish first
  sign-in (U3).
- P0 shows the app's sign-in, silent refresh or sign-out breaks on managed login (U6). That
  makes the slice touch frontend code, which this contract does not cover.
- The production template would change with all keys off.
- Any change would need SMS, a phone number or a plan change.
- The branding cannot carry the logo through the CDK resource (U4).

## Acceptance checks

- `make verify` and `make -C infra test` green.
- Synth tests (rubric item 6).
- **Staging live checks** (scope pinned here: the changed surfaces plus one cheap full-chain
  smoke; no full end-to-end run):
  1. An existing user signs in: branded page, password, branded code email arrives, code
     accepted, app loads.
  2. A newly invited user: temporary password, new password, code, app loads.
  3. Forgot password: the self-service path M3 chose works end to end.
  4. A wrong code is refused; an expired code is refused; five wrong codes start the lock-out,
     and the runbook's recovery step works.
  5. The ops pages sign in the same way.
  6. A new tab within the hour signs in with no code (cookie); sign-out, then a new sign-in
     asks for password and code.
  7. Full-chain smoke: start one task run and see its progress stream.
- The owner approves the sign-in page's look on staging.

## Verification evidence expected

In [verification.md](verification.md): the P0 record (U1 to U6, summarised, no ids or codes);
`make verify` output; the all-off baseline test passing; each staging live check with date and
result; screenshots of the branded page in light and dark mode; the user warning text that
went to staging testers; known gaps.

## Risk tier & review focus

**Tier 4**: auth, plus a production config file and a rollback plan. Review focus: the SMS
trap, the production template staying unchanged, the recovery setting, a lock-out path in the
rollout or the rollback, and anything that sends a code or a reset to the wrong person.

## P0 results

**U1** (read-only `describe-user-pool` and `describe-user-pool-domain`, 2026-11-19, by the
lead):

| | Staging | Production |
|---|---|---|
| Feature plan | Essentials | Essentials |
| MFA | OFF | OFF |
| SMS configuration | none | none |
| Recovery | `verified_email` only (`EMAIL_ONLY`) | `verified_email` only (`EMAIL_ONLY`) |
| Pool email | `DEVELOPER` (our SES) | `COGNITO_DEFAULT` (production `email.enabled` is false) |
| Hosted page version | 1 (classic) | 1 (classic) |
| Estimated users | 26 | 100 |

So: both pools already have the plan that email MFA and managed login need. No SMS
configuration exists, so SMS cannot become a factor by itself.

U2, U3, U4, U6: _to fill after P0 runs._
