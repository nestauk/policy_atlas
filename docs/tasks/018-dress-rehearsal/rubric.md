# Rubric: 018-dress-rehearsal

The task is **done only if every box holds** — otherwise it is in progress, not done.

## Standard criteria

1. [ ] Implementation satisfies [contract.md](contract.md).
2. [ ] `make verify` passes; declared manual/live checks pass.
3. [ ] No approval-gated change snuck in unapproved (the direction-rename migration and
       the contingent junk-judge prompt surface are the two pre-approved gate items).
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification.
6. [ ] Verification evidence recorded ([verification.md](verification.md)).
7. [ ] Known gaps and deferred seams listed (gap → [docs/deferred.md](../../deferred.md)).
8. [ ] Review stack ran per Tier 3 as adapted by the contract's § How this slice runs
       (Phase A/B diffs: full stack; Phase C prompts: evidence-trail review), or skipped
       with written justification.

## Slice-specific criteria

### Output quality + grounding integrity (Phase B)

9. [ ] The prompt-vs-structural fork was decided on recorded evidence (cheap probe +
       research + side-by-side options) at the plan 🛑 — not defaulted; the ADR records
       the fork, evidence and decision.
10. [ ] Every claim in the shipped artefact still carries its full lane: typed
        annotation, verified-or-flagged citations, judge verdict (judged types), honesty
        flags — nothing weakened relative to 013's guarantees, under whichever option won.
11. [ ] If Option B: claim spans bind to prose by exact validated offsets; prose outside
        claim spans carries no evidential assertion (judge-rubric line recorded in the
        ADR); the annotation layer is re-proven on a replayed live-substrate run.
12. [ ] Pattern-count recomputation, gap grading + coverage base, flag-not-drop
        (incl. mixed/unclear directions) all hold on a replayed live-substrate run.
13. [ ] The grounded key-findings block (produced last, shown first, conditional on
        headline claims) and the separate bottom conclusions block (evidence-descriptive,
        no recommendations) both exist as distinct grounded blocks; spec flow-back
        (capability.md + provenance-grounding.md + log entry) recorded.
13a. [ ] Writer-envelope fields (year / evidence type / appraisal label / author
        institution / venue …) were adopted per A/B replay evidence — any field without
        evidence of benefit stayed out (noise guard); judge envelope v2 changes carry
        before/after evidence.

### Loop discipline (Phase C)

14. [ ] Baseline-0 (017-slice runs `91d2d684`/`128c0a81`, pre-model-refresh, historical
        reference) and baseline-1 (post-Phase-A replay, unchanged prompts — the loop
        baseline) both captured; prompt refinements judged against baseline-1 only.
15. [ ] Every adopted prompt change carries before/after replay evidence (trace
        pointers); reverted changes noted.
16. [ ] Anti-overfit pins recorded: planner replay across all 7 v2-question-taxonomy
        categories; extraction/synthesis spot-checks on the non-mission recorded project.
17. [ ] The RETRO's extraction rules are validated (kept/amended/replaced) by replay —
        not still an unvalidated claim. Junk judge built only if its trigger fired, with
        flag-not-drop accounting.

### Riders (Phase A)

18. [ ] Model refresh complete; no `gpt-5-mini` constant remains; classify runs
        5.4-mini @ xhigh via a provider-neutral effort knob; demo-branch model/cap
        monkeypatches retired.
19. [ ] Direction rename migrated (up/down evidenced); no `positive`/`negative`
        direction value reachable in code, prompts, DB, or surface labels.
20. [ ] Standard×standard re-seeded from a fresh measured run; displayed band = measured
        band; select/extract/group provably skipped at standard.
21. [ ] Chain runs are Langfuse-session-correlated; token usage + per-component
        wall-clock + in/out counts persist durably from every run.
22. [ ] Planner history is native message arrays, provider-neutral (no
        OpenAI-specific conversation state), bounds/sanitisation preserved.

### Rehearsal (terminal)

23. [ ] Live standard run on a Nesta-mission question completes on the updated surface
        inside the displayed band, with honest labels visible and no invented/empty
        surface content (cards hide rather than fake — RETRO locked decision).
24. [ ] The artefact reads as authored prose answering the question (user judgment,
        recorded), with the annotation layer rendered in the prose.
25. [ ] Rehearsal record in verification.md: project id, artefact id, wall-clock,
        trace pointers, surface state; flow-back note on the loop protocol for the
        eval slice.
