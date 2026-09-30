# Amendment 3 — refinements after the amendment 2 live runs (2026-09-30)

> **Status:** topics 1 to 5 decided (2026-09-30); topic 6 (the option
> card) in work: an Opus subagent critiques the built card and proposes a
> layout. Nothing here is built. The owner read the live runs of amendment
> 2 (Phase 14) and the rounds of the profile loop that followed, and raised
> six points. Each is decided here in turn, with the owner's words.

## Conclusions so far

### Done before this amendment, after the build (committed, in the loop record `evidence/rounds/12L-profile-loop.md`)

| Round | Change to `option_profile_v1` | Result |
|---|---|---|
| 2 | "Who decides" names the body as its country's government publications do; never an acronym in place of a name, never a legal name the public does not use | No expanded or legal names ("National Health Service Commissioning Board" gone); one body each |
| 3 | The mark rule for the eight lines and ambition: order the options on the line; lower part "less", upper part "more", middle none; about a third each where the data spreads, fewer marks where the options are alike; never forced (the owner's R25 ruling) | Spread near thirds where the data supports it; stability 82–88% same mark on two runs, the same as the old rule; no opposite marks |
| 4 | The body is always one in the place of Where, never in the country of a study | Unchanged behaviour on England; a Where of New South Wales names only Australian bodies (with errors on the state/federal split); a real non-UK task stays a known unverified item |

### The decisions of this amendment

| # | Topic | Decision in one line |
|---|---|---|
| 1 | Tried on | One option-level "Tried on" replaces "Populations" and the record-level "Tried on" and "Settings" lines; the concept is the plan's target unit (people, organisations or things), not "population" |
| 2 | Outcomes | "Outcomes measured" folds into kinds the same way; both facets are made by **one folding call per facet** over the list's distinct record words (mini model), and the code counts documents per kind per option; the counts by plan outcome count documents of any role, with the evaluated count separate; no counts on the list's facets |
| 3 | Authority label | Unchanged: shown only when the plan holds a consideration on who can act |
| 4 | Where tried | Countries replace the four groups and the OECD rule; two levels (country / "multiple countries" / "not stated", then the places as listed); from the record's `study_geography` as the abstract states it; no fallback to the publisher or authors; no comparability label at the longlist (task 3, transferability) |
| 5 | Grid | Cell limit 4 |
| 6 | Option card | Open: ambition moves into "What it would take" as its first line; the four top figures repeat the evidence section; more to come from the critique |

### What the build of this amendment must do (a first list, before the card topic)

1. A folding call for each of the two facets (tried on, measures) in the profile step, the mini model, a prompt each, a refine loop each (lead), with the check "same word for the same kind; few kinds; the plan's words where they match".
2. The counts by plan outcome from documents of any role.
3. "Where tried" in two levels from `study_geography`, in code; the OECD rule and the four groups removed; the facet on the top level.
4. The check on "not stated" geographies against the abstracts (a fault only where the abstract names the place).
5. The card and the facets: the three verbatim lines leave; the new lines come in; the grid cell limit 4; the rest from topic 6.
6. Adversarial passes on this amendment, the contract items and the rubric, then on the plan, as for amendment 2.

Open for the owner after this: the tints (on the built screen); the spec wording (one rewrite after the build); the country at the start of every "who decides" sentence ("In England, …").

## Topic 1 decided: "tried on" at option level

| Item | Decision | The owner's words |
|---|---|---|
| The fault | The card's "Populations" line (every record's population words) and the "Tried on" line and facet (the words of the records tagged adjacent) show verbatim record text: obesity 55 distinct labels over 80 entries, caregiving 33 over 48. The same fault that the record-level setting had before amendment 2. | "the population/tried on list has similar issues to what the settings used to have before refinement, there's a lot of values and a lot of them overlap" |
| The concept | "Population" is the wrong word for a tool that serves every policy field (heat pumps, industrial prices). The plan's concept is the **target unit**: who or what should change. | "is population the right concept to use given that policy atlas should work on a broad range of policy domains" |
| The change | **One option-level line "Tried on"**, made in the profile step by one call over the whole list, as the setting is: the kinds of people, organisations or things that the option's evidence covers, the plan's target unit first, then the others, with document counts; the same word for the same kind across the list; few labels; no fixed list. The list's Tried on facet reads it. | "1. yes" |
| Removed from the card | The "Populations" line and the record-level "Settings" line of the evidence section. | "2. yes" |
| The words | "Tried on" stays. | "3. yes" |
| Unchanged | The record tags (on target · adjacent · other) and the counts that use them. |

