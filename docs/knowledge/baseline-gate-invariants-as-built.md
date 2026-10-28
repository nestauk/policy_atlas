---
type: Invariant
title: The baseline gate pauses only over a written baseline, is never passed by a silent Continue, and offers exactly its two options
description: Task 044's `baseline_confirm` steer point as the review stack pinned it — the gate degrades to a generic pause when synthesise failed; a non-pausing IO (NullIO, the CLI) records a flagged standing-default decision instead of fabricating a user Continue; an unattended plan may only declare `proceed_flag` for it; the check-in transaction refuses the universal `abort`/`continue` floor at the gate; and "a baseline exists" means the walk wrote an artefact, never a status guess.
tags: [options-scoping, steering, baseline-gate, runner, invariant, task-044]
timestamp: 2026-09-17
---

# Rule

The scoping gate (`runtime/scoping_plan.py::BASELINE_CONFIRM`, `PausePoint("after_component",
"synthesise")`) is structural: a plan nobody confirmed is the failure the slice exists to
prevent. Five properties hold, each with a test:

- **No card over nothing.** When synthesise left no successful run, the boundary degrades the
  steer point to `None` and pauses generically — the same rule `DEEPENING_SELECTION` and
  `FINDING_GROUPS` already had (`runner.py::_handle_after_component_boundary`). A confirm card
  over a failed baseline would record a plan confirmation against a baseline that never existed.
- **A pause the IO cannot present is recorded, not skipped.** `_pause_response` returns
  `Continue()` for any IO without `pause` (the runner's default `NullIO`, the CLI). At the gate
  that is routed to the unattended recording instead: a `steering.decision` with
  `decided_by="standing_default"` and the auto-resolved flag on the collation, so the end-of-run
  review says nobody confirmed. Every other steer point keeps its Continue.
- **Unattended never stops at the gate.** `ScopingSteerPointDefault.action` admits `proceed_flag`
  only; the unattended walk records, flags and continues (D11, A9).
- **Two options, no floor.** `continuation.answer_check_in` accepts the universal `continue` /
  `abort` ids at every pause; at the gate it refuses them and any option outside the stored two,
  because the generic `abort` marks the plan `abandoned` while "Change the plan" keeps it
  `approved` and editable.
- **A baseline exists iff the walk wrote an artefact.** `RunOut.artefact_id` (a scalar subquery on
  `artefact.capability_run_id`) is what the Task Agent's "a baseline exists" line, the plan
  document's start states and the Result band read; an `aborted` walk is not a baseline unless it
  carries one (a walk aborted at a floor pause after acquire has none; one aborted at the gate has).

# Why

Each rule closes a hole the 044 review stack found on a green build: the failed-synthesise card
(`/code-review`), the NullIO pass (Codex, the one blocker), `stop` under unattended (Codex), the
`abort` bypass (Codex), and the status-guess baseline (`/code-review`, two findings — the backend
sentence and the frontend Confirm posting the task's latest artefact against a rebuild that
aborted before writing). None was visible in the live check, which drove the API path with
`ParkIO` and never failed synthesise.

# Watch out

- `stage_vocabulary` maps `baseline_confirm` onto stage `synthesise` — there is no `StageKey`
  for the gate; a new gate in task 2 ("Assess these N") should follow the same shape.
- The gate's card is the pause render (`render_baseline_gate(bundle)`), not the component line;
  a stub artefact without a "Key assumption" block renders `KEY_ASSUMPTION_ABSENT`, not nothing.
- Related: [plan-lineage-by-fencing-not-custody](plan-lineage-by-fencing-not-custody.md),
  [confirm-gate-renders-compiled-action](confirm-gate-renders-compiled-action.md).

# Citations

- [ADR 0037](../adr/0037-options-scoping-task-kind-links-and-baseline-gate.md) § Decisions 5–7
- `backend/src/policy_atlas/runtime/runner.py` (`_handle_after_component_boundary`, `_pause_response`, `_resolve_baseline_gate_unattended`), `runtime/scoping_plan.py`, `api/continuation.py::answer_check_in`, `api/routers/_common.py::run_artefact_id_column`
- `backend/tests/runtime/test_baseline_gate.py`, `backend/tests/api/test_baseline_gate_checkin.py`, `frontend/src/views/workspace/planStart.test.ts`
- [044 verification.md](../tasks/044-scoping-shell-baseline/verification.md) § Review findings
