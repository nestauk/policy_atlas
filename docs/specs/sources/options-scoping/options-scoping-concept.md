---
type: Source
title: "Options Scoping Capability: Concept"
description: Canonical options-scoping capability intent and the owner's rulings (concept phase 2026-09-01/02 + wireframe round 2026-09-03); the doc the scoping specs distil from.
tags: [source, options-scoping, capability, canonical]
timestamp: 2026-09-03
---

# Policy Atlas v3 — Options Scoping Capability: Concept

> **Status:** frozen origin ([ADR 0002](../../../adr/0002-spec-governance.md)) as of 2026-09-04,
> reopened in PR #63 for the review round. Concept agreed with owner 2026-09-01; wireframe-round
> rulings appended 2026-09-03; **review-round rulings appended 2026-09-07** (last section, which
> wins over everything above it where they differ). The declarative spec distilled from it lives in
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
- **User:** analysts and policy officials building the options case early (departmental
  longlist work) and senior officials and decision makers choosing between options or
  sense-checking an emerging idea (No. 10 job). The two jobs carry equal weight (owner,
  2026-09-07; a primary-author / senior-reader hierarchy was considered and rejected).
  Users differ independently of role in how well they know the domain and in whether they
  have already run an Evidence search on it (ruling 22, 24). Broaden the option set beyond
  familiar approaches; cure parochialism with international evidence.
- **Why "scoping", not "appraisal":** this capability alone cannot carry appraisal depth.
  Full appraisal is a future combination of many capabilities.
- **Success:** good outputs across varied policy domains. Generalisation is a v1
  requirement, not a nice-to-have.
- **Where it strikes:** the early longlist moment — where real appraisals fail (NAO:
  narrow option sets, missing counterfactuals, post-hoc justification).
- **No composite scores or rankings** is a **product boundary**, justified by what
  single-number ranking does to incentives (Green Book Review 2020) and by the trust
  principle below. It is not a Treasury prohibition: the Green Book 2026 *recommends* the
  options framework filter rather than mandating it and permits facilitated multi-criteria
  analysis at longlist stage (corrected 2026-09-07 after the review round checked the source).

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
pipeline** — it never orchestrates full EB runs per option. A scoping task may **start
from an existing Evidence search task** and reuse its question, documents and report as
inputs (ruling 22; un-bracketed 2026-09-07). Meta-analysis across several corpora remains
deferred territory, possibly its own capability.
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
meta-analysis over EB corpuses · meeting-speed latency · **"Assess all kept options"** (a
whole-longlist assessment action; deferred 2026-09-07 on inference cost, revisit after live
runs) · an **orientation / domain-primer capability** for users new to a domain (deferred
2026-09-07 as a likely separate future capability; see `docs/deferred.md`).

## Open questions for the contract stage

1. **Evals and ground truth** — option recall against longlists in historical business
   cases/impact assessments (caveat: those longlists are documented-as-narrow, so
   recall against them is a floor, not a target — expert-built reference longlists
   needed too); a domain-diverse question set **seeded from the real V2 query log's
   non-health entries** (refineries, insolvency, regional disparities, R&D talent,
   digital infrastructure, waste management, university finances, small boats);
   transferability-judgment calibration; screening-reason quality. Shapes build order;
   sketch before committing. **Updated 2026-09-07 (ruling 27):** the primary measure is
   four behavioural tests on live asks; recall against historical longlists is a floor.
   The V2 query log has 246 records but 208 distinct titles — dedupe before use, and treat
   its categories as descriptions, not validated jobs.
2. **Mini evidence search spec** — which EB components at what depth, and the cost
   envelope (a standard run ≈ N options × one mini search; per-run price target
   constrains N and depth). **Partly resolved 2026-09-07 (ruling 16):** the mini search
   reads the full text of the documents it relies on, capped per option. **Shape to spike
   (owner, 2026-09-07):** a light per-document extraction (small field set) in parallel for the
   countable cells, retrieval-augmented reading for the narrative sections; extraction is slower
   than reading, so the document cap is the latency lever and the spike measures fit to the
   rapid budget. Open: how "one vote per independent study" detects several papers on one
   trial.
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
10. **Similarity measure** (added 2026-09-07, ruling 25) — what "most similar neighbours"
    means for the standard sense-check's comparison set (embedding distance over descriptions,
    same lever type and outcome, or agent judgement). Settle when that task is contracted.

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

