# Task 046 — amendment 2, proposed (for the owner's decision)

> **Status:** proposed 2026-09-29 · lead. **Nothing in this file is built and
> nothing in the contract or the specs is changed by it.** The owner decides
> each item. Accepted items go into contract.md as rulings with the owner's
> words, then into plan.md as build phases.
>
> **Inputs:** the owner's statements of 2026-09-29 in the build conversation;
> the two research notes in [research/](research/) (sources and their
> verification status are in the notes); the experiments in the gitignored
> evidence folder (`rounds/9-*.txt`); the three live runs (verification.md).
>
> **Owner's direction, quoted:** "We can do these in 46. this is the longlist
> refinement task and all of these are longlist refinements." · "Happy to
> change the plan fields. The contract can be expanded as much as necessary
> but let's discuss the changes and suggested contract ammendments first" ·
> "Keeping this step under 10 minutes is quite necessary".

## The idea in one paragraph

A user states five kinds of thing, and today the plan has a clear place for
two of them. The longlist card says what an option is and what evidence names
it, but not what it would take to do it, and not what the evidence reports.
So the shortlist has little to cut by. This amendment (1) gives each kind of
statement its own place in the plan, (2) adds to every option an
**implementation profile** and an **early signal** of reported outcomes, and
(3) moves the delivery setting from the record to the option. All of it must
fit in a longlist walk of 10 minutes.

## Part A — what the user states (the plan)

| # | Proposal | Basis |
|---|---|---|
| A1 | **Five kinds, each with its own rule.** Boundary (what the option is): can exclude. Authority (who has the power to adopt): labels; excludes only when the user says so. Implementation consideration (what the adopter has or lacks): informs; excludes only when the user marks it as a hard limit. Transferability consideration (how far evidence from elsewhere applies): kept for the assessment. Aim (the outcome wanted): becomes the plan's outcomes. | Owner: "Yes these 5 kinds feel right." Research note 2 § 3 maps each kind to the official guidance. |
| A2 | **A new plan slot, "Who decides"** (the body that would adopt the option: "one English council", "the Department for Education"). The Task Agent asks for it when Where is below national level: "Should I keep only options that a council can adopt, or also show options that need national action?" | Owner: "Yes" (question 3). The test of 2026-09-29: the judge was too lenient on "only options a local authority can run" when it had to work the powers out by itself. |
| A3 | **The constraint kinds become:** `boundary` (the present `requirement`; the screen word stays "requirement"), `consideration` (new), `preference` (kept for a wish about what the option achieves, for example "at least moderate evidence"), `evidence_restriction` (unchanged). A `consideration` names its **aspect** (B2) and carries `hard: true` only when the user states a limit ("no more than £2m a year", "in place by April 2027"). | Research note 2, recommendation 3: a stated ceiling or deadline is a constraint in the guidance; a capacity is a matter of degree. The guidance says a threshold must be set in advance, by the user, not after the options are seen. |
| A4 | **The Task Agent sorts a capacity statement as a consideration, never as a preference**, and keeps the user's words in Your context. | The probe of 2026-09-29: "Budget, staffing and suitable local homes still need to be established" became a preference, and constrain wrote a guess about the sentence. |
| A5 | **Aims.** The Task Agent keeps the user's words as the aim and proposes outcomes that evidence can be read against ("households entering temporary accommodation per year"), tagged *assumed*. A wish about how long an effect lasts ("make the improvement last") is a preference, checked at assessment. | The probe: "New housing crises prevented" was accepted as an outcome. |
| A6 | **A transferability consideration is stored with the plan** and shown under the default preference "Transferable to *Where*". Nothing judges it at the longlist. | Research note 2: no source excludes on transferability at the screening stage. |

Not proposed: a separate kind for acceptability or for timing. Timing is the
aspect *time* with `hard: true`. Acceptability: see B3.

## Part B — what every option carries (the longlist)

