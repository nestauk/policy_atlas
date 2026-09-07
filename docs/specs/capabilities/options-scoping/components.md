---
type: Capability spec
title: Options Scoping — component skeleton
description: The OS components — declared I/O, what each reuses from the Evidence search, realisation and gating — with the three depths and two gates made structural.
tags: [capability, options-scoping, components]
timestamp: 2026-09-07
---

# Options Scoping — component skeleton

The components, their declared I/O, what each reuses from the Evidence search, realisation and
gating. Distilled from
[options-scoping-concept.md](../../sources/options-scoping/options-scoping-concept.md) (§ Shape,
§ Architecture stance, rulings 2–6, 9, 11, 12, 14, and the review-round rulings 15–29, which win
where they differ). Shared tools and the findings schema are
owned by [../../system/execution-orchestration.md](../../system/execution-orchestration.md) and
[../../system/data-model.md](../../system/data-model.md); the EB components referenced below are
specified in [../evidence-search/components.md](../evidence-search/components.md).

```
[inherit] ─▶ plan ──▶ baseline ══gate══▶ retrieve ──▶ screen(stage 1) ──▶ mint ──▶ constrain ──▶ propose
                                                          (the longlist spine, runs over every option)
      ══gate: "Assess these N"══▶ assess ──▶ summarise ──▶ export        (shortlist only)
                                    └──▶ ramp (spawns an EB task per option)   (user-triggered)
```

`inherit` is optional (a Link to an Evidence search task, ruling 22). The sense-check entry branch
(ruling 25) runs the same spine with a short plan, a light baseline, neighbours left at longlist
depth and a proposal of the named option (rapid) or the named option plus its most similar
neighbours (standard).

- ✅ **Two gates are structural, not discretionary.** Nothing after `baseline` runs until the
  user confirms the plan against it; nothing after `propose` runs until the user says assess
  (rulings 2, 3). Re-runs after a plan change apply deltas (❓ granularity, concept open
  question 7).
- ✅ **The longlist spine runs over every option; `assess` runs over the shortlist only.** This
  is the cost model: everything before the second gate is cheap and covers the whole space;
  everything after it is per option and paid for only on options the user kept.
- ✅ **Reuse, do not re-derive.** `retrieve` is the EB's acquire (`search` is the only egress
  verb); `screen` is the EB's stage-1 consensus screen with the plan as the intent record;
  `assess` reads the full text of the documents it relies on (ruling 16) and uses the EB's
  appraise plus either its extract or a retrieval-augmented reading over those texts (❓);
  `ramp` runs the whole EB pipeline. OS never orchestrates full EB runs per option inside its
  own run (concept § Architecture stance).

## Tool wiring (consolidated)

**Universal core, ambient to every component:** `search`, `retrieve`, `lookup`, `appraise`,
`produce-grounded-block`, `escalate`, `clarify`.

**Reuse rule (owner, 2026-09-07).** Components are discrete so they can be shared across
capabilities and combined into gradations of one ([vocabulary.md § Components](../../vocabulary.md)).
Every OS component is therefore marked **is EB** (an Evidence search component, possibly with
parameters), **EB modified** (a variation of one: a new template, object or field set) or **new**,
and every "new" is justified. Only `inherit` and `propose` are new; `constrain` is the EB screen
pointed at options rather than documents.

