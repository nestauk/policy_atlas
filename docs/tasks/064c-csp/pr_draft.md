# Task 064c: a Content Security Policy and security headers on the website

## What / why

The October 2026 security review found that the website sends no Content Security Policy
(finding M-03). A Content Security Policy (CSP) is a header that tells the browser which
places a page may load scripts, styles, images and network calls from. The browser refuses
everything else. So if a future bug ever lets an attacker put a script into a page, the
browser does not run it, does not send data to an unknown host, and does not show the page
inside another site's frame. This matters here because the sign-in tokens sit in the
browser's `sessionStorage`, where any script on the page can read them.

This PR adds the policy. It is the third part of the security programme
(`docs/tasks/064-security-hardening/programme.md`), after the quick wins (PR #120) and the
firewall (PR #128).

Task folder: `docs/tasks/064c-csp/`. Decision record:
`docs/adr/0048-content-security-policy-and-security-headers-on-cloudfront.md`.

### What changes

1. **Our own headers policy replaces AWS's ready-made one.** CloudFront (AWS's content
   delivery network, which serves the website) adds the headers to every response. Until
   now both of its cache rules used AWS's managed `SECURITY_HEADERS` policy, which cannot
   be changed. A new infrastructure file, `infra/infra/components/security_headers.py`,
   builds our own policy, and both cache rules use it.
2. **The five old headers keep their values.** HSTS (HTTP Strict Transport Security: use
   HTTPS only), `X-Frame-Options`, `Referrer-Policy`, `X-XSS-Protection` and
   `X-Content-Type-Options` keep the managed policy's values and its rules about replacing a
   value the origin sends. One change: HSTS now also covers every subdomain
   (`includeSubDomains`). Every web name under both domains already serves HTTPS only.
3. **A Content Security Policy, built from `infra/pa_config.json`, never written by hand.**
   Scripts only from our own site (plus the AWS CAPTCHA script where the waitlist CAPTCHA
   is on). Network calls only to our API, the two Amazon Cognito sign-in hosts, and AWS's
   CAPTCHA hosts where the CAPTCHA is on. No inline or `eval` scripts, ever. Styles allow
   inline `<style>`, because the dialog library adds one at run time; inline styles cannot
   run code (an accepted gap, in `docs/deferred.md`).
4. **A Permissions-Policy** turns off camera, microphone, location, payment and four other
   browser features that the app never uses.
5. **One new setting per environment, `csp_mode`.** `"report-only"`: the browser blocks
   nothing and prints each violation in the developer console. `"enforce"`: the browser
   blocks every violation. Both environments start in report-only. A missing or wrong value
   stops the build before anything in AWS changes.
6. **The deployment guide** (`infra/DEPLOYMENT.md`, "Security headers") explains every header
   and source, the manual browser check, how to switch to enforce, how to add a source, and
   how to roll back.

No frontend code changes and no deploy-script changes.

### What happens after merge

Nothing is blocked by this PR. The order after it, each step a one-line config change:

1. Staging deploy, then the `curl` check and a **manual browser check** in report-only
   mode (the owner, about 30 minutes; the list is in the deployment guide). There is no
   report collector, so the browser console is the only place a violation shows. The check
   starts with a deliberate violation, to prove the console reports at all.
2. Staging switches to `"enforce"`, and the check runs again: no CSP lines except the
   deliberate one. Then one full task run on staging.
3. Production gets report-only with the next release, then switches to enforce after
   staging, with a short check.

## Size of the diff

8 commits; 19 files, +1,648 / −20 lines against `dev`. Most of the lines are docs (task
records, the deployment guide, the decision record).

| what | files | added | removed |
|---|---:|---:|---:|
| infrastructure code and config (`infra/infra`, `infra/pa_config.json`) | 3 | 172 | 3 |
| infrastructure tests (`infra/tests`) | 2 | 257 | 7 |
| docs (task records, decision record, deployment guide, knowledge, deferred) | 14 | 1,219 | 10 |

## Proof it works

Evidence: `docs/tasks/064c-csp/verification.md`.

- **`make verify`** passes, and so do the infrastructure tests (`make -C infra test`, 148)
  and the dependency check (`make audit`).
- One test per problem reads the generated AWS template for both environments: both cache
  rules use the new policy; the five old headers and their flags are exact; the CSP equals a
  written-out expected string for each environment; report-only and enforce never send both
  headers; the CAPTCHA sources appear exactly when the CAPTCHA is on; a missing or wrong
  `csp_mode` stops the build; the policy fits CloudFront's 1,783-character limit (staging
  476, production 429).
