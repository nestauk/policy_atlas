# Rubric: 031-search-count-honesty

Core completion criteria for medium/high-risk slices. The task is **done only if
every box holds** — otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes; declared manual/eval checks pass.
3. [ ] No approval-gated change snuck in unapproved — schema, auth/tenancy, egress, deps, CI,
       production config, public interfaces, scaffold (see the contract).
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md) or PR).
7. [ ] Known gaps and deferred seams listed (gap → [docs/deferred.md](../../deferred.md)).
8. [ ] Required review stack ran for the risk tier (contract verifier · code/security review ·
       adversarial where tiered · simplification), or skipped with written justification — findings
       in [verification.md](verification.md).

## Slice-specific

9. [ ] P1 check-in: with `acquired > 0`, backend counts are not all zero; they sum to `acquired`
      for that acquire run; listed queries belong to that run only.
10. [ ] Where I looked: per-backend `results` aggregates query hits across all acquire rounds;
      `relevant` remains unique project-wide per backend; UI copy does not claim a false
      subset relation.
11. [ ] Geography chart: known countries + "Not reported" = landscape's screened-in
      (relevant) population; authorship countries are not used as publisher country.
12. [ ] Funnel totals and plan-in-motion screen summaries are unchanged.
13. [ ] Multi-round (standard or deep) fixture or test covers invariants 9–10; rapid path
      still correct for the P1 zero-count fix.
14. [ ] `docs/deferred.md` no longer lists last-round-only Where I looked / P1 coverage as an
      accepted blemish (or rewrites it to the remaining true remainder).
