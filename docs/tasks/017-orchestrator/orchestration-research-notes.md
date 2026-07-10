# Agent planning/orchestration research notes (rev 2.4 evidence)

Commissioned at the 017 contract gate (2026-07-10, user direction): a /last30days
social sweep (Reddit · X · HN · GitHub, window 2026-06-10 → 2026-07-10; raw file
`~/Documents/Last30Days/ai-agent-planning-and-orchestration-raw-v3.md`) plus targeted
web research. Findings adjudicated into contract rev 2.4; this file preserves the
sources and the reasoning for the ADR and the build.

## Folded into the contract (rev 2.4)

1. **Sequencing invariant (2.4a, decision 5).** The plan-then-execute security
   literature (arXiv 2509.08646, "Architecting Resilient LLM Agents: A Guide to
   Secure Plan-then-Execute Implementations"; echoed by the 2026 SitePoint agentic
   design-patterns guide) names the property: the plan is fixed **before untrusted
   data is read**, so mid-run injection can corrupt a step's output but never
   rewrite the plan. 017 had this by construction (planner pre-acquisition;
   deterministic check-ins; user-authored amendments compiled fail-closed) but not
   as a stated invariant a build could be held to.
2. **Resume-engine seam note (2.4b, decision 7).** Durable-execution consensus
   (Inngest "Durable Execution: The Key to Harnessing AI Agents"; LangChain HITL
   docs; Zylos durable-execution-for-agent-runtimes): checkpoint-serialized state,
   suspend/resume over hours/days, and an **idempotency key persisted before the
   interruption** so a resumed action runs exactly once. Recorded on the deferred
   resume seam so it isn't rediscovered.
3. **Per-leg token/cost roll-up (2.4c, decision 11).** "Token bleed" (runaway token
   consumption across multi-agent chains) circulating as the named orchestration
   cost failure mode; existing per-component usage telemetry makes a per-leg
   roll-up nearly free, and it feeds the depth seam's bands + the plan's time-band
   honesty.

## Confirmations (no contract change; ADR/prompt-authoring inputs)

- **Unified intent-planning.** Deep-research planner taxonomy (Zylos deep-research
  architectures survey): planning-only · intent-to-planning (ChatGPT-style
  clarifying follow-ups) · **unified intent-planning** (generate the plan, surface
  it for user review/edit before execution — Gemini-style; highest alignment). The
  017 planner is the third shape. Their ask-gate wording — ask only what would
  "change the structure, depth, or direction of the answer" — is a good sharpening
  of "ask-only-on-shape" for the lead-authored planner prompt.
- **Static vs dynamic interrupts** (LangGraph): compile-time breakpoints vs
  runtime-raised interrupts, both persisting state — maps one-to-one onto 017's
  mode → pause-set compile (static) and trigger-fired deepening-selection
  escalation (dynamic). Useful vocabulary for the ADR.
- **Simplest-pattern-first.** Beam's production-patterns piece claims ~40% of
  multi-agent pilots fail within six months from wrong/over-chosen orchestration
  patterns; counsel is to start with the simplest pattern and layer only when a
  named failure mode demands it. External validation for the thin deterministic
  runner and the deferred LLM capability agent.
- **Review-gate middle tier.** r/AI_Agents (2026-07-02, "I stopped building an
  AI-first company"): "my real mistake was thinking about tasks in binary — can AI
  do it or not. The unlock was a middle tier: tasks AI does well most of the time
  but that are risky enough to need a review gate." Independent practitioner
  validation of the steer-point posture.
- **Plan-as-data convergence.** AWS AgentCore Harness GA ("agents defined in
  configuration, not orchestration code"), Kastor (Show HN, Terraform-style agent
  specs), and a PostHog production PR freezing an AI report query plan "for
  deterministic runs" — the ecosystem converging on declarative plans with
  approved-plan = executed-config properties. Confirms the compile round-trip pin.
- **Steering-at-boundaries demand signal.** anthropics/claude-code issue #71726
  asks for messages "injected into the agent loop mid-task between tool calls" —
  the live-steering-at-the-next-boundary shape the execution-orchestration spec
  already specifies.

## Deliberately not adopted

- Dynamic replanning mid-run (orchestrator-worker's evolving-context delegation):
  017's plan-time authority is the audit spine; runtime adaptation stays at the
  JIT-commit seam (future LLM EB-expert slice).
- Async/queued approval with TTLs: needs the durable-signal machinery (web-app
  cluster); v1's blocking CLI pause + Unattended mode covers the demo path.
