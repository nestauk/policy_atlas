# Verification: 058-perceived-latency

Evidence for one slice. Filled during the build (task-cycle-build, steps 5 and 6); the
review stack adds **Review findings** and **Rubric status** at step 7. Public-safe: no
secrets, no raw source text, no unredacted traces.

> Status: **Review stack run and adjudicated (2026-11-09, conversation C): five lanes plus the lead's trace lane, 50 findings adjudicated, 36 fixed in this phase, the rest declined with a reason, deferred as seams or passed to the owner (§ Review findings). Durable records written (ADR 0044 amended, deferred.md, knowledge, failure log, readiness and environment). Open for the owner at step 9: the contract's G3 and G4 gates (the archive column; the three map packages), the Codex lane's substitution, and the proposals in the local `spec-changes-proposed.md`.** The build: Phases 0 to 9 (2026-11-05), the polish cycle as rounds 1 to 15 plus consolidation batches A and B (2026-11-05 to 09), Phase 11's measures skipped by the owner (§ N25 measures). Every need N1 to N24 and N26 is implemented and tested; `make verify` and the mock journeys are green at the reviewed head (the last rows of the gate table).

## Commands run

| Gate | Command | Result | Notes |
|---|---:|---|---|
| Build-open baseline (2026-11-05) | `make verify` | pass | backend 4126 passed, 1 skipped (8 min 44 s); frontend 943 tests, 88 files; `drift-check: OK`; exit 0. Log kept in the session scratchpad. |

| Phase 0 and Phases 1 to 4 (2026-11-05) | `make okf-validate && make -C backend verify && make eval-check && make -C infra test && make audit-paths && make prompt-guard && make font-guard`, then `make openapi-sync && make drift-check` | pass | backend 4256 passed, 1 skipped (7 min 9 s); mypy clean on 464 files; ruff clean; prompt-guard 41 files unchanged after the re-pin; infra 113 passed; `drift-check: OK`. **Deviation from the gate map:** the four backend phases were built in parallel (the Codex spend cap forced a re-route mid-phase), so one combined full backend gate closed them instead of four. The frontend lane of `make verify` is red between these commits and the Phase 6 commit: the regenerated types replaced the tick fields and added `PlanStep.row`, and the client is rewired in Phases 5 to 8 (replace, do not layer). The first fully green `make verify` is the Phase 9 gate. |

| Phase 5, mock (2026-11-05, `1ae4425f`) | `pnpm vitest run src/mock`, `pnpm exec eslint src/mock`, `tsc -b` (no errors under `src/mock`) | pass | 43 tests; the backend tree is unchanged since the Phase 1 to 4 gate, so the fast gate's backend lanes were not re-run. |
| Lead additions after brief O (2026-11-05) | `pytest tests/api/test_sse.py tests/api/test_contract_models.py`, `make openapi-sync`, `make drift-check`, `pnpm vitest run src/store src/mock src/views/workspace/runProgress src/views/workspace/RunningCard src/views/taskLive` | pass | `stage.completed.counts` on the server and the client; the mock emits `plan.updated` at run start so the card has rows to come; the breathing dot's trough raised to 0.5. |
| Phase 6, store (2026-11-05, `c72006c5`) | `pnpm vitest run src/store src/api`, `pnpm exec eslint src/store src/api`, `tsc -b` (no errors under `src/store`, `src/api`) | pass | 106 tests; remaining `tsc` errors are in `src/views`, the Phase 6 surfaces. |

| Phases 6 to 8, surfaces (2026-11-05) | `make verify-fast` (backend test-fast, typecheck, lint, eval-check); `pnpm typecheck && pnpm exec eslint src e2e/<the four specs> && pnpm test && pnpm build`; `make drift-check` | pass | backend 4219 passed, 1 skipped (after two option-profile tests learned to skip verb lines); frontend 1064 tests in 93 files, build OK, `drift-check: OK`. The lint lane was run on `src` and the four committed specs because the Phase 9 agent's scratch `e2e/probe.spec.ts` was in the tree at that moment (deleted before Phase 9's gate). |

| Phase 9, journeys (2026-11-05) | `make verify && cd frontend && pnpm e2e` | pass | **First fully green `make verify` on the branch:** backend 4257 passed, 1 skipped (7 min 59 s); mypy clean; ruff clean; prompt-guard 41 unchanged; infra 113; `drift-check: OK`; frontend 1064 tests in 93 files, build OK; Playwright 33 passed (1.1 min). |

| Phase 10, round 1 (2026-11-05, `09fd7cfd`) | `make frontend-verify && make drift-check` | pass | typecheck clean, eslint 0 errors, 1064 tests, build OK, `drift-check: OK`; the backend tree is unchanged since the Phase 9 full gate. |

| Step-6 exit gate, deterministic build (2026-11-05, `ce383f24`) | `make verify` | pass | backend 4257 passed, 1 skipped (8.1 min); mypy, ruff, prompt-guard, OKF, audit, font-guard, infra all green; `drift-check: OK`; frontend 1064 tests in 93 files, build OK. The owner-gated items (the N25 measures, the owner polish rounds) re-run this gate when they land. |

| Phase 10, owner round 1 of 3 (2026-11-05) | `make verify-fast && make frontend-verify && make drift-check && pnpm e2e` | pass | backend 4220 passed, 1 skipped (test-fast, typecheck, lint); frontend 1065 tests in 93 files, build OK, `drift-check: OK`; Playwright 31 passed after three journeys moved from the nav Plan control to the card's "See plan" and one stopped matching the run status bar's time on the same text line. Live check on the owner's real completed task through a spare API and frontend pair (ports 8010/5190): the Agent and History tabs load, no Start button under the completed search, "See plan" on the card, "See the plan" on the Result tab, no "Esc closes", "Classifying"; screenshots under `research/screenshots/phase10-owner-r2/`. |

| Phase 10, owner round 2 of 3 (2026-11-05) | `make frontend-verify && make drift-check && pnpm e2e` | pass | typecheck clean, eslint 0 errors, 1070 tests in 93 files, build OK, `drift-check: OK`; Playwright 31 passed after the planning journey learned that a card with a later turn settles; the backend tree is unchanged since the round-1 gate. |

