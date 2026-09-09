---
type: Capability spec
title: Options Scoping (OS)
description: The declarative options-scoping spec — the second v3.0 capability, an instance of the capability framework that reuses the Evidence search's machinery in its own pipeline.
tags: [capability, options-scoping, compile-target]
timestamp: 2026-09-07
---

# Capability spec — Options Scoping (OS)

**The declarative spec.** Distilled from
[options-scoping-concept.md](../../sources/options-scoping/options-scoping-concept.md) (the
owner-agreed concept of 2026-09-01/02, the wireframe-round rulings of 2026-09-03 and the
review-round rulings of 2026-09-07, hereafter "concept § Shape", "concept ruling N"; the
review-round rulings 15–44 win where they differ), reopened in PR #63 for the review round; this spec + `docs/adr/` are canonical
([ADR 0002](../../../adr/0002-spec-governance.md)). OS is an **instance** of the capability
framework: the Tier-0 substrate, the retrieval contract, the findings layer, the grounding tiers
and the plan object are owned by the system contracts and only **referenced** here; the
Evidence search's components are **reused** where named, never re-derived. This spec holds what is
**specific to OS**.

Companion files: [components.md](components.md) (the skeleton) · [trust.md](trust.md) (OS's
instance of the trust contract). System contracts:
[../../system/data-model.md](../../system/data-model.md) ·
[../../system/provenance-grounding.md](../../system/provenance-grounding.md) ·
[../../system/execution-orchestration.md](../../system/execution-orchestration.md) ·
[../../system/plan-as-object.md](../../system/plan-as-object.md) ·
[../../system/prompting.md](../../system/prompting.md). Sibling capability:
[../evidence-search/](../evidence-search/capability.md).

Status legend: ✅ settled · 🟡 leaning · ❓ open · ⏸ deferred.

## Artefact & scope

- ✅ **Outcome.** A user asks a scoping-shaped policy question and gets a transparently screened
  **longlist** of intervention options, a **shortlist** that covers the decision space, and, for
  the shortlisted options, an **assessment** (mechanism, effect as reported, evidence strength,
  transferability, case studies, assumptions, reported costs) — as a first version to work
  from, not a finished document (concept § Intent, § Shape 6).
- ✅ **Users and jobs.** Analysts and policy officials building the options case early
  (departmental longlist work), and senior officials and decision makers choosing between
  options or sense-checking one named option. The two jobs carry equal weight (a
  primary-author / senior-reader hierarchy was rejected, ruling 29). They are one pipeline with
  two **entry branches**: *explore the option space* and *sense-check one option* (ruling 25;
  § Sense-check below). Users also differ, independently of role, in how well they know the
  domain (ruling 24) and in whether they arrive with an Evidence search already run (ruling 22).
- ✅ **"Scoping", not appraisal.** Full Green Book appraisal is a future composition of several
  capabilities; OS strikes at the early longlist moment where real appraisals fail (narrow
  option sets, missing counterfactuals, post-hoc justification) (concept § Intent).
- ✅ **Generalisation is a v1 requirement**, not a nice-to-have: good outputs across unrelated
  policy domains (concept § Intent). The lever-type taxonomy is domain-agnostic by design;
  themes are generated per problem (concept ruling 11).
- ✅ **Conversation-first.** The dialogue is the spine; the plan, baseline, longlist, shortlist
  and profiles are living artefacts the conversation produces and updates. Both controls write
  the same state: a chat instruction and a direct manipulation are equivalent, and a direct
  manipulation is logged as the user's turn (concept § Shape; ruling 1). The user **resumes
  from the current analysis, never by replaying the chat** (ruling 21).
- ✅ **Vocabulary.** Themes (the higher level) → Options (the actionable level) → constituent
  interventions and their documents. An option has a **specified design**; options relate as
  **variant of** and **part of** (ruling 15). Every option has one **primary lever type** and may
  touch others; coverage is counted over primary lever types, not over themes (ruling 20). Green Book words in the product: longlist, shortlist, do
  nothing, do minimum. "Lever family", "annex", "thread", "pin", "set aside", "promote", "frame"
  never appear user-facing (concept § Vocabulary; rulings 5, 8, 13; the plan lives in the "Agent"
  tab, ruling 40).
- ✅ **Rigidity:** structured — a fixed stage order with two hard gates (below), user
  iteration on top of every stage.
