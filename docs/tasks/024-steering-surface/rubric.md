# Rubric: 024-steering-surface

The task is **done only if every box holds** — otherwise it is in progress.
(Rev 4 rewrite, matching the contract's ground-up rewrite.)

1. [ ] Implementation satisfies [contract.md](contract.md) and its design
       annex [steerability-refinement.md](steerability-refinement.md).
2. [ ] `make verify` passes; declared manual/live checks pass (stub-backed,
       zero-egress in CI); migration roundtrip green.
3. [ ] No approval-gated change snuck in unapproved — schema diff is
       **exactly** decision 2 (`capability_run` + `runs.capability_run_id`;
       `event_log` untouched); no new deps; CI untouched; egress is the
       orchestrator moments + B2′ annotator only; no provider-side
       conversation state.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)).
7. [ ] Known gaps and deferred seams listed — the annex's Still-OUT set
       (B4 · tag boosts · vetting/judge/classify steering · dual-view ·
       mid-component pauses · query pre-approval · replanning · EB-expert
       · 025 items) lands in [docs/deferred.md](../../deferred.md) with
       reasons; 017's flagged deviations discharged or re-recorded.
8. [ ] Tier-3 review stack ran (contract verifier · code review · security
       lane · adversarial) — findings in verification.md.

Slice-specific:

9.  [ ] **Rebuild holds:** fresh-connection `steering_history()` over a
        scripted steered run reproduces the full pause → options/triggers →
        decision → outcome story from the database alone, keyed by
        `capability_run`, correct with two walks in one project.
10. [ ] **No decision path without an event:** pause · decision (every
        response kind × every decider) · rejected · refused · skipped ·
        auto-resolved — each with `capability_run_id`, plan lineage,
        boundary, and (where applicable) re-run mode in the payload.
11. [ ] **Attribution + verbatim provenance:** `decided_by`/`authored_by`
        everywhere; wherever prose was given, `user_text` persists exactly
        as typed alongside `interpreted_action`, `confirmed`, and the
        execution profile; orchestrator decisions emit
        `agent_judgement_routed` with reasoning.
12. [ ] **Fail-closed twice, degrade to floor:** router/watch output
        validates against the closed wire model, then compiles through the
        existing apply paths; unconfirmed readings never apply (attended);
        backend errors degrade to structural routing + canonical menu;
        the structural trigger floor is never suppressed by the watch
        (test-asserted).
13. [ ] **Honest refusal:** inexpressible intents (or fragments of a
        fan-out) yield the refusal + a `steering.refused` event, never a
        nearest-option approximation — including watch-authored proposals
        caught by validation.
14. [ ] **Unattended (c) semantics:** pinned rules override discretion;
        hard stops always honoured; no-pinned-rule decisions flagged
        loudest and ordered first in the collation; standing instructions
        are planner-authored, visible plan content.
15. [ ] **Grammar fidelity to the adjudicated set:** B1/B3/B5 + B2′ and
        D1/D3/D5/D6/D7/D8/D9 exactly — no B4, no D4/tag advertising, no
        vetting steer; every parser fail-closed with bounded scrubbed
        strings; `standard`/absent ≡ as-built guard tests pass.
16. [ ] **B2′ fencing holds:** extraction and vetter prompts are
        byte-untouched by emphasis guidance; annotations are run-scoped in
        `extraction_result` JSONB (no finding-row or fingerprint contact);
        annotator output coverage-validated, fail-open-with-flag; the
        synthesis consumer demonstrably carries and foregrounds the marks.
17. [ ] **Re-run modes:** every re-run confirmation and event declares
        additive vs replacement; additive re-entry reprocesses nothing
        already processed; replacement moves references with prior rows
        intact (nothing deleted); watch delegation asymmetry enforced
        (replacement bias-to-escalate in attended modes).
18. [ ] **EB-expert sockets only:** author-blind compile, attribution,
        authoring-seam protocol, `leg_directive` untouched — no every-leg
        directive authoring shipped; authority order (user > declared
        rules > orchestrator) test-pinned.
19. [ ] **Prompts pinned:** `orchestrator_v1` family +
        `finding_relevance_v1` lead-authored, versioned, recorded in
        execution profiles/provenance.
20. [ ] **Spec flow-back + ADR landed:** execution-orchestration
        § Steering modes rewritten (decider dial, mode table, labels);
        sequencing-invariant revision ADR'd; `log.md` entry written.