| Phase 10, owner round 3 of 3 (2026-11-05) | `make frontend-verify && make drift-check && pnpm e2e` | pass | typecheck clean, eslint 0 errors, 1070 tests in 93 files, build OK, `drift-check: OK`; Playwright 33 passed; the backend tree is unchanged since the round-1 gate. |
| Owner notes after round 3 (2026-11-05): copy, bands, settled card, fold mark, chip grouping | `make frontend-verify && make drift-check && pnpm e2e` | pass | 1072 tests in 93 files, build OK, `drift-check: OK`; Playwright 33 passed. Backend: `tests/runtime/test_task_agent.py` and `make prompt-guard` green on each prompt re-pin. |
| Owner questions on a live run (2026-11-05): no Result footer, automatic swap | `make frontend-verify && make drift-check && pnpm e2e` | pass | 1071 tests in 93 files, build OK, `drift-check: OK`; Playwright 33 passed (scene 6 now ends on the committed report's title). |
| Owner notes (2026-11-05): no event-log echoes in the thread, settled scope lines | `make frontend-verify && make drift-check && pnpm e2e` | pass | 1069 tests in 93 files, build OK, `drift-check: OK`; Playwright 33 passed. |
| The run trace (owner go, 2026-11-05): replaces the card, the minimised card, the dock, the run status bar and the sidebar's run view; the 6 px square status mark | `make frontend-verify && make drift-check && pnpm e2e` | pass | 1098 tests in 92 files, build OK, `drift-check: OK`; Playwright 33 passed; built by a frontend-designer agent from the annex § The run trace; screenshots (two rounds, desktop and phone) under `research/screenshots/trace/`; `fe-api-smoke.spec.ts` updated but not run (needs the real API). |
| Owner round 5 (2026-11-05, evening), items 1 to 9: settle on choice, no tick, rule on the right, smaller sidebar text, one way to change the scope, the fold mark as the live mark (nav still), the mark in the writing action line, the Sources default per completed step, the trace at the chat's size | `make frontend-verify && make drift-check && pnpm e2e` | pass | 1123 tests in 92 files, build OK, `drift-check: OK`; Playwright 33 passed; frontend-designer agent, lead rulings on its proposals in the annex; screenshots under `research/screenshots/round5/`. |
| Owner round 5, item 10 (the display index) | `make verify-fast` | pass | backend 4234 passed, 1 skipped; mypy and ruff clean. |
| The streaming fix (owner go, 2026-11-05) | `make verify-fast` + `make prompt-guard` | pass | backend 4233 passed, 1 skipped (7 min 12 s); mypy "no issues found in 464 source files"; ruff clean; prompt guard green on the v12 pin. Focused first: 227 tests across the prompt-pin, prompts, shape, backend, loop and call-site files. |
| Owner round 6 + evidence shown live (2026-11-05, `b69bf869` and the next commit) | `make frontend-verify && make drift-check && pnpm e2e` on the combined tree (frontend-designer, second pass); `make -C backend verify` on the evidence-live tree (deep-reasoner, own test database); lead: `make prompt-guard && make drift-check && make audit-paths` | pass | frontend 93 files / 1,142 passed, build; Playwright 33 passed; backend 4,302 passed, 1 skipped, mypy 465 files, ruff clean; prompt-guard 41 unchanged; drift-check OK; audit-paths 215. The first frontend run of round 6 had one 5 s timeout in an untouched error-boundary test (passed alone and on the rerun); the evidence-live agent's `pnpm e2e` failed only journey scene 1, the trace header the concurrent polish pass was rewriting, green once both landed. `fe-api-smoke.spec.ts` updated, not run (needs the real API). |
| Owner round 7 (live-run notes, 2026-11-05): citations on completion, case studies streamed, markers in the final style, live page = report page with an in-place swap, paced streaming with a per-batch fade, the trace as the card again, the run status bar back and the step note withdrawn | lead: `make verify` on the combined tree; agents: the same lanes on their own trees, `pnpm e2e` on the combined tree | pass | backend 4,322 passed, 1 skipped (9 min 7 s), mypy 467 files, ruff; okf-validate 200; infra 113; prompt-guard 41 unchanged; drift-check OK; frontend 94 files / 1,174 passed, build; Playwright 33 passed (designer's final run; one earlier full run had three journeys time out under parallel load, all green alone and after). The mock streaming measure before/after (research note § 6 method): 10 → 32 visible updates, longest gap 2,101 → 1,517 ms, median 21 → 7 characters per update, layout-shift total 0.135 → 0.140, no long animation frames. |
| Owner round 8 (live-run notes, 2026-11-05, evening; three agents: backend + store, Result tab, workspace + shell) | lead: `make verify && pnpm e2e` on the combined tree; the agents: the same lanes on their own trees | pass | backend 4,344 passed, 1 skipped (6 min 48 s), mypy 468 files, ruff; okf-validate 200; infra 113; prompt-guard 41 unchanged; drift-check OK; frontend 94 files / 1,233 passed, build; Playwright 33 passed. Items: citation ids and quotes on completion (live tooltips and sheets), key findings and the introduction streamed, source notes published and named, searching and screening two rows again; the trace one card from start to end with right-aligned counts, times and links, links while a step runs, the activity line breathing; "Change" on its own line and the decision card settling in place; the run status bar inset after the rail, a button that opens the Task Agent, hidden while the sidebar shows it; the rail static with no timer; the task list's running mark at 6 px; the Sources tab mark removed; staggered repairs with eased height; the chips breathing in turn during the check; pulsing placeholders in empty cells keyed to the live stage with a 5 s refetch; the tooltip no longer closes on scroll the page caused. Unverified live: the key-findings and intro streams on Bedrock (fallback counted in `stream_fallbacks`). |
| Owner round 9 (live-run notes, 2026-11-05/06; four builders: backend + store, the page, the lists and project page, the Landscape subtab; three read-only reviews: animation sweep, lists, Landscape) | lead: `make verify && pnpm e2e` on the combined tree | pass | backend 4,358 passed, 1 skipped (7 min 45 s), mypy 468 files, ruff; okf-validate 200; infra 113; prompt-guard 41 unchanged; drift-check OK; frontend 97 files / 1,346 passed, build; Playwright 34 passed. Items: search queries published live (`search.query`), "Writing search queries" and "keeping N of M candidates" lines, no "new"/"so far"; themes published at discovery (`characterise.themes`); "Writing · Introduction"; the full-text stage is "Collecting the full texts" (owner: no model reads it; chip "Full text", funnel "Full text"); the queries block at the top of All sources, live then folded; the run status bar (renamed from the strip, code included) inset, a button plus the running step's link; the chip wave in blue; themes listed while assigning; the thread makes room for arriving blocks and only new blocks rise (the sweep's ten entries); the nav's growing rule; the lists share one page header with fixed slots (layout shift on the phone walk 0.109 → 0.042) and open on Organisation when Mine is empty; the Landscape charts are accessible ranked-bar tables in Navy, the funnel without its Findings row. Unverified live: the case-studies, key-findings and intro strict-schema streams on Bedrock. |
| Consistency pass (owner, 2026-11-06; one builder on the clean tree from `research/consistency-sweep.md`, plus seven owner additions) | lead: `make verify && pnpm e2e` | pass | backend unchanged; frontend 98 files / 1,363 passed, build; Playwright 34 passed; drift-check OK. Recount: off-scale text sizes 7 → 1 (the approved chip), hand-written tracking 23 → 0, `font-medium` 12 → 0, grey shadows 4 → 0, `START_SEARCH_CLASS` 6 → 0, `animate-pulse` 0. One `:focus-visible` rule and an inset ring on the cut-corner primaries (they showed no ring: the cut clipped it); `buttonVariants` exported; an outline variant; Retry as a `Button` everywhere; one `CloseButton`; one icon module; splash on the scale; dark-panel tokens; the radio recorded as the one radius exception; the nav rule grows left-to-centre on hover and full when active (Sources subtabs the same); "Find a project"; header controls at Body; the Find popover (recent items, no empty 'no match', keyboard); the account menu arriving from its button; the New page's eyebrow removed; greyed subtabs; Landscape rows link to the filtered Sources view with one hover and one count line; Sources table headers on one line. |
| Consolidation batch B (seven rules the owner accepted 2026-11-06; one frontend builder, 2026-11-09) | lead: `make frontend-verify && make drift-check && pnpm e2e` on the quiet tree after the builder's report | pass | frontend 120 files / 1,808 passed, build; drift-check OK; Playwright 36 passed. Items: one home each for dates (`lib/dates.ts`), counts (`lib/format.ts`), a task's status words and mark (`ui/brand/taskStatus.ts`), the filter chip (`FilterChip`), the list furniture (`ui/brand/list/`), the rotating chevron (`DisclosureChevron`) and the address link (`ReferenceUrl`); the view-level copies deleted (53 files, 555 added, 703 removed). Tests moved with their rules (`landingPresentation.test.ts` deleted, its cases in `taskStatus.test.ts`; the date and count cases in `lib/*.test.ts`); word changes in the trace, status bar, list row and one e2e assert ("Paused · waiting on you", "Running", "Stopped"); the re-run notice now carries the year. Owner accepted the three copy points on 2026-11-09 (the paused words supersede the trace's earlier ones; aborted and interrupted both read "Stopped" with grey and red marks kept; the re-run notice carries the year). Annex row 9i and § Consolidation, batch B. |
| Round 16, the action line's real cause (owner, 2026-11-09; frontend-designer pass with a per-frame probe on the mock app) | lead: `make frontend-verify`, `pnpm e2e` on the combined tree | pass | frontend 121 files / 1,821 passed, typecheck, build (one pre-existing lint warning in `SplashField.tsx`); Playwright 36 passed. The first fix's retarget replaced by the margin ease in `useEasedHeight`; the probe's before and after frames under `research/screenshots/round16/`. The same hook drives the report's repairs, the check-in card and the run trace: their tests pass, their motion was not re-watched frame by frame. |
| Round 16 (owner notes after the review stack, 2026-11-09; lead, in the review conversation) | lead: `make frontend-verify`, `pnpm e2e` | pass | frontend 121 files / 1,820 passed, typecheck, build; Playwright 36 passed. Items: the plan document leaves the way it came (200 ms back to its edge or sinking, fading, the scrim over a tab with it; `closing` in the shared plan-panel state); the thread's grow-only height box retargets to where a nested easing box settles instead of finishing short and re-clipping the action line under a streaming reply; the dossier's "Full text" links to the document as the table's does (the link in `DepthMark`, the `text-link` utility). Not eye-checked live: the exit motion itself (jsdom cannot play it; the unit test covers the closing state and the timer). |
| Round 15 (owner live-run notes, 2026-11-09; the scoping, workspace and backend builders) | lead: `make frontend-verify && make drift-check`, backend ruff + mypy, the touched backend suites, `pnpm e2e` | pass | frontend 116 files / 1,790 passed, build; drift-check OK; ruff and mypy clean (478 files); shortlist routes + model routes 73 passed; Playwright 36 passed. Items: the option card's exclusion block at the top as labelled facts ('Does not meet a constraint' / 'Excluded by you', Constraint, Why); rows carry one short exclusion phrase and none inside an excluded group; 'Does not meet:' replaces 'Breaks:' in the notices; the card's breadcrumb names Shortlist or Longlist as the origin; the shortlist note step on the standard tier at low effort; the thread places a run-less History event nowhere (an allow-list of walk-written kinds); a note refresh proven to open no run, send no frame and no tick. Not reproduced: the owner's extra progress card on a note refresh (the dev database shows none; needs the task, the view and a screenshot). |
| Round 14 (owner live-run notes, 2026-11-07 to 09; backend, report, workspace, Sources, lists and scoping builders; lead prompts) | lead: `make verify && pnpm e2e` on the combined tree | pass | backend 4,404 passed, 1 skipped (10 min 49 s), mypy 478 files, ruff; infra 113; prompt-guard 43 unchanged (three lead prompts this round: task_title_v1, chat_title_v1, shortlist_note_v1, and shortlist_v2 writing no note); drift-check OK; frontend 116 files / 1,781 passed, build; Playwright 36 passed (the backend and frontend steps ran on the same tree at different moments while the last two builders finished; the final frontend step and the journeys ran on the quiet tree). Items: task names from the refined question at the step 1 decision and chat titles from the first message, revealed like streamed text; the shortlist's not-covered note with one writer, refreshed once on opening or after a pause, with the turning mark and 'Reviewing the shortlist for gaps' while it rewrites; the References numbers blue and opening the source, the method as one section at the prose width, the report titled with the plan's question, the boxes and the sheet on one marks line; tabs opening at the top, the plan's scrim and top, the Task Agent's measured jumps fixed with one growing block per turn, the status bar gated on loaded data, chats on the paced reveal with the working line and References in the report's form, the header naming the project, the sidebar trace's links right-aligned, the Result tab active on option cards; Collecting… from the row's queued status, the whole queries line as the trigger with column headings, Not reported linking, scoping theme headings filtering the table with distinct counts; the task list's timer kept, the New page's searchable multi-select limited to the chosen project (disabled until one is chosen), the foot reorganised, the archive sentence naming the solo tasks, one ProjectPicker; projects archiving their solo tasks, depth and theme filters, the mock's ingest stage, the summaries pass publishing its progress, the chat stream's conversation.titled frame; the verdict's and the links' rules recorded. Open: chat's turn citations still carry a per-citation verdict (chat API); the two unproven trace nestings (chat title, note refresh session id) for the review. |
| Round 13 (owner live-run notes, 2026-11-06 late and 2026-11-07; the scoping, Sources, report, lists, workspace and backend builders, plus consolidation batch A) | lead: `make verify && pnpm e2e` on the combined tree | pass | backend 4,386 passed, 1 skipped (5 min 26 s), mypy 470 files, ruff; infra 113; prompt-guard 41 unchanged; drift-check OK; frontend 114 files / 1,729 passed, build; Playwright 36 passed. Items: batch A (Disclosure, reference, InfoHint, remembered choices); the longlist row's plain count, the shared group heading with shortlisted counts, View as and Columns on the controls row with the count line and Show all between the rules, no contents nav, shortlisted first, Other for the lever that fits none, the circled-check shortlist toggle (only the pressed one changes), Exclude as a quiet control on the card and on an open group's description line (words then glyph in the toggles' column, one hit area), one click with Add a reason on the card only, Excluded as a section of folding groups with 'Excluded by you', uncovered levers as a grey foot under the row heads, the View Transition only on a regroup with the chrome named; the option card's documents (title then year, the References style, labelled facts, a link to the filtered table), the profile table at one size in a logical order, Your target and outcomes first; the New page's Project field always shown with the shared ProjectPicker (New project… created in place), several searches as a checklist, the shared Checkbox; one ProjectPicker and two hooks for every add-to-project and create-project path; Share's two explanation lines; Landscape's published-country note in an i, the funnel rows Appraised and Full text accessed linking (depth and appraised filters, distinct counts), Relevant in the screening filter, the scoping task's Themes subtab, the loading skeleton's bars in every column; the citation sheet (Claim with the one blue rule, Judge once from the claim with the diamond, Source/Sources · N boxes grouped by source with numbered quotes, Back from the source sheet, 'Evidence for this claim', 'Loading source details…' once); the verdict moved from the citation to the claim in the API, the live frame and the store (no compat fields); the method's rows quiet links with Full text linking; the plan document closing on an outside press; the mock's finished search and real link names; History naming the option on a reason; the page's scrollbar gutter kept. Open: chat's turn citations still carry a verdict each (the chat API's shape; a backend item). |
| Round 12 (owner live-run notes, 2026-11-06, evening; six builders plus a consolidation pass) | lead: `make verify && pnpm e2e` on the combined tree | pass | backend 4,379 passed, 1 skipped (7 min 46 s) with `test_option_searches_run_at_the_configured_width` failing once under a load average above 200 and passing alone (a timing test: peak concurrency measured with 0.2 s sleeps; flagged for the review), mypy 470 files, ruff; infra 113; prompt-guard 41 unchanged (the scoping planner prompt re-pinned twice this round, lead); drift-check OK; frontend 107 files / 1,666 passed, build; Playwright 35 passed on the quiet tree (an earlier run failed two journeys while a builder's edits reloaded the page). Items: the scoping planner's Something else option and question decision (v7); the header name at Heading; the planner's reply in its own eased box; the sidebar and Agent tab reading closed Task Agent conversations; done scoping rows linking; decision n of M; the longlist closed by default with Navy names, right-aligned counts and controls, no contents nav, shortlisted first, the theme-and-lever hover, levers counted, the dossier over the card; the option card as what it is, Evidence (places, Your target and outcomes, documents in the References form with three fact lines) and What it could take (a code-built sentence with bold takeaways, the estimate hover), only two folds, the report's scale and square bullets; the shared Select; the gate card without the key assumption; the public link reaching the longlist and shortlist read-only; the report's expand state, badges with the table's tones, the citation sheet, method rows linking; Sources tones, Full text linking, Cited under the status, the two-row filter bar, the foot line with Download CSV, the page size and 25 a page, the Search queries section, queries filtering the table; the list gap fixed by a subgrid, Projects paged and ordered by the server, row menus (three dots) with rename, archive and Add to project on rows and the task header; the evidence vocabulary defined once in `ui/brand/evidence.ts` (owner's defined-once rule) and `BulletList`; backend: the option-search count from dispatch, combined / Estimating, places split, full_text_url, query_id and record ids, projects by last activity, 20 a page, the card export, option documents' authors and venue, the mock paging. Declined: live query ids before the step commits (a rolled-back step would reuse the sequence). |
| Round 11 (owner live-run notes, 2026-11-06; six builders: backend and store, the workspace, Options scoping, the report page, Sources and Landscape, the lists) | lead: `make verify && pnpm e2e` on the combined tree | pass | backend 4,373 passed, 1 skipped (6 min 3 s), mypy 470 files, ruff; infra 113; prompt-guard 41 unchanged; drift-check OK; frontend 103 files / 1,546 passed, build; Playwright 35 passed. Items: the square's pulse deeper with a scale and the citation wave as a visible sequence; scoping rows linking to Sources and Landscape; the baseline card keeping its link and steps once the longlist starts (`RunOut.stages`); ticks and the option-search stage naming their walk; option and theme names while clustering (`characterise.themes.stage`); the shortlist count reading the shortlist after the step; the shortlist toggle saying Remove on hover; the option card in three blocks and the longlist row cut down after a UX audit (`research/longlist-ux-review.md`); most relevant sources and case studies back in cards above the Full report, the date on its own line, the sources count linking to References, the method as a ruled table, blue x-height bullets; the Sources hover affordance and strength tone, the filter bar, the finished queries line with saved citation passes (`passes`), greyed inactive subtabs, clickable funnel rows, the population line removed, a List / Map choropleth (`d3-geo`, `topojson-client`, `world-atlas`); Archived as a quiet foot link in the open scope and Find as a magnifier; the name-and-menu header for tasks and projects, projects archivable (`project.archived_at`, migration c4e8a2f6d1b3), the reconnecting line in the run status bar's frame. Open: D1; the two live Searching rows on a longlist walk are the walk's own broad search beside the option searches (display ruling pending); scoping rulings 1, 4 and 42 vs the built longlist (owner). |
| Round 10 (owner, 2026-11-06; six builders from five read-only reviews: the report page, the Sources table and Landscape years, the list rows, Share and History, Options scoping, and the backend) | lead: `make verify && pnpm e2e` on the combined tree | pass | backend 4,365 passed, 1 skipped (7 min 17 s), mypy 470 files, ruff; okf-validate 200; infra 113; prompt-guard 41 unchanged; drift-check OK; frontend 100 files / 1,480 passed, build; Playwright 35 passed. Items: the question as the report's title on both pages, the facts line, references with addresses, markers as the one control with tooltip and sorted numbers, a heading outline, ruled lists, print without chrome; visible Sources filters with Country and a year range, fixed columns, a stacked phone row, the years drag range, the subtab remembered per task; the row's accessible name carrying its status, the name cell widened, dates as "5 Nov", Show more paging and an Archived view, the switcher's growing rule; History grouped by day with sentences naming the step and the actor, runs folded behind Show steps; Share reordered with a two-step public confirm and no blue fill; the longlist as one component with rows moving into themes, one primary on the shortlist page, the gate card in the settled language, scoping trace links; the backend's history sentences, the run touching the task's date, has_more paging, the country filter, the refusal message, the gate heading and the scoping mock. Open: D1 (themes open by default; switch `THEMES_OPEN_BY_DEFAULT`). |

| Step-7 open gate, the review's self-verify (2026-11-09, `a3e583c3`) | `make verify` | pass | backend 4,407 passed, 1 skipped (9 min 31 s); mypy 478 files; ruff; okf-validate 202; infra 113; prompt-guard 43 unchanged; drift-check OK; frontend 120 files / 1,808 passed, build OK; eslint 1 pre-existing warning (`SplashField.tsx:181`, not this slice's). Settles the verifier's L4: the last build commits had been gated by `frontend-verify` only. |
| Step-7 fixes gate (2026-11-09, the reviewed tree) | `make verify`, then `make frontend-verify && make drift-check && pnpm e2e` after the OpenAPI regeneration and three journey updates | pass | backend 4,431 passed, 1 skipped (6 min 33 s); mypy 478 files; ruff; okf-validate 202; infra 113; prompt-guard 44 unchanged (`task_plan.py` newly pinned, `planner_v12`); the first `drift-check` failed on the archive route's docstring (regenerated with `make openapi-sync`); frontend 120 files / 1,815 passed, build OK, drift-check OK; Playwright 36 passed after three assertions followed the design fixes (the citation sheet highlights the quote's words without its stop; the theme item's disclosure word; the mock plan's ingest row in scene 1). |
(The gate map's step-6 exit is this command; it is re-run after the owner-gated phases.)

## Checks beyond the build

- **Deterministic tests** — per phase, listed with the gate row.
- **Manual / browser / API** — `make fe-api-smoke` (2026-11-05): 3 passed in 5.5 s against a
  real local API in stub mode (the authenticated task list; a task created through the real
  POST; a stub run started and its progress rendered from the real SSE tail with the new tick
  and frame shapes). The fixed-question captures and the live-dev screenshots are in § N25
  measures and § Polish log (owner-gated).

## End-to-end command

The live check at the contracted scope (changed surfaces plus one cheap full-chain smoke):

```
make fe-api-smoke
```

(the built frontend against a real local API in stub mode: the task list, a real task POST,
a stub run and its progress rendered from the real SSE tail with the new frames). The fixed
questions on the laptop with the capture client are the N25 measure and need the owner's go on
cost (plan Phase 0 and Phase 11); the command, once approved:

```
cd backend && uv run python -m policy_atlas.api.dev_issuer mint --dir <issuer dir> --sub <sub> --client-id policy-atlas-dev --ttl 7200
uv run --project backend python scripts/stream_capture.py --task-id <task> --token-env PA_TOKEN --out research/captures/<name>.jsonl --until-terminal
uv run --project backend python scripts/stage_walls.py --capture research/captures/<name>.jsonl --healthy true --format md
```

## N25 measures

**Skipped by owner decision (2026-11-09): "I'd rather skip the fixed question runs, I've done
enough runs with my checks."** The four fixed questions before and after (laptop) and the
staging baseline (P16) each run real model calls and were gated on the owner's go at plan
time; the owner chose not to spend them. The capture tool and the gap measure are built and
tested (Phase 0) and stay for a later measurement. What stands as live evidence instead: the
owner's own live runs on the dev app through polish rounds 6 to 15 (2026-11-05 to 09), whose
notes drove those rounds and whose fixes were each gated; one builder's live-app check on task
7f311800 (round 15). The rubric's latency-measure items are therefore **not measured**; the
review records them as an owner decision, not a gap.

## Polish log (D11)

- **Round 1, agent pass (2026-11-05):** `frontend-designer` reviewed every changed surface on
  the mock-driven app against its annex scene at 1280 and 400 (the live runs are owner-gated,
  so the mock supplied the transient states). Five layout fixes within the annex: the plan side
  panel lies over the page instead of squeezing the report; the tab group no longer collides
  with the task name; the in-progress row's clock stays on the label's line on a phone; the
  strip's elapsed time never truncates; in-card inputs drop their indent below `sm`. Gate:
  typecheck clean, eslint 0 errors, 1064 tests. Screenshots under
  `research/screenshots/phase10/` (every scene, rounds 1 and 2, the four brief O missed
  included). Lead follow-ups after the pass: "just now" under a minute, no re-run line during a
  longlist walk, the run status bar's short section form. Annex polish log row 1 filled.
- **Round 2, owner pass, round 1 of 3 (2026-11-05):** the owner's six notes on the live app
  (annex § Owner pass, round 2): two were one bug (older stored turns failed validation on the
  new `row` key; the transcript read now re-stamps stored steps with the server's copy, with a
  test); the Plan control leaves the nav, "See plan" returns to the card and a small link to the
  Result tab; "Esc closes" removed; no running card in the sidebar's pane; "Categorising" →
  "Classifying". The owner's dev API (uvicorn `--reload`) stopped answering during the edits;
  the fixes are verified in-process and by the tests, and the owner restarts `make dev` to see
  them.
- **Round 3, owner pass, round 2 of 3 (2026-11-05):** "uncompleted 'N of 3' cards in the Task
  Agent chat on completed searches": a part card with a later turn after it now collapses to
  one line naming the plan's outcome ("Thoroughness · Standard report · ~10-20 min"; the
  scope's chips; the question's text; the user's reply only where the plan names nothing) at
  the conversation's text size, and the stepper counts it as settled; only the newest unanswered
  card is open (`PartState.answered`/`answer`, `settledSummary`, tests in `PartCard.test.tsx`).
  Same round: the two stage signposts under the running card are removed (the card's row links
  point at the outputs); the Mapping row links to the Themes view. One owner round remains.
- **Round 4, owner pass, round 3 of 3 (2026-11-05):** the thoroughness options read in the
  planner's order (fastest to slowest; the primary is no longer moved first); each option shows
  its label and one sentence, the planner's reason line goes (too verbose); a settled question
  line shows the question's text and a settled scope line its chips ("That's my question" and
  "Looks right" only as fallbacks); settled lines rise in like the open card. The owner's three
  rounds at build end are used; the next two rounds belong to the review phase (D11).
- **Owner note after round 3 (2026-11-05):** the thoroughness copy cut to the plain voice (the
  planner prompt, re-pinned; the mock follows). Gate: `tests/runtime/test_task_agent.py` 43
  passed, mock tests 45 passed, the planning journey passed, `make prompt-guard` green.
- **Owner note, the preset bands (2026-11-05):** `task_plan.TIME_BANDS` presets set to ~5-10 min
  (Rapid overview), ~10-20 min (Standard report), ~20-30 min (Detailed report); the planner
  prompt reads the table, so its file and hash are unchanged (`make prompt-guard` green). The
  off-diagonal cells keep their older values and are flagged for the owner in the annex.
- `runtime/task_agent_prompt.py`, third re-pin (owner correction, 2026-11-05): the subs say
  the total documents kept (150 / 300 / 600), the report's sections (3; up to 8) and that the
  Detailed report extracts findings; the caps paragraph says the totals. Tests pin the totals.
- **Owner note, the settled card's look (2026-11-05):** between the pre-task card and the
  one-line form: a quiet block with a green left rule, the part's name and a green
  "✓ <outcome>" line; tests and the journeys follow.
- **Owner note, the agent's working mark (2026-11-05):** the "Drafting the plan" line under a
  streaming reply shows the Policy Atlas fold mark turning instead of the yellow dot (still
  after a dropped connection and under reduced motion); the run's dots are unchanged.
- **Owner note, the scope card (2026-11-05):** chips grouped under "Screening criteria" and
  "Source filters" with the planner's prefix dropped; the settled line names the groups.
- **Owner questions on a live run (2026-11-05, afternoon; annex § Owner questions):** the
  Result tab's "Checking claims and attaching citations" footer removed; a watched run's page
  swaps to the committed report by itself once the task and artefact reads have caught up
  (the "Report ready · Read the full report" footer and button removed; contract N8's last
  clause is withdrawn by the owner, to be amended in the contract at the review). Finding
  recorded for the owner's decision: the streamed section turn only runs at the turn cap
  (Langfuse: no `synthesise:section_emit` generation on the owner's run), so N6 is built but
  does not show on a normal section; fix proposed, not applied.
- **Owner notes, the same afternoon:** the run block's event-log echoes leave the Task Agent
  thread (`presentRunDecisions` and its tests deleted; the History tab is unchanged); the
  settled scope card gives each chip group its own line under a grey label (`settledSummary`
  now returns lines, one per group).
- **The streaming fix (owner go, 2026-11-05):** built by a deep-reasoner agent from the lead's
  brief (the lead wrote the prompt words and the probe first): `write_section` ready signal on
  open turns, the streamed write turn in the same loop turn with the two calls' usage added
  (`core/usage.add_token_usage`), the cache-keeping request shape (tools kept, `tool_choice`
  "none", no `response_format`), code fences stripped before the parse, the forced turn at the
  cap streams the same way, the once-only fallback kept. `call_site_kwargs_056.json` refreshed:
  the section turn and the repair now list `write_section`, the open turn's `allowed_tools`
  carries it instead of `emit_section`, the streamed row has no `response_format`. Accepted
  gap (agent proposal 1): when the streamed write and its forced fallback both fail to parse,
  the ready turn's tokens are not counted in `usage_totals` (the loop adds usage only when the
  turn returns); rare and small. Agent proposals 2 to 4 declined: `parallel_tool_calls` stays
  off the streamed request (the probe's shape B hit the cache without it); the no-stream
  route's "final turn" wording only reaches the offline test backends.
- **Owner round 5 (2026-11-05, evening), item 10, the lead:** the owner's 13:24 run streamed on
  the server (Langfuse: per section a read turn, a 14-token ready turn, a 10 s
  `synthesise:section_emit`), but the page showed nothing: the deltas and the revising spans
  carried the loop's `section_index` while the skeleton numbers sections for display (key
  findings first at 0). The seed now carries `display_index` from the progress emitter
  (`ProgressEmitter.display_index`), the key-findings seed carries 0, and
  `section_emit_stream` and `_publish_revising` address the page with it. Tests: the emitter's
  display index; deltas use `display_index` when present. Items 1 to 9 of the round are a
  frontend-designer pass (see the gates table).
- **Round 16, owner notes after the review stack (2026-11-09):** three live-app notes taken in the
  review conversation (annex § Round 16). The plan document closed with a cut while the sheets
  leave over 200 ms: the shared plan-panel state now holds `closing` for `PLAN_EXIT_MS` so the
  document (`dock-out` docked, `sink-out` centred) and the scrim over a results tab play their
  exits before it unmounts; `exitRuns` moved to `ui/motion/motion.ts` and the sheet reads it too.
  "Drafting the plan" and its mark dropped under the composer's edge when the streaming reply
  wrapped a line. The lead's first fix (a retarget of the thread's box) did not hold; a
  frontend-designer pass reproduced it on the mock app with a per-frame probe and found the
  turn's own box frozen at an animated height while the reply's box grew (annex § Round 16).
  `useEasedHeight` now eases the content's bottom margin from minus the change to nothing and
  keeps the box at its natural height; `GrowBox` opens through it; the nested-box bookkeeping is
  deleted. After the fix the probe shows 0 clipped frames in nine runs across six setups.
  The source dossier's "Full text" now links to `full_text_url` as the Sources table's does; the
  link lives in `DepthMark` (`href`) and its style in the `text-link` utility, so there is one. Tests:
  the retarget keyframes; the plan panel's closing state, its cut without Web Animations and an open
  during the exit; the dossier's link and its plain word without an address.
  Same round, later: the finished search-queries block opens the live block's table (one
  `QueriesTable`; the Database column and flat rows deleted; owner: one layout, the live one). The plan over a results tab is fixed to the viewport's full height, as the sheets are
  (it stopped at the task header).

