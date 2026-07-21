# Implementation plan: 025-web-app-foundation

> **Status:** drafted 2026-07-21 — plan-phase adversarial review pending, then 🛑 owner.
> Contract: [contract.md](contract.md) (approved + adversarially adjudicated, gates
> re-approved 2026-07-21). Annexes: [continuation-state-reducer.md](continuation-state-reducer.md)
> (walk-loop field → durable source mapping; **binds Phase C**),
> [retro-reconciliation.md](retro-reconciliation.md) (RETRO §§2–5 classification),
> [fastapi-guidelines-digest.md](fastapi-guidelines-digest.md) (§2 binds plan, §3 build).
> Tier 4 → this plan requires owner approval; rollback plan in § Rollback.

## Implementation pins (lead-designed; briefs reference, don't re-derive)

1. **Build order is substrate-out:** hoist → migrations → runner parking →
   API → codegen → frontend. The frontend is never built against an unpinned
   contract; the API is never built against an unparked runner.
2. **The API package** is `policy_atlas/api/` (routers/, contract/ (Pydantic
   models), auth.py, sse.py, readmodels/, lifecycle.py, continuation.py,
   app.py). Routers stay thin; every handler is `async def`; runner work goes
   through the offload executor (never the loop — digest §1.2/§2); DB access
   uses short sync sessions via `run_in_executor` wrappers consistent with the
   existing engine (no async-driver migration this slice — digest §2 "pick one
   and be consistent").
3. **The per-project serialization primitive** is `SELECT … FOR UPDATE` on the
   `project` row, wrapped in one helper; run dispatch, check-in answers, and
   continuation claims all take it. No other locking vocabulary.
4. **Parking is a runner seam, not a rewrite:** `run_plan` gains a pause
   disposition — `block` (CLI, unchanged behaviour) or `park` (API) — behind
   the existing `OrchestratorIO` seam. Parking raises/returns a structured
   `WalkParked` outcome carrying the boundary position; the continuation
   entrypoint `continue_plan(project_id, capability_run_id, decision)`
   rebuilds walk state via the **continuation reducer** (annex) and re-enters
   the walk loop at the recorded boundary. CLI behaviour is byte-identical.
5. **Continuation protocol:** answer + `continuation.requested` event in one
   transaction (under the project lock) → executor task claims
   (`continuation.claimed`) → executes → terminal event. Startup drainer:
   scan for requested-without-claimed (or claimed-by-dead-boot-id), redispatch.
   Orphan sweep (executing walks of a dead process → `interrupted`) runs in
   the same startup hook, ordered: sweep first, then drain.
6. **SSE:** one endpoint per project; fetch-stream client with bearer auth;
   server reads backlog to a snapshotted max sequence and tails from
   sequence+1 in the same consistent view; 15s heartbeat comments;
   `try/finally` cleanup; `X-Accel-Buffering: no`. Ephemeral ticks ride the
   same stream with `ephemeral: true` payloads, never persisted.
7. **Contract source of truth:** Pydantic models in `api/contract/` →
   `make openapi` exports the document → `npm run gen` produces types +
   openapi-fetch client into `frontend/src/api/gen/` (committed) →
   `make drift-check` regenerates and fails on diff. Discriminated unions:
   SSE event + check-in models registered as named components (digest §3).
8. **Frontend layout:** `frontend/src/` → `api/gen/` (generated, never edited),
   `api/` (client wrapper + SSE stream), `store/` (TanStack Query setup + the
   event-sourced run reducer), `auth/` (OIDC adapter + dev-issuer flow),
   `ui/` (primitives: brand/ hand-built + radix/ copied-in), `views/`,
   `routes.tsx` (URL-addressable dossier/filters). Mock mode implements the
   generated client interface; fixture shapes generated from the same OpenAPI
   examples where possible.
9. **Design tokens:** `tailwind.config` theme from `nesta-brand-tokens.md` +
   `hifi.css` custom properties; fonts via `@font-face` with `font-display:
   swap` + fallback stack; CI font-binary guard in `make verify`.
10. **No new prompt surfaces** — a content-hash pin test over the prompt
    families guards it (rename-aware, rubric 15).

## Tasks

Executor legend: `lead` (justified), `codex` (judgment-bearing execution,
machine-verifiable done), `fast-worker` (mechanical/spec transcription),
`deep-reasoner` (analysis). Verify gates per § Gate consolidation.

### Phase 0 — baseline (½ day)
- T0.1 `lead` (inline; one command): build-open `make verify` on the branch
  base — never build on red. **[FULL VERIFY — mandatory class]**

### Phase A — monorepo hoist (1 day)
- T A.1 `lead`: layout + tooling map (what moves where; CI/Docker/Makefile/doc
  path list). *Lead: seam design — the map is the brief for A.2.*
- T A.2 `fast-worker`: execute the hoist per map (git mv python project →
  `backend/`, scaffold `frontend/` placeholder + `infra/.gitkeep`, patch
  Makefile/CI/Docker/docs paths, root-relative-path audit script).
- T A.3 `fast-worker`: post-hoist sweep — allowlisted path audit green.
  **[FULL VERIFY — mandatory: scaffold class]**

### Phase B — schema migrations (1 day)
- T B.1 `lead`: both migrations designed (project columns + backfill SQL;
  capability_run status constraint) — *lead: schema is a hard gate; design
  only, transcription below.*
- T B.2 `codex`: implement migrations + up/down tests incl. populated-DB
  fixture (pre-025 rows, paused rows on downgrade) + backfill assertions.
- T B.3 `fast-worker`: lifecycle audit events (`project.renamed`/`.archived`)
  + transactional emission tests. **[FULL VERIFY — mandatory: schema class]**

### Phase C — runner: parking + continuation (3–4 days; the hard core)
- T C.1 `lead`: continuation reducer seam design from the annex — module
  layout, function signatures, event payload additions (any gap-closing
  fields the annex names), parity-test harness shape. *Lead: seam design +
  the annex adjudication is judgment.*
- T C.2 `codex`: implement the reducer + `WalkParked` disposition + 
  `continue_plan` re-entry against the parity harness. Done = parity test
  green across the full pinned surface (header/digest/bundles/options/
  router/references/overlays/collation).
- T C.3 `codex`: continuation protocol (requested/claimed events, executor
  dispatch, startup drainer + orphan sweep ordering) + crash tests both
  sides of claim + double-answer barrier test.
- T C.4 `fast-worker`: CLI blocking-path pin tests (byte-identical behaviour)
  + thread-safety audit checklist execution per C.1's list (shared clients/
  caches/tracing under two concurrent stub walks; module-global config scan).
  **[FULL VERIFY — mandatory: runner core + event vocabulary]**

