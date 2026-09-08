# Rubric: 042-citation-authors

The task is **done only if every box holds** — otherwise it is in progress,
not done. Item numbers 1–6 and decisions D1–D5 are defined in
[contract.md](contract.md).

1. [x] Implementation satisfies [contract.md](contract.md): items 1–6 all
       land; decisions D1–D5 hold as pinned.
2. [x] `make verify` passes (component commands — see the environment note in
       [verification.md](verification.md)); the pinned live check ran in the
       mock-mode app with notes and screenshots recorded (gap noted: seeded
       local-app pass left to the owner's environment).
3. [x] The OpenAPI diff is additive only (three `authorships` fields plus the
       `AuthorshipOut` schema; nothing removed or renamed); no other
       approval-gated change snuck in.
4. [x] `frontend/openapi.json` and `frontend/src/api/gen/types.ts` changed
       only via `make openapi-sync`; no generated files or secrets edited by
       hand.
5. [x] Every new author-string render path goes through `scrub()`; absence
       renders nothing (no empty separators or placeholders).
6. [x] No tests deleted, skipped or weakened without written justification.
7. [x] Verification evidence recorded ([verification.md](verification.md)).
8. [x] Deferred seams listed in docs/deferred.md: Overton snapshot backfill,
       `TopSource.authors`, institutions in the reference list.
9. [ ] Required review stack for Tier 3 ran as adjudicated at the contract
       gate (adversarial waived; standard stack pending — owner asked to open
       the PR after verification; run the stack against the PR in a fresh
       conversation), findings in [verification.md](verification.md).