## Review-round rulings (owner, 2026-09-07)

Made after a two-pass adversarial product review of this concept and the wireframes (blind
proposal first, then comparison; review pack and both answers in
`docs/research-and-development/options-scoping-review/`, gitignored; the ruled decision sheet is
`decision-sheet.md` there). These rulings win over every earlier section, including the
wireframe-round rulings, where they differ. Boards 4, 5, 5b, 6, 6b and 8 need redrawing to match;
until then the rulings win over the boards.

15. **Option relations: variant of, part of.** An option has a *specified design*: the
    features that define it (for a youth guarantee: the offer, the deadline, the obligation).
    When the user modifies an option's design ("assess it without sanctions"), the
    modification becomes **its own option**, added by you, linked **variant of** its parent,
    and it gets its own mini search with the variant as the intent. The parent's evidence
    appears in the variant's profile only as *related evidence for a different design*; it
    never appears in the variant's assessed row or in the summary. A variant with no
    matching implementations shows honest empty cells. Options can also be linked **part
    of** (a package and its ingredients). Related options are shown together on the
    longlist, and the shortlist proposal never fills two places with a package and its own
    ingredient without saying so. Screens and constraint checks apply to the specified
    design, so "most implementations attach a sanction" is a fact about the parent, not a
    finding against the sanction-free variant.
16. **Claim depth follows reading depth.** Screening stays title-and-abstract (ruling 3).
    The **mini evidence search reads the full text of the documents it relies on**, capped
    per option (the cost lever is depth, not coverage). Every claim carries the depth of
    what was read — abstract or full text — and a section may not assert what the read
    material does not support. Abstracts are quotable anywhere in a profile, as Evidence
    search reports already do; a document with no obtainable full text supports
    abstract-level claims and is labelled as such. "Scoping pass" therefore means: screened
    on titles and abstracts, full text read for the documents cited, document set not
    confirmed. The Sources tab says exactly that (board 6b's "no full text searched" was
    wrong).
17. **The do-nothing band is the starting point, not a comparison.** Scoping never
    forecasts, so it never compares an option against the UK baseline; that is the Green
    Book's shortlist appraisal, which this capability does not perform. The band above the
    assessed table is reworded as *the situation these options would change*, never
    "compared against doing nothing"; its key assumption stays inside it, labelled as
    reasoning. **Summary rules:** no superlatives across options; each effect stated with its
    own comparator, population and period; conditional recommendations only on axes that
    are comparable across options — evidence strength, where tried, cost as reported —
    never magnitude or direction. Direction tallies are per option within one outcome
    family and are not sortable across options; the **direction-consensus sort is dropped**.
    Sorts: evidence strength, study count.
18. **Transferability: three context sources, the weakest leg decides.** The Factor |
    Evidence says | Your context | Basis table takes three kinds of context entry:
    **retrieved** (from the baseline or the assessment, cited, tagged with the geography it
    applies to; a fact at a containing geography counts unless a more local retrieved or stated
    fact contradicts it, and is shown with its level — owner 2026-09-07), **stated by you** (a
    fact about the present) and **planned by you** (a commitment). Only the first two can
    lift a cap; a commitment becomes a named condition of a conditional verdict
    ("Conditional on: local delivery funded"). The verdict word is set by the **weakest
    leg**; an unknown or absent dealbreaker caps the verdict on its own whatever the other
    factors say. **No factor fractions anywhere** ("4 of 5 present" is gone). Prior use
    somewhere satisfies one leg only. This replaces "only user-stated facts count" (too
    strict once the baseline has retrieved context) and the count-based ceiling rule.
19. **Assessment allocation is debiased; three depths stay.** Reasoned guesses (ruling 12)
    **never feed the shortlist proposal or any pre-assessment recommendation**; they are a
    flag and a sort the user asks for. Study count alone is never a place reason. "Thin
    evidence" is a reason to assess, never to skip. Conditional recommendations ("if your
    priority is X…") are made **only after assessment**; before it the agent describes coverage
    and gaps. The summary and the export list every kept option that was not assessed, by
    theme, so omissions are explicit. A whole-longlist
    "Assess all kept options" action is deferred (inference cost).
