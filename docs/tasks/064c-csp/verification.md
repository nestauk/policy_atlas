# Verification: 064c-csp

Evidence for task 064c (Content Security Policy and security headers on CloudFront).
Contract: [contract.md](contract.md) (revision 2). Plan: [plan.md](plan.md) (draft 2).
ADR: [0048](../../adr/0048-content-security-policy-and-security-headers-on-cloudfront.md).

## Commands run

| Gate | Command | Result | Notes |
|---|---|---:|---|
| Phase 0 (build-open) | `make verify` | pass | Backend 4,831 passed, 1 skipped; frontend 1,998 passed; lint, typecheck, build, drift-check green. |
| Phase 0 (build-open) | `make -C infra test` | pass | 125 passed. |
| Phase 1 | `make -C infra test` | pass | 134 passed (9 new). |
| Phase 1 | `ruff check` on the four changed infra Python files | pass | |
| Step-6 exit | `make verify` (first two runs) | fail, not this slice | One backend test failed in each run, a different one each time (`test_check_steps.py::test_choose_keeps_at_most_six_success_and_three_failure_pathways`, then `test_option_search.py::test_option_searches_run_at_the_configured_width`). Both runs overlapped a full `pytest -n auto` in the 065 worktree, which uses the same test database. The first test passed 3 of 3 alone. This slice changes no backend code. |
| Step-6 exit | `make verify` (after the 065 run ended) | pass | Backend 4,831 passed, 1 skipped (the two tests above both pass); frontend 1,998 passed; infra 134; lint, typecheck, build, drift-check green. |
| Step-6 exit | `make -C infra test` | pass | 134 passed. |
| Step-6 exit | `make audit` | pass | "No known vulnerabilities found". |

## Plan-time AWS reads (read again 2026-11-18 at build-open, read-only)

**The managed `SECURITY_HEADERS` policy** (staging account):

```
$ AWS_PROFILE=pa_staging aws cloudfront get-response-headers-policy \
    --id 67f7725c-6f97-4210-82d7-5512b31e9d03 \
    --query 'ResponseHeadersPolicy.ResponseHeadersPolicyConfig.SecurityHeadersConfig'
{
    "XSSProtection": {"Override": false, "Protection": true, "ModeBlock": true},
    "FrameOptions": {"Override": false, "FrameOption": "SAMEORIGIN"},
    "ReferrerPolicy": {"Override": false, "ReferrerPolicy": "strict-origin-when-cross-origin"},
    "ContentSecurityPolicy": {},
    "ContentTypeOptions": {"Override": true},
    "StrictTransportSecurity": {"Override": false, "AccessControlMaxAgeSec": 31536000}
}
```

This matches plan P2: the five kept headers, their values and their override flags. HSTS has
no `IncludeSubdomains` and no `Preload`. There is no CSP.

**Custom response headers policies** (both accounts; limit 20):

```
$ AWS_PROFILE=pa_staging aws cloudfront list-response-headers-policies --type custom \
    --query 'ResponseHeadersPolicyList.Quantity'
0
$ AWS_PROFILE=pa-prod aws cloudfront list-response-headers-policies --type custom \
    --query 'ResponseHeadersPolicyList.Quantity'
0
```

So the name `policy-atlas-v3-security-headers` is free in both accounts.

## Checks beyond the build

- **Synth tests** (`infra/tests/unit/test_security_headers.py`, and the replaced pin in
  `test_synth.py::test_cloudfront_uses_oac_with_spa_fallback_and_certificate`). One per
  problem, matched to rubric item 6:
  - S1: `test_s1_to_s4_report_only_properties_match_each_environment_config` (both
    environments, whole stack): both behaviours reference the one custom policy, never the
    managed id; the five kept headers equal the managed policy's values and override flags
    (the dict compared is exactly the AWS read above, plus `IncludeSubdomains: true`,
    `Preload: false`).
  - S2: the same test compares the report-only value with the literal `STAGING_CSP` /
    `PROD_CSP` strings (which include `frame-src` with the Cognito hosted domain) and
    checks `https://*.awswaf.com` is present exactly when that environment's
    `backend.waf.captcha` is true; `test_s2_csp_sources_are_complete_and_safe` (no
    `'unsafe-inline'` or `'unsafe-eval'` in `script-src`, at most 1,783 characters);
    `test_s2_rejects_a_csp_over_cloudfront_limit`;
    `test_s2_function_adds_waf_source_only_when_captcha_is_enabled`;
    `test_s2_cognito_domain_config_couples_the_user_pool_and_csp` (the coupling test: a
    changed `cognito_domain_prefix` reaches both the `UserPoolDomain` and the CSP's
    `connect-src` and `frame-src`).
  - S3: `test_s3_enforce_uses_the_built_in_csp_header_only` (whole stack, copied config);
    `test_s3_rejects_missing_or_unknown_modes` (component);
    `test_s3_whole_stack_rejects_missing_or_unknown_mode_from_config` (whole stack, key
    deleted and `"Enforce"`); the report-only case is in the S1 test (no
    `ContentSecurityPolicy` in the security headers, custom header with override on).
  - S4: the S1 test pins the `Permissions-Policy` custom header, its value and override.
