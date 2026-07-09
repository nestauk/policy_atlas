---
type: Capability spec
title: Evidence Base (EB)
description: The declarative EB spec and §5 compile target — EB as an instance of the capability framework.
tags: [capability, evidence-base, compile-target]
timestamp: 2026-06-22
---

# Capability spec — Evidence Base (EB)

**The declarative spec — the §5 compile target.** Distilled from
[backend-evidence-base-build-spec.md](../../sources/backend/backend-evidence-base-build-spec.md), now
frozen origin; this spec + `docs/adr/` are canonical ([ADR 0002](../../../adr/0002-spec-governance.md)). EB is an **instance** of the capability
framework: shared machinery (Tier-0 substrate, retrieval contract, findings layer +
`intervention_outcome_finding`, grounding) is owned by the system contracts and only
**referenced** here; this spec holds what is **specific to EB**.

Companion files: [components.md](components.md) (the skeleton) · [provenance.md](provenance.md)
(EB's gap/pattern trust rules). System contracts:
[../../system/data-model.md](../../system/data-model.md) ·
[../../system/provenance-grounding.md](../../system/provenance-grounding.md) ·
[../../system/execution-orchestration.md](../../system/execution-orchestration.md) ·
[../../system/plan-as-object.md](../../system/plan-as-object.md).

## Artefact & scope

- EB is a **single, broad capability producing one artefact**.
- The artefact spans a **landscape ↔ synthesis depth axis**: shallow → an evidence *landscape*
  (corpus shape — metadata-grounded patterns, clusters, gaps); deep → adds a *synthesis* of what
  the evidence says (Tier-1 findings → grounded blocks). **The deep artefact contains the
  landscape.**
- Landscape and synthesis are **distinct, dependency-connected components**, not a pure
  gradation (they differ in output shape — scan-grounded shape vs source-grounded findings — so
  each is its own component by the I/O test). This is a distinction in **production and grounding
  mode, not presentation** (see [components.md](components.md) and output structure below).
- **The components are a registry the plan selects from** (task 013 flow-back, refining "how far
  down the chain a run goes"): which components fire is the orchestrator's plan-time selection
  from intent, adjusted by the lighter/deeper nudge — **data dependencies stay structural**
  (extract needs a selection; group and finding claims need an extraction; the artefact needs
  **at least one groundable substrate** — every upstream reference is optional, ADR 0010), expressed as explicit run references that compile
  fail-closed. **Breadth and depth are independent parameters**: a targeted question with a
  small time budget compiles to a *narrow-and-deep* run (small selection budget, few
  extractions, full grounding) — quick never has to mean shallow.
- **EB owns evidence assembly** — unlike analysis capabilities that start downstream of an
  existing selection, assembling the corpus broadly *is* EB's distinctive job, so its skeleton
  **includes the assembly components** and **`search` egress originates from inside the EB run**.
- **Rigidity:** fairly structured (toward the deterministic end of the dial).
- **Dependencies:** none upstream (EB is the front of the v3.0 chain). Downstream capabilities
  (Options Assessment, Impact, Transferability, VfM) consume EB's findings layer — all ⏸ deferred.

**Scope boundaries** (the evidence-vs-analysis line):
- Narrow, single-intervention deep analysis is **out of EB** → the **Impact** capability (⏸).
- **Precise option resolution is out of EB** — EB groups interventions *descriptively*
  (corpus-grounded thematic clusters); resolving them into named, comparable options is
  decision-relative → a future **Options Assessment** (⏸).
- EB may answer broader questions through grounded narrative synthesis over its **existing**
  findings, but must **not** add new schemas, structured computations or tools belonging to
  future capabilities (handoff §7.9). **Direct chunk-grounded narrative synthesis** is
  sanctioned (task 013 flow-back;
  [ADR 0010](../../../adr/0010-intent-led-synthesis-sections.md)): chunk quotes
  from the **screened-in corpus's** frozen text are part of grounded synthesis — screen is
  the relevance discipline that bounds reading, a referenced selection is a soft ranking
  prior (never a filter), and every claim passes the full `produce-grounded-block` bar,
  visibly chunk-cited rather than findings-mediated (nothing downstream can query such
  claims as structured findings — an accepted trade). ⏸ What remains gated on the
  index-backed `retrieve` slice is **corpus-scale** retrieval — beyond the fail-closed
  in-memory ceiling, or over unscreened content.

## Component skeleton

```
acquire → screen → classify → appraise → ingest(fetch) → synthesise   (the mandatory spine)
        + characterise (landscape content)                            (discretionary)
        + [select → extract → group]   (the deep chain, plan-selected) (discretionary)
```

**The mandatory EB spine** ([ADR 0013](../../../adr/0013-mandatory-eb-spine.md), task 016):
every run — rapid included — executes the spine, so every artefact synthesises over fetched
text (or a document's labelled abstract basis where fetch failed — a mandatory *attempt*,
reason-coded per document, never a substrate guarantee); characterise, select, extract, group
and stage-2 screen are orchestrator-discretionary per the depth gradation.
`screen` / `classify` / `appraise` run as **per-document fan-out**. **Full-text ingestion is
gated post-`screen`** (cheap shared substrate built for *all* screened-in — so even a shallow
landscape run builds the full-text corpus); **Tier-1 extraction is gated by `select`** (the
scoped, expensive step). **Synthesise is the terminus at every depth** (task 013 flow-back): one
substrate-conditional flow of intent-led sections whose claim types are gated by what the
run produced — a characterise-only run's artefact is the landscape; a run that also ran the
deep chain adds finding- and theme-grounded claims, so the deep artefact contains the
landscape. Per-component detail in [components.md](components.md).

**New shared tools EB introduces** (framework flow-backs, now in the system tool registry):
`screen`, `classify`, `select`.

## Output structure

- **User-facing sections composed from backend blocks.** The user-facing artefact is report-like **sections**; blocks +
  addressable units are the substrate. **Grounding is a per-unit property**, so a single section
  **mixes grounding modes freely** (a pattern, a cited finding and a gap in one paragraph). The
  characterise/synthesise split is about **production, not presentation**.
- **EB declares little; the orchestrator *shapes* the sections at plan time** (how many, around
  what facets, in what order — compiled plan parameters derived from intent); **EB's synthesise
  component composes the artefact at the run terminus** (task 013 flow-back — the
  capability-composes rule: every capability sub-agent composes its own artefact; the
  orchestrator owns no runtime content machinery). "Synthesis" is therefore **multiple
  sections** (typically one per facet/intervention family), not one.
- EB fixes only that the artefact carries:
  - an **artefact summary** — citation-free navigation, faithfulness-checked, **outside the
    grounding economy** (deliberately *not* "key findings"); and
  - two **content kinds** — landscape *shape* (patterns/clusters/gaps) and grounded *findings*.
- When a **headline evidence claim** is made it is a **grounded key-findings block** (a grounded
  content form carrying its headline at the appropriate grade — source-cited for a synthesis
  headline, metadata-grounded for a landscape headline), **never** the citation-free summary;
  **conditional-required** (present iff a headline claim is made).
- **Soft default order:** artefact summary (navigation) → [grounded key-findings block, *if*
  headline claims] → landscape → grounded synthesis (depth-ordered, general→specific).
  **Production ≠ presentation:** the key-findings block is produced **last** (it condenses what
  synthesis discovers) and the artefact summary is a late display rendering; both shown near the
  top, produced after their content. A convention, not a rigid template.
- EB departs from v2's decision-oriented frame: it is **evidence-descriptive** — **no
  recommendations / decision-answer section** (per scope above).

## Check-in points

- EB defines **no check-in policy of its own** — frequency is the user-set §6 **steering mode**.
  The landscape → synthesis crossing is a **mode-governed steer-point** (Frequent pauses there;
  Moderate pauses if the scope choice is important; Minimal flows through, logging/flagging).
- **EB declares no unconditional input gate** (it renders no verdict/recommendation), **but it
  pre-declares one conditional steer-point: "deepening selection"** — which clusters/documents go
  to deep extraction (a known, recurring, **emphasis-shaping** judgement, not an unanticipated
  residual). It follows §6's resolve-structurally pattern:
  - **Always log the selection rationale** (the bidirectional rationale `select` captures); the
    steer-point *reads* it.
  - **Escalate above the steering-mode baseline** when a trigger fires — each a computable proxy
    for *materially shifts emphasis*:
    - the selected subset **excludes a large / high-priority / user-nominated cluster**;
    - the **evidence base is thin** (the screen thin-base trigger);
    - the **policy can be supported only by below-policy sources** (a near-empty policy-filtered
      "well-evidenced" landscape — the characterise dual-view delta).
  - The strongest — a **user-nominated cluster dropped** (violates expressed intent), or a policy
    **unmeetable above-bar** — **escalate hardest, surfacing even in Minimal**; softer ones
    flag-and-pause per mode.
  - Otherwise route by steering mode. *(Still no unconditional always-pause gate; substance can
    never be silenced by the frequency dial.)*

## Cluster persistence

Clusters/groups (from characterise and group) are **run-local execution state**, not
information-layer objects — checkpointed for resume and reflected in durable artefact blocks, but
**never promoted to canonical, queryable state** (they are recomputable groupings over
embeddings/findings). No v3.0 consumer needs persisted clusters.
