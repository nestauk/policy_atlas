# Rubric: 013-synthesise

Core completion criteria. The task is **done only if every box holds** —
otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md) (rev 4) — every
       numbered design decision as approved (or as amended at the gates),
       implementing the spec as refined by ADRs 0009 + 0010 (incl. the
       amendment).
2. [ ] `make verify` passes (okf-validate · test · typecheck · lint ·
       build); the declared manual live check ran on **both content
       modes** with evidence recorded.
3. [ ] No approval-gated change snuck in unapproved — schema beyond the
       one `synthesis_result` table/migration, auth/tenancy, egress beyond
       the **four** approved generation surfaces + the embedding-query
       use, deps, CI, production config, public interfaces beyond the
       registry entry + `characterisation_run_id`/`grouping_run_id` + the
       two backend kwargs; no retrieval index/extension.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)),
       including the named test results the contract lists and the
       live-run evidence for both modes (sections/blocks/citations/tiers/
       gap grades/flags, retrieval provenance, Langfuse traces, cost note,
       key hygiene).
7. [ ] Known gaps and deferred seams listed (gap → [docs/deferred.md](../../deferred.md));
       the 012 `query-findings` entry, the artefact-composition entry, the
       chunk-grounded seam, the full-`retrieve` seam and the 009
       vectors-ahead-of-reader entry updated per the contract, not
       silently closed.
8. [ ] Required review stack ran for Tier 3 (contract verifier ·
       `/code-review` medium · security lane · Codex adversarial ·
       simplification or skip-with-justification) — findings adjudicated
       in [verification.md](verification.md).

Slice-specific criteria (the trust invariant, test- or evidence-enforced):

9.  [ ] **Intent-led structure holds**: sections derive from intent
        (proposal validated 1..SECTION_CAP, bounded non-generic titles,
        real group_ids; fail-closed directive override recorded as
        source); uncovered groups counted (`groups_unsectioned`); intent
        enters prompts as id-keyed data only, and shapes emphasis, never
        verification.
10. [ ] **The full claim vocabulary, each type validated**: finding claims
        cite ids ⊆ their section's finding set (the model never authors a
        finding quote); chunk-claim quotes presence-checked against the
        whole document basis with **verified spans** becoming the citation
        rows (fabricated → reject, one repair, then excluded **and
        counted**); pattern counts equal computed spreads; **gap claims**
        carry grade + coverage base, corpus-level phrasing fail-closed on
        a non-`inadequate` `search_coverage_record` (else degraded and
        counted), acknowledged-gap sparsity validated numerically,
        inferred gaps visibly labelled; **reasoning claims** visibly
        Tier-4-labelled, bounded per block, strict-routed by the judge
        (empirical/causal sentinel → flagged); theme claims landscape-only;
        no silent uncited path.
11. [ ] **Two-part verify holds on every cited claim**: deterministic
        presence check against frozen chunks; exactly one judge verdict
        from the closed lane (Tier 1–4 | unsupported_mis_cited) with a
        required rationale, persisted with judge model + prompt version +
        envelope policy version; judge input includes the cited chunks'
        full frozen text (`synthesis_envelope_v1`).
12. [ ] **Scoped retrieval is honest and bounded**: anchor chunks always
        included; top-k embedding ranking deterministic on stub vectors;
        `SYNTH_CHUNK_TOP_K` / `SYNTH_CHUNK_CHAR_BUDGET` enforced; chosen
        chunk ids in provenance; only selected-set chunks reachable (a
        foreign or unselected document's chunks never enter); recorded as
        the `retrieve` seam's first increment behind a swappable helper.
13. [ ] **Flag, don't drop — everywhere**: failed/unlocatable anchors →
        `quote_unverified` + weakly-grounded cap; unsupported,
        weakly-grounded and degraded-gap claims persist visibly after
        repair exhaustion; mixed/unclear findings visible in inputs and
        spreads; the only exclusion is fabricated chunk quotes, always
        counted.
14. [ ] **Terminus/composition v1 holds**: one artefact per run with the
        bounded intent-derived title (empty characterisation → honest
        skip, no artefact); section-ordered block binding (landscape
        first); landscape-only runs flagged; re-run → new artefact;
        claim-grain units with exact offsets; composite-FK annotation
        integrity; content_hash correct; annotations exist iff their claim
        does, on that claim's unit.
15. [ ] **Descriptive posture enforced on all four prompts**: negative
        rules asserted on the built prompts (no recommendations, no
        consensus verdicts, absence only as graded gap claims, quotes
        verbatim from supplied text only); injection-shaped labels,
        quotes, chunk text or coverage summaries land as inert data.
16. [ ] **Bounded budgets**: ≤ 2 landscape · ≤ 2 sections · ≤ 4 generation
        + 1 embedding call × sections, test-asserted; backend failure →
        `component.failed` with no roll-up row and prior blocks named.
17. [ ] **Provenance fidelity**: `synthesis_provenance` carries all four
        prompt versions, models, modes, per-mode call/repair counts, the
        section set + source + caps, the retrieval parameters +
        chunk-id hash, and the inherited chain base (characterisation
        reference; when grounded — grouping facet/finding-set + extraction
        fingerprint/base-ladder counts); the roll-up row is the last
        statement; same-run re-execution loud; determinism tests fix
        intent as input.