- **The literal CSP strings** (written out in the test):
  - Staging (457 characters): `default-src 'self'; script-src 'self' https://*.awswaf.com;
    style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self';
    connect-src 'self' https://api.v3.policyatlas.uk https://cognito-idp.eu-west-2.amazonaws.com
    https://policy-atlas-v3.auth.eu-west-2.amazoncognito.com https://*.awswaf.com; frame-src
    https://policy-atlas-v3.auth.eu-west-2.amazoncognito.com; frame-ancestors 'self';
    form-action 'self'; object-src 'none'; base-uri 'self'`
  - Production (422 characters): the same without the two `https://*.awswaf.com` sources,
    with `https://api.policyatlas.uk` and the `policy-atlas-v3-prod` hosted domain.
- **AI evals:** none (no inference).
- **Manual / browser:** none yet. The live checks run on staging after merge and deploy
  (below).

## Dry run (Phase 3, 2026-11-18, commit 53870bd5)

The plan's command, from the repository root, with the staging SSO session:

```bash
cd infra && export AWS_PROFILE=pa_staging \
  && export CDK_DEFAULT_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)" \
  && N="$(aws ssm get-parameter --region eu-west-2 --name /policy_atlas_v3/metabase/allowed_cidrs --query Parameter --output json | PYTHONPATH=. python3 -m infra.metabase_allowlist size)" \
  && PATH=.venv/bin:$PATH npx cdk@2.1133.0 diff -c env_name=staging -c stage=all -c metabase_allowlist_size="$N" PaV3AppStack
```

Result (exit 0, one stack with differences):

```
[+] AWS::CloudFront::ResponseHeadersPolicy SecurityHeaders/Policy
[~] AWS::CloudFront::Distribution FrontendDistribution
    CacheBehaviors[/index.html].ResponseHeadersPolicyId: "67f7725c-…" -> {"Ref": "SecurityHeadersPolicy37F9B5C0"}
    DefaultCacheBehavior.ResponseHeadersPolicyId:         "67f7725c-…" -> {"Ref": "SecurityHeadersPolicy37F9B5C0"}
[~] AWS::Lambda::Function Ingest/Function                     (image hash only)
[~] AWS::ECS::TaskDefinition PolicyAtlasBackendTaskDef        (image hash only, replace)
[~] AWS::ECS::TaskDefinition PolicyAtlasMigrationTaskDef      (image hash only, replace)
[~] AWS::ECS::Service PolicyAtlasBackendService               (follows the new task definition)
[~] AWS::SSM::Parameter MigrationTaskDefArnParameter          (follows the new task definition)
```

The slice's two lines are exactly the plan's expectation. The other five lines change only
the backend container image hash: this checkout's backend code is newer than the image
on staging (dev commits since the last staging deploy); this slice changes no backend
code. Every normal deploy shows them. No firewall lines, so 064b's web ACL is already on
staging. Nothing else; the diff matches.

## End-to-end command

Not run yet: the slice has no local end-to-end path (CloudFront headers exist only after a
deploy). The live checks are the contract's staging steps, run after merge to `dev` and the
staging deploy, in the owner's browser:

```bash
for p in / /index.html /tasks/x; do
  echo "== $p"; curl -sI "https://v3.policyatlas.uk$p" \
    | grep -iE 'content-security|permissions-policy|strict-transport|x-frame|referrer|x-content-type|x-xss'
done
```

then the manual pass in `infra/DEPLOYMENT.md` § 4 "Security headers" (it starts with
`fetch("https://example.com")` in the console), then `csp_mode: "enforce"` on staging, the
same `curl`, the second pass and the full-chain smoke (one task run with its progress).

## Live checks (pending)

| Step | State |
|---|---|
| Staging report-only: `curl` on `/`, `/index.html`, `/tasks/x` | pending (after merge and deploy) |
| Staging report-only manual pass (deliberate violation first) | pending |
| Sources added after the pass | pending |
| Staging enforce: `curl`, second pass with zero CSP lines | pending |
| Staging full-chain smoke after enforce | pending |
| Production report-only: `curl` | pending (with the release) |
| Production enforce: config change, `curl`, short pass | pending (after staging enforce) |

