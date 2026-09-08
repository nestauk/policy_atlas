---
type: Capability spec
title: Options Scoping — component skeleton
description: The OS components — the Evidence search spine reused as is at longlist depth, three OS variations, two new components, and the named compositions (baseline, assess, full run) that give the three depths.
tags: [capability, options-scoping, components]
timestamp: 2026-09-07
---

# Options Scoping — component skeleton

The components, their origin in the Evidence search (EB), their declared I/O, realisation and
gating. Distilled from
[options-scoping-concept.md](../../sources/options-scoping/options-scoping-concept.md) (§ Shape,
§ Architecture stance, rulings 2–6, 9, 11, 12, 14, the review-round rulings 15–44). Shared tools
and the findings schema are owned by
[../../system/execution-orchestration.md](../../system/execution-orchestration.md) and
[../../system/data-model.md](../../system/data-model.md); the EB components referenced below are
specified in [../evidence-search/components.md](../evidence-search/components.md).

**Reuse rule (owner, 2026-09-07).** Components are discrete so they can be shared across
capabilities and combined into gradations of one
([vocabulary.md § Components](../../vocabulary.md)). Every OS component is marked **is EB** (an
Evidence search component, possibly parameterised), **EB modified** (a variation: a new object,
template or field set) or **new**, and every "new" is justified. The EB's mandatory spine —
acquire, screen, classify, appraise, ingest — runs **as is** at longlist depth; OS adds three
variations (plan slots, `longlist`, `constrain`) and two new components (`inherit`, `shortlist`); `inherit` is now **shared**, the Evidence search having adopted it for the reverse direction (ruling 48).
The three depths of ruling 3 are **compositions** of these components, not components themselves.
Honesty about what "reuse" means (pass-3 review): by the execution contract's I/O test, `longlist`
and `constrain` are OS components in their own right, **built on the shared EB engines** (the
two-stage grouping engine and deterministic coverage utilities; the per-item judgment fan-out) —
nothing is mirrored, but their I/O is new. Reuse of the spine also asks three **declared changes to
EB interfaces** (ruling 43): `extract` registers two new profiles (an **abstract profile** run over
every screened-in document, and a **light full-text profile**) and `select` gains a scoping
read-set strategy; `synthesise` gains the report, profile and baseline templates; the provenance
contract declares one new block kind (the transferability working). The **screen is unchanged**: it
screens for relevance only. The execution contract was amended 2026-09-07 to say components are shared
across capabilities (ruling 40).

```
[0 inherit] ─▶ 1 plan ──▶ ⟨baseline⟩ ══gate: confirm plan against baseline══▶
   2 acquire ─▶ 3 screen ─▶ 4 classify ─▶ 5 appraise ─▶ (ingest) ─▶ 10 extract(abstract) ─▶ 6 longlist ─▶ 7 constrain ─▶ 8 shortlist
                                       (the EB spine as is, then the longlist; runs over every option)
   ══gate: "Assess these N"══▶ ⟨assess⟩ per shortlisted option ─▶ 11 synthesise(report, assessed) ─▶ export (Share seam)
                                     └──▶ ⟨full run⟩ per option = the whole EB chain as a child task (user-triggered)
```

- ✅ **Two gates are structural, not discretionary.** Nothing after the baseline runs until the
  user confirms the plan against it; nothing after `shortlist` runs until the user says assess
  (rulings 2, 3). Re-runs after a plan change apply deltas (❓ granularity, concept open
  question 7).
- ✅ **The spine runs over every option; ⟨assess⟩ runs over the shortlist only.** This is the cost
  model: everything before the second gate is the EB's cheap per-document envelope work plus
  clustering; everything after it is per-option full-text reading, paid for only on options the
  user kept.
- ✅ **Classify and appraise run at longlist depth** (owner, 2026-09-07), so every option carries
  a **source-quality profile** of its mentioning documents before assessment — never called "how
  sure" (ruling 33). Full text is fetched and ingested for the
  whole screened-in set, as in the EB, each source carrying `text_basis` (full text | abstract
  only) — the label ruling 16 needs.

## Components

