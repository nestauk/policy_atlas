# Task 046 — amendment 3, final

> **Status:** decided by the owner 2026-09-30, topic by topic; the 18 build
> questions answered; the adversarial review ran the same day (two passes,
> 34 findings) and the owner decided on its results. Nothing in this file is
> built. The contract items of § 3 are in `contract.md` § Amendment 3
> (2026-09-30); the phases of § 5 are in `plan.md` § Amendment 3; the boxes
> are in `rubric.md` § Amendment 3. No file under `docs/specs/` is changed.
>
> **Source.** [amendment-3-proposed.md](amendment-3-proposed.md) is the
> record. Its sections, in order: "Conclusions so far" (a summary written
> before topic 6); "Topic 1 decided" to "Topic 6 decided"; "Topic 6, decision
> 7 refined: the dossier's findings slot"; "Eighteen build questions from the
> final document" (the lead's answers); "The owner's answers on the four
> questions" (Q1, Q5, Q10, Q11); "Q19, settled by the lead: the record prompt
> version"; "After the adversarial review (2026-09-30)" (the owner's
> decisions); "Two more decisions (2026-09-30): no place list at all, and unit
> throughout"; "Questions 20 to 25 of the final document" (Q24 the owner's,
> the others the lead's); "The reach of the rename" (the owner's answer to
> plan-review finding 3). The plan-stage review's 15 findings and the lead's
> rules are in the lead's file `a3-plan-findings.md`; `plan.md` applies them. The lead's rule for each review finding (A1–A15, B1–B19) is in
> the lead's scratchpad file `a3-review-findings.md`; this file applies each
> one and names it. Precedence: a later decision wins over an earlier one;
> the owner's words win over the lead's. Where a decision changed something,
> this file gives the result and one line "Changed from …". Code statements
> were checked against the code at `34bba89f`.
>
> **Who decided what.** Topics 1–5, topic 6 decisions 1–7 (with the
> refinement of decision 7), Q1, Q5, Q10, Q11 and the six decisions after the
> review and the two decisions after them are the owner's, in the words quoted. The row "Also from the
> critique, accepted by the lead", the layout row of topic 6, the other build
> questions, Q19 and the review rules are the lead's; the owner can change
> them. The seams S21–S28 (`plan.md` § Amendment 3) are proposals for the
> lead to confirm at the plan gate.
>
> Terms of `contract.md` § Terms and of [amendment-2-final.md](amendment-2-final.md)
> apply. New terms: **folding call** (one model call that maps a list's
> distinct record words to a few kinds, § 2.2), **kind** (one label a folding
> call gives), **folded map** (word → kind for one facet of one list),
> **top level** and **level below** (the two levels of Where tried, § 2.4),
> **Examples** (§ 2.6), **`programme_name`**, **`study_country`**, **`unit`**,
> **`unit_tag`** (record fields, § 2.11).

## 1. Summary

For the reader of the longlist, amendment 3:

1. Folds the record words of **Tried on** and **Measures** into a few kinds per list, one mini-model call each; the code counts documents per kind per option.
2. Counts the plan's outcomes over documents of **any role**; the evaluated count stays its own figure; one outcomes table on the card.
3. Shows **Where tried** in two levels: the top level from a new record field **`study_country`** (a country · "multiple countries" · "other" · "not stated"), the level below the record's `study_geography` as written. The four groups, the OECD rule and the where-tried matcher go; the place strip and its name lists go too, if M4 holds on the replays (§ 2.12).
| `where_codes` | Goes in Phase 18 whatever M4 shows: it only feeds `home`, which Phase 18 removes (`where_tried.py:372`; `longlist.py:1520`, `:1808`; `repository.py:3502-3503`) (plan review 4) |
4. Rebuilds the option card: no top boxes; **Examples** from a new record field **`programme_name`**; seven cells with "Middle"; the authority label beside "Who decides"; checks folded; documents de-duplicated, sorted and opening the **source dossier**, whose findings slot shows the option's records.
5. Renames `population` to **`unit`** throughout: the intervention profile record (with `population_tag` → **`unit_tag`**) and the two finding records, one definition for options scoping and Evidence search.
6. Sets the grid's cell limit to 4. The authority label's rule does not change.
7. One alembic revision: `programme_name`, `study_country`, and the renames.
8. Puts the place rule in words into the screen criteria, the tagging context, constrain and the option design prompt: "the place in the question is the user's place, not a criterion; judge as if the question named no place".

Already built and **not** part of this amendment: rounds 2–5 of the profile loop (`evidence/rounds/12L-profile-loop.md`; table in § 2.10).

## 2. The decided design

### 2.1 Tried on at option level (topic 1)

| Item | Decided |
|---|---|
| The fault | The card's "Populations" line and the "Tried on" line and facet show verbatim record text: obesity 55 distinct labels over 80 entries, caregiving 33 over 48 |
| The concept | The plan's **target unit**: who or what should change (people, organisations or things). Not "population". The record field is renamed to match (§ 2.11) |
| The line | One option-level line **"Tried on"**: the kinds of people, organisations or things the option's evidence covers, the plan's target unit first, then the others, with document counts; the same word for the same kind across the list; few labels; no fixed list |
| The facet | The list's Tried on facet reads it (labels, no counts; a filter: § 2.3) |
| On the card | All kinds (lead, Q8) |
| Removed from the card | The "Populations" line and the record-level "Settings" line of the evidence section; the record-level "Tried on" line |
| The words | "Tried on" stays |
| Record tags | Kept in coverage, not shown (lead, A15): the tags (on target · adjacent · other) and their counts |

- Changed from topic 1: the line is made by a folding call (§ 2.2), not by a profile line. A profile line reads at most 5 records per option (`option_profile.py:106`), so it cannot give counts.
- Constrain keeps reading the coverage keys it reads today (`tried_on`, record-level `settings`, `constrain.py:360-384`); they stay in the coverage, hidden from the reader. M6 is retired (lead, Q9); its box becomes "Tried on shows kinds beyond the plan's target unit where the evidence has them".
- Code today: `tried_on` holds only the words of `adjacent` members (`coverage.py:416-421`), at most 8 (`coverage.py:69`); `populations` holds every member's words (`coverage.py:404-410`); the card prints both and `settings` (`OptionCard.tsx:442-444`).

### 2.2 The folding calls, and how the code counts (topic 2)

| Rule | Decided |
|---|---|
| How many calls | **One folding call per facet**: one for Tried on (the record's `unit`), one for Measures (the record's `outcome`) |
| Input | The list's **distinct record words** (not the records), read from the coverage of the whole list — all members, not the profile calls' 5 records (lead, B5); the plan's outcomes and target unit as reference |
| Output | Word → kind, in the field's words, the plan's words where they match, few kinds, no fixed list |
| Model | The mini model (`LONGLIST_ASSIGNMENT_MODEL`, `longlist_backend.py:117-118`) |
| Where it runs | In the profile step (`option_profile`) |
| Where the maps live | At **list level**, in the profile column (`longlist_result.option_profile`, key `folds`: one map per facet) (lead, B4) |
| Counting | `option_profile` recomputes the two facets per option from the members' records through the maps (a database read, no model) and writes documents per kind into coverage keys `tried_on_kinds` and `measures_kinds` (lead, B5). The coverage builder applies the stored maps whenever it computes coverage: a merge in constrain (`constrain.py:985-1000`, written at `:1109`) and an added option's read-time coverage (`repository.py:3431-3465`) (lead, B4) |
| Failure (lead, B10; A7) | An invalid response after the retry fails the step, as the line calls do (`option_profile.py:755-761`); a word missing from the output keeps its own text as its kind; a kind not built from input words is dropped |
| One kind per record | A record's `outcome` holds one primary outcome, so a record has one Measures kind (lead, B3) |
| Refine loop | A prompt each, a refine loop each (lead), with the check "same word for the same kind; few kinds; the plan's words where they match"; stop measure with a ceiling of 12 kinds per list per facet (lead, A6) |

