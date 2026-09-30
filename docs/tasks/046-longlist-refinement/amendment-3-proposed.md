# Amendment 3 — refinements after the amendment 2 live runs (2026-09-30)

> **Status:** under discussion, topic by topic. Nothing here is built. The
> owner read the live runs of amendment 2 (Phase 14) and the four rounds of
> the profile loop that followed, and raised six points. Each is decided
> here in turn, with the owner's words.

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
