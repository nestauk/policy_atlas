# Store

The client-side state that the web app builds from the server's event stream (SSE, server-sent
events), and the state of the chat transcripts. It uses no state library: the run state is a
plain reducer.

## What is in it

- `types.ts`: `RunStreamState` and its parts, and `createInitialRunStreamState`.
- `reducer.ts`: `reduceRunStreamFrame(state, frame)`. It is pure and safe to replay. A frame
  with a `sequence` below `lastSequence` is dropped. A second frame of the same type at the
  current sequence is dropped too, so two different frame types from one event both apply.
  Some frame types are ephemeral (for example `tick` and `artefact.section_delta`): they carry
  no `sequence`, are never replayed, and change only live display state. A replay therefore
  rebuilds only the durable state. The comment at the top of `reducer.ts` lists every
  ephemeral frame type and what it changes.
- `useRunStream.tsx`: `RunStreamProvider` opens one event-stream connection per open Task. It
  is mounted in `views/AppShell.tsx`. `useRunStream(taskId)` reads its state. It refreshes the
  server queries as frames arrive:
  - `stage.completed` or `run.status` of the tracked run: every query of the Task;
  - the same frames from an option search (a child walk): the options query only;
  - an `ingest` tick: the Sources list and the Landscape, at most once every 5 seconds.
  The first two are grouped in one 300 ms window, so a full replay does not cause a storm of
  refreshes.
- `transcript.ts`: the Task Agent transcript, with the local rows that show before the server
  returns them.
- `thread.ts`: puts the Task Agent turns, the runs and the steering decisions into one thread.
- `conversations.ts`: the other chats, their streamed replies and the composer draft.
- `planEdits.ts`: the unsaved edits to an Evidence search plan, kept per Task while the page
  is open.
- `index.ts`: the public exports. Import from `store`, not from the files.

## Rules

- A view must not open its own event-stream connection. It reads `useRunStream`.
- Keep the reducer pure. `reducer.test.ts` proves that a replay gives the same state.
- `../api/sse.ts` drops a connection that sends nothing for 45 seconds and reconnects from its
  cursor.

## Commands

From `frontend/`: `pnpm test` runs the unit tests, which include this folder's `*.test.ts`
files.
