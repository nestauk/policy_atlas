# Task contract: 027-frontend-uplift

> **Status:** drafted 2026-07-28, rev 2/2.1/2.2 same day. Contract approved
> (before planning): **2026-07-28 · owner** ("a contract is approved. You can
> move on to the adversarial review") — adversarial lane runs post-approval
> per the Tier-3 standard; material findings reopen this gate. · Plan approved
> (before implementation): _pending_ ·
> ADR: _due — transcript durability model + artefact SSE vocabulary_.
>
> **rev 3 (2026-07-28): contract-stage adversarial lane DONE** (codex-rescue
> job task-ms4x604a-q7oq9s; 21 findings, 17 MAJOR, all adjudicated in — the
> two as-built claims underpinning findings 1–5 verified against
> `planning.py`/`runner.py` by the lead). Material amendments needing owner
> re-approval at the reopened 🛑: **(a)** strand 12 reshaped — single
> `planning_transcript` table (no thread entity, no speculative `kind`; finding
> 20), two-phase persistence superseding "both sides one transaction"
> (finding 2), durable `client_turn_id` idempotency (finding 3), enumerated
> rehydration mapping (finding 1), run-phase-anchored ordering (finding 4);
> **(b)** strand 13 pinned — prose-in-event only, no partial-artefact read
> path (findings 15/21), separate-connection emission with
> presentation-record semantics (finding 5), full event vocabulary + section
> identity (finding 17), terminal honesty on failed/aborted/interrupted
> partial streams (findings 6/8); **(c)** gate expansion — server-side
> filter query params on paginated lists (finding 7) + the honest-omission
> scope floor (finding 16); **(d)** live check extended — restart
> mid-synthesis leg (finding 9), durable-idempotency probe, server-side
> filter check. Minor folds: live search card named (11), findings field
> set enumerated (10), composer states + rail interaction floor (18/19),
> no-backfill semantics (12), web-api.md § Planning turns rewrite (13),
> transcript pagination (14), spec-floor sweep of rubric/tests.
>
> **rev 3.1–3.3 (owner amendments, 2026-07-28):** table renamed
> `planning_transcript` (planning-only by design — co-pilot brings its own
> chat model) · **ICF findings surfaced** (strand 6 kind-aware; ICF row
> design has no demo precedent — lead-owned) · **strand 14 production
> hygiene folded in** (live landing statuses · pending check-in badge +
> title marker · per-view titles + favicon · error boundary + 404 route ·
> toasts wired, dead exports deleted · signed-in identity · evidence-base
> print stylesheet (share/export seam stays deferred) · mock-journey e2e
> into CI — the one approved CI change).
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
   collapse) · the **live search card** while acquire/screen stages run
   (per-backend accumulating result counts + recent queries + "preparing
   queries…" state — honest omission per backend where the tick/coverage data
   doesn't carry it; finding 11) · **completion card** (outcome-first, counts,
   CTAs into evidence base/sources) · groups-by-facet card · embedded
   landscape charts. The demo's 55/45→35/65 animated split already exists in
   prod (CSS var) — keep it.
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
   (strand 12), so it survives navigation and restarts. **Composer states
   pinned** (finding 18 — planning turns 409 while a run executes or parks):
   enabled during planning and after terminal runs (replanning); while a run
   executes/parks it disables with honest copy pointing at check-in steering
   — it never sends guaranteed-409 turns and never implies Q&A. **Rail
   interaction floor** (finding 19): collapse is a real keyboard-operable
   button (not drag-only), resize has sane min/max bounds, state is
   session-local (no persistence requirement).
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
6. **Findings view — both finding kinds** (owner amendment, 2026-07-28: the
   demo never rendered ICF findings; this slice adds them). The view is
   **kind-aware** over the already-kind-typed findings list (`profile`
   discriminates; the enriched rows follow the web-api typed-variants pin —
   a discriminated union, so the client narrows on kind):
   - **IOF rows** (demo-validated shape): table columns intervention /
     outcome / direction chip with tooltip / grouped-as / source link;
     expandable rows with "Reported numbers" and "The exact words"
     (verified-quote) panels. The expansion field set named in full
     (finding 10): the statistics (effect size, CI, SE, p, n, k, I², τ²)
     **plus** comparator, estimate level, causality, the primary-outcome
     marker, stratum qualifier chips, and the 020 v2 `effect_basis` +
     `study_geography`.
   - **ICF rows** (no demo precedent — designed in-slice from the 021
     schema/artifacts; taste-bearing, lead-owned at plan time): an
     implementation-context claim about a named intervention — rendered
     with its `context_type` (labelled, never the raw enum), claim,
     intervention, context label, and the populated subset of
     population/setting/study geography/design, claim level/basis, and
     resource/workforce requirements (`field_coverage` honesty: absent
     fields omit, never render "not extracted" as data) — with the same
     "The exact words" verified-quote panel (shared grounding shape).
   - The view lets the user tell and filter the kinds apart (kind filter
     alongside the facet chips); mixed lists label kind per row.
