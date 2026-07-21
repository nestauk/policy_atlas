# Task contract: 025-web-app-foundation

> **Status:** approved 2026-07-21 · owner ("Approved, run the
> adversarial review") — **adversarial lane DONE same day**
> (codex-rescue, job task-mrtxsig7-v7s1e2, family heterogeneity
> achieved; 13 MAJOR + 7 minor findings, ALL adjudicated in — see
> § Adversarial adjudication addenda + rev history). **Gate REOPENED
> on two items needing owner re-approval:** (1) schema-gate expansion
> — the `capability_run` status-constraint migration
> (paused/interrupted, finding 1); (2) deps additions —
> `openapi-fetch` (finding 14) + a frontend OIDC adapter
> (`oidc-client-ts`/`react-oidc-context`, finding 9). All other
> findings folded as non-material amendments. **Reopened gate items
> RE-APPROVED 2026-07-21 · owner** ("Happy to agree with those gates")
> — capability_run status migration + openapi-fetch + frontend OIDC
> adapter are in the approved scope. Contract FINAL for planning.
> Plan approved (before implementation): _pending_.
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
> Deferred.md sweep fold-ins (2026-07-20, full-file sweep): DB-level
> one-active-run dispatch guard (008 pre-registered) · citation-context
> clamp on chunk-context (008, named web-app consumer) · display-string
> scrub at render (024 security lane, named 025) · steering OUT-list as
> a UI fence + confirm-gate delta render load-bearing · honest
> interruption semantics (no resume engine — live-check pin corrected:
> the durable record survives a restart, the walk does not) ·
> share/export + confidence badge made explicit in Out · direct
> plan-pane editing re-deferred + upload UI out (**owner-settled
> 2026-07-20**) · B2′ relevance-emphasis clarified as in-scope steering
> (distinct from the vetter/judge fence, ADR 0023) + findings read
> model carries the priority|normal marks. Also considered and
> rejected (owner question, 2026-07-20): **Astryx** (Meta's design
> system, beta v0.1.6) — pre-1.0 API under a Tier-4 foundation,
> StyleX collides with the pinned Tailwind stack, Nesta's distinctive
> brand components need custom work regardless, and the app-specific
> surfaces (annotation spans, check-in cards, dossier) exist in no
> library; revisit at the workspace-cluster slice if the owned
> primitive set sprawls or a second app appears. FastAPI-digest
> adjudication (2026-07-21, deep-reasoner over the owner-supplied
> 89-page source → fastapi-guidelines-digest.md; all four §1 findings
> accepted): cross-owner access flipped 403→**404** (BOLA — existence
> never confirmed; 403 reserved for future role failures) · runs
> pinned **off the event loop** (mechanism + concurrent-run bound at
> plan time; responsiveness probe added to the live check) ·
> **one-instance/one-worker deployment posture** pinned (process-local
> pause/tail; LISTEN/NOTIFY cross-instance seam → deferred.md) ·
> **server-enforced page_size cap** added (offset kept deliberately;
> cursor recorded as the additive migration path). Concurrent-users
> pin (owner, 2026-07-21): per-project run guard confirmed the right
> grain; added — chain thread-safety audit under concurrent walks as
> a named plan task (module-global per-run config banned) · run bound
> counts paused walks, 409 at capacity · planner sessions
> process-local with honest draft loss (transcripts are 026) ·
> shared-rate-limit fairness recorded as v1 non-goal · two-user/
> two-project leg added to the live check + rubric item 18.
> **Parked pauses** (owner challenge, 2026-07-21 — pauses last minutes
> to days; holding a thread is wrong): blocking-pause model replaced —
> attended pauses park the walk (thread ends, durable `paused`
> status); the answer dispatches a boundary continuation walk
> rehydrated from the durable record (NOT the deferred resume engine —
> mid-component checkpointing stays out; 024 segment re-entry is the
> precedent). Parked runs survive restarts by construction;
> interruption honesty now covers executing walks only; run bound
> counts executing walks only. Live check restructured (restart while
> A parked + B executing; answer after restart; continuation
> completes). Build sizing note: adds runner continuation machinery —
> named, accepted. Context-parity pin (owner question, 2026-07-21 —
> does parking pre-026 lose orchestrator context?): no by design
> (orchestrator context is composed per moment from the durable
> record; 018 forbids provider-side sessions; ephemeral planner prose
> is deliberately non-quality-bearing per plan-as-contract +
> product.md) — now enforced by a continuation context-parity test;
> quality-bearing state found only in walk memory = stop-condition
> finding. Component-primitives decision (owner question, 2026-07-21):
> app-layer primitives split visual-identity (hand-built from brand
> tokens) vs behaviour-bearing (shadcn-style copy-in over Radix
> headless primitives, Tailwind-skinned) — owned code either way, no
> component-library dependency; MUI/Chakra/Mantine/daisyUI rejected
> with reasons in the design-sources pin; deps list gains scoped
> `@radix-ui/*` + cva/tailwind-merge.
> **Adversarial adjudication (2026-07-21, codex lane, 20/20
> accepted):** MAJORs — capability_run status migration = explicit
> gate expansion (1) · durable continuation.requested + atomic claim +
> startup drainer (2+17) · context parity respecified as an enumerated
> continuation-state reducer over the walk loop's real in-memory state
> (3) · rubric 18 vs live check reconciled (4) · per-project lock
> serialises answers, barrier test (5) · project.status = lifecycle
> only, run state derived (6) · fetch-based SSE auth + own cursor + no
> query-string tokens + mid-run expiry test (8) · frontend OIDC
> adapter dep, "config only" split backend-conformance-test /
> frontend-config (9+20) · migration backfill + NULL-owner rows
> intentionally inaccessible + populated-DB migration test (10) ·
> atomic backlog→tail cutoff + race test (11) · openapi-fetch added —
> types alone are not a client (14) · live-check parameters pinned,
> wall time demoted to observation (19). minors — planner-prose claim
> narrowed to not-execution-bearing (7) · transactional rename/archive
> audit events (12) · state/error matrix + clean-clone acceptance (13)
> · planner turn lock + 409 (15) · row lock over partial index (16) ·
> rubric greps made rename-aware/allowlisted (18).
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
   **`project.status` is lifecycle only — `active | archived`**
   (finding 6): run/walk state lives on `capability_run.status` and is
   never cached onto the project row; the landing card's
   running/paused/complete presentation is a read model derived from
   the latest capability run. **Migration policy for existing rows**
   (finding 10): expand → backfill (`name` from the approved plan's
   title else "Untitled project", `question` from the plan,
   `status=active`) → constrain; pre-existing rows keep
   `owner_user_id NULL` and are **intentionally inaccessible via the
   API** under strict per-owner scoping (documented DB-level recovery;
   the dev DB's two live-run projects are the known case) — and the
   migration is tested against a populated pre-025 database, not only
   an empty one. **Rename and archive emit transactional audit
   events** (`project.renamed` / `project.archived`, actor +
   timestamp, same transaction as the mutation — finding 12); archive
   is idempotent.
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
   pending, at its chain position. The UI renders **only
   server-supplied steering options** (demo rule, kept) and must not
   expose or tease the steer classes deferred.md rules OUT (vetting/
   judge steering — i.e. dialling the verifier; **distinct from the B2′
   relevance-emphasis channel, which is in-scope steering**: it
   annotates post-vetting survivors `priority | normal` and never
   instructs the vetter, ADR 0023 — mid-component pause, free-text
   replanning, query-set pre-approval); the router confirm gate renders
   the compiled deltas
   (the 024 review's fidelity mitigation — load-bearing, since ~half of
   live free-text steers mis-compiled before it).
5. **Durable event transport.** SSE per project with backlog replay
   served from `event_log` (+ run/plan state), not an in-memory bus; the
   frontend store rebuilds idempotently from replay alone (demo-proven
   resilience model, now on the durable substrate — survives server
   restart mid-run *including* a pending check-in). **Parked pauses,
   no held threads** (owner, 2026-07-21 — a pause can last minutes to
   days; the delegation postures are designed for the user going
   away): at an attended pause the walk **parks** — the worker thread
   ends, the run's durable status becomes `paused`, nothing in-process
   holds it. The check-in answer dispatches a **boundary continuation
   walk** that rehydrates from the durable record (per-component
   commits + the 024 steering record make the component boundary a
   natural checkpoint; 024's segment re-entry is the mechanical
   precedent) and proceeds from the next component. This is *not* the
   deferred resume engine — mid-component checkpointing stays out
   (017 seam); a walk killed mid-component is still interrupted, never
   resumed. **Honest interruption** applies to executing walks only:
   on startup the orphan sweep marks runs that died mid-execution
   `interrupted`; **parked runs survive restarts by construction**.
   Continuation is **durable before it is executable** (findings 2 +
   17): the answer and a `continuation.requested` event commit in one
   transaction; a worker claims it atomically (the per-project lock)
   and marks it executing; a startup **drainer** redispatches
   requested-but-unclaimed continuations, so a crash between answer
   and execution loses nothing — crash tests on both sides of the
   claim are named deliverables. Answers are always accepted;
   execution may queue at the bound. **Schema consequence, gate item
   (finding 1):** `paused`/`interrupted` violate `capability_run`'s
   current status check constraint — the approved schema scope
   expands to a second migration (the `capability_run` status
   constraint, up/down tested with paused rows present; component-run
   disposition named in the plan). Continuation dispatch is a
   **preserved seam**: broker-backed
   workers (Celery/RQ) stay out of this slice — boundary durability is
   Postgres's job, not the task runner's; separate workers would
   re-open the deferred cross-process tail/unblock seam; broker infra
   belongs to the infra slice — but parked segments are queue-shaped,
   so workers slot in behind this seam later without a reshape
   (digest §4, updated). **Context parity is a tested property, not an assumption**
   (owner question, 2026-07-21; sharpened by adversarial finding 3 —
   the walk loop carries substantial in-memory state: amended
   plan/chain, pending overlays, successful/attempted run maps,
   blocked discretionary components, accumulated outcomes/flags): the
   continuation is specified as a **continuation-state reducer** — an
   enumerated mapping of *every* walk-loop field to its durable source
   and ordering rule, drafted at plan time from `runner.py` as-built,
   with ambiguity handling named per field. The parity test asserts
   identical composed context between an unbroken and a
   parked-and-continued walk across the full surface: pause header,
   digest, P2–P4 bundles, canonical + authored options, router
   surface, downstream run references, overlays, and collation —
   not an unspecified "context". The known unwatched re-presentation
   seam (deferred.md, 024 build) is inherited, not widened. Anything quality-bearing found living only in walk
   memory during the build is a **stop-condition finding** (it would
   violate plan-as-contract and "project memory is structured state,
   not a transcript" — product.md), not something to quietly stuff
   into the continuation. **Runs never execute on the event
   loop** (digest §1.2 — a blocking walk would starve SSE, health and
   every other project): the run executes in offloaded worker
   threads/executors; the plan pins the mechanism and a concurrent-run
   bound, and the live check probes API responsiveness mid-run. The
   orphan sweep is idempotent and concurrency-guarded (it fires per
   process start). **Deployment posture: one API instance, one worker
   process, pinned for this slice** (digest §1.3 — pause-unblocking and
   live tail are process-local; durable replay covers reconstruction,
   not live delivery): cross-instance steering/live-tail (Postgres
   LISTEN/NOTIFY or pub-sub) is a named deferred seam for the infra
   slice, recorded in deferred.md. **Concurrent users on different
   projects are first-class** (owner, 2026-07-21): the run guard is
   per-project by design, and the plan carries (a) a **thread-safety
   audit of the chain under concurrent walks** — components were built
   one-walk-at-a-time; shared clients/caches/tracing contexts audited,
   and per-run config is parameter-passed, never module-global (the
   demo's monkeypatch pattern is banned); (b) the concurrent-run bound
   counts **executing** walks only — parked runs hold no slot (see the
   parked-pauses pin) — and at-bound *new-run* dispatch returns an
   honest 409 capacity envelope (continuations queue on the executor
   instead); broader queueing is deferred; (c) **planning-conversation state is
   process-local per project** — the approved plan object persists
   durably, an in-flight draft conversation is lost on restart honestly
   (transcript persistence is 026); (d) provider rate limits are shared
   across concurrent runs — the run bound is the v1 fairness
   mitigation, per-run fairness is a recorded non-goal. Liveness ticks
   that
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
7. **The frontend.** `frontend/` on the demo-validated stack (React —
   version resolved at the plan gate: **19 + compiler**; charts on
   **recharts 3.x**, superseding the demo's 2.15 by owner challenge
   2026-07-21,
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
   a small owned set of component primitives built in-slice as ordinary
   code — **no standalone design-system package** — in two kinds
   (owner direction, 2026-07-21): **visual-identity components**
   (45°-cutout buttons, chips, cards, nav) hand-built from the brand
   tokens/`hifi.css` — no library shares Nesta's language; and
   **behaviour-bearing components** (dossier sheet/dialog,
   tooltip/popover for the citation ladder, dropdowns, tabs, toasts)
   built **shadcn-style: component source copied into the repo over
   Radix headless primitives**, Tailwind-skinned with our tokens —
   owned code with library-grade keyboard/focus/ARIA behaviour (the
   rubric's accessibility floor rides on these). shadcn is a dev-time
   generator, not a runtime dependency. MUI/Chakra/Mantine rejected
   (second styling system + brand fight); daisyUI rejected (styles
   without behaviour — the inverse of what we lack). The wireframe pack
   (`evidence-base-wireframes.html` + screenshots + the handoff's §7
   locked decisions) is design reference under the same point-in-time
   rule as RETRO.md: the handoff predates 019–024 (e.g. Quick/Deep is
   superseded by the two-axis effort/depth gradation) — as-built code
   wins on conflict. 🟡 **Fonts:** Averta/Zosia are licensed, not
   web-free — web-deployment licensing needs comms confirmation; until
   then the documented fallback stack ships (Mulish/Manrope + geometric
   display). **Settled (owner, 2026-07-20; licence confirmed with comms
   2026-07-21):** Averta and Zosia are **licensed for use in the web
   app** — the one hard rule is that **font binaries are never
   committed to this open-source repo**. Locally they live untracked
   (gitignored) and load via `@font-face` when present; the frontend
   must render correctly on the fallback stack when absent (fresh
   clones, CI). A **CI guard asserts no font binaries are tracked**
   (`git ls-files` grep for font extensions — wired into `make
   verify`, so an accidental `git add -f` fails the gate). The
   *delivery mechanism* for the deployed webapp (serving the licensed
   files from outside the repo — e.g. private bucket at build/deploy
   time) is an **infra-slice seam** (deferred.md entry ships with this
   slice) — now purely mechanics, no licensing question remains.

## Deliverable

PR landing:

- The hoist: `backend/` (whole Python project) + `frontend/` scaffold +
  `infra/.gitkeep`; CI, Docker, Makefile and doc paths updated; full
  suite green post-hoist.
- `policy_atlas/api/`: FastAPI app — routers (projects, planning turns,
  runs, check-ins, read models, SSE), Pydantic contract models, read
  models rewritten over the real schema (the demo's `readmodels.py` is
  evidence, not source; the chunk-context read model carries the
  **citation-context character clamp** windowed around the cited span —
  discharges the 008 seam's named web-app consumer; the findings read
  model surfaces the run-scoped B2′ relevance marks — `priority |
  normal` — when the run carries them, and the P4 check-in render's
  priority-counts-per-group passes through), auth dependency
  (JWT verification + dev issuer), lifecycle semantics, the startup
  **orphan-run sweep** (in-flight runs marked `interrupted`), OpenAPI
  export command.
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
- Tests: SSE replay idempotence (restart simulation) + the
  backlog→tail race-injected test, steering check-in round-trip
  through the real seam, the double-answer barrier test (one decision
  + one 409), continuation crash tests (both sides of the claim) +
  startup-drainer redispatch, **continuation context
  parity per the reducer spec (unbroken walk vs parked-and-continued
  walk, full surface: header/digest/bundles/options/router/
  references/overlays/collation)**, the auth provider-conformance
  suite (two asymmetric issuers, key rotation) + mid-run token expiry,
  **resolved-pause replay
  (a decided pause never re-presents as pending; pending endpoint
  returns exactly the current blocking pause or nothing)**, project
  lifecycle
  (rename persists; archive hides + retains; 409 while running),
  authz fail-closed (401 unauthenticated; cross-owner reads/writes
  return 404, asserted indistinguishable from absent), migration
  up/down, orphan-sweep idempotence (double boot = no double events).
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
  409 on double-answer). **One active run per project is enforced in
  Postgres at dispatch** via a per-project row lock (`SELECT … FOR
  UPDATE` on the `project` row, or an advisory lock keyed on it —
  adversarial finding 16: a partial unique index would be a second
  schema change and a worse fit), not in app memory — the API's 409 is
  backed by the DB guard. **The same per-project serialization
  primitive guards check-in answers and continuation claims**
  (finding 5: event append assumes one writer per project; two
  simultaneous answer POSTs must yield exactly one decision + one
  clean 409, proven by a barrier test — never a 500 or a duplicate
  continuation). Discharges the pre-registered 008 seam (deferred.md
  "Concurrent-run write guard", named for the web-app /
  durable-execution slice).
- **One error envelope.** Every non-2xx returns
  `{error: {code, message, details?}}` — machine-readable `code`,
  human-readable `message`; mapping pinned: 400 malformed · 401
  unauthenticated · **404 unknown/archived/cross-owner** (another
  user's resource is indistinguishable from absent — BOLA guidance,
  digest §1.1; 403 is reserved for role/permission failures within an
  owned scope, of which this slice has none) · 409
  conflict (run active, already answered) · 422 validation (Pydantic
  detail in `details`) · 500 opaque (never leaks internals). Never
  mixed shapes; error *text* is not contract, `code` is.
- **Pagination from day one** on unbounded lists (evidence ~200+,
  findings ~400+ at real scale; projects, decisions): one envelope
  `{data, pagination: {page, page_size, total_items}}`, filters as
  query params, and a **server-enforced `page_size` cap** (digest
  §1.4 — an unbounded page size is a DoS vector; `Query(le=…)`, value
  at plan time). Offset pagination is a deliberate choice at
  per-project scale; cursor pagination is the recorded migration path
  (additive — a `cursor` param alongside, never a breaking reshape) if
  cross-project or unbounded-growth lists appear. Bounded structural
  reads (plan, funnel, landscape, artefact) stay whole-object.
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

## Adversarial adjudication addenda (2026-07-21 — codex lane, all 20 findings accepted)

Binding amendments not woven into the sections above:

- **SSE authentication (finding 8):** native `EventSource` cannot send
  an Authorization header — the SSE client is a **fetch-based stream
  with bearer auth**; reconnection uses our own cursor (the client
  passes its last-seen `event_log` sequence; `Last-Event-ID` is not
  relied on). **No tokens in query strings, ever.** No cookies are
  used, so CSRF machinery is out of scope by construction — stated,
  not assumed. A **mid-run token-expiry test** (expire → refresh via
  the OIDC adapter → reconnect → no event loss) is a named
  deliverable.
- **Backlog→live handoff (finding 11):** the replay protocol pins an
  atomic cutoff — backlog is read to a snapshotted max sequence and
  the live tail subscribes from sequence+1 in the same consistent
  view; heartbeat comments keep intermediaries from timing out;
  generator cleanup on disconnect (`try/finally`); proxy-buffering
  disabled at the edge. A **race-injected test** (event committed
  during the cutoff window; reconnect mid-stream) proves no loss and
  no duplication.
- **Planner turn concurrency (finding 15):** planning turns take the
  per-project lock; a second concurrent turn gets `409
  planning_turn_in_progress`; double-submit is idempotent (client
  turn id); the session cache is bounded and its eviction/restart
  behaviour (draft loss, honest) is rendered in the UI.
- **Planner-prose claim narrowed (finding 7):** ephemeral planner
  prose is **not execution-bearing for continuation** — but
  plan-field↔turn provenance (plan-as-object §) remains an
  acknowledged, deferred loss until 026/workspace-cluster; the
  contract does not claim the prose is worthless in every sense.
- **State/error surface matrix + clean clone (finding 13):** every
  view ships its loading / empty / partial-data states, and the app
  ships one coherent surface for each error class (401 session
  expired → re-auth, 404/archived, 409 capacity, 422 field errors,
  500, SSE-disconnected/reconnecting, interrupted-run recovery) — the
  matrix is a plan artefact and a rubric-checkable table. Clean-clone
  acceptance: documented env vars, dev-issuer bootstrap, migrations,
  `make setup/dev/verify` covering both `backend/` and `frontend/`,
  mock mode — a fresh machine reaches the running app from the README
  alone.
- **Live-check parameters (finding 19):** project A = standard
  effort, Frequent mode (guarantees an attended pause); project B =
  rapid effort, Unattended (no pause; executing at restart — restart
  fires while B's SSE shows a mid-chain stage executing).
  Responsiveness pass condition: health + one read model each < 2 s
  while both runs execute. Wall time is an observation, not a pass
  criterion; the check has an overall timeout at plan-pinned fixture
  scale. If B parks early (it should not, Unattended), the evidence
  notes it and the restart proceeds regardless.

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
- [fastapi-guidelines-digest.md](fastapi-guidelines-digest.md) — the
  89-page FastAPI/LLM best-practices source distilled for this slice
  (owner-supplied, 2026-07-21): §2 binds at plan time, §3 at build
  time, §4 lists guidance that must NOT be applied here; §1's four
  contract findings are adjudicated into this contract (BOLA 404,
  off-loop execution, single-instance posture, page-size cap).
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
  component-progress protocol (seam recorded); share/export CTAs and
  read-only/public links (deferred.md + handoff §7.3); the artefact
  confidence badge (§7.2 — descriptive language only); the run resume
  engine (017 seam — interruption is honest, not recoverable);
  **direct plan-pane editing** (re-deferred — owner, 2026-07-20:
  conversational plan editing is demo-validated and sufficient for v1;
  the plan-patch grammar + planner acknowledgement turn it needs is its
  own design surface; deferred.md entry re-tagged); **document upload
  UI** (out — owner, 2026-07-20: search supplies the corpus in v1; a
  real upload surface brings file handling, its own audit events +
  observable processing per the 009 seam, and an untrusted-input
  security surface — own slice).
- The `demo-live-run` branch itself stays untouched and unmerged; after
  this slice it is historical evidence only.

## Constraints & approval gates

Every gate below is **named for approval at this contract's 🛑** — none
may be re-decided silently mid-build:

- **Schema:** two migrations — (1) the `project` migration (columns +
  backfill policy above); (2) the `capability_run` status-constraint
  migration adding `paused`/`interrupted` (adversarial finding 1 —
  **gate expansion, needs owner re-approval**; up/down tested with
  paused rows). No other table changes; continuation state is
  event-log JSONB (`continuation.requested`), zero-schema by design.
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
  run/thread state) + **per-primitive `@radix-ui/*` packages with
  `class-variance-authority`/`tailwind-merge`** (headless behaviour
  under the shadcn-style copied-in components — exact primitive list
  at plan time, scoped to components actually built) +
  **`openapi-typescript` AND `openapi-fetch`** (finding 14:
  `openapi-typescript` generates types only; `openapi-fetch` is the
  schema-typed runtime client — together they are "the generated
  client") + **a frontend OIDC adapter** (finding 9: something must
  own browser login/token acquisition/refresh/logout —
  `oidc-client-ts` or `react-oidc-context`, picked at plan time,
  driven by the dev issuer now and Cognito config later) + `vitest`,
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
- **Model-authored display strings are untrusted at render** (024
  security-lane recommendation naming 025): event-payload display
  strings persist NUL-scrubbed only — the web renderer must scrub
  control/format characters on render (or the persistence layer adopts
  `sanitize_prompt_field`; choice at plan time), and React's default
  escaping is relied on — no `dangerouslySetInnerHTML` on any
  model-authored or source-derived string.

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
  scoped live session driven through the real browser UI — create
  project → planning conversation (2–3 turns) → start (rapid/standard
  effort) → **while the run is executing, probe API responsiveness**
  (health + a read model answer promptly — the off-loop execution pin,
  digest §1.2) → **start a second run on a second project (second
  dev-issuer user) while the first is live** — both streams progress
  without cross-talk, and each user's request for the other's project
  returns 404 → project A reaches a check-in and **parks** (run
  status `paused`, no executing walk) → **kill and restart the API
  server while A is parked and B is executing** → UI rebuilds from
  replay; **A's pending check-in survives the restart** (parked runs
  hold no process state); **B is marked `interrupted` honestly**
  (orphan sweep) → answer A's check-in post-restart (incl. one
  free-text steer through the confirm gate) → the **boundary
  continuation walk** dispatches and A completes → artefact renders
  with annotation layer + dossier → rename → archive → landing
  reflects all states. Estimated wall ≈ 20–30 min (two runs: one
  parked-then-completed, one interrupted). **No full live
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
