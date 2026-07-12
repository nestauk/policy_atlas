# Rubric: 020-extract-v2

Core completion criteria for medium/high-risk slices.
The task is **done only if every box holds** — otherwise it is in progress, not done.

1. [x] Implementation satisfies [contract.md](contract.md).
2. [x] `make verify` passes; declared manual/eval checks pass.
3. [x] No approval-gated change snuck in unapproved — schema, auth/tenancy, egress, deps, CI,
       production config, public interfaces, scaffold (see the contract).
4. [x] No generated files or secrets edited by hand.
5. [x] No tests deleted, skipped or weakened without written justification.
6. [x] Verification evidence recorded ([verification.md](verification.md) or PR).
7. [x] Known gaps and deferred seams listed (gap → [docs/deferred.md](../../deferred.md)).
8. [x] Required review stack ran for the risk tier (contract verifier · code/security review ·
       adversarial where tiered · simplification), or skipped with written justification — findings
       in [verification.md](verification.md).

Slice-specific (from the contract):

9. [x] The schema gate carries recorded owner approval; migration up/down evidenced;
       existing v1 findings rows and memo entries untouched (no backfill, no rewrite).
10. [x] Every output-affecting change is versioned into the extraction fingerprint
        (`iof_v2` · `extract_iof_v6` · `iof_rules_v2` · profile/vetter decisions as
        adjudicated at plan approval); the memo test pins old-reuse + new-fresh-alongside.
11. [x] `extract_iof_v6` is lead-authored and replay-evidenced on the contracted probe
        set (modelled-projection doc · study-geography doc · hostile-envelope fencing
        probe), with the eval-blind honesty pin stated in verification.md.
12. [x] Fencing is structurally complete: no envelope text reaches the prompt outside an
        id-keyed JSON data object (structural test + security-lane confirmation).
13. [x] `effect_basis` and `study_geography` are carried end-to-end: wire → stored →
        row → `query_findings` writer envelope → reachable at the annotation layer via
        cited finding ids (payload embedding per the plan decision), with
        `field_coverage` markers; v1-null vs v2-null distinguished (coverage
        key-absence) and tested separately.
14. [x] The open ❓s (profile-id bump · vetter payload + guidance line · evidence-type
        CHECK) are recorded as plan-approval decisions, none silently defaulted; the
        settled decisions (study_geography finding grain · effect_basis in /
        study_geography out of `claim_key` · annotation payload does NOT embed record
        metadata) are honoured, not re-opened.
15. [x] Spec flow-back landed: data-model findings-layer base fields updated with a
        task-020 note + spec-bundle `log.md` line; the touched deferred.md entries
        discharged or honestly narrowed (incl. the window-ceiling stays-deferred owner
        call and the evidence-type memo-match residual).
16. [x] Riders hold: evidence type recorded on `source_extraction_record` matches what
        the prompt was sent; mixed/unclear carry-through pinned by tests over group +
        synthesise; `_load_findings` batch load behaviour-preserving with a single
        batched basis query.
17. [x] Adversarial-review adjudications hold as built: dedup twin tests (basis twins
        distinct, geography twins collapse first-wins) · full fencing incl.
        `primary_evidence_type` in the JSON data object · evidence-type column consumed
        as extraction provenance only (writer surfaces keep live classification) ·
        stub/fixture surfaces updated in-scope.
