# Task contract: 024-steering-surface

> **Status:** drafted (rev 4, 2026-07-16). Contract approved: _pending_ ·
> Plan approved: _pending_ · ADR: expected (steering-event vocabulary ·
> sequencing-invariant revision · the decider dial).
>
> **Rev history**
> - **rev 4** (2026-07-16): **ground-up rewrite** (owner call) from the
>   settled design record after four owner review rounds —
>   [steerability-refinement.md](steerability-refinement.md) is the design
>   annex this contract binds; [steer-point-study.md](steer-point-study.md)
>   is the evidence base behind it. Supersedes revs 1–3 wholesale.
> - **rev 3** (2026-07-15): capability_run entity approved (walk identity);
>   co-pilot Q&A sequenced as 025.
> - **rev 2** (2026-07-15): owner ship-list S0+S1+S2 (superseded by the
>   rev 4 lattice, which absorbs them).
> - **rev 1** (2026-07-15): initial draft (persistence + interpreter +
>   study).

## Goal

Make Policy Atlas's steering a state-of-the-art human-in-the-loop system
(owner direction, 2026-07-16), in one large slice. The organising
principle: **every decision surfaces in the durable record; the steering
mode never changes what is decided or what is visible — it moves the
decider between the user and the orchestrator.** Four strands:

1. **A durable steering record.** Every check-in, pause (options +
   triggers), decision (user, orchestrator, or standing-default), rejected
   adjustment, refused intent, and re-run becomes a canonical `event_log`
   event keyed to a new `capability_run` walk identity — so a front-end
   rebuilds the orchestrated conversation's decision history from
   Postgres alone, across multiple runs per project.
2. **One orchestrator, three moments.** The planner, the free-text
   steering **router**, and the boundary **watch** are one agent (one
   backend seam, one prompt family, shared session): the router compiles
   prose at pauses into multi-stage bounded deltas (confirm-before-apply,
   honest refusal); the watch observes every component boundary, routes
   decisions per the decider dial, authors run-specific options, and
   decides in loco user where the mode delegates — within the user's own
   surface, attributed, fail-safe to the deterministic floor.
3. **The steer-point lattice + grammar widening.** Four steer points (P1
   search-exception · P2 evidence-base coverage, pre-select · P3
   deepening-selection, enriched · P4 synthesis shape) over widened
   fail-closed grammars: four guidance channels and seven structured keys
   (annex §Families), with the two re-run modes (additive vs replacement)
   as first-class vocabulary.
4. **Modes as delegation postures.** Frequent · Moderate · Minimal ·
   Unattended, renamed to the "when should I come back to you?"
   vocabulary; Unattended = discretion-is-the-mode with planner-authored
   standing instructions.

## Deliverable

PR landing:

- **`capability_run` entity** (decision 2): table + nullable
  `runs.capability_run_id` + alembic migration + runner threading — the
  walk's identity, the multi-run grouping key, the planning-conversation
  anchor (`session_id`).
- **Steering events** (decision 1): `steering.pause` · `steering.decision`
  (with `decided_by`/`authored_by`, verbatim `user_text`,
  `interpreted_action`, re-run mode) · `steering.rejected` ·
  `steering.refused` · `component.skipped` · `agent_judgement_routed` —
  zero-schema JSONB on the existing `event_log`.
- **History read model**: `steering_history(conn, project_id,
  capability_run_id=None)` — the deterministic per-walk projection; the
  front-end's read surface and the rebuild test's subject.
- **The orchestrator seam** (decision 3): one backend protocol + live
  structured-output implementation + deterministic stub; the
  `orchestrator_v1` prompt family (planning turn absorbing `planner_v6` ·
  router · watch), lead-authored.
- **The lattice** (decision 5): P1–P4 wired into the runner with canonical
  floor options, authored options, triggers from persisted state only,
  selection preview at P3, `propose_synthesis_plan` wired at P4.
- **Grammar widening** (decision 6): channels B1/B3/B5 + the B2′
  finding-relevance annotator (`finding_relevance_v1` prompt + run-scoped
  annotations + the synthesis consumer); keys D1/D3/D5/D6/D7/D8/D9 with
  parsers, provenance, and guard tests.
- **Re-run machinery** (decision 7): segment re-entry (additive) +
  replacement re-runs generalised from reselect, incl. the
  effective-screen-row read-rule work for criteria-changed re-screen.
- **CLI wiring**: free text at every pause, confirmation rendering
  (fan-out plan + re-run mode declaration), mode labels, Unattended
  standing-instructions authoring in the planning conversation.
