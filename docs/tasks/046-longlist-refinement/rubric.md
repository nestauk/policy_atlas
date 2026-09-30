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

Rulings R34–R53 are in [contract.md](contract.md) § Amendment 2; the design
detail and the loop checks are in [amendment-2-final.md](amendment-2-final.md)
("final" below). R35, R50 and R51 are withdrawn. The boxes above stay as
written; where a box below and a box above differ, the box below wins for
amendment 2's work. Where a box measures, it names the threshold; a measure
that is not a loop's stop measure is reported, not passed (R48, R49).

### Items (one box per group; each cites the contract's item numbers)

24. [ ] **The plan (R34; R35 withdrawn).** In `runtime/scoping_plan.py`:
    the kinds are `boundary`, `consideration` (with `aspect` whose values are
    the eight line keys of box 40 or `transferability`, and `hard`),
    `preference` and `evidence_restriction`; `CHECKED_AT_BY_KIND` maps
    `boundary` to `longlist` and `consideration` to `assessment`, with no new
    `CheckedAt` value; no plan slot "Who decides"; no new aim field. The plan read model
    and the plan screen show `boundary` (screen word "requirement") and
    `consideration`. In the planning-loop round record, on the seven
    questions and the probe: every statement lands in the right kind and
    line (a capacity → a consideration; a deadline → "time to set up", or
    "time to effect" when the user speaks of results; one consideration per
    line; the answer about who can act → a consideration on "who decides").
    Threshold (the 9L stop measure): all, read by hand.
25. [ ] **The component `option_profile` (R37).** A spine component between
    `longlist` and `constrain`. The chain in `runtime/scoping_plan.py`, the
    registry (`run_spec.py`), the harness graph, the plan mapping
    (`task_plan.py`), `LLM_BEARING_COMPONENTS` (`runner.py`), the stage key
    `option_profile` on the run stream and the stage in `runProgress.ts` all
    know it, as they know `theme`. Lever typing is in `option_profile` as
    built, with its keep-previous rule for a failed or invalid typing batch;
    its data stays in the same `longlist_result` keys (`provenance`
    `lever_reason`, `runner_up`, `typing`, `prompt_versions.typing`,
    `models.typing`; `counts.typing_invalid`), and a test shows a stub run's
    lever types and typing keys are the same as before the move. `longlist`
    has no typing code and writes no ambition. There is no code path for a
    built list with no profile; a line, ambition or setting call that fails
    after the existing retry fails the step (a test shows it). Each line call gets the plan
    (Where only for "who decides"), the baseline, and per option its design
    and at most 5 records by role; the caps are named constants; the model
    is the judgment model.
26. [ ] **"What it would take" (R36).** Each option has eight lines with a
    sentence each: cost, time to set up, time to effect, workforce
    requirements, who decides, dependencies, coordination requirements,
    delivery complexity. One call per line reads the whole list. Marks follow
    way A; who decides and dependencies have no mark. No "cannot judge"
    value; no basis mark in the wire or the storage. M10 (every option has a
    sentence on every line) is reported.
27. [ ] *Withdrawn with R51 (the add-one form). The number is kept.*
28. [ ] **Who decides and the authority label (R38).** The line names one
    body by its full name and the country from the plan's Where, and a legal
    means only when the baseline or a document states it (read on the
    tuning set). Constrain reads that line and no other place text (its
    other plan data stays stripped, `constrain.py:_plan_data`). Constrain
    gives *within your power* · *needs action by <body>* · *unclear* from the
    user's consideration on "who decides", as one labelled entry in
    `longlist_result.judgements`, never in `option_profile`; with none, no
    entry. The option read model serves it from `judgements`. **No
    exclusion comes from "who decides" or from any consideration** (a test,
    and the 13L round record). The label is a filter on the list, not the
    sort order. M11 on the hard-requirement data: threshold 9 of 10 options
    (the 13L stop measure).
29. [ ] *Withdrawn with R50 (the limit label). The number is kept.*
30. [ ] **Ambition (R40).** One call over the whole list in
    `option_profile`: relative (Smaller · Bigger · no mark) with one sentence
    against the baseline; no option called "do minimum". Stored in
    `option.ambition` (mark `less`, `more` or null) and
    `option.ambition_reason` (sentence). Lever typing writes no
    ambition. `ambition_bands`, the three bands, group by ambition and the
    ambition word on a list row are gone from the read model, the repository
    and the views. On the card, ambition is in "What it is", after the lever
    line.
