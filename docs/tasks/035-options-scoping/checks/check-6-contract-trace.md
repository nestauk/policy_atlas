# Feasibility check 6 — contract trace

Source: `../feasibility-checks.md` § 6. Question: can the declared components compose without hidden changes to
ownership, evidence eligibility, extraction profiles, context or output semantics?

Method: two cases traced on paper through every component in
`docs/specs/capabilities/options-scoping/components.md`, in pipeline order, and through the three
compositions. Each claim was checked against the four system contracts (execution-orchestration,
data-model, plan-as-object, provenance-grounding), the Evidence search components spec, and the
as-built schema (`backend/src/policy_atlas/core/schema.py`, dev at 81aa7174). The spec is
read-only here. Every proposed change is a finding.

Date: 2026-09-08. Branch `checks/035-feasibility`.

## The two cases

**Case A — inherited question (ruling 22).** An Evidence search task on "What reduces the number of
young people who are NEET (not in education, employment or training) in England?" ran the deep
chain (select, extract with both profiles, group). The user starts a scoping task from it through a
Link. Depth asked: standard. Constraints: "no benefit cuts" (scope-shaped), "low cost" (cost-shaped,
checked after assessment), "OECD evidence only" (evidence-scope).

**Case B — user-edited variant (rulings 15, 36).** In the same task, the longlist holds the option
"Youth guarantee" (offer of a job, training or education within four months, with a benefit
sanction for refusal). The user writes "assess it without sanctions". The agent judges this a design
change and mints "Youth guarantee without sanctions", added by you, *variant of* the parent.

## Reading the tables

Column *records* names the as-built table where one exists, in backticks, and gives a plain name
where the spec declares a record with no table yet. Column *gap* carries a finding number
(**F1**–**F18**, ranked in § Findings) or "none".

Facts about the build that shape both traces:

- Every Evidence search result row (`source_screening_result`, `source_classification_result`,
  `source_appraisal_result`, `characterisation_result`, `selection_result`, `extraction_result`,
  `synthesis_result`) is keyed by `evidence_scope_id`. The `evidence_scope` row is the id-keyed
  intent record: one `intent` text, one `context` JSON. A plan carries one `evidence_scope_id`.
- Cross-task FK guards require a result row and its parents to share `task_id`. No result row can
  be read as another task's result. A document enters a task once (`task_source_snapshot`, unique
  on task × snapshot) and points at the shared, content-addressed `source_snapshot`, whose chunks
  and embeddings cross tasks for free.
- The extraction memo key is `(task_id, source_snapshot_id, extraction_fingerprint)`. The
  data-model contract says memo by `(source snapshot, fingerprint)`. The build is task-scoped; the
  contract is not.
- Annotations (claims, patterns, gaps) key on `(block, unit, type)`. There is no other anchor.
- There is no Link table. "Link" and "Context" are vocabulary entries only.

## Trace A — inherited NEET question

### A0–A1 · inherit, plan, ⟨baseline⟩, gate