20. **Coverage is anchored on lever types; the grid is re-anchored; ambition is a tag.**
    The shortlist proposal fills **one place per fixed lever type present among the kept
    options** (ruling 11's curated list), each with its named axis; typically four to seven
    places, the user removes if over. Generated themes group the longlist and label the
    grid but **do not earn places**; a single-option theme gets no automatic place unless
    its lever type is otherwise uncovered (themes are generated and a singleton may be a
    clustering artefact). Every option has **one primary lever type** and may touch others;
    coverage counts the primary, and secondary types shape the gap message ("Regulate: no
    dedicated option; touched by the youth guarantee package") (owner, 2026-09-07). The grid
    view's **rows are primary lever types**. **Ambition** survives only as a per-option tag
    with a one-line justification, shown as the grid's columns, labelled "as described, not
    measured" and carried as a **tier-4 reasoning claim** (no evidence has been read when it is
    assigned); the proposal warns when every place shares one band (the all-incremental
    shortlist is the NAO failure). Board 5b's
    "Organisational has no place: both options thin" broke ruling 6 and is withdrawn.
21. **The handoff carries the whole record; resume from the analysis.** Export (ruling 14)
    additionally bundles the **full longlist with states and reasons** and the **shortlist
    assembly record** (each place, its reason, who filled it). The summary gains a fixed
    closing element, **"What needs deciding or commissioning next"**, generated from the
    unresolved differences, the unassessed options and the conditions verdicts rest on; the
    author's own steer is written outside Atlas (ruling 14's no-editing stands). Principle:
    the user **resumes from the current analysis, never by replaying the chat**; the
    conversation stays available throughout and remains the spine for steering.
22. **A scoping task may start from an Evidence search task** (a Link). Its question seeds
    the plan. Its screened documents enter the pool and are **re-screened against the
    scoping plan** (the old screen had a different intent). Its report's interventions and
    themes enter the longlist as suggestions labelled "from your evidence search" through the
    fait-accompli path, so nothing is trusted because it was found before. The run retrieves
    beyond the inherited set; the Sources tab states inherited versus added. Fallback if a
    contract must trim: question and documents only.
