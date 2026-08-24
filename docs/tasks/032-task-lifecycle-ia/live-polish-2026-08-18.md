# Live polish record — 17–18 Aug 2026

Working notes for the post-build UX pass on `task/032-task-lifecycle-ia`. This is
not the contract, plan, rubric, or step-6 `verification.md`. It records what
landed in the live conversation after the contracted 032 build, so the review
stack can see *why* the uncommitted delta is large.

Dates: evening 17 Aug through evening 18 Aug (UTC+1). Nothing in this pass was
committed. The contracted 032 phases (portfolio table, routes, `nav_label`,
lifecycle IA) were already on the branch; this pass sits on top.

Prototype reference (owner): `scripts/scratchpad/frontend_v20260817/Policy Atlas_new search standalone.html`.

Screen words stay: **Task** = `project` row; **Project** = `portfolio` row.
Prompt-bearing work stayed lead-only (`planner_prompt.py` → `planner_v8`).

---

## 1. App chrome and list pages (17 Aug evening)

### Global nav
- Added **Tasks** between New and Projects.
- **New task** shortened to **New**.
- Active item is underlined; type scale and spacing pulled toward the prototype.
- User icon made bolder; Policy Atlas wordmark enlarged (still Zosia).

### New-task page
- Layout: eyebrow **NEW TASK**, heading **What do you want to work on?**, then a
  vertical list of capabilities (not a card grid).
- Four capabilities from `frontend/src/lib/capabilities.ts`: Evidence search
  (available); Scoping policy options / Theory of change / Mapping stakeholders
  (listed, greyed, not runnable).
- Removed the “Or start with an example” block.
- Title uses Averta extra-bold, not Zosia. Content column widened (later locked
  to the 1180px list-page column).
- Coming-soon rows lightened so they stay readable; “Add to a project” dropdown
  restyled to match in-app selects; Start button enlarged and moved to the
  bottom-right of the composer row, then enlarged again.
- Secondary copy (eyebrows, hints, list labels) dropped a weight so the title,
  input and Start stay the heavy elements.

### Tasks, Projects, project-detail
- Shared header chrome in `frontend/src/views/listPageChrome.ts`: same title
  size, same primary “new” button, same secondary actions.
- Projects list: **Last updated** per row, derived from the newest assigned
  task `updated_at` (fallback: portfolio `created_at`); sort newest first.
- Task list: capability chip; status / source-count columns swapped so status
  aligns in a fixed grid (`taskListRowGridClass`); project prefix
  `Project name / Task name` (grey, lighter) when a task is in a portfolio.
- Opening a project shows that project’s tasks (same list, filtered) plus New
  task. New task from a project goes to `/new?portfolio=…` (capability picker),
  not straight into Evidence search.
- Removed redundant “All tasks” / “All projects” body copy; removed a spare
  white box on the project-detail empty state.
- Task/project rows extracted to `TaskListRow.tsx` / `TaskListPanel.tsx`.

---

## 2. Search plan (18 Aug morning–afternoon)

### Panel as a document, not a chat rewrite
Saving a field used to POST a planner turn. The planner rewrote the whole plan,
dropped fields, and posted a chat message — visible as “Saving…” then the
section vanishing.

**Local overlay** (`planOverlay.ts`): edits stay in React state until Start.
Assumptions were removed from the sidebar (planner notes only; not used by the
runner). Screening rules stay; they *are* used.

### Vocabulary (settled copy)
Wire ids unchanged. Screen words:

| Axis | Title | Options |
|---|---|---|
| `search_effort` | **Search scope** | Focused / Broad / Broadest (caps 50 / 100 / 200 **per database**, from `record_cap_per_backend`) |
| `analysis_depth` | **Analysis level** | Evidence overview / Full-text synthesis / Findings synthesis |
| diagonal presets | **Thoroughness** | Rapid overview / Standard report / Detailed report (`rapid_overview` / `standard_review` / `detailed_review`) |

Chat radio `sub`s and plan (i) hovers state the acquire cap **per database**,
not “per library”. Ready-plan composer placeholder:
“Suggest changes here, or edit directly in the plan.”

Planner prompt bumped to **`planner_v8`**; `scripts/prompt_hashes.json` updated.

### Panel layout and behaviour
- Title **Search plan**; “Approved” / version stripped.
- Expected run time under the header; updates from a frontend `TIME_BANDS`
  table when scope × level change (no planner round-trip).