7. **Sources + dossier depth**: status-ladder labels with screening-detail
   tooltips (confidence, read basis, stage-2 confirmation, reason) · venue /
   strength / cited columns · dossier sections (About · what-happened ladder ·
   quality · details · tags **grouped by asserter, never merged** · cited-in ·
   findings-from-source covering **both finding kinds**, kind-labelled).
   Appraisal renders labels, never 1–5 numbers.
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
    becomes durable. **Schema: one table, `planning_transcript`** (name
    owner-amended from `planning_turn`, 2026-07-28 — rows are turns; the
    table is the planning conversation's durable transcript, and
    deliberately **not** a general chat store: co-pilot Q&A brings its own
    thread/context model per finding 20, and may fold this table under it
    then) — one row per turn: `project_id`, `client_turn_id` (unique per project — the API's
    idempotency guarantee becomes durable, surviving restarts, instead of
    the process-local result cache), `user_message`, `reply`, the
    `plan_draft` snapshot (JSONB), `suggestions`, turn status
    (`pending | completed | failed`), `created_at`/`completed_at`. No
    thread entity and no speculative `kind` column — "model only what
    behaves"; the co-pilot slice brings its own chat tables when it brings
    the behaviour (adversarial finding 20: role/text rows would not have
    future-proofed its context/library semantics anyway). **Two-phase
    persistence, not one transaction** (finding 2 — the planner LLM call
    deliberately runs outside any transaction, as-built): the row inserts
    with the user message on receipt (short transaction, after the
    authz/409 gate); the reply + draft complete it in a second transaction
    — the same one that persists the approved plan when the turn reaches
    `ready`. A crash between the two leaves a `pending` row that renders
    honestly as an incomplete turn with retry; a retried `client_turn_id`
    returns the completed row verbatim or re-runs an incomplete one.
    **Rehydration is an enumerated mapping, not an aspiration**
    (finding 1, per the 025 context-parity precedent): every
    `_PlanningSession` field maps to a durable source — `turns` ← the
    completed rows in order; `previous_draft` ← the latest completed row's
    snapshot; the idempotency cache ← the rows themselves; `session_id` ←
    fresh per process (tracing identity, not quality-bearing) — the plan
    carries the mapping as a checked table against `planning.py` as-built,
    and a field with no durable source is a stop-condition finding.
    **Transcript reads paginate** with the standard envelope (finding 14).
    **Ordering with the steering record is run-phase-anchored, not
    timestamp-merged** (finding 4): planning turns are 409-fenced while a
    run executes or parks, so turns and steering decisions can never
    interleave within a run — the thread renders planning turns between
    run blocks, and steering decisions inside them ordered by their
    `event_log` sequence; steering stays referenced from its own record,
    never duplicated. **No backfill** (finding 12): existing projects
    simply have zero turn rows; in-memory drafts in flight at deploy time
    are lost once, honestly (named in verification.md). The 025 "draft
    conversation is lost on restart" pin is superseded, and
    `web-api.md` **§ Planning turns is rewritten** to the durable
    semantics (finding 13) — not just the SSE section.
