# Rubric: 046-longlist-refinement

The task is **done only if every box holds**. Terms, item numbers, rulings
(R1–R28), amendments and measures (M1–M9) are defined in [contract.md](contract.md).
This file does not restate them.

## Items (one box per group; each cites the contract's item numbers)

1. [ ] **Discovery at reader grain (items 1, 4, 9; R1, R2, R9, R14, R20).**
   Suggestions are named at reader grain, and their designs name no place
   and no institution of one country. Discovery receives the plan, the
   baseline, the seeds and the corpus digest, and no unit payload. The
   option count never exceeds the hard ceiling. A suggested seed can be
   folded and then shows as a variant. A user's option is never folded or
   renamed. At most one residual pass runs and its outcome is in
   `provenance`. Discovery mints no package. Variants are computed from
   members and shown on the card.
2. [ ] **Assignment (items 2, 3).** The new rule is in the prompt. Prompts
   carry short ids only. The flag reads "not stated in the abstract". The
   model tier is the mini model, or the move is justified by a recorded
   measurement.
3. [ ] **Typing and themes (items 7, 8, 26).** `lever_types_v2` is in
   force and each option records its taxonomy version. Typing receives the
   plan and the baseline. Typing and constrain batches run in parallel. The
   typing wire has no `lever_reason` and no `runner_up_reason`. The
   runner-up lever is served and shown. A typing failure keeps the previous
   typing. `theme` is a component of its own after `constrain` (R28): it
   holds included options only, it is not a spine step, `longlist` writes
   no theme, and `constrain` has no theme code.
4. [ ] **Constrain (items 5, 6, 10, 11, 12; R4, R21).** No place token
   reaches the prompt. Population overlap does not exclude. Silence about
   the target unit or the setting passes. A setting requirement excludes
   only a kind of action that cannot be delivered through the setting. The relevant screen
   accepts a stated pathway. The distinct screen sees the whole list. A
   discovered option's outcomes come from its members' tags. Constrain
   receives the baseline.
5. [ ] **The intervention profile (items 13, 14, 16; R3).** Each new
   record carries the three tags. The fingerprint includes the
   tagging-context hash and no place. The setting rule and the negative
   examples are in the prompt. The code pass folds setting labels and moves
   places to geography with a logged repair.
6. [ ] **Thinning (item 15; R17).** The three unit rules hold. Title-only
   documents are not profiled. Non-evidence documents are profiled. Each
   rule's count is in `provenance`. No rule reads a tag.
