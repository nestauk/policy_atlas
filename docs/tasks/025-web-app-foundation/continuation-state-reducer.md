# Continuation-state reducer spec (task 025)

> Drafted at plan time from `src/policy_atlas/runtime/runner.py` **as-built**
> (branch `task/025-web-app-foundation`). Discharges the contract's
> **Context-parity** pin (§5, adversarial finding 3): an enumerated mapping of
> *every* piece of in-memory state the `run_plan` walk loop threads across a
> component boundary to the durable source a boundary **continuation walk** can
> reconstruct it from, plus the ordering rule and any transformation. When a
> pause **parks** (thread ends, `capability_run.status = paused`), the answer
> dispatches a continuation that must rebuild this state exactly — the parity
> test asserts identical composed context between an unbroken walk and a
> parked-and-continued walk.

All line numbers are `runner.py` unless prefixed. Durable substrates:
`orchestration_plan` (schema 1035-1064), `capability_run` (1075-1102), `runs`
(88-111), `event_log` (113-134). Event vocabulary appended via
`core/events.append` (max+1 sequence per project, single writer — events.py:23);
steering events via `steering_events` (`base_payload` carries
`capability_run_id`/`plan_id`/`plan_version`/`boundary`/`component`,
steering_events.py:59-90).

---

## 1. Field inventory

The loop's carried state is `steering_state` (a `_SteeringState`, 348-361) plus
ten locals initialised at 631-646. Every one crosses at least one boundary.

| # | Field | Init | Type / shape | Mutated at | Consumed by |
|---|-------|------|--------------|------------|-------------|
| 1 | `steering_state.plan` | 623 | `OrchestrationPlan` | replaced on adjust (2693), replacement-rerun keeps it (2780), segment-reentry keeps it (3019) | `leg_directive` (815), bundle/header/digest, `pause_points` |
| 2 | `steering_state.plan_id` | 623 | `uuid` | amendment → new plan id (2694/2781/3020) | steering event `base_payload` (1721) |
| 3 | `steering_state.plan_version` | 623 | `int` | amendment → +1 (2695/2782/3021) | `base_payload`, `plan.compiled` payload |
| 4 | `steering_state.plan_row_id` | 623 | `uuid \| None` | tracks current version row (2696/2783/3022) | adjustment persistence guard (2643, 2971) |
| 5 | `steering_state.chain` | 623 | `ComposedChain` | recomposed on adjust (2686), unchanged on rerun/reentry | `_remaining_steps`, router context (1987), segment bounds |
| 6 | `steering_state.pause_points` | 629 | `set[PausePoint]` | recomputed on adjust (2698) | boundary handlers (which boundaries pause) |
| 7 | `steering_state.pending_overlays` | 361 | `dict[str, dict]` | `_extend_overlays` on adjust (2691); carried unchanged on rerun/reentry | first-run directive merge (819-821), `_run_step_attempt(overlay=)` |
| 8 | `remaining_steps` | 631 | `list[ComponentStep]` | `pop(0)` each iter (649); recomputed after changed/reentry (739/808/972/1034) | the `while` loop itself (648) |
| 9 | `step_outcomes` | 632 | `list[RunStepOutcome]` | appended per component (755/871/988/…) | `_finish_run` → `RunPlanOutcome.steps`, `_log_run_summary` |
| 10 | `flagged_events` | 633 | `list[dict]` | appended: retrying/retried/failed/skipped/watch (757/847/873/989/…, `_watch_flag` 4079) | `render_collation` → `collation_render` (4398) — **parity surface** |
| 11 | `successful_runs` | 634 | `dict[component→uuid]` | set on success (862/3133), popped on discretionary fail (3188/2880) | `_reference_kwargs` (822), bundles (1627/1657), downstream run references |
| 12 | `attempted_runs` | 642 | `dict[registry→uuid]` | set per final attempt incl. failed (859) | discretion floor class-9 scan (`_DiscretionContext`, boundary handlers) |
| 13 | `blocked_discretionary` | 643 | `dict[component→reason]` | set on skip (756) / discretionary fail (1049/2880/3189) | `_skip_reason` (745/4410) → downstream skips |
| 14 | `completed_components` | 644 | `set[str]` | `.add` after each component incl. skip (776/885/1002) | `_remaining_steps` (4352), adjustment-bounds validation (2657) |
| 15 | `last_check_in_payload` | 645 | `dict \| None` | `_check_in` after each component (771/880/997) | before-component boundary trigger (650) + its render (655) |
| 16 | `most_recent_attempted_run_id` | 646 | `uuid \| None` | set per attempt (843) / rerun (688) / segment (727) | `event_run_id` for before/walk steering events (run-id attachment invariant, steering_events.py:11-15); skip-event run id (769) |

