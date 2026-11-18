# Implementation plan: 064c-csp

> Status: **draft 2 (2026-11-18)**, awaiting the owner's plan gate. Draft 1 was reviewed the
> same day by Codex (read-only, 4 findings, raw record in the gitignored `research/`), all
> folded here: a review phase and its evidence (F1); a coupling test in place of the
> "same shape" test, and `csp_mode` validated through the whole stack (F2); the exact dry-run
> command (F3); the policy name checked free in both accounts (F4, done at plan time). Contract: [contract.md](contract.md) (revision 2, approved). Rubric:
> [rubric.md](rubric.md). ADR: [0048](../../adr/0048-content-security-policy-and-security-headers-on-cloudfront.md), Proposed.
> Problems S1 to S6 and the terms are defined in the contract and not restated here.
> Executor routing follows `docs/agentic-ops/harness.md` § Agent-side model routing. The
> build runs in a fresh conversation with task-cycle-build, opening on Phase 0.

## Order and why

The slice is one new infra component, one config key, its synth tests and documentation.
No frontend, backend, deploy-script, schema or auth code changes. So the order is: the
component and its tests (S1 to S5) in one phase, because the tests are the only proof
before a deploy; then the documents (S6, the ADR, the deferred items). A dry run against
staging (`cdk diff`) comes before the push, because in 064b a dry run caught a property
error that synth, tests and the whole review stack missed. One full-verify gate at
build-open and one at exit are enough; Phase 1 gates on `make -C infra test`.

## Decisions taken in this plan

