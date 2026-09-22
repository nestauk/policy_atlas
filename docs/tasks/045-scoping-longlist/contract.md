# Task contract: 045-scoping-longlist

One implementation slice: the second of the five options-scoping build tasks
(PR #69 "Task 2 — the longlist"). It lands the longlist walk that runs when
the user confirms the plan against the baseline: the model's own suggestions
and the user's own options, each with a mini evidence search; a broad
bottom-up search read by the intervention profile; the seeded clustering of
those records into options and themes; the constraint checks; and the
longlist views (list, reduced grid, option card) with the chat verbs that
edit them.

> **Status:** **drafted 2026-09-22 · lead; rulings D1–D21 taken by the owner
> in an interview the same day** (one by one; quoted below where they change a
> spec). The decision-sheet rows scheduled for task 2 (A1, A2, A9, A10, A11,
> E1, E2, E4, F2, F3; `docs/tasks/035-options-scoping/checks/decision-sheet.md`
> line 15) are folded into those rulings; rows E5, E6 and F13 wait for task 3
> (D17). **Owner review of the folded contract: _pending_.**
> Contract approved (before planning): _pending · owner_ ·
> Contract-stage adversarial review: _pending (after approval, owner's go)_ ·
> Plan approved (before implementation): _pending_ ·
> ADR: _0039 (drafted at step 4)_.
>
> **Branching:** `task/045-scoping-longlist` from `feat/options-scoping` at
> `6c19a1e1` (dev merged in: PR #81, Langfuse cost accuracy, 2026-09-22). PR
> target: `feat/options-scoping`, merge commit (not squash), per PR #69.
>
> **Prior decisions this slice builds on** (context, not targets): ADR 0037
> and the 044 contract (the task kind, `task_link`, the scoping plan, the
> baseline, the gate, the Task Agent turn projection); the sixteen
> decision-sheet rows ruled 2026-09-09, of which A4 (linked findings read
> across), A6 (`task_link`), A7 (inherited documents: no column, re-screen
> mandatory, classify and appraise read from the pinned run), A8 (duplicate
> documents: count by DOI where present, issue #75), C1 (the evidence
> restriction is the search directive at retrieval; no set-aside step), C4
> (several intent records per plan, purposes baseline · longlist · variant ·
> targeted; one document row per task) and C5 (caps withdrawn) bind the
> longlist directly; concept rulings 4, 5, 8, 11, 12, 15, 19, 20, 22, 23, 31,
> 33, 35, 36, 39, 43, 44, 49 and 50. The task number is a reservation id.

## Goal

After the user confirms the plan against the baseline, the run builds the
**longlist** both ways at once. Top-down: the model proposes options from the
plan and the baseline, the user's own options come in from the plan, and the
linked report's interventions come in through the link; each of these
entrants gets its own mini evidence search. Bottom-up: a broad search on a
PICO-shaped intent, over the new, baseline and inherited documents, read by
the intervention profile for the interventions each abstract covers. Seeded
clustering joins the two into options and themes; the plan's requirement
constraints are checked; the Result opens on the longlist. Each option shows
what it is, what it is for, where it came from and what the evidence base
holds so far. Nothing is assessed and no report is written (ruling 50). The
user adds, excludes and includes again in the Task Agent chat or with the
buttons. The shortlist is task 3.

Eleven numbered deliverables, one numbering used by the rubric, the plan and
the ADR:

1. **Start the longlist.** "Confirm plan and build longlist" starts the
   longlist walk from both of its surfaces: the gate option in the Task
   Agent thread (check-in `baseline_confirm`, option `confirm_plan`) and the
   plan document's action after a plan change (`POST .../plan/confirm-baseline`).
   Today both record the decision and end (044 D12). After this slice both
   record the decision and open a **second walk** on the confirmed plan
   version: a new `capability_run`, its own intent record (`purpose =
   longlist`, `plan_id` = the confirmed version), the chain in deliverable 3.
   The walk does not pause: the second structural gate ("Assess these N") is
   task 3. It ends `succeeded` or `degraded` and the Result opens on the
   longlist. In unattended mode the baseline walk continues into the
   longlist chain in the same walk, because no user decision ends it (044
   A9). "Search further" stays refused honestly (044 D10). (D1)
2. **The plan's new slot and the longlist intent.** The scoping plan gains
   **Options you already have in mind** (`your_options[]`, optional, the
   user's own words plus a design the Task Agent proposes back), asked once
   in the planning conversation (`task_agent_scoping_v3`) with its Edit
   action on the plan document (D19). The longlist intent is compiled
   deterministically from the plan, PICO-shaped without the C: the target
   unit (P), the intervention left open (I), the plan's outcomes (O), and
   the setting only when the user stated one as a requirement (S, optional —
   D21). **Where is not in the intent and not in the longlist's screening
   criteria** (D20): it is given to search-query generation as context ("the
   policy would apply in the United Kingdom; evidence from any country is in
   scope") so international implementations are found, and it returns at
   the baseline (as today) and at task 3's transferability working. Study
   geography is read from the abstract into every profile record (ruling 43)
   and shown as the card's countries line.
3. **The chain and the pool.** The longlist chain is: **suggest** (the
   model's own options, D7) → **entrant mini searches** (D6) in parallel
   with the **broad search** (acquire → screen → classify → appraise →
   ingest) → **intervention profile** over every screened-in document →
   **longlist** (seeded clustering) → **constrain**. The broad search's pool
   is the union of the baseline walk's documents, the **inherited
   documents** of every linked Evidence search task (the document part of
   `inherit`, deferred from 044 D4: a `task_source_snapshot` row per
   document with origin `inherited`, pointing at the same content-addressed
   snapshot), and the new acquisition at the depth's target per backend
   (D2), with the evidence restrictions as `ScopeConstraints` (044 D8).
   Inherited documents are re-screened (A7); their classification and
   appraisal are read from the linked task's pinned run through `task_link`,
   never copied (A7); new documents are classified and appraised as the ES
   does. Counting is by DOI where present (A8). The thread shows the
   progress beats: suggestions made, retrieval counts, abstracts read,
   options clustered, constraints checked.
4. **Suggestions and entrants, each with a mini evidence search.** At the
   start of the longlist step the judgment model is asked, from the plan
   (question, intended change, target unit, outcomes, Your context, the
   user's own options) and the baseline's sections, for its own **suggested
   options**, each with a name, a one-sentence description and a specified
   design: free, with the lever-type list as a breadth checklist, no quota
   per type, bounded at about ten (D7; owner: "free with the checklist").
   The **entrants** are these suggestions (*suggested by Policy Atlas*), the
   plan's own options (*added by you*), and the linked report's
   interventions (*from your evidence search*, ruling 22). Every entrant
   gets its own **mini evidence search** in the same walk (D6; owner: "we
   should have targeted acquire at the longlist stage … if we don't do
   top-down searches at the longlist stage we could omit options that the
   user might be interested in"): an intent record with `purpose =
   targeted` whose intent is the entrant's specified design, then acquire
   (a small target per backend, D2) → screen → classify → appraise → ingest
   → intervention profile; the entrant is a seed in the clustering and its
   records join the pool. Mini searches run as a bounded parallel fan-out.
   An entrant whose search finds nothing stands on the longlist with zero
   documents and says so.
5. **The intervention profile.** `extract` gains a third profile, the
   **intervention profile** (key `interventions`, version
   `intervention_profile_v1`), that runs over **every screened-in document**
   of the longlist scope and of each targeted scope, with no `select` step
   (E1, F2, F3): a selection-free path in `extract`, not a second component.
   Its table is **`intervention_profile_record`** (D3), on the findings
   pattern beside `intervention_outcome_finding` and
   `implementation_context_finding`: one row per intervention a document
   covers, with its **role** (evaluated · described · recommended ·
   comparator · mentioned — the five values stand), its stated design
   features, whether it is a bundle and of what, the quote anchor, and the
   shared reference columns (intervention, outcome, population, **setting**,
   study geography, study design); per document, whether it covers no
   intervention. Non-evidence documents are profiled (a mention, never
   evidence — ruling 43). Records join `finding_reference_union` and are
   memoised per (snapshot, profile version) through `source_extraction_record`
   like the other profiles. No adoptability flag (D3). "Mention" and
   "abstract profile" are not code names; the product says *covers* and
   *names* ("22 documents name this option, 11 evaluated it").
6. **The longlist component.** The **unit of assignment is the intervention
   profile record** (ruling 31), or the extracted IOF/ICF finding where a
   linked task ran the deep chain (D5, ruling 35), both read through the
   union view by one unit projection. The shared two-stage clustering engine
   (ADR 0018) discovers **options** (name, one-sentence description,
   **specified design**, stated outcomes served) and assigns every unit
   against the list, many-to-many, with a counted **unclustered** bucket and
   a counted **not an option** bucket, ceiling `clamp(ceil(N/4), 8, 40)`
   (D4; open question 4's target size stays open). The run is **seeded**:
   the entrants of deliverable 4 (and, on a rebuild, the existing options)
   are supplied as options to assign against, and discovery adds new ones
   (the engine's assign mode plus discovery, E4). A second pass groups
   options into generated **themes**, each with a one-line "what it does"
   (ruling 11). A typing pass gives each option one **primary lever type**
   from the versioned constant list, any secondary types, may answer **none
   fits** with a reason (counted and shown), and the **ambition tag** with a
   one-line justification carried as a tier-4 reasoning claim (ruling 20);
   the runner-up type and its reason are recorded in `longlist_result` only
   (D8). Every option records the taxonomy version it was typed under. A
   bundle becomes a **package** with *part of* links (ruling 15). Each
   membership row carries the assignment reason and a
   **`design_feature_not_stated`** flag; no stability marker (D11). Per
   option the deterministic **coverage** is the source-quality profile:
   documents by evidence type and quality tier (Unknown and Non-evidence as
   their own buckets), by role, countries, populations, settings, outcomes
   measured; flagged members counted and shown ("12 documents, 3 of which do
   not state the obligation") — never "how sure" (ruling 33).
7. **Constrain.** Every option is judged against the plan's **requirement**
   constraints (`checked_at = longlist`, validated since 044 and read for the
   first time here; a setting requirement is one of them — D21) and the three
   default screens (relevant to the stated outcomes · distinct · within
   scope), on its specified design and coverage, never on analysis; each
   exclusion names the constraint it broke; thin evidence never excludes;
   the *distinct* screen never excludes a *part of* relation (ruling 36).
   Every **preference** constraint gets a labelled **reasoned guess** per
   option (capped wording, a flag and a later sort, never a screen — trust §
   Reasoned guesses). An **evidence restriction** never excludes an option
   (ruling 23 stands — D9); an option none of whose documents pass the
   restriction's country group and years, read from publication metadata
   (the same fields retrieval filtered on; deterministic, no model call;
   language not applied, 044 C8), is marked **no in-scope evidence**, stays
   included (ruling 49), and its card names the restriction.
8. **Option records.** The option is a task-scoped entity with a stable id
   and a versioned specified design (ruling 44): tables `option`,
   `option_membership`, `option_relation`; the run-keyed `longlist_result`
   (themes, per-option coverage, constraint judgements, guesses, the
   runner-up types, the unclustered and not-an-option counts — the
   characterise pattern); `intervention_profile_record` (deliverable 5);
   `task_link.option_id` (044 D13). Option-level judgements are stored on
   the option row and in `longlist_result`, keyed `(option_id,
   design_version)`, so a changed design cannot inherit them; the
   annotation layer is extended only when a reader needs it (D10). Declared
   once, in the ADR, for tasks 3–5.
9. **The longlist views.** The Result tab opens on the **longlist** once the
   walk has run (ruling 50); a view switch offers **Baseline · Longlist**,
   and **Report** marked *available after assessment*. The **list view**: a
   header line with the counts (options · themes · included · of them with
   no in-scope evidence · excluded · unclustered records); a **Show** filter
   (All · Included · Excluded) and a **setting facet**; theme sections, each
   with its one-line description and its count line, collapsible; option
   rows with the name, the one-sentence description, the outcomes served,
   the origin (*clustered from N documents* · *suggested by Policy Atlas* ·
   *from your evidence search* · *added by you*), the state (*excluded:
   breaks "…"* · *no in-scope evidence*), and relations (*part of*); the "Do
   nothing" reference as a sentence with a link to the baseline; no sort
   (the sorts arrive with task 3). The **reduced grid** (D12): rows the
   lever types, columns the ambition bands, tiles that open the option and
   carry the excluded and no-in-scope-evidence states, empty rows saying "no
   option of this type on the longlist"; no shortlist actions, no gap
   messages, no footer (task 3 extends it). The **option card** (D15,
   assembled, no writer): breadcrumb, title, actions (**Exclude** / **Include
   again**), then *What it is* (the specified design; the primary lever type
   and what it also touches; the ambition tag "as described, not measured",
   both marked as Policy Atlas's reasoning), *What it is for*, *What the
   evidence base holds so far* (the source-quality profile turned into
   sentences by a template, closing with "a mention is not support"),
   *Constraints and guesses*, *Where it came from and what it relates to*
   with **Show the documents**; the words "how sure" appear nowhere. An
   on-demand written summary is a recorded seam (D15). Every direct action
   is logged as the user's turn in History (ruling 1). Sources, Share and
   History are otherwise unchanged.
10. **The Task Agent around the longlist** (D13; owner: "chat verbs in task
    2, buttons as the second way"). While the longlist exists and no walk is
    active, a Task Agent turn is sorted by a lead-authored surface
    (`longlist_verbs_v1`, the 044 gate sort's pattern) into **question ·
    add an option · exclude · include again · other**: a question goes to
    the answer core over the longlist scope; a verb is confirmed in the
    thread before it is applied (a verb is never inferred); *add* mints the
    option as *added by you* with the design the agent proposes back and
    runs its mini evidence search (a short walk, `purpose = targeted`, then
    assign against the existing options); *exclude* takes the user's reason;
    each applied verb writes the same state the buttons write and a History
    event as the user's turn. The plan step *Longlist* loses "Not in this
    release" and gains its blurb; the plan document's state line after the
    walk reads "Longlist built · N options"; the thread shows the progress
    beats (code-authored). A plan change after the longlist marks it *built
    from plan version N* and the plan document offers **Rebuild longlist**
    (D14): a new longlist walk seeded with the existing options, so option
    ids, user exclusions and user additions survive; an option that gains no
    member in the rebuild stays with zero documents, never deleted; entrant
    mini searches re-run only for entrants that are new. Open question 7
    (deltas, not restarts) stays open: a rebuild re-runs the whole chain.
11. **System records and API.** `GET /tasks/{id}/longlist` (themes, options,
    counts, states, the run it came from), `GET /tasks/{id}/options/{option_id}`
    (the card), `POST /tasks/{id}/options` (add by hand — the button's path,
    same handler as the chat verb), `POST .../options/{option_id}/exclude`
    and `/include` (with the user's reason), the longlist walk's progress on
    the existing run stream; the confirm-baseline route and the gate option
    now return the opened walk; `your_options` on the plan read and patch
    bodies. All additive; OpenAPI regenerated.

## Deliverable

A PR on `task/045-scoping-longlist` into `feat/options-scoping`: one alembic
migration (the option tables, `intervention_profile_record`,
`task_link.option_id`), the intervention profile, the suggest, longlist and
constrain components, the mini evidence search inside the walk, the longlist
walk and its start from the two confirm surfaces, the longlist verbs, the
frontend views, tests, `verification.md`, ADR 0039, the spec changes in
§ Spec changes, and the rulings below quoted where they are applied.

## Terms

The 044 contract's § Terms applies (capability, Task Agent, plan, intent
record, Link, inherit, baseline, the gate, steer point, walk, depth, origin
tag, constraint kind, Your context, standing default, gate sort, answer
core). New here:

| Term | Meaning |
|---|---|
| **longlist** | Both the artefact (the options grouped by theme with their states) and the component that clusters records into options (OS components § 6). The walk that builds it is the **longlist walk**. |
| **longlist scope** | The intent record with `purpose = longlist` the broad search runs under; its `plan_id` is the confirmed plan version. Screening, the intervention profile, the option records and coverage are keyed to it. |
| **targeted scope** | An intent record with `purpose = targeted` (decision C4) for one entrant's mini evidence search; its intent is the entrant's specified design. |
| **mini evidence search** | One entrant's own small chain inside the longlist walk: acquire (a small target per backend) → screen → classify → appraise → ingest → intervention profile, under a targeted scope. The spec's "own small acquire + screen + classify + appraise" (OS components § 2–5). Not an assessment. |
| **intervention profile** | The third `extract` profile (key `interventions`): for every screened-in document, the interventions its abstract covers, each with a role and its stated design. Owner naming 2026-09-22 (replaces "abstract profile"). |
| **`intervention_profile_record`** | The profile's table: one row per intervention a document covers. Owner naming 2026-09-22 (replaces "intervention mention"). The unit `longlist` assigns. Not a finding of effect. |
| **role** | What the abstract does with the intervention: **evaluated** (reports a study of its effect) · **described** (describes it without evaluating) · **recommended** (proposes it) · **comparator** (it is the comparison arm) · **mentioned** (named in passing). Comparator records never count as membership. Role sorts and describes; it never excludes. |
| **PICO-shaped intent** | The longlist intent: target unit (P), intervention open (I), outcomes (O), setting only when required (S); no comparison and no place (D20, D21). |
| **option** | A task-scoped row: name, one-sentence description, specified design (versioned), stated outcomes served, primary and secondary lever types, taxonomy version, ambition tag, origin, state. Ruling 44's durable identity. Not a document, not a theme. |
| **specified design** | The option's defining features as the longlist states them (offer, obligation, delivery point …). Support binds to it (ruling 36). Version 1 in this slice; a design edit is task 3's variant path. |
| **design feature** | One element of a specified design (for a youth guarantee: the offer within four months, the obligation to accept, sanctions). Two options can share a name and differ by one feature. |
| **`design_feature_not_stated`** | A flag on a membership row: the document covers the intervention but its abstract does not state the feature that defines this option. Counted and shown, never dropped (D11). |
| **theme** | A generated grouping of options in the problem's own words, run-local like characterise's themes (ruling 11). Never earns a shortlist place. |
| **lever type** | One of about ten curated, versioned, domain-agnostic instruments of the state (regulate · subsidise · tax or charge · inform · provide a service · enforce existing powers · devolve · change who runs the system …). One list for every domain (D8); each option has one primary; the list is a versioned Python constant. "Lever family" never appears user-facing. |
| **none fits** | The typing pass's answer when no lever type fits an option, with a reason; counted and shown so the list can be revised on evidence (D8). |
| **ambition tag** | Do minimum · incremental · structural, per option, with a one-line justification, a tier-4 reasoning claim "as described, not measured" (ruling 20). |
| **seeded clustering** | The clustering engine run with a supplied option list (the entrants; on a rebuild, the existing options) assigned against, plus discovery of new options (E4's assign mode plus discovery). |
| **unclustered · not an option** | The engine's two counted buckets: records assigned to no option; records the discovery judged not to describe an actionable option. Both shown as numbers, never hidden. |
| **source-quality profile** | An option's coverage: documents by evidence type, appraisal tier, role, country, population, setting and outcome measured, with flagged members shown. Display and a later sort, never "how sure" (ruling 33). |
| **entrant** | An option that did not come from bottom-up clustering: *suggested by Policy Atlas*, *added by you* (the plan slot or the chat verb) or *from your evidence search*. Gets a mini evidence search and is a seed in the clustering. |
| **suggest** | The first step of the longlist walk: the judgment model proposes options from the plan and the baseline, free, with the lever-type list as a breadth checklist (D7). |
| **Options you already have in mind** | The plan's new optional slot, `your_options[]`: options the user named at planning time, in their words, each with a design proposed back (D19). |
| **constrain** | The component that judges every option against the requirement constraints and the three default screens and writes the reasoned guesses (OS components § 7). |
| **default screens** | Three screens every option faces: relevant to the stated outcomes · distinct · within scope. Cited like any constraint. |
| **no in-scope evidence** | A condition, not a state: the option is included, and none of its documents pass the plan's evidence restriction, read from publication country and year (D9; rulings 23, 49). |
| **reasoned guess** | Per preference constraint and option, a capped tier-4 claim ("cost: likely low, a guess rather than evidence"); a flag, never a screen or a shortlist input. |
| **package** | An option that is a bundle; its constituents are linked *part of* (ruling 15). |
| **longlist verbs** | The sorted Task Agent turn kinds while the longlist exists and no walk is active: question · add an option · exclude · include again · other (D13). Surface `longlist_verbs_v1`. |
| **list view · reduced grid · option card** | The three longlist surfaces this slice builds. The grid is reduced: no shortlist state, actions, gap messages or footer (D12). |
| **progress beat** | A code-authored line the walk posts in the Task Agent thread at a stage boundary. |

## Read first

- [OS capability](../../specs/capabilities/options-scoping/capability.md) —
  § Depths and modes (longlist depth), § Pipeline and gates (Plan: target
  unit, Where, setting; Longlist; Screening is a pipeline stage; Three kinds
  of constraint), § Output structure (Longlist), § Product surface, § Open
  decisions (open questions 4, 5, 7).
- [OS components](../../specs/capabilities/options-scoping/components.md) —
  § 0 inherit (the document part), § 2–5 (the spine; entrants' own small
  acquire), § 6 longlist, § 7 constrain, § Interface rulings 1–4, ⟨longlist
  depth⟩ composition.
- [OS trust](../../specs/capabilities/options-scoping/trust.md) — § The
  principle, § Reasoned guesses, § Screening and shortlisting, § What is
  structurally impossible.
- [ES components](../../specs/capabilities/evidence-search/components.md) —
  § 1 acquire (query generation), § 2 screen, § 5 characterise, § 7 extract
  (the profile mechanism), § 8 group (the shared engine).
- [data-model](../../specs/system/data-model.md) — § Corpus & source
  snapshots, § Links between tasks, the option entity declared by ruling 44.
- [plan-as-object](../../specs/system/plan-as-object.md) — § What a plan
  contains, § Source / evidence policy.
- [web-api](../../specs/system/web-api.md) — § Runs, § Check-ins, § Plan.
- `docs/tasks/044-scoping-shell-baseline/contract.md` (the pattern
  precedent; its § Terms) and `verification.md` § Deferred work.
- `docs/tasks/035-options-scoping/checks/` — check 2 (roles; the profile
  field set), check 3 (option-grain clustering: 827 records from 295
  documents → 29 options, residual 26 %; 128 inherited findings → 22
  options, residual 6 %; lever typing; assign mode and the ceiling of run 3;
  all four zero-document entrants survived), check 5 (the longlist stage
  costs about a minute; the profile over 351 documents ran 106 s at 8-way
  fan-out; the fresh rapid path 676 s), the decision sheet's task-2 rows.
- The boards `Longlist`, `OptionCard`, `Main` under
  `docs/specs/sources/options-scoping/boards/` — product intent only; every
  figure is a placeholder; rulings win.
- `docs/deferred.md` § Options scoping shell and baseline (task 044 seams),
  § Document identity across snapshots, § Capabilities.

## Plan object (additions to the 044 § Plan object)

| Field | Content | Origin tag | Compiles to |
|---|---|---|---|
| `your_options[]` | `{text verbatim, design, turn_index}`: options the user named, optional, asked once (D19) | *added by you* | entrants with mini searches; seeds |
| `setting` (as a constraint) | unchanged: a requirement of kind `requirement` when stated; never a slot (044 D3 ruling) | — | the S of the longlist intent when present (D21); a `constrain` criterion |
| `steps[]` | Longlist blurb: "Suggest options, search widely, read every abstract for the interventions it covers, cluster them into options, apply your constraints." | — | display |

**Compile constants named here so nothing hides** (044 C8 pattern): the
longlist acquisition target per backend by depth (D2: standard 50, rapid 25,
owner sets after measurement); the entrant mini search target per backend
(10, measured); the suggestion bound (about ten); the mini search fan-out
width; the discovery ceiling formula; the lever-type list and its version.

## Surface map

Rows marked **keep** must not change behaviour. File paths as built at
`6c19a1e1`.

| # | Surface | Today | After this slice | Where |
|---|---|---|---|---|
| 1 | Gate option `confirm_plan` | falls through `_canonical_intent` to `("continue", None)`; the walk ends `succeeded` | a named branch: record the decision, end the baseline walk, open the longlist walk | `api/continuation.py` (`_offered_option`, `_persist_intent`), `runtime/steering.py` `baseline_confirm_options` |
| 1 | `POST /tasks/{id}/plan/confirm-baseline` | mints the confirmed plan version and stops | + opens the longlist walk on that version; response carries the run | `api/routers/task_agent.py` `confirm_baseline`, `api/routers/runs.py` `_dispatch_run` |
| 1 | Unattended mode | the gate passes on the standing default and the walk ends | the standing default continues into the longlist chain in the same walk; recorded and flagged as today | `runtime/runner.py` `_resolve_baseline_gate_unattended` |
| 2 | Scoping plan | no user options; steps say "Not in this release" | `your_options[]`; the Longlist blurb; `task_agent_scoping_v3` asks once; Edit action | `runtime/scoping_plan.py`, `runtime/task_agent_scoping_prompt.py`, `frontend/src/views/workspace/PlanDocument.tsx`, `planVocabulary.ts` |
| 2 | Longlist intent and screening criteria | baseline only (status quo; target unit + Where) | `compile_longlist_intent(...)` (PICO-shaped, no place); longlist screening criteria (target unit, outcomes; setting when required); Where passed to query generation as context | `runtime/scoping_plan.py` (`_scoping_directive_delta`, `_screening_criteria`), new `options_scoping/longlist_intent.py`; `evidence_search/sourcing/search_prompts.py` **unchanged** — context enters through the existing intent/context fields |
| 3 | `compose_scoping` | one chain, baseline | chains chosen by the intent record's purpose: baseline (as today), longlist, targeted (the mini search); the registry keeps one `compose` per capability and the purpose is a compose argument | `runtime/scoping_plan.py`, `runtime/capability_registry.py` |
| 3 | inherit, document part | `linked_context` seeds the Task Agent only | + `inherit_documents(conn, task_id, scope)`: one `task_source_snapshot` row per linked document, origin `inherited`, before acquire; classification and appraisal of inherited rows read across through the pinned run; the linked report's interventions as entrants | `runtime/inherit.py`; `api/readmodels/repository.py` |
| 3 | acquire · screen · classify · appraise · ingest | **keep** (ES components, parameterised) | unchanged code; the longlist and targeted scopes' directives only. Classify and appraise skip rows whose inherited result exists (A7) — a filter in the scoping directive, not a change to the components | `evidence_search/sourcing/*`, `assess/*` |
| 4 | suggest | does not exist | new step: one judgment-model call → entrants | new `options_scoping/suggest/` (`suggest.py`, `suggest_prompt.py`) |
| 4 | Mini evidence search | does not exist | the targeted chain as sub-steps of the longlist walk (`runs` rows on the same `capability_run`, each under its targeted scope), bounded fan-out | `runtime/runner.py` (a fan-out step), `runtime/scoping_plan.py` |
| 5 | extract | requires a `selection_run_id` | + the intervention profile on a selection-free path over the scope's screened-in set; fail-closed profile name; memoised per (snapshot, `intervention_profile_v1`) | `evidence_search/extract/extract.py`, new `intervention_profile.py`, `intervention_profile_prompt.py`, `intervention_profile_records.py` |
| 6 | longlist | does not exist | new component on the shared engine: seeded discover + assign → theme → type; coverage; writes `option*` rows and `longlist_result` | new `options_scoping/longlist/` (`longlist.py`, `longlist_cluster_prompt.py`, `longlist_theme_prompt.py`, `lever_typing_prompt.py`, `lever_types.py`, `coverage.py`) |
| 6 | Clustering engine | two callers (characterise, group) | + a unit projection over two record kinds and a seeded entry point; both existing callers behaviour-preserving (existing tests) | `evidence_search/clustering_engine.py` |
| 7 | constrain | does not exist | new component: per-option fan-out judgement; the deterministic in-scope check; writes judgements and guesses into `longlist_result` and the option state | new `options_scoping/constrain/` (`constrain.py`, `constrain_prompt.py`, `in_scope.py`) |
| 8 | Schema | `task_link` has no `option_id`; no option tables | `option`, `option_membership`, `option_relation`, `longlist_result`, `intervention_profile_record`; `task_link.option_id` (nullable FK); `runs.component` check widened for `suggest`, `extract_interventions`, `longlist`, `constrain` | `core/schema.py`; one alembic revision |
| 9 | Result tab | baseline artefact when `template = baseline` | the longlist when a longlist walk has succeeded; view switch Baseline · Longlist · Report (unavailable); list · grid | `frontend/src/views/ArtefactView.tsx`, `views/lifecycle.ts` (`hasBaseline` → `resultView`), new `views/longlist/*` (`LonglistView.tsx`, `LonglistGrid.tsx`) |
| 9 | Option card | does not exist | `/tasks/{id}/options/{option_id}` route in the app; assembled sections | new `views/longlist/OptionCard.tsx` |
| 9 | Sources · Share · History | **keep** | unchanged; Sources lists the scopes' documents like any run's; History shows the walk and the user's actions | — |
| 10 | Task Agent thread | gate turns; progress for the baseline | + the longlist verbs surface while no walk is active; the progress beats; the answer core over the longlist scope | `api/routers/task_agent.py` (`_dispatch_gate_turn` pattern), new `api/longlist_turns.py`, new `runtime/longlist_verbs_prompt.py`, `runtime/agent_backend.py` |
| 10 | Plan document | Longlist step "Not in this release"; state `confirmed` | step blurb; states `longlist_built` · `rebuild_or_keep`; action **Rebuild longlist** | `frontend/src/views/workspace/planStart.ts`, `PlanDocument.tsx`, `runtime/scoping_plan.py` `SCOPING_STEPS` |
| 11 | API | — | the routes in deliverable 11; `OptionOut`, `LonglistOut` contracts; `your_options` on the plan bodies | `api/routers/longlist.py` (new), `api/contract/longlist.py` (new), `api/contract/task_agent.py` |
| — | ES chain, ES extract profiles, ES characterise, group, ES search prompts | **keep** | byte-identical prompts and outputs | — |
| — | Prompt guard | name-based; `group_clustering.py` unguarded | every new prompt module is named `*_prompt.py` so the guard pins it; the guard's name rule is unchanged (the recorded 044 gap stays a gap for the old modules) | `scripts/prompt_hashes.json` |
| — | Generated | via `make openapi-sync` only | additive | `frontend/openapi.json`, `frontend/src/api/gen/types.ts` |

## Decisions (ruled by the owner, 2026-09-22)

- **D1 — the longlist is a second walk. Accepted.** A new `capability_run`
  on the confirmed plan version with its own `purpose = longlist` intent
  record; started from both confirm surfaces; ends `succeeded`; no pause.
  In unattended mode only, the baseline walk continues into the longlist
  chain (044 A9).
- **D2 — the acquisition targets. Accepted as a starting point** (owner:
  "start there, measure, I'll set it after"): the broad search at standard
  50 and rapid 25 per backend; the entrant mini search at 10 per backend;
  measured on the NEET question in the build and reported with the funnel
  counts; the owner sets the final numbers. Nothing else in the chain reads
  depth in this slice.
- **D3 — the intervention profile and its record. Accepted, renamed
  (owner).** The third `extract` profile is the **intervention profile**;
  its table is **`intervention_profile_record`** ("intervention mention"
  and "abstract profile" rejected as names: the first undersells a record
  whose role can be evaluated, the second names the reading depth, which
  ruling 16 makes a label a record carries). Not a subset of IOF or ICF: it
  shares their reference columns and lacks the effect (IOF) and the typed
  claim (ICF) that define each. The five roles stand. No adoptability flag
  (unvalidated in check 3); a counted *not an option* bucket instead.
- **D4 — the discovery ceiling `clamp(ceil(N/4), 8, 40)` and seeded
  assignment. Accepted;** the target longlist size (open question 4) stays
  open; the residual is a number the user sees.
- **D5 — inherited findings as units. Accepted:** one unit projection over
  two record kinds through the union view.
- **D6 — entrants get their own mini evidence search in this slice. The
  lead's deferral was rejected** (owner: "We should have targeted acquire
  at the longlist stage, that is the mini-evidence searches defined in the
  wireframes and specs. Mini-evidence searches are useful for 'top down'
  suggestions, i.e. interventions suggested by the LLM or by the human.
  Assessment is a separate step … if we don't do top-down searches at the
  longlist stage we could omit options that the user might be interested
  in"). The spec's sentence stands as written; deliverable 4 builds it.
- **D7 — the model's own suggestions, at the start of the longlist step,
  free with the lever-type checklist. Ruled** (owner: "it should be before
  clustering as well, we should ask for the LLMs suggestions at the start of
  the longlist step, so that we can do both bottom up and top down longlist
  generation"; on lever types: "free with the checklist"). No quota per
  type; about ten; each suggestion carries a specified design; lever type
  assigned afterwards like every option.
- **D8 — one versioned lever-type list for every domain. Accepted with two
  additions** (owner, after asking whether one list makes sense across
  domains): the list names the instrument the state uses, not the subject,
  which is what makes it domain-agnostic and what task 3's coverage
  denominator needs to be fixed; every option records the taxonomy version;
  the typing pass may answer *none fits* with a reason, counted and shown.
  A Python constant; the runner-up type and its reason in the record only,
  never shown (sheet A10, Codex wording).
- **D9 — "no in-scope evidence" is a deterministic check. Accepted, and
  ruling 23 stands** (owner, after asking why a restriction on evidence
  does not exclude an option: "the ruling stands, deterministic check").
  Publication country and year against the plan's country group and years;
  the same fields retrieval filtered on; language not applied; the option
  stays included; the card names the restriction. The screen stays
  relevance-only (sheet E2).
- **D10 — option-level judgements on the option row and in
  `longlist_result`, keyed `(option_id, design_version)`. Accepted;** the
  annotation layer is extended later if necessary (sheet A1, Codex wording).
- **D11 — membership rows carry the assignment reason and the
  `design_feature_not_stated` flag; no stability marker. Accepted.**
- **D12 — the reduced grid is in task 2. Revised** (the lead had deferred
  it; on the owner's challenge the argument was restated honestly as
  "build a reduced version, then extend it"; owner: "reduced grid in task
  2"): lever type × ambition, tiles open the option and show states, no
  shortlist actions, gap messages or footer; task 3 extends it.
- **D13 — chat verbs in task 2, buttons as the second way. Revised** (the
  lead had deferred the verbs; owner: "Yes, chat verbs in task 2, buttons
  as the second way"). The variant path stays task 3.
- **D14 — rebuild after a plan change, ids kept. Accepted** ("build it
  now, ids kept").
- **D15 — the longlist is not written by the synthesiser; the option card
  is assembled from the passes' outputs. Accepted, with a seam** (owner,
  after the latency table: "Assembled in task 2, on-demand summary as a
  seam"). The option's description and design come from the discovery
  stage; the card's evidence section is templated from counts; the
  constraint and guess reasons are `constrain`'s. An on-demand written
  summary at first open (about 10 to 20 s once per card) is recorded in
  `docs/deferred.md`; per-run written summaries (1 to 2 minutes wall in
  parallel, about 3 M tokens for 25 options) are not built before
  assessment.
- **D16 — count by DOI where present (A8, issue #75).** Applied as ruled.
- **D17 — routed to task 3:** the shortlist-quota guards (E5), the
  `shortlist_result` record (E6), the reading of "assess it" (F13). Owner:
  "those three wait for task 3".
- **D18 — retrieval during the baseline pause. Stays deferred.**
- **D19 — the plan gains "Options you already have in mind". Accepted**
  (a spec addition to plan-as-object and OS components § 1): optional, asked
  once, the user's words, a design proposed back; every named option is an
  entrant with its mini search in the longlist walk itself.
- **D20 — Where is not in the longlist's intent or screen. Accepted**
  (owner: "The Z that will be input by users is usually the UK, but the idea
  of options appraisal is also to bring in international evidence that might
  be transferable. Directly saying Z in the search scope may constrain the
  results too much"). Where goes to query generation as context; it stays in
  the baseline and returns at transferability; study geography is read from
  the abstract and shown on the card.
- **D21 — setting in the intent only as a stated requirement, recorded on
  every profile record, a facet on the list and a line on the card.
  Accepted** (owner: "not all users will have a setting requirement so it is
  optional"). PICO-shaped: target unit (P), intervention open (I), outcomes
  (O), setting optional (S), no comparison before assessment.

## Spec changes (applied with the owner's words quoted; a line each in `docs/specs/log.md`)

1. OS components § 1 plan and plan-as-object § What a plan contains: the
   optional slot *Options you already have in mind* (D19).
2. OS components § 2–5 and OS capability § Pipeline and gates (Plan): the
   longlist intent is PICO-shaped without Where; Where is context for query
   generation; setting is the optional S (D20, D21).
3. OS components § 6 longlist: the intervention profile and
   `intervention_profile_record` names (D3, replacing "abstract profile" and
   "mention" in the living specs, not in the frozen sources), the ceiling,
   seeded assignment, the flag and reason on membership (D4, D11), the
   suggestion step at the start (D7), the taxonomy version and *none fits*
   (D8); the 🟡 "unproven at option grain" marker closes, citing check 3.
4. OS components § 7 constrain and OS capability § Three kinds of
   constraint: "no in-scope evidence" computed from publication metadata
   (D9).
5. OS capability § Output structure (Longlist): the reduced grid before the
   proposal (D12); the assembled card and the on-demand summary seam (D15).
6. data-model § Corpus: `intervention_profile_record`, the option tables,
   `task_link.option_id`, `task_source_snapshot.origin = inherited`.
7. web-api: the longlist routes, the longlist verbs, the two confirm
   surfaces opening the walk, `your_options` on the plan bodies.
8. plan-as-object § Thoroughness: the longlist's and the mini search's
   acquisition targets per depth (D2).
9. vocabulary.md: intervention profile, `intervention_profile_record`,
   entrant, mini evidence search.
10. Decision sheet rows A1, A2, A9, A10, A11, E1, E2, E4, F2, F3: decision
    column filled with the owner's words; E5, E6, F13 marked "task 3". Row
    A9 (instance-of relation, a two-level longlist) is **not built**: the
    card's *What it is* shows the stated design features from the records,
    and a class-versus-implementation split waits for evidence from live
    use.

## Scope / Out of scope

- **In:** the surface-map rows; the migration; ADR 0039; the spec changes
  above; tests (§ Acceptance checks); `verification.md`; `docs/deferred.md`
  deltas (D15's seam, D18, open questions 4 and 7 as bounded here, sheet row
  A9).
- **Out:** the shortlist, the proposal, the grid's shortlist state and
  actions, "Assess these N", the quota guards, `shortlist_result` (task 3);
  the variant path (task 3); the sense-check branch, the Sources tab
  additions (By option, the Options column, the read-depth statuses) and
  export (task 4); the full run (task 5); the on-demand written summary
  (seam); "Search further" (044 D10); starting retrieval during the baseline
  pause (D18); the adoptability flag (D3); a run-time stability marker
  (D11); an instance-of relation (A9); corpus-level document identity (#75);
  any change to the ES chain, the ES extract profiles, characterise, group
  or the ES search prompts; deep depth; the on-demand report from the
  longlist (ruling 50, deferred).

## Constraints & approval gates

Hard gates this slice touches — approval is this contract's sign-off:

- **Schema / data model:** five new tables (`option`, `option_membership`,
  `option_relation`, `longlist_result`, `intervention_profile_record`), one
  new nullable column (`task_link.option_id`), the widened `runs.component`
  check. No value rewrites. One alembic revision, reversible: the downgrade
  drops the tables and the column; it refuses while any `capability_run`
  row of a longlist walk exists (the 044 A5 pattern) and the remedy is the
  same operator script.
- **Runtime egress:** the longlist walk reaches Overton, OpenAlex and the
  inference route with task data — the same backends, transport and verb as
  the baseline walk; more calls per walk: the broad search, one mini search
  per entrant (about ten suggestions plus the user's and the linked
  report's), the intervention profile over every screened-in document on
  the mini model (about 3,000 prompt tokens each), the suggest, clustering,
  theme, typing and constrain calls; the chat verb *add* opens a short
  targeted walk. No new host.
- **Public interface:** the routes in deliverable 11; the confirm-baseline
  response and the gate decision carry the opened walk; `your_options` on
  the plan bodies; `PlanStep` blurbs. Everything additive.
- **Prompts:** seven new lead-authored surfaces, hash-pinned, every module
  named `*_prompt.py`: the intervention profile
  (`intervention_profile_v1`), suggest (`longlist_suggest_v1`), option
  discovery and assignment (`longlist_cluster_v1`, the engine's two message
  builders), theme grouping (`longlist_theme_v1`), lever typing and
  ambition (`lever_typing_v1`), constrain (`constrain_v1`), the longlist
  verbs (`longlist_verbs_v1`); and one revision, `task_agent_scoping_v3`
  (the plan slot question), re-pinned with its diff recorded. The longlist
  and targeted intents are compiled deterministically from the plan and the
  entrant. Every other pinned hash is unchanged; the ES discovery and
  assignment prompts in `group_clustering.py` and the ES search prompts are
  untouched.
- **Dependencies, CI, auth, production config:** none. Tenancy (ADR 0033)
  and public read (ADR 0035) predicates are untouched: option rows are read
  through the task's own predicate; a link grants no read (044 A6).
- Generated files change only via `make openapi-sync`; `make drift-check`
  green.

## Public / private boundary

Contract, rubric, plan, ADR and `verification.md` are public-safe. Live-check
evidence: screenshots of the NEET longlist, grid and one option card are
public-safe (the design reference; nothing on it is a finding); raw
acquired text, traces and credentials stay private. Recorded provider
fixtures follow the sanitized fixtures policy.

## Model route

OpenAI under the approved controls, behind the existing routing seam.
Prompt-bearing, lead-authored (§ Constraints). Model tiers: the intervention
profile and the assignment stage on the mini model (check 3's cost: about
1.6 M prompt tokens over 550 documents); suggest, discovery, theme grouping,
lever typing, constrain and the longlist verbs sort on the judgment model.
Reused unchanged: acquire (with Where as context), screen, classify,
appraise, ingest, the clustering engine's two stages, the answer core, the
044 turn-sort pattern. Modified: `extract` (a selection-free path), the
engine (a unit projection and a seeded entry point).

## Disciplines binding this slice

- **Don't flatten status.** Open questions 4 (target size) and 7 (deltas)
  stay open; the residual is a number the user sees; sheet row A9 is
  recorded, not built.
- **Model only what behaves.** No stability marker, no adoptability flag,
  no annotation-layer anchor, no per-run written prose (D3, D10, D11, D15).
- **Honest absence.** Zero-document entrants say so; the unclustered and
  not-an-option counts are shown; "no in-scope evidence" names the
  restriction; *none fits* is counted.
- **Generation is free, interpretation is labelled, assessment is
  grounded** (OS trust). A suggestion needs no source; the ambition tag and
  every guess carry their label; "how sure" appears nowhere.
- **Flag, don't drop.** Thin evidence never excludes; an exclusion keeps its
  reason and can be reversed; a rebuild never deletes an option.
- **Substance is never silent.** A chat verb is confirmed before it is
  applied; every applied verb and every button writes History.
- **Reuse, never mirror** (owner, 2026-09-07): the engine, extract's profile
  mechanism, characterise's coverage pattern, the ES spine, the 044
  turn-sort pattern.
- Deferred seams go to `docs/deferred.md`: the on-demand summary; D18; the
  per-run fan-out bound; the old unguarded prompt modules; sheet row A9.

## Stop conditions

Halt and escalate when: a gate above needs more than this sign-off (a new
host, a non-additive API change, a second migration); the engine cannot take
a second unit kind or a seed list without changing characterise's or group's
outputs (the existing tests are the fence); the intervention profile cannot
run selection-free without changing the IOF/ICF path; the longlist walk on
the NEET question at rapid depth, mini searches included, cannot finish in a
time the owner will accept (report the measurement and the per-stage split,
do not cut a stage); scope would grow into task 3; or the turn/token budget
is spent.

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
  - plan and intent (D19–D21): `your_options` validates, is optional, keeps
    verbatim text and turn index, and has an Edit action; the compiled
    longlist intent contains the target unit and outcomes and never Where;
    it contains the setting only when a setting requirement exists; the
    longlist screening criteria carry no place; Where reaches query
    generation as context; the ES intent compile is unchanged.
  - pool (deliverable 3): inherited rows are created once per linked
    document with origin `inherited` and the shared snapshot id; the
    longlist scope re-screens inherited, baseline and new documents in one
    generation; inherited classification and appraisal are read across from
    the pinned run and never inserted for the scoping task; a document
    present twice by DOI counts once in coverage (A8); evidence restrictions
    land on acquire as `ScopeConstraints`; the progress beats are emitted at
    each boundary.
  - suggest and entrants (deliverable 4): the suggest step yields at most
    the bound, each with a design, labelled *suggested by Policy Atlas*;
    the plan's own options and the linked report's interventions become
    entrants with their labels; every entrant gets one targeted scope and
    one mini search chain under the same `capability_run`; the fan-out is
    bounded; an entrant whose search finds nothing survives with zero
    documents; the mini search target per backend is the constant.
  - intervention profile (deliverable 5): runs over every screened-in
    document of a scope with no selection run; Non-evidence documents are
    profiled; a document covering no intervention is recorded as such;
    memoised per (snapshot, version); comparator records never become
    members; setting and study geography are read from the abstract; the
    IOF/ICF path is unchanged (existing tests); the record joins the union
    view.
  - longlist (deliverable 6): every record is assigned, unclustered or not
    an option (code-enforced exhaustiveness); a document with three records
    can belong to three options; a bundle mints a package with *part of*
    rows; each option has exactly one primary lever type from the constant
    list or *none fits* with a reason, the taxonomy version, and an ambition
    tag with a justification stored as a tier-4 claim; the runner-up is in
    `longlist_result` and not on the read model; coverage buckets Unknown
    and Non-evidence separately, shows the role funnel, settings and
    countries, and counts flagged members; seeds are assigned against and
    survive with zero members; finding units from a linked deep task cluster
    alongside profile records (D5); the ceiling formula; characterise and
    group outputs unchanged (existing tests); membership rows carry a
    reason and the flag.
  - constrain (deliverable 7): a requirement breach excludes with the
    constraint named; a setting requirement is judged; the three default
    screens run and cite; *distinct* never excludes a *part of* row; thin
    evidence never excludes; every preference yields one capped guess per
    option; an option with every document outside the country group or
    years is marked no in-scope evidence and stays included, and the
    restriction is named; guesses never change state; the check is
    deterministic (no backend call).
  - records (deliverable 8): judgements and guesses are keyed by
    `(option_id, design_version)`; a rebuild keeps option ids and user
    states and never deletes an option; entrant searches re-run only for new
    entrants; a user exclusion carries its reason and is reversible.
  - longlist verbs (deliverable 10): a turn while the longlist exists and no
    walk is active is sorted; a question is answered over the longlist scope
    with citations; a verb is confirmed before it is applied and never
    inferred; *add* mints the option as *added by you*, proposes a design
    back, and opens a targeted walk that assigns against the existing
    options; *exclude* records the reason; the button routes and the verbs
    write the same state and one History event each; a turn while a walk
    runs is 409 `run_active`; an ES task's turns are unchanged.
  - API (deliverable 11): the routes; org-scoped read in the ADR 0033 style
    (a link grants no read of options); OpenAPI additive.
  - frontend (vitest): Result opens on the longlist after a longlist walk
    and on the baseline before; the view switch; the counts header; the
    Show filter and the setting facet; theme sections collapse; an option
    row shows origin, state, exclusion reason and relation; the reduced grid
    lays tiles by lever type and ambition, shows states, and has no
    shortlist action; the option card renders its five sections, the
    countries and setting lines, and never the words "how sure"; Exclude
    asks for a reason; Add an option posts once; the plan document shows the
    new slot with Edit, "Longlist built · N options", and *built from plan
    version N* with Rebuild longlist after a plan change; the thread renders
    a confirmed verb and the progress beats.
- **No AI eval in this slice.** Option quality is judge behaviour and goes
  to the eval slice. `verification.md` records three live longlists (NEET
  standard; NEET rapid; one linked start with inherited documents and a
  user option in the plan) with their compute times split by stage (suggest
  · mini searches · broad search · profile · clustering · constrain), the
  counts at each funnel stage (candidates · screened in · records · options ·
  unclustered · not an option · excluded · none fits), the countries on the
  NEET cards (the international-evidence check for D20), and a qualitative
  reading against the trust rules.
- **Live check (pinned scope, ~40 minutes):** local app, real egress.
  (a) New NEET scoping task started from the completed NEET Evidence
  search; in planning, name one option of your own; confirm; the baseline
  builds (as in 044). (b) Confirm plan and build longlist → the beats
  appear, the walk runs, the Result opens on the longlist; compute time and
  stage split recorded. (c) Read the list: themes, an option *suggested by
  Policy Atlas*, the one *added by you* with its mini search's documents,
  one *from your evidence search*, one excluded with its constraint, the Do
  nothing sentence, the setting facet; countries on the cards include
  non-UK implementations. (d) Open the grid; open one option card; Show the
  documents. (e) In the thread: "exclude the sanctions option, we can't do
  that" → confirmed → excluded with the reason; Include again by button;
  "add a youth mentoring scheme" → design proposed back → confirmed → the
  targeted walk runs → the option appears *added by you*; History shows the
  three actions. (f) Change the plan (add a requirement) → the longlist is
  marked built from version N → Rebuild longlist → the excluded option keeps
  its state and the added one its id (second compute time). (g) One
  question in the thread about an option, answered with citations. No ES
  live run: the ES chain is untouched and the engine's two existing callers
  are pinned by tests.

## Verification evidence expected

Command tails; the migration round-trip output; the OpenAPI diff
(additive); the prompt-hash diff (seven new entries, one re-pin, nothing
else changed); the three live longlists' funnel counts and stage-split
compute times at both depths; the intervention profile's token cost per
document and the mini search cost per entrant; live-check notes and
screenshots for (a)–(g); the spec diffs with quoted rulings; the decision
sheet's filled columns; the `docs/deferred.md` delta; known gaps.

## Risk tier & review focus

**Tier 4** — a migration with five new tables, runtime egress for a new walk
kind with two fan-outs (per document and per entrant), additive public API,
seven prompt surfaces and one revision: ADR 0039 with a rollback plan,
human-approved plan, adversarial review at the contract and plan stages
(`codex-rescue`, read-only briefs, on the owner's go), the step-7 stack per
the spine (contract verifier · `/code-review medium` · one security lane
scoped to the new routes, the longlist verbs and the option read predicate ·
`/simplify` · human deep review).

Rollback shape (ADR 0039 names the commands): quiesce the API; `alembic
downgrade -1` refuses while a longlist `capability_run` row exists (the 044
A5 pattern); the remedy is the existing operator script extended to
longlist walks; the downgrade drops the five tables and the column and
narrows the `runs.component` check; deploy the previous image.

Review focus: the ES chain, characterise, group and the ES search prompts
byte-for-byte unchanged in behaviour; the engine's two existing callers
pinned; the intervention profile never touches the IOF/ICF path; the
longlist intent never carries Where; no option row is readable across a
link; a guess never excludes and never feeds any proposal; "how sure"
appears nowhere; every exclusion carries a constraint; comparator records
never count; the unclustered and not-an-option counts are visible; a verb
is never applied unconfirmed; the rebuild never deletes an option; the
mini-search fan-out is bounded; the additive-only OpenAPI diff.