- ✅ **Dependencies.** Upstream: optional. A scoping task may **start from an Evidence search
  task** (a Link, ruling 22): its question seeds the plan, its screened documents enter the
  pool and are re-screened against the scoping plan, its report's interventions enter the
  longlist as labelled suggestions, and — when the search ran the deep chain — its **extracted
  findings** are inherited too, so clustering works at finding grain and assessment skips the
  light extraction for those documents (ruling 31); the run still retrieves beyond the inherited set and the
  Sources tab states inherited versus added. Otherwise OS assembles its own pool with the EB's
  acquire and screen components inside its own pipeline; it never orchestrates full EB runs per
  option (concept § Architecture stance). Downstream: a shortlisted option can **spawn an EB
  task** (the full evidence search, ruling 9) and can seed a Theory-of-Change session (⏸, a
  dotted-line consumer). ⏸ Meta-analysis across several corpora stays deferred.

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
  the summary (ruling 14); a whole-longlist "Assess all kept options" action (ruling 19,
  inference cost); an orientation / domain-primer capability for newcomers (ruling 24; see
  `docs/deferred.md`).
- ✅ **No composite scores or rankings is a product boundary**, justified by the incentive
  findings of the Green Book Review 2020 and by [trust.md](trust.md); the Green Book 2026
  recommends rather than mandates the options framework and permits facilitated MCDA at longlist
  stage (not the simple weight-and-score MCA it recommends against), so this is not a Treasury
  prohibition (concept § Intent, corrected 2026-09-07).

## Depths and modes

- ✅ **Three depths of evidence work, one gate between the cheap and the expensive**
  (concept ruling 3):
  1. *Longlist depth* — the EB's mandatory spine as is (acquire, title-and-abstract screen,
     classify, appraise, full-text ingest) once at the plan level, then clustering into options
     with per-option coverage: study count by evidence type and **quality tier**, countries,
     populations, outcomes measured (owner, 2026-09-07: classify and appraise always run on
     acquired documents, so a **source-quality profile** of the documents that mention an option
     exists before assessment — shown on the option card and as a user-requested sort, never a
     place reason, and **never called "how sure"**, ruling 33). Runs over every option. No
     per-option reading.
  2. *Assessment depth* — the **mini evidence search**, run on the **shortlist only** and only
     when the user says so ("Assess these N", with a time estimate). It **reads the full text of
     the documents it relies on**, capped per option (ruling 16; full text is already fetched for
     the whole screened-in set, so the cost is the reading). Per option: a targeted acquire if
     its document set is thin, a light extraction for the countable cells, and synthesise with
     the profile template. Fills the verdict strip and the option profile. Every cell is labelled
     *scoping pass*.
  3. *Full evidence search* — the complete EB pipeline for **one option**, user-triggered, which
     mints its own EB task (ruling 9).
- ✅ **Claim depth follows reading depth** (ruling 16). Screening stays title-and-abstract; no
  stage-2 confirmation in scoping (that is one of the things "full run" buys). Every claim
  carries the depth of what was read; a section may not assert what the read material does not
  support; abstracts are quotable anywhere; a document with no obtainable full text supports
  abstract-level claims and is labelled so. "Scoping pass" = screened on titles and abstracts,
  full text read for the documents cited, document set not confirmed.
- 🟡 **Assessment shape to check** (concept open question 2, owner 2026-09-07). The countable
  cells (direction per study, magnitude with its comparator and period, study design, setting)
  come from a **light per-document extraction** — a small field set, not the EB's full schema —
  run as a parallel fan-out over the capped set so latency is close to one document's, not the
  sum. The narrative sections (mechanism, case studies, what it would take, moderator quotes)
  come from **retrieval-augmented reading** over the read texts. The stage-1 screen's structured
  fields give an abstract-level strip before any full text is read. The per-option document cap
  is the latency lever; the **read set under the cap is chosen by the EB's `select` with a scoping
  strategy so that distinct implementations, the required outcomes and the counter-case
  survive**, omissions are represented, and a budget-limited result may be explicitly incomplete
  (rulings 38, 43); the check measures **whole-run** time to a usable result, not extraction alone.
  Mentions and the abstract-level fields come from `extract`'s abstract profile over every
  screened-in document; the screen is unchanged (ruling 43). ❓ How "one vote per independent study" detects
  several papers on one trial is open (a trial or registration identifier in the light
  extraction is the candidate).
