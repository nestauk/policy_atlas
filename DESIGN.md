---
name: Policy Atlas
description: Nesta's evidence-led policy-analysis workspace. Flat paper on a grey desk, one electric-blue cut-corner action per view, every claim traceable.
colors:
  electric-blue: "#0000ff"
  electric-blue-pressed: "#0000d6"
  navy: "#0f294a"
  navy-muted: "#c8d6e6"
  ink: "#1c1c1e"
  grey: "#646363"
  line: "#e4e4e7"
  line-2: "#d3d3d8"
  ground: "#f4f4f5"
  paper: "#ffffff"
  paper-2: "#fafafa"
  green: "#18a48c"
  red: "#eb003b"
  orange: "#ff6e47"
  yellow: "#fdb633"
  purple: "#9a1bbe"
  aqua: "#b6e3e8"
  violet: "#a59bee"
  pink: "#f6a4b7"
  sand: "#d2c9c0"
  blue-tint: "#ececff"
  blue-tint-2: "#f5f5ff"
  green-tint: "#e7f5f2"
  yellow-tint: "#fff6e3"
  red-tint: "#fde8ed"
typography:
  display:
    fontFamily: "Averta, Manrope, Mulish, system-ui, sans-serif"
    fontSize: "36px"
    fontWeight: 800
    lineHeight: 1.15
    letterSpacing: "-0.5px"
  wordmark:
    fontFamily: "Zosia Display, Archivo, Averta, system-ui, sans-serif"
    fontSize: "24px"
    fontWeight: 800
    lineHeight: 1.3
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Averta, Manrope, Mulish, system-ui, sans-serif"
    fontSize: "30px"
    fontWeight: 700
    lineHeight: 1.2
  heading:
    fontFamily: "Averta, Manrope, Mulish, system-ui, sans-serif"
    fontSize: "24px"
    fontWeight: 700
    lineHeight: 1.3
  lead:
    fontFamily: "Averta, Manrope, Mulish, system-ui, sans-serif"
    fontSize: "19px"
    fontWeight: 400
    lineHeight: 1.5
  body:
    fontFamily: "Averta, Manrope, Mulish, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.55
  meta:
    fontFamily: "Averta, Manrope, Mulish, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  caption:
    fontFamily: "Averta, Manrope, Mulish, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.4
  label:
    fontFamily: "Averta, Manrope, Mulish, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 700
    lineHeight: 1.5
    letterSpacing: "0.06em"
rounded:
  none: "0px"
  dot: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "40px"
  nav-height: "64px"
  nav-gutter: "24px"
  reading-column: "780px"
  prose-measure: "44em"
components:
  button-primary:
    backgroundColor: "{colors.electric-blue}"
    textColor: "{colors.paper}"
    typography: "{typography.meta}"
    rounded: "{rounded.none}"
    padding: "11px 18px"
  button-primary-hover:
    backgroundColor: "{colors.electric-blue-pressed}"
    textColor: "{colors.paper}"
  button-primary-entry:
    backgroundColor: "{colors.electric-blue}"
    textColor: "{colors.paper}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "14px 24px"
  button-start-run:
    backgroundColor: "{colors.green}"
    textColor: "{colors.paper}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "14px 24px"
  button-start-run-hover:
    backgroundColor: "#147a6c"
    textColor: "{colors.paper}"
  button-primary-disabled:
    backgroundColor: "{colors.line-2}"
    textColor: "{colors.paper}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.navy}"
    typography: "{typography.meta}"
    rounded: "{rounded.none}"
    padding: "11px 14px"
  button-secondary-hover:
    backgroundColor: "#f0f0f3"
    textColor: "{colors.navy}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.grey}"
    typography: "{typography.meta}"
    rounded: "{rounded.none}"
    padding: "9px 12px"
  button-ghost-hover:
    backgroundColor: "transparent"
    textColor: "{colors.navy}"
  chip-default:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.navy}"
    rounded: "{rounded.none}"
    padding: "4px 10px"
  chip-blue:
    backgroundColor: "{colors.blue-tint}"
    textColor: "{colors.electric-blue}"
    rounded: "{rounded.none}"
    padding: "4px 10px"
  chip-green:
    backgroundColor: "{colors.green-tint}"
    textColor: "#0c6b5a"
    rounded: "{rounded.none}"
    padding: "4px 10px"
  chip-yellow:
    backgroundColor: "{colors.yellow-tint}"
    textColor: "#8a5a00"
    rounded: "{rounded.none}"
    padding: "4px 10px"
  chip-red:
    backgroundColor: "{colors.red-tint}"
    textColor: "{colors.red}"
    rounded: "{rounded.none}"
    padding: "4px 10px"
  card:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
  pane-heading:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.grey}"
    typography: "{typography.label}"
    padding: "14px 16px 10px"
  user-message:
    backgroundColor: "{colors.blue-tint-2}"
    textColor: "{colors.ink}"
    typography: "{typography.lead}"
    rounded: "{rounded.none}"
    padding: "10px 14px"
  input:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.lead}"
    rounded: "{rounded.none}"
    padding: "10px 12px"
  nav-item:
    backgroundColor: "transparent"
    textColor: "{colors.navy}"
    typography: "{typography.lead}"
    padding: "0 0 4px"
  tooltip:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.navy}"
    typography: "{typography.caption}"
    rounded: "{rounded.none}"
    padding: "6px 10px"
  popover:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.meta}"
    rounded: "{rounded.none}"
    padding: "16px"
    width: "384px"
  citation-marker:
    backgroundColor: "{colors.blue-tint-2}"
    textColor: "{colors.electric-blue}"
    typography: "{typography.caption}"
    rounded: "{rounded.none}"
    padding: "0 6px"
---

# Design System: Policy Atlas

## Overview

**Creative North Star: "The Evidence Desk"**

Policy Atlas is a civil-service desk. Sheets of white paper sit flat on a cool grey
ground, separated by hairline rules and labelled in small uppercase pane headings.
Nothing is rounded, nothing glows, nothing floats for effect. The only pen on the desk
is Nesta's Electric Blue, and it is used for exactly one thing at a time: the one
action that moves the work forward, the one active tab, the one citation under the
cursor. Its rarity is what makes it legible.

