---
type: Integration quirk
title: Cognito invitation and verification templates render only when the pool sends through SES
description: In CDK, UserInvitationConfig and UserVerificationConfig take effect only with the SES sender. With the default Cognito sender, CDK keeps its built-in verification template, so a custom email never appears.
tags: [cognito, cdk, ses, email, integration-quirk, "065"]
generated:
  by: process:okf-migrate
  at: 2026-11-17
---

# Rule

Cognito is the AWS sign-in service. CDK is the AWS Cloud Development Kit, the Python code that defines our cloud resources.

The pool's custom invitation and verification emails are rendered only when the pool's email sender is SES (Simple Email Service). With the default Cognito sender, CDK keeps its built-in verification template. A template you wrote is silently ignored.

So the template code and the SES wiring go together. Test the synthesised template, not just that the code ran.

# Evidence

- `infra/infra/cognito_auth.py`: `cognito.UserInvitationConfig(email_subject=..., email_body=...)` sits beside `ses_region` and `ses_verified_domain`.
- Both environments have an SES identity with production access (see the deferred entry on application-sent email in `docs/deferred.md`).

