# Audit: 067 accessibility (WCAG 2.2 AA)

> **Status:** audited 2026-11-23 from the code on `dev` at `08c4fe50`; then worked on
> branch `task/067-accessibility`. The last section, "Status after the work", says what is
> done and what is open. `verification.md` has the evidence and the manual test list.
> Source: the external review of the landing page and stylesheet
> (`accessibility_improvements.md`, parts 1 to 3), plus a code audit of the signed-in views.
> This file is the map for the work. It follows the layout of
> `docs/tasks/064-security-hardening/programme.md`.

## How to read this file

- **Target:** WCAG 2.2 level AA. Where the repository has no rule of its own (`DESIGN.md`,
  `frontend/src/index.css`), the GOV.UK Design System is the reference.
- **Method:** every finding comes from reading the code. No finding comes from a browser, a
  screen reader or an automated tool. The section "Not verified from code" lists what that
  leaves open.
- **Limit of automated tools:** axe and `eslint-plugin-jsx-a11y` (part 3) find only a
  minority of accessibility problems, about a third by most estimates. They do not test
  keyboard order, screen reader output, zoom or forced colours. The manual test list at the
  end of the work is still necessary.
- **Severity:**
  - **High**: a group of users cannot do a task, or cannot see where they are.
  - **Medium**: fails a level AA criterion, but the user has a way around it.
  - **Low**: passes AA, or is close to it. A robustness or good-practice change.
- **Status against `dev`:** the external review looked at a deployed page. Some of its
  items are already corrected on `dev`. Each finding says **open**, **partly done** or
  **done**.
- Paths are relative to `frontend/src/` unless they start with another folder.

## Decisions for the owner

These findings change the visual design beyond focus states. The owner decided each one on
2026-11-23.

| Id | Decision | Outcome |
|---|---|---|
| D1 | Focus on cut-corner buttons: keep the inset ring that `dev` already has, or remove the cut corner while the button has focus (`clip-path: none`) | **Keep the inset ring.** It is the documented Focus Rule (`DESIGN.md` § Shapes), and the button does not change shape on focus. |
| D2 | Border colour of form fields | **Navy, 1px** (14.62:1 on white) on every text field, select trigger and unchecked checkbox. It is the border an open select already has. On the dark plan panel: On Navy Muted (6.83:1 on Navy Deep). |
| D3 | Splash animation | **Stop after 5 seconds** and hold the last frame. No new control. |
| D4 | Start button: white label on Green is 3.12:1 | **Approved:** Green Pressed (`#147a6c`, 5.21:1) as the fill and Green Deep (`#0c6b5a`, 6.43:1) on hover. |
| D5 | Other colour changes: a darker red for small red text (K3, K4), darker placeholders (K6, K7), and a different dash for two verdict lines on the theory of change (V1) | **All three approved.** |

## Part 1: the confirmed issues

### 1. Focus on cut-corner buttons (2.4.7 Focus Visible, 1.4.11 Non-text Contrast)

- **Status:** partly done. **Severity:** low (what remains).
- **Where:** the `cutout`, `cutout-2` and `cutout-sm` utilities, `index.css:178-210`. Used by
  `ui/brand/Button.tsx:30,44,57-58` (primary and start variants),
  `views/splash/SplashView.tsx:65` ("Request access") and
  `views/workspace/TaskAgentPane.tsx:317` (the Send button, a `Button`).
- **What the code does now:** `clip-path` removes everything outside the polygon, which
  includes an outline with a positive offset. `dev` already draws the ring inside the box:
  `Button.tsx:22` sets `CUT_FOCUS_RING` (2px white outline, offset -4px) on both cut
  variants, and `SplashView.tsx:65` sets a 2px Navy outline with the same offset. So every
  cut-corner element has a visible ring. The review's "the link has none" describes an
  older build.
- **Ring contrast:** white on Blue 8.59:1, Navy on white 14.62:1, white on Green 3.12:1
  (passes the 3:1 limit by a small margin; D4 improves it).
- **Fix (D1):** keep the inset ring. Add one test that fails
  when a `cutout*` class has no `focus-visible:outline` class next to it, so a new
  cut-corner element cannot lose its ring.

### 2. Form field borders (1.4.11 Non-text Contrast)

- **Status:** open. **Severity:** medium. **Decision D2.**
- **What the code does now:** the border is the only thing that shows where a field is. The
  field and the page around it are both white.

| Border | Ratio | Where |
|---|---|---|
| `border-line` `#e4e4e7` on white | 1.27:1 | `views/splash/WaitlistForm.tsx:271-272`; `views/workspace/chat/ConversationList.tsx:180` |
| `border-line-2` `#d3d3d8` on white | 1.49:1 | every other field: `ui/brand/Select.tsx:141`, `ui/brand/MultiSelect.tsx:127`, `views/toc/Editing.tsx:22` (`FIELD_CLASS`), `views/longlist/optionActions.tsx:23`, `views/SourcesView.tsx:1063`, `views/ShareView.tsx:214`, `views/FindPopover.tsx:176`, `views/workspace/TaskAgentPane.tsx:298`, `views/workspace/CheckInCard.tsx:530`, `views/workspace/CheckInBundle.tsx` (5 fields), `views/workspace/PartCard.tsx` (5 fields), `ops/ui.tsx:49` (`INPUT_CLASS`) |
| `border-navy/40` on white | 2.38:1 | the unchecked box, `ui/brand/Checkbox.tsx:44` |
| `border-white/25` on Navy Deep | 2.24:1 | fields on the dark plan panel, `views/workspace/PlanDocument.tsx:77` |

- **Fix (D2):** `border-navy` on the light fields and the unchecked box. On the plan
  panel, `border-on-navy-muted` (6.83:1 on Navy Deep). `border-line-2` stays for dividers,
  cards and the outline button, where the border does not identify a control on its own.

### 3. `outline-none` removes focus in forced colours (2.4.7)