- **Plan steps** (was Agreed steps) derived from analysis level
  (`stepsForAnalysisDepth`); first-step blurb follows the Sources choice
  (academic / policy / both).
- Settings: Search scope, Analysis level, Check-ins. Sources moved into
  **Search filters**. Geography labelled **Source geography**, empty = “None
  selected”. Years empty state called out as none selected.
- Thoroughness control at the top of Settings: choosing a preset sets both
  axes; going off-diagonal shows **Custom**. (i) hovers (Radix tooltip, not
  native `title`) hold the long explanations.
- Dropdowns restyled to in-app popovers so option text can wrap; view and edit
  modes share the same type size so Edit does not jump the font.
- Width increased (500 → 650px, then toward the 780px reading measure).
- Centre overlay on **Review the plan** (full-pane, header stays); dock `>` to
  the side. Start search is Nesta green. Composer 3-step choice is radio-style.
- Header/X/`>` alignment and scrolling: one scrollable document; X and dock
  stay put, aligned, same size; header left-aligned to the reading column.

### PATCH, because overlay-via-planner was still lying
Owner edited Sources to OpenAlex-only; the run still hit Overton. Start was
still compiling English through the planner.

**`PATCH /api/v1/projects/{id}/plan`** (`PlanPatchIn`): typed merge of
`backend_scope`, question, dates, geography, screening, effort, depth,
check-ins; re-validate; persist a new **approved** version; **no LLM**.

**Start search** (`planStart.ts`): PATCH first if the overlay is dirty, then
`POST /runs`. Acquire honours `backend_scope` (`academic_only` → OpenAlex only;
`grey_lit_only` → Overton only). Spec: `docs/specs/system/web-api.md`. Mock API
and tests cover the merge.

Robustness check (owner-requested) confirmed: PATCH is the write; Start does
not re-ask the planner for those fields.

---

## 3. Legal, footer, sensitive-info (18 Aug afternoon)

- App footer on **every** view (including in-task): AI-mistake line plus Terms
  and Privacy links. Compact padding and caption size.
- `TermsView` / `PrivacyView`: stack text updated (no Supabase/Clerk; Bedrock,
  then OpenAI). Averta for titles and numbered headers, not Zosia. Substance
  of the legalese otherwise kept.
- Sensitive-info banner component added for the in-app warning strip.

---

## 4. Running, Plan tab, chat overlay (18 Aug late afternoon)

- Removed the old “Analysing the evidence” journey side-panel as the live
  surface. **Running card** in the planning thread (`RunningCard.tsx` +
  `runProgress.ts`): green/blue progress; finished steps expand for a short
  what-happened. If the user scrolls away, a compact status can pin.
- Plan tab: **only** the planning conversation (no chat switcher). Overlay on
  every *other* task tab: Planning tab + follow-up chats, matching the Plan
  strip the owner wanted — except Plan itself stays planning-only.
- Bottom-left bubble labelled **Open chat**: opens the **latest** follow-up
  chat, or creates one if none exist (029 rev 3.4). `+` in the strip still
  creates/reuses a blank **New chat**.

---

## 5. Results and Sources polish (18 Aug evening)

### Results / report
- Body prose 16px → 19px (`text-lead`) in annotated prose, collapsed
  summaries, live write-up, references. Captions/chips/metadata unchanged.
- Report title and section headings dropped `font-display` (Zosia); Averta.
  Nav wordmark still Zosia.
- **Download** on the paper (`ArtefactDownload.tsx`): PDF via `window.print()`
  (existing print CSS); Markdown as a client-side `.md`. Word skipped (would
  need a library). Collapsed sections expand on `beforeprint`. Print CSS hides
  nav/footer/aside/`.print-hide` and unlocks app-shell overflow. Heading toggle
  buttons are no longer `display:none` in print (that used to drop H2s).
- Markdown first dumped raw `block.prose` and a `## References` list. Citation
  numbers live on claims, not in the string, so the file had no `[n]` markers.
  `proseWithCitationMarkers` now inserts `[n]` after citation spans (Python
  code-point offsets, same rule as `spanSegments`) and still appends the
  numbered list.
- Snapshot table: dropped screened-out; kept Last updated; **Years covered**;
  one row of cells.
