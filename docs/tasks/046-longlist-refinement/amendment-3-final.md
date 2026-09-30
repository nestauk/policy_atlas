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
> 7 refined: the dossier's findings slot". Precedence: a later decision wins
> over an earlier one; the owner's words win over the lead's. Where a
> decision changed something, this file gives the result and one line
> "Changed from …". Code statements were checked against the code at the head
> of `task/046-longlist-refinement` (`685c7157`).
>
> **Who decided what.** Topics 1–5 and topic 6 decisions 1–7 (with the
> refinement of decision 7) are the owner's, in the words quoted. The row
> "Also from the critique, accepted by the lead" and the layout row of topic 6
> are the lead's; the owner can change them. Where the record does not
> decide, § 7.2 asks a numbered question. The seams S21–S26 (`plan.md` § Amendment 3) are proposals
> for the lead to confirm at the plan gate; none is the owner's.
>
> Terms of `contract.md` § Terms and of [amendment-2-final.md](amendment-2-final.md)
> apply. New terms: **folding call** (one model call that maps a list's
> distinct record words to a few kinds, § 2.2), **kind** (one label a folding
> call gives), **top level** and **level below** (the two levels of Where
> tried, § 2.4), **Examples** (the card list that replaces the variants,
> § 2.6).

## 1. Summary

For the reader of the longlist, amendment 3:

1. Folds the record words of **Tried on** and **Measures** into a few kinds per list, one mini-model call each; the code counts documents per kind per option.
2. Counts the plan's outcomes over documents of **any role**; the evaluated count stays its own figure; one outcomes table on the card.
3. Shows **Where tried** as countries in two levels, from the record's `study_geography`; the OECD rule and the four groups go.
4. Rebuilds the option card: no top boxes; **Examples** (named programmes, at most 5) replace the variants; "Middle" in the collapsed row; checks folded; documents de-duplicated, sorted and opening the **source dossier**, whose findings slot shows the option's records.
5. Sets the grid's cell limit to 4. The authority label does not change.

Already built after amendment 2 and **not** part of this amendment: rounds 2–4 of the profile loop (`evidence/rounds/12L-profile-loop.md`; table in § 2.10).

## 2. The decided design

### 2.1 Tried on at option level (topic 1)

| Item | Decided |
|---|---|
| The fault | The card's "Populations" line and the "Tried on" line and facet show verbatim record text: obesity 55 distinct labels over 80 entries, caregiving 33 over 48 |
| The concept | The plan's **target unit**: who or what should change (people, organisations or things). Not "population" |
| The line | One option-level line **"Tried on"**: the kinds of people, organisations or things the option's evidence covers, the plan's target unit first, then the others, with document counts; the same word for the same kind across the list; few labels; no fixed list |
| The facet | The list's Tried on facet reads it (labels, no counts: § 2.3) |
| Removed from the card | The "Populations" line and the record-level "Settings" line of the evidence section; the record-level "Tried on" line |
| The words | "Tried on" stays |
| Unchanged | The record tags (on target · adjacent · other) and the counts that use them |

- Changed from topic 1: the line is made by a folding call (§ 2.2), not by a profile line. A profile line reads at most 5 records per option (`option_profile.py:106`), so it cannot give counts.
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
- Which record field feeds each call is not stated word for word. The record names "population/tried on" words for Tried on and "Outcomes measured" for Measures; the code holds them as the record's `population` and `outcome` (`coverage.py:146-148`). Seam S21 (`plan.md`) proposes these.

### 2.3 Counts, and no counts on the list (topic 2)

| Item | Decided |
|---|---|
| Counts by plan outcome | Count every document that reports on the plan outcome, **of any role**; the evaluated count stays its own figure |
| The list's facets | Setting, Tried on, and Measures if shown: labels **without counts**, as the Setting facet does. Counts are on the card only |
| How counts show on the card | Decided under topic 6 (§ 2.7, § 2.8) |

