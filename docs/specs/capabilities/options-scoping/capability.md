---
type: Capability spec
title: Options Scoping (OS)
description: The declarative options-scoping spec — the second v3.0 capability, an instance of the capability framework that reuses the Evidence Base's machinery in its own pipeline.
tags: [capability, options-scoping, compile-target]
timestamp: 2026-09-04
---

# Capability spec — Options Scoping (OS)

**The declarative spec.** Distilled from
[options-scoping-concept.md](../../sources/options-scoping/options-scoping-concept.md) (the
owner-agreed concept of 2026-09-01/02 and the wireframe-round rulings of 2026-09-03, hereafter
"concept § Shape", "concept ruling N"), now frozen origin; this spec + `docs/adr/` are canonical
([ADR 0002](../../../adr/0002-spec-governance.md)). OS is an **instance** of the capability
framework: the Tier-0 substrate, the retrieval contract, the findings layer, the grounding tiers
and the plan object are owned by the system contracts and only **referenced** here; the
Evidence Base's components are **reused** where named, never re-derived. This spec holds what is
**specific to OS**.

Companion files: [components.md](components.md) (the skeleton) · [trust.md](trust.md) (OS's
instance of the trust contract). System contracts:
[../../system/data-model.md](../../system/data-model.md) ·
[../../system/provenance-grounding.md](../../system/provenance-grounding.md) ·
[../../system/execution-orchestration.md](../../system/execution-orchestration.md) ·
[../../system/plan-as-object.md](../../system/plan-as-object.md) ·
[../../system/prompting.md](../../system/prompting.md). Sibling capability:
[../evidence-base/](../evidence-base/capability.md).

Status legend: ✅ settled · 🟡 leaning · ❓ open · ⏸ deferred.

## Artefact & scope

- ✅ **Outcome.** A user asks a scoping-shaped policy question and gets a transparently screened
  **longlist** of intervention options, a **shortlist** that covers the decision space, and, for
  the shortlisted options, an **assessment** (mechanism, effect as reported, evidence strength,
  transferability, case studies, assumptions, reported costs) — as a first version to work
  from, not a finished document (concept § Intent, § Shape 6).
- ✅ **Users and jobs.** Senior policy officials scoping options early (departmental longlist
  work) and central teams sense-checking one named option. The two jobs are one pipeline with
  two entry branches: *explore the option space* and *sense-check one option* (the latter seeds
  the working set with one option and asks what sits next to it) (concept § Shape 1).
- ✅ **"Scoping", not appraisal.** Full Green Book appraisal is a future composition of several
  capabilities; OS strikes at the early longlist moment where real appraisals fail (narrow
  option sets, missing counterfactuals, post-hoc justification) (concept § Intent).
- ✅ **Generalisation is a v1 requirement**, not a nice-to-have: good outputs across unrelated
  policy domains (concept § Intent). The lever-type taxonomy is domain-agnostic by design;
  themes are generated per problem (concept ruling 11).
- ✅ **Conversation-first.** The dialogue is the spine; the plan, baseline, longlist, shortlist
  and profiles are living artefacts the conversation produces and updates. Both controls write
  the same state: a chat instruction and a direct manipulation are equivalent, and a direct
  manipulation is logged as the user's turn (concept § Shape; ruling 1).
- ✅ **Vocabulary.** Themes (the higher level) → Options (the actionable level) → constituent
  interventions and their documents. Green Book words in the product: longlist, shortlist, do
  nothing, do minimum. "Lever family", "annex", "thread", "pin", "set aside", "promote", "frame"
  never appear user-facing (concept § Vocabulary; rulings 5, 8, 13; the shell is "Plan").
- ✅ **Rigidity:** structured — a fixed stage order with two hard gates (below), user
  iteration on top of every stage.
- ✅ **Dependencies.** Upstream: none at run time — OS assembles its own document pool with the
  EB's acquire and screen components inside its own pipeline; it never orchestrates full EB runs
  per option (concept § Architecture stance). Downstream: a shortlisted option can **spawn an EB
  task** (the full evidence search, ruling 9) and can seed a Theory-of-Change session (⏸, a
  dotted-line consumer). 🟡 Reading an existing EB corpus as the pool is bracketed as
  meta-analysis territory, possibly its own capability.

**Scope boundaries** (concept § Boundaries, § Out of scope):
- ⏸ Cross-capability triage is the product shell's job: OS assumes it receives scoping-shaped
  questions and defines only its internal branch.
- ⏸ **Critical review** of an existing artefact (draft submission, business case) is a separate
  future capability; the input-type line is *question or idea in a sentence* → OS, *existing
  artefact* → critical review. They share the assumptions vocabulary, coverage machinery and the
  three-legs transferability argument by design.
