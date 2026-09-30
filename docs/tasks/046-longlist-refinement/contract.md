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
> approved"). **Amended 2026-09-28 after approval, on the owner's
> rulings R24–R27** (the iteration loops and the prompts open for
> refinement) **and at the plan gate** (§ Amendments at the plan gate;
> R28). **Plan approved 2026-09-28 · owner.** ADR:
> **[0040](../../adr/0040-options-scoping-longlist-refinement.md)** —
> Accepted 2026-09-28. **Design phase closed 2026-09-28; the build runs in
> a fresh conversation with `task-cycle-build`.**
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
| 8 | Themes | Built inside `longlist`, before `constrain`; not recomputed. Excluded options stay in them (obesity 13 of 13, energy 20 of 20). | A component of its own, **`theme`**, after `constrain`: `longlist → constrain → theme`. It groups the included options only. The code and the prompt move out of the longlist package; the clustering engine is not touched. Not a spine step: a failure degrades the walk and the options show under "No theme". (R28) | `longlist.py:1361-1409` → new `options_scoping/theme/` (`theme.py`, `longlist_theme_prompt.py` moved), `runtime/scoping_plan.py`, `runtime/run_spec.py`, `runtime/harness.py`, `runtime/task_plan.py`, `api/stage_vocabulary.py`, `frontend/src/views/workspace/runProgress.ts` |
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
| R24 | R12; the two-round tuning limit | **Accepted.** Prompt refinement is a loop for each stage: change, replay, read, refine. Owner: "I think it would make sense to do multi round iteration - i.e. make the changes, replay, review results, then refine further". The replay tool is built early and runs one stage at a time. Tuning set: obesity, refugees, caregiving, energy. Check set, not used for tuning: NEET, heat pumps, cohesion. |
| R25 | — | **Accepted** ("D1 - A"). The lead runs the rounds and reports to the owner at the end of each stage's loop; the owner decides if the stage is good. |
| R26 | § Stop conditions | **Accepted** ("D2 - sounds good"). A loop stops when its measures pass on the tuning set, or after five rounds; then the lead stops and reports. |
| R27 | § Constraints (prompts) | **Accepted.** "Since we're doing iterative prompt refinements, all longlist prompts can be in scope for refinement." Open: planning, suggest, intervention profile, discovery and assignment, lever typing, constrain, themes, option design. Not open: the Evidence search prompts (screen, classify, search queries, baseline template, chat) and the longlist verbs sort. Reading confirmed by the owner ("yes, that reading is right"). A prompt changes only on a finding from a round, named with the change; each change is re-pinned with its diff. |
| R28 | OS components § 6; ADR 0039 decision 8 | **Accepted.** "Yes, three components". The longlist walk's last three components are `longlist` (options), `constrain` (verdicts) and `theme` (themes of the included options). Owner, on theming inside one component that runs twice: "wouldn't that just be two components then?"; on theming inside constrain: "I don't think it makes sense for constrain to contain theming". `theme` is the Evidence search characterise's theme machine, modified (its unit is the option). It is not a spine step. The list shows no themes from the end of `longlist` to the end of `theme`; accepted in this slice and recorded for task 3. |
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
| AM15 | A15 (minor) | *Superseded by R28: the theme count is in the `theme` step's summary.* ~~The theme count moves to the constrain step's summary;~~ `frontend/src/views/workspace/runProgress.ts` joins the surface map. Themes are correct at build time; a later user exclusion does not rebuild them. | Folded |
| AM16 | A16 (minor) | Concurrent acquires can insert one DOI twice. Recorded as a known limit; M9 reports duplicates per run. | Folded |
| AM17 | A17 (minor) | R15 applies to the longlist run's screen, not to the baseline. The planning prompt revision changes the target unit text, so the baseline's criteria text changes with it; no other baseline change. | Folded |
| AM18 | A18 (minor) | M3 (youth guarantee, ALMP) and M4 (place exclusions in energy and cohesion) are read in stage 1. Stage 2 reads them only for the three live domains. | Folded |
| AM19 | A19 (minor) | A kept typing keeps its own `taxonomy_version`. The page shows the definitions of the version an option was typed under. | Folded |
| AM20 | A20 (minor) | A variant is a distinct folded intervention name among an option's members, with its document count; at most 8 are shown, by count. Folded seeds are listed first. Variants are recomputed wherever coverage is (constrain's merge; an added option's own coverage). | Folded |
| AM21 | A21 (minor) | § Public interface gains the thinning counts and the title-only count. The rubric gains boxes for null tags and for the recorded place removal. "One stage-1 screen row" is per longlist walk. | Folded |