## Topic 2 decided: outcomes measured, and the mechanism for both facets

| Item | Decision | The owner's words |
|---|---|---|
| The fault | "Outcomes measured" on the card shows every record's outcome words: 87 / 77 / 57 distinct labels on the three live lists, up to 21 on one option. The amendment 2 counts by plan outcome (R42) count evaluating documents only, and the median option has 0 or 1 of them: only 11 / 8 / 2 options of about 25 have a count above zero. | "Perhaps outcomes also need to have a similar treatment, but check first" |
| The mechanism, for outcomes and for tried on | **One folding call per facet** over the list's distinct record words (not the records), the mini model, with the plan's outcomes and target unit as reference: word → kind, in the field's words, the plan's words where they match, few kinds, no fixed list. The code counts documents per kind per option. This replaces the profile-line mechanism written under topic 1 (a profile line reads at most 5 records per option, so it cannot give counts). | "yes to all" |
| The counts by plan outcome | Count every document that reports on the plan outcome, of any role; the evaluated count stays its own figure. This replaces the lead's amendment 2 decision "evaluating documents only". | "yes to all" |
| The list | The facets (Setting, Tried on, and Measures if shown) show labels without counts, as the Setting facet does. Counts are on the card only. | "We don't need the counts in the list view, as we don't have counts for the settings" |
| The card | How the counts show on the card is decided under the option card topic. | "I think we will refine the documents count in the option card refinement step anyway" |

## Topic 3 decided: the authority label stays as it is

The label and its filter show only when the plan holds a consideration on
who can act, which the Task Agent asks for only when Where is below
national level. On the live runs: obesity and caregiving (England) show no
label; refugees (Greater Manchester) shows 20 within your power and 4 needs
action by. A national user can still state it as a consideration. No
change. Owner: "I'm not sure about the 'within in your power' part. Is this
always shown. Most users will be in parliament or civil service, so won't
most things be in their organisational power. I acknowledge that for things
like local authorities then this would be more relevant" → "Yes leave as is".

## Topic 4 decided: "where tried" as countries, no comparability at the longlist

