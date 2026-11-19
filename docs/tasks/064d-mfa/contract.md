# Task contract: 064d-mfa

Fourth slice of the [064 security hardening programme](../064-security-hardening/programme.md).
Boundaries are in [AGENTS.md](../../../AGENTS.md); specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted 2026-11-19 (revision 1). Owner rulings taken before drafting
> (2026-11-19): Cognito managed login with our branding (option B), not a custom sign-in page;
> the sign-in page stays on the Cognito address for now; an email code at **every** sign-in;
> the password-reset setting is decided by a test on staging (P0), with operator-only resets as
> the fallback; staging first. · Contract approved (before planning): _pending_ · Plan approved
> (before implementation): _pending_ · ADR: 0049 (to write at step 4).

## Goal

Today a password alone opens any account, including an admin account that can read every
organisation's rows (an accepted risk in
[ADR 0033](../../adr/0033-organisation-tenancy-and-global-admin-read.md)). This slice adds a
second step: after the password, Cognito emails a one-time code, and the person types it in.
Cognito also starts to check sign-ins for leaked passwords and risky patterns. The sign-in
page itself changes from the plain AWS page to one that carries the Policy Atlas logo and
colours.

Staging gets all of it in this slice. Production keeps its current sign-in until a later
config change, after the staging live checks pass (M6).

## Deliverable

One pull request on `task/064d-mfa` into `dev` that lands M1 to M6 below: three new
per-environment keys under `sign_in` in `infra/pa_config.json`, the Cognito settings that
read them, the branding settings and logo, a branded code email, synth tests, the
deployment notes (switch-on, user warning, rollback) and ADR 0049. Staging has the keys on.
Production has them off, and its user pool template is unchanged.

## Terms

| Term | Meaning |
|---|---|
| **M1 to M6** | The six problems of this slice, numbered in § The problems. The rubric and the plan use these numbers. |
| **P0** | The test on a throwaway user pool that comes before any product change (§ P0). **U1 to U6** are the open questions it answers. |
| **Review id** (`M-13`) | The id in the 2026-10-19 project review (`original_review.md` in the programme folder). |
| **MFA** | Multi-factor authentication: a second proof after the password. Here the second proof is a code sent by email. |
| **Email MFA**, `EMAIL_OTP` | Cognito's email one-time-password factor. Cognito sends a code to the account's email address at sign-in. It needs the pool to send email through our own SES account (it does) and the Essentials or Plus feature plan. |
| **SES** | Amazon Simple Email Service. The pool sends its email (invitation, verification code and now the MFA code) through SES in the same AWS account. |
| **Feature plan** | Cognito's pricing tier for a user pool: Lite, Essentials or Plus (CloudFormation `UserPoolTier`). Email MFA and managed login need Essentials or higher; threat protection needs Plus. Plus costs $0.020 per monthly active user with no free tier (about $1 a month at 50 users). |
| **Threat protection** | Cognito's checks on sign-in (earlier name "advanced security"). Two parts: *compromised credentials* (refuse a password seen in a public leak) and *adaptive authentication* (score each sign-in for risk). Modes: off, **audit** (record only) and **full function** (act on the result). Plus plan only. |
| **Account recovery** | How a person who forgot their password gets a reset code. Today `EMAIL_ONLY`. AWS does not allow email MFA when email is the only recovery channel (M3). |
| **Hosted sign-in page** | The page on `https://<cognito_domain_prefix>.auth.eu-west-2.amazoncognito.com` where people type their password today. The app redirects there and back (authorization code flow with `react-oidc-context`). |
| **Classic hosted UI** / **managed login** | Two versions of the hosted sign-in page. Classic (version 1) is what we use. Managed login (version 2) is the newer page with a branding editor. Both live on the same Cognito address. CloudFormation property `ManagedLoginVersion` on the domain. |
| **Branding style** | A `CfnManagedLoginBranding` resource: one per app client. It holds a settings document (colours, spacing, dark mode) and image assets (logo, favicon, background). Managed login does not work for a CDK-made client without one. It cannot change the page's wording. |
| **`user reissue`** | The existing ops command that sets a new temporary password for a person (`backend/src/policy_atlas/ops/commands.py`, `reissue_temporary_password`). The fallback reset path if self-service reset must go (M3). |
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
| Second factor | none (`MfaConfiguration` OFF) | email code at every sign-in | — |
| Feature plan | unknown (P0 reads it: U1) | Plus | production: unchanged |
| Threat protection | off | audit, then full function (M2) | — |
| Account recovery | `EMAIL_ONLY` | the P0 result (M3) | — |
| Sign-in page | classic hosted UI, AWS look | managed login, our logo and colours | the Cognito address; the app's redirect flow |
| Code email | — | branded, same look as the invitation | invitation and verification emails |
| App client | code flow, 60-minute access token, 30-day refresh token, no user-existence errors | unchanged | all of it |
| Self sign-up, sign-in alias, password policy, deletion protection | as built in 064a and 065 | unchanged | all of it |
| Our CSP (064c) | lists the hosted domain in `connect-src` and `frame-src` | unchanged (same domain) | all of it |
| Frontend code | `OidcAuthProvider` | unchanged, unless P0 shows the sign-out or silent-refresh path breaks (stop condition) | — |

