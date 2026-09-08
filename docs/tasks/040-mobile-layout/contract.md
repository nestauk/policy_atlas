# Task contract: 040-mobile-layout

One implementation slice: make the app usable on narrow (phone) screens without changing
the desktop or tablet rendering.

> **Status:** approved. Contract approved (before planning): 2026-09-08 · owner ·
> Plan approved (before implementation): 2026-09-08 · owner · ADR: none expected.

## Goal

On screens narrower than 768px the app is currently squeezed: the header crams five
elements into one 64px line, the report title wraps one word per line and collides with
the download button, headings and body text are oversized for the viewport, the lifecycle
tabs are hard to reach, and the report wastes horizontal space on its gray frame. This
slice fixes the nine numbered defects below for narrow screens. Screens at 768px and wider
(desktop and iPad) must render unchanged, with one deliberate exception (D4b, all widths,
owner-approved 2026-09-08).

## Deliverable

A PR on `task/040-mobile-layout` that lands the mobile layout. Shipped = all nine defects
fixed at 390px viewport width, desktop/tablet visually unchanged (except D4b), and
`make verify` green.

## Terms

| Term | Meaning |
|---|---|
| **mobile** | Viewport narrower than Tailwind's `md` breakpoint (768px). All mobile-only styling in this slice uses the `max-md:` variant. |
| **global bar** | The first `NavBar` in `AppShell.tsx` (L353-370): logo + BETA chip, the New Task / Tasks / Projects links, and the account menu. |
| **task bar** | The second `NavBar` in `AppShell.tsx` (L371-409): task title + `LifecycleBar`. Shown on task routes only. |
| **LifecycleBar** | The five lifecycle tabs — Agent, Result, Sources, Share, History — `ui/brand/LifecycleBar.tsx`, labels from `lib/vocabulary.ts`. |
| **paper** | The white report surface: `<main class="artefact-page … bg-paper px-10 py-9 shadow-sm ring-1 ring-line">`, `ArtefactView.tsx` L1510. Sits on the gray `--color-ground` page background. |
| **outline** | `ContentsSidebar` in `ArtefactOutline.tsx` (L230-322): the report's table-of-contents nav. Left column on ≥md; stacks full-width above the paper below md today. |
| **provenance sheet** | The Radix slide-over in `ui/radix/Sheet.tsx`, used by both the claim panel and the source dossier in `ArtefactView.tsx`. Slides in from the right at all widths today. |
| **chat rail** | The collapsed state of `ChatSidePanel` (`views/workspace/chat/ChatSidePanel.tsx`): a 48px vertical strip; expanding it opens a 280–640px left panel. |
| **type scale** | The named font sizes in `index.css` `@theme` (L63-76): caption 12 · meta 14 · body 16 · lead 19 · heading 24 · title 30 · display 36 (px). |

## Defects (one numbering, used by scope, plan and rubric)

| # | Surface (file:line) | Broken on mobile | Fix |
|---|---|---|---|
| D1 | Global bar, `AppShell.tsx:353-370`, `ui/brand/Nav.tsx` | Logo + BETA + three nav links + account icon squeezed into one 64px row. | Mobile: two rows — row 1 logo + BETA on white; row 2 New Task / Tasks / Projects + account icon. ≥md unchanged. |
| D2 | Task bar / `LifecycleBar`, `AppShell.tsx:371-409` | Tabs share the top bar with the title; cramped and far from the thumb. | Mobile: hide `LifecycleBar` in the task bar; render the same five tabs as a bottom bar, horizontally scrollable (`overflow-x-auto`) if too narrow. ≥md unchanged. |
| D3 | Outline, `ArtefactOutline.tsx:273` | Stacks full-width above the report, pushing content down. | Mobile: hide the outline entirely. ≥md unchanged. |
| D4a | Report title, `ArtefactView.tsx:1517` | `text-display` (36px) wraps roughly one word per line. | Mobile: smaller title (≈`text-title`/30px or below, judged in build). ≥md unchanged. |
| D4b | Download button row, `ArtefactView.tsx:1511-1522` | Button shares the title row; overlaps the wrapping title. | **All widths:** move the download button above the title block (owner decision 2026-09-08 — deliberate desktop change). |
| D5 | Report typography, `views/artefactPresentation.ts:11-14` (+ hardcoded twin `ArtefactOutline.tsx:429`) | Part headings 28px, section headings 24px, body 19px — oversized for a phone. | Mobile: part ≈22px, section ≈20px, body 16px, via `max-md:` in the shared constants. ≥md unchanged. |
| D6 | Provenance sheet, `ui/radix/Sheet.tsx:15-65` | Slides from the right and covers the full screen width. | Mobile: bottom sheet — anchored to the bottom edge, `max-h` under half the viewport (≈45svh), slide-up. Both consumers (claim panel, source dossier) inherit. ≥md unchanged. |
| D7 | Paper + wrapper, `ArtefactView.tsx:1508-1510` (and streaming twin L1122), `listPageChrome.ts` | Gray frame + `px-6` wrapper + `px-10` paper padding waste ~30% of a 390px screen. | Mobile: full-width paper — drop outer padding, ring and shadow; reduce paper padding (≈`px-4 py-6`). ≥md unchanged. |
| D8 | Expand control, `ArtefactOutline.tsx` `SectionDisclosure` (L355-368) and `GatheredSection` (L425-436) | "Expand +" sits beside the section heading and crowds it. | Mobile: hide the heading-row control; show the expand affordance at the end of the collapsed summary instead. Heading row stays tappable. ≥md unchanged. |
| D9 | Chat rail, `ChatSidePanel.tsx`, mounted `AppShell.tsx:436-440` | Expanding opens a ≥280px panel — unusable beside content on a 390px screen. | Mobile: tapping the rail navigates to the Agent tab instead of expanding. ≥md keeps the expanding panel. |

