# Implementation plan: 025-web-app-foundation

> **Status:** rev 2, 2026-07-21 — plan-phase adversarial review DONE
> (codex, job task-mrtylb43-q9xxdv; 13 MAJOR + 3 minor, **16/16
> adjudicated in**, incl. three reducer-annex refutations — see annex
> addendum). 🛑 awaiting owner approval (with ADRs 0024/0025).
> Contract: [contract.md](contract.md) (final). Annexes:
> [continuation-state-reducer.md](continuation-state-reducer.md) (+ § Adversarial
> addendum — G3/G4/G5), [retro-reconciliation.md](retro-reconciliation.md),
> [fastapi-guidelines-digest.md](fastapi-guidelines-digest.md).
> Tier 4 → owner-approved plan + ADR + rollback required.

## Implementation pins (lead-designed; briefs reference, don't re-derive)

1. **Build order is substrate-out:** hoist → migrations → runner parking →
   API → frontend scaffold → codegen → frontend foundation → views. The
   frontend is never built against an unpinned contract; the API is never
   built against an unparked runner.
2. **API package** `policy_atlas/api/` (routers/, contract/, auth.py, sse.py,
   readmodels/, lifecycle.py, continuation.py, app.py). Handlers `async def`;
   runner work via the offload executor; DB via short sync sessions in
   executor wrappers (no async-driver migration — digest §2).
3. **Per-project serialization primitive:** `SELECT … FOR UPDATE` on the
   `project` row in one helper; run dispatch, check-in answers, continuation
   claims all take it.
4. **Parking is a runner seam:** pause disposition `block` (CLI, byte-
   identical, pin-tested) vs `park` (API) behind `OrchestratorIO`;
   `WalkParked` outcome; `continue_plan(...)` re-enters via the continuation
   reducer (`runtime/continuation_state.py`, read-only, event-sequence
   ordered; `run_plan(resume_from=…)`).
5. **Continuation protocol:** answer + `continuation.requested` in one
   transaction → atomic claim → execute; startup order: orphan sweep, then
   drainer. Crash tests both sides of claim.
6. **SSE:** per-project; fetch-stream bearer auth; snapshotted-sequence
   backlog + tail from sequence+1 (atomic cutoff); 15s heartbeats;
   `try/finally`; `X-Accel-Buffering: no`; ephemeral ticks flagged, never
   persisted; **credentials never in URLs**.
7. **Contract source of truth:** Pydantic → `make openapi` → `npm run gen`
   (openapi-typescript types + openapi-fetch client) → committed →
   `make drift-check` in verify/CI. Discriminated unions as named components.
8. **Frontend layout:** `frontend/src/` → api/gen (generated), api/, store/,
   auth/, ui/{brand,radix}/, views/, routes.tsx (URL-addressable dossier/
   filters). Mock implements the generated interface.
9. **React 19 + compiler — DECIDED at this gate** (contract 🟡 discharged):
   recharts 2.15.x marks React 19 compatible (demo already pinned ^2.15);
   known `react-is` override documented (recharts #4558 / shadcn React-19
   guide); react-router 6.28+, TanStack Query v5, Radix all compatible.
   G-phase toolchain target is deterministic: React 19 + compiler enabled;
   any incompatibility discovered is a stop-condition report, not a silent
   fallback.
10. **Design tokens:** Tailwind theme from `nesta-brand-tokens.md` +
    `hifi.css`; `@font-face` + `font-display: swap` + fallback stack; CI
    font-binary guard in `make verify`.
11. **Security build items (not review topics):** CORS explicit origin list
    (app origin only) with tests (D.2); centralized display-string scrub
    utility + adversarial Unicode/control-char tests + an ESLint ban on
    `dangerouslySetInnerHTML` (H.4); prompt-family content-hash guard script
    wired into `make verify` (C.4).
12. **No new prompt surfaces** — enforced by the hash guard (pin 11).

## State/error surface matrix (contract-required plan artefact)

