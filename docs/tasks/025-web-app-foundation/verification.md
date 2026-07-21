# Verification: 025-web-app-foundation

Evidence for the build (conversation B, step 6). Public-safe: no secrets, raw
source text, credentials or unredacted traces.

## Commands run

| Command | Result | Notes |
|---|---:|---|
| `make verify` (FULL, step-6 exit) | pass | okf-validate · backend test (1875 + ingest suite) · mypy strict (221+ files) · ruff · build · audit-paths · prompt-guard · font-guard · drift-check · frontend typecheck/lint/vitest(50)/build |
| `make audit` (CI catch, post-PR) | pass | pip-audit flagged GHSA-537c-gmf6-5ccf in cryptography 47.0.0 (new 025 dep); bumped to 48.0.1 (constraint was <48); full API suite 103/103 green on the new major |
| `make verify` (FULL, step-7 exit after the review fix wave) | pass | 1923 backend tests · mypy strict (232 files) · ruff · okf-validate (92 concepts) · drift-check (client regenerated for pagination) · frontend typecheck/lint/vitest(57)/build; `pnpm e2e` 4/4 on a fresh mock server |
| `make verify` at phase gates | pass | T0.1 baseline · A.3 (hoist) · B.3 (schema) · C.4 (runner core) · E.2 (ingest-adjacent) · H.4 — each green before its commit |
| `make verify-fast` at intermediate commits | pass | per the plan's binding gate map (D.4, F.1, G.3 verify-fast) |
| `make drift-check` mutation proof | pass | scratch field added to `ProjectOut` → gate FAILED with a clean diff naming `make openapi-sync`; reverted → green |
| `pnpm e2e` (Playwright mock journey) | pass | 4/4, run 3× for stability; steps (a)–(k): landing card/chip → workspace → stage timeline → pending check-in → answer suggested option → run completes → evidence base sections → citation marker → popover quote → dossier sheet with `?source=` URL → sources list → landscape chart → keyboard Tab+Enter on a citation → reduced-motion run → no horizontal scroll at 1280/768 |
| Clean-clone acceptance (I.1) | pass | every README command executed and verified: dev-issuer init/mint exit 0 · `make -C backend dev` → `curl /healthz` 200 · authed `GET /api/v1/projects` 200, unauthed 401 · Vite proxy live (`:5173/api/...` → 200 with a minted token) · mock mode + e2e green |

Red gates that occurred mid-build were each root-caused, never committed
over: the B-phase first verify failed on NOT-NULL `project.name` (test
seeds); the H-phase first verify failed once on the extract write-order
golden — a `ctid` physical-order assumption breaking under the busier
suite's page reuse; hardened to `(created_at, ctid)`, 5/5 after. During
I.1 the shared test DB's `project` table hit Postgres's 1600-column
tuple-descriptor ceiling (dropped columns count; the 025 migration
roundtrip adds/drops six `project` columns per suite run and the suite ran
many times today) — the test DB was recreated (14 attribute slots after)
and `test_migrations_025` now provisions its own scratch database per run,
so the consumption can never accumulate on the shared DB again.

## Checks beyond the build (contract-named deterministic tests → all pass)

- SSE replay idempotence + restart simulation; backlog→tail race injection
  (mid-flight stream, no gap/duplicate across the cutoff); resolved-pause
  replay (a decided pause never ends replay as pending; pending endpoint
  returns exactly the current blocking pause or nothing) — `tests/api/test_sse.py` (6).
- Steering round-trip through the real seam (park → answer → claim →
  continuation completes); double-answer barrier (threading.Barrier → one
  decision + one 409, never a duplicate continuation); continuation crash
  tests on BOTH claim sides + startup-drainer redispatch; orphan-sweep
  double-boot idempotence — `tests/api/test_continuation_protocol.py` (7).
- Continuation context parity per the reducer annex: unbroken vs
  parked-and-continued walks, full pinned surface (header/digest/bundles/
  options/router/references/overlays/collation) + all 16 fields, compared
  structurally (per-walk first-seen UUID canonicalisation); cases: continue ·
  adjust · failed-then-successful rerun (G4) · segment re-entry (G3,
  re-parks at the re-presentation) · free-text multi-fragment overlay (G5);
  class-9 regressions for the G3 map threading — `tests/runtime/test_continuation_parity.py` (7).
