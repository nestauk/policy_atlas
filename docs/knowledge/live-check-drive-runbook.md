---
type: Runbook
title: Live-check drives — environment and product facts that cost debugging time
description: Kill the dev API by PORT with LISTEN scope (uvicorn --reload's worker never has "uvicorn" in argv; SIGTERM drains SSE for minutes; unscoped lsof kills the test's own sockets); the dev DB is NOT migrated by make test — run alembic upgrade head before any live check on a schema slice; Playwright specs here are ESM (fileURLToPath shim for __dirname); an unattended plan takes ~6 approvals; findings rows need deep analysis depth.
tags: [live-check, uvicorn, playwright, alembic, dev-environment]
timestamp: 2026-10-21
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
- **Any throwaway driver that calls `run_plan` sits under `if __name__ == "__main__":`.**
  Full-text ingest starts spawn-mode worker processes, and on macOS a spawned worker
  re-imports the launching file; an unguarded driver re-runs itself inside the worker
  (a second task appears in the log, and the first run fails with "start a new
  process before the current process has finished its bootstrapping phase"). Task 014
  met this first; 053's live check 3 lost its one budgeted run to it because the lesson
  lived only in a verification note. The guarded re-run completed in 548 s.
- **The dev database is NOT migrated by `make test`** (that owns the test DB).
  A schema slice must run `alembic upgrade head` against dev before any live
  check — 027's drive tripped on this.
- **Playwright specs in this repo are ESM** — `__dirname` needs the
  `fileURLToPath(import.meta.url)` shim.
- **An unattended plan is not one turn**: the Task Agent walks one standing
  instruction per steer point before honestly marking ready (~6 approvals in
  027 part B) — scripted drives need a generous turn budget.
- **The Task Agent pins structured extraction to deep analysis depth** — a
  standard-depth run has no extract stage and therefore no findings rows; live
  checks that need findings must ask for deep depth.
- **Playwright strict mode collides with brand copy** (028): `getByText("ready")`
  matches prose containing "ready" — pin chips/labels with `{ exact: true }`
  from the first draft of an acceptance spec.
- **The mock e2e suite and a live Playwright leg cannot share one laptop** —
  the load makes mock `page.goto` time out; serialise them (028 G.2).
- **The chat's dev token must be minted for the subject that owns the task**
  (045): `make dev` signs in as `dev-user`; a token minted for any other `sub`
  gets 403 on every write route of a `dev-user` task.
- **live-028's restart helper only kills what it spawned** (028 review C2):
  the leg-B FIRST restart targets the `make dev`-started API and requires
  `LIVE_ALLOW_API_TAKEOVER=1`; it verifies every port-8000 listener is a
  policy-atlas uvicorn before killing, and refuses otherwise.
- **An options-scoping walk's first `paused` is a steering check-in, not the
  baseline gate** (053 live check 4): the run pauses after appraise with
  `kind = check_in`; a driver must read `/check-ins` and wait for
  `kind = baseline_confirm` before confirming. The confirm decision at that steer
  point opens the longlist walk itself, so `POST /plan/confirm-baseline` afterwards
  is refused with `409 run_active`; use one entry point or the other, not both.
- **Reading traces on a Langfuse v3 host** (053 delta review): `langfuse-cli` refuses
  the deprecated `trace list` and the v2 observations endpoint answers "v4 write mode
  only", so call the REST API directly (`GET /api/public/traces?fromTimestamp=…&toTimestamp=…`
  with basic auth, then `GET /api/public/traces/{id}` for the observations). Filter
  by `sessionId` (the task id): a peer session's run on another route can share the
  time window, and its models and errors are not yours.

# Why

Each line burned real time in the 027 G.1 drive (2026-07-29); none is
discoverable from the code without already knowing where to look.

055 addendum (2026-10-27): uvicorn `--reload` waits for open connections before it restarts;
the frontend's event stream (and the Vite proxy's keep-alive) holds one open, so a backend
file save during a browser session leaves the dev server at "Waiting for connections to
close" until the stack is restarted. Save backend files between browser sessions, or restart
`make dev` after.
