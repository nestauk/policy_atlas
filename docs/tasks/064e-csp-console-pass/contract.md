# Task contract: 064e-csp-console-pass

A small follow-up to [064c](../064c-csp/contract.md): the staging console pass in report-only
mode, and the CSP sources it shows are missing.

> **Status:** approved 2026-11-20 · owner (in chat: "commit and run /code-review and
> /security-review, then commit again and push, open a PR"). ADR: amendment to ADR 0048 (inside
> [ADR 0048](../../adr/0048-content-security-policy-and-security-headers-on-cloudfront.md):
> "adding a source" is in its scope).

## Goal

Before staging switches the CSP (Content Security Policy) to enforce, find every source the
app really uses and add the missing ones. In enforce mode, a missing source breaks that part
of the app.

## Deliverable

1. The console pass on staging, recorded in the findings table below.
2. One PR that adds the missing sources in `infra/infra/components/security_headers.py`, with
   the expected strings in `infra/tests/unit/test_security_headers.py` and the CSP table in
   `infra/DEPLOYMENT.md` § Security headers.

The switch to `csp_mode: "enforce"` is not in this task. It is the next change, after this PR
is deployed and a second pass shows no unexplained line.

## Terms

| Term | Meaning |
|---|---|
| **Report-only** | `csp_mode: "report-only"` in `infra/pa_config.json`. The browser blocks nothing; it prints a "report-only" line in the console for each violation. |
| **Source** | One address pattern in a CSP directive, for example `https://*.token.awswaf.com` in `script-src`. |
| **Console pass** | The manual check in `infra/DEPLOYMENT.md` § Security headers, "The manual pass". |

## Scope / Out of scope

- **In:** the console pass; new sources in `security_headers.py` and its test; the DEPLOYMENT.md
  CSP table; the `connect-src` CAPTCHA source made narrower than `https://*.awswaf.com` if the
  pass shows the hosts (seam in `docs/deferred.md`).
- **Out:** the enforce switch; production (CAPTCHA is off there, so its CSP does not change);
  `'unsafe-inline'` styles; a report collector; any frontend or backend code.

## Constraints & approval gates

- Never add `'unsafe-inline'` or `'unsafe-eval'` to `script-src`. A library that needs either
  is a design question: stop and ask.
- Never edit the policy in the CloudFront console as a fix.
- The CSP string stays at or below 1,783 characters (synth refuses more).
- No change to `csp_mode`.

## Public / private boundary

Record the blocked address and the page. Never record tokens, cookies, email addresses or
other user data from the console. The CAPTCHA host names hold the AWS integration id; they
are already public in every page load, so they may be committed.

## The console pass

In Chrome on `https://v3.policyatlas.uk`: open the developer console (Cmd+Option+J), turn on
**Preserve log**, and use each surface once. Copy every line that names the Content Security
Policy.

- [x] Proof: `fetch("https://example.com")` prints a report-only `connect-src` line.
Ticked items were covered on 2026-11-20 (Incognito). The unticked ones are not confirmed yet;
they must be done in the pass after this PR is deployed, before the switch to enforce.

- [x] Splash page.
- [x] Waitlist: submit, solve the puzzle, then the audio option. (First try on 2026-11-20 hit
      a staging deploy: the API returned 503, so the submit did not finish.)
- [x] Sign-in on `auth.v3.policyatlas.uk`, with the authenticator code; sign-out. Also
      record every console error on the Cognito pages (any kind, not only CSP). Our CSP
      does not apply there, so a fix is in the Cognito setup (for example the branding in
      `infra/branding/`), and it may be a separate task.
- [ ] Token refresh: a signed-in tab open for more than one hour, then use the app.
- [ ] Task list; new task with an image upload preview.
- [ ] A running task with its progress stream.
- [ ] A side sheet; the sources view with its CSV and JSON downloads; the map view.
- [ ] Theory of change: PNG, SVG and draw.io exports; print.
- [ ] A report's print.
- [ ] A public task view; the legal page.
- [ ] A deep link opened directly in a new tab (`/tasks/<id>`).

## Findings

| # | Page | Blocked address | Directive | Fix |
|---|---|---|---|---|
| 1 | Waitlist | `https://<id>.<id>.eu-west-2.captcha.awswaf.com/<id>/jsapi.js` | `script-src` | add `https://*.eu-west-2.captcha.awswaf.com` |
| 2 | Waitlist | `https://<id>.<id>.eu-west-2.token.awswaf.com/<id>/challenge.js` | `script-src` | add `https://*.eu-west-2.token.awswaf.com` |
| 3 | Waitlist | `https://static.captcha.awswaf.com/fonts/AmazonEmberLt/stylesheet.css` | `style-src` | add `https://static.captcha.awswaf.com` |
| 4 | Waitlist | the stylesheet's `AmazonEmber-Light.woff2` (not seen in the console, because a browser loads a font only when text uses it; the stylesheet, read with `curl`, names it by a relative path, so it is on `static.captcha.awswaf.com`) | `font-src` | add `https://static.captcha.awswaf.com` |
| 5 | Waitlist, audio puzzle | `data:audio/aac;base64,…` | `media-src` (falls back to `default-src`) | add `media-src 'self' data:` when the CAPTCHA is on |

All five are fixed in `security_headers.py`; `https://*.captcha-sdk.awswaf.com` is removed
(nothing used it). The `script-src` sources are pinned to the stack's region. Incognito pass
2026-11-20: no other CSP line on the splash, waitlist and sign-in pages.

Findings 1 and 2: 064c allowed `https://*.captcha-sdk.awswaf.com`, but the script address the
deploy gives the frontend (`VITE_WAF_CAPTCHA_SCRIPT_URL`, from the WAF
`ApplicationIntegrationURL`) is on `captcha.awswaf.com`.

Console pass 1 (2026-11-20, normal Chrome profile with extensions):

- Six `font-src` lines on each full page load of our app, address hidden as `<URL>`. Our own
  CSS loads fonts only from `/fonts/` (`'self'`), and the lines come before the CAPTCHA
  script loads. A stack trace on the Cognito page names `preload-content.js`, which is a
  browser extension script. Confirmed: an Incognito window (extensions off) shows no
  `font-src` line, so an extension adds them. No source is added for them.
- Cognito page (`auth.v3.policyatlas.uk`): React errors #418 and #423 (the page's HTML did
  not match what its script expected) in AWS's own managed-login code. Probably the same
  extension changes the page. Repeat in Incognito; if they stay, they are AWS's to fix.
- No CSP line after sign-in: the token exchange with `auth.v3.policyatlas.uk` passed.
- Not CSP, our app (for a separate task): repeated `404` on `/tasks/<id>/artefact`, `/plan`
  and `/coverage` while a task has none yet; "Blocked aria-hidden" warnings when a focused
  button sits inside a closing panel (`anim-fade-out`) and inside the run status bar.

## Stop conditions

A needed source would require `'unsafe-inline'` or `'unsafe-eval'` in `script-src`; a source
outside AWS or our own domains appears; the CSP would pass 1,783 characters.

## Acceptance checks

- `make -C infra test` passes, with the new literal CSP strings.
- `make verify` passes.
- After deploy: the `curl` check shows the new sources, and a second console pass shows no
  CSP line apart from the deliberate `fetch`.

## Risk tier & review focus

Tier 1: a small change to one infra component and its test, inside an approved ADR. Only
staging's CSP changes. Review: `/code-review` and `/security-review`, looking hardest at how
wide each new source is.
