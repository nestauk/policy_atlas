# Task contract: 013-synthesise

One implementation slice. Boundaries are in [AGENTS.md](../../../AGENTS.md);
specs in [docs/specs/](../../specs/index.md).

> **Status:** drafted (rev 7.5) — awaiting contract 🛑.
> Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ ·
> ADRs: [0009](../../adr/0009-capability-composes-synthesise-terminus.md)
> (terminus architecture; decision 5 as amended) +
> [0010](../../adr/0010-intent-led-synthesis-sections.md) (intent-led
> sections; four dated Amendments = the rev-4/5/6/7 rounds) — both
> Accepted 2026-07-07.
>
> **Revision history:**
> - **rev 1** (2026-07-07): initial draft — synthesise as deep-only content
>   producer per the then-current spec reading.
> - **rev 1.1** (2026-07-07): intent-derived artefact title · claim-driven
>   pattern annotations · judge envelope = cited chunks' full text ·
>   retrieval position explicit · clarity fixes.
> - **rev 2** (2026-07-07 → **ADR 0009**): capability-composes; synthesise
>   = EB's terminal component at every depth; registry + breadth ⊥ depth.
> - **rev 3** (2026-07-07, deep-reasoner interrogation → **ADR 0010**):
>   group-per-block replaced by intent-led sections; intent enters
>   synthesis; selected-set chunk grounding in-slice; pure intent-led.
> - **rev 4** (2026-07-07 — ADR 0010 § Amendment): "deep path" retired;
>   claim vocabulary completed (**gap** + **reasoning** claims); windowing
>   replaced by scoped retrieval.
> - **rev 5** (2026-07-07 — ADR 0010 § second Amendment): modes renamed;
>   theme → **cluster claims**; the section writer = capped agent-loop —
>   the repo's first agent loop, gated change 4.
> - **rev 6** (2026-07-07 — ADR 0010 § third Amendment): the mode split
>   dissolved into one substrate-conditional flow (chunk claims need only
>   a selection); the landscape prompt died (three surfaces); the loop
>   gained `lookup`; "writer agent" → the section loop.
> - **rev 7** (2026-07-07, sixth round — ADR 0010 § fourth Amendment):
>   **(a) all references optional** — characterisation joins the
>   substrate-conditional logic (it was the last unprincipled mandatory
>   reference); the requirement is **≥ 1 groundable substrate**, else
>   structural failure. A rapid acquire → screen → ingest → synthesise
>   run grounds chunk claims over the **screened-in set**. **(b) select
>   is a soft prior, never a reading boundary** (second-wave probe, same
>   round): retrieval scope = the **screened-in corpus always** — the
>   data-model's scoping principle verbatim ("a soft retrieval prior,
>   not a hard boundary … agents are never penned in"); a referenced
>   selection contributes a **look-here-first rank boost** (recorded in
>   provenance) and every chunk citation records its origin (**selected
>   | unselected_screened**) so widening is visible, never silent —
>   select's purpose is gating *extraction* cost, not penning in
>   reading. Scope guarded by a **fail-closed in-memory retrieval
>   ceiling** (`RETRIEVAL_UNIT_CAP`, the `FACET_VALUE_CAP` precedent —
>   beyond it the index-backed `retrieve` slice is required, loudly,
>   never a degraded pass). A run without characterise yields an
>   artefact with no landscape — a grounded answer, not an evidence
>   report (the plan's legitimate choice). **(c) `lookup` covers the tag
>   layer** (per its universal-core definition — aggregate queries over
>   columns/tags). **(d) clarified on the record: verification is
>   non-agentic** — deterministic code legs + a separate single-call
>   schema-constrained judge surface; maker ≠ checker at the surface
>   level. **(e) the verify loop's rewrite step named explicitly**: judge
>   rationales feed one reword-down regeneration then one re-judge —
>   **`REPAIR_ROUND_CAP` = 1, plan-pinned** (the spec's bounded verify
>   loop; round-count calibration = eval seam).
> - **rev 7.1** (2026-07-07, rigidity sweep at the user's direction):
>   **answer-shaped lead sections made explicitly legal** — the section
>   proposal's "never verdicts" rule read strictly could have prohibited
>   a "what the evidence shows on the question" lead section (the most
>   valuable section for a question-asking policymaker; the spec's
>   grounded key-findings idea in section form); the rule now targets
>   **verdict-sections** (evaluative-conclusion premises) only. The sweep
>   otherwise confirmed the remaining rigidities as deliberate recorded
>   seams (IOF-only findings layer · the consensus boundary · one-shot
>   sectioning · per-section independence · composition conventions ·
>   screened-out unreachable · one-artefact-per-run).
> - **rev 7.2** (2026-07-07, coherence/discovery brainstorm — user
>   adjudicated): **rolling claim ledger adopted** — sections written
>   serially in proposal order, each loop seeded with prior sections'
>   typed claims as **context-never-evidence** (since block content is
>   the claims' texts joined, the ledger *is* the sections as written,
>   plus structure; sibling-content citation impossible by construction).
>   **Declined/deferred with reasons**: evidence pre-allocation (inverts
>   relevance-driven selection — rejected outright); the coherence pass
>   stays at its **original spec home** — regeneration-time artefact
>   coherence (the data-model seam), not a write-time pass; the
>   structure-discovery bundle (recon-informed proposal ·
>   structure-mismatch signals · bounded revision checkpoint) **waits for
>   the slice to land** — revisit as a seam with evidence if one-shot
>   structure proves a real problem.
> - **rev 7.3** (2026-07-07, external validation round): a `/last30days`
>   field scan (raw file `~/Documents/Last30Days/agentic-rag-grounded-
>   report-generation-raw-v3.md`) **validated the direction** — retrieval-
>   as-a-controlled-loop is the 2026 consensus; verification-centric
>   design, claim-anchored citations and tiered citation UX are where the
>   field is converging; retrieval (not generation) is the dominant RAG
>   failure point; step-boundary discipline and judge calibration are the
>   named production hazards; **the field's loudest warning — shipping
>   without an eval harness sinks projects — points at our deferred eval
>   seam: recommended as the named next slice after 013.** A deep-reasoner
>   **V2 synthesis autopsy** ([v2-synthesis-autopsy.md](v2-synthesis-autopsy.md),
>   the third V2 recon leg) adjudicated in: **(a) rendering-decomposition
>   invariant** (V2's deterministic interventions table escaped grounding
>   entirely — structured renderings decompose into typed claims, no
>   verification escape hatch; decision 7.i); **(b) verbatim-evidence
>   invariant** (V2 primed its writer on re-summarised truncated chunks —
>   citation-bearing evidence is frozen-chunk text / verified anchors
>   only; decision 7.ii); **(c) named tests**: fabricated quotes never
>   persisted (V2 kept `is_supported=True` on unfindable quotes and
>   stored them), caps bind (V2's config caps were dead code) + honest
>   evidence floors (`uncited_sections` flag; V2 wrote sections on zero
>   evidence), passing claims survive sibling repair (V2 regenerated
>   whole sections). Build-phase adoption notes recorded in the autopsy
>   file (menu+default proposal pattern; renumber-by-first-appearance as
>   a composition-seam convention; click-to-highlight affordance
>   preserved by verified-span citation rows).
> - **rev 7.4** (2026-07-08, user vocabulary + consensus call):
>   **cluster claims renamed → theme claims** — the policy-maker-facing
>   word, and the more spec-aligned one (the provenance ladder's soft
>   grade is "thematic clustering"; 012's component is "facet-level
>   theming"). Semantics unchanged: one unified type validated against
>   the referenced clustering — characterise themes with a
>   characterisation, facet groups with a grouping; softest interpretive
>   grade, base-labelled. `cluster` remains the internal spec tool verb
>   (tool-wiring table untouched). **Consensus boundary confirmed as a
>   seam** (the rev-7.1 open question, answered): the artefact describes
>   the spread, never "the evidence supports X", until the ⏸
>   weighted-consensus seam lands — user-affirmed as the intended v3.0
>   line.
> - **rev 7.5** (2026-07-08, user retrieval-stack round): **(a) the
>   `search_chunks` pipeline gains a cross-encoder reranker stage** —
>   `ChunkRerankerBackend` protocol, **v1 default pass-through**
>   (recorded `reranker: "none"`); the spec's retrieval contract assigns
>   this slot to Bedrock Rerank (inference trust boundary) and 010
>   recorded the user's Cohere-class interest here — the live backend +
>   its `run_harness` injection point land with the Bedrock slice (no
>   public kwarg while nothing live exists — the V2 dead-config lesson).
>   **(b) directive-driven metadata biasing adopted** — the
>   `context["synthesis"]` directive gains optional `retrieval_boosts`
>   (select's vocabulary: clamped multiplicative weights over columns /
>   tags / appraisal tier), applied **arithmetically post-fusion** —
>   never fed to the relevance leg (the 010 signal-attributability
>   rule) — re-weight-never-exclude, default none, executed boosts +
>   `unmatched_boosts` in provenance; honours plan-as-object's
>   quality-prior ruling (steerable per-directive, never a baked
>   default) and is the surface the future source/evidence policy
>   compiles into.

## Goal

Add **synthesise** — EB component 9 and, per ADR 0009, **EB's terminal
component: it runs at every depth** and **composes the one EB artefact** —
mints it (intent-derived bounded title), renders content into grounded
blocks, binds them in proposal order. The orchestrator shapes the artefact
at plan time; composition is capability expertise and happens here. Depth
survives as the plan's thoroughness gradation steering which registry
components fire; **synthesise never hard-wires a component combination —
it adapts to whatever the plan selected** (ADR 0010, as amended).

**One flow.** Synthesise takes explicit fail-closed run references — **all
optional**: `characterisation_run_id`, and the deepest available of
`selection_run_id` / `extraction_run_id` / `grouping_run_id` (upstream
references resolved transitively from the referenced rows' own provenance
and cross-checked; explicitly-passed shallower references must match). The
requirement is **at least one groundable substrate** — zero substrate is a
structural failure. Then:

1. **Section proposal** (`synthesise_sections_v1`, one bounded
   schema-constrained call): intent + the available substrate summaries →
   a validated, capped, intent-led section list. A fail-closed
   `context["synthesis"]` directive can supply the list (the
   plan-shaped-sections seam's compile target).
2. **Per section, the section loop** (`synthesise_section_v1` — the
   component-internal realisation execution-orchestration declares;
   **the repo's first agent loop, exactly one such surface**): a capped
   tool-calling loop over **three read-only, code-scoped tools** —
   - **`search_chunks`** (when the scope has screened-in ingested
     documents): hybrid embedding + lexical retrieval, rank-fused, over
     the **screened-in corpus's** frozen units — screen is the relevance
     discipline that bounds reading; **a referenced selection is a soft
     ranking prior, never a hard boundary** (the data-model's scoping
     principle: look here first, widen when thin, agents are never
     penned in) — the boost recorded in provenance, every returned chunk
     carrying its origin (**selected | unselected_screened**).
     **Fail-closed `RETRIEVAL_UNIT_CAP`** — a corpus whose unit count
     exceeds the in-memory ceiling fails structurally naming the cap
     (the index-backed `retrieve` slice is the upgrade, never a degraded
     pass). The 009 vectors' first reader; the `retrieve` seam's first
     increment;
   - **`query_findings`** (when an extraction is referenced): the
     findings-layer read — the 012 deferral's named consumer, discharged
     in full;
   - **`lookup`** (always): the universal-core canonical-state read —
     appraisal tiers, classifications, selection rationale, coverage
     records, characterisation/grouping rows, **and the tag layer**
     (aggregate queries over columns/tags, per its own definition);
     closed query vocabulary v1, identifier/filter-addressed,
     side-effect-free —
   under a hard `SECTION_TURN_CAP`, then emits **typed claims gated by
   substrate**:
   - **pattern** (coverage counts with a characterisation; direction
     spreads with extraction/grouping) — counts must equal the computed
     values;
   - **theme** (themes with a characterisation; facet groups with a
     grouping) — validated against the referenced clustering row;
     softest interpretive grade, base-labelled;
   - **gap** (always) — graded, coverage-base-carrying (sparsity-grade
     gaps need the characterisation coverage); base-labelled to the
     narrowest base the substrate supports; corpus-level absence **only**
     on a referenced non-`inadequate` `search_coverage_record` (else
     fail-closed degraded and counted); inferred gaps visibly labelled,
     never gated;
   - **reasoning** (always) — uncited, visibly Tier-4-labelled, bounded
     per block, judge strict-routed, never in strength roll-ups;
   - **chunk** (with screened-in ingested documents) — verbatim quotes
     from tool-returned frozen text only; screen's relevance discipline
     bounds them, the selection prior steers them, and each citation
     carries its origin — a question outside the intervention–outcome
     schema is served without extract;
   - **finding** (with an extraction) — cite finding ids →
     extract-verified anchors; the model never authors these quotes.
   A characterisation-only run is the landscape degenerate case; a
   screen-only run is a grounded answer with no landscape (the plan's
   choice, honestly recorded in the substrate profile). **Groups, where
   present, are input, not structure** (`groups_unsectioned` counted).
   **Descriptive always**: no recommendations, no weighted verdicts (⏸
   consensus seam).
3. **Verify and write — non-agentic by design.** Every cited claim goes
   through the **real `produce-grounded-block` mechanism**: citations
   **co-emitted, never post-hoc**; verify = the **deterministic legs**
   (pure code — the quote-presence check against frozen chunks via
   `QuoteMatcher`, plus the per-type validators) **and the judge** — a
   **separate, single-call, schema-constrained surface**
   (`grounding_judge_v1`, its own backend seam and prompt, no tools, no
   loop: **maker ≠ checker at the surface level** — the section loop
   never grades its own homework; the seam permits a heterogeneous judge
   model at the Bedrock swap). Single lane: exactly one of Tier 1–4 /
   Unsupported-mis-cited; orthogonal weakly-grounded flag; required
   rationale; input includes the cited chunks' full frozen text
   (`synthesis_envelope_v1`); "topical relevance ≠ support". One
   **loop-free** reword-down repair; on exhaustion claims land
   **soft-flagged, never dropped, never silently promoted** — one hard
   exception: a chunk claim whose quote fails presence after repair is
   **excluded and counted**. Blocks / claim-grain units / typed
   annotations / citation rows are written to the 001 substrate; the
   run-scoped `synthesis_result` roll-up row is the last statement.

⏸ Corpus-scale chunk grounding (beyond the in-memory ceiling, or over
unscreened content) stays gated on the full `retrieve` slice. This slice
is the **first real writer of the 001 information-layer substrate**, the
**first reader of the 009 embedding-unit vectors**, and the **repo's
first agent loop**.

## Deliverable

A PR on `task/013-synthesise` → `dev` that:

- Ships `synthesise.py`: `SynthesiseContext(scope_id, intent, context,
  characterisation_run_id=None, selection_run_id=None,
  extraction_run_id=None, grouping_run_id=None)`; `synthesise_scope(...)`
  — reference resolution (transitive; consistency cross-checks; ≥ 1
  groundable substrate else structural failure; retrieval scope =
  screened-in corpus + selection prior, `RETRIEVAL_UNIT_CAP` guard) →
  artefact mint → section proposal
  (validated; directive override) → per section: the section loop (turns
  ≤ `SECTION_TURN_CAP`; tools per substrate; budgets) → typed-claim
  validation (per-type, substrate-gated) → batched judge call → one
  loop-free reword-down repair + one re-judge → block/unit/annotation/
  citation writes → roll-up row (last statement) → synthesis summary in
  `component.completed`.
- Ships **two backend seams, three prompt surfaces**: `SynthesisBackend`
  (+ OpenAI, stub) carrying **`synthesise_sections_v1`** and
  **`synthesise_section_v1`** (system prompt + the three tool schemas,
  versioned as one surface; the OpenAI form runs the bounded tool-calling
  loop), and `GroundingJudgeBackend` (+ OpenAI, stub) carrying
  **`grounding_judge_v1`** — the repo's fifth–seventh product prompts,
  all lead-authored, versioned, recorded in provenance.
- Ships the **three scoped tools**: **`search_chunks`** (hybrid retrieval
  over the resolved document scope's stored embedding-unit vectors +
  lexical scoring, rank-fused, top-k under plan-pinned caps; in-memory
  over JSONB vectors guarded by `RETRIEVAL_UNIT_CAP` — no index, no new
  dependency; behind a swappable helper seam = the `retrieve` seam's
  first increment; query embeddings via the existing 009
  `EmbeddingBackend`) · **`query_findings`** (deterministic,
  project-guarded findings-layer reads — discharges the 012 recorded
  deviation in full, agent-invoked) · **`lookup`** (closed query
  vocabulary v1 over canonical project state: appraisal by doc,
  classification by doc, selection rationale/summary,
  `search_coverage_record`, characterisation coverage/themes, grouping
  groups, **tags by document / documents by tag / tag aggregates by
  type and asserter** — identifier/filter-addressed, side-effect-free,
  scoped to this project and the referenced runs).
- Adds **one table — `synthesis_result`** — via one Alembic migration
  (gated change 1; table count 24 → 25, migration 13),
  project-scope-guarded.
- Registers `"synthesise"` in `COMPONENT_REGISTRY` (requires
  `evidence_scope_id`; **all four run references optional** —
  deepest-given resolves the rest transitively; ≥ 1 groundable substrate
  enforced at execution, structural failure otherwise; gated change 2);
  `run_harness` gains **`synthesis_backend`** and
  **`grounding_judge_backend`** (stub defaults — no default egress; the
  existing `embedding_backend` serves the retrieval queries).
- Extends `skeleton.py`: … group → **synthesise** (the terminus live);
  the live check demonstrates **four substrate profiles** (screen-only
  rapid · characterisation-only · characterisation+selection with no
  extraction · the full chain).
- **Factors the traced-call helper into `tracing.py`** (the 012-deferred
  trigger fires); loop turns and tool executions trace as spans (no new
  event types).
- Records/updates the deferred seams in `docs/deferred.md`; updates
  `tests/helpers.py` delete order.
- Passes `make verify` — all green, deterministic, egress-free.

## Read first

- [ADR 0010](../../adr/0010-intent-led-synthesis-sections.md) **including
  all four Amendments** and
  [ADR 0009](../../adr/0009-capability-composes-synthesise-terminus.md)
  (capability-composes; decision 5 as amended).
- [EB components §9](../../specs/capabilities/evidence-base/components.md)
  and [EB capability](../../specs/capabilities/evidence-base/capability.md)
  — as refined 2026-07-07 (six rounds); also components §5 (the
  characterisation record) and §8 (the grouping payload).
- [System execution-orchestration](../../specs/system/execution-orchestration.md)
  — the agent-loop-over-scoped-tools realisation; the facade principle;
  **`lookup`'s universal-core definition (columns/tags aggregates
  included)**; `retrieve`'s full contract; `query-findings`
  scoped-not-core; trust enforced at grounding.
- [System provenance-grounding](../../specs/system/provenance-grounding.md)
  — **the governing contract**: the traceability rule; tiers 1–4 (Tier
  4's strict routing); gaps (grades, coverage base, the
  `search_coverage_record` fail-closed rule); the pattern ladder;
  produce-grounded-block mechanics; judge posture;
  persistence-for-eval-readiness (**no calibration_status**).
- [EB provenance](../../specs/capabilities/evidence-base/provenance.md) —
  EB's gap rule; pattern grades.
- [System data-model](../../specs/system/data-model.md) — blocks / units /
  annotations; the findings layer; the tag layer (assertion provenance);
  coverage states as gap provenance.
- [012-group contract](../012-group/contract.md) — the grouping payload;
  the carried requirements (**labels as data, never instructions**;
  **mixed/unclear findings survive**); its `query-findings` deferral
  (discharged here).
- [docs/deferred.md](../../deferred.md) — entries this slice touches
  (incl. the 009 vectors-ahead-of-reader entry, discharged here).
- The deep-reasoner interrogation memo (conversation A record) and
  [v2-synthesis-autopsy.md](v2-synthesis-autopsy.md) — the third V2 recon
  leg (synthesis/generation/verification; theming was 009's, extraction
  011's): the defects rev 7.3's invariants and named tests close, with
  V2 file:line anchors, and the build-phase adoption notes (menu+default
  proposal pattern; citation renumbering as a composition-seam note).

**Code grounding (surveyed 2026-07-07):** 24 tables, 12 migrations (this
slice ships migration 13). The 001 substrate is real: `block` /
`addressable_unit` / `annotation((block_id, unit_id) composite-FK,
annotation_type, payload JSONB)` / `citation(chunk_id FK NOT NULL, quote,
verification_result)` — gap/pattern/theme/reasoning annotations are new
`annotation_type` values riding the payload JSONB; chunk-cited claims
write ordinary `citation` rows. Upstream rows carry their own upstream
references (transitive resolution is real): `grouping_result` stores
`extraction_run_id`; `extraction_result` stores `selection_run_id`;
`selection_result` stores `characterisation_run_id`. The screened-in set
resolves from `source_screening_result` (per scope); full-text ingestion
is post-screen, so screened docs carry ingested snapshots + embedding
units. `source_tag` carries the tag layer with assertion provenance
(`asserted_by`). `search_coverage_record` (007): the corpus-promotion
gate for gap claims. `chunk_embedding` (009): one JSONB vector per
embedding-unit, eager, **no reader yet**; `EmbeddingBackend` +
`embedding_backend` harness param exist (stub vectors deterministic).
`characterisation_result` carries `coverage` + `themes` + provenance.
Findings carry extract-verified anchors (verified `chunk_id`, quote,
match status, spans). `grouping_result.groups` carries per group: label,
description, member values, member finding ids, size, direction spread
(+ residuals + overall). `quote_verify.py`'s `build_basis` +
`QuoteMatcher.find` verify verbatim quotes against frozen chunks
deterministically. Backend pattern: protocol + stub + OpenAI class with
pydantic `response_format`, module-constant prompt + `PROMPT_VERSION`,
caller-owned budget, validation separated from the call (`gpt-5-mini`
floor). **No agent loop exists anywhere yet** — the loop runner, tool
schemas and per-turn tracing are new machinery. Component wiring:
registry entry + Config fields → context dataclass →
`_run_scope_component` → `component.*` events.

## Scope

### Design decisions embedded here (approve or flip at this gate)

1. **The complete produce-grounded-block mechanism lands in one slice** —
   the deterministic legs **and** the LLM judge **and** the bounded
   loop-free reword-down repair. Judge *calibration* stays
   eval-workstream territory; this slice's bar is mechanism correctness.
2. **Substrate-conditional, never mode-forked — all references
   optional.** `characterisation_run_id`, `selection_run_id`,
   `extraction_run_id`, `grouping_run_id` all optional; deepest-given
   resolves upstream transitively from the referenced rows' own
   provenance; explicitly-passed shallower references must match the
   resolved ones (mismatch = structural failure); **≥ 1 groundable
   substrate required** (zero → structural failure, no artefact). Claim
   types, tools and sectioning inputs are gated by the resolved
   substrate (Goal table). **Retrieval scope**: the screened-in corpus
   always — screen bounds reading; **a referenced selection is a soft
   ranking prior** (look-here-first boost, recorded in provenance;
   per-citation origin recorded: selected | unselected_screened) —
   select gates extraction cost, never reading (the data-model's
   agents-are-never-penned-in principle). Unit count above the
   plan-pinned **`RETRIEVAL_UNIT_CAP`** fails structurally naming the
   cap (fail-closed; the index-backed `retrieve` slice is the upgrade —
   never a degraded sample). The orchestrator's component freedom is
   preserved by construction: any coherent registry subset synthesises,
   including the rapid screen-only run.
3. **Blocks are real information-layer rows at claim grain.** Per block:
   one `block` row (claims' prose joined deterministically;
   `content_hash` per 001), one `addressable_unit` per claim, and per
   claim-unit the annotation its type demands: **citation annotation**
   (finding/chunk), **pattern annotation**, **theme annotation**,
   **gap annotation** (grade + coverage base + evidence refs),
   **reasoning annotation** (visible Tier-4 label + strict-routing
   verdict). `citation` rows link cited claim-units to frozen chunks.
4. **Synthesise mints the artefact — one per run, titled from the scope
   intent** (verbatim, bounded, deterministic) — and binds blocks in
   proposal order. Composition conventions stay at their seams. Re-run =
   new run = new artefact + new blocks. Zero groundable substrate →
   honest structural failure, no artefact, no roll-up row.
5. **The intent-led section proposal.** `synthesise_sections_v1`
   (+ ≤1 repair): intent + available substrate summaries (id-keyed) →
   validated section list (1..`SECTION_CAP`; bounded non-generic
   titles/focus; group assignments, where groups exist, ⊆ real group
   ids, overlap allowed, exhaustiveness not required — uncovered groups
   → `groups_unsectioned`). The fail-closed **`context["synthesis"]`
   directive** can supply the list; executed source recorded. The same
   directive may carry an optional **`retrieval_boosts`** object
   (rev 7.5 — select's directive vocabulary and disciplines exactly):
   clamped positive multiplicative weights over columns (`origin`,
   `primary_evidence_type`, `text_basis`), tags, and appraisal tier —
   parsed fail-closed per the select precedent, with the 010-review
   semantics carried whole: **malformed structure fails closed; unknown
   columns/tags match nothing and surface via `unmatched_boosts`, never
   fatal**. Boosts **re-weight, never exclude**; default = none;
   executed boosts recorded in provenance. This is the surface the
   future source/evidence policy compiles into (the 010 pin), and the
   plan-as-object's quality-prior ruling honoured: steerable
   per-directive, never a baked default.
6. **The section loop: one agent-loop surface, three read-only tools,
   hard caps — sections written serially with a rolling claim ledger.**
   Sections are written **in proposal order** (v3.0 execution is serial
   by spec, so this costs nothing). Per section,
   `synthesise_section_v1` (system prompt + tool schemas, one versioned
   unit) runs the bounded tool-calling loop seeded with (id-keyed
   data): intent, section spec, available substrate summaries, — when
   extraction ran — the section's member findings + computed spread,
   and the **rolling claim ledger**: the typed claims of every prior
   section (claim text, type, cited ids, flags — which, since block
   content is the claims' texts joined, *is* the sections as written,
   in structured form), marked **context, never evidence** (rev 7.2):
   prompt rules say don't re-make a claim already made, connect rather
   than repeat; ledger records are not citable — cited ids must be
   finding/chunk ids, structurally, so sibling-content citation is
   impossible by construction (the citation-scope rule). Tools per
   decision 2's gating:
   `search_chunks` — a staged pipeline (rev 7.5): **content-only hybrid
   relevance** (embedding cosine + lexical, rank-fused; metadata never
   feeds the relevance leg — the 010 signal-attributability rule) →
   **arithmetic soft priors** (the selection look-here-first boost where
   referenced + the directive's `retrieval_boosts`; transparent,
   re-weight-never-exclude, per-chunk contributions attributable) →
   **cross-encoder reranker stage** (`ChunkRerankerBackend` protocol —
   the retrieval-profile seam's cross-encoder slot the spec assigns to
   Bedrock Rerank; **v1 default = pass-through, recorded as
   `reranker: "none"`**; the live backend and its `run_harness`
   injection point land with the Bedrock integration slice — no public
   kwarg ships while nothing live exists, the V2 dead-config lesson) →
   plan-pinned `SYNTH_CHUNK_TOP_K` / `SYNTH_CHUNK_CHAR_BUDGET` caps.
   Id-keyed frozen chunk records out **with per-chunk origin: selected |
   unselected_screened**; deterministic given stored vectors + query;
   the **screened-in corpus** only ·
   `query_findings` (the referenced extraction's findings only) ·
   `lookup` (closed query vocabulary v1 incl. the tag layer; this
   project and the referenced runs only).
   Loop bounds, all plan-pinned and enforced in code: `SECTION_TURN_CAP`
   generation turns (tool calls consume turns; the claims emission is a
   turn), per-call and gathered-context budgets, closed tool set
   (unknown tool name = validation error, never executed), **read-only
   always, no egress verb** (`search` remains acquire's alone). Cap
   exhaustion forces the claims emission with whatever was gathered
   (`turn_cap_hit`, flagged). Every turn and tool execution traces as
   spans; tool-call counts + gathered ids land in provenance. **The
   loop is the component's internal realisation** (facade principle):
   the capability sub-agent — the standing capability-run seam, skeleton
   standing in — invokes synthesise as one tool; no second agent
   identity.
7. **Six claim types, each with its own deterministic validation,
   substrate-gated; the model never authors a finding quote.**
   - **finding** (extraction referenced) — `cited_finding_ids ⊆ the
     section's finding set`; code resolves to extract-verified anchors
     and re-runs the deterministic presence check (abstract-basis
     re-location; unlocatable/`failed` anchors → no fabricated citation
     row, `quote_unverified`, weakly-grounded cap, never dropped).
   - **chunk** (screened-in ingested documents present) — verbatim
     quote + source chunk record id **from tool-returned results only**
     (citing
     an unreturned id rejects — co-emission enforced structurally);
     claimed location untrusted — `QuoteMatcher` verifies against the
     whole document basis, verified spans become the citation rows;
     presence failure rejects (one repair), still-failing → **excluded
     and counted**.
   - **pattern** (characterisation for coverage counts;
     extraction/grouping for spreads) — stated counts must equal the
     computed value.
   - **theme** (characterisation for themes; grouping for facet
     groups) — references the clustering by id, validated against the
     referenced row; softest interpretive grade, base-labelled.
   - **gap** (always) — grade + coverage base required
     (sparsity-grade needs the characterisation coverage); corpus-level
     phrasing fail-closed on a non-`inadequate` `search_coverage_record`
     (else degraded and counted); inferred gaps visibly labelled;
     `not_selected`/`not_extracted` never license absence.
   - **reasoning** (always) — uncited, visibly Tier-4-labelled, bounded
     per block, judge strict-routed, never in roll-ups.
   Claims of a type the substrate doesn't support reject (one repair).
   No silent uncited path: every claim is cited, validated, or visibly
   labelled. Two invariants from the V2 synthesis autopsy
   ([v2-synthesis-autopsy.md](v2-synthesis-autopsy.md), rev 7.3):
   **(i) renderings never escape verification** — any structured or
   tabular rendering of block content decomposes into these same typed
   claims and passes the same per-type verification (V2's
   deterministically-rendered interventions table bypassed grounding
   entirely because grounding was prose-regex-based — its single worst
   defect); **(ii) citation-bearing evidence is verbatim** — the writer
   cites only frozen-chunk text and extract-verified anchors;
   model-authored summaries (substrate summaries, group descriptions,
   ledger entries) inform sectioning and emphasis but never serve as
   citation evidence (V2 primed its writer on re-summarised truncated
   chunks — paraphrase-of-paraphrase drift).
8. **The judge is `grounding_judge_v1` — a separate, single-call,
   schema-constrained surface: verification is non-agentic.** Batched
   per block, single-lane, reading the cited passages
   (`synthesis_envelope_v1` — the cited chunks' full frozen text).
   Judges cited claims (full lane) and reasoning claims (strict-routing
   only); pattern/theme/gap claims are deterministically validated,
   not judged. **Maker ≠ checker at the surface level**: the judge has
   its own backend seam and prompt, no tools, no loop — the section loop
   never grades its own homework; the seam permits a heterogeneous judge
   model at the Bedrock swap. Persistence for eval-readiness on the
   annotation payload; full I/O on Langfuse; **no calibration_status
   anywhere**.
9. **The verify loop rewrites down, bounded by `REPAIR_ROUND_CAP` = 1
   (plan-pinned).** The judge's per-claim rationales are not advisory —
   they drive the rewrite: on validation rejection or any
   `unsupported_mis_cited`, one reword-down regeneration **over the
   already-gathered evidence** (no new tool calls; the failing claims +
   rationales + the claim-less instruction in the prompt), then one
   re-judge — the spec's "bounded loop; its job is claim↔evidence
   convergence, not pass/fail", with the primary repair being reword
   *down*. Round-count calibration belongs to the eval seam; still-
   failing claims land soft-flagged (decision 7's one exclusion aside).
   Proposal: one regeneration on validation rejection. Call budget known
   pre-run as a **maximum**: proposal ≤ 2 · per section ≤
   `SECTION_TURN_CAP` + 2 generation calls + ≤ `SECTION_TURN_CAP`
   embedding calls → total ≤ 2 + `SECTION_CAP` × (`SECTION_TURN_CAP` +
   2). Backend failure after retries fails the component honestly
   (`component.failed`, no roll-up row); blocks already written remain
   and the failure payload names them.
10. **Descriptive, never evaluative — absence disciplined, not banned.**
    Negative rules deterministically assertable on the built surfaces;
    the citable-bar flag-not-block rule honoured by the weakly-grounded
    mechanism (policy-conditioned flagging = recorded seam).
    **Mixed/unclear findings are first-class throughout.**
11. **`query-findings` is discharged in full** (agent-invoked in the
    loop — the 012 deferral's named consumer; entry closed as landed);
    the orchestrator-level capability-run architecture remains its own
    seam.
12. **Component wiring mirrors 004–012.** Registry entry per decision 2;
    `SynthesiseContext` via `functools.partial`; `_run_scope_component`;
    roll-up row last; re-run → new run_id; same-run re-execution loud;
    `component.completed` carries the summary; **no new event types**.
13. **Stubs are sentinel-driven; the suite is deterministic and
    egress-free.** `StubSynthesisBackend` drives **scripted tool-call
    sequences through the real loop runner** (fixture-declared turns
    across all three tools — exercising the cap, unknown-tool rejection,
    substrate gating, scope resolution, budgets and cap-exhaustion
    forcing for real) and emits typed claims across all six types (real
    anchor text, real record numbers, fabricated-quote and
    corpus-absence sentinels); `StubGroundingJudgeBackend`
    sentinel-driven; retrieval runs on 009's deterministic stub vectors.
    Determinism tests fix intent as input.
14. **All three prompt surfaces carry the standing injection posture —
    and the loop tightens it.** Intent, substrate summaries,
    coverage-record summaries, finding text, anchor quotes, tool-returned
    chunk text, lookup results (incl. tag labels — model-generated and
    provider text, data-not-instruction) and labels enter as **id-keyed
    JSON data records**; responses and tool calls schema-constrained;
    the tool set closed, read-only, substrate-scoped, code-enforced.
    Hijack bounds: a hijacked loop reads more in-corpus frozen text
    (cap-bounded) and emits mis-claims that face the unchanged claim
    bar; a hijacked judge mis-tiers within a closed enum; a hijacked
    proposal mis-shapes sections whose every claim is still verified.

### Schema

**Gated change 1 — one new table** (one migration; table count 24 → 25;
exact DDL plan-pinned, shape here binding):

```
synthesis_result  synthesis_result_id PK · project_id FK→project
                  · evidence_scope_id · run_id
                  · characterisation_run_id (resolved reference, NULLABLE)
                  · selection_run_id (resolved reference, NULLABLE)
                  · extraction_run_id (resolved reference, NULLABLE)
                  · grouping_run_id (executed reference, NULLABLE)
                  · artefact_id FK→artefact NOT NULL (zero-substrate runs
                      fail structurally and write no row at all)
                  · synthesis_provenance JSONB NOT NULL (all three
                      prompt-surface versions incl. tool schemas, models,
                      judge envelope-policy version, backend modes,
                      per-phase call/turn/repair counts, the substrate
                      profile (which references resolved) + the
                      retrieval scope (screened-in doc/unit counts; the
                      selection prior + its boost where referenced; the
                      executed retrieval_boosts + unmatched_boosts; the
                      reranker mode ["none" v1]), the
                      section set + source [proposal|scope_context] +
                      caps (SECTION_CAP · SECTION_TURN_CAP ·
                      SYNTH_CHUNK_TOP_K · SYNTH_CHUNK_CHAR_BUDGET ·
                      RETRIEVAL_UNIT_CAP · REPAIR_ROUND_CAP),
                      per-section tool-call counts + gathered-id hash,
                      and the inherited chain base per resolved
                      reference)
                  · blocks JSONB NOT NULL (per section: title/focus,
                      block_id, assigned group ids where present,
                      tool-call count, claim counts by type
                      [finding|chunk|pattern|theme|gap|reasoning], tier
                      distribution, unsupported/weakly-grounded counts,
                      citation verified/unverified counts, citations by
                      origin (selected | unselected_screened),
                      chunk_claims_rejected, gap_claims_degraded,
                      repair_taken, turn_cap_hit)
                  · counts JSONB NOT NULL (blocks_written, sections_total,
                      claims_total by type, claims by verdict lane,
                      citations_verified, citations_unverified,
                      citations_from_unselected,
                      chunk_claims_rejected, gap_claims_degraded,
                      tool_calls_total, findings_cited_distinct,
                      findings_total where extraction ran, groups_total /
                      groups_unsectioned where grouping ran)
                  · flags JSONB NOT NULL (groups_unsectioned ·
                      unsupported_claims_present · weakly_grounded_present
                      · chunk_claims_rejected · gap_claims_degraded ·
                      turn_cap_hit · repair_path_taken ·
                      uncited_sections — where true; the last flags any
                      section emitted with zero cited claims, the V2
                      zero-evidence-section lesson)
                  · created_at
                  Composite FKs (evidence_scope_id, project_id),
                  (run_id, project_id) — cross-project guards
                  FK (evidence_scope_id, characterisation_run_id) →
                      characterisation_result (evidence_scope_id, run_id)
                  FK (evidence_scope_id, selection_run_id) →
                      selection_result (evidence_scope_id, run_id)
                  FK (evidence_scope_id, extraction_run_id) →
                      extraction_result (evidence_scope_id, run_id)
                  FK (evidence_scope_id, grouping_run_id) →
                      grouping_result (evidence_scope_id, run_id)
                  UNIQUE (evidence_scope_id, run_id)
```

**`synthesis_result` is a run-scoped execution roll-up, not the artefact
store** (clarity, folded post-rev-7.4 at the user's question): the
repository of all artefacts — for every current and future capability —
is the 001 substrate (`artefact` + `block`/`addressable_unit`/
`annotation`/`citation`); this table is the component's roll-up sibling
of `characterisation/selection/extraction/grouping_result`, pointing at
its artefact via `artefact_id`. Future capabilities mint artefacts into
the same substrate with their own roll-ups; an artefact
capability-discriminator column and the versioning grain arrive with
their first readers (recorded seams).

No existing-table changes. Downgrade drops the table. `tests/helpers.py`
`delete_project_data` gains it in FK-safe order.

### Out of scope

- **Corpus-scale retrieval** — beyond `RETRIEVAL_UNIT_CAP` or over
  unscreened content — and the **full `retrieve` tool** (index-backed
  hybrid with profiles): the scoped `search_chunks` tool is the recorded
  first increment behind a seam the retrieve slice upgrades.
- **Agent loops anywhere else** — exactly one loop surface (the section
  loop); the proposal and judge stay single-call; the orchestrator-level
  capability-run architecture stays its own seam.
- **Plan-compile section machinery** (the directive is its compile
  target) · **composition conventions** · **weighted consensus /
  strength roll-up** (⏸; never-contribute constraints restated incl.
  gaps + reasoning) · **block summaries / artefact summary /
  faithfulness judging** · **block versioning beyond `version=1`** ·
  **residual-bucket prose** · the **landscape→synthesis steer-point** ·
  judge-envelope widening + re-gather repair (with `retrieve`) ·
  **`implementation_context_finding`**, cross-schema linkage,
  graph-structured synthesis (⏸).
- **Judge calibration / synthesis-quality / retrieval-quality evals** —
  the eval workstream owns them; this slice's bar is mechanism
  correctness.

## Constraints & approval gates

**Four gated changes (approval needed at this gate):**

1. **Schema** — one new run-scoped table (above), one migration; table
   count 24 → 25. No existing-table changes.
2. **Public interface** — the `"synthesise"` `COMPONENT_REGISTRY` entry
   (requires `evidence_scope_id`; **all four run references optional**,
   transitively resolved, consistency and ≥-1-substrate enforced
   fail-closed) + `run_harness` gains optional **`synthesis_backend`**
   and **`grounding_judge_backend`** (stub defaults). No renames ride
   this slice.
3. **Runtime egress — three new generation surfaces + embedding-query
   use** (the repo's fifth–seventh product prompts):
   `synthesise_sections_v1` · `synthesise_section_v1` (**multi-turn**:
   each loop turn is a generation call carrying gathered in-corpus
   frozen chunk text, finding records incl. verbatim quotes,
   canonical-state lookups incl. tags, and the user's intent) ·
   `grounding_judge_v1` (cited chunks' full frozen text). Fixture corpus
   openly licensed; full-I/O Langfuse traces (every loop turn and tool
   result) flagged for approval.
4. **The repo's first agent loop** — a capability-class change: the
   section loop gains bounded tool-calling discretion (closed read-only
   three-tool set, hard turn cap, code-enforced substrate scope). Every
   prior contract declared "no agent loop, no tools" — this contract
   deliberately crosses that line for exactly one surface, per the
   spec's own declared realisation and ADR 0010's amendments.

No new dependency rides this slice (`openai`, `langfuse`, `pydantic`
cover it; cosine + lexical scoring are stdlib/in-memory).

**Explicitly not crossed:** exactly three prompt-bearing surfaces and
exactly one loop surface; no tool writes; no egress verb in the tool set;
no new dependency; no auth/tenancy/CI change; no existing-table change;
no new event types; no tag writes; no retrieval index/extension.

**Spec flow-backs: already landed with ADRs 0009 + 0010 (four
amendments)** — approved in this contract's gate conversation. Remaining
deferrals ride `docs/deferred.md`.

## Public / private boundary

- On the live path, what leaves: substrate summaries (coverage, themes,
  group summaries, selection rationale, coverage-record summaries, tag
  aggregates), per-section finding records (source-named references,
  statistics, **verbatim quotes**), **tool-retrieved frozen chunk text
  from the resolved document scope** (accumulating across loop turns),
  canonical-state lookup results, cited chunks' text, the user's
  **intent** (also as tool-query text to the embedding API), and
  model-generated labels — all fixture-corpus-derived (openly licensed
  by construction) — to the OpenAI API; full-I/O traces (every loop turn
  and tool result) to the user-operated dev Langfuse. For arbitrary
  future corpora this is source-derived text and user-authored intent
  inheriting the project's sensitivity class — private-by-default
  otherwise.
- Committed artifacts (schema, prompt text, tool schemas, roll-up
  shapes, verification counts) are public-safe. **Block content, claims,
  section titles/focus, gap texts, tool queries and judge rationales are
  model-generated text over source-derived input** — public-safe for the
  fixture corpus, private-by-default otherwise; **untrusted model output
  as data**: bounded and validated at write, rendered escaped, never
  executed. Carried forward: block content, section specs and judge
  rationales enter any future prompt as data records, never
  instructions.

## Model route

All three generation surfaces behind the two backend seams —
`gpt-5-mini`-class floor (the 009 nano lesson binding) → Bedrock at the
seam swap, unchanged. Tool-query embeddings ride the existing 009
embedding surface.

- **`synthesise_sections_v1`** — the section proposal; bounded list out;
  sections name aspects of the question and the evidence. An
  **answer-shaped lead section** ("what the evidence shows on the
  question" — descriptive, fully cited, synthesising across the
  substrate) is explicitly legal and encouraged where the intent asks a
  direct question (rev 7.1 — the spec's grounded key-findings idea in
  section form); what is prohibited is a **verdict-section** (one whose
  premise is an evaluative conclusion or recommendation — "X is the best
  option"); no generic/catch-all sections; assignments only from
  supplied ids.
- **`synthesise_section_v1`** — the section-loop surface (system prompt
  + `search_chunks`/`query_findings`/`lookup` tool schemas, versioned as
  one unit); typed claims (finding | chunk | pattern | theme | gap |
  reasoning, substrate-gated); negative rules: descriptive only; absence
  only as graded gap claims with their base; spreads/counts as given or
  tool-read, never invented; mixed/unclear reported, never aggregated
  away; quotes verbatim from tool-returned text only; claim within what
  the cited evidence supports; gather before writing, stop when
  saturated (the cap enforces it regardless).
- **`grounding_judge_v1`** — the classifier (a separate single-call
  surface — decision 8); closed verdict enum + `weakly_grounded` +
  required rationale for cited claims; strict-routing for reasoning
  claims; topical relevance ≠ support.

All three are **prompt-bearing, lead-authored, versioned** (tool schemas
included), recorded in provenance, event payloads and (judge) annotation
payloads. The judge rubric is lead-only per AGENTS.md.

## Disciplines binding this slice

- **The traceability rule is the slice** — every claim is
  cited-and-verified, deterministically validated, or visibly labelled;
  no fourth state, no silent promotion, no post-hoc citation path.
  Intent and tool discretion shape emphasis and evidence-gathering,
  never verification; **verification is non-agentic** (code legs + a
  separate single-call judge surface; maker ≠ checker).
- **Honest absence** — absence only as graded gap claims with their
  coverage base; corpus-level fail-closed on the coverage record;
  `not_selected`/`not_extracted` never license absence.
- **Flag, don't drop** — failed anchors, unsupported/weakly-grounded
  claims, degraded gaps, uncovered groups and cap-forced emissions land
  visible with status; the one exclusion is fabricated chunk quotes —
  excluded **and counted**.
- **Bounded agency** — one loop surface; closed read-only three-tool
  set; code-enforced caps and substrate scope (`RETRIEVAL_UNIT_CAP`
  fail-closed); cap exhaustion forces emission, never extends.
- **Substrate-conditional, never mode-forked** — all references
  optional; claim/tool availability derives from what resolved; the
  orchestrator's registry freedom is preserved by construction.
- **Deterministic where claimed** — presence checks, citation
  resolution, offsets, computed values, per-type validation, tool
  ranking (given stored vectors + query), reference/scope resolution,
  cross-checks, ordering and writes; generation calls bounded by the
  pre-run maximum; determinism tests fix intent as input.
- **Model only what behaves**; **never silent, never fake** — as the
  standing disciplines; reference-consistency, scope-cap and
  computed-value mismatches are structural failures.

## Stop conditions

- Any gated change (schema · public interface · egress · the agent loop)
  not yet approved, or any change beyond them (existing-table change, a
  fourth prompt surface, a second loop surface, a new or write-capable
  tool, new dependency, retrieval index/extension, consensus/summary
  machinery, new event types).
- Any *suite or library-default* code path would perform network I/O.
- The loop wants more than the three read-only tools, wants to write,
  wants out-of-scope chunks, or wants an uncapped turn budget — halt.
- The resolved scope exceeds `RETRIEVAL_UNIT_CAP` and any pressure
  exists to sample or degrade — the cap is fail-closed by design; the
  scale answer is the `retrieve` slice, a plan-gate decision.
- The synthesis wants evaluative output, free-phrased absence, or
  composition conventions — halt.
- The claim/citation model can't express something without weakening
  verification — design change; halt, never weaken the bar silently.
- `make verify` red with unclear root cause; or the turn/token budget is
  spent.

## Acceptance checks

- `make verify` — green, deterministic, zero egress (socket-deny covers
  synthesise round-trips across substrate profiles including the
  scripted stub loop).
- **One manual live check, four substrate profiles** (evidence in
  verification.md): skeleton end-to-end with `OPENAI_API_KEY`
  (+ `LANGFUSE_*`) against the fixture corpus — (a) **screen-only
  rapid** (no characterise: chunk-grounded answer over the screened-in
  set; substrate profile + scope recorded; no landscape, honestly); (b)
  **characterisation-only** (the landscape degenerate case); (c)
  **characterisation + selection, no extraction** (chunk-grounded
  sections with the selection prior visibly steering ranking, zero
  extract calls; any unselected-but-screened citation carrying its
  origin honestly); (d) **the full chain** (all claim types; the loop visibly gathering; tier
  distribution, gap grades/bases, degradations/exclusions and any
  `turn_cap_hit` shown honestly; repair path exercised or its absence
  noted; `groups_unsectioned` honest). All three surfaces + tool turns +
  embedding queries visible in dev Langfuse (versions, tokens/cost) with
  run-level scores; per-run counts and an honest cost note; keys absent
  from captured output.
- Deterministic vs AI eval: suite checks deterministic (stubs; scripted
  loop); section/prose/retrieval quality and judge calibration are eval
  territory — this slice's bar is mechanism correctness, invariant
  enforcement, honest flags and provenance fidelity.

## Verification evidence expected

`verification.md` must include:
- `make verify` table with pass counts; socket-deny result named.
- Migration roundtrip clean; table count 25.
- Named test results: **reference resolution** (all references optional;
  deepest-given resolves upstream transitively; explicit shallower
  references must match resolved — mismatch structural; missing
  referenced rows → structural failure; **zero groundable substrate →
  structural failure, no artefact, no row**; substrate profile
  recorded), **retrieval scope + prior** (scope = the screened-in corpus
  always — a screened-out or foreign document's chunks never returned;
  a referenced selection boosts ranking, never filters — an
  unselected-but-screened chunk is reachable and its citation records
  origin `unselected_screened`; boost + scope doc/unit counts in
  provenance; **unit count > RETRIEVAL_UNIT_CAP → structural failure
  naming the cap, no call, no degraded sample**; **directive
  retrieval_boosts re-weight, never exclude** — a zero-relevance chunk
  is never surfaced by boost alone and a boosted-away chunk is still
  reachable; clamps enforced; malformed boosts fail closed; unknown
  columns/tags match nothing and surface via `unmatched_boosts`; the
  relevance leg is content-only (metadata never enters the
  embedding/lexical scoring — test-asserted); **the reranker stage is
  pass-through v1 and recorded** (`reranker: "none"` in provenance; the
  protocol seam exercised by a test-scoped fake)), **substrate gating**
  (chunk claims/`search_chunks` absent without screened-in ingested
  docs; finding claims/`query_findings` absent without an extraction;
  coverage-pattern, characterise-theme and sparsity-gap claims absent without
  a characterisation; group-theme claims absent without a grouping;
  unsupported claim types reject),
  **section proposal validation** (caps, bounded non-generic titles,
  real assignments, `groups_unsectioned` counted, malformed directive
  fails closed, source recorded), **the loop** (turn cap enforced —
  exhaustion forces emission + `turn_cap_hit`; unknown tool rejected,
  never executed; tools read-only and scoped — foreign-project or
  out-of-scope content never returned, test-enforced; per-call and
  gathered-context budgets enforced; tool-call counts + gathered-id hash
  in provenance; scripted stub sequences drive the real runner; repair
  is loop-free — no new tool calls, test-asserted), **the rolling claim
  ledger** (sections written in proposal order; section N's seed carries
  sections 1..N-1's typed claims marked context-never-evidence; ledger
  records are structurally uncitable — cited ids must be finding/chunk
  ids; determinism unaffected, test-asserted), **`search_chunks`
  ranking** (hybrid fusion deterministic on stub vectors; top-k and char
  budgets enforced), **`lookup` discipline** (closed vocabulary — unknown
  query kind rejected; project/run-scoped; side-effect-free; **tag-layer
  queries covered**: tags by doc, docs by tag, aggregates by
  type/asserter), **finding-claim citation resolution** (ids ⊆ the
  section's finding set; anchors reused verbatim; abstract-basis
  re-location; failed/unlocatable anchors → `quote_unverified` +
  weakly-grounded cap, never dropped), **chunk-claim verification**
  (quotes only from tool-returned ids; presence-checked against the
  whole document basis; verified spans become the citation rows;
  fabricated quote → reject, one repair, then excluded and counted),
  **gap-claim discipline** (corpus-level phrasing without a
  non-`inadequate` coverage record → fail-closed degradation, counted;
  sparsity-grade gaps rejected without characterisation coverage;
  acknowledged sparsity validated numerically; inferred labelled; base
  always present), **theme-claim discipline** (referenced clustering
  ids validated; softest-grade label + base), **reasoning-claim
  discipline** (visibly labelled; strict-routing sentinel flagged;
  per-block count bounded), **claim/unit integrity** (every cited claim
  ≥ 1 citation target; annotations exist iff their claim does, on that
  claim's unit; offsets exact; composite-FK integrity; content_hash
  correct), **judge semantics** (single-lane enum; rationale required;
  verdict + judge provenance + envelope version persisted; judge input
  includes cited chunk text; the judge surface is distinct from the
  writer surface — maker ≠ checker structural; cited and reasoning
  claims judged; pattern/theme/gap not judged), **repair semantics**
  (bounded exactly as decision 9; budgets test-asserted; exhaustion →
  flags, claims retained except fabricated chunk quotes; **a passing
  claim survives a sibling's repair verbatim** — the V2
  whole-section-regeneration regression guard), **caps bind + honest
  evidence floors** (the plan-pinned constants are the values enforced
  on the live path — configured cap == binding cap, test-asserted; V2's
  config caps were dead code while a module constant governed; a section
  emitted with zero cited claims → `uncited_sections` flagged, never
  silent), **fabricated quotes never persisted** (a chunk-claim quote
  failing presence produces no citation row and no stored quote anywhere
  — V2 persisted hallucinated quotes with support intact), **rendering
  decomposition** (structured/tabular renderings of block content
  decompose into typed claims through the same verification — no
  prose-regex escape hatch),
  **flag-not-drop** (unsupported / weakly-grounded / degraded-gap claims
  persist visibly; mixed/unclear visible end-to-end), **descriptive
  posture** (negative rules asserted on all three built surfaces;
  injection-shaped labels, quotes, chunk text, lookup results — tag
  labels included — or coverage summaries land as inert data),
  **artefact/composition v1** (one artefact per run, intent-derived
  bounded title; proposal-ordered binding; re-run → new artefact;
  same-run re-execution loud; backend failure → `component.failed`, no
  roll-up row, prior blocks named), **determinism** (two stub runs with
  fixed intent → identical payload columns, block content and hashes;
  tool ranking deterministic), **provenance required keys** (three
  surface versions incl. tool schemas, envelope policy, substrate
  profile + resolved scope, section set + source, all caps incl.
  RETRIEVAL_UNIT_CAP, per-section tool-call counts + gathered-id hash,
  per-phase call counts, the inherited chain base per resolved
  reference), delete-order integrity.
- Live-run evidence per the manual check above (four profiles).
- Public-safety confirmation (egress was fixture-corpus text + intent
  only; traces on the user-operated instance; keys clean).
- Deferred seams recorded/updated in `docs/deferred.md`: **corpus-scale
  retrieval** + **full `retrieve` tool** (the `search_chunks` tool = its
  first increment; `RETRIEVAL_UNIT_CAP` = the fail-closed boundary; the
  009 vectors-ahead-of-reader entry discharged) · **`query-findings`
  entry closed as landed** · **plan-compile section machinery**
  (directive = compile target) · **composition conventions** ·
  policy-conditioned citable-bar flagging · consensus roll-up
  (never-contribute constraints restated incl. gaps + reasoning) · block
  summaries + faithfulness judging · judge-envelope widening +
  re-gather repair (with `retrieve`) · **synthesis structure discovery**
  (rev 7.2 — recon-informed proposal, structure-mismatch signals, the
  bounded revision checkpoint: revisit with evidence after the slice
  lands, if one-shot structure proves a real problem) · **regeneration-
  time coherence** (the data-model's original seam — a coherence pass
  when blocks regenerate; deliberately not a write-time pass, the
  rolling ledger owns write-time coherence) · **cross-encoder chunk
  reranking** (rev 7.5 — the `ChunkRerankerBackend` stage ships
  pass-through; the live Bedrock Rerank backend + its `run_harness`
  injection point land with the Bedrock integration slice, per the
  retrieval contract's inference-trust-boundary line and the 010
  Cohere-class note) · synthesis/judge/retrieval quality evals
  (envelope, SECTION_CAP, SECTION_TURN_CAP, top-k, RETRIEVAL_UNIT_CAP,
  retrieval-boost weights and `lookup`-vocabulary calibration).
- Diff summary (data files excluded from review diffs per the 007
  retro).

## Risk tier & review focus

**Tier 3** — schema is a hard gate, three new generation surfaces plus
embedding-query use ride the slice, and it deliberately crosses a
standing line: **the repo's first agent loop** (gated change 4). This is
the trust invariant's landing slice, carrying the full honest-assertion
vocabulary with bounded agency and full substrate-conditional
flexibility. Contract- and plan-stage adversarial reviews standard;
review stack sized per the review-economy notes; the security lane's
headline target is the loop. ADRs 0009 + 0010 (four amendments) cover
the architecture.

Review focus:
- **Provenance/honesty (the headline lane)**: co-emitted citations only
  (chunk claims cite only tool-returned ids); presence checks for both
  cited claim kinds; verified spans become citation rows; single-lane
  verdicts persisted; pattern/theme/gap values deterministically
  validated; the gap fail-closed corpus-promotion rule; reasoning claims
  visibly labelled and strict-routed; unsupported/weak/degraded claims
  flagged never dropped; fabricated chunk quotes excluded and counted;
  mixed/unclear survive; uncovered groups counted; cap-forced emissions
  flagged; intent and tool discretion never touch verification;
  provenance carries the substrate profile, the resolved scope and the
  inherited chain base per resolved reference.
- **Security / the loop (the second headline)**: closed read-only
  three-tool set, code-enforced scope (this project, the referenced
  runs, the resolved document scope), hard turn/result caps +
  `RETRIEVAL_UNIT_CAP`, unknown-tool rejection, no egress verb;
  injection through retrieved frozen text, tag labels or lookup results
  bounded to more reading + mis-claims facing the unchanged claim bar;
  three prompt surfaces consuming untrusted text as id-keyed data
  records; outputs bounded and validated at write; key hygiene;
  socket-deny on suite paths.
- **Correctness**: reference/scope resolution + substrate gating;
  section validation; loop runner semantics (turn accounting, budget
  enforcement, cap-exhaustion forcing, loop-free repair); hybrid ranking
  determinism; citation resolution across verified/abstract/failed
  anchors and chunk quotes; per-type validation; offsets; composite-FK
  integrity; roll-up-last ordering; FK and delete order.
- **Scope**: one loop surface only; no corpus-scale retrieval or index;
  no composition conventions; no consensus/summary machinery; no fourth
  prompt; suite egress-free.
