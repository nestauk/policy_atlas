# Steerability refinement — the fold-in plan (pre-rev-4 working note)

Owner direction (2026-07-16): one large slice; get steering to a
state-of-the-art human-in-the-loop system; refine the full addition set
before folding into the contract. This note is the refinement surface —
each item carries the lead's recommendation and the disciplines it must
obey. Items marked **ADJUDICATE** need an owner call; the rest fold in as
recommended unless challenged. On adjudication this becomes contract rev 4.

## The target shape

**One steer-point lattice — a steer point at every major phase boundary —
three compile-target families, one router.**

```
acquire ──P1──> screen ──P2──> (classify·appraise·characterise) ──> select ──P3──> extract ──> group ──P4──> synthesise
```

- **P1 post-acquire — "the search"** (was S2): triggers from
  `search_coverage_record` (`inadequate`, `re_searched_still_thin`,
  budget/wall-clock stops). Options: deepen (depth rung) · rescope
  (filters) · **guide the queries** (B1) · accept-thin (flagged) · abort.
- **P2 post-screen — "the inclusion bar"** (was S3): triggers computed from
  `source_screening_result` rows + `source.screened` event flags
  (`tie_broken`, `non_unanimous`, `unsure` share, stage-2 demote rate).
  Options: tighten/loosen criteria (existing free-text grammar) ·
  strictness posture (C1) · run stage-2 confirm (existing `stage:2`) ·
  re-screen re-run · continue.
- **P3 post-select — "deepening selection"** (existing point, enriched):
  S0 trigger enrichment; options gain **extraction profiles** (add ICF —
  the old S4, whose natural home is this pre-extract boundary) and
  **re-extract refresh** (D3) alongside the five existing options.
- **P4 post-group / pre-synthesise — "the synthesis shape"** (S1 + S5
  merged): proposal via `propose_synthesis_plan`; triggers from grouping
  per-facet flags. Options: only-these-themes / section edits (existing
  grammar) · evidence emphasis boosts (existing) · tag boosts (D4) ·
  re-group coarser/finer (C3) · re-group with guidance (B3) ·
  as-proposed.

Every point: numbered options **or free text through the router**;
Unattended auto-resolves per `steer_point_defaults` (planner emits a
default per point — planner prompt rev); every presentation/decision is a
steering event (the 024 chassis).

**Pause-set compile (ADJUDICATE — mode semantics).** With four steer
points, "Moderate pauses at every point" ≈ 4 pauses/run (~heavy). Proposed
table: **Frequent** = every component boundary (unchanged) · **Moderate** =
P3 + P4 always, P1/P2 only when a trigger fires · **Minimal** = any point
whose trigger fires (substance escalation, unchanged spirit) ·
**Unattended** = none (defaults). Alternative: Moderate pauses at all four
always. Owner call — this sets the product's default rhythm.

## Family B — guidance channels (prose-as-data into LLM prompts)

The pattern (screen-criteria precedent): bounded list of user-intent
sentences, injected as clearly-framed *data, not instructions* at one
component's prompt boundary; length-capped (`DIRECTIVE_STRING_MAX`),
scrubbed, fail-closed parsed; persisted in that component's provenance;
**never** written to shared `evidence_scope.intent`.

- **B1 `search.guidance`** — into query generation + the reformulate arm
  ("prioritise UK policy evaluations; avoid clinical literature").
  Provenance: `search_coverage_record.scope_filters` sibling key. **IN.**
- **B2 `extraction.guidance`** — into IOF/ICF extraction prompts
  ("attend to cost-effectiveness outcomes"). **Enters the memo
  fingerprint** (fingerprint-covers-knobs rule) — guided and unguided
  extractions never reuse each other. Provenance: extraction_result. **IN.**
