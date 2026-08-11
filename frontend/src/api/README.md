# API layer

`client.ts` exports `createApiClient()` (unauthenticated) and
`createAuthedApiClient(auth)` — both typed `openapi-fetch` clients bound to
the generated `paths` type in `gen/types.ts`. Base URL comes from
`VITE_API_BASE_URL`, defaulting to `/api` (the local dev proxy).

The generated client is schema-first: `gen/types.ts` and the committed
`../../openapi.json` are produced from the backend's Pydantic contract
(`policy_atlas.api.contract`) by `make openapi-sync` at the repo root.
`make drift-check` fails the build if either goes stale — never hand-edit
`gen/`.

- `authMiddleware.ts` — the `openapi-fetch` middleware `createAuthedApiClient`
  installs: injects `Authorization: Bearer <token>` from the active
  `AuthApi`, and on a 401 attempts exactly one silent refresh + retry
  before surfacing the response.
- `sseFrame.ts` — `SseFrame` (re-exported from the generated contract) and
  `narrowSseFrame`, the one runtime-narrow seam in the SSE pipeline
  (verifies `.type` against the pinned frame-type set; trusts the rest of
  the shape from the contract).
- `sse.ts` — `connectEventStream()`, the fetch-stream SSE client:
  bearer-header auth (never a query-string token), `cursor=` reconnects,
  exponential backoff with jitter (1s–30s), and a single
  refresh-then-retry on a 401 before surfacing `onUnauthenticated`.
- `queries.ts` — TanStack Query hooks over the authed client:
  `useProjects`, `useProject`, `useCheckIns`, plus the read-model hooks
  named in task 025 §6 (`useFunnel`, `useLandscape`, `useEvidence`,
  `useFindings`, `useDecisions`, `useArtefact`) and the task-027 durable
  transcript/run reads (`usePlanningTurns`, `useRuns`). `groups`/`coverage`
  are in the generated contract too but aren't named in the task brief's
  hook list — add a hook for either once a view needs it.
