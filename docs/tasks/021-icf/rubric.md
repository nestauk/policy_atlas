# Rubric: 021-icf

Core completion criteria. The task is **done only if every box holds** — otherwise it is
in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md), including the eight gate
       decisions as adjudicated by the owner (contract § Decisions).
2. [ ] `make verify` passes; declared manual/eval checks pass (replay probe set + the
       scoped live extract-both-profiles → synthesise check).
3. [ ] No approval-gated change snuck in unapproved — schema, auth/tenancy, egress, deps,
       CI, production config, public interfaces, scaffold (see the contract).
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)).
7. [ ] Known gaps and deferred seams listed (gap → [docs/deferred.md](../../deferred.md)).
8. [ ] Required review stack ran for Tier 3 (contract verifier · code review · one
       security lane · adversarial), or skipped with written justification — findings in
       [verification.md](verification.md).

Slice-specific:

9.  [ ] **IOF invalidation bounded to the approved rider**: the only IOF changes in
        the diff are item 11's — `setting` column, `iof_v3`, `iof_rules_v3`,
        `extract_iof_v7` setting line, fingerprint bump; old memos reuse under the old
        fingerprint; v2-null vs v3-null distinguished via `field_coverage`
        key-absence; no backfill, no rewritten rows.
10. [ ] **Own fingerprint domain**: ICF fingerprint composes only from ICF constants;
        ICF extracts fresh alongside an IOF memo hit on the same document; every
        output-affecting ICF constant (profile, schema, prompt, model, rules, verifier,
        window knobs, vetter sub-block) is in the fingerprint; the shared-vocabulary
        drift guard passes (one definition, both models import it).
11. [ ] **Related-but-distinct held everywhere**: unified `query_findings` returns
        kind-segregated typed sections (never one homogeneous list); no record,
        envelope entry or claim blends schemas; kind-specific filters fail closed;
        honest per-kind availability ("not extracted in this run", never a silent
        absence).
12. [ ] **Trust machinery parity**: ≥1 verified verbatim anchor per record (`qv_v1`);
        `field_coverage` markers for non-valid outcomes only (a null is never
        ambiguous); grain gate enforced; vetter storage semantics = the IOF pattern
        (vetted-out excluded from insert, recorded in the doc summary); honest
        absence on the effects-only probe and per-profile in the roll-up.
13. [ ] **Fencing from day one**: no inline envelope interpolation in `extract_icf_v1`
        (structural test) and the hostile-envelope probe leaves fields unaffected.
14. [ ] **Prompt-bearing surfaces lead-authored and replay-evidenced**
        (`extract_icf_v1`, vetter prompt, `extract_iof_v7`, the planner-prompt
        two-profile update, any synthesise line) — evidence in verification.md.
15. [ ] **First-reader payoff demonstrated**: the scoped live check shows an
        implementation-shaped pattern claim validating deterministically against ICF
        records in a minted artefact (or an honest account of why the probe corpus
        yielded none).
16. [ ] **Spec flow-back landed**: data-model ⏸ ICF entry rewritten as built; components
        §7/§8/§9 narrowed; deferred.md entry discharged into the named narrowed seams.
