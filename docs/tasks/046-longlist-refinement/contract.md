# Task contract: 046-longlist-refinement

One implementation slice. It changes how the options-scoping longlist is
built, so that the list is about twenty options at the grain a reader
decides on. It lands before task 3 (shortlist and assessment).

> **Status:** drafted 2026-09-28 · lead; rulings R1–R23 taken from the
> owner in an interview the same day and folded, the last six after the
> lead's own read of the seven runs (database and Langfuse).
> **Contract approved as folded 2026-09-28 · owner** ("yes, approved").
> **Contract-stage adversarial review ran 2026-09-28:** the Codex lane
> (`codex-rescue`, read-only, job `task-mulgi86t-r1331h`) failed after 7 s
> on the workspace spend cap with no findings; the fallback lane
> (`deep-reasoner`, read-only, same brief) returned 21 findings, verdict
> "material change needed". The lead checked the factual claims of A1–A5,
> A7, A8 and A11 in the code; they hold. The folds are in § Amendments from
> the review. The five amendments that needed the owner (AM1, AM3, AM7,
> AM8, AM9) were ruled 2026-09-28: "Happy with all your recommendations
> for the findings". **Re-approved as amended 2026-09-28 · owner** ("yes,
> approved"). · Plan approved:
> _—_ · ADR: **0040** (to write at step 4).
>
> **Branching:** `task/046-longlist-refinement` from `feat/options-scoping`
> at `1e49a65f`. PR target: `feat/options-scoping`, merge commit, per PR #69.
>
> **Inputs.** [intent.md](intent.md) is an AI-written input, not authority
> (owner, 2026-09-28: "don't treat it as gospel"). Where it and the rulings
> below differ, the rulings win. Its item numbers are kept as the one
> numbering of this slice.
>
> **Prior decisions this slice builds on** (context, not targets): the 045
> contract and ADR 0039, except the rulings this slice reopens (D4, A9, A21
> and the reading of D20). The rebuild-in-place ruling of 2026-09-24 belongs
> to task 3 and is not touched. This slice also reopens 045 D21 (setting in
> the longlist intent) and 045 deliverable 3's "option searches in parallel
> with the broad search" chain shape (R18).

## Goal

The longlist walk produces about twenty options. Each option is one thing a
government can do. Variants of an option and their evidence are on the
option's card and are never rows. Each judgement about an option uses the
baseline's account of the status quo. Evidence from an adjacent population
stays visible as a "tried on" line.