## Amendments at the plan gate (2026-09-28)

The plan-stage adversarial review (fallback lane, `deep-reasoner`,
read-only; the Codex lane has no budget) returned 21 findings, verdict
"material change needed". Most are seam detail and are folded in
[plan.md](plan.md) § Plan-review folds. The ones that change this contract:

| # | Finding | Amendment | State |
|---|---|---|---|
| PA3 | P3. Chat citations carry no text basis (`api/answer_core.py:297-301`), so the *abstract only* label (AM10) has nothing to read. | The citation facts gain `text_basis` (additive; the chat path is shared, so an Evidence search chat shows the label too). | **Accepted** (owner: "Fine") |
| PA9 | P9. Building themes at the end of `constrain` puts a model call that can fail after the verdicts, and the list shows no themes while constrain runs. | The lead proposed a filter with no model call. **The owner rejected it** ("why don't we filter the excluded options before the theme generation?") and ruled R28: `theme` is a component of its own after `constrain`. Its failure cannot touch the verdicts, because `constrain` has committed. | **Replaced by R28** |
| PA11 | P11. The where-tried matcher holds nationalities ("Polish", "Irish"). A strip by matcher removes part of a population. | The place strip removes the plan's Where text and place phrases led by a preposition ("in", "living in", "across", "within"). It never removes a nationality. Supersedes AM7's definition of the strip. | Folded |
| PA1 | P1. The replay never runs the planning conversation, so it cannot test the planning prompt. | A **planning replay**: the seven original questions are put to the planning prompt, and the lead reads the target unit, Where and Your context of each draft plan. M4 in the stage replay tests the place strip only. | Folded |
| PA14 | P14. Rubric box 16 said "three nullable columns and nothing else". | The two columns with fixed values carry a check constraint each. The box is reworded. | Folded |
| PA21 | P21. A child that the join timeout cut off can still add documents after the screen. | Known limit; M9 counts documents with no screen row in the longlist scope. | Folded |

## Amendments after the live check (2026-09-29)

The owner read the build's results (verification.md) on 2026-09-29 and ruled
in the build conversation. Each ruling supersedes the matching words above.

| # | Reopens | Ruling |
|---|---|---|
| R29 | Item 7 (the typing wire drops `lever_reason`) | **The lever type has a reason on the card**, as the ambition has. Owner: "For the ambition, we have a reasoning for the label described in the options profile. I think it would be nice to have this for the lever type too." The wire keeps `lever_reason`; it is stored with the longlist result (no new column) and served on the option. `runner_up_reason` stays removed. |
| R30 | Item 3; R23 | **The not-stated flag leaves the longlist card.** Measured at reader grain: 79 to 86 percent of memberships in the three live runs. Owner: "Yes" to "remove 'not stated in the abstract' from the longlist card". The flag stays in the stored data and the counts; task 3 reads full text. |
| R31 | R20 | **The design of the user's own option names no place** and no institution of one country, as a suggested design does. The user's words stay verbatim. Owner: "Yes". Finding: both own-option searches of the live refugee run found no document about the option; the design, which is the search query, held "in Greater Manchester". Prompt `option_design_v2` (a seventh revision, on a finding, R27). |
| R32 | Item 14 | **No fixed list of setting kinds.** Owner: "I don't think a fixed list is the right solution here given that policy atlas should be able to cater to a wide range of domains, and I don't think we'll be able to maintain a fixed list that would be able to do this". The way to a reliable setting is open; nothing is built for it until the owner rules. |
| R33 | Items 10–12 | **Constraints are under discussion.** Owner: "the idea of constraints is quite nuanced … There's something there about what should constrain an option, vs what is an implementation consideration, vs what's about transferability". A test with hard requirements ran on three replays (evidence `rounds/9-constrain-hard-requirements.txt`). No change to constrain until the owner rules. |

