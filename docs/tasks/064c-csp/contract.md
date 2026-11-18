# Task contract: 064c-csp

Third slice of the [064 security hardening programme](../064-security-hardening/programme.md).
Boundaries are in [AGENTS.md](../../../AGENTS.md); specs in [docs/specs/](../../specs/index.md).

> **Status:** revision 2 (2026-11-18). Contract approved (before planning): 2026-11-18 ·
> owner, with every § Owner items recommendation taken (production starts in report-only;
> `frame-ancestors 'self'`; refresh-token lifetime and the automated check deferred).
> Contract-stage adversarial review 2026-11-18 (Codex, 6 findings; raw record in the gitignored
> `research/`), all folded into revision 2 the same day, no design change: a deliberate
> violation proves the console reports before a pass counts (F1); every override flag pinned
> (F2); the deploy script does not read `csp_mode`, synth alone validates it (F3); the DNS
> inventory recorded (F4); the `frame-ancestors`
> and `frame-src` reasons corrected (F5, F6). · Plan approved (before implementation):
> 2026-11-18 · owner (draft 2) · ADR:
> [0048](../../adr/0048-content-security-policy-and-security-headers-on-cloudfront.md), Accepted 2026-11-18.

## Goal

Add a second layer of protection to the web app. If a future bug ever lets an attacker put a
script into a page, the browser must refuse to run it, refuse to send data to an unknown
host, and refuse to show the page inside another site's frame. Today the browser has no such
instructions: the app sends no Content Security Policy, and the sign-in tokens (including a
30-day refresh token) sit in `sessionStorage`, where any script on the page can read them.

## Deliverable

One pull request on `task/064c-csp` into `dev` that lands S1 to S6 below: a custom CloudFront
response headers policy, built in CDK from `infra/pa_config.json`, that keeps today's
security headers, adds a Content Security Policy and a Permissions-Policy, and adds
`includeSubDomains` to HSTS; one new per-environment key that chooses report-only or
enforce; the deployment notes; and synth tests for each. Both environments ship in
report-only mode. Staging and then production switch to enforce by later config changes,
each after a manual browser pass (§ Acceptance checks).

## Terms

| Term | Meaning |
|---|---|
| **Review id** (`M-03`) | The id in the 2026-10-19 project review (`original_review.md` in the programme folder). |
| **S1 to S6** | The six problems of this slice, numbered below. The rubric and the plan use these numbers. |
| **CSP** | Content Security Policy. A response header that lists, per kind of resource (scripts, styles, images, network calls, frames), the sources the browser may use. The browser refuses anything not listed. Each list is a *directive*, for example `script-src 'self'`. |
| **`'self'`** | In a CSP, the page's own origin (here `https://<domain_name>`). It does not cover `blob:` or `data:` addresses, or other hosts such as `api.<domain_name>`. |
| **Report-only** | The same policy sent in the header `Content-Security-Policy-Report-Only`. The browser blocks nothing. Chrome prints a "[Report Only]" line in the developer console for each violation, but no standard requires that without a report collector, so each manual pass first proves it with a deliberate violation (S6). We have no report collector, so the console is the only place a violation shows. |
| **Enforce** | The policy sent in the header `Content-Security-Policy`. The browser blocks every violation. |
| **`csp_mode`** | The one per-environment key this slice adds to `policy_atlas_config` in `infra/pa_config.json`: `"report-only"` or `"enforce"`. Defined under S3. |
| **Response headers policy** | A CloudFront object that adds headers to every response of the cache behaviours it is attached to. Today both behaviours (the default one and `/index.html`) use AWS's managed `SECURITY_HEADERS` policy, which cannot be changed, only replaced. |
| **Cache behaviour** | A CloudFront rule for a set of paths. The distribution has two: the default (`*`) and `/index.html`. |
| **HSTS** | HTTP Strict Transport Security. A header that tells the browser to use only HTTPS for this host for one year. `includeSubDomains` extends that to every subdomain. `preload` (not used) asks browser makers to hard-code it, which is very hard to undo. |
| **Permissions-Policy** | A header that turns off browser features (camera, microphone, location and so on) for the page and anything it embeds. |
| **Manual pass** | One person opens the app in Chrome with the developer console open, uses every surface in the S6 list once, and records each CSP line the console prints. Defined in S6. |
| **WAF CAPTCHA SDK** | The AWS script that shows the waitlist puzzle (task 064b). It loads from a per-account AWS host under `awswaf.com` and makes its own network calls there. Only staging has it on today (`backend.waf.captcha`). |
| **Cognito hosts** | The app talks to two Amazon Cognito hosts: the issuer `https://cognito-idp.<region>.amazonaws.com` (the browser reads the sign-in settings from it) and the hosted sign-in domain `https://<cognito_domain_prefix>.auth.<region>.amazoncognito.com` (the browser exchanges and refreshes tokens there). Sign-in and sign-out are page redirects, which a CSP does not govern. |
| **CDK, synth** | AWS Cloud Development Kit, the Python library our infrastructure is written in. *Synth* turns it into a CloudFormation template, which `make -C infra test` asserts on. |

