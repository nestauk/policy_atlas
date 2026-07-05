# Spec update log

## 2026-07-05
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