## Amendment 2 (2026-09-29)

The owner and the lead discussed a second amendment after the build, one
topic at a time. The record is [amendment-2-proposed.md](amendment-2-proposed.md).
The final statement, with the design detail, is
[amendment-2-final.md](amendment-2-final.md) ("final" below). **Decided by the
owner 2026-09-29. The adversarial review ran the same day (two reviewers);
the owner decided on its results.** Nothing of it is built. Each ruling
supersedes the matching words above; the text above is kept as written.

Quoted words are the owner's. "Lead's recommendation, accepted by the owner
(2026-09-29)" marks an answer the owner accepted; only the words quoted are
the owner's. For the six decisions after the review, the owner's answer to
each was "okay". The eight build questions of final § 7.3 (B1–B8) are
the lead's decision (data shape or name); the owner can change it; none is the owner's words. What is still open is in final § 7.1.

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

### Earlier items that amendment 2 changes

| Earlier item | What replaces it |
|---|---|
| § Deliverable ("one alembic revision (three nullable columns)"); § Constraints, Schema ("No other schema change") | That revision is built (`d8f3b6a2c4e1`). Amendment 2 adds one more: one JSON column on `longlist_result` for the profile (R45) |
| § Stop conditions ("a second migration or a new table is needed") | A migration beyond R45's one revision, or a new table (R45) |
| AM8 ("No new plan field") | Withdrawn: the plan gains the kind `consideration` with `aspect` and `hard` in its JSON payload (R34). No plan slot "Who decides" (R35 withdrawn) |
| Plan kind `requirement` | Renamed `boundary` (R53) |
| `CHECKED_AT_BY_KIND` (`runtime/scoping_plan.py:99-105`) | `boundary` at `longlist`; `consideration` at `assessment`; no new `CheckedAt` value (B3, the lead's decision (data shape or name); the owner can change it) |
| R4 and AM7 ("place never reaches constrain") | One exception: constrain reads the line "who decides", which names the body and the country it assumes. Evidence from another place is never excluded for its place (R38) |
| R28 (the walk's last three components are `longlist`, `constrain`, `theme`); plan S1 (`LONGLIST_CHAIN`) | `longlist → option_profile → constrain → theme`; `option_profile` is a spine step (R37) |
| Surface map item 7 (typing inside `longlist`, judging ambition against the baseline; batches in parallel); S12 | Lever typing moves into `option_profile`; it writes no ambition. Ambition is its own whole-list call (R37, R40). S12's keep-previous rule for one invalid typing moves with it, as built (B8, the lead's decision (data shape or name); the owner can change it) |
| Ambition as do minimum · incremental · structural; `ambition_bands`; group by ambition; the ambition word on a list row | Relative ambition; the bands and their read-model and view parts are removed (R40) |
| Terms, **setting**; surface map item 14 (the record's setting feeds the facet) | The delivery setting is a fact about the option; the Setting facet uses it; "studied in" on each document is not built in task 046 (R41; B4, the lead's decision (data shape or name); the owner can change it) |
| R32 ("nothing is built for it until the owner rules") | R41 |
| R33 ("No change to constrain until the owner rules") | R34, R38. Constrain gains the authority label; a consideration has no effect on exclusions |
| § Constraints, Prompts (six revisions) | Also: `task_agent_scoping_v5`, the line prompt(s), the ambition prompt, the setting prompt, lever typing moved, `constrain_v3`, each through a refine loop with one stop measure (R48). The wire models are prompt text, so the rename, the move of typing and the ambition change re-pin hashes; these edits are the lead's (`task_agent_scoping_prompt.py:83-120`, `lever_typing_prompt.py:87-104`, `constrain_prompt.py:59-130`) |
| Constrain's output (`longlist_result.judgements`) | Gains one labelled authority entry per option that has a label (plan S18; lead's decision from the plan review, 2026-09-30) |
| § Constraints, Public interface ("additive only") | Not additive only: `ambition_bands` and group by ambition are removed; the additions are in final § 3 "Contract parts that change" |
| § Constraints, Stored data | For amendment 2's fields: no code for stored values of an earlier development iteration (R52) |
| § Risk tier, rollback ("every read-model change is additive") | `alembic downgrade -1` drops the profile column; deploy the previous image. A longlist built by amendment 2 is not guaranteed to read cleanly under the previous image; nothing of this feature is staged (R52) |
| § Acceptance checks, measures | M10, M11, M12, M14 added (R49); M8 stays reported (R46) |
| § Known limits accepted | Added: the window from the end of `longlist` to the end of `option_profile`; an added option has no lines until the next rebuild; a record on two plan outcomes counts for one; the marks of a merged pair (final § 2.10) |
| § Spec changes | New items in final § 3 "Contract parts that change"; wording to the owner |

