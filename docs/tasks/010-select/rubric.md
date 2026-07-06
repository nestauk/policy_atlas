# Rubric: 010-select

Core completion criteria. The task is **done only if every box holds** — otherwise it
is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes; the declared manual live check (intent embedding + real-vector
       relevance through the skeleton) passes with evidence.
3. [ ] No approval-gated change snuck in unapproved — the slice lands exactly the two gated
       items (the `selection_result` table · the `"select"` registry entry) and nothing else
       gated: no new dependency, no new egress front, no existing-table change, no new
       `run_harness` parameter.
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

9.  [ ] **Determinism holds end-to-end**: two identical runs produce byte-identical
        `selection_result` rows (test-asserted); no ordering leak found in review.
10. [ ] **The bidirectional rationale is complete and countable**: every screened-in doc is
        accounted for as selected (with reason `must_include` | `breadth_floor` | `ranked`)
        or in an exclusion aggregate; totals reconcile with the counting invariants
        (`screened_in == selected + not_selected`).
11. [ ] **Flag-not-block verified**: null relevance, missing appraisal and unknown metadata
        demonstrably never exclude a document; must-includes are the only hard rule and
        out-of-scope must-includes are flagged, not silently handled.
12. [ ] **The anti-top-k guard works**: the breadth-floor test shows a dominant stratum
        cannot starve the others; the unclustered stratum participates as a stratum.
13. [ ] **`not_selected` never masquerades as absence**: no payload or summary phrasing
        claims a gap; selection is run-local (no canonical writes, no doc-status column);
        the escalation-trigger flags are computed and present in the payload.
14. [ ] **Suite stays egress-free**: socket-deny covers a select round-trip; the intent
        embedding on the live path is the slice's only new call site, on the approved
        embeddings front, traced by the existing wiring.
