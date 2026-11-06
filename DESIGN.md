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
- **Electric Blue** (#0000ff): the hero. The one primary button per view, the active nav underline, the active tab rule, citation markers, the key findings' square bullet (round 11), the "Atlas" half of the wordmark, focus outlines, and the fold mark's shut frame between sheets while it turns for a live run (task 058; owner 2026-11-05). Pressed state deepens to **Electric Blue Pressed** (#0000d6).
- **Electric Blue Tint** (#ececff): chip fill for blue-toned chips (BETA) and the border of the same chips at `#c7c7ff`; also a list row while it is pressed (round 10).
- **Electric Blue Wash** (#f5f5ff): the palest blue. User message bubbles, citation marker fill, menu-item hover. Reads as "touched by the reader".

### Secondary
- **Navy** (#0f294a): structural text. Headings, nav links, button labels on secondary buttons, the "Policy" half of the wordmark, sheet titles. Also the splash page ground, where **Navy Muted** (#c8d6e6) carries body copy and **Aqua** (#b6e3e8) replaces blue as the accent (and is the focus ring on the navy hero).
- **The dark plan panel** (task 058 consistency pass): the plan document's Navy sheet names its own tokens, so no view writes a hex: **Navy Deep** (#0a1f38, wells and inputs sunk into the panel), **Navy Line** (#1a3a5c, its hairlines), **On Navy** (#e8edf2, its text), **On Navy Soft** (#c5d0dc, its secondary text) and **On Navy Muted** (#97a8bc, its labels and meta). **Electric Blue Pressed** (#0000d6) and **Green Pressed** (#147a6c) are tokens too (`bg-blue-pressed`, `bg-green-pressed`).

### Tertiary (status and category)
- **Green** (#18a48c): complete. As a solid fill only on the "go" action that starts a run; otherwise as **Green Tint** (#e7f5f2) with deep green text (#0c6b5a).
- **Yellow** (#fdb633): pending. **Yellow Tint** (#fff6e3) chips with brown text (#8a5a00). (Until task 058 the running dot and the check-in glow were yellow; a live run is now the blue square mark and the glow is orange.)
- **Orange** (#ff6e47): paused or interrupted. Status mark, the check-in's rule and glow, and the interrupted-run banner border.
- **Red** (#eb003b): failed, error, and the sensitive-information banner (solid red, white text). Status mark, error text and **Red Tint** (#fde8ed) surfaces.
- **Purple** (#9a1bbe), **Violet** (#a59bee), **Pink** (#f6a4b7), **Sand** (#d2c9c0): Nesta secondaries defined as tokens but unused in the built UI. The evidence-distribution charts use Navy bars on Line grid lines, Electric Blue only on the bar under the pointer. The animated fold mark uses its own pastels (sand #ECC77F, teal #6FBFA7, salmon #F09B80, pink #E8B9C8), which are not theme tokens.

### Neutral
- **Ink** (#1c1c1e): body text.
- **Grey** (#646363): secondary text, pane headings, meta and caption copy, disabled ghost labels. AAA on white.
- **Line** (#e4e4e7): dividers, nav and footer borders, tab rails.
- **Line 2** (#d3d3d8): card and control borders, disabled fills, locked lifecycle tabs.
- **Ground** (#f4f4f5): the app background and the task-level nav bar.
- **Paper** (#ffffff): every surface that holds content. **Paper 2** (#fafafa) for a barely-lower sheet.

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
- **Heading** (700 or 800, 24px, 1.3): section headings inside a report or pane; the interrupted-run heading in the display face.
- **Lead** (400 or 600, 19px, 1.5): ledes, report body prose on desktop, nav links, lifecycle tabs, composer text. Semibold when it is a link or tab.
- **Body** (400, 16px, 1.55): running prose everywhere else. The floor: no sentence renders smaller. Report prose drops from Lead to Body below `md`.
- **Meta** (400 to 700, 14px, 1.5): secondary text, table cells, button labels, toast titles, popover content.
- **Caption** (400 to 600, 12px, 1.4): eyebrows, fine print, tooltip text, citation markers, user email in the account menu.
- **Label** (700 or 800, 14px, uppercase, tracking 0.06em, Grey): pane headings (Extrabold), plan-step and check-in eyebrows (Bold; the check-in eyebrow is Electric Blue), report outline headings. The conversation list and the settled scope card's group labels use the same treatment at Caption size.
- **Chip** (600, 11.5px): a deliberate off-scale token. Chips sit below caption text by owner ruling.
- **Hero** (`text-hero`, clamp 40 to 68px, 1.02) and **Hero 2** (`text-hero-2`, clamp 28 to 40px, 1.1): the splash page's two responsive headlines, named tokens because the splash persuades rather than operates (lead ruling P5). Splash prose is Lead.
- **Report part heading** ("Executive summary", "Full report"): Heading, Extrabold, uppercase, tracked on the label token, Navy, at every width; a section heading is Heading, Lead below `md` (task 058 consistency pass).

### Named Rules
**The Sixteen Floor Rule.** Body prose never renders below 16px. Meta and caption sizes are for labels, cells and markers, never for sentences a reader must read.

**The Brand Voice Rule.** Zosia Display speaks as Nesta: wordmark, splash, sheet titles, system-state headings. Page and report titles are Averta Extrabold at Display size. Do not set page titles in Zosia.

**The Named Size Rule.** Every text size is one of the named scale tokens (`text-caption` through `text-display`, and the splash's `text-hero` and `text-hero-2`). No ad-hoc pixel sizes in views; the one exception is the 11.5px chip. Uppercase labels use `LABEL_CLASS`, `PANE_LABEL_CLASS` or `CAPTION_LABEL_CLASS` (`ui/brand/label.ts`) and the `tracking-label` token, never a hand-written tracking. Averta has no 500 weight: a selected row is Semibold, never `font-medium`; the one `font-medium` is an idle Sources subtab, which Averta sets Regular so it reads as greyed (owner, round 11).

## Layout

The app is full-bleed. A 64px top nav runs the viewport width with a 24px gutter, brand group left and links right; below `md` it wraps to a two-row nav at 16px gutters. Inside a task a second, grey-ground nav bar carries the task title and the five lifecycle tabs (Agent · Result · Sources · Share · History), spaced 20px apart; below `md` the tabs move to a bottom bar that scrolls horizontally and respects the safe-area inset.

**List pages** (Tasks, Projects, a Project) share one header with fixed slots (task 058, lists polish): a 24 px context row (the way back on a project, empty on the lists), a 52 px title row with the page's one primary right-aligned (round 11: the header holds only the primary), and a filters row always reserved at 40 px (the scope switcher at the left; at the right the admin's note and the Find magnifier on the lists, the magnifier and Make private on a project), so the title and the list start at the same height on every page. Below `md` the actions sit above the title and the gutters are 16 px. A list row is 56 px; on phones it is two fixed lines, 84 px, without the capability, the owner and the source count. The New page's title starts where the lists' titles start (44 px top padding, no eyebrow above it).

**Task tabs** pad their page `py-8` (32 px, the report sheet's margin) and keep 24 px gutters from `md` up, 16 px below.

Content lives in a centred reading column of 780px on list pages and the report. The report page is a paper sheet with 40px horizontal and 36px vertical padding, 32px vertical margin, a hairline Line ring and Tailwind's small shadow (not the card shadow); below `md` it loses margin, ring and shadow and pads at 16px, so the paper becomes the screen. Prose inside caps at a 44em measure.

The Agent workspace is a three-region layout: a 48px icon rail on the left (toggle, new chat, active task mark), a scrolling conversation column of about 700px, and a pinned composer at the bottom with a double-cut send button 48px wide and 40px tall. The current chat's mark in the rail sits on a Blue Tint fill. The rail's Task Agent mark is the still fold mark, always, named "Task Agent": no hover status, no elapsed figure, nothing turns there (owner, round 8, reversing round 6). On every tab but Agent and only while a run is live or paused, the run status bar sits at the top of the page's column (task 058, owner rounds 7 and 8), and steps aside while the Task Agent is open in the sidebar, whose trace says the same words, returning when the sidebar shuts or shows another chat (lead, round 8): it starts after the rail from `md` up, so it never runs under the sidebar to the window's edge, and spans the screen below `md`. One line on Paper with 10px vertical padding over a Line hairline: the turning fold mark on the first line (the 6px Orange square while a check-in waits), the step's label in Meta Semibold Navy and what it is doing in Meta Grey ("**Writing** · Section 3 of 7 · Costs and funding"; "**Paused** · a check-in is waiting on you"; while searching, the query that is out, cut at about 60 characters by the server), and the run's elapsed time right-aligned in Grey tabular figures. The status bar is two controls on one bar (owner, round 9). The words are a button, the way to the agent (owner, round 8, reversing contract D8's "status only"): they open the Task Agent in the sidebar, or the Agent tab below `md`; hover Paper 2, the blue focus ring inset, named "Open the Task Agent: <words>". After the time, the running step's view as a link in Electric Blue Semibold ("Sources →", "Landscape →", "Themes →", "Report →", the same link the trace's running row carries), shown only while the reader is not on that view and not while paused; keyboard order words, then the link. The words truncate on one line and the time and the link stay in view, phones included. While the live stream reconnects the bar's frame carries the reconnecting line in place of its words, on every tab but Agent and whatever the run's state (owner, round 11): the same 10px vertical padding and Meta size, its words where the bar's words start, on Yellow Tint over a Yellow hairline, so it starts after the rail and never runs under it; the bar's words come back with the stream. On the Agent tab the same line sits at the top of the Task Agent's column, after the workspace rail. It opens and closes over 200ms on the strong ease-out when the run starts or ends, the stream drops or returns, or the sidebar takes the Task Agent, so the page eases rather than jumps; a tab switch sets it at a cut (navigation, tens of times a day). Its words rise in when the step changes; both hold still under reduced motion. Its live region stays quiet while a run trace is mounted, so a change is announced once. Popovers are 384px wide (capped at 92vw); sheets are up to 576px from the right edge, and collapse to a bottom sheet of at most 45svh below `md`.

Spacing follows the Tailwind 4px scale. Observed rhythm: 8px between chips and inline items, 16px inside cards and popovers, 20px between nav items, 24px page gutters, 40px report padding. Density is tool density, not marketing density: a list row is one line high with its metadata inline.

**The list row** (task 058, round 10; lead rulings on `research/lists-rows-polish.md`). From `md` up, one line: the project prefix in Grey (capped at 45% of the name cell, the first project and "+1") and the task name in Body Semibold Navy, which takes every pixel the fixed columns leave; the capability as plain Meta Grey text (7.5rem, not a chip); the status mark and word (11.5rem, "Paused · waiting on you" and most first names); the owner (8rem, only on Organisation and a Project, the reader's own rows "You"); the source count (5.5rem; "—" on a failed row, archived or not, never "0 sources"); the date (5.5rem). Owner, count and date are Meta Grey, right-aligned, digits in tabular figures. On phones line 1 is the name alone and line 2 leads with the status word and its live step, then " · " and the project in Grey, which gives way first, with the date at the right. The status column has one separator, " · ": "Screening · 28 min", "Complete · with gaps", "Paused · waiting on you" on the reader's own task and "Paused · waiting on <first name>" on a colleague's, "Archived" in the Archived view; the words live in the one status vocabulary (`runPresentation`). Dates have one form for every reader: "5 Nov" this year, "12 Oct 2025" before it, never relative. The row's accessible name is its content in order, joined by " · ": title, status word with its live step, projects, owner, date. Hover is the Blue Wash over 150ms; a press deepens to Blue Tint at once and eases back on release; focus is the inset blue ring. A list stops at the server's page (50 rows on Tasks, 200 on a Project) and "Show more", the outline button at 40px under the frame at its left edge, asks for the next; focus moves to the first row that arrives, and a page that fails offers the list's Retry. Archived is not a scope (owner, round 11): the switcher keeps Mine and Organisation, and a toggle at the list's foot lists the archived tasks of the open scope (the reader's on Mine, the organisation's on Organisation, with the owner column there) and the active ones again when released; the scope holds across it. It is hardly ever used, so it is quiet (owner, round 11): the quiet control of "See the plan" and "Show steps" at Caption, Grey Semibold over the Line 2 underline turning Navy on hover, "Show archived" off and "Hide archived" on (the label carries the state; no `aria-pressed`), right-aligned in the foot row after "Show more" (alone when there is no more), under every state of the list (rows, loading, empty, error); its box is the row's 40 px and holds the wider label's width. On, the list carries the heading "Archived" in Meta Semibold Navy 8 px above the frame, and an empty archive reads "No archived tasks". A reader with no organisation sees the toggle without the switcher. The Projects page carries the same toggle (owner, round 11: projects can be archived), listing the archived projects of the open scope, empty as "No archived projects"; a project row has no status word, so an archived project's row is unchanged.

## Elevation & Depth

Flat paper with ambient lift only. Surfaces sit on the grey ground and are separated by a hairline border, not by shadow. Cards carry a soft, navy-tinted ambient shadow so faint that it reads as paper weight rather than elevation. Overlays lift further because they are temporary and must read as above the page: popovers, sheets and toasts share one deeper shadow, and the sheet adds a 40% navy scrim. Nothing else casts a shadow. Hover never adds a shadow; it changes colour.

### Shadow Vocabulary
- **Paper weight** (`box-shadow: 0 1px 3px rgba(15,41,74,0.05), 0 8px 24px rgba(15,41,74,0.04)`): cards at rest. Navy-tinted, near-invisible.
- **Sheet edge** (`--shadow-paper`: `0 1px 3px rgba(15, 41, 74, 0.05), 0 8px 24px rgba(15, 41, 74, 0.04)`, the Card's navy ambient shadow, plus a 1px Line ring): the report page and the Findings table. It disappears below `md` and in print. No surface carries Tailwind's grey `shadow-sm` or `shadow-lg` (task 058 consistency pass: the find dialog and jump-to-end take the overlay lift).
- **Tooltip lift** (`box-shadow: 0 4px 16px rgba(15,41,74,0.12)`): tooltips only.
- **Overlay lift** (`box-shadow: 0 10px 30px rgba(15,41,74,0.14)`): popovers, sheets, toasts.
- **Check-in glow** (`0 0 0 6px rgb(255 110 71 / 0.25)` at the animation midpoint): a one-shot Orange ring marking a newly arrived check-in; it fades to nothing. Orange is the one "waiting on you" colour (task 058, D15): the paused mark on the trace and the Agent tab, the check-in's rule and this glow.

### Named Rules
**The Hairline First Rule.** Regions are separated by a 1px Line border. A shadow is added only when the surface is temporary and sits above the page.

**The Navy Shadow Rule.** Every shadow is tinted with Navy (`rgba(15,41,74,…)`), never neutral black, so lift stays in the palette.

## Shapes

Zero radius everywhere. Buttons, cards, chips, inputs, popovers, sheets, toasts and tooltips all have square corners, and so does the status mark: a 6px square (task 058; owner 2026-11-05, replacing the 8px circle), small enough to read as a mark and not a chip.

**The one radius exception** (lead ruling P4): the plan card's radio is round, a 16 px ring with an 8 px dot, because a round radio is how people recognise a single choice. Nothing else is rounded.

The signature form is the Nesta cut corner: a 45° clip removing 10px from the top-right of the primary button (8px on the small size). The composer's send button doubles it, cutting both top-right and bottom-left. The green run-start button shares the cut. No other element carries it, which is why the eye can find the way forward on any screen.

Borders are 1px hairlines. Active and selected states are expressed as a 3px bottom rule in Electric Blue (nav, lifecycle tabs, Sources subtabs) or a 2px rule (the Mine / Organisation switcher), never as a filled pill.

**The Focus Rule** (task 058 consistency pass). Focus is a 2px Electric Blue outline offset 2px, set once in `index.css` for every link, button, field, tab and focusable element, so no control falls back to the browser's ring. A control that cannot show an outside ring draws it inside: the cut-corner buttons (the primary, the start button, the send button) carry a 2px white ring inset 4px, because their clip-path clips anything outside the box; a row flush against its frame insets the blue ring 2px; the white splash button insets a Navy ring; controls on the navy splash hero ring in Aqua.

The fold-mark logo is the one piece of geometry with personality: a 17px diamond, a square sheet whose four corners have folded to the centre. It sits before the wordmark in the nav, marks each chat in the conversation rail, and forms the animated constellation on the splash page. While a run is live it turns through 36 frames of folding and rotating in its own pastels (sand, teal, salmon, pink), snapping shut to solid blue between sheets, as the live mark in the trace's top line, the run status bar and the section being written (14 px in text lines). The nav wordmark's mark and the rail's Task Agent mark hold still during a run, and a running task's row in the task list takes the breathing 6px blue square, so every row's mark is one size (owner, round 8). It holds still under reduced motion.

## Components

Precise and unadorned. Hard edges, hairline borders, no decoration. The cut corner is the only flourish. Feedback is a 3% press scale over 160ms on a strong ease-out and a 150ms colour ease; hover states never snap. A nav item, lifecycle tab or Sources subtab grows its blue rule from its left edge to its centre on hover and focus (200ms, strong ease-out); the active item's rule is full width, and a click carries the half rule on to the right edge.

### Buttons
- **Shape:** square with a 10px top-right cut on primary (8px on small). Secondary and ghost have no cut.
- **Primary:** Electric Blue fill, white Averta Bold at Meta size, 18px horizontal and 11px vertical padding. Hover deepens to #0000d6. Disabled is Line 2 fill with white text, present but inert. One per view.
- **Entry size:** the list pages' primary ("New task", "New project"), the New Task submit and Start run use the same cut shape at Body size: 52 px tall, at least 144 px wide, 24 px side padding, the label centred and never wrapped. `PagePrimary` is the `Button`'s own classes (`buttonVariants`), link or button.
- **Header controls:** the list-page header holds only the primary (owner, round 11); a filters-row control in words (Make private) is the ghost at 40 px, Body Semibold, the primary's label size (lead ruling, consistency pass); the ghost elsewhere stays Meta.
- **Start run:** the one action that starts a search is the entry-size cut shape in Green (#18a48c), hover #147a6c. It is the only green fill in the system and the only non-blue cut corner.
- **Secondary:** transparent, Navy Semibold, 14px horizontal padding, hover fills #f0f0f3.
- **Outline** (lead ruling P1): the secondary with a 1px Line 2 border on Paper, Navy Semibold Meta, hover #f0f0f3, at the secondary's heights. Pagination (40 px, round 10), Download CSV (32 px at the sources filter bar's end, round 11), the Download trigger, and the bordered actions inside a check-in or plan card.
- **Ghost:** transparent, Grey Semibold, 12px by 9px padding, hover turns Navy. For Cancel and Back to top.
- **Retry:** a standalone Retry is always `Button` secondary small, under the sentence that says what failed (`RetryCard`).
- **Inline actions** (`ui/brand/inlineActions.ts`), three styles and no others, each at the size of its line: **Link**, Electric Blue Semibold, underlined on hover 3 px below ("Sources →", "Read it →", "Expand all", "Ask about this analysis" at Meta, "Review the plan"); **Quiet control**, Grey Semibold over a Line 2 underline that turns Navy ("See the plan", "Show steps", "See plan", "Change" at Caption); **Prose link**, Navy, always underlined, blue on hover (legal pages, a source title in the Findings table, a project named on Share).
- **Icon buttons** (`ui/brand/icons.tsx`, the one icon module, one 1.5 stroke): a 16 px glyph in a 32 px box for chrome (the rail, panel headers, close, the longlist's option actions, jump to end) and a 13 px glyph in a 28 px box for row actions (rename and archive on a conversation row). One hover, Blue Wash with Navy, and the 3% press.
- **Close** (`CloseButton`): the chrome icon button with a 16 px ×, Grey turning Navy. Sheets, toasts, the sensitive-information banner (white glyph, white ring) and any dialog close with it; no × glyph in text.
- **Disclosure:** the chevron glyph at 12 px, turning down over 200 ms when open; never a text triangle.
- **Hover / Focus:** colour eases 150ms; active scales to 0.97; focus is a 2px blue outline offset 2px.
- **Labels:** sentence case, action-oriented ("Start search", "Looks right", "Review the plan"). Default `type="button"`.

### Chips
- **Style:** 1px border, 10px by 4px padding, 11.5px Semibold, square. Default is Paper with Line 2 border and Navy text.
- **Tones:** blue (tint fill, #c7c7ff border, blue text) for BETA and the few tags that mark one item out (not the task list's capability, which is plain Grey text since round 10); soft (Ground fill, Grey text); green, yellow and red as pale tint fills with dark tone text. Every toned chip carries its label in text.
- **Editable chips** in the plan card add a pencil and an × inline. The "+ add" control beside them is a button with a dashed Line 2 border, Paper fill, Meta Semibold Grey text.

### Cards / Containers
- **Corner Style:** square.
- **Background:** Paper on Ground.
- **Shadow Strategy:** paper weight (see Elevation). Report sheet uses the same plus a hairline ring.
- **Border:** 1px Line 2.
- **Internal Padding:** 16px; pane heading is 14px top, 10px bottom, 16px sides.
- **Pane heading:** Label style (uppercase, Extrabold, tracked, Grey) with an optional right-aligned control.
- **A list loading** sits inside its own frame (Paper, Line 2 hairline): five rows at the real row height, each with a placeholder bar where the name will be. **An empty list** is the same frame with a label and one plain sentence, left-aligned at the list's edge. A list that fails is the frame, the sentence and a 40 px ghost Try again.
- **Divider:** 1px Line.
- **Status mark:** 6px square, always followed by a word, for the still states: Green complete, Orange paused, Line 2 idle, Red failed. Blue and breathing for a step in progress, a running task's row and a searching longlist row: opacity 1 to 0.25 and scale 1 to 0.8 at the trough on the 1.6s rhythm (`anim-breathe-mark`; owner, round 11: the 0.5 pulse was too faint to read as live), still under reduced motion; the words beside it keep the soft breathe. The trace's top line, the status bar and the section being written show the turning fold mark instead (see Shapes).
- **Placeholder bar** (owner, round 8): a short Line 2 bar, 10px tall, breathing on the status mark's 1.6s rhythm, in the cell or row a running stage will fill. Only while that stage runs and only where the value is absent; still under reduced motion. The Sources table pulses Relevant while screening, Evidence type and Evidence strength (relevant sources) while classifying, and Status (relevant sources not yet read) while the full texts are read; the Themes subtab shows three placeholder theme rows while mapping until the themes are found, then the found themes in their final layout, name and description, with a bar where each document count will be; the counts fade in place when the committed landscape lands, nothing reordering or remounting (owner, round 9) and the Landscape subtab placeholder bars in the chart's own rows while classifying. While a stage that feeds the Sources tab runs, its views refetch every 5s so the values replace their bars as they land.

### Inputs / Fields
- **Style:** Paper fill, 1px Line 2 border, 12px by 10px padding, Lead size, square. The composer textarea grows with content (`field-sizing: content`) between 56px and 240px.
- **Focus:** 2px Electric Blue outline. Splash fields instead turn their border blue.
- **Error / Disabled:** error border Red with a red Body-size message beneath; disabled is Ground fill with Grey text.
- **Bare variant:** the New Task question field has no border or fill. It is Lead text on the paper card, with the primary button beside it.

### Navigation
- **Top nav:** 64px, Paper, hairline bottom border. Wordmark left (fold mark, "Policy" Navy, "Atlas" Electric Blue, display face at Heading size, tracked -0.02em) with a blue BETA chip carrying a tooltip. Links right at Lead Semibold Navy.
- **Growing underline** (owner, round 9, reshaped in the consistency pass): one 3px Electric Blue rule under the item, anchored at its left edge, over a transparent 3px border so nothing shifts. On hover (fine pointers) and keyboard focus it grows from the left edge to the item's centre (half width, 200ms, strong ease-out) and shrinks back on leave. The active item is Extrabold and its rule is full width; clicking carries the half rule on from the centre to the right edge rather than restarting it. Under reduced motion the half and the full rule appear without growing. The top nav, the lifecycle tabs and the Sources subtabs share it (`GROWING_RULE_CLASS`, `GROWING_RULE_ACTIVE_CLASS`).
- **Lifecycle tabs:** same rule language at Lead Semibold. Inactive is Grey, hover Navy with the growing rule, active Navy with the blue rule; a locked stage has no rule to grow. Locked stages render in Line 2 with a not-allowed cursor and `aria-disabled`, so the whole lifecycle is visible from the first moment.
- **Mobile:** nav wraps to two rows; lifecycle tabs move to a bottom bar with horizontal scroll.
- **Sources subtabs:** idle, Meta Grey at the medium weight (`font-medium`, which Averta sets Regular, so an idle tab reads as greyed; owner, round 11) and never a faded tint, AA on white; Navy on hover; the active one Extrabold Navy, with the growing rule.
- **The Sources tab's landing** (owner, round 10): before the reader has picked a subtab on a task, the Sources tab opens by stage (All sources, then Landscape, then Themes while a run is live; Themes when done). Once they pick one, the tab returns them there on that task, live or done, until they pick another. The choice is kept per task in the browser's `localStorage` (a per-viewer convenience); without storage the stage rule applies.
- **The Mine / Organisation switcher** uses the tab language: Meta, no fill, and the nav's growing rule at 2px (owner, round 10): on hover or focus the Electric Blue rule grows from the item's left edge to its centre over 200ms on the strong ease-out and shrinks back on leave, the active item's rule is full width, and a click carries it on from the centre to the right edge; under reduced motion the rules appear without growing. Archived is a toggle at the filters row's end, not an item here (round 11; see The list row).

### Overlays
- **Tooltip:** Paper, Line 2 border, 10px by 6px padding, Caption Navy, tooltip lift. Scales in from its trigger over 125ms.
- **Popover:** Paper, Line 2 border, 16px padding, Meta Ink, 384px wide (capped at 92vw), overlay lift. Scales in from its trigger over 150ms. Menu items hover to Blue Wash with blue text.
- **Find a task / Find a project** (owner and lead, consistency pass; round 11): a magnifier at the right of the filters row, the icon module's 16 px glyph in a 40 px target, in the quiet control's colours (Grey, Navy on hover and while open) with the house focus ring and the 3 % press, named and tooltipped "Find a task" / "Find a project" (the tooltip below it, clear of the primary); ending the row, its glyph sits on the column's right edge. It opens a popover under itself, right-aligned. The field is focused on open, its placeholder "Search your tasks by name" ("…projects…"); with nothing typed it shows no result line, only the five most recent as a starting list. Results follow the typing 150 ms after the last key; "No tasks match “<words>”" appears only once there are words. The field is a combobox: the arrow keys move the highlight (the Blue Wash, never blue text, and the matched words are not marked), Enter opens the row, Escape or an outside press closes and returns focus to the control. Rows are 40 px, Body Navy, one line, truncated.
- **Menu** (the account menu, consistency pass): the popover's tokens with no inner padding, as wide as its content and at least 240 px, right-aligned under its button. Who you are first (name in Meta Bold, email and organisation in Caption Grey, 16 px padding), a hairline, then the items as 40 px Meta Semibold rows with the menu-item wash; Sign out, the one destructive item, last. It arrives from the button, 4 px above its place, fading and settling over 200 ms on the strong ease-out, and leaves the same way in 150 ms; a cut under reduced motion. The button shows the open state (Blue Wash) with `aria-expanded`; focus moves to the first item on open and back to the button on close; the arrow keys, Home and End move between items; Escape and an outside press close it.
- **The name and its menu** (task and project headers, owner round 11). The task bar's left side is the task's name at Title (Heading below `md`), Bold Navy, truncating on one line, then the capability in plain Meta Grey on the same baseline (no chip), then the owner's 40px quiet control: the 16px chevron pointing down, Grey, Navy on a Blue Wash hover and while open. Below `md` the name takes its own line and the capability and chevron follow under it. A project page's title takes the same control after its last word, the title wrapping as text. The control opens the menu's language (the popover's tokens, 40px Meta Semibold rows, focus on the first item, the arrow keys): Rename and Archive. Rename turns the name into a field in place at the name's size, a Line 2 border on Paper, with "Save name" (outline, 40px) and "Cancel" (ghost) beside it; Enter saves, Escape cancels, focus returns to the chevron. Archive is the Share page's two-step confirm in the popover: the sentence saying what archiving does takes focus, then "Archive" (outline) and "Keep it" (lead, round 11). A task's sentence is "Archiving removes this task from your active tasks."; a project's adds "Its tasks stay as they are." An archived project offers Rename only; archiving a project goes to the Projects list. A colleague sees the name alone.
- **Sheet:** slides from the right on the drawer curve over 260ms behind a 40% Navy scrim; title in the display face at Lead Bold. Becomes a bottom sheet below `md`.
- **Toast:** Paper, Line 2 border (Red for errors), 16px padding, overlay lift, bottom-right, rises 8px into place over 200ms.

### Report and citations (signature)
The report is a paper sheet in the 780px reading column. Body prose is Lead size on desktop, Body on mobile, within a 44em measure. Cited spans wash to Blue Wash on hover. Numbered citation markers are small square tags: Caption Semibold, 80% Electric Blue text on Blue Wash with a 25% blue border, deepening on hover, 4px after the cited words (none before the full stop). In print the sheet loses all chrome and colour; markers become plain black numbers with no box.

**The page, top to bottom** (task 058, rounds 10 and 11). The kind row ("Report", Download at the right); the question as the `h1`, live and committed, so the heading never changes when the committed report lands (the generated title names the download file only; a baseline keeps its own title); the date on its own line under it, "Last updated 5 November 2026" at Meta Grey, the year always written (owner, round 11; committed only, it fades in with the facts); one action line, "See the plan" (quiet control) and "Ask about this analysis" (link) side by side at Meta, 20px apart; then the facts line. The **facts line** is one line of label and value pairs at Meta, the label Grey and the value Navy, 24px apart, wrapping to two lines on a phone: "Sources 12 cited out of 118 included · Published 2019–2024". The value of Sources links to this page's References (`#references`), opening them as the contents do (owner, round 11; it no longer leads to the Sources tab). Never a row of bordered tiles. Then the Executive summary (key findings, case studies, the most relevant sources; owner, round 11, reversing round 10's move to the end), the Full report (its opening paragraph, its sections), then the References and "How the evidence was gathered" after a hairline. The download follows the same order.

**Heading outline.** The question is the `h1`; the parts ("Executive summary", "Full report") are `h2`; the sections inside them, the case studies and the most relevant sources are `h3`; a case study's title is `h4` (Lead Bold Navy). A page without parts (a baseline, the longlist) sets its sections at `h2`. References and the method are `h2`. A collapsible heading holds its button (the GOV.UK accordion pattern), never the reverse, so it stays in a screen reader's list of headings.

**One disclosure vocabulary.** Every collapsible part of the report says the chevron then "Show" or "Hide" in Grey Semibold Meta over a Line 2 underline that turns Navy on hover, as the trace's "Show steps" and the search queries' "Show" do; the chevron points right when shut and turns down over 200ms. The control beside "Full report" is "Show all" / "Hide all" as a quiet control. Nothing prints its disclosure words: print opens everything.

**Key findings** are a list with a 6px Electric Blue square bullet (owner, round 11, reversing round 10's Navy; the Yellow square on a gap, beside its "gap" label), 12px between items. The square's middle sits on the middle of the text's x-height at every size: the item aligns the bullet to the first line's baseline and raises it by half an `ex` less half its height (measured on at 19 px and 16 px: on the x-height to the pixel). **Case studies and most relevant sources** are ruled cards (owner, round 11, reversing round 10's ruled entries): each entry in a Line hairline box with 16px padding, the cards 12px apart, no shadow; an entry's chip row takes no room while it is empty. A source title is a Navy link underlined in Line 2, the underline turning Navy on hover, and opens its dossier. Evidence types read in sentence case everywhere ("Systematic review and meta-analysis"), from one formatter. The appraisal chip ("Very strong") is the soft tone; blue chips are for capability tags and "checked".

**How the evidence was gathered** (owner, round 11) folds, like the References: shut, the heading and one line at the References' size ("312 found → 118 included → 12 cited"). Open, the run's counts come first as a ruled table at Body, one stage a row in the Landscape funnel's names (Found, Relevant, Full text, Shortlisted, Cited; Quality-checked is left out), the figures right-aligned in one column of Navy tabular figures; then the plain sentence ("This section covers only the cited sources — the Landscape tab shows the whole search."); then the cited sources' distributions and key themes as tables of the same width, each under a Body Semibold Navy caption, not a heading, so the section is one heading in the outline. Every table is 32rem wide at most and ruled by Line hairlines, so the figures line up down the section.

**References** read as citations: the number in a Grey Semibold column of tabular figures, right-aligned, then "Sampleton A, Mockford C (2022). Universal breakfast clubs and diet quality. BMJ Open. doi.org/10.1000/example.1" at Body at every width. Authors are surname and initials, up to three then "et al.", an organisation as written; a reference with no authors starts at its title. The title is the dossier link; the address is a Grey link without its scheme on screen and the full URL in print. While the report is written the list is titles only, not links.

**The marker is the control.** A claim is one tab stop: its marker, named for what it opens ("Source 2: School meals and child weight outcomes"; "Sources 7 and 12"), its numbers in ascending order. The marker shows the citation preview on hover and on keyboard focus; the cited words show it on hover and open the sheet on a click, but are not a button. The provenance sheet's dialog description ("Claim provenance") is for screen readers only, and each citation in it reads "[2] Title", the year and venue, the highlighted passage, then the authors, institutions and chips, so a phone's bottom sheet shows the passage first.

**Contents.** From `md` up, the sticky sidebar lists every section in full (titles wrap; a server `nav_label` wins), marks the section whose heading has passed a line a quarter of the way down the pane (at most 160px), and lists the method as "How the evidence was gathered" only when that section renders. Below `md`, a closed "Contents" disclosure sits under the title block (a Label with the chevron, 44px tall, rows at least 40px), closing once a section is chosen. Every page that shares `ReportPage` has it.

**Print.** The app chrome, the sensitive-information banner, the action line, the contents and every disclosure word are hidden; the bullets print as black squares (a border, since print drops backgrounds); a heading stays with what follows it, and an entry (a finding, a case study, a source, a reference) is not split across pages.

While a section is being written (task 058, owner 2026-11-05), the page shows the evidence as the writer uses it: one Meta grey line under the heading, "Drawing on 4 sources · Smith 2023 · DfE 2022 · Nesta 2021 · and 1 more", from the first read until the checked section replaces the draft (nothing in it is a link while live).

**Markers while live** (owner round 7). As each of the writer's own citations closes, the marker's own chip sits after the cited sentence in its muted look: Caption Semibold, a Line border, Ground fill, Grey text, a dot for the number ("[·]"); not a control, the source titles as hover text, named "Cited, being checked: <titles>". When the section is checked, the report's numbered marker takes its place in the report's look ("[3]", 80% Electric Blue on Blue Wash), still not a control while the report is live (named "Citation 3, Smith 2023; details when the report is ready"); the provenance sheet arrives with the committed report. Blue still means checked. While the section's claims are checked the muted chips run a blue wave, one chip after another (owners, rounds 9 and 11): every 2s each chip takes the checked marker's look (Blue Wash fill, the marker's 25% blue border, 80% blue text) with a 1px blue halo (`0 0 0 1px rgb(0 0 255 / 0.35)`) over 300ms, holds it for a tenth of the cycle and lets it go over 300ms, muted the rest of the time; each chip starts 350ms after the one before, counted across the section, not per paragraph. A narrow pulse with a wide stagger is what makes the order visible: round 9's 1.2s cycle with a wide peak, 150ms apart, read as every chip pulsing at once. Still under reduced motion. The judged marker is unchanged. The draft layer, muted chips and all, fades off the checked prose, so the numbered markers never flash.

**The live page is the report page** (owner round 7). While it is written the Result tab is the committed report's own page: the contents beside it, the kind row, the question as the title, "See the plan", the part headings, the sections in the report's order through the report's section and prose components, the case-study cards in the report's card layout as each closes, and a numbered references list at the foot that grows as sections are checked (titles only, no links). What only the committed report has (the download, the date line, the facts line, "Ask about this analysis", the method, links into provenance) is absent, with no placeholder; the most relevant sources show as each note is written, in their place at the end of the executive summary. The committed report updates the same page in place: the scroll position stays, a section the reader was reading stays open, and only what arrives (the download, the facts strip, the expand controls, the chips, the reference details, a renumbered marker) fades in once over 300ms on the strong ease-out; under reduced motion it is a cut.

**Streamed prose** (owner round 7). The draft is paced in the browser at a steady rate with word snapping: a frame loop reveals whole words at max(0.15 characters per ms, backlog / 800ms), and a quiet draft shows its trailing word after 500ms (tuning values). Settled paragraphs are frozen; only the live paragraph re-renders, and the words each frame reveals fade in over 150ms, opacity only, one span per batch, dropped when the paragraph settles. A revision that shortens the text holds the section's height until it regrows. The page follows the text down only for a reader already within 40px of the end, and stops on the first scroll up. Under reduced motion the words appear without the fade; the pacing stays. No caret.

### The run trace (signature)
A run shows in the Task Agent conversation at its place in the thread (task 058; owner 2026-11-05) as one card from start to end (owner, round 8: the ended state is the same card): a Card (Paper, Line 2 hairline, the paper-weight shadow) the width of the thread's cards. It reads as a table: the top line and every step row share one template, the words on the left, the counts and times right-aligned in Grey tabular figures in one column, and the links right-aligned in Electric Blue Semibold in the last; every line shares the Body line box (1.55rem), so rows stand equal and each mark sits on the middle of its first line. Narrower than 32rem (a phone, the sidebar) the template lets go and a row's counts, time and link follow on the line under its label, the dot bound to the cell before the link.

- **Top line**, over a Line rule while the rows show: the mark, the state word in the Label style, the run's time in the time column. Live: the turning fold mark, "Running", the elapsed time; no Minimise, the rows stay open. Paused: the orange square, "PAUSED · a check-in is waiting on you" (the state word in the Label style, the rest in Grey; to a colleague "PAUSED · <step>"). Ended well: the Green square, the walk's finish words in the Label style ("REPORT READY"), the wall time to the minute and "Read it →" in the link column, the run's one destination. Stopped or failed: the Red square, "STOPPED" or "FAILED", no link. A finish that is a sentence (a degraded shortlist walk's "Policy Atlas could not propose a shortlist. Your places are unchanged.") keeps its case in Navy.
- **Rows**, one per plan step in plan order, each mark on a Line 2 hairline spine, a Line hairline rule between rows. A done row is its label in Navy at Body, then its counts and wall time, then its link (Searching and Screening → Sources, Classifying → Landscape at once, Mapping → Themes, Writing → Report; lead, round 8). The step in progress is its label in Navy Semibold, its own elapsed time, and its link while it runs (Searching and Screening → Sources, Classifying → Landscape, Mapping → Themes, Writing → Report; owner, round 8), with the writer's section line and the activity line under it; its 6px blue square breathes while updates arrive (the mark's breathe, to 0.25 and 0.8 of its size) and the activity line breathes with it (the same 1.6s rhythm, opacity 1 to 0.6; the label holds still). Steps to come are names in Grey at Meta size. A row that lands keeps its place: its counts and time fade in over 300ms and its square eases from blue to green over 150ms (lead, round 9: it shrinks as it lands, so a rise read as a jump). As the step in progress gains or loses its section and activity lines the card eases to its new height over 300ms on the strong ease-out. "See plan" sits at the foot. Searching and Screening are two rows once the server splits them (owner, round 8). A longlist walk links as an Evidence search where it does the same work (owner, round 11): its Searching and Screening rows to Sources and its Classifying row to the Landscape, running and done; from Suggesting options on, its step in progress to the longlist ("Longlist →") and those steps' done rows nowhere; Reading the linked search nowhere. The baseline walk links as an Evidence search, its Writing row to the baseline ("Baseline →").
- **Ended**, the rows fold behind one quiet control under the top line's words, "Show steps" with the conversation surfaces' chevron, which turns down and reads "Hide steps" when open; it stays put when the rows open below it. The rows fold and open by their height and opacity over 200ms, the chevron's time, the rule under the top line folding with them (round 9). A past run (not in the stream; the baseline walk once the longlist walk starts) is the same ended card drawn by the same code (owner, round 11): its finish words, its wall time and the link its walk ended with ("Read it →" to the report, the baseline or the longlist; none after a stop or a failure), and, when the thread's run read carries its steps, the same folded "Show steps" list; without them, no control. It is not a landmark and has no live region.

A screen reader hears the current step and what the model is doing now ("Writing · Section 3 of 7 · Costs and funding") from the card. The sidebar shows the same card (its text at Body size); outside the Agent tab the run status bar says the same words (see Layout); nothing else shows the run. The Result tab carries a small navy square when a section or the report landed while the reader was elsewhere (the Sources tab has none: owner, round 8), and the browser title carries "● Report ready" when the run finished unseen.

### Plan card and check-ins (signature)
A plan step is a Paper card under one small stepper line the client computes ("Plan · step 2 of 3 · Scope"), with the part's title, a radio list (label, then one plain sentence, in the planner's order; no "Recommended" word, no pre-selection), an input inside the card for an option that needs words, and the plan card's one green Start button. The scope card has no radio list: its chips (grouped under "Screening criteria" and "Source filters", each with a pencil and an ×, plus "+ add") are how the scope changes, and one secondary "Looks right" button records the choice with any staged edits. A settled part takes the user's side: the user bubble's surface (Blue Wash fill, 1px Blue Tint border, 14px by 10px padding, 32px left indent) with a 2px Green rule on its right edge over the bubble's border, the part's name as a grey Label, and under it the outcome in deep green bold (#0c6b5a) at Lead size, the scope's groups one line each under a grey label at Caption size (owner and lead, round 6), and while the card is the newest proposal "Change" on its own line under the green words, left-aligned, a quiet control at Caption size (Semibold Grey, underlined, hover Navy; owner, round 8). It settles the moment the user chooses, before the agent's reply (task 058, owner 2026-11-05), in one container (owner, round 8: a fluid settle): the options and controls fade out over 150ms while the card eases to its settled height and across to the user's 32px indent over 300ms on the strong ease-out, the surface and border ease to Blue Wash and the Green rule, and the settled words rise in; the stepper line above folds away with it. Under reduced motion it is a cut. A pending check-in is a Card with a 2px Orange left rule, the question as its title (no eyebrow, no chip), one facts line, the same radio list with the suggested option first, a closed "Or steer in your own words" disclosure and one "Stop the run" link; it rises in when it arrives in front of the reader and its Orange ring blooms once, 150ms later (task 058; round 9). It settles the moment the user chooses, as the part cards do: its contents fade out over 150ms while its box eases to nothing over 300ms, and the answered line rises in the run block when the run records the choice; if the answer fails it comes back open with its notice. Its "Confirm your steer" step eases the card to its new height, the new contents fading in over 150ms. Under reduced motion each is a cut. A failed turn renders as a 40% Red Tint surface with a Red Tint border and a secondary Retry button. User messages are indented 32px from the left in a Blue Wash bubble with a 1px Blue Tint border, square corners; agent messages are plain Lead prose at the 44em measure.

### The search queries (Sources, signature of round 9)
At the top of All sources (owner, round 9). While the search runs it is open under "Search queries" (Lead Semibold Navy): one table at Meta size with hairline rows, the Query and Results columns headed in the table-header label style, each backend once per group as a row-group label (Label treatment at Caption size, Grey), each query as it goes out (a citation pass's or lookup's description in Grey, a query in Navy), its Results cell a placeholder bar until the count returns and then the count right-aligned in tabular figures; a row that goes out fades in over 300ms. Queries wrap on words. The sources table and its count line stay hidden until the first results land, then rise in together. Once the search has ended (round 11) the block is no box: it folds to one Meta Grey line in the filter bar's column, "Found with 12 queries and 3 citation passes · Show" (a pass that looks cited works up counts as a citation pass), whose chevron opens the rows over 200ms ("Hide" when open). Open, the queries are ruled rows at the sources table's Meta size and full width, no header band and no group labels: the query in Navy, the database it went to in Grey, the results count right-aligned in tabular figures; a citation pass is its own row, its description in Grey and in the past tense ("Followed citations from 40 sources"). The saved coverage replaces the live rows in place: each database's written queries, then its passes in the order they ran, worded by the server for a finished search; until it lands, the stream's passes are put in the past tense in the browser. Below `md` the same block spans the column.

### The sources table (All sources, round 10)
**The filter bar** (round 11): one row above the table it scopes, every control a 32 px outline box at Meta size on one baseline, 8 px apart on every line when it wraps. The screening choice is the outline switch at that height ("Screening": All, Included, Screened out; the chosen one a Navy border and Navy words, the others Grey), then Cited, then the facets (Key theme, Origin, Evidence type, Strength, Country, Year), each idle as the outline button naming its facet with a 12 px chevron. An applied filter is a filled Navy chip with white words and its × ("Strength: Moderate ×", "Cited ×"): the words reopen the choices, the × clears that filter (named "Clear the strength filter"). "Clear filters" (the ghost at 32 px) follows once any filter besides the screening choice is set, and Download CSV ends the row at the right as the 32 px outline button: the table has no single forward action, so the view has no primary (lead, round 10). The Year control's name carries its range ("Filter by year: 2015 to any") and opens two four-digit fields that apply on leaving a field or on Enter. Below `lg` "Sort: Relevant, most likely first" joins the row as an outline box. The headers sort only. Under the bar, the count ("52 sources"; "1–50 of 52 sources" on a paged list).

The table sits in one frame, the queries table's: a Line hairline above and below, no side borders, no shadow, no header band. Six fixed columns (Source, Year, Evidence type, Evidence strength, Relevant, Status), so a filter or a page never moves a column; the source takes what the values leave. Headers are the Label style at Caption size, one line, bottom-aligned, each a sort button at least 24 px tall with a 12 px arrow at the 2 px stroke whose slot is always kept (Navy when the column sorts, Line 2 on hover and focus otherwise), so every label and arrow share one baseline; Relevant is right-aligned over its figures. The read-depth column's header is one constant, `STATUS_COLUMN_HEADER` (`sourcesPresentation.ts`), while the owner chooses its name. A row: the title (Body Semibold Navy, the way into the dossier), under it a Meta Grey line "Venue · Origin" with the green "Cited" chip at its end (Origin and Cited fold in here, lead round 10; the providers stay "OpenAlex" and "Overton", owner 2026-11-06); then the values as plain Meta text that never wraps (a value too long for its column ends in an ellipsis): Year in Navy tabular figures, the evidence type in sentence case (the report's one formatter) and the strength in Ink, the Relevant figure right-aligned in Navy tabular figures after a 12 px tick or cross (Green, Red), the depth "Full text" in Navy or "Abstract only" in Grey over a dotted Line 2 underline. "Cited" is the only chip in the table. The strength carries its tone as the status mark does (round 11): the 6 px square before the word, Green for Very strong and Strong, Navy for Moderate, Grey for Limited, Weak and Unrated, in the sort's order; a tier outside the vocabulary has no square. A row washes Paper 2 under the pointer and while focus is in it. The reasons behind a type, a strength, a verdict and "Abstract only" are hover only, out of the tab order (lead, round 10): the title is the one tab stop per row, and the dossier carries the same words. Each such value says so with the standard affordance (round 11): its word under a dotted Grey underline 3 px below, and the help cursor. The verdict's name carries the figure ("Relevant, 99% confidence: screening details").

Below `lg` each source is a stacked row in the same markup (the brief gives phones the stacked row; from 768 to 1023 the six columns would leave the title under 100 px, so it holds there too): the title, "Venue · Year · Origin" and the chip, then the values in column order as one wrapping line, each carrying the dot to the next so a wrapped line never starts with one, a placeholder bar in its slot while its stage runs; 12 px by 16 px padding, a Line hairline between rows. The headers hide and a "Sort" select joins the filter row, the columns in order with the direction named ("Year, newest first").

Loading is the frame with the real header row and six rows of placeholder bars at 88 px; nothing found is the frame with "No sources yet" and "They appear here as the search finds them."; nothing matching is "No sources match" and "Clear the filters to see all 52." with a 40 px ghost "Clear filters"; a failed read is the frame, "Sources couldn't be loaded." and a 40 px ghost "Try again". Pagination is two outline buttons at 40 px with "Page 1 of 2" between them at Meta, and a page change starts the reader at the new page's top (`Pagination`, shared with Findings).

### Charts (Landscape)
Ranked bars are a real table: label, Navy bar, the value at the bar's end; Grey for missing data and folded tails. Evidence types read in sentence case (the report's formatter); their links keep the classifier's value. A row leads somewhere when it can (owner, consistency pass): an evidence type opens All sources filtered to it (`?type=`), a finding group opens Findings filtered to it, a publisher country opens All sources for that country (`?country=`, round 10), and a funnel row opens the table filtered to its set (round 11): Found to every source (`?status=all`), Relevant to the screened-in set (`?status=Included`), Cited to the cited sources (`?cited=true`). Folded rows, "Not reported", "Ungrouped", rows at zero and the funnel stages the table cannot filter to (Quality-checked, Full text, Shortlisted) lead nowhere and take no hover.

**Where sources were published** offers a List / Map switch at its heading's right (round 11, owner): the longlist's outline switch at 32 px, the list the default. The map is a choropleth on the Natural Earth projection (`d3-geo`, `topojson-client`, `world-atlas` countries-110m; loaded with `React.lazy`, so the Landscape page does not carry the atlas): the land alone on Paper, Antarctica left out, a Paper hairline between neighbours; a country with sources in a Navy sequential scale of five steps (Navy mixed into Paper at 35, 51, 67, 84 and 100%, on a log scale from 1 to the largest count, so one dominant country does not leave the rest in the lightest step), a country with none in Line 2; the scale's legend under it, the five swatches between "1" and the largest count. Under a fine pointer a country with sources turns Electric Blue and a tooltip reads "United Kingdom · 23"; a press opens All sources for it, as its row does. Names the atlas cannot place (a region, a country too small for the 1:110m map) are listed under the map in Meta Grey ("Not on the map: Global, EU"). The list is the keyboard's path: the map is for the eye and its countries take no focus. Nothing animates, so reduced motion changes nothing.

The publication years are upright Navy columns drawn in HTML, a value axis of at most four round steps on Line grid lines, the year labels under them (round 10, owner). A press and drag across the columns chooses a range: the covered columns turn Electric Blue as the pointer moves, a Meta Semibold blue label in a band above the columns reads "2015 to 2020", and release opens All sources for the range (`?year_from=&year_to=`); a press and release on one column opens that year; a year or range with no sources opens nothing. Touch drags the same way (vertical scrolling passes through) and the label's band sits above the columns, clear of the finger. Under a fine pointer the hovered column turns blue and the band reads its count and year ("6 sources 2019"). From the keyboard the chart is a horizontal listbox: arrows, Home and End move between years, Shift with them extends the range, Enter opens it (the focused year alone when no range is held), Escape drops it; the focused year is outlined in blue. Colour is the whole state: nothing animates and reduced motion changes nothing. A visually hidden table carries every year and count. One hover: the bar turns Electric Blue and the row's words go Navy, no row wash; the link covers the whole row and a keyboard focus rings the row. The page has no population line at its top (round 11: the funnel's Relevant row says it); a section carries a count only when it differs ("112 with a year", "34 findings", "Classified so far: 18 of 118").

### The longlist (Options scoping)
One page from the first row of the build to the finished list (task 058, round 10). The title is "Longlist" (the `h1`) with the plan's question under it in Lead Grey; once the longlist read exists one count line follows at Meta Grey ("14 options in 3 themes · 4 shortlisted · 2 excluded", the excluded part a link to its section), and nothing else stands between it and the options but the controls row (round 11, review); "Read from titles and abstracts" sits at the list's foot. No kind label, no "scoping pass" chip. No stage line: the run status bar above says what the walk is doing, so one fold mark turns per screen.

**The row** is the same all the way; the finished list only adds controls. The name in Body Bold Navy (a link to the option card once the list is finished), the only weight in the row (round 11, review: the origin words, relations, the rest of the evidence and the folded suggestions are the option card's). At the right, while the row's own search is the news, its line: "Queued", "Searching" after the breathing 6 px blue square, "Searched · 312 found", "Search failed" in red after the red square. While "Clustering into options" runs, the names it publishes join as rows the moment they are named, and every row not yet on the longlist reads "Assigning sources" after the breathing square until the step commits and its evidence line brings the count (round 11); the row keeps its place when the reads bring the option. Under the name the one-sentence description in Body, then one meta line at Meta Grey of fixed fields in a fixed order: the lever (the theme instead under a lever heading), the evidence signal's first part ("5 documents evaluated it"), "No in-scope evidence". Fields wrap whole, each middot bound to the field before it (a screen reader hears a comma), so no line starts with a dot; the document count is said once, by the signal. An exclusion is its own line: "Excluded:" in Red Semibold, then the constraint and reason in Ink. Rows stand 16 px apart with no rule between them; on a phone the row's controls close it, after the meta line. A held place reads "Shortlisted" in Navy Semibold after a 12 px check (round 11, owner); on the finished list, the option card and the Shortlist page that is the shortlist toggle (`aria-pressed`, the quiet control's underline), whose words become "Remove from shortlist" on hover and keyboard focus, what pressing it does, and "Add to shortlist" in Grey when the option holds none. Its labels share one grid cell, so it is always as wide as "Remove from shortlist" and neither the swap nor a press moves anything; the words sit at the cell's end where the toggle closes a row and at its start on a grid tile. The swap is a cut (a hover tens of times a day), never on touch, and not for the pointer that just pressed it until it leaves; the accessible name stays the resting words; on the list and the grid it is regular weight. Exclude and Include again stay icon buttons. No chips on the list.

**Sections.** Themes open by default (`THEMES_OPEN_BY_DEFAULT` in `LonglistView.tsx`, the lead's D1, for the owner to decide; it reverses the owner's 2026-09-23 "collapsed"), A group heading (a theme, a lever type, "Excluded") is the Label style with its count beside it in regular case ("CONDITIONALITY AND SUPPORT 6 options"), holding the disclosure button and the chevron with "Show" / "Hide" at every width, then one Body Grey line of description, open or shut; groups stand 32 px apart (round 11, review). The excluded options gather at the end, collapsed. The finished list's one controls row (40 px): "Group by" in Meta Semibold Grey and an outline switch (Theme · Lever type) on the left; "Show all" / "Hide all" as a quiet control and List · Grid on the right from `md` up; no grid on a phone, where Show all stands alone at the right. The outline switch (`ui/brand/OutlineSwitch.tsx`, shared with the Landscape's List · Map at 32 px) is joined outline buttons, the chosen one with a Navy border and Navy words, the others Grey; never a fill (the fill belongs to the one primary). The grid folds the lever types with no option into one Grey line under the table ("No options: Subsidise, Tax or charge and Inform"); its states are words, its tiles carry the toggle, and its Columns select wears the field (Paper, Line 2 border, 40 px, the 12 px chevron at the right).

**Motion.** When rows change groups (the theme wave, an exclusion) they move to their new places over 300 ms on the strong ease-out (a View Transition, each row named by its option, the names set only while it runs); a row that arrives fades in over 300 ms, one that leaves fades out over 150 ms; new theme headings rise 60 ms apart, and while "Grouping into themes" runs the themes it names stand as headings under the rows before any option is in them, the rows moving under them when the step commits (round 11); a value landing in a row (its evidence line, its lever, "Shortlisted") fades in over 300 ms. The list never blanks. Under reduced motion, or without View Transitions, it cuts. A finished list opens still.

**The option card.** The breadcrumb ("Longlist / name") carries the toggle and Exclude on its row, so no "Option" label sits over the title. Three blocks under the one rule (round 11, owner: "inconsistent text sizes, random bolding, not well organised information"): what it is (the title, the description at Body, one Meta Grey line of origin and relations, then How it works), What it would take (the profile), and Where it stands (the notices, then "Sources" with the evidence signal on one line and the standing under it, your outcomes, where it has been evaluated, the documents). One size per role: the title, the section headings, Body for every sentence, Meta for every label and secondary line; no Lead on the card. One field label style, Meta Grey regular ("Lever", "Sources", "Your outcomes", "Where it has been evaluated", a document group), over a regular value; the only weights are the title, the headings, the marked level words and a notice's tone word. A document's title is a prose link at Body, its record and quality lines Meta Grey with nothing bold. The notices are a flat block under a 1 px Line 2 rule, each a word in its tone and then its sentence ("Excluded:", "Breaks:" in Red; "May fall short:", "No in-scope evidence:" in Navy; "Cannot check:" in Grey). A marked profile value is Meta Semibold Navy after a 6 px Navy square, the word saying the direction ("Quicker", "Higher"); an unmarked one is "Middle" in Grey; no tint carries good or bad. Collapsed, the profile shows the marked lines, then "Middle on 3 of 8" once ("No line stands out" when none is marked). In "Where it has been evaluated" the plan's own place carries the same 6 px Navy square before its name, not a tint. "Documents" opens with the report's disclosure (the chevron, "Show" / "Hide").

**The Result views' tabs** (Baseline · Longlist · Shortlist · Report) take the growing rule at Meta Semibold, the active one Extrabold Navy with the full rule; a view still to come is locked as a lifecycle stage is (Line 2, not-allowed cursor, disabled), with no note beside it, so the strip stays on one line at 400 (and scrolls sideways if it must).

**The shortlist page.** The longlist's header: "Shortlist" as the title, the plan's question under it in Lead Grey. One primary, "Assess these N", at the page's end; while it is off, its reason is a Meta Grey line under it ("Assessment is not yet available."). "Risk appetite" (Meta Semibold Grey) sits over its select in the field's skin, full width up to 32rem (the longest answer whole on a desktop), then Suggest more as an outline button with "Add more from the longlist" as a link beside it; when Suggest more is off its reason is a line under it, never only a tooltip. Policy Atlas's words take bold lead-ins on their own line ("Why:", "Not covered:"), not uppercase labels.

**The baseline gate** reads as the other check-ins: the question as the title ("Does the plan still look right now you have the baseline?"), one Meta Grey facts line of the settings it ran from ending in "Baseline →", the key assumption as a plain Body sentence, the radio list. Decided, it takes the settled part card's look under the grey label "Baseline" (`SettledGateCard`), said once: no user bubble beside it and no "recorded · plan version" line. A scoping run's trace and status bar link like an Evidence search's: the longlist walk's Searching and Screening "Sources →" and its Classifying "Landscape →", running and done (owner, round 11), its step in progress from Suggesting options on "Longlist →", the baseline walk's Searching and Screening "Sources →" and its Writing "Baseline →", which the status bar hides while the Result tab shows the baseline.

### Share
Who can read the task, in order of consequence: Public link, Organisation, Projects (task 058, round 10). Each is a settings row on one paper card: the heading (Lead Semibold Navy) and the current state (Body Semibold Navy) on the left, the control on the right, a Line rule between rows; below `md` the control drops under the words and the card becomes the screen. Share has no primary: access changes are settings, so every control is the 40 px outline button and nothing carries the cut corner or a blue fill. Making a task public takes a second press inside the section ("Anyone with the link can read the report, the source list and the quoted excerpts, without signing in." · Make public · Keep private), no modal; once public the link sits in a read-only field with "Copy link" and "Copied" beside it, no toast. A task in a project follows the project, so it offers no visibility control, only the line naming the project. A colleague sees the states without the controls.

### History
The task's record, oldest first, grouped by day under a Meta Semibold Navy day heading that sticks to the top of the pane from `md` up. A row is the time ("09:02", en-GB, Meta Grey tabular, in a 3.5 rem column) and one sentence at Body that names who acted ("You" only for the reader); below `md` the time sits over the sentence. No chips: only a failure keeps the 6 px Red square, its word in the sentence. A row with something behind it is a disclosure with the 12 px chevron; the rest are plain text. Each run folds to one line ("Ran the evidence search · 36 min") with the trace's "Show steps" control; its steps hang on a Line 2 spine in the sentence column. Rows wait for every read: the skeleton, the frame's error or the frame's empty state, never half a list.

## Motion

Motion is evidence of data: it marks something arriving, a state changing or a reader's action, and quiets itself under reduced motion. The vocabulary is one curve (the strong ease-out, `cubic-bezier(0.23, 1, 0.32, 1)`; the drawer curve for sheets), one arrival and one breathing rhythm.

- **The arrival** (round 9): a block that appears after a view's first paint rises 8px and fades in over 300ms on the strong ease-out (`anim-rise`). History holds still: opening a view, the sidebar or a reload shows what is there without motion, because motion on opening a view marks navigation, not data (`ui/motion/arrivals.tsx`). A block keeps its id, so a streamed turn becoming the stored one appears in place.
- **The thread makes room** (round 9): the Task Agent thread's box eases to its content's new height over 300ms when it grows (a shrink passes straight through), and the pin to the end follows the eased box, so the thread glides up as a card arrives rather than jumping by its height. Not on the first paint or a task switch.
- **A decision card lays itself out**: an arriving part card's chip groups and radio rows fade up 4px in turn over 200ms, 80ms after the card and 40ms apart, capped at the sixth; they stay clickable throughout.
- **The reply comes at a steady pace**: the Task Agent's streamed reply is revealed the way the report is (whole words, a steady rate, a 150ms fade per batch).
- **Values land softly**: on the Sources tab a row or a value that lands while a stage runs fades in over 300ms, opacity only, so the table never shifts; found themes fade in 40ms apart.
- **The report's first words** keep the section's placeholder height until the text is taller, the lines fading out over them in 150ms.
- **Leaving**: the plan card folds and fades as the run starts while the trace rises below it; a sheet leaves along its own edge over 200ms on the drawer curve, faster than it came; the plan document arrives from the edge it docks to (16px, 260ms, drawer curve) or rises in place when centred (200ms).
- **Stays still**: ticking clocks and live counts, the activity words within a step, the rail's mark, the nav wordmark, the task list, tab switches and the sidebar, chart bars, keyboard actions and settled history.
- Loading skeletons and placeholder bars breathe on the status mark's 1.6s rhythm (`anim-breathe`, opacity 1 to 0.25 since round 11), so a page never shows two rhythms; only the 6px mark adds the scale. A breathing line of words ("Loading the dossier…") takes the soft breathe (to 0.6) so it stays readable (lead, round 11).

## Do's and Don'ts

### Do:
- **Do** put exactly one Electric Blue cut-corner primary on each view, and reserve the cut for it, the green run-start button and the double-cut send button.
- **Do** separate regions with 1px Line hairlines; add shadow only to temporary overlays.
- **Do** pair every status colour with its word: dot plus label, chip tone plus text.
- **Do** use the named type scale and keep every sentence at 16px or above; drop report prose from Lead to Body below `md`.
- **Do** tint status colours (green, yellow, red tints with dark text) rather than filling with them.
- **Do** animate only to mark real data arriving (a pulse only where a running stage will put a value), and quiet every animation under `prefers-reduced-motion`.
- **Do** render the locked lifecycle stages so the whole journey is visible; make them inert with `aria-disabled`.
- **Do** write labels in sentence case as actions, with just enough text.

### Don't:
- **Don't** round any corner; the status mark and the tab's new-content mark are 6px squares.
- **Don't** stack shadows, add hover shadows, or use neutral black shadows; every shadow is navy-tinted.
- **Don't** build dashboard SaaS chrome: KPI tiles, rounded cards, badge clutter, icon-only sidebars without labels.
- **Don't** use Electric Blue as a second fill on the same view, or as a background wash for whole regions.
- **Don't** commit font binaries, or design a surface that only works when Averta and Zosia are present.
- **Don't** introduce an ad-hoc pixel font size; add a named token instead and register it in the merge config.
- **Don't** let colour carry meaning alone, and don't ship a chip, dot or border without its text label.
- **Don't** pair blue and orange as a meaningful contrast (Nesta guidance for Scotland-facing work).
