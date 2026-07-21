# ADR 0025 — Parked pauses and boundary continuation

**Status:** Accepted — 2026-07-21 (owner; 025 plan gate, "Approved, close out the design phase"). Contract: `docs/tasks/025-web-app-foundation/contract.md`.
Annex: `docs/tasks/025-web-app-foundation/continuation-state-reducer.md`.

## Context

024's runner blocks its thread at every attended steering pause — correct
for the CLI (user present), wrong at product timescales: the delegation
postures are designed for users leaving for hours or days (owner challenge,
2026-07-21). Held threads clog capacity, and any restart destroyed a paused
run (re-run from scratch after a multi-day pause). The general resume engine
(mid-component checkpointing) remains deferred (017 seam).

## Decisions

1. **Attended pauses park.** The walk ends at the pause (thread released);
   `capability_run.status` gains `paused` (+ `interrupted`) via an approved
   check-constraint migration. The CLI keeps blocking behaviour behind the
   same seam, pin-tested byte-identical (`block` vs `park` disposition).
2. **Answers dispatch a boundary continuation walk.** Feasible without the
   resume engine because pauses occur only at component boundaries, where
   everything is already durable: per-component commits (017) + the steering
   record (024). The continuation-state reducer
   (`runtime/continuation_state.py`, read-only peer of `steering_history`)
   rebuilds the walk's carried state from `event_log` by sequence;
   `run_plan(resume_from=…)` re-enters at the recorded boundary. The annex
   verified all 16 walk-loop fields reconstructable; two payload gaps closed
   in-slice (`steering.pause` gains `segment_reentry_allowed` +
   `rerun_component`; a `run.parked` event snapshots step outcomes/flags).
3. **Continuation is durable before it is executable.** The answer and a
   `continuation.requested` event commit in one transaction under the
   per-project lock; a worker claims it atomically; a startup drainer
   redispatches unclaimed continuations (sweep interrupted walks first,
   then drain). A crash between answer and execution loses nothing.
4. **Honest interruption narrows to executing walks.** Parked runs survive
   restarts by construction; only mid-execution deaths mark `interrupted`
   (orphan sweep, idempotent). No walk is ever silently resumed
   mid-component.
5. **Context parity is a tested property.** A parity test asserts identical
   composed orchestrator context (header, digest, P2–P4 bundles, options,
   router surface, references, overlays, collation) between unbroken and
   parked-and-continued walks. Any quality-bearing state found living only
   in walk memory is a stop-condition finding, not something to serialize
   ad hoc.

## Consequences

- Multi-day pauses are first-class and free; deploys no longer destroy
  pending check-ins; the run bound counts executing walks only.
- Pre-026 the planner's draft conversation remains process-local (honest
  loss on restart); nothing execution-bearing depends on it (plan-as-
  contract). Plan-field↔turn provenance stays a deferred, acknowledged loss.
- Walk segments are queue-shaped: broker-backed workers can later slot in
  behind the continuation-dispatch seam without reshaping the walk.
- Revisit trigger: if segment-grain re-dispatch after mid-execution
  interruption is ever wanted (auto-retry from last boundary), it builds on
  this machinery — record demand via interrupted-run re-run frequency.
