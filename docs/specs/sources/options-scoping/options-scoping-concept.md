---
type: Source
title: "Options Scoping Capability: Concept"
description: Canonical options-scoping capability intent and the owner's rulings (concept phase 2026-09-01/02 + wireframe round 2026-09-03); the doc the scoping specs distil from.
tags: [source, options-scoping, capability, canonical]
timestamp: 2026-09-03
---

# Policy Atlas v3 — Options Scoping Capability: Concept

> **Status:** frozen origin ([ADR 0002](../../../adr/0002-spec-governance.md)) as of 2026-09-04.
> Concept agreed with owner 2026-09-01; wireframe-round rulings appended 2026-09-03 (last
> section). The declarative spec distilled from it lives in
> [../../capabilities/options-scoping/](../../capabilities/options-scoping/capability.md); change
> the spec, not this file. Task contracts (035 onward) consume the spec.
>
> **Inputs:** research readout ["How Governments Choose"](https://claude.ai/code/artifact/e43e34ef-110c-4395-b1c4-6bb90ebe856e)
> (Green Book / international appraisal practice / evidence toolkits / prior-art tools);
> user research synthesis (Job 1, Google Doc `1zKlIfxScpsZ5IdFXmh5qAh9xkM0_Lm6yXwLhosVl1S0`);
> workshop Figma frames; prototypes — `nestauk/dt_policy_atlas` branch `wip-prototype`
> (illustrative UX only) and `beingkk/stakeholder_atlas` (ToC machinery worth borrowing).

## Intent

- **Outcome:** a user asks a policy question and gets a structured, transparently screened
  set of intervention options — each with mechanism, evidence strength, transferability,
  and real-world case studies — as an editable first version, not a finished document.
- **User:** policy officials scoping options early (departmental longlist work) and central
  teams sense-checking an emerging idea (No. 10 job). Broaden the option set beyond
  familiar approaches; cure parochialism with international evidence.
- **Why "scoping", not "appraisal":** this capability alone cannot carry appraisal depth.
  Full appraisal is a future combination of many capabilities.
- **Success:** good outputs across varied policy domains. Generalisation is a v1
  requirement, not a nice-to-have.
- **Where it strikes:** the early longlist moment — where real appraisals fail (NAO:
  narrow option sets, missing counterfactuals, post-hoc justification).

## Shape

**Interaction model (owner ruling 2026-09-01): conversation-first.** The user works
alongside the chat/agent to do the research, produce the longlist, and whittle to the
shortlist. The dialogue is the spine of the capability; longlists, grids, and shortlist
views are living artifacts the conversation produces, references, and updates — never a
workspace with a chat widget attached. Steps 1–6 below describe the pipeline the
dialogue drives.

**Vocabulary (owner 2026-09-02):** the higher level — what round-1 called lever
families — is **Themes**; the lower, actionable level is **Options**. This aligns with
existing product vocabulary (Sources → Themes subview; EB theme-grouping machinery).
Hierarchy: Theme → Option → constituent interventions/evidence. "Lever family" appears
nowhere user-facing.

1. **Problem definition** — scaffolded chat fills the frame: action, domain/problem,
   **target unit** (who or what should change: people, firms, places, organisations,
   systems — PICO's "population" is the special case, not the schema; ruled 2026-09-01
   after the V2 query log showed targets like regions, industries, and government
   machinery), geographic scope, desired outcomes. The scaffold also branches on the two
   scoping-shaped intents: *explore the option space* vs *sense-check one named option*
   (the latter is the same pipeline seeded with a working set of one, plus "what sits
   next to it"). Non-linear: users revise the frame after seeing evidence, and re-runs
   apply deltas, not restarts.
2. **Option generation** — two directions into one funnel:
   - *Bottom-up:* evidence-base interventions cluster into **options** (an option is an
     actionable aggregate of related interventions; drill-down shows the constituents).
   - *Top-down:* LLM/taxonomy suggestions, plus user and ministerial additions. All
     suggestions enter the same funnel and get the same treatment (fait-accompli fix).
3. **Screening and shortlist assembly** (whittling mechanism ruled 2026-09-01;
   vocabulary note: user-facing language is Green Book language — longlist/shortlist,
   never invented terms) — three
   layers, LLM judgments in all of them, but only ever checkable and overridable:
   - *Hard screens:* user-added session constraints ("no new fiscal levers", "G7 only",
     "low-cost" via reported cost bands) plus the default set (relevance to stated
     outcomes, distinctness, within stated scope). Every drop cites the specific
     constraint it violated. The V2 query log shows users already state such constraints
     unprompted. Thin evidence never drops an option — it flags it
     (structural-intervention bias stays out of the screen).
   - *Structure, don't judge:* survivors placed on the grid they implicitly live on —
     lever family × ambition level. Descriptive only.
   - *Shortlist assembly:* the proposed ~5-option shortlist is a **representative
     coverage of the decision space, not a top-5** (the Green Book shortlist is itself
     a coverage set: BAU, do-minimum, preferred, more/less ambitious). Shortlist places
     cover surviving families and span the ambition range; within a family the
     representative is picked on a **single named axis stated in that place's reason**
     ("strongest evidence in the regulatory family"; "only structural option, included
     despite thin evidence"). Never a fused cross-list score.
   - *User iteration on top:* pin, swap a family's representative, add places, promote
     from the rejected list. Rejections are kept with reasons.
   - *"Most promising" is served honestly:* per-axis sorts (most evidenced, largest
     reported effects, best context fit) and **conditional recommendations** ("if your
     priority is X, A and B lead; if Y, C is the only candidate but evidence is thin").
     Fused top-5 orderings are permanently out — weights are a political question.
4. **Assessment grid** — per option, each cell sourced:
   mechanism (one-line theory of change + main failure mode) · evidence strength and
   effect direction/magnitude (EB appraisal components, shallow "mini evidence search"
   per option; see "Effect cell" below) ·
   transferability (light judgment against the stated context, working shown:
   evidence-reported moderators next to the user's stated frame) · case studies ·
   assumptions register (load-bearing flag, strength, one starred "test it first") ·
   an explicit business-as-usual row. Reported costs, reported implementation
   requirements, and reported distributional effects ride along as retrieval facts with
   provenance. Sortable by any single axis. **Never a fused ranking or composite score.**
5. **Deep-dive ramp** — any option can be sent into a full evidence-base run ending in an
   **option-profile synthesis** (grid-aligned template; doubles as a Green Book-style
   per-option annex). The grid cell then shows upgraded provenance: scoping pass vs
   full run.
6. **Output** — an editable "great first version" (option table + top-line brief). States
   what was searched; claims breadth, never exhaustiveness. Workspace retains searches,
   judgments, and rejections as institutional memory.

## Modes

Rapid / standard / deep, mirroring EB modes. **V1 = standard + rapid.** Deep (per-option
stress-testing, mechanism-analogy search) comes later. Modes differ in breadth and depth
of grounding and latency, mapped to the two jobs (rapid = sense-check; standard =
longlist).

## Trust principle

**Generation is free; interpretation is labelled; assessment is grounded.**

- *Generation:* suggesting an option needs no source — it is a labelled hypothesis.
- *Interpretation* (ruled 2026-09-01): mechanism sentences and assumptions reuse the
  EB's existing claim-type/grounding-tier machinery rather than a new scheme — tier_2/3
  inferences where the literature supports them; capped, visibly-labelled `reasoning`
  claims (tier_4, "must not smuggle findings") where they are the model's own analysis
  (`synthesis_backend.py` CLAIM_TYPES, `grounding_judge.py` tiers). The deep-dive ramp
  is what upgrades interpretive claims toward cited tiers.
- *Assessment:* anything asserted about an option (evidence strength, effect,
  transferability, case studies, costs) requires retrieval — tier_1–3 only. Unassessed
  cells are honest empty states ("not yet searched" / "no credible evidence found"),
  never hedged guesses.

The transferability cell is the one opinionated cell in the grid and must show its
working; it is a first-class eval axis.

## Effect cell: report, don't compute (owner ruling 2026-09-01)

V2's 1.0–5.0 "impact score" is the anti-pattern: a composite of LLM categorical
judgments, similarity weights, and dampening factors — with undefined magnitude buckets
at Tier 1, unknown treated as a small positive effect, string-heuristic scale detection,
maximum-not-average aggregation, two competing formulas, and extracted uncertainty that
never entered the score (autopsy: V2 `analysis/scoring.py`,
`synthesis/nodes/impact_synthesis.py`). The no-composite rule extends to cells, not just
rankings. 035's effect cell instead reports:

- **Direction** by transparent vote-count of quality-screened studies ("9 of 11 found
  reductions") with a discord flag when evidence genuinely conflicts.
- **Magnitude** quoted in native units with citations ("10–25% reduction across 3
  RCTs"), never converted across measure families, never pooled across contexts.
- **Scannability** via the source's own characterisation, quoted with provenance ("a
  small but robust effect" — the field calibrates itself). No analytical banding in v1:
  fixed cutoffs do not generalise across domains, and per-run LLM thresholds were V2's
  instability. Candidate future approaches (both need eval): literature-anchored
  benchmarks cited per field; session-calibrated thresholds persisted, shown with
  rationale, failing loudly.
- Sortable by direction consensus or evidence strength; there is no impact scalar.

**Salvage from V2:** the attribution/contribution/correlation causality taxonomy (with
its prompt definitions), contested-verdict/discord detection, the structured
profile-not-scalar framing of `docs/backend/impact_assessment.md`, result-grain
extraction separating outcome from stratum (V3's 020 `effect_basis` at finding grain is
the better successor foundation), and full per-cell audit trails.

## Transferability cell: fold-in from V2's forecast (2026-09-01)

V2 had three mechanisms called "transferability". The two scoring ones (document-level
numeric fit, intervention "Context Fit" rating) repeat the impact-score anti-pattern —
ordinal LLM labels averaged into floats, inconsistent unknown/mismatch semantics, two
dampening exponents, four label scales, silent fallbacks, no provenance, and a UK
constant silently overwriting the geography the wizard collected. None of that folds in;
nothing in 035 dampens or scores fit numerically.

The third — the **transferability forecast chat mode** — is the keeper, and supplies the
light-judgment cell's machinery:

- **Three-legs argument structure** (Cartwright): worked somewhere / same causal role /
  support factors present; any weak leg collapses the argument.
- **Moderator/dealbreaker extraction** with verbatim quotes and evidence-basis tags
  (empirical / author_hypothesis / theory_background) — the "show your working" evidence
  side, already schematized (V2 `chatbot/extraction_models.py`).
- **Default-to-Unknown context discipline**: the Factor | Your context | Basis table
  where only user-stated facts count; 035 populates "your context" from the
  problem-definition frame and never infers it.
- **Ceiling rules**: deterministic caps on opinion strength (verdict capped at
  "conditional" when mechanism confidence is weak or most factors unknown) — the
  calibrated-language mechanism for the grid's one opinionated cell.
- Geography/population/setting dimension taxonomy, honest coverage denominators
  ("3 of 5 documents"), anti-overreach hedges, and the stance: arguments and evidence,
  not verdicts.

**Stays with the future applicability capability:** the interactive factor-resolution
loop, constraint-tolerance/local-resource analysis (cost/staffing/complexity), 
jurisdiction and political machinery, any numeric fit score. (V2's own V3 architecture
doc already scoped transferability as a post-options analysis capability — the seam has
precedent.)

## Option click-through (profile) — content spec (owner-refined 2026-09-02)

Layered: **skim → annex → springboard.**

1. **Verdict strip** (reads in 30 seconds): what the option is, in two plain sentences ·
   three-dial line — how big (effect as reported, native units) / how sure (evidence
   strength + study count) / where tried (jurisdictions) · transferability verdict with
   its cap reason · the one starred pivotal assumption ("test first"). Deliberately NOT
   in the strip: cost (a reported fact, not a dial), mechanism prose, case-study detail.
2. **Annex body**: how it works + main failure mode (tier-labelled) · **what it's made
   of** — the constituent interventions the option aggregates, each linking to its
   documents (the Theme → Option → evidence drill-down made real) · the evidence as
   reported **beside the counter-case** (strongest evidence against + common criticisms
   — balance of evidence, never the most supportive studies) · **how it varies in
   practice** — design variants observed across implementations (scope, intensity,
   enforcement) · case studies typed by source tier · transferability working table ·
   assumptions register (load-bearing, strength, test-first star) · **what it would
   take** — one consolidated reported-facts block (implementation requirements, costs,
   time-to-impact, distributional notes; provenance-carrying, no analysis).
3. **Springboard**: run a deep evidence dive (upgrades provenance, mints the citable
   option profile) · start a Theory of Change session · swap/promote on the shortlist ·
   export the annex.

**Density rule (owner 2026-09-02):** never show all layers at once. Progressive
disclosure everywhere: the annex renders as collapsed sections whose headers carry
their one-line takeaways — the collapsed page IS the summary; detail exists on demand.
Applies to every scoping surface, not just the profile.

## Case-study sourcing (three tiers, typed by provenance)

1. Academic corpus, especially observational/quasi-experimental studies — implementation
   accounts with measured outcomes, already EB-appraised.
2. **Overton grey literature** — the workhorse and the USP; validatable provenance.
3. Supplementary web search — gap-filler, verified links, lowest tier. A case study never
   silently inflates an evidence-strength rating.

## Architecture stance

Scoping reuses EB components (retrieval, appraisal, synthesis profiles) in **its own
pipeline** — it never orchestrates full EB runs per option. It may optionally read
existing EB corpuses (bracketed: meta-analysis territory, possibly its own capability).
Borrow from `stakeholder_atlas` ToC prototype: assumption schema (load-bearing,
strength), failure pathways, link verification. A shortlisted option seeds a ToC session
(dotted-line consumer; separate capability).

## Boundaries with neighbouring capabilities (ruled 2026-09-01)

- **Cross-capability triage is the product shell's job, not 035's.** Recognising that a
  query is fact-finding, stakeholder mapping, or an EB question belongs to Policy
  Atlas's front door (open question 8). 035 assumes it receives scoping-shaped
  questions and defines only the internal branch (explore space vs sense-check one
  option).
- **Critical review = separate future capability.** Input-type boundary: a *question or
  idea in a sentence* → scoping; an *existing artifact* (draft proposal, submission,
  business case) → critical review (adversarial audit: evidence coverage, stated
  assumptions, citation fidelity). Shared components by design: assumptions-register
  vocabulary, evidence-coverage machinery, three-legs transferability, the ToC
  prototype's critic pass. They compose: critical review can audit a scoping output.

## Out of scope (v1)

Costing/value-for-money **analysis** (owner ruling: LLM reliability is not there for
government decision-grade numbers; reported costs with provenance are fine) · political
viability and political appetite in any form · jurisdiction-specific "will it work for
you" assessment (future applicability capability) · full baseline analysis · equality
impact assessment (reported distributional effects only) · composite scores/rankings ·
collaborative rating (v1 single-user; data model anticipates multiple raters) ·
org-level institutional memory (v1 workspace-level) · visual ToC editor · deep mode ·
meta-analysis over EB corpuses · meeting-speed latency.

## Open questions for the contract stage

1. **Evals and ground truth** — option recall against longlists in historical business
   cases/impact assessments (caveat: those longlists are documented-as-narrow, so
   recall against them is a floor, not a target — expert-built reference longlists
   needed too); a domain-diverse question set **seeded from the real V2 query log's
   non-health entries** (refineries, insolvency, regional disparities, R&D talent,
   digital infrastructure, waste management, university finances, small boats);
   transferability-judgment calibration; screening-reason quality. Shapes build order;
   sketch before committing.
2. **Mini evidence search spec** — which EB components at what depth, and the cost
   envelope (a standard run ≈ N options × one mini search; per-run price target
   constrains N and depth).
3. **Rapid-mode latency budget** — a number, and how much grounding fits inside it.
4. **Option minting mechanics** — clustering, overlap/dedup, target longlist size.
5. **Taxonomy source** — curated asset vs prompt-internal (Green Book solution dimension
   + international option types: regulate, stringency variants, market mechanism,
   inform, subsidise, enforce existing, devolve, do minimum — **plus an
   organisational/delivery branch**: guidance, funding conditions, shared frameworks,
   workforce, data-sharing; ruled in 2026-09-01 after the V2 query log's
   government-machinery cluster, e.g. "support local authorities to implement national
   strategy").
6. **BAU row generation** — current-landscape content; couples to web/grey-lit sourcing.
7. **Iteration mechanics** — delta re-run granularity; working-set versioning.
8. **Product surface** — entry point vs existing search flow; scaffolding chat as shared
   component; export formats.
9. **Magnitude banding** — whether analytical banding earns its place after v1, and
   which approach (literature-anchored vs session-calibrated; see "Effect cell").
   Requires its own eval before any band reaches users.

## Wireframe-round rulings (owner, 2026-09-03)

Made while iterating the wireframes ([editable canvas](https://claude.ai/code/artifact/bdaa69e7-9f8e-4bf2-a7fa-7bb6895b4191),
[read-only copy](https://claude.ai/code/artifact/2e4d03c0-5d32-4e33-a32f-59adc6835bc0), and the
frozen copy [options-scoping-wireframes.html](options-scoping-wireframes.html) with its readable
boards in [boards/](boards/);
sample question: reducing the number of 16 to 24 year olds who are NEET). The contract must
consume these alongside the sections above; where they sharpen an earlier ruling, they win.

1. **Shell.** The scoping task uses the evidence-base task's navigation: the lifecycle tabs
   **Plan · Results · Sources · Share · History**, with Results split into subtabs
   **Baseline · Longlist · Shortlist** (the longlist has List and Grid views; Sources holds
   "what was searched", all sources, and sources by option). The chat
   is always the left column under the tabs; the right column holds the current tab's
   content, opening wide for the longlist, the grid and the profiles. (This replaces the
   earlier "working copy" rail of collapsible sections.) The **frame is the scoping plan** and is presented exactly like the
   evidence-base search plan: the navy plan document beside the planning conversation, with
   Question · What we are trying to change · Settings (who or what should change, where,
   outcomes, depth) · Constraints (with when each is checked) · Plan steps · Check-ins, an
   Edit action per section, and a single start action. "Plan", never "frame", in the product. The longlist has a **list view** (by theme, for judging each option)
   a **grid view** (theme × ambition, for judging the set), and a **shortlist view** (only
   the options on the shortlist, each with its reason, and the assess action); the
   **shortlist is a state on longlist options**, shown outlined in the list and grid views,
   not a separate section. Grid and shortlist views are separate screens, not stacked. Collapsed headers carry a one-line takeaway (the closed
   rail is the summary); one section opens at a time; the longlist, the grid and the
   profiles open wide on the right. "Chat", never "thread".
2. **Baseline stage, and it pauses.** Confirming the plan builds the baseline only. The
   run stops; the user reads the baseline, changes the plan if needed, and confirms it
   before any option is generated. The baseline is a **profile of "Do nothing"** with its
   own structure: what is in place · trend if nothing changes · who is affected (where the
   target unit is checked against the data) · what is already changing · cost of inaction ·
   key assumption · sources. Reported facts only; the tool does not forecast; the source
   tier skew (official statistics, grey literature) is visible. "Do nothing" (not BAU) is a
   reference line above the longlist, an unremovable reference row on the shortlist, and a
   reference band above the assessment grid; never a grid row (its cells would be n/a).
3. **Three depths, one gate.**
   - *Longlist:* retrieval, then the evidence base's title-and-abstract consensus screen
     once at the frame level (suggested and user-added options get their own small
     retrieval and the same screen), then clustering. Each option carries cheap metadata
     only: study count, source type, countries, populations, outcomes measured.
   - *Assessment:* the mini evidence search, **shortlist only, user-triggered** ("Assess
     these N", with a time estimate; PA proposes a shortlist, then waits). Fills the verdict
     strip and profile. Cells are labelled "scoping pass".
   - *Full evidence search:* the complete evidence-base pipeline for one option (ruling 9).
   - **No full-text screening in scoping**; stage-2 confirmation belongs to the full
     evidence search and is one of the things the "full run" label buys.
   - Whether assessment cells come from per-document extraction or from retrieval-augmented
     reading over the option's documents is an **implementation decision, left open**
     (folds into open question 2).
4. **Screening is a pipeline stage, not a user step.** Screens run on the longlist
   metadata as options complete; there is no screening board. An option that fails a screen
   is **excluded** (never "set aside" or "dropped" in the product): it **stays in its
   theme**, greyed and sorted last, showing the constraint it broke, with an **Include
   again** action; the user can **Exclude** any option with a reason of their own; theme
   headers count included and excluded; a "show excluded only" filter covers the
   what-did-we-drop view; the chat gives one summary beat.
5. **One shortlist action, plain words.** **Add to shortlist** is available from the
   moment an option exists (longlist row, option page, or the grid), and **Remove from
   shortlist** reverses it. There is no separate "pin" or "choose": both were "I want this
   on the shortlist". An option the user added keeps its place through re-runs; screens
   still run on it and their finding shows on it ("on the shortlist · breaks: X"); the
   grid marks each filled place as **proposed by Policy Atlas** or **added by you**;
   assessment is unaffected.
6. **Shortlist assembly is separate from screening.** The theme × ambition grid is the
   instrument (ambition kept, descriptive). A place is filled in one of two ways:
   proposed by PA with its reason, or added by you. When the user adds, PA advises on
   coverage gaps and never removes. Pre-assessment reasons are limited to what
   metadata knows ("most studies in theme", "widest implementation record", "only option in
   theme", "thin evidence"); "strongest evidence" and "largest reported effects" arrive with
   the assessment as sorts.
7. **Assessment grid = verdict strips stacked.** Six columns: Option (with its one-sentence
   "what it is") · How big, as reported · How sure · Where tried · Transferability · Key
   assumption (no star glyphs). A row expands to mechanism, the sources' own words, case
   studies and reported cost. Provenance is one tag per row. The full grid is the export.
8. **Option profile.** Vocabulary: "option profile", never "annex"; export is a Share
   action (ruling 14), not a profile action.
   Sections: How it works · What it is made of · Evidence for and against (tally line,
   strongest-for / strongest-against columns, common criticisms) · How it varies in practice ·
   Case studies (each with what they did, what happened, what made it work or not, watch for;
   typed by tier) · Transferability working · Assumptions · What it would take. Actions:
   Run a full evidence search · Start a theory of change · Swap on shortlist. Every option
   carries its one-sentence description on the longlist, shortlist and grid.
9. **A full evidence search mints its own evidence-base task** (Plan · Results · Sources ·
   Share · History), seeded from the option, synthesis template = the profile sections,
   listed under the parent scoping task and linked both ways, sharing its project and
   visibility. The scoping profile then **reads its cells from that report** ("full run"),
   keeps the scoping-pass version in History, and keeps the user's context with scoping (so a
   transferability cap set by unstated context survives the full run).
10. **Sample constraints in design artefacts use plain words** ("No benefit cuts or
    sanctions", "OECD evidence only") so the screening logic can be checked by eye.
11. **Option taxonomy = fixed lever types, generated themes.** The taxonomy is a small,
    curated, versioned list (about ten) of domain-agnostic *lever types* — how government
    can act: regulate, subsidise, tax or charge, inform, provide a service, enforce existing
    powers, devolve, change who runs the system (the organisational branch) — used to
    prompt top-down suggestions and to check longlist coverage ("no market-mechanism
    option; want one?"). *Themes* are generated per problem from the clusters, named in the
    problem's own words, each mapped to the lever type(s) it draws on. Never a fixed theme
    list. Completeness of the lever list across machinery-of-government questions is an
    eval concern, not a reason to make it dynamic.
12. **Two kinds of constraint, and reasoned guesses for the second.** Scope-shaped
    constraints (geography, target group, sector, lever type, "no X" about the option
    itself) are **checked at the longlist** on metadata and the option description.
    Effect-shaped and cost-shaped constraints ("low cost", "at least moderate evidence")
    are **checked after assessment**; the frame says so. Until then Policy Atlas gives each
    option a **reasoned guess** per such constraint — a labelled, capped reasoning claim
    ("cost: likely low · guess, not evidence") shown as a flag and a sortable facet, never a
    screen, never a drop — so shortlisting and conditional recommendations can use it
    honestly. After assessment the guess is replaced by the reported fact with provenance
    and any disagreement is shown side by side ("guessed low; reported £6,500 per
    placement"). Guess-versus-evidence agreement is an **eval axis**.

13. **Design language follows the Evidence Base capability.** One body size throughout
    (the EB report body size), grey for secondary text, small uppercase labels only where
    necessary (e.g. "Contents"), as few chips and colours as possible (blue for links, the
    primary action and pins; states written as words), no small text, no jargon. Outputs —
    the "Do nothing" baseline and the option profile — read as **linear text** in the manner
    of a GOV.UK page: title, an at-a-glance list, a contents list, headed prose sections,
    sources in brackets. Not dashboards. The contents list is a side outline and each
    section is collapsible with a one-line summary visible when collapsed, exactly as the
    evidence-base report does it ("At a glance" always open). The assessment table has no
    second, expandable layer: the option name opens the profile. **Working lists stay
    clickable lists**, not documents: the longlist keeps the report typography (title, intro
    sentence, themes as collapsible headings with one-line summaries) but has no contents
    sidebar, and each option is a selectable row — name as a link, one-sentence description,
    one grey line for the outcomes it is for and its state — with its actions as line icons
    on the right (circled plus = add to shortlist, circled minus = remove, circled cross =
    exclude, undo arrow = include again; the words stay as tooltips). A click opens a light
    "option before assessment" page (what it is for · what the evidence base holds so far ·
    screens and guesses · where it came from). The grid view carries the assess action; the
    Shortlist subtab lists the places with their reasons before assessment.

14. **No brief tab; the shortlist is one tab at two stages.** The shortlist subtab shows the
    places with their reasons and the assess action before assessment, and the assessed table
    for the same options after it, with a short **summary** above the table (Policy Atlas's
    reading of the shortlist against doing nothing; never a ranking). "Assessment" is a state
    the shortlist is in, not a place in the navigation. The "editable first version" of the
    Shape section is delivered by **Export** (a Share concern, as for the evidence-base task),
    which bundles the summary, the assessed table, the option profiles, the baseline and the
    Sources statement of what was searched. Free-text editing of the summary is out of v1
    scope (owner, 2026-09-03).

Open question 8 (product surface) is largely answered by rulings 1, 2 and 9; the remaining
part is the entry point from the product's front door.