## Read first

- `infra/infra/policy_atlas_stack.py` lines 343 to 417: the CloudFront distribution, its two
  behaviours, the managed policy at line 353, and the custom error responses that serve
  `/index.html` for every app route.
- `infra/infra/components/waf.py` and its use at lines 72 to 77: the pattern for a component
  that reads a config value and is tested by synth.
- `infra/tests/unit/test_synth.py` lines 1135 to 1155: the pin on the managed policy id,
  which this slice replaces.
- `scripts/deploy.sh` lines 30 to 200 (the embedded config reader; `backend.waf` at line 81
  is the pattern for a validated key).
- `frontend/src/auth/OidcAuthProvider.tsx` (which Cognito hosts the browser calls),
  `frontend/src/views/splash/wafCaptcha.ts` (the CAPTCHA script), `frontend/src/lib/blobUrl.ts`
  and `frontend/src/views/toc/exports.ts` (blob and data addresses).
- `docs/tasks/064-security-hardening/original_review.md` § M-03.
- This task's gitignored `research/csp-facts.md` (AWS, MDN and W3C facts with URLs, gathered
  2026-11-18). ADR 0048 repeats the URLs that matter.

## What the browser loads today

Taken from the source and the built bundle on 2026-11-18. This table is the evidence for the
directive list in S2. A row marked *keep* must still work after the change.

| Kind | What | Where in the code | Directive |
|---|---|---|---|
| Script | The app bundle from `/assets/` | `frontend/index.html` | `script-src 'self'` · keep |
| Script | The WAF CAPTCHA SDK, on first focus of the waitlist form (staging only today) | `views/splash/wafCaptcha.ts:64` | `script-src https://*.awswaf.com` · keep |
| Style | The app CSS; React `style` props (set through the DOM, not governed) | `src/index.css` | `style-src 'self'` · keep |
| Style | Radix Dialog and Sheet add a `<style>` element at run time to lock page scroll | `@radix-ui/react-dialog` via `react-remove-scroll-bar` | needs `'unsafe-inline'` (see S2) · keep |
| Image | Upload previews (`URL.createObjectURL`) | `lib/blobUrl.ts`, `views/toc/uploads.tsx:50`, `views/NewTaskView.tsx:140` | `img-src blob:` · keep |
| Image | Theory-of-change PNG/SVG export and print image | `views/toc/exports.ts:134` to `179` | `img-src data:` · keep |
| Font | Self-hosted fonts under `/fonts/` | `src/index.css:15` to `50` | `font-src 'self'` · keep |
| Network | The API at `https://api.<domain_name>` (all calls, including the progress stream, use `fetch`) | `api/client.ts:19`, `api/sse.ts:115` | `connect-src` · keep |
| Network | Cognito issuer (sign-in settings) and hosted domain (token exchange and refresh) | `auth/OidcAuthProvider.tsx` | `connect-src` · keep |
| Network | Font fetches by the export library | `views/toc/exports.ts` | `connect-src 'self'` · keep |
| Network | WAF CAPTCHA SDK calls | AWS-controlled | `connect-src https://*.awswaf.com` · keep |
| Frame | A hidden frame to the Cognito hosted domain, used by the sign-in library only if a session has no refresh token (not expected; the policy permits it, and no pass exercises it) | `oidc-client-ts` | `frame-src` · keep |
| None | No analytics, no third-party fonts or images, no `eval`, no workers, no inline `<script>`, no `<object>` or `<embed>`, no form posted by the browser | bundle scan | — |

The API's own responses come from the load balancer, not CloudFront, so this policy does not
reach them. The ops pages of task 065 are served by the backend at `ops.<domain_name>`, also
not through CloudFront, so this policy does not reach them either.

## The problems

