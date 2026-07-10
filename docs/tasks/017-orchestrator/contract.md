# Task contract: 017-orchestrator

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** **drafted rev 1** — awaiting contract 🛑.
> Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ ·
> ADR: expected (the v1 orchestrator carve — which spec cluster ships
> now vs stays deferred — is a design decision; drafted at step 4).
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
017 ships the **thin v1 orchestrator** — three parts:

1. **Planner** (the one new LLM surface, prompt lead-authored): takes
   the user's intent conversationally, refines it into a sharp
   evidence question, proposes a depth-graded orchestration plan, and
   supports the relative **lighter / as-proposed / deeper** nudge.
2. **Composer** (deterministic): compiles an approved orchestration
   plan into a chain composition — fail-closed against the component
   registry, always containing the ADR 0013 mandatory spine, with
   discretionary components selected per the depth gradation.
3. **Driver** (serial): executes the composed chain over the existing
   components in topological order — per-component commits, run
   references chaining only off successful predecessors, synthesise
   taking the deepest successful reference.

Thin v1 means exactly this carve of the spec cluster: forecast →
approval → compile → execute, plus the depth nudge and spine
composition. Steering modes, durable resume, check-in mediation,
section-directive compile and the capability-run entity are named
seams, not silent omissions (decisions 6, 10; Out of scope).

## Deliverable

PR landing:

- New orchestrator module(s) (final naming plan-designed): the
  planner backend + its lead-authored prompt, the orchestration-plan
  model + composer, the chain driver, and one new CLI entrypoint
  (intent in → planner conversation → plan approval → run → artefact;
  the product path).
- The depth-gradation compile (decision 4): graded bundles →
  per-component directives over **existing** directive surfaces only.
- Failure semantics productionised (decision 7): spine-leg failure
  fails the run honestly; discretionary-leg failure degrades with
  flags; bounded retry for LLM-bearing legs.
- Plan persistence as events (decision 2): `plan.proposed` /
  `plan.approved` on the event log — the plan is the first
  decision-log entry. **No schema change.**
- Stub planner backend; `make verify` stays green, deterministic and
  egress-free.
- Tests + `verification.md` with the pinned live check (decision 9).
- Spec flow-back only if building shows spec text wrong (§ Spec
  refinement route); ADR for the v1 carve; `deferred.md` + knowledge
  updates.

## Read first

- [ADR 0013 — the mandatory EB spine](../../adr/0013-mandatory-eb-spine.md)
  — the one authoritative chain rule the composer compiles against
- [plan-as-object](../../specs/system/plan-as-object.md) — plan vs
  config, robust-compile-by-construction, forecast vs commit,
  thoroughness as a relative nudge, enough-context-to-propose
- [execution-orchestration](../../specs/system/execution-orchestration.md)
  — plan-time authority, steering modes + routing rule, durability;
  what v1 deliberately does not build (decision 6 names the posture)
- [EB capability.md](../../specs/capabilities/evidence-base/capability.md)
  — the component skeleton, "components are a registry the plan
  selects from", the orchestrator-shapes/EB-composes split
- [EB components.md](../../specs/capabilities/evidence-base/components.md)
  — per-component directive surfaces the composer authors
- As-built: `plan.py` (component config + fail-closed registry — the
  commit layer, reused), `skeleton.py` (the hand-sequenced chain this
  slice productionises: directive read-modify-write pattern, deep-round
  loop driving, run-reference threading), `search_loop.py`
  (`DEPTH_CONSTANTS` — the depth compile target), `harness.py`
  (`run_harness`, the one-component dispatcher)
- 016 `verification.md` per-leg wall-clocks (feeds the gradation bands)
- `demo/RETRO.md` + `demo/server/orchestrator.py` + `demo/server/driver.py`
  (branch `demo-live-run`) — **anecdotal prior only**: which live
  chain-driver hazards are real (characterise wobble → retry-once,
  failed stages must never feed run ids downstream, plan-shape/
  contract divergence as the recurring failure class)

## Scope / Out of scope

**In:**

- New orchestrator module(s) + CLI entrypoint + tests.
- The planner prompt surface (lead-authored) + stub backend.
- Orchestration-plan model, composer, depth-bundle table, driver.
- `plan.py`: additive extension only if composition needs it (the
  component config and registry semantics are reused, not reshaped).