13. **Live artefact streaming (backend + frontend).** The SSE vocabulary
    gains three additive events, **pinned now** (findings 15/17/21, closing
    the payload-shape question): `artefact.skeleton` (the ordered section
    list — index, title, focus — including the key-findings and conclusion
    positions), `artefact.section_started {index}`, and
    `artefact.section_completed {index, title, prose}` — **prose travels in
    the event**; sections render *only* from these durable events; there is
    **no partial-artefact read path**, and the artefact read model remains
    the bounded final object. Section identity is the skeleton index
    (duplicate titles are disambiguated by construction); the reducer
    clears live sections when a different run starts (the existing
    new-run reset rule extends). **Emission semantics** (finding 5 — the
    synthesise component runs inside one component-wide transaction
    as-built): `artefact.*` events append via a **separate
    connection/transaction** from the synthesise loop, so the SSE tail
    sees them live and they survive a component rollback. They are
    **presentation/progress records, never authoritative artefact
    content**: the artefact of record still lands only at component
    commit. **Terminal honesty** (findings 6/8): if the run fails, aborts
    or is interrupted after sections have streamed, the streamed sections
    stay visible under an explicit terminal banner (drafted sections, not
    the evidence base; citations never attached) — the streaming footer's
    "annotations attach at commit" copy must be truthful on every terminal
    path, a mock fixture exercises the partial-failure state, and
    restart-mid-synthesis follows 025 semantics unchanged (mid-component
    death = `interrupted`; streaming adds no resume). The evidence-base
    page renders the demo-validated `LiveArtefact` shape: all planned
    section headings with focus placeholders, "Writing this section now…"
    on the active one, prose filling in place as each completes —
    **whole-section grain, not token streaming**. `web-api.md` § SSE
    updated; the frontend narrow set, reducer and generated types extend
    accordingly.