| # | Component | Origin | Centres on | Reuses from EB | Realisation | Gating |
|---|---|---|---|---|---|---|
| 0 | inherit | **new** — no EB analogue; a thin procedure over Links | seed the plan, pool and longlist from a linked Evidence search task | the task's plan object, screened set and report findings (Links) | procedure | optional; user chooses the task |
| 1 | plan | EB modified — scoping slots (target unit, three constraint kinds, branch, depth) | the scaffolded planning conversation → plan object | the plan object and plan document (system § plan-as-object; EB plan UI) | agent (lead-authored prompt) | mandatory; gate: confirm |
| 2 | baseline | EB modified — acquire with a grey-literature/official-statistics source policy + synthesise with the baseline template | grey-literature + official-statistics retrieval → "Do nothing" profile incl. what is contested | `search` (Overton, web), `produce-grounded-block` | procedure + agent | mandatory; **run pauses after**; user may question it in chat |
| 3 | retrieve | is EB (acquire) | `search` over the evidence base for the plan | acquire | procedure | mandatory |
| 4 | screen | is EB (stage 1 only; 🟡 structured fields returned) | stage-1 title-and-abstract consensus screen, plan as intent | screen (stage 1 only; **no stage 2 in OS**) | per-doc fan-out | mandatory |
| 5 | mint | EB modified — group/cluster with option aggregation, primary + secondary lever types, relations, ambition tag | cluster screened interventions into options with a specified design; name themes; assign one primary lever type per option (others secondary); ambition tag as a tier-4 reasoning claim; add taxonomy, inherited and user suggestions; link variant-of / part-of | cluster / group (theming machinery) | procedure + agent | mandatory |
| 6 | constrain | EB modified — the screen's per-item judgment with object = option, criteria = constraints | scope-shaped screens on metadata and the specified design; evidence-scope constraints applied at retrieval/screen, never excluding; reasoned guesses for after-assessment constraints | — | per-option fan-out (LLM judgment, checkable, cited when corpus-based) | mandatory; every exclusion carries its constraint |
| 7 | propose | **new** — coverage over primary lever types has no EB analogue | one place per primary lever type present, one named reason per place; secondary types shape gap messages; guesses and study count excluded as reasons; ambition-band and package/ingredient warnings; unassessed list | — | procedure + agent | mandatory; user adds/removes on top |
| 8 | assess | EB modified — appraise as is; extract with a light field set; grounded reading with the profile template | the mini evidence search per shortlisted option (full text of cited documents, capped) → verdict strip + profile sections; variants assessed on their own design | appraise; light per-document extract for the countable cells + retrieval-augmented reading for the narrative sections (🟡, spike); `produce-grounded-block` | per-option fan-out | **gate: "Assess these N"**; shortlist only |
| 9 | summarise | EB modified — synthesise with the summary template | the summary above the assessed table (no superlatives, own comparators) + "What needs deciding or commissioning next" (+ "questions to put to the department" in the sense-check branch) | `produce-grounded-block` | agent | after assess |
| 10 | export | is EB (Share/export seam) | the Export bundle (summary · table · profiles · baseline · full longlist with states and reasons · shortlist assembly record · what was searched) | Share/export seam (arch §10, no contract yet) | procedure | user-triggered |
| 11 | ramp | is EB (the whole spine) | spawn an EB task from one option with the profile-shaped synthesis template; re-read the profile from the report | the whole EB spine + synthesis profile | orchestration | user-triggered, per option |

## 0 — inherit (optional; ruling 22)

- **In:** a linked Evidence search task. **Out:** a draft plan seeded from its question; its
  screened documents queued into the pool, flagged *inherited* for re-screening against the
  scoping plan; its report's interventions and themes queued as longlist suggestions labelled
  "from your evidence search".
- ✅ Nothing inherited is trusted because it was found before: inherited documents are
  re-screened (the old screen had a different intent) and inherited interventions take the
  fait-accompli path like any suggestion. ✅ The run retrieves beyond the inherited set; the
  Sources tab states inherited versus added. Fallback if a contract must trim: question and
  documents only.

## 1 — plan

- **In:** the user's question; the conversation. **Out:** the plan object — question · what we
  are trying to change · who or what should change (target unit) · where · outcomes · depth ·
  constraints (each tagged *from your question* / *assumed* / *your call*; each constraint tagged
  *checked at longlist* or *checked after assessment*) · plan steps · check-ins (ruling 1, 12).
- ✅ Branches on the two jobs: *explore the option space* vs *sense-check one option* (ruling 25:
  the latter seeds the working set with one option as added by you with its specified design,
  infers problem, target unit, outcome and place for the user to confirm). Depth (rapid /
  standard) is a plan setting orthogonal to the branch; the plan asks for it every time, no
  default. ✅ The plan is a plan object in the
  system sense ([plan-as-object](../../system/plan-as-object.md)) and compiles to the run
  configuration; ❓ the scaffolding chat as a shared component with EB (open question 8).
- ✅ Prompt-bearing: lead-authored under [prompting.md](../../system/prompting.md).

## 2 — baseline

- **In:** the plan. **Out:** the "Do nothing" baseline profile (what is in place · trend if
  nothing changes · who is affected · what is already changing · **what is contested** · cost of
  inaction · key assumption · sources), every statement provenance-carrying; "not found" stated
  as such. Retrieved baseline facts are available to `assess` as *retrieved* context, tagged
  with their geography; a containing geography counts unless a more local fact contradicts it
  (ruling 18).
