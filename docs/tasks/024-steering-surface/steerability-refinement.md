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

**Modes — SETTLED (owner, 2026-07-16): four modes kept, renamed to the
delegation-posture vocabulary; the organising principle is the decider
dial.** *Every decision surfaces in the record; the mode never changes
what is decided or what is visible — it moves the decider between the
user and the orchestrator.* Check-in stream ≠ pauses: progress check-ins
stream (and persist as events) in every mode; the mode governs only what
blocks and who answers.

| User-facing label ("When should I come back to you?") | Plan value | User decides live | Orchestrator decides (recorded + flagged) | Pauses, healthy standard run |
|---|---|---|---|---|
| "Often — walk me through it" | frequent | everything (watch only *recommends*) | nothing | ~8–10 |
| "At the key decisions" *(default)* | moderate | P3 + P4 always; P1/P2 + watch-escalations when fired | routine boundary residuals | 2 |
| "Only if something needs my judgment" | minimal | fired triggers + watch-escalated substance | everything else, within the user surface | 0 |
| "Never — here are my standing instructions" | unattended | nothing live | per the adjudicated Unattended model (watch section) | 0, guaranteed |

Spec flow-back: execution-orchestration § Steering modes gets this table +
labels and discharges the standing "Thorough" label-sync note. Plan schema
keeps the four values; presentation changes only.

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

## The orchestrator watch — the decider layer (owner-driven, 2026-07-16)

The orchestrator observes every component boundary (input/output stage) and
routes each decision per the decider dial: nothing notable → log ·
notable-but-within-intent → decide itself (flagged, evented) → needs the
user (by mode) → pause. It is the third *moment* of the one orchestrator
agent (planning turn · steer interpretation · boundary watch) — **not a new
agent**: one backend seam, one prompt family (`orchestrator_v1`,
moment-scoped framings), one execution profile, the shared session id, so
the watch reads the same refined intent the planning conversation
produced. Egress accounting stays honest: new call sites carrying project
data (~6–9 boundary calls/run, judgment-class model, stub for tests).

**Layering disciplines (each hard-constrained):**

1. **Structural triggers are the floor, never suppressible.** The declared
   trigger table fires deterministically regardless of the watch's
   judgement; the watch can add escalations, never remove one. Escalation
   never depends on an LLM recognising substance in the moment.
2. **Bias-to-escalate when substance-or-unsure** (the spec's rule) — in
   modes where the user is available, prefer routing over self-deciding.
3. **Self-decisions use the full user surface, no more, no less** (owner
   challenge upheld, 2026-07-16): the watch decides by the same options +
   free-text-authored deltas (structured keys, postures, guidance
   channels) a user has, compiled through the same author-blind fail-closed
   grammar. Integrity surfaces (grounding judge, vetter sensitivity) are
   closed to everyone. Known risk, named for eval: watch-authored guidance
   entering downstream prompts is an LLM→LLM channel with no confirm gate —
   controls are attribution, flags, the review-first collation, and user
   override at any attended pause; compounding across boundaries is an
   eval measurement, not a silent assumption.
4. **Attribution is first-class**: `decided_by: user | orchestrator |
   standing_default` and `authored_by` on every decision/option; agent
   decisions emit in the spec's `agent_judgement_routed` vocabulary with
   the watch's reasoning and authored text verbatim. The history
   projection renders one uniform story; only the decider varies by mode.
5. **Fail-safe is the floor**: a watch-call failure degrades to pure
   structural routing (today's behaviour). The run never depends on the
   judgement layer being up.

**Orchestrator-authored options (owner, 2026-07-16 — IN).** At every
pause the watch composes 2–5 run-specific suggested responses (label +
why + compiling delta) — the planner's suggested-answers pattern (017
decision 5) moved to boundaries: "Deepen 'rural childcare subsidies' (14
docs, dropped by budget)" instead of "Deepen the clusters you name."
Authoring failure degrades to the canonical menu, never blocks. The
canonical per-point options survive as two load-bearing things: the
**deterministic floor** (always present, always valid) and the **stable
vocabulary** `steer_point_defaults` rules and tests anchor on (ephemeral
authored options can anchor neither). Authored options must compile —
inexpressible proposals are caught by validation and logged, so the
refusal demand-meter survives.

**Unattended model (ADJUDICATE — a/b/c; lead recommends c):**
- (a) Status quo: declared rules + proceed-and-flag only; zero runtime
  judgement. Strongest approval-time checkability, weakest delegation.
- (b) Opt-in discretion grant: the plan visibly carries
  `orchestrator_decides` per steer-point class (± standing-instruction
  text); the *delegation* is checkable at approval even though each
  decision isn't.