## Evidence shown live (owner, 2026-11-05)

Built by a deep-reasoner agent from `research/briefs/evidence-live.md`. Display-only: nothing
new is persisted or judged, no prompt text changed.

- **Sources read (item 1).** After each read tool returns, `run_section_loop` publishes the
  sources its records came from (`synthesis_tools.read_sources`, via a new `on_tool_result`
  hook on `run_tool_loop`). Hub message `SectionSources(index, sources, occurred_at)`; the hub
  keeps the running set per task and section (first-seen order, each source once) and sends the
  whole set. SSE frame `artefact.section_sources` (index, sources `[{source_id, title}]`,
  occurred_at; ephemeral). Names: `source_short_name` ("Smith 2023": first author's family
  name, else the publisher, with the year; else the title, HTML-unescaped as the references do;
  else the locator; else "Untitled source"), read once per source per run by
  `make_source_labeller(conn, task_id)` and bound around the section loop with
  `source_labelling`. The `source <id>` placeholder title is never shown.
- **Citations as they close (item 2).** `core/openai_client.JsonArrayObjectDecoder("claims")`
  hands back each claim object as it closes; `synthesis_backend.StreamedClaimMarker` validates
  it as `_salvage_section` does, binds its text with `bind_spans`'s ordered-cursor rule, and
  publishes `SectionClaim(index, start, end, sources, occurred_at)` for a bound chunk or finding
  claim with known sources. SSE frame `artefact.section_claim` (ephemeral). The marker cannot
  raise into the turn (any error stops the markers, not the write); the final parse is unchanged.
- **Hub memory.** `_Draft` holds the text, `sources` and `claims` together; a snapshot sends
  the draft (only when it has text), then the sources, then each claim; a `replace` delta keeps
  the sources and drops the claims; `clear_draft`, `end_stage("synthesise")`, `end_run` and the
  sweep forget all three; both messages count in `dropped`.
- **Frontend.** `LiveSection.sources` / `claims` (store reducer; cleared on completion, claims
  also on a `replace` delta); the Result tab's Meta grey "Drawing on N sources · … · and N more"
  line under the heading (`drawingOnLine`, `liveSourceName` in `artefactPresentation.ts`) and a
  hollow 6 px Line 2 square after each cited span (`ProvisionalMark`, `role="img"`, name
  "Cited, being checked: <titles>", titles as hover text) in `ArtefactView.tsx`. The mock walk
  sends both frames; journey scene 6 asserts the line, the marks and their removal.
- **Tests.** `backend/tests/evidence_search/synthesis/test_evidence_live.py` (decoder: objects
  split at every size, escaped quotes and braces, nested `claims` key and code fence, stop after
  the array; markers: bound and cited claims published with spans, unbound / uncited /
  overlapping / malformed skipped, final parse equal to `_salvage_section`, broken JSON falls
  back as before, a failing labeller never fails the turn, no raw id; `read_sources`,
  `source_short_name`, the labeller reads once; the loop publishes sources right after a read);
  `tests/core/test_liveness.py` (7 hub tests); `tests/api/test_sse.py` (both frames live, the
  snapshot order, the encoder); `tests/api/test_contract_models.py` (both frames ephemeral);
  frontend `store/reducer.test.ts`, `views/ArtefactView.test.tsx` (5 tests),
  `mock/api.test.ts`, `e2e/journey.spec.ts` scene 6.

## Round 7 backend: citations on completion, case studies streamed

Built by a deep-reasoner agent from `research/briefs/round-7-backend.md` (owner notes from a
live run, 2026-11-05), with two lead decisions applied after the first report (case-studies
slot last with a `role` on every skeleton slot; a fixed order in the read model). No prompt
text changed; nothing new is judged.

- **Citations on completion (item A).** `artefact.section_completed` gains `citations:
  [{start, end, n, source_id, title, tier}]` (`SectionCitation`; default empty, so frames
  recorded before it still replay). One entry per citation row of the section's persisted
  claims; `[start, end)` is the claim's span in the frame's `prose` (code points, the span
  `_write_section` stores); `title` as the read model's `_title` (envelope snapshot title,
  HTML-unescaped, else locator, else "Unknown source"); `tier` the claim's verdict. Key
  findings and case studies carry theirs; the baseline Sources foot carries an empty list.
- **One fixed reference order (lead decision).** Before this round `artefact_out` numbered
  references in whatever row order Postgres returned (no `ORDER BY`), so a report could
  renumber between loads. No column carries the save order (every block, annotation and citation
  of a run shares one `created_at`; ids are random), so the order is computed, with no
  migration: `artefact_out` sorts its annotations by the block's save rank (`_save_rank`: body
  sections in roll-up order, the Sources foot with them, then key findings, then case studies),
  then the claim's span (start, end), then annotation id; and each claim's citations by chunk
  id, quote, citation id. The sort runs in Python, so no database collation enters it.
  `synthesis/live_citations.ReferenceNumbering` walks the same order as each section is saved,
  so the live numbers are the saved report's numbers. Claims inside a block are now listed by
  span (reading order) in the read model too. Reports saved before this change may show
  different numbers from before (once; then stable).
- **Case studies streamed (item B).** The skeleton has a case-studies slot when the Evidence
  search passes run, placed **last** (key findings 0, body 1..n, case studies n+1), so body
  indexes do not move. Every skeleton slot now carries `role` (`key_findings`, `body`,
  `case_studies`; `ArtefactSectionSkeleton.role`, default `body` for skeletons recorded before
  it), so the page orders live sections by role as it orders the saved report. The pass emits
  `section_started` for the slot, publishes "Writing the case studies" with section line "Case
  studies", and calls `OpenAISynthesisBackend.write_case_studies_stream` (the structured call's
  request and schema, streamed; `JsonArrayObjectDecoder("cards")`; each closed card with a title
  and text published as hub `SectionCard` → ephemeral `artefact.section_card {index, title,
  prose, occurred_at}`; the whole reply parsed as `CaseStudyWire`; on any failure an empty
  `replace` delta resets the slot, `stream_fallbacks` counts, `write_case_studies` runs once).
  The hub keeps cards beside the draft (snapshot: draft, sources, claims, then cards; a
  `replace` drops them; the usual forgetting rules; they count in `dropped`). The draft is
  cleared after the pass; `case_studies_completed` sends the block prose (each card as its bold
  title line and text) with its citations, or empty prose when no cards survive (the store then
  removes the slot). Before this round no `section_completed` was sent for case studies.
