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
  The ephemeral frames are the exception (see below).
- `useRunStream.tsx` — `RunStreamProvider` owns one SSE connection per open
  task (mounted from `AppShell`); `useRunStream(taskId)` reads that
  shared reducer state. Read-model invalidations on `stage.completed` /
  `run.status` are trailing-debounced so a cold full-history replay does
  not storm refetches. Leaf tabs (Plan / Results / Sources) must not open
  their own connections. Invalidation rules: the tracked run's
  `stage.completed` / `run.status` refresh every query under the task; a
  child walk's (an option search's) refresh the options query only; an
  `ingest` tick refreshes the Sources list and the Landscape at most once
  per 5 s; no other tick refreshes anything.
- `../api/sse.ts` drops a connection that sends no bytes for 45 s (the
  server's keep-alives and heartbeats are far more frequent) and reconnects
  at its cursor, so the reconnecting banner shows.

**Ephemeral slices (task 058).** Three frame types carry no `sequence`, are
never replayed and never advance `lastSequence`: `tick` (the latest activity
per stage, in `liveness`), `artefact.section_delta` (a section's streamed
`draft`, appended or replaced) and `artefact.section_revising` (the spans of
that draft being revised). A delta for a section with no skeleton yet waits
in `pendingDrafts` until the skeleton arrives. `artefact.section_completed`
is the record: it sets `prose` and clears `draft` and `revising`, so a replay,
which carries no deltas, rebuilds `prose` alone. A new run clears all three
slices.

See `src/store/reducer.test.ts` for the replay-idempotence, pending→resolved,
and tick-transience proofs. `transcript.ts` owns the durable task_agent-turn
query's local optimistic composer state; `thread.ts` is the pure,
run-phase-anchored task_agent-thread composition model.
