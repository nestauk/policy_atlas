# Implementation plan: 064d-mfa

> Status: **draft 2, 2026-11-19.** The owner pre-approved the plan with contract revision 2
> and asked for the build in the same conversation. Plan-stage adversarial review 2026-11-19
> (Codex, on draft 1 and contract revision 2; 7 findings, raw record in the gitignored
> `research/`), all folded into draft 2, no contract change: P0 runs as a throwaway CDK stack
> so every deploy step and rollback step is a real CloudFormation update (F1, F2, F3); exact
> branding assets after U4 with a test on them (F4); a P0 preflight (F5); local callback and
> logout URLs (F6); `add_property_override` for the code email (F7).
> Contract: [contract.md](contract.md) (revision 2). Rubric: [rubric.md](rubric.md).
> ADR: 0049 (written in Phase 3). Problems M1 and M3 to M6, P0, U1 to U6 and the terms are
> defined in the contract and not restated here. Executor routing follows
> `docs/agentic-ops/harness.md` § Agent-side model routing.

## Order and why

P0 comes first because its answers (U2 recovery, U4 branding, U6 frontend) decide the code,
and three of its outcomes are stop conditions. P0 runs before any product edit. Then one
infra phase: the `CognitoAuth` construct, its config keys and the synth tests, because the
tests are the only proof before a deploy. The all-off baseline is captured **before** the
construct changes, from the untouched code. Then the documents. A `cdk diff` dry run against
both accounts gates the push: production must show no Cognito change, staging must show only
the expected ones (in 064b a dry run caught what synth and review missed).

## Decisions taken in this plan

