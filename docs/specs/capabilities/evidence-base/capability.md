# Capability spec — Evidence Base (EB)

**The declarative spec — the §5 compile target.** Distilled from
[backend-evidence-base-build-spec.md](../../sources/backend/backend-evidence-base-build-spec.md), which is
the canonical EB design and wins on any conflict. EB is an **instance** of the capability
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
- **Depth is a §5 gradation *over* the component chain** — how far down it a run goes —
  orchestrator-inferred from intent, surfaced as concrete scope, adjusted by the lighter/deeper
  nudge. Gradation governs *which components fire*; the components are genuine structure.
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
  future capabilities (handoff §7.9).

## Component skeleton

```
acquire → screen → classify → appraise → characterise (shallow terminus)
        → select → extract → group → synthesise (deep terminus)
```

`screen` / `classify` / `appraise` run as **per-document fan-out**. **Full-text ingestion is
gated post-`screen`** (cheap shared substrate built for *all* screened-in — so even a shallow
landscape run builds the full-text corpus); **Tier-1 extraction is gated by `select`** (the
scoped, expensive step). Depth (§5) sets how far down the chain a run goes: shallow terminus =
the landscape, deep terminus = the synthesis. Per-component detail in [components.md](components.md).

**New shared tools EB introduces** (framework flow-backs, now in the system tool registry):
`screen`, `classify`, `select`.

## Output structure

- **User-facing sections composed from backend blocks.** The user-facing artefact is report-like **sections**; blocks +
  addressable units are the substrate. **Grounding is a per-unit property**, so a single section
  **mixes grounding modes freely** (a pattern, a cited finding and a gap in one paragraph). The
  characterise/synthesise split is about **production, not presentation**.
- **EB declares little; the orchestrator composes the sections** (how many, around what facets,
  in what order) from intent. "Synthesis" is therefore **multiple sections** (typically one per
  facet/intervention family), not one.
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
