# Rubric: 017-orchestrator

Core completion criteria. The task is **done only if every box holds** — otherwise it is
in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes — green, deterministic, zero-egress (stub planner; fixture
       defaults unchanged).
3. [ ] No approval-gated change snuck in unapproved — schema (none permitted: no plan
       table, no capability-run entity), auth/tenancy, egress beyond the approved planner
       surface, deps, CI, production config, public interfaces beyond the one approved
       CLI entrypoint, scaffold.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] **Spine enforcement test-pinned**: no composable orchestration plan omits or
       reorders a mandatory-spine leg (acquire → screen → classify → appraise →
       ingest → synthesise); discretionary selection matches the approved gradation.
7. [ ] **Fail-closed compile test-pinned**: unknown components, parameters or directives
       reject at validation — a caught error, never a silent run; approved plan and
       executed config are provably the same (round-trip property).
8. [ ] **Failure semantics test-pinned** (fault-injected): spine-leg failure fails the
       run honestly with no downstream legs; discretionary-leg failure degrades with
       reason-coded events and synthesise takes the deepest successful reference; a
       failed stage's run id never feeds downstream; the bounded-retry rule fires as
       plan-pinned.
9. [ ] **Depth compile bounded**: gradation bundles compile only to existing directive
       surfaces (search depth · stage-2 screen · characterise · deep chain · selection
       budget · grouping facet); nothing compiles into the synthesis section directive.
10. [ ] **Planner surface discipline**: exactly one new prompt surface, lead-authored;
        structured output validated fail-closed; no other prompt text changed anywhere
        in the tree.
11. [ ] **Plan lifecycle auditable**: `plan.proposed` → `plan.approved` →
        `plan.compiled` → component events reconstruct the run from the event log alone.
12. [ ] **Posture honesty**: no steering mode claimed (v1 is plan-gated then
        run-to-completion); no resume implied; per-component commit shape verified
        (mid-chain failure leaves prior legs committed and the run honestly failed).
13. [ ] The pinned live check ran and is evidenced in
        [verification.md](verification.md): (a) planner-only review across V2
        question-taxonomy intents incl. one nudge re-derivation; (b) one composed
        end-to-end run at modest gradation with plan↔chain equivalence, per-leg
        wall-clocks and intact honesty labels; (c) fault-injected failure-semantics
        tests (no live fault probe).
14. [ ] Both gate adjudications (steering/durability posture · retrieval-boost grammar
        v2) recorded — in this contract's revision history and `docs/deferred.md`.
15. [ ] Verification evidence recorded; known gaps and deferred seams listed
        (gap → [docs/deferred.md](../../deferred.md)); ADR for the v1 carve written.
16. [ ] Required review stack ran for Tier 3 (contract verifier · code review ·
        security lane · Codex adversarial · simplification), or skipped with written
        justification — findings in [verification.md](verification.md).
