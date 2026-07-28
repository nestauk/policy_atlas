# Task contract: 027-frontend-uplift

> **Status:** drafted 2026-07-28, rev 2 same day. Contract approved (before
> planning): _pending_ · Plan approved (before implementation): _pending_ ·
> ADR: _due — transcript durability model + artefact SSE vocabulary_.
>
> **rev 2 (owner calls, 2026-07-28):** (1) **transcript store IN** — the
> planning conversation persists durably (strand 12); users' chats must not
> disappear, mid-session or across restarts; discharges the 025 "transcripts
> are 026" deferred seam. (2) **Collapsible/resizable chat rail IN** (strand 3).
> (3) **Live artefact streaming IN** (strand 13) — sections fill into the
> artefact page as each completes. Adjudication of PR #35
> (`demo-live-run-test-1`, capabilities→artifacts model): the transcript store
> and rail enter here; multi-thread chat + Chats library + Q&A over artifacts
> route to the co-pilot slice, the artifact gallery/multi-artifact IA to the
> workspace-cluster slice, the four new mock capabilities to the roadmap —
> PR #35 recorded as design input ([design-inputs.md](design-inputs.md));
> the transcript schema is shaped so multi-thread/Q&A slot in without
> migration churn. ⚠️ PR #35 must not be used until
> `backend/.dev-issuer/dev-key.pem` + `jwks.json` are rebased out (private
> key on a public branch; keypair burned).
>
> **Owner re-sequencing (2026-07-28):** this slice displaces the eval slice as 027
> (eval contract draft survives at unpushed `a5c9708`). Branches from
> `task/026-infra-deployment` (depends on 026's frontend auth-gating fixes and
> deploy tooling); the PR re-targets `dev` once 026 merges — if 026's review
> changes frontend files, this branch rebases before its own review.
>
> **Contract-stage adversarial review** (Tier 3 standard): after owner approval,
> read-only `codex-rescue` brief over contract + rubric; fall back down the ladder
> on credit failure per the codex-exhaustion rule.

## Goal

Close the UX gap between the production frontend (025 + 026 fixes) and the
demo-validated surface (`demo-live-run` branch, C4 demo). The demo's view layer is
richer everywhere that matters — the journey pane, the forming-plan pane, the
evidence-base page, findings/sources depth, the motion layer — but sits on a
throwaway substrate (no auth, hand-written duplicate types, swallowed errors).
The production frontend has the inverse shape: industrial substrate, plain views.

**This slice re-implements the demo's UX on the production substrate. It is not a
wholesale code port** — and the reason is wiring, not framework versions: demo
views are bound to hand-written types, a 16-event SSE vocabulary and a
hand-rolled store, and they lack the production disciplines (error/loading/empty
states, auth routing, `scrub()`, the accessibility floor, strict lint). The
operational rule: the demo's **data, state and primitive layers never cross**
(no demo types/api/store/Tip/SlideOver; Radix-based primitives stay); its
**markup, class strings, copy maps and interaction design are the UX spec** —
transcribing them and rewiring onto the generated client + reducer + scrub +
a11y substrate is the expected workflow, and demo-derived code gets the same
review scrutiny as new code. No demo file lands unmodified; `demo-live-run`
never merges (standing rule since 018). `demo/RETRO.md` §2 product decisions
remain binding as in 025 — as-built 019–026 behaviour wins on conflict.

**Substrate invariants preserved wholesale** (regression here fails the slice):
the `AuthApi` seam + 026 OIDC gating fixes · generated client + drift check ·
bearer-header SSE with cursor reconnect/backoff · reducer replay-idempotence ·
`queryKeys` shape · `scrub()`/`safeHref()` discipline + the
`dangerouslySetInnerHTML` lint ban · URL-addressable state (`?source=`,
`?status=`, `?page=`) · the error/reauth/reconnect/interrupted feedback surfaces
· mock mode (`installMockApi`) · provider nesting order · pnpm supply-chain
config · deploy assumptions (`VITE_*` names, `dist/`, `public/fonts/`).

