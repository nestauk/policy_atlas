---
type: Product spec
title: Product boundary & mental model
description: What Policy Atlas v3 is and isn't — the evidence-led workspace, the decision-support body, and the boundary of the tool.
tags: [product, mental-model, boundary]
timestamp: 2026-07-05
---

# Product boundary & mental model

Distilled from the architecture briefing §1–§3 and the EB handoff §5 (now frozen origin). This
spec + `docs/adr/` are canonical ([ADR 0002](../adr/0002-spec-governance.md)); it remains an orienting gloss.

## What the product is

Policy Atlas v3 is an **evidence-led policy-analysis workspace**, not a document generator
and not a chatbot. A project is a **policy workstream**, and its terminal product is an
**inspectable decision-support body**: artefacts produced by capabilities, the evidence
corpus behind them, claim provenance, comments, versions, dependencies and a decision log.
Humans use that body to brief, advise, write, clear and publish **outside** the tool. The
tool supports policy judgement; it does not replace it.

## The shape of a v3.0 run (the EB journey)

```
project landing → empty workspace → planning conversation → plan ready
→ build with check-ins → Evidence Base artefact summary → progressive detail
→ evidence table (stub) → comments mode → rerun as new version → re-entry with catch-me-up
```

The conversation is the **steering surface**; the artefact and the evidence behind it are
the **work product**.

## Architectural commitments the product rests on

- **Artefacts over chat.** Chat coordinates; artefacts + their evidence are the work
  product. Project memory is structured state, not a transcript.
- **Evidence-led & inspectable.** Evidence sits in a shared information layer, reused across
  capabilities. Significant claims carry citations, quotes, grounding tier and appraisal —
  **co-emitted, never stapled on afterwards.**
- **Agency vs accountability.** Agents get bounded freedom over *method*; humans retain
  authority over *substance* (options, recommendations, assumptions, counterfactuals, value
  judgements, material deviations). Steering modes change involvement *frequency*, never this
  boundary.
- **Progressive disclosure.** Plan before run, evidence behind claims, comments beside
  blocks, summaries that drill into full grounded detail.
- **Model only what behaves.** No label, object type or flag exists in the backend unless it
  changes v3.0 system behaviour (no inert sensitivity flags, no source-class lifecycle, no
  `Library` class, no strand entity).
- **Build light, leave seams.** Meet v3.0 needs without adopting infrastructure for deferred
  complexity; preserve seams for parallelism, private deployment, richer security, workflow
  engine substitution.

## In / out of scope for v3.0

| In scope | Out of scope (deferred — see [../deferred.md](../deferred.md)) |
|---|---|
| Projects as workstreams; decision-support body as the product | Auto-writing the final white paper; policing claims lifted into external docs |
| Evidence ingest, retrieval, screening, appraisal, extraction, reuse | A general-purpose agent platform / free-form tool palette |
| Declared capabilities producing inspectable artefacts via bounded plans | Full clearance workflow, Teams/Word replacement |
| Grounded blocks, structured provenance, gaps, patterns, appraisal | Full RBAC, artefact-scoped visibility, per-item sensitivity gates |
| Anchored comments, catch-me-up, versioning, lock-on-advance, decision log | Private deployments (seams preserved) |
| **Evidence Base** capability only | All other capabilities (Options Assessment, Impact, Transferability, VfM, ToC, Risk) |

The practical rule: when in doubt, favour features that improve the **inspectable body**
(evidence, artefacts, provenance, comments, versions, audit) over features that imply a
broader workflow the tool does not yet drive.