- ✅ Reported facts only; the tool does not forecast; the key assumption is a labelled
  reasoning claim (tier 4). ✅ The run **pauses** after this component until the plan is
  confirmed against it; the pause is explicitly a place to question the baseline in chat
  (ruling 24). In the sense-check branch the baseline is light and the pause is one beat.
  ❓ Sourcing mechanics (open question 6).

## 3 — retrieve · 4 — screen

- **In:** the plan. **Out:** the screened document pool with per-document metadata (source
  type, country, population, outcomes measured, year), the OS document set for this run.
- ✅ `retrieve` is EB acquire with `search` as the only egress verb. ✅ `screen` is EB stage 1 —
  the recall-oriented title-and-abstract consensus screen — with the plan as the id-keyed intent
  record; 🟡 the screen prompt returns a few structured fields (setting country, population,
  outcome family) so the scope-shaped screens in `constrain` run on abstracts, not full text.
  ✅ **No stage-2 full-text confirmation in OS** (ruling 3).
- ✅ Suggested, inherited and user-added options with no documents get their own small
  `retrieve` + `screen` with the option as intent, so every entrant is treated the same (concept
  § Shape 2). A **variant** (ruling 15) is such an entrant: its retrieval intent is the variant's
  specified design. ✅ **Evidence-scope constraints** (ruling 23) are applied here, to retrieval
  and screening, and never to options.

## 5 — mint

- **In:** the screened pool; the lever-type taxonomy; inherited, user and ministerial additions.
  **Out:** the longlist — options (name, one-sentence description, **specified design**,
  constituent interventions with their documents, stated outcomes served, metadata, **one
  primary lever type** and any secondary ones, an ambition tag with a one-line justification
  carried as a tier-4 reasoning claim, relations *variant of* / *part of*) grouped into generated
  themes, each theme mapped to lever type(s) with a one-line "what it does".
- ✅ Bottom-up: interventions cluster into options (an option is an actionable aggregate of
  related interventions; drill-down shows the constituents) using the EB's theming machinery.
  ✅ Top-down: a **small, curated, versioned list of about ten domain-agnostic lever types**
  (regulate, subsidise, tax or charge, inform, provide a service, enforce existing powers,
  devolve, change who runs the system — the organisational branch) prompts suggestions and
  checks coverage ("no market-mechanism option; want one?"). ✅ Themes are never a fixed list
  (ruling 11). ✅ A user modification of an option's design mints a new option linked *variant
  of* its parent (ruling 15); packages and their ingredients are linked *part of* and shown
  together. ❓ Overlap/dedup and target longlist size (open question 4). 🟡 Taxonomy as a
  curated asset rather than prompt-internal text (open question 5).
- ✅ Generation is free: a suggested option needs no source and is labelled as a suggestion
  ([trust.md](trust.md)).

## 6 — constrain

- **In:** the longlist with metadata and specified designs; the plan's constraints. **Out:** each
  option marked *included* or *excluded: breaks "<constraint>"* (scope-shaped constraints only,
  ruling 23), or *no in-scope evidence* (evidence-scope), plus a labelled **reasoned guess** per
  after-assessment constraint; the three default screens (relevant to outcomes · distinct · in
  scope) applied and cited like any other.
- ✅ Runs on metadata and the option's description as options complete; never on analysis.
  ✅ Thin evidence is noted, never a reason to exclude. ✅ Fallible by design, so every judgment
  is shown and reversible (*Include again*), and every exclusion is kept with its reason as
  institutional memory. ✅ Screens judge the option's **specified design**; a finding about the
  parent's typical implementations is not a finding against a variant (ruling 15). ✅ Screen
  findings that rest on the corpus are cited. ✅ Reasoned guesses are capped reasoning claims:
  a flag and a user-requested sort, never a screen and **never an input to `propose`**
  (rulings 12, 19; [trust.md](trust.md)).

## 7 — propose

