# Task contract: 017-orchestrator

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** **drafted rev 2.3** — awaiting contract 🛑 (revs 1–2.3 were
> shaped in the gate conversation, not yet approved). Companion:
> [v2-wizard-study.md](v2-wizard-study.md) (rev 2.2c evidence).
> Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ ·
> ADR: expected (the v1 orchestrator carve + the Unattended steering-mode
> refinement; drafted at step 4).
>
> **Terminology note — two "plans" collide on this slice.** The
> **orchestration plan** (plan-as-object spec) is the product object
> this slice builds: what the user approves before a run. The
> **implementation plan** (`plan.md`, task-cycle step 3) is this
> task's build plan; "plan-pinned" means decided there, reviewed at
> the plan 🛑. The existing per-component `plan.py` `Plan` is the
> commit-layer config already in the tree — this contract calls it
> the **component config** to keep the three apart.
>
> **Revision history:**
> - **rev 2.3** (2026-07-10, user gate probes round 3 — two changes):
>   **(a) Screening criteria adopted as a first-class plan field**
>   (user probe — rev 2.2 had deferred them wholesale to the 014
>   structured-directive seam; the V2 study called invisible criteria
>   its biggest gap, and the fix splits cleanly): user-expressed and
>   planner-suggested inclusion/exclusion criteria live visibly in
>   the plan; v1 compiles them deterministically into the scope's
>   intent/scoping text the screen already judges against (no
>   screen-prompt change); the per-criterion structured compile
>   remains the 014 seam this field re-targets to. **(b)
>   "Off-limits" corrected to "staged"** (user challenge on synthesis
>   framing): only the grounding-judge surface is hard-pinned; the
>   synthesis writer prompt is refinable and explicitly queued for
>   018's refine loop (demo voice rules · writer-under-uses-finding-
>   claims · the user's live-run quality report), now including the
>   audience/user-context pair (planner field + consumption together —
>   the no-dead-fields rule is why the field doesn't ship in 017).
>   017's synthesise bar stays mechanics + honesty labels, not prose
>   quality.
> - **rev 2.2** (2026-07-10, user gate probes round 2 — three
>   changes): **(a) Plan table in — the events-only posture reversed**
>   (user challenge held; rev 2.1c superseded): the plan is the most
>   behaviour-bearing object in the slice and 018's read surface is
>   its near-term reader (the demo's event-scraping read models are
>   the RETRO-flagged anti-pattern) — a minimal `orchestration_plan`
>   table becomes the slice's one approved schema addition (decision
>   2; shape plan-designed; immutable version rows; events still emit
>   as the decision-log trail). **(b) Language scope-constraint
>   dropped** (user call): English-language tool for UK policy makers;
>   the grammar key exists if that changes. **(c) V2 search-wizard
>   study folded in** (Explore agent over `../discovery_policy_atlas`;
>   findings in the design record): adopted — suggested answers on
>   planner questions (2–5, broad→narrow, buttons + free text,
>   degrade-don't-block, re-derived as framing evolves),
>   no-preference-style visible defaults, pre-launch review; named
>   anti-patterns — intervention-framed copy/prompts (V2 hard-coded
>   "about interventions" into every suggestion prompt), dead
>   collected fields (`use_case` analytics-only, additional-questions
>   step skipped dead, `inner_setting` unread by retrieval/screening),
>   one-shot suggestions, opaque derived screening criteria (confirms
>   the visible-defaults posture + the deferred structured-criteria
>   seam).
> - **rev 2.1** (2026-07-10, user gate probes — four holds): **(a)
>   Intent-fit component selection** — rev 2 derived the discretionary
>   set from the gradation alone; the user challenge held (extraction
>   is intervention–outcome schema-bound — irrelevant to
>   non-intervention intents at any depth). Decision 4 restructured:
>   selection = **intent-fit × gradation**, the planner reasoning over
>   declared component descriptions; live check gains the
>   non-intervention composition probe. **(b) Scope constraints
>   first-class** — recency/geography/language plan fields compiled to
>   the existing search `scope_filters` grammar, defaulted visibly and
>   asked only when shape-changing; publication-vs-study-geography
>   honesty caveat; structured screening inclusion/exclusion criteria
>   named as the existing 014 seam. **(c)** Events-not-schema rationale
>   sentence added to decision 2 (the durable plan entity belongs to
>   the workspace/versioning cluster; the event log is already the
>   decision log). **(d)** "Deepest successful reference" wording
>   corrected in the goal + decision 8: synthesise composes over the
>   **entire successful upstream chain** (transitive resolution from
>   the deepest successful reference — the passing mechanism, not the
>   substrate).
> - **rev 2** (2026-07-10, user gate conversation — six adjudications):
>   **(a) Steering folded in as the structural core** (resolving rev 1's
>   ❓ decision 6a — the user challenged the exclusion and the challenge
>   held: nothing about check-ins is frontend-dependent in a serial CLI
>   driver): steering modes on the plan, deterministic-content check-ins
>   at component boundaries, the deepening-selection steer-point with
>   computable triggers, bounded contextual adjustments, abort, Minimal's
>   end-of-run collation. The conversational half (narration voice,
>   clarify/escalate parking, `agent_judgement_routed`, free-text
>   replanning) stays out as named seams. **(b) A fourth steering mode —
>   Unattended** (user call): zero mid-run interaction; the anticipated
>   steer-points' default resolutions are **visible plan content**
>   (approving/starting the run is the consent — nothing extra is
>   asked); every auto-resolution is flagged and collated. Carries a
>   **spec refinement** to execution-orchestration § Steering modes
>   (the "substance escalates in every mode" principle gains the
>   pre-declared-visible-default path; never *silent*, no longer always
>   *live*). **(c) Capability sub-agent: boundary in, expert agent its
>   own slice** (user challenge + lead pushback converged): the driver
>   is structured as the **EB capability-runner** the orchestrator
>   delegates to — a legitimate deterministic realisation per the
>   spec's rigidity dial — with the directive-authoring slot as its
>   internal seam; the LLM EB-expert (JIT directive authoring +
>   expertise-bearing cohesion) is recorded as its own future slice,
>   recommended post-eval. **(d) Retrieval-boost grammar v2 adjudicated:
>   stays deferred, eval-gated** (rev 1 decision 8's recommendation
>   ratified). **(e) Nudge vocabulary pinned**: lighter / as proposed /
>   deeper, fixed; every option presented with its re-derived concrete
>   proposal + time band; middle gradation is the default proposal.
>   **(f) Adjacency sweep folded in** (full spec-set read): expected-
>   artefact-shape forecast field; thin-base escape hatch declared in
>   the plan; deepening-selection option set speaks user intents;
>   named-out additions (uploads, artefact-instance/rerun semantics,
>   tag-namespace consolidation with the user's live observation
>   recorded, conclusion block/key-findings/summaries).
> - **rev 1** (2026-07-10): initial draft. Sequencing context: fourth
>   slice of the live-demo path (014 → 015 → 016 MERGED → **017
>   orchestrator/planning** → 018 demo dress-rehearsal → eval slice);
>   re-sequenced ahead of the dress rehearsal by the user 2026-07-10
>   (a rehearsal without a real orchestrator rehearses a scaffold;
>   the refine loop would miss the planner prompt). Grounded on:
>   ADR 0013 (the composition rule this slice compiles), the
>   plan-as-object + execution-orchestration system contracts (the
>   spec cluster this slice cuts a thin v1 from), the as-built
>   `plan.py`/`skeleton.py`/`search_loop.py` seams, 016's per-leg
>   wall-clocks, and `demo/RETRO.md` + `demo/server/orchestrator.py`
>   (branch `demo-live-run`) as **anecdotal prior only** (standing
>   user call: the demo was throwaway; no demo shape, prompt or
>   number is design authority).

## Goal

Land the first product path from **user intent to executed evidence
run**. Today the mandatory EB spine and every discretionary component
exist and run live, but nothing in product code decides *which* chain
a question deserves: `skeleton.py` hand-sequences a fixed demo
profile, and the throwaway demo branch's planner is de-authorised.
017 ships the **thin v1 orchestrator**:

1. **Planner** (the one new LLM surface, prompt lead-authored): takes
   the user's intent conversationally, refines it into a sharp
   evidence question, proposes a depth-graded orchestration plan
   anchored to concrete numbers + a time band, and supports the
   relative **lighter / as proposed / deeper** nudge.
2. **Composer** (deterministic): compiles an approved orchestration
   plan into a chain composition — fail-closed against the component
   registry, always containing the ADR 0013 mandatory spine, with
   discretionary components selected by **intent-fit × gradation**
   (decision 4: relevance to the question decides *which*; depth
   decides *how much*).
3. **EB capability-runner** (serial, deterministic): the execution
   half the orchestrator delegates to — walks the composed chain over
   the existing components in topological order with per-component
   commits, authors each component's directive from the plan (the
   commit layer), surfaces check-ins and the deepening-selection
   steer-point back through the orchestrator, and chains run
   references only off successful predecessors — so synthesise always
   composes over the entire successful upstream chain.
