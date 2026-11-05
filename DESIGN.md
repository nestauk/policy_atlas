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
- **Electric Blue** (#0000ff): the hero. The one primary button per view, the active nav underline, the active tab rule, citation markers, the "Atlas" half of the wordmark, focus outlines, and the fold mark's shut frame between sheets while it turns for a live run (task 058; owner 2026-11-05). Pressed state deepens to **Electric Blue Pressed** (#0000d6).
- **Electric Blue Tint** (#ececff): chip fill for blue-toned chips (capability tags, BETA) and the border of the same chips at `#c7c7ff`.
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

**The Named Size Rule.** Every text size is one of the named scale tokens (`text-caption` through `text-display`, and the splash's `text-hero` and `text-hero-2`). No ad-hoc pixel sizes in views; the one exception is the 11.5px chip. Uppercase labels use `LABEL_CLASS`, `PANE_LABEL_CLASS` or `CAPTION_LABEL_CLASS` (`ui/brand/label.ts`) and the `tracking-label` token, never a hand-written tracking. Averta has no 500 weight: a selected row is Semibold, never `font-medium`.

## Layout

The app is full-bleed. A 64px top nav runs the viewport width with a 24px gutter, brand group left and links right; below `md` it wraps to a two-row nav at 16px gutters. Inside a task a second, grey-ground nav bar carries the task title and the five lifecycle tabs (Agent · Result · Sources · Share · History), spaced 20px apart; below `md` the tabs move to a bottom bar that scrolls horizontally and respects the safe-area inset.

**List pages** (Tasks, Projects, a Project) share one header with fixed slots (task 058, lists polish): a 24 px context row (the way back on a project, empty on the lists), a 52 px title row with the actions right-aligned, and a filters row always reserved at 40 px, so the title and the list start at the same height on every page. Below `md` the actions sit above the title and the gutters are 16 px. A list row is 56 px; on phones it is two fixed lines, 84 px, without the owner and the source count. The New page's title starts where the lists' titles start (44 px top padding, no eyebrow above it).

**Task tabs** pad their page `py-8` (32 px, the report sheet's margin) and keep 24 px gutters from `md` up, 16 px below.

Content lives in a centred reading column of 780px on list pages and the report. The report page is a paper sheet with 40px horizontal and 36px vertical padding, 32px vertical margin, a hairline Line ring and Tailwind's small shadow (not the card shadow); below `md` it loses margin, ring and shadow and pads at 16px, so the paper becomes the screen. Prose inside caps at a 44em measure.

The Agent workspace is a three-region layout: a 48px icon rail on the left (toggle, new chat, active task mark), a scrolling conversation column of about 700px, and a pinned composer at the bottom with a double-cut send button 48px wide and 40px tall. The current chat's mark in the rail sits on a Blue Tint fill. The rail's Task Agent mark is the still fold mark, always, named "Task Agent": no hover status, no elapsed figure, nothing turns there (owner, round 8, reversing round 6). On every tab but Agent and only while a run is live or paused, the run status bar sits at the top of the page's column (task 058, owner rounds 7 and 8), and steps aside while the Task Agent is open in the sidebar, whose trace says the same words, returning when the sidebar shuts or shows another chat (lead, round 8): it starts after the rail from `md` up, so it never runs under the sidebar to the window's edge, and spans the screen below `md`. One line on Paper with 10px vertical padding over a Line hairline: the turning fold mark on the first line (the 6px Orange square while a check-in waits), the step's label in Meta Semibold Navy and what it is doing in Meta Grey ("**Writing** · Section 3 of 7 · Costs and funding"; "**Paused** · a check-in is waiting on you"; while searching, the query that is out, cut at about 60 characters by the server), and the run's elapsed time right-aligned in Grey tabular figures. The status bar is two controls on one bar (owner, round 9). The words are a button, the way to the agent (owner, round 8, reversing contract D8's "status only"): they open the Task Agent in the sidebar, or the Agent tab below `md`; hover Paper 2, the blue focus ring inset, named "Open the Task Agent: <words>". After the time, the running step's view as a link in Electric Blue Semibold ("Sources →", "Landscape →", "Themes →", "Report →", the same link the trace's running row carries), shown only while the reader is not on that view and not while paused; keyboard order words, then the link. The words truncate on one line and the time and the link stay in view, phones included. It opens and closes over 200ms on the strong ease-out when the run starts or ends or the sidebar takes the Task Agent, so the page eases rather than jumps; a tab switch sets it at a cut (navigation, tens of times a day). Its words rise in when the step changes; both hold still under reduced motion. Its live region stays quiet while a run trace is mounted, so a change is announced once. Popovers are 384px wide (capped at 92vw); sheets are up to 576px from the right edge, and collapse to a bottom sheet of at most 45svh below `md`.

Spacing follows the Tailwind 4px scale. Observed rhythm: 8px between chips and inline items, 16px inside cards and popovers, 20px between nav items, 24px page gutters, 40px report padding. Density is tool density, not marketing density: a list row is one line high with its metadata inline.

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

Borders are 1px hairlines. Active and selected states are expressed as a 3px bottom rule in Electric Blue (nav, lifecycle tabs, Sources subtabs) or a 2px rule (the Mine/Organisation switcher), never as a filled pill.

**The Focus Rule** (task 058 consistency pass). Focus is a 2px Electric Blue outline offset 2px, set once in `index.css` for every link, button, field, tab and focusable element, so no control falls back to the browser's ring. A control that cannot show an outside ring draws it inside: the cut-corner buttons (the primary, the start button, the send button) carry a 2px white ring inset 4px, because their clip-path clips anything outside the box; a row flush against its frame insets the blue ring 2px; the white splash button insets a Navy ring; controls on the navy splash hero ring in Aqua.

The fold-mark logo is the one piece of geometry with personality: a 17px diamond, a square sheet whose four corners have folded to the centre. It sits before the wordmark in the nav, marks each chat in the conversation rail, and forms the animated constellation on the splash page. While a run is live it turns through 36 frames of folding and rotating in its own pastels (sand, teal, salmon, pink), snapping shut to solid blue between sheets, as the live mark in the trace's top line, the run status bar and the section being written (14 px in text lines). The nav wordmark's mark and the rail's Task Agent mark hold still during a run, and a running task's row in the task list takes the breathing 6px blue square, so every row's mark is one size (owner, round 8). It holds still under reduced motion.

## Components

Precise and unadorned. Hard edges, hairline borders, no decoration. The cut corner is the only flourish. Feedback is a 3% press scale over 160ms on a strong ease-out and a 150ms colour ease; hover states never snap. A nav item, lifecycle tab or Sources subtab grows its blue rule from its left edge to its centre on hover and focus (200ms, strong ease-out); the active item's rule is full width, and a click carries the half rule on to the right edge.

### Buttons
- **Shape:** square with a 10px top-right cut on primary (8px on small). Secondary and ghost have no cut.
- **Primary:** Electric Blue fill, white Averta Bold at Meta size, 18px horizontal and 11px vertical padding. Hover deepens to #0000d6. Disabled is Line 2 fill with white text, present but inert. One per view.
- **Entry size:** the list pages' primary ("New task", "New project"), the New Task submit and Start run use the same cut shape at Body size: 52 px tall, at least 144 px wide, 24 px side padding, the label centred and never wrapped. `PagePrimary` is the `Button`'s own classes (`buttonVariants`), link or button.
- **Header controls:** every list-page header control that is not the primary is the ghost at 40 px, Body Semibold, the primary's label size (lead ruling, consistency pass); the ghost elsewhere stays Meta.
- **Start run:** the one action that starts a search is the entry-size cut shape in Green (#18a48c), hover #147a6c. It is the only green fill in the system and the only non-blue cut corner.
- **Secondary:** transparent, Navy Semibold, 14px horizontal padding, hover fills #f0f0f3.
- **Outline** (lead ruling P1): the secondary with a 1px Line 2 border on Paper, Navy Semibold Meta, hover #f0f0f3, at the secondary's heights. Pagination, the Download trigger, and the bordered actions inside a check-in or plan card.
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
- **Tones:** blue (tint fill, #c7c7ff border, blue text) for capability tags and BETA; soft (Ground fill, Grey text); green, yellow and red as pale tint fills with dark tone text. Every toned chip carries its label in text.
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
- **Status mark:** 6px square, always followed by a word, for the still states: Green complete, Orange paused, Line 2 idle, Red failed. Blue and breathing for a step in progress and a running task's row. The trace's top line, the status bar and the section being written show the turning fold mark instead (see Shapes).
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
- **Sources subtabs:** Meta Semibold in the Grey token (never a faded tint), Navy on hover, the active one Extrabold Navy, with the growing rule above.
- **The Mine/Organisation switcher** uses the tab language: Meta, a 2px Electric Blue rule under the active choice, no fill.

### Overlays
- **Tooltip:** Paper, Line 2 border, 10px by 6px padding, Caption Navy, tooltip lift. Scales in from its trigger over 125ms.
- **Popover:** Paper, Line 2 border, 16px padding, Meta Ink, 384px wide (capped at 92vw), overlay lift. Scales in from its trigger over 150ms. Menu items hover to Blue Wash with blue text.
- **Find a task / Find a project** (owner and lead, consistency pass): the header control opens a popover under itself, right-aligned. The field is focused on open, its placeholder "Search your tasks by name" ("…projects…"); with nothing typed it shows no result line, only the five most recent as a starting list. Results follow the typing 150 ms after the last key; "No tasks match “<words>”" appears only once there are words. The field is a combobox: the arrow keys move the highlight (the Blue Wash, never blue text, and the matched words are not marked), Enter opens the row, Escape or an outside press closes and returns focus to the control. Rows are 40 px, Body Navy, one line, truncated.
- **Menu** (the account menu, consistency pass): the popover's tokens with no inner padding, as wide as its content and at least 240 px, right-aligned under its button. Who you are first (name in Meta Bold, email and organisation in Caption Grey, 16 px padding), a hairline, then the items as 40 px Meta Semibold rows with the menu-item wash; Sign out, the one destructive item, last. It arrives from the button, 4 px above its place, fading and settling over 200 ms on the strong ease-out, and leaves the same way in 150 ms; a cut under reduced motion. The button shows the open state (Blue Wash) with `aria-expanded`; focus moves to the first item on open and back to the button on close; the arrow keys, Home and End move between items; Escape and an outside press close it.
- **Sheet:** slides from the right on the drawer curve over 260ms behind a 40% Navy scrim; title in the display face at Lead Bold. Becomes a bottom sheet below `md`.
- **Toast:** Paper, Line 2 border (Red for errors), 16px padding, overlay lift, bottom-right, rises 8px into place over 200ms.

### Report and citations (signature)
The report is a paper sheet in the 780px reading column. Body prose is Lead size on desktop, Body on mobile, within a 44em measure. Cited spans wash to Blue Wash on hover. Numbered citation markers are small square tags: Caption Semibold, 80% Electric Blue text on Blue Wash with a 25% blue border, deepening on hover. In print the sheet loses all chrome and colour; markers become plain black text.

While a section is being written (task 058, owner 2026-11-05), the page shows the evidence as the writer uses it: one Meta grey line under the heading, "Drawing on 4 sources · Smith 2023 · DfE 2022 · Nesta 2021 · and 1 more", from the first read until the checked section replaces the draft (nothing in it is a link while live).

**Markers while live** (owner round 7). As each of the writer's own citations closes, the marker's own chip sits after the cited sentence in its muted look: Caption Semibold, a Line border, Ground fill, Grey text, a dot for the number ("[·]"); not a control, the source titles as hover text, named "Cited, being checked: <titles>". When the section is checked, the report's numbered marker takes its place in the report's look ("[3]", 80% Electric Blue on Blue Wash), still not a control while the report is live (named "Citation 3, Smith 2023; details when the report is ready"); the provenance sheet arrives with the committed report. Blue still means checked. While the section's claims are checked the muted chips run a blue wave: each goes from its muted look to the checked marker's look at the peak (Blue Wash fill, the marker's 25% blue border, 80% blue text) and back over 1.2s, each 150ms after the one before (owner, round 9); still under reduced motion. The judged marker is unchanged. The draft layer, muted chips and all, fades off the checked prose, so the numbered markers never flash.

**The live page is the report page** (owner round 7). While it is written the Result tab is the committed report's own page: the contents beside it, the kind row, the question as the title, "See the plan", the part headings, the sections in the report's order through the report's section and prose components, the case-study cards in the report's card layout as each closes, and a numbered references list at the foot that grows as sections are checked (titles only, no links). What only the committed report has (the download, the facts strip, "Ask about this analysis", the most relevant sources, the method, links into provenance) is absent, with no placeholder. The committed report updates the same page in place: the scroll position stays, a section the reader was reading stays open, and only what arrives (the download, the facts strip, the expand controls, the chips, the reference details, a renumbered marker) fades in once over 300ms on the strong ease-out; under reduced motion it is a cut.

**Streamed prose** (owner round 7). The draft is paced in the browser at a steady rate with word snapping: a frame loop reveals whole words at max(0.15 characters per ms, backlog / 800ms), and a quiet draft shows its trailing word after 500ms (tuning values). Settled paragraphs are frozen; only the live paragraph re-renders, and the words each frame reveals fade in over 150ms, opacity only, one span per batch, dropped when the paragraph settles. A revision that shortens the text holds the section's height until it regrows. The page follows the text down only for a reader already within 40px of the end, and stops on the first scroll up. Under reduced motion the words appear without the fade; the pacing stays. No caret.

### The run trace (signature)
A run shows in the Task Agent conversation at its place in the thread (task 058; owner 2026-11-05) as one card from start to end (owner, round 8: the ended state is the same card): a Card (Paper, Line 2 hairline, the paper-weight shadow) the width of the thread's cards. It reads as a table: the top line and every step row share one template, the words on the left, the counts and times right-aligned in Grey tabular figures in one column, and the links right-aligned in Electric Blue Semibold in the last; every line shares the Body line box (1.55rem), so rows stand equal and each mark sits on the middle of its first line. Narrower than 32rem (a phone, the sidebar) the template lets go and a row's counts, time and link follow on the line under its label, the dot bound to the cell before the link.

- **Top line**, over a Line rule while the rows show: the mark, the state word in the Label style, the run's time in the time column. Live: the turning fold mark, "Running", the elapsed time; no Minimise, the rows stay open. Paused: the orange square, "PAUSED · a check-in is waiting on you" (the state word in the Label style, the rest in Grey; to a colleague "PAUSED · <step>"). Ended well: the Green square, the walk's finish words in the Label style ("REPORT READY"), the wall time to the minute and "Read it →" in the link column, the run's one destination. Stopped or failed: the Red square, "STOPPED" or "FAILED", no link. A finish that is a sentence (a degraded shortlist walk's "Policy Atlas could not propose a shortlist. Your places are unchanged.") keeps its case in Navy.
- **Rows**, one per plan step in plan order, each mark on a Line 2 hairline spine, a Line hairline rule between rows. A done row is its label in Navy at Body, then its counts and wall time, then its link (Searching and Screening → Sources, Classifying → Landscape at once, Mapping → Themes, Writing → Report; lead, round 8). The step in progress is its label in Navy Semibold, its own elapsed time, and its link while it runs (Searching and Screening → Sources, Classifying → Landscape, Mapping → Themes, Writing → Report; owner, round 8), with the writer's section line and the activity line under it; its 6px blue square breathes while updates arrive and the activity line breathes with it (the same 1.6s rhythm, opacity 1 to 0.6; the label holds still). Steps to come are names in Grey at Meta size. A row that lands keeps its place: its counts and time fade in over 300ms and its square eases from blue to green over 150ms (lead, round 9: it shrinks as it lands, so a rise read as a jump). As the step in progress gains or loses its section and activity lines the card eases to its new height over 300ms on the strong ease-out. "See plan" sits at the foot. Searching and Screening are two rows once the server splits them (owner, round 8).
- **Ended**, the rows fold behind one quiet control under the top line's words, "Show steps" with the conversation surfaces' chevron, which turns down and reads "Hide steps" when open; it stays put when the rows open below it. The rows fold and open by their height and opacity over 200ms, the chevron's time, the rule under the top line folding with them (round 9). A past run (not in the stream) is the same folded card with no steps and no control.

A screen reader hears the current step and what the model is doing now ("Writing · Section 3 of 7 · Costs and funding") from the card. The sidebar shows the same card (its text at Body size); outside the Agent tab the run status bar says the same words (see Layout); nothing else shows the run. The Result tab carries a small navy square when a section or the report landed while the reader was elsewhere (the Sources tab has none: owner, round 8), and the browser title carries "● Report ready" when the run finished unseen.

### Plan card and check-ins (signature)
A plan step is a Paper card under one small stepper line the client computes ("Plan · step 2 of 3 · Scope"), with the part's title, a radio list (label, then one plain sentence, in the planner's order; no "Recommended" word, no pre-selection), an input inside the card for an option that needs words, and the plan card's one green Start button. The scope card has no radio list: its chips (grouped under "Screening criteria" and "Source filters", each with a pencil and an ×, plus "+ add") are how the scope changes, and one secondary "Looks right" button records the choice with any staged edits. A settled part takes the user's side: the user bubble's surface (Blue Wash fill, 1px Blue Tint border, 14px by 10px padding, 32px left indent) with a 2px Green rule on its right edge over the bubble's border, the part's name as a grey Label, and under it the outcome in deep green bold (#0c6b5a) at Lead size, the scope's groups one line each under a grey label at Caption size (owner and lead, round 6), and while the card is the newest proposal "Change" on its own line under the green words, left-aligned, a quiet control at Caption size (Semibold Grey, underlined, hover Navy; owner, round 8). It settles the moment the user chooses, before the agent's reply (task 058, owner 2026-11-05), in one container (owner, round 8: a fluid settle): the options and controls fade out over 150ms while the card eases to its settled height and across to the user's 32px indent over 300ms on the strong ease-out, the surface and border ease to Blue Wash and the Green rule, and the settled words rise in; the stepper line above folds away with it. Under reduced motion it is a cut. A pending check-in is a Card with a 2px Orange left rule, the question as its title (no eyebrow, no chip), one facts line, the same radio list with the suggested option first, a closed "Or steer in your own words" disclosure and one "Stop the run" link; it rises in when it arrives in front of the reader and its Orange ring blooms once, 150ms later (task 058; round 9). It settles the moment the user chooses, as the part cards do: its contents fade out over 150ms while its box eases to nothing over 300ms, and the answered line rises in the run block when the run records the choice; if the answer fails it comes back open with its notice. Its "Confirm your steer" step eases the card to its new height, the new contents fading in over 150ms. Under reduced motion each is a cut. A failed turn renders as a 40% Red Tint surface with a Red Tint border and a secondary Retry button. User messages are indented 32px from the left in a Blue Wash bubble with a 1px Blue Tint border, square corners; agent messages are plain Lead prose at the 44em measure.

### The search queries (Sources, signature of round 9)
At the top of All sources (owner, round 9). While the search runs it is open under "Search queries" (Lead Semibold Navy): one table at Meta size with hairline rows, the Query and Results columns headed in the table-header label style, each backend once per group as a row-group label (Label treatment at Caption size, Grey), each query as it goes out (a citation pass's or lookup's description in Grey, a query in Navy), its Results cell a placeholder bar until the count returns and then the count right-aligned in tabular figures; a row that goes out fades in over 300ms. Queries wrap on words. The sources table and its count line stay hidden until the first results land, then rise in together. Once the search has ended the block folds to one Meta Grey line, "12 search queries · 312 results · Show", whose chevron opens the table over 200ms ("Hide" when open); the committed coverage replaces the live rows in place. Below `md` the same block spans the column.

### Charts (Landscape)
Ranked bars are a real table: label, Navy bar, the value at the bar's end; Grey for missing data and folded tails. A row leads somewhere when it can (owner, consistency pass): an evidence type opens All sources filtered to it (`?type=`), a finding group opens Findings filtered to it, a year's column opens All sources for that year (`?year_from=&year_to=`); folded rows, "Not reported", "Ungrouped", rows at zero, the funnel and the publisher countries (All sources has no country filter) lead nowhere and take no hover. One hover: the bar turns Electric Blue and the row's words go Navy, no row wash; the link covers the whole row and a keyboard focus rings the row. The relevant-source count is said once, in a Meta Grey line at the top of the page ("118 relevant sources"); a section heading carries a count only when it differs ("112 with a year", "34 findings", "Classified so far: 18 of 118").

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
- Loading skeletons breathe on the status mark's 1.6s rhythm (`anim-breathe`), so a page never shows two rhythms.

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
