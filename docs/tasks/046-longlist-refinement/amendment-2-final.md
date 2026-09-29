# Task 046 — amendment 2, final

> **Status:** decided by the owner 2026-09-29; the adversarial review ran the
> same day (two reviewers) and the owner decided on its results. Nothing in
> this file is built. The contract items of § 3 are in `contract.md`
> § Amendment 2 (2026-09-29); the phases of § 5 are in `plan.md` § Amendment 2;
> the boxes are in `rubric.md` § Amendment 2. No file under `docs/specs/` is
> changed.
>
> **Source.** [amendment-2-proposed.md](amendment-2-proposed.md) is the
> record. Its sections, in order: the first proposal (Parts A–F); the owner's
> first and second answers; "Topic 1 decided" to "Topic 5 decided"; "Topic 4
> changed"; "Questions 15 to 18 decided"; "Questions 19 and 20 decided";
> "Questions 1 to 14 decided"; "The profile step: three more decisions";
> "After the adversarial review"; "Eight build questions, settled by the
> lead". Precedence: a later decision wins over an
> earlier one and over the first proposal; the owner's words win over the
> lead's. Where a decision changed something, this file gives the result and
> one line "Changed from …". Code statements were checked against the code at
> the head of `task/046-longlist-refinement`.
>
> **Who decided what.** Q1–Q14 and the six review decisions are the lead's
> recommendations, accepted by the owner (2026-09-29). Q15–Q20 and the three
> profile-step decisions are the owner's own choices. The lead's corrections
> after the review close gaps in the writing and change no decision. The
> eight build questions B1–B8 (§ 7.3) are the lead's decision (data shape or name); the owner can change it.
>
> **What is already built** (verification.md § Amendment pass 1): R29 (lever
> reason on the card), R30 (flag off the card), R31 (no place in the user's
> own design).
>
> Terms of `contract.md` § Terms apply. New terms: **line** (one row of "What
> it would take"), **mark** (the level word an option gets on a line when it
> stands out), **way A** (the comparison rule, § 2.3), **`option_profile`**
> (the new component, § 2.3), **profile of an option** (its lever type,
> ambition, eight lines and setting).

## 1. Summary

For the reader of the longlist, amendment 2 adds:

1. A plan that keeps five kinds of user statement apart, with a new
   constraint kind `consideration`. The kind `requirement` is renamed
   `boundary`. What the user says about who can act is a consideration on
   the line "who decides".
2. A new component, `option_profile`, between `longlist` and `constrain`. It
   writes all that is said about an option: the lever type, ambition, the
   eight lines and the setting.
3. On every option card, a collapsible block "What it would take": eight
   lines, each one plain sentence, six of them with a mark when the option
   stands out from the list. Collapsed, it is a row of eight cells.
4. A new meaning for **ambition**: how big a proposal the option is against
   the baseline, as a relative mark (Smaller · Bigger). The three old bands
   go.
