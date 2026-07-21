# Store

Client-side, event-sourced state over the SSE frame stream (task 025 §4) —
no framework, a plain reducer:

- `types.ts` — `RunStreamState` and its pieces (pinned shape).
- `reducer.ts` — `reduceRunStreamFrame(state, frame)`, pure and
  replay-idempotent: frames with `sequence <= state.lastSequence` are
  dropped, so folding the same stream twice (or resuming from any
  mid-stream cursor) yields the same final state. `tick` frames are the
  one exception — no `sequence`, they only update the transient
  `liveness` slice.
- `useRunStream.ts` — the React binding: opens `src/api/sse.ts`'s
  connection for one project, folds every frame through the reducer, and
  invalidates the project's read-model queries on `stage.completed` /
  `run.status`.

See `src/store/reducer.test.ts` for the replay-idempotence, pending→resolved,
and tick-transience proofs.
