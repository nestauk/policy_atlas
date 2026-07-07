# Rubric: 013-synthesise

Core completion criteria. The task is **done only if every box holds** —
otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md) (rev 2) — every
       numbered design decision as approved (or as amended at the gates),
       implementing the ADR-0009-refined spec.
2. [ ] `make verify` passes (okf-validate · test · typecheck · lint · build);
       the declared manual live check ran on **both paths** with evidence
       recorded.
3. [ ] No approval-gated change snuck in unapproved — schema beyond the one
       `synthesis_result` table/migration, auth/tenancy, egress beyond the
       three approved generation surfaces, deps, CI, production config,
       public interfaces beyond the registry entry +
       `characterisation_run_id`/`grouping_run_id` + the two backend kwargs.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)),
       including the named test results the contract lists and the live-run
       evidence for both paths (blocks/citations/tiers/flags, Langfuse
       traces, cost note, key hygiene).
7. [ ] Known gaps and deferred seams listed (gap → [docs/deferred.md](../../deferred.md));
       the 012 `query-findings` entry and the artefact-composition entry
       updated per contract decisions 3/10, not silently closed; the
       chunk-grounded seam recorded with ADR 0009's risk note.
8. [ ] Required review stack ran for Tier 3 (contract verifier ·
       `/code-review` medium · security lane · Codex adversarial ·
       simplification or skip-with-justification) — findings adjudicated in
       [verification.md](verification.md).

Slice-specific criteria (the trust invariant, test- or evidence-enforced):

9.  [ ] **Co-emitted, validated claims only**: every finding claim carries
        ≥ 1 cited finding id from its own group (unknown/cross-group ids
        reject); no code path attaches a citation to prose after generation;
        the model never authors a quote; pattern-claim counts equal the
        code-computed spread/record numbers (wrong counts reject); theme
        claims validate against the theme list; disallowed claim types
        reject.
10. [ ] **Two-part verify holds on the findings path**: the deterministic
        presence check runs against frozen chunks for every citation
        (fabricated-quote hard-fail preserved); every finding claim receives
        exactly one judge verdict from the closed lane (Tier 1–4 |
        unsupported_mis_cited) with a required rationale, persisted with
        judge model + prompt version + envelope policy version; judge input
        includes the cited chunks' full frozen text
        (`synthesis_envelope_v1`), not quotes alone.
11. [ ] **Flag, don't drop — everywhere**: failed/unlocatable anchors →
        `quote_unverified` + weakly-grounded cap; unsupported and
        weakly-grounded claims persist visibly after repair exhaustion;
        mixed/unclear findings visible in input data and spreads; nothing
        silently promoted, nothing removed.
12. [ ] **Terminus/composition v1 holds**: one artefact per run with the
        bounded intent-derived title (empty characterisation → honest skip,
        no artefact); deterministic block order (landscape first, then
        groups); finding blocks == named groups of the referenced grouping
        run exactly; landscape-only runs flagged `landscape_only`; re-run →
        new artefact; claim-grain units with exact offsets; composite-FK
        annotation integrity; content_hash correct; spread cross-checked
        against the grouping row (mismatch = structural failure);
        pattern/theme annotations exist iff their claim does, on that
        claim's unit.
13. [ ] **Descriptive posture enforced on all three prompts**: negative
        rules asserted on the built prompts (no recommendations, no
        consensus verdicts, no absence phrasing); injection-shaped
        theme/group labels or finding quotes land as inert data; outputs
        bounded and validated at write.
14. [ ] **Bounded budgets**: ≤ 2 calls landscape, ≤ 4 × named groups
        findings, test-asserted; exactly one repair + one re-judge maximum
        per block; backend failure → `component.failed` with no roll-up row
        and prior blocks named.
15. [ ] **Provenance fidelity**: `synthesis_provenance` carries all three
        prompt versions, models, modes, per-path call/repair counts and the
        inherited chain base (characterisation reference; when deep —
        grouping facet/finding-set + extraction fingerprint/base-ladder
        counts); the roll-up row is the last statement; same-run
        re-execution loud.
