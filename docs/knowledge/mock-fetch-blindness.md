---
type: Testing rule
title: Mock-mode end-to-end tests check the contract shape, not the wiring
description: Mock mode intercepts requests at fetch, so the Playwright journey cannot see transport, auth header, base address, error mapping or backend composition bugs. The real-HTTP smoke (make fe-api-smoke) covers that layer.
tags: [testing, frontend, e2e, mock]
generated:
  by: claude-opus/5.5
  at: 2026-11-20
sources:
  - id: mock-api
    resource: frontend/src/mock/api.ts
  - id: playwright-config
    resource: frontend/playwright.config.ts
  - id: fe-api-smoke
    resource: scripts/fe_api_smoke.sh
---

# Rule

- Mock mode (`VITE_MOCK=1`) answers requests at the `fetch` call (`frontend/src/mock/api.ts`).
  The Playwright journey therefore checks the user interface against the contract shape only.
  It cannot see transport, auth headers, the base address, HTTP error mapping or how the
  frontend builds a backend request.
- That layer is covered by the real-HTTP smoke, `make fe-api-smoke` (`scripts/fe_api_smoke.sh`):
  the built frontend against a real API with stub backends and its own database. It runs in CI.
  A change to transport, auth or request building needs that smoke, not only a green mock run.
- The Playwright web server uses its own port with `--strictPort`
  (`frontend/playwright.config.ts`), so a leftover dev server on another port cannot take over
  the run.