- (c) **Discretion is what Unattended means** *(recommended)*: choosing
  Unattended is the delegation; pinned rules override where given; hard
  stop rules are always honoured (discretion can never override a
  declared stop); every decision evented with reasoning + collated;
  no-pinned-rule decisions flagged loudest, reviewed first. What approval
  makes checkable is the delegation + pinned rules; the FOI record
  improves over blanket proceed-and-flag because decisions carry
  reasoning.

**New floor triggers (Minimal's guarantee, enlarged from the study):**
screen quality-collapse (rep-failure/quorum-failure rates, stage-2 demote
spike) · classify `Unknown` share · appraise `by_score` collapsed-to-weak ·
extraction failure / `vetting_failed` spikes · **downstream capability
reduced** (a discretionary component failed/skipped so the rest of the run
is structurally poorer — e.g. group failed → ungrouped synthesis; today
collation-only). Completeness beyond the cheap-and-persisted floor is the
watch's residual coverage — no exhaustive pre-enumerated taxonomy (spec).

**The capability-agent boundary and its sockets (walk-forward by
construction).** The watch is the orchestrator as *decider-in-loco-user at
delegated decision points*; the deferred EB-expert is a capability
sub-agent as *default directive author on every leg* (replacing the
deterministic compile as the routine path). The EB-expert stays post-eval
as 017 pinned — its every-leg output has no human filter until the eval
harness can measure directive quality, whereas every watch exit is either
human-filtered (options) or flagged-and-collated (bounded decisions). 024
builds its sockets so the later fill is a backend swap, not surgery:
(1) author-blind compile (already the design) · (2) `authored_by`/
`decided_by` attribution in the events (projection unchanged when the
author changes) · (3) the authoring seam as a protocol — "boundary state +
intent → suggested responses / decision" — the orchestrator implements
today; post-eval the EB-expert plugs in behind it (and at the runner's
existing `leg_directive` slot), with the orchestrator still the only
user-facing surface. **Authority order is fixed regardless of author:
user > declared rules > orchestrator. Authorship is a seam; authority is
not.**

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
   *(The watch inherits the same limit: it adjusts within the composed
   chain, never recomposes it.)*
4b. **The EB-expert capability agent** (every-leg directive authoring,
   domain-expert persona) — post-eval as 017 pinned; 024 ships its three
   sockets (watch section) so arrival is a backend swap.
5. **Transcript persistence / turn tables** — workspace cluster;
   `session_id` anchors are in (1b).

## Cross-cutting cost & discipline ledger

- Every new grammar key: fail-closed parser + provenance + tests; B2/D3
  additionally fingerprint participation; C1 changes screen's consensus
  path behind a posture default that reproduces today's behaviour exactly
  (guard tests pin `standard` ≡ as-built).
- Prompt surfaces touched (all lead-authored): the **`orchestrator_v1`
  prompt family** — one system-prompt family, three moment-scoped
  framings: planning turn (absorbing `planner_v6`: steer-point defaults
  vocabulary ×4, posture awareness), steer interpretation/router, and the
  boundary watch (routing + option authoring + in-loco-user decisions) —
  plus guidance-composition points in search-gen / extract ×2 / group
  discovery / synthesis section prompts (data-not-instructions framing
  blocks).
- Schema: **unchanged beyond decision 1b** — all new steering state rides
  `evidence_scope.context` + result-table JSONB provenance.
- Eval: every steer-bearing lever is versioned in provenance, so the eval
  slice can condition on steering state; posture vocabularies kept small
  so baselines stay tractable.
- Watch egress: ~6–9 boundary calls/run carrying component outputs +
  authored options — named in the contract's egress gate alongside the
  router's pause-time calls; all behind the one orchestrator seam with a
  deterministic stub (zero-egress CI unchanged).
- Build sizing: roughly 3–3.5× the rev 3 build. The plan will phase it
  (chassis → grammar families → lattice → watch/router → prompts → live
  check) with per-phase verify gates.

## Adjudication list (owner) — remaining

1. **Unattended model**: (a) declared-rules-only · (b) opt-in discretion
   grant · (c) discretion-is-the-mode *(lead recommends c; hard stops
   always honoured in every variant)*.
2. **B4 global synthesis guidance**: in now vs held for audience-framing
   (two-overlapping-voice-levers risk).
3. **C2 vetting**: binary on/off + retry-failed (lead compromise) vs fully
   out vs sensitivity dial (lead recommends against the dial).
4. Anything in "Still OUT" to pull back in.

**Settled at this working note (owner, 2026-07-16):** four modes with the
delegation-posture labels + decider dial · the mode table above · the
orchestrator watch with full-user-surface discretion · orchestrator-
authored options on the canonical floor · one orchestrator prompt family ·
enlarged trigger floor · EB-expert stays post-eval with sockets shipped.