| Item | Decision | The owner's words |
|---|---|---|
| The fault | The four groups (the user's place · comparable systems (OECD) · other · unknown) hide the fact. On the live runs "unknown" is 58 / 74 / 52 percent and "other" is 0 / 2 / 0 percent. "Comparable" is a fixed OECD-membership rule in code. | "The where tried only lists the users location, then Comparable systems other and unknown. Is this granularity even useful?" · "that OECD rule feels weak" |
| The source | The record's `study_geography`, per intervention record, "exactly as the abstract states it", never the publisher, journal or authors. No new extraction: the field exists, and the setting pass already moves a stripped place name into it. | "just because a document is published in one country, it doesn't necessarily mean that's where the option was tried" |
| No fallback | No fallback to the publication country or the author institutions (OpenAlex gives institution countries for about a third of records, Overton the publisher's country for about half; neither is the place of the study). "Not stated" stays "not stated". | "Should we fall back to publication country when the country isn't stated, is that defensible?" → the lead: no; accepted |
| No comparability label | Neither the OECD rule nor a model judgement at the longlist. A model call would be cheap (one per list, seconds, cents) but its quality from country names alone is not sufficient; the judgement belongs to transferability at the assessment (task 3), with full text and the plan's transferability considerations. | "How much cost/latency would it add if we judged comparable with LLM calls. Would the quality of that even be sufficient?" |
| Two levels | **Top level:** the country, or "multiple countries" when the record's text names several countries or a group ("12 OECD countries"), or "not stated". **Level below:** the places as listed in the text — the city or region under its country ("Germany: Hamburg"), the countries under "multiple countries" ("Europe and North America"; "Sweden, Denmark, Finland"). A record counts under one named country only when its own text names that country alone. | "Maybe then it would be a top level "multiple countries" and then the level below would be the countries as listed underneath, like in your example for Hamburg" |
| The list facet | The top level, as chips, no counts. | (topic 2) |
| The card | Both levels, with document counts; the form is decided under the option card topic. | |
| The check for the build | Among records with "not stated", how many abstracts name the place of the study. A fault only where the abstract names it. | |

## Topic 5 decided: the grid's cell limit

`CELL_LIMIT` in `LonglistGrid.tsx` goes from 6 to **4**. With the round-3
mark rule a column holds about a third of the list, so a cell for one lever
type and one level holds 1 to 4 options in most cases; at 4 the fold shows
only in the larger cells. Owner: "I think it should be 3 instead" → after
the lead's count, "If it's 1 to 4 in most cases, then maybe 4 is the right
value for N."

## Topic 6 decided: the option card

An Opus subagent critiqued the built card on the live app (seven cards
across the three runs, desktop and 390 px) and proposed a layout; the
lead put seven decisions to the owner. Screenshots in the lead's scratchpad
`shots/` (not kept). The critique's findings, in short: documents sorted by
title and shown twice (bugs); a KPI-tile row of four boxes at the top
(against DESIGN.md) that repeats the evidence section and the list row;
"What it is" mixes seven kinds of content in five forms; the variants are
mostly raw record phrases; the evidence section counts the same documents
three ways in sentences; "What it is for" shows the same plan outcomes on
almost every card; the checks section is the same filler on every card; an
option with 0 documents shows three sentences about nothing; the collapsed
"What it would take" row has mostly blank cells; "scoping pass" is jargon;
two sentences are 14 px.

| # | Decision | The owner's words |
|---|---|---|
| 1 | The four boxes and the "scoping pass" chip leave the header. The abstract-only fact becomes one grey note in the evidence section: "Read from titles and abstracts only". | "1. Yes" |
| 2 | The lever line keeps its reason sentence and names the other levers. | "I think the reason is helpful. And if an option acts using multiple levers then that is useful information" |
| 3 | "Variants" becomes **"Examples"**: named programmes, schemes or laws that the records describe, at most 5, or none; written as a new `examples` field by the clustering call (which reads all member records; the variants today are the records' intervention names, unjudged, so plain phrases land beside programme names); through the cluster prompt's refine loop. | "Yes to the rename." · "3. Sounds good" |
| 4 | **One evidence table of outcomes**: a row for each plan outcome (with a "serves" mark, from the option design's pick) and a row for each other outcome kind that the records report (the folded "Measures" kinds of topic 2); columns: documents of any role, evaluated. "What it is for" as a section goes; the "Measures" line is this table. | "Maybe we don't just have to show only the plan outcomes that it is for. If there's other reported outcomes then it would also likely be useful to show" |
| 5 | Collapsed "What it would take": eight cells, each with its word, **"Middle"** for the middle group; no blank cell unless the option has no profile. This replaces amendment 2's Q10 ("no word for no mark on the card"). | "Only the marked lines feels like it could give the user a biased view. If an aspect is in the middle group then maybe we should show that" · "5. sounds good" |
| 6 | Checks: the user's considerations first, the verdict as a word with its colour; the three built-in checks fold into one line unless one fails; the transferability line goes. | "6. Yes." |
| 7 | Documents: no duplicates; sorted evaluated first, then by quality; a linked title and one grey meta line (quality · type · role · place · year) instead of chips; five shown, then "Show all N"; with 0 documents the one line "No documents found yet." A click on a document opens the **source dossier sidebar** of Evidence search (document level), reused, not the citation provenance panel. The dossier gains a section for the option's own record of that document (the intervention profile: name, setting, population, outcome, place, design) when opened from an option card. Anything on the card that relates to one document can open the dossier. | "7. Yes." · "When the document is clicked rather than a citation, we have a source dossier sidebar, not the provenance panel … Which I think is more relavant here. In general if there's things in the option card that relate to individual documents then it might be useful to be able to click on the document to see the dosier, or maybe even the profile, since we're extracting that." |
| Also from the critique, accepted by the lead | Ambition is the first row of "What it would take". The label reads "Policy Atlas's estimate" (the decided words). Section titles name, not explain (final words: lead, at build). No body sentence below 16 px. The origin section goes; origin and relations sit on one grey line under the description. Two code faults fixed: the sort by title, the duplicate documents (the same document with two snapshot ids), and the raw HTML entity in a title. | |
| Layout, in order | Header (title, description, one grey line: lever · origin · relations · also found as; Exclude) → What it is (Lever with reason and other levers; Delivered through; design features ≤ 6; Examples ≤ 5) → What it would take, Policy Atlas's estimate (table: Ambition first, then the eight lines: name, word, sentence; collapsed: eight cells with words) → Evidence (the outcomes table; Roles; Where tried in two levels; Tried on; the abstracts note; the document list) → Checks. | |

### Topic 6, decision 7 refined: the dossier's findings slot

The dossier's section "Findings from this source" shows the Evidence search
findings (intervention-outcome and implementation-context, from full text).
At longlist depth no full text is read, so on a scoping task it shows "No
findings extracted from this source" on every document. Decision: on an
options-scoping task that slot shows the **intervention profile records**
instead, with its own name — opened from an option card, "In this option":
the record for that option (intervention name, setting, tried on, outcomes
measured, where, role); opened from the Sources tab, the document's records,
one for each option that holds it. Evidence search tasks are unchanged. Owner:
"In the evidence search dossier, there is a section for extracted findings
anyway, so I suppose the profile is that?" → the lead's proposal above →
"Sounds good".

## Eighteen build questions from the final document (2026-09-30)

The consolidation found 18 gaps (`amendment-3-final.md` § 7.2). The lead
settled the technical ones; four with a visible effect go to the owner
(marked "owner").

| Q | The lead's decision |
|---|---|
| 1 | **Owner.** No clustering call reads all member records, so `examples` cannot come from it. Instead: a **folding-style call** over the list's distinct record intervention names (the source of today's variants, from all members): the mini model marks which are proper names of a programme, scheme or law and folds spellings; the code lists at most 5 per option, by document count. Same mechanism as the two facets. |
| 2 | Folded seeds show under "also found as" only; they are not examples. |
| 3 | `examples` is stored in the coverage, as the variants are; remade on a rebuild. |
| 4 | A plan-outcome row counts from `outcome_tag` (R56). The folding call gets the plan's outcomes as reference and labels a matching word with the plan outcome; a folded kind that equals a plan outcome is not a separate row. Other rows count from the folded kinds. |
| 5 | **Owner.** "Who decides" and "dependencies" have no level, so they have no cell. The collapsed row has **seven cells**: Ambition first, then the six marked lines. |
| 6 | Top level has four values: a country · "multiple countries" · "other places" (a stated place that the matcher does not know, as written) · "not stated". The level below is the record's text as written. The group words gain "Europe", "European", "North America", "Nordic", "countries". |
| 7 | A document whose records name two countries counts under "multiple countries", with both texts below. |
| 8 | Tried on and Where tried (top level) filter the list, as Setting does; each facet folds after 8 chips. No Measures facet on the list. The card shows all kinds. |
| 9 | M6 is retired; its rubric box becomes "Tried on shows kinds beyond the plan's target unit where the evidence has them". Constrain keeps reading the coverage keys it reads today (`tried_on`, record `settings`); they stay in the coverage, hidden from the reader. |
| 10 | **Owner.** "The other levers" = the secondary lever types. The runner-up line goes. |
| 11 | **Owner.** The authority label shows beside the "Who decides" row of "What it would take": the word with its colour, then the sentence. |
| 12 | "The user's considerations" in the checks = the user's boundaries and preferences, which are judged. The kind `consideration` is not judged at the longlist and does not show there. |
| 13 | The meta line: quality · type · role (the document's highest role under this option: evaluated, then described, then the rest) · place (top level) · year. `OptionDocumentOut` gains `year` from the snapshot metadata. |
| 14 | The dossier shows each record with its own words (it is the record, not the fold); several records per document each show. |
| 15 | A document with no row in this task shows its title as plain text, not a link. |
| 16 | In this amendment only the document list opens the dossier. |
| 17 | A known limit: words that no folding call saw have no kind until the next rebuild, as an added option has no lines. |
| 18 | A fault found by the "not stated" check goes to a refine round of the existing record prompt (`extract_interventions`), which is allowed: it is not a new extraction. |

### The owner's answers on the four questions (2026-09-30)

| Q | Decision | The owner's words |
|---|---|---|
| 1 | **Examples at the root.** The record extraction (`extract_interventions`) gains one field, `programme_name`: the proper name of the programme, scheme or law that the abstract gives for this intervention, or null. Examples on the card = the distinct programme names of the option's records, with document counts, at most 5. No folding call for examples. One nullable column on `intervention_profile_record`, in **one alembic revision** for amendment 3 (allowed by the owner). One refine round of the record prompt. This replaces the lead's answer to Q1 above and the "clustering call" of topic 6. | "I think your recommendation makes sense, but will that pass have enough context to name the examples correctly? And is it better to address it at the root?" → the lead: the root, with a migration → "1. yes" |
| 5 | Seven cells in the collapsed row: Ambition, then the six marked lines. | "5. Fine" |
| 10 | The runner-up line goes. The lever line takes the form "**Lever:** Subsidise, with Regulate and Provide a service." and the reason sentence under it. "also touches" goes. The final words are the lead's at build. | "10. Sounds good. But the wording of the reason needs to be refined. I don't like how it uses 'also touches'" → "2. yes" |
| 11 | The authority label (within your power · needs action by · unclear) shows beside the "Who decides" row of "What it would take", as a word with its colour, then the sentence; only when the plan holds the consideration. | "11. What is the label?" → the lead's description → accepted with the answers above |

### Q19, settled by the lead: the record prompt version

`extract_interventions` moves to v3 for `programme_name`. The version is part
of the extraction fingerprint, so the next run of a task re-extracts its
documents, which is the correct behaviour for a new field. Older records
have no `programme_name` and their options show no examples until the task
runs again; no code handles them (the owner's rule on unstaged data).

## After the adversarial review (2026-09-30): the owner's decisions and the lead's rules

Two Opus passes (fidelity; the builder's dry run) gave 34 findings on the
amendment, the contract section and the rubric section. All owner quotes were
found word for word. The lead's rule for each finding is in the lead's
scratchpad file `a3-review-findings.md` and is applied to the documents by the
consolidation pass. The decisions that were the owner's:

| Item | Decision | The owner's words |
|---|---|---|
| The dossier | Only the document list opens the dossier in this amendment. | "1. Okay if only the document list opens the dossier for now." |
| Where tried, a fourth value | "Other" is allowed as a top-level value, for a stated place with no country. | "I guess we could have 'other'." |
| The country of a stated place, at the root | The record gains **`study_country`**: the country of the stated place ("Hamburg" → Germany), from the abstract and the model's knowledge; "multiple" for a group; empty when nothing is stated. The where-tried matcher and its fixed lists of country and place names go. (The place strip on the plan's target unit and the design names keeps its list for now: a later slice, on the deferred list.) | "But the hamburg one isn't a good example because that should be under Germany, no?" · "Why do we even need a fixed list?" |
| "Middle" | Stays, also when a line has few or no marks. | "2. yea keep" |
| The unit concept in the record | The intervention profile record's `population` becomes **`unit`** ("who or what the intervention was delivered to: people, organisations, sites or things") and `population_tag` becomes **`unit_tag`**, in the same migration and prompt round. The record is shared with Evidence search, so it is one definition for both. The two finding records (intervention-outcome, implementation-context) keep `population` for now: a rename slice of their own, on the deferred list with the owner's words. | "Why is there still a population field, I thought we didn't want to use the population concept in favour of unit?" · "Will this also be an update to the evidence search fields. I don't really want there to be one definition in options scoping and another in evidence search. The unit concept is better and should be used throughout" |
| The one migration of amendment 3 | `programme_name`, `study_country`, and the rename `population` → `unit`, `population_tag` → `unit_tag`, in one alembic revision. | |

### Two more decisions (2026-09-30): no place list at all, and unit throughout

| Item | Decision | The owner's words |
|---|---|---|
| The place strip | `strip_place` and its lists of country and place names go too. It cut the place out of the plan's question, target unit and intended change before the screen criteria, the record tagging context, constrain and the option design read them. Instead, those prompts get the rule in words: the place in the question is the user's place, not a criterion; judge as if the question named no place. A phase with a loop: the screen, tagging and constrain prompts change, and M4 (no exclusion and no screen failure because of place) is measured again on the replays; the list goes only if M4 holds. With it go `names_place` (the record-level setting pass) and `where_codes`. | "I don't understand your explanation of where the other fixed list is used. Please explain. My hunch is that that isn't needed either" |
| Unit in the finding records | The intervention-outcome and implementation-context finding records and their prompts also take `unit` in this amendment (columns in the same migration; the wire; the prompt field descriptions with the wider definition; the findings view label). A like-for-like word change: re-pinned hashes and a read of the diff, no replay (the owner's 038 ruling on word swaps). | "We should reword the prompts too, it's just a minor change and the rename should be aligned, it doesn't make sense to call it two different things" |

### Questions 20 to 25 of the final document (2026-09-30)

| Q | Decision |
|---|---|
| 20 | Lead: a word that a folding call leaves out keeps its own text as its kind; no failure. |
| 22 | Lead: `study_country` holds every country the record names, separated ("United Kingdom; United States"); the code derives "multiple countries" when there are two or more; the filter on a country matches such documents too. |
| 23 | Lead: the prompt fixes the form — the country's short English name ("United Kingdom", not "UK"); England, Scotland, Wales and Northern Ireland are places under the United Kingdom, in the level below; the code folds case only. |
| 24 | **Owner.** The finding records' rename stays in this amendment although it reaches production data (Evidence search is live): a plain column rename, reversible, no version change on the finding records, so no document is extracted again; hashes re-pinned; `iof_records.py`, `icf_records.py`, `finding_references.py` and `interventions_records.py` join the hash guard. The owner's words: "Keep in this amendment." |
| 25 | Lead: every prompt that read the stripped text gets the rule in words when the strip goes (the screen, the tagging context, constrain, the design, discovery, typing, the lines, the folding calls); the loop measures M4 and the screen's pass rate. |

### The reach of the rename (2026-09-30)

The plan review found that "population" is also the grouping facet key
stored in the plans of Evidence search tasks in production
(`GROUPING_FACETS`, `schema.py:1249`; `task_plan.py:49`; `task_agent.py:54`;
read at `group.py:1291`), a key in the data sent to the models
(`longlist.py:559, 745`; `synthesis_tools.py:2022, 2068`;
`synthesise.py:1543, 1584`; `extract.py:2108, 2133`) and a word in prompts
(`longlist_cluster_prompt.py:269`, `synthesis_prompts_v6.py:148`,
`grounding_judge.py:112`). The lead put two ways to the owner; the owner
chose **all the way** ("1."): the facet key becomes `unit`, with a
reversible data migration in the same revision that rewrites the stored
facet value in production plans; the payload keys and the prompt words
change as a like-for-like word swap under the owner's 038 ruling (hashes
re-pinned, the diff read as words only, no replay); the record files and the
synthesis prompt files that change are in the hash guard. "Population" is
then gone from the product.
