# Task contract: 024-steering-surface

> **Status:** drafted (rev 1, 2026-07-15). Contract approved: _pending_ ·
> Plan approved: _pending_ · ADR: expected (sequencing-invariant revision +
> steering-event vocabulary).
>
> **Rev history**
> - **rev 2** (2026-07-15): **ship-list decided (owner)** — S0 + S1 + **S2**
>   (the owner upgraded the study's S0+S1 recommendation to include the
>   thin-search steer point). S2 moves from Out to In with its mechanics
>   pinned (decision 6b): boundary after acquire, reselect-precedent re-run.
> - **rev 1** (2026-07-15): initial draft. Origin: owner direction in the
>   steering-persistence conversation — (a) the eventual front-end must
>   rebuild the orchestrated conversation's check-in/steering history from
>   canonical state after the user goes away and comes back; (b) users
>   should be able to write free text at steer points, interpreted by the
>   orchestrator into bounded steering; (c) a design-phase study of further
>   steer points (owner picks the ship-list at this gate). Grounded on:
>   execution-orchestration § Steering modes + routing rule,
>   backend-architecture-reference §6/§9 (event-log spine, decision-log
>   projection, transcripts non-canonical), plan-as-object § audit posture,
>   the UX handoff §7.4 + wireframe frames 04/08/09, 017's contract
>   (decisions 5, 6, 11 + rev 2.5 blocker 2) and verification flagged
>   deviations, and [steer-point-study.md](steer-point-study.md).

## Goal

Make steering a first-class, durable, prose-capable surface:

1. **Steering-event persistence.** Every check-in boundary outcome the
   runner reports, every pause/steer-point presented (options + fired
   triggers), every user decision (continue · adjust · reselect · abort),
   every rejected adjustment, every refused intent, and every Unattended
   auto-resolution becomes a canonical `event_log` event — so the decision
   history is a projection over Postgres alone (the §9 spine; no transcript
   dependence), satisfying the spec lines 017 left thin: auto-resolutions
   "marked on the run record", refusals "recorded as a seam", and 017's own
   in-scope "steering-resolution events ride the run context".
2. **Free-text steering interpretation.** At any pause, the user may answer
   in prose. A new interpreter seam (planner-pattern: structured-output
   backend + deterministic stub) compiles the intent into the bounded
   steering vocabulary — option choice (params filled), directive-grammar
   `Adjust` delta, mode change, nudge, or abort — **confirm-before-apply**,
   with honest refusal (`refuse_inexpressible` + a recorded event) when the
   grammar cannot express it. Verbatim user text + interpreted action +
   interpreter execution profile persist together (never
   paraphrase-laundered).
3. **Steer-point surface per the owner ship-list** (decision 6; owner,
   2026-07-15): enrich deepening-selection's triggers from
   persisted-but-unread select signals (study **S0**), ship the
   pre-synthesise steer point on the built 022 compile machinery (study
   **S1**), and ship the thin-search steer point (study **S2**) with
   reselect-precedent re-run mechanics. Remaining candidates (S3–S5 + the
   grammar seams) land as named seams.

## Deliverable

PR landing:

