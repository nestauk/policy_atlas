---
type: Runbook
title: Live-check drives — environment and product facts that cost debugging time
description: Kill the dev API by PORT with LISTEN scope (uvicorn --reload's worker never has "uvicorn" in argv; SIGTERM drains SSE for minutes; unscoped lsof kills the test's own sockets); the dev DB is NOT migrated by make test — run alembic upgrade head before any live check on a schema slice; Playwright specs here are ESM (fileURLToPath shim for __dirname); an unattended plan takes ~6 approvals; findings rows need deep analysis depth.
tags: [live-check, uvicorn, playwright, alembic, dev-environment]
timestamp: 2026-07-29
---

# Rules

- **Killing the dev API for crash legs**: kill by port with LISTEN scope —
  `lsof -ti tcp:8000 -sTCP:LISTEN | xargs kill -9`. `uvicorn --reload`'s worker
  is a multiprocessing-spawn child whose argv never contains "uvicorn" (a
  name-based pkill orphans the serving process); graceful SIGTERM drains the
  browser's open SSE connection holding LISTEN for minutes; an unscoped lsof
  also matches the browser/Vite CLIENT sockets and kills the test itself.
  After a kill, confirm the API answers 0 **and** the port is free before
  respawning — the socket outlives the process (EADDRINUSE otherwise).
- **The dev database is NOT migrated by `make test`** (that owns the test DB).
  A schema slice must run `alembic upgrade head` against dev before any live
  check — 027's drive tripped on this.
- **Playwright specs in this repo are ESM** — `__dirname` needs the
  `fileURLToPath(import.meta.url)` shim.
- **An unattended plan is not one turn**: the planner walks one standing
  instruction per steer point before honestly marking ready (~6 approvals in
  027 part B) — scripted drives need a generous turn budget.
- **The planner pins structured extraction to deep analysis depth** — a
  standard-depth run has no extract stage and therefore no findings rows; live
  checks that need findings must ask for deep depth.
- **Playwright strict mode collides with brand copy** (028): `getByText("ready")`
  matches prose containing "ready" — pin chips/labels with `{ exact: true }`
  from the first draft of an acceptance spec.
- **The mock e2e suite and a live Playwright leg cannot share one laptop** —
  the load makes mock `page.goto` time out; serialise them (028 G.2).
- **live-028's restart helper only kills what it spawned** (028 review C2):
  the leg-B FIRST restart targets the `make dev`-started API and requires
  `LIVE_ALLOW_API_TAKEOVER=1`; it verifies every port-8000 listener is a
  policy-atlas uvicorn before killing, and refuses otherwise.

# Why

Each line burned real time in the 027 G.1 drive (2026-07-29); none is
discoverable from the code without already knowing where to look.