5. The delivery setting as a fact about the option, not about each record.
6. Outcome **counts** per option, in documents. No direction of effect.
7. An authority label (is the option within the user's power), and a filter
   on it. It never excludes. Constrain's exclusions do not change in kind.
8. Plain list rows, and a grid whose columns the reader chooses.

## 2. The decided design

### 2.1 The plan

**Five kinds** (A1; owner: "Yes these 5 kinds feel right." · "the plan kinds
look good").

| Kind | What it is | Rule at the longlist | Stored as |
|---|---|---|---|
| Boundary | What the option is | Can exclude | constraint kind `boundary` (review decision 5; the screen word stays "requirement") |
| Authority | Who has the power to adopt | Gives the authority label only; never excludes (review decision 3) | constraint kind `consideration` on the line "who decides" (Q17) |
| Implementation consideration | What the adopter has or lacks | No effect on exclusions and no label at the longlist. The plan stores it (a limit with `hard: true`); the shortlist of task 3 reads it with the option's line (review decisions 3, 4) | constraint kind `consideration`, with `aspect` and `hard` |
| Transferability consideration | How far evidence from elsewhere applies | Kept for the assessment; nothing judges it at the longlist | constraint kind `consideration` with `aspect` = `transferability`; no effect at the longlist (B1, the lead's decision (data shape or name); the owner can change it) |
| Aim | The outcome wanted | Becomes the plan's outcomes | the plan's present field `intended_change` (`runtime/scoping_plan.py:574-599`); no new field (A5; B2, the lead's decision (data shape or name); the owner can change it) |

- Changed from the first proposal (A1): no consideration excludes, hard or
  not (Q1, then review decision 3).
- Changed from the first proposal (A2): there is no plan slot "Who decides"
  (Q17).
- Changed from Q20: a hard consideration on "who decides" no longer
  excludes (review decision 3).

**The rename** (review decision 5). The kind `requirement` becomes
`boundary` in `ConstraintKind` and `CHECKED_AT_BY_KIND`
(`runtime/scoping_plan.py:94`, `:99-105`) and in the planning wire
(`runtime/task_agent_scoping_prompt.py:83-95`). No product code reads the old
name. The stored test plans of the replay clones are corrected by a one-off
script in the gitignored evidence folder (the plans that
`evidence/pre-contract-runs/set_requirements.py` wrote). Stored plans of
other tasks are not handled (R52).

**Constraint kinds after this amendment** (A3): `boundary`, `consideration`
(new), `preference` (kept, for a wish about what the option achieves, for
example "at least moderate evidence"), `evidence_restriction` (unchanged).
A `consideration` is checked at `assessment`, the same stage as `preference`;
`CheckedAt` keeps its values `longlist`, `assessment`, `retrieval`. The
authority label that constrain writes is a label, not a check (B3, the lead's decision (data shape or name); the owner can change it).

**`consideration`** (A3; Q2, Q17):

- It names its **aspect**: one of the eight line keys of § 2.10, or
  `transferability` (B1, the lead's decision (data shape or name); the owner can change it).
- A deadline names "time to set up", unless the user speaks of results; then
  it names "time to effect".
- One user sentence that names several things is stored as several
  considerations, one for each line.
- It carries `hard: true` only when the user states a limit ("no more than
  £2m a year", "in place by April 2027"). The user sets the limit in advance,
  never after the options are seen.
- Timing is not a kind of its own: a deadline is a time consideration with
  `hard: true`.

**Items adopted as written in the first proposal** (Q3; text copied from the
record):

| # | Text |
|---|---|
| A4 | "The Task Agent sorts a capacity statement as a consideration, never as a preference, and keeps the user's words in Your context." |
| A5 | "Aims. The Task Agent keeps the user's words as the aim and proposes outcomes that evidence can be read against ("households entering temporary accommodation per year"), tagged *assumed*. A wish about how long an effect lasts ("make the improvement last") is a preference, checked at assessment." |
| A6 | "A transferability consideration is stored with the plan and shown under the default preference "Transferable to *Where*". Nothing judges it at the longlist." |

**Who can act** (Q17; the lead's correction after the review). New behaviour
of planning prompt v5: when Where is below national level, the Task Agent
asks "Should I keep only options that a council can adopt, or also show
options that need national action?" (A2) and stores the answer as a
consideration on "who decides". The present prompt v4 has no such question.

### 2.2 The option profile: "What it would take"

Eight lines (topic 2; topic 4 for the names and level words).

| # | Line | Question | Mark | Level words (lower · higher; no mark shows no word) |
|---|---|---|---|---|
| 1 | Cost | Not decided. Tested: "What public money does the option need: what is paid for, once or every year, and does the amount grow with each person, firm or site it reaches?" | yes | Cheaper · Costlier |
| 2 | Time to set up | Not decided. Tested: "What must be done before the option starts to work for the first people or bodies it is for, and how long does that take?" | yes | Quicker · Slower |
| 3 | Time to effect | Not decided. Tested: the question in `profile_final_experiment.py` (from first reach to the plan's first outcome, and what sets that time) | yes | Quicker · Slower |
| 4 | Workforce requirements | Not decided. Decided content: one mark covers the number of people and the skills; the sentence tells which of the two causes the level | yes | Lower · Higher |
| 5 | Who decides | Decided content: one sentence that names one body, by its full name, and the country it assumes, from the plan's Where. It names a legal means only when the baseline or a document states it | **no** | — |
| 6 | Dependencies | Not decided. Tested: the one or two things outside the adopting body's control that the option cannot work without | **no** | — |
| 7 | Coordination requirements | **Decided:** "Which separate bodies must act together to set up and run the option, and how closely must they work together? Do not answer about what happens in one instance of delivery." | yes | Lower · Higher |
| 8 | Delivery complexity | Not decided. Tested: what must happen each time the option reaches one person, firm or site; the same action for all, or a judgement and tailoring for each | yes | Simpler · More complex |

"Tested" wording is the wording of the experiments
(`evidence/pre-contract-runs/profile_final_experiment.py`, results in
`evidence/rounds/9-profile-final-form.txt`). It is the start of the refine
loop, not a decision. "One body, by its full name" is the lead's prompt rule
from the known faults (§ 6.1).

- **"Middle"** is only a column head in the grid. On the card, a line with no
  mark shows no word (Q10).
- **"Cannot judge" is not a value.** A line always has a sentence; when
  nothing can be said, it has no mark (Q7).
- Changed from the first proposal: seven aspects with bands (B2) → eight
  lines with sentences and relative marks. "Powers" is split and cut
  (§ 2.4); legal change and acceptability are out (§ 4).
- Changed from the first proposal: "workforce" → "Workforce requirements";
  "coordination" (how many bodies) → "Coordination requirements".

### 2.3 The component `option_profile` and how a line is produced

| Rule | Decided | Source |
|---|---|---|
| Name and stage key | `option_profile` ("profile" alone already means the intervention profile of a record, `longlist.py:341`, and a stage of the replay tool, `replay.py:86`) | Review decision 6 (replaces the name `profile`) |
| Place in the walk | A component of its own between `longlist` and `constrain`, the same form as `theme`: `longlist → option_profile → constrain → theme` | Q15, Q19 |
| Spine | A spine step. No special failure rule: a line, ambition or setting call is tried again by the means the model calls have now; if it still fails, the step fails, as every other step of the walk fails. There is no code path for a built list with no profile. Lever typing keeps its behaviour as built: a failed or invalid typing batch keeps the previous typing (`longlist.py:1386-1391`; lead's decision from the plan review (2026-09-30)) | Profile-step decision 3; lead's correction; plan S20 |
| What `longlist` does | Makes the list: the options, their documents, the variants. It no longer types and no longer writes ambition | Profile-step decision 1; Q19 |
| What `option_profile` does | Writes all that is said about an option: the lever type (lever typing moves here from `longlist` as built, with its keep-previous rule for one invalid typing (B8, the lead's decision (data shape or name); the owner can change it); typing is `longlist`'s step 6 and no later part of `longlist` reads it), ambition, the eight lines, the setting. `suggest` uses the list of lever types, not the typing, and does not change | Profile-step decision 1 |
| One call for each line reads the **whole list** | Input of each line call: the plan (with Where for "who decides" only), the baseline, and for each option its design and at most 5 records ordered by role, as in the experiment. The caps are constants. The judgment model | Topic 1; lead's correction |
| The calls run at one time | Yes, with the ambition call and the setting call | Topic 1 |
| Output per option | One plain sentence that answers the line's question, and (on a marked line) the mark | Topic 1, topic 2 |
| Way A: only what stands out | An option gets a mark only when it clearly takes less or more than most of the list on that line. Every other option has no mark. On a list that differs little, nobody stands out. The sentence is always beside the mark and carries the kind of demand | Topic 2 |
| No fixed bands | No low/medium/high; no fixed list of answers | Topic 1; second answers |
| No anchor examples in the prompt | Yes | Topic 1; second answers |
| No guards on top of the prompt | The three guards the lead first proposed are dropped | Topic 1 |
| The "basis" mark | Dropped: not produced, not stored | Q8 |
| Stability | Accepted for a first version: cost 92 percent, the other lines near 80 percent, sentence always beside the mark | Topic 2 |
| No score, no rank | The marks are not added or weighted. The list does not sort by a line; the grid with reader-chosen columns does the comparison | B6; Q3 |
| When lines are made again | A full rebuild of the longlist makes all lines again. An exclusion or a merge by the reader does not | Q12 |
| Excluded options | An excluded option has its profile, because the profile runs before constrain | Q16 |

**"Add an option"** (review decision 1): it does not change. The added option
gets its documents and its lines at the next rebuild of the list. Until then
it shows with no lever type and no lines, as an added option shows with no
lever type today: the card hides "What it would take", and the grid keeps the
present "Untagged" column for it (`frontend/src/views/longlist/LonglistGrid.tsx:53-70`;
lead's adjudication of the review). Building an added option in place belongs
to task 3.

- Changed from the first proposal: one pass in batches (B1), bands (B2) and
  "take the harder band" (B5) are replaced.
- Changed from Q12: the profile no longer runs after constrain (Q15), and the
  add-one form is removed (review decision 1).
- Changed from Q19: the failure rule (list with no profile, constrain with
  no labels) is withdrawn (profile-step decision 3).
- Time: the step takes about one minute in every form tested. The experiment
  `9-profile-final-form.txt` ran ten calls at one time (eight lines,
  ambition, setting) in 54 seconds on the live obesity list.

### 2.4 "Powers", "Who decides" and the authority label

- "Powers" held two questions (who decides; is a new law needed). It is split,
  then cut.
- "Who decides" is line 5 (§ 2.2). No mark.
- **The authority label.** Constrain compares the line "who decides" with the
  user's consideration on "who decides", and labels the option. Label values
  (B4, not changed later): *within your power* · *needs action by <body>* ·
  *unclear*.
- **"Who decides" never excludes** at the longlist. It gives the label only,
  and the reader can filter the list by the label. It is not the sort order
  (review decision 3; Q3).
- With no consideration on "who decides", the option has no authority label
  (Q9, Q17).
- **One exception to "place never reaches constrain"** (review decision 2):
  the line "who decides" names the body and the country that it assumes, from
  the plan's Where, and constrain reads that line. The rule stands for all
  else: evidence from another place is never excluded for its place.
  Constrain's plan data still strips place from the question, the intended
  change and the target unit (`options_scoping/constrain/constrain.py:204-212`).
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
| How it is made | Its own call over the whole list, in `option_profile`. Lever typing no longer writes `ambition` or `ambition_reason` (Q4) |
| Where it is stored | The columns `option.ambition` and `option.ambition_reason` (`core/schema.py:1600-1601`). They are plain text with no check constraint, so the revision does not change them (lead's correction) |
| The old bands | Removed: the three bands, `ambition_bands` on the longlist read model (`api/contract/read_models.py:1010`, `api/readmodels/repository.py:3533`), "group by ambition" on the list (`LonglistView.tsx:44-49`, `:356-368`) and the ambition word on a list row (`longlistPresentation.ts:220-224`). This change to the read model is not additive (lead's correction) |
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
  batches against 10 from one call). It runs in `option_profile`.
- No fixed list of setting kinds (R32 stands).
- The list's Setting facet uses it. The record's own words stay on each
  document in the database. "Studied in" (the record's words shown on each
  document) is **not built in task 046**: no read-model field, no place on
  the screen; it goes to later work (B4, the lead's decision (data shape or name); the owner can change it).
- On the card it shows in "What it is" (Q11).

### 2.7 Outcomes at the longlist: counts only

(Topic 5; Q5; lead's correction after the review.)

- Each option shows how many documents evaluated it, and, among those
  documents, how many report on each outcome of the plan.
- **Counted in documents, not records.** A document counts for a plan outcome
  when one of its records that evaluates the option has that `outcome_tag`. A
  document with records on two outcomes counts for both.
- The counts come from the existing `outcome_tag`. **No new field, no prompt
  change.**
- **Known limit:** a record carries one plan outcome, so a record that
  reports on two plan outcomes counts for one of them. If the refine loop or
  the live check shows that this hides much, the lead brings a new field to
  the owner then.
- No direction of effect, no size, no verdict. The direction of an effect
  belongs to the shortlist assessment. The profile prompt keeps its present
  rule "no directions of effect".
- On the card the counts show in "What the evidence base holds so far" (Q11).
- Changed from topic 5: the record gains no new fact and no column.
- Changed from the first proposal: C1, C3 and C4 are not built.

### 2.8 Constrain

Constrain runs after `option_profile` and reads it (Q15, Q19). Decided:

- Boundary: can exclude (A1).
- **D1 is not in amendment 2** (B5, the lead's decision (data shape or name); the owner can change it): constrain's exclusions
  do not change. D1 was accepted by Q3; it waits for a change to exclusions.
- **A consideration has no effect on exclusions** (review decision 3). The
  authority label of § 2.4 is constrain's only new output.
- **B8** (accepted by Q3; text copied from the record): "The reasoned guess
  per preference is removed where the preference is about an aspect: the
  profile answers it. A preference about what the option achieves keeps its
  guess." Constrain's guess code needs no change for it: the planning prompt
  stores an aspect statement as a consideration (A4), so no preference about
  an aspect reaches constrain. B8 is a rule of the planning prompt only
  (lead's adjudication of the review; constraint model at
  `runtime/scoping_plan.py:298-310`).
- The relevant screen, the in-scope screen and the distinct screen stay as
  built (R21, item 5).
- Excluded options stay visible with one reason each (as built).
- **Known limit, merges** (lead's correction): the marks were made with the
  duplicate on the list; the kept option keeps its own lines
  (`constrain.py:36-47`).
- Changed from Q1: no limit label (review decision 4). The plan stores the
  limit; the option has its line; the shortlist step of task 3 reads both.

### 2.9 The reader

| Surface | Decided |
|---|---|
| List rows | Plain. No marks and no ambition word on a row (topic 4; lead's correction) |
| List grouping | Theme and lever type; group by ambition is removed (lead's correction) |
| List filter | The authority label (review decision 3; Q3) |
| Option card, "What it is" | Adds ambition after the lever line (Q4) and the delivery setting (Q11) |
| Option card, "What it would take" | The section collapses like the card's other sections. **Collapsed:** a row of eight cells, the line name above and the level word below; a line with no mark shows no word (variant C). The cells do not open single sentences. **Expanded:** all eight lines, the line name and its mark on the left, the sentence on the right (variant B). No summary paragraph (variant A). Hidden for an added option before the next rebuild (topic 4 changed, Q10, review decision 1) |
| Default state of "What it would take" | Collapsed when the card opens (lead's recommendation, accepted by the owner (2026-09-29): the row of cells is the summary, the eight sentences are long) |
| Option card, "What the evidence base holds so far" | Adds the outcome counts (Q11) |
| Label | The block heading says what it is: Policy Atlas's estimate before assessment (B7). No sentence ends with "a guess rather than evidence". Exact heading words come with the spec change wording (§ 7) |
| Grid | Rows as built (lever types, `LonglistGrid.tsx:22-27`). The reader chooses which line gives the columns (ambition, cost, or another line). Columns: lower word · Middle · higher word, and "Untagged" for an option with no profile yet (topic 3, topic 4, Q10, review decision 1) |
| Level words | § 2.2 and § 2.5. Not "less than most", "like most", "more than most" (topic 4) |
| Compare table | Dropped. The grid is the comparison (topic 4) |
| Mark colours | Tints from the Nesta palette. Not decided which (§ 7) |

- Changed from topic 4: "all eight lines, always open" → collapsed row of
  cells (variant C), expanded lines (variant B), collapsed by default.

### 2.10 Storage, migration, time, stored data

**Storage** (lead's correction after the review, and the lead's adjudication
of the review for the key):

- **One new JSON column on `longlist_result`** (`core/schema.py:1705-1721`),
  named below.
  This is the one alembic revision that the owner allowed (Q6; review).
- Keyed by option id, and within it by design version, as `judgements` is
  keyed (`core/schema.py:1716-1717`; `constrain.py:65-67`). No code in this slice
  edits a design in place, so this changes nothing today.
- **Column:** `longlist_result.option_profile` (B6, the lead's decision (data shape or name); the owner can change it).
- **Line keys:** `cost`, `time_to_set_up`, `time_to_effect`, `workforce`,
  `who_decides`, `dependencies`, `coordination`, `delivery_complexity`. A
  consideration's `aspect` uses the same keys (plus `transferability`).
- **Per option:** for each line key, the sentence and the mark; the setting
  (a main setting and at most one more). A mark is stored as `less`, `more`
  or null (no mark); the words on the screen come from the view. An option
  that is not profiled yet has no entry.
- The lever type stays in the option's columns. The typing data stays in
  the same keys of the same `longlist_result` row (`provenance.lever_reason`,
  `provenance.runner_up`, `provenance.typing`, `counts.typing_invalid`,
  `provenance.prompt_versions.typing`, `provenance.models.typing`), now
  written by `option_profile`, so the read side does not change (plan S20;
  lead's decision from the plan review (2026-09-30)).
- Ambition stays in `option.ambition` (its mark: `less`, `more` or null)
  and `option.ambition_reason` (its sentence) (§ 2.5; B6).
- The authority label is written by constrain into
  `longlist_result.judgements` (keyed `[option_id][design_version]`), one
  labelled entry for each option that has a label; never into
  `option_profile`. The option read model serves the profile from the column
  and the label from `judgements`; an option with no entry serves none (plan
  S18, S19; lead's decision from the plan review (2026-09-30)).

**Migration.** One reversible alembic revision on the head that task 046
left (`d8f3b6a2c4e1`): it adds that column. The downgrade drops it. No other
schema change; no new table.

- Changed from Q6: "no migration planned" → one revision for the profile
  column.

**Time.** No time limit is a pass condition. M8 stays a reported measure. The
walk stays a line: no side branch. F1 (measure first) is done.

**Stored data** (Q18). The build writes no code for stored values of an
earlier development iteration (old ambition words, lists with no profile).

**Known limits** (lead's adjudication of the review):

- The list shows no lever type, ambition or lines from the end of `longlist`
  to the end of `option_profile` (the step takes about one minute), as it
  shows no themes until `theme` ends.
- An added option has no lever type and no lines until the next rebuild.
- A record that reports on two plan outcomes counts for one (§ 2.7).
- Merges (§ 2.8).

## 3. Proposed contract items

These items are in `contract.md` § Amendment 2 (2026-09-29). Quoted words
are the owner's, copied from the record. "Reopens" names what each item
supersedes. For the six review decisions, the owner's answer to each was
"okay".

| # | Reopens | Ruling |
|---|---|---|
| R34 | AM8; R33 | **Five kinds of user statement.** Boundary (can exclude); authority (a consideration on "who decides"; gives the authority label, never excludes); implementation consideration (no effect on exclusions and no label at the longlist; `hard: true` marks a stated limit, stored for the shortlist); transferability consideration (kept for the assessment, A6); aim (the user's words; outcomes proposed and tagged *assumed*, A5). Constraint kinds: `boundary`, `consideration` with `aspect` and `hard`, `preference`, `evidence_restriction`. A consideration's `aspect` is one of the eight line keys or `transferability`; it is checked at `assessment`; the aim is `intended_change` (B1–B3, the lead's decision (data shape or name); the owner can change it). A consideration can name any of the eight lines; a deadline names "time to set up", or "time to effect" when the user speaks of results; one sentence that names several things gives one consideration for each line (Q2, Q17). A capacity statement is a consideration, never a preference (A4). AM8 ("No new plan field") is withdrawn. Owner: "Yes these 5 kinds feel right." · "the plan kinds look good" · "Maybe we should just have it sit in consideration rather than necessitating a who decide slot?" · review decision 3: "okay". Q2 and Q3: lead's recommendation, accepted by the owner (2026-09-29); owner: "I take your recommendations for the rest". |
| R35 | — | **Withdrawn (Q17).** It was the plan slot "Who decides" (owner then: "Yes"). Owner: "Maybe we should just have it sit in consideration rather than necessitating a who decide slot?" |
| R36 | R33 | **"What it would take": eight lines.** Cost · time to set up · time to effect · workforce requirements · who decides (no mark) · dependencies (no mark) · coordination requirements · delivery complexity. A line always has a sentence; "cannot judge" is not a value (Q7). Owner: "I think the 8 aspects are better, as we said before composite assessments are more likely to be inaccurate than if we split up the assessments right? Also a broad complexity dimension feels a bit hard to interpret." · "Yes dependencies feel distinct, I think it would still be useful information for the options page." · "Can't we just have "workforce requirements", "higher/lower" and that could cover both the number of staff and the skills? And "coordination requirements" higher or lower as well" · "Yes, I think something like that for coordination could work, but obviously we'll see what the prompt refinement results look like". Q7: lead's recommendation, accepted by the owner (2026-09-29). |
| R37 | R28; item 7 (typing in `longlist`) | **The component `option_profile`.** A spine component between `longlist` and `constrain`, the same form as `theme`, stage key `option_profile`. `longlist` makes the list (options, documents, variants); `option_profile` writes the lever type (typing moves here), ambition, the eight lines and the setting. One call per line over the whole list (the plan, with Where for "who decides" only; the baseline; per option its design and at most 5 records by role; caps as constants; the judgment model); way A marks; no bands, no fixed list of answers, no anchor examples, no guards; no basis mark (Q8). No special failure rule; lever typing keeps its behaviour as built (a failed or invalid batch keeps the previous typing) and its data stays in the same `longlist_result` keys (lead's decision from the plan review, 2026-09-30). A full rebuild makes all lines again; a reader's exclusion or merge does not (Q12); an excluded option keeps its profile (Q16). Owner: "I agree on topic 1" · "we should address the root clause, not apply a bandaid" · "Again a fixed list, what you've outlined feels too rigid at least for some of the aspects. Would those really work for a broad variety of domains?" · "Won't it be biased towards the domains that we name. When we're thinking about a generalised tool, I don't know how we can ensure we have good coverage of anchor examples" · "Yes I think that's good." (way A) · "that's good enough" (stability) · "Time is fine for now." · "This seems like added complexity for not much gain. Why don't we just run profile before constrain. As we saw before, constrain doesn't usually remove that many options anyway" · "Running profile before would make this moot" · "I think it is its own step. But then what does the longlist step do?" · "Doesn't the lever type also conceptually belong more in profile?" · "1. yes" · "3. maybe, I just think this might be overly defensive programming" · review decision 6: "okay". Q8 and Q12: lead's recommendation, accepted by the owner (2026-09-29). |
| R38 | A2 of the first proposal; R4 and AM7 (one exception) | **Who decides and the authority label.** The line names one body by its full name (the lead's prompt rule) and the country it assumes, from the plan's Where; a legal means only when the baseline or a document states it. Constrain reads the line (the one exception to "place never reaches constrain"; evidence from another place is never excluded for its place) and compares it with the user's consideration on "who decides". It gives the authority label only; it never excludes; the reader can filter the list by it; it is not the sort order (Q3); with no such consideration, no label (Q9). New in planning prompt v5: the Task Agent asks about who can act when Where is below national level and stores the answer as that consideration. "Powers" is cut; legal change is out. Owner: "I thought power was meant to be the authority in charge of something?" · "Yes I think that's good." · "authority would sort and label, and exclude only when the user says so." · "The legal change one feels like it might be prone to errors. Will that be based just on the LLMs knowledge of what's already in place?" · review decisions 2 and 3: "okay". Q3 and Q9: lead's recommendation, accepted by the owner (2026-09-29). |
| R39 | — | **Acceptability out; burden only after a test across domains.** Owner: "Let's leave it out, it feels too shaky. Maybe burden could be a good substitute but I feel like we would have to test a range of domains to decide if it's right to include". |
| R40 | Concept meaning of the ambition tag (do minimum · incremental · structural) | **Ambition is how big a proposal is, in relative levels.** Meaning, levels, sentence and the "do minimum" rule as final § 2.5. Its own call over the whole list in `option_profile`; stored in `option.ambition` and `option.ambition_reason`; on the card in "What it is", after the lever line (Q4). The three bands, `ambition_bands`, group by ambition and the ambition word on a list row are removed. Owner: "I liked ambition because it was short" · "If ambition is what's used in the green book and its what policymakers would be familiar with then I think it could stay but we just need to make sure that how we are deciding how ambitious something is makes sense" · "yes" · "These are likely to be quite small scale but it doesn't mean that the options can't necessarily be scaled to have a large reach" · "I think relative levels are quite good, it would make a better grid view" · "Agree". Q4: lead's recommendation, accepted by the owner (2026-09-29). |
| R41 | R32 ("nothing is built for it") | **The delivery setting is a fact about the option**, written by one call over the whole list in `option_profile`; no fixed list; the record keeps its setting words in the database; "studied in" is not built in task 046 (B4, the lead's decision (data shape or name); the owner can change it); on the card in "What it is" (Q11). Owner: "I think so, what's the difference between the option level, and the records?" (accepted in principle); R32 stands: "I don't think a fixed list is the right solution here given that policy atlas should be able to cater to a wide range of domains, and I don't think we'll be able to maintain a fixed list that would be able to do this". Q11: lead's recommendation, accepted by the owner (2026-09-29). |
| R42 | — | **Outcomes at the longlist are counts only, in documents.** Documents that evaluated the option; among them, documents for each plan outcome: a document counts for an outcome when one of its records that evaluates the option has that `outcome_tag`. No new field, no prompt change, no direction, size or verdict. Known limit: a record that reports on two plan outcomes counts for one. On the card in "What the evidence base holds so far" (Q11). Owner: "I think we need to think through the outcomes piece more." · "adding outcomes based on the old version is quite complex since there are a lot of different aspects" · "I think 2 sounds good." · "5,6. I take your recommendation". Q5 and Q11: lead's recommendation, accepted by the owner (2026-09-29). |
| R43 | Topic 4 ("all eight lines, always open") | **The reader.** Plain list rows (no marks, no ambition word); the card's "What it would take" collapses like the card's other sections: collapsed, a row of eight cells (line name above, level word below; the cells open nothing); expanded, the eight lines with the sentence; collapsed when the card opens; hidden for an added option before the next rebuild; a line with no mark shows no word, and "Middle" is only a grid column head (Q10); the grid with reader-chosen columns and "Untagged" for an option with no profile; no compare table; the list does not sort by a line (Q3). Owner: "On the list, I prefer plain" · "I don't like variant A in the option card. B looks pretty good. C feels too condensed and users would probably click through anyway" · "your idea of allowing the user to select which aspect the grid shows as the columns could be good" · "The compare page looks too information dense and would be offputting to users, I don't like it. Unless there's a better way to easily compare then we should drop it." · "In the grid view, I don't like the 'like most', 'less than most', and 'more than most' terms." · "Your words for the levels sound good. The ones I'm not sure about our workforce and coordination." · "I actually change my mind on the aspect variants on the card. Looking at it again, since the card's other sections are collapsible, I think variant C when collapsed, and B when expanded makes sense" · on the default state: "Yes sounds good." Q3, Q10 and the default state: lead's recommendation, accepted by the owner (2026-09-29). |
| R44 | OS trust § Reasoned guesses (spec change) | **The label moves to the block heading.** No sentence ends with "a guess rather than evidence". Owner: "we don't need 'a guess, not evidence', it sounds too LLM-generated." · "Sounds good". |
| R45 | § Constraints, Schema; § Stop conditions | **One alembic revision: one new JSON column, `longlist_result.option_profile`, for the profile** (name, line keys and mark values `less` · `more` · null: B6, the lead's decision (data shape or name); the owner can change it). Reversible; no other schema change; no new table. The stop condition "a second migration" becomes *a migration beyond this one revision*. The owner's earlier words: "Yea we'll need a db migration" · "We can do them as part of the migration we need to make for the plan anyway". Owner on Q6: "5,6. I take your recommendation". The column is the lead's correction after the review, inside the one revision that Q6 allowed. |
| R46 | Part F of the first proposal | **No time limit is a pass condition; no side branch.** M8 stays reported. Owner: "No. we can make it longer than 600 if needs be and optimise for latency afterwards." |
| R47 | Rulings 12 and 19 (a reasoned guess is never an input to the shortlist) | **For task 3: the profile informs the shortlist cut; the outcome signal waits.** The shortlist step reads the limits that the plan stores together with the option's lines (review decision 4). Owner: "the guesses are useful for how the shortlist selects. It needs something to decide how to cut the longlist down" · "Yes the profile will" · "it's the remit of the next task". |
| R48 | R27 | **Every new or changed prompt of amendment 2 goes through a refine loop on the replay tool.** Each loop names one stop measure; the other measures are reported (lead's correction). Owner: "All the prompts should go through refine loops anyway so that should hopefully get rid of most snags compared to your one off experiments." |
| R49 | — | **Measures M10, M11, M12, M14: reported**, except where a loop names one as its stop measure (Q13; lead's correction). M10 every option has a sentence on every line. M11 on the hard-requirement test data (the statements about who can act), the authority label is right for at least 9 of 10 options (read by hand). M12 the Setting facet of a list has at most 10 labels and no place or body name. M14 on the replays, the profile orders a nudge below a clinical service on delivery complexity (read by hand). Q13: lead's recommendation, accepted by the owner (2026-09-29); owner: "I take your recommendations for the rest". |
| R50 | — | **Withdrawn (review decision 4).** It was the limit label ("may not fit your limit"). The plan stores the limit; the option has its line; the shortlist of task 3 reads both. Owner: "okay". |
| R51 | — | **Withdrawn (review decision 1).** It was the add-one form of "Add an option". "Add an option" does not change; the added option gets its lines at the next rebuild. Owner: "okay". The owner's earlier question on Q12 stands in the record. |
| R52 | § Constraints, Stored data (for amendment 2's fields) | **No handling of stored values of an earlier development iteration.** Owner: "This feature is still in development and nothing is staged yet. We don't have to add complexity just due to an earlier development iteration. I don't care about old longlists, they don't exist in production or staging." |
| R53 | Plan kind `requirement` | **`requirement` is renamed `boundary`.** The replay clones' test plans are corrected by a one-off script in the gitignored evidence folder; it also rewrites the test statements about who can act as considerations on `who_decides` (B7, the lead's decision (data shape or name); the owner can change it); no product code reads the old name. Owner: "okay" (review decision 5). |

**Contract parts that change**

| Contract part | Change |
|---|---|
| § Constraints, Schema | One revision: one JSON column on `longlist_result` (R45). No new table |
| § Constraints, Prompts | New or revised: `task_agent_scoping_v5`; the line prompt(s); the ambition prompt; the setting prompt; lever typing (moved into `option_profile`); `constrain_v3`. `extract_interventions` does not change (R42). **Prompt-hash guard:** the wire models are prompt text (`task_agent_scoping_prompt.py:83-120`, `lever_typing_prompt.py:87-104`, `constrain_prompt.py:59-130`), so the rename, the move of typing and the ambition change re-pin hashes; these edits are the lead's |
| § Constraints, Stored data | No code for stored values of an earlier development iteration (R52) |
| § Public interface | **Not additive only.** Removed: `ambition_bands` on the longlist read model and group by ambition. Added: on the option read models the eight lines (sentence, mark), ambition in its new form, the delivery setting, the authority label, the outcome counts; on the plan read model the kind `consideration` with `aspect` and `hard`, and `boundary` in place of `requirement`; the grid's column choice; the authority-label filter; the stage key `option_profile` on the run stream. OpenAPI by `make openapi-sync` |
| § Walk | `longlist → option_profile → constrain → theme`; the walk stays a line (R37, R46) |
| § Stop conditions | As R45 |
| § Measures | R49; M8 stays reported (R46) |
| § Known limits | § 2.10 of this file |
| § Risk tier, rollback | `alembic downgrade -1` drops the profile column; deploy the previous image. The read-model change is not additive, so a longlist built by amendment 2 is not guaranteed to read cleanly under the previous image. Nothing of this feature is staged (R52) |
| § Spec changes | New items, wording to the owner: the five kinds and who can act as a consideration (OS components § 1, plan-as-object); `option_profile` as a component (the diagram, the component table, its own section, the ⟨longlist depth⟩ composition row, as item 0 did for `theme`); "What it would take", ambition's new meaning and the Green Book note, the setting at option level, the outcome counts (OS components § 6, OS capability § Output structure); the authority label and the place exception (OS components § 7); the label on the heading (OS trust § Reasoned guesses); the shortlist principle (OS capability § Pipeline and gates) |
| § Risk tier | Tier 4 stays |

## 4. What is cut or deferred

| Item | State | Reason | Owner's words |
|---|---|---|---|
| Acceptability line | Out | Least safe line to judge | "Let's leave it out, it feels too shaky." |
| "Burden" line | Deferred | Only after a test across a range of domains | "Maybe burden could be a good substitute but I feel like we would have to test a range of domains to decide if it's right to include" |
| Legal change line | Out of the first version | It rests on the model's knowledge; a grounded form is later work | "The legal change one feels like it might be prone to errors. Will that be based just on the LLMs knowledge of what's already in place?" |
| "Powers" line | Cut | It held two questions | "I thought power was meant to be the authority in charge of something?" |
| Plan slot "Who decides" (A2, R35) | Withdrawn (Q17) | Who can act is a consideration | "Maybe we should just have it sit in consideration rather than necessitating a who decide slot?" |
| Exclusion by "who decides" (Q20) | Withdrawn (review decision 3) | Label and filter only | "okay" |
| Limit label (Q1, R50) | Withdrawn (review decision 4) | The shortlist reads the stored limit and the line | "okay" |
| Add-one form of "Add an option" (Q12, R51) | Withdrawn (review decision 1) | Building an added option in place belongs to task 3 | "okay" |
| Failure rule of the profile step (Q19) | Withdrawn (profile-step decision 3) | No special path | "3. maybe, I just think this might be overly defensive programming" |
| Name `profile` | Replaced by `option_profile` (review decision 6) | "Profile" already has two meanings | "okay" |
| Profile after constrain (Q12) | Replaced (Q15) | Added complexity for little gain | "This seems like added complexity for not much gain. Why don't we just run profile before constrain. As we saw before, constrain doesn't usually remove that many options anyway" |
| Special case for "Include again" | Not needed (Q16) | An excluded option keeps its profile | "Running profile before would make this moot" |
| Handling of old longlists | Not built (Q18) | Nothing is staged | "This feature is still in development and nothing is staged yet. We don't have to add complexity just due to an earlier development iteration. I don't care about old longlists, they don't exist in production or staging." |
| Old ambition bands, `ambition_bands`, group by ambition, ambition word on a row | Removed | Replaced by relative ambition (lead's correction) | "Agree" (on "do minimum") |
| "Studied in" on each document | Later work (B4, the lead's decision (data shape or name); the owner can change it) | The record keeps its setting words in the database; no read-model field, no place on the screen | — |
| D1 (an exclusion needs a clear failure) | Not in amendment 2 (B5, the lead's decision (data shape or name); the owner can change it) | Constrain's exclusions do not change | — |
| Reported direction of outcomes (C1, C3, C4) | Not built | Belongs to the shortlist assessment | "I think 2 sounds good." |
| New outcome field on the record | Not built (Q5) | `outcome_tag` gives the counts | "5,6. I take your recommendation" |
| "Cannot judge" value | Dropped (Q7) | A line always has a sentence | "I take your recommendations for the rest" |
| Basis mark | Dropped (Q8) | Not reliable | "I take your recommendations for the rest" |
| Sort the list by a line (B6) | Not built (Q3) | The grid does this | "I take your recommendations for the rest" |
| Early signal as a shortlist input | Deferred to task 3 | — | "it's the remit of the next task" |
| Compare table | Dropped | Too dense | "The compare page looks too information dense and would be offputting to users, I don't like it. Unless there's a better way to easily compare then we should drop it." |
| Fixed bands (low/medium/high) | Dropped | Not calibrated across the option set | "Will high/med/low even be interpretable by users or even by downstream AIs? … if those bands aren't calibrated across the option set then it wouldn't be useful for comparisons either." |
| Named answers per aspect | Rejected | Too rigid | "Again a fixed list, what you've outlined feels too rigid at least for some of the aspects. Would those really work for a broad variety of domains?" |
| Anchor examples in the prompt | Rejected | Bias to named domains | "Won't it be biased towards the domains that we name. When we're thinking about a generalised tool, I don't know how we can ensure we have good coverage of anchor examples" |
| Naming the least and most demanding option | Rejected | — | "I don't think that idea is great, what are some other options?" |
| Way B (free groups with a phrase) | Rejected after two tests | Unstable groups | Lead's finding; the owner asked for the test |
| Ambition derived from the line marks | Rejected | Cost and ambition marks disagree often | Lead's test |
| Side branch (F3); 600-second pass condition (F4) | Rejected | — | "No. we can make it longer than 600 if needs be and optimise for latency afterwards." (This replaces "Keeping this step under 10 minutes is quite necessary".) |
| Summary paragraph (variant A) | Rejected | — | "I don't like variant A in the option card. B looks pretty good. C feels too condensed and users would probably click through anyway" |
| "All eight lines, always open" | Changed | Collapsible like the other sections | "I actually change my mind on the aspect variants on the card. Looking at it again, since the card's other sections are collapsible, I think variant C when collapsed, and B when expanded makes sense" · default state: "Yes sounds good." |

## 5. Build phases

These phases are in `plan.md` § Amendment 2. Phase numbers continue
`plan.md` (phases 0–8 are built). Executor marks: every prompt and its refine
loop = lead; judgement-bearing code = `deep-reasoner`; mechanical work =
`fast-worker`; real frontend design and final words = lead (with the
`impeccable` skill). Every loop: tuning set (obesity, refugees, caregiving,
energy), then one read of the check set (NEET, heat pumps, cohesion); at most
five rounds (R26); one stop measure, the other measures reported (R48);
report to the owner (R25).

**Gates.** Full `make verify` at 9.0, at the schema phase (10) and at the
exit (14). Other phases close on the gates in the table.

| Phase | Content | Executor | Gate |
|---|---|---|---|
| 9.0 | Build-open baseline | lead (one command) | full `make verify` |
| 9 | **The plan.** `requirement` → `boundary` at every rename site (plan § Phase 9), the prompt and wire as 9L round 0 in the same commit; kind `consideration` with `aspect` (the line keys) and `hard`; `consideration` checked at `assessment`; `aspect` values: the line keys or `transferability`; the one-off script that corrects the clones' test plans and rewrites their statements about who can act as considerations on `who_decides` (evidence folder, not product code); the replay tool's second planning turn. Plan read model and plan screen structure | `deep-reasoner` (plan model) · `fast-worker` (script, replay tool, plan screen structure) · lead (prompt, wire) | `make verify-fast` · `prompt-guard` · `drift-check` · `openapi-sync` · `frontend-verify` |
| 9L | **Planning loop:** `task_agent_scoping_v5` (five kinds, A4–A6, the deadline rule, one consideration per line, the new question about who can act, B8 as a planning rule). Stop measure (proposed): on the seven questions and the probe, every statement lands in the right kind and line, read by hand | lead | `make verify-fast` · `prompt-guard` |
| 10 | **Schema.** The one revision: the JSON column `longlist_result.option_profile`, round-trip test | `deep-reasoner` | **full `make verify`** |
| 11 | **Outcome counts.** In coverage, per option, in documents, from `outcome_tag` (R42) | `fast-worker` (exact rule) | `make verify-fast` · `drift-check` |
| 11A | **ADR 0040 amendment:** the walk `longlist → option_profile → constrain → theme`, typing in `option_profile`, the place exception; its own commit before Phase 12a | lead | `make verify-fast` |
| 12a | **The component `option_profile`, typing moved, no new prompt** (plan S16, S17, S20): chain; registration (`run_spec.py`, `harness.py`, `task_plan.py`, `LLM_BEARING_COMPONENTS`, `sse.py` both copies, `task_agent.py`, `stage_vocabulary.py`, `runProgress.ts`); spine; lever typing with its backend method, stub, Langfuse name and typing data moved; schema read and write; replay stage. The gate proves the lever types and typing keys of a stub run are as before | `deep-reasoner` · `fast-worker` | `make verify-fast` · `prompt-guard` · `drift-check` · `openapi-sync` · `frontend-verify` |
| 12b | **The line, ambition and setting calls** with 12L round 0 in the same commit (the lead's prompts, and the typing wire without ambition); writes as S17; a failed line call fails the step | `deep-reasoner` · lead | `make verify-fast` · `prompt-guard` · `drift-check` |
| 12L | **Profile loop:** the line prompt(s), the ambition prompt, the setting prompt, lever typing. Stop measure (proposed): none of the six known faults of § 6.1 on the tuning set, read by hand. Reported: lever spread and reasons; ambition counts and sentences. Also the first read of the R29 lever reasons and the R31 designs | lead | `make verify-fast` · `prompt-guard` |
| 13 | **Constrain.** Reads `option_profile`; the authority label from the line "who decides" and the consideration on it, never an exclusion, none without the consideration | `deep-reasoner` | `make verify-fast` · `prompt-guard` · `drift-check` |
| 13L | **Constrain loop:** `constrain_v3` on the refugees and obesity clones. Stop measure: M11, the authority label right for at least 9 of 10 options; no check-set read is possible for M11 | lead | `make verify-fast` · `prompt-guard` |
| 14a | **Read models and views.** Remove `ambition_bands`, group by ambition and the ambition word on a row; add the fields of § 3 and `make openapi-sync` (`fast-worker`). Structure (`fast-worker`): plain rows; the authority-label filter; "What it is" with ambition and setting; "What it would take" collapsed by default, hidden for an added option; outcome counts; the grid column chooser with "Middle" and "Untagged"; the Setting facet. Design and words (lead) | `fast-worker` · lead | `make verify-fast` · `prompt-guard` · `drift-check` · `frontend-verify` |
| 14 | **Exit.** Three live rapid runs; M1–M10, M12 and M14 read back from saved files (M11 from 13L); the browser check; spec changes with the owner's accepted wording; `docs/deferred.md`; `verification.md` | lead | **full `make verify`** |

## 6. Checks for the refine loops

### 6.1 Known faults in the test data

From `evidence/pre-contract-runs/replay-out/profile-final-form.json` (live
obesity). Each example was found in that file.

| Fault | Example | Check for the loop | Line |
|---|---|---|---|
| Setting "none" for an option that has a setting | front-of-pack labels; supermarket targets | Setting is empty only for a system-level instrument | setting |
| A mark that the sentence contradicts | lobbying controls: cost "less", the sentence says it needs legislation | The mark agrees with its sentence | all marked lines |
| No mark where the sentence lists much | active travel: no workforce mark | The mark agrees with its sentence | all marked lines |
| "Who decides" names a law by title and year | school food standards | A legal means only when the baseline or a document states it | who decides |
| "Who decides" names two bodies, or an acronym | children's meal standards; "DHSC" | One body, its full name | who decides |
| A sentence that answers another question | lobbying controls, time to effect | The sentence answers its line's question | all lines |

### 6.2 Other checks

| Check | Source |
|---|---|
| On a list that differs little, nobody stands out; no quota of marks | Topic 2 |
| Stability between two runs: cost about 92 percent, other lines about 80 percent or better | Topic 2 |
| Dependencies and time to effect were the least stable lines | Topic 1 |
| Every line has a sentence for every option (M10) | Q7; R49 |
| Setting: at most 10 labels, no place or body name, one word for one kind of place (M12) | B9; R49 |
| "Who decides" names the country from the plan's Where | Topic 2; review decision 2 |
| Ambition is not judged by the size of the studies or by whether the option would work | Topic 3 |
| The profile orders a nudge below a clinical service on delivery complexity (M14) | R49 |
| The authority label is right for at least 9 of 10 options on the hard-requirement data (M11); no exclusion comes from "who decides" | R49; review decision 3 |
| Planning: who can act → a consideration on "who decides"; the deadline rule; one consideration per line | Q2; Q17 |
| Outcome counts: how many evaluating records report on more than one plan outcome | R42 |
| Coordination answers about bodies acting together, not about one instance of delivery; measure the overlap with delivery complexity | Topic 4 |

### 6.3 Overlap between coordination and delivery complexity

Computed from saved files with the **old** coordination question. The first
loop round measures again with the decided question.

| Data | Options | Same level on both lines | Opposite | Checked by the lead |
|---|---|---|---|---|
| `aspect-pass-seven.json`, run 1, seven lists | 168 | 88 (52%) | 13 (8%) | **No** |
| `profile-final-form.json`, live obesity, way A | 24 | 14 (11 no mark on both; 3 the same mark) | 2 | Yes (Q14) |

## 7. Open items for the owner

### 7.1 Still open

1. **Tints** for the marks (lead's proposal: pale Nesta Violet for the
   higher level, pale Nesta Aqua for the lower level, navy text). The owner
   decides on the built screen.
2. **Spec wording.** [spec-changes-proposed.md](spec-changes-proposed.md)
   (task 046 build) is not applied. The new items of § 3 need wording,
   `option_profile` as a component included.
3. **Exact heading words** of "What it would take" and its label.
4. **The seven-list overlap figure** of § 6.3 is not checked by the lead.
5. **The line questions.** The question text of each line other than
   coordination is prompt work of the lead in the profile loop (12L),
   starting from the texts of the experiment `profile_final_experiment.py`.
   It is not an owner decision.
6. **The stop measures** of loops 9L and 12L are proposed by the plan; the
   lead confirms them at round 0.
7. The owner's stage decisions (R25) and the flag rate (R23) from the build.
8. Later work: a grounded legal-change line; a burden line; the outcome
   direction and the limits in task 3; building an added option in place
   (task 3); E2 and E3 of the first proposal (task 3); "studied in" on each
   document (B4).

### 7.2 Questions, answered (2026-09-29)

Q1–Q14: the lead's recommendation, accepted by the owner (owner: on Q1 "1. I
take your recommendation"; on Q5 and Q6 "5,6. I take your recommendation";
on Q12 "12. Why does add an option: need to run the calls again for the whole
list. Can't we just assess the aspects for just that one option, with the
context of what the other items have been marked as?"; on the rest "I take
your recommendations for the rest"). Q15–Q20: the owner's own choices.
"Replaced" names the later decision that wins.

| Q | Decision | State |
|---|---|---|
| Q1 | A limit never excludes; a limit label | Label **replaced** by review decision 4; "exclusion for who can act when the user says so" **replaced** by review decision 3 |
| Q2 | Any of the eight lines; the deadline rule; one consideration per line | stands |
| Q3 | D1, B8, A4–A6 accepted; no sort by a line; the authority label is a filter | stands; D1 **not in amendment 2** (B5) |
| Q4 | Ambition is its own whole-list call; on the card after the lever line | stands; old words **replaced** by Q18 |
| Q5 | Counts from `outcome_tag` | stands; counted in documents (lead's correction) |
| Q6 | Profile in the longlist result; no migration planned | **replaced**: one new JSON column (lead's correction, inside the allowed revision) |
| Q7 | No "cannot judge" | stands |
| Q8 | No basis mark | stands |
| Q9 | No authority label without the input | stands, restated by Q17 (a consideration) |
| Q10 | No word for no mark; "Middle" only in the grid | stands |
| Q11 | Setting in "What it is"; counts in "What the evidence base holds so far" | stands |
| Q12 | After constrain; add-one form; rebuild remakes all | "after constrain" **replaced** by Q15; add-one **replaced** by review decision 1; rebuild rule stands |
| Q13 | M10–M12, M14 reported | stands, with one stop measure per loop (lead's correction) |
| Q14 | Obesity overlap checked | stands |
| Q15 | Profile before constrain, on the whole list | stands |
| Q16 | No special case for "Include again" | stands |
| Q17 | No plan slot; who can act is a consideration | stands |
| Q18 | No handling of old longlists | stands |
| Q19 | A component of its own between `longlist` and `constrain` | stands; name **replaced** by `option_profile`; failure rule **withdrawn** |
| Q20 | Hard "who decides" can exclude | **replaced** by review decision 3 (never excludes) |

### 7.3 Build questions, settled by the lead (2026-09-29)

Each answer is the lead's decision (data shape or name); the owner can change it. None is the owner's words. (Numbered B1–B8 here;
the record numbers them 1–8.)

| B | Question | The lead's decision |
|---|---|---|
| B1 | How is a transferability consideration stored? | `aspect` is one of the eight line keys or `transferability`; a transferability consideration has no effect at the longlist |
| B2 | Where is the aim stored? | The plan's present field `intended_change`; no new field |
| B3 | Which stage checks a `consideration`? | `assessment`, as `preference`; no new `CheckedAt` value; the authority label is a label, not a check |
| B4 | How is "studied in" served? | Not built in task 046; later work |
| B5 | Does D1 stay? | No: constrain's exclusions do not change |
| B6 | Column, line keys, mark values | `longlist_result.option_profile`; keys `cost`, `time_to_set_up`, `time_to_effect`, `workforce`, `who_decides`, `dependencies`, `coordination`, `delivery_complexity`; mark `less`, `more` or null; no entry = not profiled yet; ambition's mark the same way in `option.ambition` |
| B7 | Does the one-off script rewrite the who-can-act test statements? | Yes, as considerations on `who_decides`; the planning loop tests prompt v5 separately |
| B8 | Does keep-previous typing move? | Yes, with lever typing, as built |

No open question in § 7 blocks a phase.
