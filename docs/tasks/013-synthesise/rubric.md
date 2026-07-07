# Rubric: 013-synthesise

Core completion criteria. The task is **done only if every box holds** —
otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md) (rev 6) — every
       numbered design decision as approved (or as amended at the gates),
       implementing the spec as refined by ADRs 0009 + 0010 (three
       amendments).
2. [ ] `make verify` passes (okf-validate · test · typecheck · lint ·
       build); the declared manual live check ran on **three substrate
       profiles** (characterisation-only · characterisation+selection
       with no extraction · full chain) with evidence recorded.
3. [ ] No approval-gated change snuck in unapproved — schema beyond the
       one `synthesis_result` table/migration, auth/tenancy, egress beyond
       the **three** approved generation surfaces + embedding-query use,
       deps, CI, production config, public interfaces beyond the registry
       entry + the run references + the two backend kwargs; **exactly one
       agent-loop surface** with the closed read-only **three-tool** set
       (`search_chunks` · `query_findings` · `lookup`) — no second loop,
       no new or write-capable tool, no retrieval index/extension.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)),
       including the named test results the contract lists and the
       live-run evidence for all three profiles (sections/blocks/
       citations/tiers/gap grades/flags, per-section tool-call counts and
       gathered ids, Langfuse traces incl. loop turns, cost note, key
       hygiene).
7. [ ] Known gaps and deferred seams listed (gap → [docs/deferred.md](../../deferred.md));
       the 012 `query-findings` entry closed as landed, the
       artefact-composition, chunk-grounded / full-`retrieve` and 009
       vectors-ahead-of-reader entries updated per the contract, not
       silently closed.
8. [ ] Required review stack ran for Tier 3 (contract verifier ·
       `/code-review` medium · security lane — headline target: the loop ·
       Codex adversarial · simplification or skip-with-justification) —
       findings adjudicated in [verification.md](verification.md).

Slice-specific criteria (the trust invariant + bounded agency +
substrate-conditional flexibility, test- or evidence-enforced):

9.  [ ] **Reference resolution and substrate gating hold**:
        `characterisation_run_id` required; deepest-given reference
        resolves upstream transitively with explicit-reference consistency
        (mismatch = structural failure); chunk claims and `search_chunks`
        exist only with a selection; finding claims and `query_findings`
        only with an extraction; group-cluster claims only with a
        grouping; unsupported claim types reject; the substrate profile is
        recorded in provenance.
10. [ ] **Intent-led structure holds**: sections derive from intent
        (proposal validated 1..SECTION_CAP, bounded non-generic titles,
        real assignments; fail-closed directive override recorded as
        source); uncovered groups counted (`groups_unsectioned`); intent
        enters prompts as id-keyed data only and shapes emphasis, never
        verification.
11. [ ] **The section loop is bounded and honest**: turn cap enforced
        with cap-exhaustion forcing emission (+ `turn_cap_hit`); unknown
        tool names rejected, never executed; tools read-only and
        project/run/selected-set-scoped (foreign or out-of-scope content
        never returned — test-enforced); `lookup`'s query vocabulary
        closed; per-call and gathered-context budgets enforced; hybrid
        ranking deterministic on stub vectors; tool-call counts +
        gathered-id hash in provenance; repair is loop-free (no new tool
        calls — test-asserted); scripted stub sequences drive the
        **real** loop runner.
12. [ ] **The full claim vocabulary, each type validated**: finding
        claims cite ids ⊆ their section's finding set (the model never
        authors a finding quote); chunk claims cite **only tool-returned
        ids** with quotes presence-checked against the whole document
        basis, verified spans becoming the citation rows (fabricated →
        reject, one repair, then excluded **and counted**); pattern
        counts equal computed values; **cluster claims** validated
        against the referenced clustering, softest-grade-labelled with
        base; **gap claims** carry grade + coverage base, corpus-level
        phrasing fail-closed on a non-`inadequate`
        `search_coverage_record` (else degraded and counted),
        acknowledged sparsity validated numerically, inferred gaps
        visibly labelled; **reasoning claims** visibly Tier-4-labelled,
        bounded per block, judge strict-routed; no silent uncited path.
13. [ ] **Two-part verify holds on every cited claim**: deterministic
        presence check against frozen chunks; exactly one judge verdict
        from the closed lane (Tier 1–4 | unsupported_mis_cited) with a
        required rationale, persisted with judge model + prompt version +
        envelope policy version; judge input includes the cited chunks'
        full frozen text (`synthesis_envelope_v1`); pattern/cluster/gap
        claims deterministically validated, not judged.
14. [ ] **Flag, don't drop — everywhere**: failed/unlocatable anchors →
        `quote_unverified` + weakly-grounded cap; unsupported,
        weakly-grounded and degraded-gap claims persist visibly after
        repair exhaustion; mixed/unclear findings visible in inputs and
        spreads; cap-forced emissions flagged; the only exclusion is
        fabricated chunk quotes, always counted.
15. [ ] **Terminus/composition v1 holds**: one artefact per run with the
        bounded intent-derived title (empty characterisation → honest
        skip, no artefact); proposal-ordered block binding; re-run → new
        artefact; claim-grain units with exact offsets; composite-FK
        annotation integrity; content_hash correct; annotations exist iff
        their claim does, on that claim's unit.
16. [ ] **Descriptive posture enforced on all three surfaces**: negative
        rules asserted on the built prompts/tool schemas (no
        recommendations, no consensus verdicts, absence only as graded
        gap claims, quotes verbatim from tool-returned text only);
        injection-shaped labels, quotes, chunk text, lookup results or
        coverage summaries land as inert data.
17. [ ] **Bounded budgets**: generation calls ≤ 2 + SECTION_CAP ×
        (SECTION_TURN_CAP + 2) as a pre-run maximum, test-asserted;
        embedding calls ≤ SECTION_TURN_CAP per section; backend failure →
        `component.failed` with no roll-up row and prior blocks named.
18. [ ] **Provenance fidelity**: `synthesis_provenance` carries all three
        surface versions (tool schemas included), models, modes,
        per-phase call/turn/repair counts, the substrate profile, the
        section set + source + all caps, per-section tool-call counts +
        gathered-id hash, and the inherited chain base per resolved
        reference; the roll-up row is the last statement; same-run
        re-execution loud; determinism tests fix intent as input.