23. **Three kinds of constraint.** Ruling 12's two kinds gain a third: **evidence-scope**
    constraints ("OECD evidence only"), checked at retrieval and screening, which can
    **never exclude an option**; an option whose only example falls outside the evidence
    scope stays on the longlist marked "no in-scope evidence". When a user's sentence is
    ambiguous between evidence scope and option scope the agent asks ("only evidence from
    OECD countries, or only options tried in OECD countries?"). Screen findings that rest on
    the corpus are cited like any claim. (Board 4's exclusion of the cash-transfer option
    was wrong under this ruling.)
24. **The baseline gains "what is contested."** Its structure adds the rival explanations of
    the problem and the disagreements between sources. The pause after the baseline is
    explicitly a place to **question the baseline in chat** before confirming, and the copy
    says so. No orientation stage is added; the first live test includes at least one
    official new to the domain, and a separate orientation / domain-primer capability is
    noted as likely future work (`docs/deferred.md`).
25. **Sense-check is an entry branch; rapid and standard are depth settings.** Depth governs
    retrieval breadth and documents read per option, and applies to both branches; the two
    were previously conflated. **Rapid sense-check:** short plan (the agent infers problem,
    target unit, outcome and place from the named option, the user confirms); light baseline,
    still paused, one beat; neighbours generated at **metadata depth only**, as context
    (parent and variants, same lever type, lever types the idea does not touch); the proposal
    through the "Assess these N" gate is **the named option alone**; one mini search at
    rapid depth; the option's **profile is the primary surface**; one extra output element,
    **"questions to put to the department"**, generated like ruling 21's closing element;
    export = profile, neighbour list, questions. **Standard sense-check:** the same, but the
    proposal is the named option **plus its most similar neighbours**, pre-ticked, confirmed
    with one action; each assessed at standard depth; the assessed table sits under the
    profile as the comparison. The user can widen at any point (add a neighbour, assess it,
    or switch to exploring the space) within the same task. **The plan asks for depth every
    time, in both branches; no default.** Which user edits count as a design change that mints a
    variant (ruling 15) is the agent's judgement, stated, with no fixed rule. The similarity
    measure is open question 10. Board 8 is redrawn as the rapid version, honouring the pause.
26. **Effect-cell vote-count rules.** "Report, don't compute" still involves choices, so
    they are fixed: one vote per independent study; direction defined per outcome family;
    statistical significance never counted; disagreement shown as the discord flag. Banding
    stays open question 9.
27. **Evaluation frame.** The primary measure for open question 1 is four behavioural tests
    on live asks: did a materially different option or a decisive question enter the team's
    next piece of advice; did the author and the receiving senior correctly read what was
    supported, inferred and unassessed; did source inspection sustain the exact claims used,
    including any variant and comparator; did the official return for the next revision
    without operator help. Recall against historical longlists stays as a floor.
28. **Scope and slicing.** This concept and the spec describe the **whole capability**. They
    carry **no build-order guidance**; cutting it into tasks is a contract-time decision and
    the initial build is expected to be several tasks. The review's "smallest testable
    version" (`pass2-answer.md` §10) is an input to that decision, not a ruling.
29. **Considered and rejected.** A primary-author / senior-reader hierarchy (the two jobs
    keep equal weight); dropping the transferability verdict word in favour of an
    argument-only cell; removing the do-nothing band; assessing every kept option by default;
    treating evidence restrictions as plan Settings rather than a constraint kind.
30. **Component skeleton corrections (owner, 2026-09-07).** Components are reused or
    modified from the Evidence search, never mirrored (each marked is-EB / EB-modified / new).
    The EB's mandatory spine — acquire, screen, classify, appraise, ingest — runs **as is at
    longlist depth**, so every option carries evidence types and quality tiers before
    assessment: shown on the option card and as a user-requested sort, **never a place reason**
    (hierarchy bias); this corrects ruling 6's "strongest evidence arrives with the assessment".
    The option-clustering component is named **`longlist`** (EB characterise modified: the same
    two machines at option grain). The three depths are **compositions**, not components:
    ⟨baseline⟩ = spine + synthesise(baseline); ⟨assess⟩ = [acquire if thin] + extract(light) +
    synthesise(profile), "how sure" being the roll-up of tiers already computed; ⟨full run⟩ =
    the whole EB chain as a child task. `inherit` stays a component of its own; `propose` is the
    only component with no EB ancestor. Export is a Share seam.
31. **A document is not an option; inherit findings too (owner, 2026-09-07).** The EB's
    characterise assigns each document to one theme. That will not work for options off the
    shelf: documents discuss bundles, name several interventions, and systematic reviews cover
    many intervention types. The `longlist` component therefore assigns **intervention
    mentions**, not documents, many-to-many — at longlist depth from the screen's structured
    fields (the interventions an abstract names), and at finding grain where a deep Evidence
    search was inherited. A document counts once per option it mentions; a review's spanning
    contribution is visible; a bundle becomes a package with *part of* links. When a linked
    Evidence search ran the deep chain, `inherit` also hands over its **extracted findings**,
    and ⟨assess⟩ skips the light extraction for those documents. The clustering-quality spike
    before the longlist contract must test many-to-many assignment, bundles and reviews across
    domains; option-grain clustering is unproven.

### Pass-3 rulings (owner, 2026-09-07, after the third review pass)

32. **The report is the Result; stages are how it is built.** The scoping task's Result artefact
    is a **report** (the vocabulary's word for the Result tab's artefact), written as linear
    text in the Evidence search report's style with a side outline and collapsible sections.
    Sections: **top line** (the question, what was searched, where things stand) · **the problem
    and what is contested** (from the baseline) · **the approaches** (a paragraph per theme
    naming its options, variants, packages and exclusions with their constraints) · **what the
    evidence base holds** (before assessment: the source-quality profile per option and where
    coverage is thin; after: the assessed table embedded, each effect with its own comparator,
    population and period, and the kept-but-unassessed options by theme) · **transferability and
    assumptions** (assessed form only) · **what needs deciding or commissioning next** (in the
    sense-check branch also the questions to put to the department) · **what was searched and
    not searched**. It **exists from the longlist stage onward** in a provisional form that says
    nothing has been assessed, and is rewritten by assessment. Ruling 14's "summary" becomes the
    top-line section; the report is a **grounded block** (`produce-grounded-block`), never the
    provenance contract's citation-free navigation summary. **Baseline, Longlist (list · grid ·
    shortlist views) and the option profiles are working views**: operated during the run,
    reachable behind the report afterwards. The sense-check branch opens the report on the named
    option. Export = the report with its attachments (profiles, baseline profile, full longlist
    with states and reasons, shortlist assembly record, sources).