4. **Steering, structural core** (rev 2a/2b): four modes — Frequent ·
   Moderate · Minimal · **Unattended** — governing check-in frequency;
   check-ins with deterministic content and bounded, contextual
   adjustment options; substance honoured in every mode (live pause,
   or Unattended's pre-declared visible defaults).

Thin v1 means exactly this carve of the spec cluster. The LLM
capability agent, durable resume, narration, section-directive
compile and the capability-run entity are named seams, not silent
omissions (decisions 1, 6, 7; Out of scope).

## Deliverable

PR landing:

- New orchestrator module(s) (final naming plan-designed): the
  planner backend + its lead-authored prompt, the orchestration-plan
  model + composer, the EB capability-runner, and one new CLI
  entrypoint (intent in → planner conversation → plan approval → run
  with check-ins per mode → artefact; the product path).
- The depth-gradation compile (decision 4): graded bundles →
  per-component directives over **existing** directive surfaces only,
  with the anchored lighter/as-proposed/deeper nudge.
- The steering structural core (decision 6): modes, check-ins, the
  deepening-selection steer-point + intent-vocabulary options,
  bounded steering application recorded as user-attributed events,
  abort, end-of-run collation.
- Failure semantics productionised (decision 8): spine-leg failure
  fails the run honestly; discretionary-leg failure degrades with
  flags; bounded retry for LLM-bearing legs.
- Plan persistence (decision 2, rev 2.2): the minimal
  `orchestration_plan` table (the one approved schema addition) +
  `plan.proposed` / `plan.approved` / `plan.amended` events
  referencing it — the plan is the first decision-log entry.
- Stub planner backend; `make verify` stays green, deterministic and
  egress-free.
- Spec flow-back: the **Unattended-mode refinement** to
  execution-orchestration § Steering modes (rev 2b — exact text
  drafted in-build, `log.md` entry; folded into this slice's ADR);
  ADR for the v1 carve; `deferred.md` + knowledge updates (new seams:
  LLM EB-expert slice; sharpened tag-consolidation trigger).
- Tests + `verification.md` with the pinned live check (decision 10).

## Read first

- [ADR 0013 — the mandatory EB spine](../../adr/0013-mandatory-eb-spine.md)
  — the one authoritative chain rule the composer compiles against
- [plan-as-object](../../specs/system/plan-as-object.md) — plan vs
  config, robust-compile-by-construction, forecast vs commit,
  thoroughness as a relative nudge, enough-context-to-propose
- [execution-orchestration](../../specs/system/execution-orchestration.md)
  — plan-time authority, steering modes + the routing rule (the
  section decision 6 implements structurally and rev 2b refines),
  durability; sub-agent realisation ("each component realised by the
  mechanism its nature demands"; rigidity dial)
- [EB capability.md](../../specs/capabilities/evidence-base/capability.md)
  — the component skeleton, § Check-in points (the deepening-selection
  steer-point + its triggers — decision 6's substance instance)
- [EB components.md](../../specs/capabilities/evidence-base/components.md)
  — per-component directive surfaces the runner authors; select's
  bidirectional rationale (what the steer-point reads)
- As-built: `plan.py` (component config + fail-closed registry — the
  commit layer, reused), `skeleton.py` (the hand-sequenced chain this
  slice productionises: directive read-modify-write pattern, deep-round
  loop driving, run-reference threading), `search_loop.py`
  (`DEPTH_CONSTANTS` + `should_escalate` — the depth compile target
  and the declared thin-base hatch), `select.py` (directive grammar:
  budget/boosts/must-includes — the steer-point's compile target),
  `harness.py` (`run_harness`, the one-component dispatcher)
- 016 `verification.md` per-leg wall-clocks (feeds the gradation bands
  and time bands)
- `demo/RETRO.md` + `demo/server/orchestrator.py` + `demo/server/driver.py`
  (branch `demo-live-run`) — **anecdotal prior only**: which live
  chain-driver hazards are real (characterise wobble → retry-once,
  failed stages must never feed run ids downstream, plan-shape/
  contract divergence as the recurring failure class)

## Scope / Out of scope

**In:**

- New orchestrator + EB capability-runner module(s) + CLI entrypoint
  + tests.
- The planner prompt surface (lead-authored) + stub backend.
- Orchestration-plan model, composer, depth-bundle table, runner,
  steering core (modes · check-ins · steer-point · bounded
  adjustments · collation).
- `plan.py`: additive extension only if composition needs it (the
  component config and registry semantics are reused, not reshaped).
- Event vocabulary: `plan.proposed` / `plan.approved` / `plan.amended`
  + steering-resolution events (event payloads, zero-schema — the 001
  event-log substrate).
- `skeleton.py`: untouched — it stays the zero-egress walking-skeleton
  smoke.
- Spec flow-back (the rev-2b steering refinement) / ADR /
  `deferred.md` / knowledge updates.

**Out (stay deferred — `docs/deferred.md`):**

- **The LLM EB-expert capability agent** (rev 2c, user + lead
  converged) — the JIT directive author system-prompted as an
  evidence-review expert: reads upstream outputs to author each
  commit's directive, makes reasoned surface-vs-settle judgement
  calls, carries domain expertise into a more cohesive artefact. Its
  own slice, recommended post-eval (directive quality is unmeasurable
  until then); the runner's directive-authoring slot (decision 1) is
  its drop-in seam.
- The conversational steering half: narration voice (the demo's
  second posture), `clarify`/`escalate` parking on durable signals,
  `agent_judgement_routed` residual events (they require runtime
  agent discretion the deterministic runner doesn't have), free-text
  steering→replanning, mid-run mode *suppression* rules.
- Durable resume engine: no block-boundary resume, no tool-result
  memoisation, no parked branches (decision 7 accepts re-run-from-
  the-top for 017/018).
- Section-directive compile: the fail-closed `context["synthesis"]`
  directive keeps **nothing compiling into it** (013 seam); synthesise
  keeps intent-led run-time sectioning — deliberately better than
  plan-time headings, since sections are substrate-aware and the
  substrate doesn't exist at plan time (ADR 0010). The plan's
  **expected-artefact-shape field** (decision 2) is the honest
  plan-time indication instead.
- Retrieval-boost grammar v2 (**adjudicated at this gate, rev 2d**:
  stays deferred, eval-gated via its own 013-surface slice; 017
  composes with the v1 grammar as-built).
- Tag-namespace consolidation — orchestrator-family seam, trigger
  unfired in v1 (one run per project); **sharpened trigger recorded**
  (user live observation, 2026-07-10): classify's open
  methodological/structural tag vocabulary fragments at live scale,
  isolating documents — consolidation becomes useful there first.
- Capability-run entity + multi-facet fan-in (schema-gated seams).
- Plan-field ↔ chat-turn provenance: v1 persists the approved plan
  object, not per-field conversation back-references (recorded seam);
  the planning transcript itself is ephemeral CLI state in v1.
- **Uploads** (user call, rev 2f): the planner takes intent text
  only; upload inputs + the 🟡 function-lane routing arrive with
  their own slice.
- **Artefact-instance / rerun semantics** (data-model: "the plan is
  the registry of artefact instances"; supersede-vs-sibling): v1 is
  one intent → one project → one run → one artefact; versioning UX is
  workspace-cluster territory.
- Conclusion block / key-findings / summaries (user call: next
  slice with the rendering surface — the 018 straddler).
- Co-pilot Q&A, source/evidence policy (both faces), time/cost
  estimate model (coarse band only), component-progress protocol,
  front-end/rendering, eval formalisation, branch parallelism.

## Decisions

1. **Architecture: orchestrator delegates to an EB capability-runner
   — the sub-agent boundary is real in v1; the expert agent is not**
   *(rev 2c)*. The orchestrator owns intent → plan → forecast →
   check-in relay; the **EB capability-runner** owns the walk, the
   commit layer (per-component directive authoring from the plan) and
   the declared escape hatch, and surfaces steer-points through the
   orchestrator (in-process, a function boundary — but the interface
   is the spec's: sub-agents never address the user directly). A
   deterministic runner is a legitimate realisation per the spec's
   rigidity dial ("fixed pipeline = degenerate case of one
   construct"; EB sits toward structured). The runner's internal seam
   — "given plan + upstream state → next component's directive" — is
   exactly where the LLM EB-expert drops in later, with its own gate.
   New modules; `skeleton.py` stays the zero-egress smoke; the
   de-authorised demo driver stays on its throwaway branch. The
   existing component config (`plan.py`) is the commit layer, reused
   as-is; any extension is additive and plan-designed.

2. **The orchestration plan is a structured selection, persisted as
   a first-class table** *(rev 2.2 — user challenge held, reversing
   rev 2.1c's events-only posture)*. A pydantic model over: refined
   question · scoping notes (user-expressed only, never invented) ·
   backend scope (existing `search_backend_scope` vocabulary) ·
   **scope constraints** *(rev 2.1b)* — recency window · geography —
   compiled into the existing search `scope_filters` grammar
   (`published_after`/`published_before` · `publisher_country`; the
   as-built 015 directive surface), each **defaulted visibly**
   (assumptions field) and asked about only when shape-changing, with
   one honesty caveat carried: a geography constraint is
   **publication** geography — study geography lives in the text and
   is a recorded extraction seam, and the plan must never imply
   otherwise (no language field *(rev 2.2)* — Policy Atlas is an
   English-language tool for UK policy makers; the grammar key exists
   if that ever changes) · **screening criteria** *(rev 2.3a — user
   probe; the V2 study's "biggest gap" finding adopted rather than
   deferred wholesale)* — user-expressed and planner-suggested
   inclusion/exclusion criteria ("only studies with under-5s",
   "exclude opinion pieces"), a first-class, visible, editable plan
   field; **v1 compile is deterministic composition into the scope's
   intent/scoping text** — the surface the screen already judges
   against, so no screen-prompt change rides this slice — and the
   field re-targets to the structured screening directive when that
   recorded 014 seam lands (per-criterion structured compile stays
   that seam; unlike V2, the criteria are never invisible: they sit
   in the plan, not buried in a rubric) · depth
   gradation (decision 4's bundle) · discretionary component set
   (decision 4's intent-fit × gradation selection, visible in the
   plan) · grouping facet ·
   **steering mode** (decision 6) · **the anticipated steer-points'
   default resolutions** (visible plan content — what Unattended
   auto-applies and every mode falls back to; rev 2b) · **the declared
   escape hatch** (the thin-base search escalation, as-built in
   `search_loop` — declared rather than firing undeclared; rev 2f) ·
   **expected artefact shape** (a forecast-level, non-executing field
   derived deterministically from the composed chain: landscape
   coverage/themes/gaps iff characterise; facet-organised synthesis
   sections iff the deep chain; grounded answer otherwise — content
   kinds, never proposed headings; rev 2f) · assumptions/open guesses
   (first-class, cheaply correctable — thin-context plans are visibly
   thin) · a coarse time band derived from the 016 wall-clocks (the
   estimate model stays deferred). Robust compile by construction:
   the plan can only reference what the registry declares; a plan
   that doesn't validate is a caught error, never a silent run.
   Persistence *(rev 2.2 — user challenge held; supersedes rev
   2.1c)*: a minimal **`orchestration_plan` table** — the plan is a
   first-class domain object, not an event-scrape. Rationale for the
   reversal: the plan is the most behaviour-bearing object in this
   slice (proposed → approved → amended at steer-points → compiled →
   executed against) and the spec's central audit object
   (plan-as-canonical); its first read surface is near-term (018
   renders "the plan for this project" — the demo's event-scraping
   read models are the RETRO-flagged anti-pattern); a keyed row beats
   latest-event lookup for every downstream reader. Shape is minimal
   and **plan-designed within this approved gate**: id · project (+
   scope) reference · status (proposed / approved / superseded /
   abandoned) · version (amendments append immutable version rows,
   never mutate) · the validated plan payload · timestamps +
   attribution; linkage to executed component runs is the minimal
   form the implementation plan justifies (e.g. nullable `plan_id` on
   `runs`, or plan id + version carried in `plan.compiled` payloads).
   The `plan.proposed` / `plan.approved` / `plan.amended` events
   still emit, referencing the plan row — the decision-log trail and
   the durable object are complements, not alternatives. What stays
   out: the artefact-like machinery (blocks/units, versioning UX,
   change-log surfaces — workspace cluster) and the capability-run
   entity (still deferred); the run's execution identity in v1
   remains the project + scope + its event trail.

3. **Composition: the ADR 0013 spine is enforced by construction and
   test-pinned.** Every composed chain executes acquire(`search`) →
   screen → classify → appraise → ingest(fetch) → synthesise in
   spine order; characterise · stage-2 screen · select → extract →
   group are selected per gradation; structural dependencies ride
   the existing fail-closed registry (select requires a
   characterisation reference, extract a selection, group an
   extraction; synthesise's references are all optional and resolve
   transitively from the deepest given — passing the deepest
   successful reference hands it the entire successful upstream
   chain, cross-checked; rev 2.1d). Tests pin: no composable plan
   omits or reorders a spine leg; an unknown component or parameter
   rejects at validation.

4. **Component selection is intent-fit × gradation; the nudge is
   anchored and its vocabulary is pinned** *(restructured rev 2.1a;
   rev 2e)*. Two independent factors select the discretionary set,
   per the spec's breadth/depth independence:
   - **Intent-fit** *(rev 2.1a — user challenge held)*: the planner
     reasons over the **declared component descriptions** (what each
     component does and what question shapes it serves — the
     execution-orchestration "reading declared capability specs"
     rule) to decide which discretionary components are *relevant* to
     the question at all. The canonical case: extract is
     intervention–outcome **schema-bound** (components §7/§9), so a
     non-intervention intent (stats/fact-finding, stakeholder
     mapping, landscape-only questions) composes **without the deep
     chain at any depth** — served by characterise + chunk-grounded
     synthesis; depth then buys search breadth and synthesis
     thoroughness instead. Irrelevant-component reasoning is visible
     in the plan (the discretionary set + a why), and composition
     stays fail-closed regardless of what the planner reasons.
   - **Gradation**: how much of what's relevant. Graded
   bundles are an orchestrator-authoring convenience (never a
   user-facing absolute dial); the user-facing controls are the
   concrete proposal and the relative nudge. Pinned now: **the
   default proposal is a middle gradation**, anchored to concrete
   numbers + a time band; the nudge vocabulary is fixed as
   **lighter / as proposed / deeper** (constant across all projects
   and runs — it lives in one prompt artifact and the plan schema);
   **every nudge option is presented with its own re-derived concrete
   proposal + time band** ("Lighter — skip deep extraction, ~15 min ·
   Deeper — extract ~40 docs, ~90 min"), so the choice is always
   between anchored proposals, never labels. Conversational effort
   signals ("quick first look") absorb into the proposal — expected
   rare; the anchored default carries the common case. v1 compile
   targets, all existing: search depth (`rapid`/`deep`, 015
   `DEPTH_CONSTANTS`) · stage-2 screen on/off · characterise on/off ·
   deep chain on/off · selection budget · grouping facet.
   Deliberately **not** compiled in v1: synthesis section directives,
   per-depth fetch budgets, synthesis caps, parser tiers — recorded
   levers of the gradation seam, which this decision opens but does
   not finish. Exact bundle table plan-pinned, informed by 016's
   per-leg wall-clocks.

5. **The planner is the slice's one new prompt surface — lead-
   authored, judgment-class.** Conversational: refines intent into an
   evidence question, asks **only when a missing piece would change
   the plan's shape** (enough-context-to-propose — shape includes the
   intent-fit component selection and any shape-determining scope
   constraint; detail unknowns become visible defaults, never
   questions; rev 2.1a/b), updates a visible
   plan draft each turn, sets a ready flag; proposal anchored per
   decision 4; carries the declared component descriptions as its
   reasoning substrate. **Questions carry suggested answers**
   *(rev 2.2c — the V2 search-wizard study, user direction)*: when
   the planner does ask, its structured turn output includes 2–5
   candidate answers alongside free text (scoping suggestions ordered
   broad → narrow — the V2 pattern that worked), so 018's surface can
   render them as buttons while the CLI shows numbered options;
   suggestion failure degrades to a plain free-text question, never
   blocks; suggestions re-derive as the framing evolves (V2's
   one-shot-never-revisited is the named anti-pattern). Scoping
   dimensions (population, setting, outcomes) **and screening
   criteria** (rev 2.3a) are suggestion material
   **when the intent type warrants them** (intent-fit — V2 hard-coded
   the intervention frame into every prompt and heading; this prompt
   is question-type-neutral by design). **No dead fields**: V2
   collected `use_case`, additional-questions and `inner_setting`
   into analytics-only or unread state; every V3 plan field compiles
   or is explicitly non-executing annotation (decision 2), and
   nothing is asked that nothing consumes (V2's audience/user-context
   field is deliberately not collected in 017 — its only consumer is
   synthesis framing, and the pair — planner field + prompt
   consumption — lands together in 018's refine loop; rev 2.3b).
   Structured output validated fail-closed (pydantic; the
   planner cannot smuggle components or parameters past the
   registry). Honesty rules carried from the product voice: never
   promise findings, never state what the evidence says, assumptions
   surfaced not buried. The demo planner prompt is an anecdotal
   prior; this prompt is written fresh by the lead. Model:
   judgment-class OpenAI (the demo observed planning needs it; exact
   model id plan-pinned). Suite runs a stub planner — zero-egress
   default unchanged.

6. **Steering: the structural core, four modes — adjudicated at this
   gate** *(rev 2a/2b, resolving rev 1's ❓)*.
   - **Modes**: Frequent · Moderate · Minimal · **Unattended**, a
     plan field compiling to *which component boundaries pause*.
     Frequent pauses at every boundary; Moderate at the important
     crossings (deepening-selection; landscape → synthesis) — exact
     pause sets plan-pinned; Minimal pauses only for substance;
     **Unattended never pauses** — anticipated steer-points
     auto-resolve to the plan's visible default resolutions
     (decision 2), every auto-resolution flagged, collated and marked
     on the run record. Substance is thereby honoured in every mode:
     live pause, or pre-declared visible defaults — never silent.
     This is a **spec refinement** to execution-orchestration
     § Steering modes (the firm principle's wording assumes a live
     pause; Unattended adds the pre-declared path — flow-back rides
     this slice, folded into the ADR).
   - **Check-in content is deterministic** — rendered from event
     payloads (the `skeleton.py` render-function pattern); no
     narration prompt surface.
   - **The deepening-selection steer-point** (EB's pre-declared
     substance point): pauses after `select`, before `extract`, in
     every mode except Unattended; reads select's bidirectional
     rationale; escalates above the mode baseline when a computable
     trigger fires — the selection **excludes a large or
     user-nominated cluster**, or the **base is thin** (the third
     spec trigger, policy-unmeetable, is n/a — no policy object in
     v1). **Options speak user intents** *(rev 2f, user call)*:
     deepen named clusters (tag boosts / must-include pins) · "just
     the strongest evidence" (appraisal-tier-weighted ordering) ·
     "most relevant to my question" (relevance-weighted ordering) ·
     adjust budget · as proposed — each compiled to the declared
     selection grammar; an intent the grammar cannot express yet is
     an honest "not yet" (recorded seam), never a silent
     approximation. Exact expressible set is a plan-time check
     against `select`'s as-built directive fields. After adjustment,
     `select` re-runs cheaply; `extract` has not yet spent.
   - **Bounded steering application, everywhere**: at any pause the
     user may continue · adjust not-yet-run legs' directives within
     the declared grammar (incl. the remaining-legs nudge and a mode
     change) · **stop the run** (clean abort: committed legs stand,
     run honestly marked abandoned, no artefact — synthesise is the
     minting terminus). Never re-runs completed legs, never free-text
     replanning. Every steering response is a user-attributed
     `plan.amended` event (the spec's "human substance enters
     honestly in provenance").
   - **Minimal/Unattended collation**: flagged events (degraded legs,
     hatch firings, retries, auto-resolutions, coverage caveats)
     collate into an end-of-run review.

7. **Durability: per-component commits, no resume engine —
   adjudicated at this gate** *(rev 2, user-confirmed)*. Each leg
   commits as it lands (the durability spec's block-boundary-commit
   direction; also what a future read surface needs to watch a run);
   a failed run reports honestly and is re-run from the top. The
   long-deep-run fragility this accepts is recorded at the durability
   seam; building the engine pre-demo is overreach. This changes the
   run's transaction shape from `skeleton.py`'s single
   `engine.begin()` — the single-active-writer-per-project invariant
   is unchanged (serial runner), and partial state on failure is
   visible-by-design (status/events say what completed); the demo
   drove per-stage transactions live without incident.

8. **Failure semantics (the RETRO priors, productionised as code
   rules).** A failed stage never feeds its run id downstream: stages
   chain only off successful predecessors. **Spine-leg failure fails
   the run honestly** (evented, run status failed, no downstream
   legs — a run that cannot screen has nothing true to synthesise).
   **Discretionary-leg failure degrades**: the leg's failure is
   evented + flagged, downstream discretionary legs that require it
   are skipped with reason, and synthesise composes over the **entire
   successful upstream chain** — the runner passes the deepest
   *successful* reference and the rest resolves transitively, so only
   the failed leg and its dependents drop (ADR 0010's
   every-upstream-reference-optional design absorbs this by
   construction; rev 2.1d). LLM-bearing legs get **one
   bounded retry** before failing (which legs, plan-pinned; the
   characterise twice-in-a-row wobble is the motivating prior). All
   outcomes reason-coded in events; nothing silently absorbed.

9. **Retrieval-boost grammar v2 — adjudicated: does NOT ride 017**
   *(rev 2d, user call at this gate)*. `deferred.md` pre-registered
   it "before 017 or alongside it"; resolved: 017 composes with the
   **v1 grammar as-built** (selection budget/boosts/must-includes;
   grouping facet) — sufficient for plan composition and the demo;
   v2 (tag-based retrieval scoping + the screen-confidence clamped
   multiplier, grammar already pre-decided) is a 013-surface,
   eval-sensitive change that lands via its own gate with eval
   coverage. Adjudication recorded in `deferred.md`.

10. **Live-check scope pin** (contract-time, per failure-log
    2026-07-08): changed surfaces + one cheap full-chain smoke —
    (a) **planner surface**: 5–7 intents sampled across the V2
    question-taxonomy categories → proposed plans lead-reviewed for
    shape (sharp question, honest assumptions + visible defaults,
    sane intent-fit selection × gradation + expected-artefact-shape,
    ask-only-on-shape behaviour); planner conversations only, **no
    chains run**; at least one conversation exercises the anchored
    nudge and shows the whole plan re-derived with its new time band;
    **at least one non-intervention intent composes without the deep
    chain** (rev 2.1a — the intent-fit probe); at least one
    conversation carries a scope constraint (e.g. recency) landing as
    a compiled `scope_filters` field (rev 2.1b) and one a screening
    criterion visibly composed into the judged intent (rev 2.3a); at
    least one planner question observed carrying sensible suggested
    answers, and none on an intent where no question was
    shape-necessary (rev 2.2c).
    (b) **one composed end-to-end run**: a real Nesta-mission
    question through the product path — planner → approval → composer
    → runner → artefact — at a **modest gradation** (deep enough to
    exercise discretionary composition, bounded corpus; the deep
    dress rehearsal is explicitly 018's), run at **Moderate** so the
    deepening-selection steer-point fires live and one steering
    adjustment (an intent-vocabulary option) is exercised and lands
    as a `plan.amended` event. Recorded: the composed chain vs the
    approved plan (provably the same — the audit point), per-leg
    wall-clocks, failure/degrade behaviour if any leg wobbles, the
    minted artefact's honesty labels intact.
    (c) **failure-semantics + Unattended evidence at test level**
    (fault-injected runner tests per decision 8; a scripted
    Unattended run auto-resolving a fired steer-point with the
    resolution flagged + collated) — no live fault probe.
    Cost: one planner conversation set + one modest live chain —
    low single-digit dollars.

11. **Telemetry: plan + steering events + existing component events;
    no new protocol.** The plan lifecycle is auditable from the event
    log (`plan.proposed` → `plan.approved` → per-component
    `plan.compiled` → component events, with `plan.amended` +
    steering-resolution events interleaved). The user-grade
    component-progress protocol stays a recorded seam (016
    precedent); the CLI surfaces the existing structured logs.

## Constraints & approval gates

- **Runtime egress** (gated, rides this slice): the planner LLM call
  — one new lead-authored prompt surface reaching the model provider
  with user intent text. Approved at this contract's 🛑. All other
  egress (search backends, fetcher, component LLM calls) is
  previously approved and rides unchanged.
- **Schema** *(rev 2.2 — one approved addition)*: the minimal
  `orchestration_plan` table + its minimal run linkage (decision 2;
  exact shape plan-designed, reviewed at the plan 🛑). Nothing else —
  the capability-run entity, plan blocks/units, or any further
  table/column is a **stop condition**.
- **Dependencies**: none expected (`openai` + `pydantic` already in
  the tree). Any candidate returns through the dependency gate with
  its case.
- **CI**: no change.
- **Public interfaces**: one addition approved at this 🛑 — the
  orchestrator CLI entrypoint (the product path). No new
  Plan/Config public fields beyond the orchestration-plan model
  itself.
- **New LLM surfaces**: exactly one — the planner prompt,
  lead-authored (AGENTS.md rule: prompt-bearing work is lead-only).
  Check-in content is deterministic by design (decision 6) — no
  narration surface. **No other prompt text changes ride this slice**
  *(rev 2.3b — staging, not sanctity)*: only the grounding-judge
  surface is hard-pinned (013: judge-input changes land with eval
  coverage only); every other prompt — the synthesis writer
  emphatically included — is refinable, but prompt *improvement* is
  018's contract-pinned refine loop, which carries the discipline
  eval-blind edits need (per-surface replay over captured I/O,
  anti-overfit checks across the question taxonomy, every change
  logged as an observation→change pair). The synthesis writer prompt
  is explicitly queued there — the demo's unvalidated voice rules,
  013's writer-under-uses-finding-claims observation, the user's
  2026-07-10 live-run quality report ("outputs quite frankly crap"),
  now joined by the **audience/user-context pair** (planner field +
  synthesis-framing consumption land together, so no dead field
  ships in 017). 017's live-check bar for synthesise is composition
  mechanics and honesty labels, not prose quality — that's 018's
  measured target.
- **Spec refinement** (rides this slice's flow-back, approved at this
  🛑 in principle): execution-orchestration § Steering modes gains
  the Unattended mode via the pre-declared-visible-defaults path
  (rev 2b); exact text drafted in-build, `log.md` entry, folded into
  the ADR.

## Public / private boundary

Committable: contract/plan/verification artefacts, tests, the stub
planner fixtures, prompt text (product IP but repo-committed like
every other prompt surface). Private: live-check artefact content and
planner conversation transcripts beyond what verification evidence
needs (counts, shapes, wall-clocks, redacted excerpts); no fetched
document bytes committed (016 discipline unchanged).

## Model route

Planner → judgment-class OpenAI model (exact id plan-pinned; the
demo's observation that planning needs judgment-class is the prior).
Every other component rides its existing routing unchanged. The stub
planner keeps the suite egress-free.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves** — no plan field that doesn't compile into behaviour,
  with the one spec-sanctioned exception named: the expected-artefact-shape field is
  explicitly non-executing annotation (plan-as-object's execution-bearing vs
  free-text-context split).
- **Flag, don't drop** — a degraded run says which legs failed and why; auto-resolved
  steer-points are flagged, never silent; the artefact's honesty labels (`text_basis`,
  coverage bases) ride through untouched.
- **Honest absence** — the plan states its assumptions rather than hiding thin context;
  a steering intent the grammar can't express is a recorded "not yet", never a silent
  approximation.
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md), not silent omissions.

## Stop conditions

Halt and escalate when: any approval gate above is hit beyond what
this contract records (schema beyond the approved
`orchestration_plan` table + minimal linkage — e.g. the
capability-run entity — deps, CI, public interfaces beyond the one
entrypoint); the composer or steer-point compile turns out to need a
directive surface that doesn't exist yet (that's the gradation seam
or boost-grammar v2 growing — gate it, don't build it silently);
scope would grow past this slice (narration, resume, section compile,
the LLM capability agent); or the turn/token budget is spent. Report
the blocker; don't push through.

## Acceptance checks

- `make verify` (okf-validate · test · typecheck · lint · build) —
  green, deterministic, zero-egress (stub planner; fixture defaults
  unchanged).
- Unit/integration tests pin: spine enforcement (no composed plan
  omits/reorders a spine leg) · fail-closed compile (unknown
  component/parameter/directive rejects — caught error, never a
  silent run) · approved-plan ↔ executed-config equivalence (the
  round-trip property, `plan.amended` included) · depth bundles
  compile only to existing directive surfaces · nudge re-derivation
  (each option yields a valid full plan + band) · steering: mode →
  pause-set compile; the deepening-selection triggers (fault-injected
  selection shapes); intent-vocabulary options compile to the
  declared grammar; adjustments touch only un-run legs; Unattended
  auto-resolution flagged + collated; abort leaves committed legs +
  an honestly-abandoned run · failure semantics (decision 8's three
  rules, fault-injected) · plan/steering events emitted in order ·
  runner per-component commit shape (a mid-chain failure leaves prior
  legs' committed state visible and the run honestly failed).
- The pinned live check (decision 10), evidenced in verification.md.

## Verification evidence expected

Command results; the live-check record (planner-review notes across
taxonomy intents, the composed-run trace: plan payload → composed
chain → steer-point firing + amendment → per-leg outcomes +
wall-clocks); diff summary; public-safety confirmation; known gaps +
deferred updates (including the gate adjudications and the spec
refinement recorded).

## Risk tier & review focus

**Tier 3** — new runtime-egress LLM surface (planner) + the product
path that drives every live component. Review focus: compile
fail-closed completeness (planner output and steering responses can
never smuggle execution past the registry — the plan is data, not
code) · spine-enforcement fidelity (ADR 0013 exactly, including
mandatory-attempt semantics) · failure-chaining honesty (no failed
run id ever feeds downstream; degrade vs fail boundaries per
decision 8) · steering honesty (substance never silent in any mode;
Unattended resolutions visibly pre-declared + flagged; adjustments
bounded to un-run legs) · prompt surface review (lead-authored
planner prompt: injection posture on user intent text, no promised
findings) · transaction-shape change (decision 7: per-component
commits vs the skeleton's single transaction — partial-state
visibility is by design, verify nothing reads it as complete) ·
spec-refinement fidelity (the Unattended text preserves the firm
principle's purpose) · scope creep (LLM capability agent, narration,
resume, section compile, boost v2, progress protocol all stay out).
