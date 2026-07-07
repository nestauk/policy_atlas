# Rubric: 013-synthesise

Core completion criteria. The task is **done only if every box holds** —
otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md) (rev 7.5) — every
       numbered design decision as approved (or as amended at the gates),
       implementing the spec as refined by ADRs 0009 + 0010 (four
       amendments).
2. [ ] `make verify` passes (okf-validate · test · typecheck · lint ·
       build); the declared manual live check ran on **four substrate
       profiles** (screen-only rapid · characterisation-only ·
       characterisation+selection with no extraction · full chain) with
       evidence recorded.
3. [ ] No approval-gated change snuck in unapproved — schema beyond the
       one `synthesis_result` table/migration, auth/tenancy, egress beyond
       the **three** approved generation surfaces + embedding-query use,
       deps, CI, production config, public interfaces beyond the registry
       entry (**all four run references optional**) + the two backend
       kwargs; **exactly one agent-loop surface** with the closed
       read-only **three-tool** set — no second loop, no new or
       write-capable tool, no retrieval index/extension.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)),
       including the named test results the contract lists and the
       live-run evidence for all four profiles (sections/blocks/
       citations/tiers/gap grades/flags, per-section tool-call counts and
       gathered ids, citation origins, Langfuse traces incl. loop turns,
       cost note, key hygiene).
7. [ ] Known gaps and deferred seams listed (gap → [docs/deferred.md](../../deferred.md));
       the 012 `query-findings` entry closed as landed, the
       artefact-composition, corpus-scale-retrieval / full-`retrieve` and
       009 vectors-ahead-of-reader entries updated per the contract, not
       silently closed.
8. [ ] Required review stack ran for Tier 3 (contract verifier ·
       `/code-review` medium · security lane — headline target: the loop ·
       Codex adversarial · simplification or skip-with-justification) —
       findings adjudicated in [verification.md](verification.md).

Slice-specific criteria (the trust invariant + bounded agency +
substrate-conditional flexibility, test- or evidence-enforced):

9.  [ ] **Reference resolution and substrate gating hold**: all four run
        references optional; deepest-given resolves upstream transitively
        with explicit-reference consistency (mismatch = structural
        failure); **≥ 1 groundable substrate required** (zero →
        structural failure, no artefact, no row); chunk claims and
        `search_chunks` gate on screened-in ingested docs; finding claims
        and `query_findings` on an extraction; coverage-pattern,
        characterise-theme and sparsity-gap claims on a characterisation;
        group-theme claims on a grouping; unsupported claim types
        reject; the substrate profile is recorded in provenance.
10. [ ] **Retrieval scope, priors and stages are honest**: scope = the
        screened-in corpus always (screened-out or foreign content never
        returned — test-enforced); a referenced selection **boosts
        ranking, never filters** (an unselected-but-screened chunk is
        reachable); every chunk citation records its origin (selected |
        unselected_screened); the relevance leg is **content-only**
        (metadata never enters embedding/lexical scoring — the 010
        signal-attributability rule, test-asserted); directive
        **`retrieval_boosts` re-weight, never exclude** (clamps enforced;
        malformed fails closed; unknown columns/tags →
        `unmatched_boosts`, never fatal); the **reranker stage is
        pass-through v1** (`reranker: "none"` in provenance; protocol
        exercised by a test-scoped fake; no public kwarg ships); boosts +
        scope counts in provenance; **unit count > `RETRIEVAL_UNIT_CAP` →
        structural failure naming the cap** — no call, no degraded
        sample.
11. [ ] **Intent-led structure holds**: sections derive from intent
        (proposal validated 1..SECTION_CAP, bounded non-generic titles,
        real assignments; fail-closed directive override recorded as
        source); uncovered groups counted (`groups_unsectioned`); intent
        enters prompts as id-keyed data only and shapes emphasis, never
        verification.
12. [ ] **The section loop is bounded and honest**: turn cap enforced
        with cap-exhaustion forcing emission (+ `turn_cap_hit`); unknown
        tool names rejected, never executed; tools read-only and
        project/run-scoped; `lookup`'s query vocabulary closed **and
        covers the tag layer** (tags by doc, docs by tag, aggregates by
        type/asserter); per-call and gathered-context budgets enforced;
        hybrid ranking deterministic on stub vectors; tool-call counts +
        gathered-id hash in provenance; scripted stub sequences drive the
        **real** loop runner; **sections written serially in proposal
        order with the rolling claim ledger** (section N's seed carries
        prior sections' typed claims marked context-never-evidence;
        ledger records structurally uncitable; determinism unaffected —
        test-asserted).