### Phase D — API core (2–3 days)
- T D.1 `lead`: contract models package skeleton + error envelope +
  the API's public shapes (one pass, all routers' request/response models) —
  *lead: the public interface is the slice's taste-bearing seam.*
- T D.2 `codex`: auth — JWT verification dependency (iss/aud/exp/JWKS,
  alg pinned), dev issuer, provider-conformance suite (two asymmetric
  issuers + key rotation), authz matrix tests (401; cross-owner 404
  indistinguishable-from-absent).
- T D.3 `codex`: projects + runs + check-ins routers — lifecycle semantics,
  run dispatch under the project lock (409 active / 409 capacity),
  check-in response → continuation.requested, planning-turns router with
  turn lock + process-local sessions + `409 planning_turn_in_progress`.
- T D.4 `fast-worker`: pagination envelope + page_size cap + snake_case
  conventions sweep + envelope conformance tests across all routers.
  **[verify-fast]**

### Phase E — SSE + read models (2 days)
- T E.1 `codex`: SSE endpoint per pin 6 + backlog→tail race-injected test +
  reconnect-cursor test + pending-vs-history invariant tests. Includes the
  search/fetch liveness signals for the ephemeral tick channel — the demo's
  4 `search_live.py` log lines are confirmed NOT on dev (retro-reconciliation
  annex): add them (or a designed equivalent) as the tick source.
- T E.2 `fast-worker`: read models over the real schema (demo readmodels.py
  as evidence): funnel, landscape, groups, evidence (+status ladder),
  findings (+B2′ priority marks), sources dossier (+citation-context clamp),
  decisions (steering_history-backed), coverage (composed sentence), plan,
  artefact (+annotation spans). Each with a golden test against seeded rows.
  **[verify-fast]**

### Phase F — contract codegen (½ day)
- T F.1 `codex`: OpenAPI export command, named-component registration for
  discriminated unions, `npm run gen` (openapi-typescript + openapi-fetch),
  drift check wired into `make verify` + CI. Done = mutating a Pydantic
  model fails the gate. **[verify-fast]**

### Phase G — frontend foundation (2 days)
- T G.1 `fast-worker`: Vite + TS strict + Tailwind scaffold per pin 8/9;
  React version decision executes here (**plan gate decision: React 19 +
  compiler, recharts/router compat verified in a spike commit first;
  fall back to 18 if the spike fails — record either way**).
- T G.2 `lead`: Tailwind theme from brand tokens + the two visual-identity
  primitives that define the language (cutout button, chip) — *lead:
  taste-bearing brand surface.*
