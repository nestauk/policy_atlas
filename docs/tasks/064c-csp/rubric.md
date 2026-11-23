# Rubric: 064c-csp

The slice is **done only if every box holds**. Problem numbers S1 to S6 and the terms are
defined in [contract.md](contract.md).

1. [ ] Implementation satisfies [contract.md](contract.md): every row of § The problems has
       its "Required" column true in the code.
2. [ ] `make verify` and `make -C infra test` pass; the
       staging live checks pass and are recorded (report-only pass, enforce pass, full-chain
       smoke), with the production steps recorded as done or pending.
3. [ ] No approval-gated change beyond the contract's list: one config key in both
       environments, one custom response headers policy per account attached to both
       behaviours, the deployment notes. No frontend code and no deploy-script change.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification. The managed
       policy id pin is replaced by the S5 assertions, not dropped.
6. [ ] One test per problem exists and fails on the old code: S1 both behaviours use the
       custom policy, the five kept headers keep their values and override flags, HSTS has
       `includeSubDomains` and no `preload`; S2 the CSP string equals the expected string for each environment,
       contains no `'unsafe-inline'` or `'unsafe-eval'` in `script-src`, includes
       `https://*.awswaf.com` exactly when `backend.waf.captcha` is true, and is at most
       1,783 characters, and lists the Cognito hosted domain in `frame-src`; S3 `report-only` sends only the custom report-only header,
       `enforce` only the built-in CSP header, each new header has override on, and a missing
       or unknown `csp_mode` fails synth; S4 the Permissions-Policy value.
7. [ ] Verification evidence recorded in [verification.md](verification.md): `curl` header
       output for `/`, `/index.html` and a deep link in both modes, and the manual-pass
       notes for each pass, each starting with the recorded console line of the deliberate
       violation.
8. [ ] Known gaps listed in [docs/deferred.md](../../deferred.md): `'unsafe-inline'`
       styles, no report collector, no automated browser check, no CSP on the ops pages
       or API responses, the refresh-token lifetime.
9. [ ] ADR 0048 written and accepted; `infra/DEPLOYMENT.md` § Security headers documents
       the policy and its sources, `csp_mode`, the manual pass, the switch to enforce, how
       to add a source, rollback, and the HSTS subdomain note; the programme map's 064c
       paragraph is corrected.
10. [ ] Required review stack for Tier 4 ran, or skipped with written justification.