## The problems

| Id | Problem | Required after the slice |
|---|---|---|
| **M1** | A password alone signs in (review M-13). | With `sign_in.mfa` = `"email"`, the pool has `MfaConfiguration` ON and `EnabledMfas` exactly `["EMAIL_OTP"]`. SMS and TOTP are never enabled (the CDK default turns SMS on, and SMS can then only be removed by turning MFA off). No SMS role is created. |
| **M2** | Leaked passwords and risky sign-ins go unseen. | `sign_in.threat_protection` = `"off"`, `"audit"` or `"full"` sets the pool's standard threat protection mode. Any value other than `"off"` sets the Plus plan. Staging ships `"audit"` and moves to `"full"` after one week of audit with no false alarms on real sign-ins. What `"full"` does is pinned by P0 (U5). |
| **M3** | Email MFA cannot work with `EMAIL_ONLY` recovery: AWS refuses it, or every email-only user fails sign-in. | Whenever email MFA is on, the recovery setting is the one P0 proves works for an email-only user. If no setting keeps self-service reset, recovery is `NONE`, the hosted page's "Forgot password" no longer sends a code, and the runbook makes `user reissue` the reset path. |
| **M4** | The sign-in page is the plain AWS page. | With `sign_in.managed_login` true, the hosted domain uses managed login and a branding style exists for the SPA client, built from committed files: one settings document and the logo (plus favicon). The owner approves the look on staging before the slice closes. |
| **M5** | The code email would use Cognito's plain default text. | The pool's email MFA subject and body come from new files in `infra/email/`, in the same style as the invitation. The body must contain `{####}`; synth fails if it does not (the existing placeholder check). |
| **M6** | A switch-on with no plan can lock people out or surprise them. | Keys are per environment and validated: a missing `sign_in` block means all off, an unknown value fails synth. With every key off, the synthesised user pool, client and domain are identical to today's (production proves it). The runbook covers: the P0 record, the user warning before switch-on, the one forced re-sign-in when the page changes version, the audit-to-full step, rollback, and the production prerequisites. |

## P0 — test on a throwaway pool (before any product change)

The AWS documents leave six points open. Each one can change the design, so they are tested
first, on a **new, throwaway user pool in the staging account** (not the live staging pool),
then the pool is deleted. Results go to `research/p0-results.md` (gitignored) and into the
contract's § P0 results and ADR 0049.

| Id | Question | Changes |
|---|---|---|
| **U1** | Which feature plan are the live staging and production pools on, and does either have an SMS configuration? (read-only `describe-user-pool`) | M6: what "unchanged" means for production; M1: an SMS configuration makes SMS an MFA factor by itself. |
| **U2** | Which recovery setting lets an email-only user sign in with email MFA required and, if any, still reset their own password: "email, then SMS" or only `NONE`? | M3 |
| **U3** | Does an invited user (temporary password) get the new-password step and then the email code, in that order, on managed login? | M1, M6 runbook |
| **U4** | Does managed login accept the branding we need (logo, colours, dark mode), and can a brand font be set? Export the settings document the editor writes. | M4 |
| **U5** | With threat protection on full function and no extra risk configuration, what happens to a sign-in with a known-leaked password, and what does adaptive authentication do with MFA already required? | M2 |
| **U6** | Do the app's silent refresh (hidden frame) and sign-out redirect still work against a managed-login domain, using a local frontend pointed at the throwaway pool? Does an existing refresh token survive the switch from classic? | the frontend "unchanged" row; M6 runbook |

P0 writes to AWS (creates and deletes one pool in the staging account) and needs the owner's
go before it runs. It changes nothing in the repository but the gitignored notes.

## Scope / Out of scope

- **In:** `infra/infra/cognito_auth.py`, its call site, `infra/pa_config.json`, new files in
  `infra/email/` and a branding folder under `infra/`, `infra/tests/unit/`,
  `infra/DEPLOYMENT.md`, ADR 0049, `docs/deferred.md`, the programme map's 064d paragraph, the
  knowledge bundle where it records sign-in facts.
