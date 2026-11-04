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
- Status is always colour plus a word; colour alone never carries meaning
- Motion is evidence of data: rise on arrival, glow on a new check-in, breathe while running

## Product design principles

The team's six principles for Policy Atlas. Every surface, feature and piece of copy is
judged against them; the visual system below exists to serve them.

1. **Change behaviour, not just knowledge.** A feature that only informs is a research
   tool. A feature that shifts what gets drafted, checked, or escalated is a policy tool.
   For every feature, name the behaviour it changes, not just the information it adds.
2. **Give control if wanted.** Let expert users steer and override the tool directly:
   filter, pin, edit, or discard, rather than accepting outputs as final. Direct and guide
   automated searches and analyses. Identify thoughtful moments where users might want to
   take more control. Include customisable search parameters (jurisdiction, timeline,
   methodology) and intuitive controls to pin, edit, or discard generated content.
3. **Earn trust every time.** Maintain absolute credibility by eliminating hidden
   hallucinations and ensuring the AI's outputs are bulletproof against intense scrutiny.
   Mandatory, verifiable source citations for every claim, statistic, or policy example,
   so users can trace insights back to primary documents and data. Decision transparency
   about why the AI has or has not done something.
4. **Provide detail when needed.** Balance high-level summaries with the deep, granular
   evidence required to withstand rigorous cross-examination and ministerial challenge.
   Make information quick to find and grasp. Progressive disclosure: a concise executive
   takeaway expands down into raw transcripts, methodology notes, and full unedited source
   excerpts. Summarise by default for users short on time and attention.
5. **Assist human judgement.** Act as a co-pilot, not an autopilot: present trade-offs and
   open questions rather than a single answer, so the human, not the AI, makes the call.
   Frame outputs around trade-offs, risks, and missing perspectives rather than
   prescribing a single path, prompting critical thinking instead of passive acceptance.
6. **Share a team brain.** Break down internal silos by ensuring that individual
   discoveries, annotations, and curated evidence collections benefit the entire team.
   Shared workspaces where policy professionals collaborate and build on verified evidence
   threads, eliminating duplicated effort and working in isolation.

## Colors

Nesta's core palette at tool density: one hero, a structural navy, warm-neutral greys, and status colours that appear as pale tints with dark text.

