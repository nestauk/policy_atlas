# Task 046 — amendment 2, final

> **Status:** decided by the owner 2026-09-29; adversarial review still to
> come. Nothing in this file is built. The contract items of § 3 are in
> `contract.md` § Amendment 2 (2026-09-29); the phases of § 5 are in
> `plan.md` § Amendment 2. No file under `docs/specs/` is changed.
>
> **Source.** [amendment-2-proposed.md](amendment-2-proposed.md) is the
> record: the first proposal (Parts A–F, ten decisions), the owner's first and
> second answers, "Topic 1 decided" to "Topic 5 decided", "Topic 4 changed",
> and "Questions 15 to 18 decided". The answers to Q1–Q14 are the lead's
> recommendations, accepted by the owner on 2026-09-29; the answers to
> Q15–Q18 are the owner's own choices. The owner's words are quoted in § 3,
> § 4 and § 7.2. This file states the result only. Precedence: a later
> decision wins over an earlier one and over the first proposal; the owner's
> words win over the lead's. Where a decision changed something, this file
> gives the result and one line "Changed from …".
>
> **What is already built** (verification.md § Amendment pass 1): R29 (lever
> reason on the card), R30 (flag off the card), R31 (no place in the user's
> own design). R32 (setting) and R33 (constraints) were open; this amendment
> answers them.
>
> Terms of `contract.md` § Terms apply. New terms: **line** (one row of "What
> it would take"), **mark** (the level word an option gets on a line when it
> stands out), **way A** (the comparison rule, § 2.3), **profile** (the lines,
> the marks, the setting and ambition of an option).

## 1. Summary

For the reader of the longlist, amendment 2 adds:

1. A plan that keeps five kinds of user statement apart, with a new
   constraint kind `consideration`. What the user says about who can act is
   a consideration on the line "who decides".
2. On every option card, a collapsible block "What it would take": eight
   lines, each one plain sentence, six of them with a mark when the option
   stands out from the list. Collapsed, it is a row of eight cells.
3. A new meaning for **ambition**: how big a proposal the option is against
   the baseline, as a relative mark (Smaller · Bigger), not three fixed bands.
4. The delivery setting as a fact about the option, not about each record.
5. Outcome **counts** per option: documents that evaluated it, and, among
   them, documents that report on each plan outcome. No direction of effect.
