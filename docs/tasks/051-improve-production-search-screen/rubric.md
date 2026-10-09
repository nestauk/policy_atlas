# Rubric: 051-improve-production-search-screen

The task is **done only if every box holds**. Otherwise it is in progress, not done.
Problems P1–P9 and decisions D1–D20 are defined in [contract.md](contract.md). D18 items
are out of scope and have no item here.

1. [ ] Implementation satisfies [contract.md](contract.md): every surface in § Surfaces
       changed as its "After" column says; the "do not change" row untouched; D1–D17 hold
       as written.
2. [ ] `make verify` and `make prompt-guard` pass. Every unit test named in § Acceptance
       checks exists and passes.
3. [ ] **P1 / P6 / P5 (D8).** Overton calls send `sort=relevance`, the parameter is
       protected, results are de-duplicated by normalised title, the 15 most-cited
       non-result documents are fetched by id, and the policy pool is ranked by
       specificity and cut at the scope's policy cap.
4. [ ] **P2 (D3–D7, D13).** Every scope runs the semantic seed calls (or records why
       they were skipped, fail-closed), the backward snowball and the forward chase; the
       paper pool is built before persistence, ranked by specificity and cut at the
       papers cap; only kept candidates are persisted and embedded; `search.executed`
       and `source.acquired` carry `query_origin`; `dropped_over_cap` is visible per pool.
5. [ ] **P3 (D1, D11, D12).** A run at any scope makes exactly one acquire run and one
       stage-1 screen run; the listed loop orchestration and tests are gone; the
       reformulate and suggest prompt pieces stay and their tests pass; the tag
       `search-round-loop-last` exists on the design-phase commit and ADR 0038 carries
       the restore recipe; the replacing tests pin the provenance invariants; no schema
       change; `DEPTH_CONSTANTS` has the three rows of D12.
6. [ ] **P4 (D10).** Stage 1 runs on `gpt-5.6-luna` with the `screen_v4` text and the
       adaptive vote as `decide_stage1`'s truth table; `screen_prompt.py` is re-pinned;
       stage 2 is unchanged; the screening eval's `vote.py` imports the production
       function; the vote tests in § Acceptance checks pass.
7. [ ] **P7 / P8 (D2, D14).** Query generation runs on `gpt-5.6-luna` with the unchanged
       prompt; `QUERY_MAX_CHARS` is 1,300.
8. [ ] **P9 (D15).** The scope hint, the frontend constant and the planner prompt carry
       the two numbers per scope; the frontend tests pass; `planner_prompt.py` is
       re-pinned.
9. [ ] **Egress hardening (D12, D19).** Every new request shape goes through
       `search_live.py` with its timeouts, limiter, retry cap and redaction; the logical
       call budgets of D12 bound each run and the HTTP ceiling is stated; the stubs and
       fixtures answer the new verbs with zero egress; the live probes, including the
       semantic-filter probe, are recorded.
10. [ ] **Measured (D17).** The eval checks run the single pass with screening at every
        depth; the live check ran within the spend ceiling: mini-set search recall meets
        the three thresholds, screen recall is at least 90% of search recall at each
        scope, the full-set Broad run is recorded or its deferral by the owner noted,
        documents, calls, tokens and cost per scope are recorded, the policy-side replay
        tests pass, the manual app run completed with a landmark shown.
11. [ ] No approval-gated change beyond those the contract names (egress shapes, model
        ids, prompt edits) — no schema, auth, dependency, CI or production-config change.
12. [ ] No generated files or secrets edited by hand.
13. [ ] No tests deleted, skipped or weakened without written justification; the deleted
        loop tests are listed with the tests that replace their invariants.
14. [ ] Verification evidence recorded in [verification.md](verification.md) as § Verification
        evidence expected lists.
15. [ ] Known gaps and deferred seams in [docs/deferred.md](../../deferred.md): the relevance
        reserve (D6), similarity damping (D8), the reformulation contingency (D11),
        seminal-decile scoring (D17), removed-title records and the `source_country` plan
        option (D18); the discharged items (the round loop, the record-cap seam, the
        Overton sort bug) marked discharged.
16. [ ] ADR 0038 written and accepted, superseding ADR 0012 decisions 1, 3, 4 and 5 and
        amending ADR 0011 decision 1; `components.md` §1 and §2 updated; the tutorial
        page describes the implemented design with the measured numbers (D20); one line in
        `docs/specs/log.md`.
17. [ ] Review stack for Tier 3 ran: contract verifier, code review, security lane,
        Codex adversarial review on the code, and the contract-stage Codex review whose
        findings are adjudicated in the contract's status line.
