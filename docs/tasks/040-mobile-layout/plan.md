# Plan: 040-mobile-layout

Defect ids D1–D9, terms and file:line anchors are defined in
[contract.md](contract.md). This plan cites them and adds nothing to scope.

> Plan approved (before implementation): 2026-09-08 · owner.
> Plan-stage adversarial review: not run — Tier 2, tight contract, pattern-following
> plan (per task-cycle-design: Tier 2 runs it on demand only).

Executor marks per AGENTS.md § Agent-side model routing; every `lead` mark carries
its reason. Owner ruling 2026-09-04 (038 plan) applies: judgment-bearing phases go
to `deep-reasoner`; the family flip happens at step 7 when Codex reviews the diff.

**Verify gates (consolidation argued here):** full `make verify` at Phase 0
(build-open baseline) and Phase 6 (step-6 exit) only — every phase is
frontend-only, no schema/ingest contact, so intermediate phases gate on
`make frontend-verify` (typecheck · lint · test · build; `verify-fast` is
backend-only). `pnpm e2e` runs at Phases 2, 5 and 6 — the phases that change
chrome or navigation behaviour, which is what the journey/eye-check specs
exercise; typography-only phases skip it.

## Decisions fixed here (lead seam design)

S1. **One breakpoint, one variant.** Every mobile-only style is a `max-md:` Tailwind
variant on the existing element. No new components except the D2 bottom bar; no
theme changes to `index.css` unless a variant needs a hook (contract § Constraints).

S2. **D2 bottom bar is a sibling, not a portal.** On task routes the shell is a
`h-svh` flex column (`AppShell.tsx:346-352`); the bottom bar renders as its last
child (`max-md:flex hidden`-style gating, `overflow-x-auto`, `print-hide`,
`shrink-0`), reusing `LifecycleBar`'s tab-building logic and labels from
`lib/vocabulary.ts` — the existing `LifecycleBar` gets `max-md:hidden` (or the
bar accepts a class prop). One source of truth for the five tabs; two placements.

S3. **D6 stays one component.** The bottom-sheet behaviour is `max-md:` overrides
on `SheetContent` (`ui/radix/Sheet.tsx:32-36`): `max-md:inset-x-0 max-md:top-auto
max-md:bottom-0 max-md:h-auto max-md:max-h-[45svh] max-md:w-full max-md:border-t
max-md:border-l-0 max-md:starting:translate-y-full max-md:starting:translate-x-0`
(exact classes judged in build). Both consumers inherit; no per-consumer code.

S4. **D9 is a render switch, not a resize listener.** The rail's expand control and
the mobile navigate-to-Agent control are both rendered, visibility gated by
`max-md:`/`md:` classes; the mobile control is a router `Link`/`navigate` to the
task's Agent tab (route exists — contract § Out of scope). No `matchMedia`
subscription unless the double-render breaks a test, judged in build.

S5. **D8 keeps one toggle.** The heading row stays the `<button>`; the mobile
affordance is a second visual element after the collapsed summary inside the same
button/section (`max-md:` shown, heading-row span `max-md:hidden`), so
`aria-expanded` semantics and `useOpenWhenNavigated` are untouched in both
`SectionDisclosure` and `GatheredSection`.

## Phase 0 — Build-open baseline — `lead` (inline)

One command, nothing to brief: full `make verify` on the branch (never build on a
red base).

## Phase 1 — Report page: D3 · D4a · D4b · D5 · D7 — `fast-worker`

Mechanical transcription of an exact spec. Brief carries the exact edits:

1. D3: `max-md:hidden` on the outline nav (`ArtefactOutline.tsx:273`).
2. D4a: title `max-md:text-title` (or the agreed size) at `ArtefactView.tsx:1517`.
3. D4b (**all widths**): restructure `ArtefactView.tsx:1511-1522` so
   `<ArtefactDownload>` renders above the eyebrow+title block (header becomes a
   column; button right-aligned), removing the side-by-side row.
4. D5: `max-md:` size steps appended inside `REPORT_PART_HEADING_CLASS`,
   `REPORT_SECTION_HEADING_CLASS`, `REPORT_BODY_CLASS`
   (`artefactPresentation.ts:11-14`); same step on the hardcoded twin
   `ArtefactOutline.tsx:429` and the `AnnotatedProse` roots
   (`ArtefactView.tsx:975,1007`) and collapsed summary (`ArtefactOutline.tsx:376`)
   where they restate `text-lead`.
