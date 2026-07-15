# Rubric: 024-steering-surface

The task is **done only if every box holds** — otherwise it is in progress.

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes; declared manual/live checks pass (stub-backed,
       zero-egress in CI).
3. [ ] No approval-gated change snuck in unapproved — **schema stays
       untouched** (zero-schema events hold), no new deps, CI untouched;
       the one approved egress surface is the pause-time interpreter only.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)).
7. [ ] Known gaps and deferred seams listed (study S2–S5 + grammar seams →
       [docs/deferred.md](../../deferred.md); 017 flagged deviations
       discharged or re-recorded).
8. [ ] Required Tier-3 review stack ran (contract verifier · code review ·
       security lane · adversarial) — findings in verification.md.

Slice-specific:

9.  [ ] **Rebuild holds:** a fresh-connection `steering_history()` over a
        scripted steered run reproduces the full pause → options/triggers →
        decision → outcome story from the database alone (test-asserted; no
        in-memory or transcript input).
10. [ ] **Every steering path emits its event:** pause presented · decision
        (all five response kinds incl. auto_resolved) · rejected adjustment ·
        refused intent · component skipped — each with plan id + version and
        boundary in the payload.
11. [ ] **Verbatim-text provenance:** wherever prose was given,
        `user_text` persists exactly as typed alongside `interpreted_action`,
        `confirmed`, and the interpreter execution profile (model + prompt
        version).
12. [ ] **Interpreter is fail-closed twice:** wire-model validation, then
        the existing apply-path validation — no interpreted action can reach
        state that a hand-authored delta could not; unconfirmed readings
        never apply; interpreter errors degrade to the numbered menu, never
        kill the run.
13. [ ] **Honest refusal:** an inexpressible intent yields
        `refuse_inexpressible` + a `steering.refused` event, never a
        nearest-option approximation.
14. [ ] **Substance never silent:** Unattended auto-resolutions emit events
        with rule + action, `unconfigured_default` flagged loudest; the
        collation is derivable from persisted state.
15. [ ] **Ship-list holds as approved:** S0 triggers read persisted
        `selection_result` signals only (no recomputation); S1 options
        round-trip through `parse_synthesis_directive`; no new
        directive-grammar keys entered the slice.
16. [ ] Spec flow-back + ADR landed (sequencing-invariant revision,
        steering-event vocabulary); `log.md` entry written.