**The shape of the list is the purpose of the slice** (owner: "list shape
is the priority"). Cost must stay manageable, because the shortlist and
assessment steps come after the longlist. A cost change is in this slice
only when it needs no edit inside an Evidence search component, with one
exception (R16, item 18).

**The plan keeps three things apart** (R19): the target unit (who or what
the intervention is for), the setting, and the geography. The screen uses
the target unit and the outcomes only, so that evidence which can transfer
is not rejected before anyone sees it. Setting and geography stay in the
plan as context for judgements and for the transferability assessment of
task 3.

The item numbers are the numbers in [intent.md](intent.md) § In scope. The
rubric, the plan and the ADR use the same numbers. Items 17, 19, 21, 24 and
25 are out of this slice; their numbers are not used again.

## Deliverable

A PR on `task/046-longlist-refinement` into `feat/options-scoping`:

- one alembic revision (three nullable columns, § Constraints);
- six revised prompt surfaces and their re-pinned hashes;
- the code changes in the surface map;
- tests, `verification.md`, ADR 0040;
- the spec changes in § Spec changes, each applied only after the owner
  accepts it;
- the staged check (R12): a replay on the seven stored tasks, then three
  live runs.

## Terms

The 045 contract's § Terms applies. New or changed here:

| Term | Meaning |
|---|---|
| **reader grain** | The grain of an option row: one kind of action a government can take ("upfront grants for heat pumps"). A named trial, a bundle component and a design variant are below reader grain. |
| **variant** | A design of an option that the evidence or a folded suggestion describes (a named programme, a delivery form). Shown on the option card with its document count. Computed from the option's member records. Not an `option` row and not an `option_relation` row. Different from the `variant_of` relation, which task 3 uses for a user's design edit. |
| **fold** | Discovery puts a suggested seed inside a wider option. The seed's design becomes a variant of that option. The mechanism is the existing merge (`option.merged_into_option_id`, name shown as *also found as*). An option the user named is never folded. |
| **corpus digest** | The input to discovery in place of every record: the distinct intervention names in the corpus, each with its record count and its counts by role. Built by code. |
| **residual** | The records that are *unclustered* after assignment. *Not an option* records are not part of the residual. |
| **residual pass** | One more discovery call over the residual only, then one assignment of the residual. It runs at most once. |
| **target size · hard ceiling** | Two product constants for the number of options on a longlist, seeds included (R1). They replace `clamp(ceil(N/4), 8, 40)`. |
| **population tag** | On each profile record: `on_target`, `adjacent` or `other`, against the plan's target unit. |
| **outcome tag** | On each profile record: the text of one of the plan's outcomes, or `other`. |
| **object tag** | On each profile record: `plan_object` (the record's intervention is the thing the plan wants adopted or changed, for example the heat pump), `option` (it is something a government or a provider does) or `neither`. |
| **tagging context** | The part of the plan the profile prompt receives: target unit, outcomes, intended change. It is reference context for the three tags only. It does not change what the profile records from the abstract. |
| **tried on** | The populations an option's adjacent-tagged members studied. A card line and a list facet beside *where tried*. Never a filter and never an exclusion. |
| **setting** | Where the recipient meets the intervention (school, home, workplace, primary care). Null for a system-level instrument. Never a country, a region, an organisation or the intervention itself. |
| **scope** | One search with its own question: a row in `evidence_scope`. One longlist run has one baseline scope, one longlist scope and one targeted scope for each option search. |
| **screen input** | What the screen judges a document against: the scope's intent text plus the screening criteria. Both are composed by the scoping side from the plan. Today a targeted scope's intent is the option's design, so each option search screens "for the option". |
| **plan-level screen** | The one screen of a longlist run after this slice: the longlist scope's screen, with the intent and criteria composed from the target unit (wide) and the outcomes. No setting, no place, no option design (R5, R18, R19). |
| **wide target unit** | The target unit as the screen uses it: the plan's population or an adjacent or wider one passes (R15). The exact target unit is used at constrain. |
| **acquire-only option search** | A child walk of a longlist walk after this slice: it runs `acquire` and ends. Its documents join the task's pool and the plan-level screen judges them (R18). |
| **add walk** | The option search that the chat action or button "add an option" starts. It has no parent walk, so it keeps the full chain. |
| **title-only document** | A document with a title and no abstract. |
| **runner-up lever** | The second lever type the typing pass names for an option. Stored today in `longlist_result.provenance`; shown on the card after this slice. |
| **short id** | A short label (`u1`, `u2` …) that stands for a unit's UUID inside one prompt. Code maps it back. |
| **replay** | A re-run of suggest, the profile, the longlist and constrain over the documents a finished task already holds. No search. It writes a separate result and leaves the task's stored longlist unchanged. |

## Read first

- [intent.md](intent.md) and, where available locally,
  `evidence/pre-contract-runs/notes.md` (gitignored; the figures this
  contract cites are copied from it).
- [OS components](../../specs/capabilities/options-scoping/components.md)
  § 2–5, § 6 longlist, § 7 constrain.
- [OS capability](../../specs/capabilities/options-scoping/capability.md)
  § Depths and modes, § Pipeline and gates, § Output structure (Longlist),
  § Open decisions (open question 4).
- [OS trust](../../specs/capabilities/options-scoping/trust.md) § Screening
  and shortlisting, § Provenance labels.
- [045 contract](../045-scoping-longlist/contract.md) (pattern precedent),
  [ADR 0039](../../adr/0039-options-scoping-longlist-option-searches-and-option-records.md).
- `docs/deferred.md` § Options scoping longlist (task 045 seams) and
  § Synthesis optimisation.

## Surface map

Paths are under `backend/src/policy_atlas/` unless they start with
`frontend/`. Rows marked **keep** must not change behaviour.

| Item | Surface | Today (as built at `1e49a65f`) | After this slice | Where |
|---|---|---|---|---|
| 1 | Suggest | Suggestions at any grain (obesity: "School-family diet and activity programme in deprived primaries"). Designs carry place and institution words (refugees: "Greater Manchester councils …"). | Suggestions are named at reader grain (R14). A design names no place and no institution of one country (R20). | `options_scoping/suggest/suggest_prompt.py` |
| 1 | Discovery input | The question, the seeds and every unit payload. No plan fields, no baseline. | The plan (question, intended change, target unit, outcomes), the baseline sections, the seeds and the corpus digest. The prompt names the target size. Discovery may fold a suggested seed; never a user's option. | `options_scoping/longlist/longlist.py` (`LonglistClusteringBackend.discover`, 727), `longlist_cluster_prompt.py` |
| 1 | Ceiling | `discovery_ceiling()`: `clamp(ceil(N/4), 8, 40)` | Two constants (R1). `discovery_ceiling()` is removed. | `longlist.py:157-188`, `1269` |
| 1 | Residual | Counted only | One residual pass, then counted (R9) | `longlist.py` |
| 1 | Variants | None | Computed per option from member records and folded seeds; stored in `longlist_result.coverage`; served and shown on the card | `options_scoping/longlist/coverage.py`, `api/contract/read_models.py`, `frontend/src/views/longlist/OptionCard.tsx` |
| 2 | Assignment rule | A unit silent on a defining feature may join with the flag; "ungroupable" when no option fits | Same kind of intervention joins, with the flag when the feature is not stated. "Ungroupable" means a different kind. "Not an option" means not an intervention. Stays on the mini model unless measurement shows it must move. | `longlist_cluster_prompt.py:202-241` |
| 2 | Unit ids in prompts | Full UUID strings | Short ids, mapped back by code | `longlist.py:365`, `544` |
| 3 | Flag wording | Chip "feature not stated" | "not stated in the abstract" | `frontend/src/views/longlist/OptionCard.tsx:327`; wire description in `longlist_cluster_prompt.py:122` |
| 4 | Packages | A discovered bundle mints a package; unmatched component labels are counted | Discovery mints no package from bundle components. A bundle is one option; its components are variants on its card. `part_of` stays in the schema for user actions and task 3. | `longlist.py:1345-1359`, `1463-1476` |
| 5 | Distinct screen | Judged inside each batch of 10, against that batch only | One call over the whole list (names, descriptions, design features). The merge rule of 2026-09-24 is unchanged. | `options_scoping/constrain/constrain.py:472-573`, `constrain_prompt.py` |
| 6 | Outcomes served, discovered option | Free text from the discovery wire | The plan outcomes that its members' outcome tags name, by code. Seeds keep the outcomes of their design. | `longlist.py:1054-1071`, `1298` |
| 7 | Lever list | `lever_types_v1`; "provide a service" includes "deliver or fund a service" | `lever_types_v2`: "provide a service" is direct delivery by the state; funding a provider is "subsidise"; buying from a provider is "procure or commission" | `options_scoping/longlist/lever_types.py` |
| 7 | Typing input and wire | Option fields only; four prose fields; batches in sequence | + plan and baseline; ambition judged against the baseline's status quo; the wire drops `lever_reason` and `runner_up_reason` and keeps `ambition_reason` and `none_fits_reason` (both are shown today); batches in parallel | `lever_typing_prompt.py`, `longlist.py:1011-1051` |
| 7 | Constrain batches | In sequence | In parallel | `constrain.py:336-385` |
| 7 | Runner-up lever | In `longlist_result.provenance`; not served | Served on the option and shown on the card when the typing names one | `api/readmodels/repository.py`, `api/contract/read_models.py`, `OptionCard.tsx` |
| 8 | Themes | Built inside `longlist`, before `constrain`; not recomputed | Built after `constrain`, over included options only | `longlist.py:1361-1409`, `constrain.py`, `runtime/scoping_plan.py` (`LONGLIST_CHAIN`) |
| 9 | Baseline as reference | Read by `suggest` only | Also passed to discovery, typing and constrain | `options_scoping/suggest/suggest.py:220` (`baseline_sections`, reused) |
| 10 | Constrain plan data | `question`, `target_unit`, `intended_change`, `outcomes`. The intended change text carries "in the UK". | No place token reaches the prompt. An exclusion never has place as its reason. | `constrain.py:173-179`, `constrain_prompt.py:129-140` |
| 10 | Target unit text | The planning conversation can write the place into it (refugees: "… living in Greater Manchester"). The longlist intent and criteria then carry the place, and the screen rejects on it. | The planning prompt keeps target unit, setting and geography apart. The compose step removes the plan's Where text from the intent and criteria and records the removal. | `runtime/task_agent_scoping_prompt.py`, `options_scoping/longlist_intent.py` |
| 11 | In-scope screen | "A different population … breaks it". Silence gives `cannot_check` ("the design does not say children aged 4 to 11"): 3 to 16 options per run. | A wider or adjacent population passes and goes to *tried on*. The option is judged as a kind of action: silence about the target unit or the setting passes. `cannot_check` is for a real unknown (R21). | `constrain_prompt.py` |
| 11 | Setting requirement at constrain | Judged on the setting the design or one study names (caregiving: 15 breaks, 12 `cannot_check`) | Excludes only when that kind of action cannot be delivered through the required setting. Evidence from another setting stays attached and shows on the card (R21). | `constrain_prompt.py` |
| 12 | Relevant screen | "acts on at least one of the plan's stated outcomes" | Also passes an outcome on a stated pathway to a plan outcome | `constrain_prompt.py` |
| 13 | Profile prompt | Title, abstract, evidence type. No plan. | + tagging context; three tags per record. The memo fingerprint gains a hash of the tagging context. | `evidence_search/extract/extract_interventions_prompt.py`, `interventions_records.py`, `interventions_profile.py:72-103`, `core/schema.py:1077` |
| 14 | Setting | Free text; holds towns, regions, bodies | Prompt rule (see Terms). Then a code pass: fold spelling variants into one facet label; move a setting the where-tried matcher recognises as a place into study geography when that field is empty; log each move as a repair. | `extract_interventions_prompt.py`, `options_scoping/longlist/coverage.py:122-126`, `where_tried.py` |
| 15 | Units | Every record except comparators | Thinned before clustering: `mentioned` records with no features and no outcome are dropped; records of one document with the same folded name collapse; at most 8 records per document. Each rule's count is in `provenance`. | `longlist.py:301-399` (`_own_units`) |
| 15 | Documents profiled | Every screened-in document, title-only included | Title-only documents are not profiled; they stay in Sources and in the counts. **Non-evidence documents stay profiled** (R17) and the thinning rules apply to them. | `evidence_search/extract/extract.py:649-690` |
| 16 | Recommended role | No negative examples | Negative examples: a target, a concept, a report, a method, a broad aim | `extract_interventions_prompt.py` |
| 18 | Option-search chain and the join | Each child walk runs acquire → screen → classify → appraise → ingest → profile. Its screen loads **every document of the task** (`_load_stage1_docs` has no scope filter) and judges it against the option's design. Obesity: the children screened 164, then 184, up to 326 documents. 139 to 183 documents per run come from option searches, and most never get a plan-level screen. The runner joins the children before `longlist`. | A child of a longlist walk is **acquire-only**. The runner joins the children before `screen_abstract`. The longlist scope's screen then judges the whole pool once (its task-wide load does this with no edit), and classify, appraise and the profile run once. Units come from the longlist scope. (R18) | `runtime/scoping_plan.py:183-205` (`LONGLIST_CHAIN`, `TARGETED_CHAIN`), `runtime/runner.py:1109-1143`, `runtime/option_search.py`, `longlist.py:1117-1149` (`_option_search_scopes`) |
| 18 | Stage-1 document loading, the add walk | Task-wide, as above | One optional directive key limits a scope to the documents its own walk acquired (`task_source_snapshot.run_id` records the acquiring run). The scoping side sets it for the add walk only. Absent key = today's behaviour. **The one edit inside an Evidence search component (R16).** The add walk's screen input is the plan-level one. | `evidence_search/assess/screen.py:439-500`, `runtime/scoping_plan.py:1390-1404` |
| 20 | Classify and appraise skip list | Filled for the longlist scope, inherited labels only. Child walks pass none. | Filled for the add walk too, with every document this task has classified or appraised in another scope under the same versions. The key exists; only the scoping runner changes. | `runtime/runner.py:653-770` (`leg_directive`, `resolved_skip_ids`) |
| 22 | Full-text ingest | A spine step in both chains | Out of every longlist and targeted chain (R13). The chat answers from the abstract chunk acquire writes. | `runtime/scoping_plan.py:183-205` |
| 23 | Screen input | Longlist scope: intent and criteria from target unit, outcomes, and the setting when required. Targeted scope: the option's design as intent, plus the same criteria. | The plan-level screen only: wide target unit and outcomes. No setting (reopens 045 D21), no place, no option design (R5, R15, R19). The screen stays two-way and its prompt does not change. | `options_scoping/longlist_intent.py:62-99` |
| 23 | Tried on | None | Coverage counts by population tag; the *tried on* line on the card; the facet on the list | `coverage.py`, `read_models.py`, `frontend/src/views/longlist/LonglistView.tsx`, `longlistPresentation.ts` |
| 26 | Where tried, sub-national | A few fixed entries | A table of recurring sub-national places, each mapped to its country | `where_tried.py:46-192` |
| 26 | Longlist intent and criteria text | A slot that ends in a full stop gives ".." | Trailing stops are stripped before composition | `options_scoping/longlist_intent.py:62-99` |
| 26 | Typing failure | Card shows no lever and no ambition | The previous typing stays; the failure is counted | `longlist.py:969-1008`, `1496-1510` |
| — | Screen vote rule, screen prompt, screen reps | **keep** | Unchanged | `screen.py:343-344`, `screen_prompt.py` |
| — | Search loop and search prompts (query forms, variants, fallback) | **keep** | Unchanged | `evidence_search/sourcing/search_loop.py`, `search_prompts.py` |
| — | Synthesis backend, baseline template, baseline targets `{"standard": 20, "rapid": 10}` | **keep** | Unchanged | `evidence_search/synthesis/*`, `runtime/scoping_plan.py:116` |
| — | Clustering engine, characterise, group, ES extract profiles, classify, appraise, ingest component | **keep** | Byte-identical prompts and outputs | `evidence_search/*` |
| — | Option design, longlist verbs, theme prompts | **keep** | Hashes unchanged | `scripts/prompt_hashes.json` |
| — | Baseline intent and criteria (they carry the place by design: the baseline is about the user's place) | **keep** | Unchanged | `runtime/scoping_plan.py:1287-1329` |
| — | Option tables, routes, Exclude / Include again / Add, the merge rule, Rebuild, option-search target, cap and width | **keep** | Unchanged | — |

## Rulings (owner, 2026-09-28)

Quoted words are the owner's. "Restate" means the owner answered "Yes" to
the restated intent that carried the item.

| # | Reopens | Ruling |
|---|---|---|
| R1 | 045 D4; open question 4 | **Accepted (restate).** The ceiling is a product number: target size 20, hard ceiling 25, seeds included. When seeds alone reach 25, discovery adds none. |
| R2 | Sheet row A9 | **Accepted (restate).** Variants are on the card, computed from members. No instance-of relation and no two-level list of rows. |
| R3 | 045 A21 | **Accepted (restate).** The profile receives the tagging context and writes three tags. Record content does not change. The memo stays per task; its fingerprint gains the tagging-context hash. |
| R4 | 045 D20 (reaffirmed) | **Accepted (restate).** Place never reaches `constrain`, and place is never an exclusion reason. |
| R5 | Intent item 17 | **Rejected.** No screen per option. Owner: "why do we need different option scope screening for each option? Isn't the scope the initial scope from the task agent planning conversation?" One criteria text, from the plan, for every screen of the run. Which option a document belongs to is decided at assignment. Item 19 (the strict vote) falls with it. |
| R6 | Intent item 21 | **Out of this slice.** It edits the Evidence search search loop (R16). |
| R7 | Intent item 25 | **Rejected.** "Leave the target at 10, record thin baselines as a known limit. I think the low number of citations is more likely to be an issue with the RAG implementation and associated parts of synthesis, as I've noticed it in evidence search syntheses as well." |
| R8 | L1, the option-search loop | **Out of this slice.** Its stop condition needed the option screen (R5) and it edits the search loop (R16). |
| R9 | L2 | **Accepted (restate).** One residual pass, then a number. |
| R10 | L3, allocation by corpus size | **Out of this slice (restate).** Recorded in `docs/deferred.md`. |
| R11 | Loop budgets | **Accepted (restate).** Constants named in this contract. The user does not see or set them. |
| R12 | Live check | **Staged.** "Initially, we don't need to run all 7, we can just start with ~3 and then I can decide whether we need to run the rest"; focused re-runs on stored data first. See § Acceptance checks. |
| R13 | Intent item 22; OS components | **Accepted.** "Yes, remove ingest, full text fetched in task 3." The chat says that it read abstracts only. |
| R14 | — | **Accepted.** Suggestions are named at reader grain and discovery may fold them; "user options aren't folded". |
| R15 | Intent item 23 | **Accepted.** "Yes, widen the criteria so adjacent populations pass." In every screen of the scoping task. |
| R16 | — | **The reuse rule.** "The preference would be to reuse evidence search components as much as possible where appropriate. If cost optimisations require changes to the underlying evidence search components, then maybe they don't fit into this task and should be considered later at a system level cost and latency optimisation task." One exception, accepted: the screen's document loading (item 18), because the task-wide load is a defect that many scopes per task brought in. |
| R17 | Intent item 15 | **Amended.** "Yes, keep non-evidence documents, exclude title-only ones." |
| R18 | 045 deliverable 3 (chain shape), S2 | **Accepted** ("yes to all"). Option searches of a longlist walk only acquire. The join moves before the screen. The longlist scope screens, classifies, appraises and profiles the whole pool once. The add walk keeps the full chain with the item-18 key. |
| R19 | 045 D21 | **Accepted.** "We should separate the target unit (who/what the intervention is for), from the target intervention setting and geography. But they are still important context of what the user wants, and will feed into things like transferability assessment. However we shouldn't let that stop potentially transferable evidence not getting in at the screen step." The division of § The four slots was put to the owner and accepted ("Yes"). |
| R20 | — | **Accepted (in the fold).** Suggested designs name no place and no institution of one country. |
| R21 | — | **Accepted.** Constrain judges the option as a kind of action: silence passes; a setting requirement excludes only when that kind of action cannot be delivered through the required setting; evidence from another setting stays attached. Owner: "That sounds right." |
| R22 | — | **Accepted** ("yes to all"). Record and do not fix in this slice: provider-written abstracts, duplicate documents without a DOI, the untested guesses path, the process-wide option-search pool, empty OpenAlex queries, full-text fetch failures (to task 3). See § Known limits accepted. |
| R23 | — | **Accepted** ("yes to all"). The not-stated flag is on 43 to 66 percent of memberships in five runs. Measure it in the replay at reader grain, then decide. |

## The four slots (R19)

| Slot | Screen | Record tag or field | Constrain | Task 3 |
|---|---|---|---|---|
| Outcomes | Yes | Outcome tag | Yes; a stated pathway passes | Yes |
| Target unit | Yes, wide | Population tag | Yes, exact; adjacent passes to *tried on* | Transferability |
| Setting | No | Setting field | Only a stated requirement; judged on the kind of action | Transferability |
| Geography | No | Study geography | No | Transferability |

The screen judges a document, and its error is not visible and not
reversible, so it is wide. Constrain judges an option, and its error is
visible and reversible, so it is exact. The target unit stays at the screen
because the outcomes alone do not keep the pool on the subject.

## Amendments from the review (2026-09-28)

Each amendment supersedes the matching words in the surface map, the terms
and the acceptance checks above. The text above is kept as written and
points here. "AMn" folds finding "An".

| # | Finding (severity) | Amendment | State |
|---|---|---|---|
| AM1 | A1 (blocker), A2, A13. The add walk cannot have a plan-level screen: acquire and the screen read the same scope intent (`runtime/harness.py:184-188`, `screen.py:1279`), and the added option's card lists its own scope's records. With the own-documents key, item 20 could never fire. | **The add walk stays exactly as built** (design as intent, task-wide load, full chain without ingest). The `screen.py` edit, the R16 exception and item 20 leave the slice. No file of the Evidence search screen changes. The screen criteria text is still the wide one (R15). | **Accepted** (owner, 2026-09-28) |
| AM3 | A3 (material). The tagging context cannot reach the profile prompt through the three profile files only. The fingerprint seam and the payload are in shared extract files (`extract.py:1751-1755`, `extraction_backend.py`, `iof_records.py:341-354`). | One optional argument, `interventions_context`, carries the tagging context to the intervention profile. It is absent for the IOF and ICF profiles, whose payloads, prompts and fingerprints stay byte-identical (existing tests, no edit). Files: `extract.py`, `extraction_backend.py`, the three profile files, `runtime/harness.py` (`_run_extract_interventions`). This is an edit in Evidence search files for a list-shape reason, not a cost reason. | **Accepted** (owner, 2026-09-28) |
| AM4 | A4 (material). Both walk kinds use purpose `targeted`; the purpose values are fixed by a database check. | The fan-out writes `acquire_only: true` into the child scope's `context`. `compose_scoping` reads it. No new purpose value and no migration. ADR 0040 records it as an amendment to ADR 0039 decision 2. | Folded |
| AM5 | A5 (material). `_option_search_scopes` reads every option's latest targeted scope, so an old full-chain child would supply units a second time. | Units come from the longlist scope and from parentless (add-walk) targeted scopes only. Test: a rebuild of a task built before this slice counts no document twice. A record with null tags, or tags from an older plan version, reads as "not tagged". | Folded |
| AM6 | A6 (material). Item 6 and item 12 conflict: a pathway outcome ("diets", "sugar") would be tagged `other`. | The outcome tag names the plan outcome the recorded outcome **is or leads to on a stated pathway**; `other` is for an outcome with no such pathway. The record's own outcome text does not change. Seeds and discovered options then carry plan outcomes alike. Test: an option whose members report only a pathway outcome passes the relevant screen. | Folded |
| AM7 | A7 (material). Place reaches constrain through the coverage summary (`where_tried` labels hold the plan's Where text), the question, and requirement texts; it reaches the profile through the intended change. "Place" had two definitions. | One place-strip function (the plan's Where text plus the tokens the where-tried matcher recognises), applied to: the screen intent and criteria, the constrain payload (question, intended change), and the tagging context. `where_tried` leaves the constrain payload. **A requirement in which the user names a place stays verbatim and is judged on the kind of action ("can this be done there"), never on where a study ran.** | **Accepted** (owner, 2026-09-28) |
| AM8 | A8 (material). The plan model has no setting slot; a setting exists only as a requirement (`task_agent_scoping_prompt.py:325-332`). | **No new plan field.** "Three slots" means three separate things in the plan's text: target unit, Where, and a setting that is either a requirement or an entry in Your context. The planning prompt puts a setting the user states without requiring it into Your context, so task 3 has it. | **Accepted** (owner, 2026-09-28) |
| AM9 | A9 (material). Seeds alone can exceed 25 (the user's options, the report's, up to ten suggestions; on a rebuild every earlier option is a seed). | The ceiling binds discovery: **discovery adds no option once the list holds 25.** Options that cannot be folded (the user's) can take the list above 25; the excess is counted in `provenance`. On a rebuild, clustered and suggested seeds can be folded; the user's cannot. | **Accepted as written** (owner: "Sounds good"). The variant that lowers the number of suggestions when the user names many options was offered and is not built. |
| AM10 | A10 (material). The chat prompt is shared with the Evidence search and says nothing about abstracts; no chat citation shows the text basis. | The label is code-authored: the chat citation shows *abstract only* from the citation's `text_basis`. No prompt changes. Files: the chat citation component in `frontend/`. Retrieval without ingest is confirmed in the code (`acquire.py:737-747`, `synthesis_tools.py:1229-1235`). | Folded |
| AM11 | A11 (material). `longlist_scope` deletes and rewrites the task's memberships and typing, so a replay on the stored task destroys the comparison. | The replay runs on a **clone** of each stored task (plan, baseline artefact, documents). It screens the whole cloned pool once in a new longlist scope under the new screen input. The stored task is checked unchanged by a row count and hash before and after. | Folded |
| AM12 | A12 (material). Spec and ADR lines this slice changes were missing from § Spec changes. | Added to § Spec changes: trust § Screening ("screens judge the option's specified design" → the kind of action, R21); trust § Provenance labels and capability § Depths and modes ("full text read for the documents cited"; ingest in the longlist spine → R13); ADR 0039 decisions 2 and 3 (chain shapes, the join) and decision 8 (runner-up "never shown" → shown, item 7), superseded in ADR 0040. | Folded |
| AM14 | A14 (minor) | The per-document cap keeps records by role (evaluated, described, recommended, mentioned), then in the profile's order. Drops are counted per rule. Title-only documents have their own count on the read model. | Folded |
| AM15 | A15 (minor) | The theme count moves to the constrain step's summary; `frontend/src/views/workspace/runProgress.ts` joins the surface map. Themes are correct at build time; a later user exclusion does not rebuild them. | Folded |
| AM16 | A16 (minor) | Concurrent acquires can insert one DOI twice. Recorded as a known limit; M9 reports duplicates per run. | Folded |
| AM17 | A17 (minor) | R15 applies to the longlist run's screen, not to the baseline. The planning prompt revision changes the target unit text, so the baseline's criteria text changes with it; no other baseline change. | Folded |
| AM18 | A18 (minor) | M3 (youth guarantee, ALMP) and M4 (place exclusions in energy and cohesion) are read in stage 1. Stage 2 reads them only for the three live domains. | Folded |
| AM19 | A19 (minor) | A kept typing keeps its own `taxonomy_version`. The page shows the definitions of the version an option was typed under. | Folded |
| AM20 | A20 (minor) | A variant is a distinct folded intervention name among an option's members, with its document count; at most 8 are shown, by count. Folded seeds are listed first. Variants are recomputed wherever coverage is (constrain's merge; an added option's own coverage). | Folded |
| AM21 | A21 (minor) | § Public interface gains the thinning counts and the title-only count. The rubric gains boxes for null tags and for the recorded place removal. "One stage-1 screen row" is per longlist walk. | Folded |

## Compile constants

| Constant | Value | Source |
|---|---|---|
| Target size · hard ceiling | 20 · 25 | R1 |
| Residual passes | 1 | R9 |
| Records per document, maximum | 8 | item 15; measured in the build |
| Option-search target, cap, width | 10 per backend · 15 · 4 | unchanged (045 D2) |
| Broad search target | standard 50 · rapid 25 per backend | unchanged |
| Baseline target | standard 20 · rapid 10 per backend | unchanged (R7) |
| Screen reps | 3 | unchanged (owner, 2026-09-17) |

## Spec changes (proposed; the owner decides each before it is applied)

Each change follows from a ruling above. The wording is put to the owner in
the build, and only accepted wording is applied.

1. OS components § 6: reader grain; target size and hard ceiling in place of
   the formula; the corpus digest; the residual pass; variants on the card;
   suggestions at reader grain and the fold; no package minting by
   discovery; lever list v2; themes after constrain; the baseline as
   reference for discovery, typing and constrain (R1, R2, R9, R14).
2. OS components § 10 extract and § 2–5: the tagging context and the three
   tags; the setting rule; title-only documents are not profiled (R3, R17).
3. OS components § 2–5 and § ⟨longlist depth⟩: ingest out of the chains;
   option searches of a longlist walk only acquire and the longlist scope
   screens the pool once; the screen input is the wide target unit and the
   outcomes, with no setting (045 D21 reopened), no place and no option
   design; the add walk screens the documents it acquired (R13, R15, R16,
   R18, R19).
3a. OS components § 1 plan and plan-as-object: target unit, setting and
   geography are three separate slots; the target unit text holds no place
   and no setting (R19).
4. OS components § 7: place never reaches constrain; adjacent population
   goes to *tried on*; the pathway rule for the relevant screen; the
   distinct screen over the whole list; an option is judged as a kind of
   action, silence passes, and a setting requirement excludes only a kind
   that cannot be delivered through the setting (R4, R21).
5. OS capability § Output structure (Longlist): the *tried on* line and
   facet; the runner-up lever on the card; § Open decisions: open question
   4 closes (R1).
6. OS capability § Pipeline and gates: a recorded principle for task 3 —
   shortlist and assessment judge against the baseline; task 3 fetches full
   text for shortlisted options (item 9, R13).
7. `vocabulary.md`: reader grain, variant, tried on.
8. Decision sheet rows A9 and E4: decision column updated.
9. One line per accepted change in `docs/specs/log.md`.

## Scope / Out of scope

- **In:** items 1–16, 18, 22, 23 and 26 as the surface map states them and
  as § Amendments from the review amends them (item 20 is withdrawn by AM1)
  (item 10 includes the target unit text; item 18 is the acquire-only
  option search);
  one migration; ADR 0040; tests; the replay script (in the gitignored
  evidence folder); the staged check; `docs/deferred.md` deltas.
- **Out, to a later system-level cost and latency task (R16):** query
  variants and a fallback ladder (item 21); the baseline writer's tool list
  (item 24); a screen memo across scopes beyond the item-18 edit; the
  option-search loop (L1); allocation by corpus size (L3).
- **Out, rejected:** a screen per option (item 17); the strict vote (item
  19); a higher baseline target (item 25).
- **Out, other:** the shortlist and assessment, update-in-place and the
  removal of Rebuild, the full-text fetch for shortlisted options (task 3);
  the wording of generated option-search queries (045 F4); any second grid
  axis; a cross-task profile memo; user-visible loop budgets; a new table;
  any change to an Evidence search output.

## Constraints & approval gates

Approval is this contract's sign-off.

- **Schema:** `intervention_profile_record` gains `population_tag`,
  `outcome_tag` and `object_tag`, all nullable text. One alembic revision
  on head `c7e2a9f4b1d8`, reversible: the downgrade drops the three columns.
  No value rewrite. No other schema change.
- **Evidence search components (as amended by AM1 and AM3):** no edit to
  the screen. One optional argument passes the tagging context through the
  extract path to the intervention profile (`extract.py`,
  `extraction_backend.py`); the IOF and ICF profiles do not receive it and
  stay byte-identical. Superseded wording: ~~one edit, in `screen.py`~~. No
  other file under `evidence_search/` changes, except the intervention
  profile's own files (`extract_interventions_prompt.py`,
  `interventions_records.py`, `interventions_profile.py`, and the
  title-only rule in `extract.py`'s selection-free path), which options
  scoping owns.
- **Runtime egress:** the same hosts and verbs as 045. Fewer calls. The
  profile prompt now carries three plan fields to the inference route.
- **Public interface:** additive only — `variants`, `tried_on`,
  `runner_up_lever_type` on the option read models; a `tried_on` facet
  source on the longlist read model. OpenAPI regenerated by
  `make openapi-sync`.
- **Prompts (lead-authored, hash-pinned):** six revisions with new version
  names and recorded diffs: `task_agent_scoping_v4`, `longlist_suggest_v2`,
  `extract_interventions_v2`, `longlist_cluster_v2`, `lever_typing_v2`,
  `constrain_v2`. Every other pinned hash is unchanged.
- **Runner (scoping side):** the join of the option searches moves from
  before `longlist` to before `screen_abstract`; the targeted chain of a
  child is `acquire` only. The Evidence search's park-and-resume path is
  not touched (the existing steering tests are the fence).
- **Stored data:** existing longlists stay readable. Null tags read as
  "not tagged". An option typed under `lever_types_v1` keeps its version.
- **Dependencies, CI, auth, production config:** none.

## Public / private boundary

Contract, rubric, plan, ADR and `verification.md` are public-safe. The
read-backs, traces, the drive script and the replay script stay in the
gitignored `evidence/` folder. `verification.md` carries counts and option
names only.

## Model route

OpenAI under the approved controls, behind the routing seam. Tiers do not
change: the profile and assignment on the mini model; suggest, discovery,
typing, themes and constrain on the judgment model. Item 2 allows a move of
assignment to the judgment model only if the build measures that the mini
model cannot follow the new rule; the measurement goes in
`verification.md`.

## Disciplines binding this slice

- **Reuse Evidence search components as they are** (R16).
- **Tags sort; they never drop.** No record is removed because of a tag.
  Thinning (item 15) uses role, features and outcome only, and each rule is
  counted.
- **Flag, don't drop.** Adjacent evidence goes to *tried on*. A thin option
  stays. A folded seed stays visible as a variant and as *also found as*.
- **The user's own options are never folded or renamed.**
- **Honest absence.** The residual and the thinning counts are numbers the
  read model carries. A chat answer at the longlist stage says that it read
  abstracts only.
- **Owner decides spec changes.**

## Known limits accepted

- **Thin baselines.** The rapid baselines of the seven runs cited 2 to 15
  sources. The target stays at 10 (R7). The baseline is still the reference
  for discovery, typing and constrain. The cause is recorded for the
  synthesis optimisation task.
- **Option searches keep their query cost** (three query forms; R6, R8).
  In the seven runs OpenAlex returned nothing for 27 to 47 of 50 to 60
  generated option-search queries, and Overton received the whole design
  paragraph as its query. For the system-level task.
- **About half of the "abstracts" are provider text** (machine summaries 32
  to 52 percent; snippets more). The profile reads and quotes them, and the
  label says *abstract only* (R22).
- **Duplicate documents inside one task** (6 to 27 duplicate titles per
  run). Only about half the documents have a DOI, so the DOI rule misses
  them (R22; issue #75).
- **Reasoned guesses have no live test.** No plan of the seven had a
  preference, so no guess was produced (R22).
- **The option-search pool is shared by every task in the process.** Two
  runs at once queue each other (energy: its option searches started 11
  minutes after its walk) (R22).
- **Full-text fetch fails for about half the documents** (obesity: 52 of
  74 attempts). Task 3 fetches full text for shortlisted options and must
  plan for this (R22).
- **A larger pool.** With setting and place out of the screen and adjacent
  populations admitted, the pool grows. The replay measures the pool size
  and the share of records tagged `other`.
- **A replay is not a full result.** A seed named in the replay has no
  search of its own, so a replayed option can show fewer documents than a
  live run. The replay judges the option rows and their grain.

## Stop conditions

Halt and escalate when: a second migration or a new table is needed; a
second edit inside an Evidence search component is needed; moving the join
needs a change to the Evidence search's park-and-resume path; the chat cannot answer from abstract chunks
without ingest (R13); the replays do not land between 13 and 25 options
after two rounds of prompt tuning (report the read-backs, do not tune a
third time without the owner); scope would grow into task 3; the budget is
spent.

## Acceptance checks

- `make verify` green.
- **Deterministic tests:**
  - migration round-trip; null tags read correctly.
  - items 1, 4: no discovery call receives unit payloads; the digest counts
    are correct; the option count never exceeds the hard ceiling; a
    suggested seed can be folded and shows as a variant; an option with
    origin `added_by_you` is never folded or renamed; no `part_of` row has
    `created_by = "longlist"`; at most one residual pass.
  - item 2: prompts carry short ids only; a mangled short id is repaired
    without a second model call where the mapping is unambiguous.
  - items 5, 8: the distinct call receives every option; themes contain no
    excluded or merged option.
  - item 6: a discovered option's outcomes are a subset of the plan's.
  - items 7, 26: typing and constrain batches run in parallel; an invalid
    typing keeps the previous values; the runner-up is served.
  - item 10: the constrain payload holds no token the where-tried matcher
    recognises, on a plan whose intended change says "in the UK"; on a plan
    whose target unit says "living in Greater Manchester", the composed
    longlist intent and criteria hold no place and the removal is recorded.
  - item 11: an option whose design is silent on the target unit or the
    setting passes; an option of a kind that cannot be delivered through
    the required setting is excluded with the requirement named.
  - items 13, 14: the fingerprint changes with the tagging context and not
    with Where; a setting that is a place moves to geography and is logged;
    folded setting labels.
  - item 15: each thinning rule, with its count; a title-only document
    produces no profile call; a Non-evidence document is profiled.
  - item 18: a child of a longlist walk runs `acquire` only; the join
    happens before `screen_abstract`; a document an option search acquired
    has exactly one stage-1 screen row in the task, in the longlist scope;
    a failed child still degrades the walk and never fails it. For the add
    walk: with the key set, the scope screens only its walk's documents;
    with the key absent, the screen loads as today (the existing Evidence
    search screen tests pass with no edit).
  - item 20: the add walk skips a document the task already classified.
  - item 22: neither chain contains `ingest_full_text`; a chat question
    over a longlist answers with citations labelled *abstract only*.
  - item 23: the screen input holds the wide target unit and the outcomes,
    and no setting, no place and no option design, on a plan with a setting
    requirement.
  - frontend (vitest): the *tried on* line and facet; variants on the card;
    the runner-up line; the flag wording.
- **No AI eval in this slice.** Option quality is read by hand.
- **The staged check (R12):**
  1. **Replay, the seven stored tasks.** Suggest, profile, longlist and
     constrain over the stored documents; stored documents the old screen
     rejected are screened once under the widened criteria. No search.
     Prompt tuning in the build uses the replay.
  2. **Live, three rapid runs on new tasks:** obesity (rich corpus,
     class-level reviews), refugees (thin corpus), caregiving (setting
     requirement, adjacent population). Not attended. Obesity is also
     opened in the browser for the card, the *tried on* facet and one chat
     question (about 10 minutes).
  3. **Live, the other four:** only on the owner's decision after stage 2.

  No Evidence search live run.
- **Measures, read from the saved results.** M1 to M6 are pass conditions
  on the hand reading. M7 and M8 are reported, not pass conditions (owner:
  "list shape is the priority").

  | # | Measure | Stage | Pass |
  |---|---|---|---|
  | M1 | Options per run | 1, 2 | 13 to 25 |
  | M2 | Rows that are one named trial | 1, 2 | none |
  | M3 | Class-level reviews (youth guarantee, ALMP, combined diet and activity) | 1, 2 | each is a member of an option |
  | M4 | Exclusions with place or population overlap as the reason | 1, 2 | none |
  | M5 | Setting facet labels that are a country, region or body | 1, 2 | none in the top 8 |
  | M6 | Adjacent-population evidence | 1, 2 | shown as *tried on* on the options that have it |
  | M7 | Screens per document; cost per run from Langfuse | 2 | reported beside the pre-contract figure |
  | M8 | Wall-clock time per run | 2 | reported beside the pre-contract figure |
  | M9 | Pool size; share of records tagged `other`; share of memberships with the not-stated flag; `cannot_check` verdicts per run | 1, 2 | reported beside the pre-contract figure (R23) |

## Verification evidence expected

Command tails; the migration round-trip; the OpenAPI diff; the six prompt
diffs and the hash diff; a table of M1 to M8 beside the pre-contract
figures, each number read back from the saved file; the hand reading of
each longlist; the item-2 model measurement; the replay's cost and time per
task; the constants as measured; known gaps; the `docs/deferred.md` delta.

## Risk tier & review focus

**Tier 4** — a migration, six prompt revisions, a change to the longlist
walk's chain and join, and one edit in a shared component. ADR 0040 with a rollback plan; adversarial review at the
contract and plan stages (`codex-rescue`, read-only; `deep-reasoner` if
Codex is not available); the step-7 stack per the spine.

Rollback shape: `alembic downgrade -1` drops the three columns; deploy the
previous image; the prompt revisions revert with the image. Longlists built
by this slice stay readable by the previous image, because every read-model
change is additive.

Review focus: Evidence search outputs unchanged and one edit only under
`evidence_search/` outside the profile's files; no tag drops a record; no
place in constrain or in the screen input; no setting in the screen
input; no exclusion for population overlap or for silence; a user's option
never folded; each document screened once in a longlist run; every thinning rule counted; no new table.