| # | Proposal | Basis |
|---|---|---|
| B1 | **One "option profile" pass** writes, for every option: the lever type and its reason (built), the ambition and its reason (built), the **delivery setting**, **who must decide**, and the **implementation profile**. It replaces the present typing pass. It reads the option's design, the baseline, the plan, and a digest of the option's member records. | One pass keeps the time down and lets the model use the same words across the list. |
| B2 | **The implementation profile has seven aspects.** Cost · time (to set up, and to an effect) · workforce · powers · dependencies · coordination · delivery complexity. Each has a band (low, medium, high; short, medium, long for time; or *cannot judge*), one line of reason, and its basis (*from the documents* or *estimate*). Bands are relative to typical public programmes in the same field. | Research note 1 § 4. The owner's point on complexity agrees with the literature: the MRC guidance defines complexity by parts, behaviours, skill and tailoring. The note splits the draft "complexity" into **coordination** (how many bodies) and **delivery complexity** (how intricate the action is for each case). |
| B3 | **Acceptability is not in the first profile.** | Research note 1 calls it the least safe aspect to judge. A model that guesses public or political resistance can mislead a senior reader. The owner can add it later. |
| B4 | **"Powers" is the authority kind.** The profile names who must decide ("national government: primary legislation", "a local authority within its existing powers") and the country it assumes. Constrain compares it with the plan's "Who decides" and labels the option: *within your power* · *needs action by <body>* · *unclear*. | Owner: "authority would sort and label, and exclude only when the user says so." |
| B5 | **The profile reasons from the class**, and takes the harder band when it is between two. | Research note 1 § 6: early estimates lean optimistic (Green Book, optimism bias). |
| B6 | **No score and no rank from the bands.** The list can sort and filter by one aspect. | The Green Book recommends against simple weighting and scoring. |
| B7 | **Wording.** No sentence ends with "a guess rather than evidence". The block has one heading that says what it is, for example "Implementation profile · Policy Atlas's estimate before assessment". | Owner: "we don't need 'a guess, not evidence', it sounds too LLM-generated." The trust spec requires a label on a reasoned guess; the label moves to the heading. **Spec change.** |
| B8 | **The reasoned guess per preference is removed** where the preference is about an aspect: the profile answers it. A preference about what the option achieves keeps its guess. | The test: the per-sentence guess has no meaning for a capacity statement. |
| B9 | **The delivery setting is a fact about the option** ("delivered through: school"): one main setting and at most one more, in words that fit the field, the same word for the same kind of place across the list; empty for a system-level instrument. The list's Setting facet uses it. The record's own words stay on each document as "studied in". | Owner (R32): no fixed list. Experiment `9-setting-option-level.txt`: 6 to 10 labels per list, no place or body names, against 41 to 67 labels from the records. Experiment `9-setting-grounding.txt`: 88 to 94 percent of record settings are word for word in the abstract, so the fault is choice, not invention. |

## Part C — the early signal of reported outcomes

| # | Proposal | Basis |
|---|---|---|
| C1 | **The intervention profile records, for an evaluated intervention, what the abstract reports** on its outcome: `improved` · `no difference` · `mixed` · `worsened` · `not reported`, and if the result is `observed` or `modelled`. It records no size of effect. | Owner: "maybe already extracting/synthesising observed/modelled outcomes might be good to already do per option at the longlist stage?" This **reverses a present rule** of the profile prompt ("no directions of effect"). |
| C2 | **Each option shows an early signal per plan outcome**: the count of evaluating documents by reported direction, observed and modelled apart. | Research note 2 § 5: the What Works toolkits show effect, cost and evidence strength as separate fields. |
| C3 | **The signal is withheld when the evidence is thin**: fewer than 3 evaluating documents on that outcome shows "too little evidence to say". "No evidence found" and "evidence of no difference" are different lines. | The EEF toolkit withholds the effect under 10 studies. The number 3 is a first value to measure. |
| C4 | **The label:** "Early signal, from abstracts. Not yet assessed." Evidence strength (the quality tiers, built) stays its own field. | Research note 2 § 5.3: abstracts mislead. A review of 17 studies found a median of 39 percent inconsistency between abstracts and full reports; spin was in 58 percent of abstract conclusions of trials with non-significant results (both biomedical). The guidance that the note read uses abstracts to screen, not to extract findings. |
| C5 | **Two nullable columns** on `intervention_profile_record` (`reported_direction`, `result_basis`), in a second alembic revision. | The contract allows one migration and names a second as a stop condition. The owner's word is needed. The other way, a JSON field, hides a product fact in a technical column. |