Error classes, one coherent surface each: **401-expired** → OIDC re-auth
redirect preserving route · **404/archived** → not-found view (owner-
indistinguishable) · **409 run-active / 409 capacity / 409 turn-in-progress /
409 answered** → inline notice on the triggering control, state refetched ·
**422** → field-anchored errors from envelope `details` · **500** → toast +
retry, never a white screen · **SSE disconnected** → "reconnecting" banner,
cursor resume, stale badge after 30s · **interrupted run** → timeline
terminal card + "start fresh run" CTA. Per-view states: every view ships
loading (skeleton), empty (honest absence copy), and partial-data (render
what read models return; hide, never fake). Rubric item 19 checks this table
against the built app.

## Contract-test matrix (every contract-named test → one task)

| Contract-named test | Task |
|---|---|
| SSE replay idempotence (restart sim) | E.1 |
| Backlog→tail race-injected + reconnect cursor | E.1 |
| Resolved-pause replay (exact pending cardinality) | E.1 |
| Steering round-trip through the real seam | C.3 |
| Double-answer barrier (1 decision + 1×409) | C.3 |
| Continuation crash tests (both claim sides) + drainer redispatch | C.3 |
| Orphan-sweep double-boot idempotence | C.3 |
| Continuation context parity (full pinned surface incl. failed-then-
  successful rerun, segment re-entry, free-text multi-fragment) | C.2 |
| CLI blocking-path byte-identical pins | C.4 |
| Prompt-family hash guard | C.4 |
| Thread-safety audit (two concurrent stub walks, **both complete**, SSE +
  read-model isolation asserted) | C.4 |
| Stub full-chain integrity (existing test stays green) | every full gate |
| Migration up/down populated-DB + backfill + downgrade mappings | B.2 |
| Lifecycle: rename persists · archive hides+retains+idempotent · 409
  while running · audit events transactional | B.3/D.3 |
| Authz matrix (401; cross-owner 404 indistinguishable) | D.2 |
| Provider conformance (2 issuers, key rotation) | D.2 |
| CORS origin-list tests | D.2 |
| Planner: turn lock 409 · client-turn-id idempotence · bounded cache
  eviction | D.3 |
| Pagination cap + envelope conformance | D.4 |
| Drift check (mutate model → gate fails) | F.1 |
| Mid-run token expiry → refresh → reconnect, no loss | G.3 |
| Store replay idempotence (unit) | G.3 |
| Scrub adversarial Unicode/control chars | H.4 |
| Playwright mock journey · clean-clone acceptance | I.1 |

## Tasks

### Phase 0 — baseline (½ day)
- T0.1 `lead` inline: `make verify` on branch base. **[FULL — mandatory]**

### Phase A — monorepo hoist (1 day)
- A.1 `lead`: layout + tooling map (the brief for A.2). *Seam design.*
- A.2 `fast-worker`: execute per map; `frontend/` placeholder; path audit
  script (root-relative, allowlisted).
- A.3 `fast-worker`: audit green. **[FULL — scaffold]**

### Phase B — schema migrations (1 day)
- B.1 `lead`: both migrations designed. **Downgrade mappings pinned here:**
  `paused → aborted`, `interrupted → failed`, `ended_at` backfilled to the
  downgrade timestamp where NULL; mappings asserted row-by-row in B.2's
  tests; continuation/park events remain inert in event_log (harmless by
  construction). *Schema is a hard gate.*
- B.2 `codex`: implement + up/down tests (populated pre-025 fixture, paused
  rows on downgrade, backfill assertions, exact downgrade transformations).
- B.3 `codex`: transactional lifecycle audit events + tests (moved from
  fast-worker — transaction semantics are judgment). **[FULL — schema]**