- **A dry run against the real staging account** (`cdk diff`, nothing changed): the only
  changes this slice makes are the new policy and the two cache rules that now point at it.
  The other lines are the usual backend image update.
- The live checks on staging cannot run until this is deployed. They are listed in
  `verification.md` § Live checks.

## Risk tier

Tier 4 (the highest). It changes production configuration in both accounts, and in enforce
mode a missing source could stop the app working for every user. That is why both
environments start in report-only, and why rollback is one config line.

## AI role

The agent (Claude) wrote the contract, rubric, plan and decision record, each approved by the
owner. Codex built the component and its tests; the lead agent reviewed them and added one
test. The lead agent wrote the docs, ran the dry run, ran the review stack in a fresh
conversation, and fixed what it found. The owner decided: production starts in report-only;
`frame-ancestors 'self'`; the refresh-token lifetime and an automated browser check are left
for later; and, in the review, to add `'self'` to `frame-src` and to narrow the CAPTCHA
script source.

## Review focus

- **The five old headers keep their values and their override flags**, and HSTS adds only
  `includeSubDomains` (no `preload`).
- **Report-only and enforce never both send the policy**, and a bad `csp_mode` stops the
  build.
- **Every host the browser calls is listed for each environment.** A missing Cognito host
  would break sign-in only at the hourly token refresh.
- **Nothing in `script-src` allows inline code.**

## Reviews run

Findings and decisions in `verification.md` § Review findings.

- [x] Contract verifier (a fresh Claude Opus agent, read-only)
- [x] `/code-review` (medium)
- [x] Security review (a fresh Claude agent, scoped to this PR's changes)
- [x] Adversarial review by Codex (a different model family, read-only)
- [ ] `/simplify`: not run. `/code-review` already ran its reuse and simplification angles
  on the same diff (three findings, adjudicated); a second pass by the same model family
  adds little.
- [x] Dry run against the staging account (`cdk diff`)

What the reviews found and this PR fixes:

- `frame-src` did not list our own site. The sign-in library's hidden frame opens Cognito,
  which sends the frame back to our site, and an enforced policy would have blocked that
  last step. Now fixed (owner ruling).
- The CAPTCHA script source allowed every `awswaf.com` host, including other AWS customers'.
  It now allows only the CAPTCHA script hosts (`*.captcha-sdk.awswaf.com`, read from the
  staging account). Network calls keep the wider source until the staging check shows
  which hosts the CAPTCHA calls.
- The guide said the next deploy undoes an emergency console edit. It does not, unless the
  deploy changes the policy. The guide now says so.
- The guide asked the enforce check for a refusal line and for zero CSP lines at once. It
  now says "zero apart from the deliberate one".
- One test left half-built stacks in the shared test app, and production was not checked to
  use the new policy. Both are fixed.

## Known gaps & deferred seams

`docs/deferred.md` § Security headers: the switch to enforce in each environment; inline
styles; no report collector; no automated browser check; no CSP on the ops pages or the
API's own responses; tokens in `sessionStorage` with a 30-day refresh token; the CAPTCHA's
network source still wide.

Still unverified until the staging deploy: whether CloudFront accepts the two custom header
names (if not, CloudFormation rolls the deploy back), whether the headers reach deep links,
and what the CAPTCHA needs beyond scripts and network calls.

## Public safety

- [x] No secrets, credentials, or real source text in the diff or evidence. The policy lists
  public host names only; the account id is not printed.
- [x] Logs and screenshots are public-safe.
- [x] No change that needs approval was added without it: one config key in both
  environments, one headers policy per account attached to both cache rules, and the guide,
  as the approved contract lists. The two review-stack changes to the policy were ruled by
  the owner.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
