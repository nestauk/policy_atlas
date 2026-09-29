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