- Citation sheet: removed “Tags remain grouped by who asserted them.”
- Report body: dropped extra underlines.
- Contents click expands the target section; scroll-margin / outline
  coordinates fixed so the left nav actually lands on the heading.
- Chat starters: `Tell me more about "{section title}"`.
- Findings subtab already matched other Sources tabs (no page header, no
  Zosia, 780 then later 1180 via the shared Sources card).

### Sources
- Themes: name, size, existing prose; click a theme with `theme_id` → All
  sources `?theme=`. No generated copy (rubric 25). Removed the “Key themes”
  eyebrow.
- Landscape: funnel chart tooltips added; **Key themes** box removed (Themes
  tab owns that). Signpost copy: “The landscape is ready.” / Sources equivalent
  without “to read”.
- All sources: collection summary line removed from the top (it belongs on
  that view only when wanted; owner asked it off).
- Width: first locked Themes/Findings to 780px and Landscape/All sources to
  1180px (`sourcesPageClass`). Owner then asked Themes onto white paper (the
  780 column on grey looked like a strip). That still looked wrong, so:
  **all Sources tabs share the 1180px column**, white card, tab bar **spanning
  the card** (equal `flex-1` segments, navy active). `sourcesPageClass` deleted;
  layout always uses `WIDE_PAGE_CLASS`. Plan / Results / History / Share stay
  on the 780px reading measure; when Plan and the plan document sit side by
  side, each column caps at that same measure.

### Share / History
- Share: “Sharing features coming soon” (`text-lead`, 19px).
- History: no page title/lede; no Zosia.

### Width token
`READING_COLUMN_MAX_W` = 780px (report paper). `PAGE_COLUMN_MAX_W` = 1180px
(list pages + Sources). Footer stays full viewport width.

---

## 6. New-chat tab bug (18 Aug, end of day)

Symptom: bottom-left Open chat could open the panel with **no New chat tab**,
while the composer still accepted questions; send then failed.

Cause: creating a conversation wrote the id to the URL and sessionStorage, but
the tab strip only renders ids that also exist in the conversations **list
query**. Invalidate-refetch had not landed yet, so the tab was filtered out.
The composer still POSTed turns (or posted against a conversation the UI did
not show).

Fix (overlapping on purpose — see review below):
1. `create()` **seeds** the list cache and the conversation detail cache before
   invalidate (`seedCreatedConversation`).
2. ConversationTabs **folds the active chat id into tabIds during render** if
   the URL names a follow-up that is not in the local strip yet.
3. If that id is still missing from the list, show a placeholder **New chat**
   tab.
4. ChatPane fences the composer (and hides starters) when `useConversation`
   errors: “This chat couldn't be opened.”

Launcher behaviour unchanged: latest follow-up if any exist, else create.

---

## 7. Files that are new in this pass (untracked at time of writing)

- `frontend/src/lib/capabilities.ts` (+ test)
- `frontend/src/views/AppFooter.tsx`
- `frontend/src/views/ArtefactDownload.tsx` (+ test)
- `frontend/src/views/SensitiveInfoBanner.tsx` (+ test)
- `frontend/src/views/TaskListPanel.tsx`, `TaskListRow.tsx`
- `frontend/src/views/legal/*`
- `frontend/src/views/listPageChrome.ts` (+ test)
- `frontend/src/views/workspace/RunningCard.tsx` (+ test)
- `frontend/src/views/workspace/planOverlay.ts` (+ test)
- `frontend/src/views/workspace/planStart.ts`
- `frontend/src/views/workspace/runProgress.ts`

Backend of note: `PATCH /plan` on `planning.py`, acquire honouring
`backend_scope`, `planner_v8`.

---

## 8. Review — accuracy

These are defects or mismatches to re-check before the PR, not work to silently
undo.

1. **Sources tabs were right-aligned, then full-width.** Both were owner
   requests on the same day. The later one (span the card, 1180px, white) is
   current. Tests that used to assert `justify-end` now assert `flex-1`. Fine,
   as long as the PR description does not still say “right-aligned subnav”.
2. **Themes on 780px then 1180px.** Same story. Findings rides the Sources card,
   so it is wide too. History/Share/Plan/Results stay 780. That split is
   intentional after the last width steer.
3. **Markdown references.** The numbered list was already in `artefactMarkdown`;
   what was missing was in-text `[n]`. PDF/print still uses the on-screen
   markers. Worth a live download of a real artefact before calling it done.