- **B3 `grouping.guidance`** — into discovery ("organise by policy
  instrument, not sector"). Provenance: grouping_provenance. **IN.**
- **B4 `synthesis.guidance`** (global) — into section drafting as
  artefact-level emphasis. Overlaps: per-section `focus` already exists;
  018's deferred audience-framing pair. **ADJUDICATE**: fold in as a
  simple global channel, or hold for the audience-framing slice — risk is
  two overlapping voice levers.
- Existing channels the router uses from day one: `screening.criteria`,
  `synthesis.sections[].focus`.
- **Not channels (pinned OUT):** vetter prompts, grounding-judge prompts
  (integrity surfaces — users must not instruct their own verifier),
  classify (factual typing; the intent lands downstream in the rubric).

## Family C — postures (named bundles over constants)

Closed vocabularies compiling to pinned parameter sets, recorded in
provenance (the `search_effort` precedent). No raw knob exposure.

- **C1 `screening.strictness`**: `inclusive | standard | strict` →
  (reps, quorum, tie policy, title-only rescue, stage-2 unsure handling).
  `standard` = today's constants exactly. **IN.**
- **C3 `grouping.granularity`**: `coarser | standard | finer` → the
  `group_max_labels` ceiling (multiplier on the derived clamp; `standard`
  = as-built). **IN.**
- **C4 `characterise` theme bounds** — characterise gains its first
  directive parser: `{"characterise": {"themes": "fewer" | "standard" |
  "more"}}` → bounds override. **IN** (small; the parser is the cost).
- **C2 vetter posture** — **ADJUDICATE, lead recommends OUT**: vetting is
  quality-integrity adjacent; proposed compromise is a binary
  `extraction.vetting: on | off` (visible, flagged in the artefact's
  honesty labels) + a `retry_vetting_failed` action, not a sensitivity
  dial. Sensitivity stays prompt-owned.

## Family D — structured keys

- **D1 `appraisal.rubric`** — appraise gains its first directive parser:
  partial type→tier override map over `DEFAULT_RUBRIC` (closed type
  vocabulary, tiers 1–5, fail-closed). `rubric_version` derives from the
  override (e.g. `v2-hierarchy-v1+<hash8>`), travelling in every row as
  today. Downstream coherence is automatic (select's quality signal and
  synthesis tier boosts read the persisted scores). Steer-point option
  vocabulary: "treat <type> as strong evidence for this question". **IN —
  the highest-leverage single addition** (spec-declared intent).
- **D3 `extraction.refresh`** — `abstract_only | failed | all`: bounded
  memo-invalidation ("re-extract the abstract-only docs now full text
  landed"). Compiles to fingerprint-bypass for the named class; provenance
  records the refresh. **IN.**
- **D4 tag-boost vocabulary advertising** — `propose_synthesis_plan.boostable`
  gains `tags` (from `source_tag`), discharging the deferred seam; the
  boost grammar already accepts them. **IN** (cheap).
- **C5/D5 `search.target`** — bounded override of
  `TARGET_CONFIDENT_RELEVANT` ("keep going until ~40 relevant"), clamped
  (e.g. 5–60), deep/standard loop only. **IN.**
- **Select** — already the richest grammar; no additions.

## The router (interpreter, upgraded from single-delta to fan-out)

- One utterance → a **fan-out plan**: deltas across multiple not-yet-run
  components, mixing families ("I care most about rural areas" → screen
  criterion + extract guidance + synthesis boost/section note). The
  `Adjust.directive_deltas` multi-component shape already supports it.
- **Partial compile with honest remainder**: fragments that compile are
  proposed; inexpressible fragments are refused *by name* in the same
  confirmation ("'only randomised trials from Nordic countries' — the
  country filter compiles; trial-design filtering at screen compiles as a
  criterion; a search-arm design filter does not exist → recorded"). The
  confirmation renders the full fan-out; **nothing applies unconfirmed**.
- Refusal events per unexpressed fragment (the demand meter survives even
  in a wide grammar).

## Still OUT, even in the big slice (each with its reason)

1. **Dual-view coverage / the source-evidence policy object** — a
   data-model design of its own (017 decision 9 deferral), not steering
   machinery. The "policy unmeetable above-bar" trigger stays parked with
   it.
2. **Judge steering** and **vetter sensitivity** — integrity boundary
   (C2's binary + retry is the compromise if adjudicated in).
3. **Mid-component steering** (between deep-search rounds / between
   sections) — requires the durable-resume engine; boundary model holds.
4. **Free-text replanning** (recomposing the chain / adding components
   mid-run beyond the existing nudge mechanics) — planner re-entry is its
   own surface; the nudge + mode change remain the composition levers.
5. **Transcript persistence / turn tables** — workspace cluster;
   `session_id` anchors are in (1b).

## Cross-cutting cost & discipline ledger

- Every new grammar key: fail-closed parser + provenance + tests; B2/D3
  additionally fingerprint participation; C1 changes screen's consensus
  path behind a posture default that reproduces today's behaviour exactly
  (guard tests pin `standard` ≡ as-built).
- Prompt surfaces touched (all lead-authored): interpreter
  (`steer_interpret_v1`, now a router), planner (`planner_v6`: steer-point
  defaults vocabulary ×4, posture awareness), guidance-composition points
  in search-gen / extract ×2 / group discovery / synthesis section
  prompts (data-not-instructions framing blocks).
- Schema: **unchanged beyond decision 1b** — all new steering state rides
  `evidence_scope.context` + result-table JSONB provenance.
- Eval: every steer-bearing lever is versioned in provenance, so the eval
  slice can condition on steering state; posture vocabularies kept small
  so baselines stay tractable.
- Build sizing: roughly 2.5–3× the rev 3 build. The plan will phase it
  (chassis → grammar families → lattice → router → prompts → live check)
  with per-phase verify gates.

## Adjudication list (owner)

1. Pause-set table (Moderate's rhythm): trigger-gated P1/P2 + always P3/P4
   (lead recommendation) vs all-four-always.
2. B4 global synthesis guidance: in now vs held for audience-framing.
3. C2 vetting: binary on/off + retry (lead compromise) vs fully out vs
   sensitivity dial (lead recommends against the dial).
4. Anything in "Still OUT" the owner wants pulled back in.
