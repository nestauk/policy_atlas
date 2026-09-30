# ADR 0040 — The longlist at reader grain: acquire-only option searches, one screen, the theme component, and tagged profile records

- **Status:** Accepted — 2026-09-28 (owner, at the task 046 plan gate; the
  decisions below were ruled one by one in the contract interview, the
  contract-stage review and the plan-stage review the same day).
  **Amended 2026-09-30** by § Amendment 2 (task 046 amendment 2; the owner
  decided its rulings R34 to R53 on 2026-09-29)
- **Date:** 2026-09-28
- **Task:** 046-longlist-refinement (contract, rubric and plan under
  `docs/tasks/046-longlist-refinement/`)
- **Relates to:** [ADR 0039](0039-options-scoping-longlist-option-searches-and-option-records.md)
  (the longlist walk; this ADR **amends its decisions 2, 3, 6, 8 and 10**
  and keeps the rest); [ADR 0037](0037-options-scoping-task-kind-links-and-baseline-gate.md)
  (the scoping plan and the baseline; unchanged);
  [ADR 0018](0018-multi-facet-clustering-engine.md) (the clustering engine;
  reused with no source change); [ADR 0013](0013-mandatory-eb-spine.md)
  (the spine; one more non-spine step); [ADR 0027](0027-durable-planning-transcript-artefact-streaming.md)
  (progress events; one stage key added).

## Context

Task 045 built the longlist walk. Seven live runs on seven policy domains
(2026-09-23 and 2026-09-28) showed that the list did not have the shape a
reader can decide on:

- Five of seven runs filled the ceiling of 40 options with design variants,
  bundle components and single trials. Hand folds of the same runs gave 13
  to 21 options.
- 54 to 72 percent of the profile records were assigned to no option. The
  class-level systematic reviews were among them.
- Constrain excluded options for the country of a study, for a population
  that overlapped the target unit, and for an outcome on the pathway to a
  plan outcome. It answered "cannot check" for 3 to 16 options per run
  because a design did not repeat the target unit.
- The plan's place reached the screen through the target unit's text. In
  one run the broad screen kept 6 of 70 documents for that reason.
- Each option search screened every document of the task against its own
  option's design. Each document was screened 5 to 12 times. 139 to 183
  documents per run came from option searches, and most of them never got
  a screen against the plan. A run cost $6.26 to $16.18, of which screening
  was $4.79 to $9.65.

The owner ruled that the shape of the list is the purpose of the slice,
that the Evidence search components are reused as they are, and that a cost
change which needs an edit inside an Evidence search component belongs to a
later system-level task.

## Decisions

1. **Option searches of a longlist walk only acquire; one screen judges
   the pool.** (Amends ADR 0039 decisions 2 and 3.) A child walk of a
   longlist walk runs `acquire` and ends. The runner joins the children
   before `screen_abstract`, not before `longlist`. The longlist scope's
   screen, classify, appraise and intervention profile then run once over
   the whole pool; the screen's task-wide document load does this with no
   change to the screen. Units come from the longlist scope and from
   add-walk scopes. Owner: "why do we need different option scope
   screening for each option? Isn't the scope the initial scope from the
   task agent planning conversation?"

   A chain is recoverable from the intent record's purpose **and its
   context**: `run_option_search` writes `acquire_only: true` into the
   scope's context when the walk has a parent, and `compose` reads it. No
   new purpose value; the purpose check in the schema is unchanged.

   The walk a user starts with "add an option" has no parent and stays as
   built in task 045, without ingest: its search and its screen read the
   option's design, and its card lists its own records.

   *Rejected:* a screen per option with a strict vote (it rejects a
   document that is about the problem and about a different option; it
   needs an edit to the Evidence search screen); an optional screen key
   that limits a scope to its own walk's documents (the review showed that
   the add walk cannot have a plan-level screen input, and that the key's
   companion, a classify skip list for the add walk, could never fire); a
   new purpose value (a second migration).

