# Verification: 067-accessibility

Evidence for the accessibility work on branch `task/067-accessibility`. The findings and
their ids are in [audit.md](audit.md).

## Commands run

All from `frontend/`, on the last commit of the branch.

| Command | Result | Notes |
|---|---:|---|
| `pnpm typecheck` | pass | |
| `pnpm lint` | pass | 0 errors. 1 warning that was there before the work (`SplashField.tsx`, `react-hooks/exhaustive-deps`). Includes the new `jsx-a11y` rules. |
| `pnpm test` | pass | 149 files, 2041 tests (2025 before the work). |
| `pnpm build` | pass | |
| `pnpm e2e` | pass | 39 tests, mock mode. Includes the 3 new tests in `e2e/a11y.spec.ts`. |

`make verify` (backend, infrastructure and evals) was not run: the work changes only
`frontend/`, `DESIGN.md` and this folder.

## Checks beyond the build

- **axe-core** (`e2e/a11y.spec.ts`): the WCAG 2.0, 2.1 and 2.2 A and AA rules on the landing
  page (with the form's errors open) and on a complete report. No violations on either page.
- **Reflow, measured in Chromium:** at 320 by 256 CSS pixels a task page's content pane was
  0px tall before the change. After it the document scrolls (1799px of content) and the
  composer can be scrolled into view. At 320 by 568 and 1280 by 800 the layout is unchanged.
- **Hover on focus:** the built CSS was read to confirm that `hover:` and `group-hover:`
  utilities each compile to a `:hover` rule (inside `@media (hover: hover)`) and a
  `:focus-visible` rule.
- **Contrast:** every ratio in the audit comes from a script that applies the WCAG formula
  to the hex values in `index.css`.

Automated tools find a minority of accessibility problems. The manual list below is the
other part of the evidence, and it is not done yet.

## What changed, by WCAG criterion

| Criterion | Change |
|---|---|
| 1.1.1 Non-text Content | The publisher map has a visually hidden table of countries and counts. |
| 1.3.1 Info and Relationships | `<main>` and `<footer>` on the landing page. Names and column scopes on tables. Canvas boxes and connections have names. |
| 1.4.1 Use of Color | Each verdict line has its own dash. Links inside a sentence are underlined. An excluded option says "(excluded)". |
| 1.4.3 Contrast (Minimum) | Start button 3.12:1 to 5.21:1. Red Deep for small red text (3.90:1 to 5.83:1). Placeholders 3.09:1 to 5.99:1. |
| 1.4.4 Resize Text | The landing headline's size is in `rem`. |
| 1.4.10 Reflow | A task page scrolls in a short viewport; it showed no content at 400% zoom. |
| 1.4.11 Non-text Contrast | Field, select, checkbox and radio borders 1.27 to 2.38:1 to 14.62:1. Focus ring on the navy plan panel 1.70:1 to 14.62:1. |
| 2.1.1 Keyboard | The page pane takes focus after navigation, so it scrolls from the keyboard at once. Menus are focusable containers. |
| 2.2.2 Pause, Stop, Hide | The landing animation stops after 5 seconds. |
| 2.4.1 Bypass Blocks | "Skip to main content" in both shells. |
| 2.4.2 Page Titled | Titles for the longlist, the shortlist and the theory of change. |
| 2.4.3 Focus Order | Focus returns to the citation when its panel closes. A contents link moves focus to its section. The plan document takes focus when it opens. Focus moves to the page after a route change. The request form moves focus to the first error and to the confirmation. The chat field gets focus back after a reply. |
| 2.4.7 Focus Visible | No `outline-none` on a control; fields take the 2px house ring; rings survive Windows High Contrast. Hover styles apply on keyboard focus. A test guards the cut-corner ring. |
| 2.4.11 Focus Not Obscured | The plan document closes when focus leaves it, so focus is never on a control it covers. |
| 3.3.1 Error Identification | The request form reports an over-limit field or an unsolved puzzle on submit; Submit is no longer disabled to signal them. |
| 4.1.2 Name, Role, Value | Canvas names. The current section in the nav has `aria-current`. |
| 4.1.3 Status Messages | A run's end and a reply's end are announced. The check-in card is no longer one large live region. Loading states have a status role. A server error on the request form is an alert. |

## Not verified

- What a screen reader says, in any of NVDA, JAWS or VoiceOver. Every announcement in this
  work is checked only by its markup.
- Windows High Contrast (forced colours). The `outline-hidden` change follows the Tailwind
  v4 documentation; it was not seen on Windows.
- Zoom at 200% and 400% on pages other than the Agent tab, and text spacing (1.4.12).
- The landing headline at 200% zoom. It grows about 1.6 times in a 1440px window, by
  calculation; see audit part 1, item 4.
- The Cognito sign-in page and the AWS WAF puzzle. AWS draws both.
- The look of the changes with the licensed fonts (Averta, Zosia). The repository has only
  the fallback fonts.
- The visual result of the owner decisions (Navy borders, the darker Start button, the new
  dashes). They were built from the decision, and no person has looked at them yet.

## Manual test list

About one hour. Use the staging site or `make dev`.

**Keyboard only (no mouse)**

1. Landing page: press Tab once. Is "Request access" ringed in Navy inside the white button?
   Tab to "Sign in": is the ring Aqua? Tab through the form: does each field show a 2px blue
   ring?
2. Submit the empty form with Enter. Does focus move to the Email field?
3. Any signed-in page: press Tab once. Does "Skip to main content" appear at the top left?
   Press Enter, then Tab: is focus in the page content?
4. Click a task, then press the Down arrow. Does the page scroll without a click first?
5. Report: Tab to a citation marker `[1]`, press Enter, then Escape. Is focus back on the
   same marker?
6. Report: press Enter on a contents link, then Tab. Is focus inside that section?
7. Agent tab: open "See plan". Is focus in the navy panel, with white rings? Tab past its
   last control: does the panel close?
8. A primary (blue) button and the Start button: is a white ring visible inside the cut
   corner?

**Screen reader (NVDA with Firefox or Chrome; VoiceOver with Safari)**

9. Landing page: list the landmarks. Are there a banner, a main and a content info region?
10. External link ("About Nesta"): does it say "opens in new tab"?
11. Start a run and stay on the Sources tab. Is each step announced once? Is "Report ready"
    announced at the end?
12. Send a message to the Task Agent. Is "The Task Agent replied" announced once, and the
    reply itself not read word by word?
13. Report: is a citation announced as "Source 1: <title>, button"?
14. Landscape tab, Map view: can you read the table of countries and counts?
15. Submit the request form with errors: is the error read with its field?

**Zoom**

16. 200% (Ctrl +): landing page, task list, report. Is anything cut off, or does the page
    scroll sideways?
17. 400% in a 1280px-wide window: open a task. Can you scroll to the conversation and the
    message field? Is there sideways scrolling? (The audit measured 8px; finding S6.)

**Windows High Contrast (Settings, Accessibility, Contrast themes)**

18. Tab through the landing page and a report. Does every control show a focus ring,
    including the cut-corner buttons and the form fields?
19. Theory of change: can you tell the six kinds of verdict line apart by their dashes?

**Reduced motion (the operating system setting)**

20. Landing page: do the shapes hold still from the start? Without the setting, do they
    stop after about 5 seconds?

**Look**

21. The owner decisions: Navy field borders, the darker green Start button, Red Deep on red
    chips, and the two new dash patterns. Are they acceptable?
