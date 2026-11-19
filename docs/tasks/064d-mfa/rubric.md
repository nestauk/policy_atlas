# Rubric: 064d-mfa

The slice is **done only if every box holds**. Problem numbers M1 and M3 to M6, P0, U1 to U6
and the terms are defined in [contract.md](contract.md).

1. [ ] Implementation satisfies [contract.md](contract.md): every row of § The problems has
       its "Required" column true in the code.
2. [ ] P0 ran before any product change; U2, U3, U4 and U6 are answered in the contract's
       § P0 results and ADR 0049; the throwaway pool is deleted.
3. [ ] `make verify` and `make -C infra test` pass; the staging live checks 1 to 7 pass and
       are recorded.
4. [ ] No approval-gated change beyond the contract's list: two `sign_in` keys, the Cognito
       settings, the branding files, the code email, the runbook. No plan change, no
       frontend, backend, dependency or deploy-script change.
5. [ ] A committed test compares the all-off user pool, client and domain (production's
       config) with a committed baseline taken from `dev` before the change, and they are
       equal.
6. [ ] Synth tests, each failing on the old code:
       - M1, one test per valid configuration (`mfa` off or `"email"` × `managed_login`
         off or on): with MFA on, `MfaConfiguration` is `ON` and `EnabledMfas` is exactly
         `["EMAIL_OTP"]`; in no configuration is there an SMS configuration, an SMS role or
         a `UserPoolTier` value.
       - M3: with MFA on, the recovery setting equals the one P0 chose; with MFA off it stays
         `EMAIL_ONLY`.
       - M4: managed login on sets `ManagedLoginVersion` 2 and exactly one branding style,
         for the SPA client, carrying the logo asset.
       - M5: with MFA on, the email MFA subject and body come from the template files; a body
         without `{####}` fails synth.
       - M6: an unknown key or value fails synth; `mfa` = `"email"` with pool email off fails
         synth; a missing `sign_in` block equals all-off.
7. [ ] No generated files or secrets edited by hand. No tests deleted, skipped or weakened
       without written justification.
8. [ ] Verification evidence recorded in [verification.md](verification.md), including
       screenshots of the page in light and dark mode and the owner's approval of the look.
9. [ ] Known gaps listed in [docs/deferred.md](../../deferred.md): production switch-on,
       threat protection, the custom sign-in address, a custom page if the wording is not
       acceptable; the MFA entry rewritten; the programme map marks review M-13 as partly
       closed.
10. [ ] ADR 0049 written and accepted; `infra/DEPLOYMENT.md` covers switch-on, the user
        warning, the one forced re-sign-in, code limits and lock-out, the reset path, rollback
        in its tested order with abort criteria, and the production prerequisites.
11. [ ] Required review stack for Tier 4 ran, or skipped with written justification.
