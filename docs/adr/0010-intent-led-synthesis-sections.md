# ADR 0010 — Intent-led synthesis sections and substrate-conditional grounding

*(Title updated 2026-07-08 with the coherence pass — originally
"…mixed grounding modes, selected-set chunk grounding"; both concepts
were superseded by this ADR's own amendment chain: the mode split
dissolved into one substrate-conditional flow, and chunk-grounding scope
widened to the screened-in corpus with the selection as a soft prior.
Filename unchanged.)*

- **Status:** Accepted — 2026-07-07 (Shabeer Rauf, task-013 contract gate,
  second round; follows an independent deep-reasoner design interrogation
  commissioned at the user's direction).
- **Date:** 2026-07-07
- **Context doc:** [task 013 contract](../tasks/013-synthesise/contract.md)
  (rev 3; revision history records the trail) ·
  [ADR 0009](0009-capability-composes-synthesise-terminus.md) (the terminus
  architecture this realises; its decision 5 amended by decision 3 below) ·
  [EB capability § Output structure](../specs/capabilities/evidence-base/capability.md)
  ("a single section mixes grounding modes freely … composed from intent") ·
  [provenance-grounding](../specs/system/provenance-grounding.md) ·
  [spec log, 2026-07-07 entries](../specs/log.md).

## Context

Contract rev 2 realised the deep synthesis as **one grounded block per facet
group**, with intent absent from the synthesis prompts (inherited from task
012's deliberate intent-exclusion) and **all** direct chunk-grounded
narrative deferred behind `retrieve`. The user challenged this as producing
an artefact shaped by what-was-studied rather than by what-was-asked —
against v3's founding principles (modularity, flexibility, collaboration) —
and directed an independent, detached design interrogation (deep-reasoner,
fresh context, contract-as-proposal-not-authority).

The interrogation confirmed the challenge and sharpened it:

1. **Group-per-block contradicts ADR 0009 itself** — the plan's authority to
   shape sections from intent had nothing to act on when composition was
   hardwired to group order; the source spec already says sections are
   "composed from the user's intent" and "mix grounding modes freely".
2. **012's intent-exclusion rationale does not transfer** — a facet
   partition should be question-independent; synthesis's entire job is
   serving the question. The recomputable unit for synthesis is
   `(config-including-intent, evidence)`.
3. **The IOF findings schema is deliberately narrow** (effect structure
   only), so findings-only prose can never carry mechanisms, implementation
   context, caveats or qualitative texture — the substance of an
   intent-relevant answer.
4. **Chunk-grounded narrative has two flavours the rev-2 contract
   conflated**: over the **selected set**, the documents' full frozen text
   is already in hand (extract windows exactly this text today; the
   `QuoteMatcher` presence machinery already verifies verbatim quotes
   against frozen chunks) — **no retrieval is needed**, and select's
   coverage discipline is inherited. Only the **corpus-wide** flavour
   (quoting unselected documents, pre-findings) genuinely needs `retrieve`.

## Decision

1. **Deep synthesis is structured as intent-led sections.** The section set
   is intent-shaped: v3.0 derives it via one bounded, schema-constrained
   section-proposal call (`synthesise_sections_v1` — intent + group
   summaries in, a validated section list out, capped), overridable by a
   fail-closed `context["synthesis"]` directive (the standing
   scope-directive precedent); plan-compile section machinery remains the
   recorded seam and this directive is its compile target. Intent also
   enters the writer prompts as emphasis-shaping **data** (id-keyed, never
   instructions). Intent is orthogonal to grounding: no claim passes verify
   because of intent — the presence check and the judge ("topical relevance
   ≠ support") are unchanged.
2. **Sections mix grounding modes** — per the source spec's own line. A
   section's typed claims are: **finding claims** (cite finding ids →
   extract-verified anchors), **chunk claims** (verbatim quote + chunk
   reference from the *selected set's* windowed frozen text — the texture
   the IOF schema cannot carry), and **pattern claims** (deterministically
   validated against computed spreads/records). All cited claims pass the
   full produce-grounded-block bar (deterministic quote-presence + the
   single-lane LLM judge + bounded reword-down repair; flag-not-drop).
   *(As amended: windowing → scoped retrieval [third round]; selected-set
   scope → screened-in corpus with the selection as a soft prior
   [sixth/seventh rounds]; the vocabulary later completed to six typed
   claims and the shape-claim type finally named **theme claim**
   [2026-07-08 round].)*
3. **Selected-set chunk grounding lands now (task 013), not behind
   `retrieve`** — amending ADR 0009 decision 5, which had contemplated only
   the corpus-wide flavour: a section's chunk window is the frozen text of
   the documents behind its assigned findings (bounded by select's budget
   and a windowing char budget; deterministic given the assignments), so it
   inherits select's coverage discipline. **Corpus-wide** chunk-grounded
   narrative (pre-findings targeted answers over unselected documents)
   remains the retrieve-gated seam with ADR 0009's recorded risk note.
   *(As amended: the in-slice scope widened to the **screened-in corpus**
   — screen bounds reading, the selection is a soft ranking prior, never
   a filter [sixth/seventh rounds]; only corpus-scale retrieval — beyond
   `RETRIEVAL_UNIT_CAP` or over unscreened content — remains
   retrieve-gated.)*
4. **Groups are demoted to input, not structure** — and, by explicit user
   choice, **no descriptive backbone blocks are rendered** (pure intent-led;
   the hybrid backbone option was offered and declined). Group summaries
   (labels, descriptions, sizes, spreads) inform the section proposal and
   the writer prompts as data; the deterministic direction spreads live on
   in `grouping_result`/`synthesis_result` roll-ups and in validated pattern
   claims. Recorded trade: the always-visible rendered full-shape check on
   intent-shaped prose is given up; the guards that remain are pattern-claim
   validation, the judge lane, the no-absence rule, and honest
   `groups_unsectioned` accounting (sections need not cover every group —
   uncovered groups are counted and flagged, never silently dropped).
5. **The trust machinery of contract rev 2 is retained unchanged** (the
   interrogation defended it): co-emitted citations only, the model never
   authors a finding-claim quote, deterministic presence re-check against
   frozen chunks, single-lane judge verdicts persisted with envelope/prompt
   versions, bounded repairs, flag-not-drop, no absence claims, the
   deterministically validated landscape path (now with intent as emphasis
   input), the intent-derived artefact title, and typed claims per unit —
   which the interrogation identified as the *enabler* of mixed-mode
   sections, not a rigidity.

## Consequences

*(Updated 2026-07-08 to the shape as amended through this ADR's chain;
the original bullets described the interim rev-3 realisation — four
surfaces incl. a separate landscape prompt, whole-document windowing,
per-path budgets.)*

- Task 013 implements one substrate-conditional flow of intent-led
  sections: **three prompt surfaces** (`synthesise_sections_v1` ·
  `synthesise_section_v1` — the section loop, multi-turn ·
  `grounding_judge_v1`), with tool-retrieved screened-corpus frozen text
  entering the writer turns (the 011 source-text egress class).
- `synthesis_result` carries the substrate profile, retrieval scope +
  priors, section provenance (the section set, its derivation source,
  unassigned groups) and per-section block entries with claim counts by
  type including chunk-cited.
- Budgets stay pre-run-known as a maximum: generation calls ≤ 2 +
  `SECTION_CAP` × (`SECTION_TURN_CAP` + 2); embedding calls ≤
  `SECTION_TURN_CAP` per section; all caps plan-pinned and binding.
- The 012 recomputability line is scoped in the specs: intent-exclusion was
  grouping-specific; synthesis determinism tests fix intent as input.

## Amendment (2026-07-07, third gate round — Shabeer Rauf)

Three user challenges against the rev-3 realisation, all adopted:

1. **"Deep path" terminology retired.** Synthesise is one component that
   always runs (ADR 0009); it renders **content modes by available
   references** — landscape content always, question-led grounded synthesis
   when the run produced findings. No mode is called a "path" or "deep".
2. **The claim vocabulary is completed to the spec's full set.** Rev 3
   carried finding/chunk/pattern claims in sections plus theme claims on
   the then-separate landscape path (the whole-design vocabulary was
   those four) — an amputation of two
   assertion types the specs make core: **gap claims** (the absence dual —
   EB's most consequential claim class; three grades with deterministic
   per-grade validation: corpus/coverage gaps require a non-`inadequate`
   `search_coverage_record` reference (007 machinery, fail-closed —
   otherwise the claim degrades to base-labelled), acknowledged domain gaps
   require the in-corpus sparsity signal validated against the
   characterisation coverage, inferred domain gaps ship visibly labelled
   as inference, never gated; grounded-synthesis gaps are base-labelled to
   the selected/extracted base, never promoted to corpus absence) and
   **reasoning claims** (visibly-labelled Tier 4 as an *authoring* mode —
   uncited framing/context; the judge applies the spec's strict-routing
   rule so policy-specific/empirical/causal content cannot hide there;
   never contributes to strength roll-ups). The earlier blanket "no absence
   claims" rule is replaced by the spec's own fail-closed gap discipline.
3. **Whole-document windowing replaced by scoped retrieval.** Feeding whole
   selected documents per section crowds context with irrelevant text and
   scales cost with length, not relevance. Instead: per section, the
   writer's chunk context = the cited findings' anchor chunks (always) +
   the top-k selected-set chunks ranked by embedding cosine against the
   section focus — in-memory over the 009-landed JSONB unit vectors (their
   **first reader**), no index, no new dependency. Recorded as the **first
   increment of the `retrieve` seam** (grounding/citation profile,
   selected-set scope), upgraded — not duplicated — by the future retrieve
   slice (index-backed, hybrid, corpus-wide); corpus-wide chunk claims
   remain gated on that slice.

## Amendment (2026-07-07, fourth gate round — Shabeer Rauf)

Four user probes, all adopted:

1. **Mode names fixed** — "question-led grounded synthesis (when the run
   produced findings)" misled twice: both modes are intent-led, and
   "findings" means the findings *layer* (`intervention_outcome_finding`
   rows, which exist only once the select-gated `extract` has run), not
   results colloquially. The modes are now **landscape synthesis** and
   **findings-grounded synthesis**. A targeted question typically runs
   narrow-and-deep (small selection, real extraction), so most
   intent-answering runs carry findings; landscape-only is the broad-scan
   case.
2. **Cluster claims unified** — the rev-4 "theme claim" was a cluster
   claim restricted to the landscape's characterise themes, leaving a
   findings-grounded section unable to assert the facet-cluster shape
   (012's groups). One **cluster claim** type now spans both modes,
   validated against the referenced clustering (themes at landscape grain;
   facet groups in sections), always labelled the softest interpretive
   grade with its inherited base — the soft end of the spec's pattern
   ladder, distinct from numeric **pattern claims** at the hard end.
3. **Depth clarified, not deleted** — retiring the shallow/deep *fork*
   does not retire depth: it survives as the plan's thoroughness
   **gradation** (plan-as-object — orchestrator-inferred from intent,
   lighter/deeper nudge, never a user-entered absolute), steering which
   registry components are selected, at the orchestrator's / sub-agent's
   discretion within structural data dependencies.
4. **The section writer is realised as a capped agent-loop (agentic
   retrieval)** — replacing the third-round amendment's deterministic
   top-k assembly. This is execution-orchestration's own declared
   realisation for synthesise ("agent-loop over scoped tools") and the
   exact consumer 012's `query-findings` deferral named. The writer
   iteratively gathers evidence through **two read-only, selected-set-
   scoped tools** — `search_chunks` (hybrid embedding-cosine + lexical,
   rank-fused, over the selected documents' units; the 009 vectors' first
   reader; the `retrieve` seam's first increment) and `query_findings` —
   under a **hard per-section turn cap**, then emits its typed claims.
   Trust properties unchanged: tools are read-only over frozen in-corpus
   text; every claim still faces per-type validation, the presence check
   and the judge; the repair regeneration is loop-free (one call over the
   already-gathered evidence). **This is the repo's first agent loop** —
   exactly one such surface (the section writer); the landscape, section
   proposal and judge calls stay single-call schema-constrained. Budget
   becomes a known pre-run *maximum* (turn-capped) rather than an exact
   count — an accepted, recorded loosening.

## Amendment (2026-07-07, fifth gate round — Shabeer Rauf)

Three user challenges, all adopted; net effect is a **simplification**:

1. **Modes dissolved into substrate-conditional synthesis.** The
   landscape/findings-grounded mode split was the last vestige of the
   retired fork: it hard-wired component combinations (chunk claims
   demanded extract → group) and so constrained the orchestrator's
   registry freedom. The extract component is deliberately narrow
   (intervention–outcome schema); a question that is not
   intervention-shaped must be servable by e.g. characterise → select →
   synthesise, grounding sections **directly in the selected set's
   chunks with no extraction** — select's coverage discipline, not
   extraction, is what bounds chunk claims. Rev 6: **one synthesise
   flow** — intent-led section proposal, then per-section loops — whose
   **claim types are gated by available substrate**: pattern (coverage
   always; spreads with extraction/grouping) · cluster (themes always;
   facet groups with grouping) · gap + reasoning (always) · **chunk
   (with a selection)** · **finding (with an extraction)**. References:
   `characterisation_run_id` required; the deepest available of
   `selection_run_id` / `extraction_run_id` / `grouping_run_id` optional,
   upstream references resolved transitively from the referenced rows'
   own provenance and cross-checked fail-closed. The separate landscape
   prompt dies — a characterisation-only run is the degenerate case of
   sections claiming pattern/cluster/gap/reasoning only. **Prompt
   surfaces: four → three** (`synthesise_sections_v1` ·
   `synthesise_section_v1` · `grounding_judge_v1`).
2. **The loop's tool set gains `lookup`** — the universal-core read tool
   the spec already defines (deterministic, identifier/filter-addressed,
   side-effect-free access to canonical project state): appraisal tiers,
   classifications, selection rationale, coverage records,
   characterisation and grouping rows are agent-queryable, not lost and
   not all pre-seeded. Three read-only scoped tools total:
   `search_chunks` · `query_findings` · `lookup` (closed query
   vocabulary v1, project-guarded).
3. **"Writer agent" naming corrected** — there is no second agent: the
   loop is the synthesise **component's internal realisation** (the
   facade principle — the capability sub-agent invokes synthesise as one
   tool; that sub-agent is the standing capability-run seam, with the
   skeleton standing in today). Renamed "the section loop" throughout.

## Amendment (2026-07-07, sixth–seventh gate rounds — Shabeer Rauf)

Five user probes across two waves; adopted or clarified on the record:

1. **Characterisation is optional too.** The fifth-round unification had
   left `characterisation_run_id` mandatory — an unprincipled residue:
   it gates coverage-pattern claims, theme-cluster claims and
   sparsity-grade gaps exactly as extraction gates finding claims. A
   rapid run (acquire → screen → ingest → synthesise) is coherent and
   groundable. The requirement drops to **at least one groundable
   substrate** (zero → structural failure). Recorded honestly: a run
   that skips characterise produces an artefact with no landscape — a
   grounded answer, not an evidence report; the plan's legitimate
   choice.
2. **Select is a soft prior, never a reading boundary.** The first draft
   of this amendment made chunk scope "the selection if referenced, else
   the screened-in set" — which inverted the data-model's own scoping
   principle ("a **soft retrieval prior, not a hard boundary** — look
   here first, then widen when thin; **agents are never penned in**")
   and produced a perversity: a full-chain run could quote *fewer*
   documents than a rapid run. Corrected: **retrieval scope = the
   screened-in corpus always** (screen is the relevance discipline that
   bounds reading; select gates *extraction cost*); a referenced
   selection contributes a **look-here-first rank boost**, recorded in
   provenance, and **every chunk citation records its origin**
   (`selected` | `unselected_screened`) so widening is visible, never
   silent. Scope guarded by the **fail-closed `RETRIEVAL_UNIT_CAP`**
   (the `FACET_VALUE_CAP` precedent: beyond it the index-backed
   `retrieve` slice is required, loudly, never a degraded pass).
3. **`lookup` covers the tag layer** — per the universal-core definition
   itself ("including aggregate queries over columns/tags"); the v1
   query vocabulary gains tag queries (tags by document, documents by
   tag, aggregates by tag type/asserter, provider-classed rows included).
4. **Verification needs no second agent — clarified on the record.**
   Verify is two non-agent mechanisms: the deterministic legs (presence
   check via `QuoteMatcher`; per-type validators) are pure code, and the
   judge is a **separate single-call schema-constrained surface**
   (`grounding_judge_v1`, own backend seam, no tools, no loop). Maker ≠
   checker holds at the surface level — the section loop never grades
   its own homework; the seam permits a heterogeneous judge model at the
   Bedrock swap; calibration stays with the eval workstream.
5. **The verify loop's rewrite step named explicitly.** The judge's
   per-claim rationales drive a **reword-down regeneration** of failing
   claims followed by one re-judge — the spec's bounded
   claim↔evidence-convergence loop — pinned as **`REPAIR_ROUND_CAP` = 1**
   (plan-pinned; round-count calibration = eval seam); exhaustion →
   soft-flagged, never dropped (fabricated chunk quotes excluded and
   counted, as before).

## Amendment (2026-07-08 — Shabeer Rauf)

**The unified claim type is named `theme claim`** (was "cluster claim",
second amendment item 2) — the policy-maker-facing word and the more
spec-aligned one (the provenance ladder's soft grade is "thematic
clustering"; group's component is "facet-level theming"). Semantics
unchanged; `cluster` remains the internal tool-registry verb. Same round,
the **consensus boundary was user-confirmed as the intended v3.0 line**
(descriptive spread, never a weighted verdict, until the ⏸ consensus seam
lands) — closing the question the task-013 rigidity sweep had raised.

## Rejected

- **Group-per-block as the artefact structure** (contract rev 2) — an
  evidence *organisation* mistaken for an artefact *structure*; intent-blind
  and thin by IOF-schema construction.
- **Hybrid with a rendered group-spread backbone** (the interrogation's and
  the lead's recommendation) — declined by the user in favour of pure
  intent-led sections; the trade is recorded in decision 4.
- **Deferring selected-set chunk grounding to 014 or `retrieve`** — the
  selected set needs no retrieval and the user directed it land in 013.
- **Model-authored quotes for finding claims** — unchanged from rev 2:
  finding claims cite ids and resolve to extract-verified anchors; only
  chunk claims carry model-emitted quotes, and those face the same
  deterministic presence check extract's own quotes face.