- CLI blocking path byte-identical pins (golden render; Continue completes;
  NullIO never pauses/parks) — `tests/runtime/test_cli_blocking_pins.py` (4).
- Thread-safety both-complete test (two concurrent stub walks, two
  projects: both succeed, event logs fully project-scoped, sequences dense)
  — `tests/runtime/test_concurrent_walks.py`; audit artefact
  `thread-safety-audit.md` (one real finding, fixed: `_SEARCH_CACHE`
  check-then-delete race → lock + pop).
- Migration up/down against a populated pre-025 DB: backfill (plan title /
  question, `Untitled project` fallback), row-by-row downgrade mappings
  (paused→aborted, interrupted→failed, `ended_at` stamped), run-less
  event_log rows deleted + NOT NULL restored, re-upgrade re-entrant —
  `tests/core/test_migrations_025.py`.
- Auth provider conformance: two asymmetric dev issuers, key rotation,
  expiry, wrong issuer/audience, cross-issuer, HS256-with-public-key and
  alg=none attacks all 401; `WWW-Authenticate: Bearer`; envelope shape —
  `tests/api/test_auth_conformance.py`; CORS explicit-origin + 422/500
  envelope — `tests/api/test_cors_and_envelope.py`.
- Authz fail-closed: 401 everywhere unauthenticated; cross-owner
  reads/writes 404 asserted **byte-identical** to never-existed —
  `tests/api/test_projects_router.py` + `test_api_conformance.py`.
- Lifecycle: rename persists + transactional audit event (rollback →
  neither); archive hides + retains + idempotent (one event); 409 while a
  run is running/parked — `tests/api/test_lifecycle.py` + routers tests.
- Planner: turn lock 409 · client-turn-id idempotence (no second planner
  call) · bounded session cache eviction — `tests/api/test_planning_router.py`.
- Pagination cap + envelope + naming conformance sweep over the OpenAPI
  document (snake_case, no internal names, response_model whitelist) —
  `tests/api/test_api_conformance.py` (15).
- Read-model goldens over a seeded ladder project (funnel, screened-in-only
  landscape, evidence statuses, findings, coverage sentence, artefact
  shape, chunk-context clamp at start/middle/end spans) —
  `tests/api/test_read_models.py`.
- Frontend (vitest, 50): store replay idempotence + mid-cursor resume ·
  pending→resolved lifecycle · tick transience · SSE line-parser (chunk
  boundaries) · token-never-in-URL · mid-run 401 → refresh → reconnect at
  the same cursor · scrub adversarial Unicode/control chars · error-class
  surfaces · primitives keyboard flows.
- Mock/live contract: one schema generates both ends; `make drift-check`
  in verify + CI; mock mode implements the same generated interface.

## End-to-end command

Deterministic full-suite gate (the exact step-6 exit command):

```sh
cd /Users/shabeer.rauf/repos/policy_atlas && make verify
```

Playwright mock-mode journey (browser end-to-end over the scripted run,
check-in answer, artefact/citation/dossier, keyboard + reduced-motion +
1280/768 no-horizontal-scroll):

```sh
cd frontend && pnpm e2e
```

**Live check (I.2): RUN 2026-07-21, ~52 min wall (inside the 60-min pin)**
— full narrated log with timestamps: [live-check-log.md](live-check-log.md).
Driven through the real browser UI (Chrome) against the live backends
(real keys, dev DB, dev-issuer auth). Every pinned step held:

- Project A (green budgeting / finance ministries, standard/Frequent, two
  real planner turns incl. a folded refinement) parked at the P1
  after-acquire steer point (49 found, honest inadequate/error coverage —
  one search backend unkeyed in this env).
- Project B (second dev-issuer user, rapid/landscape/Unattended, one
  planner turn) executing while A parked. Probes during dual activity:
  `/healthz` 200 in 0.003 s, funnel(A) 200 in 0.037 s (pin < 2 s);
  cross-owner 404s **byte-identical** to never-existed; second dispatch
  409; archive-while-running 409 `run_active`.
