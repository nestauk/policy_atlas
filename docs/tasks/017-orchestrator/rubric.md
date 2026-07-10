# Rubric: 017-orchestrator

Core completion criteria. The task is **done only if every box holds** — otherwise it is
in progress, not done. (Rev 2.5 — tracks contract rev 2.5.)

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes — green, deterministic, zero-egress (stub planner; fixture
       defaults unchanged).
3. [ ] No approval-gated change snuck in unapproved — schema limited to the approved
       `orchestration_plan` table + minimal run linkage (no capability-run entity, no
       plan blocks/units), auth/tenancy, egress beyond the approved planner surface,
       deps, CI, production config, public interfaces beyond the one approved CLI
       entrypoint, scaffold.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] **Spine enforcement test-pinned**: no composable orchestration plan omits or
       reorders a mandatory-spine component (acquire → screen → classify → appraise →
       ingest → synthesise); discretionary selection matches the approved plan
       (intent-fit × gradation, decision 4).
7. [ ] **Fail-closed compile test-pinned**: unknown components, parameters or directives
       reject at validation — a caught error, never a silent run; approved plan and
       executed config are provably the same (round-trip property, amendments included).
8. [ ] **Failure semantics test-pinned** (fault-injected): spine-component failure fails the
       run honestly with no downstream components; discretionary-component failure degrades with
       reason-coded events and synthesise takes the deepest successful reference
       (transitive resolution — the whole surviving chain feeds the artefact); a
       failed stage's run id never feeds downstream; the bounded-retry rule fires as
       plan-pinned; a DB-error failure still records its `component.failed` event
       (rollback first, fresh transaction — contract decision 8 rev 2.5), unless the
       escape valve was taken with written justification.
9. [ ] **Gradation compile bounded, two-axis, and the nudge anchored**: search breadth
       × analysis depth compile only to existing directive surfaces (search depth ·
       stage-2 screen · characterise · deep chain · selection budget · grouping facet);
       off-diagonal compositions (narrow-and-deep, broad-and-shallow) compose validly;
       nothing compiles into the synthesis section directive; the fixed
       lighter/as-proposed/deeper options each re-derive a valid full plan with its own
       concrete proposal + measured time band; the default proposal is the middle
       pairing.
10. [ ] **Steering core test-pinned**: mode → pause-set compile for all four modes;
        the deepening-selection steer-point fires on its computable triggers and pauses
        in every mode except Unattended; its intent-vocabulary options (clusters ·
        strongest · most-relevant · budget · as-proposed) compile to the declared
        selection grammar with inexpressible intents refused honestly; steering
        adjustments touch only not-yet-run components and land as user-attributed plan
        version rows; Unattended auto-resolves to the plan's visible defaults
        with every resolution flagged + collated; abort leaves committed components and an
        honestly-abandoned run with no artefact.
11. [ ] **Sub-agent boundary real**: the orchestrator delegates execution to the EB
        capability-runner; steer-points surface only through the orchestrator; the
        runner's directive-authoring slot is a named seam (the future LLM EB-expert
        drop-in), recorded in `deferred.md`.
12. [ ] **Planner surface discipline**: exactly one new prompt surface, lead-authored
        and question-type-neutral (no inherited intervention framing — the V2
        anti-pattern); questions carry suggested answers (broad→narrow, degrade to
        free text, re-derived as framing evolves); structured output validated
        fail-closed; no plan field collected that nothing consumes; check-in content
        deterministic (no narration surface); no other prompt text changed anywhere
        in the tree; the sequencing invariant holds (the planner completes before
        acquire begins — no prompt-bearing planning surface runs mid-chain, and every
        mid-run amendment is user-authored, deterministically compiled).
13. [ ] **Plan lifecycle auditable and durable (table-first)**: the
        `orchestration_plan` rows carry the proposed/approved plan and its immutable
        amendment versions with attribution; per-component `plan.compiled` events
        carry plan id + version; plan rows + events together reconstruct the run —
        including every steering interaction — with no orphan state in either.
14. [ ] **Posture honesty**: per-component commit shape verified (mid-chain failure
        leaves prior components' state committed and the run honestly failed); no resume implied;
        substance never silent in any mode.
15. [ ] **Spec refinement landed**: execution-orchestration § Steering modes carries the
        Unattended pre-declared-visible-defaults path, with a `log.md` entry, and the
        firm principle's accountability purpose preserved; ADR covers the v1 carve +
        the refinement.
16. [ ] The pinned live check ran and is evidenced in
        [verification.md](verification.md): (a) planner-only review across V2
        question-taxonomy intents incl. one anchored-nudge re-derivation, one
        non-intervention intent composing without the deep chain (intent-fit
        probe) and one compiled scope constraint; (b) one
        composed end-to-end run at modest gradation, at Moderate, with the
        deepening-selection steer-point exercised live and one intent-vocabulary
        adjustment landing as a new plan version row, plan↔chain equivalence, per-component
        wall-clocks and intact honesty labels; (c) fault-injected failure-semantics +
        scripted Unattended tests (no live fault probe).
17. [ ] Gate adjudications recorded (steering core + Unattended mode · durability
        posture · retrieval-boost grammar v2 deferred) — in the contract's revision
        history and `docs/deferred.md` (incl. the sharpened tag-consolidation trigger
        and the LLM EB-expert slice seam).
18. [ ] Verification evidence recorded; known gaps and deferred seams listed
        (gap → [docs/deferred.md](../../deferred.md)).
19. [ ] Required review stack ran for Tier 3 (contract verifier · code review ·
        security lane · Codex adversarial · simplification), or skipped with written
        justification — findings in [verification.md](verification.md).
