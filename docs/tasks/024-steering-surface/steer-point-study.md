# Steer-point expansion study — 024-steering-surface

Design-phase artefact (step 1 input). Inventories all EB components for
decision-shaping moments worth surfacing as steering points, ranked for the
owner's ship-list decision at the contract gate. Method: three parallel
read-only component inventories (sourcing+assess · corpus+extract ·
group+synthesis, 2026-07-15) over the as-built directive parsers, persisted
flags/provenance, thresholds and silent discretionary behaviour, adjudicated
by the lead against the spec's substance test (execution-orchestration § the
routing rule: emphasis/prioritisation/interpretation-shaping decisions
escalate; capability.md § Check-in points).

## The anatomy a candidate must fill (the deepening-selection pattern)

1. **Boundary** — a component boundary the runner already walks (pauses are
   between-component only; in-component pauses are out of scope, v3.0 serial
   model).
2. **Triggers** — computable from *persisted* state (flags/provenance
   columns), never recomputed. Return-payload-only signals are a named gap.
3. **Options** — a closed intent-vocabulary set whose deltas compile into an
   *existing* directive grammar, fail-closed. A steer an existing grammar
   cannot express is an honest refusal + recorded seam, never an
   approximation.
4. **Substance weight** — the decision must shape emphasis/conclusions
   (the §6 substance test), or it's a check-in, not a steer point.

## Ranked candidates

### S0 — Deepening-selection trigger enrichment *(enrich the existing point)*

Select already persists five decision-grade signals its steer point never
reads: `flags.thin_full_text` (`select.py:1006`, share < 0.5 floor),
`provenance.unmatched_boosts` + `unmatched_priority_patterns` (a user steer
that matched nothing gets no feedback), `signal_availability` (ranking
running on defaults), rerank degradation (`fallback_count`,
`title_only_count`), and `excluded_by_stratum` reason `budget_exhausted` vs
`ranked_below_cut` (directly licenses a budget-raise option). All are already
in `selection_result` — wiring them into `steer_point_triggers` is
trigger-only work on shipped machinery. **Cost: trivial. Substance: medium
(sharpens an already-live substance point).**

### S1 — Pre-synthesise steer point *(the owner-confirmed seam, machinery built)*

- **Boundary:** after group/characterise, before synthesise — the
  `before_synthesise` pause Moderate mode already fires (a bare pause today,
  no options). The capability spec names the landscape→synthesis crossing as
  a mode-governed steer point; the wireframe's build check-in is this shape.
- **Triggers (persisted):** grouping per-facet `flags`
  (`value_cap_exceeded`, `failure_class`, `groups_rejected`), high
  `ungrouped`/`no_value` counts, skewed `direction_spread`; plus the
  side-effect-free proposal itself.
- **Options (all compile today):** "only these themes" → `sections` +
  `group_ids`; "prefer strongest evidence" → `retrieval_boosts.appraisal_tier`
  / `screen_confidence`; "emphasise evidence type X" →
  `retrieval_boosts.columns.primary_evidence_type`; "as proposed".