- **Restart while A parked ∧ B executing** (hard kill): A survived
  (`paused`, exactly one pending check-in), B honestly `interrupted` by
  the orphan sweep; UI rebuilt from replay with A's pending card intact.
- Post-restart answer through the UI: free-text steer → 202 compile →
  **confirm-gate delta render** (incl. one round showing an honest
  refused-fragment list) → apply → `steering.decision` +
  `continuation.requested` in one transaction → claim → **boundary
  continuation walk** executed screen_abstract WITH the applied criteria →
  Frequent mode parked again at the next boundary (the designed
  park-per-boundary loop) → `change_mode → unattended` → walk ran to
  **succeeded** (49→11 relevant→8 read in full→11 selected→8 cited).
- Evidence base rendered: annotation layer in the prose (span-anchored
  claims, inline citation markers, Evidence-gap chip), composed coverage
  sentence honest, citation popover (quote + tier/appraisal labels) →
  clamped surrounding context (the 008 seam, live) → URL-addressable
  dossier sheet; reference-click dossier fully populated (status ladder,
  labels never scores, origin, DOI).
- Rename persisted; archive idempotent (200×2, exactly one
  `project.renamed` + one `project.archived` audit event); landing hides
  the archived project (rows retained), `?status=archived` lists it,
  user B's landing shows `interrupted` honestly.

**Five integration findings caught and fixed in place by the live check**
(each gate-checked; none reachable by the mock/unit paths):
1. API deps defaulted to stub planner/router and EMPTY search backends —
   now key-driven via `orchestrate.live_planner_and_backends` (the stub
   router would have faked the confirm gate in production).
2. `load_settings()` never loaded `backend/.env` (house `load_dotenv()`
   pattern added).
3. Double `/api` prefix in the frontend client base URLs (generated paths
   already carry `/api/v1`) — invisible to mock mode by construction.
4. C.3 confirm-apply passed the plan row as a dict into the steering
   persistence (attribute access) → 500; and the pre-existing 024 gap it
   exposed: the screen branch of `_validate_directive_delta` was the one
   of seven that didn't map its directive error into the refusal path —
   malformed router output crashed instead of refusing honestly.
5. The continuation claim's paused→running flip emitted no frame —
   `continuation.claimed` now maps to `run.status: running` in SSE (a
   continuing walk showed as still paused in the store).
6. Test hermeticity vs a keyed `backend/.env`: `tests/conftest.py`'s
   `load_dotenv()` plus `alembic/env.py`'s `load_dotenv()` (re-run by every
   migration-running fixture) injected the developer's live keys into the
   pytest process, flipping key-switched paths (the CLI pin test's
   `orchestrate.main`) live under socket-deny. Fixed: conftest scrubs the
   product-egress keys after loading; alembic env reads `DATABASE_URL` via
   side-effect-free `dotenv_values()`; API settings stays pure
   `os.environ` with `make -C backend dev` owning `.env` loading via
   `uv run --env-file`. The suite is now green with real keys present in
   `backend/.env` — the exact state every keyed dev machine will have.

**Review items from the live check** (recorded, not fixed): citation→
dossier join is title-keyed and misses locator-fallback titles
(`CitationOut` should carry `source_id`); no rename/archive control in the
views (mutations exist and are tested; actions exercised via the seam);
ingest presents under the acquire label ("Searching sources") while
reading documents; graceful SIGTERM lets the walk executor keep running
during shutdown — deploys must hard-kill or the lifespan should stop the
executor (deploy-posture note for the infra slice).

## Diff summary

Seven strands, one branch, phase commits `7a5fc78 · a1cd185 · 1b1f6b2 ·
0695dc4 · 8d7fcb4 · c47ef23` (+ this phase-I commit):

1. **Hoist** — `git mv` of the Python project into `backend/`
   (import-neutral, history-preserving); root Makefile orchestrates; new
   `audit-paths` gate; CI paths updated.