Not walk-derived state (recomposed per continuation from run config / injected
seams, out of the reducer): `engine`, `backends`, `io`, `discretion`,
`orchestrator`, `session_id` (the last is also durable on
`capability_run.session_id`, 1086).

---

## 2. Durable-source mapping

**Plan block (fields 1-6).** Single source: `orchestration_plan`. Every
amendment path calls `_persist_new_plan_version` (steering.py:1595) which flips
the prior row `status='superseded'` and inserts an `status='approved'`
successor at `version+1` (steering.py:1628-1645). Reconstruction rule: the
**unique non-superseded/non-abandoned row** for the project (equivalently
`max(version)` with `status='approved'`; `uq_oplan_project_version` guarantees
one). Transform: `plan = OrchestrationPlan.model_validate(row.payload)`;
`plan_id = plan_row_id = row.plan_id`; `plan_version = row.version`;
`chain = compose(plan)`; `pause_points = pause_points(plan.steering_mode, chain)`
(629 — pure functions, re-run at continuation, nothing to persist). Ordering:
version-monotone, no event replay needed. **Fully reconstructable.**

**`pending_overlays` (7).** Built only on the adjust path by `_extend_overlays`
(2691), which folds the *commit-layer* part (`commit_layer_overlay`) of each
adjustment's `directive_deltas`. Source: `steering.decision` events for this
walk with `rerun_mode is None` and `response ∈ {adjust, mode_change}`; the full
`directive_deltas` ride verbatim in `payload.interpreted_action.directive_deltas`
(`_interpreted_action`, 2453-2461, called at 2668-2672). Transform: replay
`_extend_overlays` over those decisions **in `event_log.sequence` order**
(merge-over per component key is order-sensitive; sequence order reproduces
it). Replacement-rerun (`rerun_mode='replacement'`) and segment-reentry
(`rerun_mode='additive'`) decisions carry `directive_deltas` too but never
touched overlays (2786/3025) — the reducer must filter them out by
`rerun_mode`. **Fully reconstructable** (no schema change).

**`successful_runs` (11).** Source: `runs` rows with
`capability_run_id = walk` (schema 88-111) joined to each run's `run.started`
event (`payload.component`, appended at 4485-4496) and terminal status
(`runs.status`, or `component.completed`/`component.failed` events — harness
192/160/185). Rule: **latest run per composed component (by
`runs.started_at`, tie-break `event_log.sequence` of `run.started`) whose
terminal status is succeeded**. This reproduces both "the reference moves to
the newer run" on replacement-rerun/segment-rewalk (2745/3133) and the pop on
discretionary failure (the latest run is the failed one → component absent).
**Reconstructable, transform-heavy.**

**`attempted_runs` (12).** Same join, keyed by `registry_component_for(...)`
(859), **latest attempted run incl. failed**. Rule: latest run per registry
component regardless of status. **Reconstructable.**

**`most_recent_attempted_run_id` (16).** The single latest `run.started` (max
sequence) under the walk. Elegant identity: the parked `steering.pause` event's
own `event_log.run_id` **is** this value at park time (the pause attached to it
per the run-id invariant, 1701/1733). **Reconstructable.**

**`completed_components` (14).** Union of components carrying a terminal
component event under the walk: `component.completed` (harness 192),
`component.failed` (harness 160/185/353/…), or `component.skipped`
(`_emit_component_skipped`, 762). Note: these events carry the **registry**
component (`config.component`); map back to composed names via the chain's
step list. **Reconstructable.**

**`blocked_discretionary` (13).** Set at skip (756, reason from
`_skip_reason`), main-loop discretionary fail (1049), and segment discretionary
fail (2880/3189). Sources: `component.skipped` payload (`reason`, emitted 762)
and `component.failed` payload (`error`/`reason`, harness 161/180-186). A spine
failure ends the run (never parks — 1039-1048), so a parked walk's blocked set
is discretionary-only, and each such block has a durable failed/skipped event
carrying its reason. Transform: `{required-component → reason}` for
discretionary components whose latest run failed or was skipped.
**Reconstructable.**

**`remaining_steps` (8).** Pure derivation `_remaining_steps(chain,
completed_components)` (4347-4352), rebuilt once fields 5 + 14 are known.
**Reconstructable** (no source of its own).

