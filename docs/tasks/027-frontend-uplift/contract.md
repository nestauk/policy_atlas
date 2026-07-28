# Task contract: 027-frontend-uplift

> **Status:** drafted 2026-07-28. Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ · ADR: _likely none — no new
> architecture; confirm at step 4_.
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
code port**: the demo is React 18/Tailwind 3/hand-rolled state; production is
React 19 + compiler/Tailwind 4/generated client + TanStack Query + event-sourced
reducer. Demo code is **UX evidence, never imported**; `demo-live-run` never
merges (standing rule since 018). `demo/RETRO.md` §2 product decisions remain
binding as in 025 — as-built 019–026 behaviour wins on conflict.

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
3. **Planning thread polish**: message bubbles, thinking row with planner
   progress, suggestion chips (exist — restyle), composer. Draft-loss honesty
   unchanged (thread is process-local by design).
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

Plus: mock fixtures extended to exercise every new surface (sanitized-fixtures
policy) · vitest for the judgment-bearing components (annotation slicing with
overlap/oversize spans, funnel/count-up under reduced motion, plan-pane label
maps, answered-state render, quote-highlight fallbacks) · `e2e/journey.spec.ts`
updated to the new surfaces · `e2e/fe-api-smoke.spec.ts` kept green (its pinned
accessible names updated in the same commit as any rename — CI depends on it) ·
`index.html` title fixed · `verification.md`.

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
- **Out:** LLM narration and any new prompt surface (unchanged 025 rule) ·
  **live-artefact streaming** (demo's `LiveArtefact` needs `artefact.skeleton` /
  `artefact.section_*` SSE events the production vocabulary deliberately lacks —
  ❓ **owner call**: in only if promoted here as a named backend strand
  (new event types = web-api.md spec change + synthesise-stage emission);
  default = deferred.md seam) · comments · re-run/v1.1 · upload UI ·
  share/export · confidence badge · direct plan-pane editing · hard delete ·
  dark mode / i18n / sub-`sm` mobile layout · backend behaviour changes of any
  kind beyond the additive read-model gate · runs-list view (endpoint exists,
  no demo precedent — stays unconsumed).
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
- **No schema changes. No auth changes** (render-level only; the auth seam and
  026 fixes are preserved-verbatim). **No new dependencies expected** — the
  demo stack is a subset of production's; any exception (e.g. an animation
  need Tailwind utilities can't meet) hits this gate explicitly. **No CI
  changes** beyond the e2e specs themselves. **No production config / deploy
  changes** (026 owns those).
- SSE event vocabulary unchanged (unless the owner promotes live-artefact
  streaming, which names its own gate).
- All model-authored/source-derived strings render through `scrub()`; source
  URLs through `safeHref()`; the lint ban stays.
- Interactive elements are real `<button>`s with accessible names; the
  fe-api-smoke pinned names stay stable or the spec updates in-slice.

## Public / private boundary

Unchanged from 025: authenticated API serves the product; no secrets in the
bundle; new mock fixtures follow the sanitized-fixtures policy (sanitized API
records; openly-licensed real documents permitted); no font binaries committed.

## Model route

n/a — no inference in this slice; no new prompt surfaces (the demo's narration
prose wrap stays unported, per 025).

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
schema/chain change · a surface needs a new SSE event type (beyond an approved
promotion) · scope tempts narration/comments/re-run/upload · the substrate
invariants would have to bend to fit a demo behaviour · turn/token budget spent.

## Acceptance checks

- `make verify` green (incl. frontend typecheck · lint · vitest · build ·
  drift-check · font-guard).
- `pnpm e2e` (mock journey, updated) green locally; `make fe-api-smoke` green.
- **Live-check pin (contract-time):** one scoped **local** live session
  (dev issuer, real backend, real chain at rapid effort) driven through the
  browser: landing rename/archive → planning conversation with plan pane
  forming → start → journey pane fills live (timeline · funnel · coverage ·
  activity) → check-in answered (answered-state renders) → evidence-base page
  with claim panel + highlighted chunk context + dossier → findings expansion →
  sources tooltips. Estimated wall ≈ 15–20 min. **No staging deploy in this
  slice** (026 owns deploy; staging OpenAI quota exhausted) and no full live
  e2e — the mock journey covers flow breadth.
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

**Tier 3** — public-interface additions (additive read-model fields/endpoint) +
the steering-surface render + broad new render paths for model-authored
strings. Requires: security lane (scoped per the review-economy pin to the
ported render paths — scrub coverage, safeHref, injection via event-payload
display strings) · adversarial review at contract + plan + code · human deep
review. `/code-review` at medium per the review-economy pin.

Review focus: substrate-invariant regressions (auth gating, reducer
idempotence, queryKeys, URL state) · raw-enum/vocabulary leaks · dishonest
surfaces (faked/placeholder data, dropped-span mis-render) · scope creep toward
narration/streaming/comments · over-abstraction (no component library, no
speculative theming) · accessibility floor (real buttons, focus, reduced
motion).
