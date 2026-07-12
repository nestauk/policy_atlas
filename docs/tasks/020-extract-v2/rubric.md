# Rubric: 020-extract-v2

Core completion criteria for medium/high-risk slices.
The task is **done only if every box holds** — otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes; declared manual/eval checks pass.
3. [ ] No approval-gated change snuck in unapproved — schema, auth/tenancy, egress, deps, CI,
       production config, public interfaces, scaffold (see the contract).
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md) or PR).
7. [ ] Known gaps and deferred seams listed (gap → [docs/deferred.md](../../deferred.md)).
8. [ ] Required review stack ran for the risk tier (contract verifier · code/security review ·
       adversarial where tiered · simplification), or skipped with written justification — findings
       in [verification.md](verification.md).

Slice-specific (from the contract):

9. [ ] The schema gate carries recorded owner approval; migration up/down evidenced;
       existing v1 findings rows and memo entries untouched (no backfill, no rewrite).
10. [ ] Every output-affecting change is versioned into the extraction fingerprint
        (`iof_v2` · `extract_iof_v6` · `iof_rules_v2` · profile/vetter decisions as
        adjudicated at plan approval); the memo test pins old-reuse + new-fresh-alongside.
11. [ ] `extract_iof_v6` is lead-authored and replay-evidenced on the contracted probe
        set (modelled-projection doc · study-geography doc · hostile-envelope fencing
        probe), with the eval-blind honesty pin stated in verification.md.
12. [ ] Fencing is structurally complete: no envelope text reaches the prompt outside an
        id-keyed JSON data object (structural test + security-lane confirmation).
13. [ ] `effect_basis` and `study_geography` are carried end-to-end: wire → stored →
        row → `query_findings` writer envelope → annotation payload, with
        `field_coverage` markers and old-row null tolerance tested.
14. [ ] The open ❓s (study_geography wire shape · profile-id bump · vetter guidance
        line · evidence-type CHECK) are recorded as plan-approval decisions, none
        silently defaulted.
15. [ ] Spec flow-back landed: data-model findings-layer base fields updated with a
        task-020 note + spec-bundle `log.md` line; the touched deferred.md entries
        discharged or honestly narrowed (incl. the window-ceiling stays-deferred owner
        call and the evidence-type memo-match residual).
16. [ ] Riders hold: evidence type recorded on `source_extraction_record` matches what
        the prompt was sent; mixed/unclear carry-through pinned by tests over group +
        synthesise; `_load_findings` batch load behaviour-preserving with a single
        batched basis query.