**`last_check_in_payload` (15).** `_check_in` (4882-4904) builds it from the
last component's `RunStepOutcome` + `headline_counts`. `headline_counts` comes
from the scalar keys of that run's `component.completed` payload (`_headline_counts`,
4821-4837 — durable). `wall_clock_s` is durable on the `component.timing`
event (4663). Rule: rebuild from the last-completed component's outcome (itself
rebuilt from `runs` + component events). **Reconstructable, transform-heavy.**
Interaction note: at continuation this non-`None` value re-fires the
before-component boundary for the next step (650) — the known unwatched
re-presentation seam the contract inherits, not a bug.

**`step_outcomes` (9) and `flagged_events` (10) / `collation_render`.**
`step_outcomes` = one `RunStepOutcome` per completed component (component,
run_id, status, wall_clock_s, retried, skipped, reason, `attempt_run_ids`);
every field is on `runs` + component events + `component.timing`.
`flagged_events` entries: `failed`→`component.failed`; `skipped`→
`component.skipped`; `retrying`/`retried`→ derivable from >1 run per component
with earlier failures; watch `auto_resolved` flags (`_watch_flag`, 4079)→
`agent_judgement_routed` + orchestrator `steering.decision` events. Rule:
rebuild both by iterating the walk's runs/component-events **in
`event_log.sequence` order** (in-memory append order is sequence order).
`collation_render = render_collation(flagged_events)` at finish (4398) — part
of the parity surface. **Reconstructable, transform-heavy** (the reducer must
reproduce list ordering and dict shapes exactly for collation parity).

