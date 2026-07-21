# C.1 — Runner parking + continuation seam design (lead brief for C.2/C.3/C.4)

Binds the [continuation-state reducer annex](continuation-state-reducer.md)
**including its adversarial addendum** (G1–G5). Line anchors are
`backend/src/policy_atlas/runtime/runner.py` as of phase-A commit `7a5fc78`.

## 1. Pause disposition: `block` vs `park`

The disposition lives in the IO seam, not the runner: `io.pause(...)` either
returns a `SteeringResponse` (blocking — CLI, byte-identical today) or raises
the new control-flow exception **`WalkParked`** (API IO). No flag threading:
the raise unwinds from `_pause_response` (inside `_handle_pause`, 1737-1738)
through the boundary handler to `run_plan`'s loop, which catches it at one
place.

```python
class WalkParked(Exception):
    """Raised by a park-disposition IO at an attended pause: the walk thread
    ends; the durable record carries the pause; an answer dispatches a
    boundary continuation walk."""
```

On catch, `run_plan` performs the **park bookkeeping in one transaction**:
- `capability_run.status = 'paused'` (`ended_at` stays NULL — the walk is
  not ended, it is parked).
- Append a **`run.parked` event** (G2 hardening, annex §3): payload =
  `{capability_run_id, flagged_events: [...], step_outcomes: [...]}` — the
  two transform-heavy fields snapshotted verbatim so the reducer reads them
  back instead of re-deriving. `step_outcomes` serialised as plain dicts
  (uuid→str, StepStatus→str); the reducer deserialises symmetrically.
  `run_id` = the parked pause's own attachment run id (annex field 16
  identity; non-None by the 024 invariant — no pause exists before the
  first run).
- Return `RunPlanOutcome(status="paused", steps=…, flagged_events=…,
  collation_render="")` — `RunPlanStatus` gains `"paused"` (runner-level
  literal; the DB constraint is widened by migration 2).

Timing note: `steering.pause` is emitted BEFORE `io.pause` is called
(1729-1735), so the parked pause is already durable when `WalkParked`
unwinds — the park transaction only flips status + snapshots.

**G1 (annex §3):** `_pause_payload` (2409) gains `segment_reentry_allowed`
and `rerun_component` keys, always present. Closes the affordance-
reconstruction ambiguity; the API's answer validation reads them off the
durable pause event (fail-closed mirror of 1793).

## 2. Continuation entry: `run_plan(resume_from=…)`

`runtime/continuation_state.py` (C.2, read-only peer of
`steering_history.py`) exposes:

```python
@dataclass(frozen=True)
class ContinuationState:  # the 16 annex fields + session_id
    ...
def build(engine, *, project_id, capability_run_id) -> ContinuationState
```

`run_plan` gains `resume_from: ContinuationState | None = None` and
`resume_decision: ResumeDecision | None = None`:

- `resume_from=None`: today's path, unchanged (init 623-646, fresh
  `_open_capability_run`).
- `resume_from` set: **no** `_open_capability_run` — the continuation IS the
  same `capability_run_id` (the claim already flipped `paused → running`,
  §4); the loop state (fields 1-16) seeds from the reducer;
  `remaining_steps = _remaining_steps(chain, completed_components)`.

`ResumeDecision` is the durable answer, applied WITHOUT re-presenting the
pause (no duplicate `steering.pause`, no re-render — parity surfaces are
asserted by the harness separately):

| answer (durable `steering.decision`) | continuation behaviour |
|---|---|
| `continue` | seed state, enter the while loop directly |
| `adjust` / `mode_change` | **applied at answer time** (API layer runs the same `_apply_adjustment` persistence path: new plan row + decision event in the answer transaction). The reducer already reads the amended plan (version-max) + overlays (decision replay) — continuation enters the loop with nothing extra to do |
| `rerun_mode='replacement'` | enter via the loop's existing rerun plumbing (687-703): execute `_run_component_rerun` for the pinned component, then fall through |
| `rerun_mode='additive'` | enter via segment-reentry plumbing (704+): `_apply_segment_reentry` re-walk, then re-present the boundary once — under a park IO the re-presentation **parks again** (a fresh pending check-in; as-built one-cycle rule preserved, 3304) |
| `abort` | no continuation at all — the answer transaction flips the run `aborted` (API layer); nothing to execute |

Free-text answers are compiled + confirmed at answer time (the API's
router confirm gate); what persists is an ordinary confirmed
adjust/fan-out decision — the continuation never sees raw prose.

The before-component re-fire (annex field 15 note): seeding
`last_check_in_payload` non-None re-fires the next before-component
boundary exactly as an unbroken walk would — inherited re-presentation
seam, not widened; do not special-case it.

## 3. Runner-behaviour deltas (plan-gate approved, regression-tested)

- **G3 — `attempted_runs` unification:** `_run_component_rerun` (2791) and
  the segment re-walk (3088-3131) gain `attempted_runs` threading and update
  it per final attempt exactly as the ordinary loop does (859 semantics:
  keyed by `registry_component_for(...)`, includes failed). Regression
  tests: class-9 discretion triggers fire after (a) a failed rerun,
  (b) a failed segment re-walk.
- **G4 — clear-on-success (adjudicated from the code):** as-built, rerun
  success threads `successful_runs[component]` (2868) and segment re-walk
  success likewise (3133), but neither clears a stale
  `blocked_discretionary[component]` left by an earlier failure — while the
  failure paths set it (2880/3189). No read shows intent: the only consumer
  is `_skip_reason` (4410), which would skip downstream dependents whose
  requirement now demonstrably holds (`successful_runs` has it) —
  inconsistent state, not design. **Adjudication: on success, both paths
  `blocked_discretionary.pop(component, None)`.** Reducer rule mirrors it:
  a component is blocked iff its **latest overall attempt** failed/skipped;
  in `successful_runs` iff that latest attempt succeeded. Parity cases:
  failed-then-successful rerun; segment re-entry after failure.