- **Status:** open. **Severity:** medium for the two fields, low for the rest.
- **Concept:** Tailwind v4 changed the meaning of this class. `outline-none` is now
  `outline-style: none`, so nothing is drawn in any mode. `outline-hidden` draws a
  transparent outline, which Windows High Contrast replaces with a visible system colour.
  A border colour change is not a substitute: forced colours overrides border colours.
- **Where (all 10 uses in `src`):**

| Location | Element | Proposed fix |
|---|---|---|
| `views/splash/WaitlistForm.tsx:271` | the four waitlist fields, `outline-none focus:border-blue` | Delete both classes. The house ring in `index.css:497` then applies. |
| `views/workspace/chat/ConversationList.tsx:180` | the rename field, `focus:border-blue focus:outline-none` | The same. |
| `views/NewTaskView.tsx:296` | the composer textarea | No change. Its wrapper (`:274`) draws a real 2px outline with `focus-within`, which forced colours keeps. |
| `ui/radix/Popover.tsx:29`, `ops/ui.tsx:575` | a popover or dialog panel that receives focus from code | `outline-hidden` |
| `views/ArtefactView.tsx:3870`, `views/longlist/ShortlistView.tsx:233`, `views/longlist/OptionCard.tsx:572`, `views/longlist/LonglistView.tsx:672`, `views/NameMenu.tsx:258` | a heading or sentence with `tabIndex={-1}` that receives focus from code | `outline-hidden` |

- `DESIGN.md:440` says "Splash fields instead turn their border blue". That line changes
  with this fix.

### 4. The landing `h1` does not grow with zoom (1.4.4 Resize Text)

- **Status:** open. **Severity:** medium.
- **Where:** `index.css:81` `--text-hero: clamp(40px, 5.4vw, 68px)` and `index.css:83`
  `--text-hero-2: clamp(28px, 3vw, 40px)`. No other font size in `src` uses `vw`.
  `--text-hero-2` is used only by `SplashFeatureSteps`, which a flag hides today.
- **Concept:** browser zoom makes the viewport narrower in CSS pixels. A `vw` term gets
  smaller as the user zooms in, so it cancels part of the zoom. In a 1440px window at 200%
  zoom the `h1` grows only 1.18 times.
- **Proposed fix:** `clamp(2.5rem, 2rem + 3vw, 4.25rem)` for the hero and
  `clamp(1.75rem, 1.5rem + 1vw, 2.5rem)` for the second size. The `rem` part grows with
  zoom and with the user's font size setting.
- **What stays true after the fix:** the `h1` then grows about 1.6 times at 200% zoom in a
  1440px window, not 2 times. Any size that depends on viewport width has this property.
  The text does reach 200% of its start size at higher zoom, which is the usual reading of
  1.4.4. A fixed size is the only way to get exactly 2 times at 200%.
- **Related, low:** the whole type scale is in `px` (`index.css:63-76`). Browser zoom
  scales it, so 1.4.4 passes. A user who changes only the default font size in the browser
  settings gets no change. GOV.UK uses `rem`. Not in scope unless the owner asks.

### 5. Landmarks on the landing page (1.3.1 Info and Relationships, 2.4.1 Bypass Blocks)

- **Status:** open. **Severity:** medium.
- **Where:** `views/splash/SplashView.tsx:40-164`. The page has a `<header>` and three
  `<section>` elements without names. There is no `<main>` and no `<footer>`.
- **Proposed fix:** wrap the hero and the request form in one `<main>`. Change the last
  section (`#links`) to `<footer>`. The app shell is in part 2.

### 6. Links that open a new tab give no warning (3.2.5 is AAA; good practice at AA)

- **Status:** open. **Severity:** low.
- **Where:** 14 links with `target="_blank"`, no shared component:
  `ui/brand/ReferenceUrl.tsx:24`, `ui/brand/EvidenceMarks.tsx:75`,
  `views/SourcesView.tsx:1542`, `views/toc/uploads.tsx:49`, `views/toc/DetailPanel.tsx:183`,
  `views/toc/Documents.tsx:261`, `views/splash/SplashView.tsx:124,134,144`,
  `views/workspace/PlanDocument.tsx:1048`, `views/workspace/TaskAgentPane.tsx:364,445`,
  `views/legal/LegalPage.tsx:47`, `ops/views/CohortsView.tsx:156`.
- **Proposed fix:** one `ExternalLink` component in `ui/brand/` that sets `target`, `rel`
  and a visually hidden " (opens in new tab)". Each of the 14 links uses it. GOV.UK shows
  the words on screen; the review asked for hidden text, so hidden is the default here.

### 7. Hover styles without a focus equivalent (2.4.7, 1.4.1 Use of Color)

- **Status:** partly done. **Severity:** low, with one medium case.
- **What the code does now:** the house ring (`index.css:497`) gives every link, button and
  field a 2px outline on keyboard focus, so no control is without a focus style. The four
  controls that hover reveals (`ui/brand/SortableColumnHeader.tsx:32`,
  `views/ListRowMenu.tsx:76`, `views/workspace/chat/ConversationList.tsx:209`,
  `views/workspace/chat/ChatSidePanel.tsx:179`) also appear on focus.
- **What is missing:** about 35 links and link-style buttons show an underline on hover
  only (`hover:underline`). A keyboard user gets the ring but not the underline.
- **Medium case (1.4.1):** a link inside a sentence that differs from the words around it
  by colour alone. Blue against Ink is 1.98:1 and against Navy 1.70:1; the criterion needs
  3:1 or a second cue. Found at `views/workspace/TaskAgentPane.tsx:445` and
  `ops/views/CohortsView.tsx:156` (`text-blue hover:underline`). Fix: underline these
  always.