### Phase C — runner: parking + continuation (4–5 days; the hard core)
- C.1 `lead`: reducer seam design binding the annex **+ its adversarial
  addendum**. Adjudications pinned: **G3** `attempted_runs` threading —
  unify runner mutation semantics (rerun + segment paths update the map as
  the ordinary loop does; **named runner-behaviour delta, approved at this
  plan gate**); **G4** `successful_runs` = latest overall attempt iff
  succeeded; stale-block-on-rerun-success adjudicated in C.1 from the code
  (clear-on-success unless a read shows intent; either way pinned + named);
  **G5** overlay reducer folds BOTH decision shapes (`interpreted_action.
  directive_deltas` and fan-out `compiled[].delta`), `kind ==
  plan_adjustment` only. G1 payload fields + G2 `run.parked` snapshot as
  annexed. C.1 **emits the thread-safety audit checklist artefact**
  (C.4's brief). *Seam design + semantic adjudication.*
- C.2 `codex`: reducer + `WalkParked` + `continue_plan` vs the parity
  harness (full surface; the three new parity cases from G3–G5).
- C.3 `codex`: continuation protocol + crash/barrier/round-trip/orphan-
  idempotence tests per matrix.
- C.4 `fast-worker`: CLI pins · prompt-hash guard script into `make verify` ·
  thread-safety audit per C.1's checklist (both-complete + isolation
  assertions). **[FULL — runner core]**

### Phase D — API core (2–3 days)
- D.1 `lead`: contract models package + error envelope + all public shapes.
  *Public interface = taste-bearing seam.*
- D.2 `codex`: auth (JWT verify, dev issuer, conformance suite, authz
  matrix) + **CORS explicit-origin config + tests**.
- D.3 `codex`: projects/runs/check-ins/planning-turns routers — lifecycle,
  lock-guarded dispatch, continuation.requested emission, turn lock +
  **client-turn-id idempotence + bounded session cache with eviction
  tests**.
- D.4 `fast-worker`: pagination/envelope/naming conformance sweep + tests.
  **[verify-fast — no schema/ingest contact]**

### Phase E — SSE + read models (2 days)
- E.1 `codex`: SSE per pin 6 + race/reconnect/pending-vs-history tests +
  the liveness tick source (`search_live.py` signals or designed
  equivalent — **ingest-adjacent**).
- E.2 `codex` (moved from fast-worker — provenance honesty, citation clamp,
  priority semantics, coverage composition are judgment): read models with
  golden tests against seeded rows. **[FULL — ingest-adjacent (E.1)]**

### Phase F — frontend scaffold + codegen (1 day)
- F.0 `fast-worker`: Vite + TS strict + Tailwind + npm scaffold; React 19 +
  compiler per pin 9 (`react-is` override if npm requires).
- F.1 `codex`: OpenAPI export + named-component unions + `npm run gen`
  (types + openapi-fetch) + drift check into verify/CI. Done = model
  mutation fails gate. **[verify-fast]**

### Phase G — frontend foundation (2 days)
- G.1 `lead`: Tailwind theme from brand tokens + cutout button + chip.
  *Brand-defining surface.*
- G.2 `fast-worker`: remaining primitives (cards, nav, radix copy-ins:
  sheet/tooltip/popover/tabs/toast) — DoD: each with a component test
  (render + keyboard interaction) and themed states.
- G.3 `codex`: OIDC adapter + dev-issuer flow + refresh + fetch-stream SSE
  client (cursor reconnect) + mid-run expiry test + TanStack Query setup +
  event-sourced reducer with replay-idempotence unit tests.
  **[verify-fast]**

### Phase H — views (3–4 days)
- H.1 `fast-worker`: landing, sources, decision log, charts — brief carries
  the **per-view RETRO §2 acceptance checklist** (lead-authored from the
  annex: 35/65 shrink, sticky timeline, status-ladder dossier fields,
  publication-country wording, labels-not-scores, hide-never-fake; **no
  FWCI field** — no backing data).
- H.2 `codex`: planning conversation (chips, plan disclosure, **draft-loss
  /eviction state rendered honestly**), run timeline (stage cards, activity
  feed, ephemeral ticks), check-in card (024 confirm-gate delta render,
  parked/pending states).
