# Verification: 064d-mfa

Evidence for task 064d (contract revision 3, plan draft 3). Problem numbers and terms are in
[contract.md](contract.md). Public-safe: no pool ids, passwords, codes or tokens.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (build-open, 2026-11-19) | pass | backend 4,973 passed, 1 skipped; infra 148; frontend 2,025 |
| `make -C infra test` (Phase 2, baseline) | pass | 149; the baseline fixture written from untouched code, then DNS records added before any infra edit (Codex F3) |
| `make -C infra test` (Phase 3) | pass | 165 (16 new) |
| `make -C backend verify-fast` (Phase 4) | pass | 4,941 passed, 1 skipped; mypy strict clean (575 files); ruff clean |
| `make verify` (after Phases 3 to 5, 2026-11-20) | pass | backend 4,979 passed, 1 skipped; infra 165; frontend 2,025; all lint, type, drift and guard checks |
| `make verify` (after the review fixes, 2026-11-20) | pass | infra 170; frontend 2,025 |
| `make verify` (rebased on `dev` at e9b491c6, 2026-11-20) | pass | backend 4,985 passed, 1 skipped; infra 170; frontend 2,025; audit-paths and rules-check 0 violations |

## P0 and P0b (live tests on throwaway pools, 2026-11-19)

Summarised in the contract's § P0 results and ADR 0049; detail in the gitignored
`research/p0-results.md`. Every throwaway stack (`Pa064dP0`, `Pa064dP0b`, `Pa064dP0bCert`)
was destroyed; the one DNS record CloudFormation left behind (the throwaway certificate's
validation CNAME) was deleted by hand on 2026-11-20, and the zone holds no `auth-p0` record.

## Dry run (Phase 6, 2026-11-20, commit 2bcf95ed)

Staging, from `infra/`, with the staging SSO session (the 064c command plus the ops
allowlist size and the cert stack):

```bash
export AWS_PROFILE=pa_staging \
  && export CDK_DEFAULT_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)" \
  && N=$(aws ssm get-parameter --region eu-west-2 --name /policy_atlas_v3/metabase/allowed_cidrs --query Parameter --output json | PYTHONPATH=. python3 -m infra.allowlist size) \
  && O=$(aws ssm get-parameter --region eu-west-2 --name /policy_atlas_v3/ops/allowed_cidrs --query Parameter --output json | PYTHONPATH=. python3 -m infra.allowlist size --label "ops allowlist") \
  && PATH=.venv/bin:$PATH npx cdk@2.1133.0 diff -c env_name=staging -c stage=all \
     -c metabase_allowlist_size="$N" -c ops_allowlist_size="$O" PaV3CertStack PaV3AppStack
```

Result: exit 0, two stacks with differences.