- **Event vocabulary + emission** in the runner/steering layer:
  `steering.pause` (boundary, kind, options, triggers, plan id/version) ·
  `steering.decision` (response kind; verbatim `user_text` where prose was
  given; `interpreted_action`; `confirmed`; option id / new plan
  id+version / unattended rule+action) · `steering.rejected` (attempted
  delta + validation error) · `steering.refused` (verbatim intent +
  refusal) · `component.skipped` (resolves 017's flagged deviation).
  Zero-schema: JSONB payloads on the existing `event_log`, attached to the
  most-recent attempted run id (decision 1).
- **History read model**: `steering_history(conn, project_id)` — the
  deterministic projection that rebuilds the ordered
  check-in/pause/decision story from `event_log` + `orchestration_plan` +
  `runs`; the front-end's read surface and the rebuildability test's
  subject.
- **Interpreter seam**: `SteeringInterpreterBackend` protocol + live
  structured-output backend + stub; wire model = discriminated union over
  the closed steering vocabulary, validated fail-closed then compiled
  through the *existing* apply paths (`apply_adjustment` / reselect /
  option compile) — the interpreter can never bypass grammar validation.
  Prompt `steer_interpret_v1`, lead-authored.
- **CLI wiring** (`orchestrate.py`): pause menus accept option number OR
  free text; interpreted readings echo for confirmation; refusals render +
  record; Unattended unchanged (no pauses — auto-resolutions now emit
  events).
- **Ship-list steer points** (decision 6): S0 trigger enrichment ·
  S1 pre-synthesise steer point (options compiling via
  `compile_synthesis_directive`; triggers from grouping flags) ·
  S2 thin-search steer point (post-acquire boundary; triggers from
  `search_coverage_record`; deepen/rescope options compiling into the
  search directive grammar; accept-thin flagged; re-run mechanics per
  decision 6b).
- **Spec/knowledge flow-back**: execution-orchestration § Steering modes
  gains the steering-event + free-text-interpretation refinement; ADR;
  deferred.md updates (study seams recorded; 017 deviations discharged);
  `log.md` entry.
- Tests + `verification.md` with the pinned live check (§ Acceptance).

## Read first

- [execution-orchestration](../../specs/system/execution-orchestration.md)
  — steering modes, the routing rule, "human substance enters two ways …
  represented honestly in provenance"
- [backend-architecture-reference](../../sources/backend/backend-architecture-reference.md)
  §6 (steering) + §9 (event-log spine; decision log as projection;
  transcripts non-canonical; transaction invariant) — via the specs'
  distillation; source is frozen origin
- [plan-as-object](../../specs/system/plan-as-object.md) — audit posture
  across modes; plan-field ↔ chat-turn provenance (the verbatim-text rule's
  origin)
- [EB capability.md](../../specs/capabilities/evidence-base/capability.md)
  § Check-in points — the two spec-named steer points
- [steer-point-study.md](steer-point-study.md) — the ranked candidate study
  (this slice's design input)
- 017 [contract](../017-orchestrator/contract.md) (decisions 5/6/11, rev 2.5
  blocker 2) + [verification](../017-orchestrator/verification.md) (flagged
  deviations 1–2) — what this slice discharges
- As-built: `runtime/steering.py` + `runtime/runner.py` (pause/adjust/
  reselect paths; every emission site), `runtime/orchestrate.py` (CliIO /
  UnattendedIO), `runtime/planner.py` (the backend pattern the interpreter
  mirrors), `core/events.py` (append-only repository),
  `synthesis/synthesise.py` `propose_synthesis_plan` /
  `compile_synthesis_directive` (S1's built compile surface),
  `corpus/select.py` flags/provenance (S0's trigger sources)

## Scope / Out of scope

**In:**

- `runtime/steering.py`, `runtime/runner.py`, `runtime/orchestrate.py` —
  event emission, interpreter wiring, S1 steer point, S0 triggers.
- New `runtime/steering_interpreter.py` (+ prompt module) + stub.
- New history projection (module home plan-designed; likely
  `runtime/steering_history.py`).
- `core/events.py` — read helpers only if the projection needs them
  (append semantics untouched).
- Tests across all of the above; spec flow-back + ADR + deferred.md.

**Out (stay deferred — recorded with the study):**

- Steer-point candidates S3–S5 (post-screen bar, extract-profile point,
  post-group re-group) and all § Recorded-seams items (appraise rubric
  grammar, classify/characterise/vetter steering, granularity keys,
  threshold directive family, tag-boost vocabulary). S2's own grammar gaps
  (arm enable/disable, target/threshold overrides, query-term injection)
  likewise stay seams — S2 ships on the depth + filters grammar as built.
- Any new directive-grammar key. The interpreter compiles into grammars
  **as built**; inexpressible = refuse + record (the demand signal the
  deferred grammar seams wait on).
- Free-text steering→**replanning** (planner re-entry mid-run), `clarify`/
  `escalate` parking, narration voice, durable resume, transcript
  persistence (the CLI planning/steering transcript remains ephemeral;
  canonical events are the record — §9's line).
- Front-end/API surfaces; the decision-log/catch-me-up *renderers* (the
  projection function is the v1 read surface).
- Schema changes (decision 1 is zero-schema; a forced migration is a stop
  condition, not a quiet pivot).

## Decisions

1. **Events are zero-schema on the existing substrate, attached to the
   most-recent attempted run id.** Every reachable pause has a predecessor
   run (`runner.py` pauses only after a first check-in;
   discretionary-skip and unattended boundaries likewise follow attempts),
   so `event_log`'s non-null composite-FK `run_id` holds without migration
   — the same table-first adjudication as 017 rev 2.5, now with the event
   half completed. The alternative (synthetic plan-walk run row) is
   presented to the plan gate but not preferred: it buys cleaner semantics
   at the cost of `runs` no longer meaning "component attempt".
   Payload rule: every steering event carries `plan_id` + `plan_version` +
   `boundary`, so the projection can join decisions to plan lineage without
   inference. Emission is transactional with its adjacent state change
   where one exists (plan version row, abandon flip) — the §9 transaction
   invariant.
2. **The projection is the contract.** `steering_history()` returns the
   ordered decision story (pause → options/triggers → decision → outcome,
   with check-in renders reconstructable via `render_check_in` over
   `component.completed`/`failed` + steering events). Acceptance pins a
   **rebuild test**: run a scripted Moderate walk with steers (adjust,
   reselect-with-free-text, a rejected delta, a refusal), open a fresh
   connection, and assert the projection reproduces the full story from the
   database alone — no in-memory state, no transcript.
3. **Interpreter: planner-pattern seam, fail-closed twice.** Structured
   output validated against a closed discriminated union (first gate), then
   compiled through the existing steering apply paths (second gate —
   `SteeringAdjustmentError` behaviour identical to a hand-authored delta).
   Confirm-before-apply: the CLI echoes the interpreted reading
   (plain-language + the exact delta) and applies only on user confirmation;
   an unconfirmed reading re-prompts. Interpretation failure or an
   `inexpressible` verdict → `refuse_inexpressible` + `steering.refused`
   event. Model: judgment-class (planner precedent), env-overridable
   (`POLICY_ATLAS_STEER_INTERPRET_MODEL`); no OpenAI-specific server-side
   state (018 standing constraint).
4. **Sequencing-invariant revision (spec/ADR flow-back).** 017 decision 5
   pinned "the one LLM surface completes before acquire begins". This slice
   deliberately revises it: mid-run LLM calls are permitted for
   **steering interpretation only**, at pause boundaries, never inside a
   component run — the run's components remain deterministic. The revision
   lands as ADR + an execution-orchestration § Steering modes refinement,
   with failure semantics pinned: an interpreter error at a pause degrades
   to the numbered menu (the run never dies on interpretation).
5. **Verbatim-text provenance.** `steering.decision` carries `user_text`
   exactly as typed alongside `interpreted_action` + `confirmed` +
   interpreter execution profile (model, prompt version) — the
   plan-field ↔ chat-turn provenance rule applied at the steer grain;
   attribution stays honest ("never paraphrase-laundered").
6. **Ship-list (owner decision at this gate).** Study recommendation:
   **S0** (deepening-selection triggers gain `thin_full_text`,
   `unmatched_boosts`/`unmatched_priority_patterns`, `budget_exhausted`
   stratum exclusions, rerank-degradation counters — all read from
   persisted `selection_result`, no recomputation) + **S1** (pre-synthesise
   steer point: `before_synthesise` pause upgraded from bare check-in to
   steer point with options compiling through
   `compile_synthesis_directive`; triggers from grouping per-facet flags;
   Unattended auto-resolves via the existing `steer_point_defaults`
   machinery, which generalises to further points). **Owner selection
   (2026-07-15): S0 + S1 + S2 ship; S3–S5 recorded as seams.**

   **6b. S2 mechanics (pinned at owner upgrade).** Boundary: after
   `acquire`, before any downstream spend — so a steer re-runs acquire
   only, never a completed downstream component (the reselect precedent:
   user-attributed plan version row + component re-run + fresh run id
   threaded forward; `apply_reselect`'s shape generalised to a
   component-parameterised form rather than duplicated). Triggers read
   persisted `search_coverage_record` rows: `adequacy_verdict ==
   "inadequate"`, `stop_condition` ∈ {`re_searched_still_thin`,
   `budget_exhausted`, `wall_clock_exceeded`}. Options: **deepen** →
   `{"search": {"depth": <next rung>}}` (compiles; new plan version via the
   generic adjust path where acquire has not completed, re-run path where
   it has) · **rescope** → `filters` delta (compiles; requires user input)
   · **accept the thin base** → continue, flagged (the 017 rapid-mode
   honesty preserved) · **abort**. Whether the same point also reads
   post-screen thinness (screened-relevant counts vs the loop's floor) is a
   plan-gate design detail — the trigger data is persisted either way.
   Unattended: auto-resolves via `steer_point_defaults` like any steer
   point, `unconfigured_default` loudest.
7. **Unattended honesty completes.** Auto-resolutions emit
   `steering.decision` events (`response="auto_resolved"`, rule, action,
   `unconfigured_default` flagged loudest) — discharging "marked on the run
   record". The end-of-run collation stays derivable (a render over
   events + outcomes), not separately persisted.

## Constraints & approval gates

- **Runtime egress (hard gate — approved by approving this contract):** one
  new inference surface (steering interpreter), pause-time only. No new
  search egress.
- **Schema: none expected.** A design-forced migration is a stop condition
  (halt, re-gate).
- **Deps: none.** CI: untouched. Public interfaces: CLI gains free-text
  input at existing prompts (additive).
- Prompt-bearing surface (`steer_interpret_v1`) is lead-authored, pinned,
  versioned in provenance.
- `make verify` stays green, deterministic, zero-egress (stub interpreter
  in tests/CLI-stub mode).

## Public / private boundary

Committable: code, prompts, specs, tests with sanitized/synthetic steering
text. Private: live-run transcripts and any real steering prose from live
checks (verification quotes structure, not user content).

## Model route

Interpreter: judgment-class via the existing OpenAI route (planner
precedent), env-overridable; Bedrock migration posture unchanged (nothing
couples to OpenAI-specific API surface). All other components: unchanged.

## Disciplines binding this slice

Template set, plus: **substance is never silent** (every auto-resolution and
refusal is an event); **honest absence** (a steer the grammar can't express
is refused + recorded, never approximated); **verbatim attribution** (user
prose is data, never rewritten); events are **append-only** (no update path
enters `core/events.py`).

## Stop conditions

Template set, plus: the zero-schema event design fails (a reachable
boundary genuinely has no run id) → halt, present the migration options;
interpreter latency/cost at a pause proves unusable in the live check →
ship menu-only + flag, don't silently degrade the seam.

## Acceptance checks

- `make verify` green (stub backends; zero egress).
- **Deterministic tests:** event emission at every steering path
  (pause/decision/rejected/refused/auto-resolved/skipped) · payload
  completeness (plan lineage + verbatim text) · the decision-2 rebuild test
  (fresh-connection projection equals the scripted story) · interpreter
  wire-model fail-closed suite (malformed output, unknown option, delta for
  a completed component, inexpressible verdict) · confirm-before-apply
  (unconfirmed never applies) · interpreter-error degradation to menu ·
  S0 trigger unit tests over seeded `selection_result` rows · S1 option
  compile round-trip through `parse_synthesis_directive` · S2 trigger unit
  tests over seeded `search_coverage_record` rows + the acquire re-run path
  (fault-injected: a failed re-run degrades honestly, never double-spends
  downstream).
- **Live check (contract-time pin):** one scoped Moderate run on the
  standard smoke corpus exercising: a free-text steer at
  deepening-selection (interpreted → confirmed → reselect), a free-text
  steer at pre-synthesise (sections pruned via prose), one deliberate
  inexpressible intent (refusal + event), then `steering_history()` output
  captured from a fresh connection. S2 live firing is corpus-dependent (a
  healthy smoke corpus may not trigger thin-search); the honest pin is:
  S2 evidenced by the scripted fault-injected tests, exercised live only
  if the corpus fires it — never a contrived live corpus just for the
  check. Cost: one planner conversation + one standard-depth chain + ≤6
  interpreter calls — low single-digit dollars, ~20–30 min wall. No full
  e2e beyond this.

## Verification evidence expected

Command results; the rebuild-test assertion; the live-check
`steering_history()` capture (sanitized); event-log excerpt for the refusal
path; diff summary; public-safety confirmation; seams recorded.

## Risk tier & review focus

**Tier 3** (runtime egress + prompt surface + audit-integrity substance).
Review focus: event completeness vs the spec's decision-log claims ·
interpreter injection surface (user prose → structured action: confirm
gate, grammar fail-closed, no prompt-echo into applied state) · provenance
honesty (verbatim text, execution profile) · projection determinism ·
scope creep into deferred grammar seams.