7. [ ] **Screening (items 10, 18, 23; R5, R15, R16, R18, R19).** The
   planning prompt keeps target unit, setting and geography apart. The
   screen input of a longlist run holds the wide target unit and the
   outcomes, and no setting, no place and no option design. An option
   search of a longlist walk runs `acquire` only (marked by
   `acquire_only` in its scope's context, AM4), the join is before the
   screen, and each document has one stage-1 screen row per longlist walk.
   Units come from the longlist scope and from add-walk scopes only (AM5).
   The add walk is as built in task 045, without ingest (AM1). No file of
   the Evidence search screen changes.
8. [ ] *Withdrawn by AM1 (item 20, the classify skip list for the add
   walk). The number is kept so that later numbers do not move.*
9. [ ] **Ingest (item 22; R13).** Neither chain contains
   `ingest_full_text`. The chat answers over a longlist from abstract
   chunks and its citations are labelled *abstract only*.
10. [ ] **Tried on (item 23).** Coverage counts members by population tag.
    The card shows the *tried on* line. The list has the facet. Neither
    filters or excludes.
11. [ ] **Small (item 26).** The sub-national table. No double full stop
    in the composed intent or criteria.

12a. [ ] **Amendments from the review.** Each amendment in contract
    § Amendments from the review holds (AM1, AM3, AM7, AM8 and AM9 as the
    owner accepted them on 2026-09-28). Where an amendment and an item above differ,
    the amendment wins. A record with null tags reads as "not tagged". The
    place removal is recorded in `provenance`.

## Cross-cutting

12. [ ] **The reuse rule (R16, AM1, AM3).** Under `evidence_search/`,
    outside the intervention profile's own files, the only edits are the
    optional `interventions_context` argument on the extract path
    (`extract.py`, `extraction_backend.py`) and the title-only rule of the
    selection-free path. The IOF and ICF payloads, prompts and fingerprints
    are byte-identical. `screen.py` has no source change. The existing
    Evidence search tests pass with no edit. The search loop, the search prompts, the
    synthesis backend and the baseline targets are unchanged.
13. [ ] `make verify` passes (okf-validate · test · typecheck · lint ·
    build · drift-check · prompt-guard).
14. [ ] Each prompt revision is re-pinned, and each round's diff is
    recorded with the finding that caused it (R27). The planned six are
    `task_agent_scoping_v4`, `longlist_suggest_v2`, `extract_interventions_v2`,
    `longlist_cluster_v2`, `lever_typing_v2`, `constrain_v2`; the theme and
    option design prompts changed only on a recorded finding. The Evidence
    search prompts and the longlist verbs prompt are unchanged.
15. [ ] **The staged check (R12, R24–R26).** Each stage's loop is recorded
    round by round (the change, the figures, the reading), ran at most five
    rounds, and was reported to the owner at its end. The prompts were
    tuned on the tuning set only; the check set was read and not tuned on.
    The planning replay ran on the seven questions. The replay ran on
    clones and left the seven stored tasks unchanged. Three live rapid runs
    ran (obesity, refugees, caregiving). M1 to M6 pass on the hand reading,
    or a failed measure is reported as failed with its read-back. M7 to M9
    are reported beside the pre-contract figures. Each figure was read back
    from a saved result file. The other four live runs ran only if the
    owner asked for them.
16. [ ] One reversible alembic revision adds three nullable columns, with
    a check constraint on the two that hold fixed values, and nothing else.
    No new table.
17. [ ] No approval-gated change beyond the contract's § Constraints.
18. [ ] No generated files or secrets edited by hand.
19. [ ] No tests deleted, skipped or weakened without written
    justification.
20. [ ] Each spec change in contract § Spec changes is applied only if the
    owner accepted its wording, with the owner's words quoted and one line
    in `docs/specs/log.md`.
21. [ ] `docs/deferred.md` carries: a new entry for the system-level cost
    and latency task (items 21 and 24, a screen memo across scopes, L1,
    L3); the thin baselines added to § Synthesis optimisation as a second
    case; the full-text fetch for shortlisted options and its failure rate
    noted for task 3; user-visible loop budgets; the known limits of R22
    (provider-written abstracts, duplicates without a DOI, the untested
    guesses path, the process-wide option-search pool, empty OpenAlex
    queries). Open question 4 is marked closed.
22. [ ] ADR 0040 written, Accepted, with the rollback commands.
23. [ ] The Tier-4 review stack ran (contract verifier · `/code-review
    medium` · one security lane · `/simplify` · adversarial at contract and
    plan · human deep review). Findings are adjudicated in
    [verification.md](verification.md).

## Amendment 2 (2026-09-29)

Rulings R34–R52 are in [contract.md](contract.md) § Amendment 2; the design
detail and the loop checks are in [amendment-2-final.md](amendment-2-final.md)
(cited below as "final"). R35 is withdrawn and has no box. The boxes above
stay as written; where a box below and a box above differ, the box below
wins for amendment 2's work.

### Items (one box per group; each cites the contract's item numbers)

24. [ ] **The plan (R34; R35 withdrawn).** In the plan model: the kind
    `boundary` (the screen word stays "requirement") and the kind
    `consideration` with `aspect` (any of the eight lines, "who decides"
    included) and `hard`; no plan slot "Who decides". In the planning replay
    record: a capacity statement is a consideration, never a preference; a
    deadline names "time to set up", or "time to effect" when the user
    speaks of results; a sentence that names several things gives one
    consideration per line; the answer about who can act is a consideration
    on "who decides"; the aim keeps the user's words and its outcomes are
    tagged *assumed*.
25. [ ] **The profile component (R37; Q19).** A component of its own
    between `longlist` and `constrain`, not a spine step: the chain in
    `runtime/scoping_plan.py`, the registry, the harness graph, the plan
    mapping, a stage key on the run stream and the stage in
    `runProgress.ts` all know it, as they know `theme`. It reads all options
    of the latest longlist result and writes the profile into that result.
    `longlist` writes no ambition. A test shows that a failed profile step
    leaves the longlist with no profile and constrain with no labels.
26. [ ] **"What it would take" (R36, R37).** Each option has eight lines:
    cost, time to set up, time to effect, workforce requirements, who decides,
    dependencies, coordination requirements, delivery complexity. Each line
    has one sentence for every option; no "cannot judge" value (M10,
    reported). One call per line reads the whole list. Marks follow way A
    (only an option that clearly stands out has one); who decides and
    dependencies have no mark. No basis mark is produced or stored.
27. [ ] **Add an option (R51).** Adding an option makes the lines of the
    new option only, one call per line, with the other options' sentences
    and marks for that line as context. A test shows that no other option's
    mark changes. The round record shows that the new option's marks agree
    with a full whole-list run in most cases.
28. [ ] **Who decides and the authority label (R38).** The line names one
    body with its full name and the place it assumes, and a legal means only
    when the baseline or a document states it. Constrain gives the authority
    label (*within your power* · *needs action by <body>* · *unclear*) from
    a consideration on "who decides" that is not hard; with no such
    consideration, no label. A hard one can exclude. The label is a filter
    on the list, not the sort order.
29. [ ] **Limits and exclusions (R50).** A hard consideration on any line
    other than "who decides" never excludes: the option gets a limit label
    ("may not fit your limit on …") with the line's sentence as the reason.
    Every exclusion names a clear failure; mixed or missing information
    keeps the option. No reasoned guess is written for a preference about
    an aspect. Read on the hard-requirement test replay (M11, reported).
30. [ ] **Ambition (R40).** Ambition is made by its own call over the whole
    list, relative (Smaller · Bigger · no mark), with one sentence against
    the baseline. No option is called "do minimum". Lever typing writes no
    `ambition` and no `ambition_reason`. On the card, ambition is in "What it
    is", after the lever line.
31. [ ] **The delivery setting (R41).** One call over the whole list writes
    one main setting and at most one more per option, empty for a
    system-level instrument. No fixed list of settings in code or prompt.
    The Setting facet reads it; each document keeps its own words as
    "studied in"; on the card it is in "What it is". M12 (reported).
32. [ ] **Outcome counts (R42).** Per option: documents that evaluate it and,
    among them, documents for each plan outcome, counted from the existing
    `outcome_tag`. No new field, no change to the profile prompt. No
    direction, size or verdict anywhere. The counts are in "What the
    evidence base holds so far".
33. [ ] **The reader and the words (R43, R44).** List rows carry no marks.
    "What it would take" is collapsible and collapsed when the card opens:
    collapsed, a row of eight cells (line name above, level word below; the
    cells open nothing); expanded, the eight lines with name, mark and
    sentence. A line with no mark shows no word. The grid's columns come
    from the line the reader chooses; "Middle" appears only as a grid column
    head. No compare table. The heading carries the estimate label; no
    sentence ends with "a guess rather than evidence". **The words on the
    screen are the decided words:** the line names of box 26 and the level
    words Cheaper · Costlier, Quicker · Slower, Lower · Higher, Simpler ·
    More complex, Smaller · Bigger; none of "less than most", "like most",
    "more than most". Checked in the vitest tests and on the browser check.
34. [ ] **Out of the first version (R39).** No acceptability line, no
    burden line, no legal-change line and no "powers" line in code, prompt
    or screen.

### Cross-cutting

35. [ ] **Every new or changed prompt went through a refine loop (R48).**
    `task_agent_scoping_v5`, the line prompt(s), the add-one variant, the
    ambition prompt, the setting prompt, `lever_typing_v3`, `constrain_v3`:
    each has its rounds recorded in `evidence/rounds/` (the change, the
    finding that caused it, the figures, the read-back), at most five
    rounds, tuning set then one read of the check set, and a report to the
    owner. Each is re-pinned in `scripts/prompt_hashes.json`.
    `extract_interventions` is unchanged.
36. [ ] **No fixed lists, bands or anchor examples (R37).** No line,
    ambition or setting prompt holds a fixed list of answers, a
    low/medium/high band, or an example option from a named domain. The
    lead's three guards are not in the code.
37. [ ] **The known faults were tested (final § 6.1).** A round record
    reads each of the six faults (setting "none" where a setting exists; a
    mark its sentence contradicts; no mark where the sentence lists much;
    a law named by title and year; two bodies or an acronym in "who
    decides"; a sentence that answers another question) and states the
    result on the tuning set.
38. [ ] **The overlap of coordination requirements with delivery complexity
    was measured** with the decided coordination question, and the figure is
    in `verification.md` beside the earlier figures of final § 6.3, each read
    back from a saved file.
39. [ ] **No code handles old longlists (R52).** No branch, migration or
    read-model rule for old ambition words or for a longlist with no
    profile made by an earlier development iteration.
40. [ ] **Migration (R45).** No alembic revision, or exactly one for the
    whole amendment with its reason recorded in `verification.md`, a
    round-trip test, and full `make verify` at its phase. No new table.
41. [ ] **Measures and time (R46, R49).** M8, M10, M11, M12 and M14 are
    reported in `verification.md`, read back from saved files; none is used
    as a pass condition. The walk has no side branch.
42. [ ] **Task 3 principle recorded, not built (R47).** The shortlist
    principle is in the spec-change list for the owner's wording; no
    shortlist code is written. `docs/deferred.md` carries burden, a grounded
    legal-change line, the outcome direction for task 3 and the two-outcome
    count limit.
43. [ ] **Spec changes of amendment 2**, the new component included, are
    applied only with the owner's accepted wording, with one line each in
    `docs/specs/log.md`.
44. [ ] **Gates.** Full `make verify` passes at Phase 9.0 and Phase 14; the
    adversarial review of amendment 2 ran (owner: "not yet but we will
    do."), and its findings are adjudicated in `verification.md`.
