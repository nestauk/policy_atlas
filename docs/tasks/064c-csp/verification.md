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
  - Staging (476 characters, after the review-stack changes below): `default-src 'self';
    script-src 'self' https://*.captcha-sdk.awswaf.com; style-src 'self' 'unsafe-inline';
    img-src 'self' data: blob:; font-src 'self'; connect-src 'self'
    https://api.v3.policyatlas.uk https://cognito-idp.eu-west-2.amazonaws.com
    https://policy-atlas-v3.auth.eu-west-2.amazoncognito.com https://*.awswaf.com; frame-src
    'self' https://policy-atlas-v3.auth.eu-west-2.amazoncognito.com; frame-ancestors 'self';
    form-action 'self'; object-src 'none'; base-uri 'self'`
  - Production (429 characters): the same without the two CAPTCHA sources, with
    `https://api.policyatlas.uk` and the `policy-atlas-v3-prod` hosted domain.
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
| Staging enforce: `curl`, second pass with zero CSP lines apart from the deliberate `fetch` refusal | pending |
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

## Review findings (step 7, 2026-11-19)

Scope: `git diff ee1de99d..HEAD` (the slice; the 064a and 064b commits below it are
reviewed in their own PRs). Fresh conversation; the lead adjudicated.

| Lane | Reviewer | Result |
|---|---|---|
| Base gate | `make verify` before the lanes | pass (exit 0; frontend 1,998, infra 134) |
| Contract verifier | `contract-verifier` agent (Claude) | rubric 1, 3, 4, 5, 8, 9 pass; 2, 7, 10 pending by design; 1 medium, 1 low, 1 note |
| Security | `deep-reasoner` agent, security brief (Claude) | no critical, high or medium; 2 low |
| Adversarial | Codex (`codex-rescue`, read-only) | 2 medium; no finding on doc claims, Cognito coupling, mode switch, policy name |
| Code review | `/code-review medium` (Claude) | 9 findings |

Adopted (fixed in this stack):

1. **`frame-src` had no `'self'`** (security L2 and `/code-review` 1; two lanes). The
   hidden sign-in frame opens the Cognito domain, which sends it back to our own address;
   an enforced policy blocked that last step, so the fallback the contract names could not
   work. Owner ruling: add `'self'`. Fixed in `security_headers.py`, the test strings, the
   coupling test, DEPLOYMENT.md, the programme map and ADR 0048 § As built.
2. **`script-src` allowed every `*.awswaf.com` host** (security L1). Owner ruling: narrow
   now. The staging account's integration address (read 2026-11-19, read-only) is
   `<id>.eu-west-2.captcha-sdk.awswaf.com`, so `script-src` lists
   `https://*.captcha-sdk.awswaf.com`. `connect-src` keeps `https://*.awswaf.com` until the
   staging pass shows the SDK's hosts (new seam in `docs/deferred.md`). A new assertion in
   the S1 test pins the `script-src` source to `backend.waf.captcha`.
3. **The runbook said the next deploy undoes a console edit** (contract verifier, medium;
   the lead had the same doubt). CloudFormation rewrites a resource only when its template
   changes, so a console edit can survive unrelated deploys. DEPLOYMENT.md § Adding a source
   and § Rollback now say so.
4. **The enforce pass asked for a refusal and for zero CSP lines** (Codex, medium). Now
   "zero CSP lines apart from the deliberate `fetch` refusal", in DEPLOYMENT.md and the
   live-check table above. Contract S6 has the same wording; the contract is left as
   approved and this note is the correction.
5. **The bad-mode test left half-built stacks in the shared test app** (Codex medium and
   `/code-review` 7; both families; the build flagged it). It now builds a fresh app and
   certificate stack per case. Its comment no longer says it reads `pa_config.json`.
6. **Production was not pinned to the custom policy** (contract verifier, low). The S1 test
   now checks, for both environments, that the behaviours reference the custom policy
   resource, instead of only "not the managed id".
7. **The docstring said report-only "records" violations** (`/code-review` 5). It now says
   the browser console shows them and there is no report collector.

Declined, with reasons:

- **HSTS `includeSubDomains` covers staging and any future name** (`/code-review` 2). Ruled
  at the contract gate after the DNS inventory; the security lane found no record the
  inventory missed; DEPLOYMENT.md warns against a plain-HTTP subdomain.
- **The CAPTCHA may need image, worker or WebAssembly sources** (`/code-review` 3). Already a
  known unverified item; the report-only pass is the check and adding a source is in scope.
- **The fixed policy name blocks a second stack in one account** (`/code-review` 4). Each
  environment has its own account; Codex confirmed a `csp_mode` switch is an in-place
  update, so the name never collides with itself.
- **Three extra whole-stack synths slow the tests** (`/code-review` 6). The infra suite runs
  in about 5 seconds; the whole-stack path is what the coupling and production checks need.
- **The Cognito domain is built by hand, not taken from `CognitoAuth`** (`/code-review` 8).
  `CognitoAuth.hosted_domain` is a deploy-time token the tests cannot compare; the coupling
  test keeps the two in step (Codex agreed).
- **The S1 test repeats a check in `test_synth.py`** (`/code-review` 9). The `test_synth.py`
  check is the replacement for the old pin (rubric 5); the S1 test covers production too.
  Small duplication, kept.
- **`test_s2_csp_sources_are_complete_and_safe` checks only the test's constants** (contract
  verifier, note). The S1 test's equality check ties them to the real output.

After the fixes: `make -C infra test` 134 passed; `ruff check` clean on the changed files;
`make okf-validate` 222 concepts, 0 violations. `make verify`: the first run failed one
backend test, `test_judge_commits.py::test_the_judge_writes_one_change_event_per_step`
(`links > 1`), a timing-sensitive theory-of-change test this slice does not touch; the
full backend suite then passed alone (4,831 passed, 1 skipped), and the next `make verify`
passed (exit 0; frontend 1,998, infra 134). The dry run above was taken before the review-stack changes; they
change only the policy's header values, so the same two slice lines are expected.

`/simplify` not run: `/code-review` ran its reuse, simplification and efficiency angles on
the same diff (findings 6, 8 and 9 above, all adjudicated), and a second same-family pass
adds little (task-cycle-review § Step 7).

Fake-done check on the fixes: no test deleted, skipped or loosened; the coupling test's
`frame-src` assertion was updated to the new value, not removed; the old "not the managed
id" check was replaced by a stronger Ref check.

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md) § Security headers (task 064c
seams): the enforce switch per environment, `'unsafe-inline'` styles, no report collector,
no automated browser check, no CSP on the ops pages or API responses, tokens in
`sessionStorage` with a 30-day refresh token.
