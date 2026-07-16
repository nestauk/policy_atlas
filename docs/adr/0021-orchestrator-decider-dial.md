# ADR 0021 — The orchestrator decider dial: one agent, three moments; the boundary watch

**Status:** Accepted — 2026-07-16 (Shabeer Rauf; task 024 contract rev 4 as
amended; owner-driven design across five review rounds + the owner cost
adjudication). Supersedable by: the eval slice's findings on watch/router
quality, and the post-eval EB-expert slice (which fills sockets this ADR
pins, never replaces the authority order).

## Context

017 shipped steering as fixed pause sets with closed option menus and one
pre-run LLM call (the planner), deferring the conversational half and
`agent_judgement_routed`. The owner's 024 direction: a state-of-the-art
human-in-the-loop system — free text at steer points, run-specific
options, and the orchestrator watching the analysis to route or take
decisions on the user's behalf.

## Decisions

1. **The decider dial.** *Every decision surfaces in the durable record;
   the steering mode never changes what is decided or what is visible —
   it moves the decider between the user and the orchestrator.* Modes
   renamed to delegation postures ("when should I come back to you?"):
   Frequent (user decides everything) · Moderate (P2/P3/P4 always; fired
   P1 + watch escalations) · Minimal (fired triggers only; 0 pauses on a
   healthy run — a live-behaviour change from 017's unconditional
   deepening-selection pause, named here) · Unattended (nothing live).
2. **One orchestrator, three moments.** Planner (succeeding `planner_v5`),
   free-text **router** (prose → a confirmed multi-stage fan-out of
   bounded deltas; partial compile with per-fragment honest refusal;
   nothing applies unconfirmed in attended modes), and boundary **watch**
   — one backend seam, one prompt family (`orchestrator_v1`), shared
   session. Mid-run LLM calls are hereby permitted **at component
   boundaries only**, never inside a component's run — this deliberately
   revises 017 decision 5's "one LLM call, pre-run" sequencing invariant;
   component execution stays deterministic; interpreter/watch failure
   degrades to the deterministic floor (structural routing + canonical
   menus) — the run never depends on the judgement layer.
3. **The watch discharges the spec's "no first-principles runtime
   classifier" ⏸** (execution-orchestration:176) as an *additive,
   floor-bounded, non-taxonomic* judgement layer: the declared structural
   trigger table fires deterministically and is never suppressible; the
   watch may add escalations, decide residuals in delegating modes
   (within the full user surface — options, keys, guidance channels —
   compiled through the author-blind fail-closed grammar), and authors
   2–5 run-specific options per pause on the canonical floor (which
   remains the stable `steer_point_defaults` vocabulary). Bias-to-escalate
   when substance-or-unsure; substance-or-unsure at a triage boundary
   promotes to decision-point treatment before any self-decision.
4. **Unattended = discretion-is-the-mode.** Revises the spec's
   unanticipated-substance mechanism (proceed-and-flag → watch
   discretion): choosing Unattended is the delegation; planner-authored
   standing instructions (per-point suggested defaults, editable in
   prose, skippable) override where pinned; hard stops always honoured;
   no-pinned-rule decisions keep `unconfigured_default` as the loudest
   flag class, reviewed first in the collation.
5. **Information + cost model (owner cost adjudication).** Structurally
   gated invocation — the watch runs only at decision points,
   trigger-fired boundaries, and anomalous check-ins; clean boundaries
   emit deterministic `clean_boundary` judgement events with no LLM call.
   Decision points are **single-shot over option-complete pre-fetched
   bundles** (every canonical option answerable from the bundle or marked
   requires-user-input), with a read-tool fallback loop capped at 2
   `lookup`/`query_findings` round-trips (never `retrieve`, never
   `search`), every call + digest evented. Model routing: mini-class
   triage, judgment-class decisions/authoring. Costs are dev-side only —
   no cost language on any user-facing surface (017 standing rule).
   Symmetry principle: same information *environment* as the user, not
   the same payload.
6. **Authority order is fixed regardless of author: user > declared rules
   > orchestrator.** Authorship is a seam (author-blind compile;
   `authored_by`/`decided_by` attribution; the authoring-seam protocol);
   authority is not. The EB-expert stays post-eval and arrives behind
   these sockets — decision-point authoring is its future home; every-leg
   directive authoring (`leg_directive`) stays untouched.
7. **Accepted residual, named:** watch-authored guidance entering
   downstream component prompts in delegated modes is an unconfirmed
   LLM→LLM channel. Containment: author-blind scrub/bounds identical to
   user prose (test-pinned), attribution + loudest-flag review,
   poisoned-input fixtures, user override at any attended pause;
   compounding across boundaries is an eval measurement.

## Consequences

- The spec flow-back rewrites § Steering modes *and* § the routing rule
  (mechanism, not labels); the "Thorough" label sync note discharges.
- The refusal event stream remains the demand meter for grammar widening
  even with the router in place; insufficient-context escalations meter
  the deferred triage-tier tooling.
- The eval slice inherits named measurements: watch routing quality,
  authored-option quality, guidance compounding, escalation rates.
