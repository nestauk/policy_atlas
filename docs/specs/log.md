# Spec update log

## 2026-07-12
* **Update**: [system/data-model.md § The findings layer](system/data-model.md) — the
  `intervention_outcome_finding` base-field list gains `effect_basis` (`observed` |
  `modelled`, null if indeterminate — evidence basis is its own dimension from causal
  identification, deliberately not folded into `causality_by_design`) and
  `study_geography` (source-named, finding-grain — the same population/comparator
  treatment; null when unreported, never inferred). Existing v1 rows are not backfilled;
  they read as "not recorded under v1" via `field_coverage` key-absence, per the
  upgrades-never-invalidate rule. Task 020, ADR 0016.

## 2026-07-11 (b)
* **Creation**: [system/prompting.md](system/prompting.md) — the prompting doctrine promoted
  out of the 018 task folder (owner decision, 2026-07-11; task-cycle step 8): the 12
  family-general rules + mini-tier adjustments from the 018 research sweep, the
  refine-replay loop method as validated by the 018 C-loop (two-stage baselines, cheap-probe
  classes, ≤3-rounds bound with the flag-not-drop-judge escape hatch, anti-overfit pins,
  compile-your-probes), agent-loop conventions (force-emit exhaustion, code-enforced read
  batching, adjacent envelopes, judge-envelope re-baselining, environment-context preamble),
  and the provider quarantine for the Bedrock swap. A hand-maintained prompt-surface registry
  was considered and declined (drifts; provenance already records surface versions).

## 2026-07-11
* **Update**: [EB capability § Output structure](capabilities/evidence-base/capability.md) and
  [provenance-grounding § Summaries](system/provenance-grounding.md) — the "what did it
  conclude" front door split into **two distinct grounded blocks, never merged** (owner
  refinement 2026-07-10; task 018, ADR 0015): the **key-findings block** (headline evidence
  claims at their appropriate grade, produced last / shown first, conditional-required —
  present iff headline claims are made) and a **conclusions block** at the report foot (what
  this evidence amounts to against the user's question, evidence-descriptive — no
  recommendations / decision-answer content; cited to sources, never to sibling blocks).
  provenance-grounding's compound "key-findings/conclusion block" phrase resolved into the
  two-block structure accordingly. Approved with the 018 contract (rev 4) per the
  spec-refinement flow.

## 2026-07-10
* **Update**: [execution-orchestration § Steering modes & the routing rule](system/execution-orchestration.md)
  — **Unattended mode** added (task 017, contract rev 2 decision 6b, user call; approved in
  principle at the 017 contract 🛑; ADR 0014): a fourth steering mode with zero mid-run
  interaction. Anticipated steer-points auto-resolve to **pre-declared visible default
  resolutions carried as plan content** (pre-declarable rules per steer-point class, never
  runtime-data-specific answers — rev 2.5 adversarial finding 6); every auto-resolution is
  flagged, collated into the end-of-run review and marked on the run record. The firm
  principle's wording assumed a live pause; its accountability purpose is preserved — the
  human substance decision moves from run-time to plan-time and is never *silent*, no longer
  always *live*. The routing-rule table gains the Unattended column; unanticipated substance
  residuals resolve proceed-and-flag as `unconfigured_default`, the loudest flag class.
  Approved with the 017 contract per the spec-refinement flow.
* **Update**: [EB components](capabilities/evidence-base/components.md) (opening chain
  statement + §9) and [EB capability](capabilities/evidence-base/capability.md) (component
  skeleton) — **the mandatory EB spine** (task 016, user call at the contract gate
  2026-07-09; ADR 0013): every EB run executes acquire(`search`) → screen → classify →
  appraise → ingest(fetch) → synthesise; characterise · select · extract · group · stage-2
  screen are orchestrator-discretionary per the depth gradation. Mandatory ingest is a
  mandatory **attempt** (reason-coded per document), never a substrate guarantee.
  Synthesise's substrate gate is untouched in character; its envelope-only refusal becomes
  unreachable-by-composition and `no_groundable_substrate` narrows to the genuinely empty
  corpus (no references AND screened-in count zero). Approved with the 016 contract
  (rev 2.2 + amendments, 2026-07-09) per the spec-refinement flow.
* **Update**: [EB components §4](capabilities/evidence-base/components.md) — as-enacted
  note on the flag-not-drop failure path (016 contract rev 2.5, user call): the
  unfetchable document's substrate IS its envelope abstract chunks (chunked + embedded at
  acquire), joining grounded retrieval as labelled substrate with `text_basis` carried on
  chunk records and citations; an all-fetch-failed corpus still synthesises, visibly
  abstract-labelled. Access-failure honesty recorded (401 → paywall; 403 → paywall only
  with corroboration, else `blocked_by_host`; bot-blocks never counted as paywalls). This
  enacts written §4 text the 008 fixture era never reached — no semantic change to the
  spec's intent.

