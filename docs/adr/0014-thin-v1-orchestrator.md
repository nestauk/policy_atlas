# ADR 0014 — The thin v1 orchestrator (planner · composer · capability-runner · steering core)

**Status:** Accepted — 2026-07-10 (Shabeer Rauf; task 017 contract rev 2.9 +
plan rev 5). The decision trail lives in the 017 contract's revision history
(revs 1–2.9: two adversarial reviews — contract-stage 8 findings/8 adopted,
plan-stage 6/6 adopted — a V2 search-wizard study, an agent-orchestration
research pass, and roughly a dozen user gate calls).

## Context

Through task 016 every EB component runs live end-to-end, but nothing in
product code turns a user intent into a chain: chains exist only as
test-harness profiles in `skeleton.py`, and the throwaway demo's planner is
de-authorised. The demo dress-rehearsal (018) would otherwise rehearse a
scaffold. The orchestrator spec cluster (plan-as-object +
execution-orchestration) is several slices big; 017 cuts a deliberate thin v1
from it.

## Decisions

1. **The v1 carve: forecast → approval → compile → execute, plus steering.**
   A lead-authored LLM **planner** (conversational, unified intent-planning:
   the plan is generated and surfaced for review/edit; ask-only-on-shape;
   questions carry 2–5 suggested answers; anchored proposals + measured time
   bands with a fixed lighter/as-proposed/deeper nudge) · a deterministic
   **composer** (fail-closed against the component registry; every composed
   chain contains the ADR 0013 mandatory spine) · a serial, deterministic
   **EB capability-runner** the orchestrator delegates to (the sub-agent
   boundary made real in code; per-component two-phase transactions; failure
   chaining off successful predecessors; its directive-authoring slot is the
   named seam the future LLM EB-expert drops into) · the **steering
   structural core** (below).

2. **Discretionary composition = intent-fit × a two-axis gradation.** The
   planner reasons over declared component descriptions for *relevance*
   (extract is intervention–outcome schema-bound — a non-intervention intent
   composes without the deep chain at any depth); the gradation decides *how
   much*: **search effort** (`rapid` = non-agentic one-pass · `standard` =
   the latency-optimised agentic loop, a new additive per-depth constants row
   · `deep` = the full loop) × **analysis depth** (`landscape` · `standard` ·
   `deep`). Diagonal pairings are planner defaults; off-diagonal shapes
   (narrow-and-deep; the horizon scan) are legitimate. Escalation is
   plan-chosen composition — the loop's stopping rule is the declared
   sanctioned method at `standard`+; v1 ships no armed runtime hatch (rapid
   flags thinness honestly).

3. **Steering: four modes, structurally honest.** Frequent · Moderate ·
   Minimal · **Unattended** — a **spec refinement** to execution-orchestration
   § Steering modes: in Unattended, the anticipated steer-points' default
   resolutions are visible plan content (pre-declarable rules only, never
   runtime-data-specific answers); starting the run is the consent; every
   auto-resolution is flagged and collated. Substance is thereby never
   *silent* though no longer always *live* — the firm principle's
   accountability purpose is preserved. Check-in content is deterministic
   renders (no narration prompt surface); the deepening-selection steer-point
   pauses in every mode except Unattended, with intent-vocabulary options
   mapped to the as-built selection grammar (multiplicative
   `weight_emphasis`; `priority_strata`); adjustments touch only not-yet-run
   components and persist as new plan version rows; abort is a clean stop.

4. **The plan is a first-class table; its lifecycle is table-first.** A
   minimal `orchestration_plan` table (immutable version rows, status,
   payload, attribution) is the slice's one schema addition; `event_log`'s
   non-null run FK makes pre-run plan events unimplementable, so plan rows
   ARE the plan's audit trail and per-component `plan.compiled` events carry
   plan id + version. No capability-run entity, no plan blocks/units.

5. **The sequencing invariant (the injection boundary).** No LLM surface
   authors or amends orchestration-plan content once acquire begins: the
   planner completes pre-acquisition; mid-run amendments are user-authored
   and deterministically compiled; capability-internal prompt surfaces write
   component/artefact state under their own verification machinery, never
   plan state.

6. **Durability: per-component commits, no resume engine.** Two-phase
   per-component run lifecycle (run row + events commit before component
   work, so failure events survive rollback — also discharging the recorded
   harness failure-event gap); a failed run is re-run from the top; the
   resume engine stays a seam carrying the idempotency-key-before-interruption
   requirement.

## Rejected

- **The LLM EB-expert capability agent now** — the expert sub-agent that
  authors directives just-in-time and carries domain expertise into
  composition. Deferred to its own slice (recommended post-eval): a second
  large prompt surface whose value is directive *quality*, unmeasurable
  before the eval slice; the runner's directive slot is its drop-in seam.
- **Dynamic mid-run replanning** (orchestrator-worker style) — conflicts
  with plan-time authority, the audit spine.
- **Events-only plan persistence** — reversed at the gate (the plan is the
  slice's most behaviour-bearing object; 018 reads it; event-scraping read
  models are the RETRO-flagged anti-pattern).
- **A user-facing absolute depth dial** and **"adaptive" as a rung name** —
  the exposure stays proposal + band + relative nudge; rung names are
  internal.
- **Section shaping compiled at plan time** — sections stay substrate-aware
  inside synthesise (ADR 0010); the plan carries a non-executing
  expected-artefact-shape field instead.

## Consequences

- 018 rehearses a real product path (intent → plan → run → artefact) and
  the planner prompt joins its refine loop.
- execution-orchestration § Steering modes gains the Unattended path
  (flow-back rides the 017 build with a `log.md` entry).
- New seams recorded in `deferred.md`: the LLM EB-expert slice ·
  plan-field↔chat-turn provenance · runner-visible usage aggregation ·
  resume-engine idempotency note · steering's conversational half
  (narration, clarify/escalate parking, `agent_judgement_routed`).
- The depth-spectrum seam gets its v1 rungs; time-band targets (≤10 / 15–30 /
  ~90 min) drive constants tuning at 018/evals, with displayed bands always
  measured.
