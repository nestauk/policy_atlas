# ADR 0009 — Capability composes its artefact; synthesise is EB's terminus at every depth

- **Status:** Accepted — 2026-07-08 (Shabeer Rauf, task-013 contract gate).
- **Date:** 2026-07-07/08 (consolidated record — the decisions here were
  settled across the task-013 contract-gate rounds; the round-by-round
  trail lives in the
  [task 013 contract's revision history](../tasks/013-synthesise/contract.md)).
- **Context doc:** [task 013 contract](../tasks/013-synthesise/contract.md) ·
  [ADR 0010](0010-intent-led-synthesis-sections.md) (the synthesis
  realisation this architecture is implemented by) ·
  [EB capability](../specs/capabilities/evidence-base/capability.md) ·
  [EB components §§5/6/9](../specs/capabilities/evidence-base/components.md) ·
  [execution-orchestration](../specs/system/execution-orchestration.md) ·
  [spec log, 2026-07-07/08 entries](../specs/log.md).

## Context

The specs as first distilled assigned artefact composition to the
**orchestrator** ("EB declares little; the orchestrator composes the
sections … from intent") and framed synthesise as a **deep-only** terminus
over grouped findings, with depth as "how far down the chain a run goes".
At the task-013 contract gate the user challenged both readings,
architecture-first:

1. If a capability is a sub-agent in charge of an area of analysis, *it*
   should produce its artefact — the orchestrator owning runtime
   composition sits badly with the architecture's own rule that expertise
   lives in the capability ("a capability never runs another's
   component"), and scales badly as future capabilities (Options
   Assessment, Impact, VfM) each add composition logic.
2. A run that stops short of the full chain must still produce an
   artefact, and a **targeted question under a time budget** should be
   answerable from the evidence base as a grounded answer — not only as a
   landscape, and not only after a full extraction chain.
3. The components are realistically a **registry** the orchestrator
   directs the EB sub-agent through — some run, some are skipped, per
   intent — not a fixed ladder with a monotone depth cut-off. ("Registry"
   deliberately: it matches the code's `COMPONENT_REGISTRY` and the
   tool-registry vocabulary, and avoids colliding with the deferred
   `Library` corpus class.)

## Decision

1. **The capability-composes rule (framework-level).** Every capability
   sub-agent composes its own artefact at its run terminus. The
   orchestrator *shapes* the artefact at plan time — how many sections,
   around what facets, in what order, how deep — as compiled plan
   parameters, and owns **no runtime content machinery**. This scales to
   future capabilities without the orchestrator accumulating
   per-capability composition logic.
2. **Synthesise is EB's terminal component at every depth**, folding the
   composition step in (a separate "compose" component would be structure
   only one capability uses today; when a second capability lands, the
   assemble-step may factor out as shared machinery — earned then). It
   renders the run's available substrate into grounded blocks per
   [ADR 0010](0010-intent-led-synthesis-sections.md)'s
   substrate-conditional realisation, **mints the artefact row and binds
   the blocks**. Artefact conventions beyond that (section ordering
   conventions, artefact summary, key-findings block,
   supersede/lock-on-advance) remain at their recorded seams.
3. **Components are a registry; dependencies are structural, not
   ordinal.** Which components fire is the plan's selection from intent;
   what a component consumes it references explicitly (`*_run_id`,
   compile fails closed). **Breadth and depth are independent
   parameters** — a targeted question with a small time budget compiles
   to a **narrow-and-deep** run (small selection budget, few extractions,
   full grounding): quick never has to mean shallow, and never means
   weakening the grounding bar.
4. **Direct chunk-grounded narrative synthesis is sanctioned** (user
   decision, overriding the drafted recommendation to confine quick
   answers to narrow-deep runs + the ephemeral Q&A surface): the EB
   artefact may carry narrative prose grounded **directly in frozen
   chunks**, every claim through the full `produce-grounded-block` bar,
   **visibly chunk-cited** rather than findings-mediated. Accepted trade,
   recorded: such claims produce no structured findings downstream
   consumers can query or reuse. **Scope:** in-corpus chunk grounding
   over the **screened-in corpus** ships with synthesise (task 013) —
   screen is the relevance discipline that bounds reading, and a
   referenced selection is a **soft ranking prior, never a filter** (the
   data-model's agents-are-never-penned-in scoping principle; select
   gates *extraction cost*, not reading). What remains gated on the
   index-backed `retrieve` slice is **corpus-scale** retrieval — beyond
   the fail-closed in-memory ceiling (`RETRIEVAL_UNIT_CAP`) or over
   **unscreened** content.

## Consequences

- Task 013 implements the terminus component whole: **one
  substrate-conditional flow** — all four upstream run references
  optional (≥ 1 groundable substrate required), intent-led sections
  written by a capped tool-calling loop, artefact minting with an
  intent-derived title, **three prompt surfaces**
  (`synthesise_sections_v1`, `synthesise_section_v1`,
  `grounding_judge_v1`). Realisation detail is ADR 0010's.
- Every synthesise run produces a real artefact from 013 onward
  (characterise-only runs yield the landscape; screen-only rapid runs a
  grounded answer); the earlier "artefact-composition seam" narrows to
  conventions (summary, key-findings, ordering, versioning) rather than
  composition itself.
- Specs updated (capability.md, components §§5/6/9,
  execution-orchestration; spec log 2026-07-07/08) — the
  orchestrator-composes reading and the deep-only-terminus reading are
  superseded.
- In-corpus chunk grounding ships in this slice; only corpus-scale
  retrieval remains gated on `retrieve`, with the recorded risk profile.

## Rejected

- **Orchestrator-composes** (the prior reading) — misplaces capability
  expertise, scales badly across capabilities.
- **A separate terminal "compose" component now** — speculative structure
  at one capability; revisit when a second capability lands.
- **Confining quick answers to narrow-deep runs + Q&A only** (the drafted
  recommendation) — rejected by the user in favour of sanctioning the
  chunk-grounded artefact mode (decision 4 records the trade).
- **A hard reading boundary at the selection** (an interim scoping) —
  inverted the data-model's soft-prior principle and produced a
  perversity (a full-chain run could quote fewer documents than a rapid
  run); replaced by screened-corpus scope with the selection as a soft
  prior.