4. **PATCH vs overlay.** Start now PATCHes then runs. Geography *is* compiled
   on the server (`_geography_constraints`): known groups, ISO tokens, or a
   comma list; unknown tokens 422 rather than persist. Empty string clears
   geo filters. The OpenAlex-only class of bug was `backend_scope` not reaching
   acquire — that path is now PATCH + acquire honouring the field. Remaining
   accuracy risk is UI: the overlay stores a display string, so a chip that
   does not round-trip through `_geography_constraints` will fail at Start,
   not silently search the world.
5. **Open chat vs New chat.** The bubble opens *latest*; `+` creates. The
   18 Aug bug was the create path with no tab. Do not describe the bubble as
   “new chat” in the PR.
6. **Planner `v8`.** Prompt-hash pin must stay in lockstep (`prompt_hashes.json`
   + harness tests). Already a hard gate.
7. **Print CSS / `beforeprint`.** Heading toggles must remain visible in print
   or H2s disappear again. Covered by an ArtefactOutline test; keep it.
8. **Capabilities list** is product surface: three greyed rows are deliberate
   (shape of the product), not dead UI. Do not “clean up” by hiding them.

---

## 9. Review — overengineering and simpler options

Nothing below is a request to delete behaviour. These are ways the same
behaviour could sit in fewer moving parts, if a later pass wants less surface.

### Already simplified in this pass
- `sourcesPageClass(pathname)` existed for two widths, then every Sources tab
  went wide. The function was deleted; `SourcesLayout` just uses
  `WIDE_PAGE_CLASS`. Good.

### Chat create (highest pile-up)
Four mechanisms now cover one race: cache seed, tabIds derive-during-render,
placeholder tab, composer error fence.

**Simpler option (keep all behaviour):** keep **seed + composer fence**. Drop
the placeholder tab and the render-time `addOpenChatTab` once seed is trusted.
The fence is the honesty path (404). The seed is the happy path (tab appears).
The other two are insurance for “URL set, list still empty”.

`addOpenChatTab` during render also writes `sessionStorage` as a side effect of
paint — legal in this codebase’s derive-during-render pattern, but noisier than
seeding.

### Markdown citation markers
`proseWithCitationMarkers` reimplements the overlap/invalid-span walk that
`spanSegments` already owns in `ArtefactView.tsx`. Importing `spanSegments`
would cycle (ArtefactView → artefactPresentation).

**Simpler option:** move `spanSegments` into `artefactPresentation.ts` (or a
tiny `proseSpans.ts`) and have both the view and the markdown exporter call it.
Same offsets, one implementation.

### Plan time bands and steps
`TIME_BANDS` and `stepsForAnalysisDepth` duplicate backend
`TIME_BANDS` / stage lists so the panel can update without a round-trip.

**Simpler option (later):** PATCH response already returns the persisted plan;
if PATCH recomputes `time_band` and `steps`, the panel could read those after
save instead of previewing from a second table. Overlay preview-before-save
would still need *some* client table, or a dry-run endpoint — so this is only
simpler if live preview is dropped.

### Overlay object
`PlanOverlay` plus `overlayToPlanPatch` is already the PATCH shape. There is
no leftover English-to-planner start-message builder in the tree (checked
2026-08-18). Keep the overlay: it is what lets the panel edit without a
round-trip until Start.

### List-page chrome
`listPageChrome.ts` is a grab-bag (widths, title class, portfolio sort, new-task
href). Not wrong. A later split (widths vs portfolio helpers) would be
cosmetic.

### Running card vs JourneyPane
Journey still exists for coverage/funnel on other surfaces. Running card is the
Plan-tab live surface. Keep both; just do not wire the old analysing pane back
as the primary run UI.

### Download
PDF = print. Markdown = client flatten. No extra libraries. That is already
the small version. Word stays out.

---

## 10. What this pass is not

- Not a new contract. Portfolio table, public routes, and `nav_label` were
  gated and built earlier; this pass did not reopen those gates except for
  **PATCH /plan** (new public write — flag for `/security-review` and the
  additive-API rule).
- Not step-6 verification. Commands run during polish were targeted vitest
  files, not a fresh `make verify`.
- Adversarial review remains waived (owner, 2026-08-17). This note does not
  change that.

When this goes to PR: say the live-polish delta is uncommitted UX on top of
032, call out PATCH /plan as the extra public interface, and say Word download
was skipped on purpose.
