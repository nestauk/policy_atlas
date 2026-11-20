---
type: Integration quirk
title: A CloudFront CSP built from config — redirects, tokens, override flags and the CAPTCHA host
description: Four traps found building the CloudFront security headers policy (064c) — frame-src is checked again on every redirect, so a sign-in frame that returns to our own address needs 'self'; the CSP needs plain strings, not CDK tokens; the managed SECURITY_HEADERS override flags are not uniform; the WAF CAPTCHA needs captcha, token and static awswaf.com sources plus data-URI media, found only by a browser console pass.
tags: [infra, cloudfront, csp, security-headers, cdk, cognito, waf]
generated:
  by: process:okf-migrate
  at: 2026-11-19
sources:
  - resource: "infra/infra/components/security_headers.py"
    title: "`infra/infra/components/security_headers.py`; `infra/infra/policy_atlas_stack.py` (the `SecurityHeaders` call)."
  - resource: "infra/tests/unit/test_security_headers.py"
    title: "`infra/tests/unit/test_security_headers.py` (literal CSP strings, override flags, coupling test)."
  - resource: "docs/adr/0048-content-security-policy-and-security-headers-on-cloudfront.md"
    title: "`docs/adr/0048-content-security-policy-and-security-headers-on-cloudfront.md` \u00a7 As built."
  - resource: "docs/tasks/064c-csp/verification.md"
    title: "`docs/tasks/064c-csp/verification.md` \u00a7 Plan-time AWS reads, \u00a7 Review findings."
---

# Rule

The web app's security headers come from one CloudFront response headers policy, built by
`infra/infra/components/security_headers.py` from `infra/pa_config.json` (task 064c,
ADR 0048). Four things that were not obvious:

1. **A frame directive is checked again at every redirect.** The sign-in library's hidden
   frame opens the Cognito hosted domain, which redirects the frame back to our own
   address. `frame-src` replaces `default-src` for frames, so with only the Cognito domain
   listed the last hop is blocked once the policy is enforced. `frame-src` lists `'self'`
   as well. The same holds for `connect-src` and any fetch that follows a redirect.
2. **Build the CSP from plain config strings, not CDK tokens.** `CognitoAuth.hosted_domain`
   is a deploy-time token: the length check and the literal-string tests cannot read it.
   The stack builds the hosted domain from `cognito_domain_prefix` and the region, and a
   coupling test (`test_s2_cognito_domain_config_couples_the_user_pool_and_csp`) proves a
   changed prefix reaches both the user pool domain and the CSP.
3. **The managed `SECURITY_HEADERS` policy's override flags are not uniform.**
   `X-Content-Type-Options` overrides the origin's value; HSTS, `X-Frame-Options`,
   `Referrer-Policy` and `X-XSS-Protection` do not. A replacement that sets every flag the
   same way silently changes behaviour. Read the managed policy with
   `aws cloudfront get-response-headers-policy` and pin the exact flags in a test.
4. **The WAF CAPTCHA uses four awswaf.com sources, and only a browser shows them.** The page
   loads `jsapi.js` from the `ApplicationIntegrationURL` that `scripts/deploy.sh` reads, which
   in staging is `<id>.<id>.eu-west-2.captcha.awswaf.com`. That script loads `challenge.js` from
   `<id>.<id>.eu-west-2.token.awswaf.com` and a font stylesheet (with its fonts) from
   `static.captcha.awswaf.com`; the audio puzzle plays a `data:` clip (`media-src`). The first
   policy guessed `captcha-sdk.awswaf.com` and missed all four; the staging report-only console
   pass on 2026-11-20 found them. A CSP `*.` wildcard matches any number of leading labels.
   Run the pass in an Incognito window: browser extensions add their own `font-src` lines.

# Why

Each trap fails silently until enforce mode or a deploy: report-only mode blocks nothing,
synth accepts tokens, and a wrong override flag still produces a valid policy.

# Watch out

- No report collector exists, so report-only violations show only in the browser console of
  whoever looks. The manual pass in `infra/DEPLOYMENT.md` § Security headers starts with a
  deliberate violation to prove the console reports at all.
- A console edit of the policy is not undone by a deploy that leaves the policy unchanged;
  see [noop-deploys-dont-reassert-template-pins](noop-deploys-dont-reassert-template-pins.md).