- Event vocabulary: `plan.proposed` / `plan.approved` additions
  (event payloads, zero-schema — the 001 event-log substrate).
- `skeleton.py`: untouched except removals the driver makes
  redundant are **not** taken — it stays the zero-egress walking
  skeleton smoke.
- Spec flow-back / ADR / `deferred.md` / knowledge updates.

**Out (stay deferred — `docs/deferred.md`):**

- Steering modes beyond the decision-6 posture: no mid-run check-in
  surface, no `clarify`/`escalate` parking, no
  `agent_judgement_routed` events, no narration voice (the demo's
  second posture) — these arrive with the web-app/workspace surfaces.
- Durable resume engine: no block-boundary resume, no tool-result
  memoisation, no parked branches (decision 6b accepts re-run-from-
  the-top for 017/018).
- Section-directive compile: the fail-closed `context["synthesis"]`
  directive keeps **nothing compiling into it** (013 seam);
  synthesise keeps intent-led sectioning (decision 4).
- Retrieval-boost grammar v2 (decision 8 — gate item).
- Capability-run entity + multi-facet fan-in (schema-gated seams;
  the driver hand-sequences as the capability sub-agent's stand-in,
  stated honestly).
- Plan-field ↔ chat-turn provenance: v1 persists the approved plan
  object, not per-field conversation back-references (recorded seam);
  the planning transcript itself is ephemeral CLI state in v1.
- Co-pilot Q&A, source/evidence policy (both faces), time/cost
  estimate model (coarse band only), component-progress protocol,
  front-end/rendering + conclusion block (018), eval formalisation,
  branch parallelism.

## Decisions

1. **Three parts behind one entrypoint; skeleton untouched.** Planner
   (LLM, conversational, structured output) · composer (pure
   function: orchestration plan → ordered component configs +
   directive writes) · driver (serial executor over `run_harness`).
   New modules — `skeleton.py` stays the deterministic zero-egress
   smoke harness and is not the product path; the de-authorised demo
   driver stays on its throwaway branch. The existing component
   config (`plan.py`) is the commit layer, reused as-is; any
   extension is additive and plan-designed.