- **Out:**
  - A custom sign-in page in our app (option C). Managed login cannot change its wording; if
    that is not acceptable after the owner sees staging, a custom page is its own task.
  - A custom sign-in address such as `auth.policyatlas.uk` (owner ruling: later).
  - Production switch-on: a later config change, after the staging live checks and with
    production email turned on first.
  - Remembered devices (neither hosted page supports them), TOTP or passkeys.
  - Token storage and the 30-day refresh token (deferred by ADR 0048).
  - Backend and frontend code, unless P0 finds a break (stop condition).

## Deferred work this slice takes in

From [docs/deferred.md](../../deferred.md):

- § Accounts, organisations and administration, **Planned** "the Cognito pool has no MFA": taken
  in. It closes for staging with this slice; the entry is rewritten to name the production
  switch as the remaining step.
- § Infrastructure and deployment, "Sign-in tokens stay in `sessionStorage` with a 30-day
  refresh token": read and left as it is. A code at every sign-in makes a shorter refresh
  token more costly for users, so the condition stays a product decision.

New entries this slice adds: the production switch-on; the custom sign-in address; a custom
sign-in page if the fixed wording is not acceptable; the audit-to-full step if it has not
happened by merge.

## Constraints & approval gates

- **Auth (hard gate):** the whole slice. Direction approved by the owner on 2026-11-19
  (§ Status). The contract's 🛑 approves the detail.
- **Production config (hard gate):** production keys stay off; its pool template must not
  change (M6). Turning them on is later work with its own approval.
- **AWS writes outside a deploy:** P0 creates and deletes one throwaway pool in the staging
  account. Needs the owner's go.
- **Cost:** Plus plan, about $1 a month per environment at today's user count, plus SES email
  at $0.10 per 1,000 codes.
- **No new dependency, no schema change, no change to public interfaces.** The app client's
  settings and the hosted domain address stay as they are.
- Synth tests use the existing infra test harness; no live AWS call in `make verify`.

## Public / private boundary

Public-safe: the CDK code, config keys, email templates, branding settings and logo (already
public on the site), the runbook. Private: P0 notes with pool ids and user names, the test
users' passwords and codes, sign-in event logs (they hold IP addresses). P0 uses test email
addresses the owner controls, never a real user's.

## Model route

n/a. No inference.

## Disciplines binding this slice

- **Model only what behaves:** three keys, each changes the pool. The feature plan and the
  recovery setting are derived from them, not separate keys.
- **Flag, don't drop:** any P0 answer that weakens the design (for example, no self-service
  reset) is written into the contract and the runbook, not hidden in the notes.
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md).

## Stop conditions

Halt and escalate when:

- P0 shows email MFA does not work on managed login, or no recovery setting lets an email-only
  user sign in (U2, U3).
- P0 shows the app's silent refresh or sign-out breaks on managed login (U6). That makes the
  slice touch frontend code, which this contract does not cover.
- The production template would change with all keys off.
- Any change would need SMS or a phone number.
- The branding cannot carry the logo (U4).

## Acceptance checks

- `make verify` and `make -C infra test` green.
- Synth tests, one per problem (rubric item 6).
- **Staging live checks** (scope pinned here: the changed surfaces plus one cheap full-chain
  smoke; no full end-to-end run):
  1. An existing user signs in: branded page, password, branded code email arrives, code
     accepted, app loads.
  2. A newly invited user: temporary password, new password, code, app loads.
  3. Forgot password: the path M3 chose works as the runbook says.
  4. A wrong code is refused; an old code is refused.
  5. The ops pages sign in the same way.
  6. Sign-out, then sign-in again in a new tab.
  7. Threat protection in audit: the sign-ins above show as events with risk results
     (`admin-list-user-auth-events`).
  8. Full-chain smoke: start one task run and see its progress stream.
  9. After the audit week: switch to full function and repeat check 1.
- The owner approves the sign-in page's look on staging.

## Verification evidence expected

In [verification.md](verification.md): the P0 record (U1 to U6, summarised, no ids or
codes); `make verify` output; the synth diff for production (no Cognito change); each staging
live check with date and result; screenshots of the branded page in light and dark mode; the
user warning text that went to staging testers; known gaps.

## Risk tier & review focus

**Tier 4**: auth, plus a production config file and a rollback plan. Review focus: the SMS
trap, the production template staying unchanged, the recovery setting, a lock-out path in the
rollout or the rollback, and anything that sends a code or a reset to the wrong person.

## P0 results

_To fill after P0 runs._
