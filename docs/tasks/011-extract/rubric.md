# Rubric: 011-extract

Core completion criteria. The task is **done only if every box holds** —
otherwise it is in progress, not done.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes; the declared manual live check passed (real
       `extract_iof_v1` calls, memo reuse demonstrated, evidence in
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
9. [ ] Provenance integrity holds as specced: every finding is single-source and
       anchored to frozen text (verbatim quote + a chunk location or
       abstract-envelope location per its basis, deterministically checked,
       flagged-not-dropped on failure); coverage vocabulary (`no_findings` ·
       `extraction_failed` · `not_extracted` · `unclear` · `not_applicable`)
       is never phrased as absence; the counting invariants over the selected
       base are test-enforced; existing findings are never invalidated or
       overwritten by a later run, and a failed extraction never blocks its
       own retry.
10. [ ] The source-groundability line holds both ways: the spec's base fields are
       all representable; question-relative judgements (normalised magnitude,
       causal weighting, is-beneficial) are absent from schema, prompt and
       output — test-asserted.
11. [ ] Suite and library defaults are stub + egress-free (socket-deny named);
       the one prompt-bearing surface is `extract_iof_v1`, lead-authored,
       versioned, recorded in provenance; document text enters prompts only as
       id-keyed data records under the data/instructions separation; stub
       fingerprints are distinguishable from live.
