# Rubric: 013-synthesise

Core completion criteria. The task is **done only if every box holds** —
otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md) — including every
       numbered design decision as approved (or as amended at the gates).
2. [ ] `make verify` passes (okf-validate · test · typecheck · lint · build);
       the declared manual live check ran with evidence recorded.
3. [ ] No approval-gated change snuck in unapproved — schema beyond the one
       `synthesis_result` table/migration, auth/tenancy, egress beyond the two
       approved generation surfaces, deps, CI, production config, public
       interfaces beyond the registry entry + `grouping_run_id` + the two
       backend kwargs.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)),
       including the named test results the contract lists and the live-run
       evidence (blocks/citations/tiers/flags, Langfuse traces, cost note,
       key hygiene).
7. [ ] Known gaps and deferred seams listed (gap → [docs/deferred.md](../../deferred.md));
       the 012 `query-findings` deviation entry updated per decision 9, not
       silently closed.
8. [ ] Required review stack ran for Tier 3 (contract verifier ·
       `/code-review` medium · security lane · Codex adversarial ·
       simplification or skip-with-justification) — findings adjudicated in
       [verification.md](verification.md).

Slice-specific criteria (the trust invariant, test- or evidence-enforced):

9.  [ ] **Co-emitted citations only**: every claim carries ≥ 1 cited finding
        id from its own group; unknown/cross-group ids reject the response;
        no code path attaches a citation to prose after generation; the model
        never authors a quote.
10. [ ] **Two-part verify holds**: the deterministic presence check runs
        against frozen chunks for every citation (fabricated-quote hard-fail
        preserved); every claim receives exactly one judge verdict from the
        closed lane (Tier 1–4 | unsupported_mis_cited) with a required
        rationale, persisted with judge model + prompt version + envelope
        policy version.
11. [ ] **Flag, don't drop — everywhere**: failed/unlocatable anchors →
        `quote_unverified` + weakly-grounded cap; unsupported and
        weakly-grounded claims persist visibly after repair exhaustion;
        mixed/unclear findings visible in input data and spreads; nothing
        silently promoted to a clean tier, nothing removed.
12. [ ] **Block substrate integrity**: one block per named group of the
        referenced grouping run (exactly — grouping-set fidelity
        test-enforced); claim-grain units with exact offsets; composite-FK
        annotation integrity; content_hash correct; one deterministic pattern
        annotation per block cross-checked against the grouping row
        (mismatch = structural failure).
13. [ ] **Descriptive posture enforced**: negative rules asserted on both
        built prompts (no recommendations, no consensus verdicts, no absence
        phrasing); injection-shaped labels/quotes land as inert data;
        outputs bounded and validated at write.
14. [ ] **Bounded budget**: call budget ≤ 4 × named groups, test-asserted;
        exactly one reword-down repair + one re-judge maximum per block;
        backend failure → `component.failed` with no roll-up row and prior
        blocks named.
15. [ ] **Provenance fidelity**: `synthesis_provenance` carries both prompt
        versions, models, modes, call/repair counts and the two-links-deep
        inherited base (grouping facet/finding-set + extraction fingerprint/
        base-ladder counts); the roll-up row is the last statement;
        same-run re-execution loud.