31. [ ] **The delivery setting (R41).** One call over the whole list writes
    one main setting and at most one more per option, empty for a
    system-level instrument; stored in `longlist_result.option_profile`. No
    fixed list of settings in code or prompt. The Setting facet reads it; on
    the card it is in "What it is". M12 (at most 10 labels, no place or body name) is
    reported.
32. [ ] **Outcome counts (R42).** Per option, in documents: the documents
    that evaluate it and, among them, the documents for each plan outcome (a
    document counts when one of its evaluating records has that
    `outcome_tag`; a document with records on two outcomes counts for both).
    A test pins this rule. No new field; `extract_interventions` unchanged;
    no direction, size or verdict anywhere. Shown in "What the evidence base
    holds so far".
33. [ ] **The reader and the words (R43, R44).** List rows carry no marks and
    no ambition word; the list groups by theme and lever type only. "What it
    would take" is collapsible and collapsed when the card opens: collapsed,
    a row of eight cells (line name above, level word below; the cells open
    nothing); expanded, the eight lines with name, mark and sentence; hidden
    for an added option before a rebuild. A line with no mark shows no word.
    The grid's columns come from the line the reader chooses: lower word ·
    Middle · higher word, and "Untagged" for an option with no profile. No
    compare table. The heading carries the estimate label; no sentence ends
    with "a guess rather than evidence". **The words on the screen are the
    decided words:** the line names of box 26 and the level words Cheaper ·
    Costlier, Quicker · Slower, Lower · Higher, Simpler · More complex,
    Smaller · Bigger; none of "less than most", "like most", "more than
    most". Checked in the vitest tests and on the browser check.
34. [ ] **Out of the first version (R39).** No acceptability line, no
    burden line, no legal-change line and no "powers" line in code, prompt
    or screen.
45. [ ] **The rename (R53).** No product code or prompt holds the kind
    `requirement`. The one-off script is in the gitignored evidence folder;
    after it ran, a round record shows the clones' test plans read as valid
    plans and their statements about who can act are considerations on
    `who_decides`.

### Cross-cutting

35. [ ] **Every new or changed prompt went through a refine loop (R48).**
    `task_agent_scoping_v5`, the line prompt(s), the ambition prompt, the
    setting prompt, lever typing (moved), `constrain_v3`: each has its
    rounds in `evidence/rounds/` (the change, the finding that caused it, the
    figures, the read-back), names one stop measure, ran at most five
    rounds, was tuned on the tuning set and read once on the check set, and
    was reported to the owner. Each is re-pinned in
    `scripts/prompt_hashes.json`. `extract_interventions` is unchanged.
36. [ ] **No fixed lists, bands or anchor examples (R37).** No line,
    ambition or setting prompt holds a fixed list of answers, a
    low/medium/high band, or an example option from a named domain. The
    lead's three guards are not in the code.
37. [ ] **The known faults were tested (final § 6.1).** A 12L round record
    reads each of the six faults on the tuning set and states the count.
    Threshold (the 12L stop measure): none of the six, read by hand.
38. [ ] **The overlap of coordination requirements with delivery complexity
    was measured** with the decided coordination question, and the figure
    (same level; opposite) is in `verification.md` beside the figures of
    final § 6.3, read back from a saved file. Reported.
39. [ ] **No code handles old longlists (R52).** No branch, migration or
    read-model rule for old ambition words, old plan kinds or a longlist
    with no profile made by an earlier development iteration.
40. [ ] **Migration (R45).** Exactly one reversible alembic revision on
    `d8f3b6a2c4e1`: the JSON column `longlist_result.option_profile`, keyed
    by option id and design version; per option the line keys `cost`,
    `time_to_set_up`, `time_to_effect`, `workforce`, `who_decides`,
    `dependencies`, `coordination`, `delivery_complexity`, each with a
    sentence and a mark stored as `less`, `more` or null, and the setting; no
    entry for an option not yet profiled; a round-trip test; full `make verify` at Phase 10.
    No other schema change; no new table.
41. [ ] **Measures and time (R46, R49).** M8, M10, M12 and M14 are reported
    in `verification.md`, read back from saved files; M11 is the 13L stop
    measure (box 28). The walk has no side branch.
42. [ ] **Task 3 principle recorded, not built (R47).** The shortlist
    principle is in the spec-change list for the owner's wording; no
    shortlist code and no limit label are written. `docs/deferred.md`
    carries burden, a grounded legal-change line, the outcome direction and
    the limits for task 3, and building an added option in place.
43. [ ] **Spec changes of amendment 2**, `option_profile` included, are
    applied only with the owner's accepted wording, with one line each in
    `docs/specs/log.md`.
