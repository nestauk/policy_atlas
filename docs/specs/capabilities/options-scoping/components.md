---
type: Capability spec
title: Options Scoping — component skeleton
description: The OS components — declared I/O, what each reuses from the Evidence Base, realisation and gating — with the three depths and two gates made structural.
tags: [capability, options-scoping, components]
timestamp: 2026-09-04
---

# Options Scoping — component skeleton

The components, their declared I/O, what each reuses from the Evidence Base, realisation and
gating. Distilled from
[options-scoping-concept.md](../../sources/options-scoping/options-scoping-concept.md) (§ Shape,
§ Architecture stance, rulings 2–6, 9, 11, 12, 14). Shared tools and the findings schema are
owned by [../../system/execution-orchestration.md](../../system/execution-orchestration.md) and
[../../system/data-model.md](../../system/data-model.md); the EB components referenced below are
specified in [../evidence-base/components.md](../evidence-base/components.md).

```
plan ──▶ baseline ══gate══▶ retrieve ──▶ screen(stage 1) ──▶ mint ──▶ constrain ──▶ propose
                                                         (the longlist spine, runs over every option)
      ══gate: "Assess these N"══▶ assess ──▶ summarise ──▶ export        (shortlist only)
                                    └──▶ ramp (spawns an EB task per option)   (user-triggered)
```

- ✅ **Two gates are structural, not discretionary.** Nothing after `baseline` runs until the
  user confirms the plan against it; nothing after `propose` runs until the user says assess
  (rulings 2, 3). Re-runs after a plan change apply deltas (❓ granularity, concept open
  question 7).
- ✅ **The longlist spine runs over every option; `assess` runs over the shortlist only.** This
  is the cost model: everything before the second gate is cheap and covers the whole space;
  everything after it is per option and paid for only on options the user kept.
- ✅ **Reuse, do not re-derive.** `retrieve` is the EB's acquire (`search` is the only egress
  verb); `screen` is the EB's stage-1 consensus screen with the plan as the intent record;
  `assess` uses the EB's appraise, and either its extract or a retrieval-augmented reading over
  the option's documents (❓); `ramp` runs the whole EB pipeline. OS never orchestrates full EB
  runs per option inside its own run (concept § Architecture stance).

## Tool wiring (consolidated)

**Universal core, ambient to every component:** `search`, `retrieve`, `lookup`, `appraise`,
`produce-grounded-block`, `escalate`, `clarify`.

| # | Component | Centres on | Reuses from EB | Realisation | Gating |
|---|---|---|---|---|---|
| 1 | plan | the scaffolded planning conversation → plan object | the plan object and plan document (system § plan-as-object; EB plan UI) | agent (lead-authored prompt) | mandatory; gate: confirm |
| 2 | baseline | grey-literature + official-statistics retrieval → "Do nothing" profile | `search` (Overton, web), `produce-grounded-block` | procedure + agent | mandatory; **run pauses after** |
| 3 | retrieve | `search` over the evidence base for the plan | acquire | procedure | mandatory |
| 4 | screen | stage-1 title-and-abstract consensus screen, plan as intent | screen (stage 1 only; **no stage 2 in OS**) | per-doc fan-out | mandatory |
| 5 | mint | cluster screened interventions into options; name themes; map to lever types; add taxonomy suggestions and user additions | cluster / group (theming machinery) | procedure + agent | mandatory |
| 6 | constrain | hard screens on metadata and option description; reasoned guesses for after-assessment constraints | — | per-option fan-out (LLM judgment, checkable) | mandatory; every exclusion carries its constraint |
| 7 | propose | the coverage set on the theme × ambition grid, one named reason per place | — | procedure + agent | mandatory; user adds/removes on top |
| 8 | assess | the mini evidence search per shortlisted option → verdict strip + profile sections | appraise; extract **or** retrieval-augmented reading (❓); `produce-grounded-block` | per-option fan-out | **gate: "Assess these N"**; shortlist only |
| 9 | summarise | the summary above the assessed table, against doing nothing | `produce-grounded-block` | agent | after assess |
| 10 | export | the Export bundle (summary · table · profiles · baseline · what was searched) | Share/export seam (arch §10, no contract yet) | procedure | user-triggered |
| 11 | ramp | spawn an EB task from one option with the profile-shaped synthesis template; re-read the profile from the report | the whole EB spine + synthesis profile | orchestration | user-triggered, per option |

## 1 — plan

- **In:** the user's question; the conversation. **Out:** the plan object — question · what we
  are trying to change · who or what should change (target unit) · where · outcomes · depth ·
  constraints (each tagged *from your question* / *assumed* / *your call*; each constraint tagged
  *checked at longlist* or *checked after assessment*) · plan steps · check-ins (ruling 1, 12).
- ✅ Branches on the two jobs: *explore the option space* vs *sense-check one option* (the latter
  seeds the working set with one option; concept § Shape 1). ✅ The plan is a plan object in the
  system sense ([plan-as-object](../../system/plan-as-object.md)) and compiles to the run
  configuration; ❓ the scaffolding chat as a shared component with EB (open question 8).
- ✅ Prompt-bearing: lead-authored under [prompting.md](../../system/prompting.md).

## 2 — baseline

- **In:** the plan. **Out:** the "Do nothing" baseline profile (what is in place · trend if
  nothing changes · who is affected · what is already changing · cost of inaction · key
  assumption · sources), every statement provenance-carrying; "not found" stated as such.
