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
| App | `[~]` ops task role policy: `cognito-idp:AdminDeleteSoftwareToken` added | yes (M3) |
| App | `[+]` security headers policy; `[~]` frontend distribution | **064c, not this slice**: 064c (PR #130) is not deployed to staging yet, and this branch is cut from it |
| App | `[~]` ingest Lambda, three task definitions "replace", export reader | the backend image hash and cross-region reader, as in every branch dry run (064c verification note) |

The record's alias reads the custom domain's CloudFront name with `Fn::GetAtt` (checked in
the synthesized template); there is no helper Lambda.

**Production dry run: not run** (no production access in this session). The committed test
`test_m6_production_sign_in_resources_equal_baseline` is the evidence that production's
pool, client, domain, DNS records, CSP and cert stack are unchanged. Someone with production
access can confirm with the command above using `AWS_PROFILE=pa-prod` and
`-c env_name=prod`; expected: no Cognito, certificate, DNS or CSP lines.

## Staging live checks

Pending the owner's staging deploy (contract § Acceptance checks, 1 to 8). Order: merge or
deploy 064c first (this branch carries it), DNS preflight (done 2026-11-19: no `auth.` or
wildcard record), user warning, deploy, checks.

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
  of Cognito addresses; the ops role gains one Cognito action.
- `infra/pa_config.json`: staging gets the block; production none.
- `backend/.../ops/commands.py`, `cli.py`: `user reset-app` (sign-out, then unlink; audit row
  in `_run` with the verified caller); the account lookup shared with `user deactivate`
  (`_resolve_account`). boto3 1.44.7 / botocore 1.44.7 locked.
- Docs: ADR 0049, `infra/DEPLOYMENT.md` § Sign-in, `infra/branding/README.md`,
  `docs/deferred.md`, the programme map, `infra/README.md`.

### Decisions made during the build (within the contract)

- `user reset-app` refuses a deactivated person using the same test as `user reactivate`:
  the database mark, or the account disabled in Cognito (one extra read-only `AdminGetUser`,
  a permission the ops role already has).
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

## Review findings

_After the review stack._

## Rubric status

_After the review stack._
