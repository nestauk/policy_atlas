# Spec update log

## 2026-07-05
* **Fidelity restoration** (full specs-vs-sources review; maintainer-approved): restored source
  content lost in the original distillation —
  [product.md](product.md): "counterfactuals" back in the human-substance authority list (briefing §1/§3);
  [data-model.md](system/data-model.md): inferred-`function` lane set restored to 🟡 illustrative /
  to-be-specced with the five example lanes (arch §3.3), removing the undocumented
  `project_context_directive` closed set;
  [provenance-grounding.md](system/provenance-grounding.md): content-scan pattern rung restored
  (ships soft and honestly labelled, never gated; arch §3.3) and the citation-scope rule added
  (citations point to sources, never to sibling blocks; arch §3.3/§4);
  [plan-as-object.md](system/plan-as-object.md): audit posture across the modes restored
  (per-commit approval in Frequent/Moderate; every commit recorded; Minimal's guarantee triple;
  arch §5), cross-referenced from
  [execution-orchestration.md](system/execution-orchestration.md).
* **Update**: [EB components §4](capabilities/evidence-base/components.md) — clarified v3.0
  Tier-0 ingestion scope: fetch → parse → segment; vectorisation deferred to the slice where
  vectors are first read, with the eager-and-uniform discipline restated (not weakened) for
  when the embed seam lands. Approved with the task 008 contract per the spec-refinement flow
  (decision 1).
* **Update**: [EB components §1](capabilities/evidence-base/components.md) — clarified v3.0
  acquire-time snapshotting: acquire snapshots the metadata envelope as text-in-hand
  (`text_basis="abstract_only"`); full-text fetch + Tier-0 ingestion remain post-screen.
  Approved with the task 007 contract per the spec-refinement flow.

## 2026-07-03
* **Update**: [EB components §4](capabilities/evidence-base/components.md) — clarified v3.0
  appraisal coverage: the light pass scores classified evidence types; Non-evidence and Unknown
  are skipped-and-counted (Unknown re-enters via the deferred full-text resolution seam).
  Approved with the task 006 contract per the spec-refinement flow.

## 2026-06-24
* **Update**: Adopted OKF — added frontmatter (type/title/description/tags) to the eight distilled
  specs and declared `okf_version: "0.1"` on the [index](index.md). Content and status markers
  unchanged; this is an *intent* bundle (status-tagged, not "verified").

## 2026-06-22
* **Creation**: Distilled the four system contracts and the Evidence Base capability spec from the
  canonical sources; ratified the conflict-resolution order in the [index](index.md).