44. [ ] **Gates.** Full `make verify` passes at Phases 9.0, 10 and 14;
    Phases 9 and 12a also pass `make openapi-sync` and `make frontend-verify`.
    ADR 0040 is amended (walk, typing in `option_profile`, place exception)
    in its own commit before Phase 12a.
46. [ ] **The contract's corrected lines hold.** The OpenAPI diff shows the
    removal of `ambition_bands` and the additions of final § 3 and nothing
    else; `verification.md` records the rollback as the contract states it
    (not additive) and the known limits of final § 2.10.

## Amendment 3

Rulings R54–R75 are in [contract.md](contract.md) § Amendment 3; the design
detail, the loop checks and the questions are in
[amendment-3-final.md](amendment-3-final.md) ("final 3" below). The boxes
above stay as written; where a box below and a box above differ, the box
below wins for amendment 3's work. It replaces, for that work (lead, A11):
box 1's "a suggested seed … shows as a variant" and "Variants are computed
from members and shown on the card" (R63); box 3's "The runner-up lever is
served and shown" (R62); box 10 (tried on by population tag; neither
filters) (R54, R57); box 15's statement that the stage prompts other than
those named do not change, for `extract_interventions`, the IOF/ICF field
descriptions and the place rule (R69, R74, R75); box 30's "ambition is in
'What it is'" (R68); box 32's rule on evaluating documents (R56); box 33's
"a line with no mark shows no word" and eight cells (R65). Where a box
measures, it names the threshold; a measure that is not a loop's stop measure
is reported, not passed (R69). Every question of final 3 § 7.2 is answered
(Q24 by the owner, Q20, Q22, Q23, Q25 by the lead).

### Items

47. [ ] **Tried on (R54, R55).** One folding call over the list's distinct
    `unit` words (read from the whole list's coverage) writes word → kind, on
    the mini model, in `option_profile`, with the plan's target unit and
    outcomes as reference; the maps are stored at list level in
    `longlist_result.option_profile` under `folds`; `option_profile` writes
    documents per kind per option into coverage `tried_on_kinds` (a test: two
    words of one kind in one document count one document). The coverage
    builder applies the stored maps on a merge and for an added option (a
    test); a word the map lacks keeps its own text as kind. The card shows
    one "Tried on" line, target unit first, all kinds, with counts; no
    "Populations" line, no record-level "Settings" or "Tried on" line. The
    record tags and their counts are kept in coverage and not shown; the old
    `tried_on` and record `settings` keys stay for constrain
    (`constrain.py:360-384`) and no read model serves them. No fixed list of
    kinds in code or prompt. **M6's replacement** (M6 retired, lead Q9): on
    the live runs, Tried on shows kinds beyond the plan's target unit where
    the evidence has them (read by hand; reported).
48. [ ] **Measures and the outcomes table (R55, R56, R64).** A second folding
    call writes word → kind for the records' `outcome` words (one kind per
    record). The card's evidence section holds one table: a row per plan
    outcome with its "serves" mark from `outcomes_served`, and a row per other
    Measures kind; columns "documents of any role" and "evaluated". Tests
    pin (lead, A4): a plan row counts records with that `outcome_tag`, plus
    records tagged `other` or null whose kind is that outcome's own text; a
    kind row counts only `other`/null records; one document counts once on
    one row. No "What it is for" section, no "Outcomes measured" line
    (vitest).