## 2026-07-08
* **Update**: [EB components §2](capabilities/evidence-base/components.md) — screen refined
  to its v3.0 **two-stage realisation of the one component** (stage-parameterised via the
  plan directive; the thoroughness gradation selects): stage 1 metadata (fail-open,
  title-only exclusion needs consensus unanimity) always; stage 2 windowed full-text
  re-screen at depth, **demote-only**, text-availability-scoped, both stages persisting with
  stage provenance ("screened-in" = *effective* screened-in); `screen_basis` gains
  `full_text`; failures never block retry. Tiered content peek noted as largely superseded.
  Approved with the task 014 contract (rev 1.10, 2026-07-08) per the spec-refinement flow;
  ADR 0011.
* **Update**: [EB components §9](capabilities/evidence-base/components.md) — `search_chunks`
  described as its staged pipeline (task 013 contract rev 7.5): content-only hybrid
  relevance → arithmetic soft priors (selection prior + fail-closed directive boosts over
  columns/tags/appraisal tier, re-weight-never-exclude — the surface the future
  source/evidence policy compiles into, honouring plan-as-object's steerable-never-baked
  quality-prior ruling) → a cross-encoder reranker slot (pass-through until Bedrock Rerank
  lands, per the retrieval contract's inference-trust-boundary line) → caps.
* **Coherence pass** (task 013 gate, pre-adversarial-review; fresh-context audit, 18
  findings, no semantic changes): superseded same-gate wording reconciled to the amended
  state across [EB capability](capabilities/evidence-base/capability.md) and
  [EB components](capabilities/evidence-base/components.md) — "artefact needs at least
  characterise's content" → **≥ 1 groundable substrate** (all upstream references
  optional); the selected-set/corpus-wide chunk-grounding binary → **screened-in corpus
  with the selection as a soft prior**, only corpus-scale retrieval (beyond the in-memory
  ceiling, or unscreened content) retrieve-gated; the tool-wiring table row for synthesise
  → substrate-conditional (+ declares `search_chunks`); ADRs 0009/0010 subsequently
  **consolidated into cohesive, amendment-free records** (user direction: amendments are
  for shipped ADRs — within one unmerged branch, decisions and justifications belong in
  the main structure; ADR 0010 retitled "…and substrate-conditional grounding"; the
  round-by-round decision trail is retained in the task-013 contract's revision history);
  cross-references updated everywhere.
* **Update**: [EB components §9](capabilities/evidence-base/components.md) — the unified
  interpretive-shape claim type renamed **cluster claims → theme claims** (task 013 gate,
  user call: policy-maker-facing vocabulary, and the more spec-aligned word — the
  provenance ladder's soft grade is "thematic clustering", group's component is
  "facet-level theming"). Semantics unchanged (validated against the referenced
  clustering: characterise themes / facet groups; softest grade, base-labelled);
  `cluster` remains the internal tool-registry verb. Recorded in
  [ADR 0010](../adr/0010-intent-led-synthesis-sections.md) (2026-07-08 amendment),
  alongside the user's confirmation of the **consensus boundary** as the intended v3.0
  line (descriptive spread, never a weighted verdict, until the ⏸ consensus seam).

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
  the 012 `query-findings` deferral in full. **Fifth-round amendment (same day, ADR 0010
  § third Amendment):** the mode split itself dissolved into **one substrate-conditional
  flow** — claim types gated by what the referenced runs produced (chunk claims need only a
  **selection**, not extraction — non-intervention-shaped questions run
  characterise → select → synthesise; finding claims need an extraction; pattern/cluster/
  gap/reasoning per available substrate); the separate landscape prompt dies (**three**
  prompt surfaces); the loop gains **`lookup`** (the universal-core canonical-state read —
  appraisals, classifications, selection rationale, coverage records, clusterings); "writer
  agent" corrected to **the section loop** (component-internal realisation per the facade
  principle — no second agent; the capability sub-agent remains the capability-run seam).
  **Sixth/seventh-round amendment (same day, ADR 0010 § fourth Amendment):** **all
  references optional** — characterisation joins the substrate-conditional logic
  (requirement = ≥ 1 groundable substrate; a rapid acquire → screen → ingest → synthesise
  run is fully served); **select is a soft prior, never a reading boundary** — retrieval
  scope = the screened-in corpus always (the data-model's agents-are-never-penned-in
  scoping principle; select gates extraction cost), a referenced selection contributes a
  recorded look-here-first rank boost, every chunk citation records its origin
  (selected | unselected_screened); fail-closed in-memory retrieval ceiling
  (`RETRIEVAL_UNIT_CAP`), beyond which the index-backed `retrieve` slice is required;
  `lookup` explicitly covers the **tag layer** (per its universal-core definition);
  clarified on the record: verification is non-agentic — deterministic code legs + a
  separate single-call judge surface (maker ≠ checker at the surface level) — and the
  verify loop's rewrite step is explicit (judge rationales → one reword-down regeneration
  → one re-judge; `REPAIR_ROUND_CAP` = 1, plan-pinned).
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