- **In:** the included options with metadata and relations; the user's additions. **Out:** the
  proposed shortlist — **one place per primary lever type present among the kept options**
  (ruling 20), each with one named reason from what metadata knows (distinctness, widest
  implementation record, only option of its lever type, thin evidence); gap messages in which
  secondary lever types are named ("Regulate: no dedicated option; touched by the youth
  guarantee package"); the list of kept options not proposed, by theme; warnings when every place
  shares one ambition band or when a package and its own ingredient would both take places.
- ✅ Never a top-N; never a fused score; **study count alone is never a reason; reasoned guesses
  are not inputs** (ruling 19); thin evidence is a reason to assess. ✅ Themes group but do not
  earn places; a singleton theme is proposed only if its lever type is otherwise uncovered.
  ✅ Places the user added are respected and worked around; PA advises on gaps and never removes
  (ruling 6). ✅ In the sense-check branch the proposal is the named option (rapid) or the named
  option plus its most similar neighbours, pre-ticked (standard) (ruling 25; ❓ similarity measure
  = open question 10). ✅ "Most
  promising" only after assessment, as per-axis sorts on comparable axes and conditional
  recommendations on those axes; before assessment `propose` describes coverage and gaps only.

## 8 — assess

- **In:** the shortlisted options with their specified designs and documents; the baseline's
  retrieved context. **Out:** per option, the verdict strip and the profile sections (§ Output
  structure in [capability.md](capability.md)): effect as reported (direction by vote count —
  one vote per independent study, per outcome family, significance never counted — with a
  discord flag; magnitude in native units with citations and its own comparator, population
  and period; the source's own characterisation quoted; ruling 26) · evidence strength with
  study count (from appraise) · where tried · transferability working (three legs;
  moderator/dealbreaker extraction with quotes and evidence-basis tags; the Factor | Evidence
  says | Your context | Basis table with context typed *retrieved* / *stated by you* / *planned
  by you*; verdict set by the weakest leg, a missing dealbreaker caps alone, commitments become
  named conditions, no factor fractions; ruling 18) · assumptions register (load-bearing,
  strength, the key one) · case studies typed by tier · what it would take (reported facts with
  provenance) · the reported cost replacing the earlier guess, shown side by side.
- ✅ **Reads the full text of the documents it relies on, capped per option; every claim carries
  the depth of what was read** (ruling 16). ✅ A variant is assessed on its own design; the
  parent's evidence appears only as related evidence for a different design (ruling 15).
  ✅ Shortlist only, on the user's word; every cell labelled *scoping pass*. ✅ Unassessed cells
  are honest empty states ("not yet searched" / "no credible evidence found").
  🟡 **Shape to spike** (open question 2, owner 2026-09-07): a **light per-document extraction**
  (small field set: direction, outcome family, magnitude with comparator and period, design,
  setting, and a trial or registration identifier if independence detection needs it) run as a
  parallel fan-out over the capped set, for the countable cells; **retrieval-augmented reading**
  over the read texts for the narrative sections; the stage-1 screen's structured fields for the
  abstract-level strip shown first. Extraction is slower than reading, so the per-option document
  cap is the latency lever and the spike measures fit to the rapid budget. ❓ Study-independence
  detection for vote counting is open. ✅ Reuses the EB's causality
  taxonomy, discord detection and profile-not-scalar framing salvaged from V2 (concept § Effect
  cell, § Transferability cell).

## 9 — summarise · 10 — export

- ✅ `summarise` writes the short summary above the assessed table: PA's reading of the
  shortlist, never a ranking — no superlatives across options; each effect with its own
  comparator, population and period; conditional recommendations only on comparable axes
  (ruling 17); the kept-but-unassessed options listed (ruling 19); a fixed closing element
  **"What needs deciding or commissioning next"** from the unresolved differences, unassessed
  options and verdict conditions (ruling 21); in the sense-check branch also **"questions to put
  to the department"** (ruling 25). Not user-editable in v1 (ruling 14).
- ✅ `export` bundles the summary, the assessed table, the option profiles, the baseline, the
  **full longlist with states and reasons**, the **shortlist assembly record** and the Sources
  statement (inherited versus added; what was read at which depth); claims breadth, never
  exhaustiveness. A Share concern (arch §10 seam; no export contract drafted yet).

## 11 — ramp (the boundary with EB)

- **In:** one shortlisted option. **Out:** a new EB task seeded from the option, with the
  option-profile sections as its synthesis template; on completion the scoping profile re-reads
  its cells from the report, tagged *full run*, and keeps the scoping-pass version in History.
- ✅ The child task is listed under the parent, linked both ways, and shares its project and
  visibility (ruling 9). ✅ The user's stated context stays with the scoping task, so a
  transferability cap caused by unstated context survives the full run until the plan says
  otherwise. ✅ Full-text confirmation happens here, not in scoping.