- **Proposed fix for the rest:** one line in `index.css` that makes every `hover:` utility
  also apply on `:focus-visible` (a Tailwind `@custom-variant`). That gives each control
  the same style for keyboard focus as for the mouse, with no edit to 150 class strings.
  The other way is to add `focus-visible:underline` at each of the 35 places.

### 8. Splash animation (2.2.2 Pause, Stop, Hide; 2.3.3 Animation from Interactions)

- **Status:** partly done. **Severity:** medium. **Decision D3.**
- **How it works:** `views/splash/SplashField.tsx:169-176` runs a `requestAnimationFrame`
  loop. Each frame calls `setSheets(place(clock))`, and React writes new SVG path data and a
  new `rotate()` value. The header mark, `ui/brand/FoldMarkAnimated.tsx:63-75`, does the
  same. No CSS animation is involved, so the reduced-motion rules in `index.css` have no
  effect on it. The review is correct on that point.
- **Already correct:** both components read `prefers-reduced-motion` with `matchMedia`
  (`SplashField.tsx:22-27`, `FoldMarkAnimated.tsx:12-17`), listen for a change, and then
  draw one still frame. Both are `aria-hidden`.
- **What fails:** without that setting the loop never stops and the page has no pause
  control. 2.2.2 requires one of the two for movement that starts on its own, lasts more
  than 5 seconds and sits next to other content.
- **Conflict with the motion rule:** `index.css:222` says an animation marks real data
  arriving, never decoration. The splash field is decoration. The same component is used
  correctly in the app as a "working" mark (`ui/brand/Card.tsx:117`,
  `views/workspace/ActionLine.tsx:35`), where it runs only while a run is live.
- **Proposed fix:** stop the loop 5 seconds after it starts and hold the last frame, in
  `SplashField` and in the header mark on the splash page only. The in-app "working" marks
  are a status indicator and stay as they are.

### 9. Request-access form (3.3.1 Error Identification, 3.3.3 Error Suggestion, 4.1.3 Status Messages)

- **Status:** partly done. **Severity:** medium.
- **Where:** `views/splash/WaitlistForm.tsx`.
- **Already correct:** each field has a `<label>`; `aria-invalid` and `aria-describedby`
  point to the error (`:148-150` and the same in each field); the error is text, not colour
  alone; `autoComplete` is set (1.3.5).
- **What fails:**

| Line | Problem | Proposed fix |
|---|---|---|
| `:66-72` | A failed submit shows the errors and leaves focus on the Submit button. | Move focus to the first field that has an error. Its `aria-describedby` then reads the error. |
| `:259` | Submit is `disabled` while a field is over its limit or the puzzle is not solved. A disabled button cannot take focus and says nothing about why. | Disable only while the request is in flight. On submit, an over-limit field counts as an error, and an unsolved puzzle shows "Solve the puzzle to continue". |
| `:246-253`, `:255` | The success message is added to the page at the moment the Submit button is removed. Focus falls to the page body, and a live region that is created with its text already inside is not announced by every screen reader. | Move focus to the success message (`tabIndex={-1}`). |
| `:246-253` | A server error uses `role="status"`. | `role="alert"`. |
| `:302` | Each field error is `role="alert"`, and the over-limit text changes on every key press, so a screen reader speaks on every key press. | Keep `role="alert"` for the missing and invalid messages; the over-limit count is linked with `aria-describedby` only. |

- **Not in this code:** the puzzle is drawn by AWS WAF (`wafCaptcha.ts`). AWS documents an
  audio version; this audit cannot confirm it.

### 10. Sign-in dialog (2.1.2 No Keyboard Trap, 2.4.3 Focus Order)

- **Status:** not applicable in this repository.
- **What the code does:** "Sign in" (`views/splash/SplashView.tsx:28-37`) does not open a
  dialog. It redirects the browser to the Cognito managed sign-in page (ADR 0049). AWS
  draws that page; the branding is set in `infra/infra/cognito_auth.py`. It needs its own
  manual test.
- **Local development only:** without OIDC the button shows a token field lower on the
  page and scrolls to it, but focus stays on the button. Low; move focus to the field.
- The dialogs that the app does have are in part 2.

### 11. Wrong comment on `--color-grey`

- **Status:** open. **Severity:** low.
- **Where:** `index.css:99` says "AAA on white". Grey on white is 5.99:1. AA needs 4.5:1
  and AAA needs 7:1, so it is AA only. `DESIGN.md:276` repeats the claim ("AAA on white").
  Correct both.

## Part 2: the signed-in views

Each finding has an id. The letter is the topic: **H** headings and landmarks, **L** live
updates, **C** citations and panels, **T** tables, **V** charts and visual encodings, **K**
contrast, **S** scroll and reflow, **P** page titles, **F** focus management, **R** roles
and names.

### Headings and landmarks (1.3.1, 2.4.1, 2.4.6)

The report has one `h1` when it is complete (`views/ArtefactView.tsx:3867`), then `h2` parts,
`h3` sections and `h4` cards with no level skipped. Every route has one `<main>`, and every
`<nav>` and `<aside>` has a name.