- Changed from topic 1: this replaces the profile-line mechanism written under topic 1.
- Changed from A7 ("counted under other"): a word that a folding call leaves out keeps its own text as its kind; no failure (lead, Q20, with B10 and B4).
- No folding call for Examples (owner, Q1; § 2.6).
- Code today: coverage is built in `longlist` before the profile step (`longlist.py:1818-1831`) and keeps word → count only (`coverage.py:404-410`); `option_profile` loads at most 5 records per option, without unit or outcome (`option_profile.py:448-504`).

### 2.3 Counts, and no counts on the list (topic 2)

| Item | Decided |
|---|---|
| Counts by plan outcome | Count every document that reports on the plan outcome, **of any role**; the evaluated count stays its own figure |
| The list's facets | Setting, Tried on, Where tried: labels **without counts**, as the Setting facet does. Counts are on the card only |
| Filters (lead, Q8) | Tried on and Where tried (top level) filter the list, as Setting does; each facet folds after 8 chips; the filter on a country also matches the documents under "multiple countries" whose `study_country` holds that country (lead, Q22) |
| Measures facet (lead, Q8) | None on the list |

- Changed from amendment 2 (R42, the lead's decision "evaluating documents only"): any role. On the three live lists only 11 / 8 / 2 options of about 25 had an evaluating count above zero.
- Code today: `outcome_counts` counts documents with an `evaluated` member (`coverage.py:381-386`); the Tried on facet shows a count per chip (`LonglistView.tsx:503-515`).

### 2.4 Where tried: two levels, the country from the record (topic 4; after the review)

| Item | Decided |
|---|---|
| **Top level** | From the record's new field **`study_country`** (§ 2.11): **the country** (one country named); **"multiple countries"**, derived in code when `study_country` holds two or more countries, or "multiple" for a group ("12 OECD countries") (lead, Q22; owner); **"other"**: a stated place with no country (`study_geography` stated, `study_country` empty) (owner); **"not stated"** (nothing stated) |
| **Level below** | The record's `study_geography` as written, under its top level ("Germany: Hamburg" when the abstract says Hamburg: the country comes from `study_country`). England, Scotland, Wales and Northern Ireland are places under the United Kingdom, in the level below (lead, Q23) |
| Spelling | The country's short English name ("United Kingdom", not "UK"), fixed in the record prompt; the code folds case only (lead, Q23) |
| Document grain | A document counts under ONE top level: the country, if every record of it that has a country gives the same one; "multiple countries" if they give two or more between them, or any gives "multiple"; else "other" if any record states a place; else "not stated" (lead, B6, applied to `study_country`; with both texts below) |
| No fallback | Never the publisher, journal, author institutions or publication country. "Not stated" stays "not stated" |
| No comparability label | Neither the OECD rule nor a model judgement at the longlist. Comparability belongs to transferability at the assessment (task 3) |
| List facet | The top level, as chips, no counts; a filter; a country chip also matches "multiple countries" documents whose `study_country` holds it — each "multiple countries" entry of the coverage carries its component countries for this (lead, Q8, Q22; plan review 5); folds after 8 chips |
| Card | Both levels, with document counts |
| Removed | The four groups (the user's place · comparable systems (OECD) · other · unknown), the OECD rule, and the **where-tried matcher with its fixed lists of country and place names** (owner) |
| The place strip | Goes too, with its lists, `names_place` (the record-level setting pass), if M4 holds on the replays (§ 2.12) (owner, "Two more decisions") |
| Check for the build | Among records with "not stated", how many abstracts name the place of the study (a fault only where the abstract names it); the check reads `study_geography` and `study_country`. A fault goes to a round of the record prompt's loop (lead, Q18, A5) |
| Words on the screen | No "comparable" or "OECD" as a group label or heading; the level below shows the record's text as written, which may hold "OECD" (lead, A3) |

- Changed from Q6 and the first form of R59 (four values with "other places"; group words; the matcher reading the text): the owner's decisions after the review. The value is named **"other"**. The top level comes from `study_country`, not from matching names. A8 and B11 (a code → name table, the example "United Kingdom: East Bristol") are superseded: no table; "Hamburg" is under Germany, as the owner said.
- Changed from topic 4's "No new extraction": the owner's decision adds `study_country`.
- Code today: `WHERE_GROUPS`, `COMPARABLE_LABEL`, `OECD_CODES` (`where_tried.py:33-41`), the name tables (`:47-318`), `OECD_MARKERS` (`:321`), `countries_in` (`:337-360`), `where_codes` (`:363-373`), `where_group` (`:376-400`), `where_labels` (`:403-418`); callers `longlist.py:150`, `:1520`, `:1808`, `:1967`; `coverage.py:48-53`, `:391-397`; `repository.py:134`, `:3503`. `WhereTriedOut` (`read_models.py:817-830`), `WhereTriedGroup` (`:734`), each document's `where_tried_group` (`:1201`).
- Changed from the review's decision "the place strip … keeps its list for now": the owner's later decision (§ 2.12).
- Changed from B7 (the filter reads the text): the countries come from `study_country` (lead, Q22).

### 2.5 The option card layout (topic 6)

In order (the lead's layout row, accepted into the topic):

| Part | Content and form |
|---|---|
| Header | Title; description; **one grey line**: lever · origin · relations · also found as; Exclude. No boxes, no "scoping pass" chip (decision 1) |
| What it is | The lever line "**Lever:** Subsidise, with Regulate and Provide a service." (the other levers = the secondary lever types), the reason sentence under it; no runner-up line; no "also touches"; final words the lead's at build (owner, Q10); Delivered through; design features, at most 6; **Examples**, at most 5 (§ 2.6) |
| What it would take — Policy Atlas's estimate | Table: **Ambition first**, then the eight lines (name, word, sentence). The authority label beside the "Who decides" row: the word with its colour, then the sentence; only when the plan holds the consideration (owner, Q11). Collapsed: seven cells (§ 2.9) |
| Evidence | The outcomes table (§ 2.7); Roles; Where tried in two levels (§ 2.4); Tried on (§ 2.1); the abstracts note; the document list (§ 2.8) |
| Checks | The user's considerations first (the user's boundaries and preferences, which are judged; the kind `consideration` does not show: lead, Q12), the verdict as a word with its colour; the three built-in checks in one line unless one fails; no transferability line (decision 6) |

Also decided (lead, from the critique):

| Item | Decided | Code today |
|---|---|---|
| The abstracts note | One grey note in the evidence section: "Read from titles and abstracts only" (decision 1) | `abstractOnlySentence`, `OptionCard.tsx:446` |
| Ambition | First row of "What it would take" | In "What it is", `OptionCard.tsx:341` |
| The label | "Policy Atlas's estimate" (the decided words) | "Estimate, before assessment", `OptionCard.tsx:71` (verification D16) |
| Section titles | Name, not explain; final words: lead, at build | `SECTIONS`, `OptionCard.tsx:55-62` |
| Text size | No body sentence below 16 px. At 16 px: every sentence of the lines, the abstracts note, "also found as", the design features, the lever reason (lead, A10) | `text-meta` at `OptionCard.tsx:268`, `:446` |
| Origin section | Goes; origin and relations sit on the header's grey line | `OptionCard.tsx:479-481` |
| "What it is for" | Goes as a section; its content is the outcomes table (decision 4) | `OptionCard.tsx:356-366` |
| Code faults | Fixed: the documents sorted by title; the duplicate documents (the same document with two snapshot ids); a raw HTML entity in a title | § 2.8 |

Removed: `SnapshotCells` (`OptionCard.tsx:302-309`) and the chip (`:244`); the runner-up line (`:340`) and the authority line in "What it is" (`:343`).

### 2.6 Examples, from the record field `programme_name` (topic 6, decision 3; owner, Q1)

| Item | Decided |
|---|---|
| The name | "Variants" becomes **"Examples"** |
| What an example is | A named programme, scheme or law that the records describe |
| The record field | **`programme_name`**: the proper name of the programme, scheme or law that the abstract gives for this intervention, or null. The name of the programme that is this intervention, not one it sits within (lead, B19) |
| On the card | The distinct programme names of the option's records, with document counts, at most 5, or none |
| No folding call | No folding call for examples, and not the clustering call |
| Where the list lives | In the coverage, remade on a rebuild (lead, Q3) |
| Folded seeds | Not examples. Coverage keeps a key `folded` (the folded seeds' names); "also found as" joins the merged duplicates and the folded seeds; the `variants` key goes (lead, Q2, A2) |
| Why | The variants today are the records' intervention names, unjudged, so plain phrases land beside programme names |

- Changed from topic 6 decision 3 ("written as a new `examples` field by the clustering call") and from the lead's Q1 row: the owner's Q1 answer.
- Code today: `variants` = the members' distinct intervention names, folded seeds first, at most 8 (`coverage.py:68-70`, `:422-459`), served as `VariantOut` (`read_models.py:1205-1219`), shown under "Variants" (`OptionCard.tsx:344-353`); "also found as" = merged duplicates from the option rows (`repository.py:2949-2959`).

### 2.7 One outcomes table (topic 6, decision 4)

| Item | Decided |
|---|---|
| Rows | One row for each **plan outcome**, with a "serves" mark from the option design's pick; one row for each **other outcome kind** the records report (the folded Measures kinds) |
| Columns | Documents of any role · evaluated |
| A plan-outcome row | Counts records whose `outcome_tag` is that outcome (R56), and also records whose `outcome_tag` is `other` or null when the folding call returned that plan outcome as their kind; one document counts once on one row (lead, A4, Q4) |
| A kind row | Counts only records whose `outcome_tag` is `other` or null and whose kind is not a plan outcome (lead, A4) |
| "Equal" | The folding call returned the plan outcome's own text (lead, A4) |
| Replaces | The section "What it is for" and the "Outcomes measured" line |

- Code today: the design's pick is `outcomes_served` (`repository.py:3122`); the counts are `outcome_counts` (`coverage.py:484-490`), printed as sentences (`OptionCard.tsx:416-425`).

### 2.8 The documents and the source dossier (topic 6, decision 7 and its refinement)

| Item | Decided |
|---|---|
| Duplicates | None. Of DOI twins, the task's own row opens the dossier (lead, B17) |
| Order | Evaluated first, then by quality |
| Each document | A linked title and one grey meta line instead of chips: quality · type · role (the document's highest role under this option: evaluated, then described, then the rest) · place (the top level) · year; `OptionDocumentOut` gains `year` from the snapshot metadata (lead, Q13). The "inherited from a linked task" chip goes (lead, B17) |
| No row in this task | The title shows as plain text, not a link (lead, Q15) |
| How many | Five shown, then "Show all N" |
| No documents | The one line "No documents found yet." |
| On click | The **source dossier sidebar** of Evidence search (document level), reused; not the citation provenance panel |
| Other openers | Only the document list opens the dossier in this amendment (owner) |
| The dossier's findings slot | On an **options-scoping task**, the slot "Findings from this source" shows the **intervention profile records** instead, under its own name. From an option card: **"In this option"**, the record for that option (intervention name, setting, tried on, outcomes measured, where, role). From the Sources tab: the document's records, one for each option that holds it. Each record in its own words; several records of one document each show (lead, Q14). A document with no record under the option (a member through a linked finding) shows its findings, as Evidence search does (lead, B8). Evidence search tasks are unchanged |

- Changed from decision 7: no new section; the existing findings slot shows the records (refinement). "Anything on the card … can open the dossier" → only the document list (owner, after the review).
- Code today: one document per membership row, never DOI-collapsed (`repository.py:3741-3749`), sorted by title (`repository.py:3893-3911`); a linked finding resolves through the source task's row (`repository.py:3884-3890`); the card de-duplicates by snapshot id only (`OptionCard.tsx:186-194`); chips (`OptionCard.tsx:431-437`). The dossier: `SourceDossier` (`ArtefactView.tsx:1034-1082`, the `source` search parameter, `:1401-1416`), keyed by this task's row (`repository.py:2371-2395`); the findings slot (`SourcesView.tsx:1055-1064`) reads `useFindings` (`queries.ts:357-370`).

### 2.9 The collapsed row with "Middle" (topic 6, decision 5)

| Item | Decided |
|---|---|
| Collapsed "What it would take" | **Seven cells**: Ambition first, then the six marked lines; each with its word, **"Middle"** for the middle group (owner, Q5) |
| "Middle" | Stays, also when a line has few or no marks (owner, after the review) |
| "Who decides", "Dependencies" | No level, so no cell (owner, Q5) |
| Blank cells | None, unless the option has no profile |
| Replaces | Amendment 2's Q10 ("no word for no mark on the card") |

- Code today: eight cells; a cell with no mark shows nothing (`OptionCard.tsx:374-389`).

### 2.10 Grid, authority, and what is unchanged (topics 3, 5)

| Item | Decided |
|---|---|
| Grid | `CELL_LIMIT` goes from 6 to **4** (`LonglistGrid.tsx:29`) |
| Authority label | Its rule is unchanged: shown only when the plan holds a consideration on who can act. Its place moves beside the "Who decides" row (owner, Q11). The Who can act facet stays |
| Delivered through | Unchanged (option-level setting, R41) |
| The profile step's ten calls, the marks, constrain's exclusions | Unchanged |
| "Add an option", Rebuild, Exclude, merges | Unchanged |

**Built after amendment 2, not part of this amendment** (committed; loop record `12L-profile-loop.md`):

| Round | Change to `option_profile_v1` | Result |
|---|---|---|
| 2 | "Who decides" names the body as its country's government publications do; never an acronym in place of a name, never a legal name the public does not use | One body each; no expanded or legal names |
| 3 | The mark rule: order the options on the line; lower part "less", upper part "more", middle none; about a third each where the data spreads; never forced | Stability 82–88% same mark on two runs; no opposite marks |
| 4 | The body is always one in the place of Where, never in the country of a study | No foreign body on England; a New South Wales Where named only Australian bodies, with state/federal errors (known unverified) |
| 5 | No country in the sentence: "do not name that place in the sentence, the reader knows it" (commit `02964db2`) | 0 of 24 sentences name England or the United Kingdom on obesity |

### 2.11 The record fields (owner, Q1 and after the review)

| Field | Decided |
|---|---|
| `programme_name` (new) | § 2.6 |
| `study_country` (new) | The country of the stated place ("Hamburg" → Germany), from the abstract and the model's knowledge; "multiple" for a group; empty when nothing is stated (owner). It holds every country the record names, separated ("United Kingdom; United States"), each as its short English name; England, Scotland, Wales and Northern Ireland give "United Kingdom" (lead, Q22, Q23) |
| `population` → **`unit`** | "who or what the intervention was delivered to: people, organisations, sites or things", on the intervention profile record. The record is shared with Evidence search: one definition for both |
| The finding records | The intervention-outcome and implementation-context finding records and their prompts also take `unit`: columns (`core/schema.py:959`, `:1019`), the wire (`iof_records.py:152`, `:314`; `icf_records.py:97`, `:193`), the prompt field descriptions with the wider definition (the shared description at `finding_references.py:37`; `iof_prompt.py`, `icf_prompt.py:257`), the read model (`IofFindingOut`, `IcfFindingOut`, `read_models.py:277`, `:294`) and the findings view label (`FindingsView.tsx:172`, `:215`, `:288`). A like-for-like word change: re-pinned hashes and a read of the diff, no replay (the owner's 038 ruling) (owner, "Two more decisions"). **It reaches production data** (Evidence search is live): a plain column rename, reversible, **no version change** on the finding records, so no document is extracted again (owner, Q24: "Keep in this amendment.") |
| `population_tag` → **`unit_tag`** | The same values (on target · adjacent · other) |
| Storage | One alembic revision on `e9a4c1f7b3d2`: the two new nullable columns and the two renames on `intervention_profile_record` (`core/schema.py:1088-1135`), the rename on the two finding tables, and the union view recreated with `unit` |
| The prompt | `extract_interventions` v3 (`PROMPT_VERSION`, `extract_interventions_prompt.py:44`) and a `SCHEMA_VERSION` bump (`interventions_records.py:28`); the new fields join `_NULLABLE_TEXT_FIELDS` (`:220`); all are components of the extraction fingerprint (`interventions_profile.py:99-110`), so the next run of a task re-extracts (Q19, lead; B1). The loop replays with the memo bypassed (`--fresh`), since the memo is per task (`extract.py:368-375`). One loop, up to five rounds; "one round" was the expected size, not a cap; a "not stated" round is a round of the same loop (lead, A5) |
| Prompt guard | The guard takes only files named "*prompt*" (`scripts/prompt_hash_guard.py:39-43`); it gains an explicit extra-files list: `interventions_records.py`, `iof_records.py`, `icf_records.py`, `finding_references.py` (lead, B12; owner, Q24) and `synthesis/grounding_judge.py`, whose words change (owner, "The reach of the rename") |
| The facet key and the words | "Population" is also the grouping facet key stored in the plans of Evidence search tasks in production (`GROUPING_FACETS`, `core/schema.py:1249`; `runtime/task_plan.py:49`; `api/contract/task_agent.py:54`; read at `group.py:1291`), a key in the data sent to the models (`longlist.py:559`, `:745`; `synthesis_tools.py:2022`, `:2068`; `synthesise.py:1543`, `:1584`; `extract.py:2108`, `:2133`) and a word in prompts (`longlist_cluster_prompt.py:269`, `synthesis_prompts_v6.py:148`, `grounding_judge.py:112`). The owner chose **all the way** ("1."): the facet key becomes `unit`, with a reversible data migration in the same revision that rewrites the stored facet value in production plans; the payload keys and the prompt words change as a like-for-like word swap under the 038 ruling (hashes re-pinned, the diff read as words only, no replay); the changed prompt files are in the hash guard. "Population" is then gone from the product |
| Production | The revision runs on production without a re-extraction: the finding tables' rename carries no version change; the intervention record's v3 re-extracts options-scoping tasks only, on their next run (Q19, Q24). The facet-key data migration rewrites stored plans in production. Rollback: `alembic downgrade -1` reverses the renames, writes `"population"` back into the stored plans and drops the two columns, with the previous image |

- Changed from the review's decision (the finding records "keep `population` for now"): the owner's later decision renames them in this amendment.
- The union view `finding_reference_union` (`core/schema.py:1145-1185`) takes the column from all three tables; it is recreated with `unit` (S27). Evidence search readers move with it (for example `group.py:1187`, `synthesis_tools.py:2112`, `:2196`, `extract.py:2095-2133`).

### 2.12 The place in the prompts, not a place list (owner, "Two more decisions")

| Item | Decided |
|---|---|
| What goes | `strip_place` and its lists of country and place names (`where_tried.py:421-510`, the tables `:47-318`), `names_place` (`:513-534`; the setting pass, `coverage.py:203-219`), `where_codes` (`:363-373`; `longlist.py:1520`, `:1808`; `repository.py:3503`) |
| What it did | Cut the place out of the plan's question, target unit and intended change before the screen criteria (`longlist_intent.py:73`, `:139-141`, `:165-166`), the record tagging context, constrain (`constrain.py:259-261`) and the option design (`design.py:163`) read them; `longlist_plan_data` (`longlist_intent.py:125-148`) also fed discovery (`longlist.py:1648`), typing, the eight lines and the folding calls (`option_profile.py:722`) |
| Instead | Every prompt that read the stripped text gets the rule in words: "the place in the question is the user's place, not a criterion; judge as if the question named no place" — the screen (its criteria), the tagging context, constrain, the design, discovery, typing, the lines, the folding calls (lead, Q25) |
| The loop | A phase with a loop: those prompts change, and **M4** (no exclusion and no screen failure because of place) and the screen's pass rate are measured on the replays (lead, Q25). The list goes only if M4 holds. If M4 fails, the list stays, and this file and `verification.md` say so |
| The screen prompt | Unchanged (a "keep" row of the contract's surface map); the rule goes into the criteria text the compose step writes |
| The tagging context | Its text is part of the extraction fingerprint (its `context_hash`, `interventions_profile.py:83-86`), so the next run re-extracts, as for v3 |

## 3. Proposed contract items

In `contract.md` § Amendment 3 (2026-09-30). Quoted words are the owner's,
copied from the record. "Reopens" names what each item supersedes. "(lead,
Qn / An / Bn)" marks the lead's rule; the owner can change it.

| # | Reopens | Ruling |
|---|---|---|
| R54 | Terms, **tried on**; surface map item 23 | **Tried on at option level.** One option-level line "Tried on" replaces "Populations" and the record-level "Tried on" and "Settings" lines of the card. The concept is the plan's target unit (people, organisations or things), not "population": the kinds the option's evidence covers, the target unit first, with document counts; the same word for the same kind across the list; few labels; no fixed list; the card shows all kinds (lead, Q8). The list's Tried on facet reads it. The record tags and their counts are kept in coverage, not shown (lead, A15). Constrain keeps reading the coverage keys it reads today (`tried_on`, record `settings`); they stay in the coverage, hidden from the reader (lead, Q9). Owner: "the population/tried on list has similar issues to what the settings used to have before refinement, there's a lot of values and a lot of them overlap" · "is population the right concept to use given that policy atlas should work on a broad range of policy domains" · "1. yes" · "2. yes" · "3. yes" |
| R55 | — | **One folding call per facet.** Tried on (the record's `unit`) and Measures (the record's `outcome`) are each made by one call over the list's distinct record words (not the records), read from the whole list's coverage (lead, B5), on the mini model, in the profile step, with the plan's outcomes and target unit as reference: word → kind, in the field's words, the plan's words where they match, few kinds, no fixed list. The maps are stored at list level in the profile column (key `folds`); `option_profile` recomputes per option, through the maps, the documents per kind (`tried_on_kinds`, `measures_kinds` in coverage); the coverage builder applies the stored maps whenever it computes coverage (merge, added option) (lead, B4, B5). An invalid response after the retry fails the step; a word missing from the output keeps its own text as its kind; a kind not built from input words is dropped (lead, B10). This replaces the profile-line mechanism of topic 1. No folding call for examples (R63). Owner: "Perhaps outcomes also need to have a similar treatment, but check first" · "yes to all" |
| R56 | R42 ("documents that evaluated the option; among them …") | **Counts by plan outcome over documents of any role.** Every document that reports on the plan outcome counts, of any role; the evaluated count stays its own figure. Owner: "yes to all" |
| R57 | — | **The list's facets: no counts.** Setting, Tried on and Where tried show labels only; counts are on the card. Tried on and Where tried (top level) filter the list, as Setting does; each facet folds after 8 chips; no Measures facet on the list (lead, Q8). Owner: "We don't need the counts in the list view, as we don't have counts for the settings" · "I think we will refine the documents count in the option card refinement step anyway" |
| R58 | — | **The authority label's rule stays as it is**: shown only when the plan holds a consideration on who can act. Its place on the card is R70. Owner: "I'm not sure about the 'within in your power' part. Is this always shown. Most users will be in parliament or civil service, so won't most things be in their organisational power. I acknowledge that for things like local authorities then this would be more relevant" → "Yes leave as is" |
| R59 | Task 045 D20 (ADR 0039 decision 10); surface map item 26 (the groups) | **Where tried in two levels.** Top level from the record's `study_country` (R72): a country · "multiple countries" (two or more countries, derived in code, or a group) · "other" (a stated place with no country) · "not stated"; a country filter also matches "multiple countries" documents that hold it (lead, Q22); level below: the record's `study_geography` as written. A document counts under one top level (lead, B6, applied to `study_country`). No fallback to publisher, journal, authors or publication country; no comparability label at the longlist (transferability, task 3). The facet shows the top level as chips, no counts; the card shows both levels with document counts. The four groups, the OECD rule and the where-tried matcher with its fixed lists go; the place strip goes as R74 says. The build checks, among "not stated" records, how many abstracts name the place, reading `study_geography` and `study_country`; a fault goes to a round of the record prompt's loop (lead, Q18, A5). Owner: "The where tried only lists the users location, then Comparable systems other and unknown. Is this granularity even useful?" · "that OECD rule feels weak" · "just because a document is published in one country, it doesn't necessarily mean that's where the option was tried" · "Should we fall back to publication country when the country isn't stated, is that defensible?" (the lead answered no; recorded as accepted) · "How much cost/latency would it add if we judged comparable with LLM calls. Would the quality of that even be sufficient?" · "Maybe then it would be a top level "multiple countries" and then the level below would be the countries as listed underneath, like in your example for Hamburg" · "I guess we could have 'other'." |
| R60 | — | **Grid cell limit 4** (`CELL_LIMIT`, was 6). Owner: "I think it should be 3 instead" → "If it's 1 to 4 in most cases, then maybe 4 is the right value for N." |
| R61 | The card's top cells (task 045 card) | **No boxes in the header.** The four boxes and the "scoping pass" chip leave the header. The abstract-only fact becomes one grey note in the evidence section: "Read from titles and abstracts only". Owner: "1. Yes" |
| R62 | Item 7 (the runner-up on the card) | **The lever line keeps its reason and names the other levers.** The other levers are the secondary lever types. Form: "**Lever:** Subsidise, with Regulate and Provide a service.", the reason sentence under it; "also touches" goes; the runner-up line goes; final words the lead's at build (owner, Q10). Owner: "I think the reason is helpful. And if an option acts using multiple levers then that is useful information" · "10. Sounds good. But the wording of the reason needs to be refined. I don't like how it uses 'also touches'" → "2. yes" |
| R63 | R2 and AM20 (variants); Terms, **variant**; topic 6 decision 3 ("by the clustering call") | **Examples replace the variants, from the record field `programme_name`.** `extract_interventions` gains one field, `programme_name`: the proper name of the programme, scheme or law that the abstract gives for this intervention, or null; the programme that is this intervention, not one it sits within (lead, B19). Examples on the card are the distinct programme names of the option's records, with document counts, at most 5, or none. No folding call and no clustering call for examples. The record prompt goes through its loop (R69). The list lives in the coverage, remade on a rebuild (lead, Q3); coverage keeps the folded seeds' names under `folded`, and "also found as" joins merged duplicates and folded seeds; the `variants` key goes (lead, Q2, A2). Owner: "Yes to the rename." · "3. Sounds good" · "I think your recommendation makes sense, but will that pass have enough context to name the examples correctly? And is it better to address it at the root?" → (the lead: the root, with a migration) → "1. yes" |
| R64 | R42 (counts in "What the evidence base holds so far"); the section "What it is for" | **One evidence table of outcomes.** A row for each plan outcome (with a "serves" mark, from the option design's pick) and a row for each other outcome kind the records report (the folded Measures kinds); columns: documents of any role, evaluated. A plan-outcome row counts records with that `outcome_tag`, and records tagged `other` or null whose folded kind is that plan outcome's own text; a kind row counts only records tagged `other` or null; one document counts once on one row (lead, Q4, A4). "What it is for" as a section goes; the "Measures" line is this table. Owner: "Maybe we don't just have to show only the plan outcomes that it is for. If there's other reported outcomes then it would also likely be useful to show" |
| R65 | R43 and Q10 ("a line with no mark shows no word"; "Middle" only in the grid) | **The collapsed row: seven cells with "Middle".** Ambition first, then the six marked lines, each with its word, "Middle" for the middle group, also when a line has few or no marks; "Who decides" and "Dependencies" have no level and no cell; no blank cell unless the option has no profile. Owner: "Only the marked lines feels like it could give the user a biased view. If an aspect is in the middle group then maybe we should show that" · "5. sounds good" · "5. Fine" · "2. yea keep" |
| R66 | 045 D22 (the transferability line on the card) | **Checks.** The user's considerations first (the user's boundaries and preferences, which are judged; the kind `consideration` does not show: lead, Q12), the verdict as a word with its colour; the three built-in checks fold into one line unless one fails; the transferability line goes. Owner: "6. Yes." |
| R67 | Surface map item 3 (document chips); `OptionDocumentOut` "one per membership row" | **Documents and the source dossier.** No duplicates (of DOI twins, the task's own row opens the dossier: lead, B17); evaluated first, then by quality; a linked title and one grey meta line — quality · type · role (the highest role under this option) · place (the top level) · year, `year` added to `OptionDocumentOut` from the snapshot metadata (lead, Q13) — instead of chips, the "inherited" chip included (lead, B17); five shown, then "Show all N"; with 0 documents the one line "No documents found yet." A click opens the source dossier sidebar of Evidence search (document level), reused, not the citation provenance panel. Only the document list opens it in this amendment; a document with no row in this task shows its title as plain text (lead, Q15). On an options-scoping task the dossier's slot "Findings from this source" shows the intervention profile records instead, under its own name: from an option card, "In this option" (that option's record: intervention name, setting, tried on, outcomes measured, where, role); from the Sources tab, the document's records, one for each option that holds it; each record in its own words, several records each shown (lead, Q14); a document with no record under the option shows its findings (lead, B8). Evidence search tasks are unchanged. Owner: "7. Yes." · "When the document is clicked rather than a citation, we have a source dossier sidebar, not the provenance panel … Which I think is more relavant here. In general if there's things in the option card that relate to individual documents then it might be useful to be able to click on the document to see the dosier, or maybe even the profile, since we're extracting that." · "In the evidence search dossier, there is a section for extracted findings anyway, so I suppose the profile is that?" → (the lead's proposal) → "Sounds good" · "1. Okay if only the document list opens the dossier for now." |
| R68 | R40 (ambition in "What it is"); R44 and D16 (the label words) | **The card's layout and the critique's items (the lead's; the owner can change them).** Layout in order: header (title, description, one grey line: lever · origin · relations · also found as; Exclude) → What it is (the lever line of R62; delivered through; design features ≤ 6; Examples ≤ 5) → What it would take, Policy Atlas's estimate (Ambition first, then the eight lines: name, word, sentence; the authority label beside "Who decides", R70; collapsed: the seven cells of R65) → Evidence (the outcomes table; roles; where tried in two levels; tried on; the abstracts note; the document list) → Checks. The label reads "Policy Atlas's estimate". Section titles name, not explain (final words: the lead, at build). No body sentence below 16 px: every sentence of the lines, the abstracts note, "also found as", the design features, the lever reason (lead, A10). The origin section goes. Fixed: the sort by title, the duplicate documents, the raw HTML entity in a title. No owner words: the record marks these "accepted by the lead" |
| R69 | R48 (for amendment 3's prompts) | **Every new or changed prompt of amendment 3 goes through a refine loop on the replay tool**, one stop measure each, at most five rounds, the other measures reported: the two folding prompts (stop measure with a ceiling of 12 kinds per list per facet: lead, A6), and the record prompt `extract_interventions` v3 (`programme_name`, `study_country`, `unit` with its wider definition; replayed with the memo bypassed; a "not stated" round is a round of this loop: lead, A5, B1, Q19). The four record files join the prompt hash guard (lead, B12; owner, Q24). The folding loops check "same word for the same kind; few kinds; the plan's words where they match". The cluster prompt does not change for examples; its discovery prompt takes the place rule (R74, Q25). Owner (amendment 2, R48): "All the prompts should go through refine loops anyway so that should hopefully get rid of most snags compared to your one off experiments." |
| R70 | Amendment 2 R43 (the authority line in "What it is") | **The authority label beside "Who decides".** The label (within your power · needs action by · unclear) shows beside the "Who decides" row of "What it would take", as a word with its colour, then the sentence; only when the plan holds the consideration. Owner: "11. What is the label?" → (the lead's description) → accepted with the answers above (record) |
| R71 | R45 ("a migration beyond this one revision"); § Stop conditions | **One alembic revision for amendment 3** on the head `e9a4c1f7b3d2`, on `intervention_profile_record`: the nullable columns `programme_name` and `study_country`, and the renames `population` → `unit` and `population_tag` → `unit_tag` (its check constraint with it); `population` → `unit` on `intervention_outcome_finding` and `implementation_context_finding` (R75); the union view recreated with `unit` (S27); a reversible data migration of the grouping facet key `"population"` → `"unit"` in the stored plan payloads in production (R73; owner, "1."); reversible; no other schema change; no new table. The stop condition becomes *a migration beyond this one revision*. Owner: the Q1 answer (allowed by the owner) → "1. yes"; the record's decision "The one migration of amendment 3" (after the review); the finding columns "in the same migration" ("Two more decisions") |
| R72 | Topic 4 ("No new extraction"); the where-tried matcher | **`study_country` at the root.** The record gains `study_country`: the country of the stated place ("Hamburg" → Germany), from the abstract and the model's knowledge; "multiple" for a group; empty when nothing is stated. It holds every country the record names, separated, each as its short English name; England, Scotland, Wales and Northern Ireland are places under the United Kingdom; the code folds case only (lead, Q22, Q23). The where-tried matcher and its fixed lists of country and place names go (the place strip: R74). Owner: "But the hamburg one isn't a good example because that should be under Germany, no?" · "Why do we even need a fixed list?" |
| R73 | Item 13 (the record's `population` and its tag) | **`unit` replaces `population` in the record, for options scoping and Evidence search.** The intervention profile record's `population` becomes `unit` ("who or what the intervention was delivered to: people, organisations, sites or things") and `population_tag` becomes `unit_tag`, in the same migration and prompt round. The two finding records take `unit` too (R75). The grouping facet key `"population"` becomes `"unit"`, with a reversible data migration of the stored plan payloads in production in the same revision (R71); the payload keys sent to the models and the prompt words change as a like-for-like word swap (the 038 ruling: hashes re-pinned, the diff read as words only, no replay); the changed prompt files join the hash guard. "Population" is then gone from the product. Owner: "Why is there still a population field, I thought we didn't want to use the population concept in favour of unit?" · "Will this also be an update to the evidence search fields. I don't really want there to be one definition in options scoping and another in evidence search. The unit concept is better and should be used throughout" · "1." (all the way, "The reach of the rename") |
| R74 | S6 and PA11 (the place strip); item 10 (constrain's plan data); R31 (the design names no place) | **No place list: the place rule in words.** `strip_place` and its lists of country and place names go, with `names_place` (the record-level setting pass) and `where_codes`. Every prompt that read the stripped text gets the rule in words: the place in the question is the user's place, not a criterion; judge as if the question named no place — the screen criteria, the record tagging context, constrain, the option design, discovery, typing, the eight lines and the folding calls (lead, Q25). A phase with a loop: the prompts change and M4 (no exclusion and no screen failure because of place) and the screen's pass rate are measured on the replays; the list goes only if M4 holds; if M4 fails, the list stays and the final and `verification.md` say so. Owner: "I don't understand your explanation of where the other fixed list is used. Please explain. My hunch is that that isn't needed either" |
| R75 | The review's decision (the finding records "keep `population` for now") | **`unit` in the two finding records.** The intervention-outcome and implementation-context finding records and their prompts take `unit` in this amendment: columns in the same migration (R71); the wire; the prompt field descriptions with the wider definition; the findings view label. A like-for-like word change: re-pinned hashes and a read of the diff, no replay (the owner's 038 ruling on word swaps). It reaches production data: a plain column rename, reversible, no version change on the finding records, so no document is extracted again; `iof_records.py`, `icf_records.py`, `finding_references.py` and `interventions_records.py` join the hash guard's extra-files list (owner, Q24). Owner: "We should reword the prompts too, it's just a minor change and the rename should be aligned, it doesn't make sense to call it two different things" · "Keep in this amendment." |

**Contract parts that change**

| Contract part | Change |
|---|---|
| § Constraints, Schema | One revision (R71): `programme_name`, `study_country`, the two renames on `intervention_profile_record`, `population` → `unit` on the two finding tables, the union view, and a reversible **data migration** of the grouping facet key `"population"` → `"unit"` in the stored plan payloads (owner, "1."). **It runs on production without a re-extraction**: the finding tables' rename is a plain, reversible column rename with no version change (Q24); the downgrade writes the facet key back. Everything else uses the JSON columns that exist (seams S21–S26) |
| § Constraints, Prompts | New: the Tried on folding prompt, the Measures folding prompt. Changed: `extract_interventions` v3 with `SCHEMA_VERSION` bumped (three fields; any "not stated" round); the place rule in words in the screen criteria, the tagging context, `constrain` and `option_design` (R74, a loop); the IOF and ICF field descriptions, `population` → `unit` (R75, a word swap, no replay). Each through a refine loop (R69); re-pinned in `scripts/prompt_hashes.json`; `interventions_records.py`, `iof_records.py`, `icf_records.py`, `finding_references.py` added to the guard (Q24). The cluster prompt does not change for examples; its discovery prompt takes the place rule (R74, Q25) |
| § Public interface | **Not additive.** Removed or replaced: `WhereTriedOut` and `WhereTriedGroup` (the four groups), `where_tried_group` on a document, `where_label` where nothing else reads it, `depth_label` on the card (R61), `transferability` (R66), `populations`, record-level `settings` and `outcomes` and `tried_on` on the evidence profile, `variants`, `runner_up_lever_type` where nothing else reads it; the record's `population` and `population_tag` wherever the API exposes the intervention record; `population` on `IofFindingOut` and `IcfFindingOut` (becomes `unit`, R75). Added: Tried on kinds with counts, Measures kinds with counts, the outcomes table data, Where tried in two levels, `examples`, `year` and `place` on a document, the records in the dossier's slot. OpenAPI by `make openapi-sync` (lead, B13) |
| § Measures | **M4** is measured again on the replays in the place-rule loop and on the live check (R74). **M6 retired** (lead, Q9); its box becomes "Tried on shows kinds beyond the plan's target unit where the evidence has them". New reported figures: kinds per folding facet per list; the "not stated" check; records with a `programme_name`; records by `study_country` value |
| § Stop conditions | As R71 |
| § Known limits | § 7.3 |
| § Risk tier, rollback | `alembic downgrade -1` drops the two columns and reverses the renames (on production too: the finding tables' rename is data-safe both ways); deploy the previous image. The read-model change is not additive; nothing of this feature is staged (R52) |
| § Spec changes | New items, wording to the owner: tried on as target unit, the folding calls, where tried in two levels from `study_country`, the outcomes table, Examples from `programme_name`, `unit` in the record and the findings, the place rule in words, the card layout, the authority label beside "Who decides", the dossier's slot on a scoping task |
| § Risk tier | Tier 4 stays |

## 4. What is cut or changed from amendments 1–2

| Earlier item | State now | Source |
|---|---|---|
| Q10 of amendment 2 / R43: "a line with no mark shows no word"; "Middle" only a grid column head; eight cells | Replaced: seven cells with "Middle" (R65) | Topic 6, decision 5; owner, Q5, after the review |
| R42: counts over "evaluating documents only" | Replaced: any role; evaluated separate (R56) | Topic 2 |
| R42: counts shown as sentences | Replaced: the outcomes table (R64) | Topic 6, decision 4 |
| The four where groups; the OECD rule; the where-tried matcher and its name tables | Removed; the top level from `study_country` (R59, R72) | Topic 4; owner, after the review |
| Q6 (four values with "other places"; group words; the text read by the matcher) | Replaced: "other" and `study_country` (R59, R72) | Owner, after the review |
| A8/B11 (a code → name table; the example "United Kingdom: East Bristol") | Superseded: no table (R72) | Owner, after the review |
| B6 (document grain from the matcher's names) | Applied to `study_country` (R59) | Owner, after the review |
| "Tried in *Where*" box and the per-document where group chip | Removed (R59, R61) | Topics 4, 6 |
| Variants (R2, AM20); folded seeds first | Replaced by Examples ≤ 5 from `programme_name`; folded seeds under "also found as" (R63) | Topic 6, decision 3; owner, Q1; lead, A2 |
| `examples` "written by the clustering call"; the lead's Q1 row | Replaced: `programme_name` (R63) | Owner, Q1 |
| R45's single revision for task 046 | One more revision for amendment 3 (R71) | Owner, Q1; after the review |
| "No new extraction" (topic 4) | Replaced: `study_country` and `programme_name` are new record fields | Owner, Q1; after the review |
| The record's `population`, `population_tag` (item 13) | Renamed `unit`, `unit_tag` (R73) | Owner, after the review |
| The finding records "keep `population` for now" (review decision) | Renamed `unit` in this amendment (R75) | Owner, "Two more decisions" |
| The place strip and its lists (S6, PA11); "keeps its list for now" (review decision) | Replaced by the rule in words, if M4 holds (R74) | Owner, "Two more decisions" |
| The setting pass (`names_place`) and `where_codes` | Removed: `names_place` with the place strip (R74); `where_codes` in Phase 18 whatever M4 shows (plan review 4) | Owner, "Two more decisions" |
| Tried on = the adjacent members' words (item 23; `TRIED_ON_MAX` 8) | Replaced: option-level kinds; all kinds on the card (R54, R55) | Topics 1, 2; lead, Q8 |
| The Tried on facet as a count, never a filter (item 23) | A filter, no counts (R57) | Topic 2; lead, Q8 |
| M6 | Retired (lead, Q9) | Lead, Q9 |
| The profile-line mechanism for Tried on | Replaced by the folding call (R55) | Topic 2 |
| "Populations", "Settings" (record-level), "Outcomes measured" lines | Removed (R54, R64) | Topics 1, 6 |
| "What it is for"; "Where it came from and what it relates to" | Removed (R64, R68) | Topic 6 |
| The four top boxes; "scoping pass" chip | Removed (R61) | Topic 6, decision 1 |
| Runner-up lever line; "also touches" | Removed (R62) | Owner, Q10 |
| Authority line in "What it is" | Moved beside "Who decides" (R70) | Owner, Q11 |
| Ambition in "What it is" (R40, Q4) | First row of "What it would take" (R68) | Topic 6, lead |
| Label "Estimate, before assessment" (D16) | "Policy Atlas's estimate" (R68) | Topic 6, lead |
| Transferability line on the card | Removed (R66) | Topic 6, decision 6 |
| Document chips, the "inherited" chip included; sort by title; one row per membership | Replaced (R67) | Topic 6, decision 7; lead, B17 |
| "The dossier gains a section" | Replaced: the findings slot shows the records (R67) | Decision 7 refined |
| "Anything on the card … can open the dossier" | Only the document list (R67) | Owner, after the review |
| "One refine round of the record prompt" (Q1) | One loop, up to five rounds (R69) | Lead, A5 |
| `CELL_LIMIT` 6 | 4 (R60) | Topic 5 |
| "Who decides" sentences begin "In England, …" (round 2) | No country in the sentence (round 5, built) | Owner, loop 12L round 5 |

## 5. Build phases

In `plan.md` § Amendment 3. Phase numbers continue `plan.md` (phases 0–14
are built). Executor marks: prompts and loops = lead; judgement-bearing code =
`deep-reasoner`; mechanical work = `fast-worker`; final reader-facing words and
card polish = lead (with the `impeccable` skill). Every loop: tuning set
(obesity, refugees, caregiving, energy), then one read of the check set (NEET,
heat pumps, cohesion); at most five rounds (R26); one stop measure, the others
reported (R69); report to the owner (R25).

**Gates** (lead, A14). Full `make verify` at 15.0, at the schema phase (16)
and at the exit (23). Elsewhere `make verify-fast`, plus `make prompt-guard`
where a prompt changes (16R, 16W, 18P, 18C when a round runs, 20, 20L), `make
drift-check` and `make openapi-sync` where the API changes, `make
frontend-verify` where the frontend changes (16, 16W, 17, 18, 21, 22a, 22c, 22b). A phase that removes an API field deletes the frontend readers and fixtures in the same commit.

| Phase | Content | Executor | Gate |
|---|---|---|---|
| 15.0 | Build-open baseline | lead (one command) | full `make verify` |
| 15 | **ADR 0040 amendment 3**: the folding calls and their maps; where tried from `study_country`, the matcher removed (supersedes ADR 0039 decision 10); the three record changes and their revision; the rollback. Own commit before 16 | lead | `make verify-fast` |
| 16 | **Schema** (S27): the one revision — `programme_name`, `study_country`, `population` → `unit` and `population_tag` → `unit_tag` on the intervention record, `population` → `unit` on the two finding tables, the union view, the facet-key data migration — and the column readers and facet-key sites; the evidence scripts; the stored-task reference saved again; round-trip tests | `deep-reasoner` (revision, view, data migration) · `fast-worker` (rename sites, scripts) | **full `make verify`** |
| 16R | **Record prompt loop** (S22): v3 with `programme_name`, `study_country`, `unit` and its wider definition, `unit_tag`; `SCHEMA_VERSION` bump; `CoverageMember` and its loaders; the guard's extra-files list with `interventions_records.py`; replays with the memo bypassed, `longlist` at the last round | lead (prompt, rounds) · `fast-worker` (wire, writer, loaders, guard) | `make verify-fast` · `prompt-guard` |
| 16W | **Word swap** (R73, R75): the IOF and ICF wires and descriptions; the payload keys sent to the models; the prompt words; `IofFindingOut`, `IcfFindingOut`; the findings view label; the guard's list extended; hashes re-pinned, the diff read as words only, no replay | lead | `make verify-fast` · `prompt-guard` · `drift-check` · `openapi-sync` · `frontend-verify` |
| 17 | **Documents** (S25) | `fast-worker` | `make verify-fast` · `drift-check` · `openapi-sync` · `frontend-verify` |
| 18 | **Where tried** (S23): from `study_country`; the matcher, `where_codes` and `home` removed; read model; facet data with each "multiple countries" entry's countries | `deep-reasoner` · `fast-worker` | `make verify-fast` · `drift-check` · `openapi-sync` · `frontend-verify` |
| 18P | **The place rule loop** (S28, R74): 18P.0, a screen reset in the replay tool; the rule in words in every prompt that read the stripped text (the folding prompts in 20); M4 and the screen pass count on the replays of every stage that reads the plan; `strip_place`, its lists and `names_place` deleted only if M4 holds (`where_codes` goes in 18) | lead (prompts, loop) · `fast-worker` (18P.0, the deletion) | `make verify-fast` · `prompt-guard` |
| 18C | **The "not stated" check** on the replay clones after 16R and on Phase 23's live lists, reading `study_geography` and `study_country`; a fault → a 16R round | lead | round record; `prompt-guard` if a round runs |
| 19 | **Outcome counts, Examples, `folded`** in coverage (S22, S24) | `fast-worker` | `make verify-fast` · `drift-check` |
| 20 | **The folding calls** (S21): maps at list level; the coverage builder applies them; 20L round 0 in the same commit | `deep-reasoner` · lead (prompts) | `make verify-fast` · `prompt-guard` · `drift-check` |
| 20L | **Folding loops**. Stop measure: no two kinds on one list name the same kind, and at most 12 kinds per list per facet | lead | `make verify-fast` · `prompt-guard` |
| 21 | **Read models and the dossier's records** (S24, S26); the frontend readers of removed fields; the route marked for `/security-review` | `fast-worker` (fields) · `deep-reasoner` (the route) | `make verify-fast` · `drift-check` · `openapi-sync` · `frontend-verify` |
| 22a | **The card: structure** | `fast-worker` | `make verify-fast` · `frontend-verify` |
| 22c | **Facets, grid, dossier slot: structure** | `fast-worker` | `make verify-fast` · `frontend-verify` |
| 22b | **Card design and final words** | lead (`impeccable`) | `make verify-fast` · `frontend-verify` |
| 23 | **Exit**: three live rapid runs; measures; the browser check; `verification.md`; `docs/deferred.md`; M4 on the live runs; spec-change proposals | lead | **full `make verify`** |

## 6. Checks for the refine loops

| Check | Loop | Source |
|---|---|---|
| The same word for the same kind across the list | 20L (both) | Record, build list item 1 |
| Few kinds (reported); at most 12 kinds per list per facet (stop measure) | 20L (both) | Record; lead, A6 |
| The plan's words where they match; a word that matches a plan outcome returns that outcome's own text | 20L (both) | Record; lead, Q4, A4 |
| The plan's target unit first on the card's Tried on | 20L (Tried on) | Topic 1 |
| No fixed list in the prompt; no new anchor example from a named domain | 20L, 16R | R37 (amendment 2), topic 1 |
| `programme_name` is the proper name the abstract gives for this intervention, not one it sits within, else null; misses reported on the check set | 16R | Owner, Q1; lead, A13, B19 |
| `study_country` is the country of the stated place, every named country separated, each as its short English name ("United Kingdom", never "UK"; England etc. give "United Kingdom"), "multiple" for a group, empty when nothing is stated | 16R | Owner, after the review; lead, Q22, Q23 |
| `unit` covers who or what the intervention was delivered to (people, organisations, sites or things), not people only | 16R | Owner, after the review |
| The record's other fields and tags do not regress (M1, M2 on the replays) | 16R | Contract § Acceptance checks |
| "Not stated": how many abstracts name the place of the study; a fault only where the abstract names it | 18C | Topic 4 |
| M4: no exclusion and no screen failure because of place, on the replays (stop measure of 18P); the screen's pass rate reported | 18P | Owner, "Two more decisions"; lead, Q25 |
| The IOF/ICF diff is words only (`population` → `unit`, the wider definition) | 16W | Owner, "Two more decisions"; 038 ruling |

## 7. Open items and questions

### 7.1 Open for the owner

1. **Tints** of the level words, "Middle" and the authority word: on the built screen (amendment 2 D23 stands open).
2. **Spec wording**: one rewrite after the build ([spec-changes-proposed.md](spec-changes-proposed.md); amendment 2 D22 is also unapplied).
3. **The final words** of the section titles and of the lever line (the lead writes them at build; the owner reads them on the built screen).
4. The owner's stage decisions (R25) for loops 16R and 20L, and those still open from amendment 2.

Closed: the country at the start of every "who decides" sentence — closed by loop 12L round 5 (commit `02964db2`): no country in the sentence.

### 7.2 Questions, answered (2026-09-30)

| Q | Answer | Who |
|---|---|---|
| Q1 | Examples from `programme_name`, written by `extract_interventions`; not a folding call, not the clustering call | Owner ("1. yes") |
| Q2 | Folded seeds are not examples; they show under "also found as" (coverage key `folded`, A2) | Lead |
| Q3 | Examples live in the coverage; remade on a rebuild | Lead |
| Q4 | Plan rows from `outcome_tag`, plus `other`/null records whose kind is the plan outcome's own text; one document once per row (A4) | Lead |
| Q5 | Seven cells: Ambition, then the six marked lines | Owner ("5. Fine") |
| Q6 | Superseded after the review: four values — a country · "multiple countries" · "other" · "not stated" — from `study_country` | Owner ("I guess we could have 'other'."; `study_country`) |
| Q7 | A document under one top level (B6, applied to `study_country`) | Lead |
| Q8 | Tried on and Where tried filter, as Setting; fold after 8 chips; no Measures facet; the card shows all kinds | Lead |
| Q9 | M6 retired; constrain keeps its coverage keys, hidden | Lead |
| Q10 | Secondary lever types; no runner-up line; no "also touches" | Owner ("10. Sounds good. …" → "2. yes") |
| Q11 | The authority label beside "Who decides" | Owner ("11. What is the label?" → accepted) |
| Q12 | The user's boundaries and preferences; the kind `consideration` does not show | Lead |
| Q13 | Meta line with the highest role, the top level and `year` | Lead |
| Q14 | Each record in its own words; several each show | Lead |
| Q15 | No row in this task: plain-text title | Lead |
| Q16 | Only the document list opens the dossier | Owner, after the review ("1. Okay if only the document list opens the dossier for now.") |
| Q17 | Words the maps do not hold keep their own text as kind (B4) | Lead |
| Q18 | A fault → a round of the record prompt's loop | Lead |
| Q19 | `extract_interventions` v3 and a `SCHEMA_VERSION` bump; the next run of a task re-extracts; older records show no examples until then | Lead |
| Q20 | A word a folding call leaves out keeps its own text as its kind; no failure | Lead |
| Q21 | The setting pass goes with the place strip (R74) | Owner ("Two more decisions") |
| Q22 | `study_country` holds every named country, separated; "multiple countries" derived in code; the filter on a country matches those documents too | Lead |
| Q23 | The country's short English name, fixed in the prompt; England, Scotland, Wales, Northern Ireland under the United Kingdom; the code folds case only | Lead |
| Q24 | The finding records' rename stays in this amendment: plain column rename, reversible, no version change, no re-extraction on production; the four record files join the hash guard | Owner ("Keep in this amendment.") |
| Q25 | The rule in words in every prompt that read the stripped text; the loop measures M4 and the screen's pass rate | Lead |

**New question (plan review)**

| Q | Question | Where |
|---|---|---|
| Q26 | **Other stored places of the facet name.** The owner's data migration rewrites the facet value in the stored plans. The facet name is also stored as a key of `grouping_result.groups` (read by `groups_out`, `repository.py:600-615`, which lists keys outside `GROUPING_FACETS` as extra facets) and in `grouping_result.grouping_provenance` ("facet + source", `core/schema.py:1263-1267`). Does the data migration rewrite those too, or do earlier grouping results keep "population" (R52 covers only options-scoping data)? | § 2.11 |

### 7.3 Known limits (proposed)

- The window from the end of `longlist` to the end of `option_profile` leaves Tried on and Measures without kinds (as amendment 2 § 2.10 for the lines).
- Words the folded maps do not hold (an added option's own search; a merge) keep their own text as kind until the next rebuild (lead, Q17, B4).
- Records extracted before the revision have no `programme_name`, `study_country` or wider `unit` until the task runs again (Q19).
- A record carries one plan outcome and one primary outcome, so a record on two outcomes counts for one (amendment 2 § 2.7; lead, B3).
- `study_country` rests on the model's knowledge of where a named place is.
- If M4 fails in 18P, the place strip keeps its list, and the result says so (R74).
- Changing the tagging context text re-extracts every task's records on its next run (R74).
- The extract prompt's existing `EXAMPLE_RESPONSE` (`extract_interventions_prompt.py:71`) predates the "no anchor example" rule; out of scope (lead, B12).
- A linked-task document with no row in this task opens no dossier (lead, Q15).
- A real non-UK task is still not run (round 4, verification.md § Known unverified items).