| # | Review | Today | Required |
|---|---|---|---|
| **S1** | M-03 | Both cache behaviours use the managed `SECURITY_HEADERS` policy. It sends HSTS (one year, no subdomains), `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-XSS-Protection: 1; mode=block` and `X-Content-Type-Options: nosniff`. | A custom `cloudfront.ResponseHeadersPolicy`, built by a new component `infra/infra/components/security_headers.py`, attached to **both** behaviours in place of the managed one. It sends the same five headers with the same values and the same override flags (the managed policy overrides the origin's value for `X-Content-Type-Options` only; the other four have override off), with one change: HSTS adds `includeSubDomains` (no `preload`). The three new headers (S2, S3, S4) have override on, so a future origin header can never weaken them; S3 sends none of them today. Every web name under the domain already serves HTTPS only. Inventory of 2026-11-18: `policyatlas.uk` (apex, `www`, `api`, `metabase`; `mail` holds mail records only) and `v3.policyatlas.uk` (apex, `www`, `api`, `metabase`), each answering plain HTTP with a 301 to HTTPS; the other records are certificate and DKIM (email signing) records, which no browser visits. The Cognito hosted sign-in domain is under `amazoncognito.com`, outside both zones. So nothing loses access. `X-Frame-Options` stays, because some browsers ignore `frame-ancestors` in report-only mode. |
| **S2** | M-03 | No CSP. | The policy sends one CSP, built by a function in the component from `pa_config.json` values, never written by hand. The directives, in this order: `default-src 'self'`; `script-src 'self'` + W; `style-src 'self' 'unsafe-inline'`; `img-src 'self' data: blob:`; `font-src 'self'`; `connect-src 'self' https://<backend_subdomain>.<domain_name> https://cognito-idp.<aws_region>.amazonaws.com https://<cognito_domain_prefix>.auth.<aws_region>.amazoncognito.com` + W; `frame-src https://<cognito_domain_prefix>.auth.<aws_region>.amazoncognito.com`; `frame-ancestors 'self'`; `form-action 'self'`; `object-src 'none'`; `base-uri 'self'`. Here **W** is `https://*.awswaf.com`, added only when `backend.waf.captcha` is true, so turning the CAPTCHA on in production later also updates that environment's CSP in the same deploy, and no new key is needed. `'unsafe-inline'` in `style-src` is an **accepted defect**: Radix adds a `<style>` element whose content changes at run time, and a static CloudFront header cannot carry a nonce (a one-time value per response), so no stricter form works. Inline styles cannot run code. `script-src` never gets `'unsafe-inline'` or `'unsafe-eval'`. `frame-ancestors 'self'` instead of `'none'` matches today's `X-Frame-Options: SAMEORIGIN` (who may put our page in a frame). `frame-src` is the separate directive for frames our page creates; listing the Cognito hosted domain there permits the sign-in library's hidden-frame fallback. The policy is at most 1,783 characters (CloudFront's limit for both header kinds); a synth test asserts it. |
| **S3** | M-03 | — | One new key `csp_mode` in `policy_atlas_config`, both environments: `"report-only"` sends the S2 policy in the custom header `Content-Security-Policy-Report-Only`; `"enforce"` sends it in CloudFront's built-in `Content-Security-Policy` security header. Never both. A missing key or any other value makes synth fail. `scripts/deploy.sh` does not read the key: it uses nothing from it, and the deploy runs synth before it changes anything in AWS, so a bad value stops the deploy at that point. (This differs from `backend.waf`, which the deploy script reads for the CAPTCHA values.) Initial values: **both environments `"report-only"`**. Each environment switches to `"enforce"` by its own config change after its own manual pass (§ Acceptance checks). The synth tests pin both environments' values. |
| **S4** | M-03 | No Permissions-Policy. | The policy sends the custom header `Permissions-Policy: accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()`. Each listed feature is off for the page and any frame. The app uses none of them. Only well-known feature names are listed, because Chrome prints a console warning for a name it does not know. This header is the same in both modes and both environments. |
| **S5** | — | The managed policy id is pinned by one synth test. | Synth tests on the template's properties, both environments: both behaviours use the custom policy and not the managed id; the five kept headers, their values and their override flags; HSTS has `includeSubDomains` and no `preload`; the CSP string equals the expected string built from that environment's config, including the Cognito hosted domain in `frame-src`; `report-only` puts it in the custom header and leaves the built-in one empty, `enforce` the reverse; the override flag of each new header; W is present exactly when `backend.waf.captcha` is true; the string is at most 1,783 characters; the Permissions-Policy value; a missing or unknown `csp_mode` raises. |
| **S6** | — | Nobody knows what a CSP would block. | `infra/DEPLOYMENT.md` gains a section "Security headers": what the policy contains and where each source comes from; the `csp_mode` key; **the manual pass** (below); how to switch to enforce; how to add a source when a pass finds a real violation (a code change in the component, never a console edit that the next deploy would undo); rollback. **The manual pass**, in Chrome with the console open and "Preserve log" on, signed in. **First, the proof:** in report-only mode, run `fetch("https://example.com")` in the console and record the "[Report Only]" line it prints (in enforce mode, the refusal line). If no line appears, the pass stops: console silence then proves nothing. Then: the splash page and the waitlist puzzle including its audio option (where the CAPTCHA is on); sign-in; sign-out; a token refresh (keep a signed-in tab open past the access token's lifetime); the task list; a new task with an image upload preview; a running task with its progress stream; a side sheet (Radix); the sources view and its CSV and JSON downloads; the map view; a theory of change with its PNG, SVG and draw.io exports and print; a report's print; a public task view; the legal page; a deep link opened directly (it is served by the error-response path). Each console line that names the CSP is recorded with the page and the blocked address. |

One number per problem, one invariant per problem.

## Scope / Out of scope

- **In:** `infra/infra/components/security_headers.py` (new), `infra/infra/policy_atlas_stack.py`
  (use it on both behaviours), `infra/pa_config.json` (one key, both environments),
  `infra/tests/unit/test_synth.py`, `infra/DEPLOYMENT.md` (§ Security
  headers), `docs/deferred.md` (the items under § Known gaps), the programme map's 064c
  paragraph (corrected: `style-src`, `frame-ancestors`, the ops note), ADR 0048.
- **Adding a source** that the manual pass shows the WAF CAPTCHA SDK needs (for example
  `data:` or `blob:` in another directive, or `https://*.awswaf.com` in `img-src`,
  `style-src`, `frame-src`, `worker-src` or `media-src`) is in scope, recorded in
  `verification.md` with the console line. Anything that would add `'unsafe-inline'` or
  `'unsafe-eval'` to `script-src` is a stop condition.
- **Out:** any frontend code change (the inventory found nothing the policy breaks that the
  app should change). Headers on the API's responses (JSON from the load balancer; a page
  cannot be built from them). Headers on the 065 ops pages (served by the backend on an
  allowlisted host; see § Known gaps). A report collector (`report-uri` or `report-to`).
  A shorter refresh-token lifetime (§ Owner items 3). An automated browser check of the CSP
  (§ Owner items 4). Moving tokens out of `sessionStorage`. MFA (064d).

