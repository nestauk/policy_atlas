# Rubric: 038-apo-mod

The task is **done only if every box holds** — otherwise it is in progress.

1. [ ] Implementation satisfies [contract.md](contract.md) — R1 (no OpenAlex
       calls), R2 (`source=apo` on every Overton call), R3 (the restriction is
       visible on the plan document).
2. [ ] `make verify` passes; the pinned live manual check ran with evidence
       (request URL, sample result).
3. [ ] No approval-gated change beyond the contract — no prompt change, no
       schema, no deps, no CI, no other egress change.
4. [ ] `openapi.json` / `types.ts` regenerated via `make openapi-sync`, never
       edited by hand.
5. [ ] The Overton allowlists gained exactly one key each (`publisher_source`
       directive key, `source` wire key) — nothing else widened.
6. [ ] APO token with Sources ≠ grey literature only returns 422 with a clear
       message.
7. [ ] No tests deleted, skipped or weakened without written justification.
8. [ ] Verification evidence recorded ([verification.md](verification.md)).
9. [ ] The removal note (stored plans carrying `publisher_source`) is in
       `docs/deferred.md`.
10. [ ] The Tier-3 review stack ran, or the owner's waiver is recorded in the
        contract and `verification.md`.
