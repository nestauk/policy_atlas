# Spec update log

## 2026-07-07
* **Update**: [EB capability](capabilities/evidence-base/capability.md), [EB components
  §9](capabilities/evidence-base/components.md) — the **intent-led synthesis refinement**
  ([ADR 0010](../adr/0010-intent-led-synthesis-sections.md); task 013 contract gate, second
  round, after an independent deep-reasoner interrogation): deep synthesis is structured as
  **intent-led sections** (bounded section proposal over intent + group summaries; fail-closed
  scope-directive override; plan-compile sectioning = the seam), each section **mixing
  grounding modes** — finding claims (extract-verified anchors), **selected-set chunk claims**
  (windowed frozen text already in hand; no retrieval needed; select's discipline inherited),
  pattern claims (deterministically validated). **Groups demoted to input, not structure**
  (pure intent-led — no rendered backbone, user choice; uncovered groups counted). ADR 0009
  decision 5 amended: only **corpus-wide** chunk grounding stays retrieve-gated. Supersedes
  the group-per-block reading of §9's "per group produce a grounded block". **Third-round
  amendment (same day, ADR 0010 § Amendment):** "deep path" terminology retired (content
  modes by available references); the claim vocabulary completed to the spec's full set —
  **gap claims** (graded, coverage-base-carrying, fail-closed corpus-promotion via
  `search_coverage_record`) and **reasoning claims** (visibly-labelled Tier-4 authoring,
  judge strict-routing guard) join finding/chunk/pattern/theme; whole-document windowing
  replaced by **scoped retrieval** (anchor chunks + top-k embedding-relevant selected-set
  chunks — the 009 unit vectors' first reader; the `retrieve` seam's first increment).
  **Fourth-round amendment (same day, ADR 0010 § second Amendment):** modes renamed
  (**landscape synthesis** / **findings-grounded synthesis** — both intent-led; "findings" =
  the findings layer); theme claims generalised to **cluster claims** across both modes
  (validated against the referenced clustering; softest grade); depth clarified as the
  plan's thoroughness gradation, not a fork; the section writer realised as a **capped
  agent-loop over scoped read-only tools** (`search_chunks` hybrid + `query-findings`) —
  execution-orchestration's declared realisation, the repo's first agent loop, discharging
  the 012 `query-findings` deferral in full.
* **Update**: [EB capability](capabilities/evidence-base/capability.md), [EB components
  §§5/6/9](capabilities/evidence-base/components.md),
  [execution-orchestration.md](system/execution-orchestration.md) — the **terminus
  refinement** (task 013 flow-back, user-decided at the contract gate): (1) the
  **capability-composes rule** — every capability sub-agent composes its own artefact at its
  run terminus; the orchestrator shapes sections at plan time and owns no runtime content
  machinery (supersedes the orchestrator-composes reading; characterise §5 note updated).
  (2) **Synthesise is EB's terminal component at every depth** — landscape rendering always
  (model prose, shape claims deterministically validated against the characterisation
  record), per-group grounded finding-blocks when the deep chain ran, artefact minting +
  block binding. (3) **Components are a registry the plan selects from**; data dependencies
  structural via explicit fail-closed run references; **breadth and depth independent** (a
  targeted question compiles to a narrow-and-deep run). (4) ⏸ **Direct chunk-grounded
  narrative synthesis sanctioned** for pre-findings targeted answers (full
  produce-grounded-block bar, visibly chunk-cited; lands with `retrieve`). ADR 0009.
* **Update**: [data-model.md](system/data-model.md) — findings-layer base-field list made
  explicit with three source-groundable sharpenings surfaced by the task-011 V2 extraction
  autopsy, all inside the spec's own "what the source reports" line: **stratum qualifiers**
  (timepoint/subgroup/setting as structured qualifiers; the outcome reference stays the base
  measure only — grain becomes *(intervention, outcome, effect, stratum)*), source-named
  nullable **comparator** (an effect direction is versus something), and the
  **estimate-level discriminator** (`study` | `pooled` | `claim`), with **τ²** joining the
  pooled stats (k, I²). Approved with the task 011 contract (rev 1.4 ⚑) per the
  spec-refinement flow.

## 2026-07-06
* **Update**: [EB components §6](capabilities/evidence-base/components.md) — select
  realisation refined: *procedure* → *procedure with an optional bounded generative rerank* of
  within-stratum ordering (stratification, breadth floor, budget arithmetic and must-includes
  stay code-side; schema-constrained per-doc scores + reasons; scores order, never exclude;
  per-doc fallback to the deterministic composite). `unclustered` named a first-class stratum
  (folding in what §5's counted-unclustered already implied). Approved with the task 010
  contract per the spec-refinement flow (rev 3).
* **Update**: [EB components §5](capabilities/evidence-base/components.md) — clarified
  content-vs-artefact: characterise produces the landscape *content* (run-scoped
  characterisation record + topic/theme tags); the single EB artefact is composed once at the
  run terminus by the orchestrator (artefact composition is a recorded seam). Approved with
  the task 009 contract per the spec-refinement flow (decision 7).
* **Update**: [EB components §5](capabilities/evidence-base/components.md) — thematic
  mechanism clarified to the bounded two-stage LLM grouping (discover over all
  titles+abstracts, batched assignment against the fixed theme list; code-enforced
  exhaustiveness; counted `unclustered`; run-local memberships; embedding-based clustering
  recorded as the very-large-corpus seam); and [EB components §4] — the embed seam opened in
  task 009 ahead of its first reader (approved exception), eager-and-uniform at
  embedding-unit grain over immutable canonical chunks. Approved with the task 009 contract
  (decisions 4, 2).
* **Update**: [data-model.md](system/data-model.md) — tag-layer clarification: "nothing hangs
  off a tag" governs the tag *label*; the assignment row carries assertion provenance
  (`asserted_by` + creating run); provider topical signals materialise as provenance-classed
  tags; provenance classes never mix. Approved with the task 009 contract (decision 10).

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
