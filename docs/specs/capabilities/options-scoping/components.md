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
§ Architecture stance, rulings 2–6, 9, 11, 12, 14, the review-round rulings 15–30). Shared tools
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
variations (plan slots, `longlist`, `constrain`) and two new components (`inherit`, `propose`).
The three depths of ruling 3 are **compositions** of these components, not components themselves.

```
[0 inherit] ─▶ 1 plan ──▶ ⟨baseline⟩ ══gate: confirm plan against baseline══▶
   2 acquire ─▶ 3 screen ─▶ 4 classify ─▶ 5 appraise ─▶ (ingest) ─▶ 6 longlist ─▶ 7 constrain ─▶ 8 propose
                                       (the EB spine as is, then the longlist; runs over every option)
   ══gate: "Assess these N"══▶ ⟨assess⟩ per shortlisted option ─▶ 10 synthesise(summary) ─▶ export (Share seam)
                                     └──▶ ⟨full run⟩ per option = the whole EB chain as a child task (user-triggered)
```

- ✅ **Two gates are structural, not discretionary.** Nothing after the baseline runs until the
  user confirms the plan against it; nothing after `propose` runs until the user says assess
  (rulings 2, 3). Re-runs after a plan change apply deltas (❓ granularity, concept open
  question 7).
- ✅ **The spine runs over every option; ⟨assess⟩ runs over the shortlist only.** This is the cost
  model: everything before the second gate is the EB's cheap per-document envelope work plus
  clustering; everything after it is per-option full-text reading, paid for only on options the
  user kept.
- ✅ **Classify and appraise run at longlist depth** (owner, 2026-09-07), so every option carries
  evidence types and quality tiers before assessment. Full text is fetched and ingested for the
  whole screened-in set, as in the EB, each source carrying `text_basis` (full text | abstract
  only) — the label ruling 16 needs.

## Components

**Universal core, ambient to every component:** `search`, `retrieve`, `lookup`, `appraise`,
`produce-grounded-block`, `escalate`, `clarify`.

| # | Component | Origin | What OS uses it for | Realisation | Gating |
|---|---|---|---|---|---|
| 0 | inherit | **new** — no EB analogue; a thin procedure over Links | seed the plan, the pool and the longlist from a linked Evidence search task | procedure | optional; user chooses the task |
| 1 | plan | system plan-as-object instance (the EB plan UI), OS slots | the scaffolded planning conversation → plan object: target unit, three constraint kinds, entry branch, depth asked every time | agent (lead-authored prompt) | mandatory; gate: confirm |
| 2 | acquire | is EB (incl. ingest) | `search` with intent = the plan, an option or a variant; source policy for the baseline; seed corpus from `inherit` | procedure | mandatory |
| 3 | screen | is EB, stage 1 only | title-and-abstract consensus screen, plan as intent; 🟡 structured fields returned; evidence-scope constraints applied here | per-doc fan-out | mandatory; **no stage 2 in OS** |
| 4 | classify | is EB | primary evidence type + open tags per screened-in document | per-doc fan-out | mandatory |
| 5 | appraise | is EB | quality tier per document under the versioned rubric; the per-option roll-up happens in `longlist` | per-doc fan-out | mandatory |
| 6 | longlist | EB characterise, **modified** | both characterise machines at option grain: cluster screened documents into options, options into themes; per-option coverage/patterns (counts, types, tiers, countries, populations, outcomes); entrants without documents; option schema (specified design, primary + secondary lever type, ambition tag, relations) | procedure + agent | mandatory |
| 7 | constrain | EB screen, **modified** — object = option, criteria = the plan's constraints | scope-shaped screens on metadata and the specified design; reasoned guesses for after-assessment constraints | per-option fan-out (LLM judgment, checkable, cited when corpus-based) | mandatory; every exclusion carries its constraint |
| 8 | propose | **new** — coverage over primary lever types has no EB analogue | one place per primary lever type present, one named reason each; gap messages; warnings; the unassessed list | procedure + agent | mandatory; user adds/removes on top |
| 9 | extract | EB, **modified** — light field set | per-document countable cells for a shortlisted option: direction, outcome family, magnitude with comparator and period, design, setting, trial identifier | per-source fan-out | inside ⟨assess⟩ only |
| 10 | synthesise | is EB, templates | `produce-grounded-block` over the option's (or the baseline's) substrate with a template: **baseline** · **profile** · **summary** · **sense-check questions** | agent-loop | per composition |

**Named compositions** (the three depths, ruling 3; not components):

