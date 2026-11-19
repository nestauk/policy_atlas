# API layer

The code that talks to the backend web API.

## What is in it

- `client.ts`: `createAuthedApiClient(auth)`, a typed `openapi-fetch` client built on the
  generated `paths` type in `gen/types.ts`. The base address comes from `VITE_API_BASE_URL`;
  the default is `/api` (the dev-server proxy).
- `authMiddleware.ts`: adds `Authorization: Bearer <token>` from the active `AuthApi`. On a 401
  (not signed in) response it refreshes the token once, silently, and tries again. A request
  sent with no token (a public link) is not retried.
- `sse.ts`: `connectEventStream()`, the client for a Task's event stream (SSE, server-sent
  events). It sends the token in a header, never in the address. It reconnects at its cursor
  with a back-off of 1 to 30 seconds, drops a connection that is silent for 45 seconds, and
  calls `onUnauthenticated` if a 401 stays after one refresh.
- `sseFrame.ts`: `SseFrame` and `narrowSseFrame`. It drops a frame whose `type` is not in the
  known list.
- `queries.ts`: `queryKeys` and the TanStack Query read hooks (`useTasks`, `useTask`,
  `useArtefact`, `useEvidence`, `useOptions`, `useToc` and the others).
- `mutations.ts`: the write hooks (create and update Tasks and Projects, start a run, answer a
  check-in, the Options scoping and Theory of change actions).
- `gen/`: generated types. Do not edit ([README](gen/README.md)). `gen/types-ops.ts` is for the
  ops pages, whose client is `src/ops/api.ts`. That client uses `authMiddleware.ts` too.

## Rules

- The types come from the backend's request and response models
  (`policy_atlas.api.contract`). After a backend contract change, run `make openapi-sync` from
  the root. `make drift-check` fails if `frontend/openapi.json`, `frontend/openapi-ops.json`,
  `gen/types.ts` or `gen/types-ops.ts` is out of date.
- Use `queryKeys` for every query key, so the event-stream refreshes find the right queries.

## Commands

From `frontend/`: `pnpm test` runs the unit tests. `pnpm gen` remakes `gen/types.ts` from
`openapi.json`, and `pnpm gen:ops` remakes `gen/types-ops.ts` from `openapi-ops.json`.
