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
> proxy). **(C) Tab IA: 🟡 HYBRID (owner direction after mock-up rounds 1–2,
> 2026-08-03; confirm at this gate):** the Landscape tab **stays** as the
> whole-corpus view; the evidence-base page gains a **cited-scoped** "How the
> evidence was gathered" section (plots show only what the report cites — the
> full search landscape stays on the tab). Six tabs. **(D) Section flow
> (owner, 2026-08-03, from the interview confusion's root cause):** the jar
> between the overview section and the per-theme sections is addressed at the
> **section-planning prompt** (a third gated prompt rev) and/or section
> organisation — see strand 12. **(C confirmed + scope additions, owner
> 2026-08-03, on mock-up rev 3 ("this looks good now")):** fork C hybrid
> stands; the ⏸ **summaries navigation layer** (provenance-grounding
> § Summaries) folds in as strand 13; **check-in refinement** (option
> overload + unnoticed pauses, live-testing findings) as strand 14.
> **(F) Strand-14 taxonomy FULLY RULED (owner, 2026-08-03, across 15
> mock-up rounds):** default mode unattended · P1 search review · P2
> evidence base + themes incl. rename-without-rerun IN · P3 reading list ·
> NEW Groups lattice point · P4 report plan with inline section editing ·
> authored-delta validation backend-first · free text first-class. The
> committed artifact `mockup/checkin-taxonomy.html` is the binding design
> record for strand 14.

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
     optional chips · 2–4 option labels; parts = question · scope ·
     thoroughness — no check-in part, steering is unattended unless
     requested) alongside the existing draft
     snapshot. Versioned as a new prompt (`planner_v6`), never edited in
     place. Thoroughness options are **outcome-first** (owner, 2026-08-04):
     each preset says what you get (cited overview across the whole screened
     corpus · cited report focused on the strongest full-text-checked
     documents · + findings database — every depth mints a cited report;
     full texts ingest at every depth) with its
     time band — internal rungs (rapid/deep, landscape) never render; free
     text compiles custom mixes. planner_v6 also **drops the default
     `published_before` bound** (live plans pin it to the plan date, so
     re-runs would exclude newer documents) and renders the recency floor
     as a visible scope chip, never a silent constraint. The binding design
     record for this strand is `mockup/planning-stage.html`.
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
   **Collapsed state shows title + summary** (owner, 2026-08-03): the
   one-line summary stays visible when the section is collapsed — expanding
   reveals the full cited prose; and **Key findings is not collapsible** —
   it always renders in full (Conclusions stays collapsible, default open).
   Summary source: the **verified block summary from strand 13** where one
   exists; the section's own first sentence as the honest fallback
   (legacy artefacts with no summary rows · `failed` summaries) — never
   `focus`, never generated at render time. Annotation spans keep working
   on collapsed→expanded prose.
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
10. **Tab IA** (fork C — 🟡 hybrid, confirm at gate): **six tabs stay.** The
    evidence-base page gains a collapsible **cited-scoped** "How the evidence
    was gathered" section — distributions over the report's cited sources
    only (evidence types · publication years · where-published + caveat ·
    key themes with document links), with a pointer to the Landscape tab for
    the whole corpus; the **Landscape tab remains the whole-evidence-base
    view** (funnel spanning the full search + screened-in distributions).
    Cited-scoped distributions may need an **additive scope variant on the
    landscape read model** (e.g. `scope=cited` query param) — inside the
    additive gate; enumerated at plan time.
11. **Small wins.** A bounded sweep listed at plan time and reviewed at the
    plan 🛑 (candidates from the mock-up: snapshot-cell navigation into
    filtered views where missing, findings-tab gated empty-state copy,
    check-in card copy tightening). Nothing lands unlisted.
12. **Section flow** (owner, 2026-08-03 — the interviews' root confusion:
    readers can't tell whether the overview "What the evidence shows…"
    section connects to the per-theme sections that follow; the transition
    jars). Addressed at the source: a **scoped rev of the section-planning
    prompt** (`synthesise_sections_v2` → v3, lead-authored, versioned) so
    the planned section list reads as a coherent narrative — the overview
    section explicitly frames the sections it opens (or the plan drops a
    redundant overview), titles form a visible hierarchy. Render support
    only if the plan finds it necessary (e.g. contents-sidebar grouping) —
    no invented structure the synthesis didn't produce. The exact prompt
    design is plan-time lead work; one live before/after section-list
    comparison joins the acceptance checks.