| Id | Where | Problem | Sev | Proposed fix |
|---|---|---|---|---|
| H1 | none in `src`; `views/AppShell.tsx:414-510` | No "Skip to main content" link. Two navs, the banners and the status bar come before the page content. | medium | A visually hidden link that shows on focus, first in `AppShell` and `PublicTaskShell`, to a wrapper around the routed view. |
| H2 | `views/ArtefactView.tsx:3681`, `:3697`, `:2925`, `:3045` | The report has no `h1` while it loads, on an error, or when the question is empty. | low | A visually hidden `h1` "Report" in those states. |
| H3 | `views/WorkspaceView.tsx:127-196` | The Agent tab has no `h1`. The task name is a `<span>`. | low | A visually hidden `h1` with the task name. |
| H4 | `views/ArtefactView.tsx:1418`, `:2046-2053`, `:3165` | Report prose is one `<p>` with `whitespace-pre-line`; paragraphs are line breaks inside it. A list is a real `<ul>` only when every line starts with `- `. | low | One `<p>` for each paragraph. The comment at `:1973` says the single element is deliberate (nothing moves at the swap), so check that first. |
| H5 | `views/ArtefactView.tsx:1385`, `:2033`, `:4034` | Lists with `list-style: none` lose their list role in Safari with VoiceOver. | low | `role="list"`, as `ui/brand/BulletList.tsx:36` has. |
| H6 | `views/ArtefactView.tsx:3293` | A source card's title is a bold `<p>`. The case study card beside it uses a heading (`:3233`). | low | The same heading component. |
| H7 | `ui/brand/PageHeader.tsx:118-125` with `views/ProjectsView.tsx:445-456` | The project `h1` contains the settings button and, during a rename, the field and its buttons. | low | Put the controls next to the `h1`, not inside it. |
| H8 | `views/AppShell.tsx:496` with `ui/feedback/ErrorBoundary.tsx:36-38` | A crash in the chat side panel renders a second `<main>` and `<h1>`. | low | A fallback for that boundary without `<main>`. |

### Live updates (4.1.3 Status Messages)

**Concept:** a live region speaks when its content changes. A region that is added to the
page with its text already inside is not announced reliably, and a region that is emptied
says nothing. So "it finished" needs a region that stays on the page and receives new words.

No live region wraps the streamed text, so a screen reader does not speak each word as it
arrives. Section changes are announced ("<section> is being written",
`views/ArtefactView.tsx:2933`).

| Id | Where | Problem | Sev | Proposed fix |
|---|---|---|---|---|
| L1 | `views/ArtefactView.tsx:2933-2935`; `views/RunStatusBar.tsx:293-297` | The end of a run is not announced. Both regions become empty when writing stops, and the report's region is removed at the swap to the complete report. | medium | Keep one visually hidden status element in both states and write the finished words into it ("Report ready"). |
| L2 | `views/workspace/ActionLine.tsx:33`; `views/workspace/TaskAgentPane.tsx:711-722` | A finished Task Agent or chat reply is not announced. The status line is removed when the reply arrives. | medium | One permanent visually hidden status element in `TaskAgentPane` and `ChatPane`, written once for each completed reply. |
| L3 | `views/workspace/CheckInCard.tsx:250`, `:342`, `:397` | `aria-live="polite"` is on the whole card. Every change inside the card is spoken, and the `role="alert"` messages inside it can be spoken twice. | medium | Remove `aria-live` from the three cards. Move focus to the card's heading when the card arrives. |
| L4 | `views/ArtefactView.tsx:3681`, `:3414`; `views/FindingsView.tsx:460`; `views/ThemesView.tsx:208`, `:317`; `views/HistoryView.tsx:306`; `views/toc/TocResult.tsx:287`; `views/LandscapeViewSkeleton.tsx:22` | Loading skeletons say nothing. `aria-busy` with `aria-label` on an element that has no role is ignored. | low | `role="status"` with visually hidden "Loading…" text; the bars `aria-hidden`. |
| L5 | `views/ArtefactView.tsx:1621-1629` | A section that is not written yet is a heading with hidden placeholder bars after it. | low | Visually hidden "Not written yet". |

### Citations and panels (2.4.3 Focus Order, 2.1.1 Keyboard, 4.1.2 Name, Role, Value)

A citation marker is a real `<button>` with a descriptive name: "Source 2: <title>" or
"Sources 7 and 12" (`views/ArtefactView.tsx:1030-1037`, `:1152-1159`). It is in the tab
order, its tooltip opens on focus and closes on Escape, and Enter opens a panel that keeps
focus inside and closes on Escape.

| Id | Where | Problem | Sev | Proposed fix |
|---|---|---|---|---|
| C1 | `ui/radix/Sheet.tsx:40-49`, `:76` | **Focus is lost when a citation's panel closes.** Radix returns focus to the dialog's trigger. Every sheet in the app is opened by state, with no trigger, so focus falls to the page body and the user starts again at the top of the report. | high | In `SheetContent`, remember the focused element when the sheet opens and focus it again in `onCloseAutoFocus`. `ops/ui.tsx:567-572` already does this. |
| C2 | `views/ArtefactView.tsx:428-432`, `:688-695`; `views/FindingsView.tsx:290-305` | The reasons for evidence type and strength are in a tooltip on a `<span>` that cannot take focus. Keyboard and touch users cannot open them. | medium | Make the trigger a `<button>`, as `ui/brand/InfoHint.tsx:33-46` does. |
| C3 | `views/SourcesView.tsx:647`, `:662`, `:711`, `:1218` | The same reasons in the Sources table are on buttons with `tabIndex={-1}`: named, but not reachable. | medium | Delete `tabIndex={-1}`. |
| C4 | `views/workspace/chat/ChatMessages.tsx:225-238`, `:278-292` | A `<span role="button">` contains the `[n]` buttons. One interactive control inside another is not valid. | medium | Make the markers siblings of the claim. |
| C5 | `views/ArtefactOutline.tsx:427-455`, `:518-523` | A contents link scrolls to its section but focus stays in the contents list. | medium | After the scroll, focus the section's heading. |
| C6 | `views/ArtefactView.tsx:3380-3402` | The result tabs have no tab panel; `aria-controls` points at an element that does not exist. | low | Render the view inside `TabsContent`. |
| C7 | `views/DownloadMenu.tsx:29-60`; `views/toc/Editing.tsx:147-160` | `role="menu"` without arrow keys. | low | Use `moveMenuFocus` from `ui/radix/menu.ts`. |

### Tables (1.3.1)

Tables in the report body use `<th scope>` and a caption or `aria-labelledby`
(`views/ArtefactOutline.tsx:828`, `:853`, `:877`). There are no tables built from `<div>`.

