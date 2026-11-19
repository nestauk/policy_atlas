# Implementation plan: 064d-mfa

> Status: **draft 3, 2026-11-19**, rewritten for contract revision 3 after P0 and P0b.
> Draft 2 folded the Codex plan-stage review (F1 to F7); its P0 design ran as planned (a
> throwaway CDK stack per stage, real CloudFormation updates, rollback stages tested), and its
> lessons are kept below. Contract: [contract.md](contract.md) (revision 3). Rubric:
> [rubric.md](rubric.md). ADR: 0049 (Phase 5). Problems M1, M3, M4, M6, M7 and the terms are
> defined in the contract and not restated here. Executor routing follows
> `docs/agentic-ops/harness.md` § Agent-side model routing. Build-open baseline (Phase 0) ran
> green on 2026-11-19 (backend 4,973 passed, infra 148, frontend 2,025).

## Order and why

P0 is done, so the code shape is known. The all-off baseline is captured first, from the
untouched code, because every later phase must keep it. Then the infra change (M1, M4, M6,
M7), then the ops command with the dependency upgrade (M3; a backend and lockfile change, so
it gets its own full-verify gate), then the documents. A `cdk diff` dry run against both
accounts gates the push.

## Decisions taken in this plan

| # | Problem | Decision |
|---|---|---|
| D1 | M6 | **Baseline first.** A one-off script renders, from the production config, the `PaV3AppStack` resources of types `AWS::Cognito::UserPool`, `UserPoolClient`, `UserPoolDomain` and `ManagedLoginBranding`, the whole `PaV3CertStack` template, and the CSP string; writes them as canonical JSON to `infra/tests/unit/fixtures/sign_in_all_off.json`. Test `test_m6_production_sign_in_resources_equal_baseline` re-renders and compares by exact equality. Generated before any construct edit, then committed. |
| D2 | M6 | Config: `policy_atlas_config.sign_in = {"mfa": "off" \| "app", "page": "classic" \| "managed", "domain": "auth.<domain_name>"}`, every key optional inside the block, absent block = nothing emitted. Validation inside `CognitoAuth` (the 064c pattern, `ValueError`): unknown key or value; `domain` not equal to `f"auth.{domain_name}"`. Staging gets `{"mfa": "app", "page": "managed", "domain": "auth.v3.policyatlas.uk"}`; production gets no block. |
| D3 | M1 | `mfa == "app"`: `mfa=cognito.Mfa.REQUIRED`, `mfa_second_factor=cognito.MfaSecondFactor(sms=False, otp=True, email=False)`. `mfa == "off"`: `mfa=cognito.Mfa.OFF` named explicitly (the rollback; CDK omits SMS and roles for OFF). `account_recovery` stays `EMAIL_ONLY` in every branch. No `feature_plan` anywhere. |
| D4 | M4 | `page == "managed"`: `managed_login_version=NEWER_MANAGED_LOGIN` on every `UserPoolDomain` of the pool, plus one `cognito.CfnManagedLoginBranding(self, "ManagedLoginBranding", user_pool_id=..., client_id=self.client.user_pool_client_id, settings=json.loads(settings.json), assets=[AssetTypeProperty(category, color_mode, extension, bytes=base64)])` with the asset list read from `infra/branding/assets.json` (the P0 shape: `PAGE_HEADER_LOGO` LIGHT and DARK, `FAVICON_SVG` LIGHT and DARK). `page == "classic"`: `CLASSIC_HOSTED_UI` named on every domain, no branding (P0: leaving it out keeps version 2). Absent: nothing passed. P0 showed no ordering problem between domain and branding, so no `DependsOn`. |
| D5 | M4 | `infra/branding/`: `settings.json`, `assets.json`, `wordmark-light.svg`, `wordmark-dark.svg`, `mark.svg` copied from the P0 `final/` folder the owner approved, plus `README.md` (what each file is, how the wordmark was outlined, that the font file is never committed, how to change a colour). The outlining script is not committed; the README records its steps. |
| D6 | M4, M7 | `domain` set: `PaV3CertStack` takes `auth_domain: str \| None` (read in `app.py` from `pa_config["policy_atlas_config"].get("sign_in", {}).get("domain")`) and, only when set, creates `acm.Certificate(self, "AuthCertificate", domain_name=auth_domain, validation=from_dns(hosted_zone))` as `self.auth_certificate` (else `None`). `PolicyAtlasStack` takes `auth_certificate` and passes it, with its existing `hosted_zone`, to `CognitoAuth`, which adds `UserPoolDomain(self, "CustomDomain", custom_domain=CustomDomainOptions(domain_name, certificate), managed_login_version=<as D4>)` and `r53.ARecord(..., target=RecordTarget.from_alias(UserPoolDomainTarget(custom)))`. `CognitoAuth` raises if `domain` is set and no certificate is given. The prefix domain stays (the CSP, SSM parameter and any old link keep working). |
| D7 | M7 | CSP: `SecurityHeaders` takes `cognito_hosted_domains: list[str]` in place of the single `cognito_hosted_domain`; the call site passes the prefix address, plus `https://auth.<domain_name>` when `sign_in.domain` is set. With one entry the string is the same as today (baseline D1 and the 064c literal tests prove it). The 064c tests are updated for the parameter name only, and a staging literal gains the new source. |
| D8 | M3 | Backend: `pyproject.toml` `boto3>=1.44.6,<2` and `boto3-stubs[cognito-idp,bedrock-runtime]>=1.44.6,<2`, `uv lock --upgrade-package boto3 --upgrade-package boto3-stubs` (and botocore, which moves with them). `commands.reset_authenticator_app(conn, cognito, *, pool_id, email \| sub, actor)` mirrors `deactivate_user`: resolve the account (`_find_user_by_email` or by sub), refuse when absent or when the person is deactivated (the same check `deactivate_user` uses), call `admin_delete_software_token` then `admin_user_global_sign_out`, write one `ops_action` row (`action="user.reset_app"`), return a `Record`. A Cognito `ClientError` becomes `OpsError` with nothing written. CLI: `user reset-app (--email E \| --sub SUB)` in `cli.py`, its help line and the module docstring's command list. Infra: `cognito-idp:AdminDeleteSoftwareToken` added to the ops task role's Cognito statement; `test_service_wiring.py`'s pinned list gains it. |
| D9 | Tests | `infra/tests/unit/test_sign_in.py`: stacks built the `test_synth.py` way for `{"mfa": "app", "page": "managed", "domain": ...}`, `{"mfa": "app", "page": "classic"}`, `{"mfa": "off", "page": "classic"}`, plus the failing configs; assertions per rubric item 6. The SMS scan covers every template. The staging fixtures in `test_synth.py` get a cert stack built with the auth domain. Backend: `tests/ops/` tests for `reset_authenticator_app` with a stubbed Cognito client (the existing pattern) and one CLI parse test. |
| D10 | Docs | `infra/DEPLOYMENT.md` new § "Sign-in: authenticator codes, branded page, own address": warning text, switch-on and timing, phase-in, `user reset-app`, rollback order (1: `page` `"classic"` alone is safe; 2: `mfa` `"off"`, one deploy; 3: removing `domain` deletes the custom domain and record, so set `page`/`mfa` first; each followed by an operator sign-in; abort if the page is unreachable or a test user cannot sign in), production prerequisites. ADR 0049. `docs/deferred.md` per contract. Programme map 064d paragraph. `infra/README.md` gains `branding/`. Knowledge bundle: sign-in facts from P0. |
| D11 | Reuse | No new module. Reused: `_read_email_template`'s pattern for file reads, `deactivate_user`'s resolve/refuse/audit shape, the 064c validation pattern, the cert stack's DNS validation, the test fixtures' config-copy pattern. New: one base64 asset reader inside `cognito_auth.py`. |