### Primary
- **Electric Blue** (#0000ff): the hero. The one primary button per view, the active nav underline, the active tab rule, citation markers, the "Atlas" half of the wordmark, focus outlines. Pressed state deepens to **Electric Blue Pressed** (#0000d6).
- **Electric Blue Tint** (#ececff): chip fill for blue-toned chips (capability tags, BETA) and the border of the same chips at `#c7c7ff`.
- **Electric Blue Wash** (#f5f5ff): the palest blue. User message bubbles, citation marker fill, menu-item hover. Reads as "touched by the reader".

### Secondary
- **Navy** (#0f294a): structural text. Headings, nav links, button labels on secondary buttons, the "Policy" half of the wordmark, sheet titles. Also the splash page ground, where **Navy Muted** (#c8d6e6) carries body copy and **Aqua** (#b6e3e8) replaces blue as the accent.

### Tertiary (status and category)
- **Green** (#18a48c): complete. As a solid fill only on the "go" action that starts a run; otherwise as **Green Tint** (#e7f5f2) with deep green text (#0c6b5a).
- **Yellow** (#fdb633): running or pending. Status dot, the glow ring on a new check-in, **Yellow Tint** (#fff6e3) chips with brown text (#8a5a00).
- **Orange** (#ff6e47): paused or interrupted. Status dot and the interrupted-run banner border.
- **Red** (#eb003b): failed, error, and the sensitive-information banner (solid red, white text). Error text and **Red Tint** (#fde8ed) surfaces.
- **Purple** (#9a1bbe), **Violet** (#a59bee), **Pink** (#f6a4b7), **Sand** (#d2c9c0): Nesta secondaries defined as tokens but unused in the built UI. The evidence-distribution charts use Electric Blue bars on Line grid lines with Navy and Grey text only. The animated fold mark uses its own pastels (sand #ECC77F, teal #6FBFA7, salmon #F09B80, pink #E8B9C8), which are not theme tokens.

### Neutral
- **Ink** (#1c1c1e): body text.
- **Grey** (#646363): secondary text, pane headings, meta and caption copy, disabled ghost labels. AAA on white.
- **Line** (#e4e4e7): dividers, nav and footer borders, tab rails.
- **Line 2** (#d3d3d8): card and control borders, disabled fills, locked lifecycle tabs.
- **Ground** (#f4f4f5): the app background and the task-level nav bar.
- **Paper** (#ffffff): every surface that holds content. **Paper 2** (#fafafa) for a barely-lower sheet.

### Named Rules
**The One Pen Rule.** Electric Blue appears as a solid fill on at most one control per view. Everywhere else it is a rule, a marker or a word.

**The Word Beside the Colour Rule.** A status dot, chip tone or coloured border never stands alone. The label sits next to it in text.

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
- **Label** (700 or 800, 14px, uppercase, tracking 0.06em, Grey): pane headings (Extrabold), plan-step and check-in eyebrows (Bold; the check-in eyebrow is Electric Blue), report outline headings. The conversation list uses the same treatment at Caption size.
- **Chip** (600, 11.5px): a deliberate off-scale token. Chips sit below caption text by owner ruling.

### Named Rules
**The Sixteen Floor Rule.** Body prose never renders below 16px. Meta and caption sizes are for labels, cells and markers, never for sentences a reader must read.

**The Brand Voice Rule.** Zosia Display speaks as Nesta: wordmark, splash, sheet titles, system-state headings. Page and report titles are Averta Extrabold at Display size. Do not set page titles in Zosia.

**The Named Size Rule.** Every text size is one of the named scale tokens (`text-caption` through `text-display`). No ad-hoc pixel sizes in views; the one exception is the 11.5px chip.

## Layout

The app is full-bleed. A 64px top nav runs the viewport width with a 24px gutter, brand group left and links right; below `md` it wraps to a two-row nav at 16px gutters. Inside a task a second, grey-ground nav bar carries the task title and the five lifecycle tabs (Agent · Result · Sources · Share · History), spaced 20px apart; below `md` the tabs move to a bottom bar that scrolls horizontally and respects the safe-area inset.

Content lives in a centred reading column of 780px on list pages and the report. The report page is a paper sheet with 40px horizontal and 36px vertical padding, 32px vertical margin, a hairline Line ring and Tailwind's small shadow (not the card shadow); below `md` it loses margin, ring and shadow and pads at 16px, so the paper becomes the screen. Prose inside caps at a 44em measure.

The Agent workspace is a three-region layout: a 48px icon rail on the left (toggle, new chat, active task mark), a scrolling conversation column of about 700px, and a pinned composer at the bottom with a double-cut send button 48px wide and 40px tall. The current chat's mark in the rail sits on a Blue Tint fill. Popovers are 384px wide (capped at 92vw); sheets are up to 576px from the right edge, and collapse to a bottom sheet of at most 45svh below `md`.

Spacing follows the Tailwind 4px scale. Observed rhythm: 8px between chips and inline items, 16px inside cards and popovers, 20px between nav items, 24px page gutters, 40px report padding. Density is tool density, not marketing density: a list row is one line high with its metadata inline.

## Elevation & Depth

Flat paper with ambient lift only. Surfaces sit on the grey ground and are separated by a hairline border, not by shadow. Cards carry a soft, navy-tinted ambient shadow so faint that it reads as paper weight rather than elevation. Overlays lift further because they are temporary and must read as above the page: popovers, sheets and toasts share one deeper shadow, and the sheet adds a 40% navy scrim. Nothing else casts a shadow. Hover never adds a shadow; it changes colour.

### Shadow Vocabulary
- **Paper weight** (`box-shadow: 0 1px 3px rgba(15,41,74,0.05), 0 8px 24px rgba(15,41,74,0.04)`): cards at rest. Navy-tinted, near-invisible.
- **Sheet edge** (Tailwind `shadow-sm`, `0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)`, plus a 1px Line ring): the report page only. The one neutral shadow in the system; it disappears below `md` and in print.
- **Tooltip lift** (`box-shadow: 0 4px 16px rgba(15,41,74,0.12)`): tooltips only.
- **Overlay lift** (`box-shadow: 0 10px 30px rgba(15,41,74,0.14)`): popovers, sheets, toasts.
- **Check-in glow** (`0 0 0 6px rgb(253 182 51 / 0.25)` at the animation midpoint): a one-shot yellow ring marking a newly arrived check-in; it fades to nothing.

### Named Rules
**The Hairline First Rule.** Regions are separated by a 1px Line border. A shadow is added only when the surface is temporary and sits above the page.

**The Navy Shadow Rule.** Every custom shadow is tinted with Navy (`rgba(15,41,74,…)`), never neutral black, so lift stays in the palette. The report sheet's Tailwind `shadow-sm` is the recorded exception.

## Shapes

Zero radius everywhere. Buttons, cards, chips, inputs, popovers, sheets, toasts and tooltips all have square corners. The single exception is the 8px status dot, which is a circle so it reads as a dot and not a chip.

The signature form is the Nesta cut corner: a 45° clip removing 10px from the top-right of the primary button (8px on the small size). The composer's send button doubles it, cutting both top-right and bottom-left. The green run-start button shares the cut. No other element carries it, which is why the eye can find the way forward on any screen.

Borders are 1px hairlines. Active and selected states are expressed as a 3px bottom rule in Electric Blue (nav, lifecycle tabs) or a 2px rule (Radix tabs), never as a filled pill. Focus is a 2px Electric Blue outline offset 2px.

The fold-mark logo is the one piece of geometry with personality: a 17px diamond, a square sheet whose four corners have folded to the centre. It sits before the wordmark in the nav, marks each chat in the conversation rail, and forms the animated constellation on the splash page. While a run is active the nav mark animates through 36 frames of folding and rotating in its own pastels (sand, teal, salmon, pink), snapping shut to solid blue between sheets.

## Components

Precise and unadorned. Hard edges, hairline borders, no decoration. The cut corner is the only flourish. Feedback is a 3% press scale over 160ms on a strong ease-out and a 150ms colour ease; hover states never snap.

### Buttons
- **Shape:** square with a 10px top-right cut on primary (8px on small). Secondary and ghost have no cut.
- **Primary:** Electric Blue fill, white Averta Bold at Meta size, 18px horizontal and 11px vertical padding. Hover deepens to #0000d6. Disabled is Line 2 fill with white text, present but inert. One per view.
- **Entry size:** list-page "New task" and the New Task submit use the same cut shape at Body size with 24px by 14px padding.
- **Start run:** the one action that starts a search is the entry-size cut shape in Green (#18a48c), hover #147a6c. It is the only green fill in the system and the only non-blue cut corner.
- **Secondary:** transparent, Navy Semibold, 14px horizontal padding, hover fills #f0f0f3.
- **Ghost:** transparent, Grey Semibold, 12px by 9px padding, hover turns Navy. For Cancel and Back to top.
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
- **Divider:** 1px Line.
- **Status dot:** 8px circle, always followed by a word. Yellow running, Green complete, Orange paused, Line 2 idle, Red failed.

### Inputs / Fields
- **Style:** Paper fill, 1px Line 2 border, 12px by 10px padding, Lead size, square. The composer textarea grows with content (`field-sizing: content`) between 56px and 240px.
- **Focus:** 2px Electric Blue outline. Splash fields instead turn their border blue.
- **Error / Disabled:** error border Red with a red Body-size message beneath; disabled is Ground fill with Grey text.
- **Bare variant:** the New Task question field has no border or fill. It is Lead text on the paper card, with the primary button beside it.

### Navigation
- **Top nav:** 64px, Paper, hairline bottom border. Wordmark left (fold mark, "Policy" Navy, "Atlas" Electric Blue, display face at Heading size, tracked -0.02em) with a blue BETA chip carrying a tooltip. Links right at Lead Semibold Navy.
- **Growing underline:** the active link is Extrabold with a 3px Electric Blue bottom rule; inactive links have a transparent rule so nothing shifts.
- **Lifecycle tabs:** same rule language at Lead Semibold. Inactive is Grey, hover Navy, active Navy with the blue rule. Locked stages render in Line 2 with a not-allowed cursor and `aria-disabled`, so the whole lifecycle is visible from the first moment.
- **Mobile:** nav wraps to two rows; lifecycle tabs move to a bottom bar with horizontal scroll.
- **Radix tabs:** Meta Semibold Grey, 2px rule, active Extrabold Navy.

### Overlays
- **Tooltip:** Paper, Line 2 border, 10px by 6px padding, Caption Navy, tooltip lift. Scales in from its trigger over 125ms.
- **Popover:** Paper, Line 2 border, 16px padding, Meta Ink, 384px wide, overlay lift. Scales in from its trigger over 150ms. Menu items hover to Blue Wash with blue text.
- **Sheet:** slides from the right on the drawer curve over 260ms behind a 40% Navy scrim; title in the display face at Lead Bold. Becomes a bottom sheet below `md`.
- **Toast:** Paper, Line 2 border (Red for errors), 16px padding, overlay lift, bottom-right, rises 8px into place over 200ms.

### Report and citations (signature)
The report is a paper sheet in the 780px reading column. Body prose is Lead size on desktop, Body on mobile, within a 44em measure. Cited spans wash to Blue Wash on hover. Numbered citation markers are small square tags: Caption Semibold, 80% Electric Blue text on Blue Wash with a 25% blue border, deepening on hover. In print the sheet loses all chrome and colour; markers become plain black text.

### Plan card and check-ins (signature)
A plan step is a Paper card with a Label eyebrow ("PLAN · 2 OF 3 · SCOPE"), a Heading-weight question, a row of editable chips, and a primary button plus a text-only alternative. A pending check-in is a Card with a 2px Orange left rule and a yellow "Waiting on your input" chip; it glows once in Yellow when it arrives. A failed turn renders as a 40% Red Tint surface with a Red Tint border and a secondary Retry button. User messages are indented 32px from the left in a Blue Wash bubble with a 1px Blue Tint border, square corners; agent messages are plain Lead prose at the 44em measure.

## Do's and Don'ts

### Do:
- **Do** put exactly one Electric Blue cut-corner primary on each view, and reserve the cut for it, the green run-start button and the double-cut send button.
- **Do** separate regions with 1px Line hairlines; add shadow only to temporary overlays.
- **Do** pair every status colour with its word: dot plus label, chip tone plus text.
- **Do** use the named type scale and keep every sentence at 16px or above; drop report prose from Lead to Body below `md`.
- **Do** tint status colours (green, yellow, red tints with dark text) rather than filling with them.
- **Do** animate only to mark real data arriving, and quiet every animation under `prefers-reduced-motion`.
- **Do** render the locked lifecycle stages so the whole journey is visible; make them inert with `aria-disabled`.
- **Do** write labels in sentence case as actions, with just enough text.

### Don't:
- **Don't** round any corner except the 8px status dot.
- **Don't** stack shadows, add hover shadows, or use neutral black shadows; every shadow is navy-tinted.
- **Don't** build dashboard SaaS chrome: KPI tiles, rounded cards, badge clutter, icon-only sidebars without labels.
- **Don't** use Electric Blue as a second fill on the same view, or as a background wash for whole regions.
- **Don't** commit font binaries, or design a surface that only works when Averta and Zosia are present.
- **Don't** introduce an ad-hoc pixel font size; add a named token instead and register it in the merge config.
- **Don't** let colour carry meaning alone, and don't ship a chip, dot or border without its text label.
- **Don't** pair blue and orange as a meaningful contrast (Nesta guidance for Scotland-facing work).