| # | Problem | Decision |
|---|---|---|
| D1 | P0 | **A throwaway CDK app** in the scratchpad (never committed) with one stack `Pa064dP0` in the staging account. Its pool copies `CognitoAuth`'s settings (Essentials, email through the staging SES identity `v3.policyatlas.uk` in DEVELOPER mode, `EMAIL_ONLY` recovery, same password policy), one public client with the SPA client's OAuth settings and both callback **and** logout URLs `http://localhost:5173` and `http://localhost:5173/`, and a prefix domain. `RemovalPolicy.DESTROY`, no deletion protection. **Preflight** (read-only, before any create): the caller identity is the staging account; `aws sesv2 get-email-identity` shows `v3.policyatlas.uk` verified in eu-west-2; the CDK bootstrap stack exists. A failure here stops P0 and is not read as a product result. **Stages**, each one `cdk deploy` (a real CloudFormation update) with its events saved: **A** today's shape (classic, MFA off). **B** the switch-on in one deploy: `mfa` email + recovery candidate + managed login + branding (U2, U4 through the real L1 resource, and the order CloudFormation uses for the domain and branding, F3). For U2, B is tried with each recovery candidate in turn (`EMAIL_ONLY`, `EMAIL_AND_PHONE_WITHOUT_MFA`, `NONE`) until one deploys **and** lets a test user sign in with a code and reset their own password on the hosted page. **C** rollback step "branding off": classic page with MFA still on: does the classic page show the code step (F1)? **D** rollback "MFA off": from B straight to MFA off + `EMAIL_ONLY` in one deploy: does it apply, and do password sign-in and self-service reset work after it (F2)? U3 on stage B: `admin-create-user` a test user, first sign-in (temporary password, new password, code); then `admin-set-user-password --no-permanent` on a never-signed-in user and sign in. U6 on stage A then B: the frontend run locally (`pnpm dev`) with `VITE_OIDC_AUTHORITY`, `VITE_OIDC_CLIENT_ID` and `VITE_OIDC_REDIRECT_URI=http://localhost:5173` pointed at the throwaway pool: sign-in, a forced silent refresh, sign-out, a new tab within the hour; a session opened on A is refreshed after B is deployed. Test addresses: the owner's choice, read by the owner. End: `cdk destroy`, then confirm the pool is gone. Notes in `research/p0-results.md`; summary into the contract. |
| D2 | M6 | **Baseline first.** Before touching the construct, a test helper renders the user pool, client and domain resources of the production-config stack (`PROD_APP_STACK` in `test_synth.py`) and writes them to `infra/tests/unit/fixtures/cognito_all_off.json` (one-off generation, then committed). The test `test_m6_all_off_cognito_resources_equal_baseline` compares the current rendering with that file by exact JSON equality (logical ids and properties). |
| D3 | M6 | Config shape: `policy_atlas_config.sign_in = {"mfa": "off" \| "email", "managed_login": false \| true}`. Read in `policy_atlas_stack.py` at the `CognitoAuth` call (`pa_app_config.get("sign_in")`) and passed as one `sign_in: dict \| None` argument. Validated inside `CognitoAuth` (the 064c pattern: the component raises `ValueError`): unknown key, unknown value, or `mfa` = `"email"` with `email.enabled` false. Missing block = `{"mfa": "off", "managed_login": False}`. |
| D4 | M1, M3, M5 | Only when `mfa == "email"`, add to the `cognito.UserPool(...)` kwargs: `mfa=cognito.Mfa.REQUIRED`, `mfa_second_factor=cognito.MfaSecondFactor(sms=False, otp=False, email=True)`, and `account_recovery=<P0 result>` (replacing `EMAIL_ONLY` in that branch only). After the pool is built, `self.user_pool.node.default_child.add_property_override("EmailAuthenticationSubject", ...)` and `("EmailAuthenticationMessage", ...)` (CDK 2.261 L2 has no prop for them; the L1 `CfnUserPool` has both, checked 2026-11-19). The MFA-on tests assert both rendered fields. The body is read by `_read_email_template("mfa-code.html", required_placeholders=("{####}",))`, reusing the existing check, and rendered through the same `__LOGO_URL__` replacement as the invitation. No `feature_plan` is passed in any branch (both pools are Essentials; passing it would change the all-off template). |
| D5 | M4 | Only when `managed_login` is true: `managed_login_version=cognito.ManagedLoginVersion.NEWER_MANAGED_LOGIN` on the existing `UserPoolDomain`, and one `cognito.CfnManagedLoginBranding(self, "ManagedLoginBranding", user_pool_id=..., client_id=self.client.user_pool_client_id, settings=<json.load of infra/branding/settings.json>, assets=[<logo>, <favicon>])`. Asset bytes are read from `infra/branding/` and base64-encoded at synth into `CfnManagedLoginBranding.AssetTypeProperty(category=..., color_mode=..., extension=..., bytes=...)`, one per committed file. Exact categories, colour modes, extensions, the settings document and any dependency order (F3) come from P0 U4 and stage B's events; this row is amended with them before Phase 3, and a test asserts each rendered asset's fields and any `DependsOn`. Classic stays the default (no `managed_login_version` passed when off, for the M6 baseline). |
| D6 | M5 | New `infra/email/mfa-code.subject.txt` and `infra/email/mfa-code.html`, copied in structure from `verification.html` (same header, logo, footer), with the code `{####}` and one line saying the code is for signing in to Policy Atlas and to ignore the email if they did not just sign in. Copy is lead-written. |
| D7 | M6 | `infra/pa_config.json`: staging `"sign_in": {"mfa": "email", "managed_login": true}`; production gets **no** `sign_in` block (all-off by absence, so its config diff is nil). |
| D8 | Tests | New `infra/tests/unit/test_sign_in.py`. Stacks built the `test_synth.py` way (copy `PA_CONFIG`, set `sign_in`, build `PolicyAtlasStack`), one per configuration in the rubric's grid (four), plus the failing configs as `pytest.raises(ValueError)`. Asserts per rubric item 6. The SMS check is a scan of all four templates for `SmsConfiguration`, `SMS_MFA` and an IAM role trusted by `cognito-idp.amazonaws.com`. The `{####}` check patches the template file path to a temp file without it. |
| D9 | Docs | `infra/DEPLOYMENT.md` new § "Sign-in: email codes and the branded page" (switch-on order, the user warning text, the forced re-sign-in, code limits and lock-out with the help step, reset path, rollback order with abort criteria and an operator sign-in check after each step, production prerequisites). Rollback order: taken from P0 stages C and D. If C works, branding can be rolled back alone; if not, the runbook says MFA off first (stage D), or both in one deploy, never branding alone. Each step ends with an operator sign-in check and has an abort criterion (sign-in page unavailable, or a test user cannot sign in). ADR 0049. `docs/deferred.md`: rewrite the MFA entry; add production switch-on, threat protection, custom address, custom page. Programme map 064d paragraph: as built, M-13 partly closed. |
| D10 | Reuse | No new module: the change lives in `cognito_auth.py` (reuses `_read_email_template`, `_email_templates`' replacement map) and its call site. No new helper outside it except the base64 asset reader, a three-line local function. |

## Phases

| Phase | Problems | Work | Executor | Gate |
|---|---|---|---|---|
| 0 | — | Build-open baseline: `make verify`, `make -C infra test` on the branch as it is. | lead | full verify |
| 1 | P0 | D1. Answers U2, U3, U4, U6 into `research/p0-results.md` and the contract's § P0 results. Stop and report to the owner if a stop condition fires. Owner reads the code emails and looks at the branded page. | lead (AWS CLI and browser need the owner in the loop) | P0 record complete; throwaway pool deleted |
| 2 | M6 baseline | D2: write the fixture from the untouched code; add the equality test; it passes. Commit. | lead | `make -C infra test` |
| 3 | M1, M3 to M6 | D3 to D8: construct, config, email template, branding files, tests. | `deep-reasoner` with this plan and the P0 results as the brief; lead writes D6 copy and picks branding values with the owner | `make -C infra test`; `make verify-fast` |
| 4 | docs | D9 and ADR 0049. | lead | `make verify-fast` |
| 5 | dry run | `cdk diff` against staging and production (read-only, the 064c command). Production: no Cognito change. Staging: only the D4/D5 changes. Recorded in `verification.md`. | lead | dry run clean |
| 6 | exit | Full `make verify` + `make -C infra test` + `make audit`; `verification.md` complete (live checks listed as pending until the owner deploys staging). | lead | full verify |

The staging live checks run after the owner deploys staging; they are recorded in
`verification.md` before the PR leaves draft.

## Risks

- **The CDK L1 escape hatch** for the email MFA message is set after construction; a CDK
  upgrade that adds an L2 prop could conflict. The test pins the rendered properties.
- **Branding settings JSON is unpublished as a schema.** P0 exports it from the editor and the
  same document is committed; a later AWS change could reject it on deploy. The dry run does
  not validate it (CloudFormation validates at deploy), so the first staging deploy is the
  real check, with branding rollback as step 1.
- **Lock-out at switch-on:** if the U2 result is wrong in the live pool, every user fails
  sign-in. Mitigation: staging only, testers warned, both rollback steps run as real deploys
  in P0 (stages C and D).
- **The live pool differs from the throwaway pool** (26 real users, existing sessions and
  refresh tokens). P0 covers a session carried across the switch; anything else surfaces at
  the staging deploy, with testers warned.
