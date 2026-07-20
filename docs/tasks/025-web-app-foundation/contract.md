# Task contract: 025-web-app-foundation

> **Status:** drafted (rev 2, 2026-07-20) — awaiting owner approval.
> rev 2: `frontend/` (no dash — owner amendment superseding the
> deferred.md `front-end/` spelling) + § API design pins added after an
> `api-and-interface-design` pass (error envelope, pagination,
> resource-oriented run/check-in shapes, typed SSE variants); +
> pending-vs-history check-in invariant (owner observation: demo
> check-ins burst on replay — root cause is the demo store rendering
> replayed pauses as fresh arrivals; the runner blocks per pause, so
> simultaneous pending check-ins are impossible backend-side); +
> RETRO.md reframed as point-in-time evidence with a plan-phase
> reconciliation sweep (owner, 2026-07-20: RETRO is out of date —
> much was attended to in 019–024); + frontend-architecture fold-ins
> (owner-supplied external notes, 2026-07-20): TanStack Query on the
> deps list, React version 🟡 to the plan gate, URL-addressable UI
> state pinned. Rejected from the same notes with reasons: offline/
> sync-engine (server-authoritative product), xstate (lifecycle state
> machine is server-side), Cloudflare/Vercel (AWS is pinned), full
> design system (component primitives suffice).
> rev 1: initial draft.
> Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ ·
> ADR: _due (Tier 4) — API architecture + auth seam + hoist; number at step 4_.
> Contract-stage adversarial lane (Tier 3+ standard): attempt `codex-rescue`
> first; on credit failure fall to deep-reasoner per the
> codex-exhaustion-fallback rule (codex verified exhausted 2026-07-16 ×2 —
> a returned job-id is not proof of credits).
>
> **Owner pins already made (context, not targets):**
> - One consolidated slice — API + frontend together (owner, 2026-07-20).
> - Auth = **AWS Cognito** (owner, 2026-07-20), landing only when the CDK
>   `infra/` code exists — this slice ships the Cognito-shaped seam, not
>   the user pool.
> - The demo took shortcuts to avoid backend changes (registry-only
>   delete/rename; check-ins on the in-memory bus) — this slice builds
>   those properly (owner, 2026-07-20).

## Goal

Replace the throwaway `demo-live-run` stack with the production web
application: an industry-standard API over the real backend, and the
frontend the demo validated, built on durable substrates end-to-end. The
organising principle: **the durable record (Postgres) is the only source
of truth the web app reads; every mutation goes through the real backend
seams; one schema generates both ends of the contract.** Seven strands:

1. **Monorepo hoist.** The Python project (pyproject.toml, src/, tests/,
   alembic/, Makefile) hoists to `backend/`; the new frontend lands at
   `frontend/`; `infra/` is reserved for the CDK (pinned owner layout
   intent, deferred.md 2026-07-14 — "do it in the slice that brings the
   frontend in"). Import-neutral (`policy_atlas` name unchanged);
   the cost is tooling paths only (CI, Docker contexts, doc links).
2. **Production API.** `policy_atlas/api/` — FastAPI, versioned under
   `/api/v1`, REST + SSE. Schema-first: Pydantic response/request models
   are the single contract; OpenAPI is generated from them; the
   TypeScript client is generated from the OpenAPI document; CI fails on
   drift. (Demo evidence: mock/live contract divergence was the #1 bug
   class — RETRO §3.) `demo/API.md` is the validated *shape* precedent;
   endpoints are re-derived from it deliberately, not copied.
3. **Project lifecycle done properly.** Schema migration: `project` gains
   `name`, `question`, lifecycle `status`, `updated_at`, soft-delete
   (`archived_at`), and nullable `owner_user_id` (Cognito `sub`, text).
   Rename and delete become real API semantics against Postgres; the
   demo's `projects.json` sidecar registry has no successor. 🟡 Delete =
   **archive** (soft-delete: hidden from listings, rows retained — the
   audit/FOI/portability standing constraint applies to the durable
   record); hard purge is a deferred seam, not shipped.
4. **Steering and check-ins on the durable substrate.** Pending
   check-ins become an API resource derived from Postgres (024's
   steering events + `steering_history` projection — built for exactly
   this consumer); answers POST through the real steering seam
   (Continue / Adjust / FreeText→router confirm / authored picks /
   Abort, per 024 vocabulary); decision history is served from
   `steering_history`, never from transport memory. The check-in
   *content of record* is the deterministic steering render; the demo's
   LLM prose wrap (`text`) is dropped — no new prompt surfaces in this
   slice (🟡 see Model route). **Pending is derived, arrival is live**
   (owner observation, 2026-07-20 — demo check-ins burst on replay):
   pending = a `steering.pause` without its decision, at most one per
   active run by construction (the runner blocks); replayed pauses that
   have decisions render as time/stage-anchored *history*, never as
   newly-pending cards — only the current blocking pause presents as
   pending, at its chain position.
5. **Durable event transport.** SSE per project with backlog replay
   served from `event_log` (+ run/plan state), not an in-memory bus; the
   frontend store rebuilds idempotently from replay alone (demo-proven
   resilience model, now on the durable substrate — survives server
   restart mid-run *including* a pending check-in). Liveness ticks that
   have no durable home (search/fetch progress) flow on a clearly
   labelled ephemeral channel — best-effort, never state-bearing. 🟡 A
   fully *designed* component-progress protocol (RETRO §4) is out; this
   slice ships stage-grain durable events + the minimal ephemeral tick
   channel, and the seam is recorded in deferred.md.
6. **Auth seam, Cognito-shaped.** OIDC/JWT bearer verification at the
   API boundary (issuer/audience/JWKS config), `user_id` = token `sub`
   threaded into project ownership and steering attribution
   (`decided_by` exists since 024). Local/dev runs use a dev issuer
   (signed JWTs from a dev keypair; visibly non-production). The Cognito
   user pool + CDK land in the later `infra/` slice; this slice must
   require **zero auth-code changes** at that point — config only.
   🟡 No `users` table in 025: verified claims are the identity; a
   profile table is a 026+ seam (co-pilot transcript store will need
   per-user rows and can bring it).
7. **The frontend.** `frontend/` on the demo-validated stack (React 18,
   TypeScript strict, Vite, Tailwind, recharts, react-router) and the
   demo-validated views: landing (project cards incl. paused state),
   planning conversation (plan disclosure, suggestion chips), workspace
   run view (stage timeline, activity feed, check-in cards with the 024
   confirm-gate rendering), evidence base/artefact (annotation layer IN
   the prose, citation hover→click ladder, source dossier slide-over),
   findings, sources, decision log, landscape charts. The RETRO §2
   product decisions are **binding unless superseded by as-built
   019–024 behaviour** (code wins on conflict): locked vocabulary,
   labels never raw numbers, data-driven surfaces (hide, never fake),
   one shared dossier, motion budget with `prefers-reduced-motion`. The
   store consumes only the generated client + SSE replay. **UI state
   that names a thing is URL-addressable**: the source dossier, active
   view, and filters live in the route/search params (typed), so a
   dossier or filtered view is deep-linkable and refresh-safe —
   library choice (router loaders vs nuqs) at plan time. **Design
   sources are two layers** (owner, 2026-07-20): the *brand layer* is
   the comms-team shared component library (Figma; distilled in-repo as
   `docs/specs/sources/evidence-base-ux/nesta-brand-tokens.md` +
   `hifi.css`) → Tailwind theme tokens (palette, type hierarchy, the
   0-radius/45°-cutout button language, nav states); the *app layer* is
   a small owned set of component primitives (chips, cards, drawer,
   check-in card, table rows, state grammar) built in-slice as ordinary
   code — **no standalone design-system package**. The wireframe pack
   (`evidence-base-wireframes.html` + screenshots + the handoff's §7
   locked decisions) is design reference under the same point-in-time
   rule as RETRO.md: the handoff predates 019–024 (e.g. Quick/Deep is
   superseded by the two-axis effort/depth gradation) — as-built code
   wins on conflict. 🟡 **Fonts:** Averta/Zosia are licensed, not
   web-free — web-deployment licensing needs comms confirmation; until
   then the documented fallback stack ships (Mulish/Manrope + geometric
   display) and the tracked font binaries question (assets.md flag,
   2026-06-22) is resolved at this gate, not silently inherited.

## Deliverable

PR landing:

- The hoist: `backend/` (whole Python project) + `frontend/` scaffold +
  `infra/.gitkeep`; CI, Docker, Makefile and doc paths updated; full
  suite green post-hoist.
- `policy_atlas/api/`: FastAPI app — routers (projects, planning turns,
  runs, check-ins, read models, SSE), Pydantic contract models, read
  models rewritten over the real schema (the demo's `readmodels.py` is
  evidence, not source), auth dependency (JWT verification + dev
  issuer), lifecycle semantics, OpenAPI export command.
- Generated TypeScript client + the drift check wired into `make verify`
  / CI (regenerate → diff → fail on mismatch).
- Alembic migration for the `project` lifecycle columns (+ downgrade).
- SSE replay from `event_log`: replay reader + live tail + ephemeral
  tick channel; documented event vocabulary (successor to `demo/API.md`
  § SSE, committed as `docs/specs/system/web-api.md` — new system spec,
  the API's living intent).
- `frontend/` app: the views above, generated-client store with
  idempotent replay rebuild, mock mode implementing the same generated
  interface, Playwright journey test (mock mode) + unit tests (vitest).
- `make verify` extended: frontend typecheck · lint · test · build +
  OpenAPI/client drift check; CI updated for the monorepo layout.
- Tests: SSE replay idempotence (restart simulation), steering
  check-in round-trip through the real seam, **resolved-pause replay
  (a decided pause never re-presents as pending; pending endpoint
  returns exactly the current blocking pause or nothing)**, project
  lifecycle
  (rename persists; archive hides + retains; 409 while running),
  authz fail-closed (401/403 incl. cross-user), migration up/down.
- ADR (API architecture + auth seam + hoist + delete semantics) +
  spec flow-back (`web-api.md` new; product.md untouched) + deferred.md
  seams + `verification.md` with the pinned live check.

## API design pins

Interface decisions binding strand 2, reviewable at this gate
(`api-and-interface-design` pass, 2026-07-20):

- **Resource-oriented, no verbs in URLs.** The demo's action endpoints
  are re-shaped: *runs are resources* — `POST /projects/{id}/runs`
  replaces `/start` (a run row is created; 409 while one is active) and
  aligns the API with `capability_run` as the walk identity, so
  multi-run/multi-question is a listing change, not a reshape. Planning
  turns are a sub-resource (`POST /projects/{id}/planning-turns`
  replaces `/chat`). A check-in answer is created as its response
  sub-resource (`POST .../check-ins/{id}/response`, one per check-in —
  409 on double-answer).
- **One error envelope.** Every non-2xx returns
  `{error: {code, message, details?}}` — machine-readable `code`,
  human-readable `message`; mapping pinned: 400 malformed · 401
  unauthenticated · 403 cross-user · 404 unknown/archived · 409
  conflict (run active, already answered) · 422 validation (Pydantic
  detail in `details`) · 500 opaque (never leaks internals). Never
  mixed shapes; error *text* is not contract, `code` is.
- **Pagination from day one** on unbounded lists (evidence ~200+,
  findings ~400+ at real scale; projects, decisions): one envelope
  `{data, pagination: {page, page_size, total_items}}`, filters as
  query params. Bounded structural reads (plan, funnel, landscape,
  artefact) stay whole-object.
- **Partial updates.** `PATCH` semantics everywhere (rename = PATCH
  with only `name`); archive is idempotent.
- **One naming convention.** snake_case JSON end-to-end (Pydantic-native;
  deliberate deviation from camelCase-on-the-wire — one convention,
  zero rename middleware, matches the existing event vocabulary);
  plural-noun paths; string-literal lower_snake enums.
- **Typed variants.** SSE event types and check-in kinds are
  discriminated unions in the same contract source (Pydantic tagged
  unions exported into the OpenAPI components), so the generated client
  narrows on `type`/`kind` — hand-rolled event typing is a rubric
  failure.
- **Hyrum hygiene.** Internal component names appear only as the pinned
  stable `stage` keys (contract vocabulary); labels/blurbs are
  server-supplied presentation and may change; nothing else internal
  (module names, model ids, raw payload keys) is observable.
- **Additive evolution, one version.** `/api/v1` is a namespace, not
  versioning machinery: new fields optional, removals via deprecation
  in `web-api.md` — no parallel-version support.

## Read first

- `demo/API.md` and `demo/RETRO.md` (branch `origin/demo-live-run`) —
  **read as point-in-time evidence (2026-07-09/10, pre-019–024), not as
  a to-do list** (owner, 2026-07-20: much of it has since been attended
  to — e.g. depth gating → 019, extraction prompt rules → 020's
  `extract_iof_v7`, synthesis voice → 022's `synthesise_section_v7`,
  facet-cap scale → 022's clustering engine, steering vocabulary → 024).
  §2 (product/UX decisions) is the validated UX baseline, read against
  the as-built 024 surfaces — code wins on conflict. §3's
  contract-discipline lesson (schema-first) stands. §§4–5 engineering
  observations are historical: **the plan includes a RETRO
  reconciliation sweep** classifying every item as discharged (naming
  the slice) · still-open (in this slice or deferred.md) · superseded —
  nothing from RETRO enters the build unverified against dev.
- [product.md](../../specs/product.md) — the workspace boundary; the EB
  journey the UI serves; progressive disclosure.
- [execution-orchestration.md](../../specs/system/execution-orchestration.md)
  — steering modes, decider dial, confirm gate (024 as-built).
- [data-model.md](../../specs/system/data-model.md) + `core/schema.py` —
  the real tables the read models project (note: `project` is bare
  today: `project_id` + `created_at` only).
- `docs/specs/sources/evidence-base-ux/` — the wireframe pack: handoff
  (§7 locked decisions), brand tokens, `hifi.css`, 11 screenshots —
  point-in-time design reference (see strand 7 caveat); the comms
  Figma shared component library is its upstream (access via owner).
- 024's `steering_history` projection + steering event vocabulary
  (`docs/tasks/024-steering-surface/` + the as-built code — code wins).
- deferred.md entries: monorepo hoist (2026-07-14) · per-query source
  provenance (2026-07-15) · transcript re-home to 025→026 (2026-07-16) ·
  024 review-stack seams touching the front-end.

## Scope / Out of scope

- **In:** everything under Deliverable; the four `demo-live-run`
  carry-forward candidates (search liveness log lines, prompt-rule and
  voice edits) **only if** verified still-unlanded on dev — check, don't
  assume; per-query source provenance (deferred.md carry-back) **if** the
  evidence/search surfaces need it — 🟡 else it stays deferred.
- **Out:** co-pilot Q&A + transcript store (**026** — needs this slice's
  auth/user identity); CDK `infra/` + the Cognito user pool + Bedrock;
  comments/versioning/catch-me-up surfaces (v3.0 product intent but
  ❓ **own slice** — real design work, nothing demo-validated; API
  shapes must not foreclose them); multi-question workspace UI
  (workspace-cluster slice; the API keys runs by `capability_run` and
  does not hard-code one-question-per-project into v1 shapes beyond the
  existing `project.question` field); RBAC/artefact-scoped visibility
  and per-item sensitivity (deferred per product.md); LLM narration
  prose and any new prompt surface; hard-delete/purge; the designed
  component-progress protocol (seam recorded).
- The `demo-live-run` branch itself stays untouched and unmerged; after
  this slice it is historical evidence only.

## Constraints & approval gates

Every gate below is **named for approval at this contract's 🛑** — none
may be re-decided silently mid-build:

- **Schema:** the `project` migration (columns above). No other table
  changes.
- **Auth/tenancy:** OIDC/JWT boundary + dev issuer as described; every
  data route authenticated; ownership = `owner_user_id` scoping on
  listings and access (❓ single-tenant team visibility vs strict
  per-owner — owner call; recommend **strict per-owner now**, sharing is
  a workspace-cluster concern).
- **Dependencies (Python):** `fastapi`, `uvicorn`, JWT verification lib
  (recommend `pyjwt` + `cryptography`), `httpx` already present;
  SSE via Starlette natively (no `sse-starlette` unless needed).
- **Dependencies (Node — new ecosystem):** the demo-validated stack
  pinned above + `@tanstack/react-query` (server-state layer over the
  generated client for read models — fetching/caching/invalidation on
  `stage.completed`; the event-sourced reducer remains only for SSE
  run/thread state) + `openapi-typescript` (client gen), `vitest`,
  `@playwright/test`. Package manager: **npm** (demo precedent).
  🟡 React version is a **plan-gate decision**: 19 + compiler
  (drops manual memoisation) vs the demo's 18 — the demo validated the
  views, not the version; recharts/router compat is the plan-time check.
- **CI:** monorepo path updates + frontend lane + drift check.
- **Public interface:** the `/api/v1` surface itself — documented in
  `web-api.md`; additive-only evolution intent.
- **Scaffold:** the hoist + `frontend/`.
- **Egress:** none new — the API serves the existing chain; product
  egress (search/model) is unchanged and stays behind approved seams.
- The API layer must not import demo code; `demo/` never merges.
- No component/runner behaviour changes except where a strand names one
  (steering answers through the existing seam is wiring, not behaviour).

## Public / private boundary

- The API is authenticated end-to-end; it may serve quotes, chunk
  context and provenance to logged-in users (that *is* the product).
  Nothing unauthenticated beyond liveness/health.
- No raw source text, traces or credentials in the repo; frontend
  fixtures/mocks follow the sanitized-fixtures policy (sanitized API
  records; openly-licensed real documents permitted).
- No secrets in the frontend bundle or its env files; CORS locked to the
  app origin; dev issuer keys are dev-only artifacts, never committed
  private keys with production semantics.

## Model route

**No new prompt-bearing surfaces.** The API fronts the existing seams:
planning turns via the 024 `orchestrator_v1` planning moment; router
confirm + watch as built; synthesis chain untouched. The demo's LLM
narration/check-in prose wrap is dropped, not ported (🟡 if the owner
wants narration in the product it is a *named future slice* with a
lead-authored prompt surface — not smuggled in here). Inference route
unchanged (OpenAI under approved controls → Bedrock seam).

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves** — no label/type/flag that doesn't change v3.0 behaviour
  (no inert `users` table, no speculative RBAC columns).
- **Flag, don't drop** — below-bar material flagged, never hidden; UI renders
  degraded/failed states honestly (RETRO: data-driven surfaces hide rather than fake).
- **Honest absence** — coverage claims carry their base; the composed coverage sentence
  (stop condition + adequacy in one line) is server-side.
- Deferred seams recorded in [docs/deferred.md](../../deferred.md), not silently omitted.

## Stop conditions

Halt and escalate when: any approval gate above is hit beyond its approved
shape; the steering seam needs a runner/behaviour change beyond wiring; a
schema change beyond the `project` migration is needed; scope tempts
comments/versioning/RBAC/narration; or the turn/token budget is spent.
Report the blocker; don't push through.

## Acceptance checks

- `make verify` green — extended: okf-validate · backend test · mypy ·
  ruff · build **+ frontend typecheck · lint · vitest · build + OpenAPI/
  client drift check** — all from the hoisted layout.
- Deterministic tests (named under Deliverable): replay idempotence ·
  steering round-trip · lifecycle semantics · authz fail-closed ·
  migration up/down. No AI-judge evals in this slice.
- **Live-check pin (contract-time, per failure-log 2026-07-08):** one
  scoped live run driven through the real browser UI — create project →
  planning conversation (2–3 turns) → start (rapid/standard effort) →
  answer one check-in in the UI (incl. one free-text steer through the
  confirm gate) → **kill and restart the API server mid-run** → UI
  rebuilds from replay and the pending state survives → completion →
  artefact renders with annotation layer + dossier → rename → archive →
  landing reflects both. Estimated wall ≈ 15–25 min. **No full live
  deep-run e2e** — the suite's stub full-chain test covers chain
  integrity. Playwright mock-mode journey covers the UI flows that the
  live pin doesn't exercise.
- Browser checks: keyboard navigation on the check-in card and dossier;
  `prefers-reduced-motion` honoured; no horizontal body scroll at
  1280/768 widths.

## Verification evidence expected

`verification.md` with: gate outputs (hoisted-layout verify), the live
check as a narrated log with timestamps + the restart moment, drift-check
proof (mutate a Pydantic model → CI-equivalent failure), authz matrix
results, migration up/down output, screenshots of the demo-validated
surfaces, diff summary, public-safety confirmation, known gaps +
deferred.md pointers.

## Risk tier & review focus

**Tier 4** — scaffold (hoist + new frontend ecosystem) + public API +
schema migration + auth boundary + deps + CI. Requires: human-approved
plan · ADR · rollback plan (plan must carry: squash-revert restores
pre-hoist layout; migration downgrade tested; frontend is additive) ·
security-auditor lane (auth boundary, JWT verification, CORS, SSE
authn) · adversarial review at contract + plan + code · human deep
review.

Review focus: auth fail-closed everywhere · contract drift (the one-schema
property actually enforced, not aspirational) · replay correctness
(idempotence, ordering, the pending-check-in edge) · lifecycle semantics
vs the audit constraint · hoist completeness (CI/Docker/doc paths) ·
scope creep toward 026/narration/comments · over-abstraction (no
speculative API versioning machinery, no state-management framework the
store doesn't need).