**Universal core, ambient to every component:** `search`, `retrieve`, `lookup`, `appraise`,
`produce-grounded-block`, `escalate`, `clarify`.

| # | Component | Origin | What OS uses it for | Realisation | Gating |
|---|---|---|---|---|---|
| 0 | inherit | **shared** — new in OS, adopted by the Evidence search (ruling 48); a thin procedure over Links, authored once, what crosses depends on the source task's kind | seed the plan, the pool, the longlist and — from a deep search — the extracted findings, from a linked Evidence search task | procedure | optional; user chooses the task |
| 1 | plan | system plan-as-object instance (the EB plan UI), OS slots | the scaffolded planning conversation → plan object: target unit, three constraint kinds, entry branch, depth asked every time | agent (lead-authored prompt) | mandatory; gate: confirm |
| 2 | acquire | is EB (incl. ingest) | `search` with intent = the plan, an option or a variant; source policy for the baseline; seed corpus from `inherit` | procedure | mandatory |
| 3 | screen | is EB, stage 1 only, **unchanged** | title-and-abstract consensus screen for relevance, plan as intent; evidence-scope constraints act at retrieval where a backend can express them and as a **deterministic set-aside after extract(abstract)** (check 6 F5, 2026-09-08), never here — the screen is relevance-only | per-doc fan-out | mandatory; **no stage 2 in OS** |
| 4 | classify | is EB | primary evidence type + open tags per screened-in document; Unknown and Non-evidence shown as their own buckets in an option's source-quality profile (a non-evidence document counts as a mention, never as evidence); Unknown is not resolved within scoping (ruling 43) | per-doc fan-out | mandatory |
| 5 | appraise | is EB | quality tier per document under the versioned rubric; the per-option roll-up happens in `longlist` | per-doc fan-out | mandatory |
| 6 | longlist | EB characterise, **modified** — unit = intervention mention (or finding), many-to-many | both characterise machines at option grain: cluster **intervention mentions** (or extracted findings where a deep search was inherited) into options — a document may support several options — then options into themes; per-option coverage/patterns (counts, types, tiers, countries, populations, outcomes); entrants without documents; option schema (specified design, primary + secondary lever type, ambition tag, relations) | procedure + agent | mandatory; 🟡 unproven at option grain — check before the longlist contract |
| 7 | constrain | EB screen, **modified** — object = option, criteria = the plan's constraints | scope-shaped screens on metadata and the specified design; reasoned guesses for after-assessment constraints | per-option fan-out (LLM judgment, checkable, cited when corpus-based) | mandatory; every exclusion carries its constraint |
| 8 | shortlist | **new** — coverage over primary lever types has no EB analogue | one place per primary lever type present, one named reason each; gap messages; warnings; the unassessed list | procedure + agent | mandatory; user adds/removes on top |
| 9 | select | is EB (new strategy) | the capped **read set** for one shortlisted option: stratify by implementation and outcome family, reserve the counter-case, cap per option, record omissions (ruling 38) | procedure (+ optional bounded rerank) | inside ⟨assess⟩ only |
| 10 | extract | **EB modified** — two new profiles, plus an `all_screened_in` select strategy that includes Non-evidence so the abstract profile runs over every screened-in document (check 6 F2) | **abstract profile** over every screened-in document at longlist depth (interventions named, setting country, population, outcome family, design hint; reused by memo) — the source of intervention mentions (ruling 43); 🟡 **light full-text profile** over the selected read set inside ⟨assess⟩ (proposed: direction, outcome family, magnitude with comparator and period, design, setting; a trial/registration identifier only if independence detection needs it); inherited findings reused at finding grain (ruling 35) | per-source fan-out | abstract profile mandatory; light profile inside ⟨assess⟩; field sets and independence method are check 2 |
| 11 | synthesise | is EB, templates | `produce-grounded-block` over the run's substrate with a template: **report** (written from the assessment, rewritten by a full run — ruling 50; the sense-check's questions are its closing section) · **profile** · **baseline** | agent-loop | per composition |

**Named compositions** (the three depths, ruling 3; not components):