| Id | Where | Problem | Sev | Proposed fix |
|---|---|---|---|---|
| T1 | `views/FindingsView.tsx:481-499` | No name; no `scope` on any `<th>`. | medium | `aria-label="Findings"`, `scope="col"`. |
| T2 | `views/SourcesView.tsx:498`; `views/longlist/LonglistGrid.tsx:169`; `views/longlist/OptionCard.tsx:766`; `views/toc/DetailedInformation.tsx:199`; `views/SearchQueries.tsx:244` | Correct headers, no name. | low | `aria-label` or `aria-labelledby`. |
| T3 | `views/sources.css:205-213` | On a narrow screen the header row is `display: none`, so cells lose their column names. | low | Hide it visually, not from assistive technology. |
| T4 | `ui/brand/SortableColumnHeader.tsx:75` | The `aria-label` "Sort by title" replaces the column name when cells are read. | low | Remove the `aria-label`; `aria-sort` carries the state. |
| T5 | `ops/ui.tsx:431` and four ops views | Ops console: `<th>` without `scope`; the Organisations table has no name. | low | `scope="col"`; one `aria-label`. |

### Charts and visual encodings (1.1.1 Non-text Content, 1.4.1 Use of Color, 2.1.1)

The bar charts and the years chart are correct: each has a real table or a visually hidden
data table (`views/LandscapeViewCharts.tsx:98-143`, `:619-635`). Colour squares, chips and
status marks always have a word next to them. `--color-violet-tint` and `--color-aqua-tint`
(`index.css:141-142`) are not used anywhere; profile lines use a Navy square and a word.

| Id | Where | Problem | Sev | Proposed fix |
|---|---|---|---|---|
| V1 | `index.css:532-535`; `views/toc/ReadingGuide.tsx:29-36` | **Verdict lines on the theory of change differ by colour alone.** "Leaning supports" (green) and "Leaning against" (red) have the same dash, `12 5`. "Supported" (green) and "Mixed" (yellow) are both solid. | medium | A different dash for "Mixed" and for "Leaning against", in the stylesheet, the legend and the image export. **Visual change: decision D5.** |
| V2 | `views/LandscapeViewMap.tsx:163-208`; `views/LandscapeViewCharts.tsx:272-299` | The map shows every country. The list folds the tail into "Other countries (N)". The counts for those countries exist only in a tooltip that opens for a mouse. | medium | A visually hidden table of all countries next to the map, as the years chart has. |
| V3 | `views/toc/TocCanvas.tsx:553-578`, `:624` | Canvas boxes have no accessible name. A connection is named by its verdict only ("Supported"), not by the boxes it joins. | medium | `ariaLabel` on each box (code, text, layer) and on each connection (from, to, verdict). |
| V4 | `views/toc/TocCanvas.tsx:573`, `:671-674` | A box can be moved by drag only (also 2.5.7 Dragging Movements). | medium | Arrow keys on a focused box. |
| V5 | `views/ThemesView.tsx:376` | An excluded option is shown by grey text alone. | medium | The word "(excluded)". |
| V6 | `ui/brand/taskStatus.ts:72-104` | "Interrupted" and "aborted" both read "Stopped"; one has a red mark and one a grey mark. | low | Different words, or one colour. |
| V7 | `views/toc/TocCanvas.tsx:649-657` | The library's default instructions ("arrow keys to move") are read for boxes that cannot be moved that way. | low | `ariaLabelConfig` with correct text. |

### Contrast (1.4.3 Contrast Minimum, 1.4.11 Non-text Contrast)

Ratios are computed with the WCAG formula from the hex values in `index.css`. Text needs
4.5:1 (3:1 at 24px, or 18.66px bold). A control boundary or a meaningful graphic needs 3:1.
`text-caption` is 12px and `text-meta` is 14px, so both need 4.5:1.

**Pairs that pass**

| Text | Background | Ratio |
|---|---|---|
| Grey `#646363` | Paper `#ffffff` | 5.99 |
| Grey | Ground `#f4f4f5` (the app background) | 5.45 |
| Grey | Paper 2 `#fafafa` | 5.74 |
| Grey | Hover Fill `#f0f0f3` | 5.27 |
| Grey | Blue Tint / Blue Tint 2 | 5.14 / 5.53 |
| Grey | Green Tint / Yellow Tint / Red Tint | 5.34 / 5.57 / 5.12 |
| Navy `#0f294a` | Paper / Ground / Yellow Tint / Red Tint | 14.62 / 13.30 / 13.61 / 12.49 |
| Ink `#1c1c1e` | Ground | 15.48 |
| Blue `#0000ff` | Paper / Ground / Blue Tint / Blue Tint 2 | 8.59 / 7.82 / 7.37 / 7.93 |
| White | Blue / Blue Pressed / Red | 8.59 / 10.65 / 4.57 |
| Red `#eb003b` | Paper | 4.57 |
| Green Deep `#0c6b5a` | Green Tint / Paper 2 | 5.74 / 6.16 |
| Yellow Deep `#8a5a00` | Yellow Tint | 5.52 |
| Navy Muted, Aqua, On Navy, On Navy Soft | Navy | 9.90, 10.54, 12.41, 9.35 |
| On Navy Muted `#97a8bc` | Navy / Navy Deep | 6.02 / 6.83 |
| White at 50% | Navy (splash separators) | 4.74 |

**Pairs that fail**