- T G.3 `fast-worker`: remaining primitives (cards, nav, radix/ copy-ins:
  sheet, tooltip, popover, tabs, toast) skinned to the theme.
- T G.4 `codex`: OIDC adapter + dev-issuer login flow + token refresh +
  fetch-stream SSE client with reconnect cursor + mid-run expiry test;
  TanStack Query setup + the event-sourced run reducer (replay idempotence
  unit tests). **[verify-fast]**

### Phase H — views (3–4 days)
- T H.1 `fast-worker`: landing, sources, decision log, charts (demo-validated
  transcription against generated types + RETRO §2 holds per annex).
  **Dossier: no FWCI field** — retro-reconciliation confirmed it has no
  backing data (still a queued 018 seam); render only fields the read
  models actually serve (data-driven surfaces: hide, never fake).
- T H.2 `codex`: planning conversation (chips, plan disclosure), workspace
  run timeline (stage cards, activity feed, ephemeral ticks), check-in card
  incl. 024 confirm-gate delta render + parked/pending states.
- T H.3 `lead`: artefact/evidence-base view — annotation layer in prose,
  citation hover→click ladder, dossier slide-over content design — *lead:
  the product's core reading surface; taste + provenance-honesty judgment.*
- T H.4 `fast-worker`: state/error matrix implementation (per-view loading/
  empty/partial + the seven error surfaces) + `prefers-reduced-motion` +
  keyboard flows. **[FULL VERIFY]**

### Phase I — acceptance (1–2 days)
- T I.1 `fast-worker`: Playwright mock-mode journey; clean-clone acceptance
  script (README-driven: setup → migrate → dev issuer → both dev servers →
  mock mode).
- T I.2 `lead`: the pinned live check (browser-driven, two users/projects,
  park + restart + continuation + interrupt legs) — *lead: adjudicates live
  evidence; contract-pinned parameters.*
- T I.3 `lead`: verification.md complete; spec flow-back (`web-api.md` new
  system spec); deferred.md entries (cross-instance seam, font delivery,
  broker seam, non-goals); AGENTS.md phase note. **[FULL VERIFY — step-6
  exit, mandatory]**

## Sizing

Comparable to 024 (± — the runner core C is smaller than 024's lattice, the
frontend H is larger than anything prior). Estimate 14–18 build days across
executors; review stack should budget to the large-slice reality flagged in
the standing retro note (022/023/024 ran ~3× the routine pins) rather than
pretend otherwise.

## Live-check script (contract-pinned parameters)

Per contract § Acceptance: A = standard/Frequent, B = rapid/Unattended;
responsiveness < 2 s during dual execution; restart while A parked ∧ B
executing; A answered post-restart → continuation completes; B interrupted
honestly; rename/archive; landing truth. Wall time recorded as observation.

## Gate consolidation summary

Full `make verify`: T0.1 (baseline) · A.3 (scaffold) · B.3 (schema) · C.4
(runner core) · H.4 (pre-acceptance) · I.3 (step-6 exit). All other phase
exits gate on `make verify-fast` — D/E/F/G touch no schema and no existing
runner behaviour (new files + API package), argued per failure-log 2026-07-08
gate-consolidation rule.

## De-scope levers (pre-authorised order, owner stop-conditions apply)

1. Charts view (H.1 partial) — landing/evidence unaffected.
2. Decision-log expandable detail rows — list view stays.
3. Playwright journey depth (keep smoke, drop breadth).
4. Dossier secondary panes (tags/citing-claims) — status ladder + abstract stay.
Never de-scoped: parking/continuation correctness, auth, drift check,
annotation layer, state/error matrix.

## Rollback (Tier 4 requirement)

- The slice merges as one squash; revert restores the pre-hoist tree
  (hoist is pure `git mv` + path edits — revert-clean).
- Both migrations carry tested downgrades (incl. paused-rows disposition on
  downgrade: continuation events remain inert in event_log, harmless).
- The frontend + API are additive packages; no existing consumer changes
  except the runner parking seam, which is disposition-gated (CLI `block`
  path pin-tested byte-identical).

## Review-stack sizing (conversation C)

Tier 4: contract-verifier · /code-review medium (scoped angles: runner
parking/continuation, auth boundary, SSE race, migrations, API contract,
frontend store, views a11y) · security-auditor lane (auth/JWT/CORS/SSE/
scrubbing) · codex adversarial (family heterogeneity available again) ·
live-trace content lane (024 precedent: confirm-gate fidelity in the real
UI) · human deep review. Diff will be large (new frontend tree) — per-angle
diff scoping per review-economy memory; exclude generated client +
package-lock from review diffs.