| # | Problem | Decision |
|---|---|---|
| P1 | S1 to S4 | New `infra/infra/components/security_headers.py`, the same shape as `components/waf.py` (module docstring in plain words, module constants, one construct). **A pure function** `content_security_policy(*, api_origin: str, cognito_region: str, cognito_hosted_domain: str, waf_captcha: bool) -> str` returns the S2 string: directives in the contract's order, joined by `"; "`, sources in each directive joined by one space, `https://*.awswaf.com` appended to `script-src` and `connect-src` only when `waf_captcha` is true. The issuer source is the host only (`https://cognito-idp.<region>.amazonaws.com`, no pool path), so it does not depend on a deploy-time value. **A construct** `SecurityHeaders(Construct)` takes `csp_mode: str` and the four values above, raises `ValueError` when `csp_mode` is not in `CSP_MODES = ("report-only", "enforce")` (a missing key reaches it as `None` and raises the same way), raises `ValueError` when the string is over `CSP_MAX_LENGTH = 1783`, and creates one `cloudfront.ResponseHeadersPolicy` named `policy-atlas-v3-security-headers`, exposed as `self.policy`. The name is free: on 2026-11-18 `aws cloudfront list-response-headers-policies --type custom` returned no custom policies in either account (limit 20). The managed policy is AWS's and is not deleted; the change adds our policy and points both behaviours at it. |
| P2 | S1 | `security_headers_behavior=ResponseSecurityHeadersBehavior(...)` with the managed policy's values and override flags: `strict_transport_security=ResponseHeadersStrictTransportSecurity(access_control_max_age=Duration.seconds(31536000), include_subdomains=True, preload=False, override=False)`; `frame_options=ResponseHeadersFrameOptions(frame_option=HeadersFrameOption.SAMEORIGIN, override=False)`; `referrer_policy=ResponseHeadersReferrerPolicy(referrer_policy=HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN, override=False)`; `xss_protection=ResponseHeadersXSSProtection(protection=True, mode_block=True, override=False)`; `content_type_options=ResponseHeadersContentTypeOptions(override=True)`. These five values were confirmed on 2026-11-18 with `aws cloudfront get-response-headers-policy --id 67f7725c-6f97-4210-82d7-5512b31e9d03` (staging account, read-only): X-XSS-Protection on with mode block, override off; X-Frame-Options `SAMEORIGIN`, override off; Referrer-Policy `strict-origin-when-cross-origin`, override off; X-Content-Type-Options override on; HSTS max age 31,536,000 seconds, override off, no subdomains, no preload; no CSP. The build copies this output into `verification.md`. |
| P3 | S2, S3, S4 | In `enforce` mode: `content_security_policy=ResponseHeadersContentSecurityPolicy(content_security_policy=<string>, override=True)` inside the security headers, and no report-only custom header. In `report-only` mode: no `content_security_policy` in the security headers, and a custom header `ResponseCustomHeader(header="Content-Security-Policy-Report-Only", value=<string>, override=True)`. In both modes: a custom header `ResponseCustomHeader(header="Permissions-Policy", value=PERMISSIONS_POLICY, override=True)`, where `PERMISSIONS_POLICY` is a module constant with the contract's eight features. All class and property names were confirmed against the installed `aws_cdk.aws_cloudfront` (`aws-cdk-lib` 2.261.0) on 2026-11-18; every one is a typed L2 class, so the camelCase trap of 064b (an `Any`-typed property rendered with the wrong case) does not apply. |
| P4 | S1, S2 | `infra/infra/policy_atlas_stack.py`: replace `security_headers = cloudfront.ResponseHeadersPolicy.SECURITY_HEADERS` (line 353) with `security_headers = SecurityHeaders(self, "SecurityHeaders", csp_mode=pa_app_config.get("csp_mode"), api_origin=f"https://{be_domain}", cognito_region=self.region, cognito_hosted_domain=f"https://{pa_app_config['cognito_domain_prefix']}.auth.{self.region}.amazoncognito.com", waf_captcha=be_config["waf"]["captcha"]).policy`. The two behaviours already read the `security_headers` variable, so they change with no other edit. The hosted domain is built from config rather than from `CognitoAuth.hosted_domain`, because that value is a deploy-time token and the CSP string must be a plain string the tests can compare. The coupling test in P6 proves the two move together. `be_config["waf"]["captcha"]` is already validated by `ApiFirewall` earlier in the same constructor, and `captcha` implies `enabled`. Update the comment above it (task 064c, ADR 0048). |
| P5 | S3 | `infra/pa_config.json`: `"csp_mode": "report-only"` in `policy_atlas_config` for staging and prod. |
| P6 | S5 | New `infra/tests/unit/test_security_headers.py` (the component's own tests, like the WAF tests) plus an edit of `test_synth.py` lines 1143 to 1150 (the managed-id pin becomes: both behaviours reference the one custom policy, and neither references the managed id). **The expected CSP strings are written out literally in the test, one per environment**, never recomputed with `content_security_policy`, so a change to the function shows up as a failed test. Cases: for each environment, the policy's template properties (`ResponseHeadersPolicyConfig`): the five kept headers, their values and override flags; HSTS `IncludeSubdomains: true`, `Preload: false`; the CSP in the custom report-only header with override on and no `ContentSecurityPolicy` in the security headers (both environments ship `report-only`); the Permissions-Policy custom header and its override; the literal CSP string, including `frame-src` with the Cognito hosted domain; `*.awswaf.com` present on staging (CAPTCHA on) and absent on prod (CAPTCHA off). With a copied config, each building the **whole `PolicyAtlasStack`** (the existing staging fixture's pattern in `test_synth.py`), so the value travels the real path from `pa_config.json`: `enforce` puts the string in `ContentSecurityPolicy` with override on and leaves no report-only header; a missing `csp_mode` and the value `"Enforce"` each raise; `waf.captcha` true adds the WAF source. **Coupling test:** a copied config with a changed `cognito_domain_prefix` (for example `pa-csp-coupling-test`); in the rendered template, the `AWS::Cognito::UserPoolDomain` resource's `Domain` and the CSP's `connect-src` and `frame-src` hosted-domain sources all carry the changed prefix. This fails if either side stops reading the config value. Function-level: the string never contains `'unsafe-inline'` or `'unsafe-eval'` inside `script-src`; the length is at most 1,783 for both environments; an input that makes it longer raises. |
| P7 | S6, docs | `infra/DEPLOYMENT.md` new § Security headers (contract S6 list, including the deliberate violation, the HSTS subdomain note and where each source comes from). `docs/deferred.md`: a § Security headers (task 064c seams) block with the five known gaps. The programme map's 064c paragraph: corrected `style-src`, `frame-ancestors` and frame reasons, the ops note (served by the backend, not CloudFront), production report-only first. ADR 0048 as built. One `docs/specs/log.md` line only if a spec changes (none expected). |
| P8 | Gates | Full `make verify` plus `make -C infra test` at build-open (gate 1) and at the step-6 exit (gate 2, plus `make audit`). Phase 1 gates on `make -C infra test`. The dry run (Phase 3) gates the push. |

## Phases

| Phase | Problems | Work | Executor | Gate |
|---|---|---|---|---|
| 0 | — | Build-open baseline: `make verify`, `make -C infra test`. Copy the plan-time AWS reads (P1 policy list, P2 managed policy) into `verification.md`. | `fast-worker` | full verify |
| 1 | S1 to S5 | P1 to P6: the component, the stack edit, the config key, the tests. | `codex` (multi-file infra coherence, verifiable by the synth tests; small enough for one brief) | `make -C infra test` |
| 2 | S6 | P7: DEPLOYMENT.md, deferred, programme map, ADR as built. | `lead` (owner-facing prose and the decision record) | step-6 exit: full verify + `make -C infra test` + `make audit` |
| 3 | — | Dry run with the owner's SSO session (`aws sso login --profile pa_staging` in their terminal; the cache is shared). From the repository root: ``cd infra && export AWS_PROFILE=pa_staging && export CDK_DEFAULT_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)" && N="$(aws ssm get-parameter --region eu-west-2 --name /policy_atlas_v3/metabase/allowed_cidrs --query Parameter --output json \| PYTHONPATH=. python3 -m infra.metabase_allowlist size)" && PATH=.venv/bin:$PATH npx cdk@2.1133.0 diff -c env_name=staging -c stage=all -c metabase_allowlist_size="$N" PaV3AppStack`` (the context and CLI version `scripts/deploy.sh` uses). Expected from this slice: one new `AWS::CloudFront::ResponseHeadersPolicy`, and the distribution's two `ResponseHeadersPolicyId` values changing from the managed id to a reference to it (CloudFormation creates the policy before it updates the distribution, because of that reference). Any other line must belong to 064a or 064b if they are not yet deployed on staging (their records list them); anything else stops the push. Record the diff summary in `verification.md`. | `lead` (the owner's account) | the diff matches |
| review | all | Step 7 in a **fresh conversation** with task-cycle-review (the reviewer must not be the chat that wrote the code): contract verifier, `/code-review`, `/security-review`, a Codex family-flip review of the diff, simplification pass; findings adjudicated into the code or `verification.md`; a final `make verify` and `make -C infra test`. Then the PR on the owner's go. | fresh conversation | full verify |
| staging | all | After merge to `dev` and the staging deploy: the contract's live checks in order (`curl` on three paths; the report-only manual pass, which starts with the deliberate violation; any source the pass shows the CAPTCHA SDK needs, added in a follow-up commit; then `csp_mode: "enforce"` on staging, deploy, `curl`, the second pass, the full-chain smoke). Production: report-only with the release; enforce by a later config change after staging enforce, with the short pass. | `lead` (the owner's browser and accounts) | — |


`verification.md` records, by the end: the gate results; the plan-time AWS reads; the
dry-run summary; for staging, the `curl` output on `/`, `/index.html` and `/tasks/x` in
both modes; each manual pass starting with the deliberate violation's console line; any
source added and its console line; the full-chain smoke; the review findings and their
outcome; production report-only and enforce as done or pending.

Every `lead` mark: Phase 3 needs the owner's SSO session; Phase 2 is
owner-facing prose and a decision record; the staging rows need the owner's browser.

## Risks and how the plan meets them

- **CloudFront refuses one of the custom header names.** AWS lists no reserved names but
  did not confirm these two. `cdk diff` cannot see it; the first staging deploy is the
  proof, and CloudFormation rolls the stack back on refusal, so the managed policy stays.
  This is the contract's stop condition.
- **The kept headers drift from the managed policy.** P2's values come from the research
  note; Phase 0 reads the live managed policy and the tests pin what it says.
- **A missing `connect-src` host breaks sessions an hour later**, at the first token
  refresh. The test pins both Cognito hosts per environment; the manual pass includes a
  refresh; the report-only phase means nothing is blocked while this is checked.
- **The header does not reach the deep-link path** (the custom error responses). AWS does
  not document it. The `curl` on `/tasks/x` is the check. If it is missing, `index.html`
  served by the error path would have no CSP; the stop is to escalate, not to patch.
- **The WAF CAPTCHA SDK needs more than AWS documents.** The report-only pass on staging,
  where the CAPTCHA is on, shows it, and adding an `awswaf.com`, `data:` or `blob:` source
  is in scope (contract § Scope). Production has the CAPTCHA off, so its CSP has no WAF
  source until `waf.captcha` turns on, and the same deploy then adds it.
- **Turning the production CAPTCHA on later.** The CSP follows `backend.waf.captcha` in the
  same deploy, and `scripts/deploy.sh` deploys the stacks before it publishes the new
  bundle, so the policy allows the SDK before any page loads it (checked by the contract
  review).
- **Two policies in a row of releases.** The 065 branch also edits
  `policy_atlas_stack.py` and `pa_config.json`. The edits are in different places; the
  second branch to merge resolves a small conflict.

## Owner items at the plan gate

1. **Nothing new to rule.** Contract § Owner items were ruled at the contract gate. The
   plan adds only the dry run (Phase 3), which needs the owner's staging SSO session once.