## Diff summary

- `infra/infra/components/security_headers.py` (new): `content_security_policy()` builds
  the CSP string from the API origin, the Cognito region and hosted domain, and the
  CAPTCHA flag; `SecurityHeaders` creates the response headers policy
  `policy-atlas-v3-security-headers` with the five kept headers (HSTS now with
  `includeSubDomains`), the CSP in the header that `csp_mode` names, and the
  Permissions-Policy. It refuses an unknown mode and a string over 1,783 characters.
- `infra/infra/policy_atlas_stack.py`: the managed policy is replaced by the component;
  both behaviours already read the same variable.
- `infra/pa_config.json`: `"csp_mode": "report-only"` in both environments.
- `infra/tests/unit/test_security_headers.py` (new) and `test_synth.py` (three extra
  whole-stack synths: enforce, coupling, production; the managed-id pin replaced).
- `infra/DEPLOYMENT.md` § 4 "Security headers"; `docs/deferred.md` § Security headers
  (task 064c seams); the programme map's 064c paragraph; ADR 0048 § As built.
- **No deviations from the contract or the plan.** One lead addition to the delegated
  build: the whole-stack test for a missing or wrong `csp_mode` (plan P6 asked for it; the
  first Codex pass tested the component only).

## Intent & assumptions

- The production whole-stack synth in the tests reuses the staging test environment
  (account, region, `env_name`) with the production `pa_config` block, so it needs no extra
  lookup context. Every CSP input comes from the production config; the region is
  `eu-west-2` in both.
- The bad-mode whole-stack test builds its stack in the shared test app after that app was
  synthesised; the stack fails in its constructor and nothing synthesises the app again.

## Known unverified items

- Whether CloudFront accepts `Content-Security-Policy-Report-Only` and `Permissions-Policy`
  as custom header names (contract stop condition). `cdk diff` cannot see it; the first
  staging deploy is the proof, and CloudFormation rolls back on refusal.
- Whether the policy reaches the error-response path (deep links). The `curl` on `/tasks/x`
  is the check.
- What the WAF CAPTCHA SDK needs beyond `script-src` and `connect-src`. The report-only pass
  shows it.

## Public safety

The policy holds public host names only. The AWS reads above show a public managed policy
and a count. The account id in the dry-run image path is not printed here. No tokens or
user data.

## Review handoff (step-7/8 inputs)

- **Executor provenance (for the family flip):** Phase 1 code and tests by Codex
  (`codex:rescue`, one brief), reviewed by the lead, plus one lead-written test
  (`test_s3_whole_stack_rejects_missing_or_unknown_mode_from_config`). Phase 0 and Phase 2
  (all prose, ADR note) and Phase 3 by the lead (Claude). So the Codex review lane should
  look hardest at the prose and the lead test; a Claude lane at the component.
- **Adjudication items:** none flagged as deviations. Worth a look: the bad-mode test adds
  a failed stack to the shared test app (see Intent); the production synth reuses the
  staging environment.
- **Diff scope:** everything on this branch after `ee1de99d` (plan approved).
- **Knowledge candidates:**
  - Two checkouts share the local test database: a full `pytest -n auto` in the 065
    worktree made two unrelated backend tests fail in this checkout's `make verify`, a
    different one each run. Before calling a red gate real, check
    `pgrep -fl pytest` for the other checkout's run. (Memory already holds this; it bit
    again, so it may deserve a line in the build skill's "red base" rule.)
  - `cdk diff` against a branch always shows the backend image hash lines (Lambda, two task
    definitions, service, SSM parameter) when the checkout's backend differs from the
    deployed image. A dry-run reviewer should expect them and look past them, not stop.
  - The managed `SECURITY_HEADERS` policy's override flags are not uniform:
    `X-Content-Type-Options` overrides the origin, the other four do not. A replacement
    that sets every flag the same way would silently change behaviour.
  - A CSP built from config must use a plain string for the Cognito hosted domain (from
    `cognito_domain_prefix`), not `CognitoAuth.hosted_domain`, which is a deploy-time token
    the tests cannot compare. The coupling test is what keeps the two in step.

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md) § Security headers (task 064c
seams): the enforce switch per environment, `'unsafe-inline'` styles, no report collector,
no automated browser check, no CSP on the ops pages or API responses, tokens in
`sessionStorage` with a 30-day refresh token.