14. **Production hygiene** (owner-approved additions, 2026-07-28): **live
    landing statuses** (projects list refetches on an interval while any
    run is non-terminal — a card never lies about "Analysing"/"Paused") ·
    **pending check-in visibility outside the workspace** (badge on the
    Workspace nav item + a `document.title` marker while a check-in is
    pending; no push/email — that stays out) · **per-view `document.title`
    (project name + view) and the brand favicon**, replacing the Vite
    defaults · **root error boundary + catch-all 404 route** (one honest
    render-crash surface; unknown URLs get a real "nothing here" view) ·
    **toasts wired to mutation failures** (rename/archive/answer errors —
    consuming the built-but-unused Toast system) **and remaining dead
    exports deleted** (`useCheckIns` and any other unconsumed surface this
    slice doesn't claim — no false signals) · **signed-in identity shown
    beside sign-out** (the existing `jwt.ts` sub/claim read; display only)
    · **print stylesheet for the evidence-base page** (`@media print` on
    the already-A4-shaped artefact; owner-ruled honest browser behaviour —
    the share/export CTA seam stays deferred and undischarged) · **the
    mock-journey Playwright e2e joins CI** (its own approved CI-gate item —
    see Constraints).

Plus: the `planning_transcript` migration (+ downgrade) and endpoints with tests
(two-phase persistence incl. the crash-between-phases pending-turn render ·
durable `client_turn_id` idempotency across a restart · rehydration parity
per the enumerated mapping · transcript round-trip + pagination ·
owner-scoped 404) · artefact-event emission with tests (separate-connection
visibility — events tail live while the component transaction is open ·
replay idempotence — a reconnect mid-synthesis rebuilds exactly the
completed sections · terminal honesty after failure/interruption with
partial sections · reducer extension incl. new-run reset) · mock fixtures
extended to exercise every new surface incl. a paused-mid-synthesis stream
and a failed-after-partial-stream state (sanitized-fixtures policy) · vitest for the judgment-bearing components (annotation slicing with
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
- **The comms shared component library (Figma)** —
  `figma.com/design/faisD0OmAfv9nhwOUiRw74/Shared-component-library` — the
  **upstream** of the in-repo brand distillation (025 pin). For this polish
  slice the plan carries a **brand reconciliation pass**: check our tokens and
  visual-identity components (buttons/cutout, chips, nav, type scale) against
  the library's current state and fold any drift back into
  `nesta-brand-tokens.md` + `index.css` — never as ad-hoc per-component
  styles. Access is via the owner (agent Figma access currently lacks editor
  rights on the file; screenshots/values supplied by the owner are an
  acceptable substitute). The library is the *visual* authority only — it is
  a Figma library, not a code component library; the 025 owned-primitives
  decision stands. The public repo carries the distillation, never Figma
  exports/assets with unclear licensing.
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

- **Public interface:** several demo surfaces show data the production API
  may not yet serve (kind-typed IOF **and ICF** finding detail fields — the
  discriminated-union enrichment of the flat `FindingOut` · dossier detail
  fields · coverage `backends_detail` · claim types beyond citation/gap ·
  screening-detail fields on evidence rows). Where the durable record
  already holds the data, the read models gain **additive-only fields, one
  optional additive dossier endpoint, and server-side filter query params
  on the existing paginated lists** (finding 7 — the demo's facet/status
  chips filter whole collections; client-side filtering of one page gives
  false counts at real scale and violates the 025 "filters as query params"
  pagination pin; the `SourcesView` client-side-filter caveat is
  discharged, not inherited). The exact list is enumerated at plan time
  from the as-built read models and approved at the plan 🛑; OpenAPI +
  generated client regenerate through `make drift-check`. Where the data
  doesn't exist in the durable record, the surface **honestly omits**
  (hide, never fake) — no chain/schema changes to manufacture it.
  **Honest omission is a bounded escape hatch, not a scope dial**
  (finding 16): the demo-validated surfaces named in strands 1/5/6/7 are
  the requirement; the plan's field list is reviewed strand-by-strand
  against them, and a strand losing its headline surface to "the read
  model doesn't serve it" reopens this contract gate rather than shipping
  silently thinner.
- **Schema (rev 2 gate, owner-directed; reshaped rev 3):** one migration
  adding the single `planning_transcript` table (strand 12), up/down tested
  against a populated database (no backfill — pre-existing projects have
  zero rows); **no other table changes** — steering stays on its existing
  record, artefact streaming is event-log JSONB (zero-schema).
- **SSE vocabulary (rev 2 gate, owner-directed):** the additive `artefact.*`
  event set per strand 13, recorded in `web-api.md`; no other event changes.
- **No auth changes** (render-level only; the auth seam and 026 fixes are
  preserved-verbatim; the new transcript endpoints sit behind the same
  owner-scoped auth dependency as every data route). **No new dependencies
  expected** — the demo stack is a subset of production's; any exception
  (e.g. an animation need Tailwind utilities can't meet) hits this gate
  explicitly. **CI (owner-approved, rev 3.3):** exactly one change — the
  mock-journey Playwright e2e (`pnpm e2e`) becomes a CI lane (chromium, mock
  mode, no backend; ~2–3 min); nothing else in CI moves. **No production
  config / deploy changes** (026 owns those).
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
  forming → **restart the API mid-planning; the thread survives, a retried
  `client_turn_id` returns the same turn, and the next turn works**
  (transcript store) → start → journey pane fills live (timeline · funnel ·
  coverage · live search card · activity) → check-in answered
  (answered-state renders; the decision appears in the thread inside its
  run block) → **during synthesise, watch at least one section stream into
  the artefact page in place** (skeleton → writing → filled), browser-reload
  mid-synthesis and confirm the completed sections replay → **on a second
  run, kill and restart the API mid-synthesis** (finding 9): the run is
  marked `interrupted` honestly, the streamed sections stay visible under
  the terminal banner, and the thread is intact → evidence-base page with
  claim panel + highlighted chunk context + dossier → findings expansion
  (both kinds) → sources filters (server-side — filtered counts are
  collection-true) + tooltips → hygiene spot-checks: while a check-in is
  pending, navigate to Sources and confirm the nav badge + title marker;
  confirm the landing card state updates without a manual refresh. Estimated wall ≈ 25–30 min. The 025 two-user/parked-restart leg
  is **not** re-run — the parked-pause and continuation machinery is
  untouched by this slice (strand 13 explicitly keeps 025 interruption
  semantics); its regression net is the existing test suite. **No staging
  deploy in this slice** (026 owns deploy; staging OpenAI quota exhausted)
  and no full live e2e — the mock journey covers flow breadth.
- Browser checks: keyboard nav on check-in card, claim spans, dossier, **and
  the rail collapse control** (finding 19); `prefers-reduced-motion` quiets
  every new animation; no horizontal body scroll at 1280/768 (rail collapsed
  and expanded).

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
