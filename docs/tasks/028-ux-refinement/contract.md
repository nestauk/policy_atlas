# Task contract: 028-ux-refinement

> **Status:** drafted 2026-08-03. Contract approved (before planning): _pending_ ·
> Plan approved (before implementation): _pending_ · ADR: _0028 expected
> (sequential plan-building), written at step 4 if the fork lands IN_.
>
> **Branching:** branches from `task/027-frontend-uplift` (stacked — 026 PR #33
> and 027 PR #36 are both at step 9, awaiting owner review/merge). The PR
> re-targets `dev` once they merge; if either review changes files this slice
> touches, this branch rebases before its own review.
>
> **Forks resolved (owner, 2026-08-03):**
> **(A) Sequential plan-building: IN, full flow** (prompt rev `planner_v6` +
> additive column + part cards + centred planning chat + inline plan card).
> **(B) Key-findings bullets: scoped prompt rev IN** — owner ruling: the eval
> slice is much deferred; build without the pre-eval prompt-freeze constraint
> (the cost/quality spot-check stays as ordinary verification, not an eval
> proxy). **(C) Tab IA: ❓ REOPENED (owner, 2026-08-03)** — the owner wants a
> mock-up of the fold before ruling (five tabs with Landscape folded vs six
> unchanged; Decision log stays either way); decided at this gate after the
> mock-up review.

## Goal

Act on the first structured user evidence the product has had: four internal
policy-team interviews on the 027 build (see
[design-inputs.md](design-inputs.md)). Three headline problems — users don't
know where to look during planning (split attention between chat and plan
pane), information overload in the outputs, and text that is too small and too
verbose. Plus a mechanics list: composer, sorting, navigation, naming.

The owner's Claude Design mock-up (`mockup/policy-atlas-ux-v2.dc.html`) is the
UX spec for the new planning flow and artefact navigation — same rule as 027's
demo spec: interaction design and copy shape cross; its runtime never does.

## Deliverable

PR landing, as strands:

1. **Type scale + copy diet.** A named type scale as `index.css` tokens
   (GOV.UK *pattern* — consistent sizes per content role, not their pixel
   values; body prose ≥16px), swept through `views/**` replacing the ad-hoc
   per-component pixel sizes; prose line length capped ~66–72ch wherever
   paragraphs render. One copy pass over all views: "just enough text" —
   redundant explainer copy cut, remaining copy consistent with the naming
   pass (strand 8). Copy/label changes land in the copy maps
   (`*Presentation.ts` / vocabulary files), not inline.
2. **Composer.** The single-line `<input>` becomes a `<textarea>` that is
   **multi-line by default (~3 rows) and expandable** (owner amendment,
   2026-08-03): auto-grows with content to a bounded max height; Enter
   sends, Shift+Enter breaks the line, with the hint line; fixed position
   under the scrolling thread (already the layout — must survive the
   strand-3 recentring); 027's composer-state semantics (disabled + honest
   copy while a run executes/parks) preserved verbatim.
3. **Sequential plan-building** (fork A — IN). The planner proposes the
   plan one part at a time; the user confirms each part with a button or
   redirects in free text.
   - **Prompt surface (lead-authored):** the planning prompt gains
     part-by-part behaviour — each turn's reply carries at most one
     **structured part proposal** (id · step label · title · optional body ·
     optional chips · 2–4 option labels) alongside the existing draft
     snapshot. Versioned as a new prompt (`planner_v6`), never edited in
     place.
   - **Durability:** the part payload persists on the turn row —
     **at most one additive nullable JSONB column on `planning_transcript`**
     (migration + tested downgrade). Rehydration and thread re-render read it
     back; 027's two-phase persistence, idempotency and 409 fencing are
     untouched.
   - **API:** additive-only — the turn read model exposes the part;
     **confirmation is an ordinary planning turn** (the button submits a
     canned message naming the option) — no new endpoints, no new SSE events.
   - **Frontend:** part cards in the thread (options → primary/secondary
     buttons; "Refine"-style options prefill the composer; confirmed state
     renders ✓ + Change); planning stage renders as a **centred single-column
     chat** (the plan pane no longer shows during planning); when the draft
     reaches ready, the plan renders as an **inline expandable chat card**
     (settings + steps + Start CTA + time band — details open by default
     pre-run, per the standing owner ruling), replacing the right-pane plan
     as the start surface. The run-stage journey pane is unchanged.
   - **Honesty:** the part card renders only what the reply carries; a turn
     with no part (planner chose prose) renders as today. Old transcripts
     (zero part payloads) render unchanged.
4. **Run-stage split 50/50** — the chat|journey split defaults to 50/50 (CSS
   var change; the resize affordance stays).