2. **The orchestration plan is a structured selection, persisted as
   events — no schema.** A pydantic model over: refined question ·
   scoping notes (user-expressed only, never invented) · backend
   scope (existing `search_backend_scope` vocabulary) · depth
   gradation (decision 4's bundle) · discretionary component set
   (derived from the bundle, visible in the plan) · grouping facet ·
   assumptions/open guesses (first-class, cheaply correctable —
   thin-context plans are visibly thin) · a coarse time band derived
   from the 016 wall-clocks (the estimate model stays deferred).
   Robust compile by construction: the plan can only reference what
   the registry declares; a plan that doesn't validate is a caught
   error, never a silent run. Persistence: `plan.proposed` and
   `plan.approved` events carry the full plan payload — the plan is
   the first decision-log entry; per-component `plan.compiled`
   events continue unchanged. The capability-run entity (a durable
   row spanning components) stays deferred; the run's identity in v1
   is the project + scope + its event trail.

3. **Composition: the ADR 0013 spine is enforced by construction and
   test-pinned.** Every composed chain executes acquire(`search`) →
   screen → classify → appraise → ingest(fetch) → synthesise in
   spine order; characterise · stage-2 screen · select → extract →
   group are selected per gradation; structural dependencies ride
   the existing fail-closed registry (select requires a
   characterisation reference, extract a selection, group an
   extraction; synthesise takes the deepest successful reference).
   Tests pin: no composable plan omits or reorders a spine leg; an
   unknown component or parameter rejects at validation.

4. **Depth gradation: a thin slice of the tool-wide seam, compiling
   only to existing directive surfaces.** Graded bundles are an
   orchestrator-authoring convenience (plan-as-object: named bundles
   survive as authoring convenience, **never a user-facing absolute
   dial**); the user-facing controls are the concrete proposal + the
   relative lighter/as-proposed/deeper nudge, which re-derives the
   bundle in one move. v1 compile targets, all existing: search depth
   (`rapid`/`deep`, 015 `DEPTH_CONSTANTS`) · stage-2 screen on/off ·
   characterise on/off · deep chain on/off · selection budget ·
   grouping facet. Deliberately **not** compiled in v1: synthesis
   section directives (013 surface, nothing compiles into it yet),
   per-depth fetch budgets, synthesis caps, parser tiers — all
   recorded levers of the gradation seam, which this decision opens
   but does not finish. Exact bundle table plan-pinned, informed by
   016's per-leg wall-clocks.

5. **The planner is the slice's one new prompt surface — lead-
   authored, judgment-class.** Conversational: refines intent into an
   evidence question, asks **only when a missing piece would change
   the plan's shape** (enough-context-to-propose), updates a visible
   plan draft each turn, sets a ready flag; proposal anchored to
   concrete numbers + the coarse time band, never an abstract depth
   label. Structured output validated fail-closed (pydantic; the
   planner cannot smuggle components or parameters past the
   registry). Honesty rules carried from the product voice: never
   promise findings, never state what the evidence says, assumptions
   surfaced not buried. The demo planner prompt is an anecdotal
   prior; this prompt is written fresh by the lead. Model:
   judgment-class OpenAI (the demo observed planning/synthesis need
   it; exact model id plan-pinned). Suite runs a stub planner —
   zero-egress default unchanged.

6. **Steering/durability posture ❓ GATE — recommendation below,
   user adjudicates at this 🛑.**
   (a) *Steering:* v1 is **plan-approval-gated, then
   run-to-completion** — the up-front forecast/shape approval that
   every steering mode guarantees is the one human gate; no mid-run
   check-ins exist because no mediation surface exists yet (CLI, no
   thread). Stated honestly: the routing rule's substance-escalation
   guarantee is **not yet reachable at runtime** in v1 — nothing can
   pause mid-run — so v1 must not claim a steering mode; the plan
   records `steering: none (v1 — plan-gated only)` rather than
   borrowing "Minimal"'s name without its substance guarantee. The
   modes + routing rule arrive with the check-in surface (web-app
   cluster).
   (b) *Durability:* per-component transactions — each leg commits as
   it lands (the durability spec's block-boundary-commit direction;
   also what lets a future read surface watch a run) — but **no
   resume engine**: a failed run reports honestly and is re-run from
   the top. The 95-minute deep-run fragility this accepts is recorded
   at the durability seam; building the engine pre-demo is overreach.
   Note this changes the run's transaction shape from `skeleton.py`'s
   single `engine.begin()` — the single-active-writer-per-project
   invariant is unchanged (serial driver), and partial state on
   failure is visible-by-design (status/events say what completed);
   the demo drove per-stage transactions live without incident.

7. **Failure semantics (the RETRO priors, productionised as code
   rules).** A failed stage never feeds its run id downstream: stages
   chain only off successful predecessors. **Spine-leg failure fails
   the run honestly** (evented, run status failed, no downstream
   legs — a run that cannot screen has nothing true to synthesise).
   **Discretionary-leg failure degrades**: the leg's failure is
   evented + flagged, downstream discretionary legs that require it
   are skipped with reason, and synthesise runs on the deepest
   successful reference (ADR 0010's every-upstream-reference-optional
   design absorbs this by construction). LLM-bearing legs get **one
   bounded retry** before failing (which legs, plan-pinned; the
   characterise twice-in-a-row wobble is the motivating prior). All
   outcomes reason-coded in events; nothing silently absorbed.

8. **Retrieval-boost grammar v2 ❓ GATE — recommendation: does NOT
   ride 017.** `deferred.md` pre-registered it "before 017 or
   alongside it"; adjudicate here. Recommendation: 017 composes with
   the **v1 grammar as-built** (selection budget/boosts/must-include;
   grouping facet) — sufficient for plan composition and the demo;
   v2 (tag-based retrieval scoping + the screen-confidence clamped
   multiplier, grammar already pre-decided) is a 013-surface,
   eval-sensitive change that lands via its own gate with eval
   coverage. Adjudication recorded in `deferred.md` either way.

9. **Live-check scope pin** (contract-time, per failure-log
   2026-07-08): changed surfaces + one cheap full-chain smoke —
   (a) **planner surface**: 5–7 intents sampled across the V2
   question-taxonomy categories → proposed plans lead-reviewed for
   shape (sharp question, honest assumptions, sane gradation +
   composition, ask-only-on-shape behaviour); planner conversations
   only, **no chains run**; at least one conversation exercises the
   lighter/deeper nudge and shows the whole plan re-derived.
   (b) **one composed end-to-end run**: a real Nesta-mission
   question through the product path — planner → approval → composer
   → driver → artefact — at a **modest gradation** (deep enough to
   exercise discretionary composition, bounded corpus; the deep
   dress rehearsal is explicitly 018's). Recorded: the composed
   chain vs the approved plan (provably the same — the audit point),
   per-leg wall-clocks, failure/degrade behaviour if any leg
   wobbles, the minted artefact's honesty labels intact.
   (c) **failure-semantics evidence at test level** (fault-injected
   driver tests: spine-leg fail → run fail; discretionary fail →
   degrade + deepest-successful synthesise) — no live fault probe.
   Cost: one planner conversation set + one modest live chain —
   low single-digit dollars.

10. **Telemetry: plan events + existing component events; no new
    protocol.** The plan lifecycle is auditable from the event log
    (`plan.proposed` → `plan.approved` → per-component
    `plan.compiled` → component events). The user-grade
    component-progress protocol stays a recorded seam (016
    precedent); the CLI surfaces the existing structured logs.

## Constraints & approval gates

- **Runtime egress** (gated, rides this slice): the planner LLM call
  — one new lead-authored prompt surface reaching the model provider
  with user intent text. Approved at this contract's 🛑. All other
  egress (search backends, fetcher, component LLM calls) is
  previously approved and rides unchanged.
- **Schema**: none. Plan persistence is event-payload only
  (zero-schema by the 001 event-log design). Any schema need — the
  capability-run entity, a plan table — is a **stop condition**.
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
  **No other prompt text changes ride this slice** (the
  prompt-refine loop is 018's contract-pinned activity; the
  grounding-judge surface stays off-limits per the 013 pin).

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
- **Model only what behaves** — no plan field that doesn't compile into behaviour
  (free-text annotation is explicitly non-executing context, per spec).
- **Flag, don't drop** — a degraded run says which legs failed and why; the artefact's
  honesty labels (`text_basis`, coverage bases) ride through untouched.
- **Honest absence** — v1 claims no steering mode it cannot honour (decision 6a);
  the plan states its assumptions rather than hiding thin context.
- Leave deferred seams as seams in [docs/deferred.md](../../deferred.md), not silent omissions.

## Stop conditions

Halt and escalate when: any approval gate above is hit beyond what
this contract records (schema — including a plan table or
capability-run entity — deps, CI, public interfaces beyond the one
entrypoint); the composer turns out to need a directive surface that
doesn't exist yet (that's the gradation seam growing — gate it,
don't build it silently); scope would grow past this slice (check-in
mediation, resume, section compile, narration); or the turn/token
budget is spent. Report the blocker; don't push through.

## Acceptance checks

- `make verify` (okf-validate · test · typecheck · lint · build) —
  green, deterministic, zero-egress (stub planner; fixture defaults
  unchanged).
- Unit/integration tests pin: spine enforcement (no composed plan
  omits/reorders a spine leg) · fail-closed compile (unknown
  component/parameter/directive rejects — caught error, never a
  silent run) · approved-plan ↔ executed-config equivalence (the
  round-trip property) · depth bundles compile only to existing
  directive surfaces · failure semantics (decision 7's three rules,
  fault-injected) · plan events emitted in order · driver
  per-component commit shape (a mid-chain failure leaves prior legs'
  committed state visible and the run honestly failed).
- The pinned live check (decision 9), evidenced in verification.md.

## Verification evidence expected

Command results; the live-check record (planner-review notes across
taxonomy intents, the composed-run trace: plan payload → composed
chain → per-leg outcomes + wall-clocks); diff summary; public-safety
confirmation; known gaps + deferred updates (including the two gate
adjudications recorded).

## Risk tier & review focus

**Tier 3** — new runtime-egress LLM surface (planner) + the product
path that drives every live component. Review focus: compile
fail-closed completeness (planner output can never smuggle execution
past the registry — the plan is data, not code) · spine-enforcement
fidelity (ADR 0013 exactly, including mandatory-attempt semantics) ·
failure-chaining honesty (no failed run id ever feeds downstream;
degrade vs fail boundaries per decision 7) · posture honesty
(decision 6a's no-claimed-steering-mode; no resume implied) · prompt
surface review (lead-authored planner prompt: injection posture on
user intent text, no promised findings) · transaction-shape change
(decision 6b: per-component commits vs the skeleton's single
transaction — partial-state visibility is by design, verify nothing
reads it as complete) · scope creep (durability engine, check-ins,
section compile, boost v2, progress protocol all stay out).