- H.3 `lead`: artefact/evidence-base view — annotation layer, citation
  hover→click ladder, dossier content. *Core reading surface.*
- H.4 `codex` (moved from fast-worker): state/error matrix implementation
  per the plan table + centralized scrub + adversarial tests + ESLint
  `dangerouslySetInnerHTML` ban + `prefers-reduced-motion` + keyboard
  flows. **[FULL]**

### Phase I — acceptance (1–2 days)
- I.1 `fast-worker`: Playwright mock journey; clean-clone acceptance —
  **pass = a fresh clone reaches (a) both dev servers up, (b) dev-issuer
  login, (c) mock-mode journey green, following README only, ≤ 30 min,
  documented commands exit 0**.
- I.2 `lead`: the pinned live check (§ below). *Live evidence adjudication.*
- I.3 `lead`: verification.md; `web-api.md` spec; deferred.md entries;
  **ADRs 0024/0025 status→Accepted with owner sign-off date, included in
  the PR**; AGENTS.md phase note. **[FULL — step-6 exit]**

## Sizing (corrected per adversarial finding 15)

Phase arithmetic: 0.5+1+1+4–5+2–3+2+1+2+3–4+1–2 = **18–22 executor-days**,
plus integration/rework contingency (~20%) → plan for ~22–26. Review stack
budgets to the large-slice reality (022/023/024 ran ~3× routine pins) — this
is a 4–6× slice; say so at the review gate rather than discover it.

## Live-check script (contract-pinned + finding 16 parameters)

Fixture scale: project A = the pinned finance-ministries-class question at
**standard effort / Frequent** (expected found corpus 50–150; parks at P2/P3);
project B = a distinct pinned question, **rapid / Unattended**, launched when
A's SSE shows `screen_abstract` executing. Probes during dual execution:
`GET /healthz` + `GET /api/v1/projects/{A}/funnel`, each < 2 s. Cross-owner:
user B `GET /api/v1/projects/{A}` → 404. Restart while A parked ∧ B
executing. Post-restart: A's pending card renders; answer includes one
free-text steer through the confirm-gate delta render; continuation
completes; B interrupted honestly with fresh-run CTA. A's artefact renders
annotation layer + dossier (citation click → context clamp visible). Rename →
archive → landing truth. **Overall timeout 60 min** (abort + report as
blocker beyond it); wall time recorded as observation.

## Gate consolidation summary

FULL `make verify`: T0.1 · A.3 (scaffold) · B.3 (schema) · C.4 (runner core)
· E.2 exit (**E.1 is ingest-adjacent** — finding 11) · H.4 · I.3 (step-6
exit). verify-fast: D.4, F.1, G.3 (no schema/ingest contact; new files +
API package only).

## De-scope levers (pre-authorised order)

1. Charts view · 2. Decision-log expandable detail · 3. Playwright breadth
(keep smoke) · 4. Dossier secondary panes. **Never:** parking/continuation
correctness, auth, drift check, annotation layer, state/error matrix.

## Rollback (Tier 4)

One squash; revert restores pre-hoist tree (pure `git mv` + path edits).
Migrations carry tested downgrades with pinned status mappings
(paused→aborted, interrupted→failed; events inert). Frontend + API additive;
the runner parking seam is disposition-gated with CLI pins; the G3/G4
mutation-semantics unification is the one approved runner-behaviour delta —
regression-tested, named in verification.md.

## Review-stack sizing (conversation C)

Tier 4: contract-verifier · /code-review medium (angles: runner parking/
continuation + reducer, auth boundary, SSE race, migrations, API contract,
frontend store, views a11y, scrub/security) · security-auditor lane ·
codex adversarial · live-trace content lane (024 precedent) · human deep
review. Exclude generated client + lockfiles from review diffs; per-angle
diff scoping per review-economy pins.
