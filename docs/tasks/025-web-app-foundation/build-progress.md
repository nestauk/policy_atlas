# 025 build progress (working note — deleted or folded into verification.md at step 6)

Updated: 2026-07-21 (build conversation B)

| Phase | State | Commit |
|---|---|---|
| 0 baseline | DONE (1797 green) | — |
| A hoist | DONE | 7a5fc78 |
| B migrations + lifecycle | DONE | a1cd185 (incl. owner-approved gate expansion: event_log.run_id nullable, 2026-07-21) |
| C parking/continuation | DONE | 1b1f6b2 (parity 7/7, protocol 7/7, pins, hash guard, thread-safety audit + _SEARCH_CACHE fix) |
| D.1 contract models + web-api.md | BUILT, uncommitted (commits with D) | — |
| D.2 auth/app/CORS | codex job task-mru53sg5-hlb16x IN FLIGHT | — |
| D.3 routers · D.4 pagination sweep | not started (D.3 next codex job after D.2) | — |
| E SSE + read models | not started | — |
| F.0 scaffold | BUILT, uncommitted (pnpm 11.15.1, React 19.2.7 + compiler via @rolldown/plugin-babel, router 7.18.1, Tailwind 4.3.3, recharts 3.9.2, TS 6.0.3, security config in pnpm-workspace.yaml) | — |
| F.1 codegen/drift | not started (needs D routers for OpenAPI export) | — |
| G.1 theme + Button/Chip · G.2 primitives (Card/Nav/Sheet/Tooltip/Popover/Tabs/Toast) | BUILT (lead), 13 tests green, uncommitted | — |
| G.3 OIDC/SSE client/store | not started (codex, after D.2 shapes exist) | — |
| H views · I acceptance | not started | — |

Python deps added (approved): fastapi/uvicorn/pyjwt/cryptography (pyproject ceilings).
Frontend deps added since F.0: cva, tailwind-merge, clsx, @testing-library/user-event, @radix-ui/{dialog,tooltip,popover,tabs,toast}.

Knowledge candidates so far (step-6 § Review handoff feed):
- event_log.run_id NOT NULL vs run-less lifecycle events — design-phase blind spot; owner widened the gate (AskUserQuestion mid-build worked well).
- Parity across two independent walks must compare STRUCTURALLY (first-seen UUID canonicalisation preserving referential structure); raw-uuid equality can never hold. Codex initially wrote the broken comparison twice.
- codex sandbox cannot reach localhost Postgres OR uv cache — always have the lead run DB tests; use .venv/bin/* fallbacks.
- codex runtime runs ONE task at a time — a second codex:rescue while one runs is silently rejected with "prior task still running".
- test seeds vs migration roundtrips: schema-aware seeding (inspect live columns) is the pattern when tests run at downgraded revisions.
- 024's "no steering event before first run" invariant means a pause (and hence parking) can only exist after the first component run — continuation.requested can always attach to the pause's run id.
- C.4 audit found a real check-then-delete race in search_live._SEARCH_CACHE, newly reachable under concurrent walks — fixed with lock+pop.
- Vite 8/@vitejs/plugin-react 6 removed babel option; React Compiler wires via @rolldown/plugin-babel + reactCompilerPreset; verified compiler ran by grepping build output for useMemoCache.
- pnpm minimumReleaseAge=1440 actually rejected 4 too-fresh packages during F.0 — the supply-chain gate demonstrably works.
- Node 25 has no bundled corepack; pnpm via brew, packageManager field still pinned.
- The universal steering floor (continue/abort valid at every pause even when not in the stored options list) must be mirrored by API-side validation — codex validated fail-closed against stored options only.

Live-check prerequisite for I.2: the user's real .env stayed at repo root (permission-blocked from moving); backend/.env currently holds only example values — the OPENAI/LANGFUSE keys must be moved into backend/.env by the user before the live check.