- ✅ **Depth settings and entry branches are orthogonal** (ruling 25). *Rapid* and *standard*
  govern retrieval breadth and documents read per option, and apply to both branches; **the plan
  asks for depth every time, in both branches; there is no default** (owner, 2026-09-07). The
  words are the Evidence search's user-facing **rapid / standard / deep** (ruling 40). Deep (per-option stress-testing, mechanism-analogy
  search) ⏸ later. ❓ The rapid latency budget is a number the contract must set (concept open
  question 3).
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
  the EB search plan (ruling 1; see § Product surface). *(Owner ruling 2026-09-09, with
  decision-sheet row D3.)* **Where** is the jurisdiction the policy would apply to — country, UK
  nation, region or local authority — and **defaults to the United Kingdom**; the user narrows or
  changes it, and the agent asks when the question implies a nation or place. **Setting** is where
  the **target unit** experiences the intervention — the delivery point or channel: schools,
  workplaces, primary care, an employer's payroll, the planning system — generalised from the
  finding field's people-centric wording as target unit was from population. It is **not a
  mandatory slot**: a user with a preference states it as a scope-shaped constraint (ruling 12),
  which the planning conversation offers and which is checked against the specified design;
  without one the longlist spans settings and shows setting as a facet. Where and setting are
  never conflated. The UK default is a candidate for the Evidence search's planning chat, not
  applied there in this ruling. Non-linear: the user revises the plan
  after seeing evidence and re-runs apply **deltas, not restarts** (concept § Shape 1; ❓ delta
  granularity and working-set versioning are open question 7).
- ✅ **Baseline, and it pauses** (rulings 2, 24). Confirming the plan builds the baseline only. The
  run stops; the user reads it, **questions it in chat**, changes the plan if needed, and
  confirms the plan before any option is generated. The baseline is a **profile of "Do
  nothing"** (structure in § Output structure): empirical premises sourced, interpretations (the
  key assumption, what is contested) labelled reasoning (ruling 40). No orientation stage; the
  baseline's "what is contested" element is how newcomers are served in v1. ❓ Baseline content generation couples to
  grey-literature and official-statistics sourcing (open question 6).