2. **The screen input is the wide target unit and the outcomes.** (Amends
   ADR 0039 decision 10.) The plan keeps three things apart: the target
   unit (who or what the intervention is for), the setting, and the
   geography. Owner: "they are still important context of what the user
   wants, and will feed into things like transferability assessment.
   However we shouldn't let that stop potentially transferable evidence not
   getting in at the screen step."

   | Slot | Screen | On the record | Constrain | Task 3 |
   |---|---|---|---|---|
   | Outcomes | yes | outcome tag | yes; a stated pathway passes | yes |
   | Target unit | yes, wide: an adjacent or wider population passes | population tag | yes, exact; adjacent goes to *tried on* | transferability |
   | Setting | no | setting field | only a stated requirement | transferability |
   | Geography | no | study geography | no | transferability |

   The screen judges a document and its error is neither visible nor
   reversible, so it is wide. Constrain judges an option and its error is
   visible and reversible, so it is exact. A setting requirement no longer
   enters the longlist intent or the screening criteria (task 045 D21
   reopened). No plan field is added: a setting the user states without
   requiring it goes to Your context.

   One function removes place from text before it reaches a model: the
   plan's Where text, and a place only when a preposition leads it. It
   never removes a nationality. It is applied to the screen's intent and
   criteria, to constrain's plan data and to the profile's tagging context.
   A requirement in which the user names a place stays in the user's words.
   The baseline's intent keeps its place.

   *Rejected:* a wide setting criterion at the screen (it does not anchor
   the subject and filters almost nothing); a strip by every token the
   where-tried matcher knows (it removes "Polish" from "Polish migrant
   workers").

3. **Full-text ingest leaves the longlist and targeted chains.** Nothing
   in those chains reads full text. The chat answers from the abstract
   chunk that acquire writes and embeds, and each citation carries its text
   basis so that the label *abstract only* is code-authored. The field is
   on the shared chat path, so an Evidence search chat shows the label too.
   Task 3 fetches full text for shortlisted options. Owner: "Yes, remove
   ingest, full text fetched in task 3."

4. **The list is at reader grain, under a product ceiling.** (Amends ADR
   0039 decision 8.) An option is one kind of action a government can take.
   Discovery names options from the plan, the baseline, the seeds and a
   digest of the corpus (distinct intervention names with counts by role),
   not from every record. The target size is 20 and the hard ceiling is 25,
   seeds included; the ceiling binds what discovery adds, and options that
   cannot be folded can take the list above it, counted. Discovery can fold
   a suggested seed into a wider option through `merged_into_option_id`. It
   never folds an option the user named or one on which the user holds a
   state. One residual pass runs over the unclustered records, then the
   residual is a number. Discovery mints no package. Design variants are
   computed from an option's members and shown on its card; there is no
   instance-of relation and no second level of rows (decision-sheet row A9
   closed). This closes open question 4.

   *Rejected:* the formula `clamp(ceil(N/4), 8, 40)` (owner: "even 40
   feels like a lot of options to expect the user to decide on"); a limit
   on the user's own options.

5. **`theme` is a component of its own, after `constrain`.** (Amends ADR
   0039 decision 8.) The walk ends `longlist → constrain → theme`.
   `longlist` makes options; `constrain` makes verdicts; `theme` groups the
   included options. It is the Evidence search characterise's theme
   machine, modified: its unit is the option. It uses the clustering engine
   with no change, and its prompt moves with it. It is not a spine step: a
   failure ends the walk `degraded`, the verdicts stay, and the options
   show under "No theme". One stage key, `theme`, joins the run stream.
   From the end of `longlist` to the end of `theme` the list shows no
   themes; this is accepted and recorded for task 3, where the update in
   place can run `constrain → theme` alone.

   *Rejected:* a filter that removes excluded options from themes built
   before constrain (owner: "why don't we filter the excluded options
   before the theme generation?" — the theme descriptions would still be
   written for options the reader does not see); theming inside
   `constrain` (owner: "I don't think it makes sense for constrain to
   contain theming"); the longlist component run twice (owner: "wouldn't
   that just be two components then?"); one component that holds options,
   verdicts and themes (the parts cannot run alone, which the update in
   place of task 3 and the replay loops need; it removes a stage key).

6. **Profile records carry three tags, written against the plan.** (Amends
   ADR 0039 decision 6.) The intervention profile receives a tagging
   context (target unit, outcomes, intended change, with place removed) and
   writes, per record: a population tag (`on_target`, `adjacent`, `other`),
   an outcome tag (the plan outcome the recorded outcome is or leads to on
   a stated pathway, or `other`) and an object tag (`plan_object`, `option`,
   `neither`). The record's own content does not change. Tags sort; they
   never drop a record. Three nullable columns on
   `intervention_profile_record`. The memo stays per task; its fingerprint
   gains a hash of the tagging context, and a record written under another
   context reads as "not tagged". The context reaches the profile through
   one optional argument on the extract path; the IOF and ICF profiles do
   not receive it and stay byte-identical. Non-evidence documents are
   profiled; documents with a title and no abstract are not. Units are
   thinned before clustering by three counted rules.

   *Rejected:* a separate tagging pass (a second call per record); a rule
   in the profile that a technology is never an intervention (owner:
   whether it is the plan's fixed object depends on the plan, so it is a
   tag).

7. **Constrain judges the option as a kind of action.** Place is never an
   exclusion reason. A wider or adjacent population passes. An outcome on a
   stated pathway to a plan outcome passes. Silence about the target unit
   or the setting passes; "cannot check" is for a real unknown. A setting
   requirement excludes only a kind of action that cannot be delivered
   through the setting. The distinct screen is one call over the whole
   list; the merge rule of task 045 is unchanged. Discovery, typing and
   constrain receive the baseline; task 3's shortlist and assessment judge
   against it too. The lever list is `lever_types_v2` ("provide a service"
   is direct delivery); the runner-up lever is shown on the card.

8. **Prompts are refined in loops, on a replay.** Each prompt stage is
   changed, replayed on clones of stored tasks, read, and refined, for at
   most five rounds. Four tasks are the tuning set and three are a check
   set that is read and never tuned on. The lead runs the rounds and
   reports to the owner at the end of each stage's loop. The prompts of the
   longlist walk and the plan are open for refinement (planning, suggest,
   intervention profile, discovery and assignment, lever typing, constrain,
   theme, option design); the Evidence search prompts and the longlist
   verbs prompt are not. A prompt changes only on a finding from a round.
   The replay tool is a development script and is not product code.

## Amendment 2 (2026-09-30)

The rulings are R34 to R53 in the contract's § Amendment 2; the design
detail is in `docs/tasks/046-longlist-refinement/amendment-2-final.md`. The
decisions above stand, except where a decision below names one.

9. **`option_profile` is a component of its own, between `longlist` and
   `constrain`.** (Amends decision 5.) The walk ends `longlist →
   option_profile → constrain → theme`. It stays a line: no side branch.
   `longlist` makes the list: the options, their documents, the variants.
   `option_profile` writes all that is said about an option: the lever
   type, the ambition, eight lines of "what it would take" and the
   delivery setting. It has the same form as `theme`, but it is a spine
   step: a failure fails the walk, as a failure of `longlist` or
   `constrain` does. There is no code path for a built list with no
   profile. One stage key, `option_profile`, joins the run stream. It runs
   before `constrain`, on the whole list, so an excluded option has its
   profile and "include again" needs no special case. From the end of
   `longlist` to the end of `option_profile` the list shows no lever type,
   no ambition and no lines; this is accepted.

   *Rejected:* the profile after `constrain`, on the included options only
   (owner: "This seems like added complexity for not much gain. Why don't
   we just run profile before constrain."); the profile inside `longlist`
   (owner: "I think it is its own step."); a special failure rule that
   keeps a list with no profile (owner: "I just think this might be overly
   defensive programming"); the name `profile` (it already means the
   intervention profile of a record).

10. **Lever typing is in `option_profile`.** (Amends decision 7, where
    typing was a part of `longlist`.) It moves as built: the same prompt,
    the same batches, and the same rule that a failed or invalid typing
    batch keeps the previous typing. Its data stays in the same keys of the
    same `longlist_result` row, so the read side does not change. Lever
    typing no longer writes the ambition.

11. **A line is one call over the whole list.** Each of the eight lines,
    the ambition and the setting is one call on the judgment model that
    reads every option of the list, so that the same words mean the same
    thing across the list. The calls run at one time. An option gets one
    plain sentence per line. On six lines an option that clearly stands
    out from most of the list also gets a relative mark (less or more);
    "who decides" and "dependencies" have no mark. Ambition is how big a
    proposal the option is against the baseline, with the same relative
    mark. The marks are not added, weighted or ranked.

    *Rejected:* fixed bands (low, medium, high), a fixed list of answers,
    anchor examples in the prompt, guards in code on top of the prompt, a
    "cannot judge" value, a basis mark, ambition derived from the line
    marks, the three fixed ambition bands of task 045.

12. **One JSON column stores the profile.** `longlist_result.option_profile`,
    keyed by option id and design version, as `judgements` is. Per option:
    for each line key the sentence and the mark (`less`, `more` or null),
    and the setting. The lever type and the ambition stay in the option's
    columns. One reversible alembic revision on `d8f3b6a2c4e1`; no other
    schema change.

13. **The plan keeps five kinds of user statement apart.** The constraint
    kind `requirement` is renamed `boundary`. A new kind, `consideration`,
    holds what the adopter has or lacks, who can act, and how far evidence
    from elsewhere applies; it names the line it speaks of and carries
    `hard` for a stated limit. It is checked at assessment. **A
    consideration never excludes an option.** There is no plan slot "who
    decides": who can act is a consideration on that line.

14. **One exception to "place never reaches constrain".** (Amends decision
    7.) The line "who decides" names the body that must adopt the option
    and the country it assumes, from the plan's Where. `constrain` reads
    that line and the user's consideration on "who decides", and writes an
    authority label (*within your power* · *needs action by <body>* ·
    *unclear*) into `longlist_result.judgements`. The label never excludes;
    the reader can filter by it. With no such consideration there is no
    label. The rule stands for all else: `constrain`'s plan data is still
    place-stripped, and evidence from another place is never excluded for
    its place.

15. **Outcomes at the longlist are counts, in documents.** Per option: the
    documents that evaluate it and, among them, the documents for each
    plan outcome, from the existing outcome tag. No direction of effect,
    no size and no verdict; those belong to the assessment.

## Amendment 3 (2026-09-30)

The rulings are R54 to R75 in the contract's § Amendment 3; the design
detail is in `docs/tasks/046-longlist-refinement/amendment-3-final.md`. The
decisions above stand, except where a decision below names one.

16. **Tried on and Measures are folded kinds, one call per facet over the
    list.** (Amends the "tried on" of decision 6's tags as a card line.) The
    record words of `unit` (Tried on) and `outcome` (Measures) are folded to
    a few kinds per list by one call each on the mini model, in
    `option_profile`, over the distinct words of the whole list's coverage,
    with the plan's target unit and outcomes as reference: word → kind, the
    plan's own words where they match, few kinds, no fixed list. The maps
    are stored at list level in `longlist_result.option_profile` under
    `folds`. The code, not a model, counts documents per kind per option and
    writes them into the coverage (`tried_on_kinds`, `measures_kinds`); the
    coverage builder applies the stored maps on a merge and for an added
    option. An invalid response after one retry fails the step; a word the
    output leaves out keeps its own text as its kind; a kind not built from
    input words is dropped. The record tags of decision 6 stay in the
    coverage for `constrain` and are not shown.

    *Rejected:* a profile line for Tried on (a line reads at most five
    records, so it cannot count); a folding call for examples; a fixed list
    of kinds; counts on the list's facets.

17. **Outcome counts cover documents of any role; one outcomes table.**
    (Amends decision 15.) A plan outcome counts every document that reports
    on it, of any role; the evaluated count is its own figure. The card
    shows one table: a row per plan outcome with the option design's
    "serves" mark, and a row per other Measures kind the records report;
    columns "documents" and "evaluated". A plan-outcome row counts records
    tagged with that outcome and records tagged `other` or null whose
    folded kind is that outcome's own text; a kind row counts only
    `other`/null records; a document counts once on one row.

18. **Where tried is two levels from the record, not a matcher.**
    (Supersedes ADR 0039 decision 10 and task 045 D20.) The record gains
    `study_country`: the country of the stated place, from the abstract
    and the model's knowledge, every named country as its short English
    name, "multiple" for a group, empty when nothing is stated. The top
    level per document is one of: a country, "multiple countries" (derived
    in code from two or more countries, or "multiple"), "other" (a place
    stated with no country) and "not stated"; the level below is
    `study_geography` as written. The four groups, the OECD rule, the
    where-tried matcher and its fixed lists of country and place names are
    removed, with `where_codes` and `home`. No fallback to the publisher,
    journal, authors or publication country. No comparability label at the
    longlist: that is transferability, at the assessment.

    *Rejected:* a fallback to the publication country (not defensible: a
    US-published journal carries a Kenyan trial); a model judgement of
    comparability at the longlist (cost, and a verdict the longlist does
    not need); a code → name table.

19. **`unit` is the one concept, for options scoping and Evidence search.**
    The intervention profile record's `population` becomes `unit` ("who or
    what the intervention was delivered to: people, organisations, sites or
    things") and `population_tag` becomes `unit_tag`, with the same values.
    The intervention-outcome and implementation-context finding records and
    their prompts take `unit` too, as a like-for-like word swap with no
    version change, so no document is extracted again. The grouping facet
    key `population` becomes `unit` everywhere it is stored: the plan
    payloads, the keys of `grouping_result.groups` and the grouping
    provenance, rewritten by a reversible data migration; no reader keeps
    an alias. The record also gains `programme_name` (the proper name of the
    programme, scheme or law the abstract gives for this intervention, or
    null); the card's Examples are the option's distinct programme names,
    with counts, at most five, and replace the variants. `extract_interventions`
    goes to v3 with a schema version bump, so an options-scoping task
    re-extracts on its next run.

    *Rejected:* one definition in options scoping and another in Evidence
    search; examples written by the clustering call or by a folding call;
    keeping `population` on the finding records "for now"; an alias for the
    old facet key in the readers.

20. **The place rule is words in the prompts, not a list in code.** (Amends
    the mechanism of decision 7; its rule stands: place is never a
    criterion.) Every prompt that read the place-stripped plan text (the
    screen criteria, the record tagging context, `constrain`, the option
    design, discovery, lever typing, the eight lines and the folding calls)
    carries the rule "the place in the question is the user's place, not a
    criterion; judge as if the question named no place". The place strip,
    its name tables and the record-level setting pass are deleted only if
    M4 (no exclusion and no screen failure because of place) holds on the
    replays; if M4 fails, the list stays and the verification says so.

21. **One revision and one card.** One reversible alembic revision on
    `e9a4c1f7b3d2` carries the two new nullable columns, the renames on
    the three tables, the union view recreated with `unit`, and the
    facet-key data migration; no other schema change; no new table. The
    option card is rebuilt (no header boxes; the lever line with its
    secondary types; "What it would take" with Ambition first, the
    authority label beside "Who decides" and seven collapsed cells with
    "Middle"; the evidence section as the outcomes table, roles, where
    tried in two levels, tried on, the abstracts note and a de-duplicated
    document list sorted evaluated first then by quality; checks with the
    user's considerations first). A document on the card opens the Evidence
    search source dossier; on an options-scoping task the dossier's
    findings slot shows the intervention profile records through one new
    owner-scoped read route. The list's facets carry no counts; Tried on
    and Where tried filter; the grid's cell limit is four.

## Rollback

**Amendment 3** adds a third reversible revision, and it is the first of
this task's revisions that reaches production data (Evidence search is
live). `alembic downgrade -1` reverses the three column renames
(`unit` → `population` on the intervention profile record and the two
finding tables, `unit_tag` → `population_tag` with its check constraint),
recreates the union view with the old name, writes the facet key
`"population"` back into the stored plan payloads, the `grouping_result`
group keys and the grouping provenance, and drops `programme_name` and
`study_country`; deploy the previous image. The finding records carry no
version change, so their memo rows and fingerprints stay valid both ways;
no document is extracted again. The intervention record's v3 prompt
re-extracts options-scoping tasks only, on their next run. The read-model
change of amendment 3 is not additive (the four where-tried groups, the
variants, the populations and the runner-up lever leave the option read
models), so a longlist built by amendment 3 is not guaranteed to read
cleanly under the previous image. To remove all three revisions, run
`alembic downgrade -3`.

**Amendment 2** adds a second reversible revision. `alembic downgrade -1`
drops `longlist_result.option_profile`; deploy the previous image. The
read-model change of amendment 2 is not additive (`ambition_bands` is
removed; the ambition values change), so a longlist built by amendment 2 is
not guaranteed to read cleanly under the previous image. Nothing of this
feature is staged. The text below describes the first revision
(`d8f3b6a2c4e1`); to remove both, run `alembic downgrade -2`.

One alembic revision, reversible, with no value rewrite. Quiesce the API.
`alembic downgrade -1` drops `population_tag`, `outcome_tag` and
`object_tag` from `intervention_profile_record` with their check
constraints. It needs no refusal rule and no operator script: the columns
are nullable and no other row depends on them. Deploy the previous image;
the prompt revisions, the chains and the `theme` component revert with it.

Stored data and the previous image:

- A longlist built by this slice stays readable by the previous image. Its
  `longlist_result` row has the same columns; the new keys in `coverage`
  and `counts` are ignored; its themes are in the same place.
- A child walk of this slice has a targeted scope with no screening rows.
  The previous image's readers filter on relevant rows, so they read
  nothing from it.
- An option typed under `lever_types_v2` shows its stored lever name. The
  previous image has the v1 definitions only; a lever whose definition
  changed shows the v1 text. Rebuild the longlist after a rollback if the
  definitions must agree.
- Profile records written under a tagging context have a fingerprint the
  previous image does not compute. It profiles those documents again at
  the next build.

## Evidence

Added in build Phase 8: the migration round-trip; the round records of the
loops; the measures M1 to M9 on the replay and on the three live runs,
beside the figures of the seven pre-contract runs; the cost and the
wall-clock time of a run. Every figure is read back from a saved result.

Pre-contract figures that the decisions rest on
(`docs/tasks/046-longlist-refinement/evidence/pre-contract-runs/`, not
committed): options per run 12 to 40; records assigned to no option 54 to
72 percent; screens per document 5 to 12; documents from option searches
139 to 183 per run; memberships with the not-stated flag 23 to 66 percent;
"cannot check" verdicts 0 to 16 per run; cost per run $6.26 to $16.18.

## Consequences

- The longlist walk has one screen and one scope that judges documents.
  The cost of a run no longer grows with the number of option searches
  times the size of the pool.
- Options scoping has one more component. `constrain` and `theme` can run
  without `longlist`, which task 3's update in place needs.
- The plan's setting and geography leave retrieval. They return at
  transferability in task 3, which must read them from the plan and from
  the record fields.
- A scoping task holds no full text before assessment. Task 3 must fetch
  it for shortlisted options, and in the seven runs about half of the
  fetches failed.
- The Evidence search changes in two places only: one optional argument on
  the extract path, and one field on the chat's citation facts.
- Recorded and not fixed: provider-written abstracts, duplicate documents
  without a DOI, the untested guesses path, the process-wide option-search
  pool, empty OpenAlex queries, a late child that adds documents after the
  screen, themes that go out of date after a user's exclusion. Deferred to
  a system-level cost and latency task: query variants and a fallback
  ladder, the baseline writer's tool list, an option-search loop,
  allocation by corpus size.