6. Two labels from constrain: the authority label (is the option within the
   user's power) and a limit label ("may not fit your limit on cost").
7. Plain list rows, and a grid whose columns the reader chooses.

## 2. The decided design

### 2.1 The plan

**Five kinds** (A1; owner: "Yes these 5 kinds feel right." · "the plan kinds
look good").

| Kind | What it is | Rule at the longlist | Stored as |
|---|---|---|---|
| Boundary | What the option is | Can exclude | constraint kind `boundary` (the present `requirement`; the screen word stays "requirement") |
| Authority | Who has the power to adopt | Labels (§ 2.4); excludes only when the user says so | constraint kind `consideration` on the line "who decides" (Q17) |
| Implementation consideration | What the adopter has or lacks | Informs. A hard one gets a limit label; it never excludes (§ 2.8) | constraint kind `consideration`, with `aspect` and `hard` |
| Transferability consideration | How far evidence from elsewhere applies | Kept for the assessment; nothing judges it at the longlist | stored with the plan, shown under the default preference "Transferable to *Where*" (A6) |
| Aim | The outcome wanted | Becomes the plan's outcomes | the user's words as the aim; outcomes proposed by the Task Agent, tagged *assumed* (A5) |

- Changed from the first proposal (A1): an implementation consideration
  marked hard no longer excludes (Q1).
- Changed from the first proposal (A2): there is no plan slot "Who decides"
  (Q17).

**Constraint kinds after this amendment** (A3): `boundary`, `consideration`
(new), `preference` (kept, for a wish about what the option achieves, for
example "at least moderate evidence"), `evidence_restriction` (unchanged).

**`consideration`** (A3, A4; Q2, Q17):

- It names its **aspect**: any of the eight lines of § 2.2, "who decides"
  included.
- A deadline names "time to set up", unless the user speaks of results; then
  it names "time to effect".
- One user sentence that names several things is stored as several
  considerations, one for each line.
- It carries `hard: true` only when the user states a limit ("no more than
  £2m a year", "in place by April 2027"). The user sets the limit in advance,
  never after the options are seen.
- The Task Agent sorts a capacity statement as a consideration, never as a
  preference, and keeps the user's words in Your context (A4).
- Timing is not a kind of its own: a deadline is a time consideration with
  `hard: true`.

**Who can act** (Q17, and the lead's note on what follows from it): the Task
Agent still asks its question when Where is below national level ("Should I
keep only options that a council can adopt, or also show options that need
national action?", A2) and stores the answer as a consideration on "who
decides". The `hard` flag carries "exclude only when the user says so": a
hard consideration on "who decides" can exclude; one that is not hard gives
the authority label (§ 2.4).

**Aims** (A5): the Task Agent keeps the user's words as the aim and proposes
outcomes that evidence can be read against, tagged *assumed*. A wish about how
long an effect lasts is a preference, checked at assessment.

A4–A6 are accepted as written in the first proposal (Q3).

The plan payload is JSON, so the new kind needs no column.

### 2.2 The option profile: "What it would take"

Eight lines (topic 2; topic 4 for the names and level words).

| # | Line | Question | Mark | Level words (lower · higher; no mark shows no word) |
|---|---|---|---|---|
| 1 | Cost | Not decided. Tested: "What public money does the option need: what is paid for, once or every year, and does the amount grow with each person, firm or site it reaches?" | yes | Cheaper · Costlier |
| 2 | Time to set up | Not decided. Tested: "What must be done before the option starts to work for the first people or bodies it is for, and how long does that take?" | yes | Quicker · Slower |
| 3 | Time to effect | Not decided. Tested: the question in `profile_final_experiment.py` (from first reach to the plan's first outcome, and what sets that time) | yes | Quicker · Slower |
| 4 | Workforce requirements | Not decided. Decided content: one mark covers the number of people and the skills; the sentence tells which of the two causes the level | yes | Lower · Higher |
| 5 | Who decides | Decided content: one sentence that names the body, with the place it assumes (from the plan's Where). It names a legal means only when the baseline or a document states it | **no** | — |
| 6 | Dependencies | Not decided. Tested: the one or two things outside the adopting body's control that the option cannot work without | **no** | — |
| 7 | Coordination requirements | **Decided:** "Which separate bodies must act together to set up and run the option, and how closely must they work together? Do not answer about what happens in one instance of delivery." | yes | Lower · Higher |
| 8 | Delivery complexity | Not decided. Tested: what must happen each time the option reaches one person, firm or site; the same action for all, or a judgement and tailoring for each | yes | Simpler · More complex |

"Tested" wording is the wording of the experiments
(`evidence/pre-contract-runs/profile_final_experiment.py`, results in
`evidence/rounds/9-profile-final-form.txt`). It is the start of the refine
loop, not a decision.

- **"Middle"** is only a column head in the grid. On the card, a line with no
  mark shows no word (Q10).
- **"Cannot judge" is not a value.** A line always has a sentence; when
  nothing can be said, it has no mark (Q7).
- Changed from the first proposal: seven aspects with bands (B2) → eight
  lines with sentences and relative marks. "Powers" is split and cut
  (§ 2.4); "Who decides" is a line; legal change and acceptability are out
  (§ 4).
- Changed from the first proposal: "workforce" → "Workforce requirements";
  "coordination" (how many bodies) → "Coordination requirements" with the
  question above.

### 2.3 How a line is produced

| Rule | Decided | Source |
|---|---|---|
| When | The profile runs **before constrain**, on the whole list, all lines in one step | Q15 |
| One call for each line reads the **whole list** | The call gets the line's question, the plan, and the design and evidence records of every option | Topic 1 |
| The calls run at one time | Yes | Topic 1 |
| Output per option | One plain sentence that answers the line's question, and (on a marked line) the mark | Topic 1, topic 2 |
| Way A: only what stands out | An option gets a mark only when it clearly takes less or more than most of the list on that line. Every other option has no mark. On a list that differs little, nobody stands out. The sentence is always beside the mark and carries the kind of demand | Topic 2 |
| No fixed bands | No low/medium/high; no fixed list of answers | Topic 1; second answers |
| No anchor examples in the prompt | Yes | Topic 1; second answers |
| No guards on top of the prompt | The three guards the lead first proposed are dropped | Topic 1 |
| The "basis" mark (from the documents / estimate) | Dropped: not produced, not stored | Q8 |
| Stability | Accepted for a first version: cost 92 percent, the other lines near 80 percent, sentence always beside the mark | Topic 2 |
| No score, no rank | The marks are not added or weighted. The list does not sort by a line; the grid with reader-chosen columns does the comparison | B6; Q3 |

**"Add an option"** (Q12, kept by Q15): the lines of the **new** option only
are made, one call for each line. Each call gets the other options' sentences
and marks for that line as context. The marks of the other options do not
change. This add-one form is a new prompt variant and goes through the refine
loop.

**When lines are made again** (Q12): a full rebuild of the longlist makes all
lines again. An exclusion or a merge by the reader does not.

**Excluded options** (Q16): an excluded option has its profile, because the
profile runs before constrain. "Include again" makes nothing.

- Changed from the first proposal: one pass in batches (B1), bands (B2) and
  "take the harder band" (B5) are replaced.
- Changed from Q12: the profile no longer runs after constrain (Q15).
- Changed from topic 1: the place (lower, middle, higher for every option)
  and the flag "wide / narrow" are replaced by way A.
- Time: the step takes about one minute in every form tested. The time comes
  from the sentences, not from the way of comparison. The experiment
  `9-profile-final-form.txt` ran ten calls at one time (eight lines,
  ambition, setting) in 54 seconds on the live obesity list.

### 2.4 "Powers", "Who decides" and the authority label

- "Powers" held two questions (who decides; is a new law needed). It is split,
  then cut.
- "Who decides" is line 5 (§ 2.2). No mark.
- **The authority label.** Constrain compares the line "who decides" with the
  user's consideration on "who decides" that is not hard, and labels the
  option. Label values (B4, not changed later): *within your power* · *needs
  action by <body>* · *unclear*.
- A **hard** consideration on "who decides" can exclude (lead's note on Q17).
- With no consideration on "who decides", the option has no authority label
  (Q9, as restated by the lead's note on Q17).
- The authority label is a **filter** on the list, not the sort order (Q3).
- An option that needs action by another body stays on the list with that
  body named, unless the user's hard consideration excludes it (D3; Q17).
- Legal change is out of the first version (§ 4).

### 2.5 Ambition

| Item | Decided |
|---|---|
| The word | "Ambition" stays (topic 3) |
| The meaning | How big a proposal the option is: how much it sets out to change, compared with what the baseline says is in place now. Judged on the kind of action as if adopted in full: an adjustment to something in place, something new beside it, or a change to how the system works (who is entitled, who provides, who pays, what the rules are) (topic 3) |
| Not the basis | The size of the studies; whether the option would work (that is the assessment) (topic 3) |
| The levels | Relative, way A: more ambitious than most · less ambitious than most · no mark. Words: Smaller · Bigger; "Middle" only as a grid column head (topic 3, topic 4, Q10) |
| The sentence | One sentence under the mark: what the option changes against the baseline (topic 3) |
| "Do minimum" | No option is called "do minimum" at the longlist. Do minimum and preferred way forward belong to the shortlist (topic 3) |
| From the aspects | No. Ambition is not derived from the line marks (on seven lists the cost mark agreed with the ambition mark for 33 of 79 marked options and was the opposite for 16) (topic 3) |
| How it is made | Its own call over the whole list, in the profile step. Lever typing stops writing `ambition` and `ambition_reason` (Q4) |
| On the card | In "What it is", after the lever line (Q4) |
| For the specification | The Green Book compares versions of one option; Policy Atlas compares kinds of action on one list (topic 3) |

- Changed from the first proposal: the three fixed bands (do minimum,
  incremental, structural) go.
- Changed from Q4: no rule for old stored words (Q18).

### 2.6 The delivery setting at option level

(B9; owner, decision 5: "I think so, what's the difference between the option
level, and the records?" — accepted in principle.)

- A fact about the option ("delivered through: school"): one main setting and
  at most one more, in words that fit the field, the same word for the same
  kind of place across the list. Empty for a system-level instrument.
- It needs **one call over the whole list** (Part F finding: 17 labels across
  batches against 10 from one call). It runs in the profile step.
- No fixed list of setting kinds (R32 stands).
- The list's Setting facet uses it. The record's own words stay on each
  document as "studied in".
- On the card it shows in "What it is" (Q11).

### 2.7 Outcomes at the longlist: counts only

(Topic 5; Q5.)

- Each option shows how many documents evaluated it, and, among those
  documents, how many report on each outcome of the plan.
- The counts come from the existing `outcome_tag` (one plan outcome for each
  record). **No new field, no prompt change.**
- No direction of effect, no size, no verdict. The direction of an effect
  belongs to the shortlist assessment. The profile prompt keeps its present
  rule "no directions of effect".
- On the card the counts show in "What the evidence base holds so far"
  (Q11).
- **Known limit:** a document that reports on two plan outcomes is counted
  for one. If the refine loop or the live check shows that this hides much,
  the lead brings a new field to the owner then.
- Changed from topic 5: the record gains no new fact and no column.
- Changed from the first proposal: C1 (direction and result basis), C3
  (withhold under 3 documents) and C4 (the "Early signal" label) are not
  built.

### 2.8 Constrain

Constrain runs after the profile step (Q15). Decided:

- Boundary: can exclude (A1).
- **An exclusion needs a clear failure.** Mixed or missing information keeps
  the option and says so (D1, accepted by Q3).
- Who can act: a hard consideration on "who decides" can exclude; one that
  is not hard gives the authority label of § 2.4 (Q17, lead's note).
- **A limit on any other line never excludes at the longlist** (Q1).
  Constrain puts a label on the option ("may not fit your limit on cost") and
  gives the line's sentence as the reason. The shortlist step uses the label.
- **The reasoned guess per preference is removed** where the preference is
  about an aspect: the profile answers it. A preference about what the option
  achieves keeps its guess (B8, accepted by Q3).
- The relevant screen, the in-scope screen and the distinct screen stay as
  built (R21, item 5).
- Excluded options stay visible with one reason each (as built).

- Changed from the first proposal (D2): a hard consideration no longer
  excludes when its band is high.

### 2.9 The reader

| Surface | Decided |
|---|---|
| List rows | Plain. No marks on a row (topic 4) |
| List filter | The authority label is a filter on the list (Q3) |
| Option card, "What it is" | Adds ambition after the lever line (Q4) and the delivery setting (Q11) |
| Option card, "What it would take" | The section collapses like the card's other sections. **Collapsed:** a row of eight cells, the line name above and the level word below; a line with no mark shows no word (variant C). The cells do not open single sentences. **Expanded:** all eight lines, the line name and its mark on the left, the sentence on the right (variant B). No summary paragraph (variant A) (topic 4 changed, Q10) |
| Default state of "What it would take" | Collapsed when the card opens (lead's recommendation, accepted by the owner (2026-09-29): the row of cells is the summary, the eight sentences are long) |
| Option card, "What the evidence base holds so far" | Adds the outcome counts (Q11) |
| Label | The block heading says what it is: Policy Atlas's estimate before assessment (B7). No sentence ends with "a guess rather than evidence". Exact heading words come with the spec change wording (§ 7) |
| Grid | Rows as built (lever types, `frontend/src/views/longlist/LonglistGrid.tsx:22-27`). The reader chooses which line gives the columns (ambition, cost, or another line). Columns: lower word · Middle · higher word (topic 3, topic 4, Q10) |
| Level words | § 2.2 and § 2.5. Not "less than most", "like most", "more than most" (topic 4) |
| Compare table | Dropped. The grid is the comparison (topic 4) |
| Mark colours | Tints from the Nesta palette. Not decided which (§ 7) |

- Changed from the first proposal: the heading example "Implementation
  profile · …" → "What it would take".
- Changed from topic 4: "all eight lines, always open" → collapsed row of
  cells (variant C), expanded lines (variant B), collapsed by default.

### 2.10 Time, migration and stored data

**Time.** No time limit is a pass condition. M8 (wall-clock time per run)
stays a reported measure. The walk stays a line: no side branch.

- Changed from the first proposal: F2 (75-second budget), F3 (side branch)
  and F4 (600 seconds as a pass condition) are out. F1 (measure first) is
  done (`9-option-profile-time.txt`, `9-aspect-pass-*.txt`,
  `9-profile-final-form.txt`).

**Migration** (Q6). The profile (lines, marks, setting, ambition) and the
labels are stored in the longlist result (JSON). The plan's new kind is in
the plan's JSON payload. **Amendment 2 plans no migration.** If the build
finds that a column is necessary, there is one alembic revision for the whole
amendment, on the head that task 046 left (`d8f3b6a2c4e1`), reversible, and
the lead records why.

- Changed from topic 5: topic 5 planned one revision for the new outcome
  fact. Q5 drops that fact, so no column is planned.

**Stored data** (Q18). The build writes no code for stored values of an
earlier development iteration (old ambition words, lists with no profile).

## 3. Proposed contract items

Style of `contract.md` § Amendments after the live check. Quoted words are
the owner's, copied from the record. "Reopens" names what each item
supersedes. These items are in `contract.md` § Amendment 2 (2026-09-29).

| # | Reopens | Ruling |
|---|---|---|
| R34 | AM8; R33 | **Five kinds of user statement.** Boundary (can exclude), authority (a consideration on "who decides"; labels; excludes only when the user says so), implementation consideration (informs; a hard one gets a limit label and never excludes, R50), transferability consideration (kept for the assessment), aim (becomes the outcomes). Constraint kinds: `boundary` (screen word "requirement"), `consideration` with `aspect` and `hard`, `preference`, `evidence_restriction`. A capacity statement is a consideration, never a preference. A consideration can name any of the eight lines; a deadline names "time to set up", or "time to effect" when the user speaks of results; one sentence that names several things is stored as one consideration for each line (Q2, Q17). A4–A6 as written in the first proposal (Q3). AM8 ("No new plan field") is withdrawn. Owner: "Yes these 5 kinds feel right." · "the plan kinds look good" · "Maybe we should just have it sit in consideration rather than necessitating a who decide slot?" Q2 and Q3: lead's recommendation, accepted by the owner (2026-09-29); owner: "I take your recommendations for the rest". |
| R35 | — | **Withdrawn (Q17).** It was the plan slot "Who decides" (owner then: "Yes"). There is no such slot; what the user says about who can act is a consideration on the line "who decides" (R34, R38). Owner: "Maybe we should just have it sit in consideration rather than necessitating a who decide slot?" |
| R36 | R33 | **"What it would take": eight lines.** Cost · time to set up · time to effect · workforce requirements · who decides (no mark) · dependencies (no mark) · coordination requirements · delivery complexity. Coordination and delivery complexity stay apart. A line always has a sentence; "cannot judge" is not a value (Q7). Owner: "I think the 8 aspects are better, as we said before composite assessments are more likely to be inaccurate than if we split up the assessments right? Also a broad complexity dimension feels a bit hard to interpret." · "Yes dependencies feel distinct, I think it would still be useful information for the options page." · "Can't we just have "workforce requirements", "higher/lower" and that could cover both the number of staff and the skills? And "coordination requirements" higher or lower as well" · "Yes, I think something like that for coordination could work, but obviously we'll see what the prompt refinement results look like". Q7: lead's recommendation, accepted by the owner (2026-09-29). |
| R37 | — | **One call per line over the whole list; way A; before constrain.** Each line is one plain sentence per option. An option gets a mark only when it clearly takes less or more than most of the list. No bands, no fixed list of answers, no anchor examples, no guards. The basis mark is dropped (Q8). The profile runs before constrain, on the whole list, all lines in one step (Q15); an excluded option keeps its profile and "Include again" makes nothing (Q16); a full rebuild makes all lines again, a reader's exclusion or merge does not (Q12). Owner: "I agree on topic 1" · "we should address the root clause, not apply a bandaid" · "Again a fixed list, what you've outlined feels too rigid at least for some of the aspects. Would those really work for a broad variety of domains?" · "Won't it be biased towards the domains that we name. When we're thinking about a generalised tool, I don't know how we can ensure we have good coverage of anchor examples" · "Yes I think that's good." (way A) · "that's good enough" (stability) · "Time is fine for now." · "This seems like added complexity for not much gain. Why don't we just run profile before constrain. As we saw before, constrain doesn't usually remove that many options anyway" · "Running profile before would make this moot". Q8 and Q12: lead's recommendation, accepted by the owner (2026-09-29). |
| R38 | A2 of the first proposal | **Who decides and the authority label; powers cut; legal change out.** The line names one body and the place it assumes; a legal means only when the baseline or a document states it. The Task Agent's question about who can act is stored as a consideration on "who decides". A hard one can exclude; one that is not hard gives the authority label; with none, no label (Q9, Q17). The label is a filter on the list, not the sort order (Q3). Owner: "I thought power was meant to be the authority in charge of something?" · "Yes I think that's good." · "authority would sort and label, and exclude only when the user says so." · "The legal change one feels like it might be prone to errors. Will that be based just on the LLMs knowledge of what's already in place?" · "Maybe we should just have it sit in consideration rather than necessitating a who decide slot?" The hard / not-hard rule is the lead's note on what follows from Q17. Q3 and Q9: lead's recommendation, accepted by the owner (2026-09-29). |
| R39 | — | **Acceptability out; burden only after a test across domains.** Owner: "Let's leave it out, it feels too shaky. Maybe burden could be a good substitute but I feel like we would have to test a range of domains to decide if it's right to include". |
| R40 | Concept meaning of the ambition tag (do minimum · incremental · structural) | **Ambition is how big a proposal is, in relative levels.** Meaning, levels, sentence and the "do minimum" rule as § 2.5. Ambition is its own call over the whole list; lever typing stops writing `ambition` and `ambition_reason`; on the card, ambition is in "What it is", after the lever line (Q4). Owner: "I liked ambition because it was short" · "If ambition is what's used in the green book and its what policymakers would be familiar with then I think it could stay but we just need to make sure that how we are deciding how ambitious something is makes sense" · "yes" · "These are likely to be quite small scale but it doesn't mean that the options can't necessarily be scaled to have a large reach" · "I think relative levels are quite good, it would make a better grid view" · "Agree". Q4: lead's recommendation, accepted by the owner (2026-09-29). |
| R41 | R32 ("nothing is built for it") | **The delivery setting is a fact about the option**, written by one call over the whole list; no fixed list; the record's words stay as "studied in"; on the card in "What it is" (Q11). Owner: "I think so, what's the difference between the option level, and the records?" (accepted in principle); R32 stands: "I don't think a fixed list is the right solution here given that policy atlas should be able to cater to a wide range of domains, and I don't think we'll be able to maintain a fixed list that would be able to do this". Q11: lead's recommendation, accepted by the owner (2026-09-29). |
| R42 | — | **Outcomes at the longlist are counts only.** Documents that evaluated the option; among them, documents that report on each plan outcome, counted from the existing `outcome_tag`. No new field, no prompt change. No direction, size or verdict. Known limit: a document that reports on two plan outcomes is counted for one; if the loop or the live check shows that this hides much, the lead brings a new field to the owner. On the card in "What the evidence base holds so far" (Q11). Owner: "I think we need to think through the outcomes piece more." · "adding outcomes based on the old version is quite complex since there are a lot of different aspects" · "I think 2 sounds good." · "5,6. I take your recommendation". Q5 and Q11: lead's recommendation, accepted by the owner (2026-09-29). |
| R43 | Topic 4 ("all eight lines, always open") | **The reader.** Plain list rows; the card's "What it would take" collapses like the card's other sections: collapsed, a row of eight cells (line name above, level word below; variant C; the cells do not open single sentences); expanded, all eight lines with the sentence (variant B); collapsed when the card opens; a line with no mark shows no word, and "Middle" is only a grid column head (Q10); the grid with reader-chosen columns; no compare table; the list does not sort by a line (Q3); level words of § 2.2 and § 2.5. Owner: "On the list, I prefer plain" · "I don't like variant A in the option card. B looks pretty good. C feels too condensed and users would probably click through anyway" · "your idea of allowing the user to select which aspect the grid shows as the columns could be good" · "The compare page looks too information dense and would be offputting to users, I don't like it. Unless there's a better way to easily compare then we should drop it." · "In the grid view, I don't like the 'like most', 'less than most', and 'more than most' terms." · "Your words for the levels sound good. The ones I'm not sure about our workforce and coordination." · "I actually change my mind on the aspect variants on the card. Looking at it again, since the card's other sections are collapsible, I think variant C when collapsed, and B when expanded makes sense" · on the default state: "Yes sounds good." Q3, Q10 and the default state: lead's recommendation, accepted by the owner (2026-09-29). |
| R44 | OS trust § Reasoned guesses (spec change) | **The label moves to the block heading.** No sentence ends with "a guess rather than evidence". Owner: "we don't need 'a guess, not evidence', it sounds too LLM-generated." · "Sounds good". |
| R45 | § Constraints, Schema; § Stop conditions | **No migration is planned for amendment 2.** The profile and the labels are stored in the longlist result (JSON); the plan's new kind is in the plan's JSON payload. One alembic revision for the whole amendment is allowed only if the build finds that a column is necessary; the lead records why. The stop condition "a second migration" becomes *a migration beyond that one allowed revision*. The owner's earlier words: "Yea we'll need a db migration" · "We can do them as part of the migration we need to make for the plan anyway". Changed by Q6, because Q5 removed the only planned column. Owner on Q6: "5,6. I take your recommendation". Q6: lead's recommendation, accepted by the owner (2026-09-29). |
| R46 | Part F of the first proposal | **No time limit is a pass condition; no side branch.** M8 stays reported. Owner: "No. we can make it longer than 600 if needs be and optimise for latency afterwards." |
| R47 | Rulings 12 and 19 (a reasoned guess is never an input to the shortlist) | **For task 3: the profile informs the shortlist cut; the outcome signal waits.** Recorded now; task 3 builds it. The shortlist step uses the limit label (R50). Owner: "the guesses are useful for how the shortlist selects. It needs something to decide how to cut the longlist down" · "Yes the profile will" · "it's the remit of the next task". |
| R48 | R27 | **Every new or changed prompt of amendment 2 goes through a refine loop on the replay tool**, the add-one variant of R51 included. The one-off experiments are not the final quality. Owner: "All the prompts should go through refine loops anyway so that should hopefully get rid of most snags compared to your one off experiments." |
| R49 | — | **Measures M10, M11, M12, M14: reported, not pass conditions**, until a loop gives real figures (Q13). M10 every option has a sentence on every line. M11 on the hard-requirement test, the authority label is right for at least 9 of 10 options (read by hand). M12 the Setting facet of a list has at most 10 labels and no place or body name. M14 on the replays, the profile orders a nudge below a clinical service on delivery complexity (read by hand). M13 of the first proposal (early signal withheld) is dropped. Q13: lead's recommendation, accepted by the owner (2026-09-29); owner: "I take your recommendations for the rest". |
| R50 | A1 and D2 of the first proposal; R33 | **A limit on an aspect never excludes at the longlist.** Constrain labels the option ("may not fit your limit on cost") with the line's sentence as the reason; the shortlist step uses the label. Exclusion stays for what the option is, and for who can act when the user says so (a hard consideration on "who decides", R38). An exclusion needs a clear failure; mixed or missing information keeps the option (D1). The reasoned guess per preference is removed where the preference is about an aspect (B8). Owner: "1. I take your recommendation" · "I take your recommendations for the rest". Q1 and Q3: lead's recommendation, accepted by the owner (2026-09-29). |
| R51 | — | **"Add an option" makes the lines of the new option only**: one call for each line, with the other options' sentences and marks for that line as context. The other options' marks do not change. Owner: "12. Why does add an option: need to run the calls again for the whole list. Can't we just assess the aspects for just that one option, with the context of what the other items have been marked as?" Q12: lead's recommendation, accepted by the owner (2026-09-29); kept by Q15. |
| R52 | § Constraints, Stored data (for amendment 2's fields) | **No handling of stored values of an earlier development iteration.** No code for old ambition words or for lists with no profile. Owner: "This feature is still in development and nothing is staged yet. We don't have to add complexity just due to an earlier development iteration. I don't care about old longlists, they don't exist in production or staging." |

**Contract parts that change**

| Contract part | Change |
|---|---|
| § Constraints, Schema | No migration planned; one revision allowed if a column proves necessary (R45). No new table |
| § Constraints, Prompts | New or revised: `task_agent_scoping_v5`; the line prompt or prompts (new; name not decided); the add-one variant (new, R51); the ambition prompt (new, whole list); the setting prompt (new, whole list); `lever_typing_v3` (stops writing ambition); `constrain_v3`. `extract_interventions` does not change (Q5) |
| § Constraints, Stored data | No code for stored values of an earlier development iteration (R52) |
| § Public interface | Additive: on the option read models, the eight lines (sentence, mark), ambition in its new form, the delivery setting, the authority label, the limit label, the outcome counts; on the plan read model, the kind `consideration` with `aspect` and `hard`; the grid's column choice; the authority-label filter. OpenAPI by `make openapi-sync` |
| § Walk | The profile step runs before `constrain`; the walk stays a line (R37, R46). See § 7.3 Q19 |
| § Stop conditions | As R45 |
| § Measures | R49; M8 stays reported (R46) |
| § Known limits | A document that reports on two plan outcomes is counted for one (R42) |
| § Spec changes | New items, wording to the owner: the five kinds, and who can act as a consideration (OS components § 1, plan-as-object); "What it would take", ambition's new meaning and the Green Book note, the setting at option level, the outcome counts (OS components § 6, OS capability § Output structure); the limit label and the clear-failure rule (OS components § 7); the label on the heading (OS trust § Reasoned guesses); the shortlist principle (OS capability § Pipeline and gates) |
| § Risk tier | Tier 4 stays. The adversarial review of this amendment runs later (§ 7) |

## 4. What is cut or deferred

"Q" rows up to Q14: lead's recommendation, accepted by the owner
(2026-09-29). Q15–Q18: the owner's own choices.

| Item | State | Reason | Owner's words |
|---|---|---|---|
| Acceptability line | Out | Least safe line to judge; a model that guesses resistance can mislead a senior reader | "Let's leave it out, it feels too shaky." |
| "Burden" line | Deferred | Only after a test across a range of domains | "Maybe burden could be a good substitute but I feel like we would have to test a range of domains to decide if it's right to include" |
| Legal change line | Out of the first version | It rests on the model's knowledge; law differs by place and changes; the reader knows it better. A grounded form (search and cite the legal basis) is later work | "The legal change one feels like it might be prone to errors. Will that be based just on the LLMs knowledge of what's already in place?" |
| "Powers" line | Cut | It held two questions; "Who decides" keeps the first | "I thought power was meant to be the authority in charge of something?" |
| Plan slot "Who decides" (A2) | Withdrawn (Q17) | Who can act is a consideration on the line "who decides" | "Maybe we should just have it sit in consideration rather than necessitating a who decide slot?" |
| Profile after constrain (Q12) | Replaced (Q15) | Added complexity for little gain | "This seems like added complexity for not much gain. Why don't we just run profile before constrain. As we saw before, constrain doesn't usually remove that many options anyway" |
| Special case for "Include again" | Not needed (Q16) | An excluded option keeps its profile | "Running profile before would make this moot" |
| Handling of old longlists (old ambition words, lists with no profile) | Not built (Q18) | Nothing is staged; old longlists exist only in development | "This feature is still in development and nothing is staged yet. We don't have to add complexity just due to an earlier development iteration. I don't care about old longlists, they don't exist in production or staging." |
| Reported direction of outcomes (C1, C3, C4) | Not built | The direction of an effect belongs to the shortlist assessment | "I think 2 sounds good." |
| New outcome field on the record, and its column | Not built (Q5, Q6) | The existing `outcome_tag` gives the counts; a new field comes back only if the loop or live check shows the known limit hides much | "5,6. I take your recommendation" |
| Exclusion on a limit on an aspect (D2) | Dropped (Q1) | A limit gives a label; the shortlist step uses it | "1. I take your recommendation" |
| "Cannot judge" value | Dropped (Q7) | A line always has a sentence; no mark when nothing can be said | "I take your recommendations for the rest" |
| Basis mark | Dropped (Q8) | Not reliable; not produced, not stored | "I take your recommendations for the rest" |
| Sort the list by a line (B6) | Not built (Q3) | The grid with reader-chosen columns does this | "I take your recommendations for the rest" |
| Recompute all lines on "Add an option" | Not built (Q12) | Marks a reader has seen stay stable; one option in about 25 moves "most" very little | "12. Why does add an option: need to run the calls again for the whole list. Can't we just assess the aspects for just that one option, with the context of what the other items have been marked as?" |
| Early signal as a shortlist input | Deferred to task 3 | — | "it's the remit of the next task" |
| Compare table | Dropped | Too dense; the grid is the comparison | "The compare page looks too information dense and would be offputting to users, I don't like it. Unless there's a better way to easily compare then we should drop it." |
| Fixed bands (low/medium/high) | Dropped | Not calibrated across the option set | "Will high/med/low even be interpretable by users or even by downstream AIs? … if those bands aren't calibrated across the option set then it wouldn't be useful for comparisons either." |
| Named answers per aspect | Rejected | Too rigid across domains | "Again a fixed list, what you've outlined feels too rigid at least for some of the aspects. Would those really work for a broad variety of domains?" |
| Anchor examples in the prompt | Rejected | Bias to the named domains | "Won't it be biased towards the domains that we name. When we're thinking about a generalised tool, I don't know how we can ensure we have good coverage of anchor examples" |
| Naming the least and most demanding option | Rejected | — | "I don't think that idea is great, what are some other options?" |
| Way B (free groups with a phrase) | Rejected after two tests | Four groups almost every time with a limit; 4 to 12 groups by kind with no limit; order changed between runs | Lead's finding; the owner asked for the test |
| Ambition's fixed bands and "do minimum" label | Dropped | 80 to 92 percent of live options were "incremental"; the label used the Green Book's words with another meaning | "Agree" (do minimum) |
| Ambition derived from the line marks | Rejected | Cost and ambition marks disagree often | Lead's test, after the owner's question |
| Side branch in the walk (F3); 600-second pass condition (F4) | Rejected | — | "No. we can make it longer than 600 if needs be and optimise for latency afterwards." (This replaces the earlier "Keeping this step under 10 minutes is quite necessary".) |
| Summary paragraph (variant A) on the card | Rejected | — | "I don't like variant A in the option card. B looks pretty good. C feels too condensed and users would probably click through anyway" |
| "All eight lines, always open" (topic 4) | Changed | The section collapses like the card's other sections: variant C collapsed, variant B expanded, collapsed by default. Variant C was first rejected as too condensed | "I actually change my mind on the aspect variants on the card. Looking at it again, since the card's other sections are collapsible, I think variant C when collapsed, and B when expanded makes sense" · default state: "Yes sounds good." |

## 5. Build phases

These phases are in `plan.md` § Amendment 2. Phase numbers continue
`plan.md` (phases 0–8 are built). Executor marks: every prompt and its refine
loop = lead; judgement-bearing code = `deep-reasoner`; mechanical work =
`fast-worker`; real frontend design and final words = lead (with the
`impeccable` skill). Every new or changed prompt goes through the loop of
`plan.md` § The loop on the replay tool: tuning set (obesity, refugees,
caregiving, energy), then one read of the check set (NEET, heat pumps,
cohesion); at most five rounds (R26); report to the owner (R25). One green
commit per phase and per loop round that changes a prompt.

**Gates.** Full `make verify` at 9.0 and at the exit (14). A phase that adds
a schema revision (only if R45's allowed revision is needed) also closes on
full `make verify`. Other phases close on the gates in the table.

| Phase | Content | Executor | Gate |
|---|---|---|---|
| 9.0 | Build-open baseline. The tree changed after the step-6 exit gate (verification.md § Amendment pass 1) | lead (one command) | full `make verify` |
| 9 | **The plan.** Plan model: kind `boundary` (renamed from `requirement`, screen word unchanged); kind `consideration` with `aspect` (any of the eight lines, "who decides" included) and `hard`; stored transferability consideration. No plan slot "Who decides". Plan read model additive. Plan screen structure | `deep-reasoner` (plan model) · `fast-worker` (plan screen structure, read model fields) | `make verify-fast` · `prompt-guard` · `drift-check` |
| 9L | **Planning loop:** `task_agent_scoping_v5` (five kinds; capacity → consideration; the deadline rule; one consideration per line for a sentence that names several things; the question about who can act, stored as a consideration on "who decides", hard only when the user says to keep only options within that power; aims as the user's words plus *assumed* outcomes). Planning replay on the seven questions plus the probe `9-plan-probe-temporary-accommodation.json` | lead | `make verify-fast` · `prompt-guard` |
| 10 | **Outcome counts.** In coverage, per option: documents that evaluate the option; among them, documents for each plan outcome, from the existing `outcome_tag`. No schema, no prompt change | `fast-worker` (exact rule from R42) | `make verify-fast` · `drift-check` |
| 11 | **The profile step.** Before `constrain`, on the whole list: one call per line over the whole list, the ambition call and the setting call, all at one time; stored in the longlist result; lever typing stops writing ambition; the add-one path for "Add an option" (R51); a full rebuild makes all lines again, a reader's exclusion or merge does not; the replay tool stage for it. Its form in the walk and its failure rule as § 7.3 Q19 decides | `deep-reasoner` (component, storage, add-one path) · `fast-worker` (replay stage wiring, tests from an exact list) | `make verify-fast` · `prompt-guard` · `drift-check`; full `make verify` if a revision is added (R45) |
| 11L | **Profile loop:** the line prompt(s), the add-one variant, the ambition prompt, the setting prompt, `lever_typing_v3`. Checks of § 6. Also the first read of the R29 lever reasons and the R31 designs, which no round has read | lead | `make verify-fast` · `prompt-guard` |
| 12 | **Constrain.** Reads the profile. The clear-failure rule (D1); a hard consideration on "who decides" can exclude; one that is not hard gives the authority label from the line "who decides", none when there is no such consideration; the limit label for a hard consideration on another line, with the line's sentence as the reason, never an exclusion; the reasoned guess removed for a preference about an aspect (B8) | `deep-reasoner` | `make verify-fast` · `prompt-guard` · `drift-check` |
| 12L | **Constrain loop:** `constrain_v3` with the hard-requirement test (`9-constrain-hard-requirements.txt`, the three clones that hold its requirements); M11 | lead | `make verify-fast` · `prompt-guard` |
| 13 | **Read models and views.** Additive read-model fields and `make openapi-sync` (`fast-worker`). Structure (`fast-worker`): plain rows; the authority-label filter; "What it is" with ambition after the lever line and the setting; the card block "What it would take", collapsed by default: collapsed a row of eight cells (name above, level word below), expanded the eight lines with sentences, no word for a line with no mark; the outcome counts in "What the evidence base holds so far"; the grid column chooser with "Middle" as the middle column head; the Setting facet from the option-level setting; the limit label; the plan screen's new kind; the compare table not built. Design and words (lead): the block in both states, the heading label, the level words, the tints put to the owner on the built screen | `fast-worker` (read models, structure, vitest) · lead (design, words) | `make verify-fast` · `prompt-guard` · `drift-check` · `frontend-verify` |
| 14 | **Exit.** Three live rapid runs (obesity, refugees, caregiving); M1–M12 and M14 read back from saved files (M10–M12 and M14 reported); spec changes with the owner's accepted wording; `docs/specs/log.md`; `docs/deferred.md` (burden, legal change grounded form, outcome direction to task 3, the two-outcome count limit); `verification.md` | lead | **full `make verify`** |

Likely surfaces (from `contract.md` § Surface map): `runtime/task_agent_scoping_prompt.py`;
`options_scoping/longlist/longlist.py`, `coverage.py`,
`lever_typing_prompt.py`, `lever_types.py`;
`options_scoping/constrain/constrain.py`, `constrain_prompt.py`;
`runtime/scoping_plan.py` (the walk); `api/contract/read_models.py`;
`frontend/src/views/longlist/OptionCard.tsx`, `LonglistView.tsx`,
`LonglistGrid.tsx`, `longlistPresentation.ts`.

## 6. Checks for the refine loops

### 6.1 Known faults in the test data

From the wireframe run (live obesity, the decided form;
`evidence/pre-contract-runs/replay-out/profile-final-form.json`). The record
says the lead had not checked them against the saved file. For this document
each example was found in that file.

| Fault | Example | Check for the loop | Line |
|---|---|---|---|
| Setting "none" for an option that has a setting | front-of-pack labels; supermarket targets | Setting is empty only for a system-level instrument (§ 2.6) | setting |
| A mark that the sentence contradicts | lobbying controls: cost "less", the sentence says it needs legislation | The mark agrees with its sentence | all marked lines |
| No mark where the sentence lists much | active travel: no workforce mark | The mark agrees with its sentence | all marked lines |
| "Who decides" names a law by title and year | school food standards | A legal means only when the baseline or a document states it | who decides |
| "Who decides" names two bodies, or an acronym | children's meal standards; "DHSC" | One body, its full name (lead's proposed prompt rule) | who decides |
| A sentence that answers another question | lobbying controls, time to effect | The sentence answers its line's question | all lines |

### 6.2 Other checks

| Check | Source |
|---|---|
| On a list that differs little, nobody stands out; no quota of marks | Topic 2, way A |
| Stability between two runs: cost about 92 percent, other lines about 80 percent or better | Topic 2 |
| Dependencies and time to effect were the least stable lines | Topic 1 |
| Every line has a sentence for every option; no "cannot judge" (M10) | Q7; R49 |
| Add-one variant: the new option's marks agree with a full whole-list run in most cases | Q12 |
| Setting: at most 10 labels per list, no place or body name, the same word for the same kind of place (M12) | B9; Part F |
| "Who decides" names the place from the plan's Where | Topic 2 |
| Ambition is not judged by the size of the studies or by whether the option would work | Topic 3 |
| The profile orders a nudge below a clinical service on delivery complexity (M14) | R49 |
| The authority label is right for at least 9 of 10 options on the hard-requirement test (M11) | R49 |
| A hard consideration on "who decides" can exclude; one that is not hard gives only the label | Q17 |
| A limit on another line gives a limit label with the line's sentence as the reason, and never an exclusion | Q1 |
| Planning: the answer about who can act becomes a consideration on "who decides"; a deadline names "time to set up", or "time to effect" when the user speaks of results; a sentence that names several things gives one consideration per line | Q2; Q17 |
| Outcome counts: note how many evaluating documents report on more than one plan outcome (the known limit of R42) | Q5 |
| Coordination answers about bodies acting together, not about one instance of delivery; measure the overlap with delivery complexity | Topic 4 |

### 6.3 Overlap between coordination and delivery complexity

The record states no figure. The figures below come from saved files, with
the **old** coordination question ("How many separate bodies must act
together, and across how many levels"). The first loop round must measure
again with the decided question.

| Data | Options | Same level on both lines | Opposite (one lower, one higher) | Checked by the lead |
|---|---|---|---|---|
| `aspect-pass-seven.json`, run 1, seven lists, a place for every option | 168 | 88 (52%) | 13 (8%) | **No** |
| `profile-final-form.json`, live obesity, way A marks | 24 | 14 (11 no mark on both; 3 the same mark) | 2 | Yes, it agrees (Q14) |

In the way A run, 13 options have a mark on at least one of the two lines; 3
of them have the same mark on both.

## 7. Open items for the owner

### 7.1 Still open

1. **Tints** for the marks. The lead's proposal: a pale Nesta Violet for the
   higher level, a pale Nesta Aqua for the lower level, navy text. The owner
   decides on the built screen.
2. **Spec wording.** [spec-changes-proposed.md](spec-changes-proposed.md)
   (task 046 build) is not applied. The new items of § 3 need wording too.
3. **Adversarial review of this amendment.** Owner: "not yet but we will do."
4. **Exact heading words** of "What it would take" and its label (decision 4:
   "The wording of the heading comes with the spec changes").
5. **The seven-list overlap figure** of § 6.3 (168 options, 52%) is not
   checked by the lead.
6. The owner's stage decisions (R25) and the flag rate (R23) from the build
   stay open. Constrain excluded no option in the three live runs
   (verification.md, known item 4).
7. **The line questions** other than coordination are not decided; the
   tested wording is the start of the loop (§ 2.2).
8. Later work: a grounded legal-change line; a burden line after a test
   across domains; the outcome direction in task 3; E2 (about five shortlist
   options) and E3 (every use of the profile in the cut shown as a written
   reason) of the first proposal are not ruled; they belong to task 3.

### 7.2 Questions, answered (2026-09-29)

Q1–Q14: the lead's recommendation, accepted by the owner. The owner's words:
on Q1, "1. I take your recommendation"; on Q5 and Q6, "5,6. I take your
recommendation"; on Q12, "12. Why does add an option: need to run the calls
again for the whole list. Can't we just assess the aspects for just that one
option, with the context of what the other items have been marked as?"; on
the rest, "I take your recommendations for the rest". Q15–Q18: the owner's
own choices; the words are in § 3 and § 4.

| Q | Decision |
|---|---|
| Q1 | A limit on an aspect never excludes at the longlist; constrain gives a limit label with the line's sentence as the reason; the shortlist uses it |
| Q2 | A consideration can name any of the eight lines; a deadline names "time to set up" (or "time to effect" for results); one consideration per line |
| Q3 | D1, B8 and A4–A6 accepted; the list does not sort by a line; the authority label is a filter |
| Q4 | Ambition is its own whole-list call; lever typing stops writing it; on the card in "What it is" after the lever line (its rule on old words is replaced by Q18) |
| Q5 | Outcome counts from the existing `outcome_tag`, among evaluating documents; no new field, no prompt change; known limit recorded |
| Q6 | The profile is stored in the longlist result; no migration planned; one revision only if a column proves necessary |
| Q7 | "Cannot judge" is not a value; a line always has a sentence |
| Q8 | The basis mark is dropped |
| Q9 | No consideration on "who decides" → no authority label |
| Q10 | A line with no mark shows no word; "Middle" is only a grid column head |
| Q11 | Setting in "What it is"; outcome counts in "What the evidence base holds so far" |
| Q12 | "Add an option" makes the new option's lines only, others unchanged; a full rebuild makes all lines again (its "after constrain" part is replaced by Q15) |
| Q13 | M10, M11, M12, M14 are reported, not pass conditions, until a loop gives real figures |
| Q14 | The obesity overlap figure is checked and agrees; the seven-list figure is not checked |
| Q15 | The profile runs before constrain, on the whole list, all lines in one step |
| Q16 | No special case: an excluded option has its profile; "Include again" makes nothing |
| Q17 | No plan slot "Who decides"; who can act is a consideration on the line "who decides" |
| Q18 | No handling of old longlists or stored values of an earlier development iteration |

### 7.3 New questions

**Q19.** Q15 says the profile runs before constrain "all lines in one step".
The record does not say the form of that step: inside the `longlist`
component (the first proposal's "simpler way"), or a component of its own
between `longlist` and `constrain` (R28 fixed the walk's last three
components as `longlist`, `constrain`, `theme`; a new component adds a stage
key to the run stream). The record also does not say what constrain does when
the profile step fails (constrain now reads the profile for both labels).

**Q20.** The hard / not-hard rule for a consideration on "who decides" (a
hard one can exclude; one that is not hard gives the label) is the lead's
note on what follows from Q17. The record shows no separate owner answer to
it. Confirm.