**Composed-context surfaces (already durable-sourced today — the strongest
evidence for the contract's "no by design" claim):** the watch **digest**
(`_watch_digest`, 4055-4074) is *already* built by reading `steering.decision`
events filtered by `capability_run_id` from the durable log — never from walk
memory; the **header** (`_watch_header`, 4041-4052) is pure over `state.plan`
(durable); the **router context** (1968-1994) is pure over chain +
`completed_components` + options; **bundles** P2/P3/P4 (`_build_bundle`,
1610-1662) are built fresh from the DB over `successful_runs`. Once fields 1-16
are reconstructed, every parity surface (pause header, digest, P2-P4 bundles,
canonical + authored options, router surface, downstream run references,
overlays, collation) recomposes deterministically.

---

## 3. Gaps

No **stop-condition** gap exists: every quality-bearing field above has a
complete durable source or is closeable by an `event_log` JSONB payload
addition on an existing steering/component event (the contract-preferred, gated
zero-schema path). Two concrete gaps, both JSONB-additions:

- **G1 — parked-pause affordance flags not persisted.** `_pause_payload`
  (2428-2446) stores `kind/boundary/component/steer_point/options/triggers/
  bundle/authored_options` but **not** `segment_reentry_allowed` or
  `rerun_component` — the rerun/reentry affordances the boundary handler
  computed and offered (passed into `_handle_pause`, 1706-1707). A continuation
  rebuilding the parked pause from its `steering.pause` event cannot directly
  tell whether segment re-entry was on offer, nor which component the
  replacement-rerun targeted. These are *reconstructable indirectly*
  (`allow_segment_reentry=True` only at after-component boundaries, 905, and
  `False` on the one post-rewalk re-presentation, 3304 — detectable by an
  earlier `rerun_mode='additive'` decision at the same boundary; `rerun_component`
  is derivable from the point), but the indirection is exactly the "ambiguity
  handling named per field" the contract wants closed. **Minimal fix:** add
  `segment_reentry_allowed` and `rerun_component` to `_pause_payload` (JSONB,
  no schema change). Closes it outright.

- **G2 — `flagged_events` / `collation_render` reproduction is derivation, not
  read-back.** The exact collation surface is rebuilt by re-deriving
  retrying/retried/watch flags and their ordering from runs + events. There is
  no single durable "collation snapshot" — parity depends on the reducer
  reproducing list order and dict shape faithfully. Not a missing source (all
  inputs are durable); it is *reconstruction risk*. **Optional hardening
  (JSONB):** the run already ends with a `_finish_run`; for a **parked** run
  add a `run.parked` event carrying the accumulated `flagged_events` +
  `step_outcomes` snapshot as JSONB, so the continuation reads them back
  verbatim instead of re-deriving. Recommended — it collapses the two
  transform-heavy fields (9, 10) to a read and makes collation parity trivially
  testable. Still zero-schema.

Everything else (plan block, overlays, run maps, completed set, blocked set,
last check-in, most-recent-run) is fully reconstructable from existing durable
sources with no addition.

---

## 4. Reducer sketch

**Where it lives.** A pure module `runtime/continuation_state.py` (a peer of
`steering_history.py`, same read-only posture): given `(conn, project_id,
capability_run_id)` it returns a `_ContinuationState` carrying the 16 fields —
literally the argument bundle `run_plan` threads. `run_plan` gains a
`resume_from: _ContinuationState | None` param: `None` = today's fresh walk
(init 623-646 unchanged); non-`None` = seed the loop state from the reducer and
enter at the parked boundary. The boundary continuation walk = the same
`run_plan` body, no second engine.

**Ordering & idempotence rules.**
1. **One walk = one `capability_run_id`.** Every source read is scoped to it:
   `runs.capability_run_id`, and `steering_history`'s payload-key partition
   (`payload.capability_run_id`, steering_history.py:8-14) — never
   `event_log.run_id` (that is FK plumbing).
2. **Sequence is the only order.** Replay `steering.decision` (overlays,
   digest) and reconstruct flagged_events strictly by `event_log.sequence`
   (events.read orders by it, events.py:93). Never `occurred_at` (clock skew /
   ties — schema note 133).
3. **Latest-wins for run maps.** `successful_runs`/`attempted_runs` take the
   most-recent run per component; this is idempotent and reproduces
   reference-move + discretionary-pop without replaying pops.
4. **Overlay replay is a left-fold** of `_extend_overlays` over adjust-only
   decisions — the same function the live path uses, so drift is impossible by
   construction.
5. **Plan is version-max**, not event-replayed — the amendment rows *are* the
   log.
6. **Idempotent re-dispatch.** The startup drainer / atomic-claim path
   (contract findings 2+17) may build the reducer more than once; it is a pure
   read, so repeated construction yields identical state — safe under the
   crash-before-execute redispatch.

**How the parity test drives it.** Run a scripted walk to a known
after-component pause twice: (a) **unbroken** — answer in-process, let it
finish; (b) **parked-and-continued** — let it park (`status=paused`, thread
ends), then build `_ContinuationState` from the durable record alone and
dispatch the continuation with the identical answer. Assert byte-identical
composed context across the **full surface** named in the contract: pause
header (`_watch_header`), digest (`_watch_digest`), P2-P4 bundles
(`_build_bundle`), canonical + authored options, router surface
(`_router_pause_context`), downstream run references (`_reference_kwargs` over
`successful_runs`), `pending_overlays`, and `collation_render`. Field-level
assertions on the 16 fields catch drift before it reaches a surface. Any
quality-bearing value that the reducer cannot source — surfacing as a parity
diff that no JSONB addition closes — is the **stop-condition finding** the
contract names. None found in this as-built pass.

---

## Adversarial addendum (2026-07-21, plan-stage codex review — adjudicated by the lead)

The review **refuted the clean "16/16, no gap" verdict** on three fields;
adjudications binding C.1/C.2:

- **G3 — `attempted_runs` (finding 6):** replacement-rerun and segment
  re-entry paths never update the map (`runner.py:2791` signature carries no
  `attempted_runs`; `runner.py:3086` updates only its local id) while the
  ordinary loop does (`runner.py:856`). A latest-durable-attempt reducer
  would therefore *diverge from the as-built in-memory map* — and class-9
  discretion reads it. Adjudication: **unify the runner's mutation semantics**
  (rerun/segment paths update the map like the ordinary loop) — a named,
  plan-gate-approved runner-behaviour delta with regression tests exercising
  class-9 triggers after both paths.
- **G4 — `successful_runs` / `blocked_discretionary` (finding 7):** the
  annex's "latest succeeded run" rule retains an older success after a newer
  failed rerun, contradicting the as-built pop (`runner.py:2877`); rerun
  success does not clear an existing block (`runner.py:2867`). Adjudication:
  reducer rule = **latest overall attempt, included iff that attempt
  succeeded**; the stale-block semantics get a deliberate C.1 code-read
  adjudication (clear-on-success unless intent shows otherwise), pinned and
  named either way; parity cases: failed-then-successful rerun, segment
  re-entry.
- **G5 — overlay event shapes (finding 8):** confirmed free-text fan-out
  stores deltas under `compiled[].delta` (`steering.py:1061`, overridden at
  `runner.py:2154/2173`), not `interpreted_action.directive_deltas`. A
  literal replay of the annex's rule silently loses confirmed free-text
  overlays. Adjudication: the reducer folds **both** decision shapes,
  restricted to `kind == plan_adjustment`; parity case: free-text
  multi-fragment overlay.

The review confirmed G1/G2 as genuine and the watch header/digest purity
evidence as sound. Verdict after addendum: still **no stop-condition gap**
(every field has a durable source), but exact parity requires the G3/G4
semantic unifications above — reconstruction rules must mirror unified
semantics, not naive latest-status reads.