5. D7: on the two-column wrapper (`ArtefactView.tsx:1508`) `max-md:px-0
   max-md:gap-0`; on the paper (`L1510`) and its streaming twin (`L1122`)
   `max-md:px-4 max-md:py-6 max-md:my-0 max-md:shadow-none max-md:ring-0`
   (exact utilities judged in build; intent: full-bleed white on mobile).

Done when `make frontend-verify` is green and existing ArtefactView tests pass
(D4b may move DOM order — update selectors, not assertions).

Gate: `make frontend-verify`. Commit.

## Phase 2 — App chrome: D1 · D2 — `lead`

Reason for `lead`: taste-bearing chrome (the two most visible surfaces in the app)
needing mid-course visual steering against the live dev server — fails the
fire-and-forget brief test. Implements S2:

1. D1: global bar (`AppShell.tsx:353-370` + `Nav.tsx` `NavBar`) wraps to two rows
   below md — row 1 logo + BETA on `bg-paper`, row 2 the three `NavItem`s +
   `AccountMenu`; `h-16` becomes per-row heights on mobile only.
2. D2: task bar keeps title + settings; `LifecycleBar` hidden below md; bottom bar
   added per S2 with `overflow-x-auto` and `print-hide`.
3. Task-route shell check: bottom bar must not overlap the scroll pane
   (`AppShell.tsx:426-459`) or the composer; `AppFooter` placement checked at
   390px.
4. Tests: bottom bar renders all five tabs on task routes; global bar still
   renders the three links + account menu (rubric item 7).

Gate: `make frontend-verify` + `pnpm e2e`. Commit.

## Phase 3 — Provenance bottom sheet: D6 — `deep-reasoner`

Judgment-bearing (Radix Dialog anchoring, `starting:` transition variants, scroll
containment) with a machine-verifiable done. Brief: implement S3 in
`ui/radix/Sheet.tsx` only; done when at <768px the sheet opens from the bottom at
≤45svh with the body scrollable and the overlay intact, at ≥768px the DOM and
classes for the right slide-over are unchanged (assert via existing Sheet/claim
panel tests plus one new test for the mobile classes), and `make frontend-verify`
is green.

Gate: `make frontend-verify`. Commit.

## Phase 4 — Expand affordance: D8 — `fast-worker`

Exact spec (S5): in `SectionDisclosure` (`ArtefactOutline.tsx:355-368`) and
`GatheredSection` (`L425-436`): heading-row `Expand +`/`Collapse −` span gains
`max-md:hidden`; when collapsed, an affordance (same `SECTION_EXPAND_LINK_CLASS`
styling) renders after the summary paragraph, `md:hidden`. When expanded on
mobile, the collapse affordance renders at the section end (user request: control
at the end of what it expands). Test: collapsed section on mobile shows the
trailing affordance; toggling still works via the heading row.

Gate: `make frontend-verify`. Commit.

## Phase 5 — Chat rail: D9 — `deep-reasoner`

Judgment-bearing behaviour with a test list. Brief: implement S4 in
`ChatSidePanel.tsx` (mounted `AppShell.tsx:436-440`); done when below md tapping
the rail navigates to the task's Agent tab (no panel expansion) and the expanded
panel state is unreachable, at ≥md behaviour is unchanged; tests cover the mobile
navigate and the desktop expand (rubric item 7); `make frontend-verify` green.

Gate: `make frontend-verify` + `pnpm e2e`. Commit.

## Phase 6 — Live check, evidence, step-6 exit — `lead`

Reason for `lead`: browser-driving the pinned live check and writing the evidence
— adjudication-adjacent, not delegable.

1. The contract-pinned live check: dev server + device toolbar — D1–D9 at 390px on
   a seeded task with a finished report; 768px and 1280px unchanged except D4b;
   the full-chain smoke (open task → five tabs → citation → download).
   Screenshots at 390/768/1280px.
2. `verification.md`: command tails, the manual-check table (defect → 390px
   observation → ≥768px unchanged), diff summary, gaps → `docs/deferred.md`
   (list pages / splash / expanded-chat-on-mobile per contract § Out of scope).
3. Full `make verify` (step-6 exit) + `pnpm e2e`.

Gate: **full `make verify`**. Commit.

## Out-of-plan reminders

- Stop conditions (contract § Stop conditions): the desktop-unchanged invariant
  cannot be held for a defect; a fix needs a dependency; scope grows past D1–D9.
- No ADR expected; if S2/S3 harden into a reusable pattern worth recording, flag
  at step 6, don't write one silently.
- Review (steps 7–10) runs in a fresh conversation with `task-cycle-review`.
