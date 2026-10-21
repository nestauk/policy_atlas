---
type: Frontend rule
title: When walks run concurrently on one task, every stream frame and thread line carries its walk id
description: The SSE stream and the decision thread are per task, not per walk. Once a longlist walk ran four option searches beside it, stage frames with no walk id painted the children's stages on the parent's timeline, a late child run.finished replaced the tracked walk, and parent lines were filed into child windows by time. As built, stage frames and DecisionOut carry capability_run_id, the reducer drops other walks' frames and remembers child ids, and a walk's kind comes from its own purpose.
tags: [frontend, sse, reducer, child-walks, thread, task-045]
timestamp: 2026-09-24
---

# Rule

Anything a UI groups by walk must carry the walk's id on the wire, never be placed by time or by
"the walk I am tracking":

- **Stage frames** (`stage.started/completed/failed`) carry `capability_run_id` (additive,
  `null` when the event names no component run). The reducer ignores a stage frame whose id is not
  the tracked run (`isOtherRunsStage`).
- **Run frames**: a `run.status` for a run already seen as a child is recorded (`childRunIds`) and
  never becomes `state.run` — a child finishing late cannot replace a terminal parent.
- **Thread lines**: `DecisionOut.capability_run_id` (or a decision's `detail.capability_run_id`)
  places a line on its walk; only an untagged line is placed by time, and only among parentless
  walks (children are hidden in the thread).
- **Walk kind** (the run-card words) comes from the run's own `purpose` (`targeted` →
  `option_search`), never from the live stream's stages — historical blocks otherwise take the
  current walk's stages.

# Why

One slice, five findings of the same shape (045 review stack A3, A7, A8, A9, F11 + g4): each
surface assumed one active walk per task, which held until child walks. Parentless add searches
(verb *add*) made it worse — with no parent id they read as a baseline.

# Watch out

- A new per-task stream consumer inherits the same assumption; ask "which walk?" of every frame it
  folds. [stream-fed-state-needs-ownership-gates](stream-fed-state-needs-ownership-gates.md) is the
  same "stream state is blind to a dimension" family, for viewers instead of walks.
- A new SSE frame field regenerates the union; see
  [generated-sse-union-reducer-cases](generated-sse-union-reducer-cases.md).

# Citations

- `backend/src/policy_atlas/api/contract/sse.py` (`_StageFrameBase.capability_run_id`), `api/routers/sse.py` (`_frames_for_row`)
- `backend/src/policy_atlas/api/contract/read_models.py` (`DecisionOut.capability_run_id`)
- `frontend/src/store/reducer.ts` (`isOtherRunsStage`, `childRunIds`); `frontend/src/views/workspace/runProgress.ts` (walk kind from purpose); `frontend/src/views/workspace/TaskAgentPane.tsx` (`threadInputs`)
- [045 verification.md](../tasks/045-scoping-longlist/verification.md) § Review findings (A3, A7–A9, F11)
