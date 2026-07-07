# Rubric: 013-synthesise

Core completion criteria. The task is **done only if every box holds** —
otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md) (rev 3) — every
       numbered design decision as approved (or as amended at the gates),
       implementing the ADR 0009 + 0010 refined spec.
2. [ ] `make verify` passes (okf-validate · test · typecheck · lint ·
       build); the declared manual live check ran on **both paths** with
       evidence recorded.
3. [ ] No approval-gated change snuck in unapproved — schema beyond the one
       `synthesis_result` table/migration, auth/tenancy, egress beyond the
       **four** approved generation surfaces, deps, CI, production config,
       public interfaces beyond the registry entry +
       `characterisation_run_id`/`grouping_run_id` + the two backend kwargs.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)),
       including the named test results the contract lists and the live-run
       evidence for both paths (sections/blocks/citations/tiers/flags,
       Langfuse traces, cost note, key hygiene).
7. [ ] Known gaps and deferred seams listed (gap → [docs/deferred.md](../../deferred.md));
       the 012 `query-findings` entry, the artefact-composition entry and
       the chunk-grounded seam updated per contract decisions 3/10 and
       ADR 0010, not silently closed.
8. [ ] Required review stack ran for Tier 3 (contract verifier ·
       `/code-review` medium · security lane · Codex adversarial ·
       simplification or skip-with-justification) — findings adjudicated in
       [verification.md](verification.md).

Slice-specific criteria (the trust invariant, test- or evidence-enforced):

9.  [ ] **Intent-led structure holds**: the deep artefact's sections derive
        from intent (proposal validated 1..SECTION_CAP, bounded non-generic
        titles, group_ids real; fail-closed directive override recorded as
        source); uncovered groups counted (`groups_unsectioned`), never
        silently dropped; intent enters prompts as id-keyed data only.
10. [ ] **Co-emitted, validated claims only**: finding claims cite ids ⊆
        their section's finding set (the model never authors a finding
        quote); chunk-claim quotes are presence-checked against the whole
        document basis with **verified spans** (never the model's claimed
        location) becoming the citation rows; pattern-claim counts equal
        the computed spreads; landscape claims validate against the record;
        disallowed claim types reject; no code path attaches a citation to
        prose after generation.
11. [ ] **Two-part verify holds on every cited claim**: deterministic
        presence check against frozen chunks (fabricated finding-anchors
        flagged; fabricated chunk quotes rejected → one repair → excluded
        **and counted** `chunk_claims_rejected`); exactly one judge verdict
        from the closed lane (Tier 1–4 | unsupported_mis_cited) with a
        required rationale, persisted with judge model + prompt version +
        envelope policy version; judge input includes the cited chunks'
        full frozen text (`synthesis_envelope_v1`).
12. [ ] **Flag, don't drop — everywhere**: failed/unlocatable anchors →
        `quote_unverified` + weakly-grounded cap; unsupported and
        weakly-grounded claims persist visibly after repair exhaustion;
        mixed/unclear findings visible in inputs and spreads; the only
        exclusion is fabricated chunk quotes, always counted.
13. [ ] **Terminus/composition v1 holds**: one artefact per run with the
        bounded intent-derived title (empty characterisation → honest skip,
        no artefact); section-ordered block binding (landscape first);
        landscape-only runs flagged; re-run → new artefact; claim-grain
        units with exact offsets; composite-FK annotation integrity;
        content_hash correct; annotations exist iff their claim does, on
        that claim's unit.
14. [ ] **Descriptive posture enforced on all four prompts**: negative
        rules asserted on the built prompts (no recommendations, no
        consensus verdicts, no absence phrasing, quotes verbatim from
        supplied text only); injection-shaped labels, quotes or windowed
        document text land as inert data.
15. [ ] **Bounded budgets**: ≤ 2 landscape · ≤ 2 sections · ≤ 4 × sections,
        test-asserted; windowing deterministic under the plan-pinned char
        budget; backend failure → `component.failed` with no roll-up row
        and prior blocks named.
16. [ ] **Provenance fidelity**: `synthesis_provenance` carries all four
        prompt versions, models, modes, per-path call/repair counts, the
        section set + source + caps, and the inherited chain base
        (characterisation reference; when deep — grouping facet/finding-set
        + extraction fingerprint/base-ladder counts); the roll-up row is
        the last statement; same-run re-execution loud; determinism tests
        fix intent as input.