| Composition | Made of | Runs |
|---|---|---|
| ⟨baseline⟩ | acquire (Overton and OpenAlex only in v1, grey-literature-weighted source policy; the coverage statement names live official statistics and departmental pages as not searched — ruling 43) → screen → classify → appraise → ingest → synthesise(**baseline**) | once, after plan confirmation; the run pauses after it |
| ⟨longlist depth⟩ | acquire → screen → classify → appraise → ingest → extract(**abstract**) → longlist → constrain → shortlist | over every option; the Result is the longlist until assessment (ruling 50) |
| ⟨assess⟩ | [acquire with the option as intent, if its document set is thin → screen → classify → appraise → ingest → extract(abstract)] → **select** (the scoping read-set strategy: stratify by implementation and outcome family, reserve the counter-case, cap per option, record omissions — rulings 38, 43) → extract(**light**) over the selected set (inherited findings reused at finding grain — ruling 35) → **longlist(assign, finding grain)**, which writes the option's finding-grain membership — the eligibility record (check 6 F4) → synthesise(**profile**, under a declared `reading_scope`); then synthesise(**report**, assessed). "How sure" = confidence in the specified claim from relevant evidence, documents counted until independence is known (ruling 33) | per shortlisted option, on "Assess these N" |
| ⟨full run⟩ | the whole EB chain (incl. classify, select, stage-2, full extract, group) as a **child Evidence search task**, opened by the child's `inherit` from the scoping task (the option's design, documents, light findings, user context and evidence scope — ruling 48) with the profile template; its report **is** the option profile, shown in place in the scoping task (ruling 47) | per option, user-triggered (ruling 9) |
| export | the Share/export seam (arch §10; no contract yet), not a component | user-triggered |

## 0 — inherit (optional; ruling 22; shared, ruling 48)

