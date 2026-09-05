---
type: System contract
title: The plan as an object
description: The plan object, plan→config compile, two-level/progressive planning, source/evidence policy and depth.
tags: [system, plan, compile, planning]
timestamp: 2026-07-05
---

# System contract — The plan as an object

**Distils** [backend-architecture-reference.md](../sources/backend/backend-architecture-reference.md)
§5. This spec + `docs/adr/` are canonical; the source is frozen origin ([ADR 0002](../../adr/0002-spec-governance.md)). Note: §5's *What a plan contains* is marked 🟡 (candidate) upstream — accepted as-is;
may be refined as implementation lands.

## Plan vs config

- The **plan** is the human-readable, method-level, **editable, canonical** object — what the
  user approves and what goes in the decision log. The **config** is the machine-level execution
  spec (tools, components, parameters), **compiled from** the plan. Never a hidden parallel
  execution truth.
- **Robust compile by construction, not a smarter translator.** The plan is a **structured
  selection over the capability's declared spec**, so compilation is a deterministic mapping
  (section → component → declared tools; depth → parameters; named input → source), valid by
  construction (a plan can only reference what the capability declares). Execution-bearing fields
  compile; free-text annotation (framing, assumptions) stays non-executing context. A config that
  doesn't validate is a **caught error, never a silent run**. The mapping round-trips, so
  **"approved plan" and "executed config" are provably the same** — the point of plan-as-canonical
  for audit. Genuinely fuzzy edits are **surfaced for confirmation, not compiled silently**.
- **Forecast vs commit — what actually compiles.** The Agent's up-front per-capability
  plan is a **forecast** (drives the preview + time estimate; **does not compile**); each
  capability agent's just-in-time selection is the **commit** (the execution-bearing layer that
  compiles, by construction). Two tiers, staged compilation: the plan spine's
  sequence/wiring compiles up front; each commit compiles **just-in-time** once its inputs exist.
- **Plan-field ↔ chat-turn provenance** — each compiled field back-references the conversation
  turn(s) that produced it (raw prose retained behind the structured field), so the plan carries
  its own "why" into the decision log without coupling compilation to free text.

## What a plan contains 🟡 *(candidate, per §5)*

- **Frame** — a thin narrative intent statement; a **living field** the Agent re-derives
  from structured inputs on a material scope-changing edit (never re-summarising chat). The
  *authoritative* "what this task is doing" is the structural reading (capability set +
  assumptions + statuses); the narrative is the readable gloss.
- **Inputs & dependencies** — sources, uploads, prior artefacts it draws on; whether it fetches
  new evidence. Also carries the capability's **extraction specs** + **selected source subset**
  (the per-capability forecast driving selection-then-extraction).
- **Output structure** — the sections/blocks it'll produce.
- **Approach** — how each section is done, described as **method, not tools**.
- **Depth per section** — the thoroughness gradation + compile target (see below).
- **Steering & check-ins** — mode + expected pauses, including mandatory gates.
- **Assumptions & boundaries** — surfaced so the user corrects cheaply before the run.
- **Source / evidence policy** — the evidentiary standard (see below).

## Thoroughness as a relative nudge, not an absolute level

Depth stays a per-section **gradation** (the deterministic compile target) but is **never a
user-entered field, and no absolute level is surfaced** (an abstract label has no calibratable
referent). Instead:
- The Agent **infers depth from task scale** (intent breadth, # capabilities, corpus
  size); urgency is not elicited separately.
- **The anchor is the concrete proposal + a cost signal, not a label** — e.g. "compare 3 options,
  screen ~50 sources, light per-source extraction, recommendation block" + a rough time band. The
  estimate **model is ⏸ deferred** for v3.0; a coarse band suffices.
- **Two adjustment paths, both anchored to the proposal**: (1) edit the proposal / converse;
  (2) a single **relative nudge — lighter / as-proposed / deeper** — re-deriving all per-section
  depths in one move. Named bundles ("modes") survive only as an Agent/authoring
  convenience, **never a user-facing absolute dial**.
