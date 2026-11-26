# Rubric: 064d-mfa

The slice is **done only if every box holds**. Problem numbers M1, M3, M4, M6 and M7, P0,
U1 to U7 and the terms are defined in [contract.md](contract.md) (revision 3).

1. [ ] Implementation satisfies [contract.md](contract.md): every row of § The problems has
       its "Required" column true in the code.
2. [ ] P0 and P0b are summarised in the contract and ADR 0049; every throwaway stack is
       destroyed.
3. [ ] `make verify` and `make -C infra test` pass; the dry runs are recorded; the staging
       live checks 1 to 8 pass and are recorded.
4. [ ] No approval-gated change beyond the contract's list: the `sign_in` block, the Cognito
       settings, branding files, the custom domain with its certificate and record, the CSP
       source, `user reset-app` with one IAM action, boto3 and boto3-stubs ≥ 1.44.6. No plan
       change, no frontend change, no schema change.
5. [ ] A committed test compares the production-config stacks (pool, client, domain, the
       certificate stack, the CSP string) with a committed baseline taken before the change,
       and they are equal.
6. [ ] Tests, each failing on the old code:
       - M1, for `mfa` `"app"` with `page` `"managed"` and `"classic"`: `MfaConfiguration` is
         `ON`, `EnabledMfas` is exactly `["SOFTWARE_TOKEN_MFA"]`, recovery is `EMAIL_ONLY`;
         in no configuration is there an SMS configuration, an SMS role, `EMAIL_OTP` or a
         `UserPoolTier` value.
       - M3: `user reset-app` calls `AdminDeleteSoftwareToken` and `AdminUserGlobalSignOut`
         for the right username and writes one `ops_action` row; it refuses an unknown
         address and a deactivated account and calls nothing; the ops role holds
         `cognito-idp:AdminDeleteSoftwareToken` on the pool ARN.
       - M4: `page` `"managed"` sets `ManagedLoginVersion` 2 on every domain and one branding
         style for the SPA client whose assets match the committed files (category, colour
         mode, extension); `page` `"classic"` sets version 1 on every domain and no branding.
       - M4, M7: `domain` set adds a custom domain on that name, a us-east-1 certificate for
         it, an alias record, and the CSP lists it in `connect-src` and `frame-src`.
       - M6: an unknown key or value fails synth; a `domain` other than `auth.<domain_name>`
         fails synth.
7. [ ] No generated files or secrets edited by hand. No tests deleted, skipped or weakened
       without written justification.
8. [ ] Verification evidence recorded in [verification.md](verification.md), including
       screenshots in light and dark mode and the owner's approval of the look.
9. [ ] Known gaps listed in [docs/deferred.md](../../deferred.md): production switch-on,
       threat protection, a custom sign-in page for the wording, `reset-app` on the ops
       pages, retiring the prefix address; the MFA entry rewritten; the programme map's 064d
       paragraph as built (app codes, not email; M-13 partly closed).
10. [ ] ADR 0049 written and accepted; `infra/DEPLOYMENT.md` covers the user warning,
        switch-on and its timing, the phase-in, a lost phone, rollback in its tested order
        with abort criteria, and the production prerequisites.
11. [ ] Required review stack for Tier 4 ran, or skipped with written justification.
