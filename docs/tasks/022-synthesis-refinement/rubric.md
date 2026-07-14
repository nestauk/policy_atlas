# Rubric: 022-synthesis-refinement — Synthesis Refinement

Core completion criteria. The task is **done only if every box holds** — otherwise it
is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md), including every gate
       decision as adjudicated (1–8 + agenda A–E).
2. [ ] `make verify` passes; the four pinned live checks pass and are evidenced.
3. [ ] No approval-gated change snuck in unapproved — the `grouping_result`
       migration and the ICF `context_label` rider column are the only schema
       changes; no new egress, deps, CI, prod config, public interfaces.
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
12. [ ] **Cost work is measured, not asserted**: before/after on the cache-discounted
        curve (dollars + cache hit rate + wall-time band) against the $15.45 / 24%
        baseline, same-shape run; no phase-2 change ships without its replay evidence.
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
16. [ ] **Unspanned-lane precision fixes hold** (item 17): the re-judge envelope
        carries the full claim span map (test-asserted); excerpts overlapping
        mapped spans are deterministically filtered and counted; the eval
        re-baseline note for `unspanned_assertions` is recorded in deferred.md
        or the eval handoff.