| Id | Pair | Ratio | Where | Proposed fix |
|---|---|---|---|---|
| K1 | White on Green `#18a48c`, 14px and 16px bold | 3.12 | the Start button, `ui/brand/Button.tsx:44` | Decision D4. |
| K2 | Green on Paper 2 | 2.99 | "✓ verified", `views/FindingsView.tsx:128`, `:135` | `text-green-deep` (6.16). |
| K3 | Red on Red Tint, 11.5px | 3.90 | the red chip, `ui/brand/Chip.tsx:24`; `ops/views/PeopleView.tsx:526` (3.85) | A new token, Red Deep `#b8002e` (5.83 on Red Tint). |
| K4 | Red on Ground | 4.16 | `views/HistoryView.tsx:133` | Red Deep (6.21 on Ground). |
| K5 | Orange on Orange at 10%, 11.5px | 2.50 | `ops/OpsShell.tsx:31` (ops console) | Navy text on the same tint. |
| K6 | Placeholder at the browser default (50% of the text colour) | 3.09 to 3.28 | `views/SourcesView.tsx:1092`, `:1109`; `ui/brand/MultiSelect.tsx:124`; `ops/ui.tsx:243` | `placeholder:text-grey` (5.99). |
| K7 | Placeholder Grey at 80% | 3.83 | `views/longlist/optionActions.tsx:23` | `placeholder:text-grey`. |
| K8 | Text under revision, opacity 0.55 | 3.84 | `index.css:598-606` | Temporary state. Under reduced motion use opacity 1. |
| K9 | House focus ring, Blue on Navy | 1.70 | every control on the dark plan panel, `views/workspace/PlanDocument.tsx:73-77`, `:293` | `focus-visible:outline-white` on the panel's controls. A focus state, so no decision is needed. |
| K10 | Field and checkbox borders | 1.27 to 2.38 | part 1, item 2; also the option ring, `views/workspace/PartCard.tsx:570` | Decision D2. |
| K11 | Yellow line on Paper 2 | 1.69 | "Mixed" verdict line, `views/toc/TocCanvas.tsx:604` | With V1: the dash carries the meaning, and the verdict word is in the panel. A darker yellow is the full fix. |
| K12 | Green line on Paper 2 | 2.99 | "Supported" verdict line | Green Pressed `#147a6c`. |
| K13 | Lightest map step on Paper; against "no data" | 2.24; 1.50 | `views/LandscapeViewMap.tsx:101`, `:118` | V2's data table is the text alternative. A darker first step is the full fix. |
| K14 | Green at 55% on Paper | 1.84 | the "weak" block, `views/toc/Documents.tsx:36` | The blocks are named buttons with counts; low priority. |

Not failures: `text-line-2` (1.49) is used only for disabled controls and decorative marks,
which the criterion exempts. One case is worth a change: a locked stage in
`ui/brand/LifecycleBar.tsx:86-93` gives its reason only in a `title` and in hidden text.

### Scroll containers and reflow (2.1.1, 1.4.10 Reflow, 1.4.4)

| Id | Where | Problem | Sev | Proposed fix |
|---|---|---|---|---|
| S1 | `views/AppShell.tsx:383-387`, `:417`; `views/PublicTaskShell.tsx:46-49`, `:80` | **Task pages lock the page to the viewport height** (`h-svh overflow-hidden` on the shell and on `<html>`). At 400% zoom (a 320 by 256 window) the fixed navigation, banner and tab bar use about 230px and leave about 25px for content. An estimate from the classes; test in a browser. | high | Lock the viewport only when there is room (from the `md` breakpoint, or above a minimum height). Otherwise let the document scroll. |
| S2 | `views/workspace/TaskAgentPane.tsx:1135-1145`; `views/workspace/chat/ChatPane.tsx:105-115`; `views/workspace/chat/DraftChatPane.tsx:62`; `views/AppShell.tsx:511-516`; `views/workspace/PlanDocument.tsx:1406` | A scroll pane can be scrolled by keyboard only when something inside it has focus. A conversation of plain text has nothing to focus. | medium | `tabIndex={0}`, `role="group"` and a name on each pane. |
| S3 | `views/WorkspaceView.tsx:184-195`; `views/workspace/chat/useFooterReveal.ts:55-69` | On the Agent tab the footer (AI notice, Privacy, Terms) is `inert` until a mouse wheel or touch scroll opens it. Keyboard and screen reader users cannot reach it. | medium | Also open it when the conversation is at its end and focus moves past the composer; or put it at the end of the scroll pane. |
| S4 | `views/WorkspaceView.tsx:140-176`; `views/workspace/PlanDocument.tsx:1383-1388` | On the Agent tab the plan sits beside the conversation at every width: about 160px each at 320px. | medium | Below `md`, lay the plan over the column, as `views/AppShell.tsx:283` does on other tabs. |
| S5 | `views/AppShell.tsx:75`; `views/RunStatusBar.tsx:263`; `views/TaskListRow.tsx:145`, `:170-177` | Truncated text has its full form only in a `title`. | low | Two lines below `md`. |
| S6 | `views/workspace/TaskAgentPane.tsx:362`; `views/NewTaskView.tsx:139-141` | Two fixed widths can overflow at 320px. | low | `max-w-[min(16rem,100%)]`; remove `shrink-0`. |

### Page titles (2.4.2 Page Titled)

Every route sets a title with `useDocumentTitle`, with one exception.

| Id | Where | Problem | Sev | Proposed fix |
|---|---|---|---|---|
| P1 | `views/ArtefactView.tsx:3349`, `:3405-3411` | The result route sets a title only for a report or a baseline. For a longlist, a shortlist or a theory of change the title of the previous view stays. | medium | `useDocumentTitle(task name, "Longlist" / "Shortlist" / "Theory of change")` in those three components. |
| P2 | `views/splash/SplashView.tsx` | The landing page keeps the static title "Policy Atlas". | low | Acceptable; no change. |

### Focus management (2.4.3, 2.4.11 Focus Not Obscured)