## Constraints & approval gates

- **Production config:** one new key in `infra/pa_config.json` for both environments; a new
  CloudFront response headers policy in both accounts (the account allows 20 custom
  policies; we have none); both behaviours of both distributions change policy. The
  programme rule applies: the mode differs per environment over time, so it is a key; the
  directive list, the Permissions-Policy and the kept headers have one right value
  everywhere and are built in the component from values the config already has.
- **Dependencies, auth, tenancy, schema, egress, public interfaces:** none. The CSP lists
  the Cognito hosts the app already uses; it changes no sign-in setting.
- **Cost:** nil. Response headers policies are free.
- **Staging leads by one release** (programme rule; CSP enforcement is on its list of
  changes that can lock people out): staging report-only and its manual pass; production
  report-only with the same PR; staging enforce and a second pass; production enforce
  after that, with a short pass.
- **Rollback:** set `csp_mode` back to `"report-only"` and deploy. The deploy updates the
  policy in place; CloudFront applies it within minutes, and `index.html` has a 60-second
  cache. A full revert of the PR restores the managed policy. There is no faster switch
  inside the app; for an emergency, the CloudFront console can edit the policy in place
  (the next deploy restores the code's version). No data to restore.
- **HSTS `includeSubDomains` is the one part with a long tail.** A browser that saw it keeps
  forcing HTTPS on every subdomain for up to a year, even after a rollback. Today every
  subdomain serves HTTPS (inventory in S1), so this only matters if someone later adds a
  plain-HTTP subdomain under `policyatlas.uk`. DEPLOYMENT.md says so.

## Public / private boundary

All artefacts are public-safe. The policy lists public host names only. Console lines
recorded in `verification.md` show page paths and blocked addresses, never tokens or user
data (a `blob:` address is a random id).

## Design annex

None. No visible change.

## Model route

n/a. No inference.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves.** One key, and it changes the synthesised template. The CAPTCHA
  sources follow the existing `backend.waf.captcha` key instead of a new one.
- **Flag, don't drop.** `'unsafe-inline'` styles, the ops pages and the API responses are
  stated, not silently skipped.
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md).