| Stack | Change | Expected? |
|---|---|---|
| Cert | `[+]` `AuthCertificate` | yes (M7) |
| Cert | `[~]` cross-region export writer "may be replaced": one export added (the new certificate's ARN) | yes: CDK's writer updates its export list |
| App | `[~]` user pool: `MfaConfiguration` ON, `EnabledMfas` `["SOFTWARE_TOKEN_MFA"]`; nothing else | yes (M1); no recovery, tier or SMS change |
| App | `[~]` prefix domain: `ManagedLoginVersion` 2 | yes (M4) |
| App | `[+]` custom domain, DNS record, branding | yes (M4, M7) |
| App | `[~]` ops task role policy: `cognito-idp:AdminDeleteSoftwareToken` added | yes at the time; **removed in the review stack** (the CLI runs on operator IAM), so a dry run after the review shows no IAM line |
| App | `[+]` security headers policy; `[~]` frontend distribution | **064c, not this slice**: 064c (PR #130, merged into `dev` 2026-11-19) was not yet deployed to staging when this ran |
| App | `[~]` ingest Lambda, three task definitions "replace", export reader | the backend image hash and cross-region reader, as in every branch dry run (064c verification note) |

The record's alias reads the custom domain's CloudFront name with `Fn::GetAtt` (checked in
the synthesized template); there is no helper Lambda.

**Rerun on the final branch** (2026-11-20, after the review fixes and the rebase on `dev`,
same command): exit 0, the same lines as above **except** the ops task role policy, which no
longer appears (the review moved that permission to the operator's IAM). The pool still gains
only `MfaConfiguration` ON and `EnabledMfas` `["SOFTWARE_TOKEN_MFA"]`; no IAM resource, no
`Custom::UserPoolCloudFrontDomainName` and no helper Lambda appear. The 064c headers policy
still shows as new: 064c is merged into `dev` but not yet deployed to staging, so the next
staging deploy carries both.

**Production dry run: not run** (no production access in this session). The committed test
`test_production_sign_in_resources_equal_baseline` is the evidence that production's
pool, client, domain, DNS records, CSP and cert stack are unchanged. Someone with production
access can confirm with the command above using `AWS_PROFILE=pa-prod` and
`-c env_name=prod`; expected: no Cognito, certificate, DNS or CSP lines.

## Staging live checks

Pending the owner's staging deploy (contract § Acceptance checks, 1 to 8). Order: DNS
preflight (done 2026-11-19: no `auth.` or wildcard record), user warning, deploy, checks.

| # | Check | Date | Result |
|---|---|---|---|
| 1 | Address `auth.v3.policyatlas.uk`, branded, light and dark | | |
| 2 | Open session continues; after sign-out: password, QR, code; entry named after our address | | |
| 3 | Invited user: temporary password, new password, QR, code | | |
| 4 | Forgot password by email | | |
| 5 | `user reset-app` on a test user, then QR at next sign-in; also on a user with no app linked | | |
| 6 | Ops pages sign-in | | |
| 7 | New tab within the hour silent; sign-out then password and code | | |
| 8 | One task run with its progress stream | | |

## Diff summary

- `infra/infra/cognito_auth.py`: the `sign_in` block (validated), MFA by authenticator app,
  managed login named on every domain, branding from `infra/branding/`, the custom domain
  and its DNS alias.
- `infra/infra/cert_stack.py`, `infra/app.py`: the us-east-1 certificate for the sign-in
  address, only when the block names one.
- `infra/infra/components/security_headers.py`, `policy_atlas_stack.py`: the CSP takes a list
  of Cognito addresses. The operator's IAM for the ops CLI gains one Cognito action
  (`infra/JUMPBOX.md`, `infra/DEPLOYMENT.md`); no ECS task role changes.
- `infra/pa_config.json`: staging gets the block; production none.
- `backend/.../ops/commands.py`, `cli.py`: `user reset-app` (sign-out, then unlink; audit row
  in `_run` with the verified caller, action `person.reset_app`; by `--email` it refuses
  unless Cognito still holds that address for the person); the account lookup shared with
  `user deactivate` (`_resolve_account`). boto3 1.44.7 / botocore 1.44.7 locked.
- Docs: ADR 0049, `infra/DEPLOYMENT.md` § Sign-in, `infra/branding/README.md`,
  `docs/deferred.md`, the programme map, `infra/README.md`.

### Decisions made during the build (within the contract)

- `user reset-app` refuses a deactivated person using the same test as `user reactivate`:
  the database mark, or the account disabled in Cognito (one extra read-only `AdminGetUser`,
  a permission the operator's IAM already has).
- With no account in the pool but a database row, `reset-app` refuses; `deactivate` still
  does its database half. Different on purpose: there is no app link to reset.
- The staging test fixtures get a second cert stack built with the auth domain; the
  production fixture and the baseline's cert stack are untouched.

## Known gaps

- Production dry run not run (above).
- What `AdminDeleteSoftwareToken` does for a person with no app linked is not tested (live
  check 5).
- Removing the custom domain (rollback step 3) is not tested.
- Deferred entries: production switch-on, threat protection, the page's wording, `reset-app`
  on the ops pages, retiring the prefix address (`docs/deferred.md`).

## Review findings (step 7, 2026-11-20)

Same conversation as the build, by owner ruling (contract Status). Scope:
`git diff 60b17e55..HEAD`, excluding the baseline fixture, the branding SVGs and `uv.lock`
(checked on their own: the fixture reproduces from pre-slice code; the lock moves only boto3,
botocore and their stubs). The code was written by Claude agents, so Codex anchors.

| Lane | Reviewer | Findings |
|---|---|---|
| Contract verifier | `contract-verifier` subagent | 11 |
| Adversarial | Codex (`codex-rescue`, read-only) | 3 |
| `/code-review` medium | Claude reviewers | 9 |
| Security | `/security-review` (the security-auditor agent is not installed here) | 0 at confidence ≥ 8 |
| Over-engineering | `ponytail-review` | 2 |

Adopted and fixed (commit 78de3bfb plus the ponytail shrink):

1. **Wrong person by a stale email** (Codex, high). `reset-app --email` now refuses unless
   Cognito's current address for that person is the one given. Test with a stale database
   address.
2. **`AdminDeleteSoftwareToken` on the internet-facing ops task role** (`/code-review`). The
   CLI runs on the operator's IAM and the ops pages have no reset button, so the permission
   moved to the operator lists in `infra/JUMPBOX.md` and `infra/DEPLOYMENT.md`. The contract's
   M3 row was wrong and is corrected.
3. **Tests asserted a helper Lambda the deploy never makes** (contract verifier, high, as
   "docs say no Lambda but code builds one"). Root cause: `cdk.json`'s
   `userPoolDomainNameMethodWithoutCustomResource` flag reaches a real synth but not a test's
   `cdk.App()`. The docs were right; the tests now load that flag and assert
   `Fn::GetAtt [CustomDomain, CloudFrontDistribution]` and no extra Lambda. Folded into the
   knowledge bundle.
4. **Rollback config untested** (contract verifier). New test: `page` classic with `domain`
   names version 1 on both domains (the reviewer's mutation, version 2 on the custom domain,
   now fails it).
5. **Contract ids in test names** (contract verifier). Renamed.
6. **Audit action name** (`/code-review`): `person.reset_app`, the `person.*` convention.
7. **Failure message claimed "still linked"** (`/code-review`): reworded; a person may never
   have linked an app.
8. **`sign_in` typing** (Codex, `/code-review`): only absent or `null` means no change;
   `false`, a list or a string fail synth. Tests.
9. **Two refusals untested** (contract verifier): a row with no pool account; a failing
   sign-out never unlinks. Tests.
10. **Overstated "production unchanged"** (contract verifier): the contract and ADR now name
    what the baseline compares.
11. **Docs**: knowledge record of the P0 facts (plan D10, which the build had dropped);
    "Task 064d" out of the branding README; ADR text confirmed by the owner 2026-11-20.
12. **ponytail**: the rerun sentence written directly instead of sliced.

Declined or deferred, with reasons:

- **No audit row if the database fails after Cognito acted** (Codex medium, `/code-review`).
  It applies to every ops command that changes Cognito, not only this one; deferred
  (`docs/deferred.md` § Accounts).
- **Cert zone not checked against `domain_name`** (`/code-review`): both environments use the
  same name in both config files; low.
- **A missing `page` key keeps version 2** (`/code-review`): deliberate, documented in the
  runbook and pinned by the classic test.
- **CSP builds the prefix address from config** (`/code-review`): the ADR 0048 decision
  (plain strings the tests can compare, with a coupling test).
- **`sign_in_block` runs at both the stack and the construct** (ponytail, borderline):
  `CognitoAuth` is a reusable construct and keeps its own check.
- **The production cert stack in the baseline is built from staging's network config**
  (contract verifier, low): it proves "no block, no change" for the cert stack; the
  production network config differs only in the domain name.
- **"Five wrong codes" in the runbook unsourced** (contract verifier, info): sourced in
  `research/cognito-facts.md` § 7 (AWS MFA page: "After five unsuccessful attempts … exponential-timeout lockout").
- **`infra/JUMPBOX.md` says no Cognito permission attaches to an ECS task role** (fix agent):
  untrue since the ops service (task 065); not this slice; left for the next docs sweep.

Convergent across families: `sign_in` typing (Codex and `/code-review`), the audit gap
(Codex and `/code-review`). Unique and decisive: the stale-email wrong person (Codex only),
the task-role over-grant (`/code-review` only), the test/deploy flag mismatch (contract
verifier only). Each lane justified itself.

Fake-done check on the fixes: no test deleted or loosened. The alias test was changed from
the custom-resource path to the deploy's path and made stricter (exact `GetAtt`, no extra
Lambda). The production baseline fixture was not regenerated after the infra change.

## Rubric status

| # | Status |
|---|---|
| 1 | Holds (the M3 IAM wording corrected in the contract). |
| 2 | Holds. |
| 3 | `make verify` green; staging dry run recorded; **staging live checks pending the owner's deploy**. |
| 4 | Holds after the review (one operator IAM action, not a task-role action). |
| 5 | Holds. |
| 6 | Holds, including the rollback configuration. |
| 7 | Holds. |
| 8 | **Pending**: staging screenshots and the owner's look approval on staging (approved on the throwaway pool). |
| 9 | Holds. |
| 10 | Holds; ADR text confirmed by the owner. |
| 11 | Holds (this section). |
