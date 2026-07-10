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

### Grounding integrity through the redesign (Phase B)

9. [ ] Every claim in a v2 artefact still carries its full lane: typed annotation,
       verified-or-flagged citations, judge verdict (judged types), honesty flags —
       nothing weakened relative to 013's guarantees.
10. [ ] Claim spans bind to prose by exact validated offsets; prose outside claim spans
        carries no evidential assertion (judge-rubric line recorded in the ADR).
11. [ ] Pattern-count recomputation, gap grading + coverage base, flag-not-drop
        (incl. mixed/unclear directions) all hold on a replayed live-substrate run.
12. [ ] The conclusion-block front door exists, is grounded (cited to sources, never
        sibling blocks), and renders first on the surface.
13. [ ] ADR written: supersedes the 013 claims-are-the-prose emission; records the
        annotation-layer purpose statement and the connective-tissue line.

### Loop discipline (Phase C)

14. [ ] Baseline captured on both recorded projects BEFORE any prompt/model change.
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