| Id | Where | Problem | Sev | Proposed fix |
|---|---|---|---|---|
| F1 | `views/workspace/PlanDocument.tsx:1372-1376`, `:1282-1290` | **The plan document is a hand-made dialog.** It has `role="dialog"` but focus does not move into it when it opens. `aria-modal` is never true, because the "center" placement cannot occur (`views/WorkspaceView.tsx:66`, `:84`, `:105`). On a narrow screen it covers the page while focus stays on the hidden button behind it. | high | Move focus into the panel when it opens (`tabIndex={-1}` on the `<aside>`). When the scrim shows, set `aria-modal` and make the page behind `inert`. Using the existing Radix `Sheet` is the larger alternative. |
| F2 | `routes.tsx`; `views/AppShell.tsx:374-379` | A route change resets the scroll position only. Focus stays on the link, or falls to the body when the link is removed. Nothing is announced. | medium | On a path change, focus the routed `<main>` (`tabIndex={-1}`). Four views already focus their title (`lib/openAtTop.ts:33`). |
| F3 | `views/workspace/CheckInCard.tsx:165`, `:248-314` | An answered check-in makes its content `inert` while the pressed control has focus, so focus is lost. | medium | Focus the composer before the card leaves. |
| F4 | `views/workspace/chat/ChatComposer.tsx:19` | The chat field is removed while a reply streams, and focus is not put back afterwards. | medium | Keep the field mounted and disabled. |
| F5 | `views/ProjectsView.tsx:111`, `:148-149`, `:313-319` | Focus is lost after a row is archived and after the New project form closes. | low | Focus the next row; focus the "New project" button. |

### Roles and names (4.1.2, 2.5.3 Label in Name, 3.3.2)

| Id | Where | Problem | Sev | Proposed fix |
|---|---|---|---|---|
| R1 | `views/workspace/CheckInCard.tsx:360`, `:449`; `views/workspace/PartCard.tsx:557-563` | Options have `role="radio"` but behave as buttons: each is a tab stop, there are no arrow keys, and a press submits at once. | medium | `role="group"` with plain buttons. |
| R2 | `views/TaskListRow.tsx:106-127` | The row's `aria-label` leaves out the capability and the source count, which are visible. | medium | Add both to the name. |
| R3 | `views/workspace/chat/ConversationSidebar.tsx:140-149`; `views/workspace/chat/ConversationRail.tsx:68-72`; `views/workspace/chat/ChatSidePanel.tsx:183-198`; `views/workspace/TaskAgentPane.tsx:296-298`; `views/ArtefactView.tsx:3884-3892` | A disabled control gives its reason only in a `title`, a tooltip on a wrapper that cannot take focus, or a placeholder. | medium | Show the reason as text, as `views/workspace/chat/ChatComposer.tsx:20` does. |
| R4 | `ui/brand/Nav.tsx:98-104` | "Tasks" looks current on a task page but has no `aria-current`. | low | `aria-current="page"`. |
| R5 | `views/ScopeSwitcher.tsx:44-50` | `role="tablist"` without panels or arrow keys. | low | Buttons with `aria-pressed`. |
| R6 | `ui/brand/Nav.tsx:53`; `views/toc/DetailPanel.tsx:244` | A focusable `<span>` with no role. | low | `<button type="button">`. |
| R7 | `ui/brand/Select.tsx:171-191` | Every option is a tab stop, so Tab goes through the whole list. | low | `tabIndex={selected ? 0 : -1}`. |
| R8 | `views/ArtefactOutline.tsx:659-666`; `views/ArtefactView.tsx:1164-1174` | Names that repeat or say too little: "Show" for each section; "gap", "pattern", "theme". | low | `aria-label` with the section title; "Evidence gap: details". |
| R9 | `views/AppShell.tsx:187-190`; `views/NameMenu.tsx:239-241` | A Radix popover is a `role="dialog"` without a name. | low | `aria-label`. |
| R10 | `views/workspace/chat/ChatSidePanel.tsx:152-158` | The "Chats" toggle uses `aria-pressed`, and `aria-controls` names an element that exists only when open. | low | `aria-expanded`. |
| R11 | `views/longlist/LonglistView.tsx:655`, `:722`; `views/HistoryView.tsx:223`, `:279`; `views/longlist/LonglistGrid.tsx:253`; `views/workspace/chat/ChatMessages.tsx:170`; `views/workspace/chat/ContextBar.tsx:19` | Targets under 24px high (2.5.8). They pass only because of the space around them. | low | `min-h-6`. |
| R12 | `views/SourcesView.tsx:1088`, `:1105` | An invalid year is dropped with no message (3.3.1). | low | `aria-invalid` and an error line. |

## Part 3: guard against regressions

| Step | What | Note |
|---|---|---|
| G1 | Add `eslint-plugin-jsx-a11y` (recommended rules) to `frontend/eslint.config.js`. Correct each new warning, or disable it on that line with a reason. | A new development dependency. |
| G2 | Add `@axe-core/playwright` and one spec, `frontend/e2e/a11y.spec.ts`, that runs axe with the WCAG 2.0, 2.1 and 2.2 A and AA tags on the landing page and the report view. | Playwright is already in the project and runs against the mock API (`frontend/playwright.config.ts`). |
| G3 | CI: no workflow change is necessary. The `mock-journey` job in `.github/workflows/verify.yml` already runs `pnpm e2e`, which picks up the new spec. `make frontend-verify` already runs `pnpm lint`. | `AGENTS.md` lists dependencies and CI as hard gates; the task brief asks for both, which is the approval. |
| G4 | One unit test: every `cutout*` class in `src` has a `focus-visible:outline` class next to it (part 1, item 1). | No test asserts a style class on a rendered element, per `AGENTS.md`; this one reads source text. |

## Not verified from code

- What a screen reader says: the order and number of announcements during a run, and
  whether a status element that is added with its text is spoken in NVDA, JAWS and VoiceOver.
- Layout at 320px wide and at 400% zoom (S1, S4, S6 are estimates from class names), text
  spacing (1.4.12), and whether the fixed navigation covers a focused control (2.4.11).
- Windows High Contrast (forced colours): the `outline-hidden` change, and whether the
  cut-corner ring, the charts and the canvas lines stay visible.
- The fonts. Averta is not in the repository; the fallback is Manrope. The font changes how
  12px text reads but not the ratios.