- ⏸ Jurisdiction-specific "will it work for you" analysis (the future applicability
  capability): the interactive factor-resolution loop, constraint-tolerance and local-resource
  analysis, political machinery, any numeric fit score.
- ✅ Out of v1: costing or value-for-money **analysis** (reported costs with provenance are in);
  political viability or appetite in any form; full baseline analysis; equality impact
  assessment (reported distributional effects only); composite scores or rankings;
  collaborative rating (single-user v1; the data model anticipates multiple raters);
  organisation-level institutional memory (workspace-level v1); a visual Theory-of-Change
  editor; deep mode; meta-analysis over EB corpora; meeting-speed latency; free-text editing of
  the summary (ruling 14).

## Depths and modes

- ✅ **Three depths of evidence work, one gate between the cheap and the expensive**
  (concept ruling 3):
  1. *Longlist depth* — retrieval, the EB's title-and-abstract consensus screen once at the plan
     level, clustering, and cheap metadata per option (study count, source type, countries,
     populations, outcomes measured). Runs over every option. No per-option analysis.
  2. *Assessment depth* — the **mini evidence search**, run on the **shortlist only** and only
     when the user says so ("Assess these N", with a time estimate). Fills the verdict strip and
     the option profile. Every cell is labelled *scoping pass*.
  3. *Full evidence search* — the complete EB pipeline for **one option**, user-triggered, which
     mints its own EB task (ruling 9).
- ✅ **No full-text screening in scoping.** Stage-2 confirmation belongs to the full evidence
  search and is one of the things the "full run" label buys.
- ❓ Whether assessment cells come from the EB's per-document extraction or from
  retrieval-augmented reading over the option's documents is an **implementation decision**
  (concept open question 2; spike before the assessment task is contracted).
- ✅ **Modes.** Rapid and standard in v1, mirroring EB modes and mapped to the two jobs (rapid =
  sense-check, standard = longlist). Deep (per-option stress-testing, mechanism-analogy search)
  ⏸ later. Modes differ in breadth and depth of grounding and in latency. ❓ The rapid-mode
  latency budget is a number the contract must set (concept open question 3).
- ✅ **Cost lever.** If a standard run is too expensive the cut is depth, not coverage: a lighter
  longlist search, and the transferability working only for shortlisted options. ❓ The
  per-run price envelope (≈ N shortlisted options × one mini search) is open question 2.

## Pipeline and gates

Stage order (concept § Shape 1–6, rulings 2–6, 14):

```
plan ──confirm──▶ baseline ══PAUSE: confirm plan against baseline══▶ longlist
     ──▶ [screens + coverage proposal, as options complete] ──▶ shortlist (user adds/removes)
     ══GATE: "Assess these N"══▶ assessment ──▶ summary ──▶ export
                                     └──per option──▶ full evidence search (EB task)
```

