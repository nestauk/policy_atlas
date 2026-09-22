# Task contract: 045-scoping-longlist

One implementation slice: the second of the five options-scoping build tasks
(PR #69 "Task 2 — the longlist"). It lands the longlist walk that runs when
the user confirms the plan against the baseline: the model's own suggestions
and the user's own options, each with an option search; a broad bottom-up
search read by the intervention profile; the seeded clustering of those
records into options and themes; the constraint checks; and the longlist
views (list, reduced grid, option card) with the chat verbs that edit them.

> **Status:** **drafted 2026-09-22 · lead; rulings D1–D21 taken by the owner
> in an interview the same day; approved as folded 2026-09-22 · owner;
> D22–D26 ruled at the review's adjudication.**
> **Contract-stage adversarial review ran 2026-09-22:** the Codex lane
> (`codex-rescue`, read-only) failed after 13 min 38 s on the workspace spend
> cap with no findings; the fallback lane (`deep-reasoner`, read-only, same
> brief) returned 23 findings, verdict "material change needed", all
> adjudicated with the owner one by one (§ Adversarial findings): four
> blockers reshaped the option searches (A1 → D6 amended), the unattended
> path (A2 → D1 amended), inherited rows (A3) and the inherited labels (A4 →
> D23); the review also produced D22, D24 and D25 and amended D2 and D20.
> The decision-sheet rows scheduled for task 2 (A1, A2, A9, A10, A11, E1, E2,
> E4, F2, F3; `docs/tasks/035-options-scoping/checks/decision-sheet.md` line
> 15) are folded into the rulings; rows E5, E6 and F13 wait for task 3 (D17).
> **Re-approved as folded 2026-09-22 · owner** (after D1 and D6 changed
> materially and D26 was added). **Amended at the plan gate 2026-09-22
> (plan-review findings P4, P5, P10, P16a, P16b, owner-ruled):** surface-map
> row 3 (the skip is a per-step directive key), deliverable 3 (`inherit`
> non-spine), deliverables 10 and 11 (existence and activity, not a latest
> run; `active_run`, `has_longlist`; the card route stays `204`), and
> § Constraints (the per-component semaphores).
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
> longlist directly; concept rulings 1, 4, 5, 8, 11, 12, 15, 19, 20, 22, 23,
> 29, 31, 33, 35, 36, 39, 43, 44, 49 and 50. Ruling 5's "Add to shortlist
> from the moment an option exists" is deferred to task 3 with the shortlist.
> The task number is a reservation id.

## Goal

After the user confirms the plan against the baseline, the run builds the
**longlist** both ways at once. Top-down: the model proposes options from the
plan, the baseline and the linked report; the user's own options come in
from the plan; each of these entrants gets its own option search. Bottom-up:
a broad search on a PICO-shaped intent, over the new, baseline and inherited
documents, read by the intervention profile for the interventions each
abstract covers. Seeded clustering joins the two into options and themes;
the plan's requirement constraints are checked; the Result opens on the
longlist. Each option shows what it is, what it is for, where it came from,
where it has been tried, and what the evidence base holds so far. Nothing
is assessed and no report is written (ruling 50). The user adds, excludes
and includes again in the Task Agent chat or with the buttons. The
shortlist is task 3.

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
   **Unattended mode opens the second walk in the same way** (A2): the
   standing default is recorded and flagged as today (044 A9), and nothing
   pauses. Both start paths take the run dispatch lock and the pre-insert
   reservation that `POST /runs` holds, so two walks cannot race (A23). The
   walk does not pause: the second structural gate ("Assess these N") is
   task 3. **A longlist exists when a `longlist_result` row exists** (A6);
   the Result, the plan document and the rubric key on that fact, not on a
   status. The walk ends `succeeded` (every step ran), `degraded` (an option
   search failed; the longlist exists without its records) or `failed` (a
   spine step failed; no longlist; the Result stays on the baseline with the
   failure line). "Search further" stays refused honestly (044 D10). (D1)
2. **The plan's new slots and the longlist intent.** The scoping plan gains
   **Options you already have in mind** (`your_options[]`, optional, the
   user's own words plus a design the Task Agent proposes back through
   `option_design_v1`), asked once in the planning conversation
   (`task_agent_scoping_v3`) with its Edit action (D19), and a **default
   preference** "Transferable to *Where*" (D22): kind preference, checked at
   assessment, origin *assumed*, following Where until the user edits it,
   removable. The longlist intent is compiled deterministically from the
   plan, PICO-shaped without the C: the target unit (P), the intervention
   left open (I), the plan's outcomes (O), and the setting only when the
   user stated one as a requirement (S, optional — D21). **Where enters
   nothing in the retrieval chain** (D20 as amended): not the intent, not
   query generation, not the screen, not acquisition ranking. It is read
   from each abstract as study geography (ruling 43) and shown on the way
   out: the card's **where tried** line and a list facet, grouped against
   the plan's Where (*United Kingdom · comparable systems (OECD) · other*),
   deterministic from a fixed country grouping. Transferability is judged
   at assessment only (ruling 29; task 3). The Evidence search's query
   prompts are untouched (A11 dissolved).
3. **The chain and the pool.** The longlist chain is: **suggest** (D7) →
   **option searches** (D6, child walks, deliverable 4) in parallel with the
   **broad search** (acquire → screen → classify → appraise → ingest) →
   **intervention profile** over every screened-in document → **longlist**
   (seeded clustering) → **constrain**. Spine membership (A6, P16b): the
   broad chain, the profile, `longlist` and `constrain` are spine (a
   failure ends the walk `failed`); `inherit` (owner at the plan gate:
   "inherit non-spine" — an unreadable link degrades the walk, which
   continues without the linked documents, the missing link named on the
   longlist), `suggest` and each option search are not (a failure
   degrades). The broad search's pool is the union of the baseline walk's
   documents, the **inherited documents** of every linked Evidence search
   task (the document part of `inherit`, deferred from 044 D4: a
   `task_source_snapshot` row per document pointing at the same
   content-addressed snapshot, **origin unchanged** — OpenAlex or Overton as
   acquired; the row is inherited because the inherit step created it, per
   the A7 ruling in data-model — A3), and the new acquisition at the depth's
   target per backend (D2), with the evidence restrictions as
   `ScopeConstraints` (044 D8). Inherited documents are re-screened under
   the longlist scope (A7; screening is scope-keyed, so this needs no
   migration). Their classification and appraisal are **read across** (D23):
   one resolver, `labels_for_snapshots(task_id, snapshot_ids)`, returns per
   document the evidence type and quality tier with their provenance (this
   task's own scope, or a linked task's pinned run through `task_link` and
   the shared snapshot id), distinguishing *inherited* from *absent*; the
   tier carries its rubric version and a document whose version differs
   from the current rubric is re-appraised (deterministic) rather than
   mixed; classification is read as is. Three readers use it: the
   longlist's coverage, the Sources tab read model, and the citation labels
   in the answer core; the ES's own run-time readers never see inherited
   rows and are untouched. Classify and appraise skip rows the resolver
   already answers. Counting is by **DOI** where present (A8, A20): the
   per-option coverage and the header counts collapse documents that share
   a normalised DOI (lower-cased, `https://doi.org/` prefix stripped);
   membership rows stay uncollapsed; a document without a DOI counts as
   itself. The thread shows the **progress beats**, one per boundary:
   suggestions made · option searches finished (aggregated) · retrieval
   counts · abstracts read · options clustered · constraints checked.
4. **Suggestions and entrants, each with an option search.** At the start
   of the longlist step the judgment model is asked, from the plan
   (question, intended change, target unit, outcomes, Your context, the
   user's own options), the baseline's sections **and the linked report's
   body** (A15), for its **suggested options**, each with a name, a
   one-sentence description and a specified design: free, with the
   lever-type list as a breadth checklist, no quota per type, bounded (D7;
   owner: "free with the checklist"). Options drawn from the linked report
   are labelled *from your evidence search* with the report section named;
   the rest *suggested by Policy Atlas*. Nothing is attributed to the
   report's prose: a report-derived option's evidence comes only from
   documents (its own option search, and the clustering's assignment of the
   corpus's records, inherited documents included). The **entrants** are
   these suggestions and the plan's own options (*added by you*). Every
   entrant gets its own **option search** (D6; owner: "we should have
   targeted acquire at the longlist stage … if we don't do top-down
   searches at the longlist stage we could omit options that the user might
   be interested in"). The option search is a **tool**,
   `run_option_search(design)`, with two callers: the longlist walk calls it
   once per entrant and waits; the Task Agent calls it for the chat verb
   *add* (deliverable 10). Its implementation is a **child walk** (D6 as
   amended, A1): a `capability_run` under its own intent record (`purpose =
   targeted`, intent = the entrant's specified design), linked to the
   longlist walk by `capability_run.parent_capability_run_id`, running
   acquire (10 per backend, D2) → screen → classify → appraise → ingest →
   intervention profile; its records join the pool and the entrant is a
   seed in the clustering. **The design is the tool's only input** (D26):
   the queries are written inside the walk by the acquire component's own
   search generation, as the Evidence search does; the Task Agent decides
   what to search for, not how. A `guidance` argument (the search
   directive's existing steering channel) is a recorded seam, tested during
   the build on the NEET option searches and added in this slice only if
   the queries miss what the design meant (owner: "Let's test it during
   implementation, though, and add it if needed"). Option searches run **in
   parallel at width 4**
   under a **cross-walk bound** built in this slice (the 044 seam: per-run
   fan-out had no bound across walks); at most **15 option searches per
   longlist walk** (A16): the user's own options and the report-derived
   ones always run, the model's suggestions fill the rest. An entrant whose
   search finds nothing stands on the longlist with zero documents and says
   so. A document an option search returns that is already in the task's
   pool is the same row (one document row per task, C4).
5. **The intervention profile.** `extract` gains a third profile, the
   **intervention profile** (union kind `interventions`; id
   `os_interventions_base_v1`, schema `interventions_v1`, prompt
   `extract_interventions_v1` — A10), that runs over **every screened-in
   document** of the longlist scope and of each targeted scope, with no
   `select` step: a **selection-free path** in `extract` (D24; rows E1, F2,
   F3 edited), which needs `extraction_result.selection_run_id` nullable,
   the component registry, harness graph and plan mapping entries for the
   new component, and the directive rule "an extraction must include the
   IOF profile" lifted (A5, A10). Its table is **`intervention_profile_record`**
   (D3), on the findings pattern beside `intervention_outcome_finding` and
   `implementation_context_finding`: one row per intervention a document
   covers, with its **role** (evaluated · described · recommended ·
   comparator · mentioned — the five values stand), its stated design
   features, whether it is a bundle and of what, the quote anchor, and the
   shared reference columns (intervention, outcome, population, **setting**,
   study geography, study design); per document, whether it covers no
   intervention. Non-evidence documents are profiled (a mention, never
   evidence — ruling 43). Records join `finding_reference_union`, which the
   migration recreates with a third branch (A5), and are memoised per
   (task, snapshot, fingerprint) through `source_extraction_record` like the
   other profiles — task-keyed, so one profile of a document serves the
   longlist scope and every targeted scope (A21). No adoptability flag
   (D3). "Intervention mention" and "abstract profile" are not names in the
   code or the living specs; the product says *covers* and *names* ("22
   documents name this option, 11 evaluated it").
6. **The longlist component.** The **unit of assignment is the intervention
   profile record** (ruling 31), or the extracted IOF/ICF finding where a
   linked task ran the deep chain (D5, ruling 35), read through the union
   view and projected to engine units **by the component** (A9: the engine
   already takes any unit). The shared clustering engine (ADR 0018) is
   **untouched**: the component composes its public functions (call budget,
   first assignment round with a supplied label list, validation) to run
   **seeded** — the entrants (and, on a rebuild, the existing options) are
   supplied as options to assign against, and discovery adds new ones (E4)
   — with the ceiling `clamp(ceil(N/4), 8, 40)` (D4; open question 4's
   target size stays open). **One option per record**; a document with
   several records belongs to several options (ruling 31). The component
   keeps two counted buckets of its own, **unclustered** and **not an
   option**, shown as numbers. Discovery yields each option's name,
   one-sentence description, **specified design** and outcomes served. A
   second pass groups options into generated **themes**, each with a
   one-line "what it does" (ruling 11). A typing pass gives each option one
   **primary lever type** from the versioned constant list, any secondary
   types, may answer **none fits** with a reason (counted and shown), and
   the **ambition tag** with a one-line justification, shown "as described,
   not measured" as Policy Atlas's reasoning (ruling 20; the words on the
   card and in the record, no claim row — A13); the runner-up type and its
   reason are recorded in `longlist_result` only (D8). Every option records
   the taxonomy version it was typed under. A bundle becomes a **package**
   with *part of* links (ruling 15). Each membership row carries the
   assignment reason and a **`design_feature_not_stated`** flag; no
   stability marker (D11). Per option the deterministic **coverage** is the
   source-quality profile: documents by evidence type and quality tier
   (Unknown and Non-evidence as their own buckets), by role, where tried
   (grouped against Where, D20), populations, settings, outcomes measured;
   flagged members counted and shown ("12 documents, 3 of which do not
   state the obligation") — never "how sure" (ruling 33).
7. **Constrain.** Every option is judged against the plan's **requirement**
   constraints (`checked_at = longlist`, validated since 044 and read for the
   first time here; a setting requirement is one of them — D21) and the three
   default screens (relevant to the stated outcomes · distinct · within
   scope), on its specified design and coverage, never on analysis; each
   exclusion names the constraint it broke; thin evidence never excludes;
   the *distinct* screen never excludes a *part of* relation (ruling 36).
   Every **preference** constraint gets a labelled **reasoned guess** per
   option (capped wording, a flag and a later sort, never a screen — trust §
   Reasoned guesses), **except the default transferability preference**,
   which gets no guess before assessment (ruling 29; D22): its row on the
   card reads "checked at assessment" beside the where-tried line. An
   **evidence restriction** never excludes an option (ruling 23 stands —
   D9). Because retrieval already applies the restriction, only inherited
   documents and documents acquired under an earlier plan version's
   restriction can fall outside it (A12): an option none of whose documents
   pass the restriction's country group and years, read from publication
   metadata (deterministic, no model call; language not applied, 044 C8),
   is marked **no in-scope evidence**, stays included (ruling 49), and its
   card names the restriction.
8. **Option records and the walk's claims.** The option is a task-scoped
   entity with a stable id and a versioned specified design (ruling 44):
   tables `option`, `option_membership`, `option_relation`; the run-keyed
   `longlist_result` (themes, per-option coverage, constraint judgements,
   guesses, the runner-up types, the unclustered, not-an-option and
   none-fits counts — the characterise pattern); `intervention_profile_record`
   (deliverable 5); `task_link.option_id` (044 D13; `task_link` is unique
   per task pair, noted for task 5 — A21); `capability_run.parent_capability_run_id`
   (A1). Option-level judgements are stored on the option row and in
   `longlist_result`, keyed `(option_id, design_version)`, so a changed
   design cannot inherit them; the annotation layer is extended only when a
   reader needs it (D10). **Claim inventory** (A19): the longlist walk
   produces pattern claims (the coverage denominators, metadata-grounded,
   with `option_membership` as the reproducible membership set behind each
   one — ruling 39), thematic clustering (options and themes, the softest
   grade), and tier-4 reasoning (the ambition tag and the guesses); it
   produces no chunk claims and no artefact blocks. Declared once, in the
   ADR, for tasks 3–5.
9. **The longlist views.** The Result tab opens on the **longlist** once a
   `longlist_result` exists (ruling 50; the existence signal is on the
   longlist route and the task read model — A7); a view switch offers
   **Baseline · Longlist**, and **Report** marked *available after
   assessment*. Every longlist surface carries the **scoping pass** depth
   label, and a coverage line says *abstract only* where the profile read
   only an abstract (trust § Provenance labels; A18). The **list view**: a
   header line with the counts (options · themes · included · of them with
   no in-scope evidence · excluded · unclustered records); a **Show** filter
   (All · Included · Excluded), a **setting facet** and a **where tried
   facet**; theme sections, each with its one-line description and its
   count line, collapsible; option rows with the name, the one-sentence
   description, the outcomes served, the origin (*clustered from N
   documents* · *suggested by Policy Atlas* · *from your evidence search* ·
   *added by you*), the state (*excluded: breaks "…"* · *no in-scope
   evidence*), and relations (*part of*); the "Do nothing" reference as a
   sentence with a link to the baseline; no sort (the sorts arrive with task
   3). The **reduced grid** (D12): rows the lever types, columns the
   ambition bands, tiles that open the option and carry the excluded and
   no-in-scope-evidence states, empty rows saying "no option of this type on
   the longlist"; no shortlist actions, no gap messages, no footer (task 3
   extends it). The **option card** (D15, assembled, no writer): breadcrumb,
   title, actions (**Exclude** / **Include again**), then *What it is* (the
   specified design; the primary lever type and what it also touches; the
   ambition tag "as described, not measured", both marked as Policy Atlas's
   reasoning), *What it is for*, *Where tried* (grouped against Where),
   *What the evidence base holds so far* (the source-quality profile turned
   into sentences by a template, closing with "a mention is not support"),
   *Constraints and guesses* (the transferability preference shown as
   "checked at assessment"), *Where it came from and what it relates to*
   with **Show the documents**; the words "how sure" appear nowhere. An
   on-demand written summary is a recorded seam (D15). Every direct action
   is logged as the user's turn in History (ruling 1). Sources, Share and
   History are otherwise unchanged; Sources lists the longlist scope's and
   the targeted scopes' documents like any run's.
10. **The Task Agent around the longlist** (D13; owner: "chat verbs in task
    2, buttons as the second way"). While the longlist exists and no walk is
    active, a Task Agent turn is sorted by a lead-authored surface
    (`longlist_verbs_v1`, the 044 gate sort's pattern) into **question ·
    add an option · exclude · include again · other**: a question goes to
    the answer core over **the union of the longlist scope and the targeted
    scopes** (A8), so an added option's own documents are searchable; a
    verb is confirmed in the thread before it is applied (a verb is never
    inferred); *add* mints the option as *added by you* with the design
    `option_design_v1` proposes back (A14) and calls `run_option_search`
    (a child walk with no parent); *exclude* takes the user's reason; each
    applied verb writes the same state the buttons write and a History
    event as the user's turn. The ordinary task chat answers over the
    longlist walk and its children's scopes once a longlist exists, and
    over the baseline walk before (A8; at the plan gate the "latest walk"
    reading was replaced — P4, owner: "scoping readers see what exists and
    what is active": a scoping task's readers key on which artefacts exist
    and whether any walk, children included, is active, never on a single
    latest run; `latest_run` stays as it is for the Evidence search). The plan step *Longlist* loses "Not in this
    release" and gains its blurb; the plan document's state machine gains
    `longlist_built` and `rebuild_or_keep` ahead of `confirmed`, and the
    shared line "Plan confirmed · the longlist arrives with the next stage"
    is replaced by "Longlist built · N options" (A7); the thread shows the
    progress beats (code-authored). A plan change after the longlist marks
    it *built from plan version N* and the plan document offers **Rebuild
    longlist** (D14): a new longlist walk seeded with the existing options,
    so option ids, user exclusions and user additions survive; an option
    that gains no member in the rebuild stays with zero documents, never
    deleted; option searches re-run only for entrants that are new. Open
    question 7 (deltas, not restarts) stays open: a rebuild re-runs the
    whole chain.
11. **System records and API.** `GET /tasks/{id}/longlist` (themes, options,
    counts, states, the run it came from), `GET /tasks/{id}/options/{option_id}`
    (the card), `POST /tasks/{id}/options` (add by hand — the button's path,
    same handler as the chat verb), `POST .../options/{option_id}/exclude`
    and `/include` (with the user's reason), the longlist walk's and its
    children's progress on the existing run stream; the confirm-baseline
    route returns the opened walk in an **optional** field of the shared
    plan model and the chat's gate decision carries it on the decision
    (A23); **the check-in card route stays `204`** (P16a, owner: "card
    route stays 204") — the thread learns of the walk from the run stream;
    `TaskOut` gains `active_run` (any running or paused walk, children
    included) and `has_longlist` (P4); `your_options` and the default
    preference on the plan read and patch bodies. All additive; OpenAPI
    regenerated.

## Deliverable

A PR on `task/045-scoping-longlist` into `feat/options-scoping`: one alembic
migration (§ Constraints), the intervention profile, the suggest, longlist
and constrain components, the option search tool and its child walks, the
cross-walk bound, the label resolver, the longlist walk and its start from
the two confirm surfaces, the longlist verbs, the frontend views, tests,
`verification.md`, ADR 0039, the spec changes in § Spec changes, and the
rulings below quoted where they are applied.

## Terms

The 044 contract's § Terms applies (capability, Task Agent, plan, intent
record, Link, inherit, baseline, the gate, steer point, walk, depth, origin
tag, constraint kind, Your context, standing default, gate sort, answer
core). New here:

| Term | Meaning |
|---|---|
| **longlist** | Both the artefact (the options grouped by theme with their states) and the component that clusters records into options (OS components § 6). The walk that builds it is the **longlist walk**. A longlist exists when a `longlist_result` row exists. |
| **longlist scope** | The intent record with `purpose = longlist` the broad search runs under; its `plan_id` is the confirmed plan version. Screening and the option records are keyed to it. |
| **targeted scope** | An intent record with `purpose = targeted` (decision C4) for one option search; its intent is the entrant's specified design. |
| **option search** | An option's own search (owner naming 2026-09-22; the spec's "own small acquire + screen + classify + appraise", OS components § 2–5). A tool, `run_option_search(design)`, whose implementation is a **child walk** under a targeted scope: acquire (10 per backend) → screen → classify → appraise → ingest → intervention profile. Not the spec's "mini evidence search", which is assessment depth (task 3). |
| **child walk** | A `capability_run` whose `parent_capability_run_id` names the longlist walk that asked for it. The parent waits for its children and aggregates their beats; a child's failure degrades the parent. A walk the Task Agent starts for *add an option* has no parent. |
| **cross-walk bound** | The semaphore that limits how many walks run at once in one process (width 4 for option searches), built in this slice. 044 recorded its absence as a seam. |
| **intervention profile** | The third `extract` profile: for every screened-in document, the interventions its abstract covers, each with a role and its stated design. Owner naming 2026-09-22 (replaces "abstract profile"). Names: union kind `interventions`, id `os_interventions_base_v1`, schema `interventions_v1`, prompt `extract_interventions_v1`. |
| **`intervention_profile_record`** | The profile's table: one row per intervention a document covers. Owner naming 2026-09-22 (replaces "intervention mention"). The unit `longlist` assigns. Not a finding of effect. |
| **role** | What the abstract does with the intervention: **evaluated** (reports a study of its effect) · **described** (describes it without evaluating) · **recommended** (proposes it) · **comparator** (it is the comparison arm) · **mentioned** (named in passing). Comparator records never count as membership. Role sorts and describes; it never excludes. |
| **selection-free path** | `extract` running a profile over a scope's screened-in set with no `select` run (D24). Needs `extraction_result.selection_run_id` nullable. |
| **label resolver** | `labels_for_snapshots(task_id, snapshot_ids)`: per document, the evidence type and quality tier with provenance (own scope, or a linked task's pinned run) and an explicit *absent*; the rubric-version rule (D23). The seam a future cross-task reader widens. |
| **PICO-shaped intent** | The longlist intent: target unit (P), intervention open (I), outcomes (O), setting only when required (S); no comparison and no place (D20, D21). |
| **where tried** | The countries an option's documents were studied in, from study geography, grouped against the plan's Where (*United Kingdom · comparable systems (OECD) · other*) by a fixed country grouping. A facet and a card line; never a filter, never a verdict (D20). |
| **option** | A task-scoped row: name, one-sentence description, specified design (versioned), stated outcomes served, primary and secondary lever types, taxonomy version, ambition tag, origin, state. Ruling 44's durable identity. Not a document, not a theme. |
| **specified design** | The option's defining features as the longlist states them (offer, obligation, delivery point …). Support binds to it (ruling 36). Version 1 in this slice; a design edit is task 3's variant path. |
| **design feature** | One element of a specified design (for a youth guarantee: the offer within four months, the obligation to accept, sanctions). Two options can share a name and differ by one feature. |
| **`design_feature_not_stated`** | A flag on a membership row: the document covers the intervention but its abstract does not state the feature that defines this option. Counted and shown, never dropped (D11). |
| **theme** | A generated grouping of options in the problem's own words, run-local like characterise's themes (ruling 11). Never earns a shortlist place. |
| **lever type** | One of about ten curated, versioned, domain-agnostic instruments of the state (regulate · subsidise · tax or charge · inform · provide a service · enforce existing powers · devolve · change who runs the system …). One list for every domain (D8); each option has one primary; the list is a versioned Python constant. "Lever family" never appears user-facing. |
| **none fits** | The typing pass's answer when no lever type fits an option, with a reason; counted and shown so the list can be revised on evidence (D8). |
| **ambition tag** | Do minimum · incremental · structural, per option, with a one-line justification, shown "as described, not measured" as reasoning (ruling 20). |
| **seeded clustering** | The longlist component composing the engine's public functions with a supplied option list (the entrants; on a rebuild, the existing options) assigned against, plus discovery of new options (E4). The engine is untouched (A9). |
| **unclustered · not an option** | The component's two counted buckets: records assigned to no option; records the discovery judged not to describe an actionable option. Both shown as numbers, never hidden. |
| **source-quality profile** | An option's coverage: documents by evidence type, appraisal tier, role, where tried, population, setting and outcome measured, with flagged members shown. Display and a later sort, never "how sure" (ruling 33). |
| **entrant** | An option that did not come from bottom-up clustering: *suggested by Policy Atlas*, *from your evidence search* (drawn from the linked report by the suggest step) or *added by you* (the plan slot or the chat verb). Gets an option search and is a seed in the clustering. |
| **suggest** | The first step of the longlist walk: the judgment model proposes options from the plan, the baseline and the linked report's body, free, with the lever-type list as a breadth checklist (D7, A15). |
| **Options you already have in mind** | The plan's new optional slot, `your_options[]`: options the user named at planning time, in their words, each with a design proposed back (D19). |
| **default transferability preference** | "Transferable to *Where*", a preference on every scoping plan, assumed, checked at assessment, no guess before it (D22). |
| **constrain** | The component that judges every option against the requirement constraints and the three default screens and writes the reasoned guesses (OS components § 7). |
| **default screens** | Three screens every option faces: relevant to the stated outcomes · distinct · within scope. Cited like any constraint. |
| **no in-scope evidence** | A condition, not a state: the option is included, and none of its documents pass the plan's evidence restriction, read from publication country and year (D9; rulings 23, 49). Reachable only through inherited documents or an earlier version's restriction (A12). |
| **reasoned guess** | Per preference constraint and option, a capped tier-4 claim ("cost: likely low, a guess rather than evidence"); a flag, never a screen or a shortlist input. Not made for the transferability preference. |
| **package** | An option that is a bundle; its constituents are linked *part of* (ruling 15). |
| **longlist verbs** | The sorted Task Agent turn kinds while the longlist exists and no walk is active: question · add an option · exclude · include again · other (D13). Surface `longlist_verbs_v1`. |
| **`option_design_v1`** | The prompt surface that proposes a specified design back from a user's words (the plan slot and the verb *add*) (A14). |
| **list view · reduced grid · option card** | The three longlist surfaces this slice builds. The grid is reduced: no shortlist state, actions, gap messages or footer (D12). |
| **scoping pass** | The depth label every longlist surface carries: screened on titles and abstracts, nothing read in full, document set not confirmed (ruling 16; trust § Provenance labels). |
| **progress beat** | A code-authored line the walk posts in the Task Agent thread at a stage boundary. |

## Read first

- [OS capability](../../specs/capabilities/options-scoping/capability.md) —
  § Depths and modes (longlist depth; "mini evidence search" = assessment
  depth), § Pipeline and gates (Plan: target unit, Where, setting; Longlist;
  Screening is a pipeline stage; Three kinds of constraint), § Output
  structure (Longlist), § Product surface, § Open decisions (open questions
  4, 5, 7), § Considered and rejected (ruling 29: no argument-only
  transferability).
- [OS components](../../specs/capabilities/options-scoping/components.md) —
  § 0 inherit (the document part), § 2–5 (the spine; entrants' own small
  acquire), § 6 longlist, § 7 constrain, § Interface rulings 1–4, ⟨longlist
  depth⟩ composition.
- [OS trust](../../specs/capabilities/options-scoping/trust.md) — § The
  principle, § Provenance labels, § Transferability, § Reasoned guesses,
  § Screening and shortlisting, § What is structurally impossible.
- [ES components](../../specs/capabilities/evidence-search/components.md) —
  § 1 acquire, § 2 screen, § 5 characterise, § 7 extract (the profile
  mechanism), § 8 group (the shared engine).
- [data-model](../../specs/system/data-model.md) — § Corpus & source
  snapshots (the A7 ruling on inherited documents), § Links between tasks,
  the option entity declared by ruling 44.
- [plan-as-object](../../specs/system/plan-as-object.md) — § What a plan
  contains, § Source / evidence policy.
- [provenance-grounding](../../specs/system/provenance-grounding.md) —
  pattern claims and the membership set.
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
- `docs/deferred.md` § Options scoping shell and baseline (task 044 seams:
  the per-run fan-out bound; inline versus retrieval inherit), § Document
  identity across snapshots, § Capabilities.

## Plan object (additions to the 044 § Plan object)

| Field | Content | Origin tag | Compiles to |
|---|---|---|---|
| `your_options[]` | `{text verbatim, design, turn_index}`: options the user named, optional, asked once (D19); the design from `option_design_v1` | *added by you* | entrants with option searches; seeds |
| default preference | `constraints[]` gains one row on every scoping plan: "Transferable to *Where*", kind preference, checked at assessment, origin assumed; text follows Where until edited; removable (D22) | *assumed* | task 3's transferability working; no guess at the longlist |
| `setting` (as a constraint) | unchanged: a requirement when stated; never a slot (044 D3 ruling) | — | the S of the longlist intent when present (D21); a `constrain` criterion |
| `steps[]` | Longlist blurb: "Suggest options, search widely, read every abstract for the interventions it covers, cluster them into options, apply your constraints." | — | display |

**Compile constants named here so nothing hides** (044 C8 pattern): the
broad search's acquisition target per backend by depth (D2: standard 50,
rapid 25); the option search target per backend (10); the option-search
cap per walk (15) and width (4); the suggestion bound (about ten, within the
cap); the discovery ceiling formula; the lever-type list and its version;
the country grouping behind *where tried*. All measured in the build; the
numbers are the owner's after measurement (D2). **Expected pool at
standard** (A16): about 100 broad + about 40 baseline + the inherited set +
up to 15 × about 20 from option searches, about 350 to 450 documents; at
rapid about half. Per-stage time is estimated in the plan and measured in
`verification.md`.

## Surface map

Rows marked **keep** must not change behaviour. File paths as built at
`6c19a1e1`.

| # | Surface | Today | After this slice | Where |
|---|---|---|---|---|
| 1 | Gate option `confirm_plan` | falls through `_canonical_intent` to `("continue", None)`; the walk ends `succeeded` | a named branch: record the decision, end the baseline walk, open the longlist walk under the dispatch lock and reservation (A23) | `api/continuation.py` (`_offered_option`, `_persist_intent`), `runtime/steering.py` `baseline_confirm_options`, `api/routers/runs.py` (`_dispatch_lock`, `_dispatching_tasks`) |
| 1 | `POST /tasks/{id}/plan/confirm-baseline` | mints the confirmed plan version and stops | + opens the longlist walk on that version; response carries the run in an optional field | `api/routers/task_agent.py` `confirm_baseline`, `api/contract/task_agent.py` `PlanOut`, `api/routers/runs.py` `_dispatch_run` |
| 1 | Unattended mode | the gate passes on the standing default and the walk ends | the standing default is recorded and flagged, then the second walk opens (A2) | `runtime/runner.py` `_resolve_baseline_gate_unattended` |
| 2 | Scoping plan | no user options; no default preference; steps say "Not in this release" | `your_options[]`; the default transferability preference; the Longlist blurb; `task_agent_scoping_v3` asks once; Edit actions | `runtime/scoping_plan.py`, `runtime/task_agent_scoping_prompt.py`, `frontend/src/views/workspace/PlanDocument.tsx`, `planVocabulary.ts` |
| 2 | Longlist intent and screening criteria | baseline only (status quo; target unit + Where) | `compile_longlist_intent(...)` (PICO-shaped, no place); longlist screening criteria (target unit, outcomes; setting when required), composed as data under the screen's 2,000-character ceiling (fail-closed) | `runtime/scoping_plan.py` (`_scoping_directive_delta`, `_screening_criteria`), new `options_scoping/longlist_intent.py` |
| 2 | ES query generation | `intent` + user `guidance` | **keep**: Where is not passed; prompts untouched (A11 dissolved) | `evidence_search/sourcing/search_prompts.py`, `search_loop.py` |
| 3 | `compose_scoping` | one chain, baseline | chains chosen by the intent record's purpose: baseline (as today), longlist, targeted (the option search); the registry keeps one `compose` per capability and the purpose is a compose argument | `runtime/scoping_plan.py`, `runtime/capability_registry.py` |
| 3 | inherit, document part | `linked_context` seeds the Task Agent only | + `inherit_documents(conn, task_id)`: one `task_source_snapshot` row per linked document, origin unchanged, created by the inherit step (A3); the linked report's body handed to `suggest` (A15) | `runtime/inherit.py` |
| 3 | Inherited labels | none | the **label resolver** (D23) and its three readers: longlist coverage, Sources read model, answer-core citation labels; the rubric-version rule | new `options_scoping/labels.py`; `api/readmodels/repository.py`; `api/answer_core.py` (`apply_appraisal_labels`) |
| 3 | acquire · screen · classify · appraise · ingest | **keep** (ES components, parameterised) | unchanged behaviour; the longlist and targeted scopes' directives only. *Amended at the plan gate (P10; owner: "amend row 3"):* classify and appraise skip rows the resolver answers through **one optional, fail-closed directive key each** (`skip_task_source_snapshot_ids`), computed per step by the runner's directive-authoring seam (`leg_directive`) after the inherit step has run — a compose-time filter is impossible, because the directive is the only channel into these components and the inherited rows do not exist at compose time. Behaviour-preserving when the key is absent. Classify's and ingest's fan-outs also take the shared per-component semaphores (P5) | `evidence_search/sourcing/*`, `assess/*` |
| 4 | suggest | does not exist | new step: one judgment-model call over the plan, the baseline and the linked report → entrants | new `options_scoping/suggest/` (`suggest.py`, `suggest_prompt.py`) |
| 4 | Option search tool and child walks | does not exist | `run_option_search(design)`; child `capability_run` rows with `parent_capability_run_id`; a fan-out step in the longlist walk that dispatches and waits; the cross-walk bound | `runtime/runner.py`, `runtime/option_search.py` (new), `core/schema.py` (`capability_run`), `api/routers/runs.py` (the executor bound) |
| 5 | extract | requires a `selection_run_id`; refuses an extraction without IOF | + the selection-free path; the interventions profile; the IOF rule lifted; registry, harness graph and plan-mapping entries for `extract_interventions` | `evidence_search/extract/extract.py`, new `interventions_profile.py`, `extract_interventions_prompt.py`, `interventions_records.py`; `runtime/run_spec.py`, `runtime/harness.py`, `runtime/task_plan.py` |
| 6 | longlist | does not exist | new component composing the engine's public functions: seeded assignment + discovery → theme → type; coverage; writes `option*` rows and `longlist_result` | new `options_scoping/longlist/` (`longlist.py`, `longlist_cluster_prompt.py`, `longlist_theme_prompt.py`, `lever_typing_prompt.py`, `lever_types.py`, `coverage.py`, `where_tried.py`) |
| 6 | Clustering engine | two callers (characterise, group) | **keep**: untouched (A9) | `evidence_search/clustering_engine.py` |
| 7 | constrain | does not exist | new component: per-option fan-out judgement; the deterministic in-scope check; writes judgements and guesses into `longlist_result` and the option state | new `options_scoping/constrain/` (`constrain.py`, `constrain_prompt.py`, `in_scope.py`) |
| 8 | Schema | `task_link` has no `option_id`; no option tables; `extraction_result.selection_run_id` NOT NULL; the union view names two tables; `capability_run` has no parent | `option`, `option_membership`, `option_relation`, `longlist_result`, `intervention_profile_record`; `task_link.option_id` (nullable FK); `capability_run.parent_capability_run_id` (nullable self-FK); `extraction_result.selection_run_id` nullable; `finding_reference_union` recreated with a third branch (A5) | `core/schema.py`; one alembic revision |
| 8 | Component names | Python registries | `suggest`, `extract_interventions`, `longlist`, `constrain` registered (no `runs` column exists — A5) | `runtime/run_spec.py`, `runtime/harness.py`, `runtime/task_plan.py` |
| 9 | Result tab | baseline artefact when `template = baseline` | the longlist when a `longlist_result` exists; view switch Baseline · Longlist · Report (unavailable); list · grid; the scoping pass label | `frontend/src/views/ArtefactView.tsx`, `views/lifecycle.ts` (`hasBaseline` → `resultView` with the longlist existence signal), `views/LifecycleRoute.tsx`, `views/AppShell.tsx`, new `views/longlist/*` (`LonglistView.tsx`, `LonglistGrid.tsx`) |
| 9 | Option card | does not exist | `/tasks/{id}/options/{option_id}` route in the app; assembled sections | new `views/longlist/OptionCard.tsx` |
| 9 | Sources · Share · History | **keep** | unchanged code paths; Sources lists the scopes' documents like any run's and reads inherited labels through the resolver; History shows the walk, its children and the user's actions | — |
| 10 | Task Agent thread | gate turns; progress for the baseline | + the longlist verbs surface while no walk is active; the progress beats; the answer core over the union of scopes (A8) | `api/routers/task_agent.py` (`_dispatch_gate_turn` pattern), new `api/longlist_turns.py`, new `runtime/longlist_verbs_prompt.py`, new `runtime/option_design_prompt.py`, `runtime/agent_backend.py`, `api/chat_scope.py` (`build_chat_readers` over several scopes) |
| 10 | Ordinary task chat | resolves the latest succeeded/degraded walk | re-points to the longlist walk after it runs (intended; A8) | `api/chat_scope.py` `resolve_terminal_run_components` |
| 10 | Plan document | Longlist step "Not in this release"; state `confirmed`; shared "longlist arrives" line | step blurb; states `longlist_built` · `rebuild_or_keep` dispatched ahead of `confirmed`; action **Rebuild longlist**; the shared line replaced (A7) | `frontend/src/views/workspace/planStart.ts`, `PlanDocument.tsx`, `runtime/scoping_plan.py` `SCOPING_STEPS` |
| 11 | API | — | the routes in deliverable 11; `OptionOut`, `LonglistOut` contracts; `your_options` and the default preference on the plan bodies | `api/routers/longlist.py` (new), `api/contract/longlist.py` (new), `api/contract/task_agent.py` |
| — | ES chain, ES extract profiles, ES characterise, group, ES search prompts | **keep** | byte-identical prompts and outputs | — |
| — | Prompt guard | name-based; `group_clustering.py` unguarded | every new prompt module is named `*_prompt.py` so the guard pins it; the guard's name rule is unchanged (the recorded 044 gap stays a gap for the old modules) | `scripts/prompt_hashes.json` |
| — | Generated | via `make openapi-sync` only | additive | `frontend/openapi.json`, `frontend/src/api/gen/types.ts` |

## Decisions (ruled by the owner, 2026-09-22)

- **D1 — the longlist is a second walk. Accepted; amended at review (A2).**
  A new `capability_run` on the confirmed plan version with its own
  `purpose = longlist` intent record; started from both confirm surfaces;
  ends without a pause. Unattended mode opens the second walk too (the
  unattended gate handler cannot extend a chain, and one walk carries one
  scope); the standing default is recorded and flagged as 044 A9 requires.
- **D2 — the acquisition targets and the pool. Accepted as a starting
  point; amended at review (A16)** (owner: "start there, measure, I'll set
  it after"; "cap at 15, run the live check at rapid"): the broad search at
  standard 50 and rapid 25 per backend; the option search at 10 per
  backend; at most 15 option searches per longlist walk, the user's own and
  the report-derived ones never squeezed out; the expected pool stated;
  measured on the NEET question in the build and reported with the funnel
  counts and a per-stage split; the owner sets the final numbers. Nothing
  else in the chain reads depth in this slice.
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
- **D5 — inherited findings as units. Accepted:** one unit projection, in
  the component, over two record kinds through the union view.
- **D6 — every entrant gets its own option search in this slice. The
  lead's deferral was rejected** (owner: "We should have targeted acquire
  at the longlist stage, that is the mini-evidence searches defined in the
  wireframes and specs. Mini-evidence searches are useful for 'top down'
  suggestions, i.e. interventions suggested by the LLM or by the human.
  Assessment is a separate step … if we don't do top-down searches at the
  longlist stage we could omit options that the user might be interested
  in"). **Amended at review (A1):** the option search is a tool whose
  implementation is a child walk under a targeted scope (owner: "I was
  thinking the mini evidence searches function as essentially a tool which
  the task agent runs"; "accept that"), because one walk carries one intent
  record and the runner's step loop is sequential and keyed by component
  name; the searches run in parallel at width 4 under a cross-walk bound
  built in this slice (owner: "parallel at width 4, build the cross-walk
  bound in this task").
- **D7 — the model's own suggestions, at the start of the longlist step,
  free with the lever-type checklist. Ruled** (owner: "it should be before
  clustering as well, we should ask for the LLMs suggestions at the start of
  the longlist step, so that we can do both bottom up and top down longlist
  generation"; on lever types: "free with the checklist"). No quota per
  type; each suggestion carries a specified design; lever type assigned
  afterwards like every option. **At review (A15):** the linked report's
  body is a second input to `suggest`, its options labelled *from your
  evidence search*; the report is never a source of profile records (owner:
  "the source would be the AI written synthesis").
- **D8 — one versioned lever-type list for every domain. Accepted with two
  additions** (owner, after asking whether one list makes sense across
  domains): the list names the instrument the state uses, not the subject,
  which is what makes it domain-agnostic and what task 3's coverage
  denominator needs to be fixed; every option records the taxonomy version;
  the typing pass may answer *none fits* with a reason, counted and shown.
  A Python constant; the runner-up type and its reason in the record only,
  never shown (sheet A10, Codex wording). Closes open question 5 (A22).
- **D9 — "no in-scope evidence" is a deterministic check. Accepted, and
  ruling 23 stands** (owner, after asking why a restriction on evidence
  does not exclude an option: "the ruling stands, deterministic check").
  Publication country and year against the plan's country group and years;
  the same fields retrieval filtered on; language not applied; the option
  stays included; the card names the restriction. Reachable only through
  inherited documents or an earlier version's restriction (A12).
- **D10 — option-level judgements on the option row and in
  `longlist_result`, keyed `(option_id, design_version)`. Accepted;** the
  annotation layer is extended later if necessary (sheet A1, Codex wording).
  The ambition tag and the guesses are labelled as reasoning in words; no
  claim row (A13).
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
- **D16 — count by DOI where present (A8, issue #75).** Applied as ruled;
  the surfaces, normalisation and no-DOI rule stated (A20).
- **D17 — routed to task 3:** the shortlist-quota guards (E5), the
  `shortlist_result` record (E6), the reading of "assess it" (F13). Owner:
  "those three wait for task 3".
- **D18 — retrieval during the baseline pause. Stays deferred.**
- **D19 — the plan gains "Options you already have in mind". Accepted**
  (a spec addition to plan-as-object and OS components § 1): optional, asked
  once, the user's words, a design proposed back; every named option is an
  entrant with its option search in the longlist walk itself.
- **D20 — Where is out of the longlist's retrieval chain. Accepted;
  amended at review (A11).** Owner: "The Z that will be input by users is
  usually the UK, but the idea of options appraisal is also to bring in
  international evidence that might be transferable. Directly saying Z in
  the search scope may constrain the results too much." At review the
  "Where as context for query generation" idea was dropped (owner: "would
  that cause the query generation to inject the Where into every query?";
  "maybe the where is more useful for screening or ranking, probably not
  as much for query generation"), and screening and ranking were ruled out
  for the same narrowing reason; Where is shown on the way out as *where
  tried*, grouped against Where, and returns at transferability (task 3).
- **D21 — setting in the intent only as a stated requirement, recorded on
  every profile record, a facet on the list and a line on the card.
  Accepted** (owner: "not all users will have a setting requirement so it is
  optional"). PICO-shaped: target unit (P), intervention open (I), outcomes
  (O), setting optional (S), no comparison before assessment.
- **D22 — "Transferable to *Where*" is a default preference. Ruled at
  review** (owner: "Should be a default preference"), after the owner asked
  whether transferability should count at the longlist stage: a verdict or
  a guess before assessment is out (trust § Assessment is grounded; ruling
  29 rejected an argument-only transferability cell), so the preference is
  present on every plan, assumed, checked at assessment, following Where,
  with no reasoned guess before assessment and the where-tried grouping as
  its longlist-stage display.
- **D23 — inherited classification and appraisal are read across through
  one resolver. Ruled at review** (A4; owner: "I think it would make sense
  to have documents be able to be read across tasks rather than just copying
  them over … laying the groundwork for [a meta-analysis capability]").
  The cross-task key already exists (`source_snapshot` is content-addressed
  with no task id); the resolver is one function with explicit provenance
  and an explicit *absent*, three call sites, and the rubric-version rule;
  no general cross-task layer is built. Re-running (rejected by the owner
  as waste) and copying rows (rejected in favour of reading across) were
  the alternatives. A7 is honoured as written.
- **D24 — the selection-free path in `extract`, recorded as an edit to
  decision-sheet rows E1, F2 and F3. Ruled at review** (A17; owner: "Yes,
  selection-free, record it as an edit to those rows"): the `all_screened_in`
  select strategy those rows proposed would write a selection row per
  scope, including one per option search, to say "all of them"; task 3's
  read-set strategy is a different thing.
- **D25 — the name "option search". Ruled at review** (A21; owner: "let's
  go with option search"): the spec's "mini evidence search" is assessment
  depth, so the entrant's chain needed its own name; "entrant search" was
  rejected.
- **D26 — the option search takes the design, not queries. Ruled at
  review** (owner, on whether the Task Agent gets to define its own
  searches: "keep the design as input, guidance as a seam. Let's test it
  during implementation, though, and add it if needed"): the queries are
  generated inside the walk from the design, as the ES generates them from
  its intent; a `guidance` argument through the search directive's existing
  steering channel needs no prompt change and is added in this slice only
  if the build's NEET option searches show the queries missing what the
  design meant; otherwise it stays a recorded seam.

## Adversarial findings (contract stage, 2026-09-22)

Codex lane: `codex-rescue`, read-only brief, job `task-muco86o8-u4m1lt`,
**failed** after 13 min 38 s ("You hit your spend cap set by the owner of
your workspace"); no findings, two partial observations (both confirmed by
the fallback lane as A4 and A6). Fallback lane: `deep-reasoner`, read-only,
same brief; 23 findings; verdict "material change needed". Every finding
was put to the owner one by one; the factual ones were spot-checked in the
code by the lead before the report (the four blockers hold).

| # | Finding | Severity | Ruling / fold |
|---|---|---|---|
| A1 | One `capability_run` cannot carry N option searches (one scope per walk; `runs` has no scope; the step loop is sequential and keyed by component name; the chain is fixed before `suggest` runs) | blocker | **owner:** the option search is a tool whose implementation is a child walk; parallel at width 4; the cross-walk bound built here (D6 amended) |
| A2 | The unattended handler cannot continue into the longlist chain; one walk would key everything to the baseline scope | blocker | unattended opens the second walk (D1 amended) |
| A3 | `origin = inherited` contradicts the A7 ruling ("no inheritance column") and would render as OpenAlex | blocker | **owner:** origin stays the original source; inherited = created by the inherit step |
| A4 | No reader can see a linked task's classification or appraisal rows; the "directive-only skip" claim is false (classify reads no directive; appraise's parser is fail-closed) | blocker | **owner:** read across through one resolver with provenance and the rubric-version rule (D23) |
| A5 | No `runs.component` column; `finding_reference_union` must be recreated; `extraction_result.selection_run_id` NOT NULL | material | all three folded into § Constraints and the rollback |
| A6 | Every scoping step is spine, so "succeeded or degraded" was incoherent; a longlist has no artefact row | material | spine membership declared; "a longlist exists" = a `longlist_result` row; `failed` admitted |
| A7 | No query says whether a longlist exists; the plan document's dispatcher and a shared copy string need explicit changes | material | existence signal on the route and read model; dispatcher reordered; the line replaced |
| A8 | The answer core binds to one scope (an added option's documents unreachable); the ordinary chat silently re-points | material | readers over the union of scopes; the re-pointing stated as intended |
| A9 | Four wrong claims about the engine (units already generic; one label per unit; one residual bucket; prompts live in callers) | material | engine untouched; the component composes its public functions; "one option per record"; a stop condition retired |
| A10 | The selection-free path is enforced in four places plus the IOF-mandatory directive rule; the profile's names matched no convention | material | files added to the surface map; rule lifted; three house-form names |
| A11 | Query generation has no context field; the guidance channel is the user's steering | material | **owner:** Where dropped from query generation, screening and ranking entirely (D20 amended); the finding dissolves |
| A12 | "No in-scope evidence" is reachable only for inherited documents; the test could not fail | material | domain stated; fixture-based test; linked-start live check |
| A13 | "Stored as a tier-4 claim" is unimplementable without the annotation layer D10 keeps closed | material | **owner:** the words on the card, no claim record |
| A14 | The surface that proposes a design back from the user's words was unnamed | material | `option_design_v1`; eight surfaces plus one re-pin |
| A15 | How the linked report's interventions become entrants was unspecified; a rapid ES task has no grouping rows | material | **owner** (after the lead proposed profiling the report and the owner objected that its source would be the AI-written synthesis): the report is a second input to `suggest`, labelled; never a source of records |
| A16 | The pool was unbounded; the 40-minute live check was not credible | material | **owner:** cap 15 option searches; pool estimate; live check at rapid |
| A17 | The contract cited E1/F2/F3 for the opposite mechanism (`all_screened_in` select) | material | **owner:** selection-free, recorded as an edit to those rows (D24) |
| A18 | The *scoping pass* depth label was missing from every longlist surface | minor | added, with *abstract only* |
| A19 | The walk's claim kinds were undeclared | minor | claim inventory in deliverable 8; `option_membership` as the membership set |
| A20 | The DOI rule was under-specified | minor | surfaces, normalisation and no-DOI case stated |
| A21 | Name collisions: "mini evidence search" (assessment depth in the spec); rubric item 5 versus the role `mentioned`; the profile is task-keyed; `task_link` unique per pair; rulings 1 and 5 | minor | **owner:** "option search" (D25); the rest fixed in place |
| A22 | D8 closes open question 5 unstated; the profile memo is task-scoped so inherited documents are re-profiled (no cost today: no ES task runs the profile) | minor | both stated; the cross-task memo a recorded seam |
| A23 | The confirm response's run field must be optional; the new start paths must take the dispatch lock and reservation | minor | both folded; a race test added |

## Spec changes (applied with the owner's words quoted; a line each in `docs/specs/log.md`)

1. OS components § 1 plan and plan-as-object § What a plan contains: the
   optional slot *Options you already have in mind* (D19) and the default
   transferability preference (D22).
2. OS components § 2–5 and OS capability § Pipeline and gates (Plan): the
   longlist intent is PICO-shaped without Where; Where enters nothing in
   retrieval and is shown as *where tried*; setting is the optional S (D20,
   D21); the entrant's "own small acquire" is the **option search**, a child
   walk (D6, D25); "mini evidence search" stays the assessment-depth term.
3. OS components § 6 longlist: the intervention profile and
   `intervention_profile_record` names (D3, replacing "abstract profile" and
   "mention" in the living specs, not in the frozen sources), the ceiling,
   seeded assignment, the flag and reason on membership (D4, D11), the
   suggestion step at the start with the linked report as input (D7, A15),
   the taxonomy version and *none fits* (D8); the 🟡 "unproven at option
   grain" marker closes, citing check 3; open question 5 closes (D8).
4. OS components § 7 constrain and OS capability § Three kinds of
   constraint: "no in-scope evidence" computed from publication metadata
   (D9); the transferability preference carries no guess (D22).
5. OS capability § Output structure (Longlist): the reduced grid before the
   proposal (D12); the assembled card and the on-demand summary seam (D15);
   the where-tried line and facet (D20).
6. OS components § 0 inherit and data-model § Corpus: inherited rows keep
   their origin (A3); classification and appraisal read across through the
   resolver (D23); `intervention_profile_record`, the option tables,
   `task_link.option_id`, `capability_run.parent_capability_run_id`.
7. web-api: the longlist routes, the longlist verbs, the two confirm
   surfaces opening the walk, `your_options` and the default preference on
   the plan bodies, child walks on the run stream.
8. plan-as-object § Thoroughness: the broad search's and the option
   search's targets per depth, the option-search cap and width (D2).
9. vocabulary.md: intervention profile, `intervention_profile_record`,
   entrant, option search, child walk, where tried.
10. Decision sheet rows A1, A2, A9, A10, A11, E1, E2, E4, F2, F3: decision
    column filled with the owner's words (E1, F2, F3 as an edit — D24); E5,
    E6, F13 marked "task 3". Row A9 (instance-of relation, a two-level
    longlist) is **not built**: the card's *What it is* shows the stated
    design features from the records, and a class-versus-implementation
    split waits for evidence from live use.
11. ES components § 7 extract: the selection-free path and the third
    profile; § 1 acquire unchanged.

## Scope / Out of scope

- **In:** the surface-map rows; the migration; ADR 0039; the spec changes
  above; tests (§ Acceptance checks); `verification.md`; `docs/deferred.md`
  deltas (D15's seam, D18, open questions 4 and 7 as bounded here, sheet row
  A9, the cross-task profile memo, the 044 fan-out seam closed).
- **Out:** the shortlist, the proposal, the grid's shortlist state and
  actions, "Assess these N", the quota guards, `shortlist_result` (task 3);
  the variant path (task 3); transferability verdicts and guesses (task 3);
  the sense-check branch, the Sources tab additions (By option, the Options
  column, the read-depth statuses) and export (task 4); the full run (task
  5); the on-demand written summary (seam); "Search further" (044 D10);
  starting retrieval during the baseline pause (D18); the adoptability flag
  (D3); a run-time stability marker (D11); an instance-of relation (A9); a
  general cross-task reading layer (D23); corpus-level document identity
  (#75); any change to the ES chain, the ES extract profiles, characterise,
  group, the clustering engine or the ES search prompts; deep depth; the
  on-demand report from the longlist (ruling 50, deferred).

## Constraints & approval gates

Hard gates this slice touches — approval is this contract's sign-off:

- **Schema / data model:** five new tables (`option`, `option_membership`,
  `option_relation`, `longlist_result`, `intervention_profile_record`); two
  new nullable columns (`task_link.option_id`, FK to `option` with the task
  guard; `capability_run.parent_capability_run_id`, self-FK); one column
  relaxed (`extraction_result.selection_run_id` nullable); the view
  `finding_reference_union` dropped and recreated with a third branch. No
  value rewrites. One alembic revision, reversible: the downgrade drops the
  tables and columns, restores NOT NULL (refusing if a null exists) and
  restores the two-branch view; it refuses while any `capability_run` row
  of a longlist or targeted walk exists (the 044 A5 pattern) and the remedy
  is the same operator script.
- **Runtime egress:** the longlist walk and its child walks reach Overton,
  OpenAlex and the inference route with task data — the same backends,
  transport and verb as the baseline walk; more calls per walk: the broad
  search, up to 15 option searches, the intervention profile over every
  screened-in document on the mini model (about 3,000 prompt tokens each),
  the suggest, clustering, theme, typing and constrain calls; the chat verb
  *add* opens one child walk. No new host. The option-search pool (width
  4), the per-component semaphores around classify's and ingest's fan-outs
  (P5, closing the 044 seam as stated) and the executor cap govern
  concurrency; database connections are measured in the live check and
  the pool size is not changed (production config).
- **Public interface:** the routes in deliverable 11; the confirm-baseline
  response and the chat gate decision carry the opened walk in an optional
  field (the card route stays `204`); `TaskOut.active_run` and
  `has_longlist`; `your_options` and the default preference on the plan
  bodies; `PlanStep` blurbs; the six new stage keys on the run stream
  (additive Literal widening); child walks on the run stream. Everything
  additive.
- **Prompts:** eight new lead-authored surfaces, hash-pinned, every module
  named `*_prompt.py`: the intervention profile
  (`extract_interventions_v1`), suggest (`longlist_suggest_v1`), option
  discovery and assignment (`longlist_cluster_v1`), theme grouping
  (`longlist_theme_v1`), lever typing and ambition (`lever_typing_v1`),
  constrain (`constrain_v1`), the longlist verbs (`longlist_verbs_v1`), the
  option design (`option_design_v1`); and one revision,
  `task_agent_scoping_v3` (the plan slot question and the default
  preference), re-pinned with its diff recorded. The longlist and targeted
  intents are compiled deterministically. Every other pinned hash is
  unchanged: the ES discovery and assignment prompts, the ES search
  prompts, screen, classify, the IOF and ICF prompts.
- **Dependencies, CI, auth, production config:** none. Tenancy (ADR 0033)
  and public read (ADR 0035) predicates are untouched: option rows are read
  through the task's own predicate; a link grants no read (044 A6); the
  label resolver reads a linked task's rows only through an existing
  `task_link`, the same reach `inherit` already has.
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
lever typing, constrain, the option design and the longlist verbs sort on
the judgment model. Reused unchanged: acquire, screen, classify, appraise,
ingest, the clustering engine, the answer core (over several scopes), the
044 turn-sort pattern. Modified: `extract` (a selection-free path, the IOF
rule lifted), the runner (child walks, the fan-out step, the cross-walk
bound), the chat readers (several scopes).

## Disciplines binding this slice

- **Don't flatten status.** Open questions 4 (target size) and 7 (deltas)
  stay open; open question 5 is closed by D8; the residual is a number the
  user sees; sheet row A9 is recorded, not built.
- **Model only what behaves.** No stability marker, no adoptability flag,
  no annotation-layer anchor, no claim rows, no per-run written prose, no
  general cross-task layer (D3, D10, D11, D15, D23).
- **Honest absence.** Zero-document entrants say so; the unclustered and
  not-an-option counts are shown; "no in-scope evidence" names the
  restriction; *none fits* is counted; *absent* is distinct from
  *inherited* in the resolver.
- **Generation is free, interpretation is labelled, assessment is
  grounded** (OS trust). A suggestion needs no source; the report's prose
  is never a source; the ambition tag and every guess carry their label;
  transferability is neither judged nor guessed before assessment; "how
  sure" appears nowhere; every surface carries *scoping pass*.
- **Flag, don't drop.** Thin evidence never excludes; an exclusion keeps its
  reason and can be reversed; a rebuild never deletes an option.
- **Substance is never silent.** A chat verb is confirmed before it is
  applied; every applied verb and every button writes History; the chat's
  re-pointing to the longlist walk is stated.
- **Reuse, never mirror** (owner, 2026-09-07): the engine's public
  functions, extract's profile mechanism, characterise's coverage pattern,
  the ES spine, the walk as the unit of durable execution, the 044
  turn-sort pattern.
- Deferred seams go to `docs/deferred.md`: the on-demand summary; D18; the
  cross-task profile memo; the option search's `guidance` argument (D26,
  unless added in the build); the old unguarded prompt modules; sheet row A9;
  the `task_link` uniqueness note for task 5. The 044 per-run fan-out seam
  is **closed** by the cross-walk bound.

## Stop conditions

Halt and escalate when: a gate above needs more than this sign-off (a new
host, a non-additive API change, a second migration); the runner cannot
dispatch and wait for child walks without changing the Evidence search's
park-and-resume path (the existing steering tests are the fence); the
intervention profile cannot run selection-free without changing the IOF/ICF
path; the longlist walk on the NEET question at rapid depth, option
searches included, cannot finish in a time the owner will accept (report
the measurement and the per-stage split, do not cut a stage); scope would
grow into task 3; or the turn/token budget is spent.

## Acceptance checks

- `make verify` green (okf-validate · test · typecheck · lint · build ·
  drift-check · prompt-guard).
- **Deterministic tests** (backend unless stated):
  - migration round-trip: upgrade, downgrade, upgrade; the downgrade refuses
    while a longlist or targeted `capability_run` exists; `task_link.option_id`
    is nullable and FK-checked to `option` with the task guard;
    `parent_capability_run_id` is a nullable self-FK; the union view has
    three branches after upgrade and two after downgrade;
    `extraction_result.selection_run_id` is nullable after upgrade.
  - start (D1, A2, A23): `confirm_plan` at the gate records the decision,
    ends the baseline walk `succeeded` and opens a longlist walk whose
    intent record has `purpose = longlist` and the confirmed `plan_id`; the
    confirm-baseline route does the same on its new version and returns the
    run in an optional field; both paths hold the dispatch lock and the
    reservation, and a race between them and `POST /runs` in the pre-insert
    window yields exactly one walk; a second confirm while the longlist
    walk runs is 409 `run_active` and a second decision on the same
    check-in is 409 `already_answered`; unattended records and flags the
    standing default and opens the second walk; an ES task has no longlist
    chain (registry).
  - plan and intent (D19–D22): `your_options` validates, is optional, keeps
    verbatim text and turn index, and has an Edit action; every new scoping
    plan carries the default transferability preference, assumed, checked
    at assessment, following Where until edited, removable; the compiled
    longlist intent contains the target unit and outcomes and never Where;
    it contains the setting only when a setting requirement exists; the
    longlist screening criteria carry no place and compose under the
    screen's ceiling; the ES intent compile and the ES query prompts are
    unchanged.
  - pool (deliverable 3): inherited rows are created once per linked
    document with their original origin and the shared snapshot id, by the
    inherit step; the longlist scope re-screens inherited, baseline and new
    documents in one generation; the label resolver returns a linked task's
    classification and appraisal with provenance, returns *absent*
    distinctly, re-appraises on a rubric-version mismatch, and never
    inserts rows for the scoping task; classify and appraise skip resolved
    rows; two documents sharing a normalised DOI count once in coverage and
    the header counts and stay two membership rows; a document without a
    DOI counts as itself; evidence restrictions land on acquire as
    `ScopeConstraints`; the six progress beats are emitted at their
    boundaries.
  - suggest and option searches (deliverable 4): the suggest step reads the
    plan, the baseline and the linked report and yields at most the bound,
    each with a design, labelled *suggested by Policy Atlas* or *from your
    evidence search* with the report section named; no profile record is
    ever created from the report; the plan's own options become entrants
    labelled *added by you*; every entrant gets one child walk under its own
    targeted scope with `parent_capability_run_id` set; at most 15 per
    longlist walk with the user's and the report's never dropped; the
    cross-walk bound holds at width 4 under a concurrency test; a failing
    child degrades the parent and the longlist still exists; an entrant
    whose search finds nothing survives with zero documents; a document an
    option search returns that is already in the pool is the same row; the
    option-search target per backend is the constant.
  - intervention profile (deliverable 5): runs over every screened-in
    document of a scope with no selection run and no IOF profile; the
    registry, harness graph and plan mapping know `extract_interventions`;
    Non-evidence documents are profiled; a document covering no
    intervention is recorded as such; memoised per (task, snapshot,
    fingerprint) and reused across the longlist and targeted scopes;
    comparator records never become members; setting and study geography
    are read from the abstract; the IOF/ICF path is unchanged (existing
    tests); the record joins the union view with kind `interventions`.
  - longlist (deliverable 6): every record is assigned to one option,
    unclustered or not an option (code-enforced exhaustiveness); a document
    with three records can belong to three options; the engine's own tests
    pass with no source change to `clustering_engine.py`; a bundle mints a
    package with *part of* rows; each option has exactly one primary lever
    type from the constant list or *none fits* with a reason, the taxonomy
    version, and an ambition tag with a justification and the reasoning
    words; the runner-up is in `longlist_result` and not on the read model;
    coverage buckets Unknown and Non-evidence separately, shows the role
    funnel, where tried grouped against Where, settings, and counts flagged
    members; seeds are assigned against and survive with zero members;
    finding units from a linked deep task cluster alongside profile records
    (D5); the ceiling formula; characterise and group outputs unchanged
    (existing tests); membership rows carry a reason and the flag.
  - constrain (deliverable 7): a requirement breach excludes with the
    constraint named; a setting requirement is judged; the three default
    screens run and cite; *distinct* never excludes a *part of* row; thin
    evidence never excludes; every preference except the transferability
    preference yields one capped guess per option, and that one yields
    none; a fixture with an inherited document outside the country group
    marks its only option no in-scope evidence, included, with the
    restriction named; guesses never change state; the in-scope check makes
    no backend call.
  - records (deliverable 8): judgements and guesses are keyed by
    `(option_id, design_version)`; a rebuild keeps option ids and user
    states, re-runs option searches only for new entrants, and never
    deletes an option; a user exclusion carries its reason and is
    reversible; no annotation row is written by the longlist walk.
  - longlist verbs (deliverable 10): a turn while the longlist exists and no
    walk is active is sorted; a question is answered over the union of the
    longlist and targeted scopes with citations, including a document only
    an option search found; a verb is confirmed before it is applied and
    never inferred; *add* proposes a design back through `option_design_v1`,
    mints the option as *added by you* and opens a child walk with no
    parent; *exclude* records the reason; the button routes and the verbs
    write the same state and one History event each; a turn while a walk
    runs is 409 `run_active`; an ES task's turns are unchanged; the ordinary
    chat resolves the longlist walk after it runs.
  - API (deliverable 11): the routes; org-scoped read in the ADR 0033 style
    (a link grants no read of options; the resolver reads only through an
    existing link); OpenAPI additive.
  - frontend (vitest): Result opens on the longlist when the existence
    signal is set and on the baseline before; the view switch; the scoping
    pass label; the counts header; the Show filter, the setting facet and
    the where-tried facet; theme sections collapse; an option row shows
    origin, state, exclusion reason and relation; the reduced grid lays
    tiles by lever type and ambition, shows states, and has no shortlist
    action; the option card renders its sections including *Where tried*,
    the transferability row as "checked at assessment", and never the words
    "how sure"; Exclude asks for a reason; Add an option posts once; the
    plan document shows the new slot and the default preference with Edit,
    "Longlist built · N options", and *built from plan version N* with
    Rebuild longlist after a plan change; the thread renders a confirmed
    verb and the progress beats.
- **No AI eval in this slice.** Option quality is judge behaviour and goes
  to the eval slice. `verification.md` records three live longlists (NEET
  rapid; NEET standard, once, for the numbers; one linked start at rapid
  with inherited documents and a user option in the plan) with their
  compute times split by stage (suggest · option searches · broad search ·
  profile · clustering · constrain), the counts at each funnel stage
  (candidates · screened in · records · options · unclustered · not an
  option · excluded · none fits), the where-tried grouping on the NEET cards
  (the international-evidence check for D20), and a qualitative reading
  against the trust rules.
- **Live check (pinned scope, at rapid depth, ~45 minutes):** local app,
  real egress. (a) New NEET scoping task started from the completed NEET
  Evidence search; in planning, name one option of your own and see the
  default transferability preference; confirm; the baseline builds (as in
  044). (b) Confirm plan and build longlist → the beats appear, the child
  walks run in parallel, the Result opens on the longlist; compute time and
  stage split recorded. (c) Read the list: themes, an option *suggested by
  Policy Atlas*, the one *added by you* with its option search's documents,
  one *from your evidence search* naming the report section, one excluded
  with its constraint, the Do nothing sentence, the setting and where-tried
  facets; where tried on the cards includes non-UK implementations. (d)
  Open the grid; open one option card; Show the documents. (e) In the
  thread: "exclude the sanctions option, we can't do that" → confirmed →
  excluded with the reason; Include again by button; "add a youth mentoring
  scheme" → design proposed back → confirmed → the child walk runs → the
  option appears *added by you*; History shows the three actions. (f)
  Change the plan (add a requirement) → the longlist is marked built from
  version N → Rebuild longlist → the excluded option keeps its state and
  the added one its id (second compute time). (g) One question in the
  thread about the added option, answered with citations from its own
  search's documents. No ES live run: the ES chain is untouched and the
  engine's two existing callers are pinned by tests.

## Verification evidence expected

Command tails; the migration round-trip output; the OpenAPI diff
(additive); the prompt-hash diff (eight new entries, one re-pin, nothing
else changed); the three live longlists' funnel counts and stage-split
compute times; the intervention profile's token cost per document and the
option search's cost per entrant; the cross-walk bound's measured effect;
live-check notes and screenshots for (a)–(g); the spec diffs with quoted
rulings; the decision sheet's filled columns; the `docs/deferred.md` delta;
known gaps.

## Risk tier & review focus

**Tier 4** — a migration with five new tables, two columns, a relaxed
constraint and a recreated view; runtime egress for a new walk kind with
child walks and two fan-outs (per document and per entrant); additive
public API; eight prompt surfaces and one revision: ADR 0039 with a
rollback plan, human-approved plan, adversarial review at the contract
(done, fallback lane) and plan stages (`codex-rescue` read-only if the
spend cap is raised, else the fallback lane), the step-7 stack per the
spine (contract verifier · `/code-review medium` · one security lane scoped
to the new routes, the longlist verbs, the option read predicate and the
label resolver's cross-task reach · `/simplify` · human deep review).

Rollback shape (ADR 0039 names the commands): quiesce the API; `alembic
downgrade -1` refuses while a longlist or targeted `capability_run` row
exists (the 044 A5 pattern); the remedy is the existing operator script
extended to those walks; the downgrade drops the five tables and two
columns, restores NOT NULL on `extraction_result.selection_run_id`
(refusing while a null row exists) and the two-branch union view; deploy
the previous image.

Review focus: the ES chain, characterise, group, the clustering engine and
the ES search prompts byte-for-byte unchanged; the intervention profile
never touches the IOF/ICF path; the longlist intent and screen never carry
Where; no option row and no linked label is readable without an existing
link; a guess never excludes and never feeds any proposal; no
transferability verdict or guess before assessment; "how sure" appears
nowhere; every surface carries *scoping pass*; every exclusion carries a
constraint; comparator records never count; the report's prose is never a
source; the unclustered and not-an-option counts are visible; a verb is
never applied unconfirmed; the rebuild never deletes an option; the child
walks are bounded and a child failure never fails the parent; the two new
start paths cannot race `POST /runs`; the additive-only OpenAPI diff.