## Phases

| Phase | Problems | Work | Executor | Gate |
|---|---|---|---|---|
| 0 | — | Build-open baseline. **Done** 2026-11-19, green. | lead | full verify |
| 1 | — | P0 and P0b. **Done**; throwaway stacks destroyed (P0b teardown after the SSO login). | lead + owner | records complete |
| 2 | M6 | D1: baseline fixture from untouched code, equality test passes. Commit. | lead | `make -C infra test` |
| 3 | M1, M4, M6, M7 | D2 to D7, D9 infra tests, D5 files. | `deep-reasoner` (brief: this plan, contract, P0 results); lead reviews | `make -C infra test`, `make verify-fast` |
| 4 | M3 | D8 and its tests. | `deep-reasoner`; lead reviews | full `make verify` (lockfile change) |
| 5 | docs | D10, ADR 0049. | lead | `make verify-fast` |
| 6 | dry run | `cdk diff` both accounts (read-only): production no change to Cognito, cert stack or CSP; staging the D3 to D7 changes. Recorded. | lead | dry run clean |
| 7 | exit | Full `make verify` + `make -C infra test` + `make audit`; `verification.md` with live checks pending the owner's staging deploy. | lead | full verify |

## Risks

- **The custom domain's first deploy takes about 8 minutes** and adds a us-east-1 resource to
  the cert stack, which the app stack reads through a cross-region reference. A failed deploy
  rolls back; the runbook says to deploy outside working hours.
- **Rollback trap** (P0): leaving out `ManagedLoginVersion` keeps version 2 with no branding.
  D4 names version 1 for `"classic"`; a test pins it.
- **boto3 upgrade** touches every AWS call in the backend (Bedrock, SES, S3). The full
  `make verify` gate in Phase 4 and the full-chain smoke cover the paths we use.
- **The 30-day phase-in** means admin accounts may keep a session without a code for up to 30
  days. Accepted by the owner; the runbook says an admin can sign out and in to enrol at once.