## Owner amendments (2026-09-08, after the D1–D9 build)

Same slice, same rules (mobile = `max-md:`, ≥768px unchanged unless said):

| # | Surface | Fix |
|---|---|---|
| A1 | New Task view (`NewTaskView.tsx`) | Mobile: smaller eyebrow/title/body type; column uses full width (was `max-w-[50vw]`) — also stops the "Coming soon" chip crowding the row labels. |
| A2 | Task list rows (`TaskListRow.tsx`, `listPageChrome.ts`) | Mobile: rows wrap — title takes the whole first line, metadata (capability, status, sources, date) flows below; fixes hidden project/title and overflowing right columns. |
| A3 | Project list rows (`ProjectsView.tsx`) | Same multi-line treatment. |
| A4 | Global bar row 2 (`AppShell.tsx`, `Nav.tsx`) | Mobile: nav links left-justified at default gap (not spread); account icon moves up to the logo row, top-right. Desktop DOM/visuals unchanged. |
| A5 | Sources sub-tabs + Key-theme filter (`SourcesLayout.tsx`, `SourcesView.tsx`) | Mobile: smaller tab type (`text-caption`), tighter padding; the theme `<select>` width capped so long theme names can't overflow. |
| A6 | Chat rail on mobile (`ChatSidePanel.tsx`) | **Supersedes D9's strip:** below md the rail hides with no stand-in — the bottom bar's Agent tab is the way in. Desktop unchanged. |

## Read first

- [docs/specs/vocabulary.md](../../specs/vocabulary.md) — tab and nav labels (D1, D2) come
  from `lib/vocabulary.ts`; labels must not be renamed by this slice.
- [docs/specs/product.md](../../specs/product.md) — product surface overview.

## Scope / Out of scope

- **In:** `frontend/src/views/AppShell.tsx`, `ui/brand/Nav.tsx`, `ui/brand/LifecycleBar.tsx`,
  `ui/radix/Sheet.tsx`, `views/ArtefactView.tsx`, `views/ArtefactOutline.tsx`,
  `views/artefactPresentation.ts`, `views/listPageChrome.ts`,
  `views/workspace/chat/ChatSidePanel.tsx`, plus their tests. `index.css` only if a
  `max-md:` variant needs a theme hook.
- **Out:** desktop/tablet (≥768px) rendering — must stay pixel-identical except D4b. No
  label/vocabulary changes. No backend, API, schema or routing changes (D9 uses the
  existing Agent-tab route). No chat panel redesign beyond D9. Splash page, list pages
  (Tasks/Projects) and Sources sub-tabs: only what D1/D2/D7 chrome touches, no dedicated
  mobile pass — gaps go to `docs/deferred.md`.

## Constraints & approval gates

- No new dependencies. No schema, auth, egress, CI or public-interface changes. No
  generated-file edits (`openapi.json`, `api/gen/types.ts`).
- All mobile styling via Tailwind `max-md:` variants (or an equivalent single media query)
  — no JS viewport listeners unless a behaviour (D9) cannot be expressed in CSS; D9 may
  use a matchMedia check or CSS-hidden alternative rendering, judged in build.
- `make font-guard` and the print stylesheet (`index.css` `@media print`) must stay green —
  D2's bottom bar must carry `print-hide` semantics like the other nav chrome.

## Public / private boundary

All artefacts in this slice are public-safe (UI code, layout screenshots of seeded dev
data). No source text or credentials involved.

## Model route

n/a — no inference-bearing changes.

## Disciplines binding this slice

Repo defaults apply (status markers, flag-don't-drop, deferred seams to
`docs/deferred.md`). Nothing slice-specific beyond the desktop-unchanged invariant.

## Stop conditions

Halt and escalate when: a fix needs a dependency or scaffold change; the
desktop-unchanged invariant cannot be held for some defect; scope grows past the nine
defects; or the token budget is spent.

## Acceptance checks

- `make verify` green (includes `frontend-verify`: typecheck · lint · test · build).
- **Live manual check (contract-time pin):** dev server + browser device toolbar, scoped
  to the changed surfaces — at **390px**: each defect D1–D9 shows its fixed behaviour on a
  seeded task with a finished report; at **768px and 1280px**: header, task bar, report
  view, provenance sheet and chat panel are visually unchanged except D4b. One cheap
  full-chain smoke: open a task, switch all five tabs, open a citation, download the
  report. Estimated wall time ≈15 min. No full e2e run for this slice.
- Component tests updated where behaviour changed (D2 bottom bar renders the five tabs;
  D9 rail navigates on mobile).

## Verification evidence expected

In [verification.md](verification.md): command results, the manual-check table (defect →
390px observation → ≥768px unchanged confirmation), screenshots at 390/768/1280px,
diff summary, known gaps.

## Risk tier & review focus

**Tier 2** — feature slice, UI-only, no hard gates. Review: contract verifier + tests +
human review. Focus: the desktop-unchanged invariant (the easiest thing to silently
break), missed defect coverage, and scope creep into a general redesign.