| Composition | Made of | Runs |
|---|---|---|
| ⟨baseline⟩ | acquire (grey-literature + official-statistics source policy) → screen → classify → appraise → ingest → synthesise(**baseline**) | once, after plan confirmation; the run pauses after it |
| ⟨longlist depth⟩ | acquire → screen → classify → appraise → ingest → longlist → constrain → propose | over every option |
| ⟨assess⟩ | [acquire with the option as intent, if its document set is thin → screen → classify → appraise → ingest] → extract(light) over the option's documents → synthesise(**profile**); "how sure" = the roll-up of appraise tiers already computed | per shortlisted option, on "Assess these N" |
| ⟨full run⟩ | the whole EB chain (incl. classify, select, stage-2, full extract, group) as a **child Evidence search task** seeded from the option with the profile template; the scoping profile re-reads its cells from the report | per option, user-triggered (ruling 9) |
| export | the Share/export seam (arch §10; no contract yet), not a component | user-triggered |

## 0 — inherit (optional; ruling 22)

- **In:** a linked Evidence search task. **Out:** a draft plan seeded from its question; its
  screened documents queued into the pool, flagged *inherited* for re-screening against the
  scoping plan; its report's theme claims and grouping rows queued as longlist suggestions
  labelled "from your evidence search" (the report holds no list of named interventions; `longlist`
  turns the rows into option suggestions).
- ✅ Nothing inherited is trusted because it was found before: inherited documents are
  re-screened and re-pass classify/appraise if their rubric version differs; inherited rows take
  the fait-accompli path like any suggestion. ✅ The run acquires beyond the inherited set; the
  Sources tab states inherited versus added. Fallback if a contract must trim: question and
  documents only. Kept as its own component so the inherited-versus-added accounting has one
  owner (owner, 2026-09-07).

## 1 — plan

- **In:** the user's question (or, in the sense-check branch, a named option); the conversation.
  **Out:** the plan object — question · what we are trying to change · who or what should change
  (target unit) · where · outcomes · **depth (asked every time, no default)** · constraints (each
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

## 2 — acquire · 3 — screen · 4 — classify · 5 — appraise (the EB spine, as is)

- **In:** the plan (or an option / variant as intent; or the baseline's source policy). **Out:**
  the screened-in document set with, per document: evidence type and tags (classify), quality tier
  under the rubric version (appraise), `text_basis`, and the screen's structured fields (🟡
  setting country, population, outcome family) so scope-shaped screens in `constrain` run on
  abstracts.
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
  measured) — the longlist metadata, including a descriptive "how sure" before assessment.
- ✅ **Same two machines as EB characterise, at option grain**: the bounded two-stage LLM grouping
  (discover, then assign every document, code-enforced exhaustiveness, an explicit unclustered
  bucket) discovers *options* rather than landscape themes and then groups options into themes;
  the deterministic coverage/patterns run per option instead of per run. **Different**: the output
  is an option schema with a specified design, two grouping levels, generation-free entrants, and
  relations. Named for what it produces (owner, 2026-09-07).
