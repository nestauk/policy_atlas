# Steerability refinement — the fold-in plan (pre-rev-4 working note)

Owner direction (2026-07-16): one large slice; get steering to a
state-of-the-art human-in-the-loop system; refine the full addition set
before folding into the contract. This note is the refinement surface —
each item carries the lead's recommendation and the disciplines it must
obey. Items marked **ADJUDICATE** need an owner call; the rest fold in as
recommended unless challenged. On adjudication this becomes contract rev 4.

## The target shape

**One steer-point lattice — two compile-target families (structured keys ·
guidance channels), one router.** *(Restructured at owner review,
2026-07-16: the coverage judgment moved to where it is actually judgeable —
after assess, not after acquire.)*

```
acquire ─P1*─> screen ──> classify ──> appraise ──> (characterise) ──P2──> select ──P3──> extract ──> group ──P4──> synthesise
        (*exception-only)                                    ↑______________additive re-search loops back to acquire
```

- **P1 post-acquire — exception point only, every mode.** Fires solely on
  hard triggers: backend errors, `adequacy_verdict="inadequate"`,
  `re_searched_still_thin` — no point assessing garbage. Options: deepen
  (depth rung) · rescope (filters) · guide the queries (B1) · accept-thin
  (flagged) · abort. Never a routine pause.
- **P2 pre-select — "the evidence base" (the coverage steer point).**
  Sits after screen + classify + appraise (+ characterise when composed),
  where adequacy is actually judgeable. Renders the full coverage
  picture: screened-in counts, document-type mix (classify), quality mix
  (appraise), themes (characterise, when present), zero-result queries
  and **the executed queries** (persisted per-call in `search.executed`
  events). Triggers: screened-relevant below floor · type-mix collapse ·
  quality collapse · coverage-verdict flags. Options: continue ·
  **"search more on X"** (free text → search guidance → **additive
  re-search segment**: acquire→assess re-walk, incremental by
  construction) · adjust criteria + re-screen (**replacement** at doc
  grain) · stage-2 toggle · re-characterise with guidance/bounds
  (replacement). Note: pre-approval of the generated query set stays a
  named seam (query generation is in-component); the iterative
  equivalent — guidance in, executed queries visible, targeted re-search
  after — is the shipped shape.