The system inherits the Nesta visual identity and applies it at tool density. Zosia
Display is the brand voice, not the page voice: it sets the wordmark, the splash
headlines, sheet titles and the system-state headings (interrupted, not found, error).
Page and report titles are Averta Extrabold. Averta carries everything on a
GOV.UK-pattern type scale, a deliberate borrowing: one named size per content role,
body prose never below 16px, a reading measure of 44em. The signature Nesta shape, a
square with one 45° cut corner, is reserved for the primary button, so a reader can
find the way forward on any screen by looking for the cut.

Depth is paper depth. Cards carry a hairline border and a soft navy-tinted ambient
shadow that a reader barely registers. Only overlays (popovers, sheets, toasts) lift
further, and they arrive from their trigger on a strong ease-out, never from nowhere.
Motion marks real data arriving and quiets itself completely under reduced motion.
The confirmed anti-reference is Dashboard SaaS: no rounded cards, no shadow stacks,
no KPI tiles, no badge clutter, no icon soup.

**Key Characteristics:**
- Flat white paper on a `#f4f4f5` grey ground, hairline `#e4e4e7` rules between regions
- Zero border radius everywhere; the 45° cut corner is the single form flourish
- One Electric Blue primary action per view; blue is otherwise a pointer, not a fill
- Averta at seven named sizes, 16px floor, 44em measure; Zosia Display for the wordmark, splash and system-state headings
- Status is always colour plus a word; colour alone never carries meaning; the status mark is a 6px square
- Motion is evidence of data: rise on arrival, glow on a new check-in, breathe while running

## Product design principles

The team's six principles (change behaviour, not just knowledge · give control if wanted ·
earn trust every time · provide detail when needed · assist human judgement · share a
team brain) live in `PRODUCT.md` § Product Principles. Every surface, feature and piece of
copy is judged against them; the visual system below exists to serve them.

## Colors

Nesta's core palette at tool density: one hero, a structural navy, warm-neutral greys, and status colours that appear as pale tints with dark text.