**The lead's caution on Part C.** This is the part with the most risk to
trust. An abstract says what its authors chose to say. The signal must never
read as a finding, and the assessment must be free to contradict it. If the
owner wants a smaller first step, C can ship as counts only ("12 documents
evaluated it; 9 report on obesity prevalence") with no direction.

## Part D — constrain

| # | Proposal | Basis |
|---|---|---|
| D1 | **An exclusion needs a clear failure.** Mixed or missing information keeps the option and says so. | Research note 2, recommendation 2: the business case guidance says "clearly"; the EC toolbox says "self-evident and indisputable". |
| D2 | **Constrain judges:** each boundary; each `hard` consideration against the profile's band (excludes only when the band is *high* against a stated limit, and says "likely"); the authority label (B4); relevance to the aim; the duplicate check (built). | A1, A3, B4. |
| D3 | **The excluded options stay visible with one reason each** (built). An option that needs action by another body stays on the list with that body named. | Research note 2, recommendations 4 and 6. |

## Part E — for the shortlist (task 3), recorded now

The shortlist is task 3. This amendment builds what it needs and records the
principle, so that task 3 starts from it.

| # | Principle | Basis |
|---|---|---|
| E1 | The cut uses four tests in order: passes the hard limits · serves the aim · is distinct · adds spread (kinds of action, levels of ambition, a do-minimum). The profile and the early signal choose **within** these tests. | Research note 2, recommendation 7. Owner: "the guesses are useful for how the shortlist selects. It needs something to decide how to cut the longlist down". **This reopens rulings 12 and 19** (a reasoned guess is never an input to the shortlist). |
| E2 | About five options, in a range of three to six, plus the baseline. | Green Book 2026 para 5.17; New Zealand Treasury. |
| E3 | Every use of the profile in the cut is shown on the slot as a written reason. No weighted score. | Green Book 2026 para 5.15. |

## Part F — time

The limit is 600 seconds for the longlist walk. The three live walks took
531, 569 and 622 seconds.

| Step (live obesity) | Seconds now | Change |
|---|---|---|
| Suggest | 41 | none |
| Acquire and option searches | 27 | none |
| Screen | 76 | none |
| Classify | 48 | none |
| Intervention profile | 93 | + two short fields per evaluated record (C1) |
| Longlist: discovery, assignment, residual pass | about 140 | none |
| Longlist: typing | about 45 | becomes the option profile pass (B1): more output per option |
| Constrain | 28 | fewer guesses (B8), one label more (B4) |
| Theme | 39 | none |

**Measured 2026-09-29** (experiment `9-option-profile-time.txt`, one pass on
two live lists, judgment model, six calls at one time):

| List | Options | Batch size | Seconds | Output tokens | Complete profiles |
|---|---|---|---|---|---|
| Obesity | 24 | 5 | 61 | 15,318 | 24 of 24 |
| Caregiving | 25 | 5 | 62 | 19,367 | 25 of 25 |
| Obesity | 24 | 8 | 82 | 15,557 | 24 of 24 |

The pass replaces the typing pass (about 45 seconds), so the net cost is
about 15 to 20 seconds at a batch size of 5. Two findings for the prompt
loop: the bands gather at *medium* and *high* (1 to 3 *low* per aspect on the
obesity list), so they separate the options too little; and the setting
words are not the same across batches (17 labels on the obesity list,
against 10 when one call reads the whole list), so the setting needs the
whole list in one call.

| # | Proposal |
|---|---|
| F1 | **Measure first.** Before the build, one experiment on the replays gives the seconds and the tokens of the option profile pass at batch sizes of 5 and 8 options with 6 calls at one time. |
| F2 | **The budget:** the option profile pass takes at most 75 seconds for 25 options. If it does not, the reason lines get a word limit, then the batches get smaller. |
| F3 | **One saving to pay for it:** `theme` and the option profile pass read different things (themes need the included options; the profile needs every option), so the profile pass can run while `constrain` and `theme` run. This changes the walk from a line to a line with one side branch. It needs a change in the scoping runner. The lead measures the simpler way first (the pass inside `longlist`). |
| F4 | **M8 becomes a pass condition:** each of the three live walks ends in 600 seconds or less. |

## What changes in the contract

| Contract part | Change |
|---|---|
| § Constraints, Schema | A second revision: two nullable columns (C5). No new table. |
| § Constraints, "No new plan field" (AM8) | Withdrawn: the plan gains "Who decides" and the constraint kind `consideration` with `aspect` and `hard` (A2, A3). The plan payload is JSON, so this needs no migration. |
| § Constraints, Prompts | Four more revisions: `task_agent_scoping_v5`, `extract_interventions_v3`, the option profile prompt (replaces `lever_typing_v2`), `constrain_v3`. |
| § Public interface | Additive: the profile, the early signal, the delivery setting and the authority label on the option read models; "Who decides" and the new kind on the plan read model. |
| § Stop conditions | "A second migration" leaves the list. |
| Measures | New: M10 every option has a complete profile, or *cannot judge* with a reason · M11 on the hard-requirement test, the authority label is right for at least 9 of 10 options (read by hand) · M12 the Setting facet of a list has at most 10 labels and no place or body name · M13 the early signal is withheld under the threshold · M14 the profile orders a nudge below a clinical service on delivery complexity (read by hand on the replays). M8 becomes a pass condition (F4). |
| § Spec changes | New items: the five kinds and "Who decides" (OS components § 1, plan-as-object); the option profile and the early signal (OS components § 6, OS capability § Output structure); the label of a reasoned estimate (OS trust § Reasoned guesses); abstracts as a source of a reported direction (OS trust § The principle); the shortlist principle (OS capability § Pipeline and gates). Wording goes to the owner. |
| Review | Tier 4. The amendment and its plan get an adversarial review before the build, as the contract and the plan did. |

## Build phases, if accepted

| Phase | Content | Executor |
|---|---|---|
| 9 | Time experiment (F1). Plan model: "Who decides", `consideration`. Planning prompt v5 and its replay loop. | lead (prompt, loop) · `deep-reasoner` (plan model, plan screen structure) |
| 10 | The option profile pass: prompt, wire, storage in the longlist result, the loop on the replays (M10, M12, M14). | lead (prompt, loop) · `deep-reasoner` (component) |
| 11 | The early signal: revision, profile prompt v3, coverage, the loop (M13). | lead (prompt, loop) · `deep-reasoner` (code) |
| 12 | Constrain v3: clear failure, hard considerations, the authority label, the loop with the hard-requirement test (M11). | lead (prompt, loop) · `deep-reasoner` (component) |
| 13 | Read models and views: the profile block, the early signal, the setting facet, the authority label, the plan screen. | `fast-worker` (structure) · lead (words and finish) |
| 14 | Three live runs, verification, spec changes with the owner's wording, full gate. | lead |

## Decisions for the owner

1. **Part A:** accept the five kinds, "Who decides", and the kind `consideration` with `hard`?
2. **B2:** seven aspects, or the smaller set of six (coordination and delivery complexity as one line)?
3. **B3:** acceptability out of the first profile?
4. **B7:** the label on the heading of the block, not in each sentence? (The wording of the heading comes with the spec changes.)
5. **B9:** the setting at option level, with the record's words kept as "studied in"?
6. **Part C:** the reported direction from abstracts (C1 to C4), or counts only as a first step?
7. **C5:** a second migration?
8. **E1:** the profile and the early signal may inform the shortlist cut (reopens rulings 12 and 19)?
9. **F3:** may the walk get a side branch, if the simple way does not fit in 600 seconds?
10. **Review:** an adversarial review of this amendment before the build?

## The owner's first answers (2026-09-29)

Quoted from the build conversation. Items still open stay proposals.

| Decision | Answer | State |
|---|---|---|
| 1. The plan | "What is the consideration kind? Give me the five kinds for the new proposed plan" | open: explained in the conversation |
| 2. Aspects | "I think the 8 aspects are better, as we said before composite assessments are more likely to be inaccurate than if we split up the assessments right? Also a broad complexity dimension feels a bit hard to interpret." · "7 or 8" | coordination and delivery complexity stay apart; 7 or 8 depends on acceptability |
| 3. Acceptability | "Why recommend out?" | open |
| 4. Wording | "Not sure what you mean by this" | open: explained in the conversation |
| 5. Setting | "I think so, what's the difference between the option level, and the records?" | accepted in principle |
| 6. Outcomes | "I think we need to think through the outcomes piece more." A review of the previous version (`../discovery_policy_atlas`) is asked for: "don't treat it as gospel, some things might be good/useful, but others might be subpar". | open; review running |
| 7. Migration | "Yea we'll need a db migration" | **accepted** |
| 8. Shortlist | "Yes the profile will" inform the cut. The early signal waits: "it's the remit of the next task". | **accepted** for the profile |
| 9. The walk | "No. we can make it longer than 600 if needs be and optimise for latency afterwards." | **F3 rejected.** F4 is withdrawn: M8 stays a reported measure |
| 10. Review | "not yet but we will do." | later |

New questions from the owner, to answer in the design:

- **The reader.** "8 would be a lot to take in for a reader though so we would
  need to think about the UX, whether to even show all of them or to have
  more of a condensed summary somehow".
- **The bands.** "Will high/med/low even be interpretable by users or even by
  downstream AIs? … if those bands aren't calibrated across the option set
  then it wouldn't be useful for comparisons either."

## The owner's second answers (2026-09-29)

| Item | Answer | State |
|---|---|---|
| The plan kinds (Part A) | "the plan kinds look good" | **accepted** |
| Acceptability (B3) | "Let's leave it out, it feels too shaky. Maybe burden could be a good substitute but I feel like we would have to test a range of domains to decide if it's right to include" | **out**; "burden" only after a test across domains |
| The label on the heading (B7) | "Sounds good" | **accepted** |
| Named answers for each aspect | "Again a fixed list, what you've outlined feels too rigid at least for some of the aspects. Would those really work for a broad variety of domains?" | **rejected as proposed** |
| Anchor examples in the prompt | "Won't it be biased towards the domains that we name. When we're thinking about a generalised tool, I don't know how we can ensure we have good coverage of anchor examples" | **rejected as proposed** |
| Comparison across the list | "sounds like it would be good. But again we would have to test it and also think about potential latency." | to test |
| The reader | "needs more thought" | open |
| Ambition | "should the 'ambition' label we're currently doing be based on these? How is it currently produced?" | open |
| Outcomes | "adding outcomes based on the old version is quite complex since there are a lot of different aspects" | open |

The owner asked to take the open topics one at a time.

## Topic 1 decided (2026-09-29): how an aspect is expressed

The owner: "I agree on topic 1".

- **Each aspect is one plain sentence** that answers the aspect's question for
  the option. No band, no fixed list of answers, no anchor examples in the
  prompt.
- **One call for each aspect reads the whole list.** It gets the aspect's
  question, the plan, and the design and evidence records of every option. It
  writes, for every option, the sentence and the option's **place** among the
  options of this list (lower, middle, higher), and says if the list differs
  much on the aspect (wide, narrow). The eight calls run at one time.
- This replaces B1 (one pass in batches), B2's bands, B5's "take the harder
  band", and the three guards that the lead first proposed (the owner: "we
  should address the root clause, not apply a bandaid").
- Evidence: `evidence/rounds/9-compare-experiment.txt` (the two-step form and
  its fault), `9-aspect-pass-experiment.txt` (the accepted form).
- Open from the test: the step takes about one minute; the places of two
  aspects are less stable (dependencies, time to effect); the "basis" mark is
  not reliable and is not shown until a test proves it.

## Topic 2 decided in part (2026-09-29): the test across seven fields

Evidence: `evidence/rounds/9-aspect-pass-seven.txt`.

| Item | The owner | State |
|---|---|---|
| Time: about one minute for the step | "Time is fine for now." | **accepted** |
| Dependencies: a sentence only, no place | "Yes dependencies feel distinct, I think it would still be useful information for the options page." | **accepted** |
| Stability: cost 92 percent, the other aspects near 80 percent, with the sentence always beside the place | "that's good enough" | **accepted** for a first version |
| "The list differs little" is used too seldom (1 of 56 aspect runs). The lead's idea (name the least and the most demanding option and the distance) | "I don't think that idea is great, what are some other options?" | **rejected**; other ways under test |

## Topic 2 decided (2026-09-29): the comparison, and the aspects

Evidence: `evidence/rounds/9-aspect-variants.txt` (ways A and B),
`9-aspect-groups-v2.txt` (the changed way B, which failed).

| Item | Decision | The owner |
|---|---|---|
| The way of comparison | **Way A: only what stands out.** An option gets a mark only when it clearly takes less or more than most of the list on an aspect. Every other option has no mark. On a list that differs little, nobody stands out. The sentence is always beside the mark and carries the kind of demand. | "Yes I think that's good." |
| Way B (free groups with a phrase) | Rejected after two tests. With a limit of four the model made four groups almost every time, also on a list that differs little. With no limit it made 4 to 12 groups, by kind and not by amount, and their order changed between runs (pairs in the opposite order: up to 19 percent). | the lead's finding; the owner asked for the test |
| "Powers" | **Split, then cut.** The lead's question held two questions (who decides; is a new law needed). The owner: "I thought power was meant to be the authority in charge of something?" | |
| "Who decides" | **An aspect: one sentence that names the body**, with the place it assumes (from the plan's Where). No mark. Constrain compares it with the plan's "Who decides" for the authority label. The sentence names a legal means only when the baseline or a document states it. | "Yes I think that's good." |
| "Legal change" | **Out of the first version.** The owner: "The legal change one feels like it might be prone to errors. Will that be based just on the LLMs knowledge of what's already in place?" It would rest on the model's knowledge, law differs by place and changes with time, and the reader knows it better. A grounded form (search and cite the present legal basis) is a later piece of work. | "Yes I think that's good." |

**The aspects of the first version (eight lines):** cost · time to set up ·
time to effect · workforce · who decides (no mark) · dependencies (no mark) ·
coordination · delivery complexity.

**Time:** the step takes about one minute in every form that was tested. The
time comes from the sentences (one for each option, in each call), not from
the way of comparison.

## Topic 3 decided (2026-09-29): ambition

Evidence: `evidence/rounds/9-change-from-now.txt`, `9-ambition-seven.txt`; the
Green Book (2026), paras 5.18, 5.28, 5.29.

| Item | Decision | The owner |
|---|---|---|
| The word | **Ambition stays.** | "I liked ambition because it was short"; "If ambition is what's used in the green book and its what policymakers would be familiar with then I think it could stay but we just need to make sure that how we are deciding how ambitious something is makes sense" |
| The meaning | **How big a proposal the option is: how much it sets out to change, compared with what the baseline says is in place now.** Judged on the kind of action as if adopted in full: an adjustment to something in place, something new beside it, or a change to how the system works (who is entitled, who provides, who pays, what the rules are). | "yes" |
| Not the basis | The size of the studies ("These are likely to be quite small scale but it doesn't mean that the options can't necessarily be scaled to have a large reach"), and whether the option would work (that is the assessment, after the shortlist). | |
| The levels | **Relative: more ambitious than most · less ambitious than most · no mark** (way A). The three fixed bands (do minimum, incremental, structural) go. | "I think relative levels are quite good, it would make a better grid view" |
| The sentence | One sentence under the mark: what the option changes against the baseline. | "yes" |
| "Do minimum" | **No option is called "do minimum" at the longlist stage.** The Green Book's do minimum and preferred way forward belong to the shortlist (the next task). | "Agree" |
| Ambition from the aspects | **No.** Of 79 options with an ambition mark on seven lists, the cost mark says the same for 33 and the opposite for 16. Rules and market reforms change much and cost the state little. | the lead's test, after the owner's question |
| The grid | The reader chooses which line gives the columns (ambition, cost, or another aspect). Details in topic 4. | "your idea of allowing the user to select which aspect the grid shows as the columns could be good" |

Findings on the present label, for the record: 80 to 92 percent of the
options of the three live runs are "incremental"; and the label uses the
Green Book's words with another meaning (the Green Book's do minimum is "the
option that just achieves the proposal's objectives", para 5.18).

To state in the specification: the Green Book compares versions of one
option; Policy Atlas compares kinds of action on one list.

## Topic 4 decided in part (2026-09-29): the reader

A wireframe from the real obesity run (24 options, the decided form) showed
four screens. It is in the gitignored evidence folder
(`evidence/mock/longlist-reader-mock.html`).

| Item | Decision | The owner's words |
|---|---|---|
| List rows | **Plain.** No marks on a row. | "On the list, I prefer plain" |
| Option card, "What it would take" | **All eight lines, always open:** the line name and its mark on the left, the sentence on the right (variant B). No summary paragraph (variant A), no row of cells (variant C). | "I don't like variant A in the option card. B looks pretty good. C feels too condensed and users would probably click through anyway" |
| Compare table | **Dropped.** The grid, with columns that the reader chooses, is the comparison. | "The compare page looks too information dense and would be offputting to users, I don't like it. Unless there's a better way to easily compare then we should drop it." |
| Mark colours | Tints from the Nesta palette. The two tints are open. | "We should use some nesta colours for tints" |
| Words for the levels | Open. Not "less than most", "like most", "more than most". | "In the grid view, I don't like the 'like most', 'less than most', and 'more than most' terms." |

### Known faults in the test data, for the build to test

The builder of the wireframe read the sentences of the obesity run. These
faults go to the prompt loops of the build. The lead has not yet checked them
against the saved file.

| Fault | Example | What in this amendment covers it |
|---|---|---|
| Setting "none" for an option that has a setting | front-of-pack labels, supermarket targets | B9, and the finding that the setting needs the whole list in one call. The test run used one call for each aspect. |
| A mark that the sentence contradicts | lobbying controls: cost "less", the sentence says it needs legislation | Not covered. New check for the loop: the mark must agree with its sentence. |
| A mark that is absent where the sentence lists much | active travel: no workforce mark | Not covered. Same check. |
| "Who decides" names a law by title and year | school food standards | Topic 2: a legal means only when the baseline or a document states it. The loop must test it. |
| "Who decides" names two bodies, or uses an acronym | children's meal standards; "DHSC" | Not covered. New rule for the prompt: one body, its full name. |
| A sentence that answers another question | lobbying controls, time to effect | Not covered. New check for the loop: the sentence answers its line's question. |

## Topic 4 decided (2026-09-29): the words for the levels, and two questions

| Item | Decision | The owner's words |
|---|---|---|
| Words for the levels | One comparative word for each line; the middle level is "Middle". Ambition: Smaller · Bigger. Cost: Cheaper · Costlier. Time to set up and time to effect: Quicker · Slower. Delivery complexity: Simpler · More complex. | "Your words for the levels sound good. The ones I'm not sure about our workforce and coordination." |
| Workforce | The line is **"Workforce requirements"**, levels Lower · Middle · Higher. One mark covers the number of people and the skills. The sentence tells which of the two causes the level. | "Can't we just have "workforce requirements", "higher/lower" and that could cover both the number of staff and the skills? And "coordination requirements" higher or lower as well" |
| Coordination | The line is **"Coordination requirements"**, levels Lower · Middle · Higher. The question changes from the count of bodies to: "Which separate bodies must act together to set up and run the option, and how closely must they work together? Do not answer about what happens in one instance of delivery." The refine loop measures the overlap with delivery complexity. | "Yes, I think something like that for coordination could work, but obviously we'll see what the prompt refinement results look like" |
| All prompts | Each goes through a refine loop; the one-off experiments are not the final quality. | "All the prompts should go through refine loops anyway so that should hopefully get rid of most snags compared to your one off experiments." |
| Tints | Open. The lead's proposal: a pale tint of Nesta Violet for the higher level and of Nesta Aqua for the lower level, navy text. The owner decides on the built screen. | "We should use some nesta colours for tints" |

## Topic 5 decided (2026-09-29): outcomes at the longlist

| Item | Decision | The owner's words |
|---|---|---|
| What the option shows | **Counts only** (the smaller first step of Part C): how many documents evaluated the option, and how many report on each outcome of the plan. No direction of effect, no size, no verdict. C1's direction and basis, C3 and C4 are not built. The direction of an effect belongs to the shortlist assessment. | "I think 2 sounds good." |
| Migration | **One alembic revision for the whole of amendment 2.** It holds every new column of the amendment, and the new fact of the record (the plan outcomes that the document reports on) is one of them. The plan's new fields are in the plan's JSON payload and need no column. | "We can do them as part of the migration we need to make for the plan anyway" |

## Topic 4 changed (2026-09-29): the card's "What it would take"

| Item | Decision | The owner's words |
|---|---|---|
| Option card, "What it would take" | The section collapses like the card's other sections. **Collapsed:** the row of eight cells, the line name above and the level word below, no word for a line with no mark (variant C, without the sentence on demand). **Expanded:** all eight lines, the name and the mark on the left, the sentence on the right (variant B). This replaces "all eight lines, always open". | "I actually change my mind on the aspect variants on the card. Looking at it again, since the card's other sections are collapsible, I think variant C when collapsed, and B when expanded makes sense" |
| Default state | The section is **collapsed** when the card opens (the lead's recommendation: the row of cells is the summary, the eight sentences are long). | "Yes sounds good." |

The final statement of amendment 2, with the answers to its 14 questions, is
`amendment-2-final.md`.

## Questions 15 to 18 decided (2026-09-29)

The owner chose the simpler way on each. The lead agrees with all four.

| Q | Decision | The owner's words |
|---|---|---|
| 15 | **The profile runs before constrain**, on the whole list, all lines in one step. This replaces the lead's recommendation on Q12 that the profile runs after constrain. "Add an option" stays as decided: the new option only, with the other options as context. | "This seems like added complexity for not much gain. Why don't we just run profile before constrain. As we saw before, constrain doesn't usually remove that many options anyway" |
| 16 | No special case. An excluded option has its profile, so "Include again" makes nothing. | "Running profile before would make this moot" |
| 17 | **No plan slot "Who decides".** What the user says about who can act is a consideration that names the line "who decides". This replaces A2 of the first proposal. A consideration can name any of the eight lines. | "Maybe we should just have it sit in consideration rather than necessitating a who decide slot?" |
| 18 | **No handling of old longlists.** The build writes no code for stored values of an earlier development iteration (old ambition words, lists with no profile). This also replaces the part of Q4 that kept the old words. | "This feature is still in development and nothing is staged yet. We don't have to add complexity just due to an earlier development iteration. I don't care about old longlists, they don't exist in production or staging." |

What follows from 17, stated by the lead: the Task Agent still asks its
question when Where is below national level, and stores the answer as a
consideration. The consideration's `hard` flag carries "exclude only when the
user says so": a hard consideration on "who decides" can exclude; one that is
not hard gives the authority label. A limit on another line never excludes
(Q1). With no such consideration, the option has no authority label (Q9).

## Questions 19 and 20 decided (2026-09-29)

| Q | Decision | The owner's words |
|---|---|---|
| 19 | **The profile is a step of its own**, a component between `longlist` and `constrain`, the same form as `theme`. `longlist` makes the list: which options there are, which documents belong to each, and the lever type. It no longer writes ambition. The lead's recommendation on failure, put to the owner in the same question: if the profile step fails, the longlist shows with no profile and constrain runs with no labels. | "I think it is its own step. But then what does the longlist step do?" |
| 20 | A consideration on "who decides" that is hard can exclude an option; one that is not hard gives the authority label only. | "yea fine" |
