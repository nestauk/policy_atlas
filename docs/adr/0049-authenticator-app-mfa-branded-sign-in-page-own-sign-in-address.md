# ADR 0049 — Authenticator-app MFA, a branded Cognito sign-in page, and our own sign-in address

- **Status:** Accepted — 2026-11-19 (owner, task 064d contract revision 3 and plan draft 3).
- **Date:** 2026-11-19
- **Task:** [064d-mfa](../tasks/064d-mfa/contract.md), fourth slice of the
  [064 security hardening programme](../tasks/064-security-hardening/programme.md).
- **Builds on:** the 2026-10-19 project review (finding M-13) · ADR 0033 (the admin read
  across organisations, accepted on a password alone until MFA) · ADR 0046 (the ops service
  and its Cognito permissions) · ADR 0048 (the CSP, which lists the Cognito sign-in
  address) · the programme rules (config keys per environment; staging first).

## Context

A password alone opens any account, including an admin account that reads every
organisation's rows. The sign-in page is Cognito's plain AWS page on an AWS address. The
programme map planned email codes, because every user has a verified email and no app to
install.

Live tests on throwaway pools in the staging account (P0 and P0b, 2026-11-19; record in the
task's gitignored `research/p0-results.md`) changed that plan:

- **Email codes and self-service password reset cannot live together** for people with no
  phone number. With email-only recovery, AWS refuses the deploy ("At least one recovery
  mechanism other than verified_email should be present"). With "email, then SMS", the
  deploy works but "Forgot password" fails for an email-only person. With no recovery, only
  an admin can reset.
- **Authenticator-app codes (TOTP) keep email reset as it is.** An invited person gets:
  temporary password, new password, QR setup, code.
- **Changing a person's MFA preference does not unlink a lost phone** when the app is the only
  factor. `AdminDeleteSoftwareToken` (announced 2026-08-26; boto3 1.44.6 has it, the pinned
  1.43.79 does not) plus a global sign-out brings back the QR setup.
- **Managed login takes our colours, logo and dark mode** through `CfnManagedLoginBranding`;
  it has no font setting and its wording cannot change. A logo's ratio must be 1:1 to 4:1.
  The AWS default style has the header off and light mode only.
- **Leaving `ManagedLoginVersion` out of the template does not change a domain back** to
  classic; the domain stays on version 2 with no branding. A rollback must name version 1.
- **The authenticator entry is named after the sign-in address.** With a custom domain, the
  issuer's discovery document names it for every endpoint, so the app needs no change.
- **A refresh token issued before the switch-on still works after it.**

Sources: https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-mfa.html ·
https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-mfa-totp.html ·
https://aws.amazon.com/about-aws/whats-new/2026/08/amazon-cognito-totp-reset/ ·
https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-managed-login.html ·
https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_cognito/CfnManagedLoginBranding.html ·
https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-add-custom-domain.html ·
https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-cognito-userpool.html

## Decision

1. **MFA is required, with an authenticator app as the only factor**
   (`EnabledMfas: ["SOFTWARE_TOKEN_MFA"]`). SMS and email codes are never enabled. Account
   recovery stays `EMAIL_ONLY`. The code is asked each time a person types their password;
   Cognito's one-hour session cookie skips it, as it skips the password.
2. **No forced sign-out at switch-on** (owner ruling). Existing sessions continue, so each
   person meets the QR setup at their next full sign-in, at most 30 days later.
3. **A lost phone is an operator action:** `user reset-app` signs the person out everywhere,
   then deletes their app link, and records an `ops_action` row with the operator's verified
   AWS identity. Sign-out goes first because it is repeatable and harmless alone, so a
   failure between the two calls leaves a safe state and a rerun is safe.
4. **The hosted page is managed login with our branding**, from committed files in
   `infra/branding/` (colours from `DESIGN.md`, the wordmark outlined from Zosia Display,
   light and dark following the browser).
5. **Our own sign-in address `auth.<domain_name>`**, a Cognito custom domain with a us-east-1
   certificate from the existing cert stack and an alias record. The prefix address stays
   beside it. The CSP lists both.
6. **One `sign_in` block per environment** (`mfa`, `page`, `domain`). No block emits nothing
   new, and a committed test proves the production template is unchanged. `page: "classic"`
   names version 1 so a rollback really rolls back.
7. **The Essentials plan stays.** Threat protection (Plus) is a later task.

## Consequences

- Admin accounts lose the "password alone" exposure of ADR 0033 once each admin signs in
  again; the runbook tells admins to do that at switch-on.
- People must install an authenticator app. A lost phone needs an operator.
- The page says "Sign in to your account." and cannot say more; only a custom sign-in page
  in our app could change it (deferred).
- boto3 moves to 1.44.6 or later for one Cognito call.
- The first deploy with `domain` set takes about eight minutes (certificate and the
  custom domain's CloudFront distribution).
- Removing `domain` again was not tested; it is the last rollback step.
- The DNS alias for the custom domain uses CDK's `UserPoolDomainTarget`, which adds a small
  helper Lambda function and a role that may call `cognito-idp:DescribeUserPoolDomain` on any
  domain (CDK's standard way to read the address's CloudFront name).

## Alternatives rejected

- **Email codes** (the programme plan): no self-service reset for email-only people.
- **An operator reset command for passwords**: would have kept email codes, but a password
  reset path that depends on an operator for every forgotten password is worse than an app.
- **Email codes for admins only** (MFA optional): leaves most accounts on a password alone.
- **A custom sign-in page in our app**: full control of copy, but it puts password and code
  handling in our code and needs a new library.
- **Restyling the classic page**: colours and a raster logo only; no dark mode.