- The Cognito sign-in page and the AWS WAF puzzle. Both are drawn by AWS.
- Whether report prose from the model can contain Markdown headings, numbered lists or
  tables. That decides how serious H4 is.
- Radix behaviour (focus trap, Escape, focus return) is taken from the library, not tested.
- Pointer target sizes as drawn, for example year columns on a long range.

## Order of work

One commit for each row, in this order. Rows marked **D** wait for an owner decision.

| # | Commit | Findings |
|---|---|---|
| 1 | This audit | |
| 2 | Focus rings: `outline-hidden`, field rings, white ring on the plan panel, hover styles on focus, underlined links in text, the Grey comment | part 1: 3, 7, 11; K9 |
| 3 | Landing page: landmarks, `rem` hero size, `ExternalLink` | part 1: 4, 5, 6 |
| 4 | Request-access form | part 1: 9 |
| 5 | Splash animation **D3** | part 1: 8 |
| 6 | Field borders **D2** and colour pairs **D4**, **D5** | part 1: 2; K1 to K7, K10 to K12; V1 |
| 7 | Shell: skip link, titles, focus on navigation, `aria-current` | H1, P1, F2, R4 |
| 8 | Announcements: run end, reply end, check-in card, loading states | L1 to L5 |
| 9 | Panels and hints: sheet focus return, contents focus, hints as buttons, nested buttons | C1 to C5 |
| 10 | Plan dialog, check-in focus, chat composer | F1, F3, F4, R1 |
| 11 | Tables and charts: names, scopes, map table, canvas names, keyboard move | T1 to T5, V2 to V5 |
| 12 | Scroll and reflow, after a browser test of S1 | S1 to S6 |
| 13 | Names and small items | H2 to H8, C6, C7, R2, R3, R5 to R12, V6, V7, F5 |
| 14 | Lint rule, axe spec, cut-corner test | G1 to G4 |
| 15 | `DESIGN.md` (Focus Rule, field borders, colours) and a summary with the manual test list | |

## Status after the work

The findings above describe `dev` before the work. This table says where each one stands on
`task/067-accessibility`.

### Done

| Findings | What changed |
|---|---|
| Part 1: 1 | Inset ring kept (D1); a source test guards it (G4). |
| Part 1: 2; K10 | Navy border on every field, select trigger, checkbox and radio (D2). |
| Part 1: 3; K9 | `outline-hidden` in place of `outline-none`; fields take the house ring; white ring on the plan panel. |
| Part 1: 4 | Hero sizes in `rem`. |
| Part 1: 5 | `<main>` and `<footer>` on the landing page. |
| Part 1: 6 | `ExternalLink` on 13 links (the fourteenth, in `EvidenceMarks`, already said it in its `aria-label`). |
| Part 1: 7 | One `@custom-variant` applies every `hover:` style on `:focus-visible`; links inside a sentence are underlined. |
| Part 1: 8 | The splash animation stops after 5 seconds (D3). |
| Part 1: 9 | Focus to the first error; Submit not disabled for incomplete input; the confirmation takes focus; a server error is an alert. |
| Part 1: 11 | Comment and `DESIGN.md` corrected. |
| K1, K3, K4, K6, K7; V1 | Start button, Red Deep, placeholders, verdict dashes (D4, D5). |
| H1, P1, F2, R4 | Skip link, titles, focus after a route change, `aria-current`. |
| L1 to L5 | Run end and reply end announced; check-in card not a live region; loading states have a status role. |
| C1, C5 | Focus returns when a sheet closes; a contents link moves focus. |
| F1, F4 | The plan document takes focus and closes when focus leaves it; the chat field gets focus back. |
| T1; T2 (three of five tables); V2, V3, V5 | Table names and scopes; map data table; canvas names; "(excluded)". |
| S1 | **Measured in a browser:** at 320 by 256 the content pane was 0px tall. The viewport lock now applies from 30rem of height. |
| G1 to G4 | Lint rules, axe spec (both pages: no violations), cut-corner test. No CI workflow change was necessary. |

### Open: needs an owner decision

| Finding | Why it waits |
|---|---|
| C2, C3 | `DESIGN.md` § "A value with a reason" says these reasons show "on hover only … out of the tab order; the dossier carries the same words". That is a recorded design decision, so the audit does not change it. The dossier is reachable by keyboard, which is an equivalent path. Recommendation: make the hint a focusable button, as `InfoHint` is. |
| K2 | "✓ verified" in Green on Paper 2 is 2.99:1. A colour change: `text-green-deep`. |
| K5 | Ops console: Orange on its tint is 2.50:1. A colour change. |
| K8 | Text under revision at opacity 0.55 is 3.84:1 for a short time. |
| K11 to K14 | Line and map colours under 3:1. The dashes (V1) and the map table (V2) now carry the meaning; darker colours are the full fix. |

### Open: not done in this task

| Finding | Severity | Note |
|---|---|---|
| C4 | medium | The chat's claim `<span role="button">` contains the marker buttons. The fix changes which panel a keyboard user can open, so it needs a design choice. |
| C8 (new) | medium | In the chat, an inline citation marker's accessible name is "[1]". The report's markers say "Source 1: <title>". 16 unit tests and one journey test find the marker by "[1]". |
| F3 | medium | Focus after a check-in is answered. |
| R1, R2, R3 | medium | Radio role on option buttons; the task row's name; reasons for disabled controls. |
| S2, S3, S4 | medium | Keyboard scrolling of the conversation panes; the Agent tab's footer; the plan beside the conversation at 320px. |
| V4 | medium | Moving a canvas box from the keyboard. |
| S6 (measured) | low | Task pages are 328px wide in a 320px viewport: 8px of horizontal overflow. |
| H2 to H8, C6, C7, T2 (two tables), T3 to T5, V6, V7, F5, R5 to R12, S5 | low | As listed above. |