2. **Schema** — `project` lifecycle columns with expand→backfill→constrain
   + `event_log.run_id` nullable (**owner-approved gate expansion,
   2026-07-21** — finding-12 audit events on run-less projects had nowhere
   to live under the 024 NOT-NULL pin); `capability_run` status check
   widened (`paused`/`interrupted`) with pinned downgrade mappings.
3. **Runner parking + continuation** (the hard core) — `WalkParked` park
   disposition (one transaction: `paused` + `run.parked` snapshot);
   `runtime/continuation_state.py` reducer (16 fields, G1–G5 adjudications;
   G3/G4 are the one approved runner-behaviour delta);
   `run_plan(resume_from, resume_decision)`; `api/continuation.py`
   protocol (answer+`continuation.requested` atomic, claim, drainer,
   orphan sweep); per-project `FOR UPDATE` lock primitive.
4. **API** — contract package → OpenAPI → generated TS client with a
   mutation-proven drift gate; RS256/JWKS auth + dev issuer; routers for
   projects/planning/runs/check-ins with the pinned error envelope,
   pagination cap, BOLA-opaque 404s; read models over the real schema
   (screened-in-only landscape, composed coverage sentence, chunk-context
   clamp, B2′ marks); SSE replay+tail from `event_log` with typed frames
   and the ephemeral tick channel.
5. **Frontend** — pnpm 10+ scaffold with the pinned supply-chain config;
   React 19 + Compiler; brand layer from the Nesta tokens (cutout buttons,
   0 radius, growing underline) + Radix copy-in primitives; auth seam
   (dev token panel now, OIDC config-only later); replay-idempotent
   event-sourced store; the demo-validated views incl. the annotation
   layer, citation ladder, dossier, confirm-gate delta render; mock mode;
   state/error matrix surfaces; scrub + `dangerouslySetInnerHTML` ban.

**Flagged deviations / adjudications (visible, not silent):**
- `event_log.run_id` nullable — owner-approved gate expansion (see above).
- Adjudicated durable-event additions of the `run.parked` class:
  `run.opened`, `run.finished`, `plan.approved`, and the pause event now
  carrying its exact deterministic `render` (the check-in content of
  record is served verbatim, never re-derived).
- `continue`/`abort` validate as the universal steering floor at every
  pause even when absent from the stored options list (mirrors the
  in-process path; codex had validated fail-closed against stored options
  only).
- Egress-guard test extended: `api/auth.py` + `api/app.py` are sanctioned
  HTTP homes (JWKS/identity-provider egress — auth-plane, never
  search/model egress).
- `CitationOut` gained `citation_id` (clients could not discover the
  chunk-context key); client regenerated through the drift gate.
- Extract write-order golden hardened from `ctid` to `(created_at, ctid)`
  (pre-existing test; full-suite-only flake under the busier suite).
- `_SEARCH_CACHE` lock+pop fix (thread-safety-audit finding, newly
  reachable under concurrent walks).

**Executor provenance (family-flip input for review):** B.2/B.3, C.2, C.3,
D.2, D.3, E.1, E.2, H.4 — codex lane (briefs + lead adjudication; all
DB-backed acceptance run by the lead — codex sandbox reaches neither
Postgres nor the uv cache). A.2/A.3, D.1 transcription, D.4, F.0, F.1,
G.3, I.1 — fast-worker. **Re-routes logged:** F.1 and G.3 moved
codex→fast-worker (codex is one-serial-task; both are precisely-specified
plumbing) — the codex-constraint fallback, not a mid-build re-decision of
judgment work. C.1, D.1 shapes (web-api.md), G.1/G.2, H.1–H.3, all fixes
above — lead.

## Intent & assumptions

The durable record is the only source of truth the web app reads; every
mutation goes through the real backend seams; one schema generates both
ends. Parked pauses hold no thread; interrupted ≠ resumable; pending is
derived, arrival is live. Strict per-owner tenancy. One instance / one
worker posture (cross-instance is a named seam).

## Known unverified items

- Real-Cognito verification is config-only by design and conformance-tested
  against two asymmetric issuers, but no actual Cognito pool exists until
  the infra slice.
