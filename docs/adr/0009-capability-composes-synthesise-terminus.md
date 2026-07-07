# ADR 0009 — Capability composes its artefact; synthesise is EB's terminus at every depth

- **Status:** Accepted — 2026-07-07 (Shabeer Rauf, task-013 contract gate).
- **Date:** 2026-07-07
- **Context doc:** [task 013 contract](../tasks/013-synthesise/contract.md)
  (revision history records the gate-challenge trail) ·
  [EB capability](../specs/capabilities/evidence-base/capability.md) ·
  [EB components §§5/6/9](../specs/capabilities/evidence-base/components.md) ·
  [execution-orchestration](../specs/system/execution-orchestration.md) ·
  [provenance-grounding](../specs/system/provenance-grounding.md) ·
  [spec log, 2026-07-07 terminus entry](../specs/log.md).

## Context

The specs as distilled assigned artefact composition to the **orchestrator**
("EB declares little; the orchestrator composes the sections … from intent";
characterise's 009 decision recorded composition as an orchestrator-owned
seam) and framed synthesise as the **deep-only** terminus over grouped
findings, with depth as "how far down the chain a run goes". At the task-013
contract gate the user challenged both readings, architecture-first:

1. If a capability is a sub-agent in charge of an area of analysis, *it*
   should produce its artefact — the orchestrator owning runtime composition
   sits badly with the architecture's own rule that expertise lives in the
   capability ("a capability never runs another's component"), and scales
   badly as future capabilities (Options Assessment, Impact, VfM) each add
   composition logic.
2. A run that stops at characterise would today produce no artefact until a
   separate composition slice lands; and a **targeted question under a time
   budget** should be answerable from the evidence base as a grounded
   answer, not only as a landscape.
3. The components are realistically a **registry** the orchestrator directs
   the EB sub-agent through — some run, some are skipped, per intent — not a
   fixed ladder with a monotone depth cut-off. ("Registry" deliberately: it
   matches the code's `COMPONENT_REGISTRY` and the tool-registry vocabulary,
   and avoids colliding with the deferred `Library` corpus class.)

## Decision

1. **The capability-composes rule (framework-level).** Every capability
   sub-agent composes its own artefact at its run terminus. The orchestrator
   *shapes* the artefact at plan time — how many sections, around what
   facets, in what order, how deep — as compiled plan parameters, and owns
   **no runtime content machinery**. This scales to future capabilities
   without the orchestrator accumulating per-capability composition logic.
2. **Synthesise is EB's terminal component at every depth**, folding the
   composition step in (a separate "compose" component would be structure
   only one capability uses today; when a second capability lands, the
   assemble-step may factor out as shared machinery — earned then). It
   renders **landscape blocks** from the referenced characterisation record
   (always — the minimum content an artefact needs), adds **per-group
   grounded finding-blocks** when the deep chain ran, **mints the artefact
   row and binds the blocks**. Artefact conventions beyond that (section
   ordering conventions, artefact summary, key-findings block,
   supersede/lock-on-advance) remain at their recorded seams.
3. **Landscape rendering is model prose, pattern-validated.** Shape-asserting
   claims are deterministically validated against the characterisation
   record (the claim-typing machinery); no source citations at this grade —
   none exist, none are faked. Grounded finding-blocks use the full
   `produce-grounded-block` bar (deterministic quote-presence + LLM judge).
4. **Components are a registry; dependencies are structural, not ordinal.**
   Which components fire is the plan's selection from intent; what a
   component consumes it references explicitly (`*_run_id`, compile
   fails closed). **Breadth and depth are independent parameters** — a
   targeted question with a small time budget compiles to a
   **narrow-and-deep** run (small selection budget, few extractions, full
   grounding): quick never has to mean shallow, and never means weakening
   the grounding bar.
5. **Direct chunk-grounded narrative synthesis is sanctioned** (user
   decision, overriding the drafted recommendation to confine quick answers
   to narrow-deep runs + the ephemeral Q&A surface): the EB artefact may
   carry narrative prose grounded **directly in frozen chunks** when a
   targeted question warrants answering before the findings chain has run —
   every claim through the full `produce-grounded-block` bar, **visibly
   chunk-cited** rather than findings-mediated. Accepted trade, recorded:
   such claims bypass select's coverage discipline and produce no structured
   findings downstream consumers can query or reuse. **Lands with
   `retrieve`** (its chunk-selection substrate); a ⏸ seam until then.
   *Amended by [ADR 0010](0010-intent-led-synthesis-sections.md) (same
   gate, later round): this decision as written covers only the
   **corpus-wide** flavour, which stays retrieve-gated with the trade above.
   The **selected-set** flavour — chunk grounding over the selected
   documents' already-in-hand frozen text — needs no retrieval, inherits
   select's coverage discipline, and lands in task 013.*

## Consequences

- Task 013 implements the terminus component whole: landscape path
  (`characterisation_run_id` required) + grouped-findings path
  (`grouping_run_id` optional), artefact minting with an intent-derived
  title, three prompt surfaces (`synthesise_landscape_v1`,
  `synthesise_block_v1`, `grounding_judge_v1`).
- Shallow runs produce real artefacts from 013 onward; the earlier
  "artefact-composition seam" narrows to conventions (summary, key-findings,
  ordering, versioning) rather than composition itself.
- Specs updated (capability.md, components §§5/6/9,
  execution-orchestration; spec log 2026-07-07) — the
  orchestrator-composes reading and the deep-only-terminus reading are
  superseded.
- The chunk-grounded mode is a named seam with a recorded risk profile; its
  arrival is gated on `retrieve`, not on this slice.

## Rejected

- **Orchestrator-composes** (the prior reading) — misplaces capability
  expertise, scales badly across capabilities.
- **A separate terminal "compose" component now** — speculative structure at
  one capability; revisit when a second capability lands.
- **Confining quick answers to narrow-deep runs + Q&A only** (the drafted
  recommendation) — rejected by the user in favour of additionally
  sanctioning the chunk-grounded artefact mode (decision 5 records the
  trade).