5. **Artefact navigation + progressive disclosure.** Sticky contents sidebar
   with scroll-spy on the evidence-base page (mock-up's sidebar variant; the
   top-bar variant is not built). The sidebar must work at the **real
   section-list shape** (verified against live artefacts, 2026-08-03:
   ~8–10 long question-specific titles — not the mock-ups' short generic
   ones). Sections collapsible with an always-visible one-line summary =
   **the section's own first sentence** (the synthesis prompt mandates
   opening with the takeaway, so it *is* the summary; `SectionOut.focus` is
   NOT used — live data shows it is the writing brief, "Synthesize
   across…", which must never render to readers); key findings +
   conclusions default open, the rest collapsed (plan pins the exact
   defaults); expand/collapse are real buttons with `aria-expanded`.
   Annotation spans keep working on collapsed→expanded prose (render-only
   change).
6. **Key-findings formatting** (fork B — prompt rev IN): the key-findings
   section emits scannable bullets instead of dense paragraphs — a **scoped
   rev of the synthesise section prompt for the key-findings role only**
   (lead-authored, versioned; other section roles untouched), with the
   renderer treating bullet lines as list items while annotation spans still
   anchor into the same persisted prose (spans crossing a bullet boundary
   degrade honestly, never mis-render). One live cost/quality spot-check
   pinned in acceptance (ordinary verification — owner ruled the pre-eval
   prompt-freeze concern void, 2026-08-03).
7. **Sources table.** Sortable columns (Source · Year · Evidence type ·
   Evidence strength · Status) as **additive server-side `sort`/`order` query
   params** on the existing paginated list (client-side sort of one page lies
   across pages — same logic as the 025 filters pin), with URL-addressable
   state; "Strength" → **"Evidence strength"**; row cleanup per the mock-up
   (venue under title, chip tones, count footer); **additive `theme` filter
   query param** + a theme select in the filter row.
8. **Themes → sources + naming.** Real artefacts have **no themes section**
   (verified 2026-08-03) and none is faked: themes render as a
   **data-driven page component** from the durable theme/grouping read
   model, labelled "Key themes", wherever themes show (the journey's
   discovered-themes card · the Landscape surface or the folded
   gathered-section per fork C) — each theme row carries a "N documents →"
   affordance opening the theme-filtered sources view; theme counts
   labelled "Documents" consistently. One **naming pass** consolidating
   stage/artefact labels across tabs, cards and empty states (the plan
   carries the copy map: e.g. plan · analysis · evidence base · sources
   vocabulary used identically everywhere).
9. **Signposting.** The planning empty state names the flow (question → plan
   → run); the ready plan card carries the start affordance + expectation
   copy; post-run the completion card CTAs stay the canonical route into the
   outputs. No new surfaces — copy and emphasis on existing ones.
10. **Tab IA** (fork C — ❓ open pending mock-up review): *option 1* —
    Landscape folds into the evidence-base page as a "How the evidence was
    gathered" collapsible section carrying today's six Landscape blocks
    (funnel · evidence types · publication years · where-published + caveat ·
    themes · finding groups; the tab retires, its route redirects); five
    tabs. *Option 2* — six tabs unchanged. Decision log stays either way.
11. **Small wins.** A bounded sweep listed at plan time and reviewed at the
    plan 🛑 (candidates from the mock-up: snapshot-cell navigation into
    filtered views where missing, findings-tab gated empty-state copy,
    check-in card copy tightening). Nothing lands unlisted.

Plus: migration (+ downgrade) if fork A lands · OpenAPI + generated client
regenerated through `make drift-check` · mock fixtures extended (sequential
turns, part cards, sorted/theme-filtered sources) · vitest for the
judgment-bearing pieces (part-card render incl. no-part and rehydrated turns ·
plan-card inline render · section collapse/summary fallback · bullet
annotation slicing · sort/filter URL state) · `e2e/journey.spec.ts` +
fe-api-smoke pinned names updated in the same commit as any rename ·
deferred.md updates · verification.md.

## Read first

- [design-inputs.md](design-inputs.md) + `mockup/policy-atlas-ux-v2.dc.html` —
  the requirements and UX spec.