- **G5 — overlay reducer folds both decision shapes**: `interpreted_action.
  directive_deltas` AND fan-out `compiled[].delta`, restricted to
  `kind == plan_adjustment`, `rerun_mode is None`,
  `response ∈ {adjust, mode_change}`, in `event_log.sequence` order via the
  live path's own `_extend_overlays` (left-fold; drift impossible by
  construction). Parity case: free-text multi-fragment overlay.

## 4. Continuation protocol (C.3)

- **Durable before executable:** the answer endpoint commits, in ONE
  transaction: the `steering.decision` event (+ plan-row for adjust) + a
  **`continuation.requested`** event (payload: `capability_run_id`,
  `decision_event_id`, `requested_at`) — attached to the same run id as the
  pause.
- **Atomic claim:** a worker takes the per-project serialization primitive
  (`SELECT … FOR UPDATE` on the `project` row — the same helper guarding
  run dispatch and answers, plan pin 3), re-checks the run is `paused` with
  an unclaimed continuation, appends `continuation.claimed`, flips
  `capability_run.status = 'running'`, commits, THEN dispatches the
  continuation walk on the offload executor. Claimed = a
  `continuation.claimed` event exists for that `continuation.requested`.
- **Startup order: orphan sweep, then drainer** (both in the API lifespan,
  idempotent, per-process):
  1. **Orphan sweep:** every `capability_run` in `status='running'` is a
     walk that died mid-execution (one-instance posture) → mark
     `interrupted`, `ended_at=now()`, append `run.interrupted`. Parked runs
     (`paused`) are untouched — they survive by construction. Idempotent:
     double boot appends nothing the second time (no `running` rows left).
  2. **Drainer:** every `continuation.requested` without a matching
     `continuation.claimed` → claim + dispatch (same claim path). Covers a
     crash between answer and claim. A crash after claim but before/mid
     execution leaves the run `running` → next boot's orphan sweep marks it
     `interrupted` honestly (mid-component death is interruption, never
     resumed — 017 seam).
- **Crash tests (both claim sides):** (a) answer committed, process dies
  before claim → restart → drainer dispatches → continuation completes;
  (b) claim committed, process dies before execution → restart → orphan
  sweep marks interrupted, drainer does NOT re-dispatch (claimed), UI shows
  honest interruption.
- **Barrier test (finding 5):** two simultaneous answer POSTs → exactly one
  decision + one 409 + at most one continuation (the per-project lock
  serialises; prove with a threading barrier).

## 5. Parity harness (C.2, drives the reducer)

Per annex §4: scripted walk to a known after-component pause, (a) unbroken
(blocking IO answers in-process) vs (b) parked-and-continued (park IO +
reducer + `resume_from`), identical answer. Assert byte-identical composed
context across the full pinned surface: pause header, digest, P2–P4
bundles, canonical + authored options, router surface, downstream run
references (`_reference_kwargs` over `successful_runs`), `pending_overlays`,
`collation_render` — plus field-level equality on all 16 fields. Cases:
continue; adjust; failed-then-successful rerun (G4); segment re-entry (G3);
free-text multi-fragment overlay (G5). Any quality-bearing value the
reducer cannot source = **stop-condition finding** — report, do not patch
around.

## 6. CLI pins + hash guard (C.4)

- **CLI blocking path byte-identical:** pin tests asserting the blocking
  IO's pause/render behaviour is unchanged (same rendered pause text, same
  response handling) — the park disposition must be invisible to the CLI.
- **Prompt-family content-hash guard** (plan pin 11/12): script hashing the
  prompt-bearing modules (the `*_prompt.py` family + orchestrator/planner
  prompts); wired into `make verify`; the committed hash list changes only
  with an explicit, named prompt change. 025 must show NO prompt drift.
- **Thread-safety audit checklist** (§7) executed as C.4's test.

## 7. Thread-safety audit checklist (C.4 brief — contract concurrent-users pin)

Components were built one-walk-at-a-time; the API introduces concurrent
walks (different projects). Audit for module-global mutable state and
cross-run leakage:

1. `grep` sweep: module-level mutable assignments (dicts/lists/caches),
   `functools.lru_cache` on functions taking run-scoped args,
   `os.environ` mutation, monkeypatching (the demo's pattern is banned),
   class attributes used as shared state — across
   `policy_atlas/{core,evidence_base,runtime}`.
2. Named suspects to clear explicitly: `core/openai_client.py` (shared
   client — must be thread-safe per SDK docs), `core/tracing.py` (Langfuse
   context — per-run session ids must be parameter-passed, never global),
   `core/db.py` (engine is process-singleton by design — fine),
   `core/embeddings.py` cache scope, `search_live.py` HTTP client reuse.
3. Per-run config is parameter-passed everywhere (assert no
   read-from-global of directive/plan state).
4. **The both-complete test:** two concurrent stub walks on two projects
   (threads), assert both complete successfully, event logs are fully
   project-scoped (no cross-project rows), read models isolated, and the
   per-project sequence counters never collide (the single-writer-per-
   project invariant holds because the lock is per-project).

Findings that are real shared-mutable-state bugs: fix if mechanical
(parameter-pass), else report as stop-condition (runner behaviour change
beyond the approved deltas).