- ✅ Reported facts only; the tool does not forecast; the key assumption is a labelled
  reasoning claim (tier 4). ✅ The run **pauses** after this component until the plan is
  confirmed against it. ❓ Sourcing mechanics (open question 6).

## 3 — retrieve · 4 — screen

- **In:** the plan. **Out:** the screened document pool with per-document metadata (source
  type, country, population, outcomes measured, year), the OS document set for this run.
- ✅ `retrieve` is EB acquire with `search` as the only egress verb. ✅ `screen` is EB stage 1 —
  the recall-oriented title-and-abstract consensus screen — with the plan as the id-keyed intent
  record; 🟡 the screen prompt returns a few structured fields (setting country, population,
  outcome family) so the scope-shaped screens in `constrain` run on abstracts, not full text.
  ✅ **No stage-2 full-text confirmation in OS** (ruling 3).
- ✅ Suggested and user-added options with no documents get their own small `retrieve` +
  `screen` with the option as intent, so every entrant is treated the same (concept § Shape 2).

## 5 — mint

- **In:** the screened pool; the lever-type taxonomy; user and ministerial additions. **Out:**
  the longlist — options (name, one-sentence description, constituent interventions with their
  documents, stated outcomes served, metadata) grouped into generated themes, each theme mapped
  to lever type(s) with a one-line "what it does".
- ✅ Bottom-up: interventions cluster into options (an option is an actionable aggregate of
  related interventions; drill-down shows the constituents) using the EB's theming machinery.
  ✅ Top-down: a **small, curated, versioned list of about ten domain-agnostic lever types**
  (regulate, subsidise, tax or charge, inform, provide a service, enforce existing powers,
  devolve, change who runs the system — the organisational branch) prompts suggestions and
  checks coverage ("no market-mechanism option; want one?"). ✅ Themes are never a fixed list
  (ruling 11). ❓ Overlap/dedup and target longlist size (open question 4). 🟡 Taxonomy as a
  curated asset rather than prompt-internal text (open question 5).
- ✅ Generation is free: a suggested option needs no source and is labelled as a suggestion
  ([trust.md](trust.md)).

## 6 — constrain

- **In:** the longlist with metadata; the plan's constraints. **Out:** each option marked
  *included* or *excluded: breaks "<constraint>"*, plus a labelled **reasoned guess** per
  after-assessment constraint; the three default screens (relevant to outcomes · distinct · in
  scope) applied and cited like any other.
- ✅ Runs on metadata and the option's description as options complete; never on analysis.
  ✅ Thin evidence is noted, never a reason to exclude. ✅ Fallible by design, so every judgment
  is shown and reversible (*Include again*), and every exclusion is kept with its reason as
  institutional memory. ✅ Reasoned guesses are capped reasoning claims: a flag and a sort,
  never a screen (ruling 12; [trust.md](trust.md)).

## 7 — propose

- **In:** the included options with metadata; the user's additions. **Out:** the proposed
  shortlist as places on the theme × ambition grid — one per surviving theme, spanning
  do-minimum → incremental → structural — each with one named reason from what metadata knows;
  coverage gaps named ("Organisational has no place: both options thin").
- ✅ Never a top-N; never a fused score. ✅ Places the user added are respected and worked
  around; PA advises on gaps and never removes (ruling 6). ✅ "Most promising" only as per-axis
  sorts and conditional recommendations, on what is known at this depth.

## 8 — assess

- **In:** the shortlisted options and their documents. **Out:** per option, the verdict strip
  and the profile sections (§ Output structure in [capability.md](capability.md)): effect as
  reported (direction by vote count of quality-screened studies with a discord flag; magnitude
  in native units with citations; the source's own characterisation quoted) · evidence strength
  with study count (from appraise) · where tried · transferability working (three legs;
  moderator/dealbreaker extraction with quotes and evidence-basis tags; the Factor | Your
  context | Basis table where only user-stated facts count; deterministic ceiling rules on
  verdict strength) · assumptions register (load-bearing, strength, the key one) · case studies
  typed by tier · what it would take (reported facts with provenance) · the reported cost
  replacing the earlier guess, shown side by side.
- ✅ Shortlist only, on the user's word; every cell labelled *scoping pass*. ✅ Unassessed
  cells are honest empty states ("not yet searched" / "no credible evidence found").
  ❓ Extraction vs retrieval-augmented reading; latency lever: strips first, deeper sections in
  the background or on first open (concept open question 2). ✅ Reuses the EB's causality
  taxonomy, discord detection and profile-not-scalar framing salvaged from V2 (concept § Effect
  cell, § Transferability cell).

## 9 — summarise · 10 — export

- ✅ `summarise` writes the short summary above the assessed table: PA's reading of the
  shortlist against doing nothing, never a ranking; the reasons differ per option and the table
  shows them. Not user-editable in v1 (ruling 14).
- ✅ `export` bundles the summary, the assessed table, the option profiles, the baseline and the
  Sources statement; states what was searched; claims breadth, never exhaustiveness. A Share
  concern (arch §10 seam; no export contract drafted yet).

## 11 — ramp (the boundary with EB)

- **In:** one shortlisted option. **Out:** a new EB task seeded from the option, with the
  option-profile sections as its synthesis template; on completion the scoping profile re-reads
  its cells from the report, tagged *full run*, and keeps the scoping-pass version in History.
- ✅ The child task is listed under the parent, linked both ways, and shares its project and
  visibility (ruling 9). ✅ The user's stated context stays with the scoping task, so a
  transferability cap caused by unstated context survives the full run until the plan says
  otherwise. ✅ Full-text confirmation happens here, not in scoping.