- `docs/specs/system/web-api.md` §§ Planning turns · read models · SSE — the
  additive gate baseline (027's rewrite is current).
- `docs/tasks/027-frontend-uplift/contract.md` + `verification.md` — the
  substrate this refines; every 027 pin not amended here is binding.
- `backend/src/policy_atlas/api/contract/read_models.py` +
  `routers/read_models.py` + `routers/planning.py` — as-built read models,
  list params, planning-turn machinery (two-phase persistence, 409 fence).
- Planning prompt family as-built (orchestrator planning surface) — before
  drafting `planner_v6`.
- GOV.UK type-scale page — pattern reference only.

## Scope / Out of scope

- **In:** `frontend/src/**` per strands; the named additive API/schema/prompt
  gates; `docs/` artefacts.
- **Out:** co-pilot Q&A · multi-thread chat/Chats library · artifact
  gallery/multi-artifact IA · comments · re-run/v1.1 · upload · share/export ·
  dark mode / i18n / sub-`sm` mobile · auth changes · any chain behaviour
  change beyond the two named prompt revs · steering/check-in *behaviour*
  (render/copy only) · Bedrock/eval work. The 027 substrate invariants
  (auth seam · generated client + drift check · SSE reconnect · reducer
  idempotence · queryKeys · scrub()/safeHref() + lint ban · URL-addressable
  state · mock mode · pnpm supply-chain config · deploy assumptions) are
  preserved wholesale — regression fails the slice.

## Constraints & approval gates

- **Prompt surfaces (owner gate, forks A/B):** exactly two prompt changes,
  both lead-authored, both new versions never in-place edits: the planning
  prompt part-by-part rev (fork A) and the key-findings section rev (fork B).
  No other prompt/template touches; prompt-guard pins update in the same
  commit.
- **Schema:** at most the one additive nullable JSONB column on
  `planning_transcript` (fork A); zero migrations otherwise.
- **Public interface:** additive-only — the turn read-model part field,
  `sort`/`order`/`theme` query params on existing lists. Anything
  non-additive reopens this gate.
- **No new dependencies · no CI changes · no prod-config/deploy changes ·
  no auth changes · no new SSE events.**
- All model-authored strings render through `scrub()`; part-card option
  labels and step labels are server-supplied — **raw enum keys never
  render**; unknown → omit.
- Interactive elements are real `<button>`s with accessible names; the
  fe-api-smoke pinned names stay stable or its spec updates in-slice.

## Public / private boundary

Unchanged from 027: no secrets in the bundle; mock fixtures follow the
sanitized-fixtures policy; no font binaries committed (the mock-up HTML is
committed without its font/runtime files).

## Model route

OpenAI under the approved controls, unchanged. Prompt-bearing changes are the
two named revs above — lead-only, gated, versioned. If planner part-by-part
behaviour turns out to need more than a prompt + additive payload (e.g. new
orchestration state), that's a stop condition, not a quiet edit.

## Disciplines binding this slice

- **Don't flatten status.** settled · 🟡 leaning · ❓ open · ⏸ deferred stay as-is.
- **Model only what behaves** — the part payload carries only what the cards render.
- **Flag, don't drop** — spans/sections that can't render the new way degrade honestly.
- **Honest absence** — summaries come from durable text (focus/first sentence),
  never invented; counts keep their base.
- Deferred seams → [docs/deferred.md](../../deferred.md).

## Stop conditions

Halt and escalate when: a gate above is hit beyond its named allowance · the
planner rev needs non-prompt orchestration changes · a read-model addition
turns non-additive · annotation-span integrity can't survive a render change ·
scope tempts co-pilot/multi-thread/export · 026/027 merge review lands
conflicting frontend changes (rebase + reassess) · turn/token budget spent.

## Acceptance checks

- `make verify` green (backend + frontend suites, drift-check, prompt-guard,
  font-guard).
- `pnpm e2e` (mock journey, updated) green locally; `make fe-api-smoke` green.
- **Live-check pin (contract-time, scoped):** one local live session (dev
  issuer, real backend + real planner at rapid effort), ≈15–20 min: a
  sequential planning conversation (parts propose → button-confirm → free-text
  redirect on one part → ready plan card inline, details open) → restart the
  API mid-planning (thread + part states survive rehydration) → start → 50/50
  run view → artefact: contents sidebar scroll-spy, section collapse/expand,
  key-findings bullets with working claim popovers (fork B) → theme row →
  filtered sources → sort two columns (URL state, collection-true across
  pages) → composer: Enter/Shift+Enter, growth, disabled-during-run copy.
  Plus one key-findings cost/quality spot-check on the fork-B rev (same
  substrate re-run comparison, cost delta named in verification.md). No
  staging deploy; no full live e2e.
- Browser checks: keyboard operation of part-card options, section toggles,
  sortable headers; `prefers-reduced-motion` quiets new animation; no
  horizontal body scroll at 1280/768; type scale holds at both widths.

## Verification evidence expected

`verification.md` with: gate outputs · the live check narrated with
timestamps + screenshots per uplifted surface (before/after where visual) ·
the additive API list as approved vs landed · both prompt revs' diffs
summarised + the fork-B cost spot-check numbers · substrate-invariant
confirmation · copy-map/naming table as landed · diff summary ·
public-safety confirmation · known gaps + deferred.md pointers.

## Risk tier & review focus

**Tier 3** — two prompt-surface revs + one additive migration + additive
public-interface changes + broad render paths for model-authored strings.
Requires: ADR (sequential plan-building, if fork A lands) · migration
downgrade tested · security lane scoped to the new render paths (part-card
payload display strings) + the additive params (injection/sort-param
validation) · adversarial review at contract + plan + code · human deep
review. `/code-review` medium per the review-economy pin.

Review focus: planner-rev regressions (draft quality, 409/idempotency
behaviour unchanged) · annotation-span integrity under bullets + collapse ·
raw-enum/vocabulary leaks in part cards · dishonest summaries · sort/filter
correctness across pages · copy-diet overreach (cutting load-bearing honesty
copy) · scope creep toward co-pilot.