- The review-stack fixes (§ Review findings below) have deterministic
  coverage but have not been re-exercised in a second live browser session;
  the pinned live check (I.2) ran against the pre-review build.

*(Stale-section fix, step 7: this section previously still said the live
check was blocked — it ran 2026-07-21 as narrated above; the contradiction
was itself a review finding.)*

## Public safety

No secrets, keys, or raw source text in the diff or this file. Frontend
fixtures are invented policy-domain content per the sanitized-fixtures
policy. Dev-issuer keys are generated locally into gitignored dirs; font
binaries untracked with a CI guard; no tokens in URLs or logs.

## Review handoff (step-7/8 inputs)

Adjudication items: the flagged deviations above, esp. the gate expansion,
the durable-event additions, and the universal-floor validation. Per-angle
diff scoping: exclude `frontend/src/api/gen/**`, `frontend/openapi.json`,
`frontend/pnpm-lock.yaml`, `backend/uv.lock` from review diffs.

## Review findings (step 7, 2026-07-21 — fresh conversation, lead-adjudicated)

**Lanes run (Tier 4):** contract-verifier (pinned Opus, all 19 rubric items +
verification/ADR-vs-code) · code review ×2 scoped passes (backend; frontend —
the `/code-review medium` substitute: the command is not invocable in this
harness session, so the sanctioned `code-reviewer` agent ran as the Claude
half, per-surface-scoped with generated/lock/data/`docs/tasks` files excluded)
· security-auditor (auth/JWT/BOLA/SSE/injection/supply-chain/secrets) ·
**codex adversarial** (family-heterogeneous half — credits were live again,
superseding the 2026-07-16 exhaustion; job task-mruhezri-fpcxsw) · a
deep-reasoner adversarial pass (dispatched before codex availability was
known; kept as a supplementary same-family read — its findings proved
non-redundant) · lead trace-content review of live-check-log.md + the five
live fixes (none fake-done; the steering fix routes to the refusal path and
was proven live). `make verify` was green before any lane dispatched.

**Economy:** ~740K reasoning-class + ~490K fast-worker tokens. The
reasoning-class figure is ~3× the routine-slice pin — driver: Tier-4 baseline
(5 lanes) over a 21.5K-line seven-strand diff, plus the double adversarial
lane. Fast-worker stayed inside its 500K pin. Recorded for the standing
review-economy retro (this is the fourth slice running over).