## Stop conditions

Halt and escalate when: the deliberate violation of S6 prints nothing in the console;
CloudFront refuses `Content-Security-Policy-Report-Only` or
`Permissions-Policy` as a custom header (AWS lists no reserved names, but did not confirm
these two); the manual pass shows the app or the CAPTCHA SDK needs `'unsafe-inline'` or
`'unsafe-eval'` in `script-src`, or a host not in § What the browser loads today other than
an `awswaf.com` one; or the policy would exceed 1,783 characters.

## Acceptance checks

- `make verify` green; `make -C infra test` green.
- The S5 tests, one per problem, listed in the plan.
- **Live check on staging after the deploy** (about 30 minutes, the owner's browser):
  - S1 to S4: `curl -sI https://v3.policyatlas.uk/`, `/index.html` and a deep link such as
    `/tasks/x` each show the kept headers, HSTS with `includeSubDomains`, the
    Permissions-Policy, and the CSP in the report-only header only. The deep link proves the
    header reaches the error-response path, which AWS does not document.
  - S6: the manual pass in report-only mode. Every CSP console line is either fixed by
    adding a source (in scope, above) or explained. Then `csp_mode: "enforce"` on staging,
    deploy, the same `curl` shows the enforced header, and the manual pass runs again with
    zero CSP lines.
- **Production:** with this PR, `curl` shows the report-only header. After staging enforce,
  a config change to `"enforce"`, deploy, `curl`, and a short pass (sign-in, task list, one
  sheet, one export, sign-out). The production steps are follow-on config changes,
  recorded in `verification.md` as done or pending.
- **One cheap full-chain smoke** on staging after enforce: one task run completes and shows
  its progress, which proves the API, Cognito refresh and progress stream are all allowed.

## Verification evidence expected

Command results; the `curl` header output for both modes on staging; the manual-pass notes
(page, console lines, action taken) for report-only and enforce; the diff summary; the ADR
link; in `verification.md`.

## Known gaps (go to `docs/deferred.md`)

- `'unsafe-inline'` in `style-src` (S2). Lever: a Radix version without run-time `<style>`,
  or a nonce, which needs the HTML served by something other than S3.
- No report collector: a violation in production after enforce is seen only if someone
  opens the console. Lever: `report-to` and a small endpoint.
- No automated browser check of the policy (§ Owner items 4).
- The 065 ops pages and the API's responses carry no CSP. The ops host is limited to
  allowlisted addresses. Lever: a small backend middleware on the ops host.
- Sign-in tokens stay in `sessionStorage` with a 30-day refresh token (§ Owner items 3).

## Owner items (to rule at the contract gate)

1. **Production starts in report-only, not enforce.** The programme's order is staging
   report-only, staging enforce, production enforce. This contract adds production
   report-only in between, because it costs nothing and shows production-only differences
   (no CAPTCHA, other Cognito domain) before anything is blocked. Recommended: yes.
2. **`frame-ancestors 'self'`, not `'none'`.** `'none'` is a little stricter, but it differs
   from today's `X-Frame-Options: SAMEORIGIN`, and our own origin is the only one allowed
   either way. (Revision 2: the first draft also cited the sign-in fallback; that is
   `frame-src`'s job, see S2.) Ruled: `'self'`.
3. **Refresh-token lifetime.** The review suggests a shorter one than 30 days. That changes
   how often people sign in, which is a product decision, not a header. Recommended: out
   of this slice; recorded in `docs/deferred.md`.
4. **An automated check.** A Playwright test that serves the built app with the real header
   and fails on any CSP console line would catch a future library that breaks the policy.
   It needs a way to share the policy string between infra and the frontend test, about
   half a day. Recommended: defer; the manual pass covers this slice, and DEPLOYMENT.md
   tells the next person who adds a third-party library to rerun it.

## Risk tier & review focus

**Tier 4** (production config in both accounts; enforce mode can stop the app working for
every user). ADR, rollback plan and human-approved plan required. Review stack: contract
verifier, `/code-review`, `/security-review`, adversarial review of contract and plan,
simplification pass, human deep review. Focus: the kept headers really keep their values
and override flags; report-only and enforce never both send the policy; the policy reaches
both behaviours and the error-response path; every `connect-src` host the app calls is
listed for each environment (a missing Cognito host breaks sign-in only at token refresh,
an hour later); W follows `backend.waf.captcha`; nothing in `script-src` allows inline code.
