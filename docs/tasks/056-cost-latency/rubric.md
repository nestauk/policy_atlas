# Rubric: 056-cost-latency

Core completion criteria. The task is **done only if every box holds** — otherwise it is
in progress, not done. Numbers (N1 to N8, D1 to D6, O1 to O5) point at
[contract.md](contract.md).

1. [ ] Implementation satisfies [contract.md](contract.md) for every phase the owner kept (D5).
2. [ ] `make verify` passes; `make prompt-guard` passes; declared manual checks pass.
3. [ ] No approval-gated change snuck in unapproved: the model set is the one approved at
       the contract gate (D2, O2); no production config, schema, auth, dependency, CI or
       public-interface change.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)): the before-and-
       after cost table per phase on the fixed questions (D1), read from saved results.
7. [ ] Known gaps and deferred seams listed (gap → [docs/deferred.md](../../deferred.md)),
       including the Langfuse custom-row cleanup note.
8. [ ] Required review stack ran for Tier 3 (contract verifier · code and security review ·
       adversarial at contract and plan · simplification), or skipped with written
       justification — findings in [verification.md](verification.md).
9. [ ] N1: every generation in Langfuse carries cache-read and cache-write token counts as
       separate usage buckets, and the cost-per-run script reproduces the contract's
       baseline figures for the sessions it names.
10. [ ] N2: both routes name GPT-6 models for all three tiers; each model's reasoning-effort
        knob is set; no prompt module changed; `make prompt-guard` unchanged by P1.
11. [ ] N3: the one-shot sites send the caching-off option and show zero cache writes on the
        fixed questions; the section writer, repair, screen stage 1, extract and chat keep
        their cache reads (shares recorded before and after).
12. [ ] Cost per standard run on the fixed questions meets O1 as the owner set it; any phase
        that raised cost or failed the owner's read was reverted and recorded.
13. [ ] The owner's read of the fixed questions' reports is recorded for every phase that
        changes a model or a judge (P1, P5, and P3 to P4 if the owner asks).
14. [ ] P4's repair template re-pin is recorded with its diff; no other pinned file changed.
15. [ ] Options scoping ran the fixed scoping question before and after and its cost per run
        is in the table (shared machinery carried the gains, or the gap is explained).