- **Spec/knowledge flow-back**: execution-orchestration § Steering modes
  rewritten (decider dial, mode table, labels — discharges the "Thorough"
  sync note); ADR; deferred.md (seams in/out per annex; 017 deviations
  discharged; 025 scope notes: transcripts + Q&A); `log.md` entry.
- Tests + `verification.md` with the pinned live check.

## Read first

- [steerability-refinement.md](steerability-refinement.md) — **the design
  annex**; this contract binds it. [steer-point-study.md](steer-point-study.md)
  — the component-by-component evidence.
- [execution-orchestration](../../specs/system/execution-orchestration.md)
  — steering modes + routing rule (this slice revises both), durability.
- [plan-as-object](../../specs/system/plan-as-object.md) — audit posture;
  plan-field ↔ chat-turn provenance (the verbatim-text rule's origin).
- [EB capability.md](../../specs/capabilities/evidence-base/capability.md)
  § Check-in points; [components.md](../../specs/capabilities/evidence-base/components.md)
  for every touched directive surface.
- backend-architecture-reference §6/§9 (via the specs; frozen origin) —
  event-log spine, decision-log projection, `agent_judgement_routed`,
  transcripts non-canonical.
- 017 [contract](../017-orchestrator/contract.md) (decisions 2/5/6/11, rev
  2.5 blocker 2) + [verification](../017-orchestrator/verification.md)
  (flagged deviations) — what this slice discharges and revises.
- As-built: `runtime/steering.py` · `runtime/runner.py` ·
  `runtime/orchestrate.py` · `runtime/planner.py` (the seam pattern) ·
  `core/events.py` · the directive parsers named in the annex (search_loop
  · screen · select · extract · facet_values · synthesis_tools) ·
  `synthesise.propose_synthesis_plan`/`compile_synthesis_directive` ·
  the vetter coverage validator (`finding_vetter.py`) — B2′'s pattern.

## Scope / Out of scope

**In:** `runtime/` (steering, runner, orchestrate, planner→orchestrator
seam, new steering_interpreter/watch + history modules) · `core/schema.py`
+ one migration (decision 2 only) · the component modules gaining grammar
keys/channels (search_loop, screen, characterise, appraise, select,
extract + the B2′ annotator, facet_values/group, synthesis_tools/backend
prompt touch) · prompts (`orchestrator_v1` family, `finding_relevance_v1`)
· tests · spec flow-back/ADR/deferred/knowledge.

**Out (annex § Still OUT carries reasons; all recorded seams):** B4 global
synthesis guidance (held for audience-framing) · tag boosts (D4; post
tag-consolidation) · any vetting steer or judge steering · classify
steering · dual-view coverage / the policy object · mid-component pauses ·
query-set pre-approval · free-text replanning (the watch adjusts within
the composed chain, never recomposes) · the EB-expert capability agent
(sockets only — decision 9) · transcript persistence + co-pilot Q&A
(**025**, owner-sequenced, incl. the per-user transcript store) ·
front-end/API renderers · schema beyond decision 2.

## Decisions

1. **Steering events ride the existing `event_log` unchanged.**
   `after_component` events attach to the run they are about; walk-level /
   `before_component` events attach to the most-recent attempted run as FK
   plumbing, with semantics in the payload: every steering event carries
   `capability_run_id` + `plan_id` + `plan_version` + `boundary` (+
   `decided_by`/`authored_by`, verbatim `user_text` where prose was given,
   the interpreter/watch execution profile, and the re-run mode where one
   is triggered). Emission is transactional with its adjacent state change
   (plan version row, abandon flip) — the §9 invariant. Append-only stays
   inviolate.
2. **The `capability_run` entity — the one approved schema change.**
   `capability_run_id` · `project_id` · `evidence_scope_id` · `capability`
   ("evidence_base") · `plan_id`+`plan_version` at approval · `status`
   (running/succeeded/degraded/failed/aborted) · `session_id` (nullable) ·
   `started_at`/`ended_at`; plus nullable `runs.capability_run_id`.
   Deliberately not modelled: composition fields, artefact back-refs
   (derivable), turn tables (025). Alembic explicit-revisions roundtrip.
3. **One orchestrator, three moments, five watch disciplines.** One
   backend seam + `orchestrator_v1` prompt family + shared session. The
   **router**: prose → fan-out plan across not-yet-run components mixing
   channels and keys; partial compile with per-fragment honest refusal;
   **nothing applies unconfirmed** (attended modes). The **watch**: at
   every boundary — log · decide-in-loco-user · route — under the annex's
   five disciplines: (i) the structural trigger floor is never
   suppressible; (ii) bias-to-escalate when substance-or-unsure; (iii)
   self-decisions use the full user surface (keys + channels), author-
   blind-validated, with the re-run asymmetry (additive self-decidable,
   replacement bias-to-escalate); (iv) first-class attribution
   (`decided_by`/`authored_by`, `agent_judgement_routed`); (v) fail-safe:
   watch/router errors degrade to the deterministic floor (structural
   routing, canonical menu) — the run never depends on the judgement
   layer. **Authored options**: 2–5 run-specific suggested responses per
   pause on the canonical floor (the planner suggested-answers pattern);
   canonical options remain the floor and the stable vocabulary
   `steer_point_defaults` anchor. **Information model — two-tier** (annex
   § watch information model; symmetry of the information *environment*,
   not the payload): routine boundary **triage is push-only** — a
   deterministic composed context (orienting header + the payload a
   pausing user would be shown + a run-so-far digest incl. prior steering
   decisions from the events); at **decision points** (P1–P4 +
   watch-escalated) the watch gets **bounded read-only deliberation** —
   capped (~4) `lookup`/`query_findings` calls over canonical state
   (never `retrieve`, never `search`), each call + result digest evented,
   so replay-from-Postgres shows what the watch consulted, not just what
   it decided. Insufficient context after the cap → bias-to-escalate with
   the reason evented.
4. **Sequencing-invariant revision (ADR + spec flow-back).** 017 decision
   5's "one LLM call, pre-run" is deliberately revised: mid-run LLM calls
   are permitted at component boundaries only (router at pauses, watch at
   boundaries, the B2′ annotator inside extract's run as a component
   sub-step) — never steering a component from inside its own run.
   Component execution itself stays deterministic.
5. **The lattice and the modes** — as the annex pins them: P1 exception-
   only (coverage-record triggers) · P2 pre-select coverage (full
   picture: screened counts, type/quality mix, themes, executed queries;
   additive re-search segment; criteria+re-screen; re-characterise) · P3
   deepening-selection (S0-enriched triggers, selection preview, profile/
   refresh/strata/doc-exclusion options, combined free-text levers) · P4
   synthesis shape (proposal, sections, boosts, re-group). Modes renamed
   to the delegation vocabulary; **Moderate = P2+P3+P4 always, P1 fired**;
   Minimal = fired-only; **Unattended = discretion-is-the-mode (c)**:
   pinned rules override, hard stops always honoured, no-pinned-rule
   decisions flagged loudest; standing instructions are planner-authored
   per steer point at plan time (suggested-answers pattern), skippable.
6. **Grammar widening — exactly the adjudicated set.** Channels: B1
   `search.guidance` · B3 `grouping.guidance` · B5 `characterise.guidance`
   · **B2′** `extraction.relevance_emphasis` → the sibling annotator
   (extraction and vetting prompts untouched — verdict fenced by
   construction; run-scoped `relevance_annotations` in `extraction_result`
   JSONB; no fingerprint participation; synthesis consumer in-slice;
   pay-only-when-steered). Keys: D1 `appraisal.rubric` (partial type→tier
   override; derived `rubric_version`) · D3 `extraction.refresh`
   (fingerprint-bypass by class) · D5 `search.target` (clamped) · D6
   `selection.strata_scope` · D7 `selection.exclude_ids` · D8
   `grouping.granularity` · D9 `characterise.themes`. Every key/channel:
   fail-closed parser, bounded scrubbed strings (data-not-instructions),
   provenance, `standard`/absent ≡ as-built guard tests. The posture
   family is retired; the intent taxonomy (substantive bars →
   criteria/guidance/rubric · output shape → enumerated keys · emphasis →
   weights/boosts) is the router's compile map.
7. **Two re-run modes, first-class.** Additive re-entry (segment re-walk,
   incremental by construction, union coverage, all contributing runs in
   provenance) vs replacement re-run (reference moves, rows immutable —
   superseded, never deleted; criteria-changed re-screen = doc-grain
   replacement via the effective-screen-row read rule, plan-designed).
   The mode is declared in every confirmation and stamped on the event.
8. **The trigger floor** — computed from persisted state only, never
   recomputed, never watch-suppressible: the S0 select signals · P1
   coverage triggers · P2 coverage/type/quality collapse · P4 grouping
   flags · screen quality-collapse · classify Unknown share · extraction
   failure//vetting_failed spikes · **downstream-capability-reduced**.
9. **The EB-expert boundary.** Post-eval as 017 pinned. 024 ships its
   sockets: author-blind compile · authorship attribution in events · the
   authoring seam as a protocol (+ the untouched `leg_directive` slot).
   Authority order is fixed regardless of author: **user > declared rules
   > orchestrator**. Authorship is a seam; authority is not.
10. **Prompt surfaces** — all lead-authored, pinned, versioned in
    provenance: the `orchestrator_v1` family, `finding_relevance_v1`, the
    guidance-composition blocks (search-gen, group discovery, characterise
    discovery, synthesis section prompt incl. priority-finding
    foregrounding).

## Constraints & approval gates

- **Runtime egress (hard gate — approved by approving this contract):**
  the orchestrator moments (router at pauses; watch at ~6–9 boundaries/run
  carrying component outputs + authored options) and the B2′ annotator
  (per-doc mini-class, only when emphasis is set). All behind the one
  seam with deterministic stubs; CI stays zero-egress. No new search
  egress. No provider-side conversation state (018 constraint).
- **Schema (hard gate — approved):** exactly decision 2. Anything further
  is a stop condition.
- Deps: none. CI: untouched. Public interface: CLI additions only.

## Public / private boundary

Committable: code, prompts, specs, tests with synthetic steering text.
Private: live transcripts and real steering prose from live checks
(verification quotes structure, not content).

## Model route

Orchestrator moments: judgment-class via the existing OpenAI route,
env-overridable (`POLICY_ATLAS_ORCHESTRATOR_MODEL`); B2′ annotator:
mini-class. Bedrock posture unchanged.

## Disciplines binding this slice

Template set, plus: substance never silent (every decision surfaces —
the decider dial moves who answers, never visibility) · honest absence
(inexpressible = refused + evented, never approximated) · verbatim
attribution (user prose is data; never paraphrase-laundered) · append-only
events · faithfulness of the extraction substrate (nothing user-authored
enters extraction or vetting prompts) · replacement never deletes.

## Stop conditions

Template set, plus: any schema need beyond decision 2 · a reachable
boundary with no attachable run id · watch/router latency or cost proving
unusable live (ship floor-only + flag, don't silently degrade the seam) ·
the effective-screen-row rework revealing doc-grain replacement is
unsound (halt, re-gate that option).

## Acceptance checks

- `make verify` green (stubs; zero egress). Migration upgrade/downgrade
  roundtrip; schema diff exactly decision 2.
- **Deterministic tests:** steering events at every path (pause · all
  decision kinds × three deciders · rejected · refused · skipped ·
  auto-resolved) with payload completeness · the **rebuild test**
  (fresh-connection `steering_history` reproduces a scripted steered
  multi-walk story, two walks in one project) · router/watch wire-model
  fail-closed suites + confirm gate (unconfirmed never applies) +
  degrade-to-floor on backend error · watch deliberation bounds (call cap
  enforced; lookup/query_findings only; calls + digests evented; stubbed
  tools) · floor-trigger tests over seeded
  rows (all decision-8 classes) · authored-options degrade test · parser
  suites for every key/channel + `standard`/absent ≡ as-built guards ·
  B2′: vetter/extraction prompts byte-untouched, annotator coverage
  validation, run-scoped persistence, consumer payload carries marks ·
  re-run modes: additive re-entry reprocesses nothing already processed;
  replacement moves references with rows intact; segment re-entry
  fault-injected · D1 rubric override → derived rubric_version travels ·
  Unattended (c): pinned-rule override, hard-stop honoured, loudest-flag
  ordering.
- **Live check (pinned scope):** one Moderate run on the smoke corpus —
  free-text steers at P2 (coverage → additive re-search on a subtopic),
  P3 (combined levers + preview render), P4 (sections pruned via prose);
  one deliberately inexpressible intent (refusal + event); one Minimal
  segment where the watch self-decides (flagged); `steering_history()`
  captured from a fresh connection. P1 evidenced by fault-injected tests
  (a healthy corpus may not fire it). Cost: one planning conversation +
  one standard chain + ≤12 orchestrator calls — ~$5–10, ~30–45 min. No
  full e2e beyond this.

## Verification evidence expected

Command results · rebuild-test assertion · live `steering_history()`
capture (sanitized) · refusal-path event excerpt · B2′ fencing evidence
(prompt diffs) · migration roundtrip output · diff summary ·
public-safety confirmation · seams recorded.

## Risk tier & review focus

**Tier 3.** Review focus: event completeness vs the decider-dial claim
(no decision path without an event) · injection surfaces (user prose →
prompts: framing/bounds; watch-authored text → downstream prompts) ·
verdict fencing (B2′) and integrity surfaces staying closed · provenance
honesty (verbatim, attribution, execution profiles) · replacement/
additive semantics (no silent deletion, no double-spend) · projection
determinism · scope fidelity to the adjudicated set (no B4/D4/vetting
creep) · migration safety.
