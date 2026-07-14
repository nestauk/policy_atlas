# Rubric: 022-synthesis-refinement — Synthesis Refinement

Core completion criteria. The task is **done only if every box holds** — otherwise it
is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md), including every gate
       decision as adjudicated (1–8 + agenda A–E).
2. [ ] `make verify` passes; the four pinned live checks pass and are evidenced.
3. [ ] No approval-gated change snuck in unapproved — the `grouping_result`
       migration (including its rewrite of persisted group ids in
       `synthesis_result.blocks` + theme-annotation payloads, and the cross-kind
       UNION view), plus the ICF `context_label` rider column, are the only
       schema changes; no new egress, deps, CI, prod config, public interfaces.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)): live-run
       ids, cost before/after table, replay-round records, migration up/down.
7. [ ] Known gaps and deferred seams listed (gap → [docs/deferred.md](../../deferred.md));
       every agenda item A–E has a recorded outcome (built / explicitly re-deferred) —
       silent inheritance of an old deferral fails this box.
8. [ ] Required Tier-3 review stack ran (contract verifier · code/security review ·
       adversarial · simplification), findings adjudicated in verification.md.
9. [ ] **Scale fix live-evidenced**: a both-profiles corpus at ≥184 distinct facet
       values partitions healthily (no duplicate-id rejection) — the
       facet-partition-value-list-scale-limit failure mode demonstrably closed.
10. [ ] **Per-facet honesty holds**: one facet's failure lands an honest per-facet
        failure row with persisted rejection reasons; sibling facets survive; per-facet
        residuals and `groups_unsectioned` are never silently merged or dropped.
11. [ ] **Facet-qualified ids are collision-safe end-to-end**: directive `group_ids`,
        `query_findings` filters, section assignment and envelope carriage all reject
        unqualified/ambiguous ids fail-closed (test-asserted).
12. [ ] **Cost work is measured, not asserted**: BOTH arms of the two-arm
        comparison on the cache-discounted curve — (a) v6 vs v7 on the legacy
        one-facet substrate (Phase-2 isolation), (b) final multi-facet v6 vs the
        $15.45 / 24% historical baseline — each recording facet/section set,
        corpus, model, cache state, repair incidence, run order; no phase-2
        change ships without its replay evidence.
13. [ ] **Prompt discipline held**: every touched prompt surface bumped its version
        string; the planner prompt swept for changed group semantics (coupled-readers
        rule); judge prompt byte-identical and judge-envelope content unchanged
        EXCEPT item 17(i)'s re-judge span-map completeness fix, evidenced by its
        re-judge-set replay (verdict-flip inspection); characterise prompts
        byte-identical.
14. [ ] **Provider neutrality held**: no OpenAI-specific API coupling introduced by
        the caching work (Bedrock constraint).
15. [ ] Upgrades-never-invalidate held: pre-migration `grouping_result` rows are
        migrated in place per decision 1; existing synthesis references resolve.
16. [ ] **Unspanned-lane precision fixes hold** (item 17): the judge span map is
        built from ALL valid claims' spans (all types, kept + rejudged;
        test-asserted) with verdict coverage unchanged, evidenced by the
        mandatory re-judge-set replay; the three counters land with the pinned
        names and precedence (`unspanned_overlap_filtered` →
        `unspanned_duplicate_stale` → `unspanned_unlocated`); a prose-changing
        repair's re-judge unspanned results supersede the initial scan's; the
        eval re-baseline note for `unspanned_assertions` is recorded in
        deferred.md or the eval handoff.
17. [ ] **ICF `context_label` rider holds**: strictly source-named (null when the
        source provides no short name — vetter flag class test-asserted on a
        paraphrase fixture); `icf_v2` fingerprint bump with nothing else riding;
        v1 rows read "not recorded under icf_v1" via `field_coverage`
        key-absence, no backfill.
18. [ ] **Repair is a dependency-complete micro-call**: repair inputs carry the
        failing claims' ids, reasons, local prose context and per-claim-type
        dependency records — and demonstrably NOT the full transcript
        (test-asserted on input size/content); replacements validate against
        the failing set by id.
19. [ ] **Tool-return hygiene holds**: dedup covers chunks, findings and lookup
        records (repeat = `{id, already_returned}`; citation eligibility spans
        reference-only repeats — test-asserted); windowed returns fire only on
        oversized chunks, anchored on retained winning-unit offsets; the
        per-turn budget skips-and-continues past over-budget results (the
        `break` drop is gone).
20. [ ] **Plumbing surfaces hold**: `search_chunks` scope filters validate
        per-argument fail-closed (doc ids ∈ corpus · group ids resolve ·
        evidence types closed enum · tags ∈ project tag set);
        `_soft_prior`'s combined product clamps to [0.1, 10] with raw factors +
        executed multiplier + confidence-suppression recorded in provenance;
        `propose_synthesis_plan`/compile is side-effect-free (no-write test) and
        the compile is deterministic; `lookup` reaches screening rows.
21. [ ] **Cost riders hold**: the key-findings seed carries only chunks cited by
        surviving claims; read-batch query embeddings are batched per turn;
        prompt-facing DTOs carry no membership UUID lists and the slimmed
        ledger shape (test-asserted on seed content).
22. [ ] **Characterise equivalence + granularity**: characterise outputs are
        behaviourally unchanged on the engine (regression evidence; prompts
        byte-identical); group discovery honours the per-run computed ceiling
        with no lower bound, replay-evidenced across differently-sized pinned
        inputs against the live over-fragmentation baseline.