13. **Summaries navigation layer** (owner fold-in, 2026-08-03 — discharges
    the ⏸ "Block summaries / artefact summary / faithfulness judging" seam;
    the spec is `provenance-grounding.md` § Summaries and is **binding**):
    - **Block summary**: co-versioned nullable second column on the block
      record, written as a trailing step of block production, excluded from
      the content hash, with a `pending | verified | failed` marker; no
      independent staleness. **No backfill** — legacy blocks stay
      summary-free (strand 5's first-sentence fallback renders them).
    - **Artefact summary**: a field on the artefact (not a block; accrues no
      annotations), emphasis anchored on the conclusion-bearing component.
      The spec's flag-and-propose staleness machinery is trivially satisfied
      at v1 (blocks don't regenerate yet) — recorded, not built beyond the
      marker.
    - **Faithfulness**: LLM judge alone, bounded regenerate-on-fail,
      flat (always against raw detail + its epistemic annotations —
      flagged/gap content carried-with-status, never silently promoted;
      emphasis inherited, never originated). Exhausted retries →
      `failed`, surfaced honestly (that summary never renders as a
      summary).
    - **Display invariant** (spec): a summary never renders detached from
      its drill-down affordance — the collapsed section IS the drill-down;
      the artefact summary renders on the report page only (placement at
      plan time). Summaries carry no citations and stay outside
      evidence-strength roll-ups.
    - Two new lead-authored prompt surfaces (summariser + faithfulness
      judge), versioned; per-run cost delta measured in the live check.
14. **Check-in refinement — the ruled steering taxonomy** (owner-designed
    across 15 mock-up rounds, 2026-08-03; the committed design record is
    `mockup/checkin-taxonomy.html` — BINDING; survey grounding in
    design-inputs § 6). The full shape:
    - **Default steering mode = UNATTENDED** (owner ruling): a run started
      without opting into steering never pauses — flagged/honest-fail on
      problems, never waiting. Check-ins are requested, not offered (owner,
      2026-08-03): the planning flow asks no check-in question — users who
      want them ask in the planning chat or switch mode from a card. Mode table (lattice
      policy change): frequent = all always + generic boundary check-ins ·
      moderate = P1 + P4 always, P2/P3/Groups fired · minimal = all fired
      · unattended = all off.
    - **P1 → the search review** (was failure-only): "here's what the
      search collected" — per-backend counts, queries, sample titles;
      expand/refine options; mechanical failure is a context variant of
      the same stop (failure-led copy, "Search harder" primary). Renamed
      honestly — thin-evidence judgment belongs to P2's post-screen
      triggers, not P1.
    - **P2 → evidence base + themes**: shows the theme map (names +
      document counts); pool-shaping options re-homed here from P3 (scope
      to strata · exclude documents); re-map covers plain regenerate and
      guided; **theme rename-without-rerun IN (owner)** — the one new
      machinery item: a durable edit-delta class (rename on the
      characterisation record) + steering audit event, **P2-only by
      constraint** (strata are name-keyed downstream; the plan pins the
      mechanism and the constraint's enforcement).
    - **P3 → the reading list**: the card shows the shortlist (titles +
      strata, browse-all); floor slimmed to proceed + change-count /
      ranking-emphasis / must-include (pool options moved to P2; "add ICF"
      dropped — ICF already defaults at deep depth; "refresh extraction"
      dropped from the floor — a rare re-run condition that belongs to
      authored suggestions).
    - **Groups → a NEW deep-only lattice point** (after group; owner
      principle: one checkpoint steers one component): the regroup options
      (which re-run `group`) move here off P4's floor — also fixing the
      found honesty bug (`_p4_options()` offered regrouping unconditionally,
      incl. standard runs where findings were never extracted). Its fired
      set already exists (`grouping_flag_triggers`). Groups + P4 share one
      interruption: two single-subject questions in sequence.
    - **P4 → the report plan**: shows the proposed sections; options are
      synthesis-directive only (write-as-planned primary · emphasis);
      **inline per-section edit/✕ remove/+ add** compose the full edited
      list into the existing `edit_sections` requires-input delta (grammar
      unchanged, same confirm ladder); the retype-everything option
      retires.
    - **Copy at source**: the static option strings in
      `runtime/steering.py` rewritten in plain reader language (the
      jargon leaks — `weight_emphasis x2.0`, `D3/D6/D7/D8/B3` — are code
      strings, not prompts); honest semantics stay explicit in plain words.
    - **Authored options ("Suggested from this run's results")**:
      backend-first validation per the gates (one grammar/one validator,
      authoring-time compile with drop+log+event, apply-time revalidation,
      loud refusals — closes the found hallucinated-delta hole,
      `recover_full_text`) + the watch-authoring prompt rev (reader-facing
      framing) + render rules: endorsements of a floor option render as
      the reason under the blue primary (no badge, no duplicate button);
      only novel suggestions get the block.
    - **Free text on every card**: the existing 024 free-text→compile→
      confirm ladder surfaces as a composer-style "or say it in your own
      words" row on every check-in; the compile→confirm exchange renders
      as a mini-thread (your words → plain-language compiled changes →
      apply/discard; partial refusals name which part and why).
    - **Pause salience** (for opted-in runs): the paused state is
      unmissable — journey heading + stage bar + timeline render
      paused-waiting-on-you; a cross-tab banner jumps to the check-in;
      composer state says waiting, not running; nav badge + title marker
      stay. The mock e2e asserts a paused run is visually distinct from an
      executing one on every tab.
    Behaviour-change inventory for the gates: lattice extension (Groups
    point) · mode-table changes incl. the unattended default · option
    re-homes + floor slimming + depth-conditional floors · the rename
    edit-delta class + audit event · authored-delta validation. The
    024/025 invariants stay: server-supplied options, compile→confirm
    ladder, `confirm_token`, steering events on the durable record.

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

- **Prompt surfaces (owner gate, forks A/B/D/E):** the named lead-authored
  prompt changes only, all new versions never in-place edits: the planning
  prompt part-by-part rev (fork A) · the key-findings section rev (fork B) ·
  the section-planning flow rev (strand 12) · the summariser + faithfulness
  judge (strand 13, new surfaces) · the **watch-authoring prompt rev**
  (strand 14a, now definite — owner findings 2026-08-03: (i) authoring
  reuses the internal decision prompt verbatim, so authored option labels
  arrive in machinery language; (ii) a live authored option carried an
  **invented delta** — intent `recover_full_text`, which exists nowhere in
  the codebase: a button promising an impossible action. Owner ruling:
  **fix the substrate, not frontend guardrails.** The rev gives authoring
  its own reader-facing framing — plain-language labels, reasons citing
  visible facts, machinery vocabulary banned, endorse-existing-option
  signalling, a count cap — and the **backend delta pipeline closes the
  validation asymmetry** (as-built: free text compiles through the
  router's author-blind grammar with honest refusals, but authored options
  are only JSON-parse-checked at transport and `_offered_option` applies
  stored deltas verbatim after shape checks — semantically invalid deltas
  ride through to a silent no-op): (a) **one grammar, one validator, all
  three producers** — authored options validate through the same
  author-blind grammar as free-text fragments **at authoring time**;
  non-compiling options are dropped, logged and evented, never persisted
  into the pause payload; (b) **apply-time revalidation** at the answer
  route for any authored delta (the trust boundary re-checks, cheap since
  the validator exists); (c) **unknown directive keys are loud** — a delta
  the grammar can't compile is a refusal with a reason, never a silent
  no-op). No other prompt/template touches; prompt-guard pins update in
  the same commit.
- **Schema:** additive-only, enumerated: the nullable JSONB part column on
  `planning_transcript` (fork A) + the block-summary column & marker and the
  artefact-summary field & marker (strand 13, per spec). One migration (+
  tested downgrade); no backfill anywhere; nothing else moves.
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

OpenAI under the approved controls, unchanged. Prompt-bearing changes are
exactly the gate-listed surfaces (fork A planner rev · fork B key-findings
rev · strand 12 sections rev · strand 13 summariser + faithfulness judge ·
the strand-14 watch-authoring rev) — lead-only, gated, versioned.
If planner part-by-part behaviour turns out to need more than a prompt +
additive payload (e.g. new orchestration state), that's a stop condition,
not a quiet edit.

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
  pages) → composer: Enter/Shift+Enter, growth, disabled-during-run copy →
  **summaries** (strand 13): block summaries mint + verify during the run,
  collapsed sections show them, a legacy artefact still renders on the
  first-sentence fallback → **check-in salience** (strand 14): while paused,
  every tab visibly says so and the banner jumps to the check-in; the
  check-in card leads with the recommended action and discloses the rest.
  Plus one key-findings cost/quality spot-check on the fork-B rev (same
  substrate re-run comparison) and the **per-run cost delta of the
  summariser + judge**, both named in verification.md. Plus one live
  before/after section-list comparison for the strand-12 rev. No staging
  deploy; no full live e2e.
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

**Tier 3** — five-to-six prompt surfaces + one additive migration + additive
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
