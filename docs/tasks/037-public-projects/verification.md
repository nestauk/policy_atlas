# Verification: 037-public-projects

Evidence for the build (steps 5–6), 2026-09-04. Requirement ids (R1–R5) and
design decisions (D1–D6) are in [contract.md](contract.md).

## Owner ruling on gates (recorded deviation from the plan's gate map)

The owner instructed at build-open: "don't over do it with interim long
tests (make verify). Do the work and then let's test in the end." Applied
as: baseline `make verify-fast` at build-open; targeted pytest/vitest per
phase; **one full `make verify` at the step-6 exit** (below). The plan's
phase-2 full-verify gate was folded into the exit gate on this ruling.

## Red base inherited from task 036 (fixed here, commit `a95e1aa`)

The build-open baseline was **red before any 037 change**: task 036 added
the `waitlist_entry` table (37 tables) but the six metadata table-count
tests still asserted 36. Fixed with a comment trail; not a 037 defect, but
037 carries the fix.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify-fast` (baseline) | fail → explained | the six 036 table-count tests above; green after `a95e1aa` |
| Phase 1 targeted pytest (52 tests) + mypy | pass | fast-worker run, re-verified in the phase-2 battery |
| Phase 2 battery: 9 API test files (205 tests) | pass | run by the lead — Codex's sandbox cannot reach Postgres |
| `uv run mypy src/policy_atlas/api` | pass | 44 files |
| `uv run ruff check src/policy_atlas/api tests/api` | pass | |
| `pnpm vitest run src/views/` (380 tests) + full FE suite in phase 3 (515) | pass | |
| `pnpm typecheck` / `pnpm lint` | pass | 1 pre-existing warning (`SplashField.tsx`) |
| `make openapi-sync` | pass | run after phase 1 and again after phase 2 |
| `make verify` (step-6 exit) | **pass** (exit 0) | full suite: okf-validate · test (backend 2419 + frontend 515+) · typecheck · lint · build, 2026-09-04 |

## Checks beyond the build

- **Deterministic tests.** The conformance suite now pins a three-class
  auth boundary: always-401 (every route not listed), conditionally-public
  (the 11 GETs — anonymous 404 byte-identical for private/unknown, non-401
  for a public Task), public write (waitlist). `test_public_access.py`
  covers the D2 header matrix (no header / garbage bearer / `Basic` /
  bare `Bearer` / wrong scheme), revocation (flip off → next anonymous
  request 404), archive revocation, redaction (D5), signed-in outsider
  (D4), listings unaffected (D3), admin no-trace on a public row.
  Frontend: public shell (two tabs, Sign in, stash-and-splash on 404,
  SSE never opened), LifecycleRoute public gate (Share/History/Plan URLs
  land on Results; run-state locks do not apply on the public leg),
  AppShell public branch (two tabs, no chat panel), Share tab control
  (owner-only, PATCH body, copy-link URL, warning copy).
- **Manual / API (live dev stack, 2026-09-04).** Against the running dev
  backend and the real "ottoacoustic emissions" Task
  (`65f4e460-1d06-4890-ab98-3c064786d2d6`): owner read `access=full`;
  anonymous 404 while private; owner PATCH `{is_public:true}` → anonymous
  GET 200 in the redacted shape (`access=public`, `owner_display=null`,
  `portfolio_ids=[]`, `is_owner=false`); anonymous funnel/artefact/
  evidence 200; anonymous decisions 401; garbage bearer 401; `Basic` 401.
- **Manual browser check — PENDING (human).** Browser automation was not
  available in this session. The Task above is left public for the check:
  open `http://localhost:5173/projects/65f4e460-1d06-4890-ab98-3c064786d2d6/results`
  in a private (signed-out) window → Results renders with exactly two
  tabs and a Sign in button; check Sources; then as the owner use the new
  Share-tab control to Stop sharing publicly → the private-window URL now
  lands on the splash page. This is the contract's live-check pin.

## End-to-end command

```
TOKEN=$(cd backend && uv run python -m policy_atlas.api.dev_issuer mint \
  --dir .dev-issuer --sub dev-user --client-id policy-atlas-dev | tail -1)
PID=65f4e460-1d06-4890-ab98-3c064786d2d6
curl -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"is_public": true}' http://localhost:8000/api/v1/projects/$PID
curl http://localhost:8000/api/v1/projects/$PID           # 200, redacted
curl http://localhost:8000/api/v1/projects/$PID/artefact  # 200
curl -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"is_public": false}' http://localhost:8000/api/v1/projects/$PID
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/projects/$PID  # 404
```

## Diff summary

Five commits on `task/037-public-projects` after the design docs:

1. `a95e1aa` — the inherited 036 table-count fix (above).
2. `b7f5bfb` (phase 1) — additive migration `b2f6a9d4c1e7`
   (`project.is_public`), `ProjectOut.is_public` + `access`,
   `ProjectUpdate.is_public` under the explicit-null 422 rule,
   owner-only flip in `update_project` with `project.shared_publicly` /
   `project.unshared` audit events on real changes only, redacted-shape
   support in `project_out()`.
3. `03cc63e` (phase 3) — Share tab "Public link" section: owner-only
   toggle, exposure warning, copy-link; replaces the coming-soon line.
4. `6037009` (phase 4) — public router gains the task Results/Sources
   routes under `PublicTaskShell`; public-view context disables the chat
   query/affordance; `RunStreamProvider connect=false`; signed-in
   outsiders get the two-tab view via AppShell + the LifecycleRoute gate;
   query cache cleared on settled auth-status changes.
5. `d6aac6f` (phase 2) — `get_optional_user` (header-keyed anonymity),
   `readable_or_public_project` (the one public-leg helper: graded →
   public → traced admin), optional auth on the 11-route surface
   (`decisions` stays authenticated), `GET /projects/{id}` on a tokenless
   router with redaction, the conditionally-public conformance class,
   `test_public_access.py`.

**Flagged deviations (minor, within contract vocabulary):**

- `tests/api/test_projects_router.py` asserted tokenless
  `GET /projects/{id}` → 401; under the approved boundary it is the
  indistinguishable 404. Updated deliberately with a comment (rubric 5).
- The LifecycleRoute public gate also bypasses run-state tab locks on the
  public leg (contract R2 promises "full current content"; the locks are
  an owner-side affordance) — pinned by a test.
- `frontend/src/mock/fixtures.ts` gained the two new fields
  (`is_public: false`, `access: "full"`) to keep typecheck green; the
  mock still serves only the signed-in world (contract § Out).

## Review findings

_Added at step 7 (fresh conversation)._

## Rubric status

_Completed at step 7._

## Intent & assumptions

- Public means link-only (D3): no index, no listing changes — pinned by
  `test_public_access.py::listings` and the unchanged `listing_scope`.
- A public row read by an admin is served by the public leg, not the
  admin leg — no `admin_read` trace (the caller was entitled anyway).

## Known unverified items

- **The manual browser check** (§ above) — pending the human; everything
  else on the live-check pin ran at the API level.
- The plan's phase-2 full-verify gate was consolidated into the exit gate
  (owner ruling, § above).
- Codex could not run DB-backed tests in its sandbox (TCP to Postgres
  blocked); the lead ran the full battery locally instead. Worth knowing
  for future codex-as-doer briefs on this repo.

## Public safety

No secrets, no source text, no traces in this file or the diff. The dev
Task named above is the user's own dev-database row; its title is not
sensitive. Waitlist/PII surfaces untouched.

## Review handoff (step-7/8 inputs)

- **Executor provenance (family flip):** phase 2 (the security-critical
  access layer) was implemented by Codex against the lead's fixed seam
  design and reviewed by the lead — the step-7 security lane should be a
  non-author Claude context reading `_access.py::readable_or_public_project`,
  `auth.py::get_optional_user`, `read_models.py`, and the conformance
  diff. Phases 1/3 fast-worker, phase 4 lead.
- **Adjudication items:** the three flagged deviations in § Diff summary.
- **Knowledge candidates:**
  - A slice that adds a table must bump the six metadata table-count
    tests (`assert len(metadata.tables) == N`); 036 shipped without it
    and handed 037 a red base. A grep for `metadata.tables) ==` belongs
    in any schema-adding checklist.
  - `HTTPBearer(auto_error=False)` returns `None` for wrong-scheme and
    malformed `Authorization` headers — an optional-auth dependency keyed
    on the parsed credentials silently treats them as anonymous; key on
    the raw header instead (adversarial finding 4, now
    `get_optional_user`).
  - The Codex sandbox cannot reach local Postgres — briefs that need
    DB-backed pytest must say "implement + static checks; the lead runs
    the DB battery", or the run wastes its verification step.
  - Background `make verify-fast` racing a subagent's edits in the same
    working tree produces confusing partial failures; sequence baseline
    runs before launching workers (the 037 baseline red turned out to be
    genuine, but the diagnosis cost was the race ambiguity).
  - React Query cache + router-swap-on-auth-status = stale-identity
    leaks; `queryClient.clear()` on settled status change is the whole
    fix (adversarial finding 2).

## Deferred work

See `docs/deferred.md` § Export & sharing (updated this slice):
portfolio-level public sharing · public index/gallery · mock-API public
mode (and with it, public-view e2e journeys).
