# API layer

`client.ts` exports `createApiClient()`, a typed `openapi-fetch` client
factory bound to the generated `paths` type in `gen/types.ts`. Base URL
comes from `VITE_API_BASE_URL`, defaulting to `/api` (the local dev proxy).

The generated client is schema-first: `gen/types.ts` and the committed
`../../openapi.json` are produced from the backend's Pydantic contract
(`policy_atlas.api.contract`) by `make openapi-sync` at the repo root.
`make drift-check` fails the build if either goes stale — never hand-edit
`gen/`.

Typed hooks over `createApiClient()` (React Query, per task 025 §6) land
here in a later phase.
