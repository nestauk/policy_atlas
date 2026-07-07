# Rubric: 012-group

Core completion criteria. The task is **done only if every box holds** —
otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes; the declared manual live check passed (real
       `group_facet_v1` call(s), a second-facet run shown, evidence in
       verification.md).
3. [ ] No approval-gated change snuck in unapproved — schema, auth/tenancy,
       egress, deps, CI, production config, public interfaces, scaffold (see the
       contract's three gated changes).
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)).
7. [ ] Known gaps and deferred seams listed (gap → [docs/deferred.md](../../deferred.md)).
8. [ ] Required review stack ran for the risk tier (contract verifier ·
       code/security review · adversarial · simplification), sized per the
       review-economy notes (class-split budget, per-angle diff scoping), or
       skipped with written justification — findings in
       [verification.md](verification.md).
9. [ ] Grouping integrity holds as specced: the grouped set is exactly the
       referenced extraction run's finding set (resolved via
       `docs[].extraction_record_id`, memo-reused included, integrity
       cross-check enforced); mixed/unclear findings are first-class **in the
       partition** (named groups + `ungrouped` + `no_value`), with direction
       spreads recorded per group, per residual bucket and overall; residuals
       are counted, never dropped, never forced into a catch-all group; the
       exhaustiveness sum identities are test-enforced.
10. [ ] The grouping stays run-local and descriptive: one `grouping_result`
       roll-up row per run; no group entities, tags, finding mutations or
       consensus/evaluative fields anywhere — direction spreads are counts,
       never verdicts; provenance records the facet, its source, and the
       inherited extraction base (fingerprint + base-ladder counts).
11. [ ] Suite and library defaults are stub + egress-free (socket-deny named);
       the one prompt-bearing surface is `group_facet_v1`, lead-authored,
       versioned, recorded in provenance; facet values enter prompts only as
       id-keyed data records under the data/instructions separation; the prompt
       carries the no-catch-all and descriptive-labels negative rules,
       test-asserted on the built prompt — **and** labels/descriptions are
       treated as untrusted model output: deterministically validated at write
       (empty/length/control-char/duplicate/forbidden-generic checks), stored
       and rendered as data, never executed.
