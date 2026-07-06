# Rubric: 010-select

Core completion criteria. The task is **done only if every box holds** — otherwise it
is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes; the declared manual live check (intent embedding + real-vector
       relevance + live `llm_rerank_v1` calls through the skeleton, traced) passes with
       evidence.
3. [ ] No approval-gated change snuck in unapproved — the slice lands exactly the three gated
       items (the `selection_result` table · the `"select"` registry entry +
       `ranking_backend` parameter · the `select_rerank_v1` generation surface + intent-embed
       call site) and nothing else gated: no new dependency, no existing-table change, no
       second prompt surface.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md) or PR), including
       every named test result the contract lists.
7. [ ] Known gaps and deferred seams listed (gap → [docs/deferred.md](../../deferred.md)),
       including the 009 vectorisation-entry update (first read landed).
8. [ ] Required review stack ran for Tier 3 (contract verifier · code/security review ·
       adversarial · simplification), sized per the 009 retro note, or skipped with written
       justification — findings in [verification.md](verification.md).

Slice-specific criteria (from the contract's disciplines):

9.  [ ] **Determinism holds where claimed**: under `coverage_stratified_v1`, two identical
        runs produce byte-identical `selection_result` rows (test-asserted); no ordering
        leak found in review. The structure (strata, allocation, budget, hard rules) is
        deterministic under both strategies.
10. [ ] **The bidirectional rationale is complete and countable**: every screened-in doc is
        accounted for as selected (with reason `must_include` | `breadth_floor` | `ranked`)
        or in an exclusion aggregate; totals reconcile with the counting invariants
        (`screened_in == selected + not_selected`).
11. [ ] **Flag-not-block verified**: null relevance, missing appraisal and unknown metadata
        demonstrably never exclude a document; directive boosts re-weight and can never
        exclude (no directive shape manufactures a hard gate); must-includes are the only
        hard rule and out-of-scope must-includes are flagged, not silently handled.
11a. [ ] **The directive surface is agent-ready**: `SelectionDirective` is a first-class
        facade argument (not JSONB archaeology); an empty directive equals the default scan;
        a column boost and a tag boost each demonstrably steer a selection; the executed
        directive + its source are recorded whole in `selection_provenance`.
12. [ ] **The anti-top-k guard works**: the breadth-floor test shows a dominant stratum
        cannot starve the others; the unclustered stratum participates as a stratum.
13. [ ] **`not_selected` never masquerades as absence**: no payload or summary phrasing
        claims a gap; selection is run-local (no canonical writes, no doc-status column);
        the escalation-trigger flags are computed and present in the payload.
14. [ ] **Suite stays egress-free**: socket-deny covers a select round-trip (stub embedder +
        stub ranker); live egress is exactly the two approved surfaces (intent embedding ·
        `select_rerank_v1` on contested strata), both traced by the existing wiring; no key
        appears in logs/events/artifacts.
15. [ ] **The rerank degrades, never fails or excludes**: every contested doc is LLM-scored
        or falls back to the deterministic composite with a counted `rank_fallback` flag;
        the call-budget maximum is enforced pre-call (counting-double test); LLM scores
        demonstrably cannot exclude a document; reasons are code-constrained and stored as
        inert data; prompt hygiene (id-keyed data records) asserted structurally.
