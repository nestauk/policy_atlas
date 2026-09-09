# Rubric: 043-scoping-shell-baseline

The task is **done only if every box holds** — otherwise it is in progress,
not done. Deliverables 1–10, decisions D1–D13 and the terms are defined in
[contract.md](contract.md); this rubric points at them and restates nothing.

1. [ ] Implementation satisfies [contract.md](contract.md): deliverables 1–10
       all land; decisions D1–D13 hold as ruled on 2026-09-09.
2. [ ] `make verify` passes; the deterministic test list in the contract
       § Acceptance checks is present and green; the pinned live check (a)–(g)
       ran with notes, screenshots and the measured compute time recorded.
3. [ ] Schema changes are exactly those named in the contract § Constraints
       (`task.capability`, `task_link` without an option id, `evidence_scope.purpose`,
       `evidence_scope.plan_version`, the widened check constraint, the
       deliverable-2 renames), in one reversible migration whose downgrade
       reverses the stored values and refuses while a scoping task exists.
4. [ ] The rename (deliverable 2) is one commit reviewed on its own before
       feature code; the sweep test finds no `planning_transcript`,
       `/planning-turns`, `PlanningTurn`, `PlannerBackend`, `planner_prompt`
       or `POLICY_ATLAS_PLANNER_MODEL` left in `backend/src`, `frontend/src`,
       `infra/DEPLOYMENT.md` or `web-api.md`; the version string `planner_v1`
       still stands; "EB" is gone from the living specs, skills, templates and
       code comments (grep recorded); the conversation kind is `task_agent`,
       not `agent`.
5. [ ] The OpenAPI diff is additive apart from the path rename;
       `frontend/openapi.json` and `frontend/src/api/gen/types.ts` changed
       only via `make openapi-sync`; no generated files or secrets edited by
       hand.
6. [ ] Prompt hashes: two new entries (`task_agent_scoping_v1`, the baseline
       template); the ES Task Agent prompt's entry moved with its file and its
       text and `planner_v1` version string are unchanged; every other hash
       unchanged; the ES chain and the ES's card-based steering behave
       byte-for-byte as before.
7. [ ] The gate `baseline_confirm` pauses in frequent, moderate and minimal,
       passes on a recorded and flagged standing default in unattended (D11),
       and the default mode is moderate; nothing after the gate runs (D12);
       a link grants no access.
8. [ ] Gate turns in the Task Agent thread are sorted and routed as D9 states;
       no delta applies unconfirmed; no turn lands a plan under a running walk;
       an Evidence search pause still refuses turns.
9. [ ] The baseline always carries the eight required sections and at most two
       proposed ones; every section can render the not-found state; the key
       assumption and what is contested carry the reasoning label; the coverage
       statement names what was not searched; the writing-mode trial is
       recorded, the owner's pick applied and the losing mode deleted.
10. [ ] Inherit context carries the linked plan, the report body without
        citations and the coverage statement, fenced once and stable across
        turns; nothing is copied into the receiving task's rows (D4).
11. [ ] No tests deleted, skipped or weakened without written justification.
12. [ ] Verification evidence recorded ([verification.md](verification.md)),
        including the trial record, the three-baseline qualitative note and the
        measured triage and router latency.
13. [ ] Known gaps and deferred seams listed in
        [docs/deferred.md](../../deferred.md): per-field turn provenance ·
        Search further (D10) · inherited document rows (task 2, D4) ·
        `task_link.option_id` (task 2, D13) · scoping deep (D6) · the later
        latency levers (D7) · the Task Agent as the Evidence search's control
        surface and any chat carrying Task Agent turns (D9).
14. [ ] The four spec changes in contract § Spec changes are applied with the
        owner's words quoted and logged in `docs/specs/log.md`; sources
        untouched.
15. [ ] ADR 0037 written and Accepted with sign-off date, with the rollback
        commands.
16. [ ] Required review stack for Tier 4 ran (contract verifier ·
        `/code-review medium` · one security lane · adversarial at contract,
        plan and code · `/simplify` · human deep review), or a step was
        skipped with the owner's written ruling — findings and dispositions
        in [verification.md](verification.md).
