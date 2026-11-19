# Rubric: 064d-mfa

The slice is **done only if every box holds**. Problem numbers M1 to M6, P0, U1 to U6 and the
terms are defined in [contract.md](contract.md).

1. [ ] Implementation satisfies [contract.md](contract.md): every row of § The problems has
       its "Required" column true in the code.
2. [ ] P0 ran before any product change; U1 to U6 are answered in the contract's § P0 results
       and ADR 0049; the throwaway pool is deleted.
3. [ ] `make verify` and `make -C infra test` pass; the staging live checks 1 to 8 pass and are
       recorded; check 9 is recorded as done or as a deferred entry.
4. [ ] No approval-gated change beyond the contract's list: three `sign_in` keys, the Cognito
       settings, the branding files, the code email, the runbook. No frontend, backend,
       dependency or deploy-script change.
5. [ ] With every `sign_in` key off (production), the synthesised user pool, client and domain
       are identical to today's.
6. [ ] One test per problem exists and fails on the old code: M1 `EnabledMfas` is exactly
       `["EMAIL_OTP"]` with MFA on, and no SMS role or SMS configuration exists in any mode;
       M2 each threat protection value maps to its mode and any value but `"off"` sets Plus;
       M3 email MFA on never synthesises `EMAIL_ONLY` recovery; M4 managed login sets version 2
       and a branding style for the SPA client; M5 the code email template is used and a
       template without `{####}` fails synth; M6 an unknown key value fails synth and a
       missing `sign_in` block means all off.
7. [ ] No generated files or secrets edited by hand. No tests deleted, skipped or weakened
       without written justification.
8. [ ] Verification evidence recorded in [verification.md](verification.md), including the
       production synth diff, screenshots of the page in light and dark mode, and the owner's
       approval of the look.
9. [ ] Known gaps listed in [docs/deferred.md](../../deferred.md): production switch-on, the
       custom sign-in address, a custom page if the wording is not acceptable, and the MFA entry
       rewritten.
10. [ ] ADR 0049 written and accepted; `infra/DEPLOYMENT.md` covers switch-on, the user
        warning, the one forced re-sign-in, audit to full, the reset path, rollback in its
        safe order, and the production prerequisites (email on, U1 plan check).
11. [ ] Required review stack for Tier 4 ran, or skipped with written justification.
