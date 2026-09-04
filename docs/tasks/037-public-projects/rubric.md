# Rubric: 037-public-projects

The task is **done only if every box holds** — otherwise it is in progress,
not done. Requirement ids (R1–R5) and design decisions (D1–D6) are defined
in [contract.md](contract.md); this file does not restate them.

1. [ ] Implementation satisfies [contract.md](contract.md) — R1 through R5
       each hold with the tests named in § Acceptance checks.
2. [ ] `make verify` passes; the declared manual browser check passed and
       is recorded.
3. [ ] No approval-gated change snuck in beyond the three the contract
       approves (one column · the 11-route public read surface · the
       additive `is_public` field).
4. [ ] No generated files or secrets edited by hand (`api/gen/types.ts`
       regenerated via `pnpm gen` only).
5. [ ] No tests deleted, skipped or weakened without written justification —
       the conformance allowlist and 404-sweep were **widened
       deliberately**, with the conditionally-public class asserted, never
       loosened.
6. [ ] Verification evidence recorded ([verification.md](verification.md)).
7. [ ] Known gaps and deferred seams listed (mock-API public mode; any
       held-back excerpt routes if the owner rules against the default) —
       gap → [docs/deferred.md](../../deferred.md), and the discharged
       "read-only/public links" line updated there.
8. [ ] The Tier-3 review stack ran (contract verifier · code review ·
       security review on the access-layer diff · adversarial review ·
       simplification), or a skip is justified in writing — findings in
       [verification.md](verification.md).
9. [ ] Boundary checks hold: every route outside the public surface still
       401s without a token; anonymous 404 bodies for private, archived and
       unknown Tasks are byte-identical; listings, the portfolio
       invariant (i.1–i.6) and the admin trace are untouched by the flag.
10. [ ] The redacted shape with `access = "public"` (D5) holds on every
       public-leg read; any present `Authorization` header that does not
       authenticate — bad token, expired, wrong scheme, malformed — still
       401s (D2); and the public view issues only public-surface requests
       (no conversations, SSE or decisions calls from the two tabs).