## Deliverable

PR landing the uplifted `frontend/src/views/**` (+ supporting `ui/` primitives,
`index.css` motion layer, mock fixtures, tests), organised as strands:

1. **Journey pane** (the largest delta — demo `Workspace.tsx` right column vs
   prod `RunPane`): progress strip · phase-switching heading with honest
   degraded/aborted/failed banners · collapsed-expandable **plan recap** with
   full plan parity · sticky section mini-nav · **timeline** (glyphs, per-stage
   tooltips with blurb/elapsed/failure-reason, humanised summary counts,
   "skipped — a prior step failed" copy) · **funnel** (7 tracked stages, animated
   bars + count-up, plain-English tooltip definitions, "N screened out — kept in
   the sources table with reasons" footer) · **coverage card** ("Where I
   looked": per-backend results/relevant + query list + the composed adequacy
   sentence) · **activity feed** (liveness ticks, newest highlighted, duplicate
   collapse) · **completion card** (outcome-first, counts, CTAs into evidence
   base/sources) · groups-by-facet card · embedded landscape charts. The
   demo's 55/45→35/65 animated split already exists in prod (CSS var) — keep it.
2. **Plan pane**: the forming plan as a first-class right-pane surface
   (question · focus/scoping chips · constraint chips with the demo's
   geography-collapse rule · labelled search-effort/depth/sources/check-in
   settings · steps checklist · ready/forming chip · time band · full-width
   "Start the analysis" CTA with starting-lock), replacing the collapsible
   `<dl>` PlanDisclosure. Labels are server-supplied or from the locked
   vocabulary — **raw enum keys never render** (no `key.replace(/_/g,' ')`
   fallbacks; unknown key → omit, don't leak).
3. **Planning thread polish + the chat rail**: message bubbles, thinking row
   with planner progress, suggestion chips (exist — restyle), composer; the
   thread pane becomes a **collapsible/resizable rail** (PR #35's IDE-style
   left rail, single-thread for now — the multi-thread/Chats-library UI stays
   with the co-pilot slice). The thread renders from the durable transcript
   (strand 12), so it survives navigation and restarts.
4. **Check-in card uplift — presentation only.** The 025/024 behaviour contract
   is untouched: server-supplied options only, compile→confirm ladder with
   `confirm_token`, `requires_user_input` options route to free text, server
   stage labels only. Uplift: arrival emphasis, trigger copy, suggested-by-
   orchestrator eyebrow, and the demo's **answered-state collapse** (decision
   echo: chosen option label + typed prose + params). The demo's raw-id
   comma-separated param forms were placeholders — not ported.
5. **Evidence-base page**: A4 page framing with eyebrow/title/question header ·
   4-cell coverage snapshot · key-findings-first + conclusion ordering ·
   claim-type render breadth (beyond citation/gap: reasoning · pattern/theme ·
   source-check, styled per type with inline chips) · the claim detail surface
   gains type-specific explainer callouts and **quote-highlighted chunk context**
   (exact match → whitespace-normalised remap → quote-above-text degrade, never
   a broken panel). Keep prod's three-rung ladder (tooltip → popover → dossier)
   and `?source=` addressability.
6. **Findings view**: facet filter chips · table (intervention / outcome /
   direction chip with tooltip / grouped-as / source link) · expandable rows
   with "Reported numbers" (stat labels incl. the 020 v2 fields) and "The exact
   words" (verified-quote) panels.
7. **Sources + dossier depth**: status-ladder labels with screening-detail
   tooltips (confidence, read basis, stage-2 confirmation, reason) · venue /
   strength / cited columns · dossier sections (About · what-happened ladder ·
   quality · details · tags **grouped by asserter, never merged** · cited-in ·
   findings-from-source). Appraisal renders labels, never 1–5 numbers.