- ✅ **Longlist.** Two directions into one funnel: bottom-up (**intervention mentions** — not
  documents — cluster into options, many-to-many, since a document may discuss a bundle or, as a
  systematic review does, many interventions; drill-down shows the constituents; ruling 31) and
  top-down (lever-type suggestions, the user's
  and ministerial additions, and a linked Evidence search report's interventions labelled "from
  your evidence search", ruling 22). Every entrant gets the same treatment — the fait-accompli
  fix (concept § Shape 2). **A user modification of an option's design becomes a new option,
  variant of its parent, with its own mini search** (ruling 15); which edits count as a design
  change is the agent's judgement, stated in the chat, with no fixed rule (owner, 2026-09-07); a
  substantive edit suspends inherited claims until the variant's own assessment; the default
  *distinct* screen never excludes a variant or a part-of relation; support binds to a finding
  and a specified design, never to a document (ruling 36); packages and ingredients are linked
  part of and shown together. ❓ Minting mechanics — clustering, overlap and dedup,
  target longlist size — are open question 4; 🟡 clustering at option grain is unproven and is
  checked before the longlist contract (ruling 31).
- ✅ **Screening is a pipeline stage, not a user step** (ruling 4). Screens run on longlist
  metadata as options complete. Hard screens = the user's session constraints of the
  scope-shaped kind plus three defaults (relevant to stated outcomes, distinct, within scope).
  Every exclusion cites the specific constraint it broke; **thin evidence never excludes an
  option, it is noted**; an excluded option stays in its theme and can be included again.
- ✅ **Three kinds of constraint** (rulings 12, 23). *Scope-shaped* constraints (geography,
  target group, sector, lever type, "no X" about the option itself) are checked at the longlist
  against the option's specified design. *Effect- and cost-shaped* constraints ("low cost", "at
  least moderate evidence") are checked after assessment; the plan says so; until then each
  option carries a labelled **reasoned guess** that is a flag and a user-requested sort only
  (see [trust.md](trust.md)). *Evidence restrictions* ("OECD evidence only"; "evidence-scope
  constraints" in the frozen rulings) are the Evidence search's search-directive filters —
  country group, years, languages — applied at retrieval (owner ruling on decision-sheet row C1,
  2026-09-09; the Sources statement says they filter by where a source was published, not where a
  study was done) and **can never exclude a known option**; an option whose only example
  is out of scope stays, marked "no in-scope evidence" (an evidence-scope constraint can prevent
  an option from ever being discovered, so the breadth claim is bounded by the authorised scope,
  ruling 36). The agent asks when a sentence is ambiguous between the kinds. Screen findings
  that rest on the corpus are cited. After assessment, an effect- or cost-shaped constraint that
  fails or cannot be checked is shown on the option ("breaks: low cost (assessed)" /
  "unresolved: cost not comparable"); the option stays and the user decides (ruling 40).
- ✅ **Shortlist assembly is separate from screening** (rulings 6, 19, 20). The proposed
  shortlist is a **provisional allocation of reading effort across the decision space, not a
  top-N** and not a certificate of representative coverage (ruling 37): **one place per primary
  lever type present among the kept options**, each picked on a **single named axis stated
  in its reason**. An option's secondary lever types do not fill places but do shape the gap
  message ("Regulate: no dedicated option; touched by the youth guarantee package") (owner,
  2026-09-07). Themes group the longlist and label the grid but do not earn places; a
  single-option theme gets no automatic place unless its primary lever type is otherwise
  uncovered.
  Pre-assessment reasons are limited to what coverage knows (distinctness, "widest
  implementation record" = implementations and countries recorded in the mentioning documents,
  "only option of its lever type", "thin evidence" = few mentioning documents or none of the
  required outcome; ruling 37); **study count alone
  and quality-tier distribution are never reasons** (tiers are display and a user-requested sort
  only, guarding hierarchy bias — owner, 2026-09-07), **reasoned guesses never feed the
  proposal**, and thin evidence is a reason to assess. The proposal never fills two places with a package and its own ingredient
  without saying so, and warns when every place shares one ambition band. "Strongest evidence"
  arrives with the assessment as a sort. A place is filled in one of two ways — **proposed by
  Policy Atlas** with its reason, or **added by you**; when the user adds, PA advises on
  coverage gaps and never removes. "Most promising" is served honestly and **only after
  assessment**: per-axis sorts on comparable axes and **conditional recommendations** on those
  axes only. Before assessment the agent describes coverage and gaps and makes no "if your
  priority is X" statements (owner, 2026-09-07). Fused orderings are permanently out.
- ✅ **One shortlist action, plain words** (ruling 5). *Add to shortlist* is available from the
  moment an option exists (longlist row, option page, grid); *Remove from shortlist* reverses it;
  *Exclude* and *Include again* are the user's screening actions. An option the user added keeps
  its place through re-runs; screens still run on it and their finding shows on it; assessment
  is unaffected.
- ✅ **Assessment** runs on the shortlist only, on the user's word. It produces the verdict strip
  per option and the option profile, all labelled *scoping pass* (see § Output structure and
  [trust.md](trust.md)). The summary and the export **list every kept option that was not
  assessed**, by theme (ruling 19).
- ✅ **The report and export** (rulings 14, 17, 21, 32). The Result is the **report** (§ Output
  structure): written from the assessment, rewritten by a full run; before assessment the Result is the longlist (ruling 50). Its top-line section
  is what ruling 14 called the summary — PA's reading, never a ranking: no superlatives across
  options; each effect with its own comparator, population and period; conditional
  recommendations only on comparable axes and only after assessment; cost comparisons only on
  matching bases (ruling 33). Its closing section, **"What needs deciding or commissioning
  next"**, is built from the unresolved differences, the unassessed options and the conditions
  verdicts rest on; before assessment it identifies unknowns only and carries no conditional
  recommendation, and a question never carries an unsupported premise (ruling 39). The "editable
  first version" is delivered by **Export**, a Share concern: the report with its attachments —
  the option profiles, the baseline profile, the **full longlist with states and reasons**, the
  **shortlist assembly record** (each place, its reason, who filled it) and the Sources statement
  of what was searched; it claims breadth, never exhaustiveness. The author's own steer is
  written outside Atlas.
- ✅ **The full evidence search mints its own EB task** (rulings 9, 41): seeded from the option,
  synthesis template = the option-profile sections, listed under the parent scoping task and
  linked both ways, sharing its project and visibility. The child report, written with that
  template and given the scoping task's user context as input, **computes the profile's
  judgement cells itself** (how sure, transferability and its conditions, the key assumption)
  under the OS trust rules; that report **is the option profile** after a full run, shown in
  place in the scoping task tagged "full run" with the scoping frame around it (shortlist place,
  row in the scoping report, "what changed" from History) — one document, two homes, no mirror
  (ruling 47). The scoping-pass profile is its earlier version, kept in History, and the context
  stays owned by scoping (so a cap set by unstated context survives). This widens the Evidence
  search's declared output boundary for the profile-template case only.

### The sense-check branch (ruling 25)

- ✅ **Input:** one named option, often a minister's. The agent infers the problem it addresses,
  the target unit, the outcome and the place; the user confirms a short plan. The option enters
  as added by you with its specified design (so a variant of a known approach is recognised as
  one).
- ✅ **Baseline:** light, still paused, one beat ("is this already being done, and what is the
  trend?").
- ✅ **Neighbours at metadata depth only**, as context: parent and variants, options of the
  same lever type, and the lever types the idea does not touch. Secondary on the page.
- ✅ **Proposal through the gate.** Rapid: the named option alone. Standard: the named option
  **plus its most similar neighbours plus one challenger** — an option reaching the same stated
  outcome through a different primary lever type, when the longlist has one — pre-ticked, one
  confirmation, each comparator's reason stated (ruling 37). Each assessed at the chosen depth.
  ❓ The similarity measure is an implementation decision (open question 10).
- ✅ **Primary surface = the report opened on the named option**, with its profile as the main
  view; in standard the assessed comparison sits in "what the evidence base holds". The closing
  section carries the **"questions to put to the department"** (ruling 39 bounds them). Export =
  the same complete report and attachments as the explore branch (ruling 32); the sense-check
  bundle is its front, not a smaller record.
- ✅ The user can widen at any point (add a neighbour, assess it, switch to exploring the space)
  within the same task. Sense-check is not scrutiny of a developed proposal (⏸ critical review).

## Output structure

- ✅ **The report** (ruling 32) — the Result artefact, a grounded block written as linear text in
  the Evidence search report's style with a side outline and collapsible sections carrying
  one-line takeaways. Sections: **top line** · **the problem and what is contested** · **the
  approaches** (a paragraph per theme: options in a sentence each, variants and packages,
  exclusions with their constraints) · **what the evidence base holds** (one verdict strip per
  option, each effect with its own comparator, population and period, with the comparison table as
  a working view (ruling 45); the kept-but-unassessed options by theme) · **transferability and
  assumptions** · **what needs deciding or commissioning next** (plus the questions to put to the
  department in the sense-check) · **what was searched and not searched**. **Written from the
  assessment, rewritten by a full run (ruling 50)**; before assessment the Result tab opens on the
  longlist and the Report view is marked as available after assessment; an on-demand report from
  the longlist is deferred. Baseline, Longlist (list · grid · shortlist views) and the profiles are
  working views behind it.
- ✅ **Baseline profile ("Do nothing")** (rulings 2, 24). Its own structure, different from an
  option's because the question is different: what is in place · trend if nothing changes · who
  is affected (where the target unit is checked against the data) · what is already changing ·
  **what is contested** (rival explanations of the problem; disagreements between sources) ·
  cost of inaction · key assumption · sources. Empirical premises sourced; the key assumption
  and what is contested are labelled reasoning (ruling 40); the tool does not forecast. In v1 the
  baseline searches Overton and OpenAlex only, and its coverage statement names live official
  statistics and departmental pages as not searched; the user may supply them as stated facts
  (ruling 43). The source-tier skew (grey literature) is visible. "Do nothing" is the
  reference wherever options appear — a sentence with a link on the longlist, an unremovable
  reference on the shortlist, and a band above the assessed table worded as **the situation
  these options would change**, never "compared against" (ruling 17; scoping does not perform
  the Green Book's shortlist comparison) — **never a grid row** (its cells would be n/a).
- ✅ **Longlist.** Options grouped by generated theme; each theme carries a one-line "what it
  does" mapped to its lever type; each option carries its name, a one-sentence description, the
  stated outcomes it is for, its relations (variant of · part of), and its state (on the
  shortlist · suggested · from your evidence search · added by you · excluded with the
  constraint · no in-scope evidence); its source-quality profile shows unknown-type and
  non-evidence documents as their own buckets (ruling 43). Two views: list (for judging each option) and grid
  (**primary lever type × ambition**, for judging the set; ambition is a per-option tag with a
  one-line justification, labelled "as described, not measured" and carried as a **tier-4
  reasoning claim** since no evidence has been read when it is assigned, ruling 20; owner
  2026-09-07). A click opens a
  light **option-before-assessment** page: what it is for · what the evidence base holds so far
  (the **source-quality profile**: mentioning documents by evidence type and quality tier,
  countries, populations, outcomes — never "how sure", ruling 33) · screens and guesses · where
  it came from.
- ✅ **Shortlist view.** Before assessment, the places with their reasons and the assess action;
  after, the same options with their assessed rows, which live in the report's "what the
  evidence base holds" section (ruling 32).
- ✅ **Assessed evidence = verdict strips in the report, a comparison table as a working view**
  (rulings 7, 45). The report carries one strip per option in its prose column; the longlist's
  shortlist view after assessment lays the same content out in six columns: Option (with its
  description) · How big, as reported · How sure · Where tried · Transferability · Key
  assumption. No study-design labels in the table ("15 studies", not "4 randomised"; owner
  2026-09-03, recorded in ruling 40). One provenance
  tag per row (*scoping pass* / *full run*). A variant's row shows only the variant's own
  evidence (ruling 15). The option name opens the profile; there is no second, expandable
  layer. "How sure" here means confidence in the specified design–outcome claim from relevant
  evidence, counting documents until independence is known (ruling 33). Sortable by evidence
  strength and document count only; direction tallies are per option within one outcome family
  and **not sortable across options** (ruling 17); cost cells compare only on matching bases;
  **no composite score, ever.**
- ✅ **Option profile** (concept § Option click-through; rulings 8, 13). Layered skim → sections
  → next steps. *At a glance*: what it is in two plain sentences · how big (as reported, native
  units) · how sure (evidence strength and study count) · where tried · transferability verdict
  with its cap reason · the key assumption to test first. Deliberately **not** in the strip:
  cost, mechanism prose, case-study detail. Sections, each collapsible with a one-line summary
  visible when collapsed ("At a glance" always open): How it works (mechanism and main failure
  mode, tier-labelled) · What it is made of (constituent interventions, each linking to its
  documents; for a variant, the parent's evidence appears here as *related evidence for a
  different design*, ruling 15) · Evidence for and against (tally line; strongest for /
  strongest against; common criticisms — balance of evidence, never the most supportive
  studies) · How it varies in
  practice (design variants observed across implementations) · Case studies (each with what they
  did, what happened, what made it work or not, and what to watch for; typed by source tier) ·
  Transferability working (the Factor | Evidence says | Your context | Basis table, with
  context entries typed retrieved · stated by you · planned by you; a retrieved fact at a
  containing geography fills a local factor only when the proposition applies at the target
  unit by its nature, otherwise it is context and the factor stays Unknown, ruling 34) ·
  Assumptions (load-bearing, strength, the key one) · What it would take (implementation
  requirements, reported costs, time to impact, distributional notes — provenance-carrying, no
  analysis). Next steps: run a full evidence search · start a theory of change (⏸ consumer) ·
  remove from shortlist. No export from the profile.
- ✅ **Case studies** come from three tiers typed by provenance: the academic corpus (especially
  observational and quasi-experimental implementation accounts), **Overton grey literature (the
  workhorse and the USP)**, and supplementary verified web links (gap-filler, lowest tier). A
  case study never silently raises an evidence-strength rating (concept § Case-study sourcing).
- ✅ **Sources tab = the Evidence search's Sources component** (ruling 46): By option · Landscape
  · All sources (· Findings when a deep search was inherited), the coverage header stating what
  was searched (documents retrieved and passed, inherited versus added (ruling 22), what was read
  at which depth (ruling 16), set aside under the evidence scope, not read under the cap, not
  searched), filter chips and the document table, plus scoping's statuses (*set aside: outside
  evidence scope* · *read in full* · *abstract only* · *not read under the cap*) and an Options
  column.
- ✅ **Density rule.** Never all layers at once; collapsed headers carry their takeaways; detail
  on demand. Applies to every scoping surface (concept § Option click-through).

## Product surface

Settled by the owner on the wireframes (rulings 1, 13; source
[README](../../sources/options-scoping/README.md)):

- ✅ **Navigation is the task's** (post-038 vocabulary, ruling 40): **Agent · Result · Sources ·
  Share · History**. The plan document and the planning chat live in the Agent tab. **Result is
  the report** (ruling 32), with **Baseline** and **Longlist** (list · grid · shortlist views) as
  working views reachable from it and from the run's progress. The chat is always the left
  column; the right column holds the current content and opens wide for the longlist, the grid
  and the profiles. ("Assessment" is a state the shortlist is in, not a place.) The grid view's
  rows are the fixed lever types (ruling 20). The boards were redrawn to rulings 15–44 on
  2026-09-07 and refined to rulings 45–50 on 2026-09-08; where a board and a ruling still differ,
  the ruling wins (source README).
- ✅ **The plan is presented exactly like the EB search plan**, in the Agent tab: the navy plan
  document beside the planning conversation, with Question · What we are trying to change · Settings · Constraints
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
  baseline** (before any option is generated; the pause is a place to question the baseline in
  chat) — the first gate.
- ✅ **"Assess these N"** — the second gate, the only point after the longlist where the user
  commits real time and money on options other than those they chose to keep.
- ✅ **Full evidence search** — per option, always the user's call.
- ✅ Everything else is iteration on living artefacts, not a gate: add or remove from the
  shortlist, exclude or include again, revise the plan (deltas), ask for a per-axis sort or a
  conditional recommendation.

## Evaluation (❓ shapes the build order)

Open question 1 of the concept, to be sketched before committing the longlist and assessment
contracts:
- ✅ **Primary measure: four behavioural tests on live asks** (ruling 27) — did a materially
  different option or a decisive question enter the team's next piece of advice; did the author
  and the receiving senior correctly read what was supported, inferred and unassessed; did
  source inspection sustain the exact claims used, including any variant and comparator; did the
  official return for the next revision without operator help. The live set includes an
  evidence-dense question, thin-evidence structural questions, at least one official new to the
  domain, and at least one continuation from an Evidence search. A newcomer's inclusion is not a
  success criterion: the test is whether they recognise an omission or an unsupported transfer
  after the baseline (ruling 42). User-requested sorts (guesses, tiers) are evaluated for what
  they discourage from assessment, not only for guess accuracy.
- **Option recall** against longlists in historical business cases and impact assessments — a
  floor, not a target, since those longlists are documented as narrow; expert-built reference
  longlists are needed too.
- A **domain-diverse question set seeded from the real V2 query log** (246 records, 208 distinct
  titles — dedupe first; categories are descriptions, not validated jobs): refineries,
  insolvency, regional disparities, R&D talent, digital infrastructure, waste management,
  university finances, small boats, industrial energy prices.
- **Screening-reason quality**; **transferability-judgment calibration** (the transferability
  cell is a first-class eval axis); **effect-cell fidelity** against the studies;
  **guess-versus-evidence agreement** for the reasoned guesses (ruling 12).
- ✅ **Feasibility checks before any contract, in order** (ruling 42, which calls them spikes): 1 advice and commissioning on live asks ·
  2 evidence attribution and confidence · 3 option-grain construction and selection stability ·
  4 local-condition adjudication · 5 balanced reading within a real budget · 6 a
  specification-level contract trace of one inherited question and one edited variant. Each names
  the question it answers and the result that would change the design (`pass3-answer.md` § 5 in
  the review pack).
- ✅ This spec carries **no build-order guidance** (ruling 28): slicing into tasks is a
  contract-time decision and the initial build is expected to be several tasks. A check order is
  not a build order.

## Open decisions and deferred seams

❓ Open (carried from concept § Open questions, updated by the rulings): 2 mini-search cost
envelope and the light-extraction-plus-reading shape to check (reading rule settled, ruling 16;
read-set discipline stated, ruling 38; study-independence detection open) · 3 rapid latency budget · 4 option-minting mechanics · 5 taxonomy storage (curated asset 🟡 vs prompt-internal)
· 6 baseline generation and grey-literature sourcing · 7 iteration mechanics and versioning ·
8 the entry point from the product's front door (the rest of the product surface is settled) ·
9 magnitude banding (requires its own eval before any band reaches users) · 10 the similarity
measure behind "most similar neighbours" in the standard sense-check (settle when that task is
contracted).

⏸ Deferred: deep mode · the applicability capability · critical review · the Theory-of-Change
session · collaborative rating · org-level memory · meta-analysis across several corpora ·
"Assess all kept options" (ruling 19) · an orientation / domain-primer capability (ruling 24).
Considered and rejected (ruling 29): a primary-author / senior-reader hierarchy; an
argument-only transferability cell; removing the do-nothing band; assessing every kept option
by default; evidence restrictions as plan Settings.