- ✅ **Plan.** A scaffolded conversation fills the plan: the question · what we are trying to
  change · **who or what should change** (the target unit — people, firms, places,
  organisations, systems; PICO's "population" is the special case) · where · outcomes · depth ·
  constraints, each tagged *from your question* / *assumed* / *your call*. Presented exactly like
  the EB search plan (ruling 1; see § Product surface). Non-linear: the user revises the plan
  after seeing evidence and re-runs apply **deltas, not restarts** (concept § Shape 1; ❓ delta
  granularity and working-set versioning are open question 7).
- ✅ **Baseline, and it pauses** (ruling 2). Confirming the plan builds the baseline only. The run
  stops; the user reads it, changes the plan if needed, and confirms the plan before any option
  is generated. The baseline is a **profile of "Do nothing"** (structure in § Output structure).
  ❓ Baseline content generation couples to grey-literature and official-statistics sourcing
  (open question 6).
- ✅ **Longlist.** Two directions into one funnel: bottom-up (screened documents cluster into
  options; drill-down shows the constituents) and top-down (lever-type suggestions, the user's
  and ministerial additions). Every entrant gets the same treatment — the fait-accompli fix
  (concept § Shape 2). ❓ Minting mechanics — clustering, overlap and dedup, target longlist
  size — are open question 4.
- ✅ **Screening is a pipeline stage, not a user step** (ruling 4). Screens run on longlist
  metadata as options complete. Hard screens = the user's session constraints of the
  scope-shaped kind plus three defaults (relevant to stated outcomes, distinct, within scope).
  Every exclusion cites the specific constraint it broke; **thin evidence never excludes an
  option, it is noted**; an excluded option stays in its theme and can be included again.
- ✅ **Two kinds of constraint** (ruling 12). Scope-shaped constraints (geography, target group,
  sector, lever type, "no X" about the option itself) are checked at the longlist. Effect- and
  cost-shaped constraints ("low cost", "at least moderate evidence") are checked after
  assessment; the plan says so; until then each option carries a labelled **reasoned guess**
  (see [trust.md](trust.md)).
- ✅ **Shortlist assembly is separate from screening** (ruling 6). The theme × ambition grid is
  the instrument (ambition kept, descriptive: do minimum · incremental · structural). The
  proposed shortlist is a **representative coverage of the decision space, not a top-N** — one
  place per surviving theme spanning the ambition range, each place picked on a **single named
  axis stated in its reason**; pre-assessment reasons are limited to what metadata knows ("most
  studies in theme", "widest implementation record", "only option in theme", "thin evidence");
  "strongest evidence" and "largest reported effects" arrive with the assessment as sorts.
  A place is filled in one of two ways — **proposed by Policy Atlas** with its reason, or
  **added by you**; when the user adds, PA advises on coverage gaps and never removes. "Most
  promising" is served honestly: per-axis sorts and **conditional recommendations** ("if your
  priority is X, A and B lead"); fused orderings are permanently out.
- ✅ **One shortlist action, plain words** (ruling 5). *Add to shortlist* is available from the
  moment an option exists (longlist row, option page, grid); *Remove from shortlist* reverses it;
  *Exclude* and *Include again* are the user's screening actions. An option the user added keeps
  its place through re-runs; screens still run on it and their finding shows on it; assessment
  is unaffected.
- ✅ **Assessment** runs on the shortlist only, on the user's word. It produces the verdict strip
  per option and the option profile, all labelled *scoping pass* (see § Output structure and
  [trust.md](trust.md)).
- ✅ **Summary and export** (ruling 14). A short summary above the assessed table — PA's reading
  of the shortlist against doing nothing, never a ranking. The "editable first version" is
  delivered by **Export**, a Share concern: it bundles the summary, the assessed table, the
  option profiles, the baseline and the Sources statement of what was searched, states what was
  searched and claims breadth, never exhaustiveness.
- ✅ **The full evidence search mints its own EB task** (ruling 9): seeded from the option,
  synthesis template = the option-profile sections, listed under the parent scoping task and
  linked both ways, sharing its project and visibility. The scoping profile then **reads its
  cells from that report** ("full run"), keeps the scoping-pass version in History, and keeps the
  user's context with scoping (so a transferability cap set by unstated context survives).

## Output structure

- ✅ **Baseline profile ("Do nothing")** (ruling 2). Its own structure, different from an option's
  because the question is different: what is in place · trend if nothing changes · who is
  affected (where the target unit is checked against the data) · what is already changing ·
  cost of inaction · key assumption · sources. Reported facts only; the tool does not forecast;
  the source-tier skew (official statistics, grey literature) is visible. "Do nothing" is the
  reference wherever options appear — a sentence with a link on the longlist, an unremovable
  reference on the shortlist, a two-sentence band above the assessed table — **never a grid
  row** (its cells would be n/a).
- ✅ **Longlist.** Options grouped by generated theme; each theme carries a one-line "what it
  does" mapped to its lever type; each option carries its name, a one-sentence description, the
  stated outcomes it is for, and its state (on the shortlist · suggested · added by you ·
  excluded with the constraint). Two views: list (for judging each option) and grid (theme ×
  ambition, for judging the set). A click opens a light **option-before-assessment** page: what
  it is for · what the evidence base holds so far · screens and guesses · where it came from.
- ✅ **Shortlist.** One list at two stages: before assessment, the places with their reasons and
  the assess action; after, the assessed table for the same options with the summary above it.
- ✅ **Assessed table = verdict strips stacked** (ruling 7). Six columns: Option (with its
  description) · How big, as reported · How sure · Where tried · Transferability · Key
  assumption. No study-design labels in the table (they belong to the profile). One provenance
  tag per row (*scoping pass* / *full run*). The option name opens the profile; there is no
  second, expandable layer. Sortable by any single column; **no composite score, ever.**
- ✅ **Option profile** (concept § Option click-through; rulings 8, 13). Layered skim → sections
  → next steps. *At a glance*: what it is in two plain sentences · how big (as reported, native
  units) · how sure (evidence strength and study count) · where tried · transferability verdict
  with its cap reason · the key assumption to test first. Deliberately **not** in the strip:
  cost, mechanism prose, case-study detail. Sections, each collapsible with a one-line summary
  visible when collapsed ("At a glance" always open): How it works (mechanism and main failure
  mode, tier-labelled) · What it is made of (constituent interventions, each linking to its
  documents) · Evidence for and against (tally line; strongest for / strongest against; common
  criticisms — balance of evidence, never the most supportive studies) · How it varies in
  practice (design variants observed across implementations) · Case studies (each with what they
  did, what happened, what made it work or not, and what to watch for; typed by source tier) ·
  Transferability working (the Factor | Evidence says | Your context | Basis table) ·
  Assumptions (load-bearing, strength, the key one) · What it would take (implementation
  requirements, reported costs, time to impact, distributional notes — provenance-carrying, no
  analysis). Next steps: run a full evidence search · start a theory of change (⏸ consumer) ·
  remove from shortlist. No export from the profile.
- ✅ **Case studies** come from three tiers typed by provenance: the academic corpus (especially
  observational and quasi-experimental implementation accounts), **Overton grey literature (the
  workhorse and the USP)**, and supplementary verified web links (gap-filler, lowest tier). A
  case study never silently raises an evidence-strength rating (concept § Case-study sourcing).
- ✅ **Sources tab**: what was searched (the coverage statement: documents retrieved and passed,
  grey literature, web, screens applied, not searched) · all sources · sources by option.
- ✅ **Density rule.** Never all layers at once; collapsed headers carry their takeaways; detail
  on demand. Applies to every scoping surface (concept § Option click-through).

## Product surface

Settled by the owner on the wireframes (rulings 1, 13; source
[README](../../sources/options-scoping/README.md)):

- ✅ **Navigation is the EB task's**: Plan · Results · Sources · Share · History, with Results
  split into **Baseline · Longlist · Shortlist**. The chat is always the left column under the
  tabs; the right column holds the tab's content and opens wide for the longlist, the grid and
  the profiles. ("Assessment" is a state the shortlist is in, not a place.)
- ✅ **The plan is presented exactly like the EB search plan**: the navy plan document beside the
  planning conversation, with Question · What we are trying to change · Settings · Constraints
  (each with when it is checked) · Plan steps · Check-ins, an Edit action per section, and one
  start action.
- ✅ **Design language follows the EB report**: one body size, grey for secondary text, small
  uppercase labels only where necessary, as few chips and colours as possible (blue for links,
  the primary action and shortlist state; states written as words), no jargon. Outputs (baseline,
  profile) read as **linear text** with a side contents outline and collapsible sections;
  working lists (the longlist) keep the typography but stay **clickable lists** — selectable
  rows with their actions as line icons (add to shortlist · remove · exclude · include again;
  words as tooltips) and no contents sidebar.
- ✅ Sample constraints and questions in design artefacts use plain words so the logic can be
  checked by eye (ruling 10). The design reference is the NEET question; nothing on it is a
  finding.

## Check-in points

- ✅ **Plan confirmation** (before anything runs) and **plan re-confirmation against the
  baseline** (before any option is generated) — the first gate.
- ✅ **"Assess these N"** — the second gate, the only point after the longlist where the user
  commits real time and money on options other than those they chose to keep.
- ✅ **Full evidence search** — per option, always the user's call.
- ✅ Everything else is iteration on living artefacts, not a gate: add or remove from the
  shortlist, exclude or include again, revise the plan (deltas), ask for a per-axis sort or a
  conditional recommendation.

## Evaluation (❓ shapes the build order)

Open question 1 of the concept, to be sketched before committing the longlist and assessment
contracts:
- **Option recall** against longlists in historical business cases and impact assessments — a
  floor, not a target, since those longlists are documented as narrow; expert-built reference
  longlists are needed too.
- A **domain-diverse question set seeded from the real V2 query log's non-health entries**
  (refineries, insolvency, regional disparities, R&D talent, digital infrastructure, waste
  management, university finances, small boats).
- **Screening-reason quality**; **transferability-judgment calibration** (the transferability
  cell is a first-class eval axis); **effect-cell fidelity** against the studies;
  **guess-versus-evidence agreement** for the reasoned guesses (ruling 12).

## Open decisions and deferred seams

❓ Open (carried from concept § Open questions, updated by the rulings): 2 mini-search
mechanics and cost envelope (extraction vs retrieval-augmented reading) · 3 rapid latency
budget · 4 option-minting mechanics · 5 taxonomy storage (curated asset 🟡 vs prompt-internal)
· 6 baseline generation and grey-literature sourcing · 7 iteration mechanics and versioning ·
8 the entry point from the product's front door (the rest of the product surface is settled) ·
9 magnitude banding (requires its own eval before any band reaches users).

⏸ Deferred: deep mode · the applicability capability · critical review · the Theory-of-Change
session · collaborative rating · org-level memory · meta-analysis over EB corpora · reading an
existing EB corpus as the pool (🟡 bracketed).