- **Machinery:** BUILT (022 item 14) — `propose_synthesis_plan` (side-effect
  free) + fail-closed `compile_synthesis_directive`; the deferred remainder
  is exactly the mode-governed pause UX this slice ships. deferred.md:986
  ("pairs with `deepening_selection` the same way select pairs with
  extract").
- **Gaps (stay seams):** tag-boost vocabulary not advertised in `boostable`
  (deferred.md:338); no section-depth/turn-budget/judge-strictness knobs.
- **Cost: low (options surface + runner wiring on built compile machinery).
  Substance: HIGH — the section set and evidence emphasis shape the artefact
  directly.** Recommended ship.

### S2 — Thin-search steer point *(the wireframe's canonical pause)*

- **Boundary:** after acquire (and/or after screen stage 1, where thinness
  is honestly measurable in screened counts).
- **Triggers (persisted):** `search_coverage_record.stop_condition`
  (`re_searched_still_thin`, `budget_exhausted`, `wall_clock_exceeded`),
  `adequacy_verdict="inadequate"`; screen's relevant-count vs
  `THIN_CONFIDENT_RELEVANT`.
- **Options:** "deepen the search" → `{"search":{"depth":"deep"}}`
  (compiles); "narrow/widen scope" → `filters` deltas (compile); "accept the
  thin base and continue" (flagged); "abort". A search re-run needs
  reselect-style re-run mechanics for acquire (new machinery: re-walk from
  acquire under an amended plan version).
- **Gaps:** arm enable/disable, target/threshold overrides, query-term
  injection — all constants (`search_loop.py:76-131`); stay seams.
- **Cost: medium (re-run-from-acquire mechanics are new; triggers and deltas
  exist). Substance: HIGH — 017 deliberately made rapid-mode thinness
  flag-not-escalate; this is the honest human half of that decision.**
  Strong second candidate.

### S3 — Post-screen bar adjustment

- **Boundary:** after screen stage 1 (or stage 2).
- **Triggers:** `tie_broken` / `non_unanimous` / `unsure_reps` /
  `stage2_unsure_referred_back` — today on `source.screened` **events** and
  return payloads, not queryable columns (gap: trigger read needs an event
  scan or a counts column).
- **Options:** "tighten/loosen criteria" → `{"screening":{"criteria":[...]}}`
  (the one free-text-native grammar already live — criteria are user
  sentences); "confirm on full text" → `{"screening":{"stage":2}}` (compiles);
  re-screen = re-run mechanics. Consensus knobs (reps/quorum/confidence
  floor) are constants — seams.
- **Cost: medium. Substance: medium-high (inclusion bar shapes the base).**

### S4 — Extract-profile steer (before extract)

- **Options compile:** `{"extraction":{"profiles":[IOF, ICF]}}` — add the
  implementation-context profile when the question warrants. **Trigger gap:**
  no corpus signal flags "implementation-heavy"; it's intent-shaped and
  plan-time. Better served by the planner + the pre-extract check-in render
  than a triggered steer point. **Cost: trivial (delta exists). Substance:
  medium.** Candidate for the option list of an existing boundary rather
  than a new steer point.

### S5 — Post-group re-group steer

- **Options that compile:** facet add/drop →
  `{"grouping":{"facets":[...]}}` + re-run (deferred.md already records
  re-group-as-new-run as shipped semantics). Granularity (finer/coarser) has
  **no grammar** (`group_max_labels` is derived, `min_labels=0` fixed) — the
  clearest group grammar gap; a `granularity` directive key is a seam.
- **Triggers (persisted):** per-facet `flags`/`counts` (`value_cap_exceeded`,
  ungrouped share, `failure_class`).
- Partially covered by S1 (theme pruning at section grain). **Cost: medium.
  Substance: medium.**

## Recorded seams (below the line — no ship this cycle)

- **Appraise steerable rubric** — zero directive grammar; the type→tier map
  is the emphasis lever and the spec *intends* it steerable
  (components.md § appraise; `rubric_version` already travels). Grammar-build
  slice.
- **Classify** — zero grammar; re-classify-Unknowns-on-full-text is an ADR
  0011-rejected-then-deferred seam. `by_type` histogram is ready trigger
  material.
- **Characterise** — zero grammar; the spec-declared policy-filtered
  dual-view coverage (components.md:184) is unbuilt, and it is the *third
  capability-spec trigger* for deepening selection ("policy supportable only
  by below-policy sources") — that trigger stays unbuildable until dual-view
  lands. `unclustered.share` fires no flag (gap).
- **Vetter steering** — no grammar; sound-bias is prompt-baked; fail-open is
  fixed. `vetted_out.by_class` spikes are ready triggers for a future point.
- **Mid-loop steering** (between deep-search rounds, between synthesis
  sections) — in-component pauses; violates the component-boundary pause
  model; blocked on the deferred durable-resume engine.
- **Consensus/threshold knobs everywhere** — reps, quorums, confidence
  floors, targets, caps are module constants across all components; a
  "thresholds" directive family is a deliberate future grammar decision, not
  this slice.

## Cross-cutting findings

1. **Grammar coverage is uneven:** select (5 keys) and synthesis
   (sections + 4 boost families) are rich; search (depth+filters) and screen
   (stage+criteria) are real; extract is one-dimensional (profiles); group is
   facet-only; classify, appraise, characterise, vetters have **none**.
2. **Trigger material is persisted for select/coverage/group/synthesis but
   return-payload-only for screen/classify/appraise** — any steer point
   there needs its counts made queryable first (or read from `source.*`
   events).
3. **Free text is already native in one grammar:** screening `criteria` are
   user sentences carried as data — the precedent that free-text steering
   compiles into bounded grammars without becoming prompt injection.

## Lead recommendation (for the owner's ship-list call)

Ship **S0 + S1** with the machinery (both ride existing compile targets;
S1 is the spec-blessed, owner-confirmed pair to deepening-selection and
gives the interpreter a second live point to prove generality). Hold **S2**
as the named next steer-point slice (its re-run-from-acquire mechanics are
real new machinery). Record S3–S5 + the seams above in deferred.md with
their grammar gaps named.