**Headline: 19 MAJOR/critical-class findings, all verified against the code
by the lead before adoption; ~25 minors.** Convergent across independent
lanes (high-confidence by the stack's own rule): park/phantom-pending
(deep-reasoner + codex), abort-invisible-to-SSE (deep-reasoner + codex),
sequence-allocator race (backend lane + codex), zombie-`running` on executor
exception (backend lane + codex), `href` scheme gap (frontend + security
lanes), stage-vocabulary leak (contract-verifier + frontend scrub note).
Unique catches justifying each lane: codex — drainer-runs-on-stub-backends,
plan-lineage cross-contamination, same-sequence SSE frame drop, option-params
shape, archive-dispatch race; contract-verifier — the locked-vocabulary leak
+ the `event_log.run_id` gate-expansion audit; security — JWKS negative-cache
DoS + conformance under-coverage; backend lane — SSE idle full-log re-read +
the boot-bricking sweep `LookupError`; frontend lane — the 401-retry
consumed-body clone + unkeyed CheckInCard; deep-reasoner — the
claim→execute unrecoverable window + `_live()` posture.

### Adopted and fixed (all gate-checked; frontend 57/57 vitest, backend suites green)

Continuation protocol (the slice's hard core — six findings fixed together):
1. Startup sweep three-way classification: claimed-but-unexecuted walks are
   **re-executed, never interrupted** (adv-M1; contract's answer-durability
   promise now covers the claim→execute window); running-with-no-attachment
   is interrupted with a null attachment instead of raising inside the
   lifespan (backend-M3 — previously **bricked every subsequent boot**);
   post-claim progress detection errs toward interruption (never re-runs a
   committed component).
2. The lifespan drainer now composes the same key-driven backends + `ParkIO`
   + orchestrator as the request path (codex-1 — it previously redispatched
   real continuations onto deterministic stubs with NullIO auto-continuing
   every pause); `execute_continuation`'s backends/io are now required
   parameters so the stub fallback is unreachable from any production seam.
3. Pending check-ins require the walk to actually be `paused` (adv-M2/
   codex-3 — a death between pause-emit and park no longer renders a phantom
   card whose answer 404s). The pause-emit/park two-transaction window itself
   is accepted residual: a death inside it is a genuine mid-execution death
   and now presents honestly end-to-end.
4. Every executor catch-block marks the walk interrupted best-effort
   (backend-I1/codex-7 — no more permanently-`running` zombies holding the
   project's run slot until the next restart).
5. Plan lineage (codex-2): planning turns now 409 `run_active` while a walk
   is running or parked — steering is the sanctioned mid-run plan channel,
   and the fence makes the reducer's latest-approved plan selection provably
   the walk's own lineage (amendments supersede within it). Adjudicated as
   the minimal sound resolution; per-walk plan custody plumbing declined as
   unneeded under the fence.
6. API abort now mirrors the runner path (adv-M5/codex-5): plan →
   `abandoned` and `run.finished{status:aborted}` in the same transaction —
   an aborted run no longer renders as "Paused" forever in the store.

Transport/store:
7. `events.append` allocates under a SAVEPOINT retry (backend-M2/codex-6 —
   the two 025 writer families collide instead of failing a rename or a
   component commit; misordering remains impossible; two-writer barrier test).
8. SSE idle polls no longer re-read the whole project log per client per
   0.4s (backend-M1); the decided-pause context fetches decision events only.
9. The store accepts equal-sequence distinct-type frames (codex-4 — one
   decision's `checkin.resolved` no longer permanently swallows its
   `plan.updated` twin) and resets stage/liveness state on a new run id
   (codex-10).
10. The 401-retry middleware clones requests before the body is consumed
    (frontend-critical-1 — bodied POST/PATCH retries after token expiry
    previously threw; now tested with a bodied retry). `CheckInCard` is
    keyed by `check_in_id` (frontend-critical-2 — confirm state can no
    longer carry across check-ins at the 024 fidelity surface).

Product pins / API surface:
11. Locked vocabulary (contract-verifier MAJOR-1): `CheckInOut.stage` now
    carries the public stage key (shared `stage_vocabulary` module); the
    card renders the server-supplied stage *label* (hides the chip when
    unknown — hide, never fake) and scrubs it.
12. Option parameters (codex-8): change_mode renders a mode select posting
    `{new_mode}`; other input-requiring options route into the free-text
    compile→confirm-gate flow instead of posting a malformed `{value}` delta.
13. Runs + check-ins lists paginated in the standard envelope (rubric 17,
    contract-verifier minor-3), regenerated through the drift gate.
14. Explicit backend-mode posture (adv-M4): `PA_BACKEND_MODE=live|stub|auto`
    — `live` fails loud without the core key, `stub` pins stubs on keyed
    boxes, boot logs missing search keys instead of degrading silently.
15. Archive consults the in-process dispatch reservation (codex-9); planner
    LLM calls moved outside the row-lock transaction (backend-I2 — a slow
    turn no longer stalls run creation process-wide, and a failed turn no
    longer leaves a dangling user message, m4); dispatch await 2s→10s
    (backend-I3); fan-out rerun decisions record post-amendment plan
    identity (backend-m1); router 400/422 details reach the user while 404
    stays deliberately generic for BOLA byte-identity (backend-m2); lost
    confirm tokens are an actionable 409 `confirm_expired`, not an opaque
    404 (backend-m3).
16. Frontend error surfaces wired: real 409 code vocabulary, view-level
    `isError` branches (no more fake-empty on 500), `ReauthRedirect` on
    persistent 401; `safeHref` http(s) allowlist on source URLs (convergent
    frontend+security); scrub uniformity on the remaining server strings;
    SourcesView page clamp + filter-scope honesty; SSE project-switch race
    guard; stable `AuthApi` across silent renewals (no more full replay per
    token lifetime); per-turn `client_turn_id` (idempotency key now works);
    `connecting` initial connection state; recharts route lazy-loaded
    (bundle warning gone); dead code deleted (`usePrefersReducedMotion`,
    `InlineConflictNotice`, `ServerErrorToast`).
17. Security hardening: JWKS negative cache (30s TTL, rotation test intact);
    unauthenticated + byte-identical-404 conformance sweeps now derive from
    the live route table (22 + 13 routes, all clean — a future route missing
    auth or ownership fails CI by construction); `nosniff` + HSTS headers.
18. Reducer snapshot hardening: `completed_components` is snapshot-read-back
    (G2 pattern, adv-m4) with derived fallback; new parity case interleaves
    canonical and free-text overlays on one component (adv-m5), asserting
    sequence-order folding is observable.

**Deliberate test changes (rubric item 5 justification):** two
`test_continuation_protocol` tests pinned the discarded interrupt-on-claim
behaviour; they were rewritten to assert the adopted recovery semantics and
a new companion test pins the interrupt path for genuine post-claim
progress. Two list assertions updated for the pagination envelope. The
extract write-order golden flaked AGAIN under the post-review suite (the
build's `(created_at, ctid)` hardening still tied on equal timestamps and
scrambled within the tie) — reworked to observe insertion order **at the
write seam** via a cursor-event capture, removing the physical-order
dependence entirely; the assertion itself is unchanged and strictly
stronger. Nothing else was weakened; the backend lane's rename-aware sweep
found no weakened tests in the build either. (Process note: the first
post-fix e2e run failed spuriously — Playwright's `reuseExistingServer`
silently reused a leftover non-mock dev server from the morning's live
check; 4/4 green on a fresh server.)

### Declined / deferred (with reasons)

- **NULL-owner backfill (backend-I4):** contract-pinned intent ("pre-existing
  rows … intentionally inaccessible; documented DB-level recovery") — a
  clarifying note added to the migration docstring only.
- **`event_log.run_id` nullable gate expansion:** disclosed, owner-approved
  mid-build via AskUserQuestion; the repo cannot prove the approval — named
  as the **top step-9 human-review confirmation item** (contract-verifier).
- **Park pause-emit/park atomicity:** narrow fixes adopted (finding 3 above);
  full single-transaction parking would move the pause emit inside the park
  path shared with the CLI blocking mode — declined as a runner reshape
  disproportionate to a window that now fails honest.
- **Sweep instance-ownership lease (adv-M3):** correct at the pinned
  one-instance posture; recorded as a hard deploy invariant
  (hard-kill-old-before-boot-new) in deferred.md alongside the existing
  SIGTERM/executor note — the lease belongs to the LISTEN/NOTIFY seam
  (infra slice).
- **Automated FE↔real-API integration net (adv-M6):** recorded as a known
  risk + deferred.md entry (thin real-HTTP smoke in CI); not buildable
  inside this review phase.
- **Refusal-wrap centralization (adv-m2):** declined — all seven (nine
  as-built) branches are individually wrapped; a parametrized test now pins
  every branch to the refusal path, which is the property that matters.
- **Prompt-guard filename scoping (contract-verifier minor-4):** declined —
  the guard covers the established prompt family by content hash;
  whole-repo LLM-string detection is a different tool. Noted.
- **`_dispatching` process-memory window (contract-verifier minor-2):**
  accepted under the pinned single-process posture (same posture as the
  reservation itself); the archive-race fix narrows its blast radius.
- **decisions `detail` allowlist (minor-7) / `VITE_OIDC_AUTHORITY` prod
  build guard (security-info):** deferred — latent-only today; the second
  rides the infra slice's deploy checklist (deferred.md).
- Cosmetic live-check review items already recorded (ingest under acquire
  label; rename/archive UI controls; `CitationOut.source_id`) → deferred.md
  in step 8; `source_id` is small but touches the contract — next-slice
  material rather than review-phase scope creep.

**Step-8 knowledge adjudication (2026-07-21):** authored from BOTH the
build candidates below and the stack's findings — 10 new concepts + 1
amendment (`event-log-sequence.md`), all written against the as-built code,
`make okf-validate` clean: startup-recovery-classifies-never-discards ·
run-status-transitions-emit-run-events · plan-lineage-by-fencing-not-custody
· observe-order-at-the-write-seam · structural-parity-uuid-canonicalisation
· tests-are-zero-egress-scrub-keys · column-churn-migrations-need-scratch-db
· mock-fetch-blindness · frontend-supply-chain-pnpm ·
vite8-react-compiler-wiring. Folded: run.parked-attachment invariant + G2
read-back (into the parity/recovery concepts); pnpm/corepack/vitest-glob
quirks (into the supply-chain concept). Declined with reasons: codex
sandbox/serial-task constraints (agentic-ops lane, recorded in this file's
provenance notes); dev-issuer two-provider seam (spec layer owns it,
web-api.md); HTML `content`-attr prop collision (transient library quirk,
recorded below); schema-aware test seeding (already encoded in
tests/helpers as-built — the code is the record).

Knowledge candidates (raw, per the 014 rule — step 8 authors
`docs/knowledge/` from these against the final code):

- `event_log.run_id NOT NULL` vs run-less lifecycle events was a
  design-phase blind spot; the mid-build owner gate (AskUserQuestion)
  resolved it cleanly — build-time gate reopening works.
- Parity across two independent walks must be STRUCTURAL: per-walk
  first-seen UUID canonicalisation preserving referential structure;
  raw-uuid equality can never hold. Codex wrote the broken comparison
  twice before the normalization spec was pinned.
- The codex sandbox reaches neither localhost Postgres nor the uv cache —
  design codex briefs so the lead runs DB acceptance; `.venv/bin/*` is the
  fallback for tooling.
- The codex runtime executes ONE task at a time; a second codex:rescue
  while one runs is silently rejected ("prior task still running") — plan
  serial codex pipelines, or re-route mechanical work down the ladder.
- Schema-aware test seeding (inspect live columns) is the pattern when a
  shared helper serves migration roundtrips at downgraded revisions.
- The 024 "no steering event before the first run" invariant guarantees a
  parked pause always has an attachment run id — `continuation.requested`
  can always ride it.
- `ctid`-ordered assertions are physical-order assertions: they break under
  page reuse once the suite gets busier; order by a logical key with ctid
  as tiebreak.
- Ambiguous/implicit SQLAlchemy joins (two FK paths, chained join
  inference) are a recurring codex failure mode — require explicit
  onclauses in briefs touching multi-FK tables.
- Vite 8 / @vitejs/plugin-react 6 removed the babel option; the React
  Compiler wires via `@rolldown/plugin-babel` + `reactCompilerPreset`;
  verify it actually ran by grepping the bundle for `useMemoCache`.
- pnpm `minimumReleaseAge: 1440` rejected four <24h-old packages during
  F.0 — the supply-chain gate demonstrably bites; pin to next-older
  releases rather than excluding.
- Node 25 dropped bundled corepack: install pnpm standalone (brew), keep
  the `packageManager` pin for corepack-capable machines.
- Native `EventSource`-style `TestClient` requests buffer infinite
  streams; an httpx-`ASGITransport` streaming harness with incremental
  line reads is the workable SSE test pattern.
- The HTML `content` attribute collides with a `content: ReactNode` prop
  when intersecting `ComponentPropsWithoutRef` — `Omit` it.
- The dev issuer is a CLI keypair, not an interactive IdP: browser auth
  needs a two-provider seam (paste-token dev panel / real OIDC adapter)
  behind one `getToken()` — Cognito stays config-only.
- Postgres counts DROPPED columns toward its 1600-per-table limit, so a
  migration-roundtrip test that add/drops columns on a shared test DB is a
  slow fuse: every suite run permanently consumes tuple-descriptor slots
  until CREATEs start failing with TooManyColumns. Column-churning
  migration tests must run on a per-test scratch database.
- Playwright specs under the package root get collected by vitest's
  default glob — exclude `e2e/**` in the vitest config or `pnpm test`
  breaks on `test.describe` outside the Playwright runner.
