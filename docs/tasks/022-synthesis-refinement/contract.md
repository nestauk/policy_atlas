# Task contract: 022-synthesis-refinement — Synthesis Refinement

Slice C of the owner-adjudicated pre-eval sequencing (2026-07-12): the last
schema/composition slice before the eval slice. Shipped as **one slice, two phases**
(owner call, 2026-07-14 — the adjudicated shape stands; no split).

> **Status:** approved. Contract approved (before planning): **2026-07-14 · owner**
> (all gate decisions settled in the design conversation; Codex cost investigation
> folded in owner-confirmed; contract-stage adversarial review adjudicated — 15/15
> findings folded) · Plan approved (before implementation): _pending_ ·
> ADR: expected (multi-facet clustering-engine design).

## Goal

Two things, one slice:

**Phase 1 — multi-facet grouping.** One `group` run themes the findings across
*several* facets at once (in-component fan-out — owner shape, 2026-07-12), so one
synthesis reads intervention-, outcome- and implementation-context lenses together
instead of the current one-facet-per-run limit (the 013 live run's motivating hole:
the outcome facet's 13 healthy groups were structurally invisible to a synthesis
referencing the intervention facet's 0). This is also where ICF earns its facet:
grouping BY `context_type` (barrier / mechanism / condition), the 021 seam.

**Phase 2 — cost + surface.** Quality-neutral cost work on the synthesis loop, so the
eval slice scores a launch-plausible config, not the $15.45/run shape (2026-07-11
anatomy: writer turns ~74% — 30 × ~93k input; repair ~21% — full-transcript resends;
prompt cache only 24% on a strictly-growing transcript). Plus the writer/steer surface
items the owner confirmed: read-tool scoping plumbing, the pre-synthesise steer point,
the id-carrying repair schema, and the screen-confidence boost gate.

## Deliverable

One PR to `dev` landing: the multi-facet `group` component (fan-out within one run,
facet at group grain — one `grouping_result` migration) on the **two-stage
clustering engine** (open discovery + batch-validated assignment — the value-list
scale fix; characterise refactored onto it, behaviour-preserving), facet-qualified
group ids through directive / `query_findings` / envelope, the **ICF claim-theme
facets** (barrier/enabler/mechanism), the **cross-kind UNION read view** as the
loader's read surface, the bounded **ICF `context_label` rider** (`icf_v2`); and the
phase-2 cost/surface set under **one** writer prompt-version bump
(`synthesise_section_v6`) with replay evidence and a before/after cost measurement on
the cache-discounted curve. Spec flow-back (components §8/§9, data-model) +
deferred.md discharge/narrowing + an ADR for the multi-facet design.

## Read first

- `docs/knowledge/facet-partition-value-list-scale-limit.md` — **required design
  input**: `group_facet_v1` on gpt-5.4-mini emits duplicate value ids at ~184 distinct
  facet values (4/4 live attempts, honest degradation to all-ungrouped). Kind-spanning
  membership doubles the list. The redesign must bound the per-call value list
  (batched partitioning / hierarchical merge / duplicate-proof id scheme) — a
  first-class constraint, not a retry problem.
- `docs/deferred.md` — § Group (facet seams, large-corpus grouping, agent-authored
  directive), § Synthesise (pre-synthesise steer point · writer read-tool scoping ·
  018's A/B-gated writer-envelope metadata queue · unspanned-lane coverage half ·
  id-carrying repair schema), § Extract/ICF (ICF facet grouping · UNION view · hybrid
  dimension search — both "decide at the Slice C gate"), the multi-facet grouping
  entry under capability-run orchestration (~line 1079 — the five recorded design
  questions), the citation-context char clamp entry (~line 489), retrieval-boost
  grammar v2 (~line 328), `effect_basis` judge-envelope candidate (~line 727),
  screen-confidence multiplier grammar (~line 1110).
- [EB components](../../specs/capabilities/evidence-base/components.md) §8 group, §9
  synthesise — kind-spanning membership is an inherited requirement of the redesign.
- [data-model](../../specs/system/data-model.md) § findings layer — hybrid-queryable
  dimensions (the committed intervention/outcome indexing), UNION-view seam,
  presentation-grain note.
- [prompting doctrine](../../specs/system/prompting.md) — binds all phase-2 prompt
  work: versioned bumps, refine-replay loop (≤3 rounds/surface), cache-prefix layout
  rules, **cost judged on the cache-discounted curve** (the 31%-tokens/64%→23%-cache
  lesson), provider-neutral caching (no OpenAI-specific coupling — Bedrock constraint),
  and the coupled-readers rule (a group-semantics change MUST sweep the planner prompt).
- `docs/tasks/021-icf/contract.md` — pattern precedent; its gate decisions 6–8 are
  pinned context (unified `query_findings`, kind-spanning membership).
- Owner steer, pre-eval plan (2026-07-12): **reopened rulings are agenda items** —
  earlier deferrals (grammar v2, judge-envelope clamp, unspanned coverage) don't bind;
  decide at this gate. Select-at-standard regrade moved OUT to 019 (done); this slice
  keeps the screen-confidence boost gate + the cost-work wall-time band re-measure.
- Code spine: `group.py` + `facet_values.py` + `facet_grouping.py` (partition
  machinery, `FACET_VALUE_CAP`, `GROUPING_FACETS`, `FacetValueRecord` — the unit
  projection the engine generalises), `characterise.py` / `grouping.py`
  (`_discover_themes` + batched assignment — the two-stage shape precedent the
  engine adopts), `schema.py` (`grouping_result` —
  `facet` column, `ck_grr_facet`, `uq_grr_scope_run`, `fk_synr_grouping`),
  `synthesise.py` (grouping payload read, `group_ids`, `groups_unsectioned`),
  `synthesis_tools.py` (`query_findings` group filter, `search_chunks`, tool returns),
  `grounding.py`/`grounding_judge.py` (repair path, judge envelope), `orchestration_plan.py`
  (depth table, directive compile), `planner_prompt.py` (coupled reader).

## Scope / Out of scope

**In — Phase 1 (multi-facet grouping):**

1. **In-component facet fan-out.** The grouping directive names a facet **list**; one
   `group` run clusters the (kind-spanning) finding set once-loaded, **per facet —
   separate calls per facet, never one call spanning facets** (owner-confirmed,
   2026-07-14). One run row; synthesise keeps **one** grouping-run reference
   (`fk_synr_grouping` untouched). This dissolves the recorded multi-run design
   questions (reference shape, share-one-extraction rule, capability-run-entity
   dependency) by construction — record that in the ADR.
2. **Facet moves to group grain** (schema gate, decision 1 — **SETTLED: migrate in
   place**, owner 2026-07-14): each group carries its `facet`; the migration stamps
   every existing row's groups with that row's single facet, then drops the
   row-level `facet` column + `ck_grr_facet`; the run's facet list joins provenance
   + per-facet payload keys. One read path forever — no dual-shape reader
   (greenfield: no users, nothing in production, old rows carry no obligations
   beyond honest migration). One migration on `grouping_result`. `uq_grr_scope_run`
   stays (one row per scope+run). Adversarial-review completions (2026-07-14):
   - **The migration rewrites persisted consumers too** — group ids live outside
     `grouping_result`: `synthesis_result.blocks` persists section `group_ids`,
     and grouping-theme annotation payloads persist `referenced_ids` (today's
     payloads carry no explicit `group_id`; readers fall back to label). The
     migration applies one deterministic old-label → facet-qualified-id mapping
     across all three surfaces, keeping the one-read-path property true
     end-to-end rather than only on the grouping row.
   - **Downgrade policy**: the down migration refuses when multi-facet rows
     exist (a one-facet schema cannot faithfully represent them — refusal is
     honest, lossy down-writes are not); the down test covers a pre-upgrade
     dataset. The exact target JSON shapes (`groups`, per-facet residuals with
     facet identity, `counts`, `flags`, provenance facet list) are pinned in
     the plan and reviewed at the plan 🛑.
3. **Facet-qualified group ids** — labels collide across facets; ids become
   facet-qualified everywhere they travel: directive `group_ids`, `query_findings`
   `group_id` filter, section assignment, `groups_unsectioned`, envelope carriage.
   The id scheme is co-designed with the scale fix (duplicate-proof ids serve both).
4. **The two-stage clustering engine — the scale fix and the machinery convergence,
   one decision** (🛑 design decision 2; owner-settled direction, 2026-07-14).
   `group` adopts the **two-stage open-discovery / validated-assignment shape**
   (characterise's proven split, the owner's recorded candidate in deferred.md
   § Group): stage 1 discovers groups openly (labels + descriptions — never an
   exhaustive id list, which is exactly the one-call capacity cliff that produced
   duplicate ids 4/4 at ~184 values); stage 2 assigns every unit in small batches,
   **validated against the deterministically-known unit list** (no fabricated ids,
   no double assignment, unplaced units land in the counted residual — the
   exhaustive-assignment honesty everything downstream leans on; discovery stays
   open, validation binds assignment, per the owner's clustering model). The engine
   is parameterised by **unit projection**: a value facet's unit = the normalized
   value string + counterparts (today's `FacetValueRecord`); a claim-theme facet's
   unit = the claim's prose. Components stay distinct — characterise and group keep
   their own substrates, gates and consumers; the *engine* is **one shared
   code-owned orchestration/validation core with substrate-specific adapters and
   prompt backends** ("shape-identical" duplicate engines are exactly what this
   settlement retires; ADR records the boundary). Adapter minima differ honestly
   (adversarial review, 2026-07-14): group discovery's minimum is **zero**
   (no-lower-target — zero discovered groups → all eligible units land in the
   counted residual, assignment skipped); characterise keeps its existing ≥1
   theme bound through its adapter. `FACET_VALUE_CAP` survives as the
   fail-closed input guard; the per-call bound becomes an internal batch size.
   **Characterise refactors onto the shared engine in this slice** (owner call,
   2026-07-14) — behaviour-preserving only: characterise's prompt surfaces stay
   byte-identical (no version bumps there), its outputs/records unchanged,
   regression-covered; the refactor is code-level convergence, never a
   characterise redesign. **Per-unit context payloads are built and ON by
   default** (owner call, 2026-07-14), generalising the existing counterpart
   mechanism (a value facet's units already carry up to `COUNTERPART_CAP` paired
   reference surfaces): bounded char-capped source snippets per unit, id-keyed
   data records under the standing data/instructions separation, **source content
   only — never intent** (the facet-relative recomputability pin holds).
   Enrichment is pin-or-revert on build-time replay evidence (the refine-replay
   loop, ≤3 rounds — not deferred to evals); known risks the replay checks:
   context anchoring (clustering by snippet topic instead of value identity) and
   discovery-stage dilution at full-list scale. Full calibration stays eval work.
   **Granularity is a named design input** (owner Langfuse observation,
   2026-07-14): the shipped one-call partition over-fragments — too many
   too-granular groups. The exhaustive-partition framing is a plausible cause
   (every value must land somewhere in one response, so singleton-ish groups
   emerge); open discovery removes that pressure. Steering (owner-shaped,
   2026-07-14 — corpus sizes vary too much for an absolute target): a
   **corpus-relative numeric ceiling, never an absolute target** — a bound
   expressed as a function of unit count (ratio pinned at plan time), computed
   per run in code and injected into the discovery prompt as that run's number;
   **no lower target** (a corpus with three genuine themes gets three groups);
   direction carried by qualitative guidance ("a group is a recurring pattern
   across sources, not a restatement of one value"). Never fixed by catch-all
   buckets (`FORBIDDEN_GROUP_LABELS` stands) or code-side forced merges —
   coarseness is asked for in discovery, honesty stays in assignment. Replay
   evidence must show granularity behaviour across **differently-sized pinned
   inputs** against the observed live over-fragmentation, not just id-integrity;
   ratio calibration is eval work.
5. **Facet vocabulary this slice** (decision 3 — **SETTLED: build**, owner
   2026-07-14): `intervention` / `outcome` / `population` (existing value facets,
   now running on the engine) + **claim-theme facet(s) scoped by `context_type`**
   (e.g. `barrier_theme`): discover themes across the type's claim texts, assign
   every claim — the lens that delivers the promised payoff ("planning delays
   recur as a barrier across heat-pump programmes" backed by a validated group).
   On the item-4 engine this is a second unit projection (claim prose; known
   list = claim ids; scale story = claim count, 203 live), not new machinery.
   Context: ICF stores no short open-vocabulary content values (deliberate 021
   call: no extraction-time canonicalisation) — the content is `claim` prose
   scoped by the closed `context_type` enum, so "what distinct barriers/mechanisms
   were extracted" is claim-theme clustering, not value-string partitioning.
   **The high-value trio only this slice** (owner call, 2026-07-14):
   `barrier_theme` / `enabler_theme` / `mechanism_theme`; the remaining four
   `context_type`s are a config addition later (same engine, same projection —
   recorded in deferred.md, not machinery).
   **ICF `context_label` rider (owner, 2026-07-14 — reopens and supersedes the
   earlier rejection; the 021 setting-rider shape):** one nullable Text column on
   `implementation_context_finding`, **strictly source-named** — filled only when
   the source itself provides a short name for the claim's theme (a subheading, a
   named barrier in the source's own table); null otherwise, **never
   extractor-authored summarisation** (authorship stays with the source — the
   line that distinguishes it from the rejected free-label shape; adherence is a
   named ICF-vetter flag class). `icf_v1 → icf_v2` fingerprint bump (ICF's own
   domain — IOF memos untouched), one prompt-rule block in `extract_icf_v2`,
   `field_coverage` per the nullable-field pattern; v1 rows read "not recorded
   under icf_v1" — no backfill. **Nothing else rides the bump.** Reasoning
   corrections recorded for the ADR: cross-source naming variance was never the
   objection (value clustering absorbs it — same as intervention/outcome);
   clustering-noise dissolves with claim prose riding as unit context; and
   pre-ground-truth is the CHEAP fingerprint moment (the pre-eval sequencing
   criterion itself) — the eval slice authors ICF ground truth next, so the field
   gets ground-truthed alongside the rest, which is exactly why it lands now or
   never cheaply. Readers: grouping unit context now; the finding explorer at the
   web-app slice (the data-model presentation-grain note).
   **Claim-theme eligibility identity (adversarial review, 2026-07-14):** each
   theme facet's eligible universe is exactly the ICF findings whose
   `context_type` matches (e.g. `barrier_theme` = ICF rows with
   `context_type="barrier"`); every eligible claim appears exactly once across
   groups + residual; **all other findings (IOF and non-matching ICF) are
   outside the facet base — never `no_value` residual members**. The eligible
   base's size + content hash persist in that facet's provenance, so CAP,
   failure and coverage denominators are deterministic and test-assertable.
   (A bare deterministic partition BY the seven-value enum is not a facet — that
   read surface already exists as `icf_context_type_count`; named here so nobody
   ships it as one.) Cross-kind clustering on the shared-reference facets is
   **already built** (021 membership bridge) and owner-ratified 2026-07-14: the same
   document's IOF and ICF rows naming one intervention normalize to one value
   record with kind-spanning finding ids; ICF rows with null `outcome` land in the
   outcome facet's counted `no_value` residual, never force-joined. Which facets a
   given run requests stays orchestrator-discretionary; the deep-depth default
   facet set is a plan-time constant (named in the plan, not silently compiled).
6. **Per-facet honesty** (decision 4 — **SETTLED: per-facet**, owner 2026-07-14):
   per-facet residuals, per-facet CAP accounting, per-facet `groups_unsectioned`;
   one facet's clustering failure lands honestly while sibling facets survive —
   never all-or-nothing. **Executable failure model (adversarial review,
   2026-07-14 — "failure row" was under-specified against the one-row-per-run
   design):** each facet gets a per-facet outcome object *within the single
   `grouping_result` row*: `status` (succeeded | failed), groups/residuals,
   counts, rejection reasons, call accounting, flags. **Facet-local failures**
   (caught, persisted on that facet's outcome, siblings continue): cap
   exceeded, backend exception, discovery exhaustion, assignment exhaustion,
   partition-validation failure. **Component-abort failures** (the whole run
   fails structurally): corrupt shared extraction input, or a post-assembly
   cross-facet invariant violation. "Fail-closed cap" thus means the FACET
   fails closed, not the component.
7. **Cross-kind UNION read view** (decision 5 — **SETTLED: build**, owner
   2026-07-14): the recorded seam whose named first reader is this slice's
   cross-schema grouping. Scope sharpened at the adversarial review (2026-07-14):
   the view projects the **shared reference columns** (+ kind discriminator,
   finding id, project/extraction scoping — per the data-model's commitment,
   which is reference-columns-only); the multi-facet loader reads
   **shared-reference (value-facet) projections** through it, retiring the
   direct two-table read for those. **Claim-theme loading reads the ICF table
   directly** — its unit projection needs `context_type` + `claim` prose, which
   are deliberately NOT shared vocabulary; a kind-scoped facet gets a kind-scoped
   read, honestly. The view is a **schema object inside the approved
   `grouping_result` migration's approval envelope** (named in the rubric);
   exact column list + down behaviour pinned in the plan.
8. **Hybrid dimension search over finding reference values** (decision 6 —
   **SETTLED: defer**, owner 2026-07-14): the data-model's committed
   intervention/outcome dimension indexing (ICF's source-named values co-ride free
   by construction) stays behind its own observed-query-behaviour promotion gate —
   no observed behaviour exists yet, evals will generate it, and item 13's scoped
   `search_chunks` + kind-typed `query_findings` cover every reader this slice
   has. Deferred.md entry updated with this adjudication — **and the flow-back
   must touch data-model § findings layer's hybrid-indexing line**, which today
   reads as committed-for-v3.0 (adversarial review: the deferral must be visible
   in the spec, not only in deferred.md).

**In — Phase 2 (cost + surface; ONE writer prompt bump, `synthesise_section_v6`):**

9. **Cache-prefix engineering** — a major quality-neutral lever (24% hit rate on
   the $15.45 run; a later trace showed 51.5% writer hit rate with 12/28 calls
   still at zero — the win is real but variable, so the item claims the shape,
   not a superlative; Codex investigation, 2026-07-14). **Layered prefix design**:
   stable system prompt → stable run substrate/intent → section-varying data
   (member findings, ledger) → task restated last; exact append-only prefix
   within each section. Provider-neutral (suits OpenAI automatic + Bedrock
   `cachePoint`; no `prompt_cache_key`-class coupling). Measured on the
   cache-discounted curve.
10. **Repair as a dependency-complete micro-call** (refined per Codex
    investigation, 2026-07-14: ~29k repair-input tokens per repaired claim
    today) — a repair call receives each failing claim's id + failure reason,
    the replacement span plus adjacent prose context, and **the records its
    claim type actually depends on** (cited chunks for chunk/finding claims;
    the computed/lookup records for pattern, theme and gap claims — "cited
    chunks" alone is too narrow), never the full transcript resend (~21% of run
    cost today). Interface shaped so the deferred re-gather repair plugs in
    later without rework.
11. **Id-carrying repair schema** (013 seam) — replacements carry the failing claim's
    id, validated against the failing set; kills the positional-binding fragility.
    Rides the same prompt bump and completes item 10's micro-call shape.
12. **Tool-return hygiene** (shape owner-settled, 2026-07-14; widened per Codex
    investigation same day — ~68% of writer input in the measured trace was
    re-sent content) — **dedup covers every immutable tool record**, not just
    chunks: full chunk/finding/lookup content returns once per section, repeat
    reads return `{id, already_returned: true}` references; citation
    eligibility stays the union of all returned ids; the character budget
    charges only newly returned content. Plus **oversized-chunk-only windowed
    returns**: under `embedding_unit_policy_v1` a normal chunk (≤ unit budget)
    IS its one unit and returns whole; a collapsed chunk returns the **matched
    unit's span widened by a margin** instead of the full frozen text (unit
    offsets anchor the window; quotes still verify — the window is a substring
    of the frozen chunk; the chunk stays the citation grain). Never a universal
    truncation. Two implementation prerequisites/fixes (Codex, verified):
    retrieval must **retain the winning unit's offsets** through candidate
    construction (currently discarded), and the per-turn character budget must
    **skip-and-continue** past an over-budget result instead of `break`ing and
    silently dropping every later ranked candidate. The **judge envelope stays
    unclamped** (agenda B, settled).
13. **Writer read-tool scoping plumbing** — `search_chunks` gains optional
    fail-closed scope filters, **validated per argument** (adversarial review,
    2026-07-14 — the earlier "like the directive boosts" precedent was wrong:
    directive tag boosts accept bounded arbitrary keys and record unmatched
    values rather than failing): doc ids must parse and belong to the scoped
    corpus; group ids must resolve in the referenced grouping; evidence types
    validate against the closed enum; tags must exist in the scoped project's
    tag set — each rejecting loudly on miss. Plumbing + minimal tool-description
    text this slice; WHEN-to-scope prompt guidance is post-eval tuning
    (lead-only, replay-evidenced when it comes).
14. **Pre-synthesise steer point** — the owner-confirmed seam: after group /
    characterise, surface proposed sections + discovered themes/facet groups; the
    response compiles into the **existing** fail-closed `context["synthesis"]`
    directive (sections + group_ids + retrieval_boosts — its first author).
    **Surface pinned (adversarial review, 2026-07-14 — the current proposal path
    is NOT side-effect-free: `synthesise_scope` mints the artefact before
    proposing sections):** a bounded, **side-effect-free**
    `propose_synthesis_plan` + compile surface — an external caller obtains the
    proposal (no artefact minted, no rows written), collects the user's
    response out-of-band, and submits the compiled directive on a later
    invocation; **no runtime pausing exists**. Input/output schemas pinned in
    the plan; deterministic compile + no-write tests. Mode-governed pause UX
    stays deferred (plan-as-object seam).
15. **Screen-confidence retrieval boost** (decision 7 — **SETTLED: build**, owner
    2026-07-14): the pre-decided grammar (linear clamped functional multiplier,
    product clamped [0.1, 10], steerable-never-baked) wired as a directive boost
    over screen confidence. Constants plan-pinned; calibration is eval-slice work.
    Rider (Codex investigation, 2026-07-14 — verified): `_soft_prior` today
    multiplies selection × column × tag × appraisal factors with **no final
    product clamp** — add the grammar's required combined-product clamp
    [0.1, 10] and record raw factors + executed multiplier in provenance; plus
    the **no-double-count guard**: suppress confidence execution when a
    selection reference already prices confidence, suppression recorded.
16. **Riders:** `lookup` widening to screening rows · the cost-work wall-time band
    re-measure (D1's ~10–20 min band re-measured on the post-phase-2 config, so the
    rehearsal numbers stay honest) · **key-findings seed filter** (Codex,
    2026-07-14: the key-findings call receives the union of every section's
    gathered chunks, ~2% of input — filter `chunk_content_by_id` to chunks cited
    by surviving claims; citation eligibility already restricts to those) ·
    **batched query embeddings** (Codex, 2026-07-14: 57 sequential single-text
    embed calls ≈ 12 s wall-time — embed a read-batch's uncached queries in one
    call; retrieval stays deterministic per query vector).
18. **Prompt-facing DTO slimming** (Codex investigation, 2026-07-14 — NEW):
    characterisation and grouping summaries serialize full membership UUID
    lists into every section seed, and the rolling ledger repeats cited_ids,
    flags and a fixed note per record despite ledger records being non-citable
    by prompt rule. Split internal vs prompt-facing DTOs: prompt-side
    themes/groups carry id · label · description · size · spread · residuals —
    never membership lists; the ordinary ledger slims to claim id/type/text
    (the evidence-bearing key-findings ledger stays separate). Small now
    (~1–5%) but grows directly with phase 1's multi-facet fan-out — the two
    phases compound here. Quality-neutral; replay-checked with the v6 rounds.
17. **Unspanned-lane precision fixes** (owner-adopted 2026-07-14, from the live
    trace scan — 404 `synthesise:judge` observations, 429 unspanned excerpts:
    ~16% re-judge artifacts, ~24% judge over-reports inside mapped spans, ~59%
    genuine writer-authored unclaimed evidential prose, ~1% span-edge):
    - **(i) Span-map completeness — ALL valid claims** (widened per Codex
      corroboration, 2026-07-14): the judge's span map is built only from
      `JUDGED_TYPES` claims today, so valid pattern/theme/gap spans are
      invisible to the unspanned lane even on initial calls — and the
      post-repair re-judge passes only the rejudged subset. Fix: separate
      `claims_to_judge` (verdict coverage unchanged) from `occupied_claim_spans`
      (every final valid claim's span, all types, kept + rejudged). This is the
      slice's ONE judge-envelope change; A/B-bound — re-judge-set replay with
      verdict-flip inspection.
    - **(ii) Unspanned observability counters** (recast per Codex challenge,
      2026-07-14 — verified: `_bind_unspanned` already refuses to bind
      excerpts inside claim spans, so persisted records are already filtered):
      instead of a second drop-filter, split the single `unspanned_unbound`
      counter into three, with **fixed names and classification precedence**
      (adversarial review, 2026-07-14 — an excerpt can qualify for more than
      one): (1st) `unspanned_overlap_filtered` — overlaps any final claim
      span; (2nd) `unspanned_duplicate_stale` — exact duplicate of an
      already-bound excerpt or a stale pre-splice result; (3rd)
      `unspanned_unlocated` — not locatable in the final prose. Judge
      over-report becomes measurable separately from real binding failures.
    - **(iii) Supersede, never concatenate** (Codex, 2026-07-14: 52/429
      excerpts are exact initial/re-judge duplicates): when repair changes the
      prose, the re-judge's unspanned results REPLACE the initial scan's
      (`unspanned = rejudge_unspanned`), not extend them; a rebuilt prose with
      no re-judge keeps no stale flags and relies on `unspanned_lane_skipped`.
    - The genuine ~59% (evidential summary sentences, "As an inference…"
      labelled-inference prose, cluster descriptions) is a named input to the
      `synthesise_section_v6` replay work — claim-or-flag is a v6 taste call
      made on replay evidence, not pre-decided here.
    - **Eval note:** `unspanned_assertions` counts before/after these fixes are
      NOT comparable — the eval slice must re-baseline that metric.

**Agenda — owner-reopened rulings, decided at this gate (🛑 decisions A–E; "don't
inherit the deferral" is the owner's own instruction):**

- **A. Grammar-v2 boundary — SETTLED: subsumed and retired (owner, 2026-07-14).**
  The multiplier half is discharged by decision 7 (built); the tag-scoping half is
  delivered better by item 13's call-level writer scoping. One narrow seam stays in
  deferred.md: directive-level tag-boost vocabulary on the `context["synthesis"]`
  grammar, trigger = observed steer-point demand for it (no author exists today —
  the recorded steer examples compile against the existing grammar). The
  grammar-v2 deferred entry is discharged with this adjudication.
- **B. Judge-envelope char clamp — SETTLED: judge envelope stays unclamped**
  (owner, 2026-07-14). The tool-return clamp is reshaped as item 12's
  oversized-only windowed return (matched unit's span + margin — the owner's own
  formulation); no judge-input change, no re-baseline triggered.
- **C. Unspanned-lane coverage half — SETTLED: stays parked for the eval slice**
  (owner, 2026-07-14) — the live trace scan showed the lane's problem is
  precision, not coverage; the precision fixes are adopted instead as
  item 17. `unspanned_lane_skipped` honesty flag unchanged.
- **D. 018's dangling writer-envelope metadata A/B queue** — **SETTLED: explicit
  re-defer to the eval gate** (owner, 2026-07-14). Phase 2 already rebuilds the
  writer surface (`synthesise_section_v6`); stacking an envelope-content A/B on
  the cache/repair changes would muddy attribution of both, and this slice's cost
  measurement wants a clean before/after. Deferred.md entry re-recorded with this
  adjudication — the "dangling" state is discharged by the explicit decision.
- **E. `effect_basis` as judge-envelope candidate** — **SETTLED: re-defer to the
  eval gate, alongside D** (owner, 2026-07-14). Judge verdicts are a function
  of the envelope — every envelope change forces a re-baseline. Refinement
  (Codex, 2026-07-14, owner-confirmed): the eval-gate A/Bs run **sequentially
  per envelope change**, not as one merged baseline event — merged baselines
  confound which change moved the verdicts; in particular effect_basis's A/B
  must not share a baseline with item 17(i)'s span-map change.

**Out:**

- Bedrock migration (post-eval by design; standing constraint binds: nothing new
  couples to OpenAI-specific API surface — including the caching work).
- Retrieval-boost grammar v2 beyond decision A's boundary call.
- Steering-mode / plan-as-object machinery (the steer point lands as directive
  compile, not pause UX) · facet-theme promotion (canonical groupings — the
  entity-resolution bar stands) · multi-execution fan-in (dissolved for grouping by
  the in-component shape; the general seam stays deferred).
- Re-gather repair (item 10 shapes the interface only) · corpus-scale retrieval /
  index-backed `retrieve` · cross-encoder reranker (pass-through stands).
- Prompt tuning beyond the one versioned bump; all plan-pinned constant calibrations
  (eval work); the evals themselves.
- **Gather/writer model split** (routing tool-selection turns to a cheaper model —
  Codex investigation 2026-07-14: gather turns ≈ 43% of input tokens for ~4.7k
  output in the measured trace, est. 20–30% saving): stays **deliberately
  post-eval** per the owner's 2026-07-12 quality-sensitive-cost-routing pin,
  re-confirmed by the owner 2026-07-14 — it is semi-neutral (a weaker gatherer
  can fetch worse evidence) and evals are its regression net. The trace evidence
  goes to deferred.md so it heads the post-eval queue.
- The 19 ICF cleanup/altitude candidates (deferred to the third-schema slice).
- Two-profile extraction parallelism (extract wall-clock — eval-slice cost-axis
  input, not this slice's surface).
- Demo surface (C4, codex lane) · anything web-app.

## Constraints & approval gates

- **Schema** 🛑: two approved migrations — the `grouping_result` migration
  (decision 1) and the ICF `context_label` rider column (owner-approved
  2026-07-14, `icf_v2`). Any further table change is a stop condition.
- **Prompt-bearing surfaces are lead-only** (AGENTS.md): `synthesise_section_v6`,
  the group prompt surfaces (discovery + assignment — supersede `group_facet_v1`),
  the claim-theme facet prompts, the planner-prompt sweep (coupled-readers rule —
  multi-facet changes group semantics the planner describes), steer-point compile
  text. Every change bumps its version string; replay-evidenced.
  **Characterise's prompt surfaces are byte-identical this slice** — the engine
  refactor is code-level; a characterise prompt change is a stop condition.
- **Egress unchanged**: existing approved OpenAI routes only; no new backends.
- **No OpenAI-specific coupling** in the cache work (Bedrock constraint).
- Upgrades-never-invalidate: the group prompt bump changes future grouping runs
  only; existing `grouping_result` rows are migrated in place to the new shape
  (decision 1, settled) — honest one-time migration, one read path after it.

## Public / private boundary

Committable: contract/rubric/plan/ADR, code, migrations, prompt text, spec flow-back,
replay *summaries* and cost figures. Private: raw model transcripts, live-run
document text, traces, credentials. Cost anatomy numbers ($, token counts, cache
rates) are public-safe.

## Model route

OpenAI under approved controls (Bedrock post-eval). Prompt-bearing changes (all
lead-authored): `synthesise_section_v6` (cache layout · repair schema · scoping tool
description), the group discovery + assignment prompts (superseding
`group_facet_v1`), the claim-theme facet prompts, `extract_icf_v2` (the
`context_label` rule block — nothing else changes in that prompt), the ICF-vetter
label flag class, planner prompt sweep for group-semantics vocabulary. The judge
prompt and its verdict input set are byte-identical; the ONE approved
judge-envelope change is item 17(i)'s span-map widening (`occupied_claim_spans`
gains all final valid claim spans), with its mandatory re-judge-set replay —
independent of B/E, which stay deferred. Any other judge prompt/envelope change
is out of scope.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves** — no facet machinery beyond what this slice's readers use.
- **Flag, don't drop** — per-facet failures are honest rows, never silent absences;
  rejection reasons persist (the 013/021 diagnosability property).
- **Honest absence** — per-kind, per-facet availability stays visible.
- Deferred seams stay seams in [docs/deferred.md](../../deferred.md).
- Quality-neutral means **measured** neutral: phase-2 changes are judged on replay
  evidence, not asserted.

## Stop conditions

Halt and escalate when: a schema change beyond the two approved migrations (+ the
UNION view) appears · any judge-envelope change beyond item 17(i)'s span-map
widening is tempted · the cache work tempts provider-specific API surface · scope
grows past this contract (e.g. re-gather repair, pause UX, canonicalisation) · a
spec is wrong enough to block · budget spent.

## Acceptance checks

- `make verify` green (test · typecheck · lint · build · okf-validate).
- Deterministic: migration up/down; facet-qualified id collision tests; per-facet
  residual/failure-row invariants; repair-id binding validation; scope-filter
  fail-closed tests; dedup/clamp unit tests.
- **Live checks (contract-time pin — scoped, not full e2e):**
  1. Live grouped run at the previously-failing scale (both-profiles corpus,
     ≥184 distinct values) — healthy partitions, no duplicate-id rejection; the
     knowledge doc's failure mode demonstrably closed.
  2. Live multi-facet run (≥2 facets incl. **at least one claim-theme facet**,
     e.g. `barrier_theme` — `context_type` is the eligibility predicate, never
     itself a facet) — per-facet groups + residuals land; synthesise consumes
     both lenses via one grouping ref. The claim-theme arm runs at a realistic
     claim count (≥ the ~200-claim live scale) **with context payloads enabled**:
     discovery succeeds, assignment covers the eligible base exactly, group
     count stays under the computed ceiling (the value-facet scale check does
     not prove claim-theme scale — adversarial review, 2026-07-14).
  3. One cheap full-chain smoke (mandatory-spine composition).
  4. **Cost re-measure, two arms** (adversarial review, 2026-07-14 — a single
     historical comparison conflates Phase 2 savings with Phase 1 substrate
     growth): **(a)** `synthesise_section_v5` vs `v6` on the same legacy
     one-facet substrate — isolates Phase 2's cost/quality neutrality;
     **(b)** the final v6 multi-facet configuration vs the $15.45 / 24%-cache
     historical baseline — the launch-plausible total. Each arm reports $,
     cache hit rate and wall-time band (rider 16) on the cache-discounted
     curve, recording facet set, section set, corpus, model, cache state,
     repair incidence and run order.
- Replay evidence per bumped prompt surface (refine-replay loop, ≤3 rounds,
  pin-or-revert); the mandatory 17(i) re-judge-set replay with verdict-flip
  inspection (B/E stay deferred — no other envelope change exists to A/B).

## Verification evidence expected

`verification.md` with: exact commands + run/trace ids for the four live checks, the
cost before/after table, replay-round records per surface, migration evidence
(up/down + old-row readability), diff summary, public-safety confirmation, gaps →
deferred.md.

## Risk tier & review focus

**Tier 3** — schema migration + prompt-bearing surfaces + untrusted-document text
flowing through tool returns and repair inputs. Review stack per tier (contract
verifier · code review · security lane · adversarial · simplification), within the
review-stack economy pins (medium effort, one security lane, per-angle diff scoping —
and data files excluded from review diffs). Focus: partition-exactness invariants
under the new scale machinery · facet-id collision/fail-closed discipline ·
cost-change measurement honesty (cache-discounted, not raw tokens) · repair binding
correctness · scope creep toward the Out list.

## Decisions for the owner at this gate

1. **Facet-at-group-grain migration — SETTLED (owner, 2026-07-14): migrate in
   place, drop the column** — greenfield call: no users, nothing in production;
   one read path, no dual-shape reader.
2. **The two-stage clustering engine — SETTLED in full (owner, 2026-07-14)**: open
   discovery + batch-validated exhaustive assignment, parameterised by unit
   projection; **characterise refactors onto the engine this slice**
   (behaviour-preserving, prompts byte-identical); **context payloads built and on
   by default** (bounded, source-content-only, build-time replay pin-or-revert).
   Residual for the gate: what `FACET_VALUE_CAP` becomes.
3. **First ICF content facet — SETTLED in full (owner, 2026-07-14)** — claim-theme
   facets on the item-4 engine, **high-value trio only**: `barrier_theme` /
   `enabler_theme` / `mechanism_theme` (remaining four context_types = later
   config, deferred.md). **Plus the `context_label` rider** (owner, same day,
   reopening the earlier rejection): nullable, strictly source-named, `icf_v2`
   bump, nothing else rides — the 021 setting-rider precedent. Residual for the
   plan: the deep-depth default facet set.
4. **Per-facet failure isolation — SETTLED (owner, 2026-07-14): per-facet** —
   honest per-facet failure rows, rejection reasons persisted, siblings survive.
5. **Cross-kind UNION view — SETTLED: build (owner, 2026-07-14)** — the multi-facet
   loader reads through it; the shared-reference read surface over both finding
   tables.
6. **Hybrid dimension search — SETTLED (owner, 2026-07-14): defer** — stays behind
   the observed-query-behaviour promotion gate; item 13's scoped `search_chunks`
   covers this slice's readers.
7. **Screen-confidence boost — SETTLED (owner, 2026-07-14): build** — pre-decided
   grammar in; constants plan-pinned, calibration eval-owned.
8. **Agenda D + E — SETTLED (owner, 2026-07-14): both re-defer to the eval gate**,
   evaluated there as **separate, sequential envelope A/Bs** (never one merged
   baseline; neither shares item 17(i)'s replay baseline) — the E entry's
   detailed ruling governs.
9. **Agenda A–C — SETTLED (owner, 2026-07-14)**: A = grammar v2 subsumed and
   retired · B = judge envelope unclamped, tool-return clamp reshaped as
   oversized-only windowed returns (item 12) · C = coverage half parked,
   precision fixes adopted (item 17, trace-scan-evidenced).

**All contract-gate decisions are now settled.** Remaining plan-time residuals:
`FACET_VALUE_CAP` value · deep-depth default facet set · granularity ceiling
ratio · context-payload bounds · engine refactor sequencing.
