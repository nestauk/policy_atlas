# Rubric: 043-scoping-shell-baseline

The task is **done only if every box holds** — otherwise it is in progress,
not done. Deliverables 1–10, decisions D1–D13 and the terms are defined in
[contract.md](contract.md); this rubric points at them and restates nothing.

1. [ ] Implementation satisfies [contract.md](contract.md): deliverables 1–10
       all land; decisions D1–D13 hold as pinned (or as amended at the
       contract gate, quoted in `verification.md`).
2. [ ] `make verify` passes; the deterministic test list in the contract
       § Acceptance checks is present and green; the pinned live check (a)–(h)
       ran with notes and screenshots recorded.
3. [ ] Schema changes are exactly the four named in the contract
       § Constraints (`task.capability`, `task_link`, `evidence_scope.role`,
       `evidence_scope.plan_version`, plus the widened check constraint), in
       one reversible migration; the downgrade refuses while a scoping task
       exists.
4. [ ] The OpenAPI diff is additive only; `frontend/openapi.json` and
       `frontend/src/api/gen/types.ts` changed only via `make openapi-sync`;
       no generated files or secrets edited by hand.
5. [ ] Prompt hashes: two new entries (`scoping_planner_v1`, the baseline
       template), every existing hash unchanged; the EB planner prompt and
       the EB chain compose byte-for-byte as before.
6. [ ] The gate `baseline_confirm` pauses in all four steering modes (D11);
       nothing after it runs in this slice (D12); the capability switch cannot
       be bypassed by a direct API call (D3); a link grants no access.
7. [ ] Every baseline section can render the not-found state; the key
       assumption and what is contested carry the reasoning label; the
       coverage statement names what was not searched.
8. [ ] No tests deleted, skipped or weakened without written justification.
9. [ ] Verification evidence recorded ([verification.md](verification.md)),
       including the three-baseline qualitative note.
10. [ ] Known gaps and deferred seams listed in
        [docs/deferred.md](../../deferred.md): per-field turn provenance ·
        Search further (D10) · inherited document rows (task 2, D4) ·
        `task_link.option_id` (task 2, D13).
11. [ ] ADR 0037 written and Accepted with sign-off date, with the rollback
        commands.
12. [ ] Required review stack for Tier 4 ran (contract verifier ·
        `/code-review medium` · one security lane · adversarial at contract,
        plan and code · `/simplify` · human deep review), or a step was
        skipped with the owner's written ruling — findings and dispositions
        in [verification.md](verification.md).
