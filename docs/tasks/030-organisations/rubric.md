# Rubric: 030-organisations

The task is **done only if every box holds** — otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes; `make drift-check` green; declared manual/live checks pass
       per the contract's live-check scope pin.
3. [ ] No approval-gated change snuck in unapproved — the schema/auth/API changes land
       exactly as contracted; no roles, IdP, or infra change rode along.
4. [ ] No generated files or secrets edited by hand (`openapi.json`/`gen/types.ts` only
       via `make openapi-sync`).
5. [ ] No tests deleted, skipped or weakened without written justification — in
       particular the existing cross-owner 404 suite stands unmodified.
6. [ ] Verification evidence recorded ([verification.md](verification.md)).
7. [ ] Known gaps and deferred seams listed (gap → [docs/deferred.md](../../deferred.md)),
       including every contract Out item touched in passing.
8. [ ] Required Tier-4 review stack ran (contract verifier · code review · security lane ·
       adversarial · simplification), or skipped with written justification — findings in
       [verification.md](verification.md).
9. [ ] **Tenancy matrix holds:** same-org read 200 · same-org write 403 `forbidden` ·
       cross-org and not-visible 404 (indistinguishable body) · `private` hidden from org
       listings and direct GET · own-chats isolation both directions · pending-turn cap
       keyed to the acting user — each pinned by a named test.
10. [ ] **Every project-scoped route** (12 read models, SSE, runs, planning, check-ins,
        conversations ×6 former inline sites) resolves access through the single helper —
        no residual inline `owner_user_id` filter outside it.
11. [ ] Dark-launch invariant: with zero orgs/enrolments the API behaviour and frontend
        are observably unchanged for existing users (pinned by test or live check).
12. [ ] Migration up/down roundtrip green on the scratch-DB pattern, `created_by`
        backfill correctness asserted; downgrade restores the pre-030 schema.
13. [ ] Auth dependency (`get_current_user`) remains DB-free (asserted structurally —
        no Connection dependency creep).
14. [ ] Spec flow-back landed: `web-api.md` auth boundary + resources updated; ADR 0030
        Accepted; AGENTS.md phase pointer current.