- **Deviation: case studies are now streamed.** The earlier rule, pinned by the test
  `test_progress_emitter_has_no_case_studies_stream_surface` ("Contract F6: case studies are
  post-run only and never streamed"), is superseded by the owner's note from the live run on
  2026-11-05: "the case studies section is being written but isn't streamed". The test is
  replaced by one that pins the slot, the role and the citations through replay.
- **Store and mock.** `LiveSection.role?: string` (from the skeleton),
  `LiveSection.citations?: LiveCitation[]` (set on completion when non-empty, kept),
  `LiveSection.cards?: LiveCard[]` (appended, cleared on completion and on a `replace` delta).
  The mock skeleton is key findings 0, the streamed body section 1, case studies 2, each with its
  role; the walk ends with the slot started, two cards and the completion. Completed sections
  carry citations that equal `mockArtefact`'s: key findings reference 1; the body section
  references 2, then 2 and 3; the case studies reference 2. `mockArtefact` gains a case-studies
  section (the first card cites reference 2) and references 2 and 3.
- **Tests.** `tests/evidence_search/synthesis/test_live_citations_and_cards.py` (a whole stub
  run whose completed citations equal `artefact_out`'s per section; the slot last with roles,
  the stream call, the section line and the draft clear; the non-streaming backend; absent case
  studies; the card decoder at four chunk sizes, a card without a title, the fallback; the read
  model's walk order whatever the row order); `tests/core/test_liveness.py` (5 card tests);
  `tests/api/test_sse.py` (card frames live and on reconnect, the encoder);
  `tests/api/test_contract_models.py`; `tests/runtime/test_progress.py` (slot layout and roles,
  citations through replay, an old frame without citations); `test_synthesise_baseline.py`
  (Conclusions then Case studies end the skeleton); `test_step_timeout_sites.py` lists the new
  exempt stream; frontend `store/reducer.test.ts`, `mock/api.test.ts` (citations equal the
  committed report's, section by section).

## Round 8 backend: key findings, introduction and source notes live; search and screen split

Built by a deep-reasoner agent from `research/briefs/round-8-backend.md` (owner notes from a
live run, 2026-11-05, evening). No prompt text changed; nothing new is judged or persisted
beyond the frames below.

- **B1. Citation ids on completion.** Each `artefact.section_completed.citations` entry gains
  `citation_id`, `claim_id` and `quote` (`SectionCitation`; defaults `null`, `null`, `""`, so
  round-7 frames still replay). `ReferenceNumbering.citations(claims, block_id=...)` reads back
  the rows `_write_section` has just saved for the block (citation joined to its annotation and
  addressable unit) and matches each entry on (claim span, chunk id, quote); `claim_id` is the
  addressable-unit id, which is what the committed `ClaimOut.claim_id` carries (not the
  annotation id). Store: `LiveCitation.citationId`, `claimId` (`string | null`), `quote`.
- **B2. The key findings stream.** `OpenAISynthesisBackend.write_key_findings_stream(seed, *,
  index, sources)`: the same messages; the forced `emit_section` tool cannot stream on bedrock
  (probe 1, one burst at the end), so the request asks for the same arguments as a strict
  `json_schema` reply (`emit_section`'s parameters schema, the shape probe 4 showed streams
  prose first). `JsonStringFieldDecoder("prose")` deltas and `StreamedClaimMarker` marks go to
  the key-findings slot (index 0); the "- " list is carried as it is; the whole text is parsed
  by `_salvage_section` as the forced call's arguments are; any failure (including a reply that
  is not a section object) resets the slot, counts a fallback and runs `write_key_findings`
  once. The marks need the cited ids' sources: the run collects `citable_sources(seed,
  transcript)` from every section and passes them in, and the labeller is bound around the
  pass so the marks carry "Smith 2023" names. Activity line "Writing the key findings" with
  section line "Key findings"; the pass's "Checking claims" and "Revising" lines carry it too.
  An absent key findings block clears the draft before the empty completion.
- **B3. The introduction streams into its own slot.** Skeleton slot `{index: n+2, title: "Full
  report", focus: "", role: "intro"}` (after the case studies, so no other index moves; listed
  last); `ProgressEmitter.intro_started` / `intro_completed(prose)` (no citations; empty prose
  when there is no intro). `write_full_report_intro_stream(seed, *, index)`: the structured
  call's request and schema, streamed, `JsonStringFieldDecoder("intro")` deltas, `IntroWire`
  parse, the same fallback rule. Activity "Writing the introduction" with section line "Full
  report". `LiveSectionRole` gains `intro`.
- **B4. Source notes as they are written.** The activity line names the source ("Writing a
  source note · Smith 2023", `ACTIVITY["synthesise.source_note_named"]`, short name from
  `source_short_name`); each kept note is sent as hub `SourceNote` and ephemeral SSE frame
  `artefact.source_note {source_id, title, note, occurred_at}` (`title` as the references title
  the source, `live_citations.source_names`). The hub keeps the run's notes (snapshot: after the
  draft; kept through `clear_draft` and `end_stage`, forgotten by `begin_run`, `end_run` and the
  sweep after the memory TTL; counted in `dropped`). Store: `RunStreamState.liveSourceNotes`,
  one per source in order (a reconnect's repeat replaces), cleared by a new run.
- **B5. Two rows.** `STAGE_ROW`: `acquire` → `search` ("Searching", "Querying the databases and
  collecting candidates."), `screen` → `screen` ("Screening", "Reading each abstract against the
  question."). Plan steps, stage frames and `stage_label` carry the new words through the same
  table.
- **Deviation: the key findings and the introduction now stream.** Contract N6 kept the key
  findings in "today's shape" (one forced call, not streamed), and the introduction had no live
  surface. Superseded by the owner's notes from the live run on 2026-11-05: "How come streaming
  isn't working for the key findings section?" and "There's a bit of a lag at the end of the
  synthesis where the status says 'writing introduction' but I don't see what's happening on the
  page."
- **Mock.** Skeleton gains the intro slot (index 3); the walk streams the key findings (deltas
  and one claim mark), then after the case studies sends two source notes and streams the
  introduction; `mockArtefact` gains `full_report_intro` and `most_relevant_notes` matching them;
  completed citations carry the committed ids and quotes; stage copy and rows as B5.
- **Tests.** `tests/evidence_search/synthesis/test_round8_live.py` (a whole stub run: key
  findings streamed into slot 0 with the sections' sources, the intro slot started and completed
  with the saved intro, notes sent in the saved order with the references' titles, the named
  lines; the key-findings stream at four chunk sizes with marks and the request shape, without
  sources, and its fallback; the intro stream at three sizes and its fallback);
  `test_live_citations_and_cards.py` (live entries equal the saved report's including ids and
  quote); `tests/runtime/test_progress.py` (intro slot and replay; round-7-shaped citations
  replay with null ids); `tests/core/test_liveness.py` (4 note tests); `tests/api/test_sse.py`
  (note frames live and on reconnect, the encoder); `tests/api/test_contract_models.py`;
  `tests/api/test_stage_vocabulary.py` (two rows, the named line); `test_task_agent_router.py`;
  frontend `store/reducer.test.ts` (ids, notes, intro slot), `mock/api.test.ts`.

## Round 9 backend: the search's queries and the themes live; plainer counts; the introduction's line

Built by a deep-reasoner agent from `research/briefs/round-9-backend.md` (owner notes from a
live run, 2026-11-05, night). No prompt text changed; nothing new is judged or persisted.

- **B1. The search as it happens.** `run_search` publishes "Writing search queries"
  (`ACTIVITY["search.writing_queries"]`, no count) before the query-generation call, then
  "searching · 0 found". `_LiveSearch` (one per pass, lock-guarded; both legs and their thread
  pools report to it) publishes hub `SearchQuery` / ephemeral SSE frame `search.query
  {backend, query, kind, results, occurred_at}` when each topic (`search`) or semantic
  (`search_semantic`) call goes out (`results` null) and when it comes back (its kept count);
  the same text sent once per filter variant is one entry whose count adds up. The id passes
  are one entry each, described in words: backward "Looking up {n} cited works" (`lookup`),
  forward "Following citations from {n} sources" (`citations`), Overton landmarks "Looking up
  {n} cited documents" (`lookup`), with results the pass's total. The activity line is
  "searching · {found:,} found · {query}" (the query sent last that is still out, cut at about
  60 characters on a word), "following citations · {found:,} found" while only an id pass is
  out, else "searching · {found:,} found"; `found` is the distinct records the calls have
  returned so far; `done` = found, `unit` "documents" as before. The hub keeps the run's
  queries (one per key, latest state, in first-sent order; before the ticks in a snapshot),
  forgets them with the run (`begin_run`, `end_run`, the TTL sweep), and they count in
  `dropped`. Store: `RunStreamState.liveSearchQueries`, one row per (backend, query, kind).
- **Lead rulings on the three open points (round 9).** (1) Acquisition has its own line,
  `ACTIVITY["acquire.keeping"]` "keeping {kept:,} of {found:,} candidates", with `done` = kept
  and `total` = the candidates the search counted (`acquire_sources(search_found=...)`), so the
  count never reads as a drop; the done row's figure is unchanged. (2) An option search (scope
  purpose `targeted`) publishes no `search.query` frames; its lines stay. (3) The mock's saved
  landscape names the same four themes as the live frame, in its order, with counts
  (`mockLiveThemes` is derived from `mockLandscape.themes`; `theme_count` 4).
- **Owner decision: the full-text stage collects, it does not read (round 9).** `ingest` is
  "Collecting the full texts" / "Fetching each full text and making it searchable."; its line
  "collecting {done} of {total}"; its done-row noun "collected" ("38 collected"). The full-text
  screen's "Reading full texts for relevance" (a model reading) is unchanged. Mock stage table
  updated.
- **B2. Plainer counts.** "screening {remaining:,} abstracts · {relevant:,} relevant",
  "searching · {found:,} found", "Search {n} · {found:,} found".
- **B3. Themes while they are assigned.** `ClusteringPolicy.on_labels` is called with the
  discovered labels after discovery and before assignment; only the characterise policy sets
  it, publishing hub `ThemesFound` / ephemeral frame `characterise.themes {themes: [{label,
  description|null}], occurred_at}` (kept for a reconnect, forgotten with the run). The batch
  ticks are unchanged. Store: `RunStreamState.liveThemes`.
- **B4. The introduction's line.** Section line "Introduction" (`INTRO_SECTION_LINE`); the slot
  keeps the title "Full report". The key findings keep section line "Key findings".
- **Mock.** The walk writes queries, sends five topic queries (the coverage record's) out and
  back and one citations pass, then completes `acquire` at 312; screening lines as B2;
  characterise says "Finding themes", sends four themes, then the batches; the intro line
  names "Introduction".
- **Tests.** `tests/core/test_liveness.py` (5: in place, snapshot order, themes, forgetting,
  dropped, helpers); `tests/api/test_sse.py` (encoder; live and reconnect);
  `tests/api/test_contract_models.py`; `tests/api/test_stage_vocabulary.py` (the new lines);
  `test_search_single_pass.py` (the whole pass's lines and query entries; the cut);
  `test_clustering_engine.py` (labels before assignment; only characterise publishes);
  `test_round8_live.py`, `test_acquire.py`, `test_screen.py` (strings); frontend
  `store/reducer.test.ts` (2), `mock/api.test.ts` (2 new, 2 updated).

## Round 10 backend: History lines that say what happened; runs touch the task; paging, country, a reason on a refused share

Built by a deep-reasoner agent from `research/briefs/round-10-backend.md` (four design reviews:
`share-history-polish.md` H2/P6/S5/S8, `lists-rows-polish.md`, `landscape-polish.md`). No
prompt text changed; no schema change (the new fields are read-model fields and two payload
keys).

- **History lines.** The sentences are written by the History read model
  (`api/read_models/history.py`, new; `repository.decisions_page`), per reader: a person's act
  reads "You" for that person and their display name for anyone else (`owner_display_for`, never
  the email); Policy Atlas's acts name it; a step's line has no subject. Step words come from
  `stage_vocabulary` (the run page's labels and counts). A run's searches are one row (per walk)
  quoting the first five distinct queries, then "and N more", with every query in
  `detail.queries`. A check-in answer names the option in the card's words: the decision payload
  now records `option_id` (`continuation.answer_check_in`, the gate's two ends), and the label is
  read from the pause it answers. `DecisionOut` gains `actor_display` and `actor_is_viewer`
  (null when no person acted). The plan approval and a user's check-in answer have no actor in
  their payloads; both are owner-only acts, so they read as the task owner.
- **A run touches the task.** `lifecycle.touch_task` sets `task.updated_at`; called first in the
  transaction (task row before run rows, the API's order) at a top-level walk's open and end
  (`runner._open_run`'s transaction, `runner._finish_run`) and in every check-in answer
  (`continuation._append_decision`). Option searches (child walks) do not touch it.
- **Paging.** `PageMeta.has_more` (derived: `page * page_size < total_items`) on every page;
  `GET /tasks` already took `page` / `page_size` (50 default) and `status=archived`. Store:
  `useTasksPaged` (infinite query, next page only while `has_more`).
- **Country.** `GET /tasks/{id}/evidence?country=` (any spelling: "United Kingdom", "GB", "UK";
  "Not reported" = none); `EvidenceItemOut.country`; the Landscape `geographies` keys are now
  the same display names (`repository.country_name`, from the options-scoping ISO tables), so
  the chart row and the filter share one value.
- **Refused project change.** A non-owner's `PATCH /tasks/{id}` carrying `project_ids` gets 403
  `{"error": {"code": "forbidden", "message": "Only the task's owner can change its
  projects."}}`.
- **Mock.** History fixture with the new lines and actors; 64 more tasks (55 the owner's, 6 a
  colleague's, 3 archived) paged like the server; a country on every source and the Landscape
  geographies to match; `is_public` stored; a colleague's project change refused with the
  server's message (`mockTask.is_owner = false`).

- **Follow-up (lead, same round).** The gate's server heading
  (`runtime/baseline_gate.GATE_HEADING`) is now the card's title, "Does the plan still look
  right now you have the baseline?" (`CheckInCard.BASELINE_GATE_QUESTION`). Mock gaps from the
  scoping builder: the finished longlist is the build's own 13 live options (14 rows less the
  folded one), themed, with working cards (`mockWalkOptionCards`), not the fixture's four; the
  themed build is held 1.5 s before the shortlist stage; Suggest more waits 0.8 s; one option
  search fails ("Conditionality reform for under-25s": `stage.failed`, child `failed`, row
  `search_status: "failed"`, join summary `{total 12, finished 11, failed 1}`); the gate
  bundle carries `risk_appetite` (the label); the gate card's `created_at` is the time it opens,
  so it sits after the opening question. `resetMockScenario` now also clears hand-added
  options. Gate: `pnpm vitest run src/mock src/store src/api` "Tests 180 passed (180)";
  backend gate tests (`test_baseline_gate.py`, `test_baseline_gate_checkin.py`,
  `test_task_agent_gate_turns.py`) "48 passed"; `make prompt-guard` 41 unchanged.

Tests: `tests/api/test_history_sentences.py` (new: step, search, run and check-in lines; a page
with grouped searches and a named chooser, seen by the owner and a colleague);
`test_continuation_protocol.py` (run start, answer and end touch the task; the decision carries
`option_id`); `test_tenancy_api_surface.py` (the 403 message); `test_tasks_router.py` (paging,
`has_more`, archived listed); `test_read_models.py` (country filter by spelling, the geography
name, the search golden); `test_shortlist_routes.py` (owner "You", colleague by name);
`test_pre_038_vocabulary_compatibility.py`, `test_api_conformance.py` and three pagination
literals (`has_more`); frontend `api/queries.test.ts` (paged hook), `mock/api.test.ts` (4 new,
1 updated).

## Round 11 backend: the shortlist count, the longlist walk's two searches, names while clustering, steps on earlier runs, archived projects, saved passes

Built by a deep-reasoner agent from `research/briefs/round-11-backend.md`, plus two items the
lead added mid-build (project archive, the owner's "add a way to archive (and rename)
projects"; the saved search passes, from the Sources builder). No prompt text changed. One
schema change: `project.archived_at` (migration `c4e8a2f6d1b3`, an empty nullable column).

- **Shortlist count.** `shortlist` writes `shortlisted` (the shortlist after the step: the
  reader's places, the picks and, for Suggest more, the earlier picks that stay; read back from
  the rows it reports in `shortlist.proposed`). `STAGE_COUNTS["shortlist"]` reads it; `kept` stays
  in the summary, meaning what it meant.
- **Two live searching rows (cause).** Not a child leak. Replaying the owner's live run
  (`7f311800`, 2026-11-06) through the stream's own mapping shows both rows are the longlist
  walk's: the runner dispatches the option searches after `suggest` (stage `option_searches`
  starts, seq 235), then the walk runs its own broad `acquire` (seq 246, the walk's id) while
  they run, and joins them only before `screen_abstract` (seq 1109). The children's `acquire`
  frames carry their own ids and the reducer drops them. The real defect found on the way: the
  fan-out and join events have no component run, so their stage frames carried
  `capability_run_id: null` (passes any run filter). Fixed: the join payload names the walk and
  the stream falls back to the payload's `capability_run_id`. Whether two live rows should read
  as one is a display ruling, not decided here. The mock now runs the walk's own search beside
  the option searches, then `screen`, `classify`, `appraise`, as the server does.
- **Ticks name their walk** (lead, from the workspace builder). A child option search's
  `acquire` tick landed on the walk's own Searching row and the run status bar: ticks carried no
  run. `TickFrame.capability_run_id` (null when unknown); the hub keeps a stage's memory per
  walk and stage, so the two `acquire` lines no longer coalesce into one another; the harness
  binds the component run's walk (`task_liveness(..., run_id=)`), the join's tick names the
  longlist walk. The reducer drops a tick from another walk as it drops that walk's stage
  frames (`isOtherRunsStage`); an unnamed tick still applies.
- **Mock ticks** (lead): the scoping walk sends no line that only repeats its row's label
  (inherit, suggest, appraise send none; classify sends "1,200 of 2,410 classified"); its
  ticks name the walk.
- **Names while clustering.** The `characterise.themes` frame gains `stage`
  (`characterise` | `longlist` | `theme`); `ClusteringPolicy.on_labels` publishes the longlist's
  options (each pass; the residual pass replaces the list) and the theme stage's themes. The hub
  keeps the latest per stage for a reconnect. Store: `liveOptions` and `liveOptionThemes` beside
  `liveThemes`, cleared on a new run.
- **Steps on each run.** `RunOut.stages: RunStageOut[]` on `GET /runs` and `GET /runs/{id}`,
  folded from the frames the stream sends (`sse.walk_stages`): `{stage, label, status
  (started|completed|failed|skipped), started_at, ended_at, summary, counts, seconds}`, the walk's
  own only. A pre-round-11 join completion with no walk goes to the walk whose fan-out started
  last. Mock: each walk's steps folded from its emitted frames.
- **Archived projects.** `POST /projects/{id}/archive` (owner only; idempotent, first time
  kept), `GET /projects?status=active|archived|all` (`active` default), `ProjectOut.archived_at`.
  Archiving leaves the project's tasks as they are (lead ruling). No unarchive (tasks have
  none). `useArchiveProject(projectId)`; mock route and filter.
- **Saved search passes.** The coverage read listed each id call of a citations or lookup pass
  as a "query" with its ids as text. `CoverageBackendDetailOut.queries` is now the written
  searches only and `passes: [{pass: "citations"|"lookup", query, results}]` the passes, one per
  run, backend and verb, in the order run, counted by distinct ids, worded "Followed citations
  from N sources", "Looked up N cited works", "Looked up N cited documents" (new `ACTIVITY`
  keys). `results` counts both. Mock coverage carries the citations pass.

Tests: `test_shortlist.py` (count after the step, with Suggest more), `test_stage_vocabulary.py`,
`test_option_search.py` (the stage frames name the walk; the join payload and tick),
`test_liveness.py` (names per stage, residual replaces; a walk's and its option search's ticks
apart), `test_harness.py` (the stage ends under its walk), `test_sse.py` and
`test_contract_models.py` (the frame's `stage`), `test_sse.py` (a tick names its walk),
`test_schema.py` and `test_migration_057_document_store.py` (the new column and head), `test_clustering_engine.py` (three policies
publish under their stage), `test_runs_router.py` (a walk's own steps, a child's apart, the old
unnamed join), `test_projects_router.py` (archive, list filter, tasks untouched, 404 to an
outsider), `test_read_models.py` (passes in words); frontend `store/reducer.test.ts` (the live
run's replay order; names by stage; a child's tick dropped), `mock/api.test.ts` (walk stages and names, runs' steps,
archive, coverage passes), `api/mutations.test.ts` (`useArchiveProject`).

## Round 12 backend: the option-search count from the fan-out, plainer option words, twenty a page, a full-text link, sources by query

Built by a deep-reasoner agent from `research/briefs/round-12-backend.md`, plus item 6 the lead
added mid-build (a reader clicks a query in All sources and the table filters to what it
returned). No prompt text, no schema change.

- **The option-search count from the start.** The fan-out publishes the `option_searches` tick
  at once ("0 of 12 searches done · 0 sources"), then a daemon poll re-reads the children every
  0.5 s while the walk runs its own broad search; the join stops it and publishes the same line
  from then on (one body, `_publish_progress`). The poll also stops when every child has ended,
  after the join timeout, on `abandon_children`, or on a failed read (logged, never the walk's
  failure). "so far" dropped from the line. Mock: the 0-of-12 tick at the fan-out.
- **Words.** "Options may be combined or added" (`longlist` blurb, `longlist.clustering`);
  "Estimating what each option would take" (the `option_profile` label); the profile steps'
  "Writing" verbs: "Estimating each option" (`option_profile_line`) and "Describing the places"
  (`option_profile_place_sentences`, `option_profile.places`). Mock copies follow.
- **Twenty a page.** `LIST_PAGE_SIZE_DEFAULT = 20` for `GET /tasks` and `GET /projects` (the
  max stays 200; the read models keep 50). Client: `useTasks` and `useProjects` ask for 200 when
  the caller names no size, so pickers and name lookups never stop at twenty silently;
  `useProjectsPaged` added for a Projects list with Show more. Mock lists page at 20.
- **Full-text link.** `EvidenceItemOut.full_text_url` (and so the dossier): the address the full
  text was fetched from (`task_source_snapshot.fetched_from`, else the full-text snapshot's
  locator), only when `ingested` and http(s); Europe PMC's XML service reads as the article page.
- **Sources by query.** `search.executed` carries `record_ids` (the backend record ids an ok
  call returned; passes too). The coverage rows carry `query_id` (the event's sequence; a pass's
  first call). `GET /tasks/{id}/evidence?query=<query_id>` keeps the rows whose backend and
  `backend_record_id` that search (or every call of that pass) returned; a search from before
  the ids were kept, or an unknown key, gives the empty page. Mock: `query_id` on each coverage
  row, `mockEvidenceByQuery`, the filter honoured.
- **Places with no one country** (item 7, lead mid-build). "Where it has been evaluated" no
  longer groups them under "No single place": after the countries come "Several countries"
  (top level "multiple countries"), "Place not stated" and "Other", each absent when empty
  (`place_sentences.NO_COUNTRY_GROUPS`). The place name is data to the sentence call; no prompt
  file changed. Mock fixtures and `OptionCard.test.tsx` follow.
- **Projects by last activity** (item 8). `GET /projects` orders by `last_activity_at` (the
  newest of the project's `created_at` and its counted members' `updated_at`: active,
  caller-readable, own organisation, the members `task_count` counts), newest first, ties by
  `project_id`; `ProjectOut.last_activity_at` on every project read. Mock: the field, the order.
- **Mock abstracts** (item 9). The mock's evidence rows carry their abstracts (provider, and the
  uploaded row's LLM description as its dossier has it); one row stays title only.
- **Card text** (item 11). The shortlist's card text reads "What it could take" and follows the
  card: How it works, Evidence (the places first, then the outcomes, the maturity rung and the
  documents), then What it could take after the document lines (`CardText.tail`, kept whole
  when the ceiling cuts document lines).
- **Mock dossiers** (item 12). The mock's dossier route serves every id a page links to: a
  written dossier, else the evidence row's own fields, else an option card's document
  (`mock-doc-a1` and kin); an unknown id stays 404. The mock's evidence read pages like the
  server (`page`, `page_size`, 50 by default).
- **Option documents for the References form** (item 13). `OptionDocumentOut` gains `authors`
  (names, in order, as the reference line names them; empty when unknown) and `venue` (as the
  evidence row's); `year` was already there. The mock's card documents carry all three.
- **Whom an option acts on** (item 15; the lead changed the prompt, `option_profile_v5`).
  `_checked_setting` takes the setting call's `acts_on`: each item folded onto one line and
  lower-cased; a blank item, a repeat or more than four fails the answer as malformed. The
  profile column writes `"setting": {"main", "second", "acts_on"}` (same JSON, no migration);
  `OptionProfileOut.acts_on` serves it, empty for older profiles. Mock profiles carry two or
  three each.
- **Funnel rows to the sources table** (item 16, round 13). `GET /tasks/{id}/evidence` takes
  `depth=full_text|abstract|title` (the Status column's read depth, the client's
  `readDepthLabel` rule) and `appraised=true|false` (has an appraise result). The funnel's
  `quality_checked` now counts distinct appraised documents (lead ruling), so a redrawn plan
  that appraises a document again still counts it once and matches `appraised=true`. The
  "Full text accessed" row (`read_in_full`) already counted obtained texts only (`ingested`);
  the `!= not_attempted` count only decides whether the row has a number. A test with one
  failed fetch pins that it equals `depth=full_text`. Mock: both honoured.
- **A reason after a one-click exclusion** (item 17, round 13). The exclude route, on an option
  the same user already excluded (state `excluded`, `by: user`, the latest `option.excluded`
  event's actor): with a reason, fills the stored reason in and writes one
  `option.exclusion_reason_added` event ("You gave a reason: …"); with none, changes nothing.
  No new route. Test: History shows one exclusion and one reason line.
- **A search to start from in the mock** (item 18). One finished Evidence search, "Youth
  employment programmes: what works" (`MOCK_LINKABLE_SEARCH_ID`), in the mock project with a
  succeeded latest run, so the New page's "Evidence search to start from" offers it. The mock
  project counts 2 tasks; the task lists hold one more row. Creating a task in the mock links
  each chosen `from_task_ids` search under its own name, one link each (item 19).
- **The grounding verdict on the claim** (item 20). `ClaimOut.grounding_tier` and
  `ClaimOut.grounding_rationale`, filled from the claim's annotation payload; `CitationOut`
  loses both. Live: `artefact.section_completed` gains `claims[]` (`SectionClaim`: `claim_id`,
  `start`, `end`, `tier`, `rationale`, from `ReferenceNumbering.claim_verdicts`) and its
  `citations[]` lose `tier`. Store: `LiveSection.checkedClaims` (`LiveCheckedClaim`), and
  `LiveCitation.tier` gone. Mock fixtures and stream follow. The report view's readers are the
  report and workspace builders' to wire.
- **Live query ids** (item 10) not built: the `search.query` frame goes out while the search
  runs, and the `search.executed` event is written at the end of `acquire`, inside the step's
  transaction, so its sequence is unknown at the frame and uncommitted until the step ends (a
  rolled-back sequence is reused, `events.append` takes max+1). A safe build is a second frame
  after the runner's commit, mapping each event back to the frame's `(backend, query, kind)`;
  left for the lead.

Tests: `test_place_sentences.py` and `test_longlist_routes.py` (the three groups, an empty one
absent), `test_projects_router.py` (pages by last activity, `last_activity_at` on the list and
the single read), `test_card_text.py` (the card's order, the profile after a cut), `test_option_profile.py` and
`test_longlist_routes.py` (`acts_on` checked, written and served; empty for an older profile),
`test_option_search.py` (the first tick at the fan-out, the poll current until the join,
the poll ending by itself), `test_stage_vocabulary.py`, `test_theme.py`, `test_option_profile.py`
(words), `test_api_conformance.py` and `test_admin_leg.py` (twenty a page, projects too),
`test_acquire.py` (`record_ids` on the event; one id key per mapper), `test_read_models.py`
(filter by query and by pass, the empty page for an older search; `full_text_url` with Europe
PMC, an older row and an uncollected one; passes carry `query_id`); frontend `mock/api.test.ts`
(the 0-of-12 tick, twenty a page, filter by query, full-text links), `api/queries.test.ts`
(`useProjectsPaged`, `useProjects` asks for the whole list), `api/queryKeys.test.ts`.

## Round 14 backend: names from the question, chat titles, country none, archiving a project's tasks, own searches link, a pending fetch

Built by a deep-reasoner agent from the lead's round 14 message (owner, 2026-11-07), plus two
additions from the lists builder. The lead wrote the two title prompts (`task_title_v1`,
`chat_title_v1`) and their route steps; no prompt file changed here. No schema change.

- **Task names from the confirmed question.** `api/titles.name_task_from_question`, at the
  step 1 decision (owner): on a turn whose message answers the question part
  (`[confirm part=question …]`, sent for a pick and for accepted words), with the draft's
  question, after the turn's commit and in the turn's worker before the stream's completed
  line; and on a `PATCH /plan` that edits `question` (off the request). Not at plan approval. It calls the `task_title` step
  (`AgentBackend.write_title`) and renames through `rename_task` as `agent` ("Policy Atlas
  renamed the task to …"), the event carrying `prompt_version` and `question`. Skipped when a
  person has renamed the task (any rename not by Policy Atlas, checked again under the row
  lock) or the name was already written for that question; a failed call, or no line, keeps
  the name. `cache_modes` gains both title steps (`breakpoint`, one-shot).
- **Chat titles.** The first message's reservation still writes the cut at once; the stream
  route then calls `chat_title` off the request and replaces the cut with `clean_title` of the
  line, only while the chat still carries the cut. A failed call, or no line, leaves the cut.
- **The chat's new title, live** (item 11). When the `chat_title` line lands while the first
  turn's NDJSON stream is open, the stream sends `{"type": "conversation.titled",
  "conversation_id", "title"}` (`ConversationTitledEvent`, never terminal; dropped once the
  stream has ended). Not on the task's SSE stream: that stream is readable by people who
  cannot read the chat. Client: `store/conversations.applyConversationTitle` puts the title
  into every cached chats list of a task and the chat's detail, so the list re-renders without
  a refetch, then marks the task's chats reads stale so the next server read confirms it;
  accepted after the terminal line too. Mock: the event a second after the first
  answer. Tests: `test_chat_stream.py`, `store/conversations.test.ts`, `mock/api.test.ts`.
- **The summaries pass moves the line** (item 12). `write_summaries_after_commit` ran after
  the harness's `task_liveness` had ended, so its line reached nobody. The runner now binds
  `task_liveness(task_id, stage="synthesise", run_id=<the walk>)` around it; the pass publishes
  "Summarising the sections · n of N" per section (`synthesise.summary_section`, with
  done/total/unit `sections`) and "Checking the summaries" (`synthesise.summary_check`) before
  each judge call. Mock: the same lines after the introduction. Tests: `test_runner.py` (the
  pass runs bound to the task, the stage and the walk), `test_summary_runtime.py` (the lines),
  `mock/api.test.ts`.
- **`country=none`** on the evidence read keeps the rows with no publisher country (the same
  set as "Not reported"). Mock too.
- **Archiving a project archives its solo tasks** (owner, reversing round 11): the caller's own
  active tasks in the project that no other active project holds, in the same transaction,
  each through `archive_task` with `project_id` and `project_name` on its `task.archived`
  event ("You archived the project “X”, and this task with it."). The route returns
  `ProjectArchiveOut` = `ProjectOut` + `archived_task_count`. `ProjectOut.solo_task_count`
  gives the same count before archiving. Client: `useArchiveProject` also refreshes `["tasks"]`.
  Mock: the count, the archive and the overlay, reset with the scenario.
- **Linking your own searches: reverted** (owner correction). The New page lists only searches
  in the same project again, so `_write_links` keeps the shared-project rule for every search
  and `flagged` keeps its meaning; the code and tests are as before round 14. The mock's
  finished search stays in the mock project.
- **A longlist theme's sources** (item 7). `GET /evidence?theme=` also takes a longlist theme
  id on an options-scoping task: the documents of every option in it (their memberships in this
  task), by the latest longlist's grouping. The two id spaces are unioned, so an Evidence
  search's characterisation theme reads as before. Mock: a longlist theme lists its options'
  card documents.
- **The shortlist note, one writer** (item 10; the lead's `shortlist_v2` and
  `shortlist_note_v1`). `shortlist_note.write_shortlist_note` runs the `shortlist_note` step
  (`LonglistBackend.shortlist_note`) with the plan's outcomes, the option list (short ids, lever
  types, ambition, excluded and why) and the places as they stand, and stores `note`,
  `places_at` and `note_prompt_version` on the latest `longlist_result.shortlist`. The shortlist
  step calls it after its picks with the proposal's changes (each place added, with its reason,
  or removed); a failed note keeps the picks. `ShortlistOut.note_stale`: the places differ from
  `places_at` (or a proposal has no note). `POST /tasks/{id}/shortlist/note` (owner only)
  calls the same writer with no changes only when stale, else returns the shortlist as it is;
  one History line, "Policy Atlas updated the shortlist note" (`shortlist.note_updated`).
  Mock: `note_stale` and the route. The constants `SHORTLIST_NOTE_MIN_CHARS` and
  `SHORTLIST_NOTE_MAX_CHARS` stay in `shortlist_prompt.py`: its `reask_message` still passes
  them (a prompt-file edit, the lead's).
- **A note refresh opens no run** (round 15, owner bug). Checked: `POST /shortlist/note` runs the
  note writer inline under the request and creates no capability or component run, no `run.*`
  or stage event; its one event is `shortlist.note_updated` (run `null`).
  `test_shortlist_routes.py` pins it: the runs read and the `capability_run` rows are unchanged,
  and the only new event is that one; the stream maps that event to no frame (`_map_rows`
  returns none for it) and the request publishes no tick to the hub (nothing is bound). The
  reducer opens a run only from a `run.status` frame: a tick with no run never does
  (`reducer.test.ts`). The thread card is placed client-side:
  `TaskAgentPane` puts a decision with no walk into whichever parentless walk's window holds its
  time, an open walk included, so the note's History line lands in a run block there.
- **A longlist theme's document count** (item 9). `LonglistThemeOut.document_count`: the
  theme's distinct member documents across its options, each once, the rows
  `evidence?theme=` lists. Mock: counted the same way.
- **Ingest in the mock walk** (item 8). The mock's Evidence search walk runs `ingest` between
  appraise and characterise: the rows it collects read `queued`, then `ingested` one by one, a
  tick each ("collecting n of N"); the state resets with the scenario.
- **Traced under the pipeline's names** (lead, owner's check). Every new call goes through the
  shared `traced_parse` (`tracing.traced_attempts`): `task_agent:title` (step `task_title`, the
  task's session, under the turn worker's user scope), `chat:title` (step `chat_title`, the
  conversation's session, under the user's scope in its thread), `shortlist:note` (step
  `shortlist_note`, inside the shortlist component on a proposal, under the refresh route's
  user scope on a refresh); `acts_on` rides in the `option_profile` setting call.
  `test_round14_observation_names.py` pins the names, steps, versions and sessions.
- **A pending fetch.** `EvidenceItemOut.full_text_status` (`not_attempted` | `queued` |
  `ingested` | `fetch_failed` | `parse_failed`); `queued` is the fetch handed to the ingest
  queue and not yet back. Mock rows carry it (one `queued`).

Tests: `test_titles.py` (the name written as Policy Atlas with its version and question, not
again for the same question; a user's rename stands; a failed or empty call keeps the name; the
turn hook reads only the question part's answer; a chat's cut replaced, kept when nothing is written, left when renamed),
`test_projects_router.py` (solo count, archive with a shared task kept, the event and its
sentence), `test_longlist_routes.py` (a longlist theme lists its options'
documents; an unknown theme none), `test_read_models.py` (`country=none`, `full_text_status`;
the Evidence search theme filter unchanged),
`test_shortlist.py` (picks then the note with their changes and places; a failed note keeps
the picks and reads stale), `test_shortlist_routes.py` (fresh is a no-op, stale after a place
moves, owner only, one History line, the places stored),
`test_model_routes.py`, `test_step_timeouts.py` (the title and note sites, added to
`scripts/step_timeouts.py`); frontend `mock/api.test.ts` (`country=none`, archive with solo
tasks, a longlist theme's documents, the ingest stage),
`api/mutations.test.ts` (`["tasks"]` refreshed).

## Diff summary

Filled per phase as it lands; the flagged deviations are in § Review handoff.

## Intent & assumptions

- The hub API (`core/liveness.py`) was designed by the lead before any brief was written
  and is recorded in `research/briefs/hub-api.md` (gitignored research folder). Every
  Phase 1 and Phase 2 brief codes against it.

## Known unverified items

- The N25 fixed-question measures were skipped by the owner (2026-11-09, § N25 measures);
  both capabilities were watched on the live dev app by the owner through rounds 6 to 15, and
  the owner's notes from those runs drove the rounds. No before/after figure exists for the
  perceived-latency targets.
- Not reproduced: the owner's report (round 15) of a new progress card in the Task Agent
  thread on each shortlist-note refresh. The server, the stream, the hub, the reducer and a
  live-app run on task 7f311800 were all clean; the thread's placement rule was tightened
  anyway. Needs the task, the view and a screenshot.
- Not proven by test: that the `chat:title` generation nests inside the chat turn's trace and
  that a note refresh carries the task's session id (round 14 backend report).
- Chat's turn citations still carry a per-citation verdict (the chat API's shape); the
  report's moved to the claim (round 13).
- **D1 build-time check, done 2026-11-05** (`research/exp-luna-strict-check.md`, two live calls,
  cents): Luna accepted the streamed strict `json_schema` response with the raw
  `SectionProseWire` schema (what the section call sent before the streaming fix) and with the strict-transformed one
  (what the planner sends); both streamed `prose` ahead of `claims` (first payload 1.031 s and
  0.896 s, last chunk 1.824 s and 1.783 s), validated, and carried usage on the last chunk. The
  strict-transformed schema makes the model fill every optional claim field with `[]`/`null`
  (230 against 260 output tokens); the raw schema leaves them out. Neither Luna call shows how
  strictly Bedrock enforces the two strict-mode rules the schema breaks (`default` keys, the
  open map on `PatternPayloadWire.stated`): the once-only fallback (N6) covers a refusal.
- The Codex spend cap means no Codex family-flip review happened in the build; conversation C's
  adversarial lane covers it if the cap is lifted.
- The `#000` design-hook findings in `frontend/src/index.css` are the pre-existing print
  stylesheet (black ink); the ignore could not be persisted from this session (permission
  denied) and is disclosed instead.

## Public safety

No secrets, no raw source text and no model output in this file or the commits. The research
folder (briefs, screenshots, captures) is gitignored. Ticks carry the model's search query
text, derived from the user's question: it goes only to the task's authenticated stream,
normalised and bounded at 120 characters, never to a log line (`normalise_query`, and the
writer's publisher never logs it).

## Review handoff (step-7/8 inputs)

### Dispatch log (plan § Briefs, P15)

| Brief | Seam | Executor planned | Executor actual | Result |
|---|---|---|---|---|
| F | `scripts/stream_capture.py`, `stage_walls.py --capture`, tests | builder | builder (Opus) | done 2026-11-05: 30 tests pass, ruff clean. Two departures the lead accepted: `--until-terminal` follows the run the page follows (the reducer's rule) and ignores terminal statuses older than the capture start; the measure uses that run's stage frames only. |
| A | `core/liveness.py` hub | codex | **deep-reasoner** (Codex died on the workspace spend cap before applying any change) | done: 15 hub tests, the ingest and single-pass tests pass; nine API points interpreted (recorded in the agent's report, the main ones: a held append is sent to existing subscribers before a snapshot so no text arrives twice; the kept draft keeps the first 20 000 characters; `end_run` resets the dropped counter; a loop tick blocks hook verbs for the rest of the stage). Lead change after: `clear_draft` sends a held append before forgetting the draft. |
| B | `core/tracing.py` hooks, `traced_parse` `before`, harness stage binding | codex | codex (code applied; cap hit) → deep-reasoner finished | done; `_verb` imports the table inside the function (core stays import-light) |
| C | `api/routers/sse.py` encoder, snapshot, drain | codex | codex (code applied; cap hit) → deep-reasoner finished | done; the revocation tests now also publish a delta and a revising mark after revocation and assert nothing leaks |
| D | runner `begin_run`/`end_run`, `wall_clock_s`, join-loop tick | codex | codex (code applied; cap hit) → deep-reasoner finished | done; note: `component.timing.headline_counts` now carries `wall_clock_s` for every component (it copies the completed payload); `stage_walls.py` reads the top-level timing field, so the anatomy is unchanged |
| E | loop counts (N2) | fast-worker | fast-worker | done: ten loops, five summary keys (`theme_count`, `selected_count`, `finding_count`, `group_count`, `documents`), new `core/done_callbacks.py` (a pool thread runs a done-callback in an empty context, so the callback must carry the submitting thread's context or the bound task is lost); `ClusteringPolicy.progress_key`; `round_index` is 1-based so "Search n" shows from the second pass |
| G | `section_emit_stream` | codex | codex (method and loop call applied; cap hit) → deep-reasoner finished | done; the decoder dropped the first of two adjacent high surrogates (fixed, every-split-point test); lead: the step's `CACHE_MODES` row was missing, so every streamed turn fell back silently (added `auto`); lead: one decoder for both sites (`core/openai_client.JsonStringFieldDecoder`) |
| H | writer activity lines, revising frame | codex | deep-reasoner (cap) | done with G; "Checking claims" and the revising frame also run for key findings, which is not streamed (harmless: the client blurs only draft spans) |
| J | planner stream | codex | deep-reasoner (cap; Codex applied nothing) | done; the strict schema sent is `openai.lib._pydantic.to_strict_json_schema(wire)` (the raw schema is not strict-valid); the pre-token retry catches the SDK's error classes only (the import guard forbids `httpx`); the shared test helper `resource_support.task_agent_turn` now reads the stream |
| K | planner fixes (N18/N19/N20 backend) | fast-worker | fast-worker | done; its asterisk test needed a real option id on `PendingAction` (lead fix) |
| M | frontend store (N5, N7, N15, N16, N23) | codex | deep-reasoner (cap) | done: 106 tests; the watchdog, drafts held before the skeleton, child frames refresh `options` only, ingest ticks refresh evidence and landscape once per 5 s |
| N | mock contracts and fixtures (N26 first half) | fast-worker | fast-worker | done: 43 tests; the annex figures; the real `search_review` check-in; twelve child walks; the options read; scenarios `reload-mid-section`, `paused-strip`; `setMockPace` for unit tests. Follow-up by a second fast-worker: the walk-time longlist read shares the options read's ids and grows stage by stage. |
| O | card C, strip, tab marks, title, task row, Plan control, Sources default, one orange | frontend-designer | frontend-designer (hit its 150-turn limit; reported on a resume) | done: 859 view tests; `useFreshness`, `taskLive.tsx`, `planPanel.tsx`; the client vocabulary deleted; screenshots partial (round 1 of the run status bar, the paused card, the task row). Lead after: the done-row counts moved to the frame; the mock sends `plan.updated` at run start; dot trough 0.5. |
| P | Result tab before and while writing; the sidebar | frontend-designer | frontend-designer | done: 143 tests; `SidebarRun.tsx`; screenshots of every state (round 1 and 2). Lead after: three copy fixes (ended-early line, "just now", the tail shows the activity only). |
| Q | planning conversation and check-ins (N9, N10, N18, N19, N20) | frontend-designer | frontend-designer | done: 956 tests across views, store and api; the turn stream reader, `planEdits.ts`, `Button variant="start"`, `LABEL_CLASS`; screenshots of scenes 10 to 12. Lead after: the server's check-in render starts with its question (`CHECK_IN_QUESTIONS`), and the client titles the card with it. |
| R | the longlist during the build (N24) | frontend-designer | frontend-designer | done: 174 tests; `LonglistBuilding`, `useOptions`; no screenshots (two mock gaps, fixed by the follow-up to N). Lead after: the clustering note comes from the server tick. |
| S | the mock journeys (N26 second half) | fast-worker | fast-worker | done: 31 Playwright tests pass (`pnpm exec playwright test e2e/journey.spec.ts e2e/scoping.spec.ts`, 1.1 min); scenarios selected by an init script that appends `mockScenario=` to the `/events` request; transient states asserted from a record of every distinct line the page showed. Mock gaps (private fixture, not product): the mock always serves a committed report so the early Result tab is tested with a shimmed 404; a literal reload resets the mock world, so the reload case asserts what a reconnect sees under `reload-mid-section`; the mock skeleton has two sections and no key-findings slot, so the footer and key-findings states are unit-tested only; no part cards on the mock's scoping task; the mock's check-in facts line still says "2 rounds". |
| L | task-list stage, options read | codex | deep-reasoner (cap) | done; the `LatestRun.model_rebuild` workaround for the `StageKey` import cycle was replaced by the lead: `StageKey`/`STAGE_KEYS` now live in `contract/common.py` and are re-exported |
| evidence-live | sources read and citations as they close (two ephemeral frames, hub, Result tab) | deep-reasoner | deep-reasoner (Opus) | done 2026-11-05: `make -C backend verify` "4302 passed, 1 skipped", mypy "Success: no issues found in 465 source files", ruff "All checks passed!"; `make frontend-verify` "Test Files 93 passed (93)", "Tests 1141 passed (1141)", build ok; `make drift-check` "drift-check: OK" (after `make openapi-sync`); `make prompt-guard` "41 prompt file(s) unchanged"; `pnpm e2e` "32 passed", 1 failed: journey scene 1 (the run trace header, `RunTrace.tsx`, being rewritten by the concurrent polish pass); scene 6 passed. A first `pnpm e2e` run beside the backend suite had 5 `page.goto` timeouts (load). |
| round-7-backend | citations on `section_completed`; case studies streamed card by card (slot last with roles, frame, hub, store, mock); a fixed reference order in `artefact_out` | deep-reasoner | deep-reasoner (Opus) | done 2026-11-05 after two lead decisions: `make -C backend verify` "4322 passed, 1 skipped", mypy "Success: no issues found in 467 source files", ruff "All checks passed!", build ok; `make drift-check` "drift-check: OK" (after `make openapi-sync`); `make prompt-guard` "41 prompt file(s) unchanged"; `pnpm vitest run src/store src/api src/mock` "Tests 165 passed (165)"; `pnpm exec tsc -b` clean on the combined tree. An earlier full run had `test_option_searches_run_at_the_configured_width` fail once under load (passes alone and on every rerun). |
| round-8-backend | citation ids and quote on `section_completed`; key findings and the introduction streamed into their slots (intro slot, role `intro`); source notes live (`artefact.source_note`, hub, store); search and screen as two rows; mock | deep-reasoner | deep-reasoner (Opus) | done 2026-11-05: `make -C backend verify` "4344 passed, 1 skipped", mypy "Success: no issues found in 468 source files", ruff "All checks passed!", build ok; `make drift-check` "drift-check: OK" (after `make openapi-sync`); `make prompt-guard` "41 prompt file(s) unchanged"; `pnpm vitest run src/store src/api src/mock` "Tests 170 passed (170)"; `pnpm exec tsc -b`: one error, in `views/workspace/runProgress.ts` (a concurrent designer edit), none in the store, api or mock. |
| round-9-backend | the search says it writes its queries and shows each query out and back (`search.query`, id passes in words); "new" and "so far" gone from the counts; themes shown once found (`characterise.themes`, `ClusteringPolicy.on_labels`); the introduction's line "Introduction"; store and mock; then the lead's rulings (`acquire.keeping`, no query frames from option searches, mock themes aligned) and the owner's "Collecting the full texts" | deep-reasoner | deep-reasoner (Opus) | done 2026-11-05 (first gate, before the rulings): `make -C backend verify` "4356 passed, 1 skipped", mypy "Success: no issues found in 468 source files", ruff "All checks passed!", build ok; `make drift-check` "drift-check: OK" (after `make openapi-sync`); `make prompt-guard` "41 prompt file(s) unchanged"; `pnpm vitest run src/store src/api src/mock` "Tests 174 passed (174)"; `pnpm exec tsc -b` clean on the combined tree.; after the rulings and the "collecting" copy: `make -C backend verify` "4358 passed, 1 skipped", mypy "Success: no issues found in 468 source files", ruff "All checks passed!", build ok; `make drift-check` "drift-check: OK"; `make prompt-guard` "41 prompt file(s) unchanged"; `pnpm vitest run src/store src/api src/mock` "Tests 174 passed (174)"; `pnpm exec tsc -b` clean. |
| round-10-backend | History lines that say what happened, with the actor ("You" for the reader, the name for others, "Policy Atlas"), one search row with its queries, the check-in's option recorded and named; a run's start and end and a check-in answer touch `task.updated_at`; `has_more` on every page and a paged tasks hook; `country=` on All sources and `country` on each source, the Landscape geography names shared; the 403 message on a colleague's project change; mock | deep-reasoner | deep-reasoner (Opus) | done 2026-11-06: `make -C backend verify` "4365 passed, 1 skipped", mypy "Success: no issues found in 470 source files", ruff "All checks passed!", build ok; `make drift-check` "drift-check: OK" (after `make openapi-sync`); `make prompt-guard` "41 prompt file(s) unchanged"; `pnpm vitest run src/store src/api src/mock` "Tests 179 passed (179)"; `pnpm exec tsc -b`: two errors, both in `views/LandscapeViewCharts.test.tsx` (a concurrent designer edit), none in the store, api or mock. |
| round-11-backend | the shortlist row counts the shortlist after the step (`shortlisted`); the two live searching rows traced to the longlist walk's own search beside its option searches (the walk-level stage frames now name the walk); clustering names live per stage (`characterise.themes.stage`, `liveOptions`, `liveOptionThemes`); `RunOut.stages`; then the lead's additions: archived projects (`archived_at`, `POST /projects/{id}/archive`, `status=`), saved search passes in words (`CoverageBackendDetailOut.passes`), ticks name their walk (`TickFrame.capability_run_id`, hub memory per walk), mock ticks without the label | deep-reasoner | deep-reasoner (Opus) | done 2026-11-06: `make -C backend verify` "4373 passed, 1 skipped", mypy "Success: no issues found in 470 source files", ruff "All checks passed!", build ok; `make drift-check` "drift-check: OK" (after `make openapi-sync`); `make prompt-guard` "41 prompt file(s) unchanged"; `pnpm vitest run src/store src/api src/mock` "Tests 186 passed (186)"; `pnpm exec tsc -b` clean on the combined tree. Earlier full runs failed only on tests this round had to update (head revision, the project column set, three fake hubs) and once on contract edits made while the suite ran. |
| round-12-backend | the option-search count from the fan-out (a poll until the join); "combined", "Estimating", "Describing the places"; twenty a page for tasks and projects (`useProjectsPaged`); `full_text_url` on source rows; sources filtered by a coverage row's `query_id` (`record_ids` on `search.executed`); "Several countries", "Place not stated", "Other" replace "No single place"; projects by last activity (`last_activity_at`); mock abstracts and dossiers; card text in the card's order | deep-reasoner | deep-reasoner (Opus) | done 2026-11-06, final gate after items 7 to 12: backend 4,379 passed, 1 skipped (16 min 54 s); then mypy 470 files (after one fix), ruff, build; the touched suites rerun after the last edits (185 passed); drift-check OK; prompt-guard 41 unchanged; vitest store/api/mock and the Sources and longlist views passed; `tsc -b` clean. Item 10 (live `query_id`) not built: ordering, see § Round 12 backend |
| round-14-backend | task names from the confirmed question (`task_title`), chat titles (`chat_title`), `country=none`, a project's archive archives its solo tasks (`archived_task_count`, `solo_task_count`), `full_text_status` on source rows (one's own searches linking whatever their projects was reverted) | deep-reasoner | deep-reasoner (Opus) | done 2026-11-09: backend 4,402 passed, 1 skipped (8 min 6 s), mypy 478 files, ruff, build; then the observation names (85 passed in the touched suites; mypy and ruff clean); drift-check OK; prompt-guard 43 unchanged; vitest store/api/mock 198 passed; `tsc -b` clean |

**Executor substitution (memory rule, owner 2026-07-09):** the Codex workspace spend cap was
hit at about 09:30 on 2026-11-05 during Phase 1. Every Codex-marked seam from that point
runs on `deep-reasoner` (Opus); the family flip for review stays with conversation C's
Codex adversarial lane if the cap is lifted, else with the Claude lanes alone (to be
adjudicated at step 7).

### Prompt-hash re-pin (G2)

`python3 scripts/prompt_hash_guard.py --update` re-pinned two files on 2026-11-05:

- `evidence_search/synthesis/section_prompt.py`: `d9011b4a…` → `b771fd12…`. The only text change
  is a second final-turn message for the streamed shape, `SECTION_FINAL_TURN_MESSAGE_STREAMED`
  ("This is your final turn: write the section now, as the prose and the claims this section can
  support from what you have gathered."), selected by `build_section_messages(..., streamed=True)`.
  The research turns, the repair and the forced-tool final turn keep their wording.
- `runtime/task_agent_prompt.py`: `4071ece4…` → `ead2bf75…`. The three preset time bands are
  now read from `task_plan.TIME_BANDS` (one table, N20). Two bands were already equal; the
  Rapid overview band changes from "~5-10 min" to "~10-15 min" (the plan document's value).
  No other prompt text changes; `PLANNER_PROMPT_VERSION` stays (like-for-like swap ruling).
- `runtime/task_agent_prompt.py`, second re-pin (owner note after polish round 3, 2026-11-05):
  the three thoroughness `sub` sentences are cut to the plain voice ("Abstracts only: themes,
  coverage and gaps. Up to 100 papers and 50 policy documents."; "Reads about 15 of the
  strongest sources in full. Up to 200 papers and 100 policy documents."; "Reads about 25
  sources in full and extracts their findings. Up to 400 papers and 200 policy documents."),
  and the non-intervention Detailed report example likewise. Labels, ids, bands and the caps
  are unchanged; `PLANNER_PROMPT_VERSION` stays.
- `evidence_search/synthesis/section_prompt.py`, second re-pin (owner go on the streaming fix,
  2026-11-05): `b771fd12…` → `197e3a63…` (`SECTION_PROMPT_VERSION` bumped to
  `synthesise_section_v12`, a behaviour change, so not a like-for-like swap; the prompt-pin test
  `test_section_prompt_templates.py` now hashes v12). The "How to work" bullet now tells the writer to call
  `write_section` (a new no-argument tool) when it has gathered enough, and to write the
  section on the next turn; the forced-turn sentence says "write the section" instead of "call
  emit_section". `SECTION_FINAL_TURN_MESSAGE_STREAMED` becomes `SECTION_WRITE_TURN_MESSAGE`
  ("Write the section now: reply with one JSON object, the emit_section arguments … The JSON
  object only, no code fence."). The `emit_section` schema, the read tools, the repair and the
  forced-tool final message keep their wording. Reason and probe: annex § Owner questions,
  item 1; `research/exp-stream-cache-probe.md`.

### Flagged deviations (minor, resolved within the contract's vocabulary)

1. **`PlanStep.row`** (public interface, additive; not on G1's list). N17 says the server's
   presentation table decides which stage keys share one card row and "the client decides
   nothing about rows". The only way the client can learn the grouping without a copy of
   its own is a key on the plan step, so `PlanStep` gains `row: str` and the server fills it
   from `STAGE_ROW`. The frontend and backend deploy together (owner, 2026-11-04).
2. **Stage derived once, in the harness.** N1 says the hook derives the stage from the
   structlog `component` through `STAGE_BY_REGISTRY`. The harness already knows the
   component, so it derives the stage there and binds it into the liveness context
   (`task_liveness(task_id, stage=...)`); the hook reads the bound stage. Same mapping,
   one place, and the loops need not name their stage.
3. **`stage.completed.counts`** (public interface, additive; not on G1's list). N17 says the
   count keys are chosen per stage on the server and the client has no copy; the first build
   put a copy of `STAGE_COUNTS` in the client (the frontend-designer flagged it), so the frame
   now carries `counts: [{value, noun}]` and the client renders them as given. The mock keeps a
   copy of the table to build its frames (a private fixture). Spec table updated.
4. **Grouped stages share a label.** `classify` and `appraise` share one row, so every
   surface that shows a stage label (the run status bar, the task list, the sidebar line)
   shows the row's name. As first built `acquire` and `screen` also shared a row ("Searching
   and screening") and the shared row was "Categorising". The owner changed this: round 8
   split search and screen into two rows, "Searching" and "Screening", and owner round 2
   renamed the classify and appraise row "Classifying". That is what ships.

### Open proposals from the frontend passes (for the polish cycle and the owner)

- The strip shows the writer's whole section line while writing; a short form ("Section 3 of 7")
  needs the server to ship one or the client to cut at the first middot.
- The built longlist view takes over when the walk ends (its own header, themes collapsed); keep
  the watched rows in place, or open the themes expanded after a watched build.
- Link the longlist's row names to the option card once the longlist read exists.
- `STAGE_ROW` and `STAGE_COUNTS` have no backend coverage test of their own yet (the vocabulary
  test covers labels and blurbs; the route-step verb test covers verbs).
- `planStart.ts` `START_SEARCH_CLASS` (the plan document's own Start button) could move to
  `Button variant="start"` (done).
- Add a `role` to `ArtefactSectionSkeleton` so key findings is not recognised by index and
  title; add a phase key to the writer tick so the client does not compare the server's text
  against "Writing". (`role` on `ArtefactSectionSkeleton`: done, round 7/8.)
- The `funnel` query does not refresh on ingest ticks (only evidence and landscape).

### Knowledge candidates (014 retro)

- Codex's sandbox has no Postgres and no localhost sockets (known), and the workspace
  spend cap can end a job mid-apply with no file list: `git status` after every Codex job,
  and every Codex partial needs a finishing brief that names what was found applied.
- A streamed strict `json_schema` response delivers `prose` incrementally on Bedrock; a
  streamed forced tool call delivers its arguments in one burst at the end (probe 1 vs 2).
- A pool thread runs a `Future` done-callback in an empty context: a callback that reads a
  contextvar (the bound task and stage) must carry the submitting thread's context with it
  (`core/done_callbacks.py`), or it publishes nothing in production and everything in a test.
- A new route step needs three rows, not one: `[steps]`, the per-route override, and
  `CACHE_MODES`; a missing cache-mode row raised inside the streamed call's broad `except`, so
  every streamed turn fell back to the forced tool call silently. A test now pins the cache
  table against the steps table.
- A frontend-designer run that must also take screenshots of transient mock states runs out of
  turns (150) before reporting; the screenshot round is better as its own brief.
- Tests that never ask for the `engine` fixture depended on an earlier test migrating the
  worker's database; adding tests reshuffled the order and exposed it (`conftest` now migrates
  once per worker before any test).
- The hub's queue drain: the SSE loop took one tick per 0.4 s poll; with deltas it must
  drain the whole queue per poll or the 32-slot queue evicts prose.

## Review findings (step 7, conversation C, 2026-11-09)

The review ran in a fresh conversation. Base: `origin/dev` (the local `dev` was one commit
behind, PR #113; the branch also carries two small `.claude/skills/task-cycle-*` edits that
record the owner's 2026-11-04 "do not commit review records" rule, read once by the adjudicator
and left as process-record commits). Self-verify gate before any lane: `make verify` green at
`a3e583c3` (first row of the table below).

### Lanes and cost

| Lane | Reviewer | Tokens | Findings |
|---|---|---:|---|
| Contract verifier | `contract-verifier` (Opus, read-only) | 227K | 3 high, 7 medium, 6 low; 16 owner-ruled contract items; the spec rows list |
| Security | `agent-skills:security-auditor` | 234K | 1 medium, 4 low, 4 informational; no critical or high |
| Adversarial (Codex stand-in) | `deep-reasoner` on the adversarial brief | 176K | 1 high, 6 medium, 5 low, 2 informational, one structural note |
| `/code-review medium` | the Claude half of the pair | 309K | 10 findings |
| Design lane | `frontend-designer`, read-only, 242 screenshots | 434K | 8 material fixes, 5 lower, 5 annex inconsistencies, 4 copy proposals |
| Trace lane | the lead, Langfuse (dev) | — | 4 findings |
| Fix builders | 2 × `deep-reasoner`, `frontend-designer`, `fast-worker` | 193K + 206K + 295K + 70K | — |

**The Codex adversarial lane did not run.** The `codex-rescue` job (`task-mw8meh61-h0vfk9`)
failed in 8 s on the workspace spend cap, as every Codex seam had in the build. A fresh Claude
reader on the same adversarial brief stood in, so the Tier 3 pair was two Claude contexts, not two
model families. Owner decision at step 9 (proposal C1): accept the substitution or lift the cap and
the lead re-runs the Codex lane before merge. The reasoning-class spend (1.38M) is 5.5 times the
routine ceiling on a diff about ten times a routine slice (66K code lines, 430 files; fifteen
owner polish rounds across the app); recorded in `docs/agentic-ops/failure-log.md`.

### Trace lane (the lead reading Langfuse for content)

- **A real stream fallback, visible only in the trace.** On 2026-11-06 22:47 UTC (trace
  `5d466d7f…`) a `synthesise:section_emit` turn ended in `ReadTimeout` after 32 s; a non-streamed
  `synthesise:section_turn` (2,227 output tokens) followed, then the judge and the repair as normal.
  So N6's fallback path worked once in real use, but the count lived in memory
  (`stream_fallbacks`) and a warning log line, and the fallback turn is indistinguishable by trace
  name from a research turn. **Fixed:** the synthesis component's completed payload carries
  `stream_fallbacks` per run (`synthesise.py` reads the backend's counter at entry and records
  the difference; a ponytail comment names the ceiling: two synthesis runs in one process can
  mis-attribute one). Test: `test_the_rollup_counts_only_this_runs_stream_fallbacks`.
- **The shortlist note refresh carried no session.** Seven `shortlist:note` generations since
  2026-11-08 have no `sessionId`; `api/routers/longlist.py`'s refresh route opened
  `trace_scope(user_id=...)` only. The build's "not proven by test" claim was false. **Fixed:**
  `session_id=task_id` on the scope; test `test_a_note_refresh_carries_the_tasks_session`.
- **The title generations are sibling root traces, not nested.** `chat:title` and
  `task_agent:title` are root traces with one generation each in the task's session (parent
  `None`), one second before `run:chat` or after the `task_agent:turn` spans. Adopted as built;
  the record now says "sibling in the session" (proposal C7 asks the owner whether to nest).
- **The unreproduced extra progress card** (round 15) stays a known unverified item: nothing in
  the server, the stream, the hub or the reducer produces it, and the owner's task id, view and
  screenshot are still needed.

### Adjudication

Every finding was adopted, declined with a reason, deferred to `docs/deferred.md` § Perceived
latency, or passed to the owner (`spec-changes-proposed.md`, local). Convergent findings across
lanes are marked ◆.

**Adopted and fixed in this phase (backend; builders A and B):**

1. ◆ One unserialisable hub message closed the stream for every reader and replayed on reconnect
   (security M; pydantic raises on a lone surrogate, which the streaming decoder passes through).
   `sse.py` skips a message it cannot encode and logs its type only; `liveness.py` makes every
   text that enters memory UTF-8 encodable (`_clean`). Two tests.
2. ◆ The model's query text was normalised on the writer's path only (security L, verifier M5).
   `normalise_query` moved to `core/liveness.py` with a `limit`; the hub applies it to every
   search query (`SEARCH_QUERY_MAX = 300` for the frame, a lead decision: the Search queries table
   shows whole queries; 120 stays the activity line's bound) and keys its memory on the clean text;
   `search_loop._short_query` normalises before its cut. Four tests.
3. ◆ Hub memory was swept only while a model call was open (security L, adversarial 12). The
   sweep is armed whenever any task has memory, so the 600 s TTL holds for a run that died; the
   runner's `run_plan` `except` path now calls `tick_hub.end_run` too. Test: a dead run is
   forgotten after the TTL.
4. ◆ A reconnect during the fallback kept a stale draft and case-study cards doubled on every
   reconnect (adversarial 3). The snapshot sends `replace` with the draft's text whenever a draft
   exists, empty or not, before sources, claims and cards; the reducer already clears claims and
   cards on `replace`. Hub tests updated; reducer test: two cards, not four.
5. A full subscriber queue evicted appends for good (adversarial 6, the half adopted). On
   `QueueFull` the hub empties the queue and refills it from the task's remembered state, draft
   first (`_remembered`, shared with the snapshot); messages fanned out before the resync are
   numbered and skipped so no text arrives twice. Ceiling: a resync longer than 32 messages is cut
   after the draft items. The poll-rate half is deferred (owner-tuned feel; measure first).
6. Counts could go backwards and a late callback recreated an ended stage (adversarial 8). The
   hub keeps the larger `done` for the same stage and total; `end_stage` marks the key ended and
   `publish_tick` ignores it until `task_liveness` binds the stage again (`open_stage`: the
   synthesise summaries pass and steering reruns reuse a stage key legitimately). Two tests; two
   test fakes gained a no-op `open_stage`.
7. Within one poll, live frames were written before durable rows committed earlier (adversarial
   9): the durable tail goes first. Test added.
8. A heartbeat never refreshed the stage entry, so the TTL dropped it mid-call (code review 3):
   an open call keeps its entry fresh. Test at 700 s.
9. ◆ The streamed turns sent no heartbeats (adversarial 5; the 32 s silent gap in the 2026-11-06
   trace). `synthesis_backend._open_model_call` brackets all four streamed calls with the same
   `model_call_opened`/`model_call_closed` pair `traced_attempts` uses. Test on the section stream,
   streamed and fallback paths.
10. The fallback left the section blank until `section_completed` (adversarial 11). Each
    fallback publishes its parsed result once as a `replace` (the case studies as cards). Four
    tests updated.
11. ◆ The planner's streamed turn retried only connection errors before the first token
    (adversarial 4, code review 1): it now retries whatever `tracing._retryable` retries (429,
    5xx), waits `Retry-After` up to 30 s, and counts `started` only once reply text reached the
    client. Attempts stay at two (a test the chat path shares pins it; lead decision, recorded).
    Four tests.
12. The task title was generated inside the stream worker while it held the turn lock (code
    review 2): it runs through `in_background` as `patch_plan` does; the rename still reaches the
    page as a `task.updated` frame (`task.renamed` maps to it). Test: `completed` does not wait for
    the title.
13. An abort chosen from a check-in card option lost its option id (code review 8): `extra` flows
    to `_persist_abort`; History can quote the card's words. Test extended.
14. Resuming a longlist walk past the join republished the fan-out count for a finished stage
    (code review 4): no poll when `component.completed` exists for the stage and walk. Test.
15. ◆ Archiving a project archived tasks that were mid-run (adversarial HIGH): the project route
    now skips a solo task whose latest walk is running or paused or whose dispatch is reserved,
    the same check the task route makes (the query exists in two places; one helper later). Test:
    `archived_task_count == 0`, the task stays active. Ceiling: `solo_task_count` in the confirm
    sentence still counts a mid-run task, so it can say one more than gets archived.
16. The summaries pass published `done` one ahead (code review 7): `done` counts finished blocks.
17. The shortlist note's link check was dropped silently (verifier M6). A re-ask would need new
    prompt text (lead-only, not written at the review), so the one writer takes a link out
    instead (`without_links`: a Markdown link keeps its words, any other word with a link mark is
    dropped) and logs it. Test `test_a_note_with_a_link_has_the_link_taken_out` replaces the
    removed dev test under a true name. Ceiling: the sentence can read ragged; a note re-ask is
    lead work for a later slice.
18. The planner prompt's text was built from an unhashed table and its version did not move
    through three content changes (verifier M1): `task_plan.py` is now in the hash guard's pinned
    set (44 files) and the version is `planner_v12` (lead; the 038 like-for-like ruling was
    038-only). Hash diff below.
19. `--token` on `scripts/stream_capture.py` removed; `--token-env` is the one way (security I).
20. Stale text (verifier L2): the `synthesise_section_emit` route comment (it kept the tools and
    sends no schema), the vocabulary test's temporary allowance, the `WorkspaceView` comment, the
    flagged deviation 4 wording, the open proposals already done, the D1 Luna bullet.
21. `STAGE_ROW` and `STAGE_COUNTS` have a coverage test against the stage keys (verifier M7).

**Adopted and fixed in this phase (frontend; builder C, design lane):** fifteen items, all applied
(`frontend-designer`, 295K tokens; it hit its 150-turn limit once on the screenshot round and
finished on a resume; 127 screenshots of one round under
`research/screenshots/review-design-fixes/`, not reviewed by the agent, no reshoot):

1. ◆ The four `<details>` with the browser's triangle (check-in steer, citation sheet theme item,
   check-in bundle queries, chat references) use `DisclosureChevron` (batch B rule).
2. The fold mark holds still when the stream is not connected (`LiveMark still`; the trace, the
   run status bar and the live section's action line). Lead ruling, now in DESIGN.md § Shapes:
   the mark turns while the stream is open and the run is live (heartbeats count as data); it
   holds still when the connection is down or motion is reduced. Test: no animation frames while
   the stream is closed.
3. The strength word prints the tier's name (`strengthTierName`), the same case on every surface.
4. The citation sheet's quote matches with and without its trailing stop; on no match it shows the
   quote at Body Navy only (round 12 ruling), never the passage twice. Three tests.
5. No "Show 0 documents" disclosure; the mock's cards and rows agree on the count.
6. "Paused · waiting on you" never splits in the sidebar trace.
7. No doubled full stop after a quoted sentence in History (`stopAfter`).
8. The report's three source counts agree: the server's `source_count` is the References count
   and the view read it right; the mock fixture was wrong (46 → 3; funnel cited 12 → 3).
9. The stepper's text "✓" is the icon module's `CheckIcon`.
10. One `prefersReducedMotion` (`ui/motion/motion.ts`); `PartCard`'s copy deleted.
11. Off-token colours and raw shadows defined once as tokens (`--color-hover-fill`,
    `--color-green-deep`, `--color-yellow-deep`, four tint edges, `--shadow-overlay`,
    `--shadow-tooltip` beside `--shadow-paper`) and referenced from twelve files; no visual change.
12. The mock plan carries the `ingest` step in the real order; the mock's theme counts sum their
    options.
13. DESIGN.md: the longlist meta line's stale "5 documents evaluated it" → the round-13 count;
    § Shapes carries the ruling from item 2.
14. Copy (lead): a finished row with no documents reads "No documents" ("No documents yet" while
    building); the theme item reads "Identified across N sources" with the shared Show/Hide
    disclosure; Share's heading is "Projects".
15. Code review 9 and 10: `useArchiveProject`'s docstring states the server's behaviour once;
    `formatMinutes` folded into `formatElapsed(seconds, { withSeconds })`.

Left as built by the agent and recorded as seams: the Findings table keeps its own quote
fallback (italic Grey over the passage) and the Sources table draws its own tick and cross SVGs;
`auth/DevTokenLoginPanel.tsx` keeps two raw colours (auth is off limits to agents); the
whitespace-normalised quote match still extends the highlight by up to 20 characters.

**Declined, with the reason:**

- The failed streamed call's usage is "lost" (adversarial 2, part): usage arrives on a stream's
  final chunk; a stream cut by the timeout has none. Honest absence; the ERROR generation marks it.
- Caps on the hub's lists (security, adversarial 12): bounded by the run's own counts (option
  searches publish no query frames, round 9; about 25 notes; a section's claims and cards);
  recorded as a seam, one line if ever needed.
- Attempts on the planner stream at `MODEL_CALL_ATTEMPTS` (3): the chat path shares the pinned
  "at most once" test; two attempts with the wider predicate is the change the finding asked for.
- The "Querying academic databases." blurb (verifier M7): removed by the owner's one-voice rewrite
  of every blurb (N17), not dropped.

**Deferred to `docs/deferred.md` § Perceived latency (task 058 seams):** the live channel's
database poll per wake-up; one blocked executor thread per planner or chat stream (pre-existing
pattern on chat, six threads on the 2-vCPU task); `cursor=0` replay cost and no per-user stream
cap; the planner lock taken before authorisation (pre-existing); offset paging skips under a
moving sort (tasks and projects); the projects list's triple membership scan; a timer thread per
coalesce window; chat's per-citation verdict; the case study's bold arriving at the swap; the hub
lists' run-bound size; the lost usage of a timed-out stream; the load-sensitive width test.

**Passed to the owner (`spec-changes-proposed.md`, local; decided at step 9):** the contract's
gates G1 (about forty interface items beyond the list; `RunOut.stages` and the longlist read
changed against the text), G2 (seven re-pins; section v12 is a behaviour change), **G3 (the
`project.archived_at` migration, owner-requested in round 11, never ratified on the record)**,
**G4 (three map packages, likewise)**, G6 (owner rounds 2 to 15), G7 and N25 (skipped); the
sixteen needs the owner ruled otherwise during polish; the § Out-of-scope items built on the
owner's notes; thirteen spec row groups for `web-api.md`; and eight decisions (C1 to C8): the
Codex substitution, in-progress options on the public leg, the blue "Shortlisted" words, two
turning marks on the Result tab, when the plan card appears, the pre-existing `react-router`
advisory (GHSA-qwww-vcr4-c8h2, fixed in 7.18.2; found by the review's `pnpm audit`), the sibling
title traces, and whether a second owner polish round is wanted. The three new packages carry no
advisories.

**Flagged deviations re-examined (task-cycle-review rule):** 1 `PlanStep.row` adopted as-is
(G1 amendment A1); 2 the stage derived in the harness adopted as-is; 3 `stage.completed.counts`
adopted as-is (A1); 4 grouped stages' labels: the owner changed them in rounds 2 and 8, the
deviation text was corrected to what ships.

**Known unverified items re-examined:** the extra progress card (still unreproduced; owner input
needed); the two trace nestings (both read on the instance: one false and fixed, one "sibling by
design"); chat's per-citation verdict (deferred seam); the D1 Luna check (text corrected to the
pre-fix schema); the Codex family flip (did not happen in the build or the review: C1).

**Fake-done check on this phase's fixes:** no test relaxed or deleted without its replacement
named here (the shortlist link test is replaced under a true name; `test_liveness` scheduling and
snapshot tests were rewritten for the new behaviour, each asserting more); no swallowed error
added (the SSE skip logs the type and continues, by design); no stub returns. `/simplify` and
`ponytail-review` were not run as separate passes: `/code-review medium` carried the reuse and
simplification angles (findings 9 and 10 of its ten) and their fixes are applied.

### Prompt-hash re-pin at the review

`python3 scripts/prompt_hash_guard.py --update` on 2026-11-09 (44 files, 43 before):
`runtime/task_agent_prompt.py` `1968366b…` → `e3c152b1…` (`PLANNER_PROMPT_VERSION`
`planner_v11` → `planner_v12`, the version comment only; the prompt text is unchanged since the
build's third re-pin); `runtime/task_plan.py` newly pinned at `7ebc3859…` (the band table the
planner prompt substitutes). The seven files the build re-pinned, for the record (verifier M2):
`section_prompt.py` (v12), `task_agent_prompt.py` (three times), `task_agent_scoping_prompt.py`
(v7), `option_profile_prompt.py` (v5), `shortlist_prompt.py` (v2), `shortlist_note_prompt.py`
(new), `title_prompt.py` (new); their hashes are the diff of `scripts/prompt_hashes.json` against
`origin/dev`.

### Owner decisions at step 9 (2026-11-09)

The owner took every item in `spec-changes-proposed.md` (local) in one sitting:

- **C1 accepted:** the Claude adversarial reader stands for the Codex lane (spend cap); no re-run.
- **C2 keep:** the options read stays on the public leg while the longlist is built (B13).
- **C3 keep:** the blue "Shortlisted" words on the option card.
- **C4 keep both:** the status bar's and the section's turning marks on the Result tab.
- **C5 keep:** the Search plan card from decision 1.
- **C6 go:** `react-router` bumped to 7.18.5 (clears GHSA-qwww-vcr4-c8h2, fixed in 7.18.2) in this PR.
- **C7 sibling:** the title traces stay their own root traces in the task's session.
- **C8 nod:** no further owner polish round beyond the notes already taken (round 16 landed the
  same day); the rubric's D11 line records it.
- **A1 to A9 and B1 to B13 accepted as written:** applied to `contract.md` (§ Amendments at
  the review; the gate table) and `docs/specs/system/web-api.md` (its 2026-11-09 log line).

## Rubric status (step 7)

Judged by the contract verifier (fresh context) and adjudicated by the lead; "owner-ruled" means
the annex records the owner's later ruling and `spec-changes-proposed.md` A8 carries the
contract amendment.

| # | Status | Evidence |
|---|---|---|
| 1 | Pass, with owner-ruled deviations | N1 to N24 and N26 built and tested; N25 skipped by the owner; sixteen needs ruled otherwise during polish (A8). |
| 2 | Pass | The gate table: build-open baseline, the combined backend gate for Phases 1 to 4 (frontend red by design until Phase 6), Phase 9, every round, the step-7 open gate and the step-7 fixes gate. |
| 3 | **Holds only with the owner's ratification** | G3: `project.archived_at` (owner request, round 11; A3). G4: `d3-geo`, `topojson-client`, `world-atlas` (round 11; A4). G1 exceeded by about forty items and G2 by five re-pins (A1, A2). No CI, prod config or auth change; no compatibility shim. |
| 4 | Pass | `drift-check: OK` in every gate row; `prompt-guard` green on 44 files. |
| 5 | Pass after the review | Deleted or moved tests and their replacements: `RunningCard.test.tsx` → `RunTrace.test.tsx`; `landingPresentation.test.ts` → `ui/brand/taskStatus.test.ts`; `presentRunDecisions` tests deleted with the feature (owner); the F6 case-studies test → the streamed card tests; the N17 client vocabulary tests (`planVocabulary.test.ts`: `timeBandFor`, `stepsForAnalysisDepth`, `acquireSearchBlurb`, `COMPONENT_LABEL`; `journey/presentation.test.ts`: approved summary keys) → `tests/api/test_stage_vocabulary.py` (every stage key has a presentation; every route step has a verb; every key has a row and a counts entry, added at the review) and `tests/runtime/test_task_agent.py` plus `tests/runtime/test_task_plan.py` (the bands and totals pinned); the shortlist note's link test → `test_a_note_with_a_link_has_the_link_taken_out` (review). Two option-profile tests skip verb lines (recorded in the Phases 6 to 8 row). No `skip` or `xfail` added. |
| 6 | Partial, by owner decision | Gates, commands, prompt-hash diffs (build and review), screenshots (gitignored research folder), the polish log and the owner's rulings are recorded; the N25 measures, the staging run and a live fallback count are not measured (owner, 2026-11-09); the fallback count is now durable for later runs. |
| 7 | Pass | `docs/deferred.md` § Perceived latency (task 058 seams): D6, D7, D9, D12, D13, D14 and the review's seams; thirteen earlier lines discharged or reworded. |
| 8 | Pass, with one substitution and the human gate open | Contract verifier, one security lane, `/code-review medium`, the design lane and the trace lane ran; the Codex adversarial lane failed on the spend cap and a fresh Claude reader stood in (C1); `/simplify` folded into the code review's cleanup angles (recorded); the contract- and plan-stage adversarial reviews are folded into those documents; ADR 0044 Accepted and amended; the human deep review is step 9. |
| 9 to 13 | Pass vs the latest ruling | Hub tests (coalescing, heartbeats, bounds, TTL, child walks, and the review's resync, clamp and ended-stage tests); route-step verbs; `freshness.ts`; `RunTrace` tests. The live screening line rests on the owner's runs. |
| 14 | Pass vs the owner's call shape | Fallback once, counted and now durable; decoder surrogate tests; heartbeats around the streamed turns (review). Not `json_schema` (A7). |
| 15 | Pass in code; spec rows pending | Reducer replay tests; the review's empty-replace and no-doubled-cards tests; nine ephemeral frames vs the spec's three (B1 to B3). |
| 16 | Pass vs owner rulings | Live region; the footer and claim-marker clauses owner-overridden (A8). |
| 17, 18 | Pass | Stream refusals before headers, disconnect, one terminal event; the review's 429 and 5xx retry tests; the reload case. |
| 19 to 24 | Pass or owner-overridden | Pre-writing states; the status bar as a button (A8); the sidebar trace; tab marks (Sources mark removed, A8); the Plan control off the nav (A8); Sources default by completed step (A8). |
| 25 | Pass | One server table; no client label literal; nineteen keys in the spec; the row and counts coverage test (review). |
| 26 to 29 | Pass or owner-overridden | Planner's order, no reason line, one "Looks right" button (A8); check-in shape; bands from one table (now hashed); "so far" dropped (A8). |
| 30 to 32 | Pass; 31 owner-asked | Options read tenancy tests; `RunOut.stages` added against the contract text (A1); the longlist during the build. |
| 33 | Not measured, owner decision | § N25 measures. |
| 34 | Pass | 36 Playwright journeys at the reviewed head (the last gate row). |
| 35 | Met, by owner decision | Agent passes at build end and at the review (the design lane and its fix pass); the owner's rounds were 2 to 16, each from live-run notes; the owner closed the polish on 2026-11-09 (C8: "nod"). Screenshots under the gitignored `research/screenshots/`. |

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md), listed at step 8.
