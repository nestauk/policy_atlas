# Task 046 — amendment 3, final

> **Status:** decided by the owner 2026-09-30, topic by topic. Nothing in this
> file is built. No adversarial review has run yet (record, "What the build
> must do", item 6). The contract items of § 3 are in `contract.md`
> § Amendment 3 (2026-09-30); the phases of § 5 are in `plan.md` § Amendment 3;
> the boxes are in `rubric.md` § Amendment 3. No file under `docs/specs/` is
> changed.
>
> **Source.** [amendment-3-proposed.md](amendment-3-proposed.md) is the
> record. Its sections, in order: "Conclusions so far" (a summary written
> before topic 6); "Topic 1 decided" to "Topic 6 decided"; "Topic 6, decision
> 7 refined: the dossier's findings slot"; "Eighteen build questions from the
> final document" (the lead's answers); "The owner's answers on the four
> questions" (Q1, Q5, Q10, Q11). Precedence: a later decision wins
> over an earlier one; the owner's words win over the lead's. Where a
> decision changed something, this file gives the result and one line
> "Changed from …". Code statements were checked against the code at the head
> of `task/046-longlist-refinement` (`685c7157`).
>
> **Who decided what.** Topics 1–5 and topic 6 decisions 1–7 (with the
> refinement of decision 7) are the owner's, in the words quoted. The row
> "Also from the critique, accepted by the lead" and the layout row of topic 6
> are the lead's; the owner can change them. The 18 build questions are
> answered (§ 7.2): Q1, Q5, Q10 and Q11 by the owner; the others by the lead
> (the owner can change them). The owner's Q1 answer replaces the lead's Q1
> row and the "clustering call" of topic 6. One new question is open (§ 7.2,
> Q19). The seams S21–S26 (`plan.md` § Amendment 3) are proposals
> for the lead to confirm at the plan gate; none is the owner's.
>
> Terms of `contract.md` § Terms and of [amendment-2-final.md](amendment-2-final.md)
> apply. New terms: **folding call** (one model call that maps a list's
> distinct record words to a few kinds, § 2.2), **kind** (one label a folding
> call gives), **top level** and **level below** (the two levels of Where
> tried, § 2.4), **Examples** (the card list that replaces the variants,
> § 2.6), **`programme_name`** (the new record field, § 2.6).

## 1. Summary

For the reader of the longlist, amendment 3:

1. Folds the record words of **Tried on** and **Measures** into a few kinds per list, one mini-model call each; the code counts documents per kind per option.
2. Counts the plan's outcomes over documents of **any role**; the evaluated count stays its own figure; one outcomes table on the card.
3. Shows **Where tried** as countries in two levels, from the record's `study_geography`; the OECD rule and the four groups go.
4. Rebuilds the option card: no top boxes; **Examples** (the programme names of the option's records, at most 5, from a new record field `programme_name`) replace the variants; seven cells with "Middle" in the collapsed row; the authority label beside "Who decides"; checks folded; documents de-duplicated, sorted and opening the **source dossier**, whose findings slot shows the option's records.
5. Sets the grid's cell limit to 4. The authority label's rule does not change.
6. Adds one nullable column, `intervention_profile_record.programme_name`, in one alembic revision.

Already built after amendment 2 and **not** part of this amendment: rounds 2–4 of the profile loop (`evidence/rounds/12L-profile-loop.md`; table in § 2.10).

## 2. The decided design

### 2.1 Tried on at option level (topic 1)

| Item | Decided |
|---|---|
| The fault | The card's "Populations" line and the "Tried on" line and facet show verbatim record text: obesity 55 distinct labels over 80 entries, caregiving 33 over 48 |
| The concept | The plan's **target unit**: who or what should change (people, organisations or things). Not "population" |
| The line | One option-level line **"Tried on"**: the kinds of people, organisations or things the option's evidence covers, the plan's target unit first, then the others, with document counts; the same word for the same kind across the list; few labels; no fixed list |
| The facet | The list's Tried on facet reads it (labels, no counts; a filter: § 2.3) |
| On the card | All kinds (lead, Q8) |
| Removed from the card | The "Populations" line and the record-level "Settings" line of the evidence section; the record-level "Tried on" line |
| The words | "Tried on" stays |
| Unchanged | The record tags (on target · adjacent · other) and the counts that use them |

- Changed from topic 1: the line is made by a folding call (§ 2.2), not by a profile line. A profile line reads at most 5 records per option (`option_profile.py:106`), so it cannot give counts.
- Constrain keeps reading the coverage keys it reads today (`tried_on`, record-level `settings`, `constrain.py:360-384`); they stay in the coverage, hidden from the reader. M6 is retired (lead, Q9); its box becomes "Tried on shows kinds beyond the plan's target unit where the evidence has them".
- Code today: `tried_on` holds only the populations of `adjacent` members (`coverage.py:416-421`), at most 8 (`coverage.py:69`); `populations` holds every member's words (`coverage.py:404-410`); the card prints both and `settings` (`OptionCard.tsx:442-444`).

### 2.2 The folding calls, and how the code counts (topic 2)

| Rule | Decided |
|---|---|
| How many calls | **One folding call per facet**: one for Tried on, one for Measures |
| Input | The list's **distinct record words** (not the records); the plan's outcomes and target unit as reference |
| Output | Word → kind, in the field's words, the plan's words where they match, few kinds, no fixed list |
| Model | The mini model (in code, `LONGLIST_ASSIGNMENT_MODEL`, `longlist_backend.py:117-118`) |
| Where it runs | In the profile step (`option_profile`) |
| Counting | The code counts documents per kind per option |
| Refine loop | A prompt each, a refine loop each (lead), with the check "same word for the same kind; few kinds; the plan's words where they match" |

- Changed from topic 1: this replaces the profile-line mechanism written under topic 1.
- Plan outcomes (lead, Q4): the call gets the plan's outcomes as reference and labels a matching word with the plan outcome; a folded kind that equals a plan outcome is not a separate row of the outcomes table.
- No folding call for Examples (owner, Q1; § 2.6).
- Which record field feeds each call is not stated word for word. The record names "population/tried on" words for Tried on and "Outcomes measured" for Measures; the code holds them as the record's `population` and `outcome` (`coverage.py:146-148`). Seam S21 (`plan.md`) proposes these.

### 2.3 Counts, and no counts on the list (topic 2)

| Item | Decided |
|---|---|
| Counts by plan outcome | Count every document that reports on the plan outcome, **of any role**; the evaluated count stays its own figure |
| The list's facets | Setting, Tried on, Where tried: labels **without counts**, as the Setting facet does. Counts are on the card only |
| Filters (lead, Q8) | Tried on and Where tried (top level) filter the list, as Setting does; each facet folds after 8 chips |
| Measures facet (lead, Q8) | None on the list |
| How counts show on the card | Decided under topic 6 (§ 2.7, § 2.8) |

- Changed from amendment 2 (R42, the lead's decision "evaluating documents only"): any role. On the three live lists only 11 / 8 / 2 options of about 25 had an evaluating count above zero.
- Code today: `outcome_counts` counts documents with an `evaluated` member (`coverage.py:381-386`); the Tried on facet shows a count per chip (`LonglistView.tsx:503-515`).

### 2.4 Where tried: countries in two levels (topic 4)

| Item | Decided |
|---|---|
| Source | The record's `study_geography`, per intervention record, "exactly as the abstract states it". No new extraction for where tried. The setting pass still moves a place named as a setting into it (`coverage.py:203-219`) |
| No fallback | Never the publisher, journal, author institutions or publication country. "Not stated" stays "not stated" |
| No comparability label | Neither the OECD rule nor a model judgement at the longlist. Comparability belongs to transferability at the assessment (task 3) |
| **Top level** (four values, lead, Q6) | The country; **"multiple countries"** when the record's text names several countries or a group ("12 OECD countries"); **"other places"**: a stated place the matcher does not know, as written; **"not stated"** |
| Group words (lead, Q6) | "OECD" (as today) and "Europe", "European", "North America", "Nordic", "countries" |
| **Level below** | The record's text as written (lead, Q6): the city or region under its country ("Germany: Hamburg"); the countries under "multiple countries" ("Europe and North America"; "Sweden, Denmark, Finland") |
| Document grain (lead, Q7) | A document whose records name two countries counts under "multiple countries", with both texts below |
| One country | A record counts under one named country only when its own text names that country alone |
| List facet | The top level, as chips, no counts; a filter; folds after 8 chips (lead, Q8) |
| Card | Both levels, with document counts |
| Removed | The four groups (the user's place · comparable systems (OECD) · other · unknown) and the OECD rule |
| Check for the build | Among records with "not stated", how many abstracts name the place of the study. A fault only where the abstract names it. A fault goes to a refine round of the existing record prompt `extract_interventions` (lead, Q18) |

- Code today: `WHERE_GROUPS`, `COMPARABLE_LABEL`, `OECD_CODES` (`where_tried.py:33-41`), `where_group` (`:376-400`) and `where_labels` (`:403-418`); coverage counts one group per document (`coverage.py:391-392`) and already keeps the country codes per document (`coverage.py:393-397`). The contract's `WhereTriedOut` (`read_models.py:817-830`), `WhereTriedGroup` (`read_models.py:734`) and each document's `where_tried_group` (`read_models.py:1201`, `repository.py:3906`) carry the groups. The facet filters by group (`LonglistView.tsx:148-151`, `:471-484`).
- The matcher stays for the place strip (`strip_place`, `where_tried.py:465-510`) and the setting pass (`names_place`, `:518-534`).
- Changed from task 045 D20 (ADR 0039 decision 10): no grouping against the plan's Where.

### 2.5 The option card layout (topic 6)

In order (the lead's layout row, accepted into the topic):

| Part | Content and form |
|---|---|
| Header | Title; description; **one grey line**: lever · origin · relations · also found as; Exclude. No boxes, no "scoping pass" chip (decision 1) |
| What it is | The lever line: "**Lever:** Subsidise, with Regulate and Provide a service." (the other levers = the secondary lever types), the reason sentence under it; no runner-up line; no "also touches"; final words the lead's at build (owner, Q10); Delivered through; design features, at most 6; **Examples**, at most 5 (§ 2.6) |
| What it would take — Policy Atlas's estimate | Table: **Ambition first**, then the eight lines (name, word, sentence). The authority label beside the "Who decides" row: the word with its colour, then the sentence; only when the plan holds the consideration (owner, Q11). Collapsed: seven cells (§ 2.9) |
| Evidence | The outcomes table (§ 2.7); Roles; Where tried in two levels (§ 2.4); Tried on (§ 2.1); the abstracts note; the document list (§ 2.8) |
| Checks | The user's considerations first (the user's boundaries and preferences, which are judged; the kind `consideration` does not show, lead, Q12), the verdict as a word with its colour; the three built-in checks in one line unless one fails; no transferability line (decision 6) |

Also decided (lead, from the critique):

| Item | Decided | Code today |
|---|---|---|
| The abstracts note | One grey note in the evidence section: "Read from titles and abstracts only" (decision 1) | `abstractOnlySentence`, `OptionCard.tsx:446` |
| Ambition | First row of "What it would take" | In "What it is", `OptionCard.tsx:341` |
| The label | "Policy Atlas's estimate" (the decided words) | "Estimate, before assessment", `OptionCard.tsx:71` (verification D16) |
| Section titles | Name, not explain; final words: lead, at build | `SECTIONS`, `OptionCard.tsx:55-62` |
| Text size | No body sentence below 16 px | `text-meta` at `OptionCard.tsx:268`, `:446` |
| Origin section | Goes; origin and relations sit on the header's grey line | `OptionCard.tsx:479-481` |
| "What it is for" | Goes as a section; its content is the outcomes table (decision 4) | `OptionCard.tsx:356-366` |
| Code faults | Fixed: the documents sorted by title; the duplicate documents (the same document with two snapshot ids); a raw HTML entity in a title | § 2.8 |

Removed with the boxes: `SnapshotCells` (`OptionCard.tsx:302-309`) and the chip (`:244`). Removed with Q10 and Q11: the runner-up line (`OptionCard.tsx:340`) and the authority line in "What it is" (`:343`).

### 2.6 Examples, from the record field `programme_name` (topic 6, decision 3; owner, Q1)

| Item | Decided |
|---|---|
| The name | "Variants" becomes **"Examples"** |
| What an example is | A named programme, scheme or law that the records describe |
| The record field | `extract_interventions` gains one field, **`programme_name`**: the proper name of the programme, scheme or law that the abstract gives for this intervention, or null |
| On the card | The distinct programme names of the option's records, with document counts, at most 5, or none |
| No folding call | No folding call for examples, and not the clustering call |
| Storage | One nullable column `intervention_profile_record.programme_name` (`core/schema.py:1088-1135`), in **one alembic revision** for amendment 3, allowed by the owner; the head is `e9a4c1f7b3d2` |
| The prompt | One refine round of the record prompt (`extract_interventions_v2`, `extract_interventions_prompt.py:44`) |
| Where the list lives | In the coverage, as the variants are; remade on a rebuild (lead, Q3) |
| Folded seeds | Under "also found as" only; not examples (lead, Q2) |
| Why | The variants today are the records' intervention names, unjudged, so plain phrases land beside programme names |

- Changed from topic 6 decision 3 ("written as a new `examples` field by the clustering call") and from the lead's Q1 row (a folding-style call): the owner's Q1 answer.
- Changed from § 2.4's "No new extraction": that rule stays for where tried; `programme_name` is the one new record field, by the owner's Q1 answer.

- Code today: `variants` are the members' distinct intervention names, folded seeds first, at most 8 (`coverage.py:68-70`, `:422-459`), served as `VariantOut` (`read_models.py:1205-1219`) and shown under "Variants" (`OptionCard.tsx:344-353`).
- The gap that led to Q1: no clustering call reads all member records (discovery reads a names digest, `longlist_cluster_prompt.py:15-17`, `:201-204`; assignment judges one unit at a time, `:256-311`). The cluster prompt does not change.
- The record prompt's version is a component of the extraction fingerprint (`interventions_profile.py:101`): see Q19.

### 2.7 One outcomes table (topic 6, decision 4)

| Item | Decided |
|---|---|
| Rows | One row for each **plan outcome**, with a "serves" mark from the option design's pick; one row for each **other outcome kind** the records report (the folded Measures kinds of § 2.2) |
| Columns | Documents of any role · evaluated |
| Replaces | The section "What it is for" and the "Outcomes measured" line |

- Code today: the design's pick is `outcomes_served` (`repository.py:3122`, `_design_out` `:3722-3731`); the counts are `outcome_counts` (`coverage.py:484-490`), printed as sentences (`OptionCard.tsx:416-425`).
- A plan-outcome row counts from `outcome_tag` (R56); the other rows count from the folded Measures kinds; a folded kind that equals a plan outcome is not a separate row (lead, Q4).

### 2.8 The documents and the source dossier (topic 6, decision 7 and its refinement)

| Item | Decided |
|---|---|
| Duplicates | None |
| Order | Evaluated first, then by quality |
| Each document | A linked title and one grey meta line instead of chips: quality · type · role (the document's highest role under this option: evaluated, then described, then the rest) · place (the top level) · year; `OptionDocumentOut` gains `year` from the snapshot metadata (lead, Q13) |
| No row in this task | The title shows as plain text, not a link (lead, Q15) |
| How many | Five shown, then "Show all N" |
| No documents | The one line "No documents found yet." |
| On click | The **source dossier sidebar** of Evidence search (document level), reused; not the citation provenance panel |
| Other openers | In this amendment only the document list opens the dossier (lead, Q16) |
| The dossier's findings slot | On an **options-scoping task**, the slot "Findings from this source" shows the **intervention profile records** instead, under its own name. From an option card: **"In this option"**, the record for that option (intervention name, setting, tried on, outcomes measured, where, role). From the Sources tab: the document's records, one for each option that holds it. Each record in its own words (it is the record, not the fold); several records of one document each show (lead, Q14). Evidence search tasks are unchanged |

- Changed from decision 7: "The dossier gains a section for the option's own record" → no new section; the existing findings slot shows the records (refinement). The record's field list is the refinement's (no "design").
- Code today: one document per membership row, never DOI-collapsed (`repository.py:3741-3749`), sorted by title (`repository.py:3893-3911`); the card de-duplicates by snapshot id only (`OptionCard.tsx:186-194`); chips (`OptionCard.tsx:431-437`). The dossier: `SourceDossier` (`ArtefactView.tsx:1034-1082`, opened by the `source` search parameter, `:1401-1416`), keyed by this task's document row (`repository.py:2371-2395`); the body and the findings slot (`SourcesView.tsx:962`, `:1055-1064`) read `useFindings` (`queries.ts:357-370`), which calls `GET /tasks/{task_id}/findings?source_id=` (`routers/read_models.py:123-135`).

### 2.9 The collapsed row with "Middle" (topic 6, decision 5)

| Item | Decided |
|---|---|
| Collapsed "What it would take" | **Seven cells**: Ambition first, then the six marked lines; each with its word, **"Middle"** for the middle group (owner, Q5) |
| "Who decides", "Dependencies" | No level, so no cell (owner, Q5) |
| Blank cells | None, unless the option has no profile |
| Replaces | Amendment 2's Q10 ("no word for no mark on the card") |

- Changed from decision 5 ("eight cells"): seven, by the owner's Q5 answer.
- Code today: eight cells; a cell with no mark shows nothing (`OptionCard.tsx:374-389`).

### 2.10 Grid, authority, and what is unchanged (topics 3, 5)

| Item | Decided |
|---|---|
| Grid | `CELL_LIMIT` goes from 6 to **4** (`LonglistGrid.tsx:29`) |
| Authority label | Its rule is unchanged: shown only when the plan holds a consideration on who can act. Its place moves beside the "Who decides" row (owner, Q11; § 2.5). The Who can act facet stays |
| Record tags | Unchanged (on target · adjacent · other) and their counts |
| Delivered through | Unchanged (option-level setting, R41) |
| The profile step's ten calls, the marks, constrain's exclusions | Unchanged |
| "Add an option", Rebuild, Exclude, merges | Unchanged |

**Built after amendment 2, before this amendment** (committed; loop record `12L-profile-loop.md`):

| Round | Change to `option_profile_v1` | Result |
|---|---|---|
| 2 | "Who decides" names the body as its country's government publications do; never an acronym in place of a name, never a legal name the public does not use | One body each; no expanded or legal names |
| 3 | The mark rule: order the options on the line; lower part "less", upper part "more", middle none; about a third each where the data spreads; never forced | Stability 82–88% same mark on two runs; no opposite marks |
| 4 | The body is always one in the place of Where, never in the country of a study | No foreign body on England; a New South Wales Where named only Australian bodies, with state/federal errors (known unverified) |

## 3. Proposed contract items

In `contract.md` § Amendment 3 (2026-09-30). Quoted words are the owner's,
copied from the record. "Reopens" names what each item supersedes. "(lead,
Qn)" marks the lead's answer to a build question; the owner can change it.

| # | Reopens | Ruling |
|---|---|---|
| R54 | Terms, **tried on**; surface map item 23 | **Tried on at option level.** One option-level line "Tried on" replaces "Populations" and the record-level "Tried on" and "Settings" lines of the card. The concept is the plan's target unit (people, organisations or things), not "population": the kinds the option's evidence covers, the target unit first, with document counts; the same word for the same kind across the list; few labels; no fixed list; the card shows all kinds (lead, Q8). The list's Tried on facet reads it. The record tags and their counts do not change. Constrain keeps reading the coverage keys it reads today (`tried_on`, record `settings`); they stay in the coverage, hidden from the reader (lead, Q9). Owner: "the population/tried on list has similar issues to what the settings used to have before refinement, there's a lot of values and a lot of them overlap" · "is population the right concept to use given that policy atlas should work on a broad range of policy domains" · "1. yes" · "2. yes" · "3. yes" |
| R55 | — | **One folding call per facet.** Tried on and Measures are each made by one call over the list's distinct record words (not the records), on the mini model, in the profile step, with the plan's outcomes and target unit as reference: word → kind, in the field's words, the plan's words where they match, few kinds, no fixed list. The code counts documents per kind per option. This replaces the profile-line mechanism of topic 1. No folding call for examples (R63). Owner: "Perhaps outcomes also need to have a similar treatment, but check first" · "yes to all" |
| R56 | R42 ("documents that evaluated the option; among them …") | **Counts by plan outcome over documents of any role.** Every document that reports on the plan outcome counts, of any role; the evaluated count stays its own figure. Owner: "yes to all" |
| R57 | — | **The list's facets: no counts.** Setting, Tried on and Where tried show labels only; counts are on the card. Tried on and Where tried (top level) filter the list, as Setting does; each facet folds after 8 chips; no Measures facet on the list (lead, Q8). Owner: "We don't need the counts in the list view, as we don't have counts for the settings" · "I think we will refine the documents count in the option card refinement step anyway" |
| R58 | — | **The authority label's rule stays as it is**: shown only when the plan holds a consideration on who can act. Its place on the card is R70. Owner: "I'm not sure about the 'within in your power' part. Is this always shown. Most users will be in parliament or civil service, so won't most things be in their organisational power. I acknowledge that for things like local authorities then this would be more relevant" → "Yes leave as is" |
| R59 | Task 045 D20 (ADR 0039 decision 10); surface map item 26 (the groups) | **Where tried as countries, in two levels.** From the record's `study_geography` as the abstract states it; no fallback to publisher, journal, authors or publication country; no comparability label at the longlist (transferability, task 3). Top level, four values: the country · "multiple countries" (several countries or a group) · "other places" (a stated place the matcher does not know, as written) · "not stated" (lead, Q6). Group words: "OECD", "Europe", "European", "North America", "Nordic", "countries" (lead, Q6). Level below: the record's text as written (lead, Q6). A record counts under one named country only when its own text names that country alone; a document whose records name two countries counts under "multiple countries", with both texts below (lead, Q7). The facet shows the top level as chips, no counts; the card shows both levels with document counts. The four groups and the OECD rule are removed. The build checks, among "not stated" records, how many abstracts name the place; a fault goes to a refine round of `extract_interventions` (lead, Q18). Owner: "The where tried only lists the users location, then Comparable systems other and unknown. Is this granularity even useful?" · "that OECD rule feels weak" · "just because a document is published in one country, it doesn't necessarily mean that's where the option was tried" · "Should we fall back to publication country when the country isn't stated, is that defensible?" (the lead answered no; recorded as accepted) · "How much cost/latency would it add if we judged comparable with LLM calls. Would the quality of that even be sufficient?" · "Maybe then it would be a top level "multiple countries" and then the level below would be the countries as listed underneath, like in your example for Hamburg" |
| R60 | — | **Grid cell limit 4** (`CELL_LIMIT`, was 6). Owner: "I think it should be 3 instead" → "If it's 1 to 4 in most cases, then maybe 4 is the right value for N." |
| R61 | The card's top cells (task 045 card) | **No boxes in the header.** The four boxes and the "scoping pass" chip leave the header. The abstract-only fact becomes one grey note in the evidence section: "Read from titles and abstracts only". Owner: "1. Yes" |
| R62 | Item 7 (the runner-up on the card) | **The lever line keeps its reason and names the other levers.** The other levers are the secondary lever types. Form: "**Lever:** Subsidise, with Regulate and Provide a service.", the reason sentence under it; "also touches" goes; the runner-up line goes; final words the lead's at build (owner, Q10). Owner: "I think the reason is helpful. And if an option acts using multiple levers then that is useful information" · "10. Sounds good. But the wording of the reason needs to be refined. I don't like how it uses 'also touches'" → "2. yes" |
| R63 | R2 and AM20 (variants); Terms, **variant**; topic 6 decision 3 ("by the clustering call") | **Examples replace the variants, from the record field `programme_name`.** `extract_interventions` gains one field, `programme_name`: the proper name of the programme, scheme or law that the abstract gives for this intervention, or null. Examples on the card are the distinct programme names of the option's records, with document counts, at most 5, or none. No folding call and no clustering call for examples. One refine round of the record prompt. The list lives in the coverage, remade on a rebuild (lead, Q3); folded seeds show under "also found as" only (lead, Q2). Owner: "Yes to the rename." · "3. Sounds good" · "I think your recommendation makes sense, but will that pass have enough context to name the examples correctly? And is it better to address it at the root?" → (the lead: the root, with a migration) → "1. yes" |
| R64 | R42 (counts in "What the evidence base holds so far"); the section "What it is for" | **One evidence table of outcomes.** A row for each plan outcome (with a "serves" mark, from the option design's pick) and a row for each other outcome kind the records report (the folded Measures kinds); columns: documents of any role, evaluated. A plan-outcome row counts from `outcome_tag`; a folded kind that equals a plan outcome is not a separate row (lead, Q4). "What it is for" as a section goes; the "Measures" line is this table. Owner: "Maybe we don't just have to show only the plan outcomes that it is for. If there's other reported outcomes then it would also likely be useful to show" |
| R65 | R43 and Q10 ("a line with no mark shows no word"; "Middle" only in the grid) | **The collapsed row: seven cells with "Middle".** Ambition first, then the six marked lines, each with its word, "Middle" for the middle group; "Who decides" and "Dependencies" have no level and no cell; no blank cell unless the option has no profile. Owner: "Only the marked lines feels like it could give the user a biased view. If an aspect is in the middle group then maybe we should show that" · "5. sounds good" · "5. Fine" |
| R66 | 045 D22 (the transferability line on the card) | **Checks.** The user's considerations first (the user's boundaries and preferences, which are judged; the kind `consideration` does not show: lead, Q12), the verdict as a word with its colour; the three built-in checks fold into one line unless one fails; the transferability line goes. Owner: "6. Yes." |
| R67 | Surface map item 3 (document chips); `OptionDocumentOut` "one per membership row" | **Documents and the source dossier.** No duplicates; evaluated first, then by quality; a linked title and one grey meta line — quality · type · role (the highest role under this option) · place (the top level) · year, `year` added to `OptionDocumentOut` from the snapshot metadata (lead, Q13) — instead of chips; five shown, then "Show all N"; with 0 documents the one line "No documents found yet." A click opens the source dossier sidebar of Evidence search (document level), reused, not the citation provenance panel. In this amendment only the document list opens it (lead, Q16); a document with no row in this task shows its title as plain text (lead, Q15). On an options-scoping task the dossier's slot "Findings from this source" shows the intervention profile records instead, under its own name: from an option card, "In this option" (that option's record: intervention name, setting, tried on, outcomes measured, where, role); from the Sources tab, the document's records, one for each option that holds it; each record in its own words, several records each shown (lead, Q14). Evidence search tasks are unchanged. Owner: "7. Yes." · "When the document is clicked rather than a citation, we have a source dossier sidebar, not the provenance panel … Which I think is more relavant here. In general if there's things in the option card that relate to individual documents then it might be useful to be able to click on the document to see the dosier, or maybe even the profile, since we're extracting that." · "In the evidence search dossier, there is a section for extracted findings anyway, so I suppose the profile is that?" → (the lead's proposal) → "Sounds good" |
| R68 | R40 (ambition in "What it is"); R44 and D16 (the label words) | **The card's layout and the critique's items (the lead's; the owner can change them).** Layout in order: header (title, description, one grey line: lever · origin · relations · also found as; Exclude) → What it is (the lever line of R62; delivered through; design features ≤ 6; Examples ≤ 5) → What it would take, Policy Atlas's estimate (Ambition first, then the eight lines: name, word, sentence; the authority label beside "Who decides", R70; collapsed: the seven cells of R65) → Evidence (the outcomes table; roles; where tried in two levels; tried on; the abstracts note; the document list) → Checks. The label reads "Policy Atlas's estimate". Section titles name, not explain (final words: the lead, at build). No body sentence below 16 px. The origin section goes. Fixed: the sort by title, the duplicate documents, the raw HTML entity in a title. No owner words: the record marks these "accepted by the lead" |
| R69 | R48 (for amendment 3's prompts) | **Every new or changed prompt of amendment 3 goes through a refine loop on the replay tool**, one stop measure each, the other measures reported: the two folding prompts, and the record prompt `extract_interventions` (`programme_name`, one round by the owner's Q1 answer). The folding loops check "same word for the same kind; few kinds; the plan's words where they match". The cluster prompt does not change. Owner (amendment 2, R48): "All the prompts should go through refine loops anyway so that should hopefully get rid of most snags compared to your one off experiments." |
| R70 | Amendment 2 R43 (the authority line in "What it is") | **The authority label beside "Who decides".** The label (within your power · needs action by · unclear) shows beside the "Who decides" row of "What it would take", as a word with its colour, then the sentence; only when the plan holds the consideration. Owner: "11. What is the label?" → (the lead's description) → accepted with the answers above (record) |
| R71 | R45 ("a migration beyond this one revision"); § Stop conditions | **One alembic revision for amendment 3**: one nullable column, `intervention_profile_record.programme_name`, on the head `e9a4c1f7b3d2`; reversible; no other schema change; no new table. The stop condition becomes *a migration beyond this one revision*. Owner: the Q1 answer (allowed by the owner) → "1. yes" |

**Contract parts that change**

| Contract part | Change |
|---|---|
| § Constraints, Schema | One revision: one nullable column `intervention_profile_record.programme_name` (R71). Everything else uses the JSON columns that exist (seams S21–S26) |
| § Constraints, Prompts | New: the Tried on folding prompt, the Measures folding prompt. Changed: `extract_interventions` (`programme_name`; and a round for a "not stated" fault if the check finds one, Q18). Each through a refine loop (R69); re-pinned in `scripts/prompt_hashes.json`. The cluster prompt does not change |
| § Public interface | **Not additive.** Removed or replaced: `WhereTriedOut` and `WhereTriedGroup` (the four groups), `where_tried_group` on a document, `populations`, record-level `settings` and `outcomes` and `tried_on` on the evidence profile, `variants`, `runner_up_lever_type` if nothing else reads it. Added: Tried on kinds with counts, Measures kinds with counts, the outcomes table data, Where tried in two levels, `examples`, `year` and the meta fields on a document, the records in the dossier's slot. OpenAPI by `make openapi-sync` |
| § Measures | **M6 retired** (lead, Q9); its box becomes "Tried on shows kinds beyond the plan's target unit where the evidence has them". New reported figures: kinds per folding facet per list; the "not stated" check; records with a `programme_name` |
| § Stop conditions | As R71 |
| § Known limits | § 7.3 |
| § Risk tier, rollback | `alembic downgrade -1` drops `programme_name`; deploy the previous image. The read-model change is not additive; nothing of this feature is staged (R52) |
| § Spec changes | New items, wording to the owner: tried on as target unit, the folding calls, where tried in two levels, the outcomes table, Examples from `programme_name`, the card layout, the authority label beside "Who decides", the dossier's slot on a scoping task |
| § Risk tier | Tier 4 stays |

## 4. What is cut or changed from amendments 1–2

| Earlier item | State now | Source |
|---|---|---|
| Q10 of amendment 2 / R43: "a line with no mark shows no word"; "Middle" only a grid column head; eight cells | Replaced: seven cells with "Middle" (R65) | Topic 6, decision 5; owner, Q5 |
| R42: counts over "evaluating documents only" (the lead's amendment 2 decision) | Replaced: any role; evaluated separate (R56) | Topic 2 |
| R42: counts shown in "What the evidence base holds so far" as sentences | Replaced: the outcomes table (R64) | Topic 6, decision 4 |
| The four where groups; the OECD rule (`COMPARABLE_LABEL`, `OECD_CODES`, `where_group`) | Removed; four new top-level values (R59) | Topic 4; lead, Q6 |
| "Tried in *Where*" box and the per-document where group chip | Removed (R59, R61) | Topics 4, 6 |
| Variants (R2, AM20; `VARIANTS_MAX` 8, folded seeds first) | Replaced by Examples ≤ 5 from `programme_name` (R63) | Topic 6, decision 3; owner, Q1 |
| `examples` "written by the clustering call" (topic 6, decision 3); the lead's Q1 row (a folding-style call) | Replaced: the record field `programme_name` (R63) | Owner, Q1 |
| R45's single revision for task 046 | One more revision for amendment 3 (R71) | Owner, Q1 |
| "No new extraction" (topic 4) | Stands for where tried; `programme_name` is the one new record field | Owner, Q1 |
| Tried on = the adjacent members' population words (item 23; `TRIED_ON_MAX` 8) | Replaced: option-level kinds from a folding call; all kinds on the card (R54, R55) | Topics 1, 2; lead, Q8 |
| The Tried on facet as a count, never a filter (item 23) | A filter, no counts (R57) | Topic 2; lead, Q8 |
| M6 ("adjacent-population evidence shown as *tried on*") | Retired (lead, Q9) | Lead, Q9 |
| The profile-line mechanism for Tried on (topic 1 as first written) | Replaced by the folding call (R55) | Topic 2 |
| "Populations", "Settings" (record-level), "Outcomes measured" lines on the card | Removed (R54, R64) | Topics 1, 6 |
| "What it is for" section | Removed (R64) | Topic 6, decision 4 |
| "Where it came from and what it relates to" section | Removed; on the header's grey line (R68) | Topic 6, lead |
| The four top boxes; "scoping pass" chip | Removed (R61) | Topic 6, decision 1 |
| Runner-up lever line (item 7); "also touches" | Removed (R62) | Owner, Q10 |
| Authority line in "What it is" | Moved beside "Who decides" (R70) | Owner, Q11 |
| Ambition in "What it is" (R40, Q4) | Moved: first row of "What it would take" (R68) | Topic 6, lead |
| Label "Estimate, before assessment" (built, D16) | Replaced: "Policy Atlas's estimate" (R68) | Topic 6, lead |
| Transferability line on the card | Removed (R66) | Topic 6, decision 6 |
| Document chips; sort by title; one row per membership | Replaced (R67) | Topic 6, decision 7 |
| "The dossier gains a section for the option's own record" (decision 7 as first written) | Replaced: the existing findings slot shows the records (R67) | Decision 7 refined |
| "Anything on the card that relates to one document can open the dossier" | Only the document list, in this amendment (R67) | Lead, Q16 |
| `CELL_LIMIT` 6 | 4 (R60) | Topic 5 |

## 5. Build phases

In `plan.md` § Amendment 3. Phase numbers continue `plan.md` (phases 0–14
are built). Executor marks: prompts and loops = lead; judgement-bearing code =
`deep-reasoner`; mechanical work = `fast-worker`; final reader-facing words and
card polish = lead (with the `impeccable` skill). Every loop: tuning set
(obesity, refugees, caregiving, energy), then one read of the check set (NEET,
heat pumps, cohesion); at most five rounds (R26); one stop measure, the others
reported (R69); report to the owner (R25).

**Before the build** (record, item 6): adversarial passes on this file, the
contract items and the rubric; then on the plan; as for amendment 2.

**Gates.** Full `make verify` at 15.0, at the schema phase (16) and at the
exit (23). Elsewhere `make verify-fast`, plus `make prompt-guard` where a
prompt changes, `make drift-check` and `make openapi-sync` where the API
changes, `make frontend-verify` where the frontend changes.

| Phase | Content | Executor | Gate |
|---|---|---|---|
| 15.0 | Build-open baseline | lead (one command) | full `make verify` |
| 15 | **ADR 0040 amendment 3**: the folding calls in `option_profile` on the mini model; where tried as countries (supersedes ADR 0039 decision 10); `programme_name` and its revision; the rollback. Own commit before 16 | lead | `make verify-fast` |
| 16 | **Schema**: the one revision, `intervention_profile_record.programme_name` (nullable), round-trip test | `deep-reasoner` | **full `make verify`** |
| 16R | **Record prompt round**: `extract_interventions` writes `programme_name` (wire, records writer, prompt round 0 in one commit); then one refine round | lead (prompt, round) · `fast-worker` (wire and writer plumbing) | `make verify-fast` · `prompt-guard` |
| 17 | **Documents** (S25): one entry per document; evaluated first, then quality; role, place, `year`; the HTML entity decoded | `fast-worker` (exact rules) | `make verify-fast` · `drift-check` · `openapi-sync` · `frontend-verify` |
| 18 | **Where tried** (S23): four top-level values, the group words, the level below as written, the document grain; the groups and the OECD rule removed; read model; facet data | `deep-reasoner` (the rule) · `fast-worker` (read model, removal sites) | `make verify-fast` · `drift-check` · `openapi-sync` · `frontend-verify` |
| 18C | **The "not stated" check**: on the live lists, how many "not stated" abstracts name the place (read by hand); a fault → a refine round of `extract_interventions` | lead | round record; `prompt-guard` if a round runs |
| 19 | **Outcome counts and Examples in coverage** (S24, S22): plan outcomes over any role, evaluated separate; examples from `programme_name`, variants removed | `fast-worker` (exact rules) | `make verify-fast` · `drift-check` |
| 20 | **The folding calls** (S21), with 20L round 0 (the two prompts) in the same commit | `deep-reasoner` · lead (prompts) | `make verify-fast` · `prompt-guard` · `drift-check` |
| 20L | **Folding loops**: Tried on, Measures. Stop measure (proposed): on the tuning set, no two kinds on one list name the same kind (read by hand) | lead | `make verify-fast` · `prompt-guard` |
| 21 | **Read models and the dossier's records** (S24, S26); `runner_up_lever_type` off the card's read | `fast-worker` | `make verify-fast` · `drift-check` · `openapi-sync` · `frontend-verify` |
| 22a | **Card, facets, grid, dossier slot: structure** from § 2.5 with exact words; seven cells; authority beside "Who decides"; facets with filters, no counts, fold after 8; `CELL_LIMIT` 4 | `fast-worker` | `make verify-fast` · `frontend-verify` |
| 22b | **Card design and final words**: section titles, the lever line, the grey lines, the table, the collapsed row, 16 px; tints for the owner | lead (`impeccable`) | `make verify-fast` · `frontend-verify` |
| 23 | **Exit**: three live rapid runs (obesity, caregiving, refugees); measures read back from saved files; the browser check; `verification.md`; `docs/deferred.md`; spec-change proposals | lead | **full `make verify`** |

## 6. Checks for the refine loops

| Check | Loop | Source |
|---|---|---|
| The same word for the same kind across the list | 20L (both) | Record, build list item 1 |
| Few kinds | 20L (both) | Record, build list item 1 |
| The plan's words where they match (target unit; outcomes); a word matching a plan outcome is labelled with it | 20L (both) | Record, build list item 1; lead, Q4 |
| The plan's target unit first on the card's Tried on | 20L (Tried on) | Topic 1 |
| No fixed list in the prompt; no anchor example from a named domain | 20L, 16R | R37 (amendment 2), topic 1 "no fixed list" |
| `programme_name` is the proper name of a programme, scheme or law the abstract gives, else null; never a plain phrase | 16R | Owner, Q1 |
| The record's other fields and tags do not regress (M1, M2 on the replays) | 16R | Contract § Acceptance checks |
| "Not stated" geographies: how many abstracts name the place of the study; a fault only where the abstract names it | 18C | Topic 4 |

## 7. Open items and questions

### 7.1 Open for the owner

1. **Tints** of the level words, "Middle" and the authority word: on the built screen (amendment 2 D23 stands open).
2. **Spec wording**: one rewrite after the build ([spec-changes-proposed.md](spec-changes-proposed.md); amendment 2 D22 is also unapplied).
3. **The country at the start of every "who decides" sentence** ("In England, …"; round 2 made every sentence begin so).
4. **The final words** of the section titles and of the lever line (the lead writes them at build; the owner reads them on the built screen).
5. The owner's stage decisions (R25) for loops 16R and 20L, and those still open from amendment 2.
6. **Q19** below.

### 7.2 Questions, answered (2026-09-30)

| Q | Answer | Who |
|---|---|---|
| Q1 | Examples from a new record field `programme_name` written by `extract_interventions`; one nullable column, one alembic revision, one refine round of the record prompt; no folding call, not the clustering call | Owner ("1. yes") |
| Q2 | Folded seeds show under "also found as" only; not examples | Lead |
| Q3 | Examples live in the coverage, as the variants did; remade on a rebuild | Lead |
| Q4 | A plan-outcome row counts from `outcome_tag`; the folding call labels a matching word with the plan outcome; a folded kind equal to a plan outcome is not a separate row | Lead |
| Q5 | Seven cells: Ambition, then the six marked lines; "Who decides" and "Dependencies" have no cell | Owner ("5. Fine") |
| Q6 | Four top-level values (country · "multiple countries" · "other places" · "not stated"); level below = the text as written; group words gain "Europe", "European", "North America", "Nordic", "countries" | Lead |
| Q7 | A document whose records name two countries counts under "multiple countries", both texts below | Lead |
| Q8 | Tried on and Where tried (top level) filter, as Setting; each folds after 8 chips; no Measures facet; the card shows all kinds | Lead |
| Q9 | M6 retired, its box becomes "Tried on shows kinds beyond the plan's target unit where the evidence has them"; constrain keeps its coverage keys, hidden from the reader | Lead |
| Q10 | The other levers = the secondary lever types; the runner-up line goes; "**Lever:** Subsidise, with Regulate and Provide a service." with the reason under it; no "also touches" | Owner ("10. Sounds good. …" → "2. yes") |
| Q11 | The authority label beside the "Who decides" row: word with colour, then the sentence; only with the consideration | Owner ("11. What is the label?" → accepted) |
| Q12 | The user's boundaries and preferences; the kind `consideration` does not show | Lead |
| Q13 | Meta line: quality · type · highest role under the option · place (top level) · year; `year` on `OptionDocumentOut` from the snapshot metadata | Lead |
| Q14 | Each record in its own words; several records each show | Lead |
| Q15 | No row in this task: the title is plain text | Lead |
| Q16 | Only the document list opens the dossier | Lead |
| Q17 | Known limit: unseen words have no kind until the next rebuild | Lead |
| Q18 | A fault → a refine round of `extract_interventions` (not a new extraction) | Lead |

**New question**

| Q | Question | Where |
|---|---|---|
| Q19 | **The record prompt's version and the stored records.** The prompt version is a component of the extraction fingerprint (`interventions_profile.py:101`; `PROMPT_VERSION = "extract_interventions_v2"`, `extract_interventions_prompt.py:44`). A new version makes every document of the next run re-extract (cost and time on every task's next rebuild); keeping v2 with new text breaks the memo's rule that the same fingerprint gives the same output. Records made before the revision have `programme_name` null, so an option built from them shows no examples until re-extracted (R52: no code for old data). Which: bump the version (and re-extract the replay clones for the loops), or not? | § 2.6 |

### 7.3 Known limits (proposed)

- The window from the end of `longlist` to the end of `option_profile` now also leaves Tried on and Measures without kinds (as amendment 2 § 2.10 for the lines).
- Words that no folding call saw (an added option's own search; a merge in constrain) have no kind until the next rebuild, as an added option has no lines (lead, Q17).
- Records extracted before the revision carry no `programme_name`, so their options show no examples until re-extracted (Q19).
- A record carries one plan outcome (`outcome_tag`), so a record on two plan outcomes counts for one (amendment 2 § 2.7, unchanged).
- Where tried recognises only the matcher's names; any other stated place shows under "other places", as written.
- A linked-task document with no row in this task opens no dossier (lead, Q15).
- A real non-UK task is still not run (round 4, verification.md § Known unverified items).
