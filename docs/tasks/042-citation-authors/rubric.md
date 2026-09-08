# Rubric: 042-citation-authors

The task is **done only if every box holds** — otherwise it is in progress,
not done. Item numbers 1–6 and decisions D1–D5 are defined in
[contract.md](contract.md).

1. [ ] Implementation satisfies [contract.md](contract.md): items 1–6 all
       land; decisions D1–D5 hold as pinned.
2. [ ] `make verify` passes; the pinned live check ran with notes recorded.
3. [ ] The OpenAPI diff is additive only (three `authors` fields; nothing
       removed or renamed); no other approval-gated change snuck in.
4. [ ] `frontend/openapi.json` and `frontend/src/api/gen/types.ts` changed
       only via `make openapi-sync`; no generated files or secrets edited by
       hand.
5. [ ] Every new author-string render path goes through `scrub()`; absence
       renders nothing (no empty separators or placeholders).
6. [ ] No tests deleted, skipped or weakened without written justification.
7. [ ] Verification evidence recorded ([verification.md](verification.md)).
8. [ ] Deferred seams listed in docs/deferred.md: Overton snapshot backfill,
       `TopSource.authors`, institutions in the reference list.
9. [ ] Required review stack for Tier 3 ran as adjudicated at the contract
       gate (adversarial waived or run — record which), findings in
       [verification.md](verification.md).