| step | in | out | records | gap |
|---|---|---|---|---|
| 0 inherit (scoping direction) | a Link to the Evidence search task | draft plan seeded from its question; its screened-in documents queued *inherited*; its report's theme claims and grouping rows queued as longlist suggestions; its abstract-profile extractions where they exist; its IOF and ICF findings at finding grain | new `task`; new `task_source_snapshot` per inherited document (points at the shared snapshot; `origin` has no value for "inherited"); the Link itself has no record; the deep findings are in the source task's tables and cannot be read across the FK guard, so they are copied or re-extracted; the abstract profile does not exist in the source task (Evidence search never ran it), so "reused by memo" is empty in case A and, when it does exist, the memo key includes `task_id`, so a cross-task lookup misses | **F6** Link has no record · **F7** inherited flag and classify/appraise crossing · **F3** memo and finding reuse are task-scoped |
| 1 plan | the seeded question; the conversation | plan object: question · what we are trying to change · target unit (young people 16–24) · where (England) · outcomes (NEET rate, sustained employment) · depth = standard · three constraints, each tagged by origin and by kind · steps · check-ins | `plan` (payload JSON, versioned) and one `evidence_scope` compiled from it (intent text + context) | **F5** the evidence-scope constraint has no compile target · **F10** stated user context has no promoted home · **F12** one plan, several scopes |
| ⟨baseline⟩ acquire → screen → classify → appraise → ingest | the plan's question as intent; grey-literature-weighted backend policy (Overton, OpenAlex) | a screened-in set about the NEET problem itself (statistics, trend reports, rival explanations) | `search_coverage_record`; `task_source_snapshot`; screening, classification and appraisal rows under **a baseline `evidence_scope`** whose intent ("the problem and its trend") differs from the longlist scope's intent ("interventions for these outcomes") | **F12** baseline is its own scope; Sources must show both |
| ⟨baseline⟩ synthesise(baseline) | the baseline scope's chunks | the "Do nothing" profile: what is in place · trend · who is affected · what is already changing · what is contested · cost of inaction · key assumption · sources | `artefact` + `block`s + `synthesis_result`; claims and gaps as annotations; the key assumption and what is contested as tier-4 reasoning claims | none; the baseline composes as declared |
| gate: confirm plan against baseline | the baseline; chat | a confirmed plan version | `plan` version bump; steering event | none |

### A2–A5 · the spine at longlist depth, plus extract(abstract)

| step | in | out | records | gap |
|---|---|---|---|---|
| 2 acquire | the plan as intent; seed corpus = inherited documents; `scope_filters` where the backend can express them | candidate documents beyond the inherited set, metadata only | `search_coverage_record` (depth, filters, stop condition); new `task_source_snapshot` rows for added documents | **F5** "OECD evidence only" cannot be a backend filter (backends filter by institution country, not study geography) |
| 3 screen (stage 1, unchanged) | every document in the longlist scope, inherited and added, title + abstract; the plan as intent | `is_relevant`, confidence, `screen_basis`, stage 1 | `source_screening_result` under the longlist scope; inherited documents get **new** rows (their old rows belong to the source task and a different intent) | none; re-screening is as ruled. **F5** the screen cannot apply the evidence-scope constraint: it is relevance-only (ruling 43) and runs before study geography is known |
| ingest | screened-in set | full text fetched where possible; `text_basis` per snapshot | shared `source_snapshot` + `chunk` + `chunk_embedding` (already present for inherited snapshots) | none |
| 4 classify | screened-in set | `primary_evidence_type` (incl. Unknown, Non-evidence) + open tags | `source_classification_result` under the longlist scope; `source_tag` rows. Inherited documents' classifications cannot be read across the guard | **F7** copy with provenance when the classifier version matches, else re-run (the 🟡 in components.md § 0) |
| 5 appraise | screened-in evidence types | quality tier + `rubric_version`; Unknown and Non-evidence skipped-and-counted | `source_appraisal_result` under the longlist scope; same crossing problem | **F7** |
| 10 extract(abstract) | **every** screened-in document, Non-evidence included | per document: interventions named (none / one / several), setting country, population, outcome family, design hint | no record kind exists. The fields match the shared source-named reference vocabulary (`intervention`, `outcome`, `population`, `setting`, `study_geography`, `study_design`) plus a mention grain. As built, `extract` requires a selection (`extraction_result.selection_run_id`) and excludes Non-evidence | **F2** declare the mention record as a third finding kind on the shared vocabulary and an `all_screened_in` select strategy that includes Non-evidence |
| evidence-scope set-aside (not a declared step) | abstract-profile `study_geography`; the "OECD evidence only" constraint | documents outside the scope set aside with the reason; counted; shown on Sources; never support, never a reason to exclude an option | a set-aside status per `task_source_snapshot` × constraint. No home | **F5** this is where the constraint acts, deterministically, after extract(abstract) and before longlist |

### A6–A8 · longlist, constrain, shortlist

