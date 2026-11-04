# Rubric: 058-perceived-latency

Core completion criteria. The task is **done only if every box holds**, otherwise it is in
progress. Item numbers point at [contract.md](contract.md): N1 to N26, D1 to D14, G1 to G7,
S1 to S5. Terms are defined in the contract's § Terms. Looks are judged against
[design-annex.md](design-annex.md) at its cited version, never against this file.

Core
1. [ ] Implementation satisfies [contract.md](contract.md) for every need N1 to N26.
2. [ ] `make verify` passes at the build-open baseline, after the backend frames phase, after
       the frontend phases and at the step-6 exit; `make drift-check` passes after type
       regeneration.
3. [ ] No approval-gated change beyond G1 to G7: no schema, no dependency, no CI or prod
       config change; the public-interface additions are exactly those G1 lists; the
       prompt-hash re-pin covers only the final turn's call shape and the time-band table.
4. [ ] No generated files or secrets edited by hand.
5. [ ] No tests deleted, skipped or weakened without written justification (the client
       vocabulary tests N17 removes are listed with the server-side test that replaces each).
6. [ ] Verification evidence recorded ([verification.md](verification.md)) as the contract's
       § Verification evidence lists, read from saved results.
7. [ ] Known gaps and deferred seams listed in [docs/deferred.md](../../deferred.md): cancel
       (D7), computed bands (D6), per-option reading counts (D9), the section proposal's place
       (D12), telemetry (D13), email (D14).
8. [ ] Required Tier 3 review stack ran (contract verifier · one security lane · the
       heterogeneous pair · the `frontend-designer` design lane · simplification) or skipped
       with written justification; the ADR is Accepted.

Activity line (N1 to N5, D2)
9. [ ] N1: one tick per 500 ms per stage under a burst, carrying the latest values; every
       step has a verb (test); the screening line moves on a live run.
10. [ ] N2: every loop with a known total registers it; batch stages say "batch n of M";
        acquire and screen stage 1 say "n so far" with the round; the option-search join
        publishes; fetch notes are no longer labelled acquire.
11. [ ] N3: the writer publishes the section line and the action line in the contract's
        sequence, with the model's query verbatim.
12. [ ] N4: a client connecting mid-stage receives the last tick per stage first; a reload
        shows the activity line within one poll.
13. [ ] N5: the card follows the annex § The running card (direction C): rows, the dot's
        1.5 s stop, the 120 s "Still working on this step" line, no counter, no raw note.

Streaming (N6 to N10, D1, D3)
14. [ ] N6: the final turn streams as strict `json_schema`, deltas are published, the parsed
        object continues unchanged into the claims path, the fallback runs once on failure
        and is counted; strict acceptance checked on Terra and Luna.
15. [ ] N7: the two ephemeral frames are in the union and the spec; the reducer appends,
        marks, replaces, and rebuilds identically from a replay with no deltas.
16. [ ] N8: the Result tab's states match annex scene 6, including the blur and cross-fade
        with nothing marked afterwards, the key-findings note, the footer states, and
        reduce motion.
17. [ ] N9: the planner turn streams for both profiles; the Agent tab fills the pending turn
        and shows "Drafting the plan"; the opening turn streams in the Agent tab.
18. [ ] N10: the clarifying question renders above its chips; chips survive a reload.

Result tab, strip, sidebar, tabs (N11 to N16, D8)
19. [ ] N11: the three pre-writing states (empty, re-run notice with no button, paused) match
        annex scenes 5 and 8; "Preparing your results" is gone.
20. [ ] N12: the run strip with the Task Agent mark is on every non-Agent tab; the mark opens
        the sidebar in place; below `md` it goes to Agent; the paused state is on the strip
        and the separate paused banner is gone; the done state is green.
21. [ ] N13: the sidebar carries the real stream: run line, thread tail, an answerable
        check-in, the locked composer; plan links open the plan; the paused strip's mark opens
        the sidebar on the check-in.
22. [ ] N14: tab dots appear for new content and clear on visit; the title changes on
        completion; `degraded` opens the report.
23. [ ] N15: the task list row shows the stage and elapsed time; the "Plan" control opens the
        plan from any tab; Escape closes it; the reconnecting banner is mounted.
24. [ ] N16: Sources defaults to "All" until screening completes; per-document stages refresh
        the Sources queries on ticks.

Copy (N17, D4, D5)
25. [ ] N17: every public key has a server label, blurb and verb in the plain voice; the
        client has no label literal; the Options scoping blurbs are rewritten; count keys are
        chosen per stage; the spec lists all 19 keys (S1).

Planning conversation and check-ins (N18 to N21, D10)
26. [ ] N18: the stepper is client-computed; the part card is a radio list with the primary
        first and its reason under it, no label, no pre-selection; inputs are inside the
        card; settled parts collapse to one line; both plan cards start the run; the two
        scoping parts render.
27. [ ] N19: the check-in matches annex scene 12; one stop; "You chose" comes from the
        durable frame; the card reads PAUSED while a check-in waits.
28. [ ] N20: time bands agree; no literal asterisks; plan edits survive leaving the tab.
29. [ ] N21: the scoping card shows "n of M searches done · k sources so far".

Scoping Result tab (N22 to N24, D9)
30. [ ] N22: the provisional longlist read returns the suggested rows with `provisional`
        after suggest; `has_longlist` semantics unchanged.
31. [ ] N23: `RunOut.option_id` is set on child walks; child stage frames are kept per walk;
        the longlist refreshes on child `run.status`.
32. [ ] N24: the longlist during the build matches annex scene 15: per-row search status,
        stage lines, the fold, new rows, waves, shortlist marks, "provisional" until the end.

Measurement, mock, polish (N25, N26, D11, G7)
33. [ ] N25: before and after measures on the fixed questions on laptop and staging, read
        from saved results; no silent gap over 30 s on a healthy run; first delta within 5 s
        of the writing turn; the cost delta per report recorded against the $0.03 estimate.
34. [ ] N26: the mock API returns parts, suggestions, a real check-in, child frames, ticks,
        deltas and revising frames; both journeys assert the annex's states, including a
        reload mid-run.
35. [ ] D11: polish passes complete at build end and after review (agent, then owner, within
        the round budget), the annex's polish log filled, the owner's sign-off recorded in
        `verification.md`, live-dev screenshots of every changed surface attached.
