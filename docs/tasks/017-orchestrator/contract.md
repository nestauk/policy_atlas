# Task contract: 017-orchestrator

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** **APPROVED rev 2.4 · amended revs 2.5 (ack'd) · 2.6 (micro-clarification) · 2.7–2.9 (plan-gate user calls)** — contract approved (before
> planning): **2026-07-10 · Shabeer Rauf** (covering the gated set:
> runtime egress — the planner LLM surface; one CLI entrypoint; the
> `orchestration_plan` schema addition; the Unattended steering-mode
> spec refinement in principle — and ratifying the gate adjudications
> recorded in revs 2–2.4). Companions:
> [v2-wizard-study.md](v2-wizard-study.md) (rev 2.2c evidence) ·
> [orchestration-research-notes.md](orchestration-research-notes.md)
> (rev 2.4 evidence).
> Contract-stage adversarial review adjudicated rev 2.5 — 8/8
> adopted; the two flagged items (findings 1 + 7) **ack'd by the
> user**. **Plan approved (before implementation): 2026-07-10 ·
> Shabeer Rauf (plan rev 5)** · ADR:
> [0014](../../adr/0014-thin-v1-orchestrator.md) **Accepted**.
> **Design phase complete; build next (conversation B).**
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
> - **rev 2.9** (2026-07-10, user call at the plan 🛑, round 3 —
>   confirmed after the latency question was answered from measured
>   anchors: one-pass ≈ 1 min live (016: acquire 24 s + screen 36 s);
>   full deep episode ≈ 5.7 min live (015: 343 s)): search-effort
>   rungs re-cut — **rapid = non-agentic one-pass · standard = the
>   latency-optimised agentic loop (round cap 2, reformulate +
>   diversity arms, bounded budget; est. ~2.5–3.5 min) · deep = the
>   full loop**; "adaptive" dropped as uninterpretable; the runtime
>   thin-base hatch dissolves into plan-chosen composition (the
>   loop's stopping rule is the declared method at standard+; rapid
>   flags thinness honestly); scope gains the additive
>   `search_loop.py` constants row the 015 extensible table
>   pre-sanctioned; diagonals re-paired rapid×landscape ·
>   standard×standard · deep×deep.
> - **rev 2.8** (2026-07-10, user calls at the plan 🛑, round 2):
>   **(a) Search axis renamed and given three rungs** — "search
>   breadth (focused/broad)" → **search effort (rapid / adaptive /
>   deep)**: the deep agentic loop is targeting-heavy (query
>   reformulation), not merely broad, so effort is the honest axis
>   name; `adaptive` = the as-built thin-base escalation as the
>   middle rung (hatch armed), `rapid` disarms the hatch and flags
>   thinness honestly; 3×3 parity with analysis depth; diagonal
>   pairings rapid×landscape / adaptive×standard / deep×deep.
>   **(b) Demo extraction-timing prior corrected** — extraction is
>   parallel as-built (`ThreadPoolExecutor`, `MAX_CONCURRENT_EXTRACT
>   = 4`); the ~1.4 min/doc prior is a concurrency-4 measurement,
>   not serial-demo noise; pool size is a recorded depth-seam tuning
>   lever; standard budget stays 10 (user call).
> - **rev 2.7** (2026-07-10, user calls at the plan 🛑 — three):
>   **(a) Gradation split into two independent axes** — search
>   breadth (evidence-base size) × analysis depth (component set +
>   budgets) — enacting capability.md's breadth/depth independence;
>   named bundles = the diagonal, off-diagonal composition
>   (narrow-and-deep · broad-and-shallow horizon scan) now
>   expressible; user-facing exposure unchanged (proposal + band +
>   one nudge over both axes, per-axis movement via conversation/
>   edits/check-ins). **(b) Time-band targets pinned** (lighter
>   ≤ ~10 min · standard ~15–30 · deeper ~90) with the
>   displayed-band-is-measured discipline; standard selection budget
>   dropped 12 → 10 toward the target. **(c) Terminology aligned to
>   repo vocabulary** — "leg" (this contract's coinage) swept to
>   "component" throughout contract/plan/rubric.
> - **rev 2.6** (2026-07-10, micro-clarification from the PLAN-stage
>   adversarial review, finding 4): decision 11's developer-side
>   roll-up precised — wall-clocks in the end-of-run summary log;
>   per-component tokens via Langfuse (usage is trace-only as-built); the
>   single-line aggregate is a recorded seam. No settled decision
>   changed.
> - **rev 2.5** (2026-07-10, contract-stage adversarial review
>   adjudicated — Codex, 8 findings: 2 blocker · 5 major · 1 minor;
>   **8/8 adopted**, all verified against as-built code before
>   adoption): **BLOCKER 1** — the rev-2.4a sequencing invariant
>   overclaimed ("only deterministic surfaces" post-acquire is false
>   against ADR 0010's section proposal + synthesise's section loop);
>   narrowed to the plan-authorship property actually meant: no LLM
>   surface authors or amends orchestration-plan content once acquire
>   begins. **BLOCKER 2** — pre-run plan events don't fit the event
>   substrate (`event_log.run_id` non-null, composite FK to `runs` —
>   verified); plan lifecycle made **table-first** (plan rows are the
>   audit trail; `plan.compiled` events gain plan id + version; no
>   schema relaxation, no synthetic planning run). **3** — screening
>   criteria compile pinned to the screen's intent INPUT at the screen
>   boundary, never the shared `evidence_scope.intent` (search and
>   synthesise read it too). **4** — scope-filter grammar precised
>   (two-level shared/openalex/overton blocks; `publisher_country`
>   Overton-only; backend enum exactly `academic_only`/
>   `grey_lit_only`/`both`; stale deferred.md spelling fixed in
>   flow-back). **5** — steer-point options mapped to the real
>   directive grammar (`priority_strata` for clusters,
>   `weight_emphasis` quality/screen_confidence for strongest/most-
>   relevant — richer than the rev-2.2f guess). **6** — Unattended
>   defaults restricted to pre-declarable rules per steer-point class,
>   never runtime-data-specific answers. **7** — the recorded
>   harness gap (failure event dies in an aborted transaction) folded
>   in as a rider on the runner's transaction ownership: rollback
>   first, failure event on a fresh transaction (escape valve back to
>   deferred if non-trivial). **8** — token/cost roll-up carrier
>   pinned developer-log-only (no `runs` summary column exists or is
>   approved). Findings 1 + 7 flagged for user ack (claim narrowing;
>   small scope rider).
> - **rev 2.4** (2026-07-10, research pass — /last30days + web research
>   on agent planning/orchestration, user-directed; findings + full
>   adjudication in
>   [orchestration-research-notes.md](orchestration-research-notes.md)):
>   **(a) Sequencing invariant pinned** (decision 5): the one LLM
>   planning surface completes before the chain touches untrusted
>   content; mid-run amendments are user-authored and deterministically
>   compiled — corpus text has no machine path into plan content (the
>   plan-then-execute security literature's injection-boundary
>   property, stated so the build can't accidentally break it; joins
>   review focus + rubric). **(b) Resume-seam design note** (decision
>   7): the deferred resume engine's requirement recorded — checkpoint
>   state serialization + an idempotency key persisted before any
>   interruption. **(c) Per-component token/cost roll-up** joins wall-clocks
>   in the run record (decision 11) — **developer-side only** (user
>   call): users see time bands, never tokens or cost; cost data may
>   inform the bands invisibly. Confirmations recorded, not
>   folded: unified intent-planning taxonomy (our planner's shape),
>   static/dynamic interrupt ↔ mode-compile/steer-point mapping,
>   simplest-pattern-first + the review-gate middle tier (validate the
>   thin deterministic runner + steering posture), plan-as-data
>   convergence (AgentCore/Kastor/plan-freezing).
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
>   `plan.py`/`skeleton.py`/`search_loop.py` seams, 016's per-component
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
- Failure semantics productionised (decision 8): spine-component failure
  fails the run honestly; discretionary-component failure degrades with
  flags; bounded retry for LLM-bearing components.
- Plan persistence (decision 2, rev 2.2; table-first rev 2.5): the
  minimal `orchestration_plan` table (the one approved schema
  addition) — status transitions + immutable version rows are the
  plan's audit trail; per-component `plan.compiled` events carry
  plan id + version.
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
- 016 `verification.md` per-component wall-clocks (feeds the gradation bands
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
- `search_loop.py` *(rev 2.9)*: one **additive** `standard` row in
  the extensible per-depth constants table + a loop arm-selection
  parameter for the trimmed variant — the extension the 015 design
  pre-sanctioned; no logic change; `parse_search_directive` admits
  the new depth value by construction.
- Event vocabulary: `plan.compiled` payloads gain plan id + version;
  steering-resolution events ride the run context they occur in
  (event payloads, zero-schema — the 001 event-log substrate; plan
  lifecycle itself is table-first, rev 2.5).
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
   **scope constraints** *(rev 2.1b; grammar precised rev 2.5,
   adversarial finding 4)* — recency window · geography — compiled
   into the as-built **two-level** search filter grammar: a `filters`
   object with `shared` / `openalex` / `overton` blocks
   (`search_loop.py`), recency via shared
   `published_after`/`published_before`, geography via Overton
   `publisher_country` (**Overton-only as-built** — whether OpenAlex
   carries a usable geography key is a plan-time check, and the plan
   states the asymmetry honestly if not); the backend-scope enum is
   exactly `plan.py`'s `academic_only`/`grey_lit_only`/`both` (the
   deferred.md variant spelling is stale — fix rides this slice's
   flow-back). Each **defaulted visibly**
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
   field; **v1 compile pinned precisely (rev 2.5, adversarial finding
   3): criteria compose into the screen's intent INPUT at the screen
   boundary — never written into the shared `evidence_scope.intent`**
   (which search generation and synthesise also read; as-built,
   screen/search/synthesis all consume the one intent string, so
   composing criteria into the scope row would leak them into query
   generation and sectioning). The screen prompt template is
   unchanged; its intent input grows. If plan-time design finds this
   needs more than input composition, criteria consumption defers to
   the 014 structured-directive seam and the field ships
   plan-visible-only with that stated honestly. The field re-targets
   to the structured screening directive when that seam lands
   (unlike V2, the criteria are never invisible: they sit in the
   plan, not buried in a rubric) · depth
   gradation (decision 4's bundle) · discretionary component set
   (decision 4's intent-fit × gradation selection, visible in the
   plan) · grouping facet ·
   **steering mode** (decision 6) · **the anticipated steer-points'
   default resolutions** (visible plan content — what Unattended
   auto-applies and every mode falls back to; rev 2b) · **the declared
   method note** *(was "declared hatch", rev 2f; dissolved rev 2.9)*:
   escalation is plan-chosen via the effort axis — the agentic loop's
   stopping rule is the declared sanctioned method at `standard`+;
   at `rapid` thinness flags honestly; no armed runtime hatch in v1 ·
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
   2.1c; lifecycle made table-first rev 2.5, adversarial finding 2)*:
   a minimal **`orchestration_plan` table** — the plan is a
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
   **The plan lifecycle is table-first** *(rev 2.5)*: as-built,
   `event_log.run_id` is non-null and composite-FK-bound to `runs`
   (verified — `schema.py`), so pre-run `plan.proposed`/`plan.approved`
   events cannot exist on this substrate without a schema relaxation
   or a synthetic planning-run row — neither is taken. The plan rows'
   status transitions + version rows + attribution ARE the plan's
   audit trail (the "first decision-log entry" is satisfied by the
   decision-log projection reading plan rows alongside events);
   steering amendments persist as new plan version rows; execution-
   time `plan.compiled` events gain plan id + version so every run
   back-references the plan version it executed. What stays
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
   omits or reorders a spine component; an unknown component or parameter
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
   - **Gradation — two independent axes** *(rev 2.7, user call at
     the plan gate; axis renamed + three-rung rev 2.8 — "broad" was a
     misnomer: the as-built deep loop raises coverage through
     iterative TARGETING — reformulation over judged exemplars,
     snowball, suggest arms — as much as volume, so the axis measures
     acquisition effort, not width; enacts the spec's
     breadth/depth-independence line and instantiates the deferred
     depth-spectrum seam's v1 rungs; rungs re-cut rev 2.9, user
     call — "adaptive" was uninterpretable, and the honest split is
     non-agentic vs two loop variants)*: **search effort**
     (`rapid` — the non-agentic one-pass multi-query fan-out, rapid
     caps, thinness flagged honestly — no runtime escalation ·
     `standard` — the **latency-optimised agentic loop**: round cap
     2, trimmed arms (reformulate + diversity reserve), bounded
     episode budget — a new **additive row in the extensible
     per-depth constants table** the 015 design pre-sanctioned,
     values plan-pinned; measured anchors put the episode at
     ~2.5–3.5 min vs ~1 min one-pass and ~6 min full loop ·
     `deep` — the full agentic loop, all arms, round cap 3, deep
     caps) × **analysis depth** (`landscape` · `standard`
     · `deep` — discretionary components, stage-2 screen, selection
     budget, facet). Escalation thereby stops being a runtime escape
     hatch and becomes **plan-chosen composition**: the loop's own
     stopping rule (spec'd + as-built) is the declared sanctioned
     method at `standard`+; v1 ships no armed runtime hatch. Named
     pairings survive as authoring convenience
     (the lighter/standard/deeper diagonal = rapid×landscape ·
     standard×standard · deep×deep — never a user-facing dial), and
     the planner composes **off-diagonal** shapes where intent
     warrants: narrow-and-deep (rapid search, full extraction) and
     the horizon scan (deep search, landscape only). User-facing
     exposure unchanged: the concrete proposal + time band; the
     single nudge re-derives both axes coherently; either axis moves
     individually via conversation, plan edits, or bounded check-in
     adjustments. Pinned now: **the
   default proposal is a middle gradation**, anchored to concrete
   numbers + a time band; the nudge vocabulary is fixed as
   **lighter / as proposed / deeper** (constant across all projects
   and runs — it lives in one prompt artifact and the plan schema);
   **every nudge option is presented with its own re-derived concrete
   proposal + time band**, so the choice is always
   between anchored proposals, never labels. **Time-band targets**
   *(user call, rev 2.7)*: lighter ≤ ~10 min · standard ~15–30 min ·
   deeper ~90 min — targets, not claims: the **displayed** band
   derives from measured wall-clocks (016 + build live check), never
   the target; target-vs-measured divergence is a recorded
   depth-seam calibration item (tuning constants toward targets is
   018/eval work, never silent band inflation). Conversational effort
   signals ("quick first look") absorb into the proposal — expected
   rare; the anchored default carries the common case. v1 compile
   targets, all existing: search depth (`rapid`/`deep`, 015
   `DEPTH_CONSTANTS`) · stage-2 screen on/off · characterise on/off ·
   deep chain on/off · selection budget · grouping facet.
   Deliberately **not** compiled in v1: synthesis section directives,
   per-depth fetch budgets, synthesis caps, parser tiers — recorded
   levers of the gradation seam, which this decision opens but does
   not finish. Exact bundle table plan-pinned, informed by 016's
   per-component wall-clocks.

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
   registry). **Sequencing invariant** *(rev 2.4a; narrowed rev 2.5,
   adversarial finding 1 — the 2.4a wording claimed "only
   deterministic surfaces" for the whole run, which is false against
   ADR 0010's bounded section-proposal call and synthesise's section
   loop, both prompt-bearing over corpus substrate post-acquisition)*:
   **no LLM surface authors or amends orchestration-plan content once
   acquire begins.** The planner completes pre-acquisition; every
   mid-run plan amendment is user-authored input compiled fail-closed
   against the declared grammar; check-in content is deterministic
   renders. The capability-internal prompt surfaces that legitimately
   read corpus text post-acquisition (screen · classify · characterise
   · extract · group · synthesise, including its section proposal) are
   unchanged by this slice and write component/artefact state under
   their own verification machinery — never plan state. Corpus text
   therefore has no machine path into **plan content**, which is the
   injection-boundary property the plan-then-execute security
   literature names. Honesty rules
   carried from the product voice: never
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
     on the run record. Defaults are **pre-declarable rules per
     steer-point class, never runtime-data-specific answers** *(rev
     2.5, adversarial finding 6 — trigger data like cluster names
     exists only after `select` runs)*: e.g. "on any
     deepening-selection trigger: proceed as proposed and flag"; the
     user-nominated-cluster trigger evaluates against nominations
     already in the plan (must-includes / priority clusters), so
     every rule is checkable at approval time. Substance is thereby honoured in every mode:
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
     v1). **Options speak user intents, mapping pinned to the
     as-built grammar** *(rev 2f, user call; mapping precised rev
     2.5, adversarial finding 5 — `select.py`'s directive keys are
     `budget` · `must_include_ids` · `boosts` · `weight_emphasis` ·
     `priority_strata`, weight signals `recency` · `quality` ·
     `text_basis` · `screen_confidence` · `origin`)*: deepen named
     clusters → `priority_strata` (+ `must_include_ids` for named
     documents) · "just the strongest evidence" → `weight_emphasis`
     on `quality` · "most relevant to my question" →
     `weight_emphasis` on `screen_confidence` (named honestly as the
     relevance proxy — the closest as-built signal) · adjust budget →
     `budget` · as proposed → no directive change. Exact emphasis
     values plan-pinned; an intent the grammar cannot express is an
     honest "not yet" (recorded seam), never a silent approximation.
     After adjustment, `select` re-runs cheaply; `extract` has not
     yet spent.
   - **Bounded steering application, everywhere**: at any pause the
     user may continue · adjust not-yet-run components' directives within
     the declared grammar (incl. the remaining-components nudge and a mode
     change) · **stop the run** (clean abort: committed components stand,
     run honestly marked abandoned, no artefact — synthesise is the
     minting terminus). Never re-runs completed components, never free-text
     replanning. Every steering response persists as a new
     user-attributed plan version row (the spec's "human substance
     enters honestly in provenance"; table-first, rev 2.5).
   - **Minimal/Unattended collation**: flagged events (degraded components,
     hatch firings, retries, auto-resolutions, coverage caveats)
     collate into an end-of-run review.

7. **Durability: per-component commits, no resume engine —
   adjudicated at this gate** *(rev 2, user-confirmed)*. Each component
   commits as it lands (the durability spec's block-boundary-commit
   direction; also what a future read surface needs to watch a run);
   a failed run reports honestly and is re-run from the top. The
   long-deep-run fragility this accepts is recorded at the durability
   seam — the seam note now also carries the resume-engine design
   requirement the 2026 durable-execution consensus supplies *(rev
   2.4b)*: state serialized at the checkpoint, and an **idempotency
   key persisted before any interruption** so a resumed action runs
   exactly once; building the engine pre-demo is overreach. This changes the
   run's transaction shape from `skeleton.py`'s single
   `engine.begin()` — the single-active-writer-per-project invariant
   is unchanged (serial runner), and partial state on failure is
   visible-by-design (status/events say what completed); the demo
   drove per-stage transactions live without incident.

8. **Failure semantics (the RETRO priors, productionised as code
   rules).** A failed stage never feeds its run id downstream: stages
   chain only off successful predecessors. **Spine-component failure fails
   the run honestly** (evented, run status failed, no downstream
   components — a run that cannot screen has nothing true to synthesise).
   **Discretionary-component failure degrades**: the component's failure is
   evented + flagged, downstream discretionary components that require it
   are skipped with reason, and synthesise composes over the **entire
   successful upstream chain** — the runner passes the deepest
   *successful* reference and the rest resolves transitively, so only
   the failed component and its dependents drop (ADR 0010's
   every-upstream-reference-optional design absorbs this by
   construction; rev 2.1d). LLM-bearing components get **one
   bounded retry** before failing (which components, plan-pinned; the
   characterise twice-in-a-row wobble is the motivating prior). All
   outcomes reason-coded in events; nothing silently absorbed —
   **including DB-error failures** *(rev 2.5, adversarial finding 7,
   folding the recorded repo-wide harness gap into this slice)*: the
   deferred ledger records that a `component.failed` append dies
   inside an aborted transaction (the event write itself fails and no
   audit record survives); since decision 7 makes the runner own
   per-component transactions anyway, the runner's failure path
   **rolls back first and appends the failure event on a fresh
   transaction** — discharging the deferred.md harness entry. If
   plan-time design finds this non-trivial, it returns to deferred
   with the failure-semantics claim narrowed to non-DB-aborting
   failures (escape valve, must not grow the slice).

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
    as a new plan version row. Recorded: the composed chain vs the
    approved plan (provably the same — the audit point), per-component
    wall-clocks, failure/degrade behaviour if any component wobbles, the
    minted artefact's honesty labels intact.
    (c) **failure-semantics + Unattended evidence at test level**
    (fault-injected runner tests per decision 8; a scripted
    Unattended run auto-resolving a fired steer-point with the
    resolution flagged + collated) — no live fault probe.
    Cost: one planner conversation set + one modest live chain —
    low single-digit dollars.

11. **Telemetry: plan + steering events + existing component events;
    no new protocol.** The plan lifecycle is auditable table-first
    (rev 2.5): `orchestration_plan` status transitions + version rows,
    joined to execution via per-component `plan.compiled` events
    carrying plan id + version, with steering-resolution events on
    their run context. Per-component wall-clocks are emitted in an end-of-run
    structured-log summary; per-component token usage is read in Langfuse,
    where the existing telemetry already records it per call *(rev
    2.4c; carrier pinned rev 2.5, adversarial finding 8; split
    precised rev 2.6 — plan-stage review, finding 4: as-built
    backends discard `_usage` after tracing, so a single-line token
    aggregate would need a usage-return refactor — recorded seam, not
    built; both surfaces are developer-side, no durable carrier, no
    user exposure)*.
    "Token bleed" is the season's named orchestration cost failure
    mode; the roll-up feeds the depth seam's bands and the plan's
    time-band honesty at near-zero cost. **The roll-up is developer-side telemetry only**
    *(user call, 2026-07-10)*: no token count or monetary cost ever
    reaches a user-facing surface — the plan and check-ins speak in
    **time bands**, which cost data may inform invisibly; the
    roll-up lives in the run record/logs for the depth seam, evals
    and ops. The user-grade
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
- **Flag, don't drop** — a degraded run says which components failed and why; auto-resolved
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
  omits/reorders a spine component) · fail-closed compile (unknown
  component/parameter/directive rejects — caught error, never a
  silent run) · approved-plan ↔ executed-config equivalence (the
  round-trip property, amendment version rows included) · depth bundles
  compile only to existing directive surfaces · nudge re-derivation
  (each option yields a valid full plan + band) · steering: mode →
  pause-set compile; the deepening-selection triggers (fault-injected
  selection shapes); intent-vocabulary options compile to the
  declared grammar; adjustments touch only un-run components; Unattended
  auto-resolution flagged + collated; abort leaves committed components +
  an honestly-abandoned run · failure semantics (decision 8's three
  rules, fault-injected) · plan/steering events emitted in order ·
  runner per-component commit shape (a mid-chain failure leaves prior
  components' committed state visible and the run honestly failed).
- The pinned live check (decision 10), evidenced in verification.md.

## Verification evidence expected

Command results; the live-check record (planner-review notes across
taxonomy intents, the composed-run trace: plan payload → composed
chain → steer-point firing + amendment → per-component outcomes +
wall-clocks); diff summary; public-safety confirmation; known gaps +
deferred updates (including the gate adjudications and the spec
refinement recorded).

## Risk tier & review focus

**Tier 3** — new runtime-egress LLM surface (planner) + the product
path that drives every live component. Review focus: compile
fail-closed completeness (planner output and steering responses can
never smuggle execution past the registry — the plan is data, not
code) · the rev-2.4a sequencing invariant (no prompt-bearing
planning surface runs once acquire begins; corpus text has no
machine path into plan content) · spine-enforcement fidelity (ADR
0013 exactly, including
mandatory-attempt semantics) · failure-chaining honesty (no failed
run id ever feeds downstream; degrade vs fail boundaries per
decision 8) · steering honesty (substance never silent in any mode;
Unattended resolutions visibly pre-declared + flagged; adjustments
bounded to un-run components) · prompt surface review (lead-authored
planner prompt: injection posture on user intent text, no promised
findings) · transaction-shape change (decision 7: per-component
commits vs the skeleton's single transaction — partial-state
visibility is by design, verify nothing reads it as complete) ·
spec-refinement fidelity (the Unattended text preserves the firm
principle's purpose) · scope creep (LLM capability agent, narration,
resume, section compile, boost v2, progress protocol all stay out).