Authored once and used by both capabilities: the input is a Link, and **what crosses depends on the
source task's kind**. This section is the scoping direction (from an Evidence search task); the
Evidence search direction (from a scoping task, the child full run's normal case) is
[../evidence-search/components.md § 0](../evidence-search/components.md).


- **In:** a linked Evidence search task. **Out:** a draft plan seeded from its question; its
  screened documents queued into the pool, flagged *inherited* for re-screening against the
  scoping plan; its report's theme claims and grouping rows queued as longlist suggestions
  labelled "from your evidence search" (the report holds no list of named interventions; `longlist`
  turns the rows into option suggestions); its documents' **abstract-profile extractions** where
  they exist (reused by memo); and, **when the linked task ran the deep chain, its
  extracted findings** (`intervention_outcome_finding` / `implementation_context_finding`, at
  finding grain with the intervention named) — the best possible input to `longlist`, since a
  finding already isolates one intervention from a document that may discuss several (owner,
  2026-09-07). ⟨assess⟩ reuses those findings **at finding grain**: it skips only the extraction
  requirements a finding satisfies for the specified option and the same source snapshot, fills
  or labels the rest, and reconciles profile, version and coverage before counting (ruling 35).
- ✅ Nothing inherited is trusted because it was found before: inherited documents are
  re-screened (🟡 proposal: they re-pass classify/appraise when the rubric or classifier version
  differs — not yet ruled; the shared cache-validity rules decide); inherited rows take the
  fait-accompli path like any suggestion. Acquired source snapshots cross with the Link. Uploaded
  snapshots (task-private in the data model; no upload feature exists yet) do **not** cross
  automatically — the inherit contract of the day uploads ship decides the mechanism (ruling 43).
  ✅ The run acquires beyond the inherited set; the
  Sources tab states inherited versus added. Fallback if a contract must trim: question and
  documents only. Kept as its own component so the inherited-versus-added accounting has one
  owner (owner, 2026-09-07).
- ✅ **Settled 2026-09-08 (feasibility check 6 F6, F7; check 2 C2-5).** The input is a
  `task_link` row ([data-model.md § Links between tasks](../../system/data-model.md)). Record by
  record: snapshots, chunks and embeddings cross for free; screening never crosses; classify and
  appraise rows are **copied as inherited assertions** when the classifier or rubric version
  matches the current default, else re-run (this closes the 🟡 above); findings cross under the
  field-grain memo; the inherited flag is `inherited_from_task_id` on the task's document row,
  not an `origin` value. Document identity for counting (DOI or normalised title plus year) is
  resolved here, so a review present as two snapshots is inherited once.

## 1 — plan

- **In:** the user's question (or, in the sense-check branch, a named option); the conversation.
  **Out:** the plan object — question · what we are trying to change · who or what should change
  (target unit) · where · outcomes · **depth (rapid / standard / deep, asked every time, no
  default; the Evidence search's words)** · constraints (each
  tagged *from your question* / *assumed* / *your call*; each tagged *scope-shaped* / *effect- or
  cost-shaped, checked after assessment* / *evidence-scope*) · plan steps · check-ins (rulings 1,
  12, 23, 25).
- ✅ Branches on the two jobs: *explore the option space* vs *sense-check one option* (ruling 25:
  the latter seeds the working set with one option as added by you with its specified design, and
  the agent infers problem, target unit, outcome and place for the user to confirm). Depth (rapid /
  standard) is orthogonal to the branch. ✅ A plan object in the system sense
  ([plan-as-object](../../system/plan-as-object.md)), compiled to the run configuration; ❓ the
  scaffolding chat as a shared component with EB (open question 8). ✅ Prompt-bearing:
  lead-authored under [prompting.md](../../system/prompting.md).

## 2 — acquire · 3 — screen · 4 — classify · 5 — appraise (the EB spine, as is) · extract(abstract)

- **In:** the plan (or an option / variant as intent; or the baseline's source policy). **Out:**
  the screened-in document set with, per document: evidence type and tags (classify), quality tier
  under the rubric version (appraise), `text_basis`, and — from **extract's abstract profile**
  (ruling 43) — the interventions the abstract names (none / one / several), setting country,
  population, outcome family and a design hint, so scope-shaped screens in `constrain` run on
  abstracts and `longlist` clusters mentions. Study geography is read from the abstract text,
  never inferred from publication metadata.
- ✅ `acquire` is EB acquire with `search` as the only egress verb; full text is fetched and
  ingested for the whole screened-in set. ✅ `screen` is EB stage 1 with the plan as the id-keyed
  intent record; **no stage-2 full-text confirmation in OS** (ruling 3). ✅ **Evidence-scope
  constraints** (ruling 23) act here, on retrieval and screening, never on options. ✅ Suggested,
  inherited and user-added options with no documents — and every **variant** (ruling 15), whose
  intent is its specified design — get their own small acquire + screen + classify + appraise, so
  every entrant is treated the same (concept § Shape 2).

## 6 — longlist (characterise, modified)

- **In:** the screened-in set with its per-document columns; the lever-type taxonomy; inherited,
  user and ministerial additions. **Out:** the longlist — options (name, one-sentence description,
  **specified design**, constituent interventions with their documents, stated outcomes served,
  **one primary lever type** and any secondary ones, ambition tag with a one-line justification
  carried as a tier-4 reasoning claim, relations *variant of* / *part of*) grouped into generated
  themes, each theme mapped to lever type(s) with a one-line "what it does"; **per-option
  coverage** (study count by evidence type and quality tier, countries, populations, outcomes
  measured) — the longlist metadata, shown as a **source-quality profile**, never as "how sure"
  (ruling 33).
- ✅ **Same two machines as EB characterise, at option grain**: the bounded two-stage LLM grouping
  (discover, then assign, code-enforced exhaustiveness, an explicit unclustered bucket) discovers
  *options* rather than landscape themes and then groups options into themes; the deterministic
  coverage/patterns run per option instead of per run. **Different, and why it will not work off
  the shelf** (owner, 2026-09-07): characterise assigns each *document* to one theme, and **a
  document is not an option**. Documents discuss bundles, name several interventions, and —
  systematic reviews especially — cover many intervention types. So the **unit of assignment is
  the intervention mention**, not the document: at longlist depth the mentions come from
  `extract`'s abstract profile (the interventions the abstract names); where a deep search was
  inherited, the unit is the extracted finding. Assignment is **many-to-many**: one document may
  support several options and counts once per option it mentions; a review's contribution is
  visible as such ("3 of 12 documents are reviews spanning several options"); a bundle becomes a
  package option with *part of* links to its constituents. The output is an option schema with a
  specified design, two grouping levels, generation-free entrants and relations. Named for what
  it produces. 🟡 **Unproven**: the concept's clustering-quality check must test many-to-many
  assignment, bundles and reviews across domains before the longlist contract.
- ✅ Top-down: the **small, curated, versioned list of about ten domain-agnostic lever types**
  (regulate, subsidise, tax or charge, inform, provide a service, enforce existing powers, devolve,
  change who runs the system) prompts suggestions and checks coverage. Themes are never a fixed
  list (ruling 11). ✅ A user modification of an option's design mints a new option linked *variant
  of* its parent (ruling 15; which edits count is the agent's judgement, stated); a substantive
  edit suspends inherited claims until the variant's own assessment; support binds to a finding
  and a specified design, not to a document (ruling 36); packages and ingredients are linked
  *part of* and shown together. ✅ Generation is free: a suggested option
  needs no source and is labelled ([trust.md](trust.md)). ❓ Overlap/dedup and target longlist size
  (open question 4). 🟡 Taxonomy as a curated asset rather than prompt-internal text (open
  question 5).
- **Checked 2026-09-08 (feasibility check 3, three staging corpora; check 2).** The two machines
  work at option grain on the shared engine (827 mentions → 29 options, 22 calls, 36 s;
  many-to-many is real: a third of documents land in two or more options). Findings that change
  this section: **(a)** mentions cluster to **class-grain** options and deep findings to **named
  implementations**; ❓ **owner ruling needed (C3-1)** — relations gain *instance of* so a class
  option carries its named implementations beneath it, or *part of* is reused with a type.
  **(b)** A quarter of mentions were residual, half of them not interventions (theories, study
  designs, events) or not for the question; the mention record carries an **adoptability** flag and
  the discovery ceiling becomes `clamp(ceil(N/4), 8, 40)` — the old formula was binding in the thin
  corpus (C3-3). **(c)** Lever typing is a close call for most options; store **primary,
  secondary and runner-up** with the reason (C3-4). **(d)** Membership is stable for named designs
  and not for classes (a third of members moved under paraphrase); the membership record carries
  a stability marker and coverage denominators are computed over the stable core (C3-5). **(e)**
  Assignment admits **design feature not stated** beside member and ungroupable, attaching to the
  parent class only (check 2 C2-3, ruling 36). **(f)** `longlist` declares an **assign-only mode**
  (fixed option list, discovery skipped) so ⟨assess⟩ and the child full run can attribute
  findings to specified designs (check 6 F4, F9).

## 7 — constrain (screen, modified)

- **In:** the longlist with coverage and specified designs; the plan's constraints. **Out:** each
  option marked *included* or *excluded: breaks "<constraint>"* (scope-shaped constraints only,
  ruling 23), or *no in-scope evidence*, plus a labelled **reasoned guess** per after-assessment
  constraint; the three default screens (relevant to outcomes · distinct · in scope) applied and
  cited like any other — the *distinct* screen never excludes a variant or a part-of relation
  (ruling 36). After assessment, a failed or uncheckable effect/cost constraint is shown on the
  option ("breaks: low cost (assessed)" / "unresolved: cost not comparable"); the option stays and
  the user decides (ruling 40).
- ✅ The EB screen's per-item judgment with the object changed: an option judged against
  constraints instead of a document against an intent. Runs on coverage and the specified design
  as options complete; never on analysis. ✅ Thin evidence is noted, never a reason to exclude.
  ✅ Screens judge the **specified design**; a finding about the parent's typical implementations
  is not a finding against a variant (ruling 15). ✅ Corpus-based screen findings are cited by
  coverage denominator. ✅ Fallible by design, so every judgment is shown and reversible (*Include
  again*), and every exclusion is kept with its reason as institutional memory. ✅ Reasoned guesses
  are capped reasoning claims: a flag and a user-requested sort, never a screen and **never an
  input to `shortlist`** (rulings 12, 19; [trust.md](trust.md)).

## 8 — shortlist (new)

The shortlisting component (renamed from `propose`, owner 2026-09-07, to pair with `longlist`); its
output is still called *the proposal* — the proposed shortlist the user adds to and removes from.

- **In:** the included options with coverage and relations; the user's additions. **Out:** the
  proposed shortlist — **one place per primary lever type present among the kept options**
  (ruling 20) — a **provisional allocation of reading effort**, never "representative coverage"
  (ruling 37) — each with one named reason from what coverage knows (distinctness; widest
  implementation record = implementations and countries recorded in the mentioning documents;
  only option of its lever type; thin evidence = few mentioning documents or none of the required
  outcome); gap messages naming
  secondary lever types ("Regulate: no dedicated option; touched by the youth guarantee package");
  the list of kept options not proposed, by theme; warnings when every place shares one ambition
  band or when a package and its own ingredient would both take places.
- ✅ Never a top-N; never a fused score; **study count alone and quality-tier distribution are
  never place reasons** (tiers are display and a user-requested sort only — owner, 2026-09-07,
  guarding hierarchy bias); reasoned guesses are not inputs (ruling 19); thin evidence is a reason
  to assess. ✅ Themes group but do not earn places; a singleton theme is proposed only if its
  primary lever type is otherwise uncovered. ✅ Places the user added are respected and worked
  around; PA advises on gaps and never removes (ruling 6). ✅ In the sense-check branch the
  proposal is the named option (rapid) or the named option plus its most similar neighbours
  **plus one challenger** reaching the same outcome through a different primary lever type,
  pre-ticked, each with its reason (standard) (rulings 25, 37; ❓ similarity measure = open
  question 10). ✅ "Most promising"
  only after assessment, as per-axis sorts on comparable axes and conditional recommendations on
  those axes; before assessment `shortlist` describes coverage and gaps only.
- **Why new:** nothing in the EB selects a representative set over a fixed taxonomy; EB `select`
  picks documents for extraction by strategy, not options for coverage.
- **Checked 2026-09-08 (feasibility check 3 § 2).** Relabelling the primary lever moved up to
  four of five places in a thin corpus and seated a one-document, unevaluated option as the only
  "regulate" place; paraphrase swapped two of six places in a dense corpus. ❓ **Owner ruling
  needed (C3-2):** keep one place per primary lever type present, and add two guards — a lever
  type whose options all have **zero evaluated mentions** earns a **gap message, not a place**
  ("Regulate: mentioned in 3 documents, none evaluates an option"); a place is marked
  **contested** when the seated option's typer named a runner-up lever or a rival's implementation
  record is within one country or one evaluated document, and the user confirms it. The assembly
  record (places, reasons, who filled them, gap messages, warnings) is a run-keyed
  **`shortlist_result`** row, like `selection_result`, so export has one thing to read (check 6
  F15).

## 9 — select · 10 — extract (light profile) · 11 — synthesise (templates): inside ⟨assess⟩

- **In:** a shortlisted option with its specified design and ingested documents; the baseline's
  retrieved context (geography-tagged; a containing geography counts unless a more local fact
  contradicts it, ruling 18). **Out:** the verdict strip and the profile sections (§ Output
  structure in [capability.md](capability.md)).
- ✅ **select, scoping read-set strategy** (ruling 43): from the option's screened documents,
  stratify by implementation and outcome family, reserve places for the counter-case, cap per
  option, and record what was left out and why — the EB's own `select` tool with a second strategy
  beside its coverage-aware-stratified-over-clusters one. The omissions record feeds the report's
  "what was not read".
- ✅ **extract, light field set** for the countable cells over the selected set: direction (one vote per independent
  study, per outcome family, significance never counted — ruling 26; ❓ independence detection
  open, a trial/registration identifier is the candidate field), magnitude in native units with
  its comparator, population and period, design, setting. Run as a parallel per-source fan-out
  over the **read set** — chosen under the per-option cap so that distinct implementations, the
  required outcomes and the counter-case survive, with omissions represented and a
  budget-limited result allowed to be explicitly incomplete (ruling 38) — so one stage's latency
  is close to one document's; whole-run latency is what the rapid budget measures. Inherited
  findings are reused at finding grain: only the requirements they satisfy are skipped (ruling
  35). ✅ **synthesise(profile)** by
  retrieval-augmented reading over the option's chunks for the narrative sections: mechanism and
  failure mode (tier-labelled) · constituents (a variant's parent evidence here as related
  evidence for a different design) · evidence for and against · variants in practice · case
  studies typed by tier · transferability working (three legs; moderator/dealbreaker extraction
  with quotes; context typed retrieved / stated by you / planned by you; weakest leg decides; no
  factor fractions — ruling 18) · assumptions · what it would take · reported cost beside the
  earlier guess. "How sure" = confidence in the specified design–outcome claim from evidence
  found relevant to it; documents counted until independence is known; the pre-assessment
  source-quality profile is shown beside it, not in place of it (ruling 33). Retrieved context
  fills a local transferability factor only where the proposition applies at the target unit by
  its nature (ruling 34).
- ✅ **Reads the full text of the documents it relies on, capped per option; every claim carries
  the depth of what was read** (`text_basis`; ruling 16). ✅ A variant is assessed on its own
  design (ruling 15). ✅ Shortlist only, on the user's word; every cell labelled *scoping pass*.
  ✅ Unassessed cells are honest empty states. 🟡 **Shape to check** (open question 2): extraction
  is slower than reading, so the per-option document cap is the latency lever and the check
  measures fit to the rapid budget; the abstract-profile extraction already on every document
  gives the abstract-level strip shown first.
- ✅ **synthesise(report)** writes the Result (rulings 32, 50) **from the assessment**, never
  before it: top line · the problem and what is contested · the approaches · what the evidence
  base holds (one verdict strip per option; the comparison table as a working view) ·
  transferability and assumptions · what needs deciding or commissioning next · what was searched.
  A full run rewrites it. (An on-demand report from the longlist alone is deferred.) The report
  is never a ranking — no superlatives across options; each effect with its own
  comparator, population and period; conditional recommendations only on comparable axes and
  matching bases (rulings 17, 33); the kept-but-unassessed options listed (ruling 19); in the
  sense-check branch the closing section carries **"questions to put to the department"**
  (ruling 25), bounded by ruling 39 (structure unlabelled; no unsupported proposition, even
  inside a question). Not user-editable in v1 (ruling 14). ✅ **synthesise(baseline)** writes the
  "Do nothing" profile (what is in place · trend if nothing changes · who is affected · what is
  already changing · what is contested · cost of inaction · key assumption · sources), empirical
  premises sourced and interpretations labelled reasoning (ruling 40), every statement
  provenance-carrying, "not found" stated as such; the run **pauses** after it and the
  pause is a place to question it in chat (rulings 2, 24). ❓ Baseline sourcing mechanics (open
  question 6).
- **Checked 2026-09-08 (feasibility checks 2, 4, 5).** **select:** strata are the abstract
  profile's *evaluated* role × outcome family, with one review and one primary study reserved
  and text availability a tiebreaker only — full-text-first picked process evaluations with no
  effects; the per-option cap is a plan setting, defaults 5 (rapid) and 8 (standard) — a cap of 3
  read one-sided pictures (C5-2, C5-4). **extract(light):** the field set is an IOF subset plus
  `design_features`, `magnitude_as_reported` (number and unit only; the source's own
  characterisation is a separate field), `period`, `trial_or_registration_id`, and a
  document-level `study_identity` ([data-model.md](../../system/data-model.md)); the Evidence
  search's quote vetter and claim-key dedup are wired for it (17 percent of anchors failed
  verification unvetted; repeated results across windows doubled one document's claims) (C2-2,
  C2-6, C2-8). The **countable cells come from per-document extraction, never from reading
  alone**: one call over five texts missed contrary evidence extraction found (C5-3). **"How
  sure"** is two numbers — documents read, and independent own-data studies where identity is
  known; reviews are documents (C2-1; ❓ owner to confirm the wording). **synthesise(profile):**
  the transferability working is **two steps** — factor extraction from the evidence, then
  context fill against the fixed list — with code-side verify
  ([provenance-grounding.md](../../system/provenance-grounding.md)); the profile carries a
  declared **section budget and `reading_scope`**, because synthesis, not extraction, is the
  latency lever (C4-1, C5-1).

## ⟨full run⟩ — the boundary with EB (ruling 9)

- **In:** one shortlisted option and the scoping task's user context. **Out:** a new Evidence
  search task whose `inherit` (ruling 48) takes from the scoping task the option's specified design
  as its question, the user context and evidence-scope constraint, the option's mentioning
  documents (re-screened against the new plan) and the light findings ⟨assess⟩ extracted (reused at
  finding grain), then acquires beyond them; with the option-profile sections as its synthesis template;
  its report **computes the profile's judgement cells** (how sure, transferability and
  conditions, key assumption) under the OS trust rules carried by the template (ruling 41); on
  completion that report **is** the option profile, shown in place in the scoping task tagged
  *full run* (one document, two homes — ruling 47); the scoping-pass version is kept in History.
- ✅ The child task is listed under the parent, linked both ways, and shares its project and
  visibility. ✅ The user's stated context is owned by the scoping task and passed to the child as
  input, so a transferability cap caused by unstated context survives the full run until the plan
  says otherwise. ✅ Stage-2 full-text confirmation, `select` and full extraction happen here, not
  in scoping. ✅ This is the one place the Evidence search's evidence-descriptive boundary is
  widened, and only for the profile-template case (see the EB capability spec § Scope boundaries).
- ✅ **Checked 2026-09-08 (feasibility check 6 F8, F9).** Ruling 47's "prior version in History"
  is a **derivation edge** from the child artefact to the scoping-pass block version, plus a
  display convention — history is linear per artefact and an artefact lives in one task, so it
  cannot be a shared version chain. Ruling 41 stands on one condition: the child computes
  membership against the **specified design** (no Evidence search component does today), through
  `group`'s fixed-target-list mode or `longlist(assign)` composed in; without it the "how sure"
  cell cannot be computed in the child.

## Interface rulings (owner, 2026-09-07; concept ruling 43)

The six open interfaces the third review pass raised, ruled:

1. **Mentions and abstract-level fields** come from `extract` with a new **abstract profile** over
   every screened-in document; the screen is unchanged. Whether the abstract record is a finding
   or a new record kind is a contract detail.
2. **Classify at option level:** Unknown and Non-evidence documents appear as their own buckets in
   the source-quality profile; non-evidence counts as a mention, never as evidence; Unknown is
   not resolved within scoping.
3. **The read set** is built by `select` with a scoping strategy (ruling 38's discipline); `extract`
   keeps taking a selected set.
4. **Claim kinds:** membership and countable aggregates are EB pattern claims; relations are
   reasoning claims or user actions; constraint states are records; the **transferability
   working** is a new grounded-block kind with per-column grounding, declared in
   [../../system/provenance-grounding.md](../../system/provenance-grounding.md).
5. **Baseline backends:** Overton and OpenAlex only in v1; the coverage statement names live
   statistics and departmental pages as not searched; the open-web seam stays closed.
6. **Uploaded snapshots:** deferred — no upload feature exists; when it does, uploads do not cross
   automatically.

**Shared seams still recorded for the system contracts** (ruling 42): reading budget and evidence
eligibility; source-quality policy distinct from evidence-scope constraints; durable option
identity and relations across runs. **All three resolved 2026-09-08** by the feasibility checks:
reading budget and eligibility → `reading_scope` on synthesise plus the finding-grain membership
record ([execution-orchestration.md](../../system/execution-orchestration.md)); the evidence-scope
constraint → the plan's third policy face and the set-aside step
([plan-as-object.md](../../system/plan-as-object.md)); option identity → the option as an
addressable-unit kind with `task_link` and `inherited_from_task_id`
([data-model.md](../../system/data-model.md)).

## export (Share seam)

- ✅ Bundles the **report** with its attachments: the option profiles, the baseline profile, the
  **full longlist with states and reasons**, the **shortlist assembly record** and the Sources
  statement (inherited versus added; what was read at which depth; what was not read under the
  cap); the same complete bundle in both branches (ruling 32); claims breadth, never
  exhaustiveness (rulings 14, 21). Arch §10 seam; no export contract drafted yet.