- **P3 post-select — "deepening selection"** (existing point, enriched):
  S0 trigger enrichment; the payload gains a **selection preview** (top
  selected docs with strata/scores/reasons + notable exclusions, from
  persisted `selected`/`excluded`) so the judgment is informed, not
  blind. Options gain **extraction profiles** (add ICF — natural home:
  this pre-extract boundary), **re-extract refresh** (D3), **strata
  scoping** (D6) and **doc exclusion** (D7) alongside the five existing
  options; the router compiles combined free-text asks ("fewer docs,
  favour strong UK evidence, keep the IFS paper") into one confirmed
  multi-lever delta.
- **P4 post-group / pre-synthesise — "the synthesis shape"**: proposal via
  `propose_synthesis_plan`; triggers from grouping per-facet flags.
  Options: only-these-themes / section edits (existing grammar) ·
  evidence emphasis boosts (type/tier columns — tag boosts dropped, see
  D4) · re-group coarser/finer (`grouping.granularity`) · re-group with
  guidance (B3) · as-proposed.

Every point: canonical floor options + orchestrator-authored run-specific
options **or free text through the router**; Unattended resolves per the
settled discretion model; every presentation/decision is a steering event
(the 024 chassis). Every re-run option declares its mode — additive or
replacement (§ The two re-run modes).

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
| "At the key decisions" *(default)* | moderate | P2 + P3 + P4 always (the base · the selection · the synthesis shape); P1 + watch-escalations when fired | routine boundary residuals | 3 |
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
- **B2 `extraction.guidance` (into the extraction prompt) — DROPPED;
  replaced by B2′ (owner review rounds 3–4, 2026-07-16).** Extraction's
  contract is *faithfulness*: downstream treats the findings layer as the
  complete substrate, and emphasis guidance inside a bounded token budget
  tilts recall (over-X, silently-under-Y); it would also enter the memo
  fingerprint, fragmenting cross-question extraction reuse. Both
  objections dissolve in B2′:
- **B2′ finding-relevance emphasis channel — IN (owner, round 4).**
  `context["extraction"]["relevance_emphasis"]`: bounded user-emphasis
  sentences ("cost-effectiveness matters most for this question"),
  fail-closed parsed, consumed by a **sibling annotator pass** — never by
  the extraction or vetter prompts. Pipeline: extraction unguided →
  vetting unguided (**verdict fenced by construction** — guidance never
  enters that call) → when (and only when) emphasis is present, a small
  annotator (`finding_relevance_v1`, mini-class, lead-authored) marks
  each surviving finding `relevance: priority | normal`, coverage-
  validated (each finding exactly once, the vetter validator pattern),
  fail-open to unannotated with a flag. **Persistence is run-scoped, not
  finding-scoped**: relevance is question-relative (memo-reused findings
  differ per question), so it lands as `relevance_annotations:
  {finding_id: …}` in that run's `extraction_result` JSONB — no schema
  change, no fingerprint participation, memo reuse fully preserved.
  **Consumer ships in-slice**: findings surfaced to synthesis (substrate
  tools + section proposal) carry the marks; the section-drafting prompt
  foregrounds priority findings where relevant; P4's proposal render
  shows priority counts per group. Authored at P2/P3 by user free text
  (router) or by the watch where the mode delegates; verbatim + compiled
  provenance as for every channel.
- **B3 `grouping.guidance`** — into discovery ("organise by policy
  instrument, not sector"). Provenance: grouping_provenance. **IN.**
- **B5 `characterise.guidance`** *(owner review, 2026-07-16)* — into the
  theme-discovery prompt ("organise around policy instruments; keep
  delivery-model themes separate"), symmetric with B3; pairs with the
  theme-bounds key and the landscape review/redo at P2. Provenance:
  `characterisation_result.grouping_provenance`. **IN.**
- **B4 `synthesis.guidance` (global) — HELD (owner, 2026-07-16)** for the
  audience-framing pair (two-overlapping-voice-levers risk). Global
  writing intents route through per-section focus fan-out + boosts
  meanwhile; refusal events meter residual demand.
- Existing channels the router uses from day one: `screening.criteria`,
  `synthesis.sections[].focus`.
- **Not channels (pinned OUT):** vetter prompts, grounding-judge prompts
  (integrity surfaces — users must not instruct their own verifier),
  classify (factual typing; the intent lands downstream in the rubric).

## Family C — postures: RETIRED (owner review, 2026-07-16)

The posture *family* is retired. The test that killed it: "what does
`strict` mean?" — screening strictness bundled consensus mechanics (reps,
quorum, tie policy, title-only rescue) that control decision reliability,
not the substantive bar; an opaque lever wearing a plain-language label,
redundant next to free-text **criteria** (substantive, inspectable) and
the appraise rubric / select emphasis (quality). **C1 dropped**; consensus
constants stay module-owned, like the vetter internals. **C2 vetting: no
steer of any kind** (quality-integrity surface; `vetting_failed` stays a
floor trigger only).

What survives moves to Family D as ordinary enumerated keys — granularity
and theme bounds are single, monotonic, directly-observable properties of
the *output* ("40 splinter groups → ~10 broad ones"), not bundles of
internals. The resulting intent taxonomy: **substantive bars →
criteria/guidance/rubric · output shape → enumerated keys · emphasis →
weights/boosts.**

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
- **D4 tag-boost vocabulary advertising — DROPPED (owner review,
  2026-07-16).** The open tag layer is disparate at live scale (the 017
  tag-consolidation trigger records exactly this fragmentation); an
  exact-match boost over a fragmented vocabulary boosts a sliver and
  silently distorts retrieval. The closed-vocabulary cases users actually
  want are already boostable columns (`primary_evidence_type`, appraisal
  tiers). The boost grammar keeps *accepting* tags (built, clamped,
  `unmatched_boosts` honest) but nothing advertises or authors them; the
  router steers tag-ish intents to type/tier boosts. Seam: tag boosts
  return after tag consolidation + hybrid matching over the open layer.
- **D5 `search.target`** — bounded override of
  `TARGET_CONFIDENT_RELEVANT` ("keep going until ~40 relevant"), clamped
  (e.g. 5–60), deep/standard loop only. **IN.**
- **D6 `selection.strata_scope`** *(owner review, 2026-07-16)* — scope or
  exclude strata/themes from selection ("only these themes go forward"):
  the post-characterise filtering intent `priority_strata` (boost-only)
  cannot express. Fail-closed; must-include conflicts flagged. **IN.**
- **D7 `selection.exclude_ids`** *(owner review, 2026-07-16)* — remove a
  named document, the complement of `must_include_ids`; flagged in
  provenance. **IN.**
- **D8 `grouping.granularity`**: `coarser | standard | finer` → the
  `group_max_labels` ceiling (multiplier on the derived clamp; `standard`
  ≡ as-built). *(Moved from the retired posture family.)* **IN.**
- **D9 `characterise.themes`**: `fewer | standard | more` → theme-bounds
  override; characterise's first directive parser (with B5 riding it).
  *(Moved from the retired posture family.)* **IN.**
- **Select** otherwise unchanged — already the richest grammar.

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
   free-text-authored deltas (structured keys, guidance channels) a user
   has, compiled through the same author-blind fail-closed grammar. One
   asymmetry by re-run mode (§ The two re-run modes): **additive** re-runs
   are self-decidable where the mode delegates; **replacement** re-runs
   bias-to-escalate in attended modes — they change what everything
   downstream sees, the routing rule's definition of substance. Integrity surfaces (grounding judge, vetter sensitivity) are
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

**The watch's information model — two-tier: push triage, bounded pull at
decision points (owner challenge upheld, 2026-07-16 round 5).** The first
cut (push-only "the watch sees the payload the user sees") failed the
owner's test: the payload is the *notification*; the user's real
information environment at a pause is the whole workspace (evidence
table, detail panels, coverage views, decision log) with agency to go
digging. The corrected principle: **symmetry of the information
environment, not of the payload** — same canonical state, same authority
to consult it; the user reads it through UI projections, the watch
through bounded read tools over the same tables.

- **Tier 1 — boundary triage, push-only.** Every routine boundary call
  gets the composed deterministic context: (1) orienting header (refined
  question/intent, plan summary, mode, standing instructions); (2) the
  boundary payload (check-in render, fired triggers, previews/proposals,
  canonical options); (3) a run-so-far digest incl. prior steering
  decisions read from the events (decision memory). One cheap judgment:
  notable or not, route or proceed. No tools, no loops.
- **Tier 2 — decision-point deliberation, bounded pull.** At P1–P4 and
  watch-escalated boundaries — where a user would go digging — the watch
  may make a **capped** number (~4) of **deterministic, read-only** calls
  before deciding or authoring options: `lookup` (id/filter-addressed
  canonical rows + aggregates) and `query_findings` at the later points.
  E.g. pull the documents in the dropped stratum before authoring
  "deepen 'rural childcare' (14 docs)"; check what screened out before
  proposing a subtopic re-search. **Never `retrieve`** (chunk-text
  injection surface) · **never `search`** (egress from a non-user
  surface — the Q&A rule). In-repo precedent: synthesis's agentic
  section loop over scoped read tools.
- **Audit by eventing the deliberation**: each tool call + result digest
  lands in the decision's event payload — replay-from-Postgres shows what
  the watch looked at, not just what it decided.
- **Insufficient context after the cap → bias-to-escalate** with the
  reason evented. Containment unchanged: payload and tool-result text is
  corpus-derived data, data-framed; watch output still compiles through
  the author-blind grammar.

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
- (c) **Discretion is what Unattended means** *(SETTLED — owner,
  2026-07-16)*: choosing Unattended is the delegation; pinned rules
  override where given; hard stop rules are always honoured (discretion
  can never override a declared stop); every decision evented with
  reasoning + collated; no-pinned-rule decisions flagged loudest,
  reviewed first. What approval makes checkable is the delegation +
  pinned rules; the FOI record improves over blanket proceed-and-flag
  because decisions carry reasoning.

  **How standing instructions are authored (owner UX question,
  2026-07-16):** never a blank config field. When the user picks
  Unattended, the **planner walks the steer points and proposes a
  plain-language default for each** (the suggested-answers pattern),
  anchored to the canonical option vocabulary; the user accepts, edits
  in prose (the router compiles it to option ids/rules), or skips —
  skipped points fall to watch discretion under (c), flagged loudest.
  The pinned rules are visible plan content approved with the plan
  (017's consent posture, preserved).

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

## The two re-run modes (owner distinction, 2026-07-16)

Every steer that re-runs work is one of two kinds, and the kind is
first-class vocabulary — declared in the confirmation ("this will *add
to* your evidence base" vs "this will *redo* selection, replacing the
current one"), stamped on the steering event, and visible in the history
projection.

- **Additive re-entry** — the incremental model, cheap by construction:
  re-search adds sources (acquire dedups; screen/classify/appraise
  process only the unprocessed); adding the ICF profile is additive at
  the profile grain (memo skips existing IOF work); adding a facet is
  additive at the facet grain. Prior outputs stand; the base grows;
  coverage recomputes over the union; provenance records all contributing
  runs. This is P2's "search more on X" **segment re-entry**: the walk
  jumps back to acquire with the amended directive and proceeds forward
  through the boundary again (contract 6b's single-component re-run
  mechanics, generalised to a bounded segment).
- **Replacement re-run** — for run-scoped outputs downstream references by
  one run id: reselect (the pattern's origin), re-characterise, re-group
  the same facet, re-screen with *changed criteria* (replacement at the
  **document** grain — new screen rows must become the effective row over
  already-screened docs, which touches the effective-screen-row read
  rule: real plan-design work, named here honestly). Semantics: old rows
  persist immutably; the walk's reference moves — **superseded, never
  deleted**, the same posture as plan versions and the audit spine.

Disciplines: (1) mode declared at confirmation + on the event ·
(2) replacement never deletes · (3) the watch's delegation boundary
follows the mode (additive self-decidable, replacement bias-to-escalate —
watch discipline 3).

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
4e. **Tooling at routine boundaries** — partially adjudicated IN (owner,
   2026-07-16 round 5): bounded pull ships at decision points (tier 2,
   above); tooling for tier-1 *triage* stays deferred (cost explodes for
   little value) with insufficient-context escalations as its demand
   meter.
4c. **Query-set pre-approval** — approving generated queries before they
   execute requires an in-component pause (generation happens inside
   acquire's run). The iterative equivalent ships: B1 guidance in,
   executed queries visible at P1/P2, targeted additive re-search after.
4d. **Tag boosts** (see D4) — return after tag consolidation + hybrid
   matching over the open tag layer.
5. **Transcript persistence / turn tables — re-homed to 025 (owner,
   2026-07-16)**: not workspace-cluster-distant after all — the co-pilot
   Q&A slice *requires* persisted per-user sessions (spec: "multiple
   persisted sessions; browse previous ones"), so the transcript
   companion store (per-user/per-project turn table, surface +
   session/`capability_run` linkage, window-plus-recall context
   assembly) lands with 025, answering chat-continuity-on-return one
   slice out. 024 ships the anchors (`session_id` on `capability_run`,
   verbatim text in events). Provider-side conversation state (OpenAI
   Responses, Bedrock sessions) stays forbidden — the record lives in
   our store (018 standing constraint; audit/FOI/portability).

## Cross-cutting cost & discipline ledger

- Every new grammar key: fail-closed parser + provenance + tests; D3
  additionally fingerprint participation; D8/D9 carry guard tests pinning
  `standard` ≡ as-built. Criteria-changed re-screen (replacement at doc
  grain) adds effective-screen-row read-rule work — the one re-run with
  real plumbing cost, plan-designed.
- Prompt surfaces touched (all lead-authored): the **`orchestrator_v1`
  prompt family** — one system-prompt family, three moment-scoped
  framings: planning turn (absorbing `planner_v6`: steer-point defaults
  vocabulary ×4, posture awareness), steer interpretation/router, and the
  boundary watch (routing + option authoring + in-loco-user decisions) —
  plus `finding_relevance_v1` (the B2′ annotator) and guidance-composition
  points in search-gen / group discovery / characterise theme-discovery /
  synthesis section prompts (data-not-instructions framing blocks;
  priority-finding foregrounding rides the synthesis section prompt;
  extraction-prompt and synthesis-global channels dropped/held per
  B2/B4).
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

## Plan-gate adjudications (2026-07-16)

Plan-stage adversarial review (deep-reasoner lane of record; the Codex
family-flip attempted twice, blocked on workspace credits — session
resumable). All findings adjudicated into the plan; headline: **B1** —
the no-schema recency-first screen supersession proved infeasible
(partial unique index blocks the fresh-row INSERT), briefly excluded,
then **restored by the owner's schema-gate expansion** ("I'm fine with
schema changes for this slice") on the lead's generation-supersession
design: `screen_generation` column + widened partial unique index;
generation-first effective-row ordering; skip-bypass only under
explicit re-screen. Schema gate now = capability_run (+ composite runs
FK) + screen_generation (+ index). Also folded: task-2 emission rescope
(per-path wiring lives with the path's task; rubric-10 closes at
Phase-5 exit) · pre-first-run emission invariant · B2′ split
(fencing/consumer → deep-reasoner) · composite runs FK ·
mode_change on `steering.decision` · authority-order test owned ·
Phase-5 split seam pre-marked · gate framing corrected (verify-fast
defers less than implied).

## Owner cost adjudication (2026-07-16, after the adversarial round)

The M5 cost exposure resolved by design, not de-scope — **A + B + C
adopted, D dropped**: (A) **structurally gated invocation** — watch
called only at decision points / fired triggers / anomalous check-ins;
clean boundaries emit deterministic `clean_boundary`
`agent_judgement_routed` events, no LLM; (B) **single-shot deliberation
over pre-fetched bundles** under the **option-completeness rule** (every
canonical option answerable from the bundle or marked
requires_user_input; P3 enriched: selected-vs-pool composition,
full-text availability, budget picture, ranking-trust signals;
representative digests, never full doc lists); fallback read-tool loop
only on "insufficient", capped ≤2; (C) **model routing by moment** —
mini-class triage, judgment-class decisions/authoring (cost tiering, not
agent identity — decision-point authoring remains the EB-expert's future
socket); (D — dropped, 017 standing rule reaffirmed) **no cost language
on any user-facing surface**: caps are internal constants + telemetry;
escalations never mention budgets. New envelope: ~6–10 orchestrator
turns typical Moderate, ~15–20 worst case (was 35–40); live check
~$5–12 / 30–45 min. This supersedes the tier-1/tier-2 loop-first
framing above where they differ.

## Adversarial adjudication (2026-07-16, deep-reasoner lane — codex
## attempted first, workspace out of credits)

All findings accepted in substance; deltas folded into the contract
(which stays binding over this note where they touch the same ground):
**M1/M2** flow-back + ADR scope expanded — the watch discharges the
spec's "no first-principles runtime classifier" ⏸ (additive,
floor-bounded, non-taxonomic) and Unattended (c) revises the
unanticipated-substance mechanism (proceed-and-flag → watch discretion;
`unconfigured_default` retained as the loudest flag class) · **M3**
segment re-entry re-scoped as a new bounded runner construct (one
re-entry cycle per boundary), its own plan phase · **M4**
criteria-changed re-screen re-scoped as a supersession redesign
(stage-2-supersession = halt-and-re-gate trigger; consumers move in
lockstep) · **M5** egress + live-check figures re-derived for tier-2
(~35–40 turn ceiling; live check ~$10–20/45–60 min) · **M6** generic
floor pinned for non-lattice Frequent boundaries (continue · mode ·
abort · free text) · **M7/n3** poisoned-input fixtures + author-blind
scrub-equality tests added; ADR records the accepted LLM→LLM residual in
delegated modes · **M8** sizing re-priced ~4–6×; pre-authorised overrun
de-scope ordering recorded (tier-2 deliberation first, criteria-changed
re-screen second) · **m1** transaction invariant qualified (pause/
refused/rejected = standalone appends) · **m2** every triage verdict
emits `agent_judgement_routed` · **m3** payload-key read path noted ·
**m4** planner label corrected (v5 → orchestrator_v1 planning moment);
section-prompt foregrounding = additive block on v7 → v8 with
cost-baseline note · **m5** Minimal behaviour change named in flow-back ·
**m6** tier-1→tier-2 promotion rule pinned.

## Adjudication list — SETTLED (owner, 2026-07-16)

1. **Unattended model: (c) discretion-is-the-mode.** Choosing Unattended
   is the delegation; pinned rules override; hard stops always honoured;
   no-pinned-rule decisions flagged loudest, reviewed first.
2. **B4 global synthesis guidance: HELD for audience-framing.** Global
   writing intents route through per-section focus fan-out + boosts; the
   global voice lever lands with the audience-framing pair as one design.
   Refusal events are the demand meter meanwhile.
3. **C2 vetting: FULLY OUT.** No vetting steer of any kind this slice —
   no binary, no retry action, no dial; vetter behaviour stays entirely
   fixed. (`vetting_failed` spikes remain a floor *trigger* — the user is
   told; they just steer other levers in response.)
4. No pull-backs from "Still OUT".

**Settled at this working note (owner, 2026-07-16):** four modes with the
delegation-posture labels + decider dial · the mode table above · the
orchestrator watch with full-user-surface discretion · orchestrator-
authored options on the canonical floor · one orchestrator prompt family ·
enlarged trigger floor · EB-expert stays post-eval with sockets shipped.

**Settled at owner review round 5 (2026-07-16):** the watch information
model corrected and pinned — two-tier: push-only triage at routine
boundaries; **bounded read-only deliberation at decision points**
(`lookup` + `query_findings`, call cap ~4, every call + digest evented,
never retrieve/search) — symmetry of the information *environment*, not
the payload; build grows a notch (tool plumbing on the in-repo loop
precedent).

**Settled at owner review round 4 (2026-07-16):** B2′ finding-relevance
emphasis channel folded IN (owner call, upgrading round 3's seam):
sibling annotator pass, verdict fenced by construction, run-scoped
persistence in `extraction_result` JSONB (question-relative relevance;
memo reuse preserved; no schema change), synthesis consumer in-slice,
pay-only-when-steered.

**Settled at owner review round 3 (2026-07-16):** Unattended (c)
confirmed + the planner-authored standing-instructions flow pinned · B2
extraction guidance dropped (faithful-substrate + memo-reuse rationale;
finding-grain relevance annotation recorded as a verdict-fenced,
eval-gated seam) · transcript persistence re-homed from workspace cluster
to 025 (Q&A requires persisted sessions; provider-side state stays
forbidden) · 025's scope note grows accordingly.

**Settled at owner review round 2 (2026-07-16):** lattice restructured —
P1 exception-only, P2 = pre-select coverage point with executed-query
visibility + additive re-search segment re-entry, Moderate = P2/P3/P4 ·
B5 characterise guidance + landscape review/redo · D6 strata scoping +
D7 exclude_ids + P3 selection preview · posture family retired (C1
dropped; granularity/theme-bounds → D8/D9) · D4 tag boosts dropped to a
named seam · the two re-run modes (additive vs replacement) pinned as
first-class vocabulary with the watch delegation asymmetry.