### Primary
- **Electric Blue** (#0000ff): the hero. The one primary button per view, the active nav underline, the active tab rule, citation markers, the square bullet, the "Atlas" half of the wordmark, focus outlines, and the fold mark's shut frame between sheets while it turns for a live run. Pressed state deepens to **Electric Blue Pressed** (#0000d6).
- **Electric Blue Tint** (#ececff): chip fill for blue-toned chips (BETA), with a `#c7c7ff` border; also a list row while it is pressed.
- **Electric Blue Wash** (#f5f5ff): the palest blue. User message bubbles, citation marker fill, menu-item and row hover. Reads as "touched by the reader".

### Secondary
- **Navy** (#0f294a): structural text. Headings, nav links, button labels on secondary buttons, the "Policy" half of the wordmark, sheet titles. Also the splash page ground, where **Navy Muted** (#c8d6e6) carries body copy and **Aqua** (#b6e3e8) replaces blue as the accent (and is the focus ring on the navy hero).
- **The dark plan panel**: the plan document's Navy sheet has its own tokens, so no view writes a hex: **Navy Deep** (#0a1f38, wells and inputs sunk into the panel), **Navy Line** (#1a3a5c, its hairlines), **On Navy** (#e8edf2, its text), **On Navy Soft** (#c5d0dc, its secondary text) and **On Navy Muted** (#97a8bc, its labels and meta). **Electric Blue Pressed** and **Green Pressed** (#147a6c) are tokens too (`bg-blue-pressed`, `bg-green-pressed`).

### Tertiary (status and category)
- **Green** (#18a48c): complete. As a solid fill only on the "go" action that starts a run; otherwise as **Green Tint** (#e7f5f2) with deep green text (#0c6b5a).
- **Yellow** (#fdb633): pending, and the middle tone square (Moderate and Limited strength, Abstract only). **Yellow Tint** (#fff6e3) chips with brown text (#8a5a00). Yellow does not mark a live run: live work is the blue mark (see Status mark).
- **Orange** (#ff6e47): paused or interrupted, the one "waiting on you" colour. The paused status mark, the check-in's rule and glow, and the interrupted-run banner border.
- **Red** (#eb003b): failed, error, and the sensitive-information banner (solid red, white text). Status mark, error text and **Red Tint** (#fde8ed) surfaces.
- **Purple** (#9a1bbe), **Violet** (#a59bee), **Pink** (#f6a4b7), **Sand** (#d2c9c0): Nesta secondaries defined as tokens but unused in the built UI. The evidence-distribution charts use Navy bars on Line grid lines, Electric Blue only on the bar under the pointer. The animated fold mark uses its own pastels (sand #ECC77F, teal #6FBFA7, salmon #F09B80, pink #E8B9C8), which are not theme tokens.

### Neutral
- **Ink** (#1c1c1e): body text.
- **Grey** (#646363): secondary text, pane headings, meta and caption copy, disabled ghost labels. AAA on white.
- **Line** (#e4e4e7): dividers, nav and footer borders, tab rails, table frames.
- **Line 2** (#d3d3d8): card and control borders, disabled fills, locked lifecycle tabs, placeholder bars.
- **Ground** (#f4f4f5): the app background and the task-level nav bar.
- **Paper** (#ffffff): every surface that holds content. **Paper 2** (#fafafa) for a barely-lower sheet and a table row under the pointer.

### Named Rules
**The One Pen Rule.** Electric Blue appears as a solid fill on at most one control per view. Everywhere else it is a rule, a marker or a word.

**The Word Beside the Colour Rule.** A status mark, chip tone or coloured border never stands alone. The label sits next to it in text.

**The Tint-Not-Fill Rule.** Status and category colours appear as pale tints with dark text on chips and surfaces. Solid status fills are reserved for the run-start action (green) and the safety banner (red).

## Typography

**Display Font:** Zosia Display (fallback Archivo, then Averta, then system-ui)
**Body Font:** Averta (fallback Manrope, then Mulish, then system-ui)
**Label Font:** Averta Extrabold, uppercase, tracked 0.06em

**Character:** A geometric humanist pairing with no serif anywhere. Zosia is the brand's short, snappy voice and appears where the product speaks as Nesta: the wordmark, the splash page, sheet titles, and the headings of system states. Averta does everything else, including page and report titles, at a generous 1.55 body line height. The brand source specifies Averta Light for prose; the app uses Regular so the 16px floor stays legible.

Both faces are licensed. Their binaries are never committed to the public repository; they load from `/fonts` when present locally. Every surface must render correctly on the fallback stack, and CI fails if a font binary is tracked.

### Hierarchy
- **Display** (800, 36px, 1.15, tracking -0.5px, Averta): the one statement per page. List-page titles ("Tasks", "Projects"), the New Task question heading and the report title. Drops to Title size below `md`.
- **Wordmark** (800, 24px, tracking -0.02em, Zosia Display): "Policy Atlas" in the nav and splash header.
- **Title** (700 or 800, 30px, 1.2): the "plan ready" heading, splash section headings, and system-state headings (not found, error) in the display face.
- **Heading** (700 or 800, 24px, 1.3): section headings inside a report or pane; the interrupted-run heading in the display face. A report part heading ("Executive summary", "Full report") is Heading, Extrabold, uppercase, tracked on the label token, Navy, at every width; a report section heading is Heading, Lead below `md`.
- **Lead** (400 or 600, 19px, 1.5): ledes, report body prose on desktop, nav links, lifecycle tabs, composer text. Semibold when it is a link or tab.
- **Body** (400, 16px, 1.55): running prose everywhere else. The floor: no sentence renders smaller. Report prose drops from Lead to Body below `md`.
- **Meta** (400 to 700, 14px, 1.5): secondary text, table cells, button labels, toast titles, popover content.
- **Caption** (400 to 600, 12px, 1.4): eyebrows, fine print, tooltip text, citation markers, user email in the account menu.
- **Label** (700 or 800, 14px, uppercase, tracking 0.06em, Grey): pane headings (Extrabold), plan-step and check-in eyebrows (Bold; the check-in eyebrow is Electric Blue), report outline headings. The conversation list, table headers and the settled scope card's group labels use the same treatment at Caption size.
- **Chip** (600, 11.5px): a deliberate off-scale token. Chips sit below caption text (owner ruling).
- **Hero** (`text-hero`, clamp 40 to 68px, 1.02) and **Hero 2** (`text-hero-2`, clamp 28 to 40px, 1.1): the splash page's two responsive headlines, named tokens because the splash persuades rather than operates. Splash prose is Lead.

### Named Rules
**The Sixteen Floor Rule.** Body prose never renders below 16px. Meta and caption sizes are for labels, cells and markers, never for sentences a reader must read.

**The Brand Voice Rule.** Zosia Display speaks as Nesta: wordmark, splash, sheet titles, system-state headings. Page and report titles are Averta Extrabold at Display size. Do not set page titles in Zosia.

**The Named Size Rule.** Every text size is one of the named scale tokens (`text-caption` through `text-display`, and the splash's `text-hero` and `text-hero-2`). No ad-hoc pixel sizes in views; the one exception is the 11.5px chip. Uppercase labels use the label classes in `ui/brand/label.ts` and the `tracking-label` token, never a hand-written tracking.

**The No Medium Rule.** Averta has no 500 weight: a selected row is Semibold, never `font-medium`. The one `font-medium` is an idle Sources subtab, which Averta sets Regular so it reads as greyed (owner ruling).

**The Figures Rule.** Counts, times, years and dates that stand in a column or tick in place are tabular figures, so they line up and never jitter.

**The Middot Rule.** A line of facts joins its fields with " · ". Each dot binds to the field before it (a no-break space), so a wrapped line never starts with a dot; a screen reader hears a comma.

## Layout

The app is full-bleed. A 64px top nav runs the viewport width with a 24px gutter, brand group left and links right; below `md` it wraps to a two-row nav at 16px gutters. Inside a task a second, grey-ground nav bar carries the task name and the five lifecycle tabs (Agent · Result · Sources · Share · History), spaced 20px apart; below `md` the tabs move to a bottom bar that scrolls horizontally and respects the safe-area inset. Task tabs pad their page by the report sheet's 32px margin and keep the page gutters.

**List pages** (Tasks, Projects, a Project) share one header with fixed slots: a context row (the way back on a project, empty on the lists), a title row with the page's one primary right-aligned, and a filters row that is always reserved (the scope switcher at the left, Find and any word control at the right). The title and the list start at the same height on every page, and the header holds only the primary. Below `md` the actions sit above the title.

**The New page** has no eyebrow; its title starts where the lists' titles start. Under the question come the optional fields, each a Body Semibold Navy label, one Body Grey line of help and its control, then the primary alone on its own row at the right (owner ruling). "Project" is always shown: the shared project picker. "Evidence search to start from" (options scoping only) is the shared multi-select of the reader's own finished Evidence searches in the chosen project, disabled until a project is chosen. Picking a search never changes the project; changing the project clears the picks it does not hold.

Content lives in a centred reading column of 780px on list pages and the report. The report page is a paper sheet with 40px horizontal and 36px vertical padding, 32px vertical margin, a hairline Line ring and the paper-weight shadow; below `md` it loses margin, ring and shadow and pads at 16px, so the paper becomes the screen. Prose inside caps at a 44em measure. The longlist takes the full content column instead.

The Agent workspace is a three-region layout: a 48px icon rail on the left (toggle, new chat, active task mark), a scrolling conversation column of about 700px, and a pinned composer at the bottom with a double-cut send button 48px wide and 40px tall. The current chat's mark in the rail sits on a Blue Tint fill. The rail's Task Agent mark is always the still fold mark: no status, no elapsed figure. Popovers are 384px wide (capped at 92vw); sheets are up to 576px from the right edge, and collapse to a bottom sheet of at most 45svh below `md`.

Spacing follows the Tailwind 4px scale. Observed rhythm: 8px between chips and inline items, 16px inside cards and popovers, 20px between nav items, 24px page gutters, 40px report padding. Density is tool density, not marketing density: a list row is one line high with its metadata inline.

## Elevation & Depth

Flat paper with ambient lift only. Surfaces sit on the grey ground and are separated by a hairline border, not by shadow. Cards carry a soft, navy-tinted ambient shadow so faint that it reads as paper weight rather than elevation. Overlays lift further because they are temporary and must read as above the page: popovers, sheets and toasts share one deeper shadow, and the sheet adds a 40% navy scrim. Nothing else casts a shadow. Hover never adds a shadow; it changes colour.

### Shadow Vocabulary
- **Paper weight** (`--shadow-paper`: `0 1px 3px rgba(15,41,74,0.05), 0 8px 24px rgba(15,41,74,0.04)`): cards at rest. Navy-tinted, near-invisible.
- **Sheet edge** (the paper weight plus a 1px Line ring): the report page and the Findings table. It disappears below `md` and in print.
- **Tooltip lift** (`--shadow-tooltip`: `0 4px 16px rgba(15,41,74,0.12)`): tooltips only.
- **Overlay lift** (`--shadow-overlay`: `0 10px 30px rgba(15,41,74,0.14)`): popovers, sheets, toasts, the find dialog and jump to end.
- **Check-in glow** (`0 0 0 6px rgb(255 110 71 / 0.25)` at the animation midpoint): a one-shot Orange ring marking a newly arrived check-in; it fades to nothing.

### Named Rules
**The Hairline First Rule.** Regions are separated by a 1px Line border. A shadow is added only when the surface is temporary and sits above the page.

**The Navy Shadow Rule.** Every shadow is tinted with Navy (`rgba(15,41,74,…)`), never neutral black, so lift stays in the palette. No surface carries Tailwind's grey `shadow-sm` or `shadow-lg`.

## Shapes

Zero radius everywhere. Buttons, cards, chips, inputs, popovers, sheets, toasts and tooltips all have square corners, and so does the status mark: a 6px square, small enough to read as a mark and not a chip.

**The one radius exception**: the plan card's radio is round, a 16px ring with an 8px dot, because a round radio is how people recognise a single choice. Nothing else is rounded.

The signature form is the Nesta cut corner: a 45° clip removing 10px from the top-right of the primary button (8px on the small size). The composer's send button doubles it, cutting both top-right and bottom-left. The green run-start button shares the cut. No other element carries it, which is why the eye can find the way forward on any screen.

Borders are 1px hairlines. Active and selected states are expressed as a 3px bottom rule in Electric Blue (nav, lifecycle tabs, Sources subtabs) or a 2px rule (the Mine / Organisation switcher), never as a filled pill.

**The Focus Rule.** Focus is a 2px Electric Blue outline offset 2px, set once in `index.css` for every focusable element, so no control falls back to the browser's ring. A control that cannot show an outside ring draws it inside: the cut-corner buttons carry a 2px white ring inset 4px, because their clip-path clips anything outside the box; a row flush against its frame insets the blue ring 2px; the white splash button insets a Navy ring; controls on the navy splash hero ring in Aqua.

**The fold mark** is the one piece of geometry with personality: a 17px diamond, a square sheet whose four corners have folded to the centre. It sits before the wordmark in the nav, marks each chat in the conversation rail, and forms the animated constellation on the splash page. It is also the live mark: while a run is live it turns through 36 frames of folding and rotating in its own pastels, snapping shut to solid blue between sheets, in the trace's top line, the run status bar and the section being written (14px in text lines), and the working line (what the agent is doing now) carries it too. It turns only while the stream is open and the run is live, and holds still when the connection is down or motion is reduced. The nav wordmark's mark and the rail's mark never turn; a running task's list row takes the breathing blue square, so every row's mark is one size.

## Components

Precise and unadorned. Hard edges, hairline borders, no decoration. The cut corner is the only flourish. Feedback is a 3% press scale over 160ms on a strong ease-out and a 150ms colour ease; hover states never snap.

### Defined once

**The Defined-Once Rule** (owner ruling). Shared vocabulary is defined once and imported, never re-typed in a view. A surface sets only the spacing and the affordance around a shared piece. A view-level copy of a shared rule (a local tier-to-colour map, a typed-out depth word, a hand-drawn tone square) is a defect, fixed by importing the shared one. Where a surface's own piece serves two views (the longlist's list and grid, the trace and the status bar), it too is written once.

| Home | What it owns |
|---|---|
| `src/index.css` | the tokens, the focus ring, the keyframes and their reduced-motion fallbacks |
| `ui/brand/evidence.ts`, `ui/brand/EvidenceMarks.tsx` | the strength tiers (order, tones, colours, legend, hover); the read depth's words, tones and hovers; the evidence-type formatter (sentence case everywhere); the judge's tier labels and unchecked words; `ToneSquare`, `StrengthMark`, `DepthMark` |
| `ui/brand/taskStatus.ts` | a task's status words (`taskStatusWord`), the row's mark (`taskStatusTone`), `isStale`, a finished walk's words (`READY_WORDS`); the list row, the trace, the status bar and the browser title read them, and the caller adds only the live step |
| `ui/brand/Disclosure.tsx` | the Show / Hide word, the rotating chevron, the open-for-print hook |
| `ui/brand/reference.ts`, `ui/brand/ReferenceUrl.tsx` | the reference line's parts and the source title link; the address without its scheme (in full in the printed References, not in the dossier) |
| `ui/brand/InfoHint.tsx` | the info "i" |
| `ui/brand/Chip.tsx` | the filter chip (`FilterChip`) |
| `ui/brand/list/` | list frames (empty, error, skeleton, the frame and the 40px ghost control) and the foot (`ListFootRow`, `ShowMore`, `Pagination`) for Tasks, Projects, History, All sources and Findings |
| `ui/brand/label.ts` | the uppercase label classes |
| `ui/brand/inlineActions.ts` | the three inline action styles |
| `ui/brand/icons.tsx` | every icon, one 1.5 stroke |
| `ui/brand/CloseButton.tsx` | the close control |
| `ui/brand/Button.tsx`, `ui/brand/PageHeader.tsx` | the button variants; the list-page header and its primary (`PagePrimary`) |
| `ui/brand/Nav.tsx` | the growing rule |
| `ui/brand/Select.tsx`, `ui/brand/MultiSelect.tsx`, `ui/brand/Checkbox.tsx` | the one dropdown, the multi-select, the checkbox |
| `ui/brand/OutlineSwitch.tsx` | the outline switch |
| `ui/brand/BulletList.tsx` | the Electric Blue square bullet list |
| `ui/feedback/RetryCard.tsx` | a standalone Retry |
| `ui/motion/arrivals.tsx` | the arrival rule |
| `lib/dates.ts` | `formatDate(value, form)`: `short` ("5 Nov" this year, "12 Oct 2025" before it), `long` ("6 November 2026", always with its year), `time` ("09:02"). Dates are never relative |
| `lib/format.ts` | `formatCount` (en-GB, "1,234") for every count, range and page number |
| `lib/remembered.ts` | a reader's remembered choices, under one key scheme, `policy-atlas:<name>:<taskId>` |

### Buttons
- **Shape:** square with a 10px top-right cut on primary (8px on small). Secondary and ghost have no cut.
- **Primary:** Electric Blue fill, white Averta Bold at Meta size, 18px horizontal and 11px vertical padding. Hover deepens to #0000d6. Disabled is Line 2 fill with white text, present but inert. One per view.
- **Entry size:** the list pages' primary, the New Task submit and Start run use the same cut shape at Body size: 52px tall, at least 144px wide, 24px side padding, the label centred and never wrapped.
- **Start run:** the one action that starts a search is the entry-size cut shape in Green (#18a48c), hover #147a6c. It is the only green fill in the system and the only non-blue cut corner.
- **Secondary:** transparent, Navy Semibold, 14px horizontal padding, hover fills #f0f0f3.
- **Outline:** the secondary with a 1px Line 2 border on Paper. Pagination, Show more, Download, and the bordered actions inside a check-in or plan card.
- **Outline switch:** joined outline buttons, the chosen one with a Navy border and Navy words, the others Grey; never a fill, which belongs to the one primary. Used for the screening choice, Group by, View as and List / Map.
- **Ghost:** transparent, Grey Semibold, 12px by 9px padding, hover turns Navy. For Cancel and Back to top. A word control in a list header's filters row is the ghost at 40px in Body Semibold.
- **Retry:** a standalone Retry is the small secondary, under the sentence that says what failed.
- **Inline actions**, three styles and no others, each at the size of its line: **Link**, Electric Blue Semibold, underlined on hover ("Sources →", "Read it →"); **Quiet control**, Grey Semibold over a Line 2 underline that turns Navy ("See the plan", "Show steps", "Change"); **Prose link**, Navy, always underlined, blue on hover (legal pages, a source title in a table, a project named on Share).
- **Icon buttons:** a 16px glyph in a 32px box for chrome and a 13px glyph in a 28px box for row actions. One hover, Blue Wash with Navy, and the 3% press. Close is the chrome icon button with a 16px ×; no × glyph in text.
- **Hover / Focus:** colour eases 150ms; active scales to 0.97; focus follows the Focus Rule.
- **Labels:** sentence case, action-oriented ("Start search", "Looks right", "Review the plan"). Default `type="button"`.

### Chips
- **Style:** 1px border, 10px by 4px padding, 11.5px Semibold, square. Default is Paper with Line 2 border and Navy text.
- **Tones:** blue (tint fill, #c7c7ff border, blue text) for BETA and the few tags that mark one item out; soft (Ground fill, Grey text); green, yellow and red as pale tint fills with dark tone text. Every toned chip carries its label in text.
- **Filter chip:** the filled Navy chip with white words and its ×. The words reopen the choice, the × removes it. Used by the Sources filter bar, the multi-select's chosen items and the plan card's scope chips (with a dashed "+ add" beside them).
- **Where chips are not:** a capability on a list row, a table value, a report card, the longlist, a History row, a sheet. These are plain words, a tone square or a marks line.

### Cards / Containers
- **Card:** square, Paper on Ground, 1px Line 2 border, paper weight, 16px padding. A **ruled card** is a Line hairline box with no shadow, for entries inside a page. An empty chip or mark row takes no room.
- **Pane heading:** Label style with an optional right-aligned control; 14px top, 10px bottom, 16px sides.
- **Status mark:** a 6px square, always followed by a word. Still states: Green complete, Orange paused, Line 2 idle, Red failed. Work in progress is Blue and breathing; where the run itself is shown, the turning fold mark stands in its place.
- **Tone square:** the 6px square before a value's word, in the palette's green, yellow and red, the word always beside it; a value outside its vocabulary has no square.
- **Placeholder bar:** a short Line 2 bar, 10px tall, breathing, in the cell or row a running stage will fill. Only while that stage runs and only where the value is absent.
- **A value with a reason** (a type, a strength, a verdict, a partial read depth) shows the reason on hover only, its word over a dotted Grey underline with the help cursor, out of the tab order; the dossier carries the same words.
- **Callout:** a tinted surface for one verdict: Blue Wash checked, Red Tint unsupported, Ground unchecked. A failed turn is a 40% Red Tint surface with a Red Tint border and a Retry.

### Disclosure
- **The chevron:** the 12px glyph, right when shut, turning down over 200ms; Grey, Navy with its control's hover. Never a text triangle.
- **The word:** "Show" / "Hide" as a quiet control after the chevron; "Show all" / "Hide all" for a set; "Show steps" / "Hide steps" on a run. The control stays put when its content opens below it.
- **A collapsible heading holds its button** (the GOV.UK accordion pattern), never the reverse.
- **The fold** eases height and opacity over 200ms. **Print** opens everything and prints no disclosure words.

### Inputs / Fields
- **Style:** Paper fill, 1px Line 2 border, 12px by 10px padding, Lead size, square. The composer textarea grows with content (`field-sizing: content`) between 56px and 240px.
- **Focus:** 2px Electric Blue outline. Splash fields instead turn their border blue.
- **Error / Disabled:** error border Red with a red Body-size message beneath; disabled is Ground fill with Grey text.
- **Bare variant:** the New Task question field has no border or fill. It is Lead text on the paper card, its box holding the question alone.
- **Dropdown:** the one select in the app, styled, never the browser default (owner ruling); no native `<select>` outside the Sources filter bar's own listboxes. The trigger is the field with the chevron, a Navy border while open, at 40px with Body words or 32px with Meta words in a card or panel. The list is the popover, 40px Meta rows, Blue Wash on hover and on the chosen one. A select-only combobox: Enter, Space or an arrow opens it; arrows, Home, End and a first letter move; Enter picks; Escape or a press outside closes and returns focus. On a phone it opens as the popover does, never the platform's picker.

### Navigation
- **Top nav:** 64px, Paper, hairline bottom border. Wordmark left (fold mark, "Policy" Navy, "Atlas" Electric Blue) with a blue BETA chip carrying a tooltip. Links right at Lead Semibold Navy.
- **The growing rule:** one 3px Electric Blue rule under the item, anchored at its left edge, over a transparent border so nothing shifts. On hover and keyboard focus it grows to the item's centre over 200ms and shrinks back on leave. The active item is Extrabold with a full rule; a click carries the half rule on to the right edge. Under reduced motion the rules appear without growing. The top nav, the lifecycle tabs, the Sources subtabs, the Result views' tabs and (at 2px) the Mine / Organisation switcher share it.
- **Lifecycle tabs:** Lead Semibold, Grey idle, Navy active. Locked stages render in Line 2 with a not-allowed cursor and `aria-disabled`, so the whole lifecycle is visible from the first moment. A locked Result view has no note beside it, so the strip stays on one line (and scrolls sideways if it must).
- **Sources subtabs:** idle is Meta Grey at the medium weight, never a faded tint; the active one Extrabold Navy. Until the reader picks one, the Sources tab opens by stage; after that it returns them to their pick on that task (a remembered choice).

### Overlays
- **Tooltip:** Paper, Line 2 border, 10px by 6px padding, Caption Navy, tooltip lift. Scales in from its trigger over 125ms.
- **Popover:** Paper, Line 2 border, 16px padding, Meta Ink, 384px wide (capped at 92vw), overlay lift. Scales in from its trigger over 150ms. Menu items hover to Blue Wash with blue text.
- **Info hint:** a 16px "i" in a 24px target just after the words it explains, Grey turning Navy, the help cursor, focusable and named; a tooltip on hover and focus, a small popover on a tap. It says what a section counts or how far to trust it, in place of a line on the page.
- **Menu:** the popover's tokens, 40px Meta Semibold rows, at least 240px wide, right-aligned under its button; the account menu's one destructive item, Sign out, comes last. It arrives from the button, 4px above its place, over 200ms and leaves in 150ms. Focus moves to the first item and back to the button on close; the arrows, Home and End move; Escape and a press outside close it.
- **Find:** a magnifier at the right of a list's filters row opens a popover with a combobox field: the five most recent until there are words, results 150ms after the last key, the highlight in Blue Wash.
- **The name and its menu:** a task or project header is its name with the owner's quiet chevron control on the name's baseline, and for a task the capability on a Meta Grey line under it (with the project it is in). The menu holds Rename (a field in place at the name's size, Save and Cancel, Enter and Escape), Archive (a two-step confirm in words inside the popover) and, on a task, "Add to project". An archived project offers Rename only; a project is archived from the Projects list. A colleague sees the name alone. A name the backend writes is revealed as streamed text is; the reader's own rename just commits.
- **Sheet:** slides from the right on the drawer curve over 260ms behind a 40% Navy scrim; title in the display face at Lead Bold. Becomes a bottom sheet below `md`. The citation sheet and the dossier keep one type scale: the title, then Body and Meta, no chips and no bold below the title.
- **Toast:** Paper, Line 2 border (Red for errors), 16px padding, overlay lift, bottom-right, rises 8px into place over 200ms.

### Lists
- **The row**, from `md` up, is one line: the name in Body Semibold Navy, taking all the room the other columns leave; the capability as plain Meta Grey text; the status mark and word; the owner where rows can be a colleague's ("You" for the reader); the source count and the date. The capability, status and owner columns are as wide as the widest value the list holds, not the widest any list could hold, so names are never cramped. A failed row's count is "—", never "0 sources". On phones the row is two fixed lines.
- **The status column** has one separator, " · ": "Screening · 28 min" (the step truncates; the timer always shows).
- **The row's accessible name** is its content in order, joined by " · ".
- **Hover** is the Blue Wash; a press deepens to Blue Tint at once; focus is the inset ring.
- **Paging:** a list stops at the server's page and "Show more" asks for the next; focus moves to the first new row.
- **Archived is not a scope** (owner ruling). It is hardly ever used, so it is a quiet toggle at the list's foot, "Show archived" / "Hide archived" (the label carries the state; no `aria-pressed`), on Tasks and Projects alike; the scope holds across it.
- **The row's menu** (owner ruling): its owner gets a three-dot quiet control at the row's right end, a sibling of the row's link, never inside it, in room every row keeps so columns line up. It shows on hover, focus and while open, and always on phones. It opens the header's menu; an archived row offers Rename only. Archiving folds the row away where it stood.
- **States** sit inside the list's own frame: loading is rows at the real height with placeholder bars; empty is a label and one plain sentence; failed is the sentence and "Try again".

### Tables
The search queries and the sources table share one frame; the report's method tables share its rules for figures and row links.
- **The frame:** a Line hairline above and below, rows ruled by Line hairlines, no side borders, no shadow, no header band. Headers are the Label style at Caption size, one line, bottom-aligned; a sortable header always keeps its arrow's slot, so labels share one baseline.
- **Columns are fixed**, so a filter, a sort or a page never moves one. Figures sit right-aligned in one column, the numbers alone.
- **Values are plain words** at Meta, with a tone square where the vocabulary has one. No chips in a table.
- **A row label leads where the destination can filter to it**, as a quiet title link; what cannot be filtered to stays plain, and so do the counts.

## Signature surfaces

Each surface is built from the system above. Only what is distinctive about it, and the rulings that constrain it, are written here.

### Report and citations
The report is a paper sheet in the reading column, its prose at Lead (Body on a phone). Citation markers are small square tags, Caption Semibold, 80% Electric Blue on Blue Wash with a 25% blue border, after the cited words and never before the full stop.

**The page** opens with the plan's refined question as its `h1`, live and committed, so the heading never changes when the report lands; a dated line with the year always written; one action line; one facts line of label and value pairs, never a row of tiles. Then the Executive summary, the Full report, the References and "How the evidence was gathered", in the download's order too. **The expand state** is one per task: a reader who watched the report written finds it open, one who opens it fresh finds it shut, and moving between tabs keeps it as the reader left it.

**Key findings** take the Electric Blue square bullet, centred on the x-height. **Case studies and sources** are ruled cards, each with one marks line (evidence type, strength, facts) shared with the citation sheet. **The method** folds to one funnel line ("312 found → 118 included → 12 cited") and opens to tables whose figures share one column down the section. **References** read as citations (surname and initials, three then "et al."), the address without its scheme on screen and in full in print.

**The marker is the control:** one tab stop per claim, named for what it opens. The citation sheet shows the claim behind the sheet's only coloured rule, the judge's one verdict led by the blue fold-mark diamond (the product's AI judgement), then one box per source, counting sources, never quotes, the quoted words in Yellow Tint.

**Headings:** the question is the `h1`; the parts, the References and the method `h2`; sections and cards `h3`. A page without parts sets its sections at `h2`.

**Contents:** a sticky sidebar from `md` up marks the section being read; below `md` it is a closed disclosure under the title.

**Print** drops the chrome, the colour and every disclosure word, prints markers as black numbers, and splits no entry across pages.

**The live page is the report page:** the same components in the same order, the committed-only parts absent with no placeholder. A writer's citation shows as a muted chip until its section is checked; blue means checked. While claims are checked, the muted chips pulse blue one after another in reading order, a narrow pulse with a wide stagger so the order shows. A section being written names the sources the writer is drawing on. The committed report replaces the draft in place: scroll and open sections hold, the draft layer fades off, and the numbered markers never flash.

### The run trace and the run status bar
**One card** in the Task Agent thread shows a run from start to end; the ended state, and any past run, is the same card. It reads as a table: words left, counts and times right-aligned in tabular figures, a link per row to the view that step filled, running and done. A scoping walk links like an Evidence search wherever it does the same work. The top line is the live mark and state word ("Running", "PAUSED · waiting on you", "REPORT READY", "FAILED") with the run's time and, when it ended well, its one destination. The step in progress breathes with its blue square while its label holds still; a step that lands keeps its place. Ended, the rows fold behind "Show steps". It is not a landmark and has no live region; a screen reader hears the current step from the card.

**The run status bar** says the same words on every tab but Agent, only while a run is live or paused, and steps aside while the sidebar shows the Task Agent. It is two controls: the words open the Task Agent, and a link goes to the running step's view when the reader is elsewhere. The time and link stay in view; the words truncate. While the stream reconnects, the bar's frame carries the reconnecting line on Yellow Tint instead. It eases open and shut when the run or the stream starts or stops, and is set at a cut on a tab switch. Its live region stays quiet while a trace is mounted, so a change is announced once.

**Nothing else shows the run:** the Result tab carries a small navy square when something landed unseen (the Sources tab never does), and the browser title says "● Report ready".

### Plan card and check-ins
A plan step is a card under one stepper line ("Plan · decision 2 of 3 · Scope") counting only the decisions the planner asks. Its radio list keeps the planner's order with no "Recommended" word and no pre-selection; the card's one green Start button starts the run. The scope card changes through its filter chips and records with one "Looks right".

**A settled part takes the user's side:** the user bubble's surface with a 2px Green rule on its right edge and the outcome in deep green bold, with a quiet "Change" while it is the newest proposal. It settles the moment the user chooses, before the agent replies, in one container that eases to its new size and indent.

**A pending check-in** is a card with a 2px Orange left rule, the question as its title, the suggested option first, a closed "Or steer in your own words" and one "Stop the run". Its Orange ring blooms once as it arrives; its confirm step eases the card to its new height. Answered, it eases away and the answer appears in the run's block; if the answer fails it comes back open. **The baseline gate** reads as a check-in and, decided, takes the settled card's look, said once.

User messages are indented 32px in a Blue Wash bubble with a 1px Blue Tint border; agent messages are plain Lead prose at the 44em measure.

### The search queries
At the top of All sources. While the search runs, the queries are a live table grouped by database (Overton first), each query's count a placeholder bar until it returns; the sources table stays hidden until its first results land. When the search ends, the block folds into one line above the filter bar, because the search came before the filtering, so the filter bar reads as the table's own head. The whole line ("Search queries · Found with 12 queries and 3 citation passes · Show"; a pass that looks up cited works counts as a citation pass) is the disclosure, opening the same table as the live one. Every query and pass links to the sources it found.

### The sources table and the dossier
**The filter bar** holds filters only, above the table it scopes, every control a 32px outline box: the screening choice alone on the first row as an outline switch, the facets wrapping on the second, an applied filter a filter chip whose × is named for what it clears. The view has no primary: the table has no single forward action. The foot line holds Download CSV at the left and the page size, count and page controls at the right; the page size is remembered per task.

**The table** has six fixed columns whose widths follow the view's own column, not the window; in a narrow column each source becomes a stacked row in the same markup, with a "Sort" select. The title is the way into the dossier and the row's main tab stop. Strength tones: Green for Very strong and Strong, Yellow for Moderate and Limited, Red for Weak and Unrated. The read depth links "Full text" to the document itself; a cited source says "Cited" under it. While stages run, each column waits on its own stage with placeholder bars and fills as values land.

**Themes** show their final layout as soon as they are found, counts fading in when the landscape commits, nothing reordering. **The dossier** is a sheet on one type scale: the reference line as the References read it, a ruled list of facts, then each block under a sentence-case label, a model-written description labelled "AI description".

### Charts (Landscape)
Ranked bars are a real table: label, Navy bar, value at the bar's end; Grey for missing data and folded tails. The hovered bar turns Electric Blue, with no row wash. **A row leads somewhere when it can:** a type, a country, a year or a funnel stage opens All sources filtered to it; what cannot be filtered to takes no hover. **Where sources were published** says what it counts in an info hint and offers List or Map, the list the keyboard's path; the map is a five-step Navy log scale. **Publication years** are Navy columns where a drag chooses a range and a keyboard listbox does the same, with a hidden table for screen readers. Charts never animate; colour is the whole state. A section carries a count only when it differs from the population.

### The longlist (Options scoping)
**One page** from the first row of the build to the finished list, in the full content column, with no contents sidebar and no stage line: the run status bar says what the walk is doing, so one fold mark turns per screen. No chips on the list.

**The row is the same all the way;** the finished list only adds controls. The name is the row's only weight; under it one sentence and one Meta Grey line of fixed fields in a fixed order. **An excluded row** keeps the same sizes, and grey alone marks it, never red. One short phrase says who excluded it; the constraint's words and the reason are the card's. Shortlisted rows come first in each group.

**The shortlist toggle** is one circled check everywhere (list, grid, card, Shortlist page): a Grey outline, or filled Electric Blue when the option holds a place. A press changes only its own toggle, at once, held until the read agrees. Exclude lives on the card and on a group's heading, not on rows.

**Groups:** the finished list opens with every group shut (owner ruling). One group heading serves both views, with every count and Show / Hide on one right edge and the group actions in one column with the row toggles. Lever types no option carries are named once at the foot, never as an empty group. Excluded is a section of groups, not a group. **Only a regroup moves rows** (a View Transition, the app's chrome still above it); a toggle or a single exclusion updates in place, and the list never blanks.

**The option card** reads at the report's scale, in three blocks: what it is, Evidence, What it could take; only the last and the documents list fold. An exclusion stands at the top. Notices lead with a tone word ("Does not meet:" in Red, never "Breaks"). What it could take is Policy Atlas's estimate, behind an info hint, marked relative to the rest of the longlist; no tint carries good or bad.

**The Shortlist page** has one primary at its end; a control that is off says why in a line under it, never only in a tooltip. Its "Not covered" note is kept current without a call per change: rewritten once on opening and once 3s after the reader's last change, never from the longlist. **On the public link** every longlist view is read-only.

### Share
Who can read the task, in order of consequence: Public link, Organisation, Projects, each a settings row on one card. Share has no primary: access changes are settings, so every control is the outline button and nothing carries the cut or a blue fill. Making a task public takes a second press inside the section, not a modal; the copied link confirms in place, not with a toast. A task in a project follows the project and offers no visibility control. A colleague sees the states without the controls.

### History
The task's record, oldest first, grouped by day under a sticky day heading. A row is the time and one sentence naming who acted ("You" only for the reader). No chips: only a failure keeps the Red square. Each run folds to one line with "Show steps". Rows wait for every read: never half a list.

## Motion

Motion is evidence of data: it marks something arriving, a state changing or a reader's action, and quiets itself under reduced motion.

### Vocabulary
- **Curves:** the strong ease-out (`--ease-out-strong`, `cubic-bezier(0.23, 1, 0.32, 1)`) for everything; the drawer curve (`--ease-drawer`, `cubic-bezier(0.32, 0.72, 0, 1)`) for sheets and docked panels.
- **Durations:** 125ms tooltip in; 150ms colour, popover in, a fade out, a word batch's fade; 160ms press; 200ms a disclosure, a fold, a menu, the status bar, a sheet leaving; 260ms a sheet or docked panel arriving; 300ms an arrival, a height easing, a value landing.
- **Rhythms:** one 1.6s breathe. Skeletons and placeholder bars go from opacity 1 to 0.25; the 6px mark adds a scale to 0.8; a breathing line of words goes only to 0.6 so it stays readable. A page never shows two rhythms.

### Rules
- **The arrival:** a block that appears after a view's first paint rises 8px and fades in over 300ms. Opening a view, the sidebar or a reload shows what is there without motion, because motion on opening a view marks navigation, not data. A block keeps its identity, so a streamed turn becoming the stored one appears in place.
- **Make room, never jump:** a container that grows eases to its new height, and anything pinned to its end follows the eased box; an inner easing box eases first and the outer takes only the rest. In the Task Agent thread each turn is one eased block. Not on the first paint or a task switch; a shrink passes straight through.
- **Paced text:** streamed words are revealed at a steady pace, whole words only, each batch fading in; settled paragraphs are frozen. The report, replies, chats and backend-written names all use it. A revision that shortens the text holds its height until it regrows. The page follows the text only for a reader already at the end. No caret. Under reduced motion the fade goes and the pace stays.
- **A decision card lays itself out:** its chip groups and radio rows fade up 4px in turn over 200ms, 80ms after the card and 40ms apart, capped at the sixth, clickable throughout.
- **Values land softly:** a value or row that lands while a stage runs fades in place, opacity only, so a table never shifts; found themes fade in 40ms apart.
- **Settle on the reader's choice:** a card the reader answers settles at once, before the server replies.
- **Leaving:** a sheet leaves along its own edge, faster than it came. The plan document arrives from the edge it docks to (or rises in place when centred), leaves the way it came, closes on Escape and on a press outside, and returns focus to its opener.
- **Stays still:** ticking clocks and live counts, the activity words within a step, the rail's mark, the nav wordmark, the task list, tab switches and the sidebar, charts, keyboard actions and settled history.
- **Reduced motion:** every move, fade and ease becomes a cut. Breathing marks and bars hold still. Paced text keeps its pace.

## Do's and Don'ts

### Do:
- **Do** put exactly one Electric Blue cut-corner primary on each view, and reserve the cut for it, the green run-start button and the double-cut send button.
- **Do** separate regions with 1px Line hairlines; add shadow only to temporary overlays.
- **Do** pair every status colour with its word: mark plus label, chip tone plus text.
- **Do** use the named type scale and keep every sentence at 16px or above; drop report prose from Lead to Body below `md`.
- **Do** tint status colours (green, yellow, red tints with dark text) rather than filling with them.
- **Do** animate only to mark real data arriving (a pulse only where a running stage will put a value), and quiet every animation under `prefers-reduced-motion`.
- **Do** render the locked lifecycle stages so the whole journey is visible; make them inert with `aria-disabled`.
- **Do** write labels in sentence case as actions, with just enough text.
- **Do** import shared words, tones and marks from their home; never re-type them in a view.

### Don't:
- **Don't** round any corner except the plan card's radio; the status mark and the tab's new-content mark are 6px squares.
- **Don't** stack shadows, add hover shadows, or use neutral black shadows; every shadow is navy-tinted.
- **Don't** build dashboard SaaS chrome: KPI tiles, rounded cards, badge clutter, icon-only sidebars without labels.
- **Don't** use Electric Blue as a second fill on the same view, or as a background wash for whole regions.
- **Don't** commit font binaries, or design a surface that only works when Averta and Zosia are present.
- **Don't** introduce an ad-hoc pixel font size; add a named token instead and register it in the merge config.
- **Don't** let colour carry meaning alone, and don't ship a chip, mark or border without its text label.
- **Don't** pair blue and orange as a meaningful contrast (Nesta guidance for Scotland-facing work).