8. **Landing**: wire the existing-but-unconsumed `useUpdateProject` /
   `useArchiveProject` into card UI (inline rename with cancel-restores;
   archive with two-step confirm — **archive vocabulary, not delete**) ·
   staggered-rise cards · dashed new-project tile.
9. **Decision log**: check-in rows tinted + expandable friendly-labelled detail.
10. **Motion layer**: the demo's animation utilities (rise/glow/breathe/bar,
    count-up) rebuilt as Tailwind-4 utilities under the pinned rule — **every
    animation marks real data arriving, never decoration** — all quiet under
    `prefers-reduced-motion`.
11. **Chart hygiene**: recharts colours read the `index.css` tokens (kill the
    hardcoded hexes); the publication-country caveat line ("where sources were
    published, not where the studies were conducted") renders wherever that
    distribution shows.
12. **Transcript store (backend + frontend).** The planning conversation
    becomes durable: a schema migration adds transcript tables — shaped for
    the co-pilot future (a thread table with a `kind`, messages with
    role/text/timestamps; exactly one `planning` thread per project in this
    slice, no thread CRUD UI) — and the planning-turn endpoint persists both
    sides of each turn **in the same transaction as the turn itself**. New
    read endpoint(s) serve the transcript; the frontend thread renders from
    it (replacing process-local React state), interleaving the
    already-durable steering record (check-in answers, free-text steers from
    `steering_history`) at their chain positions — steering history is
    referenced, never duplicated into the new tables. **Restart honesty
    upgrades**: the 025 "in-flight draft conversation is lost on restart"
    pin is superseded — after a restart the thread re-renders from the
    store, and the planning moment's context composition gains the stored
    transcript as a durable source (🟡 rehydration semantics — how much
    history feeds the planner prompt context — pinned at plan time from the
    as-built planning moment; no new prompt template, same moment composed
    from a durable source, consistent with 018's no-provider-sessions rule).
13. **Live artefact streaming (backend + frontend).** The SSE vocabulary
    gains additive `artefact.*` events (skeleton after sectioning ·
    section-completed per committed section; exact set + payload shape —
    prose-in-event vs refetch-on-event — pinned at plan time), emitted as
    durable `event_log` rows from the synthesise stage's per-section loop, so
    streaming is **replay-safe by construction** (a mid-run reconnect shows
    exactly the sections completed so far). The evidence-base page renders
    the demo-validated `LiveArtefact` shape: all planned section headings
    with focus placeholders, "Writing this section now…" on the active one,
    prose filling in place as each section completes — **whole-section
    grain, not token streaming** — with the honest footer that citations and
    claim annotations attach when the run commits the final artefact.
    `web-api.md` § SSE updated; the frontend narrow set, reducer and
    generated types extend accordingly.

Plus: the transcript migration (+ downgrade) and endpoints with tests
(turn-persists-transactionally · transcript round-trip · restart survival ·
owner-scoped 404) · artefact-event emission with tests (per-section durable
rows · replay idempotence — a reconnect mid-synthesis rebuilds exactly the
completed sections · reducer extension) · mock fixtures extended to exercise
every new surface incl. a paused-mid-synthesis stream (sanitized-fixtures
policy) · vitest for the judgment-bearing components (annotation slicing with
overlap/oversize spans, funnel/count-up under reduced motion, plan-pane label
maps, answered-state render, quote-highlight fallbacks, live-section fill-in) ·
`e2e/journey.spec.ts` updated to the new surfaces · `e2e/fe-api-smoke.spec.ts`
kept green (its pinned accessible names updated in the same commit as any
rename — CI depends on it) · `index.html` title fixed · the ADR · deferred.md
updates (025 transcript seam discharged; co-pilot UI + workspace-cluster IA
seams recorded) · `verification.md`.

## Read first

- `demo/RETRO.md` §2 + `demo/API.md` (branch `demo-live-run`) — the validated UX
  baseline and locked vocabulary; point-in-time evidence, as-built code wins.
- The demo views themselves (`demo/frontend/src/views/`, `ui.tsx`,
  `sourcePanel.tsx`, `index.css`) — the UX spec, read-only.
- `frontend/README.md` + `docs/specs/system/web-api.md` — the substrate and the
  pinned 9-event SSE vocabulary + read-model surface.
- `docs/specs/sources/evidence-base-ux/` — brand tokens, `hifi.css`, handoff §7.
- 025 contract strand 7 + its state/error matrix (binding precedent).

## Scope / Out of scope

- **In:** `frontend/src/**` view/ui/css/mock/test work per Deliverable; the
  **additive read-model gate** below; e2e spec updates.
- **Out:** LLM narration and any new prompt surface (unchanged 025 rule — the
  transcript store persists the *existing* planning moment; **co-pilot Q&A
  over artifacts stays out**, it needs a lead-authored prompt surface and is
  its own slice) · **multi-thread chat UI + Chats library** (PR #35 — the
  transcript schema is shaped for them; the UI lands with co-pilot) ·
  **capability picker / artifact gallery / multi-artifact IA + the four mock
  capabilities + per-artifact "Cited in"** (PR #35 — workspace-cluster slice
  and roadmap; see design-inputs.md) · comments · re-run/v1.1 · upload UI ·
  share/export · confidence badge · direct plan-pane editing · hard delete ·
  dark mode / i18n / sub-`sm` mobile layout · backend behaviour changes beyond
  the named strands 12–13 and the additive read-model gate · runs-list view
  (endpoint exists, no demo precedent — stays unconsumed).
- `demo-live-run` stays untouched and unmerged; after this slice its frontend
  is fully superseded and the branch is pure history.

## Constraints & approval gates

- **Public interface (the one expected gate):** several demo surfaces show data
  the production API may not yet serve (findings stats/direction/quote fields ·
  dossier detail fields · coverage `backends_detail` · claim types beyond
  citation/gap · screening-detail fields on evidence rows). Where the durable
  record already holds the data, the read models gain **additive-only fields
  (or one additive dossier endpoint)** — the exact list enumerated at plan time
  from the as-built read models, approved at the plan 🛑; OpenAPI + generated
  client regenerate through `make drift-check`. Where the data doesn't exist,
  the surface **honestly omits** (hide, never fake) — no chain/schema changes
  to manufacture it.
- **Schema (rev 2 gate, owner-directed):** one migration adding the
  transcript tables (thread + message, per strand 12), up/down tested against
  a populated database; **no other table changes** — steering stays on its
  existing record, artefact streaming is event-log JSONB (zero-schema).
- **SSE vocabulary (rev 2 gate, owner-directed):** the additive `artefact.*`
  event set per strand 13, recorded in `web-api.md`; no other event changes.
- **No auth changes** (render-level only; the auth seam and 026 fixes are
  preserved-verbatim; the new transcript endpoints sit behind the same
  owner-scoped auth dependency as every data route). **No new dependencies
  expected** — the demo stack is a subset of production's; any exception
  (e.g. an animation need Tailwind utilities can't meet) hits this gate
  explicitly. **No CI changes** beyond the e2e specs themselves. **No
  production config / deploy changes** (026 owns those).
- All model-authored/source-derived strings render through `scrub()`; source
  URLs through `safeHref()`; the lint ban stays.
- Interactive elements are real `<button>`s with accessible names; the
  fe-api-smoke pinned names stay stable or the spec updates in-slice.

## Public / private boundary

Unchanged from 025: authenticated API serves the product; no secrets in the
bundle; new mock fixtures follow the sanitized-fixtures policy (sanitized API
records; openly-licensed real documents permitted); no font binaries committed.

## Model route

No new prompt surfaces and no route change (the demo's narration prose wrap
stays unported, per 025; co-pilot Q&A stays out). Strand 12's planner
rehydration recomposes the *existing* planning moment from a durable source —
same prompt family, no template change; if rehydration turns out to need a
prompt change, that's a stop condition, not a quiet edit.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves** — no speculative props/fields for surfaces not built.
- **Flag, don't drop** — degraded/failed/empty states render honestly; dropped
  annotation spans are honest (skip, never mis-render).
- **Honest absence** — data-driven surfaces hide when the API doesn't serve the
  data; they never render placeholders as facts. Coverage claims keep their base.
- Deferred seams recorded in [docs/deferred.md](../../deferred.md) (live-artefact
  streaming lands there unless promoted).

## Stop conditions

Halt and escalate when: a read-model addition turns non-additive or tempts a
chain change · schema beyond the one transcript migration is needed · an SSE
event beyond the approved `artefact.*` set is needed · planner rehydration
turns out to need quality-bearing state that lives only in process memory
(stop-condition finding, per the 025 precedent) · scope tempts
narration/Q&A/multi-thread/comments/re-run/upload · the substrate invariants
would have to bend to fit a demo behaviour · turn/token budget spent.

## Acceptance checks

- `make verify` green (incl. frontend typecheck · lint · vitest · build ·
  drift-check · font-guard).
- `pnpm e2e` (mock journey, updated) green locally; `make fe-api-smoke` green.
- **Live-check pin (contract-time):** one scoped **local** live session
  (dev issuer, real backend, real chain at rapid effort) driven through the
  browser: landing rename/archive → planning conversation with plan pane
  forming → **restart the API mid-planning; the thread survives and the next
  turn works** (transcript store) → start → journey pane fills live
  (timeline · funnel · coverage · activity) → check-in answered
  (answered-state renders) → **during synthesise, watch at least one section
  stream into the artefact page in place** (skeleton → writing → filled),
  then reload mid-synthesis and confirm the completed sections replay →
  evidence-base page with claim panel + highlighted chunk context + dossier →
  findings expansion → sources tooltips. Estimated wall ≈ 20–25 min. **No
  staging deploy in this slice** (026 owns deploy; staging OpenAI quota
  exhausted) and no full live e2e — the mock journey covers flow breadth.
- Browser checks: keyboard nav on check-in card, claim spans, dossier;
  `prefers-reduced-motion` quiets every new animation; no horizontal body
  scroll at 1280/768.

## Verification evidence expected

`verification.md` with: gate outputs · the live check narrated with timestamps ·
screenshots of each uplifted surface (before/after where the delta is visual) ·
the additive-field list as approved vs as landed · substrate-invariant
confirmation (auth/SSE/reducer/scrub tests untouched and green, or renames
justified) · diff summary · public-safety confirmation · known gaps +
deferred.md pointers.

## Risk tier & review focus

**Tier 3** — schema (transcript migration) + public-interface additions
(transcript endpoints, `artefact.*` events, additive read-model fields) + the
steering-surface render + broad new render paths for model-authored strings.
Requires: ADR (transcript durability + artefact event vocabulary) · migration
downgrade tested (the rollback plan — frontend/API changes are additive and
squash-revertible) · security lane (scoped per the review-economy pin to the
transcript endpoints' owner scoping + the ported render paths — scrub
coverage, safeHref, injection via event-payload display strings incl. the new
streamed section prose) · adversarial review at contract + plan + code ·
human deep review. `/code-review` at medium per the review-economy pin.

Review focus: substrate-invariant regressions (auth gating, reducer
idempotence, queryKeys, URL state) · raw-enum/vocabulary leaks · dishonest
surfaces (faked/placeholder data, dropped-span mis-render) · scope creep toward
narration/streaming/comments · over-abstraction (no component library, no
speculative theming) · accessibility floor (real buttons, focus, reduced
motion).
