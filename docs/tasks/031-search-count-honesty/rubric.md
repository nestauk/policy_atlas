# Rubric: 031-search-count-honesty

These are the core completion criteria for a slice of medium risk or high risk.
The task is **done only if each box is true**. If one box is not true, the task
is in progress.

1. [ ] The implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes. The declared manual checks and eval checks pass.
3. [ ] No approval-gated change entered without approval. The gated items are the
       schema, auth and tenancy, egress, dependencies, CI, production config,
       public interfaces and the scaffold. See the contract.
4. [ ] Nobody edited a generated file or a secret by hand.
5. [ ] Nobody deleted, skipped or weakened a test without a written reason.
6. [ ] The verification evidence is recorded, in
       [verification.md](verification.md) or in the PR.
7. [ ] The known gaps and the deferred items are listed. Put each gap in
       [docs/deferred.md](../../deferred.md).
8. [ ] The review stack for the risk tier ran: the contract verifier, the code
       review and the security review, the adversarial review where the tier needs
       it, and the simplification review. If a review was skipped, the reason is
       written down. The findings are in [verification.md](verification.md).

## Slice-specific

The defect numbers are in [contract.md](contract.md) § Audit. That document also
defines the terms and the screens.

9. [ ] P1 check-in, defects 1a and 1b: when `acquired` is more than 0, the
       backend counts are not all zero. They add up to `acquired` for that
       acquire run. The listed queries belong to that run only.
10. [ ] Where I looked, defect 2: `results` for each backend adds up the query
       hits across all the acquire rounds. `relevant` stays the unique
       project-wide count for each backend. The UI copy states no false subset
       relation.
11. [ ] Geography chart, defect 3: the known countries plus "Not reported" are
       equal to the population that the chart draws. At the default scope that is
       the funnel `relevant` count. At `scope="cited"` it is the cited count, and
       a test covers that case. The code does not use an authorship country as the
       publisher country.
12. [ ] The funnel totals and the plan-in-motion screen summaries are unchanged.
13. [ ] A fixture or a test with more than one round, at standard depth or deep
       depth, covers items 9 and 10. The rapid path is still correct after the
       fix to defect 1a.
14. [ ] `docs/deferred.md` no longer lists the last-round-only coverage of Where I
       looked and of P1 as an accepted defect. If some part of the defect remains,
       the entry describes only that part.