- Changed from amendment 2 (R42, the lead's decision "evaluating documents only"): any role. On the three live lists only 11 / 8 / 2 options of about 25 had an evaluating count above zero.
- Code today: `outcome_counts` counts documents with an `evaluated` member (`coverage.py:381-386`); the Tried on facet shows a count per chip (`LonglistView.tsx:503-515`).

### 2.4 Where tried: countries in two levels (topic 4)

| Item | Decided |
|---|---|
| Source | The record's `study_geography`, per intervention record, "exactly as the abstract states it". No new extraction. The setting pass still moves a place named as a setting into it (`coverage.py:203-219`) |
| No fallback | Never the publisher, journal, author institutions or publication country. "Not stated" stays "not stated" |
| No comparability label | Neither the OECD rule nor a model judgement at the longlist. Comparability belongs to transferability at the assessment (task 3) |
| **Top level** | The country; or **"multiple countries"** when the record's text names several countries or a group ("12 OECD countries"); or **"not stated"** |
| **Level below** | The places as listed in the text: the city or region under its country ("Germany: Hamburg"); the countries under "multiple countries" ("Europe and North America"; "Sweden, Denmark, Finland") |
| One country | A record counts under one named country only when its own text names that country alone |
| List facet | The top level, as chips, no counts |
| Card | Both levels, with document counts |
| Removed | The four groups (the user's place · comparable systems (OECD) · other · unknown) and the OECD rule |
| Check for the build | Among records with "not stated", how many abstracts name the place of the study. A fault only where the abstract names it |

- Code today: `WHERE_GROUPS`, `COMPARABLE_LABEL`, `OECD_CODES` (`where_tried.py:33-41`), `where_group` (`:376-400`) and `where_labels` (`:403-418`); coverage counts one group per document (`coverage.py:391-392`) and already keeps the country codes per document (`coverage.py:393-397`). The contract's `WhereTriedOut` (`read_models.py:817-830`), `WhereTriedGroup` (`read_models.py:734`) and each document's `where_tried_group` (`read_models.py:1201`, `repository.py:3906`) carry the groups. The facet filters by group (`LonglistView.tsx:148-151`, `:471-484`).
- The matcher stays for the place strip (`strip_place`, `where_tried.py:465-510`) and the setting pass (`names_place`, `:518-534`).
- Changed from task 045 D20 (ADR 0039 decision 10): no grouping against the plan's Where.

### 2.5 The option card layout (topic 6)

In order (the lead's layout row, accepted into the topic):

| Part | Content and form |
|---|---|
| Header | Title; description; **one grey line**: lever · origin · relations · also found as; Exclude. No boxes, no "scoping pass" chip (decision 1) |
| What it is | Lever with its reason and the other levers (decision 2); Delivered through; design features, at most 6; **Examples**, at most 5 (§ 2.6) |
| What it would take — Policy Atlas's estimate | Table: **Ambition first**, then the eight lines (name, word, sentence). Collapsed: eight cells with words (§ 2.9) |
| Evidence | The outcomes table (§ 2.7); Roles; Where tried in two levels (§ 2.4); Tried on (§ 2.1); the abstracts note; the document list (§ 2.8) |
| Checks | The user's considerations first, the verdict as a word with its colour; the three built-in checks in one line unless one fails; no transferability line (decision 6) |

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

Removed with the boxes: `SnapshotCells` (`OptionCard.tsx:302-309`) and the chip (`:244`).

### 2.6 Examples, from the clustering call (topic 6, decision 3)

| Item | Decided |
|---|---|
| The name | "Variants" becomes **"Examples"** |
| What an example is | A named programme, scheme or law that the records describe |
| How many | At most 5, or none |
| Where it comes from | A new `examples` field written by the clustering call, through the cluster prompt's refine loop |
| Why | The variants today are the records' intervention names, unjudged, so plain phrases land beside programme names |

- Code today: `variants` are the members' distinct intervention names, folded seeds first, at most 8 (`coverage.py:68-70`, `:422-459`), served as `VariantOut` (`read_models.py:1205-1219`) and shown under "Variants" (`OptionCard.tsx:344-353`).
- **Gap (Q1).** The record says the clustering call "reads all member records". In the code no clustering call does: discovery reads a digest of intervention names, never the unit records (`longlist_cluster_prompt.py:15-17`, `:201-204`), and makes the options before any unit joins; assignment reads units in batches and judges one unit at a time (`:256-311`).

### 2.7 One outcomes table (topic 6, decision 4)

| Item | Decided |
|---|---|
| Rows | One row for each **plan outcome**, with a "serves" mark from the option design's pick; one row for each **other outcome kind** the records report (the folded Measures kinds of § 2.2) |
| Columns | Documents of any role · evaluated |
| Replaces | The section "What it is for" and the "Outcomes measured" line |

- Code today: the design's pick is `outcomes_served` (`repository.py:3122`, `_design_out` `:3722-3731`); the counts are `outcome_counts` (`coverage.py:484-490`), printed as sentences (`OptionCard.tsx:416-425`).
- Open: which source counts a plan outcome row (Q4).

### 2.8 The documents and the source dossier (topic 6, decision 7 and its refinement)

| Item | Decided |
|---|---|
| Duplicates | None |
| Order | Evaluated first, then by quality |
| Each document | A linked title and one grey meta line (quality · type · role · place · year) instead of chips |
| How many | Five shown, then "Show all N" |
| No documents | The one line "No documents found yet." |
| On click | The **source dossier sidebar** of Evidence search (document level), reused; not the citation provenance panel |
| Other openers | Anything on the card that relates to one document can open the dossier |
| The dossier's findings slot | On an **options-scoping task**, the slot "Findings from this source" shows the **intervention profile records** instead, under its own name. From an option card: **"In this option"**, the record for that option (intervention name, setting, tried on, outcomes measured, where, role). From the Sources tab: the document's records, one for each option that holds it. Evidence search tasks are unchanged |

- Changed from decision 7: "The dossier gains a section for the option's own record" → no new section; the existing findings slot shows the records (refinement). The record's field list is the refinement's (no "design").
- Code today: one document per membership row, never DOI-collapsed (`repository.py:3741-3749`), sorted by title (`repository.py:3893-3911`); the card de-duplicates by snapshot id only (`OptionCard.tsx:186-194`); chips (`OptionCard.tsx:431-437`). The dossier: `SourceDossier` (`ArtefactView.tsx:1034-1082`, opened by the `source` search parameter, `:1401-1416`), keyed by this task's document row (`repository.py:2371-2395`); the body and the findings slot (`SourcesView.tsx:962`, `:1055-1064`) read `useFindings` (`queries.ts:357-370`), which calls `GET /tasks/{task_id}/findings?source_id=` (`routers/read_models.py:123-135`).

### 2.9 The collapsed row with "Middle" (topic 6, decision 5)

| Item | Decided |
|---|---|
| Collapsed "What it would take" | Eight cells, each with its word, **"Middle"** for the middle group |
| Blank cells | None, unless the option has no profile |
| Replaces | Amendment 2's Q10 ("no word for no mark on the card") |

- Code today: a cell with no mark shows nothing (`OptionCard.tsx:377-384`).
- Open: the two lines that never carry a mark, and whether ambition has a cell (Q5).

### 2.10 Grid, authority, and what is unchanged (topics 3, 5)

| Item | Decided |
|---|---|
| Grid | `CELL_LIMIT` goes from 6 to **4** (`LonglistGrid.tsx:29`) |
| Authority label | Unchanged: shown only when the plan holds a consideration on who can act |
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
copied from the record. "Reopens" names what each item supersedes.

| # | Reopens | Ruling |
|---|---|---|
| R54 | Terms, **tried on**; surface map item 23 | **Tried on at option level.** One option-level line "Tried on" replaces "Populations" and the record-level "Tried on" and "Settings" lines of the card. The concept is the plan's target unit (people, organisations or things), not "population": the kinds the option's evidence covers, the target unit first, with document counts; the same word for the same kind across the list; few labels; no fixed list. The list's Tried on facet reads it. The record tags and their counts do not change. Owner: "the population/tried on list has similar issues to what the settings used to have before refinement, there's a lot of values and a lot of them overlap" · "is population the right concept to use given that policy atlas should work on a broad range of policy domains" · "1. yes" · "2. yes" · "3. yes" |
| R55 | — | **One folding call per facet.** Tried on and Measures are each made by one call over the list's distinct record words (not the records), on the mini model, in the profile step, with the plan's outcomes and target unit as reference: word → kind, in the field's words, the plan's words where they match, few kinds, no fixed list. The code counts documents per kind per option. This replaces the profile-line mechanism of topic 1. Owner: "Perhaps outcomes also need to have a similar treatment, but check first" · "yes to all" |
| R56 | R42 ("documents that evaluated the option; among them …") | **Counts by plan outcome over documents of any role.** Every document that reports on the plan outcome counts, of any role; the evaluated count stays its own figure. Owner: "yes to all" |
| R57 | — | **No counts on the list's facets.** Setting, Tried on, and Measures if shown, show labels only; counts are on the card. Owner: "We don't need the counts in the list view, as we don't have counts for the settings" · "I think we will refine the documents count in the option card refinement step anyway" |
| R58 | — | **The authority label stays as it is**: shown only when the plan holds a consideration on who can act. Owner: "I'm not sure about the 'within in your power' part. Is this always shown. Most users will be in parliament or civil service, so won't most things be in their organisational power. I acknowledge that for things like local authorities then this would be more relevant" → "Yes leave as is" |
| R59 | Task 045 D20 (ADR 0039 decision 10); surface map item 26 (the groups) | **Where tried as countries, in two levels.** From the record's `study_geography` as the abstract states it; no fallback to publisher, journal, authors or publication country; no comparability label at the longlist (transferability, task 3). Top level: the country, "multiple countries" (several countries or a group), or "not stated"; level below: the places as listed in the text. A record counts under one named country only when its own text names that country alone. The facet shows the top level as chips, no counts; the card shows both levels with document counts. The four groups and the OECD rule are removed. The build checks, among "not stated" records, how many abstracts name the place. Owner: "The where tried only lists the users location, then Comparable systems other and unknown. Is this granularity even useful?" · "that OECD rule feels weak" · "just because a document is published in one country, it doesn't necessarily mean that's where the option was tried" · "Should we fall back to publication country when the country isn't stated, is that defensible?" (the lead answered no; recorded as accepted) · "How much cost/latency would it add if we judged comparable with LLM calls. Would the quality of that even be sufficient?" · "Maybe then it would be a top level "multiple countries" and then the level below would be the countries as listed underneath, like in your example for Hamburg" |
| R60 | — | **Grid cell limit 4** (`CELL_LIMIT`, was 6). Owner: "I think it should be 3 instead" → "If it's 1 to 4 in most cases, then maybe 4 is the right value for N." |
| R61 | The card's top cells (task 045 card) | **No boxes in the header.** The four boxes and the "scoping pass" chip leave the header. The abstract-only fact becomes one grey note in the evidence section: "Read from titles and abstracts only". Owner: "1. Yes" |
| R62 | — | **The lever line keeps its reason and names the other levers.** Owner: "I think the reason is helpful. And if an option acts using multiple levers then that is useful information" |
| R63 | R2 and AM20 (variants); Terms, **variant** | **Examples replace the variants.** Named programmes, schemes or laws that the records describe, at most 5, or none; a new `examples` field written by the clustering call; through the cluster prompt's refine loop. Owner: "Yes to the rename." · "3. Sounds good" |
| R64 | R42 (counts in "What the evidence base holds so far"); the section "What it is for" | **One evidence table of outcomes.** A row for each plan outcome (with a "serves" mark, from the option design's pick) and a row for each other outcome kind the records report (the folded Measures kinds); columns: documents of any role, evaluated. "What it is for" as a section goes; the "Measures" line is this table. Owner: "Maybe we don't just have to show only the plan outcomes that it is for. If there's other reported outcomes then it would also likely be useful to show" |
| R65 | R43 and Q10 ("a line with no mark shows no word"; "Middle" only in the grid) | **The collapsed row shows "Middle".** Eight cells, each with its word, "Middle" for the middle group; no blank cell unless the option has no profile. Owner: "Only the marked lines feels like it could give the user a biased view. If an aspect is in the middle group then maybe we should show that" · "5. sounds good" |
| R66 | 045 D22 (the transferability line on the card) | **Checks.** The user's considerations first, the verdict as a word with its colour; the three built-in checks fold into one line unless one fails; the transferability line goes. Owner: "6. Yes." |
| R67 | Surface map item 3 (document chips); `OptionDocumentOut` "one per membership row" | **Documents and the source dossier.** No duplicates; evaluated first, then by quality; a linked title and one grey meta line (quality · type · role · place · year) instead of chips; five shown, then "Show all N"; with 0 documents the one line "No documents found yet." A click opens the source dossier sidebar of Evidence search (document level), reused, not the citation provenance panel. Anything on the card that relates to one document can open the dossier. On an options-scoping task the dossier's slot "Findings from this source" shows the intervention profile records instead, under its own name: from an option card, "In this option" (that option's record: intervention name, setting, tried on, outcomes measured, where, role); from the Sources tab, the document's records, one for each option that holds it. Evidence search tasks are unchanged. Owner: "7. Yes." · "When the document is clicked rather than a citation, we have a source dossier sidebar, not the provenance panel … Which I think is more relavant here. In general if there's things in the option card that relate to individual documents then it might be useful to be able to click on the document to see the dosier, or maybe even the profile, since we're extracting that." · "In the evidence search dossier, there is a section for extracted findings anyway, so I suppose the profile is that?" → (the lead's proposal) → "Sounds good" |
| R68 | R40 (ambition in "What it is"); R44 and D16 (the label words) | **The card's layout and the critique's items (the lead's; the owner can change them).** Layout in order: header (title, description, one grey line: lever · origin · relations · also found as; Exclude) → What it is (lever with reason and other levers; delivered through; design features ≤ 6; Examples ≤ 5) → What it would take, Policy Atlas's estimate (Ambition first, then the eight lines: name, word, sentence; collapsed: eight cells with words) → Evidence (the outcomes table; roles; where tried in two levels; tried on; the abstracts note; the document list) → Checks. The label reads "Policy Atlas's estimate". Section titles name, not explain (final words: the lead, at build). No body sentence below 16 px. The origin section goes. Fixed: the sort by title, the duplicate documents, the raw HTML entity in a title. No owner words: the record marks these "accepted by the lead" |
| R69 | R48 (for amendment 3's prompts) | **Every new or changed prompt of amendment 3 goes through a refine loop on the replay tool**, one stop measure each, the other measures reported: the two folding prompts, and the cluster prompt with `examples`. The folding loops check "same word for the same kind; few kinds; the plan's words where they match". Owner (amendment 2, R48): "All the prompts should go through refine loops anyway so that should hopefully get rid of most snags compared to your one off experiments." |

**Contract parts that change**

| Contract part | Change |
|---|---|
| § Constraints, Schema | No revision is planned. The seams S21–S26 use the JSON columns that exist; if the lead's seam needs a column, it is a new revision and goes to the owner first (R45 allowed one revision for amendment 2) |
| § Constraints, Prompts | New: the Tried on folding prompt, the Measures folding prompt. Changed: `longlist_cluster_v2` → v3 with `examples`. Each through a refine loop (R69); re-pinned in `scripts/prompt_hashes.json`. `extract_interventions` does not change (no new extraction, § 2.4) |
| § Public interface | **Not additive.** Removed or replaced: `WhereTriedOut` and `WhereTriedGroup` (the four groups), `where_tried_group` on a document, `populations`, record-level `settings` and `outcomes` and `tried_on` on the evidence profile, `variants`. Added: Tried on kinds with counts, Measures kinds with counts, the outcomes table data, Where tried in two levels, `examples`, the document meta fields, the records in the dossier's slot. OpenAPI by `make openapi-sync` |
| § Measures | M6 needs a new meaning or retirement (Q9). New reported figures: kinds per folding facet per list; the "not stated" check |
| § Known limits | § 7.3 |
| § Risk tier, rollback | No schema change planned: deploy the previous image. The read-model change is not additive; nothing of this feature is staged (R52) |
| § Spec changes | New items, wording to the owner: tried on as target unit, the folding calls, where tried in two levels, the outcomes table, Examples, the card layout, the dossier's slot on a scoping task |
| § Risk tier | Tier 4 stays |

## 4. What is cut or changed from amendments 1–2

| Earlier item | State now | Source |
|---|---|---|
| Q10 of amendment 2 / R43: "a line with no mark shows no word"; "Middle" only a grid column head | Replaced: "Middle" in the collapsed row and the table (R65) | Topic 6, decision 5 |
| R42: counts over "evaluating documents only" (the lead's amendment 2 decision) | Replaced: any role; evaluated separate (R56) | Topic 2 |
| R42: counts shown in "What the evidence base holds so far" as sentences | Replaced: the outcomes table (R64) | Topic 6, decision 4 |
| The four where groups; the OECD rule (`COMPARABLE_LABEL`, `OECD_CODES`, `where_group`) | Removed (R59) | Topic 4 |
| "Tried in *Where*" box and the per-document where group chip | Removed (R59, R61) | Topics 4, 6 |
| Variants (R2, AM20; `VARIANTS_MAX` 8, folded seeds first) | Replaced by Examples ≤ 5 (R63) | Topic 6, decision 3 |
| Tried on = the adjacent members' population words (item 23; `TRIED_ON_MAX` 8) | Replaced: option-level kinds from a folding call (R54, R55) | Topics 1, 2 |
| The profile-line mechanism for Tried on (topic 1 as first written) | Replaced by the folding call (R55) | Topic 2 |
| "Populations", "Settings" (record-level), "Outcomes measured" lines on the card | Removed (R54, R64) | Topics 1, 6 |
| "What it is for" section | Removed (R64) | Topic 6, decision 4 |
| "Where it came from and what it relates to" section | Removed; on the header's grey line (R68) | Topic 6, lead |
| The four top boxes; "scoping pass" chip | Removed (R61) | Topic 6, decision 1 |
| Ambition in "What it is" (R40, Q4) | Moved: first row of "What it would take" (R68) | Topic 6, lead |
| Label "Estimate, before assessment" (built, D16) | Replaced: "Policy Atlas's estimate" (R68) | Topic 6, lead |
| Transferability line on the card | Removed (R66) | Topic 6, decision 6 |
| Document chips; sort by title; one row per membership | Replaced (R67) | Topic 6, decision 7 |
| "The dossier gains a section for the option's own record" (decision 7 as first written) | Replaced: the existing findings slot shows the records (R67) | Decision 7 refined |
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

**Gates.** Full `make verify` at 15.0, at any phase that changes the schema
(none is planned) and at the exit (23). Elsewhere `make verify-fast`, plus
`make prompt-guard` where a prompt changes, `make drift-check` and
`make openapi-sync` where the API changes, `make frontend-verify` where the
frontend changes.

| Phase | Content | Executor | Gate |
|---|---|---|---|
| 15.0 | Build-open baseline | lead (one command) | full `make verify` |
| 15 | **ADR 0040 amendment 3**: the folding calls in `option_profile` on the mini model; where tried as countries (supersedes ADR 0039 decision 10); Examples from the clustering call. Own commit before 18 | lead | `make verify-fast` |
| 16 | **Documents** (S25): one entry per document (DOI key as coverage's `document_key`); evaluated first, then quality; the meta fields; the HTML entity decoded | `fast-worker` (exact rules) | `make verify-fast` · `drift-check` · `openapi-sync` · `frontend-verify` |
| 17 | **Where tried** (S23): the two levels in coverage from `study_geography`; the groups and the OECD rule removed; read model; the facet's data | `deep-reasoner` (the counting rule) · `fast-worker` (read model, removal sites) | `make verify-fast` · `drift-check` · `openapi-sync` · `frontend-verify` |
| 17C | **The "not stated" check**: on the live lists' records with "not stated", how many abstracts name the place (read by hand). Reported | lead | — (round record) |
| 18 | **Outcome counts** (S24): plan outcomes over any role; evaluated separate | `fast-worker` (exact rule) | `make verify-fast` · `drift-check` |
| 19 | **The folding calls** (S21), with 19L round 0 (the two prompts) in the same commit; the backend methods, stubs, Langfuse names; the stored map; the per-option counts | `deep-reasoner` · lead (prompts) | `make verify-fast` · `prompt-guard` · `drift-check` |
| 19L | **Folding loops**: Tried on, Measures. Stop measure (proposed): on the tuning set, no two kinds on one list name the same kind (read by hand). Reported: kinds per list; words that match the plan's; the target unit first | lead | `make verify-fast` · `prompt-guard` |
| 20 | **Examples** (S22), **waits on Q1 and Q3**: the field, its storage, served; variants removed; 20L round 0 in the same commit | `deep-reasoner` · lead (prompt) | `make verify-fast` · `prompt-guard` · `drift-check` · `openapi-sync` |
| 20L | **Cluster loop** (`examples`). Stop measure (proposed): every example on the tuning set is a named programme, scheme or law that a member record describes (read by hand). Reported: M1, M2, options with no example | lead | `make verify-fast` · `prompt-guard` |
| 21 | **Read models and the dossier's records** (S24, S26): the fields of § 3; the removed fields; OpenAPI | `fast-worker` | `make verify-fast` · `drift-check` · `openapi-sync` · `frontend-verify` |
| 22a | **Card, facets, grid, dossier slot: structure** from § 2.5 with exact words; `CELL_LIMIT` 4; facets without counts | `fast-worker` | `make verify-fast` · `frontend-verify` |
| 22b | **Card design and final words**: section titles, the grey lines, the table, the collapsed row, 16 px; tints for the owner | lead (`impeccable`) | `make verify-fast` · `frontend-verify` |
| 23 | **Exit**: three live rapid runs (obesity, caregiving, refugees); measures read back from saved files; the browser check (card desktop and 390 px, dossier from the card and from Sources, facets, grid); `verification.md`; `docs/deferred.md`; spec-change proposals | lead | **full `make verify`** |

## 6. Checks for the refine loops

| Check | Loop | Source |
|---|---|---|
| The same word for the same kind across the list | 19L (both) | Record, build list item 1 |
| Few kinds | 19L (both) | Record, build list item 1 |
| The plan's words where they match (target unit; outcomes) | 19L (both) | Record, build list item 1 |
| The plan's target unit first on the card's Tried on | 19L (Tried on) | Topic 1 |
| No fixed list in the prompt; no anchor example from a named domain | 19L, 20L | R37 (amendment 2), topic 1 "no fixed list" |
| An example is a named programme, scheme or law the records describe; at most 5; none is right | 20L | Topic 6, decision 3 |
| The list itself does not regress (M1 13–25 options; M2 no row that is one named trial) | 20L | Contract § Acceptance checks |
| "Not stated" geographies: how many abstracts name the place of the study; a fault only where the abstract names it | 17C | Topic 4 |

## 7. Open items and questions

### 7.1 Open for the owner

1. **Tints** of the level words and of "Middle": on the built screen (amendment 2 D23 stands open).
2. **Spec wording**: one rewrite after the build ([spec-changes-proposed.md](spec-changes-proposed.md); amendment 2 D22 is also unapplied).
3. **The country at the start of every "who decides" sentence** ("In England, …"; round 2 made every sentence begin so).
4. **The final words of the section titles** (the lead writes them at build; the owner reads them on the built screen).
5. The owner's stage decisions (R25) for loops 19L and 20L, and those still open from amendment 2.

### 7.2 Questions (gaps or contradictions in the record; not resolved here)

| Q | Question | Where |
|---|---|---|
| Q1 | **Which call writes `examples`?** The record says the clustering call "reads all member records"; no clustering call does (discovery reads a names digest before any unit joins, `longlist_cluster_prompt.py:15-17`, `:201-204`; assignment judges one unit at a time, `:256-311`). A seed (suggested or the user's) gets no design from discovery. Possible forms: discovery from the digest; a new whole-list call after assignment; a field on the assignment wire | § 2.6 |
| Q2 | Folded seeds are listed first among the variants today (`coverage.py:438-459`). Do they leave with the variants (they already show under "also found as", contract Terms, **fold**)? | § 2.6 |
| Q3 | **Where is `examples` stored** (the option's `design` JSON, coverage, or the profile column), and is it remade on a full rebuild only? | § 2.6 |
| Q4 | **A plan outcome row: from `outcome_tag` (R42's source, `coverage.py:383-386`) or from the Measures kind that matches the plan's words?** They can disagree. Is a Measures kind that matches a plan outcome shown once, on the plan row? | § 2.7 |
| Q5 | **"No blank cell"**: "who decides" and "dependencies" never carry a mark (R36; `option_profile.py:546-562`). What word goes in their cells? Does Ambition, now the table's first row, get a ninth cell collapsed ("collapsed: eight cells with words")? | § 2.9 |
| Q6 | **Where tried, a stated place the matcher does not know**: a country outside `COUNTRY_NAMES` (`where_tried.py:47-133`), a group other than "OECD" ("Europe", "North America"; the only group word is `OECD_MARKERS`, `:321`), a city with no country ("Hamburg"). "Not stated", its own top-level value, or the text as written? Is the level below the record's text as written, or the place names read from it? | § 2.4 |
| Q7 | **Where tried at document grain.** Counts are in documents; a document's records can state different places (today one group per document, `coverage.py:391-392`). Does a document whose records name two countries count under each, or under "multiple countries"? | § 2.4 |
| Q8 | **Facets.** Tried on today is a count and never a filter (`longlistPresentation.ts:282-284`); Where tried filters (`LonglistView.tsx:148-151`). After amendment 3, do Tried on and Where tried (countries) filter? Does a Measures facet show ("Measures if shown")? Does a long country list fold after N chips as the Setting facet does (`SETTING_FACET_LIMIT` 8, `LonglistView.tsx:57`)? How many kinds show on the card (today 8, `coverage.py:69`; the record says "few")? | § 2.1, § 2.3 |
| Q9 | **M6 and constrain's input.** M6 is "adjacent-population evidence shown as *tried on*" (contract § Acceptance checks); the new Tried on no longer marks adjacent evidence. Retire M6 or restate it? Constrain reads coverage `tried_on` and record-level `settings` as screen context (`constrain.py:360-384`): keep those keys for constrain, switch to the kinds, or drop them? | § 2.1 |
| Q10 | **"Names the other levers"**: the secondary lever types (`OptionCard.tsx:339`), or also the runner-up (`:340`)? The layout has no runner-up line | § 2.5 |
| Q11 | **The authority line** is in "What it is" today (`OptionCard.tsx:343`) and absent from the decided layout. Where does it go? | § 2.5 |
| Q12 | **"The user's considerations first"**: the user's boundaries and preferences (judgements and guesses, `OptionCard.tsx:451-463`), or also the plan's kind `consideration`, which is not judged at the longlist (R34)? | § 2.5 |
| Q13 | **The meta line.** `OptionDocumentOut` has no year and carries a where group (`read_models.py:1179-1202`). "Place": the top level or the level below? "Role": which one, when the document's records under the option carry several? After "quality", what order? | § 2.8 |
| Q14 | **The dossier's record.** "Tried on" and "outcomes measured": the record's own words, or its folded kind? One document can hold several records under one option (up to 8 per document, surface map item 15): show each? | § 2.8 |
| Q15 | **Documents that open no dossier.** A linked-task finding's document has no row in this task when the task does not hold it (`task_source_snapshot_id` nullable, `read_models.py:1195`; `repository.py:3884-3890`); the dossier is keyed by this task's row (`repository.py:2371-2395`). What does its title do? | § 2.8 |
| Q16 | **Which card items, besides the document list, open the dossier** ("anything on the card that relates to one document")? | § 2.8 |
| Q17 | **Kinds after the list is built.** An added option's coverage is computed at read time from its own search (`repository.py:3431-3465`) and a merge recomputes coverage in constrain (`constrain.py:985-1000`), both after the folding calls. Words the calls never saw have no kind. Known limit until the next rebuild, as an added option has no lines (amendment 2 § 2.3)? | § 2.2 |
| Q18 | **The "not stated" check finds faults**: what then? No new extraction is allowed (§ 2.4) | § 2.4 |

### 7.3 Known limits (proposed)

- The window from the end of `longlist` to the end of `option_profile` now also leaves Tried on and Measures without kinds (as amendment 2 § 2.10 for the lines).
- Words that no folding call saw (Q17).
- A record carries one plan outcome (`outcome_tag`), so a record on two plan outcomes counts for one (amendment 2 § 2.7, unchanged).
- Where tried reads only what the matcher knows (Q6).
- A real non-UK task is still not run (round 4, verification.md § Known unverified items).