## Amendment 3 (2026-09-30)

The owner and the lead discussed a third amendment after the amendment 2
live runs, one topic at a time. The record is
[amendment-3-proposed.md](amendment-3-proposed.md). The final statement, with
the design detail, is [amendment-3-final.md](amendment-3-final.md) ("final 3"
below). **Decided by the owner 2026-09-30; the 18 build questions answered;
the adversarial review ran the same day (two passes, 34 findings) and the
owner decided on its results, then made two more decisions.** Nothing of it
is built. Each ruling supersedes the matching words above; the text above is
kept as written.

Quoted words are the owner's. R68 is the lead's (the record marks it
"accepted by the lead"); the owner can change it. "(lead, Qn / An / Bn)"
marks the lead's answer to a build question or the lead's rule for a review
finding (the lead's file `a3-review-findings.md`, applied in final 3); the
owner can change it. Q1, Q5, Q10, Q11, Q16 and the decisions after the
review are the owner's, and so is Q24; Q20, Q22, Q23 and Q25 are the
lead's. What is still open is in final 3 § 7.1; no question is open. Rounds 2–5 of the profile loop
(`evidence/rounds/12L-profile-loop.md`) were built after amendment 2 and are
not part of this amendment; round 5 closes the "country in the sentence"
item.

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
| R71 | R45 ("a migration beyond this one revision"); § Stop conditions | **One alembic revision for amendment 3** on the head `e9a4c1f7b3d2`, on `intervention_profile_record`: the nullable columns `programme_name` and `study_country`, and the renames `population` → `unit` and `population_tag` → `unit_tag` (its check constraint with it); `population` → `unit` on `intervention_outcome_finding` and `implementation_context_finding` (R75); the union view recreated with `unit` (S27); reversible; no other schema change; no new table. The stop condition becomes *a migration beyond this one revision*. Owner: the Q1 answer (allowed by the owner) → "1. yes"; the record's decision "The one migration of amendment 3" (after the review); the finding columns "in the same migration" ("Two more decisions") |
| R72 | Topic 4 ("No new extraction"); the where-tried matcher | **`study_country` at the root.** The record gains `study_country`: the country of the stated place ("Hamburg" → Germany), from the abstract and the model's knowledge; "multiple" for a group; empty when nothing is stated. It holds every country the record names, separated, each as its short English name; England, Scotland, Wales and Northern Ireland are places under the United Kingdom; the code folds case only (lead, Q22, Q23). The where-tried matcher and its fixed lists of country and place names go (the place strip: R74). Owner: "But the hamburg one isn't a good example because that should be under Germany, no?" · "Why do we even need a fixed list?" |
| R73 | Item 13 (the record's `population` and its tag) | **`unit` replaces `population` in the record, for options scoping and Evidence search.** The intervention profile record's `population` becomes `unit` ("who or what the intervention was delivered to: people, organisations, sites or things") and `population_tag` becomes `unit_tag`, in the same migration and prompt round. The two finding records take `unit` too (R75). Owner: "Why is there still a population field, I thought we didn't want to use the population concept in favour of unit?" · "Will this also be an update to the evidence search fields. I don't really want there to be one definition in options scoping and another in evidence search. The unit concept is better and should be used throughout" |
| R74 | S6 and PA11 (the place strip); item 10 (constrain's plan data); R31 (the design names no place) | **No place list: the place rule in words.** `strip_place` and its lists of country and place names go, with `names_place` (the record-level setting pass) and `where_codes`. Every prompt that read the stripped text gets the rule in words: the place in the question is the user's place, not a criterion; judge as if the question named no place — the screen criteria, the record tagging context, constrain, the option design, discovery, typing, the eight lines and the folding calls (lead, Q25). A phase with a loop: the prompts change and M4 (no exclusion and no screen failure because of place) and the screen's pass rate are measured on the replays; the list goes only if M4 holds; if M4 fails, the list stays and the final and `verification.md` say so. Owner: "I don't understand your explanation of where the other fixed list is used. Please explain. My hunch is that that isn't needed either" |
| R75 | The review's decision (the finding records "keep `population` for now") | **`unit` in the two finding records.** The intervention-outcome and implementation-context finding records and their prompts take `unit` in this amendment: columns in the same migration (R71); the wire; the prompt field descriptions with the wider definition; the findings view label. A like-for-like word change: re-pinned hashes and a read of the diff, no replay (the owner's 038 ruling on word swaps). It reaches production data: a plain column rename, reversible, no version change on the finding records, so no document is extracted again; `iof_records.py`, `icf_records.py`, `finding_references.py` and `interventions_records.py` join the hash guard (owner, Q24). Owner: "We should reword the prompts too, it's just a minor change and the rename should be aligned, it doesn't make sense to call it two different things" · "Keep in this amendment." |

### Earlier items that amendment 3 changes

| Earlier item | What replaces it |
|---|---|
| Terms, **tried on** ("the populations an option's adjacent-tagged members studied"); surface map item 23 (a count, never a filter) | Option-level kinds of the target unit from a folding call; the facet filters, no counts (R54, R55, R57) |
| Terms, **variant**; R2; AM20 (at most 8, folded seeds first); topic 6 decision 3 ("by the clustering call") | Examples, at most 5, from the record field `programme_name`; folded seeds under "also found as" (R63) |
| R42 ("documents that evaluated the option; among them …"; the lead's "evaluating documents only") | Any role; the evaluated count separate (R56); shown in one outcomes table (R64) |
| R43 and Q10 ("a line with no mark shows no word"; "Middle" only a grid column head; eight cells) | Seven cells with "Middle", also on a line with few marks (R65) |
| R43 (the authority line in "What it is") | Beside the "Who decides" row (R70) |
| Item 7 (the runner-up shown on the card) | Removed; the lever line of R62 |
| R40 and Q4 (ambition in "What it is", after the lever line) | Ambition is the first row of "What it would take" (R68) |
| R44 / verification D16 (label "Estimate, before assessment") | "Policy Atlas's estimate" (R68) |
| Task 045 D20, ADR 0039 decision 10 (where tried grouped against Where; comparable = OECD); item 26 (the sub-national table) | Two levels from `study_country`: a country · "multiple countries" · "other" · "not stated"; no comparability label; no matcher (R59, R72) |
| S6 and PA11 (the place strip); item 14's setting pass (`names_place`) | The place rule in words, if M4 holds on the replays (R74) |
| Item 13 (the record's `population`, `population_tag`) | `unit`, `unit_tag` (R73) |
| The finding records' `population` | `unit` (R75) |
| The card's four top cells and the depth chip | Removed; the abstracts note in the evidence section (R61) |
| The card's sections "What it is for" and "Where it came from and what it relates to" | Removed (R64, R68) |
| The card's "Populations", record-level "Settings" and "Outcomes measured" lines | Removed (R54, R64) |
| 045 D22 (the transferability line on the card) | Removed (R66) |
| `OptionDocumentOut` one per membership row, sorted by title; the document chips | One per document, evaluated first then quality, one meta line with `year` (R67) |
| `CELL_LIMIT` 6 | 4 (R60) |
| R45 and § Stop conditions ("a migration beyond this one revision") | One more revision: two new columns and the renames (R71) |
| § Constraints, Schema ("No other schema change") | The one revision of R71. **It runs on production without a re-extraction**: the finding tables' `population` → `unit` is a plain, reversible column rename with no version change on the finding records (owner, Q24: "Keep in this amendment."); the intervention record's v3 re-extracts options-scoping tasks only, on their next run. Rollback: `alembic downgrade -1` reverses the renames and drops the two columns; deploy the previous image |
| § Constraints, prompt hash guard | `interventions_records.py`, `iof_records.py`, `icf_records.py` and `finding_references.py` join the guard's file list (owner, Q24) |
| § Constraints, Prompts | Also: two folding prompts (new), `extract_interventions` v3, the place rule in the screen criteria, tagging context, `constrain` and `option_design` (a loop), the IOF/ICF word swap (no replay) (R69, R74, R75); the cluster prompt unchanged for examples |
| § Constraints, Public interface | Not additive: final 3 § 3 "Contract parts that change" |
| § Acceptance checks, M4 | Measured again on the replays (18P) and the live runs (R74) |
| § Acceptance checks, M6 ("adjacent-population evidence shown as *tried on*") | Retired (lead, Q9); rubric box 47 carries its replacement |
| § Known limits accepted | Added: final 3 § 7.3 |
| § Risk tier, rollback | `alembic downgrade -1` drops the two columns and reverses the renames; deploy the previous image (final 3 § 3) |
| § Spec changes | New items in final 3 § 3; wording to the owner |

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

0. **Applied 2026-09-28, wording accepted by the owner ("Looks good").**
   OS components (the diagram, the component table, § 6, the ⟨longlist
   depth⟩ composition) and ADR 0039 decision 8: **`theme` is a component of
   its own after `constrain`** (R28). § 6 longlist loses "then options into
   themes"; a new section describes `theme` (in: the included options; out:
   the themes; origin: ES characterise, modified; not a spine step). OS
   capability § Pipeline and gates: the stage order.
1. OS components § 6: reader grain; target size and hard ceiling in place of
   the formula; the corpus digest; the residual pass; variants on the card;
   suggestions at reader grain and the fold; no package minting by
   discovery; lever list v2; the baseline as
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
- **Public interface:** additive only — one new stage key on the run
  stream, `theme` (R28); `text_basis` on the chat citation facts (PA3);
  `variants`, `tried_on`,
  `runner_up_lever_type` on the option read models; a `tried_on` facet
  source on the longlist read model. OpenAPI regenerated by
  `make openapi-sync`.
- **Prompts (lead-authored, hash-pinned):** six revisions are planned,
  with new version names and recorded diffs: `task_agent_scoping_v4`,
  `longlist_suggest_v2`, `extract_interventions_v2`, `longlist_cluster_v2`,
  `lever_typing_v2`, `constrain_v2`. The theme prompt and the option design
  prompt are open too and change only on a finding from a round (R27). A
  prompt can go through several rounds; the version name changes once for
  the slice and each round's diff is recorded. The Evidence search prompts
  and the longlist verbs prompt keep their hashes.
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
- **The list shows no themes for a short time** (from the end of
  `longlist` to the end of `theme`; estimate 2 to 3 minutes). Holding the
  Result on the baseline until `theme` ends changes the rule for "a
  longlist exists"; recorded for task 3 (R28).
- **Themes go out of date after a user's exclusion**, as today. `theme` can
  run alone, so task 3's update in place can run it again.
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
without ingest (R13); a stage's loop does not pass its measures on the
tuning set after five rounds (R26: stop and report the read-backs); scope would grow into task 3; the budget is
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
  - items 5, 8: the distinct call receives every option; `theme` runs after
    `constrain` and receives the included options only; themes contain no
    excluded or merged option; `longlist` writes no theme and `constrain`
    has no theme code; a failed `theme` step ends the walk `degraded` with
    the verdicts stored; the run stream carries the `theme` stage; the
    registry, the harness graph and the plan mapping know `theme`.
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
- **The staged check (R12, as amended by R24–R26):** stage 1 below is the
  work loop of the build, not one run at the end. Each prompt stage is
  tuned on the tuning set and then read once on the check set. A figure
  from the check set is reported as it is; the prompts are not tuned on it.
- **The stages:**
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