| step | in | out | records | gap |
|---|---|---|---|---|
| 6 longlist | mention records (in-scope documents); inherited IOF/ICF findings at finding grain; the inherited report's theme and grouping rows as suggestions; lever-type taxonomy; user additions | options (name · description · specified design v1 · constituent interventions with documents · outcomes served · primary and secondary lever type · ambition tag as a tier-4 claim · relations); themes; per-option coverage (counts by evidence type and tier, countries, populations, outcomes) as metadata-grounded pattern claims | option rows (declared in data-model, no table yet); design version rows; **membership** rows (mention or finding → option id + design version); relation rows; theme grouping (run-local, like characterise); pattern claims and the ambition claim need an anchor and **have none**: annotations key on block units, an option is not a unit | **F1** the option needs to be an addressable unit kind · **F12** membership keys on `task_source_snapshot`, not on scope, so coverage unions across scopes |
| 7 constrain | options with coverage and designs; the plan's constraints | per option: included · excluded: breaks "no benefit cuts" · no in-scope evidence; a labelled reasoned guess for "low cost"; the three default screens applied | state records against the option id (declared); the reasoned guess and the screen judgement are reasoning claims that again need an anchor | **F1** · **F5** "no in-scope evidence" is derived from the set-aside records |
| 8 shortlist | included options with coverage and relations; user additions | one place per primary lever type present, one named reason each; gap messages; warnings; the unassessed list | shortlist state records against option ids (declared); the assembly record (each place, reason, who filled it), gap messages and warnings need a run-keyed result row for export; none is declared | **F15** declare `shortlist_result` |
| gate: "Assess these N" | the proposal | N options in state *on the shortlist* | steering event | none |

### ⟨assess⟩ per shortlisted option — "Youth guarantee" (parent)

| step | in | out | records | gap |
|---|---|---|---|---|
| targeted acquire → screen → classify → appraise → ingest → extract(abstract), if thin | the option's specified design as intent | more mentioning documents | a **per-option `evidence_scope`**; new result rows; new mention records; membership updated | **F12** |
| 9 select (scoping strategy) | the option's mentioning documents (membership); abstract-profile fields (implementation, outcome family); `text_basis`; the per-option cap | the read set; omissions with reasons | `selection_result` (strategy, budget, selected, excluded) under the per-option scope. Input widens from Tier-0 columns to abstract-profile fields | **F14** note the widened input on the shared `select` tool |
| 10 extract(light) | the read set; inherited IOF findings for the same snapshots | direction per outcome family, magnitude with comparator, population and period, design, setting; only the requirements an inherited finding does not satisfy | the light field set is a subset of IOF, so it can write `intervention_outcome_finding` under its own profile id with `field_coverage` marking what was not extracted. "Skip only satisfied requirements" is field-grain resolution across two profiles; the build resolves whole records by fingerprint | **F3** |
| attribution (not a declared step) | the light findings; the option list with designs | which findings belong to which option design (support binds to finding + design, ruling 36) | membership rows at finding grain. No component is named to write them: extract is per source and does not know options; select is pre-reading; synthesise consumes | **F4** ⟨assess⟩ needs `longlist` in assign-only mode at finding grain after extract(light) |
| 11 synthesise(profile) | the option's chunks within the read set (full text) and its mentioning documents (abstracts); eligible findings; the baseline's retrieved context; user context | verdict strip · sections · the transferability working (column-grounded block) · how sure = a finding-query pattern over eligible findings | `artefact` + `block`s + `synthesis_result`; the column-grounded block kind and its verify rule are declared in provenance-grounding but not built in `produce-grounded-block`. As built, synthesise's `search_chunks` ranges over the whole screened-in corpus with the selection as a soft prior; the per-option cap is therefore not a boundary on reading | **F4** a hard `reading_scope` parameter · **F10** user context input · **F11** geography level and date on the retrieved-context citation |
| 11 synthesise(report, assessed) | all assessed profiles; the longlist with states; the shortlist record; the baseline; omissions | the report; the comparison table as a working view | `artefact` + `block`s | **F15** the report's "what was not read" reads `selection_result.excluded` and the set-aside records; both must exist as records |
| export | the report and attachments | bundle | Share seam; none | none in scope |

### ⟨full run⟩ for "Youth guarantee" — inherit in the Evidence search direction (ruling 48)

