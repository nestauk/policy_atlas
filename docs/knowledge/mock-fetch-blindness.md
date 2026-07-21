---
type: Testing rule
title: Mock-mode e2e tests validate contract shape, not wiring
description: Mock mode intercepts at fetch, so the Playwright journey structurally cannot see transport/auth/base-URL/error-mapping/backend-composition bugs — all five 025 live-check integration bugs were in exactly that layer. Playwright's reuseExistingServer can also silently absorb the e2e run into whatever process already holds the port.
tags: [testing, frontend, e2e, mock, live-check, coverage-class]
timestamp: 2026-07-21
---

# Rule

Mock mode (`VITE_MOCK=1`) intercepts HTTP at the `fetch` call (`mockFetch` in
`src/mock/api.ts`, wired into the generated openapi-fetch client), so the
Playwright journey validates UI logic against the **contract shape** —
request/response schemas, state transitions, rendering — but is structurally
blind to anything below that seam: transport, auth headers, base-URL
construction, HTTP error-code mapping, and how the frontend actually composes a
backend request. All five 025 live-check integration bugs (stub-vs-live backend
wiring, `.env` not loading, a doubled `/api` prefix in the client base URL, a
dict-vs-row argument crossing an API boundary, a missing SSE frame mapping) were
in exactly that layer — none reachable from mock or unit tests, all found within
minutes of a real backend.

# Why

The drift gate (contract tests + generated types) guarantees shape parity
between frontend and backend; it says nothing about wiring, because mock mode
never constructs a real request in the first place.

**Operational corollary:** Playwright's `webServer.reuseExistingServer` (true
outside CI) silently reuses whatever process already holds the configured
port. A leftover non-mock dev server from an earlier live-check session made
all 4 e2e specs fail mysteriously — a wrong-mode server, not a real regression.
Treat unexplained full-suite e2e failures as "check what's listening on the
port" before "check the test."

# Watch out

The compensating control is recorded, not built: a thin real-HTTP smoke (real
HTTP + dev-issuer auth + SSE against stub backends) is deferred to the infra
slice (`docs/deferred.md`, "Automated FE↔real-API smoke"). Until it lands, any
change to backend composition, transport, or auth needs a live check, not just
a green mock-mode e2e run.

# Citations

- `frontend/src/mock/api.ts`
- `frontend/playwright.config.ts` (`webServer.reuseExistingServer`)
- `docs/deferred.md` § Automated FE↔real-API smoke
- `docs/tasks/025-web-app-foundation/verification.md` (five integration
  findings)
