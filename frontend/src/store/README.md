# Store

Client-side, event-sourced state over the SSE frame stream (task 025 §4) —
no framework, a plain reducer:

- `types.ts` — `RunStreamState` and its pieces, including presentation-only
  `liveSections` keyed by artefact display index.
- `reducer.ts` — `reduceRunStreamFrame(state, frame)`, pure and
  replay-idempotent: frames below `lastSequence`, or a repeated frame type
  at the current sequence, are dropped. This permits the intentional
  `checkin.resolved` + `plan.updated` same-sequence pair while making a
  replay safe. `artefact.*` frames build the live, non-authoritative section
  outline; empty completed prose removes that slot rather than faking it.
  `tick` frames are the one exception — no `sequence`, they only update the
  transient `liveness` slice.
- `useRunStream.ts` — the React binding: opens `src/api/sse.ts`'s
  connection for one project, folds every frame through the reducer, and
  invalidates the project's read-model queries on `stage.completed` /
  `run.status`.

See `src/store/reducer.test.ts` for the replay-idempotence, pending→resolved,
and tick-transience proofs. `transcript.ts` owns the durable planning-turn
query's local optimistic composer state; `thread.ts` is the pure,
run-phase-anchored planning-thread composition model.