- *(Maps the wireframe's **Quick / Deep** control: treat it as a `search_effort_signal` /
  `search_breadth_signal`, **not** a hard public depth ladder — EB handoff §7.1.)*

## Source / evidence policy

A plan-level declared constraint expressing the **evidentiary standard** (e.g. "official
statistics and peer-reviewed evaluations only"). Two faces:
- **Acquisition face — already covered**: which backends / **trust classes** may be searched
  (existing `search` machinery; open-web behind its seam). Bundles an existing capability, no new
  mechanism.
- **Use face — the new bit: a grounding standard, not a retrieval boundary**. The agent may
  still **retrieve and read** any in-corpus source (never penned in), but the policy sets the
  **appraisal tier** (source *quality*, **not** the grounding/inference tier) a source must meet
  to be cited as **grounding support**, enforced at the `produce-grounded-block` verify boundary.
- **Flag, not block** — a claim grounded only on a **below-policy** source is **produced**, with
  the citation **marked as resting on below-policy evidence** (a soft typed flag), so the user
  *sees* the lower-tier information and decides. (Project-wide flag-don't-drop.) *Rejected:* a hard
  block (hides evidence, manufactures false gaps, overrides the user) and a retrieval boundary
  (pens the agent in, redundant with appraisal-column scoping).
- **Substance-relevant** → lives in the plan and the audit record.
- 🟡 **Open extension**: a quality/recency-aware ranking prior behind the rerank seam —
  deliberately not built (novelty-vs-established balance is use-case-dependent; should be a
  steerable per-policy preference, not a baked default).

## Two-level & progressive planning

- **Task plan (forecast spine)** — Agent-authored: which capabilities, order,
  inter-capability dependency graph, overall steering, best-guess component/depth forecast. A
  **living** object tracking forecast-vs-actual as commits land. The **template is a default
  task plan**.
- **Per-capability plan (commit)** — capability-agent-authored just-in-time once inputs land.
- **Plan is artefact-*like*** — versioned, user-facing, editable; **reuses the artefact machinery**
  (blocks, units, versioning, change log) but stays a distinct *kind* (Agent-authored
  executable instrument). Structure is **separate-but-linked** (spine + per-capability plans).
- **System proposes, user disposes** — intent → recommended capability set (template), accepted
  wholesale (fast path) or edited (power path); ordering bounded by declared dependencies.
- **Progressive** — later capabilities can't be fully planned up front (inputs don't exist);
  **forecast the whole, commit each just-in-time**. Material commit-vs-forecast divergence surfaces
  at the between-capability check-in by mode; **substance divergence escalates in every mode**.
- **Audit posture across the modes** — approval lands at the **forecast/shape** level up front
  in every mode; **per-commit approval happens in Frequent/Moderate**. **Every commit is
  recorded in the decision log** (nothing executes invisibly). Minimal's guarantee =
  **approved-shape + recorded-commits + substance-escalation**; higher modes add per-commit
  gating.
- **Flexible yet robust** — flexibility in the combinations, robustness in the pieces (each choice
  is a bounded selection that always compiles). A user-added **free-form section compiles to a
  generic grounded-section component** (expressive freedom without breaking bounded compile).
  Honest limit: you can only compose what's declared.

## Enough context to propose — ask only on shape

A **principle, not an intake schema**. The Agent may propose on thin context but:
- **The proposal is honestly calibrated to what it actually knows** — assumptions/open guesses are
  first-class, cheaply-correctable plan content. A thin-context plan is *visibly* thin, which
  defuses anchoring better than withholding it.
- **It asks only when a missing piece would change the plan's *shape*, not its detail** —
  shape-determining unknowns (which capabilities, order, core framing, explicit out-of-scope) are
  expensive to unwind, so a single targeted question beats guessing; detail unknowns are absorbed
  by plan edits + the lighter/deeper nudge.

The plan is the **first decision-log entry**. *(Rejected: a bare output-defined threshold —
near-vacuous; a declared intake checklist — frictionful and brittle.)*
