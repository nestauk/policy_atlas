# Verification: 058-perceived-latency

Evidence for one slice. Filled during the build (task-cycle-build, steps 5 and 6); the
review stack adds **Review findings** and **Rubric status** at step 7. Public-safe: no
secrets, no raw source text, no unredacted traces.

> Status: **Phases 0 to 9 built and committed (2026-11-05); the build pauses at two owner gates.** (1) Phase 10, the polish cycle: the agent pass and up to three owner rounds on the live dev app, in their own conversation (D11). (2) Phase 11, the measures: the four fixed questions before and after on the laptop, and the staging baseline (P16), each a real run whose cost the owner approves (plan Phase 0). Step 6's exit (the measures, the Luna strict check, the polish log, live-dev screenshots) follows those; the review stack then runs in a fresh conversation. Everything deterministic is done: every need N1 to N24 and N26 is implemented and tested; `make verify` and the mock journeys are green at `HEAD`.

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
| Round 12 (owner live-run notes, 2026-11-06, evening; six builders plus a consolidation pass) | lead: `make verify && pnpm e2e` on the combined tree | pass | backend 4,379 passed, 1 skipped (7 min 46 s) with `test_option_searches_run_at_the_configured_width` failing once under a load average above 200 and passing alone (a timing test: peak concurrency measured with 0.2 s sleeps; flagged for the review), mypy 470 files, ruff; infra 113; prompt-guard 41 unchanged (the scoping planner prompt re-pinned twice this round, lead); drift-check OK; frontend 107 files / 1,666 passed, build; Playwright 35 passed on the quiet tree (an earlier run failed two journeys while a builder's edits reloaded the page). Items: the scoping planner's Something else option and question decision (v7); the header name at Heading; the planner's reply in its own eased box; the sidebar and Agent tab reading closed Task Agent conversations; done scoping rows linking; decision n of M; the longlist closed by default with Navy names, right-aligned counts and controls, no contents nav, shortlisted first, the theme-and-lever hover, levers counted, the dossier over the card; the option card as what it is, Evidence (places, Your target and outcomes, documents in the References form with three fact lines) and What it could take (a code-built sentence with bold takeaways, the estimate hover), only two folds, the report's scale and square bullets; the shared Select; the gate card without the key assumption; the public link reaching the longlist and shortlist read-only; the report's expand state, badges with the table's tones, the citation sheet, method rows linking; Sources tones, Full text linking, Cited under the status, the two-row filter bar, the foot line with Download CSV, the page size and 25 a page, the Search queries section, queries filtering the table; the list gap fixed by a subgrid, Projects paged and ordered by the server, row menus (three dots) with rename, archive and Add to project on rows and the task header; the evidence vocabulary defined once in `ui/brand/evidence.ts` (owner's defined-once rule) and `BulletList`; backend: the option-search count from dispatch, combined / Estimating, places split, full_text_url, query_id and record ids, projects by last activity, 20 a page, the card export, option documents' authors and venue, the mock paging. Declined: live query ids before the step commits (a rolled-back step would reuse the sequence). |
| Round 11 (owner live-run notes, 2026-11-06; six builders: backend and store, the workspace, Options scoping, the report page, Sources and Landscape, the lists) | lead: `make verify && pnpm e2e` on the combined tree | pass | backend 4,373 passed, 1 skipped (6 min 3 s), mypy 470 files, ruff; infra 113; prompt-guard 41 unchanged; drift-check OK; frontend 103 files / 1,546 passed, build; Playwright 35 passed. Items: the square's pulse deeper with a scale and the citation wave as a visible sequence; scoping rows linking to Sources and Landscape; the baseline card keeping its link and steps once the longlist starts (`RunOut.stages`); ticks and the option-search stage naming their walk; option and theme names while clustering (`characterise.themes.stage`); the shortlist count reading the shortlist after the step; the shortlist toggle saying Remove on hover; the option card in three blocks and the longlist row cut down after a UX audit (`research/longlist-ux-review.md`); most relevant sources and case studies back in cards above the Full report, the date on its own line, the sources count linking to References, the method as a ruled table, blue x-height bullets; the Sources hover affordance and strength tone, the filter bar, the finished queries line with saved citation passes (`passes`), greyed inactive subtabs, clickable funnel rows, the population line removed, a List / Map choropleth (`d3-geo`, `topojson-client`, `world-atlas`); Archived as a quiet foot link in the open scope and Find as a magnifier; the name-and-menu header for tasks and projects, projects archivable (`project.archived_at`, migration c4e8a2f6d1b3), the reconnecting line in the run status bar's frame. Open: D1; the two live Searching rows on a longlist walk are the walk's own broad search beside the option searches (display ruling pending); scoping rulings 1, 4 and 42 vs the built longlist (owner). |
| Round 10 (owner, 2026-11-06; six builders from five read-only reviews: the report page, the Sources table and Landscape years, the list rows, Share and History, Options scoping, and the backend) | lead: `make verify && pnpm e2e` on the combined tree | pass | backend 4,365 passed, 1 skipped (7 min 17 s), mypy 470 files, ruff; okf-validate 200; infra 113; prompt-guard 41 unchanged; drift-check OK; frontend 100 files / 1,480 passed, build; Playwright 35 passed. Items: the question as the report's title on both pages, the facts line, references with addresses, markers as the one control with tooltip and sorted numbers, a heading outline, ruled lists, print without chrome; visible Sources filters with Country and a year range, fixed columns, a stacked phone row, the years drag range, the subtab remembered per task; the row's accessible name carrying its status, the name cell widened, dates as "5 Nov", Show more paging and an Archived view, the switcher's growing rule; History grouped by day with sentences naming the step and the actor, runs folded behind Show steps; Share reordered with a two-step public confirm and no blue fill; the longlist as one component with rows moving into themes, one primary on the shortlist page, the gate card in the settled language, scoping trace links; the backend's history sentences, the run touching the task's date, has_more paging, the country filter, the refusal message, the gate heading and the scoping mock. Open: D1 (themes open by default; switch `THEMES_OPEN_BY_DEFAULT`). |

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

Not yet run: the four fixed questions before and after (laptop) and the staging baseline
(P16) each run real model calls and were gated on the owner's go at plan time. The capture
tool and the gap measure are built and tested (Phase 0). The "before" captures must run on
`dev` (the old tick shape, mapped by the capture client), the "after" on this branch.

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

## Diff summary

Filled per phase as it lands; the flagged deviations are in § Review handoff.

## Intent & assumptions

- The hub API (`core/liveness.py`) was designed by the lead before any brief was written
  and is recorded in `research/briefs/hub-api.md` (gitignored research folder). Every
  Phase 1 and Phase 2 brief codes against it.

## Known unverified items

- No run of either capability has been watched on the live app with the new code; every
  surface is verified by unit tests, the mock journeys and screenshots of the mock. The first
  live runs are the N25 "after" runs.
- **D1 build-time check, done 2026-11-05** (`research/exp-luna-strict-check.md`, two live calls,
  cents): Luna accepted the streamed strict `json_schema` response with the raw
  `SectionProseWire` schema (what the section call sends) and with the strict-transformed one
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
4. **Grouped stages share a label.** `acquire` and `screen` both carry "Searching and
   screening", `classify` and `appraise` both "Categorising", so every surface that shows
   a stage label (the run status bar, the task list, the sidebar line) shows the row's name.

### Open proposals from the frontend passes (for the polish cycle and the owner)

- The strip shows the writer's whole section line while writing; a short form ("Section 3 of 7")
  needs the server to ship one or the client to cut at the first middot.
- The built longlist view takes over when the walk ends (its own header, themes collapsed); keep
  the watched rows in place, or open the themes expanded after a watched build.
- Link the longlist's row names to the option card once the longlist read exists.
- `STAGE_ROW` and `STAGE_COUNTS` have no backend coverage test of their own yet (the vocabulary
  test covers labels and blurbs; the route-step verb test covers verbs).
- `planStart.ts` `START_SEARCH_CLASS` (the plan document's own Start button) could move to
  `Button variant="start"`.
- Add a `role` to `ArtefactSectionSkeleton` so key findings is not recognised by index and
  title; add a phase key to the writer tick so the client does not compare the server's text
  against "Writing".
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

## Deferred work

Seams left open → [docs/deferred.md](../../deferred.md), listed at step 8.