33. **Source quality is not "how sure"** (amends ruling 30). Before assessment an option shows a
    **source-quality profile** of the documents that mention it — by evidence type and appraisal
    tier — and never the words "how sure": a high-tier review that mentions an option only to say
    it was never evaluated is not support. After assessment "how sure" means confidence in the
    **specified design–outcome claim** from evidence found relevant to it. Documents are counted,
    not studies, until independence is known; no independent-study tally before then. Ruling 17's
    comparable axes are narrowed: cost as reported is comparable only on matching denominators,
    price bases and scope, otherwise the comparison is withheld.
34. **Applicability, not containment** (amends ruling 18's addendum). A retrieved fact at a
    containing geography fills a local transferability factor only when the proposition applies
    at the target unit by its nature — rules, entitlements, duties, universal provisions, with
    relevant exceptions considered. Aggregates, averages, typical conditions and implementation
    observations are shown as context with their level and date; the local factor stays Unknown.
35. **Inherited findings are reused at finding grain** (amends ruling 31). An inherited
    extraction may be partial, for a different intervention, or under an older field profile.
    ⟨assess⟩ reuses the findings that satisfy the specified option's requirements for the same
    source snapshot and fills or labels the rest; it never skips a whole document because findings
    exist. Profile, version, coverage and source links are preserved and reconciled before
    counting.
36. **Identity rules.** Support binds to a **finding and a specified design**, not to a document:
    a parent's document may carry findings for both designs. A substantive user edit **suspends**
    inherited claims for the variant until its own assessment (it shows "not yet assessed"). The
    default *distinct* screen never excludes a variant or a part-of relation. "Never exclude an
    option" protects **known** candidates: an evidence-scope constraint can prevent an option
    from ever being discovered, so the breadth claim is bounded by the authorised evidence scope,
    and candidates already encountered are preserved when their sources are filtered.
37. **The proposal is a provisional allocation of reading effort**, never "debiased" or
    "representative coverage". "Thin evidence" and "widest implementation record" are defined on
    real fields (count and type of mentioning documents; countries and implementations recorded
    in them), not on impressions. The standard sense-check's comparison set is the most similar
    neighbours **plus one challenger**: an option reaching the same stated outcome through a
    different primary lever type, when the longlist has one; each comparator's reason is stated.
38. **The read set and the cap.** ⟨assess⟩ states how the read set is chosen under the per-option
    cap (stratified so that distinct implementations, the required outcomes and the counter-case
    survive) and how omissions are represented. A budget-limited result may be **explicitly
    incomplete**; the report says what was not read. Whole-run latency, not extraction latency, is
    what the rapid budget measures.
39. **Editorial exceptions are bounded.** Unlabelled editorial structure is allowed; unlabelled
    new empirical or evaluative **propositions** are not, including propositions embedded in a
    question ("how will you scale this proven low-cost intervention?" carries two assessment
    claims). Before assessment the closing questions identify unknowns and never carry
    conditional recommendations. A coverage denominator is the **rendering** of a corpus-level
    claim; behind it stands a reproducible membership set and a per-source support record, as the
    Evidence search's pattern claims already require.
40. **Corrections and recorded decisions.** Tabs are the post-038 vocabulary's: **Agent · Result ·
    Sources · Share · History** (the plan document lives in the Agent tab; Result = the report
    with Baseline and Longlist as views), replacing ruling 1's Plan · Results. Depth words are the
    Evidence search's user-facing **rapid / standard / deep**. The execution contract now says
    components are shared across capabilities (ruling 30's reuse rule, made canonical). The
    assessed table carries no study-design labels ("15 studies", not "4 randomised") — the
    owner's canvas ruling of 2026-09-03, recorded here for the first time. Ruling 8's "Swap on
    shortlist" is superseded by ruling 5's add/remove. The baseline's empirical premises are
    sourced and its interpretations (key assumption, what is contested) are labelled reasoning —
    "reported facts only" was too strong. After assessment, an effect- or cost-shaped constraint
    that fails or cannot be checked is shown on the option ("breaks: low cost (assessed)" /
    "unresolved: cost not comparable"); the option stays and the user decides. The Green Book
    permits facilitated **MCDA**, not the simple weighting-and-scoring MCA it recommends against
    (term corrected in Intent). The distillation comb-through rulings of 2026-09-07 (variant
    threshold left to the agent · no default depth · similarity measure open · sorts = evidence
    strength and study count · parent evidence in "What it is made of" · place-reason vocabulary ·
    no pre-assessment conditional recommendations · inherit as component 0 · one primary lever
    type per option · ambition tag tier-4 · light extraction + reading as the shape to spike ·
    trust boundary between propositions · corpus claims by denominator · closing elements
    unlabelled) are canonical as rulings, recorded here from the review pack's decision sheet.
41. **The child report carries the verdicts** (sharpens ruling 9). The full evidence search stays a
    child Evidence search task with its own report, Sources and History. Written with the
    option-profile template, that report **computes the profile's judgement cells itself** — how
    sure, the transferability verdict and its conditions, the key assumption — with the parent
    scoping task's **user context passed in as input**, so a cap set by unstated context
    persists. The scoping profile mirrors those cells, tagged *full run*, and keeps the
    scoping-pass version in History. This **widens the Evidence search's declared output
    boundary** for the profile-template case only; the OS trust rules (weakest leg, three context
    sources, applicability, no factor fractions) travel with the template. Rejected: the child
    supplying evidence only with scoping recomputing; a single report with no child task.
42. **Spikes, eval refinements and shared seams (from the third review pass).** The spikes before
    any contract, in this order: **1** advice and commissioning on live asks (does the ruled
    journey improve what officials write or commission, against a progressive account with the
    same evidence); **2** evidence attribution and confidence (mention vs support; documents vs
    independent evidence; inherited availability vs compatibility); **3** option-grain construction
    and selection stability (mentions and findings → options, packages, variants; does relabelling
    a primary lever move places without changing substance); **4** local-condition adjudication
    (applicable rule vs aggregate; report vs commitment); **5** balanced reading within a real
    budget (whole-run time to a usable qualified result; what a tighter cap loses); **6** a
    specification-level contract trace of one inherited question and one edited variant through
    every component. The original two spikes are 3 and 5. Eval refinements: user-requested sorts
    are choices with selection effects and are evaluated for what they discourage, not only for
    guess accuracy; a newcomer's inclusion is not a success criterion — the test is whether they
    recognise an omission or an unsupported transfer after the baseline. Shared seams recorded for
    the system contracts: a reading-budget and evidence-eligibility mechanism (execution /
    retrieval); source-quality policy kept distinct from evidence-scope constraints in the plan
    vocabulary (policy flags, never deletes); durable option identity and relations across runs
    (data model — a run-local cluster id is not enough).
43. **Interface rulings (owner, 2026-09-07).** The six open interfaces the third review pass
    raised: (1) intervention mentions and the abstract-level fields (setting, population, outcome
    family, design hint) come from **`extract` with a new abstract profile** over every
    screened-in document, reused by memo; the **screen is unchanged** and screens for relevance
    only; study geography is read from the abstract, never inferred from publication metadata.
    (2) Unknown and Non-evidence documents appear as **their own buckets** in an option's
    source-quality profile; non-evidence counts as a mention, never as evidence; Unknown is **not
    resolved within scoping**. (3) The capped read set in ⟨assess⟩ is built by the EB's
    **`select` with a scoping strategy** (ruling 38's discipline: stratify by implementation and
    outcome family, reserve the counter-case, cap, record omissions); `extract` keeps taking a
    selected set. (4) Claim kinds: membership and countable aggregates are EB **pattern claims**;
    relations are reasoning claims or user actions; constraint states are records; the
    **transferability working is a new column-grounded block kind** declared in the provenance
    contract. (5) The baseline searches **Overton and OpenAlex only** in v1 and says what it could
    not reach; the open-web seam stays closed. (6) Uploaded snapshots: **deferred** — no upload
    feature exists; when it does, uploads do not cross a Link automatically. Options scoping
    therefore uses `extract` with two profiles (abstract; light full-text) and `select` with one
    new strategy, and adds no sibling component for any of them.