- ✅ Top-down: the **small, curated, versioned list of about ten domain-agnostic lever types**
  (regulate, subsidise, tax or charge, inform, provide a service, enforce existing powers, devolve,
  change who runs the system) prompts suggestions and checks coverage. Themes are never a fixed
  list (ruling 11). ✅ A user modification of an option's design mints a new option linked *variant
  of* its parent (ruling 15; which edits count is the agent's judgement, stated); packages and
  ingredients are linked *part of* and shown together. ✅ Generation is free: a suggested option
  needs no source and is labelled ([trust.md](trust.md)). ❓ Overlap/dedup and target longlist size
  (open question 4). 🟡 Taxonomy as a curated asset rather than prompt-internal text (open
  question 5).

## 7 — constrain (screen, modified)

- **In:** the longlist with coverage and specified designs; the plan's constraints. **Out:** each
  option marked *included* or *excluded: breaks "<constraint>"* (scope-shaped constraints only,
  ruling 23), or *no in-scope evidence*, plus a labelled **reasoned guess** per after-assessment
  constraint; the three default screens (relevant to outcomes · distinct · in scope) applied and
  cited like any other.
- ✅ The EB screen's per-item judgment with the object changed: an option judged against
  constraints instead of a document against an intent. Runs on coverage and the specified design
  as options complete; never on analysis. ✅ Thin evidence is noted, never a reason to exclude.
  ✅ Screens judge the **specified design**; a finding about the parent's typical implementations
  is not a finding against a variant (ruling 15). ✅ Corpus-based screen findings are cited by
  coverage denominator. ✅ Fallible by design, so every judgment is shown and reversible (*Include
  again*), and every exclusion is kept with its reason as institutional memory. ✅ Reasoned guesses
  are capped reasoning claims: a flag and a user-requested sort, never a screen and **never an
  input to `propose`** (rulings 12, 19; [trust.md](trust.md)).

## 8 — propose (new)

- **In:** the included options with coverage and relations; the user's additions. **Out:** the
  proposed shortlist — **one place per primary lever type present among the kept options**
  (ruling 20), each with one named reason from what coverage knows (distinctness, widest
  implementation record, only option of its lever type, thin evidence); gap messages naming
  secondary lever types ("Regulate: no dedicated option; touched by the youth guarantee package");
  the list of kept options not proposed, by theme; warnings when every place shares one ambition
  band or when a package and its own ingredient would both take places.
- ✅ Never a top-N; never a fused score; **study count alone and quality-tier distribution are
  never place reasons** (tiers are display and a user-requested sort only — owner, 2026-09-07,
  guarding hierarchy bias); reasoned guesses are not inputs (ruling 19); thin evidence is a reason
  to assess. ✅ Themes group but do not earn places; a singleton theme is proposed only if its
  primary lever type is otherwise uncovered. ✅ Places the user added are respected and worked
  around; PA advises on gaps and never removes (ruling 6). ✅ In the sense-check branch the
  proposal is the named option (rapid) or the named option plus its most similar neighbours,
  pre-ticked (standard) (ruling 25; ❓ similarity measure = open question 10). ✅ "Most promising"
  only after assessment, as per-axis sorts on comparable axes and conditional recommendations on
  those axes; before assessment `propose` describes coverage and gaps only.
- **Why new:** nothing in the EB selects a representative set over a fixed taxonomy; EB `select`
  picks documents for extraction by strategy, not options for coverage.

## 9 — extract (light) · 10 — synthesise (templates): inside ⟨assess⟩

- **In:** a shortlisted option with its specified design and ingested documents; the baseline's
  retrieved context (geography-tagged; a containing geography counts unless a more local fact
  contradicts it, ruling 18). **Out:** the verdict strip and the profile sections (§ Output
  structure in [capability.md](capability.md)).
- ✅ **extract, light field set** for the countable cells: direction (one vote per independent
  study, per outcome family, significance never counted — ruling 26; ❓ independence detection
  open, a trial/registration identifier is the candidate field), magnitude in native units with
  its comparator, population and period, design, setting. Run as a parallel per-source fan-out
  over the capped set so latency is close to one document's. ✅ **synthesise(profile)** by
  retrieval-augmented reading over the option's chunks for the narrative sections: mechanism and
  failure mode (tier-labelled) · constituents (a variant's parent evidence here as related
  evidence for a different design) · evidence for and against · variants in practice · case
  studies typed by tier · transferability working (three legs; moderator/dealbreaker extraction
  with quotes; context typed retrieved / stated by you / planned by you; weakest leg decides; no
  factor fractions — ruling 18) · assumptions · what it would take · reported cost beside the
  earlier guess. "How sure" = the roll-up of appraise tiers and study counts already computed at
  longlist depth.
- ✅ **Reads the full text of the documents it relies on, capped per option; every claim carries
  the depth of what was read** (`text_basis`; ruling 16). ✅ A variant is assessed on its own
  design (ruling 15). ✅ Shortlist only, on the user's word; every cell labelled *scoping pass*.
  ✅ Unassessed cells are honest empty states. 🟡 **Shape to spike** (open question 2): extraction
  is slower than reading, so the per-option document cap is the latency lever and the spike
  measures fit to the rapid budget; the stage-1 screen's structured fields give the abstract-level
  strip shown first.
- ✅ **synthesise(summary)** writes the summary above the assessed table: never a ranking — no
  superlatives across options; each effect with its own comparator, population and period;
  conditional recommendations only on comparable axes (ruling 17); the kept-but-unassessed options
  listed (ruling 19); the closing element **"What needs deciding or commissioning next"** (ruling
  21); in the sense-check branch also **"questions to put to the department"** (ruling 25). Not
  user-editable in v1 (ruling 14). ✅ **synthesise(baseline)** writes the "Do nothing" profile
  (what is in place · trend if nothing changes · who is affected · what is already changing ·
  what is contested · cost of inaction · key assumption · sources), reported facts only, every
  statement provenance-carrying, "not found" stated as such; the run **pauses** after it and the
  pause is a place to question it in chat (rulings 2, 24). ❓ Baseline sourcing mechanics (open
  question 6).

## ⟨full run⟩ — the boundary with EB (ruling 9)

- **In:** one shortlisted option. **Out:** a new Evidence search task seeded from the option, with
  the option-profile sections as its synthesis template; on completion the scoping profile
  re-reads its cells from the report, tagged *full run*, and keeps the scoping-pass version in
  History.
- ✅ The child task is listed under the parent, linked both ways, and shares its project and
  visibility. ✅ The user's stated context stays with the scoping task, so a transferability cap
  caused by unstated context survives the full run until the plan says otherwise. ✅ Stage-2
  full-text confirmation, `select` and full extraction happen here, not in scoping.

## export (Share seam)

- ✅ Bundles the summary, the assessed table, the option profiles, the baseline, the **full longlist
  with states and reasons**, the **shortlist assembly record** and the Sources statement (inherited
  versus added; what was read at which depth); claims breadth, never exhaustiveness (rulings 14,
  21). Arch §10 seam; no export contract drafted yet.