| step | in | out | records | gap |
|---|---|---|---|---|
| 0 inherit (Evidence search direction) | a Link from the scoping task naming one option | draft plan: question = the specified design; user context and evidence-scope constraint as inputs; the option's mentioning documents with classify and appraise results and abstract profiles, queued *inherited*; the light findings at finding grain | new `task` in the same project and visibility; new `task_source_snapshot` rows; classify/appraise/abstract-profile rows cannot cross the guard (copy or re-run); light findings cannot cross the task-scoped memo; the Link has no record | **F6** · **F7** · **F3** — the same three gaps as the scoping direction, which confirms one procedure serves both |
| 1 plan · 2–5 spine · stage 2 · characterise · 6 select · 7 extract(both profiles) · 8 group | as Evidence search | as Evidence search; extract skips only requirements a light finding satisfies (field grain) | as Evidence search | **F3** |
| attribution against the specified design | IOF and ICF findings; the one option's design | eligible findings for the "how sure" cell | `group` clusters by the intervention facet but not against a fixed specified design; membership against a design is not produced by any Evidence search component | **F9** `group` needs a fixed-target-list mode, or `longlist(assign)` is composed into the child |
| 9 synthesise with the profile template | the eligible findings; user context; the column-grounded block kind | the report that **is** the option profile, with the judgement cells | child `artefact`; the block kind lands once in the shared `produce-grounded-block` and serves both compositions | **F9** · **F10** |
| one document, two homes (ruling 47) | the child artefact | shown in place in the scoping task, tagged *full run*; the scoping-pass profile "is the prior version in History" | `artefact.task_id` is the child's; history is linear **per artefact** and an artefact lives in one task, so the scoping-pass profile (a block in the scoping task's artefact) cannot be a prior version of the child's artefact. It is a derivation edge in the cross-artefact DAG plus a display convention | **F8** |

## Trace B — the variant "Youth guarantee without sanctions"

Rows identical to trace A are marked "as A". The variant enters after the longlist exists.