49. [ ] **Counts over any role (R56).** A plan outcome's count includes a
    document whose only member with that outcome is `described`,
    `recommended` or `mentioned`; the evaluated count counts `evaluated`
    members only; DOI collapse as before (the old "described counts for
    nothing" test replaced with a written reason).
50. [ ] **The list's facets (R57).** Setting, Tried on and Where tried carry
    labels only (vitest: no digit in a chip); Tried on and Where tried (top
    level) filter the list as Setting does; a country chip also matches a
    document under "multiple countries" whose `study_country` holds that
    country (lead, Q22; a vitest); each folds after 8 chips; no Measures
    facet (vitest).
51. [ ] **The authority label's rule unchanged (R58).** The label shows only
    with a consideration on who can act; box 28's tests are edited for the
    label's new place (`OptionCard.test.tsx:241-259`) and listed in
    `verification.md`'s edited-tests section (lead, B14); the facet shows only
    when an option has a label.
52. [ ] **Where tried (R59, R72).** No `WHERE_GROUPS`, `COMPARABLE_LABEL`,
    `OECD_CODES`, `OECD_MARKERS`, `countries_in`, `where_group` or
    `where_labels` in product code; no "comparable" or "OECD" as a group label
    or heading (the level below may show the record's text: lead, A3).
    Coverage gives per document one top level from `study_country`: a country
    · "multiple countries" · "other" · "not stated", and the level below as
    `study_geography` as written. Tests pin: one country → that country;
    two or more countries in `study_country` ("United Kingdom; United
    States") or "multiple" → "multiple countries" (derived in code, Q22);
    case folded only ("united kingdom" = "United Kingdom", Q23); a place stated with an
    empty `study_country` → "other"; nothing stated → "not stated"; a document
    whose records give two countries → "multiple countries", both texts
    below; no read of publisher, journal, institution or publication country.
    The facet shows the top level with no counts; the card both levels with
    counts.
53. [ ] **The "not stated" check (R59).** A round record gives, on the three
    live lists, the records with "not stated", how many abstracts name the
    place of the study, and the faults (read by hand), reading
    `study_geography` and `study_country`. Reported. A fault leads to a round
    of the record prompt's loop (box 63).
54. [ ] **Grid (R60).** `CELL_LIMIT` is 4 in `LonglistGrid.tsx`; a vitest
    shows the fold at 5 options in a cell.
55. [ ] **Header (R61).** No `SnapshotCells` and no depth chip on the card;
    the evidence section carries the grey note "Read from titles and
    abstracts only".
56. [ ] **Lever line (R62).** "Lever:" with the primary type, "with" the
    secondary types, the reason sentence under it; no "also touches"; no
    runner-up line on the card (vitest).
57. [ ] **Examples from `programme_name` (R63).** `extract_interventions`
    writes `programme_name` on each record; coverage lists the option's
    distinct programme names with document counts, at most 5, empty allowed;
    served as `examples`; coverage has no `variants` key and keeps the folded
    seeds' names under `folded`; "also found as" joins merged duplicates and
    folded seeds (lead, A2); the card heading is "Examples"; no folding call
    and no cluster-prompt change for examples. The 16R read: on the tuning
    set every non-null `programme_name` is a proper name the abstract gives
    **for this intervention**, not one it sits within (lead, A13, B19).
    Threshold: all. Misses on the check set reported.
58. [ ] **Collapsed row (R65).** Collapsed, **seven cells**: Ambition, then
    cost, time to set up, time to effect, workforce, coordination, delivery
    complexity; no cell for who decides or dependencies; every cell shows a
    word, "Middle" for no mark, also on a line with few or no marks; a blank
    cell only for an option with no profile (vitest). Expanded, the table's
    first row is Ambition.
59. [ ] **Checks (R66).** The user's boundaries and preferences first, each
    verdict as a word with its colour; the three built-in checks as one line
    when all pass, in full when one fails; no transferability line (vitest).
60. [ ] **Documents (R67, R68).** One entry per document (a test: the same DOI
    under two snapshot ids gives one entry, and the task's own row opens the
    dossier); evaluated first, then by quality; the highest role under the
    option, the top-level place and `year` (from the snapshot metadata) on
    `OptionDocumentOut`; no HTML entity in a title (a test); the card shows a
    linked title and one grey meta line, no chips (the "inherited" chip
    included), five documents then "Show all N", and "No documents found
    yet." with none (vitest).
61. [ ] **The dossier from the card (R67).** A document title on the card
    opens the Evidence search source dossier (`SourceDossier`), not the
    citation panel (vitest); a document with no row in this task shows its
    title as plain text; nothing else on the card opens the dossier. On an
    options-scoping task the findings slot is named "In this option" when
    opened from a card and shows that option's record (intervention name,
    setting, tried on, outcomes measured, where, role), each record in its own
    words, several records each shown; a document with no record under the
    option shows its findings (lead, B8); opened from the Sources tab it shows
    the document's records, one per option holding it. On an Evidence search
    task the slot is unchanged (a vitest for each case, and the browser
    check).
62. [ ] **The layout and the critique items (R68).** The card's parts are in
    the order of final 3 § 2.5; ambition is the first row of "What it would
    take"; its label reads "Policy Atlas's estimate"; no "Where it came from"
    section; origin and relations on the header's grey line. At 16 px, not
    `text-meta` (lead, A10): every sentence of the lines, the abstracts note,
    "also found as", the design features, the lever reason (vitest on the
    classes).
67. [ ] **Migration (R71).** Exactly one reversible alembic revision on
    `e9a4c1f7b3d2`: nullable Text columns `intervention_profile_record.
    programme_name` and `study_country`; `population` → `unit` and
    `population_tag` → `unit_tag` (check constraint renamed with it) on
    `intervention_profile_record`; `population` → `unit` on
    `intervention_outcome_finding` and `implementation_context_finding`; the
    union view recreated with `unit`; a round-trip test; full `make verify` at
    Phase 16. No other schema change; no new table. **Production:** the
    revision needs no re-extraction (no version change on the finding
    records, Q24); `verification.md` records the downgrade path for
    production (`alembic downgrade -1`, the previous image).
68. [ ] **The authority label beside "Who decides" (R70).** In "What it
    would take", the "Who decides" row carries the label word with its colour,
    then the sentence, only when the option has an authority entry; no
    authority line in "What it is"; the Who can act facet unchanged (vitest).
69. [ ] **`study_country` (R72; lead, Q22, Q23).** The record wire, the
    writer and the column carry `study_country`; the prompt fixes the form:
    every named country, separated, each as its short English name
    ("United Kingdom", not "UK"), England, Scotland, Wales and Northern
    Ireland as "United Kingdom". The 16R read on the tuning set: the country
    of the stated place ("Hamburg" → Germany), every named country listed,
    "multiple" for a group, empty when nothing is stated, no short form or
    UK nation as a country. Threshold: all records read, no wrong country. Records
    by `study_country` value reported per list.
70. [ ] **`unit` throughout (R73, R75).** No product code, wire, prompt or
    read model uses `population` or `population_tag` for the intervention
    record or the two finding records (a grep over `backend/src` and
    `frontend/src`, the words "population" in prose aside); the intervention
    record's `unit` description reads "who or what the intervention was
    delivered to: people, organisations, sites or things"; the IOF/ICF
    prompts carry the same definition; the findings view label reads the
    new word. The 16W diff is words only, read by the lead and recorded;
    hashes re-pinned; no replay; **no version change** on the finding records
    (their schema and prompt versions as before), so the revision runs on
    production without a re-extraction; the downgrade reverses the rename
    (round-trip test on a finding row) (owner, Q24).
71. [ ] **The place rule in words (R74).** The screen criteria, the tagging
    context, `constrain` and `option_design` carry "the place in the question
    is the user's place, not a criterion; judge as if the question named no
    place", and so does every other prompt that read the stripped text:
    discovery, typing, the eight lines and the folding calls (lead, Q25).
    **M4** on the replays (18P stop measure): no exclusion and no screen
    failure because of place, read by hand. Threshold: none. The screen's
    pass rate reported beside the last loop's. If M4
    holds, `strip_place`, its name tables, `names_place` and `where_codes`
    are gone from product code; if it fails, they stay and `verification.md`
    and final 3 say so. M4 on the live runs reported.

### Cross-cutting

63. [ ] **Every new or changed prompt went through a refine loop (R69, R74,
    R75).** The two folding prompts; `extract_interventions` v3 with
    `SCHEMA_VERSION` bumped and the three fields in `_NULLABLE_TEXT_FIELDS`
    as needed, replayed with the memo bypassed (lead, B1, Q19); any round the
    "not stated" check calls for, in the same loop; the place-rule prompts
    (18P). Each: rounds in `evidence/rounds/` (change, finding, figures,
    read-back), one stop measure, at most five rounds, tuned on the tuning
    set and read once on the check set, reported to the owner, re-pinned in
    `scripts/prompt_hashes.json`; `interventions_records.py` is in the guard's
    file list with `iof_records.py`, `icf_records.py` and
    `finding_references.py` (lead, B12; owner, Q24), each hashed in
    `scripts/prompt_hashes.json`. Folding stop measure (20L): on the tuning set, no
    two kinds on one list name the same kind, and at most 12 kinds per list
    per facet (lead, A6); kinds per list and plan-word matches reported. The
    16W word swap is not a loop (R75). The cluster prompt is unchanged for examples; its discovery prompt takes the place rule (18P).
64. [ ] **Gates (lead, A14).** Full `make verify` at 15.0, 16 (the schema)
    and 23; `prompt-guard` at 16R, 16W, 18P, 20 and 20L (and 18C if a round
    runs); `openapi-sync` at 16W, 17, 18 and 21; `frontend-verify` at 16W,
    17, 18, 21, 22a and 22b; ADR 0040 amended in its own commit before
    Phase 16.
65. [ ] **The contract's lines hold.** The OpenAPI diff shows only the
    removals and additions of final 3 § 3; `verification.md` records the
    known limits of final 3 § 7.3, M1, M2 and M4 on the live runs, records
    with a `programme_name` per list (reported, lead A14), and names rounds
    2–5 of 12L as built before this amendment.
66. [ ] **Spec changes of amendment 3** are applied only with the owner's
    accepted wording, one line each in `docs/specs/log.md`.
