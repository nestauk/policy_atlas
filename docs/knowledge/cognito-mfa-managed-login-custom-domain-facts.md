---
type: Integration quirk
title: Cognito MFA, managed login and custom domains — what live tests showed
description: Email MFA cannot coexist with self-service password reset for email-only users; preference calls do not unlink a TOTP app (AdminDeleteSoftwareToken does); leaving ManagedLoginVersion out does not roll a domain back; the authenticator entry is named after the sign-in address; discovery switches to a custom domain; old refresh tokens survive the MFA switch-on.
tags: [infra, cognito, mfa, totp, managed-login, cdk, auth]
generated:
  by: process:okf-migrate
  at: 2026-11-20
---

# Rule

Facts from live tests on throwaway user pools in the staging account (task 064d, ADR 0049,
2026-11-19). Each one contradicted or filled a gap in the AWS documents.

1. **Email MFA and self-service password reset cannot live together for people with no
   phone number.** With `EMAIL_ONLY` recovery, a deploy that enables email MFA fails: "At
   least one recovery mechanism other than verified_email should be present". With "email,
   then SMS" recovery the deploy works, but "Forgot password" fails for an email-only user
   ("Could not reset password for the account"). Authenticator-app MFA (TOTP) keeps
   `EMAIL_ONLY` reset working.
2. **Going back from email MFA to `EMAIL_ONLY` takes two deploys.** CloudFormation sets the
   recovery setting before it removes the email MFA settings, so one deploy is refused
   ("Cannot set verified_email as the only member … when EmailMfaConfiguration is active").
3. **With TOTP as the only factor, `AdminSetUserMFAPreference` does not unlink a lost
   phone**; the user's MFA settings list reads empty even while an app is linked.
   `AdminDeleteSoftwareToken` (announced 2026-08-26; boto3 1.44.6 has it, 1.43.79 and
   aws-cli 2.27.43 do not) plus `AdminUserGlobalSignOut` brings back the QR setup.
4. **Leaving `ManagedLoginVersion` out of the template does not change a domain back to
   classic.** The domain stays on version 2 while the branding resource is deleted. A
   rollback must name version 1 (`CLASSIC_HOSTED_UI`). The classic page handles TOTP.
5. **Managed login branding** (`CfnManagedLoginBranding`): no font setting; wording cannot
   change; a logo's width-to-height ratio must be 1:1 to 4:1; the AWS default style has
   `categories.global.pageHeader.enabled` false and `colorSchemeMode` `LIGHT`, so a header
   logo and dark mode need both changed. Read the default with
   `DescribeManagedLoginBrandingByClient` (`ReturnMergedResources`) and edit it.
6. **The authenticator entry is named after the sign-in address**
   (`<prefix>.auth.<region>.amazoncognito.com` by default). With a custom domain, the
   issuer's `openid-configuration` names it for every endpoint, so an OIDC client that reads
   discovery from the issuer needs no change. A pool can hold a prefix and a custom domain
   at once.
7. **A refresh token issued before MFA is switched on still refreshes after it.** People
   meet the new step only at their next full sign-in (up to the refresh-token lifetime)
   unless they are signed out.
8. **A DNS-validated certificate's validation CNAME survives `cdk destroy`.** Delete it by
   hand after a throwaway stack.

# Why

Each fact decides a design or a rollback step, and each is silent until a deploy or a real
sign-in: synth accepts every one of these configurations.