13. [ ] **The full claim vocabulary, each type validated**: finding
        claims cite ids ⊆ their section's finding set (the model never
        authors a finding quote); chunk claims cite **only tool-returned
        ids** with quotes presence-checked against the whole document
        basis, verified spans becoming the citation rows (fabricated →
        reject, one repair, then excluded **and counted**); pattern
        counts equal computed values; **theme claims** validated
        against the referenced clustering, softest-grade-labelled with
        base; **gap claims** carry grade + coverage base, corpus-level
        phrasing fail-closed on a non-`inadequate`
        `search_coverage_record` (else degraded and counted),
        sparsity-grade rejected without characterisation coverage,
        inferred gaps visibly labelled; **reasoning claims** visibly
        Tier-4-labelled, bounded per block, judge strict-routed; no
        silent uncited path; **structured/tabular renderings decompose
        into the same typed claims through the same verification** (no
        escape hatch — the V2 table lesson); **citation-bearing evidence
        is verbatim frozen-chunk text / verified anchors only**
        (model-authored summaries never serve as citation evidence);
        **a fabricated quote is never persisted anywhere** (no citation
        row, no stored quote).
14. [ ] **Verify is two-part, non-agentic, and rewrites down**:
        deterministic presence check against frozen chunks for every
        cited claim; exactly one judge verdict from the closed lane
        (Tier 1–4 | unsupported_mis_cited) with a required rationale,
        persisted with judge model + prompt version + envelope policy
        version; judge input includes the cited chunks' full frozen text
        (`synthesis_envelope_v1`); the judge surface is distinct from the
        writer surface (maker ≠ checker — structural);
        pattern/theme/gap claims deterministically validated, not
        judged; **judge rationales drive one loop-free reword-down
        regeneration + one re-judge (`REPAIR_ROUND_CAP` = 1,
        test-asserted — no new tool calls on repair; a passing claim
        survives a sibling's repair verbatim — the V2
        whole-section-regeneration regression guard)**.
15. [ ] **Flag, don't drop — everywhere**: failed/unlocatable anchors →
        `quote_unverified` + weakly-grounded cap; unsupported,
        weakly-grounded and degraded-gap claims persist visibly after
        repair exhaustion; mixed/unclear findings visible in inputs and
        spreads; cap-forced emissions flagged; the only exclusion is
        fabricated chunk quotes, always counted.
16. [ ] **Terminus/composition v1 holds**: one artefact per run with the
        bounded intent-derived title (zero substrate → structural
        failure, no artefact); proposal-ordered block binding; re-run →
        new artefact; claim-grain units with exact offsets; composite-FK
        annotation integrity; content_hash correct; annotations exist iff
        their claim does, on that claim's unit.
17. [ ] **Descriptive posture enforced on all three surfaces**: negative
        rules asserted on the built prompts/tool schemas (no
        recommendations, no consensus verdicts, absence only as graded
        gap claims, quotes verbatim from tool-returned text only);
        injection-shaped labels, quotes, chunk text, lookup results —
        tag labels included — or coverage summaries land as inert data.
18. [ ] **Bounded budgets that BIND**: generation calls ≤ 2 + SECTION_CAP
        × (SECTION_TURN_CAP + 2) as a pre-run maximum, test-asserted;
        embedding calls ≤ SECTION_TURN_CAP per section; **the plan-pinned
        constants are the values enforced on the live path — configured
        cap == binding cap (the V2 dead-config lesson)**; a section
        emitted with zero cited claims → `uncited_sections` flagged,
        never silent; backend failure → `component.failed` with no
        roll-up row and prior blocks named.
19. [ ] **Provenance fidelity**: `synthesis_provenance` carries all three
        surface versions (tool schemas included), models, modes,
        per-phase call/turn/repair counts, the substrate profile + the
        retrieval scope + selection prior, the section set + source +
        all caps (incl. RETRIEVAL_UNIT_CAP and REPAIR_ROUND_CAP),
        per-section tool-call counts + gathered-id hash, and the
        inherited chain base per resolved reference; the roll-up row is
        the last statement; same-run re-execution loud; determinism
        tests fix intent as input.
