# Task contract: 045-scoping-longlist

One implementation slice: the second of the five options-scoping build tasks
(PR #69 "Task 2 — the longlist"). It lands the longlist walk that runs when
the user confirms the plan against the baseline: retrieval, the abstract
profile that reads every abstract for the interventions it names, the
clustering of those mentions into options and themes, the constraint checks,
and the longlist list view with its option card.

> **Status:** **drafted 2026-09-22 · lead.** Decisions D1–D18 below carry the
> lead's recommendation and wait for the owner's ruling, one by one. The
> decision-sheet rows scheduled for task 2 (A1, A2, A9, A10, A11, E1, E2, E4,
> F2, F3; `docs/tasks/035-options-scoping/checks/decision-sheet.md` line 15)
> are folded into those decisions and get their decision column filled when
> the owner rules. Rows E5, E6 and F13 are routed to task 3 (D17).
> Contract approved (before planning): _pending · owner_ ·
> Contract-stage adversarial review: _pending (after approval)_ ·
> Plan approved (before implementation): _pending_ ·
> ADR: _0039 (drafted at step 4)_.
>
> **Branching:** `task/045-scoping-longlist` from `feat/options-scoping` after
> `dev` was merged in (PR #81, Langfuse cost accuracy, 2026-09-22). PR target:
> `feat/options-scoping`, merge commit (not squash), per PR #69.
>
> **Prior decisions this slice builds on** (context, not targets): ADR 0037
> and the 044 contract (the task kind, `task_link`, the scoping plan, the
> baseline, the gate, the Task Agent turn projection); the sixteen
> decision-sheet rows ruled 2026-09-09, of which A4 (linked findings read
> across), A6 (`task_link`), A7 (inherited documents: no column, re-screen
> mandatory, classify and appraise read from the pinned run), A8 (duplicate
> documents: count by DOI where present, issue #75), C1 (the evidence
> restriction is the search directive at retrieval; no set-aside step), C4
> (several intent records per plan; one document row per task) and C5 (caps
> withdrawn) bind the longlist directly; concept rulings 4, 5, 8, 11, 12, 15,
> 19, 20, 22, 23, 31, 33, 35, 36, 39, 43, 44, 49 and 50. The task number is a
> reservation id.

## Goal

After the user confirms the plan against the baseline, the run builds the
**longlist**: every screened-in document's abstract is read for the
interventions it names, the mentions are clustered into options and the
options into themes, the plan's requirement constraints are checked, and the
Result tab opens on the longlist. Each option shows what it is, what it is
for, where it came from and what the evidence base holds so far. Nothing is
assessed and no report is written (ruling 50). The user can exclude an option,
include it again, and add one of their own. The shortlist is task 3.

Ten numbered deliverables, one numbering used by the rubric, the plan and the
ADR:

1. **Start the longlist.** "Confirm plan and build longlist" starts the
   longlist walk from both of its surfaces: the gate option in the Task
   Agent thread (check-in `baseline_confirm`, option `confirm_plan`) and the
   plan document's action after a plan change (`POST .../plan/confirm-baseline`).
   Today both record the decision and end (044 D12). After this slice both
   record the decision and open a **second walk** on the confirmed plan
   version: a new `capability_run`, its own intent record (`purpose =
   longlist`, `plan_id` = the confirmed version), the chain in deliverable 2.
   The walk does not pause: the second structural gate ("Assess these N") is
   task 3. It ends `succeeded` or `degraded` and the Result opens on the
   longlist. "Search further" stays refused honestly (044 D10). (D1)
2. **The pool and the chain.** The longlist chain is `acquire → screen →
   classify → appraise → ingest → extract(abstract) → longlist → constrain`
   (OS components § named compositions, without `shortlist`). The pool is
   the union of three sets, all screened under the longlist intent record:
   the documents the baseline walk acquired, the **inherited documents** of
   every linked Evidence search task (the document part of `inherit`,
   deferred from 044 D4: a `task_source_snapshot` row per document with
   origin `inherited`, pointing at the same content-addressed snapshot), and
   the new acquisition. The acquire is intent-driven: the plan compiles an
   intervention-oriented intent ("what has been tried to change X for Y in
   Z"), not the baseline's status-quo intent, with the evidence restrictions
   as `ScopeConstraints` (044 D8). The acquisition target per backend is set
   by depth (D2). Inherited documents are re-screened (A7); their
   classification and appraisal are read from the linked task's pinned run
   through `task_link`, never copied (A7); documents that are new to the
   scoping task are classified and appraised as the ES does. Counting is by
   DOI where present (A8). The chain shows three progress beats in the Task
   Agent thread: retrieval counts, mentions clustered, constraints checked.
3. **The abstract profile.** `extract` gains an **abstract profile** that
   runs over **every screened-in document** of the longlist scope, with no
   `select` step (E1, F2, F3): a selection-free path in `extract`, not a
   second component. Per document it records the interventions the abstract
   names, each with a **role** (evaluated · described · recommended ·
   comparator · mentioned), its design features as stated, whether it is a
   bundle and of what; and per document the setting country (read from the
   abstract text, never from publication metadata — ruling 43), the
   population, the outcome family and a design hint; a document that names
   no intervention says so. Non-evidence documents are profiled (a mention,
   never evidence — ruling 43). Records are memoised per (snapshot, profile
   version) like the other profiles. The record kind is D3.
4. **The longlist component.** The **unit of assignment is the mention**
   (ruling 31), or the extracted finding where a linked task ran the deep
   chain (A4, ruling 35). The shared two-stage clustering engine (ADR 0018)
   discovers **options** (name, one-sentence description, **specified
   design**, stated outcomes served) and assigns every unit against the
   fixed list, many-to-many, with a counted **unclustered** bucket, ceiling
   `clamp(ceil(N/4), 8, 40)` (E4). Then a second pass groups options into
   generated **themes**, each with a one-line "what it does" (ruling 11), and
   a typing pass gives each option one **primary lever type** from the
   curated list of about ten, any secondary types, and an **ambition tag**
   with a one-line justification carried as a tier-4 reasoning claim (ruling
   20). A bundle becomes a **package** with *part of* links to its
   constituents (ruling 15). Per option the deterministic **coverage** is the
   source-quality profile: mentioning documents by evidence type and quality
   tier (Unknown and Non-evidence as their own buckets), by role, countries,
   populations, outcomes measured — never "how sure" (ruling 33). Entrants
   without documents — the linked report's interventions labelled *from your
   evidence search* (ruling 22) and options the user adds — enter the same
   funnel through the engine's **assign mode** (E4): the supplied list is
   assigned against, so an entrant gains the mentions the corpus holds and
   otherwise stands with zero documents. (D4, D5, D6, D7, D8)
5. **Constrain.** Every option is judged against the plan's **requirement**
   constraints (`checked_at = longlist`, validated since 044 and read for the
   first time here) and the three default screens (relevant to the stated
   outcomes · distinct · within scope), on its specified design and coverage,
   never on analysis; each exclusion names the constraint it broke; thin
   evidence never excludes; the *distinct* screen never excludes a variant
   or a *part of* relation (ruling 36). Every **preference** constraint gets
   a labelled **reasoned guess** per option (capped wording, a flag and a
   user-requested sort, never a screen — trust § Reasoned guesses). An
   **evidence restriction** never excludes an option (ruling 23); an option
   whose mentioning documents all fall outside the restriction is marked
   **no in-scope evidence** and stays included (ruling 49). (D9)
6. **Option records.** The option is a task-scoped entity with a stable id
   and a versioned specified design (ruling 44): tables `option`,
   `option_membership`, `option_relation`; the run-keyed `longlist_result`
   (themes, per-option coverage, constraint judgements, guesses, the
   unclustered count — the characterise pattern); `intervention_mention`
   (deliverable 3); `task_link.option_id` (044 D13). Declared once, in the
   ADR, for tasks 3–5. (D3, D10, D11)
7. **The longlist views.** The Result tab opens on the **longlist** once the
   walk has run (ruling 50); a view switch offers **Baseline · Longlist**,
   and **Report** marked *available after assessment*. The **list view**:
   a header line with the counts (options · themes · included · of them with
   no in-scope evidence · excluded); a **Show** filter (All · Included ·
   Excluded); theme sections, each with its one-line description and its
   count line, collapsible; option rows with the name, the one-sentence
   description, the outcomes served, the origin (*clustered from N
   documents* · *from your evidence search* · *added by you*), the state
   (*excluded: breaks "…"* · *no in-scope evidence*), and relations (*part
   of*); the "Do nothing" reference as a sentence with a link to the
   baseline; no sort (the sorts arrive with task 3). The **option card**
   (the option-before-assessment page): breadcrumb, title, actions
   (**Exclude** / **Include again**), then *What it is* (the specified
   design; the primary lever type and what it also touches; the ambition tag
   "as described, not measured", both marked as Policy Atlas's reasoning),
   *What it is for*, *What the evidence base holds so far* (the
   source-quality profile in prose, closing with "a mention is not support"),
   *Constraints and guesses*, *Where it came from and what it relates to*
   with **Show the documents**. **Add an option** is a small form on the
   list view (name and a sentence); the option enters as *added by you* and
   is assigned against the corpus (deliverable 4). Every direct action is
   logged as the user's turn in History (ruling 1). The grid view, the
   shortlist actions and the variant path are task 3 (D12, D13). Sources,
   Share and History are unchanged.
8. **The Task Agent around the longlist.** The plan step *Longlist* loses
   "Not in this release" and gains its blurb; the plan document's state line
   after the walk reads "Longlist built · N options"; the thread shows the
   three progress beats (code-authored, not model-written). While no walk is
   active the thread takes questions as it does today (the answer core over
   the task's terminal run — the longlist scope's documents). A plan change
   after the longlist marks the longlist *built from plan version N* and the
   plan document offers **Rebuild longlist**, a new longlist walk in which
   the engine's assign mode is seeded with the existing options, so option
   ids, user exclusions and user additions survive (D14). Chat instructions
   that add or exclude an option in words are task 3, with the shortlist
   verbs (D13).
9. **System records and API.** `GET /tasks/{id}/longlist` (themes, options,
   counts, states, the run it came from), `GET /tasks/{id}/options/{option_id}`
   (the card), `POST /tasks/{id}/options` (add by hand), `POST
   .../options/{option_id}/exclude` and `/include` (with the user's reason),
   the longlist walk's progress on the existing run stream; the
   confirm-baseline route and the gate option now return the opened walk.
   All additive; OpenAPI regenerated.
10. **Depth.** Depth sets the longlist's acquisition target per backend and
    nothing else in this slice (D2). Compute time is measured on the NEET
    question at both depths and reported; the plan shows a coarse band and
    promises no number (E16).

## Deliverable

A PR on `task/045-scoping-longlist` into `feat/options-scoping`: one alembic
migration (the option tables, `intervention_mention`, `task_link.option_id`),
the abstract profile, the longlist and constrain components, the longlist
walk and its start from the two confirm surfaces, the frontend views, tests,
`verification.md`, ADR 0039, the spec changes in § Spec changes, and the
decisions below quoted where they are applied.

## Terms

The 044 contract's § Terms applies (capability, Task Agent, plan, intent
record, Link, inherit, baseline, the gate, steer point, walk, depth, origin
tag, constraint kind, Your context, standing default). New here:

| Term | Meaning |
|---|---|
| **longlist** | Both the artefact (the options grouped by theme with their states) and the component that clusters mentions into options (OS components § 6). The walk that builds it is the **longlist walk**. |
| **longlist scope** | The intent record with `purpose = longlist` the longlist walk runs under; its `plan_id` is the confirmed plan version. Screening, the abstract profile, the option records and coverage are keyed to it. |
| **mention** | One intervention an abstract names, with its role and stated design features: a row of `intervention_mention`, the abstract profile's record (deliverable 3). The unit `longlist` assigns. Not a finding of effect. |
| **role** | What the abstract does with the intervention: evaluated · described · recommended · comparator · mentioned (check 2). Comparator mentions never count as membership. |
| **option** | A task-scoped row: name, one-sentence description, specified design (versioned), stated outcomes served, primary and secondary lever types, ambition tag, origin, state. Ruling 44's durable identity. Not a document, not a theme. |
| **specified design** | The option's defining features as the longlist states them (offer, obligation, delivery point …). Support binds to it (ruling 36). Version 1 in this slice; a design edit is task 3's variant path. |
| **theme** | A generated grouping of options in the problem's own words, run-local like characterise's themes (ruling 11). Never earns a shortlist place. |
| **lever type** | One of about ten curated, versioned, domain-agnostic types (regulate · subsidise · tax or charge · inform · provide a service · enforce existing powers · devolve · change who runs the system …). Each option has one primary; the list is a versioned Python constant (D8). "Lever family" never appears user-facing. |
| **ambition tag** | Do minimum · incremental · structural, per option, with a one-line justification, a tier-4 reasoning claim "as described, not measured" (ruling 20). |
| **assign mode** | The clustering engine's second stage run against a supplied option list without discovery (E4). Used for entrants and for rebuilds. |
| **unclustered** | The engine's counted bucket of mentions assigned to no option; shown as a number, never hidden. |
| **source-quality profile** | An option's coverage: mentioning documents by evidence type, appraisal tier, role, country, population and outcome measured. Display and a later sort, never "how sure" (ruling 33). |
| **entrant** | An option that did not come from clustering: *from your evidence search* (the linked report's interventions) or *added by you*. Enters the funnel through assign mode. |
| **constrain** | The component that judges every option against the requirement constraints and the three default screens and writes the reasoned guesses (OS components § 7). |
| **default screens** | Three screens every option faces: relevant to the stated outcomes · distinct · within scope. Cited like any constraint. |
| **no in-scope evidence** | A condition, not a state: the option is included, and none of its mentioning documents pass the plan's evidence restriction (ruling 23, 49). |
| **reasoned guess** | Per preference constraint and option, a capped tier-4 claim ("cost: likely low, a guess rather than evidence"); a flag, never a screen or a shortlist input. |
| **package** | An option that is a bundle; its constituents are linked *part of* (ruling 15). |
| **list view · option card** | The two longlist surfaces this slice builds; the grid view and the shortlist view are task 3. |
| **progress beat** | A code-authored line the walk posts in the Task Agent thread at a stage boundary (retrieval · clustering · constraints). |

## Read first

- [OS capability](../../specs/capabilities/options-scoping/capability.md) —
  § Depths and modes (longlist depth), § Pipeline and gates (Longlist,
  Screening is a pipeline stage, Three kinds of constraint), § Output
  structure (Longlist), § Product surface, § Open decisions (open questions
  4, 5, 7).
- [OS components](../../specs/capabilities/options-scoping/components.md) —
  § 0 inherit (the document part), § 2–5 and extract(abstract), § 6 longlist,
  § 7 constrain, § Interface rulings 1–4, ⟨longlist depth⟩ composition.
- [OS trust](../../specs/capabilities/options-scoping/trust.md) — § The
  principle, § Reasoned guesses, § Screening and shortlisting, § What is
  structurally impossible.
- [ES components](../../specs/capabilities/evidence-search/components.md) —
  § 2 screen, § 5 characterise (the two machines the longlist reuses), § 7
  extract (the profile mechanism), § 8 group (the shared engine).
- [data-model](../../specs/system/data-model.md) — § Corpus & source
  snapshots, § Links between tasks, the option entity declared by ruling 44.
- [plan-as-object](../../specs/system/plan-as-object.md) — § Source /
  evidence policy (the evidence restriction).
- [web-api](../../specs/system/web-api.md) — § Runs, § Check-ins, § Plan
  (confirm-baseline).
- `docs/tasks/044-scoping-shell-baseline/contract.md` (the pattern
  precedent; its § Terms) and `verification.md` § Deferred work.
- `docs/tasks/035-options-scoping/checks/` — check 2 (roles and the abstract
  profile), check 3 (option-grain clustering: 827 mentions from 295
  documents → 29 options, residual 26 %; lever typing; the assign mode and
  ceiling of run 3), check 5 (the longlist stage costs about a minute; the
  abstract profile over 351 documents ran 106 s at 8-way fan-out), the
  decision sheet's task-2 rows.
- The boards `Longlist`, `OptionCard`, `Main` (grid, task 3 — for the
  vocabulary only) under `docs/specs/sources/options-scoping/boards/` —
  product intent only; every figure is a placeholder; rulings win.
- `docs/deferred.md` § Options scoping shell and baseline (task 044 seams),
  § Document identity across snapshots, § Capabilities (Search further,
  inherited document rows, `task_link.option_id`).

## Surface map

Rows marked **keep** must not change behaviour. File paths as built at
`feat/options-scoping` after the 2026-09-22 dev merge.

| # | Surface | Today | After this slice | Where |
|---|---|---|---|---|
| 1 | Gate option `confirm_plan` | falls through `_canonical_intent` to `("continue", None)`; the walk ends `succeeded` | a named branch: record the decision, end the baseline walk, open the longlist walk | `api/continuation.py` (`_offered_option`, `_persist_intent`), `runtime/steering.py` `baseline_confirm_options` |
| 1 | `POST /tasks/{id}/plan/confirm-baseline` | mints the confirmed plan version and stops | + opens the longlist walk on that version; response carries the run | `api/routers/task_agent.py` `confirm_baseline`, `api/routers/runs.py` `_dispatch_run` |
| 1 | Unattended mode | the gate passes on the standing default and the walk ends | the standing default continues into the longlist chain in the same walk (no second `capability_run`); recorded and flagged as today | `runtime/runner.py` `_resolve_baseline_gate_unattended` |
| 2 | `compose_scoping` | one chain, baseline | two chains chosen by the intent record's purpose: baseline (as today) and longlist; the registry keeps one `compose` per capability and the purpose is a compose argument | `runtime/scoping_plan.py`, `runtime/capability_registry.py` |
| 2 | Longlist intent and screening criteria | baseline only | `compile_longlist_intent(...)`; longlist screening criteria (target unit, Where, outcomes) | `runtime/scoping_plan.py` (`_scoping_directive_delta`, `_screening_criteria`), new `longlist_prompt.py` |
| 2 | inherit, document part | `linked_context` seeds the Task Agent only | + `inherit_documents(conn, task_id, scope)`: one `task_source_snapshot` row per linked document, origin `inherited`, before acquire; classification and appraisal of inherited rows read across through the pinned run | `runtime/inherit.py`; `api/readmodels/repository.py` |
| 2 | acquire · screen · classify · appraise · ingest | **keep** (ES components, parameterised) | unchanged code; the longlist scope's directives only. Classify and appraise skip rows whose inherited result exists (A7) — a filter in the scoping directive, not a change to the components | `evidence_search/sourcing/*`, `assess/*` |
| 3 | extract | requires a `selection_run_id` | + the abstract profile on a selection-free path over the scope's screened-in set; fail-closed profile name; memoised per (snapshot, `abstract_v1`) | `evidence_search/extract/extract.py`, new `abstract_profile.py`, `abstract_prompt.py`, `abstract_records.py` |
| 4 | longlist | does not exist | new component on the shared engine: discover (or assign) → theme → type; coverage; writes `option*` rows and `longlist_result` | new `policy_atlas/options_scoping/longlist/` (`longlist.py`, `longlist_prompt.py`, `lever_types.py`, `coverage.py`) |
| 5 | constrain | does not exist | new component: per-option fan-out judgement; writes judgements and guesses into `longlist_result` and the option state | new `options_scoping/constrain/` (`constrain.py`, `constrain_prompt.py`) |
| 6 | Schema | `task_link` has no `option_id`; no option tables | `option`, `option_membership`, `option_relation`, `longlist_result`, `intervention_mention`; `task_link.option_id` (nullable FK); `runs.component` check widened for `extract_abstract`, `longlist`, `constrain` | `core/schema.py`; one alembic revision |
| 7 | Result tab | baseline artefact when `template = baseline` | the longlist when a longlist walk has succeeded; view switch Baseline · Longlist · Report (unavailable) | `frontend/src/views/ArtefactView.tsx`, `views/lifecycle.ts` (`hasBaseline` → `resultView`), new `views/longlist/*` |
| 7 | Option card | does not exist | `/tasks/{id}/options/{option_id}` route in the app | new `views/longlist/OptionCard.tsx` |
| 7 | Sources · Share · History | **keep** | unchanged; Sources lists the longlist scope's documents like any run's; History shows the walk and the user's actions | — |
| 8 | Plan document | Longlist step "Not in this release"; state `confirmed` | step blurb; states `longlist_built` · `rebuild_or_keep`; action **Rebuild longlist** | `frontend/src/views/workspace/planStart.ts`, `PlanDocument.tsx`, `runtime/scoping_plan.py` `SCOPING_STEPS` |
| 8 | Task Agent thread | gate turns; progress for the baseline | + the three progress beats | `runtime/runner.py` progress path, `api/gate_turns.py` copy |
| 9 | API | — | the routes in deliverable 9; `OptionOut`, `LonglistOut` contracts | `api/routers/longlist.py` (new), `api/contract/longlist.py` (new) |
| — | ES chain, ES extract profiles, ES characterise, group | **keep** | byte-identical prompts and outputs; the engine gains a unit projection and an assign-mode entry point, behaviour-preserving for its two callers (existing tests) | `evidence_search/clustering_engine.py` |
| — | Prompt guard | name-based; `group_clustering.py` unguarded | every new prompt module is named `*_prompt.py` so the guard pins it; the guard's name rule is unchanged (the recorded 044 gap stays a gap for the old modules) | `scripts/prompt_hashes.json` |
| — | Generated | via `make openapi-sync` only | additive | `frontend/openapi.json`, `frontend/src/api/gen/types.ts` |

## Decisions for the owner (lead recommendation in bold)

- **D1 — the longlist is a second walk.** A new `capability_run` on the
  confirmed plan version with its own `purpose = longlist` intent record;
  started from both confirm surfaces; ends `succeeded`; no pause. **Accept.**
  *Rejected:* continuing the baseline walk (it has ended by the time the
  plan document's confirm is pressed, and the gate ends it by design — 044
  D12, C1). *In unattended mode only,* the baseline walk continues into the
  longlist chain, because no user decision ends it (044 A9).
- **D2 — the longlist's acquisition target per backend, by depth.** The
  baseline used 20 · 10 per backend. The longlist needs breadth: check 3
  built 29 options from 295 documents and 20 from 59. **Standard 50 per
  backend, rapid 25 per backend** (about 100 and 50 candidates over Overton
  and OpenAlex), measured on the NEET question in the build and reported;
  the owner sets the final numbers at the plan gate or after the
  measurement. Nothing else in the chain reads depth in this slice.
- **D3 — `intervention_mention` is its own record kind** (sheet A2, check 2
  C2-3, C2-5), a table with its own fingerprint domain and prompt version,
  joining the reference vocabulary; the fields in deliverable 3. **Accept,
  without the adoptability flag**: the flag was not validated (check 3's
  judge called two mention-path outputs non-options with it) — the
  discovery prompt carries a *not an option* bucket instead, counted with
  the unclustered. Codex wording adopted: mentions and roles are stored
  separately from the reviewable judgement about options.
- **D4 — the discovery ceiling `clamp(ceil(N/4), 8, 40)` and the assign
  mode** (sheet E4). **Accept**; open question 4's target longlist size stays
  open, the residual is shown as a count.
- **D5 — inherited findings as the unit where a linked task ran the deep
  chain** (A4, ruling 35). **Accept**: the engine gets one unit projection
  over two unit kinds (mention, finding); check 3 measured 128 findings → 22
  options, residual 6 %. A linked task without extraction contributes
  mentions like any document.
- **D6 — entrants without documents get no acquire of their own in this
  slice.** The spec gives every entrant "its own small acquire + screen +
  classify + appraise". **Defer that acquire to task 3**, where the targeted
  acquire for a thin document set already exists inside ⟨assess⟩; in this
  slice an entrant is assigned against the corpus in assign mode and
  otherwise stands with zero documents, its profile saying "no mentioning
  documents in this search". Spec § 2–5 sentence amended if accepted.
  *Reason:* a per-entrant walk is the most expensive item in the slice and
  the check never exercised it.
- **D7 — lever-type gap suggestions are task 3.** "Tax or charge and devolve
  have none on the longlist; want suggestions?" is a coverage conversation
  that belongs with the shortlist's gap messages. **Defer.** The longlist's
  top-down entrants in this slice are the linked report's interventions and
  the user's additions.
- **D8 — the lever-type list is a versioned Python constant** (open question
  5), about ten types, shown in the prompt and in the typing output. **Accept**
  as the simplest thing that behaves; a curated asset in the database waits
  until something edits it. Primary and secondary types are stored; the
  runner-up and its one-sentence reason are recorded in `longlist_result`
  only, never shown (sheet A10, Codex wording).
- **D9 — where "no in-scope evidence" comes from** now that C1 retired the
  set-aside (sheet E2). Retrieval already applies the restriction, so only
  inherited and baseline documents can fall outside it. **Compute the
  condition deterministically** from the document's publication country and
  year against the plan's `country_group` and years; language is not
  applied (044 C8). The screen stays relevance-only.
- **D10 — the option as a claim anchor** (sheet A1, check 6 F1). **Accept in
  the bounded form**: the ambition tag, the constraint judgements and the
  reasoned guesses are stored keyed by `(option_id, design_version)` in
  `longlist_result` and on the option row, so a changed design cannot inherit
  them (Codex wording). The block-annotation layer is not extended until a
  reader needs it (model only what behaves).
- **D11 — membership carries an assignment reason and a
  `design_feature_not_stated` flag; no stability marker** (sheet A11, check 2
  C2-3). A run-time stability marker needs a second clustering pass per run.
  **Accept the flag and the reason; reject the marker.** Denominators count
  every member and show the flagged ones ("12 documents, 3 of which do not
  state the obligation").
- **D12 — the grid view is task 3.** It is "for judging the set" and the
  board pairs it with the shortlist proposal. **Defer.** The list view and
  the option card are this slice.
- **D13 — user actions in this slice are direct actions on the views**
  (Exclude with a reason · Include again · Add an option), each logged as
  the user's turn; chat instructions in words ("exclude X", "add Y") arrive
  in task 3 with the shortlist verbs ("add to shortlist", "assess it") on
  one sorted-turn surface. The variant path (a design edit mints a variant
  with its own search) is task 3. **Accept.**
- **D14 — rebuild after a plan change keeps option ids.** A plan change
  after the longlist marks it *built from plan version N* and offers
  **Rebuild longlist**; the rebuild seeds assign mode with the existing
  options and discovers new ones, so ids, user exclusions and user additions
  survive; an option that gains no member in the rebuild is shown with zero
  documents, never deleted. **Accept.** Open question 7 (deltas, not
  restarts) stays open: a rebuild re-runs the whole chain. *Alternative:*
  defer rebuild to task 4 and refuse a plan change after the longlist.
- **D15 — the longlist is not a synthesise product.** No section writer,
  no artefact blocks; the Result reads `longlist_result` and the option
  rows through the read model (ruling 50: nothing is synthesised at the
  longlist stage beyond theme summaries and profiles, both produced by the
  engine passes). **Accept.**
- **D16 — duplicate documents (A8, issue #75).** Coverage counts by DOI where
  present at the point of counting; no schema or ingestion change. Applied
  as ruled.
- **D17 — routed to task 3:** the shortlist-quota guards (E5, rejected by
  Codex twice), the `shortlist_result` record (E6), the reading of "assess
  it" (F13). *Recorded, not decided here.*
- **D18 — starting the longlist's retrieval while the user reads the
  baseline.** **Stays deferred**: it makes two concurrent walks routine and
  the per-run fan-out has no cross-run bound (044 seams). Recorded with the
  measured longlist time so the owner can weigh it.

## Spec changes (applied only after the owner rules; quoted where applied)

1. OS components § 2–5: the per-entrant acquire moves to ⟨assess⟩ (D6).
2. OS components § 6 longlist: the record kinds, the ceiling, assign mode,
   the flag and reason on membership (D3, D4, D11); the 🟡 "unproven at option
   grain" marker closes, citing check 3.
3. OS components § 7 constrain and OS capability § Three kinds of
   constraint: "no in-scope evidence" computed from document metadata (D9).
4. data-model § Corpus: `intervention_mention`, the option tables,
   `task_link.option_id`, `task_source_snapshot.origin = inherited`.
5. web-api: the longlist routes; the two confirm surfaces open the walk.
6. plan-as-object § Thoroughness: the longlist's acquisition target per
   depth (D2).
7. Decision sheet rows A1, A2, A9, A10, A11, E1, E2, E4, F2, F3: decision
   column filled with the owner's words; E5, E6, F13 marked "task 3".
8. `docs/specs/log.md`: one line per change.

## Scope / Out of scope

- **In:** the surface-map rows; the migration; ADR 0039; the spec changes
  above; tests (§ Acceptance checks); `verification.md`; `docs/deferred.md`
  deltas (D6, D7, D12, D13, D18, open questions 4 and 7 as bounded here).
- **Out:** the shortlist, the proposal, the grid view, "Assess these N", the
  quota guards, `shortlist_result` (task 3); the variant path and chat
  instructions that edit the longlist (task 3); the sense-check branch, the
  Sources tab additions (By option, the Options column, the read-depth
  statuses) and export (task 4); the full run (task 5); lever-type gap
  suggestions (D7); per-entrant acquire (D6); "Search further" (044 D10);
  starting retrieval during the baseline pause (D18); the adoptability flag
  (D3); a run-time stability marker (D11); corpus-level document identity
  (#75); any change to the ES chain, the ES extract profiles, characterise
  or group behaviour; deep depth; the on-demand report from the longlist
  (ruling 50, deferred).

## Constraints & approval gates

Hard gates this slice touches — approval is this contract's sign-off:

- **Schema / data model:** five new tables (`option`, `option_membership`,
  `option_relation`, `longlist_result`, `intervention_mention`), one new
  nullable column (`task_link.option_id`), the widened `runs.component`
  check. No value rewrites. One alembic revision, reversible: the downgrade
  drops the tables and the column; it refuses while any `capability_run`
  row of a longlist walk exists (the 044 A5 pattern) and the remedy is the
  same operator script.
- **Runtime egress:** the longlist walk reaches Overton, OpenAlex and the
  inference route with task data — the same backends, transport and verb as
  the baseline walk; more calls per walk (the abstract profile over every
  screened-in document on the mini model, about 3,000 prompt tokens each;
  the clustering, theme, typing and constrain calls). No new host.
- **Public interface:** the routes in deliverable 9; the confirm-baseline
  response and the gate decision carry the opened walk; `PlanStep` blurbs.
  Everything additive.
- **Prompts:** five new lead-authored surfaces, hash-pinned: the abstract
  profile (`extract_abstract_v1`), option discovery and assignment
  (`longlist_cluster_v1`, the engine's two message builders), theme grouping
  (`longlist_theme_v1`), lever typing and ambition (`lever_typing_v1`),
  constrain (`constrain_v1`). The longlist intent text is compiled
  deterministically from the plan. Every existing pinned hash is unchanged;
  the ES discovery and assignment prompts in `group_clustering.py` are
  untouched (the engine's new entry points take their own message builders).
- **Dependencies, CI, auth, production config:** none. Tenancy (ADR 0033)
  and public read (ADR 0035) predicates are untouched: option rows are read
  through the task's own predicate; a link grants no read (044 A6).
- Generated files change only via `make openapi-sync`; `make drift-check`
  green.

## Public / private boundary

Contract, rubric, plan, ADR and `verification.md` are public-safe. Live-check
evidence: screenshots of the NEET longlist and one option card are
public-safe (the design reference; nothing on it is a finding); raw
acquired text, traces and credentials stay private. Recorded provider
fixtures follow the sanitized fixtures policy.

## Model route

OpenAI under the approved controls, behind the existing routing seam.
Prompt-bearing, lead-authored (§ Constraints). Model tiers: the abstract
profile and the assignment stage on the mini model (check 3's cost: about
1.6 M prompt tokens over 550 documents); discovery, theme grouping, lever
typing and constrain on the judgment model. Reused unchanged: acquire,
screen, classify, appraise, ingest, the clustering engine's two stages, the
answer core. Modified: `extract` (a selection-free path), the engine (a
unit projection and an assign-mode entry point).

## Disciplines binding this slice

- **Don't flatten status.** Open questions 4 (minting mechanics: target
  size) and 7 (deltas) stay open; the residual is a number the user sees.
- **Model only what behaves.** No stability marker, no adoptability flag,
  no annotation-layer anchor until a reader exists (D3, D10, D11).
- **Honest absence.** Zero-document entrants say so; the unclustered count
  is shown; "no in-scope evidence" names the restriction.
- **Generation is free, interpretation is labelled, assessment is
  grounded** (OS trust). The longlist asserts nothing about effect; the
  ambition tag and every guess carry their label; "how sure" appears
  nowhere.
- **Flag, don't drop.** Thin evidence never excludes; an exclusion keeps its
  reason and can be reversed.
- **Reuse, never mirror** (owner, 2026-09-07): the engine, extract's profile
  mechanism, characterise's coverage pattern, the ES spine.
- Deferred seams go to `docs/deferred.md`: D6, D7, D12, D13, D18; the
  per-run fan-out bound; the old unguarded prompt modules.

## Stop conditions

Halt and escalate when: a gate above needs more than this sign-off (a new
host, a non-additive API change, a second migration); the engine cannot take
a second unit kind without changing characterise's or group's outputs (the
existing tests are the fence); the abstract profile cannot run selection-free
without changing the IOF/ICF path; the longlist walk on the NEET question at
standard depth cannot finish in a time the owner will accept (report the
measurement, do not cut a stage); scope would grow into task 3; or the
turn/token budget is spent.

## Acceptance checks

- `make verify` green (okf-validate · test · typecheck · lint · build ·
  drift-check · prompt-guard).
- **Deterministic tests** (backend unless stated):
  - migration round-trip: upgrade, downgrade, upgrade; the downgrade refuses
    while a longlist `capability_run` exists; `task_link.option_id` is
    nullable and FK-checked to `option` with the task guard.
  - start (D1): `confirm_plan` at the gate records the decision, ends the
    baseline walk `succeeded` and opens a longlist walk whose intent record
    has `purpose = longlist` and the confirmed `plan_id`; the confirm-baseline
    route does the same on its new version; a second confirm while the
    longlist walk runs is 409 `run_active`; unattended continues in one walk
    with the standing default recorded and flagged; an ES task has no
    longlist chain (registry).
  - pool (deliverable 2): inherited rows are created once per linked
    document with origin `inherited` and the shared snapshot id; the
    longlist scope re-screens inherited, baseline and new documents in one
    generation; inherited classification and appraisal are read across from
    the pinned run and never inserted for the scoping task; a document
    present twice by DOI counts once in coverage (A8); evidence restrictions
    land on acquire as `ScopeConstraints`.
  - abstract profile (deliverable 3): runs over every screened-in document
    of the scope with no selection run; Non-evidence documents are profiled;
    a document naming no intervention is recorded as such; memoised per
    (snapshot, version); comparator mentions never become members; the
    IOF/ICF path is unchanged (existing tests).
  - longlist (deliverable 4): every mention is assigned or counted
    unclustered (code-enforced exhaustiveness); a document with three
    mentions can belong to three options; a bundle mints a package with
    *part of* rows; each option has exactly one primary lever type from the
    constant list and an ambition tag with a justification stored as a
    tier-4 claim; coverage buckets Unknown and Non-evidence separately;
    entrants are assigned in assign mode and survive with zero members;
    finding units from a linked deep task cluster alongside mentions (D5);
    the ceiling formula; characterise and group outputs unchanged (existing
    tests).
  - constrain (deliverable 5): a requirement breach excludes with the
    constraint named; the three default screens run and cite; *distinct*
    never excludes a *part of* row; thin evidence never excludes; every
    preference yields one capped guess per option; an option with every
    mentioning document outside the country group or years is marked no
    in-scope evidence and stays included; guesses never change state.
  - records (deliverable 6): judgements and guesses are keyed by
    `(option_id, design_version)`; a rebuild keeps option ids and user
    states (D14); a user exclusion carries its reason and is reversible.
  - API (deliverable 9): the four routes; org-scoped read in the ADR 0033
    style (a link grants no read of options); exclude/include/add write a
    History event as the user's turn; OpenAPI additive.
  - frontend (vitest): Result opens on the longlist after a longlist walk
    and on the baseline before; the view switch; the counts header; the
    Show filter; theme sections collapse; an option row shows origin, state,
    exclusion reason and relation; the option card renders its five sections
    and never the words "how sure"; Exclude asks for a reason; Add an option
    posts once; the plan document shows *built from plan version N* and
    Rebuild longlist after a plan change.
- **No AI eval in this slice.** Option quality is judge behaviour and goes
  to the eval slice. `verification.md` records three live longlists (NEET
  standard; NEET rapid; one linked start with inherited documents) with
  their compute times, the counts at each funnel stage (candidates ·
  screened in · mentions · options · unclustered · excluded), and a
  qualitative reading against the trust rules.
- **Live check (pinned scope, ~30 minutes):** local app, real egress.
  (a) From the 044 live-check state (a NEET scoping task at its baseline
  gate, started from a completed NEET Evidence search): Confirm plan and
  build longlist → the three beats appear, the walk runs, the Result opens
  on the longlist; compute time recorded. (b) Read the list: themes, an
  option *from your evidence search*, one excluded with its constraint, the
  Do nothing sentence. (c) Open one option card; Show the documents. (d)
  Exclude one option with a reason; Include it again; Add an option; History
  shows the three actions. (e) Change the plan (add a requirement) → the
  longlist is marked built from version N → Rebuild longlist → the excluded
  option keeps its state and the added one its id (second compute time).
  (f) One question in the thread about an option, answered with citations.
  No ES live run: the ES chain is untouched and the engine's two existing
  callers are pinned by tests.

## Verification evidence expected

Command tails; the migration round-trip output; the OpenAPI diff
(additive); the prompt-hash diff (five new entries, nothing else changed);
the three live longlists' funnel counts and compute times at both depths;
the abstract profile's token cost per document; live-check notes and
screenshots for (a)–(f); the spec diffs with quoted rulings; the decision
sheet's filled columns; the `docs/deferred.md` delta; known gaps.

## Risk tier & review focus

**Tier 4** — a migration with five new tables, runtime egress for a new walk
kind with a per-document fan-out, additive public API, five prompt surfaces:
ADR 0039 with a rollback plan, human-approved plan, adversarial review at
the contract and plan stages (`codex-rescue`, read-only briefs), the step-7
stack per the spine (contract verifier · `/code-review medium` · one
security lane scoped to the new routes and the option read predicate ·
`/simplify` · human deep review).

Rollback shape (ADR 0039 names the commands): quiesce the API; `alembic
downgrade -1` refuses while a longlist `capability_run` row exists (the 044
A5 pattern); the remedy is the existing operator script extended to
longlist walks; the downgrade drops the five tables and the column and
narrows the `runs.component` check; deploy the previous image.

Review focus: the ES chain, characterise and group byte-for-byte unchanged
in behaviour; the engine's two existing callers pinned; the abstract
profile never touches the IOF/ICF path; no option row is readable across a
link; a guess never excludes and never feeds any proposal; "how sure"
appears nowhere; every exclusion carries a constraint; comparator mentions
never count; the unclustered count is visible; the rebuild never deletes an
option; the additive-only OpenAPI diff.