| step | in | out | records | gap |
|---|---|---|---|---|
| chat turn → 6 longlist (mint) | "assess it without sanctions"; the parent option | the agent states its judgement that this is a design change; a new option *added by you*, design v1 = the parent's design minus the sanction, *variant of* the parent; inherited claims suspended → state "not yet assessed" | option row; design version; relation row; the judgement is a stated reasoning claim with no anchor | **F1** · **F13** "assess it" is a longlist edit, a shortlist add, or an assess-gate trigger; the spec does not say which |
| 2–5 spine for the variant (concept § Shape 2, ruling 15) | the variant's specified design as intent | its own small screened-in set | a **per-variant `evidence_scope`**; result rows for documents already in the task get new rows under the new scope; the `task_source_snapshot` is shared | **F12** |
| 10 extract(abstract) | the variant scope's screened-in set | mentions; most name the parent design, some name sanction-free guarantees | mention records; memo hits for snapshots already extracted (same task, same fingerprint) | **F2** |
| evidence-scope set-aside | as A | as A | as A | **F5** |
| 6 longlist (assign) | the new mentions; the fixed option list | membership: a mention of a sanction-free guarantee → the variant; a mention of a guarantee with a sanction → the parent; a mention that does not state the obligation → a labelled judgement (ruling 36 says support binds to the design; the abstract profile's `intervention` is source-named text, so the assignment is an LLM judgement, shown) | membership rows at mention grain, per design version | **F4** the "intervention as implemented" field (ruling 44.1) is what makes this assignment possible; the abstract and light profiles must carry it |
| 7 constrain | the variant's design and coverage | "no benefit cuts": the parent breaks it, the variant does not; the *distinct* screen never excludes a variant; thin evidence noted, never a reason | state records | none; the design-level rule holds |
| 8 shortlist | included options incl. the variant | parent and variant share a primary lever type, so Policy Atlas proposes at most one of them; the variant is on the shortlist only if the user adds it; the package warning does not fire (variant-of, not part-of) | shortlist state records | **F13** whether minting from "assess it" adds the variant to the shortlist |
| gate: "Assess these N" | | | | **F13** |
| ⟨assess⟩ select | the variant's mentioning documents, possibly none | the read set, possibly empty → honest empty cells (ruling 15) | `selection_result` | none |
| ⟨assess⟩ extract(light) | the read set; the parent's light findings for shared snapshots | a parent finding on a guarantee **with** a sanction does not satisfy a variant requirement, so it is not skipped; the field-grain rule needs the intervention-as-implemented to decide | as A | **F3** · **F4** |
| ⟨assess⟩ attribution | the variant's light findings | eligible findings for the variant only | membership at finding grain | **F4** |
| ⟨assess⟩ synthesise(profile) | the variant's read set; its eligible findings; the parent's findings as *related evidence for a different design* (section "What it is made of" only) | profile; the parent's evidence never in the row or the report | as A; the "related evidence" section is a chunk- or finding-cited block whose citations are the parent's sources, so the citation-scope rule (source, never block) holds | **F4** the reading scope must admit the parent's documents for that one section while the cap still governs |
| synthesise(report) | | the variant's row shows only its own evidence | | none |
| ⟨full run⟩ | as A, with the variant's design as the question and the parent's findings not inherited | as A | as A | **F9** · **F3** · **F6** · **F7** · **F8** |

## Findings, ranked by whether they change the design

**Changes the design — substantial new I/O the origin column did not admit, or a shared invariant
missing from the system contracts.**

- **F1 — Claims about an option have no anchor.** The ambition tag, the reasoned guess, the
  coverage pattern claims, the constraint judgement and the relation rationale are all declared as
  claims. Claims are annotations keyed on `(block, unit, type)`, and unit ids change on
  regeneration. An option is a stable task-scoped entity, not a unit. Proposal: data-model declares
  the **option as an addressable-unit kind** (stable id, not bound to a block version), so the
  annotation layer and `produce-grounded-block` verify serve it unchanged. Affects tasks 2 and 3.
- **F2 — The abstract profile is a third record kind, and `extract` must take every screened-in
  document.** Neither finding schema fits (IOF needs an effect, ICF needs a claim). The abstract
  profile's fields are the shared source-named reference vocabulary plus a mention grain, so the
  record joins `finding_reference_union` and `longlist` reads mentions and inherited findings as
  one unit shape. As built, `extract` needs a selection and excludes Non-evidence; ruling 43 keeps
  "extract takes a selected set". Proposal: declare `intervention_mention` in data-model as a finding
  kind with its own fingerprint domain; declare an `all_screened_in` select strategy that includes
  Non-evidence (ruling 43.2: a Non-evidence document counts as a mention). Mark extract(abstract)
  **EB modified**, not "is EB". Affects task 2.
- **F3 — Finding reuse at finding grain (rulings 35, 48) is not what the build does.** The memo key
  is task-scoped and whole-record. Both inherit directions depend on cross-task, field-grain reuse
  within one schema (a light IOF record satisfying some requirements of the full IOF profile, and the
  reverse). Proposal: data-model states two invariants — the memo key for **acquired** snapshots
  drops `task_id` (they are already a cross-task substrate; uploads stay task-private), and
  requirement resolution is at field grain within a schema, recorded through `field_coverage`, with
  the intervention-as-implemented as a match key. This is Evidence search work too, so it wants its
  own ADR. Affects tasks 1 (inherit), 3 and 5.
- **F4 — Reading budget and evidence eligibility (seam 44.1) — settled by the trace.** Two grains,
  two mechanisms. (i) The **read set** is a hard boundary on what synthesise may read in ⟨assess⟩,
  which contradicts the Evidence search's "a selection is a soft prior, never a boundary". Proposal:
  execution-orchestration declares a `reading_scope` parameter on synthesise (full text: the read
  set; abstract only: the option's mentioning documents; plus, for the one "related evidence"
  section, the parent's documents), with chunks outside it not retrievable in that composition and
  omissions represented. The data-model's soft-prior rule is about intent scoping and is untouched.
  (ii) **Eligibility** is the per-option finding-grain membership record, written by `longlist` in
  assign-only mode after extract(light). ⟨assess⟩ currently omits this step. Proposal: add
  "longlist(assign, finding grain)" to the ⟨assess⟩ composition; require both extraction profiles to
  carry `intervention` as implemented (ruling 44.1 already asks this). Affects task 3.
- **F5 — The evidence-scope constraint (seam 44.2) cannot act at the screen.** The screen is
  relevance-only and runs before study geography is known; study geography comes from the abstract
  profile (ruling 43.1), and backends cannot filter by it. Proposal: the plan contract gains a third
  policy face that compiles to (a) `scope_filters` where a backend can express them and (b) a
  **deterministic set-aside** over abstract-profile columns after extract(abstract) and before
  longlist, writing a status per `task_source_snapshot` × constraint (set aside: outside evidence
  scope), counted on Sources, never support, never an option exclusion. components.md § 3's
  "applied at retrieval and here" should read "at retrieval where expressible, and as a set-aside
  after the abstract profile". **Name collision:** the code's `evidence_scope` table is the intent
  record; the constraint must not be compiled into it and should carry a different code name
  (`source_scope_constraint` or similar). Affects tasks 1 and 2.
- **F6 — A Link has no record.** `inherit`'s declared input does not exist in the data model.
  Proposal: data-model declares `task_link` (source task, target task, kind, optional option id,
  created by, created at). Both inherit directions read it; the option entity's "link to the child
  task" is one row of it. Affects task 1.

**Clarifies the design — no new I/O, but a rule the contracts must state.**

- **F7 — What crosses a Link, record by record.** Snapshots, chunks and embeddings cross for free
  (shared substrate). Screening never crosses (re-screen, as ruled). Classify and appraise rows
  cannot be read across the FK guard. Proposal, settling the 🟡 in components.md § 0: copy as an
  inherited assertion (new row, `asserted_by` = inherit, source run recorded) when the classifier or
  rubric version matches the current default, else re-run. The inherited flag is a nullable
  `inherited_from_task_id` on `task_source_snapshot`, **not** a new `origin` value (`origin` is a
  closed column that egress and appraisal read). Affects task 1.
- **F8 — "One document, two homes" is a derivation edge, not a shared version chain.** History is
  linear per artefact and an artefact belongs to one task. The scoping-pass profile is a block
  version in the scoping task's artefact; the child's report is a new artefact. Proposal: the child
  artefact carries a derived-from edge to that block version; the scoping task renders the child's
  artefact through the option's child-task link and shows "what changed" from the edge. Ruling 47
  holds; its word "version" is display language. Affects task 5.
- **F9 — Ruling 41 stands, on one condition.** The child can compute the judgement cells inside the
  widened boundary if three things hold: synthesise accepts the profile template as a fail-closed
  scope directive; the column-grounded block kind and its verify rule land once in the shared
  `produce-grounded-block`; and the child produces membership against the **specified design**,
  which no Evidence search component does today (`group` clusters by intervention facet, not against
  a fixed design). Proposal: `group` gains a fixed-target-list mode (discovery skipped, assignment
  against a given list) on the shared clustering engine; `longlist(assign)` is the same call. Without
  it "how sure" cannot be computed in the child, and 41 would need revisiting. Affects task 5.
- **F10 — User context must be promoted structured state.** "Stated by you" and "planned by you"
  entries arrive in chat, often after the plan is confirmed. Capability agents never read
  transcripts. Proposal: a typed `user_context` entry set under the plan's Assumptions section
  (type stated | planned, verbatim `user_text`, date, decision-event provenance), versioned with
  the plan and carried by `inherit`. This also removes the verbal trap in trust.md: "a cap lifted by
  a plan" is impossible, yet stated facts live in the plan object; the type on the entry is what
  decides, not its home. Affects tasks 1 and 3.
- **F11 — The retrieved-context cell needs level and date.** Ruling 34 decides applicability by the
  geography level and recency of the retrieved fact. The column-grounded block declaration types
  the cell but names no fields. Proposal: add geography level and observation date to the *Your
  context: retrieved* cell in provenance-grounding. Affects task 3.
- **F12 — One scoping task holds several `evidence_scope` rows.** Baseline, longlist, one per
  variant, one per thin option's targeted acquire. Per-option coverage unions across scopes;
  membership keys on `task_source_snapshot`; Sources shows the baseline scope as Landscape and the
  rest By option. The plan compiles to more than one intent record, which plan-as-object's "a plan
  carries one scope" wording does not admit. Affects task 1.

**Ambiguities — no design change, but a contract must pick.**

- **F13 — Minting a variant from "assess it without sanctions".** Ruling 15 says the variant "gets
  its own mini search". The gates say nothing after shortlist runs until "Assess these N". Read
  as: the chat turn mints the variant (longlist edit) and adds it to the shortlist as *added by
  you*; assessment still waits for the gate, which the agent offers immediately with N = 1. The
  contract for task 3 should state this.
- **F14 — `select` reads finding-layer fields.** The scoping strategy stratifies by implementation
  and outcome family, which are abstract-profile fields, not Tier-0 columns. Note on the shared tool.
- **F15 — The shortlist assembly record has no home.** Reasons, gap messages and warnings are
  exported. Proposal: a run-keyed `shortlist_result` row, like `selection_result`. Task 3.
- **F16 — The baseline's retrieved context cites sources, not the baseline block.** The
  citation-scope rule already requires this. Record it in trust.md so the transferability working
  is not built to cite a sibling artefact.
- **F17 — Deltas after a plan change** (open question 7) touch every scope and every membership
  record. Out of this check; the multi-scope layout (F12) makes deltas per scope, which helps.
- **F18 — Non-evidence in the source-quality profile.** Appraise skips-and-counts Unknown and
  Non-evidence; the profile shows them as buckets. Consistent; no change.

**Confirmed as declared:** `inherit` is one procedure in both directions (the record operations are
identical; only the plan seed and the suggestion mapping differ by source kind), so ruling 48
holds. ⟨baseline⟩ composes without change. `longlist`, `constrain` and `shortlist` produce exactly
the I/O their rows declare. The screen is unchanged. The light profile is an IOF subset and needs
no new schema.

## What this means for task 1 and task 2's contracts

**Task 1 — shell and baseline.** Its contract owns the shared records the whole capability stands
on, and should land them in the system contracts first:

- `task_link` (F6) and `inherited_from_task_id` on `task_source_snapshot` (F7), with the
  copy-or-rerun rule for classify and appraise.
- The plan's three constraint kinds with the evidence-scope face compiling to a set-aside predicate,
  under a code name that does not collide with `evidence_scope` (F5). The set-aside step itself is
  task 2's, but its record is declared here.
- The typed `user_context` entry set under Assumptions (F10).
- A plan that compiles to more than one `evidence_scope` (baseline and longlist at least), with
  Sources showing both (F12).
- The memo-key change for acquired snapshots (F3) if `inherit` is to reuse anything beyond
  snapshots and chunks; otherwise task 1 should state that inherit copies findings and the ADR moves
  to task 3.

**Task 2 — longlist.** Its contract mints the option entity and must add:

- The option as an addressable-unit kind so its ambition tag, coverage patterns, constraint
  judgements and reasoned guesses are ordinary annotations (F1).
- `intervention_mention` as a third finding kind on the shared reference vocabulary, joining
  `finding_reference_union`, with `intervention` as implemented; the `all_screened_in` select
  strategy including Non-evidence; extract(abstract) re-marked **EB modified** (F2).
- The deterministic evidence-scope set-aside after extract(abstract), before longlist (F5).
- Membership keyed on `task_source_snapshot` and design version, unioned across scopes (F12), and
  `longlist` declared with an assign-only mode so task 3 can call it at finding grain (F4).
- The F13 reading of "assess it" as mint + add-to-shortlist + offer the gate.

Tasks 3 and 5 inherit F3, F4, F8, F9, F11, F14 and F15 from this list; none of them changes what
task 1 or 2 must build, but F3 and F9 want ADRs of their own because they change the Evidence
search.
