# ADR 0048 — A Content Security Policy and our own security headers on CloudFront, report-only before enforce

- **Status:** Accepted — 2026-11-18 (owner, task 064c plan gate).
- **Date:** 2026-11-18
- **Task:** [064c-csp](../tasks/064c-csp/contract.md), third slice of the
  [064 security hardening programme](../tasks/064-security-hardening/programme.md).
- **Builds on:** the 2026-10-19 project review (finding M-03; the review file sits in the
  programme folder) · task 026's review hardening, which attached AWS's managed
  `SECURITY_HEADERS` policy to both CloudFront behaviours · ADR 0047 (the WAF CAPTCHA
  script, the app's first third-party script) · the programme rules (every
  environment-specific value is a config key; staging leads by one release for anything
  that can lock people out).

## Context

The web app is static files on S3 behind CloudFront. It sends no Content Security Policy,
so if a bug ever let an attacker put a script into a page, the browser would run it, and
that script could read the sign-in tokens in `sessionStorage` (including a 30-day refresh
token) and send them anywhere. No such bug is known; the CSP is the second layer.

Four facts shape the design. AWS's managed security headers policy cannot be extended,
only replaced. A static file on S3 cannot carry a per-response nonce, so the policy must
list sources, not one-time values. Radix, our component library, adds a `<style>` element
whose content changes at run time, so no strict `style-src` works. We have no report
collector, so in report-only mode the browser console is the only place a violation shows.

The pages these decisions rest on (gathered 2026-11-18, more in the task's gitignored
`research/csp-facts.md`):

- The managed policy's headers:
  https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/using-managed-response-headers-policies.html
- Response headers policies and their limits (1,783 characters per CSP or custom header):
  https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/understanding-response-headers-policies.html
  and https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cloudfront-limits.html
- The WAF SDK's CSP needs: https://docs.aws.amazon.com/waf/latest/developerguide/waf-javascript-api-csp.html
- CSP Level 3 (source matching, report-only): https://www.w3.org/TR/CSP3/

## Decision

1. **Replace the managed policy with our own** CloudFront response headers policy, built in
   CDK by `infra/infra/components/security_headers.py` and attached to both behaviours. It
   repeats the managed policy's five headers with their values and override flags, and adds
   `includeSubDomains` to HSTS (every web name in our DNS zones already redirects to
   HTTPS; no `preload`).
2. **Build the CSP from config, never by hand.** The API origin, the two Cognito hosts and
   the region come from `pa_config.json`; the WAF source `https://*.awswaf.com` follows
   `backend.waf.captcha`, so the CSP and the CAPTCHA can never disagree. `script-src` stays
   `'self'` (plus the WAF source); `style-src` allows `'unsafe-inline'` (accepted, see
   Consequences); `frame-ancestors 'self'` keeps parity with `X-Frame-Options: SAMEORIGIN`;
   `frame-src` lists the Cognito hosted domain for the sign-in library's fallback.
3. **One key, `csp_mode`, per environment**: `report-only` sends the policy in
   `Content-Security-Policy-Report-Only` (a custom header), `enforce` in
   `Content-Security-Policy`. Both environments start in report-only. Each switches to
   enforce by its own config change after a manual browser pass that first proves the
   console reports a deliberate violation.
4. **A Permissions-Policy** turns off eight browser features the app does not use.

## Alternatives considered

- **Keep the managed policy and add the CSP in a CloudFront Function.** A function runs on
  every request and is code to maintain; a response headers policy is configuration.
- **A `<meta>` CSP tag in `index.html`.** It cannot carry `frame-ancestors` or report-only,
  and it would be built by the frontend, away from the config the sources come from.
- **Nonces or hashes for styles.** Nonces need a server that writes each response; hashes
  cannot cover content that changes at run time.
- **Enforce straight away.** The WAF SDK's needs are not fully documented, and a missing
  source would stop the app for everyone; report-only costs one extra release.
- **A report collector (`report-to`).** Useful for seeing violations in production, but it
  is a new endpoint to run. Deferred.

## Consequences

- An injected script cannot run and cannot send data to an unlisted host, once enforced.
- `'unsafe-inline'` styles remain allowed. Inline styles cannot run code; the risk left is
  CSS-based data leaks, which the strict `connect-src` and `img-src` limit.
- A new third-party library that loads from a new host, injects a script or uses `eval`
  breaks after enforce until its source is added in the component. DEPLOYMENT.md tells the
  person adding it to rerun the manual pass.
- HSTS `includeSubDomains` stays in browsers for up to a year after any rollback, so no
  plain-HTTP subdomain can be added under `policyatlas.uk` later.
- The 065 ops pages and the API's own responses are not served by CloudFront and carry no
  CSP (recorded in `docs/deferred.md`).
- Rollback: `csp_mode: "report-only"` and a deploy; a full revert restores the managed
  policy.

## As built (2026-11-18)

Built as decided, with no deviation. The component is
`infra/infra/components/security_headers.py`: a pure function `content_security_policy`
returns the CSP string, and the construct `SecurityHeaders` creates the policy
`policy-atlas-v3-security-headers` and refuses an unknown `csp_mode` or a string over 1,783
characters. The synth tests in `infra/tests/unit/test_security_headers.py` pin both
environments' strings literally, so any change to a source shows as a failed test.

Two changes from decision 2, made in the review stack (owner ruling, 2026-11-19):

- `frame-src` also lists `'self'`. The sign-in library's hidden frame opens the Cognito
  hosted domain, which sends the frame back to our own address; without `'self'` an
  enforced policy blocks that last step, so the fallback named in decision 2 could not work.
- `script-src` lists `https://*.captcha-sdk.awswaf.com` instead of `https://*.awswaf.com`.
  The CAPTCHA script loads from `<id>.<region>.captcha-sdk.awswaf.com` (read from the
  staging account on 2026-11-19), and the narrower source stops a page from loading scripts
  from other AWS customers' `awswaf.com` hosts. `connect-src` keeps `https://*.awswaf.com`,
  because the hosts the CAPTCHA script calls are known only after the staging pass.

The staging CSP is 476 characters and production's 429.

## Amendment (2026-11-20, task 064e)

The staging report-only console pass showed that the `captcha-sdk` source above was wrong. The
page loads `jsapi.js` from the WAF `ApplicationIntegrationURL`, on
`<id>.<id>.<region>.captcha.awswaf.com`; that script loads `challenge.js` from
`<id>.<id>.<region>.token.awswaf.com` and a font stylesheet with its fonts from
`static.captcha.awswaf.com`, and the audio puzzle plays a `data:` clip. When the CAPTCHA is on,
the policy now has `script-src https://*.<region>.captcha.awswaf.com
https://*.<region>.token.awswaf.com` (pinned to the stack's region, so other regions' customer
hosts are not allowed), `https://static.captcha.awswaf.com` in `style-src` and `font-src`, and
`media-src 'self' data:`. `captcha-sdk` is removed. Production's CSP does not change (the
CAPTCHA is off there). The decision itself stands.
