# Rubric: 019-folding-pass

Core completion criteria for medium/high-risk slices.
The task is **done only if every box holds** — otherwise it is in progress, not done.

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

Slice-specific (from the contract):

9. [ ] Every gate decision (coverage-grain CHECK migration · `is_retracted` screening
       eligibility · rename persisted-vocabulary handling, migration vs read-alias)
       carries recorded owner approval — none inherited nor implied.
10. [ ] Planner capability-line change is lead-authored and replay-evidenced on planner
        probes, including one honest-decline case; evidence in verification.md.
11. [ ] Allowlists and group-membership tables are static, provenance-stamped, and
        fail-closed (invalid input rejects; nothing silently returns zero results).
12. [ ] D1 rider: `TIME_BANDS` re-seed traces to the one measured composed standard run;
        the `$` verdict and band-target verdict are recorded in 018's verification.md
        (§ Phase log D1 + § Review handoff); no additional e2e runs were spent.
